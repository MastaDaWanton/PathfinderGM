"""The opening, written — from material the app assembled and checked against it.

`opening.compose` builds the first screen out of the export's fields, and it is
honest, grounded and flat: "Vyrakon keeps to matriarchal clan law. The day here is
morning markets and evening prayers. Just past noon. You are in a crowded common
room." The player's verdict on it, 2026-09-04: "there is absolutely no description of
the place i am in. this is a failure." Their critique was specific — lore first and
the tension buried, a class label where a person should be, a phrase repeated, and
nothing you could see, hear or smell — and their own revision put the silence first,
wove the law into why the silence matters, and showed the fighter as a hand near a
blade.

A template cannot do that; a model can, and invents. So this is the repo's standing
shape for model prose: the app supplies the material (the place's own paragraphs, the
character's own sheet, the situation the dice rolled), the model writes, and the
result is *checked mechanically* against the material before it is shown — names it
did not get from the material, digits, a missing question, a copied example, a
decision made for the player — and repaired once with the complaint named, or
dropped for the template. The template is the floor, never the ceiling.

The second verdict, 2026-09-05, after many starts: "the order of information is
strange … I have no idea what is going on or where i am. hardly even know what i am
supposed to be doing." That is the oldest finding in interactive fiction. Emily
Short, on an opening where "the player's goal is not sufficiently obvious": give
them "an obvious starting problem, even if it's not the main goal of the game", and
a prologue "should have a very clearly articulated goal" and set up "the player's
character and long-term motivation" (*Plot, scene by scene*; *WIP Rescue*). Nelson's
overture said who, where, what — it never said WHY, and a player who does not know
why they are standing there cannot choose anything. So the opening now carries an
errand — why the character came here today — and the order is the order a person
orients in: where am I, why am I here and what am I doing, what is happening, and
what could I do about it.
"""
from __future__ import annotations

import json
import re

from gm import client, narration
from gm.narration import build_echo_index, invented_names

# Whether the model is asked at all. The test suite turns this off in `conftest.py`:
# with Ollama up, 166 tests that start a campaign each paid a ten-second prose call
# and the two-minute suite took more than ten — and with Ollama down, each paid a
# refused connection. Tests of this module turn it back on and stub the client.
ENABLED = True

# The bounds the checks hold the prose to. Below the floor it is the template with
# adjectives; above the ceiling it is Beyond Zork's title page. Raised from 90-180 on
# "i want more text and more description per generation"; the brief and the example
# grew with them, since the example is what the model measures itself against.
MIN_WORDS = 200
MAX_WORDS = 380

BRIEF = """You are the Game Master opening a tabletop campaign. Write the first thing the
player reads: four paragraphs, then a question, about 280 words in all. Each paragraph
is three to five sentences.

The order is how a person orients, and it is the whole craft:
1. WHERE. Name the place and say what kind of place it is, then the exact spot the
   player is standing in — what it looks, sounds and smells like, built from the
   place's own writing below. This is the longest paragraph.
2. WHY. Who the player is (shown by what they carry and where they come from, never
   a class name), why they came here today — the errand in the material — and what
   they are doing at this moment.
3. WHAT. The thing already happening, as seen and heard from where they stand; then
   what it looks like it means to someone standing there, drawn from how the place
   is run or from what is really going on underneath. Show the visible edge of that;
   never state its cause outright. The person beside them belongs here.
4. NOW. Two or three concrete things the player could do next, in one sentence, and
   then the question of what they do.

Then give two to four short suggestions — one line each, in the player's voice, each
one a thing they could say or do right now.

Use only names that appear in the material. Never write digits. Never decide for the
player ("you realise", "you decide", "something tells you"). Write to the player as
"you"."""

# One demonstration, and about nowhere the table can roll: no common room, market,
# yard, well, gate, square, workshop, doorway, cart, step, crossing or ritual. The
# Continue examples taught this repo that the model finishes the nearest stopped thing
# in front of it, so the example is a ferry landing — copyable, and caught if copied.
EXAMPLE = {
    "user": (
        "Material:\n"
        "Place: Hollin Stair. Its facts: Architecture: slate roofs, stone stairs cut "
        "into the cliff; Formal Power: a harbour reeve elected by the boat-owners; "
        "Daily Norms: the tide sets the day.\n"
        "The place's own writing: Hollin Stair climbs its cliff in flights of stone, "
        "the boats drawn up at the foot and the houses stacked above them under slate. "
        "The reeve is chosen by whoever owns a hull, so the fishing families decide "
        "everything and the porters carry it.\n"
        "Character: Teodor Vance. Heritage: Marrish, a long way from anyone who knows "
        "you. Carrying: a boat-hook, a leather jerkin.\n"
        "Why they are here today: You came to be across the water by noon, with the "
        "last of your money and a letter you have not opened.\n"
        "Situation: Low tide. On the landing, waiting for the ferry that has not come. "
        "The porter beside you has put his load down.\n"
        "Already happening: The porters at the water's edge have stopped talking, all "
        "at once, and are looking out at the empty channel.\n"
        "What is really going on underneath (show its visible edge only): the "
        "boat-owners have quietly agreed to stop the ferry until the reeve is replaced.\n\n"
        "The template says: Low tide. You are on the landing among slate roofs and "
        "stone stairs. You are Teodor Vance, Marrish, a long way from anyone who knows "
        "you, with a boat-hook in hand. You came to be across the water by noon. You "
        "are waiting for the ferry. The porters have stopped talking. What do you do?"
    ),
    "assistant": json.dumps({"opening": (
        "Hollin Stair is a fishing town that climbs its cliff in flights of wet stone, "
        "the houses stacked under slate above the boats drawn up at the foot. You are "
        "on the landing at the bottom of it, where the stair meets the water: a shelf "
        "of black rock slick with weed, nets steaming in the cold, the smell of tar "
        "and fish and, from the houses above, woodsmoke. The steps behind you are worn "
        "to a dish in the middle by four hundred years of feet. The tide is out, and "
        "the channel beyond the landing is a stretch of grey water with nothing on "
        "it.\n\n"
        "You are Teodor Vance, Marrish by your face, with a boat-hook in your fist "
        "and a jerkin that has seen better coasts, and nobody on this landing knows "
        "your name. You came down the stair this morning with the last of your money "
        "and a letter you have not opened, meaning to be across the water by noon; "
        "the ferry is the only way over, and you have been standing here long enough "
        "to have counted the boats twice.\n\n"
        "The porters at the water's edge have stopped talking, all at once. Not a lull "
        "— a stop. Twenty men with their loads down, looking out at the empty channel, "
        "and the gulls have lifted off the shallows together. The tide sets the day "
        "here and the boat-owners set everything else, which is why a ferry that has "
        "not come is not a delay to these men but a verdict: somebody with a hull has "
        "decided something, and the porters are waiting to find out what. The porter "
        "beside you has not picked his load back up.\n\n"
        "You could ask him what a stopped ferry means here, go up the stair and find "
        "whoever owns the boats, or open the letter while you wait. What do you do?"
    ), "suggestions": [
        "Ask the porter beside me what a stopped ferry means here",
        "Climb the stair and find who owns the boats",
        "Open the letter while I wait",
    ]}),
}

SCHEMA = {"type": "object",
          "properties": {"opening": {"type": "string"},
                         "suggestions": {"type": "array", "items": {"type": "string"}}},
          "required": ["opening", "suggestions"]}

# Jerz's cop-outs, the same list `tests/test_opening.py` holds the template to.
_DECIDES = re.compile(r"you reali[sz]e|you decide|you can't bear|something tells you|"
                      r"you feel that", re.I)

# The ferry landing's own furniture — what a draft has taken from the EXAMPLE rather
# than from this place. Same device as `gm.narration._EXAMPLE_MARKS`.
#
# Measured 2026-09-18 on a player's opening (the log line reads "opening fell back to
# the template: it copies the example about the ferry"): both drafts shared one
# six-word run with the example and were thrown away for the template, which is a
# third shorter than either. Reproduced the same morning on a different character,
# one write in three. The run in question is the kind of stock English the example
# and the material both use — "with the last of your money" — and a six-word match
# on stock English is a coincidence, not a copy. A copy carries the ferry's nouns.
EXAMPLE_MARKS = frozenset({
    "hollin", "stair", "teodor", "vance", "marrish", "ferry", "landing", "porter",
    "porters", "reeve", "tide", "channel", "gulls", "shallows", "hull", "jerkin",
    "slate", "cliff", "weed", "nets", "woodsmoke", "verdict", "coasts", "dish",
})
# How many shared runs make a copy even without a ferry noun in them: three six-word
# runs is a sentence lifted whole, whatever it is about.
COPIED_RUNS = 3


def copied_from_the_example(text: str) -> list[str]:
    """The six-word runs a draft shares with the worked example that are copying
    rather than coincidence, as phrases the repair can be told to remove."""
    shared = build_echo_index(text) & build_echo_index(
        json.loads(EXAMPLE["assistant"])["opening"])
    if not shared:
        return []
    marked = [g for g in shared if set(g) & EXAMPLE_MARKS]
    if not marked and len(shared) < COPIED_RUNS:
        return []
    return sorted({" ".join(g) for g in (marked or shared)})[:4]


# The problems that make the template the better first screen. Everything else
# `problems` reports is a reason to ask for a rewrite, not a reason to prefer the
# template: measured 2026-09-18, a draft short of the word floor by a dozen words was
# being dropped for a template a third shorter still, and a draft that had not quoted
# the place's own paragraphs for one that quotes only its facts. The template is the
# floor for prose that is *wrong* — the wrong place, no player, a decided outcome, a
# person who does not exist, a number, the ferry — not for prose that is merely less
# than was asked.
_SOFT = ("only ", "it describes nothing", "give two to four suggestions")


def hard_problems(found: list[str]) -> list[str]:
    return [p for p in found if not p.startswith(_SOFT)]
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


def underneath(campaign) -> str:
    """The campaign's undercurrent, from the GM's private note, or "".

    The note is the one place the thread lives (`opening.private_note`), so this
    reads it back rather than rolling again — a second roll would be a second story.
    """
    from . import opening

    for h in getattr(campaign, "history", None) or []:
        if str(h.get("content", "")).startswith(opening.NOTE_PREFIX):
            return opening.note_thread(h["content"])
    return ""


def material(campaign, situation, skeleton: str) -> tuple[str, set[str]]:
    """What the model may draw on, and every name it is allowed to use.

    The allowed set is every capitalised word in the material rather than a curated
    list, because the place's paragraphs name markets, councils and treaties the
    export never lists as entities, and a check that reported "Salt Market" as an
    invention would be refusing the world's own words.
    """
    place, pc = campaign.location, campaign.scene.pc()
    lines = []
    if place is not None:
        facts = "; ".join(f"{k}: {v}" for k, v in (place.facts or {}).items())
        lines.append(f"Place: {place.name}." + (f" Its facts: {facts}." if facts else ""))
        prose = (getattr(place, "prose", "") or "").strip()
        if prose:
            lines.append(f"The place's own writing: {prose}")
    if pc is not None:
        carrying = ", ".join(pc.carried()) or "nothing much"
        people = campaign.world.get(pc.world_people_id) if pc.world_people_id else None
        heritage = people.name if people is not None else (pc.heritage or pc.race or "")
        lines.append(f"Character: {pc.name}. Heritage: {heritage}. Carrying: {carrying}.")
    if situation.errand:
        lines.append(f"Why they are here today: {situation.errand}")
    lines.append(f"Situation: {situation.when}. {situation.where}. {situation.doing}")
    lines.append(f"Already happening: {situation.edge}")
    thread = underneath(campaign)
    if thread:
        lines.append("What is really going on underneath (show its visible edge only, "
                     f"never its cause): {thread}")
    text = "\n".join(lines)
    allowed = set(re.findall(r"\b[A-Z][A-Za-z'’-]+\b", text + " " + skeleton))
    if pc is not None:
        allowed.update(_WORD.findall(pc.name))
    # The template's own "You could …" line is withheld: shown it, the model copied
    # it word for word on three drafts of three ("go and see for yourself, or keep to
    # what you came here for") while its separate suggestions were specific and good.
    # The choices are the model's to write from the scene it just wrote.
    shown = "\n\n".join(p for p in skeleton.split("\n\n") if not p.startswith("You could "))
    return f"Material:\n{text}\n\nThe template says: {shown}", allowed


_STOP = {"the", "and", "that", "with", "from", "this", "here", "there", "their", "which",
         "have", "been", "were", "your", "into", "over", "under", "than", "them", "they",
         "what", "when", "where", "about", "after", "before", "through", "while", "would",
         "could", "should", "these", "those", "other", "every", "still", "being"}


def drawn_from_the_place(text: str, prose: str, skeleton: str) -> list[str]:
    """The words the draft took from the place's own writing that the template did
    not already hand it.

    Measured on the first three live drafts, 2026-09-04: every one passed every other
    check and not one used the paragraphs — the Salt Market, the cyclone coast, the
    flooded low districts — because the template's facts were nearer to hand. "Take
    a detail from the place's writing" is an instruction, and instructions lose; a
    check that fails the draft and names the fix is what holds.
    """
    def words(s: str) -> set[str]:
        # Letters only, so "cyclone-prone" yields "cyclone" and "prone" — a draft that
        # writes "cyclone winds" has taken the detail even though it split the word.
        return {w.lower() for w in re.findall(r"[A-Za-z]{5,}", s or "")} - _STOP
    return sorted((words(text) & words(prose)) - words(skeleton))


def problems(text: str, allowed: set[str], place_name: str, pc_name: str,
             prose: str = "", skeleton: str = "",
             suggestions: list[str] | None = None) -> list[str]:
    """Everything wrong with a draft, each named so the repair call can fix only that."""
    out = []
    if prose and skeleton and not drawn_from_the_place(text, prose, skeleton):
        out.append("it describes nothing the place's own writing describes; put one "
                   "physical detail from that writing into the first paragraph")
    words = len(text.split())
    if words < MIN_WORDS:
        out.append(f"only {words} words — it needs at least {MIN_WORDS}")
    if words > MAX_WORDS:
        out.append(f"{words} words — cut it to under {MAX_WORDS}")
    if not text.rstrip().endswith("?"):
        out.append("it must end with the question of what the player does")
    if re.search(r"\d", text):
        out.append("it contains digits; write no numbers")
    if m := _DECIDES.search(text):
        out.append(f'"{m.group(0)}" decides for the player; describe, do not decide')
    for name in invented_names(text, allowed):
        out.append(f"{name!r} is a name the material does not contain; remove it")
    # Where first: the place is named in the first paragraph or the reader is lost
    # before the second. "I have no idea … where i am" was said of an opening that
    # named the place in its second paragraph, after the thing going wrong.
    first = text.split("\n\n")[0] if text else ""
    if place_name and place_name not in text:
        out.append(f"it never says where this is; name {place_name}")
    elif place_name and place_name not in first:
        out.append(f"the first paragraph must say where this is; name {place_name} in it")
    # Case-blind: every character on the player's own shelf is saved in lowercase
    # ("john", "dorito", "spooter"), and a model writing "John" has named the player.
    if pc_name and pc_name.split()[0].lower() not in text.lower():
        out.append(f"it never says who the player is; name {pc_name}")
    copied = copied_from_the_example(text)
    if copied:
        # Named, so the repair can find them. "It copies the example" on its own is a
        # blind retry — the lesson `gm.narration.review` learned on the same check —
        # and a blind retry against a model that shares one stock phrase with the
        # example produced a second draft sharing another.
        out.append("it copies the example about the ferry, word for word: "
                   + "; ".join(repr(p) for p in copied)
                   + " — this is not a ferry landing; say those parts in this place's "
                     "own words")
    if suggestions is not None:
        clean = [s for s in suggestions if isinstance(s, str) and 3 <= len(s.split()) <= 16]
        if not 2 <= len(clean) <= 4:
            out.append("give two to four suggestions, each one short line in the "
                       "player's voice")
    return out


def _ask(messages: list[dict], cfg: dict) -> tuple[str, list[str]]:
    # `think=False` is load-bearing, as it is on every prose call in `gm/agent.py`:
    # measured here first, the 12B gemma spent the whole budget in its thinking
    # channel and returned content "" — the format grammar constrains only the
    # content, which never started — so every draft was "0 words" and the opening
    # fell to the template three times out of three.
    reply = client.chat(messages, model=cfg["model"], host=cfg.get("host", ""),
                        provider=cfg.get("provider", "ollama"),
                        api_key=cfg.get("api_key", ""), schema=SCHEMA,
                        think=False, temperature=0.8, num_predict=1100)
    try:
        data = reply.json()
        text, offered = data.get("opening", ""), data.get("suggestions", [])
    except (ValueError, AttributeError):
        text, offered = "", []
    # A model that writes "\n" inside the JSON string hands back a literal backslash-n;
    # measured on the second live draft, "grain.\n\nThe room is still".
    text = str(text or "").replace("\\n", "\n").replace("\r", "")
    offered = [" ".join(str(s).split()) for s in (offered or []) if str(s).strip()]
    return text.strip(), offered


def write(campaign, situation, skeleton: str,
          fallback_suggestions: list[str] | None = None
          ) -> tuple[str, list[str], list[str]]:
    """The written opening and its suggestions, or the skeleton and the template's,
    with what was wrong with the last draft.

    One write, one repair with the complaint named, then the template. Never raises:
    a model that is not running is a flat first screen, not a campaign that fails to
    start.
    """
    from . import modelcfg

    floor = (skeleton, list(fallback_suggestions or []))
    if not ENABLED:
        return *floor, ["the written opening is switched off"]
    cfg = modelcfg.for_role("prose") or modelcfg.for_role("narrator")
    if not cfg:
        return *floor, ["no prose model configured"]
    user, allowed = material(campaign, situation, skeleton)
    place = campaign.location
    pc = campaign.scene.pc()
    messages = [{"role": "system", "content": BRIEF},
                {"role": "user", "content": EXAMPLE["user"]},
                {"role": "assistant", "content": EXAMPLE["assistant"]},
                {"role": "user", "content": user}]

    def check(draft, offered):
        return problems(draft, allowed, place.name if place is not None else "",
                        pc.name if pc is not None else "",
                        prose=getattr(place, "prose", "") or "", skeleton=skeleton,
                        suggestions=offered)

    found: list[str] = []
    best: tuple[str, list[str], list[str]] | None = None
    try:
        draft, offered = _ask(messages, cfg)
        found = check(draft, offered)
        if draft and not found:
            return narration.destutter(draft), offered, []
        if draft and not hard_problems(found):
            best = (draft, offered, found)
        if draft:
            messages += [{"role": "assistant",
                          "content": json.dumps({"opening": draft, "suggestions": offered})},
                         {"role": "user", "content": "Rewrite it. What is wrong:\n"
                                                     + "\n".join(f"- {p}" for p in found)}]
            draft, offered = _ask(messages, cfg)
            found = check(draft, offered)
            if draft and not found:
                return narration.destutter(draft), offered, []
            if draft and not hard_problems(found):
                best = (draft, offered, found)
    except Exception as exc:                       # noqa: BLE001 — the floor is the point
        found = [f"the prose model failed: {exc}"]
    # A draft that is merely less than was asked — a dozen words under the floor, not
    # quoting the place's paragraphs — still beats the template, provided it is at
    # least the template's length: the template is the floor for prose that is
    # WRONG. The soft problems are returned so the caller can record them; they
    # are not a reason to ship a third less text (see `hard_problems`).
    if best is not None and len(best[0].split()) >= len(skeleton.split()):
        draft, offered, soft = best
        clean = [s for s in offered if isinstance(s, str) and 3 <= len(s.split()) <= 16]
        return (narration.destutter(draft),
                clean[:4] if 2 <= len(clean) else list(fallback_suggestions or []),
                soft)
    return *floor, found
