# A town's trouble shown: before and after samples (2026-11-21)

These are real beats from the bench (§5 of `2026-11-21-matter-shown.md`), across two
worlds. Each pair is the same snapshot, the same line and the same Ollama seed, with the
town's own trouble as the beat's matter.

- **Before** is integrate/0.4.9 at aa5df0c6.
- **After** is fix/matter-shown.

The saves are copies of the owner's and testers' Aurvantis games, plus a fresh Pangrella
campaign. The pages are given whole, closing question included.

## 1. Aurvantis: Balzun, at the gate. "I ask nobody in particular how things are around here."

Trouble: Ongoing friction over grazing land.

**Before.** You ask nobody in particular how things are around here. Tense whispers of
trade disputes over grazing lands ripple through the crowd as the busy trading season
begins to heat tensions. 'It's a bit of a tiff over the grazing lands, and it's making folk
a bit prickly. But as far as the daily grind goes, the market and the docks are where the
real action is,' the wagon master says kindly. What do you do?

**After.** You ask nobody in particular how things are around here. A tattered notice
pinned to a post near the gate lists the boundaries of the disputed grazing lands, its
edges curled and scorched. 'Most of it is just the usual fuss over the grass, but the folks
here keep to their business. If you need a drink or a rest, the inn is right there, and the
docks are just a stone's throw away,' the wagon master says kindly. What do you do?

## 2. Aurvantis: Fizspark, the market. "I look around."

Trouble: Ongoing friction over grazing land.

**Before.** You survey the morning bustle of the market, taking in the sights of the stalls
and awnings under the early morning sun. You look around the area, your eyes passing over
the various displays and the people moving among the crates. Tense whispers regarding the
disputed grazing lands drift through the air, a shadow of local friction over the village's
territory. The guild clerk meticulously folds a scrap of paper into a small bird and places
it upon a nearby surface. What do you do?

**After.** You look around the busy market, taking in the rows of stalls and awnings
beneath the early morning sun. A crude, hand-painted notice pinned to a nearby post lists
the growing list of disputed grazing claims, its edges frayed and stained by the elements.
The guild clerk meticulously folds a scrap of paper into a small bird and places it upon a
nearby table. What do you do?

## 3. Aurvantis: Scrapden, the tavern. "I listen to what people around here are talking about."

Trouble: Ongoing friction over smuggling routes.

**Before.** You lean back against a wooden bench and call out for the locals to keep their
voices low enough for you to overhear their talk. You want to catch the whispers of the
early morning in the tavern. The tension over the city's smuggling routes hangs heavy in the
air, a sharp edge of local friction that colors the morning atmosphere. The goblin behind
the bar continues their work, moving with a steady, rolling gait among the supplies. What do
you do?

**After.** The mystery of the caravan remains unsolved as the goblin continues their
rhythmic work behind the bar. You sit amidst the heavy wooden furniture and focus your
attention on the hushed murmurs of the room, listening intently to the conversations of
those nearby. A heavy, iron-banded crate sits near the hearth, its side marked with a
jagged, unofficial seal used by smugglers to bypass the city's formal gates. What do you do?

## 4. Aurvantis: Scrapden, the tavern. "I sit down and rest for a bit."

Trouble: Ongoing friction over smuggling routes.

**Before.** You pay the one behind the bar 5 Cinderwarren silver pieces for a room at the
tavern for the night. You pay the goblin behind the bar five silver pieces for a common room
and settle onto the raised, heated floor. You close your eyes and rest for eight hours, the
warmth of the stones beneath you providing a steady comfort as you sleep through the passing
of the day. Outside, the tension over contested smuggling routes hangs heavy over the city's
streets and rooftops. The goblin behind the bar continues their work, moving with a steady,
rhythmic gait as they tend to the supplies. What do you do?

**After.** You pay the one behind the bar 5 Cinderwarren silver pieces for a room at the
tavern for the night. You pay the goblin behind the bar five silver pieces for a room and
spend the next eight hours resting on the heated floor. By the time you awaken, the midday
sun hangs high over Scrapden, casting a harsh light across the tavern's tables and benches.
A crude, unofficial seal of a crossed key and anchor is branded into the wood of the main
door, a silent marker of a disputed smuggling route. Ratta Farrow stands nearby, his steady
gaze fixed on the room while he waits for the day's business to begin. What do you do?

## 5. Pangrella: Mirabalos, the warrens. "I wait a while and watch the people go by."

Trouble: competition for power between regional lords and winged nobles.

**Before.** You wait for several minutes in the shadow of the warrens as the morning sun
climbs higher. It is now approximately ten in the morning. In the distance, the hushed,
tense negotiations of the local lords over trade routes and resources permeate the air of
the district. Azhil Vyrnys remains at your elbow, watching the crowd with a practiced,
calculating eye. What do you do?

**After.** You wait for several minutes in the morning air as the sun climbs higher over
the city. A fresh, jagged mark of a rival house's crest is carved into a nearby stone
pillar, its edges still sharp and unweathered. Azhil Vyrnys keeps their eyes scanning the
crowd, moving with a practiced, restless energy. What do you do?

## 6. Pangrella: Mirabalos, the warrens. "I check my pack and gear."

Trouble: competition for power between regional lords and winged nobles.

**Before.** You hold a description of a target who has just caught your gaze across the
cluttered stalls. You reach into your pack to check your gear and equipment. The tense
atmosphere of the warrens reflects the fierce competition between regional lords and the
winged nobility for control over local resources. What do you do?

**After.** A sense of urgency remains as the target's gaze lingers across the way and the
paper's description matches the face watching you. You reach into your pack and begin to
check your gear amidst the morning bustle of the warrens. A heavy, wax-sealed decree from a
regional lord is tacked to a nearby post, its bold script demanding exclusive passage for
the wing-bound elite. What do you do?

## What these do not show

- **A new formula across separate beats.** Every bench beat started from a fresh
  snapshot, so none had an earlier showing to avoid. Within a single town, the model then
  settles on one shape:
  - Fizspark: a notice or sign "pinned to a nearby post" on 7 of 8 beats;
  - Mirabalos: a "fresh, jagged mark" of a crest on 5 of 8.

  In play, `Card.shown` hands the next showing what was already shown. The live check saw
  this work once: the save held the sign after the first showing, and the town's trouble
  then rested on the next turn as it should. No live chain was run long enough to see a
  second, different showing, so how well the rotation works against this formula is
  **not measured**.
- **A mood outside the trouble.** A "still" slot still writes a mood about the player's
  own open matter: "A heavy uncertainty hangs in the air, a puzzle regarding the lost
  caravan". "Uncertainty" is not on the detector's list, which holds only the trouble's
  words.
- **A reply is never read.** In one beat the wagon master's own words were "the tension
  over those pastures is thick enough to cut with a blade". That was left alone on purpose:
  it is talk.
