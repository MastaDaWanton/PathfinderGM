# Rules audit — Pathfinder GM 0.3.4 (master 0b5e5be0), 2026-11-15

Seven engine areas that had never been read against the book (docs/outstanding-2026-11-13.md,
C2): summoning, metamagic, item powers, wards, concealment, combat manoeuvres and effect
validation. For each area I found the path the player actually reaches (a cast from the
Spells tab, `/api/use` from Equipment, a manoeuvre in a fight) and read it against the rule
text on aonprd.com / d20pfsrd.com. Most findings were confirmed with small engine probes on
the fixture PC. Each fix has a test in `tests/test_rules_audit_2026_11_15.py`, and the
docstring of each test names what was measured before the fix.

A critic pass on the first readers' notes reversed three claims. They are listed at the end
so nobody "fixes" them.

**Areas the other lane owns, not touched here:** secondary natural attacks, Power Attack,
composite bows, blinded/sightless (including a blinded attacker's miss chance), charm
breaking, held saves.

## Fixed (highest severity first)

1. **Shield did not stop magic missile, and no spell's immunity was ever granted** (`rules/engine.py` `_EXECUTES`, `_run_one`)
   - Rule: Shield, "It negates magic missile attacks directed at you." ([aonprd](https://aonprd.com/SpellDisplay.aspx?ItemName=Shield))
   - What the engine did: a cast's `immunity` spec was shown to the GM and never applied. That covers 133 specs across the corpus, including fiery body's fire, gaseous form's criticals and heroism's fear.
   - Player sees: a shielded wizard took all five missiles at CL 10 and went to -7 hp.
   - Fix: `_grant_immunity` grants the spell's immunity through `Actor.grant_defence` for the spell's duration. In the cast loop, `_immune_to_spell` removes from the target list any target whose immunity names this spell. The match is on the whole name, never a stem.
   - Severity: high. Status: **fixed**.

2. **Summoned creatures never left** (`Engine._summon`, `Scene.lift`, `Scene._end_standing`)
   - Rule: "When the spell ends or is dispelled, a summoned creature is instantly sent back to where it came from." ([aonprd, Conjuration (Summoning)](https://aonprd.com/Rules.aspx?Name=Conjuration&Category=Magic%20Schools))
   - What the engine did: `_summon` gave the creature no lifetime, and the end of a fight did not remove it.
   - Player sees: a 3-round celestial dog was still there 100 rounds later and after the fight.
   - Fix: each arrival is held by a `Manifestation` that carries the spell's clock (new `creature` field). Expiry, dispel and the end of the encounter all reach `Scene.lift`, which removes the creature through `Scene.remove`. A `summon_ended` tell says it is gone.
   - Severity: high for anything using the `summon` type (homebrew spells and items; see N1 for the shipped spells). Status: **fixed**.
   - Also fixed: "goes away if it is killed or if its hit points drop to 0 or lower". The scene's round tick ends the summons of a creature that is down.

3. **Blur and displacement changed no roll** (`content/spells/mechanics/part-03.json`, `part-06.json`)
   - Rule: Blur grants "concealment (20% miss chance)". Displacement grants "a 50% miss chance as if it had total concealment".
   - What the engine did: both spells were written as prose with a "VOCABULARY GAP" note. The `concealment` type was later built for exactly these two spells, and they were never moved onto it.
   - Player sees: the caster's miss chance stayed 0 after casting either spell. The potion of blur did work.
   - Fix: both documents now carry a `concealment` spec.
   - Severity: high. Status: **fixed**.

4. **A malformed duration validated clean, then became permanent** (`rules/effectspec.py` `validate` → `_duration_problems`)
   - What the engine did: `validate` had no branch for the `duration` field.
   - Measured: `{"amount": "2d", "unit": "hour"}` and `"banana"` both passed. `Engine._duration_rounds` then read them as no duration, which means permanent. `-3` became 1 round, and `"weeks"` became rounds.
   - Player sees: a typo in a homebrew buff's duration means it never wears off.
   - Fix: a duration must be an object with a known unit and a non-negative number or dice. The whole shipped corpus was checked and has no case that now fails.
   - Severity: medium. Status: **fixed**.

5. **Agile Maneuvers did nothing** (`content/feats/mechanics/core.json`, `Actor.cmb_modifiers`)
   - Rule: "You add your Dexterity bonus ... instead of your Strength bonus." (CRB, Agile Maneuvers)
   - What the engine did: the feat had no document and nothing read it.
   - Player sees: a Str 8 / Dex 18 PC who took the feat kept a CMB built on -1.
   - Fix: a `cmb_ability` field in the feat-document grammar, validated by `classbuilder` and read by `Actor._cmb_ability`. The feat's card says what it does.
   - Severity: medium. Status: **fixed**.

6. **Oozes and fliers could be tripped** (the `Engine._check_legality` manoeuvre gate; `_printed_riders` for a monster's trip)
   - Rule: "Some creatures—such as oozes, creatures without legs, and flying creatures—cannot be tripped." ([d20pfsrd, Combat](https://www.d20pfsrd.com/gamemastering/combat/))
   - What the engine did: `extra_legs_penalty` on the trip and overrun rows had no reader, and nothing refused a trip.
   - Player sees: a gray ooze, and a creature hovering a level above its ground, were both knocked prone.
   - Fix: `Engine._untrippable` refuses a trip against a `type.ooze` or an airborne creature, with the reason named. A monster's trip rider is refused the same way.
   - Severity: medium. Status: **fixed for oozes and fliers**.
   - Not built: legless creatures, and "+2 to the DC ... for each additional leg" on trip and overrun. The bestiary carries no leg count. Size: a `limbs.legs` count per stat block, compiled from the body type, plus one reader.

7. **A feat scoped to a misspelt manoeuvre loaded clean** (`classbuilder.validate_feat_document`)
   - What the engine did: `scope: {"maneuver": "tripp"}` passed validation.
   - Player sees: a homebrew Improved Trip written that way never adds its +2 and never stops the attack of opportunity, because `_scope_holds` compares words.
   - Fix: a scope key must be one of weapon, maneuver or school, and a manoeuvre must be a `MANEUVERS` key.
   - Severity: low. Status: **fixed**.

8. **An item's spell power with no caster level cast at caster level 1** (`Engine._use_power`)
   - Rule: an item's caster level is "never lower than the minimum level needed to cast the needed spell". ([aonprd, Magic Item Creation](https://aonprd.com/Rules.aspx?Name=Magic%20Item%20Creation&Category=Magic%20Items))
   - What the engine did: a power whose caster level was left empty (the bench says "Empty: the item's own") fell back to 1. Potions already floored at 2 × level − 1. Every shipped property writes its CL, so only homebrew items reach this.
   - Player sees: a homebrew fireball ring rolled 1d6.
   - Fix: the same floor the potion path uses.
   - Severity: low. Status: **fixed**.

## Not built (the engine does not model it; sized)

N1. **Summon monster I–IX and summon nature's ally I–IX bring nothing** (`content/spells/mechanics/part-17.json` and the SNA rows)
   - What the engine does: every one of these spells is prose. It spends the slot and nobody arrives (probed: Summon Monster 1, CL 3, `slots_left` 2 and no new actor). The narrator is then handed "summon one extraplanar creature of your choice" and may invent one.
   - The engine half is ready: the `summon` type, `_bring_in`, sides, initiative, and now the lifetime from fix 2. The bestiary covers the lists, including the `celestial`/`fiendish` prefixes; 7 of 9 SM I names resolve.
   - What is missing:
     - Table 10-1 and the SNA tables as documents: 18 lists, about 250 rows.
     - A `choose_one` of summons per spell, with the 1d3 / 1d4+1 lower-list counts.
     - A creature picker on the Spells tab. Today `choose` exists only as a cast param, and the UI never sends it.
     - The celestial/fiendish template by the caster's alignment. **Owner call:** the app tracks no alignment, the same gap the smite ruling met.
   - Size: large (a content lane plus a small UI piece). Severity: high.

N2. **Metamagic does not exist** (no reader anywhere; `rules/leveling.py:697` offers metamagic feats as wizard bonus feats)
   - What the engine does: Empower, Maximize, Extend, Still, Silent, Quicken, Enlarge, Widen, Heighten and the rest can be taken and do nothing. There is no slot adjustment and no metamagic param on `cast`. There is also no full-round casting time for a spontaneous caster's metamagic spell.
   - Size: large.
     - A player-written `metamagic` list on the cast, which the model never writes.
     - `casting.cast_source` paying the adjusted slot.
     - `casting_plan` multiplying the dice (Empower ×1.5 on variable numbers, Maximize the maximum) and the duration (Extend).
     - The spontaneous caster's full-round action.
     - A picker on the Spells tab.
   - Severity: medium. A feat pick is wasted, but nothing is wrong at the table.

N3. **Wands, staffs and scrolls are not usable items**
   - What the engine does not model:
     - There are no charge pools: no 50 wand charges, no 10 staff charges and no staff recharge.
     - There is no spell-trigger or spell-completion activation, and no class-list requirement.
     - Use Magic Device is not used for items. The DC 20 wand check, DC 20 + CL scroll check, emulating a class and the natural 1 lockout are all missing.
     - There is no scroll caster level check (DC = scroll CL + 1) and no mishap. Scrolls exist only to copy spells into a book.
   - What does exist: per-day and once-ever power counts (`_uses_per_day`, `Actor.reset_item_uses`) and spell storing weapons.
   - Size: large. Severity: medium, since nothing in the shipped catalogue sells a wand yet.

N4. **Sanctuary, lesser globe and globe of invulnerability are prose**
   - What the engine does: no attacker rolls a Will save against sanctuary, and the spell does not end when the warded creature attacks. No spell of 3rd (or 4th) level or lower is stopped at a globe.
   - Size:
     - Sanctuary is medium: a ward with an `attacker_save` trigger asked at `_op_attack`/`_op_cast` commit, ended by the bearer's own attack. The invisibility spells' `ends_when` already carries the second half.
     - The globes are medium: a manifestation whose area strikes targets inside from a cast below the level threshold, beside the SR step in `_op_cast`.
   - Severity: medium.

N5. **Protection from evil/good/chaos/law gives nothing**
   - What the engine does: the +2 deflection AC and +2 resistance on saves are `situational_mod`, which is `engine=False`. The mind-control immunity is a sentence that matches no condition. The `permission.ward_mind_control` and `permission.ward_summoned_contact` tags have no reader.
   - **Owner call:** the app tracks no alignment, and the existing ruling (smite, holy) answers "any foe" until it does. Extending that ruling here would give +2 against everyone, which the book does not say. I left it for the owner.
   - Size: medium. It needs a `when: {"attacker": {"alignment": ...}}` term read by `ac_modifiers(attacker=)` and the save path, and `_ac_grant` taught to apply a term with a `when`.

N6. **Total concealment from fog or darkness does not stop attacks of opportunity or targeting** (`rules/reactions.py:689`, `Engine` target gates)
   - What the engine does: only Stealth and invisibility block these, through `awareness.sees`. A creature in 50% fog or darkness still provokes and can still be named as a spell's target.
   - Size: small to medium. `Actor.concealment(attacker, ...)` already returns 50 for these cases; the reaction and target gates would ask it.
   - Severity: medium.

N7. **Entropic shield, blurred movement and mirror image are prose.** Entropic shield needs a ranged-only scope on the `concealment` type, which is small. Mirror image needs a decoy pool, which is medium.

N8. **The extras on the Greater manoeuvre feats are missing** (`content/feats/mechanics/core.json`)
   - Every Greater feat carries only its +2s. Missing:
     - Greater Trip's attack of opportunity when the target falls.
     - Greater Bull Rush and Greater Overrun's attacks of opportunity for allies.
     - Greater Disarm's 15 ft throw.
     - Greater Grapple's move-action maintain.
     - Greater Sunder's excess damage carried to the wielder.
     - The APG four.
   - Size: medium, roughly one applicator each in `_MANEUVER_OUTCOMES`.

N9. **Overrun cannot be avoided.** Rule: "it can choose to avoid you, allowing you to pass through its square". Every target resists here.
   - **Owner call:** whether an NPC ever chooses to step aside, and how; the book leaves it to the defender. Small once ruled.

N10. **Grappling without two free hands is not penalised.** Rule: "Humanoid creatures without two free hands attempting to grapple a foe take a –4 penalty".
   - What the engine does: the row's `needs_two_hands` is read only by the sheet's card. The comment at `Engine._resolve_maneuver` ("so is grappling without two hands") claims a penalty that nothing applies.
   - Not built: neither PCs nor thugs carry a `type.humanoid` tag (probed), so "humanoid" cannot be asked. Size: small once the type tag is on every PC and humanoid NPC.

N11. **Spell storing releases on the first wound, always.** The book says "if the wielder desires" (`Engine._release_stored`, which admits this in its own comment). The ring of spell storing is not modelled. Small; it needs a player choice on the blow.

N12. **The per-day item counts reset at the calendar day, not 24 hours after use.** This is a common house reading. Logged, not changed.

N13. **Legs** (see fix 6).

## Checked and right (no change)

- Combat manoeuvres:
  - CMB/CMD formula, size table, flat-footed losing Dex and dodge, penalties to AC applying to CMD.
  - A natural 20/1 on the check, through `dice.d20_succeeds`.
  - The attack of opportunity before the manoeuvre, with its damage as a penalty on the check.
  - Each Improved feat's +2/+2 and no AoO.
  - Size limits: bull rush, overrun, trip, reposition and drag only.
  - Every manoeuvre's own result (docs/maneuver-outcomes.md).
- Concealment:
  - The miss chance is rolled only after a hit, on weapons, touch spells, rays and splash weapons.
  - The best source wins, not the sum.
  - Dim light 20% and darkness 50% unless darkvision reaches; fog 20% within 5 ft and 50% beyond.
  - See invisibility ignores invisibility's 50%.
  - Blind-Fight's reroll in melee.
  - Sneak attack refused against concealment.
- Item powers:
  - The item DC is 10 + level + level // 2 (the minimum ability modifier), from the lowest list.
  - Spell storing's limits: targeted, 3rd level or lower, the storing caster's CL and DC.
- Effect validation: unknown types, missing fields, choice fields outside their list, unparsable dice, unknown formula variables and a trigger with no window are all refused with the fix named.

## Claims the critic pass reversed

- **"Grapple maintain +5 should be untyped."** Wrong. The CRB says "a +5 circumstance bonus on grapple checks made against the same target in subsequent rounds". The engine is right.
- **"Wands provoke attacks of opportunity."** Wrong. Using Items: spell trigger "does not provoke attacks of opportunity". Only spell completion (scrolls) does, "exactly as casting a spell does". The engine's never-provokes answer for command-word and use-activated powers is right.
- **"Item powers should cost a standard action and don't."** True, but it is not a defect of item powers. Only a drink marks `Scene.standard_spent` today. Attacks and casts are not counted either, which is the open turn-budget work (steps 3–5 in docs/turn-budget-and-fixtures-plan.md).
