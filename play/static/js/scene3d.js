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
    bystander: [0xf2, 0xec, 0xdd],
    // Fixtures (2026-11-11), from the table's own palette: wood from the leather and brass
    // browns, stone from the board's greys, book spines from the side colours dimmed.
    wood: [0x6b, 0x4a, 0x3a], wooddark: [0x4a, 0x33, 0x26], plank: [0x7d, 0x68, 0x45],
    tread: [0x9a, 0x84, 0x58], hoop: [0x2e, 0x26, 0x1e], stone: [0x5c, 0x58, 0x52],
    stonedark: [0x3a, 0x31, 0x28], iron: [0x6a, 0x6f, 0x76], water: [0x2e, 0x3c, 0x46],
    waterhi: [0x6a, 0x7a, 0x86], spine0: [0x7d, 0x1a, 0x14], spine1: [0x1f, 0x4a, 0x26],
    spine2: [0x7d, 0x68, 0x45], spine3: [0x3a, 0x40, 0x48], spine4: [0x7a, 0x6f, 0x5a]
  };
  // A fire is its own light: the ember, never shaded by the lamp.
  var EMBER = "#ffb054";

  // A square the party can reach is a WASH over whatever the ground already is, which is
  // what the flat map does with it — `#map .reach { fill: var(--gold); opacity: .12 }`.
  // It was its own flat colour here, close enough to the gold of the player's own token
  // that on a board of lit squares the token stopped being findable. A tint keeps the
  // ground legible underneath it and leaves gold meaning "you".
  var GOLD = [0xd9, 0xc0, 0x8a], WASH = 0.26;

  // A spell's area: the flat map's `.spellarea` fill, character for character.
  var AREA = "#e0701e";

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

  // A box of any footprint and height, all five visible faces: a rail on an edge, a step,
  // a table top, a shelf. `attrs` (e.g. pointer-events) goes on every face.
  function slab(out, x0, y0, x1, y1, z0, z1, mat, cls, attrs) {
    face(out, [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], UP, mat, cls, attrs);
    face(out, [[x0, y0, z1], [x1, y0, z1], [x1, y0, z0], [x0, y0, z0]], NORTH, mat, cls, attrs);
    face(out, [[x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0]], SOUTH, mat, cls, attrs);
    face(out, [[x0, y0, z1], [x0, y1, z1], [x0, y1, z0], [x0, y0, z0]], WEST, mat, cls, attrs);
    face(out, [[x1, y0, z1], [x1, y1, z1], [x1, y1, z0], [x1, y0, z0]], EAST, mat, cls, attrs);
  }

  function key(c, r) { return c + "," + r; }

  /* An upright frustum of `n` sides: radius r0 at z0 to r1 at z1, its normals tilted by
     the taper so the lamp lights a narrowing body as it narrows. `cap` ({cls, inner})
     puts a lid on top. */
  function frustum(out, cx, cy, r0, r1, z0, z1, n, mat, cls, cap) {
    var h = z1 - z0, ring = [], i;
    for (i = 0; i < n; i++) {
      var a = i / n * 2 * Math.PI, b = (i + 1) / n * 2 * Math.PI, m = (a + b) / 2;
      face(out, [[cx + r1 * Math.cos(a), cy + r1 * Math.sin(a), z1],
                 [cx + r1 * Math.cos(b), cy + r1 * Math.sin(b), z1],
                 [cx + r0 * Math.cos(b), cy + r0 * Math.sin(b), z0],
                 [cx + r0 * Math.cos(a), cy + r0 * Math.sin(a), z0]],
           norm([Math.cos(m) * h, Math.sin(m) * h, r0 - r1]), mat, cls);
      ring.push([cx + r1 * Math.cos(a), cy + r1 * Math.sin(a), z1]);
    }
    if (cap) face(out, ring, UP, mat, cap.cls, "", cap.inner);
  }

  /* --- figures (2026-11-11) ------------------------------------------------------------
     The owner: "replace the square people with something that will indicate it is a
     humanoid". A tabletop miniature, because that is the thing a player already reads
     as "a person standing here": a round base in the side's colour, two legs, a body
     that widens to the shoulders with the arms at its sides, a head. Built of a few lit frusta, like the rest
     of the board — no image, no icon.

     A body that is not a person must not be drawn as one (`form`, play/views.py
     `_body_form`, from the `type.*` tags): an animal, a vermin, a magical beast stands
     on all fours, low and long; an ooze is a mound. Two generic shapes, never one per
     monster. Anyone at zero hit points lies on their base whatever they are: prone is
     what should read across the room.

     Every piece is a closed convex solid, so a face turned away from the camera is
     hidden by its own front at every quarter-turn — marked `cull` and never drawn,
     which halves what a figure costs the depth sort. Returns the figure's top. */
  function figure(out, cx, cy, z, s, form, down, mat, cls, baseCls, tip) {
    var start = out.length;
    frustum(out, cx, cy, 0.42 * s, 0.4 * s, z, z + 0.07 * s, 10, mat, cls,
            { cls: cls + baseCls, inner: tip });
    var b = z + 0.07 * s, top;
    if (down) {
      slab(out, cx - 0.36 * s, cy - 0.12 * s, cx + 0.16 * s, cy + 0.12 * s, b, b + 0.2 * s,
           mat, cls);
      slab(out, cx + 0.18 * s, cy - 0.09 * s, cx + 0.38 * s, cy + 0.09 * s, b,
           b + 0.17 * s, mat, cls);
      top = b + 0.2 * s;
    } else if (form === "beast") {
      [[-0.24, -0.13], [0.15, -0.13], [-0.24, 0.06], [0.15, 0.06]].forEach(function (l) {
        slab(out, cx + l[0] * s, cy + l[1] * s, cx + (l[0] + 0.07) * s,
             cy + (l[1] + 0.07) * s, b, b + 0.34 * s, mat, cls);
      });
      slab(out, cx - 0.3 * s, cy - 0.16 * s, cx + 0.24 * s, cy + 0.16 * s, b + 0.3 * s,
           b + 0.58 * s, mat, cls);
      slab(out, cx + 0.2 * s, cy - 0.11 * s, cx + 0.44 * s, cy + 0.11 * s, b + 0.44 * s,
           b + 0.7 * s, mat, cls);
      slab(out, cx - 0.42 * s, cy - 0.03 * s, cx - 0.3 * s, cy + 0.03 * s, b + 0.46 * s,
           b + 0.53 * s, mat, cls);
      // Ears, so the head reads as a head and the block as an animal, not a table.
      [-1, 1].forEach(function (k) {
        slab(out, cx + 0.24 * s, cy + k * 0.1 * s - 0.03 * s, cx + 0.3 * s,
             cy + k * 0.1 * s + 0.03 * s, b + 0.7 * s, b + 0.8 * s, mat, cls);
      });
      top = b + 0.8 * s;
    } else if (form === "ooze") {
      frustum(out, cx, cy, 0.38 * s, 0.32 * s, b, b + 0.14 * s, 10, mat, cls);
      frustum(out, cx, cy, 0.32 * s, 0.19 * s, b + 0.14 * s, b + 0.3 * s, 10, mat, cls);
      frustum(out, cx, cy, 0.19 * s, 0.06 * s, b + 0.3 * s, b + 0.38 * s, 10, mat, cls,
              { cls: cls });
      top = b + 0.38 * s;
    } else {
      // Two legs, a torso widening to the shoulders, arms at its sides, a head on a
      // neck: the pawn-like first cut (one tapered column) read as a bottle.
      [-1, 1].forEach(function (k) {
        frustum(out, cx + k * 0.08 * s, cy, 0.06 * s, 0.075 * s, b, b + 0.52 * s, 6, mat,
                cls);
        slab(out, cx + k * 0.23 * s - 0.04 * s, cy - 0.045 * s, cx + k * 0.23 * s + 0.04 * s,
             cy + 0.045 * s, b + 0.5 * s, b + 0.96 * s, mat, cls);
      });
      frustum(out, cx, cy, 0.13 * s, 0.21 * s, b + 0.5 * s, b + 0.96 * s, 6, mat, cls);
      frustum(out, cx, cy, 0.21 * s, 0.07 * s, b + 0.96 * s, b + 1.04 * s, 6, mat, cls);
      frustum(out, cx, cy, 0.09 * s, 0.15 * s, b + 1.06 * s, b + 1.19 * s, 6, mat, cls);
      frustum(out, cx, cy, 0.15 * s, 0.08 * s, b + 1.19 * s, b + 1.35 * s, 6, mat, cls,
              { cls: cls });
      top = b + 1.35 * s;
    }
    for (var i = start; i < out.length; i++) out[i].cull = true;
    return top;
  }

  /* --- textures (2026-11-11) -----------------------------------------------------------
     The owner: "make the textures like stone apear in the 3D view as well". Stone courses
     on walls and the sides of raised ground, planks on wall-walk tops and crates, a
     subtle flagstone on the floor: the flat board's materials, as SVG patterns.

     A pattern is laid in the FACE'S OWN PLANE. Its tile is drawn in squares and levels
     (u along the face, v up it or across it) and `patternTransform` is the projection of
     those two axes, so a course of stone runs level along a side face and a plank runs
     along a top, and both turn with the board. Under an orthographic camera every face
     of one orientation shares that map, so a board needs one pattern per material,
     orientation and lit colour — about a dozen — never one per square.

     The lamp stays on top of the texture: the pattern is painted in the face's lit
     colour (stone mortar and plank seams are that colour darkened), so a wall turned
     away from the lamp is dark stone and the lit one bright stone, as before.

     The cost the projection leaves: parallel walls a row apart start their courses at
     different heights (the plane through the origin is what the transform anchors). Real
     masonry is not coursed to the board either; measured by eye, it does not read. */
  function tint(hex, k) {
    var out = "#";
    for (var i = 1; i < 7; i += 2) {
      var v = Math.round(Math.max(0, Math.min(255, parseInt(hex.substr(i, 2), 16) * k)));
      out += (v < 16 ? "0" : "") + v.toString(16);
    }
    return out;
  }
  var TILES = {
    // Coursed stone: courses a quarter-level high, stones half a square long, bonded.
    stone: function (c) {
      var m = tint(c, 0.6);
      return [1, 0.5, '<rect width="1" height=".5" fill="' + c + '"/>' +
        '<rect x=".5" width=".5" height=".25" fill="' + tint(c, 1.1) + '"/>' +
        '<rect x=".25" y=".25" width=".5" height=".25" fill="' + tint(c, 0.9) + '"/>' +
        '<path d="M0 0h1v.025H0zM0 .25h1v.025H0zM0 0h.02v.25H0zM.5 0h.02v.25h-.02z' +
        'M.25 .25h.02v.25h-.02zM.75 .25h.02v.25h-.02z" fill="' + m + '"/>'];
    },
    // Boards a quarter-square wide, butt joints staggered.
    plank: function (c) {
      return [1, 0.75, '<rect width="1" height=".75" fill="' + c + '"/>' +
        '<rect y=".25" width="1" height=".25" fill="' + tint(c, 1.07) + '"/>' +
        '<path d="M0 0h1v.02H0zM0 .25h1v.02H0zM0 .5h1v.02H0zM.3 0h.02v.25h-.02z' +
        'M.75 .25h.02v.25h-.02zM.12 .5h.02v.25h-.02z" fill="' + tint(c, 0.62) + '"/>'];
    },
    /* The floor, quietly: two rows of slabs to a square, joints only, laid once over
       the whole ground as one polygon (see `ground` in render). Painted per tile it was
       576 pattern fills on a 24x24 board and doubled the time a turn takes to show
       (52 ms to 113, measured in Chrome); one overlay costs about nothing. */
    flag: function () {
      return [1, 1, '<path d="M0 .5h1v.018H0zM.5 0h.018v.5h-.018zM.25 .5h.018v.5h-.018z' +
        'M.75 .5h.018v.5h-.018z" fill="#0a0806" fill-opacity=".3"/>' +
        '<rect x=".5" width=".5" height=".5" fill="#0a0806" fill-opacity=".05"/>'];
    }
  };
  // Which texture a face wears: axis-aligned faces only (a barrel's staves and a figure
  // keep their flat lit colour), and never the thin detail panels laid over a face.
  function textureOf(f) {
    if (f.cls.indexOf("fxd") >= 0 || f.cls.lastIndexOf("fig", 0) === 0) return null;
    var up = f.n[2] === 1, side = !f.n[2] && (Math.abs(f.n[0]) === 1 || Math.abs(f.n[1]) === 1);
    if (!up && !side) return null;
    if (f.mat === "solid" || f.mat === "stone") return "stone";
    if (f.mat === "raised") return up ? "plank" : "stone";
    if (f.mat === "wood" || (f.mat === "plank" && up)) return "plank";
    return null;
  }

  // Whether screen point p lies inside polygon q (even-odd ray cast).
  function inside(p, q) {
    var hit = false;
    for (var i = 0, j = q.length - 1; i < q.length; j = i++) {
      if ((q[i][1] > p[1]) !== (q[j][1] > p[1]) &&
          p[0] < (q[j][0] - q[i][0]) * (p[1] - q[i][1]) / (q[j][1] - q[i][1]) + q[i][0]) {
        hit = !hit;
      }
    }
    return hit;
  }

  // --- fixtures as the things they are (2026-11-11) ---------------------------------------
  // The owner: "i want the fixtures to actually look like what the represent". Each kind
  // in content/rules/fixtures.json is built from the same lit faces as everything else —
  // prisms, slabs and thin panels laid on their faces — never an image or an icon, in the
  // table's own browns, greys and ember. Detail panels carry `fxd` (no outline stroke, so a
  // plank seam reads as a seam) and `pointer-events="none"`, so a click still lands on the
  // square under them.

  // A box whose top and sides are different stuff: a tread over its riser, a counter top.
  function slab2(out, x0, y0, x1, y1, z0, z1, top, side, cls, attrs) {
    face(out, [[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], UP, top, cls, attrs);
    face(out, [[x0, y0, z1], [x1, y0, z1], [x1, y0, z0], [x0, y0, z0]], NORTH, side, cls, attrs);
    face(out, [[x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0]], SOUTH, side, cls, attrs);
    face(out, [[x0, y0, z1], [x0, y1, z1], [x0, y1, z0], [x0, y0, z0]], WEST, side, cls, attrs);
    face(out, [[x1, y0, z1], [x1, y1, z1], [x1, y1, z0], [x1, y0, z0]], EAST, side, cls, attrs);
  }

  // An upright n-sided prism: a barrel's staves (or only a band of them, `sidesOnly`).
  function prism(out, cx, cy, r, z0, z1, mat, cls, sidesOnly, top) {
    var n = 8, ring = [];
    for (var i = 0; i < n; i++) {
      var a = (i + 0.5) / n * 2 * Math.PI;
      ring.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
    }
    for (i = 0; i < n; i++) {
      var p = ring[i], q = ring[(i + 1) % n], m = (i + 1) / n * 2 * Math.PI;
      face(out, [[p[0], p[1], z1], [q[0], q[1], z1], [q[0], q[1], z0], [p[0], p[1], z0]],
           [Math.cos(m), Math.sin(m), 0], mat, cls, NOPOINT);
    }
    if (!sidesOnly) {
      face(out, ring.map(function (p) { return [p[0], p[1], z1]; }), UP, top || mat, cls,
           NOPOINT);
    }
  }

  // A thin panel lying on one face of the box [x0,x1]x[y0,y1], `d` the face's outward
  // direction, from fraction a0 to a1 along it and z0 to z1 up it, a hair proud of it.
  function panel(out, x0, y0, x1, y1, d, a0, a1, z0, z1, mat, cls) {
    var e = 0.012, pts;
    if (d[1]) {
      var py = d[1] > 0 ? y1 + e : y0 - e, u0 = x0 + (x1 - x0) * a0, u1 = x0 + (x1 - x0) * a1;
      pts = [[u0, py, z1], [u1, py, z1], [u1, py, z0], [u0, py, z0]];
    } else {
      var px = d[0] > 0 ? x1 + e : x0 - e, v0 = y0 + (y1 - y0) * a0, v1 = y0 + (y1 - y0) * a1;
      pts = [[px, v0, z1], [px, v1, z1], [px, v1, z0], [px, v0, z0]];
    }
    face(out, pts, [d[0], d[1], 0], mat, cls + " fxd", NOPOINT);
  }

  // A thin strip on a top face at height z, across the square along x (`alongX`) or y.
  function seam(out, x0, y0, x1, y1, z, at, alongX, mat, cls) {
    var w = 0.025;
    var pts = alongX
      ? [[x0, at - w, z], [x1, at - w, z], [x1, at + w, z], [x0, at + w, z]]
      : [[at - w, y0, z], [at + w, y0, z], [at + w, y1, z], [at - w, y1, z]];
    face(out, pts, UP, mat, cls + " fxd", NOPOINT);
  }

  var NOPOINT = ' pointer-events="none"';
  var SIDES = [[0, -1], [0, 1], [-1, 0], [1, 0]];
  var SPINES = ["spine0", "spine1", "spine2", "spine3", "spine4"];

  /* One fixture square, drawn as its kind. `front` is the side facing the open floor
     (where a shelf's spines and a hearth's fire are), `runX` whether the fixture runs
     along x (a counter's length, a cart's axle across it). Returns the height it reaches,
     or -1 when the kind has no drawing of its own and the plain block should stand. */
  function fixtureAt(out, f, x, y, z, front, runX, cls) {
    var k = f.kind, i;
    if (k === "barrel") {
      prism(out, x + 0.5, y + 0.5, 0.36, z, z + 0.9, "wood", cls, false, "plank");
      prism(out, x + 0.5, y + 0.5, 0.372, z + 0.15, z + 0.24, "hoop", cls + " fxd", true);
      prism(out, x + 0.5, y + 0.5, 0.372, z + 0.66, z + 0.75, "hoop", cls + " fxd", true);
      return z + 0.9;
    }
    if (k === "crate") {
      var b = [x + 0.1, y + 0.1, x + 0.9, y + 0.9], h = z + 0.82;
      slab(out, b[0], b[1], b[2], b[3], z, h, "wood", cls, NOPOINT);
      SIDES.forEach(function (d) {
        panel(out, b[0], b[1], b[2], b[3], d, 0, 1, z + 0.27, z + 0.3, "wooddark", cls);
        panel(out, b[0], b[1], b[2], b[3], d, 0, 1, z + 0.53, z + 0.56, "wooddark", cls);
        panel(out, b[0], b[1], b[2], b[3], d, 0.04, 0.12, z + 0.04, h - 0.02, "plank", cls);
        panel(out, b[0], b[1], b[2], b[3], d, 0.88, 0.96, z + 0.04, h - 0.02, "plank", cls);
      });
      seam(out, b[0], b[1], b[2], b[3], h + 0.002, y + 0.37, true, "wooddark", cls);
      seam(out, b[0], b[1], b[2], b[3], h + 0.002, y + 0.63, true, "wooddark", cls);
      return h;
    }
    if (k === "table") {
      slab2(out, x + 0.02, y + 0.02, x + 0.98, y + 0.98, z + 0.68, z + 0.8, "plank", "wood",
            cls, NOPOINT);
      [[0.1, 0.1], [0.82, 0.1], [0.1, 0.82], [0.82, 0.82]].forEach(function (l) {
        slab(out, x + l[0], y + l[1], x + l[0] + 0.08, y + l[1] + 0.08, z, z + 0.68,
             "wooddark", cls, NOPOINT);
      });
      return z + 0.8;
    }
    if (k === "counter") {
      slab(out, x + 0.06, y + 0.06, x + 0.94, y + 0.94, z, z + 0.95, "wooddark", cls,
           NOPOINT);
      slab2(out, x, y, x + 1, y + 1, z + 0.95, z + 1.05, "plank", "wood", cls, NOPOINT);
      panel(out, x + 0.06, y + 0.06, x + 0.94, y + 0.94, front, 0.12, 0.88, z + 0.15,
            z + 0.82, "wood", cls);
      return z + 1.05;
    }
    if (k === "stall") {
      // A trestle counter, two poles at its back and a cloth awning over the lot: the
      // book-spine red, with a brass fringe along the front edge.
      slab(out, x + 0.08, y + 0.08, x + 0.92, y + 0.92, z, z + 0.78, "wooddark", cls, NOPOINT);
      slab2(out, x + 0.02, y + 0.02, x + 0.98, y + 0.98, z + 0.78, z + 0.86, "plank", "wood",
            cls, NOPOINT);
      var bx = front[0] ? (front[0] > 0 ? x + 0.06 : x + 0.86) : null;
      var by = front[1] ? (front[1] > 0 ? y + 0.06 : y + 0.86) : null;
      (bx !== null ? [[bx, y + 0.06], [bx, y + 0.86]] : [[x + 0.06, by], [x + 0.86, by]])
        .forEach(function (p) {
          slab(out, p[0], p[1], p[0] + 0.08, p[1] + 0.08, z + 0.86, z + 1.75, "wooddark", cls,
               NOPOINT);
        });
      slab(out, x - 0.02, y - 0.02, x + 1.02, y + 1.02, z + 1.75, z + 1.81, "spine0", cls,
           NOPOINT);
      panel(out, x - 0.02, y - 0.02, x + 1.02, y + 1.02, front, 0, 1, z + 1.66, z + 1.75,
            "plank", cls);
      return z + 1.81;
    }
    if (k === "hearth") {
      slab(out, x + 0.03, y + 0.03, x + 0.97, y + 0.97, z, z + 1, "stone", cls, NOPOINT);
      SIDES.forEach(function (d) {
        panel(out, x + 0.03, y + 0.03, x + 0.97, y + 0.97, d, 0, 1, z + 0.33, z + 0.36,
              "stonedark", cls);
        panel(out, x + 0.03, y + 0.03, x + 0.97, y + 0.97, d, 0, 1, z + 0.66, z + 0.69,
              "stonedark", cls);
      });
      panel(out, x + 0.03, y + 0.03, x + 0.97, y + 0.97, front, 0.22, 0.78, z + 0.06,
            z + 0.62, "ember", cls);
      face(out, [[x + 0.28, y + 0.28, z + 1.003], [x + 0.72, y + 0.28, z + 1.003],
                 [x + 0.72, y + 0.72, z + 1.003], [x + 0.28, y + 0.72, z + 1.003]],
           UP, "ember", cls + " fxd", NOPOINT);
      return z + 1;
    }
    if (k === "bookshelf" || k === "rack") {
      // A case against the wall behind it, its open face to the room.
      var c0 = [x, y, x + 1, y + 1], depth = 0.5, top = z + 1.9;
      if (front[1] > 0) c0[1] = y + 1 - depth;
      else if (front[1] < 0) c0[3] = y + depth;
      else if (front[0] > 0) c0[0] = x + 1 - depth;
      else c0[2] = x + depth;
      slab(out, c0[0], c0[1], c0[2], c0[3], z, top, "wooddark", cls, NOPOINT);
      var rows = [z + 0.06, z + 0.68, z + 1.3];
      rows.forEach(function (r0, ri) {
        panel(out, c0[0], c0[1], c0[2], c0[3], front, 0, 1, r0 - 0.05, r0, "plank", cls);
        if (k === "bookshelf") {
          var spots = [[0.05, 0.22], [0.24, 0.37], [0.39, 0.58], [0.6, 0.74], [0.76, 0.95]];
          spots.forEach(function (s, si) {
            var tall = 0.42 + ((si + ri) % 3) * 0.05;
            panel(out, c0[0], c0[1], c0[2], c0[3], front, s[0], s[1], r0, r0 + tall,
                  SPINES[(si * 2 + ri) % SPINES.length], cls);
          });
        } else {
          [0.18, 0.5, 0.82].forEach(function (a) {
            panel(out, c0[0], c0[1], c0[2], c0[3], front, a - 0.025, a + 0.025, r0,
                  r0 + 0.52, "iron", cls);
          });
        }
      });
      panel(out, c0[0], c0[1], c0[2], c0[3], front, 0, 1, top - 0.05, top, "plank", cls);
      return top;
    }
    if (k === "cart") {
      var bed0 = z + 0.32, bed1 = z + 0.6;
      slab(out, x + 0.06, y + 0.06, x + 0.94, y + 0.94, bed0, bed1, "wood", cls, NOPOINT);
      seam(out, x + 0.06, y + 0.06, x + 0.94, y + 0.94, bed1 + 0.002, runX ? y + 0.37 : x + 0.37,
           runX, "wooddark", cls);
      seam(out, x + 0.06, y + 0.06, x + 0.94, y + 0.94, bed1 + 0.002, runX ? y + 0.63 : x + 0.63,
           runX, "wooddark", cls);
      // A wheel on each long side: an upright octagon, its hub at the axle.
      (runX ? [[0, -1], [0, 1]] : [[-1, 0], [1, 0]]).forEach(function (d) {
        var pts = [], r = 0.3, cz = z + 0.3;
        for (i = 0; i < 8; i++) {
          var a = (i + 0.5) / 8 * 2 * Math.PI, u = 0.5 + r * Math.cos(a), w = cz + r * Math.sin(a);
          pts.push(d[1] ? [x + u, d[1] > 0 ? y + 0.97 : y + 0.03, w]
                        : [d[0] > 0 ? x + 0.97 : x + 0.03, y + u, w]);
        }
        face(out, pts, [d[0], d[1], 0], "hoop", cls, NOPOINT);
      });
      return bed1;
    }
    return -1;
  }

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
    // The named fixtures (rules/fixtures.py). A low one (a table, the bar, a barrel) stands
    // one level high rather than a wall's two, which is what the engine now reads it as —
    // something you see and shoot over — and anything a person put there is brass, the
    // palette's own word for it. Stairs are drawn after the floor, as steps.
    var fx = {}, stairs = [];
    (g.fixtures || []).forEach(function (f) {
      (f.squares || []).forEach(function (p) { fx[key(p[0], p[1])] = f; });
      if (f.form === "steps") stairs.push(f);
    });

    // Which way a fixture runs (a counter's length) and which side of a square faces the
    // open floor (where a shelf shows its spines and a hearth its fire).
    function runsX(f) {
      var xs = f.squares.map(function (p) { return p[0]; });
      var ys = f.squares.map(function (p) { return p[1]; });
      return Math.max.apply(null, xs) - Math.min.apply(null, xs) >=
             Math.max.apply(null, ys) - Math.min.apply(null, ys);
    }
    function frontOf(f, x, y) {
      var sides = runsX(f) ? [[0, 1], [0, -1]] : [[1, 0], [-1, 0]];
      for (var i = 0; i < sides.length; i++) {
        var nx = x + sides[i][0], ny = y + sides[i][1];
        if (nx >= 0 && ny >= 0 && nx < W && ny < H && !solid[key(nx, ny)]) return sides[i];
      }
      return sides[0];
    }
    // What lies ON a walkable square: a gallery's planks, water's ripples, rubble's stones.
    function surface(out, f, x, y, z, cls) {
      if (!f) return;
      var t = z + 0.003;
      if (f.kind === "gallery") {
        var ax = runsX(f);
        [0.33, 0.66].forEach(function (a) {
          seam(out, x, y, x + 1, y + 1, t, (ax ? y : x) + a, ax, "wooddark", cls);
        });
      } else if (f.kind === "water") {
        face(out, [[x + 0.15, y + 0.33, t], [x + 0.6, y + 0.33, t], [x + 0.6, y + 0.37, t],
                   [x + 0.15, y + 0.37, t]], UP, "waterhi", cls + " fxd", NOPOINT);
        face(out, [[x + 0.4, y + 0.68, t], [x + 0.85, y + 0.68, t], [x + 0.85, y + 0.72, t],
                   [x + 0.4, y + 0.72, t]], UP, "waterhi", cls + " fxd", NOPOINT);
      } else if ((f.kind === "crate" || f.kind === "cart") && z > 0) {
        // Climbable: the raised square itself is the crate or the cart's bed.
        SIDES.forEach(function (d) {
          if (f.kind === "crate") {
            panel(out, x, y, x + 1, y + 1, d, 0.04, 0.12, 0.04, z - 0.02, "plank", cls);
            panel(out, x, y, x + 1, y + 1, d, 0.88, 0.96, 0.04, z - 0.02, "plank", cls);
            panel(out, x, y, x + 1, y + 1, d, 0, 1, z * 0.5 - 0.015, z * 0.5 + 0.015,
                  "wooddark", cls);
          }
        });
        seam(out, x, y, x + 1, y + 1, t, y + 0.37, true, "wooddark", cls);
        seam(out, x, y, x + 1, y + 1, t, y + 0.63, true, "wooddark", cls);
      } else if (f.kind === "rubble") {
        var h = (x * 7 + y * 13) % 5;
        [[0.15, 0.2, 0.18], [0.55, 0.15, 0.12], [0.35, 0.6, 0.2], [0.68, 0.62, 0.14]]
          .forEach(function (r, i) {
            if ((h + i) % 5 === 4) return;
            slab(out, x + r[0], y + r[1], x + r[0] + 0.2, y + r[1] + 0.17, z, z + r[2],
                 "stone", cls + " fxd", NOPOINT);
          });
      }
    }

    var reach = {};
    (g.reachable || []).forEach(function (e) { reach[key(e[0], e[1])] = e; });

    // How high the ground stands in every square, worked out once: a wall is only a wall
    // where the square next door is lower, and answering that per neighbour per square
    // needs the whole board first. Off the edge of the board reads as ground level, so
    // the outside faces of the room are drawn.
    function topAt(x, y) {
      if (x < 0 || y < 0 || x >= W || y >= H) return 0;
      var k = key(x, y), z = ground[k] || 0;
      if (!solid[k]) return z;
      return fx[k] && fx[k].height === 1 ? z + 1 : Math.max(z + 2, 2);
    }

    var faces = [], tallest = 1;
    for (var x = 0; x < W; x++) {
      for (var y = 0; y < H; y++) {
        var k = key(x, y), z = ground[k] || 0, mat = "tile", cls = "tile";
        if (solid[k]) { mat = fx[k] && fx[k].height ? "rail" : "solid"; cls = "solid"; }
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

        /* RAISED GROUND IS SOLID (2026-11-11). It used to be drawn at 45% whenever it
           stood above the level being looked at, so a token under a gallery stayed in
           view — and the owner saw the whole mass as glass: "fix the glass block". The
           mass is opaque now, and only what it actually hides is shown through it (the
           x-ray pass at the end of `render`). */
        var f3 = fx[k], drawn = -1;
        // A crate or cart you can climb onto (a raised square, not a solid one) is built of
        // wood, not of the room's raised floor.
        if (f3 && !solid[k] && (f3.kind === "crate" || f3.kind === "cart")) mat = "wood";
        if (solid[k] && f3) {
          drawn = fixtureAt(faces, f3, x, y, z, frontOf(f3, x, y), runsX(f3), cls);
        }
        if (drawn >= 0) {
          // The floor under it, holding the name for the pointer (the drawing is deaf).
          cap(faces, x, y, z, z ? "raised" : "tile", "tile", "",
              "<title>" + esc(f3.name) + "</title>", 0, false);
          if (z > 0) {
            walls(faces, x, y, z, [topAt(x, y - 1), topAt(x, y + 1), topAt(x - 1, y),
                                   topAt(x + 1, y)], "raised", "tile");
          }
        } else {
          if (f3 && f3.kind === "water") mat = "water";
          cap(faces, x, y, topz, mat, cls, hit,
              f3 && solid[k] ? "<title>" + esc(f3.name) + "</title>" : "",
              solid[k] ? (f3 && f3.form === "round" ? 0.18 : 0.07) : 0, wash);
          if (topz > 0) {
            walls(faces, x, y, topz,
                  [topAt(x, y - 1), topAt(x, y + 1), topAt(x - 1, y), topAt(x + 1, y)],
                  mat, cls);
          }
          surface(faces, f3, x, y, topz, cls);
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
          var rcls = "rail3";
          /* A GALLERY'S RAIL IS DRAWN ON THE GALLERY'S EDGE (2026-11-11). The floorplan
             stores a gallery's rail on the ground square in front of it (`_raise`'s lip),
             so the pane above stood in the middle of that square: at the gate it cut the
             stair in half and ran through the player standing beside it. What the rule
             asks of that square — lines at or under the walkway stopped — is the
             gallery's own face, which `walls` already draws; what a player needs to see
             is the railing on top of it. So where the square in front of the rail is
             floor at the rail's height, the rail is a low bar on that shared edge, from
             the walkway up, and the lip square stays clear. */
          var edge = null;
          [[0, -1], [0, 1], [-1, 0], [1, 0]].forEach(function (d) {
            var n = key(x + d[0], y + d[1]);
            if (!edge && !solid[n] && (ground[n] || 0) >= top) edge = d;
          });
          if (edge) {
            var e = 0.09, rh = 0.42;
            var ex0 = edge[0] > 0 ? x + 1 : edge[0] < 0 ? x - e : x;
            var ex1 = edge[0] > 0 ? x + 1 + e : edge[0] < 0 ? x : x + 1;
            var ey0 = edge[1] > 0 ? y + 1 : edge[1] < 0 ? y - e : y;
            var ey1 = edge[1] > 0 ? y + 1 + e : edge[1] < 0 ? y : y + 1;
            slab(faces, ex0, ey0, ex1, ey1, top, top + rh, "rail", rcls);
            if (top + rh > tallest) tallest = top + rh;
          } else if (top > foot) {
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

    /* A stair as real steps (2026-11-11, the owner: "get the shape right"): four solid
       steps climbing toward the higher ground beside it, each a lighter tread over a
       darker riser, the last one meeting the gallery's floor. Deaf to the pointer, so the
       floor under them still takes the click that queues a move onto the stair. */
    stairs.forEach(function (f) {
      (f.squares || []).forEach(function (p) {
        var sx = p[0], sy = p[1], z0 = ground[key(sx, sy)] || 0;
        var best = SIDES[0], hi = -1;
        SIDES.forEach(function (d) {
          var h = topAt(sx + d[0], sy + d[1]);
          if (!solid[key(sx + d[0], sy + d[1])] && h > hi) { hi = h; best = d; }
        });
        var rise = Math.max(1, hi - z0), n = 4;
        for (var i = 0; i < n; i++) {
          // Step i covers the i-th quarter of the square counted from the far side, so
          // the highest step is the one against the gallery.
          var a0 = (n - 1 - i) / n, a1 = (n - i) / n, x0, x1, y0, y1;
          if (best[0]) {
            x0 = best[0] > 0 ? sx + a0 : sx + 1 - a1; x1 = x0 + 1 / n; y0 = sy; y1 = sy + 1;
          } else {
            y0 = best[1] > 0 ? sy + a0 : sy + 1 - a1; y1 = y0 + 1 / n; x0 = sx; x1 = sx + 1;
          }
          var zt = z0 + (n - i) * rise / n;
          slab2(faces, x0, y0, x1, y1, z0, zt, "tread", "wooddark",
                "fxstep", NOPOINT);
        }
        if (z0 + rise > tallest) tallest = z0 + rise;
      });
    });

    /* The latest turn's spell areas (`g.areas`, the engine's ruling on where a cone or
       burst fell). Until 2026-09-29 only the flat board drew them, so turning on 3D hid
       exactly the thing a player switches views to check: where the fire went.

       One square per column, as the flat map draws it, and by the flat map's own rule
       for which: a column with a cell on the level being looked at (its level, or that
       far above the ground under it) is filled, lying on that cell's floor; a column
       whose cells are all above or below (a cone into the canopy) is a dashed outline
       at the lowest of them, so a spell aimed up floats up. The same colours as the
       flat board's `.spellarea`, written as attributes here because this view keeps
       `fill` out of the stylesheet (see #view3d in table.html).

       Lifted a hair off the floor so the depth sort puts it over its own tile and under
       anybody standing in it, and `pointer-events="none"` so a lit square underneath
       still takes the click that queues a move. Drawn for what the engine sent and
       nothing more: this adds no cells and removes none. */
    var shown = {};
    (g.areas || []).forEach(function (a) {
      if (!a || !(a.cells || []).length) return;
      a.cells.forEach(function (cell) {
        var c = cell[0], r = cell[1], z = cell.length > 2 ? cell[2] : 0;
        var k = key(c, r), under = ground[k] || 0;
        var here = z - under === level || z === level;
        var was = shown[k];
        if (!was || (here && !was.here) || (here === was.here && z < was.z)) {
          shown[k] = { c: c, r: r, z: z, here: here, spell: a.spell };
        }
      });
    });
    Object.keys(shown).forEach(function (k) {
      var s = shown[k], z = s.z + 0.02;
      var name = esc(String(s.spell || "a spell").replace(/-/g, " "));
      // The stroke as a style, not attributes: `#view3d polygon` sets every face's
      // stroke in the stylesheet, and a stylesheet rule beats a presentation attribute.
      var attrs = s.here
        ? ' fill-opacity="0.32" style="stroke:#f0a050;stroke-opacity:.55;stroke-width:.8"'
        : ' fill-opacity="0" style="stroke:#f0a050;stroke-opacity:.8;stroke-width:1.2;' +
          'stroke-dasharray:3 2"';
      face(faces, [[s.c, s.r, z], [s.c + 1, s.r, z], [s.c + 1, s.r + 1, z],
                   [s.c, s.r + 1, z]], UP, "area",
           "spellarea3" + (s.here ? "" : " offlevel"),
           attrs + ' pointer-events="none"',
           "<title>" + name + (s.here ? "" : ", above or below this floor") + "</title>");
    });

    var figs = [];
    (actors || []).forEach(function (a) {
      if (!a.at) return;
      var ax = a.at[0], ay = a.at[1], az = a.at.length > 2 ? a.at[2] : 0;
      var n = a.squares || 1;
      /* The server's `stance` (attitude.stance), the one answer the flat map and the
         panel read too; never worked out here from a fight's side name. */
      var side = a.stance || "bystander";
      var down = a.hp <= 0;
      var cls = "fig " + side + (down ? " down" : "");
      if (az !== level) cls += " offlevel";
      var tip = "<title>" + esc(a.name || "") + " — " + a.hp + "/" + a.hp_max +
                (a.members != null ? " · " + a.members + " of " + a.members_max +
                 " still standing" : "") +
                (az ? " · " + az * 5 + " ft up" : "") + "</title>";
      // Whose turn it is: a gold rim on the base (the flat token's ring, in 3D).
      var baseCls = " base" + (opts.up && a.ref === opts.up ? " up" : "");
      var start = faces.length, cx = ax + n / 2, cy = ay + n / 2, top;
      if (a.members != null) {
        /* A crowd held as one actor (item 33): three small people standing together on
           its footprint, never one big body — a 3x3 block read as a giant. */
        top = az;
        [[0.28, 0.3], [0.72, 0.36], [0.46, 0.74]].forEach(function (o, i) {
          top = Math.max(top, figure(faces, ax + n * o[0], ay + n * o[1], az, n * 0.42,
                                     a.form, down, side, cls, baseCls, i ? "" : tip));
        });
      } else {
        // A Large body stands on its whole footprint, and as much taller as it is wider.
        top = figure(faces, cx, cy, az, n, a.form, down, side, cls, baseCls, tip);
      }
      /* The letter, on a small plate over the head: the flat token's initial, or a
         crowd's count. In the depth sort like a face, so a wall in front still covers it
         (and the x-ray then shows it). */
      var mark = a.members != null ? String(a.members)
        : String(a.name || "?").slice(0, 1).toUpperCase();
      faces.push({ pts: [[cx, cy, top + 0.32]], n: UP, at: [cx, cy, top + 0.32], mat: side,
                   cls: cls.replace("fig ", "fig plate "), attrs: "", inner: tip,
                   plate: esc(mark) });
      if (top + 0.6 > tallest) tallest = top + 0.6;
      figs.push({ faces: faces.slice(start), x: cx, y: cy, z: az, top: top,
                  own: [ax, ay, ax + n, ay + n], offlevel: az !== level });
    });

    // Back to front. One comparison on the real distance to the viewer, where the first
    // version summed a rotated row and column and added hand-picked offsets for the
    // things that came out wrong. A face marked `cull` (a closed solid's back) that faces
    // away from the camera is hidden by its own front and is not drawn at all.
    faces = faces.filter(function (f) {
      return !f.cull || dot(turned(f.n, turn), TOWARD) > 0;
    });
    faces.forEach(function (f) {
      f.d = depth(f.at, turn);
      f.sp = f.pts.map(function (p) { return project(p, turn); });
    });
    /* Ground-level floor first, whatever its depth: nothing lies under it, so it can
       never hide anything and is always safe to paint before the rest. That makes room
       for the floor's texture to go down as ONE polygon right after it. */
    faces.forEach(function (f) {
      f.ground = f.n === UP && f.cls.lastIndexOf("tile", 0) === 0 &&
        f.cls.indexOf("fxd") < 0 && f.pts.every(function (p) { return p[2] === 0; });
    });
    faces.sort(function (a, b) { return (b.ground - a.ground) || (a.d - b.d); });

    /* WHAT A MASS HIDES IS SHOWN THROUGH IT, AND NOTHING ELSE IS (2026-11-11).
     *
     * The tactical games that put people behind walls agree on the shape of the answer
     * and disagree only on the cut. Baldur's Gate 3 cuts a circular hole through the wall
     * round the character (community recreations of its "occlusion cutout": 80.lv,
     * Brendan Sullivan's ArtStation write-up); Divinity: Original Sin 2 and Torchlight 2
     * draw the hidden character's silhouette over the wall (players asking BG3 for
     * opaque walls cite Divinity's outline as what they want — Steam discussion
     * 3811785047377002290). XCOM 2 fades whole walls and roofs, which players report as
     * "translucent walls" they cannot read — the glass this replaced. A hole needs a
     * depth buffer this painter's-sort SVG does not have; a silhouette needs only the
     * figure's own faces drawn again, last. So: the mass stays solid, and a token the
     * mass actually hides is drawn over it as a flat ghost in its side's colour.
     *
     * "Actually hides" is measured, not guessed: three points up the figure's axis, each
     * tested against every face nearer the camera than it that rises above the floor the
     * figure stands on (a floor tile in front cannot hide anybody). Two of three covered
     * and the figure is hidden. The same test on five points of each square the player
     * can reach, four of them covered: such a square is redrawn as an outline on top,
     * carrying the same `data-sq`, so a move can still be queued onto the floor behind
     * a gallery. Both are
     * worked out from the projected faces after the sort, so they hold at every
     * quarter-turn and agree with the painter's order by construction. */
    var masses = faces.filter(function (f) {
      if (f.mat === "area" || f.cls.lastIndexOf("fig", 0) === 0) return false;
      var top = -1e9, x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      f.pts.forEach(function (p) { if (p[2] > top) top = p[2]; });
      f.sp.forEach(function (p) {
        if (p[0] < x0) x0 = p[0]; if (p[0] > x1) x1 = p[0];
        if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1];
      });
      f.top = top; f.box = [x0, y0, x1, y1];
      return true;
    });
    // Binned by screen position, so a point is tested against the few faces over it
    // rather than every face on the board (a 24x24 board: 31 ms of render to 10).
    var BIN = 24, bins = {};
    masses.forEach(function (m) {
      for (var bx = Math.floor(m.box[0] / BIN); bx <= Math.floor(m.box[2] / BIN); bx++) {
        for (var by = Math.floor(m.box[1] / BIN); by <= Math.floor(m.box[3] / BIN); by++) {
          (bins[bx + "," + by] = bins[bx + "," + by] || []).push(m);
        }
      }
    });
    // `own` is the footprint the thing stands on: a stair's own steps, the crate it is
    // climbing, are under it, not in front of it (measured at the gate: the player on
    // the stair was ghosted at every turn by the steps beneath their feet).
    function covered(p, floor, own) {
      var d = depth(p, turn), s = project(p, turn);
      var near = bins[Math.floor(s[0] / BIN) + "," + Math.floor(s[1] / BIN)] || [];
      for (var i = 0; i < near.length; i++) {
        var m = near[i], b = m.box;
        if (m.d <= d || m.top <= floor + 0.05) continue;
        if (m.at[0] > own[0] && m.at[0] < own[2] && m.at[1] > own[1] && m.at[1] < own[3]) {
          continue;
        }
        if (s[0] < b[0] || s[0] > b[2] || s[1] < b[1] || s[1] > b[3]) continue;
        if (inside(s, m.sp)) return true;
      }
      return false;
    }
    function pts2(sp) {
      return sp.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ");
    }
    var xray = "";
    figs.forEach(function (g) {
      var h = g.top - g.z, hid = 0;
      [0.3, 0.6, 0.9].forEach(function (k) {
        if (covered([g.x, g.y, g.z + h * k], g.z, g.own)) hid++;
      });
      if (hid < 2) return;
      xray += '<g class="xray' + (g.offlevel ? " offlevel" : "") + '" pointer-events="none">' +
        g.faces.filter(function (f) { return f.sp; }).map(function (f) {
          return f.plate ? plate(f, "plate") : '<polygon fill="' + paint(f.mat, shade(f.n, turn)) +
            '" points="' + pts2(f.sp) + '"/>';
        }).join("") + "</g>";
    });
    faces.forEach(function (f) {
      if (f.attrs.indexOf("data-sq") < 0) return;
      var c = f.at, z = c[2], hid = 0, sq = [Math.floor(c[0]), Math.floor(c[1])];
      sq.push(sq[0] + 1, sq[1] + 1);
      var seen = 0;
      [[0, 0], [-0.3, -0.3], [0.3, -0.3], [-0.3, 0.3], [0.3, 0.3]].forEach(function (o) {
        if (seen > 1) return;          // two points in view: it can no longer be hidden
        if (covered([c[0] + o[0], c[1] + o[1], z], z, sq)) hid++; else seen++;
      });
      if (hid < 4) return;           // mostly in view: the square itself takes the click
      xray += '<polygon class="xsq lit face-top" points="' + pts2(f.sp) + '"' + f.attrs +
        "><title>reachable, behind what stands in front of it</title></polygon>";
    });

    // The face's own plane, projected: its u and v axes in screen pixels (`TILES`).
    var AXES = { z: [[1, 0, 0], [0, 1, 0]], y: [[1, 0, 0], [0, 0, 1]],
                 x: [[0, 1, 0], [0, 0, 1]] };
    var defs = {};
    function textured(tex, n, hex) {
      var axis = n[2] ? "z" : n[1] ? "y" : "x", id = "s3" + tex + axis + hex.slice(1);
      if (!defs[id]) {
        var u = project(AXES[axis][0], turn), v = project(AXES[axis][1], turn);
        var t = TILES[tex](hex);
        defs[id] = '<pattern id="' + id + '" patternUnits="userSpaceOnUse" width="' + t[0] +
          '" height="' + t[1] + '" patternTransform="matrix(' + [u[0], u[1], v[0], v[1]]
          .map(function (k) { return k.toFixed(3); }).join(" ") + ' 0 0)">' + t[2] +
          "</pattern>";
      }
      return "url(#" + id + ")";
    }

    // A figure's letter plate: the side's colour, unshaded, as the flat token's is.
    function plate(f, cls) {
      var p = f.sp[0];
      return '<g class="' + cls + '"><rect x="' + (p[0] - 4.2).toFixed(1) + '" y="' +
        (p[1] - 4.6).toFixed(1) + '" width="8.4" height="8.4" rx="1.8" fill="' +
        paint(f.mat, 1) + '"/><text x="' + p[0].toFixed(1) + '" y="' + (p[1] + 2.3).toFixed(1) +
        '">' + f.plate + "</text>" + (cls === "plate" ? "" : f.inner) + "</g>";
    }

    var laid = false;
    function floorTex() {
      laid = true;
      return '<polygon class="floortex" pointer-events="none" fill="' +
        textured("flag", UP, "#000000") + '" points="' +
        pts2([[0, 0, 0], [W, 0, 0], [W, H, 0], [0, H, 0]].map(function (p) {
          return project(p, turn); })) + '"/>';
    }
    var body = faces.map(function (f) {
      var lay = !f.ground && !laid ? floorTex() : "";
      if (f.plate) return lay + plate(f, f.cls);
      // A spell's area is a tint over the board, not a lit surface: the flat map's own
      // colour, unshaded, so the two views show the same orange.
      var fill = f.mat === "area" ? AREA : f.mat === "ember" ? EMBER
        : paint(f.mat, shade(f.n, turn), f.wash);
      var tex = f.mat !== "area" && textureOf(f);
      if (tex) fill = textured(tex, f.n, fill);
      // A textured side carries no outline: the courses are the detail, and a stroke at
      // every square's edge cut a twenty-square wall-walk into twenty boxes. Tops keep
      // theirs, because the squares on them are where a player moves.
      return lay + '<polygon class="' + f.cls + (tex && !f.n[2] ? " txs" : "") + '" fill="' + fill +
        '" points="' + pts2(f.sp) + '"' + f.attrs +
        (f.inner ? ">" + f.inner + "</polygon>" : "/>");
    }).join("") + (laid ? "" : floorTex()) + xray;

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
      w.toFixed(1) + " " + h.toFixed(1) + '" preserveAspectRatio="xMidYMid meet"><defs>' +
      Object.keys(defs).map(function (k) { return defs[k]; }).join("") + "</defs>" +
      body + "</svg>";
  }

  window.Scene3D = { render: render, TURNS: 4 };
})();
