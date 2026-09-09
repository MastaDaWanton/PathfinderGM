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

    send = table[table.index("async function sendRoll("):][:1400]
    assert "Dice3D.land(" in send, "the main roll path still never lands the die"
    assert "state.rolled" in send, "the page is not landing on what the server rolled"
    assert "Dice3D.close()" in send, "a held-open mat with nothing to land would hang"

    assert '"rolled": face' in views, "the roll endpoint no longer says what it rolled"
    assert "hold: true" in table, "the mat is no longer held across the request"


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
