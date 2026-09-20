# Spellcasting, and the cleric's own table

Group 12 of the fix pass after the 2026-09-19 play-test
(`docs/playtest-2026-09-18.md` items 25, 26 and the cleric half of 27). Branch
`spellcasting`. Tests: `tests/test_spellcasting.py` (15).

**Reported.** *"Spellcasting is broken in general. A lvl 1 cleric can cast wall of flame at
6th level."* — *"This spells panel should show a list of all known spells as well."* — *"oh
i had forgotten domains those need chosen at creation as well."*

## The engine's gate was never the fault

`_check_cast` makes nine checks including caster level, and refuses live: *"Flame Strike is
a level 5 spell and Ted is a level 1 cleric — they reach level 1."* The proof it was never
reached is on the player's own screen — after the wall of flame the panel still read **Spell
Slot 0: 3 of 3, Spell Slot 1: 4 of 4**. Nothing was cast. The gate was working; nothing ever
knocked on it.

Three links, each of which had to be fixed for any of it to work:

1. **The prepared check fired only for `prepare_from == "spellbook"`** — wizards. A cleric,
   druid, paladin or ranger prepared nothing, ever, for the life of the character. It now
   fires for every caster whose `kind` is `prepared`, and the prepared copy is spent with
   the slot for all of them.
2. **`inject_cast` built its vocabulary from `spellbook + prepared`**, which are empty for
   every one of those classes, so "I cast wall of flame" was never an intent and fell
   through to prose. It now reads `casting.known_spells`, which answers for each kind of
   caster: the book a wizard carries, the repertoire a sorcerer knows, the whole class list
   for a cleric or druid whose god is the book.
3. **The brief said nothing about spells at all** — not the slots, not the prepared list,
   not even that the character is a caster. It now states what can be cast, what is
   prepared, and how many slots are left, as fact.

And the backstop under all three, the same shape as `wrong-hands`:
`narration.cut_uncast_spells` cuts a sentence claiming a spell the engine did not cast. The
engine is the only thing that casts a spell, so prose asserting one it did not cast is
asserting an outcome that never happened.

### Two rules the book has that the app did not

- **Spontaneous cure conversion.** "A good cleric can spontaneously cast a cure spell in
  place of a prepared spell of the same level or higher." Alignment is deliberately not
  consulted — the ruling was *"don't worry about the gods or the alignment"* — and the
  healing half is the one the player asked for: *"may use a slot at any time for a healing
  spell of that slot level"*. The cheapest qualifying prepared spell pays for it, a domain
  slot never does, and the page says what was given up: *"Ted gives up Bless to cast Cure
  Light Wounds instead."*
- **A wizard's opening book.** "All 0-level wizard spells… plus three 1st-level spells of
  her choice… for each point of Intelligence bonus." A new wizard's book held **one** orison
  and five first-level spells; it now holds every cantrip in the corpus and 3 + Int. The
  creation cap counts the first-level ones only, which is what the book says — counting the
  cantrips refused a legal book as "38 spells against 4 known".

## The panel has a door (item 26)

Every number on that page was right — three orisons and four first-level slots is correct
for a Cleric 1 with WIS 30, and DC 21 is 10 + 1 + 10. It simply had no door: the tab offered
a `+` only on rows already in the book, so a list-caster read *"Nothing in the book yet"*
forever while the note beside it said *"A cleric prepares from the whole cleric list"*.

A third region now sits beside Slots and Prepared today, fed by `casting.known_spells`:
every spell the caster may choose from, grouped by spell level, levels they cannot reach
folded shut, and a search box — because a Cleric 1 chooses from **179** castable spells out
of a list of **1,143**. Each row's `+` calls the preparation endpoint, which already
enforced the rule the player asked for (what is prepared at a level, counted against the
slots at that level).

## Domains (item 27's cleric half)

**Derived, not authored.** Measured: 153 distinct domain names across 452 spells, carried on
the spell itself as `domain: "Luck (2), Tactics (2)"` — the name and the level it sits at.
So `rules/domains.py` is a query over the corpus and nothing needed transcribing. What the
corpus does *not* carry is the domain **powers**, and those are left unbuilt rather than
invented: a domain grants its spells here, and the module says so.

- **Picked at creation**, on the same screen as the spells and one step ahead of it, from a
  searchable list of all 153. A cleric without them is refused — the same precedent as a
  wizard with an empty book.
- **No deity step and no alignment gate**, per the ruling: *"grab whatever the belief system
  of the world is and let that be enough."* The world's own `Metaphysics` fact says why that
  is enough — "Gods are real, distant, and plural; no single faith holds the whole world."
- **The domain slot** is its own row: "one domain spell slot for each level of cleric spell
  she can cast, from 1st on up". Held apart from the ordinary slots rather than added into
  them, because only a domain spell may go in it — a cleric shown "4 of 4" who can only use
  three of them for what she wants has been told something false.

## The cleric's class table

The Class tab printed twenty rows of **—** because cleric, fighter, wizard and rogue lived
in `rules/tables.CLASSES` with no `levels` table at all. `content/classes/cleric.json` now
carries the rulebook's twenty rows — aura, channel energy at every odd level, domains,
orisons, spontaneous casting — in the same shape the other eight classes already used. Its
proficiencies are corrected too: the stub said "simple" and nothing else, and a cleric has
light armour, medium armour and shields.

The fighter, wizard and rogue are group 13.
