"""A minimal Ollama client.

stdlib only — no `requests` — because every dependency is another thing PyInstaller has
to be told about and another thing that can break in the frozen build.

Models are configured per role (settings.MODELS), each pointing independently at Ollama or
an API, mirroring World Bible's generator/proofreader split. Local is the default and must
always be sufficient.
"""
from __future__ import annotations

import http.client
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from gm import prompts

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


# How long Ollama keeps a model in memory after a request. Long enough to cover the
# thinking between turns and a character build; the model is unloaded by `warm`'s
# absence, never by a turn.
KEEP_ALIVE = "45m"


def warm(model: str, host: str, provider: str = "ollama") -> bool:
    """Ask Ollama to load `model` now, and keep it. No prompt, so nothing is
    generated; the call returns when the weights are in memory. Called in a thread
    from the pages a player sits on before play — the shelf, the forge — so the
    opening does not pay the cold load. Hosted providers have nothing to warm."""
    if provider and provider != "ollama" or not model:
        return False
    try:
        req = urllib.request.Request(
            f"{host.rstrip('/')}/api/generate",
            data=json.dumps({"model": model, "keep_alive": KEEP_ALIVE}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=600) as resp:
            resp.read()
        return True
    except Exception:
        return False


def warm_roles(*roles: str) -> None:
    """Warm each role's model once, in the background, deduplicated by model."""
    import threading

    from play import modelcfg

    seen = set()
    for role in roles:
        cfg = modelcfg.for_role(role) or {}
        key = (cfg.get("model"), cfg.get("host"))
        if not cfg.get("model") or key in seen:
            continue
        seen.add(key)
        threading.Thread(target=warm, args=(cfg["model"], cfg.get("host", ""),
                                            cfg.get("provider", "ollama")),
                         daemon=True, name=f"warm-{role}").start()


def chat(
    messages: list[dict],
    model: str,
    host: str = "http://localhost:11434",
    as_json: bool = False,
    temperature: float = 0.8,
    timeout: int = 600,
    num_predict: int = 700,
    provider: str = "ollama",
    api_key: str = "",
    schema: dict | None = None,
    think: bool | None = None,
) -> Reply:
    """
    The timeout is generous because a cold load is genuinely slow: measured on this
    machine, `llama3.1:8b` reported `load_duration` of 95.4s against 0.46s of actual
    generation, for 104.8s wall clock on a three-token reply. A 180s timeout looked
    ample and still failed under disk contention. Latency here is load time, not
    inference — which is why the first turn of a session should warm the model rather
    than making the player wait for it.
    """
    if provider and provider != "ollama":
        return _hosted(messages, model, host, provider, api_key, as_json,
                       temperature, timeout, num_predict)

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        # num_ctx is not decoration: Ollama's default window is 4096, and the
        # prose call's real prompt measured 4,086 tokens — the model was left TEN
        # tokens of room, answered '{"narration": "The woman stands by the' and
        # died done_reason=length on every turn of a live scene, silently, with
        # num_predict=900 ignored because the window was already spent. 16k costs
        # roughly 1.5GB of KV cache at 12B and ends the class.
        # One window, named once. `gm/prompts.py` budgets the prompt against this exact
        # number; two copies of it would be the trap CLAUDE.md names, and the failure
        # would be silent — a prompt built for one window sent to another.
        "options": {"temperature": temperature, "num_predict": num_predict,
                    "num_ctx": prompts.NUM_CTX},
        # Stay loaded. Ollama's default unloads a model five minutes after its last
        # request, and a player who spends six minutes building a character then
        # waits the whole cold load again — 60 to 100 seconds on this machine — for
        # the opening. Measured 2026-09-07: a warm opening is 22 s for two calls.
        "keep_alive": KEEP_ALIVE,
    }
    # A schema, when the caller has one, rather than "some JSON please". Ollama passes
    # `format` to the sampler as a grammar, so a reply that breaks the schema is not
    # rejected after the fact — it is never generated. That is the difference between
    # asking the model for an attack and making a turn without one unrepresentable, and
    # it is the only lever on this project that does not depend on the model cooperating.
    if schema:
        payload["format"] = schema
    elif as_json:
        payload["format"] = "json"
    # Whether a reasoning model may think before it answers. Measured on the watcher's
    # garnish call: deepseek-r1:8b spent its ENTIRE budget in the `thinking` channel —
    # 900 and 2,000 tokens both ended done_reason=length with content "" — because the
    # format grammar constrains only the content, which never started. With
    # think=False the same call answered in 0.4s. None sends nothing, because Ollama
    # refuses the key outright for models with no thinking to switch off.
    if think is not None:
        payload["think"] = think

    started = time.monotonic()

    def _post(pl):
        req = urllib.request.Request(
            f"{host.rstrip('/')}/api/chat",
            data=json.dumps(pl).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        try:
            body = _post(payload)
        except urllib.error.HTTPError as exc:
            # Not every runtime compiles every schema keyword. Measured on
            # gemma4:12b: `maxLength` alone made the grammar compiler refuse the
            # whole turn schema ("failed to parse grammar", HTTP 400) and every
            # turn died as a 503 — while llama3.1 accepted the same schema for
            # months. One retry with the uncompilable keyword stripped: the cap
            # was always advisory (the groomers cut long prose anyway); the
            # `minLength` floor, which IS load-bearing, compiles and stays.
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")
            except Exception:
                pass
            if exc.code == 400 and "grammar" in detail and schema:
                def _strip(node):
                    if isinstance(node, dict):
                        return {k: _strip(v) for k, v in node.items()
                                if k != "maxLength"}
                    if isinstance(node, list):
                        return [_strip(v) for v in node]
                    return node
                bare = dict(payload, format=_strip(payload["format"]))
                body = _post(bare)
            else:
                raise
    except TimeoutError as exc:
        raise ModelUnavailable(
            f"{model} did not answer within {timeout}s."
        ) from exc
    # `URLError` is what urllib raises when the CONNECT fails. When Ollama dies or
    # restarts with a request already sent — measured 2026-09-17, turn 59 of a sixty-turn
    # audit, the server restarted under the running model — CPython's `do_open` calls
    # `getresponse()` OUTSIDE its `except OSError` and the bare
    # `http.client.RemoteDisconnected` comes up through `urlopen` unwrapped. It reached
    # the view as a 500 (the audit's log has "Internal Server Error: /api/say" right under
    # the "Service Unavailable" of the turn before), where a player would have seen a
    # server error instead of the "start Ollama" message the next line already writes.
    # Every socket-level failure is the same fact to the player: the model is not there.
    except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
        raise ModelUnavailable(
            f"cannot reach Ollama at {host}: {exc}. Start Ollama, or point "
            f"settings.MODELS at a running host."
        ) from exc

    return Reply(
        text=strip_thinking(body.get("message", {}).get("content", "")),
        seconds=time.monotonic() - started,
        model=model,
    )


def hosted_base(provider: str, host: str) -> str:
    """The base URL a hosted provider's chat completions hang off.

    Google's OpenAI-compatible surface lives under `/v1beta/openai`, and the settings
    page copies a provider's default host into the role when the provider is picked —
    so every role saved before 2026-09-18 carries `/v1beta` and would 404 on every turn.
    Mended here, on the way out, rather than by asking the player to re-save.
    """
    base = str(host or "").rstrip("/")
    if provider == "google" and base.endswith("/v1beta"):
        base += "/openai"
    return base


def _hosted(messages, model, host, provider, api_key, as_json,
            temperature, timeout, num_predict) -> Reply:
    """A provider that is not on this machine.

    Everything here speaks the OpenAI chat shape except Anthropic, which is close
    enough that one branch covers it: a different auth header, a different envelope,
    and the system message lifted out of the list. Google is reached through its own
    OpenAI-compatible endpoint rather than a third shape.

    The key is read from the config and never logged. A failure names the provider and
    the status and nothing else — an error message with a bearer token in it is a
    credential in a screenshot.
    """
    if not api_key:
        raise ModelUnavailable(
            f"{provider} needs an API key. Add one on the settings page.")

    anthropic = provider == "anthropic"
    headers = {"Content-Type": "application/json"}
    if anthropic:
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
        system = " ".join(m["content"] for m in messages if m.get("role") == "system")
        body = {"model": model, "max_tokens": num_predict,
                "temperature": temperature,
                "messages": [m for m in messages if m.get("role") != "system"]}
        if system:
            body["system"] = system
        url = f"{host.rstrip('/')}/messages"
    else:
        headers["Authorization"] = f"Bearer {api_key}"
        body = {"model": model, "messages": messages,
                "temperature": temperature, "max_tokens": num_predict}
        if as_json:
            body["response_format"] = {"type": "json_object"}
        url = f"{hosted_base(provider, host)}/chat/completions"

    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers=headers)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            got = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # The provider's own words, which never contain the key: "model not found",
        # "invalid API key", "response_format is not supported". A bare status code
        # left a player with a fresh Gemini key reading "refused (404)" and nothing to
        # act on — the 404 was this app's URL, not their key.
        detail = ""
        try:
            raw = exc.read().decode("utf-8", "replace")
            try:
                parsed = json.loads(raw)
                err = parsed.get("error", parsed) if isinstance(parsed, dict) else parsed
                detail = str(err.get("message", err) if isinstance(err, dict) else err)
            except ValueError:
                detail = raw
        except Exception:  # noqa: BLE001 — the body is a courtesy, not a requirement
            detail = ""
        detail = " ".join(detail.split())[:200]
        raise ModelUnavailable(
            f"{provider} refused the request ({exc.code})"
            + (f": {detail}" if detail else "")
            + ". Check the model name and the key on the settings page.") from None
    # `OSError` and `HTTPException` for the same reason as the Ollama path above: a
    # connection dropped mid-request arrives unwrapped by urllib.
    except (urllib.error.URLError, TimeoutError, http.client.HTTPException,
            OSError) as exc:
        raise ModelUnavailable(f"cannot reach {provider}: {exc}") from None

    if anthropic:
        text = "".join(b.get("text", "") for b in got.get("content", [])
                       if b.get("type") == "text")
    else:
        text = (got.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return Reply(text=strip_thinking(text), seconds=time.monotonic() - started,
                 model=model)


def available(host: str = "http://localhost:11434", timeout: int = 3) -> list[str]:
    """Every model Ollama has pulled, or an empty list for any reason at all.

    Kept as it was — the settings page's datalist genuinely does not care why the list
    is empty. `probe` is for callers that do.
    """
    return list(probe(host, timeout).installed)


# The three answers `/api/tags` can give, which `available` flattened to one.
#
# It returned `[]` for "Ollama is not installed", for "installed but not running", for
# "running but you have pulled nothing", and for "the host you typed is a typo" — four
# situations with four different fixes, and the settings page could only ever offer the
# same empty datalist to all of them. A first run needs to tell them apart to say
# anything useful, which is what `play/preflight.py` is built on.
#
# `refused` is the one that carries real information: nothing is listening on the port.
# Whether that means "not installed" or "installed but not started" is a question about
# the filesystem, not the socket, and is answered in preflight where the platform
# knowledge already lives.
@dataclass
class Probe:
    reachable: bool
    installed: tuple[str, ...] = ()
    refused: bool = False
    why: str = ""


def probe(host: str = "http://localhost:11434", timeout: int = 3) -> Probe:
    """Ask Ollama what it has, and report *how* it failed when it did."""
    url = f"{host.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            got = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return Probe(False, why=f"{host} answered {exc.code}. That is not Ollama.")
    except urllib.error.URLError as exc:
        # ConnectionRefusedError is WinError 10061 on Windows and ECONNREFUSED
        # everywhere else; urllib wraps whichever in `.reason`. A refusal means the
        # port is free, which is a different situation from a host that cannot be
        # found or one that never answers, and the fix offered differs for each.
        refused = isinstance(exc.reason, ConnectionRefusedError)
        return Probe(False, refused=refused,
                     why=(f"nothing is listening on {host}." if refused
                          else f"cannot reach {host}: {exc.reason}"))
    except (TimeoutError, OSError) as exc:
        return Probe(False, why=f"cannot reach {host}: {exc}")
    except ValueError as exc:
        return Probe(False, why=f"{host} did not answer with JSON: {exc}")

    models = got.get("models") if isinstance(got, dict) else None
    names = tuple(m["name"] for m in models
                  if isinstance(m, dict) and isinstance(m.get("name"), str)
                  ) if isinstance(models, list) else ()
    return Probe(True, installed=names)
