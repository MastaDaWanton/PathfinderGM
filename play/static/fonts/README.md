# Display font

The sheet asks for **Cinzel** and falls back to Palatino when it is not here, so the app
works with this folder empty — it just looks less like carved Roman capitals.

Cinzel is a Trajan-inspired face by Natanael Gama, released under the **SIL Open Font
License 1.1**, which permits embedding and redistribution inside an application including
a commercial one. That licence is why it is the right choice here: most Trajan-style
faces are commercial and may not be shipped inside a `.exe`.

## To install it

1. Download the family from [Google Fonts](https://fonts.google.com/specimen/Cinzel) —
   the "Get font" button gives a zip.
2. Put these two files in this folder, named exactly:

   ```
   Cinzel-Regular.woff2
   Cinzel-SemiBold.woff2
   ```

   The download contains `.ttf`, not `.woff2`. Either convert them (any
   ttf-to-woff2 converter will do, and woff2 is roughly half the size) or drop the
   `.ttf` files in with the same base names and change the `format()` hints in
   `play/templates/play/table.html`.

3. Copy the licence in as `OFL.txt`. The OFL requires it to travel with the font, the
   same way the OGL requires its licence to travel with the rules — see
   [`../../../OGL-NOTICE.md`](../../../OGL-NOTICE.md).

Reload the page; no rebuild needed.

## Why the app does not download it for you

Everything the app needs has to work offline and be present in the packaged build. A
font fetched at runtime from a CDN would break the moment the machine was offline, which
is the one condition this project is built to survive.
