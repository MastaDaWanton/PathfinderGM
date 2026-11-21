# Board texture: how stylised tabletops get grain cheaply (2026-11-21)

The owner, 2026-11-21: "the colors on the 3d tabletop maps are too smooth and need a bit of
texture." Owner instruction 2026-09-28: keep the existing colours. This note is the search
done before designing, and what was taken from it.

## The boards

Only one 3D tabletop exists: `play/static/js/places-board.js` (Three.js r170), reached from
Map, then Places. It draws five boards: Town, Region (12-mile hexes), Continent, World and
Site. The battle board's 3D view (`scene3d.js`) is an isometric SVG that already carries
stone, plank and flagstone patterns, so it was left alone.

What was flat: the painted miniatures and the grey primer (`mat()`/`PRIMER`, single-colour
`MeshStandardMaterial`), the Kenney hex tiles and buildings (one shared palette texture,
`colormap.png`, so every face is one flat colour), and the site rooms. The table (canvas
wood), the paper (photo of chart paper) and the leather already had texture.

## What the traditions do

- **Per-face vertex-colour jitter.** The common low-poly answer: forum posts show per-triangle
  colour randomisation (a Unity thread, about plus or minus 20 percent) and normal-seeded
  vertex colour shifts (an Unreal thread)
  ([Unreal: flat shading tips](https://forums.unrealengine.com/t/flat-shading-tips-techniques/10147),
  [Unity: low poly world](https://discussions.unity.com/t/low-poly-world/565228)). It reads as
  facets, not grain, and Kenney's tiles share one palette texture, so it would mean rewriting
  their geometry. Not taken.
- **World-space or triplanar projection.** Sample a texture by world position on the three
  axis planes and blend by the surface normal, so no UVs are needed and adjacent objects line
  up. In Three.js the forum answers use TSL node materials
  ([aligning textures across objects](https://discourse.threejs.org/t/how-to-make-textures-align-across-adjacent-objects/66193),
  [triplanar and lighting](https://discourse.threejs.org/t/triplanar-and-lighting/35241); the
  [Babylon forum](https://forum.babylonjs.com/t/procedural-noise-texture-coordinates-from-world-position/61734)
  does the same with its NodeMaterial). The other route is patching a built-in material with
  `onBeforeCompile`, as [three.js issue 18992](https://www.github.com/mrdoob/three.js/issues/18992)
  does for world-space UVs; its workaround hooks the literal `#include <...>` lines, because
  the hook sees the shader before the includes are expanded. The board uses the classic
  WebGL renderer, not the node system, so the patch route was taken, hooking
  `#include <project_vertex>` and `#include <color_fragment>` (checked to compile in r170 in
  the running app).
- **Noise in the shader versus a noise texture.** Textureless GLSL noise runs on WebGL 1 /
  GLES 2 with performance "on par with previously presented GPU implementations"
  ([McEwan, Sheets, Gustavson and Richardson, 2012](https://arxiv.org/pdf/1204.1461)); a 2019
  study found hash-based noise roughly on par with texture-based Perlin noise, trading ALU
  for memory bandwidth ([arXiv 1903.12270](https://arxiv.org/pdf/1903.12270); authors not
  confirmed from the fetched page). So neither wins on raw speed in the literature. Mobile
  developers on the Unity forum say a texture lookup is the safer default on weak GPUs,
  without measurements
  ([Unity forum](https://discussions.unity.com/t/comparing-performance-of-textures-vs-procedural-shaders-on-mobile-gpu/662156)).
  What decides it here: a texture gets mipmaps for free, so distant surfaces average out
  instead of shimmering, which shader noise cannot do without extra work, and three fetches
  of a 16 KB tile are less code than three octaves of hash noise. Taken: a small texture.
- **Kenney practice.** Kenney's kits colour everything from one shared palette texture; the
  usual way to change their look is to recolour that atlas (that the kits share one palette is
  read from our own `.glb` files, whose only material is `colormap`)
  ([Atlas Recolor, Godot asset library](https://godotengine.org/asset-library/asset/4780)).
  We do not want to recolour, so the grain is laid over whatever colour the palette gives.
- **Named games.** I looked for how Bad North, A Short Hike and similar dioramas texture flat
  colours and found no primary source; a forum comment says A Short Hike uses a post effect,
  which I could not confirm. Nothing here relies on those games.

## What was built

One 128x128 tiling value-noise tile (five octaves), generated once in code, cached and
reused by every board (no fetch: the packaged app is offline). A `grained()` patch on the
board's painted, primer and Kenney materials, and on the translucent nation plates, samples
it in world space on the three planes, weighted by the face's own normal (taken from screen
derivatives, so it works for flat- and smooth-shaded meshes and instanced hexes alike), one
tile per 4 table units, and multiplies the colour by about seven percent at one sigma.
Colours keep their own hue. The plates were added after the first look: they are most of what
the Region and Continent show, and a flat wash over grained tiles still read smooth. One tile
per 7 units was tried first and left a miniature inside a single blotch. Fog clouds, the haze
over seen-but-unsearched hexes, the gilt reach rings, names and highlights are untouched, so
knowledge and selection read exactly as before. (The white faceted "peaks" on the Continent
are those fog clouds over unknown land, not mountains; mountains and hills are Kenney's
stone-hill tiles and the cave and keep miniatures, and those are grained.)

The owner then narrowed it the same day: the grain is for the Continent and the Region (the
12-mile hex map, which is the `nation` level in the code). The materials are shared across
levels (a Kenney house is both a town miniature and a hex village), so one shared uniform,
set when each board is built, switches the grain on for those two levels and off for World,
Town and Site, which skip the fetches behind a uniform branch and look exactly as before.

Cost: three texture fetches of a 16 KB single-channel tile per pixel of a grained surface,
one shared program variant per material type. Frame times are in the lane report.

## Second pass

A separate critic pass fetched every link (none dead) and checked each claim against it. It
caught: the Unreal thread jitters by normal, not per face; the three.js forum threads use
node materials, not `onBeforeCompile`; the 2019 hash-noise paper was cited the wrong way round
(on par with texture noise, not slower) and with the wrong authors; the 2012 paper compares
with earlier GPU noise, not specifically texture-based noise. All five are corrected above.
