// The play table, part 01 of 6 (core). Split out of
// play/templates/play/table.html on 2026-09-25, in the order it ran; the six
// files are classic scripts, loaded in that order, sharing one global scope.
// The state last drawn. `render` keeps it current: it was `const`, set once at page load
// and never updated, so after switching characters the death panel still announced the
// character you had started the page as — and anything else reading STATE was reading a
// snapshot of a game that had moved on.
let STATE = window.PATHFINDER_BOOT.state;
const $ = s => document.querySelector(s);

function csrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : "";
}

// --- The roster ----------------------------------------------------------------
// Switching is switching campaigns: one per character, so somebody you come back to is
// where you left them rather than at the start of a new game.
async function openRoster() {
  let d;
  try { d = await readJSON(await fetch("/api/characters")); }
  catch (e) { $("#err").textContent = e.message; return; }

  $("#deathtitle").textContent = "Who is playing";
  $("#deathtext").textContent =
    "Switching picks up that character's game where it stopped. The dead stay on the "
    + "roster; they are the reason the next game went the way it did.";
  $("#deathchoices").innerHTML = (d.roster || []).map(e => `
    <button class="pick ${e.current ? "current" : ""}" data-switch="${esc(e.id)}"
            ${e.playable && !e.current ? "" : "disabled"}>
      <b>${esc(e.name)}</b>
      <small>${esc(e.line)} · ${esc(e.hp)} hp${
        e.current ? " · playing now" : e.status === "dead" ? " · dead" : ""}</small>
      ${e.epitaph ? `<em>${esc(e.epitaph)}</em>` : ""}
    </button>`).join("");
  $("#deathroster").innerHTML = `<h3>Somebody new</h3>` + (d.choices || []).map(ch => `
    <button class="pick" data-source="${esc(ch.source)}">
      <b>${esc(ch.name)}</b><small>${esc(ch.line)} · ${ch.hp} hp</small>
    </button>`).join("")
    + `<button class="pick" id="closeroster"><b>Never mind</b>
       <small>carry on with the game in front of you</small></button>`;
  // The death screen's way out is for a death; the roster has "Never mind" instead.
  $("#deathhome").hidden = true;
  $("#deathveil").classList.add("on");
}

// One listener for every button in the panel. Two of them — one for switching, one for
// starting somebody new — both matched `.pick`, so a click on a roster row fired both:
// it switched campaigns *and* posted /api/character/new with an undefined source, and
// "Never mind" quietly rolled a new character instead of closing the panel.
// The map. It was a tray that slid in from a MAP tab on the left edge; since the table
// rebuild (docs/table-rebuild-inventory.md, M5) it is a tab of its own, the board where
// the book was, because the owner's approved design made it one (the mock README, "Map
// is a tab, Talk is a tray": the side panel's copy was 18px a square, "legible only as
// a shape"). `render` redraws it on every state, so a token that moves on the turn you
// are watching moves on the board too. `Shell` is 12-shell.js, loaded later; a key press
// can only come after it has.
function showMap(on) {
  if (typeof Shell !== "object" || !Shell) return;
  Shell.show(on ? "map" : "table");
}
// The drawer, the edge tabs and the map tray went with the rebuild: the tabs on top are
// the one way to a page, on a phone as on a desktop (the mock README, "Phone (375px)").
// `showSheet` is still not declared anywhere: a later classic script's function of the
// same name silently wins, the JS form of what test_no_silent_shadowing guards.
document.addEventListener("keydown", e => {
  // A map is worth a shortcut in a game where the whole question is where you stand.
  const into = document.activeElement;
  if (e.key === "m" && !e.ctrlKey && !e.metaKey && !e.altKey
      && !/^(INPUT|TEXTAREA|SELECT)$/.test(into && into.tagName)) {
    showMap(!(typeof Shell === "object" && Shell && Shell.mode() === "map"));
  }
});

// Taking a level. The roll goes through the campaign's dice, so the hit points land
// in the roll log beside everything else the app rolls rather than appearing from
// nowhere on the sheet.
document.addEventListener("click", async e => {
  if (!e.target.closest("#levelup")) return;
  e.target.closest("#levelup").disabled = true;
  try {
    const r = await fetch("/api/level-up", {
      method: "POST", headers: {"X-CSRFToken":
        document.cookie.match(/csrftoken=([^;]+)/)?.[1] || ""}});
    // The level moved the game's revision; without noting it, the very next write from
    // this page — choosing the feat the level owed — was refused as "another device
    // moved the game on" (measured live 2026-10-04).
    noteRevision(r);
    const d = await readJSON(r);
    if (!r.ok) { $("#levelerr").textContent = d.error || "could not level"; return; }
    // Shown before the sheet redraws, so the number arrives as a die landing rather than
    // as a figure that was already on the sheet by the time anybody looked.
    if (d.rolled != null) {
      await Dice3D.land({
        title: "Hit points",
        why: `${d.name || "You"} reaches level ${d.level}`,
        sides: d.hit_die || 8,
        result: d.rolled,
        terms: [
          { label: `d${d.hit_die || 8}`, value: d.rolled },
          ...(d.con ? [{ label: "Constitution", value: sign(d.con) }] : []),
          { label: "hit points gained", value: d.hp, total: true },
        ],
        note: `${d.hp_max != null ? "Now " + d.hp_max + " at full." : ""}`,
      });
    }
    render(d);
    SHEET = await readJSON(await fetch("/api/sheet"));
    $("#sheetbody").innerHTML = TABS.find(x => x[0] === SHEET_TAB)[2](SHEET);
  } catch (err) { $("#levelerr").textContent = String(err); }
});

document.addEventListener("click", async e => {
  const pick = e.target.closest(".pick");
  if (!pick || pick.disabled) return;
  // A link dressed as a pick (the death screen's "Return to the main page") is left to
  // the browser. Without this the fall-through below posted /api/character/new with an
  // undefined source, the same double-handling the note above records for the roster.
  if (pick.tagName === "A") return;

  if (pick.id === "closeroster") {
    $("#deathveil").classList.remove("on");
    return;
  }
  if (pick.id === "resurrectbtn") {
    pick.disabled = true;
    try {
      render(await post("/api/resurrect", {}));
      $("#deathveil").classList.remove("on");
    } catch (err) { $("#err").textContent = err.message; pick.disabled = false; }
    return;
  }
  const switching = pick.dataset.switch !== undefined;
  pick.disabled = true;
  try {
    render(switching
      ? await post("/api/character/switch", {id: pick.dataset.switch})
      : await post("/api/character/new", {source: pick.dataset.source}));
    $("#deathveil").classList.remove("on");
  } catch (err) { $("#err").textContent = err.message; pick.disabled = false; }
});

