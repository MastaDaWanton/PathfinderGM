"""The die has to move, land the right way up, and make a noise when it hits.

Reported at the table: the 3D roller was "lack luster and doesn't feel good". Four
defects were measured on the bench (`tools/dicebench/`, served over HTTP so the module
gets a real origin for its audio context), and each has a line here.

  * **The throw did not animate.** The first 600ms set `transition: none` and stepped
    through seven random orientations 60 to 140ms apart. The die teleported between
    poses, then played one 0.85s transition into the landing. Two thirds of the throw
    had no motion in it.
  * **The number landed any way up.** Rotating a face normal onto the view axis leaves
    one degree of freedom unused, and nothing used it, so which way up the winning
    number read was luck. Measured 2026-09-09: a d20 showing 14 landed with the 14
    upside down, and the 19 above it too.
  * **A percentile roll drew one die.** `#d3d-die2` carries `display:none` in the
    stylesheet and `landPercentile` cleared the INLINE display to reveal it — which
    falls back to the rule, so the ones die had never been visible. A d100 drew the
    tens die alone, off to the left of centre.
  * **No sound at all.** The one quantitative study found (arXiv:2208.06155) names
    sound coherence as one of three features that make or break how an impact feels,
    and its finding is specifically about sync.

These are source checks rather than behaviour: there is no JavaScript test runner here
and adding one would be a third dependency in an app that has two. What they pin is
that the mechanism is still present, in the shape the bench was used to verify.
See docs/dice-feel.md.
"""
from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parents[1] / "play" / "static" / "js"
       / "dice3d.js").read_text(encoding="utf-8")


def _code(text: str) -> str:
    """Source with the comments stripped.

    Twice now a test has failed on a comment that explains the very number it was
    checking had gone — the prose is not the bug, and a test that cannot tell them
    apart is checking the wrong thing.
    """
    kept = [l for l in text.splitlines() if not l.strip().startswith("//")]
    return chr(10).join(kept)


def _fn(name: str) -> str:
    """One function's source, from its declaration to the next one at column two."""
    start = SRC.index("function " + name + "(")
    rest = SRC[start + 10:]
    end = rest.find("\n  function ")
    return rest if end < 0 else rest[:end]


def test_the_throw_actually_animates():
    """The seven-pose slideshow is gone and the throw is one real animation."""
    throw = _fn("tumble")
    assert "el.animate(" in throw, "the throw is no longer an animation"
    assert "[60, 60, 65, 75, 90, 110, 140]" not in SRC, "the jump-cut tumble is back"
    # Every frame carries the landing pose, so whatever the tumble did, the last frame
    # is exactly where the server's result lives.
    assert throw.count("at(") >= 4
    assert "landTransform" in _fn("tumble")


def test_the_throw_is_shorter_than_it_was():
    """It was about 1.5s. Frequent animations want to be short, and the field evidence
    on dice is one-sided: every product whose dice are slow has a revolt about it."""
    line = next(l for l in SRC.splitlines() if l.strip().startswith("var THROW_MS"))
    ms = int(line.split("=")[1].split(";")[0].strip())
    assert 500 <= ms <= 900, ms


def test_the_number_lands_the_right_way_up():
    """The unused degree of freedom, now used."""
    land = _fn("faceToFront")
    assert "rotateZ(" in land, "the roll correction is gone; numbers land any way up"
    assert "rotateAbout(" in land, "the face's own up is no longer carried through"
    assert "Math.atan2" in land


def test_a_percentile_roll_draws_both_dice():
    """Clearing an inline style falls back to the rule, and the rule said none."""
    assert "#d3d-stage.pair #d3d-die2{display:block}" in SRC


def test_the_die_makes_a_noise_when_it_lands():
    """Scheduled on the audio clock at the same instant the animation starts, so the
    sound cannot drift from the frame it belongs to."""
    throw = _fn("tumble")
    assert throw.count("clack(") >= 2, "both contacts should sound"
    assert "ms * 0.68" in throw and "ms * 0.91" in throw, \
        "the clacks are no longer pinned to the contact frames"
    # Pitch jitter: a dozen identical samples in a row is the machine-gun effect.
    assert "Math.random()" in throw.split("var pitch")[1][:60]


def test_the_sound_can_be_silenced_and_needs_no_asset():
    assert "pfgm.dice.mute" in SRC
    assert "createBufferSource" in SRC and "createOscillator" in SRC, \
        "the clack is no longer synthesised"
    for asset in (".mp3", ".wav", ".ogg", "base64"):
        assert asset not in SRC, f"an audio asset ({asset}) crept into the roller"


def test_the_shadow_is_never_on_the_element_holding_the_faces():
    """`opacity` below 1 and `filter` both force `transform-style: flat` on their own
    subtree. Either on the die would collapse the solid into a flat card."""
    assert "#d3d-stage .sh{position:absolute" in SRC
    assert "class=\"sh\" id=\"d3d-sh1\"" in SRC or 'class="sh" id="d3d-sh1"' in SRC


def test_reduced_motion_shortens_the_throw_rather_than_removing_it():
    """Reduce, not remove: the player still needs to see that a roll happened."""
    throw = _fn("tumble")
    assert "reducedMotion()" in throw
    branch = throw.split("if (reducedMotion())")[1][:400]
    assert "landTransform" in branch, "reduced motion no longer lands on the result"
    assert "clack(" in branch, "reduced motion lost its feedback entirely"


@pytest.mark.parametrize("shape", ["tetrahedron", "cube", "octahedron",
                                   "trapezohedron", "dodecahedron", "icosahedron"])
def test_every_solid_is_still_built_from_its_own_vertices(shape):
    """The roller was not rewritten. Everything above is polish on the geometry that
    was already right."""
    assert "function " + shape + "()" in SRC


def test_the_light_belongs_to_the_room_and_not_to_the_die():
    """The one the table could see without knowing the word for it.

    `buildSolid` shaded each face once, at build time, from that face's normal in the
    DIE's own frame — so the shading was painted onto the die and turned with it.
    Reported 2026-09-09: "the lighting is assigned to a few faces and it spins with
    those faces, all other faces are darker."

    Measured on the bench by turning each of the twenty faces square-on to the camera
    in turn — the same `faceToFront` the landing uses, so the face's normal is the
    identical direction every time — and reading what the browser computed for it:

        before   brightness 0.620-1.147, spread 0.527, and TEN of the twenty faces
                 pinned at 0.620, which is the unlit floor. "A few faces" was exact.
        after    0.786 on all twenty. Spread 0.000.

    So the number the die lands on is now lit the same whichever number it is. The
    shading has to be recomputed per frame — CSS has no lighting model, and every
    CSS-3D implementation that shades faces at all does it in script from the object's
    live orientation — and the die's own matrix is where the orientation comes from.
    """
    src = _code(SRC)
    assert "function shadeOne(" in src, "nothing shades the die as it turns"
    assert "new DOMMatrix(" in src, "the shading no longer reads the die's live matrix"
    assert "requestAnimationFrame(shadeLoop)" in src, "the light is not kept up to date"
    assert "var LIGHT = norm(" in src, "there is no one light for the room"
    build = _code(_fn("buildSolid"))
    assert "el.style.filter" not in build, "the light is baked into the faces again"
    assert "brightness(" not in build, "a face is deciding its own brightness again"
    # The cheap direction: the light and the eye are carried INTO the die's frame, so a
    # frame costs two rotations rather than one per face.
    shade = _code(_fn("shadeOne"))
    assert "dot(cx, LIGHT)" in shade and "dot(cx, VIEW)" in shade, \
        "the light is being carried the expensive way round"


def test_a_face_that_is_turned_away_is_not_shaded():
    """Half the faces of a solid point away from the camera at any moment and are
    hidden by `backface-visibility`. Shading them is twenty writes a frame that nobody
    can see, and this loop runs every frame of every roll."""
    shade = _code(_fn("shadeOne"))
    assert "f.toward <= 0.02" in shade, "hidden faces are being shaded again"


def test_the_numbers_are_engraved_rather_than_printed():
    """A groove shows a dark wall on the side the light comes from and a lit one
    opposite — the letterpress recipe, with the light direction live instead of
    authored, so the cut keeps facing the same way while the die turns.

    The offsets are the light flattened into that face's own plane, which is why they
    fall to nothing as a face turns to meet the light head-on: a groove seen straight
    down has no visible wall.
    """
    src = _code(SRC)
    assert "text-shadow:calc(var(--ex,0) * 1px)" in src, "the numerals are printed flat"
    assert "calc(var(--ex,0) * -1.3px)" in src, "the lit wall of the groove is gone"
    shade = _code(_fn("shadeOne"))
    assert 'setProperty("--ex"' in shade and 'setProperty("--ey"' in shade, \
        "nothing tells the engraving which way the light is"
    assert "dot(L, f.x0)" in shade, "the groove no longer follows the real light"


def test_a_face_is_brass_with_an_edge_a_bevel_a_rule_and_a_panel():
    """Four layers clipped to the same polygon at four insets, which is what a cast
    metal die is: the dark chamfer where two faces meet, the bevel that catches the
    light, the hairline rule that is the ornament, and the flat panel the number is cut
    into. A clip-path cannot be stroked, so the rule is a dark layer showing through."""
    build = _code(_fn("buildSolid"))
    for cls, what in [('"b"', "bevel"), ('"g"', "ruled groove"), ('"p"', "panel")]:
        assert "className = " + cls in build, "the " + what + " is gone"
    src = _code(SRC)
    assert "var BEVEL = " in src and "var RULE = " in src
    assert "linear-gradient(158deg,var(--m1),var(--m2) 40%" in src, \
        "the brass ramp is no longer a variable, so the landed state cannot restate it"
    # Metal does not shade like plastic: the ramp alternates light and dark along a
    # grain rather than running smoothly from one end to the other.
    assert "repeating-linear-gradient(118deg" in src, "the anisotropic grain is gone"


def test_the_bevel_is_a_constant_width_rather_than_a_scaled_copy():
    """Scaling a face's points toward its centre is one line and is exact for a regular
    polygon — which every face here is EXCEPT the d10's kite. On a kite it puts a wide
    border on the blunt end and pinches it to nothing at the sharp one, and that shows
    on screen. Each edge is offset along its own inward normal instead, with a mitre
    limit, because at a sharp corner the true mitre runs far outside the face."""
    src = _code(SRC)
    assert "function inset(pts, d)" in src
    assert "var cap = d * 3.2" in src, "the mitre limit is gone; sharp corners will fly"
    assert "p[0] * k" not in src, "the old centroid scaling is back"


def test_the_bench_walks_the_path_the_player_walks():
    """The instruction written down after the last dice build: the bench verified
    `land()` while the game called `ask()`, posted to the server and then landed, so
    every fix was green and the player saw no change. The joins are where the defects
    were, so the bench has to walk the joins."""
    bench = (Path(__file__).resolve().parents[1] / "tools" / "dicebench"
             / "index.html").read_text(encoding="utf-8")
    assert 'id="real"' in bench, "the bench cannot walk the real path again"
    assert "Dice3D.ask(Object.assign({ hold: true }" in bench
    assert "setTimeout(r, 6000)" in bench, "the bench no longer waits out a model call"
    assert "requestAnimationFrame" not in bench.split('id="light"')[1][:1200], \
        "the light measurement waits for a frame, and frames stop in a background tab"


def test_the_bench_is_kept():
    """Judging how a die feels needs it thrown a hundred times, which inside a campaign
    would mean a hundred real turns and a model call each."""
    bench = (Path(__file__).resolve().parents[1] / "tools" / "dicebench" / "index.html")
    assert bench.exists()
    text = bench.read_text(encoding="utf-8")
    assert "../../play/static/js/dice3d.js" in text, \
        "the bench must load the live roller, not a copy"


def test_a_face_normal_comes_from_its_own_plane():
    """The one that made the dice come apart.

    `prepare` took each face's normal as the direction of its CENTRE from the origin.
    That is the same as the plane's normal only when a face is symmetric about it —
    true of every regular solid here, and false of the d10, whose kites run from a near
    apex to a far equator point. All ten of its faces were tilted off their true
    planes, so neighbours could not meet.

    Measured in the browser, 2026-09-09, sampling a grid across the middle of each die
    and asking what was under each point:

        d6 0 holes, d12 0, d20 0 — and d10 238 holes of 784.

    After: every one of d6, d8, d10, d12 and d20 at 0 of 676. (The d4 keeps 31, because
    a tetrahedron's silhouette is a triangle and the sample square overhangs it.)
    """
    prep = _fn("prepare")
    code = _code(prep)
    assert "cross(sub(verts[face[b]], verts[face[a]])" in code,         "the normal is no longer taken from the face's own plane"
    assert "z = z || norm(c);" in code, "the degenerate fallback is gone"
    assert "if (dot(z, c) < 0)" in code, "nothing is orienting the normal outward"
    assert "var z = norm(c);" not in code, "the old centre-direction normal is back"


def test_the_d10_apex_is_derived_rather_than_guessed():
    """A kite is four points, and four points are coplanar at exactly one apex height
    for a given zigzag. Shipped as zigzag 0.25 with apex 1.15, which is not it: every
    kite was bent 0.26 out of plane on a die of radius 1."""
    trap = _fn("trapezohedron")
    # The code, not the comment: the comment above it explains the old 1.15 at length,
    # and the comment is not the bug.
    code = _code(trap)
    assert "ZIG * (5 + 2 * Math.sqrt(5))" in code,         "the apex is a magic number again, and the d10's faces will not be flat"
    assert "1.15" not in code


def test_faces_are_found_rather_than_guessed():
    """The d12 took its twelve face directions from the icosahedron's vertices, and
    that is the wrong cyclic permutation for this vertex set: those directions point at
    the dodecahedron's own vertices. Each "face" was five points 1.05 out of plane."""
    assert "function hullFaces(" in SRC
    dodeca = _fn("dodecahedron")
    assert "hullFaces(v)" in dodeca
    assert "icosahedron().verts" not in dodeca, "the wrong twelve directions are back"


def test_the_roller_can_report_its_own_flatness():
    """Both geometry bugs were invisible until something measured them. This is the
    instrument: every solid's worst out-of-plane distance, which must be zero."""
    assert "_flatness:" in SRC
    assert "worst * 10000" in SRC

def test_the_main_roll_path_actually_lands_the_die():
    """The one the player kept seeing, and the one the bench never tested.

    `showPopup` asked, `sendRoll` posted the answer and rendered the state, and nothing
    ever called `land`. So `ask`'s cast — a full 910ms throw of its own — ended on
    whatever face happened to face the camera, the mat closed, and the number arrived
    in a table. Reported 2026-09-09: "the animation skips and the dice don't land with
    the number facing the user." They never did on that path.

    `/api/roll` now answers with the face it used, the mat is held open across the
    request, and the throw lands on it.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    table = (root / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")
    views = (root / "play" / "views.py").read_text(encoding="utf-8")

    # The WHOLE function, not a fixed slice of it. This read `[:1400]` and went stale on
    # 2026-09-16 the moment the function grew comments: the call it checks for was still
    # there, four characters past the cut, and the test reported that the main roll path
    # never lands the die. A measurement with a magic number in it measures the number.
    at = table.index("async function sendRoll(")
    send = table[at:table.index(chr(10) + "}", at) + 2]
    assert "Dice3D.land(" in send, "the main roll path still never lands the die"
    assert "state.rolled" in send, "the page is not landing on what the server rolled"
    assert "Dice3D.close()" in send, "a held-open mat with nothing to land would hang"

    assert '"rolled": face' in views, "the roll endpoint no longer says what it rolled"
    assert "hold: true" in table, "the mat is no longer held across the request"


def test_the_die_lands_before_the_narrator_has_finished():
    """Reported from the table 2026-09-16: *"as it stands when dice are rolled the last
    die spins until a reply is sent to the user. I would prefer that the dice land show
    the number it landed on and then be able to be closed while the user waits."*

    The cause was the shape of `/api/roll`: it knows the face in its first few lines and
    returns it after resolution AND the narrator, which is a local model and the slow
    part of a turn. So the die span for the whole generation — and the last die of a turn
    span longest, because every earlier one only had to be handed back for the next
    prompt.

    Three things hold the fix together, and each is one a later edit could quietly undo:
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    table = (root / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")
    views = (root / "play" / "views.py").read_text(encoding="utf-8")
    urls = (root / "pathfindergm" / "urls.py").read_text(encoding="utf-8")

    # 1. the face is available without doing the turn, and asking for it changes nothing
    assert "def roll_face(" in views
    assert "api/roll/face" in urls
    face = views[views.index("def roll_face("):views.index("def roll(request):")]
    for mutates in ("engine.resume", "c.save()", "scene.awaiting =", "_finish("):
        assert mutates not in face, f"roll_face must not {mutates} — it may be abandoned"

    at = table.index("async function sendRoll(")
    send = table[at:table.index(chr(10) + "}", at) + 2]
    # 2. the page asks for it and lands WITHOUT waiting for /api/roll
    assert "/api/roll/face" in send
    assert send.index("Dice3D.land(") < send.index('post("/api/roll"'),         "the die is still landing after the turn instead of before it"
    # 3. and does not await the landing, because `land` resolves only when the player
    #    closes the mat — awaiting it here is exactly the stall being fixed
    early = send[:send.index('post("/api/roll"')]
    assert "await Dice3D.land(" not in early, \
        "awaiting the landing blocks the request on the player closing the mat"


def test_the_ask_winds_up_and_does_not_throw():
    """Two throws with a cut between them is what "skips" meant. The wind-up lifts the
    die and hands over; the throw belongs to `land`, which is the only thing that knows
    what the die has to show."""
    cast = _code(_fn("cast"))
    assert "translateY(-52px)" in cast
    assert "560" not in cast and "rotateX(560deg)" not in cast,         "the old second throw is back inside the ask"
    assert cast.count("setTimeout") == 1, "the wind-up grew a second stage again"

def test_the_die_keeps_rolling_while_the_table_works_it_out():
    """`/api/roll` narrates the turn, so it can take twenty seconds. Holding the mat
    open across it left the die frozen in its wind-up pose for all of them.

    Reported 2026-09-09: the die "freezes like this for a while until it snaps to the
    number it rolled... the snap only seems to happen after i take a screen shot" —
    which is the window losing focus, script timers throttling, and a pose held by a
    transition that had already finished.

    A CSS keyframe animation, deliberately: it runs on the compositor and keeps moving
    when script callbacks are throttled. The file already learned this once, for the
    idle drift.
    """
    assert "@keyframes d3d-cast{" in SRC, "the waiting die has nothing turning it"
    ask = _code(_fn("ask"))
    assert "d3d-cast 1.05s linear infinite" in ask,         "the held mat no longer keeps the die rolling"
    assert "textContent = " in ask

    # And the throw takes over from it rather than fighting it.
    throw = _code(_fn("tumble"))
    assert 'el.style.animation = "none";' in throw,         "the waiting animation is never stopped, so the throw competes with it"


def test_the_foraging_survival_die_lands_and_can_be_closed():
    """The same two faults as the main path, found on 2026-09-17 when asked to fix the
    craft dice, and one of them older than the other.

    1. **The Survival die never landed at all.** `Dice3D.ask` was called with no `hold`,
       so the mat shut the instant the player threw: they wound the die up, it went, and
       the mat vanished with no number on it. That is precisely the defect reported on
       2026-09-09 — "the dice don't land with the number facing the user" — fixed on the
       table's own roll and left living here.

    2. **The number waited on the narrator.** The second half of a forage runs a closing
       narration, a model call, before it answers. With `hold` added and nothing else,
       that would have made this path strictly worse than it was: a die spinning over a
       held mat for the length of a generation, which is the exact complaint that started
       this work.

    So the face is asked for first, on the endpoint that changes nothing, and the die
    lands on it before the turn is posted.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    table = (root / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")

    at = table.index('post("/api/craftaction", { action: "forage"')
    block = table[at:table.index("render(await", at)]

    assert "hold: true" in block, "the forage mat still shuts on the throw"
    assert "/api/roll/face" in block, "the forage die still waits on the narrator"
    assert block.index("Dice3D.land(") < block.index('"/api/craftaction", { face:'), \
        "the Survival die still lands after the turn instead of before it"
    # A held mat over a failed request is a die spinning on a page that has stopped.
    assert "Dice3D.close()" in block, "a failed forage would leave the die spinning"
    # And the haul is a second die: it must not open on top of the first.
    assert "await survival" in block, "the d100 would open over the Survival check"


def test_the_excursion_die_is_left_alone_because_nothing_narrates_behind_it():
    """Checked rather than assumed, and it corrected something I had reported.

    The excursion dice were named alongside foraging as having the same defect. They do
    not: `craft_excursion` makes no narration call at all — the line it returns is built
    out of the haul by string formatting — so its answer comes back in milliseconds and a
    die that lands on it is not waiting for anything.

    This pins the reason. If a narration call is ever added to that view, the die in
    front of it becomes the foraging problem and this fails, which is the only warning
    anyone would get.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    src = (root / "play" / "craft_views.py").read_text(encoding="utf-8")
    view = src[src.index("def craft_excursion("):src.index("def craft_action(")]
    assert "_narrate(" not in view, (
        "craft_excursion now narrates, so its die waits on a model — it needs the "
        "same split as foraging (see /api/roll/face)")
