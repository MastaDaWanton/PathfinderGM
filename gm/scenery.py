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
# Two more ways, both from the owner's 0.2.25 report (2026-11-01), each a thing that is in
# the world and is still never a loose thing to pick up:
#   * a plant growing in the land. "pick the chaSMIER LEAF" was answered "shown here" with
#     the quote "The rare Chasmyre Leaf grows among the tangled roots and stagnant waters
#     of the marsh." — a sentence about where the herb grows, written by the planned
#     narrator's thread slot. The quote was the page's own, so it passed, the leaf was
#     ledgered, and the give took it: any herb the prose mentioned could be had with no
#     forage roll. Herbs come out of the ground by foraging and out of a carcass by
#     harvesting, never off the page.
#   * a body. "loot the body" was read as a take of the thing "body", answered "shown
#     here" off a sentence about the grub's jaws, and the give put `"body": 1` in the
#     pack. A dead creature's body is where its loot is, not goods (`_bodies_looted`).
GROWING = "not here: a plant growing in the land, had only by foraging for it"
BODY = "a body: the body, corpse or remains of a person or creature"
REFUSALS = (BROKEN, ELSEWHERE, WRONG_PLACE, GROWING)
# The fourth way: the thing is the player's already, because the engine put it in their pack
# here and the page described it. Measured on the owner's 0.2.21 report (2026-10-27): the
# engine paid a grioth's guarded find into the satchel, the planned beat wrote "you find a
# bundle of herbs — 18 Monkshood, 18 Caranator, and 12 Coldwood — left behind in its wake",
# and "I take the bundle of herbs" was read "shown here" — true of the page — and ledgered,
# and the give minted `"bundle of herbs": 1` beside the 48 herbs it described. The reader
# could not have answered otherwise: it was never told what the player had been given. It
# is now (`Engine.granted_here`), and it names WHICH grant (`given`, an enum Ollama's
# grammar holds); code checks the number is one it was shown. Offered only when there is a
# grant to name, so a reader with nothing given here cannot answer it.
ALREADY = "already the player's: the game put it in their pack"
ANSWERS = (SHOWN, COMMON, *REFUSALS, BODY, ALREADY)

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
    "somebody's hands within reach. Copy the narration's own words into \"quote\". A "
    "passage that only says what grows or is found in this land, or what a place is "
    "known for, shows nothing lying here.\n"
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
    "have one lying about — a sword in a wood, a crossbow in a tavern.\n"
    "\"" + GROWING + "\": a herb, leaf, flower, root, berry, mushroom or other plant "
    "still growing here or in this land: picking it is foraging, not picking up a thing.\n"
    "\"" + BODY + "\": the thing is a body, corpse, carcass or remains of somebody or "
    "some creature.\n"
    "When the player has been given things here, they are listed, numbered:\n"
    "\"" + ALREADY + "\": the thing is one of those, or holds them, or is made of them — "
    "the passages describing what the player was given, however they put it. Put its "
    "number in \"given\". Only for a thing that IS what was given: anything else the "
    "passages show is answered as above, and \"given\" is \"\".")

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
    # A sentence about what grows in the land is not a thing lying here (the owner's
    # 0.2.25 report: "The rare Chasmyre Leaf grows among the tangled roots…" ledgered a
    # leaf). Neither demonstration's words are the report's.
    ("the fen (open country)",
     "Mist hangs over the fen. Bitterwort is said to grow along these banks, though few "
     "who come looking find it.",
     "the bitterwort", {"answer": GROWING, "quote": ""}),
    ("the old orchard (open country)",
     "A dead wolf lies in the long grass where it fell, its pelt matted with blood.",
     "the wolf's body", {"answer": BODY, "quote": ""}),
    # Given things listed: the page's own words for what the game put in the pack are that,
    # and a thing beside it on the same page is still answered as scenery.
    ("the old quarry (open country)",
     "The wolf slinks off into the scrub. Where it lay you find a sack of grey rock salt, "
     "left behind on the stones.",
     "the sack of salt", {"answer": ALREADY, "quote": "", "given": "2"},
     ("the herbs Arlo gathered: 4× Sukake", "the salt the wolf held: 6× Rock Salt")),
    ("the old quarry (open country)",
     "The wolf slinks off into the scrub. A pick handle, split and grey, lies across the "
     "path where the wolf lay.",
     "the pick handle", {"answer": SHOWN, "quote": "A pick handle, split and grey, lies "
                                                   "across the path", "given": ""},
     ("the salt the wolf held: 6× Rock Salt",)),
]


def _user(place: str, passages: str, thing: str, given=()) -> str:
    listed = ""
    if given:
        listed = ("\n\nGiven to the player here, already in their pack:\n"
                  + "\n".join(f"({i}) {g}" for i, g in enumerate(given, 1)))
    return (f"The player is at: {place}\n\nWhat the player has read here:\n{passages}"
            f"{listed}\n\nThe thing: {thing}")


def where_said(place: str, kinds=()) -> str:
    """The place as the reader is told it: its name and the kinds of place it truly is
    (`places.settings_for`), so "would a place like this have one" has a place to ask of."""
    kinds = [str(k) for k in kinds or () if k]
    return f"{place} ({'; '.join(kinds)})" if kinds else place


def messages(place: str, passages: str, thing: str, given=()) -> list[dict]:
    out = [{"role": "system", "content": _SYSTEM}]
    for demo in _DEMOS:
        at, said, what, answer = demo[:4]
        shown_given = demo[4] if len(demo) > 4 else ()
        answer = dict(answer)
        if not given:
            # With nothing given, the demonstrations that list a grant still show it, but
            # no answer carries a `given` the call's own schema will not have.
            answer.pop("given", None)
        else:
            answer.setdefault("given", "")
        out.append({"role": "user", "content": _user(at, said, what, shown_given)})
        out.append({"role": "assistant", "content": json.dumps(answer)})
    out.append({"role": "user", "content": _user(place, passages, thing, given)})
    return out


SCHEMA = {"type": "object", "properties": {
    "answer": {"type": "string", "enum": list(ANSWERS)}, "quote": {"type": "string"}},
    "required": ["answer", "quote"]}


def schema_for(given=()) -> dict:
    """The call's grammar: `ALREADY` and its `given` number only when something was given
    here — a reader shown no grant cannot answer that it is one."""
    if not given:
        return {"type": "object", "properties": {
            "answer": {"type": "string", "enum": [a for a in ANSWERS if a != ALREADY]},
            "quote": {"type": "string"}}, "required": ["answer", "quote"]}
    return {"type": "object", "properties": {
        "answer": {"type": "string", "enum": list(ANSWERS)}, "quote": {"type": "string"},
        "given": {"type": "string",
                  "enum": [""] + [str(i) for i in range(1, len(given) + 1)]}},
        "required": ["answer", "quote", "given"]}


def ask(place: str, passages: str, thing: str, given=(), *, chat=None,
        cfg: dict | None = None) -> tuple:
    """(one of `ANSWERS`, the quote, the grant's number or "") — ("", "", "") when the
    call fails, which ledgers nothing: the engine's refusal then stands, as it does with
    the reader off."""
    if chat is None:
        from . import client

        chat = client.chat
    if cfg is None:
        from play import modelcfg

        cfg = modelcfg.for_role("interpreter")
        if not cfg.get("model"):
            cfg = modelcfg.for_role("narrator")
    try:
        reply = chat(messages(place, passages, thing, given), cfg.get("model"),
                     cfg.get("host"), as_json=True, think=False, temperature=0.0,
                     num_predict=140, provider=cfg.get("provider", "ollama"),
                     api_key=cfg.get("api_key", ""), schema=schema_for(given))
        got = reply.json() or {}
    except Exception:  # noqa: BLE001 — unasked is not here: the engine's refusal stands
        return "", "", ""
    answer = str(got.get("answer") or "")
    if answer == ALREADY and not given:
        answer = ""
    return ((answer if answer in ANSWERS else ""), str(got.get("quote") or ""),
            str(got.get("given") or ""))


def decide(place: str, kinds, passages: list[str], thing: str, *, ask_fn=None,
           cfg: dict | None = None, given=()) -> dict:
    """The verdict on one thing: {"answer", "quote", "ledger", "origin", "why", "given"}
    — `given` the index into `given` of the grant it is, or None."""
    texts = [str(t) for t in passages if str(t or "").strip()]
    shown = "\n\n".join(texts) or "(nothing yet)"
    said = where_said(place, kinds)
    given = tuple(given or ())
    if ask_fn is None:
        got = ask(said, shown, thing, given, cfg=cfg)
    else:
        got = ask_fn(said, shown, thing, given) if given else ask_fn(said, shown, thing)
    answer, quote = got[0], got[1]
    which = str(got[2]) if len(got) > 2 else ""
    out = {"answer": answer or "unread", "quote": quote, "ledger": False, "origin": "",
           "why": "", "given": None, "body": answer == BODY}
    herb = growing_herb(thing)
    if herb and answer not in (ALREADY, BODY):
        # Checked in code whatever the reader said: a name off the herbalist's own
        # catalogue is a plant, and a plant is foraged (`Engine._gather`) or harvested,
        # never picked up off a page. Near names count — the player typed "chasmier"
        # for the catalogue's Chasmyre, which `ingredients.by_name` (deliberately exact,
        # for the satchel) does not match, so the give minted a goods line "chasmier
        # leaf". Names compared against a closed catalogue, never English read.
        out["answer"] = GROWING
        out["why"] = f"{herb} is a plant: foraged, never picked up"
        return out
    if answer == BODY:
        return out
    if answer == ALREADY:
        # The number checked against what was shown: one grant needs no number, and a
        # number that names nothing shown is no answer — nothing is ledgered, so nothing
        # is minted, and the engine's own refusal stands.
        if which.isdigit() and 1 <= int(which) <= len(given):
            out["given"] = int(which) - 1
        elif len(given) == 1:
            out["given"] = 0
        else:
            out["answer"] = "unread"
            out["why"] = f"answered as given, naming {which!r} of {len(given)}"
        return out
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


def growing_herb(thing: str) -> str:
    """The catalogue name of the plant the player's words name, or "": a herb or fungus
    off the ingredient list (`ingredients.all_ingredients`, the forageable kinds), by its
    name or a near spelling of it. Near is a ratio of 0.84 on the whole name (difflib's
    SequenceMatcher): "chasmier leaf" against "Chasmyre Leaf" is 0.85, while "a stool"
    against "Stoolcap" (0.77) and "a rose" against "rope" are not near enough. Only
    plants: a monster part is harvested, not foraged (a herb that is also a salve base,
    Marsh-Mallow's root, is still a plant)."""
    from difflib import SequenceMatcher

    from rules import holding, ingredients

    def norm(text) -> str:
        return " ".join(str(text or "").lower().replace("-", " ").split())

    said = norm(holding.plain(str(thing or "")))
    if not said:
        return ""
    plants = [i for i in ingredients.all_ingredients().values()
              if (i.forageable or str(i.kind or "") in ("herb", "fungus"))
              and str(i.kind or "") not in ("monster part", "poison")]
    # The whole name against the whole name, never a name found inside the words:
    # `ingredients.by_name` would answer "an oak branch" with the herb Oak, and a branch
    # picked up to swing is scenery.
    best, score = "", 0.0
    for ing in plants:
        for k, name in enumerate([ing.name, *str(ing.aka or "").split(",")]):
            name = norm(name)
            if not name:
                continue
            # A herb's own name outranks another's alias for it on a tie.
            r = SequenceMatcher(None, said, name).ratio() - (0.001 if k else 0.0)
            if r > score:
                best, score = ing.name, r
    return best if score >= 0.84 else ""


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


def body_meant(engine, words: str = "") -> str:
    """`fallen_meant` of the engine's scene."""
    return fallen_meant(engine.scene, words)


def fallen_meant(scene, words: str = "") -> str:
    """The ref of the fallen body a take or loot means, or "": somebody down or dead here
    whom the words name (`scope.in_the_room`, which knows the fallen too), else the one
    body lying here, else the body nearest the player on the map. The engine's own
    finders and state; the words are never read for what they mean."""
    from rules import scope

    actors = getattr(scene, "actors", {}) or {}
    bodies = [r for r, a in actors.items() if not a.is_pc and a.is_down]
    if not bodies:
        return ""
    if words:
        named = scope.in_the_room(scene, words)
        if named in bodies:
            return named
    if len(bodies) == 1:
        return bodies[0]
    pc = scene.pc() if hasattr(scene, "pc") else None
    pos = getattr(scene, "positions", {}) or {}
    if pc is not None and pc.ref in pos:
        px, py = pos[pc.ref][:2]

        def gap(r):
            x, y = (pos.get(r) or (px + 999, py))[:2]
            return max(abs(x - px), abs(y - py))
        return min(bodies, key=gap)
    return bodies[0]


def _names_the_fallen(engine, thing: str) -> bool:
    """Whether the words name somebody down or dead here (`scope.in_the_room`)."""
    from rules import scope

    scene = engine.scene
    ref = scope.in_the_room(scene, thing)
    who = (getattr(scene, "actors", {}) or {}).get(ref) if ref else None
    return who is not None and not who.is_pc and who.is_down


def _bodies_looted(raw, engine, thing: str) -> str:
    """Every give in the plan that takes `thing` — a body — rewritten in place as the
    `loot` of the body meant (`body_meant`). Returns the body's ref, "" when nobody lies
    here (the give is then dropped: there is no body to take and nothing to mint)."""
    ref = body_meant(engine, thing)
    for i, r in enumerate(list(raw)):
        if not isinstance(r, dict) or str(r.get("op") or "").lower() != "give":
            continue
        p = r.get("params") or {}
        if " ".join(str(p.get("item") or "").split()) != thing:
            continue
        if ref:
            raw[i] = {"op": "loot", "actor": r.get("actor") or "pc",
                      "because": "the player searches the body",
                      "params": {"from_": ref}}
        else:
            raw[i] = {"op": "narrate_only", "actor": None,
                      "because": "there is no body here to take"}
    # A loot the plan already had of the same body is the same deed: kept once.
    seen = False
    for i in range(len(raw) - 1, -1, -1):
        r = raw[i]
        if isinstance(r, dict) and str(r.get("op") or "").lower() == "loot" \
                and str((r.get("params") or {}).get("from_") or "") == ref and ref:
            if seen:
                del raw[i]
            seen = True
    return ref


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
    # What the engine has put in the player's pack here (`Engine.granted_here`), said as
    # the satchel holds it now: the page may be describing exactly these.
    pc = scene.pc() if hasattr(scene, "pc") else None
    grants, given = [], []
    for rec in (engine.granted_here(pc) if hasattr(engine, "granted_here") else []):
        held = engine.granted_line(pc, rec)
        if held:
            grants.append(rec)
            given.append(f"{rec.get('name')}: {held}")
    rows: list[dict] = []
    for thing in things:
        verdict = decide(place, kinds, passages, thing, ask_fn=ask_fn, given=given)
        if not verdict["body"] and _names_the_fallen(engine, thing):
            # The thing is somebody lying here, by the engine's own finder — "the grub",
            # "Lila's body" — whatever the reader answered: never goods.
            verdict.update(body=True, ledger=False, answer=BODY,
                           why="the words name somebody lying here")
        row = {"kind": "scenery", "thing": thing, "answer": verdict["answer"],
               **({"quote": verdict["quote"]} if verdict["quote"] else {}),
               **({"note": verdict["why"]} if verdict["why"] else {})}
        if verdict["body"]:
            # Not ledgered and never goods: the take becomes the loot of the body meant.
            ref = _bodies_looted(raw, engine, thing)
            row["looted"] = ref or ""
        elif verdict["given"] is not None:
            # Not ledgered: it is the grant, under the page's name for it, and the take
            # is answered "already in the pack" (`Engine._already_carried`).
            rec = grants[verdict["given"]]
            engine.known_as(rec, thing)
            row["already"] = str(rec.get("name") or "")
        elif verdict["ledger"]:
            rec = scene.place_prop(thing, state="intact",
                                   turn=int(getattr(scene, "clock_minutes", 0) or 0))
            rec["origin"] = verdict["origin"]
            if verdict["origin"] == "narrated":
                rec["quote"] = verdict["quote"]
            row["ledgered"] = True
        rows.append(row)
    return rows + _picked(raw, engine)
