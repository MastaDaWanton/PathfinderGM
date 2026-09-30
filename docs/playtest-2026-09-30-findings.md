# Playtest 2026-09-30: what the investigations found

These are the causes behind [playtest-2026-09-30.md](playtest-2026-09-30.md). Five
read-only investigations ran in parallel on a copy of the owner's save; nothing was changed
while investigating. Each item gives the cause, the proposed fix, the files it touches, a
size, and any owner questions. The plan and its order of work follow at the end, once every
investigation has reported.

## Item 3: the line that follows the cursor (ultrawide)

**Cause.** The candle's dimming veil, `#cursorshade` (`play/templates/play/table.html`
about 1685–1706), is a fixed 6000px square centred on the pointer. It reaches only 2934 to
3138px from the cursor, and past its edge nothing is dimmed, so the page shows a hard step
of about 10% brightness.

- It follows the pointer, and it sways about 204px with the flicker (`--flick`,
  06-trade-and-page.js lines 741–757).
- It is visible only on windows wider than about 2934 CSS px. Measured at 3440x1440: 356
  columns were left undimmed.
- There was no edge at 2560, 2000, 1792 or 1440.
- The owner's screenshots were scaled down, so the line does not show in them.

**Fix (proven by injecting CSS live).**
- Size the square as `max(6000px, calc(200vmax + 400px))` and pin the gradient's last stop
  at 4243px, the old 100%.
- 3440: no undimmed column at any pointer position or flicker scale.
- 2560 and below: pixel-identical.
- The light, flicker, candle cursor and embers are kept.
- The same rule has copies to fix in `home.html` (704–714), `craft.html` (463–471) and the
  mock's `mock.css`.
- Add a test: no `#cursorshade` rule uses a fixed px size.

**Size:** S. It touches only templates.

## Item 2: make all weapons and armour usable

**Cause: two weapon tables.**
- `goods.kind_of`, and the `known_item` it calls, look only in the 12-row curated
  `tables.WEAPONS`.
- The attack op, the sheet, the outfit page and the shops read `weapons.all_weapons()`:
  456 content rows with hyphenated ids.
- So `kind_of("bo-staff")` is gear: `_op_wear` refuses it, and `_carried` hides Wield
  behind "The rules cannot put this in hand by name yet".
- Measured: **348 of the 356 weapons sold cannot be wielded**; only 8 can.
- The attack side already works for NPCs, but a PC attacking with a double weapon (16 rows,
  "1d6/1d6") or ammunition (empty damage) raises `BadDice` (6 of 6).

**Armour.**
- All 10 pieces sold can be worn, but only by their exact key.
- "leather armour", the display name, and "chain-shirt", hyphenated, are filed as gear.
- The table has 7 of the CRB's 12 armours and 3 of its shields, with no weights and no
  arcane spell failure.

**Loot and outfit.**
- Looted armour goes into the ingredient satchel as "chain-shirt" (`engine.py` about 8526),
  where it can neither be seen nor worn.
- The outfit page stores a replaced suit under its display name.
- Forged armour: "Wear" puts it in a slot and AC stays 11 → 11.
- Forged weapons: "Wear" puts them in the hands slot and they lend +1 to every weapon (the
  stage-9 door).

**Proficiency.**
- Sam is a wizard, so most "not proficient" labels are right: the shortbow is martial and
  the bo staff exotic.
- But ammunition rows are marked exotic. That is an import artefact, and arrows got an
  attack row at "+20".
- Class tokens that match no row:
  - wizard "heavy crossbow";
  - rogue "hand crossbow" and "short sword";
  - monk "brass knuckles", "crossbow" and "shuriken".
- Armour proficiency is not read at all.

**No ammunition model.** A bow fires forever. The CRB rule: a hit destroys the ammunition,
a miss has a 50% chance to destroy it; bows draw as a free action.

**Proposed fix.**

| Part | What | Size |
|---|---|---|
| **E1** | One name resolver (key, display name, hyphen or space, "(20)", armor/armour). `kind_of` reads the merged table, and the curated `light crossbow` and `shortsword` become aliases. `_op_wear` stores the canonical key. Proficiency tokens go through the same resolver. | M |
| E2 | Double weapons: damage from the first end | S |
| E3 | Ammunition: filing, counts, spent per shot, refused with none, recovery | M |
| E4 | Take off (and put away): op, tell, donning time | S–M |
| E5 | Looted and outfit armour into `goods` by canonical key | S |
| **D** | Data: the missing armours and shields, weights, arcane spell failure, don times; ammunition rows' proficiency cleared; `ammo` families on launchers; the missing ranges; the class tokens | S–M |
| **U** | UI: one `wieldable()` behind both the op and the button; Take off and Put away buttons; ammunition as a counted row | S–M |
| Later | Drop (E6, S), forged gear (E7, M, stage 9), off hand / TWF (E8, L), encumbrance (E9, M–L) | |

**Owner questions**, with the recommendation for each:
1. Recover arrows automatically at 50% of misses, with a tell? **Recommended: yes.**
2. Armour changes cost the donning times out of combat, and only shields change mid-fight?
   **Recommended: yes.**
3. Apply arcane spell failure and non-proficient armour penalties? **Recommended: yes.**
4. A two-handed weapon while holding a shield: refuse, saying "take the shield off first"?
   **Recommended: yes.**
5. Stop the weaponsmith selling siege engines and modern explosives? **Recommended: yes.**
6. Do E1–E5, D and U now, and drop, off hand and encumbrance later? **Recommended: yes.**

**Aside:** Sam's saved scores are Str 30, Dex 58 and Con 30, and a "Power leaf" buff adds
+26 Str and +26 Con. Worth a look apart from item 2.

## Item 5: Bluff rolled when nobody lied (four times; the owner saw three)

**Cause.** Every one came from `inject_false_claim` (`gm/judgement.py` about 3409–3434,
called at `gm/agent.py:560`), injecting "claiming to be what the sheet says they are not"
at DC 30. It was not the model and not a Bluff declarer.

| Turn | Player's line | What the detector read |
|---|---|---|
| 4 | "I **take the herbs**…" | "produce a herbs you do not have" |
| 5 | "…I'll **take my payment**…" | "produce a payment…" |
| 12 | "I'm **a bit of a free spirit**" | `_SELF_CLAIM`: an identity claim |
| 23 | "I **take the key**…" | the same plan also gave Sam the key |

- `_PRODUCE` (about :3070) accepts bare "take", which is acquisition, not production.
- "hand" and "hands" match with no subject anchor. Replayed: "my hand on the hilt" and
  "Lay on Hands on the fighter" both misfire.
- `_IDENTITY_HEAD` matches any word in the predicate, so the hedge "a bit of a free spirit"
  counts.
- The interpreter had already read `act: take`, and nothing passes that reading in.

**Consequence.** `note_heat` marks the crowd as having heard a "delusion", and the prose
mocked Sam for boasts he never made (beats 18, 25 and 47).

**DC 30.** A flat heroic DC, not the listener's Sense Motive. With Sam's Bluff +6 it fails
by construction.

**Regression?** No. The rules date from 2026-09-18 and 2026-09-22; Sam's lines were simply
the first to trip them.

**Fix (S–M, `gm/judgement.py` plus one call site).**
- Drop bare take/takes, keeping "take out".
- Anchor the verbs to a subject or clause start.
- Pass `self.reading` in, and treat a take/pick up/accept, or a plan carrying a `give` of
  that item, as acquisition.
- `_SELF_CLAIM` judges the head noun only, and treats hedges ("a bit of a", "kind of") as
  character, not identity.
- `note_heat` and narration follow through the shared `false_claim`.

**Owner questions.**
- Should a spoken lie be opposed by the listener's Sense Motive, with 1e's believability
  bonuses, instead of a flat DC 30? **Recommended: yes.**
- Should an unhedged "I'm a free spirit" be exempt too? **Recommended:** fix hedges and the
  head noun now, and add idioms only if this recurs.

## Item 6: prose cut off at "They'"

**Cause.**
- The rewrite (`polish`) runs with `prose_schema(max_chars=1600)` (`gm/agent.py` about
  1874), a lower ceiling than the prose call's 1,800.
- Ollama's grammar closed the string at exactly 1,600 characters, mid-word.
- `_accept` took the cut rewrite, and `ensure_hand_back` added ". What do you do?".
  Reproduced byte for byte.
- Nothing detects an unfinished ending.
- Not a regression: this dates from 2026-08-25.

**Fix (S).**
- Add `narration.trim_unfinished`, which cuts back to the last complete sentence or closed
  quote. Run it after the prose call and on the polish candidate, and have `_accept` refuse
  a candidate that ends unfinished.
- `ensure_hand_back` trims a fragment rather than adding a period to it.
- Raise the polish ceiling to 1,800.
- Keep the tail of `raw` in the log as well.

## Item 4: suggestions offer abilities the character lacks

**Cause.**
- The prose call writes the suggestions. The brief *does* list what Sam can cast; the model
  ignored it, because instructions lose.
- No code checks a suggestion against the sheet.
- A second live instance is in the save now: "…the hilt of my blade", when Sam has no blade.
- Clicking "I use a healing spell…" passes every detector silently.
- Found alongside: "I cast cure light wounds" resolves to **Light**, by a substring match.

**Fix (M).**
- Add `play/aftermath/suggestion_sheet.py`, which runs each suggestion through the turn's
  own detectors:
  - named powers;
  - named spells, with the resolver made word-bounded;
  - a generic "spell/cast/pray" line must be answerable by a prepared spell;
  - "my <item>" must be carried, with `equipped` no longer vouching "blade" for a bow.
- Drop what fails, and log it.
- Log every beat's suggestions so the next report can be traced.

**Owner question.** Drop a bad suggestion, or replace it with a targeted model call?
**Recommended:** drop it, and fall back to the start's generic lines if fewer than two
remain.

## Item 13: the key

**No defect as reported.** Gorm produced the key in prose, "I take the key" gave it to Sam
through `inject_goods`, and Sam holds it.

**Found on the same path.**
- The lead coin Sam pocketed at turn 7 was never recorded, because `inject_goods` bows out
  when any `give` is present.
- The herbs "used" at turn 4 are still in Sam's goods, because `use_item` was refused
  before the give landed.
- The owner question (later): should things an NPC produces in prose become props that NPC
  holds, so taking one is a real transfer? **Recommended: yes, later.**

## Aside: the Power leaf

The owner's homebrew Power leaf (+20 Str, +20 Con) landed as **+26** each (`power-leaf.json`).
Sam's base scores are the owner's own house rules (point buy and caps off), not a cheat.

## Item 8: the Clockwork Spy

**What happened.** The forage (from the craft panel, at the outskirts) rolled a creature,
and `_bring_in` put the Spy (c7) there. The sentence is an engine tell template
(`rules/gathering.py:115`).

"I aprouch the clockwork Spy" was read as `seek target: the clockwork Spy`, and the plan was
one `travel` to the gate. The tell was "Left behind: Clockwork Spy". Written at the gate,
the prose denied the Spy existed.

**Causes.**
1. **The excursion's model calls spend their whole budget thinking.**
   - `play/craft_views.py:755` `_narrate` is the only chat call without `think=False`.
   - Probe: 140 of 140 tokens went on thinking, and the content came back empty.
   - 4 of 4 excursion narrations fell to their template floors. The opening floor also
     misnamed the place ("away from Ledgerwarren" while at the outskirts).
2. The closing prompt never mentions the encounter. The tell is glued on after it, and it
   contradicts the full haul already in the satchel.
3. **The excursion never reaches the model's memory.** `craft_action` writes only the
   transcript: no `c.history`, no turn_log row. The planner and narrator never saw either
   forage or the Spy.
4. **Nothing declares "approach someone who is here" out of a fight.**
   - `travel` is the only movement op the prompt documents in peacetime; `move` is
     undocumented.
   - `interpret` lets `seek` license a travel.
   - No check refuses a travel that leaves behind the very person being sought.

**Regression?** No. This is older code, exposed by a thinking model (gemma-4-12B).

**Fix.**
- **S:** `_narrate` passes `think=False`.
- **S:** `craft_action` writes history plus a turn_log row, the same shape as
  `pending_free`.
- **M, the encounter scene:**
  - Detected in code when a gathering effect holds a creature.
  - One scene call with `think=False`, grounded in the creature's bestiary fields, the
    place, the time and what was gathered.
  - Checks after the call: no invented names, no attack or flee verb with the creature as
    subject, no numbers.
  - A better floor if the call fails.
- **M, the creature stays where it is:**
  - A `state.holding-ground` ActiveEffect with a tell, until dismissed.
  - The NPC loop respects it.
  - Optionally the patch is booked as a guarded find.
- **S–M, approach:** a judgement filter refuses a travel that leaves the sought ref behind,
  and names the fix: `move` toward them, or narrate. Document peacetime `move`.

**Owner question 8a:** is the creature sitting on unreached ground a booked find (at ×1)
you get once it's gone, or only an obstacle? **Recommended: a booked find.**

## Item 9: walking to the Velvet Veil

**What happened.**
- The reading was "go the back streets / search the Velvet Veil".
- `travel` to the Veil was refused, with a hint to `found` it first, and the hint omits
  `parent`.
- The plan founded it with no parent, so it went **off the gate**, where Sam stood (not the
  outskirts), one hop away.

**Causes.**
- `_parent_place("")` defaults to where you stand (`engine.py` about 8832).
- The validation hint teaches omitting `parent` (`engine.py` about 2522, since 68fd6f0).
- No declarer reads the parent from the words.

**What already works.** Spoken travel already walks the whole route in one turn:
- one encounter roll per place, at 8% a hop in town;
- a tell naming each place passed through;
- prose held to the route.

Replayed with the parent set, the Veil is reached gate → market → back streets → Veil in
one turn. Over 300 walks, 23.7% met something, and **every meeting stops the walk**.

**Gaps against the owner's ruling.**
- (a) The Map tab's Walk there attaches one leg per turn: stage 3's choice, which the
  ruling now overrides.
- (b) A place chip must be an adjacent exit.
- (c) Every meeting stops the walk.
- (d) A meeting on the last hop says "You get no further" at the destination (24 of 71
  stops).
- (e) **The watch is only checked at the endpoint.** A wanted character walked
  outskirts → market past the gate in 32 of 40 runs.
- (f) Places passed through never join `been`, so they stay under fog.

**Research.**
- Inform's *Approaches* (GO TO): one command, the route narrated, visited rooms only,
  stopped by rules.
- zMUD dropped uncancellable speedwalks.
- PF2e hexploration: one check a day; when it hits, 50% harmless, 20% hazard, 30% creature.
- Necropraxis, "overloading the encounter die".

**Design.**
1. **(S–M)** A new named place goes under the parent read from the words ("head to the back
   streets to find X", "the X behind/in Y"), else a recent NPC's answer, else the kind's
   natural street, else where you stand. The hint names `parent`.
2. **(M)** Far chips: `_read_place` accepts any place routed through places you've been.
   Walk there attaches **the destination** as one chip, and the engine walks it in one turn.
3. **(S)** Per hop:
   - the watch is checked at every gate passed;
   - the places passed through join `been`;
   - no "no further" at the destination.
4. **(M)** One roll per place, split into *passing* meetings (hawker, beggar, press: told in
   the hop's line, nobody stays) and *stopping* ones (a squabble blocking the way, a
   cutpurse, trouble, a patrol for the wanted, aggressive creatures). That brings stopping
   down to about 8–10% for a 3-hop walk. Every meeting is an engine tell.

**Owner questions.**
- 9a. "A low chance of encounters stopping": most meetings pass by, and only a few stop?
  **Recommended: yes.**
- 9b. Walk there only through places you have visited? **Recommended: yes.** A spoken turn
  still routes anywhere.

## Item 1: NPC speech missing from the conversation log

37 of 43 real NPC lines reached the log. 6 did not, at beats 0, 3, 33 and 49.

**Causes.**
1. **The opening throws its speech records away.** `opening_prose.py:720` does
   `speech.lift` and discards the records, so the cage owner's opening lines never logged.
   The Q48 test passes only because it builds the records by hand.
2. **Lines already attributed are then dropped.**
   - An untagged line attributed to someone present (`("board", ref)`) writes only a miss
     row (`speaker_real.py` about 377) and never a `said` record.
   - It also returns early when no line contains "you".
3. The "sentence before" rule doesn't carry a leading He/She/They. The "line before" rule
   ignores tagged predecessors.
4. A polish rewrite that edits a tagged quote loses its tag. At beat 49 the Velvet polish
   did this, which is item 11.

Not a regression: the log is new, and the opening path never worked.

**Fix (M).**
- Board attribution books a `said` record with `from:"page"`, with no "you" gate for
  logging.
- Pronoun carry for rule 3, and tagged predecessors for rule 2.
- `_said_kept` accepts page records.
- The opening keeps its records.
- Optionally, re-align records to rewritten quotes.

This needs item 12 fixed first. Otherwise narration in quotes would be logged as Gorm's
speech.

## Item 7: names

**Keepers carry their true name from the moment they are minted** (`rules/keepers.py`
about 445, 2026-09-19), so the board and the brief showed Oren Bramble and Soren Moorcock
before anyone gave a name. Measured: 4 of 4 keepers were shown by full name before any
introduction, and the page used "Gorm Vesper" and "Quin Nutmeg" unprompted. Sorva's
answer revealed only her own name, which was correct.

**Related: a ref became a name.** `introduce {who:"c8"}` minted **c9 named "c8"**, and the
tell read "the c8 (c9)". `_op_introduce` doesn't treat a ref as a ref.

**Fix.**
- **(S)** `_op_introduce` binds a ref to that actor, and refuses a ref-shaped `who` that
  names nobody.
- **(M)** Keepers are minted like everyone else: the descriptor as `name`, the name kept
  back until introduced.

Prior art: Evennia's sdesc and `recog`, and Armageddon MUD.

**Owner question 7a:** keepers named on sight (the name over the shop), or a descriptor
until introduced? **Recommended: descriptor until introduced**, unless the world marks the
keeper as publicly known.

## Item 10: Quin Nutmeg described as a human

- **Every NPC is stored as `race: "human"`** (the `Actor` default, `rules/sheet.py:486`),
  with a Ratfolk face text and no world people id. 8 of 8 NPCs in the save, including the
  Clockwork Spy.
- Keepers, `population.embody` and `speaker_real._embody` write the face but never the
  people. Only the spawn path records the people.
- The human text itself:
  - the player asked "any human women here?", and Gorm answered "There is one" before Quin
    existed;
  - the prose then described human hair and skin;
  - later it flipped to "rodent-featured eyes".

**Fix.**
- **(M)** Every minting door records the people its face was drawn from, through one shared
  helper, and the brief states it as fact.
- **(L, could be later)** A people the prose granted in reply ("There is one") binds the
  next person minted there.

**Owner questions.**
- 10a. Should that promise bind? **Recommended: yes.**
- 10b. Which "human" did you see? The UI prints no NPC race, so it was presumably the prose.

## Item 11: "the stranger Veil"

**Cause.**
- `_known_names` (`gm/agent.py` about 1088) never includes places the engine made
  (`scene.founded`, ventured places, counters), so "Velvet" read as an invented name.
- `unname_strangers` (`gm/narration.py`) then swapped "the Velvet" for "the stranger",
  because its place rule needs the preposition directly before the name.
- "the Great Cathedral" became "the Great the stranger" the same way (6 copies in the 09-25
  recording).

Not a regression.

**Fix (S).**
- Known names include founded and ventured places, exits and counters.
- The place rule allows an article and capitals between the preposition and the name.
- Never substitute inside a capitalised noun phrase.

This also stops the needless polish that cost beat 49 its speech tags.

## Item 12: narration put in Gorm's mouth

**Cause (a regression from the 2026-09-28 fix pass).**
- `keeper_forward` (Lane D) flags the *spoken lines* as the sentences to repair.
- `_repair_sentences` (Lane A) splices the model's rewrite with a string replace **inside
  the quotation marks**. The rewrite paraphrased our own `fix_hint` ("…until you turn to
  them"), with the wrong pronoun too.
- Its acceptance check passes any rewrite that differs.
- Measured: 5 narration sentences inside quotes across beats 51 and 53.
- Contributing: "I ask how much for a woman" was read as `talk` with an unresolved target,
  so Gorm still counted as "in the background".

**Fix (M).**
- A repair aimed at a quoted line widens to the whole speech unit, the quote plus its
  "he says" clause.
- For keeper-forward and master-approaches, a deterministic backstop cuts the quote and its
  clause, with no rewrite.
- A detector: a quote attributed to X that names X in the third person, or echoes the
  fix_hint, is narration in quotes.
- `fix_hint` uses the actor's pronouns.
- `dealt_with` counts an untargeted `talk` to the only keeper present.

Must land before item 1.
