"""Prepare the downloaded CC0 / public-domain textures for the mock (see CREDITS.md).

    python docs/mock/table-free/textures/prepare_textures.py <folder of originals>

The folder holds the originals as downloaded, under these names: ph_wood_table_worn.jpg,
ph_brown_leather.jpg, ph_velour_velvet.jpg (Poly Haven 1K), oldpaper.jpg (Old_paper1.jpg at
1280px), linenbank.jpg (Linen_Bank_A4_backlit_watermarks.jpg) and marble1720.jpg (the 1720
marbled endpaper at 1280px). This script downloads nothing. It crops, resizes, and turns the
paper and cloth into grey detail maps that table.css tints with multiply blending.
"""
import os
import sys
from PIL import Image, ImageOps, ImageEnhance

SRC = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(__file__))


def save(im, name, q=72):
    path = os.path.join(OUT, name)
    im.save(path, "JPEG", quality=q, optimize=True, progressive=True)
    print(name, im.size, os.path.getsize(path) // 1024, "KB")


def lift(im, lo, hi):
    """Map a grey image's 2nd..98th percentile onto lo..hi, so a multiply only darkens a little."""
    im = ImageOps.autocontrast(im, cutoff=2)
    return im.point(lambda v: int(lo + (hi - lo) * v / 255))


# The desk: Poly Haven wood_table_worn, as it is, a little darker and flatter in the highlights.
desk = Image.open(os.path.join(SRC, "ph_wood_table_worn.jpg")).convert("RGB")
desk = ImageEnhance.Brightness(desk).enhance(0.82)
save(desk, "desk-walnut.jpg", 70)

# The bar's leather: Poly Haven brown_leather albedo.
leather = Image.open(os.path.join(SRC, "ph_brown_leather.jpg")).convert("RGB")
save(leather.resize((768, 768), Image.LANCZOS), "leather-brown.jpg", 70)

# The book's paper: the centre of Old_paper1.jpg (the left edge is water-stained), as a grey
# grain map between 212 and 255, keeping the foxing specks faint.
paper = Image.open(os.path.join(SRC, "oldpaper.jpg")).convert("L")
w, h = paper.size
paper = paper.crop((int(w * .12), int(h * .08), int(w * .95), int(h * .08) + int(w * .83)))
paper = paper.resize((1024, 1024), Image.LANCZOS)
save(lift(paper, 212, 255), "paper-grain.jpg", 74)

# The ledger's stock: the cloud of fibres in a backlit sheet of Linen Bank laid paper, cropped
# between its two watermarks so no lettering shows.
linen = Image.open(os.path.join(SRC, "linenbank.jpg")).convert("L")
linen = linen.crop((120, 600, 1160, 1020)).resize((1040, 420), Image.LANCZOS)
save(lift(linen, 214, 255), "ledger-fibre.jpg", 74)

# The endpaper: an 18th-century marbled pastedown, kept in its own colours.
marble = Image.open(os.path.join(SRC, "marble1720.jpg")).convert("RGB")
marble = marble.resize((640, int(640 * marble.height / marble.width)), Image.LANCZOS)
save(marble, "marbled-endpaper.jpg", 70)

# The dice tray's baize: Poly Haven velour_velvet as a grey nap map, tinted lapis in CSS.
nap = Image.open(os.path.join(SRC, "ph_velour_velvet.jpg")).convert("L").resize((512, 512), Image.LANCZOS)
save(lift(nap, 150, 255), "baize-nap.jpg", 72)
