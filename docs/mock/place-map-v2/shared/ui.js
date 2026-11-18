// Place map v2 mocks: the controller every style shares. It keeps the state (where you
// stand, what you have been, which map is open, what is pressed, the hour, the rain),
// writes the slip and the breadcrumb, and hands each style's `Renderer` a plain view to
// draw. A style only draws and animates; every rule lives here or in model.js, so the
// three styles cannot disagree about what is known.
//
// The interactions are the current map's (16-tab-map.js): press a place for its way
// there, leg by leg with the engine's minutes; Walk there walks it in one go; the fog is
// one way beyond every place stood in. New here: the breadcrumb between three maps, a
// floor as a badge, a ↓ into a site, roads as arrows to the region.
const MapUI = (() => {
  const M = MapModel, e = s => String(s == null ? "" : s).replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let D, R, T, L, SITES, st, els, FIVE = false;

  async function start(renderer, { styleName }) {
    R = renderer;
    D = await M.load();
    // The worst case (made up) swaps the data where it is loaded, the one door the real data
    // uses; the drawing is never touched. It lives in the URL, so a reload keeps it.
    const worst = new URLSearchParams(location.search).get("worst") === "1";
    if (worst) D = M.worstCase(D);
    T = D.town; L = M.townLayout(T); SITES = M.sites(D);
    if (!worst) M.selfCheck(T);   // the made-up town has no chart() to agree with
    const visitedTowns = new Set(D.region.towns.filter(t => t.visited).map(t => t.id));
    st = { level: "town", here: T.here, been: new Set(T.been), sel: null, said: "", fresh: new Set(),
           regionHere: D.region.here, visitedTowns, site: "sewers", minutes: T.clock_minutes || 0,
           rain: false, walking: false, worst, maps: worst ? D.world.worstMaps : [] };
    if (!st.been.has(st.here)) st.been.add(st.here);
    // Five maps for a renderer that draws them (the tabletop): World > Continent > Region (the
    // nation you stand in) > Town (inside the walls) > Site. The owner, 2026-11-18: "anything
    // outside of the city should not be included in the city map but instead in the region map".
    FIVE = (R.levels || []).includes("continent");
    const home = D.world.cities.find(c => c.id === D.region.here) || {};
    st.continent = home.continent; st.nation = home.nation;
    document.body.innerHTML = `<div class="app"><header class="bar">
        <ol class="crumbs" aria-label="Maps"></ol>
        <span class="style-name">${e(styleName)} · <a href="index.html">all mocks</a></span>
        <label class="hour">Hour <input type="range" min="0" max="1439" step="10" aria-label="Hour of the day">
          <output></output></label>
        <button type="button" class="toggle" id="rain" aria-pressed="false">Rain</button>
        <button type="button" class="toggle worst-toggle" id="worst" aria-pressed="${worst}">Worst case (made up)</button>
      </header><div class="main"><div class="stage${worst ? " is-worst" : ""}" id="stage"></div><aside class="rail" aria-live="polite"></aside></div></div>`;
    els = { crumbs: document.querySelector(".crumbs"), rail: document.querySelector(".rail"),
            stage: document.getElementById("stage"), hour: document.querySelector(".hour input"),
            out: document.querySelector(".hour output"), rain: document.getElementById("rain") };
    els.hour.value = st.minutes % 1440;
    els.hour.addEventListener("input", () => { st.minutes = Math.floor(st.minutes / 1440) * 1440 + +els.hour.value; paint(); });
    els.rain.addEventListener("click", () => { st.rain = !st.rain; paint(); });
    document.getElementById("worst").addEventListener("click", () => {
      const u = new URL(location.href); if (st.worst) u.searchParams.delete("worst"); else u.searchParams.set("worst", "1"); location.href = u; });
    els.crumbs.addEventListener("click", ev => { const b = ev.target.closest("[data-level]"); if (b) open(b.dataset.level, b.dataset.site || b.dataset.arg); });
    els.rail.addEventListener("click", onRail);
    document.addEventListener("keydown", ev => { if (ev.key === "Escape" && st.sel) { st.sel = null; paint(); } });
    R.init(els.stage, { pick, open, reduced: () => reduced.matches, level: () => st.level });
    if (worst) els.stage.insertAdjacentHTML("beforeend", `<p class="worst-flag">Worst case (made up): invented places, names and maps, not a real save</p>`);
    const q = new URLSearchParams(location.search);
    if (q.get("hour")) { st.minutes = Math.floor(st.minutes / 1440) * 1440 + Math.round(+q.get("hour") * 60); els.hour.value = st.minutes % 1440; }
    if (q.get("rain")) st.rain = true;
    if (q.get("level")) open(q.get("level"), q.get("site") || q.get("arg") || "sewers"); else paint();
    if (q.get("sel")) pick(q.get("sel"));
    window.MAP_STATE = st;  // for the screenshots and the frame-rate probe
  }

  // --- What each map is showing ----------------------------------------------------------
  function view() {
    const base = { level: st.level, sel: st.sel, hour: (st.minutes % 1440) / 60, rain: st.rain,
                   light: M.light((st.minutes % 1440) / 60), reduced: reduced.matches };
    if (st.level === "town") {
      const F = M.fog(T, [...st.been], st.here);
      const r = st.sel && st.sel !== st.here && F.found.has(st.sel) ? M.route(T.ways, F.visited, st.here, st.sel) : null;
      return { ...base, T, L, F, here: st.here, fresh: st.fresh,
               route: r && r.legs.length ? [st.here, ...r.legs.map(l => l.to)] : null };
    }
    if (st.level === "world") {
      const been = new Set([...D.world.been, ...st.visitedTowns]);
      const WL = M.worldLayout(D.world), K = M.worldKnown(D.world, [...been], st.maps);
      const legs = st.sel && st.sel !== st.regionHere && K.how[st.sel] ? M.worldRoute(D.world, K, st.regionHere, st.sel) : null;
      return { ...base, W: D.world, WL, K, here: st.regionHere, route: legs && legs.length ? [st.regionHere, ...legs.map(l => l.to)] : null, legs };
    }
    if (st.level === "continent" || st.level === "nation") {
      const been = new Set([...D.world.been, ...st.visitedTowns]);
      const WL = M.worldLayout(D.world), K = M.worldKnown(D.world, [...been], st.maps), F = M.fog(T, [...st.been], st.here);
      const city = D.world.cities.find(c => c.id === st.sel);
      let route = null, legs = null, walkLegs = null;
      if (city && K.how[st.sel] && st.sel !== st.regionHere) {
        legs = M.worldRoute(D.world, K, st.regionHere, st.sel);
        route = legs && legs.length ? [st.regionHere, ...legs.map(l => l.to)] : null;
      } else if (st.sel && T.settings[st.sel] === "outside" && F.found.has(st.sel) && st.sel !== st.here) {
        walkLegs = M.route(T.ways, F.visited, st.here, st.sel);
        route = walkLegs.legs.length ? [st.here, ...walkLegs.legs.map(l => l.to)] : null;
      }
      return { ...base, W: D.world, WL, K, T, L, F, continent: st.continent, nation: st.nation, here: st.regionHere,
               at: st.here, home: D.region.here, route, legs, walkLegs };
    }
    if (st.level === "region") {
      const G = M.regionLayout(D.region, T, st.visitedTowns);
      const F = M.fog(T, [...st.been], st.here);
      return { ...base, R: D.region, W: D.world, G, here: st.regionHere, visited: st.visitedTowns,
               wildFound: F.found, wildVisited: F.visited,
               route: st.sel && G.pos[st.sel] && st.sel !== st.regionHere ? [st.regionHere, st.sel] : null };
    }
    // Underground the hour does not reach: no tint, no night.
    base.light = { r: 255, g: 240, b: 220, a: 0, night: false, dark: 0 };
    const s = SITES[st.site], S = M.siteLayout(s.rooms);
    const here = s.here || [...s.been].pop() || S.root;
    const path = st.sel && st.sel !== here ? M.siteRoute(S, s.been, here, st.sel) : null;
    return { ...base, site: s, S, here, been: s.been, route: path };
  }

  function paint() {
    els.out.textContent = M.clockWords(st.minutes % 1440);
    els.rain.setAttribute("aria-pressed", st.rain);
    const s = SITES[st.site];
    const crumbs = FIVE
      ? [["world", "World", true], ["continent", D.world.continents[st.continent] || "Continent", true],
         // A nation on another continent than the one open is not this map's region: the crumb waits.
         ["nation", (D.world.nations[st.nation] || {}).continent === st.continent ? D.world.nations[st.nation].name : "Region",
          (D.world.nations[st.nation] || {}).continent === st.continent], ["town", "Featherperch", true],
         ["site", s ? M.upper(s.name) : "Site", st.level === "site"]]
      : [...((R.levels || []).includes("world") ? [["world", "World", true]] : []), ["region", "Region", true], ["town", "Featherperch", true],
         ["site", s ? M.upper(s.name) : "Site", st.level === "site"]];
    els.crumbs.innerHTML = crumbs.map(([lv, name, on]) => `<li><button type="button" data-level="${lv}"${
      lv === "site" ? ` data-site="${st.site}"` : ""}${st.level === lv ? ' aria-current="page"' : ""}${on ? "" : " disabled"}>${e(name)}</button></li>`).join("");
    const v = view();
    els.rail.innerHTML = slip(v);
    els.rail.querySelectorAll("h3").forEach(h => { h.title = h.textContent.trim(); });  // the clamped heading's whole name
    R.draw(v);
    st.fresh = new Set();
  }

  function open(level, arg) {
    if (st.walking) return;
    if (FIVE && level === "region") level = "nation";   // the old region board is the continent now; "region" means your nation
    st.level = level; st.sel = null; st.said = "";
    if (level === "site" && arg && SITES[arg]) st.site = arg;
    if (level === "continent" && arg && D.world.continents[arg]) st.continent = arg;
    if (level === "nation" && arg && D.world.nations[arg]) { st.nation = arg; st.continent = D.world.nations[arg].continent; }
    paint();
  }
  function pick(id) {
    if (st.walking) return;
    st.sel = id === st.sel ? null : id; st.said = ""; paint();
  }

  // --- Walking ----------------------------------------------------------------------------
  function walk() {
    const v = view();
    if (!v.route || st.walking) return;
    st.walking = true;
    if (v.level === "town") {
      const r = M.route(T.ways, v.F.visited, st.here, st.sel), before = v.F.found;
      R.walk(v.route, () => {
        st.walking = false; st.here = st.sel; st.been.add(st.sel); st.minutes += r.minutes;
        const after = M.fog(T, [...st.been], st.here).found;
        st.fresh = new Set([...after].filter(x => !before.has(x)));
        st.said = `You walk to ${T.names[st.here]}, ${r.minutes} minutes by the way you know.${
          st.fresh.size ? ` New on the map: ${[...st.fresh].map(x => M.bare(T.names[x])).join(", ")}.` : ""}`;
        st.sel = null; els.hour.value = st.minutes % 1440; paint();
      });
    } else if (v.level === "continent" || v.level === "nation") {
      const to = st.sel;
      if (v.legs) {
        // A journey: the miles of the roads you know, at Pathfinder's 24 miles a day on foot (speed 30).
        const miles = v.legs.reduce((a, l) => a + (l.miles || 0), 0), days = Math.max(1, Math.ceil(miles / 24));
        R.walk(v.route, () => {
          const c = D.world.cities.find(x => x.id === to);
          st.walking = false; st.minutes += days * 1440; st.regionHere = to; st.visitedTowns.add(to); st.nation = c.nation; st.continent = c.continent;
          st.said = `You set out for ${c.name} and arrive after about ${days} ${days === 1 ? "day" : "days"} on the road${miles ? ` (${miles} miles at 24 a day)` : ""}. Journey events, another lane's work, would happen on the way.`;
          st.sel = null; els.hour.value = st.minutes % 1440; paint();
        });
      } else {
        const r = v.walkLegs;
        R.walk(v.route, () => {
          st.walking = false; st.minutes += r.minutes; st.here = to; st.been.add(to); st.regionHere = D.region.here;
          st.said = `You walk out to ${T.names[to]}, ${r.minutes} minutes.`; st.sel = null; els.hour.value = st.minutes % 1440; paint();
        });
      }
    } else if (v.level === "region") {
      const to = st.sel, G = v.G, town = G.towns[to];
      R.walk(v.route, () => {
        st.walking = false;
        if (town) {
          const road = G.roads.find(r => (r.a === st.regionHere && r.b === to) || (r.b === st.regionHere && r.a === to));
          st.minutes += (road ? road.days : 1) * 1440;
          st.regionHere = to; st.visitedTowns.add(to);
          st.said = `You set out for ${town.name} and arrive after ${road ? road.days : "some"} days on the road. (Journey events, another lane's work, would happen on the way.)`;
        } else {
          const r = M.route(T.ways, M.fog(T, [...st.been], st.here).visited, st.here, to);
          st.minutes += r.minutes; st.here = to; st.been.add(to); st.regionHere = D.region.here;
          st.said = `You walk out to ${T.names[to]}, ${r.minutes} minutes.`;
        }
        st.sel = null; els.hour.value = st.minutes % 1440; paint();
      });
    } else {
      const s = SITES[st.site], to = st.sel;
      R.walk(v.route, () => {
        st.walking = false; s.here = to; s.been.add(to);
        st.said = `You go through to ${s.rooms.find(r => r.id === to).name}.`;
        st.sel = null; paint();
      });
    }
  }

  function onRail(ev) {
    const b = ev.target.closest("button");
    if (!b) return;
    if (b.dataset.walk !== undefined) walk();
    else if (b.dataset.open) open(b.dataset.open, b.dataset.site || b.dataset.arg);
    else if (b.dataset.pick) pick(b.dataset.pick);
    else if (b.dataset.readmap) {
      const n = b.dataset.readmap;
      // One way: what a map taught stays known, as `been` only grows (the fog rule refuses
      // forgetting; NetHack took map amnesia out because players just wrote the map down).
      if (!st.maps.includes(n)) st.maps = st.maps.concat(n);
      st.said = `You buy a map of ${D.world.nations[n].name} at the general store for 5 gp and study it: its towns and roads go onto yours.`; paint();
    }
    else if (b.dataset.replay) {
      const s = SITES[st.site], S = M.siteLayout(s.rooms);
      s.been = new Set([S.root]); s.here = S.root; st.sel = null; st.said = "Replaying from the way in: rooms beyond what you have seen are blank."; paint();
    }
  }

  // --- The slip ---------------------------------------------------------------------------
  const MW = w => String(w || "").replace(/(?:'s|') walk$/, "");
  function slip(v) {
    let out = st.said ? `<div class="mapnote said"><p>${e(st.said)}</p></div>` : "";
    if (v.level === "town") out += townSlip(v);
    else if (v.level === "region") out += regionSlip(v);
    else if (v.level === "world") out += worldSlip(v);
    else if (v.level === "continent") out += continentSlip(v);
    else if (v.level === "nation") out += nationSlip(v);
    else out += siteSlip(v);
    return out;
  }
  // The world: what you know of each city, and how you came to know it.
  function worldSlip(v) {
    const { W, K } = v, city = id => W.cities.find(c => c.id === id), nm = id => (city(id) || {}).name || id;
    const how = h => h.by === "been" ? "You have stood here."
      : h.by === "road" ? `A road out of ${e(nm(h.from))} is signed for it.`
      : h.by === "heard" ? `Heard of in talk: “${e(h.line)}”`
      : `On the map of ${e(W.nations[h.nation].name)} you bought.`;
    let out = "";
    if (st.sel && K.how[st.sel] && st.sel !== st.regionHere) {
      const c = city(st.sel), n = W.nations[c.nation] || {};
      out += `<div class="mapnote picked"><h3>${e(c.name)}${K.how[st.sel].by === "been" ? "" : " <small>not yet visited</small>"}</h3>
        <p>${how(K.how[st.sel])}</p><p>${e(n.name || "")}, ${e(W.continents[c.continent] || "")}.</p>${
        v.legs ? `<ol class="route">${v.legs.map(l => `<li>${e(nm(l.to))}<span>${l.by === "sea" ? "by sea" : (l.miles ? l.miles + " miles" : "") + (l.by === "river" ? " by river" : "")}</span></li>`).join("")}</ol>
          <p>${v.legs.length} ${v.legs.length === 1 ? "journey" : "journeys"} by the roads you know.</p>`
        : `<p class="shutwhy">No road you know goes there.</p>`}</div>`;
    }
    const counts = { been: 0, road: 0, heard: 0, map: 0 };
    Object.values(K.how).forEach(h => counts[h.by]++);
    const here = city(st.regionHere), nation = here && here.nation;
    out += `<div class="mapnote"><h3>${e(nm(st.regionHere))} <small>you are here</small></h3>
      <p>${Object.keys(K.how).length} cities known: ${counts.been} stood in, ${counts.road} from road signs, ${counts.heard} heard of, ${counts.map} from maps.</p>
      <p>${FIVE ? "Point at a continent to light it; press it, or zoom in on it, to go in." : "Zoom out past the region to come here; press a town for the way there."}</p>
      <div class="btnrow"><button type="button" class="go quiet" data-open="${FIVE ? "continent" : "region"}"${FIVE ? ` data-arg="${e(here && here.continent)}"` : ""}>${FIVE ? e(W.continents[here && here.continent] || "Continent") : "Region map"}</button>${nation ? `
      <button type="button" class="go quiet" data-readmap="${e(nation)}" ${st.maps.includes(nation) ? " disabled" : ""}>${st.maps.includes(nation) ? `You have the map of ${e(W.nations[nation].name)}` : `Buy a map of ${e(W.nations[nation].name)}, 5 gp`}</button>` : ""}</div>
      <p class="proposed">Ruling 2026-11-18: general stores sell maps for about 5 gp, one map to a nation, showing its towns and roads; a store sells only its own nation's map. Not in the game yet.</p></div>`;
    out += placeList(Object.keys(K.how).sort((a, b) => nm(a).localeCompare(nm(b))), nm, id => K.how[id].by !== "been");
    return out;
  }
  // What you know of a city, and the way there by the roads you know (continent and region).
  function citySlip(v) {
    const { W, K } = v, c = W.cities.find(x => x.id === st.sel), h = K.how[st.sel], nm = id => (W.cities.find(x => x.id === id) || {}).name || id;
    const how = h.by === "been" ? "You have stood here." : h.by === "road" ? `A road out of ${e(nm(h.from))} is signed for it.`
      : h.by === "heard" ? `Heard of in talk: “${e(h.line)}”` : `On the map of ${e(W.nations[h.nation].name)} you bought.`;
    const miles = v.legs ? v.legs.reduce((a, l) => a + (l.miles || 0), 0) : 0;
    return `<div class="mapnote picked"><h3>${e(c.name)}${h.by === "been" ? "" : " <small>not yet visited</small>"}</h3><p>${how}</p>
      <p>${e(W.nations[c.nation].name)}, ${e(W.continents[c.continent])}.</p>${
      v.legs ? `<ol class="route">${v.legs.map(l => `<li><b class="leg">${e(nm(l.to))}</b><span>${l.by === "sea" ? "by sea" : (l.miles ? l.miles + " miles" : "") + (l.by === "river" ? " by river" : "")}</span></li>`).join("")}</ol>
        <p>About ${Math.max(1, Math.ceil(miles / 24))} days on foot${miles ? `, ${miles} miles` : ""}.</p>`
      : st.sel === st.regionHere ? "" : `<p class="shutwhy">No road you know goes there.</p>`}
      <div class="btnrow">${v.legs ? `<button type="button" class="go" data-walk>Set out</button>` : ""}${
        v.level === "continent" ? `<button type="button" class="go quiet" data-open="nation" data-arg="${e(c.nation)}">Open ${e(W.nations[c.nation].name)}</button>` : ""}${
        st.sel === v.home ? `<button type="button" class="go quiet" data-open="town">Open the town map</button>` : ""}</div></div>`;
  }
  function continentSlip(v) {
    const { W, K } = v, mine = id => (W.cities.find(c => c.id === id) || {}).continent === v.continent;
    let out = st.sel && K.how[st.sel] ? citySlip(v) : "";
    const known = Object.keys(K.how).filter(mine);
    const nations = [...new Set(known.map(id => W.cities.find(c => c.id === id).nation))].sort((a, b) => W.nations[a].name.localeCompare(W.nations[b].name));
    const here = W.cities.find(c => c.id === st.regionHere);
    out += `<div class="mapnote"><h3>${e(W.continents[v.continent])}</h3>
      <p>${here && here.continent === v.continent ? `You are in ${e(here.name)}, ${e(W.nations[here.nation].name)}. ` : ""}${known.length} ${known.length === 1 ? "city" : "cities"} known here. Point at a nation to light it; press it, or zoom in on it, to open its region.</p>
      <div class="btnrow">${nations.map(n => `<button type="button" class="go quiet" data-open="nation" data-arg="${e(n)}">${e(W.nations[n].name)}</button>`).join("")}</div></div>`;
    // Sea passages: the world's own, and the ones the engine works out for a port (journey.legs_from).
    const seaFrom = p => [...new Set([...W.routes, ...D.region.roads].filter(r => r.by === "sea" && (r.a === p || r.b === p))   /* by: the route's stated way; `sea` is also set on river legs */.map(r => r.a === p ? r.b : r.a))];
    const ports = [...st.visitedTowns].filter(mine).map(p => [p, seaFrom(p)]).filter(x => x[1].length);
    ports.forEach(([p, to]) => { out += `<div class="mapnote"><h3>By sea from ${e(W.cities.find(c => c.id === p).name)}</h3><p>${to.map(t => e((W.cities.find(c => c.id === t) || {}).name)).sort().join(", ")}.</p></div>`; });
    out += placeList(known.sort((a, b) => W.cities.find(c => c.id === a).name.localeCompare(W.cities.find(c => c.id === b).name)),
                     id => W.cities.find(c => c.id === id).name, id => K.how[id].by !== "been");
    return out;
  }
  function nationSlip(v) {
    const { W, K, F } = v, N = W.nations[v.nation], inN = id => (W.cities.find(c => c.id === id) || {}).nation === v.nation;
    let out = "";
    if (st.sel && K.how[st.sel]) out += citySlip(v);
    else if (st.sel && T.settings[st.sel] === "outside" && F.found.has(st.sel) && st.sel !== st.here) {
      const r = v.walkLegs, site = siteFor(st.sel);
      out += `<div class="mapnote picked"><h3>${e(M.upper(T.names[st.sel]))}${F.visited.has(st.sel) ? "" : " <small>not yet visited</small>"}</h3>${
        r.legs.length ? `${legsHtml(r.legs)}<p>About ${r.minutes} minutes on foot.</p>` : `<p class="shutwhy">${e(r.why)}</p>`}
        <div class="btnrow">${r.legs.length ? `<button type="button" class="go" data-walk>Walk there</button>` : ""}${
        site ? `<button type="button" class="go quiet" data-open="site" data-site="${site}">Go down ↓</button>` : ""}</div></div>`;
    }
    const outside = T.settings[st.here] === "outside";
    const homeHere = (W.cities.find(c => c.id === v.home) || {}).nation === v.nation;
    out += `<div class="mapnote"><h3>${e(N.name)}</h3>
      <p>${homeHere ? (outside ? `You are at ${e(T.names[st.here])}, outside Featherperch's walls. ` : "You are in Featherperch. ") : ""}Each hex is about 12 miles across, some four hours on foot (Pathfinder's overland hex). Roads leaving ${e(N.name)} end in an arrow with where they go.</p>
      <div class="btnrow">${homeHere ? `<button type="button" class="go quiet" data-open="town">Featherperch</button>` : ""}<button type="button" class="go quiet" data-open="continent" data-arg="${e(N.continent)}">${e(W.continents[N.continent])}</button></div></div>`;
    const towns = Object.keys(K.how).filter(inN), wild = homeHere ? [...F.found].filter(i => T.settings[i] === "outside" && !/@the-road-to-/.test(i)) : [];
    out += placeList([...towns, ...wild], id => K.how[id] ? W.cities.find(c => c.id === id).name : T.names[id], id => K.how[id] ? K.how[id].by !== "been" : !F.visited.has(id));
    return out;
  }
  function legsHtml(legs) {
    return `<ol class="route">${legs.map(x => `<li><b class="leg" title="${e(M.upper(x.name))}">${e(M.upper(x.name))}</b><span>${e(MW(x.time_words))}</span></li>`).join("")}</ol>`;
  }
  function floorsBadge(id) {
    const f = (L.floors[M.baseOf(id)] || []).map(M.floorOf);
    if (!f.length) return "";
    const up = f.filter(n => n > 0).length, down = f.filter(n => n < 0).length;
    return `<div class="badges">${up ? `<span class="badge">${up + 1} storeys</span>` : ""}${down ? `<span class="badge">an undercroft</span>` : ""}</div>`;
  }
  function siteFor(id) {
    if (/@the-woods$/.test(id) && SITES.cave) return "cave";
    if (/urban:the-well$/.test(id) && SITES.sewers) return "sewers";
    return "";
  }
  function townSlip(v) {
    const { F } = v, here = st.here;
    let out = "";
    const n = st.sel && F.found.has(st.sel) ? st.sel : null;
    if (n && n !== here) {
      const r = M.route(T.ways, F.visited, here, n), site = siteFor(n);
      const road = (T.ways[n] || []).find(w => w.journey);
      out += `<div class="mapnote picked"><h3>${e(M.upper(T.names[n]))}${F.visited.has(n) ? "" : " <small>not yet visited</small>"}</h3>${floorsBadge(n)}${
        r.legs.length ? `${legsHtml(r.legs)}<p>About ${r.minutes} ${r.minutes === 1 ? "minute" : "minutes"} on foot, by the way above.</p>`
          : `<p class="shutwhy">${e(r.why)}</p>`}
        ${road ? `<p>From there: ${e(M.upper(road.name))}, ${e(road.time_words)}.</p>` : ""}
        <div class="btnrow">${r.legs.length ? `<button type="button" class="go" data-walk>Walk there</button>` : ""}${
          site ? `<button type="button" class="go quiet" data-open="site" data-site="${site}">Go down ↓</button>` : ""}${
          road ? `<button type="button" class="go quiet" data-open="region">Region map</button>` : ""}${
          FIVE && /gate$/.test(n) ? `<button type="button" class="go quiet" data-open="nation">Out the gate: ${e((D.world.nations[st.nation] || {}).name || "the region")}</button>` : ""}</div></div>`;
    }
    if (FIVE && T.settings[here] === "outside") {
      out += `<div class="mapnote"><h3>Outside the walls <small>you are at ${e(T.names[here])}</small></h3>
        <p>The town map shows only what is inside the walls; the land outside is on the region map.</p>
        <button type="button" class="go quiet" data-open="nation">${e((D.world.nations[st.nation] || {}).name || "Region")}</button></div>`;
    }
    if (!(FIVE && T.settings[here] === "outside")) out += `<div class="mapnote"><h3>${e(M.upper(T.names[here]))} <small>you are here</small></h3>${floorsBadge(here)}
      <p>Press a place for the way there. The town is laid out by rule: the great square in the middle, the crossings at their compass points, every place in a fixed seat on its street, so nothing moves when more is found.</p></div>`;
    const inWalls = i => !FIVE || T.settings[i] === "in";   // the town map counts what is inside its walls
    out += `<div class="mapnote key"><span>${[...F.found].filter(inWalls).length} places found in the walls, ${[...F.visited].filter(inWalls).length} of them visited.</span>
      <span><i class="k-here"></i>You are here</span><span><i class="k-been"></i>Visited</span>
      <span><i class="k-seen"></i>Seen, not yet visited</span><span><i class="k-fog"></i>Not yet found</span></div>`;
    out += placeList([...F.found].filter(i => !M.floorOf(i) && (!FIVE || T.settings[i] === "in")).sort((a, b) => T.names[a].localeCompare(T.names[b])),
                     i => T.names[i], i => !F.visited.has(i));
    return out;
  }
  function regionSlip(v) {
    const { G } = v;
    let out = "";
    const n = st.sel;
    if (n && G.towns[n] && n !== st.regionHere) {
      const road = G.roads.find(r => (r.a === st.regionHere && r.b === n) || (r.b === st.regionHere && r.a === n));
      out += `<div class="mapnote picked"><h3>${e(G.towns[n].name)}${st.visitedTowns.has(n) ? "" : " <small>not yet visited</small>"}</h3>${
        road ? `<p>${road.days} days ${road.by === "river" ? "by river" : "by road"}${road.miles ? `, ${road.miles} miles` : ""}.</p>
               <button type="button" class="go" data-walk>Set out</button>`
             : `<p class="shutwhy">No road from ${e(G.towns[st.regionHere].name)} goes straight there.</p>`}</div>`;
    } else if (n && G.wild.some(w => w.id === n)) {
      const F = M.fog(T, [...st.been], st.here), r = M.route(T.ways, F.visited, st.here, n), site = siteFor(n);
      out += `<div class="mapnote picked"><h3>${e(M.upper(T.names[n]))}${F.visited.has(n) ? "" : " <small>not yet visited</small>"}</h3>${
        r.legs.length ? `${legsHtml(r.legs)}<p>About ${r.minutes} minutes on foot.</p>` : `<p class="shutwhy">${e(r.why)}</p>`}
        <div class="btnrow">${r.legs.length ? `<button type="button" class="go" data-walk>Walk there</button>` : ""}${
        site ? `<button type="button" class="go quiet" data-open="site" data-site="${site}">Go down ↓</button>` : ""}</div></div>`;
    }
    const here = G.towns[st.regionHere];
    out += `<div class="mapnote"><h3>${e(here.name)} <small>you are here</small></h3>
      <p>Towns one journey beyond every town you have stood in. Each notch on a road is a day: journey events will be pinned there.</p>
      ${st.regionHere === D.region.here ? `<button type="button" class="go quiet" data-open="town">Open the town map</button>`
        : `<p>(Only Featherperch's town chart was exported for this mock.)</p>`}</div>`;
    G.harbours.forEach(h => { out += `<div class="mapnote"><h3>By sea from ${e(G.towns[h.id].name)}</h3><p>${h.ports.map(p => e(G.towns[p].name)).join(", ")}.</p></div>`; });
    out += placeList([...G.shown].sort((a, b) => G.towns[a].name.localeCompare(G.towns[b].name)), i => G.towns[i].name, i => !st.visitedTowns.has(i));
    return out;
  }
  function siteSlip(v) {
    const s = v.site, room = id => s.rooms.find(r => r.id === id);
    let out = "";
    if (st.sel && st.sel !== v.here) {
      const r = room(st.sel), path = v.route;
      out += `<div class="mapnote picked"><h3>${e(M.upper(r.name))}${s.been.has(r.id) ? "" : " <small>not yet entered</small>"}</h3>
        ${s.been.has(r.id) && r.about ? `<p>${e(M.upper(r.about))}.</p>` : ""}
        ${path ? `<p>${path.length - 1} ${path.length === 2 ? "room" : "rooms"} on, through the rooms you know.</p><button type="button" class="go" data-walk>Go there</button>`
               : `<p class="shutwhy">No way there through the rooms you know.</p>`}</div>`;
    }
    const h = room(v.here);
    out += `<div class="mapnote"><h3>${e(M.upper(h.name))} <small>you are here</small></h3>${h.about ? `<p>${e(M.upper(h.about))}.</p>` : ""}
      <p>${e(M.upper(s.name))}, ${e(s.from)}. ${s.been.size} of ${s.rooms.length} rooms entered.</p>
      <div class="btnrow"><button type="button" class="go quiet" data-open="town">Back up to Featherperch</button>
      ${s.key === "sewers" ? `<button type="button" class="go quiet" data-replay="1">Replay from the way in</button>` : ""}</div></div>`;
    out += `<div class="mapnote"><h3>Sites</h3><div class="btnrow">${Object.values(SITES).map(x =>
      `<button type="button" class="go quiet" data-open="site" data-site="${x.key}"${x.key === s.key ? " disabled" : ""}>${e(M.upper(x.name))}</button>`).join("")}</div></div>`;
    return out;
  }
  function placeList(ids, name, seen) {
    return `<details class="list mapnote"><summary>Every place on this map (${ids.length})</summary><ul>${ids.map(i =>
      `<li><button type="button" data-pick="${e(i)}" class="${seen(i) ? "seen" : ""}" aria-pressed="${st.sel === i}">${e(M.upper(name(i)))}</button></li>`).join("")}</ul></details>`;
  }

  return { start, siteFor: id => siteFor(id) };
})();
