"""Make the mock's textures from CC0 source photographs and the owner's own two images.

Resize, crop, tint, and re-light: the ornaments are lit here by the page's lamp from the
old ornaments' own relief; the room is the owner's boiler room with its highlights rolled
off; the device is cut out of the owner's photograph of it, in layers. Nothing is
generated or painted. Downloads nothing: the CC0 sources are the files named in
CREDITS.md, fetched by hand from Poly Haven and ambientCG into one folder and passed as
--src, and the owner's two images (18.webp, 19.jpg) are passed as --owner:

    python docs/mock/table-layout/textures/prepare.py --src path/to/sources --owner path/to/owner

Run from the repository root. It reads the app's own images in play/static/img (never
writes there) for two things only: the old textures' tone, which each new one is matched
to, and the ornaments' silhouettes, which are kept pixel for pixel.

Why match tone rather than use the photographs as they come: the owner asked for better
material, not a new palette ("keep the leather and bronze look"). The leathers and the
page are moved to the old texture's mean colour in YCbCr, and their grain is scaled to a
chosen multiple of the old texture's spread. The mean keeps the page's colour and its text
contrast; the gain is where the quality comes from (the old card leather varied by 4
levels of 255, a smear). The owner's two images are the exception: room() and device()
say why.

Why the ornaments are re-lit: the old corner pieces and bosses were made in each
orientation by mirroring one render (table.html: "CSS cannot mirror a background image, so
the four corner orientations and the flipped boss are baked as files"), so whatever light
the render had is mirrored with it, and at least two corners are lit from the wrong side.
Baked here, every piece is lit by the page's one lamp, scene3d.js's LIGHT
(-0.42, -0.78, 0.47): high, left, in front.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

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


def chart(src: Path) -> None:
    """The parchment the place chart is drawn on (Map mode, Places): the same Paper 006 as
    the book's page, but left light, as a sheet of paper laid on the desk under the lamp
    and inked on, the way the other mock (mock/table-free) draws the chart the owner
    picked. Its mean is a warm parchment, #ccbd9c; its grain is the photograph's own at
    2.2 times its spread, enough to read as paper at the drawn size and not so much that
    the ink's thin lines break up. The ink labels on it measure 5-9:1 (README)."""
    im = load(src / "Paper006_2K-JPG_Color.jpg").resize((1024, 1024), Image.LANCZOS)
    a = ycc(im)
    target = ycc(Image.new("RGB", (1, 1), (0xcc, 0xbd, 0x9c)))[0, 0]
    out = np.empty_like(a)
    for c, gain in ((0, 2.2), (1, 0.8), (2, 0.8)):
        out[..., c] = (a[..., c] - a[..., c].mean()) * gain + target[c]
    save_jpg(from_ycc(out), "chart-paper.jpg", 80)


def room(owner: Path) -> None:
    """The room: the owner's own boiler room (18.webp), the page's backdrop.

    Replaced the lit plank desk of the pass before on the owner's word ("take this image
    and make it the background"). Only resized and re-encoded here, never re-lit: it is a
    picture with its own lamps, and the page dims and vignettes it in CSS (mock.css, body)
    so that it sits behind the book and the panels rather than competing with them. Kept
    square and whole, because a wide window crops its top and bottom and a phone its
    sides; `background-position` chooses what stays (the door and the lamps)."""
    im = load(owner / "18.webp").resize((1800, 1800), Image.LANCZOS)
    # A highlight roll-off, the one tint: above a knee the picture's brightness is
    # compressed, so its lamps and white gauge faces glow instead of blowing through the
    # page's dimming. Measured on the Equipment page's open ground at 1440x900: the dim
    # labels (#93866e) over the white gauge held 3.53:1 at the brightest 2% under the
    # first dimming, and 3.93 even at a deeper one, which had already sunk the room.
    a = np.asarray(im, float) / 255
    y = a @ np.array([0.2126, 0.7152, 0.0722])
    knee = 0.22
    y2 = np.where(y < knee, y, knee + (1 - knee) * (1 - np.exp(-(y - knee) / 0.20)) * 0.25)
    a = a * (y2 / np.maximum(y, 1e-4))[..., None]
    im = Image.fromarray(np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8))
    save_jpg(im, "room-boiler.jpg", 76)


# The device (the owner's 19.jpg), in the photograph's own pixels. The chamber is the
# opening in the frame where the photo shows its movement: a top arch and a lower U where
# the scrolled panel cuts into it, measured off the photograph on a 2px grid. The lamp sits
# in the round socket of the top plate and the lever pivots on the knob beside it.
DEV_CROP = (514, 39, 782, 812)        # the cut-out's box, 2px clear of the metal
DEV_SCALE = 0.45                      # 268x773 -> 121x348: twice its largest drawn size
CH_X0, CH_X1 = 562, 748               # the opening's inner sides, 2px inside the frame lip
CH_TOP, CH_ARCH = 205, 23             # the top arch: 205 at the sides, 182 at the middle
CH_BOT, CH_U = 468, 58                # the lower U: 468 at the sides, 526 at the middle
LAMP = (600, 97, 14)                  # socket centre and radius
KNOB = (697, 92, 12)                  # the lever's pivot
FOOT = (665, 806)                     # the middle of the foot's underside: smoke comes out here
# Two meshing gears in the opening, the smaller above, as the photograph's own movement
# sits: 10 and 16 teeth on one module, so the centre distance is m(10+16)/2 and the small
# gear turns 16/10 = 1.6 times for each turn of the large one, the other way. Tried first
# at 8 and 12 teeth on a larger module: at the drawn size they read as toy sprockets.
GEAR_M = 8.5
GEAR_SMALL = (655, 272, 10)
GEAR_LARGE = (655, 272 + GEAR_M * (10 + 16) / 2, 16)
# The tab on the top plate's left edge (the owner, 2026-09-29, circling it: "add a glowing
# bit that pops out green ... it should only pop out when its green"). In the photograph it
# is a plate standing 16px proud of the body, x 518-533, y 61-149, with a dark crevice
# where it goes in (x 530-534), which stays with the body as the slot it slides into.
# The piece is cut at x < 530 and lengthened (its face, x 524-528, stretched) so it can
# stand TAB_EXTRA further out than the photograph shows and still reach into the slot,
# overshoot included; retracted, its end is inside the slot and none of it shows.
TAB_BOX = (516, 57, 530, 152)          # the piece as photographed, 2px of margin each side
TAB_EXTRA = 16                         # how much further out than the photograph, out
TAB_FACE = (524, 528)                  # the columns stretched to lengthen it
TAB_LEN = 38                           # its length after, into the body by 8px when out
TAB_TRAVEL = 29                        # out -> in: its visible end (x 518 + 29 - 16) at 531


def chamber_polygon(n: int = 48) -> list[tuple[float, float]]:
    pts = []
    for i in range(n + 1):
        t = i / n
        x = CH_X0 + (CH_X1 - CH_X0) * t
        pts.append((x, CH_TOP - CH_ARCH * np.sin(np.pi * t)))
    for i in range(n, -1, -1):
        t = i / n
        x = CH_X0 + (CH_X1 - CH_X0) * t
        pts.append((x, CH_BOT + CH_U * np.sin(np.pi * t)))
    return pts


def device(owner: Path) -> None:
    """The brass device cut out of its grey studio backdrop, in four layers.

    Isolation, with PIL and numpy only (no model is downloaded):
    1. The backdrop is modelled, not guessed: a smooth cubic surface in x and y is fitted,
       per channel, to every pixel well clear of the device (x < 470 or x > 830). It fits
       the studio's light fall-off to a mean residual of 2.5 levels.
    2. Each pixel is scored by its distance from that surface and by its colour: brass is
       yellow and the backdrop grey, so chroma above the backdrop's own counts 1.6 times.
    3. Hand fix: below the foot's top edge (y > 776) the foot's cast shadow on the floor is
       dark enough to pass the distance test but it is grey, so there only colour counts.
    4. The device's own component is kept (flood-filled from a point on the lower panel)
       and its holes filled, so the dark of the movement is not mistaken for backdrop.
    5. The edge is eroded 1px (the grey fringe) and feathered 0.9px, and in the partly
       covered edge pixels the backdrop's colour is taken back out, so no grey halo is left
       on a dark page.

    Layers, all in the same box so they stack exactly:
    - device-chamber.png: the opening's back. The photograph's own movement, kept at a
      third of its brightness so the new gears read in front of it.
    - device-lip.png: the shadow the frame's lip throws into the opening, lit by LIGHT
      (down and right), laid over the gears.
    - device-frame.png: the frame with the opening cut out, lit by LIGHT (a gentle fall
      from the upper left to the lower right; the photograph was lit nearly flat), and
      with the tab taken off it.
    - device-tab.png: the tab on the top plate's left edge, its own piece so that it can
      slide in and out under the frame (TAB_BOX above says how it is cut and lengthened).
    - device-geometry.js: the numbers the page draws the gears, lamp, lever and smoke at.
    """
    im = load(owner / "19.jpg")
    a = np.asarray(im, float)
    H, W, _ = a.shape
    yy, xx = np.mgrid[0:H, 0:W]
    clear = (xx < 470) | (xx > 830)
    u, v = xx.ravel() / W, yy.ravel() / H
    X = np.stack([np.ones(H * W), u, v, u * u, v * v, u * v, v ** 3, u ** 3], 1)
    m = clear.ravel()
    bg = np.empty_like(a)
    for c in range(3):
        coef, *_ = np.linalg.lstsq(X[m], a[..., c].ravel()[m], rcond=None)
        bg[..., c] = (X @ coef).reshape(H, W)
    d = np.linalg.norm(a - bg, axis=-1)
    chroma = a.max(-1) - a.min(-1) - (bg.max(-1) - bg.min(-1))
    hard = np.maximum(d * 0.35, chroma * 1.6) > 26
    hard = np.where(yy > 776, chroma * 1.6 > 30, hard)
    # A numpy-backed image is read-only to floodfill, which then silently does nothing.
    mk = Image.fromarray((hard * 255).astype(np.uint8)).copy()
    seed = next((648, y) for y in range(560, 700) if hard[y, 648])
    ImageDraw.floodfill(mk, seed, 128)
    comp = Image.fromarray(((np.asarray(mk) == 128) * 255).astype(np.uint8)).copy()
    ImageDraw.floodfill(comp, (0, 0), 64)
    solid = np.asarray(comp) != 64
    er = Image.fromarray((solid * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3))
    alpha = np.asarray(er.filter(ImageFilter.GaussianBlur(0.9)), float) / 255
    al = np.clip(alpha, 1e-3, 1)[..., None]
    fg = np.where(alpha[..., None] > 0.98, a, np.clip((a - (1 - al) * bg) / al, 0, 255))

    # The page's lamp on the frame: brighter to the upper left, darker to the lower right.
    x0, y0, x1, y1 = DEV_CROP
    t = ((xx - x0) / (x1 - x0) * -LIGHT[0] + (yy - y0) / (y1 - y0) * -LIGHT[1])
    t = t / (-LIGHT[0] - LIGHT[1])
    fg = fg * (1.12 - 0.26 * t)[..., None]

    hole = Image.new("L", (W, H), 0)
    ImageDraw.Draw(hole).polygon(chamber_polygon(), fill=255)
    hole = np.asarray(hole.filter(ImageFilter.GaussianBlur(0.8)), float) / 255
    # The lip's shadow: inside the opening, where the point up-left of it (against the
    # light, 14px deep) is still frame.
    dx, dy = int(round(-LIGHT[0] / LIGHT[2] * 7)), int(round(-LIGHT[1] / LIGHT[2] * 7))
    shifted = np.zeros_like(hole)
    shifted[dy:, dx:] = hole[:-dy or None, :-dx or None]
    lip = np.clip(hole - shifted, 0, 1)
    lip = blur(lip, 6) * hole

    def save(rgba: np.ndarray, name: str) -> None:
        img = Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA").crop(DEV_CROP)
        img = img.resize((round(img.width * DEV_SCALE), round(img.height * DEV_SCALE)),
                         Image.LANCZOS)
        path = OUT / name
        img.save(path, optimize=True)
        print(f"{name:22s} {img.size[0]}x{img.size[1]} {path.stat().st_size:>8d} bytes")

    # The tab comes off the frame as its own piece, so it moves as brass and not as paint.
    tx0, ty0, tx1, ty1 = TAB_BOX
    tab_cut = np.zeros((H, W), bool)
    tab_cut[ty0:ty1, :tx1] = True
    piece = np.dstack([fg, alpha * 255])[ty0:ty1, tx0:tx1]
    f0, f1 = TAB_FACE[0] - tx0, TAB_FACE[1] - tx0
    face = Image.fromarray(np.clip(piece[:, f0:f1], 0, 255).astype(np.uint8), "RGBA")
    face = np.asarray(face.resize((TAB_LEN - f0 - (tx1 - tx0 - f1 + 1), ty1 - ty0),
                                  Image.LANCZOS), float)
    piece = np.concatenate([piece[:, :f0], face, piece[:, f1 - 1:]], 1)
    assert piece.shape[1] == TAB_LEN, piece.shape
    tab = Image.fromarray(np.clip(piece, 0, 255).astype(np.uint8), "RGBA")
    tab = tab.resize((round(TAB_LEN * DEV_SCALE), round((ty1 - ty0) * DEV_SCALE)), Image.LANCZOS)
    tab.save(OUT / "device-tab.png", optimize=True)
    print(f"{'device-tab.png':22s} {tab.size[0]}x{tab.size[1]} "
          f"{(OUT / 'device-tab.png').stat().st_size:>8d} bytes")

    save(np.dstack([fg, alpha * (1 - hole) * ~tab_cut * 255]), "device-frame.png")
    save(np.dstack([fg * 0.34, alpha * hole * 255]), "device-chamber.png")
    save(np.dstack([np.zeros_like(fg), lip * 0.75 * 255]), "device-lip.png")

    geo = {
        "box": [DEV_CROP[2] - DEV_CROP[0], DEV_CROP[3] - DEV_CROP[1]],
        "origin": DEV_CROP[:2],
        "lamp": LAMP, "knob": KNOB, "foot": FOOT, "m": GEAR_M,
        "gears": [GEAR_SMALL, GEAR_LARGE],
        # Out: the piece's box [x, y, length, height]; in: moved TAB_TRAVEL to the right.
        "tab": [tx0 - TAB_EXTRA, ty0, TAB_LEN, ty1 - ty0], "tabTravel": TAB_TRAVEL,
        "light": [round(float(c), 4) for c in LIGHT],
    }
    js = ("// Written by textures/prepare.py: the device's geometry, in the owner's\n"
          "// photograph's pixels (19.jpg). Do not edit by hand.\n"
          "window.DEVICE_GEOMETRY = " + json.dumps(geo) + ";\n")
    (OUT / "device-geometry.js").write_text(js, encoding="utf-8")
    print("device-geometry.js", len(js), "bytes")


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
    ap.add_argument("--owner", required=True, type=Path,
                    help="folder holding the owner's own 18.webp and 19.jpg")
    args = ap.parse_args()
    surfaces(args.src)
    chart(args.src)
    ornaments(args.src)
    room(args.owner)
    device(args.owner)
