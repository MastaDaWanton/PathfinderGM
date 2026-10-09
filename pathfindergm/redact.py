"""What must never leave this machine inside a report, taken out of text.

One module, because the rule has two callers and a rule with two copies drifts (CLAUDE.md:
"when you fix a rule, grep for every copy of it"). `desktop.py` masks the LAN pass before a
line reaches `logs/pathfindergm.log`; `pathfindergm/report.py` runs every text file it
puts in the zip a player sends the developer through `scrub`. Neither may know a pattern
the other does not.

Prior art, and what it taught:

  **Signal Desktop's debug log** redacted Windows home paths written with backslashes and
  missed the same path written as a `file:///C:/Users/<name>/...` URL with forward
  slashes, so usernames (often a legal name) went to a public log host
  (signalapp/Signal-Desktop#2869). So a path is matched with either slash, doubled
  backslashes as JSON writes them, and percent-encoded separators as a URL writes them.

  **Paths, not words.** The username is replaced where it sits in a path, never wherever
  the word appears: a player called Mark whose character says "a mark on the wall" must
  get their transcript back intact, and the owner asked for "the Windows username in
  paths". A name typed into the game as prose is the player's own words.

  **Known values, then shapes.** The keys actually saved in `models.json` and this
  install's `secret.key` are replaced by value wherever they appear, and then the common
  hosted-key shapes and `Bearer` headers by pattern, because a key that leaked into a log
  through somebody's error message is not one this module was told about.
"""
from __future__ import annotations

import re
from pathlib import Path

# `?k=` is `pathfindergm.lan.QUERY_KEY`. The value stops at the first character that
# cannot be in a pass, so a pass inside a JSON string keeps its closing quote. The first
# version (`[^&\s]+`, in desktop.py) ate `ABC",` out of `"?k=ABC", "next"` — harmless on
# a console line, a broken save inside a report.
_PASS = re.compile(r"([?&]k=)[^&\s\"'<>\\]+")

# `C:\Users\name`, `C:/Users/name`, `C:\\Users\\name` (JSON), `/Users/name` (macOS).
_USERS = re.compile(r"(?i)([\\/]Users[\\/]+)([^\\/\s\"'<>:*?|]+)")
# `%5CUsers%5Cname`, `%2FUsers%2Fname` (a path inside a URL).
_USERS_ENCODED = re.compile(r"(?i)((?:%5C|%2F)Users(?:%5C|%2F)+)([^%\s\"'<>&]+)")
# `/home/name` on Linux.
_HOME = re.compile(r"(/home/+)([^/\s\"'<>:]+)")

# The shapes hosted providers give their keys, for a key nobody told this module about.
_KEY_SHAPES = re.compile(
    r"\b(?:sk-(?:ant-|proj-|or-)?[A-Za-z0-9_\-]{16,}"   # OpenAI, Anthropic, OpenRouter
    r"|AIza[0-9A-Za-z_\-]{30,}"                           # Google
    r"|gsk_[A-Za-z0-9]{20,}"                              # Groq
    r"|xai-[A-Za-z0-9]{20,})")                            # xAI
_BEARER = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/\-]{8,}=*")
_KEY_PARAM = re.compile(r"(?i)([?&](?:key|api_key|apikey|token|access_token)=)[^&\s\"'<>]+")
# `http://user:secret@host` — credentials carried in a URL.
_URL_CREDENTIALS = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^/\s@\"'<>]+@")

USER = "<user>"
KEY = "<api key>"


def without_pass(text: str) -> str:
    """`text` with any `?k=` pass masked. The log's rule since 2026-09-25 (desktop.py)."""
    return _PASS.sub(r"\1(the pass)", text)


def _home_variants() -> list[tuple[str, str]]:
    """This user's home directory as text, in each spelling a file might hold it.

    For a profile that does not live under `Users` (a redirected `D:\\Profiles\\bob`),
    which the path patterns below would not recognise."""
    out: list[tuple[str, str]] = []
    try:
        home = Path.home()
    except Exception:
        return out
    if not home.name:
        return out
    plain = str(home)
    masked = str(home.parent / USER)
    for a, b in ((plain, masked),
                 (plain.replace("\\", "/"), masked.replace("\\", "/")),
                 (plain.replace("\\", "\\\\"), masked.replace("\\", "\\\\"))):
        if len(a) > 3:
            out.append((a, b))
    return out


def paths_without_user(text: str) -> str:
    """`text` with the user's name taken out of every path it appears in."""
    for plain, masked in _home_variants():
        text = re.sub(re.escape(plain), lambda _m, m=masked: m, text, flags=re.I)
    text = _USERS.sub(lambda m: m.group(1) + USER, text)
    text = _USERS_ENCODED.sub(lambda m: m.group(1) + USER, text)
    text = _HOME.sub(lambda m: m.group(1) + USER, text)
    return text


def scrub(text: str, *, secrets=()) -> str:
    """Everything above, in one pass, plus each value in `secrets` replaced outright.

    `secrets` are the values this install actually holds (its API keys, its secret key,
    the pass open right now): a mapping of value to the label it is replaced with, or
    plain values, which read as API keys. Replaced first and longest first, so a key that
    contains a shorter one is not left half-masked."""
    labels = dict(secrets) if isinstance(secrets, dict) else {s: KEY for s in secrets}
    for value in sorted((s for s in labels if s and len(s) >= 6), key=len, reverse=True):
        text = text.replace(value, labels[value])
    text = without_pass(text)
    text = _URL_CREDENTIALS.sub(lambda m: m.group(1) + "<credentials>@", text)
    text = _KEY_PARAM.sub(lambda m: m.group(1) + KEY, text)
    text = _BEARER.sub(lambda m: m.group(1) + KEY, text)
    text = _KEY_SHAPES.sub(KEY, text)
    return paths_without_user(text)
