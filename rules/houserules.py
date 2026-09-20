"""The table's own rules: toggles that bend 1e where the player says to.

These are settings, not content — one small JSON file beside the homebrew folders,
read fresh on every ask. No cache, because the file is a hundred bytes and a cached
copy of a rule the player just changed is a rule that silently is not in effect: the
exact staleness trap CLAUDE.md records against derived caches.

Two rules exist today.

**Point buy tier.** 1e's own table stops at 25 (Epic Fantasy); the tiers above it are
homebrew and say so. One is active at a time — a budget is a single number, and the
forge, the validator and the refusal text all read the same one, so there is nothing
to disagree.

**Magic effect stacking.** By the book, magical effects from different sources do not
stack — the best applies — and the same source reapplies rather than piling up. The
toggle keeps the second half (same source still reapplies; two castings of one ward
are a renewal, not a doubling) and lifts the first: different sources add. Today the
engine's live no-stack rule is temporary hit points, so that is what the toggle
reaches; typed bonuses join it when the engine executes them at all. Where the rules
already refresh-on-same-source — guards, compulsions — the toggle changes nothing,
because that half is the half both modes share.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings

# The four named tiers are the Core Rulebook's own table. Everything past 25 is this
# app's homebrew, and the names admit it rather than borrowing the book's authority.
POINT_BUY_TIERS = [
    {"points": 10, "name": "Low fantasy", "book": True},
    {"points": 15, "name": "Standard fantasy", "book": True},
    {"points": 20, "name": "High fantasy", "book": True},
    {"points": 25, "name": "Epic fantasy", "book": True},
    {"points": 30, "name": "Mythic", "book": False},
    {"points": 40, "name": "Legendary", "book": False},
    {"points": 50, "name": "Demigod", "book": False},
    {"points": 75, "name": "Ascendant", "book": False},
    {"points": 100, "name": "The full hundred", "book": False},
    # 0 is no budget at all — every score bought as high as the ceiling allows, which
    # with no ceiling is the point-buy table's own top. "add an Unlimited option"
    # (2026-09-08). Readers ask `point_budget()` and treat 0 as unlimited.
    {"points": 0, "name": "Unlimited", "book": False},
]

# How high one score may go before the race is applied. 18 is the Core Rulebook's own
# ceiling and the point-buy table stops there; everything above it is this table's
# homebrew and the cost of it is extrapolated (see `creation.point_cost`). 0 means no
# ceiling at all — which is not unlimited in practice, because the point budget is
# still a wall and a 24 costs fifty of it.
ABILITY_CAPS = [
    {"cap": 18, "name": "By the book", "book": True},
    {"cap": 20, "name": "Heroic", "book": False},
    {"cap": 25, "name": "Titanic", "book": False},
    {"cap": 0, "name": "No cap", "book": False},
]

DEFAULTS = {"point_buy": 20, "magic_stacking": False, "ability_cap": 18,
            "pronoun_sets": [],
            # The Core Rulebook's seven offered beside a world's own races. Off, and a
            # world's forge offers only the races the world ships — "instead of picking
            # the fantasy races that ship with pathfinder".
            "core_races": True,
            # How strong a race the forge accepts, in the Advanced Race Guide's race
            # points: 10 is the Race Builder's standard tier, the Core seven's own.
            "race_rp": 10,
            # The table's own debugging view of the quest schemes running — what fired
            # and why. Off by default: it shows the GM's secrets, and is never the brief.
            "gm_view": False,
            # Whether `/gm` may OFFER what the character does not know. Ruled
            # 2026-09-18 (docs/playtest-2026-09-18.md, item 9): the information should
            # be available, but only after the player is asked. Off: hidden facts stay
            # hidden and `/gm` names the in-play route (ask around). On: "Your
            # character wouldn't know this yet — say the word if you want it anyway."
            # The known trade-off, accepted with the ruling: the offer itself tells the
            # player a secret exists. Public facts are answered either way; rumour-grade
            # facts ride a secret Knowledge (local) roll, once, PF1e's "Try Again: No".
            "knowledge_offer": False,
            # What the narrator does when a scene turns to intimacy: "fade" — say that
            # time passes and resume after, a designed transition rather than a stall —
            # or "explicit". The app had taken no position (item 22) and the outcome was
            # whatever the guards happened to do. Fade is the default; explicit is the
            # table's to turn on.
            "content": "fade"}

# What the character forge offers everybody. Two, because that is what the table asked
# for: "male and female should be the only options default".
#
# Anything else is opt-in and arrives one of two ways — the player writes it themselves
# in the free field, or the table turns a set on here, which is how a world of winged
# people or constructs makes its own pronouns a first-class choice rather than a thing
# every player has to retype. Nothing is offered by default that nobody asked for.
DEFAULT_PRONOUNS = ("she/her", "he/him")


def _path() -> Path:
    """Beside the homebrew content folders — not *in* the rulesets one, because every
    file in a bench folder counts as something the user authored, and a settings file
    showing up as "1 yours" on the bench is a lie about what was made."""
    p = Path(settings.CAMPAIGN_DIR).parent / "homebrew"
    p.mkdir(parents=True, exist_ok=True)
    return p / "house-rules.json"


def active() -> dict:
    """The rules in effect, defaults filled in, unknown keys dropped.

    A file this small is read on every ask on purpose — see the module docstring.
    A half-written or hand-mangled file falls back to the book rather than crashing
    every roll in the app over a settings toggle.
    """
    out = dict(DEFAULTS)
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except Exception:
        return out
    if isinstance(raw, dict):
        if raw.get("point_buy") in {t["points"] for t in POINT_BUY_TIERS}:
            out["point_buy"] = int(raw["point_buy"])
        out["magic_stacking"] = bool(raw.get("magic_stacking", False))
        if raw.get("ability_cap") in {c["cap"] for c in ABILITY_CAPS}:
            out["ability_cap"] = int(raw["ability_cap"])
        # The race tier and the Core-seven switch, re-read the way they are written.
        # Missed when they were added: `set_active` wrote them and this whitelist
        # dropped them, so the 20 and 40 RP buttons could be pressed and never held.
        try:
            from . import races as races_mod

            if int(raw.get("race_rp", -1)) in {t["rp"] for t in races_mod.TIERS}:
                out["race_rp"] = int(raw["race_rp"])
        except (TypeError, ValueError):
            pass
        out["core_races"] = bool(raw.get("core_races", DEFAULTS["core_races"]))
        out["gm_view"] = bool(raw.get("gm_view", False))
        # The same omission again, found by the live check that groups 5 and 6 still
        # owed (2026-09-20): `set_active` wrote `knowledge_offer` and `content`, the
        # file on disk read `"knowledge_offer": true`, and this whitelist handed back
        # the default — so the shelf toggle could be pressed and never held, and the
        # content setting could not be changed at all. Exactly what the comment six
        # lines above records for `race_rp`; adding a key here is part of adding a
        # rule, which is CLAUDE.md's "when you fix a rule, grep for every copy of it".
        out["knowledge_offer"] = bool(raw.get("knowledge_offer", False))
        said = str(raw.get("content", "") or "").strip().lower()
        if said in ("fade", "explicit"):
            out["content"] = said
        # Re-read the same way it is written. `set_active` validated these on the way in,
        # and a key this function does not name is silently dropped — which is the point
        # of the whitelist and was why a saved set came back as the defaults.
        sets = raw.get("pronoun_sets")
        if isinstance(sets, (list, tuple)):
            out["pronoun_sets"] = [" ".join(str(p).split()).lower() for p in sets
                                   if str(p).strip()]
    return out


def set_active(updates: dict) -> tuple[dict, list[str]]:
    """Change the house rules, or say exactly why not. Only known keys move."""
    problems: list[str] = []
    current = active()
    if "point_buy" in updates:
        tiers = {t["points"] for t in POINT_BUY_TIERS}
        try:
            points = int(updates["point_buy"])
        except (TypeError, ValueError):
            points = -1
        if points not in tiers:
            problems.append(
                f"{updates['point_buy']!r} is not a point-buy tier; the tiers are "
                + ", ".join(str(t["points"]) for t in POINT_BUY_TIERS) + ".")
        else:
            current["point_buy"] = points
    if "magic_stacking" in updates:
        current["magic_stacking"] = bool(updates["magic_stacking"])
    if "core_races" in updates:
        current["core_races"] = bool(updates["core_races"])
    if "gm_view" in updates:
        current["gm_view"] = bool(updates["gm_view"])
    if "knowledge_offer" in updates:
        current["knowledge_offer"] = bool(updates["knowledge_offer"])
    if "content" in updates:
        want = str(updates["content"] or "").strip().lower()
        if want not in ("fade", "explicit"):
            problems.append(f"{updates['content']!r} is not a content setting; it is "
                            f"'fade' or 'explicit'.")
        else:
            current["content"] = want
    if "race_rp" in updates:
        from . import races as races_mod

        allowed = {t["rp"] for t in races_mod.TIERS}
        try:
            points = int(updates["race_rp"])
        except (TypeError, ValueError):
            points = -1
        if points not in allowed:
            problems.append(
                f"{updates['race_rp']!r} is not a race tier; the tiers are "
                + ", ".join(f"{t['rp']} ({t['name']})" for t in races_mod.TIERS) + ".")
        else:
            current["race_rp"] = points
    if "pronoun_sets" in updates:
        raw = updates["pronoun_sets"]
        if isinstance(raw, str):
            # Typed into a textarea, one per line or comma separated. Built with chr(10)
            # rather than an escape: this line was written through a heredoc once and the
            # backslash-n became a real newline in the source, which is the trap
            # CLAUDE.md records for exactly this.
            raw = raw.replace(",", chr(10)).split(chr(10))
        if not isinstance(raw, (list, tuple)):
            problems.append("Pronoun sets are a list of forms like 'ze/hir'.")
        else:
            kept = []
            for one in raw:
                said = " ".join(str(one).split()).strip().lower()
                if not said:
                    continue
                if "/" not in said or len(said) > 40:
                    problems.append(
                        f"{one!r} is not a pronoun set; write them as 'ze/hir'.")
                    continue
                if said not in kept and said not in DEFAULT_PRONOUNS:
                    kept.append(said)
            current["pronoun_sets"] = kept
    if "ability_cap" in updates:
        allowed = {c["cap"] for c in ABILITY_CAPS}
        try:
            cap = int(updates["ability_cap"])
        except (TypeError, ValueError):
            cap = -1
        if cap not in allowed:
            problems.append(
                f"{updates['ability_cap']!r} is not an ability ceiling; the ceilings "
                f"are " + ", ".join(str(c["cap"]) or "none" for c in ABILITY_CAPS) + ".")
        else:
            current["ability_cap"] = cap
    if not problems:
        _path().write_text(json.dumps(current, indent=2), encoding="utf-8")
    return active(), problems


def knowledge_offer() -> bool:
    """Whether `/gm` may offer what the character does not know (item 9's ruling)."""
    return bool(active().get("knowledge_offer", False))


def content() -> str:
    """"fade" or "explicit": what the narrator does when a scene turns to intimacy."""
    return str(active().get("content", "fade") or "fade")


def gm_view() -> bool:
    return bool(active().get("gm_view", False))


def core_races() -> bool:
    return bool(active().get("core_races", DEFAULTS["core_races"]))


def race_rp() -> int:
    return int(active().get("race_rp", DEFAULTS["race_rp"]))


def point_budget() -> int:
    return active()["point_buy"]


def magic_stacking() -> bool:
    return active()["magic_stacking"]


def ability_cap() -> int:
    """The highest a single score may be bought to. 0 means no ceiling."""
    return int(active()["ability_cap"])


def pronoun_sets() -> list[str]:
    """Every pronoun set the forge should offer: the two defaults, then any this table
    has turned on. Order matters — the defaults come first because they are what most
    characters use, and the rest are there because somebody asked for them."""
    extra = active().get("pronoun_sets") or []
    return list(DEFAULT_PRONOUNS) + [p for p in extra if p not in DEFAULT_PRONOUNS]
