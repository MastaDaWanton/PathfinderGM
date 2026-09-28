# Enemies that choose — the plan

*Written 2026-09-27, before any code. Branch `enemy-tactics-plan` (off `npc-turn-pc-name`,
whose enemy-turn prose fixes this builds on). Six research passes ran in parallel — three
code maps of this repository, three prior-art sweeps — and a critic pass checked the claims
the plan leans on; its verdicts are folded in under "What the critic changed".*

## The ask

> "enemies that only attack will feel stale immediately. but now that you know what is
> expected of enemies we need to make sure that they can choose the best option based on
> the circumstance. which might mean a tactics pass as these fights should be taking place
> over a 3D space."

Four pieces, as offered on 2026-09-27: (1) tell each enemy what it can do, (2) demonstrate
varied options, (3) make spell-like abilities and special attacks real, (4) morale and
tactics. The research changed the shape of (1) and (2) — see "The one decision" — and found
that most of (4)'s "3D space" already exists.

## What is there today (measured, not remembered)

**What enemies do.** 73 recorded enemy turns (the committed corpus's 41 plus the four live
runs of 2026-09-27): `attack` 40, `move` 33, **nothing else, and not one param** — no
manoeuvre, no full attack, no destination. A move with no square changes nothing and writes
"Borin Lyraxys moves from near to near" (`rules/engine.py` ~8848-8895).

**Why.** The enemy is never told anything it could choose with:
- the turn prompt is "Round N. It is c2 (Borin Lyraxys) turn. They are bloodied and their
  conditions are: none. What does c2 do?" (`prompts.npc_turn_messages`);
- the four worked examples show `attack` at `pc` and `narrate_only` — and `narrate_only` is
  not in the fight grammar (`prompts._FIGHT_OPS`), so two of four demonstrations are of an op
  the sampler refuses; none carries a param;
- the brief's "WHAT X CAN DO / CAN CAST" blocks are written for the player only; the "WHO IS
  HERE" list carries no position, side, hit points, weapons or speed for anyone;
- the NPC call never includes the main system prompt that lists ops and manoeuvres.

**What an enemy could do if it knew.** Real, engine-resolved and unused: ten combat
manoeuvres (`tables.MANEUVERS`), `full_attack`, `move` to a square with speed, route and
terrain enforced, flanking (+2), higher ground (+1 melee), cover (+4 / soft / total), 3D
spell areas, attacks of opportunity on leaving a threatened square, flying and climbing by
movement mode (`rules/position.py`, `rules/grid.py`, `rules/reactions.py`).

**What it cannot do, whatever it knew.**
- `cast`, `use_ability`, `use_item` are dead for every bestiary creature: casting is keyed
  on a class (`casting.caster_data`), abilities on class paths, items on the player's satchel.
- Spell-like abilities (2,163 of 6,406 stat blocks), special attacks (4,994) and special
  abilities (2,020) are stripped at `bestiary.instantiate` (`_NOT_ON_THE_SHEET`), readable
  only as raw text through `Actor._creature_doc()`.
- **Stat-block damage is not used.** A bestiary creature has no weapons, so it swings an
  unarmed strike: an ogre (2d8+7, minimum 9) hit for 6 and 7 in a probe. One flat attack,
  so `full_attack` gives a claw/claw/bite creature nothing. Spun off as its own task
  ("Make bestiary enemies deal stat-block damage") — it is phase 0 here.
- No action economy for anyone (an intent list may hold any number of attacks and moves);
  no charge, withdraw, total defence, fighting defensively, feint, demoralize (Intimidate
  moves *attitude*, never `shaken`), aid another, ready, or hiding in a fight; casting and
  standing up do not provoke.
- Morale exists only for troops (2d6 against a score, `rules/troops.py`); `default_npc_action`
  (attack the most-hurt foe) is the only other scoring rule in the game.
- Nothing checks that an NPC's intents are its own (`intent.actor == ref`).

**What the data has that the import dropped.** The bestiary's own source,
`monster_stat_blocks_full.xlsx` (6,748 rows, 102 columns — it is an *NPC* database,
"Copyright 2020 Mike Chopswil"), carries columns `tools/build_bestiary.py` never read:
**BeforeCombat 2,397, DuringCombat 4,139, Morale 3,605, SpellsPrepared 1,497, SpellsKnown
948, Gear 5,048, Class 5,094**, SpellDomains 669, SpellLikeAbilities 2,225 (counts
confirmed by the critic with openpyxl). But the tactics text is **adventure NPCs, not
monsters**: of the Morale rows, Adventure Paths 1,750, Society scenarios 1,314, other
modules 510, all the Codex books together 9, **bestiaries 0**; about 686 name the PCs, a
page or an area code. ("Janiven surrenders at 4 hp if she believes her opponents will
spare her life, otherwise she flees.") So monster morale has to come from code, whatever
the licence says (D1). 342 rows are also lost to slug dedupe, and `core.json`'s special
attacks are cut at 300 characters (85 rows at exactly 300).

**The space.** The engine already fights in three dimensions: 5-ft squares, a per-square
floor height, parapets, ceilings, a creature's feet level as the third coordinate,
5-10-5 distance over three axes, storeys as places joined by stairs, an axonometric
viewport. Built across stages 1-9 of `docs/distance-and-geography.md`, after research that
refused voxels ("nobody who does tactical-grid combat well uses voxels") and a second
spatial authority. **The fight is 3D; the enemy has simply never been shown it.**

## What the traditions do (the sweep, condensed)

- **Every shipped tactical RPG scores legal options in code.** Divinity: Original Sin 2
  simulates each skill on candidate targets and scores damage, healing and control through
  per-archetype multiplier files, searching positions only for the top candidates, and flags
  what its simulator cannot model `CanNotUse` (docs.larian.game). Owlcat's Kingmaker gives
  each unit a brain: a list of actions with a base score, actor and target considerations,
  a per-combat count and a cooldown. XCOM 2 scores targets additively and destinations by
  move profile (Aggressive/Defensive/Fanatic…), with a linger penalty; its `FallbackChance`
  is a retreat to the mission objective for the last unit of a group, with an exclusion
  list — *not* a morale roll (`XComAI.ini`).
- **Utility AI, done well** (Mike Lewis, *Game AI Pro 3* ch. 13): normalise each
  consideration to 0-1, pass it through a response curve, **multiply**, and a zero vetoes.
  Lewis recommends taking the best-scoring decision, with a commitment term against
  oscillation. **Dual utility** (Kevin Dill, *GAIP 2* ch. 3): rank buckets first — dying
  outranks everything — then weighted choice among the near-best, because always-the-max
  is predictable and pure random "can easily make your AI look stupid". The two disagree
  on the last step; this plan takes a side (phase 2).
- **Position**: generate reachable cells, filter, score — flank partner, cover from the
  threat, height, reach, retreat path (Jack, *GAIP* ch. 26, Tactical Position Selection).
- **Personality follows the stat block** (Keith Ammann, *The Monsters Know What They're
  Doing* — a D&D 5e author's own heuristic, not a rule or a measurement): Intelligence and
  Wisdom bands (≤7, 8-11, 12+, 14+) gate how much a creature adapts, how well it picks
  targets and when it knows to flee; "reduced to 40 percent of its maximum hit points or
  fewer — you may prefer a different threshold" is his flee line. Physical ability contour
  gives brute, skirmisher, sniper. Paizo prints Before Combat / During Combat / Morale for
  adventure NPCs, never in the bestiaries.
- **Small models choosing combat actions** collapse and mis-index. Measured: Mistral-7B
  (a real-time strategy tag every five seconds, not turn-based picking) chose the same one
  of four tactics in 83.8% of 2,430 decisions regardless of opponent; Llama-3.1-8B "could
  not provide the correct index" from a numbered list — *without* a constrained schema;
  LLMs favour particular option ids regardless of content (Zheng et al., 20 models). What
  worked: the engine enumerates legal options and the model answers an option id under a
  schema (DungeonBench, 2026 — frontier models only, given the whole legal list); an 8B
  model proposing inside an engine's minimax search beat GPT-4o choosing alone (PokéChamp,
  64%); free chain-of-thought made choices *worse* (PokéLLMon: 54% vs 58%, "panic
  switching" 10.8% vs 6.2%). **No source shows a ~12B model choosing well from a shortlist
  in turn-based combat** — the scorer has to play well on its own.
- **Space in a text game.** Gridless systems buy simplicity by dropping exactly what was
  asked for — Paizo's own theatre-of-the-mind advice is to avoid cover and terrain. On
  text-game maps "even GPT-4 … performs poorly" (MANGO); DungeonBench hands its models
  precomputed distances rather than a map. So: **the engine chains the geometry and hands over
  one-step relations** — flanked, in cover, above you, out of reach — anchored to two to
  four named features of the room, never squares or feet.
- **Refused or abandoned elsewhere**: GOAP for combat turns (F.E.A.R.'s plans were one or
  two actions; High Moon moved to HTN for speed); tuning near-ties with bonuses; letting the
  model generate actions or decide morale; per-pair range bands (n² state, abandoned by
  FFG's players); Fate's weighted zone borders; cinematic advantage in place of flanking (a
  negotiated number).

## The one decision

**The engine proposes, scores and shortlists; the model chooses among a few and says it;
the engine disposes.** This replaces offers (1) and (2) as first put. "Tell the enemy what
it has" in prose and "show it varied examples" are instruction and demonstration aimed at
free generation — the shape every source above measured failing on small models, and the
shape that produced 73 turns of attack-or-shuffle here. Telling the enemy what it has
becomes **the engine building its menu**; demonstration becomes **examples of choosing
from a menu**.

It is also this project's own first law read one level up: *detect mechanically, repair
with a targeted call* becomes *decide mechanically, dress with a targeted call*. And it is
the architecture the project already has for the player — the model proposes, the engine
validates — with the proposal space narrowed to what the engine has already proved legal.

**The scorer must play well on its own.** No study shows a model this size choosing well
from a menu, so the model is only ever given a choice the engine is indifferent between:
options within a small margin of the best. Whether that choice adds anything is measured,
not assumed (phase 2's instrument): if it tracks the scorer, or collapses onto one id, it
is costing latency and adding no judgement, and the engine picks.

## The plan

Phases are ordered by dependency. Each ends with the whole suite green, the fight audit
rerun, and the change verified in the running app. Every number stays in the modifier
funnel and every new behaviour is a document row or a rule row, validated on load — the
three laws hold throughout (`tests/test_three_laws.py`).

### Phase 0 — make the floor true

Nothing tactical is worth building on enemies that do a fraction of their damage.

1. **Stat-block attacks become real attacks** (the spun-off task): the `melee`/`ranged`
   strings parsed into weapons and natural attacks — name, bonus, damage, type, critical,
   full-attack routine — read through the existing funnel, provenance `creature:<template>`.
   Prior art: Foundry PF1's statblock converter keeps attacks as items. Measure: ogre damage
   over 50 swings against 2d8+7; the `kills` script before and after. **Balance warning:**
   every fight so far was played against enemies doing unarmed-strike damage; phase 0 alone
   makes fights much deadlier (see decision D3).
2. **Per-turn action economy** for every combatant: one standard + one move, or one
   full-round, plus swift/free, checked in `_check_legality`. Without it a menu has no
   shape ("attack, attack, move, attack" is legal today). Grep for the player paths that
   rely on chaining (the combat panel's `end_turn`, free actions) and keep them legal.
3. **The enemy acts only for itself**: refuse an NPC intent whose actor is not the NPC.
4. **The fight grammar and the examples agree**: `narrate_only` joins `_FIGHT_OPS` or leaves
   the examples; fleeing and surrendering become real ops in phase 4 either way.
5. **The instrument**, in `tools/narrator_audit.py` and the replay corpus: per enemy turn —
   op, params, whether it did anything mechanical (a param-less move is a fault);
   per creature per fight — choice spread (the 83.8% collapse check); resources used when
   available; flanks achieved; morale triggers against the rule; seconds per enemy turn.
   New scripts beside `fight`: `pack` (wolves: flank and trip), `caster` (a cultist with
   spell-like abilities), `gallery` (an archer above, cover, height), `cowards` (bandits
   whose morale should break). Baseline all of them before phase 1.

### Phase 1 — the menu (offer 1)

`rules/tactics.py`, engine side, deterministic, no model:

- `options(scene, ref) -> list[Option]`: every legal thing this creature can do this turn,
  each a small bundle of raw intents the validator already accepts — attack each reachable
  foe (with the weapon or natural attack), each legal manoeuvre, full attack when it has not
  moved, move to each *candidate* square (below), charge, withdraw, total defence, use an
  ability or spell-like ability with uses left (phase 3 fills these in), flee, surrender.
  Legality by construction: an option is generated only if `engine.validate` accepts it,
  so the menu cannot offer what the engine would refuse (Larian's `CanNotUse` lesson).
- **Candidate squares, not the grid**: reachable cells within speed (`grid` routing exists),
  filtered for occupancy and headroom, then the few that change something tactically —
  flanking a foe with an ally, cover from the foes who can shoot, higher ground, reach
  without being reached, a retreat line, out of threatened squares. Tactical Position
  Selection's generate → filter → score, over the grid the engine already has.
- `Option.label` is written by the engine in relation words anchored to named features
  ("circle behind her — flanking with the other thug", "climb onto the gallery — above him,
  in cover"), never coordinates; it is what the model reads and what the tell will say.

Measure (the `fight` script): op variety, param-less moves (must be 0), seconds per turn.

### Phase 2 — scoring, and the model's one choice (offer 2)

- **Considerations**, each 0-1 through a response curve, multiplied, zero vetoes (Lewis):
  hit chance against the target's AC or touch AC or CMD; expected damage against hit points
  left; save DC against the target's save; creatures in an area, friendly fire a veto;
  attacks of opportunity the option provokes; flanking, cover, height gained or lost;
  distance to preferred range; uses left of a limited resource and how much of the fight
  remains; own hit points; a linger penalty (XCOM) so nobody stands still.
- **The selection rule** (the critic asked the plan to choose between Lewis and Dill):
  rank buckets first (Dill) — morale and self-preservation outrank fighting; within the top
  bucket, the options within a margin of the best score form the **near-best band**; a band
  of one is simply taken (the model then only narrates); a band of two to four is the
  model's choice; the scorer's argmax is the fallback. Across turns a commitment term
  (Lewis) keeps a creature from flip-flopping between two near-equal plans. The model's
  pick replaces Dill's weighted random — it is the variety, and it is measured.
- **Profiles are data**: `content/tactics/*.json` — archetypes (brute, skirmisher, sniper,
  caster, controller, pack hunter, guardian, coward, mindless), each a set of weights and
  curves, validated on load in the classbuilder's message style. A creature's archetype and
  gates derive from its stat block (Ammann): Intelligence decides which considerations it
  may use at all (a wolf never aims at the weakest save; a mindless undead never retreats),
  Wisdom how well it judges targets and danger; creature type and subtype, its attacks and
  its speeds decide the archetype. A world or homebrew creature may name its own profile.
- **The model's call** stays the one call an enemy turn makes today. It is shown the
  creature, its situation in relation words, and **the near-best band (at most four),
  shuffled, as an enum of opaque ids in the schema** (Ollama enforces enums, measured 6/6), and returns
  `{"choice": id, "narration": "the wind-up"}`. No free reasoning. Unparseable or out of
  enum → the top-scored option. Worked examples become examples of choosing — one per
  archetype, filled with the acting creature as today.
- **Measured, not assumed**: how often the model picks the top-scored option, the
  first-listed option, and the same option across a fight. If it tracks the scorer, the
  engine picks and the model only narrates — decision D2.

### Phase 3 — spell-like abilities and special attacks made real (offer 3)

1. **Import the mechanics that were dropped.** `tools/build_bestiary.py` reads
   SpellsPrepared, SpellsKnown, SpellDomains, SpellLikeAbilities, Class and Gear (game
   mechanics); recovers the 342 deduped rows; the PDF extractor stops cutting special
   attacks at 300 characters. Cache version stamped (CLAUDE.md: derived caches outlive
   reinstalls). **BeforeCombat, DuringCombat and Morale are not imported** (D1): they are
   read offline, once, to design the morale taxonomy in phase 4, and no text is copied.
2. **Parse spell-like abilities into a creature document** — per creature, per ability:
   frequency (constant / at will / N per day / N per day *each* / every 1d4 rounds / per
   week…), the spell it duplicates, caster level (printed, else Hit Dice — UMR), save DC
   (printed, else 10 + the spell's level + Charisma modifier — UMR), concentration. Uses
   become ordinary `rest.night` pools; constant ones clockless `ActiveEffect`s. The grammar
   is regular (2,421 headers, one line format); names match the spell table for 76% of
   8,446 entries today, most misses mechanical (inverted names "greater teleport",
   metamagic prefixes, book-code suffixes). **What does not match is `unresolved` and never
   offered** — class powers such as *touch of evil*, *acid dart*, *rebuke death* are class
   features, not spells, and resolve through class ability documents where one exists.
   Foundry's converter turns misses into placeholders; so do we, visibly, with a count.
   Measure: parse rate over the 2,163, and the share of creatures whose every ability
   resolves (861 of 2,163 before any repair).
3. **The engine casts a spell-like ability**: a `cast` whose source is the creature
   document — no components, a standard action, caster level and DC from the document,
   the use spent from its pool, subject to spell resistance, **provoking** an attack of
   opportunity unless cast defensively (UMR) — through the same `_op_cast` resolution and
   its per-spell effects, origin `creature:<template>/sla:<spell>`. Casting provoking is
   absent for everyone today; it lands here for all casters, player included.
4. **Spellcasting NPCs** (SpellsPrepared/Known, 1,497 + 948): the same document carries the
   prepared list and slots at the printed caster level.
5. **Special attacks as Universal Monster Rules rows** — a closed set, hand-built, because no
   tool anywhere turns their text into mechanics. Triggered riders, not choices: grab (free
   grapple on a hit, +4, no provoke), trip (free trip on a hit), rake (two extra attacks on a
   foe it began the turn grappling — "can't begin a grapple and rake in the same turn"),
   rend (two natural hits → extra damage once a round), pounce (full attack on a charge,
   "including rake attacks" — which contradicts rake's own requirement; no Paizo FAQ
   settles it, so the engine takes an explicit, documented ruling). Choices, on the menu: breath weapon (DC
   10 + ½ HD + Con, a cooldown pool "every 1d4 rounds"), poison through `save_gate`, gaze.
   Poison's "1/round for 6 rounds" needs the periodic executor the ledger still lists as
   promised-not-built; it is built here, once, for every periodic effect.
6. **Retire the `creature:` door**: as coverage rises, `damage`/`ability_damage` leave
   `_CREATURE_OPS` for creatures whose document covers their special attacks, and the
   stage-8 ratchet (`tests/test_stage8_provenance.py`) is tightened by count.

### Phase 4 — tactics and morale over the space (offer 4)

1. **The missing tactical ops, as rule rows**: charge (straight line, +2 attack / −2 AC),
   withdraw, total defence, fighting defensively, aid another, demoralize (Intimidate →
   `state.fear.shaken` through the mind gate with a `rule:` origin), attacks of opportunity
   for casting and standing up. Each validated, each on the menu, each open to the player
   too — the combat panel gains what enemies gain.
2. **Relations, derived and read — never stored.** Flanked, in cover from whom, above or
   below whom, engaged with whom, out of reach: computed from the grid each turn (the grid
   is the one spatial authority; zones already are such a derived view). They feed the
   scorer, the option labels and the tells ("the archer climbs to the gallery above you"),
   replacing "near to near". Two to four named features per fight from the floorplan anchor
   the words. A persistent state tag would be a second store of a fact the grid owns, so
   these are not `ActiveEffect`s; if a narrator-facing tag is needed it is computed, like
   `has_state` over `standing_tags()`.
3. **Morale in code, top rank bucket.** A small policy enum with parameters — *fights to
   the death*, *flees below a threshold*, *surrenders if it will be spared, else flees*,
   *breaks when its leader falls*, *falls back when last of its group*. The taxonomy and
   its rough frequencies come from reading the 3,605 Morale lines offline (1,659 mention
   death; 1,252 carry a numeric or "half" threshold); **no line is shipped** (D1). Every
   creature's policy is derived in code from its stat block, since monsters have no Morale
   line at all: mindless creatures, constructs and most undead fight to the death;
   intelligent creatures and animals break at a threshold (Ammann's 40% as the starting
   point, labelled as his heuristic and tuned by measurement), later with high Wisdom;
   fanatics and summoned creatures excepted. The existing `state.fear.*` tags feed it. Fleeing is a real
   move off the map; a creature that escapes leaves the scene alive and is booked into the
   population (`docs/the-population.md`) — the one who got away can come back.
4. **Before Combat** — a creature that saw the fight coming spends its first round
   preparing: the scorer's pre-fight bucket favours its own buff spells and a good square
   when it had warning. Derived from what it can cast, not from Paizo's prose.
5. **Companions** share the tactician with the other side's weights (`fight-from-either-side`):
   today they would read the enemy prompt, whose examples target `pc`.

### Phase 5 — the narration carries the tactic

The chosen option's label and its outcome become the tell; the enemy-turn consequence call
(`call_two_messages(acting=…)`) dresses it; `narration.wrong_actor` still guards it. The
narrator is fed what happened in relation words and nothing else about mechanics.

## Decisions for the user

- **D1 — the Tactics/Morale text and the public repository.** Recommended: **do not ship
  it.** Paizo's Adventure Path declaration (checked verbatim) makes "proper names
  (characters, deities, etc.), dialogue, plots, storylines, locations, characters" Product
  Identity and only "the game mechanics" Open Game Content, and "no portion … other than the
  material designated as Open Game Content may be reproduced". The tactics prose mixes the
  two, and it covers adventure NPCs, not monsters, so the design loses almost nothing
  without it. It is read offline to derive a code-owned taxonomy; ideas are not
  copyrightable. (Not legal advice; the critic flagged it as its own reading.)
  **Separately, and already true today:** the shipped `content/bestiary/creatures.json` was
  built from the same NPC database and carries Adventure Path characters by name
  ("Janiven", "Thmei" — proper names are Product Identity under that declaration), and
  `OGL-NOTICE.md` already records Section 15 as outstanding. That predates this plan and is
  raised as its own question.
- **D2 — does the model choose at all?** Recommended: yes, from three or four scored
  options, measured in phase 2; switched to engine-picks if the measurement says the model
  only adds latency.
- **D3 — difficulty.** Stat-block damage plus tactics makes every fight far deadlier than
  anything played so far. Proposed: a table setting (the house-rules shelf) that scales the
  scorer's cleverness — which considerations are on, how near-best the choice must be —
  rather than the enemies' numbers, the way Baldur's Gate 3's Tactician mode is described.
- **D4 — the action economy for the player.** Phase 0 enforces it for every combatant; the
  player's free-text turns that chain several actions today would be held to one standard
  and one move.

## Refused, with reasons

- **GOAP or multi-turn plans** for a combat turn — F.E.A.R.'s plans were one or two actions,
  studios moved on for speed; cooldowns and a commitment term give sequence for free.
- **The model authoring squares, distances, targets outside the menu, or morale** — the
  measured small-model failures above, and the third law.
- **Free chain-of-thought or self-consistency** for the choice — worse on measurement, and
  self-consistency triples a local model's latency.
- **The whole option list in the prompt** — position bias and collapse; three or four only.
- **Pure weighted random**, and **tuning near-ties with bonuses**.
- **A second spatial authority** — per-pair range bands, stored relation tags, voxels.
- **Cinematic advantage** in place of flanking — a negotiated number.
- **Tactics prose as instruction to the model** — instruction volume loses to demonstration
  volume, and the prose is for the parser, not the prompt.

## What the critic changed

The critic re-read each load-bearing source. Confirmed: DungeonBench's indexed options and
schema-constrained choice id; the 83.8% collapse; the Llama-8B index failure; PokéLLMon's
and PokéChamp's figures; Zheng's option-id bias; Larian's simulate-score-then-position and
`CanNotUse`; Lewis's multiply-and-veto; Jack's generate/filter/weight; Dill's buckets; the
XCOM keys; the UMR rules as quoted; the spreadsheet's counts exactly. Corrected here:

- **StepGame's 85.77% → 31.25% decay was a trained 2022 memory network, not a language
  model** — cut; MANGO stands.
- **The shortlist has no small-model evidence behind it** — DungeonBench tested only
  frontier models, the Llama failure was without a schema, the 83.8% collapse was a
  real-time tagging task. Hence: the scorer must play well alone, and the model chooses
  only inside the near-best band.
- **Lewis and Dill disagree on the final pick** — the plan now says which step comes from
  whom.
- **XCOM's `FallbackChance` is a retreat to the objective, not morale; Ammann's 40% is his
  stated preference** — both relabelled.
- **The tactics text is adventure NPCs, not monsters, and not safe to ship** — phase 3
  imports mechanics only; morale is derived in code (D1).
- **Pounce contradicts rake** — an explicit ruling is owed.

Not checked, and said so: Paizo's declarations for Society scenarios and the NPC Codex
(very likely the same boilerplate); Owlcat's own account of its AI; Baldur's Gate 3's
internals (mods only); any direct comparison of an LLM against utility AI for monsters —
none was found.

## Sources

- Larian, *Combat AI* and *Archetypes and Modifiers*: <https://docs.larian.game/Combat_AI>,
  <https://docs.larian.game/CombatAi_Archetypes_And_Modifiers>
- Mike Lewis, "Choosing Effective Utility-Based Considerations", *Game AI Pro 3* ch. 13:
  <https://www.gameaipro.com/GameAIPro3/GameAIPro3_Chapter13_Choosing_Effective_Utility-Based_Considerations.pdf>
- Kevin Dill, "Dual-Utility Reasoning", *Game AI Pro 2* ch. 3:
  <https://www.gameaipro.com/GameAIPro2/GameAIPro2_Chapter03_Dual-Utility_Reasoning.pdf>
- Matthew Jack, "Tactical Position Selection", *Game AI Pro* ch. 26:
  <https://www.gameaipro.com/GameAIPro/GameAIPro_Chapter26_Tactical_Position_Selection.pdf>
- XCOM 2 `XComAI.ini`: <https://github.com/russgray/xcom2-config/blob/master/XComAI.ini>
- Owlcat brains, as modded: <https://raw.githubusercontent.com/Holic75/KingmakerAi/master/UpdateAi.cs>
- Jeff Orkin, "Three States and a Plan" (F.E.A.R.):
  <https://www.gamedevs.org/uploads/three-states-plan-ai-of-fear.pdf>; Humphreys, HTN planners,
  *Game AI Pro* ch. 12
- Keith Ammann, "Why These Tactics?": <https://www.themonstersknow.com/why-these-tactics/>
- DungeonBench (2026): <https://arxiv.org/html/2607.29577>; Nair & Karim (2026):
  <https://arxiv.org/html/2609.02931>; Dayo et al. (2025): <https://arxiv.org/html/2503.15726>;
  PokéLLMon: <https://arxiv.org/abs/2402.01118>; PokéChamp: <https://arxiv.org/abs/2503.04094>;
  Zheng et al., option-id bias: <https://arxiv.org/abs/2309.03882>; MANGO:
  <https://arxiv.org/abs/2403.19913>; FIREBALL: <https://arxiv.org/abs/2305.01528>
- Pathfinder 1e, Universal Monster Rules (spell-like abilities, grab, pounce, rake, rend, trip,
  breath weapon, poison): <https://aonprd.com/UMR.aspx?ItemName=Spell-Like+Abilities> and
  siblings; Special Abilities: <https://aonprd.com/Rules.aspx?ID=246>
- Paizo theatre of the mind (2e): <https://2e.aonprd.com/Rules.aspx?ID=512>; Fate zones:
  <https://fate-srd.com/fate-core/setting-scene>; 13th Age: <https://www.13thagesrd.com/combat-rules/>
- Foundry PF1 statblock converter: <https://gitlab.com/foundryvtt_pathfinder1e/pf1-statblock-converter>;
  PathfinderMonsterDatabase: <https://github.com/c0d3rman/PathfinderMonsterDatabase>
- Inform 7 adaptive text: <https://ganelson.github.io/inform-website/book/WI_14_3.html>
