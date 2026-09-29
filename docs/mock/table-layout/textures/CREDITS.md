# Texture credits

Every texture here is made by `prepare.py` from CC0 photographs (public-domain
dedication: free to use, modify and redistribute, attribution not required but given).
Nothing here is used by the app: the mock only, under `docs/`, which is not bundled.
`play/static/img` is read by the script (for the old tones and the ornaments'
silhouettes) and never written.

## Sources

Fetched by hand, 2026-09-29. Poly Haven files are the direct JPG maps; ambientCG serves
only zips, so each zip was opened, the named JPGs taken out, and the zip deleted. Nothing
executable was kept or run.

| Source file | From | Author | Licence | Size as fetched |
|---|---|---|---|---|
| `wood_table_large_diff_2k.jpg` | [Poly Haven: Wood Table Large](https://polyhaven.com/a/wood_table_large), [file](https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/wood_table_large/wood_table_large_diff_2k.jpg) | Dimitrios Savva | [CC0](https://polyhaven.com/license) | 2048x2048, 2,672,834 B |
| `wood_table_large_nor_gl_2k.jpg` | same asset, [file](https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/wood_table_large/wood_table_large_nor_gl_2k.jpg) | Dimitrios Savva | CC0 | 2048x2048, 3,049,711 B |
| `wood_table_large_ao_2k.jpg` | same asset, [file](https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/wood_table_large/wood_table_large_ao_2k.jpg) | Dimitrios Savva | CC0 | 2048x2048, 2,927,210 B |
| `brown_leather_albedo_2k.jpg` | [Poly Haven: Brown Leather](https://polyhaven.com/a/brown_leather), [file](https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/brown_leather/brown_leather_albedo_2k.jpg) | Rob Tuytel | CC0 | 2048x2048, 2,137,518 B |
| `fabric_leather_02_diff_2k.jpg` | [Poly Haven: Fabric Leather 02](https://polyhaven.com/a/fabric_leather_02), [file](https://dl.polyhaven.org/file/ph-assets/Textures/jpg/2k/fabric_leather_02/fabric_leather_02_diff_2k.jpg) | Rob Tuytel | CC0 | 2048x2048, 2,938,354 B |
| `Paper006_2K-JPG_Color.jpg` | [ambientCG: Paper 006](https://ambientcg.com/view?id=Paper006), from `Paper006_2K-JPG.zip` | ambientCG | [CC0](https://docs.ambientcg.com/license/) | 2048x2048, 5,314,220 B |
| `Metal048C_1K-JPG_Color.jpg`, `_Roughness.jpg` | [ambientCG: Metal 048 C](https://ambientcg.com/view?id=Metal048C), from `Metal048C_1K-JPG.zip` | ambientCG | CC0 | 1024x1024, 871,864 B and 539,353 B |
| `Metal047B_1K-JPG_Color.jpg` | [ambientCG: Metal 047 B](https://ambientcg.com/view?id=Metal047B), from `Metal047B_1K-JPG.zip` | ambientCG | CC0 | 1024x1024, 1,886,277 B |

Also fetched and not used: ambientCG Leather032 (CC0), the first try at the room's
backdrop, dropped because its fine scars read as a cobweb over the open ground (see
`prepare.py`, `desk()`). Nothing of it is in the repository.

## What was made, and what each replaces

Sizes are as committed. 2,209,312 bytes in all.

| File | Made from | Dimensions | Bytes | Replaces (was `play/static/img/...`) |
|---|---|---|---|---|
| `room-desk.jpg` | Wood Table Large: albedo toned dark, relief lit by the page's lamp from its normal map, seams darkened by its AO | 2048x1152 | 233,208 | `grimoire-leather.jpg`, the page's backdrop |
| `card-leather.jpg` | Brown Leather, toned to the old card leather and one step darker for the dim labels' contrast | 1024x1024 | 186,546 | `card-leather.jpg`: the top bar, the desk, framed cards, the Talk tray, the Equipment head |
| `side-leather.jpg` | Fabric Leather 02, the seamless right half, as grey grain for the CSS's multiply | 600x1200 | 204,333 | `leather-tile.jpg`: the two sides, the Equipment figure, the one-column sheet |
| `page-paper.jpg` | Paper 006, toned to the old page's dark | 1024x1024 | 217,819 | `card-leather.jpg` where it was the book's page |
| `brass-grain.jpg` | Metal 048 C colour and roughness, as grey grain around the middle | 512x512 | 54,096 | nothing: laid over the gilt gradient (rings, gilt edges, coin rims) in soft-light |
| `clasp-tl.png`, `-tr`, `-bl`, `-br` | the old clasp's own alpha and relief; Metal 047 B for the plate, Metal 048 C for the gilt; lit by the page's lamp | 340x247 each | 141,579 / 140,931 / 140,750 / 141,966 | `clasp-*.png` (same size, same silhouette, so the same placement) |
| `boss-top.png`, `-bottom`, `-left`, `-right` | the old boss's own alpha and relief, the same metals and lamp | 380x249, 249x380 | 185,780 / 186,068 / 187,525 / 188,711 | `boss-*.png` (same size, same silhouette) |

Not replaced: `cursor-candle.png`, which is a drawn candlestick used as the pointer,
not a material; and the two Cinzel fonts. Both are still read from `play/static`.

## Reproducing

Put the source files above, under the names above, in one folder and run from the
repository root:

```
python docs/mock/table-layout/textures/prepare.py --src path/to/that/folder
```

Run twice on 2026-09-29, it wrote the same bytes both times for all thirteen files.
