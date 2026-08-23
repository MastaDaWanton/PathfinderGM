"""Which model does which job, and the keys for the ones that are not local.

`settings.MODELS` is the shipped default and stays that: a fresh install plays against
Ollama with no configuration at all, which is the standing constraint. This module is
the *override* — a small JSON file in the user's data directory, read fresh on every
ask for the same reason the house rules are, because a cached copy of a model the
player just changed is a model that silently is not in use.

**Three jobs, and they are genuinely different.** The narrator writes the scene and has
to satisfy a schema. The event watcher reads what happened and decides what changed —
a reasoning model suits it, and it is still wired to nothing (see `settings.py`). The
backup narrator exists because a model that refuses is a lost turn: it takes the last
two slots of the schedule when the first has burned all five of its own.

**Keys never come back out.** They are written here and read by the client; what the
page is sent is whether a key is set and its last four characters, which is enough to
recognise the one you pasted and not enough to be worth stealing off a screenshot. The
file lives beside the campaigns in the user's own data directory, never in the repo,
and nothing logs it.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings

# The jobs a model can hold. Order is the order the settings page draws them.
ROLES = (
    ("narrator", "Narrator",
     "Writes the scene and proposes what the engine should resolve. The one that has "
     "to satisfy a schema, so a model that follows instructions beats a model that "
     "writes prettily."),
    ("prose", "Consequence",
     "Says what the dice did, in two or three sentences. No schema to satisfy — this "
     "is the half a creative-writing tune is good at. Falls back to the narrator."),
    ("watcher", "Event watcher",
     "Reads the log and decides what changed in the world. A reasoning model suits "
     "reading a record and drawing a conclusion. Not yet wired to anything."),
    ("fallback", "Backup narrator",
     "Takes the turn when the narrator has burned all five of its attempts. Worth "
     "pointing at a small abliterated model — a 4B one loads fast and will push a "
     "response through where a tuned model refuses, and whatever it returns passes "
     "the same validators as everything else. A rescued turn from a worse model "
     "beats a wall of red from a better one."),
)

# Every provider the client can actually reach. `ollama` needs a host and no key; the
# rest need a key and use their own default endpoint. Listed rather than accepted
# free-form so the page can say what a key is *for* and the client knows how to sign it.
PROVIDERS = {
    "ollama": {"name": "Ollama (local)", "key": False,
               "host": "http://localhost:11434",
               "note": "On your own machine. No key, no cost, no data leaves."},
    "openai": {"name": "OpenAI", "key": True,
               "host": "https://api.openai.com/v1"},
    "anthropic": {"name": "Anthropic", "key": True,
                  "host": "https://api.anthropic.com/v1"},
    "google": {"name": "Google Gemini", "key": True,
               "host": "https://generativelanguage.googleapis.com/v1beta"},
    "mistral": {"name": "Mistral", "key": True,
                "host": "https://api.mistral.ai/v1"},
    "groq": {"name": "Groq", "key": True,
             "host": "https://api.groq.com/openai/v1"},
    "deepseek": {"name": "DeepSeek", "key": True,
                 "host": "https://api.deepseek.com/v1"},
    "xai": {"name": "xAI Grok", "key": True, "host": "https://api.x.ai/v1"},
    "openrouter": {"name": "OpenRouter", "key": True,
                   "host": "https://openrouter.ai/api/v1"},
    "together": {"name": "Together", "key": True,
                 "host": "https://api.together.xyz/v1"},
}


def _path() -> Path:
    """Beside the campaigns, in the user's own data directory. Never in the repo."""
    p = Path(settings.CAMPAIGN_DIR).parent
    p.mkdir(parents=True, exist_ok=True)
    return p / "models.json"


def _stored() -> dict:
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def keys() -> dict[str, str]:
    """The API keys, in full. For the client only — never for a response."""
    got = _stored().get("keys") or {}
    return {k: str(v) for k, v in got.items() if str(v).strip()}


def roles() -> dict[str, dict]:
    """Every role's live configuration: the shipped default under any override."""
    saved = _stored().get("roles") or {}
    out = {}
    for role, _, _ in ROLES:
        base = dict(settings.MODELS.get(role) or {})
        over = saved.get(role) or {}
        merged = {**base, **{k: v for k, v in over.items() if str(v).strip()}}
        merged.setdefault("provider", "ollama")
        if not merged.get("host"):
            merged["host"] = PROVIDERS.get(merged["provider"], {}).get("host", "")
        out[role] = merged
    return out


def for_role(role: str) -> dict:
    """One role's model, host, provider and key, ready to hand to the client."""
    cfg = dict(roles().get(role) or {})
    cfg["api_key"] = keys().get(cfg.get("provider", "ollama"), "")
    return cfg


def masked() -> dict[str, dict]:
    """What the settings page is told about the keys.

    Whether one is set and its last four characters — enough to recognise the key you
    pasted, and not enough to be worth lifting off a screenshot or a support log.
    """
    have = keys()
    out = {}
    for pid, spec in PROVIDERS.items():
        got = have.get(pid, "")
        out[pid] = {"set": bool(got),
                    "tail": got[-4:] if len(got) > 4 else ("set" if got else "")}
    return out


def save(roles_in: dict | None = None, keys_in: dict | None = None) -> list[str]:
    """Write the overrides. Returns problems; nothing is written if there are any.

    A key sent as empty is left alone rather than cleared — the page never receives the
    real one, so an untouched field comes back blank and would otherwise wipe it. To
    remove a key the page sends the word `clear`, which is a thing nobody's key is.
    """
    problems: list[str] = []
    data = _stored()
    data.setdefault("roles", {})
    data.setdefault("keys", {})

    for role, cfg in (roles_in or {}).items():
        if role not in {r for r, _, _ in ROLES}:
            problems.append(f"{role!r} is not a job a model can hold.")
            continue
        provider = str((cfg or {}).get("provider", "ollama")).strip().lower()
        if provider not in PROVIDERS:
            problems.append(f"{provider!r} is not a provider this build can reach.")
            continue
        entry = {"provider": provider,
                 "model": str((cfg or {}).get("model", "")).strip(),
                 "host": str((cfg or {}).get("host", "")).strip()
                         or PROVIDERS[provider]["host"]}
        if not entry["model"]:
            problems.append(f"{role}: name the model it should use.")
            continue
        data["roles"][role] = entry

    for pid, value in (keys_in or {}).items():
        if pid not in PROVIDERS:
            problems.append(f"{pid!r} is not a provider this build can reach.")
            continue
        value = str(value or "").strip()
        if value.lower() == "clear":
            data["keys"].pop(pid, None)
        elif value:
            data["keys"][pid] = value

    if problems:
        return problems
    _path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        _path().chmod(0o600)     # keys: readable by this user and nobody else
    except OSError:
        pass                     # Windows and some filesystems do not do modes
    return []
