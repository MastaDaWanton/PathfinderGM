# Design C — starts and variety

Phase 0 research and design for Lane C of `docs/fix-plan-2026-09-28.md`. It was a read-only
sweep, written 2026-09-28 on branch `fixes-2026-09-28`, and nothing here is built. Every
measurement comes from the three fixtures (`aurvantis-campaign.json`,
`pangrella-campaign.json`, `synthetic-world.json`) or from the code at the line cited. A
claim that could not be sourced is marked as such.

---

## 1. Items covered

| Item | Measured cause | Lane C answer |
|---|---|---|
| 1 | Vormoor, a village, was called a sprawling city. The world's own writing says "the city's" or "the city" in 48 of Aurvantis's 64 settlements and in 4 of Pangrella's 6 towns. `material()` has no scale line, the EXAMPLE shows the model working the size out from the facts, and `problems()` has no size check. | Four changes: a scale line in the material; a village EXAMPLE that copies that line; the stock words normalised; a hard size check. |
| 2 | Every campaign starts in Vormoor: `starting_place` breaks ties on summary length, then reverse alphabetical order. | The town and the start are chosen together in one seeded, weighted draw that takes the character into account. |
| 3 | Twelve starts that are really one start. The pick is seeded from the slugified name. Every edge is "went quiet". No engine state exists. The errand is always "broke stranger". The background is ignored. There is no tavern or road start. | Start documents: each has an engine-backed incident, a lead and an exact hand-off, is weighted by background, and is drawn from a per-campaign story seed. |
| 3.4 | There are no road starts. | The schema accepts `where: road` now. Placing one is refused until I1 delivers Lane B's outskirts. |
| 4b | "the watchman waving traffic through" was used as a name. | Each lead has a short `label` and a separate `look`. The validator refuses a role phrase as a label. |
| 4 (opening) | The opening companion is never described on first sight. | The face goes into the material and the template, backed by a check and a backstop. Then `described = True` is set. |
| 8 | Drenn is the first named person in every game. Cast roles are "Person"; the fallback is `cast[len(taken) % len(cast)]`; there are separate `taken` sets; keepers take their family names only from the cast. | Roles are read from the person's entity. Picks are seeded per campaign. One `spoken_for` list lives on the scene. Keeper families come from the town's own `play.names` pool. |
| 8.5 / 9 | "The lost thing" opens at hour zero. | Not Lane C's to fix: `content/schemes/` belongs to Lane D. A start only carries `opens_scheme`, and I4 wires it. |

---

## 2. Prior art per tradition

**CRPG origin prologues.**
- *Dragon Age: Origins* picks one of six origins from race plus class. After the origin, "all classes follow the same plot" ([Wikipedia](https://en.wikipedia.org/wiki/Dragon_Age:_Origins)). The first draft had **twelve** origins (Human Commoner and Avvar barbarian among them). Most were "scrapped for being 'ridiculous'" (same source).
  - Secondary coverage says the Commoner's farmhouse siege was cut for tone and because it was technically hard ([TheGamer](https://www.thegamer.com/dragon-age-origins-cut-origin-stories-human-commoner-barbarian/)).
  - No primary developer statement was reached.
- *Cyberpunk 2077*'s three lifepaths are 20–30 minute prologues that converge into one montage. The criticism: after the first mission "there's no feeling that it's shaped your character" ([TheGamer](https://www.thegamer.com/cyberpunk-2077-life-paths-pointless/), a secondary source).

**Scenario starts in simulation games.**
- **RimWorld.** A scenario is a list of parts: faction, pawns, arrival method, items, map conditions, forced traits or health, incidents. The wiki's own description: "choose, randomize, and customize special situations to play in" ([RimWorld Wiki](https://rimworldwiki.com/wiki/Scenario_system)). Crashlanded, Lost Tribe, Rich Explorer and Naked Brutality are the same parts with different values. This is the closest match to a start document.
- **Kenshi** has 13 starts ([summary](https://lilura1.blogspot.com/p/kenshi-game-starts.html); the Fandom page did not load).
  - Most put **engine state** in place at minute one: a bounty (Holy Sword), a missing arm (Rock Bottom), shackles (The Slaves), an immediate cannibal attack.
  - Three randomise the place: Holy Sword (random town), Freedom Seekers (random waystation), Holy Nation Citizen (one of two towns).
- **Caves of Qud** keeps one static village, Joppa, recommended for new players. It also offers four generated village starts, each with generated quests of its own ([official wiki](https://wiki.cavesofqud.com/wiki/Joppa)). A fixed floor sits beside the variety.
- **Dwarf Fortress adventure mode.** You pick a site of your own civilisation, and it "decides where you start the game at". The same page admits "most of the occupations are presently only there for flavor" ([DF wiki](https://dwarffortresswiki.org/index.php/Adventurer_mode_character_creation)). That is our item 3.
- **Mount & Blade.**
  - Warband lets you choose the starting town ([StrategyWiki](https://strategywiki.org/wiki/Mount%26Blade/Character_creation)). Per a search snippet of the Fandom wiki (the page did not load), a merchant approaches after your first fight on arrival and opens a quest chain: a street fight, then a lead, then an offer.
  - In Bannerlord, culture decides the starting location ([Fextralife](https://mountandblade2bannerlord.wiki.fextralife.com/Cultures)).
- **Skyrim.** Every character starts at Helgen. The best-known answer is the mod *Alternate Start – Live Another Life* ([UESP](https://en.uesp.net/wiki/Skyrim_Mod:Alternate_Start_-_Live_Another_Life)), which offers:
  - about 17 general starts: an inn patron, a property owner, arrival by ship, camping in the woods, shipwrecked, left for dead, a bandit lair;
  - 8 race-restricted starts, such as a Khajiit caravan guard or an Argonian dock worker;
  - "Surprise Me".

  Several of these begin in immediate danger. That is the player's request (a tavern, a road, a start shaped by background) already built by a community.

**Tabletop first sessions.**
- **Dungeon World** ([SRD](https://www.dwsrd.org/gm/first-session.html)):
  - "Start the session with a group of player characters … in a tense situation."
  - "Ask questions right away."
  - A situation that "stems directly from the characters" is better.
  - The GM never brings "a planned storyline or plot".
- **Blades in the Dark** ([Planning & Engagement](https://bladesinthedark.com/planning-engagement)):
  - The engagement roll skips "ponderous non-action".
  - The GM cuts "to the first serious obstacle"; the crew is "already in action". **This is the hand-off the player described:** the cage owner stops talking where the Heal check begins.
  - The book's one canned starting situation, the Crow's Foot war, is shared by many actual plays. The Alexandrian recommends a structure instead: two factions at odds, a third profiting, and an opening scene with a **job offer** ([The Alexandrian](https://thealexandrian.net/wordpress/40638/roleplaying-games/blades-in-the-dark-alternative-starting-situations)).
- **Ironsworn** pairs a long-term background vow with an **inciting incident**: "a problem which you can (and must!) deal with now". This is from the fan wiki, via search results; the page returned HTTP 402 and I did not reach the rulebook.
- **Apocalypse World**: the MC does not plan and fishes with provocative questions. Secondary sources only ([RPG Musings](https://rpgmusings.com/2011/08/apocalypse-world-an-introduction/)).
- **Sly Flourish's "strong start"**: an innkeeper drops dead mid-sentence; a wyvern strikes mid-wedding ([Lazy DM](https://slyflourish.com/eight_steps_2023.html), via search).
- **The Alexandrian on *in medias res***: mystery at the start "can create significant issues when the players are supposed to *be* the characters". The fixes are "why are you here?" or a flashback ([Art of Pacing 6](https://thealexandrian.net/wordpress/33796/roleplaying-games/the-art-of-pacing-part-6-more-advanced-techniques)). A predetermined scenario is "very light railroading" ([Railroading Manifesto 3](https://thealexandrian.net/wordpress/36914/roleplaying-games/the-railroading-manifesto-part-3-penumbra-of-problems)).

**Interactive fiction and generated variety.**
- The opening already follows Nelson's overture and Emily Short's "obvious starting problem" (`play/opening.py:446`, `play/opening_prose.py:21`). I did not re-verify those quotes; the Inform manual PDF would not extract.
- New here: Emily Short says variation matters by "whether the generation is connected to anything mechanical" ([Bowls of Oatmeal](https://emshort.blog/2016/09/21/bowls-of-oatmeal-and-text-generation/)).
- Kate Compton's "10,000 bowls of oatmeal" names content that is mathematically unique but perceptually the same ([slides](https://golancourses.net/2022f/wp-content/uploads/2022/09/kate-compton-oatmeal.pdf)). Today's twelve edges are twelve bowls of oatmeal.

**One NPC across runs.** I found no primary source; the RimWorld search found only name-deduplicating mods. The design rests on our own measurement: Drenn was first in 100% of campaigns.

**Settlement sizes.** The GameMastery Guide gives: village 61–200, small town 201–2,000, large city 10,001–25,000, metropolis over 25,000 ([AoN](https://aonprd.com/Rules.aspx?ID=842)). The app's `POPULATION_BY_SCALE` says village 200–1,200 and city 50,000–250,000 (`rules/places.py:253`). This is an open question (§9), not a Lane C change.

---

## 3. What was tried and abandoned, and why

1. **DA:O went from 12 origins to 6.** The reason given is quality and fit, not the idea itself. *Ship a few engine-real starts, not twelve paragraphs.*
2. **DA2 and Veilguard dropped playable origins.** DA2 fixed its protagonist. Veilguard's backgrounds have "no special starting quests" ([Deltia's](https://deltiasgaming.com/dragon-age-the-veilguard-backgrounds-factions-explained/), secondary). No developer reason was found, and none is claimed. *Prologues are the expensive part: share the machinery (verbs, lead, hand-off) and vary only the document.*
3. **Cyberpunk's lifepaths converge and are then forgotten.** *A start must leave state behind: a patient who lives or dies, a lead with `bond.knows-you`, a card, a scheme.*
4. **Helgen for everybody.** In practice a mod with 25+ starts replaced it. *The demand is real.*
5. **Blades' canned Crow's Foot.** It made many plays alike. *Ship a vocabulary of kinds, leads and hand-offs, not one story.* Our Vormoor-every-time bug is this failure, produced by a tie-break.
6. **DF's flavour occupations.** *A background has to change where and how the game begins.* Today `_bind_background` runs after the roll.
7. **In medias res with the reason hidden.** *The lead says the reason aloud, the errand says why you came, and control passes before anything is decided for the player.*
8. **Our own abandoned attempts:**
   - leading with trouble and naming the place second (2026-09-05; the orientation order stays);
   - the "best-described" ranking, which a templated export turned into alphabetical order (retired here).
9. **Kept on purpose, like Qud's Joppa:** three of today's quiet situations stay as a low-weight floor.

---

## 4. Recommended design per item

### 4.1 The start document (item 3)

`content/openings/*.json` uses the envelope `{"_about": [...], "starts": [...]}`, the same as backgrounds and schemes. Homebrew goes in `homebrew/openings/` and wins on a shared id. The loader and validator live in a new `rules/openings.py`.

```json
{
  "id": "called-to-the-cage",
  "name": "Called to the cage",
  "kind": "injury",
  "fits": {"backgrounds": ["bonesetter"], "open": false,
           "scales": ["village", "town", "city"],
           "needs": ["arena|green|lane|market"], "people": "any"},
  "where": {"at": "place", "kinds": ["the arena", "the green", "the lane", "the market"]},
  "when": "Late afternoon",
  "lead": {"slot": "lead", "role": "fixer", "words": ["fixer", "bouncer", "thug"],
           "label": "the cage owner",
           "look": "talking over his shoulder as he pushes through the crowd",
           "says": "He went down in the second and has not got up. The last one who looked at him wanted paying first."},
  "incident": [
    {"do": "bring", "slot": "patient", "label": "the beaten fighter",
     "words": ["pit fighter", "brawler"], "zone": "engaged"},
    {"do": "wound", "slot": "patient", "to": "dying"},
    {"do": "bring", "slot": "crowd", "label": "the crowd", "words": ["commoner"],
     "count": "some", "zone": "near"}
  ],
  "hand_off": {"at": "check", "skill": "heal", "on": "$patient",
               "moment": "The cage owner stops at the edge of the sand and steps back."},
  "errand": "You came because somebody sent a boy running for the bonesetter, and you are the bonesetter.",
  "suggestions": ["Kneel and stop the bleeding", "Ask the cage owner what happened",
                  "Clear the crowd back first"],
  "tags": ["start.injury", "start.in-town", "start.background"],
  "grants": [{"to": "pc", "tags": ["knows.who-is-ailing"],
              "say": "You know the look of a man with a cracked skull."}],
  "opens_scheme": ""
}
```

**What the validator checks** (`openings.validate(doc) -> list[str]`, in the style of `classbuilder.validate_class`). It reports every problem at once, and each message names the fix.

- **`id`**: lower case with hyphens, and permanent, because it is saved.
- **`kind`**: must be in `KINDS = (attack, injury, rescue, chase, brawl, fire, offer, arrival, summons, accused, quiet)`.
- **`fits.backgrounds`**: every entry must exist in `backgrounds.all_backgrounds()`.
- **`fits.scales`**: must be drawn from `places.SCALES`.
- **`fits.needs`**: alternatives separated by `|`, each one a key of `places.KINDS` or of `schemes.PLACE_KINDS`, or the word `water`.
- **`fits.people`**: `own`, `stranger` or `any`, compared against `names.people_of(town)`.
- **`where.at`**: `place`, `lodging`, `road` or `outskirts`.
  - `road` and `outskirts` **validate** now.
  - `openings.placeable(doc)` refuses them with the message "a road start needs the outskirts (I1)" until I1 lands.
- **`when`**: must be a key of `opening._HOUR_OF`, and never night.
- **`lead.label`**: at most 3 words, and it must start with "the". It may not contain an `-ing` word or any of `who`, `that`, `with`, `through` (item 4b). The message names the fix, e.g. "put 'waving traffic through' in `look`".
- **`lead.says`, `errand`, `moment`, `grants[].say`**: no digits, and no capitalised words that are not at the start of a sentence. Ground every name: the world supplies names, not the document.
- **`incident`**: may use only the verbs in §4.2, and every `$slot` it uses must be declared.
- **`hand_off.at`**: must be in `HANDOFFS`. A `check` hand-off must name a real skill and a declared slot.
- **`errand`**: must begin "You came".
- **`tags`**: must start with `start.`.
- **`grants`**: must use the families in schemes' `GRANTABLE`, and a `knows.*` grant must carry a `say`.
- **`suggestions`**: between 2 and 4 of them.

Tags and grants go to the PC as ActiveEffects with `origin: start:<id>`.

### 4.2 Incident verbs, expressed only in existing ops

`new_campaign` runs the incident through `Engine.validate(intents, origin=f"start:{id}")` and then `engine.run`, using the trusted provenance door at `rules/engine.py:1877`. No model is involved.

| Verb | Becomes | The numbers come from |
|---|---|---|
| `bring` | `introduce`, with `who` = label and `template` = `npcs.choose(words, level)`, plus `zone`/`count`. Everyone enters through the S4 arrival door and gets a square. | the codex, at party level |
| `wound` (`hurt`, `staggered`, `dying`) | `damage`, lethal. `openings.py` computes the amount **from the target's own hp, by rule**: dying = hp + 1, which lands at −1 and becomes `state.down.dying` via `apply_hp_state`; staggered = hp; hurt = hp ÷ 2. | the rulebook's thresholds |
| `fight` | `spawn` using `npcs.choose(words, level)` (or `bestiary.search(biome, window)` on a road, as `ontheway.road` does), then `begin_encounter`. | `ontheway.BELOW`/`ABOVE` |
| `offer` | a `quest` with giver `$lead`. The engine prices the reward; a digit anywhere is refused. | engine pricing |
| `grant` | the grammar of schemes' `_grant` (e.g. `state.suspected` for "accused") | — |
| `move` | `move` | — |

**No new op is needed.** Fire (`kind: fire`) is deferred to I3. The authored `catching-fire` hazard is a damage slot over a number of rounds, with no step for putting the fire out (`content/rules/hazards.json`), so a burning stall cannot yet be held open at a hand-off.

**One engine behaviour is missing: first aid.** No path I could find lets a Heal check stabilise a dying creature. `_op_check` (`rules/engine.py:3565`) has no heal branch. `sheet.bleed_out` only rolls the patient's own Constitution. The PF1e rule is DC 15, a standard action, after which the patient "stops losing" hp ([d20pfsrd, Heal](https://www.d20pfsrd.com/skills/heal/)). §6 asks the owner who builds it.

### 4.3 The hand-off

`HANDOFFS = (check, fight, offer, speech, arrival)`. The opening stops at `hand_off.moment`, matching Blades' "first serious obstacle", and the NOW paragraph asks its question *there*.

| `at` | What the engine holds | What the prose must not narrate (a hard, mechanical check) |
|---|---|---|
| `check` | The target is in the state the check addresses (e.g. dying). | The check's result: `stabilis/z`, `bleeding stops`, `set the bone`, and similar. The list is per skill, in `openings.CROSSED`. |
| `fight` | `in_encounter` is set; initiative is rolled; nobody has acted. | Anyone among the spawned refs struck, fallen or fled. |
| `offer` | The quest card is open. | `you (accept\|agree\|take the job)` |
| `speech` | The lead is present, as someone who knows the PC (`KNOWS_YOU`) or as a stranger. | The player's reply. |
| `arrival` | The party is at the place. | `_DECIDES` (already in the checks). |

A draft that crosses the hand-off gets one repair that names the offending phrase. If the repair still crosses it, the opening falls back to the template. The template itself ends on `moment` followed by "What do you do?".

### 4.4 The town and the start, drawn together (items 2 and 3.1)

`openings.choose(world, pc, rng) -> (town, doc)` makes **one weighted draw over (town, start) pairs**, which is Qud's random village combined with Alternate Start's "your life".

- **Towns.** The settlements `starting_place` finds, kept if they are adequately described: at least one prose section, or at least 4 facts, and a non-empty `places.spots_for`. If none qualify, the old ranking is the floor.
- **Town weight.** Starts at 1.
  - ×3 when `names.people_of(town) == pc.world_people_id`; ×1/3 instead for a start marked `people: stranger` (e.g. exile).
  - ×2 when a background tie's role is filled *in that town*, per `geography.role_of`. Measured: a healer exists in 12 of 64 Aurvantis towns, a guard officer in 23 and a fixer in 21, so a bonesetter is drawn toward the towns where their teacher could live.
- **Start weight.**
  - 6 if `fits.backgrounds` names the character's background;
  - 1 for a generic start;
  - 0.5 for a `quiet` start.
- **Seed.** `random.Random(f"{story_seed}:start")`. A string seed is stable across processes, unlike `hash()`, which is why `_seed_from` exists. The same seed, salted with `:lead`, `:cast:<slot>` or `:keeper:<place>`, feeds every later pick. **The character's name decides nothing.**
- **The start is deterministic without a model.** That means the live script's town and kind criteria can be verified offline for its 30 seeds before any Ollama time is spent.
- **Letting the player choose.** `begin_with(character, world_source, start_town=None, start_id=None)` honours a choice that passes `fits`. `openings.offer(world, pc)` feeds a future picker. The screen itself is an open question.

### 4.5 First ship: 15 documents

| id | kind | fits | where | hand-off |
|---|---|---|---|---|
| called-to-the-cage | injury | bonesetter | arena, green, lane, market | check: heal |
| pulled-from-the-water | rescue | ferryman; needs `water` (`Land.coast`/`Land.water`, a sea/river road out, or docks/bridge) | docks, bridge, market | check: heal |
| the-bout-tonight | brawl | pit-fighter | arena, green, lane | fight (nonlethal) |
| short-on-the-gate | chase | gate-watch | gate, way in | speech (the officer names the runner) |
| the-name-on-the-list | chase | thief-taker | market, lane, back streets | speech (the mark bolts) |
| a-hand-short | offer | caravan-hand | stables, carters yard, market | offer |
| home-by-the-back-door | brawl | innkeepers-child; needs lodging | lodging | fight (nonlethal) |
| stop-thief | accused | generic; stallholder and exile ×3 | market | speech (`state.suspected` granted) |
| sent-for | summons | generic; household, guild-clerk, pilgrim ×3 | guildhall, temple, moot hall | speech |
| cutpurse | chase | generic | market | arrival (the child runs with your coin; `ontheway`'s lift roll) |
| trouble-in-the-lane | attack | generic | lane, back streets | fight |
| a-room-and-a-notice | arrival | generic; needs lodging | lodging | speech |
| the-hiring-table | offer | generic; apprenticed, forager ×3 | guildhall, market, workshops | offer |
| road-caravan-attack | attack | caravan-hand ×6; generic | **road** (waits for I1) | fight |
| road-in | arrival | generic | **road** (waits for I1) | arrival |

Three of today's situations are converted to `quiet` documents and form the floor. That gives **ten in-town kinds** in Phase 2, against a gate of at least 8. Both of the player's examples are in the set; the caravan one waits for I1. The fire start follows I3.

### 4.6 The scale line and the size check (item 1)

1. **A scale line in the material.** `material()` adds, right after `Place:`, a line like this:

   > What kind of place (a fact; copy it, never make it bigger): Vormoor is a village of a few hundred people, and everyone knows everyone.

   It comes from `places.what_it_is(places.scale_of(place))`, the one composer the panel, brief and template already share. It is added only when the world **stated** a scale, because `scale_of` answers "town" whenever it cannot read one.
2. **Stock words normalised.** Facts and prose pass through `geography.in_its_own_words(text, scale)` (S5), which rewrites "the city's"/"the city" to the settlement's scale word but never touches "the city of X". Keys pass through `geography.display_key`, so "Urban Life" becomes "Daily life". Measured: 96 + 12 occurrences in Aurvantis non-cities and 16 + 7 in Pangrella's towns drop to 0.
3. **The EXAMPLE becomes a village.** It gets the same line: "Hollin Stair is a village of a few hundred people…". Its answer opens "Hollin Stair is a village that climbs its cliff…" and replaces "Twenty men" with "everybody on this landing knows everybody else's boat". The failing case is the small place, so the one demonstration is a small place copying its size. `EXAMPLE_MARKS` is unchanged.
4. **A hard size check in `problems()`**, applied when the stated scale is village or town.
   - Words that fail a **village**: city, cities, sprawling, metropolis, metropolitan, tens of thousands, districts, thoroughfares, boulevard, teeming, crowds.
   - Words that fail a **town**: metropolis, sprawling, tens of thousands, the city.
   - A word inside a capitalised allowed name, like "City Watch", is exempt.
   - The repair message names both the word and the fact: "it calls Vormoor 'sprawling' and 'the city' — Vormoor is a village of a few hundred; describe it at that size".
   - One repair is allowed. If the draft still fails, the opening falls back to the template, which states the kind itself.
   - A test records the 2026-09-28 draft.
5. **The brief's WHERE line** gains "copy what kind of place it is". Measure it before trusting it.

### 4.7 A role phrase is not a name (4b); the lead's face on first sight

- **The label is the name.** The validated `label` becomes the actor's `name` and the population record's `who`. `look` carries the description. The legacy `Situation.who` strings are split the same way.
- **Which lead is used**, in order:
  1. The person a background tie names, when the tie's role equals `lead.role`. They are named and arrive knowing the PC (`bond.knows-you`).
  2. A town cast member whose `role_of` matches `lead.words`, chosen by the seeded draw. They are named, and a stranger.
  3. Otherwise, the bare label with a codex block.
- **The face on first sight.**
  - The material adds "What {label} looks like: {appearance}". The appearance is `names.resident_appearance` for cast members, otherwise the face `new_campaign` already rolls.
  - The template carries the same clause.
  - `problems()` adds a **soft** complaint when no word of five or more letters from the appearance appears in the paragraph that first names the label.
  - If both drafts miss, a backstop appends the world's own face line to that paragraph. This is measured first, because 2026-09-17 showed our backstops become tics.
  - Whichever path runs, `lead.described = True` is then set, so Lane A's `settle_descriptions` never owes this face on turn 3.

### 4.8 Roles, seeded picks, one shared set, keepers (item 8)

1. **Roles.** `_role_for` matches against `geography.role_of(world, row)`.
   - It reads the entity's role fact from the candidate keys `Role`, `Occupation`, `Profession`, `Position`, `Title`.
   - If there is none, it uses `row.role`, unless that is generic (`person`, `character`, `npc`, or empty).
   - Otherwise it returns `""`.
   - Matching is by whole word, so Pangrella's long role phrases still match.
2. **Seeded picks.** `cast[len(taken) % len(cast)]` becomes a draw with `Random(f"{story_seed}:cast:{owner}:{slot}")` from the id-sorted candidates.
   - Preference order: an in-town role match; then a match anywhere in the world (fine for a tie in the *past*: "you learned it from Wenna Cobbe of Brindle Ford"); then any in-town person; then the role word itself.
3. **One shared set.** `bind` and `fill_slots` both read and write `scene.spoken_for` instead of a local `set()`. A deliberate reuse (a `from:` slot, or a lead drawn from a tie) bypasses it.
4. **Knows-you on every tied person.** `bind` records each tie's entity id in `scene.acquainted`. The arrival door then applies `bond.knows-you` (origin `background:<id>`) whenever that person arrives. `acquaint` keeps its existing behaviour for the lead.
5. **Keepers.**
   - `name_stock` reads the town's own pool first, via a new additive `names.town_pool(world, location_id)`: the `play.names` row whose `home_id` is the town. Aurvantis ships 64 such rows; Vormoor's holds 16 families (Grimstone, Fellhaven…) that nothing reads today. Next come the cast families, then the people's pool.
   - `name_for` gains a `salt` argument, passed `scene.story_seed`. A keeper is then stable within a campaign (stored once staffed) and different between campaigns.
   - `kin_note` is unchanged.

---

## 5. What the Phase-1 seams must provide

**Trap.** `Campaign.engine()` builds a new `Dice(self.seed)` on every one of its 31 calls (`play/campaign.py:181`). Today `seed` is `None`, which means fresh entropy each time. **If S4 sets `Campaign.seed` to a fixed integer as planned, every turn replays the same dice.** Leave `seed` as it is and add a separate story seed.

| Seam | Name | Type | Old-save default | Notes |
|---|---|---|---|---|
| S4 | `Scene.story_seed` | `int` | `opening._seed_from(campaign.id)` | Set from `secrets.randbits(31)` at creation. It lives on the scene so `rules/` can reach it. `Campaign.story_seed` is a read-only property. |
| S4 | `Scene.start` | `dict` | `{}` | `{"id", "kind", "where", "slots": {name: ref}, "hand_off": {...}, "tells": [str]}`. When it is empty, `situation_for` uses the legacy `SITUATIONS`, byte-identical. |
| S4 | `Campaign.start_id` | `str` | `""` | A mirror, for the roster and home page. |
| S4 | `Scene.spoken_for` | `list[str]` | the entity ids in scheme slots | One set shared by bind, schemes and the lead. |
| S4 | `Scene.acquainted` | `list[str]` | `[]` | `arrive()` grants `bond.knows-you` to matching arrivals. |
| S4 | `arrive()` | — | — | Every `bring` and `fight` goes through it. |
| S5 | `geography.role_of(world, cast_row) -> str` | pure | — | §4.8 |
| S5 | `geography.in_its_own_words(text, scale) -> str` | pure | — | Returns the text unchanged when `scale` is empty or "city". |
| S5 | `geography.display_key(key) -> str` | pure | — | "Urban Life" → "Daily life" |
| S5 | `geography.land_around` and `roads_out` | as in `design-b-space.md` | — | `needs: water` is true when `Land.coast`, when `Land.water` is non-empty, or when any road has `by ∈ {sea, river}`. Lane C only reads these; it does not own them. |
| Engine (unowned) | first aid | behaviour | — | A heal `check` on `state.down.dying`: DC 15 → `stable`. |
| Outcomes | `origin = "start:<id>"` | existing | — | Nothing is written to `turn_log`: `begin_with` counts played turns to spot abandoned starts. The tells go to `Scene.start["tells"]`. |
| API | `begin_with(..., start_town, start_id)`; `/api/state.start = {"id", "kind", "hand_off"}` | — | — | read-only |

---

## 6. Owned edits: confirmed and amended

- **Confirmed.** New `rules/openings.py` and `content/openings/*.json`; `opening.starting_place` and `roll`; `opening_prose.material` and `EXAMPLE`; `campaign.new_campaign`; `schemes._role_for`; `backgrounds.acquaint`; `keepers.name_for`.
- **Added.**
  - `opening.py`: `Situation` (new defaulted fields `look`, `kind`, `hand_off`, `moment`, `start_id`), `situation_for`, `compose`, `suggestions_for`. `SITUATIONS`/`ERRANDS` stay as the legacy path.
  - `opening_prose.py`: `BRIEF` (one line), `problems`, `write`.
  - `campaign.py`: `begin_with`, `_bind_background`, `open_the_story`, `opening_text`. S4 keeps save/load.
  - `schemes.py`: `fill_slots`, `_cast_candidates`.
  - `backgrounds.bind`.
  - `keepers.name_stock`.
  - `names.town_pool`: a new function only.
- **Owner's ruling needed.** The **first-aid branch of `_op_check`** is in no lane, yet both flagship background starts depend on it. Two options:
  - Give Lane C that one branch: a pure `rules/firstaid.py` plus a three-line call.
  - Make it a Phase-1 item.
- **Not Lane C's.** `content/schemes/the-lost-thing.json` (D); `judgement._mentions`/`settle_descriptions` (A); `cards.thread_to_pull` (I4). `cards.from_opening` works unchanged, because it takes a `Situation`.

---

## 7. World-agnostic notes and export asks

**How the three worlds differ, as measured:**

| | Aurvantis | Pangrella | Synthetic |
|---|---|---|---|
| Settlement `kind` | all `CITY` | — | `VILLAGE`/`TOWN`/`CITY` |
| Cast `role` field | always "Person" | always "Person" | real roles |
| Entity `Role` facts | short nouns | long phrases | real roles |
| Name pools | 64 per-town (`home_id`) + 16 per-people | none | one pool |
| Cast per town | 4 | 1–4, one town has 21 | — |
| Villages | yes | none | yes |
| Other | — | — | different fact keys (`Landscape`, `Daily Life`, `Conflict`) |

Nothing keys on a name, an id or a fact label. Facts are read through candidate keys, `needs` uses the app's own place vocabulary, water comes from route `by`, and keepers without pools fall back to cast families and then to the title.

**Export asks** (for `docs/from-world-bible.md`):

| Need | Seen as | Best shape |
|---|---|---|
| Real cast roles | `role: "Person"` × 303 (both worlds) | `role` = the entity's short role noun (≤ 3 words); `role_long` = the phrase |
| Scale-aware stock sentences | 48/64 non-cities say "the city's" | stock sentences keyed on `scale`; `kind` documented as "settlement" |
| Who lives where | inferred from each resident's Identity prose | `play.settlements[].peoples: [people_id…]`, majority first |
| Per-town name pools | Pangrella has none | a `play.names` row per settlement (`home_id`), gender per name |
| Water at a settlement | only route `by` | `play.settlements[].water: coast\|river\|lake\|""` (shared with Lane B) |
| Hooks with a place | `unwritten` has no location | `unwritten[].where_id` |

---

## 8. Tests and the live `starts` script

Tests live in `tests/test_c_*.py` and run over the `worlds` fixture unless marked otherwise. Each docstring records its measurement.

1. `start_town_is_not_always_the_last_village`: over 1,000 seeds (Aurvantis), ≥ 40 towns, and no single town above 8%. *Measured: Vormoor 100%.*
2. `name_no_longer_decides_the_start`: "masta" over 50 seeds gives ≥ 6 start ids. *Measured: 1 name = 1 start.*
3. `same_seed_same_start` and `old_saves_reopen_the_same_way`: with no story seed and an empty `start_id`, the `SITUATIONS` opening comes out byte-identical.
4. `every_shipped_start_validates` and `validator_names_the_fix`: a table of broken documents, one per rule (an `-ing` label, a digit, an undeclared slot, an unknown kind, night, an unknown background).
5. `road_start_waits_for_the_outskirts`: over 1,000 draws, never placed.
6. `bonesetter_start_leaves_a_dying_patient`: hp < 0 and `state.down.dying`; the lead has a square; origin is `start:called-to-the-cage`; `turn_log` is empty.
7. `first_aid_stabilises_at_fifteen`: only if Lane C gets the branch.
8. `material_says_what_kind_of_place`, `example_copies_its_size`, and `size_check_records_the_vormoor_draft`: "sprawling settlement… the city's bustling thoroughfares" is caught, hard, with the words named.
9. `no_city_words_reach_the_model`: 108 occurrences in the Aurvantis material become 0.
10. `role_phrase_is_not_a_name`: "the watchman waving traffic through" becomes "the watchman".
11. `lead_described_at_first_sight`: the face is in the template, and `described` is set.
12. `ties_find_real_roles`: over 200 bonesetter seeds, the tie is always a person whose role is healer, and ≥ 8 distinct people appear. *Measured: always cast[0].*
13. `past_and_first_giver_not_the_same_by_accident`: 0 collisions without a `from:` in 200 seeds.
14. `nobody_is_first_in_every_game`: no first-named person appears in more than 5% of 200 seeds. *Measured: Drenn 100%.*
15. `keepers_take_the_towns_own_families`: the Vormoor keeper's family is drawn from its own pool plus the cast, with ≥ 5 distinct across seeds; Pangrella falls back to cast families; the keeper is stable within a seed.
16. `ten_kinds_in_town`: Aurvantis offers ≥ 8 eligible in-town kinds.

**The live `starts` script** (`tools/narrator_audit.py starts`, R0's harness, run in the serial queue on a quiet Ollama):
- **Runs:** Aurvantis 30 seeds, cycling through the 14 backgrounds plus none; Pangrella and the synthetic world 10 seeds each.
- **Recorded per run:** town, start, kind, lead, problems found, size words in the **shipped** text, whether the face was given on first sight, whether the hand-off was crossed, any invented names.
- **Pass:**
  - Aurvantis reaches ≥ 5 towns and ≥ 8 kinds (checked offline first).
  - Every world:
    - **0** villages or towns called a city;
    - leads described on first sight 30/30 (Aurvantis);
    - 0 hand-offs crossed;
    - 0 invented names;
    - template fallback within baseline + 10 points. There is no baseline yet; record one first.

---

## 9. Open questions for the owner

1. **First aid.** Should the heal-on-dying branch of `_op_check` (DC 15) be Lane C's, or a Phase-1 item? Without it, the bonesetter and ferryman starts hand off to a check the engine cannot resolve.
2. **The picker.** Should a start/town picker ("Surprise me" as the default) ship in Phase 2? That means UI in `home_views`, which has no owner. Or should it wait?
3. **Losable starts.** An untreated patient bleeds out under the engine's own rule (`leave_behind`, `_resolve_dying`). Is that acceptable?
4. **Keepers.** Should a place's keeper differ between campaigns (recommended), or be the same in every game in a world?
5. **Population bands.** The app says village 200–1,200 and city 50,000+; the GameMastery Guide says village 61–200 and large city ≤ 25,000. That line is on the first screen. Should it change?
6. **Exile's weighting.** Should exile be drawn away from its own people (×1/3), and should everyone else be drawn toward their own (×3)?
7. **The quiet floor.** Keep three quiet starts at half weight, or retire them once there are 12 or more documents?
8. **Road starts.** Are the caravan attack and the road-in start the right first road set for I1?
9. **The lost thing.** Should any start deliberately open "The lost thing" via `opens_scheme` once Lane D moves it off hour zero?

*Source note:* the fetch of `tcrf.net/Dragon_Age:_Origins` returned text addressed to language models instead of page content. It was ignored, and nothing here relies on it.
