# The fight is the engine's, from either side

Group 1 of the fix pass after the 2026-09-18 play-test (`docs/playtest-2026-09-18.md`,
items 13a, 14, 16, 17, 18, 19). Built on branch `fight-from-either-side`, 2026-09-18.
Tests: `tests/test_fight_from_either_side.py` (24, each named for the defect it holds).

## What was wrong, in one sentence each

- The only door into an encounter from the world's side was the model's own
  `begin_encounter` op; the player was attacked and nothing rolled (16).
- The man who swung was never on the board: introduced as "the man in the leather
  apron", the ledger kept "man", found "desperate man" and skipped him (16b).
- "I strike the weapon and sunder it" refused five times on "a sunder needs a target",
  then the misaim repair spawned a thug named "weapon" (16c, 17, 19).
- Seven bystanders promoted from prose were all fightable and all candidates for
  "him"; a 4-hp boy died to a thrown chunk of wood (18, 14).
- The thread's subject was a free phrase bound to nobody; the fight's first attack
  went to the man the player had spoken to, not the challenger (14).
- Sunder's `damages_item` flag was read by nothing: no damage roll, the club took
  nothing, the prose decided it was in fragments (13a).
- An NPC's miss reached the page as "Your blade whistles through the air" (17a).
- The death backstop appended a second death after a described one, and a pebble took
  a head off (17b).

## What was built

**The fight opens on their swing.** `judgement.attacked_by(scene, beat)` reads a GM beat
for a non-player striking at the player — a finite attack verb, then "you"/"your" in the
same sentence, with negations, threats and feints refused ("waiting for you", "threatens
to lunge", "as if to"). The striker is the actor whose name-head stands before the verb,
else the pronoun's antecedent (the last non-player named earlier in the beat), else
nobody — and nobody is logged (`npc-opener`, ref None), never guessed. `Engine.struck_first`
then runs the same attack twice: the first run forms the encounter through the existing
first-swing gate (`_ensure_encounter`: sides drawn between him and the player ONLY, the
grid laid, the initiator holding the turn) and stops at "battle is joined"; the second is
his swing with dice. The player is flat-footed until they act, as the Core Rulebook has
it ("before your first regular turn in the initiative order, you are flat-footed"). The
NPC loop then carries the order on to the player.

**The second man is booked.** `_CAST_INTRO` keeps one article-led description after the
role ("man in the leather apron", "woman in the doorway"; a participle or material or
colour, then one noun, so a verb is never booked). Dedup on the head word applies only to
a bare repeat: "the man" after "desperate man" is the same man; a described one is a
second person.

**Bystanders are not combatants.** Promoted civilians carry the condition `bystander`
(tag `role.bystander`, `rules/states.py`, the key `states.BYSTANDER_KEY`). `_can_be_fought`
refuses them, so no fill lands on them and "I attack" cannot mean them; the tag is lifted
by the one door into a fight (`join_fight`) and by a blow given or taken (`_op_attack`,
`_ensure_encounter`). The cap counts bodies standing, not ledger entries. Bare plural
roles ("weary porters", "nearby merchants") stay prose: one body with a plural name and
4 hp was the "local guards" of the play-test roster. The person the beat puts in front
of the player — a challenge cue in their sentence (`_CHALLENGES`: steps forward, squares
off, ready to spring, the grin deepens…) — goes in over the cap.

**The engagement is a ref.** `bind_thread` gives the thread's subject a ref: an actor
whose name shares a distinctive word with it, else the one promoted person the beat
puts in front of the player while the engagement is fresh (age ≤ 1). A fight keeps it as
`thread["opponent"]` whether it opened by `begin_encounter` or by a swing, so the anchor
never writes "you are still waiting for a challenger" into the beat that squares them
off. `check_the_target` holds the plan's attack to `engaged_refs`: one engaged person and
a target the player never named is moved with the fix named; two live foes and no name
is handed back through the engine's own refusal (`params.undecided` → "Which of them —
X or Y? Say who, and the blow follows."). A player who names their victim is never
second-guessed.

**A thing is not a person.** `names_a_thing` refuses the misaim spawn for an object
phrase; the spawn op refuses an object name at validation with the fix named; the spawn
hint says so. `aim_at_the_holder` turns "I strike the weapon" into an attack on the one
person engaged, and sets the sunder the player asked for whether or not anybody is
engaged (the manoeuvre correction only ever removed one).

**Sunder breaks the thing it hit.** Core Rulebook, Sunder (aonprd.com): "If your attack is
successful, you deal damage to the item normally. Damage that exceeds the object's
Hardness is subtracted from its hit points. If an object has equal to or less than half
its total hit points remaining, it gains the broken condition. If the damage you deal
would reduce the object to less than 0 hit points, you can choose to destroy it." The
manoeuvre now rolls the attacker's weapon damage against the held item through
`Item.take_damage` (hardness, broken at half, destroyed at zero; the hand is emptied), the
CMB roll is parked in `attack_state` so the player rolls each die once, and the tell names
the state: unmarked / dented / broken / destroyed — in pieces. When the beat omits the
item's fate the view appends the tell's own sentence (`item_fate_on_the_page`).

**Agency is a fact of the tell.** `wrong_hands` flags "your blade / you swing" when the
turn's blows were all somebody else's; `right_hands` is the free backstop (cut, the plain
tell in second person in its place) — the one that runs on the NPC turn where no rewrite
does. `premature_blows` / `cut_premature_blows` do the same for a blow landed on the turn
the fight was only declared. Both read `blows`, built from the outcomes' TELLS (law three).

**One death, the right size.** `_DEATH_LANGUAGE` accepts a described death ("does not
move", "lies still", "motionless"); `press_the_death` replaces the beat's own falling
sentence rather than appending a second death; the death pool takes the weapon's heft as
its third axis (light: always the plain line; one-handed: never the through-the-body
line); a verb after the NAME agrees with the name, not the pronoun ("The warrior takes
it … they are on the ground"). The award line names the fallen as people.

## Measured live, three replays on a copy of the `masta` save

Through `/api/say` and `/api/roll`, gemma-4-12B heretic, the same six lines each time:
stand and stare down the meanest man; wait for a challenger; the insult; strike the
weapon and sunder it; hit him; Continue.

| | Replay 1 (b41477f) | Replay 2 | Replay 3 |
|---|---|---|---|
| Second man booked with his description | yes ("massive man", "man with the dried fish") | yes | yes ("stranger") |
| Fight opened on HIS swing | **no** — 100 chars between verb and "your", 80-char window | no swing in the beat (he "tenses as if ready to spring") | model's own `begin_encounter` |
| Sunder set from the player's words | **no** — plain attack | yes | yes: CMB 38, 1d3+19 = 20 vs club, hardness 5, **0/10, in pieces, hand emptied** |
| Blow landed on the declaring turn | **yes** — "buckle… mangled" shipped | caught: `swing-not-yet-struck` cut it | n/a |
| Target held to the engaged man | no engaged ref (four promoted at once) | **wrong** — bound to the woman who recoiled; the challenger was over the cap | yes |
| Death: one, sized, agreeing | "The warrior **take** it" | one death, named "the woman in the shadows" | "He lies motionless" accepted; no second death |
| Award names a person | "for the warrior" | "for the woman in the shadows" | "for the stranger" |

Each **bold** failure became a test and a fix before the next replay: the sentence-wide
window; the sunder parameter independent of engagement; the challenge cue as the binding
signal and the cap bypass; the plural-scenery rule; the in-fight thread conversion; the
name-agreement tokens; the premature-blow guard; the item-fate line.

## Left open, seen in these replays (not group 1)

- On Continue the plan wrote the PLAYER's attack (replay 3) or an NPC attack from a
  wrong ref (replay 2, "the man in the scarred leather" not on the board → `weary
  porters`). Item 23, group 4.
- The NPC turn emitted `use_ability intimidation` with no actor and the refusal named the
  player ("Masta has no ability called intimidation"). NPC-turn actor fill — group 6.
- "the beast" for the player, "its" for a man: items 13c/12, group 3.
- `contradicts-the-engine` false positives: "shattered remains of the man's pride" read as
  the massive man hurt; "girls is described as hurt" for a collective name. Group 4.
- The model's `begin_encounter` on the insult beat was correct, and a swing the same
  beat described was then not rolled by anybody until his initiative came round. Since
  the fight is open, `joiners` does not read it and `attacked_by` does not run. Worth a
  measured look: does the first NPC turn always follow, or can a described swing be lost?
