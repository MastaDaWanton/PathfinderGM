# Why the dice do not feel good

Research record, 2026-09-08, with what was built from it on 2026-09-09 at the end.
Three sweeps and an adversarial pass over them; the critic verified the load-bearing
claim and caught four errors, corrected in place.

## What we do today, measured

`play/static/js/dice3d.js`, 606 lines, hand-written, no library, no WebGL. Every solid
is built from its own vertex construction, which is the right call and not the problem.
The throw is `tumble()`:

| Stage | What happens |
|---|---|
| 0 to 600 ms | Seven random orientations, with `transition: none` between them |
| 600 ms to ~1.5 s | One transform transition, 0.85 s or 0.95 s, `cubic-bezier(.16,.9,.3,1)`, plus 720° of Y spin, into the landing pose |
| On landing | A class is added to the face |

Nothing else. No contact shadow, no squash, no bounce, no settle, no sound.

**The first 600 ms is the biggest single problem and it is not a matter of taste.**
With `transition: none`, those seven steps do not animate. The die teleports between
seven poses, 60 to 140 ms apart. It is a slideshow, not a tumble, and no amount of
polish elsewhere will fix a throw whose first two thirds have no motion in them.

## The thing we already get right

Our roller labels every face with a real value, finds the face carrying the server's
result, and lands on that one. When the value is not printed on the die it relabels a
face instead.

That is exactly what the traditions do, and the critic confirmed it in their source.
Dice So Nice runs its physics in a web worker, computes the whole trajectory up front
(`MAX_FRAMES = 1001`), and then calls `swapDiceFace` and `bakeSwapIntoQuaternionBuffer`
to multiply a corrective rotation into every frame of that buffer, so the face carrying
the decided value is the one that ends up on top. `byWulf/threejs-dice` reads which
face physics left pointing up with `getUpsideValue()` and then reassigns which number
sits on which face with `shiftUpperValue()`. Neither steers the physics toward a face.

So the architecture is not the flaw. We arrived at the industry technique
independently, and a rewrite would not change it.

## What the evidence says is missing, strongest first

**Sound, and it is not a nice-to-have.** The one quantitative study found
(arXiv:2208.06155, 5,000 annotated Steam comments from **15** games — the critic caught
the sweep saying 16, which is a different subset in the same paper) identifies three
features that make or break how an impact feels: hit stop, **sound coherence**, and
camera control. Its finding on sound is specifically about *sync*: a delay between
seeing the impact and hearing it "will lead to a sense of unnaturalness and ruins the
user experience." We have no sound at all. A die clack can be synthesised in Web Audio
with no shipped asset — a short filtered-noise burst with a fast exponential decay —
and the click on the roll button is itself the user gesture the autoplay policy wants,
so nothing special is needed to start the audio context.

**A real tumble instead of seven jump cuts.** See above.

**Contact and weight.** Squash and stretch on landing has usable published numbers: a
stretch ratio around 1.25 and a squash around 1.5, with `transform-origin: center
bottom` so the shape stays glued to the ground. A contact shadow that grows and darkens
as the die nears the surface is a well-attested pattern, though I could not find a
primary source giving concrete opacity and scale numbers for one.

**A settle.** A single `cubic-bezier()` mathematically cannot express a curve that
overshoots and returns more than once, so a real multi-bounce needs either explicit
keyframes or the newer `linear()` easing, which takes an arbitrary point list and is
what people use for bounce and spring curves now. A cheaper half-measure is one
overshoot at the end using `cubic-bezier(0.34, 1.56, 0.64, 1)`.

## The timing question, which cuts both ways

This is the one place the evidence genuinely conflicts, and it should not be resolved
by picking the half we like.

Against a long roll: Nielsen Norman Group's numbers are blunt and verified verbatim.
Simple feedback is about 100 ms, substantial changes 200 to 300 ms, "at 500ms,
animations start to feel like a real drag for users", the appropriate range is 100 to
400 ms, and "the more frequent the animation, the more subtle and shorter you'll want it
to be". Our roll is about 1.5 s and happens many times a session.

For a pause before the reveal: a Journal of Gambling Studies study measured genuine
anticipatory arousal in the seconds before a reward was revealed, during a roughly
two-second shake, and that arousal is what makes a reveal feel like something.

The honest reading is that these are about different things. NN/g is measuring
interface latency, where the animation is in the way of the task. A dice roll is the
task. But the frequency rule still bites, and the field evidence is one-sided: every
product whose dice are slow has a standing revolt about it, with at least eight
separate threads on one platform alone, and a browser extension built by the community
purely to skip one vendor's roll animation.

**So: shorten the baseline, and let importance change the flourish rather than the
duration.** A natural twenty earns more, not longer.

## What it would cost to go further

If we ever wanted real physics, vendoring three.js and cannon-es is 178 KiB plus 34 KiB
gzipped, both MIT, no build step, and WebGL is on by default in an Electron window. A
dedicated dice library is 11.4 MB unpacked, which is a whole 3D engine and not worth it
here. The closest existing project to ours, `roll-a-die`, is 108 KB with zero
production dependencies and is CSS-only, which the critic confirmed.

My reading is that we should not add the dependency. The measured defects above are all
fixable in the renderer we have, and none of them are physics.

Two traps if we stay in CSS. There is no depth buffer: browsers sort 3D-transformed
planes with Newell's algorithm, so faces must never intersect. And `overflow`,
`opacity` below 1, `filter`, `clip-path`, `mask-image` and `mix-blend-mode` all silently
force `transform-style: flat` on their subtree, which collapses the die. A drop-shadow
must go on a wrapper, never on the element holding the faces.

## What I would change, in order

1. Make the first 600 ms actually move. This alone is most of the complaint.
2. Add a synthesised clack, timed to the frame the die lands, not before or after.
3. Add a contact shadow and a squash on landing.
4. Add one settle bounce with `linear()`, or one overshoot if that is enough.
5. Bring the whole throw down to roughly 700 to 900 ms.
6. Scale flourish with stakes, never duration: a natural twenty gets more.
7. Honour `prefers-reduced-motion` by shortening to a quick reveal rather than
   removing the feedback, which is what the accessibility guidance actually asks for.

## Built 2026-09-09

The first three, plus two defects the bench turned up while verifying them.

| Change | State |
|---|---|
| The throw animates instead of jump-cutting | done, one Web Animations call |
| A synthesised clack at both contacts | done, no asset, scheduled on the audio clock |
| Contact shadow, a floor to cast it on, squash on landing | done |
| The winning number lands the right way up | done, and it never did before |
| A percentile roll draws both dice | done, and it never did before |

Measured on the bench afterwards: the throw settles in **780 ms** against about 1,500,
the die and its shadow animate in step for the same 780, and one throw schedules four
audio nodes — a filtered-noise transient and a body for each of the two contacts, with
the pitch jittered per throw. Under `prefers-reduced-motion` it settles in about 170 ms
with one quiet clack and still lands on the result.

Two things the bench found that nobody had reported. The winning number landed any way
up, because rotating a face normal onto the view axis leaves one degree of freedom and
nothing was using it — a d20 showing 14 landed with the 14 upside down. And a percentile
roll had only ever drawn one die: the stylesheet gives the second die `display: none`
and the code revealed it by clearing the *inline* style, which falls back to the rule.

`tools/dicebench/` is kept. Judging how a die feels needs it thrown a hundred times, and
doing that inside a campaign means a hundred real turns and a model call each.

## Two geometry bugs the table found next, 2026-09-09

Reported with a screenshot: "these die are splitting apart." Both predate all the work
above, and both were invisible until something measured them.

**The face normal was the direction of the face's centre.** `prepare` took each
normal as `norm(centre)`, which equals the plane's normal only when a face is
symmetric about it. That is true of every regular solid here and false of the d10,
whose kites run from a near apex to a far equator point, so all ten of its faces sat
tilted off their true planes and could not meet their neighbours. Sampling a grid
across the middle of each die and asking what lay under each point:

| Die | Holes before | Holes after |
|---|---|---|
| d6, d12, d20 | 0 | 0 |
| d10 | 238 of 784 | 0 of 676 |

The d4 keeps 31, because a tetrahedron's silhouette is a triangle and a square sample
region overhangs it.

**The d10's apex height was a guess.** A kite is four points, and four points are
coplanar at exactly one apex height for a given equator zigzag: apex = zigzag times
5 + 2√5. It shipped as zigzag 0.25 with apex 1.15, which is not that height, so every
kite was bent 0.26 out of its own plane on a die of radius 1.

**The d12's faces were the wrong five vertices.** It took its twelve face directions
from `icosahedron().verts` and kept the five vertices leaning furthest each way, and
that is the wrong cyclic permutation for this vertex set — those directions point at
the dodecahedron's own vertices. Each "face" was five points 1.05 out of plane. Faces
now come from support planes of the hull, found rather than guessed, which is the same
discipline the icosahedron already used.

The roller can now report its own flatness, which is the instrument that would have
caught all three: `Dice3D._flatness()` returns the worst out-of-plane distance per
solid, and every one is zero.

## Corrections the critic made to the sweep

- The impact-feel paper annotated 5,000 comments across **15** games, not 16. The
  sixteen is a different subset in the same paper.
- The claim that Demiplane ships no 3D dice is **stale**. The "thinking about it for
  the future" reply is real and from January 2024, but Demiplane's own patch notes in
  May 2025 mention fixing a bug where 3D dice were not showing for all players. Do not
  use it as evidence that a modern product judged dice unnecessary.
- The Game Developer article arguing against "audio is 50% of the experience" does not
  say "completely false". It says the claim is problematic and obviously untrue. Treat
  any percentage for audio's share of feel as rhetoric, not measurement.
- "No z-buffer, per the spec" overstates the sourcing. The CSS Transforms Level 2 spec
  cites Newell's algorithm and never uses the word. The practical consequence is right;
  the citation was not.

## What could not be sourced

- Any vendor stating a designed target duration for a dice animation. All the timing
  evidence is negative: complaints when it is too slow.
- Concrete opacity and scale numbers for a contact shadow, only the pattern.
- Swink's own primary text for "for players, simulation and polish are
  indistinguishable" and for the hundred-millisecond control figure. Only chapter one
  was reachable and neither passage is in it. Multiple secondary sources agree.
- Roll20's dice being off by default, and D&D Beyond's dice being unskippable because
  the physics is the randomness. Both are consistent across forum sources; both
  official pages refused fetching.
- A measured rejection rate for re-rolling a physics die until it matches a target,
  which is moot for us since nobody does it that way.

## The light was on the die, 2026-09-09

Reported from the table: "as it is right now the lighting is assigned to a few faces and
it spins with those faces, all other faces are darker. can you have the light stay
consistent and directional?" — and the same message asked for brass, with the numbers
engraved.

The lighting complaint was exactly right, and the code said so in one line. `buildSolid`
shaded each face once, at build time, from that face's normal **in the die's own frame**.
That is a light painted onto the die, so it turned with it. Turning each of the twenty
faces square-on to the camera in turn — the same `faceToFront` the landing uses, so the
normal is the identical direction every time — and reading what the browser computed:

| | brightness of the face turned to the camera | spread |
|---|---|---|
| before | 0.620–1.147, and **ten of the twenty faces pinned at 0.620**, the unlit floor | 0.527 |
| after | 0.786, all twenty | **0.000** |

"A few faces" was not an impression. Half the die was at the minimum.

### What the traditions do about it

Nothing, is the short answer: **CSS has no lighting model**, and there is no way to hold
a light still under a rotating object without recomputing per frame. Every CSS-3D
implementation that shades faces at all computes it in script from the object's live
orientation — the draggable-cube demos vary face opacity by angle to the viewport, the
`qube` library ships "automatic flat shading", and `filter: brightness()` per side is the
usual instrument. The physics renderers (Dice So Nice) have real lights because they have
a real renderer. Nothing found offers a static trick; the one article that promises CSS
lighting turns out to move `perspective-origin` and place a fixed dark copy on the floor,
which is a shadow, not a light.

So the shape is a per-frame pass, and the only real choice is which way round to carry
the rotation. Rotating twenty normals out of the die's frame costs twenty transforms per
frame; carrying the light and the eye **into** that frame costs two, because the rotation
is orthonormal and its inverse is its transpose. Everything after that is dot products in
the frame the geometry already lives in.

Two honest limits, both written at the code. On the contact frames the die carries a
non-uniform `scale3d`, for which the correct normal transform is the inverse transpose
rather than the rotation, so the shading is slightly wrong for about a tenth of a second.
And this is script, so it stops when the window is in the background while the compositor
keeps turning the die — the same throttling that caused the frozen die, running the other
way. The die is lit again a frame after anyone looks at it.

Measured cost: 60 frames in 1000ms through a real throw, median gap 16.7ms, worst 16.8ms,
nothing over 20ms, with 100 nodes on the die.

### Brass, and numbers cut into it

A face is now four layers clipped to the same polygon at four insets, which is what a
cast metal die is: the dark chamfer where two faces meet, the bevel that catches the
light, a hairline rule that is the ornament, and the flat panel the number is cut into. A
clip-path cannot be stroked, so the rule is a dark layer showing through between two
others.

- **The metal.** Brass is anisotropic, and the whole of the CSS "brushed metal" tradition
  is alternating light and dark stops running along a grain rather than a smooth ramp.
  The ramp colours are custom properties, so the landed, critical and fumbled states
  restate the metal in four values instead of restating three background layers.
- **The sheen** sits where the light is: `--sx`/`--sy` are the light flattened into that
  face's own plane, so the highlight slides across the brass as the die turns.
- **The numerals are engraved**, by the letterpress recipe — a dark wall on the side the
  light comes from and a lit one opposite — with the offsets live rather than authored,
  so the cut keeps facing the same way while the die turns. They fall to nothing as a
  face turns to meet the light head-on, which is what a groove seen straight down does.
- **The bevel is a constant width.** Scaling a face's points toward its centre is one
  line and is exact for a regular polygon, which every face here is except the d10's
  kite: on a kite it puts a wide border on the blunt end and pinches it to nothing at the
  sharp one, and it showed. Each edge is offset along its own inward normal now, mitred,
  with the mitre clamped the way SVG clamps it.

### The bench walks the joins now

Two buttons were added, because of the instruction written down after the last dice
build. One runs the sequence the game runs — ask, hold the mat, wait out a six-second
stand-in for the model call, land — since every dice defect the table has reported lived
in the joins between those, not inside any one of them. The other measures the light.

The first attempt at that measurement was wrong in a way worth keeping: it sampled
"whichever face is most square-on" through a spin and reported a spread of 0.920. On a
d20 the front-most face still wanders about twenty degrees off the view axis, so its own
normal is moving and the reading moves with it. It measured nothing. Driving each face
square-on with `faceToFront` measures the thing. And the loop is synchronous, because
animation frames do not fire in a background tab — a bench that waits for one measures
nothing unless somebody is watching it, which is the same throttling that froze the die.
