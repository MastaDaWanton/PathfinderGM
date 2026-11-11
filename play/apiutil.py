"""Reading what the browser sent without trusting it.

Every endpoint opened the same way — `json.loads(request.body or "{}")` and then
`body.get(...)` — and that line raises on four separate shapes of input:

* malformed JSON is a `JSONDecodeError`;
* a bare array, string or `null` parses perfectly well and then dies on `.get`.

Measured by probing one endpoint with twenty-seven hostile bodies: seven came back as
HTTP 500 with a traceback, and four of the seven were that one line. In the packaged app
a 500 is a button that does nothing and says nothing, which is the failure mode
CLAUDE.md already records for a hidden required field.

The numbers had the same problem one level down. `int(body.get("hours", 1) or 1)` is
fine for a number and raises for `"many"`, for `[1, 2]` and for `NaN` — three more of
the seven.

Neither of these is a case for a friendly error message. A browser that sends a JSON
array where an object belongs is not a player making a mistake; it is a bug or a probe,
and the right answer is to read nothing out of it and carry on with the defaults, which
is exactly what an empty object does.
"""
from __future__ import annotations

import json
import math


def read_body(request) -> dict:
    """The request's JSON object. Anything that is not one reads as empty."""
    try:
        body = json.loads(request.body or "{}")
    except (ValueError, TypeError):
        return {}
    return body if isinstance(body, dict) else {}


def script_json(obj) -> str:
    """`obj` as JSON that is safe to write inside an inline `<script>` block.

    `json.dumps` leaves `<` alone and the HTML parser ends a script at the first
    `</script>` whatever JavaScript thinks of it. Measured 2026-11-11:
    `GET /outfit/?character=</script><script>alert(1)</script>` came back 200 with the
    payload raw in the page, and a character name, a world name or a LAN guest's line
    did the same on the table. The three characters are written as `\\uXXXX`, which
    JavaScript reads back as the same string, so the page parses the identical object.
    U+2028/U+2029 need nothing: `ensure_ascii` (the default) already escapes them.
    """
    return (json.dumps(obj).replace("<", "\\u003c")
            .replace(">", "\\u003e").replace("&", "\\u0026"))


def read_int(body: dict, key: str, default: int = 0,
             *, lo: int | None = None, hi: int | None = None) -> int:
    """One integer out of a body, clamped, never raising.

    `True` is deliberately not 1 here. `isinstance(True, int)` is True in Python, so a
    JSON `true` sailed through `int()` and became an hour — a real difference between
    "the client sent a boolean by mistake" and "the player asked for one hour".
    """
    raw = body.get(key, default)
    if isinstance(raw, bool) or raw is None:
        value = default
    elif isinstance(raw, (int, float)):
        value = default if isinstance(raw, float) and not math.isfinite(raw) else int(raw)
    else:
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            value = default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value
