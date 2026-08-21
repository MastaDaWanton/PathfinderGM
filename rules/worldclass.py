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
    grantable_at_creation: bool = True

    @property
    def max_level(self) -> int:
        return max((l.level for l in self.levels), default=1)

    def at(self, level: int) -> Level:
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
        """Mastery needed to leave this level, or None at the top."""
        if level >= self.max_level:
            return None
        return self.thresholds[level - 1]


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

    def knows(self, recipe_id: str) -> bool:
        return recipe_id in self.crafted


def award(track: Track, progress: Progress, *, recipe_id: str, tier: str,
          success: bool = True, risky: bool = False, stages: int = 1,
          milestone: str = "") -> dict:
    """Score one craft and advance the track if it is earned.

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
        elif times < REPEAT_LIMIT:
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

    gained = sum(r["mp"] for r in reasons)
    progress.mp += gained
    levelled = _advance(track, progress)
    return {
        "track": track.id, "mp": gained, "reasons": reasons, "total": progress.mp,
        "level": progress.level, "levelled": levelled,
        "to_next": _remaining(track, progress),
    }


def _advance(track: Track, progress: Progress) -> list[int]:
    """Spend mastery on levels, as many as have been earned."""
    gained = []
    while progress.level < track.max_level:
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
                      max_tier=l.get("max_tier", "common"), note=l.get("note", ""))
                for l in data.get("levels", [])],
        thresholds=[int(t) for t in data.get("thresholds", [])],
        milestones={int(k): v for k, v in (data.get("milestones") or {}).items()},
        grantable_at_creation=bool(data.get("grantable_at_creation", True)),
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
