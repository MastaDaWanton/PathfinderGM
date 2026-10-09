"""The deeds on the page: the Sheet tab's Deeds card, the Journal's history line, and
GET api/deeds (docs/deeds-plan.md §9, §12 DEED-2).

The owner, 2026-10-08: "you should be able to look at this number in your sheet but i
dont want it to affect anything yet". The card shows the number, its word and the rows it
is the sum of; nothing on it is worked out in the page, and no ref reaches it (the ruling
"refs never on the page", 2026-09-28). The card's functions run in node against the real
`/api/sheet` payload, as tests/test_sheet_pages.py runs the rest of the sheet.
"""
from __future__ import annotations

import json
import re

from django.conf import settings
from django.test import Client

from rules import deeds
from rules.sheet import from_dict, load_pc
from tests.test_sheet_pages import _run, _text, _tree, needs_node

ABILITIES = {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")}
# Node writes its stdout in UTF-8 and the harness reads it in the console's code page, so
# the minus sign (U+2212) on a chip arrives as mojibake; escaped, it arrives as itself.
_BS = chr(92)        # built, not typed: a backslash in an edit tool or heredoc is a trap
_ASCII = (".replace(/[" + _BS + "u0080-" + _BS + "uffff]/g, ch => \"" + _BS + _BS
          + "u\" + ch.charCodeAt(0).toString(16).padStart(4, \"0\"))")
_REF = re.compile(r"\bc\d+\b|5bbd0c40345f")


def _campaign(tmp_path):
    from play import campaign as cm

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    cm._LIVE.clear()
    c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
    seller = c.scene.add(from_dict({"name": "fruit seller", "kind": "npc", "hp": 9,
                                    "hp_max": 9, "abilities": dict(ABILITIES),
                                    "goods": {"apple": 5, "pear": 2}}, ref="c71"))
    return cm, c, seller


def _turn(c, raw):
    """One player turn through the engine, logged the way the views log it."""
    from play import history as history_mod

    e = c.engine()
    intents = e.validate(raw)
    res = e.run(intents)
    c.turn_log.append(history_mod.stamp(c, {
        "kind": "turn", "intents": [i.as_dict() for i in intents],
        "outcomes": [o.as_dict() for o in res.outcomes]}))
    return res


def _three(tmp_path):
    """Three deeds in order: a theft (-1), the same theft again (0), and the pear handed
    back to its owner (+1)."""
    cm, c, seller = _campaign(tmp_path)
    take = {"op": "give", "actor": "pc", "because": "she pockets it", "params": {"to": "pc"}}
    _turn(c, [dict(take, params={"item": "apple", "to": "pc"})])
    _turn(c, [dict(take, params={"item": "pear", "to": "pc"})])
    _turn(c, [{"op": "give", "actor": "pc", "target": seller.ref, "because": "back",
               "params": {"item": "pear"}}])
    c.save()
    pc = c.scene.pc()
    assert [r["tag"] for r in pc.deeds] == ["deed.theft", "deed.theft", "deed.restitution"]
    return cm, c, pc


@needs_node
def test_the_sheet_shows_the_number_the_word_and_the_rows(tmp_path):
    """A save with three deeds renders all three on the card, newest first, with the
    engine's total and word, the counts, and the seven words with the current one marked.
    The card is a sum the player can audit (Sawyer's visible +1/-1, PA §3); a card that
    showed a number and not the rows would be the hidden meter RDR2's players distrust."""
    cm, c, pc = _three(tmp_path)
    s = Client().get("/api/sheet").json()
    d = s["deeds"]
    assert (d["total"], d["word"], d["good"], d["bad"], d["again"]) == (0, "Unremarkable", 1, 1, 1)
    out = _run(tmp_path, f"const S = {json.dumps(s)};\n"
               "console.log(JSON.stringify({ html: deedsCard(S), page: pageSheet(S) })" + _ASCII + ");")
    els = _tree(out["html"])
    assert _text(next(e for e in els if "dd-num" in e["attrs"].get("class", ""))) == "0"
    assert _text(next(e for e in els if "dd-word" in e["attrs"].get("class", ""))) == "Unremarkable"
    rows = [e for e in els if e["tag"] == "li" and "dd-row" in e["attrs"].get("class", "")]
    said = [_text(next(x for x in els if r in x["ancestors"]
                       and "dd-said" in x["attrs"].get("class", ""))) for r in rows]
    assert said == ["Gave pear back to the fruit seller",
                    "Took pear from the fruit seller without asking",
                    "Took apple from the fruit seller without asking"]
    chips = [_text(next(x for x in els if r in x["ancestors"]
                        and "dd-v" in x["attrs"].get("class", ""))) for r in rows]
    assert chips == ["+1", "0, again that day", "−1"]
    lit = [e for e in els if e["tag"] == "li" and e["attrs"].get("aria-current") == "true"]
    assert [_text(e) for e in lit] == ["Unremarkable"]
    assert "Nothing in the game reads this number yet" in out["html"]
    # On the Sheet tab, after Class and before Background and notes (plan §9.1).
    page = out["page"]
    assert page.index('id="sc-class"') < page.index('id="sc-deeds"') < page.index('id="sc-background"')


@needs_node
def test_the_help_opens_from_its_question_mark_only(tmp_path):
    """The help is behind a "?" button that says what it opens (aria-expanded,
    aria-controls) and starts hidden. Nothing on the card opens it on hover: the skill
    card that opened on hovering a row covered the rows under it and made skills
    impossible to pick (2026-10-08)."""
    cm, c, pc = _three(tmp_path)
    s = Client().get("/api/sheet").json()
    out = _run(tmp_path, f"const S = {json.dumps(s)};\n"
               "console.log(JSON.stringify({ html: deedsCard(S) }));")
    els = _tree(out["html"])
    q = next(e for e in els if e["attrs"].get("id") == "dd-q")
    assert q["tag"] == "button" and q["attrs"]["aria-expanded"] == "false"
    assert q["attrs"]["aria-controls"] == "dd-help" and q["attrs"].get("aria-label")
    help_ = next(e for e in els if e["attrs"].get("id") == "dd-help")
    assert "hidden" in help_["attrs"]
    src = open("play/static/js/table/05-sheet.js", encoding="utf-8").read()
    block = src[src.index("// --- Deeds ---"):src.index("// Initiative, base attack")]
    assert "mouseover" not in block and "mouseenter" not in block and "focusin" not in block


def test_no_ref_reaches_the_deeds_page(tmp_path):
    """The ruling "refs never on the page" (2026-09-28): every row is said with the names
    of the time, and the place by its name. The refs and the place id stay in the save
    for renown, and never reach /api/sheet's deeds or /api/deeds."""
    cm, c, pc = _three(tmp_path)
    assert pc.deeds[0]["subject"] == "c71"            # in the save, for later
    client = Client()
    sheet = client.get("/api/sheet").json()["deeds"]
    older = client.get("/api/deeds").json()
    for payload in (sheet, older):
        text = json.dumps(payload)
        assert not _REF.search(text), text
        assert "witnesses" not in text and "subject" not in text


def test_the_history_writes_a_deed_line(tmp_path):
    """The Journal's running history shows a deed as it happens, with its value, and a
    repeat as not counted: the visible change Sawyer asked for (PA §3). The line is the
    record's own sentence, never "deed.theft"."""
    from play import history as history_mod

    cm, c, pc = _three(tmp_path)
    lines = [l["text"] for d in history_mod.history(c)["days"] for l in d["lines"]]
    assert "A deed: took apple from the fruit seller without asking (−1)." in lines
    assert ("Not counted: took pear from the fruit seller without asking, the same again "
            "that day.") in lines
    assert "A deed: gave pear back to the fruit seller (+1)." in lines
    assert not any("deed." in l for l in lines)


def test_api_deeds_pages_back_twenty_at_a_time(tmp_path):
    """"Show earlier deeds" fetches older rows: newest first, twenty a page, `before`
    the number of the oldest row shown, and `more` until the first is reached."""
    cm, c, _ = _campaign(tmp_path)
    pc = c.scene.pc()
    for i in range(45):
        deeds.record(pc, "deed.trespass", scene=c.scene, minute=i * 24 * 60,
                     subject=f"h{i}", subject_name=f"house {i}")
    c.save()
    client = Client()
    first = client.get("/api/sheet").json()["deeds"]
    assert [r["n"] for r in first["rows"]][:2] == [44, 43] and len(first["rows"]) == 20
    assert first["more"] is True
    page = client.get(f"/api/deeds?before={first['rows'][-1]['n']}").json()
    assert [r["n"] for r in page["rows"]] == list(range(24, 4, -1)) and page["more"]
    last = client.get("/api/deeds?before=5").json()
    assert [r["n"] for r in last["rows"]] == [4, 3, 2, 1, 0] and not last["more"]
    assert client.get("/api/deeds?before=0").json() == {"rows": [], "more": False}
    assert client.get("/api/deeds?before=x").status_code == 400
