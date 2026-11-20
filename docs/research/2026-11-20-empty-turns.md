# Research note, 2026-11-20: empty turns, a self-contradicting beat, an inventing table voice

Lane `fix/empty-turns`, playtest 2026-11-20 items 7, 14, 15 (owner's 0.4.4 game, save
`owner-1120-data`, campaign `shadow`). Written before the code, as the brief asks, then
re-checked against the sources (second pass at the end).

## What the save says happened (reproduced from `turn_log`, `training/inputs`, `auto-corrections`)

| page | what the pipeline did | where it broke |
|---|---|---|
| #50 "Look for a different way into the gallery" | reader: `search`, `where` left at the default `elsewhere`, so the act table built nothing; the plan's own check aimed at a placeholder and `settle_placeholders` dropped it on the retry → `narrate_only`, no tell → the `doing` slot ("show them starting on it, and nothing that comes of it") | **engine resolved nothing** |
| #14 "I help him lift the cart and … I'd like an item from his pack in exchange" | Aid Another + Make Request resolved; tell "the carter agrees to do Shadow the favour. Nothing changes hands." The reply slot ("I can certainly share something from my pack") was read as clashing with "Nothing changes hands", the remake clashed too, the reply was **dropped** | engine tell without what was asked; the world's answer then cut by the tells check |
| #85/#86 "move to (1,9)" | engine: the cockroach "moves 30 ft toward Shadow and is still 25 ft away"; prose "closing the distance by thirty feet until it stands twenty-five feet away" was flagged by `closing_claimed` (a false positive on "closing the distance"), cut, and the stand-in said only "The giant cockroach is still 25 feet from you." | **backstop dropped the world's answer** (the creature's move) |
| #141 "I up upstairs" | reader: `go`, fixture `stair` → move onto the stair square at ground level; tell "moves 40 ft, onto a stair"; page "you begin to ascend" — the engine never took them up | reader's fixture answer (stair, not the gallery it serves) |
| #97 (item 14) "I move to A14 and strike the clockwork spy" | declared-fight slot told "squares up from where they stand: nobody moves" because the move was a separate act of the same turn; the next slot moved 35 ft | plan wording reads only its own act |
| #9, #45, #48 (item 15) | Gleeful's lines: crates that were never there, "a cellar or a crawlspace", "listening beneath the stones". `beyond_tells` scores "a question to the player, or advice on what they might try" as `reacts`, so a lead posed as a question or a tip is never checked; the `refused` job asks it to "point at another way if there is an obvious one". "cellar" came from the engine's own refusal list of ground kinds | the read's carve-out, and the job's invitation |

So the answer to the lane's question ("engine resolving nothing, tell never reaching the
narrator, or the narrator dropping it?") is: **all three shapes occur**, and in two of the
four the dropper was our own check, not the model.

## Item 7: "the player acted, the world must answer"

Sources:
- Inform 7, Writing with Inform §12.2 "How actions are processed"
  (https://ganelson.github.io/inform-website/book/WI_12_2.html): check rules decide whether
  the action makes sense, carry-out rules do it, and report rules "tell the player what has
  happened". Every action that passes check has a report; a refused one is stopped at check
  with its own message.
- intfiction.org, "Neutral Library Messages extension" thread
  (https://intfiction.org/t/neutral-library-messages-extension-beta/1839/19): a poster says
  the stock "Nothing obvious happens" "always implied that something terribly interesting was
  going on somewhere else"; another (Aaron A. Reed) that a bare default answer misleads the
  player about what they could do. Lesson: the answer to an action must be the specific
  outcome, not a placeholder.
- Apocalypse World, "always say … what the rules demand … what honesty demands", via the
  Daily Apocalypse commentary (https://daily-apocalypse.com/daily-apocalypse/36-always-say):
  players are owed "the full benefit of their moves and rolls", the MC "scrupulous, even
  generous, with the truth". I could not check the rulebook page itself; that is a secondary
  source quoting it.
- Narrative-AI output validation: the project's own verified sweep of 2026-11-04 (memory
  `narration-accuracy-measured`): omission is a separate error class from contradiction;
  Kasner & Dušek ACL 2024 (arXiv 2401.10186) measure omissions and inventions separately in
  data-to-text; a contradiction checker cannot see an omitted fact ("a sentence that is
  missing contradicts nothing", already written in `planned._all_told`).
- PF1e: searching is Perception, "Intentionally searching for stimulus is a move action"
  (https://www.aonprd.com/Skills.aspx?ItemName=Perception); a request is a Diplomacy check
  whose DC is the attitude plus the request's own modifier — the request is the player's
  (https://www.aonprd.com/Skills.aspx?ItemName=Diplomacy; the page has no "Make Request"
  heading, the code's "CRB p.93" is the book's page).

Chosen:
1. **Fix each dropper at its root, in the shared path.** (a) A search the reader read and
   nothing answered, on a turn otherwise only `narrate_only`, is the Perception search of
   where the player stands (`acts_to_ops.search_unanswered`, beside `nowhere_to_go`, the same
   "otherwise nothing" rule). By the book a search is Perception of your surroundings; a search
   "elsewhere" that no travel/found/venture door took is still a search of here. (b) A request
   for a favour carries what was asked (the reader's own `object` words) into the tell, and a
   granted one says "Nothing has changed hands yet" — a promise is not a handover, so the reply
   can answer it. (c) `closing_claimed`'s stand-in states the creature's move from the engine's
   own position effect, not only the gap. (d) The reader's `fixture` description and one example
   send "upstairs / up the stairs" to `gallery`, the raised part the stair serves.
2. **The mechanical check that a beat states its outcome.** Inform's report stage, done as the
   house shape: detect in code, repair with one targeted call. Every resolved act slot (not a
   blow slot, which has its own facts, and not a declared fight) is read after it is written by
   a closed two-answer read, "says how it came out" / "only the attempt", the result first
   (`beat_verify.outcome_told`); on "only the attempt" the slot is asked once more with the
   result named, and the remake stands only if the read then says it came out.

Measured before building (probe in the lane's scratchpad, gemma-4-12B heretic, temp 0):
- the existing fact-first read (`second_on_tell`, "tells it / says nothing about it"), asked
  with the whole tell, passed 3 of 4 attempt-only passages as "tells it" ("You scan the
  surrounding ruins, searching for a different way…" against "searches the ruins and finds
  nothing") — useless for omission, because the tell's attempt half matches;
- the dedicated two-answer read scored 14 of 15 labelled pairs (all 6 attempt-only caught;
  one false alarm, an eat told as "you pull rations from your pack and eat"). A false alarm
  costs one re-ask; the first answer stands unless the remake reads as told.

Rejected:
- Rewording the `doing` slot or the act slot to "always say the result": instruction, not
  detection (CLAUDE.md); the act slot ask already says "Show the player doing what the engine
  decided", and the model still wrote the attempt alone.
- Building the search in the act table whenever `where` is unset: "look for a tavern" is an
  elsewhere search the travel/found doors answer; a Perception roll beside it would be a second,
  wrong outcome.
- A keyword list for "upstairs": a regex deciding meaning (owner ruling 2026-10-03).
- Splitting tells into "attempt" and "outcome" halves in code: that is reading the engine's
  English; the read takes the whole tell as the result and judges the passage.

## Item 14: a beat that contradicts itself (#97)

Sources:
- PF1e: a move action and a standard action are both taken in one turn, in either order
  (https://www.aonprd.com/Rules.aspx?Name=Action%20Types&Category=Combat — not fetched this
  session; the engine already resolves it that way, the move tell sits beside the blow).
- Inform 7 §12.2 again: report rules run after carry-out, per action, in order; one action's
  report does not describe another's absence. Our declared-fight slot described the moment as
  "nobody moves", which is a claim about the whole turn made from one act.
- Data-to-text: Kasner & Dušek 2024 (above) name fact merging as a surviving error; a slot
  told a negative ("nobody moves") about a fact another slot carries is that shape.

Chosen: the declared moment's opening fact reads the TURN's outcomes for the player's own
move, not only its act: when the player moves anywhere this turn, the squaring-up says no
blow has landed and says nothing about moving (the move has its own slot); when they
move in the same act it is "closes and squares up" as before.
Rejected: a post-hoc contradiction read of the whole beat — the tells check reads sentences
against tells, not against each other, and the defect is our own instruction (the fix is at
the source, where the false negative was written).

## Item 15: the table voice invents leads

Sources:
- The Alexandrian, "Three Clue Rule"
  (https://thealexandrian.net/wordpress/1118/roleplaying-games/three-clue-rule): a GM gives
  real clues to real conclusions; red herrings are "overrated" and to be used with "extreme
  caution" because players latch onto them. A GM's pointer at something that is not there is
  an unplanned red herring.
- Apocalypse World's MC principles include "ask provocative questions and build on the
  answers" (secondary listings; Gnome Stew, Daily Apocalypse) — in PbtA the players' answers
  BECOME true. That is the tradition this table voice imitates by accident, and the one we
  must refuse: here the engine owns what exists (architecture.md, "the GM proposes; the
  engine disposes"), so a leading question about crates creates an expectation nothing backs.
- AW "what honesty demands" (above): real information players can use about their surroundings.
- Grounding research: GroundAct (arXiv 2508.05614) and TALES (arXiv 2504.14128) found by
  search; only the abstracts were read. GroundAct reports LLM agents falling from 85-96% to
  29-53% when an action's feasibility depends on state the instruction does not mention — the
  same family of failure. I did not verify their numbers beyond the abstract/search summary.

Chosen: (1) the `beyond_tells` read stops excusing advice and questions that name or presume a
thing, place, way or hidden presence the facts and the story do not hold — they are `adds`, with
two new demonstrations; the story the player just read is given to the read as a fact source,
so pointing at the rubble the page described still passes. (2) The `refused` job no longer asks
the GM to "point at another way if there is an obvious one"; only a way the MOMENT or THE SCENE
names. The existing repair (ask once naming the words, then cut sentence by sentence) does the
rest.
Rejected: a word-overlap check of the line's nouns against the facts (regex reading meaning,
and "cellar" was in the engine's own refusal list of ground kinds, so it would have passed);
giving the table voice the place's full fixture list so it can suggest real things (more
prompt to invent from; the table's job is reaction, not hinting — Three Clue Rule clues are
the world's, delivered by play).

## Measured after building (2026-11-20, gemma-4-12B heretic, shared Ollama)

- Reader, 12 lines, before → after: "I up upstairs" and "I go upstairs" `stair` → `gallery`
  (0/2 → 2/2); "walk over to the stairs" stays `stair`; "onto the wall-walk", "up to the loft"
  stay `gallery`, "go back down" stays `floor`. "I climb the stairs" is `stair` (ambiguous;
  left). The reader's prompt-budget test forced the description short: "wall-walk" is now
  carried by its own demonstration only.
- Table read (`beyond_tells`), 10 labelled table lines: 6/10 → 10/10 (inventions 0/4 → 4/4,
  clean 6/6 kept). Without the story given, the new prompt flagged "Take your time checking the
  gallery" (9/10) — hence the story as a source.
- Reply vs the new favour tell (`against_tells`, 3 reads): "I can certainly share something
  from my pack" 0 clashes; a handover sentence still clashes. The OLD tell also gave 0 clashes
  on this reply in isolation (3/3): the live false clash was not reproduced outside its beat, so
  the favour fix rests on the tell naming nothing, not on a measured clash rate.
- Live, the owner's save at the ruins, port 8964: "Look for a different way into the gallery"
  rolled Perception and the page said "the ruins yield nothing of interest" (the reader read
  `where: here` this time, so the new backstop was not the path taken; it is unit-tested);
  "I up upstairs" → "Shadow moves 15 ft, up onto a gallery", page "ascending onto the gallery
  above".

## Second pass (re-read of the sources, 2026-11-20)

- Inform's report-rule claim checked against §12.2 itself: "tell the player what has
  happened" is the page's wording. Kept.
- The intfiction quote is from a forum poster ("Matt"), not the Inform designers; worded so.
- AW's "always say" is quoted from a commentary blog, not the book; flagged above. The MC
  principle wording varies between secondary sources ("answer"/"answers"); not quoted exactly.
- The aonprd Diplomacy page has no "Make Request" heading (fetched); the CRB page number is the
  code's, not re-verified here.
- The PF1e action-types page was not fetched; the claim used (move + standard in one turn) is
  standard PF1e and already how the engine resolves turns, but it is unsourced in this note.
- GroundAct/TALES: abstract level only; not used to justify any number in the code.
