# By what means: the gate on deeds out of the character's reach

The owner, 2026-10-05: *"getting rid of the regex has brought back the ability to use
psychic powers and alter memories through narration. I dont want to put the regex back so
figure out how to solve this issue and if you cant do it without the regex put that one
back."* Then, the same day: *"if it allows those things there are an infinite number of
things it will allow. whatever you do must catch anything that is not within the players
power to do not just psychic and memory stuff"*.

## Where it leaked

Reproduced live on a copy of the owner's save (Sammy, a level-1 asura wizard, at the
smithy; gemma-4-12B heretic; master content, before this change):

| line | what happened |
|---|---|
| "I read the smith's mind" | caught: `refuse_unnamed_power` matched, the engine printed "Sammy has no ability called psychic powers. They can use: nothing yet." (wrong for a wizard with eight spells) |
| "I make the smith forget he saw me" | **leaked**: no `_PSYCHIC` pattern lists "forget"; the plan made it Diplomacy against the smith's Perception, and a roll was asked for a memory wipe |
| "I erase the apprentice's memory of me" | **leaked**: the regex matched and stood down, because the plan had guessed `cast charm-person` (the door stands down for any cast); the engine refused the cast (not prepared); `_players_refusal` dropped it as "an op nobody asked for"; the page wrote "the flicker of recognition of your presence … simply dissolves" |
| "I make the apprentice remember me as his cousin" | **leaked**: read `claim`, planned as Bluff |
| "I convince the smith I was never here" | correct: Bluff |

The regex had not been removed: it was still called on the turn's path. It leaked by its
gaps (a phrasing list has no end) and by trusting the plan's own guess as the player's
power. The owner's saves this shell can read (sammy, bobby, bobby-2) hold no such turn.

## Prior art

- **Play-by-post etiquette** on autohitting and godmodding: "you write the attempt, they
  write the result" (CharHaven, "Roleplay Etiquette"; rulesofroleplay on tumblr). A
  declared result is not a result.
- **Dogs in the Vineyard**, "say yes or roll the dice" (Baker 2004): an ordinary attempt
  is the dice's.
- **Apocalypse World**, "to do it, you do it" and fictional positioning: without the
  positioning, the move does not trigger, whatever is said.
- **Fate System Toolkit**, extras as permissions: an aspect or extra is what lets a
  character do what others cannot. I could not fetch the SRD page that defines it (404);
  the summary is from search results only.
- **PF1e Bluff** (CRB; d20pfsrd): some lies are so implausible that no check convinces
  anybody — the book's own ceiling on talking a mind round.
- **dungeonOne issue #111** (an LLM-GM project): the engine refused a change and the
  narration claimed it anyway; its fixes are an engine-authored fallback and a check that
  the narration does not assert results the turn did not produce. Ours are both.
- GAS, already this engine's rule: an ability that was never granted cannot be activated.

All of them sort a deed by HOW it is done, never by a list of WHAT may not be done.

## What was built

1. **The reader writes the means** (`gm/interpret.py`, `MEANS`): every action carries a
   required enum `means` — `ordinary` (anything a person could try), `power` (a named
   spell, ability, trait, feat or item; its name copied into `power`, held to the
   sentence like every slot), `beyond` (nothing an ordinary person can do, no power
   named). Last in each per-act alternative, so it chooses no act. Thirteen new
   demonstrations, none in the corpus (five of them written from dev-set misses).
2. **Code asks the sheet** (`gm/means.py`): `held_power` looks the power's name, or the
   deed's own words, up in closed vocabularies — the spells the caster can reach (the one
   spell finder), class and path abilities, feats, race traits, things carried.
   `which_power` puts what no name found to one enum question over the sheet's own list
   plus "anyone could try this" and "none" (the asura's wings, "I bend the bars"). Spells
   are never offered to it: a spell stood behind a deed it does not do is the leak.
   A turn that only claims ("I decide the smith owes me fifty gold") is refused as
   saying-so.
3. **Where it lands** (`gm/agent.py`): a turn of nothing but deeds out of reach is the
   refusal, printed (422, no turn spent), naming what was reached for, why, the spells
   and abilities the character can use, and the ordinary routes — and no model is asked.
   A mixed turn keeps its ordinary half: the plan's guesses at the refused part are struck
   (`strike`, including a guessed cast like the charm person above) and the engine's
   ability door prints the refusal as a tell. A held power the words reached for joins
   the declared ops, so its refusal (unprepared) is the player's to hear, not dropped.
4. **The page** (`gm/checks/power_unbacked.py`): the finished beat is asked one closed
   question — which sentence has the player doing what no ordinary person can that the
   rules did not resolve this turn — shown the resolved tells and the character's own
   gifts. One rewrite naming the fact, then the sentence cut and an authored line put in
   its place.

The regex door `refuse_unnamed_power` stays where it was (see the numbers).

## Numbers

`tools/means_bench.py`, gemma-4-12B heretic, shipped fixture sheets (Kesst, a rogue;
Ysolde, a wizard). The corpus is `tests/means/gold.py`. DEV is 87 refuse / 89 pass / 9
declared-result lines; HELD_OUT (written after the first pass, no fix made from it) is 47
/ 41 / 5. "psychic" is the regex gate's own 32 + 40 from tests/test_psychic_powers.py.

| | refused (should) | spared (should) |
|---|---|---|
| regex doors only, dev | 9/87 | 89/89 |
| regex doors only, held-out | 2/47 | 41/41 |
| regex doors only, psychic | 32/32 | 40/40 |
| means gate, dev, first pass | 83/87 | 86/89 |
| means gate, dev, final | 85/87 | 89/89 |
| **means gate, held-out, final** | **43/47** | **41/41** |
| means gate, psychic, final | 30/32 | 39/40 |
| **both, as the turn runs them, psychic** | **32/32** | **39/40** |
| both, dev / held-out | 85/87 / 43/47 | 89/89 / 41/41 |

Declared results ("…and he believes every word") were never refused (14/14); the reader
put the result in `claims` on 9 of 14 — the rest merged it into the deed, which the dice
then decide anyway.

**The regex stays on the path**, because the regex-free gate alone does not reach the old
gate's numbers on its own corpus: 30/32 against 32/32 ("I search his memories for the
name" and "I charm the guard" were stood as anybody's by the enum question). Together
they catch 32/32 there and lose nothing elsewhere: the regex never refused a line that
should pass. The one psychic false refusal is "I charm the snake with my flute" for a
rogue who carries no flute — the reader named the flute as the power, and the sheet does
not hold one.

**The held-out misses** (looked at once, after the gate froze): "I squeeze myself through
the keyhole", "I shatter the door with a shout", "I spit acid at the guard", "I declare
that I am now the mayor of this town" — all read `ordinary`. They reach the engine as an
attempt (a check, an attack, a Bluff); the page check is the net for the prose.

**On real play** (the interpreter's 302 labelled lines, read with the new schema): no line
came back `beyond`; four came back `power`, all real casts or a potion (they stand or fall
on the sheet, as they should); three came back as a bare claim, and the closed claim
question (`means.claim_kind`) passed the two that are plans ("I plan to rob the counting
house tonight", "I mean to kill him if he comes back") and refuses "I am the lost heir of
the old kings". Probed live on 12 bare claims, it sorted all 12 as intended.

**The reader did not get worse** with the new fields: on the held-out 160 of
`tools/interpreter_bench.py`, strict 0.713, engine-relevant 0.831, acts in order 0.875,
against round 2's final 0.681 / 0.787 / 0.838; no failed call in 302.

**The page check** read the owner's leaked page live and named "His pupils dilate … the
flicker of recognition of your presence … simply dissolves"; it named nothing on three
clean pages of the same session (a refused mind read narrated as failing, a walk, a
punch).

**Live, in the running app** (copy of the owner's save, own server, 2026-10-06): "I read
the innkeeper's mind" and "I make the guard forget he saw me" came back as the printed
refusal in 18 s and 8 s (no planner call; the turn was not spent); "I convince the guard I
was never here" went to the planner, asked for a Bluff roll, and the page wrote the lie
hanging in the air with the guard unconvinced — no memory touched.

**Skills are held (2026-10-08).** "I use the Heal skill on the porter" was read
`means: power, power: Heal` and refused as "no spell, ability or item by that name … has no
powers yet" (the deeds lane, local model). Every skill of `tables.SKILLS` is now on the
sheet's held list (`means._skill_names`; "skill" is filler in a power's name), backs a
`check` (`HELD_OPS`), and is kept out of `which_power`'s enum. Fly is not: the Fly skill is
for a creature that already flies. Re-run on all three corpora with fresh readings: no deed
in dev, held-out or psychic is backed by a skill (dev 86/87 refused, 89/89 spared; held-out
43/47, 41/41 — the documented finals or better).

## Not done

- The page check has no bench of its own; it is measured on the live turns only.
- The reader's means is not scored in `tools/interpreter_bench.py`.
- A wizard who says "I read his mind" without naming a spell is refused even if she
  holds one that would do it; the refusal lists her spells.
- `which_power` costs one short call per deed nothing was found for by name.
