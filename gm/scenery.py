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

from . import speech

SHOWN = "shown here"
COMMON = "fits a place like this"
# The three ways a thing is NOT there. A refusal must name which: asked "is it there?"
# with one "not here" answer, the reader refused things it had read (a thrown bucket, a
# torch in its bracket: 2 of the 12 present cases of the first held-out probe, 2026-10-16,
# both "not here" with no quote — the model's answer, not the quote check), and a wrong
# refusal breaks play harder than the old minting did (the coordinator, 2026-10-17). A
# refusal now has to be one of these, each a thing the reader can point at.
# Worded narrowly, for pieces only: as "only if something had broken or happened" the
# reader filed things the narration had TAKEN AWAY under it ("the last apple … the cart is
# bare", the boathooks locked in the shed: 4 of 4 such refusals on the held-out batches,
# 2026-10-17), where the all-words override below then wrongly let them through.
BROKEN = "not here: a piece of something no passage shows broken"
ELSEWHERE = "not here: taken away, gone, far off, or only spoken of or remembered"
WRONG_PLACE = "not here: would not be found in a place like this"
ABSENT = WRONG_PLACE           # the old name, for callers that only ask "refused?"
REFUSALS = (BROKEN, ELSEWHERE, WRONG_PLACE)
ANSWERS = (SHOWN, COMMON, *REFUSALS)

# The most things one turn asks about: a plan reaching for more than this from nowhere is
# a plan conjuring, and the rest stay refused.
MOST = 3

_SYSTEM = (
    "In a role-playing game the player's character reaches for a thing, to pick it up or "
    "to hit somebody with it. Answer one question: is that thing there to be had, going "
    "by the passages the player has read and the kind of place they are in? When in "
    "doubt it is there: a player who has read about a thing must be able to use it.\n"
    "\"shown here\": a passage's narration shows this thing, or the things it is one of, "
    "here where the player is — lying, standing, hanging, set out, thrown down, or in "
    "somebody's hands within reach. Copy the narration's own words into \"quote\".\n"
    "\"fits a place like this\": no passage shows it, but a place of this kind would "
    "plausibly have one to hand without anything having to happen first — a stone on a "
    "road, a stool in a tavern, a hammer in a smithy. quote is \"\".\n"
    "Refuse only when it is clearly not there, and say why:\n"
    "\"" + BROKEN + "\": a piece, shard, splinter or fragment of something that no "
    "passage shows broken.\n"
    "\"" + ELSEWHERE + "\": a passage says it was carried off, cleared away, locked up, "
    "used up or taken out of sight, or has it only far off across the place, somewhere "
    "else, in somebody's speech or in a memory.\n"
    "\"" + WRONG_PLACE + "\": no passage shows it and a place of this kind would not "
    "have one lying about — a sword in a wood, a crossbow in a tavern.")

_DEMOS = [
    ("the fish market (a town street, square or market)",
     "The fishwife's stall is stacked with clay pots and baskets of eels. She eyes you "
     "over the counter. 'Buy or move on,' she says.",
     "a clay pot", {"answer": SHOWN, "quote": "stacked with clay pots"}),
    ("the fish market (a town street, square or market)",
     "The fishwife's stall is stacked with clay pots and baskets of eels. She eyes you "
     "over the counter. 'Buy or move on,' she says.",
     "a shard of a broken pot", {"answer": BROKEN, "quote": ""}),
    ("the river road (open country)",
     "The road winds on between the hedgerows, rutted and dry. The carter has pulled up "
     "his mule and is watching you with his hand on his knife.",
     "a stone", {"answer": COMMON, "quote": ""}),
    ("the toll house (inside a building)",
     "The clerk slams the ledger shut and stands. 'You'll get nothing here,' he says, "
     "'not a coin, and not the iron bar my brother keeps behind the door either.'",
     "the iron bar", {"answer": ELSEWHERE, "quote": ""}),
    ("the river road (open country)",
     "The carter heaves the last sack of meal onto his wagon and drives off round the "
     "bend.",
     "a sack of meal", {"answer": ELSEWHERE, "quote": ""}),
    ("the toll house (inside a building)",
     "The clerk slams the ledger shut and stands, his chair grinding back on the boards.",
     "a pitchfork", {"answer": WRONG_PLACE, "quote": ""}),
]


def _user(place: str, passages: str, thing: str) -> str:
    return (f"The player is at: {place}\n\nWhat the player has read here:\n{passages}\n\n"
            f"The thing: {thing}")


def where_said(place: str, kinds=()) -> str:
    """The place as the reader is told it: its name and the kinds of place it truly is
    (`places.settings_for`), so "would a place like this have one" has a place to ask of."""
    kinds = [str(k) for k in kinds or () if k]
    return f"{place} ({'; '.join(kinds)})" if kinds else place


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


def decide(place: str, kinds, passages: list[str], thing: str, *, ask_fn=None,
           cfg: dict | None = None) -> dict:
    """The verdict on one thing: {"answer", "quote", "ledger", "origin", "why"}."""
    texts = [str(t) for t in passages if str(t or "").strip()]
    shown = "\n\n".join(texts) or "(nothing yet)"
    said = where_said(place, kinds)
    if ask_fn is None:
        answer, quote = ask(said, shown, thing, cfg=cfg)
    else:
        answer, quote = ask_fn(said, shown, thing)
    out = {"answer": answer or "unread", "quote": quote, "ledger": False, "origin": "",
           "why": ""}
    if answer == SHOWN and not _quoted_on(quote, texts):
        # Biased toward allowing (the coordinator, 2026-10-17): the reader said the thing
        # is there, and a quote that paraphrases, joins two sentences or picks up a word of
        # speech is not a reason to refuse it. It is ledgered as fitting the place, not as
        # narrated, and the row says the quote missed. The refusal stays for the answers
        # that name why a thing is not there.
        out["why"] = "the quote is not the narration the player read; kept as fitting"
        answer = COMMON
    if answer in (BROKEN, WRONG_PLACE) and _named_on(thing, texts):
        # A refusal that the thing was never shown, or exists only if something broke, of
        # a thing whose every word is in the narration the player read. Measured on the
        # held-out set (2026-10-17): "The fishwife hurls a bucket of eel water at your
        # feet" came back "only if something had broken or happened" for "the bucket", 2
        # runs of 2. A narrow second read was tried and dropped: asked "is the bucket here,
        # where you could take hold of it?" gemma said no while writing "At your feet" as
        # where it was (the best of three wordings 6/8 on eight probe sentences, and wrong
        # on the bucket every time). So the player's own words for the thing are compared
        # with the page instead — every word, so "a shard of the broken pot" beside a pot
        # that "rocks but holds" stays refused ("shard" and "broken" are not on the page)
        # while "the bucket" beside "a bucket of eel water" is not. Words compared, never
        # English read; it can only ALLOW, and `ELSEWHERE` — a named thing that is gone or
        # only spoken of — is never overruled.
        out["why"] = f"refused as {answer!r}, but every word of it is on the page"
        answer = SHOWN
    if answer in (SHOWN, COMMON):
        out["ledger"] = True
        out["origin"] = "narrated" if answer == SHOWN else "commonplace"
    return out


def _named_on(thing: str, texts: list[str]) -> bool:
    """Whether every word of the thing's name, its article and "of" aside, is a word of the
    narration (speech blanked), a plural `s` forgiven as `holding.same` forgives it."""
    from rules import holding

    from . import beat_verify as bv

    own = [w for w in bv._norm(holding.plain(thing)).split()
           if w not in ("of", "the", "a", "an", "some", "one")]
    if not own:
        return False
    page = set()
    for t in texts:
        page |= {w.rstrip("s") for w in bv._norm(speech.unquoted(t)).split()}
    return all(w.rstrip("s") in page for w in own)


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


def ground(raw, engine, passages: list[str], *, ask_fn=None, skip=()) -> list[dict]:
    """Ledger what the plan reaches for that the narration showed or the place plainly
    holds; one row per thing asked, for the turn log. Nothing is asked with no `ask_fn`
    (the reader off) or nothing to ask about, and nothing in `skip` (asked already this
    turn) is asked again."""
    if ask_fn is None:
        return _picked(raw, engine)
    things = [t for t in reached_for(raw, engine) if t not in set(skip or ())]
    if not things:
        return _picked(raw, engine)
    scene = engine.scene
    kinds: tuple = ()
    try:
        from rules import places as places_mod

        here = engine.here()
        place = str(getattr(here, "name", "") or "") or "here"
        known = tuple(engine.places()) + tuple(engine.open_ground())
        kinds = tuple(sorted(places_mod.settings_for(here, known))) if here else ()
    except Exception:  # noqa: BLE001
        place = "here"
    rows: list[dict] = []
    for thing in things:
        verdict = decide(place, kinds, passages, thing, ask_fn=ask_fn)
        row = {"kind": "scenery", "thing": thing, "answer": verdict["answer"],
               **({"quote": verdict["quote"]} if verdict["quote"] else {}),
               **({"note": verdict["why"]} if verdict["why"] else {})}
        if verdict["ledger"]:
            rec = scene.place_prop(thing, state="intact",
                                   turn=int(getattr(scene, "clock_minutes", 0) or 0))
            rec["origin"] = verdict["origin"]
            if verdict["origin"] == "narrated":
                rec["quote"] = verdict["quote"]
            row["ledgered"] = True
        rows.append(row)
    return rows + _picked(raw, engine)
