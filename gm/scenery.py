"""Scenery becomes a thing when the player reaches for it: ledgered from the narration that
showed it, or refused.

Measured 2026-10-16 (a real player's 0.2.19 game, a market fight, free narrator): the page
wrote a dagger "clattering against a clay pot … the pot shatters into shards that spray
outward" when nothing in the engine broke anything, and then "a heavy wooden crate sits
partially overturned, its contents of iron nails" — scenery nobody had recorded, changing
state in prose. "I grab a shard of the broken pot and stab him" then minted the shard from
nowhere (`Engine._op_give`'s old "the world never runs out") and swung it as an improvised
weapon (`params.item` had no prop behind it). The same report's "I pick up the hairball
and hurl it" was a thing the narrator HAD put on the floor, and the player was right to
reach for it.

What the traditions do (sources: Inform 7, Writing with Inform §3.8-3.9 and the Inform 7
Handbook's scenery chapter; TADS 3 adv3 library reference, `Decoration`, `Distant`,
`Unthing`; CircleMUD building guide §3; Fate Core SRD, "Setting the Scene", "The Four
Actions", "Fate Points"; Fate Condensed changelog 2020-05-06; arXiv 2505.03547):

  * a look-only tier between "not there" and "a real object" — Inform's scenery and
    backdrops, TADS 3's `Decoration` ("isn't important") and `Distant`, Diku's extra
    descriptions — which can be described and never change state;
  * Fate: what the GM described is established and usable ("poorly lit" can be invoked
    without an aspect), a state change needs an action ("the barn doesn't catch On Fire!
    without someone kicking over the lantern"), and Fate Condensed's revised rule for a
    declared detail — free when it follows from what is established, paid for when it is
    a stretch;
  * STORY2GAME (arXiv 2505.03547) creates objects on demand, and its commonest failure was
    duplicate referents ("Key" vs "Metallic Key") — so a thing is ledgered once, by the
    player's own name for it, and found again by `Scene.prop_on_the_ground` thereafter.

So: the engine refuses a pick-up or an improvised weapon with no record
(`Engine._picked_from_nowhere`, `Engine._improvised_unheld`), and this step runs before
the plan does. For each thing the plan reaches for that nothing records
(`Engine.unrecorded_thing`), ONE closed question is asked of the passages the player has
read here: is it "shown here" (quoted, and the quote checked in code to be the page's own
narration, speech blanked), "commonplace here" (no passage shows it, but a place of this
kind plainly has one loose: a stone on a road), or "not here". Shown or commonplace, it is
ledgered at the party's spot through the one door (`Scene.place_prop`), intact, with how
it came to be on the record (`origin`, `quote`) — the way a person the beat shows is given
a body (play/aftermath/seen_people.py). Not here, the engine's refusal stands.

What this does NOT do: it does not read every beat for scenery (a call per beat for a
rare need), and it does not judge a narrated state change — the shattered pot itself is
the read-back's to catch, not this step's. A shard of a pot shown shattering on a page the
player read is "shown here": what the player saw is what is there, the owner's rule for
people (2026-10-01) applied to things. A shard of a pot no page broke is not.

Off in the test suite with the interpreter (`interpret.ENABLED`): with no answer, nothing is
ledgered, and the engine's refusal stands.
"""
from __future__ import annotations

import json

SHOWN = "shown here"
COMMON = "commonplace here"
ABSENT = "not here"
ANSWERS = (SHOWN, COMMON, ABSENT)

# The most things one turn asks about: a plan reaching for more than this from nowhere is
# a plan conjuring, and the rest stay refused.
MOST = 3

_SYSTEM = (
    "In a role-playing game the player's character reaches for a thing, to pick it up or "
    "to hit somebody with it. Answer one question: is that thing there to be had, going "
    "by the passages the player has read and the kind of place they are in?\n"
    "\"shown here\": a passage's narration shows this thing here, where the player is, in "
    "the state the player names it — copy the narration's own words into \"quote\".\n"
    "\"commonplace here\": no passage shows it, but any place of this kind plainly has one "
    "lying loose to hand — a stone on a road, a stick in a wood. quote is \"\".\n"
    "\"not here\": neither. A piece, shard or splinter of something is shown only when a "
    "passage shows that thing broken. A thing only spoken of in quotation marks, "
    "remembered, or seen far off is not here.")

_DEMOS = [
    ("the fish market",
     "The fishwife's stall is stacked with clay pots and baskets of eels. She eyes you "
     "over the counter. 'Buy or move on,' she says.",
     "a clay pot", {"answer": SHOWN, "quote": "stacked with clay pots"}),
    ("the fish market",
     "The fishwife's stall is stacked with clay pots and baskets of eels. She eyes you "
     "over the counter. 'Buy or move on,' she says.",
     "a shard of a broken pot", {"answer": ABSENT, "quote": ""}),
    ("the river road",
     "The road winds on between the hedgerows, rutted and dry. The carter has pulled up "
     "his mule and is watching you with his hand on his knife.",
     "a stone", {"answer": COMMON, "quote": ""}),
    ("the toll house",
     "The clerk slams the ledger shut and stands. 'You'll get nothing here,' he says, "
     "'not a coin, and not the iron bar my brother keeps behind the door either.'",
     "the iron bar", {"answer": ABSENT, "quote": ""}),
]


def _user(place: str, passages: str, thing: str) -> str:
    return (f"The player is at: {place}\n\nWhat the player has read here:\n{passages}\n\n"
            f"The thing: {thing}")


def messages(place: str, passages: str, thing: str) -> list[dict]:
    out = [{"role": "system", "content": _SYSTEM}]
    for at, said, what, answer in _DEMOS:
        out.append({"role": "user", "content": _user(at, said, what)})
        out.append({"role": "assistant", "content": json.dumps(answer)})
    out.append({"role": "user", "content": _user(place, passages, thing)})
    return out


SCHEMA = {"type": "object", "properties": {
    "answer": {"type": "string", "enum": list(ANSWERS)}, "quote": {"type": "string"}},
    "required": ["answer", "quote"]}


def ask(place: str, passages: str, thing: str, *, chat=None, cfg: dict | None = None
        ) -> tuple[str, str]:
    """(one of `ANSWERS`, the quote) — ("", "") when the call fails, which ledgers
    nothing: the engine's refusal then stands, as it does with the reader off."""
    if chat is None:
        from . import client

        chat = client.chat
    if cfg is None:
        from play import modelcfg

        cfg = modelcfg.for_role("interpreter")
        if not cfg.get("model"):
            cfg = modelcfg.for_role("narrator")
    try:
        reply = chat(messages(place, passages, thing), cfg.get("model"), cfg.get("host"),
                     as_json=True, think=False, temperature=0.0, num_predict=120,
                     provider=cfg.get("provider", "ollama"), api_key=cfg.get("api_key", ""),
                     schema=SCHEMA)
        got = reply.json() or {}
    except Exception:  # noqa: BLE001 — unasked is not here: the engine's refusal stands
        return "", ""
    answer = str(got.get("answer") or "")
    return (answer if answer in ANSWERS else ""), str(got.get("quote") or "")


# --- what the plan reaches for ----------------------------------------------------------------

def _pc_refs(scene) -> set[str]:
    pc = scene.pc() if hasattr(scene, "pc") else None
    return {str(getattr(pc, "ref", "pc") or "pc"), "pc", "you", "player"}


def reached_for(raw, engine) -> list[str]:
    """The things this plan has the player take from nowhere or swing as an improvised
    weapon that nothing records (`Engine.unrecorded_thing`), in the plan's order, once
    each. A give with a giver or a container is a hand-over the engine answers itself."""
    scene = engine.scene
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None or not isinstance(raw, list):
        return []
    mine = _pc_refs(scene)
    out: list[str] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        op = str(r.get("op") or "").lower()
        p = r.get("params") or {}
        actor = str(r.get("actor") or pc.ref)
        if op == "give":
            to = str(p.get("to") or r.get("target") or actor)
            if to not in mine or p.get("from_") or actor not in mine:
                continue
            item = " ".join(str(p.get("item") or "").split())
        elif op == "attack" and str(p.get("weapon") or "").lower() == "improvised":
            if actor not in mine:
                continue
            item = " ".join(str(p.get("item") or "").split())
        elif op == "attack" and str(p.get("manoeuvre") or "").lower() == "steal" \
                and not _foe_carries(engine, r, p):
            # In a fight a take naming no holder is built as a Steal at the foe
            # (`acts_to_ops._take`); a thing the foe does not carry is the ground's
            # question, not theirs (`steals_off_the_ground` below).
            if actor not in mine:
                continue
            item = " ".join(str(p.get("item") or "").split())
        else:
            continue
        if item and item not in out and engine.unrecorded_thing(item, pc):
            out.append(item)
    return out[:MOST]


def _foe_carries(engine, r: dict, p: dict) -> bool:
    who = engine.scene.actors.get(str(r.get("target") or ""))
    if who is None:
        return True                       # no foe to ask: the engine's own refusal answers
    return engine._carried_by(who, str(p.get("item") or "")) is not None


def steals_off_the_ground(raw, engine) -> list[str]:
    """A Steal at a foe of a thing the foe does not carry and that lies here on the
    ledger is a pick-up: rewritten, in place, as the `give` it is. Returns the things.

    In a fight "I grab a shard of the broken pot" names no holder, and the act table
    builds a Steal at the foe the player is locked with (`acts_to_ops._take`, right for
    "I take what he was carrying", 2026-10-09). The shard is not in her hands: it is on
    the ground, and stooping for it is a pick-up, which provokes by its own rule."""
    pc = engine.scene.pc() if hasattr(engine.scene, "pc") else None
    if pc is None or not isinstance(raw, list):
        return []
    mine = _pc_refs(engine.scene)
    out: list[str] = []
    for i, r in enumerate(raw):
        if not isinstance(r, dict) or str(r.get("op") or "").lower() != "attack":
            continue
        p = r.get("params") or {}
        if str(p.get("manoeuvre") or "").lower() != "steal" \
                or str(r.get("actor") or pc.ref) not in mine or _foe_carries(engine, r, p):
            continue
        item = " ".join(str(p.get("item") or "").split())
        rec = engine.scene.prop_on_the_ground(item) if item else None
        if rec is None:
            continue
        raw[i] = {"op": "give", "actor": pc.ref, "because": "the player picked it up",
                  "params": {"item": str(rec.get("name") or item), "to": pc.ref}}
        out.append(item)
    return out


def _picked(raw, engine) -> list[dict]:
    return [{"kind": "scenery", "thing": t, "answer": "on the ground", "picked_up": True}
            for t in steals_off_the_ground(raw, engine)]


def _quoted_on(quote: str, passages: list[str]) -> bool:
    """Whether the quote is the narration of one of the passages, speech blanked — the
    read-back's own test (`beat_verify.place_quote`). Not its three-word floor: that guards
    a claim about what HAPPENED read off one word ("the exchange" as a sale), and this is
    a question about whether a noun is on the page at all — the probe's own right answers
    were "hairball" and "iron nails" (2026-10-16)."""
    from . import beat_verify as bv

    return any(bv.place_quote(quote, bv._sentences(text)) for text in passages)


def ground(raw, engine, passages: list[str], *, ask_fn=None) -> list[dict]:
    """Ledger what the plan reaches for that the narration showed or the place plainly
    holds; one row per thing asked, for the turn log. Nothing is asked with no `ask_fn`
    (the reader off) or nothing to ask about."""
    if ask_fn is None:
        return _picked(raw, engine)
    things = reached_for(raw, engine)
    if not things:
        return _picked(raw, engine)
    scene = engine.scene
    try:
        here = engine.here()
        place = str(getattr(here, "name", "") or "") or "here"
    except Exception:  # noqa: BLE001
        place = "here"
    texts = [str(t) for t in passages if str(t or "").strip()]
    shown = "\n\n".join(texts) or "(nothing yet)"
    rows: list[dict] = []
    for thing in things:
        answer, quote = ask_fn(place, shown, thing)
        row = {"kind": "scenery", "thing": thing, "answer": answer or "unread",
               **({"quote": quote} if quote else {})}
        if answer == SHOWN and not _quoted_on(quote, texts):
            # A thing "shown" in words that are not the page's narration is a reader
            # leaning on its own guess: not ledgered (the read-back's quote rule).
            row["dropped"] = "the quote is not the narration the player read"
            answer = ABSENT
        if answer in (SHOWN, COMMON):
            rec = scene.place_prop(thing, state="intact",
                                   turn=int(getattr(scene, "clock_minutes", 0) or 0))
            rec["origin"] = "narrated" if answer == SHOWN else "commonplace"
            if answer == SHOWN:
                rec["quote"] = quote
            row["ledgered"] = True
        rows.append(row)
    return rows + _picked(raw, engine)
