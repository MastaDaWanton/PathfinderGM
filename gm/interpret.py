"""What the player means, read once, before the turn is planned: the interpreter.

Asked for 2026-09-27 ("the whole app hinges on consistently good narration and
accuracy"): about twenty regex readers in gm/judgement.py each read the player's English
for one kind of declaration, and nearly every live defect of that day was one of them
misreading it — "go to the market AND look for the bread seller" read as looking for
"market", "the woman WHO SOLD me bread" as "woman", "I ask HER NAME" as a person to
introduce, "until TEN AT NIGHT" as 140 minutes. This module is the experiment in reading
the sentence once, into a frame, and letting code check the frame.

The shape comes from a research pass (sources in docs/the-interpreter.md):
  * VERBATIM SPANS, never paraphrase or normalised values: every slot must be a piece of
    the player's own sentence, checked in code, and a slot that is not is dropped.
    Google's LangExtract aligns each extraction to the input and flags the ones it
    cannot (it keeps them; dropping is ours — checked by a critic pass). Small models
    invent normalised values (Uniphore, COLING 2025) and substitute objects: "examine
    phone" came back "examine note" from an LLM front end tested on intfiction.org.
    Times stay words ("until ten at night"); code turns them into minutes.
  * A CLOSED LIST OF ACTS, as an enum the sampler cannot leave, with `other` for the
    rest (Rasa's command generators; Ollama's structured outputs).
  * SPANS BEFORE THE ACT in each action, so the words are chosen before the label
    ("Let Me Speak Freely": the order of fields changes what a constrained model does).
  * ATTEMPTS APART FROM CLAIMS: "I kick in the door and the guards cower" attempts one
    thing and claims another; the claim is the engine's to refuse.
  * DEMONSTRATIONS OVER INSTRUCTIONS: this project's own lesson (CLAUDE.md — instruction
    volume loses to demonstration volume). The demonstrations below are not in the
    labelled set (tests/interpreter/gold.py), which would measure recall of the prompt.
"""
from __future__ import annotations

import json
import re
import time

# On in the app. Off in the test suite (tests/conftest.py), as the written opening and
# the schemes are: most turn tests script the model's replies in order, and a reading
# would spend one of them. The interpreter's own tests turn it back on.
ENABLED = True

ACTS = (
    "go", "journey", "leave", "look", "search", "track", "seek", "talk", "insult", "buy",
    "sell", "give", "take", "drop", "steal", "attack", "cast", "use", "consume", "wait",
    "rest", "rise", "call_on", "break_in", "stealth", "athletics", "exert", "gather",
    "follow", "request", "claim", "craft", "commission", "escape", "loot", "harvest", "other",
)
# `commission` since 2026-11-01. Owner report that day (Corvin, turns 21-29): "can you put
# them together and i will give you 10 gold peices" to the smith, about a forged blank for a
# trident — read as a question with no action, then a `give` of "the money" with no
# amount. The vocabulary had no word for paying somebody to do work on your things: `craft`
# is the player's own hands, `buy` is goods off the shelf, `request` is a favour or pay
# asked FOR the player. `commission` owes the engine's `commission` op, built whole
# (`acts_to_ops._commission`): the keeper's trade and the work are the engine's.
# `escape` since 2026-11-01, from the owner's report (Corvin T., held by a giant rot grub):
# "excape grap[ple", "escape grapple" and "roll escape artist to escape grappled condition"
# came back `other`, `other` and a question — `other` owes no op, so nothing broke the
# hold; the planner reached for a grapple at the grub (refused five times as "already
# grappled") and a plain Escape Artist check at DC 10 that removed nothing. Breaking a
# grapple is its own deed in the book (CRB p.200: a combat manoeuvre or Escape Artist
# check against the holder's CMD), and the fix is the enum, not a word list. `escape` owes
# the engine's `escape` op, built whole (`acts_to_ops._escape`); HOW is a closed choice
# (`ESCAPE_WAYS`): force (the combat manoeuvre), slip (Escape Artist), or either.
ESCAPE_WAYS = ("either", "force", "slip")
# `blow` since 2026-11-04, on `attack`: whether the words are a killing stroke given to
# somebody who cannot defend themselves — "I finish him off", "I slit his throat", "put it
# out of its misery" — or an ordinary blow. The owner's ruling that day: finishing words
# aimed at a helpless foe in a fight make 1e's coup de grâce (CRB p.197, a full-round
# action that provokes, hits and crits by right, Fortitude or die). Until then the act
# table made every blow at a body on the floor inside a fight an ordinary swing at helpless
# AC, whatever the words, because nothing told the two apart but a regex in the free
# narrator's door (`judgement.is_finishing_blow`). The reader reads the words; whether the
# one struck IS helpless is the engine's state, never the reader's (`acts_to_ops.victims`).
BLOWS = ("ordinary", "finishing")
# `loot` and `harvest` since 2026-11-01, both from the owner's 0.2.25 report (Corvin's game):
#
# * "loot the body" was read `take, object: the body`, a take of a THING, and the give
#   minted `"body": 1` into the pack beside the loot a regex detector added; "punch until
#   she is dead thernm loot her" was read `take, target: her` with no object, which the
#   act table answers "nothing named to take" — and the detector stood down because she
#   was not yet down when the plan was read, so the loot half was dropped. Searching a
#   body is its own deed (the engine's `loot` op: the down or dead body's whole kit), and
#   its target is whose body: `loot` owes that op, built whole (`acts_to_ops._loot`).
# * "kill it and skin iot for parts" was read `craft, craft: leatherworker`, and the make
#   op refused it for want of a tannery. Taking parts off a carcass is not a craft at a
#   bench: it is the harvest (rules/harvest.py — Ultimate Wilderness's "Harvesting
#   Trophies", Survival for what is outside the body, Heal for what is inside, DC 15 +
#   CR), until now reachable only from the harvest sheet's button. `harvest` owes the
#   engine's `harvest` op, which runs the sheet's own rules (`acts_to_ops._harvest`).
# The fix is the enum, not a word list: nothing in code reads "loot" or "skin".
# `craft` since 2026-10-28. The report: "My wife tries to level up blacksmithing through
# narration and didn't get real items or experience." Probed on gemma-4-12B before the
# change: of eleven craft lines ("I forge a dagger at the anvil", "I brew a basic healing
# draught", "I tan this hide into leather" …) ten came back `other` and one `cast`; `other`
# owes no op, so nothing was rolled, spent or made, and the narrator wrote the work done.
# The owner's ruling the same day: a typed craft line makes the craft's base item for real
# (rules/typed_craft.py). `craft` owes the engine's `make` op, built whole
# (`acts_to_ops._craft`). Which craft is a closed choice (`CRAFTS`), never read out of the
# words in code; whether the words ask for the plain item or finer work is another
# (`WORKS`): a special material, masterwork, a finish or an enchantment is the bench's.
CRAFTS = ("blacksmith", "leatherworker", "alchemist", "herbalist", "enchanter")
WORKS = ("plain", "finer")
# The two closed answers a `stealth` action carries since 2026-10-30, both read off the
# player's words by the reader and never by a word list in code:
#   `pace`: careful (up to half speed, no penalty) or hurried (faster, up to full speed,
#     -5) — "You can move up to half your normal speed and use Stealth at no penalty. When
#     moving at a speed greater than half but less than your normal speed, you take a -5
#     penalty" (Stealth, CRB p.106). Before, every hiding was capped at half speed.
#   `diversion`: none, or bluff when the same words first draw the watchers' eyes away by
#     a trick, a shout or a lie — "You can use Bluff to allow you to use Stealth. A
#     successful Bluff check can give you the momentary diversion you need to attempt a
#     Stealth check while people are aware of you" (Stealth, CRB p.106). Built whole into
#     the Bluff and the Stealth check (`acts_to_ops._sneak`).
PACES = ("careful", "hurried")
DIVERSIONS = ("none", "bluff")
# `until` since 2026-11-01, on `wait` and `rest`: the time of day the words wait or sleep
# until, as a closed choice the sampler holds. The owner's report that day (Corvin): "wait
# till tomarrow" was read `wait, time: till tomarrow`, nothing in code could turn the words
# into a clock time (`timewords.minutes_until` has no "tomorrow", and a misspelling defeats
# any table), the plan wrote `advance_time 1 day`, and the party woke at ten at night of
# the next day. Not one more regex: the reader already reads the words, misspellings and
# all, so it names the time of day; code turns the name into minutes against the clock
# (`until_minutes`). "Tomorrow" and "the next day" are the next morning (the owner's
# ruling, the same day). `an hour named` hands the time slot's own words to the
# numbers table ("until ten at night"); `a while` is a length, which stays the plan's;
# `none` says no time at all.
UNTILS = ("none", "a while", "dawn", "morning", "noon", "dusk", "midnight", "an hour named")
DAY_PARTS = frozenset({"dawn", "morning", "noon", "dusk", "midnight"})
# `exert` since 2026-10-16. The owner: "my wife was playing and a man needed help with his
# cart. When she helped him the game narrated that i lifted his cart but never gave a
# strength check." Probed the same day (gemma-4-12B heretic): "I help the man lift his
# cart", "I help him push the cart out of the mud", "I lift the cart so he can fix the
# wheel" and two more all came back `other`, which owes no op — nothing rolled, and the
# deeds backstop then wrote the player's own line onto the page as done. A feat of
# strength is 1e's Strength check (CRB p.16), and helping somebody with theirs is Aid
# Another (CRB p.86); `exert` owes that check, built whole (`acts_to_ops._exert`). Its
# `target` is whoever the player helps; a door forced is still `break_in`.
# `request` since 2026-10-16, from a real player's game (0.2.19): "…then I ask for fair
# compensation for helping the carter" was read `talk`, which owes a `say`, so nothing was
# rolled — and the free narrator answered the request itself, with a coin the engine never
# gave. Asking somebody to GIVE something or DO something for you is Diplomacy's Make
# Request (CRB p.93), a deed with its own roll, as looking for tracks is a Survival check
# and not a search (`track`, above): the fix is the enum, not a word list. What is asked
# for is a closed choice of its own (`REQUESTS`), never read out of the words in code.
# Probed on gemma-4-12B before the change: 0 of 8 lines asking for pay, a reward, a favour
# or help came back as anything but `talk`.
#
# Why an act and not a slot on `talk`: a slot on `talk` would change the shape of every
# conversational line the reader writes (the 2026-09-27 slot measurement: a slot offered
# is a slot filled), and the act→op table keys its rows on the act. The `offer` act
# withdrawn on 2026-10-03 (below) split one deed by how far it was done; this splits two
# deeds — a question and a request — that the book rolls differently.

# What a `request` asks for: payment (pay, a reward, wages, compensation, money) or a
# favour (help, aid, a service). `rules/requests.KINDS` is the engine's copy of this list.
REQUESTS = ("payment", "favour")
# `rise` and `track` since 2026-10-09, both from one live run (gemma-4-12B, Pangrella):
#
# * "I break camp and head back to town" was read `rest, go` — the vocabulary had a word
#   for making camp (`rest`) and none for breaking it, and the sampler, held to the enum,
#   took the nearest — and the engine slept the party nine more hours. Probed again before
#   the change: "I break camp at first light and walk to the ford" came back `rest, time:
#   at first light`, a sleep. `rise` is the end of a rest; it owes no op. The fix is the
#   enum, not a word list: nothing in code reads "break".
# * "I look for tracks in the grass" was read `search` (the gloss listed tracks under it),
#   which owes no op, so no Survival check was ever rolled and the narrator invented a
#   cart's ruts. Looking for tracks is 1e's Survival to find tracks (CRB p.107, Follow
#   Tracks), a deed of its own: `track` owes the engine's `track` op, built whole
#   (`acts_to_ops.table`).
# `drop` since 2026-10-03, because the act→op table (gm/acts_to_ops.py) needs it and the
# vocabulary did not have it: "I also drop the Brunt of the weight on the ground" was read
# `give, target: the Brunt of the weight, place: the ground` on the owner's items save, and
# a give is a hand-over to somebody — the smith gained a copy.
#
# Tried and withdrawn the same day: an `offer` act, for a sale not yet closed. It moved the
# problem rather than solving it — the live reader read "I try to sell the crate to Korvu"
# as `offer` and "I try to sell the crate to the smith" as `sell`, and on the held-out lines
# a `talk` came back `offer`. What separates them is not WHAT is done but how far it is
# done, which every act has: COMMITMENT, below.
SLOTS = ("target", "object", "place", "time", "says")

# How far each action is done (2026-10-03, lane F round 2). The coordinator, after the
# replay: "I take the crate to the man in the counting house who will buy it" was read as a
# sale and the crate was sold a turn early; "I try to sell the crate to the smith" was read
# `sell` and sold. The engine acted on something the player had not committed to.
#
# The research's answer is old. Event annotation marks every event mention with its REALIS:
# Rich ERE's "Actual (asserted), Generic (generic, habitual), and Other (future,
# hypothetical, negated, uncertain, etc.)" (Song et al. 2015, "From Light to Rich ERE",
# ACL W15-0812; the TAC KBP event-nugget task scored the same three). FactBank grades the
# same axis finer (certain / probable / possible, Saurí & Pustejovsky 2009). And dialogue
# acts keep an offer apart from its acceptance: ISO 24617-2's Offer is answered by an
# Accept Offer, "which has a functional dependence relation to the preceding Offer" (Bunt,
# annotation guidelines) — a sale tried is an offer, and only an agreement closes it.
# Ours is Rich ERE's split with the attempt kept apart, because 1e rolls for an attempt:
#   done      performed now, as stated ("I sell the crate to him", "it's a deal")
#   tried     attempted now, the outcome open ("I try to pick the lock", "I try to sell…")
#   intended  a plan, purpose or wish, not done this turn ("to sell it", "who will buy it",
#             "I'm going to…", "I want to…")
#   asked     asked about, not done ("can I sell it here?", "would you buy it?")
# Only `done` and `tried` move the engine (`acts_to_ops`, `ops_for`, `supported`).
COMMITS = ("done", "tried", "intended", "asked")
ACTING = frozenset({"done", "tried"})

# By what MEANS each action is done (2026-10-05, gm/means.py). The owner: "whatever you do
# must catch anything that is not within the players power to do not just psychic and
# memory stuff". The regex door before this (`judgement.refuse_unnamed_power`) listed the
# ways of reaching into a mind it knew, and the table found the ones it did not: "I make
# the smith forget he saw me" became a Diplomacy check, and "I erase the apprentice's
# memory of me" became the plan's guess at `cast charm-person`, which stood the door down.
#
# The answer every tradition gives is the same three-way split, and none of them is a
# list of forbidden verbs:
#   ordinary  what anybody can TRY — body, voice, skill, the things carried. "You write
#             the attempt, they write the result" (play-by-post etiquette on autohitting);
#             1e's skills and combat roll it.
#   power     by a named document — a spell, a class or path ability, a racial trait, a
#             feat, a magic item. Fate calls this a permission: an aspect or extra is what
#             lets a character do what others cannot (Fate System Toolkit, "Extras").
#   beyond    neither: nothing an ordinary person can do, and no power named for it.
#             Apocalypse World's "fictional positioning" — without it the move does not
#             trigger, whatever is said.
# The reader answers which (an enum, enforced by the sampler); code then asks the SHEET
# whether a power named is held (`means.held_power`) — a closed vocabulary, never English.
MEANS = ("ordinary", "power", "beyond")

# What each action COSTS in the turn (2026-11-06, docs/turn-budget-and-fixtures-plan.md).
# The owner's ruling that day: a line may hold several deeds outside a fight, "but once a
# limit of actions has been hit the world doesnt stand still it moves as well". The budget
# he set:
#   free        moving about the place you are in; words said to nobody who would answer
#   quick       a moment's deed — take, give, open, eat, look — and a turn holds two
#   takes_time  a deed that takes a while (cook, craft, search a room, rest): the turn ends
#   addresses   speaking to somebody here who would answer (ask, offer, threaten, insult):
#               the turn ends, so they reply first
# The reader answers which (an enum the sampler holds), as it answers `commit` and
# `means`; never a word list in code (the owner's direction of 2026-10-03). The runner
# that spends it is `sequence.within_budget`, called from play/views.py.
COSTS = ("free", "quick", "takes_time", "addresses")
# The cost when the reading names none — a reading from before 2026-11-06, a remembered
# frame, a hosted provider that does not hold the enum — and the cost every demonstration
# teaches unless it says otherwise. Keyed on the closed act, never on words. A `go` is
# free whether it crosses the room or the town (the reader's `go` is "somewhere within
# reach"); a `journey` is days on the road. A blow is `addresses`: the one struck answers,
# in a fight of their own (fights keep their own action economy, and the budget is not
# spent inside one). `call_on` is the visit, answered at the door.
ACT_COSTS: dict[str, str] = {
    "go": "free", "leave": "free", "seek": "free", "follow": "free", "stealth": "free",
    "claim": "free",
    "look": "quick", "take": "quick", "give": "quick", "drop": "quick", "consume": "quick",
    "use": "quick", "steal": "quick", "cast": "quick", "break_in": "quick",
    "athletics": "quick", "exert": "quick", "escape": "quick", "rise": "quick",
    "other": "quick",
    "journey": "takes_time", "search": "takes_time", "track": "takes_time",
    "gather": "takes_time", "craft": "takes_time", "harvest": "takes_time",
    "loot": "takes_time", "wait": "takes_time", "rest": "takes_time",
    "talk": "addresses", "insult": "addresses", "request": "addresses", "buy": "addresses",
    "sell": "addresses", "commission": "addresses", "call_on": "addresses",
    "attack": "addresses",
}
# The engine's own facts about time, which overrule the reader in code: these acts' ops
# happen at once (a hand-over, a bite, a draw), so a reading of `takes_time` on one is
# quick; and these always run on the clock (a work on the bench, a night's sleep, the
# road), so a reading of free or quick on one takes time.
INSTANT_ACTS = frozenset({"take", "give", "drop", "consume", "use", "steal"})
TIMED_ACTS = frozenset({"craft", "rest", "journey"})
# Words said to nobody who could answer are free, not a deed ("I mutter a curse").
_SPOKEN_ACTS = frozenset({"talk", "insult"})


def cost_of(action: dict, scene=None) -> str:
    """What this action of a reading spends of the turn's budget (`COSTS`).

    The reader's own answer when it gave one in the enum, else the act's (`ACT_COSTS`);
    then the engine's facts: an act whose op is instant is never `takes_time`, one that
    always runs on the clock is never less; and `addresses` needs somebody here who could
    answer (`_answers`) — said to nobody, words are free and any other deed is quick. A
    plan, a purpose or a question (`COMMITS`) does nothing this turn, so it costs nothing.
    `call_on` is answered at the door of a house elsewhere, so nobody here need answer."""
    if not isinstance(action, dict) or not acting(action):
        return "free"
    act = str(action.get("act") or "other")
    said = str(action.get("cost") or "")
    cost = said if said in COSTS else ACT_COSTS.get(act, "quick")
    if cost == "takes_time" and act in INSTANT_ACTS:
        cost = "quick"
    elif cost in ("free", "quick") and act in TIMED_ACTS:
        cost = "takes_time"
    if cost == "addresses" and scene is not None and act != "call_on" \
            and not _answers(action, scene):
        cost = "free" if act in _SPOKEN_ACTS else "quick"
    return cost


def said_to_nobody(frame: dict | None, scene=None) -> bool:
    """Whether the reading's words are all said to nobody who would answer: it read speech
    done now, no `insult` among it, and every spoken action costs `free` (`cost_of`, the
    reader's closed answer checked against who is here). False with no reading — the turn
    is then as it always was.

    Measured in the live check of 2026-11-07: "I mutter "fool" and walk out" was read
    `talk, says: fool, cost: free` with no target, and `judgement.inject_provoke` — which
    reads an insulting word in the quotation — still provoked the potboy, the only person
    standing there, and his regard fell for a word muttered to nobody. The reader already
    said whom the words were for; a provocation needs somebody they were said to."""
    if not isinstance(frame, dict) or frame.get("error"):
        return False
    spoken = [a for a in frame.get("actions") or ()
              if isinstance(a, dict) and acting(a) and a.get("act") in _SPOKEN_ACTS]
    if not spoken or any(a.get("act") == "insult" for a in spoken):
        return False
    return all(cost_of(a, scene) == "free" for a in spoken)


# A move inside the place the party stands in, not a walk anywhere else: the reader's
# closed `within_place` on a `go` (the per-act schema holds it), and, when the reading has
# none or says false, the place phrase's own head noun from a CLOSED list of the parts and
# fixtures of a room (`judgement._FIXTURES`, the within-scene rule's list, and the few it
# lacks). Measured in the live check of 2026-11-07: "I run to the other side of the room and
# begin cooking dinner…" was read `go: the other side of the room`, which no place is
# called, and the walk-to-nowhere answer (`acts_to_ops._nowhere`) refused it as "You don't
# know of anywhere called "the other side of the room" here" — then the beat said "You move
# toward the hearth … You remain where you are". The old check read only the LAST word
# ("room"); the part of the room is the word before "of" ("side"). No model is asked to
# decide it and no sentence is parsed: a closed field, then a closed noun list.
def fixture_kinds() -> tuple[str, ...]:
    """The reader's closed fixture answer: "none" first, then content/rules/fixtures.json,
    then `fixtures.FLOOR` — back down to the room's own floor ("I go back down")."""
    from rules import fixtures

    return ("none", *fixtures.names(), fixtures.FLOOR)


_ROOM_EXTRA = frozenset({"fire", "fireside", "stair", "stairs", "staircase", "seat",
                         "nook", "alcove", "rear"})


def within_place(action: dict, places=(), here: str = "") -> bool:
    """Whether a `go` moves inside the place the party is in (see `_ROOM_EXTRA`'s note):
    the reader said so, or the phrase's head — its last word, or the word before its first
    "of" when what follows is no other place the town has — is a part or fixture of a
    room."""
    from rules import places as places_mod

    from . import judgement

    if not isinstance(action, dict) or action.get("act") != "go":
        return False
    if action.get("within_place") is True or action.get("fixture"):
        return True
    words = " ".join(str(action.get("place") or "").lower().replace("’", "'").split())
    words = [w.strip(".,;!?") for w in words.split()]
    if not words:
        return False
    parts = set(judgement._FIXTURES.split("|")) | _ROOM_EXTRA
    if words[-1] in parts:
        return True
    if "of" in words[1:]:
        at = words.index("of", 1)
        rest = " ".join(words[at + 1:])
        other = places_mod.find(places, rest) if places and rest else None
        if words[at - 1] in parts and (other is None or getattr(other, "id", "") == here):
            return True
    return False


def _answers(action: dict, scene) -> bool:
    """Whether somebody here would answer this action: the person its target names, when
    the words name one standing here (`acts_to_ops.person`) — and then only if they are up
    and not helpless — else anybody up and seen here (`acts_to_ops._standing_here`). The
    engine's state, never the words' meaning."""
    from . import acts_to_ops

    words = action.get("target")
    if words:
        ref = acts_to_ops.person(scene, words)
        actor = (getattr(scene, "actors", {}) or {}).get(ref) if ref else None
        if actor is not None:
            return not actor.is_down and not actor.is_helpless
    return bool(acts_to_ops._standing_here(scene))


UNTIL_ACTS = frozenset({"wait", "rest"})


def acting(a: dict) -> bool:
    """Whether this action of a reading is done or attempted now — the ones the engine
    acts on. A reading from before commitment existed has none, and is `done`."""
    return str(a.get("commit") or "done") in ACTING

# The slots each act can have: TADS 3's verb templates, where a verb names the slots it
# takes and nothing else (tads.org, "t3verb"). Measured 2026-09-27: with every slot
# required, the model filled all five on most lines and copied one phrase into several
# ("the ore he uses" as object AND place), slot precision 0.33. A slot the act cannot
# have is not the act's, and is dropped in code — never asked of the model twice.
ACT_SLOTS: dict[str, tuple[str, ...]] = {
    # A walk's `object` is what is carried along (round 2): "I take the crate to the man in
    # the counting house" was read `go`, and a crate the player was not yet holding never
    # came with them — the replay of the owner's items save then had nothing to sell.
    "go": ("place", "object", "time"), "journey": ("place",), "leave": ("place",),
    "look": ("object", "target", "place", "time"), "search": ("object", "place"),
    # Whose tracks (a person or a creature named) and where the ground is looked over.
    "track": ("target", "object", "place"), "rise": (),
    "seek": ("target", "place", "object"), "talk": ("target", "says"),
    "insult": ("target", "says"),
    # Who is asked, and the words for what is asked of them; `asks_for` (`REQUESTS`) is
    # the closed choice the engine reads, written after them (`per_act_schema`).
    "request": ("target", "object"),
    "buy": ("object", "target", "place"), "sell": ("object", "target"),
    "drop": ("object", "place"),
    # A take's `target` is who or what it comes OUT of — a person, or a container: "the
    # coins from the pouch" is `object: the coins, target: the pouch` (TADS 3's TakeFrom,
    # whose indirect object is the holder, person or thing).
    "give": ("target", "object", "place"), "take": ("object", "target"),
    "steal": ("object", "target"), "attack": ("target", "object", "place", "time"),
    # `place` as well since I3 (2026-09-29): where a spell goes is as often a place-shaped
    # phrase ("into the tree tops", "into the empty air above my head") as a person, and a
    # slot the act cannot have is dropped in code — so the phrase was lost before the aim
    # reader could see it. Bobby's reading of "I cast burning hands into the tree tops"
    # came back `object: burning hands, target: the tree tops`; another reading of the
    # same line may put the treetops in `place`, and both now reach `cast_aim`.
    "cast": ("object", "target", "place"), "use": ("object", "target"), "consume": ("object",),
    "wait": ("place", "time", "target"), "rest": ("place", "time"),
    "call_on": ("target", "place"), "break_in": ("target", "object", "place"),
    "stealth": ("target", "place"), "athletics": ("place",),
    # What is heaved, and who is helped with it ("join the ferryman in hauling his boat").
    "exert": ("object", "target", "place"), "gather": ("object", "time"),
    "follow": ("target", "object", "time"), "claim": (),
    # What is made or worked (the thing named: "a dagger", "this hide"), and where. Which
    # craft and how fine are the closed `craft` and `work`, written after (`per_act_schema`).
    "craft": ("object", "place"),
    # Who is paid to do the work, and the thing it is done to or makes.
    "commission": ("target", "object"),
    # Whose hold is broken ("the grub's grip"); HOW is the closed `way` (`ESCAPE_WAYS`).
    "escape": ("target",),
    # Whose body is searched; what creature is cut up, and which part when one is named.
    "loot": ("target",), "harvest": ("target", "object"),
    "other": ("target", "object", "place"),
}

_WHAT_EACH_IS = """\
go        walk somewhere within reach (a place in town, the crossroads, the fields, into
          the trees, back to the gate); walking OUT INTO somewhere named is go, not leave.
          `within_place` is true for a move inside the place you are in (across the
          room, to the hearth, a corner, the bar, the window), false for anywhere else;
          `fixture` is which fixture the walk is to (counter for a bar, bookshelf, stair,
          barrel…; gallery for a wall-walk, landing, loft or balcony above the floor;
          floor for back down to the ground), or none
journey   take the road or a ship to another town
leave     walk out of where you are — a building, or the settlement itself — with
          nowhere else named
look      look, watch, listen, read, examine
search    look for a THING or a PLACE (water, a way in, somewhere to sleep)
track     look for tracks, a trail or footprints; read the ground for who passed
seek      look for, ask around for, wave down, head for or turn to a PERSON
talk      speak to, ask, tell, greet, thank, persuade, order, haggle with somebody;
          asking a question, for directions or for advice is talk
request   ask somebody to pay you for your work, reward you, or do you a favour or help
          for nothing in return; `asks_for` is payment (money owed or given to you) or
          favour (anything else). Buying, ordering, taking a room and paying or bribing
          somebody are never a request
insult    mock, taunt, call names, spit at, pick a fight with words — and telling
          anybody something meant to shame somebody ("I tell the room he is a coward")
buy       buy, order, shop for, pay for goods, take goods and pay the seller for them;
          the object is the goods
sell      sell, offer for sale, agree a sale, accept a price, close a deal
give      hand over, pay a debt or a fee, buy somebody a drink
take      pick up, take, tip or count out of a container; the target is the
          person or the container it comes out of
drop      put down, set down, drop or leave a thing behind
steal     pick a pocket, steal, filch
loot      loot, strip, search or go through the body or belongings of somebody or some
          creature that is down or dead; the target is whose body
harvest   skin, butcher, gut, or cut a hide, horns, teeth, venom or other parts off a dead
          creature; the target is the creature, the object the part
attack    hit, punch, stab, shoot, assault, pick a fight with, run amok, finish somebody.
          `blow` is finishing when the words kill somebody who is down, dying, bound or
          helpless — finish off, slit a throat, put out of its misery, the killing stroke
          — else ordinary
cast      cast a named spell
use       draw a weapon, put on, show, use, bandage, light
consume   eat or drink
wait      wait, sit, stand, stay, keep watch, pass time
rest      sleep, lie down, make camp, rest, take a room
          (wait and rest: `until` is the time of day it lasts until — tomorrow or the next
          day is morning; first light or sunrise is dawn; dark or nightfall is dusk; a
          clock hour said ("ten at night") is an hour named; a length ("for an hour",
          "two days") is a while; none when no time is said)
rise      get up, wake, break camp, pack up: the end of a rest
call_on   go to somebody's house, knock at their door, visit them at home
break_in  kick in, force or pick the lock of a door
stealth   sneak, hide, slip past. `pace` is careful, or hurried when the words hurry
          (dash, rush, quickly, at a run-walk); `diversion` is bluff when the same words
          first distract the onlookers by a trick, a shout or a lie, else none
athletics climb, swim, jump
exert     lift, push, pull, heave, drag, hold up or shift something heavy by main
          strength, alone or with somebody; the target is whoever you help with it
gather   forage, gather, fill waterskins
follow    follow somebody or a trail; go along with, come quietly with or give yourself
          up to whoever is taking you somewhere (going quietly is never stealth)
claim     assert who or what you are
craft     make or work something yourself at a trade: forge, smith, hammer out or
          assemble metal work; tan, cure or stitch leather; brew, mix or bottle alchemy;
          grind, steep or brew herbs into a remedy; enchant. The object is the thing
          made or worked. `craft` is which trade: blacksmith, leatherworker, alchemist,
          herbalist or enchanter. `work` is plain for the ordinary thing, or finer when
          the words ask for more: a special metal or hide, masterwork, a finish, an
          enchantment. Paying somebody else to make it is commission, never craft
commission pay or offer to pay somebody to make, fit, finish, mend or put together
          something for you, from your own things; the target is who does the work, the
          object the thing worked on or made
escape    break free of a grapple, a hold, a grip or a pin; wriggle, twist or force your
          way out of somebody's hands. `way` is force (overpower the hold), slip (wriggle
          out, Escape Artist), or either when the words say neither
other     anything else

Each action also says by what MEANS it is done:
ordinary  anything a person could try with their body, voice, skill and what they carry
power     a spell, ability, trait, feat or magic item the sentence names; copy its name
          into `power`
beyond    something no ordinary person can do, with no power named for it

And what it COSTS of the player's turn:
free        moving about where you are; words said to nobody who would answer
quick       a moment's deed: take, give, open, eat, drink, look, draw, drop
takes_time  a deed that takes a while: cook, craft, search a room, rest, any long task
addresses   asking, offering, buying from, threatening, insulting or striking somebody
            here who will answer"""

_DEMOS = [
    ("I head down to the docks and ask a fisherman what he caught today.",
     {"question": False, "claims": [], "actions": [
         {"span": "head down to the docks", "place": "the docks", "act": "go"},
         {"span": "ask a fisherman what he caught today", "target": "a fisherman",
          "says": "what he caught today", "act": "talk"}]}),
    ("I look for the tailor who mended my cloak last week.",
     {"question": False, "claims": [], "actions": [
         {"span": "look for the tailor who mended my cloak last week",
          "target": "the tailor who mended my cloak last week", "act": "seek"}]}),
    ("I buy three candles from her and ask where the temple is.",
     {"question": False, "claims": [], "actions": [
         {"span": "buy three candles from her", "object": "three candles", "target": "her",
          "act": "buy"},
         {"span": "ask where the temple is", "says": "where the temple is", "act": "talk"}]}),
    # Paying for goods taken off a stall is buying them, not a gift of coin: on 2026-10-15
    # "I pick up a waterskin and pay for it" and "I ask the smith for a dagger and pay
    # him" read as take/give, so the counter never opened (3 of 10 purchases missed).
    ("I take a lantern off the shelf and pay the keeper for it.",
     {"question": False, "claims": [], "actions": [
         {"span": "take a lantern off the shelf and pay the keeper for it",
          "object": "a lantern", "target": "the keeper", "act": "buy"}]}),
    ("I sit on the steps until noon.",
     {"question": False, "claims": [], "actions": [
         {"span": "sit on the steps until noon", "place": "the steps", "time": "until noon",
          "until": "noon", "act": "wait"}]}),
    ("I ask him his name.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask him his name", "target": "him", "says": "his name", "act": "talk"}]}),
    # A request (2026-10-16): asked to give or do something, beside a question, which
    # stays talk. None of these is a probe line (the probe's 14 are kept apart).
    ("I ask the netmaker which inn is cheapest and ask to be paid for mending her nets.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask the netmaker which inn is cheapest", "target": "the netmaker",
          "says": "which inn is cheapest", "act": "talk"},
         {"span": "ask to be paid for mending her nets",
          "object": "to be paid for mending her nets", "asks_for": "payment",
          "act": "request"}]}),
    ("I ask the boatwright for my wages.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask the boatwright for my wages", "target": "the boatwright",
          "object": "my wages", "asks_for": "payment", "act": "request"}]}),
    ("I ask the gatekeeper to hold the gate open for me.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask the gatekeeper to hold the gate open for me",
          "target": "the gatekeeper", "object": "to hold the gate open for me",
          "asks_for": "favour", "act": "request"}]}),
    # …and what is NOT a request, because the first cut took them: on the labelled set
    # "I order an ale" and "I pay for a room at the inn" came back `request` (they are
    # buy and rest), and "I try to bribe the gatekeeper with a silver coin" too (a give).
    # Coin going OUT is never a request. Neither line is in the labelled set.
    ("I order a mug of cider.",
     {"question": False, "claims": [], "actions": [
         {"span": "order a mug of cider", "object": "a mug of cider", "act": "buy"}]}),
    # One action, no purpose clause: with "…to look the other way" written as a second,
    # `other` action, the bench's single deeds grew a trailing `other` ("I steal a loaf
    # while the baker's back is turned" -> steal, other; 5 lines of 302).
    ("I slip the clerk a silver piece.",
     {"question": False, "claims": [], "actions": [
         {"span": "slip the clerk a silver piece", "target": "the clerk",
          "object": "a silver piece", "act": "give"}]}),
    ("I smash the tavern door and everyone inside flees.",
     {"question": False, "claims": ["everyone inside flees"], "actions": [
         {"span": "smash the tavern door", "object": "the tavern door", "act": "break_in"}]}),
    ("Is it still raining?",
     {"question": True, "claims": [], "actions": []}),
    ("I find somewhere dry to shelter and sleep until first light.",
     {"question": False, "claims": [], "actions": [
         {"span": "find somewhere dry to shelter", "object": "somewhere dry to shelter",
          "act": "search"},
         {"span": "sleep until first light", "time": "until first light", "until": "dawn",
          "act": "rest"}]}),
    ("I go round to the cooper's house.",
     {"question": False, "claims": [], "actions": [
         {"span": "go round to the cooper's house", "target": "the cooper",
          "place": "the cooper's house", "act": "call_on"}]}),
    ("I tell the sergeant, \"We march at dawn.\"",
     {"question": False, "claims": [], "actions": [
         {"span": "tell the sergeant, \"We march at dawn.\"", "target": "the sergeant",
          "says": "We march at dawn.", "act": "talk"}]}),
    # Words said to nobody named: the quotation is `says`, and the target is null — never
    # the quotation (2026-10-03, item 13, where `say "…"` came back as the target and was
    # minted as a person). Kept out of the labelled set, like every demonstration here.
    ("I shrug and say \"Only passing through, friend.\"",
     {"question": False, "claims": [], "actions": [
         {"span": "say \"Only passing through, friend.\"",
          "says": "Only passing through, friend.", "act": "talk"}]}),
    ("I spit on the ground in front of the fat merchant.",
     {"question": False, "claims": [], "actions": [
         {"span": "spit on the ground in front of the fat merchant",
          "target": "the fat merchant", "act": "insult"}]}),
    ("I tell the crowd the reeve is a thief and a liar.",
     {"question": False, "claims": [], "actions": [
         {"span": "tell the crowd the reeve is a thief and a liar", "target": "the crowd",
          "says": "the reeve is a thief and a liar", "act": "insult"}]}),
    # An oath, a denial or a protest is said aloud, so it is talk — its words in `says` —
    # never a claim, whatever they say happened (round 2, 2026-11-05). Measured on the
    # rerun of the 44 lines: "I swear I never touched her", at the trial, came back
    # `claims: ["I never touched her"]` with no deed on 7 of 7 runs and 6 of 6 probes, and
    # the means gate refused the turn as a declaration ("saying so does not make it so").
    # Before 8c6cf4e8 it came back the `claim` act, which owes no op and narrated by luck;
    # "I insist …", "I deny everything" and "I swear on my mother's grave …" still did
    # (0 of 24 probes read as talk). Neither line below is a probe or a labelled line.
    ("I swear by the old gods the ox was dead when I found it.",
     {"question": False, "claims": [], "actions": [
         {"span": "swear by the old gods the ox was dead when I found it",
          "says": "the ox was dead when I found it", "act": "talk"}]}),
    ("I protest to the sergeant that the purse was mine all along.",
     {"question": False, "claims": [], "actions": [
         {"span": "protest to the sergeant that the purse was mine all along",
          "target": "the sergeant", "says": "the purse was mine all along",
          "act": "talk"}]}),
    ("I head for the cooper to ask about barrels.",
     {"question": False, "claims": [], "actions": [
         {"span": "head for the cooper", "target": "the cooper", "act": "seek"},
         {"span": "to ask about barrels", "commit": "intended", "says": "about barrels",
          "act": "talk"}]}),
    ("I climb the bell tower to look over the rooftops.",
     {"question": False, "claims": [], "actions": [
         {"span": "climb the bell tower", "place": "the bell tower", "act": "athletics"},
         {"span": "to look over the rooftops", "commit": "intended",
          "object": "the rooftops", "act": "look"}]}),
    # Feats of strength (`exert`, 2026-10-16), written unlike the probe lines (no cart, no
    # "help him"): one heave alone, one beside somebody, who is the target. Here, beside the
    # other deed of the body, and not last: appended at the end of the list they were the
    # last example before every sentence, and the interpreter bench moved on 11 of 302
    # lines (act F1 0.921 -> 0.916, "I go to her house" losing `call_on`). Here it read
    # act F1 0.920 and frame exact 0.709, against master's own two runs at 0.921/0.918 and
    # 0.702/0.699 — the same prompt run twice moves 5 lines, `call_on` among them.
    ("I set my shoulder to the fallen beam and shove it off the trapdoor.",
     {"question": False, "claims": [], "actions": [
         {"span": "set my shoulder to the fallen beam and shove it off the trapdoor",
          "object": "the fallen beam", "place": "the trapdoor", "act": "exert"}]}),
    ("I join the old fisherwoman in hauling her boat up the shingle.",
     {"question": False, "claims": [], "actions": [
         {"span": "join the old fisherwoman in hauling her boat up the shingle",
          "object": "her boat", "target": "the old fisherwoman", "place": "the shingle",
          "act": "exert"}]}),
    ("I sit on the bench for an hour.",
     {"question": False, "claims": [], "actions": [
         {"span": "sit on the bench for an hour", "place": "the bench", "time": "for an hour",
          "until": "a while", "act": "wait"}]}),
    # Going on, with nowhere named, is a walk all the same (owner report 2026-11-01,
    # Corvin, turn 14: "keep going" came back with no action at all, so the walk a crowd
    # had cut short could not be carried on — `acts_to_ops._carry_on`).
    ("I keep going.",
     {"question": False, "claims": [], "actions": [
         {"span": "keep going", "act": "go"}]}),
    # "Tomorrow" is the next morning (`UNTILS`, the owner's ruling 2026-11-01).
    ("I wait by the fountain till tomorrow.",
     {"question": False, "claims": [], "actions": [
         {"span": "wait by the fountain till tomorrow", "place": "the fountain",
          "time": "till tomorrow", "until": "morning", "act": "wait"}]}),
    ("I buy the old soldier a pint.",
     {"question": False, "claims": [], "actions": [
         {"span": "buy the old soldier a pint", "target": "the old soldier",
          "object": "a pint", "act": "give"}]}),
    # What each deed costs of the turn (`COSTS`, the owner's ruling 2026-11-06). Every
    # demonstration teaches its act's cost (`ACT_COSTS`, written by `_demo_reply`); these
    # are the ones the act alone does not settle: a task that takes a while under `other`,
    # three moments' deeds in a row, words said to nobody, and an order beside a gift (and
    # the killing strokes below are quick: the one struck cannot answer). None is the
    # owner's example, a test line or a labelled line.
    ("I cross to the hearth and set a pot of stew on to simmer for supper.",
     {"question": False, "claims": [], "actions": [
         {"span": "cross to the hearth", "place": "the hearth", "within_place": True,
          "fixture": "hearth", "act": "go"},
         {"span": "set a pot of stew on to simmer for supper", "object": "a pot of stew",
          "cost": "takes_time", "act": "other"}]}),
    # A move inside the place named by a part of the room rather than a thing in it
    # (`within_place`, the live check of 2026-11-07). Not a test line.
    ("I shoulder through the crowd to the far end of the bar.",
     {"question": False, "claims": [], "actions": [
         {"span": "shoulder through the crowd to the far end of the bar",
          "place": "the far end of the bar", "within_place": True, "fixture": "counter",
          "act": "go"}]}),
    # A raised part of the place by its own name, and the walk back down (the gate,
    # 2026-11-11): "onto the wall-walk above the gate" was read as a walk to somewhere
    # else, planned as travel to the gate the player stood in, and moved nobody.
    ("I climb the steps up onto the wall-walk above the gate.",
     {"question": False, "claims": [], "actions": [
         {"span": "climb the steps up onto the wall-walk above the gate",
          "place": "the wall-walk", "within_place": True, "fixture": "gallery",
          "act": "go"}]}),
    ("I head back down to the ground.",
     {"question": False, "claims": [], "actions": [
         {"span": "head back down to the ground", "place": "the ground",
          "within_place": True, "fixture": "floor", "act": "go"}]}),
    ("I pick up the lantern, light it and peer down the stairwell.",
     {"question": False, "claims": [], "actions": [
         {"span": "pick up the lantern", "object": "the lantern", "act": "take"},
         {"span": "light it", "object": "it", "act": "use"},
         {"span": "peer down the stairwell", "object": "the stairwell", "act": "look"}]}),
    ("I turn the whole loft over looking for the missing ledger.",
     {"question": False, "claims": [], "actions": [
         {"span": "turn the whole loft over looking for the missing ledger",
          "object": "the missing ledger", "place": "the whole loft", "act": "search"}]}),
    ("I darn the hole in my stocking by the fire.",
     {"question": False, "claims": [], "actions": [
         {"span": "darn the hole in my stocking by the fire",
          "object": "the hole in my stocking", "place": "the fire", "cost": "takes_time",
          "act": "other"}]}),
    ("I mutter a curse under my breath.",
     {"question": False, "claims": [], "actions": [
         {"span": "mutter a curse under my breath", "says": "a curse", "cost": "free",
          "act": "talk"}]}),
    ("I warn the stable boy off the grey mare and toss him a copper.",
     {"question": False, "claims": [], "actions": [
         {"span": "warn the stable boy off the grey mare", "target": "the stable boy",
          "says": "off the grey mare", "act": "talk"},
         {"span": "toss him a copper", "target": "him", "object": "a copper",
          "act": "give"}]}),
    # --- 2026-10-03: the reader now carries the turn (docs/structured-turn.md) ----------
    # Each from a measured systematic miss on the first 60 labelled lines — never a line
    # of the labelled set itself, and none from the 160 held out. Demonstrations, not
    # instructions: CLAUDE.md's ratio rule, and "head for the cooper" above taught `seek`
    # for every "head for", places included ("I head for the stables" came back `seek,
    # target: the stables`). A place headed for is `go`; a person headed for is `seek`.
    ("I head for the tannery to ask about hides.",
     {"question": False, "claims": [], "actions": [
         {"span": "head for the tannery", "place": "the tannery", "act": "go"},
         {"span": "to ask about hides", "commit": "intended", "says": "about hides",
          "act": "talk"}]}),
    # …and the person beside it, because the place demonstration alone turned "I head for
    # the smith" into `go, place: the smith` on the dev bench. "ask for X" is what is said.
    ("I head for the ferryman and ask for a crossing.",
     {"question": False, "claims": [], "actions": [
         {"span": "head for the ferryman", "target": "the ferryman", "act": "seek"},
         {"span": "ask for a crossing", "says": "for a crossing", "act": "talk"}]}),
    # "ask where/what X" is what is said, all of it, pronoun and all: "I wave down a
    # passing carter and ask where he is headed" came back `talk, target: he` and the
    # question was lost; "ask where the dockhands drink" came back `target: the
    # dockhands`. Nobody is named as spoken to, so the target is null.
    ("I flag down a porter and ask where she is taking the trunk.",
     {"question": False, "claims": [], "actions": [
         {"span": "flag down a porter", "target": "a porter", "act": "seek"},
         {"span": "ask where she is taking the trunk",
          "says": "where she is taking the trunk", "act": "talk"}]}),
    ("I ask where the ropemakers work, and walk there.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask where the ropemakers work", "says": "where the ropemakers work",
          "act": "talk"},
         {"span": "walk there", "place": "there", "act": "go"}]}),
    # A house, and where somebody lives, is a place: "I go to her house" lost `place`.
    ("I ask around where the midwife lives.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask around where the midwife lives", "target": "the midwife",
          "place": "where the midwife lives", "act": "seek"}]}),
    ("I call the bailiff a drunk to his face.",
     {"question": False, "claims": [], "actions": [
         {"span": "call the bailiff a drunk to his face", "target": "the bailiff",
          "says": "a drunk", "act": "insult"}]}),
    # A gesture is no hand-over: "I give a friendly wink" planned a `give` of "friendly
    # wink" on the owner's market save (2026-10-03, item 8).
    ("I give the guard a lazy salute and say \"Long night, friend?\"",
     {"question": False, "claims": [], "actions": [
         {"span": "give the guard a lazy salute", "target": "the guard", "act": "other"},
         {"span": "say \"Long night, friend?\"",
          "says": "Long night, friend?", "act": "talk"}]}),
    # Things moving, the shapes the owner's items save misread. Out of a container, the
    # container is the take's target; set down is `drop`, never a give to the nearest.
    ("I shake the silver out of the sack into my purse and set the empty sack down by "
     "the door.",
     {"question": False, "claims": [], "actions": [
         {"span": "shake the silver out of the sack into my purse", "object": "the silver",
          "target": "the sack", "act": "take"},
         {"span": "set the empty sack down by the door", "object": "the empty sack",
          "place": "by the door", "act": "drop"}]}),
    # Withdrawn, round 2: "I lift the lantern off the hook, then hand it to the boy." Two of
    # the 4.4 points of acts-in-order lost on the held-out lines were a search and an
    # `other` read as `take` (an act-level count, no sentence read), and this was one of
    # two take demonstrations added that day; "it" is the table's to resolve, in code.
    #
    # How far a deed is done (`COMMITS`). A sale tried is an offer the fiction answers; a
    # sale agreed, or closed in the player's own quoted words, is done.
    ("I offer the furrier my wolf pelts and ask what he would pay.",
     {"question": False, "claims": [], "actions": [
         {"span": "offer the furrier my wolf pelts", "commit": "tried",
          "object": "my wolf pelts", "target": "the furrier", "act": "sell"},
         {"span": "ask what he would pay", "says": "what he would pay", "act": "talk"}]}),
    ("I tell the miller, \"Done. The mule is yours.\"",
     {"question": False, "claims": [], "actions": [
         {"span": "tell the miller, \"Done. The mule is yours.\"", "target": "the miller",
          "says": "Done. The mule is yours.", "act": "talk"},
         {"span": "The mule is yours", "object": "The mule", "target": "the miller",
          "act": "sell"}]}),
    # One deed, not two (round 2): a time is when the deed ends, a weapon is what it is
    # done with, and where the player leans or stands is where they do it. Measured on the
    # dev lines written for it (`authored:segment`, after an act-level count of held-out
    # flips): 7 of 14 came back with an extra action — `go, wait`, `use, attack`,
    # `wait, look`, `other, talk`.
    ("I walk along the river until the bell rings.",
     {"question": False, "claims": [], "actions": [
         {"span": "walk along the river until the bell rings", "place": "the river",
          "time": "until the bell rings", "act": "go"}]}),
    ("I level my spear and drive it into the boar.",
     {"question": False, "claims": [], "actions": [
         {"span": "level my spear and drive it into the boar", "target": "the boar",
          "object": "my spear", "act": "attack"}]}),
    ("I lean against the doorframe and watch the street.",
     {"question": False, "claims": [], "actions": [
         {"span": "lean against the doorframe and watch the street",
          "object": "the street", "act": "look"}]}),
    ("I seize the pickpocket by the arm.",
     {"question": False, "claims": [], "actions": [
         {"span": "seize the pickpocket by the arm", "target": "the pickpocket",
          "act": "attack"}]}),
    # Violence nobody is named for (2026-10-09, the owner: "if i say I attack the closest
    # person or i go on a rampage or i assault a civilian etc. it should be able to start a
    # fight"). Measured live the same day on gemma-4-12B: "I go on a rampage." was read
    # `other`, and "I pick a fight with the biggest bruiser in the room." `insult` -- the
    # gloss said "pick a fight with words". Who the blow lands on is not the reader's to
    # say here: the words are kept whole and `confirm_victims` asks it of the people here.
    ("I pick a fight with the tallest of the sailors.",
     {"question": False, "claims": [], "actions": [
         {"span": "pick a fight with the tallest of the sailors",
          "target": "the tallest of the sailors", "act": "attack"}]}),
    ("I run amok through the fish stalls.",
     {"question": False, "claims": [], "actions": [
         {"span": "run amok through the fish stalls", "place": "the fish stalls",
          "act": "attack"}]}),
    # What somebody else will do is not the player's deed at all: no action. Tried first
    # as `sell, commit: intended` for "who will pay me for it", and on the dev lines the
    # reader then read "the net, which he will mend for me" as the player's own sale.
    ("I carry the barrel over to the cooper, who will pay me for it.",
     {"question": False, "claims": [], "actions": [
         {"span": "carry the barrel over to the cooper", "target": "the cooper",
          "object": "the barrel", "act": "seek"}]}),
    ("I take the lamp along to the old woman's hut.",
     {"question": False, "claims": [], "actions": [
         {"span": "take the lamp along to the old woman's hut",
          "place": "the old woman's hut", "object": "the lamp", "act": "go"}]}),
    # A purpose clause or a plan: intended, never done. "going to <a place>" is going;
    # "going to <do something>" is a plan.
    ("I'm going to the baker's to buy bread.",
     {"question": False, "claims": [], "actions": [
         {"span": "going to the baker's", "place": "the baker's", "act": "go"},
         {"span": "to buy bread", "commit": "intended", "object": "bread", "act": "buy"}]}),
    # …and "to <a place>" is where the walk goes, not a plan: "I head out of town to
    # wherever the charcoal burners work" came back `go, commit: intended` on the dev lines
    # — a walk the engine would never have made.
    ("I ride out past the walls to the old mill.",
     {"question": False, "claims": [], "actions": [
         {"span": "ride out past the walls to the old mill", "place": "the old mill",
          "act": "go"}]}),
    ("I go to the forge to sell the horseshoes.",
     {"question": False, "claims": [], "actions": [
         {"span": "go to the forge", "place": "the forge", "act": "go"},
         {"span": "to sell the horseshoes", "commit": "intended",
          "object": "the horseshoes", "act": "sell"}]}),
    # A price is not a second thing sold: "agree to sell the goat to the herder for six
    # silver" came back as two sales on the dev lines, the second of "six silver".
    ("I accept four silver from the tanner for the hides.",
     {"question": False, "claims": [], "actions": [
         {"span": "accept four silver from the tanner for the hides",
          "object": "the hides", "target": "the tanner", "act": "sell"}]}),
    ("I'm going to find the harbourmaster and ask about passage.",
     {"question": False, "claims": [], "actions": [
         {"span": "going to find the harbourmaster", "commit": "intended",
          "target": "the harbourmaster", "act": "seek"},
         {"span": "ask about passage", "commit": "intended", "says": "about passage",
          "act": "talk"}]}),
    # Tried: done now, the outcome the dice's.
    ("I try to pick the lock of the chapel door.",
     {"question": False, "claims": [], "actions": [
         {"span": "try to pick the lock of the chapel door", "commit": "tried",
          "target": "the chapel door", "act": "break_in"}]}),
    # Asked about: the asking is done; the deed asked about is not.
    ("I ask the trader whether she would buy my furs.",
     {"question": False, "claims": [], "actions": [
         {"span": "ask the trader whether she would buy my furs", "target": "the trader",
          "says": "whether she would buy my furs", "act": "talk"},
         {"span": "whether she would buy my furs", "commit": "asked", "object": "my furs",
          "target": "the trader", "act": "sell"}]}),
    # --- 2026-10-05: by what means (`MEANS`, gm/means.py) ------------------------------
    # Every demonstration above is `ordinary`, by default, which is the ratio the table
    # has. These are not in the means corpus (tests/means/gold.py). Paired on purpose: a
    # mind worked on by will against the same mind worked on by words and a coin, and a
    # result the player declared kept apart as a claim, never as a means.
    ("I stare hard at the ferryman until he forgets what I look like.",
     {"question": False, "claims": [], "actions": [
         {"span": "stare hard at the ferryman until he forgets what I look like",
          "target": "the ferryman", "means": "beyond", "act": "other"}]}),
    ("I tell the ferryman he never saw me and press a coin into his palm.",
     {"question": False, "claims": [], "actions": [
         {"span": "tell the ferryman he never saw me", "target": "the ferryman",
          "says": "he never saw me", "act": "talk"},
         {"span": "press a coin into his palm", "target": "his palm", "object": "a coin",
          "act": "give"}]}),
    ("I lie to the reeve and he swallows it whole.",
     {"question": False, "claims": ["he swallows it whole"], "actions": [
         {"span": "lie to the reeve", "target": "the reeve", "act": "talk"}]}),
    ("I peer at the fisherman's hands to see if he is hiding a knife.",
     {"question": False, "claims": [], "actions": [
         {"span": "peer at the fisherman's hands", "object": "the fisherman's hands",
          "act": "look"}]}),
    ("I cast hold portal on the cellar door.",
     {"question": False, "claims": [], "actions": [
         {"span": "cast hold portal on the cellar door", "object": "hold portal",
          "target": "the cellar door", "power": "hold portal", "means": "power",
          "act": "cast"}]}),
    ("I use Stunning Fist on the boatman.",
     {"question": False, "claims": [], "actions": [
         {"span": "use Stunning Fist on the boatman", "object": "Stunning Fist",
          "target": "the boatman", "power": "Stunning Fist", "means": "power",
          "act": "use"}]}),
    ("I call up a gale to blow the fishing boats back to shore.",
     {"question": False, "claims": [], "actions": [
         {"span": "call up a gale to blow the fishing boats back to shore",
          "means": "beyond", "act": "other"}]}),
    ("I vanish from the jetty and step out on the far bank.",
     {"question": False, "claims": [], "actions": [
         {"span": "vanish from the jetty and step out on the far bank",
          "place": "the far bank", "means": "beyond", "act": "other"}]}),
    # Three from the means corpus's first pass (dev lines, docs/means-gate.md): a skill
    # read as beyond twice — remembering, a disguise — and a result clause read as a deed
    # of its own; and a lock opened by a touch read as a lock picked. None is a corpus line.
    ("I try to remember the name of the ship's captain.",
     {"question": False, "claims": [], "actions": [
         {"span": "try to remember the name of the ship's captain", "commit": "tried",
          "object": "the name of the ship's captain", "act": "other"}]}),
    ("I dress up as a priest to get past the doorman.",
     {"question": False, "claims": [], "actions": [
         {"span": "dress up as a priest", "act": "other"},
         {"span": "to get past the doorman", "commit": "intended",
          "target": "the doorman", "act": "stealth"}]}),
    ("I shout at the dog until it slinks off.",
     {"question": False, "claims": [], "actions": [
         {"span": "shout at the dog until it slinks off", "target": "the dog",
          "act": "other"}]}),
    # Remembering is a deed, not a claim: on the regex gate's own corpus "I remember the
    # road to the coast" came back with no action, only a claim, which the means gate
    # refuses as saying-so (gm/means.py).
    ("I remember the way to the old quarry.",
     {"question": False, "claims": [], "actions": [
         {"span": "remember the way to the old quarry",
          "object": "the way to the old quarry", "act": "other"}]}),
    ("I make the shutters fly open by pointing at them.",
     {"question": False, "claims": [], "actions": [
         {"span": "make the shutters fly open by pointing at them",
          "object": "the shutters", "means": "beyond", "act": "other"}]}),
    # Crafts (2026-10-28): the player's own work at a trade is `craft`, with the trade and
    # how fine closed. None of these is a probe line or a labelled line; a trade asked of
    # somebody else stays talk or buy, and walking to a workshop stays go.
    # A common metal named is still the plain item (the first probe read "an iron spear"
    # as finer); a special one, masterwork or a finish is not (the warhammer, below).
    ("I heat the bar and hammer out a steel mace on the anvil.",
     {"question": False, "claims": [], "actions": [
         {"span": "heat the bar and hammer out a steel mace on the anvil",
          "object": "a steel mace", "place": "the anvil", "craft": "blacksmith",
          "work": "plain", "act": "craft"}]}),
    ("I cure the wolf pelt and stitch it into a jerkin.",
     {"question": False, "claims": [], "actions": [
         {"span": "cure the wolf pelt and stitch it into a jerkin", "object": "a jerkin",
          "craft": "leatherworker", "work": "plain", "act": "craft"}]}),
    ("I steep the chamomile into a calming infusion.",
     {"question": False, "claims": [], "actions": [
         {"span": "steep the chamomile into a calming infusion",
          "object": "a calming infusion", "craft": "herbalist", "work": "plain",
          "act": "craft"}]}),
    ("I bottle a flask of acid at my kit.",
     {"question": False, "claims": [], "actions": [
         {"span": "bottle a flask of acid at my kit", "object": "a flask of acid",
          "place": "my kit", "craft": "alchemist", "work": "plain", "act": "craft"}]}),
    ("I forge a masterwork warhammer of adamantine.",
     {"question": False, "claims": [], "actions": [
         {"span": "forge a masterwork warhammer of adamantine",
          "object": "a masterwork warhammer of adamantine", "craft": "blacksmith",
          "work": "finer", "act": "craft"}]}),
    # Searching a body and cutting up a carcass (2026-11-01, `loot` and `harvest`): never
    # a take of the thing "body", and never a craft at a bench. A blow before either is its
    # own deed, and the loot's target is whose body even when the words say "her body".
    # None of these is a probe or a labelled line.
    ("I finish off the jackal and go through its pack.",
     {"question": False, "claims": [], "actions": [
         {"span": "finish off the jackal", "target": "the jackal", "blow": "finishing",
          "cost": "quick", "act": "attack"},
         {"span": "go through its pack", "target": "its pack", "act": "loot"}]}),
    # The killing stroke and an ordinary blow meant to kill (2026-11-04, `blow`): finishing
    # is the stroke at somebody who cannot fight back, never the wish to kill a foe who
    # can. Neither is a probe or a labelled line.
    ("I kneel and slit the bound smuggler's throat.",
     {"question": False, "claims": [], "actions": [
         {"span": "kneel and slit the bound smuggler's throat",
          "target": "the bound smuggler", "blow": "finishing", "cost": "quick",
          "act": "attack"}]}),
    ("I swing my axe to kill the charging boar.",
     {"question": False, "claims": [], "actions": [
         {"span": "swing my axe to kill the charging boar", "target": "the charging boar",
          "object": "my axe", "blow": "ordinary", "act": "attack"}]}),
    ("I strip the drowned sailor's corpse.",
     {"question": False, "claims": [], "actions": [
         {"span": "strip the drowned sailor's corpse",
          "target": "the drowned sailor's corpse", "act": "loot"}]}),
    ("I skin the dead boar and cut out its tusks.",
     {"question": False, "claims": [], "actions": [
         {"span": "skin the dead boar", "target": "the dead boar", "object": "the dead boar",
          "act": "harvest"},
         {"span": "cut out its tusks", "target": "its", "object": "its tusks",
          "act": "harvest"}]}),
    # Hiding (2026-10-30): the pace and the diversion, closed. A careful creep, a hurried
    # dash still hidden, and a trick that pulls the eyes away first. None is a probe or a
    # labelled line.
    ("I creep along the hedge, keeping low.",
     {"question": False, "claims": [], "actions": [
         {"span": "creep along the hedge, keeping low", "place": "the hedge",
          "pace": "careful", "diversion": "none", "act": "stealth"}]}),
    ("I dash for the woodpile, keeping out of sight.",
     {"question": False, "claims": [], "actions": [
         {"span": "dash for the woodpile, keeping out of sight", "place": "the woodpile",
          "pace": "hurried", "diversion": "none", "act": "stealth"}]}),
    ("I yell that the mill is on fire, and while they turn I duck behind the cart.",
     {"question": False, "claims": [], "actions": [
         {"span": "yell that the mill is on fire", "says": "the mill is on fire",
          "act": "talk"},
         {"span": "while they turn I duck behind the cart", "place": "the cart",
          "pace": "careful", "diversion": "bluff", "act": "stealth"}]}),
    # Going quietly is giving yourself up (live 2026-11-01, the integration build's arrest):
    # "I sigh and go quietly with them" was read as stealth, rolled against the stallholder
    # and left the prisoner hidden between his two guards, 200 XP the richer.
    ("I hold out my hands and come quietly with the watchmen.",
     {"question": False, "claims": [], "actions": [
         {"span": "hold out my hands", "act": "other"},
         {"span": "come quietly with the watchmen", "target": "the watchmen",
          "act": "follow"}]}),
    # Paying somebody to do the work (owner report 2026-11-01, Corvin, turn 22).
    ("Can you fit a haft to this axe head for me? I'll pay you two silver.",
     {"question": False, "claims": [], "actions": [
         {"span": "fit a haft to this axe head for me", "object": "this axe head",
          "act": "commission"}]}),
    # Breaking a hold (2026-11-01): the way, closed. None is a probe or a labelled line.
    ("I twist out of the bandit's grip and step back.",
     {"question": False, "claims": [], "actions": [
         {"span": "twist out of the bandit's grip", "target": "the bandit",
          "way": "slip", "act": "escape"},
         {"span": "step back", "act": "go"}]}),
    ("I wrench myself free of the ogre's hold.",
     {"question": False, "claims": [], "actions": [
         {"span": "wrench myself free of the ogre's hold", "target": "the ogre",
          "way": "force", "act": "escape"}]}),
    ("I try to get loose.",
     {"question": False, "claims": [], "actions": [
         {"span": "try to get loose", "commit": "tried", "way": "either",
          "act": "escape"}]}),
    ("I walk over to the tannery and look at the drying hides.",
     {"question": False, "claims": [], "actions": [
         {"span": "walk over to the tannery", "place": "the tannery", "act": "go"},
         {"span": "look at the drying hides", "object": "the drying hides",
          "act": "look"}]}),
]


def schema() -> dict:
    """The reply's shape, enforced by the sampler: spans first, the act last."""
    slot = {"type": ["string", "null"]}
    return {
        "type": "object",
        "properties": {
            "question": {"type": "boolean"},
            "actions": {
                "type": "array", "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {"span": {"type": "string"},
                                   "commit": {"type": "string", "enum": list(COMMITS)},
                                   **{s: slot for s in SLOTS},
                                   "power": slot,
                                   "means": {"type": "string", "enum": list(MEANS)},
                                   "act": {"type": "string", "enum": list(ACTS)},
                                   "cost": {"type": "string", "enum": list(COSTS)}},
                    # Every slot required (null allowed). Measured 2026-09-27 on the
                    # labelled set: with the slots optional, the constrained sampler
                    # wrote `span` and `act` and nothing else on 220 of 220 lines —
                    # slot recall 0.0 — because an optional property is one the grammar
                    # lets it skip. The commitment is required for the same reason, and
                    # the cost: Ollama holds required properties and enums, nothing more.
                    "required": ["span", "commit", *SLOTS, "power", "means", "act", "cost"],
                },
            },
            "claims": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        },
        "required": ["question", "actions", "claims"],
    }


# Which reply shape the reader is held to: "flat" (every slot on every action, the act
# last) or "per_act" (an `anyOf` of one object per act, the act a `const` straight after
# the span, and only that act's slots — TADS 3's verb templates, enforced by the sampler
# instead of dropped in code afterwards). Probed 2026-10-03 on six real lines before any
# reliance: Ollama enforced the per-act shape on 6 of 6, in both field orders. With the act
# LAST, the slot keys the model wrote first chose the act — "I look around and take stock"
# came back `claim, claim`, the one act with no slots — so the act goes straight after the
# span. Chosen on the dev bench (the first 60 labelled lines; docs/structured-turn.md),
# the same demonstrations both ways: engine-relevant frames 0.833 per-act against 0.767
# flat, strict 0.683 against 0.650, median 1.4 s against 2.4 s — fewer keys to write.
SCHEMA = "per_act"


def per_act_schema() -> dict:
    slot = {"type": ["string", "null"]}
    alts = []
    for act in ACTS:
        # The commitment between the span and the act: read off the words before the
        # label, as the slots are ("Let Me Speak Freely": field order changes what a
        # constrained model does), and the same in every alternative, so it chooses no act.
        props = {"span": {"type": "string"},
                 "commit": {"type": "string", "enum": list(COMMITS)},
                 "act": {"const": act},
                 **{s: slot for s in ACT_SLOTS.get(act, ())},
                 # What a request asks for, a closed enum the sampler holds, written after
                 # the words for it (the slots before the label, as everywhere here).
                 **({"asks_for": {"type": "string", "enum": list(REQUESTS)}}
                    if act == "request" else {}),
                 # Which craft and how fine, closed enums after the words, as `asks_for`.
                 **({"craft": {"type": "string", "enum": list(CRAFTS)},
                     "work": {"type": "string", "enum": list(WORKS)}}
                    if act == "craft" else {}),
                 # How fast, and whether a diversion comes first (`PACES`, `DIVERSIONS`).
                 **({"pace": {"type": "string", "enum": list(PACES)},
                     "diversion": {"type": "string", "enum": list(DIVERSIONS)}}
                    if act == "stealth" else {}),
                 # Until what time of day (`UNTILS`), after the time slot's own words.
                 **({"until": {"type": "string", "enum": list(UNTILS)}}
                    if act in UNTIL_ACTS else {}),
                 # How a grapple is broken (`ESCAPE_WAYS`), after the words, as `pace`.
                 **({"way": {"type": "string", "enum": list(ESCAPE_WAYS)}}
                    if act == "escape" else {}),
                 # Whether a blow is the killing stroke (`BLOWS`), after the words.
                 **({"blow": {"type": "string", "enum": list(BLOWS)}}
                    if act == "attack" else {}),
                 # Whether a walk stays inside the place (`within_place`), after the
                 # place's own words, as `until` follows the time's: a closed answer the
                 # walk-to-nowhere refusal reads (`acts_to_ops._nowhere`), never English.
                 **({"within_place": {"type": "boolean"}} if act == "go" else {}),
                 # Which fixture of the room the walk is to (`fixture_kinds`), a closed
                 # enum after `within_place`: the map places one the room lacks
                 # (rules/fixtures.name_one), never a word read out of the sentence.
                 **({"fixture": {"type": "string", "enum": list(fixture_kinds())}}
                    if act == "go" else {}),
                 # The means last, with the deed and its slots already written, and the
                 # same in every alternative, so it chooses no act (gm/means.py). The
                 # power's name before the verdict, so the verdict is written with its
                 # evidence already chosen — the deed reader's order.
                 # What it costs of the turn (`COSTS`), with the deed and its words
                 # already written; the same in every alternative, so it chooses no act,
                 # and required, so the sampler cannot skip it. Before the means, which
                 # stays last (tests/test_means_gate.py).
                 "cost": {"type": "string", "enum": list(COSTS)},
                 "power": slot,
                 "means": {"type": "string", "enum": list(MEANS)}}
        alts.append({"type": "object", "properties": props, "required": list(props),
                     "additionalProperties": False})
    out = schema()
    out["properties"]["actions"]["items"] = {"anyOf": alts}
    return out


def reply_schema() -> dict:
    return per_act_schema() if SCHEMA == "per_act" else schema()


def _demo_reply(frame: dict) -> str:
    """A demonstration in the shape the sampler holds the reply to. A demonstration that
    names no commitment is `done`."""
    acts = []
    for a in frame.get("actions") or []:
        commit = a.get("commit") or "done"
        means = {"power": a.get("power"), "means": a.get("means") or "ordinary"}
        # The act's cost unless the demonstration names its own (`ACT_COSTS`), so every
        # demonstration teaches one.
        cost = {"cost": a.get("cost") or ACT_COSTS[a["act"]]}
        if SCHEMA != "per_act":
            acts.append({"span": a.get("span", ""), "commit": commit,
                         **{s: a.get(s) for s in SLOTS}, **means, "act": a["act"], **cost})
            continue
        acts.append({"span": a.get("span", ""), "commit": commit, "act": a["act"],
                     **{s: a.get(s) for s in ACT_SLOTS.get(a["act"], ())},
                     **({"asks_for": a.get("asks_for") or REQUESTS[1]}
                        if a["act"] == "request" else {}),
                     **({"craft": a.get("craft") or CRAFTS[0],
                         "work": a.get("work") or WORKS[0]}
                        if a["act"] == "craft" else {}),
                     **({"pace": a.get("pace") or PACES[0],
                         "diversion": a.get("diversion") or DIVERSIONS[0]}
                        if a["act"] == "stealth" else {}),
                     **({"until": a.get("until") or UNTILS[0]}
                        if a["act"] in UNTIL_ACTS else {}),
                     **({"way": a.get("way") or ESCAPE_WAYS[0]}
                        if a["act"] == "escape" else {}),
                     **({"blow": a.get("blow") or BLOWS[0]}
                        if a["act"] == "attack" else {}),
                     **({"within_place": bool(a.get("within_place")),
                         "fixture": a.get("fixture") or "none"}
                        if a["act"] == "go" else {}), **cost, **means})
    return json.dumps({"question": frame.get("question", False), "actions": acts,
                       "claims": frame.get("claims", [])})


def messages(sentence: str) -> list[dict]:
    system = (
        "You read what a player typed in a text role-playing game and write down, in "
        "order, each thing their character sets out to do. Copy every slot as words "
        "from the sentence itself — never a paraphrase, never a word that is not "
        "there. Leave a slot null when the sentence does not say it. A question asked "
        "of the game, not done in it, is question=true with no actions. Anything the "
        "player states as having happened, rather than attempts, is a claim.\n\n"
        "The acts:\n" + _WHAT_EACH_IS)
    out = [{"role": "system", "content": system}]
    for said, frame in _DEMOS:
        out.append({"role": "user", "content": said})
        out.append({"role": "assistant", "content": _demo_reply(frame)})
    out.append({"role": "user", "content": sentence})
    return out


_TIME_WORD = re.compile(
    r"\b(?:until|till|for|while|dawn|dusk|noon|midday|midnight|morning|evening|night|"
    r"tonight|tomorrow|hours?|minutes?|days?|weeks?|months?|years?|dark|light|sunset|"
    r"sunrise|daybreak|nightfall|moment|bell|o'clock|am|pm)\b", re.I)


# A slot that is nothing but a time: "a while", "for an hour", "until he stops moving".
_A_TIME = re.compile(r"^(?:until|till|for|all|a|the)\s+(?:while\b|night\b|day\b|hour|moment|morning|evening)|^(?:until|till)\b|^for\s+(?:a|an|the|\d+|one|two|three|some|several)\b", re.I)


_NULL_WORDS = frozenset({"none", "null", "n/a", "-"})


def _within(span, sentence: str) -> bool:
    return bool(span) and str(span).strip().lower() in sentence.lower()


def ground(frame: dict, sentence: str) -> tuple[dict, list[str]]:
    """Every slot must be the player's own words: one that is not is dropped, and said.
    A claim that is not in the sentence is dropped the same way."""
    dropped: list[str] = []
    actions = []
    for a in frame.get("actions") or []:
        if not isinstance(a, dict) or a.get("act") not in ACTS:
            continue
        kept = {"act": a["act"]}
        # How far it is done; a reply from the flat schema of before 2026-10-03, or a
        # value outside the enum, is `done` — the reading the turn always acted on.
        commit = str(a.get("commit") or "done")
        if commit != "done":
            kept["commit"] = commit if commit in COMMITS else "done"
        used: set[str] = set()
        for s in ACT_SLOTS.get(a["act"], SLOTS):
            v = a.get(s)
            if v in (None, ""):
                continue
            v = str(v).strip()
            # The null written as a word: the per-act schema's probe came back
            # `target: "none"` on a gesture. Nothing is there.
            if v.lower() in _NULL_WORDS:
                continue
            if not _within(v, sentence):
                dropped.append(f"{a['act']}.{s}={v!r}")
                continue
            # One phrase, one slot: measured, "I punch him again" came back with "him"
            # as target, object AND place. The act's first slot keeps it — and a phrase
            # inside another slot's phrase is part of that description, not a second
            # thing: "a scribe" as the place of "a scribe who can read a letter".
            low = v.lower()
            if any(low in u or u in low for u in used):
                continue
            # A time is a time: "the face", "again" and "keep" all came back as one.
            if s == "time" and not _TIME_WORD.search(v):
                continue
            # And a time written into another slot is the time: "I follow the tracks a
            # while" came back with "a while" as the object.
            if s != "time" and _A_TIME.match(v):
                if "time" in ACT_SLOTS.get(a["act"], SLOTS) and "time" not in kept:
                    kept["time"] = v
                    used.add(low)
                continue
            kept[s] = v
            used.add(low)
        _speech_is_not_a_target(kept, dropped)
        if kept["act"] == "request":
            # What is asked for is the enum's, never words: outside it (a hosted provider
            # does not enforce the schema, or a reply from the flat shape) the asking is
            # only talk, and the engine rolls nothing for it.
            asks = str(a.get("asks_for") or "").strip().lower()
            if asks in REQUESTS:
                kept["asks_for"] = asks
            else:
                dropped.append(f"request.asks_for={a.get('asks_for')!r}")
                kept["act"] = "talk"
                if kept.get("object"):
                    kept["says"] = kept.pop("object")
        if kept["act"] == "craft":
            # Which craft is the enum's, never words, as a request's `asks_for` is: outside
            # it the work is `other`, which owes no op — and nothing is made. How fine is
            # the enum's too; outside it the plain item is the reading.
            trade = str(a.get("craft") or "").strip().lower()
            if trade in CRAFTS:
                kept["craft"] = trade
                work = str(a.get("work") or "").strip().lower()
                kept["work"] = work if work in WORKS else WORKS[0]
            else:
                dropped.append(f"craft.craft={a.get('craft')!r}")
                kept["act"] = "other"
        if kept["act"] == "stealth":
            # The enums' or the default: outside them (a hosted provider, a remembered
            # frame) the hiding is the careful one with no diversion — the reading the
            # turn always acted on. Kept only when they say something, as `commit` is.
            pace = str(a.get("pace") or "").strip().lower()
            if pace in PACES and pace != PACES[0]:
                kept["pace"] = pace
            div = str(a.get("diversion") or "").strip().lower()
            if div in DIVERSIONS and div != DIVERSIONS[0]:
                kept["diversion"] = div
        if kept["act"] in UNTIL_ACTS:
            # The enum's or nothing, kept only when it names something (`UNTILS`). Outside
            # it (a hosted provider, a remembered frame) the time slot's words are read
            # by the numbers table as they always were (`until_minutes`).
            until = str(a.get("until") or "").strip().lower()
            if until in UNTILS and until != UNTILS[0]:
                kept["until"] = until
        if kept["act"] == "escape":
            # The way is the enum's or "either": the engine then rolls the better of the
            # two (`Engine._escape_from`). Kept only when it says something.
            way = str(a.get("way") or "").strip().lower()
            if way in ESCAPE_WAYS and way != ESCAPE_WAYS[0]:
                kept["way"] = way
        if kept["act"] == "attack":
            # The enum's or ordinary: outside it (a hosted provider, a remembered frame)
            # the blow is the one the turn always built. Kept only when it is finishing.
            blow = str(a.get("blow") or "").strip().lower()
            if blow in BLOWS and blow != BLOWS[0]:
                kept["blow"] = blow
        if kept["act"] == "go" and a.get("within_place") is True:
            # A walk inside the place (`within_place`): kept only when it says so, as
            # `blow` is. Only the boolean itself: a hosted provider's "yes" is not it.
            kept["within_place"] = True
        if kept["act"] == "go":
            # The fixture is the enum's or nothing; "none", or a word outside the closed
            # list (a hosted provider does not enforce the schema), is no fixture.
            fixture = str(a.get("fixture") or "").strip().lower()
            if fixture != "none" and fixture in fixture_kinds():
                kept["fixture"] = fixture
            elif fixture and fixture != "none":
                dropped.append(f"go.fixture={a.get('fixture')!r}")
        # By what means (`MEANS`). Absent or outside the enum — a reading from before
        # 2026-10-05, a remembered test frame — is ordinary: the reading the turn always
        # acted on. A power's name is held to the sentence like every slot; one that is
        # not the player's words is dropped and said, and the means stands without it
        # (gm/means.py then asks the sheet about the deed's own words instead).
        means = str(a.get("means") or "ordinary")
        if means in MEANS and means != "ordinary":
            kept["means"] = means
        # What it costs of the turn (`COSTS`): the enum's, kept only when it differs from
        # the act's own (`ACT_COSTS`), as `commit` and `means` are kept only when they say
        # something — after the act is settled, since a request or a craft outside its
        # enum became talk or other above. Outside the enum it is dropped and said, and
        # `cost_of` answers from the act.
        cost = str(a.get("cost") or "").strip().lower()
        if cost in COSTS:
            if cost != ACT_COSTS.get(kept["act"]):
                kept["cost"] = cost
        elif cost:
            dropped.append(f"{kept['act']}.cost={a.get('cost')!r}")
        power = str(a.get("power") or "").strip()
        if power and power.lower() not in _NULL_WORDS:
            if _within(power, sentence):
                kept["power"] = power
            else:
                dropped.append(f"{a['act']}.power={power!r}")
        # The action's own words, when they are the player's: what a targeted second
        # question is asked about (`confirm_sale`).
        if _within(a.get("span"), sentence):
            kept["span"] = " ".join(str(a["span"]).split())
        actions.append(kept)
    actions = merge_repeats(actions)
    claims = [c for c in (frame.get("claims") or []) if _within(c, sentence)]
    dropped += [f"claim={c!r}" for c in (frame.get("claims") or []) if not _within(c, sentence)]
    return ({"question": bool(frame.get("question")), "actions": actions,
             "claims": claims}, dropped)


def merge_repeats(actions: list[dict], dropped: list[str] | None = None) -> list[dict]:
    """One deed read twice is one deed: two actions in a row with the same act whose
    slots do not disagree are merged, the first's slots kept and the second's added.

    Measured 2026-10-03 on the first 60 labelled lines, 3 of the 19 misses: "I make camp
    and sleep until dawn" came back `rest` then `rest, time: until dawn`; "I look around
    and take stock" `look` then `look …`; "I thank her, say goodnight" `talk, target: her`
    then `talk, says: goodnight`. Each would be two ops in the turn — two rests, two says.
    Structure only, never the words: a second action that names a DIFFERENT target, object,
    place, time or words is a second deed ("I buy bread and buy cheese"; "I turn my back
    on him and tell the barkeep he smells" insults two people), and stays.

    Narrowed in round 2: never when the SECOND is bare. The first rule — merge whenever
    nothing disagrees — joined `consume, object: …` and a bare `consume` into one, and the
    held-out set had that as two deeds ("eat … and drink"): one of the 4.4 acts-in-order
    points lost, found by an act-level count of the flips (no sentence read). A bare second
    is a deed whose object went unsaid; a second that only adds to the first (`rest` then
    `rest, time: until dawn`; `attack, target: him` then the same with `object: the face`)
    is the first spelled out. A first try that merged only after a bare FIRST lost the
    second kind (`attack` twice, the same count). And the commitments must agree."""
    out: list[dict] = []
    for a in actions:
        prev = out[-1] if out else None
        if prev is not None and prev.get("act") == a.get("act") \
                and prev.get("commit", "done") == a.get("commit", "done") \
                and prev.get("means", "ordinary") == a.get("means", "ordinary") \
                and any(a.get(s) for s in SLOTS) and not any(
                    prev.get(s) and a.get(s) and prev[s].lower() != a[s].lower()
                    for s in SLOTS):
            for s in (*SLOTS, "power", "cost"):
                if a.get(s) and not prev.get(s):
                    prev[s] = a[s]
            if dropped is not None:
                dropped.append(f"{a['act']} (the same deed twice, merged)")
            continue
        out.append(a)
    return out


_SAY_HEAD = re.compile(r"^\s*(?:say|says|said|tell|tells|ask|asks|shout|shouts|whisper|"
                       r"whispers|murmur|murmurs|reply|replies|answer|answers|mutter|"
                       r"mutters|add|adds)\b[\s,:]*", re.I)


def _speech_is_not_a_target(action: dict, dropped: list[str]) -> None:
    """A quotation is never who is spoken to; "say X" is speech, not a person called
    "say X".

    Measured on the owner's 2026-10-03 save (item 13): `I give a friendly wink and say
    "just trying to start a conversation and see what is happening here."` came back
    `talk, target: say "just trying…"` — the span was the sentence's own words, so
    grounding kept it — and `introduce` minted a person by that name. Inform's grammar
    keeps a topic or a quoted string out of the object slots entirely (WI §7.6, §17.5),
    and TADS 3 reads SAY's argument as a literal (`LiteralAction`). Same here, in code:
    a target whose shape is not a person's (`names.not_a_name`) is dropped, and its
    words become what is said when the act can say anything and nothing else was read."""
    from rules.names import not_a_name

    target = action.get("target")
    if not target or not not_a_name(target):
        return
    del action["target"]
    dropped.append(f"{action['act']}.target={target!r} (speech, not somebody)")
    if "says" in ACT_SLOTS.get(action["act"], ()) and not action.get("says"):
        from .speech import spans

        # The one quotation scanner (gm/speech.py), never a second rule here.
        quoted = [target[a + 1:b - 1] for a, b in spans(target) if b - a > 2]
        words = (quoted[0] if quoted else _SAY_HEAD.sub("", target)).strip()
        if words:
            action["says"] = words


def interpret(sentence: str, *, model: str | None = None, host: str | None = None,
              provider: str | None = None, api_key: str = "",
              temperature: float = 0.0) -> dict:
    """The frame for one sentence: {"question", "actions", "claims", "dropped",
    "seconds", "raw"}. The narrator's model unless another is named — the model already
    loaded, because a second model's load is what dominates local latency."""
    from . import client
    from play import modelcfg

    # A role nobody configured comes back as {"api_key": ""}, which is truthy.
    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    started = time.monotonic()
    reply = client.chat(messages(sentence), model or cfg["model"],
                        host or cfg["host"], as_json=True, think=False,
                        temperature=temperature, num_predict=400,
                        provider=provider or cfg.get("provider", "ollama"),
                        api_key=api_key or cfg.get("api_key", ""), schema=reply_schema())
    try:
        raw = reply.json()
    except Exception:
        raw = {}
    frame, dropped = ground(raw if isinstance(raw, dict) else {}, sentence)
    frame.update(dropped=dropped, seconds=round(time.monotonic() - started, 2),
                 raw=reply.text)
    return frame


# --- a sale, asked again ---------------------------------------------------------------------
#
# CLAUDE.md's rule: detect mechanically, repair with a targeted call. A sale is the one
# goods op the player cannot take back, and the frozen reader still misread its
# commitment on the owner's own lines (round 2's replay, readings from the frozen reader):
# "I take the crate to the man in the counting house who will buy it from me" came back
# `sell` DONE, and "I smile and flirt with the clerk and offer the crate for coin" `sell`
# DONE — the round-1 regression back, through a different door. So when the table is
# about to build a sale to somebody who keeps no counter, the reader is asked that one
# question alone, with the sale's own words in front of it: closed now, only offered,
# meant for later, or asked about? One enum, demonstrated; the frame's other twenty
# fields are not asked again. The demonstrations are not in the labelled set.
_SALE_DEMOS = [
    ("I tell the tanner the hides are his for four silver.", "the hides are his", "done"),
    ("I offer the tanner the hides.", "offer the tanner the hides", "tried"),
    ("I haggle with the tanner over the hides, smiling.", "haggle with the tanner over the hides",
     "tried"),
    ("I bring the hides to the tanner, who always buys them from me.",
     "who always buys them from me", "intended"),
    ("I shake the tanner's hand on the price.", "shake the tanner's hand on the price", "done"),
    ("Tomorrow I'll sell the hides to the tanner.", "sell the hides to the tanner", "intended"),
    ("I ask the tanner if she would take the hides.", "if she would take the hides", "asked"),
    ("I hand the hides over to the tanner and take her coin.",
     "hand the hides over to the tanner", "done"),
]


def sale_messages(sentence: str, span: str) -> list[dict]:
    system = ("A player in a role-playing game wrote the line below. Answer one question "
              "about the sale in it: is the sale CLOSED now (done: agreed, accepted, handed "
              "over for the price), only OFFERED or haggled over (tried), meant for LATER or "
              "something somebody else will do (intended), or ASKED ABOUT (asked)?")
    out = [{"role": "system", "content": system}]
    for said, part, commit in _SALE_DEMOS:
        out.append({"role": "user", "content": f"Line: {said}\nThe sale: {part}"})
        out.append({"role": "assistant", "content": json.dumps({"commit": commit})})
    out.append({"role": "user", "content": f"Line: {sentence}\nThe sale: {span}"})
    return out


def confirm_sale(sentence: str, span: str, *, model: str | None = None) -> str:
    """How far the sale in `span` is done, asked alone: one of `COMMITS`; "" when the
    call fails (the caller then holds the sale back — an offer, never a sale)."""
    from . import client
    from play import modelcfg

    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    schema = {"type": "object", "properties": {"commit": {"type": "string",
                                                          "enum": list(COMMITS)}},
              "required": ["commit"]}
    try:
        reply = client.chat(sale_messages(sentence, span), model or cfg["model"], cfg["host"],
                            as_json=True, think=False, temperature=0.0, num_predict=30,
                            provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = str((reply.json() or {}).get("commit") or "")
    except Exception:  # noqa: BLE001 — a failed check holds the sale back
        return ""
    return got if got in COMMITS else ""


# --- a take from a person, asked again -------------------------------------------------
#
# Since 2026-10-08 a `give` the player makes from somebody else's hands is a TAKE
# (`Engine._op_give`): the owner is kept and the thing is marked stolen. That is right for
# "I take an apple from the fruit seller without paying" (measured: it used to be filed as
# the seller handing it over), and wrong for "I take the purse he holds out" — a reward
# would be a theft. Whether the holder agreed is not in the take's own words; it is in the
# beat before them, so the one question is asked with that beat in front of it: did the
# person give or offer it, or did the player take it without their agreement? Two enum
# values, demonstrated, none of them from the measured lines (tests/test_spoken_theft.py
# holds what was measured).
TAKE_ANSWERS = ("offered", "taken")

_TAKE_DEMOS = [
    ("The tanner is bent over a vat, her back to the street.",
     "I lift a strip of leather from the tanner's rack", "taken"),
    ("The old reeve holds out a small purse. \"For your trouble,\" he says.",
     "I take the purse from the reeve", "offered"),
    ("The baker slides a warm bun across the counter. \"On the house.\"",
     "I take the bun from her and thank her", "offered"),
    ("The gaoler snores on his stool, the ring of keys on his belt.",
     "I take the keys from the gaoler", "taken"),
    ("The pedlar haggles with a woman over a length of ribbon.",
     "I help myself to a ribbon from the pedlar's tray", "taken"),
    ("\"Go on, then — pick one,\" the fishwife says, tipping her basket towards you.",
     "I take a herring from the fishwife", "offered"),
    ("The clerk pushes the receipt across the desk for you to keep.",
     "I take the receipt from the clerk", "offered"),
    ("The cooper counts his barrels and does not look up.",
     "I grab a mallet from the cooper", "taken"),
]


def take_messages(beat: str, span: str) -> list[dict]:
    system = ("A player in a role-playing game takes something from another person. "
              "Using the scene just before, answer one question: did that person GIVE or "
              "OFFER it (held it out, handed it over, told them to take it, a gift, a "
              "reward, their change) — offered — or did the player take it WITHOUT the "
              "person agreeing (lifted, grabbed, helped themselves, did not pay, while "
              "the person was busy or asleep) — taken?")
    out = [{"role": "system", "content": system}]
    for before, said, answer in _TAKE_DEMOS:
        out.append({"role": "user", "content": f"Scene: {before}\nThe take: {said}"})
        out.append({"role": "assistant", "content": json.dumps({"took": answer})})
    out.append({"role": "user", "content": f"Scene: {beat or '(nothing yet)'}\n"
                                           f"The take: {span}"})
    return out


def confirm_take(beat: str, span: str, *, model: str | None = None) -> str:
    """"offered" or "taken" for a take from a person; "" when the call fails (the caller
    then leaves it a take — the engine's own rule, docs/items-have-owners.md)."""
    from . import client
    from play import modelcfg

    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    schema = {"type": "object", "properties": {"took": {"type": "string",
                                                        "enum": list(TAKE_ANSWERS)}},
              "required": ["took"]}
    try:
        reply = client.chat(take_messages(beat, span), model or cfg["model"], cfg["host"],
                            as_json=True, think=False, temperature=0.0, num_predict=20,
                            provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = str((reply.json() or {}).get("took") or "")
    except Exception:  # noqa: BLE001 — a failed question leaves the take a take
        return ""
    return got if got in TAKE_ANSWERS else ""


# --- first aid, asked -----------------------------------------------------------------
#
# A deed aimed at somebody the engine says is dying (`acts_to_ops.first_aid`) may be first
# aid or anything else done to a body. The reader reads "I give first aid to the porter"
# as `other` and "I bandage him" as `use`, and no act of its vocabulary is first aid, so
# the one question is put on its own, with the deed's own words. Demonstrations written
# for this; none is a measured line.
AID_ANSWERS = ("first aid", "something else")

_AID_DEMOS = [
    ("press my cloak hard against the sailor's wound", "the sailor", "first aid"),
    ("drag the sailor into the shade of the wall", "the sailor", "something else"),
    ("stitch the gash in the hunter's thigh", "the hunter", "first aid"),
    ("say a prayer over the old drover", "the old drover", "something else"),
    ("try to stop the bleeding with my belt", "the guard", "first aid"),
    ("search the guard's boots for a hidden blade", "the guard", "something else"),
]


def aid_messages(span: str, patient: str) -> list[dict]:
    system = ("In a role-playing game, the player's character does something to a person "
              "who is lying on the ground dying, bleeding out. Answer one question: is the "
              "player trying to keep them alive — first aid, binding or stitching the "
              "wound, stopping the bleeding, tending them — or doing something else?")
    out = [{"role": "system", "content": system}]
    for said, who, answer in _AID_DEMOS:
        out.append({"role": "user", "content": f"Dying: {who}\nThe act: {said}"})
        out.append({"role": "assistant", "content": json.dumps({"act": answer})})
    out.append({"role": "user", "content": f"Dying: {patient}\nThe act: {span}"})
    return out


def confirm_first_aid(span: str, patient: str, *, model: str | None = None) -> str:
    """One of `AID_ANSWERS`; "" when the call fails (no first aid is built: the plan's own
    ops stand, as before)."""
    from . import client
    from play import modelcfg

    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    # The key is act: the deeds system keeps its own word out of everything the models are
    # shown (tests/test_deeds.py), and this question is about the act itself.
    schema = {"type": "object", "properties": {"act": {"type": "string",
                                                       "enum": list(AID_ANSWERS)}},
              "required": ["act"]}
    try:
        reply = client.chat(aid_messages(span, patient), model or cfg["model"], cfg["host"],
                            as_json=True, think=False, temperature=0.0, num_predict=20,
                            provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = str((reply.json() or {}).get("act") or "")
    except Exception:  # noqa: BLE001
        return ""
    return got if got in AID_ANSWERS else ""


# --- what a trail is followed to, asked ------------------------------------------------
#
# The owner's report, 2026-10-27: "I continue to track the caravan" — and there was no
# caravan anywhere in the engine. To say so, the track has to know what it is after. The
# reader puts that in either slot, and the marks themselves in either too — probed live the
# same day on gemma-4-12B: "I follow the tracks in search of the caravan" came back
# `target: the tracks, object: the caravan`; "I continue to track the caravan" `object: the
# caravan`; "I search the ground for footprints" `object: footprints`; "I follow the cart
# ruts toward the ford" `target: the cart ruts`. Which phrase names the one who MADE the
# trail is a reading, so it is asked, one phrase at a time, with the act's own words; a
# phrase that names somebody the engine already holds is never asked (`acts_to_ops`).
# Demonstrations written for this, in no world's words; none is a probed line.
QUARRY_ANSWERS = ("the maker", "only the marks")

_QUARRY_DEMOS = [
    ("follow the drag marks back to the boar", "the boar", "the maker"),
    ("follow the drag marks back to the boar", "the drag marks", "only the marks"),
    ("read the mud by the ford for hoofprints", "hoofprints", "only the marks"),
    ("track the smugglers' handcart along the dyke", "the smugglers' handcart", "the maker"),
    ("look for a trail", "a trail", "only the marks"),
    ("hunt for the missing shepherd's tracks", "the missing shepherd", "the maker"),
]


def quarry_messages(span: str, phrase: str) -> list[dict]:
    system = ("In a role-playing game, the player's character looks for tracks or follows "
              "a trail. One phrase of what they said is given. Answer one question: does "
              "the phrase name WHO OR WHAT MADE the trail — a person, a creature, a group, "
              "a cart or a wagon train — or only the marks themselves (tracks, a trail, "
              "footprints, ruts, prints)?")
    out = [{"role": "system", "content": system}]
    for said, words, answer in _QUARRY_DEMOS:
        out.append({"role": "user", "content": f"What they said: {said}\nThe phrase: {words}"})
        out.append({"role": "assistant", "content": json.dumps({"names": answer})})
    out.append({"role": "user", "content": f"What they said: {span}\nThe phrase: {phrase}"})
    return out


def confirm_quarry(span: str, phrase: str, *, model: str | None = None) -> str:
    """One of `QUARRY_ANSWERS`; "" when the call fails (no quarry is kept: the track looks
    for tracks, as it did before, and claims nothing about what it is after)."""
    from . import client
    from play import modelcfg

    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    schema = {"type": "object", "properties": {"names": {"type": "string",
                                                         "enum": list(QUARRY_ANSWERS)}},
              "required": ["names"]}
    try:
        reply = client.chat(quarry_messages(span, phrase), model or cfg["model"],
                            cfg["host"], as_json=True, think=False, temperature=0.0,
                            num_predict=20, provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = str((reply.json() or {}).get("names") or "")
    except Exception:  # noqa: BLE001
        return ""
    return got if got in QUARRY_ANSWERS else ""


# --- a matter taken on, asked -----------------------------------------------------------
#
# Measured live 2026-10-27 on a scratch Fizspark campaign: "I tell Brix, 'I will find your
# Coldwood for you.'" to the giver of a quest the player had heard of, and the planner
# proposed no `quest` op — the take-up the plan's rules ask for — so the quest stayed
# somebody else's. Whether the player's words agree to do it is a reading, asked only when
# the engine holds such a matter from the person spoken to (`acts_to_ops.take_ups`).
# Demonstrations written for this, in no world's words; none is a probed line.
TAKE_UP_ANSWERS = ("agrees to do it", "does not")

_TAKE_UP_DEMOS = [
    ("tell the miller I'll get his ledger back", "the miller", "Recover the miller's ledger",
     "agrees to do it"),
    ("ask the miller where he last saw the ledger", "the miller",
     "Recover the miller's ledger", "does not"),
    ("shake the ferrywoman's hand on it and promise to bring the net back",
     "the ferrywoman", "Find the ferrywoman's lost net", "agrees to do it"),
    ("tell the ferrywoman to find her own net", "the ferrywoman",
     "Find the ferrywoman's lost net", "does not"),
    ("say \"Fine, I'll look into it\"", "the reeve", "Find out who poisoned the well",
     "agrees to do it"),
    ("ask the reeve what he would pay", "the reeve", "Find out who poisoned the well",
     "does not"),
]


def take_up_messages(span: str, giver: str, matter: str) -> list[dict]:
    system = ("In a role-playing game, somebody wants a task done, and the player's "
              "character speaks to them. Answer one question: in these words, does the "
              "player AGREE to do the task — say they will, promise it, accept it — or "
              "not (asking about it, haggling, refusing, or talking of something else)?")
    out = [{"role": "system", "content": system}]
    for said, who, task, answer in _TAKE_UP_DEMOS:
        out.append({"role": "user",
                    "content": f"Who wants it: {who}\nThe task: {task}\nThe words: {said}"})
        out.append({"role": "assistant", "content": json.dumps({"answer": answer})})
    out.append({"role": "user",
                "content": f"Who wants it: {giver}\nThe task: {matter}\nThe words: {span}"})
    return out


def confirm_take_up(span: str, giver: str, matter: str, *,
                    model: str | None = None) -> str:
    """One of `TAKE_UP_ANSWERS`; "" when the call fails (nothing is taken up: the matter
    stays the giver's, as the plan alone would have left it)."""
    from . import client
    from play import modelcfg

    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    schema = {"type": "object", "properties": {"answer": {
        "type": "string", "enum": list(TAKE_UP_ANSWERS)}}, "required": ["answer"]}
    try:
        reply = client.chat(take_up_messages(span, giver, matter), model or cfg["model"],
                            cfg["host"], as_json=True, think=False, temperature=0.0,
                            num_predict=20, provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = str((reply.json() or {}).get("answer") or "")
    except Exception:  # noqa: BLE001
        return ""
    return got if got in TAKE_UP_ANSWERS else ""


# --- what the player's words do about a job, asked ---------------------------------------
#
# The owner's report of 2026-10-27: at the hiring table ("Can you carry, count or fight?")
# the clerk's replies made up an escort nobody held. With real jobs held (rules/jobs.py),
# what the player's words DO about them — say what work they can do, ask about it, agree to
# it, turn it down, ask for more pay — is a reading, asked only when the engine holds work
# from the person spoken to (`acts_to_ops.jobs_spoken`), as one closed question: the
# answer, the work named (the table's own three words), and which of the jobs put to them
# an agreement is to (their titles, the engine's, as the enum). Demonstrations written for
# this, in no world's words; none is a probed line.
JOB_ANSWERS = ("says what work they can do", "asks about the work", "agrees to the job",
               "turns it down", "asks for more pay", "something else")
WORK_SAID = ("carry", "count", "fight", "not said")
NOT_SAID = "not said"

_JOB_DEMOS = [
    ("tell the reeve I can swing an axe as well as anyone", "the reeve",
     ["Clear the north field"], "says what work they can do", "fight", NOT_SAID),
    ("say \"I can haul sacks all day\"", "the foreman", [],
     "says what work they can do", "carry", NOT_SAID),
    ("ask the foreman what the job pays and where it goes", "the foreman",
     ["Drive cattle to the ford"], "asks about the work", NOT_SAID, NOT_SAID),
    ("tell her I'll take the cattle drive", "the drover",
     ["Drive cattle to the ford", "A week mending fences"], "agrees to the job", NOT_SAID,
     "Drive cattle to the ford"),
    ("say \"Done. Put my name down.\"", "the foreman", ["A week mending fences"],
     "agrees to the job", NOT_SAID, "A week mending fences"),
    ("tell him that's too little for a sword arm, I want more", "the reeve",
     ["Clear the north field"], "asks for more pay", NOT_SAID, NOT_SAID),
    ("tell the drover I'd rather not", "the drover", ["Drive cattle to the ford"],
     "turns it down", NOT_SAID, "Drive cattle to the ford"),
    ("ask the foreman where the privy is", "the foreman", ["A week mending fences"],
     "something else", NOT_SAID, NOT_SAID),
]


def job_messages(span: str, employer: str, jobs) -> list[dict]:
    system = ("In a role-playing game, somebody is hiring, and the player's character speaks "
              "to them. Answer from the words alone: what the words do about the work — say "
              "what work the character can do (and which: carry, count, or fight — guarding "
              "and swordwork are fight), ask about it, agree to a job (and which of the jobs "
              "put to them), turn it down, ask for more pay, or something else.")
    out = [{"role": "system", "content": system}]
    for said, who, titles, answer, work, job in _JOB_DEMOS:
        out.append({"role": "user", "content": f"Who is hiring: {who}\nJobs put to the "
                    f"character: {'; '.join(titles) or 'none yet'}\nThe words: {said}"})
        out.append({"role": "assistant",
                    "content": json.dumps({"answer": answer, "work": work, "job": job})})
    out.append({"role": "user", "content": f"Who is hiring: {employer}\nJobs put to the "
                f"character: {'; '.join(jobs) or 'none yet'}\nThe words: {span}"})
    return out


def confirm_job(span: str, employer: str, jobs=(), *,
                model: str | None = None) -> dict:
    """{"answer", "work", "job"} from the closed lists; {} when the call fails (nothing is
    done about the work: the turn goes on as the plan alone would have it)."""
    from . import client
    from play import modelcfg

    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    titles = [str(t) for t in jobs or ()]
    schema = {"type": "object", "properties": {
        "answer": {"type": "string", "enum": list(JOB_ANSWERS)},
        "work": {"type": "string", "enum": list(WORK_SAID)},
        "job": {"type": "string", "enum": titles + [NOT_SAID]}},
        "required": ["answer", "work", "job"]}
    try:
        reply = client.chat(job_messages(span, employer, titles), model or cfg["model"],
                            cfg["host"], as_json=True, think=False, temperature=0.0,
                            num_predict=60, provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = reply.json() or {}
    except Exception:  # noqa: BLE001
        return {}
    answer = str(got.get("answer") or "")
    if answer not in JOB_ANSWERS:
        return {}
    work = str(got.get("work") or NOT_SAID)
    job = str(got.get("job") or NOT_SAID)
    return {"answer": answer, "work": work if work in WORK_SAID else NOT_SAID,
            "job": job if job in titles else NOT_SAID}


# --- whether the player's words have somebody come along, asked --------------------------
#
# The owner's save of 2026-11-05 (turn_log row 7): "Accept the terms of the work", to Vyrnys,
# who had just offered a week of guard work. The reader read one `other`, and the table built
# the job (`acts_to_ops.jobs_spoken`). The plan ALSO wrote `{"op": "company", "params":
# {"who": "c2"}}` — the prompt's own example, word for word, with no actor and no `because`
# (gm/prompts.py teaches company for "a friend, a guide, a hired sword", and c2 was Vyrnys).
# The engine refused it, Vyrnys being indifferent ("Talk them round first — that is a
# Diplomacy check"), and the planned narrator wrote "Vyrnys remains unmoved by your words"
# on a turn where the player had simply taken a job.
#
# Somebody coming along is the player's to ask for, in their own words, and the reader has
# no act for it: a `talk`, a `request`, or an `other`. So a plan's `company` is asked ONE
# question, only when the plan wrote one (`acts_to_ops.company_asked`): do these words have
# this person come along, send them away, or neither. Demonstrations written for this, in no
# world's words; none is a probed line, and the owner's line is not among them.
COMPANY_ANSWERS = ("has them come along", "sends them away", "something else")
_COMPANY_DEMOS = [
    ("ask Tamsin to come with me to the ford", "Tamsin", "has them come along"),
    ("say \"Pack your things, you're coming with us\"", "the guide", "has them come along"),
    ("tell him he's welcome to travel with us", "the old tinker", "has them come along"),
    ("hire the sellsword to watch my back on the road", "the sellsword",
     "has them come along"),
    ("tell her to go home, we part ways here", "the guide", "sends them away"),
    ("take the foreman's job guarding the warehouse", "the foreman", "something else"),
    ("agree to the reeve's terms for the week", "the reeve", "something else"),
    ("ask her what the road ahead is like", "the guide", "something else"),
    ("thank him for the bread", "the baker", "something else"),
]


def company_messages(span: str, who: str) -> list[dict]:
    system = ("In a role-playing game the player's character says or does something near "
              "another person. Answer from the words alone: do they have that person come "
              "along with the character from now on (asked to come, invited, hired to go "
              "with them, or told yes when the person offered to come), send that person "
              "away (part company, tell them to go), or something else? Taking work FROM "
              "somebody, agreeing to their terms, or talking with them is something else.")
    out = [{"role": "system", "content": system}]
    for said, person_, answer in _COMPANY_DEMOS:
        out.append({"role": "user", "content": f"The person: {person_}\nThe words: {said}"})
        out.append({"role": "assistant", "content": json.dumps({"answer": answer})})
    out.append({"role": "user", "content": f"The person: {who}\nThe words: {span}"})
    return out


def confirm_company(span: str, who: str, *, model: str | None = None) -> str:
    """One of `COMPANY_ANSWERS`; "" when the call fails (the caller then judges the plan's
    company by the reading's acts alone, `acts_to_ops.company_asked`)."""
    from . import client
    from play import modelcfg

    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    schema = {"type": "object", "properties": {"answer": {
        "type": "string", "enum": list(COMPANY_ANSWERS)}}, "required": ["answer"]}
    try:
        reply = client.chat(company_messages(span, who), model or cfg["model"],
                            cfg["host"], as_json=True, think=False, temperature=0.0,
                            num_predict=20, provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = str((reply.json() or {}).get("answer") or "")
    except Exception:  # noqa: BLE001
        return ""
    return got if got in COMPANY_ANSWERS else ""


# --- who a blow lands on, asked ---------------------------------------------------------
#
# The owner, 2026-10-09: "if i say I attack the closest person or i go on a rampage or i
# assault a civilian etc. it should be able to start a fight." Measured live the same day
# (gemma-4-12B, a market of three bystanders on scratch data): "I attack the closest person."
# had the planner aim, rightly, at the fruit seller beside the player — and the fight
# declarer required a `spawn` behind it, so two bandits came out of nowhere and joined the
# fight on her side. `judgement.inject_fight` read the sentence with a regex and, finding
# nobody `_can_be_fought` (bystanders are not), conjured a template opponent.
#
# Who "the closest person", "a civilian" or "the biggest bruiser in the room" means is not
# in the words alone: it is the words held against the people standing here. So the one
# question is put with those people in front of it, as refs the sampler cannot leave: WHICH
# of them could the words mean — every one of them for "the closest person" or a rampage,
# the townsfolk for "a civilian", the one bruiser for "the biggest bruiser", nobody when
# nobody here fits. Which of those is NEAREST is the engine's to answer, from the squares
# people keep (`acts_to_ops.victims`), never the model's: a model asked "who is closest"
# would be guessing at a map it cannot see.
#
# Demonstrations written for this, with their own people; none is a measured line.
_VICTIM_DEMOS = [
    ("attack the closest person",
     [("c1", "a fishwife gutting herring"), ("c2", "the sailor with a bad leg"),
      ("c3", "the harbour guard")], ["c1", "c2", "c3"]),
    ("assault a civilian",
     [("c1", "the gate guard (a guard)"), ("c2", "a baker carrying loaves"),
      ("c3", "the old washerwoman")], ["c2", "c3"]),
    ("run amok through the stalls",
     [("c1", "the pedlar"), ("c2", "a girl selling ribbons")], ["c1", "c2"]),
    ("pick a fight with the biggest man in the tavern",
     [("c1", "a thin clerk"), ("c2", "the hulking stevedore with tattooed arms"),
      ("c3", "an old woman by the fire")], ["c2"]),
    ("punch the guard",
     [("c1", "a merchant"), ("c2", "the watchman at the door (a guard)")], ["c2"]),
    ("stab the priest",
     [("c1", "a farmer"), ("c2", "a small boy")], []),
    ("hit the nearest guard",
     [("c1", "the sergeant (a guard)"), ("c2", "a spearman of the watch (a guard)"),
      ("c3", "a cloth merchant")], ["c1", "c2"]),
    ("keep swinging my sword",
     [("c1", "a merchant watching from his stall")], []),
]


def victim_messages(span: str, words: str, people) -> list[dict]:
    system = ("In a role-playing game the player's character attacks somebody. Here are the "
              "people standing nearby, each with a ref. Answer one question: which of them "
              "could the player's words mean? Everyone the words could fit — all of them "
              "for 'the closest person', 'someone', 'anyone' or a rampage; only those who "
              "fit a description ('a civilian' is anybody who is not a guard or soldier); "
              "the one person a name or a description picks out; nobody ([]) when nobody "
              "here fits the words.")
    out = [{"role": "system", "content": system}]

    def ask(deed, here):
        listed = "\n".join(f"{ref}: {label}" for ref, label in here)
        return f"People here:\n{listed}\nThe attack: {deed}"

    for deed, here, meant in _VICTIM_DEMOS:
        out.append({"role": "user", "content": ask(deed, here)})
        out.append({"role": "assistant", "content": json.dumps({"meant": meant})})
    # The span holds the target words; when the reader's span lost them, they are added.
    deed = span if (not words or words.lower() in str(span).lower()) else f"{span} ({words})"
    out.append({"role": "user", "content": ask(deed or words, people)})
    return out


def confirm_victims(span: str, words: str, people, *,
                    model: str | None = None) -> list[str] | None:
    """The refs among `people` ((ref, label) pairs, everyone standing here) that the attack
    in `span` could mean; [] for nobody here; None when the call fails (the caller then
    builds nothing, and the plan stands)."""
    from . import client
    from play import modelcfg

    refs = [str(r) for r, _ in people]
    if not refs:
        return []
    cfg = modelcfg.for_role("interpreter")
    if not cfg.get("model"):
        cfg = modelcfg.for_role("narrator")
    schema = {"type": "object",
              "properties": {"meant": {"type": "array",
                                       "items": {"type": "string", "enum": refs}}},
              "required": ["meant"]}
    try:
        reply = client.chat(victim_messages(span, words, people), model or cfg["model"],
                            cfg["host"], as_json=True, think=False, temperature=0.0,
                            num_predict=20 + 8 * len(refs),
                            provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""), schema=schema)
        got = (reply.json() or {}).get("meant")
    except Exception:  # noqa: BLE001 — a failed question builds nothing
        return None
    if not isinstance(got, list):
        return None
    # Checked in code, whatever the sampler enforced: a ref that is not here is no answer.
    return list(dict.fromkeys(str(r) for r in got if str(r) in refs))


# --- in the turn ---------------------------------------------------------------------
#
# First integration (2026-09-27), additive by design: the research's advice was to keep
# the fast word-detectors as a second opinion (Rasa's pattern) and to retire each one
# only on a measured comparison. So the reading is (1) shown to the planner as fact, (2)
# joined to the ops the schema requires, (3) handed to the readers that need a slot
# (who is sought, what is bought, whose house), with the regex as the fallback, and (4)
# logged beside the detectors' opinion so each disagreement is on the record.
_READINGS: dict[str, dict] = {}


def _key(text: str) -> str:
    return " ".join(str(text or "").split()).lower()


def remember(text: str, frame: dict | None) -> None:
    """This turn's reading of this sentence, for the readers that ask later in the turn."""
    if len(_READINGS) > 64:
        _READINGS.clear()
    if frame is not None:
        _READINGS[_key(text)] = frame


def reading_of(text: str) -> dict | None:
    return _READINGS.get(_key(text))


# A reading made before the planner was asked, handed on to it once: the turn budget
# (play/views.py `_within_the_budget`) reads the whole line to find where the turn ends,
# and the planner is then handed that reading — cut to the deeds done now — instead of
# asking the reader a second time. Taken once and gone, so it never outlives its turn.
_HANDED: dict[str, dict] = {}


def hand_on(text: str, frame: dict | None) -> None:
    _HANDED.clear()
    if frame is not None:
        _HANDED[_key(text)] = frame


def handed(text: str) -> dict | None:
    """The reading handed on for this sentence, taken (a second ask answers None)."""
    return _HANDED.pop(_key(text), None)


def _road_to(phrase, scene) -> bool:
    """Whether the phrase names a settlement a road from here reaches — the world's own
    legs (`journey.legs_from`, `journey.find`), never the words' meaning."""
    from rules import journey, residency

    world = residency._world(None)
    if scene is None or world is None or not str(phrase or "").strip():
        return False
    legs = journey.legs_from(world, str(getattr(scene, "location_id", "") or ""))
    want = " ".join(str(phrase).split()).lower().removeprefix("the ")
    return any(leg.to_name.lower() == want or leg.to_id == phrase for leg in legs)


def _board_square(a: dict, scene) -> bool:
    """Marks a `go` whose words name a square of this room's board (`square`) — the
    printed coordinate, read by code (`fixtures.square_said`)."""
    from rules import fixtures

    words = f"{a.get('place') or ''} {a.get('span') or ''}".upper()
    sq = fixtures.square_said(getattr(scene, "grid", None), words)
    if sq is not None:
        a["square"] = fixtures.square_name(sq)
    return sq is not None


def ops_for(frame: dict | None, scene=None, places=()) -> list[str]:
    """The ops the reading commits the turn to, where the reading grounds.

    Only the acts whose op cannot go wrong for want of a guess: a `go` to a place this
    town really has (the model still names it, from the brief's list); the house calls
    and break-ins; sleep; a wait with a time; an insult; words said. Buying opens the
    counter and is not an op; a fight's attacks are the fight schema's already."""
    from rules import places as places_mod

    ops: list[str] = []
    here = str(getattr(scene, "at", "") or "")

    def add(op):
        if op not in ops:
            ops.append(op)

    for a in (frame or {}).get("actions") or []:
        act = a.get("act")
        # A plan, a purpose or a question owes no op this turn (`COMMITS`): "I head for
        # the stables to ask about a horse" walks, and the asking is the next turn's.
        if not acting(a):
            continue
        if act == "cast" and scene is not None:
            # Where the spell goes, grounded here once: the cast's object, target or place
            # that is not the spell's own name, read by the same reader a typed and an
            # attached cast share (`areas.aim_from_words`). Kept on the action, so the
            # planner is shown it as fact (`brief_lines`) and the turn log records what
            # the words aimed at. No op is added: the cast is declared by its spell's
            # name (`judgement.inject_cast`), which the reading does not know.
            aim = cast_aim(frame, scene, a)
            if aim:
                a["aim"] = aim
        if act == "go" and _board_square(a, scene):
            # "I walk over to L9": a square of this room's board, which the table walks
            # (`acts_to_ops._to_the_square`). Marked so the brief says so and no travel
            # is owed. Measured live 2026-11-12: read `go: L9`, the plan's first attempt
            # was a travel to 'L9' and the schema refused it.
            pass
        elif act == "go" and a.get("place") and _road_to(a["place"], scene):
            # A town the roads from here reach, named whole: the journey, whatever verb the
            # reader filed it under. Asked before the town's own places, whose finder takes
            # "Kalixiri" for "the road to Kalixiri". Measured live 2026-10-27: "I give the
            # word and set out with the caravan for Kalixiri" was read `go: Kalixiri`, and
            # the plan walked the party to the road head it already stood on ("You are
            # already at the road to Kalixiri").
            add("journey")
        elif act == "go" and a.get("place"):
            p = places_mod.find(places, a["place"]) if places else None
            if p is None and scene is not None:
                # A person standing here, named where a place goes: "I go back to the
                # guild clerk" is read `go: the guild clerk`, which no place is called.
                # Marked as a seek of somebody here is (below), so it licenses no walk
                # (`supported`). Measured live 2026-10-27: the line kept a detector's
                # travel, the plan wrote a walk to the market the party stood in seven
                # times, the engine refused it seven times ("the guild clerk (c3) is HERE
                # … this travel would leave the guild clerk behind"), and the turn
                # degraded to narration with the player's offer to work lost.
                from rules import scope as scope_mod

                ref = scope_mod.in_the_room(scene, str(a["place"]))
                person = (getattr(scene, "actors", {}) or {}).get(ref)
                if person is not None and not getattr(person, "is_pc", False):
                    a["here"] = ref
            if p is not None and p.id != here:
                add("travel")
            elif p is None and _outward(a["place"]) and _has_outside(places):
                # "the nearest crossroads", "the path away from town": a phrase no place
                # here is called, which names the ground outside (Bobby, turns 6 and 7).
                # The travel is owed; `travel_choices` holds it to the ring's names.
                add("travel")
        elif act == "leave" and _leaving(a, scene, places):
            # Bobby's turn 5: `leave: outside it` mapped to no op at all, and the plan
            # took the nearest listed place — the way in, INSIDE the village
            # (docs/playtest-2026-09-28.md, 16.1). Leaving is a move.
            add("travel")
        elif act == "journey":
            add("journey")
        elif act in ("call_on", "break_in", "rest"):
            add(act)
        elif act == "wait" and (a.get("time") or a.get("until") in DAY_PARTS):
            add("advance_time")
        elif act == "insult":
            add("provoke")
        elif act == "talk" and a.get("says"):
            add("say")
        elif act == "seek" and a.get("target") and scene is not None:
            # Somebody sought who is HERE (item 8, 2026-09-30: "I aprouch the clockwork
            # Spy" planned a travel to the gate and left the Spy behind). Kept on the
            # action, so `supported` does not let this seek stand behind a travel.
            from rules import scope as scope_mod

            ref = scope_mod.in_the_room(scene, str(a["target"]))
            person = (getattr(scene, "actors", {}) or {}).get(ref)
            if person is not None and not getattr(person, "is_pc", False):
                a["here"] = ref
    return ops


def until_words(action: dict | None) -> str:
    """The words a wait or a sleep runs until, for the clock's numbers table
    (`timewords.minutes_until`): "until morning" when the reader named a time of day
    (`UNTILS`), the time slot's own words when it named an hour or nothing (an old frame),
    and "" for a length or no time at all. Structure only — the reader's enum and slot."""
    if not isinstance(action, dict):
        return ""
    until = str(action.get("until") or "")
    if until in DAY_PARTS:
        return f"until {until}"
    if until in ("a while", "none"):
        return ""
    return str(action.get("time") or "").strip()


def until_minutes(action: dict | None, clock: int) -> int | None:
    """Minutes from `clock` to the time a wait or a sleep runs until, or None when the
    reading names no time of day (`until_words`). Read against the clock by the one table
    the sleep door reads (`timewords.minutes_until`), so "till tomorrow" waits to the next
    morning — not a day of twenty-four hours."""
    from rules import timewords

    words = until_words(action)
    return timewords.minutes_until(words, clock) if words else None


def spell_named(scene, words) -> object | None:
    """The spell the player's caster can reach whose name the words hold, or None — read
    by `judgement.spell_in_words` against the whole catalogue, word-bounded and longest
    first, so "cure light wounds" is Cure Light Wounds (and None for a wizard who cannot
    reach it), never Light (item 4, 2026-09-30: the substring match here and in
    `inject_cast` were the same rule twice). Asked of the book, the prepared list and the
    class's own list, as `judgement.inject_cast` asks."""
    from rules import casting, spells as spells_mod

    from . import judgement

    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    said = " ".join(str(words or "").lower().split())
    if pc is None or not said or not casting.is_caster(pc):
        return None
    ids = [sp.id for lvl in casting.known_spells(
        pc, up_to=casting.highest_spell_level(pc)).values() for sp in lvl]
    ids += [s for s in (getattr(pc, "prepared", {}) or {}) if s not in ids]
    chosen = judgement._reachable_by_name(judgement.spell_in_words(said), ids)
    if not chosen:
        return None
    try:
        return spells_mod.get(chosen)
    except KeyError:
        return None


def cast_aim(frame: dict | None, scene, action: dict | None = None,
             spell=None) -> str | None:
    """Where the reading's cast is aimed, as an aim (`areas.AIM_PATTERN`), or None.

    Measured 2026-09-28 (docs/playtest-2026-09-28.md 21.2): "I cast burning hands into the
    tree tops" was read `cast, object: burning hands, target: the tree tops` — the
    treetops a *target*, as if a creature — and nothing turned that phrase into anything
    a cast could be pointed at. A cast act's target, place and object that is not the
    spell's own name are each grounded by `areas.aim_from_words` (a person here → `ref:`,
    a thing or a feature → `object:`, "above my head" → `dir:up`), target first: it is the
    words about WHO or WHAT. The spell is the one the action names when the caster can
    reach it, so a direction is not offered to a burst.

    `action` is one cast action of the frame; the first cast action when None."""
    from rules import areas

    if scene is None or not frame:
        return None
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None:
        return None
    acts = [action] if action is not None else [
        a for a in frame.get("actions") or [] if isinstance(a, dict) and a.get("act") == "cast"]
    for a in acts:
        if not isinstance(a, dict) or a.get("act") != "cast":
            continue
        chosen = spell
        if chosen is None:
            for slot in ("object", "target", "place"):
                chosen = spell_named(scene, a.get(slot))
                if chosen is not None:
                    break
        own = " ".join(str(getattr(chosen, "name", "") or "").lower().split())
        for slot in ("target", "place", "object"):
            phrase = " ".join(str(a.get(slot) or "").split())
            if not phrase or (own and own in phrase.lower()):
                continue
            aim = areas.aim_from_words(scene, pc.ref, phrase, chosen)
            if aim:
                return aim
    return None


def travel_choices(frame: dict | None, scene, places, location) -> tuple[str, ...]:
    """The place names a declared travel may choose among — the `places` enum of
    `prompts.turn_schema`, so the planner walks to a place that exists and invents none.

    Every place here but the one the party stands in — unless the reading says the
    party is LEAVING (Lane B, docs/design-b-space.md 16.1):

    - leaving the settlement ("I leave the village", "the path away from town"): the
      ring's names only — the outskirts, the fields, the roads out. The enum is enforced
      by the sampler (6 of 6, memory `ollama-schema-enforcement`), so the plan cannot
      walk to the way in and call it leaving, which is what Bobby's turn 5 did;
    - leaving a building ("I leave the tavern"): its exits under the sky only.

    With no ring (no world to build one from) the answer is today's.
    """
    here = getattr(scene, "at", None)
    everything = tuple(p.name for p in places if p.id != here)
    going = _going(frame, scene, places, location)
    if going == "settlement":
        from rules import places as places_mod

        ring = tuple(p.name for p in places if places_mod.is_ring(p.id) and p.id != here
                     and "along-the-road-to-" not in p.id)
        return ring or everything
    if going == "building":
        from rules import places as places_mod

        by_id = {p.id: p for p in places}
        cur = by_id.get(here)
        street = tuple(by_id[x].name for x in (cur.exits if cur else ())
                       if x in by_id and not places_mod.is_indoors(
                           x, by_id[x].terrain, by_id[x].shape))
        return street or everything
    nearby = _sought_nearby(frame, here, places)
    if nearby:
        return nearby
    return everything


# The acts that name where the party goes: with one of these done, the words chose the
# place (the travel's own enum and refusals hold it). Without, a travel serves a search.
_MOVING_ACTS = frozenset({"go", "leave", "journey", "seek", "call_on", "follow",
                          "break_in"})


def _sought_nearby(frame: dict | None, here, places) -> tuple[str, ...]:
    """A place LOOKED FOR, with no place named to go to, is looked for close by: the places
    one door from here, inside the settlement — never the ground outside its walls.

    Measured live 2026-10-09 (gemma-4-12B, the fight script, after the tavern brawl): "I
    find somewhere quiet and sit down" was read `search, object: somewhere quiet` and
    `wait`; the plan, offered every place in town, chose the outskirts, and the party
    walked half an hour through the guildhall, the market and the gate out into the desert.
    A search names no place; what it may reach is the engine's to bound, by the map's own
    exits (`Place.exits`) — the sampler then cannot leave them. "" (no bound) when the
    words did name a move, or nothing is next door."""
    from rules import places as places_mod

    acting_acts = [a for a in (frame or {}).get("actions") or [] if acting(a)]
    if not any(a.get("act") == "search" for a in acting_acts) or any(
            a.get("act") in _MOVING_ACTS for a in acting_acts):
        return ()
    by_id = {p.id: p for p in places or ()}
    cur = by_id.get(here)
    if cur is None:
        return ()
    near = [by_id[x] for x in (cur.exits or ()) if x in by_id]
    return tuple(p.name for p in near
                 if p.id != here and not places_mod.is_ring(p.id)
                 and places_mod.setting_of(p.id) != "outside")


# What a player says when the place they are leaving is the settlement itself, or the
# ground they want is outside it. Matched as whole words in the slot.
_SETTLEMENT_WORDS = frozenset({"town", "village", "city", "settlement", "outside", "out",
                               "it", "here", "walls", "hamlet", "place"})
_OUTWARD_WORDS = frozenset({"road", "roads", "path", "track", "trail", "crossroads",
                            "crossroad", "fields", "field", "outskirts", "signpost",
                            "milestone", "countryside", "wilds", "wilderness"})
_WORDS_RE = re.compile(r"[a-z']+")


def _outward(phrase) -> bool:
    words = set(_WORDS_RE.findall(str(phrase or "").lower()))
    return bool(words & _OUTWARD_WORDS) or "out of town" in str(phrase or "").lower()


def _has_outside(places) -> bool:
    from rules import places as places_mod

    return any(places_mod.is_ring(p.id) for p in places or ())


def _leaving(action: dict, scene, places, location=None) -> str:
    """"settlement", "building" or "" for one `leave` action of the reading."""
    from rules import places as places_mod

    here_id = str(getattr(scene, "at", "") or "")
    if places_mod.setting_of(here_id) == "outside":
        return ""                      # already out: "leave" names nowhere to go
    slot = str(action.get("place") or "").strip().lower()
    words = set(_WORDS_RE.findall(slot))
    name = str(getattr(location, "name", "") or "").lower()
    by_id = {p.id: p for p in places or ()}
    cur = by_id.get(here_id)
    named = places_mod.find(places, slot) if slot else None
    indoors = cur is not None and places_mod.is_indoors(cur.id, cur.terrain, cur.shape)
    # Asked of the place's own id when the list does not carry it (the floorplan answers
    # either way, `places.is_indoors`).
    roofed = indoors if cur is not None else bool(here_id) and places_mod.is_indoors(here_id)
    if not slot and here_id and not roofed:
        # A bare "walk off" under the open sky names nothing to leave: not a building
        # (there is none around them) and not the settlement (nobody said so). Measured
        # 2026-10-08 (the deeds lane, local model): "I take another apple from the fruit
        # seller and walk off" read `leave` with no place, this answered "settlement",
        # the travel was owed with only the roads out to choose from, and the player
        # walked out of Vormoor onto the road to Scrapden over an apple. Inform's EXIT
        # outside any container answers "But you aren't in anything at the moment" —
        # leaving needs a thing to leave. No walk is owed; the plan may still choose one.
        return ""
    if (not slot or words & _SETTLEMENT_WORDS or (name and name in slot)
            or (location is not None and places_mod.scale_of(location) in words)):
        if indoors and slot and (named is not None and named.id == here_id):
            return "building"
        if indoors and not slot:
            return "building"
        return "settlement" if _has_outside(places) or not indoors else "building"
    if named is not None and named.id == here_id and indoors:
        return "building"
    return ""


def _going(frame, scene, places, location) -> str:
    """Whether the reading leaves the settlement, a building, or neither."""
    for a in (frame or {}).get("actions") or []:
        if a.get("act") == "leave":
            got = _leaving(a, scene, places, location)
            if got:
                return got
        if a.get("act") == "go" and a.get("place") and _outward(a["place"]) \
                and _has_outside(places):
            from rules import places as places_mod

            if places_mod.find(places, a["place"]) is None:
                return "settlement"
    return ""


# Which acts of the reading can stand behind an op a word-detector requires. An op with
# no row here is dropped (`supported`), unless it is in `UNJUDGED`.
#
# Until 2026-11-08 an op with no row was kept, unjudged (ponytail audit #7): `take_off`,
# `found`, `venture` and `check` survived a reading of nothing but `talk`, and the take-off
# regex matches "I promise I'll never take off my armour". Their rows, below the first
# block: taking armour off is no act of its own in the reading's list, so whatever deed
# a small model files it under (`use`, `drop`, `take` for the verb, or `other`); a base is
# made where one goes (`go`, the heard place's found and travel, `acts_to_ops.apply`),
# settles (`rest`, "make camp") or declares (`claim`, `other`); new ground is entered by
# going, searching, sneaking or climbing into it; and a check is any deed a skill rolls
# for, speech included (persuade, bluff, threaten are `talk`, `request`, `insult`).
_OP_NEEDS = {
    "travel": {"go", "leave", "journey", "search", "seek", "call_on"},
    "journey": {"journey"}, "introduce": {"seek", "talk", "call_on", "request"},
    "say": {"talk", "insult", "request"}, "provoke": {"insult"},
    "give": {"give", "take", "drop"},
    "sell": {"sell"},
    "rest": {"rest"}, "advance_time": {"wait", "rest"}, "call_on": {"call_on"},
    "break_in": {"break_in"}, "forage": {"gather"}, "prospect": {"gather"},
    "gather": {"gather"},
    "loot": {"take", "steal", "loot"}, "cast": {"cast"},
    "use_item": {"consume", "use"}, "drink": {"consume"}, "eat": {"consume"},
    "taste": {"consume", "use"},
    "take_off": {"use", "drop", "take", "other"},
    "found": {"go", "rest", "claim", "other"},
    "venture": {"go", "leave", "journey", "search", "seek", "stealth", "athletics",
                "follow"},
    "check": {"stealth", "steal", "take", "break_in", "use", "athletics", "exert", "go",
              "escape", "talk", "request", "insult", "claim", "search", "look", "track",
              "follow", "other"},
}

# The declarers that read a CLOSED vocabulary, not English: an ability's name against
# the character's own sheet. Their op is the reading's to override only where a row says
# so (a spell's `cast` and a jar's `use_item` have rows above). The audit's short list.
UNJUDGED = frozenset({"use_ability"})


def supported(ops: list[str], frame: dict | None) -> tuple[list[str], list[str]]:
    """(the detectors' ops the reading supports, the ones it does not). Measured live
    2026-09-27: a detector required `give` for "I buy a dragon's egg", which the reading
    read — rightly — as a purchase. On the labelled set the reading's acts score F1 0.91
    against the detectors' 0.47, so where the two disagree the reading decides, and the
    overruled op is logged.

    A `seek` of somebody HERE (`ops_for` marks it `here`) licenses no travel: you do not
    walk to another place to find the person beside you. Measured on the 2026-09-30 save
    (turn_log row 82). Inform's GO TO takes only a room for the same reason (Emily
    Short's *Approaches*, "go to [any visited room]")."""
    # Only what is done or tried now stands behind an op (`COMMITS`).
    actions = [a for a in (frame or {}).get("actions") or [] if acting(a)]
    acts = {a.get("act") for a in actions}
    # And a `go` whose place is a person here (`ops_for` marks that too): "I go back to
    # the guild clerk" with the clerk at the table. Or a square of the board ("go to L9").
    elsewhere = {a.get("act") for a in actions
                 if not (a.get("act") in ("seek", "go") and (a.get("here") or a.get("square")))}
    kept, dropped = [], []
    # A body searched and nothing else (`acts_to_ops.body_search_only`): the check the
    # check detector reads off "search" is not the player's — the loot is the search, and
    # rolls nothing (the narration diagnosis bench, 2026-11-04).
    looting_only = "loot" in acts and not acts & {"gather", "search", "look", "track"}
    for op in ops:
        if op == "check" and looting_only:
            dropped.append(op)
            continue
        need = _OP_NEEDS.get(op)
        have = elsewhere if op == "travel" else acts
        backed = op in UNJUDGED if need is None else bool(have & need)
        (kept if backed else dropped).append(op)
    return kept, dropped


# The acts under which the player can come away holding something. One set for both
# doors that judge a give to the player: `drop_unread_gifts` and the act→op table's
# overrule (`acts_to_ops.apply`; until 2026-10-03 the other door was the retired
# `judgement.inject_goods`).
GETTING_ACTS = frozenset({"give", "take", "buy", "steal", "gather", "sell", "loot",
                          "harvest"})


def gets_nothing(frame: dict | None) -> bool:
    """Whether a reading exists and none of its acts can leave the player holding
    anything. False when there is no reading to judge by."""
    if not frame or frame.get("error"):
        return False
    return not ({a.get("act") for a in frame.get("actions") or [] if acting(a)}
                & GETTING_ACTS)


# And the other direction: the acts under which the player can part with something —
# handing it over, dropping it, paying, selling. Measured 2026-10-03 on the market-talk
# save: "I give a friendly wink and say …" was read as `other` + `talk`, the reading
# overruled the detector's `give`, and `judgement.inject_goods` (retired since) planned
# one anyway — "Kesst Vayr has no friendly wink to give", and the ledger kept "handed
# something to Kesst Vayr". The rule that already held for gains holds for hand-overs;
# `drop` joined with the act itself.
PARTING_ACTS = frozenset({"give", "sell", "buy", "drop"})


def drop_unread_gifts(raw, frame: dict | None) -> tuple[list, list]:
    """(the plan's intents, the gives dropped). A `give` to the player that no act of the
    reading asked for is the model conjuring: goods are open (rules/goods.py), so a give
    makes whatever it names. Measured live 2026-09-27 on the fight script, both with and
    without the interpreter: "Kesst Vayr takes fight", "takes table", "takes c3" — for
    "I pick a fight", "I throw him over a table". Only with a reading to judge by, and
    only gives to the player; a give the player makes to somebody else is left alone."""
    if not isinstance(raw, list) or not frame or frame.get("error"):
        return (raw if isinstance(raw, list) else []), []
    if not gets_nothing(frame):
        return raw, []
    kept, dropped = [], []
    for r in raw:
        p = (r.get("params") or {}) if isinstance(r, dict) else {}
        to = str(p.get("to") or "").lower()
        if (isinstance(r, dict) and str(r.get("op", "")).lower() == "give"
                and (to in ("pc", "you", "player") or not p.get("from_") and not to)):
            dropped.append(str(p.get("item") or ""))
            continue
        kept.append(r)
    return kept, dropped


_SPEECH_ACTS = frozenset({"talk", "insult", "request"})


def words_said(frame: dict | None, sentence: str) -> str:
    """The whole of what the player's character says now, as words of the sentence: the
    first speech act done or tried with words (`says`), run on through the speech acts
    whose spans follow it in the sentence with nothing between but a comma or space, to
    nobody else — reported speech from the first one's verb, a quotation as quoted, to
    the end of the last.

    Round 2, 2026-11-05: "I invite the innkeeper up to my room to share my bed tonight" was
    read as a talk saying "up to my room" and an intended talk "to share my bed tonight",
    and only "up to my room" reached the say (7 of 7 runs). The say slot then told the
    invitation as asking for a room ("You turn to the gnome and ask for a room for the
    night"), the deed backstop put the line on the page as well, and the invitation was
    told twice. Spans and their places in the sentence, read in code; no English is read.
    "" when nothing is said."""
    if not isinstance(frame, dict) or not sentence:
        return ""
    acts = [a for a in frame.get("actions") or [] if isinstance(a, dict)]
    low = str(sentence)
    for i, a in enumerate(acts):
        says = str(a.get("says") or "").strip()
        if a.get("act") not in _SPEECH_ACTS or not acting(a) or not says:
            continue
        span = str(a.get("span") or "")
        at = low.find(span) if span else -1
        start = low.find(says, at if at >= 0 else 0)
        if at < 0 or start < 0:
            return says
        end, who = at + len(span), a.get("target")
        for b in acts[i + 1:]:
            nxt = str(b.get("span") or "")
            if b.get("act") not in _SPEECH_ACTS or not nxt:
                break
            if b.get("target") and who and b.get("target") != who:
                break
            k = low.find(nxt, end)
            if k < 0 or low[end:k].strip(" ,") != "":
                break
            end = k + len(nxt)
        # Reported speech is said whole, from its own verb: the live bench of round 2
        # carried "up to my room to share my bed tonight" (read as one talk, or run on from
        # two), and the say slot wrote "you request a room to share your bed" on 5 of 5
        # runs — without "invite" the words read as a room asked for. The verb is the
        # player's own word for what the speaking does (invite, swear, beg). Quoted words
        # are the quotation alone, as typed.
        from . import speech

        if any(qa <= start < qb for qa, qb in speech.spans(low)):
            return says
        return " ".join(low[at:end].split()).strip(" ,")
    return ""


def brief_lines(frame: dict | None) -> str:
    """What the planner is told the player's words say, in order, as fact."""
    if not frame:
        return ""
    if frame.get("question") and not frame.get("actions"):
        return ("THE PLAYER'S WORDS, READ (fact): a question asked of the game, not "
                "something the character does. Answer it; the character does nothing.")
    rows = []
    for n, a in enumerate(frame.get("actions") or [], 1):
        slots = ", ".join(f"{s}: {a[s]}" for s in (*SLOTS, "aim", "asks_for") if a.get(s)
                          and not (s == "place" and a.get("square")))
        if a.get("square"):
            # A board square is no place of the town: the engine walks it, the plan
            # writes no travel and no found for it.
            slots = ", ".join(filter(None, [slots, f"to square {a['square']} of this room's "
                                            "board (the engine walks it: no travel, no found)"]))
        # How far it is done, said: a plan or a question is context for the plan, never
        # an op of its own (`COMMITS`).
        how = {"tried": " (TRIED now: the outcome is the dice's or the other person's)",
               "intended": " (INTENDED, not done this turn: no op for it)",
               "asked": " (ASKED ABOUT, not done: no op for it)"}.get(
                   str(a.get("commit") or "done"), "")
        rows.append(f"{n}. {a['act']}" + (f" — {slots}" if slots else "") + how)
    out = ""
    if rows:
        out = ("THE PLAYER'S WORDS, READ (fact, in the order they are done; the plan "
               "carries each one done or tried now): " + " ".join(rows))
    if frame.get("claims"):
        out += (" THE PLAYER CLAIMS, and it is not so unless the engine makes it so: "
                + "; ".join(frame["claims"]) + ".")
    return out


_BARE_PRONOUN = {"him", "her", "them", "he", "she", "they", "it", "his", "their", "its",
                 "me", "you", "us"}


def target_of(frame: dict | None, acts=("seek", "call_on", "talk", "request", "give",
                                         "buy", "follow")) -> str:
    """The person the sentence goes looking for or addresses, without its article —
    the reading's answer to `judgement.person_sought`. "" when it names nobody."""
    for a in (frame or {}).get("actions") or []:
        t = str(a.get("target") or "").strip()
        if a.get("act") in acts and t and t.lower() not in _BARE_PRONOUN:
            return re.sub(r"^(?:the|a|an|my|some)\s+", "", t, flags=re.I)
    return ""


# --- who is asked, and who is only asked ABOUT ---------------------------------------------
#
# Inform's rule for ASK … ABOUT (Recipe Book §6.2; the I7 Handbook): the person token must
# be in scope, the topic token reaches out of it. `judgement.inject_company` learned it for
# the spawn door (item 5.1 of the 2026-09-28 playtest). Measured live 2026-09-29 on G3's
# market-seek turn 1, the same sentence came through the OTHER door: "I ask the nearest
# person about the girl who sells herbs in the market." read `talk, target: the nearest
# person, says: about the girl who sells herbs in the market` — right — and the plan still
# wrote `introduce who="herbalist vendor"` and a `say` TO her. The girl is the topic.
_TOPIC_OPENS = re.compile(r"^(?:about|regarding|concerning|after|of)\s+(.+)$", re.I)
_ASKED_ABOUT = re.compile(
    r"\b(?:ask|asks|asking|question|questions|enquire|enquires|inquire|inquires|"
    r"talk|talks|speak|speaks|chat|chats|tell|tells)\b[^.!?;\"“]*?"
    r"\b(?:about|regarding|concerning|after)\s+([^.!?;\"“]+)", re.I)
_NOT_A_DESCRIBING_WORD = frozenset({
    "the", "a", "an", "some", "any", "who", "that", "which", "in", "at", "on", "of", "by",
    "to", "for", "from", "with", "and", "or", "is", "are", "person", "people", "one",
    "someone", "somebody", "anyone", "anybody", "folk", "nearest", "closest", "nearby",
    "next", "here", "there", "me", "my", "him", "her", "them", "his", "their",
})


def topics(frame: dict | None, sentence: str = "") -> list[str]:
    """The phrases the sentence asks ABOUT: a `talk` act's "about …" `says` slot, the part
    of its span after "about", and — with no reading — the sentence's own "ask … about …"."""
    out: list[str] = []
    for a in (frame or {}).get("actions") or []:
        if a.get("act") not in ("talk", "insult", "seek"):
            continue
        for slot in ("says", "span"):
            said = " ".join(str(a.get(slot) or "").split())
            m = _TOPIC_OPENS.match(said) if slot == "says" else _ASKED_ABOUT.search(said)
            if m and m.group(1).strip() not in out:
                out.append(m.group(1).strip())
    if not out:
        from .speech import blanked

        for m in _ASKED_ABOUT.finditer(blanked(str(sentence or ""))):
            topic = " ".join(m.group(1).split()).strip()
            if topic and topic not in out:
                out.append(topic)
    return out


def addressee(frame: dict | None, sentence: str = "") -> str:
    """Who a `talk` act speaks to, in the player's words — "the nearest person"; "" when
    the reading names nobody (the regex's answer is `judgement.person_sought`'s)."""
    for a in (frame or {}).get("actions") or []:
        if a.get("act") in ("talk", "insult") and str(a.get("target") or "").strip():
            return " ".join(str(a["target"]).split())
    return ""


def _describing(phrase: str) -> set[str]:
    from rules import population

    words = [w for w in re.findall(r"[a-z][a-z'-]+", str(phrase or "").lower())
             if w not in _NOT_A_DESCRIBING_WORD]
    return {population._stem(w) for w in words} | set(population._tokens(" ".join(words)))


def _shares(a: set[str], b: set[str]) -> bool:
    """A word in common: the same stem or synonym token ("vendor" and "sells" are both
    `sell`), or one stem the start of the other ("herbalist", "herbs")."""
    if a & b:
        return True
    return any(len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x))
               for x in a for y in b if not x.startswith("work:") and not y.startswith("work:"))


def in_topic(phrase: str, topic_list, addressed: str = "") -> bool:
    """Whether a person phrase is somebody the sentence only asks ABOUT: it shares a
    describing word with a topic and none with the person addressed."""
    mine = _describing(phrase)
    if not mine or not topic_list:
        return False
    if addressed and _shares(mine, _describing(addressed)):
        return False
    return any(_shares(mine, _describing(t)) for t in topic_list)


def bought(frame: dict | None) -> str:
    for a in (frame or {}).get("actions") or []:
        if a.get("act") == "buy" and a.get("object"):
            return str(a["object"])
    return ""


def called(frame: dict | None) -> tuple[str, bool]:
    for a in (frame or {}).get("actions") or []:
        if a.get("act") == "call_on":
            return str(a.get("target") or "her"), True
    return "", False


def broken_into(frame: dict | None) -> tuple[str, str]:
    for a in (frame or {}).get("actions") or []:
        if a.get("act") == "break_in":
            who = str(a.get("target") or "")
            who = re.sub(r"(?:'s|s')?\s*(?:front\s+)?(?:door|house|home|lock)\b.*$", "", who,
                         flags=re.I).strip()
            if who.lower() in ("the", "a", "an", ""):
                who = ""
            how = "pick" if re.search(r"\block|pick", str(a.get("object") or ""), re.I) \
                else "force"
            return who, how
    return "", ""
