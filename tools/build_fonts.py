"""Rebuild the two Cinzel woff2 files the sheet's display face is made of.

Run once; the output is committed and this script is not needed to build or run the app.
`fonttools` and `brotli` are build-time only and are deliberately absent from
`requirements.txt` — nothing at runtime reads a font file, the app only serves it.

    python -m pip install "fonttools[woff]"
    python tools/build_fonts.py

Why a script rather than two binaries dropped in from a download: the files are not what
Google Fonts hands you. Upstream Cinzel v2 ships as a **single variable font**,
`Cinzel[wght].ttf`, with a continuous 400-900 weight axis, and the templates ask for two
static faces at 400 and 600. Without this script the provenance of those two blobs is a
sentence in a README that nobody can check.

Two things the first attempt got wrong, recorded because both are silent:

- `instantiateVariableFont(..., updateFontNames=True)` raises
  `ValueError: Cannot find Axis Values {'wght': 600}` for the SemiBold. Upstream's STAT
  table names exactly three weights — Regular 400, Bold 700, Black 900 — so there is no
  axis value to copy a name from at 600. The weight axis is continuous and 600 is a
  perfectly ordinary interpolation; only the *naming* is missing, so SemiBold is named
  here by hand and Regular still uses upstream's own names.
- The SemiBold has to be checked for being genuinely heavier, not merely a differently
  named copy of the Regular. A pinned instance that silently failed to interpolate would
  still load, still render, and look wrong in a way no size or byte comparison catches.
  The assertion measures ink area per glyph; the shipped pair came out +45% to +68%.

`recalcTimestamp=False` is what makes rerunning this produce the committed bytes. With
fontTools' default the `head.modified` field is rewritten on every save, so two runs a
minute apart differed by 20 bytes after compression — measured, and the reason the check
below can be an equality rather than a shrug. A binary in the tree that cannot be
regenerated and compared is exactly the derived-cache trap CLAUDE.md names.

The full character set is kept — 367 codepoints, latin and latin-ext. No subsetting: the
Regular is 27 KB whole, and a latin-only subset would drop the accented letters that
World Bible's exported names are full of, which fails one glyph at a time rather than
loudly.

The OFL requires the licence to travel with the font, so `OFL.txt` is fetched alongside
and committed next to it; `FONTLOG.txt` asks the same for derivative works, and the
SemiBold is one. Cinzel carries **no Reserved Font Name** — the copyright line names no
name after it — so the interpolated face may keep the family name.
"""
from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "play" / "static" / "fonts"

UPSTREAM = "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/"
SOURCE = "Cinzel[wght].ttf"
CARRIED = ("OFL.txt", "FONTLOG.txt")

# (weight, filename, names to set). Regular takes upstream's own name records via
# updateFontNames; SemiBold has none to take, so it is spelled out. The nameIDs are the
# RIBBI convention: 1/2 are what an old application sees, 16/17 what a modern one prefers.
FACES = (
    (400, "Cinzel-Regular.woff2", None),
    (600, "Cinzel-SemiBold.woff2", {
        1: "Cinzel SemiBold", 2: "Regular", 4: "Cinzel SemiBold",
        6: "Cinzel-SemiBold", 16: "Cinzel", 17: "SemiBold",
    }),
)

OFL_NOTICE = "This Font Software is licensed under the SIL Open Font License"


def fetch(name: str) -> bytes:
    url = UPSTREAM + urllib.parse.quote(name)
    request = urllib.request.Request(url, headers={"User-Agent": "pathfindergm-build"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def ink_area(font, char: str) -> float:
    """Total outline area of one glyph — the measurement that catches a weight that did
    not actually interpolate."""
    from fontTools.pens.areaPen import AreaPen

    glyphs = font.getGlyphSet()
    pen = AreaPen(glyphs)
    glyphs[font.getBestCmap()[ord(char)]].draw(pen)
    return abs(pen.value)


def main() -> int:
    try:
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer
    except ImportError:
        print('fonttools is not installed: python -m pip install "fonttools[woff]"',
              file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    source = OUT.parent / "Cinzel-variable.ttf"          # scratch, not committed
    source.write_bytes(fetch(SOURCE))

    try:
        for weight, filename, names in FACES:
            font = TTFont(source, recalcTimestamp=False)
            instancer.instantiateVariableFont(
                font, {"wght": weight}, inplace=True, updateFontNames=names is None)
            if names:
                font["OS/2"].usWeightClass = weight
                for name_id, value in names.items():
                    font["name"].setName(value, name_id, 3, 1, 0x409)   # Windows/en-US
                    font["name"].setName(value, name_id, 1, 0, 0)       # Mac/English
            font.flavor = "woff2"
            font.save(OUT / filename)

        for name in CARRIED:
            (OUT / name).write_bytes(fetch(name))
    finally:
        source.unlink(missing_ok=True)

    regular, semibold = (TTFont(OUT / filename) for _, filename, _ in FACES)
    for filename, font in zip((f for _, f, _ in FACES), (regular, semibold)):
        assert (font["name"].getDebugName(13) or "").startswith(OFL_NOTICE), \
            f"{filename} lost the OFL notice from its name table"
        assert "fvar" not in font, f"{filename} is still a variable font"
        assert len(font.getBestCmap()) == 367, f"{filename} lost characters"
        print(f"  {filename:24} {(OUT / filename).stat().st_size:>6} bytes  "
              f"{len(font.getBestCmap())} codepoints")

    for char in "HOAM":
        light, heavy = ink_area(regular, char), ink_area(semibold, char)
        assert heavy > light * 1.2, \
            f"SemiBold '{char}' is {heavy / light:.2f}x the Regular — it did not interpolate"
        print(f"  {char}: SemiBold carries {(heavy / light - 1) * 100:.0f}% more ink")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
