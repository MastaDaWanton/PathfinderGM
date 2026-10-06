# Enchanting revamp: the owner's answers

Asked by the lead from `docs/enchanting-prior-art.md` and the inventory (2026-10-04, the enchanter
on master e028885). Nothing is designed yet; these rulings bind the plan.

## Round 1 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Who can enchant | **The Enchanter class, book-flavoured.** Anyone with the Enchanter world class enchants; its level stands in for caster level. A known spell, or a potion/scroll holding it (the book's "another magic item or spellcaster" rule), is a prerequisite; each missing one is +5 DC, never a refusal. |
| How magic sits on a forged item | **A layer on top, capacity from quality.** The forged item keeps its pieces, materials and build; enchantments (+N and properties) are added on top within the book's +10. A Superior (masterwork) piece holds the book limit; Flawless and +N pieces hold a little more (Ultima Online's exceptional items). |
| Cost | **Essences are the cost.** Magic comes from essences found, harvested or bought (priced to follow the book), plus time scaled by power. |
| Failure | **Book curses, hidden.** Miss by 5+ and the item works but carries a hidden curse from the book's table, discovered by identifying well (beat the DC by 10) or the hard way. Materials are not lost. |

## Round 2 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Discovery | **Disenchant + identify + herb routes.** Break down a magic item to learn its property; identify graded by the roll (beat by 10 to see curses); study, teachers, libraries, manuals. |
| Minigames | **Order, matching and timed windows.** Lay components in order, match essence to vessel, bind at timed windows (e.g. planetary hours computed from the game clock). No freehand drawing. |
| Engine | **Every book property works.** A magic-weapon property vocabulary (flaming, frost, shock, keen, ghost touch, bane vs a chosen foe, holy, speed, defending ...), readers for every effect type, and "counts as magic" for DR, through the one applicator with tells. |
| Levels | **Same as the others.** L1 common/uncommon, L2 rare/exotic, L3 legendary, then endless perks: potency, quality, yield, and an enchanting perk such as capacity (+1 to what an item holds, within +10). |

## Round 3 (2026-10-05)

| Question | Owner's answer |
|---|---|
| Products | **Arms, armour, wondrous items, rings** on one bench, on vessels from the forge and the leatherworker. Wands, staves and scrolls wait for a later pass (charges and spell use). |
| Two modes | **One craft, essences feed both.** A catalogue item is a known recipe of essences and a vessel; free-form binding makes your own. Same bench, rules and curses. |
| Bench | **Its own bench, built from the shared parts** (the bench core), with a 3D stage: the item on a circle of chalk and inks, lit by candles and the essence's glow. |
| Old saves | **Convert.** Levels above 3 become endless levels with perks picked on first load; old enchanted items keep their +N and specs, re-derived onto the new layer where possible, the old record kept beside them for one version. |

## Round 4: the plan's open points (2026-10-05)

These settle `docs/enchanting-revamp-plan.md` §22. Where an answer differs from what the plan
took, **the answer wins** and the plan section named must be built to it.

| Open point | Owner's answer |
|---|---|
| 1. Capacity (§6.3) | **Uncapped, half the Enchanter level, quality adds on top.** An item holds floor(Enchanter level / 2) worth of enhancement-equivalent bonus, with no +10 ceiling (Enchanter 20 = +10, Enchanter 30 = +15). The smith's quality adds a little more room on top (proposed: +1 per quality step above Superior, and the Capacity perk +1 each). *Replaces the plan's Superior +8 / Flawless +9 / +10 cap.* |
| 2. Curse visibility (§11.1) | **Know it is flawed, not which curse.** The d20 and margin are shown, the verdict says FLAWED; which curse stays hidden until identified. (As taken.) |
| 3. Curse rows (§11.2) | **Drop all of them**: change of gender, race and alignment; polymorph; incurable disease; compulsion to attack. The d% is re-scaled over the rest. (As taken.) |
| 4. Caster level (§4.2) | **+5 DC per missing requirement, never a refusal.** (As taken.) |
| 5. Countdowns (§6.8, §15) | **Runs on the calendar, and no limit to how many things are in progress at once**, in every craft. They sit in the In progress section/sidebar the other crafts use, with countdowns on game time. *Replaces "one binding in progress at a time".* |
| 6. Unbind (§13) | **The item stays, a quarter of the motes come back.** (As taken.) |
| 7. Alignment | Waived: the app tracks no alignment yet (owner ruling of the same day for smite and channel energy). Holy and its kin neither check the maker's alignment nor give the wielder a negative level until alignment exists. |
| 8. Bane and DR (§9) | **Yes**: bane's +2 against its foe counts toward the +3/+4/+5 DR thresholds. (As taken.) |
| 9. Numbers | **Use the proposed numbers, tune in play**: 1 mote = 100 gp; cold iron +2,000 gp = 20 motes; affinity −1 DC, max −2; favourable-time windows ×1.5; residue a quarter; attuned vessels hold a day; perk sizes as proposed. |
| 10. Planetary hours (§17) | **Not Earth's planets: "this is not earth", and named planets would not be world-agnostic.** Replaced by **phases of the day only**: dawn, morning, noon, dusk, night and midnight each favour some essence families (e.g. fire at noon, the dead at midnight, frost before dawn). Needs nothing from the world. `rules/sky.py` becomes day phases from the game clock; each essence family names its phase (`phase`, not `planet`) in data; the bench says "Noon, 42 minutes left" / "Midnight in 3 hours 10 minutes" with **Wait for it**. |

## Round 5: lane G's calls (2026-10-05)

| Question | Owner's answer |
|---|---|
| Day phases | **Add "afternoon"** (13:00–17:00), so no hour is called noon that the narrator's hour check would flag. Seven phases: dawn, morning, noon, afternoon, dusk, night, midnight. |
| Stopping a steep | **No: a steep must finish.** It is collected when ready; there is no Stop for jars. |

## Round 6: lane A's calls (2026-10-05)

| Question | Owner's answer |
|---|---|
| Holy, unholy, axiomatic, anarchic | **Anyone, like smite.** With no alignment tracking, the +2d6 lands on any foe for now, and the property's text says it will narrow to the right alignment once alignment is added. Lane C's reader for `when.target.alignment` answers "yes" for every target until then. |
| Skill competence items | **No cap.** Caster level by bonus as proposed; no +10 cap; the price formula (bonus² × 100 gp) keeps big bonuses expensive. |

## Round 7: lane B's calls (2026-10-05)

| Question | Owner's answer |
|---|---|
| Enchanter 1 | **Minimum +1.** Capacity is half the Enchanter level, but never less than +1 for an Enchanter of any level. |
| Rings and wondrous items | **Keep the price reading**: a ring or wondrous power takes the plus a weapon would carry at its price, ceil(sqrt(gp / 2000)); one budget for every item. |
