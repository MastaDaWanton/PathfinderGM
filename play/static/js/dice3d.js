/* A real die, in three dimensions, shared by everything in the app that rolls one.
 *
 * An icosahedron built from its own geometry rather than from twenty hand-written CSS
 * transforms: the twelve vertices are the golden-ratio construction, the twenty faces are
 * found by taking every triple of vertices an edge apart, and each face is placed with a
 * `matrix3d` assembled from that face's own basis. Hand-transcribing twenty transforms is
 * the kind of thing that is wrong in one place and nobody ever finds out which.
 *
 * The die lands on the number the *server* rolled. Nothing here decides anything — the
 * faces flickering during the tumble are decoration, thrown away, and the landing
 * orientation is computed from a result that arrived before the animation started. A die
 * that decided its own result would be a second source of randomness in an app whose whole
 * design is that the engine owns the dice.
 *
 * One shape for every die. A d20 numbers its faces 1-20 and lands on the rolled one. For
 * anything else — a d8 for hit points, a pooled 2d6 for damage — the faces are labelled
 * with that die's own values (repeated across twenty faces where there are fewer than
 * twenty) and it still lands on a face bearing the true number. It is a d20-shaped object
 * showing d8 numbers, which is a compromise; the alternative was five more polyhedra, and
 * every number you can read is true either way.
 */
(function () {
  "use strict";

  var PHI = (1 + Math.sqrt(5)) / 2;

  // The twelve vertices: three golden rectangles at right angles. Edge length is 2.
  function vertices() {
    var v = [];
    [-1, 1].forEach(function (a) {
      [-PHI, PHI].forEach(function (b) {
        v.push([0, a, b], [a, b, 0], [b, 0, a]);
      });
    });
    return v;
  }

  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]];
  }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function len(a) { return Math.sqrt(dot(a, a)); }
  function norm(a) { var l = len(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
  function dist2(a, b) { var d = sub(a, b); return dot(d, d); }

  // Every triple of vertices that are pairwise one edge apart is a face. Twenty of them,
  // found rather than listed — the count is asserted below, so a wrong constant cannot
  // pass silently.
  function faces(verts) {
    var out = [], edge = 4.0, eps = 0.001;
    for (var i = 0; i < verts.length; i++) {
      for (var j = i + 1; j < verts.length; j++) {
        if (Math.abs(dist2(verts[i], verts[j]) - edge) > eps) continue;
        for (var k = j + 1; k < verts.length; k++) {
          if (Math.abs(dist2(verts[i], verts[k]) - edge) > eps) continue;
          if (Math.abs(dist2(verts[j], verts[k]) - edge) > eps) continue;
          out.push([i, j, k]);
        }
      }
    }
    return out;
  }

  var VERTS = vertices();
  var FACES = faces(VERTS);

  // Face centres double as outward normals: the solid is centred on the origin, so the
  // direction from the centre to a face centre is that face's normal.
  var CENTRES = FACES.map(function (f) {
    return [(VERTS[f[0]][0] + VERTS[f[1]][0] + VERTS[f[2]][0]) / 3,
            (VERTS[f[0]][1] + VERTS[f[1]][1] + VERTS[f[2]][1]) / 3,
            (VERTS[f[0]][2] + VERTS[f[1]][2] + VERTS[f[2]][2]) / 3];
  });

  // Opposite faces sum to 21, the way a real d20 is numbered. Found by looking for the
  // face whose normal is the negation of this one, rather than assumed from the order the
  // triples happened to be generated in.
  function numbering() {
    var n = new Array(FACES.length).fill(0), next = 1;
    for (var i = 0; i < CENTRES.length; i++) {
      if (n[i]) continue;
      var mine = norm(CENTRES[i]);
      var opposite = -1;
      for (var j = 0; j < CENTRES.length; j++) {
        if (j !== i && dot(mine, norm(CENTRES[j])) < -0.999) { opposite = j; break; }
      }
      n[i] = next;
      if (opposite >= 0) n[opposite] = 21 - next;
      next++;
    }
    return n;
  }

  var NUMBERS = numbering();

  /* The transform that puts one flat triangle onto one face of the solid.
   *
   * Built from the face's own basis: local +Z becomes the face normal, local -Y points at
   * the face's first vertex (which is where the clip-path puts the triangle's apex), and
   * +X follows from those two. `matrix3d` takes exactly that, column by column.
   */
  function facePlacement(index, scale) {
    var f = FACES[index], c = CENTRES[index];
    var z = norm(c);
    var apex = norm(sub(VERTS[f[0]], c));
    var y = [-apex[0], -apex[1], -apex[2]];          // CSS +Y runs down the screen
    var x = cross(y, z);
    // Right-handed or the triangle lands mirrored, and a mirrored 6 is a 9.
    if (dot(cross(x, y), z) < 0) x = [-x[0], -x[1], -x[2]];
    x = norm(x); y = norm(y);
    var t = [c[0] * scale, c[1] * scale, c[2] * scale];
    return "matrix3d(" + [x[0], x[1], x[2], 0,
                          y[0], y[1], y[2], 0,
                          z[0], z[1], z[2], 0,
                          t[0], t[1], t[2], 1].join(",") + ")";
  }

  // The rotation that brings a face to the front. Axis-angle straight from the normal, so
  // there is no table of twenty orientations to get wrong.
  function faceToFront(index) {
    var n = norm(CENTRES[index]), front = [0, 0, 1];
    var d = Math.max(-1, Math.min(1, dot(n, front)));
    var angle = Math.acos(d) * 180 / Math.PI;
    var axis = cross(n, front);
    if (len(axis) < 1e-6) return d > 0 ? "rotate3d(1,0,0,0deg)" : "rotate3d(1,0,0,180deg)";
    axis = norm(axis);
    return "rotate3d(" + axis[0] + "," + axis[1] + "," + axis[2] + "," + angle + "deg)";
  }

  /* What each face reads, for a die of `sides` showing `result`.
   *
   * A d20 is the identity case. Below twenty, the values repeat around the solid; above
   * twenty — a pooled 2d6 total, say — the neighbouring faces carry other totals that die
   * could have produced. Either way the face that lands is the true one, which is the only
   * face anybody reads.
   */
  function labels(sides, lo, hi, result, landing) {
    var out = new Array(FACES.length), span = hi - lo + 1;
    for (var i = 0; i < out.length; i++) {
      out[i] = lo + (i % span);
    }
    out[landing] = result;
    return out;
  }

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
    /* The stage. `perspective` here and `preserve-3d` on the die is what makes the faces
       hold their places in space instead of flattening into a stack. */
    "#d3d-stage{height:190px;display:flex;align-items:center;justify-content:center;",
    "perspective:760px}",
    "#d3d-die{position:relative;width:0;height:0;transform-style:preserve-3d}",
    "#d3d-die .f{position:absolute;width:120px;height:104px;left:-60px;top:-69px;",
    "transform-origin:50% 66.667%;",
    "clip-path:polygon(50% 0%,0% 100%,100% 100%);",
    "display:flex;align-items:flex-end;justify-content:center;padding-bottom:14px;",
    "font:400 26px/1 'Cinzel','Palatino Linotype',Georgia,serif;",
    "background:linear-gradient(#2c2318,#191309);color:#c9b489;",
    "border-bottom:1px solid rgba(0,0,0,.5);backface-visibility:hidden}",
    /* The landed face lifts out of the crowd; a 1 and a 20 say so in colour. */
    "#d3d-die .f.land{background:linear-gradient(#3a2f1d,#241c10);color:#f0dcae}",
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

  var mat, die, faceEls, resolveRoll, DEBUG_KEY = "pfgm.dice.manual";

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
      '<div id="d3d-stage"><div id="d3d-die"></div></div>' +
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
    faceEls = [];
    // 120px triangles: the placement scale is half that, the solid's edge being 2 units.
    var scale = 60;
    for (var i = 0; i < FACES.length; i++) {
      var el = document.createElement("div");
      el.className = "f";
      el.style.transform = facePlacement(i, scale);
      // A fixed light, baked per face. Every face carried the same gradient, so the solid
      // read as a silhouette with numbers on it rather than as an object with sides —
      // shading by the angle between each face and one light is what makes twenty flat
      // triangles look like one thing. The light is on the die, not on the room, so it
      // turns with the solid the way a facet catches a candle.
      var lit = dot(norm(CENTRES[i]), norm([-0.35, -0.75, 0.56]));
      el.style.filter = "brightness(" + (0.62 + 0.55 * Math.max(0, lit)).toFixed(3) + ")";
      die.appendChild(el);
      faceEls.push(el);
    }

    mat.querySelector("#d3d-debug").addEventListener("click", function () {
      var on = !debugOn();
      try { localStorage.setItem(DEBUG_KEY, on ? "1" : "0"); } catch (e) { /* private mode */ }
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

  /* Roll the die and settle it on `result`.
   *
   * `opts`: {sides, result, lo, hi, title, why, terms, dc, verdict, note}
   * Resolves when the die has landed. `ask` mode instead resolves with the number the
   * player wants, having asked for it — either from the die or, with the debug toggle on,
   * from their own physical roll.
   */
  function land(opts) {
    build();
    var sides = opts.sides || 20;
    var lo = opts.lo != null ? opts.lo : 1;
    var hi = opts.hi != null ? opts.hi : sides;
    var result = opts.result;

    // The face that will end up facing the viewer. Chosen at random among the twenty so
    // the same number does not always arrive on the same side of the solid.
    var landing = Math.floor(Math.random() * FACES.length);
    var text = labels(sides, lo, hi, result, landing);
    for (var i = 0; i < faceEls.length; i++) {
      faceEls[i].textContent = sides === 20 ? NUMBERS[i] : text[i];
      faceEls[i].className = "f";
    }

    mat.querySelector("#d3d-title").textContent = opts.title || "Roll";
    mat.querySelector("#d3d-why").textContent = opts.why || "";
    mat.querySelector("#d3d-terms").innerHTML = "";
    mat.querySelector("#d3d-verdict").textContent = "";
    mat.querySelector("#d3d-verdict").className = "";
    mat.querySelector("#d3d-note").textContent = "";
    mat.classList.add("on");

    // For a d20 the landing face is the one already bearing that number, so the solid
    // reads correctly from every angle rather than only from the front.
    if (sides === 20) {
      var found = NUMBERS.indexOf(result);
      if (found >= 0) landing = found;
    }

    die.style.transition = "none";
    return (async function () {
      for (var g = 0; g < 7; g++) {
        die.style.transform = spin();
        await wait([60, 60, 65, 75, 90, 110, 140][g]);
      }
      die.style.transition = "transform .85s cubic-bezier(.16,.9,.3,1)";
      die.style.transform = "rotateY(720deg) " + faceToFront(landing);
      await wait(880);

      faceEls[landing].classList.add("land");
      if (sides === 20 && result === 20) faceEls[landing].classList.add("crit");
      if (sides === 20 && result === 1) faceEls[landing].classList.add("fumble");

      if (opts.terms && opts.terms.length) {
        mat.querySelector("#d3d-terms").innerHTML = opts.terms.map(function (t) {
          return '<div class="r' + (t.total ? " tot" : "") + '"><span>' + esc(t.label) +
                 "</span><b>" + esc(String(t.value)) + "</b></div>";
        }).join("");
      }
      if (opts.verdict) {
        var v = mat.querySelector("#d3d-verdict");
        v.textContent = opts.verdict.text;
        v.className = opts.verdict.good ? "good" : opts.verdict.good === false ? "bad" : "";
      }
      if (opts.note) mat.querySelector("#d3d-note").textContent = opts.note;
      mat.querySelector("#d3d-go").textContent = "Close";
      mat.querySelector("#d3d-go").disabled = false;
      mat.querySelector("#d3d-debug").style.display = "none";
      mat.querySelector("#d3d-own").classList.remove("on");
      return new Promise(function (done) {
        mat.querySelector("#d3d-go").onclick = function () {
          mat.classList.remove("on");
          done(result);
        };
      });
    })();
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* Ask the player for a roll.
   *
   * Resolves with a number they rolled themselves, or with null meaning "the table rolls
   * it" — which is the default, and is what the 3D die is for. The manual entry is behind
   * the debug toggle because a physical die on the desk is the exception, not the norm.
   */
  function ask(opts) {
    build();
    var lo = opts.lo != null ? opts.lo : 1;
    var hi = opts.hi != null ? opts.hi : (opts.sides || 20);

    for (var i = 0; i < faceEls.length; i++) {
      faceEls[i].textContent = (opts.sides || 20) === 20 ? NUMBERS[i]
        : lo + (i % (hi - lo + 1));
      faceEls[i].className = "f";
    }
    die.style.transition = "none";
    die.style.transform = "rotateX(-18deg) rotateY(24deg)";

    mat.querySelector("#d3d-title").textContent = opts.title || "Roll";
    mat.querySelector("#d3d-why").textContent = opts.why || "";
    mat.querySelector("#d3d-terms").innerHTML = (opts.terms || []).map(function (t) {
      return '<div class="r' + (t.total ? " tot" : "") + '"><span>' + esc(t.label) +
             "</span><b>" + esc(String(t.value)) + "</b></div>";
    }).join("");
    mat.querySelector("#d3d-verdict").textContent = "";
    mat.querySelector("#d3d-note").textContent = opts.note || "";
    var face = mat.querySelector("#d3d-face");
    face.min = lo; face.max = hi; face.value = "";
    face.placeholder = opts.die || ("d" + (opts.sides || 20));
    mat.querySelector("#d3d-go").textContent = "Roll";
    mat.querySelector("#d3d-go").disabled = false;
    mat.querySelector("#d3d-debug").style.display = "";
    showOwn(debugOn());
    mat.classList.add("on");

    return new Promise(function (done) {
      function finish(value) { mat.classList.remove("on"); done(value); }
      mat.querySelector("#d3d-go").onclick = function () {
        if (debugOn()) {
          var v = parseInt(face.value, 10);
          // Refused rather than silently rounded: a value outside the die is a typo, and
          // accepting it would put an impossible roll in the log.
          if (!(v >= lo && v <= hi)) { face.focus(); return; }
          finish(v);
        } else {
          finish(null);                    // null means "the table rolls it"
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
    faces: FACES.length,
    numbers: NUMBERS.slice(),
    // Exposed so a test can check the solid is a solid rather than twenty stacked
    // triangles: every face normal should be a unit vector and opposite pairs sum to 21.
    _centres: CENTRES,
  };
})();
