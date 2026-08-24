/* Real dice, in three dimensions, shared by everything in the app that rolls one.
 *
 * Every die is its own solid now — "this is 2 d20s, that is a d10": a d4 is a
 * tetrahedron, a d6 a cube, a d8 an octahedron, a d10 a pentagonal trapezohedron with
 * kite faces, a d12 a dodecahedron, a d20 an icosahedron, and a d100 is the percentile
 * pair of d10s every table actually throws. Each is built from its own vertex
 * construction rather than hand-written CSS transforms, for the same reason the
 * icosahedron was: twenty (or twelve, or ten) hand-transcribed transforms is the kind
 * of thing that is wrong in one place and nobody finds out which.
 *
 * The die lands on the number the *server* rolled. Nothing here decides anything — the
 * tumble is decoration, thrown away, and the landing orientation is computed from a
 * result that arrived before the animation started. A die that decided its own result
 * would be a second source of randomness in an app whose whole design is that the
 * engine owns the dice.
 */
(function () {
  "use strict";

  var PHI = (1 + Math.sqrt(5)) / 2;

  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]];
  }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function len(a) { return Math.sqrt(dot(a, a)); }
  function norm(a) { var l = len(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
  function centreOf(verts, face) {
    var c = [0, 0, 0];
    face.forEach(function (i) {
      c[0] += verts[i][0]; c[1] += verts[i][1]; c[2] += verts[i][2];
    });
    return [c[0] / face.length, c[1] / face.length, c[2] / face.length];
  }

  /* --- the solids -------------------------------------------------------------------
     Each construction returns {verts, faces}, faces as vertex-index lists. Vertex
     order within a face does not matter — faces are re-ordered by angle around their
     own centre before rendering. Every solid is normalised to the same circumradius,
     so a d8 and a d20 sit on the mat at the same visual weight. */

  function tetrahedron() {
    return { verts: [[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]],
             faces: [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]] };
  }

  function cube() {
    var v = [];
    [-1, 1].forEach(function (x) { [-1, 1].forEach(function (y) {
      [-1, 1].forEach(function (z) { v.push([x, y, z]); }); }); });
    // A face is the four vertices sharing one fixed coordinate.
    var faces = [];
    [0, 1, 2].forEach(function (axis) {
      [-1, 1].forEach(function (side) {
        faces.push(v.map(function (p, i) { return [p, i]; })
          .filter(function (pi) { return pi[0][axis] === side; })
          .map(function (pi) { return pi[1]; }));
      });
    });
    return { verts: v, faces: faces };
  }

  function octahedron() {
    var v = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]];
    var faces = [];
    [0, 1].forEach(function (x) { [2, 3].forEach(function (y) {
      [4, 5].forEach(function (z) { faces.push([x, y, z]); }); }); });
    return { verts: v, faces: faces };
  }

  /* The d10: a pentagonal trapezohedron. Ten kite faces, not triangles — the shape in
     the photograph. An equator of ten points zigzagging above and below the midline,
     an apex over each pole; each kite is an apex, two near equator points and the far
     one between them. */
  function trapezohedron() {
    var verts = [], faces = [];
    for (var k = 0; k < 10; k++) {
      var ang = Math.PI * 2 * k / 10;
      verts.push([Math.cos(ang), Math.sin(ang), (k % 2 === 0 ? 0.25 : -0.25)]);
    }
    verts.push([0, 0, 1.15]);      // 10: top apex
    verts.push([0, 0, -1.15]);     // 11: bottom apex
    for (var i = 0; i < 5; i++) {
      faces.push([10, (2 * i) % 10, (2 * i + 1) % 10, (2 * i + 2) % 10]);
      faces.push([11, (2 * i + 1) % 10, (2 * i + 2) % 10, (2 * i + 3) % 10]);
    }
    return { verts: verts, faces: faces };
  }

  function icosahedron() {
    var v = [];
    [-1, 1].forEach(function (a) { [-PHI, PHI].forEach(function (b) {
      v.push([0, a, b], [a, b, 0], [b, 0, a]); }); });
    // Faces found, not listed: every triple of vertices pairwise one edge apart.
    var faces = [], edge = 4.0, eps = 0.001;
    function d2(a, b) { var d = sub(a, b); return dot(d, d); }
    for (var i = 0; i < v.length; i++)
      for (var j = i + 1; j < v.length; j++) {
        if (Math.abs(d2(v[i], v[j]) - edge) > eps) continue;
        for (var k = j + 1; k < v.length; k++)
          if (Math.abs(d2(v[i], v[k]) - edge) < eps &&
              Math.abs(d2(v[j], v[k]) - edge) < eps) faces.push([i, j, k]);
      }
    return { verts: v, faces: faces };
  }

  /* The dodecahedron's pentagons are found rather than listed: its twelve face
     directions are the icosahedron's twelve vertices, and each face is the five
     dodecahedron vertices leaning furthest that way. */
  function dodecahedron() {
    var v = [];
    [-1, 1].forEach(function (x) { [-1, 1].forEach(function (y) {
      [-1, 1].forEach(function (z) { v.push([x, y, z]); }); }); });
    [-1, 1].forEach(function (a) { [-1, 1].forEach(function (b) {
      v.push([0, a / PHI, b * PHI], [a / PHI, b * PHI, 0], [a * PHI, 0, b / PHI]);
    }); });
    var dirs = icosahedron().verts;
    var faces = dirs.map(function (dir) {
      var n = norm(dir);
      return v.map(function (p, i) { return [dot(norm(p), n), i]; })
        .sort(function (a, b) { return b[0] - a[0]; })
        .slice(0, 5).map(function (x) { return x[1]; });
    });
    return { verts: v, faces: faces };
  }

  /* --- solid preparation ------------------------------------------------------------
     Normalise to a shared circumradius, order each face's vertices by angle, compute
     centres and outward normals, and number the faces so opposite ones sum the way a
     real die's do. Done once per shape and cached. */
  var TARGET_R = 1.9;   // the icosahedron's own circumradius — the size everything had

  function prepare(raw, zeroBased) {
    var maxR = Math.max.apply(null, raw.verts.map(len));
    var verts = raw.verts.map(function (p) {
      return [p[0] * TARGET_R / maxR, p[1] * TARGET_R / maxR, p[2] * TARGET_R / maxR];
    });
    var faces = raw.faces.map(function (face) {
      var c = centreOf(verts, face);
      var z = norm(c);
      var y0 = norm(sub(verts[face[0]], c));
      var x0 = norm(cross(y0, z));
      var ordered = face.slice().sort(function (a, b) {
        function ang(i) {
          var d = sub(verts[i], c);
          return Math.atan2(dot(d, y0), dot(d, x0));
        }
        return ang(a) - ang(b);
      });
      return { idx: ordered, centre: c, normal: z };
    });

    // Opposite faces sum to faces+1 — or faces-1 zero-based, the way a real d10's 0
    // backs onto its 9 — found by looking for the negated normal rather than assumed
    // from construction order. A tetrahedron has no opposite faces; the gaps fill in
    // order afterwards.
    var n = faces.length;
    var numbers = new Array(n).fill(null), next = zeroBased ? 0 : 1;
    var total = zeroBased ? n - 1 : n + 1;
    for (var i = 0; i < n; i++) {
      if (numbers[i] !== null) continue;
      var opp = -1;
      for (var j = 0; j < n; j++)
        if (j !== i && dot(faces[i].normal, faces[j].normal) < -0.98) { opp = j; break; }
      numbers[i] = next;
      if (opp >= 0) numbers[opp] = total - next;
      next++;
    }
    var used = {}, fill = zeroBased ? 0 : 1;
    numbers = numbers.map(function (x) {
      if (x !== null && !used[x]) { used[x] = true; return x; }
      while (used[fill]) fill++;
      used[fill] = true;
      return fill;
    });

    return { verts: verts, faces: faces, numbers: numbers };
  }

  var SHAPES = {};
  function shape(sides) {
    if (!SHAPES[sides]) {
      SHAPES[sides] =
        sides === 4 ? prepare(tetrahedron()) :
        sides === 6 ? prepare(cube()) :
        sides === 8 ? prepare(octahedron()) :
        sides === 10 ? prepare(trapezohedron(), true) :
        sides === 12 ? prepare(dodecahedron()) :
        prepare(icosahedron());
    }
    return SHAPES[sides];
  }

  /* --- rendering one solid into a host element -------------------------------------- */
  var PX = 60;   // world units to pixels

  function buildSolid(host, sides) {
    if (host.dataset.shape === String(sides)) {
      return Array.prototype.slice.call(host.children);
    }
    host.dataset.shape = String(sides);
    host.innerHTML = "";
    var s = shape(sides), els = [];
    s.faces.forEach(function (f) {
      // The face projected into its own plane gives both the clip-path outline and
      // the element box; the face basis, column by column, is what matrix3d takes.
      var z = f.normal;
      var y0 = norm(sub(s.verts[f.idx[0]], f.centre));
      var x0 = norm(cross(y0, z));
      var pts = f.idx.map(function (vi) {
        var d = sub(s.verts[vi], f.centre);
        return [dot(d, x0) * PX, dot(d, y0) * PX];
      });
      var hw = Math.max.apply(null, pts.map(function (p) { return Math.abs(p[0]); }));
      var hh = Math.max.apply(null, pts.map(function (p) { return Math.abs(p[1]); }));
      var el = document.createElement("div");
      el.className = "f";
      el.style.width = (hw * 2) + "px";
      el.style.height = (hh * 2) + "px";
      el.style.left = (-hw) + "px";
      el.style.top = (-hh) + "px";
      el.style.clipPath = "polygon(" + pts.map(function (p) {
        return ((p[0] + hw) / (hw * 2) * 100).toFixed(2) + "% " +
               ((p[1] + hh) / (hh * 2) * 100).toFixed(2) + "%";
      }).join(",") + ")";
      var t = [f.centre[0] * PX, f.centre[1] * PX, f.centre[2] * PX];
      el.style.transform = "matrix3d(" + [x0[0], x0[1], x0[2], 0,
                                          y0[0], y0[1], y0[2], 0,
                                          z[0], z[1], z[2], 0,
                                          t[0], t[1], t[2], 1].join(",") + ")";
      // A fixed light, baked per face — what makes flat polygons read as one object.
      var lit = dot(z, norm([-0.35, -0.75, 0.56]));
      el.style.filter = "brightness(" + (0.62 + 0.55 * Math.max(0, lit)).toFixed(3) + ")";
      host.appendChild(el);
      els.push(el);
    });
    return els;
  }

  function faceToFront(sides, index) {
    var n = shape(sides).faces[index].normal, front = [0, 0, 1];
    var d = Math.max(-1, Math.min(1, dot(n, front)));
    var angle = Math.acos(d) * 180 / Math.PI;
    var axis = cross(n, front);
    if (len(axis) < 1e-6) return d > 0 ? "rotate3d(1,0,0,0deg)" : "rotate3d(1,0,0,180deg)";
    axis = norm(axis);
    return "rotate3d(" + axis[0] + "," + axis[1] + "," + axis[2] + "," + angle + "deg)";
  }

  /* --- the mat ---------------------------------------------------------------------- */
  var STYLE = [
    "#d3d-mat{position:fixed;inset:0;z-index:60;display:none;align-items:center;",
    "justify-content:center;background:radial-gradient(60% 50% at 50% 40%,",
    "rgba(10,8,6,.74),rgba(4,3,3,.92));font:15px/1.55 'Palatino Linotype',Palatino,Georgia,serif}",
    "#d3d-mat.on{display:flex}",
    "#d3d-card{width:380px;max-width:92vw;padding:24px 26px 22px;border-radius:3px;",
    "background:linear-gradient(rgba(27,22,17,.96),rgba(18,15,11,.97));",
    "border:1px solid #7a6543;box-shadow:inset 0 0 0 1px rgba(221,196,142,.08),",
    "0 18px 60px rgba(0,0,0,.8);color:#e6dcc6}",
    "#d3d-card h3{margin:0 0 2px;color:#d9c08a;text-align:center;letter-spacing:.06em;",
    "font:400 22px/1.2 'Cinzel','Palatino Linotype',Georgia,serif;font-variant:small-caps}",
    "#d3d-why{color:#8e816a;font-style:italic;font-size:13px;text-align:center;margin-bottom:6px}",
    "#d3d-stage{height:190px;display:flex;align-items:center;justify-content:center;",
    "perspective:760px}",
    "#d3d-die,#d3d-die2{position:relative;width:0;height:0;transform-style:preserve-3d}",
    "#d3d-stage.pair #d3d-die{margin-right:150px}",
    "#d3d-die2{margin-left:150px;display:none}",
    "#d3d-die .f,#d3d-die2 .f{position:absolute;",
    "display:flex;align-items:center;justify-content:center;",
    "font:400 26px/1 'Cinzel','Palatino Linotype',Georgia,serif;",
    "background:linear-gradient(#2c2318,#191309);color:#c9b489;",
    "backface-visibility:hidden}",
    "#d3d-die .f.land,#d3d-die2 .f.land{background:linear-gradient(#3a2f1d,#241c10);",
    "color:#f0dcae}",
    "#d3d-die .f.land.crit{color:#6fcf8f;background:linear-gradient(#1d3a28,#122117)}",
    "#d3d-die .f.land.fumble{color:#d9776b;background:linear-gradient(#3a1d1a,#210f0d)}",
    "#d3d-terms{background:rgba(0,0,0,.34);border:1px solid #2b2319;border-radius:2px;",
    "padding:10px 12px;margin:6px 0 4px}",
    "#d3d-terms .r{display:flex;justify-content:space-between;font-size:13px;color:#8e816a}",
    "#d3d-terms .r b{color:#e6dcc6;font-weight:400;font-variant-numeric:tabular-nums}",
    "#d3d-terms .r.tot{border-top:1px solid #3a3022;margin-top:6px;padding-top:6px;color:#d9c08a}",
    "#d3d-terms .r.tot b{color:#d9c08a}",
    "#d3d-verdict{text-align:center;margin:12px 0;min-height:19px;letter-spacing:.07em;",
    "font:400 19px/1 'Cinzel','Palatino Linotype',Georgia,serif;font-variant:small-caps}",
    "#d3d-verdict.good{color:#6fcf8f}#d3d-verdict.bad{color:#d9776b}",
    "#d3d-note{color:#8e816a;font-size:12.5px;text-align:center;margin-bottom:10px}",
    "#d3d-acts{display:flex;gap:8px}",
    "#d3d-acts button{flex:1;cursor:pointer;border-radius:2px;padding:11px 14px;",
    "color:#d9c08a;background:linear-gradient(#2a2114,#1a140c);border:1px solid #7a6543;",
    "letter-spacing:.08em;font:400 15px/1 'Cinzel','Palatino Linotype',Georgia,serif;",
    "font-variant:small-caps}",
    "#d3d-acts button:hover:not(:disabled){border-color:#c9a86a;color:#f0dcae}",
    "#d3d-acts button:disabled{opacity:.4;cursor:not-allowed}",
    "#d3d-acts button.ghost{opacity:.55;flex:0 0 auto;font-size:12px;padding:11px 12px}",
    "#d3d-acts button.ghost:hover{opacity:1}",
    "#d3d-own{display:none;gap:6px;margin-bottom:10px}",
    "#d3d-own.on{display:flex}",
    "#d3d-own input{flex:1;padding:10px;text-align:center;border-radius:2px;color:#d9c08a;",
    "background:#0c0a08;border:1px solid #7a6543;font:400 17px/1 'Cinzel',Georgia,serif;",
    "font-variant-numeric:tabular-nums}",
    "#d3d-own input:focus{outline:none;border-color:#c9a86a}",
  ].join("");

  var mat, die, die2, DEBUG_KEY = "pfgm.dice.manual";

  function debugOn() {
    try { return localStorage.getItem(DEBUG_KEY) === "1"; } catch (e) { return false; }
  }

  function build() {
    if (mat) return;
    var style = document.createElement("style");
    style.textContent = STYLE;
    document.head.appendChild(style);

    mat = document.createElement("div");
    mat.id = "d3d-mat";
    mat.innerHTML =
      '<div id="d3d-card">' +
      '<h3 id="d3d-title">Roll</h3>' +
      '<div id="d3d-why"></div>' +
      '<div id="d3d-stage"><div id="d3d-die"></div><div id="d3d-die2"></div></div>' +
      '<div id="d3d-terms"></div>' +
      '<div id="d3d-verdict"></div>' +
      '<div id="d3d-note"></div>' +
      '<div id="d3d-own"><input type="number" id="d3d-face"></div>' +
      '<div id="d3d-acts">' +
      '<button id="d3d-go">Roll</button>' +
      '<button class="ghost" id="d3d-debug" title="Enter the result of a die you rolled ' +
      'yourself">my own roll</button>' +
      '</div></div>';
    document.body.appendChild(mat);
    die = mat.querySelector("#d3d-die");
    die2 = mat.querySelector("#d3d-die2");

    mat.querySelector("#d3d-debug").addEventListener("click", function () {
      var on = !debugOn();
      try { localStorage.setItem(DEBUG_KEY, on ? "1" : "0"); } catch (e) { /* private */ }
      showOwn(on);
    });
  }

  function showOwn(on) {
    var box = mat.querySelector("#d3d-own");
    box.classList.toggle("on", on);
    mat.querySelector("#d3d-debug").textContent = on ? "roll it for me" : "my own roll";
    if (on) mat.querySelector("#d3d-face").focus();
  }

  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function spin() {
    return "rotateX(" + (Math.random() * 360 | 0) + "deg) rotateY(" +
           (Math.random() * 360 | 0) + "deg) rotateZ(" + (Math.random() * 360 | 0) + "deg)";
  }

  function resetMat(opts, dieLabel) {
    mat.querySelector("#d3d-title").textContent = opts.title || "Roll";
    mat.querySelector("#d3d-why").textContent =
      (opts.why || "") + (dieLabel ? (opts.why ? " — " : "") + dieLabel : "");
    mat.querySelector("#d3d-terms").innerHTML = "";
    mat.querySelector("#d3d-verdict").textContent = "";
    mat.querySelector("#d3d-verdict").className = "";
    mat.querySelector("#d3d-note").textContent = "";
    mat.querySelector("#d3d-own").classList.remove("on");
    mat.querySelector("#d3d-debug").style.display = "none";
    mat.querySelector("#d3d-go").textContent = "…";
    mat.querySelector("#d3d-go").disabled = true;
    mat.classList.add("on");
  }

  function fillTerms(terms) {
    mat.querySelector("#d3d-terms").innerHTML += (terms || []).map(function (x) {
      return '<div class="r' + (x.total ? " tot" : "") + '"><span>' + esc(x.label) +
             "</span><b>" + esc(String(x.value)) + "</b></div>";
    }).join("");
  }

  function finish(opts, result) {
    if (opts.verdict) {
      var v = mat.querySelector("#d3d-verdict");
      v.textContent = opts.verdict.text;
      v.className = opts.verdict.good ? "good" : opts.verdict.good === false ? "bad" : "";
    }
    if (opts.note) mat.querySelector("#d3d-note").textContent = opts.note;
    mat.querySelector("#d3d-go").textContent = "Close";
    mat.querySelector("#d3d-go").disabled = false;
    return new Promise(function (done) {
      mat.querySelector("#d3d-go").onclick = function () {
        mat.classList.remove("on");
        mat.querySelector("#d3d-stage").classList.remove("pair");
        die2.style.display = "none";
        done(result);
      };
    });
  }

  /* Which solid a request rolls on. An exact die uses its own shape; a pooled total —
     2d6's 2 to 12, say — uses the smallest solid with enough faces for its whole
     range, labelled with real values from it. */
  function solidFor(lo, hi) {
    var span = hi - lo + 1;
    var order = [4, 6, 8, 10, 12, 20];
    for (var i = 0; i < order.length; i++) if (span === order[i]) return order[i];
    for (var j = 0; j < order.length; j++) if (span <= order[j]) return order[j];
    return 20;
  }

  function labelFaces(els, sides, lo, hi, result) {
    var s = shape(sides), span = hi - lo + 1, n = els.length;
    var landing = -1;
    for (var i = 0; i < n; i++) {
      var value;
      if (span === n) {
        // The die's own numbering — a d10 wears 0-9, everything else 1..N — shifted
        // when the range starts somewhere other than the die's own first face.
        value = s.numbers[i] + (lo - (sides === 10 ? 0 : 1));
      } else if (span < n) {
        value = lo + (i % span);
      } else {
        // More range than faces: values spread across it, jittered off a printed
        // scale, every one a number this roll could genuinely have produced.
        var base = lo + Math.round((span - 1) * (i + 0.5) / n);
        value = Math.max(lo, Math.min(hi, base + (Math.floor(Math.random() * 5) - 2)));
      }
      els[i].textContent = value;
      els[i].className = "f";
      if (value === result && landing < 0) landing = i;
    }
    if (landing < 0) {
      landing = Math.floor(Math.random() * n);
      els[landing].textContent = result;
    }
    return landing;
  }

  async function tumble(el, landTransform, slower) {
    el.style.transition = "none";
    for (var g = 0; g < 7; g++) {
      el.style.transform = spin();
      await wait([60, 60, 65, 75, 90, 110, 140][g]);
    }
    el.style.transition = "transform " + (slower ? ".95s" : ".85s") +
                          " cubic-bezier(.16,.9,.3,1)";
    el.style.transform = "rotateY(" + (slower ? "-" : "") + "720deg) " + landTransform;
    await wait(slower ? 980 : 880);
  }

  /* Roll and settle on `result`. Resolves when the mat is closed. */
  function land(opts) {
    build();
    var reqSides = opts.sides || 20;
    if (reqSides === 100) return landPercentile(opts);
    var lo = opts.lo != null ? opts.lo : 1;
    var hi = opts.hi != null ? opts.hi : reqSides;
    var sides = solidFor(lo, hi);
    var els = buildSolid(die, sides);
    resetMat(opts, "d" + reqSides);

    var landing = labelFaces(els, sides, lo, hi, opts.result);
    return (async function () {
      await tumble(die, faceToFront(sides, landing));
      els[landing].classList.add("land");
      if (reqSides === 20 && opts.result === 20) els[landing].classList.add("crit");
      if (reqSides === 20 && opts.result === 1) els[landing].classList.add("fumble");
      fillTerms(opts.terms);
      return finish(opts, opts.result);
    })();
  }

  /* The percentile pair: tens and ones, both true d10s, settling a beat apart. */
  function landPercentile(opts) {
    var result = Math.max(1, Math.min(100, opts.result | 0));
    var tens = Math.floor((result % 100) / 10);
    var ones = result % 10;
    mat || build();
    build();
    mat.querySelector("#d3d-stage").classList.add("pair");
    die2.style.display = "";
    var elsA = buildSolid(die, 10), elsB = buildSolid(die2, 10);
    resetMat(opts, "percentile dice");

    var s = shape(10), landA = 0, landB = 0;
    for (var i = 0; i < elsA.length; i++) {
      elsA[i].textContent = ("0" + (s.numbers[i] * 10)).slice(-2);
      elsA[i].className = "f";
      elsB[i].textContent = s.numbers[i];
      elsB[i].className = "f";
      if (s.numbers[i] === tens) landA = i;
      if (s.numbers[i] === ones) landB = i;
    }
    return (async function () {
      await Promise.all([
        tumble(die, faceToFront(10, landA)),
        tumble(die2, faceToFront(10, landB), true),
      ]);
      elsA[landA].classList.add("land");
      elsB[landB].classList.add("land");
      mat.querySelector("#d3d-terms").innerHTML =
        '<div class="r"><span>tens</span><b>' + ("0" + tens * 10).slice(-2) + "</b></div>" +
        '<div class="r"><span>ones</span><b>' + ones + "</b></div>" +
        '<div class="r tot"><span>d100</span><b>' + result + "</b></div>";
      fillTerms(opts.terms);
      return finish(opts, result);
    })();
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* Ask the player for a roll: resolves with their own number (debug toggle) or null,
     meaning "the table rolls it" — the default, and what the 3D die is for. */
  function ask(opts) {
    build();
    var reqSides = opts.sides || 20;
    var lo = opts.lo != null ? opts.lo : 1;
    var hi = opts.hi != null ? opts.hi : reqSides;
    var sides = reqSides === 100 ? 10 : solidFor(lo, hi);
    var els = buildSolid(die, sides);
    var s = shape(sides);
    for (var i = 0; i < els.length; i++) {
      els[i].textContent = s.numbers[i];
      els[i].className = "f";
    }
    die.style.transition = "none";
    die.style.transform = "rotateX(-18deg) rotateY(24deg)";

    resetMat(opts, opts.die || ("d" + reqSides));
    fillTerms(opts.terms);
    if (opts.note) mat.querySelector("#d3d-note").textContent = opts.note;
    var face = mat.querySelector("#d3d-face");
    face.min = lo; face.max = hi; face.value = "";
    face.placeholder = opts.die || ("d" + reqSides);
    mat.querySelector("#d3d-go").textContent = "Roll";
    mat.querySelector("#d3d-go").disabled = false;
    mat.querySelector("#d3d-debug").style.display = "";
    showOwn(debugOn());

    return new Promise(function (done) {
      function close(value) { mat.classList.remove("on"); done(value); }
      mat.querySelector("#d3d-go").onclick = function () {
        if (debugOn()) {
          var v = parseInt(face.value, 10);
          if (!(v >= lo && v <= hi)) { face.focus(); return; }
          close(v);
        } else {
          close(null);
        }
      };
      face.onkeydown = function (e) {
        if (e.key === "Enter") mat.querySelector("#d3d-go").click();
      };
    });
  }

  window.Dice3D = {
    land: land,
    ask: ask,
    // Exposed for probes: the d20's numbering and geometry, plus every shape by sides.
    faces: shape(20).faces.length,
    numbers: shape(20).numbers.slice(),
    _centres: shape(20).faces.map(function (f) { return f.centre; }),
    _shape: shape,
  };
})();
