"""A life, rolled: the face, the work, the temperament, what they want, what they are
after, what they do for pleasure, and the one thing that makes them theirs.

Asked for 2026-09-25: every person the prose describes is recorded, and "the notes should
include things they want and goals for the future hobbies and what they do for work";
"roll a personality from a massive chart and everyone should get a quirky thing to make
them special also rolled"; and results that would not be coherent with what was already
rolled are locked out. Design record: docs/the-population.md.

**The order is the coherence.** Body and face first (the people's own line and
`rules/faces.py`'s tables), then work, then the hands and clothes chosen to fit that work,
then temperament, wants, goal, hobby, and the quirk last because it is the most specific
and has the most to agree with. Every roll after the first is drawn only from the rows
that agree with everything already rolled:

  * a row's `requires` — at least one of these tags must already be rolled;
  * a row's `excludes` / `forbids` — none of these may be;
  * a row's `classes` — the work class must be one of these;
  * a quirk frame's `needs` — body facts that must be true (hair, the gap in the teeth).

Only the rolled THINGS carry tags (the work, the body, the temperament poles); the rows
of the want, goal, hobby and quirk tables add none, so every check runs one way against
what is already fixed and cannot depend on the order two rows were considered in — the
order-dependent conflict The Sims 4 shipped (see the research record).

**Deterministic.** Seeded by the person's own id (sha256, as `names` and `faces` are), so
the same person always rolls the same life; and the caller stores what was rolled, so a
reload never re-rolls anybody.

**A pool emptied by exclusions falls back** to the rows with no conditions and says so in
`fallbacks`, never to a row that contradicts — the replay corpus counts these.

**Quirk frames are drawn without replacement within a settlement** (`used_frames`): ten
people drawing from forty frames share one about 71% of the time otherwise, and a frame is
what a player notices.

Nothing here is a number the narrator sees: the axis scores stay with the engine; the
model is given two or three trait words, the quirk, and one line of how it shows.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import faces as faces_mod

_TABLES: dict | None = None


def tables() -> dict:
    """The shipped charts, read once. Found through `settings.BASE_DIR`, never `__file__`,
    which points inside the bundle when frozen (CLAUDE.md; the packaging test caught the
    first cut of this module doing exactly that)."""
    global _TABLES
    if _TABLES is None:
        from django.conf import settings

        folder = Path(settings.BASE_DIR) / "content" / "people"
        read = lambda n: json.loads((folder / n).read_text(encoding="utf-8"))  # noqa: E731
        _TABLES = {
            "occupations": read("occupations.json")["occupations"],
            "personality": read("personality.json")["axes"],
            **{k: v for k, v in read("life.json").items() if k != "note"},
            **{k: v for k, v in read("quirks.json").items() if k != "note"},
            "synonyms": read("synonyms.json"),
        }
    return _TABLES


# --- the face, with the facts about a body the quirk chart asks --------------------------

# What each face line says about the body, for the frames that need one.
_MARK_TAGS = {
    "a scar through one eyebrow": {"scar_brow"},
    "the last two fingers of the left hand gone at the knuckle": {"missing_fingers"},
    "an old burn across the back of one hand": {"burned_hand"},
    "one eye clouded and turned slightly out": {"one_eye"},
    "a limp favouring the right leg": {"limp"},
    "a stoop that has become the way they stand": {"stoop"},
    "a missing front tooth that shows when they talk": {"gap_tooth"},
}
_YEARS_TAGS = {0: {"young"}, 1: {"young"}, 4: {"old"}, 5: {"old"}, 6: {"old"}}

# A child's own years, marks and clothes: `faces.YEARS` starts at "not long out of their
# growing", and a boy rolled as "weathered well past what the years alone would do" with
# a brand on his wrist was the first child this module made (2026-09-25).
_CHILD_YEARS = ("a child still growing into their own feet",
                "a child of perhaps eight or nine, all elbows and questions",
                "a child at the age where every sentence starts with why")
_CHILD_MARKS = {"a scar through one eyebrow", "a missing front tooth that shows when they talk",
                "the marks of an old pox across the cheeks", "an old burn across the back of one hand",
                "a limp favouring the right leg", "a pale seam of scar tissue down one forearm"}
_CHILD_HANDS = {"clothes good once and mended more than once since",
                "a coat too heavy for the weather, worn anyway",
                "boots that have walked further than the rest of the outfit",
                "hands soft and clean, the nails kept"}
_CHILD_HEADS = {"hair cropped close to the skull",
                "hair worn in a single thick braid down the back",
                "a mane of hair left to do as it likes",
                "hair hidden under a cap that has not been off in a while",
                "a fringe cut straight across, badly",
                "hair the colour of wet rope, tied with a strip of cloth"}
# A head that shows no hair to smooth: the people may have hair and this person not.
_NO_VISIBLE_HAIR = {"a shaved head, nicked in two places by the razor",
                    "hair hidden under a cap that has not been off in a while"}
_OLD_WORDS = ("old", "elderly", "aged", "grey-haired", "grey-bearded", "greybeard", "ancient",
              "crone", "wizened")
_YOUNG_WORDS = ("young", "youth", "youngster", "lad", "lass")

# Which work each hands-and-clothes line can belong to (any of these tags, or any work at
# all when absent). The line was chosen independently of the work before 2026-09-25, so a
# fisherman could come out with a scribe's ink-black fingertips.
_HANDS_FIT = {
    "hands stained to the wrist with dye that will not wash out": {"cloth"},
    "hands thick with the calluses of rope and haft": {"sea", "labour", "arms", "farm", "road"},
    "hands soft and clean, the nails kept": {"learned", "gentry", "trade", "faith", "letters"},
    "fingers stained black at the tips with ink": {"letters"},
    "a carter's shoulders and a carter's rolling walk": {"road", "labour", "travel"},
    "boots that have walked further than the rest of the outfit": {"travel", "mobile"},
    "a knife at the belt that is a tool and not a weapon": {"craft", "labour", "farm", "sea", "food"},
    "rings on three fingers, none of them worth much": {"trade", "gentry", "rogue", "coin"},
    "a smell of smoke and hot iron that goes everywhere they do": {"forge"},
}


@dataclass
class Life:
    work: str
    work_name: str
    mobility: str
    face: str
    traits: list[str]
    trait_ids: list[str]
    shows: list[str]
    axes: dict[str, int]
    wants: str
    goal: str
    hobby: str
    quirk: str
    quirk_frame: str
    tags: list[str]
    fallbacks: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _rng(*parts: str) -> random.Random:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _fits(row: dict, tags: set[str], work_class: str) -> bool:
    req = row.get("requires") or []
    if req and not (set(req) & tags):
        return False
    if set(row.get("excludes") or []) & tags or set(row.get("forbids") or []) & tags:
        return False
    classes = row.get("classes") or []
    return not classes or work_class in classes


def _pick(rows: list[dict], rng: random.Random, tags: set[str], work_class: str,
          what: str, fallbacks: list[str]) -> dict:
    """One row that agrees with everything rolled so far.

    A row whose `requires` or `classes` matched is weighted three to one over a row with
    no conditions: the specific row is the characterful one, and drawn flat the
    unconditional rows swamped it — "to learn to read and write properly" came up for
    three of the first six people rolled (2026-09-25)."""
    legal = [r for r in rows if _fits(r, tags, work_class)]
    if not legal:
        legal = [r for r in rows if not (r.get("requires") or r.get("excludes")
                                         or r.get("forbids") or r.get("classes"))]
        fallbacks.append(what)
    weights = [3 if (r.get("requires") or r.get("classes")) else 1 for r in legal]
    return rng.choices(legal, weights=weights, k=1)[0]


def occupation_for(phrase: str) -> dict | None:
    """The work a described phrase names outright — "the smith", "a fishwife" — or None."""
    words = f" {str(phrase or '').lower()} "
    best = None
    for occ in tables()["occupations"]:
        for m in occ.get("match") or ():
            if f" {m} " in words or f" {m}s " in words or f" {m}'s " in words:
                if best is None or len(m) > best[0]:
                    best = (len(m), occ)
    if best is not None:
        return best[1]
    # Then word by word, stemmed as the finder stems them (`population._stem`). Measured
    # live 2026-09-27: "somebody selling bread in the market" was rolled a gravedigger,
    # while the finder read "selling" as a stallholder's word; the two disagreed about
    # what a person was, and now the trade decides where they are.
    from .population import _stem

    stems = {_stem(w) for w in re.findall(r"[a-z][a-z'-]*", words)}
    for occ in tables()["occupations"]:
        for m in occ.get("match") or ():
            if " " not in m and _stem(m) in stems:
                if best is None or len(m) > best[0]:
                    best = (len(m), occ)
    return best[1] if best else None


def roll(seed: str, *, phrase: str = "", body: str = "", used_frames=()) -> Life:
    """A whole life for the person whose id is `seed`.

    `phrase` is how the prose described them, read only for the work it names; `body` is
    their people's own line (what `faces` reads to decide whether there is hair to speak
    of); `used_frames` are the quirk frames already carried by people in this settlement.
    """
    t = tables()
    rng = _rng("life", seed)
    fallbacks: list[str] = []
    tags: set[str] = {"hands"}

    # What the prose already said comes first, because a roll may not contradict it: the
    # work it names ("the smith"), and its age ("an old fisherman", "a boy").
    words = f" {str(phrase or '').lower()} "
    occ = occupation_for(phrase)
    minor = bool(occ and "minor" in (occ.get("tags") or []))
    said_old = any(f" {w} " in words for w in _OLD_WORDS)
    said_young = any(f" {w} " in words for w in _YOUNG_WORDS)

    # Body and face, agreeing with that.
    if minor:
        years_line = rng.choice(_CHILD_YEARS)
        tags |= {"young"}
    else:
        bands = [i for i in range(len(faces_mod.YEARS))
                 if (not said_old or "old" in _YEARS_TAGS.get(i, set()))
                 and (not said_young or "young" in _YEARS_TAGS.get(i, set()))
                 and not (occ and "young" in (occ.get("tags") or [])
                          and "old" in _YEARS_TAGS.get(i, set()))
                 and not (occ and "old" in (occ.get("tags") or [])
                          and "young" in _YEARS_TAGS.get(i, set()))]
        years_i = rng.choice(bands or list(range(len(faces_mod.YEARS))))
        years_line = faces_mod.YEARS[years_i]
        tags |= _YEARS_TAGS.get(years_i, set())
    bits = [years_line]
    if not faces_mod._no_hair(body or ""):
        head = rng.choice([h for h in faces_mod.HEAD if not minor or h in _CHILD_HEADS])
        if head not in _NO_VISIBLE_HAIR:
            tags.add("hair")
        bits.append(head)
    marks = [m for m in faces_mod.MARK if not minor or m in _CHILD_MARKS]
    mark = rng.choice(marks)
    tags |= _MARK_TAGS.get(mark, set())
    bits.append(mark)

    # Work: what the prose named, else a roll that agrees with the years.
    if occ is None:
        pool = [o for o in t["occupations"] if o["id"] not in ("child",)
                and not ("young" in o.get("tags", []) and "old" in tags)
                and not (o["id"] == "retired" and "old" not in tags)]
        occ = rng.choice(pool)
    work_class = occ["class"]
    tags |= set(occ.get("tags") or []) | {work_class, occ["mobility"]}

    # Hands and clothes, chosen to fit the work.
    hands = [h for h in faces_mod.HANDS
             if (not _HANDS_FIT.get(h) or _HANDS_FIT[h] & tags)
             and (not minor or h in _CHILD_HANDS)]
    bits.append(rng.choice(hands))
    face = "; ".join(bits)
    face = face[0].upper() + face[1:] + "."

    # Temperament: ten axes on a bell curve; the work may forbid a pole outright (a
    # priest who mocks the gods is not a priest), which leaves that axis silent.
    axes: dict[str, int] = {}
    for axis in t["personality"]:
        score = int(round((sum(rng.randint(1, 6) for _ in range(3)) - 3) / 15 * 100))
        pole = axis["low"] if score < 40 else axis["high"] if score > 60 else None
        if pole and pole["id"] in set(occ.get("excludes") or []):
            score = 50
        axes[axis["id"]] = score
    loudest = sorted(axes, key=lambda a: -abs(axes[a] - 50))
    speaking = [a for a in loudest[:3] if abs(axes[a] - 50) > 10]
    if len(speaking) == 3 and abs(axes[speaking[2]] - 50) < 35:
        speaking = speaking[:2]
    traits, trait_ids, shows = [], [], []
    by_id = {a["id"]: a for a in t["personality"]}
    for a in speaking:
        s = axes[a]
        pole = by_id[a]["low"] if s < 50 else by_id[a]["high"]
        depth = abs(s - 50)
        word = pole["words"][0 if depth <= 25 else 1 if depth <= 40 else 2]
        traits.append(word)
        trait_ids.append(pole["id"])
        shows.append(pole["shows"])
    tags |= set(trait_ids)

    wants = _pick(t["wants"], rng, tags, work_class, "wants", fallbacks)["text"]
    goal = _pick(t["goals"], rng, tags, work_class, "goal", fallbacks)["text"]
    hobby = _pick(t["hobbies"], rng, tags, work_class, "hobby", fallbacks)["text"]

    # The quirk, last: a frame not yet carried in this settlement, its slots filled from
    # this person's own trade and the world's small things.
    frames = [f for f in t["frames"] if set(f.get("needs") or []) <= tags
              and _fits(f, tags, work_class)]
    fresh = [f for f in frames if f["id"] not in set(used_frames)]
    frame = rng.choice(fresh or frames)
    if not fresh:
        fallbacks.append("quirk frames all used here")
    text = frame["text"]
    fill = {
        "small": rng.choice(t["small"]),
        "tool": rng.choice(occ.get("objects") or t["small"]),
        "food": rng.choice(t["food"]),
        "animal": rng.choice(t["animal"]),
        "occasion": _pick(t["occasions"], rng, tags, work_class, "occasion",
                          fallbacks)["text"],
    }
    for slot, value in fill.items():
        text = text.replace("{" + slot + "}", value)

    return Life(work=occ["id"], work_name=occ["name"], mobility=occ["mobility"],
                face=face, traits=traits, trait_ids=trait_ids, shows=shows, axes=axes,
                wants=wants, goal=goal, hobby=hobby, quirk=text, quirk_frame=frame["id"],
                tags=sorted(tags), fallbacks=fallbacks)
