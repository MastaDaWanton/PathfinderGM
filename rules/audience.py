"""Who the master of the market will hear, and what they say to everybody else.

Measured on the 2026-09-28 playtest (item 10): the market was one person — "the
stallholder who runs the pitch" — who was at once its authority and its only seller, and
who was the first person every player met there because the trade panel needed a body.
The market is now its counters (`rules/market.py`), and its authority stands apart from
them: the master, who sells nothing and is busy.

**Prior art** (docs/design-d-people.md §2). The medieval clerk of the market regulated
and did not trade: a court at every market "for the punishment of minor crimes", with
control over prices, weights and measures; disputes on the spot went to piepowder, where
merchants judged contract disputes, theft and violence. Skyrim's steward stands before the
authority — "The Jarl is, as you can imagine, very busy" — which is the busy master with a
go-between; Daggerfall's reputation "determines which people will talk to you". The
refusal CircleMUD's keeper gives at a shut counter ("Sorry, come back tomorrow.") is the
shape of the brush-off: it names when, and it sends the player somewhere useful.

**The grounds for a hearing**, each read off state the engine already holds (the second
law — no flag of this module's own):

- `regard`: the master is friendly or better toward the player (`attitude.of`). A
  Diplomacy request that succeeds is the engine's own sway, which moves an indifferent
  master to friendly — so "asked well" is this ground, reached through a check the engine
  rolls, and needs no rule here;
- `tie`: the player's background puts them in the market's world — a background tie at
  the `market` (the stallholder, the apprentice, the pit-fighter) or the guild-clerk's —
  read from the background document through the character's `background:<id>` effect;
- `their_business`: the player brings what a master of the market is for — a dispute, a
  theft, a false measure, a pitch to be had (`matter_of`), or the player being wanted in
  this town, which is the master's business whether the player likes it or not;
- `the_count`: it is the evening count, the slot the brush-off tells people to come back
  in (`keepers.COUNT_SLOT`), so the promise the line makes is one the rule keeps.

Otherwise the player is **brushed off**, and it costs no regard (the owner, Q29): nothing
here writes to the attitude track. Pressing on after a refusal is an ordinary Diplomacy
check, which already has a failure of its own.
"""
from __future__ import annotations

import re

# What a master of the market is there for, in the player's words. Detected, never
# guessed at by a model (CLAUDE.md: detect mechanically). The first match wins, in this
# order, so "someone stole from my pitch" is a theft and not a pitch.
MATTERS: tuple[tuple[str, re.Pattern], ...] = (
    ("theft", re.compile(r"\b(?:stole|stolen|steal(?:s|ing)?|thie(?:f|ves|ving)|robbed|"
                         r"cutpurse|pickpocket|swindl\w*|cheat(?:ed|ing|s)?)\b", re.I)),
    ("measure", re.compile(r"\b(?:false|short|light|crooked|rigged)\s+(?:weights?|"
                           r"measures?|scales?|balance)\b|\bshort[- ]weight\w*\b|"
                           r"\bgave me short\b", re.I)),
    ("dispute", re.compile(r"\b(?:dispute|quarrel|complain(?:t|ts|ing)?|grievance|"
                           r"owe[sd]?|debt|refused to pay|won't pay|wont pay|"
                           r"fair price|overcharg\w*)\b", re.I)),
    # "a stall" alone is where the player shops; a stall of their own is a pitch.
    ("pitch", re.compile(r"\b(?:a|my own|our own|rent a|take a)\s+pitch\b|"
                         r"\b(?:my|our) own stall\b|\bset up (?:a )?stall\b|"
                         r"\blicen[cs]e to (?:sell|trade)\b|"
                         r"\bsell (?:my|our) (?:own )?(?:goods|wares)\b", re.I)),
)

# Background ties that put a character in the market's world (content/backgrounds): the
# tie's `place` is the market, or the background is the guild's own clerk.
TIE_PLACES = frozenset({"market"})
TIE_BACKGROUNDS = frozenset({"guild-clerk"})

GROUND_WORDS = {
    "regard": "they already think well of the player",
    "tie": "the player is one of the market's own people, by their past",
    "their_business": "the player brings the master's own business",
    "the_count": "it is the evening count, when the master hears whoever has waited",
}


def matter_of(player_text: str, reading=None) -> str:
    """"theft" / "measure" / "dispute" / "pitch" / "" — what the player brings, from
    their own words (and the reading's own words for its acts, when there is one)."""
    text = " ".join([str(player_text or "")] + [
        str(a.get("target") or "") + " " + str(a.get("about") or "")
        for a in ((reading or {}).get("actions") or []) if isinstance(a, dict)])
    for name, pattern in MATTERS:
        if pattern.search(text):
            return name
    return ""


def _background_of(pc) -> dict:
    """The background document this character's bound background effect names."""
    from . import backgrounds

    for e in getattr(pc, "effects", None) or ():
        source = str(getattr(e, "source", "") or "")
        if getattr(e, "kind", "") == "background" and source.startswith("background:"):
            return backgrounds.get(source.split(":", 1)[1]) or {}
    return {}


def tie_ground(pc) -> bool:
    doc = _background_of(pc)
    if not doc:
        return False
    if str(doc.get("id") or "") in TIE_BACKGROUNDS:
        return True
    return any(str(t.get("place") or "") in TIE_PLACES for t in doc.get("ties") or ()
               if isinstance(t, dict))


def addressed(scene, master, player_text: str = "", reading=None) -> bool:
    """Whether the player turned to the master this beat: the reading's talk, seek or call
    lands on them, the player said their name, or asked for the master by their office."""
    if master is None:
        return False
    from . import hooks

    for _act, target in hooks.targets(reading):
        if hooks.resolve_target(scene, None, target) == master.ref:
            return True
        if re.search(r"\bmaster\b|\bclerk of the market\b", target, re.I):
            return True
    text = str(player_text or "")
    if re.search(r"\b(?:master|clerk) of the market\b|\bmarket(?:'s)? master\b", text, re.I):
        return True
    # The words of their NAME, which is a proper name only once given: since owner ruling
    # F1 (2026-09-30) the master goes by "the master of the market" until introduced, and
    # every word of that — "the" among them — matched any sentence at all. The office is
    # the regex above; this is the given name.
    names = {w.lower() for w in re.findall(r"[A-Z][A-Za-z]{2,}", str(master.name or ""))}
    said = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", text)}
    return bool(names and names & said)


def grounds(scene, master, pc, player_text: str = "", reading=None) -> list[str]:
    """Every ground the player has for a hearing, in the order they are tried."""
    from . import attitude, states
    from .keepers import COUNT_SLOT
    from .residency import slot_of

    out = []
    if attitude.step_of(attitude.of(master)) >= attitude.step_of(attitude.COMES_ALONG):
        out.append("regard")
    if tie_ground(pc):
        out.append("tie")
    if matter_of(player_text, reading) or states.standing_with_the_law(
            pc, str(getattr(scene, "location_id", "") or "")) == "wanted":
        out.append("their_business")
    if slot_of(int(getattr(scene, "clock_minutes", 0) or 0)) == COUNT_SLOT:
        out.append("the_count")
    return out


def brush_off_line(scene, master, nearest: str = "") -> str:
    """What the master says to somebody they will not hear now: busy, when they will be
    free, and where ordinary questions go — shaped like `keepers.shut_line`."""
    from .keepers import COUNT_SLOT
    from .residency import slot_of

    who = str(getattr(master, "name", "") or "The master of the market")
    slot = slot_of(int(getattr(scene, "clock_minutes", 0) or 0))
    when = ("this evening, at the day's count" if slot < COUNT_SLOT
            else "tomorrow evening, at the day's count")
    send = (f" For anything to buy, {nearest} will serve you." if nearest
            else " For anything to buy, ask at the stalls.")
    return (f"{who} has the market to run and no time now; {who} hears people {when}."
            + send)


def hearing(scene, master, pc, player_text: str = "", reading=None,
            nearest: str = "") -> dict:
    """{"granted": bool, "why": str, "line": str} for the player seeking the master now.

    `why` is the first ground that holds (`GROUND_WORDS`), or "brushed off". `line` is
    the brush-off in the master's own terms, or "" when they hear the player. Reads only;
    a brush-off costs no regard (Q29), so nothing here writes."""
    got = grounds(scene, master, pc, player_text, reading)
    if got:
        return {"granted": True, "why": got[0], "line": ""}
    return {"granted": False, "why": "brushed off",
            "line": brush_off_line(scene, master, nearest)}
