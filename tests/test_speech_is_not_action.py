"""What the character SAID may not be read as what the character DID.

Measured 2026-09-08, nine player lines through `judgement.wants_a_fight`. Three
opened a fight and all three were speech:

  * `I tell the clerk "I am a monk, I can handle myself in a fight or handle a bunch
    of others."` — the line from the live session. Guards lunged, initiative rolled.
  * `I tell the clerk I am a monk and can handle myself in a fight`
  * `I tell the guard "put down your sword, I do not want to fight"` — a line
    refusing a fight, which started one.

The cause was that the scan ran over the whole raw line, and the "I" inside the
quotation satisfied `_player_is_the_one_swinging`, which asks who is named in front
of the verb. The guard that should have caught it, `_MUSING`, lists talk, speak and
ask but not tell, say or warn: a verb blacklist doing a job the traditions do with a
quarantined payload.

Inform 7 stores what follows "about" or "that" as a `topic` and says it "does not try
to understand automatically what that text might mean". LambdaMOO rewrites a leading
quote into `say` before any verb lookup happens at all. In neither can a word inside
speech reach the command table. See docs/speech-vs-action.md.
"""
from gm import judgement


SPEECH = [
    'I tell the clerk "I am a monk, I can handle myself in a fight or handle a bunch '
    'of others."',
    "I tell the clerk I am a monk and can handle myself in a fight",
    'I tell the guard "put down your sword, I do not want to fight"',
    "I warn the thug that I will hit him if he does not move",
    "I ask the woman if she wants to pay for my services",
    'I say to the merchant "if you point me in a direction I will dispense justice"',
    "I don't want to fight, I look for the door",
]

ACTION = [
    "I attack the guard",
    "I punch the thug in the mouth",
    "I tell him to move, then I draw my sword and attack the guard",
    "*I draw my blade and attack the guard*",
    "I don't hesitate, I attack the guard",
    "Just start swinging at him",
    "I throw my dagger at the watchman",
]


def test_speech_never_starts_a_fight():
    """Three of these nine started one on 2026-09-08, including a refusal to fight."""
    started = [t for t in SPEECH if judgement.wants_a_fight(t)]
    assert not started, started


def test_action_still_starts_a_fight():
    """The quarantine must not buy its silence by going deaf. A line with a real
    declaration in it is still a declaration, including one that follows speech in
    the same breath and one written in the asterisk convention."""
    missed = [t for t in ACTION if not judgement.wants_a_fight(t)]
    assert not missed, missed


def test_a_threat_is_not_an_attack():
    """Pathfinder 1e already draws this line: threatening is Intimidate, a standard
    action with a DC, not a swing. Speech about future violence is not violence."""
    assert not judgement.wants_a_fight(
        'I tell him "I will kill you where you stand if you touch that jar"')
    assert judgement.wants_a_fight("I kill him where he stands")


def test_redaction_keeps_the_line_the_same_length():
    """The detectors work in offsets — `_player_is_the_one_swinging` reads what comes
    before the verb — so blanking has to preserve position, not shorten the line."""
    for line in SPEECH + ACTION:
        assert len(judgement.redact_speech(line)) == len(line), line


def test_asterisks_are_action_and_are_left_alone():
    """The convention the player already knows, from IRC's emote and the MUSH pose
    onward: *asterisks are the action*, quotes are the speech. An asterisked span is
    exactly what a declaration detector should be reading."""
    line = '*I draw my blade* and I tell him "I will not be robbed"'
    kept = judgement.redact_speech(line)
    assert "draw my blade" in kept
    assert "robbed" not in kept


def test_an_apostrophe_is_not_a_quotation_mark():
    """Single quotes are deliberately not a delimiter. "I don't" and "the guard's
    blade" would each open one, and a redactor that swallows the rest of a line on an
    apostrophe is worse than the bug it fixes."""
    line = "I don't like the look of the guard's blade so I attack him"
    assert judgement.redact_speech(line) == line
    assert judgement.wants_a_fight(line)


def test_speech_runs_to_the_end_of_its_sentence_and_no_further():
    """Blanking to the end of the line would lose the sword in this one."""
    kept = judgement.redact_speech("I tell him to move, then I draw my sword")
    assert "draw my sword" in kept
    assert "to move" not in kept


def test_violence_the_player_is_declining_is_not_a_declaration():
    """Found beside the speech bug: "I don't want to fight, I look for the door" has
    no speech verb and no quotation, so redaction correctly leaves it whole — and the
    old rule then read "fight", found an "I" in front of it, and started one."""
    assert not judgement.wants_a_fight("I don't want to fight, I look for the door")
    assert not judgement.wants_a_fight("I would rather not fight the watchman")
    # Still a fight: the negation belongs to a different clause.
    assert judgement.wants_a_fight("I don't hesitate, I attack the guard")


def test_a_quoted_number_is_not_a_head_count_or_a_range():
    """`opponent_count` and `opening_feet` read the same line. A number the character
    speaks is not a number about the fight."""
    assert judgement.opponent_count('I say "there were four of them last night"') == 1
    assert judgement.opponent_count("I attack the four guards") == 4


def test_a_turn_where_the_player_spoke_never_gets_the_holding_line():
    """Measured on the 2026-09-08 playtest: every line the player wrote as speech came
    back as "The moment holds — nothing new shows itself just yet", while physical
    actions in the same session worked. The holding line is a parser-error floor being
    used as a conversation response.

    TADS 3 asks authors for a `DefaultAskTellTopic` matched at the lowest possible
    priority so an unanticipated topic still reaches a designed in-character
    non-answer; Façade carries "generic deflection and recovery global mix-ins" beside
    its beat-specific handlers. No tradition accepts silence here.
    """
    from pathlib import Path

    from gm import narration

    said = narration.unanswered_speech(
        'I ask the clerk if he wants coin', ["the clerk", "the apprentice"], turn=0)
    assert "The moment holds" not in said
    assert "clerk" in said
    assert said.endswith("What do you do?")

    src = (Path(__file__).resolve().parents[1] / "play" / "views.py").read_text(
        encoding="utf-8")
    floor = src[src.index("def _floor("):][:900]
    assert "was_speech" in floor, "the floor no longer asks whether the player spoke"


def test_the_non_answer_never_names_somebody_who_is_not_here():
    """Ground every name. Given freedom a model invents people and then treats them as
    settled fact; a canned line has no more licence than the model does."""
    from gm import narration

    said = narration.unanswered_speech("I ask Bellara about the seals", [], turn=0)
    assert "Bellara" not in said

    said = narration.unanswered_speech(
        "I ask the harbourmaster about the seals", ["the clerk"], turn=0)
    assert "harbourmaster" not in said


def test_the_non_answer_is_not_one_sentence_repeated():
    """Ten of ten paragraphs ending the same way is this project's oldest measured
    smell, and a canned floor is the easiest place in the app to reintroduce it."""
    from gm import narration

    seen = {narration.unanswered_speech("I say hello to the clerk", ["the clerk"], turn=t)
            for t in range(4)}
    assert len(seen) == 4, seen


def test_speech_reaches_the_engine_as_an_op():
    """Measured 2026-09-08: of the 42 ops the engine accepted, none carried speech, so
    every line the player wrote as dialogue could only resolve to `narrate_only` — and
    a narrate_only turn carries no tells, which is why the prose call had nothing to
    dress and answered with the holding line. Actions in the same session worked
    because every one of them had a door."""
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    eng.run(eng.validate([{"op": "spawn", "because": "the stall",
                           "params": {"template": "guildhand", "count": 1,
                                      "name": "the clerk"}}]))

    raw = judgement.inject_say([], 'I tell the clerk "keep the change"', c.scene)
    assert [i["op"] for i in raw] == ["say"]
    assert raw[0]["params"]["words"] == "keep the change"
    assert raw[0]["params"]["to"] in c.scene.actors

    out = eng.run(eng.validate(raw))
    assert out.outcomes and out.outcomes[0].tell, "a say produced no tell"
    assert "keep the change" in out.outcomes[0].tell


def test_the_sampler_is_told_speech_is_expected():
    """A declarer, so `declared_ops` finds it and the schema REQUIRES the op rather
    than hoping the model reaches for it."""
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    assert "say" in judgement.declared_ops(
        'I tell them "I am looking for work"', c.scene, c.world)
    assert "say" not in judgement.declared_ops("I attack the guard", c.scene, c.world)


def test_reported_speech_is_not_quoted_back():
    """"I ask her if she wants to pay for my services" is not a sentence the character
    said. A tell that quotes it puts the player's own framing, first person and all,
    into somebody's mouth for the narrator to copy."""
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    eng.run(eng.validate([{"op": "spawn", "because": "the stall",
                           "params": {"template": "guildhand", "count": 1,
                                      "name": "the clerk"}}]))
    raw = judgement.inject_say(
        [], "I ask the clerk if he wants to pay for my services", c.scene)
    assert not raw[0]["params"].get("quoted")
    out = eng.run(eng.validate(raw))
    assert '"' not in out.outcomes[0].tell, out.outcomes[0].tell


def test_talking_costs_nothing_because_the_rules_say_so():
    """Pathfinder 1e: "In general, speaking is a free action that you can perform even
    when it isn't your turn." A directed social attempt — persuade, deceive, threaten —
    is a different thing with a DC and a time cost, and it is a `check`."""
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    before = eng.scene.clock_minutes if hasattr(eng.scene, "clock_minutes") else None
    out = eng.run(eng.validate([{"op": "say", "because": "t",
                                 "params": {"words": "well met", "quoted": True}}]))
    assert not out.outcomes[0].rolls, "speaking rolled dice"
    if before is not None:
        assert eng.scene.clock_minutes == before, "speaking spent time"


def test_every_worked_suggestion_is_the_players_own_line():
    """Reported from the table, 2026-09-08: the chips read as advice from outside the
    fiction — "Ask what kind of coin it is" — and clicking one puts it straight into
    the player's box, where it arrives as advice. Instruction volume loses to
    demonstration volume, so the examples are what had to change, all fifty-one of
    them; the briefing line alone would not have moved it."""
    from gm import prompts

    bad = []
    for group in (prompts.EXAMPLES, prompts.COMBAT_EXAMPLES,
                  getattr(prompts, "CARRY_ON_EXAMPLES", [])):
        for ex in group:
            for said in ex["reply"].get("suggestions") or []:
                if not said.lower().startswith(("i ", "i'")):
                    bad.append(said)
    assert not bad, bad


def test_the_page_tells_speech_and_action_apart():
    """*Asterisks are what you did*, "quotes are what you said" — the convention the
    player already knows, from the IRC emote and the MUSH pose onward. Presentation
    only: no source was found claiming it improves what a model writes, and we do not
    claim it either."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "play" / "templates" / "play"
           / "table.html").read_text(encoding="utf-8")
    assert "const said = s => esc(s)" in src
    assert 'class="said"' in src and 'class="did"' in src
    # The transcript renders through it, not through the bare escaper.
    story = src[src.index('$("#story").innerHTML'):][:400]
    assert "said(b.text)" in story, "beats are no longer marked up"
