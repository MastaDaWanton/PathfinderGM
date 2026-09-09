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
    // The zigzag and the apex are NOT free to choose independently. A kite face is
    // four points, and four points are only coplanar at one apex height for a given
    // zigzag: apex = zigzag * (5 + 2 sqrt 5), from solving the coplanarity condition.
    //
    // Shipped for months as zigzag 0.25 with apex 1.15, which is not that height, so
    // every kite was bent 0.26 out of its own plane on a die of radius 1 — the browser
    // drew each face flat anyway, the neighbours could not meet, and the d10 came
    // apart into shards. Reported from the table with a screenshot, 2026-09-09: "these
    // die are splitting apart."
    //
    // The ratio also fixes the die's proportions, so the zigzag is what sets how tall
    // it is: 0.115 gives an apex of 1.09 against an equator radius of 1, which is
    // about the shape of a d10 in the hand.
    var ZIG = 0.115, APEX = ZIG * (5 + 2 * Math.sqrt(5));
    for (var k = 0; k < 10; k++) {
      var ang = Math.PI * 2 * k / 10;
      verts.push([Math.cos(ang), Math.sin(ang), (k % 2 === 0 ? ZIG : -ZIG)]);
    }
    verts.push([0, 0, APEX]);      // 10: top apex
    verts.push([0, 0, -APEX]);     // 11: bottom apex
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

  /* Faces as SUPPORT PLANES: a plane through three vertices with every other vertex on
     one side of it is a face of the hull, and the face is everything lying on it.

     Found rather than guessed, because guessing is what was wrong. The dodecahedron
     used to take its twelve face directions from `icosahedron().verts` and keep the
     five vertices leaning furthest each way — and those twelve directions are the
     WRONG cyclic permutation for this vertex set. They point at the dodecahedron's own
     vertices, not at its faces, so each "face" was five points that were nowhere near
     coplanar: 1.05 out of plane on a solid of radius 1.7. The d12 was drawn as twelve
     bent pentagons that could not meet, which is the same "splitting apart" the d10
     had for a different reason.

     Twenty vertices is 1,140 triples, computed once per shape and cached, so the cost
     of never guessing again is nothing. */
  function hullFaces(v) {
    var faces = [], seen = {};
    for (var i = 0; i < v.length; i++) {
      for (var j = i + 1; j < v.length; j++) {
        for (var k = j + 1; k < v.length; k++) {
          var n = cross(sub(v[j], v[i]), sub(v[k], v[i]));
          if (len(n) < 1e-9) continue;
          n = norm(n);
          var d = dot(n, v[i]);
          if (d < 0) { n = [-n[0], -n[1], -n[2]]; d = -d; }
          var outside = false, on = [];
          for (var m = 0; m < v.length; m++) {
            var s = dot(n, v[m]);
            if (s > d + 1e-9) { outside = true; break; }
            if (Math.abs(s - d) < 1e-9) on.push(m);
          }
          if (outside || on.length < 3) continue;
          var key = on.join(",");
          if (seen[key]) continue;
          seen[key] = 1;
          faces.push(on);
        }
      }
    }
    return faces;
  }

  function dodecahedron() {
    var v = [];
    [-1, 1].forEach(function (x) { [-1, 1].forEach(function (y) {
      [-1, 1].forEach(function (z) { v.push([x, y, z]); }); }); });
    [-1, 1].forEach(function (a) { [-1, 1].forEach(function (b) {
      v.push([0, a / PHI, b * PHI], [a / PHI, b * PHI, 0], [a * PHI, 0, b / PHI]);
    }); });
    return { verts: v, faces: hullFaces(v) };
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
      // The normal comes from the face's own PLANE, not from the direction of its
      // centre. Those are the same thing only when a face is symmetric about its
      // normal — true for every regular solid here, and false for the d10, whose kites
      // run from a near apex to a far equator point. Taking `norm(c)` tilted all ten
      // of the d10's faces off their true planes, so the neighbours could not meet:
      // measured 2026-09-09, 238 of 784 sample points in the middle of a d10 landed on
      // no face at all, against 0 for the d6, d12 and d20.
      var z = null;
      for (var a = 0; a < face.length - 2 && !z; a++) {
        for (var b = a + 1; b < face.length - 1 && !z; b++) {
          for (var d = b + 1; d < face.length && !z; d++) {
            var n = cross(sub(verts[face[b]], verts[face[a]]),
                          sub(verts[face[d]], verts[face[a]]));
            if (len(n) > 1e-9) { z = norm(n); }
          }
        }
      }
      z = z || norm(c);
      if (dot(z, c) < 0) { z = [-z[0], -z[1], -z[2]]; }
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

  /* Rodrigues, so a vector can be carried through the same rotation the die takes. */
  function rotateAbout(v, axis, deg) {
    var a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), k = norm(axis);
    var kv = cross(k, v), kd = dot(k, v);
    return [v[0] * c + kv[0] * s + k[0] * kd * (1 - c),
            v[1] * c + kv[1] * s + k[1] * kd * (1 - c),
            v[2] * c + kv[2] * s + k[2] * kd * (1 - c)];
  }

  /* Turn face `index` to the front — and then turn the NUMBER the right way up.
     Rotating a normal onto the view axis is a rotation with one degree of freedom
     left over, and nothing was using it, so which way up the winning number landed was
     luck. Measured on the bench, 2026-09-09: a d20 showing 14 landed with the 14
     upside down, and so did the 19 above it. A die that reads upside down at the
     moment the player looks at it is most of what "doesn't feel good" means.

     The text's own up in three dimensions is -y0, the same basis `buildSolid` builds
     each face with. Carry it through the rotation, see which way it ends up pointing
     on screen, and undo that roll in view space. */
  function faceToFront(sides, index) {
    var s = shape(sides), f = s.faces[index];
    var n = f.normal, front = [0, 0, 1];
    var d = Math.max(-1, Math.min(1, dot(n, front)));
    var angle = Math.acos(d) * 180 / Math.PI;
    var axis = cross(n, front);
    var flat = len(axis) < 1e-6;
    if (flat) { axis = [1, 0, 0]; angle = d > 0 ? 0 : 180; }
    else { axis = norm(axis); }

    var y0 = norm(sub(s.verts[f.idx[0]], f.centre));
    var up = rotateAbout([-y0[0], -y0[1], -y0[2]], axis, angle);
    // CSS space has +Y downward, so screen-up is (0,-1). rotateZ(t) carries (0,-1) to
    // (sin t, -cos t); the die is currently rolled by that t, so undo it.
    var roll = Math.atan2(up[0], -up[1]) * 180 / Math.PI;

    return "rotateZ(" + (-roll).toFixed(2) + "deg) rotate3d(" +
           axis[0].toFixed(6) + "," + axis[1].toFixed(6) + "," + axis[2].toFixed(6) +
           "," + angle.toFixed(4) + "deg)";
  }

  /* --- the mat ---------------------------------------------------------------------- */
  var STYLE = [
    // The waiting die turns on the compositor, not in script: a CSS animation keeps
    // drifting when script callbacks are throttled (embedded panes, background
    // windows), and it is the cheaper path besides.
    "@keyframes d3d-drift{from{transform:rotateX(-18deg) rotateY(24deg)}",
    "to{transform:rotateX(342deg) rotateY(384deg)}}",
    "#d3d-mat{position:fixed;inset:0;z-index:60;display:none;align-items:center;",
    "justify-content:center;background:radial-gradient(60% 50% at 50% 40%,",
    "rgba(10,8,6,.74),rgba(4,3,3,.92));font:15px/1.55 'Palatino Linotype',Palatino,Georgia,serif}",
    "#d3d-mat.on{display:flex}",
    "#d3d-card{width:380px;max-width:92vw;padding:24px 26px 22px;border-radius:3px;",
    "background:linear-gradient(rgba(27,22,17,.96),rgba(18,15,11,.97));",
    "border:1px solid #7a6543;box-shadow:inset 0 0 0 1px rgba(221,196,142,.08),",
    "0 18px 60px rgba(0,0,0,.8);color:#e6dcc6}",
    // Two dice need a wider table, and widening the card is the one way to give them
    // one without transforming anything that owns a perspective.
    "#d3d-card.wide{width:470px}",
    "#d3d-card h3{margin:0 0 2px;color:#d9c08a;text-align:center;letter-spacing:.06em;",
    "font:400 22px/1.2 'Cinzel','Palatino Linotype',Georgia,serif;font-variant:small-caps}",
    "#d3d-why{color:#8e816a;font-style:italic;font-size:13px;text-align:center;margin-bottom:6px}",
    "#d3d-stage{height:212px;display:flex;align-items:center;justify-content:center;",
    "perspective:760px;position:relative}",
    // Something to land ON. A shadow is a darkening, and on a mat this dark there was
    // nothing for it to darken — the first build put a black ellipse on a near-black
    // card and it was invisible in a screenshot. This is a faint warm pool under the
    // die, and the shadow reads against it.
    "#d3d-stage .floor{position:absolute;bottom:2px;left:50%;width:300px;height:50px;",
    "transform:translateX(-50%);pointer-events:none;border-radius:50%;",
    "background:radial-gradient(closest-side,rgba(196,166,110,.10),rgba(196,166,110,.03) 60%,",
    "rgba(0,0,0,0))}",
    "#d3d-stage.pair #d3d-floor1{left:calc(50% - 95px);width:190px}",
    "#d3d-stage.pair #d3d-floor2{left:calc(50% + 95px);width:190px}",
    "#d3d-floor2{display:none}",
    "#d3d-stage.pair #d3d-floor2{display:block}",
    // The contact shadow. A sibling of the die, never an ancestor: `opacity` below 1
    // forces `transform-style:flat` on its own subtree, and on the die that would
    // collapse the solid into a flat card.
    "#d3d-stage .sh{position:absolute;bottom:11px;left:50%;width:104px;height:17px;",
    "border-radius:50%;opacity:0;pointer-events:none;transform:translateX(-50%) scale(1);",
    "background:radial-gradient(closest-side,rgba(0,0,0,.92),rgba(0,0,0,.35) 55%,",
    "rgba(0,0,0,0))}",
    "#d3d-stage.pair #d3d-sh1{left:calc(50% - 95px)}",
    "#d3d-stage.pair #d3d-sh2{left:calc(50% + 95px)}",
    "#d3d-sh2{display:none}",
    "#d3d-stage.pair #d3d-sh2{display:block}",
    "#d3d-die,#d3d-die2{position:relative;width:0;height:0;transform-style:preserve-3d}",
    // Two dice at a d20's size ran off both edges of a 380px card the moment the ones
    // die became visible at all. The first fix scaled the STAGE — and the stage is the
    // element carrying `perspective`, so scaling it changed the projection out from
    // under the faces and the solids came apart into loose shards. Reported from the
    // table with a screenshot, 2026-09-09. The card widens instead; nothing that owns
    // a perspective gets transformed.
    "#d3d-stage.pair #d3d-die{margin-right:95px}",
    // `landPercentile` clears the inline display to show the second die, and clearing
    // an inline style falls back to THIS rule — so the ones die has been hidden on
    // every percentile roll since the rule was written. Found on the bench, 2026-09-09:
    // a d100 drew the tens die alone, off to the left of centre, and read as a bug in
    // the layout. The pair rule below is what makes clearing it mean "show".
    "#d3d-die2{margin-left:95px;display:none}",
    "#d3d-stage.pair #d3d-die2{display:block}",
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

  var mat, die, die2, sh1, sh2, DEBUG_KEY = "pfgm.dice.manual";

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
      '<div id="d3d-stage"><div class="floor" id="d3d-floor1"></div>' +
      '<div class="floor" id="d3d-floor2"></div>' +
      '<div class="sh" id="d3d-sh1"></div>' +
      '<div class="sh" id="d3d-sh2"></div>' +
      '<div id="d3d-die"></div><div id="d3d-die2"></div></div>' +
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
    sh1 = mat.querySelector("#d3d-sh1");
    sh2 = mat.querySelector("#d3d-sh2");

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

  /* --- the clack -------------------------------------------------------------------
     Synthesised rather than shipped: a die landing is a noise burst with a fast decay
     and a little body under it, which is a dozen lines of Web Audio and no asset in
     the installer.

     Why it is here at all: the only quantitative study found on what makes an impact
     feel like an impact (arXiv:2208.06155, 5,000 annotated comments across 15 games)
     names three features that make or break it — hit stop, camera control, and SOUND
     COHERENCE — and its finding about sound is specifically about sync. A delay
     between seeing the hit and hearing it "will lead to a sense of unnaturalness and
     ruins the user experience". So the clacks are scheduled on the audio clock at the
     same instant the animation starts, at the exact offsets of the two contacts, and
     cannot drift from them.

     Pitch is jittered per throw. A dozen identical samples in a row is the machine-gun
     effect, and it is the single most audible way canned audio announces itself.

     Set `pfgm.dice.mute` in localStorage to silence it. */
  var actx, noise;

  function audio() {
    if (actx === undefined) {
      try {
        var Ctx = window.AudioContext || window.webkitAudioContext;
        actx = Ctx ? new Ctx() : null;
      } catch (e) { actx = null; }
    }
    // Chromium starts an AudioContext suspended when it is made before a gesture. The
    // click on the roll button IS the gesture, so resuming here always works.
    if (actx && actx.state === "suspended") { try { actx.resume(); } catch (e) { /* */ } }
    try { if (localStorage.getItem("pfgm.dice.mute") === "1") return null; } catch (e) { /* */ }
    return actx;
  }

  function noiseBuffer(ctx) {
    if (!noise) {
      noise = ctx.createBuffer(1, (ctx.sampleRate * 0.25) | 0, ctx.sampleRate);
      var d = noise.getChannelData(0);
      for (var i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    }
    return noise;
  }

  function clack(afterMs, level, pitch) {
    var ctx = audio();
    if (!ctx) return;
    var at = ctx.currentTime + Math.max(0, afterMs) / 1000;

    // The transient: filtered noise, gone in sixty milliseconds.
    var src = ctx.createBufferSource();
    src.buffer = noiseBuffer(ctx);
    var band = ctx.createBiquadFilter();
    band.type = "bandpass";
    band.frequency.value = 1650 * pitch;
    band.Q.value = 1.1;
    var g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, at);
    g.gain.exponentialRampToValueAtTime(level, at + 0.004);
    g.gain.exponentialRampToValueAtTime(0.0001, at + 0.06);
    src.connect(band); band.connect(g); g.connect(ctx.destination);
    src.start(at); src.stop(at + 0.09);

    // The body: what tells you the thing has weight.
    var osc = ctx.createOscillator();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(210 * pitch, at);
    osc.frequency.exponentialRampToValueAtTime(120 * pitch, at + 0.07);
    var og = ctx.createGain();
    og.gain.setValueAtTime(0.0001, at);
    og.gain.exponentialRampToValueAtTime(level * 0.55, at + 0.006);
    og.gain.exponentialRampToValueAtTime(0.0001, at + 0.1);
    osc.connect(og); og.connect(ctx.destination);
    osc.start(at); osc.stop(at + 0.12);
  }

  function reducedMotion() {
    try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
    catch (e) { return false; }
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
    // Whatever the last throw left holding — the shadow's filled final state, an
    // animation still running because the player closed the mat mid-roll.
    [sh1, sh2].forEach(function (s) {
      if (!s) return;
      s.getAnimations().forEach(function (a) { a.cancel(); });
      s.style.opacity = "0";
    });
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
        mat.querySelector("#d3d-card").classList.remove("wide");
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

  /* --- the throw -------------------------------------------------------------------
     What this replaced, and why: the first 600ms of every roll used to set
     `transition: none` and step through seven random orientations 60 to 140ms apart.
     It did not animate. The die teleported between seven poses and then played one
     0.85s transition into the landing, so two thirds of the throw had no motion in it
     at all — a slideshow with a nice ending. That is the whole of the "doesn't feel
     good" report, and no amount of polish elsewhere would have covered it.

     The die still lands on the number the server rolled, exactly as before: the
     leading rotations unwind to zero, so whatever they were, the last frame IS
     `landTransform`. This is the same shape every real implementation uses — Dice So
     Nice bakes a corrective quaternion into a precomputed buffer, threejs-dice
     relabels which face carries which number — and none of them steer physics at a
     face. See docs/dice-feel.md.

     Timing: about 780ms against the 1.5s it was. Nielsen Norman's guidance is that
     frequent animations want to be shorter, and the field evidence on dice is
     one-sided — every product whose dice are slow has a standing revolt about it. A
     natural twenty earns more flourish, never more waiting. */
  var THROW_MS = 780;

  function tumble(el, landTransform, slower, shadow) {
    var ms = slower ? THROW_MS + 110 : THROW_MS;

    if (reducedMotion()) {
      // Reduce, not remove: the player still needs to see that a roll happened, so
      // this keeps a short reveal and one quiet clack rather than snapping silently.
      el.style.transition = "none";
      el.style.transform = landTransform;
      if (shadow) { shadow.style.opacity = ".42"; }
      clack(20, 0.1, 1);
      return wait(170);
    }

    // Leading rotations, unwound to nothing by the time the die touches down. Whole
    // turns plus a part-turn, so the tumble reads as continuous rather than as a
    // shortest-path wobble between two orientations.
    var ax = (2 + (Math.random() * 2 | 0)) * 360 + 140 + (Math.random() * 80 | 0);
    var ay = (2 + (Math.random() * 2 | 0)) * 360 + 200 + (Math.random() * 80 | 0);
    var az = 180 + (Math.random() * 180 | 0);
    if (slower) { ay = -ay; }

    function at(f) {
      return "rotateX(" + Math.round(ax * f) + "deg) rotateY(" + Math.round(ay * f) +
             "deg) rotateZ(" + Math.round(az * f) + "deg) " + landTransform;
    }

    // Squash on contact, with the ratios from Josh Comeau's worked demo — about 1.5
    // squash, 1.25 stretch — and a rebound between the two contacts.
    var frames = [
      { offset: 0, transform: "translateY(-64px) scale3d(.94,1.08,.94) " + at(1),
        easing: "cubic-bezier(.16,.62,.42,1)" },
      { offset: 0.5, transform: "translateY(-34px) scale3d(1,1,1) " + at(0.34),
        easing: "cubic-bezier(.55,0,.9,.5)" },
      { offset: 0.68, transform: "translateY(0) scale3d(1.18,.82,1.18) " + at(0),
        easing: "cubic-bezier(.2,.9,.35,1)" },
      { offset: 0.8, transform: "translateY(-15px) scale3d(.95,1.06,.95) " + at(0),
        easing: "cubic-bezier(.55,0,.9,.6)" },
      { offset: 0.91, transform: "translateY(0) scale3d(1.09,.92,1.09) " + at(0),
        easing: "ease-out" },
      { offset: 1, transform: "translateY(0) scale3d(1,1,1) " + at(0) },
    ];

    // The contact shadow. It is a separate element on purpose: `filter` and `opacity`
    // below 1 both force `transform-style: flat` on their own subtree, so putting
    // either on the element that holds the faces would collapse the die.
    if (shadow) {
      shadow.animate([
        { offset: 0, opacity: 0.08, transform: "translateX(-50%) scale(.5)" },
        { offset: 0.5, opacity: 0.2, transform: "translateX(-50%) scale(.78)" },
        { offset: 0.68, opacity: 0.5, transform: "translateX(-50%) scale(1.14)" },
        { offset: 0.8, opacity: 0.28, transform: "translateX(-50%) scale(.84)" },
        { offset: 0.91, opacity: 0.46, transform: "translateX(-50%) scale(1.05)" },
        { offset: 1, opacity: 0.42, transform: "translateX(-50%) scale(1)" },
      ], { duration: ms, fill: "forwards" });
    }

    // Both contacts, scheduled on the audio clock at the same instant the animation
    // starts, so the sound cannot drift from the frame it belongs to. Second one
    // quieter and a touch higher, the way a real second bounce is.
    var pitch = 0.9 + Math.random() * 0.25;
    clack(ms * 0.68, 0.15, pitch);
    clack(ms * 0.91, 0.07, pitch * 1.14);

    var anim = el.animate(frames, { duration: ms, easing: "linear", fill: "forwards" });
    return anim.finished.catch(function () { /* cancelled by a close */ }).then(function () {
      // Held as an inline style rather than by the animation's fill, so the next roll
      // starts from a clean element with nothing of this throw left running on it.
      anim.cancel();
      el.style.transition = "none";
      el.style.transform = landTransform;
    });
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
      await tumble(die, faceToFront(sides, landing), false, sh1);
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
    mat.querySelector("#d3d-card").classList.add("wide");
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
        tumble(die, faceToFront(10, landA), false, sh1),
        tumble(die2, faceToFront(10, landB), true, sh2),
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

    // The die turns slowly while it waits — "it should spin slowly and then when i
    // hit roll it should look like its getting cast and rolling." The idle is a CSS
    // keyframe loop on the compositor, and the cast freezes the animation at its
    // current pose (the computed matrix) before throwing, so there is no snap.
    die.style.animation = "d3d-drift 26s linear infinite";

    function cast() {
      var pose = getComputedStyle(die).transform;
      die.style.animation = "none";
      die.style.transform = pose === "none"
        ? "rotateX(-18deg) rotateY(24deg)" : pose;
      void die.offsetWidth;                     // commit the freeze before the throw
      return new Promise(function (r) {
        // Up, over, and down: a throw reads as a throw because it leaves the table.
        die.style.transition = "transform .35s cubic-bezier(.3,.7,.6,1)";
        die.style.transform += " translateY(-46px) rotateX(200deg) rotateY(260deg)";
        setTimeout(function () {
          die.style.transition = "transform .55s cubic-bezier(.15,.85,.25,1)";
          die.style.transform = die.style.transform
            .replace("translateY(-46px)", "translateY(0)")
            .replace("rotateX(200deg)", "rotateX(560deg)")
            .replace("rotateY(260deg)", "rotateY(740deg)");
          setTimeout(r, 560);
        }, 350);
      });
    }

    return new Promise(function (done) {
      function close(value) {
        die.style.animation = "";
        mat.classList.remove("on");
        done(value);
      }
      mat.querySelector("#d3d-go").onclick = function () {
        var v = null;
        if (debugOn()) {
          v = parseInt(face.value, 10);
          if (!(v >= lo && v <= hi)) { face.focus(); return; }
        }
        mat.querySelector("#d3d-go").disabled = true;
        cast().then(function () { close(v); });
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
    // How far the worst face of each solid strays from its own plane, as a fraction of
    // the die's radius. Two shapes were shipping bent faces and the browser drew them
    // flat anyway, so neighbours could not meet: this is the number that says so.
    _flatness: function () {
      var out = {};
      [4, 6, 8, 10, 12, 20].forEach(function (sides) {
        var s = shape(sides), worst = 0;
        s.faces.forEach(function (f) {
          var p = f.idx.map(function (i) { return s.verts[i]; });
          if (p.length < 4) return;
          var n = norm(cross(sub(p[1], p[0]), sub(p[2], p[0])));
          for (var q = 3; q < p.length; q++) {
            worst = Math.max(worst, Math.abs(dot(n, sub(p[q], p[0]))));
          }
        });
        out["d" + sides] = Math.round(worst * 10000) / 10000;
      });
      return out;
    },
  };
})();
