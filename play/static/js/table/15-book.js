// The play table, part 15 (the book's head). Classic script, sharing one global scope
// with 01-14 and 16-21.
//
// Where you are, in words, across the top of the page (the approved design's head row):
// the place's name, the line under it, and who is here. The line is the old side
// column's biome line, moved (docs/table-rebuild-inventory.md, B7): geography's words
// (`where_label`, `where_detail`, docs/fix-interfaces.md §2.10) when the server sends
// them, today's location, scale and biome otherwise, then the clock and the part of the
// day. The title attribute keeps what the old line kept in its own: what kind of place
// this is.
//
// Who is here is the scene's actors the player can see. The design opens a line about
// the person pressed; the state sends no face for them (the engine has
// `names.appearance_for`, and the actor payload would have to carry it), so the line says
// how they stand, hurt or not and any condition on them, from the same fields the old
// "In the scene" list showed. It never guesses a face.

let BOOK_PERSON = null;

function bookWhere(s) {
  const sc = (s && s.scene) || {};
  const town = sc.where_label || sc.location || "";
  // The place you stand in, when the ground is laid ("the gate", "the market"): the
  // design's head names it, with the settlement on the line under it. Measured live: a
  // walk from the market to the gate left the head reading "Torvathys · town" throughout.
  // Its NAME, from the place chart's current node. The grid's `place` is the id's path,
  // which for a place founded inside another reads "the gate/the velvet veil/the
  // chamber" (seen 2026-10-01 on the owner's save); its last part is the fallback.
  const here = ((sc.places_found && sc.places_found.nodes) || []).find(n => n.current);
  const local = (here && here.name)
    || String((sc.grid && sc.grid.place) || "").split("/").pop().trim();
  const place = local || town;
  const parts = [];
  if (local && town) parts.push(town);
  if (sc.where_label) {
    if (sc.where_detail) parts.push(sc.where_detail);
  } else {
    const kind = [sc.scale, sc.biome].filter(Boolean).join(", ");
    if (kind) parts.push(kind);
  }
  if (typeof fmtClock === "function") parts.push(fmtClock(sc.clock_minutes));
  if (sc.day_part) parts.push(sc.day_part);
  return { place, line: parts.map(sidesUp).join(". ") + (parts.length ? "." : ""),
           about: sc.what_it_is || sc.biome_describe || "" };
}

function bookStanding(a) {
  const hurt = a.hp < a.hp_max ? (a.hp <= 0 ? "down" : "wounded") : "unhurt";
  const conds = (a.conditions || []).filter(Boolean);
  return `${sidesUp(a.name)}: ${hurt}${conds.length ? `, ${conds.join(", ")}` : ""}.`;
}

function renderBookHead(s) {
  const head = document.getElementById("place-name");
  if (!head) return;
  const w = bookWhere(s);
  head.textContent = w.place || "Nowhere yet";
  const line = $("#where-line");
  line.textContent = w.line;
  line.title = w.about;

  const people = ((s && s.scene && s.scene.actors) || []).filter(a => !a.is_pc);
  if (BOOK_PERSON && !people.some(a => a.ref === BOOK_PERSON)) BOOK_PERSON = null;
  $("#here").hidden = !people.length;
  $("#here-list").innerHTML = people.map(a => `<button type="button" class="v2-btn"
      data-person="${esc(a.ref)}" aria-expanded="${BOOK_PERSON === a.ref}"
      aria-controls="face">${esc(a.name)}</button>`).join("");
  const who = people.find(a => a.ref === BOOK_PERSON);
  $("#face").hidden = !who;
  $("#face").textContent = who ? bookStanding(who) : "";
}

onRender(function bookHead(s, prev) {
  renderBookHead(s);
  storyLand(s, prev);
});

// --- Where the story opens ---------------------------------------------------------------
// A new beat lands with its first line at the top of the page, and a reader who has
// scrolled back to reread is left where they are. The page used to be sent to its foot
// (`scrollTop = scrollHeight`), which put a beat longer than the page with its opening
// above the head: measured at 1792x805 on a reload, the fresh beat's top at 119 against
// the story's top at 145, 26px under the head, its drop cap showing only its stem. And the
// foot moved after it was sent there: the first draw runs before this head is filled in,
// so the head then grew and the page's last 103px went under the desk (scrollTop 4390 +
// 252 of 4745, measured the same way). So the landing is by the beat's own offset, made
// once the head is drawn, and made again whenever the layout under it settles (the head,
// the fonts, the width) until the reader moves the page themselves.
//
// Which page scrolls: `#story` on a desktop; on a phone the whole leaf (`#bookin`), head
// and all (the design's phone: a fixed head left the story 190px).
//
// WHERE THE READER WAS is taken before the rebuild, not after it (the owner, 2026-10-27:
// "once the narration goes a few turns ... it jumps you up"). render() rebuilds the story
// whole with every "That's wrong" slot empty, and 23-thats-wrong.js fills them in a hook
// that runs after this one. In between, the story is one slot shorter per narrated beat,
// and a page at its foot is clamped up by all of them. Measured on the owner's save, 24
// slots in: 13689 to 13001, and the landing read the clamped position as a reader who had
// scrolled back to reread, so it held the page there; then the slots filled above it and
// the new turn sat 1192px below the top of a 587px pane. So `storyKeep` (called by render
// before the rebuild) keeps the position the reader really had, the reread test reads
// that, and every landing, or a rereader's own place, is put back once the hooks have
// drawn (a microtask: after render's last hook, before the browser paints).
const STORY = { count: 0, beat: -1, landedAt: null, holding: false, watch: null, was: null };

function storyKeep() {
  const scroller = storyScroller();
  STORY.was = scroller ? scroller.scrollTop : null;
}

function storyAfterHooks(fn) {
  if (typeof queueMicrotask === "function") queueMicrotask(fn);
  else Promise.resolve().then(fn);
}

function storyScroller() {
  const story = document.getElementById("story");
  if (!story) return null;
  return getComputedStyle(story).overflowY === "visible"
    ? document.getElementById("bookin") : story;
}

// The scroll position that puts beat `i`'s first line at the top of the page: its offset
// in the story (the story is `position: relative`, so that is its offsetParent), less the
// story's own top padding, so it sits where the first beat of all would; on a phone the
// story's offset in the leaf is added and the head is scrolled past with it.
function storyTopOf(i) {
  const story = document.getElementById("story"), scroller = storyScroller();
  const beat = story && story.querySelectorAll(".beat")[i];
  if (!beat || !scroller) return null;
  const pad = parseFloat(getComputedStyle(story).paddingTop) || 0;
  const within = scroller === story ? 0 : story.offsetTop;
  return Math.max(0, within + beat.offsetTop - pad);
}

function storySettle() {
  const scroller = storyScroller(), top = storyTopOf(STORY.beat);
  if (!scroller || top === null) return;
  scroller.scrollTop = top;
  STORY.landedAt = scroller.scrollTop;          // what the browser allowed (the foot clamps)
}

function storyLand(s, prev) {
  const n = ((s && s.transcript) || []).length;
  const scroller = storyScroller();
  // Where the reader was before this draw's rebuild (`storyKeep`), or, when nothing
  // called it, where the page is now.
  const was = STORY.was !== null ? STORY.was : (scroller ? scroller.scrollTop : 0);
  STORY.was = null;
  if (!scroller || !n) { STORY.count = n; return; }
  // Put back where they were once every hook has drawn: the rebuild's clamp has moved it.
  const stay = () => storyAfterHooks(() => {
    if (STORY.holding) storySettle(); else scroller.scrollTop = was;
  });
  if (prev && n <= STORY.count) { STORY.count = n; stay(); return; }   // nothing new
  // Scrolled back above where the last beat landed: they are rereading. Nothing moves.
  const rereading = prev && STORY.landedAt !== null && was < STORY.landedAt - 24;
  // The first new beat (the player's own line leads the answer), or on a fresh page, the
  // newest beat of all.
  STORY.beat = prev ? Math.min(STORY.count, n - 1) : n - 1;
  STORY.count = n;
  if (rereading) { STORY.holding = false; stay(); return; }
  STORY.holding = true;
  storySettle();
  // And again once the slots under the beats are filled, which moves every beat below
  // them down by their height.
  storyAfterHooks(() => { if (STORY.holding) storySettle(); });
  storyWatch();
}

// While a landing holds, a change of size under it (the head drawn, a font arriving, the
// window resized) lands it again. The reader's own wheel, touch, key or press lets go.
function storyObserve() {
  if (!STORY.watch) return;
  STORY.watch.disconnect();
  // The slots under the narrated beats too: one filled or opened late moves every beat
  // after it, and the story's own box (a scroller) never changes size when they do.
  const els = [document.getElementById("story"), document.getElementById("bookin"),
               document.querySelector(".bookhead"),
               ...document.querySelectorAll("#story .beat, #story .beatfix")];
  for (const el of els) if (el) STORY.watch.observe(el);
}

function storyWatch() {
  if (STORY.watch || typeof ResizeObserver !== "function") { storyObserve(); return; }
  const story = document.getElementById("story"), leaf = document.getElementById("bookin");
  STORY.watch = new ResizeObserver(() => { if (STORY.holding) storySettle(); });
  storyObserve();
  const letGo = () => { STORY.holding = false; };
  for (const el of [story, leaf]) {
    if (!el) continue;
    for (const type of ["wheel", "touchstart", "pointerdown", "keydown"]) {
      el.addEventListener(type, letGo, { passive: true });
    }
  }
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => { if (STORY.holding) storySettle(); });
  }
}
// The story's content changes height without its box changing (a beat's text reflowing
// as the drop cap's face loads): the beats themselves are watched too, the fresh set on
// each render (`storyObserve`, above).
