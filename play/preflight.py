"""Whether this machine can actually run a turn, and what to do about it if not.

The standing constraint says the user installs one file and needs no terminal. The
thing that constraint cannot cover is the **weights**: the two default models are
7.4 GB and 2.5 GB, and no installer ships those. So there is a first-run download
whatever else is decided, and the only question is whether the player types
`ollama pull igorls/gemma-4-12B-it-heretic-GGUF` into a terminal to get it — which
would put a command line back into an app whose whole premise is not having one.

This module is the answer: the app finds out what is missing, says so in words, and
offers a button. Ollama itself is **not** bundled. Its CLI is MIT and could legally be
shipped, and doing so would still not avoid the 9.9 GB download — it would only save
one double-click, in exchange for owning a GPU runtime, its driver matrix and its
security patching. The surveyed field splits on bundling an engine (LM Studio, Jan,
Msty) versus detecting one (Open WebUI, AnythingLLM); it does not split on the weights.
Nobody ships those.

**Why this is a preflight and not an installer step.** The obvious place to put it is
the NSIS installer, and that is the wrong place. The installer runs once; the condition
it checks changes constantly — the Ollama service gets stopped, a model gets deleted,
the player points a role at a different model on the settings page. A check that only
ran at install time would be wrong by the second week. This runs on every launch and
costs one HTTP call.
"""
from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

from gm import client as gm_client

# Where to send somebody who has no Ollama. The download page rather than a direct
# installer link: the direct link changes shape with every release and a 404 on the
# very first screen of the app is a worse first run than one extra click.
DOWNLOAD_PAGE = "https://ollama.com/download"

# What the shipped defaults weigh, in bytes, for the one sentence a player needs before
# agreeing to a download: how big is this going to be.
#
# Hardcoded because there is nowhere to ask. `/api/tags` and `/api/show` describe models
# that are *already local*, and the size of one that is not is only knowable from the
# registry — which is a network call to answer a question the player asked in order to
# decide whether to make network calls. The pull stream reports the true `total` within
# a second of starting, and the page switches to that the moment it arrives; this is an
# estimate to decide by, and is labelled as one.
#
# Verified against ollama.com on 2026-09-11. A model the player configured themselves is
# simply unknown, and says so rather than guessing.
KNOWN_SIZES = {
    "igorls/gemma-4-12B-it-heretic-GGUF:latest": 7_400_000_000,
    "richardyoung/qwen3-4b-instruct-2507-abliterated:latest": 2_500_000_000,
}

# Headroom over the declared weights before the download is called safe. A pull that
# dies at 94% on a full disk is the worst possible first run: it leaves a partial blob
# behind, and Ollama's own error names the disk rather than the fact that the app
# offered a download it had no room for.
DISK_HEADROOM = 2_000_000_000


def _norm(model: str) -> str:
    """Ollama's own spelling of a tag. `foo` and `foo:latest` are one model.

    `/api/tags` always answers with the tag present, and `settings.MODELS` may or may
    not carry one — `richardyoung/qwen3-4b-instruct-2507-abliterated` is configured
    without. Compared raw, an installed model reads as missing and the player is
    offered a 2.5 GB download of something they already have.
    """
    name = (model or "").strip()
    if not name:
        return ""
    # A digest-pinned reference (`model@sha256:...`) names one exact blob; the part
    # before the `@` is still the tag Ollama lists it under.
    name = name.split("@", 1)[0]
    return name if ":" in name.rsplit("/", 1)[-1] else f"{name}:latest"


@dataclass
class Need:
    """One model some role is configured to use, and whether it is here."""
    model: str
    roles: tuple[str, ...]
    present: bool = False
    bytes_estimate: int = 0
    # The fallback narrator is worth having and is not worth blocking a first game
    # over: it exists for the turns the narrator burns all five attempts on, and a
    # campaign that never hits one will never call it. Keeping it optional is what
    # makes the mandatory download 7.4 GB rather than 9.9 GB.
    required: bool = True

    def as_dict(self) -> dict:
        return {"model": self.model, "roles": list(self.roles), "present": self.present,
                "bytes": self.bytes_estimate, "required": self.required}


@dataclass
class Report:
    """What the app found, in the words the setup page says back."""
    # "ready" | "missing-models" | "not-running" | "not-installed" | "unreachable"
    state: str
    host: str
    why: str = ""
    needs: list[Need] = field(default_factory=list)
    hosted: list[str] = field(default_factory=list)
    disk_free: int = 0
    disk_needed: int = 0

    @property
    def ok(self) -> bool:
        """Whether a turn can be attempted. Missing *optional* models never block."""
        return self.state == "ready"

    def as_dict(self) -> dict:
        return {
            "state": self.state, "ok": self.ok, "host": self.host, "why": self.why,
            "needs": [n.as_dict() for n in self.needs],
            "hosted": self.hosted,
            "disk_free": self.disk_free, "disk_needed": self.disk_needed,
            "download": DOWNLOAD_PAGE,
        }


def ollama_on_disk() -> bool:
    """Whether Ollama is installed but simply not running.

    The socket cannot tell these apart — a refused connection is a refused connection
    whether the binary exists or not — and they have different fixes: one is a 900 MB
    download and the other is starting a program that is already there. So the question
    is asked of the filesystem.

    Windows installs per user and needs no administrator, which is why
    `%LOCALAPPDATA%\\Programs\\Ollama` is checked before anything under Program Files.
    """
    names = ("ollama.exe", "ollama")
    if shutil.which("ollama"):
        return True
    roots = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots += [Path(local) / "Programs" / "Ollama", Path(local) / "Ollama"]
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if base:
            roots.append(Path(base) / "Ollama")
    roots += [Path("/usr/local/bin"), Path("/usr/bin"), Path("/opt/homebrew/bin"),
              Path.home() / ".ollama" / "bin"]
    for root in roots:
        for name in names:
            try:
                if (root / name).exists():
                    return True
            except OSError:
                continue
    return False


def models_dir() -> Path:
    """Where Ollama keeps the weights, which is the drive that has to have room.

    Not the install directory: `%LOCALAPPDATA%\\Programs\\Ollama` holds a few hundred
    megabytes of binary and the blobs go somewhere else entirely, so checking the
    install drive would happily approve a 7.4 GB download onto a full disk.
    """
    override = os.environ.get("OLLAMA_MODELS")
    if override:
        return Path(override)
    return Path.home() / ".ollama" / "models"


def _free_bytes() -> int:
    """Free space on the models drive, or 0 when it cannot be told.

    Walks up to the first parent that exists: on a machine with no Ollama, nothing
    under `~/.ollama` has been created yet, and `disk_usage` raises on a path that is
    not there. Zero means "unknown" and the caller declines to warn rather than
    inventing a number.
    """
    path = models_dir()
    for candidate in [path, *path.parents]:
        try:
            if candidate.exists():
                return shutil.disk_usage(candidate).free
        except OSError:
            continue
    return 0


def is_local(host: str) -> bool:
    """Whether this host is the machine the app is running on.

    Disk space and "is the binary installed" are questions about *this* box. A player
    who has pointed the narrator at Ollama on another machine on the LAN — which the
    settings page allows — must not be told their own C: drive is too full.
    """
    return any(mark in (host or "") for mark in ("localhost", "127.0.0.1", "::1", "[::1]"))


def needs(roles: dict | None = None) -> list[Need]:
    """Every distinct Ollama model the configured roles call for, deduplicated.

    Deduplicated because three of the four shipped roles point at the same model, and a
    setup page that listed "narrator 7.4 GB, consequence 7.4 GB, watcher 7.4 GB" would
    be telling a player they are about to download 22 GB.
    """
    from . import modelcfg

    live = roles if roles is not None else modelcfg.roles()
    order: list[str] = []
    by_model: dict[str, list[str]] = {}
    for role, _label, _why in modelcfg.ROLES:
        cfg = live.get(role) or {}
        if (cfg.get("provider") or "ollama") != "ollama":
            continue
        model = _norm(cfg.get("model", ""))
        if not model:
            continue
        if model not in by_model:
            by_model[model] = []
            order.append(model)
        by_model[model].append(role)
    return [Need(model=m, roles=tuple(by_model[m]),
                 bytes_estimate=KNOWN_SIZES.get(m, 0),
                 # A model no role but the backup narrator wants is the backup
                 # narrator, whatever it has been pointed at.
                 required=set(by_model[m]) != {"fallback"})
            for m in order]


def hosted_roles(roles: dict | None = None) -> list[str]:
    """Roles pointed at something other than Ollama, which this check cannot speak for.

    A player who has put an API key in has already solved this problem, and the setup
    page must not stand in front of a game it has no reason to block.
    """
    from . import modelcfg

    live = roles if roles is not None else modelcfg.roles()
    return [role for role, _l, _w in modelcfg.ROLES
            if ((live.get(role) or {}).get("provider") or "ollama") != "ollama"]


def check(timeout: int = 3) -> Report:
    """One HTTP call, and the whole first-run story told from its answer."""
    from . import modelcfg

    live = modelcfg.roles()
    wanted = needs(live)
    hosted = hosted_roles(live)
    host = ((live.get("narrator") or {}).get("host")
            or settings.MODELS["narrator"]["host"])

    # Nothing local is wanted at all: every role is on a hosted provider. There is no
    # Ollama to find and nothing to download, and saying "Ollama is not running" to
    # somebody playing on an API key would be a lie with a button under it.
    if not wanted:
        return Report(state="ready", host=host, hosted=hosted)

    found = gm_client.probe(host, timeout)
    if not found.reachable:
        if found.refused and is_local(host):
            state = "not-running" if ollama_on_disk() else "not-installed"
        elif found.refused:
            state = "not-running"
        else:
            state = "unreachable"
        return Report(state=state, host=host, why=found.why, needs=wanted,
                      hosted=hosted, disk_free=_free_bytes() if is_local(host) else 0,
                      disk_needed=sum(n.bytes_estimate for n in wanted))

    have = {_norm(name) for name in found.installed}
    for need in wanted:
        need.present = need.model in have
    missing = [n for n in wanted if not n.present and n.required]
    return Report(
        state="ready" if not missing else "missing-models",
        host=host, needs=wanted, hosted=hosted,
        disk_free=_free_bytes() if is_local(host) else 0,
        disk_needed=sum(n.bytes_estimate for n in wanted if not n.present),
    )


def room_for(report: Report) -> str:
    """A warning about disk space, or "" when there is room or no way to tell."""
    if not report.disk_needed or not report.disk_free:
        return ""
    if report.disk_free >= report.disk_needed + DISK_HEADROOM:
        return ""
    return (f"{gb(report.disk_free)} free on the drive holding {models_dir()}, and the "
            f"download needs about {gb(report.disk_needed)}. Free some space first — a "
            f"pull that runs out part way leaves a partial file behind.")


def gb(n: int) -> str:
    """Bytes as the number a person would say. Decimal GB, because that is what the
    model's own page says and a player comparing the two must see one number."""
    if not n:
        return "an unknown amount"
    return f"{n / 1_000_000_000:.1f} GB"


def pull(model: str, host: str = "", timeout: int = 60):
    """Stream Ollama's own pull progress, one dict per update.

    **Over HTTP, never as a subprocess.** `ollama pull` on the PATH would be the
    shorter code, and `pathfindergm/version.py` records in full what happened the last
    time this app shelled out from the frozen build under the Electron shell: git hung
    on the Windows pipes, the timeout killed the wrapper and left the real process
    holding them, and `communicate()` waited on those pipes forever (bpo-38207) while
    three requests parked on the join and the player saw an empty window. That was a
    call that should have taken 20 ms. This one takes twenty minutes, runs while the
    player watches a progress bar, and has no PATH to find and no pipe to deadlock.

    Yields Ollama's own frames — `{"status": ..., "total": ..., "completed": ...}` —
    and finally one of our own carrying `done` or `error`, so a consumer that reaches
    the end of the stream always knows which it was.
    """
    host = host or settings.MODELS["narrator"]["host"]
    body = json.dumps({"model": model, "stream": True}).encode("utf-8")
    req = urllib.request.Request(f"{host.rstrip('/')}/api/pull", data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    frame = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(frame, dict):
                    continue
                # Ollama reports a failed pull in-band, with a 200 and an `error` key.
                # Read as progress it would look like a download that simply stopped.
                if frame.get("error"):
                    yield {"error": str(frame["error"])}
                    return
                yield frame
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", "")
        except Exception:
            pass
        yield {"error": detail or f"Ollama refused the pull ({exc.code}). "
                                  f"Check the model name."}
        return
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        yield {"error": f"lost the connection to {host}: {exc}"}
        return
    yield {"done": True, "model": model}
