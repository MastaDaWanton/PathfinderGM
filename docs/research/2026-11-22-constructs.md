# Constructs at the enchanting circle: sources and calls (lane impl3/constructs, 2026-11-22)

The owner's ruling (2026-11-22): "Remove item creation feats they are unnecessary, instead
build the magic items like wands and scrolls and constructs into the enchanting world
class." This note gives the sources for `content/rules/constructs.json` and `rules/constructs.py`,
and lists every call I made that the owner has not ruled on.

A research pass read the pages through a summarising fetcher. Any number that matters should
be checked against the page.

## The book (primary)

- **Craft Construct** (Bestiary, monster feats):
  https://legacy.aonprd.com/bestiary/monsterFeats.html
  - Prerequisites: CL 5th, Craft Magic Arms and Armor, Craft Wondrous Item.
  - Materials cost half the base price plus the full cost of the body.
  - Animating takes 1 day per 1,000 gp of price.
- **Building and Modifying Constructs** (Ultimate Magic):
  https://legacy.aonprd.com/ultimatemagic/magic/buildingAndModifyingConstructs.html
  - The check is DC 5 + the construct's CL, +5 for each missing requirement.
  - The feat and minimum-CL requirements can never be skipped.
  - The construction line's "Skill" is the creation check itself, not a body-only check.
  - Pricing a new construct: CR² × 500 gp. Animated objects price by CR this way, so a
    Medium (CR 3) one costs 4,500 gp.
  - Repair: 100 gp per HD, a check at the craft DC − 5, and 1d6 hp per HD restored.
- **Construct lines**, one page each:
  - Golem pages: https://legacy.aonprd.com/bestiary/golem.html, bestiary2/golem.html,
    bestiary3/golem.html, bestiary4/golem.html
  - Homunculus: https://legacy.aonprd.com/bestiary/homunculus.html
  - Crystal, Lead, Gold and Obsidian golems: aonprd.com MonsterDisplay pages (the URLs are in
    the rows).
- **The printed DCs are not always 5 + CL.**
  - Wood: CL 7, printed DC 17.
  - Glass: CL 10, printed DC 17.
  - Mithral: CL 18, printed DC 25.
  - So the DC is stored as data and never derived. Forum discussion of the wood case:
    https://paizo.com/threads/rzs2pdvl (forum source).
- **Commanding golems** (golem.html):
  - They are mindless and "do nothing without orders from their creators".
  - They "follow instructions explicitly" and are incapable of complex strategy.
  - Left uncommanded, a golem follows its last instruction, and returns an attack if attacked.
  - The creator must be within 60 ft, and the golem must be able to see and hear him.
- **Homunculus:**
  - Int 10, so it is not mindless.
  - Languages: "Common (cannot speak); telepathic link".
- **Construct type** (https://legacy.aonprd.com/bestiary/creatureTypes.html): "cannot heal
  damage on its own".
- **Make whole** (https://legacy.aonprd.com/coreRulebook/spells/makeWhole.html): 1d6 per
  caster level on a construct, at most 5d6.
- **Mending** does not affect constructs.

## Prior art: what other games did, and abandoned

- **PF2 minion trait** (https://2e.aonprd.com/Traits.aspx?ID=109):
  - A minion acts only when commanded.
  - Uncommanded, it only defends itself or escapes obvious harm.
  - A mindless minion left without orders stops acting after about a minute.
- **The PF2 Inventor's construct** (https://2e.aonprd.com/Innovations.aspx?ID=2) follows the
  same command rule.
- **PF2 dropped open-ended construct crafting.** A Paizo forum answer points to a ritual
  plus GM permission instead (forum source: https://paizo.com/threads/rzs42u7f).
- **5e Steel Defender** (secondary sources): it takes the Dodge action unless commanded.
- **Arcanum** (forum and wiki sources, which disagree with each other): built mechanical
  followers sat outside the follower cap, so players built as many as they liked.
- **The common lesson:** fix the uncommanded construct's behaviour in the rules (do nothing,
  defend itself), and count it like any other ally. The golem text already says the first.
  Here, the uncommanded construct's turn is told the golem's rule. The second is the encounter
  budget's existing companion count.
- **Could not source:**
  - Owlcat's Kingmaker and Wrath of the Righteous construct crafting.
  - Foundry PF1 construct crafting.
  - The designer reasoning behind the Steel Defender.

## What was built

The **Animate** method at the circle (Enchanter 1; `content/world-classes/enchanter.json`).

- **The check.** The DC is the line's printed DC, plus +5 per spell group neither known nor
  carried in a potion or scroll. A carried potion or scroll is used up. Add +5 if the
  Enchanter level is below the line's CL.
- **The cost.** It spends the body and the essences, plain motes first.
- **The time.** The work goes In progress for 8 hours per 1,000 gp of price, the circle's
  binding clock.
- **Collect.** The construct rises from the bestiary block and joins the party:
  - it holds `bond.owned-by-you` (source `made:<ref>`), `bond.travels-with-you` (company
    door) and devoted;
  - the game's quality adds ±1 hp per HD per step from Sound, through one `hp_max` modifier
    on its bond effect;
  - its turn and answers are told it is mindless and mute;
  - the answer call has no `say` op for a mute construct.
- **Healing and repair:**
  - Constructs no longer heal from rest. Before the fix, `Actor.rest` healed every actor, so
    a construct at 3 hp rose to 4, and a broken one at −5 rose to 1.
  - The repair DC now reads the construction line. A homunculus repairs at DC 7, not the
    house default of 15.
  - Make whole now scales: it rolled 1d6 at every caster level before.

## Owner calls (my readings, for the owner to confirm or overrule)

1. **The level gate is the stat block's CR, rounded up.** Homunculus 1, animated object 3,
   flesh golem 7, iron golem 13. The book's gate is "CL 5 and the line's CL". The owner
   replaced caster level with Enchanter level everywhere, and the CR keeps golems late.
2. **The DC follows the owner's Bind rule.** Below the CL is +5, never a refusal, so the
   book's "minimum CL can never be skipped" is not kept. A level-1 enchanter making a
   homunculus without the three spells faces DC 32.
3. **The check is the Enchanter check, not the line's named Craft skill.** The circle uses it
   for every item.
4. **Quality sets hit points.** House numbers: Crude −1/HD, Fine +1, Superior +2, Flawless
   +3. The book has no construct quality.
5. **A miss costs only the time.** This is the owner's Bind rule. The book wastes the
   materials, and nothing cursed is made on a miss by 5 or more.
6. **Bodies:**
   - A homunculus needs one mandrake root (the herbalist's ingredient). Clay, ash, spring
     water and blood are not tracked.
   - An animated object is a carried suit of armour made by the forge or the leatherworker.
     Only the Medium block exists in the bestiary, so there is no Tiny or Small animated
     object yet.
   - Golems' bodies are bought in coin at the book's body price, because no bench builds a
     5,000 lb iron body.
7. **Encounter budget:** a made construct counts at its CR, as a claimed construct already
   does (`encounter_budget.companion_level`). The book's Step 1 counts only PCs. The owner's
   2026-11-13 ruling counts companions, and a construct that fights is one.
8. **Not modelled:**
   - The creator's 60 ft command range.
   - The flesh and clay golems' berserk chance.
   - The homunculus' telepathic sharing and the 2d10 damage to its master when it is
     destroyed.
   - Handing control to someone else.
