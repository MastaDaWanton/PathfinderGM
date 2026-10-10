"""The report a player makes for the developer: one zip, built here, never read by a page.

The owner's design (2026-10-08): a button in Settings builds one zip, it lands in the
player's Downloads folder, and beside it the app offers two ways to send it, a prefilled
GitHub issue and a prefilled email. The zip carries enough to see the whole context of a
problem (the logs, the current campaign's turn log, the end of its transcript, and the save
itself, included by default) and nothing that is the player's to keep.

How others did it, and what this took from them:

  **VS Code's Report Issue** prefills `github.com/.../issues/new?title=&body=` and, once
  the body outgrows what GitHub accepts in a URL, gives up on the URL and puts the text on
  the clipboard instead ("There is too much data to send to GitHub directly. The data will
  be copied to the clipboard", microsoft/vscode#100054, #42985). Users found that path
  confusing enough to file issues about it. So the URL here carries only the short things
  (version, system, the player's own words cut to fit) and everything long goes in the
  zip, which is attached by hand. The exact limit VS Code uses could not be confirmed
  from its source; GitHub answers 414 somewhere past 8 KB, so this stays well under at
  `GITHUB_URL_LIMIT`.

  **Factorio** asks for `factorio-current.log` with every report and tells players where
  it is (`%APPDATA%\\Factorio`); its forum's standing complaint is reports without one.
  Hence one button that finds the logs itself rather than a manual page saying where.

  **Signal Desktop** shows the debug log before it is submitted, and its redaction once
  missed forward-slash `file:///C:/Users/<name>` paths (signalapp/Signal-Desktop#2869).
  Hence the listing before saving, and `pathfindergm/redact.py`'s every-spelling paths.

  **mailto cannot attach a file** (RFC 6068 has no attachment field), and Windows mail
  handlers drop or truncate a mailto URL past about 2,000 characters (measured by others
  at 2,046 for Outlook from Chrome and Firefox; at 2,083 in IE). The email therefore says
  to attach the zip, and the URL stays under `MAILTO_LIMIT`.

Nothing here sends anything anywhere. The zip is saved on the player's own machine, and
both delivery routes open the player's own browser or mail program with a draft they can
read, change or throw away.
"""
from __future__ import annotations

import io
import json
import os
import platform
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit

from django.conf import settings

from pathfindergm import redact

ISSUES_URL = "https://github.com/MastaDaWanton/PathfinderGM/issues/new"
# Given by the owner for exactly this purpose (2026-10-08).
DEVELOPER_EMAIL = "mastadawanton@gmail.com"

# GitHub refuses a new-issue URL somewhere past 8 KB (414). Kept well under, because
# the browser, the shell and GitHub's own redirect through sign-in each add their share.
GITHUB_URL_LIMIT = 6000
# Windows mail handlers: ~2,000 characters is where a mailto stops working at all.
MAILTO_LIMIT = 1900

# How much of the transcript rides along as readable text. The save carries all of it;
# this is the part a person reads first.
TRANSCRIPT_TAIL = 80

PREFIX = "pathfindergm-report-"

# Never in the zip, and said so in the manifest, so the developer reading a report knows
# their absence is deliberate rather than a bug in the report.
LEFT_OUT = (
    "secret.key: this install's own signing key",
    "models.json: your API keys (the models named in this manifest are read from it, "
    "the keys are not)",
    "the phone pass, wherever a log line held it",
    "your Windows user name, wherever a path held it",
)


# The kinds of member that go only when "Include the save" is ticked.
WITH_THE_SAVE = ("save", "corrections")


@dataclass
class Member:
    name: str        # the path inside the zip
    data: bytes
    kind: str        # manifest, words, log, turnlog, transcript, save, corrections
    note: str = ""


# --- where things are -------------------------------------------------------------------

def data_root() -> Path:
    """The player's data folder. Read off `CAMPAIGN_DIR` as `modelcfg` reads it, so a test
    that points the campaigns somewhere else points the whole report there too; in the app
    it is `pathfindergm.paths.user_data_root()`."""
    return Path(settings.CAMPAIGN_DIR).parent


def zip_name(now: datetime | None = None) -> str:
    """`pathfindergm-report-20261008-153012.zip`. The Electron shell recognises a report
    download by this shape (`electron/main.js`, `REPORT_NAME`), so it is pinned by a test."""
    return f"{PREFIX}{(now or datetime.now()):%Y%m%d-%H%M%S}.zip"


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _secrets() -> dict[str, str]:
    """The values this install actually holds that must not travel, each with the label
    it is replaced by: every saved API key, the secret key, and the phone pass open now."""
    out: dict[str, str] = {}
    try:
        from . import modelcfg

        out.update({v: redact.KEY for v in modelcfg.keys().values()})
    except Exception:
        pass
    key = _read_text(data_root() / "secret.key")
    if key and key.strip():
        out[key.strip()] = "<secret key>"
    try:
        from pathfindergm import lan

        if lan.token():
            out[lan.token()] = "(the pass)"
    except Exception:
        pass
    return out


def _clean(text: str, secrets: dict[str, str]) -> str:
    return redact.scrub(text, secrets=secrets)


# --- what the app is ------------------------------------------------------------------

def app_version() -> str:
    """The release the player installed: `0.2.11`.

    The Electron shell knows it (`app.getVersion()`) and hands it to the backend it
    spawns as `PATHFINDER_GM_APP_VERSION`; the backend exe on its own has no copy of
    `package.json`. In a working copy, `electron/package.json` is read directly."""
    given = os.environ.get("PATHFINDER_GM_APP_VERSION", "").strip()
    if given:
        return given
    from pathfindergm.paths import is_frozen, resource_root

    if not is_frozen():
        try:
            pkg = json.loads((resource_root() / "electron" / "package.json")
                             .read_text(encoding="utf-8"))
            return f"{pkg.get('version', '?')} (working copy)"
        except (OSError, ValueError):
            pass
    return "unknown"


def _host(url: str) -> str:
    """A model host with any credentials, path and query taken off: scheme, name, port."""
    try:
        parts = urlsplit(str(url or ""))
    except ValueError:
        return ""
    if not parts.hostname:
        return ""
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname}{port}"


def models() -> dict:
    """Which model holds which job, by name, and which providers have a key: names only."""
    try:
        from . import modelcfg

        roles = modelcfg.roles()
        keyed = sorted(modelcfg.keys())
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "roles": {role: {"provider": cfg.get("provider", ""),
                         "model": cfg.get("model", ""),
                         "host": _host(cfg.get("host", ""))}
                  for role, cfg in roles.items()},
        "providers_with_a_key": keyed,
    }


def _ollama(roles: dict, probe: bool) -> dict:
    """Whether the Ollama the narrator uses answers, and what it has, by name."""
    if not probe:
        return {"asked": False}
    narrator = (roles.get("roles") or {}).get("narrator") or {}
    if narrator.get("provider", "ollama") != "ollama":
        return {"asked": False, "why": "the narrator is not on Ollama"}
    try:
        from gm.client import probe as ask
        from . import modelcfg

        host = modelcfg.roles().get("narrator", {}).get("host") or "http://localhost:11434"
        found = ask(host, timeout=2)
    except Exception as exc:
        return {"asked": True, "error": f"{type(exc).__name__}: {exc}"}
    return {"asked": True, "reachable": found.reachable, "installed": list(found.installed),
            "why": found.why}


def system() -> dict:
    out = {"platform": platform.platform(), "machine": platform.machine(),
           "python": f"{platform.python_implementation()} {platform.python_version()}"}
    if sys.platform == "win32":
        release, build, *_ = platform.win32_ver() + ("",)
        out["windows"] = f"{release} {build}".strip()
        try:
            out["windows_edition"] = platform.win32_edition()
        except Exception:
            pass
    return out


def shell() -> dict:
    """The desktop app's shell, when there is one. Set by `electron/main.js` on spawn."""
    electron = os.environ.get("PATHFINDER_GM_ELECTRON_VERSION", "").strip()
    return {"kind": "desktop app" if electron else "browser",
            "electron": electron or None,
            "chrome": os.environ.get("PATHFINDER_GM_CHROME_VERSION", "").strip() or None}


# --- the campaign ---------------------------------------------------------------------

def _campaign() -> tuple[str, Path] | None:
    """The campaign being played and its save file, read from disk. Never loaded: a report
    must not start a game, and the save on disk is always a whole one (it lands by rename,
    `pathfindergm/files.py`), which is exactly the state worth showing."""
    try:
        from . import campaign as campaign_mod
        from pathfindergm import files

        cid = campaign_mod.active_id()
        path = files.child(Path(settings.CAMPAIGN_DIR), cid)
    except Exception:
        return None
    return (cid, path) if path.is_file() else None


def _transcript_text(beats: list) -> str:
    lines = []
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        who = str(beat.get("who") or "?")
        kind = beat.get("kind")
        label = f"{who}/{kind}" if kind else who
        lines.append(f"[{label}] {str(beat.get('text') or '').strip()}")
    return "\n\n".join(lines) + "\n"


# --- the zip --------------------------------------------------------------------------

def members(description: str = "", include_save: bool = True, *,
            probe: bool = True, note: str = "", now: datetime | None = None) -> list[Member]:
    """Everything that goes in the zip, already cleaned, in the order it is listed.

    One function for both the listing the player reads before saving and the zip itself,
    so what they were shown is what they get. `note` is a line from whatever opened the
    report (the shell's startup failure, the stalled-model message), kept apart from the
    player's own words."""
    now = now or datetime.now()
    secrets = _secrets()
    root = data_root()
    out: list[Member] = []

    words = description.strip() or "(nothing was written)"
    if note.strip():
        words += "\n\n--- from the app ---\n" + note.strip()
    out.append(Member("what-went-wrong.txt",
                      (_clean(words, secrets) + "\n").encode("utf-8"), "words",
                      "your words"))

    for rel in ("logs/pathfindergm.log", "logs/update.log"):
        text = _read_text(root / rel)
        if text is not None:
            out.append(Member(rel, _clean(text, secrets).encode("utf-8"), "log"))

    camp = _campaign()
    info: dict = {"played": False}
    if camp:
        cid, path = camp
        raw = _read_text(path) or ""
        try:
            save = json.loads(raw)
        except ValueError:
            save = None
        info = {"played": True, "id": cid, "save_file": path.name,
                "save_included": bool(include_save)}
        if isinstance(save, dict):
            turn_log = save.get("turn_log") or []
            beats = save.get("transcript") or []
            info.update({"save_version": save.get("save_version"),
                         "world": redact.paths_without_user(
                             str(save.get("world_source") or "")),
                         "turns_logged": len(turn_log),
                         "transcript_beats": len(beats)})
            out.append(Member("campaign/turn-log.json", _clean(
                json.dumps(turn_log, indent=1, ensure_ascii=False), secrets)
                .encode("utf-8"), "turnlog"))
            out.append(Member("campaign/transcript-tail.txt", _clean(
                _transcript_text(beats[-TRANSCRIPT_TAIL:]), secrets).encode("utf-8"),
                "transcript", f"the last {min(len(beats), TRANSCRIPT_TAIL)} beats"))
        else:
            info["unreadable"] = True
        if include_save:
            out.append(Member(f"campaign/save/{path.name}",
                              _clean(raw, secrets).encode("utf-8"), "save",
                              "the whole game as it stands"))

    # The beats the player marked wrong and what replaced them (play/corrections.py), with
    # the save: the same choice, because both carry the story as the player read it. An
    # intimate beat's prompt is withheld here (`corrections.for_report`).
    if include_save:
        try:
            from . import corrections

            log = corrections.for_report()
        except Exception:  # noqa: BLE001 — a report never fails over its extras
            log = None
        if log:
            out.append(Member("training/corrections.jsonl",
                              _clean(log, secrets).encode("utf-8"), "corrections",
                              "the beats you marked wrong, and what replaced them"))

    roles = models()
    manifest = {
        "report": {"made": now.isoformat(timespec="seconds"), "format": 1},
        "app": {"version": app_version(), "build": _build(), "frozen": _frozen()},
        "shell": shell(),
        "system": system(),
        "models": roles,
        "ollama": _ollama(roles, probe),
        "campaign": info,
        "files": [{"name": m.name, "bytes": len(m.data)} for m in out],
        "left_out_on_purpose": list(LEFT_OUT),
    }
    text = _clean(json.dumps(manifest, indent=2, ensure_ascii=False), secrets)
    out.insert(0, Member("manifest.json", text.encode("utf-8"), "manifest",
                         "versions, system and models by name"))
    return out


def _build() -> str:
    try:
        from pathfindergm import version

        # A working copy asks git on a thread; a second is plenty, and frozen it is a file.
        return version.build(wait=1.0)
    except Exception:
        return "unknown"


def _frozen() -> bool:
    from pathfindergm.paths import is_frozen

    return is_frozen()


def build(description: str = "", include_save: bool = True, **kw) -> bytes:
    """The zip, as bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for m in members(description, include_save, **kw):
            zf.writestr(m.name, m.data)
    return buf.getvalue()


def listing(include_save: bool = True, **kw) -> dict:
    """What the page shows before saving: each file and its size, the save marked."""
    found = members("", True, **kw)
    return {
        "files": [{"name": m.name, "bytes": len(m.data), "kind": m.kind, "note": m.note,
                   "included": include_save or m.kind not in WITH_THE_SAVE}
                  for m in found],
        "has_save": any(m.kind == "save" for m in found),
        "left_out": list(LEFT_OUT),
    }


# --- sending it -----------------------------------------------------------------------

def _fit(make, text: str, limit: int) -> str:
    """`make(text)` for the longest start of `text` that keeps the URL under `limit`."""
    url = make(text)
    if len(url) <= limit:
        return url
    cut = " ... (cut short here; the whole text is in the zip)"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(make(text[:mid].rstrip() + cut)) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return make(text[:lo].rstrip() + cut if lo else cut.strip())


def links(description: str, zip_file: str) -> dict:
    """The prefilled GitHub issue and email for a saved report. Built here, opened by the
    player's own browser or mail program; nothing is sent by the app."""
    secrets = _secrets()
    words = _clean(description.strip(), secrets) or "(nothing was written)"
    first = words.splitlines()[0] if description.strip() else ""
    if len(first) > 80:
        # At a word: cut mid-token, a scrubbed key read "my key <api" in the title.
        first = first[:80].rsplit(" ", 1)[0] + "..."
    title = f"Report: {first}" if first else "A problem report"
    zip_file = Path(str(zip_file or zip_name())).name
    sysinfo = system()
    where = f"{sysinfo.get('windows') or sysinfo['platform']}"
    facts = (f"Version: {app_version()} (build {_build()})\n"
             f"System: {where}\n"
             f"Shell: {shell()['kind']}\n")

    def issue(text: str) -> str:
        body = (f"What went wrong:\n\n{text}\n\n{facts}\n"
                f"The report is {zip_file}, in my Downloads folder. "
                f"(Drag it into this box before you submit, so it is attached.)\n")
        return f"{ISSUES_URL}?title={quote(title, safe='')}&body={quote(body, safe='')}"

    def mail(text: str) -> str:
        crlf = "\r\n"           # RFC 6068: line breaks in a mailto body are %0D%0A
        body = (f"What went wrong:{crlf}{crlf}{text.replace(chr(10), crlf)}{crlf}{crlf}"
                f"{facts.replace(chr(10), crlf)}{crlf}"
                f"Attach {zip_file} from your Downloads folder to this email before you "
                f"send it. An email link cannot attach it for you.\r\n")
        return (f"mailto:{DEVELOPER_EMAIL}?subject={quote('Pathfinder GM ' + title, safe='')}"
                f"&body={quote(body, safe='')}")

    return {"github": _fit(issue, words, GITHUB_URL_LIMIT),
            "mailto": _fit(mail, words, MAILTO_LIMIT),
            "zip": zip_file}


def save_to(folder: Path, description: str = "", include_save: bool = True,
            **kw) -> Path:
    """Write the zip into `folder` under a name not already taken. For the desktop shell's
    startup-failure box (`desktop.py --report`), where no page exists to download it."""
    folder.mkdir(parents=True, exist_ok=True)
    name = zip_name()
    target = folder / name
    n = 1
    while target.exists():
        target = folder / name.replace(".zip", f"-{n}.zip")
        n += 1
    data = build(description, include_save, **kw)
    tmp = target.with_suffix(".zip.part")
    tmp.write_bytes(data)
    os.replace(tmp, target)
    return target
