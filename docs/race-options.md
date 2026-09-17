# Every option a race card has

**Generated from `rules/races.py` by `tools/export_race_cues.py`. Do not edit by hand — regenerate it.**

This is the complete list. A race card in a World Bible export can produce **a size, a speed, up to 14 traits, and an ability array** — all of them below, and nothing else. There is no other channel: any sentence whose words match none of these rows is read by the consumer, matched against every pattern, and discarded.

**12 of the 14 do something in play today.** The rest are recorded on the sheet and shown to the player, and the engine cannot act on them yet — it has no walls to climb, no water to swim, no air to fly through, and it rolls the weapon in hand rather than a claw. Write them anyway; they are true about the people and they will start working without the card changing.

## Size

One of: `tiny`, `small`, `medium`, `large`. Send the word in the `size` field.

The prose is also read, and overrides nothing — it only fills the gap when `size` is missing:

- **small** — small, short, slight, diminutive, half the height, child-sized, waist-high, knee-high, halfling-sized
- **large** — towering, giant, huge, massive, twice the height, ten feet, nine feet, eight feet — RECOGNISED BUT NOT GRANTED: the Race Builder allows Large for giants only, so the sheet stays medium and a not_yet line is written

## Speed

One of `slow`, `normal`, `fast` in the `speed` field — which become 20, 30 and 40 feet. Never write the number.

- **fast** — swift, fast, quick, fleet, sprint, outrun, rapid
- **slow** — slow, lumbering, plodding, ponderous, waddling

## The traits, and the words that trigger them

Every one of these is matched over `body[]`, `senses[]` and `movement[]` **joined together**. Which field a word sits in makes no difference to what fires — put it in the field a reader would expect, because the fields are for the human, not the matcher.

### fly 30 ft (clumsy)

- *Write one of:* wings, winged, fly, flight, glide, soar, airborne
- *Grants:* `move.fly.30`
- *Status:* works in play

> They have broad wings and fly between the canopy platforms.

### blindsense 30 ft

- *Write one of:* echolocation (any ending), blindsense, sonar
- *Grants:* `sense.blindsense.30`
- *Status:* works in play

> They hunt by echolocation, and the dark costs them nothing.

### darkvision 60 ft

- *Write one of:* one of see / sight / vision / eyes WITHIN FORTY CHARACTERS of one of dark / darkness / night / lightless / pitch — or the single words darkvision / nightvision
- *Grants:* `sense.darkvision.60`
- *Status:* works in play

> They see in pitch darkness as well as in daylight.

### low-light vision

- *Write one of:* dim light, low light, low-light, twilight, dusk
- *Grants:* `sense.low-light`
- *Status:* works in play

> They see clearly by dusk light and hunt in the last of it.

### scent

- *Write one of:* one of scent / smell / olfactory / nose WITHIN FORTY CHARACTERS of one of keen / sharp / track / hunt / acute / strong — or the phrases "track by scent" / "hunt by smell"
- *Grants:* `sense.scent`
- *Status:* works in play

> They track by scent over open ground.

### amphibious; swim 30 ft

- *Write one of:* gills, amphibious, aquatic, "breathe water", "breathes underwater"
- *Grants:* `amphibious`, `move.swim.30`
- *Status:* **not yet: swimming as movement: a swim speed spares you the water's penalties, and does not yet carry you faster through it**
- *Note:* grants TWO tags: amphibious and a swim speed

> Gills at the throat let them breathe underwater.

### climb 20 ft

- *Write one of:* climb (any ending), arboreal, tree-dwelling
- *Grants:* `move.climb.20`
- *Status:* works in play

> They climb sheer trunks without rope.

### burrow 20 ft

- *Write one of:* burrow, tunnel, dig (any ending)
- *Grants:* `move.burrow.20`
- *Status:* **not yet: a burrow speed: the engine has no earth**

> They dig through packed earth to move between chambers.

### claws

- *Write one of:* talon, talons, claw, claws, clawed
- *Grants:* `natural.claws`
- *Status:* works in play

> Each hand ends in heavy claws.

### bite

- *Write one of:* fang, fangs, bite, tusk, tusks, mandibles, beak
- *Grants:* `natural.bite`
- *Status:* works in play

> A hooked beak, strong enough to break bone.

### +1 natural armour

- *Write one of:* carapace, chitin (any ending), scale, scales, scaled, hide, armour, armored, plated, shell
- *Grants:* `natural.armor.1`
- *Status:* works in play

> Overlapping scales cover the back and shoulders.

### light sensitivity

- *Write one of:* one of light / sun / sunlight / daylight WITHIN FORTY CHARACTERS of one of pain / blind / burn / dazzle / hurt / weak (any ending)
- *Grants:* `weakness.light-sensitivity`
- *Status:* works in play

> Direct sunlight dazzles them within moments.

### an extra feat and an extra skill rank

- *Write one of:* versatile / adaptable / unremarkable / highly variable / jack of all
- *Grants:* `versatile`
- *Status:* works in play
- *Note:* grants the extra feat and the extra skill rank a human gets, not a number on any roll

> They are physically unremarkable and highly variable.

### +1 on all saving throws

- *Write one of:* luck / lucky / fortunate / charmed
- *Grants:* `lucky`
- *Status:* works in play
- *Note:* +1 racial bonus on every saving throw, which is a halfling's luck

> They have a reputation for unusually good luck.

## What a people is good and bad at

Two fields, and six words. This is what makes a race *playable* rather than merely flavourful — without it every race in a world gets the same generic array and differs from its neighbours only in its senses.

| Field | What to send |
|---|---|
| `strengths` | **exactly two** of the words below |
| `weakness` | **exactly one** of the words below, and not one of the two strengths |

- **`clever`**
- **`commanding`**
- **`hardy`**
- **`nimble`**
- **`perceptive`**
- **`strong`**

Not one of those is a rules term. A world can say a people is hardy without knowing what Constitution is; the consumer maps the word and prices the result against the Advanced Race Guide's standard array.

**All three or none.** The standard array is +2/+2/-2 as a unit, so a card giving one strength, or two strengths and no weakness, is ignored entirely and the race keeps the generic array — otherwise leaving the weakness out would buy a net +4 by saying less. When a card gets it wrong the reason is written onto the race where the player can see it.

> `"strengths": ["nimble", "perceptive"], "weakness": "commanding"`

## What a card still cannot say

None of these can be expressed in the card format, and no wording reaches them:

- **Skill bonuses**, save bonuses, and any conditional modifier ("+4 against poison", "+2 on checks made underground").
- **Creature type.** Every world race is `humanoid`.
- **Bonus feats or extra skill ranks.**
- **Languages** beyond the people's own.
- **Anything Large.** The Race Builder allows Large for giants only, so a towering people is recorded as medium with a note.

