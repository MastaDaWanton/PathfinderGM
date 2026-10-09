"""The tanner's ledger card, the Journal's Tanner's ledger and the leather perk picker
(docs/leatherworking-ui-plan.md §6.7; leatherworking contracts §11 U5 and §11.1). Lane U5.

The card and the Journal section are play/static/js/table/44-forge-ledger.js, parameterised
by track (`window.MaterialLedger.card(track, materialId, anchorEl)` and
`.journal(host, track)`), with `window.ForgeLedger` kept as the forge's thin alias; the
picker is 36-bench-perks.js, on which 44 registers the leatherworker's four perks. The
behaviour checks load the real files into node with a small fake DOM, as
tests/test_forge_ledger_ui.py does, and feed them the REAL server's answers: a campaign is
begun, a wolf pelt and oak bark are carried, one property is learned through
rules/knowledge.py, a real Grade is rolled through `/api/leather/grade`, and the material,
ledger and state routes are read through the Django test client. They skip, saying why,
where node is not installed. Each test names the defect it prevents.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from play import leather_views
from rules import knowledge
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parent.parent
TABLE_JS = ROOT / "play" / "static" / "js" / "table"
LEDGER = TABLE_JS / "44-forge-ledger.js"
PERKS = TABLE_JS / "36-bench-perks.js"
JOURNAL = TABLE_JS / "21-tab-journal.js"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- the server's answers, from a real campaign -----------------------------------------------

@pytest.fixture(scope="module")
def served(tmp_path_factory):
    """What the page is given: the real leather views over the real knowledge and materials
    modules, on a scratch campaign dir. Only lane G's door is stood in for (the field kit
    here), so Grade can be rolled without walking to a tannery."""
    from rules import places

    tmp = tmp_path_factory.mktemp("leather-ledger")
    with pytest.MonkeyPatch.context() as mp, override_settings(CAMPAIGN_DIR=tmp / "campaigns"):
        mp.setattr(places, "leather_bench_here", lambda scene, actor, known=(): {
            "at": "field", "tannery": None, "field_kit": True,
            "tiers": ("common", "uncommon"), "vats": False})
        cm._LIVE.clear()
        leather_views._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.herb_known.clear()
        client = Client()
        out = {"empty_ledger": client.get("/api/leather/ledger").json()}
        pc.carry("wolf-pelt", 1)
        pc.carry("oak-bark", 2)
        keys = knowledge.property_keys(knowledge.material("wolf-pelt"))
        knowledge.reveal(pc, "wolf-pelt", [keys[0]], "graded, day 3")
        c.save()
        out["pelt"] = client.get("/api/leather/material/wolf-pelt").json()
        out["bark"] = client.get("/api/leather/material/oak-bark").json()
        out["ledger"] = client.get("/api/leather/ledger").json()
        out["track"] = client.get("/api/leather/state").json()["track"]
        r = client.post("/api/leather/grade", data=json.dumps({"material": "wolf-pelt", "face": 20}),
                        content_type="application/json")
        assert r.status_code == 200, r.content[:400]
        out["graded"] = r.json()
        out["pelt_after"] = client.get("/api/leather/material/wolf-pelt").json()
        cm._LIVE.clear()
        leather_views._PENDING.clear()
    return out


# --- the node harness --------------------------------------------------------------------------

_NODE = r"""
const fs = require('fs'), vm = require('vm');
const args = JSON.parse(process.argv[2]);
const data = JSON.parse(fs.readFileSync(args.data, 'utf8'));

class El {
  constructor() { this.listeners = {}; this.kids = []; this.attrs = {}; this.dataset = {}; this.style = {};
    this.innerHTML = ''; this.removed = false; this.parentNode = null; this.cls = new Set(); this.hidden = false;
    const self = this;
    this.classList = { add: (c) => self.cls.add(c), remove: (c) => self.cls.delete(c),
      contains: (c) => self.cls.has(c), toggle: (c, on) => { on ? self.cls.add(c) : self.cls.delete(c); } }; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  appendChild(c) { c.parentNode = this; this.kids.push(c); return c; }
  remove() { this.removed = true; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  querySelector() { return null; }
  contains(x) { return x === this; }
  focus() {}
}
const ids = {};
const events = [];
const doc = { activeElement: null, cookie: '', head: new El(), body: new El(),
  getElementById: (id) => ids[id] || null, createElement: () => new El(), querySelector: () => null,
  addEventListener() {}, contains: (x) => !!x && !x.removed,
  dispatchEvent: (e) => { events.push([e.type, e.detail]); return true; } };
class CustomEvent { constructor(type, init) { this.type = type; this.detail = init && init.detail; } }
const calls = [];
// The server, as the routes answered it: GETs by path, POSTs by route.
const reply = (path, body) => {
  if (path === '/api/leather/material/wolf-pelt') return calls.filter(c => c[1]).length ? data.pelt_after : data.pelt;
  if (path === '/api/leather/grade') return data.graded;
  if (path === '/api/leather/ask') return data.refusal;
  if (path === '/api/leather/perks') return Object.assign({}, data.track, { picks_banked: 0 });
  throw new Error('unexpected ' + path);
};
const fetch = (path, opts) => {
  const body = opts && opts.body ? JSON.parse(opts.body) : null;
  calls.push([path, body]);
  const answer = reply(path, body);
  return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(JSON.stringify(answer)) });
};
const sandbox = { document: doc, console, setTimeout, clearTimeout, Promise, JSON, Object, Array,
  String, Number, Math, Error, RegExp, CustomEvent, fetch, addEventListener() {},
  innerWidth: 1600, innerHeight: 900 };
sandbox.window = sandbox;
vm.createContext(sandbox);
const tick = () => new Promise((r) => setTimeout(r, 0));
const target = (map) => ({ closest: (sel) => map[sel] || null });
const out = {};

(async () => {
  vm.runInContext(fs.readFileSync(args.perks, 'utf8'), sandbox);
  vm.runInContext(fs.readFileSync(args.ledger, 'utf8'), sandbox);
  const M = sandbox.MaterialLedger, F = sandbox.ForgeLedger, R = M.render;
  if (args.mode === 'render') {
    const L = { track: 'leatherworker' };
    out.api = ['card', 'journal', 'peek', 'unpeek', 'close', 'forget'].filter((n) => typeof M[n] !== 'function');
    out.forgeApi = ['card', 'journal', 'peek', 'unpeek', 'close', 'forget'].filter((n) => typeof F[n] !== 'function');
    out.sameRender = F.render === M.render;
    out.pelt = R.card(data.pelt, Object.assign({ actions: true, pinned: true }, L));
    out.peltJournal = R.props(data.pelt, L);
    out.peltAsForge = R.props(data.pelt);
    out.bark = R.card(data.bark, Object.assign({ actions: true }, L));
    out.none = R.card(Object.assign({}, data.pelt, { carried_units: 0, carried: 0 }), Object.assign({ actions: true }, L));
    out.tanner = R.card(Object.assign({}, data.pelt, { tanners_here: [{ ref: 'npc:hollin', name: 'Hollin', price: '5 sp' }] }),
                        Object.assign({ actions: true }, L));
    const shield = Object.assign({}, data.pelt, { properties: data.pelt.properties.concat([
      { key: 's0', known: true, text: '+1 shield bonus', drawback: false, how: 'graded, day 4', group: 'shield' }]) });
    out.shield = R.props(shield, L);
    out.shieldForge = R.props(shield);
    const marked = Object.assign({}, data.pelt, { properties: data.pelt.properties.concat([
      { key: 'k0', known: true, text: 'Fire resistance 1', drawback: false, how: 'graded, day 4', group: 'mark' }]) });
    out.marked = R.card(marked, Object.assign({ actions: true }, L));
    const markedBlind = Object.assign({}, data.pelt, { properties: data.pelt.properties.concat([
      { key: 'unknown-9', known: false, text: null, drawback: null, how: null, group: 'mark' }]) });
    out.markedBlind = R.card(markedBlind, Object.assign({ actions: true }, L));
    out.rows = R.rows({ track: 'leatherworker', ledger: data.ledger.ledger, open: '', cards: {}, unknownFirst: false });
    out.rowsFirst = R.rows({ track: 'leatherworker', ledger: data.ledger.ledger, open: '', cards: {}, unknownFirst: true });
    out.rowsEmpty = R.rows({ track: 'leatherworker', ledger: data.empty_ledger.ledger, open: '', cards: {} });
    out.rowsOpen = R.rows({ track: 'leatherworker', ledger: data.ledger.ledger, open: 'wolf-pelt', cards: { 'wolf-pelt': data.pelt } });
    out.learned = R.learned(data.graded, 'You graded Wolf Pelt.');
    out.grader = R.needsConfirm(data.pelt);
  }
  if (args.mode === 'grade') {
    ids['leather-rack'] = null;
    const anchor = { closest: () => null, getBoundingClientRect: () => ({ top: 100, left: 20, right: 300, bottom: 130 }), focus() {} };
    M.card('leatherworker', 'wolf-pelt', anchor);
    await tick(); await tick();
    const card = doc.body.kids.find((k) => k.id === 'forge-ledger-card') || doc.body.kids[doc.body.kids.length - 1];
    out.first = card.innerHTML;
    out.open = M.isOpen('leatherworker') && !M.isOpen('blacksmith');
    card.listeners.click.forEach((f) => f({ target: target({ '[data-fl]': { dataset: { fl: 'grade' } } }) }));
    for (let i = 0; i < 8; i++) await tick();
    out.calls = calls;
    out.events = events;
    out.after = card.innerHTML;
    card.listeners.click.forEach((f) => f({ target: target({ '[data-fl]': { dataset: { fl: 'ask', ref: 'npc:hollin' } } }) }));
    for (let i = 0; i < 8; i++) await tick();
    out.asked = card.innerHTML;
    out.askCall = calls[calls.length - 2];
  }
  if (args.mode === 'perks') {
    const P = sandbox.BenchPerks;
    out.registered = !!P.tracks.leatherworker;
    const pops = new El(); const posts = []; const saved = [];
    const wrap = P.open({ track: 'leatherworker', state: Object.assign({}, data.track, { picks_banked: 2 }), pops,
      api: (p, b) => { posts.push([p, b]); return Promise.resolve(Object.assign({}, data.track, { picks_banked: 0 })); },
      saved: (t, picks) => saved.push(picks) });
    out.html = wrap.innerHTML;
    const click = (map) => wrap.listeners.click.forEach((f) => f({ target: target(map) }));
    click({ '[data-perk]': { dataset: { perk: 'yield' } } });
    click({ '[data-perk]': { dataset: { perk: 'quality' } } });
    click({ '[data-pk]': { dataset: { pk: 'ok' }, disabled: false } });
    await tick(); await tick();
    out.posts = posts; out.saved = saved;
  }
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


def _node(mode: str, data: dict) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed; the behaviour checks need a JS engine")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "ledger.js"
        script.write_text(_NODE, encoding="utf-8")
        blob = Path(tmp) / "data.json"
        blob.write_text(json.dumps(data), encoding="utf-8")
        done = subprocess.run([node, str(script), json.dumps({
            "mode": mode, "data": str(blob), "perks": str(PERKS), "ledger": str(LEDGER)})],
            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr[:2000]
    return json.loads(done.stdout)


REFUSAL = "Hollin has no wish to help you, and keeps what they know of Wolf Pelt to themselves."


@pytest.fixture(scope="module")
def drawn(served):
    return _node("render", served)


@pytest.fixture(scope="module")
def graded(served):
    return _node("grade", {**served, "refusal": {"revealed": [], "paid": "", "minutes": 0, "refused": REFUSAL}})


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# --- the card ---------------------------------------------------------------------------------

def test_the_leather_card_shows_what_is_known_how_and_one_line_per_unknown(served, drawn):
    """UI plan §6.7: a known property says what it does and how it was learned ("graded,
    day 3"); every property still unknown is one "unknown" line, never its text. The wolf
    pelt has four properties; with one learned the card carries three "unknown" lines, and
    the Journal draws the very same lines."""
    props = served["pelt"]["properties"]
    assert len(props) == 4 and sum(p["known"] for p in props) == 1
    assert all(p["text"] is None for p in props if not p["known"]), "the server leaked a secret"
    html = drawn["pelt"]
    assert html.count(">unknown</span>") == 3
    assert "+2 Survival" in html and "graded, day 3" in html
    assert drawn["peltJournal"].count(">unknown</span>") == 3 and "graded, day 3" in drawn["peltJournal"]


def test_an_unknown_line_never_says_where_it_acts_on_the_tanners_card(served, drawn):
    """Grade reveals one benefit and one drawback (lane F), so where an unknown property
    acts is part of what Grade finds. Measured 2026-10-08: `/api/leather/material/wolf-pelt`
    sent its unknown working trait with `group: "working"`, and the smith's renderer, which
    files unknown lines by group on purpose, headed it "At the anvil" before anything had
    been graded there: the alchemy leak lane U1 closed on 2026-10-07. The tanner's card files
    unknown lines under "Not yet known" and names no group no known line has earned. The
    smith's card is unchanged (it still heads the same row, by its own design)."""
    # Since the lead's fix the same day the server sends no group at all on an unknown
    # row (`leather_views.leather_material`, "unknown-N"), so the page cannot leak one.
    blind = [p for p in served["pelt"]["properties"] if not p["known"]]
    assert blind and all(p.get("group") is None and p["key"].startswith("unknown-")
                         for p in blind)
    html = drawn["pelt"]
    assert "At the bench" not in html and "At the anvil" not in html
    assert '<h4 class="fl-group">In armour</h4>' in html
    assert '<h4 class="fl-group">Not yet known</h4>' in html
    assert html.index("In armour") < html.index("+2 Survival") < html.index("Not yet known")
    assert "At the anvil" not in drawn["peltAsForge"], "a blind row reached a group heading"


def test_the_shield_group_has_a_heading_on_both_cards(drawn):
    """Lane F's knowledge added a `shield` property list (rules/knowledge.py MATERIAL_LISTS,
    "s") that no UI labelled: the smith's group table had weapon, armour, working and
    quench_mark only, and its order list dropped any other group, so a known shield line
    would not have been drawn at all. Both cards head it "In a shield"."""
    for html in (drawn["shield"], drawn["shieldForge"]):
        assert '<h4 class="fl-group">In a shield</h4>' in html and "+1 shield bonus" in html


def test_a_known_mark_has_its_heading_and_an_unknown_one_names_nothing(drawn):
    """Marks were held on the morning of 2026-10-08 and the card dropped every mark row,
    known or not; the owner kept them as planned the same day. A KNOWN mark (graded) is
    drawn under "On the finished item"; an unknown one is a blank "unknown" line under no
    heading of its own, even if a stray `group: "mark"` reaches the page, so the card never
    says a supply has a mark before Grade finds it."""
    assert '<h4 class="fl-group">On the finished item</h4>' in drawn["marked"]
    assert "Fire resistance 1" in drawn["marked"]
    blind = drawn["markedBlind"]
    assert "On the finished item" not in blind
    assert blind.count(">unknown</span>") == drawn["pelt"].count(">unknown</span>") + 1


def test_grade_is_offered_with_the_servers_cost_and_refused_in_words_with_nothing_to_cut(drawn):
    """The card's first action (UI plan §6.7): Grade, "a scrap, 10 minutes", in the
    server's words (`grade_cost`: a quarter unit of hide, or one measure of a supply). With
    none carried the button is disabled and says why beside it; a greyed button with no
    reason is the defect the rack's "never colour alone" rule exists for."""
    assert ">Grade<" in drawn["pelt"] and 'data-fl="grade">' in drawn["pelt"]
    assert "a quarter unit of hide, 10 minutes" in drawn["pelt"]
    assert "one measure, 10 minutes" in drawn["bark"]
    assert "Assay" not in _text(drawn["pelt"])
    none = drawn["none"]
    assert 'data-fl="grade" disabled aria-describedby="fl-assay-why"' in none
    assert "You carry none of it to take a scrap from." in none


def test_ask_a_tanner_shows_only_when_the_server_names_one_here(drawn):
    """"Ask a tanner when one is in the scene" (UI plan §6.7, §8): with nobody named the
    button must not be there at all; with one named it reads "Ask a tanner", the plan's one
    label for the intent, and names who and the price."""
    assert "Ask a tanner" not in drawn["pelt"] and "Ask a smith" not in drawn["pelt"]
    t = drawn["tanner"]
    assert 'data-fl="ask" data-ref="npc:hollin"' in t and ">Ask a tanner<" in t
    assert "Hollin, 5 sp" in t


def test_a_hide_is_counted_in_hide_units_and_a_supply_in_measures(served, drawn):
    """Lane E's card counts a carried hide in hide units (`carried_units`; a Grade takes a
    quarter) and a supply by count (`carried`). Printing `carried` for a hide said "0
    carried" of a pelt in the pack. Both read as the server sent them."""
    assert served["pelt"]["carried_units"] == 1 and served["pelt"]["carried"] == 0
    assert "1 hide unit carried" in _text(drawn["pelt"])
    assert "0 carried" not in _text(drawn["pelt"])
    assert "2 carried" in _text(drawn["bark"])


def test_every_number_on_the_leather_card_is_one_the_server_sent(served, drawn):
    """UI plan §12: "the page never computes a number". Every run of digits in the drawn
    card appears in the server's own answer (the tanner's price is the test's own)."""
    sent = json.dumps(served["pelt"])
    for html in (drawn["pelt"], drawn["tanner"]):
        for n in re.findall(r"\d+", _text(html)):
            assert n in sent or n == "5", (n, _text(html))


def test_a_grade_never_asks_first(drawn):
    """The owner's answer 10 (2026-10-08): dangerous hides force a second check while
    skinning, never a hazard at Grade. The leather card carries neither `assay_danger` nor
    `reactive`, so Grade never raises the forge's reactive confirm; a confirm on every grade
    trains the player to click through the one that matters."""
    assert drawn["grader"] is False


# --- Grade and Ask, driven through the card -------------------------------------------------------

def test_grading_posts_to_the_tanners_route_and_says_what_it_paid(served, graded):
    """The card's Grade runs the real round trip: the card is read from
    `/api/leather/material/<id>`, Grade posts the material and the player's face (none
    without the table's dice) to `/api/leather/grade`, and the answer is said in the card:
    what was learned and the mastery each property paid, from the server's own lines
    (`worldclass.STUDY_MP`, 1 a property found, the 2026-10-08 ruling). The bench's shell is
    told on `leather:learned` so it reads the rack and clock again (the scrap is gone and
    ten minutes passed); the forge's `forge:learned` must not fire for it."""
    calls = graded["calls"]
    assert calls[0] == ["/api/leather/material/wolf-pelt", None]
    assert calls[1] == ["/api/leather/grade", {"material": "wolf-pelt", "face": None}]
    revealed = served["graded"]["revealed"]
    assert revealed, "a natural 20 against DC 10 found nothing"
    text = _text(graded["after"])
    assert "You graded Wolf Pelt (d20 20" in text
    for f in revealed:
        assert f["text"] in text
    assert text.count("(+1 mastery)") == len(served["graded"]["mastery"]["lines"]) == len(revealed)
    assert "10 minutes passed." in text
    kinds = [e[0] for e in graded["events"]]
    assert "leather:learned" in kinds and "forge:learned" not in kinds
    assert graded["open"] is True


def test_a_tanner_who_will_not_help_is_said_in_their_own_words(graded):
    """`/api/leather/ask` answers a refusal (below indifferent, nothing new, or no coin) as
    `refused`, a sentence. The forge's card printed "You asked. Nothing new." over it, so the
    player never learned that the smith would not talk or that the purse was short. The
    card now prints the server's sentence."""
    assert graded["askCall"] == ["/api/leather/ask", {"material": "wolf-pelt", "ref": "npc:hollin"}]
    assert REFUSAL in _text(graded["asked"]).replace("&#39;", "'")
    assert "Nothing new" not in _text(graded["asked"])


# --- the Journal ------------------------------------------------------------------------------

def test_the_journal_counts_what_is_known_from_the_tanners_ledger(served, drawn):
    """UI plan §6.7: every hide met, "3 of 7 known", from the ledger's own `known` and
    `total` (rules/knowledge.py `ledger_row`): the pelt reads "1 of 4 known" and the bark
    "0 of 3 known", as the server sent them."""
    rows = {r["id"]: r for r in served["ledger"]["ledger"]}
    assert rows["wolf-pelt"]["known"] == 1 and rows["wolf-pelt"]["total"] == 4
    text = _text(drawn["rows"])
    assert "1 of 4 known" in text and f"0 of {rows['oak-bark']['total']} known" in text
    # The server lists by kind then name (hide before tannin); "Unknowns first" puts the
    # most unknown on top, by name on a tie (three each here), so the bark leads.
    plain, first = drawn["rows"], drawn["rowsFirst"]
    assert plain.index('data-fl-mat="wolf-pelt"') < plain.index('data-fl-mat="oak-bark"')
    assert first.index('data-fl-mat="oak-bark"') < first.index('data-fl-mat="wolf-pelt"')


def test_the_tanners_journal_says_what_to_do_when_empty(drawn):
    """An empty ledger invites the act that fills it, in the craft's own words: "Buy or mine
    one" is the smith's and would send a tanner to the mine."""
    assert "No hides or supplies yet. Take one from a carcass or buy one and it appears here." in drawn["rowsEmpty"]
    assert "mine" not in drawn["rowsEmpty"]


def test_a_tanners_journal_row_has_ids_of_its_own(drawn):
    """The smith's and the tanner's ledgers sit on one Journal page and can list the same
    material (rules/knowledge.py's ledger is every material met). A row body id of
    "fl-jr-card-wolf-pelt" in both would give two elements one id, and the smith's
    disclosure would control the tanner's body. The tanner's ids carry the track."""
    html = drawn["rowsOpen"]
    assert 'aria-controls="fl-jr-card-leatherworker-wolf-pelt"' in html
    assert 'id="fl-jr-card-leatherworker-wolf-pelt" class="fl-jr-body">' in html
    assert "graded, day 3" in html and "At the bench" not in html


def test_the_journal_mounts_the_tanners_ledger_after_the_smiths():
    """Read statically: 21 adds the "Tanner's ledger" card, whose list id is not the
    heading's id, and draws it through 44 for the leatherworker track. It mounts LAST in
    the observer: the essences and the codex each insert themselves straight after the
    smith's ledger, so a tanner's ledger mounted before them would be pushed down under
    both."""
    js = _src(JOURNAL)
    assert 'sheetCard("jr-hides", "Tanner\'s ledger", `<div id="jr-hides-list"></div>`, "jr-hides")' in js
    assert 'window.MaterialLedger.journal(document.getElementById("jr-hides-list"), "leatherworker")' in js
    assert "herbariumMount(); ledgerMount(); essencesMount(); codexMount(); hidesMount(); }" in js
    assert '["jr-ledger", "jr-herbarium"]' in js


# --- the contract ----------------------------------------------------------------------------------

def test_the_ledger_answers_both_names(drawn):
    """Contracts §11.1: `MaterialLedger.card(track, materialId, anchorEl)` and
    `.journal(host, track)` for the leather bench; `ForgeLedger` stays a thin alias with its
    old names, so the forge is unchanged. One renderer behind both."""
    assert drawn["api"] == [] and drawn["forgeApi"] == []
    assert drawn["sameRender"] is True


def test_the_ledger_never_loops_and_carries_no_dash():
    """Nothing in the ledger animates on a timer (no setInterval, no requestAnimationFrame:
    idle zero frames, UI plan §14), and no new string carries an em-dash or en-dash (UI
    plan §8, the lane greps for both)."""
    js = _src(LEDGER)
    assert not re.search(r"\b(setInterval|requestAnimationFrame)\s*\(", js)
    assert "—" not in js and "–" not in js
    journal = _src(JOURNAL)
    sect = journal[journal.index("// --- The tanner's ledger"):journal.index("(function watchTheJournal()")]
    assert "—" not in sect and "–" not in sect


# --- the perk picker ------------------------------------------------------------------------

def test_the_leather_picker_offers_its_four_perks_with_the_servers_words(served):
    """Owner Q6.3: "the forge's four, Yield moved to skinning". 36's picker had rows for the
    herbalist, the blacksmith, the enchanter and the alchemist only, so
    `BenchPerks.open({track: "leatherworker"})` returned null and a Leatherworker 4 could
    never spend a pick. 44 registers the row: each choice says what the next pick does in
    the server's words with its numbers (`perk_info[id].next`), the level line reads
    "Leatherworker", and the picks go to the tanner's route."""
    run = _node("perks", served)
    track = served["track"]
    assert run["registered"] is True
    html = run["html"]
    for perk in ("potency", "hardening", "quality", "yield"):
        assert f'data-perk="{perk}"' in html
        assert track["perk_info"][perk]["next"] in html
    assert 'data-perk="duration"' not in html
    assert '<h3 id="leather-perks-t">Pick two perks</h3>' in html
    assert f"<p>Leatherworker {track['level']}. The same perk twice is allowed.</p>" in html
    assert run["posts"] == [["/api/leather/perks", {"picks": ["yield", "quality"]}]]
    assert run["saved"] == [["yield", "quality"]]
