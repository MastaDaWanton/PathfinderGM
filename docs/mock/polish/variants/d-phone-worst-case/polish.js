/* Variant d-phone-worst-case: what the board knows beyond the grid, worked out once per
 * draw and shared by both views, so flat and 3D cannot disagree.
 *
 * Everything here is READ from window.POLISH_SCENE (extras and light, the engine's own
 * answers) or derived from it by arithmetic. Nothing is decided here that the engine did
 * not decide: who provokes, who threatens, what is seen, who is caught by the cone.
 *
 * The one exception is PV.worst, the "worst case (made up)" scene at the foot of this
 * file. It is invented to break the design, says so on the board, and never mixes with
 * the real scene.
 */
const PV = (function () {
  "use strict";

  // --- the worst-case toggle ---------------------------------------------------------
  let worst = false;
  try { worst = new URLSearchParams(location.search).get("worst") === "1"; } catch (e) {}

  // --- small helpers -------------------------------------------------------------------
  const key = (c, r) => `${c},${r}`;
  // Pathfinder's 5-10-5 diagonal count, the same distance the engine's reach and hunch
  // use. A circle would be prettier and would be wrong at the corners.
  function feet(a, b) {
    const dx = Math.abs(a[0] - b[0]), dy = Math.abs(a[1] - b[1]);
    const d = Math.min(dx, dy), s = Math.max(dx, dy) - d;
    return 5 * (s + d + Math.floor(d / 2));
  }
  // A signed bonus with a real minus sign, never a hyphen or a dash.
  const signed = n => (n < 0 ? "−" + Math.abs(n) : "+" + n);
  // Initials by grapheme, not by UTF-16 unit: "Þórunn" is Þ, an emoji-first name does not
  // become half a surrogate. First and last word of the name before any comma, so
  // "second goblin" is SG and "third goblin" TG: three goblins, three different tokens.
  let seg = null;
  try { seg = new Intl.Segmenter(undefined, { granularity: "grapheme" }); } catch (e) {}
  const first = w => seg ? ([...seg.segment(w)][0] || { segment: "?" }).segment : ([...w][0] || "?");
  function initials(name) {
    const words = String(name || "?").split(",")[0].trim().split(/\s+/).filter(Boolean);
    if (!words.length) return "?";
    const out = words.length > 1 ? first(words[0]) + first(words[words.length - 1])
                                  : first(words[0]);
    return out.toLocaleUpperCase();
  }
  function list(names) {
    if (names.length < 2) return names.join("");
    return names.slice(0, -1).join(", ") + " and " + names[names.length - 1];
  }

  // --- the lamp --------------------------------------------------------------------------
  /* The room's one lamp, which the 3D board shades with and the dice share (dice3d.js is
     not in this harness; it would read window.ROOM_LAMP the same way). Strength comes
     from the light LEVEL the engine reports (Scene.ambient_light), colour from the PHASE
     of the day (sky.phase_at), and every colour is an existing token mixed toward white:
     --candle for the morning, --ember for dawn and dusk, --player for night. Nothing
     below .8 strength: the owner's rule is that the board stays readable at night, so the
     lamp shifts the mood and the tokens keep their colours. */
  const TOK = { candle: [0xf0, 0xc0, 0x70], ember: [255, 176, 84], player: [0x8f, 0xb0, 0xc8] };
  const PHASE = {
    dawn: ["ember", 0.30], morning: ["candle", 0.12], noon: [null, 0],
    afternoon: ["candle", 0.08], dusk: ["ember", 0.34], evening: ["ember", 0.22],
    night: ["player", 0.5],
  };
  const LEVEL = { bright: 1, normal: 1, dim: 0.86, dark: 0.8 };
  function lamp(light) {
    const ph = (light && light.phase && light.phase.phase) || "noon";
    const [tok, k] = PHASE[ph] || [null, 0];
    const strength = LEVEL[(light && light.ambient) || "bright"] || 1;
    const t = tok ? TOK[tok] : [255, 255, 255];
    // Normalised so the brightest channel of the tint is 1: a hue, not a dimmer.
    const mx = Math.max(...t);
    const rgb = t.map(v => strength * (1 - k + k * v / mx));
    const hex = "#" + rgb.map(v => Math.round(Math.min(1, v) * 255).toString(16).padStart(2, "0")).join("");
    // The flat board takes the same lamp as two layers: the hue (blend mode "color", which
    // keeps every square's lightness, so night turns the stones blue without darkening a
    // board that is already near black) and the strength (a grey multiply).
    const grey = Math.round(Math.min(1, strength) * 255).toString(16).padStart(2, "0");
    return { phase: ph, ambient: (light && light.ambient) || "bright", rgb, hex,
             hue: tok ? "#" + t.map(v => v.toString(16).padStart(2, "0")).join("") : null,
             hueAmount: +(k * 0.7).toFixed(3), dim: strength < 1 ? "#" + grey + grey + grey : null,
             plain: !tok && strength >= 1 };
  }

  // --- the facts for one draw ---------------------------------------------------------
  function facts(state, sc) {
    const s = state.scene, g = s.grid, ex = (sc && sc.extras) || {};
    const actors = (s.actors || []).filter(a => a.at);
    const byRef = new Map(actors.map(a => [a.ref, a]));
    const pc = actors.find(a => a.stance === "pc" || a.is_pc);

    const threat = new Map();          // "c,r" -> [refs]
    const tb = (ex.threatened && ex.threatened.by_foe) || {};
    for (const ref of Object.keys(tb))
      for (const [c, r] of tb[ref]) {
        const k = key(c, r);
        if (!threat.has(k)) threat.set(k, []);
        threat.get(k).push(ref);
      }
    const provokes = (ex.provokes && ex.provokes.squares) || {};

    const unseen = new Set(), dark = new Set();
    for (const [c, r, v] of ((ex.sight && ex.sight.squares) || []))
      if (!v) unseen.add(key(c, r));
    for (const [c, r, lv] of ((sc && sc.light && sc.light.at_square) || []))
      if (lv === "dark") dark.add(key(c, r));

    // Hunches: grouped by range. Each is a range from the PC and nothing else: no ref,
    // no square, which is all awareness.has_hunch tells the player.
    const hunchBy = new Map();
    for (const h of ((ex.awareness && ex.awareness.hunches) || []))
      hunchBy.set(h.within_ft, (hunchBy.get(h.within_ft) || 0) + 1);
    const hunches = [...hunchBy].sort((a, b) => a[0] - b[0])
      .map(([ft, n]) => ({ ft, n, edges: pc ? edgesOf(g, sq => feet(pc.at, sq) <= ft) : [] }));

    // The cone is shown only while the board is showing it (the harness's spell toggle
    // lays it into grid.areas, as a real cast does).
    const spellOn = (g.areas || []).some(a => a && (a.cells || []).length);
    const sa = ex.spell_area || {};
    const caught = new Set(spellOn ? (sa.caught || []) : []);
    const spell = spellOn ? String(sa.spell || (g.areas[0] && g.areas[0].spell) || "the spell").replace(/-/g, " ") : "";

    const reach = new Map((g.reachable || []).map(e => [key(e[0], e[1]), e]));
    const reachEdges = edgesOf(g, sq => reach.has(key(sq[0], sq[1])));

    // Who shares a square: a prone foe under a standing ally is legal in Pathfinder, and
    // two full tokens drawn on one square hide one of them completely.
    const stacks = new Map();
    for (const a of actors) {
      const k = a.at.join(",");
      if (!stacks.has(k)) stacks.set(k, []);
      stacks.get(k).push(a.ref);
    }

    // Token labels, unique on this board. Initials alone gave the worst case two "FG"
    // (fourth and fifth goblin) and two "G" (two creatures both called goblin): two
    // tokens nobody could tell apart. A clash becomes first letter and a count, G1 G2.
    const labels = new Map(), seen = new Map();
    for (const a of actors) {
      const l = a.members != null ? String(a.members) : initials(a.name);
      labels.set(a.ref, l);
      if (a.members == null) seen.set(l, (seen.get(l) || []).concat(a.ref));
    }
    for (const [l, refs] of seen) if (refs.length > 1)
      refs.forEach((r, i) => labels.set(r, first(l) + (i + 1)));

    return { s, g, ex, actors, byRef, pc, threat, labels, provokes, unseen, dark, hunches,
             spellOn, caught, spell, reach, reachEdges, stacks,
             turn: s.turn_ref, light: lamp(sc && sc.light) };
  }

  // The outline of a set of squares, as unit edges [x1,y1,x2,y2] in square units.
  function edgesOf(g, inside) {
    const out = [];
    for (let c = 0; c < g.width; c++) for (let r = 0; r < g.height; r++) {
      if (!inside([c, r])) continue;
      const ok = (x, y) => x >= 0 && y >= 0 && x < g.width && y < g.height && inside([x, y]);
      if (!ok(c, r - 1)) out.push([c, r, c + 1, r]);
      if (!ok(c, r + 1)) out.push([c, r + 1, c + 1, r + 1]);
      if (!ok(c - 1, r)) out.push([c, r, c, r + 1]);
      if (!ok(c + 1, r)) out.push([c + 1, r, c + 1, r + 1]);
    }
    return out;
  }

  // --- the readout ----------------------------------------------------------------------
  // One fixed-height strip under the board, the same for a tap and a pointer: a phone has
  // no hover, so nothing on this board is reachable only by hovering.
  // In running text a name stops at its first comma: the worst case's "Ünsal the
  // Twice-Drowned, Reeve of the Saltmarsh Ossuaries" made a five-name list four lines
  // long and a possessive that read "Ossuaries's turn". The full name stays in the
  // creature's own readout and on its token's label for assistive technology.
  const short = n => String(n).split(",")[0].trim();
  // Two creatures with one name are told apart by their token's label: "goblin (G1) and
  // goblin (G2)", not "goblin and goblin".
  const nameOf = (F, ref) => {
    const a = F.byRef.get(ref);
    if (!a) return "someone you cannot see";
    const n = short(a.name);
    const twin = F.actors.some(b => b !== a && short(b.name) === n);
    return twin ? `${n} (${F.labels.get(ref)})` : n;
  };
  const LIGHTWORD = { bright: "Bright light", normal: "Normal light", dim: "Dim light", dark: "Darkness" };

  function idle(F) {
    const turnA = F.turn && F.byRef.get(F.turn);
    const nm = turnA && short(turnA.name);
    const who = turnA ? (turnA === F.pc ? "Your turn" : `${nm}${/s$/i.test(nm) ? "'" : "'s"} turn`) : "";
    const lines = [];
    // Most important first. On a phone the box shows two lines; the first cut put the
    // square count and the light in the heading, which wrapped there and pushed the hunch
    // out of sight below the fold of the box.
    lines.push(`<p class="pv-h pv-one"><span>${esc(who || "The ground")}</span><span class="pv-dim">${
      esc(LIGHTWORD[F.light.ambient] || cap(F.light.ambient))}, ${esc(F.light.phase)}</span></p>`);
    if (F.spellOn) {
      const names = [...F.caught].map(r => nameOf(F, r));
      lines.push(`<p><span class="pv-spell">${esc(cap(F.spell))}</span> ${names.length
        ? `would catch ${esc(list(names))}.` : "would catch nobody you can see."}</p>`);
    }
    if (F.hunches.length) {
      // "2 foes within 30 ft and 1 within 60 ft", never "3 foes within 30 ft and within
      // 60 ft", which is what the first wording said of the worst case's three hunches.
      const parts = F.hunches.map((h, i) => `${i ? h.n : h.n === 1 ? "a foe" : h.n + " foes"} within ${h.ft} ft`);
      lines.push(`<p><span class="pv-hunch">You sense ${list(parts)}</span>, but not where.</p>`);
    }
    const body = lines.slice(1).map(l => l.replace(/^<p>|<\/p>$/g, "")).join(" ");
    const sq = F.g.speed && F.reach.size ? `${F.reach.size} squares within ${F.g.speed} ft. ` : "";
    return lines[0] + `<p>${body} <span class="pv-dim">${sq}Tap or point at a foe for your attack, or a lit square for the move.</span></p>`;
  }

  function forActor(F, a) {
    const out = [];
    const hp = `${a.hp}/${a.hp_max}`;
    const where = a.at.length > 2 && a.at[2] ? `, ${a.at[2] * 5} ft up` : "";
    const down = a.hp <= 0 ? ", down" : "";
    // Cover is something the player can see (the wall is on the board); its number goes
    // to the hidden AC and is never shown.
    const cover = F.ex.sight && F.ex.sight.cover && F.ex.sight.cover[a.ref];
    const cv = cover && cover !== "none"
      ? `, ${cover === "total" ? "total cover" : cover === "soft" ? "soft cover" : "behind cover"}` : "";
    // One line: the name gives way (ellipsis, whole on the token's own label), the
    // numbers never do. A two-line name on a phone filled the whole readout and left
    // the attack bonus, the thing the player tapped for, below its fold.
    out.push(`<p class="pv-h pv-one pv-who"><span class="pv-name" title="${esc(a.name)}">${esc(a.name)}${nameOf(F, a.ref).endsWith(")") ? ` (${esc(F.labels.get(a.ref))})` : ""}</span><span class="pv-dim">${hp}${where}${down}${cv}</span>${
      F.caught.has(a.ref) ? `<span class="pv-spell">in the ${esc(F.spell)} area</span>` : ""}</p>`);
    const pv = (F.ex.attack_preview && F.ex.attack_preview.by_foe || {})[a.ref];
    if (pv && pv.length) {
      // Weapons that come to the same bonus by the same terms are one line ("Rapier or
      // dagger +5"): the readout has two lines on a phone, and a repeat spends one.
      const groups = new Map();
      for (const w of pv) {
        const k = JSON.stringify([w.bonus, w.terms, w.in_reach]);
        if (!groups.has(k)) groups.set(k, { w, names: [] });
        groups.get(k).names.push(w.name || w.weapon);
      }
      for (const { w, names } of groups.values()) {
        const terms = (w.terms || []).map(([t, v]) => {
          const sit = (w.situational || []).some(([u]) => u === t);
          return `<span class="pv-term${sit ? " sit" : ""}">${esc(cap(t))}&nbsp;${signed(v)}</span>`;
        }).join(" ");
        // The total first, then what it is with, then why: the number is what a player
        // compares, and a long weapon name pushed it to the end of a wrapped line.
        out.push(`<p class="pv-atk"><b class="pv-bonus">${signed(w.bonus)}</b> <span class="pv-wpn">${
          esc(cap(names.join(" or ")))}</span>${w.in_reach ? "" : ` <span class="pv-warn">out of reach</span>`} ${terms}</p>`);
      }
    }
    const shared = (F.stacks.get(a.at.join(",")) || []).filter(r => r !== a.ref);
    if (shared.length) out.push(`<p class="pv-dim">Sharing the square with ${esc(list(shared.map(r => nameOf(F, r))))}.</p>`);
    return out.join("");
  }

  function forSquare(F, sq) {
    const k = key(sq[0], sq[1]);
    const e = F.reach.get(k);
    const out = [`<p class="pv-h">${e ? `${e[2]} ft to here` : "Out of your move"}${
      e && e[3] ? `<span class="pv-dim">${e[3] * 5} ft up</span>` : ""}</p>`];
    if (F.unseen.has(k)) out.push(`<p class="pv-dim">You cannot see this square.</p>`);
    else if (F.dark.has(k)) out.push(`<p class="pv-dim">Too dark to see much there.</p>`);
    const pr = F.provokes[k];
    if (e) out.push(pr && pr.length
      ? `<p><span class="pv-warn">Provokes</span> an attack from ${esc(list(pr.map(r => nameOf(F, r))))}.</p>`
      : `<p>No attack of opportunity.</p>`);
    const th = F.threat.get(k);
    if (th && th.length) out.push(`<p class="pv-dim">Threatened there by ${esc(list(th.map(r => nameOf(F, r))))}.</p>`);
    return out.join("");
  }

  const cap = t => String(t).charAt(0).toUpperCase() + String(t).slice(1);

  return { feet, signed, initials, facts, edges: edgesOf, idle, forActor, forSquare, key,
           get worst() { return worst; }, set worst(v) { worst = !!v; },
           worstScene: () => WORST() };

  // --- the worst case (made up) ------------------------------------------------------------
  /* Invented, every word of it, to break the design: the realistic worst a World Bible
     world and a long fight can send, shaped exactly like data.js. Long and diacritic names
     (World Bible worlds name their peoples freely), a one-letter-ish name, a Large and a
     Huge body, a crowd unit, two people sharing a square, the downed, an archer two floors
     up, a fog-heavy board with smoke, three hunches at two ranges, night with dark
     squares, a foe's turn rather than the PC's, a seven-term attack with penalties, and a
     cone that catches five. Never shown without the "worst case (made up)" label. */
  function WORST() {
    const W = 20, H = 14;
    const A = (ref, name, stance, at, extra) => Object.assign({ ref, name, stance, at,
      hp: 7, hp_max: 12, squares: 1, is_pc: stance === "pc", conditions: [] }, extra || {});
    const actors = [
      A("pc", "Aleksandra Wiśniewska-Kowalczyk", "pc", [8, 7], { hp: 3, hp_max: 31 }),
      A("a1", "Bartholomew Fitzgerald-Ó Súilleabháin, sworn sword of the Seventh Lantern Gate", "ally", [9, 7]),
      A("a2", "Jo", "ally", [7, 8], { hp: 0, hp_max: 9 }),
      A("f1", "goblin", "foe", [8, 6]),
      A("f2", "second goblin", "foe", [9, 6]),
      A("f3", "third goblin", "foe", [7, 6]),
      A("f4", "fourth goblin", "foe", [7, 7]),
      A("f5", "Ünsal the Twice-Drowned, Reeve of the Saltmarsh Ossuaries", "foe", [9, 8]),
      A("f6", "Þórunn Æðelflǣd", "foe", [8, 8]),
      A("f7", "fifth goblin", "foe", [7, 8], { hp: -4, hp_max: 6 }),
      A("f8", "hill giant", "foe", [11, 6], { squares: 2, size: "large", hp: 84, hp_max: 85 }),
      A("f9", "ancient bronze guardian of the drowned counting-house", "foe", [3, 2], { squares: 3, size: "huge", hp: 160, hp_max: 160 }),
      A("f10", "crossbowman on the gallery", "foe", [16, 3, 3]),
      A("f11", "second crossbowman on the gallery", "foe", [17, 3, 3]),
      A("f12", "goblin", "foe", [13, 10], { hp: 0, hp_max: 6 }),
      A("u1", "the frightened townsfolk of Lower Brackwater", "bystander", [2, 9],
        { squares: 3, members: 37, members_max: 40, hp: 110, hp_max: 120 }),
      A("b1", "a pedlar", "bystander", [12, 12]),
      A("b2", "Mm", "bystander", [0, 0]),
      A("f13", "rat", "foe", [19, 13], { size: "tiny" }),
      A("f14", "rat", "foe", [18, 13], { size: "tiny" }),
    ];
    const blocked = [[5, 4], [5, 5], [6, 10], [6, 11], [14, 0], [14, 1], [14, 2], [14, 5], [14, 6]];
    const floor = [];
    for (let c = 15; c < 20; c++) for (let r = 0; r < 7; r++) floor.push([c, r, 3]);
    const parapet = []; for (let r = 0; r < 7; r++) parapet.push([14, r, 3]);
    const obscuring = [[10, 2], [11, 2], [10, 3], [11, 3], [12, 3]];
    const difficult = [[4, 10], [5, 10], [4, 11], [12, 8], [13, 8]];
    const solid = new Set(blocked.map(p => p.join(",")));
    const occ = new Set();
    actors.forEach(a => { const n = a.squares || 1;
      for (let dx = 0; dx < n; dx++) for (let dy = 0; dy < n; dy++) occ.add((a.at[0] + dx) + "," + (a.at[1] + dy)); });
    const pc = actors[0];
    const reachable = [];
    for (let c = 0; c < W; c++) for (let r = 0; r < H; r++) {
      const k = c + "," + r, ft = feet(pc.at, [c, r]);
      if (ft && ft <= 30 && !solid.has(k) && !occ.has(k) && c < 14) reachable.push([c, r, ft, 0]);
    }
    const foes = actors.filter(a => a.stance === "foe" && a.hp > 0);
    const by_foe = {};
    for (const f of foes) {
      const n = f.squares || 1, sq = [], rch = n > 1 ? 2 : 1;
      for (let c = f.at[0] - rch; c < f.at[0] + n + rch; c++)
        for (let r = f.at[1] - rch; r < f.at[1] + n + rch; r++)
          if (c >= 0 && r >= 0 && c < W && r < H && !(c >= f.at[0] && c < f.at[0] + n && r >= f.at[1] && r < f.at[1] + n))
            sq.push([c, r]);
      by_foe[f.ref] = sq;
    }
    const adj = foes.filter(f => feet(f.at, pc.at) <= 5 || (f.squares > 1 && feet(f.at, pc.at) <= 15)).map(f => f.ref);
    const provokes = {};
    for (const [c, r, ft] of reachable) if (ft > 5) provokes[c + "," + r] = adj;
    // Fog: everything east of the smoke and most of the south is out of sight.
    const squares = [];
    for (let r = 0; r < H; r++) for (let c = 0; c < W; c++)
      squares.push([c, r, (c > 11 || r > 10 || (c < 3 && r < 5)) ? 0 : 1]);
    const at_square = [];
    for (let r = 0; r < H; r++) for (let c = 0; c < W; c++)
      at_square.push([c, r, (c > 15 || r > 11) ? "dark" : "dim"]);
    const terms = [["Dex (Finesse)", 4], ["base attack", 2], ["flanking with Bartholomew Fitzgerald-Ó Súilleabháin", 2],
      ["shaken", -2], ["Power Attack", -1], ["bless", 1], ["into melee", -4]];
    const atk = ref => [
      { weapon: "rapier", name: "masterwork cold iron rapier of the Saltmarsh wardens", category: "melee",
        in_reach: feet(by(ref).at, pc.at) <= 5, bonus: -1, terms, situational: [terms[2], terms[6]] },
      { weapon: "shortbow", name: "shortbow", category: "ranged", in_reach: true, bonus: 3,
        terms: [["Dex", 4], ["range 40 ft", -2], ["higher ground", 1]], situational: [["range 40 ft", -2], ["higher ground", 1]] },
    ];
    const by = r => actors.find(a => a.ref === r);
    const cone = [[8, 9], [7, 9], [8, 10], [9, 9], [9, 10], [7, 10], [6, 9], [10, 10], [8, 11], [10, 9], [9, 11], [7, 11]];
    const state = { scene: {
      in_encounter: true, round: 14, turn_ref: "f5",
      actors: actors.map(a => Object.assign({}, a)),
      pools: [{ at: [8, 6], owner: "f1" }, { at: [7, 8], owner: "a2" }, { at: [13, 10], owner: "f12" }],
      grid: { width: W, height: H, difficult, blocked, obscuring, floor, parapet, ceiling: 5,
        levels: [0, 3], reachable,
        place: "the collapsed counting-house of the Brotherhood of Salt and Lantern-Oil, east wing",
        about: "a counting-house fallen in on its own ledgers, a gallery along the east wall and a smoke of burning paper",
        speed: 30, areas: [] },
    } };
    const extras = {
      threatened: { by_foe },
      provokes: { squares: provokes },
      sight: { squares, cover: { f10: "cover", f11: "total", f9: "soft" } },
      attack_preview: { by_foe: Object.fromEntries(foes.map(f => [f.ref, atk(f.ref)])) },
      spell_area: { spell: "burning-hands", cells: cone.map(c => [c[0], c[1], 0]),
        caught: ["f5", "f6", "a2", "f7", "pc"].filter(r => by(r)),
        as_grid_area: { spell: "burning-hands", cells: cone.map(c => [c[0], c[1], 0]) } },
      awareness: { hunches: [{ within_ft: 30 }, { within_ft: 30 }, { within_ft: 60 }] },
    };
    const light = { ambient: "dark", phase: { phase: "night" }, at_square };
    return { label: "Worst case (made up)", state, extras, light };
  }
})();
