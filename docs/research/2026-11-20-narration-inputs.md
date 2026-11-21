# Research: narration inputs (lane fix/narration-inputs, 2026-11-20)

Playtest 2026-11-20 items #23, #24, #25 and two more from "Version check on items 23-27":
after-turn state in pre-blow slots (A3) and "the page said" promoting the narrator's own
sentences. All five reproduced from the owner's save (shadow) or the 0.4.4 plans in
`pgm-work/prose-gold/plans/`.

## 1. #23: the crowd line with nobody to see

**Reproduced.** In the owner's save the party is in the empty ruins. Only a broken clockwork spy is
present. `scene.heat` = "the player just killed second lizard in front of onlookers" (age 6),
and `heat_brief` still gives "Bystanders react to it ... someone running for the watch".
`note_heat` counts as a watcher any non-PC who is not down
(`any(not a.is_pc and not a.is_down ...)`). The foes being fought were the "onlookers" of
their own fight. The note was then carried for 8 turns wherever the player went
(shadow-0097: "attacked ghoran", which was three beats old).

**PF1e.** No rule makes a crowd react. Whether anyone notices is Perception (CRB p.102),
and a creature has to be there to notice. Nothing in the book makes your enemies
"bystanders".

**Traditions.**
- Skyrim's crime system, from wikis rather than official documentation. A bounty comes
  only from a *witness* who sees the act. UESP says most living creatures count,
  "including horses, farm animals, and hostile bandits". Killing the witnesses soon after
  removes the bounty. Sources: https://en.uesp.net/wiki/Skyrim:Crime (403 to the fetcher;
  the claim is from the search snippet) and https://skyrim.wiki.fextralife.com/Crime
  ("Anyone that sees you commit a crime will become a witness").
  - Hostile bandits as witnesses is the part players ridicule, and crime mods change it.
    I could not source a statement from Bethesda that they changed it, so I do not claim
    it was abandoned. I take only the core: the reaction belongs to the witnesses, and it
    lasts only while a witness lives.
- Blades in the Dark, heat (https://bladesinthedark.com/heat). Its base heat is set by
  exposure: "Smooth & quiet; low exposure" is 0, and "Loud & chaotic; high exposure" is 4.
  - Critic's correction: the same page adds "+2 heat if killing was involved (whether the
    crew did the killing or not—bodies draw attention)". So Blades does charge some heat
    for an act nobody saw. I cite it for exposure only. Blades' heat is the crew's
    standing with the law over time, which is closer to this engine's warrants
    (`trial.report`) than to a crowd's reaction in the moment.

**Chosen.**
- Heat records its witnesses. A witness is a non-PC present at the act who is not down,
  is not hidden, and is not a foe fighting the player (`attitude` hostile; the one struck
  is made hostile by the attack itself). Companions who came along are not "the crowd"
  either.
  - Known limit (the critic's): attitude is read after the turn. A guard who saw the act
    and turned hostile in the same turn is not counted as a witness. His reaction is his
    own fight turn, so this is accepted.
- The cast ledger (prose-people with no ref) no longer counts as watchers. The critic
  found it made heat out of a non-empty ledger with nobody in the room.
- With no witness there is no heat.
- `heat_brief` gives the line only while at least one recorded witness is still here and
  not down, and it names them ("seen by: X"), so the reaction is theirs.
- Walking away, or seeing them all go down, ends it, like Skyrim's dead witnesses.

**Rejected.**
- Keeping the line and only softening the wording. The shape of the prompt is the shape
  of the output (CLAUDE.md).
- A Perception roll per onlooker. 1e does not roll Perception for plainly visible acts.
  Line of sight to the act is already the engine's `harm_unseen`, and this lane does not
  extend it.

**Regex heat (`_HEAT_PROPERTY`, `_HEAT_BRANDISH`, `_HEAT_SHOUT`).** These read the
player's English and break the owner's "models read, code validates" ruling (memory
models-read-code-validates). The reader already reads these deeds in closed vocabulary:
- `attack` with a target that is no person here: goods, a crate, a door;
- `break_in`;
- `threaten`.

These replace `_HEAT_PROPERTY` and the threat half of `_HEAT_BRANDISH`, so the change is
contained. Drawing a weapon and shouting have NO closed reading today: the reader reads a
shout as `talk` and has no `draw` act. Replacing those two needs a new reader field (for
example `aloud: bool` on talk, and a `draw` act or `brandish` flag), benched on the
labelled set before reliance (docs/structured-turn.md; Ollama enforces enums and
required fields). That is not contained, so it is reported, and those two regexes are
removed. Their heat goes until the reader can carry them. This is an owner call.

## 2. #24: the blow said "down" beside "disabled: still standing"

**Reproduced.** shadow-0073 shows "the ghoran after it: down" beside the condition tell
"The ghoran is disabled: still standing". `rules.engine.left_after` bands `hp <= 0` as
"down". `Actor.apply_hp_state` writes `disabled` at exactly 0, and the condition tell
comes from that. Two ladders disagreed at 0 hp.

**PF1e.** CRB p.189 (as AoN gives it), Disabled (0 hit points), https://www.aonprd.com/Rules.aspx?Name=Disabled%20(0%20Hit%20Points)&Category=Injury%20and%20Death:
"You gain the staggered condition and can only take a single move or standard action each
turn". The disabled creature is up and acting, not down. Negative hit points is dying.
Pathfinder Unchained's optional wound thresholds
(https://legacy.aonprd.com/unchained/gameplay/woundLevels.html) are one ladder derived
from hp. Disabled starts at 0, and with Constitution 12 or more it runs down to minus the
Constitution modifier; it stacks with "critical". It is one ladder again, though not the
core rule's exact rung, which this engine follows.

**Traditions.**
- TempusMUD PR #493 (https://codeberg.org/TempusMUD/Tempuscode/pulls/493): "When killing
  something you just get the standard damage message instead of the death message". The
  fix restored the `update_pos` call before the message was chosen. The message has to
  read the same, updated state that the rest of the game reads.
- Dungeon Crawl Stone Soup has one enum ladder of monster damage levels
  (`mon_dam_level_type`, up to `MDAM_DEAD`, mon-stuff.h,
  https://sources.debian.org/src/crawl/2%3A0.7.1-3/source/mon-stuff.h) behind one
  function, `mons_get_damage_level`. I saw the declaration, not the body or every caller.

**Chosen.** `left_after` keeps its band names and reads the engine's own thresholds:
- dead at `Actor.death_floor()`, the one reader of the death threshold. This also fixes
  an undead or a troop at 0 being called "down" instead of dead.
- down when `is_down` (which includes hp < 0), when nonlethal damage exceeds hp, or when
  the construct's broken rung applies at 0;
  - Known limit (the critic's): a creature with ferocity, below 0 and still fighting, is
    banded "down" because `is_down` says so. The band now agrees with `is_down`, which is
    this item's point. Ferocity against `is_down` is a separate question, not changed here.
- a new band, "disabled", at exactly 0 for a living body. Its wordings say what the
  condition tell says: still standing.

**Rejected.**
- Banding after `apply_hp_state` runs. The band is computed as each blow falls, by
  design: a sap's knockout was banded before the tag landed (the docstring's 2026-10-16
  measurement), and the multi-blow order needs a band per blow.
- Dropping the "after it" fact. It is the blow's ending, which the slot is asked to write.

## 3. #25: the matter slot made of the player's own deed

**Reproduced.** In the owner's save, card `play-1` "The Hollow's Toll" has origin
`watcher`, tag `situation.play` and people c6, c7, c8, the lizards being fought. Its facts:
- "The lizard is dead."
- "The remaining lizards are now in active combat."
- "Shadow has collected the essence from the fallen lizard."

`cards._pull_one` takes `c.facts[-1]` as a SITUATION's fact. `matter_slot` then words it
"A matter of the world here, not a task of the player's: The Hollow's Toll — Shadow has
collected the essence ...", in shadow-0141 and shadow-0144.

**Traditions.**
- Blades in the Dark, progress clocks (https://bladesinthedark.com/progress-clocks).
  Faction clocks are each faction's "long-term goal", ticked by the GM in downtime. The PCs
  "may also directly affect" them by their scores. And: "Not every situation and obstacle
  requires a clock". A fight is a roll or a score, not a faction's matter.

**Chosen.**
- The watcher may not open a new card whose people are all actors of the running fight.
  The engine keeps the fight itself; the encounter is its card.
- At pull time, a card born in play (`situation.play`, the watcher's) with a standing of
  SITUATION is a matter only while one of its people is here and not down. The critic
  showed the name filter alone would still pull "The lizard is dead." from the owner's
  `play-1`. Cards already in saves are covered by this rule, not only new ones.
- At pull time, a world matter (standing SITUATION) never offers a fact that is the
  player's own doing. That is a fact naming the player's character, by the PC's own name
  from the sheet, which is closed vocabulary. The slot takes the latest fact that is not
  the player's, and with none the card is passed over.
- The name is matched as whole words (any word of the PC's name of three letters or
  more), not as a substring. Second-person facts ("You came on foot ...") are on the
  errand card, which is the player's OWN, so no pronoun rule is needed.

**Rejected.**
- A word list of "deed verbs".
- Reading the fact with a model. A second call per beat buys little over a name check
  against the sheet.

## 4. A3: after-turn state in slots that come before the blow

**Reproduced.** shadow-0097 shows PEOPLE HERE NOW with the spy already "broken, on the
ground" and slot 3's own text "The clockwork spy is broken", while slot 1 is the
squaring-up. Every slot shares one prefix, kept identical for the Ollama prompt cache, so
every slot sees the end of the turn. richer-prose-paths.md §1.5 measured the move slot in
#89 writing the strike ("lunge forward to strike the dying giant cockroach").

**Traditions.**
- The MUD message model (tbaMUD and Diku `dam_message`, cited in `blow_facts`; the
  TempusMUD PR above). Each message is emitted at its event with the state of that moment,
  never the end state.
- Data-to-text content planning: Puduppully, Dong & Lapata 2019, "Data-to-Text Generation
  with Content Selection and Planning" (AAAI). The plan is ordered and each segment
  realises its own records. Cited from memory of the paper; I did not refetch it.
- `Outcome.blows[].left` is already the per-event snapshot.

**Chosen.** The research note's option (b). A slot that comes before a blow slot is told,
in its own ask (not the shared prefix, so the cache holds), that the blow in slot N has not
happened yet, that the people it strikes are not yet struck, and that PEOPLE HERE and THE
SCENE NOW tell the end of the turn.

**Rejected.** Option (a), a second PEOPLE HERE per slot with the before-state. The engine
does not keep a pre-turn snapshot of each actor's bands, and building one is a larger
change that the exp/richer-prose arm does not need either. The same `NOT_YET` idea is in
that branch behind an environment switch; this lane makes it the default.

## 5. "the page said": the narrator's sentences as facts

**Reproduced.** In the owner's save, the clockwork spy's `described_as` is "You square your
shoulders and face the clockwork spy, preparing to strike from your current position." It
is shown as ALREADY DESCRIBED in shadow-0105 onwards, and the three lizards share the same
sentence (shadow-0111).

**Why it exists.** Item 16.7 (gm/brief/faces.py, commit 8426bd26). The page's first
description of a person is kept so later beats do not re-invent a face (the Bobby
watchman, 2026-09-28). That purpose is real, and it is Inform's "initial appearance":
https://ganelson.github.io/inform-website/book/WI_3_11.html, the text shown the first time
the player sees a thing, used until the player first handles it. That is a looser fit:
it is for things, and it lapses. The keeping here is the project's own item 16.7.

**The defect.** `judgement.settle_descriptions` keeps the sentences `describing_sentences`
returns. A sentence counts as describing a person when it names them and carries a body
word. On the code, the word that matched was "face", the VERB ("and face the clockwork
spy"). "Shoulders" is not in the body-word list. Kept, the narrator's
sentence about the PC became a "fact" about the spy, a seed for hallucination snowballing.
Zhang et al. 2023, https://arxiv.org/abs/2305.13534: models produce further errors to stay
consistent with an earlier one.

**Chosen.**
- "face" as a verb, which takes its object straight after it, is no face. A body word
  after "your" is the player's own body. Both are dropped inside `narration._describes`,
  as `_GESTURE` drops a gaze. Inside it, so that `faceless` agrees too; the critic caught
  that a fix in `describing_sentences` alone would still mark the spy as described.
- Saves already carrying such a sentence are mended where it is read (`faces.section`
  keeps only the sentences that still describe), and `settle_descriptions` un-marks a
  person whose kept sentences describe nobody, so they are owed a real face again.
- Not fixed: one generic sentence was booked to all three lizards (shadow-0111). That is
  attribution by a generic head noun, a separate defect.
- The description memory stays.

**Rejected.**
- Removing ALREADY DESCRIBED. It would bring back the face drift it fixed.
- Showing only the engine face. Many creatures have no held face, and then the page's
  description is the only continuity there is.
