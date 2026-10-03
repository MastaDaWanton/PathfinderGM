# People and names (Lane C of the 2026-10-03 playtest)

Items 13–16 of `docs/playtest-2026-10-03.md`. Everything below was measured on the owner's two
Zhilvarnia saves: *market-talk*, 8 turns, and *items*, 15 turns later. The saves are never
committed. The tests, `tests/test_people_and_names.py`, are built from those saves' own lines.

## What went wrong, and where

| Item | Evidence | Where it came in |
|---|---|---|
| 13. The player's quoted words became a person | `I give a friendly wink and say "just trying…"` was read as `talk, target: say "just trying…"`. `introduce` minted c4 with that phrase as his name. It showed up in prose ("The say \"just trying…\" is a Korvu"), in tells and in the ledger, and was still the talk target 10 turns later. | `gm/interpret.py` `ground`: the span was the sentence's own words, so grounding kept it. Then `judgement.person_sought` → `inject_introduce` → `Engine._op_introduce`. Nothing at any of these doors asked whether the phrase could be a name. |
| 14. A people's name became a personal name | "The laborer—a man named Korvu…", and c11 became "Korvu", true name and all. | The appositive reader (`narration.named_in_apposition` → `judgement.apply_introductions` → `_take_the_name`). The phrase "is a Korvu" was the backstop's own face line ("The merchant with a heavy pack is a Korvu: …"), which the narrator copied. |
| 15. Lines and faces landed on the wrong person | Market-talk: 11 lines tagged to c1, the jug-carrying servant. In 10 of them the servant appears nowhere in the beat and the page makes "the man" the speaker. Each tag opened a conversation with the servant (`hailed_by`). The PC's own lines were booked as the servant's (beat 4) and the clerk's (items, beat 32). c6's face was placed after "The man in the heavy coat (c4)". | The model's `<say who=…>` tags were trusted unconditionally. No clause rule knew "you" as a speaker (`checks._quotes.clause`, `speaker_real._whose`, `hailed_by`). `speaker_real` could not see the "(c4)" the page pinned to the description, so the bare word "man" made a new man, c6. `place_the_face` put c6's face after the first sentence containing "man". |
| 16. The narrator spoke for the PC at an ordinary table | The plan's invented `say` was dropped by `own_words_only`. The prose then gave Kesst 38 words of her own anyway: "'A piece of work like this,' you say…". | No check existed. `prompts.INTIMATE_BRIEFING`'s note had already recorded this on 2026-10-01: "no check in the pipeline catches the narrator speaking for the player on ANY beat". |

## What was built

**13: a name has a shape.** `names.not_a_name(phrase)` returns why a phrase can never be what a
person is called, or "" when it can be:

- quotation marks;
- a verb of speech at its head ("say …", "ask him …");
- a first-person opening;
- a sentence's closing mark;
- more than 14 words.

Every door that mints a person asks it: `population.names_a_person`, which is the engine's
`introduce` gate, and the refusal now says why and names `say` as the fix. `judgement._introducible`
and `inject_introduce` ask it too.

The reader fixes it at the source: `interpret._speech_is_not_a_target` drops such a target and,
for a `talk`, moves the quotation into `says`. A new demonstration shows a quotation with no
target. Re-grounding the save's own reading gives `talk, says: "just trying…"`, `person_sought`
returns "", and the ops are `["say"]`.

**14: a people's name is never a person's.** `names.people_names(world, scene)` gathers names
from three places: the world's PEOPLE entities and `play.races`, the heritages the scene's
people carry, and the rulebook's races (`rules/races`). `apply_introductions` refuses such a
name at both its doors, speech and apposition, and logs "a people of this world" as the reason.
No world's names are written into code.

The face line now reads "is of the Korvu people: …" (`narration.a_face_for` and its copy
`opening.face_line`). "A Korvu" is a noun phrase a name fits into; "of the Korvu people" can
only be a people. This phrasing change is not the fix on its own.

**15: precision over recall, by the page's word.**

- `_quotes.pc_spoken` and `pc_lines` read "…,' you say", "You lean in and murmur, '…", "your
  voice …" and a tag naming the player as the PC's line. They also catch the second half of a
  split line: "…,' you say, …, '…'".
- `speaker_real`, `_quotes.speakers` and `hailed_by` give such a line to nobody.
- `judgement.doubt_tags` runs in `views` before names, bodies or hails read the tags. It
  withdraws a model tag in two cases, and never re-points one:
  - the line is the PC's;
  - the tagged person is nowhere in the beat (not by name words, not by ref marker, not by the
    attribution) and the narration makes a different person-word the speaker.

  A withdrawn line to the player is then `speaker_real`'s to settle from the page.
- `speaker_real` reads a description pinned to a ref ("the man in the heavy coat (c4)") as that
  person.
- `place_the_face` skips a sentence that is plainly somebody else's: one with another ref's
  marker, or one the attribution read as naming only other people.

**16: `gm/checks/speaks_for_player.py`** (kind `speaks-for-the-player`).

- **Detects** a PC line whose content words fall below `judgement.OWN_WORDS` (0.5) of the
  player's own line. That is the bar the plan's `say` is already held to.
- **Repairs** with one targeted rewrite through `_repair_sentences`, which names what the player
  actually wrote.
- **Backstop:** cut the sentence(s). When the player quoted words this turn and the page lacks
  them, they stand in as "You say, “…”".
- **Exempt** at the intimate table (`BeatContext.intimate`, from `GMAgent._intimate_beat`), by
  the owner's ruling of 2026-10-01.

**Existing saves are healed on load.** `person_words.heal_phrase_names` sits beside
`heal_ref_names` in `Campaign._retire_stale_masters`. An actor whose name fails the shape check,
or whose name and true name are both a people's name, gets a description back. The sources are
tried in this order:

1. the description the page pinned to their ref;
2. their record's words;
3. their work;
4. their stat block;
5. "a stranger".

The record, the cast entry, the conversation log and the ledger's lines follow the new name. A
true name that was a people's name is drawn again from the world's pools.

## Replay on both saves (scratch scripts, not committed)

| What | Before | After |
|---|---|---|
| The reader on the wink line | `talk target='say "…"'` → introduce | `talk says='just trying…'`, no target, person sought "" |
| c4 on load (both saves) | `say "just trying to start a conversation…"` | `man in the heavy coat` |
| c11 on load (items) | `Korvu`, true name `Korvu` | `lone laborer`, true name "" (Pangrella ships no `play.names`) |
| Ledger rows holding the phrase | 2 (market-talk), 3 (items) | 0 |
| speaks-for-the-player over every beat | not checked | 1 of 30 beats flagged: items beat 32, the real case. The backstop leaves "…as you gesture to the heavy crate. You let the silence stretch…" |
| Bobby corpus (13 beats, 25 quotations) | — | 0 read as the PC's, 0 flagged |
| Model tags withdrawn | — | market-talk: 10 of 11 (every c1 "man" line but "The docks?", where nobody is described before it). Items: 11 of 41, the same 10 plus one c4 line that was right, withdrawn only because c4's name was still the bad phrase in that replay. After the load heal his name matches the page. |

## Research (searched 2026-10-03)

### Inform 7 and TADS 3

In Inform 7, a topic is text, not an object. What follows ASK … ABOUT is "a piece of text in
double-quotes, and not the name of something" (*Writing with Inform* §7.6). The `[text]` token
goes into "the topic understood" and is never resolved against the world (§17.5). `bob, hello`
becomes *answering Bob that "hello"*: the person comes from the vocative, and the rest stays
text.

TADS 3's `LiteralAction` "will accept anything as the literal phrase … and treat them all simply
as text". Its examples are SAY and TYPE.

Adopted: a quotation, or the words after SAY, is never an object slot. That is
`_speech_is_not_a_target` and `not_a_name`.

### Quote attribution

- Muzny et al. 2017 is a two-stage sieve. Its high-precision variant gets 90.4% precision at
  65.1% recall and leaves about a third of quotes unattributed on purpose.
- On PDNC (Vishnubhotla et al. 2022), explicit quotes are attributed at about 0.95, but
  anaphoric and implicit ones at under 0.5, for both Muzny's sieve and BookNLP.
- He, Barbosa & Kondrak 2013 reached 83%.

Adopted: a tag is only withdrawn on the page's own evidence, never guessed onto somebody else.
The "you" clause is added as an explicit-clause rule.

Refused: Muzny's last-resort "majority speaker" fallback. It is exactly the stale default
item 15 describes.

### OntoNotes 5.0

OntoNotes keeps NORP ("nationalities or religious or political groups") apart from PERSON, even
inside one noun phrase: "Nicaraguan President Daniel Ortega". Adopted: the world's peoples act
as the NORP list, and nothing on it may become a PERSON name.

### Speaking for the user

SillyTavern's defence is to add "Names as Stop Strings … to prevent model impersonation"
(docs.sillytavern.app, context template). Its issue #652 records the stop string missing when
the model writes the user's name without the colon. Issue #2556 asked for the always-on stop
string to be made optional, because it cut off replies where both sides speak. Shared presets
carry "never write for {{user}}", and the docs still add stop strings on top of it.

Play-by-post etiquette ("godmodding", "powerplay") forbids writing another player's dialogue.

Refused: stop strings. They cannot fire inside second-person prose ("'…,' you say"), which is
this app's whole register. Adopted instead: mechanical detection on the finished page, then a
targeted repair. That inference is consistent with the sources, but none of them documents it.

### Could not source

- AI Dungeon, NovelAI or Character.AI primary documentation on stopping the model acting for
  the player. Only unofficial posts were found.
- Any measured failure rate for a "never speak for the user" prompt.
- Anything Inform or TADS tried and abandoned here.
- Rules or studies on "a man named X" extraction, or on confusing a demonym with a name.
- Whether BookNLP leaves low-confidence quotes unattributed.

## Left open

- **c6 in the saves.** c6, the "man" made out of c4's lines on market-talk beat 14, is still in
  both saves. Two actors cannot be merged safely on load.
- **Whether the market-talk "man" really was c1.** On items beat 16 the model writes "the man
  with the jugs" for the servant, so it may have meant c1 all along. The page never said so in
  beats 2–12. The lines are left unattributed, not given to anybody.
- **`(cN)` refs on the page.** They are lane D's leak (item 19). Here they are only read as
  evidence, never added.
- **A people's word forms.** World Bible would need to export each people's singular, plural
  and adjective forms (`docs/from-world-bible.md`) before a refusal can catch "Korvus" or
  "Korvan" reliably. Today a trailing "s" is the only form recognised.
