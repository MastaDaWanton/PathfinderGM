# Quest schemes — a plan, and its second pass

Planned 2026-09-08 from a conversation: "is there a way that we can have complex
quests … on the way we find out that was a lie … when we bring the flower back he is
gone and the PC walks into a murder scene as the guards arrive … is it possible to have
that quest get messed up if I turn back early". Then: "instead of letting the complex
quests be created we should make them and give them triggers", "the quests we write
[should] be world agnostic", "plan a system … make sure we align it with our GAS like
framework … plan out a full quest line … use consequences and rewards as incentives",
and "check it critically for improvements and better methods."

**Nothing here is built.** It is the design of record for when it is.

---

## 1. What the traditions do, and what the first draft got wrong

The first draft was a *grim-portent timetable*: an ordered list of steps, each firing
at an hour. The second pass checked that against five traditions and changed it.

- **Dungeon World's fronts** (grim portents, impending doom) are what the twist *feels*
  like from the GM's chair: a plan that advances when the players look away. Kept as the
  authoring metaphor.
- **Inform's scenes** begin and end on *conditions* ("begins when the player is in the
  lodging and the giver is absent"), never on a clock alone. Time is one condition among
  many. This is the correction that matters most: the world clock in this app jumps —
  a travel is hours, a haggle is minutes — so a step keyed to "hour four" fires in
  whatever scene happens to be running, mid-haggle, with no way to place it.
- **Valve's rule databases** (Ruskin, GDC 2012, the Left 4 Dead dialogue system) pick
  which authored line fires by *salience*: every rule lists criteria over the world
  state; all rules whose criteria hold are candidates; the one with the **most
  criteria** wins, so the most specific authored beat beats the generic one. Adopted
  wholesale for choosing which step of which scheme fires on a given tick.
- **Storylets / quality-based narrative** (Fallen London; Short's surveys): a story is
  many small pieces, each with prerequisites over "qualities" and results that change
  them, and the great virtue is modularity — pieces written later interlock with pieces
  written earlier. Our qualities are already there: the tag vocabulary. A scheme step
  is a storylet whose prerequisites are `has_state` questions. Short's warning is also
  ours: the bookkeeping of qualities is manual, and the economy of them has to be
  balanced or every story fires at once.
- **Skyrim's quest stages** and **Baldur's Gate 3's journal**: stages are not always
  reached, and not in order; objectives are separate from what has happened. Kept.

**Refused, with reasons.** A linear timetable (brittle, see above). The watcher
inventing schemes (the least reliable author; structure is authored, colour is
generated). Free-text conditions the model evaluates (a condition is a tag query or a
registered event, or it does not save). Borrowing the published adventures' stories or
speech (the import holds their numbers only, and the narrator's material is the world's
own words).

---

## 2. The system

### 2.1 A scheme is a document

Same grammar family as a feat, a race, a class ability. Shipped in `content/schemes/`,
editable on a homebrew bench, and later a `play.schemes[]` list in a World Bible
export. Fields:

| Field | Meaning |
|---|---|
| `id`, `title`, `about` | the scheme as the author names it; `about` is for the bench, never the brief |
| `slots` | roles and places with no names (§2.2) |
| `cards` | the visible quest card(s) and the secret card(s) it opens, as card documents with `$slot` placeholders in their text |
| `steps` | the storylets (§2.3) |
| `outcomes` | named endings with effects and what they open next (§2.4) |
| `fairness` | the foreshadowing the author promises: which tags the brief must have carried before the twist may fire (§2.5) |

Validated on save with the fix named, the classbuilder's style: a slot with no filler
rule, a step naming an event the registry does not know, a condition that is not a tag
query, an outcome that grants a tag outside the vocabulary, a number in any prose field.

### 2.2 Slots, filled once, from the world

A slot is `{"role": "giver", "wants": {...}}` or `{"place": "lodging", "kind": ...}`.
Roles are filled from the world's cast by role words in its facts, then from the
bestiary by role words and challenge rating — the NPC Codex and Inner Sea NPC Codex
first (generic people by class and level), the Villain and Monster Codexes second, the
adventure-path blocks last with their names stripped, the three hand-written townsfolk
as the floor. Places are filled from the places module by kind (`market`, `lodging`,
`gate`, `road`, `wild`), which the three doors already provide in every settlement.
Items are filled from the ingredient list by biome. **Filled once, at open, and frozen
on the scheme instance**: the giver cannot change halfway. A slot no world can fill
falls back to a minted bestiary body with a name from the world's naming, so a scheme
never refuses to open and never names a stranger.

This depends on one piece of infrastructure the app lacks: a **chooser** from role
words to a stat block, and an **NPCs bench** where the chosen block for a world
character is kept and can be corrected. That is the reserved, unbuilt NPCs bench, and
it comes first.

### 2.3 Steps are storylets, chosen by salience

A step: `{"id", "criteria": [...], "action": {...}, "tell": "...", "once": true}`.

- **Criteria** are tag queries and registered events, over the scheme's slots and the
  world: `player.at == $lodging`, `not has_state($giver, "state.hidden")`, `clock >=
  opened + 2h`, `event:objective_done($quest, 2)`, `event:item_gained($flower)`,
  `has_state(pc, "knows.giver-lied")`. Time is a criterion like any other.
- **Selection**: on every tick — a turn ending, a travel arriving, the clock advancing
  — every step of every open scheme whose criteria all hold is a candidate; the one
  with the most criteria fires (Valve's rule); ties break by authored order. One step
  per tick, so the world never does three things at once.
- **Actions** are the existing vocabulary only: move a person (`Scene.move`), open or
  resolve a card, add a fact, bring a creature in, tick or reveal an objective, grant an
  effect. No new mechanics; a schedule for the ones we have.
- **Breakers** are simply criteria with `not`: a step that needs the giver still
  hidden does not fire once the player has found him. Every step must have at least
  one criterion a player could plausibly change — the validator counts them.
- **Out of sight is silent.** (Corrected 2026-09-08: the first draft had a
  "meanwhile" paragraph handed to the narrator, which would tell the player what their
  character cannot know — the same fault as the narrator inventing a belt.) A step that
  fires where the player is not changes the world and says nothing to the prose. Its
  tell goes to the turn log with its provenance, and to the secret card on the GM's
  brief marked "the GM's alone" — so the narrator may let the world *behave* as if it
  happened (a guard glancing at you twice) but may not state it. The player learns it
  the way their character would: the empty room when they arrive, the body, the
  guards' words, the Witness's account. Three exceptions, each an authored choice on
  the step and refused otherwise: a step may carry a **perceptible** tell when its
  criteria put the player within earshot or sight of it (a shout from the street,
  riders passing the gate the player is standing at); a step may **defer** its tell to
  a later step that has the player present (the guards say what they were told); and a
  step may name a **teller**, a person on the board who will say it when next spoken to.
  Steps that need the player *present* (the guards arrive) carry `player.at == $place`
  as a criterion and so never fire elsewhere.
- **News: the world comes to you, by a route your character would meet.** (Added
  2026-09-08: "a letter arriving with an invitation to the funeral of a person who was
  murdered while the player was out".) A step that fires out of sight may name a news
  item — a *carrier* (a letter by courier, a crier or posted notice, gossip from a
  stallholder, kin or a witness who seeks you out, an invitation), a *reach* (who could
  have heard: kin only, the town, the next settlement) and a *delay*. Its arrival is a
  salience step like any other: the delay elapsed, the player at a place the carrier
  reaches, for gossip a person on the board who would have heard, for an invitation a
  `knows.*` tag that says the kin know the player's name. It fires as an outcome with a
  tell in the world's terms ("a boy at the gate hands you a folded letter") and grants
  `knows.<fact>` through the applicator — which is exactly the foreshadowing the
  fairness rule looks for, so news is also how later twists become fair. Two rules: news
  carries no more than its carrier could know (kin say the victim is dead, not who did
  it; gossip may be wrong, and a false rumour is its own storylet), and news is always
  an object or a person in the scene the player can read, question or throw away —
  never a fact the narrator volunteers. News opens choices, not conclusions: the
  invitation opens the funeral as a storylet at a place within a window; attending opens
  the clues; ignoring it costs regard and leaves the guards' version the only one told.
  Prior art: Skyrim's courier, Crusader Kings' messages, Dwarf Fortress's rumours by
  contact and distance, Mount & Blade's tavern rumours.

### 2.4 Outcomes, rewards and consequences are effects

An outcome names effects through the one applicator with source `scheme:<id>/<outcome>`:

- Rewards: coin to the purse, an item to stock, a place founded and held
  (`holds.place.*`), a companion added, the story award (`award_story("new")`), regard
  (`attitude.*` on a person or a faction's people).
- Consequences: the same with the sign reversed, plus **`state.wanted.<town>`** and its
  lesser `state.suspected.<town>`, granted as `ActiveEffect`s with `until-dismissed`.
  Two readers make them bite: the gate refuses and the stallholders charge more or
  refuse (pricing asks `has_state`), and guards join a fight against the player (the
  join-fight door already reads sides). Clearing the name removes the effect and every
  bite evaporates with it — law two, exactly.

### 2.5 The three laws, and fairness

- **One vocabulary.** Everything a scheme tests or grants is a tag; `knows.*` for what
  the player has learned, `state.wanted.*`, `attitude.*`, `holds.*`. No string match.
- **One applicator.** Every grant is an effect with a source; removal is one call.
- **Severed tells.** A step fires as an engine outcome with a tell; the narrator
  dresses it; prose claiming a step that did not fire dies in the scrubber. Provenance
  on every outcome: `scheme:<id>/<step>`.
- **Model proposes, engine disposes.** The GM may still propose `quest_step` and the
  watcher may still add facts; neither may add a step, change criteria, or open a
  scheme. The salience pass is deterministic and seedable, so a scheme is testable.
- **Fairness is enforced, not hoped for.** A twist step lists the `knows.*` or
  `situation.*` tags that must already be on the player's brief (the giver's unease was
  narrated; the witness was met). The validator refuses a scheme whose twist has no
  foreshadowing; the engine refuses to fire a twist whose foreshadowing tags are not
  held. Being framed is fair when you could have seen it and chose the flower anyway.

### 2.6 Order of building

1. The NPCs bench and the role-word chooser over the bestiary (prerequisite).
2. The scheme document, validator, slot filling, salience selection, the silent
   out-of-sight rule with its three authored exceptions.
3. `state.wanted` with its two readers.
4. The line below, hand-written, played end to end in both worlds.
5. Only then: schemes in the World Bible export; never the watcher authoring them.

---

## 3. The line: "A Small Favour" (world-agnostic)

Slots: **Giver** (a trader or fixer from the cast, else an NPC Codex expert), **Victim**
(a person of standing the Patron's `wants` stood against), **Patron** (a faction from the
export's `conflicts`), **Captain** (a guard officer build), **Witness** (the opening's own
companion, already on the board), **Hunter** (a ranger or assassin build by level).
Places: `market`, `lodging`, `wild` (a few hours out), `gate`, `road`. Item: `errand`
(an ingredient of the biome).

**Q1 — The errand.** At the market the Giver asks for the errand item from the wild
place. Visible objectives: go, gather, return; promise in words ("a season's custom at
cost"). Secret card: the Giver is paid by the Patron to have the Victim dead and an
outsider blamed. Foreshadowing tags the brief must carry before the twist: the Giver's
unease (`knows.giver-uneasy`, granted when the quest opens, so the prose has it), the
Witness having spoken of the Victim.
Steps (each shown as criteria → action):
- player left the market, ≥1h → the Giver moves to the lodging, `state.hidden`.
- Giver hidden, ≥3h, player not at the lodging → the Victim is moved to the lodging and
  killed off-stage; a fact on the secret card; `meanwhile` tell.
- player arrives at the market with the item, Victim dead → the Captain and two guards
  brought in, hostile; `state.suspected.<town>`; visible card gains "the guards say
  the Victim is dead and name you"; outcome `betrayed` → Q2.
- player arrives at the lodging while Giver hidden and Victim alive → the Giver is
  found with the Victim: the plan collapses; outcome `exposed` → Q3 opens early, with
  the Victim's regard raised.
- player returns to the market <1h → the Giver is there, uneasy; nothing fires; the
  errand stands (the honest path: the scheme is only a scheme if you go).

**Q2 — Wanted.** `state.wanted.<town>`: prices up, gate shut, guards join against you.
Two visible quests at once. *Clear your name*: three clues, any two suffice — the
Witness's word (a talk at the tavern), the Giver's ledger (the lodging), the Patron's
coin on the body (the temple or wherever the dead are laid). *Leave by the road*: the
Witness knows a way past the gate, at the cost of `attitude.unfriendly` from the town.

**Q3 — The one who paid.** Opens on two clues held, or on `exposed`. The Giver is at the
wild place or on the road. Taken: he names the Patron and can be kept as a companion
with a debt (`attitude.friendly`, a `holds.debt.*` tag the narrator can use). Killed:
the secret card gains "the loose end is gone"; the road quest closes; the Patron's
regard rises — a reward with a hook in it.

**Q4 — The Patron.** The faction's own `wants`, `works_by`, `holds` and `undone_by`
become the objectives: what it holds is where the proof is, what undoes it is how you
win. Outcomes: **justice** — wanted removed, Captain helpful, story award, the Victim's
kin grant a house (founded and held); **bargain** — coin and the Patron's regard, wanted
softened to suspected, Captain unfriendly; **failure** — wanted hardens, Q5 opens.

**Q5 — The price on your head.** Hunters from the bestiary by biome and the player's
level, on a criterion of days elapsed rather than hours, until the name is cleared, the
region left, or the Patron ended. Its breakers are Q4's endings.

**A lighter first scheme to prove the machinery** before this one: *The lost thing* —
a giver, a lost item at the wild place, a rival who took it, one twist (the rival is the
giver's kin), one consequence (returning it to the wrong one costs regard). Three
steps, no guards, no deaths. If the salience pass, the slots and the out-of-sight rule
hold there, the murder line is safe to play.

---

## 4. Costs, stated plainly

- Turn time: none at play for authored schemes; a salience pass is a dictionary scan.
- Development: the chooser and the NPCs bench first; the scheme grammar and validator;
  two readers for wanted; the out-of-sight rule; then authoring and playing two lines.
- Legibility: more hidden state; every step is on the turn log with its provenance, and
  a `schemes` view on the sheet (GM-only, or after the fact) shows what fired and why.
- Authoring: a scheme is a few dozen lines with conditions, and a wrong criterion is a
  quest that never fires or fires at once. The validator's counting rules (every step
  has a player-changeable criterion; every twist has foreshadowing) catch the worst.

Sources: [Ruskin, Rule Databases for Contextual Dialog (GDC 2012)](https://archive.org/stream/valve-publications/2012/GDC2012_Ruskin_Elan_DynamicDialog_djvu.txt);
[Short, Beyond Branching: quality-based, salience-based and waypoint narrative](https://emshort.blog/2016/04/12/beyond-branching-quality-based-and-salience-based-narrative-structures/);
[Short, survey of storylets](https://emshort.blog/2019/01/06/kreminski-on-storylets/);
[Dungeon World fronts](https://www.dungeonworldsrd.com/gamemastering/fronts/);
[Blades in the Dark clocks](https://bladesinthedark.com/progress-clocks);
[BG3 journal design](https://docs.baldursgate3.game/index.php?title=Journal_Design_Guidelines);
[UESP quest stages](https://en.uesp.net/wiki/UESPWiki:Style_Guide/Quest_Layout).

---

## 5. Splitting the work across agents — second pass

Checked against what has been measured (2026-09-08). Anthropic's own account of its
multi-agent research system found the gains on *breadth-first* work, where subagents
explore independent directions, and warned that the pattern suits coding poorly where
agents must share context or the pieces depend on each other — the token cost runs
around fifteen times a single agent's. The parallel-coding-agent reports converge on
three rules: one worktree per agent, nothing merges until the suite passes in that
worktree (one team measured an 80% drop in "the agent broke something"), and agents
fail where they cannot see what else changes when they change a thing — lineage and
contracts, not files.

That changes the first draft in four ways.

**1. A walking skeleton before any parallel work, by one agent.** The first draft
fanned four builders out against a prose schema. The engine pieces — the loader,
salience, the silent rule, news — are one coupled thing, and four agents building
against a document each read differently is the integration failure the reports
describe. So one agent first builds the thinnest end-to-end slice: one scheme
document, one step, one criterion, one action (move a person), the silent rule,
provenance on the turn log, and "The lost thing" playable in tests. That slice *is*
the contract, and it is executable.

**2. The contract is tests, not prose.** Before the skeleton, one agent writes the
failing tests from the plan — each docstring naming the defect it prevents, the repo's
rule — and a second, adversarial, writes the tests that should *refuse*: a step no
player can change, a twist with no foreshadowing, a criterion in prose, a number on a
reward, a leak to the narrator. The skeleton makes the first set pass and the refusals
hold. Builders later read tests, which cannot be read two ways.

**3. Parallel only where genuinely independent.** After the skeleton, three agents in
worktrees, with a file-ownership map so no two touch one module:
- the **chooser** and NPCs bench (`rules/bestiary.py` search, a new `rules/npcs.py`,
  the bench) — depends on nothing in the engine;
- the **wanted** state and its two readers (`rules/states.py`, the gate in
  `rules/engine.py`'s travel, pricing) — depends on the tag vocabulary only;
- the **author** writing "A Small Favour" as a document against the skeleton's grammar,
  with a scheme-lint pass of its own.
The engine's breadth — criteria kinds, news, the three tells — stays with the skeleton's
agent, serially, because it is the coupled part.

**4. Critics are separate agents with one lens each, and they gate.** Fairness (reach
the framing without the foreshadowing), leak (read every brief across a playthrough for
a fact the character cannot hold), and three-laws (grep for a string match on a
condition or a number added outside the funnel). A finding returns to the owning
builder, never to the orchestrator to patch.

**The orchestrator builds nothing.** It sequences, merges only worktrees whose suite is
green, and runs the whole suite after every merge — not once at the end. Then one
playtest agent with the browser and the real model plays both worlds and reports
transcripts and timings, and one ship agent does the build, the proof and the record.

**Scale.** About nine agents across five phases, inside this repo's guideline of
fifteen, and the token cost is real: this is worth it because the phases are gated by
verification rather than by a plan nobody re-reads. Whether to run it as an orchestrated
workflow is the table's call, and the skeleton is worth reading before the rest start.

Sources: [Anthropic, How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system);
[Anthropic, When to use multi-agent systems](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them);
[5 lessons from running coding agents in parallel](https://dev.to/battyterm/5-lessons-from-running-ai-coding-agents-in-parallel-53on);
[Coherence through orchestration, not autonomy](https://mikemason.ca/writing/ai-coding-agents-jan-2026/).


---

## 6. The final plan (supersedes §1–5 where they differ)

Decided 2026-09-08: phases 1 and 2 built by one hand; phases 3 and 4 with agents.

### 6.1 What a scheme is

An authored, world-agnostic document that runs a story the world does to the player
while the player does their own thing. It opens visible quest cards the player
believes and secret cards the GM alone holds; it advances by storylet steps chosen by
salience; it ends in named outcomes that are effects. It is grounded at open by
filling slots from the world's real people, places and goods; it never names a
stranger and never authors a number. The narrator is told only what the character
could know.

### 6.2 The document

```
{
  "id": "a-small-favour", "title": "A Small Favour", "about": "…bench only…",
  "slots": {
    "giver":   {"role": "trader|fixer", "level": "pc", "prefer": "cast"},
    "victim":  {"role": "standing", "against": "$patron.wants"},
    "patron":  {"faction": "conflict"},
    "captain": {"role": "guard officer", "level": "pc+1"},
    "witness": {"role": "companion", "prefer": "opening"},
    "market":  {"place": "market"}, "lodging": {"place": "lodging"},
    "wild":    {"place": "wild", "hours": 3}, "gate": {"place": "gate"},
    "errand":  {"item": "ingredient", "biome": "$wild"}
  },
  "cards": [ {"id": "errand", "kind": "quest", "title": "Fetch $errand for $giver",
              "objectives": ["Reach $wild", "Gather $errand", "Return to $giver"],
              "giver": "$giver", "reward": "a season's custom at cost"},
             {"id": "plan", "secret": true, "title": "$giver's plan",
              "facts": ["$giver is paid by $patron to see $victim dead and an outsider blamed."]} ],
  "grants_on_open": [{"to": "pc", "tags": ["knows.giver-uneasy"]}],
  "steps": [ … see 6.4 … ],
  "outcomes": { "betrayed": {...}, "exposed": {...} },
  "fairness": {"twist": "guards", "needs": ["knows.giver-uneasy", "knows.victim-named"]}
}
```

Validated on save with the fix named: every slot has a filler rule; every `$name`
resolves to a slot; every criterion is a tag query, a registered event, a place test
or a clock test; every action is in the vocabulary; every step has at least one
player-changeable criterion; every twist lists foreshadowing tags; no digit in any
prose field; every outcome's grants are vocabulary tags.

### 6.3 Slots and the chooser

Filled once at open, frozen on the instance, saved with the campaign beside `founded`
and `cards`. Roles: the world's cast first (role words in `play.cast[].role` and the
character's facts), then the bestiary by role words and challenge rating with sources
ranked NPC Codex / Inner Sea NPC Codex, Villain and Monster Codex, adventure paths
name-stripped, the three townsfolk as the floor; tiered duplicates collapsed and used
as a level ladder. The chosen block for a world character is kept on the NPCs bench
(`homebrew/npcs/<entity>.json`) so the same person has the same numbers next time and
can be corrected. Places by kind from `places.for_scene` (market, lodging, gate, road,
wild — a lodging is minted under the giver's place through the founding door if the
settlement has none). Items from the ingredient list by biome. Factions from
`play.conflicts`, whose `wants`, `works_by`, `holds` and `undone_by` become objectives
in the endgame.

### 6.4 Steps, criteria, salience, actions

A step: `{"id", "criteria": [...], "action": {...}, "tell": {...}, "once": true}`.

Criteria (all engine-measurable, none prose):
- `at($slot)`, `not at($slot)`, `left($slot)`, `arrived($slot)` — the player's place;
- `has($who, tag)`, `not has($who, tag)` — `has_state` on the pc or a slot;
- `since(open|step-id) >= Nh`, `clock >= N` — time;
- `event:<name>` — a registered engine event (objective done, item gained, travel,
  fight ended, talk with `$slot`), from the same registry the homebrew rules keep;
- `alive($slot)`, `present($slot)`, `holds(pc, $item)`.

Selection: on every tick (turn end, travel arrival, clock advance) every step of every
open instance whose criteria all hold is a candidate; most criteria wins; ties by
authored order; one step per tick. Deterministic, seeded, testable.

Actions (existing vocabulary only): `move($who, $place)`, `hide($who)` (a `state.hidden`
effect), `kill($who)` off-stage, `bring_in(role, count, side)`, `open_card`,
`fact(card, text)`, `objective(card, n)`, `reveal_objective(card, text)`,
`resolve(card, how)`, `grant($who, tags|effect)`, `news(...)` (6.5), `outcome(name)`.

Tells: every fired step is an `Outcome` with provenance `scheme:<id>/<step>` on the turn
log. Visibility is decided by the silent rule (6.5).

### 6.5 Out of sight, and news

A step that fires where the player is not says nothing to the prose. Its tell goes to
the log and to the secret card (the GM's alone); the narrator may let the world
behave accordingly but may not state it. Three authored exceptions: `perceptible`
(criteria put the player within sight or earshot), `deferred` (a later step with the
player present carries it), `teller` (a person on the board says it when spoken to).

News: `{"carrier": "letter|courier|crier|notice|gossip|kin|invitation", "reach":
"kin|town|region", "delay": "1d", "says": "…no more than the carrier could know…"}`.
Arrival is itself a step with criteria (delay elapsed, player at a reachable place,
for gossip a person present who would have heard, for an invitation `knows.pc-name`
held by the kin). It fires as an object or a person in the scene and grants
`knows.<fact>` through the applicator. Gossip may be wrong. News opens choices: the
invitation opens the funeral as a storylet with a place and a window.

### 6.6 Outcomes, rewards, consequences

Effects through the one applicator with source `scheme:<id>/<outcome>`: purse credit,
stock item, a founded and held place, a companion, `award_story("new")`, `attitude.*`
regard on people or a faction's people; and the consequences `state.wanted.<town>`,
`state.suspected.<town>`, regard lowered, a place closed. Two new readers make the
wanted state bite: travel through a gate refuses (with the fix named: leave by another
way, clear the name), pricing and the merchant gate ask `has_state`, and guards join a
fight against the player through the existing join-fight door. Clearing the name
removes the one effect and every bite evaporates.

### 6.7 Fairness

A twist step names the `knows.*` / `situation.*` tags the brief must have carried
before it may fire; the validator refuses a scheme without them; the engine skips a
twist whose tags are not held and logs why. `grants_on_open` is how the giver's unease
reaches the brief on turn one.

### 6.8 What the player and the GM see

The Quests tab shows visible quest cards only. A GM-only Schemes view (behind the
Rulesets bench, off by default) lists open instances, filled slots, fired steps and
why — for the table's own debugging, never the narrator's brief. The brief gets the
visible cards as today and the secret cards marked as the GM's alone.

### 6.9 Where schemes come from

`content/schemes/` ships "The lost thing" and "A Small Favour". The Schemes bench edits
them with pickers for roles, places, criteria and actions (the race editor's idiom:
nothing typed but names and sentences). Later, `play.schemes[]` in the World Bible
export. Never the watcher.

### 6.10 Build order and who builds

Phase 1 (one hand): the contract as tests — the passing set and the refusal set.
Phase 2 (one hand): the walking skeleton — loader, validator, slot filling for places
and items, one role via the townsfolk floor, salience, `move` / `hide` / `fact` /
`objective` / `outcome`, the silent rule, provenance, persistence, "The lost thing"
playable in tests and at the table; then, serially, the remaining criteria kinds, the
three tells, news.
Phase 3 (agents, worktrees, file-ownership map): the chooser and NPCs bench; the wanted
state and its readers; the author of "A Small Favour" with a lint pass.
Phase 4 (agents): fairness critic, leak critic, three-laws critic; then the playtest
agent in both worlds with the real model; then the ship agent.
Merge rule: green suite in the worktree, whole suite after every merge.

### 6.11 Costs, stated

No cost at play for authored schemes. Development is the chooser, the grammar, the
engine slice, two readers, the bench, and two lines played twice. Hidden state grows;
the log and the Schemes view keep it legible. Authoring a scheme is a few dozen lines
with conditions; the validator's counting rules catch the worst mistakes. The watcher
authoring schemes stays refused until the authored ones have been played enough to
know what a good one looks like.

---

## 7. Built (2026-09-08)

**Phases 1 and 2, one hand.** `tests/test_schemes.py` is the contract: nine passing
tests and five refusals. `rules/schemes.py` is the skeleton: the document loader over
`content/schemes/` and `homebrew/schemes/`; the validator with the fix named; slot
filling — places by kind from the places module, the wild place as the settlement's
region, items by the wild ground's biome from the ingredient list, people from the
world's own cast at this location with the townsfolk floor as their block; the criteria
grammar (`at`, `left`, `arrived`, `has`, `since`, `clock`, `event`, `alive`, `present`,
`holds`); salience selection, one step per tick, most criteria wins; the actions
`move`, `hide`, `kill`, `bring_in`, `fact`, `objective`, `reveal_objective`, `resolve`,
`grant`, `news`, `outcome`; the silent rule with perceptible tells as outcomes and
silent ones on the instance and the secret card; news with a carrier, a reach and a
delay that never lands on the tick it was born; outcomes as effects with source
`scheme:<id>/<outcome>` and the story award. The engine ticks schemes after every
resolved batch (`Engine._tick_schemes`), instances persist on the scene beside
`founded`, a GM-only view sits behind the `gm_view` house rule, and the Quest schemes
bench lists and validates what ships. "The lost thing" ships and plays end to end in
tests: found, twist, returned, given away, the rival coming to town unseen, the gossip
arriving next tick.

Measured on the way: the give op's effect names the taker as `ref` under kind `give`,
not the shape the first reader guessed; news with no delay arrived on the same tick
as the step that made it, which read as one event, so word now takes at least a beat.

---

## 8. "A Small Favour", as authored (2026-09-08)

Written against the §6 grammar as it shipped in §7, by the author agent of §6.10 phase
3, with `rules/schemes.py` untouched. Five linked schemes in
`content/schemes/a-small-favour.json`, checked as documents and played in
`tests/test_a_small_favour.py`, linted by `tools/scheme_lint.py`. Each scheme opens on
a tag the one before it granted, so the line is five storylets that interlock rather
than one script, and a later scheme can open on any path that grants its tag.

**Q1 `a-small-favour` — the errand.** Opens at the market after a day of the campaign
(the first draft opened on `at($market)` alone, which put a second quest card on the
table in the first tick of every lost-thing test; the day is also a fair pacing: the
favour is asked of a face the market has seen). Slots: giver (trader, at the market),
victim (standing, at the market), witness (companion, at the market), captain (guard
officer, at the gate), patron (a faction from the conflicts), market, lodging, gate,
road, wild (three hours), errand (an ingredient of the wild ground's biome). The visible
card is the errand in three objectives; the secret card is the giver's plan. The unease
is granted at open. Steps: the witness's aside names the victim on the open tick where
the player stands (perceptible; it is the second fairness tag); the giver shuts the
stall and hides at the lodging once the player has left the market and an hour has
passed (silent); reaching and gathering tick the objectives (perceptible); with the
giver hidden three hours and the player not at the lodging, the victim is brought
there and killed off-stage, a fact goes to the secret card and gossip is queued for the
town two hours on (silent); a player who walks into the lodging after that finds the
body (perceptible, no twist); back at the market holding the errand with the victim
dead, the captain comes up from the gate with two guards, the errand card fails with
the guards' words on it and `betrayed` grants `state.suspected` and `knows.betrayed`
— gated on `knows.giver-uneasy` and `knows.victim-named` being held; reaching the
lodging while the giver is hidden and the victim alive is `exposed`: the giver bolts for
the road, the victim's regard rises, `knows.giver-to-find` opens Q3 early. Back within
the hour, nothing fires: measured in the test, the fired set is the witness's aside
alone and the giver is at the stall unhidden.

**Q2 `wanted`.** Opens on `knows.betrayed`; grants `state.wanted` at open. Two visible
cards at once: clear your name (three clues, any two) and leave by the road. The notice
at the market and the shut gate are perceptible where the player stands. The witness's
word is a teller at the lodging; the ledger is in the giver's empty room; the coin is
on the body laid out at the temple. "Any two of three" is three steps, one per pair,
all firing the one outcome `two-clues`, which grants `knows.giver-to-find`. The witness
also offers the way past the gate (a fourth criterion, so by salience it fires the tick
after the word, before the ledger — measured); going out by the road with it is `fled`,
which costs the captain's regard.

**Q3 `the-one-who-paid`.** Opens on `knows.giver-to-find` from either Q1's `exposed` or
Q2's `two-clues` (an OR the grammar cannot write, done by having both grant the same
tag). The giver is at the wild place: found, then named (the patron), then — still alive
and in your keeping an hour on — `taken`, with `attitude.friendly` on the giver and
`holds.debt.giver` on the pc; dead at the wild place after being found, `loose-end`.

**Q4 `the-patron`.** Opens on `knows.patron-named`. The faction's house is the guildhall;
an envoy speaks for it, the captain is at the market, the victim's kin beside. Books,
then the proof (a fact and `knows.proof-held`), then `justice` at the market with the
captain present (story award, captain helpful, kin friendly, `knows.name-cleared`,
`knows.patron-ended`, `holds.place.kin-house`), or `bargain` by handing the envoy
anything (`event:give($envoy)`; suspected, captain unfriendly), or `failure` when the
proof has sat three days or five days pass without it (silent; `knows.patron-unbeaten`).

**Q5 `the-price-on-your-head`.** Opens on `knows.patron-unbeaten`. Two waves of hunters
brought in where the player stands, away from the market and the gate, at two days and
then three more, each wave broken by `knows.name-cleared` or `knows.patron-ended`;
outcomes `cleared`, `ended`, and `gone` (fled the town and a week away from its places).

**What the lint found.** On the line: nothing, after two rounds. On the way there: the
validator's twist heuristic matched `kin` inside "looking" and `lie` inside "lies dead"
and refused two innocent tells as unforeshadowed twists (reworded; the heuristic wants
a word boundary). On "The lost thing": `$market` and `$wild` are filled and never named
in a tell, which the lint reports (the file is not this author's to edit). The lint's
authoring rules beyond the validator: fairness tags supplied by the open, an earlier
step, or another scheme in the set; every slot named in a tell; every outcome fired by a
step; every non-secret card touched by a step or an outcome; `since(<step>)` naming a
real step; a scheme that opens on a `has(pc, …)` tag nothing in the set grants.

### 8.1 Grammar gaps, for the engine agent

What the plan asked for, what the grammar could not say, and what was written instead.

1. **Slug-bearing tags.** The plan wants `state.wanted.<town>` and
   `state.suspected.<town>`; a grant's tag is refused if it carries `$town` and no slot
   kind yields a settlement slug. Written: the family roots `state.wanted` and
   `state.suspected`. The *query* side is not a gap — `has(pc, state.wanted)` matches
   any `state.wanted.<x>` by dot-boundary prefix (`states.matches`), so Q2 may keep
   opening on the family once the grant is fixed. Needed: a `$town` (or `$here`)
   placeholder in grant tags resolved at fill time to the settlement id, or a `place:
   settlement` slot whose id is usable in a tag. xfail: `test_the_suspected_state_names_the_town`.
2. **No removal action.** Nothing in the vocabulary lifts an effect, so `justice`
   cannot remove `state.wanted`, `bargain` cannot soften it to suspected, and Q5's
   "until the name is cleared" is a tag (`knows.name-cleared`) rather than the effect
   going. Needed: `{"do": "ungrant", "to": "pc", "tags": [...]}` through the one
   applicator (remove by tag, any source). xfail: `test_justice_lifts_the_wanted_state`.
3. **Slots are per instance.** Q2's giver, victim, witness and captain are filled fresh,
   not Q1's people: the ledger names a stranger, the body at the temple is a living cast
   member stood there, the captain who arrested you is not the one you clear your name
   with. Needed: a slot spec `{"from": "a-small-favour.giver"}` that copies the earlier
   instance's filled slot (and refuses to open if that instance does not exist). xfail:
   `test_the_later_schemes_share_the_errands_people`.
4. **`opens` is a conjunction.** Q3 opens on Q1 `exposed` *or* Q2 `two-clues`; written
   by both outcomes granting one tag. Fine as a convention; note it in the bench.
5. **`road` fills to the gate.** `PLACE_KINDS["road"]` is `("the gate",)`, so `$road`
   and `$gate` are one place, Q2's "leave by the road" fires at the gate, and Q5's
   "not at the gate" also means "not on the road". Needed: a road place of its own,
   or the first place of the region set.
6. **No "since the player left".** `since(open|step)` only; the honest path "return
   within the hour" is written as `since(open) >= 1h` on the giver's hiding, and the
   wild being hours away means any player who does the errand triggers it — which is
   the plan's intent, but a player who dawdles in town an hour and then leaves also
   does. Needed: `since(left($place))`, or `left($place)` recording its clock.
7. **No day unit on `since`.** `since(...) >= 48h`, not `2d` (news `delay` takes `d`).
8. **No repeat interval.** Q5's waves are two authored steps; a `once: false` step with
   `since(open)` would fire every tick. Needed: `since(self) >= Nh` for a repeating step.
9. **`bring_in` has three templates** (watchman, thug, guildhand): a "hunter" is a
   guildhand. Needed: the codex chooser by role word, biome and level (§6.3).
10. **Faction fields are not addressable.** `$patron` fills to the name; `wants`,
    `works_by`, `holds`, `undone_by` are on the filled slot but `fill_text` cannot reach
    them, so Q4's objectives say "what $patron holds" in general words. Needed:
    `$patron.holds` in `fill_text`.
11. **No grant to a faction's people or the town.** `attitude.*` is granted to one slot
    actor; "regard from the town" and "the Patron's regard rises" are written as the
    captain's regard and a `knows.patron-owes-you` tag on the pc.
12. **No founding from a scheme.** "The victim's kin grant a house (founded and held)"
    is a `holds.place.kin-house` tag; the founding door is not called.
13. **No companion, talk or surrender event.** "Taken as a companion" is `spared`: the
    giver alive and in your presence an hour after naming the patron. Needed:
    `event:talk($slot)` and a `companion($who)` action.
14. **Cross-scheme cards.** Q3's `loose-end` should close Q2's road card; a scheme
    can only resolve its own cards.
15. **Leaving the region** has no criterion; Q5's `gone` is fled-town plus a week away
    from the town's places.
16. **`side` names.** The engine's fight sides are `pc` and `them`; the brief said
    `against`, which would make a third side the fight does not read. Written: `them`.
17. **The twist heuristic** in the validator substring-matches `kin`, `lie`, `never`;
    "looking", "lies", "keeping" trip it. A word-boundary match is the fix.

---

## 9. Phase 3 merged, and the gaps closed (2026-09-08)

Three agents in worktrees, each with a file-ownership map, merged in turn with the
whole suite green after each: the codex chooser and NPCs bench (docs/npc-codex.md),
the wanted state with its three readers (docs/wanted.md), and "A Small Favour" as
authored with its lint (§8). Of the seventeen gaps the author named, the ones the
line needed were closed by one hand on the merged tree:

- `$town` is an implicit slot in a tag: `state.suspected.$town` is spelled by
  `states.town_tag` at grant time and never authored.
- `remove` joins the action vocabulary, and an outcome may carry `removes`: justice
  lifts the warrant; a bargain lifts it and lays the lesser one down.
- A slot may be `{"from": "other-scheme.slot"}`: the later quests keep the errand's
  giver, victim, witness, captain and patron rather than minting strangers.
- `since(...)` takes days as well as hours.
- `on_open` actions: the open moves people (the witness goes to ground; the giver
  flees to the wild) without spending the first tick.
- The twist heuristic reads words, not substrings ("looking" is not "kin").
- The gate honours `knows.way-past-gate` on the open road, the way a witness's door
  is meant to, while the arch stays shut.
- The narrated buy and sell pay the wanted price; a GM-declared fight brings the
  guards in as a swing does.

The three strict xfails the author left are passing tests now. `tools/scheme_lint.py`
reports no problems on the shipped content.
