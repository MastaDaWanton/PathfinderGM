# Senses and light: research for playtest 2026-11-23 items 1, 2, 13 and O6

Lane fix/senses-and-light, 2026-11-25. Each item: the rule, what other traditions did
(and dropped), the option taken and the options refused.

## Item 1: the rooms below the trapdoor were under the open sky

**What happened.** Every room behind the tower's locked trapdoor was a founded place with
`origin: "dungeon"` whose id was minted under the venture's head
(`...~ruins:@hex-m114-76/the-tower/the-narthex`). `Scene.ambient_light` asked only
`terrain_of(at) == "underground"`, got "ruins", fell through to `is_indoors`, which said
no roof (the ruins floor plan has `ceiling=None`), and lit the room by the night sky: dim
light, 20% miss chance. Six of Shadow's sixteen swings were lost to it. The ruins shape's
`about` ("broken walls, and rubble where they fell") was the room's UNDERFOOT line, and the
prose put "a dark, starry sky" over the vestibule.

**The rule.** CRB, Vision and Light (legacy.aonprd.com/coreRulebook/additionalRules.html):
"Areas of darkness include an unlit dungeon chamber, most caverns, and outside on a
cloudy, moonless night"; "In areas of darkness, creatures without darkvision are
effectively blinded." The same section gives a blinded creature's penalties: a 50% miss
chance in combat, loses any Dexterity bonus to AC, a -2 penalty to AC. CRB Conditions,
Blinded (d20pfsrd.com/gamemastering/conditions): "-2 penalty to Armor Class, loses its
Dexterity bonus to AC (if any)", -4 on most Str/Dex skills and opposed Perception.
Bestiary, Universal Monster Rules, darkvision
(legacy.aonprd.com/bestiary/universalMonsterRules.html): "can see in total darkness,
usually to a range of 60 feet"; "Darkvision is black and white only but otherwise like
normal sight."

**Owner ruling, 2026-11-25** (supersedes "do not change ambient light"): "yes underground
is dark ... make sure the GM notes the total darkness and properly acknowledges whether
the PC can see."

**Traditions.**
- DikuMUD line: a room flag set by its builder overrides everything; only without it do
  the sector and the sky decide. LuminariMUD's room-flag reference
  (luminarimud.github.io/Luminari-Source/web/guides/room_flags.html): ROOM_DARK "Forces
  the room to be dark regardless of other conditions"; players "Require[] light source or
  darkvision to see"; ROOM_INDOORS rooms "don't go dark at night". The Merc/ROM
  `room_is_dark()` seen in a Gammon forum thread (gammon.com.au/forum/threads/3841.html)
  checks the room's light count, then the flag, then the sector (inside/city), then the
  sun. In the one copy seen there, the whole body had been commented out to
  `return FALSE`, so every room was lit. That is an anecdote, not evidence that the
  tradition abandoned the check.
- NetHack: whether a room is lit is decided when the level is made, and the NetHack wiki
  (nethackwiki.com/wiki/Lit, /wiki/Dlvl) says dark rooms grow more frequent the deeper the
  level. I could not confirm the exact `litstate_rnd` formula from a primary source in
  this pass.
- OSR / B/X practice: a dungeon is dark and the party carries its light (Moldvay's
  encumbrance and light-source rules). Not re-sourced here; it is the common reading and
  agrees with the CRB line above.

**Taken.** The room's own record decides, like ROOM_DARK: `Scene.underground(place_id)` is
true on underground terrain OR for a room with a `dungeon` record (`dungeons.room`), and
`ambient_light` returns dark for it. Every way down in `dungeons.FEATURES` is a descent (a
trapdoor and steps, a ladder down a pit, a shaft, a stair under a flagstone, a passage
going down), so every dungeon room is under the ground. The id is never rewritten, so an
old save answers the same as a new one. A dungeon room's `Place` takes the underground
floor plan (`places._dungeon_shape`: a ceiling, "close stone, and not much air"), so the
roof, the brief's UNDERFOOT line and the battle grid agree. Effectively blinded in
combat: `Engine._unseen_attacker` (Dex to AC lost, uncanny dodge still keeps it) and a
named "can't see in the dark" -2 AC term beside cover (`_dark_ac_mods`) for a defender
who cannot see the attacker in the dark; skipped when the defender is already blinded,
whose own row charges both.

**Refused.**
- A per-room lit/unlit roll (NetHack). Nothing in the app authors a lamp in a dungeon
  room, and the owner ruled underground is dark.
- Rewriting the dungeon rooms' ids or terrain to "underground". It would fix
  `terrain_of` everywhere at once, but it would also re-seed every room's floor plan and
  move every existing save's room ids, and encounter, foraging and map code all read the
  terrain.
- The -4 skill and opposed-Perception penalties of blindness from darkness. The owner's
  2026-10-06 ruling (alchemy open point 8) keeps Stealth and Perception in the dark for a
  later pass. Noted, not built.

**The page.** `light_shown.dark_seen` is the other half of `sight`: total darkness and a
darkvision range. `prompts.light_now` says total darkness every beat, and either "sees
nothing at all" or "sees in it by darkvision: shades of grey, no colour, black beyond a
short way" (words, not feet: law 3). Under the ground every dark line adds "no sky: no
stars, no moon, no daylight". The check now owes the dark on every turn beat, not only in a
fight or a search (dim light keeps that rule), with darkvision backstop lines, and flags
any SKY word (sky, stars, moon, starlight, sunlight, daylight, open air) in a sentence set
under the ground. Detect mechanically, repair with a targeted rewrite, cut as backstop:
the house shape, docs/narrator-guards.md D1.

## Items 2 / O6: the undine had no darkvision

**What happened.** The Aurvantis Undine card states `grants: ["amphibious",
"move.swim.30"]` and says "Can hold breath far longer than a human, sees clearly
underwater" and "Gills at the throat let them breathe underwater". Under the 2026-09-16
ruling, a card that states its tags is read for nothing else, so no cue ran and the PC had
no sense at all.

**The rule.** Paizo's undine (ARG; d20pfsrd.com/races/other-races/featured-races/
arg-undine): "Undines can see perfectly in the dark up to 60 feet", swim speed 30 ft, and
an alternate Amphibious trait. That agrees with the owner's ruling and is NOT what decides
it: the world owns its peoples (memory the-world-owns-its-own-races.md), so the senses are
read from the world's own words and never checked against the book's undine.

**Owner ruling, 2026-11-25 (O6):** "if an undine doesn't have darkvision it is an
oversight, how could they live underwater otherwise." World-agnostic, and models read,
code validates (owner, 2026-10-03).

**Traditions.**
- Foundry VTT's PF1 system keeps senses as named fields on the actor (darkvision, low-light,
  scent, blindsense ...) rather than as free text, and the Bestiary prints senses as a
  closed line. Both are a closed vocabulary that a reader fills in. I did not re-fetch
  Foundry's schema in this pass; it is from the project's earlier race research (the
  races.py docstring) and is unconfirmed here.
- This app's own regex cue table (`races.CUES`) is the abandoned shape. It fires on "night
  vision" or "see ... dark", misses a way of life ("they live under the water"), and the
  owner ruled out regex reading English.

**Taken.** `gm/race_senses.py`: one model call per people, temperature 0, under a JSON
schema with four REQUIRED booleans (sees_in_darkness, sees_in_dim_light, keen_scent,
senses_without_sight) and a reason written first. Ollama enforces required properties
(6/6 probed, memory ollama-schema-enforcement). Code maps each yes to one tag of
`races.SENSE_TAGS` (`sense.darkvision.60`, `sense.low-light`, `sense.scent`,
`sense.blindsense.30`), so no model writes a tag or a number. Four invented peoples serve as
demonstrations (lake-dwellers, plain farmers, night hunters, cave-dwellers that echolocate),
none from a shipped world. The reading is stored at `homebrew/race-senses.json`, stamped
with a reader version and a CRC of the exact words, and `races.draft` adds it beside a
card's stated tags. It runs in a background thread on campaign load (the player's race
first) and when the forge lists a world. The race document is read live
(`Actor._race_doc` -> `world_shared`), so an existing save gains the sense with nothing
written onto the character. World Bible ask 36 asks the export to state these senses
itself.

**Measured live, 2026-11-25** (igorls gemma-4-12B, shared Ollama, 19 s for all 16 Aurvantis
races): Undine -> darkvision. For 14 of the 15 other cards the reading equals the senses
the card already states. The one difference is Grippli -> low-light plus blindsense 30 ft
from "Keen hearing tuned to vibration" (the card states low-light and climb). That is a
defensible reading and an owner call. Shadow on the owner's save: `has_state
("sense.darkvision")` went from False to True, and the miss chance against the chickens in
the death room went from 50 to 0.

**Refused.**
- Adding "underwater|aquatic|gills" to the regex cue table: regex reading English, and a
  card that states its tags never reaches the table anyway.
- Granting darkvision to everything with `amphibious` or a swim speed, in code. Paizo's own
  aquatic peoples differ (its merfolk have low-light vision by default; darkvision is only an ARG alternate
  trait, d20pfsrd.com/races/other-races/uncommon-races/arg-merfolk), so the rule
  would be the app's invention rather than the world's words.
- Reading on the turn path or synchronously at load: a cold model load is 60-100 s on
  this machine (memory slice-findings).

## Item 13: the aside said darkvision gives no help to hit

**What happened.** "/gm I have dark vision dim light doesnt matter to me why did dim light
make me miss?" matched no engine topic and went to the model with no sight facts. It
answered that darkvision "doesn't give you a bonus to your accuracy", which is the rule
backwards (darkvision removes the light's miss chance within its range) and leaves out the
engine's real reason: Shadow had no darkvision.

**Taken.** `gm_answers.sight_facts` hands the aside the engine's own readings whenever the
light where the player stands is poor or a blow was lost to the light last turn: what the
player sees by (`Actor.eyes`), the light at their square (`Scene.light_at`,
`Scene.underground`), each miss the light decided (the tells `_concealment_of` wrote,
parsed by the existing `light_shown.light_misses`, with "because X has no darkvision" when
that is why), and the rule in the book's words (CRB Vision and Light, Bestiary
darkvision). These go in the record slot, last in the user message.

**Traditions.** The engine-first `/gm` door (play/gm_answers.py docstring: Diku `ooc`,
answering from state) is the house pattern. The fix grounds the model on state rather than
letting it recall rules.

**Refused.** Routing "why did ... miss" with another regex topic. The words vary endlessly
and the owner ruled out regex reading English. The facts are handed over by the engine's
state, not by the question's words.

## Second pass
A critic subagent re-fetched every external source on 2026-11-25. It confirmed the CRB,
Blinded, Bestiary, ARG undine, LuminariMUD and NetHack-wiki quotes. The Foundry claim is
still unconfirmed. It corrected three overclaims, all fixed above: the merfolk
alternate trait, the order of the checks in `room_is_dark`, and calling one commented-out
copy "the abandoned shape".

## Owner calls made provisionally
- Every dungeon room is dark, and no room is lit by its builders or inhabitants.
- The Grippli reads blindsense 30 ft from "keen hearing tuned to vibration".
- The darkness's -4 skill and opposed-Perception penalties are not applied (the 2026-10-06
  ruling stands).
- A sense read by the model is added even to a card that stated its own tags. This
  overrides the 2026-09-16 "stated tags are the whole truth" ruling for senses only,
  following O6.
