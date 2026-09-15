/* The board in three dimensions, built and lit the way the dice are.
 *
 * Asked for in as many words: "a 3D viewport where i can see the action and choose where
 * to cast spells/use abilities (like x-com, but still text based and without fancy
 * textures. Just something you can clearly see and rotate)."
 *
 * WHY THIS IS HAND-ROLLED. The app ships as an offline executable and bundles no
 * third-party JavaScript at all, so a CDN is not available and a library would be a
 * bundling decision rather than an import. `dice3d.js` builds five Platonic solids from
 * vertex arrays with nothing behind it; this is the same bargain, and now the same
 * geometry and the same light.
 *
 * WHAT THIS REWRITE FIXED, and it is the defect dice3d.js already had and cured. The
 * first version projected with a hand-written 2:1 formula and shaded by CLASS: `.face-a`
 * was the +y wall at brightness .72 and `.face-b` the +x wall at .55, welded to the
 * geometric side. Turn the board a quarter and the same two walls keep the same two
 * brightnesses while swapping sides of the screen — so the light rotated with the board,
 * which is word for word what was reported from the table about the dice: "the lighting
 * is assigned to a few faces and it spins with those faces". A board has four times as
 * many chances to show it, because the board is the thing that turns.
 *
 * So the light belongs to the room. Every face carries a real world-space normal, the
 * normal is carried into the camera's frame, and the brightness is the same expression
 * `dice3d.js` uses against the same LIGHT vector — one ambient term, one diffuse, one
 * tight specular. Turn the board and the lit wall stays the wall facing the light.
 *
 * ROTATION IS FOUR FIXED QUARTER-TURNS, and that is a decision rather than a shortcut.
 * Firaxis chose the same for XCOM: a fixed camera with 90-degree steps, specifically
 * against the disorientation a free camera causes over a tactical map. Their own
 * postmortem records cutting visualised sight lines after months of iteration because the
 * lines became "tough for the player to determine what was going on" — legibility is what
 * kills a tactical 3D view, not frame rate. The camera is a real basis now, so free
 * rotation is three lines away; it stays refused for the reason above, not for want of
 * the maths.
 *
 * WHAT IT DRAWS AND WHAT IT REFUSES TO INVENT. Everything comes from the geometry payload
 * `play/views.py::_grid_state` already sends — blocked, difficult, obscuring, floor,
 * parapet, ceiling, levels, and reachable-with-its-level. This module adds no facts. It
 * cannot: a viewport that decided where a wall was would be a second map disagreeing with
 * the one the rules use.
 *
 * Every reachable top face carries `data-sq="c,r,level"`, the same attribute the flat map
 * writes and the combat builder already reads, so clicking a cell here queues a move or a
 * target through exactly the path the 2D map uses.
 */
(function () {
  "use strict";

  /* --- vectors -----------------------------------------------------------------------
     The same three helpers dice3d.js has. Duplicated rather than shared, and that is a
     considered call: CLAUDE.md's "grep for every copy of it" is about RULES, which go
     stale when one copy is corrected. A dot product is arithmetic. Pulling a module out
     from under a working dice renderer to save six lines would be the riskier change. */
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]];
  }
  function norm(a) {
    var l = Math.sqrt(dot(a, a)) || 1;
    return [a[0] / l, a[1] / l, a[2] / l];
  }

  /* --- the camera --------------------------------------------------------------------
     World axes are the board's own: +x a column east, +y a row south, +z a level up. One
     square and one level are both ONE unit, because a square is five feet and a level is
     five feet, and the first version carried two different pixel constants for the same
     distance (TILE_W 26, LEVEL_H 16) with nothing saying why they disagreed.

     Orthographic, because a tactical map wants a square at the back of the room to be the
     same size as a square at the front — that is the whole reason the genre is isometric
     and not perspective.

     The pitch is atan(1/2): the 2:1 "game isometric" rather than a true 30-degree one,
     which is what shipped and what the eye expects from this kind of board. It is a
     number here rather than baked into a formula, so it is a thing that can be changed. */
  var PITCH = Math.atan(0.5);
  var UNIT = 18;                 // pixels per five feet, in either direction

  /* The screen's three axes, as (right, down, toward-the-viewer), in the coordinates of
   * a board that has already been turned.
   *
   * DOWN rather than up, deliberately: SVG's y grows downward and so does CSS's, which
   * means a normal carried into this frame can be lit by the very same LIGHT constant
   * dice3d.js uses without a sign flip anywhere. Two renderers, one light.
   *
   * The basis is fixed and the BOARD turns, rather than the camera flying round it. Two
   * reasons, and the second is the one that was measured. Rotating the coordinates keeps
   * the projection and the depth sort agreeing without a matrix between them, which is
   * what the first version did and got right. And a camera built the obvious way — point
   * it at the board, cross with world up — puts square (0,0) at the BOTTOM of the
   * screen, where the flat map draws it at the top and every player switching between
   * the two views has to re-find the room. Seen side by side with the old renderer, that
   * flip was the most disorienting thing about the rewrite; it is not a matter of taste,
   * it is the other view's orientation. */
  var SIN = Math.sin(PITCH), COS = Math.cos(PITCH), R2 = Math.SQRT1_2;
  var RIGHT = [R2, -R2, 0];                   // east goes right, south goes left
  var DOWN = [R2 * SIN, R2 * SIN, -COS];      // and up on the board is up on the screen
  var TOWARD = cross(RIGHT, DOWN);            // the viewer: above the far corner

  // A quarter-turn of the board about its origin. Applied to points AND to normals, so a
  // wall that faces the light keeps facing it while the board turns under it.
  function turned(p, q) {
    var a = p[0], b = p[1], t;
    for (var i = 0; i < (q & 3); i++) { t = a; a = b; b = -t; }
    return [a, b, p[2]];
  }

  // A world point to screen pixels, and how near the viewer it is.
  function project(p, q) {
    var v = turned(p, q);
    return [dot(v, RIGHT) * UNIT, dot(v, DOWN) * UNIT];
  }
  function depth(p, q) { return dot(turned(p, q), TOWARD); }

  /* --- the light ---------------------------------------------------------------------
     Lifted from dice3d.js unchanged, including the constants, so a brass rail on the
     board and a brass die on the mat are lit by the same lamp. High, left, and in front
     — of the room, not of the board.

     The board is what turns here, where the die was what turned there, so the normal is
     carried into the camera's frame and lit in it. Same arithmetic, same result: a face
     pointing at the lamp is bright however the thing it belongs to is standing. */
  var LIGHT = norm([-0.42, -0.78, 0.47]);
  var VIEW = [0, 0, 1];
  var HALF = norm([LIGHT[0] + VIEW[0], LIGHT[1] + VIEW[1], LIGHT[2] + VIEW[2]]);

  function shade(n, q) {
    var v = turned(n, q);
    var f = [dot(v, RIGHT), dot(v, DOWN), dot(v, TOWARD)];
    var diffuse = Math.max(0, dot(f, LIGHT));
    var spec = Math.pow(Math.max(0, dot(f, HALF)), 26);
    return 0.46 + 0.66 * diffuse + 0.9 * spec;
  }

  /* --- materials ---------------------------------------------------------------------
     The shade is multiplied into the colour here rather than handed to CSS as
     `filter: brightness(var(--lit))`, which is how the dice do it. The dice light twenty
     faces; a tavern is closer to five hundred, and a per-element CSS filter is a filter
     region and a compositing pass each. The brightness is data, not decoration, so it is
     resolved where the geometry is.

     The palette is the app's: worn leather for ground, brass for anything a person put
     there, and the sides read by who is standing on them. Brighter than the flat map's
     hexes by about half, and that is the shading's doing rather than a change of taste —
     a wall turned away from the lamp takes the ambient term alone, 0.46, so a colour
     authored to look right flat comes out near black once it is a wall. Authored at the
     value a LIT face should land on, and measured against the board rather than guessed:
     side by side with the old renderer the first pass was legibly darker. */
  var MATERIAL = {
    tile: [0x38, 0x31, 0x28],           // flagstones, boards, packed earth
    raised: [0x58, 0x4c, 0x37],         // a dais, a gallery floor, a cart bed
    rough: [0x43, 0x39, 0x23],          // rubble, undergrowth, standing water
    murk: [0x33, 0x38, 0x40],           // smoke and fog: sight stops, feet do not
    solid: [0x53, 0x47, 0x39],          // wall, pillar, stall
    chamfer: [0x22, 0x1d, 0x16],        // the dark lip a box is cut back to
    rail: [0x7a, 0x6a, 0x44],           // brass, and the one thing you shoot over
    // The four tokens are the flat map's own colours, not approximations of them. Both
    // views are on screen within one click of each other and a foe that is #a33 in one
    // and #e0261e in the other is two different foes to anybody not looking closely.
    pc: [0xd9, 0xc0, 0x8a],
    ally: [0x6f, 0xc2, 0x76],
    foe: [0xe0, 0x26, 0x1e],
    bystander: [0xf2, 0xec, 0xdd]
  };

  // A square the party can reach is a WASH over whatever the ground already is, which is
  // what the flat map does with it — `#map .reach { fill: var(--gold); opacity: .12 }`.
  // It was its own flat colour here, close enough to the gold of the player's own token
  // that on a board of lit squares the token stopped being findable. A tint keeps the
  // ground legible underneath it and leaves gold meaning "you".
  var GOLD = [0xd9, 0xc0, 0x8a], WASH = 0.26;

  function paint(name, lit, wash) {
    var c = MATERIAL[name] || MATERIAL.tile, out = "#";
    for (var i = 0; i < 3; i++) {
      var base = wash ? c[i] + (GOLD[i] - c[i]) * WASH : c[i];
      var v = Math.round(Math.max(0, Math.min(255, base * lit)));
      out += (v < 16 ? "0" : "") + v.toString(16);
    }
    return out;
  }

  /* --- faces -------------------------------------------------------------------------
     One quad, its world normal, and where it sits. Faces are collected and then sorted by
     how near the viewer their centre is, which replaces the first version's three
     hand-tuned depth offsets (+8 per row, +4 for a figure, +0.5 for a rail) — each of
     which was a guess that happened to work at one angle. */
  function face(out, pts, normal, mat, cls, attrs, inner, wash) {
    var c = [0, 0, 0], i;
    for (i = 0; i < pts.length; i++) {
      c[0] += pts[i][0] / pts.length;
      c[1] += pts[i][1] / pts.length;
      c[2] += pts[i][2] / pts.length;
    }
    out.push({ pts: pts, n: normal, at: c, mat: mat, cls: cls || "",
               attrs: attrs || "", inner: inner || "", wash: !!wash });
  }

  var UP = [0, 0, 1], NORTH = [0, -1, 0], SOUTH = [0, 1, 0],
      WEST = [-1, 0, 0], EAST = [1, 0, 0];

  // The top of a box at (x, y), bevelled or not. A chamfer is what the dice call a
  // bevel: the full quad in the dark lip colour with the panel inset on top of it.
  // Inset in WORLD space by a fraction of a square — exact for any quad, where insetting
  // the projected polygon needs the mitre solver dice3d.js carries, because a clip-path
  // has no third dimension to inset in.
  function cap(out, x, y, z, mat, cls, attrs, inner, bevel, wash) {
    if (bevel) {
      face(out, [[x, y, z], [x + 1, y, z], [x + 1, y + 1, z], [x, y + 1, z]],
           UP, "chamfer", cls);
      x += bevel; y += bevel;
      var w = 1 - 2 * bevel;
      face(out, [[x, y, z], [x + w, y, z], [x + w, y + w, z], [x, y + w, z]],
           UP, mat, cls + " face-top", attrs, inner, wash);
      return;
    }
    face(out, [[x, y, z], [x + 1, y, z], [x + 1, y + 1, z], [x, y + 1, z]],
         UP, mat, cls + " face-top", attrs, inner, wash);
  }

  /* The four walls under a top face, and only the ones that are a wall.
   *
   * `under` is what each neighbour's own top stands at, so a wall is drawn from where the
   * ground next door leaves off rather than from zero. Two things fall out, and both were
   * visible side by side against the first version:
   *
   * A twenty-eight square gallery is one platform, not twenty-eight boxes. Drawing every
   * cell's full four walls put a seam down the middle of every flat expanse, because the
   * wall between two equally raised squares is a real polygon with a real stroke on it
   * that happens to be edge-on. Culled, the gallery reads as the one surface it is.
   *
   * And the hidden half stops being drawn at all. Those interior walls were two coincident
   * polygons fighting over the same pixels, which is wasted work in the sort as well as in
   * the paint: this took the library from 470 polygons to 214 with nothing removed that
   * anybody could see. */
  function walls(out, x, y, top, under, mat, cls) {
    var sides = [
      [NORTH, under[0], [[x, y, top], [x + 1, y, top]]],
      [SOUTH, under[1], [[x, y + 1, top], [x + 1, y + 1, top]]],
      [WEST, under[2], [[x, y, top], [x, y + 1, top]]],
      [EAST, under[3], [[x + 1, y, top], [x + 1, y + 1, top]]]
    ];
    sides.forEach(function (s) {
      var foot = Math.max(0, s[1]);
      if (top <= foot) return;                       // the ground next door is as high
      var a = s[2][0], b = s[2][1];
      face(out, [a, b, [b[0], b[1], foot], [a[0], a[1], foot]], s[0], mat, cls);
    });
  }

  // A freestanding box — a figure, a rail post. Nothing abuts it, so all four walls stand.
  function box(out, x, y, z0, z1, mat, cls, attrs, inner, bevel) {
    cap(out, x, y, z1, mat, cls, attrs, inner, bevel);
    walls(out, x, y, z1, [z0, z0, z0, z0], mat, cls);
  }

  function key(c, r) { return c + "," + r; }

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  /* Draw the whole board.
   *
   * `g` is the grid payload verbatim; `actors` is the scene's actor list, each with `at`.
   * `opts.turn` is 0-3, `opts.level` the floor being looked at, `opts.reach` whether to
   * light the squares the PC can reach.
   */
  function render(g, actors, opts) {
    opts = opts || {};
    var turn = (opts.turn || 0) & 3;
    var level = opts.level || 0;
    var W = g.width, H = g.height;

    var ground = {}, rails = {}, solid = {}, rough = {}, murk = {};
    (g.floor || []).forEach(function (f) { ground[key(f[0], f[1])] = f[2]; });
    (g.parapet || []).forEach(function (p) { rails[key(p[0], p[1])] = p[2]; });
    (g.blocked || []).forEach(function (p) { solid[key(p[0], p[1])] = true; });
    (g.difficult || []).forEach(function (p) { rough[key(p[0], p[1])] = true; });
    (g.obscuring || []).forEach(function (p) { murk[key(p[0], p[1])] = true; });

    var reach = {};
    (g.reachable || []).forEach(function (e) { reach[key(e[0], e[1])] = e; });

    // How high the ground stands in every square, worked out once: a wall is only a wall
    // where the square next door is lower, and answering that per neighbour per square
    // needs the whole board first. Off the edge of the board reads as ground level, so
    // the outside faces of the room are drawn.
    function topAt(x, y) {
      if (x < 0 || y < 0 || x >= W || y >= H) return 0;
      var k = key(x, y), z = ground[k] || 0;
      return solid[k] ? Math.max(z + 2, 2) : z;
    }

    var faces = [], tallest = 1;
    for (var x = 0; x < W; x++) {
      for (var y = 0; y < H; y++) {
        var k = key(x, y), z = ground[k] || 0, mat = "tile", cls = "tile";
        if (solid[k]) { mat = "solid"; cls = "solid"; }
        else if (murk[k]) { mat = "murk"; cls = "murk"; }
        else if (rough[k]) { mat = "rough"; cls = "rough"; }
        else if (z) { mat = "raised"; cls = "tile raised"; }

        var hit = "", wash = false;
        if (!solid[k] && opts.reach && reach[k]) {
          wash = true;
          cls += " lit";
          // The level a step onto this square actually lands on, straight from the
          // server's own answer. The flat map writes the same attribute.
          hit = ' data-sq="' + x + "," + y + (reach[k][3] ? "," + reach[k][3] : "") + '"';
        }

        // A wall is two levels of stone whatever the floor under it does; a raised square
        // is the height the server said.
        var topz = topAt(x, y);
        if (topz > tallest) tallest = topz;

        /* A GALLERY YOU ARE NOT ON IS DRAWN THROUGH. Standing on the library floor at
           turn 0, the player's own token sits behind ten feet of gallery and the camera
           cannot see it — correct occlusion, and useless. XCOM answers this by cutting
           away the walls between the camera and the floor being played on.
           The level picker above the map is already that control, so it is given
           something to do here rather than a second control being invented: a raised
           FLOOR standing above the level being looked at is drawn through, and a wall is
           not. That distinction is the point — a gallery is somebody else's floor and you
           are entitled to see under it, where a wall is a wall from every level, and
           making the stacks translucent would be telling the player they have a shot. */
        if (!solid[k] && topz > level) cls += " above";

        cap(faces, x, y, topz, mat, cls, hit, "", solid[k] ? 0.07 : 0, wash);
        if (topz > 0) {
          walls(faces, x, y, topz,
                [topAt(x, y - 1), topAt(x, y + 1), topAt(x - 1, y), topAt(x + 1, y)],
                mat, cls);
        }

        if (rails[k] !== undefined) {
          /* A balustrade, standing where the rule says it stands.
           *
           * BOTH EARLIER VERSIONS DREW IT IN THE WRONG PLACE, and this is the precision
           * bug worth naming. `grid.parapet` holds a low obstacle "by the absolute level
           * of their top", and `_crosses_parapet` says what that means: "a rail whose top
           * is level 2 stops a line running at 1 and does nothing to one running at 3".
           * The barrier therefore fills the square from the ground UP TO its top. The
           * viewport drew it from the top upward — a beam floating above the levels it
           * blocks, showing clear air exactly where a shot is stopped and a solid bar
           * exactly where one sails over. A picture that contradicts the rule is worse
           * than no picture, because the player plans from it.
           *
           * Thin, and that stays the point. `blocked` is solid at every height, so a
           * gallery rail drawn as a full square reads as total cover in both directions —
           * which is the opposite of what a rail is for, and is a mistake the engine
           * itself used to make. A hand's breadth of stone standing in the square says
           * "shoot over this" the way a wall does not. */
          var top = rails[k], foot = Math.max(0, topAt(x, y)), t = 0.14;
          var rcls = "rail3" + (top > level ? " above" : "");
          if (top > foot) {
            // Which way the fence runs: along the row if the parapet continues that way,
            // along the column otherwise. A run of them should read as one balustrade
            // rather than as a line of unrelated posts.
            var alongX = rails[key(x - 1, y)] !== undefined ||
                         rails[key(x + 1, y)] !== undefined;
            var x0 = alongX ? x : x + 0.5 - t / 2, x1 = alongX ? x + 1 : x + 0.5 + t / 2;
            var y0 = alongX ? y + 0.5 - t / 2 : y, y1 = alongX ? y + 0.5 + t / 2 : y + 1;
            face(faces, [[x0, y0, top], [x1, y0, top], [x1, y1, top], [x0, y1, top]],
                 UP, "rail", rcls);
            face(faces, [[x0, y0, top], [x1, y0, top], [x1, y0, foot], [x0, y0, foot]],
                 NORTH, "rail", rcls);
            face(faces, [[x0, y1, top], [x1, y1, top], [x1, y1, foot], [x0, y1, foot]],
                 SOUTH, "rail", rcls);
            face(faces, [[x0, y0, top], [x0, y1, top], [x0, y1, foot], [x0, y0, foot]],
                 WEST, "rail", rcls);
            face(faces, [[x1, y0, top], [x1, y1, top], [x1, y1, foot], [x1, y0, foot]],
                 EAST, "rail", rcls);
            if (top > tallest) tallest = top;
          }
        }
      }
    }

    (actors || []).forEach(function (a) {
      if (!a.at) return;
      var ax = a.at[0], ay = a.at[1], az = a.at.length > 2 ? a.at[2] : 0;
      var n = a.squares || 1;
      var side = a.is_pc ? "pc" : (a.side === "pc" || a.side === "you") ? "ally"
                 : a.side ? "foe" : "bystander";
      var cls = "fig " + side + (a.hp <= 0 ? " down" : "");
      if (az !== level) cls += " offlevel";
      /* Eight feet of a Medium creature is 1.6 levels — "their height contained within
         2x5ft squares (8ft is max for medium)" — and a bigger body is as tall as it is
         wide. A creature at zero hit points is drawn as a slab a third of a level high
         rather than a standing figure at reduced opacity: prone is a thing you should be
         able to read across the room, and a faded box is not it. */
      var tall = a.hp <= 0 ? 0.3 : Math.min(1.6 * n, 2 * n);
      var tip = "<title>" + esc(a.name || "") + " — " + a.hp + "/" + a.hp_max +
                (az ? " · " + az * 5 + " ft up" : "") + "</title>";
      for (var dx = 0; dx < n; dx++) {
        for (var dy = 0; dy < n; dy++) {
          box(faces, ax + dx, ay + dy, az, az + tall, side, cls, "",
              dx === 0 && dy === 0 ? tip : "", 0.12);
        }
      }
      if (az + tall > tallest) tallest = az + tall;
    });

    // Back to front. One comparison on the real distance to the viewer, where the first
    // version summed a rotated row and column and added hand-picked offsets for the
    // things that came out wrong.
    faces.sort(function (a, b) { return depth(a.at, turn) - depth(b.at, turn); });

    var body = faces.map(function (f) {
      var pts = f.pts.map(function (p) { return project(p, turn); });
      return '<polygon class="' + f.cls + '" fill="' +
        paint(f.mat, shade(f.n, turn), f.wash) +
        '" points="' +
        pts.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ") +
        '"' + f.attrs + (f.inner ? ">" + f.inner + "</polygon>" : "/>");
    }).join("");

    // The viewBox is measured from the projected corners rather than guessed, so a map of
    // any size at any rotation fills the frame without clipping. Measured to the board's
    // own tallest thing, where the first version always reserved four levels of air.
    var xs = [], ys = [];
    [0, W].forEach(function (cx) {
      [0, H].forEach(function (cy) {
        [0, tallest].forEach(function (cz) {
          var p = project([cx, cy, cz], turn); xs.push(p[0]); ys.push(p[1]);
        });
      });
    });
    var pad = 10;
    var x0 = Math.min.apply(null, xs) - pad, y0 = Math.min.apply(null, ys) - pad;
    var w = Math.max.apply(null, xs) - x0 + pad, h = Math.max.apply(null, ys) - y0 + pad;
    return '<svg id="view3d" viewBox="' + x0.toFixed(1) + " " + y0.toFixed(1) + " " +
      w.toFixed(1) + " " + h.toFixed(1) + '" preserveAspectRatio="xMidYMid meet">' +
      body + "</svg>";
  }

  window.Scene3D = { render: render, TURNS: 4 };
})();
