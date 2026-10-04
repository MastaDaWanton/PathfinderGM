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


class ModelStalled(ModelUnavailable):
    """Ollama has the model loaded and has stopped answering, or cannot start it at all.

    Measured 2026-10-03 on this machine: after a normal reply at 20:50, Ollama took every
    later request and answered none — the game's turn and a five-token probe both sat
    silent while `/api/ps` went on answering and listing the model as loaded. At 21:35 the
    idle model was unloaded and every reload failed in the log ("llama-server GPU discovery
    watchdog timed out", "Load failed … timed out waiting for llama-server"); the GPU was
    healthy and nearly empty. The game waited the full 600-second cold-load allowance per
    call, several calls a turn. Ollama's own tracker has the same shape (ollama/ollama
    #18685, #15950: the HTTP server stays up while a runner is wedged). Only a restart of
    Ollama clears it, and that is what the player is told, in a minute or two rather than
    half an hour. A subclass, so every caller that catches `ModelUnavailable` still does."""


class ModelNotInstalled(ModelUnavailable):
    """Ollama answered, and said it does not have this model: HTTP 404 from `/api/chat`
    (`server/routes.go`: `model 'x' not found`, or the scheduler's `model "x" not found,
    try pulling it first`). A different fact from "Ollama is down" with a different fix,
    and it was reported as the other one: "could not be reached: cannot reach Ollama at
    http://localhost:11434: HTTP Error 404" (playtest 2026-10-03, item 18), while the
    same Ollama was answering the narrator's calls in the same turn. A subclass, so every
    caller that catches `ModelUnavailable` still does."""


def model_tag(model: str) -> str:
    """Ollama's own spelling of a tag. `foo` and `foo:latest` are one model.

    `/api/tags` always answers with the tag present, and `settings.MODELS` may or may
    not carry one — `richardyoung/qwen3-4b-instruct-2507-abliterated` is configured
    without. Compared raw, an installed model reads as missing. (Moved here from
    `play/preflight.py`, which now calls this, so the two questions "is it installed"
    cannot disagree about a spelling.)
    """
    name = (model or "").strip()
    if not name:
        return ""
    # A digest-pinned reference (`model@sha256:...`) names one exact blob; the part
    # before the `@` is still the tag Ollama lists it under.
    name = name.split("@", 1)[0]
    return name if ":" in name.rsplit("/", 1)[-1] else f"{name}:latest"


# What `/api/tags` said, per host: (when, the tags, whether it answered). Cached because
# the question is asked on every turn and the answer changes only when the player pulls
# or deletes a model; a minute is short enough that a pull made mid-session is seen on
# the next turn after it. LiteLLM keeps a cooldown cache for the same reason
# (docs/turn-pipeline-2026-10-03.md).
TAGS_TTL = 60.0
_tags_cache: dict[str, tuple[float, frozenset, bool]] = {}
_said_missing: set[tuple[str, str]] = set()


def has_model(model: str, host: str = "http://localhost:11434",
              provider: str = "ollama") -> bool | None:
    """Whether `host`'s Ollama has `model` pulled: True, False, or None when it cannot
    say (a hosted provider, or an Ollama that did not answer — then the call itself is the
    test, and its own error says what is wrong)."""
    if (provider or "ollama") != "ollama" or not model:
        return None
    key = (host or "").rstrip("/")
    now = time.monotonic()
    got = _tags_cache.get(key)
    if got is None or now - got[0] > TAGS_TTL:
        found = probe(host)
        got = (now, frozenset(model_tag(n) for n in found.installed), found.reachable)
        _tags_cache[key] = got
    if not got[2]:
        return None
    return model_tag(model) in got[1]


def _forget_model(model: str, host: str) -> None:
    """A 404 said this model is gone: the cache stops listing it until its next refresh."""
    key = (host or "").rstrip("/")
    got = _tags_cache.get(key)
    if got is not None:
        _tags_cache[key] = (got[0], got[1] - {model_tag(model)}, got[2])


def say_missing_once(model: str, host: str, role: str = "") -> bool:
    """Log, once per process, that a configured model is not on its host. True the first
    time. Once, because the check runs every turn and the fact does not change between
    them; a log that says it sixty times is a log nobody reads."""
    key = (model_tag(model), (host or "").rstrip("/"))
    if key in _said_missing:
        return False
    _said_missing.add(key)
    import logging

    logging.getLogger("pathfindergm").warning(
        "%s%s is not installed on the Ollama at %s, so it is skipped. Download it from "
        "the app's model setup, or choose another model in Settings.",
        f"the {role} model " if role else "", model, host)
    return True


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

# How long a LOADED model may go without sending a single token — before the first or
# between two — before the call is given up as a wedged Ollama (`ModelStalled`). A warm
# reply's first token comes after prompt evaluation (about 0.5 s per thousand tokens on
# this machine; a full 16k window is under ten seconds) plus any queue behind the game's
# own other calls; between tokens the gap is milliseconds, and still well under a second
# on a CPU-only machine. Two minutes is generous to all of that and far short of the
# half hour a wedged server cost (`ModelStalled`). A model NOT loaded keeps the caller's
# own allowance, because a cold load really is slow (104.8 s measured on a 3-token reply).
STALL_SECONDS = 120


def loaded(model: str, host: str) -> bool | None:
    """Whether Ollama has `model` in memory right now (`/api/ps`), or None when it cannot
    say. Not cached: it is asked once per call, costs milliseconds, and a stale "loaded"
    would cut a genuine cold load short."""
    try:
        with urllib.request.urlopen(f"{host.rstrip('/')}/api/ps", timeout=3) as r:
            models = json.loads(r.read().decode("utf-8")).get("models") or []
    except Exception:  # noqa: BLE001 — no answer means no claim either way
        return None
    want = model_tag(model)
    return any(model_tag(str(m.get("name") or m.get("model") or "")) == want
               for m in models)


def _fold(text: str) -> dict:
    """One reply from `/api/chat`, streamed or not: the streamed lines' content and
    thinking joined, the last line's counts and `done_reason` kept, an `error` line
    raised. A single JSON object (an unstreamed reply, or a test's) is returned as is."""
    lines = [json.loads(ln) for ln in str(text or "").splitlines() if ln.strip()]
    if not lines:
        raise ModelUnavailable("Ollama sent an empty reply.")
    for ln in lines:
        if isinstance(ln, dict) and ln.get("error"):
            raise ModelUnavailable(f"Ollama answered with an error: {ln['error']}")
    if len(lines) == 1:
        return lines[0]
    body = dict(lines[-1])
    message = {"role": "assistant",
               "content": "".join(str((ln.get("message") or {}).get("content") or "")
                                  for ln in lines)}
    thinking = "".join(str((ln.get("message") or {}).get("thinking") or "") for ln in lines)
    if thinking:
        message["thinking"] = thinking
    body["message"] = message
    return body


def _stalled(model: str, host: str, why: str) -> ModelStalled:
    return ModelStalled(
        f"The model has stopped answering: Ollama has {model} loaded but {why}. This is "
        f"Ollama, not your game — quit Ollama from its tray icon, start it again, and send "
        f"your line again. Your turn has not been lost.")


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
        # Streamed, so silence can be told from work: the socket's wait applies to each
        # chunk, and a loaded model that sends nothing for `STALL_SECONDS` is wedged, not
        # thinking (`ModelStalled`). Unstreamed, the whole reply is one read, and a wedged
        # server and a long answer look the same until the full allowance runs out.
        "stream": True,
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
    # Loaded: silence past `STALL_SECONDS` is a wedged Ollama. Not loaded (or no answer
    # from `/api/ps`): the caller's own allowance, which covers a cold load.
    warm = loaded(model, host) is True
    wait = min(timeout, STALL_SECONDS) if warm else timeout

    def _post(pl):
        req = urllib.request.Request(
            f"{host.rstrip('/')}/api/chat",
            data=json.dumps(pl).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=wait) as resp:
            return _fold(resp.read().decode("utf-8"))

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
            elif exc.code == 404:
                # The server is up — it answered — and the model is not on it.
                _forget_model(model, host)
                why = " ".join(detail.split())[:160] or "not found"
                raise ModelNotInstalled(
                    f"{model} is not installed on the Ollama at {host} (it answered "
                    f"404: {why}). Download it from the app's model setup, or choose "
                    f"another model in Settings."
                ) from exc
            elif exc.code >= 500 and re.search(r"llama|runner|load", detail, re.I):
                # Ollama answered, and could not start the model: measured 2026-10-03,
                # "Load failed … timed out waiting for llama-server" after its GPU
                # discovery watchdog timed out, on a healthy GPU. The same cure as a stall.
                why = " ".join(detail.split())[:160] or f"HTTP {exc.code}"
                raise ModelStalled(
                    f"Ollama could not start {model} ({why}). This is Ollama, not your "
                    f"game — quit Ollama from its tray icon, start it again, and send "
                    f"your line again. Your turn has not been lost.") from exc
            else:
                raise
    except TimeoutError as exc:
        if warm:
            raise _stalled(model, host, f"sent nothing for {wait} seconds") from exc
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

    # A reply the budget cut off is said in the log. `done_reason` and
    # `prompt_eval_count` were never read (measured 2026-09-25), so a truncated turn and a
    # prompt that filled the window both looked, from the log, like a model that simply
    # wrote badly — the 4,086-token prompt that left ten tokens of room (see num_ctx
    # above) was found by hand.
    if body.get("done_reason") == "length":
        import logging

        logging.getLogger("pathfindergm").warning(
            "%s stopped at its token limit (prompt %s tokens of %s, reply %s tokens) — "
            "the reply is cut off", model, body.get("prompt_eval_count"),
            prompts.NUM_CTX, body.get("eval_count"))
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
