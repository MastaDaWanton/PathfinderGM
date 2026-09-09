"""`/cheat` — the author's own hand, and the machinery that keeps it honest.

The player asked for it in these words: "/cheat I defeat all the enemies", "/cheat the
merchant falls deeply in love with me", "/cheat I have 1000 gold" — and named the risk
themselves: "the hard part is perhaps making it actually give me the items and/or
narrating correctly."

Prior art settles the shape. Inform's PURLOIN moves a *real object* into your hands
wherever it is in the game; NetHack's #wizwish goes through the same object-naming
parser ordinary play uses, and an unparseable wish gives a random real object rather
than an invented one; DikuMUD's immortal commands are `load obj <vnum>` and
`set <player> gold 1000` — typed, targeted, resolved by the same code as normal play.
No tradition lets a sentence become fiction directly, because a wish the engine did not
execute is a fact only the narrator remembers, and the narrator forgets.

So both halves of the player's worry have one answer: the cheat becomes intents, and the
intents go through `engine.run`. Items are real because `give` is the op a shopkeeper
uses. Prose is honest because the narrator is fed the resulting tells and the claims
scrubber deletes any sentence stating a mechanic no tell backs.
"""
from __future__ import annotations

from rules import states
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


def _scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


def test_the_marker_is_read_in_code_not_by_the_model():
    """A model asked to notice a marker sometimes does not, and a cheat quietly narrated
    instead of executed is the worst of both: the fiction says you have the gold and the
    purse does not. Every declaration-detection in this app is in code for this reason."""
    from play.views import _CHEAT

    for said in ("/cheat I have 1000 gold", "/CHEAT the guard is my friend",
                 "  /cheat: it is midnight", "/cheat  I defeat all the enemies"):
        assert _CHEAT.match(said), said
        assert not _CHEAT.sub("", said, count=1).strip().startswith("/")
    for ordinary in ("I cheat at cards", "cheat", "/ cheat", "I take the tally board"):
        assert not _CHEAT.match(ordinary), ordinary


def test_a_cheat_is_checked_before_the_reaching_across_the_table_guard():
    """`say` refuses turns that declare what the WORLD does — which is every sentence a
    cheat is made of. "The merchant falls in love with me" is exactly the shape that
    guard exists to hand back, so the cheat branch has to run first or the feature is
    unreachable by two of its own three worked examples."""
    import ast
    from pathlib import Path

    src = Path("play/views.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "say")
    body = ast.get_source_segment(src, fn) or ""
    assert "_CHEAT.match" in body, "say no longer routes /cheat"
    assert body.index("_CHEAT.match") < body.index("player_input.check"), (
        "the world-declaration guard runs before the cheat branch, so "
        "'/cheat the merchant falls in love with me' is refused as reaching "
        "across the table")


def test_a_thousand_gold_is_a_thousand_gold_in_the_purse():
    """The first half of the player's worry: "actually give me the items". `give` is the
    same op a shopkeeper uses, so a cheat that reaches the engine moves real coin."""
    scene = _scene()
    engine = Engine(scene, Dice(seed=1))
    before = dict(scene.pc().purse or {})
    engine.run(engine.validate([
        {"op": "give", "because": "the author says so",
         "params": {"item": "gold", "count": 1000, "to": "pc"}}]))
    after = scene.pc().purse or {}
    assert after != before, f"the purse did not move: {before} -> {after}"
    assert sum(after.values()) > sum(before.values())


def test_defeating_everyone_leaves_nobody_standing():
    scene = _scene()
    engine = Engine(scene, Dice(seed=1))
    engine.run(engine.validate([
        {"op": "spawn", "because": "the fight",
         "params": {"template": "thug", "count": 3, "zone": "engaged"}},
        {"op": "begin_encounter", "because": "the fight",
         "params": {"sides": {"you": ["pc"], "them": ["c1", "c2", "c3"]}}}]))
    assert scene.in_encounter

    engine.run(engine.validate(
        [{"op": "condition", "because": "the author says so",
          "params": {"condition": "dead", "to": ref}} for ref in ("c1", "c2", "c3")]
        + [{"op": "end_encounter", "because": "the author says so", "params": {}}]))
    assert not scene.in_encounter
    assert all(scene.actors[r].is_down for r in ("c1", "c2", "c3"))


# --- the attitude track, which had nowhere to live until the merchant needed it --------

def test_an_attitude_is_a_state_and_not_a_sentence():
    """`rules/effectspec.py` has offered an `attitude` effect type since the spell
    import — thirty-three spells set one, charm person among them — and it shipped
    `engine=False` with its own note: "no check in the app consults an attitude yet".
    A charmed guard was charmed in the effect list and hostile in every sentence about
    him, because there was nowhere for the answer to live."""
    scene = _scene()
    engine = Engine(scene, Dice(seed=1))
    engine.run(engine.validate([
        {"op": "spawn", "because": "the stall",
         "params": {"template": "guildhand", "count": 1, "name": "the merchant"}}]))
    merchant = scene.actors["c1"]
    assert states.attitude_of(merchant) == ""

    # `origin="author:cheat"` is what `/cheat` itself passes (gm/agent.py). Since
    # 2026-09-09 an attitude is refused without a document behind it — the psychic
    # exploit came in through this exact op — and the author's console is one of the
    # documented doors. A bare validate() here would be asserting the exploit is legal.
    engine.run(engine.validate([
        {"op": "condition", "because": "the author says so",
         "params": {"condition": "helpful", "to": "c1"}}], origin="author:cheat"))
    assert states.attitude_of(merchant) == "helpful"
    assert merchant.has_state("attitude"), "the family is not queryable by prefix"


def test_an_attitude_is_not_a_state_that_stops_anything():
    """Under `attitude.*` and never `state.*`: being fond of somebody impairs no roll and
    stops no action, and a `recovery.*` tag would have every sweep in the app cure
    infatuation on a night's sleep."""
    for step in states.ATTITUDES:
        tags = states.tags_for(step)
        assert tags == (f"attitude.{step}",), (step, tags)
        assert not states.stops(tags), f"{step} blocks actions"


def test_nobody_is_hostile_and_helpful_at_once():
    """One step at a time. Without this a charm laid over an old grudge left both
    standing and `attitude_of` answered with whichever the reversed walk hit first."""
    scene = _scene()
    engine = Engine(scene, Dice(seed=1))
    engine.run(engine.validate([
        {"op": "spawn", "because": "the stall",
         "params": {"template": "guildhand", "count": 1, "name": "the merchant"}}]))
    for step in ("hostile", "friendly", "helpful"):
        engine.run(engine.validate([
            {"op": "condition", "because": "t",
             "params": {"condition": step, "to": "c1"}}], origin="author:cheat"))
    merchant = scene.actors["c1"]
    assert states.attitude_of(merchant) == "helpful"
    held = [t for c in merchant.conditions for t in states.tags_for(c.key)
            if t.startswith("attitude.")]
    assert held == ["attitude.helpful"], held


def test_the_brief_says_how_they_feel_or_the_narrator_cannot_know():
    """The tell is severed: the narrator is told facts, never asked to read the effect
    list. An attitude nobody states is an attitude the prose contradicts."""
    from gm import prompts

    scene = _scene()
    engine = Engine(scene, Dice(seed=1))
    engine.run(engine.validate([
        {"op": "spawn", "because": "the stall",
         "params": {"template": "guildhand", "count": 1, "name": "the merchant"}},
        {"op": "condition", "because": "the author says so",
         "params": {"condition": "helpful", "to": "c1"}}],
        origin="author:cheat"))

    class _W:
        name, premise, secret = "Fantasia", {}, ""

        def ancestors(self, _):
            return []

    brief = prompts.scene_brief(_W(), scene, None, [])
    assert "helpful towards the player" in brief, brief[-1500:]


def test_a_cheat_cannot_reach_for_an_op_that_rolls():
    """The measurement that earned the allowlist. Probing `/cheat I have 1000 gold`
    against gemma-4-12B in a scene that happened to be mid-fight came back with
    `{"op": "attack", "actor": "pc"}` — the merchant swung at the player and knocked
    her unconscious, on a wish about money. A model in a fight does what it does in a
    fight, and no instruction outweighs a brief describing one.

    So the enum at the sampler carries it instead: `attack` is a token the model
    cannot emit here. The line is derived from the op table's own visibility column,
    not hand-listed, so an op added tomorrow lands on the right side of it — a cheat
    never rolls, because the author has already decided the outcome.
    """
    from gm import prompts
    from rules.intents import OPS

    rolls = {op for op, (_n, _m, vis) in OPS.items() if vis == "player"}
    assert rolls & {"attack", "check", "save", "sell", "buy"}, (
        "the visibility column no longer marks the rolling ops; this derivation "
        "needs rewriting rather than the test relaxing")
    assert not (set(prompts.CHEAT_OPS) & rolls), sorted(set(prompts.CHEAT_OPS) & rolls)
    assert "condition" in prompts.CHEAT_OPS and "give" in prompts.CHEAT_OPS

    schema = prompts.turn_schema(ops=prompts.CHEAT_OPS)
    enum = schema["properties"]["intents"]["items"]["properties"]["op"]["enum"]
    assert "attack" not in enum and "give" in enum

    # And the reference the prompt carries lists exactly those, generated rather than
    # hand-copied: CLAUDE.md's rule about grepping for every copy of a rule exists
    # because a consequence rule was fixed in one prompt and left stale in another.
    ref = prompts._op_reference()
    for op in prompts.CHEAT_OPS:
        assert f"\n  {op}:" in ref, op
    for op in rolls:
        assert f"\n  {op}:" not in ref, op


def test_a_plural_target_is_fanned_out_and_never_a_500():
    """Measured live against gemma-4-12B on the first `/cheat I defeat all the
    enemies`: it answered the plural honestly with ONE intent carrying
    `"to": ["c2", "c3"]`. Every op takes one ref, `_known` did `ref in
    self.scene.actors` on a list, and `unhashable type: 'list'` reached Django as a
    500 with a traceback.

    Two answers, both needed: the validator refuses the shape instead of dying on
    it, and the shaper fans it out first — because refusing is the wrong answer to a
    request that was perfectly clear.
    """
    from gm import judgement

    fanned = judgement.split_plural_targets([
        {"op": "condition", "because": "t",
         "params": {"condition": "dead", "to": ["c2", "c3"]}}])
    assert [i["params"]["to"] for i in fanned] == ["c2", "c3"]
    assert all(i["params"]["condition"] == "dead" for i in fanned)

    fanned = judgement.split_plural_targets(
        [{"op": "attack", "actor": "pc", "target": ["c1", "c2"]}])
    assert [i["target"] for i in fanned] == ["c1", "c2"]

    # Untouched when there is nothing plural about it.
    plain = [{"op": "narrate_only"}, {"op": "heal", "params": {"amount": 3, "to": "pc"}}]
    assert judgement.split_plural_targets(plain) == plain


def test_the_validator_refuses_a_container_where_a_ref_belongs():
    """The floor under the fan-out. Anything the shaper misses must be a rejection
    the model can read, never an exception Django turns into a blank button."""
    from rules.intents import IntentError

    scene = _scene()
    engine = Engine(scene, Dice(seed=1))
    for raw in ([{"op": "condition", "because": "t",
                  "params": {"condition": "dead", "to": ["c9"]}}],
                [{"op": "begin_encounter", "because": "t",
                  "params": {"sides": ["pc", "c1"]}}],
                [{"op": "check", "actor": "pc", "because": "t",
                  "params": {"skill": "stealth", "opposed_by": ["c1"]}}]):
        try:
            engine.run(engine.validate(raw))
        except IntentError:
            pass
        except Exception as exc:                      # noqa: BLE001 — that is the point
            raise AssertionError(
                f"{raw[0]['op']} raised {type(exc).__name__}, which is a 500") from exc


def test_the_number_in_the_wish_is_the_number():
    """Measured live against gemma-4-12B: `/cheat I have 1000 gold` came back as
    `give count=500` — half of what was asked for, resolved cleanly, tell and prose
    both confident about it. A cheat is the one turn where the author has already
    decided the quantity, so a model choosing a different one is a silent
    transcription error rather than a judgement call.

    And the model was not even the culprit. `_bounded` clamps `give.count` to 500
    because "no model authors a number", so a repair applied before validation was
    clamped straight back and the live probe read identically before and after — which
    is how the real cause was found. It runs on validated intents for that reason.
    """
    from gm import judgement
    from rules.intents import parse_all

    intents = parse_all([
        {"op": "give", "params": {"item": "gold", "count": 1000, "to": "pc"}}])
    assert intents[0].params["count"] == 500, (
        "the give clamp is gone; this test's whole point was that a pre-validation "
        "repair is undone by it")

    fixed = judgement.keep_the_authors_numbers(intents, "I have 1000 gold")
    assert fixed[0].params["count"] == 1000
    assert fixed[0].params["item"] == "gold", "it rewrote more than the number"

    # And it lands in the purse, which is the thing the player asked for.
    scene = _scene()
    engine = Engine(scene, Dice(seed=1))
    engine.run(judgement.keep_the_authors_numbers(
        engine.validate([{"op": "give", "because": "the author says so",
                          "params": {"item": "gold", "count": 1000, "to": "pc"}}]),
        "I have 1000 gold"))
    assert (scene.pc().purse or {}).get("gp") == 1000, scene.pc().purse

    # Commas are how people write big numbers.
    fixed = judgement.keep_the_authors_numbers(
        parse_all([{"op": "heal", "params": {"amount": 3}}]), "heal me for 1,000")
    assert fixed[0].params["amount"] == 1000

    # Two numbers cannot be assigned without guessing which belongs where, and
    # guessing is what this exists to stop.
    for wish in ("2 potions of 3 doses", "give me a potion"):
        same = parse_all([{"op": "give", "params": {"item": "potion", "count": 2}}])
        assert judgement.keep_the_authors_numbers(same, wish)[0].params["count"] == 2
