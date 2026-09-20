# The two choices nobody can make from memory

Group 17 of the fix pass after the 2026-09-19 play-test. Branch `guided-choices`.
Tests: `tests/test_guided_choices.py` (16).

**Reported 2026-09-20**, with a screenshot of the forge showing *"Search all 1,474 feats"*
and *"Spells known — level 0-1 wizard spells 0 / 28"* over a box wanting comma-separated
ids:

> "not only is the spells known broken, You should move these to a page of their own and
> show a list of feats that only includes feats they meet the prerequisites for. People do
> not usually know the feats without looking through them so the process needs guiding.
> same for spells. Choosing known spells and then filling spell slots for the first session
> should be easy and intuitive chosen not from a massive list of all spells but instead
> from a list of spells they can take. if its a wizard only spells from the wizard spell
> list should pop up and even that should be limited to whatever level spells need chosen
> [lvl0-1 at first level]."

## What was measured before anything was designed

The rules layer already knew all of it. The forge called none of it.

- **`feats.available` and `feats.meets` already existed**, and 1,237 of the 1,474 feats
  carry prerequisites *parsed into structured conditions*. The forge searched names.
- **A 1st-level fighter qualifies for 143 feats.** Ten to one, and a list a person can read
  — general 61, combat 49, metamagic 32.
- **Every spell carries `lists` = {class: level}.** Wizard: 35 at level 0, 245 at level 1.
  "Only this class, only the levels it can cast" was already a query.
- **`creation.build`'s validation was correct**, including item 25's fix. The brokenness
  was entirely in the forge.

And the reported number was wrong in kind rather than in arithmetic: **0 / 28** is
`3 + Int mod`, which is right for that character — but it is the *first-level* allowance,
and the 35 cantrips a wizard is granted were neither counted nor mentioned anywhere.

## Prior art

- **Pathbuilder** shows what you qualify for. That is the positive case and the shape
  adopted here.
- **D&D Beyond's builder** is the cautionary one, and the two loudest standing complaints
  on its own forums are precisely the two reported at this table: it **offers every spell
  level at low level**, and it **does not show your slots while you choose**, so you pick
  blind. A third — the confusion between the spellbook and prepared spells — matters here
  because this app has had both since group 12, so the page names them apart.

## Built

**A second page.** The forge is now "who they are" then "what they can take", because what
a character may take is decided by what they are: prerequisites read *finished* scores, so
the race, the class and the six abilities have to be settled before the question can be
asked honestly. `creation._provisional` embodies the draft, asks it, and throws the body
away — the same move `build` already makes for feat legality, one step earlier.

**Feats.** `creation.feat_choices` returns both halves: `open` is what they qualify for,
`shut` is the rest *with the missing prerequisite named in plain English* ("needs Critical
Focus, caster level 9"). Both, because a list showing only what you can have today hides
the ladder you are climbing. A tick-box shows the shut ones, greyed and unclickable.

**Spells.** `creation.spell_choices` answers with the class's own list at only the levels
it can cast, the slots it will have on day one, and — for a wizard — the 35 cantrips
**granted rather than chosen**, stated as such, with the cap shown as the first-level
allowance it actually is.

**A wizard's cantrips are now granted by the server.** `build` adds every 0-level wizard
spell to the book. They are a rule, not a choice: "a wizard begins play with a spellbook
containing all 0-level wizard spells". The old forge demanded the whole book as typed ids,
so a player who typed their three first-level picks got a wizard with **no cantrips at
all** — a caster who cannot take a turn without spending a slot. The empty-book refusal now
counts the spells that were *chosen*, so the grant cannot swallow the choice.

**Prepared casters are told their slots too.** A cleric declares no spells-known cap — she
prepares from the whole list — and the first build of this page therefore showed her no
spell section whatever, which reads as a broken page rather than a kept rule. She now gets
the slot line and a sentence saying where her spells come from.

## Three defects the browser found that the tests could not

Every one of these passed its unit tests and was wrong on screen.

1. **The "show what they cannot take" tick-box appeared to do nothing.** The pool was
   `open` then `shut` and the list caps at 60 rows, so the shut entries began at row 138
   and were never reached. Interleaved by name now.
2. **The feat search bypassed the entire guided list.** Typing repaints `#featmatches`, and
   that repaint called the *old* `featMatches()`, which searches `FORGE.opts.feats` — all
   1,474. So the page rendered 143 correct rows and the first keystroke replaced them with
   feats needing a Leadership score of 13. Two implementations of one question, which is
   exactly what CLAUDE.md says to grep for; there is one now, and it reads the server's
   answer.
3. **Mythic feats were being offered.** `feats.NOT_YET` already shuts 155 of the 158 by
   treating `mythic_tier` as uncheckable, but three state no prerequisite at all — Extra
   Mythic Power, Mythic Paragon, Potent Surge — and a first-level character in a game with
   no mythic tiers was being offered them.

## One rule that was nearly copied

The racial ability adjustment lived inline in `build`, and this page needs the same
finished scores. It is `creation.place_racial_adjustments` now, called by both. A second
copy would have been a rule with two homes, and the one that drifted would be the one the
player sees — the forge showing a cap of three where the server grants four, which
`spellCap` already carries a comment about having happened once.

## Driven in the browser, end to end

A wizard forged through the real page: feat picked by click (1/2), "missile" typed,
Magic Missile picked (1/7, search text kept, focus returned to the box), three spells
chosen, **Create for the roster** pressed. The saved character:

    name: Vess | class: wizard | race: human
    feats: ['combat casting', 'toughness']
    spellbook: 38  by level: {1: 3, 0: 35}
    abilities: int 18   (16 bought, +2 human)

Three chosen, thirty-five granted. A cleric shows domains, her slots and no picker; a
fighter shows 143 feats and no spell section at all.
