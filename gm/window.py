"""How many characters fit in the model's window: measured from the model, not assumed.

`gm/prompts.py` counts the prompt in characters and converts with one ratio,
`CHARS_PER_TOKEN = 3.6`, measured 2026-09-08 by `tools/token_ratio.py` on OUR fixture
world (3.79 to 3.83 there). Measured 2026-10-08 in a player's log, on the same model
(igorls/gemma-4-12B-it-heretic) with a world of their own:

    stopped at its token limit (prompt 16250 tokens of 16384, reply 134 tokens)

Their text ran about 3.2 characters a token. A budget of (16384 - 1400 - 600) x 3.6 =
51,782 characters is 16,182 tokens at 3.2: the prompt filled the window and the reply had
134 tokens left. The ratio is a property of the model's tokeniser AND of the text, and the
text is the player's world, which we never see.

So the ratio is read off every call. Ollama answers each chat with `prompt_eval_count`,
the tokens it actually evaluated, which includes the chat template's own wrapping (so the
ratio errs low, the safe way). `observe` keeps the recent ratios per model; the budget is
sized from the WORST of them, never above the shipped 3.6 (a world that tokenises better
than ours gains nothing we have not measured) and never below `FLOOR` (one corrupt reading
must not shrink every prompt to nothing).

Prior art, unverified this session because the search tools were down: SillyTavern
counts with a real tokenizer per model where it can and offers a fixed "token padding"
where it cannot; a fixed pad is the shipped constant's approach, and it is what failed
here. Using the server's own count of the previous prompt is the cheapest real tokenizer
an app with no tokenizer dependency has. (Measured here, 2026-10-08, on this Ollama:
a repeated prompt reports the same `prompt_eval_count` both times, 5,434 and 5,434, so a
cached prefix does not undercount.)

Kept in memory, and in the data folder (`token-ratios.json`) so a restart does not open
on the shipped ratio and overflow once before it learns again. CLAUDE.md: a cache in the
user's data folder outlives every reinstall, so it is stamped (`FORMAT`, and the shipped
ratio it was measured against) and read back only when the stamp matches.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import deque

from gm import prompts

# Never above what was shipped: the measured fixture world's margin stays the ceiling.
SHIPPED = prompts.CHARS_PER_TOKEN
# Never below. English prose measured 3.2 (the player) to 5.1 (repetitive text) on the
# shipped model; 2.0 is well under any of it and keeps one wild reading from halving
# every prompt. A world that really tokenises below this is still caught by the call's
# own guard (`fit`), which reports what it cut.
FLOOR = 2.0
# Below this many characters the chat template's few tokens a message are a large share
# of the count, and the ratio reads low for reasons that have nothing to do with the
# text. Every large prompt this app sends is well above it.
MIN_SAMPLE_CHARS = 4000
# The recent readings kept per model. The worst of them sizes the budget; an old bad one
# ages out after this many calls instead of shrinking prompts for ever.
KEEP = 32
# The chat template's own tokens per message, taken off a reading before the ratio is
# formed (`observe`). Low on purpose: Gemma's turn markers are about five, and taking
# off too few only makes the ratio read low, which is the safe way to be wrong.
WRAP_TOKENS = 4
FORMAT = 1
FILE_NAME = "token-ratios.json"

_LOCK = threading.Lock()
_SEEN: dict[str, deque] = {}
_LOADED = False
_log = logging.getLogger("pathfindergm")


def _key(model: str | None) -> str:
    from gm.client import model_tag      # gm.client imports this module

    return model_tag(model or "")


def _path():
    from pathfindergm.paths import user_data_root

    return user_data_root() / FILE_NAME


def _reset() -> None:
    """Forget everything, and do not read the file again. For tests."""
    global _LOADED
    with _LOCK:
        _SEEN.clear()
        _LOADED = True


def _load() -> None:
    """Seed each model's readings with the worst one kept on disk, once per process."""
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — no file, or a torn one: start from the shipped ratio
        return
    if (not isinstance(data, dict) or data.get("format") != FORMAT
            or data.get("shipped") != SHIPPED):
        return                            # written by another build: not trusted
    for model, worst in (data.get("models") or {}).items():
        try:
            worst = float(worst)
        except (TypeError, ValueError):
            continue
        if FLOOR <= worst <= SHIPPED:
            _SEEN.setdefault(model, deque(maxlen=KEEP)).append(worst)


def _save() -> None:
    from pathfindergm import files

    try:
        files.write_text(_path(), json.dumps({
            "format": FORMAT, "shipped": SHIPPED,
            "models": {m: round(min(d), 4) for m, d in _SEEN.items() if d},
        }, indent=1))
    except Exception:  # noqa: BLE001 — a cache that cannot be written is only a cache
        pass


def observe(model: str, chars: int, prompt_tokens, messages: int = 0) -> float | None:
    """One call's reading: `chars` of message content sent in `messages` messages,
    `prompt_tokens` counted. Returns the ratio when it was kept. Saved when it moves the
    model's worst case.

    The chat template's few tokens a message are taken off first (`WRAP_TOKENS`), since
    the budget is in characters of content and `SAFETY_TOKENS` already pays for the
    wrapping. Measured 2026-10-08 on the shipped model in a long session: the
    interpreter's call, 108 short messages and 19,641 characters, read 3.12 characters a
    token raw, while every large call read 3.8 to 3.9; with four tokens a message taken
    off it reads 3.35. Left raw, the call with the most messages would size every prompt.

    A prompt that overflowed the window is counted at no more than the window (Ollama
    cut it first), so its reading is an upper bound on the true ratio. It is kept: below
    the shipped ratio it still shrinks the next prompt nearly all the way, and the next
    call, which fits, reads the true figure."""
    try:
        tokens = int(prompt_tokens or 0) - WRAP_TOKENS * max(0, int(messages or 0))
    except (TypeError, ValueError):
        return None
    if not model or tokens <= 0 or chars < MIN_SAMPLE_CHARS:
        return None
    ratio = chars / tokens
    key = _key(model)
    with _LOCK:
        _load()
        seen = _SEEN.setdefault(key, deque(maxlen=KEEP))
        was = min(seen) if seen else None
        seen.append(ratio)
        now = min(seen)
        if was is None or abs(now - was) > 0.005:
            _save()
    return ratio


def chars_per_token(model: str | None = None) -> float:
    """The ratio to size a prompt for `model` with: its worst recent reading, held
    between FLOOR and SHIPPED. With no model named, the worst over every model seen,
    which is the safe answer for a prompt that does not know where it is going."""
    with _LOCK:
        _load()
        if model:
            seen = _SEEN.get(_key(model))
            readings = list(seen) if seen else []
        else:
            readings = [r for d in _SEEN.values() for r in d]
    worst = min(readings) if readings else SHIPPED
    return max(FLOOR, min(SHIPPED, worst))


def prompt_budget_chars(model: str | None = None,
                        completion: int = prompts.MAX_COMPLETION_TOKENS) -> int:
    """Characters of message content that leave `completion` tokens of the window free,
    plus the shipped safety margin. `prompts.PROMPT_BUDGET_CHARS` is this at the shipped
    ratio, and is the most it can ever be."""
    room = prompts.NUM_CTX - int(completion or 0) - prompts.SAFETY_TOKENS
    return max(0, int(room * chars_per_token(model)))


def _chars(messages) -> int:
    return sum(len(m.get("content") or "") for m in messages)


def fit(messages: list[dict], budget: int) -> tuple[list[dict], dict]:
    """The last guard, for every call: drop the oldest conversation until it fits.

    `prompts.pack` decides what goes for the turn prompts, in a stated order. This is
    for everything that does not pass through it, or grows after it: the retries that
    append a failed reply and a correction to an already packed prompt (`gm/agent.py`,
    `_with_correction` and the beat corrections) add one whole reply, up to 1,400 tokens,
    to a prompt that was already at the budget — and Ollama, handed more than the
    window, drops messages from the front silently (measured here 2026-10-08: a
    153,088-character, five-message chat was evaluated as 13,575 tokens, the oldest
    turn gone without a word) or, when one message alone is too long, keeps about half
    the window (208,663 characters evaluated as 8,195 tokens, the system message and the
    first line both lost).

    What goes, in order: the oldest messages after the leading system messages, a user
    message together with the replies that follow it, so what is kept never opens on a
    reply. Never the system messages, never the last message, never the GM's pinned
    note. Returns the messages and a report; `report["over"]` says the parts that are
    never cut are still over the budget, which is sent anyway and said."""
    from play.opening import NOTE_PREFIX

    report = {"dropped": 0, "dropped_chars": 0, "over": False}
    if _chars(messages) <= budget or len(messages) < 3:
        report["over"] = _chars(messages) > budget
        return messages, report
    lead = 0
    while lead < len(messages) - 1 and messages[lead].get("role") == "system":
        lead += 1
    head, middle, tail = messages[:lead], list(messages[lead:-1]), messages[-1:]

    def pinned(m) -> bool:
        return str(m.get("content", "")).startswith(NOTE_PREFIX)

    total = _chars(messages)
    while total > budget:
        i = next((k for k, m in enumerate(middle) if not pinned(m)), None)
        if i is None:
            break
        bite = [i]
        j = i + 1
        while j < len(middle) and middle[j].get("role") != "user" and not pinned(middle[j]):
            bite.append(j)
            j += 1
        for k in reversed(bite):
            total -= len(middle[k].get("content") or "")
            report["dropped_chars"] += len(middle[k].get("content") or "")
            report["dropped"] += 1
            del middle[k]
    report["over"] = total > budget
    return head + middle + tail, report
