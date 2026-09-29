"""Make the mock's textures from CC0 source photographs.

Resize, crop, tint, and re-light: the desk and the ornaments are lit here by the page's
lamp, from the desk's own normal and occlusion maps and from the old ornaments' own relief.
Nothing is generated or painted. Downloads nothing: the sources are the files named in
CREDITS.md, fetched by hand from Poly Haven and ambientCG into one folder, and passed as
--src:

    python docs/mock/table-layout/textures/prepare.py --src path/to/sources

Run from the repository root. It reads the app's own images in play/static/img (never
writes there) for two things only: the old textures' tone, which each new one is matched
to, and the ornaments' silhouettes, which are kept pixel for pixel.

Why match tone rather than use the photographs as they come: the owner asked for better
material, not a new palette ("keep the leather and bronze look"). The leathers and the
page are moved to the old texture's mean colour in YCbCr, and their grain is scaled to a
chosen multiple of the old texture's spread. The mean keeps the page's colour and its text
contrast; the gain is where the quality comes from (the old card leather varied by 4
levels of 255, a smear). The desk is the exception, and desk() says why.

Why the ornaments are re-lit: the old corner pieces and bosses were made in each
orientation by mirroring one render (table.html: "CSS cannot mirror a background image, so
the four corner orientations and the flipped boss are baked as files"), so whatever light
the render had is mirrored with it, and at least two corners are lit from the wrong side.
Baked here, every piece is lit by the page's one lamp, scene3d.js's LIGHT
(-0.42, -0.78, 0.47): high, left, in front.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path.cwd()
OLD = ROOT / "play" / "static" / "img"
OUT = Path(__file__).resolve().parent

LIGHT = np.array([-0.42, -0.78, 0.47])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
CARD_GAIN, CARD_LIFT = 1.6, -19.0


def load(path: Path, mode: str = "RGB") -> Image.Image:
    return Image.open(path).convert(mode)


def ycc(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("YCbCr")).astype(np.float64)


def from_ycc(a: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "YCbCr").convert("RGB")


def match(im: Image.Image, ref: Image.Image, gain: float, chroma_gain: float = 1.0,
          lift: float = 0.0) -> Image.Image:
    """The photograph's grain on the old texture's tone.

    Y is moved to the reference mean (plus `lift`, a tint step used where contrast needed
    it) and its spread to `gain` times the reference spread. Cb and Cr are moved to the
    reference means, and keep `chroma_gain` of the reference spread, so a brown photograph
    stays brown in the old texture's brown."""
    a, r = ycc(im), ycc(ref)
    out = np.empty_like(a)
    for c in range(3):
        m, s = a[..., c].mean(), a[..., c].std() or 1.0
        rm, rs = r[..., c].mean(), r[..., c].std()
        g = gain if c == 0 else chroma_gain
        out[..., c] = (a[..., c] - m) / s * rs * g + rm + (lift if c == 0 else 0.0)
    return from_ycc(out)


def grey_match(im: Image.Image, ref: Image.Image, gain: float) -> Image.Image:
    """For the multiply role: grain only, no colour, on the old grey's mean."""
    y, r = ycc(im)[..., 0], ycc(ref)[..., 0]
    y = (y - y.mean()) / (y.std() or 1.0) * r.std() * gain + r.mean()
    g = np.clip(y, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([g, g, g]), "RGB")


def save_jpg(im: Image.Image, name: str, quality: int) -> None:
    path = OUT / name
    im.save(path, "JPEG", quality=quality, optimize=True, progressive=True, subsampling=0)
    print(f"{name:22s} {im.size[0]}x{im.size[1]} {path.stat().st_size:>8d} bytes")


def surfaces(src: Path) -> None:
    desk(src)

    # The card leather: the top bar, the desk, the framed cards, the Talk tray and the
    # Equipment head. Tiles, so it stays square and whole.
    # Tinted below the old tone (lift): the desk's and the top bar's dim labels (#93866e)
    # measured 3.68:1 and 3.73:1 against the brightest 2% of the old leather under its lit
    # top edge, and 4.42 and 4.49 at a lift of -14. At -19 they hold 4.66 and 4.75. The
    # light gradient is the page's styling and stays; the leather under it was darkened.
    im = load(src / "brown_leather_albedo_2k.jpg").resize((1024, 1024), Image.LANCZOS)
    save_jpg(match(im, load(OLD / "card-leather.jpg"), gain=CARD_GAIN, chroma_gain=1.4,
                   lift=CARD_LIFT), "card-leather.jpg", 82)

    # The sides' tooled leather, which the CSS multiplies with the app's brown. The
    # photograph has a seam down its middle, so the right-hand half is taken: tileable top
    # to bottom, and wider than any side panel, so it never repeats across.
    im = load(src / "fabric_leather_02_diff_2k.jpg")
    w, h = im.size
    im = im.crop((int(w * 0.53), 0, int(w * 0.53) + 900, h)).resize((600, 1200), Image.LANCZOS)
    save_jpg(grey_match(im, load(OLD / "leather-tile.jpg"), gain=1.9), "side-leather.jpg", 78)

    # The book's page. It sat on the card leather before; now it is paper, taken to the
    # same dark tone, which is what the story's contrast was measured against.
    im = load(src / "Paper006_2K-JPG_Color.jpg").resize((1024, 1024), Image.LANCZOS)
    save_jpg(match(im, load(OLD / "card-leather.jpg"), gain=3.2, chroma_gain=1.3),
             "page-paper.jpg", 74)

    # Brass grain for the gilt: the frames' and coins' gold stays the CSS gradient (its
    # light is the page's lamp), and this is laid over it in soft-light, grey around the
    # middle so it adds the metal's surface and not a colour.
    col = load(src / "Metal048C_1K-JPG_Color.jpg", "L")
    rough = load(src / "Metal048C_1K-JPG_Roughness.jpg", "L")
    a = 0.55 * np.asarray(col, float) + 0.45 * (255 - np.asarray(rough, float))
    a = (a - a.mean()) / (a.std() or 1.0) * 26 + 128
    g = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((512, 512), Image.LANCZOS)
    save_jpg(g.convert("RGB"), "brass-grain.jpg", 84)


def desk(src: Path) -> None:
    """The room: what the book and the panels lie on, where the old grimoire leather was.

    A worn plank table, lit by the page's lamp. The owner, on the first two tries (a
    black scarred leather, then an aged hide, both toned to the old texture): "the
    background texture is notably worse, I was hoping for something interesting, give it
    some depth but keep it dark". Both had been flattened to the old mean and spread, and
    a flat photograph at that tone is wallpaper. Depth here comes from the table's own
    normal map, lit by LIGHT, so every plank edge, crack and nail hole is lit on the same
    side as the page's bevels, and from its ambient occlusion, which darkens the seams.
    The vignette and the warm pool are CSS layers over it (mock.css, body), so they cost
    no bytes and stay exactly centred at every width.

    Cover-fitted and never repeated, so it has no seam to show: a 16:9 piece of the 2K
    square, away from the bottom row (a darker board that read as a stripe)."""
    alb = load(src / "wood_table_large_diff_2k.jpg")
    nor = np.asarray(load(src / "wood_table_large_nor_gl_2k.jpg"), float) / 255 * 2 - 1
    ao = np.asarray(load(src / "wood_table_large_ao_2k.jpg", "L"), float) / 255
    w, h = alb.size
    top = (h - 1152) // 2 - 180
    box = (0, top, 2048, top + 1152)
    a = ycc(alb.crop(box))
    nor = nor[box[1]:box[3], box[0]:box[2]]
    ao = ao[box[1]:box[3], box[0]:box[2]]
    # Dark, but a warm dark wood, not the old near-black: Y to a mean of 24 with the
    # grain at 0.85 of its spread; the colour kept at half its distance from grey.
    y = a[..., 0]
    a[..., 0] = (y - y.mean()) * (24 / y.mean()) * 0.85 + 24
    a[..., 1:] = 128 + (a[..., 1:] - 128) * 0.5
    base = np.asarray(from_ycc(a), float) / 255
    # OpenGL normal maps point green up the image; the page's axes run down. The relief is
    # exaggerated 2.2 times, or the planks read flat at the size they are drawn.
    n = np.dstack([nor[..., 0] * 2.2, -nor[..., 1] * 2.2, nor[..., 2]])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    lit = np.clip(n @ LIGHT, 0, None) / LIGHT[2]
    out = base * (0.35 + 0.65 * lit)[..., None] * (ao ** 1.4)[..., None]
    img = Image.fromarray(np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8))
    save_jpg(img, "room-desk.jpg", 80)


def blur(a: np.ndarray, r: float) -> np.ndarray:
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), float) / 255


def tiled(tex: Image.Image, size: tuple[int, int], scale: float, offset: int) -> np.ndarray:
    """The texture repeated over an ornament's canvas, at `scale` texture pixels per
    ornament pixel, so the metal's grain survives the ornament being drawn at 96px."""
    t = tex.resize((int(tex.width * scale), int(tex.height * scale)), Image.LANCZOS)
    t = np.asarray(t, float) / 255
    w, h = size
    ys = (np.arange(h)[:, None] + offset) % t.shape[0]
    xs = (np.arange(w)[None, :] + offset * 2) % t.shape[1]
    return t[ys, xs]


def ornaments(src: Path) -> None:
    bronze = load(src / "Metal047B_1K-JPG_Color.jpg")
    brass = load(src / "Metal048C_1K-JPG_Color.jpg")
    brass_rough = load(src / "Metal048C_1K-JPG_Roughness.jpg", "L")
    names = ["clasp-tl", "clasp-tr", "clasp-bl", "clasp-br",
             "boss-top", "boss-bottom", "boss-left", "boss-right"]
    for i, name in enumerate(names):
        old = Image.open(OLD / f"{name}.png").convert("RGBA")
        a = np.asarray(old, float) / 255
        rgb, alpha = a[..., :3], a[..., 3]
        lum = rgb @ np.array([0.299, 0.587, 0.114])
        mx, mn = rgb.max(-1), rgb.min(-1)
        sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
        # Which parts were the gold filigree and which the dark iron plate: the filigree is
        # the warm, saturated, lighter metal. A soft weight, so edges blend.
        gold = np.clip((sat - 0.22) / 0.2, 0, 1) * np.clip((lum - 0.18) / 0.2, 0, 1)
        gold = blur(gold, 0.8)

        # Relief from the old render's own values: a raised line is lighter than the
        # recess beside it. Normals from its slope, lit by the page's lamp; a flat face
        # takes exactly its old brightness, a face turned to the lamp more, away less.
        h = blur(lum * (alpha > 0.02), 1.6)
        gy, gx = np.gradient(h)
        # Measured by eye at 9: every raised edge glittered like foil at the drawn size.
        k = 5.0
        n = np.dstack([-gx * k, -gy * k, np.ones_like(h)])
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        lit = np.clip(n @ LIGHT, 0, 1) / LIGHT[2]
        cavity = 0.38 + 0.95 * np.clip((lum - 0.05) / 0.6, 0, 1)

        size = old.size
        # Darker than the gilt, as the old iron plate was, so the filigree stands off it.
        plate = tiled(bronze, size, 0.9, 37 * i) * np.array([0.64, 0.60, 0.56])
        gild = tiled(brass, size, 0.9, 53 * i)
        grain = tiled(brass_rough.convert("RGB"), size, 0.9, 53 * i)[..., :1]
        # The photographed brass is a pale lemon; the old filigree's gold is deeper and
        # warmer (its mean is about #a8844a against the brass's #efd9a0). Tinted to it, or
        # the filigree read as silver on the first bake.
        gild = gild * (1.05 - 0.35 * grain) * np.array([1.0, 0.80, 0.50])
        albedo = plate * (1 - gold[..., None]) + gild * gold[..., None]
        spec = np.clip(n @ (LIGHT + np.array([0, 0, 1])) / np.linalg.norm(LIGHT + [0, 0, 1]),
                       0, 1) ** 30 * 0.22 * (0.3 + gold)
        out = albedo * (cavity * lit)[..., None] * 0.80 + spec[..., None] * np.array([1, .9, .7])
        rgba = np.dstack([np.clip(out, 0, 1), alpha])
        img = Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA")
        path = OUT / f"{name}.png"
        img.save(path, optimize=True)
        assert img.size == old.size
        print(f"{name + '.png':22s} {size[0]}x{size[1]} {path.stat().st_size:>8d} bytes")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", required=True, type=Path, help="folder of the CC0 sources")
    args = ap.parse_args()
    surfaces(args.src)
    ornaments(args.src)
