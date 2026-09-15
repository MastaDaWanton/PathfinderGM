/* The board in three dimensions, drawn as flat shapes.
 *
 * Asked for in as many words: "a 3D viewport where i can see the action and choose where
 * to cast spells/use abilities (like x-com, but still text based and without fancy
 * textures. Just something you can clearly see and rotate)."
 *
 * WHY THIS IS SVG POLYGONS AND NOT A 3D LIBRARY. The app ships as an offline executable
 * and bundles no third-party JavaScript at all — `dice3d.js` builds five Platonic solids
 * from vertex arrays with no library behind it, and this is the same bargain one step
 * further. An axonometric projection with a painter's-algorithm depth sort is a few dozen
 * lines, needs nothing fetched, and draws exactly the blocky untextured look that was
 * asked for. WebGL buys free rotation at any angle; that is the only thing it buys here,
 * and see below for why that is not wanted.
 *
 * ROTATION IS FOUR FIXED QUARTER-TURNS, and that is a decision rather than a shortcut.
 * Firaxis chose the same for XCOM: a fixed camera with 90-degree steps, specifically
 * against the disorientation a free camera causes over a tactical map. Their own
 * postmortem also records cutting visualised sight lines after months because the lines
 * became "tough for the player to determine what was going on" — legibility is the thing
 * that kills a tactical 3D view, not frame rate. Quarter-turns keep every square in a
 * predictable place and keep the grid readable.
 *
 * WHAT IT DRAWS AND WHAT IT REFUSES TO INVENT. Everything comes from the geometry payload
 * `play/views.py::_grid_state` already sends — blocked, difficult, obscuring, floor,
 * parapet, ceiling, levels, and reachable-with-its-level. This module adds no facts. It
 * cannot: a viewport that decided where a wall was would be a second map disagreeing with
 * the one the rules use.
 *
 * Every top face carries `data-sq="c,r,level"`, which is the same attribute the flat map
 * writes and the combat builder already reads, so clicking a cell here queues a move or a
 * target through exactly the path the 2D map uses. That is the whole reason the flat
 * level-picker was built first.
 */
(function () {
  "use strict";

  // The projection. A square is drawn as a rhombus twice as wide as it is tall — the
  // 2:1 "game isometric" rather than a true 30-degree isometric, because 2:1 lands every
  // corner on a whole pixel and a grid drawn on half-pixels shimmers.
  var TILE_W = 26, TILE_H = 13, LEVEL_H = 16;

  function project(x, y, z, turn) {
    // Quarter-turns are applied to the coordinates, not the camera: rotating the board is
    // the same picture as walking round it, and doing it here keeps the depth sort and
    // the projection agreeing without a matrix between them.
    var a = x, b = y, t;
    for (var i = 0; i < (turn & 3); i++) { t = a; a = b; b = -t; }
    return [(a - b) * TILE_W / 2, (a + b) * TILE_H / 2 - z * LEVEL_H];
  }

  function depth(x, y, z, turn) {
    var a = x, b = y, t;
    for (var i = 0; i < (turn & 3); i++) { t = a; a = b; b = -t; }
    // Back to front: further from the viewer first, and higher things later so a token
    // on a gallery is drawn over the gallery it stands on.
    return (a + b) * 8 + z;
  }

  function poly(points, cls, extra, inner) {
    var open = '<polygon class="' + cls + '" points="' +
      points.map(function (p) { return p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ") +
      '"' + (extra || "");
    // A polygon with a child cannot be self-closing, and a `<title>` is how an SVG shape
    // gets a tooltip — so the two forms are spelled out here rather than patched together
    // by the caller.
    return inner ? open + ">" + inner + "</polygon>" : open + "/>";
  }

  // The four corners of one square's top face, at a level.
  function top(x, y, z, turn) {
    return [project(x, y, z, turn), project(x + 1, y, z, turn),
            project(x + 1, y + 1, z, turn), project(x, y + 1, z, turn)];
  }

  /* One box: a top face and the two side faces that can be seen from this angle.
   * Only two of the four sides ever face the viewer in an axonometric projection, and
   * which two depends on the turn — so they are picked rather than drawn and overdrawn,
   * which halves the polygons and keeps the SVG small enough to re-render every turn. */
  function box(x, y, z0, z1, turn, cls, attrs, inner) {
    var out = [];
    out.push(poly(top(x, y, z1, turn), cls + " face-top", attrs || "", inner || ""));
    out.push(poly([project(x, y + 1, z1, turn), project(x + 1, y + 1, z1, turn),
                   project(x + 1, y + 1, z0, turn), project(x, y + 1, z0, turn)],
                  cls + " face-a"));
    out.push(poly([project(x + 1, y, z1, turn), project(x + 1, y + 1, z1, turn),
                   project(x + 1, y + 1, z0, turn), project(x + 1, y, z0, turn)],
                  cls + " face-b"));
    return out.join("");
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

    var items = [];
    for (var x = 0; x < W; x++) {
      for (var y = 0; y < H; y++) {
        var k = key(x, y), z = ground[k] || 0;
        var cls = "tile";
        if (solid[k]) cls = "solid";
        else if (murk[k]) cls = "murk";
        else if (rough[k]) cls = "rough";
        else if (z) cls = "tile raised";

        var hit = "";
        if (!solid[k] && opts.reach && reach[k]) {
          cls += " lit";
          // The level a step onto this square actually lands on, straight from the
          // server's own answer. The flat map writes the same attribute.
          hit = ' data-sq="' + x + "," + y + (reach[k][3] ? "," + reach[k][3] : "") + '"';
        }
        var tall = solid[k] ? Math.max(z + 2, 2) : z;
        items.push([depth(x, y, z, turn),
                    tall > 0 ? box(x, y, 0, tall, turn, cls, hit)
                             : poly(top(x, y, 0, turn), cls, hit)]);

        if (rails[k] !== undefined) {
          // A rail is drawn as a thin standing plane on the square's far edge, not as a
          // block — it is a thing to shoot over, and drawing it solid would say the
          // opposite, which is the mistake the engine itself used to make.
          var rz = rails[k];
          items.push([depth(x, y, rz, turn) + 0.5,
            poly([project(x, y, rz + 0.55, turn), project(x + 1, y, rz + 0.55, turn),
                  project(x + 1, y, rz, turn), project(x, y, rz, turn)], "rail3")]);
        }
      }
    }

    (actors || []).forEach(function (a) {
      if (!a.at) return;
      var ax = a.at[0], ay = a.at[1], az = a.at.length > 2 ? a.at[2] : 0;
      var n = a.squares || 1;
      var cls = "fig" + (a.is_pc ? " pc" : a.side === "pc" || a.side === "you" ? " ally"
                        : a.side ? " foe" : " bystander") + (a.hp <= 0 ? " down" : "");
      if (az !== level) cls += " offlevel";
      for (var dx = 0; dx < n; dx++) {
        for (var dy = 0; dy < n; dy++) {
          items.push([depth(ax + dx, ay + dy, az, turn) + 4,
            box(ax + dx, ay + dy, az, az + 1.6, turn, cls, "",
                "<title>" + esc(a.name || "") + " — " + a.hp + "/" + a.hp_max +
                (az ? " · " + az * 5 + " ft up" : "") + "</title>")]);
        }
      }
    });

    items.sort(function (p, q) { return p[0] - q[0]; });
    var body = items.map(function (i) { return i[1]; }).join("");

    // The viewBox is measured from the projected corners rather than guessed, so a map
    // of any size and any rotation fills the frame without clipping.
    var xs = [], ys = [];
    [[0, 0], [W, 0], [0, H], [W, H]].forEach(function (c) {
      [0, 4].forEach(function (z) {
        var p = project(c[0], c[1], z, turn); xs.push(p[0]); ys.push(p[1]);
      });
    });
    var pad = 12;
    var x0 = Math.min.apply(null, xs) - pad, y0 = Math.min.apply(null, ys) - pad;
    var w = Math.max.apply(null, xs) - x0 + pad, h = Math.max.apply(null, ys) - y0 + pad;
    return '<svg id="view3d" viewBox="' + x0.toFixed(1) + " " + y0.toFixed(1) + " " +
      w.toFixed(1) + " " + h.toFixed(1) + '" preserveAspectRatio="xMidYMid meet">' +
      body + "</svg>";
  }

  window.Scene3D = { render: render, TURNS: 4 };
})();
