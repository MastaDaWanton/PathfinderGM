# Display font

**Cinzel**, the carved-Roman-capital face the sheet, the craft bench, the class builder and
the engraved numerals on the 3D dice are drawn in. Two weights ship here:

```
Cinzel-Regular.woff2     400
Cinzel-SemiBold.woff2    600
```

Cinzel is a Trajan-inspired face by Natanael Gama, released under the **SIL Open Font
License 1.1**, which permits embedding and redistribution inside an application including
a commercial one. That licence is why it is the right choice here: most Trajan-style faces
are commercial and may not be shipped inside a `.exe`. `OFL.txt` is the licence, which the
OFL requires to travel with the font — the same way the OGL requires its licence to travel
with the rules, see [`../../../OGL-NOTICE.md`](../../../OGL-NOTICE.md). `FONTLOG.txt` is
upstream's, which asks the same of derivative works, and the SemiBold is one.

Cinzel carries **no Reserved Font Name** — its copyright line names none — so the
interpolated SemiBold keeps the family name legitimately.

## Where these two files came from

Not from the Google Fonts download button. Upstream Cinzel v2 is a *single variable font*
with a continuous 400–900 weight axis, and there is no static SemiBold in it to download:
600 is an interpolation, and upstream's STAT table names only 400, 700 and 900.

[`../../../tools/build_fonts.py`](../../../tools/build_fonts.py) fetches the variable font
from the `google/fonts` repository, pins it at each weight, converts to woff2 and checks
the result — that the OFL notice survived in the name table, that all 367 codepoints are
still there, and that the SemiBold is genuinely heavier rather than a renamed copy of the
Regular. It is byte-reproducible, so the committed files can be regenerated and compared:

```bash
python -m pip install "fonttools[woff]" && python tools/build_fonts.py && git diff --stat
```

Nothing at runtime reads a font file — the app only serves it — so `fonttools` is a
build-time tool and stays out of `requirements.txt`.

## Why the app does not download it for you

Everything the app needs has to work offline and be present in the packaged build. A font
fetched at runtime from a CDN would break the moment the machine was offline, which is the
one condition this project is built to survive. `pathfindergm.spec` ships `play/static`
whole, so these files are in the `.exe` without a spec change.

## If they are ever missing again

The CSS keeps `local("Cinzel")` ahead of the `url()` and a Palatino/Georgia stack behind
it, so an empty folder degrades rather than breaks. That is also how the gap hid for so
long: on a machine with Cinzel installed the 404 is invisible, and everywhere else the
page silently wore the fallback. `tests/test_fonts.py` is what notices now.
