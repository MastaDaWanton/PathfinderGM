# Texture credits

Every texture here is made by `prepare.py`, from CC0 photographs (public-domain
dedication: free to use, modify and redistribute, attribution not required but given) or
from the owner's own two images. Nothing here is used by the app: the mock only, under
`docs/`, which is not bundled. `play/static/img` is read by the script (for the old tones
and the ornaments' silhouettes) and never written.

## Sources

### The owner's own images

The owner's own images, supplied 2026-09-29; cleared by the owner for publication in this
public repository. Neither original is in the repository; only what `prepare.py` makes
from them.

| Source file | What it is | Size as supplied | Made into |
|---|---|---|---|
| `18.webp` | a boiler room: a door, lamps, gauges and pipes | 2000x2000, 319,158 B | `room-boiler.jpg` |
| `19.jpg` | a brass mechanism photographed on a grey studio backdrop | 1285x832, 452,992 B | `device-frame.png`, `device-chamber.png`, `device-lip.png`, `device-tab.png`, `device-geometry.js` |

### CC0 photographs

Fetched by hand, 2026-09-29. Poly Haven files are the direct JPG maps; ambientCG serves
only zips, so each zip was opened, the named JPGs taken out, and the zip deleted. Nothing
executable was kept or run.

| Source file | From | Author | Licence | Size as fetched |
|---|---|---|---|---|
| `brown_leather_albedo_2k.jpg` | [Poly Haven: Brown Leather](https://polyhaven.com/a/brown_leather), [file](https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/brown_leather/brown_leather_albedo_2k.jpg) | Rob Tuytel | [CC0](https://polyhaven.com/license) | 2048x2048, 2,137,518 B |
| `fabric_leather_02_diff_2k.jpg` | [Poly Haven: Fabric Leather 02](https://polyhaven.com/a/fabric_leather_02), [file](https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/fabric_leather_02/fabric_leather_02_diff_2k.jpg) | Rob Tuytel | CC0 | 2048x2048, 2,938,354 B |
| `Paper006_2K-JPG_Color.jpg` | [ambientCG: Paper 006](https://ambientcg.com/view?id=Paper006), from `Paper006_2K-JPG.zip` | ambientCG | [CC0](https://docs.ambientcg.com/license/) | 2048x2048, 5,314,220 B |
| `Metal048C_1K-JPG_Color.jpg`, `_Roughness.jpg` | [ambientCG: Metal 048 C](https://ambientcg.com/view?id=Metal048C), from `Metal048C_1K-JPG.zip` | ambientCG | CC0 | 1024x1024, 871,864 B and 539,353 B |
| `Metal047B_1K-JPG_Color.jpg` | [ambientCG: Metal 047 B](https://ambientcg.com/view?id=Metal047B), from `Metal047B_1K-JPG.zip` | ambientCG | CC0 | 1024x1024, 1,886,277 B |

Fetched, used, and since replaced: Poly Haven's Wood Table Large by Dimitrios Savva (CC0;
`wood_table_large_diff_2k.jpg`, `_nor_gl_2k.jpg`, `_ao_2k.jpg`), which made the lit plank
desk that was the room's backdrop in commit cf63c7e (`room-desk.jpg`, 2048x1152, 233,208
B). The owner's boiler room replaced it; the file is removed and `prepare.py` no longer
reads those sources. Also fetched and never used: ambientCG Leather032 (CC0), the first
try at the room, dropped because its fine scars read as a cobweb over the open ground.
Nothing of either is in the repository now.

## What was made, and what each replaces

Sizes are as committed. 2,425,393 bytes in all, eighteen files.

| File | Made from | Dimensions | Bytes | Replaces (was `play/static/img/...`) |
|---|---|---|---|---|
| `room-boiler.jpg` | the owner's `18.webp`, resized, its highlights rolled off above a knee (its lamps and gauge faces glow instead of blowing through the page's dimming) | 1800x1800 | 358,134 | `grimoire-leather.jpg`, the page's backdrop |
| `device-frame.png` | the owner's `19.jpg`: the device cut from its backdrop (a fitted backdrop surface, a colour test, a flood fill, a 1px erosion, a 0.9px feather, the backdrop's colour taken back out of the edge), lit by the page's lamp, the opening and the tab removed | 121x348 | 65,336 | nothing: new |
| `device-chamber.png` | the same cut, only the opening, at a third of its brightness | 121x348 | 22,141 | nothing: new |
| `device-lip.png` | the shadow the opening's lip throws inward, from the page's lamp | 121x348 | 1,655 | nothing: new |
| `device-tab.png` | the tab on the top plate's left edge, cut as its own piece and lengthened along its face so it can stand further out | 17x43 | 1,625 | nothing: new |
| `device-geometry.js` | the device's measured points (lamp, lever pivot, foot, gear centres, tab) in the photograph's pixels | - | 398 | nothing: new |
| `card-leather.jpg` | Brown Leather, toned to the old card leather and one step darker for the dim labels' contrast | 1024x1024 | 186,546 | `card-leather.jpg`: the top bar, the desk, framed cards, the Talk tray, the Equipment head |
| `side-leather.jpg` | Fabric Leather 02, the seamless right half, as grey grain for the CSS's multiply | 600x1200 | 204,333 | `leather-tile.jpg`: the two sides, the Equipment figure, the one-column sheet |
| `page-paper.jpg` | Paper 006, toned to the old page's dark | 1024x1024 | 217,819 | `card-leather.jpg` where it was the book's page |
| `brass-grain.jpg` | Metal 048 C colour and roughness, as grey grain around the middle | 512x512 | 54,096 | nothing: laid over the gilt gradient (rings, gilt edges, coin rims) in soft-light |
| `clasp-tl.png`, `-tr`, `-bl`, `-br` | the old clasp's own alpha and relief; Metal 047 B for the plate, Metal 048 C for the gilt; lit by the page's lamp | 340x247 each | 141,579 / 140,931 / 140,750 / 141,966 | `clasp-*.png` (same size, same silhouette, so the same placement) |
| `boss-top.png`, `-bottom`, `-left`, `-right` | the old boss's own alpha and relief, the same metals and lamp | 380x249, 249x380 | 185,780 / 186,068 / 187,525 / 188,711 | `boss-*.png` (same size, same silhouette) |

Not replaced: `cursor-candle.png`, which is a drawn candlestick used as the pointer,
not a material; and the two Cinzel fonts. Both are still read from `play/static`.

## Reproducing

Put the CC0 source files above, under the names above, in one folder, and the owner's
`18.webp` and `19.jpg` in another (or the same), and run from the repository root:

```
python docs/mock/table-layout/textures/prepare.py --src path/to/cc0 --owner path/to/owner
```

Run twice on 2026-09-29 (after the tab was added), it wrote the same bytes both times for
all eighteen files; the twelve committed in the passes before (the leathers, paper, brass
grain, clasps and bosses) came out unchanged from their commits.
