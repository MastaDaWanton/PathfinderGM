# Craft and Profession: what they do here, and how to make them worth a rank

The owner, 2026-10-06: *"the craft skill and the profession skill seem pretty useless what
can we do to make them more viable"*. This paper measures the current state, sets out what
the tabletop and the CRPGs did about the same complaint (and what they abandoned), and
offers five options with a recommendation. The skill hover shipped the same day
(`content/rules/skills-explained.json`) told the player the truth below, card by card.

**The owner chose A, B and C on 2026-10-07 (not D, not E), and they are built** on
`feature/craft-profession`: see §5 for what each does, the numbers' sources and what is
left. Sections 1 to 4 are the paper as written, before the build.

## 1. What the code does today (measured 2026-10-06, master 067e516)

A grep of `rules/`, `gm/`, `play/` and `content/` for every read of the two skills, with
reads of the *skill modifier* told apart from the word "craft" used as a label.

**One id each, no trade.** `rules/tables.py` carries `"craft": ("int", False, False)` and
`"profession": ("wis", True, False)` (Profession is trained only). Ranks can be placed only
on those ids (`rules/creation.py` "is not a skill.", `rules/leveling.py` `rank_problems`).
`content/rules/repairs.json` is the one place that says so in words: the sheet carries one
Craft, so Craft (clockwork), Craft (weapons) and the rest are all it.

**Where Craft ranks change anything: one place.**

| Use | How | Where |
|---|---|---|
| Mending a construct (house rule) | better of Craft and Knowledge (engineering), DC = construct's crafting DC − 5, 10 minutes, 1d6 per HD | `content/rules/repairs.json`, `rules/repair.py` `best_skill`, `rules/engine.py` `_op_repair` |
| The GM's ordinary `check` | any skill, d20 + bonus against a band DC | `rules/engine.py` `_op_check` |

**Where Profession ranks change anything: two places.**

| Use | How | Where |
|---|---|---|
| Studying a herb | better of Knowledge (nature) and Profession (any trade), DC 10 + 5 per rarity, a property per 5 of margin | `content/rules/herb-lore.json`, `rules/herbknowledge.py` `study_skill` |
| Ramming a ship | Profession against the target's AC; no ranks, no ram ("is no sailor") | `rules/engine.py` sea op |
| The GM's ordinary `check` | as above, refused untrained | `rules/engine.py` `_op_check` |

**What does NOT read them:**

- **None of the five world-class benches.** Herbalist, Blacksmith, Alchemist,
  Leatherworker and Enchanter all roll d20 + track level + ½ character level + an ability
  modifier (`check_terms` in `rules/crafting.py`, `blacksmith.py`, `alchemist.py`,
  `leatherworker.py`, `enchanter.py`; `magicitem.py` reuses the enchanter's). Their comments
  cite Craft only to justify choosing Intelligence. The excursions (mining, skinning,
  buying) use the same formula (`play/craft_views.py`). The engine's `craft` op rolls
  nothing: it records a world-class session and awards mastery.
- **No item-making by the week** (the CRB's check × DC in silver), no mending of ordinary
  gear, no Appraise-like use, no identifying items of your trade. Identify is the Enchanter
  check or Spellcraft; the forge's assay is the Blacksmith formula.
- **No earning.** There is no downtime, wage or day-job code. "Downtime" appears once, as a
  price-ratio citation in `rules/pricing.py`. Paid work is a narrative errand card
  (`rules/cards.py` `MEANS_KEYS`).
- **No prices.** `rules/pricing.py` and `rules/market.py` price from tables; haggling is
  an alias to Diplomacy.
- **The means gate** (`gm/means.py`) has nothing specific to either: a skill use is
  `ordinary`, which anybody may attempt.

So a Craft rank buys one house-rule repair of constructs, and a Profession rank buys herb
study (which Knowledge (nature) already covers) and ramming at sea. For a skill that costs
the same rank as Perception, that is the complaint, confirmed.

**Three defects found on the way (not fixed here; each is a separate change):**

1. **Feat prerequisites naming a trade can never be met.** `rules/feats.py` reads
   `actor.ranks.get("craft (alchemy)")`, but ranks only ever land on `craft`. 9 feats in
   `content/feats/feats.json` require a `craft (...)` and 3 a `profession (...)`.
2. **Printed NPC trades are unreachable.** `content/bestiary/creatures.json` prints 854
   `craft (...)` and 673 `profession (...)` totals. `Actor.skill_modifiers("profession")`
   looks the bare id up in `flat_skills` (`rules/sheet.py`, exact key), misses
   "profession (sailor)", and refuses the roll as untrained. A printed sailor cannot ram.
   (Reported by the code survey from those two lines and the loader's lower-casing at
   `sheet.py` `from_dict`; I did not replay a ship fight to watch it.)
3. **The GM cannot ask for a trade.** A `check` naming "craft (alchemy)" fails validation
   ("is not a Pathfinder 1e skill", `rules/intents.py`), and nothing folds a subtype into
   the base id.

## 2. Prior art

Sources were read by a research pass and checked by a second, critic pass; confidence is
marked where it is less than a primary rules page.

**The book (CRB, via Archives of Nethys).** Craft: materials cost ⅓ of the price; each week
check × DC in silver accrues until it reaches the price; fail by 5 and half the materials
are lost; masterwork is a separate DC 20 component; repairs use the creation DC at ⅕ of the
price; and Craft earns half the check in gold a week, the same rate as Profession.
Profession: half the check in gp a week (no retry that week), plus the trade's know-how at
DC 10, 15 and up. Craft (armor/weapons/jewelry) can stand in for Spellcraft when making
magic items, and Master Craftsman lets 5 Craft or Profession ranks count as caster level.
https://www.aonprd.com/Skills.aspx?ItemName=Craft,
https://www.aonprd.com/Skills.aspx?ItemName=Profession,
https://www.d20pfsrd.com/magic-items/magic-item-creation/

**Ultimate Combat, vehicles.** A sailing ship is driven with Profession (sailor) or
Knowledge (nature); an alchemical vehicle with Craft (alchemy). Official precedent for a
trade replacing a check in play. https://aonprd.com/Rules.aspx?ID=1106

**Ultimate Campaign, downtime.** Skilled work earns check ÷ 10 gp a day, or capital
(Goods, Influence, Labor, Magic); Craft and Profession qualify for all four. Rooms such as
the Forge, Alchemy Lab and Artisan's Workshop roll their own daily earnings and count as
masterwork tools. Its bargaining rules use Appraise, Sense Motive, Bluff and Diplomacy;
**Profession (merchant) appears nowhere in them**, so "merchant haggles" is a house rule.
https://www.aonprd.com/Rules.aspx?Name=Downtime%20Activities&Category=Downtime,
https://aonprd.com/Rules.aspx?ID=1341 (capital table read through a summary: medium
confidence).

**Pathfinder Unchained, Background Skills.** Two free ranks per level for background
skills only: Appraise, Artistry, Craft, Handle Animal, Knowledge (engineering, geography,
history, nobility), Linguistics, Lore, Perform, Profession, Sleight of Hand. The stated
reason is that skills do not give characters equal benefit, so nobody should have to
trade "the knowledge to understand the world and the ability to survive in it"
(Unchained, via https://www.aonprd.com/Rules.aspx?Name=Background%20Skills&Category=Skills%20in%20Unchained).
I could not find Paizo saying in so many words that players never spent ranks on these
skills; that is the forums' reading, not a sourced quote.

**Unchained, Expanded Craft and Profession.** Everyday uses beyond money: identify a maker's
mark or the culture an item came from, spot masterwork on sight (DC 15), smelt ore, skin and
tan, mend a sail; a sailor navigates (DC 20), a herbalist identifies herbs (10/15), a
merchant knows where a good sells higher (15), a soldier estimates a force (15), a miner
identifies metals. https://www.aonprd.com/Rules.aspx?ID=1742,
https://www.aonprd.com/Rules.aspx?ID=1744

**Unchained, Consolidated Skills.** Thirty-five skills become twelve, and Craft, Profession
and Appraise are simply dropped, with a pointer back to background skills to restore them.
Paizo's own consolidation could not absorb these two.
https://www.aonprd.com/Rules.aspx?Name=Consolidated%20Skills&Category=Skills%20in%20Unchained

**Pathfinder Society (1e), Day Job.** One Craft, Perform or Profession roll after each
scenario for a small payout from a table; mundane crafting itself was banned. Players
judged it worth ranks only "with spare points". (Forum reproductions of the Guide; medium
to low confidence.) https://paizo.com/threads/rzs2pk2o

**PF2e and PFS2.** Earn Income pays by **task level and proficiency**, not by the raw d20
total; Profession became Lore, granted free by backgrounds; Crafting stayed a full skill
with Repair and Identify Alchemy. https://2e.aonprd.com/Skills.aspx?ID=21&General=true,
https://2e.aonprd.com/Skills.aspx?ID=41. No Paizo statement explaining *why* Profession
became Lore was found.

**CRPGs.** Pathfinder: Kingmaker and Wrath of the Righteous have no Craft, Profession or
Appraise at all (WotR list confirmed; Kingmaker from snippets); Kingmaker's crafting goes
through kingdom artisans. NWN1/2's Appraise silently shifted shop prices by an opposed roll
players found opaque. BG3 crafting needs no skill and its tool proficiencies were left out
(secondary sources). 5e's tools (Xanathar's) give each tool concrete uses: smith's tools
repair metal objects, a herbalism kit finds and identifies plants, and a skill plus a tool
together roll with advantage. https://www.dndbeyond.com/sources/dnd/basic-rules-2014/equipment#Tools

**What was abandoned, and why it matters here.**

- **The pure payout roll** (PFS1 Day Job): kept the skill alive on paper, judged not
  worth a rank. A wage alone will not fix "useless".
- **The raw d20-total-to-gold formula**: PF2e replaced it with a level-and-proficiency
  table, so stacked bonuses stop inflating income.
- **Folding the skills away** (Unchained Consolidated, Owlcat): it worked only by
  deleting them, and Paizo had to bolt them back on.
- **Opaque price rolls** (NWN Appraise): a number the player cannot see moving is not a
  reward.

Every tradition that kept these skills worthwhile did at least one of three things: made
the ranks free, gave the skill uses in play, or tied its income to level and training.

## 3. Options

### A. Craft ranks count at the benches

Add one term to every world-class bench check: **Craft ranks ÷ 2** (rounded down), itemised
like the others ("Craft 4 ranks +2"). Herbalism takes the better of Craft and Profession
ranks, after the book's own herbalist route (Profession (herbalist) can prepare herbs) and
the herb study that already accepts Profession.

- **What it takes:** a term in five `check_terms` functions and the excursion bonus; the
  bench dice popups already list terms. Tests that name the measurement (today 0 of 5
  benches read a Craft rank).
- **World classes:** they keep their own levels; the track level is earned by doing, ranks
  by choosing, and a character who does both is the better smith. Half ranks keep it below
  the track (a level-10 smith with 10 ranks gains +5, against track and half level).
- **Means gate:** untouched; the benches are their own screens.
- **Cost:** the bench DCs were tuned without it; +5 at level 10 moves every chance. Retune
  or accept, the owner's call.
- **Single Craft:** with one id, a rank in "Craft" helps every bench. Defensible while
  there is one Craft; option D is where trades would split.

### B. Craft and Profession get the everyday uses (Unchained Expanded)

Teach the engine a short list of uses, each a closed rule the GM cites rather than a DC it
invents: Craft spots masterwork (DC 15) and tells a forged item's maker and origin; Craft
mends ordinary broken gear at the creation DC for ⅕ of the price (the `item_damage` op
already breaks things, and `rules/repair.py` already has the shape for constructs);
Profession answers a trade question (DC 10/15); Profession (herbalist) identifies a herb at
DC 10/15 as a cheaper study.

- **What it takes:** rows in a rule document like `repairs.json`, one op or two (`mend`,
  `inspect`), the declaration-verb entries, and a card line each.
- **World classes:** Craft's mend and identify sit beside the forge's assay rather than
  replacing it; masterwork spotting reads the item's own `masterwork` flag.
- **Means gate:** ordinary deeds, so nothing changes; the rule supplies the DC.

### C. Profession earns: a day's work

A `work` deed: the character spends a day (or a week) at their trade and is paid. Pay from
a **table by level and Profession ranks**, PF2e-shaped, not half the d20 total; a natural
roll decides poor, fair or good pay. Craft and Perform qualify too, as in the book.

- **What it takes:** one op that advances the clock by the day, a pay table in content,
  and the player's route to it (a "Work" action where there is an employer, or the
  declaration "I work at the docks for a week").
- **World classes:** a smith with a forge already earns by selling what she makes; the
  work deed is for the rest. It must never pay more per day than the benches, or it
  becomes the only thing worth doing.
- **Interactions:** the day passes for hunger, thirst and sleep clocks (`rules/survival.py`),
  the world agent ticks, and the employer's regard can move a step for good work, giving
  Profession a social face.
- **Means gate:** an ordinary deed.
- **Warning from the record:** on its own this is PFS1's Day Job, which players judged not
  worth a rank. Ship it with A or B, not instead of them.

### D. Name the trade: Craft (x) and Profession (x)

Ranks keyed by trade, picked when the rank is placed ("Profession: sailor"). Each trade
lights its own scenes: sailor at sea (ramming today; navigation and piloting from Ultimate
Combat), herbalist at the herbarium, miner on a prospecting run, soldier reading a force,
merchant knowing where a good sells higher (Unchained). Bench terms from option A then read
the matching Craft (weapons/armor for the forge, alchemy for the alchemist, leather for the
leatherworker).

- **What it takes:** the largest change. Ranks keyed `craft (weapons)`; the forge and the
  level-up picker ask which trade; `normalise_skill` folds a subtype onto its base for every
  generic read; the GM may name a trade in a check. It also **fixes all three defects** in
  section 1 (feat prerequisites, 1,527 printed NPC trade totals, the GM's trade checks).
- **World Bible:** NPC occupations (`content/people/occupations.json`, `rules/roster.py`)
  already carry trades; a world's people could arrive with their trades as Profession
  totals. Per the standing instruction that fixes are world-agnostic, the export format
  would name the trade per NPC.
- **Means gate:** a trade the sheet holds becomes something the gate can see ("as a sailor,
  I read the swell"), the way it now reads spells and feats.

### E. House rule: Unchained Background Skills

A toggle on the Rulesets bench: two free ranks a level, for background skills only
(Appraise, Craft, Handle Animal, Knowledge (engineering, geography, history, nobility),
Linguistics, Perform, Profession, Sleight of Hand). Off by default.

- **What it takes:** a second rank budget in `leveling.skill_ranks` and the forge, and the
  picker showing which ranks are which.
- **The catch, measured above:** of those eleven skills, seven are read by nothing in play
  today (Appraise, Handle Animal, Knowledge (geography, history, nobility), Linguistics,
  Perform), and Sleight of Hand only by the player's pickpocket roll. Free ranks in skills that do
  nothing are still nothing. This removes the cost; it does not add the point.

## 4. Recommendation

**A, then C, with B's mend-and-spot pair alongside; D when the defects are fixed; E as a
toggle only once enough background skills do something.**

- **A first** because it is small, it puts a Craft rank on the screen the player already
  uses most, and the benches' itemised terms make the payoff visible at every roll (the
  opposite of NWN's hidden Appraise).
- **C next**, with pay by level and training rather than by the raw d20 (PF2e's correction
  of PF1), so Profession has a loop of its own. Alone it repeats the Day Job; with A it
  is the half of the pair that serves the character who does not craft.
- **B's two Craft uses** (spot masterwork, mend ordinary gear) are cheap once A lands and
  give Craft a use away from a bench.
- **D is the right end state** and the only one that fixes the three defects, but it
  changes how ranks are keyed everywhere. The defects themselves (feat prerequisites,
  printed NPC trades, the GM's trade checks) can be fixed before it by folding a
  subtype onto its base id at read time, which costs little and keeps D open.
- **E** waits: it is Paizo's answer to "the ranks cost too much", and the owner's
  complaint is "they do too little". Turn it on only after A to D give the background
  skills something to do.

## 5. What was built (2026-10-07, branch `feature/craft-profession`)

The owner chose **A, B and C**; not D (named trades) and not E (background skills). The
rules live in `content/rules/trade-uses.json` (each row cites its source and marks every
HOUSE departure) and `rules/tradecraft.py`; the engine's five new ops are in
`rules/engine.py` beside `_op_item_damage`.

**A. Craft at the benches.** `tradecraft.bench_terms(actor, bench)` returns one itemised
term, half the ranks rounded down, built as a `Modifier` and passed through `dice.stack`:
"Craft ranks ½ (3)" +1. Called from `check_terms` in `rules/crafting.py` (herbalist: the
better of Craft and Profession), `rules/blacksmith.py`, `rules/enchanter.py` (and so
`magicitem.py`, which reuses it) and `rules/leatherworker.py`; the excursions read
`check_bonus`, so they carry it too. No ranks, no term. The alchemy bench being rebuilt on
`build/alchemy` needs one call in its `check_terms`, before the laboratory term:
`from . import tradecraft` and `out += tradecraft.bench_terms(actor, "alchemist")`. The bench
DCs were tuned without it and were not retuned (the paper's "retune or accept").

**B. Everyday uses**, each an op with the player's own die and a tell:

| Op | Skill | The rule | Source |
|---|---|---|---|
| `judge` | Craft | DC 15 masterwork on sight; at 20 (trained) hardness and hit points; the same day's look again says the same | Unchained p.51; CRB Appraise |
| `mend` | Craft | the making DC (CRB table: simple 12, martial 15, exotic 18, armour 10 + AC; masterwork 20), a fifth of the price in materials, an hour a point; fail by 5 and half the materials are ruined; magic and ruined things refused | CRB Craft; CRB Broken |
| `trade_lore` | Profession | basic DC 10, complex 15; a success names the places here where the trade works, from the engine's place list | CRB Profession |
| `haggle` | Profession vs the keeper's Sense Motive | 2% + 1% a point, at most 25%, both ways, for that counter for the day; once a counter a day | Ultimate Campaign, Bargaining (Profession for Bluff is HOUSE) |

`_op_buy`, `_op_sell` and `_sell_goods` read the haggle (`tradecraft.haggled`), and the
trade window shows the moved prices and the result on its Haggle button. The Equipment
tab offers Judge its make on every weapon, suit and shield, and Mend, with a "broken: 2
of 5 hit points" chip, on anything damaged (`views._trade_acts`).

**Object hit points come off the book (2026-10-07).** Until then every steel thing had an
inch of steel from Table 7-13 — 30 hit points — so a broken longsword took 15 to 16 hours
to mend, and a forged adamantine longsword read hardness 29 and 51 hit points (Table
7-13's adamantine plus the material document's own step from steel, counted twice). The
owner: "use the book but only as a base — the materials used when smithing should change
that if they say so." `rules/object_numbers.py` is the one reader: Table 7-12's row
(CRB p.175: one-handed blade 5, light blade 2, heavy steel shield 20, armour its bonus × 5,
...), then the forge build's `hardness` / `hp_per_inch` numbers (or, for a bought
"adamantine longsword", the material document's `book: true` numbers only), then +2
hardness and +10 hit points per +1 (CRB p.174). A broken longsword now mends in 3 hours;
a bought adamantine longsword is hardness 20, 6 hit points (the book's "one-third more");
a +1 longsword hardness 12, 15 hit points. Saves are re-read on load, damage carried by
proportion with whole, broken and ruined kept (`object_numbers.carry_damage`). Pinned by
`tests/test_object_numbers.py`.

**C. A day's paid work** (`work`): PF2e's Earn Income (Player Core p.228, Table 4-2)
in PF1's coin. The task level is the lower of the character's level and the settlement's
(village 1, town 4, city 7: GM Core's "the level of the settlement", at the top of each
band); training is read from ranks at the levels PF2e first allows each rank (trained 1,
expert 3, master 7, legendary 15); the die only picks the column (critical success = the
next task's pay, failure the Failed column, critical failure nothing and the work ends the
first day). Amounts are PF2e's × 5 (`coin_scale`, HOUSE): first set at × 10, anchored on
the untrained wage (PF1 1 sp a day, PF2e's failed task 0 pays 1 cp) and a dagger (PF1 2 gp,
PF2e 2 sp), then halved by the owner on 2026-10-07 (below). No
ranks in either skill: the CRB's untrained 1 sp a day, no roll. Only inside a settlement.
A day is 8 hours charged to the body, then fed, watered and slept, `_march`'s shape.

**Measured against the book, and retuned.** Kesst, Profession +6 with 3 ranks at level 3
in a city: task 3, expert, DC 18, 5 gp a day on a success at × 10 — 35 gp for a week,
where the CRB's half-the-check wage taking 10 is 8 gp a week. Working paid about four
times the PF1 wage at low level because PF2e's table is generous in purchasing power once
converted. The owner, 2026-10-07: "Paid work: halve it." `coin_scale` is 5 now: 2 gp 5 sp
a day on a success, 17 gp 5 sp a week (about twice the PF1 wage). The untrained 1 sp a day
is the CRB's own and is not scaled. Pinned by `tests/test_trade_uses.py`.

**The three defects of §1, fixed by folding a trade onto its base** (`tables.base_skill`):
feat prerequisites (17 feats asked for a trade's ranks; all 18 conditions now read the
base), printed NPC trades (`Actor.printed_skill`: the best printed total under a trade
name; Caulky Tarroon's Profession (sailor) +6 now reaches the helm), and the GM's checks
(`intents.normalise_skill` folds "craft (alchemy)" to Craft).

**Left:** making items by the week from the CRB's Craft rules; a sailor's navigation, a
soldier's reading of a force and the rest of Unchained's per-trade rows (they need D's
named trades); the employer's regard moving with good work; a question of the trade has no
button (it needs the question, so it comes through a spoken turn); World Bible exports
nothing new for any of this (settlement scale was already exported), though a world that
said what a town's trades are (a port raises sailing tasks, GM Core p.53) would sharpen C.
