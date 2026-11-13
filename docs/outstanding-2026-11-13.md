# Outstanding work, 2026-11-13

*Checked against master ea1257f4 plus feat/map-fixtures (released together as 0.2.30). A
sweep of the owner's memory, docs/ plans and playtest lists, the 2026-11-07 audit, the
2026-11-11 Python review, and every branch with commits not in master (each commit's diff
tested against master, so branches squashed into 0.2.26/0.2.28/0.2.29 count as released).
"(unverified)" means one grep or less stood behind it.*

## A. Ruled or agreed, not built

1. **A GM you can prompt from any screen**: help, create (characters, items, creatures,
   spells, feats, packs), chat about PF; /gm crafting guidance is part of it. Next in the
   queue after the audit fixes.
2. **Ships**: keep them and make them reachable (board, sail, fight). Needs ports and
   vessels in the World Bible export.
3. **Inflict spells heal any negative-energy-affinity creature**, not only undead.
4. **A spell starts a fight only if it harms someone who saw the cast, or a guard sees
   harm** (an unseen charm, then talk). (unverified)
5. **Shot in the dark**: an unknown fact gets a hidden oracle roll; true is real leverage,
   false is a bluff at -5 and a step of attitude lost.
6. **Every class before multiclassing** (12 classes now).
7. **Turn budget steps 3-5**: work in progress as a task, the world's beat when the budget
   ends, options built from what was left unfinished. (unverified beyond a grep)
8. **Fixtures phase 2**: break, burn, push, topple; swing on the chandelier; doors and
   windows with state; +2 for creative use of a real fixture; the 30 ft low-obstacle cover
   clause; steep stairs as difficult terrain; retire `judgement._FIXTURES`. (Climbing is done.)
9. **A world roster across playthroughs**: one id per person, name rolled at creation.
10. **"Since last we met"** catch-up when returning to someone.
11. **Deferred phases 3-7**: initiative-count encounters, an explicit cancel, stage 9 (class
    names out of the engine; Swift Strikes is still matched by name), the world tick.
12. **Whole-app visual polish**, every bench included: later, mock first, plain JS.
13. **Install REA**: blocked on Node 24.22.1 (this machine has 24.15).

## B. Built, not in master

1. **fix/beat-unseen-kind-declared** (3aeb7805, 5edff80e): one unseen contradiction throws
   away every finding for a beat. Small, real.
2. **Hidden-creature leaks**, UNCOMMITTED in pgm-work\hidden-leaks: a hidden foe listed in
   initiative, the reachable-square light giving away its square, a foe on a ledge
   threatening the ground below.
3. **fix/use-waits-its-turn** (e6815ec3): the Use button refuses off-turn in a fight.
4. **fix/manuals-read-at-forge-and-bench** (4551d8a4): manuals at the forge, enchanting and
   alchemy benches; the herb bench's manual button is still missing.
5. **fix/narrated-wait-tells-expiries** (1e3a6489, 09399797): a counted burn caps later
   entries (`times_left`); looks still present.
6. **fix/inner-run-suspension** (572a80eb): nested ops through `_run_within`. Old; may no
   longer be needed. (unverified)
7. **mock/polish**: board variants A-E, D liked, nothing ported.
8. **checker-bench**, **mock/table-free**: likely obsolete; keep or delete.
9. **fix/audit-data 84f0cc6c**: drop the dead JS `api()` copies; needs the UI test harnesses
   rewritten first.

## C. Logged, not ruled on or started

1. **Audit "left to fix"**: dead routes and helpers in the crafts; unmodelled rules
   (secondary natural attacks, Power Attack on off-hand and natural, composite bow Strength,
   bestiary creatures without feats, a no-map zone move not stopping a full attack, blinded
   -4 on every Perception, slapping a sleeper awake, charm breaking only on the PC's harm, a
   held PC's save has no popup, sightless as blinded, a check from "I'll never pick the lock").
2. **Never audited**: ~380 innerHTML sites, an unbounded turn log, manoeuvres, summoning,
   concealment, spell storing, charges, item powers, wards, travel/escort/found internals,
   effect validation, metamagic.
3. **/cheat bugs**: a failed cheat plan still narrates the ogre; "25 feet" read as 25
   creatures; "within reach" with the PC 40 ft short.
4. **Older live-check bugs** (unverified since 0.2.27): "doze off by the fire" rented a room;
   narrate-only invents props; "you remain at your table" after a move; a muttered line aimed
   at the potboy; two places in one beat; the welcome's repeated tip.
5. **Python review leftovers**: unbounded save growth; the confiscation flip only logged;
   the installer signer check is a substring; backups can all fall in one turn; pin
   requirements, a ruff config; ~165 broad excepts; ~160 dead-code hits.
6. **A ruling judge** taught by the owner's own rulings: neither judge is fit yet (57-60%).
7. **Hosted budget option** (parked): Hugging Face; first make `gm/client.py` send schemas.
8. **Blacksmithing section 15**: lazy forge chunk, focus after a game, no recipes API,
   noqual/elysian checks, old-work migration, inexpressible book effects, packaged checks.
9. **Own items**: Mask of the Mantis (charge pool), war paint and tabard, drugs and
   addiction, looted magic weapons and shields stay plain, homebrew creatures not compiled.
10. **World Bible export asks**: names with gender, bearings, water, supplies, materials,
    essences, gods, ports and vessels.
11. **The merchants' row** still scatters its stalls.
12. **Short windows**: under 1000x640 the fight buttons get a 17 px strip ("later").
13. **Older lists not re-checked one by one**: docs/fix-plan-2026-09-30.md, the 2026-10-03
    playtest's open items, an NPC's prose items becoming props they hold, armour and shield
    homebrew. Many are probably superseded.
14. **Memory policy**: a bounded history exists; the rolling summary is unverified.

## D. Waiting on the owner

1. Board polish: port variant D or E?
2. Merge the off-turn Use refusal? Is a drink from Equipment in a fight free, or a standard
   action that provokes (the book)?
3. Race-point pricing: two identical branches in rules/races.py; a mispricing?
4. Coup de grace with a nonlethal weapon: death save, or unconscious?
5. Encounter CR windows, now monsters hit at printed strength. (unverified whether done)
6. The glowlizard hide is unreachable: what should happen?
7. Section 15 notices for ~173 non-rulebook sources.
8. Blacksmithing house modifiers: your review. (unverified)
9. Soundtrack: confirm the Suno plan's rights before a public release.
10. Refs in the sidebar: keep, hide, or show on hover?

## Not checked

The 72 KB playtest bug list (sessions 1-3 recorded as built), the 2026-09-28 playtest's 22
items, the enemy-tactics, quest and deeds plans, and anything in another chat that is
neither committed nor in memory.
