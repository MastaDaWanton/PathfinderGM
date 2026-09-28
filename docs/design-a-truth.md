# Lane A design: the page tells the truth about the engine

Phase 0 research for `docs/fix-plan-2026-09-28.md`, Lane A. Read-only research and design;
no product code was changed. Every number below was measured on the Bobby save
(`%LOCALAPPDATA%\PathfinderGM\campaigns\bobby.json`, 27 transcript beats, 56 turn-log rows),
on the other four saves on this machine (`boop`, `borin-achereth`, `the-great-one`, `zoom`:
32 prose beats in all five), or by calling the current functions on the saved beats. Where a
claim is a design guess and not a measurement it says so.

---

## 1. Items covered

| Item | Defect on the page | Measured cause (this pass) |
|---|---|---|
| 4 | The watchman owed a face only on beat 3 | `_mentions` and `faceless` key a person on the last word of their name. Of the **twelve** opening companions (`play/opening.py`), the last word is the wrong key for **12 of 12** ("through", "you", "door", "table", "step"...); "the old man ahead of you" is keyed on **"you"**, so he is "mentioned" in every beat. `mentions._head` (the attribution's own head finder) is wrong on **10 of 12** because it does not stop at a participle ("waving", "clearing") or an adverb ("ahead") |
| 6 | An NPC's line booked as the PC's `say` | `GMAgent._merge_declared` turns the model's `declared.say` into an intent with the model's words and `because: "the player's words commit the turn to it"`. Across all seven PC `say`s in the five saves, content-word overlap with the player's input is **1.0 six times and 0.0 once** — the one defect |
| 13 | Drenn hailed the player, no conversation opened | `hailed_by` splits into sentences first, then looks for whole quotes in each. On the seven Bobby beats with speech: **20 quotations on the whole beat, 14 found sentence by sentence** (6 lost, 30%); Drenn's beat **2 → 0**. The tag path is inside the span loop, so two correct `to=you` tags were never read |
| 16.3 | The patrol that stopped the player written as background | The travel outcome carries `met: "patrol"` and the tell "You get no further", but no check reads `met`; the prose made it "the watchmen are making their rounds" |
| 16.4 | Leaving narrated as arriving | Move market → the way in (outward); prose: "the gates of Vormoor open to receive you", "the dusty road stretches out behind you". Nothing compares prose direction with the move |
| 16.7 | A described person re-described differently | The brief does carry every present person's face, but labels it "use it when they are first described" — which licenses re-invention after the first. Whether the "older man… broadsword" of beat 10 was c1 or the undescribed patrol guard c6 **could not be settled**: the attribution labelled one of its two mentions "unknown" |
| 17.5 | All moves refused, prose moves the player | Turns 25 and 29: `found` and `travel` both `status: refused`; beat 14 says "You are now on the outskirts". `stands-elsewhere` only knows place nouns; "outskirts" is not one |
| 17.6 | Brief wording pasted into prose | "There is a settlement to the north, reachable by journey: Dustgate." is the ROADS OUT line's shape, not its exact words — it shares no 3-gram with the brief, so an echo index would miss it. The *label-colon-name* shape occurs **2 times in 32 prose beats, both of them this defect** |
| 20.4 | A speaker the prose invented is never made real | Turn 36: `speech-tags` logged `unknown_refs: ["new1"]`, 3 lines, 0 attributed. The man existed as a population record only; he became c8 one turn later, when the player addressed him |
| 21.3 | A player-fixable refusal retried 7 times, then disguised | "cast: Bobby did not prepare Burning Hands today." — **7 of 7** attempts, identical, across two models; then `narrate_only` with "the moment does not answer". No plan could have fixed it: the fix was the player's |
| 21.5 | The false-claim check misread a spell's aim | `_PRODUCE` counts `hands` as a verb ("hands over"), so "cast burning **hands into the** tree tops" is read as producing "a tree tops you do not have". The claim went to the prose as `false_claim_block` and to the heat note; `nobody-reacts` then asked the man to mock "so little fire" |
| 22.4 | A damage roll with no victim narrated as a hit | Outcome: Burning Hands, `targets: []`, `1d4 — 1`, no damage effect on anyone. `contradicts_state` run on the beat finds **nothing**: `_name_stems` drops "man" (three letters), the wound sentences say "he"/"his", and `_WOUNDED` has no burn or impact words |

---

## 2. Prior art per tradition

One sweep (a research agent, primary sources, PDFs read in full where marked), then a spot
check of the two load-bearing quotes against their pages. The repo's own earlier sweeps
(`docs/narrator-guards.md`, `docs/declared-not-guessed.md`) are not repeated; where they
already settled something it is cited as settled.

### Interactive fiction: the report cannot be reached on failure

- **Inform 7, check / carry out / report** (WI §12.9,
  https://ganelson.github.io/inform-website/book/WI_12_9.html; order in §12.2,
  https://ganelson.github.io/inform-website/book/WI_12_2.html). Check rules decide and stay
  silent when they pass; carry out changes the world; report describes what has happened.
  "If any of our checks fail, we should say why and stop the action." (WI §12.9). A stopped
  action never reaches carry out or report — that follows from the processing order in
  §12.2; §12.9 itself does not say it in so many words (the spot check caught the sweep
  overstating this). **The prose that reports a move is structurally unreachable when the
  move was refused, and the refusal is the refusing rule's own sentence.** That is items
  17.5 and 22.4, and it is why the backstop for a refused move is the refusal's sentence.
- **Unsuccessful attempts and responses** (WI §12.5; §14.10–14.11, since 6L02, 2014). A
  failed action is reported by the rule that refused it (`the reason the action failed`),
  and every library message is a named value tied to its rule (`can't go that way rule
  response (A)`). For us: `Outcome.for_a_person` is a response — the refusal's words live
  with the refusal.
- **TADS 3, verify versus check** (http://www.tads.org/t3doc/doc/techman/t3verchk.htm).
  `verify()` stops a command with a *logical* problem; `check()` "is for enforcing conditions
  that aren't obvious to the player" (TADS 3 Technical Manual). Neither may change state.
  The action-results page (http://www.tads.org/t3doc/doc/techman/t3res.htm) ranks
  `illogicalNow` (wrong given the current state — its example is a deflated raft) apart
  from `illogical` (always wrong). This is the nearest documented split to item 21.3's
  "not prepared today" against "no such spell"; it is framed by what the player knows,
  not by who can fix it, and **no source found says a remediable failure should be shown
  rather than retried** — that part is this design's inference.
- **Andrew Plotkin, "These violent delights"** (2022,
  https://blog.zarfhome.com/2022/02/these-violent-delights.html). A default refusal must
  work in any game and should leave other options open; he praises "Violence isn't the
  answer to this one" for scoping itself. Refusals "should be neutral and unassuming in
  tone" (Plotkin). Item 21.3's refusal names the one thing and the one fix.

### Faithfulness checks on generated text

- **RotoWire** (Wiseman, Shieber, Rush 2017, https://arxiv.org/abs/1707.08052), the nearest
  analogue to prose written from tells: records in, summary out. Their *relation
  generation* metric extracts records from the generated text and checks each against the
  table. Best neural model 71.82% of checkable claims correct; a template 99.30%.
- **Re3** (Yang et al. 2022, https://arxiv.org/abs/2210.06774, read in full) keeps a
  per-character **attribute dictionary** and checks each new passage only against it;
  comparing every statement pair gave "a sea of false positive contradictions". Detection
  on 200 controlled pairs: plain NLI entailment ROC-AUC 0.528, near chance; their structured
  detector 0.684. That is item 16.7's shape (slots per person, compared to the held face) and
  its warning (a detector near chance on free comparison).
- **FIREBALL** (Zhu et al. 2023, https://arxiv.org/abs/2305.01528, read): D&D play with real
  game state. No numeric faithfulness score; evaluators' commonest complaint was the model
  **narrating the player's character acting or speaking** (item 6's family), and a
  "hit point reasoning" failure — any damage read as a kill, "regardless of the target's
  true remaining health" (Zhu et al.) — their example kills a dog still at 39/39. Item 22.4
  is the same failure with no target at all.
- **CALYPSO** (Zhu et al. 2023, https://arxiv.org/abs/2308.07540, read): a summarising prompt
  echoed stat blocks into its output despite being told not to. Item 17.6 in another
  system: what is in the prompt leaks through as content.

### Quote attribution and mentions

- **Muzny et al. 2017, the two-stage sieve** (https://aclanthology.org/E17-1044/): quote to
  mention, then mention to entity, sieves ordered by precision; average F 87.5 over three
  novels, 90.4% precision at 65.1% recall in the precise setting.
- **PDNC** (Vishnubhotla et al. 2022, https://arxiv.org/abs/2204.05836): 35,978 quotes in 22
  novels. Explicit quotes are attributed at 0.94–0.96; anaphoric at 0.46–0.48; implicit at
  0.41–0.46. The follow-up (2023, https://arxiv.org/abs/2307.03734) finds quotation
  *identification* over the whole text easy (0.94) and does it first; end-to-end BookNLP
  attribution scored 0.40, and restricting candidates to mentions already resolved to known
  characters raised it to 0.62. **Tags first, whole-text spans, and only registered people as
  candidates** is item 13's and item 20.4's design.
- **Raghunathan et al. 2010, the Stanford sieve** (https://aclanthology.org/D10-1048.pdf):
  mention heads come from the parse, and strict head match also requires word inclusion,
  because "naive matching of their head words generates a lot of spurious links"
  (Raghunathan et al.). Last-word matching is weaker than head matching; the head of "the
  watchman waving traffic through" is *watchman*. Item 4.
- **BookNLP** (https://github.com/booknlp/booknlp) types mentions PROP, NOM and PRON and
  resolves pronouns; the pronoun continuation in `about()` is the cheapest slice of that.
- The repo's own measurement stands: speaker tags taught by the model's own tagged beats
  reached 16 of 20 lines (`docs/declared-not-guessed.md`).

### AI narrator products

- **SillyTavern World Info** (https://docs.sillytavern.app/usage/core-concepts/worldinfo/)
  matches whole words by default; **AI Dungeon Story Cards**
  (https://help.aidungeon.com/faq/story-cards) match substrings and warn: "Be cautious with
  short Triggers that could be part of common words." Item 4's false positive, named.
- **Friends & Fables** (https://fables.gg/blog/introducing-ace-1-the-engine-powering-the-best-ai-ttrpg-experiences)
  moved off updating state from the narrator's response (see section 3).

### Planner retries

- **Huang et al. 2023** (https://arxiv.org/abs/2310.01798, read): self-correction without
  external feedback made answers worse (GPT-3.5 CommonSenseQA 75.8 → 38.1). **Kamoi et al.
  2024** (https://arxiv.org/abs/2406.01297) survey: correction works when the feedback is
  reliable and external. Our refusal *is* reliable and external — and still useless,
  because no plan can prepare a spell. No study was found of retrying when the fix lies
  outside the model's control; the seven identical refusals of turn 48 are the measurement.

### Could not be sourced

Why Inform introduced responses beyond customisation and translation; any primary source
that splitting sentences before finding quotes breaks quote detection (item 13's cause is
this repo's measurement, not the literature's); a numeric faithfulness score in FIREBALL;
Hidden Door's internals (one reviewer's inference only); AI Realm and FactCC (not
researched); whether a failed action should cost a turn (Inform's every-turn rules still
run after a failed action according to secondary handbook material, not confirmed against
WI).

---

## 3. Tried and abandoned, and why

- **Re3's Edit module — dropped by its own authors.** Removing it changed nothing
  significantly in ablation, and the successor DOC (https://arxiv.org/abs/2212.10077)
  removed the editing step. A whole-passage "make it consistent" repair does not hold; every
  repair here is one sentence with the fact named, re-checked, cut on failure (the shape of
  `_repair_state_claims`, which cites RARR).
- **Plain NLI (0.528 in Re3) and all-pairs checking (a sea of false positives)** — not
  adopted; closed slots against the one held face, and engine records.
- **"One speaker per paragraph"** in older quote corpora — Muzny et al. call it wrong for
  novels with real conversation and report it only for comparison. `hailed_by` must not give
  every quote in a stretch to one speaker; tags are per line.
- **Deriving state from narration** — Friends & Fables moved off it (duplicates, updates at
  the wrong moment), and this repo ruled the same on 2026-09-27. Item 20.4's embodiment is
  therefore narrow: a speaker addressing the player, matched to a record, through the one
  door — and it needs the owner's word (section 9).
- **Substring triggers** — AI Dungeon warns against them; SillyTavern made whole-word the
  default. Last-word matching is a substring trigger with extra steps.
- **Aaron Reed's Smarter Parser** cut its "overly ambitious" guesses (every -ly word as an
  adverb) to a fixed list and spun noun-specific rules off to another extension (Reed's
  own update post, https://intfiction.org/t/major-smarter-parser-update/3342). The lexicons
  in this design are closed lists of verbs, for the same reason. Whether the extension was
  formally abandoned could not be confirmed.
- **Custom Library Messages** became obsolete when Inform built responses in (forum
  summaries, not a release note): refusal wording belongs with the refusal.
- **CALYPSO's summarisation prompt** was replaced after it echoed stat blocks despite being
  told not to. Item 17.6 is detected in code, not forbidden in the brief.
- **Telling the model not to.** The brief already listed the places that exist; the tell
  already said "You get no further"; the prose went its own way both times.

---

## 4. Recommended design per item

The house shape throughout: **detect in code, repair with one targeted call naming the fact,
deterministic backstop last.** Three items are not prose checks — the cause is upstream (6,
21.3, 21.5), and the fix stops the wrong thing being written. Measured targets are in
section 8.

Two shared pieces, in a new Lane A module `gm/checks/_people.py`:

- **`head_of(name)`**: the first person word in the name (the attribution's
  `_PERSON_WORDS`, the scene's templates, the world's `play.races[].name`); else the word
  before the first boundary — a preposition or adverb of place (`at, with, beside, behind,
  ahead, near, through…`), a relative (`who, that`), or an `-ing`/`-ed` word after the first
  noun. The boundary rule alone gets 12 of 12 opening companions right. A proper name keeps
  its own words. `mentions._head`, `judgement._mentions`, `narration.faceless` and
  `narration._name_stems` all call it — every copy of the rule.
- **`about(ctx, ref)`**: the sentences the attribution gives to a ref, plus a **pronoun
  continuation** — a sentence whose subject is a third-person pronoun inherits the previous
  sentence's one attributed person when the pronoun family matches theirs. Code only. This is
  the gap that hid 22.4 ("the heat licks across **his** face").

### Item 4 — mentions by head noun, never the last word

- **Detect.** `_mentions(beat, name)`: the attribution's answer when it has one; else the
  whole name, a proper name's words, or `head_of(name)`. `faceless` uses the same head;
  `settle_descriptions` gains `attribution=None`.
- **Repair / backstop.** Unchanged (`place_the_face`, the world's own line) — but on the beat
  the person is first used.
- **The opening** never runs `settle_descriptions`, so the one person every campaign meets
  first is never owed a face. The aftermath registry runs on the opening beat too (S3 or
  Lane C). Item 4b is Lane C's; this works with or without it.

### Item 6 — a `say` whose words the player never wrote is not the PC's

- **Detect** (`judgement.own_words_only(raw, player_text, reading)`, last in `plan_turn`'s
  chain): content-word overlap of each PC `say`'s words with the player's text; threshold
  0.5 (measured bimodal, 1.0 or 0.0).
- **Repair, deterministic.** Below it, the words become the reading's `says`, else
  `spoken(player_text)`, else the `say` is dropped and logged. `_merge_declared` stops minting
  a `say` with the model's own words. Not a prose check: once the tell says "Bobby speaks…",
  the page can only be right by luck.

### Item 13 — hails: tags first, spans on the whole beat

- **Detect.** (1) Every `said` record on the page with `to == "you"` and `who` a living non-PC
  is a hail — no spans needed. (2) For untagged lines only: spans over the whole beat, each
  read with the narration of the sentences holding its opening and closing marks (on
  `speech.blanked`, which keeps offsets), then the existing name/role match.
- **Every copy.** `narration.introduced_by._tagged` moves to the same context
  (`_people.spans_in_context`, since `speech.py` is Lane F's). Grep found no other
  sentence-first span reader. No backstop needed: the tag is the declaration.

### Item 16.3 — a stop is a stop (`gm/checks/stop_shown.py`)

- **Condition.** A move whose biome effect has `met != ""` or `stopped_short`.
- **Detect.** (a) A `met_refs` person acts on the player — a sentence `about` them with a
  closed-list stopping verb (stop, block, bar, halt, step into your path, question, look you
  over) or a line tagged to them; habitual framing ("making their rounds") does not count.
  (b) When `stopped_short`, `stands_elsewhere` with `here` = the place actually reached.
- **Repair.** One rewrite naming the meeting in the tell's words, happening to the player now.
- **Backstop.** The engine's own meeting sentence (`ontheway.describe`) inserted after the
  arrival sentence.

### Item 16.4 — leaving is never narrated as arriving (`gm/checks/direction.py`)

- **Needs** `direction: "out" | "in" | "along"` on the biome effect, from place tiers (Lane B).
- **Detect.** On `out`: the settlement (its own name, its scale word, or `town, village,
  city, gates, walls`) receiving the player — `open to receive/admit you`, `welcome you`,
  `you enter / arrive in / step into`; a road or path `behind you`. On `in`: `leave
  <settlement> behind`.
- **Repair.** One rewrite naming from, to and direction. **Backstop.** Cut the sentences; the
  tell already says where they are.

### Item 16.7 — a described person keeps their face

- **Brief** (`gm/brief/faces.py`): for everyone present and `described`, "ALREADY DESCRIBED
  — keep to it:" with the sentence the page first described them in (new
  `Actor.described_as`) and the held appearance. Showing the sentence is demonstration.
- **Detect** (`gm/checks/face_kept.py`): closed slots on sentences `about` a described person
  — people (the world's race names), age band, hair (bald against a colour), what they carry
  (`state_claims`' wielded check). An unfilled slot is never a contradiction; a new detail is
  drift and is not flagged.
- **Repair.** One sentence rewrite. **No backstop**, as `_repair_misnamed` has none: the flag
  rests on the labeller, and a wrong swap writes a wrong face.
- **Honest limit.** Beat 10's "older man… face like cracked leather" contradicts no slot of
  c1's or c6's face; only "broadsword" is checkable. Here the brief is the fix.

### Item 17.5 — refused moves shown as refused (`gm/checks/refused_move.py`)

- **Condition.** No move changed the place, and a move was refused or the reading had a
  `go`/`leave` act. Highest priority: every later turn resolves from where the engine is.
- **Detect** (narration only). Second-person displacement: `you (are|stand|find yourself)
  (now )?(on|at|in|outside|beyond)` + not the current place; `you (reach|arrive|emerge)`;
  `you (walk|head|set off|make your way|leave|turn your back on)` with a directional
  complement. Hedged, future and question forms do not count.
- **Repair.** "The player did not move: <refusal>. They are still at <here>."
- **Backstop.** Cut from the first move claim on (`hold_the_door`'s shape) and append
  `for_a_person`. Today's refused-move tells are written for the planner ("The kinds are:
  arena, back streets…") and cannot stand on the page.

### Item 17.6 — brief wording kept out of the prose (`gm/checks/brief_verbatim.py`)

- **Detect.** (1) The label-colon shape in narration — a lowercase label, a colon, then one or
  more capitalised names and a full stop (2 hits in 32 beats, both the defect). (2) A 4-gram
  of a brief section's registered **scaffold** (its fixed words, values masked). The world's
  own sentences are not scaffold.
- **Repair.** Through `polish`, naming the phrase. **Backstop.** Cut the sentence.

### Item 20.4 — a speaker the prose introduces is made real (aftermath `speaker_real.py`)

- **Detect.** A line on the page whose tag named nobody here (`said` with empty `who` and a
  `was`), or an untagged line to the player whose guess finds nobody.
- **Resolve.** The description mention with no ref in that context is matched to the
  population record this beat wrote; that person walks on through S4's arrival door (a
  square — item 14) wearing their rolled face, the `said` record is re-tagged, and the hail
  opens the conversation.
- **Otherwise** a finding, "a line with no speaker", rewritten to someone present or to
  crowd noise. In a fight `_undeclared_arrivals` stands.
- **Needs the owner's ruling** (section 9): this is a body from prose.

### Item 21.3 — a player-fixable refusal goes to the player once

- **Detect.** `IntentError.fixable_by: "player" | "plan"` (default `"plan"`); `"player"` where
  only the player can change the fact (not prepared, no slots, not in the book, level or
  ability out of reach, no such weapon, not your turn, out of reach). In `plan_turn`, such a
  refusal on a PC intent whose op the player declared ends the loop at once.
- **The player gets** `TurnPlan.refusal = {"text", "code", "fix"}` and a `narrate_only` plan:
  no second model, no "the moment does not answer", no false claim. Lane E renders a plain
  `refusal` beat with the fix button.
- An op the player never declared (the model invented it) is dropped instead, and the loop
  goes on.

### Item 21.5 — a spell's aim is not a possession claim

- **Fix, deterministic.** `false_possession` masks every spell name the PC can reach
  (`casting.known_spells`, and the reading's `cast` object) before `_PRODUCE` scans. The
  plan's "nobody-reacts skips cast" treats the symptom: the heat note and
  `false_claim_block` both came from this claim.

### Item 22.4 — no victim for an empty roll (`gm/checks/empty_roll.py`)

- **Condition.** An outcome with a damage roll and no victim (`targets == []`, no `damage` or
  `condition` effect on a ref other than the caster).
- **Detect.** For each non-PC not harmed this turn, `about` sentences with harm words by the
  damage family: fire (burn, scorch, sear, singe, blacken, soot on a body), impact (thrown
  back, hits the ground), generic (wound, bleed). The same linker and lexicon go into
  `contradicts_state`; the registry drops a duplicate finding on one sentence.
- **Repair.** "The spell reached nobody; <name> is untouched." **Backstop.** Cut the sentences
  and add Lane E's no-victim sentence. The burning ferns are Lane E's hazard rules.

---

## 5. What the Phase-1 seams must provide

### `BeatContext` (S1)

| Field | Type | Exists in the plan? | Used by |
|---|---|---|---|
| `text` | `str` | yes | all |
| `player_text` | `str` | yes | 17.5, 6 |
| `scene` | `Scene` | yes | all |
| `outcomes` | `list[Outcome]` — **all** of `resolution.outcomes`, refused and tell-less included | yes (say "all") | 16.3, 16.4, 17.5, 22.4 |
| `reading` | `dict \| None` | yes | 17.5, 21.5 |
| `brief_facts` | `list[str]` | yes | — |
| `said` | `list[dict]` — `speech.lift` records for this draft | **add** | 13, 20.4 |
| `attribution` | `mentions.Attribution \| None` | **add** | 4, 16.3, 16.7, 22.4 |
| `brief` | `str` — the whole brief as sent | **add** | 17.6 |
| `scaffold` | `frozenset[tuple[str, ...]]` — 4-grams of registered brief scaffold | **add** | 17.6 |
| `here` | `str` — the place's name now | **add** (from `engine.here()`) | 16.3, 17.5 |
| `settlement` | `str` — the settlement's name and its scale word | **add** | 16.4 |
| `door` | `"turn" \| "consequence" \| "npc" \| "opening"` | **add** | gating |
| `in_fight` | `bool` | **add** | gating |

Member module shape (S1): `ORDER: int`, `KIND: str`, `WEIGHT: int`,
`DOORS: frozenset[str]`, `find(ctx) -> list[Finding]`, optional
`backstop(ctx, text) -> tuple[str, list[str]]`. `Finding` gains `sentences: list[str]` (the
spans flagged, so the repair edits only them). The registry drops a finding whose sentences
are all already flagged by a heavier one. Truth findings are repaired sentence by sentence
by one agent method (`GMAgent._repair_sentences`, Lane A), in the shape of
`_repair_state_claims`: rewrite with the fact named, re-check, cut on failure, then the
member's backstop.

**Order matters, and the attribution must exist before the checks.** Today
`mentions.attribute` runs in `_groom` *after* `polish`. The truth checks need it before. S1
should build `BeatContext` after the attribution call and run the truth members in a second
review pass after `polish` — or move the attribution before `polish` (one more ~1 s call on
beats the polish then rewrites). This is the one seam decision this lane forces.

### Brief sections (S2)

- `gm/brief/faces.py` — ALREADY DESCRIBED, as above.
- Every section module declares `SCAFFOLD: tuple[str, ...]`, the fixed words of its lines.

### Aftermath steps (S3)

- `speaker_real.py` (item 20.4): after `record_people`, before the hails.
- S3's hook must sit **before** the inline `hailed_by` call (views ~2112), or the hails move
  into the aftermath as a step, so a speaker made real can be hailed on the same beat.
- The `settle_descriptions` call gains `attribution=getattr(agent, "attribution", None)` —
  an S3 edit, since `views.py` is Lane E's in Phase 2.
- The aftermath runs on the **opening** beat too (item 4).

### Persisted fields (S4)

- `Actor.described_as: list[str]` — at most two sentences, the page's first description.
  Default `[]`.
- `said` records may carry `"made": ref` when a speaker was made real. No migration.

### Outcome and effect fields the engine must emit

| Field | Where | Owner |
|---|---|---|
| `met: str` (exists), `met_refs: list[str]`, `meant_for: str`, `stopped_short: bool` | the biome effect of `travel`, `venture` (journey has `stopped_short` already) | B |
| `direction: "out" \| "in" \| "along"` | the biome effect of every move | B |
| `Outcome.for_a_person: str`, `Outcome.fixable_by: str` | `_refuse` and every refused outcome | register; `_refuse` is unowned |
| `IntentError.fixable_by: str`, `IntentError.fix: dict \| None` | `_check_cast` and the other PC-resource refusals | E (cast branch), register for the rest |
| cast `targets`/`caught: list[ref]`, one `damage` effect per victim with `ref`, `reached_nobody: bool` | `_op_cast` | E |

### API payload keys

- `/api/say` and `/api/cast` responses: `refusal: {"text": str, "code": str, "fix":
  {"kind": "prepare", "spell": str} | null}` when a player-fixable refusal ended the turn.
- Transcript beat kind `"refusal"` (plain text, never fed back as the narrator's own prose:
  `own_prose` reads `setup` beats only, so it is excluded already).

---

## 6. Owned edits: the Lane A list, confirmed and amended

Confirmed: `judgement.hailed_by`, `_mentions`, `settle_descriptions`; `agent.plan_turn`'s
retry loop; the new check files; `gm/brief/faces.py`.

Amended:

- **Add** `judgement.false_possession` (item 21.5's real cause). **Drop** "the nobody-reacts
  check skips interpreter-read cast acts" — it treats the symptom.
- **Add** `agent._merge_declared` and a new `judgement.own_words_only` (item 6).
- **Add** `narration.faceless`, `narration._name_stems`, `narration.contradicts_state`,
  `narration.introduced_by` (every copy of the last-word and per-sentence rules).
- **Add** `gm/mentions.py: _head` (and, if S1 does not move it, where `attribute` is called).
- **Add** `agent._repair_sentences` (new) and the `_groom` call sites for the truth pass.
- **Add** `rules/engine.py: _refuse` — one door, not owned by B or E; either the register
  gives it to Lane A or S4 adds the fields in Phase 1.
- **Rename** `empty_roll.py` to cover harm-without-victim; `speaker_real.py` is an
  aftermath step, not a check.
- New helper module `gm/checks/_people.py` (`head_of`, `about`, `spans_in_context`).

Seen, not ours (Lane F, `speech.spans`): "the trees' teeth" inside a single-quoted line
closed the quotation, so beat 22 recorded the line "That makes the trees".

---

## 7. World-agnostic notes and World Bible asks

- Every check keys on engine records (outcome status, effect kinds, refs), the attribution,
  and closed English lexicons of *verbs* (motion, stopping, harm). None keys on a place
  name, a fact label or a people. People words come from the world's `play.races[].name`;
  settlement words from the settlement's own name and `places.scale_of`.
- The face slots are the fragile part: `Appearance` is free prose in all three worlds
  (Aurvantis "carries an old scar earned young…", Pangrella "Tall, dark-haired, with
  Zhilakai facial markings", the synthetic "a grey plait pinned up…"). A Pangrella Korvu has
  talons and wings, so "hands" and "hair" slots must be read from the people's own `body`
  lines, not assumed.
- **Export ask:** appearance as fields beside the prose —
  `appearance: {"text": str, "age": "young|middle|old|ageless", "hair": str | null,
  "marks": [str]}` per character, and `play.races[].body_slots: {"hair": bool,
  "hands": "hands|talons|paws", ...}`. Words, not numbers; the prose stays the world's own.
- No ask for direction: it comes from place tiers the app owns (Lane B).

---

## 8. Tests

Each test's docstring carries the measurement; all run over the three worlds where a world
is involved.

| Test file | Encodes |
|---|---|
| `test_a_mentions_by_head.py` | 12 of 12 opening companions keyed on the wrong last word; "the old man ahead of you" mentioned in every beat by "you"; `mentions._head` wrong on 10 of 12. Replay: Bobby beats 2, 4, 6 — the watchman owed a face on beat 1 (transcript 2), not beat 3 (transcript 6) |
| `test_a_say_is_the_players.py` | 6 of 7 PC says at overlap 1.0, 1 at 0.0; replay turn 12's plan: the `say` of "She doesn't like the desperate ones…" is dropped or replaced |
| `test_a_hails_whole_beat.py` | 20 quotations on the beat, 14 sentence by sentence; replay Drenn's beat (transcript 8, `said` c4 ×2): 2 hails where there were 0 |
| `test_a_stop_shown.py` | replay transcript 10 with turn 21's outcome (`met: patrol`): flagged |
| `test_a_direction.py` | replay transcript 10 with market → the way in: both sentences flagged; the same text on an inward move is not |
| `test_a_refused_move.py` | replay transcripts 12 and 14 with turns 25/29 (all moves refused): 14 flagged, 12 not; a resolved move with the same prose is not |
| `test_a_brief_verbatim.py` | 2 label-colon hits in 32 beats, both defects; transcript 14 flagged; the other 31 beats clean |
| `test_a_speaker_real.py` | turn 36's `unknown_refs: ["new1"]`, 0 of 3 lines attributed: the man is embodied with a square and the hail opens a conversation |
| `test_a_player_fixable_refusal.py` | turn 48: 7 identical legality refusals across two models; replayed through `plan_turn` with scripted replies, one refusal and 0 retries |
| `test_a_spell_aim_not_a_claim.py` | "I cast burning hands into the tree tops" produced "produce a tree tops you do not have"; now "" |
| `test_a_no_victim.py` | transcript 26 with the resolution of turn log row 55 (`targets: []`, 1d4 = 1): `contradicts_state` found 0 sentences; now at least 3 |
| `test_a_face_kept.py` | synthetic cases per slot over three worlds; beat 10 is **not** asserted as flagged (the slot rule cannot see it — see 16.7) |

All replays read `tests/replays/bobby-2026-09-28/` (R0's corpus).

---

## 9. Open questions for the owner

1. **Item 20.4 and the 2026-09-27 ruling.** Should a person the prose introduces who speaks
   *to the player* get a body on that beat (recommended: yes, through the arrival door), or
   should the line be rewritten out?
2. **Does a player-fixable refusal cost the turn?** Recommended: no time passes and no NPC
   acts, as a parser error in IF takes no turn — the character knows what they prepared.
3. **Order of the attribution call** (section 5): a second review pass after `polish`, or
   the attribution before `polish`?
4. **Face drift without contradiction** (beat 10): accept the brief change alone, or also
   flag *new* body details on a described person (higher false-positive risk)?
