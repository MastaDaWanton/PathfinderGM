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
  $("#deathveil").classList.add("on");
}

// One listener for every button in the panel. Two of them — one for switching, one for
// starting somebody new — both matched `.pick`, so a click on a roster row fired both:
// it switched campaigns *and* posted /api/character/new with an undefined source, and
// "Never mind" quietly rolled a new character instead of closing the panel.
// The map tray. `render` refills it while it is open, so a token that moves on the
// turn you are watching moves here too rather than going stale behind the tab.
function showMap(on) {
  $("#maptray").classList.toggle("on", on);
  $("#maptab").style.display = on ? "none" : "";
  if (on && STATE) renderMap(STATE);
}
// The sheet drawer, which exists only under the phone breakpoint. Two panels that slide
// over the same screen must not both be open: on a 375px phone the second one lands on
// top of the first and the one underneath can only be found by closing the one above it.
function showSheet(on) {
  $("aside").classList.toggle("on", on);
  $("#sheettab").style.display = on ? "none" : "";
  if (on) showMap(false);
}
document.addEventListener("click", e => {
  if (e.target.closest("#maptab") || e.target.closest("#mapopen")) {
    showSheet(false);
    showMap(true);
  }
  else if (e.target.closest("#mapclose")) showMap(false);
  else if (e.target.closest("#sheettab")) showSheet(true);
  // Anywhere outside it, while it is open. A drawer with no way out but a tab it is
  // currently covering is a trap, and the tab is hidden precisely while it is open.
  else if ($("aside").classList.contains("on") && !e.target.closest("aside")) {
    showSheet(false);
  }
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && $("#maptray").classList.contains("on")) showMap(false);
  if (e.key === "Escape" && $("aside").classList.contains("on")) showSheet(false);
  // A map is worth a shortcut in a game where the whole question is where you stand.
  if (e.key === "m" && !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) {
    showMap(!$("#maptray").classList.contains("on"));
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

