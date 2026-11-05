"""Instrumentation for the narration diagnosis bench: every text a turn's narration passes
through, recorded in the order it happened, without changing what the game does.

Installed into the bench's own process only (`install`), never by the app. It wraps:

  * `gm.client.chat` — every model call: who asked (the nearest gm/ frames), the
    temperature, the raw reply, the seconds. The slot levers (temperature, best-of-N) are
    applied here and in `planned.call_slot`, behind `LEVERS`, so the defaults stay as they
    are in the code under test.
  * `gm.planned._ask` and `gm.planned.write` — each slot's every answer, realised as page
    text, with why it was asked (first, or the re-ask's named fault), and the `Planned`
    object itself (slots, their instructions and tells, the tells check's reads and
    remakes, the notes).
  * every function of `gm.narration` and `gm.judgement`, and every method of
    `gm.agent.GMAgent`, that takes a text and gives one back: a change is recorded as
    (function, depth, before, after). A sentence on the final page that no slot wrote is
    then traced to the innermost function that first put it there (tools/narration_diag/
    attribute.py).

Why wrap rather than log from inside the pipeline: the question is where errors are born,
and the pipeline's own notes say what a repair meant to do, not what text it left. The
2026-11-02 bench found 7 of 37 shipped slips were written by our own repairs only by
reading slot drafts beside pages by hand; this makes that diff mechanical."""
from __future__ import annotations

import functools
import inspect
import json
import sys
import threading
import time
import zlib

# One turn's capture. `on` is set by the driver around the turn's requests.
STATE = {"on": False, "seq": 0, "depth": 0, "changes": [], "chats": [], "asks": [],
         "planned": [], "bestof": [], "pc": "", "seed_key": "", "chat_n": 0}
# The levers (the driver sets them per job): None leaves the code's own behaviour.
LEVERS = {"slot_temperature": None, "best_of": 1, "seed": True, "prose_model": None}
_LOCAL = threading.local()


def reset(seed_key: str = "") -> None:
    STATE.update(seq=0, depth=0, changes=[], chats=[], asks=[], planned=[], bestof=[],
                 pc="", seed_key=seed_key, chat_n=0)


def _first_text(args, kwargs):
    if "text" in kwargs and isinstance(kwargs["text"], str):
        return kwargs["text"]
    for a in args:
        if isinstance(a, str):
            return a
    return None


def _result_text(res):
    if isinstance(res, str):
        return res
    if isinstance(res, tuple) and res and isinstance(res[0], str):
        return res[0]
    return None


def _words(t: str) -> set:
    return {w for w in "".join(ch.lower() if ch.isalnum() else " " for ch in t).split()}


def _a_rewrite(before: str, after: str) -> bool:
    """Whether a text-in, text-out call rewrote a passage, rather than pulling something out
    of it: both are passage-sized and share most of the shorter one's words. The first
    probe (2026-11-04) recorded 3,332 "changes" on one turn, 3,267 of them
    `judgement._spell_words` and the rest extractors (`person_sought` and the like) that take
    a line and return a name — none of them a page edit."""
    if len(before) < 40 or len(after) < 40:
        return False
    a, b = _words(before), _words(after)
    return bool(a and b) and len(a & b) / min(len(a), len(b)) >= 0.5


def _wrap_text_fn(fn, name):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not STATE["on"]:
            return fn(*args, **kwargs)
        before = _first_text(args[1:] if name.startswith("GMAgent.") else args, kwargs)
        STATE["depth"] += 1
        depth = STATE["depth"]
        STATE["seq"] += 1
        start_seq = STATE["seq"]
        try:
            res = fn(*args, **kwargs)
        finally:
            STATE["depth"] -= 1
        after = _result_text(res)
        if before is not None and after is not None and after != before \
                and _a_rewrite(before, after):
            STATE["changes"].append({"start": start_seq, "end": STATE["seq"], "depth": depth,
                                     "fn": name, "before": before, "after": after})
        return res
    wrapper.__diag_wrapped__ = True
    return wrapper


def _caller() -> str:
    """The nearest few gm/ and play/ frames above the chat call: who asked."""
    names = []
    f = sys._getframe(2)
    while f is not None and len(names) < 4:
        mod = f.f_globals.get("__name__", "")
        if mod.startswith(("gm.", "play.")) and mod != "gm.client" and not mod.startswith(
                "tools."):
            names.append(f"{mod.split('.')[-1]}.{f.f_code.co_name}")
        f = f.f_back
    return " < ".join(names)


def install() -> None:
    """Wrap everything once, in this process. Idempotent."""
    from gm import agent, client, judgement, narration, planned

    if getattr(client.chat, "__diag_wrapped__", False):
        return

    real_chat = client.chat

    def chat(messages, model, host="http://localhost:11434", as_json=False,
             temperature=0.8, *a, **kw):
        slot = getattr(_LOCAL, "slot", None)
        if slot is not None and LEVERS["slot_temperature"] is not None:
            temperature = LEVERS["slot_temperature"]
        if STATE["on"] and LEVERS["seed"]:
            # The same seed for the same call of the same item and rep in every condition:
            # common random numbers across the levers, as far as a sampler allows.
            STATE["chat_n"] += 1
            _LOCAL.seed = zlib.crc32(f"{STATE['seed_key']}|{STATE['chat_n']}".encode())
        started = time.monotonic()
        err = ""
        reply = None
        _LOCAL.load = 0.0
        try:
            reply = real_chat(messages, model, host, as_json, temperature, *a, **kw)
            return reply
        except Exception as exc:
            err = f"{type(exc).__name__}: {str(exc)[:200]}"
            raise
        finally:
            _LOCAL.seed = None
            if STATE["on"]:
                STATE["chats"].append({
                    "seq": STATE["seq"], "who": _caller(),
                    "slot": (slot or {}).get("key"),
                    "temperature": temperature, "model": model,
                    "load": round(getattr(_LOCAL, "load", 0.0) or 0.0, 2),
                    "seconds": round(time.monotonic() - started, 2),
                    "raw": getattr(reply, "text", "") or "", "error": err})

    chat.__diag_wrapped__ = True
    client.chat = chat

    # Ollama's own `load_duration` for each reply, so a model swap (the model arm runs the
    # narrator on one model and the interpreter on another, and only one fits the GPU) is
    # taken out of the seconds a turn is charged: measured 2026-11-04, 6.5 s a swap.
    real_fold = client._fold

    def _fold(text):
        body = real_fold(text)
        if isinstance(body, dict):
            _LOCAL.load = float(body.get("load_duration") or 0) / 1e9
        return body

    client._fold = _fold

    # The seed reaches Ollama through the request body (the client builds `options`
    # itself); added on the way out, only for /api/chat, only while a seed is set.
    import urllib.request as ur

    real_request = ur.Request

    class SeededRequest(real_request):
        def __init__(self, url, data=None, *a, **kw):
            seed = getattr(_LOCAL, "seed", None)
            if seed is not None and data and str(url).endswith("/api/chat"):
                try:
                    body = json.loads(data.decode("utf-8"))
                    body.setdefault("options", {})["seed"] = seed
                    data = json.dumps(body).encode("utf-8")
                except ValueError:
                    pass
            super().__init__(url, data, *a, **kw)

    ur.Request = SeededRequest

    # Every text-to-text function of the narration and judgement modules.
    for mod in (narration, judgement):
        for name, fn in list(vars(mod).items()):
            if inspect.isfunction(fn) and fn.__module__ == mod.__name__ \
                    and not getattr(fn, "__diag_wrapped__", False):
                setattr(mod, name, _wrap_text_fn(fn, f"{mod.__name__.split('.')[-1]}.{name}"))
    # And every method of the agent (staticmethods kept static).
    for name, raw in list(vars(agent.GMAgent).items()):
        if name.startswith("__"):
            continue
        if isinstance(raw, staticmethod):
            setattr(agent.GMAgent, name,
                    staticmethod(_wrap_text_fn(raw.__func__, f"GMAgent*{name}")))
        elif inspect.isfunction(raw):
            setattr(agent.GMAgent, name, _wrap_text_fn(raw, f"GMAgent.{name}"))

    # The planned narrator: every slot answer, realised, with why it was asked.
    real_ask = planned._ask

    def _ask(out, plan, slots, i, written, who, *, suggest=False, redo="", lift=None,
             core=True):
        s = slots[i]
        _LOCAL.slot = {"key": s["key"], "first": not redo, "s": s, "lift": lift,
                       "suggest": suggest}
        try:
            text, data = real_ask(out, plan, slots, i, written, who, suggest=suggest,
                                  redo=redo, lift=lift, core=core)
        finally:
            _LOCAL.slot = None
        if STATE["on"]:
            # Which planned beat of the turn this answer belongs to: since 2026-11-04 the
            # enemies' turns are planned too (`planned.write(acting=…)`), so one turn holds
            # several beats whose slots share keys ("fact1").
            STATE["asks"].append({"seq": STATE["seq"], "key": s["key"],
                                  "beat": len(STATE["planned"]),
                                  "redo": redo, "text": text,
                                  "raw": (out.calls[-1].get("raw") if out.calls else "")})
        return text, data

    planned._ask = _ask

    real_call_slot = planned.call_slot

    def call_slot(s, messages, who, *, suggest=False):
        ctx = getattr(_LOCAL, "slot", None)
        if ctx is None:
            # A tells-check remake (`_tells_kept`) calls the slot directly: the temperature
            # lever applies to it too, as it is a slot call.
            _LOCAL.slot = {"key": s["key"], "first": False, "s": s}
            try:
                return real_call_slot(s, messages, who, suggest=suggest)
            finally:
                _LOCAL.slot = None
        n = int(LEVERS["best_of"] or 1)
        if n <= 1 or not ctx.get("first") or not str(s["key"]).startswith("fact") \
                or not s.get("tells"):
            return real_call_slot(s, messages, who, suggest=suggest)
        return _best_of(n, s, messages, who, suggest, ctx, real_call_slot)

    planned.call_slot = call_slot

    real_write = planned.write

    def write(engine, **kw):
        try:
            pc = engine.scene.pc()
            STATE["pc"] = getattr(pc, "name", "") or ""
        except Exception:  # noqa: BLE001
            pass
        out = real_write(engine, **kw)
        if STATE["on"]:
            STATE["planned"].append(_planned_record(out, kw))
        return out

    planned.write = write

    # The model arm: the prose role (every slot, the free and enemy-turn narrators, the
    # repairs, and the readers and checks that ride the prose route — the tells check, the
    # beat reader, the read back) on another model. The narrator role (the interpreter,
    # the plan, the enemies' own turns) stays as configured, so the engine decides the same
    # way from the same reading. `PATHFINDER_GM_DIAG_PROSE_MODEL` sets it for a whole run.
    import os

    from play import modelcfg

    real_for_role = modelcfg.for_role

    def for_role(role):
        cfg = real_for_role(role)
        want = LEVERS.get("prose_model") or os.environ.get("PATHFINDER_GM_DIAG_PROSE_MODEL")
        if role == "prose" and want:
            cfg = dict(cfg, model=want)
        return cfg

    modelcfg.for_role = for_role


def _best_of(n, s, messages, who, suggest, ctx, real_call_slot):
    """Best-of-N for an act slot's first answer: up to N candidates, the first that passes
    the page's own check (`planned.page_fault`) and reads clean against the slot's own tells
    (`beat_verify.against_tells`, the tells check's first read) stands; none passing, the
    first. Every candidate and its verdict is kept for the record."""
    from gm import beat_verify, planned
    from play import modelcfg

    cfg = modelcfg.for_role("prose") or {}
    tried = []
    first = None
    for k in range(n):
        reply, data = real_call_slot(s, messages, who, suggest=suggest)
        text = planned.realise(s, data, ctx.get("lift"))
        verdict = planned.page_fault(text) if text else "empty"
        clashes = []
        if not verdict:
            read = beat_verify.against_tells(
                text, s.get("tells") or [], who=STATE["pc"], model=cfg.get("model", who[0]),
                host=cfg.get("host", who[1]), provider=cfg.get("provider", "ollama"),
                api_key=cfg.get("api_key", ""))
            clashes = [c.as_log() for c in read.clashes]
            if read.error:
                verdict = "unread: " + read.error[:80]
            elif clashes:
                verdict = "clash"
        tried.append({"text": text, "verdict": verdict or "pass", "clashes": clashes})
        if first is None:
            first = (reply, data)
        if not verdict:
            STATE["bestof"].append({"key": s["key"], "beat": len(STATE["planned"]),
                                    "picked": k, "tried": tried})
            return reply, data
    STATE["bestof"].append({"key": s["key"], "beat": len(STATE["planned"]), "picked": 0,
                            "tried": tried})
    return first


def _planned_record(out, kw) -> dict:
    """The planned beat as the bench keeps it: each slot's instruction, tells, every answer
    in order, the text that stood; the tells check's reads and remakes; the notes."""
    def slot_row(s):
        msgs = s.get("messages") or []
        return {"key": s.get("key"), "say": s.get("say", ""), "tells": s.get("tells") or [],
                "max": s.get("max"), "speaker": s.get("speaker_name", ""),
                "wrote": s.get("wrote", ""), "dropped": bool(s.get("dropped")),
                "reply": s.get("reply", ""),
                "ask": (msgs[-1]["content"] if msgs else "")}

    return {"text": out.text, "slots": [slot_row(s) for s in out.slots],
            "calls": [{k: c.get(k) for k in ("key", "raw", "seconds", "note")}
                      for c in out.calls],
            "plan_user": (out.messages[1]["content"] if len(out.messages) > 1 else ""),
            "plan_system": (out.messages[0]["content"] if out.messages else ""),
            "notes": list(out.notes), "faith": list(out.faith),
            "remade": [{k: r.get(k) for k in ("slot", "rejected", "rejected_raw", "clashes",
                                               "remade", "remade_raw", "passed", "stood",
                                               "remade_broken", "remade_against_tell")}
                       for r in out.remade],
            "player_input": kw.get("player_input", ""),
            "acting": str(kw.get("acting") or "")}


def snapshot() -> dict:
    """This turn's capture, JSON-ready."""
    return {"pc": STATE["pc"], "changes": list(STATE["changes"]), "chats": list(STATE["chats"]),
            "asks": list(STATE["asks"]), "planned": list(STATE["planned"]),
            "bestof": list(STATE["bestof"])}
