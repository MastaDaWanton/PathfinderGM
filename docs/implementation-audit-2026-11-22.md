# Implementation audit: skills, feats, spells and class features (2026-11-22)

The owner's request: *go through the skills, feats and spells to figure out which ones are
not fully implemented*, so that lanes can build them overnight *using the same tag
framework for everything we can*. Class features were added to the scope mid-audit.

This document is the audit and the lane plan. Nothing was implemented.

- Branch: `audit/implementation`, off `integrate/0.5.0` `a696ccc8`.
- Per-item ledger: `docs/implementation-audit-2026-11-22.json`. It has one row per spell,
  feat and class feature, plus a per-skill table.

---

## 1. Method

Each verdict is a measurement made in code, as CLAUDE.md asks ("detect mechanically").

| Category | How it was measured |
|---|---|
| **Spells (3,038)** | The critic's independent classifier, which recurses into bundles and does not mirror the condition-clock rule, got 383 / 348 / 2,307 against these 376 / 345 / 2,317. Classified with the engine's **own readers**, imported live under Django against a scratch data dir, at caster level 5. `spells.casting_plan` splits the core dice from the riders. `Engine._executes` decides which rider types run. `engine._ac_grant` decides which AC bonuses land. `Engine._gate_applies` decides which save-gate branches `_magic_gate` applies. A condition lays only with a clock and a none/negates save, per `_condition_term`'s rules, mirrored. **FULL** = every spec runs. **PARTIAL** = some run and some are only rendered onto the tell for the GM. **NARRATED** = nothing runs. A non-FULL spell is also tagged `vocabulary` (every unexecuted spec is a `narrative` spec) or `executor` (a typed spec exists and nothing runs it). The first static mirror disagreed with the live readers on 519 spells, which is why the live readers were used. Script: `spellreal.py` in the session scratchpad. Its output is the JSON's `spells`. |
| **Feats (1,453)** | `content/feats/feats.json` joined to `content/feats/mechanics/core.json`, the only feat-document file. **FULL** = a document with no `not_yet`. **PARTIAL** = a document whose `not_yet` names the missing clause. **NARRATED** = no document. **N/A** = mythic (no tiers in this game, shut in the creator by `creation.feat_rows`) or monster-only. Every tag a document grants was grepped for a reader; all have one (`reactions.unprovoking_tag`, `armour.py`, `position.SHOOTS_INTO_MELEE`, `sheet.DYING_STABILISES`, `sheet.QUICK_DRAW`, `engine` miss-chance reroll). Code-only implementations were found by grepping every feat id and name in `rules/ gm/ play/`: 43 hits, all false positives (mythic twins, the monk bonus-feat list in `leveling.py`, ordinary words like "run"), except Stunning Fist, which runs as the monk class ability. **Takeable** = non-mythic and every prerequisite machine-checkable (`feats.meets` returns `unknown`, and the creator shuts the feat, for an unparsed clause or a `NOT_YET` kind). |
| **Skills (35)** | Traced by hand in code. A use counts as **resolved** only when the engine computes the DC or the opposed roll for that use *and* applies its consequence. The starting point was the existing honesty ledger `content/rules/skills-explained.json` (the creator's "?" text, `uses` plus `not_yet`, mapped 2026-10-06), and every `not_yet` was re-checked against current code. |
| **Class features (12 classes)** | A probe walks each class's `levels` 1–20 and joins every grant to its `class-features` / `class-abilities` document, its option family, or a hand-verified reader. A document with empty `not_yet` is FULL, otherwise PARTIAL. Granted powers (domains, bloodlines, schools, bonds) are FULL with a passive or a using document, **POOL-ONLY** when they have a use-counter and nothing applies the effect. Blood-bending paths were resolved through `resolves`. 21 hand overrides were made after grepping (rage's ladder rungs, spontaneous casting, granted feats, the N/A auras). Every class in `content/classes` can be picked at creation. The world-classes grant only tools and tiers, so they are excluded. Output: the JSON's `class_features`. |

**Priority.** Reach comes first, not the alphabet:

1. The seven core casting classes' lists, Core Rulebook spells, spell levels 0–4, then 5–6.
2. Core Rulebook feats and the common combat chains.
3. What the 15 distinct characters across all 120-odd `pgm-work\*-data` saves actually hold (read-only).
4. What the playtest logs `pgm-work\playtest-2026-11-1*.md` / `-20.md` complained of.

**What the saves hold.**
- Feats: power attack 5, combat reflexes 4, dodge 3, blind-fight 2, quick draw 2, scribe scroll 2, iron will 2, weapon finesse 2, stealthy 2, deceitful 2, toughness 2, and one each of weapon focus, **extra rage**, **defiant luck**, deft hands, **defensive combat training**, **cleave**, **cleaving finish**, endurance, combat casting and fleet. The bold ones do nothing today.
- Spells: acid splash, arcane mark, bleed, burning hands, magic missile, the cantrip spread, **enlarge person** ×2, shield ×2, **expeditious retreat**, obscuring mist, charm person, color spray, sleep, mage armor.

---

## 2. Totals

### Spells: 3,038

| | FULL | PARTIAL | NARRATED | of which NARRATED for want of an executor |
|---|---:|---:|---:|---:|
| All spells | **376** | **345** | **2,317** | 777 (the other 1,540: no vocabulary) |
| Core Rulebook, core-class level 0–4 (353) | 58 | 57 | 238 | |
| Core Rulebook, level 5–6 (138) | 19 | 14 | 105 | |
| Core Rulebook, level 7–9 (133) | 20 | 22 | 91 | |

Per class list, all sources, levels 0–4 (FULL / PARTIAL / NARRATED):

| Class | FULL | PARTIAL | NARRATED |
|---|---:|---:|---:|
| Wizard | 138 | 131 | 957 |
| Cleric | 77 | 73 | 608 |
| Druid | 85 | 58 | 418 |
| Bard | 42 | 68 | 619 |
| Paladin | 24 | 34 | 242 |
| Ranger | 31 | 27 | 332 |

**Spells holding an unexecuted spec, by spec type.** One spell can count under several types.
- narrative 2,436
- permission 279
- situational_mod 231
- combat_mod (non-AC) 124
- spell_effect 106
- skill_mod 96
- save_mod 74
- ability_mod 64
- speed 52
- sense 41
- damage_reduction 38
- remove_condition 18
- apply_condition 17, plus 12 more with no clock or a partial save
- temp_hp 15
- fast_healing 13
- ability_damage 13
- resistance 7

**The headline finding: numeric buffs are never applied.** `Engine._EXECUTES` has no entry for `ability_mod`, `save_mod`, `skill_mod`, non-AC `combat_mod`, `speed`, `temp_hp`, `resistance`, `damage_reduction`, `fast_healing` or `remove_condition`. So Bless, Aid, Prayer, Heroism, Divine Favor, the six animal-name ability buffs, Resistance, Guidance, True Strike, Magic Weapon, Stoneskin, Expeditious Retreat, Remove Fear, Lesser Restoration and every other buff spell is only told.

`tests/test_casting_executes.py::test_a_buff_is_shown_to_the_gm_rather_than_invented` pins this. Its reason ("the spell's duration is still prose") is **no longer true**:
- `spells.duration_rounds` exists.
- The read layer carries a duration on 2,585 spells.

The applicator exists too: `consumables._spec_to_intents` already maps every one of those types onto `buff`/`grant`/`temp_hp`/`resistance` intents for potions, and `Actor.add_buff` is typed, timed, scoped by `when`, and an `ActiveEffect`. This is the cheapest large win in the audit.

Routing those ten types through `_spec_to_intents`:
- turns 46 NARRATED spells FULL and 253 NARRATED spells PARTIAL;
- in Core-class level 0–4 lists, that is 37 FULL and 192 PARTIAL;
- adding `situational_mod` with its `when` raises it to 76 FULL and 375 PARTIAL.

**The second finding is a live correctness bug: 341 of the 376 "FULL" spells are the
unreviewed regex layer, and some of them deal damage that does not exist.**
- The hand-read layer (`content/spells/mechanics/part-01..20.json`) skipped exactly the 354 spells `spells-mechanics.json` already covered, so those stand as a regex made them.
- `spells.casting_plan` confirmed, at caster level 7:
  - dimension door: a flat 1d6 untyped, Will negates
  - meld into stone: 5d6
  - blink: 1d6
  - snare: 1d6
  - shillelagh: a flat 1d8, Will negates
  - phantasmal killer: 3d6, Fort partial (not death)
  - wall of iron: 10d6
  - forbiddance: 6d6
  - **web: 2d4 fire, Reflex negates**
  - ethereal jaunt: 1d6
  - glyph of warding: 3d8 on cast
- `_op_cast` rolls these at the target. **Reproduced by the critic with a driven cast:** web at caster level 7 dealt "the thug takes 3 fire" (13 → 10 hp) and turned him hostile. Dimension door hit for 1d6 on a failed Will save. Fifty CRB non-evocation spells in that layer run dice and need reading. That list is the JSON rows with `layer: "regex (unreviewed)"`.
- The 11-spell veto in `test_casting_executes.py` catches none of the above.

**Smaller spell defects.**
- `casting_plan.take()` drops the other failure branches of a save-gate whose failure branch holds the damage, without telling anyone. That affects 13 spells, 8 of them typed (bleed, ectoplasmic snare, geyser, greater interrogation, nightmare, resonating word, sirocco, sunbeam).
- The summon executor `Engine._summon` exists, but **no spell carries a `summon` spec**. Summon Monster I–IX and Summon Nature's Ally I–IX are all NARRATED.

### Feats: 1,453

| | FULL | PARTIAL | NARRATED | N/A |
|---|---:|---:|---:|---:|
| All | **63** | **8** | **1,215** | 167 (mythic 158, monster-only) |
| PFRPG Core (175) | 55 | 7 + Stunning Fist | 112 | 0 |
| APG / UC / UM / ARG | 8 / 0 / 0 / 0 | 0 | 158 / 254 / 110 / 184 | |

- **939 feats are takeable**: non-mythic, prerequisites readable. **871 of them do nothing.** Another 348 are shut in the creator because a prerequisite clause is unreadable. That is the app's shortcoming, said on the page.
- PARTIAL clauses (from each `not_yet`):
  - Blind-Fight: an invisible attacker's melee advantage, and movement while blind.
  - Diehard: acting while disabled below 0.
  - Endurance: five clauses, all with no host rule.
  - Improved Unarmed Strike: counts as armed / threatens.
  - Master Craftsman: caster level for the craft feats.
  - Power Attack: touch attacks are not excluded.
  - Quick Draw: throwing at the full attack rate, and drawing hidden weapons.
  - **Stunning Fist**: runs only as the monk's class ability. A non-monk who takes the feat gets no uses.

NARRATED Core feats by the machinery they need (hand-sorted; the JSON's `why` is a regex triage over the other 1,100):

| Machinery | Core feats |
|---|---|
| Attack toggles in Power Attack's `choice` grammar | Combat Expertise, Deadly Aim |
| Attack shape / action economy | Vital Strike ×3, Cleave, Great Cleave, Two-Weapon Fighting ×3, Double Slice, Two-Weapon Rend, Rapid Shot, Manyshot, Spring Attack, Whirlwind Attack, Shot on the Run, Mobility, Step Up, Stand Still, Lunge, Ride-By Attack, Spirited Charge, Shield Slam, Pinpoint Targeting, Lightning/Wind Stance |
| Crit-threat and crit-rider docs | Improved Critical, Critical Focus, Bleeding/Blinding/Deafening/Exhausting/Sickening/Staggering/Stunning/Tiring Critical, Critical Mastery |
| Plain modifier docs (grammar already expresses them) | Improved Great Fortitude/Iron Will/Lightning Reflexes (reroll), Far Shot, Two-Weapon Defense, Shield Master, Improved Shield Bash, Defensive Combat Training (CMD = HD), Acrobatic Steps / Nimble Moves (terrain), Run |
| Skill uses | Improved Feint, Greater Feint, Dazzling Display, Catch Off-Guard, Throw Anything, Improvised Weapon Mastery, Deflect Arrows, Snatch Arrows |
| Class pools | Extra Rage/Channel/Ki/Lay on Hands/Mercy/Performance, Improved Channel, Selective Channeling, Alignment/Elemental Channel, Command/Turn Undead, Channel Smite, Natural Spell, Improved Familiar |
| Metamagic (all 9 core, 40 total) | Empower, Enlarge, Extend, Heighten, Maximize, Quicken, Silent, Still, Widen |
| Spell hooks | Augment Summoning, Spell Mastery, Improved Counterspell, Arcane Strike, Eschew Materials |
| Item creation (8) | The benches replace these on purpose. N/A by ruling until an owner decision says otherwise. |
| Other | Leadership (a cohort is a companion actor), Gorgon's Fist / Medusa's Wrath / Scorpion Style (style chain), Disruptive / Spellbreaker, Penetrating Strike ×2, Strike Back, Mounted Combat / Mounted Archery / Trample / Unseat |

### Skills: 35, about 100 CRB uses

- About 45 uses are resolved, about 28 narrated only and about 27 absent. The use list is from memory of the CRB, least certain for Appraise, Perform and Handle Animal.
- **Strong**: Perception, Stealth, Diplomacy, Intimidate, Craft, Profession, Survival, Disable Device, Swim.
- **No resolved use at all**: Use Magic Device (no wands or scrolls exist), Fly, Ride, Linguistics, Handle Animal, Perform, Appraise, Sense Motive (the PC's own), and Knowledge in 7 of its 10 subskills.
- **The honesty ledger is stale in 11 of 35 entries** (Climb only partly). Each `not_yet` below is now false:
  - Climb (**partly** stale): `dungeons.climb_out` slips back, but only out of a dungeon pit. "Climbing is not a way of moving" is still true.
  - Diplomacy: `requests.py` / `Engine._make_request`.
  - Disable Device: traps, `dungeons.disarm_lands`.
  - Disguise: `Engine._op_disguise` persists, and `disguise.passes` is read.
  - Escape Artist: `Engine._escape_from`.
  - Intimidate: `Engine._demoralize`.
  - Perception: `dungeons.searched` / `arrived`.
  - Sleight of Hand: the take moves.
  - Stealth: `Engine._stealth_lands`.
  - Survival: `Engine._op_live_off_land`.
  - Swim: `Engine.swim`.
- `tests/test_skill_help.py` checks every `uses` anchor and never checks a `not_yet`. That is how this ledger aged.

Top skill gaps by how often play hits them:
1. **Feint.** Aliased to Bluff and rolled with no consequence. It is the rogue's sneak-attack enabler.
2. **Acrobatics tumble.** No DC vs CMD, and `reactions.py` knows only the 5-ft step and withdraw.
3. **Knowledge monster lore.** DC 10 + CR exists only as out-of-character text in `play/gm_answers.py`.
4. **Perception against ambush.** There is no surprise round.
5. **Heal against bleed.** `Engine._rider_bleed`'s tell (engine.py ~23346) promises "until a DC 15 Heal check or magical healing". `firstaid` only treats the dying, and `Actor.heal` removes no bleed. The engine makes two promises it does not keep.
6. **Heal**: treat poison, treat disease, long-term care.
7. **The PC's own Sense Motive.**
8. **Use Magic Device.**
9. **Acrobatics**: soften a fall, jump distances.
10. **Ride, Handle Animal and Spellcraft**: identify a spell as it is cast.

### Class features: 12 classes, levels 1–10 first

Levels 1–10, by verdict:

| Class | FULL | PARTIAL | NARRATED | Option-family headline |
|---|---:|---:|---:|---|
| Barbarian | 4 | 2 | 0 | rage powers: 8 FULL / 20 NARRATED of 28 |
| Bard | 2 | 4 | 7 | perform types 9/9 NARRATED |
| Blood Bending | 6 | 1 | 4 | paths: 16 FULL / 9 PARTIAL / **14 REFUSED** / 23 NARRATED of 62 |
| Cleric | 2 | 1 | 0 | domain powers: 20 FULL / 11 PARTIAL / **36 POOL-ONLY** / 4 NARRATED of 71 |
| Druid | 2 | 1 | 5 | |
| Fighter | 2 | 2 | 0 | |
| Monk | 9 | 4 | 3 | **flurry of blows NARRATED (no code)** |
| Paladin | 3 | 4 | 1 | mercies 12/15 FULL |
| Ranger | 3 | 2 | 4 | |
| Rogue | 4 | 2 | 0 | **rogue talents 23/23 NARRATED** |
| Sorcerer | 4 | 0 | 0 | bloodline powers 1–10: 12 FULL / 8 PARTIAL / 5 POOL-ONLY / 5 NARRATED |
| Wizard | 2 | 0 | 0 | school powers: 8 FULL / 4 PARTIAL / 8 POOL-ONLY / 6 NARRATED; bonded object POOL-ONLY; familiar has no creature |

Central gaps at levels 1–10:
- **Monk:** flurry of blows; ki's extra attack.
- **Rogue:** all talents. The `grants_feat`, `sneak_attack` and `once_per_rage` keys have no reader.
- **Barbarian:** 20 rage powers.
- **Cleric and the other casters:**
  - 36 domain powers are POOL-ONLY: Touch of Chaos, Bit of Luck, Bleeding Touch, the weapon blades.
  - Channel energy has no Selective Channeling and no burst radius without a map.
- **Druid:** wild shape has no elemental/plant forms and no form movement or senses. Five druid features are NARRATED, including nature sense and wild empathy.
- **Bard:** bardic knowledge, versatile performance, countersong.
- **Paladin:**
  - The auras' ally +4 is missing.
  - The lay-on-hands document's `self_action: "swift"` is read by nothing, so healing yourself costs a standard action.
- **Ranger:** favored enemy's skill terms are dropped (skill rolls carry no target). Track's +½ level and wild empathy are missing.
- **Saves:** bravery, still mind, trap sense and the like have no save or skill descriptor. `effectspec.AGAINST` has `fear`/`enchantment`/`trap`; the callers do not pass them.
- **Blood Bending:** 14 path abilities are refused before payment (`engine.py:32320`). Their `needs` says a computed DC is missing, while their `effects` already carry `dc: 10 + level/2 + con_mod`, so the honesty field looks stale.

The shared machinery the class gaps need (counts across levels 1–20):

| Machinery | Gaps |
|---|---:|
| Save and skill descriptors | ~16 |
| Movement modes and terrain | ~13 |
| Bearer-centred auras | ~11 |
| Plain modifier documents | ~10 |
| Cast-op hooks (metamagic, unprepared cast) | 8 |
| Ability-check roller | 7 |
| d20 reroll, roll twice | 7 |
| Timed weapon property | 5 |
| SLA run by rounds | 5 |
| Extra attacks | 5 |
| On-hit / on-damaged triggers | 5 |
| Companion completion | 5 |
| Senses from a power | ~5 |
| Morning pick | 3 |
| Periodic damage | 3 (possibly stale: bleed runs) |
| Single-use "next roll" bonus | ~3 |

---

## 3. Three-law findings

Only one item breaks a law in the strict sense, the `swift strikes` name-match under law 1. The rest are stale honesty text, silent fields, and state the laws arguably reach. All are listed so a ruling can be made.

1. **Law 3 / honesty: a tell promises rules nobody resolves.** `Engine._rider_bleed` tells "until a DC 15 Heal check or magical healing". No Heal use and no cure removes bleed.
2. **Law 3 / honesty: stale "not yet" text in three places.**
   - 11 of the 35 skill `not_yet` lines (above).
   - `spells.casting_plan`'s `note` ("duration … is still prose") is false.
   - The `needs` on the blood-bending paths.
3. **Law 2: a silent field.** `content/class-abilities/paladin.json` `self_action` is read by nothing. `class_abilities.validate_documents` has no key whitelist, unlike class-features' `DOC_KEYS`, which is how it got in. A field the validator accepts and nothing applies is the "a number added outside the funnel" failure in reverse: a rule that silently is not.
4. **Law 2: cooldown state outside `ActiveEffect`.** `Scene.swayed` (the once-a-day limit for Diplomacy and Intimidate) and `scene.dealings` (haggle and judge-make daily keys) are dicts of timestamps. They are not numbers in the funnel, but they are a second store of timed state. **Needs an owner ruling** on whether law 2 covers them.
5. **Law 1: name-matched abilities.**
   - `rules/engine.py:10023` `has_passive(actor, "swift strikes")`, plus two Blood Bending names. These are pinned at their ceilings by `tests/test_three_laws.py`.
   - `rules/precision.py:64` finds sneak attack by a regex over the class table's English (`sneak attack NdN`). It sits outside the ratchet.
   - The ratchet's name list covers Blood Bending names and five feats only. Rage, smite, channel, wild shape and ki are unguarded. The engine is clean of them today; nothing keeps it so.
6. **Law 2: a minor bare sum.** `rules/sheet.py:2672/2675` sums land-speed class and feat terms with `sum()` rather than `dice.stack`. It is commented as correct while every term is untyped.
7. **Law 1: `attitude._sleep_spec`** matches condition keys and runs a regex over a note's English.
8. **Law 2 and the regex spells.** The 341 unreviewed FULL spells put numbers into play that no person checked. Web's fire damage enters through the right door (`_apply_damage`), but the number is a machine's misreading of prose. That is "no model authors a number" by another route.

No string-matched conditions were found in the skill, class-ability, class-feature or granted-power code (`grep '"<condition>" in …conditions'` returns nothing). The rage and performance drain is `ActiveEffect.periodic`, not a second ticker.

---

## 4. Prior art

Researched before the lanes were designed, per the standing instruction. URLs are primary sources unless marked otherwise.

**Foundry VTT, PF1 system.**
- A *Change* is `{operator, target, type, priority, formula}`; flags and context notes are separate ([wiki](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/wikis/Help/Items/Changes)).
- What they abandoned, from the [CHANGELOG](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/raw/master/CHANGELOG.md):
  - 10.0: "Script change support has been removed." The "function" operator went too, "with no replacement". They retreated to declarative formulas only.
  - 10.0: `penalty` removed as a bonus type.
  - Dice in Changes: 10.0 maximises them "with exception of deferred rolls (damage and skill checks)". 0.77.10 had already deferred attack and damage changes to the roll, and 11.0 defers ability checks too.
  - 0.77–11.0: years of sync bugs between a buff item and its copied Active Effect, until 11.0: "Active Effects no longer control active state of buffs".
  - Duration-end bugs (1-turn, a round early, infinite) recurred across 10.0, 10.5 and 10.8. 10.0 made spells and buffs share one duration configuration.
- Power Attack is an attack-dialog option, not a buff. Conditionals (per-attack toggles) produced several bugs:
  - default-on always applied (0.80.22);
  - lost when the dialog was skipped (0.80.16);
  - applied only to the first attack (0.81.1).
- **Metamagic was never built.** Issues #17 and #1069 are open, and users duplicate spell entries ([issues](https://gitlab.com/api/v4/projects/foundryvtt_pathfinder1e%2Ffoundryvtt-pathfinder1/issues?search=metamagic)).
- **Summons have no executor.** The open issues ask only for reference lists.
- Foundry core v11 let effects stay on the item and still apply. The copy-onto-the-actor model, whose `origin` pointer "historically had problems" with unlinked tokens and compendia, is **still the default**: `CONFIG.ActiveEffect.legacyTransferral` defaults to true, and non-transfer is opt-in ([v11 article](https://foundryvtt.com/article/v11-active-effects/)). Our ledger's refusal of a stored effect per feat points the same way, but v11 did not abolish the copy.

**PCGen.**
- Syntax: `BONUS:<cat>|<target>|<formula>|PRExxx|TYPE=x`. The same type takes the highest; the stacking types are listed in a game-mode file; negatives "have been found to stack even when they have matching types". A BONUS cannot be cleared, only countered ([docs](https://raw.githubusercontent.com/PCGen/pcgen/master/docs/listfilepages/globalfilestagpages/globalfilesbonus.html)).
- `TEMPBONUS` replaced `PREAPPLY` for buffs. **I found no duration field.** The inference that temporary bonuses are toggled by hand is unconfirmed.
- The project went into archive mode with its formula-layer rewrite unfinished ([EN World](https://www.enworld.org/threads/pcgen-entering-archive-mode.669245/), secondary).

**Owlcat (Kingmaker / Wrath).**
- Abilities are compositions of components: deliver, then `AbilityEffectRunAction` (per-target actions, with `AbilityEffectMiss` for the missed), over one shared execution context ([modding wiki](https://github-wiki-see.page/m/WittleWolfie/OwlcatModdingWiki/wiki/%5BWrath%5D-Abilities)).
- Toggles are `BlueprintActivatableAbility`, which applies a buff on activation and removes it on deactivation.
- `ContextRankConfig` takes **one** rank source per value ([API](https://wittlewolfie.github.io/WW-Blueprint-Core/api/BlueprintCore.Utils.Types.ContextRankConfigs.html)).
- A duration value carries `isExtendable`: Extend is declared per value, not inferred ([API](https://wittlewolfie.github.io/WW-Blueprint-Core/api/BlueprintCore.Utils.Types.ContextDuration.html)).
- Kingmaker merged PF1e's skills into use categories (Persuasion = Bluff/Diplomacy/Intimidate, Athletics, Mobility, Trickery …) and kept bonuses able to target one use ([Kickstarter update #23 via RPG Codex](https://rpgcodex.net/article.php?id=10685)).
- **Could not confirm:** Owlcat's Power Attack blueprint, how Empower/Maximize hook damage, and why Wish/Simulacrum were cut.

**Fantasy Grounds.**
- Effects are strings such as `ATK: 1; DMG: 1`. Any clause without a known tag "is treated as descriptive text only", so a typo silently becomes flavour.
- The docs claim 80–90% of the rules are covered ([docs](https://fantasygroundsunity.atlassian.net/wiki/rest/api/content/996643237?expand=body.view)).
- A community extension exists only to build those strings from forms ([FG Effect Builder](https://github.com/SoxMax/FG-Effect-Builder)).

**Lessons taken into the lanes.**

1. A buff is **one** `ActiveEffect` holding its typed modifiers. It is never a record linked to a second record (Foundry, 0.77 to 11.0). That is our law 2 already.
2. Dice never enter a stored total. Divine Favor-style dice are a roll-time term (Foundry 10.0 / 0.80.21).
3. Duration end timing gets its own tests, and spells share the one duration source (Foundry 10.0 / 10.5 / 10.8). Here that source is `spells.duration_rounds`.
4. No scripts in data: a closed set of executors with validators that name the fix (Foundry 10.0, PCGen, Fantasy Grounds). This is what `classbuilder.validate_feat_documents` and `effectspec.validate` already are.
5. Attack toggles reuse Power Attack's `choice`. Attack-shape feats (Vital Strike, TWF, Rapid Shot, Cleave) belong in the attack pipeline, not the stacking funnel. Iterative and extra attacks get explicit tests, because Foundry's conditional applied only to the first attack.
6. Metamagic is a transform of a **copy** of the spell at cast time: effective slot level, ×1.5 variable dice, maximised dice, doubled durations. Spells known are never consumed, and nothing is duplicated in data (Owlcat `isExtendable`; Foundry #379, #1369).
7. Skill uses are named data rows with their own DC formula, action and outcome, which feats can target (Owlcat use categories). Our analogue is a `skill-uses` table keyed `skill.<skill>.<use>`.
8. Summons need **data**: a per-level table pointing at bestiary ids, with the duration, dismissal and the caster as source. Nobody shipped that data well, so expect to write it.

---

## 5. Lane plan

Six lanes, grouped by **shared machinery**. Each lane owns disjoint content files and adds its own methods to `rules/engine.py`, so that conflicts are separate hunks. Each lane:
- branches off fresh `integrate/0.5.0`;
- runs the full suite with `-n 12` (suite-workers ruling) plus `tests/test_three_laws.py`;
- names the measured defect in every test docstring.

All of them run on the existing vocabulary:
- `ActiveEffect` via `Actor.apply_effect` / `add_buff`;
- `has_state` prefix tags;
- `Intent.origin` of `spell:<id>` / `ability:<path>/<key>` / `rule:<id>`;
- `effectspec.validate`;
- `classbuilder.validate_feat_documents`.

**Data ownership rule (from the critic pass).** The spell mechanics loader layers every
`content/spells/mechanics/*.json` in sorted order, and the later file silently wins. Feat
documents work the same way: a duplicate id across files is won by the later one, and nothing
refuses it. So:

- **Every regex-only spell id belongs to Lane B's `part-21.json` and to no other lane.**
  - Nine of Lane A's and C's priority spells are regex-only: bless, shield of faith, the six
    animal-name ability buffs, and resist energy.
  - Lane A wires the executor against their existing curated effects (`spells.CURATED`), and
    sends any data correction for them to B.
  - Lane C's resist energy choice field is written by B in part-21 to C's spec.
- Each lane's new feat documents go in its own file:
  - D: `combat.json`
  - C: `summoning.json`
  - E: `skills.json`
  - F: `pools.json`
  - `core.json` is touched by no lane.
- Shared test file: `tests/test_casting_executes.py` is edited by A (the buff test) and B (the
  veto list). Keep the hunks apart.
- Shared class file: `content/class-abilities/monk.json` is edited by D (flurry) and F (Extra
  Ki's pool). D edits only the flurry entry, F only the ki pool's `max`.

### Lane A: Spell buffs as timed ActiveEffects

The biggest reach for the least code.

- **Machinery.** In `_op_cast`'s rider block, route the riders `ability_mod`, `combat_mod` (non-AC), `save_mod`, `skill_mod`, `speed`, `temp_hp`, `resistance`, `damage_reduction`, `fast_healing` and `remove_condition`, plus `situational_mod` with its `when`, through the existing `consumables._spec_to_intents`:
  - rounds come from `spells.duration_rounds(spell, cl)`;
  - origin is `spell:<id>`;
  - recipients are the cast's targets, with `recipient: "caster"` honoured.
- A **harmless** `save_gate` (enlarge person) applies its failure branch to a willing target without a roll.
- Dice-bearing buffs roll once at cast and store the total (Aid's 1d8 + CL temporary HP).
- Pass the rounds explicitly: `_spec_to_intents` defaults a spec with no duration to one hour (consumables.py ~548).
- Correct readings that ship wrong. Divine Favor's document is a flat +1, where the CRB gives +1 per three caster levels, to +3. FULL means every spec runs, not that each is right.
- Retire the stale `casting_plan` note, and rewrite `test_a_buff_is_shown_to_the_gm_rather_than_invented` into its opposite, with the measurement in the docstring.
- **Items, in priority order.** Bless, Bane, Shield of Faith (already applied; regression guard), Divine Favor, Aid, Prayer, Heroism, Resistance, Guidance, Bull's Strength, Cat's Grace, Bear's Endurance, Owl's Wisdom, Fox's Cunning, Eagle's Splendor, Enlarge Person (and Reduce, and the masses), Magic Weapon, Magic Fang, True Strike, Expeditious Retreat, Longstrider, Jump, False Life, Remove Fear, Lesser Restoration (`remove_condition` plus ability damage), Remove Paralysis, Remove Blindness/Deafness, Stoneskin, Protection from Arrows, Good Hope, Crushing Despair, Divine Power, Rage, the numeric halves of Haste and Slow, Protection from Evil's situational terms, Death Ward.
- **Files.** `rules/engine.py` (the rider block of `_op_cast`, plus one new helper `_cast_buff_riders`), `rules/spells.py` (the note), `content/spells/mechanics/part-01..20.json` (corrections to the named spells only), new `tests/test_spell_buffs.py`, `tests/test_casting_executes.py`.
- **New vocabulary.** None. Possibly `effectspec` `bonus_type` checks; "armour" already exists.
- **Realistic in about 8 hours.** The wiring plus about 30 of the CRB items, verified with tests. By measurement that flips about 37 core level 0–4 spells to FULL and about 190 to PARTIAL.

### Lane B: Spell data truth (read the regex layer) and save-or-condition completion

- **Machinery: data first.** Read by hand the 354 spells only the regex layer covers, into a **new** `content/spells/mechanics/part-21.json`. Those ids appear in no `part-01..20` file, so this cannot collide with Lane A.
  - Start with the confirmed misreadings: web, dimension door, meld into stone, blink, snare, shillelagh, phantasmal killer, wall of iron, forbiddance, ethereal jaunt, glyph of warding.
  - Then the rest of the 50 CRB non-evocation spells in that layer.
- Then the save-or-condition path:
  - `casting_plan.take()` must keep, not drop, the non-damage failure branches of a core save-gate (13 spells).
  - `apply_condition` with a partial save (12).
  - Conditions blocked only for want of a clock where the spell's own duration answers it.
  - The CRB save-or-suck spells whose condition branch is a `narrative` because the condition was missing from `states.TAGS`:
    - command, which needs a compulsion tag under the mind gate;
    - suggestion;
    - blindness/deafness, contagion, bestow curse (`curses.py` exists), ray of enfeeblement (an `ability_damage`-like penalty), touch of idiocy;
    - poison, through the affliction executor `Actor._afflicted`;
    - hold portal and arcane lock as door tags.
- **Files.** New `content/spells/mechanics/part-21.json`, `rules/spells.py` (`casting_plan.take`), `rules/engine.py` (`_condition_term` and `_gate_rider` only), `rules/states.py` (new `TAGS` rows under existing families, e.g. `state.compelled.*` under the mind gate), new `tests/test_spell_readings.py`, and extending the veto test.
- **Overlap.** `rules/states.py` is shared with Lane E, if E adds `state.feinted`. Assign `states.py` additions to B, or agree to append-only rows.
- **Realistic.** About 120 of the 354 read and corrected, all 11 confirmed misreadings among them, plus the `take()` fix and 6–8 condition spells. The rest of the 354 is a follow-up lane. Say so in the merge note.

### Lane C: Cast-time choices (summons, chosen elements, metamagic)

- **Machinery.** One idea, three uses: a choice made when the spell is cast. It is carried on the cast intent's params, validated against the document's own list, and never invented by the model.
  1. **Summons.**
     - A new `content/spells/summon-tables.json`: Summon Monster I–IX and Summon Nature's Ally I–IX, level to bestiary ids (CRB tables).
     - A `summon` spec with `choose_from: <table level>` and `count` (1, 1d3 at one level lower, 1d4+1 at two lower).
     - `Engine._summon` takes the chosen id, and the rounds come from `duration_rounds`. It already holds a `Manifestation`.
     - Augment Summoning becomes a feat document (in `content/feats/mechanics/summoning.json`): +4 enhancement Str/Con on arrivals, as an `ActiveEffect` with source `feat:augment-summoning`.
  2. **Chosen element.** Resist Energy, Protection from Energy, Energy Immunity's `choice_at_cast`. This closes the gap docs/spells.md §5.3 names.
  3. **Metamagic.** A new `rules/metamagic.py` transforms a **copy** of the spell for the cast:
     - Extend doubles `duration_rounds`.
     - Empower multiplies the variable dice total by 1.5.
     - Maximize maximises the dice.
     - Enlarge doubles range.
     - Silent and Still drop V and S for the components gate.
     - Each raises the slot level, checked by `casting.py` at prepare and cast for prepared casters and at cast for spontaneous ones (who also pay a full-round cast).
     - Quicken and Heighten come second.
- **Items, in priority.** Summon Monster I–IV, Summon Nature's Ally I–IV, Augment Summoning, Resist Energy, Protection from Energy, Extend, Empower, Maximize, Silent, Still, Enlarge, then Quicken and Heighten.
- **Files.** New `content/spells/summon-tables.json`, new `rules/metamagic.py`, `rules/casting.py` (the slot-level check), `rules/engine.py` (one transform call at the top of `_op_cast`, and `_summon`), `rules/effectspec.py` (the `choose_from` / `choice_at_cast` fields), new tests.
- **Overlap.**
  - `_op_cast` is shared with A and B. Keep C's call at the top, A's in the rider block and B's in `casting_plan`, so the hunks are separate.
  - `effectspec` is shared with B only if B adds fields.
- **Realistic.** Summons I–IV of both families, Augment Summoning, the chosen element, and four metamagic feats (Extend, Empower, Maximize, Silent/Still). That is about 16 spells and 5 feats.

### Lane D: Attack-shape combat feats and extra attacks

- **Machinery.**
  1. Attack toggles in Power Attack's existing `choice` grammar: Combat Expertise (−attack/+dodge AC, BAB-scaled), Deadly Aim, Piranha Strike.
  2. Feat **actions**, the open "feat actions have no `find_ability` branch" line in the ledger:
     - Vital Strike, Improved and Greater (a standard-action attack that multiplies weapon dice);
     - Cleave and Great Cleave (a second attack on an adjacent foe at −2 AC).
  3. Extra attacks in the full attack:
     - Two-Weapon Fighting, Improved and Greater, Double Slice, Two-Weapon Defense. `sheet.py:3223` says no off-hand swing is offered.
     - Rapid Shot and Manyshot.
     - **Monk flurry of blows**, ki's extra attack, and haste's extra attack, all in the same "extra attack at a penalty" field.
  4. Crit-range and crit-rider documents: Improved Critical (the sheet already does the keen arithmetic), Critical Focus, and the core `*Critical` riders through the existing condition doors.
  5. Mobility (+4 dodge AC against movement-provoked AoO, as a `when`).
- **Files.**
  - New `content/feats/mechanics/combat.json`. `feats.documents()` loads every `*.json` in the folder, so there is no edit to `core.json`.
  - `rules/engine.py` (`_op_attack`'s full-attack loop and a new feat-action branch).
  - `rules/sheet.py` (attack modifiers).
  - `rules/classbuilder.py` (new grammar fields: `extra_attacks`, `dice_multiplier`, `feat_action`).
  - `content/class-abilities/monk.json` (flurry).
  - New `tests/test_attack_feats.py`.
- **Overlap.**
  - `rules/sheet.py` attack modifiers are shared with Lane F's descriptor work, which touches saves and skill modifiers, not attack. Separate functions.
  - The monk document is shared with F (Extra Ki). D edits only the flurry entry.
- **Realistic.** Combat Expertise, Deadly Aim, the Vital Strike chain, Cleave, the TWF chain, Rapid Shot, Improved Critical, Critical Focus, Mobility and flurry. That is about 12 feats and 1 class feature. Manyshot, Spring Attack, Whirlwind and Step Up are the follow-up.

### Lane E: Skill uses with DC tables

- **Machinery.** A new `content/rules/skill-uses.json`: rows keyed `skill.<skill>.<use>` with the DC formula, the action cost and the outcome, in effectspec terms. A new `rules/skilluses.py` resolves them through `_op_check` and the one applicator. Feats target the use id. Then fix the stale honesty ledger and add a test that every `not_yet` clause is checked against a grep anchor, so a stale line fails the suite as a stale `uses` line already does.
- **Items, in priority.**
  1. **Feint**: Bluff vs 10 + BAB + Wis, or vs Sense Motive, whichever is higher. The target loses Dex to AC against the feinter's next melee attack, via a tag such as `state.dex_denied.to.<ref>` read by `loses_dex_to_ac`, ending on that attack or the next turn. Plus Improved Feint (move action) and Greater Feint.
  2. **Acrobatics tumble**: DC = CMD, +10 through a square, half speed, with a `reactions.py` waiver tag `movement.unprovoking.<ref>` in the existing `maneuver.unprovoking` style.
  3. **Knowledge monster lore**: DC 10 + CR (5 for common), the type-to-skill map from `play/gm_answers.py` moved into data, and a `knows.creature.<template>` tag on the observer. The tell names facts only on success, so the narrator gets only what was learned.
  4. **Heal**: staunch bleed (DC 15 removes the bleed effect; this fulfils the existing tell's promise), treat poison and disease (the patient's next save gets a circumstance term), long-term care (doubled rest healing in `_op_rest`).
  5. **Dazzling Display**: demoralize everyone within 30 ft.
  6. **The PC's own Sense Motive**: a hunch, and sensing enchantment against `state.charmed`.
- **Files.** New `content/rules/skill-uses.json`, new `rules/skilluses.py`, new `content/feats/mechanics/skills.json` (Improved/Greater Feint, Dazzling Display), `rules/engine.py` (dispatch, `_op_rest`'s Heal term), `rules/reactions.py` (the tumble waiver), `rules/sheet.py` (`loses_dex_to_ac` reading the feint tag), `gm/judgement.py` (declaring feint and tumble from the player's words, in the closed-reader style), `content/rules/skills-explained.json`, tests.
- **Overlap.**
  - `states.py` with B: append-only rows.
  - `gm/judgement.py` with nobody else.
- **Realistic.** Feint with its two feats, tumble, monster lore, Heal's three uses, Dazzling Display, and the 11 stale ledger lines plus their ratchet. That is about 8 uses and 3 feats.

### Lane F: Class and feat pools, passive documents, descriptors

- **Machinery.**
  1. **Pool readers for Extra-X feats.** A `pool.max` formula term counting held copies of a feat: Extra Rage, Channel, Ki, Lay on Hands, Mercy, Performance. Then Selective Channeling (a `choice` of excluded refs), Improved Channel (+2 DC to channel), and Channel Smite.
  2. **The rogue talents' keys.** Readers for `grants_feat` (Combat Trick, Finesse Rogue, Weapon Training, Feat), plus Bleeding Attack (the bleed executor exists), Surprise Attack, Fast Stealth. Also the 20 rage powers that are plain modifiers or tags.
  3. **Plain modifier documents** for bardic knowledge, nature sense, track (+½ level Survival), lore master, jack of all trades, wild empathy (a Diplomacy-like check against animals).
  4. **Save and skill descriptors.** The save callers pass `against: fear / enchantment / trap / poison / charm / compulsion`, which are already in `effectspec.AGAINST`, so bravery, still mind, trap sense ×2, indomitable will, well-versed and resist nature's lure stop being dropped.
  5. Close `self_action` (paladin, swift self-heal), and add a key whitelist to `class_abilities.validate_documents`.
  6. Unblock the 14 REFUSED blood-bending path abilities whose `effects` already carry a DC. Re-read their `needs` first.
  7. Extend the three-law ratchet to the core class-ability names.
- **Files.**
  - `content/class-abilities/*.json`, `content/class-options/rogue-talents.json` and `rage-powers.json`.
  - New `content/feats/mechanics/pools.json` (the Extra-X feats).
  - `rules/class_abilities.py` (pool max, the validator whitelist).
  - `rules/engine.py` (only the save callers' `against`, `_op_save` and the cast's saves; the use-ability self-action).
  - `rules/sheet.py` (save and skill modifier contexts).
  - `content/classes/blood-bending.json`, `tests/test_three_laws.py`.
- **Overlap.**
  - The cast's save call is shared with B (`_gate_rider` / `_cast_save`). F only adds an `against` argument, and B should not reshape those signatures. Name it in both briefs.
  - `rules/sheet.py` is shared with D and E, in different functions.
- **Realistic.** The six Extra-X feats, Selective and Improved Channeling, about 8 rogue talents, about 8 rage powers, the six plain-modifier class features, the descriptor pass over about 10 features, the `self_action` fix and the validator. That is about 35 items, most of them data.

### Not in any lane

Each of these is its own design, and some need an owner ruling first:
- a surprise round;
- auras that move with their bearer (~11 class features);
- movement modes and terrain (~13);
- wild shape's elemental and plant forms;
- familiars and cohort actors;
- item-creation feats (the benches replaced them; ruling needed);
- Use Magic Device (no wands or scrolls exist);
- Ride and mounted combat;
- the remaining ~1,500 spells whose only spec is `narrative` (vocabulary, not executor).

The Kingmaker precedent says fewer skills and uses can be a legitimate design. Whether to *cut* rather than build Fly, Ride or Linguistics is an owner question.

---

## 6. What this audit could not measure

- **Nothing was driven in the running app.** A FULL verdict means the engine's readers say every spec runs at caster level 5, not that a cast was watched. Runtime refusals inside an executor are not counted: `_summon` with an unknown template, `_lay_condition` against a spared target, a touch attack missing. FULL is therefore an upper bound.
- **Regex-layer spells are "FULL" by execution and unknown by correctness.** Twelve were confirmed wrong by reading. The other 329 were not read.
- **The feat `why` column is a regex triage of benefit prose** and is wrong in places (it filed Vital Strike under class pools because of the word "extra"). The Core table above is hand-sorted. For the other ~1,100 the column is a planning signal only.
- **Skill use counts** rest on a CRB use list from memory, least certain for Appraise, Perform and Handle Animal. Whether every resolved path is reachable from the player's actual click path was not traced.
- **Class features.** `not_yet` text was taken as true where present, and found stale where it was grepped (the blood-bending `needs`, Bleeding Touch's periodic damage). Levels 11–20 option catalogues were counted, not read clause by clause.
- **Saves.** The `char_class` field was empty in all 15 distinct saved characters, so class reach could not be weighted from saves. Spells were counted from `spellbook`/`known`/`prepared`/`casting` keys only.
- **Research, unconfirmed:**
  - PCGen's lack of duration tracking (an inference from what the docs omit);
  - Owlcat's Power Attack and Empower internals;
  - why Owlcat cut Wish and Simulacrum.
