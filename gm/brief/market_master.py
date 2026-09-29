"""THE MARKET: its counters, and its master — an authority, busy, who does not sell.

Measured on the 2026-09-28 playtest (item 10): the market was one person, "the
stallholder who runs the pitch", at once its authority and its only seller — and so the
first person every player met there, walked up to them because the trade panel needed a
body. The market is now its counters (`rules/market.py`: a general store, and in a town or
a city an armorer, a weaponsmith and an alchemist, and stalls dealt by lot), and its master
stands apart from them (`rules/audience.py`).

This section tells the narrator both halves, because a model that is not told which
counters exist invents a stallholder, and one that is not told the master is busy walks
them over to the player: the fix that held in this codebase is always the fact in the
brief plus a check on the page (`gm/checks/master_unprompted.py`), never an instruction
alone. When the player turns to the master this beat, the engine has already decided
whether they are heard (`audience.hearing`), and the section says which — with the
brush-off in the master's own words, so the prose has something true to say instead of
something invented. Being brushed off costs no regard (the owner, Q29): the section says
so, because a narrator left to guess writes the master's contempt.
"""
from __future__ import annotations

ORDER = 45
SLOT = "people"
SCAFFOLD = (
    "THE MARKET'S COUNTERS (fact):",
    "trade happens at these, never with the master.",
    "THE MASTER OF THE MARKET (fact):",
    "is the master of the market: an authority, not a seller, and they sell nothing.",
    "Busy; they do not seek the player out or speak to them first.",
    "They hear:",
    "HEARING (fact):",
    "hears the player now, because",
    "does not hear the player now, and says so without offence:",
    "The player's standing with them does not change for it.",
)

# What earns a hearing, in the words the narrator is shown (`audience.grounds`).
_HEARS = ("those they already think well of, the market's own people, anyone bringing a "
          "theft, a quarrel, a false measure or asking for a pitch, and whoever waits for "
          "the evening count")


def section(ctx) -> tuple[str, dict]:
    from rules import audience, keepers, market, places

    scene = ctx.scene
    at = str(getattr(scene, "at", "") or "")
    if not at or not market.is_market(at, getattr(scene, "founded", None) or ()):
        return "", {}
    location = ctx.location if ctx.location is not None else getattr(scene, "location_id", "")
    try:
        choices = market.counters(location)
    except Exception:
        return "", {}
    lines, facts = [], {}
    if choices:
        met = {}
        for a in scene.people.values():
            cid = keepers.counter_of(getattr(a, "world_entity_id", "") or "")
            if cid and keepers.place_of(a.world_entity_id) == at:
                met[cid] = a
        shown = [f"{x.label} ({met[x.id].name})" if x.id in met else x.label
                 for x in choices]
        lines.append(f"  THE MARKET'S COUNTERS (fact): {', '.join(shown)}; trade happens at "
                     f"these, never with the master.")
        facts["counters"] = [x.id for x in choices]
    master = keepers.master_here(scene)
    if master is not None and places.has_a_master(places.scale_of(location)):
        pc = scene.pc()
        now = keepers.occupation(master, int(getattr(scene, "clock_minutes", 0) or 0),
                                 ctx.world, str(getattr(scene, "location_id", "") or ""))
        lines.append(f"  THE MASTER OF THE MARKET (fact): {master.name} ({master.ref}) is the "
                     f"master of the market: an authority, not a seller, and they sell "
                     f"nothing. Now: {now}. Busy; they do not seek the player out or speak "
                     f"to them first. They hear: {_HEARS}.")
        facts["master"] = master.ref
        if pc is not None and audience.addressed(scene, master, ctx.player_text, ctx.reading):
            general = next((x for x in choices if x.id == "general"), None)
            nearest = ""
            if general is not None:
                who = next((a for a in scene.people.values()
                            if keepers.counter_of(getattr(a, "world_entity_id", "") or "")
                            == "general"), None)
                nearest = (f"{who.name} at {general.label}" if who is not None
                           else general.label)
            heard = audience.hearing(scene, master, pc, ctx.player_text, ctx.reading,
                                     nearest=nearest)
            facts["hearing"] = heard
            if heard["granted"]:
                lines.append(f"  HEARING (fact): {master.name} hears the player now, because "
                             f"{audience.GROUND_WORDS.get(heard['why'], heard['why'])}.")
            else:
                lines.append(f"  HEARING (fact): {master.name} does not hear the player now, "
                             f"and says so without offence: \"{heard['line']}\" The player's "
                             f"standing with them does not change for it.")
    if not lines:
        return "", {}
    return "\n" + "\n".join(lines), facts
