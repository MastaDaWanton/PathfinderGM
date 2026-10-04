"""The beat-reader bench's labels (docs/beat-reader.md): finished beats, the scene they were
read in, and what a careful reader would say of them — by hand, 2026-10-03.

Three sources:

  * ``kesst-*`` — the owner's two saves of 2026-10-03 (Kesst Vayr in Zhilvarnia, the
    Pangrella fixture world), the live copies whose later beats hold the smith, the forge
    and the large man. SHORT EXCERPTS only, cut to the sentences a label needs (the saves
    are the owner's and are never committed; tests here quote them the same way);
  * ``bobby-*`` — the Bobby corpus (tests/replays/bobby-2026-09-28). The corpus is kept out
    of the repository (owner's ruling, 2026-09-28), so these cases carry no text: the
    bench reads the beat from the corpus on disk and skips them when it is absent;
  * ``replay-*`` — `narrator_audit.py --record` sessions already committed under
    tests/replay (fixture worlds, every raw reply), the text lifted of its speaker tags.

Each case:

  ``cast``   — who the reader is shown: (ref, name, what), "pc" for the player's character.
               The people present when the reader runs: after the plan, before the
               aftermath — so somebody the plan introduced this turn is listed.
  ``vague``  — refs present with no gender and they/them: the page may settle them (Q26).
  ``town``/``here`` — this settlement's places (`Engine.places()` + open ground), and here.
  ``said``   — the prose call's own speaker tags: (ref, first words of the line).
  ``people`` — mention phrase (as `mentions.find` marks it; "#2" for the second of the same
               words) -> answer. "cN" | "pc" | "nobody" | "new:K" (newcomer K); "a|b" when
               more than one answer is right; "*" when anything is.
  ``new``    — newcomer K -> {"head": a word their description must hold, "where": "here"
               | "elsewhere" | "*", "optional": True when making nobody is also right}.
  ``lines``  — first words of a quoted line -> who says it: "cN" | "you" | "new:K" | ...
  ``places`` — places a speaker named that the town does not have: {"words": a word the
               reader's name must hold, "kind": the kind or "*", "near": a town place name |
               "here" | "none" | "*", "optional"}.
  ``placed`` — people a speaker put at one of the town's places: {"words", "at", "optional"}.
  ``pronouns`` — vague ref -> "he" | "she": what the page settles. A vague ref not listed
               must be left unsettled.
  ``names``  — ref -> the name that should be TAKEN (after the checks: on the page, nobody
               else's, not a people of the world). Scored only where the case has the key.
"""
from __future__ import annotations

# Zhilvarnia, as the engine has it (`Engine.places()` + `open_ground()`, read off a copy of
# the save on 2026-10-03) — the floors and undercrofts left out: they are rooms of the
# places listed, and no speaker in these beats names one.
ZHIL = ["the great square", "the north crossing", "the east crossing", "the south crossing",
        "the west crossing", "the gate", "the guardhouse", "the barracks", "the well",
        "the market", "the guildhall", "the mine head", "the cathedral", "the warrens",
        "the bathhouse", "the counting house", "the bridge", "the granary",
        "the customs house", "the graveyard", "the tavern", "the merchants row",
        "the docks", "the outskirts", "the road to Xylorvotha", "the shore", "the approach",
        "the heart of it", "the edge"]
ZHIL_LATER = ZHIL + ["the storage area"]
ZHIL_SMITHY = ZHIL_LATER + ["the smithy"]

KESST = ("pc", "Kesst Vayr", "pc")
SERVANT = ("c1", "the servant carrying jugs two at a time", "guildhand")
MASTER = ("c2", "the master of the market", "merchant")
KEEPER = ("c3", "the keeper of the general store", "merchant")
COAT = ("c4", "man in the heavy coat", "guildhand")

CASES: list[dict] = [
    # --- the owner's saves, 2026-10-03 -------------------------------------------------
    {
        "id": "kesst-02-man-on-the-stool",
        "why": "item 15: six beats of 'the man' tagged to the servant carrying jugs",
        "cast": [KESST, SERVANT, MASTER, KEEPER], "vague": ["c2", "c3"],
        "town": ZHIL, "here": "the market",
        "text": ("Behind him, the tavern patrons have stopped their drinking; the clatter of "
                 "mugs and the low hum of conversation have died away as if someone had cut "
                 "a rope. The man on the stool blinks, his eyes darting to the door, then to "
                 "the man at the bar, and finally back to you. He doesn't know if you are a "
                 "madwoman, a threat, or a joke. He finds his voice, but it is cracked. 'What "
                 "is going on?' he repeats, though this time it is a question."),
        "said": [("c1", "What is going on?")],
        "people": {"The man": "new:stool", "the man": "new:bar|c2|c3"},
        "new": {"stool": {"head": "man", "where": "here"},
                "bar": {"head": "man", "where": "here", "optional": True}},
        "lines": {"What is going on": "new:stool"},
    },
    {
        "id": "kesst-04-a-quoted-player-line",
        "why": "a quoted player line became a person called `say \"just trying…\"` (c4)",
        "cast": [KESST, SERVANT, MASTER, KEEPER,
                 ("c4", "man on the stool", "guildhand")], "vague": ["c2", "c3"],
        "town": ZHIL, "here": "the market",
        "text": ("The man's tense posture relaxes, the sharp edge of his hostility blunted by "
                 "the sheer, bewildered absurdity of your tone. He glances toward the nearby "
                 "stalls where other figures remain seated, then looks back at you. "
                 "'Conversation? In a place like this?' he mutters, his fists finally "
                 "beginning to unclench. He simply looks like a man trying to figure out if he "
                 "has just witnessed a very strange joke. The say \"just trying to start a "
                 "conversation and see what is happening here.\" is a Korvu: grey-streaked and "
                 "unbothered by it; a coat too heavy for the weather, worn anyway. You speak "
                 "clearly, 'Just trying to start a conversation and see what is happening "
                 "here.' What do you do?"),
        "said": [("c1", "Conversation? In a place like this?")],
        "people": {"The man's": "c4", "a man": "c4|nobody"},
        "new": {},
        "lines": {"Conversation? In a place": "c4", "just trying to start": "you",
                  "Just trying to start": "you"},
    },
    {
        "id": "kesst-08-he-repeats-your-words",
        "why": "the man repeats the player's words back: his line, not the player's",
        "cast": [KESST, SERVANT, ("c4", "man on the stool", "guildhand")], "vague": [],
        "town": ZHIL, "here": "the market",
        "text": ("The man’s heavy, defensive stance wavers. The tavern patrons, who had begun "
                 "to tense at the sound of a shout, now simply watch with curious, guarded "
                 "expressions. The man blinks, his fist still half-curled. 'Conversation?' he "
                 "mutters, his voice rough. 'In a place like this? You speak as if you expect "
                 "someone to have an answer.' He glances toward the other patrons, then back "
                 "to you. 'Just trying to start a conversation and see what is happening "
                 "here.' he repeats, though his words are more of a challenge than an "
                 "observation."),
        "said": [("c1", "Conversation?"), ("c1", "In a place like this?"),
                 ("c1", "Just trying to start")],
        "people": {"The man’s": "c4", "The man": "c4"},
        "new": {},
        "lines": {"Conversation?": "c4", "In a place like this": "c4",
                  "Just trying to start": "c4"},
    },
    {
        "id": "kesst-10-folks-at-the-docks",
        "why": "the docks man spoke of the warehouse; nothing recorded it",
        "cast": [KESST, SERVANT, ("c4", "man on the stool", "guildhand")], "vague": [],
        "town": ZHIL, "here": "the market",
        "text": ("The man's fist is still trembling slightly, and he looks at you with a "
                 "mixture of suspicion and a strange, weary curiosity. 'You're looking for "
                 "work, then?' He gestures with a jerk of his head toward the door. 'There's a "
                 "few folks at the docks who are desperate for honest hands, and even more at "
                 "the warehouse who don't care much about the honesty as long as the work gets "
                 "done. But you'll find they're harder to deal with than I am.' He sighs. 'If "
                 "you're looking for coin, you'd best find a way to make yourself useful to "
                 "someone who's actually paying it.'"),
        "said": [("c1", "You're looking for work"), ("c1", "There's a few folks"),
                 ("c1", "If you're looking for coin")],
        "people": {"The man's": "c4"},
        "new": {},
        "lines": {"You're looking for work": "c4", "There's a few folks": "c4",
                  "If you're looking for coin": "c4"},
        "places": [{"words": "warehouse", "kind": "warehouses", "near": "*"}],
    },
    {
        "id": "kesst-12-the-master-of-the-docks",
        "why": "a person only spoken of in the narration is a record, not a body",
        "cast": [KESST, SERVANT, ("c4", "man on the stool", "guildhand")], "vague": [],
        "town": ZHIL, "here": "the market",
        "text": ("He leans back against the bar, the wood groaning under his weight. 'The "
                 "docks?' he repeats, the word tasting like grit in his mouth. It's a hard "
                 "place for a newcomer to find a foothold. The master of the docks—a man with "
                 "more coin than sense—is currently looking for someone with the nerve to move "
                 "the shipments from the western warehouses before the tide turns. He gestures "
                 "with a thick, scarred hand toward the door. 'But if you go there and mention "
                 "my name, they'll know you're looking for a job.' He pauses, watching your "
                 "reaction. 'You look like you've traveled a long way to find a way forward.'"),
        "said": [("c1", "The docks?"), ("c1", "But if you go there"),
                 ("c1", "You look like you've traveled")],
        "people": {"a man": "new:master|nobody"},
        "new": {"master": {"head": "master|man", "where": "elsewhere", "optional": True}},
        "lines": {"The docks?": "c4", "But if you go there": "c4",
                  "You look like you've traveled": "c4"},
    },
    {
        "id": "kesst-14-the-man-is-a-korvu",
        "why": "'The man is a Korvu' made a new man, c6, who took c4's lines (live, item 15)",
        "cast": [KESST, SERVANT, COAT, ("c5", "figure", "guildhand")], "vague": ["c5"],
        "town": ZHIL, "here": "the market",
        "text": ("Beside you, the servant (c1) shifts the weight of the heavy jugs, his face a "
                 "mask of indifference. The man in the heavy coat (c4) leans against a timber "
                 "post, his gaze fixed on the ground. The man is a Korvu: weathered well past "
                 "what the years alone would do; a coat too heavy for the weather, worn anyway. "
                 "When you ask who holds the mastership of the docks, the man in the heavy "
                 "coat (c4) lets out a dry, raspy chuckle. He doesn't look at you, but his "
                 "voice carries a weary weight.\n\n\"The docks? That's a different beast "
                 "entirely,\" he mutters, his voice low enough to stay beneath the notice of "
                 "any passing figure. \"The master of the docks isn't a man who cares for the "
                 "petty trade of the stalls. If you're looking for his name, you're looking "
                 "for a ghost.\"\n\nHe finally turns his head, his eyes squinting under the "
                 "brim of his cap. \"You're going to have to decide how you want to play this. "
                 "You can try to find his name through the whispers of the dock-workers.\" "
                 "What do you do?"),
        "said": [],
        "people": {"the servant": "c1", "The man": "c4", "The man#2": "c4", "the man": "c4"},
        "new": {},
        "lines": {"The docks? That's": "c4", "The master of the docks": "c4",
                  "You're going to have": "c4"},
    },
    {
        "id": "kesst-16-the-man-with-the-jugs",
        "why": "a person present described by other words than his name",
        "cast": [KESST, SERVANT, COAT], "vague": [],
        "town": ZHIL, "here": "the market",
        "text": ("The man in the heavy coat shifts his weight, his eyes tracking your every "
                 "movement. Beside him, the man with the jugs remains steady, though his hands "
                 "tighten slightly on the handles as you announce your destination. The "
                 "mention of the docks brings a ripple of silence to the immediate circle. "
                 "The man in the heavy coat leans in, his voice dropping to a conspiratorial "
                 "rasp. 'The docks? That's a different beast entirely,' he mutters. But a word "
                 "of warning: the dock-masters don't like locals walking with purpose."),
        "said": [("c4", "The docks? That's a different beast")],
        "people": {"The man": "c4", "the man": "c1", "The man#2": "c4"},
        "new": {},
        "lines": {"The docks? That's": "c4"},
    },
    {
        "id": "kesst-18-the-merchant-moves-on",
        "why": "a merchant who walked a pace beside and moved on was made a body (c8)",
        "cast": [KESST], "vague": [],
        "town": ZHIL, "here": "the docks",
        "text": ("At the east crossing, a merchant with a heavy pack assumes you are a "
                 "customer and walks a pace beside you, but he soon tires of your silence and "
                 "moves on. The merchant with a heavy pack is a Korvu: somewhere in the middle "
                 "of life; a scar through one eyebrow. Now, the air is thick with the smell of "
                 "brine and drying timber. The docks are a forest of masts. Amidst the "
                 "shouting of sailors and the groaning of the cranes, a man is struggling with "
                 "a heavy, sodden crate near a stack of hempen rope, his hands bleeding where "
                 "the wood has splintered. He is cursing the weight of it and the slippery "
                 "footing of the quay. What do you do?"),
        "said": [],
        "people": {"a merchant": "new:merchant", "The merchant": "new:merchant",
                   "a man": "new:crate"},
        "new": {"merchant": {"head": "merchant", "where": "elsewhere"},
                "crate": {"head": "man", "where": "here"}},
        "lines": {},
    },
    {
        "id": "kesst-20-bless-you-girl",
        "why": "the prose tagged the struggling man's lines to the servant, who was not there",
        "cast": [KESST, ("c9", "man struggling with a heavy, sodden crate", "guildhand")],
        "away": [("c7", "the harbourmaster", "")],
        "vague": [], "town": ZHIL, "here": "the docks",
        "text": ("A wet, hacking cough echoes across the quay. The man’s face, streaked with "
                 "grime and a desperate hope, twists as he looks at your offer. He gestures "
                 "with a blood-stained hand toward the massive wooden crate. 'Bless you, girl. "
                 "It's a cursed thing, weighing more than it should,' he grunts, his voice "
                 "raspy from the salt air. The man's knuckles turn white against the wood as "
                 "he pulls closer. 'Steady now,' he wheezes, his eyes darting toward the "
                 "harbor master's office just out of sight."),
        "said": [],
        "people": {"The man’s": "c9", "The man's": "c9", "the harbor master's": "*"},
        "new": {},
        "lines": {"Bless you, girl": "c9", "Steady now": "c9"},
        "places": [{"words": "office", "kind": "*", "near": "*", "optional": True}],
    },
    {
        "id": "kesst-22-the-lone-laborer",
        "why": "one newcomer shown; the people left behind are not made here",
        "cast": [KESST], "vague": [], "town": ZHIL_LATER, "here": "the storage area",
        "away": [("c8", "merchant with a heavy pack", ""),
                 ("c9", "man struggling with a heavy, sodden crate", "")],
        "text": ("You step into the heavy pack and haul the weight onto your own shoulders, "
                 "the rough grain of the leather biting into your collar as the merchant's eyes "
                 "widen and his mouth hangs open. You turn and walk away, leaving him and the "
                 "man behind him as the docks fall away. You pass the line of merchant stalls "
                 "and the heavy gates of the inner courtyard, moving into the district of the "
                 "warehouses. Here, the work is heavy and the noise is the rhythmic thud of "
                 "crates hitting floorboards and the low grumble of teamsters. A few paces "
                 "ahead, a lone laborer is struggling with a stubborn, oversized crate at the "
                 "base of a loading ramp, his knuckles white where they grip the wood."),
        "said": [],
        "people": {"the merchant's": "c8|*", "the man": "c9|*",
                   "a lone laborer": "new:laborer"},
        "new": {"laborer": {"head": "laborer", "where": "here"}},
        "lines": {},
    },
    {
        "id": "kesst-24-a-man-named-korvu",
        "why": "'a man named Korvu' renamed the laborer after a people of the world (item 14)",
        "cast": [KESST, ("c11", "lone laborer", "guildhand")], "vague": [],
        "town": ZHIL_LATER, "here": "the storage area",
        "text": ("The laborer—a man named Korvu, his face etched with the deep lines of a life "
                 "spent under heavy loads—stops his struggle and looks up. 'That's a heavy one "
                 "for a single back,' he says, wiping his hands on a tattered loincloth. He "
                 "gestures with a calloused hand toward the very end of the loading bay. 'The "
                 "foreman is in the back office, but he's a hard man to catch when he's "
                 "counting. If you're looking to offload that beast, you'd best get it onto "
                 "the ramp before the evening shift change.' He leans against a nearby pillar. "
                 "'The main gate's been jammed since the morning tide, so there's no easy way "
                 "out once you move past the next turn.'"),
        "said": [("c11", "That's a heavy one"), ("c11", "The foreman is in the back office"),
                 ("c11", "The main gate's been jammed")],
        "people": {"The laborer": "c11", "a man": "c11"},
        "new": {},
        "names": {},
        "lines": {"That's a heavy one": "c11", "The foreman is": "c11",
                  "The main gate's": "c11"},
        "places": [{"words": "office", "kind": "*", "near": "here|none", "optional": True}],
    },
    {
        "id": "kesst-28-a-man-in-the-counting-house",
        "why": "a person a speaker puts at a real place of the town is heard of there",
        "cast": [KESST, ("c11", "lone laborer", "guildhand")], "vague": [],
        "town": ZHIL_LATER, "here": "the storage area",
        "text": ("Korvu watches you for a long moment. The mention of coin makes him let out a "
                 "short, dry chuckle that turns into a cough. 'Sell it to me?' he says, his "
                 "voice a low rasp. 'I'm just a man with a shovel and a heavy list of debts. "
                 "If I bought it, I'd have to find a way to hide it from the overseer, and he's "
                 "a man who doesn't like surprises.' He leans closer, the smell of old sweat "
                 "and dry earth clinging to him. 'But,' he adds, his voice dropping even lower, "
                 "'I know a man in the counting house.' What do you do?"),
        "said": [("c11", "Sell it to me?"), ("c11", "I'm just a man with a shovel"),
                 ("c11", "But,")],
        "people": {},
        "new": {},
        "lines": {"Sell it to me": "c11", "I'm just a man": "c11", "But": "c11",
                  "I know a man": "c11"},
        "placed": [{"words": "man", "at": "the counting house"}],
    },
    {
        "id": "kesst-30-a-clerk-a-man-with-a-weary-face",
        "why": "the counting house's own keeper described, recorded as a stranger (p9)",
        "cast": [KESST, ("c12", "the clerk of the counting house", "moneylender")],
        "vague": [], "town": ZHIL_LATER, "here": "the counting house",
        "text": ("You pass under the arch of the south crossing and into the counting house. "
                 "The air here is dry and smells of old paper and dust. The men of the "
                 "counting house move with deliberate, measured steps, and the only sound is "
                 "the scratching of quills. A clerk, a man with a weary face, is currently "
                 "weighing a sack of grain on a heavy iron scale nearby. What do you do?"),
        "said": [],
        "people": {"A clerk": "c12", "a man": "c12"},
        "new": {},
        "lines": {},
    },
    {
        "id": "kesst-32-you-say",
        "why": "the player's own words in the beat were booked as the clerk's (item 15)",
        "cast": [KESST, ("c12", "the clerk of the counting house", "moneylender")],
        "vague": [], "town": ZHIL_LATER, "here": "the counting house",
        "text": ("You catch the clerk's eye, tilting your head just enough as you gesture to "
                 "the heavy crate. \"A piece of work like this,\" you say, your voice dropping "
                 "into a sultry lilt, \"deserves a bit more respect than just being weighed. "
                 "It’s a rare find, and I suspect you have a very keen eye for what is truly "
                 "valuable.\" You let the silence stretch for a heartbeat, watching him. The "
                 "clerk stops his work, the scale settling, and he looks at you—not just as a "
                 "customer, but as a woman who knows exactly how to command a room."),
        "said": [],
        "people": {"the clerk's": "c12", "The clerk": "c12", "a woman": "pc"},
        "new": {},
        "lines": {"A piece of work": "you", "deserves a bit more": "you"},
    },
    {
        "id": "kesst-36-quietly",
        "why": "a plain beat: one speaker, every line his, nobody new",
        "cast": [KESST, ("c12", "the clerk of the counting house", "moneylender")],
        "vague": [], "town": ZHIL_LATER, "here": "the counting house",
        "text": ("The clerk’s eyes drop to the floor for a heartbeat before he looks back up. "
                 "\"Quietly is a high-priced commodity in this city,\" he whispers back. \"The "
                 "guild likes their paperwork orderly, and the streets prefer their problems... "
                 "settled.\" He reaches out and places a large, calloused hand on the edge of "
                 "the crate. \"So, we have an understanding?\" What do you do?"),
        "said": [("c12", "Quietly is a high-priced"), ("c12", "The guild likes")],
        "people": {"The clerk’s": "c12"},
        "new": {},
        "lines": {"Quietly is": "c12", "The guild likes": "c12",
                  "So, we have an understanding": "c12"},
    },
    {
        "id": "kesst-40-past-the-smithy",
        "why": "'past the smithy': nothing wrote the smithy down; the planner founded it blind",
        "cast": [KESST, ("c12", "the clerk of the counting house", "moneylender")],
        "vague": [], "town": ZHIL_LATER, "here": "the counting house",
        "text": ("He looks toward the back of the room where the shadows are thickest. 'One "
                 "more thing,' he adds, his voice returning to its normal, weary rasp. 'The men "
                 "in the back will be moving the haul to the vault tonight. They don't like to "
                 "be disturbed, and they certainly don't like to be seen.' He leans back, the "
                 "transaction over. 'I suggest you make your exit through the side door, past "
                 "the smithy. It leads straight to the main thoroughfare.' What do you do?"),
        "said": [("c12", "One more thing"), ("c12", "The men in the back"),
                 ("c12", "I suggest you make your exit")],
        "people": {},
        "new": {},
        "lines": {"One more thing": "c12", "The men in the back": "c12",
                  "I suggest you": "c12"},
        "places": [{"words": "smithy", "kind": "smithy", "near": "here"},
                   {"words": "vault", "kind": "*", "near": "*", "optional": True},
                   {"words": "thoroughfare", "kind": "*", "near": "*", "optional": True}],
    },
    {
        "id": "kesst-44-a-pair-of-smiths",
        "why": "the smith is new and shown; a pair working is two, one of them the smith",
        "cast": [KESST], "vague": [], "town": ZHIL_SMITHY, "here": "the smithy",
        "away": [("c12", "the clerk of the counting house", "")],
        "text": ("The heavy door of the ledger-room clicks shut behind you, muffling the "
                 "clerk's unfinished sentence as you step into the heat of the forge. You are "
                 "inside the smithy now. Near the main anvil, a pair of smiths are working in "
                 "tandem—one holding a heavy piece of bronze while the other strikes it with a "
                 "heavy mallet, their faces masked by sweat and soot. The smith is a Korvu: "
                 "young enough that the face has not settled yet; hair worn in a single thick "
                 "braid down the back."),
        "said": [],
        "people": {"the clerk's": "*", "The smith": "new:smith"},
        "new": {"smith": {"head": "smith", "where": "here"}},
        "lines": {},
    },
    {
        "id": "kesst-52-the-smith-korvu",
        "why": "'the smith, Korvu' — Korvu is a people of the world, not his name (item 14)",
        "cast": [KESST, ("c13", "the smith", "guildhand")], "vague": ["c13"],
        "town": ZHIL_SMITHY, "here": "the smithy",
        "text": ("The coins clink as they find their place in your purse, a small, heavy "
                 "sound in the cavernous space of the forge. Beside you, the smith, Korvu, "
                 "reaches out with a hand calloused into leather and takes the crate from you. "
                 "He doesn't say a word of thanks, but he grips the handles with a steady, "
                 "practiced hold."),
        "said": [],
        "people": {"the smith": "c13"},
        "new": {},
        "lines": {},
        "names": {},
        "pronouns": {"c13": "he"},
    },
    {
        "id": "synthetic-the-sergeant-gives-his-name",
        "why": "a name given in play is the panel's name from then on (2026-09-18, 'call me "
               "Kael'); written here in the shape of Sam's sergeant (2026-09-30), not "
               "copied from a save",
        "cast": [KESST, ("c5", "the sergeant of the watch", "watchman")], "vague": [],
        "town": ZHIL, "here": "the gate",
        "text": ("The sergeant studies you a moment longer, then shrugs. 'Caspian Tidestone,' "
                 "he says. 'Sergeant of the second watch, for my sins.' He jerks his chin at "
                 "the gate behind him. 'Now move along before the carts back up.'"),
        "said": [("c5", "Caspian Tidestone")],
        "people": {"The sergeant": "c5"},
        "new": {},
        "lines": {"Caspian Tidestone": "c5", "Sergeant of the second": "c5",
                  "Now move along": "c5"},
        "names": {"c5": "Caspian Tidestone"},
    },
    {
        "id": "kesst-60-a-man-enters",
        "why": "a man who enters at first light: made c14 live; he may be the smith",
        "cast": [KESST, ("c13", "the smith", "guildhand")], "vague": ["c13"],
        "town": ZHIL_SMITHY, "here": "the smithy",
        "text": ("The crate sits before you, a solid weight in the center of the room. When "
                 "the first real light breaks, the heavy door creaks open. A man enters, his "
                 "face still weary from the night, and he stops before the workbench, his eyes "
                 "falling on the crate. He doesn't speak at first; he just puts his club down "
                 "with a dull thud. He moves toward the crate, his hands—scarred and steady—"
                 "reaching for the lid. What do you do?"),
        "said": [],
        "people": {"A man": "new:enters|c13"},
        "new": {"enters": {"head": "man", "where": "here", "optional": True}},
        "lines": {},
        "pronouns": {"c13": "he|*"},
    },
    {
        "id": "kesst-62-he-is-a-large-man",
        "why": "'He is a large man' made a second smith (c15) who joined the conversation",
        "cast": [KESST, ("c13", "the smith", "guildhand"), ("c14", "man", "guildhand")],
        "vague": [], "town": ZHIL_SMITHY, "here": "the smithy",
        "text": ("The man at the workbench—the smith—does not look up from the crate as you "
                 "speak. He is a large man, his hands calloused and stained with the grey of "
                 "ash. He reaches out, his fingers hooking under the edge of the lid. He "
                 "pauses, his muscles tensed, waiting to see what he has just unearthed. "
                 "'Well,' he grunts, his voice like grinding stones. 'You're the first one to "
                 "bring me a haul like this in three moons. Let's see what's inside before we "
                 "talk of coin.' He reaches for a heavy iron pry-bar. What do you do?"),
        "said": [("c1", "You're the first one")],
        "people": {"The man": "c13|c14", "the smith": "c13", "a large man": "c13|c14"},
        "new": {},
        "lines": {"Well": "c13|c14", "You're the first one": "c13|c14"},
    },
    {
        "id": "kesst-64-by-the-forge",
        "why": "the smith's lines, with the duplicate gone",
        "cast": [KESST, ("c13", "the smith", "guildhand"), ("c14", "man", "guildhand")],
        "vague": [], "town": ZHIL_SMITHY, "here": "the smithy",
        "text": ("The smith's grip on the pry-bar tightens as he hears your words, and he "
                 "gives a short, sharp nod. He jams the iron bar into the seam of the lid and "
                 "heaves. The smith stares at them, his eyes widening, the pry-bar still "
                 "gripped in his shaking hands. He looks from the shards to you, his face a "
                 "mask of stunned silence. 'By the Forge...' he whispers. 'What in the hell "
                 "did you bring me?'"),
        "said": [("c13", "By the Forge"), ("c13", "What in the hell")],
        "people": {"The smith's": "c13", "The smith": "c13"},
        "new": {},
        "lines": {"By the Forge": "c13", "What in the hell": "c13"},
    },
    {
        "id": "kesst-66-the-one-with-the-clouded-eye",
        "why": "the man beside the smith is the man already here, by other words",
        "cast": [KESST, ("c13", "the smith", "guildhand"), ("c14", "man with a club",
                                                             "guildhand")],
        "vague": [], "town": ZHIL_SMITHY, "here": "the smithy",
        "text": ("The smith's hands are still shaking from the impact of the lid hitting the "
                 "wall. The man beside him, the one with the clouded eye, has stepped back, "
                 "his hand gripping the hilt of the club at his belt. The silence in the room "
                 "is heavy, broken only by the distant hammering of another smith working on a "
                 "piece of iron down the lane. The smith looks at the shards, then back at "
                 "you. 'You heard him,' he says, his voice cracking slightly. 'If you're "
                 "handing this over, you're handing over the rights to it. Every scrap.'"),
        "said": [("c13", "You heard him"), ("c13", "If you're handing this over")],
        "people": {"The smith's": "c13", "The man": "c14", "The smith": "c13"},
        "new": {},
        "lines": {"You heard him": "c13", "If you're handing": "c13"},
    },
    {
        "id": "kesst-68-get-the-leather",
        "why": "a line said to somebody else here, not to the player",
        "cast": [KESST, ("c13", "the smith", "guildhand"), ("c14", "man with a club",
                                                             "guildhand")],
        "vague": [], "town": ZHIL_SMITHY, "here": "the smithy",
        "text": ("The smith reaches out, his taloned fingers trembling as they hover just "
                 "inches from the gray shards. He looks back at you, and a grim, knowing smile "
                 "pulls at the scarred skin of his face. 'Then it is settled,' he says. He "
                 "turns his head toward the man with the clouded eye, who is still watching "
                 "the shards with a fearful intensity. 'Get the leather. We need to wrap these "
                 "in lead-lined hide before the humming starts to crack the windows.' He looks "
                 "back at you, the deal concluded. 'You'll have your payment, but I'd advise "
                 "you to find a very sturdy lock for your purse once you leave.'"),
        "said": [("c13", "Then it is settled"), ("c13", "Get the leather"),
                 ("c13", "You'll have your payment")],
        "people": {"The smith": "c13", "the man": "c14"},
        "new": {},
        "lines": {"Then it is settled": "c13", "Get the leather": "c13",
                  "You'll have your payment": "c13"},
        "to": {"Get the leather": "c14"},
    },
    {
        "id": "kesst-ld2-20-he-only-cares-for-the-steel",
        "why": "a sharpener only spoken of in a line, by pronoun: nobody is made",
        "cast": [KESST, SERVANT, COAT], "vague": [], "town": ZHIL, "here": "the market",
        "text": ("The heavy fabric of his coat creaks like old timber as he shifts his weight. "
                 "When you ask where a rapier might be sharpened, he doesn't point toward the "
                 "center of the market, but instead gestures toward the far end of the "
                 "promenade where the shadows of the warehouse district begin to stretch.\n\n"
                 "'A blade like that doesn't need a simple whetstone,' he says, his voice a low "
                 "rasp. 'He doesn't care for your business, and he doesn't care for your "
                 "problems. He only cares for the steel. You bring it to him, and he’ll tell "
                 "you if it’s worth keeping.' He looks back at you, his expression hard."),
        "said": [("c4", "A blade like that"), ("c4", "He doesn't care for your business")],
        "people": {},
        "new": {},
        "lines": {"A blade like that": "c4", "He doesn't care": "c4"},
    },
    {
        "id": "kesst-ld2-22-the-forge-of-the-broken-tide",
        "why": "'The Forge of the Broken Tide' + 'the back of the smithy' became two places "
               "with no landmark; the speaker said follow the quay to the wharf (the docks)",
        "cast": [KESST, SERVANT, COAT], "vague": [], "town": ZHIL, "here": "the market",
        "text": ("A dry, rasping grunt escapes the man in the heavy coat—the sound of a person "
                 "who has finished their part in the exchange. He turns his head toward the "
                 "end of the promenade, his gaze drifting toward the distant warehouse "
                 "district. 'The Forge of the Broken Tide,' he says, the name sounding like a "
                 "line pulled from a ledger. 'Follow the main quay until you hit the turn for "
                 "the wharf. He's there every night at this hour, sitting in the back of the "
                 "smithy. He doesn't open for anyone else.' He turns his gaze away from you, "
                 "looking back toward the market center."),
        "said": [("c4", "The Forge of the Broken Tide"), ("c4", "Follow the main quay")],
        "people": {"the man": "c4", "a person": "c4"},
        "new": {},
        "lines": {"The Forge of the Broken Tide": "c4", "Follow the main quay": "c4"},
        "places": [{"words": "forge|smithy", "kind": "smithy", "near": "the docks",
                    "one_of": "forge"}],
    },
    # --- names: the shapes the retired name patterns were tested on (tests/ texts) -------
    {
        "id": "names-the-man-korgath-varn",
        "why": "'The man—Korgath Varn—takes a slow pull of his ale': the panel kept 'man' "
               "(reported 2026-09-24)",
        "cast": [("pc", "Spree", "pc"), ("c8", "man", "guildhand")], "vague": [],
        "town": ZHIL, "here": "the tavern",
        "text": ("The man—Korgath Varn—takes a slow pull of his ale, the mug letting out a "
                 "wet sound as he sets it back down. He watches you over the rim."),
        "said": [],
        "people": {"The man": "c8"},
        "new": {}, "lines": {},
        "names": {"c8": "Korgath Varn"},
    },
    {
        "id": "names-two-men-one-named",
        "why": "the head word 'man' belonged to two unnamed men; the guess took the first",
        "cast": [("pc", "Spree", "pc"), ("c2", "man by the door", "guildhand"),
                 ("c3", "man at the bar", "guildhand")], "vague": [],
        "town": ZHIL, "here": "the tavern",
        "text": ("The man by the door watches the street. At the bar, the man—Korgath "
                 "Varn—takes a slow pull of his ale."),
        "said": [],
        "people": {"The man": "c2", "the man": "c3"},
        "new": {}, "lines": {},
        "names": {"c3": "Korgath Varn"},
    },
    {
        "id": "names-the-tag-decides-whose",
        "why": "'The woman glances at the man. \"Call me Kael,\" he says.' — the role-word "
               "guess gave the woman his name",
        "cast": [("pc", "Kesst Vayr", "pc"), ("c2", "man by the fire", "guildhand"),
                 ("c3", "woman at the counter", "guildhand")], "vague": [],
        "town": ZHIL, "here": "the tavern",
        "text": "The woman glances at the man. 'Call me Kael,' he says.",
        "said": [],
        "people": {"The woman": "c3", "the man": "c2"},
        "new": {}, "lines": {"Call me Kael": "c2"},
        "names": {"c2": "Kael"},
    },
    {
        "id": "names-the-one-who-was-asked",
        "why": "asked her name, the woman in the corner said 'you may call me Gorvothor'; "
               "two women here, and the panel kept the descriptor (2026-09-19)",
        "cast": [("pc", "Kesst Vayr", "pc"), ("c4", "woman in the corner", "guildhand"),
                 ("c5", "woman", "guildhand")], "vague": [],
        "town": ZHIL, "here": "the tavern",
        "text": ("The woman in the corner looks up at your question. 'Names are heavy things "
                 "to carry in a place like this,' she says, her voice a low, resonant grind. "
                 "'But if you must have one, you may call me Gorvothor.'"),
        "said": [],
        "people": {"The woman": "c4"},
        "new": {}, "lines": {"Names are heavy": "c4", "But if you must": "c4"},
        "names": {"c4": "Gorvothor"},
    },
    {
        "id": "names-a-place-in-apposition",
        "why": "a place in apposition is no person's name; nor is a name inside somebody "
               "else's speech",
        "cast": [("pc", "Kesst Vayr", "pc"), ("c2", "Drenn Ironvale", "agent")],
        "vague": ["c2"], "town": ZHIL, "here": "the market",
        "text": ("You cross the market, Vormoor's heart, at a walk. Drenn says, 'the man, "
                 "Korgath Varn, sits in the back corner.'"),
        "said": [("c2", "the man, Korgath Varn")],
        "people": {},
        "new": {}, "lines": {"the man, Korgath": "c2"},
        "names": {},
        "pronouns": {"c2": "*"},
    },
    # --- Sam's save, replayed 2026-10-01 (the seen-people ruling's own cases) ------------
    {
        "id": "sam-a-figure-it-is-a-woman",
        "why": "'a figure … It is a woman' stayed prose; '/cheat the woman …' was refused "
               "and every 'her' went to Quin Nutmeg in another room",
        "cast": [KESST, ("c9", "Gorm Vesper", "barkeep")], "vague": [],
        "town": ZHIL, "here": "the tavern",
        "text": ("The door gives under your hand. At the top of the stairs, a figure is "
                 "silhouetted against the lamplight. It is a woman, her face mostly in "
                 "shadow, and she does not move."),
        "said": [],
        "people": {"a figure": "new:woman", "a woman": "new:woman"},
        "new": {"woman": {"head": "woman", "where": "here"}},
        "lines": {},
    },
    {
        "id": "sam-a-woman-in-the-stories",
        "why": "the player standing, and a woman who exists in stories, were read as a woman "
               "here: a phantom walked on with a Ratfolk face",
        "cast": [KESST, ("c9", "Gorm Vesper", "barkeep")], "vague": [],
        "town": ZHIL, "here": "the tavern",
        "text": ("You have been chasing a ghost, a woman who exists in the stories of the "
                 "desperate. You are still standing before him, and the search for the "
                 "woman has just become a search for why the lie persists."),
        "said": [],
        "people": {"a woman": "nobody|new:story", "the woman": "nobody|new:story"},
        "new": {"story": {"head": "woman", "where": "elsewhere", "optional": True}},
        "lines": {},
    },
    {
        "id": "sam-the-question-you-posed",
        "why": "talk of the woman three streets over recorded her where the party stood",
        "cast": [KESST, ("c9", "Gorm Vesper", "barkeep")], "vague": [],
        "town": ZHIL, "here": "the tavern",
        "text": ("Gorm sets down the cup. The question you posed, concerning the woman "
                 "three streets over, hangs in the air between you."),
        "said": [],
        "people": {"the woman": "new:three"},
        "new": {"three": {"head": "woman", "where": "elsewhere"}},
        "lines": {},
    },
    # --- the Bobby corpus (read from disk; no text here) ------------------------------
    {
        "id": "bobby-01-the-watchman", "corpus": ("bobby-2026-09-28", 1, 0),
        "why": "the watchman's lines; the merchant and fish-seller pass by",
        "cast": [("pc", "Bobby", "pc"), ("c1", "the watchman waving traffic through",
                                         "watchman")],
        "vague": ["c1"], "town": None, "here": "the way in",
        "people": {"The watchman": "c1", "The merchant": "new:merchant|nobody",
                   "the watchman": "c1", "a man": "c1|nobody"},
        "new": {"merchant": {"head": "merchant", "where": "*", "optional": True}},
        "lines": {"The owner's a fool": "c1", "Stalled his wheels": "c1",
                  "You looking for something": "c1"},
        "pronouns": {"c1": "he"},
    },
    {
        "id": "bobby-02-the-girl-in-the-market", "corpus": ("bobby-2026-09-28", 2, 0),
        "why": "'The girl in the market' was written down nowhere (item 5.2)",
        "cast": [("pc", "Bobby", "pc"), ("c1", "the watchman waving traffic through",
                                         "watchman")],
        "vague": ["c1"], "town": None, "here": "the way in",
        "people": {"The watchman": "c1"},
        "new": {},
        "lines": {"Coin and adventure": "c1", "A common enough motive": "c1",
                  "The girl in the market": "c1", "You want the direction": "c1"},
        "placed": [{"words": "girl", "at": "the market"}],
        "places": [{"words": "bunkhouse|tunnel", "kind": "*", "near": "*", "optional": True}],
        "pronouns": {"c1": "he"},
    },
    {
        "id": "bobby-04-a-man-in-a-suit", "corpus": ("bobby-2026-09-28", 4, 0),
        "why": "Drenn on the page as 'a man in a suit'; the suggestions asked about 'her'",
        "cast": [("pc", "Bobby", "pc"), ("c3", "Ashla Ironvale", "merchant"),
                 ("c4", "Drenn Ironvale", "agent")],
        "away": [("c1", "the watchman waving traffic through", ""), ("c2", "girl", "")],
        "vague": ["c3", "c4"], "town": None, "here": "the market",
        "people": {"the girl": "*", "a man": "c4", "the local traders": "nobody",
                   "the crowd": "nobody", "merchants": "nobody"},
        "new": {},
        "lines": {"You! You have the look": "c4", "I am Drenn Ironvale": "c4"},
        "names": {},
        "pronouns": {"c4": "he"},
    },
    {
        "id": "bobby-05-one-of-them-an-older-man", "corpus": ("bobby-2026-09-28", 5, 0),
        "why": "one of the watchmen, described: one of the guards here, or one more",
        "cast": [("pc", "Bobby", "pc"), ("c1", "the watchman waving traffic through",
                                         "watchman"), ("c6", "Guard", "guard"),
                 ("c7", "second Guard", "guard")],
        "vague": ["c1", "c6", "c7"], "town": None, "here": "the way in",
        "people": {"an older man": "c1|c6|c7|new:older"},
        "new": {"older": {"head": "man", "where": "here", "optional": True}},
        "lines": {},
        "pronouns": {"c1": "*", "c6": "*", "c7": "*"},
    },
    {
        "id": "bobby-09-a-man-in-a-stained-leather-jerkin", "corpus": ("bobby-2026-09-28", 9, 0),
        "why": "tagged to `new1`, nobody held it: 3 lines, 0 attributed (item 20.4)",
        "cast": [("pc", "Bobby", "pc")], "vague": [], "town": None, "here": "the approach",
        "said_from_corpus": False,
        "people": {"a man": "new:jerkin"},
        "new": {"jerkin": {"head": "man", "where": "here"}},
        "lines": {"The road to Grotburrow": "new:jerkin", "The trees have ears": "new:jerkin",
                  "You looking for a shortcut": "new:jerkin"},
    },
    {
        "id": "bobby-10-exploring", "corpus": ("bobby-2026-09-28", 10, 0),
        "why": "Drenn's case again: they/them on the sheet, 'he says' on the page (Q26)",
        "cast": [("pc", "Bobby", "pc"), ("c8", "man in a stained leather jerkin",
                                         "guildhand")],
        "vague": ["c8"], "town": None, "here": "the approach",
        "people": {"The man": "c8"},
        "new": {},
        "lines": {"Exploring": "c8", "Most who say": "c8", "If you want to see": "c8",
                  "The further you go": "c8"},
        "pronouns": {"c8": "he"},
    },
    {
        "id": "bobby-12-the-man-with-the-whetstone", "corpus": ("bobby-2026-09-28", 12, 0),
        "why": "two descriptions of one man here; the player's spell words are no line",
        "cast": [("pc", "Bobby", "pc"), ("c8", "man in a stained leather jerkin",
                                         "guildhand")],
        "vague": ["c8"], "town": None, "here": "the approach",
        "people": {"the man": "c8", "The man": "c8", "the man#2": "c8"},
        "new": {},
        "lines": {"burning hands": "you|nobody", "You're making a lot of noise": "c8"},
        "pronouns": {"c8": "he"},
    },
    # --- the recorded narrator-audit sessions (committed, fixture worlds) ----------------
    {
        "id": "replay-strangers-0-the-person-you-find",
        "why": "the person the plan introduced, described as 'the person you find'",
        "cast": [KESST, ("c1", "the lamplighter starting his round", "commoner"),
                 ("c2", "someone who knows the roads north", "commoner")],
        "vague": ["c1", "c2"], "town": ZHIL, "here": "the north crossing",
        "text": ("The person you find is leaning against a stack of grain sacks, their face "
                 "partially obscured by a heavy, salt-stained cap. They have a missing front "
                 "tooth and a voice like gravel over silk. 'Two days,' they grunt, not looking "
                 "at you, but at the muddy rut of the road. 'That's the time you'll need to "
                 "reach the northern gates if you're moving heavy. You're traveling light, I "
                 "see. You'll make it in one, but you'll be lucky to keep your coin.' They spit "
                 "into the dirt. 'The roads are open, but the patrols are thick since the moon "
                 "turned. You want the safe way, or the fast way?' Behind you, the "
                 "lamplighter's warning still hangs in the air, and the crowd continues to "
                 "flow past the gap in the road as if the space in the center were empty. What "
                 "do you do?"),
        "said": [("c2", "Two days"), ("c2", "That's the time"), ("c2", "The roads are open")],
        "people": {"The person": "c2", "the lamplighter's": "c1", "the crowd": "nobody"},
        "new": {},
        "lines": {"Two days": "c2", "That's the time": "c2", "The roads are open": "c2"},
        "places": [{"words": "northern gates", "kind": "*", "near": "*", "optional": True}],
    },
    {
        "id": "replay-strangers-1-the-girl-selling-bread",
        "why": "two speakers in one beat; 'a nearby merchant's tally' made a phantom (c5)",
        "cast": [KESST, ("c1", "the lamplighter starting his round", "commoner"),
                 ("c2", "someone who knows the roads north", "commoner"),
                 ("c3", "somebody selling bread", "commoner")],
        "vague": ["c1", "c2", "c3"], "town": ZHIL, "here": "the north crossing",
        "text": ("The girl selling bread has a way of looking at you that suggests she’s "
                 "already decided exactly how much of a nuisance you are. She holds up a small, "
                 "dense loaf and gestures with a thumb toward a nearby merchant's tally. 'A "
                 "loaf of the common grain is two coppers,' she says, her voice flat and dry. "
                 "'But if you want the white-flour,' she adds, her one good eye narrowing, "
                 "'that’s five.' From the crowd behind you, the lamplighter’s heavy boots "
                 "crunch on the grit of the street. He stops a few paces away. He doesn't look "
                 "at the girl, but his gaze is fixed on the path ahead. 'You heard me, girl,' "
                 "he grunts, his voice a low rumble. 'Keep your eyes on your wares.' He turns "
                 "his head slightly toward you. 'The crowd's split for a reason. Don't go "
                 "poking your nose into the gap.'"),
        "said": [("c3", "A loaf of the common grain"), ("c3", "But if you want"),
                 ("c3", "that’s five"), ("c1", "You heard me, girl"),
                 ("c1", "Keep your eyes"), ("c1", "The crowd's split")],
        "people": {"The girl": "c3", "a nearby merchant's": "nobody|new:tally",
                   "the crowd": "nobody", "the lamplighter’s": "c1", "the girl": "c3"},
        "new": {"tally": {"head": "merchant", "where": "*", "optional": True}},
        "lines": {"A loaf": "c3", "But if you want": "c3", "that’s five": "c3",
                  "You heard me": "c1", "Keep your eyes": "c1", "The crowd's split": "c1"},
        "to": {"You heard me": "c3"},
        "pronouns": {"c1": "he", "c3": "she", "c2": "*"},
    },
    {
        "id": "replay-strangers-2-the-sisters-of-the-veil",
        "why": "places in a line that the town has, and does not have",
        "cast": [KESST, ("c1", "the lamplighter starting his round", "commoner"),
                 ("c3", "somebody selling bread", "commoner"), ("c4", "girl", "commoner")],
        "vague": ["c1", "c3", "c4"], "town": ZHIL, "here": "the north crossing",
        "text": ("He looks at you, his face a map of soot and weary duty. 'A healer, you "
                 "say?' he grunts, his voice like grinding stones. 'If it's a matter of the "
                 "bone-fever or the blood-wasting, the Sisters of the Veil in the lower "
                 "district have a few who still work, though they'll charge a king's ransom in "
                 "coin or favor.' He shifts his weight. 'But if you're looking for someone for "
                 "the shadows, the 'Grayed' ones in the warrens are more... discreet. They "
                 "won't ask for your lineage, only your gold.' He doesn't wait for your "
                 "answer. The girl with the bread watches you, her one good eye tracking the "
                 "lamplighter's movements. What do you do?"),
        "said": [("c1", "A healer, you say?"), ("c1", "If it's a matter"),
                 ("c1", "But if you're looking for someone")],
        "people": {"The girl": "c3|c4", "the lamplighter's": "c1"},
        "new": {},
        "lines": {"A healer": "c1", "If it's a matter": "c1", "But if you're looking": "c1"},
        "places": [{"words": "lower district|sisters", "kind": "*", "near": "*",
                    "optional": True}],
        "placed": [{"words": "grayed", "at": "the warrens", "optional": True}],
        "pronouns": {"c1": "he", "c3": "she|*", "c4": "she|*"},
    },
    {
        "id": "replay-strangers-4-a-passing-carter",
        "why": "the carter the plan introduced, described at length; the woman at the bar",
        "cast": [KESST, ("c7", "Borin Lyraxys", "innkeeper"),
                 ("c8", "sturdy woman with a missing front tooth", "commoner"),
                 ("c9", "passing carter", "commoner")],
        "vague": ["c7", "c8", "c9"], "town": ZHIL, "here": "the tavern",
        "text": ("The man at the bar, a sturdy woman with a missing front tooth, continues her "
                 "methodical work while the crowd hums around you. A man in a stained leather "
                 "harness, a passing carter, maneuvers a laden cart through the muddy churn of "
                 "the street just outside the tavern's door. He looks exhausted, his head "
                 "hanging low as he navigates the turn toward the docks. 'Heading for the "
                 "river_docks,' he calls out, his voice strained from shouting over the wind "
                 "all day. 'Got a load of salt-stone that needs moving before the tide turns.' "
                 "He doesn't wait for a response."),
        "said": [("c9", "Heading for the"), ("c9", "Got a load of salt-stone")],
        "people": {"The man": "c8|c7", "a sturdy woman": "c8|c7", "the crowd": "nobody",
                   "A man": "c9", "a passing carter": "c9"},
        "new": {},
        "lines": {"Heading for the": "c9", "Got a load": "c9"},
        "pronouns": {"c8": "she", "c9": "he", "c7": "*"},
    },
    {
        "id": "replay-strangers-7-a-figure-in-the-shadows",
        "why": "a figure the innkeeper points out: the man in the corner already here",
        "cast": [KESST, ("c8", "sturdy woman with a missing front tooth", "commoner"),
                 ("c11", "man in a shadowed corner", "commoner")],
        "vague": ["c8", "c11"], "town": ZHIL, "here": "the tavern",
        "text": ("The woman with the missing tooth leans in closer, the scent of yeast and old "
                 "spice clinging to her. 'A guide is a heavy thing to ask for,' she says, her "
                 "voice like grinding stones. 'Most who go there for trade don't come back "
                 "with their wits intact.' She gestures with a thick thumb toward the back of "
                 "the room, where a figure sits in the shadows. 'But there is one. They know "
                 "the grass, and they know the ways through it. They are not a man of many "
                 "words, but their feet are steady.' She watches you."),
        "said": [("c8", "A guide is a heavy thing"), ("c8", "Most who go there"),
                 ("c8", "But there is one")],
        "people": {"The woman": "c8", "a figure": "c11|new:guide"},
        "new": {"guide": {"head": "figure|man", "where": "here", "optional": True}},
        "lines": {"A guide": "c8", "Most who go": "c8", "But there is one": "c8"},
        "pronouns": {"c8": "she", "c11": "*"},
    },
    {
        "id": "replay-strangers-8-the-nearby-scriptorium",
        "why": "a place not in the town, named by the woman behind the bar",
        "cast": [KESST, ("c8", "sturdy woman with a missing front tooth", "commoner")],
        "vague": ["c8"], "town": ZHIL, "here": "the tavern",
        "text": ("The woman with the missing tooth nods slowly. She leans back, her eyes "
                 "remaining on yours. 'A scribe? You'll find one at the nearby scriptorium, or "
                 "perhaps one who still keeps their papers in the counting house. But be "
                 "warned,' she adds, her voice dropping to a conspiratorial rasp. 'The ones "
                 "who deal in letters of trade have ears.' She takes a long, steady pull of her "
                 "own brew. 'I'd be careful with what you show them.'"),
        "said": [("c8", "A scribe?"), ("c8", "The ones who deal"), ("c8", "I'd be careful")],
        "people": {"The woman": "c8"},
        "new": {},
        "lines": {"A scribe": "c8", "The ones who deal": "c8", "I'd be careful": "c8"},
        "places": [{"words": "scriptorium", "kind": "*", "near": "none|here|*"}],
        "placed": [{"words": "one", "at": "the counting house", "optional": True}],
        "pronouns": {"c8": "she"},
    },
    {
        "id": "replay-strangers-9-the-old-man",
        "why": "the plan's 'oldest person on the street' is the old man; every line his",
        "cast": [KESST, ("c13", "oldest person on the street", "commoner")],
        "vague": ["c13"], "town": ZHIL, "here": "the tavern",
        "text": ("The old man sits on a stool that seems to groan under his weight, his "
                 "hands—gnarled like the roots of an old oak—resting on the scarred wood of the "
                 "table. When he speaks, his voice is thin and brittle. 'Once?' he rasps. 'The "
                 "city was younger then. The walls were taller.' He looks toward the door. "
                 "'You're looking for something that isn't here anymore, girl.' He leans in. "
                 "'If you're looking for the old ways, you won't find them in the tavern.' He "
                 "gestures vaguely with a hand that lacks its last two fingers."),
        "said": [("c13", "Once?"), ("c13", "The city was younger"),
                 ("c13", "You're looking for something"), ("c13", "If you're looking for the")],
        "people": {"The old man": "c13"},
        "new": {},
        "lines": {"Once": "c13", "The city was younger": "c13", "You're looking for": "c13",
                  "If you're looking": "c13"},
        "pronouns": {"c13": "he"},
    },
    {
        "id": "replay-town-2-two-speakers-untagged",
        "why": "two people talking in one beat, no tags: whose is each line",
        "cast": [KESST, ("c1", "the neighbour beside you who knows the words", "commoner"),
                 ("c2", "merchant", "commoner")],
        "vague": ["c1", "c2"], "town": ZHIL, "here": "the north crossing",
        "text": ("The merchant's hand tightens on the bundle of cloth. 'The Council holds the "
                 "keys to the gates,' they say, their voice barely rising above the dull roar "
                 "of the awakening district, 'but the land—the very dirt under your "
                 "boots—belongs to the Keepers.' They pause, their eyes narrowing. 'But if "
                 "you're looking for who rules the quarter, you're looking for the names on "
                 "the stone at the end of the lane.' As they speak, the neighbor beside you "
                 "leans in so close their breath fans your ear. 'The stone is old,' they hiss, "
                 "their voice a jagged edge. 'And the names upon it are not what they seem.' "
                 "The merchant watches you, waiting."),
        "said": [],
        "people": {"The merchant's": "c2", "the neighbor": "c1", "The merchant": "c2"},
        "new": {},
        "places": [{"words": "lane|stone", "kind": "*", "near": "*", "optional": True}],
        "lines": {"The Council holds": "c2", "but the land": "c2",
                  "But if you're looking for who": "c2", "The stone is old": "c1",
                  "And the names upon it": "c1"},
        "pronouns": {"c1": "*", "c2": "*"},
    },
    {
        "id": "replay-town-5-a-woman-with-a-sharp-face",
        "why": "three newcomers shown at the gate, one of whom speaks",
        "cast": [KESST], "vague": [], "town": ZHIL, "here": "the gate",
        "text": ("Now, you stand at the gate. The crowd here is a dense weave of movement: "
                 "Nirkor porters haul crates of spices, while the elite of the Khy'vyr clans "
                 "glide past in silks. A guard stands atop the stone balustrade, his gaze "
                 "tracking the flow of the throng. Near the center of the gate, a stall is "
                 "being adjusted; a woman with a sharp, intelligent face and a tattered cloak "
                 "over her shoulders is arguing with a clerk over a scroll of papers. She looks "
                 "up as you approach. 'You there,' she calls out over the noise, 'you look "
                 "like you’ve come a long way to find something specific.' What do you do?"),
        "said": [],
        "people": {"The crowd": "nobody", "A guard": "new:guard", "a woman": "new:woman",
                   "a clerk": "new:clerk"},
        "new": {"guard": {"head": "guard", "where": "here"},
                "woman": {"head": "woman", "where": "here"},
                "clerk": {"head": "clerk", "where": "here"}},
        "lines": {"You there": "new:woman", "you look like": "new:woman"},
    },
    {
        "id": "replay-town-11-the-south-wharf",
        "why": "a wharf the town does not have, by the docks it does",
        "cast": [KESST, ("c14", "stallholder", "commoner")], "vague": ["c14"],
        "town": ZHIL, "here": "the approach",
        "text": ("The man behind the counter leans forward, his knuckles white where they grip "
                 "the edge of the wood. 'Work?' he repeats, the word sounding heavy in his "
                 "mouth. 'The dock-master's men are hiring for the heavy hauls today. They're "
                 "looking for folk who can move the spice-crates from the south berths.' He "
                 "pauses. 'But if you're looking for coin that isn't weighed in sweat, you'd "
                 "best head toward the merchant's row.' He reaches under the counter and pulls "
                 "out a small, tattered piece of paper. 'If you want the heavy work, go find "
                 "Foreman Kael at the south wharf. He’s the one who keeps the lines moving.' "
                 "It is a crude map of the nearby docks, with a heavy circle around the south "
                 "wharf."),
        "said": [],
        "people": {"The man": "c14"},
        "new": {},
        "lines": {"Work?": "c14", "The dock-master's men": "c14", "But if you're": "c14",
                  "If you want the heavy work": "c14"},
        "places": [{"words": "south wharf", "kind": "docks|other", "near": "the docks|none"},
                   {"words": "south berths", "kind": "*", "near": "*", "optional": True}],
        "placed": [{"words": "kael", "at": "the docks", "optional": True}],
        "pronouns": {"c14": "he"},
    },
    {
        "id": "replay-town-21-the-merchant-at-his-stall",
        "why": "the merchant the plan introduced, described as 'a sturdy man'",
        "cast": [KESST, ("c20", "laborer", "commoner"), ("c21", "laborer", "commoner"),
                 ("c22", "stallholder", "commoner")],
        "vague": ["c20", "c21", "c22"], "town": ZHIL, "here": "the approach",
        "text": ("The merchant is a sturdy man whose face is mapped with the lines of years "
                 "spent in the sun and the grit of the market. He is currently fussing with a "
                 "roll of thick, waxed canvas. 'Work?' he grunts, his voice like gravel in a "
                 "tin. 'The work is moving. The work is hauling.' He pauses, finally looking at "
                 "you over the rim of his spectacles. 'You look like someone who can move "
                 "things. I need a pair of strong hands to escort a delivery of spice-sacks "
                 "through the lower gates.' He gestures to a heavy, iron-bound crate sitting on "
                 "a neighboring cart. 'If you can get that crate to the west gate without "
                 "getting questioned or shoved, I'll see to it you get a pouch of coin and a "
                 "hot meal at the way-inn.'"),
        "said": [],
        "people": {"The merchant": "c22", "a sturdy man": "c22"},
        "new": {},
        "lines": {"Work?": "c22", "The work is moving": "c22", "You look like": "c22",
                  "If you can get": "c22"},
        "places": [{"words": "way-inn|way inn", "kind": "*", "near": "*", "optional": True},
                   {"words": "west gate", "kind": "*", "near": "*", "optional": True},
                   {"words": "lower gates", "kind": "*", "near": "*", "optional": True}],
        "pronouns": {"c22": "he", "c20": "*", "c21": "*"},
    },
]
