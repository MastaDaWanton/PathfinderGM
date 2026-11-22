"""The numbers a tutorial card may say, read from the engine that makes them true.

The words of every tutorial live in content/tutorials/*.json, and a card that says "a hex
of rough ground takes eight hours" is a promise about the engine. Written into the JSON as
a digit it is a second copy of the number, and the copy drifts: `16-tab-map.js` already
carries "DC 10, 2 more each hour, 1d6" in its own words while `rules/survival.py` owns them
(found while planning, docs/tutorials-plan.md §2). So a tutorial writes `{march_dc_first}`
and this module fills it from the engine's own constant or function, the "no model authors
a number" law applied to the app's own text (tests/test_tutorials.py refuses a bare digit
and an unknown placeholder).

Each fact is a function, called when the page asks, so a number changed in the engine is
the card's new number without anybody touching the card.
"""
from __future__ import annotations

import re
import string


def _hex_hours(which: int) -> int:
    from . import hexes
    return (hexes.HOURS_PLAIN, hexes.HOURS_ROUGH)[which]


def _march_free() -> int:
    from . import journey
    return journey.HOURS_PER_DAY


def _march_dc(extra_hour: int) -> int:
    from . import survival
    return survival.forced_march_dc(extra_hour)


def _march_damage() -> str:
    from . import survival
    return survival.FORCED_MARCH_DAMAGE


def _hex_miles() -> int:
    from . import hexes
    return hexes.HEX_MILES


def _herb_in_progress_hours() -> int:
    # The herb bench's own threshold (content/rules/herbal-methods.json, read by
    # crafting.plan's split): a step this long or longer goes In progress.
    from . import crafting
    minutes = int(crafting.herbal_rules()["methods"].get("in_progress_after", 60))
    return max(1, round(minutes / 60))


def _knockout_dice() -> str:
    # A non-lethal coup de grâce's failed save: out this many hours, never dead.
    from . import coup_de_grace
    return coup_de_grace.KNOCKOUT_DICE


def _forge_in_progress_hours() -> int:
    # The forge's own threshold (rules/blacksmith.py plan: `minutes >= in_progress_after`).
    from . import blacksmith
    return max(1, round(int(blacksmith.bench_rules().get("in_progress_after", 60)) / 60))


def _alchemy_in_progress_hours() -> int:
    # Alchemy's (rules/alchemist.py: a step *longer than* this waits, and every Transmute).
    from . import alchemist
    return max(1, round(int(alchemist.bench_rules().get("in_progress_after", 480)) / 60))


def _perk_track():
    # Every craft's endless levels start and pay alike today (each track's `endless`
    # block); the herbalist's is read as the card's.
    from . import worldclass
    return worldclass.get("herbalist")


def _perk_from_level() -> int:
    return int(_perk_track().max_level)


def _perk_picks() -> int:
    from . import worldclass
    return int(_perk_track().endless.get("picks_per_level", worldclass.PICKS_PER_LEVEL))


FACTS = {
    "hex_hours_open": lambda: _hex_hours(0),
    "hex_hours_rough": lambda: _hex_hours(1),
    "hex_miles": _hex_miles,
    "march_free_hours": _march_free,
    "march_dc_first": lambda: _march_dc(1),
    "march_dc_step": lambda: _march_dc(2) - _march_dc(1),
    "march_damage": _march_damage,
    "herb_in_progress_hours": _herb_in_progress_hours,
    "knockout_dice": _knockout_dice,
    "forge_in_progress_hours": _forge_in_progress_hours,
    "alchemy_in_progress_hours": _alchemy_in_progress_hours,
    "perk_from_level": _perk_from_level,
    "perk_picks": _perk_picks,
}

_FIELD = re.compile(r"\{([a-z_]+)\}")


def names(text: str) -> list[str]:
    """The placeholders a piece of tutorial text uses."""
    return _FIELD.findall(str(text or ""))


def fill(text: str) -> str:
    """`text` with every `{name}` replaced by the engine's value. An unknown name raises
    KeyError: the test catches that at authoring time, never the player at runtime."""
    values = {n: FACTS[n]() for n in names(text)}
    return string.Formatter().vformat(str(text or ""), (), values)
