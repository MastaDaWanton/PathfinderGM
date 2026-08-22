"""A minimal Ollama client.

stdlib only — no `requests` — because every dependency is another thing PyInstaller has
to be told about and another thing that can break in the frozen build.

Models are configured per role (settings.MODELS), each pointing independently at Ollama or
an API, mirroring World Bible's generator/proofreader split. Local is the default and must
always be sufficient.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

# Reasoning models emit their working before their answer. Qwen3 and its tunes do it by
# default, and DeepSeek-R1 always does — both are in the user's Ollama already.
#
# Measured on R4C3R/qwen3-8b-heretic: every consequence call came back as a thousand
# characters of "Okay, let me break down what's happening here" and never reached the
# prose at all, because 250 tokens of budget were spent thinking. Call 1 looked fine only
# because `format=json` forces the model out of that mode.
#
# Written with chr(92) rather than through a heredoc. The first version of these two
# lines went in through a shell heredoc and the backreference arrived as a literal
# 0x01 byte, so the closed-block pattern never matched, the open-block pattern ate the
# whole reply, and every answer came back empty. CLAUDE.md warns about exactly this.
#
# Stripped here rather than at the call sites, so nothing downstream has to know which
# models think. An unterminated block — thinking that ran out of budget mid-thought — is
# treated as thinking all the way to the end, which is exactly what it was.
_THINK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.S | re.I)
_THINK_OPEN = re.compile(r"<(think|thinking|reasoning)>.*\Z", re.S | re.I)


def strip_thinking(text: str) -> str:
    out = _THINK.sub("", text or "")
    out = _THINK_OPEN.sub("", out)
    return out.strip()


class ModelUnavailable(RuntimeError):
    """Ollama is not answering. Surfaced to the player as itself — a local model that is
    not running is an ordinary situation with an ordinary fix, not a crash."""


@dataclass
class Reply:
    text: str
    seconds: float
    model: str

    def json(self) -> dict:
        """Parse a JSON reply, tolerating the wrappers models add around it.

        `format=json` mostly prevents this, but a model that has decided to be helpful
        will still occasionally wrap the object in prose or a fenced block, and losing a
        whole turn to that is not worth the purity.
        """
        text = self.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"no JSON object in reply: {self.text[:200]!r}")
        return json.loads(text[start:end + 1])


def chat(
    messages: list[dict],
    model: str,
    host: str = "http://localhost:11434",
    as_json: bool = False,
    temperature: float = 0.8,
    timeout: int = 600,
    num_predict: int = 700,
) -> Reply:
    """
    The timeout is generous because a cold load is genuinely slow: measured on this
    machine, `llama3.1:8b` reported `load_duration` of 95.4s against 0.46s of actual
    generation, for 104.8s wall clock on a three-token reply. A 180s timeout looked
    ample and still failed under disk contention. Latency here is load time, not
    inference — which is why the first turn of a session should warm the model rather
    than making the player wait for it.
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    if as_json:
        payload["format"] = "json"

    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ModelUnavailable(
            f"cannot reach Ollama at {host}: {exc}. Start Ollama, or point "
            f"settings.MODELS at a running host."
        ) from exc
    except TimeoutError as exc:
        raise ModelUnavailable(
            f"{model} did not answer within {timeout}s."
        ) from exc

    return Reply(
        text=strip_thinking(body.get("message", {}).get("content", "")),
        seconds=time.monotonic() - started,
        model=model,
    )


def available(host: str = "http://localhost:11434", timeout: int = 3) -> list[str]:
    try:
        with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=timeout) as r:
            return [m["name"] for m in json.loads(r.read().decode("utf-8")).get("models", [])]
    except Exception:
        return []
