"""Gold beats for the read-back's `unseen` question (gm/beat_verify.py, `unseen_messages`).

The question asks which sentences show somebody who cannot see the player looking at them,
aiming at them or striking at them. It shipped in feat/hidden-state on three live gemma
turns and never fired in play, so nothing measured it. These are hand-labelled passages,
written for this measurement (none is a recorded beat and none is a demonstration of the
prompt's), half that show the defect and half that do not — the clean half deliberately
close to it: a blind swing at empty air, a look at somebody else, a search, a pass within
a pace of the player, a sentence that says the eyes do NOT find them.

Each beat: `unseen` the refs the engine says cannot see the player; `flag` the sentences a
right reading reports, as (ref, a phrase of that sentence); `opt` sentences that may be
reported or not without being scored either way (an arc "whistles past your ear" with no
actor in the sentence).
"""
from __future__ import annotations

PEOPLE = (("pc", "Kesst Vayr", "you", True), ("c1", "the thug", "thug"),
          ("c2", "Mother Vell", "innkeeper"), ("c3", "the gate guard", "guard"))

BEATS = [
    {"id": "u01", "unseen": ("c1",),
     "text": "The thug swings his sap in a wide arc aimed at your head. It whistles past "
             "your ear and cracks against the beam.",
     "flag": [("c1", "aimed at your head")], "opt": [("c1", "whistles past your ear")]},
    {"id": "u02", "unseen": ("c1",),
     "text": "The thug turns a slow circle in the middle of the room, listening. He sniffs "
             "the air and mutters a curse under his breath.",
     "flag": []},
    {"id": "u03", "unseen": ("c3",),
     "text": "The gate guard levels his spear at your chest and barks a challenge into the "
             "rain.",
     "flag": [("c3", "levels his spear at your chest")]},
    {"id": "u04", "unseen": ("c3",),
     "text": "The gate guard squints into the rain, his spear lowered. Somewhere behind the "
             "wall a dog barks twice and falls quiet.",
     "flag": []},
    {"id": "u05", "unseen": ("c2",),
     "text": "Mother Vell looks straight at you and asks what you will be drinking tonight.",
     "flag": [("c2", "looks straight at you")]},
    {"id": "u06", "unseen": ("c2",),
     "text": "Mother Vell wipes down the bar, humming an old tune. She glances toward the "
             "door as it creaks on its hinges.",
     "flag": []},
    {"id": "u07", "unseen": ("c1",),
     "text": "The thug swings blindly at the empty air beside the barrels and finds nothing "
             "but splinters.",
     "flag": []},
    {"id": "u08", "unseen": ("c1",),
     "text": "The thug grabs for your collar with one meaty hand, fingers closing on cloth.",
     "flag": [("c1", "grabs for your collar")]},
    {"id": "u09", "unseen": ("c1", "c3"),
     "text": "The thug glares at the gate guard and spits on the cobbles. The guard "
             "pretends not to notice and studies the road.",
     "flag": []},
    {"id": "u10", "unseen": ("c1", "c3"),
     "text": "The gate guard calls out into the dark, asking who is there. The thug, "
             "though, stares right at you and grins.",
     "flag": [("c1", "stares right at you")]},
    {"id": "u11", "unseen": ("c1",),
     "text": "Rain hammers the roof. You hold your breath as the thug's boots scrape past, a "
             "pace from where you stand, and on toward the stairs.",
     "flag": []},
    {"id": "u12", "unseen": ("c1",),
     "text": "The thug meets your eyes for a heartbeat, then charges across the room at you.",
     "flag": [("c1", "meets your eyes")]},
    {"id": "u13", "unseen": ("c1",),
     "text": "The thug jabs his cudgel into the shadows where he guesses someone might be "
             "hiding, and strikes only stone.",
     "flag": []},
    {"id": "u14", "unseen": ("c2",),
     "text": "Mother Vell turns to you and smiles, a fresh tankard already in her hand.",
     "flag": [("c2", "turns to you and smiles")]},
    {"id": "u15", "unseen": ("c2",),
     "text": "Mother Vell calls toward the kitchen for more bread, never once looking your "
             "way.",
     "flag": []},
    {"id": "u16", "unseen": ("c3",),
     "text": "The gate guard shoots a crossbow bolt at you, and it thuds into the post "
             "beside your shoulder.",
     "flag": [("c3", "shoots a crossbow bolt at you")]},
    {"id": "u17", "unseen": ("c3",),
     "text": "The gate guard looses a crossbow bolt into the dark at nothing in particular, "
             "and swears when it skitters off the wall.",
     "flag": []},
    {"id": "u18", "unseen": ("c1",),
     "text": "The thug follows you with his eyes as you slip along the wall toward the "
             "back door.",
     "flag": [("c1", "follows you with his eyes")]},
    {"id": "u19", "unseen": ("c1",),
     "text": "You slip along the wall toward the back door. Behind you, the thug kicks over "
             "a stool in frustration.",
     "flag": []},
    {"id": "u20", "unseen": ("c1",),
     "text": "The thug growls that he knows someone is here, and swings his sap straight "
             "at you.",
     "flag": [("c1", "swings his sap straight at you")]},
    # Harder, added after the first twenty scored 10/10 and 0/10 on both runs: the defect
    # said without "at you", and the clean case said with "you" in it.
    {"id": "u21", "unseen": ("c1",),
     "text": "The thug's gaze sweeps the room and slides past you without stopping.",
     "flag": []},
    {"id": "u22", "unseen": ("c1",),
     "text": "The thug steps toward you, cudgel ready, and his free hand reaches for your "
             "sleeve.",
     "flag": [("c1", "steps toward you")]},
    {"id": "u23", "unseen": ("c2",),
     "text": "Mother Vell sets a tankard down where you stood a moment ago and frowns at "
             "the empty stool.",
     "flag": []},
    {"id": "u24", "unseen": ("c3",),
     "text": "The gate guard's crossbow tracks you as you edge along the parapet.",
     "flag": [("c3", "crossbow tracks you")]},
    {"id": "u25", "unseen": ("c1",),
     "text": "The thug shouts toward the far corner for whoever is there to come out, and "
             "waits with his back to you.",
     "flag": []},
    {"id": "u26", "unseen": ("c2",),
     "text": "Mother Vell's eyes narrow at you over the rim of her cup.",
     "flag": [("c2", "eyes narrow at you")]},
    {"id": "u27", "unseen": ("c3",),
     "text": "The gate guard tells you to move along and stop loitering by the gate.",
     "flag": [("c3", "tells you to move along")]},
    {"id": "u28", "unseen": ("c1", "c2"),
     "text": "Mother Vell hands the thug a lantern. He holds it high and peers into every "
             "corner of the cellar but yours.",
     "flag": []},
]


def facts(beat):
    """The beat's engine side, as `beat_verify.facts_from` builds it for a hidden player."""
    from gm import beat_verify as bv

    people = tuple(bv.Person(ref=p[0], name=p[1], what=p[2],
                             pc=bool(p[3]) if len(p) > 3 else False) for p in PEOPLE)
    return bv.Facts(start="", end="", places=(), people=people,
                    unseen=tuple(beat["unseen"]))
