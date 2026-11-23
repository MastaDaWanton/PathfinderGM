# Spell items lane (round 3, 2026-11-22): sources and owner calls

The design record is `docs/item-creation-feats-study.md`; the owner's ruling of 2026-11-22
("Remove item creation feats they are unnecessary, instead build the magic items like wands
and scrolls and constructs into the enchanting world class") settles its Q1, Q3, Q6, Q10 and
Q14 in favour of the world class and against keeping any feat. This note records what was
read for the build and every call made without the owner.

## Primary sources read for this build

- Scrolls, legacy.aonprd.com/coreRulebook/magicItems/scrolls.html: the three requirements
  ("The spell must be of the correct type (arcane or divine)", "The user must have the
  spell on her class list", "The user must have the requisite ability score"); the caster
  level check "DC = scroll's caster level + 1"; "If she fails, she must make a DC 5 Wisdom
  check to avoid a mishap"; the seven mishaps; the price, 25 gp x spell level x caster
  level. The page does not say whether a failed activation spends the scroll.
- Wands, legacy.aonprd.com/coreRulebook/magicItems/wands.html: spell trigger, 50 charges,
  4th level or lower, 750 gp x spell level x caster level.
- Use Magic Device, legacy.aonprd.com/coreRulebook/skills/useMagicDevice.html: use a
  scroll DC 20 + caster level; use a wand DC 20; emulate an ability score, the result
  minus 15; a natural 1 that fails bars the item for 24 hours; "Failing the roll does not
  expend a charge"; trained only.
- Arcane Magical Writings, legacy.aonprd.com/coreRulebook/magic.html: copying from a
  scroll (an hour's study, Spellcraft DC 15 + level, +2 for a specialist's school, a week
  before another try, the scroll spent only on a success, wizard list only); writing
  costs by spell level and 1 hour a level (a cantrip 30 minutes); deciphering, Spellcraft
  DC 20 + level.

Prior art (Owlcat's WotR keeping only scrolls and potions, NWN's crafted wand blank, PF2e's
once-a-day wand, Foundry PF1's consumable-from-spell) is the study's §2.3; nothing in it
changed for this build.

## What was built (by the study's options)

- **Feats out.** Brew Potion, Scribe Scroll, Craft Wand, Craft Staff, Craft Rod, Craft
  Wondrous Item, Craft Magic Arms and Armor, Forge Ring and Craft Construct leave the
  catalogue (`rules/feats.py` RETIRED). A sheet holding one sheds it on load; a player
  character is owed a free feat pick for each (`Actor.feats_refunded`, `leveling.owed`).
- **Scrolls** (study §3.2 option A without the feat): the circle's Scribe method, Enchanter
  1, a sheet of vellum and an ink, the order minigame, In progress for the book's time.
  Read through the item cast door with the book's spell completion rules or Use Magic
  Device (`Engine._spell_item_gate`).
- **Wands** (§3.3 option A): the circle's Wand method, Enchanter 2, a wand blank, 50
  charges as the layer's use count, spell trigger rules or Use Magic Device.
- **Copying** a scroll into a wizard's spellbook (`spellitems.copy_plan`, `api/spells/copy`).
- **Shops:** 30 classic scrolls and 12 classic wands on the magic counters' draw.

## Owner calls (made by the book, or by the least surprising reading)

1. **The wizard's 1st-level Scribe Scroll** becomes one more wizard bonus feat at 1st level
   (a metamagic feat or Spell Mastery; "an item creation feat" is gone from the wizard's
   bonus list). A wizard made before this keeps their level 1 as it was and gets the
   refund pick instead, which is a general feat, slightly more generous than the bonus.
2. **Rune domain** loses its Scribe Scroll grant and gets nothing in its place; the arcane
   bloodline's bonus feat list loses Scribe Scroll (7 left). Three feats whose only
   prerequisite path ran through a retired feat (Cypher Magic, Create Sanguine Elixir,
   Create Reliquary Arms and Shields) can no longer be qualified for.
3. **Master Craftsman stays** for its +2; its caster-level clause has no feat left to serve.
4. **Which spells a scroll may hold:** any spell the cast door can cast, at the same
   fidelity as its cast (a told part stays told). Not alchemy's every-part rule. The owner
   is being asked about the parallel potion rule.
5. **Who may scribe what:** any spell up to max(1, floor(Enchanter level / 2)) in level, a
   wand never above 4th. The circle's own rule, not the book's refusal: a spell neither
   known nor carried in a scroll or potion is +5 DC (a carried one is spent), and an
   Enchanter level below the caster level another +5 (study Q5, Q16).
6. **Cost:** half the book price; the vellum, ink and blank count toward it; each whole
   100 gp of the rest is a mote of essence (the circle's 1 mote = 100 gp), the remainder
   coin "for the pigments" (study Q15).
7. **Vellum and the wand blank are bought** (vellum at the CRB's parchment price, 2 sp; the
   blank at 5 gp, ours). The study's vellum from the leatherworker and bone blank from a
   harvest are not built: the tannery's Cut has no vellum or blank pattern yet (study Q7).
8. **A miss** by 1 to 4 keeps everything (the circle's Bind rule); by 5 or more the vellum
   or blank and the ink spoil and the essences are kept. No curse on a scroll or a wand.
9. **Quality** raises the caster level by one a step above Sound, never above the Enchanter
   level (alchemy's rule, owner Q6.4), and the price follows the caster level.
10. **A scroll's tradition** is its writer's when a caster writes a spell on their own list;
    otherwise arcane if the spell is on the wizard's or sorcerer's list, else divine. A
    cure light wounds scroll from a shop is divine; a cleric reads it, a wizard needs UMD.
11. **A failed caster level check** keeps the scroll (the book does not say). A mishap is
    the book's first, 1d6 per spell level to the reader: the GM picks among seven in the
    book, and the engine takes the one with a number.
12. **Use Magic Device on a scroll** asks no further caster level check (the DC 20 + CL is
    it); the book does not say either way.
13. **Deciphering** is the circle's Identify: a found scroll whose writing is not known is
    refused until identified, for reading and for copying. A bought or made one is known.
14. **A wand stack** shares one layer: the charges are the wand in hand's, and an emptied
    wand is taken off the stack. A part-used wand sells at the full price (not reduced by
    charges spent).
15. **No limit on works in progress** (round 4) holds for scrolls too, against the book's
    "one item per day".

## Not built

- **Staffs and rods** (task item 4): not started. The study's staff needs a wielder's-own
  CL and DC branch in the cast door; rods would start with the six lesser metamagic rods on
  round 1's metamagic. Craft Staff and Craft Rod are retired with the rest.
- **Constructs at the circle** are the constructs lane's (Animate, merged on
  integrate/0.5.1-impl 92e7f06b), not this lane's.
- **Loot:** printed wands and scrolls in stat blocks ("wand of cure light wounds (20
  charges)") are still not read off a body; only shops sell them.
- Use Magic Device's other uses (activate blindly, emulate a race or an alignment,
  decipher a written spell).
