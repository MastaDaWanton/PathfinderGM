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

Sly Flourish, *Writing Awesome Read-Aloud Text*: decide "the one main thing you want
your players to get", keep it focused, and cut. The one thing here is the thing
already going wrong in the room; the place is the ground it happens on.
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
# adjectives; above the ceiling it is Beyond Zork's title page.
# Raised from 90-180 the same day on "i want more text and more description per
# generation"; the brief and the example grew with them, since the example is what
# the model measures itself against and the bounds only catch what it got wrong.
MIN_WORDS = 170
MAX_WORDS = 340

BRIEF = """You are the Game Master opening a tabletop campaign. Write the first thing the
player reads: four paragraphs, then a question, about 250 words in all. Each paragraph
is three or four sentences, and the second — the place — is the longest.

The order is the whole craft:
1. The thing already going wrong, first, as something seen or heard — never explained.
2. Where they are, physically: what the room or street looks, sounds and smells like,
   built from the place's own material below. Weave in ONE thing about how this place
   is run, as the reason the moment matters, not as a lecture.
3. Who they are, shown by what they carry and where they come from, never by a class
   name or a label.
4. A question that asks what they do.

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
        "Situation: Low tide. On the landing, waiting for the ferry that has not come. "
        "The porter beside you has put his load down.\n"
        "Already happening: The porters at the water's edge have stopped talking, all "
        "at once, and are looking out at the empty channel.\n\n"
        "The template says: Low tide. You are on the landing among slate roofs and "
        "stone stairs. The porters have stopped talking. You are Teodor Vance, "
        "Marrish, a long way from anyone who knows you, with a boat-hook in hand. You "
        "are waiting for the ferry. What do you do?"
    ),
    "assistant": json.dumps({"opening": (
        "The porters at the water's edge stop talking all at once. Not a lull — a "
        "stop. Twenty men with their loads down, looking out at a channel with nothing "
        "on it, and the gulls that were working the shallows have lifted off together "
        "and gone up the cliff. The only sound left is the water working at the "
        "stones.\n\n"
        "Hollin Stair climbs the cliff behind you in flights of wet stone, the houses "
        "stacked under slate, the boats drawn up at the foot with their nets steaming "
        "in the cold. Every flight of the stair has its own smell — tar at the "
        "bottom, then fish, then woodsmoke from the houses — and the whole place is "
        "wet, the steps worn to a dish in the middle by four hundred years of feet. "
        "The tide sets the day here and the boat-owners set everything else, which "
        "is why a ferry that has not come is not a delay to these men but a "
        "verdict; somebody with a hull has decided something, and the porters are "
        "waiting to find out what.\n\n"
        "You stand a little apart from them with a boat-hook in your fist and a jerkin "
        "that has seen better coasts, Marrish by your face, and nobody on this landing "
        "knows your name. You came down the stair this morning with the last of your "
        "money and a letter you have not opened, meaning to be across the water by "
        "noon.\n\n"
        "The porter beside you has not picked his load back up. What do you do?"
    )}),
}

SCHEMA = {"type": "object",
          "properties": {"opening": {"type": "string"}},
          "required": ["opening"]}

# Jerz's cop-outs, the same list `tests/test_opening.py` holds the template to.
_DECIDES = re.compile(r"you reali[sz]e|you decide|you can't bear|something tells you|"
                      r"you feel that", re.I)
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


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
    lines.append(f"Situation: {situation.when}. {situation.where}. {situation.doing}")
    lines.append(f"Already happening: {situation.edge}")
    text = "\n".join(lines)
    allowed = set(re.findall(r"\b[A-Z][A-Za-z'’-]+\b", text + " " + skeleton))
    if pc is not None:
        allowed.update(_WORD.findall(pc.name))
    return f"Material:\n{text}\n\nThe template says: {skeleton}", allowed


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
             prose: str = "", skeleton: str = "") -> list[str]:
    """Everything wrong with a draft, each named so the repair call can fix only that."""
    out = []
    if prose and skeleton and not drawn_from_the_place(text, prose, skeleton):
        out.append("it describes nothing the place's own writing describes; put one "
                   "physical detail from that writing into the second paragraph")
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
    if place_name and place_name not in text:
        out.append(f"it never says where this is; name {place_name}")
    if pc_name and pc_name.split()[0] not in text:
        out.append(f"it never says who the player is; name {pc_name}")
    if build_echo_index(text) & build_echo_index(json.loads(EXAMPLE["assistant"])["opening"]):
        out.append("it copies the example about the ferry; this is not a ferry landing")
    return out


def _ask(messages: list[dict], cfg: dict) -> str:
    # `think=False` is load-bearing, as it is on every prose call in `gm/agent.py`:
    # measured here first, the 12B gemma spent the whole budget in its thinking
    # channel and returned content "" — the format grammar constrains only the
    # content, which never started — so every draft was "0 words" and the opening
    # fell to the template three times out of three.
    reply = client.chat(messages, model=cfg["model"], host=cfg.get("host", ""),
                        provider=cfg.get("provider", "ollama"),
                        api_key=cfg.get("api_key", ""), schema=SCHEMA,
                        think=False, temperature=0.8, num_predict=900)
    try:
        text = reply.json().get("opening", "")
    except (ValueError, AttributeError):
        text = ""
    return " ".join(str(text or "").split("\r")).strip()


def write(campaign, situation, skeleton: str) -> tuple[str, list[str]]:
    """The written opening, or the skeleton, with what was wrong with the last draft.

    One write, one repair with the complaint named, then the template. Never raises:
    a model that is not running is a flat first screen, not a campaign that fails to
    start.
    """
    from . import modelcfg

    if not ENABLED:
        return skeleton, ["the written opening is switched off"]
    cfg = modelcfg.for_role("prose") or modelcfg.for_role("narrator")
    if not cfg:
        return skeleton, ["no prose model configured"]
    user, allowed = material(campaign, situation, skeleton)
    place = campaign.location
    pc = campaign.scene.pc()
    messages = [{"role": "system", "content": BRIEF},
                {"role": "user", "content": EXAMPLE["user"]},
                {"role": "assistant", "content": EXAMPLE["assistant"]},
                {"role": "user", "content": user}]
    found: list[str] = []
    try:
        draft = _ask(messages, cfg)
        found = problems(draft, allowed, place.name if place is not None else "",
                         pc.name if pc is not None else "",
                         prose=getattr(place, "prose", "") or "", skeleton=skeleton)
        if draft and not found:
            return narration.destutter(draft), []
        if draft:
            messages += [{"role": "assistant", "content": json.dumps({"opening": draft})},
                         {"role": "user", "content": "Rewrite it. What is wrong:\n"
                                                     + "\n".join(f"- {p}" for p in found)}]
            draft = _ask(messages, cfg)
            found = problems(draft, allowed, place.name if place is not None else "",
                             pc.name if pc is not None else "",
                             prose=getattr(place, "prose", "") or "", skeleton=skeleton)
            if draft and not found:
                return narration.destutter(draft), []
    except Exception as exc:                       # noqa: BLE001 — the floor is the point
        found = [f"the prose model failed: {exc}"]
    return skeleton, found
