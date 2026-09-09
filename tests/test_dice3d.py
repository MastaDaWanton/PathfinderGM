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
