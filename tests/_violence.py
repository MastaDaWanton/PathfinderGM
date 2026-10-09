"""The readings a declared blow is decided from, and the path a turn runs them through.

Since 2026-10-09 (the owner: "if i say I attack the closest person or i go on a rampage or
i assault a civilian etc. it should be able to start a fight") nothing reads the player's
sentence with a regex to decide whether a fight was declared: the reader's `attack` act
does, and `acts_to_ops.victims` finds the real person the blow lands on. So every test that
pinned the retired `wants_a_fight` / template-thug `inject_fight` hands in the reading the
LIVE reader gave its sentence (docs/structured-turn.md's practice for retired readers).

READINGS: gemma-4-12B heretic through `interpret.interpret`, 2026-10-09, with the two
violence demonstrations of that day in the prompt; recorded once by a probe script and
copied here verbatim (slots only). A sentence the reader read as no attack at all is the
protection the regex used to give: speech, a question, a report, an idiom.
"""
from __future__ import annotations

READINGS: dict[str, list[dict]] = {
    # The owner's four lines.
    'I attack the closest person.': [{'act': 'attack', 'target': 'the closest person', 'span': 'attack the closest person'}],
    'I assault a civilian.': [{'act': 'attack', 'target': 'a civilian', 'span': 'assault a civilian'}],
    'I go on a rampage.': [{'act': 'attack', 'span': 'go on a rampage'}],
    'I pick a fight with the biggest bruiser in the room.': [{'act': 'attack', 'target': 'the biggest bruiser in the room', 'span': 'pick a fight with the biggest bruiser in the room'}],
    # Speech: measured 2026-09-08, three of these started fights through the regex.
    'I tell the clerk "I am a monk, I can handle myself in a fight or handle a bunch of others."': [{'act': 'talk', 'target': 'the clerk', 'says': 'I am a monk, I can handle myself in a fight or handle a bunch of others.', 'span': 'tell the clerk "I am a monk, I can handle myself in a fight or handle a bunch of others."'}],
    'I tell the clerk I am a monk and can handle myself in a fight': [{'act': 'talk', 'target': 'the clerk', 'says': 'I am a monk', 'span': 'tell the clerk I am a monk'}, {'act': 'claim', 'span': 'and can handle myself in a fight'}],
    'I tell the guard "put down your sword, I do not want to fight"': [{'act': 'talk', 'target': 'the guard', 'says': 'put down your sword, I do not want to fight', 'span': 'tell the guard "put down your sword, I do not want to fight"'}],
    'I warn the thug that I will hit him if he does not move': [{'act': 'talk', 'target': 'the thug', 'says': 'that I will hit him if he does not move', 'span': 'warn the thug that I will hit him if he does not move'}],
    'I ask the woman if she wants to pay for my services': [{'act': 'talk', 'target': 'the woman', 'says': 'if she wants to pay for my services', 'span': 'ask the woman if she wants to pay for my services'}],
    'I say to the merchant "if you point me in a direction I will dispense justice"': [{'act': 'talk', 'target': 'the merchant', 'says': 'if you point me in a direction I will dispense justice', 'span': 'say to the merchant "if you point me in a direction I will dispense justice"'}],
    "I don't want to fight, I look for the door": [{'act': 'search', 'object': 'the door', 'span': 'I look for the door'}],
    'I tell him "I will kill you where you stand if you touch that jar"': [{'act': 'talk', 'target': 'him', 'says': 'I will kill you where you stand if you touch that jar', 'span': 'tell him "I will kill you where you stand if you touch that jar"'}],
    'I would rather not fight the watchman': [],
    # Action.
    'I attack the guard': [{'act': 'attack', 'target': 'the guard', 'span': 'attack the guard'}],
    'I punch the thug in the mouth': [{'act': 'attack', 'target': 'the thug', 'span': 'punch the thug in the mouth'}],
    'I tell him to move, then I draw my sword and attack the guard': [{'act': 'talk', 'target': 'him', 'says': 'move', 'span': 'tell him to move'}, {'act': 'use', 'object': 'my sword', 'span': 'draw my sword'}, {'act': 'attack', 'target': 'the guard', 'span': 'attack the guard'}],
    '*I draw my blade and attack the guard*': [{'act': 'use', 'object': 'my blade', 'span': 'draw my blade'}, {'act': 'attack', 'target': 'the guard', 'span': 'attack the guard'}],
    "I don't hesitate, I attack the guard": [{'act': 'attack', 'target': 'the guard', 'span': 'attack the guard'}],
    'Just start swinging at him': [{'act': 'attack', 'target': 'him', 'span': 'Just start swinging at him'}],
    'I throw my dagger at the watchman': [{'act': 'attack', 'target': 'the watchman', 'object': 'my dagger', 'span': 'throw my dagger at the watchman'}],
    'I kill him where he stands': [{'act': 'attack', 'target': 'him', 'place': 'where he stands', 'span': 'kill him where he stands'}],
    "I don't like the look of the guard's blade so I attack him": [{'act': 'attack', 'target': 'him', 'span': 'I attack him'}],
    # Idioms, questions, reports: the template thug's old false alarms.
    'I hit the road at first light.': [{'act': 'journey', 'place': 'the road', 'span': 'hit the road at first light'}],
    'I strike a match.': [{'act': 'use', 'object': 'a match', 'span': 'strike a match'}],
    'I strike camp.': [{'act': 'rest', 'span': 'strike camp'}],
    'I jump the queue.': [{'act': 'other', 'span': 'jump the queue'}],
    'I attack the problem from another angle.': [{'act': 'other', 'target': 'the problem', 'span': 'attack the problem from another angle'}],
    'I shove the door open.': [{'act': 'break_in', 'object': 'the door', 'span': 'shove the door open'}],
    'I charge the toll and let him pass.': [{'act': 'talk', 'says': 'the toll', 'span': 'charge the toll'}, {'act': 'other', 'target': 'him', 'span': 'let him pass'}],
    'Should I attack him?': [],
    # Intended, not done: commitment keeps it off the engine (`interpret.COMMITS`).
    'I think about attacking him.': [{'act': 'attack', 'commit': 'intended', 'target': 'him', 'span': 'think about attacking him'}],
    'The thug attacks me.': [],
    'I watch as the thug attacks me.': [{'act': 'look', 'object': 'the thug attacks me', 'span': 'watch as the thug attacks me'}],
    'He punches me in the ribs.': [],
    'They start fighting each other.': [],
    # The lines the retired template thug's own tests used.
    'I shoulder my way into the tavern and pick a fight with the bruiser.': [{'act': 'go', 'place': 'the tavern', 'span': 'shoulder my way into the tavern'}, {'act': 'attack', 'target': 'the bruiser', 'span': 'pick a fight with the bruiser'}],
    'I attack the man at the bar.': [{'act': 'attack', 'target': 'the man', 'place': 'the bar', 'span': 'attack the man at the bar'}],
    'I punch him.': [{'act': 'attack', 'target': 'him', 'span': 'punch him'}],
    'I take a swing at the nearest drunk.': [{'act': 'attack', 'target': 'the nearest drunk', 'span': 'take a swing at the nearest drunk'}],
    'We charge the camp.': [{'act': 'attack', 'place': 'the camp', 'span': 'We charge the camp'}],
    'Attack the watchman.': [{'act': 'attack', 'target': 'the watchman', 'span': 'Attack the watchman'}],
    'Start swinging.': [{'act': 'attack', 'span': 'Start swinging.'}],
    'I attack the thug.': [{'act': 'attack', 'target': 'the thug', 'span': 'attack the thug'}],
    'I shoot the thug again.': [{'act': 'attack', 'target': 'the thug', 'span': 'shoot the thug again'}],
    'I attack Bob.': [{'act': 'attack', 'target': 'Bob', 'span': 'attack Bob'}],
    'I punch the bruiser in the face.': [{'act': 'attack', 'target': 'the bruiser', 'span': 'punch the bruiser in the face'}],
    'I keep hitting him.': [{'act': 'attack', 'target': 'him', 'span': 'keep hitting him'}],
    'I attack it': [{'act': 'attack', 'target': 'it', 'span': 'attack it'}],
    'i strike him one final time to put him out of his misery': [{'act': 'attack', 'target': 'him', 'span': 'i strike him one final time to put him out of his misery'}],
    'I continue my rampage.': [{'act': 'attack', 'span': 'continue my rampage'}],
    'I attack someone in the crowd.': [{'act': 'attack', 'target': 'someone', 'place': 'the crowd', 'span': 'attack someone in the crowd'}],
}


def reading(line: str) -> dict:
    """The frame for a recorded line, as `interpret.interpret` returns it."""
    return {"question": line.rstrip().endswith("?"), "claims": [],
            "actions": [dict(a) for a in READINGS[line]]}


def everyone(span, words, people):
    """A stand-in for `interpret.confirm_victims` that answers what the live question
    answered for "the closest person", a rampage and "someone" (14 of 14 probes,
    2026-10-09): every person here."""
    return [ref for ref, _ in people]


def nobody(span, words, people):
    """…and what it answered for "the biggest bruiser in the room" with no bruiser here."""
    return []


def through_the_reading(raw, line, scene, *, ask=None, frame=None):
    """What a turn does with the player's blow: the table, the victim, the refusal, then
    `inject_fight` on the plan. Returns (plan, refusal text)."""
    from gm import acts_to_ops, judgement

    frame = frame if frame is not None else reading(line)
    rows = acts_to_ops.table(frame, scene, sentence=line)
    acts_to_ops.victims(rows, frame, scene, ask=ask)
    stop = acts_to_ops.refusal(rows)
    out = judgement.inject_fight(list(raw), line, scene, rows=rows, frame=frame)
    return out, stop
