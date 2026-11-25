"""The senses a world's people have, read out of the world's own words by a model.

Playtest 2026-11-23 #2 and the owner's ruling O6 (2026-11-25): *"if an undine doesn't have
darkvision it is an oversight, how could they live underwater otherwise."* Aurvantis's
Undine card says "sees clearly underwater" and "gills at the throat let them breathe
underwater", states `amphibious` and a swim speed, and nothing else; the cue table in
`rules/races.py` never runs on a card that states its tags, so the player's undine had no
darkvision at all and fought the tower's dark rooms half blind.

**Models read, code validates** (owner, 2026-10-03; docs/structured-turn.md). The model is
handed one people's words and answers four yes-or-no questions under a JSON schema whose
properties are all required (required properties ARE enforced by Ollama, 6/6 probed —
memory ollama-schema-enforcement), plus a short reason it writes first. Code maps each
yes to one tag of the closed list `races.SENSE_TAGS`; no model writes a tag, a range or a
number, so a reply cannot name a sense the engine has no reader for.

**What the traditions do.** Every system that imports creatures from prose reads senses
into a fixed list: Foundry's PF1 actor sheet keeps `senses` as named fields (darkvision,
low-light, scent, blindsense ...) rather than free text, and the Bestiary prints a
creature's senses as a closed line ("darkvision 60 ft., low-light vision"). The regex cue
table this app already had (`races.CUES`) is the abandoned shape here: it fired on
"night vision" and missed every world that described a way of life rather than an eye
("they live under the water"), which is exactly the inference the owner made.

**When it runs.** Once per people per wording, stored with a checksum of the words
(`races.remember_senses`), never on the turn path: in the background when a campaign
loads (the player's own race first) and when the forge lists a world's races. A save
made before this gains the sense on the next race read after the reading lands — nothing
is written onto the character, the race document is read live (`Actor._race_doc`).
"""
from __future__ import annotations

import json
import logging
import threading

ENABLED = True

_SYSTEM = (
    "You read a description of one people from a fantasy world and say which senses "
    "their bodies have. A sense counts when the words show it, or when the people's own "
    "way of life could not work without it: a people who live under the water, under the "
    "ground or in other lightless places must see without light; a people who hunt or "
    "work by night see well in dim light. Ordinary sight is all a people has when the "
    "words show nothing more. Answer with JSON only.")

# Demonstrations, not rules (CLAUDE.md: demonstration volume beats instruction volume).
# Invented peoples, none of any shipped world's, so the reader learns the inference and
# not an answer to copy.
_SHOTS = (
    ("Tarn-folk", "Long-limbed and grey-skinned. Breathe through slits behind the jaw and "
                  "live in the lake itself, seeing clearly beneath the water.",
     {"reason": "they live under the water, where the light fails",
      "sees_in_darkness": True, "sees_in_dim_light": False, "keen_scent": False,
      "senses_without_sight": False}),
    ("Furrowmen", "Stocky, sun-browned farmers of the river plains. Ordinary eyes and ears.",
     {"reason": "nothing beyond ordinary senses is shown",
      "sees_in_darkness": False, "sees_in_dim_light": False, "keen_scent": False,
      "senses_without_sight": False}),
    ("Vashri", "Slit-pupiled hunters who sleep by day and stalk their prey under the "
               "moon, following its trail by smell.",
     {"reason": "they hunt at night and track by scent",
      "sees_in_darkness": False, "sees_in_dim_light": True, "keen_scent": True,
      "senses_without_sight": False}),
    ("Hollow-born", "Small, pale and large-eyed; born in the deep caverns and never see "
                    "the sun. They find one another in the tunnels by clicks and echoes.",
     {"reason": "they live underground without light and find their way by echoes",
      "sees_in_darkness": True, "sees_in_dim_light": False, "keen_scent": False,
      "senses_without_sight": True}),
)

# Each yes, and the one tag of the vocabulary it means (`races.SENSE_TAGS`).
ANSWERS = {
    "sees_in_darkness": "sense.darkvision.60",
    "sees_in_dim_light": "sense.low-light",
    "keen_scent": "sense.scent",
    "senses_without_sight": "sense.blindsense.30",
}

SCHEMA = {"type": "object", "properties": {
    "reason": {"type": "string"},
    **{k: {"type": "boolean"} for k in ANSWERS}},
    "required": ["reason", *ANSWERS]}


def _user(name: str, words: str) -> str:
    return f"PEOPLE: {name}\nTHEIR WORDS: {words or '(nothing written)'}"


def messages(name: str, words: str) -> list[dict]:
    out = [{"role": "system", "content": _SYSTEM}]
    for who, said, answer in _SHOTS:
        out.append({"role": "user", "content": _user(who, said)})
        out.append({"role": "assistant", "content": json.dumps(answer)})
    out.append({"role": "user", "content": _user(name, words)})
    return out


def tags_from(answer: dict) -> list[str]:
    """The vocabulary's tags for a reply's yeses; anything else in it is ignored."""
    from rules import races

    return races.valid_senses(tag for key, tag in ANSWERS.items()
                              if isinstance(answer, dict) and answer.get(key) is True)


def read(name: str, words: str, *, chat=None, cfg: dict | None = None) -> list[str] | None:
    """The tags one people's words read as, or None when the model could not be asked
    (nothing is stored then, so the next load asks again)."""
    if chat is None:
        from . import client

        chat = client.chat
    if cfg is None:
        from play import modelcfg

        cfg = modelcfg.for_role("interpreter")
        if not cfg.get("model"):
            cfg = modelcfg.for_role("narrator")
    try:
        reply = chat(messages(name, words), cfg.get("model"), cfg.get("host"),
                     as_json=True, think=False, temperature=0.0, num_predict=160,
                     provider=cfg.get("provider", "ollama"), api_key=cfg.get("api_key", ""),
                     schema=SCHEMA, remember_stall=False)
        got = reply.json()
    except Exception:  # noqa: BLE001 — unread stays unread; the race keeps its stated tags
        return None
    if not isinstance(got, dict) or any(not isinstance(got.get(k), bool) for k in ANSWERS):
        return None
    return tags_from(got)


def read_world(world, first: str = "", *, chat=None, cfg=None) -> dict[str, list[str]]:
    """Read every people of `world` not yet read from its current words, `first` (a race
    id) before the rest. Stops at the first call that fails: a model that is down for one
    is down for all of them. Returns {key: tags} for what it read."""
    from rules import races

    rows = races.sense_sources(world)
    want = races.slug(first) if first else ""
    rows.sort(key=lambda r: 0 if want and want in (races.slug(r["name"]), r["key"]) else 1)
    out: dict[str, list[str]] = {}
    for row in rows:
        if races.senses_read(row["world"], row["key"], row["words"]) is not None:
            continue
        tags = read(row["name"], row["words"], chat=chat, cfg=cfg)
        if tags is None:
            break
        out[row["key"]] = races.remember_senses(row["world"], row["key"], row["words"], tags)
    return out


_BUSY: set[str] = set()
_LOCK = threading.Lock()


def in_background(world_key: str, first: str = "") -> bool:
    """`read_world` on a daemon thread, one per world at a time. Nobody waits on it: the
    race documents pick the readings up as they land. Returns whether one was started."""
    key = str(world_key or "").strip()
    if not ENABLED or not key:
        return False
    with _LOCK:
        if key in _BUSY:
            return False
        _BUSY.add(key)

    def work():
        try:
            from play import library

            world = library.world(key)
            if world is not None:
                read_world(world, first)
        except Exception:  # noqa: BLE001 — a reading never takes the app down
            logging.getLogger(__name__).exception("reading %s's senses failed", key)
        finally:
            with _LOCK:
                _BUSY.discard(key)

    threading.Thread(target=work, daemon=True, name=f"race-senses:{key}").start()
    return True
