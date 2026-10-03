"""Everybody the beat showed here is in the scene as a full person (owner's ruling, 2026-10-01),
and somebody only spoken of is a record — as the beat reader read them (gm/beat_reader.py).

"show described people in the scene. if i can see them they should be in the scene as a
fully made person ready to be interacted with and saved if not already existing." Measured
on the owner's save, the turn that made the ruling: "At the top of the stairs, a figure is
silhouetted … It is a woman" left her a population record and nothing more, and every
"her" after it went to the only woman the engine held, in another room.

**Who is new, and whether they are here, is the reader's answer, not a regex's.** Until
2026-10-03 this step's people came from `note_cast`'s phrase finder and
`judgement.seen_in_beat`'s cue words, with `only_a_predicate` beside them. That day alone:
"He is a large man" made a second smith (c15), who then joined the conversation; a quoted
player line became a person called `say "just trying…"` (c4); "a merchant with a heavy
pack … walks a pace beside you … and moves on" was given a body at the docks (c8). Each
needed one more rule (docs/beat-reader.md). Now each person mention is answered from a
closed list — somebody here, "new", "same as" an earlier newcomer, or nobody — and each
newcomer "here" or "elsewhere", with the page's own words for them (checked to be on the
page). This step only applies that:

  * **here** — a population record at the party's place, marked shown, then a body through
    the one door (`judgement.embody_seen` → `embody` → `population.embody` → `Scene.add`,
    a square with it), which keeps its own limits: no bodies in a fight, at most
    `SEEN_CAP` a beat, a known person walked in rather than made twice, a householder for
    a vague figure in their own house;
  * **elsewhere** — a record with no place, heard from the one person talking (the woman
    who lives "three streets over" is not in the tavern);
  * somebody heard of a moment ago whom these words describe is that record, not a second
    one (`population.heard_of_match`).

And the names the page gives (`Reading.names`), after the bodies, so a newcomer named in
the beat that made them gets the name: each through the engine's checks
(`beat_reader.name_refusal` — nobody else's, not a people of the world, nobody already
named) and `judgement._take_the_name`. That replaced `apply_introductions`' reading of
"'…,' he says" and "The man—Korgath Varn—" by pattern.

No reading (the call failed, or the reader is off) makes nobody and names nobody: nothing
here falls back to the patterns it replaced, and the row says the beat went unread.
"""
from __future__ import annotations

STAGE = "people"
ORDER = 10
DOORS = frozenset({"turn", "carry_on"})


def step(ctx) -> list[dict]:
    from gm import beat_reader, judgement
    from rules import names as names_mod
    from rules import population

    reading = ctx.attribution
    if not isinstance(reading, beat_reader.Reading) or not reading.read:
        if isinstance(reading, beat_reader.Reading) and reading.asked:
            return [reading.unread_row("seen_people")]
        return []
    scene, turn, world = ctx.scene, int(ctx.turn or 0), ctx.world
    rows: list[dict] = []
    body = (names_mod.appearance_for(world, scene.location_id, own="")
            if world is not None else "")
    engine = ctx.campaign.engine() if ctx.campaign else None
    for ref in reading.arrived:
        # Somebody the engine holds elsewhere in this town, shown here by the page: they
        # walk in through the engine's door (never `Scene.move` from here — the
        # one-spatial-authority ratchet), not made twice. Not in a fight: the fight's
        # rule is the same for the known as for the new.
        who = (getattr(scene, "people", {}) or {}).get(ref)
        if who is None or engine is None:
            continue
        if getattr(scene, "in_encounter", False):
            rows.append({"kind": "seen-people", "made": "", "same_as": ref,
                         "why": "in a fight the prose brings nobody in"})
            continue
        engine.walk_in(ref)
        theirs = population.of_ref(scene, ref)
        if theirs is not None:
            population.seen(scene, theirs)
        rows.append({"kind": "seen-people", "made": "", "same_as": ref, "walked_in": True})
    claimed: set[str] = set()       # the records this beat's newcomers already are
    for n in reading.newcomers:
        if judgement._plural_role(n.words):
            # A group is no one person with one life (`record_people`'s rule, measured
            # 2026-09-25: "neighboring merchants" rolled a work and a face of their own);
            # a group is the troop door's to make. The reader's answer is checked, not
            # trusted: a "new" on a plural makes nobody.
            rows.append({"kind": "seen-people", "made": "", "phrase": n.words,
                         "why": "a group, not one person"})
            n.where = ""
            continue
        heard = population.heard_of_match(scene, n.words, turn=turn)
        if heard is not None and heard["id"] in claimed:
            heard = None
        if n.where == beat_reader.HERE:
            if heard is not None:
                # Heard of a moment ago and now standing here: the same person, seen.
                heard["spot"] = getattr(scene, "at", None)
                population.seen(scene, heard)
                heard["last_seen"] = int(getattr(scene, "clock_minutes", 0) or 0)
                rec = heard
            else:
                rec = population.note(scene, n.words, turn=turn, body=body)
                if rec["id"] in claimed:
                    # Two newcomers the reader told apart are two people, whatever the
                    # finder's synonyms make of their words: measured writing these
                    # tests, "the drover" beside "a carter in a patched coat" came back
                    # as the carter's record, and the drover never got a body.
                    rec = population.note(scene, n.words, turn=turn, body=body, fresh=True)
            rec["shown"] = turn
            rec["said_as"] = n.words
        elif n.where == beat_reader.ELSEWHERE:
            rec = heard or population.note(scene, n.words, turn=turn, body=body, spot="",
                                           heard_from=judgement._the_one_talking(scene))
        else:
            # The reader named them new and left where unanswered: a record where the
            # party is, and no body — the old door's "neither clearly".
            rec = population.note(scene, n.words, turn=turn, body=body)
        n.record = rec["id"]
        claimed.add(rec["id"])
    rows += judgement.embody_seen(scene, turn=turn, world=world, beat=ctx.text,
                                  engine=engine)
    pop = getattr(scene, "population", {}) or {}
    for n in reading.newcomers:
        rec = pop.get(n.record) or {}
        if rec.get("ref") and rec["ref"] in (getattr(scene, "actors", {}) or {}):
            n.ref = rec["ref"]
    rows += name_them(ctx, reading)
    return rows


def name_them(ctx, reading) -> list[dict]:
    """The names the reader read, through the engine's checks; one row each."""
    from gm import beat_reader, judgement

    scene = ctx.scene
    actors = getattr(scene, "actors", {}) or {}
    rows = []
    for n in reading.names:
        ref = n["who"] if n["who"] in actors else (
            (reading.newcomer(n["who"]) or beat_reader.Newcomer("", [], "", "")).ref)
        if not ref:
            rows.append({"kind": "name-read", "name": n["name"], "taken": False,
                         "why": "a newcomer with no body"})
            continue
        why = beat_reader.name_refusal(scene, ctx.world, ref, n["name"])
        if why:
            rows.append({"kind": "name-read", "ref": ref, "name": n["name"], "taken": False,
                         "why": why})
            continue
        was = str(actors[ref].name)
        judgement._take_the_name(scene, actors[ref], n["name"])
        rows.append({"kind": "name-read", "ref": ref, "was": was, "name": n["name"],
                     "taken": True})
    return rows
