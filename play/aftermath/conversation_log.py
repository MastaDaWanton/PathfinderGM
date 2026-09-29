"""What was said, per person: the conversation log's one writer (docs/design-f-ui.md §4.2).

Playtest item 7.1: "a log of what has been said… just the dialogue and vocalizations such
as grunting or laughing". Every beat, after it is on the page, this step appends to
`Scene.conversation_log` (docs/fix-interfaces.md §2.4, the Entry of §2.10):

  * the NPC lines the prose call tagged and `_finish` kept on the beat (its `said`) — so a
    line a groomer cut is never logged, because it was never kept;
  * the player's own QUOTED words (`speech.lines(player_text)`). Owner, Q43: quoted words
    only — "I ask him about the girl" is an action, not a line. Continue carries no words,
    so it records nothing;
  * vocalisations (`speech.vocalisations`): an NPC's from the GM prose, the player's own
    only from the player's text ("I laugh", "*grunts*"). The narrator does not decide what
    the player's character did, so a PC grunt in the prose is never booked.

NPC reported speech ("Drenn asks where you're headed") is narration and is not logged
(owner, Q44). Neither is scenery: every `line` entry is a quotation of its beat or of the
player's words, and every `vocal` entry lies outside quotation marks.

**Persisted, not derived** (design F §4.2): a person deleted from the scene takes their
name with them, and who was in the conversation at that moment is recorded nowhere else,
so each entry snapshots `name` and `among`. Append-only; `n` is never reused.

**The cap** (owner, Q6: 300, no backfill): each person keeps at least their newest 300
entries. An entry goes only when every person it involves already has 300 newer ones, so
one chatty companion cannot push a quiet stranger's three lines out of the log. Old saves
start empty — the `said` on beats before this step are not replayed into it.

A vocal word the detector could not give a speaker is a `vocal-miss` turn-log row, so
recall is measured before anyone reaches for a tag (design F §4.2).
"""
from __future__ import annotations

STAGE = "beat"
ORDER = 50
# The opening companion's first lines are logged too (owner, Q48), through
# `aftermath.after_opening`, which Lane C calls at the end of `new_campaign`.
DOORS = frozenset({"turn", "carry_on", "opening"})

CAP = 300


def _pc_words(phrase: str) -> str:
    """The player's own sound in the second person the page speaks in: "*grunts*" is
    shown as "You grunt", "*lets out a sigh*" as "You let out a sigh"."""
    words = phrase.split()
    if not words:
        return phrase
    first = words[0]
    low = first.lower()
    if low == "lets":
        first = "let"
    elif low.endswith(("sses", "shes", "ches", "xes", "zes")):
        first = first[:-2]
    elif low.endswith("s") and not low.endswith("ss") and low not in ("was", "has"):
        first = first[:-1]
    return " ".join([first] + words[1:])


def _involved(entry: dict) -> list[str]:
    """Whose log an entry is in (design F §4.2): who said it, who it was said to, and —
    for the player's words — everyone in the conversation. "" stands for nobody."""
    refs = []
    for r in [entry.get("who"), entry.get("to")]:
        if r and r != "you":
            refs.append(str(r))
    if entry.get("who") == "you":
        refs += [str(r) for r in entry.get("among") or []]
    return list(dict.fromkeys(refs)) or [""]


def capped(log: list[dict], cap: int = CAP) -> list[dict]:
    """The log with the entries dropped that no one needs any more: newest first, an entry
    is kept while any person it involves has fewer than `cap` newer ones kept."""
    counts: dict[str, int] = {}
    keep: list[dict] = []
    for entry in reversed(log):
        refs = _involved(entry)
        if any(counts.get(r, 0) < cap for r in refs):
            keep.append(entry)
            for r in refs:
                counts[r] = counts.get(r, 0) + 1
    keep.reverse()
    return keep


def _player_beat(transcript: list, gm_beat: int | None) -> int | None:
    """The transcript index of the player's line this beat answers."""
    if gm_beat is None:
        return None
    for i in range(min(gm_beat, len(transcript)) - 1, -1, -1):
        if (transcript[i] or {}).get("who") == "player":
            return i
    return None


def step(ctx) -> list[dict]:
    from gm import speech

    scene = ctx.scene
    people = dict(ctx.people or {})
    pc_refs = {r for r, p in people.items() if (p or {}).get("is_pc")}
    pc_ref = next(iter(sorted(pc_refs)), "")
    among = [r for r in ctx.talking_after if r not in pc_refs]
    t = int(getattr(scene, "clock_minutes", 0) or 0)
    text = str(ctx.text or "")
    said = [r for r in (ctx.said or []) if isinstance(r, dict)]
    rows: list[dict] = []

    def name_of(ref: str) -> str:
        return str((people.get(ref) or {}).get("name") or ref)

    new: list[tuple[int, dict]] = []   # (order key, entry without n)

    # The player's words first: they were said before the beat that answers them.
    player_text = str(ctx.player_text or "") if ctx.door == "turn" else ""
    if player_text.strip():
        beat = _player_beat(list(getattr(ctx.campaign, "transcript", []) or []),
                            ctx.beat_index)
        to = among[0] if len(among) == 1 else next(
            (r["who"] for r in said if r.get("to") == "you" and r.get("who")
             and r["who"] not in pc_refs), "")
        me = name_of(pc_ref) if pc_ref else "You"
        for line in speech.lines(player_text):
            if line.strip():
                new.append((-1, {"t": t, "beat": beat, "who": "you", "name": me, "to": to,
                                 "kind": "line", "text": line.strip(), "among": list(among),
                                 "src": "player"}))
        for v in speech.vocalisations(player_text, (), people, player=True):
            if v.get("who") and v["who"] in pc_refs:
                new.append((-1, {"t": t, "beat": beat, "who": "you", "name": me,
                                 "to": v.get("to") or "", "kind": "vocal",
                                 "text": _pc_words(v["text"]), "among": list(among),
                                 "src": "player"}))

    # The NPCs' lines, in the order they stand on the page.
    quotes = speech.spans(text)
    for rec in said:
        who = str(rec.get("who") or "")
        line = str(rec.get("line") or "").strip()
        # The player's own words the narrator quoted back are already logged from what
        # the player typed; a line tagged to nobody books nobody.
        if not who or who in pc_refs or not line:
            continue
        at = next((a for a, b in quotes
                   if speech.speaker([rec], text[a + 1:b - 1] if b - a >= 2 else "")),
                  len(text))
        new.append((at, {"t": t, "beat": ctx.beat_index, "who": who, "name": name_of(who),
                         "to": str(rec.get("to") or ""), "kind": "line", "text": line,
                         "among": list(among), "src": "tag"}))

    for v in speech.vocalisations(text, said, people):
        if not v.get("who"):
            rows.append({"kind": "vocal-miss", "phrase": v.get("text", "")[:120],
                         "why": v.get("why", "")})
            continue
        if v["who"] in pc_refs:
            continue
        new.append((int(v.get("at", 0)), {
            "t": t, "beat": ctx.beat_index, "who": v["who"], "name": name_of(v["who"]),
            "to": v.get("to") or "", "kind": "vocal", "text": v["text"],
            "among": list(among), "src": v.get("src") or ""}))

    if not new:
        return rows
    new.sort(key=lambda pair: pair[0])
    log = [e for e in (getattr(scene, "conversation_log", None) or []) if isinstance(e, dict)]
    seq = int(getattr(scene, "conversation_seq", 0) or 0)
    for _at, entry in new:
        seq += 1
        log.append({"n": seq, **entry})
    scene.conversation_log = capped(log)
    scene.conversation_seq = seq
    return rows
