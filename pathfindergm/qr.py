"""A QR code, drawn by us, because the alternative was a dependency.

`requirements.txt` says it in its own words: "Every dependency is another thing
PyInstaller has to be told about and another thing that can break in the frozen build,
so the Ollama client is stdlib urllib rather than requests." A QR encoder is a few
hundred lines of very well-specified arithmetic with no I/O and no platform surface —
exactly the kind of thing that is cheaper to own than to bundle. The board in
`table.html` is hand-rolled SVG for the same reason.

**Scope is deliberately small.** Byte mode, error correction level M, versions 1 to 6.
That is 134 bytes at the top end, against a URL like
`http://192.168.1.14:54321/?k=ABCDEFGHJK` — forty characters. Versions 7 and up need
an extra version-information block in two corners, and writing that code to serve a
string that cannot occur would be carrying a spare for a road we do not drive on.
Anything longer raises rather than silently producing something a phone cannot read.

Level M rather than L: L is smaller, and this code is going to be read off a glossy
laptop screen at an angle by a phone camera in a room lit for atmosphere. Fifteen percent
recovery is the cheapest insurance available here.

**Verified by Chrome, not by itself.** `tests/test_qr.py` renders the matrix and hands it
to the browser's own `BarcodeDetector`, which decodes it back to the original string. An
encoder checked only against its own output is a test that passes when the spec has been
misread — and the whole risk of writing one of these by hand is precisely that.
"""
from __future__ import annotations

# --- GF(256), the field Reed-Solomon lives in -----------------------------------------
# Primitive polynomial x^8 + x^4 + x^3 + x^2 + 1 = 0x11D, which is the one QR specifies.
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _generator(degree: int) -> list[int]:
    """The generator polynomial for `degree` error-correction codewords."""
    poly = [1]
    for i in range(degree):
        # Multiply by (x - alpha^i).
        nxt = [0] * (len(poly) + 1)
        for j, coeff in enumerate(poly):
            nxt[j] ^= coeff
            nxt[j + 1] ^= _mul(coeff, _EXP[i])
        poly = nxt
    return poly


def _remainder(data: list[int], degree: int) -> list[int]:
    """The error-correction codewords for one block."""
    gen = _generator(degree)
    rem = list(data) + [0] * degree
    for i in range(len(data)):
        factor = rem[i]
        if factor == 0:
            continue
        for j, g in enumerate(gen):
            rem[i + j] ^= _mul(g, factor)
    return rem[len(data):]


# --- The tables, for level M only -----------------------------------------------------
# (total codewords, ec codewords per block, blocks, data codewords per block).
# Versions 4 and up split into equal blocks at this level, which is why there is no
# second group here: it does not arise below version 7 at M.
_SPEC = {
    1: (26, 10, 1, 16),
    2: (44, 16, 1, 28),
    3: (70, 26, 1, 44),
    4: (100, 18, 2, 32),
    5: (134, 24, 2, 43),
    6: (172, 16, 4, 27),
}

# Bits left over after the codewords, which are placed as zeros.
_REMAINDER_BITS = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7}

# Alignment pattern centres. Version 1 has none; 2-6 have exactly one, because the only
# two coordinates combine into four positions and three of those sit under the finders.
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34]}

_ECC_M = 0b00                      # the level indicator that goes into the format bits


class TooMuchToEncode(ValueError):
    """The string does not fit in the versions this module implements."""


def _capacity(version: int) -> int:
    _total, _ec, blocks, per_block = _SPEC[version]
    return blocks * per_block


def _pick_version(length: int) -> int:
    for version in sorted(_SPEC):
        # 4 bits of mode + 8 bits of length + the data itself.
        if 4 + 8 + length * 8 <= _capacity(version) * 8:
            return version
    raise TooMuchToEncode(
        f"{length} bytes needs a QR version above 6, which this module does not "
        f"implement — see its docstring for why the ceiling is where it is.")


def _bitstream(data: bytes, version: int) -> list[int]:
    capacity = _capacity(version)
    bits: list[int] = []

    def put(value: int, width: int) -> None:
        for i in range(width - 1, -1, -1):
            bits.append((value >> i) & 1)

    put(0b0100, 4)                  # byte mode
    put(len(data), 8)               # 8-bit count field, which holds through version 9
    for byte in data:
        put(byte, 8)

    # Terminator, up to four zeros, then pad to a byte boundary.
    put(0, min(4, capacity * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    # Then the two alternating pad codewords the spec names.
    pad = (0xEC, 0x11)
    i = 0
    while len(bits) < capacity * 8:
        put(pad[i % 2], 8)
        i += 1
    return bits


def _codewords(data: bytes, version: int) -> list[int]:
    """Data and error correction, interleaved the way the spec orders them."""
    _total, ec_per_block, blocks, per_block = _SPEC[version]
    bits = _bitstream(data, version)
    flat = [int("".join(str(b) for b in bits[i:i + 8]), 2) for i in range(0, len(bits), 8)]

    groups = [flat[i * per_block:(i + 1) * per_block] for i in range(blocks)]
    checks = [_remainder(g, ec_per_block) for g in groups]

    out: list[int] = []
    for i in range(per_block):
        for g in groups:
            out.append(g[i])
    for i in range(ec_per_block):
        for c in checks:
            out.append(c[i])
    return out


# --- The matrix -----------------------------------------------------------------------

def _blank(size: int):
    return [[0] * size for _ in range(size)], [[False] * size for _ in range(size)]


def _place_function_patterns(m, reserved, version: int) -> None:
    size = len(m)

    def square(top: int, left: int, n: int, draw) -> None:
        for r in range(n):
            for c in range(n):
                rr, cc = top + r, left + c
                if 0 <= rr < size and 0 <= cc < size:
                    m[rr][cc] = draw(r, c)
                    reserved[rr][cc] = True

    def finder(top: int, left: int) -> None:
        # The 7x7 eye, plus the one-module separator around it.
        square(top - 1, left - 1, 9,
               lambda r, c: 1 if (1 <= r <= 7 and 1 <= c <= 7 and
                                  (r in (1, 7) or c in (1, 7) or (3 <= r <= 5 and 3 <= c <= 5)))
               else 0)

    finder(0, 0)
    finder(0, size - 7)
    finder(size - 7, 0)

    # Timing: the alternating run along row 6 and column 6.
    for i in range(size):
        if not reserved[6][i]:
            m[6][i] = 1 - (i % 2)
            reserved[6][i] = True
        if not reserved[i][6]:
            m[i][6] = 1 - (i % 2)
            reserved[i][6] = True

    # Alignment, everywhere the centres combine except under a finder.
    centres = _ALIGN[version]
    for r in centres:
        for c in centres:
            if reserved[r][c]:
                continue
            square(r - 2, c - 2, 5,
                   lambda rr, cc: 1 if (rr in (0, 4) or cc in (0, 4) or (rr == 2 and cc == 2))
                   else 0)

    # The dark module, which is always set and is not part of the format copies.
    m[size - 8][8] = 1
    reserved[size - 8][8] = True

    # Reserve the two format-information strips so data placement steps over them.
    for i in range(9):
        for rr, cc in ((8, i), (i, 8)):
            if 0 <= rr < size and 0 <= cc < size:
                reserved[rr][cc] = True
    for i in range(8):
        reserved[size - 1 - i][8] = True
        reserved[8][size - 1 - i] = True


def _place_data(m, reserved, codewords: list[int], version: int) -> None:
    size = len(m)
    bits: list[int] = []
    for word in codewords:
        for i in range(7, -1, -1):
            bits.append((word >> i) & 1)
    bits.extend([0] * _REMAINDER_BITS[version])

    pos = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:                      # the vertical timing line is not a data column
            col -= 1
        for i in range(size):
            row = (size - 1 - i) if upward else i
            for c in (col, col - 1):
                if reserved[row][c]:
                    continue
                m[row][c] = bits[pos] if pos < len(bits) else 0
                pos += 1
        upward = not upward
        col -= 2


_MASKS = (
    lambda i, j: (i + j) % 2 == 0,
    lambda i, j: i % 2 == 0,
    lambda i, j: j % 3 == 0,
    lambda i, j: (i + j) % 3 == 0,
    lambda i, j: (i // 2 + j // 3) % 2 == 0,
    lambda i, j: (i * j) % 2 + (i * j) % 3 == 0,
    lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0,
    lambda i, j: ((i + j) % 2 + (i * j) % 3) % 2 == 0,
)


def _penalty(m) -> int:
    """The four rules, which together are what stops a code a scanner cannot lock onto."""
    size = len(m)
    score = 0

    # 1: runs of five or more of one colour.
    for line in list(m) + [list(col) for col in zip(*m)]:
        run, last = 1, line[0]
        for cell in line[1:]:
            if cell == last:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run, last = 1, cell
        if run >= 5:
            score += 3 + (run - 5)

    # 2: every 2x2 block of one colour.
    for r in range(size - 1):
        for c in range(size - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3

    # 3: the finder-like pattern, either way round, in any row or column.
    wanted = ([1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1])
    for line in list(m) + [list(col) for col in zip(*m)]:
        for i in range(size - 10):
            if list(line[i:i + 11]) in wanted:
                score += 40

    # 4: how far the whole code is from half dark.
    dark = sum(sum(row) for row in m)
    percent = dark * 100 // (size * size)
    score += 10 * (abs(percent - 50) // 5)
    return score


def _format_bits(mask: int) -> int:
    """Fifteen bits: the level, the mask, a BCH check, and the spec's fixed XOR."""
    value = (_ECC_M << 3) | mask
    rem = value << 10
    for i in range(14, 9, -1):
        if rem & (1 << i):
            rem ^= 0b10100110111 << (i - 10)
    return ((value << 10) | rem) ^ 0b101010000010010


def _place_format(m, mask: int) -> None:
    size = len(m)
    fmt = _format_bits(mask)
    for i in range(15):
        # Most significant bit first. The format string is written into the modules in
        # the order it is printed, so the first cell holds bit 14 — the opposite of the
        # `(value >> i) & 1` reflex. Indexed the other way the code is structurally
        # perfect and every scanner rejects it, because the one field that says which
        # mask was used is backwards. Caught by cross-checking against an independent
        # encoder; nothing about the picture looks wrong.
        bit = (fmt >> (14 - i)) & 1
        # Copy one, wrapped around the top-left eye.
        if i < 6:
            m[8][i] = bit
        elif i == 6:
            m[8][7] = bit
        elif i == 7:
            m[8][8] = bit
        elif i == 8:
            m[7][8] = bit
        else:
            m[14 - i][8] = bit
        # Copy two, split between the other two eyes. Seven below the top-right and
        # eight to the right of the bottom-left — not eight and seven, because the
        # dark module already owns (size - 8, 8).
        if i < 7:
            m[size - 1 - i][8] = bit
        else:
            m[8][size - 15 + i] = bit


def matrix(text: str) -> list[list[int]]:
    """The QR modules for `text`: 1 is dark, 0 is light, no quiet zone."""
    data = text.encode("utf-8")
    version = _pick_version(len(data))
    size = 17 + 4 * version

    words = _codewords(data, version)
    best = None
    for mask in range(8):
        m, reserved = _blank(size)
        _place_function_patterns(m, reserved, version)
        _place_data(m, reserved, words, version)
        for r in range(size):
            for c in range(size):
                if not reserved[r][c] and _MASKS[mask](r, c):
                    m[r][c] ^= 1
        _place_format(m, mask)
        score = _penalty(m)
        if best is None or score < best[0]:
            best = (score, m)
    return best[1]


def svg(text: str, *, quiet: int = 4, dark: str = "#17120d",
        light: str = "#f3e7c8") -> str:
    """The code as an SVG string, sized in modules so CSS decides how big it is.

    A light background is drawn rather than left transparent, and it is not a style
    choice: this app's pages are near-black, and a QR rendered dark-on-dark is one a
    camera cannot find at all. The quiet zone is four modules because that is what the
    spec requires — a scanner may fail without it, and the failure looks like a bad code
    rather than a missing margin.
    """
    m = matrix(text)
    size = len(m)
    span = size + quiet * 2
    runs = []
    for r, row in enumerate(m):
        c = 0
        while c < size:
            if not row[c]:
                c += 1
                continue
            start = c
            while c < size and row[c]:
                c += 1
            # One rect per horizontal run rather than per module: a version 3 code is
            # 841 modules and roughly a tenth as many runs, which is the difference
            # between an inline SVG that is pleasant to ship and one that is not.
            runs.append(f'<rect x="{start + quiet}" y="{r + quiet}" '
                        f'width="{c - start}" height="1"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {span} {span}" '
        f'shape-rendering="crispEdges" role="img" aria-label="QR code">'
        f'<rect width="{span}" height="{span}" fill="{light}"/>'
        f'<g fill="{dark}">{"".join(runs)}</g></svg>'
    )
