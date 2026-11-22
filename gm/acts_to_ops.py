"""The act→op table: what the reading of the player's sentence commits the engine to.

docs/structured-turn.md, lane F. The owner, 2026-10-03: "we cant really depend i think on
just layering mechanical detection logic on top this will be an endless loop". Every live
bug of that day on the forward side was a regex misreading a sentence the reader
(gm/interpret.py) had read correctly — "…, then tip the coins", a quoted "It's a deal",
"pick the crate back up" — and each fix taught one more regex one more phrasing.

So the reading drives the ops. A model reads; this module validates the reading against
what the engine owns and builds the ops; the engine changes state. It never reads English:
every slot is resolved through the engine's own finders, or it is not resolved at all.

  * people: `scope.in_the_room` (the phrase against the names of who is here); a bare
    pronoun is the one the player is engaged with, talking to, or the only other person
    here — the engine's state, never a guess at the words;
  * things: `holding.key_in` against the pack, the stock shelf by id, base or name, and
    a container by `holding.is_container` (a closed list of nouns, the engine's own);
  * coin: `holding.is_money`, and an amount as a number and a denomination
    (`goods.coin_named`): numbers and a closed vocabulary, which code may check;
  * places: `places.find`, and a heard-of place through `heard_places.named_in`.

Two kinds of row. Most acts owe an op the planner writes the params of (a `travel` to one
of this town's real places, a `say`, a `provoke`): those are op NAMES, joined to the
plan's required `declared` block. The acts that move a thing — take, drop, give, sell —
are built here WHOLE, because their params are exactly what the regexes kept getting wrong
(which way the coin goes, who the buyer is, whether a deal was closed) and the reading's
slots plus the engine's finders settle each of them.

Only what is done or tried NOW moves the engine (`interpret.COMMITS`, round 2): an action
the reading marks intended or asked about makes no row of ops at all. A sale tried is an
offer — ISO 24617-2's Offer, which only an Accept Offer closes — and is never a sale, at a
counter or anywhere else: only an agreement closes it.

Where a slot cannot be resolved, no op is invented: the row says what was not found, and
the turn says so (`refusal`, and the brief's fact line). Prior art: FIREBALL (Zhu et al.,
ACL 2023) — utterance to executable command, with the state in front of it; Wordplay
2024's function-calling GM; "Orchestrated Reality"'s Plan–Diff–Validate–Apply, where a
proposal that fails a check is refused before it commits. TADS 3's verb templates give
the slots each verb takes (`interpret.ACT_SLOTS`); TakeFrom's indirect object is the
holder, person or container alike.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from rules import words as english

# The acts whose ops are built here, whole.
GOODS_ACTS = frozenset({"take", "drop", "give", "sell", "steal"})
# The acts under which coin leaves the player's purse. `rest` was one ("I take a room for
# the night": the act list's own words for it), which let the plan pay for a room with a
# coin `give` at whatever figure the model wrote. The rest door charges the room itself
# now, at the book's price (`Engine._room_bill`, 2026-10-16), so a plan's coin beside a
# rest would be the room paid twice — and a number no model may author.
PAYING_ACTS = frozenset({"give", "buy", "drop"})

_PRONOUNS = frozenset({"him", "her", "them", "he", "she", "they", "his", "their"})
_IT = frozenset({"it", "them", "these", "those", "this", "that"})
# The words for the whole of what a container holds: a quantifier, not a thing's name.
_WHOLE = frozenset({"everything", "contents", "inside", "all", "stuff", "lot", "within"})
_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
            "fifty": 50, "hundred": 100}
_AMOUNT = re.compile(r"^\s*(?:the\s+)?(\d+|" + "|".join(_NUMBERS) + r")\s+(.+?)\s*$", re.I)
# The player's own figure for a sale, as a share of the worth: "at 75% of the crate's
# value". A number, so code may read it; it only ever LOWERS the engine's price
# (`Engine._sell_goods`, `accept`).
_SHARE = re.compile(r"\b(\d{1,3})\s*(?:%|per\s*cent|percent)", re.I)


@dataclass
class Row:
    """One action of the reading, as the engine will carry it."""
    index: int
    act: str
    ops: list[str] = field(default_factory=list)       # op names the plan must carry
    intents: list[dict] = field(default_factory=list)  # ops built here, whole
    missing: str = ""                                   # what the words named and is not here
    note: str = ""                                      # why nothing was built, for the log
    # A walk to a place the engine cannot find: the printable answer `nowhere_to_go` gives
    # when the plan moves nobody either. Not `missing`, which the brief states as "nothing
    # is made to fill it" — the plan may still found the place (places are creatable).
    nowhere: str = ""
    thing: str = ""                                     # a goods row's object, resolved
    commit: str = "done"                                # interpret.COMMITS
    weapon: str = ""                                    # a blow's weapon, resolved (`weapons`)
    # A give of no thing at all ("give him a nod"): the deed is still the player's to show,
    # though nothing changes hands (`narration.moved_nothing`).
    gesture: bool = False
    # A thing the deed handles that is not here or not carried, as the engine's printed
    # answer (`things_not_here`): "Kesst Vayr is not carrying pelts."
    unheld: str = ""

    def record(self) -> dict:
        out = {"act": self.act, "ops": list(self.ops)}
        if self.commit != "done":
            out["commit"] = self.commit
        if self.weapon:
            out["weapon"] = self.weapon
        if self.intents:
            out["built"] = [{"op": i["op"], "params": dict(i.get("params") or {})}
                            for i in self.intents]
        if self.missing:
            out["missing"] = self.missing
        if self.note:
            out["note"] = self.note
        if self.nowhere:
            out["nowhere"] = self.nowhere
        if self.gesture:
            out["gesture"] = True
        if self.unheld:
            out["unheld"] = self.unheld
        return out


# --- finding things the engine owns ---------------------------------------------------------

def _plain(words) -> str:
    from rules import holding

    return holding.plain(words)


def _props(scene) -> list:
    return getattr(scene, "props", None) or []


def addressed(scene) -> str:
    """The one person the player is dealing with, by the engine's state: engaged with,
    then in conversation (`state.talking`), then the only other person standing here.
    "" when that is not one person."""
    from rules import states as states_mod

    from . import judgement

    actors = getattr(scene, "actors", {}) or {}
    engaged = judgement.engaged_refs(scene)
    if len(engaged) == 1:
        return engaged[0]
    talking = [r for r, a in actors.items() if not a.is_pc and not a.is_down
               and a.has_state(states_mod.TALKING)]
    if len(talking) == 1:
        return talking[0]
    others = [r for r, a in actors.items() if not a.is_pc and not a.is_down]
    return others[0] if len(others) == 1 else ""


_FORMS = {"he": {"he", "him", "his"}, "him": {"he", "him", "his"},
          "she": {"she", "her", "hers"}, "her": {"she", "her", "hers"},
          "they": {"they", "them", "their"}, "them": {"they", "them", "their"},
          "it": {"it", "its"}, "its": {"it", "its"}}


def _pronoun_forms(pronouns) -> set[str]:
    out: set[str] = set()
    for p in str(pronouns or "").lower().split("/"):
        out |= _FORMS.get(p.strip(), set())
    return out


def person(scene, words) -> str:
    """The ref of the person here the slot names; a bare pronoun is `addressed`."""
    from rules import scope

    said = " ".join(str(words or "").split())
    if not said or scene is None:
        return ""
    if said.lower() in _PRONOUNS:
        # The pronoun against the pronouns the engine holds for each person here (the
        # sheet's `pronouns`, a closed vocabulary): "I toss her five silver" with a woman
        # and the challenger in the ring is the woman. Else the one the player is dealing
        # with.
        fits = [r for r, a in (getattr(scene, "actors", {}) or {}).items()
                if not a.is_pc and not a.is_down
                and said.lower() in _pronoun_forms(getattr(a, "pronouns", ""))]
        return fits[0] if len(fits) == 1 else addressed(scene)
    ref = scope.in_the_room(scene, said)
    actor = (getattr(scene, "actors", {}) or {}).get(ref)
    if actor is None or actor.is_pc:
        return ""
    return ref


def _follows_a_trail(a: dict, scene, places=()) -> bool:
    """Whether a `follow` act follows a trail rather than somebody in sight or a way to a
    place: nobody it names is standing here (`person`), and nothing it names is a place
    the engine knows (`places.find`). The engine's state, never the words' meaning:
    "I follow the guards" with the guards beside you is the thread's
    (`judgement.update_thread`), and "I follow the road to the well" is a walk."""
    from rules import places as places_mod

    said = [" ".join(str(a.get(s) or "").split()) for s in ("target", "object", "place")]
    said = [w for w in said if w]
    if any(person(scene, w) for w in said):
        return False
    # A bare pronoun with somebody standing here is them, whoever `person` could not pick
    # out. Measured live 2026-11-01: "I sigh and go quietly with them", the captain and
    # two guards arresting the player, was read as a follow of "them"; nobody was being
    # talked to, so the pronoun named nobody and a Survival roll looked for their tracks
    # on the market floor.
    if any(w.lower() in _PRONOUNS for w in said) and any(
            not x.is_pc and not x.is_down for x in (getattr(scene, "actors", {}) or {}).values()):
        return False
    if places and any(places_mod.find(places, w) is not None for w in said):
        return False
    return True


def quarries(rows: list[Row], frame: dict | None, scene, *, ask=None,
             world=None) -> list[str]:
    """What each track the table built is after — its `quarry`, the player's own words —
    and a line per one kept, for the turn log.

    A phrase that names somebody the engine holds (`tracking.quarry_of`) is the quarry
    outright. Any other phrase is asked ONE question (`interpret.confirm_quarry`): does it
    name the one who made the trail, or only the marks? — because the reader puts "the
    caravan" and "the tracks" in either slot (probed live, 2026-10-27). `ask` None (the
    suite, the reader off) keeps only a held quarry: a track that claims nothing about
    what it is after is the track as it was before.

    The owner's report the same day: "I continue to track the caravan", a caravan nothing
    held, rolled Survival and the beat found its ruts. With the quarry kept, the engine
    answers that no trail of the caravan crosses this ground."""
    from rules import tracking

    notes: list[str] = []
    if not frame or scene is None:
        return notes
    actions = frame.get("actions") or []
    for row in rows:
        a = actions[row.index] if row.index < len(actions) else {}
        for built in row.intents:
            if built.get("op") != "track":
                continue
            phrases = []
            for slot in ("target", "object"):
                w = " ".join(str(a.get(slot) or "").split())
                if w and w not in phrases:
                    phrases.append(w)
            quarry = next((w for w in phrases
                           if tracking.quarry_of(scene, w, world=world) is not None), "")
            if not quarry and ask is not None:
                span = str(a.get("span") or " ".join(phrases))
                quarry = next((w for w in phrases if ask(span, w) == "the maker"), "")
            if quarry:
                built["params"] = dict(built.get("params") or {}, quarry=quarry[:80])
                notes.append(f"track: after {quarry!r}")
    return notes


# The acts a player agrees to a task in: words said to somebody.
_AGREEING_ACTS = frozenset({"talk", "request", "other"})


def take_ups(rows: list[Row], frame: dict | None, scene, *, ask=None) -> list[str]:
    """A quest the player knows of (`cards.offered_quests`), taken up when the player
    speaks to the one who wants it done and the reader says the words agree to do it
    (`interpret.confirm_take_up`) — the engine's `quest` op, built whole with the card's
    own title and objectives, so the planner's wording never replaces them.

    Detected in code from the engine's state — an act done now, aimed at a person here
    who is the giver of such a quest — and asked one closed question; `ask` None (the
    suite, the reader off) takes nothing up. Measured live 2026-10-27: "I will find your
    Coldwood for you" to Brix Sootspar, the planner proposed nothing, and the quest stayed
    his. Returns a line per quest taken up, for the turn log."""
    from rules import cards as cards_mod

    from . import interpret

    notes: list[str] = []
    if ask is None or not frame or scene is None:
        return notes
    known = cards_mod.offered_quests(scene)
    if not known:
        return notes
    actions = frame.get("actions") or []
    taken: set[str] = set()
    for row in rows:
        a = actions[row.index] if row.index < len(actions) else {}
        if row.act not in _AGREEING_ACTS or not interpret.acting(a):
            continue
        ref = person(scene, " ".join(str(a.get("target") or "").split())) or addressed(scene)
        for card in known:
            if card.id in taken or not ref or card.giver != ref:
                continue
            who = scene.actors[ref].name
            if ask(str(a.get("span") or ""), who, card.title) != "agrees to do it":
                continue
            row.intents.append({
                "op": "quest", "actor": scene.pc().ref if scene.pc() else "pc",
                "params": {"title": card.title, "quest": card.id,
                           "objectives": [o["text"] for o in card.objectives] or [card.title]},
                "because": f"the player agrees to it, to {who}"})
            taken.add(card.id)
            notes.append(f"{card.title}: taken up, to {who}")
    return notes


def _names_too(actor, words: str) -> bool:
    """Whether the words' head noun is a word of this person's shown or true name — the
    room finder's own test for a description (`scope._head_noun`, `scope._words`)."""
    from rules import scope

    noun = scope._head_noun(scope.head_phrase(words))
    called = scope._words(f"{getattr(actor, 'name', '')} {getattr(actor, 'true_name', '')}")
    return bool(noun) and noun in called


# The acts a player speaks to an employer in: words said, a request, what they claim to be
# ("I can fight" is often read as a claim), anything else.
_JOB_ACTS = frozenset({"talk", "request", "claim", "other"})


def jobs_spoken(rows: list[Row], frame: dict | None, scene, *, ask=None) -> list[str]:
    """What the player's words do about the work an employer here holds (rules/jobs.py),
    built whole as the engine's `job` op — or, for a request for more pay read as talk, the
    Diplomacy request the engine turns into the haggle (`Engine._haggle_job`).

    Detected in code from the engine's state — an act done now, by words, to (or in front
    of) a person here who is the employer of a live job — and asked one closed question
    (`interpret.confirm_job`): what the words do, the work named from the table's own three
    words, and which of the jobs put to the player an agreement is to, from their titles.
    `ask` None (the suite, the reader off) does nothing. Returns a line per job op built,
    for the turn log.

    The owner's report of 2026-10-27: "I tell the clerk I can fight" at the hiring table
    and five planned replies made up an escort nobody held; the answers of the same day
    say the clerk offers a real escort or a week's guard work (rules/jobs.py)."""
    from rules import cards as cards_mod
    from rules import jobs as jobs_mod

    from . import interpret

    notes: list[str] = []
    if ask is None or not frame or scene is None:
        return notes
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None:
        return notes
    actions = frame.get("actions") or []
    done: set[str] = set()
    # The one person standing here who holds work: who "the clerk" means when the words do
    # not find a name (a world character cast as the clerk carries their own name, measured
    # on Pangrella) and the player is dealing with nobody in particular.
    # And a keeper who takes on hands by the week (`jobs.HIRES`): asked like any employer,
    # the week opened when they are asked for it (`Engine._op_job`, playtest #84).
    def hires(r: str) -> bool:
        return bool(jobs_mod.held_by(scene, r)
                    or jobs_mod.hires_hands((getattr(scene, "actors", {}) or {}).get(r)))

    # The ones who hold work first: a keeper who hires on demand (the guild's clerk at the
    # counter) is asked only when nobody here holds any, or the hiring table's own clerk
    # had a rival in the same room (Pangrella's guildhall, 2026-11-17).
    holding = [r for r in (getattr(scene, "actors", {}) or {})
               if jobs_mod.held_by(scene, r)]
    hiring = holding or [r for r in (getattr(scene, "actors", {}) or {}) if hires(r)]
    for row in rows:
        a = actions[row.index] if row.index < len(actions) else {}
        if row.act not in _JOB_ACTS or not interpret.acting(a):
            continue
        words = " ".join(str(a.get("target") or "").split())
        ref = ((person(scene, words) if words else "") or addressed(scene)
               or (hiring[0] if len(hiring) == 1 else ""))
        if ref not in hiring and len(hiring) == 1 and words and _names_too(
                scene.actors[hiring[0]], words):
            # Two people the words fit as well, and one of them is hiring: measured on
            # Pangrella's guildhall, "the clerk" was the clerk of the guild at the counter
            # (first in the room) beside the guild clerk taking names. The room's own
            # finder words it as a tie; the work decides it.
            ref = hiring[0]
        if not ref or ref in done or ref not in hiring:
            continue
        offered = [c for c in jobs_mod.held_by(scene, ref)
                   if cards_mod.standing(c) == cards_mod.OFFERED and c.job.get("work")]
        # And the ones the player already took and has not started: what "I've changed my
        # mind about the caravan" gives up. Playtest 2026-11-15 #9: only the offers were
        # listed, so the reader named the town week, which was turned down instead, and
        # the caravan contract she held stayed.
        taken = [c for c in jobs_mod.held_by(scene, ref)
                 if cards_mod.standing(c) == cards_mod.OWN and not jobs_mod.quit_refusal(c)]
        who = scene.actors[ref].name
        got = ask(str(a.get("span") or ""), who, [c.title for c in offered + taken]) or {}
        answer = got.get("answer", "")
        named = next((c for c in offered if c.title == got.get("job")), None)
        quits = next((c for c in taken if c.title == got.get("job")), None)
        if quits is None and named is None and not offered and len(taken) == 1:
            quits = taken[0]      # nothing else on the table to turn down
        if answer == "turns it down" and quits is not None:
            row.intents.append({"op": "job", "actor": pc.ref, "target": ref,
                                "params": {"do": "decline", "job": quits.id},
                                "because": f"the player, to {who}: gives up the job"})
            notes.append(f"{who}: gives up {quits.title}")
            done.add(ref)
            continue
        built = None
        if answer == "says what work they can do":
            said = got.get("work") if got.get("work") in jobs_mod.SAID else ""
            built = {"do": "offer", **({"work": said} if said else {})}
        elif answer == "asks about the work":
            # What the work is, what it pays, where it goes: the engine's answer, every
            # job this employer holds put to the player as the engine holds it.
            built = {"do": "offer"}
        elif answer == "agrees to the job" and offered:
            built = {"do": "accept", **({"job": named.id} if named else {})}
        elif answer == "turns it down" and offered:
            built = {"do": "decline", **({"job": named.id} if named else {})}
        elif answer == "asks for more pay" and jobs_mod.priced_offer(scene, ref) is not None:
            # One request a sentence. Measured live 2026-10-27: "I tell the clerk a sword
            # like mine is worth more than a gold a day and ask for better pay" was read as a
            # talk AND a request; the request row had built its check, this talk row built
            # a second, and the player was handed two Diplomacy popups (the second at +5).
            if not any(i.get("op") == "check" and i.get("target") == ref
                       and (i.get("params") or {}).get("request") == "payment"
                       for r in rows for i in r.intents):
                name = (f"the {who}" if who[:1].islower()
                        and not who.lower().startswith(("the ", "a ", "an ")) else who)
                row.intents.append({"op": "check", "actor": pc.ref, "target": ref,
                                    "params": {"skill": "diplomacy", "request": "payment"},
                                    "because": f"the player asks {name} for better pay"})
            notes.append(f"{who}: asked for more pay")
            done.add(ref)
            continue
        if answer:
            notes.append(f"{who}: {answer}")
        if built is None:
            continue
        if built.get("do") == "offer":
            # Asking for work is not asking to be paid: live 2026-11-17 (fix/inns-and-jobs),
            # "I ask the clerk of the guild if there is any paid work for a blade" was read
            # a `request` for payment, and a Diplomacy roll for a favour (failed, "offers no
            # payment") stood beside the week of guard work the clerk put. The job is the
            # answer; the request roll for it goes.
            row.intents[:] = [i for i in row.intents
                              if not (i.get("op") == "check" and i.get("target") == ref
                                      and (i.get("params") or {}).get("request")
                                      == "payment")]
        row.intents.append({"op": "job", "actor": pc.ref, "target": ref, "params": built,
                            "because": f"the player, to {who}: {answer}"})
        done.add(ref)
    return notes


def coin_amount(words) -> tuple[str, int] | None:
    """("gp", 10) for "ten gold", "10 gp", "three silver pieces"; None otherwise."""
    from rules import goods

    m = _AMOUNT.match(str(words or ""))
    if not m:
        return None
    denom = goods.coin_named(m.group(2))
    if not denom:
        return None
    n = m.group(1).lower()
    return denom, (int(n) if n.isdigit() else _NUMBERS.get(n, 1))


def _is_coin(words) -> bool:
    from rules import goods, holding

    return holding.is_money(words) or bool(goods.coin_named(str(words or "")))


def _stock_id(pc, words) -> str:
    """The id of the jar on the player's shelf the words name, exact by id, base or name
    — `consumables.resolve_stock` guesses by content words, and a sale by guess sells the
    wrong jar."""
    from rules import holding

    return holding.stock_key(getattr(pc, "stock", {}) or {}, words)


def _carried(pc, words, coming=()) -> str:
    """The pack's key for the thing, or the stock jar's id; "" when the player has none.
    `coming` is what an earlier deed of the same sentence picks up: "I lift the lantern off
    the hook, then hand it to the boy" hands over a lantern the pack does not hold YET —
    one action at a time, each against the state the last one leaves (Inform's DM4 §34)."""
    from rules import holding

    return (holding.key_in(getattr(pc, "goods", {}) or {}, words) or _stock_id(pc, words)
            or next((c for c in coming if holding.same(c, words)), ""))


def _a_thing(words) -> bool:
    from . import judgement

    return judgement._is_a_thing(words)


def _object(frame, i: int, pc=None, recent=()) -> str:
    """The action's object; "it" and its kin are the object of the deed before it in the
    same sentence ("I lift the lantern off the hook, then hand it to the boy") — the
    frame's own structure. With none there, the one thing in the pack the last few beats
    name, longest name first: "It's a deal, he can have it" after "The clerk eyes the
    crate". The pack is a closed vocabulary, matched whole-word, as a spell's name is
    matched against the catalogue (`judgement.spell_in_words`); the beats are not read for
    anything else. Nothing when that is not one thing."""
    from rules import holding

    acts = frame.get("actions") or []
    said = " ".join(str(acts[i].get("object") or "").split())
    if said.lower() not in _IT:
        return said
    for prev in reversed(acts[:i]):
        if prev.get("object") and str(prev["object"]).lower() not in _IT:
            return " ".join(str(prev["object"]).split())
    goods = sorted((getattr(pc, "goods", {}) or {}), key=len, reverse=True)
    for beat in reversed([str(b or "").lower() for b in recent or ()]):
        named = [k for k in goods if len(holding.plain(k)) > 2 and re.search(
            rf"\b{re.escape(holding.plain(k))}s?\b", beat)]
        if len(named) == 1:
            return named[0]
    return ""


# --- the rows -------------------------------------------------------------------------------

def _a_person(scene, words) -> bool:
    """Whether an object slot names a person, not a thing: a bare pronoun for one, or
    somebody standing here. "I grab him and throw him over a table" was read `take` — and a
    take of "him" is a grapple, never goods (the fight recordings, 2026-09-25 and 09-27)."""
    said = " ".join(str(words or "").split()).lower()
    return said in _PRONOUNS or said in ("me", "myself", "you") or bool(person(scene, said))


def _counter_keeper(scene) -> str:
    """The keeper whose counter a take names when its holder is no person here — "his
    open till", "the stall": the one person here who keeps a counter, else the one of
    them the player is dealing with; "" when that is not one person. Structure, not
    English: the slot named a holder the people here could not answer, and a counter is
    the one holder a keeper stands behind (playtest 2026-11-15 #7: "pocket a handful of
    coins from his open till" built a give from nobody, refused "nobody here is holding
    any coin")."""
    from rules import keepers

    keeping = [r for r, a in (getattr(scene, "actors", {}) or {}).items()
               if not a.is_pc and keepers.keeps_a_counter(a)]
    if len(keeping) == 1:
        return keeping[0]
    dealt = addressed(scene)
    return dealt if dealt in keeping else ""


def _take(row: Row, frame, i, scene, pc, recent=()) -> None:
    from rules import holding

    a = frame["actions"][i]
    thing = _object(frame, i, pc, recent)
    if not thing:
        row.note = "nothing named to take"
        return
    coin = _is_coin(thing)
    if not coin and (_a_person(scene, thing) or not _a_thing(thing)):
        row.note = f"{thing!r} is not a thing to carry"
        return
    source = " ".join(str(a.get("target") or "").split())
    if not source:
        # A take that names no holder, right after a take that did, comes out of the same
        # hands — the frame's own structure, as "it" is the object before it. Measured
        # live on this branch (2026-10-08): "I take one of the pears from the fruit
        # seller, then a melon" read the melon with no target, nobody here carried one,
        # and the world-never-runs-out rule minted it ("Kesst Vayr takes the melon")
        # where a melon from the seller is refused: she has none.
        prev = next((p for p in reversed(frame["actions"][:i])
                     if p.get("act") in ("take", "steal")), None)
        if prev is not None and prev.get("target"):
            source = " ".join(str(prev["target"]).split())
    # Still nobody named: a thing that is not lying here, carried by the one person the
    # player is dealing with, comes out of their hands — so `confirm_takes` asks whether
    # they offered it. Playtest 2026-11-20 #5: "I accept the food" named nobody, and the
    # food offered never left the carter's pack (nothing on record held it, then).
    held_from = ""
    if not source and not coin:
        ref = addressed(scene)
        them = (getattr(scene, "actors", {}) or {}).get(ref) if ref else None
        lying = getattr(scene, "prop_on_the_ground", None)
        if them is not None and not them.is_pc and holding.carried_by(them, thing) \
                and not (lying and lying(thing) is not None):
            held_from = ref
    if source and _mine(source) and not coin and not person(scene, source):
        # Out of the player's own pack, pocket or pouch: what it holds is what they carry,
        # and taking it out moves nothing (playtest 2026-11-17 #18: "take a torch out of my
        # pack" built a pick-up, refused "a torch is not here: it lies at the market").
        # Not `holding.is_container`, whose closed list has no "pack": "my" says whose.
        boxed = any(r.get("held_by") == pc.ref and holding.key_in(
            ((r.get("contents") or {}).get("goods") or {}), thing)
            for r in getattr(scene, "props", None) or ())
        if not boxed:
            if _carried(pc, thing):
                row.note = f"{thing} is already carried"
            else:
                row.missing = row.unheld = f"{pc.name} has no {_plain(thing)}"
            return
    if getattr(scene, "in_encounter", False) and not coin \
            and not (source and holding.is_box(source, _props(scene))):
        # In a fight, a thing taken off a foe is 1e's Steal (CMB against CMD, the `attack`
        # op's `manoeuvre: steal`, which picks from what they really carry and refuses in
        # words what they do not — `Engine._steal_choice`). The foe is the one the words
        # name, else the one the player is locked with (`addressed`: engaged first).
        # Measured live 2026-10-09 (the fight script, mid-grapple): "I take what he was
        # carrying" became a `give` of the item "what he was carrying" from nobody — the
        # world minted it, "Kesst Vayr takes the what he was carrying" — beside the plan's
        # own steal, which the review then turned into a rapier swing nobody declared.
        foe = person(scene, source) if source else addressed(scene)
        actor = (getattr(scene, "actors", {}) or {}).get(foe) if foe else None
        if actor is not None and not actor.is_pc:
            row.intents.append({"op": "attack", "actor": pc.ref, "target": foe,
                                "params": {"manoeuvre": "steal",
                                           "item": _plain(thing) or thing},
                                "because": "the player takes it off them in the fight"})
            row.note = f"a steal from {actor.name}: {thing}"
            return
    params: dict = {"item": _plain(thing) or thing, "to": pc.ref}
    amount = coin_amount(thing) if coin and not holding.is_box(source, _props(scene)) else None
    if amount:
        # "ten gold" from a person or a till: a denomination and a count, as a give's is
        # (a pouch's coin keeps its own door, which empties it).
        params.update(item=amount[0], count=amount[1])
    if source and holding.is_box(source, _props(scene)):
        params["from_"] = _plain(source)
        if set(re.findall(r"[a-z]+", _plain(thing))) & _WHOLE:
            # "everything that's in the gaoler's box", "what's inside": the box emptied,
            # its contents the engine's record (`Engine._empty_box`). Playtest 2026-11-17
            # #42: the give of "everything" was answered "'everything' is a word, not a
            # thing", logged resolved, and the 50 gp stayed in the box.
            params["item"] = "everything"
    elif source:
        who = person(scene, source) or _counter_keeper(scene)
        if who:
            params["from_"] = who
    elif held_from:
        params["from_"] = held_from
    if not coin and "from_" not in params and holding.key_in(pc.goods, thing):
        # Carrying what is already carried: "I take the crate to the counting house"
        # (2026-10-03, turn 73: a second crate came out of the air).
        row.note = f"{thing} is already carried"
        return
    row.intents.append({"op": "give", "actor": pc.ref, "params": params,
                        "because": "the player took it"})


def _drop(row: Row, frame, i, scene, pc, recent=(), coming=()) -> None:
    thing = _object(frame, i, pc, recent)
    if not thing:
        row.note = "nothing named to set down"
        return
    key = _carried(pc, thing, coming)
    if not key and not _is_coin(thing):
        row.missing = f"{pc.name} is not carrying {thing}"
        return
    row.intents.append({"op": "give", "actor": pc.ref,
                        "params": {"item": key or _plain(thing), "from_": pc.ref},
                        "because": "the player set it down"})


def fine_pending(scene, pc) -> bool:
    """Whether the player stands before the watch's sentence with a fine to come: held
    (rules/trial.py `law.custody`), questioned or at the plea, not escaped, and the charges
    held against them carry no death sentence. The engine's record, never the words."""
    from rules import trial

    try:
        held = trial.custody(pc) if pc is not None else None
    except Exception:  # noqa: BLE001 — no custody to read is no fine
        return False
    pay = dict(getattr(held, "payload", None) or {})
    if held is None or pay.get("escaped") or pay.get("stage") not in ("questioning", "plea"):
        return False
    chs = trial._from_dicts(pay.get("charges"))
    if not chs:
        return False
    return not trial.sentence_for(chs, mercy=False)["death"]


def _to_the_law(scene, ref: str) -> bool:
    from rules import trial

    return trial._is_law((getattr(scene, "actors", {}) or {}).get(str(ref or "")))


def fold_the_fine(raw, scene, notes=None):
    """A hand-over to the watch while a fine is to come is the fine, and the fine is the
    sentence's own: rules/trial.py `_sentence` takes it from the purse when sentence is
    passed (and gives the stolen goods back to their owners). So every give of the
    player's to one of the law — coin or goods — is dropped while `fine_pending`.

    Measured on the bench of 2026-11-02, the owner's slip of 2026-11-01 again: "I say
    nothing more and pay the fine" at the plea was planned as a give of 6 gold pieces to
    the officer, and the engine, seeing coin handed to the law by somebody held, read it
    as a bribe (`trial.bribed`): "pushes it back: looking the other way would take …"
    beside the sentence's own "pays 6 gold pieces" (2 of 3 runs; the third gave silver
    and was refused). The page cannot tell both. Runs inside `apply` and again in
    `GMAgent.plan_turn` after the check injectors, as `fold_price_talk` does, so a plan
    with no reading behind it is folded too.

    A give of the player's that names nobody else goes as well: with no receiver the
    engine reads it as the player picking the thing up. Measured on the after-bench of
    2026-11-03 (fine, 1 of 3 runs): the plan's "6 gp" and "silver-bracelet" with no `to`
    were refused "Nobody here is holding 6 gp out to <the player>" and "There is no
    silver-bracelet here … to pick up", and the page told "the silver bracelet remains
    safely in your possession" beside the sentence's "taken back to their owners"."""
    if not isinstance(raw, list) or scene is None:
        return raw
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None or not fine_pending(scene, pc):
        return raw
    out = []
    for r in raw:
        if isinstance(r, dict) and _op(r) == "give":
            p = r.get("params") or {}
            actor = str(r.get("actor") or "")
            mine = actor in ("", "pc", pc.ref, "None") or str(p.get("from_") or "") == pc.ref
            to = str(p.get("to") or r.get("target") or "")
            if mine and (to in ("", pc.ref) or _to_the_law(scene, to)):
                if notes is not None:
                    notes.append(f"the give of {p.get('item')!r} to the watch is the fine: "
                                 f"the sentence takes it, dropped")
                continue
        out.append(r)
    return out


def _give(row: Row, frame, i, scene, pc, recent=(), coming=()) -> None:
    a = frame["actions"][i]
    thing = _object(frame, i, pc, recent)
    if (not thing or (_is_coin(thing) and not coin_amount(thing))) \
            and _agreed_work(row, a, scene, pc):
        # "pay", "give him the money": coin of no named amount, at a keeper asked for
        # work today, is the job's price paid — the commission's own (`_agreed_work`).
        return
    if not coin_amount(thing) and not _carried(pc, thing, coming):
        # Paid to somebody asking a toll, a sum not named is the toll (`Engine._pay_toll`):
        # "I pay the toll-keeper his toll" (playtest 2026-11-17 #22) was "not carrying his
        # toll" to every door, and no coin moved. Structure: who it goes to holds the toll.
        from rules import states

        said_to = " ".join(str(a.get("target") or "").split())
        ref = person(scene, said_to) if said_to else addressed(scene)
        held = (getattr(scene, "actors", {}) or {}).get(ref)
        if held is not None and held.has_state(states.ASKS_A_TOLL):
            row.intents.append({"op": "give", "actor": pc.ref,
                                "params": {"item": "the toll", "from_": pc.ref, "to": ref},
                                "because": "the player paid the toll"})
            return
    if not thing:
        row.note = "nothing named to hand over"
        return
    to_words = " ".join(str(a.get("target") or "").split())
    if fine_pending(scene, pc) and (not to_words or _to_the_law(scene, person(scene, to_words))):
        # Paying the watch while a fine is to come: the sentence's own payment
        # (`fold_the_fine`). Nothing is built, and nothing is "not carried": "I pay the
        # fine" alone was a refusal of the whole turn ("is not carrying the fine"), and the
        # sentence never came.
        row.note = "the fine is the sentence's own payment: rules/trial.py takes it"
        return
    amount = coin_amount(thing)
    key = _carried(pc, thing, coming)
    if not (amount or key or _is_coin(thing)):
        if _a_person(scene, thing) or not _a_thing(thing):
            row.note = f"{thing!r} is not a thing to hand over"
            row.gesture = True
        else:
            # "I buy the old soldier a pint": nothing in the pack to hand over, and the
            # pint is the bar's to pour. Said, never minted.
            row.missing = f"{pc.name} is not carrying {thing}"
        return
    to_words = " ".join(str(a.get("target") or "").split())
    # Nobody named ("I hand over the brass key"): the one the player is dealing with.
    to = person(scene, to_words) if to_words else addressed(scene)
    if not to:
        row.missing = (f"there is nobody here who is {to_words}" if to_words
                       else f"nobody here to give {thing} to")
        return
    stay = _stay_paid_for(a, scene, to) if (amount or _is_coin(thing)) else None
    if stay is not None:
        # Coin handed to the house's keeper for a room is the room bought, at the book's
        # price through the counter's own door (`Engine._buy_stay`), never the sum said:
        # jack T205 (owner's save 2026-11-17), "I hand over 2 gold for the private room"
        # was a plain gift, no room was held, and the night upstairs was billed again.
        row.intents.append({"op": "buy", "actor": pc.ref,
                            "params": {"item": stay["id"], "from_": to},
                            "because": "the player paid the keeper for a room"})
        row.note = f"coin for a room: the {stay['quality']} stay, at the house's price"
        return
    if amount:
        params = {"item": amount[0], "count": amount[1], "from_": pc.ref, "to": to}
    else:
        params = {"item": key or _plain(thing), "from_": pc.ref, "to": to}
    row.intents.append({"op": "give", "actor": pc.ref, "params": params,
                        "because": "the player handed it over"})


def _stay_paid_for(a: dict, scene, to: str) -> dict | None:
    """The inn's stay a coin `give` pays for (`lodging.find`'s row), or None: only to the
    keeper of the house the party stands in, where beds are let, and only when the act's
    own place slot (else its span) names a room the house lets."""
    from rules import keepers, lodging

    at = str(getattr(scene, "at", "") or "")
    keeper = keepers.keeper_in(scene, at) if at and lodging.lets_beds(scene, at) else None
    if keeper is None or keeper.ref != to:
        return None
    for words in (a.get("place"), a.get("span")):
        found = lodging.find(str(words or "")) if words else None
        if found is not None:
            return found
    return None


def _agreed_work(row: Row, a: dict, scene, pc) -> bool:
    """A price agreed, or paid, to a keeper who was asked for work today: the commission,
    taken at the engine's price (rules/commission.py, `agree`). True when it was built.

    Built from the reader's closed answer and the engine's record, never the words: a `sell`
    (whose gloss is "agree a sale, accept a price") or a `give` with nothing of the
    player's to hand over but coin, at a keeper `commission.asked_of` holds work asked of
    today. Measured on the bench of 2026-11-02, 3 of 3 runs of "I agree to his price and
    pay" at the smith the turn after the job was asked for: read `sell: his price` and
    `give: pay`, the table built nothing ("nothing was named to sell"), and the plan paid
    10 gold, 1 gold or nothing — never the job's own price — and twice the unshown-deed
    backstop wrote the agreement and the payment as done."""
    from rules import commission

    actors = getattr(scene, "actors", {}) or {}
    words = " ".join(str(a.get("target") or "").split())
    ref = person(scene, words) if words else ""
    asked = None
    keeper = actors.get(ref) if ref else None
    if keeper is not None and not keeper.is_pc:
        asked = commission.asked_of(scene, pc, keeper)
    if asked is None:
        # Nobody named, or a name the slot could not ground ("his"): the one keeper here
        # with work asked of them today.
        open_ = [(r, x) for r, x in actors.items() if not x.is_pc and not x.is_down
                 and commission.asked_of(scene, pc, x) is not None]
        if len(open_) != 1:
            return False
        ref, keeper = open_[0]
        asked = commission.asked_of(scene, pc, keeper)
    row.intents.append({"op": "commission", "actor": pc.ref,
                        "params": {"who": ref, "item": str(asked.get("item") or ""),
                                   "agree": True},
                        "because": f"the player agrees {keeper.name}'s price for the work"})
    row.note = f"{keeper.name}'s price for the work agreed: the commission"
    return True


def _sell(row: Row, frame, i, scene, pc, sentence: str, recent=(), coming=()) -> None:
    from rules import pricing

    a = frame["actions"][i]
    thing = _object(frame, i, pc, recent)
    key = _carried(pc, thing, coming) if thing else ""
    count = 0
    many = _carried_among(pc, thing) if thing and not key else []
    if len(many) > 1:
        # "the dagger, rope, bedroll and backpack": several things the pack holds, each
        # named whole inside the one slot — sold one by one, as the panel sells them.
        key = many[0]
    if thing and not key:
        # The party's cargo (rules/trade.py) is in no pack: "I sell my iron to the keeper
        # of the general store" was refused "not carrying my iron" with 2000 lb of it on
        # the quay (live, 2026-11-15). The row by the world's table, the engine's own
        # `_op_sell` door; the whole of it within reach, as "my iron" means.
        from rules import trade

        bulk = trade.row_for(thing)
        here = trade.reachable(scene, bulk) if bulk else []
        if here:
            key, count = trade.PREFIX + bulk, sum(int(x.get("units", 0)) for x in here)
    if not thing and row.commit == "done" and _agreed_work(row, a, scene, pc):
        # A sale of nothing named: a price accepted. Only with no object at all — "I sell
        # him my sword" with no sword is the refusal below, never a job taken.
        return
    if not key and row.commit == "tried":
        # An offer of something not in the pack is talk, not a sale refused: the live
        # reader read "I approach the man and offer to help him with the crate" as an
        # offer of "to help him with the crate", and "not carrying to help him…" would
        # have reached the brief as a fact.
        row.note = f"an offer of {thing or 'nothing named'}, nothing carried to sell"
        # Except a thing the player calls their own: the live check of 2026-11-15, "I
        # offer the smith my pelts, then leave" with no pelts in the pack, was planned a
        # bare narrate_only and the page wrote "You reach into your pack and pull out the
        # bundle of pelts". The pack answers, printed (`things_not_here`).
        if _mine(thing) and _a_thing(thing):
            row.missing = row.unheld = f"{pc.name} has no {_plain(thing)}"
        return
    if not key:
        row.missing = (f"{pc.name} is not carrying {thing}" if thing
                       else "nothing was named to sell")
        return
    buyer_words = " ".join(str(a.get("target") or "").split())
    buyer = person(scene, buyer_words) if buyer_words else addressed(scene)
    if not buyer and _walks_first(frame, i):
        # "I go to the market and sell … to the general store": the buyer stands where
        # the walk ends, not here, and the engine finds whoever keeps the counter there
        # when the sale resolves (`Engine._stall_here`). Playtest 2026-11-15 #74 refused it
        # "there is nobody here who is the general store" at plan time.
        buyer = ""
    elif not buyer:
        row.missing = (f"there is nobody here who is {buyer_words}" if buyer_words
                       else f"nobody here to sell {thing} to")
        return
    if row.commit == "tried":
        # A sale tried is an offer (ISO 24617-2: an Offer, which only an Accept Offer
        # closes) — a haggle the fiction answers, and only an agreement closes it. At a
        # counter too: round 1 let a keeper buy whatever was offered (CircleMUD's
        # shopkeeper, the retired `_sell_goods_declared`'s rule), and in round 2's replay
        # the counting house's clerk keeps one, so "…offer the crate for coin" would have
        # sold the crate three turns before the player agreed a price. A stall's own
        # screen is where a priced sale is made in one step. Measured on the replay,
        # round 1: "I try to sell the crate to the smith for coin" was read `sell` and sold.
        row.note = "an offer, not a sale: the buyer must agree first"
        return
    from rules import goods

    for key in (many if len(many) > 1 else [key]):
        params: dict = {"item": key}
        if buyer:
            params["to"] = buyer
        held = (getattr(pc, "stock", {}) or {}).get(key)
        if count:
            params["count"] = count
        elif held is not None and goods.unit_for(getattr(held, "base", "") or held.name):
            # "the rope" is the whole length carried, never one foot of it (#76).
            params["count"] = int(held.count)
        share = _SHARE.search(str(sentence or ""))
        if share and key in (pc.goods or {}):
            params["accept"] = round(int(share.group(1)) / 100 * pricing.goods_worth(key),
                                     2)
        row.intents.append({"op": "sell", "actor": pc.ref, "params": params,
                            "because": "the player sold it"})


def _carried_among(pc, words) -> list[str]:
    """Every thing in the pack or on the shelf named whole inside `words`, in the words'
    order — the pack as a closed vocabulary, matched whole-word as `_object` matches it
    against a beat; nothing outside it is read. Playtest 2026-11-15 #74: "sell the
    merchant's dagger, rope, bedroll and backpack to the general store" was one slot,
    "not carrying the merchant's dagger, rope, bedroll and backpack", and nothing sold."""
    from rules import holding

    said = holding.plain(words)
    names: dict[str, str] = {}
    for k in (getattr(pc, "goods", {}) or {}):
        names.setdefault(holding.plain(k), k)
    for sid, st in (getattr(pc, "stock", {}) or {}).items():
        for n in (getattr(st, "name", ""), getattr(st, "base", "")):
            if n:
                names.setdefault(holding.plain(n), sid)
    # And each thing's head noun when only one thing carried has it: "rope" is the hemp
    # rope (measured on the #74 replay: the rope was left unsold).
    heads: dict[str, set] = {}
    for name, key in names.items():
        heads.setdefault(holding.head_of(name), set()).add(key)
    for head, keys in heads.items():
        if head and len(keys) == 1:
            names.setdefault(head, next(iter(keys)))
    found: list[tuple[int, str]] = []
    taken: list[range] = []
    for name in sorted(names, key=len, reverse=True):
        if len(name) < 3:
            continue
        m = re.search(rf"\b{re.escape(name)}s?\b", said)
        if m is None or any(m.start() in r for r in taken) \
                or names[name] in {k for _, k in found}:
            continue
        taken.append(range(m.start(), m.end()))
        found.append((m.start(), names[name]))
    return [k for _, k in sorted(found)]


def _walks_first(frame, i: int) -> bool:
    """Whether an earlier deed of the sentence, done or tried, walks somewhere."""
    from . import interpret

    return any(str(p.get("act") or "") in ("go", "journey", "seek") and interpret.acting(p)
               for p in (frame.get("actions") or [])[:i])


def table(frame: dict | None, scene, *, places=(), sentence: str = "",
          recent=()) -> list[Row]:
    """The rows the reading makes, one per action, in the order the words do them.
    `recent` is the last few beats, asked only for which carried thing "it" is."""
    from . import interpret

    rows: list[Row] = []
    if not frame or frame.get("error") or scene is None:
        return rows
    if frame.get("question") and not frame.get("actions"):
        return rows
    pc = scene.pc() if hasattr(scene, "pc") else None
    coming: list[str] = []
    gone: list[str] = []
    approached = ""
    bought = sold_not_asked(frame, scene)
    # "I follow her to her rooms": the walk is done now, with the person followed
    # (`_walk_rides_the_follow`, row 56 of the owner's 2026-11-05 save).
    led = _walk_rides_the_follow(frame, scene)
    for i, a in enumerate(frame.get("actions") or []):
        act = str(a.get("act") or "")
        if act == "attack" and a.get("target") and not person(scene, a["target"]):
            # A blow at a shut door out of here is the door forced (`break_in`, which
            # dungeons.break_door rolls at the book's DC). Playtest 2026-11-17 #43: "I
            # throw my shoulder against the door to the beast's pool again" was read
            # `attack, target: the door…`, nobody answered to it, and the turn was a 422
            # "Nobody here answers to the door to the beast's pool" — while the same door
            # forced in other words a turn earlier had worked. Rewritten in the reading,
            # so every later reader of it (`broken_into`, `victims`) agrees.
            from rules import dungeons

            beyond = dungeons.shut_door_named(scene, a["target"])
            if beyond:
                a.pop("blow", None)
                a.update(act="break_in", target=beyond)
                act = "break_in"
        row = Row(index=i, act=act, commit=str(a.get("commit") or "done"))
        if i in bought:
            row.note = bought[i]
        if a.get("commit_was"):
            row.note = f"done now: it rides on the follow ({a['commit_was']} as read)"
        if not interpret.acting(a):
            # Intended or asked about: context for the plan (`interpret.brief_lines` says
            # so), never an op. Round 1's replay sold the crate a turn early on "I take
            # the crate to the man … who will buy it from me", read as a sale.
            row.note = f"{row.commit}, not done this turn: no op"
            rows.append(row)
            continue
        if act in GOODS_ACTS and pc is not None:
            row.thing = _object(frame, i, pc, recent)
            if act == "steal" and getattr(scene, "in_encounter", False):
                # In a fight a steal is the combat manoeuvre (CMB against CMD, the
                # `attack` op's `maneuver: steal`), which the fight's own plan writes.
                row.note = "a steal in a fight is a manoeuvre: the fight's plan writes it"
            elif act in ("take", "steal"):
                # Out of a fight a steal is a take the holder never agreed to — the same
                # `give` a take builds, which the engine reads as taken because the player
                # is the one acting (`Engine._op_give`); never asked whether it was
                # offered (`confirm_takes`): the words already said.
                _take(row, frame, i, scene, pc, recent)
                # "It" taken again, right after the deed that took it: one thing taken
                # once. Measured live on the integration build (2026-11-01, the theft
                # scenario): "I snatch the silver bracelet from her tray and pocket
                # it" read `steal: the silver bracelet` then `take: it`, both built a give
                # of the bracelet, and the second came back "already carries the silver
                # bracelet, and none lies here: nothing more is picked up" beside the
                # theft's own tell — and the page wrote the bracelet still on the tray.
                # Only a pronoun object: "an apple, then another apple" is two takes.
                said = " ".join(str(a.get("object") or "").split()).lower()
                if said in _IT:
                    twice = [t for t in row.intents
                             if not _is_coin(t["params"]["item"])
                             and any(_same_thing(t["params"]["item"], g, pc)
                                     for g in coming)]
                    if twice:
                        row.intents = [t for t in row.intents if t not in twice]
                        row.note = f"{twice[0]['params']['item']} is already taken"
                coming += [str(t["params"]["item"]) for t in row.intents]
            elif act == "drop":
                _drop(row, frame, i, scene, pc, recent, coming)
            elif act == "give":
                _give(row, frame, i, scene, pc, recent, coming)
            else:
                _sell(row, frame, i, scene, pc, sentence, recent, coming)
            if act not in ("take", "steal"):
                # A thing an earlier deed of the sentence already parted with is not
                # parted with twice. Measured on the items save's last line, read live:
                # "I also drop the Brunt of the weight on the ground and leave it behind"
                # came back `drop: the Brunt of the weight` then `drop: it` — the same
                # brunt, set down twice, the second refused by the engine into the prose.
                # Coin is a number, and two payments are two (`_same_thing` calls any two
                # mentions of coin one thing, for replacing the plan's coin op).
                twice = [t for t in row.intents if not _is_coin(t["params"]["item"])
                         and any(_same_thing(t["params"]["item"], g, pc) for g in gone)]
                if twice:
                    row.intents = [t for t in row.intents if t not in twice]
                    row.note = f"{twice[0]['params']['item']} is already parted with"
                gone += [str(t["params"]["item"]) for t in row.intents]
        else:
            # The op names: one action at a time through the reading's own op map, so each
            # op is owed by the action that declared it.
            row.ops = interpret.ops_for({"actions": [a]}, scene, places)
            if act in ("leave", "athletics") and pc is not None \
                    and pc.has_state("state.position.pit"):
                _out_of_the_pit(row, pc)
                rows.append(row)
                continue
            if act == "go" and pc is not None and _to_the_square(row, a, scene, pc):
                rows.append(row)              # "I go to C5": the board's own square
                continue
            # A walk to a place somebody named and the town does not have yet owes the
            # found and the travel `judgement.go_to_heard_place` writes for it — owned by
            # this action, so `order` puts them where the words do. Measured live on the
            # merged branch: "I pick the crate back up and head to the old tannery" left
            # the travel unowned (`ops_for` grounds only places the town has), the
            # pick-up ran at the tannery, and the engine minted a second crate there.
            if act == "go" and not row.ops and a.get("place"):
                from rules import heard_places
                from rules import places as places_mod

                heard = heard_places.named_in(str(a["place"]), scene, places)
                if heard is not None:
                    # A rumoured way in is a venture (`go_to_heard_place`), not a found.
                    mark = (places_mod.find(places, heard.get("landmark") or "")
                            if heard.get("landmark") else None)
                    row.ops = (["venture"] if mark is not None
                               and heard_places.venture_kind(heard, scene, mark)
                               else ["found", "travel"])
            if act in ("go", "seek") and a.get("here"):
                approached = str(a["here"])
            if act == "talk" and not a.get("says") and pc is not None:
                _greet(row, a, scene, pc, approached)
            if act == "go" and not a.get("place") and not row.ops and pc is not None:
                _carry_on(row, scene, pc)
            elif act == "go" and a.get("place") and not row.ops and pc is not None:
                # Somebody's home, with them standing here: the walk there together
                # (`_home_together`) — else the town named whole, else nowhere known.
                from rules import places as places_mod

                home = (_dwelling_owner(a["place"], scene, led)
                        if not places or places_mod.find(places, a["place"]) is None else "")
                if home:
                    _home_together(row, home, scene, pc)
                elif not _to_my_room(row, str(a["place"]), scene, places, pc):
                    _to_the_town(row, str(a["place"]), scene, places, pc)
                    _nowhere(row, a, scene, places)
            if act == "go" and a.get("fixture"):
                # The reader named a fixture of the room (its closed `fixture`): one the
                # room lacks is put on the map, near the player, and keeps its square.
                from rules import fixtures as fixtures_mod

                # Held to the walker's own words against the room's fixtures ("the bar"
                # is the counter here, never the barrel the reader chose, 2026-11-12).
                a["fixture"] = fixtures_mod.held_to_words(
                    getattr(scene, "grid", None), str(a["fixture"]),
                    f"{a.get('place') or ''} {a.get('span') or ''}")
                fixtures_mod.name_one(scene, str(a["fixture"]))
                # And the walk happens: free of the turn's time, never of the map. Built
                # whole, through the engine's own move (stair, reach and provoking rules).
                if pc is not None:
                    _to_the_fixture(row, str(a["fixture"]), scene, pc)
            if act == "go" and pc is not None and not row.intents and not row.ops \
                    and not a.get("place") and not a.get("fixture") \
                    and getattr(scene, "in_encounter", False):
                _a_step(row, scene, pc)
            if act == "call_on" and pc is not None:
                # The reader's own call on a person who is standing here is the same walk
                # home together; their door would refuse them ("is here, with you").
                said = " ".join(str(a.get("target") or "").split())
                ref = (_by_pronoun(scene, said, led) if said.lower() in _PRONOUNS
                       else person(scene, said))
                if ref:
                    _home_together(row, ref, scene, pc)
            if act in ("go", "seek") and a.get("object") and pc is not None:
                _carry(row, frame, i, scene, pc, recent)
                coming += [str(t["params"]["item"]) for t in row.intents]
            if act == "track" and pc is not None:
                # Built whole: the op takes nothing the plan could get wrong — the ground
                # and the trails are the scene's (rules/tracking.py). Measured live
                # 2026-10-09: read as a `search`, the line owed no op, and no Survival
                # was rolled at all.
                row.intents.append({"op": "track", "actor": pc.ref, "params": {},
                                    "because": "the player looks for tracks"})
            # "Look for tracks and follow them": the pronoun is the tracks the same line
            # looked for, whoever else is standing here (`_follows_a_trail` reads a bare
            # pronoun with people present as them).
            on_the_trail = any(isinstance(x, dict) and x.get("act") == "track"
                               for x in frame.get("actions") or [])
            if act == "follow" and pc is not None and not row.ops \
                    and (_follows_a_trail(a, scene, places) or (on_the_trail and not any(
                        person(scene, a.get(k)) for k in ("target", "object")
                        if str(a.get(k) or "").lower() not in _PRONOUNS))):
                # Following a trail is the same Survival check, and where it leads is the
                # engine's (`Engine._op_track` with `follow`). Measured on the owner's
                # 0.2.21 save (row 136): "I follow the tracks in search of the caravan"
                # owed no op, and the plan walked the party to "the fields" — a walk
                # toward nothing the engine held.
                looked = next((i for r in rows for i in r.intents if i["op"] == "track"),
                              None)
                if looked is not None:
                    # "I look for tracks of the caravan and follow them": one look, one
                    # roll, followed. Measured live 2026-10-27 as two tracks and two d20s.
                    looked["params"] = dict(looked.get("params") or {}, follow=True)
                else:
                    row.intents.append({"op": "track", "actor": pc.ref,
                                        "params": {"follow": True},
                                        "because": "the player follows a trail"})
            if act == "exert" and pc is not None:
                _exert(row, frame, i, scene, pc)
            if act == "request" and pc is not None:
                _request(row, a, scene, pc)
            if act in ("threaten", "use", "other") and pc is not None                     and _dazzling_display(row, a, pc):
                pass
            elif act == "threaten" and pc is not None:
                _threaten(row, a, scene, pc, frame, i, rows)
            if act == "look" and a.get("recall") and pc is not None and not any(
                    (t.get("params") or {}).get("skill", "").startswith("knowledge")
                    for r in rows for t in r.intents):
                _recall(row, a, scene, pc)       # one recall a turn: one memory searched
            if act == "craft" and pc is not None:
                _craft(row, a, pc)
            if act == "loot" and pc is not None:
                _loot(row, frame, i, scene, pc)
            if act == "harvest" and pc is not None:
                _harvest(row, frame, i, scene, pc, rows)
            if act == "stealth" and pc is not None:
                # Hiding behind something of this room moves you there first. Live
                # 2026-11-12, twice: "duck behind the nearest stall" and "slip around
                # behind the bar" were read as stealth (`place` the stall, the bar), and
                # the player never left their square.
                from rules import fixtures as fixtures_mod

                kind = fixtures_mod.held_to_words(
                    getattr(scene, "grid", None), "", str(a.get("place") or ""))
                if kind:
                    _to_the_fixture(row, kind, scene, pc)
                _sneak(row, a, scene, pc)
            if act == "use" and pc is not None and not row.ops:
                if not (_skill_used(row, a, pc) or _put_on(row, a, pc)
                        or _light(row, a, pc)):
                    _draw(row, a, pc)
            if act in ("other", "look", "use") and pc is not None and not row.intents:
                _look_in(row, frame, i, scene, rows, places)
            if act == "disguise" and pc is not None:
                _disguise(row, a, pc)
            if act == "challenge" and pc is not None:
                _challenge(row, a, scene, pc)
            # Taking 10 or 20 is always on the ground at hand: nobody takes 20 on a tavern.
            # And a search at the landmark somebody gave for a way in they spoke of, read
            # "elsewhere" because it looks for somewhere to go: the engine's search looks
            # for that place there (`Engine._search_for_heard`). Playtest 2026-11-20 #2,
            # "I search the woods for the cave everyone has a story about", standing in
            # the woods the carter's old mine is off: it owed no op, and the plan rolled
            # tracks and a secret-door check.
            # And every search that names what it is for (the owner's ruling of
            # 2026-11-20, #19: "If I type to search for anything I should be searching for
            # that thing, not tracks"): the engine answers about that thing
            # (`Engine._sought`). A walk the plan adds to go and find it stays.
            if act == "search" and pc is not None and (
                    a.get("where") == "here" or a.get("take") or a.get("object")
                    or _heard_way_in_here(scene, places)):
                _search(row, a, pc)
            if act == "commission" and pc is not None:
                _commission(row, a, scene, pc)
            if act == "escape" and pc is not None:
                _escape(row, a, scene, pc)
            if act in ("prone", "rise") and pc is not None:
                _posture(row, act, pc)
            if act == "surrender" and pc is not None:
                _surrender(row, a, scene, pc)
            if act in ("fend", "hunt") and pc is not None:
                _fend(row, act, pc)
        rows.append(row)
    # One commission a keeper a turn: "agree to his price and pay" is read as two deeds
    # (`sell`, `give`), and each agrees the same job (`_agreed_work`). The first stands.
    seen: set[str] = set()
    for row in rows:
        for b in list(row.intents):
            if b.get("op") != "commission":
                continue
            who = str((b.get("params") or {}).get("who") or "")
            if who in seen:
                row.intents.remove(b)
                row.note = "the same work agreed once already this turn"
            seen.add(who)
    _take_is_the_harvest(rows)
    _tumbles(rows, frame, scene, pc)
    # One search a turn: "I take my time and go over every brick …, taking twenty on the
    # search" was read as two searches (playtest 2026-11-16, beat 256). The first stands,
    # taking whatever the words took on either.
    first = None
    for row in rows:
        for b in [b for b in row.intents
                  if b.get("op") == "check" and (b.get("params") or {}).get("search")]:
            if first is None:
                first = b
                continue
            if b["params"].get("take", 0) > first["params"].get("take", 0):
                first["params"]["take"] = b["params"]["take"]
            row.intents.remove(b)
            row.note = "the same search once already this turn"
    # One surrender a turn: live 2026-11-15, "shout for the city watch, telling everyone I
    # beat a merchant" was read as two surrenders and the call went out twice.
    given = False
    for row in rows:
        for b in [b for b in row.intents if b.get("op") == "surrender"]:
            if given:
                row.intents.remove(b)
                row.note = "giving themselves up once this turn already"
            given = True
    # A journey is the turn's one move, and it walks the party out from wherever it stands
    # (`Engine._op_journey`: the docks, the quay, the road head, a hex). A walk owed beside
    # it is the same leaving twice, and the engine refuses whichever comes second ("One
    # journey a turn"). Playtest of the owner's save 2026-11-21 (journey-words #1): "I leave
    # the ruins and set out on the road to Brackgate" was read `leave` + `journey`; the
    # leave's travel ran first, founded "the road to Brackgate" in the ruins, walked 8
    # minutes into it, and the journey was refused.
    if any("journey" in r.ops for r in rows):
        for row in rows:
            if "travel" in row.ops:
                row.ops.remove("travel")
                row.note = row.note or "the journey is the way out"
            walks = [b for b in row.intents if b.get("op") in ("travel", "found")]
            if walks:
                row.intents = [b for b in row.intents if b not in walks]
                row.note = row.note or "the journey is the way out"
    return rows


def _take_is_the_harvest(rows: list[Row]) -> None:
    """A take out of a carcass the same sentence harvests is the harvest's own yield, not
    a second deed: the harvest op is what takes parts off a body (`Engine._op_harvest`),
    and the parts it took land in the pack.

    Measured on the narration diagnosis bench (2026-11-04, docs/narration-diagnosis.md,
    mechanism 1 — 14% of the baseline's errors): "I skin the wolf and take its pelt" was
    read `harvest: the wolf` then `take: its pelt, target: the wolf`; the take built a
    give from the wolf, and the engine refused it — "the wolf has no pelt to take.
    Nothing changes hands." — beside the harvest's own "peels the wolf pelt off the wolf".
    One deed, two tells that contradict: the slot followed the refusal, or the tells check
    flagged the true sentence against it. The shape of the 2026-11-02 fix above (a pronoun
    take of a thing the sentence already took): structure only — the give's holder is the
    harvest's carcass, by ref, whichever order the words put them in."""
    carcasses = {str(t.get("target") or "") for r in rows for t in r.intents
                 if t.get("op") == "harvest" and t.get("target")}
    if not carcasses:
        return
    for row in rows:
        if row.act not in ("take", "steal"):
            continue
        folded = [t for t in row.intents if t.get("op") == "give"
                  and str((t.get("params") or {}).get("from_") or "") in carcasses]
        if folded:
            row.intents = [t for t in row.intents if t not in folded]
            row.note = (f"{folded[0]['params'].get('item')} comes off the carcass with the "
                        f"harvest: one deed, not a second take")


def _out_of_the_pit(row: Row, pc) -> None:
    """Leaving, or climbing, at the bottom of a pit is the climb out, built whole: a Climb
    check the engine sets at the pit's DC (`dungeons.climb_out`). Inform's EXIT leaves
    the container you are in, and the pit is that container, so no walk is owed.

    Playtest 2026-11-17 #38: "I climb up out of the pit" read `leave` and built nothing,
    and the next turn's Climb check was the plan's DC 10, which changed nothing."""
    row.ops = []
    row.intents.append({"op": "check", "actor": pc.ref, "params": {"skill": "climb"},
                        "because": "the player climbs out of the pit"})
    row.note = "at the bottom of a pit: the climb out"


def _fend(row: Row, act: str, pc) -> None:
    """Living off the land (`fend`) or hunting (`hunt`), the reader's acts: the engine's
    `live_off_land` (CRB p.107, get along in the wild) or `hunt` op, built whole.
    Whether the ground can feed anybody is the engine's (`Engine._op_live_off_land`).

    The owner's report of 2026-11-17 (#6): three searches for water in a forest built a
    Perception check, a herb forage and a hunt for tracks, and none of them gave water."""
    hunt = act == "hunt"
    row.intents.append({"op": "hunt" if hunt else "live_off_land", "actor": pc.ref,
                        "params": {},
                        "because": "the player hunts" if hunt
                        else "the player lives off the land"})
    row.note = "hunting for game" if hunt else "living off the land"


def _posture(row: Row, act: str, pc) -> None:
    """Down on the ground, or up off it: the `prone` condition on the player, laid or
    lifted through the engine's `condition` op (`Engine._op_condition`). "Drop Prone ...
    is a free action" (CRB p.188); prone is -4 AC against melee and +4 against ranged
    (CRB Appendix 2, `tables.CONDITIONS["prone"]`). Whether they are prone to stand up is
    the sheet's state, asked by tag, never the words.

    Playtest 2026-11-15 #62/#64: "drop to my knees" was read `go`, told "moves from near
    to near", laid nothing, and the sergeant's spear swung six times at standing AC."""
    prone = pc.has_state("state.position.prone")
    if act == "prone" and not prone:
        row.intents.append({"op": "condition", "actor": pc.ref,
                            "params": {"condition": "prone", "to": pc.ref},
                            "because": "the player drops prone"})
        row.note = "down on the ground: prone"
    elif act == "rise" and prone:
        row.intents.append({"op": "condition", "actor": pc.ref,
                            "params": {"condition": "prone", "to": pc.ref, "ends": True},
                            "because": "the player stands up"})
        row.note = "up off the ground"


# How the reader's closed `way` (`interpret.ESCAPE_WAYS`) reaches the engine's `how`.
_ESCAPE_HOW = {"force": "cmb", "slip": "escape artist"}


def _escape(row: Row, a: dict, scene, pc) -> None:
    """Breaking a grapple, built whole: the engine's `escape` op (`Engine._op_escape`), the
    player's combat manoeuvre or Escape Artist against the holder's CMD (CRB p.200). Who
    holds them is the engine's own record, never the words; the words choose a holder only
    when two hold them (`person`). HOW is the reader's closed answer — never read here.

    The owner's report of 2026-11-01: "escape grapple" was read `other`, which owes no op,
    and the planner's own tries were a grapple at the grub (refused five times as "already
    grappled") and an Escape Artist check at DC 10 that removed nothing."""
    params: dict = {}
    how = _ESCAPE_HOW.get(str(a.get("way") or ""))
    if how:
        params["how"] = how
    built: dict = {"op": "escape", "actor": pc.ref, "params": params,
                   "because": "the player breaks the hold"}
    words = " ".join(str(a.get("target") or "").split())
    holder = person(scene, words) if words else ""
    if holder:
        built["target"] = holder
    row.intents.append(built)
    row.note = "a grapple broken: " + (
        {"cmb": "the combat manoeuvre", "escape artist": "Escape Artist"}.get(
            how or "", "the better of the combat manoeuvre and Escape Artist"))


def _surrender(row: Row, a: dict, scene, pc) -> None:
    """Giving yourself up, built whole: the engine's `surrender` op (`Engine._op_surrender`,
    rules/trial.py `give_up`). Who is the law here is the engine's; the words only say
    whom the player turned to first (`person`), never whether they are the law."""
    built: dict = {"op": "surrender", "actor": pc.ref, "params": {},
                   "because": "the player gives themselves up"}
    words = " ".join(str(a.get("target") or "").split())
    who = person(scene, words) if words else ""
    if who:
        built["target"] = who
    row.intents.append(built)
    row.note = "giving themselves up to the law"


def _whose_body(frame, i: int, scene) -> str:
    """The ref of the creature whose body a `loot` or `harvest` act means: the person the
    words name, standing or fallen (`scope.in_the_room`); for a bare pronoun or words that
    name nobody ("her body", "the body"), the one an earlier blow of the same sentence was
    aimed at ("punch until she is dead then loot her"); else the fallen body lying here
    (`scenery.fallen_meant`). The engine's own finders, never the words' meaning. "" when
    there is nobody to mean."""
    from rules import scope

    from . import scenery

    acts = frame.get("actions") or []
    a = acts[i]
    words = " ".join(str(a.get("target") or a.get("object") or "").split())
    actors = getattr(scene, "actors", {}) or {}
    if words and words.lower() not in _PRONOUNS:
        ref = scope.in_the_room(scene, words)
        if ref in actors and not actors[ref].is_pc:
            return ref
    for prev in reversed(acts[:i]):
        if prev.get("act") == "attack" and prev.get("target"):
            ref = person(scene, str(prev["target"]))
            if not ref:
                ref = scope.in_the_room(scene, str(prev["target"]))
            if ref in actors and not actors[ref].is_pc:
                return ref
    if words.lower() in _PRONOUNS:
        fits = [r for r, x in actors.items() if not x.is_pc and x.is_down
                and words.lower() in _pronoun_forms(getattr(x, "pronouns", ""))]
        if len(fits) == 1:
            return fits[0]
    return scenery.fallen_meant(scene, words)


def _loot(row: Row, frame, i, scene, pc) -> None:
    """A body searched, built whole: the engine's `loot` op, which strips the down or dead
    body of everything it carries and refuses, in words, one still on its feet
    (`Engine._op_loot`). Measured on the owner's 0.2.25 report (2026-11-01): read as a
    take, "loot the body" minted `"body": 1` and "…then loot her" was dropped because she
    was not down yet when the plan was read. The blow before it in the same sentence runs
    first, so a body killed by it is a body by the time the loot is resolved."""
    ref = _whose_body(frame, i, scene)
    # Words that name no body ("search the area for more loot", "loot the room") search
    # the room as well: every container lying here that holds something on the record is
    # emptied (`Engine._empty_box`). Owner bug 2026-11-17 #2 (frag, turn 831): the words
    # were read `loot: the area`, the dire rat's picked-clean body was looted again, and
    # the 70 gp hoard on the same floor stayed unopened.
    boxes = [] if _names_a_body(frame, i, scene) else [
        str(r["name"]) for r in _props(scene)
        if r.get("at") == getattr(scene, "at", None) and not r.get("held_by")
        and ((r.get("contents") or {}).get("goods")
             or any((r.get("contents") or {}).get("purse", {}).values()))]
    if not ref and not boxes:
        row.note = "nobody here to loot"
        return
    if ref:
        row.intents.append({"op": "loot", "actor": pc.ref, "params": {"from_": ref},
                            "because": "the player searches the body"})
    for name in boxes:
        row.intents.append({"op": "give", "actor": pc.ref,
                            "params": {"item": "everything", "from_": name, "to": pc.ref},
                            "because": "the player searches the room"})
    who = (getattr(scene, "actors", {}) or {}).get(ref)
    row.note = "; ".join(([f"a loot of {getattr(who, 'name', ref)}"] if ref else [])
                         + [f"{n} emptied" for n in boxes])


def _names_a_body(frame, i: int, scene) -> bool:
    """Whether a loot's words mean one body: a person here they name, a pronoun, or the
    target of a blow earlier in the sentence (`_whose_body`'s first three answers)."""
    from rules import scope

    acts = frame.get("actions") or []
    words = " ".join(str(acts[i].get("target") or acts[i].get("object") or "").split())
    if words.lower() in _PRONOUNS:
        return True
    if words and scope.in_the_room(scene, words) in (getattr(scene, "actors", {}) or {}):
        return True
    return any(p.get("act") == "attack" and p.get("target") for p in acts[:i])


def _harvest(row: Row, frame, i, scene, pc, rows=()) -> None:
    """Parts cut off a carcass, built whole: the engine's `harvest` op, which runs the
    harvest sheet's own rules (rules/harvest.py — the parts the character's crafts can
    take, each its own skill roll at DC 15 + CR, the dangerous body's rounds first) and
    refuses, in words, a body still breathing or one with nothing left to take. The part
    named, when one is, narrows it (`part`: the words, matched against the sheet's own
    rows by the engine). Measured on the owner's report: "kill it and skin iot for parts"
    was read as leatherworking and refused for want of a tannery."""
    ref = _whose_body(frame, i, scene)
    if not ref:
        row.note = "no carcass here to harvest"
        return
    body = (getattr(scene, "actors", {}) or {}).get(ref)
    if body is not None and not body.has_state("state.down.dead") \
            and (body.is_down or body.has_state("state.helpless")):
        # A knife put into a body that still breathes is the killing blow first: 1e's coup
        # de grâce (CRB p.197), the act table's own answer for a blow at somebody down
        # (`victims`). Measured on the narration diagnosis bench (2026-11-04): "I cut the
        # dying bandit's throat" was read `harvest: the dying bandit`, and the engine
        # refused it — "still breathing: nothing is cut from a living body" — so the
        # killing the words did was never done. The engine's state decides, never the
        # words: down and not dead. The harvest stays only for a body the sheet could take
        # parts off once dead (`harvest.banned`, `harvest.tagged`): a throat cut on a
        # bandit is a killing and nothing more.
        from rules import harvest as hv

        row.intents.append({"op": "attack", "actor": pc.ref, "target": ref,
                            "params": {"coup_de_grace": True},
                            "because": f"the player cuts into {body.name}, who still "
                                       f"breathes"})
        yields = not hv.banned(hv.block_of(body)) and bool(hv.tagged(body))
        row.note = (f"{body.name} still breathes: a coup de grâce"
                    + (", then the harvest" if yields else ", and nothing to harvest"))
        if not yields:
            return
    a = frame["actions"][i]
    part = " ".join(str(a.get("object") or "").split())
    if part and person(scene, part) == ref:
        part = ""
    # Two harvest deeds of one sentence on one carcass ("skin the boar and cut out its
    # tusks") are one sitting at it: the parts named are added to the first.
    first = next((t for r in rows for t in r.intents
                  if t.get("op") == "harvest" and t.get("target") == ref), None)
    if first is not None:
        if part:
            have = first["params"].setdefault("parts", [])
            if part not in have:
                have.append(part)
        row.note = "the same carcass, the same sitting"
        return
    params: dict = {"parts": [part]} if part else {}
    row.intents.append({"op": "harvest", "actor": pc.ref, "target": ref, "params": params,
                        "because": "the player cuts parts off the carcass"})
    who = (getattr(scene, "actors", {}) or {}).get(ref)
    row.note = f"a harvest of {getattr(who, 'name', ref)}"


def _draw(row: Row, a: dict, pc) -> None:
    """A weapon the player carries and does not hold, used: drawn, through the `wear` door
    every draw takes (`Engine._draw_before`), which prices it in a fight.

    Live 2026-11-12, three fights running: "I draw my rapier and ..." was read `use: my
    rapier`, the act owed no op, and the page said "You draw your rapier" while the rapier
    stayed on the belt. shortcut: weapons the sheet lists only, not crafted ones; widen when
    a crafted blade is drawn this way."""
    from rules import weapons as weapons_mod

    want = weapons_mod.key_for(str(a.get("object") or ""))
    if not want or want == weapons_mod.key_for(str(pc.equipped or "")):
        return
    carried = next((w for w in pc.weapons if w and weapons_mod.key_for(str(w)) == want), None)
    if carried is not None:
        row.intents.append({"op": "wear", "actor": pc.ref,
                            "params": {"item": str(carried), "actor": pc.ref},
                            "because": f"the player draws the {carried}"})


def _light(row: Row, a: dict, pc) -> bool:
    """A `use` of a thing on the player's shelf that gives light (a torch, a sunrod: its
    own `light` document, `consumables._light`): the `use_item` that lights it, through
    the engine's door. True when it was built.

    Playtest 2026-11-17 #13 and #15: "I light a torch" and "I light one of my torches",
    three torches on the shelf, built no op either way, and the page lit a torch the engine
    never did — on the way into a dark dungeon. The shelf's own record says what lights,
    never the verb: "use my torch" and "light my torch" are one deed. And 2026-11-17b #3:
    "a fresh torch" is the torch, its name found whole among the words — among the things
    that light only, so "the torch with my flint and steel" is still the torch."""
    from rules import consumables, holding

    def lights(item) -> bool:
        return any(str(s.get("type")) in ("light", "manifest")
                   for s in consumables._specs(item))

    shelf = getattr(pc, "stock", {}) or {}
    said = " ".join(str(a.get("object") or "").split())
    sid = _stock_id(pc, said) if said else ""
    if said and (not sid or not lights(shelf[sid])):
        sid = holding.stock_among({k: v for k, v in shelf.items() if lights(v)}, said)
    held = shelf.get(sid) if sid else None
    if held is None or not lights(held):
        return False
    row.intents.append({"op": "use_item", "actor": pc.ref,
                        "params": {"item": sid, "how": "light"},
                        "because": f"the player lights the {held.name}"})
    row.note = f"lights the {held.name}"
    return True


def _look_in(row: Row, frame, i: int, scene, rows=(), places=()) -> None:
    """Opening or looking into a container that holds something on the engine's record
    ("open the gaoler's box", "see what's inside" after it): `narrate_only` with
    `looks_in`, which tells the contents (`Engine._looks_in`). Once a box a turn.
    Playtest 2026-11-17 #41: the prose pried the lid and never said what was inside.
    The record decides — a container named here with `contents` — never the verb.

    "Here" is where the sentence has walked by then: R1 of 2026-11-17, "I go to the broken
    pen and open the gaoler's box to see what's inside" from the cells, looked for the box
    in the cells, found none, and nothing was said of the 50 gp in it. One action at a
    time, each against the place the last one leaves (Inform's DM4 §34, as `order`)."""
    from rules import holding
    from rules import places as places_mod

    from . import interpret

    acts = frame.get("actions") or []
    said = " ".join(str(acts[i].get("object") or "").split())
    boxes = getattr(scene, "props", None) or ()
    if said and not holding.is_box(said, boxes) and (
            set(re.findall(r"[a-z]+", _plain(said))) & _WHOLE or said.lower() in _IT):
        # "what's inside", "it": the container of the deed before it.
        said = next((" ".join(str(p.get("object") or "").split())
                     for p in reversed(acts[:i])
                     if holding.is_box(str(p.get("object") or ""), boxes)), "")
    if not said or not holding.is_box(said, boxes):
        return
    want = holding.head_of(said)
    here = str(getattr(scene, "at", "") or "")
    for p in acts[:i]:
        if places and p.get("act") == "go" and p.get("place") and interpret.acting(p):
            went = places_mod.find(places, str(p["place"]), near=here)
            here = went.id if went is not None else here
    pc = scene.pc()
    if not any("contents" in r and (holding.same(r.get("name"), said)
                                    or holding.head_of(r.get("name")) == want)
               and (r.get("at") == here or r.get("held_by") == pc.ref)
               for r in getattr(scene, "props", None) or ()):
        return
    if any(b.get("params", {}).get("looks_in") and holding.head_of(b["params"]["looks_in"])
           == want for r in rows for b in r.intents):
        return
    row.intents.append({"op": "narrate_only", "actor": pc.ref,
                        "params": {"looks_in": _plain(said)},
                        "because": "the player looks inside"})


def _challenge(row: Row, a: dict, scene, pc) -> None:
    """A bout asked for, built whole: the engine's `bout` op (`Engine._op_bout`), which
    an arena's house stages and anywhere else refuses with who does. Playtest 2026-11-17b
    #24: "Put me in the next bout" to the master of the games built nothing. A challenge to
    somebody here by name who is not the keeper of this place is theirs to answer in
    words, and builds nothing (a sparring match with a soldier is not built)."""
    from rules import keepers

    words = " ".join(str(a.get("target") or "").split())
    who = person(scene, words) if words else ""
    actor = (getattr(scene, "actors", {}) or {}).get(who) if who else None
    if actor is not None \
            and actor is not keepers.keeper_in(scene, str(getattr(scene, "at", "") or "")):
        return
    row.intents.append({"op": "bout", "actor": pc.ref, "params": {},
                        "because": "the player asks for a bout"})
    row.note = "a bout asked for"


def _disguise(row: Row, a: dict, pc, what: str | None = None) -> None:
    """A disguise, built whole: the engine's `disguise` op (`Engine._op_disguise`), with the
    reader's object as who the character passes for. Playtest 2026-11-15 #83: the same
    words rolled a plan's check one turn and nothing the next."""
    what = " ".join(str(a.get("object") if what is None else what or "").split())
    row.intents.append({"op": "disguise", "actor": pc.ref,
                        "params": {"as": what} if what else {},
                        "because": "the player makes a disguise"})
    row.note = "a disguise: one secret Disguise check, held"


def _skill_named(words) -> str:
    """The skill a `use` names ("my Disguise skill", "Perception"), from the engine's own
    skill table, or "". A closed vocabulary, as an ability's name is matched against the
    sheet; the words around it ("my", "skill") are the frame, not a reading of intent."""
    from rules import tables

    low = [w for w in str(words or "").lower().replace("'s", "").split()
           if w not in ("my", "the", "her", "his", "their", "skill", "skills", "own")]
    name = " ".join(low)
    return name if name in tables.SKILLS else ""


def _skill_used(row: Row, a: dict, pc) -> bool:
    """A `use` of the Disguise skill by name is the disguise op. Playtest 2026-11-15 #80: "I
    use my Disguise skill to make myself look like a dock labourer" was refused "There is
    no disguise skill here" — the skill's name looked for as an item. Any other skill
    named is left to its own builder (the Heal skill is `first_aid`'s) and to the plan's
    check, and is never asked about as a thing (`scenery.handled`)."""
    skill = _skill_named(a.get("power")) or _skill_named(a.get("object"))
    if skill != "disguise":
        return False
    _disguise(row, a, pc, what="")
    return True


def _put_on(row: Row, a: dict, pc) -> bool:
    """A `use` that puts on an outfit the player carries: the `wear` op, which changes the
    body slot (`Engine._change_clothes`). Playtest 2026-11-15 #79: "I change into the new
    traveler's outfit" was read but no op owed it, and the outfit stayed in the pack."""
    from rules import goods

    said = " ".join(str(a.get("object") or "").split())
    key = _carried(pc, said)
    if not key:
        # "the new traveler's outfit": the pack's own outfit named whole among other words.
        # The pack is the closed vocabulary here, matched word for word, never the reverse.
        words = set(said.lower().split())
        fits = [k for k in (getattr(pc, "goods", {}) or {})
                if goods.is_clothes(k) and set(k.lower().split()) <= words]
        key = fits[0] if len(fits) == 1 else ""
    if not key or not goods.is_clothes(key):
        return False
    row.intents.append({"op": "wear", "actor": pc.ref,
                        "params": {"item": key, "actor": pc.ref},
                        "because": f"the player changes into the {key}"})
    row.note = f"changes into the {key}"
    return True


def _sneak(row: Row, a: dict, scene, pc) -> None:
    """A hiding, built whole: the player's Stealth check opposed by whoever here is
    likeliest to notice (`judgement.stealth_opposed`, CRB p.106), at the pace the words
    chose (`interpret.PACES`: hurried is the -5 band, `pace: full`), and — when the same
    words first pull the watchers' eyes away (`interpret.DIVERSIONS`) — the Bluff that
    makes the diversion, ahead of it (`diversion: true`; Stealth, CRB p.106: "You can use
    Bluff to allow you to use Stealth").

    Both closed answers are the reader's, never a word list (the owner's direction of
    2026-10-03, docs/structured-turn.md). The plan's own Stealth or Bluff check for the
    same deed is replaced by these (`apply`'s built-check rule), so one hiding rolls once.
    With nobody here to hide from there is nothing to roll, as before."""
    from . import judgement

    opposed = judgement.stealth_opposed(scene)
    if opposed is None:
        row.note = "a hiding with nobody here to notice: nothing to roll"
        return
    params: dict = {"skill": "stealth", "opposed_by": opposed}
    if a.get("pace") == "hurried":
        params["pace"] = "full"
    if a.get("diversion") == "bluff":
        row.intents.append({"op": "check", "actor": pc.ref,
                            "params": {"skill": "bluff", "diversion": True},
                            "because": "the player draws the watchers' eyes away"})
    row.intents.append({"op": "check", "actor": pc.ref, "params": params,
                        "because": "the player hides"})
    row.note = ("a Bluff to divert, then " if a.get("diversion") == "bluff" else "") + (
        "Stealth at full speed (-5)" if params.get("pace") else "Stealth at half speed")


def _heard_way_in_here(scene, places) -> bool:
    """Whether a heard-of way in (`heard_places.ventures_at`) has its landmark where the
    party stands."""
    from rules import heard_places
    from rules import places as places_mod

    if scene is None or not getattr(scene, "heard_places", None):
        return False
    here = places_mod.find(places or (), getattr(scene, "at", "") or "")
    return bool(heard_places.ventures_at(scene, here, places or ()))


def _search(row: Row, a: dict, pc) -> None:
    """A search of where the player is (`interpret.SEARCH_WHERE` here), built whole: the
    engine's Perception search, one roll against everything hidden here at its own DC
    (`Engine._player_search`) — never a DC of the plan's. Taking 10 or 20 is the reader's
    closed `take` (CRB p.86); whether it may be taken is the engine's.

    Playtest 2026-11-16: the search act owed no op, and of five searches for a hidden way
    down the plan rolled Survival twice ("finding tracks", "inspecting the masonry"),
    Perception at its own "average (DC 10)" three times, and a forage once for a ship's
    hold; the dungeon's own search at DC 20 ran on none of them."""
    params: dict = {"skill": "perception", "search": True}
    take = {"ten": 10, "twenty": 20}.get(str(a.get("take") or ""))
    if take:
        params["take"] = take
    # What it is for: the player's words, and the reader's closed kind of thing.
    sought = " ".join(str(a.get("object") or "").split())
    if sought:
        params["sought"] = sought[:80]
    if a.get("seeking") and a["seeking"] != "anything":
        params["seeking"] = str(a["seeking"])
    row.intents.append({"op": "check", "actor": pc.ref, "params": params,
                        "because": "the player searches"})
    row.note = f"a Perception search, taking {take}" if take else "a Perception search"


def _craft(row: Row, a: dict, pc) -> None:
    """A craft worked by the player's own hands, built whole: the engine's `make` op
    (rules/typed_craft.py), which walks the bench's chain for the base item — the player's
    d20 per step, the materials out of the pack, the time, the item and the mastery.

    The report, 2026-10-28: "My wife tries to level up blacksmithing through narration and
    didn't get real items or experience." The reader read every craft line `other`, which
    owes no op. Which craft and how fine are the reader's closed answers (`interpret.CRAFTS`,
    `WORKS`); what is made is the player's own words, grounded in the craft's catalogue by
    the engine's finders, never here."""
    params = {"craft": str(a.get("craft") or ""), "work": str(a.get("work") or "plain")}
    if a.get("object"):
        params["item"] = " ".join(str(a["object"]).split())
    if a.get("span"):
        params["words"] = " ".join(str(a["span"]).split())
    row.intents.append({"op": "make", "actor": pc.ref, "params": params,
                        "because": "the player works at their craft"})
    row.note = f"a {params['craft']}'s work: {params.get('item') or 'unnamed'}"


# The band a feat of strength is built at before the plan names one (`apply` carries the
# plan's own band over): the book's "average" task, DC 10 (rules/tables.py DC_BANDS).
EXERT_BAND = "average"


def _exert(row: Row, frame, i, scene, pc) -> None:
    """A feat of strength, built whole: the player's Strength check (CRB p.16), or — with
    somebody here as the target — Aid Another on THEIR effort (CRB p.86): the player's
    check against the book's 10, and the helped person's own check, +2 if it made it,
    against the task (`Engine._aid_lands`).

    The owner, 2026-10-16: "a man needed help with his cart. When she helped him the game
    narrated that i lifted his cart but never gave a strength check." The reader read
    every such line `other`, which owes no op. The skill and the target are the engine's
    finders' (`person`); the plan is asked only how hard the task is — the `check` it must
    declare, whose band `apply` carries over and whose op it replaces. A door forced is
    `break_in`'s, which keeps its own path (the size bonus is the book's for doors).

    Carrying capacity (CRB p.169, "Lifting and Dragging": overhead up to the maximum
    load, off the ground twice it, push or drag five times it) is not used: it needs the
    thing's weight, and nothing a player heaves at — a cart in the mud, a beam, a boulder —
    is a record with one; what the pack holds is already lifted."""
    a = frame["actions"][i]
    words = " ".join(str(a.get("target") or "").split())
    helped = person(scene, words) if words else ""
    who = (getattr(scene, "actors", {}) or {}).get(helped) if helped else None
    params: dict = {"skill": "strength", "dc": {"band": EXERT_BAND}}
    built: dict = {"op": "check", "actor": pc.ref, "params": params,
                   "because": "the player puts their strength to it"}
    from rules import ontheway

    walk = ontheway.walk_cut(scene, pc)
    if who is not None and not who.is_pc and not who.is_down \
            and not (walk and who.ref in (walk.get("by") or ())):
        params["aid"] = True
        built["target"] = who.ref
        built["because"] = f"the player helps {who.name} with it"
        row.note = f"Aid Another: {who.name}'s own effort, the player's check at DC 10"
    elif walk is not None and walk.get("kind") != "watch":
        # Shoving through where a walk was cut short — at the crowd, at the people who
        # stopped it, or at nobody named — is a push past them: made, the walk goes on to
        # where it was for (`Engine._drive`, the check's `past`). Owner report
        # 2026-11-01 (Corvin, turn 13): "Try to push through the crowd" made its Strength
        # check by 6, and the walk to the smithy never resumed. Helping somebody else
        # with their load is still Aid Another (above); the watch is not shoved past.
        params["past"] = True
        built["because"] = f"the player pushes through, making for {walk['name']}"
        row.note = f"a Strength check to push through; made, on to {walk['name']}"
    else:
        row.note = "a Strength check, the player's own"
    row.intents.append(built)
    # The plan names how hard the task is in the check it is required to write; `apply`
    # takes its band and replaces it with this one.
    row.ops = list(dict.fromkeys([*row.ops, "check"]))


def _commission(row: Row, a: dict, scene, pc) -> None:
    """Paying a keeper to work the player's things, built whole (rules/commission.py).

    The keeper is whoever the words name here, else the one keeper here who works a craft,
    else the one the player is talking to; their craft is read off their trade by the
    engine. The thing is the reading's own words for it. Owner report 2026-11-01 (Corvin,
    turn 22): "can you put them together and i will give you 10 gold" to the smith, about
    a forged trident blank, owed no op and the fitting was narrated, never done."""
    from rules import commission

    actors = getattr(scene, "actors", {}) or {}
    words = " ".join(str(a.get("target") or "").split())
    ref = person(scene, words) if words else ""
    if not ref:
        crafty = [r for r, x in actors.items() if not x.is_pc and not x.is_down
                  and commission.craft_of(x)]
        ref = crafty[0] if len(crafty) == 1 else addressed(scene)
    who = actors.get(ref) if ref else None
    if who is None or who.is_pc:
        row.note = "nobody here named to do the work"
        return
    params = {"who": who.ref, "item": " ".join(str(a.get("object") or "").split())}
    if row.commit == "tried":
        # Offered rather than agreed ("I offer the smith five silver to fit it", "I try to
        # get him to do it cheaper"): the price is open, and the engine haggles it with the
        # player's Diplomacy before the job is taken (rules/commission.py `_haggle`). The
        # commitment is the reader's closed answer; no word of the sentence is read here.
        params["haggle"] = True
    row.intents.append({"op": "commission", "actor": pc.ref, "params": params,
                        "because": f"the player pays {who.name} to do the work"})
    row.note = f"{who.name} is asked to do the work for pay"


def fold_price_talk(raw, notes=None):
    """A Diplomacy check at the keeper this turn commissions is the commission's haggle.

    Measured live 2026-11-01 on the integration build: "I ask the smith to finish my
    trident for me, and I try to talk him down on the price" was read as a commission
    beside a tried talk, and a plain Diplomacy check at the smith reached the engine — the
    plan's, or `judgement.inject_checks`'s from the words, which runs after `apply`. It made
    DC 14 by 2, the smith warmed, and the job was taken at the full list price. The check
    is folded into the commission's own haggle (rules/commission.py `_haggle`) wherever it
    came from, so this runs inside `apply` and again after the check injectors
    (`gm/agent.py`). A Diplomacy check at anybody else is left alone."""
    if not isinstance(raw, list):
        return raw
    commissioned = {str(((r or {}).get("params") or {}).get("who")): r for r in raw
                    if isinstance(r, dict) and _op(r) == "commission"}
    if not commissioned:
        return raw
    out = []
    for r in raw:
        if isinstance(r, dict) and _op(r) == "check":
            p = r.get("params") or {}
            ob = p.get("opposed_by") if isinstance(p.get("opposed_by"), dict) else {}
            at = str(r.get("target") or ob.get("ref") or "")
            if str(p.get("skill") or "").lower() == "diplomacy" and at in commissioned:
                commissioned[at].setdefault("params", {})["haggle"] = True
                if notes is not None:
                    notes.append("the Diplomacy at the keeper folded into the "
                                 "commission's own haggle")
                continue
        out.append(r)
    return out


def _greet(row: Row, a: dict, scene, pc, approached: str = "") -> None:
    """Speaking to somebody here with no words given opens the talk (`greet`), built whole.

    Owner report 2026-11-01 (Corvin, turns 61, 62 and 66): "Speak to Snik Dunmoor." and "go
    back to the guards and ask what they called me for" were read `talk` with a person and
    no `says`; `say` needs words, so the table owed nothing, the plan narrated, and no
    conversation opened. The person is the engine's finder's (`person`); a bare pronoun
    after a walk up to somebody here is the one walked up to."""
    words = " ".join(str(a.get("target") or "").split())
    ref = ""
    if words and not (approached and words.lower() in _PRONOUNS):
        ref = person(scene, words)
    if not ref:
        ref = approached
    who = (getattr(scene, "actors", {}) or {}).get(ref) if ref else None
    if who is None or who.is_pc:
        return
    from rules import states

    if who.has_state(states.TALKING):
        return
    row.intents.append({"op": "greet", "actor": pc.ref, "params": {"who": who.ref},
                        "because": f"the player speaks to {who.name}"})
    row.note = f"the talk with {who.name} opens; no words were given"


def _carry_on(row: Row, scene, pc) -> None:
    """A walk with nowhere named, where the last walk was cut short, goes on to where that
    walk was for (`ontheway.walk_cut`). Owner report 2026-11-01 (Corvin, turns 14-15): after
    the crowd at the north crossing, "keep walking" was read `go` with no place, owed no
    op, and the plan narrated standing still — twice. Built whole: the place is the
    engine's record of the walk, never the plan's guess."""
    from rules import ontheway

    walk = ontheway.walk_cut(scene, pc)
    if walk is None:
        return
    row.intents.append({"op": "travel", "actor": pc.ref, "params": {"place": walk["to"]},
                        "because": f"on to {walk['name']}, where the walk was going"})
    row.note = f"the walk goes on to {walk['name']}"


# A room the player holds at an inn, by the head nouns a bed is asked for by: the same closed
# vocabulary shape as DWELLINGS, asked only while a room is held (`lodging.room_held`).
_MY_ROOM_WORDS = frozenset({"room", "rooms", "bed", "bedroom", "chamber", "bedchamber",
                            "quarters", "lodging", "lodgings"})


def _to_my_room(row: Row, phrase: str, scene, places, pc) -> bool:
    """A walk to the room the player paid for — "my room", "the room i paid for" — is the
    walk up to the inn's upper floor while the room is held (its ground floor where the
    house has none). True when it was settled here. frag T113 (owner's save 2026-11-17):
    "go to the room i paid for" was "You don't know of anywhere called…", and the prose
    said the only beds were the floor by the hearth, of a good room bought that night."""
    from rules import lodging
    from rules import places as places_mod

    held = lodging.room_held(pc)
    words = set(re.findall(r"[a-z]+", phrase.lower()))
    if held is None or not (words & _MY_ROOM_WORDS) or places_mod.find(places, phrase):
        return False
    house = places_mod.base_of(held[0])
    up = places_mod.storey_id(house, 1)
    target = next((p for p in places or () if p.id == up), None) \
        or next((p for p in places or () if p.id == house), None)
    if target is None:
        return False
    if target.id == getattr(scene, "at", None):
        row.note = "already in the room the player holds"
    else:
        row.intents.append({"op": "travel", "actor": pc.ref,
                            "params": {"place": target.name},
                            "because": f"to the {held[1]} room the player holds"})
        row.note = f"{phrase}: the {held[1]} room held at {target.name}"
    return True


def _to_the_town(row: Row, phrase: str, scene, places, pc) -> None:
    """A walk to the settlement named whole — "the town", "the city", its own name — is a
    walk to its way in from outside, or to its middle from inside
    (`places.the_settlement`), built whole. Owner report 2026-11-01 (Corvin, turn 35): "go
    to the town" from the smithy was read `go: the town`, owed no op (no place is called
    that), and the plan's travel had nowhere in it."""
    from rules import places as places_mod
    from rules import residency

    if places_mod.find(places, phrase) is not None:
        return
    world = residency._world(None)
    found = world.get(getattr(scene, "location_id", "")) if world is not None else None
    target = places_mod.the_settlement(places, phrase, str(getattr(scene, "at", "") or ""),
                                       str(getattr(found, "name", "") or ""))
    if target is None or target.id == getattr(scene, "at", None):
        return
    row.intents.append({"op": "travel", "actor": pc.ref, "params": {"place": target.name},
                        "because": f"to {target.name}, where {phrase} is from here"})
    row.note = f"{phrase}: {target.name} from here"


# --- going home with somebody standing here ---------------------------------------------
#
# Measured on the owner's save of 2026-11-05 (Pangrella, the market; turn_log rows 47-69).
# Ariniel Thorne, helpful, stood beside the player. "I follow Ariniel Thorne to her private
# quarters" was read `follow: Ariniel Thorne` and `go, commit: intended, place: her private
# quarters`; the table built nothing ("intended, not done this turn: no op"), the plan
# walked a square toward her, and three more tries ended "You remain in the market".
# The engine had no route at all: `call_on` refuses a person who is here ("there is no
# need to go to their door"), and no place is called "her private quarters".
#
# The reader's closed answer carries the parts: the act (`go`, `call_on`, `follow`) and the
# person (`follow`'s target, or the possessor in the place slot, resolved by `person` —
# the engine's people, never a guess). What it does not carry is that the place is a
# DWELLING; the slot is free text. So the one judgement left to code is a closed noun list,
# asked of the place slot's head word only — the same shape as `interpret._OUTWARD_WORDS`,
# a vocabulary rather than a reading of the sentence. The closed reader answer that would
# retire it (a `home_of` field on the go act, or a demonstration reading "I follow Mara to
# her house" as `follow` + `call_on`) is a reader-prompt change, measurable only live.
DWELLINGS = frozenset({
    "house", "home", "quarters", "rooms", "room", "lodgings", "lodging", "cottage", "hovel",
    "hut", "cabin", "chambers", "chamber", "bedroom", "bedchamber", "apartment",
    "apartments", "flat", "place", "dwelling", "residence", "abode", "digs"})
_POSSESSIVE = frozenset({"her", "his", "their"})


def _dwelling_owner(place, scene, led: str = "") -> str:
    """The ref of the person here whose home the place slot names, or "".

    The head word (the slot's last) is a dwelling noun (`DWELLINGS`), and the owner is the
    possessor before it — "her", "his", "their" (the person `led` when the same sentence
    follows somebody, else the pronoun through `person`), or a name with "'s" — or, with
    no possessor and an article, the person the sentence follows ("I follow Mara to the
    house"). "the quarters" alone, with nobody followed, names nobody's."""
    words = " ".join(str(place or "").lower().replace("’", "'").split()).split()
    if not words or words[-1].strip(".,;!?") not in DWELLINGS:
        return ""
    first = words[0]
    if first in _POSSESSIVE:
        return _by_pronoun(scene, first, led)
    owner = []
    for w in words[:-1]:
        owner.append(w)
        if w.endswith("'s") or w.endswith("s'"):
            said = " ".join(owner)
            said = said[:-2] if said.endswith("'s") else said[:-1]
            return person(scene, said)
    if led and first in ("the", "a"):
        return led
    return ""


def _by_pronoun(scene, pronoun: str, led: str = "") -> str:
    """Whose home "her", "his" or "their" means, from the engine's state: the person the
    same sentence follows; else the one person the player is dealing with (`addressed`),
    when the pronoun fits them. Never just any woman here: "I go to her house" after
    asking where the bread seller lives means the bread seller, whose door `call_on`'s own
    pronoun rule finds (`Engine._callee`), not a stranger standing beside the player."""
    if led:
        return led
    ref = addressed(scene)
    who = (getattr(scene, "actors", {}) or {}).get(ref)
    if who is None or pronoun.lower() not in _pronoun_forms(getattr(who, "pronouns", "")):
        return ""
    # Not when the character knows somebody's home and not this person's: the pronoun may
    # be that somebody's, as the engine's own finder reads it (`Engine._callee`), so the
    # plain call decides. Asked as a prefix of the tag vocabulary (law one).
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is not None and pc.has_state("knows.home"):
        from rules import population

        try:
            rec = population.of_ref(scene, ref)
        except Exception:  # noqa: BLE001 — a scene without a population answers no
            rec = None
        keys = {ref, str(getattr(who, "world_entity_id", "") or ""),
                str((rec or {}).get("id") or "")} - {""}
        if not any(pc.has_state(f"knows.home.{k}") for k in keys):
            return ""
    return ref


def _followed_here(frame: dict | None, scene) -> str:
    """The ref of the person here a `follow` act done or tried now follows, or ""."""
    from . import interpret

    for a in (frame or {}).get("actions") or []:
        if isinstance(a, dict) and a.get("act") == "follow" and interpret.acting(a):
            ref = person(scene, a.get("target"))
            if ref:
                return ref
    return ""


def _walk_rides_the_follow(frame: dict | None, scene) -> str:
    """A walk the reading marked intended, in a sentence that follows somebody standing
    here now, is done now: "I follow Ariniel Thorne to her private quarters" is one deed
    with its destination, not a follow and a plan. Row 56 of the owner's save (2026-11-05)
    came back `follow` (done) and `go, commit: intended`; the table's "intended, not done
    this turn" rule dropped the go and the turn moved nobody. Structure only: the
    reading's acts and commits, and `person` over the engine's people. The go's commit is
    rewritten on the frame, so every later reader (`ops_for`, `supported`, the brief)
    sees one answer. Returns the followed ref, "" when nobody here is followed."""
    led = _followed_here(frame, scene)
    if not led:
        return ""
    for a in (frame or {}).get("actions") or []:
        if isinstance(a, dict) and a.get("act") == "go" and a.get("place") \
                and str(a.get("commit") or "done") == "intended":
            a["commit"] = "done"
            a["commit_was"] = "intended"
    return led


def _home_together(row: Row, ref: str, scene, pc) -> None:
    """The walk home with the person here, built whole: `call_on` with `together`, which
    the engine answers from their attitude and makes their house if it has none
    (`Engine._home_together`)."""
    who = (getattr(scene, "actors", {}) or {}).get(ref)
    if who is None or who.is_pc:
        return
    row.intents.append({"op": "call_on", "actor": pc.ref,
                        "params": {"who": ref, "together": True},
                        "because": f"the player goes home with {who.name}"})
    row.ops = []
    row.note = f"home with {who.name}, who is here"


def _a_square(frame, i: int, scene) -> bool:
    """Whether action `i` of the reading names a square of this board (`_to_the_square`'s
    own read: `fixtures.square_said`)."""
    from rules import fixtures

    acts = (frame or {}).get("actions") or []
    grid = getattr(scene, "grid", None)
    if grid is None or not 0 <= i < len(acts):
        return False
    a = acts[i]
    return fixtures.square_said(grid, f"{a.get('place') or ''} {a.get('span') or ''}"
                                .upper()) is not None


def _to_the_square(row: Row, a: dict, scene, pc) -> bool:
    """A walk to a square the board names by its printed coordinate ("I stand at C5",
    `fixtures.square_said`): the move to it, or the reason there is none. False when the
    words name no square of this board. The owner, 2026-11-12: "display coordinates on the
    map so that the user can be precise about where he wants to stand even outside of
    combat"."""
    from rules import fixtures

    grid = getattr(scene, "grid", None)
    words = f"{a.get('place') or ''} {a.get('span') or ''}".upper()
    sq = fixtures.square_said(grid, words)
    if sq is None:
        return False
    row.ops = []
    name = fixtures.square_name(sq)
    if sq in grid.blocked or not grid.passable(sq):
        row.nowhere = f"{name} is solid: nobody can stand there."
    elif sq in scene.occupied(ignore=pc.ref):
        row.nowhere = f"Somebody already stands at {name}."
    elif tuple(scene.positions.get(pc.ref) or ())[:2] != sq:
        row.intents.append({"op": "move", "actor": pc.ref,
                            "params": {"who": pc.ref, "square": [*sq, grid.ground(sq)]},
                            "because": f"the player walks to {name}"})
    return True


def _to_the_fixture(row: Row, kind: str, scene, pc) -> None:
    """The move a walk to a fixture of this room owes (`fixtures.walk_to`).

    The gate, 2026-11-11: "I walk up the stair onto the wall-walk above the gate" read as
    two walks within the place, `fixture: stair` and the wall-walk, and the table built
    nothing for either ("a move inside the place: no travel"); the plan's travel to the
    gate answered "You are already at the gate", the token stayed at (2, 3) on the ground,
    and the page said "You climb the stone stairs and step onto the wall-walk". Moving
    about the place is free of time (2026-11-06), not free of happening."""
    from rules import fixtures

    square, why = fixtures.walk_to(scene, kind, pc)
    if square is not None:
        here = getattr(getattr(scene, "grid", None), "fixtures", None) or []
        name = next((f["name"] for f in here if f["kind"] == kind),
                    "the floor" if kind == fixtures.FLOOR else kind)
        row.intents.append({"op": "move", "actor": pc.ref,
                            "params": {"who": pc.ref, "square": list(square)},
                            "because": f"the player walks to {name}"})
        row.note = ""
    elif why:
        row.nowhere = why


def _a_step(row: Row, scene, pc) -> None:
    """A walk that names nowhere, in a fight, is a step: one square, back from whoever
    stands nearest (the 5-foot step, CRB p.189). Playtest 2026-11-15 #60: "I raise my
    hands, step back and surrender" was read `go` with no place, the plan chose square
    (0, 0) itself, and she ran 30 ft out into open ground. A square the player never named
    is the plan's to invent no longer.
    shortcut: always back, away from the nearest person; "step forward" with nobody named
    reads the same, and wants a direction slot on `go` if it is ever measured."""
    grid = getattr(scene, "grid", None)
    here = (getattr(scene, "positions", {}) or {}).get(pc.ref)
    if grid is None or here is None:
        return
    others = [tuple(p)[:2] for r, p in (scene.positions or {}).items()
              if r != pc.ref and r in (getattr(scene, "actors", {}) or {})
              and not scene.actors[r].is_down]
    if not others:
        return
    x, y = tuple(here)[:2]
    near = min(others, key=lambda p: max(abs(p[0] - x), abs(p[1] - y)))
    taken = {tuple(p)[:2] for r, p in scene.positions.items() if r != pc.ref}

    def apart(p):
        return max(abs(p[0] - near[0]), abs(p[1] - near[1]))

    steps = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
             if (dx or dy) and (x + dx, y + dy) not in taken
             and grid.passable((x + dx, y + dy))]
    steps = [p for p in steps if apart(p) > apart((x, y))]
    if not steps:
        return
    to = min(steps, key=lambda p: (-apart(p), abs(p[0] - x) + abs(p[1] - y), p))
    row.intents.append({"op": "move", "actor": pc.ref,
                        "params": {"who": pc.ref, "square": list(to)},
                        "because": "the player takes a step back"})
    row.note = "a step back: one square"


def _nowhere(row: Row, a: dict, scene, places) -> None:
    """A walk to a place the engine cannot find, with nothing built for it, records the
    printable answer (`nowhere_to_go` prints it when the plan moves nobody either).

    Row 69 of the owner's save (2026-11-05): "Continue walking toward the quarters" was
    read `go: the quarters`; no place is called that, no op was owed, the plan wrote a
    bare `narrate_only`, and the page said "You remain in the market" — a beat in which
    nothing happened and nothing said why. Not for a fixture of the room the party stands
    in ("the counter", "the far corner": `judgement._FIXTURES`, the closed list the
    within-scene rule reads), which is a walk across the room.

    Nor for any move inside the place (`interpret.within_place`: the reader's closed
    `within_place`, else the part of the room before "of"). The live check of 2026-11-07:
    "I run to the other side of the room and begin cooking dinner" was refused here as
    nowhere known — the old test read only the phrase's last word, "room" — and the beat
    then said "You move toward the hearth … You remain where you are". Moving about the
    place you are in is free (the turn-budget ruling, 2026-11-06), never travel."""
    from rules import places as places_mod

    from . import interpret

    place = " ".join(str(a.get("place") or "").split())
    if not place or row.ops or row.intents or a.get("here"):
        return
    if places and places_mod.find(places, place) is not None:
        return
    if interpret._outward(place) or interpret._road_to(place, scene):
        return
    if interpret.within_place(a, places, str(getattr(scene, "at", "") or "")):
        row.note = row.note or "a move inside the place: no travel"
        return
    words = place.lower().replace("’", "'").split()
    head = (words or [""])[-1].strip(".,;!?")
    # The player's own ("my room", "our camp") is where they keep things, not a place the
    # town is asked to have: the rest at the inn and the camp answer those.
    if words[0] in ("my", "our"):
        return
    # Somebody's home by its owner ("her house", "the baker's rooms") is the knock's to
    # answer (`call_on`, whose own finder reads the pronoun), never "anywhere" unknown.
    if head in DWELLINGS and (words[0] in _POSSESSIVE
                              or any(w.endswith(("'s", "s'")) for w in words[:-1])):
        return
    row.nowhere = "You don't know of anywhere called \"" + place + "\" here."


def _mine(words) -> bool:
    """Whether an object slot is the player's own by its determiner: "my pelts"."""
    return str(words or "").lower().split()[:1] in (["my"], ["our"])


def things_not_here(raw, rows: list[Row], *, notes: list | None = None) -> list:
    """The plan, with the engine's answer to a deed whose thing is not here or not carried
    (`Row.unheld`), stamped on `narrate_only`'s `not_here` — which the engine prints as a
    refusal (`Engine._op_narrate_only`) — whatever else the plan does.

    Measured live 2026-11-15 (the table-checks lane, Fizspark's inn, gemma-4-12B): "I
    light the lamp, read the note and burn it" and "I offer the smith my pelts" were
    planned as bare `narrate_only`, and the page lit a lamp nothing recorded and pulled
    pelts out of a pack that held none. Unlike `nowhere_to_go`, a plan that also does
    something else still owes the sentence: the walk out after the offer is no answer to
    the pelts."""
    said = [r.unheld for r in rows if getattr(r, "unheld", "")]
    if not said or not isinstance(raw, list):
        return raw
    line = " ".join(s[0].upper() + s[1:].rstrip(".") + "." for s in dict.fromkeys(said))
    out = [dict(r) if isinstance(r, dict) else r for r in raw]
    if notes is not None:
        notes.append(f"things the deeds handle that are not here: {line}")
    for r in out:
        if _op(r) == "narrate_only" and not (r.get("params") or {}).get("looks_in"):
            had = " ".join(str((r.get("params") or {}).get("not_here") or "").split())
            if line in had:
                return out
            r["params"] = dict(r.get("params") or {},
                               not_here=(had + " " + line).strip())
            return out
    return out + [{"op": "narrate_only", "because": "the deed's thing is not here",
                   "params": {"not_here": line}}]


def nowhere_to_go(raw, rows: list[Row], *, notes: list | None = None) -> list:
    """The plan, with the engine's answer to a walk that went nowhere.

    A go row the table found no place for (`_nowhere`), on a plan of nothing but
    `narrate_only` — no travel, found, move, word or roll of anybody's — gets its
    sentence on `narrate_only`'s `not_here`, which the engine prints as a refusal
    (`Engine._op_narrate_only`): 'You don't know of anywhere called "the quarters" here.'
    Refuse gracefully: never a raise, and never a narrated nothing. A plan that founds the
    place, or walks anywhere, is left alone: places are creatable in play (ruling
    2026-10-03), and the plan's `found` is one of their doors."""
    said = [r.nowhere for r in rows if getattr(r, "nowhere", "")]
    if not said or not isinstance(raw, list):
        return raw
    # Only a turn that is otherwise nothing: a plan that walks, founds, speaks, rests or
    # rolls anything has done something, and "go back up to my room and sleep" at the inn
    # is the sleep (the leave-by-deed turns, docs/conversation.md).
    if any(_op(r) != "narrate_only" for r in raw):
        return raw
    if any(isinstance(r, dict) and (r.get("params") or {}).get("not_here") for r in raw):
        return raw
    out = [dict(r) if isinstance(r, dict) else r for r in raw]
    if notes is not None:
        notes.append(f"a walk to nowhere the engine holds: {said[0]}")
    for r in out:
        if _op(r) == "narrate_only" and not (r.get("params") or {}).get("looks_in"):
            r["params"] = dict(r.get("params") or {}, not_here=said[0])
            return out
    return out + [{"op": "narrate_only", "because": "the player walked to nowhere known",
                   "params": {"not_here": said[0]}}]


def search_unanswered(raw, frame: dict | None, scene, *, notes: list | None = None) -> list:
    """The plan, with the Perception search of where the player stands when the reading
    holds a search and the turn is otherwise nothing (only `narrate_only`, no printed
    answer): searching is Perception, "intentionally searching for stimulus is a move
    action" (CRB, Perception), and a search no travel, found or venture door took is still
    a search of here. The same "otherwise nothing" rule as `nowhere_to_go`.

    Playtest 2026-11-20 #50: "Look for a different way into the gallery", in the ruins,
    was read `search` with `where` left at elsewhere, so the table built nothing; the plan's
    own check was aimed at a placeholder and dropped on the retry; the turn resolved only
    `narrate_only`, and the page said "You scan the surrounding ruins, searching for a
    different way into the gallery. What do you do?" — the act and no answer."""
    if not isinstance(raw, list) or not isinstance(frame, dict):
        return raw
    acts = [a for a in frame.get("actions") or [] if isinstance(a, dict)]
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None or not any(a.get("act") == "search" for a in acts):
        return raw
    if any(_op(r) != "narrate_only" for r in raw) or any(
            isinstance(r, dict) and (r.get("params") or {}).get(k)
            for r in raw for k in ("not_here", "looks_in")):
        return raw
    row = Row(index=0, act="search")
    _search(row, next(a for a in acts if a.get("act") == "search"), pc)
    if notes is not None:
        notes.append("a search nothing answered: the Perception search of here")
    return [r for r in raw if _op(r) != "narrate_only"] + row.intents


def _effort_check(r, pc) -> bool:
    """Whether a plan op is the player's own check of the body's strength — a plain
    ability check, a Strength-keyed skill (`tables.SKILLS`), or the 5e "athletics" a model
    reaches for — which a built feat of strength replaces rather than rolls beside."""
    from rules.intents import normalise_skill
    from rules.tables import SKILLS, ability_check_of

    if _op(r) != "check":
        return False
    if str(r.get("actor") or "pc") not in ("pc", pc.ref, "", "None"):
        return False
    said = " ".join(str((r.get("params") or {}).get("skill") or "").lower().split())
    if ability_check_of(said) or said == "athletics":
        return True
    skill = normalise_skill(said) if said else None
    return bool(skill) and SKILLS[skill][0] == "str"


def _band_of(r) -> str:
    """The difficulty band a plan op's `dc` names, or "": a band word as written, a stated
    number as the band it lands in (`dc._nearest_band`) — the engine resolves the number."""
    from rules import dc as dc_mod
    from rules.intents import IntentError, normalise_dc

    spec = (r.get("params") or {}).get("dc")
    if spec is None or spec == "":
        return ""
    try:
        d = normalise_dc(spec, "check", 0)
    except (IntentError, TypeError, ValueError):
        return ""
    return str(d.get("band") or dc_mod._nearest_band(int(d["value"])))


def sold_not_asked(frame: dict | None, scene) -> dict[int, str]:
    """A request made of somebody who sells, for something they sell, is a purchase: the
    reading's action is turned into the `buy` (or, for a bed at an inn, the `rest`) it is,
    IN PLACE, so every later reader of this turn's reading — the counter's screen
    (`judgement.purchase_sought` reads `interpret.reading_of`, the same dict), the brief,
    this table — sees the purchase and nothing rolls Diplomacy for the goods.

    The coordinator's review, 2026-10-16: "ask for a room", "ask for a mug of ale", "ask
    the smith for a sword" came back `request` from the reader, which would have rolled a
    favour and let a good roll take the goods for nothing. Decided in code from what the
    engine holds (`rules/requests.sells` / `offered`: who keeps a counter or lets beds,
    and what is priced), never from the words: "ask him for fair pay" and "ask the priest
    to bless my blade" name nothing priced, or nobody who sells, and stay requests.
    Returns {action index: note} for the turn log."""
    from rules import requests as requests_mod

    out: dict[int, str] = {}
    if not frame or scene is None:
        return out
    for i, a in enumerate(frame.get("actions") or []):
        if not isinstance(a, dict) or a.get("act") != "request":
            continue
        words = " ".join(str(a.get("target") or "").split())
        who = person(scene, words) if words else addressed(scene)
        actor = (getattr(scene, "actors", {}) or {}).get(who) if who else None
        if actor is None or actor.is_pc:
            continue
        got = requests_mod.offered(scene, actor, str(a.get("object") or ""))
        if got is None:
            continue
        a.pop("asks_for", None)
        a["was"] = "request"
        if got[0] == "lodging":
            # Taking a room is the reading's `rest` (its gloss: "take a room"; the labelled
            # set's "I pay for a room at the inn"). What the bed costs is the rest door's:
            # `Engine._room_bill` charges the house's price and holds the room.
            a["act"] = "rest"
            a.pop("object", None)
            a.pop("target", None)
            out[i] = f"asked {actor.name} for a bed: taking a room, not a favour"
        else:
            a["act"] = "buy"
            out[i] = (f"asked {actor.name} for {a.get('object')}: a purchase of "
                      f"{getattr(got[1], 'name', '')}, not a favour")
    return out


def _request(row: Row, a: dict, scene, pc) -> None:
    """Asking somebody for something, built whole: the player's Diplomacy check against
    the person asked, carrying what is asked for (`interpret.REQUESTS`), which the engine
    resolves as Make Request (CRB p.93, `Engine._make_request`) — its DC off their
    attitude, and what a granted request for payment pays its own (`rules/requests.py`).

    Measured 2026-10-16 (a real player's game): "…then I ask for fair compensation for
    helping the carter" was a `talk`, so a `say`, and nothing was rolled. Who is asked is
    the engine's finder (`person`) on the words, else the one the player is dealing with
    (`addressed`) — "ask for fair compensation" names nobody. Nobody here to ask is said,
    never invented."""
    kind = str(a.get("asks_for") or "")
    words = " ".join(str(a.get("target") or "").split())
    # "you" (or "him") is the one spoken to: live 2026-11-18, "Then I'll hire you for a
    # week" came back `target: you` and was refused "there is nobody here who is you".
    if words.lower() in _PRONOUNS | {"you"}:
        words = ""
    # Somebody named who is not here is not quietly swapped for whoever is.
    who = person(scene, words) if words else addressed(scene)
    actor = (getattr(scene, "actors", {}) or {}).get(who) if who else None
    if actor is None or actor.is_pc:
        row.missing = (f"there is nobody here who is {words}" if words
                       else "there is nobody here to ask")
        return
    # The popup shows `because`: "asks tanner's apprentice" read wrong live; a descriptor
    # name takes its article.
    name = str(actor.name)
    if name[:1].islower() and not name.lower().startswith(("the ", "a ", "an ")):
        name = f"the {name}"
    # A hire rides the same check to the engine, which takes it to the wage door and
    # rolls nothing (`Engine._make_request`, `requests.HIRE`).
    # What a favour asks for, in the player's own words: playtest 2026-11-20 #14, "I'd like
    # an item from his pack in exchange" was told "agrees to do Shadow the favour. Nothing
    # changes hands." — what favour? — and the carter's answer about his pack was then cut
    # as a clash with it.
    wants = " ".join(str(a.get("object") or "").split()) if kind == "favour" else ""
    row.intents.append({"op": "check", "actor": pc.ref, "target": who,
                        "params": {"skill": "diplomacy", "request": kind,
                                   **({"wants": wants} if wants else {})},
                        "because": (f"the player hires {name}" if kind == "hire" else
                                    f"the player asks {name} for "
                                    + ("payment" if kind == "payment" else "a favour"))})
    row.note = f"a request of {name}: {kind}"


def _threaten(row: Row, a: dict, scene, pc, frame=None, i: int = 0, rows=()) -> None:
    """A threat, built whole: the player's Intimidate check at the person threatened,
    carrying what is demanded (`interpret.DEMANDS`). The engine makes it Influence Attitude
    out of a fight and Demoralize in one (CRB p.99, `Engine._cowed`, `Engine._demoralize`),
    the DC its own (10 + Hit Dice + Wisdom), and what the demand does is the engine's.

    Playtest 2026-11-15: "yield the Red Gull to me or die" (#97) and "tell the crew the Red
    Gull is mine now" (#94) were each a `say` and nothing more. Who is threatened is the
    engine's finder on the words; a crowd ("the crew") or no words at all is the one the
    player is dealing with, else — in a fight — the nearest foe, else — aboard a ship —
    her master (`Engine._crew_master`). Nobody here to threaten is said, never invented."""
    from . import interpret, judgement

    words = " ".join(str(a.get("target") or "").split())
    actors = getattr(scene, "actors", {}) or {}
    who = person(scene, words) if words else ""
    # Whose intents the sentence has already aimed, latest first: "him" is the one the
    # same line just levelled a dagger at or grabbed, before anybody else in the room.
    # Playtest 2026-11-16 #3: "I level my dagger at the bleeding captain and tell him to
    # yield…" read as two threats, and "him" went to the deckhand (`addressed`).
    aimed = [t["target"] for r in reversed(list(rows)) for t in r.intents
             if isinstance(t.get("target"), str) and t["target"] in actors
             and t["target"] != pc.ref]
    if words.lower() in _PRONOUNS and aimed:
        # Before the finder's own guess: `person` answers a pronoun with whoever it
        # fits in the room (the live replay of #3 gave the deckhand).
        who = aimed[0]
    if who:
        earlier = next((t for r in rows for t in r.intents
                        if t.get("op") == "check" and t.get("target") == who
                        and (t.get("params") or {}).get("skill") == "intimidate"), None)
        if earlier is not None:
            # One threat, one check (CRB p.99: Intimidate is one check at the one
            # threatened): the gesture and the words of it are not two. The demand is
            # the first one the sentence made plainly; "obey" only stands in for none.
            # #4: the second reading's hand_over answered "has no coin on them to hand
            # over" to a demand to yield the ship.
            if earlier["params"].get("demand") == "obey" and a.get("demand"):
                earlier["params"]["demand"] = str(a["demand"])
            row.note = f"the same threat at {actors[who].name}"
            return
    if not who:
        who = addressed(scene) if not words or words.lower() in _PRONOUNS else ""
    if not who and getattr(scene, "in_encounter", False):
        who = nearest(scene, [x.ref for x in _standing_here(scene)
                              if judgement._can_be_fought(x)])
    if not who and words:
        crew = _crew_here(scene)
        who = crew.ref if crew is not None else ""
    actor = actors.get(who) if who else None
    if actor is None and (not words or words.lower() in _PRONOUNS) and any(
            interpret.acting(b) and b.get("act") in _FINDS_SOMEBODY_FIRST
            for b in ((frame or {}).get("actions") or [])[:i]):
        # "pick out a merchant ..., and demand his purse": the threat is at the one the
        # plan finds, as a blow there is (`DEFERRED`, `judgement.inject_fight`). Live replay
        # of playtest #18/#21, 2026-11-15: "there is nobody here who is him" was printed.
        row.note = DEFERRED
        return
    if actor is None or actor.is_pc:
        row.missing = (f"there is nobody here who is {words}" if words
                       else "there is nobody here to threaten")
        return
    demand = str(a.get("demand") or "obey")
    row.intents.append({"op": "check", "actor": pc.ref, "target": who,
                        "params": {"skill": "intimidate", "demand": demand},
                        "because": f"the player threatens {actor.name}"})
    row.note = f"a threat at {actor.name}: {demand}"


def _crew_here(scene):
    """The master of the ship the player stands on, when there is one: who answers when
    the words address her people ("I tell the crew the ship is mine")."""
    from rules import ships

    return ships.master_of(ships.crew_of(scene, ships.aboard(scene)))


def _carry(row: Row, frame, i, scene, pc, recent=()) -> None:
    """What a walk carries along is picked up first when the player is not holding it:
    "I take the crate to the man in the counting house" carries the docks man's crate
    there. Measured on round 2's replay of the owner's items save: read as a walk with no
    crate, the crate never came, and the agreed sale four turns later had nothing to sell
    (the retired `inject_goods` had read "I take the crate" and picked it up). A thing
    already in the pack is only carried; a person is never goods."""
    from rules import holding

    from rules import jobs as jobs_mod

    thing = _object(frame, i, pc, recent)
    if not thing or _a_person(scene, thing) or not _a_thing(thing):
        return
    if jobs_mod.group_named(scene, thing) is not None:
        # A job's caravan is people and their wagons, never a thing to pick up. Measured on
        # the 0.2.22 leftovers run: "I … lead the wagons on toward Kalixiri" was read `go`
        # with `object: the wagons`, and the table built "Kesst Vayr takes the wagons".
        row.note = f"{thing}: the caravan, led, not carried"
        return
    if holding.key_in(pc.goods, thing):
        row.note = f"{thing} carried along"
        return
    row.thing = thing
    row.intents.append({"op": "give", "actor": pc.ref,
                        "params": {"item": _plain(thing) or thing, "to": pc.ref},
                        "because": "the player took it along"})


def confirm_sales(rows: list[Row], frame: dict | None, scene, *, sentence: str = "",
                  ask=None) -> list[str]:
    """A sale about to be built is asked again, alone (`interpret.confirm_sale`): closed
    now, or only offered, meant for later, asked about? Anything but "closed" holds it back
    — an offer, a plan, a question — at a counter as anywhere else. A failed check holds
    it back too, because a sale cannot be taken back and an offer can be repeated.
    Returns a line per sale held back, for the turn log. `ask` None (no model: the test
    suite, or the reader off) trusts the reading.

    Measured: round 2's replay with the frozen reader read "I take the crate to the man
    in the counting house who will buy it from me" and "I smile and flirt with the clerk
    and offer the crate for coin" as sales DONE — the round-1 regression back."""
    notes: list[str] = []
    if ask is None or not frame:
        return notes
    actions = frame.get("actions") or []
    for row in rows:
        sale = next((i for i in row.intents if i["op"] == "sell"), None)
        if row.act != "sell" or sale is None or row.commit != "done":
            continue
        a = actions[row.index] if row.index < len(actions) else {}
        said = ask(sentence, str(a.get("span") or sentence))
        # Only a sale closed stands, at a counter too: the counting house's clerk keeps
        # one, and in the replay "…who will buy it from me" sold the crate to him a turn
        # early while a check that skipped keepers never asked.
        if said == "done":
            continue
        row.commit = said or "tried"
        row.intents = []
        if isinstance(a, dict):
            # The reading carries the answer, so the plan's own sale has nothing to stand
            # behind either (`apply`), and the brief says how far it was done.
            a["commit"] = row.commit
        row.note = (f"the sale asked again: {said or 'no answer'}, so an offer, not a sale"
                    if row.commit == "tried" else
                    f"the sale asked again: {row.commit}, not done this turn: no op")
        notes.append(f"{row.thing or sale['params'].get('item')}: {row.note}")
    return notes


def confirm_takes(rows: list[Row], frame: dict | None, scene, *, recent=(),
                  ask=None) -> list[str]:
    """A take from a person, asked whether that person gave or offered it
    (`interpret.confirm_take`, shown the last beat). "offered" makes the holder the one
    acting — they hand it over, and `Engine._op_give` reads a hand-over; anything else
    leaves the player acting, which the engine reads as a take: owner kept, `stolen` set.
    A `steal` is never asked (the words said it), nor a take out of a container. `ask`
    None (no model: the test suite, or the reader off) leaves every take a take — the
    engine's own rule (docs/items-have-owners.md). Returns a line per take turned into a
    hand-over, for the turn log.

    Measured 2026-10-08 (the deeds lane): "I take an apple from the fruit seller without
    paying" came out as the seller handing the apple over. The engine now reads the
    player taking from a person as a take; this asks only so that "I take the purse he
    holds out" stays the reward it was."""
    notes: list[str] = []
    if ask is None or not frame or scene is None:
        return notes
    actions = frame.get("actions") or []
    people = getattr(scene, "actors", {}) or {}
    beat = " ".join(str(b or "") for b in list(recent or ())[-2:])[-700:]
    for row in rows:
        if row.act != "take" or row.commit != "done":
            continue
        for built in row.intents:
            p = built.get("params") or {}
            holder = people.get(str(p.get("from_") or ""))
            if built.get("op") != "give" or holder is None or getattr(holder, "is_pc", False):
                continue
            a = actions[row.index] if row.index < len(actions) else {}
            said = ask(beat, str(a.get("span") or row.thing or p.get("item") or ""))
            if said != "offered":
                continue
            built["actor"] = holder.ref
            built["because"] = f"{holder.name} handed it over"
            row.note = "asked again: offered, so handed over"
            notes.append(f"{p.get('item')}: offered by {holder.name}, handed over")
    return notes


_TENDING_ACTS = frozenset({"use", "other"})


def first_aid(rows: list[Row], frame: dict | None, scene, *, ask=None) -> list[str]:
    """First aid built whole: a deed aimed at somebody here who is DYING becomes the Heal
    check the Core Rulebook stabilises them with (`rules/firstaid.py`, DC 15) — with its
    `target`, the patient, which is the one slot the plan kept leaving off.

    Measured 2026-10-08 (the deeds lane, local model): "I give first aid to the wounded
    porter" was planned `check skill=heal` with no target 3 times of 3, so the engine found
    no patient and the porter bled on; on this branch's own repro the planner wrote
    `use_item medical_kit_01` (carried by nobody), `check sense motive`, and
    `use_item bandage_1` for three phrasings — never once the Heal check aimed at him.

    Detected in code, from the engine's state: an action done now of a kind that can be
    tending (`use`, `other` — the acts the reader gives "bandage" and "give first aid"),
    whose target is somebody here `firstaid.dying` says is dying. A Heal named as a skill
    ("I use the Heal skill on the porter": the `object`/`power` slot is the skill's own
    name, a closed list) is first aid outright. Anything else is asked ONE question
    (`interpret.confirm_first_aid`): keeping them alive, or something else? — CLAUDE.md's
    detect-then-ask. `ask` None (the test suite, the reader off) builds only the
    skill-named route. Returns a line per check built, for the turn log."""
    from rules import firstaid, holding

    from . import interpret

    notes: list[str] = []
    if not frame or scene is None or not hasattr(scene, "pc") or scene.pc() is None:
        return notes
    pc = scene.pc()
    actions = frame.get("actions") or []
    people = getattr(scene, "actors", {}) or {}
    tended: set[str] = set()
    for row in rows:
        a = actions[row.index] if row.index < len(actions) else {}
        # Done or tried ("I try to stabilise him" is `tried`, and 1e rolls it).
        if row.act not in _TENDING_ACTS or row.intents or not interpret.acting(a):
            continue
        ref = person(scene, " ".join(str(a.get("target") or "").split()))
        if not ref:
            # Aimed at a wound, not a person ("bandage his wound", read live with
            # `target: his wound`), or at nobody: the one creature here who is dying, when
            # there is exactly one — the engine's state, as `firstaid.patient_of` reads it.
            # The question below still decides whether the deed is first aid at all.
            dying_here = [x for x in people.values()
                          if x is not pc and firstaid.needs_aid(x)]
            ref = dying_here[0].ref if len(dying_here) == 1 else ""
        patient = people.get(ref) if ref else None
        if (patient is None or patient is pc or not firstaid.needs_aid(patient)
                or patient.ref in tended):
            # One first aid per patient a turn: "I kneel by the porter and try to
            # stabilise him" is two actions of the reading and one Heal check.
            continue
        named = any(" ".join(w for w in holding.plain(a.get(slot)).split()
                             if w not in ("skill", "skills")) == firstaid.SKILL
                    for slot in ("object", "power") if a.get(slot))
        if not named:
            if ask is None or ask(str(a.get("span") or ""), patient.name) != "first aid":
                continue
        tended.add(patient.ref)
        # The band is there because a check must name something to beat (the parse
        # refuses one without); with the patient dying when it resolves it is never read
        # — first aid is the rule's DC 15, whatever the band (`Engine._op_check`).
        row.intents.append({"op": "check", "actor": pc.ref, "target": patient.ref,
                            "params": {"skill": firstaid.SKILL, "dc": {"band": "average"}},
                            "because": "the player gave first aid"})
        row.note = f"first aid to {patient.name}"
        notes.append(row.note)
    return notes


# --- skill uses with their own row (lane E, rules/skilluses.py) -----------------------------

def _tumbles(rows: list[Row], frame, scene, pc) -> None:
    """A move the reading says tumbles past somebody's reach (`interpret` `go.tumble`), in
    a fight: the Acrobatics check goes in front of each move the row built, aimed at the
    same square, so the engine rolls it against every foe the move would provoke
    (`skilluses.tumble`). A tumble with no square built is said, not invented."""
    if pc is None or not getattr(scene, "in_encounter", False):
        return
    actions = (frame or {}).get("actions") or []
    carried = False
    for row in rows:
        a = actions[row.index] if row.index < len(actions) else {}
        if row.act != "go" or not (a.get("tumble") or carried):
            carried = False
            continue
        moves = [b for b in row.intents if b.get("op") == "move"
                 and (b.get("params") or {}).get("square")]
        if not moves:
            # Read live 2026-11-22 (gemma-4-12B): "I roll under the ogre's swing and come
            # up at E6" came back as two walks, the tumble at "under the ogre's swing" and
            # the square on the next. The tumble rides on to the next walk of the line.
            carried = True
            row.note = row.note or "a tumble with no square named: carried to the next walk"
            continue
        carried = False
        for b in moves:
            row.intents.insert(row.intents.index(b), {
                "op": "check", "actor": pc.ref,
                "params": {"skill": "acrobatics", "tumble": True,
                           "square": list(b["params"]["square"])[:2]},
                "because": "the player tumbles past their foes' reach"})
        row.note = "a tumble, then the move"


def _recall(row: Row, a: dict, scene, pc) -> None:
    """Recalling what a creature here is (`interpret` `look.recall`): the Knowledge check
    its type calls for, at DC 10 + its CR (`skilluses.monster_lore`). Who is meant is the
    engine's finder on the words, else the one the player is dealing with."""
    from rules import skilluses

    words = " ".join(str(a.get("target") or a.get("object") or "").split())
    ref = person(scene, words) if words else addressed(scene)
    if not ref and not words:
        # Read live 2026-11-22: "I try to recall what I know about the troll" came back
        # `look, recall` with no target 3 times of 3. The engine's answer: the one
        # stranger standing here, else in a fight the nearest of them.
        here = [x.ref for x in _standing_here(scene) if not _ours(x)]
        ref = here[0] if len(here) == 1 else (
            nearest(scene, here) if here and getattr(scene, "in_encounter", False) else "")
    who = (getattr(scene, "actors", {}) or {}).get(ref) if ref else None
    if who is None or who is pc:
        # Not a creature here: a question about the world (round 2, skills-mind), asked
        # when the world's own index finds the words (`skilluses.knowledge_answer`, whose
        # Knowledge is the record's own field for what was found).
        here = str(getattr(scene, "location_id", "") or "")
        if words and skilluses.topic_in(None, words, here) is not None:
            row.intents.append({"op": "check", "actor": pc.ref,
                                "params": {"skill": "knowledge (local)", "about": words,
                                           "dc": {"band": "average"}},
                                "because": f"the player tries to recall {words}"})
            row.note = f"what the world's record holds on {words}"
            return
        row.note = "a recall of nobody here: nothing to roll"
        return
    row.intents.append({"op": "check", "actor": pc.ref, "target": who.ref,
                        "params": {"skill": skilluses.lore_skill(who),
                                   "dc": {"band": "average"}},
                        "because": f"the player tries to recall what {who.name} is"})
    row.note = f"monster lore on {who.name}"


def _dazzling_display(row: Row, a: dict, pc) -> bool:
    """A power named as Dazzling Display, a feat the player holds (`feats.resolve` on the
    reader's `power` slot: the feat list's own names, never a word list): the Intimidate
    at every foe who sees it (`skilluses.dazzling_display`). False when it is not."""
    from rules import feats as feats_mod

    feat, _target = feats_mod.resolve(str(a.get("power") or ""))
    if feat is None or feat.id != "dazzling-display":
        return False
    row.intents.append({"op": "check", "actor": pc.ref,
                        "params": {"skill": "intimidate", "display": True},
                        "because": "the player makes a dazzling display"})
    row.note = "Dazzling Display"
    return True


# --- who a declared blow lands on -------------------------------------------------------------

# The acts whose deed is a blow at somebody (`interpret.ACTS`).
VIOLENT_ACTS = frozenset({"attack"})
# The reader's closed `blow` (`interpret.BLOWS`) that is a combat manoeuvre, and which
# (CRB pp.198-201; the engine's MANEUVERS keys). Playtest 2026-11-15 #18, #52.
MANOEUVRE_OF_BLOW = {"shove": "bull rush", "grab": "grapple", "trip": "trip",
                     "disarm": "disarm"}
# Acts that, done before a blow in the same sentence, put somebody in front of the player
# whom the engine cannot see yet: a walk into another room, the person sought or followed.
# "I walk into the tavern and punch the first man I see" is about people in the tavern,
# and the people standing HERE at plan time are not them.
_FINDS_SOMEBODY_FIRST = frozenset({"go", "journey", "leave", "call_on", "break_in",
                                   "seek", "follow"})
# How far each zone is, in feet, for a scene with no map to measure on (rules/intents.py
# ZONES; the squares `Scene.place_by_zone` lays them at).
_ZONE_FEET = {"engaged": 5, "near": 15, "far": 40}

NOBODY_TO_ATTACK = "there is nobody here to attack"
# The note on a blow left for after a walk or a seek finds somebody (`victims`); the fight
# injector aims it at the one the plan found (`judgement.inject_fight`).
DEFERRED = "the blow comes after somebody is found or a place is reached"


def _standing_here(scene) -> list:
    """Everybody non-player here who could be struck as a fresh blow: not down, not dead,
    and seen (somebody hiding is not in the room the character can see — the brief's own
    rule for WHO IS HERE)."""
    return [a for a in (getattr(scene, "actors", {}) or {}).values()
            if not getattr(a, "is_pc", False) and not a.is_down
            and not a.has_state("state.hidden")]


def _ours(actor) -> bool:
    from rules import states as states_mod

    return (actor.has_state(states_mod.TRAVELS_WITH_YOU)
            or actor.has_state(states_mod.OWNED_BY_YOU))


def nearest(scene, refs) -> str:
    """The one of `refs` nearest the player, by the squares people keep (`Scene.positions`;
    the ruling of 2026-09-28: everyone in a scene has a square from arrival and keeps it),
    else by zone; the lower ref breaks a tie, so the answer never depends on dict order.
    The player's own people come last: an unnamed blow is never the obvious reading of a
    friend (the drover shot dying, 2026-10-01)."""
    pc = scene.pc() if hasattr(scene, "pc") else None
    actors = getattr(scene, "actors", {}) or {}

    def key(ref):
        a = actors.get(ref)
        feet = scene.distance_between(pc.ref, ref) if pc is not None else None
        if feet is None:
            feet = _ZONE_FEET.get(str((getattr(scene, "zones", {}) or {}).get(ref)), 999)
        num = int(re.sub(r"\D", "", ref) or 0)
        return (a is not None and _ours(a), feet, num, ref)

    pool = [r for r in refs if r in actors]
    return min(pool, key=key) if pool else ""


def label(actor) -> str:
    """How the victim question shows a person: the name the player knows them by, and the
    two facts the engine holds that decide "a civilian" and "my friend" — never a guess."""
    from rules import states as states_mod

    bits = []
    # Who they are, as the sheet holds it: the gender (a closed field, "man"/"woman") or
    # else the pronouns, and the size category when it is not a person's. Measured live
    # 2026-10-09 (the fight script): "I pick a fight with the biggest man in the room",
    # with one person in the tavern — "the one behind the bar", a man, he/him, Medium on
    # his sheet — was answered `[]` 2 of 2 times and the turn was refused "nobody here
    # answers to the biggest man in the room"; shown "(a man)" or "(he/him)" it was
    # answered `["c3"]` 2 of 2 times, and "(she/her)" still `[]`. The question could not
    # see the facts that decide "a man".
    gender = str(getattr(actor, "gender", "") or "").strip().lower()
    pronouns = str(getattr(actor, "pronouns", "") or "").strip().lower()
    if gender in ("man", "woman", "boy", "girl"):
        bits.append(f"a {gender}")
    elif pronouns and pronouns not in ("they/them", "it/its"):
        bits.append(pronouns)
    size = str(getattr(actor, "size", "") or "").strip().lower()
    if size and size not in ("medium", "small"):
        bits.append(size)
    if actor.has_state("role.guard") or str(getattr(actor, "from_template", "")) in (
            "watchman", "guard", "soldier"):
        bits.append("a guard")
    if actor.has_state(states_mod.TRAVELS_WITH_YOU):
        bits.append("travels with you")
    elif actor.has_state(states_mod.OWNED_BY_YOU):
        bits.append("yours")
    if actor.is_down:
        bits.append("down")
    return str(actor.name) + (f" ({'; '.join(bits)})" if bits else "")


def victims(rows: list[Row], frame: dict | None, scene, *, ask=None) -> list[str]:
    """A declared blow lands on a REAL person here, or the turn says there is nobody.

    The owner, 2026-10-09: "if i say I attack the closest person or i go on a rampage or i
    assault a civilian etc. it should be able to start a fight." Measured live the same day
    (gemma-4-12B, a market of three bystanders, scratch data): "I attack the closest person."
    was planned at the fruit seller beside the player, and the fight declarer then REQUIRED
    a spawn, so two bandits came out of nowhere and joined the fight on her side; "I go on a
    rampage." was read `other` and five plans aimed at `new1` until the turn degraded into
    prose about slicing men who were not there. The regex door (`inject_fight`'s cue table
    and template thug) is gone; this builds the blow from the reading:

      * the target slot resolves through the engine's finders (`person`: a name, a
        description shown as the name, a pronoun) — "I attack Bob" is Bob;
      * a pronoun keeps the 2026-09-18 rule in a fight: it means somebody IN the fight
        (`judgement._can_be_fought`), never a bystander, or the one the player is engaged
        with; out of a fight it is the one the player is dealing with (`addressed`);
      * no words in a fight: the nearest foe standing;
      * anything else — "the closest person", "a civilian", "the biggest bruiser", a
        rampage — is ONE question with the people here as an enum
        (`interpret.confirm_victims`): which of them could the words mean? The NEAREST of
        those, by the squares people keep, is the engine's answer (`nearest`);
      * nobody standing here at all, or nobody the words fit: the row is `missing`, and
        the turn is the refusal in words ("There is nobody here to attack.") — never an
        invented opponent.

    The attack built here goes to the plan through `judgement.inject_fight`, which aims the
    plan's own blow at it; the engine's battle gate opens the fight on it and brings in
    their own kind and the law (`Engine._ensure_encounter`, `rally`, `_law_joins`).
    `ask` None (the test suite, the reader off) builds only what needs no question.
    Returns a line per row decided, for the turn log."""
    from . import interpret, judgement

    notes: list[str] = []
    if not frame or scene is None or not hasattr(scene, "pc") or scene.pc() is None:
        return notes
    pc = scene.pc()
    actions = frame.get("actions") or []
    actors = getattr(scene, "actors", {}) or {}
    fighting = bool(getattr(scene, "in_encounter", False))
    for row in rows:
        a = actions[row.index] if row.index < len(actions) else {}
        if row.act not in VIOLENT_ACTS or row.intents or not interpret.acting(a):
            continue
        named_here = fighting and bool(person(scene, a.get("target"))) \
            and str(a.get("target") or "").lower() not in _PRONOUNS
        if not named_here and any(interpret.acting(b) and b.get("act") in _FINDS_SOMEBODY_FIRST
                                  for b in actions[:row.index]):
            # In a fight nobody new is found: a blow at somebody named and standing here
            # is at them, whatever walk the line began with. Playtest 2026-11-15 #93:
            # "I leave the penguin, draw my dagger, put it to the captain's throat" was
            # read `leave` first, and the blow at the captain was dropped.
            row.note = DEFERRED
            continue
        here = _standing_here(scene)
        words = " ".join(str(a.get("target") or "").split())
        # "it" too, for a blow: the live reader reads "I attack it" `target: it`.
        pronoun = words.lower() in _PRONOUNS | {"it"}
        if not fighting and not here and not any(
                not getattr(x, "is_pc", False) and not x.has_state("state.down.dead")
                for x in actors.values()) and not (words and not pronoun
                                                   and person(scene, words)):
            # Not a soul but the player (and the dead): the refusal, in words. A body the
            # words name is theirs to kick (`redirect_attacks_off_corpses` lets that blow
            # stand); in a fight the answer to nobody left is the fight's end
            # (`judgement.inject_fight`), which is what pays out.
            row.missing = NOBODY_TO_ATTACK
            notes.append(row.missing)
            continue
        ref, how = "", ""
        if pronoun:
            ref = _pronoun_victim(scene, words, fighting)
            how = f"{words!r}, by the engine's state"
        elif words:
            ref = person(scene, words)
            how = f"{words!r}, by name"
        elif fighting:
            foes = [x.ref for x in here if judgement._can_be_fought(x)]
            ref = nearest(scene, foes)
            how = "the nearest foe"
        if not ref and here and not pronoun:
            if ask is None:
                row.note = "who the blow is aimed at was not asked (no reader)"
                continue
            meant = ask(str(a.get("span") or words), words,
                        [(x.ref, label(x)) for x in here])
            if meant is None:
                row.note = "the question of who the blow is aimed at failed"
                continue
            if not meant:
                if fighting:
                    # "I keep swinging" with every foe down: the fight is over, and
                    # `inject_fight` says so.
                    row.note = "nobody left in the fight the words could mean"
                    continue
                row.missing = (f"nobody here answers to {words}" if words
                               else NOBODY_TO_ATTACK)
                notes.append(row.missing)
                continue
            # The player's own people only when nobody else is meant.
            strangers = [r for r in meant if not _ours(actors[r])]
            ref = nearest(scene, strangers or meant)
            how = (f"the nearest of {len(meant)} the words could mean" if len(meant) > 1
                   else "the one the words mean")
        victim = actors.get(ref) if ref else None
        if victim is None:
            if not row.note:
                row.note = "nobody resolved; the plan's own blow stands"
            continue
        if victim.is_down or victim.has_state("state.helpless"):
            if victim.has_state("state.down.dead"):
                row.note = f"{victim.name} is dead: the plan's own blow stands"
                continue
            # A blow the reader read at a body on the floor is a blow, whatever words the
            # player used. Before, this left "the plan's own blow", and a plan that wrote
            # none (it took the dying wolf for dead and wrote `narrate_only`) left the wolf
            # breathing at -2 while the prose killed it: measured in the leather final
            # pass's playthrough, 2026-10-09, "I finish the dying wolf with a thrust of my
            # rapier" (read `attack`, target "the dying wolf") changed nothing, and the
            # harvest stayed shut ("still breathing: finish it first"). Out of a fight it
            # is the coup de grâce (CRB p.197; no time is short out of a fight, and it
            # opens none); in one, the reader's closed `blow` says which (the owner's
            # ruling 2026-11-04, by the book): finishing words make the coup de grâce — a
            # full-round action that provokes (`Engine._coup_provokes`) — and any other
            # blow is an ordinary one at helpless AC, the engine's own rule. Before the
            # ruling every blow here in a fight was the ordinary one, so "I slit his
            # throat" could miss on a natural 1. Whether the body IS helpless is the
            # engine's state, asked above; a finishing word at a foe still standing is an
            # ordinary blow, below. `judgement.inject_fight` adds it only when the plan
            # aimed nothing at them.
            coup = (not fighting) or a.get("blow") == "finishing"
            params = {"coup_de_grace": True} if coup else {}
            row.intents.append({"op": "attack", "actor": pc.ref, "target": victim.ref,
                                "because": f"the player strikes {victim.name}, who is down",
                                "params": params})
            row.note = f"{victim.name} is down: " + (
                "a coup de grâce" if coup else "a blow at helpless AC")
            notes.append(row.note)
            continue
        if a.get("blow") == "feint":
            # A feint is no blow (lane E, rules/skilluses.py `feint`): the Bluff at the
            # foe's own DC, which leaves them without their Dexterity against the next.
            row.intents.append({"op": "check", "actor": pc.ref, "target": victim.ref,
                                "params": {"skill": "bluff", "feint": True},
                                "because": f"the player feints at {victim.name}"})
            row.note = f"a feint at {victim.name} ({victim.ref}): {how}"
            notes.append(row.note)
            continue
        man = MANOEUVRE_OF_BLOW.get(str(a.get("blow") or ""))
        row.intents.append({"op": "attack", "actor": pc.ref, "target": victim.ref,
                            "because": f"the player attacks {victim.name}",
                            **({"params": {"manoeuvre": man}} if man else {})})
        row.note = f"the blow lands on {victim.name} ({victim.ref}): {how}" + (
            f", a {man}" if man else "")
        notes.append(row.note)
    return notes


def _pronoun_victim(scene, words: str, fighting: bool) -> str:
    """Who "him", "her", "them" means for a blow. In a fight, only somebody in it: measured
    2026-09-18 with the map open, the planner's attack on "the man" landed on a 4-hp
    bystander who had never been in the fight (`judgement._can_be_fought`). Out of one, the
    pronoun against the people here, else whoever the player is dealing with."""
    from . import judgement

    here = _standing_here(scene)
    pool = [x for x in here if judgement._can_be_fought(x)] if fighting else \
        [x for x in here if not _ours(x)]
    fits = [x.ref for x in pool if _pronoun_fits(x, words)]
    if len(fits) == 1:
        return fits[0]
    who = addressed(scene)
    if who in {x.ref for x in pool}:
        return who
    # Nobody standing: the pronoun reaches down to a body on the floor that still
    # breathes, and `victims` makes the blow at it the coup de grâce (or, in a fight, a
    # blow at helpless AC). Measured on the owner's report of 2026-11-01 (Corvin T., the
    # shrine): "kill it and skin it for parts" with the giant rot grub dying at -1 and
    # nobody else here — "it" pooled only the standing, resolved to nobody, and the coup
    # de grâce branch never ran; the grub was left breathing while the prose killed it.
    # Which body is the engine's: the one the pronoun fits, and never the dead.
    down = [x for x in (getattr(scene, "actors", {}) or {}).values()
            if not getattr(x, "is_pc", False) and x.is_down
            and not x.has_state("state.down.dead") and not x.has_state("state.hidden")
            and not _ours(x)]
    fits = [x.ref for x in down if _pronoun_fits(x, words)]
    return fits[0] if len(fits) == 1 else ""


def _pronoun_fits(actor, words: str) -> bool:
    """Whether a pronoun can mean this actor: the sheet's own pronouns (a closed field),
    or — for "it" — a creature that is no person (`bestiary.body_size` answers a size only
    then). Every bestiary creature is made "they/them", so "it" matched no pronoun at all."""
    from rules import bestiary

    said = words.lower()
    if said in _pronoun_forms(getattr(actor, "pronouns", "")):
        return True
    return said in ("it", "its") and bool(bestiary.body_size(actor))


# --- what a declared blow is struck with -----------------------------------------------------

# Acts that put a thing in the player's hands before a later deed of the same sentence: "I
# snatch the knife off the table and stab him" stabs with a knife the pack does not hold yet.
_PUTS_IN_HAND = frozenset({"take", "steal", "buy", "gather"})


def _weapon_words(frame: dict, i: int) -> str:
    """The words for what the blow at action `i` is struck with: the attack's own object,
    else the object of the `use` done just before it in the same sentence — the frame's
    structure, as "it" is the object of the deed before it (`_object`).

    Both shapes are what the live reader returns (gemma, 2026-10-16, two runs each): "I
    draw my dagger and stab the shopkeeper", "I stab him with my dagger" and "I attack him
    with my dagger" come back as ONE action, `attack, object: my dagger` (the reader is
    shown "I level my spear and drive it into the boar" as one deed); "I pull out my
    dagger and slash at the smith" and "I swap to my dagger and attack" come back `use,
    object: my dagger` then `attack` with no object."""
    from . import interpret

    acts = frame.get("actions") or []
    said = " ".join(str(acts[i].get("object") or "").split())
    if said:
        return said
    for prev in reversed(acts[:i]):
        if not interpret.acting(prev):
            continue
        if prev.get("act") in VIOLENT_ACTS:
            break                         # the blow before this one took its own weapon
        if prev.get("act") == "use" and prev.get("object"):
            return " ".join(str(prev["object"]).split())
    return ""


def _weapon_of(pc, words: str) -> tuple[str, bool]:
    """(the weapon the words name, whether the player carries it): the carried entry as
    the sheet spells it, a carried crafted weapon's record id, or the weapon table's key
    for one not carried. ("", False) when the words name no weapon the rules know — "the
    hilt of my rapier", "a chair", "my blade" — which is the plan's and the improvised
    door's to read, never guessed at here. Every name goes through the engine's own
    finders (`holding.plain`, `weapons.key_for`, `Actor.crafted_records_called`), the
    ones the `wear` door draws by."""
    from rules import holding
    from rules import weapons as weapons_mod
    from rules.sheet import _is_weapon_record

    plain = holding.plain(words)
    key = weapons_mod.key_for(plain) if plain else ""
    if key:
        carried = next((w for w in getattr(pc, "weapons", ()) or () if w and
                        (weapons_mod.key_for(w) or str(w).lower()) == key), None)
        if carried is not None:
            return str(carried), True
    made = [r for r in pc.crafted_records_called(words) if _is_weapon_record(r)]
    if len(made) == 1:
        return str(made[0].get("id") or made[0].get("name")).lower(), True
    return (key, False) if key else ("", False)


def _holds_one(actor, key: str) -> bool:
    from rules import weapons as weapons_mod

    if actor is None:
        return False
    theirs = [actor.equipped, *(getattr(actor, "weapons", ()) or ())]
    return any(w and (weapons_mod.key_for(str(w)) or str(w).lower()) == key for w in theirs)


def weapons(rows: list[Row], frame: dict | None, scene) -> list[str]:
    """The weapon each declared blow is struck with, from the reading: `Row.weapon`, and
    on the blow `victims` built. A weapon the words name that the player does not carry
    makes the row `missing` — "Kesst Vayr is not carrying a greataxe" — and the turn says
    so, as a sale of a crate nobody carries does (`refusal`).

    Measured live on master, 2026-10-16: "I draw my dagger and stab the shopkeeper" was read
    `attack, object: my dagger`, and nothing below the reader looked at the object — the
    plan wrote no `weapon`, the engine swung what was in hand, and the tell was "Kesst
    Vayr's attack with the rapier misses…", the prose "the blade of your rapier".

    Left alone: a blow whose words name no weapon the rules know (the plan's, or the
    improvised door's); a weapon the player has none of and somebody the blow is aimed at
    holds ("I strike his club" is at HIS club — `aim_at_the_holder`'s sunder — never a
    refusal that she carries no club); and one an
    earlier deed of the sentence puts in the player's hands ("I snatch the knife off the
    table and stab him"), which the pack does not hold until that deed resolves.
    Returns a line per row decided, for the turn log."""
    from . import interpret

    notes: list[str] = []
    if not frame or scene is None or not hasattr(scene, "pc") or scene.pc() is None:
        return notes
    from rules import holding

    pc = scene.pc()
    actors = getattr(scene, "actors", {}) or {}
    acts = frame.get("actions") or []
    for row in rows:
        a = acts[row.index] if row.index < len(acts) else {}
        if row.act not in VIOLENT_ACTS or not interpret.acting(a):
            continue
        words = _weapon_words(frame, row.index)
        if not words:
            continue
        key, carried = _weapon_of(pc, words)
        if not key:
            continue
        if not carried:
            # Only when she has none of her own: the thug carries a dagger too, and "I stab
            # him with my dagger" is still hers.
            aimed = [actors.get(i.get("target")) for i in row.intents] or [
                actors.get(person(scene, a.get("target")))]
            if any(_holds_one(x, key) for x in aimed if x is not None and not x.is_pc):
                row.note = f"{words!r} is a weapon the one struck holds: not the player's"
                continue
            if any(interpret.acting(p) and p.get("act") in _PUTS_IN_HAND
                   and p.get("object") and holding.same(str(p["object"]), words)
                   for p in acts[:row.index]):
                row.note = f"{words!r} comes to hand earlier in the sentence"
                continue
            from rules import weapons as weapons_mod

            row.missing = (f"{pc.name} is not carrying "
                           f"{_a_or_an(weapons_mod.get(key)['name'].lower())}")
            row.weapon = key                 # with `missing`: named, and not there
            row.intents = []
            notes.append(row.missing)
            continue
        row.weapon = key
        for i in row.intents:
            i["params"] = dict(i.get("params") or {}, weapon=key)
        notes.append(f"the blow is struck with the {key}: {words!r}")
    return notes


def _a_or_an(noun: str) -> str:
    return english.a(noun)


def strike_with(raw, rows: list[Row], scene, *, notes: list | None = None) -> list:
    """The player's blows struck with the weapon the reading named (`weapons`), whatever
    the plan wrote: the plan's own `weapon` param — or none, which the engine reads as
    whatever is in hand — is replaced. The engine then draws it if it is not in hand
    (`Engine._draw_before`) and pays for the draw in a fight.

    Not on a manoeuvre (a disarm or a steal names the OTHER's thing in `item`), an
    improvised weapon (`inject_improvised`'s thing is the weapon), or a turn whose blows
    name two different weapons (each act's blow is not told apart from the plan's here)."""
    if not isinstance(raw, list) or scene is None or not hasattr(scene, "pc") \
            or scene.pc() is None:
        return raw
    pc = scene.pc()

    def players_blow(r) -> bool:
        params = (r.get("params") or {}) if isinstance(r, dict) else {}
        return (isinstance(r, dict) and str(r.get("op", "")).lower() == "attack"
                and str(r.get("actor") or pc.ref) in ("pc", pc.ref)
                and not params.get("manoeuvre") and not params.get("reaction")
                and str(params.get("weapon") or "").lower() != "improvised")

    # A weapon named and not carried: no blow of the player's is struck with something
    # else in its place. The turn says what is missing (`unresolved`, the brief's NOT HERE
    # line; the whole turn's refusal when it is the only deed, `refusal`).
    gone = [r.missing for r in rows or () if r.weapon and r.missing]
    if gone:
        kept = [r for r in raw if not players_blow(r)]
        if len(kept) != len(raw) and notes is not None:
            notes.append(f"the player's blow dropped: {gone[0]}")
        return kept
    named = list(dict.fromkeys(r.weapon for r in rows or () if r.weapon))
    if len(named) != 1:
        return raw
    for r in raw:
        if not players_blow(r):
            continue
        params = dict(r.get("params") or {})
        if str(params.get("weapon") or "").lower() != named[0].lower():
            if notes is not None:
                notes.append(f"the player's blow struck with the {named[0]}, the weapon "
                             f"the words name (the plan had "
                             f"{params.get('weapon') or 'what is in hand'})")
            params["weapon"] = named[0]
        r["params"] = params
    return raw


def declared(rows: list[Row]) -> list[str]:
    """The op names the plan must carry, in the order the words do them — the `declared`
    block's keys (`prompts.turn_schema`). Ops built whole are not asked of the model."""
    return list(dict.fromkeys(op for r in rows for op in r.ops))


def built_ops(rows: list[Row]) -> list[str]:
    return list(dict.fromkeys(i["op"] for r in rows for i in r.intents))


def unresolved(rows: list[Row]) -> list[str]:
    return list(dict.fromkeys(r.missing for r in rows if r.missing))


def refusal(rows: list[Row]) -> str:
    """The turn's whole answer when every deed the words declared moves a thing and not
    one of them can: "Kesst Vayr is not carrying a crate." Nothing is planned, nothing is
    invented, and the player is told what was not found. "" when anything else is owed.

    A blow with nobody to land on is the same refusal (`victims`, 2026-10-09): "There is
    nobody here to attack." — the words the template thug used to answer."""
    if not rows or any(r.act not in GOODS_ACTS | VIOLENT_ACTS or r.intents or r.ops
                       for r in rows):
        return ""
    missing = unresolved(rows)
    if not missing or any(not r.missing for r in rows):
        return ""
    return " ".join(m[0].upper() + m[1:] + "." for m in missing)


# --- the reading confirms the plan, or overrules it ------------------------------------------

def _op(r) -> str:
    return str((r or {}).get("op", "")).lower() if isinstance(r, dict) else ""


def _skill(r) -> str:
    """The 1e skill a check names, as validation will read it: the plan's "search" or
    "investigation" is Perception (`intents.SKILL_ALIASES`). Live 2026-11-16: the plan's
    own search check beside the table's survived the built-check rule under its alias and
    rolled a second Perception at its "average" DC."""
    from rules import intents as intents_mod

    said = str(((r or {}).get("params") or {}).get("skill") or "")
    return intents_mod.normalise_skill(said) or said.strip().lower()


def _coin_amount(params: dict) -> bool:
    """Whether a coin op's params say how much: a count, or a number in the item's words
    ("gold-piece-10", "10 gp", "ten gold")."""
    if int((params or {}).get("count") or 0) > 0:
        return True
    words = str((params or {}).get("item") or "").lower().replace("-", " ")
    return bool(re.search(r"[0-9]", words)) or any(
        w in _NUMBERS and w not in ("a", "an") for w in words.split())


def _same_thing(a, b, pc=None) -> bool:
    """Two mentions of one thing: both coin, or the same name — a jar by its shelf id
    ("yarow-elixir#1") or the way a person says it ("Yarow Elixir"). Measured on the
    trade tests: the plan's give of "Yarow Elixir" stood beside the table's sale of
    yarow-elixir#1, and the elixir left twice."""
    from rules import holding

    if _is_coin(a) and _is_coin(b):
        return True
    if pc is not None:
        a, b = (_stock_id(pc, a) or a), (_stock_id(pc, b) or b)
    return holding.same(a, b)


def _to_player(p: dict, pc, target=None) -> bool:
    """Whether a give lands in the player's hands. The intent's own `target` is where it
    goes when the params name nobody, as `Engine._op_give` reads it: the recorded
    `give actor=pc target=c13` of the brunt was a give TO the smith."""
    to = str(p.get("to") or target or "").strip().lower()
    frm = str(p.get("from_") or p.get("from") or "").strip().lower()
    return to in (pc.ref, "pc", "you", "player") or not (to or frm)


# The acts that ask for the ground to be searched, or for a look around: beside any of
# them a Perception check or a forage is the player's own.
_LOOKING_ACTS = frozenset({"gather", "search", "look", "track"})


def body_search_only(frame: dict | None) -> bool:
    """Whether the words search a body and nothing else: a `loot` act done or tried, and no
    act that looks, searches, tracks or gathers. The reading's closed acts, never words.

    Measured on the narration diagnosis bench (2026-11-04): "I search the bandit's body"
    was read `loot` (right) and the table built the loot; the plan wrote its own `forage`
    and a Survival check beside it — "1 hour of looking: … comes back with 2 Angelica",
    "makes the survival check by 14" — before the bandit was stripped, on 2 of 3 runs, and
    a Perception or Survival check on all 3; dropped from the plan, the same check came
    back from `judgement.inject_checks`, whose verbs read "search" as Perception (live
    check, 2 of 2). The loot op rolls nothing (`Engine._op_loot`): the body's whole kit is
    the search's answer."""
    from . import interpret

    if not frame or frame.get("error"):
        return False
    acts = {str(a.get("act") or "") for a in frame.get("actions") or []
            if interpret.acting(a)}
    return "loot" in acts and not acts & _LOOKING_ACTS


def _searches_the_ground(r) -> bool:
    """A forage, a prospect or a gather, or a Perception or Survival check: what a search
    of the ground or a look around is made of."""
    op = _op(r)
    return op in ("forage", "prospect", "gather") or (
        op == "check" and _skill(r) in ("perception", "survival"))


def loot_is_the_search(raw, frame: dict | None, scene=None, *,
                       notes: list | None = None) -> list:
    """The same rule as `apply`'s, after the word injectors: run behind
    `judgement.inject_checks`, which adds a Perception check for "search" when the plan
    carries none — and the plan carries none once `apply` dropped its own. The player's
    own ops only: somebody else's look is theirs."""
    if not isinstance(raw, list) or not body_search_only(frame):
        return raw
    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    mine = {"", "pc", "None", str(getattr(pc, "ref", "pc"))}
    kept = [r for r in raw if not (_searches_the_ground(r)
                                   and str((r or {}).get("actor") or "") in mine)]
    if len(kept) != len(raw) and notes is not None:
        notes.append("a search of the ground or a look dropped: the words search a body, "
                     "which is the loot")
    return kept


def apply(raw, rows: list[Row], frame: dict | None, scene, *, notes: list | None = None) -> list:
    """The plan, with the reading's goods ops in it.

    1. A plan op that moves the same thing as a built one is replaced by it, wherever it
       stood: the reading settles which way the thing goes and to whom ("the coins from
       the pouch into my coin purse" is coin IN; the model's coin give was a payment OUT).
    2. A plan op that moves a thing and that no act of the reading stands behind is
       overruled: a give to the player needs an act that gets something, a give from the
       player one that parts with something, and a sale needs a `sell` DONE — a sale only
       tried is an offer, never a sale. Only acts done or tried stand behind anything; an
       intended or asked-about one stands behind nothing. Gives
       between other people are theirs.
    3. Built ops the plan did not carry are added.

    Only with a reading: with none there is nothing to stand behind or overrule with, and
    the plan stands alone (`GMAgent.plan_turn`)."""
    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error") or scene is None:
        return raw
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None:
        return raw
    # A blow the table aimed (`victims`) is put in by `judgement.inject_fight`, which aims
    # the plan's own blow at the same person rather than adding a second one.
    built = [i for r in rows if r.act not in VIOLENT_ACTS for i in r.intents]
    nothing = [r.thing for r in rows if r.act in GOODS_ACTS and r.thing and not r.intents]
    acting = [a for a in frame.get("actions") or [] if interpret.acting(a)]
    acts = {str(a.get("act") or "") for a in acting}
    closed = any(a.get("act") == "sell" and (a.get("commit") or "done") == "done"
                 for a in acting)
    out: list = []
    placed: set[int] = set()
    checks = {str((b.get("params") or {}).get("skill") or "").lower()
              for b in built if b.get("op") == "check"}
    tracking = any(b.get("op") == "track" for b in built)
    # A search the table built (`_search`) is the turn's one look for what is hidden here:
    # the plan's Survival for it, its track or its forage would search for something else.
    searching = any(b.get("op") == "check" and (b.get("params") or {}).get("search")
                    for b in built)
    # A trail followed walks where the engine says it leads (`Engine._op_track`), so the
    # plan's own walk for the same follow is not the walk: on the owner's 0.2.21 save
    # (row 136) it was "the fields", toward nothing the engine held.
    # Only when no other deed of the sentence walks ("I head out of town and follow the
    # tracks" keeps its walk out of town).
    trailing = any(b.get("op") == "track" and (b.get("params") or {}).get("follow")
                   for b in built) \
        and not (acts & (interpret._MOVING_ACTS - {"follow"}))
    # A feat of strength the table built (`_exert`) takes the plan's word for how hard the
    # task is — the band of the plan's own check for it, which it then replaces: one roll,
    # the engine's skill and target, the plan's difficulty. Reset on every call, because
    # the rows outlive the attempt and a retried plan may name another band or none.
    exerted = [i for r in rows if r.act == "exert" for i in r.intents if i.get("op") == "check"]
    if exerted:
        band = next((b for b in (_band_of(r) for r in raw
                                 if isinstance(r, dict) and _effort_check(r, pc)) if b),
                    EXERT_BAND)
        for b in exerted:
            b["params"]["dc"] = {"band": band}
    # A steal the table built (`_take` in a fight) is the player's blow at that person:
    # the plan's own attack on them is the same deed, and is replaced, not rolled beside it.
    stolen_from = {str(b.get("target")) for b in built if b.get("op") == "attack"}
    # A job the table built (`jobs_spoken`) is the turn's word on the work: the plan's own
    # week of `work`, or a `quest` it wrote for the same job, would work it or take it twice.
    jobbing = any(b.get("op") == "job" for b in built)
    # And the person the job is with: the plan's `company` of them is not what taking,
    # offering or turning down their work is. The owner's save of 2026-11-05 (row 7):
    # "Accept the terms of the work" to Vyrnys built the job, and the plan's `company c2`
    # beside it was refused as indifferent into "Vyrnys remains unmoved by your words".
    employers = {str(b.get("target") or "") for b in built if b.get("op") == "job"} - {""}
    making = any(b.get("op") == "make" for b in built)
    # A grapple broken (`_escape`) is the turn's word on it: the plan's own Escape Artist
    # check, its grapple at the holder or its own escape would roll a second time for the
    # same deed — and the check at a DC the plan chose removed nothing (2026-11-01).
    escaping = any(b.get("op") == "escape" for b in built)
    # A disguise the table built (`_disguise`) is the turn's one Disguise check: the plan's
    # own Disguise check would make a second disguise (`Engine._op_check` routes one there).
    disguising = any(b.get("op") == "disguise" for b in built)
    # A change of clothes the table built (`_put_on`) is the turn's one `wear` of it: the
    # plan's own for the same outfit would find it already on and be refused beside it.
    dressing = {str((b.get("params") or {}).get("item") or "") for b in built
                if b.get("op") == "wear"} - {""}
    lighting = [str((b.get("params") or {}).get("item") or "") for b in built
                if b.get("op") == "use_item"]
    taken = any(r.act in ("take", "steal") and any(b.get("op") == "give" for b in r.intents)
                for r in rows)
    # A loot or a harvest the table built is the turn's word on that body: the plan's own
    # loot, or a skill check it wrote for the cutting, would strip or roll a second time.
    looting = any(b.get("op") == "loot" for b in built)
    posturing = any(b.get("op") == "condition" and (b.get("params") or {}).get(
        "condition") == "prone" for b in built)
    harvesting = any(b.get("op") == "harvest" for b in built)
    fending = any(b.get("op") in _FEND_OPS for b in built)
    # A go the reading owes a journey for (`interpret.ops_for`: a town the roads reach) is
    # that journey, and the plan's own walk beside it is not: measured on the 0.2.22
    # leftovers run, "I … lead the wagons on toward Kalixiri" from a stretch of the road
    # was planned as a travel to "the outskirts" AND the journey; the travel walked the
    # party a day back to the town they had left, shed the caravan, and the journey was
    # then refused as the turn's second.
    # Any act's journey, since journey-words #2 (2026-11-21): "book passage to Balgrim" and
    # "set sail for Balgrim" are read `journey`, the plan wrote a travel ashore to the docks
    # (or to the deck) beside each, and the walk took the party off the ship it had just
    # boarded, so sailing cost a turn more.
    journeying = any("journey" in r.ops for r in rows)
    # A walk the table carried on (`_carry_on`) is the turn's walk: the plan's own travel
    # beside it would walk twice, or somewhere else.
    carrying_on = any(b.get("op") == "travel" for b in built)
    # A walk home with the person here (`_home_together`) is the turn's walk: the plan's
    # own travel, found or call beside it would walk elsewhere, mint a second house, or
    # knock at a door the person is standing beside (row 56/62 of the owner's 2026-11-05
    # save planned travels to "the private quarters" and a `found` of a tavern for it).
    going_home = any(b.get("op") == "call_on" and (b.get("params") or {}).get("together")
                     for b in built)
    # A commission the table built is the turn's word on that keeper's price: the plan's own
    # `haggle` at them (the counter's Profession roll) becomes the commission's Diplomacy
    # haggle instead (rules/commission.py `_haggle`, owner ruling 2026-11-01). Measured live
    # that day: "I offer the smith five silver to fit a haft to my trident blank" was planned
    # as a haggle and read as a commission done, not tried; the haggle was refused as
    # untrained Profession and the job taken at the list price.
    commissioned = {str((b.get("params") or {}).get("who")): b for b in built
                    if b.get("op") == "commission"}
    from rules import lodging as _lodging

    staying = {str((b.get("params") or {}).get("from_") or "") for b in built
               if b.get("op") == "buy" and str((b.get("params") or {}).get("item") or "")
               .startswith(_lodging.PREFIX)}
    # A take the table built as a give is that act's whole deed: when it is the only act
    # that could stand behind a take-off, the plan's take-off has none. Playtest 2026-11-17
    # #49: "I take the coin from the crew's cargo chest" was planned as take_off of
    # "cargo_chest_coins" beside the built give; the take-off resolved as "is wearing
    # nothing called cargo_chest_coins", and the beat told the one take three times.
    doffs = interpret._OP_NEEDS["take_off"]
    taken = [r for r in rows if r.act == "take"
             and any(i.get("op") == "give" for i in r.intents)]
    unbacked_doff = bool(taken) and sum(1 for a in acting
                                        if a.get("act") in doffs) <= len(taken)
    for r in raw:
        op = _op(r)
        if op == "take_off" and unbacked_doff:
            if notes is not None:
                notes.append("the plan's take_off dropped: the take is the built give")
            continue
        if op == "haggle" and str((r or {}).get("target") or "") in commissioned:
            commissioned[str(r.get("target"))].setdefault("params", {})["haggle"] = True
            if notes is not None:
                notes.append("the plan's haggle folded into the commission's own haggle")
            continue
        if op == "job":
            # Never the plan's (`intents.CODE_ONLY_OPS`): a job is offered and taken by the
            # reader's answer about the player's own words.
            if notes is not None:
                notes.append("the plan's job dropped: only the reading's answer writes one")
            continue
        if op in ("make", "craft"):
            # Never the plan's either (`intents.CODE_ONLY_OPS`, 2026-10-28): the plan's
            # `craft` paid mastery from a tier it chose and made nothing. A craft is the
            # reading's `craft` act, built whole into `make` (`_craft`).
            if notes is not None:
                notes.append(f"the plan's {op} dropped: only the reading's craft makes")
            continue
        if making and op == "check" and str(((r or {}).get("params") or {}).get(
                "skill") or "").lower().startswith(("craft", "profession")):
            # The make op rolls the craft's own check, step by step; the plan's Craft
            # check beside it would be a second roll for the same work.
            if notes is not None:
                notes.append("the plan's craft check replaced by the reading's make")
            continue
        if escaping and str((r or {}).get("actor") or pc.ref) in (pc.ref, "pc") and (
                op == "escape"
                or (op == "check" and str(((r or {}).get("params") or {}).get("skill")
                                          or "").lower() in ("escape artist",
                                                             "escape_artist"))
                or (op == "attack" and str(((r or {}).get("params") or {}).get(
                    "manoeuvre") or "") == "grapple")):
            if notes is not None:
                notes.append(f"the plan's {op} replaced by the reading's escape")
            continue
        # Living off the land or a hunt (`_fend`) is the turn's word on the hours spent
        # looking: the plan's own forage, track, Perception or Survival check, or a wait
        # beside it, is the same looking a second time (owner's report 2026-11-17 #6: a
        # Perception check, a herb forage and a hunt for tracks, and no water). And its
        # drink or meal from the pack is the need the land just met: live 2026-11-18, "I
        # look around for a stream to drink from" carried the plan's `drink`, refused "the
        # pack holds none, and there is no well here", and the page said so beside the
        # stream found.
        if fending and str((r or {}).get("actor") or pc.ref) in (pc.ref, "pc") and (
                op in _FEND_OPS | {"forage", "track", "advance_time", "drink", "eat"}
                or (op == "check" and str(((r or {}).get("params") or {}).get("skill")
                                          or "").lower() in ("perception", "survival"))):
            if notes is not None:
                notes.append(f"the plan's {op} replaced by the reading's fend")
            continue
        # Dropping prone or standing (`_posture`) is the turn's word on the player's
        # posture: the plan's own `move` beside it walked nowhere and told "moves from near
        # to near" (playtest 2026-11-15 #62), and its own prone would lay it twice.
        if posturing and str((r or {}).get("actor") or pc.ref) in (pc.ref, "pc") and (
                (op == "move" and not (acts & interpret._MOVING_ACTS))
                or (op == "condition" and str(((r or {}).get("params") or {}).get(
                    "condition") or "").lower() == "prone")):
            if notes is not None:
                notes.append(f"the plan's {op} replaced by the reading's posture")
            continue
        if disguising and op in ("check", "disguise") and str(((r or {}).get("params") or {})
                                                          .get("skill") or "disguise"
                                                          ).lower() == "disguise":
            if notes is not None:
                notes.append(f"the plan's {op} replaced by the reading's disguise")
            continue
        if op == "wear" and dressing and str(((r or {}).get("params") or {}).get("item")
                                              or "").lower().strip() in dressing:
            continue
        if op == "use_item" and _is_coin(((r or {}).get("params") or {}).get("item")):
            # Coin is spent by a trade, never used: playtest 2026-11-16 N2's `use_item gold
            # piece` was refused into "she has no gold" with 12 gp in her purse.
            if notes is not None:
                notes.append("the plan's use_item of coin dropped")
            continue
        if op == "take_off" and taken and not (acts & {"use", "drop", "other"}):
            # A take the table built whole is the turn's take: the plan's `take_off` beside
            # it is the planner reaching for an op called "take". Playtest 2026-11-17 #48:
            # beside the give of the cargo chest's coin it wrote `take_off
            # cargo_chest_coins`, told "is wearing nothing called cargo_chest_coins".
            if notes is not None:
                notes.append("the plan's take_off dropped: the reading's take is a give")
            continue
        if op == "use_item" and lighting and any(
                _same_thing(((r or {}).get("params") or {}).get("item"), x, pc)
                for x in lighting):
            # The torch the table lights (`_light`): the plan's own would light a second.
            continue
        if op == "disguise":
            # Code-only (`intents.CODE_ONLY_OPS`): a disguise is the reading's act.
            continue
        if looting and op == "loot":
            if notes is not None:
                notes.append("the plan's loot replaced by the reading's")
            continue
        # A body searched is the loot, and only the loot (`body_search_only`).
        if looting and body_search_only(frame) and _searches_the_ground(r):
            if notes is not None:
                notes.append(f"the plan's {op} dropped: the words search a body, which is "
                             f"the loot")
            continue
        if op == "harvest" and not harvesting:
            # Code-only (`intents.CODE_ONLY_OPS`): a harvest is the reading's act.
            if notes is not None:
                notes.append("the plan's harvest dropped: only the reading's harvest cuts")
            continue
        if harvesting and (op == "harvest" or (op == "check" and str(
                ((r or {}).get("params") or {}).get("skill") or "").lower()
                in ("survival", "heal"))):
            if notes is not None:
                notes.append(f"the plan's {op} replaced by the reading's harvest")
            continue
        if jobbing and op in ("work", "quest"):
            if notes is not None:
                notes.append(f"the plan's {op} replaced by the reading's job")
            continue
        if op == "company" and _company_who(scene, r) in employers:
            if notes is not None:
                notes.append("the plan's company dropped: the reading's job is the turn's "
                             "word on the employer")
            continue
        if carrying_on and op == "travel":
            if notes is not None:
                notes.append("the plan's travel replaced by the walk carried on")
            continue
        if going_home and op in ("travel", "found", "venture", "call_on"):
            if notes is not None:
                notes.append(f"the plan's {op} replaced by the walk home together")
            continue
        if journeying and op in ("travel", "found"):
            # And the found the travel was written for: a place minted for a walk that
            # never happens (journey-words #1, "the road to Brackgate" in the ruins).
            if notes is not None:
                notes.append(f"the plan's {op} struck: the reading's go is a journey")
            continue
        if op == "attack" and stolen_from and str((r or {}).get("target")) in stolen_from \
                and str((r or {}).get("actor") or pc.ref) in (pc.ref, "pc"):
            if notes is not None:
                notes.append("the plan's attack replaced by the reading's take, a steal")
            continue
        if op == "quest" and any(b.get("op") == "quest" for b in built):
            # The take-up the table built (`take_ups`) is the quest op for this turn: the
            # plan's own, with its own wording, would be refused as a repeat.
            if notes is not None:
                notes.append("the plan's quest replaced by the reading's take-up")
            continue
        if trailing and op in ("travel", "journey"):
            if notes is not None:
                notes.append(f"the plan's {op} replaced by the reading's follow of a trail")
            continue
        if tracking and (op == "track" or (op == "check" and str(
                ((r or {}).get("params") or {}).get("skill") or "").lower() == "survival")
                or (op == "forage" and "gather" not in acts)):
            # The reading's look for tracks is the table's `track`, built whole: the
            # plan's own copy, its Survival check for the same look, or the forage it
            # reached for (turn 10 of the 2026-10-09 run planned one) would roll twice
            # or search for herbs instead.
            if notes is not None:
                notes.append(f"the plan's {op} replaced by the reading's look for tracks")
            continue
        if searching and str((r or {}).get("actor") or pc.ref) in (pc.ref, "pc") and (
                (op == "track" and "track" not in acts)
                or (op == "check" and _skill(r) == "survival" and "track" not in acts)
                # A prospect too: live 2026-11-20, "I search the woods for my lost silver
                # locket" came back with an hour's dig and two chunks of lead ore.
                or (op in ("forage", "prospect") and "gather" not in acts)):
            if notes is not None:
                notes.append(f"the plan's {op} replaced by the reading's search")
            continue
        if op == "track" and not acts & {"track", "follow"} and str(
                (r or {}).get("actor") or pc.ref) in (pc.ref, "pc"):
            # Tracks are looked for when the player asks for them (the owner, 2026-11-20
            # #19). Live that day: "I look around the woods for the harbourmaster" was
            # read `seek`, the engine said he was not here, and the plan's own track with
            # `follow` rolled Survival and told of footprints.
            if notes is not None:
                notes.append("the plan's track dropped: no look for tracks was asked for")
            continue
        if exerted and _effort_check(r, pc):
            if notes is not None:
                notes.append(f"the plan's {((r.get('params') or {}).get('skill'))} check "
                             f"replaced by the reading's feat of strength (band "
                             f"{exerted[0]['params']['dc']['band']})")
            continue
        if op == "check" and checks and _skill(r) in checks:
            # The table built this check whole (`first_aid`, `_request`): the plan's own
            # copy of it, usually without the patient, would roll a second Heal against
            # nobody — or a second Diplomacy, an Influence Attitude beside the request.
            if notes is not None:
                notes.append(f"the plan's {((r or {}).get('params') or {}).get('skill')} "
                             f"check replaced by the reading's own")
            continue
        if op not in ("give", "sell"):
            out.append(r)
            continue
        p = r.get("params") or {}
        actor = str(r.get("actor") or "")
        target = r.get("target")
        mine = actor in ("", "pc", pc.ref, "None") or str(p.get("from_") or "") == pc.ref \
            or _to_player(p, pc, target)
        if not mine:
            out.append(r)                        # between other people: theirs
            continue
        if _pays_for_the_room(r, acts, scene, pc):
            if notes is not None:
                notes.append(f"the plan's {op} of {p.get('item')!r} to the keeper: the "
                             f"room is the rest's to charge, at the house's price, dropped")
            continue
        if _is_coin(p.get("item")) and str(p.get("to") or target or "") in staying:
            # Coin to the keeper the table bought the room from (`_stay_paid_for`): the
            # stay charges the house's price, so the plan's figure beside it pays twice.
            if notes is not None:
                notes.append("the plan's coin to the keeper: the stay bought charges its "
                             "own price, dropped")
            continue
        if op in ("give", "sell") and _is_coin(p.get("item")) \
                and str(p.get("to") or target or "") in commissioned:
            # Coin to the keeper this turn commissions: the commission charges its own
            # price (rules/commission.py), so the plan's figure beside it would pay twice —
            # the bench's "agree to his price and pay" had the plan pay 10 gold, then 1.
            # A coin `sell` too: the reading's `sell` ("agree to his price") let it stand,
            # and `judgement.inject_payment` made it three gives of a gold, a silver and a
            # copper (the rerun of 2026-11-03, 1 of 3).
            if notes is not None:
                notes.append("the plan's coin to the keeper: the commission charges its "
                             "own price, dropped")
            continue
        twin = next((k for k, b in enumerate(built)
                     if _same_thing(p.get("item"), b["params"].get("item"), pc)), None)
        if twin is None and not _is_coin(p.get("item")) and any(
                _same_thing(p.get("item"), t, pc) for t in nothing):
            # The reading named this very thing and the table found nothing to move —
            # not carried, already carried, not a thing. The plan's op on it goes too.
            # Measured in the replay of the items save's last line: the reading's drop of
            # the brunt found none in the pack, and the plan's `give actor=pc target=c13`
            # of it stood and was refused into the prose ("has no Brunt of the weight").
            if notes is not None:
                notes.append(f"the plan's {op} of {p.get('item')!r}: the reading named it "
                             f"and the table found nothing to move, dropped")
            continue
        if twin is not None:
            b = built[twin]
            # Only for coin going OUT: coin coming in is counted off the records (a pouch,
            # a pile), and a plan's "1 gp" for the pouch's contents is the model's guess.
            if _is_coin(p.get("item")) and _is_coin(b["params"].get("item")) \
                    and not _to_player(b["params"], pc) \
                    and _coin_amount(p) and not _coin_amount(b["params"]):
                # The plan's coin carries the amount the reading's does not: kept. Owner
                # report 2026-11-01 (Corvin, turn 29): "i give him the money as I take the
                # grip" — the reading's give of "money" (no amount) replaced the plan's
                # coin op for ten gold, and the engine asked "How much?" of a price agreed
                # the turn before. The reading still says which way it goes and to whom.
                b["params"] = dict(b["params"], item=p.get("item"),
                                   **({"count": p["count"]} if p.get("count") else {}))
            if twin not in placed:
                placed.add(twin)
                out.append(built[twin])
            if notes is not None:
                notes.append(f"the reading's {built[twin]['op']} of "
                             f"{built[twin]['params'].get('item')} in place of the plan's "
                             f"{op} of {p.get('item')}")
            continue
        if op == "sell":
            stands = closed
        elif _to_player(p, pc, target):
            stands = bool(acts & interpret.GETTING_ACTS)
        elif _is_coin(p.get("item")):
            # Coin out of the purse is a payment, and only paying pays: measured on the
            # table's first run, "It's a deal. You can have the crate." kept the plan's
            # `give gp 1 from pc` beside the sale — the seller paying the buyer.
            stands = bool(acts & PAYING_ACTS)
        else:
            stands = bool(acts & interpret.PARTING_ACTS)
        if not stands:
            if notes is not None:
                notes.append(f"the plan's {op} of {p.get('item')!r}: no act of the "
                             f"reading stands behind it, dropped")
            continue
        out.append(r)
    for k, b in enumerate(built):
        if k in placed:
            continue
        if _pays_for_the_room(b, acts, scene, pc):
            if notes is not None:
                notes.append(f"the reading's give of {b['params'].get('item')!r} to the "
                             f"keeper: the room is the rest's to charge, dropped")
            continue
        if b.get("op") == "give" and _is_coin(b["params"].get("item")) \
                and str(b["params"].get("to") or "") in commissioned:
            if notes is not None:
                notes.append("the reading's coin to the keeper: the commission charges its "
                             "own price, dropped")
            continue
        out.append(b)
    out = fold_price_talk(out, notes)
    out = fold_the_fine(out, scene, notes)
    aim_the_reads(out, acting, scene, pc, notes)
    return out or [{"op": "narrate_only", "because": "nothing the reading stands behind"}]


# The player's own checks whose door reads a subject the plan kept leaving off (round 2,
# rules/skilluses.py): who is read, and what is appraised or studied.
_READS_A_PERSON = frozenset({"sense motive"})
_READS_A_THING = frozenset({"appraise", "spellcraft"})


def aim_the_reads(out: list, acting: list, scene, pc, notes: list | None = None) -> None:
    """A plan's Sense Motive with no target, or Appraise/Spellcraft with no `item`, given
    the subject the reading names: the person its words find (`person`), else the one
    the player is dealing with (`addressed`); the thing its `object` names that the player
    carries. Measured live 2026-11-22 (gemma-4-12B): "I watch Tanna Vell's face closely.
    Is she lying to me?" was planned `check sense motive` with target null, so the read
    had nobody to read. Code finds the person; the plan only named the skill."""
    from rules import tradecraft

    for b in out:
        if not isinstance(b, dict) or b.get("op") != "check" \
                or b.get("actor") not in (None, "", "pc", pc.ref):
            continue
        p = b.get("params") or {}
        skill = str(p.get("skill") or "").strip().lower()
        if skill in _READS_A_PERSON and not b.get("target"):
            words = [" ".join(str(a.get("target") or "").split()) for a in acting]
            ref = next((r for r in (person(scene, w) for w in words if w) if r), "") \
                or addressed(scene)
            if ref and ref != pc.ref:
                b["target"] = ref
                if notes is not None:
                    notes.append(f"the plan's {skill} read aimed at {ref}")
        if skill in _READS_A_THING and not p.get("item"):
            for a in acting:
                said = " ".join(str(a.get("object") or a.get("target") or "").split())
                if said and tradecraft.carries(pc, said):
                    b.setdefault("params", {})["item"] = said
                    break


def _pays_for_the_room(r: dict, acts: set, scene, pc) -> bool:
    """Whether a give is coin from the player to the keeper of the inn or tavern they
    stand in, on a turn whose reading takes a room (`rest`). The rest door bills the room
    at the house's price (`Engine._room_bill`) and holds it for the day; this coin beside
    it would pay for the same bed twice — measured before the bill existed, "I pay for a
    room" moved coin only when the plan wrote a figure for it, and never held a room.
    Structure only: the reading's act, the op's item, its receiver, and what the engine
    holds about the place — never the player's words."""
    if "rest" not in acts or not isinstance(r, dict) or r.get("op") != "give":
        return False
    p = r.get("params") or {}
    if not _is_coin(p.get("item")) or _to_player(p, pc, r.get("target")):
        return False
    from rules import keepers, lodging

    at = str(getattr(scene, "at", "") or "")
    if not lodging.lets_beds(scene, at):
        return False
    keeper = keepers.keeper_in(scene, at)
    to = str(p.get("to") or r.get("target") or "")
    return keeper is not None and to == keeper.ref


# The acts that choose where a walk goes: a move, a person sought or followed, a door
# forced (`interpret._MOVING_ACTS`). A search stands behind a walk only to the places next
# door (`interpret._sought_nearby`).
def walk_in_place(raw, rows: list[Row], frame: dict | None, scene, places=(), *,
                  notes: list | None = None) -> list:
    """The plan, with no travel to the place the party already stands in when the reading
    walks inside it, and no move of the player's own beside the move the table built.

    The gate, 2026-11-11: "I walk up the stair onto the wall-walk above the gate" — the
    reading's walks were inside the place, the table built nothing, and the plan wrote
    `travel` to "the wall-walk above the gate", which the engine answered "You are already
    at the gate." A travel cannot stand in for a walk across the room; the built move is
    that walk (`_to_the_fixture`)."""
    from rules import places as places_mod

    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error") or scene is None:
        return raw
    here = str(getattr(scene, "at", "") or "")
    acts = frame.get("actions") or []

    def inside_here(k: int, a: dict) -> bool:
        # A square of this board named by its coordinate (`_to_the_square`) is a step
        # inside the place, whatever the reader said of it. Owner bug 2026-11-17 #5 (jack,
        # turn 83): "I move to G3" in the woods kept a planned travel to the outskirts as
        # well, an hour away, and the flying squirrel beside G3 was "left behind".
        return interpret.within_place(a, places, here) or (
            a.get("act") == "go" and _a_square(frame, k, scene))

    within = any(interpret.acting(a) and inside_here(k, a) for k, a in enumerate(acts))
    built = [i for r in rows for i in r.intents if i.get("op") == "move"]
    pc = scene.pc() if hasattr(scene, "pc") else None
    if not within and not built:
        return raw

    inside = {" ".join(str(a.get("place") or "").lower().split())
              for k, a in enumerate(acts)
              if interpret.acting(a) and inside_here(k, a)} - {""}

    def is_here(name: str) -> bool:
        if not name:
            return True                     # a travel to nowhere, for a walk in the room
        found = places_mod.find(places, name) if places else None
        # The place stood in, or the very words the reading put inside it — never a
        # place not founded yet ("…then head to the old tannery" keeps its walk).
        return (found is not None and getattr(found, "id", "") == here)             or " ".join(name.lower().split()) in inside

    # Every walk the words make stays inside the place: then no travel, journey or
    # venture is the player's at all. Live on the fix, 2026-11-11: "I go back down"
    # (fixture `floor`) was planned as a travel to the outskirts beside the built move;
    # `unasked_travel` stands aside for any moving act, so it walked the party out of town.
    moving = [(k, a) for k, a in enumerate(acts)
              if interpret.acting(a) and a.get("act") in interpret._MOVING_ACTS]
    inside_only = within and moving and all(inside_here(k, a) for k, a in moving)
    out = []
    for r in raw:
        op = _op(r)
        params = (r.get("params") or {}) if isinstance(r, dict) else {}
        if inside_only and op in ("travel", "journey", "venture"):
            if notes is not None:
                notes.append(f"the plan's {op} dropped: every walk the words make is "
                             f"inside the place")
            continue
        if within and op == "travel" and is_here(str(params.get("place") or "")):
            if notes is not None:
                notes.append(f"the plan's travel to {params.get('place')!r} dropped: the "
                             f"words walk inside the place")
            continue
        if built and op == "move" and pc is not None and not any(r is b for b in built)                 and str(r.get("actor") or "") in (pc.ref, "pc")                 and str(params.get("who") or pc.ref) in (pc.ref, "pc"):
            if notes is not None:
                notes.append("the plan's move replaced by the reading's walk to a fixture")
            continue
        out.append(r)
    return out


def unasked_travel(raw, frame: dict | None, scene=None, places=(), *,
                   notes: list | None = None) -> list:
    """A walk no deed of the player's stands behind is the plan's, and is struck.

    Two measurements, one rule:
      * the fight run, 2026-10-09, turn 8: "I find somewhere quiet and sit down", read
        `search: somewhere quiet` and `wait`, was planned as a travel to the outskirts —
        half an hour through the guildhall, the market and the gate into the desert. The
        plan's own travel is free text the sampler holds to nothing (the places enum binds
        only a `declared` travel, `prompts.turn_schema`), so a search may walk only to a
        place next door (`interpret._sought_nearby`), inside the walls;
      * verifying these fixes live on the town save: "I make camp and sleep until dawn",
        one `rest`, was planned as a travel to the outskirts AND the rest — an hour's walk
        nobody asked for.
    The rule the detectors already answer to (`interpret.supported`), held to the plan's
    own walk: it stands when an act done now moves (`interpret._MOVING_ACTS`) or names a
    place (`rest` at the inn, `wait` at the well). Structure only — the reading's acts and
    slots, and the engine's place finder. With no reading, the plan stands."""
    from rules import places as places_mod

    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error"):
        return raw
    acting_acts = [a for a in frame.get("actions") or [] if interpret.acting(a)]
    # A go or seek whose words name a person standing here (`interpret.ops_for` marks it
    # `here`) walks nowhere: "I go back to the guild clerk" with the clerk at the table.
    if not acting_acts or any((a.get("act") in interpret._MOVING_ACTS or a.get("place"))
                              and not a.get("here") for a in acting_acts):
        return raw
    here = str(getattr(scene, "at", "") or "")
    nearby = set(interpret._sought_nearby(frame, here, places)) if places else set()
    # A place the plan founds for the search is where the search found it: "I look for a
    # tavern where the dockhands drink" is `found` and a walk in (`Engine.validate`'s
    # `_found_before_travel`), and the found door places it by its own rules.
    founded = {" ".join(str(((r or {}).get("params") or {}).get("name") or "").lower().split())
               for r in raw if _op(r) == "found"}
    searching = any(a.get("act") == "search" for a in acting_acts)

    def allowed(r) -> bool:
        if _op(r) == "journey":
            return False
        want = str(((r or {}).get("params") or {}).get("place") or "")
        if searching and " ".join(want.lower().split()) in founded - {""}:
            return True
        found = places_mod.find(places, want) if want and places else None
        return found is not None and found.name in nearby

    out = [r for r in raw if _op(r) not in ("travel", "journey") or allowed(r)]
    if len(out) != len(raw) and notes is not None:
        notes.append("the plan's walk struck: no deed of the player's asked for it"
                     + (f" (a search reaches {', '.join(sorted(nearby))})" if nearby else ""))
    return out or [{"op": "narrate_only", "because": "nothing the reading stands behind"}]


def _company_who(scene, r) -> str:
    """The ref a `company` op's `who` names: a ref however decorated, else the one person
    here of that exact name (the engine's own fallback in `Engine._op_company`)."""
    from rules import intents as intents_mod

    want = str(((r or {}).get("params") or {}).get("who") or "").strip()
    actors = getattr(scene, "actors", {}) or {}
    ref = intents_mod.normalise_ref(want) if want else ""
    if ref and ref in actors:
        return str(ref)
    named = [k for k, a in actors.items()
             if not a.is_pc and " ".join(str(a.name).lower().split()) == want.lower()]
    return named[0] if len(named) == 1 else str(ref or want)


# The acts a player has somebody come along in, or sends them away in: words said, a
# request, anything else (`take_ups`' agreeing acts), and a walk or a journey made with
# them. Only words said or asked stand behind a company by structure alone, when the
# question is not asked or its call fails: an `other` or a walk needs the question's yes.
_COMPANY_ACTS = frozenset({"talk", "request", "other", "go", "journey"})
_COMPANY_SPOKEN = frozenset({"talk", "request"})
# The acts a hire is made in: words said or asked, and `other` — "I hire the guard." was
# read as one and planned as a `check` (tools/hire_bench.py, 2026-11-15). Never a walk:
# going somewhere is not hiring anybody.
_HIRE_ACTS = frozenset({"talk", "request", "other"})
# The acts an order about the other ship comes in: a walk at her ("close with the pirate
# ship" read as `go`), a blow, words to the captain, anything else.
_SEA_ACTS = frozenset({"go", "attack", "talk", "request", "other", "leave", "journey"})
# Hiring is having them come along for pay (the demos say "hire the sellsword"); a guard
# order is its own answer (rules/hirelings.py).
_COMPANY_DOES = {"join": "has them come along", "hire": "has them come along",
                 "leave": "sends them away", "guard": "sets them to guard"}


def company_asked(raw, frame: dict | None, scene, *, ask=None, asked: dict | None = None,
                  notes: list | None = None) -> list:
    """A plan's `company` stands only where the player's own words have that person come
    along — or, for `do: leave`, send them away. Otherwise it is struck, silently: the
    plan's invention, never the player's refusal to hear.

    The owner's save of 2026-11-05 (turn_log row 7): "Accept the terms of the work" to
    Vyrnys, read as one `other`. The table built the job; the plan also wrote `company
    who=c2`, the prompt's own example with no actor and no `because`. The engine refused it
    — "Vyrnys is indifferent towards you and does not walk out of here at your word. Talk
    them round first" — and the planned narrator wrote "Vyrnys remains unmoved by your
    words … You must find a way to convince them", on a turn the player took a job.

    Why not code-only, as `job` is (`intents.CODE_ONLY_OPS`): the reader has no act for
    "come with me" — it is a `talk` or a `request` — so the plan is still the only door a
    real invitation comes in by, and companions are recruited by spoken words (the owner's
    rulings: companions obey in character; Diplomacy requests). So the plan proposes and
    the reading confirms: detected in code (the plan wrote a company; an act done now that
    words could carry it), then ONE closed question per such act
    (`interpret.confirm_company`), asked only on a turn whose plan wrote one. With no
    question (`ask` None: the suite, the reader off) or a failed call, a `talk` or a
    `request` done now stands behind it by structure, as before; an `other` does not.
    `asked` memoises the answers across the plan's attempts. With no reading the plan
    stands alone, as at every door of this table."""
    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error") or scene is None:
        return raw
    if not any(_op(r) == "company" for r in raw):
        return raw
    acting = [a for a in frame.get("actions") or [] if interpret.acting(a)
              and str(a.get("act") or "") in _COMPANY_ACTS]
    spoken = any(str(a.get("act") or "") in _COMPANY_SPOKEN for a in acting)
    memo = asked if asked is not None else {}
    actors = getattr(scene, "actors", {}) or {}
    out: list = []
    for r in raw:
        if _op(r) != "company":
            out.append(r)
            continue
        do = str(((r or {}).get("params") or {}).get("do") or "join").strip().lower()
        ref = _company_who(scene, r)
        who = getattr(actors.get(ref), "name", "") or ref
        want = _COMPANY_DOES.get(do)
        stands = False
        if want is not None and acting:
            answers = []
            if ask is not None:
                for a in acting:
                    key = (str(a.get("span") or ""), who)
                    if key not in memo:
                        memo[key] = ask(key[0], who) or ""
                    answers.append(memo[key])
            if any(answers):
                stands = want in answers
            else:
                # Not asked, or every call failed: the words said carry it, as before.
                stands = spoken
        elif want is None:
            # A `do` the engine does not know is its own printed refusal, with the fix
            # named (`Engine._op_company`); not this door's to judge.
            stands = True
        if stands:
            out.append(r)
            continue
        if notes is not None:
            notes.append(f"the plan's company of {who} struck: the player's words did not "
                         f"ask for it")
    return out or [{"op": "narrate_only", "because": "nothing the reading stands behind"}]


def trade_sought(raw, frame: dict | None, *, notes: list | None = None) -> list:
    """The one newcomer a plan introduces on a turn whose reading went looking for
    somebody by their trade is somebody of that trade: `trade` on the introduce, so the
    population rolls their life to it (`population.note`'s `work`).

    Playtest 2026-11-17b #17/#20: "I walk to the tavern near the docks and look for a
    sellsword for hire" was read `seek: a sellsword for hire`; the finder missed
    (`work:caravan-guard`), the plan introduced "man in corner" with no trade, and the
    next turn he called himself a sellsword with no rate and could never be hired
    (`hirelings.hires_out` reads the population's work). Structure only: the reading's
    one acting `seek` target, the occupation table's own match words for it
    (`lives.occupation_for`), and exactly one introduce whose `who` names no trade of its
    own. Two seeks or two newcomers are not guessed between."""
    from rules import lives

    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error"):
        return raw
    sought = [str(a.get("target") or "") for a in frame.get("actions") or []
              if a.get("act") == "seek" and interpret.acting(a) and a.get("target")]
    newcomers = [r for r in raw if _op(r) == "introduce"]
    if len(sought) != 1 or len(newcomers) != 1:
        return raw
    occ = lives.occupation_for(sought[0])
    params = dict(newcomers[0].get("params") or {})
    if occ is None or params.get("trade") or lives.occupation_for(str(params.get("who") or "")):
        return raw
    # The table's own word the player used, so the newcomer's trade reads as they said it.
    word = next((m for m in occ.get("match") or () if m in sought[0].lower()),
                str(occ["name"]))
    params["trade"] = word
    newcomers[0]["params"] = params
    if notes is not None:
        notes.append(f"the newcomer {params.get('who')!r} is the {word} the player looked for")
    return raw


def orders_spoken(raw, frame: dict | None, scene, *, ask=None, asked: dict | None = None,
                  ask_what=None, notes: list | None = None) -> list:
    """A hire or a guard order the player's words make and the plan left out, added:
    `company do: hire` for a sword for hire the words are said to, `company do: guard` for
    somebody already with the party (or hired by the same words) they are said to.

    Measured live 2026-11-14 (gemma-4-12B, Scrapden tavern): "I will hire you after all,
    sellsword. Come with me." was planned as a `say` and a `greet`, no `company`; the
    sellsword answered "Fine. Lead the way" and stayed where they stood, unpaid (one plan in
    two wrote the hire). The same day, "Your first job: stand over my wares in the hold and
    let nobody near them." was planned as a `say` alone; the sellsword promised to keep
    the wares safe and held no guard.

    Measured 2026-11-15 on a fixed set of 22 spoken hires (tools/hire_bench.py, one plan a
    line, gemma-4-12B): the plans missed 12 (10 of 22 caught); with the three shapes below
    read, 3 (19 of 22), and 0 of 4 control lines (a question, a refusal) hired anybody
    either time. The misses had three shapes this door did not look at: a `say` with no `to`
    ("You're hired. Come with me." to the one guard here), no `say` at all ("I hire the
    guard." planned as a `check`), and a guard order to a sword not yet hired ("I hire the
    guard to guard my cargo." planned as `company do: guard` alone, which the engine
    refuses — they are not with you). So who the words go to is found three ways, in
    code: the plan's `say` addressee; the reading's own target for a spoken or other act,
    found among the people here (`person`); and, a target named nobody, the one person
    the player is dealing with by the engine's state (`addressed`). Then the company
    question already asked of a plan's own company (`interpret.confirm_company`), once per
    act; for a guard, ONE more closed question for what is guarded
    (`interpret.confirm_guarded`, `ask_what`). With no question (`ask` None: the suite,
    the reader off) nothing is added: coin is never spent and no order given on a
    guess."""
    from rules import hirelings, states

    from . import interpret

    if ask is None or not isinstance(raw, list) or not frame or frame.get("error") \
            or scene is None:
        return raw
    actors = getattr(scene, "actors", {}) or {}
    planned = {(_company_who(scene, r),
                str(((r or {}).get("params") or {}).get("do") or "join").lower())
               for r in raw if _op(r) == "company"}
    # The reading's own hire (`_request`, a check the engine takes to the wage door).
    planned |= {(str((r or {}).get("target") or ""), "hire") for r in raw
                if _op(r) == "check"
                and str(((r or {}).get("params") or {}).get("request") or "") == "hire"}
    spoken = [a for a in frame.get("actions") or [] if interpret.acting(a)
              and str(a.get("act") or "") in _HIRE_ACTS]
    if not spoken:
        return raw
    memo = asked if asked is not None else {}
    out = list(raw)
    # A line said to nobody by name, with one companion along, is said to them: measured
    # live 2026-11-14, the guard order above was read as a `talk` with no target and
    # planned as a `say` with no `to`, the sellsword the only one travelling with the
    # party. Only a guard order is taken this way; a hire needs its addressee found.
    along = [k for k, x in actors.items()
             if not getattr(x, "is_pc", False) and x.has_state(states.TRAVELS_WITH_YOU)]
    heard: list[tuple[str, bool]] = []
    for r in raw:
        if _op(r) != "say":
            continue
        ref = str(((r or {}).get("params") or {}).get("to") or "")
        unnamed = not ref and len(along) == 1
        heard.append((along[0] if unnamed else ref, unnamed))
    # Said to nobody by name, with nobody the engine has the player dealing with: the one
    # sword for hire standing here, if there is exactly one ("You're hired. Come with me."
    # in a market of five, tools/hire_bench.py). The company question still decides.
    swords = [k for k, x in actors.items() if not getattr(x, "is_pc", False)
              and not x.is_down and hirelings.wage(x) is None and hirelings.hires_out(scene, x)]
    for a in spoken:
        target = str(a.get("target") or "").strip()
        ref = person(scene, target) if target else addressed(scene)
        if not ref and not target and len(swords) == 1:
            ref = swords[0]
        heard.append((ref, False))
    seen: set[str] = set()
    for ref, unnamed in heard:
        who = actors.get(ref)
        if who is None or getattr(who, "is_pc", False) or ref in seen:
            continue
        seen.add(ref)
        hireable = hirelings.wage(who) is None and hirelings.hires_out(scene, who) \
            and (ref, "hire") not in planned and not unnamed
        guardable = who.has_state(states.TRAVELS_WITH_YOU) and (ref, "guard") not in planned
        # The plan's own guard order to a sword nobody has hired yet ("I hire the guard to
        # guard my cargo"): the hire the order needs, ahead of it.
        ordered = (ref, "guard") in planned and not who.has_state(states.TRAVELS_WITH_YOU)
        if not (hireable or guardable):
            continue
        for a in spoken:
            span = str(a.get("span") or "")
            key = (span, who.name)
            if key not in memo:
                memo[key] = ask(span, who.name) or ""
            hired_now = hireable and (memo[key] == "has them come along" or (
                memo[key] == "sets them to guard" and not who.has_state(
                    states.TRAVELS_WITH_YOU)))
            if hired_now:
                hire = {"op": "company", "because": "the player hired them",
                        "params": {"who": ref, "do": "hire"}}
                at = next((k for k, r in enumerate(out) if _op(r) == "company"
                           and _company_who(scene, r) == ref), len(out)) if ordered \
                    else len(out)
                out.insert(at, hire)
                planned.add((ref, "hire"))
                if notes is not None:
                    notes.append(f"the hire of {who.name} the words made, added")
            guarded = memo[key] == "sets them to guard" and (guardable or hired_now) \
                and (ref, "guard") not in planned
            if guarded:
                what = (ask_what(span, who.name) if ask_what is not None else "") or "you"
                out.append({"op": "company", "because": "the player set them to guard",
                            "params": {"who": ref, "do": "guard", "what": what}})
                planned.add((ref, "guard"))
                if notes is not None:
                    notes.append(f"the guard order to {who.name} the words gave, added")
            if hired_now or guarded:
                break
    return out


# The acts a bout is asked for in, besides the reader's own `challenge`: words to the house,
# a request, anything else.
_BOUT_ACTS = frozenset({"talk", "request", "other"})


def bout_spoken(raw, frame: dict | None, scene, *, ask=None, places=(),
                notes: list | None = None) -> list:
    """The `bout` the player's words ask the arena for, when the reading built none.

    Playtest 2026-11-17b #24 and the live check of 2026-11-18: words asking the master of
    the games for a bout came back `talk`, `other` or a bare question, never `challenge`,
    and the house staged nothing. Detected in code (the party stands at an arena, or the
    same plan walks there; no `bout` in the plan; an act done now), repaired by ONE closed
    question per act (`interpret.confirm_bout`). With no question (`ask` None) nothing is
    added; the engine still refuses a bout where no house stages one."""
    from rules import arena, keepers
    from rules import places as places_mod

    from . import interpret

    if ask is None or not isinstance(raw, list) or not frame or frame.get("error") \
            or scene is None or any(_op(r) == "bout" for r in raw):
        return raw
    pc = scene.pc() if hasattr(scene, "pc") else None
    founded = getattr(scene, "founded", ()) or ()
    going = [places_mod.find(places, str(((r or {}).get("params") or {}).get("place") or ""))
             for r in raw if _op(r) == "travel"]
    there = keepers.kind_of(str(getattr(scene, "at", "") or ""), founded) == arena.KIND \
        or any(p is not None and keepers.kind_of(p.id, founded) == arena.KIND for p in going)
    if pc is None or not there:
        return raw
    for a in frame.get("actions") or []:
        if not interpret.acting(a) or str(a.get("act") or "") not in _BOUT_ACTS:
            continue
        if ask(str(a.get("span") or "")) != "bout":
            continue
        if notes is not None:
            notes.append("the bout the words asked for, added")
        return raw + [{"op": "bout", "actor": pc.ref, "params": {},
                       "because": "the player asks for a bout"}]
    return raw


def sea_spoken(raw, frame: dict | None, scene, *, ask=None, notes: list | None = None) -> list:
    """The `sea` op the player's words make about the other ship, when the plan wrote none.

    Measured live 2026-11-15 (fix/merchant-road, pirates a sail away): "I tell the captain
    to bring us alongside the Cold Hound." was planned as a `say`; "We close with the pirate
    ship." was read `go, place: the pirate ship` and refused "You don't know of anywhere
    called the pirate ship"; the pirates stayed on the horizon and no fight on deck could
    be reached by words at all — no prompt names the op. Detected in code (an engagement on
    `Scene.sea`, no `sea` in the plan, an act done now), repaired by ONE closed question per
    act over the engine's own verbs (`interpret.confirm_sea`). A board takes everybody
    travelling with the party. With no question (`ask` None) nothing is added."""
    from rules import states

    from . import interpret

    sea = getattr(scene, "sea", None) or {}
    if ask is None or not isinstance(raw, list) or not frame or frame.get("error")             or not sea.get("theirs") or any(_op(r) == "sea" for r in raw):
        return raw
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None:
        return raw
    for a in frame.get("actions") or []:
        if not interpret.acting(a) or str(a.get("act") or "") not in _SEA_ACTS:
            continue
        do = ask(str(a.get("span") or ""))
        if not do:
            continue
        params: dict = {"do": do}
        if do == "board":
            params["with"] = [k for k, x in (getattr(scene, "actors", {}) or {}).items()
                              if not x.is_pc and x.has_state(states.TRAVELS_WITH_YOU)]
        if notes is not None:
            notes.append(f"the ship's {do} the words gave, added")
        kept = [r for r in raw if _op(r) != "narrate_only"]
        return kept + [{"op": "sea", "actor": pc.ref, "because": "the player's orders at sea",
                        "params": params}]
    return raw


# The acts a cruise comes in: a journey to no port ("out along the trade route"), a seek
# of a ship, a wait for one, an order to the crew, anything else.
_CRUISE_ACTS = frozenset({"journey", "seek", "wait", "talk", "request", "other"})


def cruise_spoken(raw, frame: dict | None, scene, *, ask=None,
                  notes: list | None = None) -> list:
    """The `sea` op's `cruise` the player's words make, aboard a ship the PC holds with no
    other ship in sight (playtest 2026-11-16 #8/#9: "take the Red Gull out along the trade
    route, hunting for a merchant ship to rob" was planned as a journey to "the trade
    route", refused for no such port, and a seek of "a merchant ship" was answered "The
    merchant, is not here"). Detected in code (the ship is the PC's, no engagement, no
    `sea` in the plan, an act done now), repaired by ONE closed question per act
    (`interpret.confirm_cruise`). A cruise stands in for the plan's every way of going
    somewhere and its `narrate_only`: the engine's cruise is where she goes, and what she
    meets is told. Live 2026-11-16 the plan wrote `travel` and `found` to "the trade
    route" five times and the turn degraded to narration with the question answered.
    With no question (`ask` None) nothing is changed."""
    from rules import ships

    from . import interpret

    pc = scene.pc() if hasattr(scene, "pc") else None
    if ask is None or pc is None or not isinstance(raw, list) or not frame \
            or frame.get("error") or getattr(scene, "sea", None) \
            or any(_op(r) == "sea" for r in raw):
        return raw
    ship = ships.aboard(scene)
    if ship is None or ship.held_by != pc.ref:
        return raw
    for a in frame.get("actions") or []:
        if not interpret.acting(a) or str(a.get("act") or "") not in _CRUISE_ACTS:
            continue
        if ask(str(a.get("span") or "")) != "cruise":
            continue
        if notes is not None:
            notes.append("the ship's cruise the words gave, added")
        kept = [r for r in raw
                if _op(r) not in ("narrate_only", "journey", "travel", "found")]
        return kept + [{"op": "sea", "actor": pc.ref, "because": "the player puts her out "
                        "to cruise", "params": {"do": "cruise"}}]
    return raw


def travel_named(raw, frame: dict | None, places=(), *, notes: list | None = None) -> list:
    """A `travel` with no `place`, given the one place here the reading's walk names.

    Measured live 2026-11-16 (playtest #14 replayed): "I go back aboard the Red Gull" was
    read `go, place: the Red Gull`, her deck one of this town's places; the plan wrote
    `travel` with a placeholder target and no place, the placeholder was taken out
    (`judgement.settle_placeholders`), and the engine refused "Nobody moves: where to?".
    Detected in code (the op, the empty param), repaired from the reading's own slot when
    exactly one walk names a place `places.find` knows; the engine still judges the walk."""
    from rules import places as places_mod

    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error") or not places:
        return raw
    found = [places_mod.find(places, str(a.get("place") or ""))
             for a in frame.get("actions") or []
             if a.get("act") == "go" and interpret.acting(a)
             and str(a.get("place") or "").strip()]
    if len(found) != 1 or found[0] is None:
        return raw
    out = []
    for r in raw:
        params = (r or {}).get("params") if isinstance(r, dict) else None
        if _op(r) == "travel" and not str((params or {}).get("place") or "").strip():
            r = {**r, "params": {**(params or {}), "place": found[0].id}}
            if notes is not None:
                notes.append(f"the walk's place, {found[0].name}, from the words")
        out.append(r)
    return out


def journey_named(raw, frame: dict | None, *, notes: list | None = None) -> list:
    """A `journey` with no `to`, given the one place the reading's journey act names.

    Measured live 2026-11-15 (Zhilvarnia, fix/merchant-road): "I head to the docks with my
    guard and book passage to Mirabalos for us and my silk." was read `journey, place:
    Mirabalos`; the plan wrote `journey` without `to` five times, every attempt refused
    "missing required param(s) to", and the turn degraded to narration — nobody moved.
    Detected in code (the op, the empty param), repaired from the reading's own slot; the
    engine still judges the place (`Engine._op_journey`). Only with exactly one journey act
    naming a place: two are a pairing this does not guess."""
    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error"):
        return raw
    places = [str(a.get("place") or "").strip() for a in frame.get("actions") or []
              if a.get("act") == "journey" and interpret.acting(a)
              and str(a.get("place") or "").strip()]
    if len(places) != 1:
        return raw
    out = []
    for r in raw:
        params = (r or {}).get("params") if isinstance(r, dict) else None
        if _op(r) == "journey" and not str((params or {}).get("to") or "").strip():
            r = {**r, "params": {**(params or {}), "to": places[0]}}
            if notes is not None:
                notes.append(f"the journey's place, {places[0]}, from the words")
        out.append(r)
    return out


def led_along(raw, frame: dict | None, scene, *, notes: list | None = None) -> list:
    """Somebody here the reading's walk takes along (`go`/`leave`/`journey` whose `object`
    is a person here) is put in every walk's `with`; the engine then decides whether they
    come and whether they stay with the party (`Engine._op_travel`, the `company` rule).

    Playtest 2026-11-17 #34: the smuggler had just said "I'll follow you into the dark",
    and "I lead the smuggler on into the broken pen" was refused twice as a travel that
    would leave him behind, then built a 10 ft move inside the cells. Structure, not
    English: the reader's slot names the person, the engine's finder says who."""
    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error") or scene is None:
        return raw
    led: list[str] = []
    for a in frame.get("actions") or []:
        if not isinstance(a, dict) or a.get("act") not in ("go", "leave", "journey")                 or not interpret.acting(a):
            continue
        ref = person(scene, a.get("object"))
        actor = (getattr(scene, "actors", {}) or {}).get(ref)
        if actor is not None and not actor.is_pc and ref not in led:
            led.append(ref)
    if not led:
        return raw
    out = []
    for r in raw:
        if _op(r) in ("travel", "journey"):
            params = dict((r or {}).get("params") or {})
            taken = params.get("with") or []
            taken = [taken] if isinstance(taken, str) else list(taken)
            more = [ref for ref in led if ref not in taken]
            if more:
                r = {**r, "params": {**params, "with": taken + more}}
                if notes is not None:
                    notes.append(f"{', '.join(more)} led along on the walk, from the words")
        out.append(r)
    return out


def wage_not_tipped(raw, scene, *, notes: list | None = None) -> list:
    """No coin `give` beside a hire to the same person: the engine's wage is the payment.

    Measured live 2026-11-14: "Here is your coin, sellsword. You are hired; come with me."
    was planned as `company do: hire` AND `give gp 1 to c10`, and the purse paid the week's
    wage the engine named plus a gold piece the model did. No model authors a number (the
    third law), so the give is struck and the note says why; the hire's own tell says what
    was paid."""
    from rules import goods
    from rules import intents as intents_mod

    if not isinstance(raw, list) or scene is None:
        return raw
    hired = {_company_who(scene, r) for r in raw if _op(r) == "company"
             and str(((r or {}).get("params") or {}).get("do") or "").lower() == "hire"}
    hired |= {str((r or {}).get("target") or "") for r in raw if _op(r) == "check"
              and str(((r or {}).get("params") or {}).get("request") or "") == "hire"}
    hired.discard("")
    if not hired:
        return raw
    pc = scene.pc() if hasattr(scene, "pc") else None
    coins = {c for c, _v in goods.DENOMINATIONS} | {"coin", "coins"}
    out = []
    for r in raw:
        params = (r or {}).get("params") or {}
        if _op(r) == "company" and str(params.get("do") or "join").lower() == "join" \
                and _company_who(scene, r) in hired:
            # The plan's own "come along" beside the hire: the hire brings them. Live
            # 2026-11-18, it was refused beside it "is indifferent ... Talk them round".
            if notes is not None:
                notes.append("the plan's company struck: the hire brings them along")
            continue
        to = intents_mod.normalise_ref(str(params.get("to") or ""))
        frm = str(params.get("from_") or params.get("from") or (r or {}).get("actor") or "")
        if (_op(r) == "give" and to in hired
                and str(params.get("item") or "").strip().lower() in coins
                and frm in ("", "pc", getattr(pc, "ref", "pc"))):
            if notes is not None:
                notes.append(f"the coin given to {to} struck: the hire pays the engine's wage")
            continue
        out.append(r)
    return out or [{"op": "narrate_only", "because": "nothing the reading stands behind"}]


def address_the_named(raw, frame: dict | None, scene, *,
                      notes: list | None = None, places=()) -> list:
    """The player's line goes to the person the reading's `talk` names — never to
    somebody else the plan picked.

    Measured live 2026-10-09 (gemma-4-12B, Pangrella, turn 8): "I ask the gate guard what
    lies north" was read `talk, target: the gate guard`; the plan introduced the guard
    (new1, made c6) and then wrote the `say` to c4, the smith — the last conversation
    partner, standing at the gate only because the prose had walked him there — and the
    engine opened a conversation with the smith. Nothing checked the say's addressee
    against the words.

    Structure and the engine's finders only, no English read:
      * the target found among the people here (`person`, i.e. `scope.in_the_room`, a
        bare pronoun by `addressed`) is who the line goes to;
      * a target found nobody here, in a plan that introduces somebody, is the person the
        plan brings in — the introduce's first placeholder (one introduce per plan,
        `Engine.validate`) — and the say is put after it so the placeholder exists;
      * anything else is left as the plan wrote it.
    Only when the reading has exactly one spoken-to target and the plan one say by the
    player: two of either is a pairing this does not guess."""
    from rules.intents import INTRODUCED_REFS

    from . import interpret

    if not isinstance(raw, list) or not frame or frame.get("error") or scene is None:
        return raw
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None:
        return raw
    named = [str(a.get("target") or "").strip()
             for a in frame.get("actions") or []
             if a.get("act") in ("talk", "insult") and interpret.acting(a)
             and str(a.get("target") or "").strip()]
    says = [k for k, r in enumerate(raw) if _op(r) == "say"
            and str(r.get("actor") or "pc").lower() in ("pc", pc.ref.lower(), "none", "")]
    if places and len(named) > 1 and len(named) == len(says):
        return _each_to_its_own(raw, frame, scene, places, says, notes)
    # Who is spoken to after the line's own walk is looked for where it ends (#94). A say
    # no talk owns is looked for where its own words were said (`_said_in`, #30): "I go to
    # the barracks and challenge one of the soldiers" speaks at the barracks.
    owner = _said_in(raw[says[0]], frame) \
        if says and not any(a.get("act") in interpret._ADDRESSING_ACTS
                            for a in frame.get("actions") or []) else None
    scene = (interpret.scene_by_then(frame, scene, places, upto=owner) if places
             and owner is not None else
             interpret.scene_by_then(frame, scene, places) if places else scene)
    if not named and len(says) == 1:
        return _said_to_nobody(raw, frame, scene, says[0], notes,
                               moved=owner is not None and _seen_from(scene))
    if len(named) != 1 or len(says) != 1:
        return raw
    want = person(scene, named[0])
    intro = next((k for k, r in enumerate(raw) if _op(r) == "introduce"), None)
    if not want:
        # A pronoun the engine could not settle names nobody new either.
        if intro is None or named[0].lower() in _PRONOUNS:
            return raw
        want = INTRODUCED_REFS[0]
    k = says[0]
    say = raw[k]
    params = dict(say.get("params") or {})
    if params.get("to") == want:
        return raw
    was = params.get("to") or "nobody named"
    params["to"] = want
    out = list(raw)
    # The plan writes the addressee twice as often as not (turn 8: `target: c4` and
    # `params.to: c4`); both, or the target's ref check refuses the say.
    out[k] = dict(say, params=params, **({"target": want} if say.get("target") else {}))
    if want == INTRODUCED_REFS[0] and intro is not None and k < intro:
        out.insert(intro, out.pop(k))
    if notes is not None:
        notes.append(f"the say to {was} goes to {want}: the one the player's words name")
    return out


def once_each_walk(raw, *, notes: list | None = None) -> list:
    """A plan's second `travel` to the place an earlier one in the list already goes,
    struck. Live 2026-11-17 on the playtest's #75 line, once the whole line ran: the plan
    wrote the walk to the docks three times, and the two the engine refused ("The party has
    already travelled this turn and is at the docks") reached the page as "Since you've
    already made your travel for this turn". The same op with the same params, compared
    as data; a walk on to somewhere else is kept for the engine's one-journey rule."""
    if not isinstance(raw, list):
        return raw
    seen, out = [], []
    for r in raw:
        if _op(r) == "travel":
            key = dict((r or {}).get("params") or {})
            if key in seen:
                if notes is not None:
                    notes.append(f"a second travel to {key.get('place')!r} struck")
                continue
            seen.append(key)
        out.append(r)
    return out


def _each_to_its_own(raw, frame, scene, places, says: list[int], notes) -> list:
    """Two or more lines to two or more people named, as many says as talks: the n-th
    say goes to the one the n-th talk names, looked for where the line has walked to by
    then (`interpret.scene_by_then`). Live 2026-11-17 on the playtest's #75 line: "I tell
    the deckhand I'll be back by nightfall, then walk down to the docks and ask the
    foreman…" ran whole, and the parting words went to nobody ("Vesna Kroll speaks, to
    the effect that…"), since this door paired only one talk with one say. Nobody new is
    named here: a name not found leaves that say as the plan wrote it."""
    from . import interpret

    talks = [k for k, a in enumerate(frame.get("actions") or [])
             if a.get("act") in ("talk", "insult") and interpret.acting(a)
             and str(a.get("target") or "").strip()]
    out = list(raw)
    for k, at in zip(says, talks):
        name = str(frame["actions"][at]["target"]).strip()
        want = person(interpret.scene_by_then(frame, scene, places, upto=at), name)
        params = dict(out[k].get("params") or {})
        if not want or params.get("to") == want:
            continue
        was = params.get("to") or "nobody named"
        params["to"] = want
        out[k] = dict(out[k], params=params,
                      **({"target": want} if out[k].get("target") else {}))
        if notes is not None:
            notes.append(f"the say to {was} goes to {want}: the one the player's words name")
    return out


def _seen_from(scene) -> bool:
    from rules.engine import SeenFrom

    return isinstance(scene, SeenFrom)


def _nearest_answerer(scene) -> str:
    """The ref of the nearest person here who would answer a question put to the room: up,
    seen, not hostile, and not the market's master, who answers only the one who turns to
    them (`gm/checks/master_unprompted.py`). Nearest by the board's squares, else the first.
    "" for nobody."""
    from rules import attitude, keepers

    pc = scene.pc() if hasattr(scene, "pc") else None
    master = keepers.master_here(scene)
    pos = getattr(scene, "positions", None) or {}
    me = tuple(pos.get(getattr(pc, "ref", ""), ()) or ())[:2]
    who = [(r, a) for r, a in (getattr(scene, "actors", {}) or {}).items()
           if not a.is_pc and a.name and not a.is_down and not a.has_state("state.hidden")
           and attitude.of(a) != attitude.HOSTILE
           and (master is None or r != master.ref)]
    if not who:
        return ""

    def far(item) -> int:
        there = tuple(pos.get(item[0], ()) or ())[:2]
        return max(abs(there[0] - me[0]), abs(there[1] - me[1])) if me and there else 999

    return min(who, key=far)[0]


def _said_to_nobody(raw, frame, scene, k: int, notes, moved: bool = False) -> list:
    """A line the reading says nobody would answer goes to nobody the plan picked.

    Measured live 2026-11-15 (the table-checks lane; first seen 2026-11-07): 'I mutter
    "fool" and walk out' was read `talk`, no target, cost `free` — "words said to nobody
    who would answer" — and the plan wrote the say `to` the potboy, one of two people in
    the inn; the engine opened a conversation with him and the page had Kesst call him a
    fool. The reader's own cost is the evidence, no English read. The one the player is
    plainly dealing with (`addressed`: engaged, in conversation, or the only other person
    here) still hears it, as `Engine._op_say` would decide with no `to`."""
    from . import interpret

    talks = [a for a in frame.get("actions") or []
             if a.get("act") == "talk" and interpret.acting(a)]
    say = raw[k]
    params = dict(say.get("params") or {})
    was = str(params.get("to") or say.get("target") or "")
    # Or said to somebody the line's own walk left behind: playtest 2026-11-17b #11, "I walk
    # to the guildhall and ask if anyone's hiring a blade", the plan wrote the say `to` the
    # barkeep she had been talking with in the tavern, the engine found nobody of that ref
    # at the guildhall, and the clerk, the one person there, was told "ignoring the
    # inquiry". Asked aloud in a room of one, it is asked of that one (`Engine._op_say`'s
    # own rule, which an absent `to` had switched off). `scene` is where the walk ends.
    # `moved`: a say no talk owns, said after the line's walk (#30) — the same test.
    gone = (bool(talks) or moved) and bool(was)         and was not in (getattr(scene, "actors", {}) or {})
    # A question put to the room, the reader naming nobody: asked of somebody who can
    # answer. jack T276 (owner's save 2026-11-17), "I ask how to get to the docks?" at the
    # market: the say went to nobody, no reply was written, and the page had the master and
    # a keeper go about their business; the player had to ask again by name. The engine
    # reads only `to`, and fills a missing one only in a room of one. Live on this branch
    # the plan wrote the say three ways — no `to`, `to=new1` nobody introduced, and
    # `target` on the market's master with no `to` — and each went to nobody.
    to = str(params.get("to") or "")
    if talks and (not to or to not in (getattr(scene, "actors", {}) or {})) \
            and all(interpret.cost_of(a, scene) == "addresses" for a in talks):
        from rules import keepers

        master = keepers.master_here(scene)
        aimed = was if was in (getattr(scene, "actors", {}) or {}) \
            and (master is None or was != master.ref) else ""
        # The plan's own aim when it is somebody who answers; then the one the player is
        # dealing with; then the nearest who can answer (never the master unprompted).
        near = aimed or addressed(scene) or _nearest_answerer(scene)
        if near:
            out = list(raw)
            out[k] = dict(say, params=dict(params, to=near), target=near)
            if notes is not None:
                notes.append(f"the say to nobody goes to {near}: the nearest who can answer")
            return out
    if not gone and (not talks
                     or any(str(a.get("cost") or "") != "free" for a in talks)):
        return raw
    keep = addressed(scene)
    if not was or was == keep:
        return raw
    params.pop("to", None)
    if keep:
        params["to"] = keep
    out = list(raw)
    out[k] = {key: v for key, v in dict(say, params=params).items() if key != "target"}
    if keep:
        out[k]["target"] = keep
    if notes is not None:
        notes.append(f"the say to {was} goes to {keep or 'nobody'}: "
                     + ("the one it was meant for is not where the walk ends" if gone else
                        "the words were said to nobody who would answer"))
    return out


def timed_rests(raw, frame: dict | None, *, notes: list | None = None) -> list:
    """A sleep the words put a waking time on carries it: the reading's `time` slot,
    verbatim ("until dawn"), as the rest's `until`, which the engine reads against the
    clock (`Engine._camp_for`). Measured live 2026-10-09 (gemma-4-12B, Pangrella, turn
    11): "I make camp and sleep until dawn" was read `rest, time: until dawn`, the rest
    was planned `kind: night` with nothing else, and the party slept eight hours from
    11:57 and woke at 7.57 pm. The slot had nowhere to go.

    The time is the player's words or nothing: an `until` the plan wrote with no rest of
    the reading's behind it is struck — a model choosing when the player wakes is a model
    authoring the clock (law 3). Structure only: the reading's act and slot, never the
    sentence."""
    from . import interpret

    if not isinstance(raw, list):
        return raw
    said = ""
    if frame and not frame.get("error"):
        # The reader's time of day when it named one ("till tomarrow" → "until morning",
        # `interpret.UNTILS`), else the slot's own words, as before 2026-11-01.
        said = next((interpret.until_words(a)
                     for a in frame.get("actions") or []
                     if a.get("act") == "rest" and interpret.acting(a)
                     and interpret.until_words(a)), "")
    out = []
    for r in raw:
        if _op(r) != "rest":
            out.append(r)
            continue
        params = dict(r.get("params") or {})
        if said:
            if params.get("until") != said:
                params["until"] = said
                if notes is not None:
                    notes.append(f"the rest runs {said!r}, the player's own time")
        elif params.pop("until", None) is not None and notes is not None:
            notes.append("the plan's waking time struck: the player named none")
        out.append(dict(r, params=params))
    return out


# What a wait the words give no length to puts on the clock ("I wait to see who comes").
# HOUSE: ten minutes, "a while"; the length the watch takes to answer a report
# (content/rules/law.json `report.minutes`), so waiting over a crime sees who comes.
OPEN_WAIT_MINUTES = 10
_OWN_CLOCK = frozenset({"advance_time", "rest", "travel", "venture", "journey", "forage",
                        "prospect", "gather", "live_off_land", "hunt"})
# The ops a `fend` builds (`_fend`).
_FEND_OPS = frozenset({"live_off_land", "hunt"})


def _open_wait(raw, wait, resting, scene, notes) -> list:
    """A wait with no time in the words passes `OPEN_WAIT_MINUTES` — by the engine's
    number, never the plan's — unless the plan already moves the clock.

    Playtest 2026-11-15 #46: "I stand over the merchant and wait to see who comes" was
    read `wait` twice, and the plan was a bare narrate_only: no rule applied and the clock
    stuck at 8h 32m, so nothing that was coming could come."""
    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    if wait is None or resting or pc is None or wait.get("time") \
            or getattr(scene, "in_encounter", False) \
            or any(_op(r) in _OWN_CLOCK for r in raw):
        return raw
    if notes is not None:
        notes.append(f"an open wait: {OPEN_WAIT_MINUTES} minutes on the clock")
    return list(raw) + [{
        "op": "advance_time", "actor": pc.ref,
        "params": {"amount": OPEN_WAIT_MINUTES, "unit": "minutes"},
        "because": "the player waited a while"}]


def timed_waits(raw, frame: dict | None, scene, *, notes: list | None = None) -> list:
    """A wait the words put a time of day on runs to it: the plan's `advance_time` is set
    to the minutes from now to that time (`interpret.until_minutes`), the clock's
    arithmetic and never the model's.

    Owner report 2026-11-01 (Corvin, turn 19): "wait till tomarrow" was read `wait, time:
    till tomarrow`; the plan wrote `advance_time 1 day`, nothing corrected it (the wait
    door's table has no "tomorrow", and the misspelling would beat it if it had), and
    "1 day pass" ran the clock from 22:00 to 22:00 — "When the new day breaks" written over
    a late evening. The reader names the time of day now (`interpret.UNTILS`), and this
    turns it into minutes. A wait the reading gives a length or no time is left as the
    plan wrote it. Structure only: the reading's act, slot and enum."""
    from . import interpret

    if not isinstance(raw, list) or scene is None or not frame or frame.get("error"):
        return raw
    wait = next((a for a in frame.get("actions") or []
                 if a.get("act") == "wait" and interpret.acting(a)), None)
    resting = any(a.get("act") == "rest" and interpret.acting(a)
                  for a in frame.get("actions") or [])
    if wait is not None and not resting and any(_op(r) == "rest" for r in raw):
        # A wait is never a night: the plan's `rest` beside a wait and no rest act of the
        # reading is struck, whatever time the words give. Measured live 2026-11-15 (the
        # table-checks lane): "I stroll to the fire, warm my hands and doze off" was read
        # `wait` (a doze, `interpret.ACTS`), the plan wrote `rest`, and the rest door asked
        # 5 sp for a room at the inn. With nothing left, the turn is narrated, as a wait
        # with no time is (`interpret.ops_for` owes it no op).
        raw = [r for r in raw if _op(r) != "rest"] or [
            {"op": "narrate_only", "because": "the player dozed: a wait, not a night"}]
        if notes is not None:
            notes.append("the plan's rest dropped: the words wait, not sleep the night")
    clock = int(getattr(scene, "clock_minutes", 0) or 0)
    minutes = interpret.until_minutes(wait, clock) if wait is not None else None
    if minutes is None:
        return _open_wait(raw, wait, resting, scene, notes)
    out, changed = [], False
    # One wait, one clock: a `rest` the plan wrote beside the wait, with no rest act of the
    # reading behind it, is the same night counted twice. Measured on the narration
    # diagnosis bench (2026-11-04): "I wait until morning" at 18:24 was read `wait, until:
    # morning`; the plan wrote `rest: night` AND an `advance_time`, set to 696 minutes
    # here; the rest slept twelve hours and the wait then ran its 696 minutes on top, so
    # the player "waiting until morning" came out of it at 17:36 the next day — and the
    # narrator, told only "696 minutes pass", wrote the afternoon sun. And in the cell
    # ("I sit in the cell and wait for dawn") the same rest was refused — "still in
    # conversation" — a refusal of a sleep nobody asked for, told on the page.
    if not resting and any(_op(r) == "advance_time" for r in raw):
        kept = [r for r in raw if _op(r) != "rest"]
        if len(kept) != len(raw) and notes is not None:
            notes.append("the plan's rest dropped: the words wait, and the wait is the "
                         "clock's one move")
        raw = kept
    for r in raw:
        if _op(r) == "advance_time":
            params = dict(r.get("params") or {})
            if (params.get("amount"), params.get("unit")) != (minutes, "minutes"):
                r = dict(r, params=dict(params, amount=minutes, unit="minutes"))
                changed = True
        out.append(r)
    if changed and notes is not None:
        notes.append(f"the wait runs {interpret.until_words(wait)!r}: {minutes} minutes "
                     f"by the clock")
    return out


# The ops an act PLACES without the plan being required to carry them: owned for `order`
# only, never `declared` (which would make the schema demand an `eat` of every line that
# drinks). Owner report 2026-11-01 (Ansel): "have a bite to eat and then sleep" was read
# `consume, rest`; the consume row owed no op (`interpret.ops_for` has none for it — a meal
# is the survival door's, `judgement.inject_survival`), so the plan's `eat`, written last,
# had no owner and the night ran first: "rests for 8 hours ... hunger holds it until Ansel
# eats", and only then "Ansel has no bread to eat".
# And a climb's check where the climb is in the words, before the walk that follows it
# (playtest 2026-11-16 E4: "climb out and walk to X" rolled the climb after the travel).
_PLACED_BY_ACT = {"consume": ("eat", "drink", "taste", "use_item"), "athletics": ("check",)}


def _said_in(say: dict, frame: dict | None) -> int | None:
    """The index of the reading's action whose words a `say` no action owns came from:
    the one whose span shares the most content words with it, or None. Playtest
    2026-11-17b #30: "I go to the barracks and challenge one of the soldiers to a friendly
    sparring bout" was read `go` + `attack` (no `talk`, so no row owned the plan's say),
    the say kept its place ahead of the walk, and the challenge went to the alchemist she
    was leaving. Word overlap with the player's own spans, as `own_words_only` measures a
    say's words; no meaning read."""
    from .judgement import _content_words

    if not isinstance(frame, dict) or frame.get("error"):
        return None
    words = _content_words(str((say.get("params") or {}).get("words") or ""))
    best, at = 0, None
    for k, a in enumerate(frame.get("actions") or []):
        n = len(words & _content_words(str((a or {}).get("span") or "")))
        if n > best:
            best, at = n, k
    return at


# The acts whose deed is the speaking: within one, the words come before what the table
# built from them (the job taken, the hire made).
_SPOKEN_ACTS = frozenset({"talk", "request", "insult", "threaten"})


def order(raw, rows: list[Row], frame: dict | None = None) -> list:
    """The plan's ops in the order the words do them.

    Each op owed by exactly one action of the reading (a built op by its row, a named op
    by the row that names it) is put back in that action's order; every other op keeps
    its place. Inform's DM4 §34 and adv3Lite parse and run one action at a time, because
    what the second means depends on where the first left the player: "I pick up the
    crate, then go to the market" carries the crate there, and the other way round leaves
    it behind. A player's say no action owns goes where its words were said (`_said_in`,
    given the reading's `frame`)."""
    if not isinstance(raw, list) or not rows:
        return raw
    by_built = {id(i): r.index for r in rows for i in r.intents}
    acts = {r.index: r.act for r in rows}
    owners: dict[str, list[int]] = {}
    for r in rows:
        for op in (*r.ops, *(op for op in _PLACED_BY_ACT.get(r.act, ())
                             if op not in r.ops)):
            owners.setdefault(op, []).append(r.index)
    slots, keyed = [], []
    for k, r in enumerate(raw):
        idx = by_built.get(id(r))
        if idx is None and len(owners.get(_op(r), ())) == 1:
            idx = owners[_op(r)][0]
        if idx is None and _op(r) == "say" and not owners.get("say") \
                and str(r.get("actor") or "pc").lower() in ("pc", "none", ""):
            idx = _said_in(r, frame)
        if idx is not None:
            slots.append(k)
            # Within one action, what the table built goes first: the crate a walk carries
            # is picked up before the walk (`_carry`), not at the far end of it. Except
            # where the act IS the speaking: the words first, then the job they take.
            # Playtest 2026-11-17b #15: "Fine. I'll take the guard work." was told after
            # the whole week it agreed to, and after the pay for it.
            first = (_op(r) == "say") if acts.get(idx) in _SPOKEN_ACTS \
                else id(r) in by_built
            keyed.append((idx, 0 if first else 1, k, r))
    if len(keyed) < 2:
        return raw
    keyed.sort(key=lambda t: t[:3])
    out = list(raw)
    for at, (*_, r) in zip(slots, keyed):
        out[at] = r
    return out
