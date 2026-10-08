# Deeds: the plan

Written 2026-10-08 on branch `deeds/research` (off `build/leatherworking` 7b3592e). The research
it rests on is `docs/deeds-prior-art.md` (cited **PA §n**). The measurements are this codebase's,
taken on that commit and cited by file and line. Nothing here is built. Numbers marked
**(proposed)** are mine and live in a rule document the owner can retune; everything else is the
owner's ruling or the book's.

Three parts: the deeds system (§1–§12), the leatherworking hook (§10), and the owner's
"dangerous skinning" ruling (§13), which is a leatherworking rule researched in the same pass.

---

## 1. The ruling

The owner, 2026-10-08 (`docs/leatherworking-questions.md`, plan open point 11):

> "Build out a deeds system that tracks good or bad things you do, most actions should only have
> a small impact, otherwise people will not mean to do certain things and it goes from a funny
> accident to a source of frustration very quickly if they are punished too heavily. for now just
> track this as a number positive for good deed and -negative for bad deeds. you should be able to
> look at this number in your sheet but i dont want it to affect anything yet."

And with it (open point 12, and Q5.2): harvesting a good outsider, or a good-aligned dragon **by
its kind**, is a bad deed. Alignment is not tracked on any sheet; the paladin's smite and holy
weapons hold against any foe "until alignment is added" (`rules/sheet.py:6695-6706`,
`rules/engine.py:21698-21713`).

What it settles:
- one signed number, good positive, bad negative;
- most acts small;
- visible on the sheet;
- **read by nothing**: no price, no attitude, no roll, no narrator.

What it leaves to this plan: which acts, how much each, how accidents are told apart, and where
the number lives.

## 2. What the research changes

The full sweep is `docs/deeds-prior-art.md`. The decisions it drives:

| Finding | Decision here |
|---|---|
| Ultima IV ran a whole moral system on values of 1 to 5 out of 99 (PA §5); RDR2 shrank petty acts to −1 (PA §6); the book ranks acts as a warning, 1 step, 2 steps, or extreme (PA §11) | **Values from −5 to +5, most of them ±1.** The validator refuses anything outside that fence (§8). |
| Fallout 3's +50 water bottle erases ten thefts and its −1000 Megaton swamps everything (PA §2) | **No quest-sized value in this counter.** Quests are not deeds here. |
| Ultima IV judges only the fights the player starts (PA §5); GTA VI's rule, as reported, exempts self-defence and what a mission demands (PA §6); atonement makes an unwitting misdeed cheap (the spell, no 2,500 gp) and a deliberate one dear (PA §11) | **Intent is read in code, three ways: meant, careless, accident** (§5.3). An accident costs 0 or −1, never more. Fighting back is never a deed. |
| RDR2 has no accident rule and its players complain of exactly the owner's "funny accident" (PA §6) | The splash flask's spill and a missed throw's scatter are **accidents**, recorded at 0 (§5.3). |
| Fallout 2 counts only `source_obj == dude_obj` (PA §1) | **Only the player character's own acts.** A companion's acts are theirs. |
| Ultima IV's beggar was farmed through one shared time-only gate; KOTOR had no cooldown; Fallout 4 cools per action; Horror Adventures counts the time between evil castings (PA §4, §5, §8, §11) | **One counted deed per kind per person per game day**, good and bad alike (§8.2). Repeats are still listed, at 0. |
| The book never calls killing evil good (PA §11); the MUDs and Fallout do, and Sawyer's New Vegas retune kept it (evil +5, very evil +30, PA §1, §3, §12) | **Killing a foe is never a deed**, whatever its alignment. |
| RDR2 honor moves unseen; KCD's hidden witness rule reads as a bug; New Vegas keeps witnessed reputation on a separate track (PA §3, §6, §10) | **Witnesses are recorded and never change the value.** What the world knows is the renown system's job (the owner's "renown is a world system"). |
| The gating failures in PA §7, §8 and §11 (ME2 Charm, KOTOR mastery, Wrath's paladin drift) came from a meter something read; the rest had other causes (PA, "What the sweep says", item 7) | **Nothing reads the total**, and a test holds that line (§8.5). |
| Sawyer championed visible +1/−1 changes, while saying he was not championing karma (PA §3) | The sheet shows the number, words, and the list of rows it is the sum of (§9). |

## 3. What exists today (measured)

- **No deeds store.** "Deed" in the code means two other things: a world-class milestone
  (`rules/worldclass.py:106-110`, `Progress.deeds`, a crafting level's gate) and the narrator's
  "deed the player declared" (`gm/agent.py:2914`, `narration.owed_deeds`). Neither is a moral
  record. The new module is `rules/deeds.py` and the tag family is `deed.*`. Neither clashes in
  code. A prose note in `rules/deeds.py` says which "deed" it means.
- **The world's knowledge of crime already exists**, and it is not this. A witnessed break-in or a
  report to the watch writes `state.suspected.<town>` then `state.wanted.<town>` through the one
  applicator (`docs/wanted.md`; `rules/engine.py:4824-4846`, `_witnessed_break_in`). That is the
  New Vegas reputation half (PA §3). Deeds are the karma half. Neither writes the other.
- **The engine already knows intent, harm and consent** at a handful of doors. Every one is
  structural, never prose:
  - `attitude.harmed(engine, victim, by, source, seen=...)` (`rules/attitude.py:599`) is the one
    door all player harm goes through. It has four callers: the attack (`rules/engine.py:6614`),
    the spell (`:15116`), the splash flask (`:17057`) and the ability (`:19134`). It returns
    `{"kind": "attitude", "from": <step before>, "why": "harmed"}`, or `harm_unseen`. It returns
    nothing for a corpse.
  - The battle gate defers the first swing and emits `battle_joined` with the target
    (`rules/engine.py:5668`). That is the moment the player starts a fight.
  - The splash knows its aim. In `_splash_reactions` (`rules/engine.py:17028-17082`), `b is defender`
    is the aimed creature; everybody else caught is spill.
  - `give` marks a non-consensual take as `how: "took_from"`, with the owner kept on the props
    ledger as `stolen` (`rules/engine.py:18385-18390`, `:18234-18239`). It marks a gift as
    `a_gift` (`:18055`).
  - The steal manoeuvre writes `{"kind": "stolen", "from": ...}` (`rules/engine.py:7462`).
  - First aid lifts `dying` in `firstaid.settle` (`rules/firstaid.py:50`). Healing records `heal`
    with the conditions it ends (`rules/engine.py:8218`).
  - `break_in` records `{"kind": "break_in", "opened": ...}` (`rules/engine.py:4777`).
  - Deaths are `{"kind": "condition", "condition": "dead"}` records on the outcome that caused
    them (`_hp_state_effects`, `rules/engine.py:21441`; the coup de grâce at `:6604`).
- **Where outcome and intent meet.** `Engine._drive` appends each resolved outcome at
  `rules/engine.py:3855`. It is the one place that sees the intent (actor, target, origin), the
  outcome and the queue together. `_settle_gate` uses that same spot for the same reason.
- **The stat blocks print alignment and types.** 7,193 blocks carry `alignment`. 530 are good,
  4,030 evil. Only `_printed_alignment` reads it, for the holy/evil-only items.
  - Outsiders: 32 carry `subtype good`, 55 have a printed good alignment, 58 have either. 3 with
    `subtype good` print CE (fallen).
  - Dragons: 9 of 119 print a good alignment. **No metallic true dragon ships in the bestiary**:
    the good dragons are the faerie dragon, the pseudodragon and seven named individuals.
- **Spells carry descriptors.** 138 of 3,040 spells are `[evil]` and 74 are `[good]`
  (`content/spells/spells.json`, `Spell.descriptors`, `rules/spells.py:144`).
- **People carry their trade's tags.** A person's rolled life has `work` and `tags`
  (`rules/lives.py:133`). The beggar occupation (matching beggar, vagrant, urchin) is the one
  tagged `poor` among 53 occupations (`content/people/occupations.json:982`).
- **The save round-trips byte for byte**
  (`test_the_owners_real_saves_round_trip_byte_identically`). A new actor field must be written
  only when non-empty, as `awake_checks` is (`rules/sheet.py:6788`).

## 4. The store

### 4.1 One list on the player's sheet

```python
Actor.deeds: list[dict] = field(default_factory=list)   # append-only; [] on every old save
```

One row per deed, written by **one writer**, `deeds.record`, and never edited after:

```python
{
  "tag": "deed.theft",              # the one vocabulary (§6)
  "value": -1,                      # from the rule row at record time; 0 for a repeat (§8.2)
  "again": False,                   # True when the day's gate made this a repeat
  "how": "meant",                   # meant | careless | accident (§5.3)
  "minute": 18235,                  # scene.clock_minutes
  "place": "5bbd0c40345f/market",   # scene.at
  "subject": "c13",                 # the ref acted on, or None (a spell cast)
  "subject_name": "the merchant",   # said at record time: refs never reach the page
  "what": "a coin purse",           # the thing, where there is one; "" otherwise
  "witnesses": ["c7", "c9"],        # §5.4; refs, for the renown system to read later
  "origin": "rule:deeds/theft",     # the rule row, stage 8's stamp
}
```

- **The total is derived, never stored**: `deeds.total(actor) == sum(r["value"] for r in
  actor.deeds)`. A stored running total next to the list is a second store that can drift. The
  brief's "running total" is this sum. The `deed` effect record on the outcome carries the total
  *after* the row, the way the `xp` record carries `total` (`rules/engine.py:17769`), so the log
  can show it without recounting.
- **No clamp.** Ultima's 99 and Fallout's ±1000 (PA §5, §2) make a total that is no longer the sum
  of the rows the player can read. A total of −40 is a fact about the rows, not a bug.
- **A rule row retuned later does not rewrite history.** XP awarded is not taken back when a table
  changes. The `value` is the row's at the moment.

### 4.2 Why not an `ActiveEffect` per deed

Law 2 asks every change to a number or a state to travel as an `ActiveEffect`. A deed changes no
number in play and grants no state, so it is a record, like `xp` (`rules/sheet.py:455`) and
`herb_known`. Three readings were weighed:

- **One effect per deed.** Refused. `Actor.effects` is walked by every modifier question
  (`_buff_mods`, `has_state`). A campaign's hundreds of permanent deed effects would be walked on
  every roll, to contribute nothing.
- **One effect holding the score**, as regard does (`rules/attitude.py:84-117`, one effect replaced
  whole). Refused. Regard has no history to show. The owner asked for a number the player can read
  *and* the deeds behind it, and an effect whose payload grows a list is the store in disguise.
- **A plain list.** Chosen. `test_no_fourth_store_grows_back_on_the_actor` forbids a second store
  of **timed** records; this list is untimed and passes it by its own reasoning.

**The rule for later.** When a future system makes deeds matter, it reads `deeds.of` / `deeds.total`
and grants an `ActiveEffect` through the applicator: a renown tag, a `knows.*` tag on a witness.
It never adds the total to a roll. §8.5's ratchet makes that a test, not a promise.

### 4.3 Save and load, and old saves

- `actor_to_dict` writes `"deeds"` only when the list is non-empty
  (`**({"deeds": [...]} if actor.deeds else {})`), beside `awake_checks` (`rules/sheet.py:6788`).
- `from_dict` reads `list(data.get("deeds") or [])`.
- **An old save has no key, reads as `[]`, total 0.** No migration step and no `SAVE_VERSION` bump
  (`play/campaign.py:33`). The owner's twelve saves round-trip byte for byte because nothing is
  written for an empty list.
- **Only the player character keeps deeds.** NPC actors never get rows. The field exists on every
  Actor because the dataclass is shared, and it serialises to nothing for them.

## 5. Detection: one reader, one direct door

### 5.1 The reader in `_drive`

```python
# rules/engine.py, Engine._drive, beside outcomes.append(outcome) (:3855)
outcome.effects.extend(deeds.read(self, intent, outcome, partial.get("deeds_before")))
```

- **`deeds.read` classifies the outcome's own effect records** (§7's catalogue) and calls
  `deeds.record` for each deed it finds. It returns the `deed` effect records to append to *that
  outcome*.
- **One site rather than a call in each op**, for the reason `_settle_gate` and `defeat.settle`
  give: it is the one place that sees the intent and the outcome together. A new op's harm is
  found by its records, not by remembering to add a call.
- **It runs only for an intent whose actor is the player character.**

**The snapshot.** Some deeds turn on who somebody *was* before the act. A first blow makes its
victim hostile, and a corpse has no attitude.

```python
deeds.before(scene) -> {ref: {"hostile", "helpless", "dying", "hurt", "party", "sapient", "poor"}}
```

- It is taken when an intent is first entered and kept in `partial["deeds_before"]`. A resume from
  the player's d20 reads the same snapshot. This is the pattern `attack_state["seen"]` uses
  (`rules/engine.py:5614-5621`: "asked once, on the first entry, and kept").
- It is cheap: a scene holds a handful of actors.

The fields:
- **hostile**: `attitude.of(a) == HOSTILE`, or on a side other than the player's in
  `scene.sides`.
- **helpless**: `is_helpless`.
- **dying**: `has_state("state.down.dying")`.
- **hurt**: `hp < hp_max` or nonlethal > 0.
- **party**: `has_state(states.TRAVELS_WITH_YOU)` or the player.
- **sapient**: Int 3 or more on the sheet's `abilities`. 1e's animal intelligence is 1–2. Measured:
  239 of 263 animals are under 3, and 3,749 of 3,756 humanoids are 3 or more.
- **poor**: the person's life tags include `poor`.

### 5.2 The ledger is the memory

Two deeds need to know what happened earlier the same day, and the ledger answers without a new
store:
- **A fight the player started.** The battle gate's `battle_joined` writes
  `deed.violence.unprovoked` against a target who was not hostile. Then `_foes_settle` makes them
  hostile for the fight (`rules/engine.py:3550`). A kill later in that fight is still a murder,
  because a `deed.violence.unprovoked` row names that subject today.
- **A death the player's blow caused later.** Somebody the player dropped to dying who bleeds out
  on a later round dies in a tick, not in the player's outcome. The reader also scans every
  outcome's `dead` records. A death of a subject the player has a `deed.violence.*` row on today
  writes the matching `deed.kill.*` row. This also covers the coup de grâce.

### 5.3 Meant, careless, accident

| How | When, structurally | Example |
|---|---|---|
| **meant** | the subject is the intent's target (`intent.targets()`), or a give/steal/loot/break-in names them | the swing, the theft, the aimed flask |
| **careless** | caught by an area the player placed while aiming at somebody else: a spell's or ability's area, where the victim is not in `intent.targets()` | a fireball that takes the stallkeeper with the thugs |
| **accident** | the splash spill (`b is not defender` in `_splash_reactions`) and a missed throw's scatter (`_scatter`); `outcome.mode == "splash"` marks the outcome | the alchemist's fire that lands a point on the boy by the well |

Fighting back is not a deed at all: a subject hostile in the snapshot is no victim of violence.
This follows Ultima IV's "who attacked first" (PA §5) and GTA VI's "dealing with someone who picks
a fight" (PA §6).

### 5.4 Witnesses

The conscious, non-player actors in the scene when the deed is recorded (`scene.actors`,
`scene.conscious`), companions included. This is the set `_op_break_in` already treats as "it is
seen" (`rules/engine.py:4809-4815`). Three exceptions:
- **The subject** is a witness while conscious, and not when the harm was unseen (`harm_unseen`).
- **A player holding `state.hidden`** has no witnesses but a subject who perceived them.
- **A dead subject** witnesses nothing.

The list is recorded and read by nothing (§8.5). It is there for renown, which will read who saw
what (Dwarf Fortress spreads deeds through the people who know them, PA §12).

### 5.5 The direct door: harvest

Lane C's harvest calls `deeds.record` itself, because the harvest is its own op and the deed turns
on the carcass, not on an effect record (§10).

## 6. How it obeys the three laws

1. **One vocabulary.** Every deed is a tag under `deed.*`. Readers ask by prefix:
   `deeds.of(actor, "deed.kill")` and `deeds.of(actor, "deed.mercy")`. `states.matches` is the one
   matcher, as for `harvest.*` and `state.wanted.*`. The family is listed in the vocabulary's
   prose in `rules/states.py`, as `role.*` and `bond.*` are. There is no `TAGS` row, because a
   deed is not a state anybody holds.
2. **One applicator, and nothing to apply.** A deed changes no number and grants no state (§4.2).
   The one writer is `deeds.record`, and `test_only_deeds_record_writes_the_ledger` holds that.
   Anything that ever makes deeds matter must grant an `ActiveEffect` (§4.2), and §8.5's ratchet
   refuses any other reader.
3. **Severed tells; no model authors a number.**
   - **Values come only from `content/rules/deeds.json` rows.** The validator refuses a value
     outside −5..+5, a tag not under `deed.`, or a row with no `said` or `source`, and names the
     fix in the classbuilder's style. No model proposes a deed. There is no `deed` op in the
     intent schema, and the sampler enum never offers one. `deeds.record` refuses a tag with no
     rule row.
   - **The narrator is told the act, never the verdict.** The deed rides as a
     `{"kind": "deed", ...}` record on the outcome of the act that earned it. That outcome
     already carries the act's tell ("takes the purse from the merchant, who did not hand it
     over"). `test_an_outcome_with_literal_effects_carries_a_tell` holds because no deed outcome
     is new.
   - **No sentence like "that was a bad deed" reaches the prose.** A narrator handed one would
     moralise, and the owner's "affect nothing" includes the story. The player sees the deed in
     the history line and on the sheet (§9), which is Sawyer's visible +1/−1 (PA §3).
   - This is the plan's position. Open point 4 asks the owner to confirm it.

## 7. The catalogue: what the engine can detect today

Every row is a rule row in `content/rules/deeds.json`. The value is **(proposed)**. "Gate" is §8.2.

### 7.1 Bad deeds

| Tag | Value | What is detected | Hooks | Why this value |
|---|---|---|---|---|
| `deed.violence.unprovoked` | **−2** | The player starts violence against a sapient creature that was not hostile: `battle_joined` at such a target, or a harm record (`attitude`, `why: harmed`, `from` not hostile) on one who is meant. | `_op_attack` battle gate (`:5668`); `attitude.harmed` records from the attack, spell and ability doors | Ultima IV's −5 of 99 for attacking a non-hostile (PA §5); the book's 1 step for an execution (PA §11). Started by the player and meant, so it is more than the petty −1. |
| `deed.violence.careless` | **−1** | The same, but caught by an area aimed at somebody else | spell / ability harm records whose victim is not in `intent.targets()` | Collateral harm is the player's doing but not their aim |
| `deed.violence.accident` | **0** | The same, by the splash spill or a scattered throw | `_splash_reactions` records with `b is not defender` | The owner's "funny accident". Listed so the player sees it was noticed and forgiven, and costs nothing (atonement's unwitting misdeed, which skips the 2,500 gp, PA §11) |
| `deed.kill.unprovoked` | **−3** (with the violence row: **−5** in all) | A sapient creature dies by the player's meant act when it was not hostile, or when the player's `deed.violence.unprovoked` row names it today (§5.2) | `dead` condition records on the player's outcome, or any outcome's for a subject the ledger names | Murder is the gravest act the engine can see. −5 in all is five thefts. Fallout 3 makes it twenty (PA §2), and open point 1 asks. Written on top of the violence row, so one blow and ten blows weigh the same |
| `deed.kill.careless` | **−1** (−2 in all) | Death from a careless harm | as above | Collateral death weighs more than collateral harm, and much less than murder |
| `deed.kill.accident` | **−1** | Death from the spill or the scatter | as above | A death is never nothing. The owner's "small" for an accident is −1 |
| `deed.kill.captive` | **−2** | A helpless sapient creature that was hostile, killed by the player **outside a fight** (`not scene.in_encounter`): the beaten bandit finished on the ground after the fight | coup de grâce (`:6604`) or any blow; snapshot `helpless` and `hostile` | The book's own example: "executing a captured orc combatant" is 1 step toward evil (PA §11). The same act mid-fight is tactics, and not a deed |
| `deed.theft` | **−1** | The player takes from a person without consent: `give` with `how: "took_from"`; a steal manoeuvre (`stolen`) on a target not hostile; `loot` of a living, down subject who was not hostile | `_op_give` (`:18389`), `_outcome_take` (`:7462`), `_op_loot` (`:11195`) | Fallout's flat theft and Ultima's −1 for a chest (PA §2, §5). **Not scaled by value**: a fork and a fortune are both a theft, and value scaling would make one theft a quest-sized number (§2). Robbing a hostile in a fight, or a corpse, is not theft here |
| `deed.trespass` | **−1** | A home's door opened by `break_in` | `_op_break_in` (`:4777`, `opened: true`) | Petty, and the law's `state.suspected` already answers the town's half |
| `deed.harvest.good-outsider` | **−2** | Any part taken from an outsider with `subtype good` or a printed good alignment | lane C's `harvest.take` (§10) | The owner's ruling. The creature is already dead, so this is the act on the body: less than its killing would have been had it been innocent |
| `deed.harvest.good-dragon` | **−2** | Any part taken from a `type.dragon` whose stat block prints a good alignment ("by its kind") | lane C's `harvest.take` | The owner's open point 12, the same weight as the outsider |
| `deed.spell.evil` | **−1** | The player casts a spell with the `[evil]` descriptor | `_op_cast` outcome; the spell's `descriptors` | "Casting an evil spell is an evil act, but... once isn't enough to change her alignment" (PA §11). Counted at most once a day (§8.2). Open point 2 |

### 7.2 Good deeds

| Tag | Value | What is detected | Hooks | Why this value |
|---|---|---|---|---|
| `deed.mercy.saved` | **+2** | The player stops somebody outside the party from dying, by a first-aid success or by healing that lifts `dying`, **foe or not** | `firstaid.settle` record (`condition: stable, by: first aid`); `heal` outcomes listing `dying` among `ends` | The mirror of the execution's 2. Mercy to an enemy counts: KOTOR and Ultima both reward sparing (PA §5, §8) |
| `deed.mercy.tended` | **+1** | The player heals hit points of somebody outside the party who was hurt and not hostile (spell, potion handed and drunk, ability) | `heal` records with `amount > 0` on such a subject | A small kindness, gated per person per day so a cure-light-wounds wand cannot farm it |
| `deed.mercy.subdued` | **+1** | A hostile sapient creature brought down by the player's **nonlethal** damage instead of killed | a `damage` record with `lethality: "nonlethal"` and an `unconscious` condition record on the same ref | Choosing not to kill. RDR1's alive-bounty reward, Ultima's letting a foe go (PA §5, §6). A later execution (`kill.captive` −2) outweighs it |
| `deed.charity.alms` | **+1** | Coin given freely (`a_gift`, a coin denomination) to a person whose life is tagged `poor` | `_op_give` (`:18055`, `:18432`) | Ultima's beggar: +2 of 99, whatever the amount (PA §5). +1 here, and **per beggar per day**: the gate Ultima lacked |
| `deed.restitution` | **+1** | The player hands an item to the person the props ledger names as its owner when the record is `stolen` | `_op_give` with `how: "handed"` and the prop's `owner == taker` | Undoing a theft. A player who stole and returns it nets 0 |
| `deed.spell.good` | **+1** | The player casts a spell with the `[good]` descriptor | `_op_cast` | Horror Adventures' sidebar applies its advice to the other alignment descriptors too (PA §11). Once a day. Open point 2 |

**Eighteen rows: twelve bad (one of them always 0) and six good.** The asymmetry is the engine's,
not a judgement. It sees harm in four doors and kindness in three (heal, first aid, give).

### 7.3 Not yet: the engine cannot see these, so they are not guessed

None of these is read from prose. Each waits on the named engine fact:

- **Sparing a foe who surrenders or flees.** There is no surrender state. Surrender travels as
  narration (`gm/judgement.py:2812`, `gm/prompts.py:2560`), and only troops rout
  (`rules/troops.py`). This waits on a yield state.
- **Freeing a captive, keeping a promise, betraying a companion.** No captive or promise is held
  by the engine.
- **Desecration** (a grave, a shrine, a body). No op touches a grave or an altar.
- **Killing livestock or a pet.** Animals are not sapient (§5.1), so killing a farmer's cow writes
  nothing today. Ownership of animals is not on the props ledger. This waits on owned creatures
  and would be a `deed.theft`-weight row.
- **Quests that help people.** Quest cards carry no good/bad marking, and quest-sized values are
  refused anyway (§2).
- **A companion's deeds on the player's orders.** Companions obey in character (ruling
  2026-10-01). Whether an order makes the deed the player's waits on an order record.
- **Selling stolen goods** and **looting corpses.** Considered and not deeds. The theft was
  counted once, and corpse-looting is every adventurer's trade (Fallout and the book are silent).
- **Insults and provocation.** Not deeds. Regard already answers them (`rules/provocation.py`).
- **Lying (Bluff).** Not a deed. Deception is a skill in 1e; the paladin's code is a class rule,
  and a class reading this number is Wrath's paladin drift (PA §11).
- **Poison use, animate dead's minions acting, curses.** Counted through the cast where the spell
  is `[evil]`; nothing further.

## 8. The scale

### 8.1 The numbers

- Most acts are **±1**. The deliberate harms and the life saved are **±2**. Only murder reaches
  **−5**, and only as two rows. An accident costs **0**, or **−1** if somebody died.
- The validator fences every value to −5..+5. A row outside the fence is refused with the fix
  named: "a deed is a small number; a quest-sized value belongs to a quest, not here (PA §2)".

### 8.2 The day's gate

- **One counted deed per tag per subject per game day.** For the two spell tags, which have no
  subject, it is once per day.
- A repeat is still recorded, with `value: 0` and `again: true`, so the list stays honest and the
  player sees "again, the same day".
- The gate is in the rule row (`"gate": "subject-day"` or `"day"`), so a later row can choose
  differently.
- Bad acts are gated too, unlike Ultima IV (PA §5). Ten snatches at one stall in a minute is one
  theft for the counter's purposes, which keeps a bit of business at a stall from becoming a
  catastrophe.
- Kills need no gate: the dead die once.

### 8.3 Accidents

- The splash spill and the scattered throw are accidents (§5.3). Harm by accident is **0** and
  death by accident is **−1**.
- An area the player aimed at somebody else is careless: **−1** and **−2**.
- **Nothing that happens to the player is a deed.** Being robbed and fighting back are not deeds.

### 8.4 Words

The words are presentation. They live in `deeds.json` as `bands`. **(Proposed;** open point 5.)

| Total | Word |
|---|---|
| −30 or less | Cruel |
| −29 to −10 | Callous |
| −9 to −3 | Rough-handed |
| −2 to +2 | Unremarkable |
| +3 to +9 | Decent |
| +10 to +29 | Kind |
| +30 or more | Selfless |

The bands are sized for a scale whose unit is 1. Ten thefts make you callous; fifteen people
pulled back from dying make you kind.

### 8.5 Nothing reads it yet: a ratchet, not a promise

`test_nothing_reads_the_deeds_yet` allows exactly these callers of `deeds.total`, `deeds.of` and
`Actor.deeds`:
- `rules/deeds.py`
- the sheet payload (`rules/sheet.py: full_sheet`)
- the deeds and history views (`play/views.py`, `play/history.py`)
- the save (`actor_to_dict`/`from_dict`)
- the harvest's call to `deeds.record`

Any other reader fails the test. Its docstring names the defect it prevents: ME2's Charm options,
KOTOR's mastery and Wrath's paladin drift all failed because something read the meter (PA §7, §8,
§11). It also asserts that `gm/` never names `deeds`, so the
narrator never hears the number.

## 9. The sheet, the history, the API

### 9.1 The Sheet tab

There is **a "Deeds" card** in `pageSheet` (`play/static/js/table/05-sheet.js:51-61`), after
Class and before Background and notes. It is a `sheetCard` like the others:
- **The number, signed, large** (`+7`), and **the word** beside it ("Decent").
- **One line of counts**: "12 good, 5 bad, 2 not counted (the same thing again that day)".
- **The history, newest first**. Each row reads:
  - the game day and hour, as the journal writes them;
  - where, by place name;
  - what, from the row's `said` template ("Took a coin purse from the merchant without asking");
  - the value as a chip: `+1`, `−2`, or `0 · accident`.

  The first twenty are shown, with "Show all" fetching the rest.
- **One line of honesty under it**: "Nothing in the game reads this number yet. It changes no
  price, no person and no roll." That is the owner's ruling, said to the player.
- **Empty**: "No deeds yet."

The look follows the owner's standing instruction for UI work: the frontend-design and
design-taste-frontend skills, keeping colours, images and textures unchanged
(`sheetCard`, `.v2-card-leather`, the existing `.terms` rows).

### 9.2 The journal's History

`play/history.py:_effect_lines` gains `kind == "deed"`. It writes "A deed: took a coin purse from
the merchant (−1)." or "Not counted: the same again that day." This uses the sentence shape `xp`
uses (`play/history.py:240`), so the running history shows deeds as they happen. That is the
visible change Sawyer asked for (PA §3).

### 9.3 The API

- `full_sheet(actor)` gains `"deeds": deeds.summary(actor)`:
  `{"total", "word", "good", "bad", "again", "rows": [the newest 20, display-ready], "more": bool}`.
  The sheet is fetched on demand (`play/views.py:1146`), so this costs nothing per turn.
- `GET api/deeds?before=<n>` returns older rows, twenty at a time. It is registered beside
  `api/history` in `pathfindergm/urls.py`.
- Each display row carries `subject_name` and the place's name, **never a ref** (the ruling
  "refs never on the page"). The refs stay in the save for renown.
- `Actor.summary()` (sent every turn) is **not** given the deeds. Nothing on the table needs them
  per turn.

## 10. The leatherworking hook

Lane C (`docs/leatherworking-contracts.md` §5.4) is already promised a deeds store. This plan
supersedes that section's shapes. The contract changes are:

- **`rules/deeds.py` moves out of lane C to the deeds lane** (§11). Lane C only calls it.
  `leatherworking-contracts.md` §1 and §5.4 need that one edit.
- The kind rule lives in the deeds module, so harvest never spells it:

  ```python
  deeds.of_carcass(creature) -> str | None
  #   "deed.harvest.good-outsider" when the body is `type.outsider` and has `subtype.good` or a
  #   printed good alignment (`_printed_alignment`); "deed.harvest.good-dragon" when it is
  #   `type.dragon` with a printed good alignment; else None. Tags and the printed field
  #   only, never the name.
  ```

  `_printed_alignment` is private to `rules/engine.py` today (`:21698`). DEED-1 moves it to
  `rules/bestiary.py` as the one reader of a block's printed alignment, and the engine's two
  callers import it from there. Otherwise deeds would grow a second copy of the rule.

- `harvest.parts` puts that answer in each row's `deed` field (contracts §5.2, already shaped for
  it), so the confirm shows before the roll (UI plan §6.9).
- `harvest.take` calls, **once per carcass, not once per part**:

  ```python
  deeds.record(actor, tag, scene=scene, subject=creature.ref, subject_name=creature.name,
               what="", how="meant")
  ```

  The day's gate (§8.2) holds that anyway, because the subject is the carcass. It returns the
  `deed` effect record, and harvest's outcome carries it.
- `deeds.record`'s signature keeps contracts §5.4's keywords (`minute`, `place`, `subject`,
  `witnesses`). With `scene=` given, it reads `minute`, `place` and witnesses itself (§5.4).
- **Native outsiders are not humanoids.** 225 blocks are native outsiders, among them aasimar,
  tiefling, sylph, suli and nephilim, which are peoples, not beasts. The humanoid ban
  (leatherworking plan §5.6) does not cover them. They yield nothing today only because untagged
  outsiders yield nothing (plan §5.3). A hand tag on one would let the player skin a tiefling with
  no deed at all. Open point 3.

## 11. Build lanes

One lane builds the deeds system. Lane C of leatherworking consumes it.

| Lane | Owns | Reads only |
|---|---|---|
| **DEED-1: store and reader** | NEW `rules/deeds.py`; NEW `content/rules/deeds.json`; `rules/sheet.py` (the `deeds` field, its two serialisation lines, `full_sheet`'s `deeds` key); `rules/engine.py` (the `_drive` call, the `partial["deeds_before"]` snapshot, and importing `printed_alignment` only); `rules/bestiary.py` (`printed_alignment`, moved from the engine); `rules/states.py` (the `deed.*` prose entry only); `tests/test_deeds.py`, `tests/test_deeds_catalogue.py` | `rules/attitude.py`, `rules/firstaid.py`, `rules/spells.py`, `rules/lives.py` |
| **DEED-2: sheet and history** | `play/static/js/table/05-sheet.js` (the Deeds card), its CSS, `play/history.py` (the `deed` line), `play/views.py` (`api/deeds`), `pathfindergm/urls.py` (that route only); `tests/test_deeds_api.py` | `rules/deeds.py` |
| **Leather C** | calls `deeds.of_carcass` and `deeds.record` from `rules/harvest.py` | `rules/deeds.py` |

DEED-1 merges before Leather C needs it. Leather C can build against a two-line stub of
`deeds.record` / `deeds.of_carcass` and swap it at merge.

## 12. Tests each lane must add

Each names the defect it prevents in its docstring.

**DEED-1**
- `test_an_old_save_has_no_deeds_and_writes_none`: an old campaign loads with `deeds == []` and
  saves byte-identical. The defect: a new field written as `"deeds": []` would break all twelve
  owner saves' round trip.
- `test_the_total_is_the_sum_of_the_rows`: no stored total exists to drift.
- `test_a_splash_on_the_boy_by_the_well_costs_nothing`: alchemist's fire aimed at a thug, spill on
  a non-hostile bystander. One `deed.violence.accident` row at 0. The defect it prevents is RDR2's
  "accident punished me" (PA §6); the owner's "funny accident".
- `test_swinging_at_the_merchant_is_one_deed_however_many_blows`: three blows in one fight, one
  counted −2. The defect: the first blow makes him hostile through `_foes_settle`, and a reader
  without the ledger memory would score the later blows as fighting back.
- `test_murder_weighs_the_same_in_one_blow_or_ten`: −5 in both cases.
- `test_a_merchant_who_bleeds_out_after_your_blow_is_still_your_kill`: a kill row from a later
  tick.
- `test_fighting_back_is_never_a_deed`: a robber who opened the fight is killed, and no row is
  written. This is Ultima IV's "who attacked first".
- `test_killing_a_red_dragon_writes_nothing`: killing evil is not good (PA §11, §12).
- `test_ten_snatches_at_one_stall_are_one_theft`: the day's gate.
- `test_the_same_beggar_twice_a_day_counts_once`: Ultima IV's farmed beggar (PA §5).
- `test_a_resumed_attack_reads_the_same_snapshot`: suspend on the player's d20, resume, and the
  victim's pre-blow attitude is the one recorded.
- `test_only_the_player_records_deeds`: a companion's kill writes nothing (Fallout 2's
  `dude_obj`).
- `test_witnesses_are_recorded_and_change_nothing`: the same theft seen and unseen has the same
  value.
- `test_a_deed_value_outside_five_is_refused_with_the_fix_named`.
- `test_no_model_can_author_a_deed`: no `deed` op exists in the intent schema or the sampler enum,
  and `deeds.record` refuses a tag with no rule row.
- `test_nothing_reads_the_deeds_yet`: §8.5's allowlist, plus `gm/` naming no deeds.
- `test_only_deeds_record_writes_the_ledger`: no other module appends to `Actor.deeds`.
- `test_the_narrator_is_never_told_a_deed`: the deed record's outcome tell is the act's own, and
  no `deed` text reaches `gm/prompts`.

**DEED-2**
- `test_the_sheet_shows_the_number_the_word_and_the_rows`: a save with three deeds renders all
  three on the card, newest first.
- `test_no_ref_reaches_the_deeds_page`: the "refs never on the page" ruling.
- `test_the_history_writes_a_deed_line`.
- Verified in the running app (CLAUDE.md), not only in tests: take a purse from a merchant on a
  copy of an owner save, open the Sheet, read the row.

**Leather C** (added to its §23.1 list): `test_harvesting_an_archon_writes_one_deed_per_carcass`
(six parts, one row); `test_a_pseudodragon_is_a_good_dragon_by_its_printed_alignment`;
`test_the_carcass_deed_never_reads_the_name` (a renamed archon still writes the deed).

## 13. Dangerous skinning

### 13.1 The ruling, and what the book has

The owner (leatherworking open point 10, 2026-10-08): *"dangerous hides should not bite they
should force another round of checks to avoid poison, acid or elemental dmg while skinning."*

**What 1e prints** (PA §11's sweep, Part B; the critic pass at the end of the prior-art doc):
- **Ultimate Wilderness, Harvesting Poisons (p.142)** is the one 1e rule found for harvesting a
  *dead* creature with a risk to the harvester (the same section's Milking Venom risks a bite from
  the *living* donor on a Handle Animal failure by 5) (https://aonprd.com/Rules.aspx?Name=Harvesting+Poisons&Category=Mastering+the+Wild,
  read 2026-10-08). The terms:
  - the check is "Survival check (DC = 15 + the dead creature's CR)", over 10 minutes with
    surgical tools;
  - "Failing the check causes all of the venom to be lost";
  - failing by 5 or more "exposes the harvester to 1d3 doses of the creature's venom unless she
    has the poison use class feature".
- **Multiple doses** (CRB p.557, Poison, https://www.aonprd.com/Rules.aspx?Name=Poison&Category=Afflictions):
  "Each additional dose extends the total duration of the poison (as noted under frequency) by
  half its total duration. In addition, each dose of poison increases the DC to resist the poison
  by +2." The same paragraph says injury and contact poisons "cannot inflict more than one dose of
  poison at a time"; Harvesting Poisons' 1d3 doses is the specific rule that overrides it. (The
  d20pfsrd text of this rule reads differently, with "These increases are cumulative" and stacking
  only while an earlier dose is still active and the new save failed; its source printing could
  not be identified. For 1d3 doses arriving at once, both readings give one save at +2 per dose
  past the first.)
- **Ultimate Wilderness's Trophies and Treasures (p.162)** (Survival or Heal, DC 15 + CR) and
  **the Monster Hunter's Handbook's Harvest Parts feat (p.24)** (Craft or Heal) have no hazard rule
  at all.
- **Burn (Ex)**: whoever hits the creature with a natural weapon or unarmed attack takes its fire
  damage automatically, and makes a Reflex save, DC 10 + ½ racial HD + Con, only to avoid catching
  fire (https://www.aonprd.com/UMR.aspx?ItemName=Burn).
- **Heat (Ex)**: "its mere touch deals additional fire damage"
  (https://www.aonprd.com/UMR.aspx?ItemName=Heat).
- **Acid**: the CRB's acid effects deal 1d6 per round of exposure and 10d6 immersed. A flask of
  acid is 1d6 on a direct hit (Ultimate Equipment p.107,
  https://www.aonprd.com/EquipmentMiscDisplay.aspx?ItemName=Acid).
- **No 1e rule found speaks of a dead creature's acid or fire** (none in the three harvesting
  texts above; a negative across the whole line could not be confirmed). Extending Burn, Heat and
  acid to skinning is a house extension, and is said so on the card.

### 13.2 What makes a body dangerous: tags, derived from fields

There is one function, `harvest.dangers(block) -> list[danger]`. Lane C's tag pass
(`tools/harvest_tags.py`) writes its answers as tags into the stat blocks, in the reviewed table.
The same function is the reader's fallback for untagged blocks (a World Bible beast), as
generic hides are (leatherworking plan §5.3). **It reads stat-block fields, never a name.**

| Tag | Read from | Harvestable blocks (animal, magical beast, vermin, dragon: 680) |
|---|---|---|
| `harvest.danger.poison` | a natural attack's or special attack's `plus poison` rider (`melee`, `ranged`, `special_attacks`); a printed `Poison (Ex/Su)` paragraph (`special_abilities`); poisonous flesh or blood printed in `special_abilities` | 132 with a poison attack; 3 with a poisonous body |
| `harvest.danger.acid` | an attack's `plus Nd6 acid`; `corrosion`; an acid breath weapon | 11 riders, 1 corrosion, 25 acid breaths |
| `harvest.danger.fire` | `plus Nd6 fire`; `burn`; `heat`; `subtype fire`; a fire breath | 5 riders, 2 burn, 5 heat, 27 subtype, 26 breaths |
| `harvest.danger.cold` | `plus Nd6 cold`; `subtype cold`; a cold breath | 10, 19, 15 |
| `harvest.danger.electricity` | `plus Nd6 electricity`; an electricity breath | 5, 9 |
| `harvest.danger.sonic` | a sonic breath | 4 |

(The kinds overlap: a red-dragon-like block is a fire subtype *and* a fire breath. Counted by
`content/bestiary/*.json` on 7b3592e.)

**Refused, with reasons:**
- **Auras.** An aura is the living creature's (only 4 harvestable blocks print one).
- **Immunity alone.** A fire-immune hide is a fine hide, not a hot one.
- **Air, earth and water subtypes.** No energy.
- **Negative-energy and other breaths** (26). There is no book damage for touching them.

### 13.3 The second round

- **When.** Once per carcass per danger kind, at the first part taken. The body is opened once,
  and a dragon's six parts are not six exposures. A poisonous fire-breather has two rounds: one
  poison, one fire. **(Proposed;** open point 6.)
- **The check.** The skill of the part being taken (Survival for an external part, Heal for an
  internal one), with the Leatherworker level and the skinning kit's +2 that the harvest roll
  already carries (owner's answer 4). It is rolled as the player's own d20, through the same
  roll door as the harvest.
- **The DC: the creature's own number.** Use the printed DC where the block prints one: the poison
  paragraph's "save Fort DC N", or burn's "(1d8, DC 16)". Otherwise use the universal monster rule
  DC, **10 + ½ HD + Con modifier** (`Engine._rider_dc` already uses this shape with Str,
  `rules/engine.py:12773-12776`; Con is the book's for poison and burn). No DC is authored.
  Using a saving-throw DC (Fort for poison, burn's Reflex-to-avoid-ignition) as a skill check's DC
  is **this plan's extension, not the book's**: Harvesting Poisons has no second round, and its
  one check is Survival at 15 + CR with exposure on failing that check by 5.
- **Failure exposes. Success is told** ("You work the hide off around the venom sac"). This is
  Harvesting Poisons' shape. The owner asked for a round whose whole purpose is avoidance, so any
  failure exposes, rather than failure by 5 or more **(proposed)**.

### 13.4 What an exposure deals

**Poison, through the one poison door.** The block's printed paragraph goes through
`effects.extract`, which already turns "save Fort DC 27 … effect 1d2 Strength damage" into a
`save_gate` and an `ability_damage` spec (measured 2026-10-08). From there it follows the
`taste` op's path (`rules/engine.py:20760-20880`):
- `consumables.poisons` groups the gate with its effect;
- `_gate_intent` emits the Fortitude save;
- the effect is gated by `_settle_gate`;
- the whole runs as `validate([...], origin="creature:<template>")`.

So stage 8's provenance, the mind gate and immunity all apply, and the effect lands only on a
failed save.

The details:
- **Doses.** 1d3 doses, as Harvesting Poisons says. Each dose past the first adds +2 to the save
  DC (CRB, cumulative).
- **Not built.** The duration and frequency ("1/round for 6 rounds") land once. A poison's track
  needs `ActiveEffect.periodic`'s executor, which the ledger lists as promised, not built.
- **The poison use exemption.** It is read as a tag (`trait.poison-use`). **No class grants it
  today**: `content/classes/` has no alchemist. The tag is honoured where it appears.
- **The extractor gap, measured.**

  | Harvestable blocks | Count |
  |---|---|
  | have a poison attack | 132 |
  | print the paragraph | 79 |
  | parse to save and effect today | 34 |

  The 45 between are abbreviated effects ("effect 1d2 Con"). `effects.extract` reads "Strength"
  and not "Str". Teaching it the six abbreviations is the lane's first change, and the review
  table reports the new parse count.
- **Blocks with no paragraph.** 53 print no paragraph. Every one of `core.json`'s 782 blocks
  lacks `special_abilities`. For these **the poison round does not run**, and the review table
  lists them. A poison nobody printed is not invented. A hand mapping to the same creature's
  `creatures.json` block, where one exists, is the reviewed fix.

**Acid and energy, through the hazard door.** Damage goes through the `hazard` op with new rows
in `content/rules/hazards.json`:

```json
"contact-acid":        {"type": "acid",        "dice_per_unit": "1d6", "slot": {"name": "rounds", "min": 1, "max": 1, "per": 1},
                        "source": "CRB, Acid Effects — 1d6 per round of exposure; a dead acid body touched once"},
"contact-fire":        {"type": "fire",        ... "source": "Burn / Heat (UMR); one touch"},
"contact-cold":        {"type": "cold",        ...},
"contact-electricity": {"type": "electricity", ...},
"contact-sonic":       {"type": "sonic",       ...}
```

- **The amount is the book's small one.** It is 1d6, or the creature's own printed burn or heat
  dice where it prints them (burn 1d8 is 1d8 fire), and never its breath weapon's dice. The
  gland is not the breath.
- **Resistance and immunity apply** through `take_damage`, since the row's type is the energy.
- The `hazard` op stamps `origin: rule:contact-<energy>`, so
  `test_every_number_that_lands_names_a_document_it_came_from` covers it.
- The tell is the hazard's ("the acid in the pudding's flesh eats into your hands").

### 13.5 Tests (Leather C, or a lane of its own)

- `test_a_giant_scorpion_forces_a_poison_round_once_per_carcass`: taking three parts makes one
  round. The defect: per-part exposure would make a dragon six hazards.
- `test_a_failed_poison_round_goes_through_the_poison_door`: the save at the printed DC, +2 per
  extra dose. The effect lands only on a failed save. The origin is `creature:<template>`.
- `test_an_unprinted_poison_is_never_invented`: a core block with a "plus poison" rider and no
  paragraph runs no poison round.
- `test_the_extractor_reads_abbreviated_abilities`: "effect 1d2 Con" parses. The measured 34 of
  79 rises to the new count.
- `test_a_fire_bodied_hide_burns_for_its_own_burn_dice`: a fire elemental-like block with burn
  1d8 deals 1d8 fire on failure, and fire resistance applies.
- `test_dangers_never_read_the_name`: a renamed scorpion is still poisonous.
- `test_an_aura_is_not_a_danger_to_the_skinner`.

## 14. Open points for the owner

1. **How heavy is murder?** Proposed: killing somebody who was not hostile is −5 in all (the
   assault −2 plus the death −3), the weight of five thefts. Fallout 3 makes it twenty thefts
   (PA §2). Keep −5, or make it heavier?
2. **Do evil and good spells count?** The book (Horror Adventures) says casting an `[evil]` spell
   is an evil act, one cast is not enough to change anyone, but two typically make a good creature
   nongood and three make it evil, less so the longer between castings (PA §11). Proposed: `[evil]` −1 and `[good]` +1, each
   at most once a day. This covers 138 and 74 spells. Yes, or leave spells out?
3. **Which outsiders are "good", and the peoples who are outsiders.**
   - Proposed: either the good subtype or a printed good alignment counts. That is 58 blocks; the
     subtype alone is 32.
   - Separately, for leatherworking: aasimar, tieflings and the other native outsiders (225
     blocks) are peoples but not humanoids, so the "humanoids are never skinned" rule misses
     them. Proposed: treat `subtype.native` outsiders as humanoids are treated, so they are
     never skinned and the validator refuses a hide tag on them. Reading `languages` instead
     would not separate peoples from beasts: 222 of the 225 native outsiders print a
     language, but so do 680 of all 708 outsiders.
4. **Should the narrator hear about deeds?** Proposed: **no**. The prose is told what the player
   did, and the player sees the number on the sheet and in the history. A narrator told "a bad
   deed" would moralise, and that is an effect.
5. **The words.** Cruel, Callous, Rough-handed, Unremarkable, Decent, Kind, Selfless, at
   −30 / −10 / −3 / +3 / +10 / +30 (§8.4). Keep these, or choose your own?
6. **Dangerous skinning: once per carcass, any failure exposes.** Proposed: one second round per
   danger kind per carcass, at the first cut, with any failure exposing. The other choice is
   Harvesting Poisons' "fail by 5 or more". Keep the proposal, or use the book's margin?
