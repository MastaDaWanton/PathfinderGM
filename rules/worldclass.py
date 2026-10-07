"""World classes: progression that runs alongside a character class, not instead of it.

An Herbalist is not a Fighter's alternative — a Fighter *is* an Herbalist, if they forage.
A world class grants no BAB, no saves, no hit dice and no class skills; it gates a set of
methods and the tier of material they may be used on, and it levels on what the character
does rather than on their experience total.

That is why none of this lives in `tables.CLASSES`. A world class shares no fields with a
PF1e class and advances on a different clock, and putting it there would have meant every
consumer of `CLASSES` learning to ignore half its entries.

The framework is generic on purpose: Herbalist is the first track, and blacksmithing,
leatherworking and alchemy are meant to be three more files rather than three more code
paths.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Material tiers, in order. A track names them however it likes ("Common / Mundane") and
# the position in this list is what the rules compare.
TIERS = ("common", "uncommon", "rare", "exotic", "legendary")

TIER_ALIASES = {
    "mundane": "common", "volatile": "uncommon", "magical": "rare",
    "planar": "exotic", "mythic": "legendary",
}


def tier_rank(name: str) -> int:
    """`Rare / Magical` -> 3. Either half of a slashed pair is accepted, because the
    source documents write both and a recipe will cite whichever one reads better."""
    for part in str(name or "").lower().replace("/", " ").split():
        part = TIER_ALIASES.get(part, part)
        if part in TIERS:
            return TIERS.index(part) + 1
    return 1


# --- how mastery is earned -----------------------------------------------------------------

# Awards as authored. Two clarifications the source left open, both settled the way that
# matches its stated intent rather than the way that reads most literally:
#
#   `per_extra_stage` is per stage *beyond the first*, because the award is called
#   "Multi-Stage Crafting Chain" and a single grind is not a chain. Counting the first
#   stage would hand +2 to every craft in the game and quietly re-inflate the curve.
MP_AWARDS = {
    "first_time": 3,
    "repeat": 1,
    "risky_harvest": 2,
    "per_extra_stage": 2,
    "mishap": 1,
}

# "Once an Herbalist reaches Level 3, Level 1 recipes no longer grant Mastery Points."
# Generalised to a gap so it keeps working at 4 and 5 without a new special case each
# time: anything this far below your level teaches you nothing.
TRIVIAL_GAP = 2

# The stated design purpose of the award table is to stop players "spamming 100 basic
# health potions". Diminishing returns alone do not, because they only start at level 3 —
# at level 1 a factory line of twenty-five teas is still a level. A recipe pays repeat
# mastery a few times and then it is a thing you know how to do.
#
# RETIRED for successes by the owner, 2026-10-05: "batch of 10 should pay 10". A batch of
# N is N single crafts, and every successful craft pays: ten crafts are ten crafts' work.
# The limit stood behind the batch and the singles alike, so a batch of 10 paid 3 and so
# did ten singles; lifting it for batches only would have paid batching more than the
# same work done by hand. Kept as a name for the history; no award reads it. The mishap
# limit below stays: failing on purpose with cheap ingredients is still not progress, and
# the ruling was about work that succeeded.
REPEAT_LIMIT = 3

# A failed craft teaches something the first time and nothing the fourth, for the same
# reason. Without a limit, deliberate failure on cheap ingredients is free progress.
MISHAP_LIMIT = 2


@dataclass
class Level:
    level: int
    tools: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    max_tier: str = "common"
    note: str = ""
    # The highest quality index work at this level can reach (0 Crude ... 4 Flawless),
    # for a track whose bench grades quality. None for a track that does not, so the
    # older world classes load unchanged (docs/herbalism-revamp-plan.md §4.3).
    ceiling: int | None = None


@dataclass
class Track:
    """One world class."""
    id: str
    name: str
    summary: str = ""
    levels: list[Level] = field(default_factory=list)
    # Mastery needed to reach level 2, 3, 4, 5.
    thresholds: list[int] = field(default_factory=list)
    # Levels that need something done as well as points paid.
    milestones: dict[int, str] = field(default_factory=dict)
    # What each of those deeds actually *is*, as {milestone: {"min_tier": ...}}. The
    # track has to say, because nothing else can: `milestones` names a deed and the
    # engine had no way to recognise one being done, so the bench never recorded any and
    # the milestone-locked level stayed locked whatever the character achieved.
    deeds: dict[str, dict] = field(default_factory=dict)
    grantable_at_creation: bool = True

    # The last level the track *writes down*. Levelling does not stop there: see
    # `to_next`. A track that wants a hard ceiling says so with `capped`.
    capped: bool = False

    # How the levels past the written table are priced and what they give, as the track
    # declares it: {"base": 50, "step": 10, "picks_per_level": 2, "perks": {...}}. Empty
    # for a track that prices its unwritten levels flat at `top_cost` and grants nothing
    # but the number. Declared in the JSON, never keyed on a track id here, so a second
    # track can adopt endless levels with no code change (docs/herbalism-revamp-plan.md
    # §4.2).
    endless: dict = field(default_factory=dict)

    # Everything else the track's JSON declares, as written: a bench's rule rows (the
    # Blacksmith's `bench` block, docs/blacksmithing-revamp-plan.md §7), method help, old
    # method names. Kept on the track rather than re-read from disk by each bench, so a
    # homebrew track that overrides the shipped one overrides its rules too, and the one
    # cache `tests/conftest.py` already clears covers it.
    data: dict = field(default_factory=dict)

    @property
    def perks(self) -> tuple[str, ...]:
        """The perks this track's endless levels offer, in the order its JSON lists them.

        The Herbalist offers potency, duration, quality and yield; the Blacksmith
        potency, hardening, quality and yield (plan §4.2). A track with no `endless.perks`
        falls back on the Herbalist's four, which is what every caller saw before the
        list was per track.
        """
        sizes = self.endless.get("perks") or {}
        return tuple(str(k) for k in sizes) or PERKS

    @property
    def max_level(self) -> int:
        return max((l.level for l in self.levels), default=1)

    @property
    def top_cost(self) -> int:
        """What a level costs once the written thresholds run out.

        Held flat at the last one rather than climbing: "dont increase the points
        required to level beyond 100". The unlocks stop at 5 because that is where the
        track's own table stops, and everything that scales with the level goes on
        scaling past it.
        """
        return self.thresholds[-1] if self.thresholds else 100

    def deed_done(self, *, tier: str, success: bool) -> str:
        """The milestone this craft satisfies, if it satisfies one.

        Only successes count, and only at or above the tier the deed names — the deed
        for Herbalist 5 is working legendary material, so an exotic elixir is not it
        however well it went.
        """
        if not success:
            return ""
        rank = tier_rank(tier)
        # Most demanding first, so a track that ever declares two deeds credits the
        # harder one rather than whichever the dict happened to yield first.
        earned = sorted(
            ((tier_rank(str(spec.get("min_tier", "legendary"))), name)
             for name, spec in self.deeds.items()),
            reverse=True,
        )
        return next((name for need, name in earned if rank >= need), "")

    def at(self, level: int) -> Level:
        # Only for reading the unlock table: a level past its end unlocks whatever the
        # last row did, and clamping *here* is what keeps that lookup in range without
        # capping the character.
        level = max(1, min(int(level), self.max_level))
        return next(l for l in self.levels if l.level == level)

    def unlocked_methods(self, level: int) -> list[str]:
        """Everything learned up to here — methods do not expire."""
        out: list[str] = []
        for l in sorted(self.levels, key=lambda x: x.level):
            if l.level <= level:
                out.extend(m for m in l.methods if m not in out)
        return out

    def unlocked_tools(self, level: int) -> list[str]:
        out: list[str] = []
        for l in sorted(self.levels, key=lambda x: x.level):
            if l.level <= level:
                out.extend(t for t in l.tools if t not in out)
        return out

    def to_next(self, level: int) -> int | None:
        """Mastery needed to leave this level. None only for a track that says it caps.

        Past the written table the cost is the last threshold, unchanged, unless the
        track declares `endless` pricing: then the first unwritten level costs `base`
        and each one after it `step` more, forever (the Herbalist's 50, 60, 70...). A
        crafter who has unlocked everything keeps levelling, and every number that reads
        the level — the potency a grind adds, a formula naming the track — keeps growing
        with it.
        """
        if self.capped and level >= self.max_level:
            return None
        if level - 1 < len(self.thresholds):
            return self.thresholds[level - 1]
        if self.endless:
            # Counted from the first level the written thresholds do not price, so a
            # track with two thresholds (to 2, to 3) charges `base` to leave level 3.
            past = max(0, int(level) - len(self.thresholds) - 1)
            return int(self.endless.get("base", self.top_cost)) + \
                int(self.endless.get("step", 0)) * past
        return self.top_cost


@dataclass
class Progress:
    """What one character has done in one track."""
    track: str
    level: int = 1
    mp: int = 0
    # recipe id -> times crafted, so novelty and repetition can be told apart.
    crafted: dict[str, int] = field(default_factory=dict)
    mishaps: dict[str, int] = field(default_factory=dict)
    milestones: list[str] = field(default_factory=list)
    # Endless-level perk picks, perk id -> times taken (docs/herbalism-revamp-plan.md
    # §4.2). Read live by the bench; never stored as effects.
    perks: dict[str, int] = field(default_factory=dict)
    # Which version of the track's rules this progress was last settled under. 0 is
    # "before the herbalism revamp"; the migration (§14) stamps it once.
    schema: int = 0

    def knows(self, recipe_id: str) -> bool:
        return recipe_id in self.crafted


# --- endless levels (herbalism revamp; contracts in docs/herbalism-contracts.md) -------
#
# Levels past a track's written table that pay out in perks rather than unlocks
# (docs/herbalism-revamp-plan.md §4.2-4.4). Everything a track varies — where the unlocks
# stop, how a level is priced, how many picks it gives, what each perk is worth, the
# quality ceiling per level — is read from the track's own JSON, so nothing here names a
# track. The signatures of `perk_picks_banked`, `ceiling_index` and `award_bonus` are the
# lead's contract with the other lanes and do not change without the lead.

# The Herbalist's perks, and the fallback for a track that names none. A track's own list
# is `Track.perks` (the Blacksmith swaps duration for hardening, plan §4.2).
PERKS = ("potency", "duration", "quality", "yield")
# Fallbacks for a progress whose track cannot be found (a homebrew track the user since
# removed). A known track answers from its own written table and `endless` block.
UNLOCK_LEVELS = 3
PICKS_PER_LEVEL = 2
# Quality ladder indices: 0 Crude, 1 Sound, 2 Fine, 3 Superior, 4 Flawless, 5 Flawless +1 ...
CEILING_BY_LEVEL = {1: 2, 2: 3, 3: 4}
QUALITY_NAMES = ("Crude", "Sound", "Fine", "Superior", "Flawless")

# Mastery from a bench step (§4.4, owner-accepted 2026-10-02). These replace the old
# "first time 3 / repeat 1" per recipe for a track whose bench works one step at a time:
# a chain is now several rolls, each paid on its own, so a per-chain award would count
# the same work twice.
STEP_MP = 1                 # each successful step, +1 per rarity band above common
QUALITY_MP = {3: 1, 4: 2}   # Superior +1; Flawless *or higher* +2 (index 4 and up)
FIRST_MP = 3                # a first: a property learned, a product type, a new herb
MANUAL_MP = 5               # an unread herbalism manual, once per manual
# Studying a material (an assay, a read, a teacher's lesson): 1 for each property it
# turns up, 0 when it finds nothing. Owner, 2026-10-06: "studying materials should give
# you 1 point and 0 if you dont find anything. I had made almost nothing and was level 5
# blacksmithing", then "1 for each property it finds is okay" — each revealed property
# had paid FIRST_MP (3), so one assay that turned up three properties paid 9.
STUDY_MP = 1

# The stamp `migrate_herbalist` writes. 0 is every save from before the revamp.
HERBALISM_SCHEMA = 2
# The stamp `migrate_blacksmith` writes (docs/blacksmithing-revamp-plan.md §14).
BLACKSMITH_SCHEMA = 2
# The stamp `migrate_enchanter` writes (docs/enchanting-revamp-plan.md §19).
ENCHANTER_SCHEMA = 2
# The stamp `migrate_alchemist` writes (docs/alchemy-revamp-plan.md §18, `alchemy_v2`).
ALCHEMIST_SCHEMA = 2


def quality_name(index: int) -> str:
    """0 Crude ... 4 Flawless, then "Flawless +1", "+2" without end. The server names
    tiers and the page never builds them (contracts §2), so this is the one copy."""
    i = max(0, int(index))
    top = len(QUALITY_NAMES) - 1
    return QUALITY_NAMES[i] if i <= top else f"{QUALITY_NAMES[top]} +{i - top}"


def _track_of(progress: Progress) -> Track | None:
    try:
        return get(progress.track)
    except KeyError:
        return None


def _perk_size(track: Track | None, perk: str) -> float:
    # The sizes live in the track's `endless.perks` so they tune in the JSON without a
    # code change (plan §16). A track without the block grants nothing from a perk.
    sizes = (track.endless.get("perks") or {}) if track is not None else {}
    return float(sizes.get(perk, 0))


def _banked(track: Track | None, progress: Progress) -> int:
    if track is None:
        start, per = UNLOCK_LEVELS, PICKS_PER_LEVEL
    elif not track.endless:
        # A track that never declared endless levels has no perks to pick. Before this
        # the scaffold counted picks for every track past level 3, so an Alchemist 6
        # would have been offered six Herbalist perks.
        return 0
    else:
        start = track.max_level
        per = int(track.endless.get("picks_per_level", PICKS_PER_LEVEL))
    earned = max(0, int(progress.level) - start) * per
    return max(0, earned - sum(int(n) for n in progress.perks.values()))


def _ceiling(track: Track | None, progress: Progress) -> int:
    base = track.at(progress.level).ceiling if track is not None else None
    if base is None:
        base = CEILING_BY_LEVEL.get(min(int(progress.level), max(CEILING_BY_LEVEL)), 2)
    step = _perk_size(track, "quality") if track is not None else 1
    return int(base + int(step) * int(progress.perks.get("quality", 0)))


def perk_picks_banked(progress: Progress) -> int:
    """Perk picks earned by endless levels and not yet spent.

    Counted, not stored: the level *is* the bank. Level 4 of a track whose unlocks stop
    at 3 has earned one pair, level 5 two, and whatever has been picked is subtracted.
    That is what lets the migration (§14) express "Herbalist 5 becomes 3 plus two
    pick-pairs" by leaving the level alone.
    """
    return _banked(_track_of(progress), progress)


def ceiling_index(progress: Progress) -> int:
    """The highest quality index this crafter's hands can reach (§4.3): the level row's
    `ceiling` (Fine, Superior, Flawless at 1-3), plus one step per Quality perk."""
    return _ceiling(_track_of(progress), progress)


def perk_multipliers(progress: Progress) -> dict:
    """What the perks do to everything this crafter makes, for the bench to apply.

    {"potency": 1.10, "duration": 1.2, "yield_chance": 0.05} for two Potency picks, two
    Duration and one Yield. Rounded, because 1 + 0.05 * 3 is 1.1500000000000001 and a
    number shown to the player should not be.

    A track that offers Hardening (the Blacksmith) also gets `hardening`: what its
    negatives are multiplied by, 0.95 per pick, compounding (plan §4.3: "0.9^5 x 0.95^2"
    at level 6 with two picks). Only then, so the Herbalist's answer keeps its four keys.
    """
    track = _track_of(progress)
    n = {p: int(progress.perks.get(p, 0)) for p in set(PERKS) | {"hardening"}}
    out = {
        "potency": round(1 + _perk_size(track, "potency") * n["potency"], 4),
        "duration": round(1 + _perk_size(track, "duration") * n["duration"], 4),
        "yield_chance": round(_perk_size(track, "yield") * n["yield"], 4),
    }
    if track is not None and "hardening" in track.perks:
        out["hardening"] = round((1 - _perk_size(track, "hardening")) ** n["hardening"], 4)
    # The Enchanter's Capacity perk (enchanting plan §5.2): +N to what an item holds, a
    # count `magic_layer.capacity` adds, so it is said as one rather than a multiplier.
    if track is not None and "capacity" in track.perks:
        out["capacity"] = int(_perk_size(track, "capacity") * int(progress.perks.get(
            "capacity", 0) or 0))
    return out


def _next_rung(track: Track, progress: Progress, ceiling: int) -> str:
    """Where the ceiling rises next, as a sentence: a written level that lifts it, or else
    the next Quality perk. Empty when nothing ever raises it again."""
    quality = int(_perk_size(track, "quality")) * int(progress.perks.get("quality", 0))
    for row in sorted(track.levels, key=lambda r: r.level):
        if row.level > progress.level and row.ceiling is not None \
                and row.ceiling + quality > ceiling:
            return f"{quality_name(row.ceiling + quality)} at {track.name} {row.level}"
    step = int(_perk_size(track, "quality"))
    if track.endless and step:
        return f"{quality_name(ceiling + step)} at your next Quality perk"
    return ""


def track_summary(track: Track, progress: Progress) -> dict:
    """The `track` object of the bench state (contracts §3.1), and the reply to a perk
    pick (§3.5). One builder so the two can never disagree.

    `to_next` here is {"need": the level's price, "have": mastery banked}, the contract's
    shape, which is not `_remaining`'s {"need": what is left, "of": ...}.
    """
    need = track.to_next(progress.level)
    ceiling = _ceiling(track, progress)
    return {
        "id": track.id,
        "level": int(progress.level),
        "mp": int(progress.mp),
        "to_next": None if need is None else {"need": int(need), "have": int(progress.mp)},
        "ceiling": ceiling,
        "ceiling_name": quality_name(ceiling),
        "perks": {p: int(progress.perks[p]) for p in track.perks if progress.perks.get(p)},
        "picks_banked": _banked(track, progress),
        "next_rung": _next_rung(track, progress, ceiling),
    }


def pick_perks(track: Track, progress: Progress, picks: list[str]) -> dict:
    """Spend banked picks. The same perk twice is allowed (owner, 2026-10-02).

    All or nothing: every pick is checked before any is taken, so a bad last pick never
    leaves the first ones spent. Raises ValueError with a plain sentence the bench can
    show as it is. Returns `track_summary`.
    """
    chosen = [str(p).strip().lower() for p in (picks or [])]
    if not chosen:
        raise ValueError("Choose at least one perk.")
    offered = track.perks
    unknown = [p for p in chosen if p not in offered]
    if unknown:
        raise ValueError(f"There is no perk called {unknown[0]!r}. The perks are "
                         f"{', '.join(offered[:-1])} and {offered[-1]}.")
    banked = _banked(track, progress)
    if len(chosen) > banked:
        have = "no perk picks" if not banked else \
            f"{banked} perk pick{'s' if banked != 1 else ''}"
        raise ValueError(f"You have {have} banked and chose {len(chosen)}.")
    for p in chosen:
        progress.perks[p] = int(progress.perks.get(p, 0)) + 1
    return track_summary(track, progress)


def _settle(track: Track, progress: Progress, reasons: list[dict]) -> dict:
    gained = sum(r["mp"] for r in reasons)
    progress.mp += gained
    levelled = _advance(track, progress)
    return {"track": track.id, "mp": gained, "reasons": reasons, "total": progress.mp,
            "level": progress.level, "levelled": levelled,
            "to_next": _remaining(track, progress)}


def _units(n: int, noun: str) -> str:
    """"1 dose", "5 doses", "3 ingots": every noun a bench passes takes a plain s."""
    return f"{n} {noun}{'' if n == 1 else 's'}"


def award_step(track: Track, progress: Progress, *, method: str, ingredient_id: str,
               rarity_rank: int, quality_index: int, success: bool = True,
               name: str = "", count: int = 1, noun: str = "step") -> dict:
    """Score one bench step (§4.4) and advance the track if it is earned.

    A success pays `STEP_MP`, one more per rarity band above common, and a quality bonus
    at Superior and up. Itemised exactly as `award` is, so "Grind, comfrey 1; rare
    material 2; Superior work 1" is a sentence the player can check.

    Every successful step pays, every time (owner, 2026-10-05: "batch of 10 should pay
    10"; `REPEAT_LIMIT` no longer caps a success). A mishap still pays `MISHAP_LIMIT`
    times per (method, ingredient) and then teaches nothing more. `TRIVIAL_GAP` is
    dropped on this path: past level 3 the levels no longer climb in rarity bands, so
    "beneath you" has no meaning.

    A batch is `count` steps, paid exactly as that many single steps in a row would be
    (owner, 2026-10-05: "batch crafting does not give equivalent experience"). Measured
    before this: a batch of 5 Ground Mint paid 1 step MP and five single grinds paid 3;
    at Herbalist 2 with Superior hands, 2 against 6. The batch also moved the repeat
    counter by one, so ten doses spent one of the three paid repeats and the next two
    singles still paid: the batch underpaid *and* walked round the anti-grind rule. Now
    the per-step MP, the rarity bands and the quality bonus are paid for every step, a
    failed batch's steps (one roll the whole stack shares, as the owner ruled for the
    minigame) each take their turn against `MISHAP_LIMIT`, and the counter moves by
    `count`. So a batch never pays less than the singles and never more: a batch of 10
    pays what 10 singles pay. (Until the owner's second ruling the same day the repeat
    limit held both to 3.) Firsts are not steps and stay the caller's, once.

    `name` is the ingredient's display name for the line; the id stands in without it.
    `noun` names one step's unit for a batch's lines ("5 doses: 5", "3 ingots: 3").
    """
    key = f"{method}:{ingredient_id}"
    label = f"{str(method).title()}, {name or str(ingredient_id).replace('-', ' ')}"
    count = max(1, int(count or 1))
    # A single step keeps its old lines word for word; a batch says how many it paid for.
    each = (lambda n: "") if count == 1 else (lambda n: f": {_units(n, noun)}")
    reasons: list[dict] = []
    if not success:
        seen = progress.mishaps.get(key, 0)
        paid = max(0, min(count, MISHAP_LIMIT - seen))
        if paid:
            reasons.append({"why": f"{label}, a lesson in failure{each(paid)}",
                            "mp": MP_AWARDS["mishap"] * paid})
        if paid < count:
            reasons.append({"why": f"{label}: {_units(count - paid, noun)} failed with "
                                   f"nothing more to teach (a failure teaches "
                                   f"{MISHAP_LIMIT} times)", "mp": 0})
        progress.mishaps[key] = seen + count
    else:
        times = progress.crafted.get(key, 0)
        paid = count
        if paid:
            reasons.append({"why": f"{label}{each(paid)}", "mp": STEP_MP * paid})
            bands = min(len(TIERS) - 1, max(0, int(rarity_rank) - 1))
            if bands:
                reasons.append({"why": f"{TIERS[bands]} material{each(paid)}",
                                "mp": bands * paid})
            q = int(quality_index)
            bonus = max((mp for at, mp in QUALITY_MP.items() if q >= at), default=0)
            if bonus:
                reasons.append({"why": f"{quality_name(q)} work{each(paid)}",
                                "mp": bonus * paid})
        progress.crafted[key] = times + count
    return _settle(track, progress, reasons)


def award_bonus(track: "Track", progress: Progress, *, why: str, mp: int) -> dict:
    """Mastery that is not a step: a first (`FIRST_MP`) or a manual read (`MANUAL_MP`).
    Itemised the way `award` is, and advances the track the same way. Nothing here
    remembers which first or which manual: the caller owns that record (the herbarium,
    `Actor.manuals_read`), because only it knows what "first" means."""
    gained = max(0, int(mp))
    return _settle(track, progress, [{"why": why, "mp": gained}] if gained else [])


def migrate_herbalist(progress: Progress) -> bool:
    """Settle a pre-revamp Herbalist under the new rules, once (plan §14). True if it ran.

    Old levels 4 and 5 (and the uncapped 6+ past them) become endless levels. Nothing has
    to move to say so: the unlocks now stop at 3 and the bank is counted from the level,
    so an old Herbalist 4 already holds one pick-pair and an old 5 two, waiting for the
    player to choose on their first visit to the bench. Banked mastery is untouched. An
    old `legendary-catalyst` in `milestones` is inert: no level waits on it any more.

    Idempotent by the stamp: a progress at `HERBALISM_SCHEMA` or later is left alone, so
    running it on every load is safe.
    """
    if int(progress.schema) >= HERBALISM_SCHEMA:
        return False
    progress.schema = HERBALISM_SCHEMA
    return True


def migrate_blacksmith(progress: Progress) -> bool:
    """Settle a pre-revamp Blacksmith under the 2026-10-03 rules, once (plan §14). True if
    it ran.

    The Herbalist's conversion, for the same reason it needs no arithmetic: the unlocks
    now stop at 3 and the perk bank is counted from the level, so an old Blacksmith 4
    already holds one pick-pair and an old 5 two, waiting for the player at the forge.
    Banked mastery is untouched. An old `legendary-metal` in `milestones` is inert: no
    level waits on it any more. Old recipes naming draw, polish, flux or rivet are read
    through `rules/blacksmith.py` (`old_method`), not rewritten here.

    Idempotent by the stamp, so running it on every load is safe.
    """
    if int(progress.schema) >= BLACKSMITH_SCHEMA:
        return False
    progress.schema = BLACKSMITH_SCHEMA
    return True


def migrate_enchanter(progress: Progress) -> bool:
    """Settle a pre-revamp Enchanter under the 2026-10-05 rules, once (enchanting plan §19).
    True if it ran.

    The Herbalist's and the Blacksmith's conversion: the unlocks stop at 3 and the bank is
    counted from the level, so an old Enchanter 4 holds one pick-pair and an old 5 two,
    waiting at the circle. Banked mastery is untouched; an old `legendary-binding` in
    `milestones` is inert. This only stamps the progress: old enchanted ITEMS are converted
    record by record on load (`enchanter.migrate_old_record`, called from `sheet._migrated`
    for the pack and the worn copies; lane H), and old chain recipes need nothing here —
    the track's `old_methods` maps their methods, and no save measured on 2026-10-06 holds
    one. An old Enchanter 5 measured on the live bench: level 5 kept, 4 picks banked, the
    perk picker's to show on the first visit (tests/test_enchant_migration.py).

    Idempotent by the stamp, so running it on every load is safe.
    """
    if int(progress.schema) >= ENCHANTER_SCHEMA:
        return False
    progress.schema = ENCHANTER_SCHEMA
    return True


def migrate_alchemist(progress: Progress) -> bool:
    """`alchemy_v2`: settle a pre-revamp Alchemist under the 2026-10-05 rules, once (alchemy
    plan §18; owner Q10.1). True if it ran.

    The other three crafts' conversion: the unlocks stop at 3 and the bank is counted from
    the level, so an old Alchemist 4 holds one pick-pair and an old 5 two, waiting at the
    bench's perk picker; banked mastery is untouched; the old `legendary-work` milestone is
    inert. Under the owner's spell rule an old Alchemist 3 now bottles 1st-level spells only
    (they needed 4 for 2nd before): that is the rule, and their stock is untouched.

    Unlike the other three it stamps **only a level past the unlocks**, the one case the
    conversion changes anything. Levels 1 to 3 are the same three levels before and after,
    and every owner save measured on 2026-10-07 holds an Alchemist 1 with no stamp: stamping
    it would rewrite every save on its first load for nothing, where "a save with no alchemy
    in it round-trips byte for byte" (tests/test_alchemy_migration.py). Old ITEMS, knowledge
    and saved chains are rules/alchemy_migration.py's (on load, from `sheet._migrated` and
    `Campaign.load`).

    Idempotent by the stamp, so running it on every load is safe.
    """
    if int(progress.schema) >= ALCHEMIST_SCHEMA:
        return False
    track = _track_of(progress)
    unlocks = track.max_level if track is not None else UNLOCK_LEVELS
    if int(progress.level) <= unlocks:
        return False
    progress.schema = ALCHEMIST_SCHEMA
    return True


# Load-time migrations by track id. The one place a track is named in this module, and
# only because a migration is by definition about one track's own history.
MIGRATIONS = {"herbalist": migrate_herbalist, "blacksmith": migrate_blacksmith,
              "enchanter": migrate_enchanter, "alchemist": migrate_alchemist}


def migrate(progress: Progress) -> bool:
    """Run whatever migration this progress's track has. Called by `sheet._progress` on
    every load, which is safe because each migration is idempotent."""
    fn = MIGRATIONS.get(progress.track)
    return bool(fn and fn(progress))


def award(track: Track, progress: Progress, *, recipe_id: str, tier: str,
          success: bool = True, risky: bool = False, stages: int = 1,
          milestone: str = "") -> dict:
    """Score one craft and advance the track if it is earned.

    The per-recipe award the Alchemist, Blacksmith, Leatherworker and Enchanter benches
    and the GM's `craft` op use. The Herbalist's step-by-step bench scores through
    `award_step` instead.

    Returns an itemised breakdown rather than a total, for the same reason every roll in
    this app does: "3 first time, 2 risky harvest, 4 for three stages" is a sentence the
    player can check, and a bare +9 is one they have to trust.
    """
    reasons: list[dict] = []
    gap = progress.level - tier_rank(tier)

    if not success:
        seen = progress.mishaps.get(recipe_id, 0)
        if seen < MISHAP_LIMIT and gap < TRIVIAL_GAP:
            reasons.append({"why": "mishap", "mp": MP_AWARDS["mishap"]})
        progress.mishaps[recipe_id] = seen + 1
    elif gap >= TRIVIAL_GAP:
        # Beneath you. Recorded as known, so it still counts as discovered, but the
        # points are gone — this is the whole of the anti-grind rule.
        progress.crafted[recipe_id] = progress.crafted.get(recipe_id, 0) + 1
    else:
        times = progress.crafted.get(recipe_id, 0)
        if times == 0:
            reasons.append({"why": "first-time recipe", "mp": MP_AWARDS["first_time"]})
        else:
            # Every repeat pays (owner, 2026-10-05): see `REPEAT_LIMIT`.
            reasons.append({"why": "repeat craft", "mp": MP_AWARDS["repeat"]})
        if risky:
            reasons.append({"why": "risky harvest", "mp": MP_AWARDS["risky_harvest"]})
        extra = max(0, int(stages) - 1)
        if extra:
            reasons.append({"why": f"{extra + 1}-stage chain",
                            "mp": extra * MP_AWARDS["per_extra_stage"]})
        progress.crafted[recipe_id] = times + 1

    if milestone and milestone not in progress.milestones:
        progress.milestones.append(milestone)

    return _settle(track, progress, reasons)


def _advance(track: Track, progress: Progress) -> list[int]:
    """Spend mastery on levels, as many as have been earned."""
    gained = []
    # No ceiling: `to_next` returns None only for a track that declares one.
    while True:
        need = track.to_next(progress.level)
        if need is None or progress.mp < need:
            break
        required = track.milestones.get(progress.level + 1)
        if required and required not in progress.milestones:
            # The points are kept, not burned: the level is waiting on the deed.
            break
        progress.mp -= need
        progress.level += 1
        gained.append(progress.level)
    return gained


def _remaining(track: Track, progress: Progress) -> dict | None:
    need = track.to_next(progress.level)
    if need is None:
        return None
    blocked = track.milestones.get(progress.level + 1)
    if blocked and blocked in progress.milestones:
        blocked = None
    return {"need": max(0, need - progress.mp), "of": need, "milestone": blocked}


# --- loading -------------------------------------------------------------------------------

def from_dict(data: dict) -> Track:
    return Track(
        id=data["id"], name=data["name"], summary=data.get("summary", ""),
        levels=[Level(level=int(l["level"]), tools=l.get("tools", []),
                      methods=l.get("methods", []),
                      max_tier=l.get("max_tier", "common"), note=l.get("note", ""),
                      ceiling=(int(l["ceiling"]) if l.get("ceiling") is not None
                               else None))
                for l in data.get("levels", [])],
        thresholds=[int(t) for t in data.get("thresholds", [])],
        milestones={int(k): v for k, v in (data.get("milestones") or {}).items()},
        deeds=dict(data.get("deeds") or {}),
        grantable_at_creation=bool(data.get("grantable_at_creation", True)),
        # Author's notes (`_..._note`) inside the block are documentation, not rules.
        endless={k: v for k, v in (data.get("endless") or {}).items()
                 if not str(k).startswith("_")},
        data={k: v for k, v in data.items() if not str(k).startswith("_")},
    )


def load_dir(path: str | Path) -> dict[str, Track]:
    out: dict[str, Track] = {}
    for p in sorted(Path(path).glob("*.json")):
        track = from_dict(json.loads(p.read_text(encoding="utf-8")))
        out[track.id] = track
    return out


_TRACKS: dict[str, Track] | None = None


def tracks() -> dict[str, Track]:
    """Every world class the app knows, shipped and homebrew.

    Homebrew is layered over the shipped set rather than replacing it, so a corrected
    Herbalist in a later build is not shadowed by a stale copy in the user's data
    directory — the trap `CLAUDE.md` records from World Bible's stylesheet.
    """
    global _TRACKS
    if _TRACKS is None:
        from django.conf import settings

        _TRACKS = load_dir(Path(settings.BASE_DIR) / "content" / "world-classes")
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "world-classes"
        if user.is_dir():
            _TRACKS.update(load_dir(user))
    return _TRACKS


def get(track_id: str) -> Track:
    t = tracks().get((track_id or "").strip().lower())
    if t is None:
        known = ", ".join(sorted(tracks())) or "none"
        raise KeyError(f"no world class {track_id!r}. Known: {known}")
    return t
