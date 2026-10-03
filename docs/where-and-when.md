# Where and when

Lane B of the 2026-10-03 playtest (`docs/playtest-2026-10-03.md`, items 9–12). Two saves
of Kesst Vayr in Zhilvarnia: **market-talk** (8 turns at the market) and **items** (the
same game 15 turns on: the docks, a storage area, the counting house, a smithy). Built
2026-10-03 on branch `fix/where-and-when`.

## What was measured

| Item | In the save | Root cause |
|---|---|---|
| 9 | "move it toward the storage area" founded *the storage area* and moved the party in; "head for the side door" founded *the smithy* | The plan's `travel` was refused, and the refusal's own hint ("found it first in the same plan") taught the retry to mint a place |
| 10 | All five travel tells said "You leave X mid-sentence", the first naming four people | `end_talk("walked away")` printed "mid-sentence" for everybody holding `states.TALKING`, which is sticky by the 2026-09-24 ruling |
| 11 | "work of the morning" → "first hint of dawn" → "pre-dawn gloom"; market-talk's last turn "midnight" | The clock read 0–88 minutes (just past midnight), and the brief said so every turn. The save predates 2026-09-27, when the clock began starting at the opening's hour, so its opening said "Evening" over a midnight clock. Nothing checked the prose's hour |
| 12 | The engine held the party at the market; the page wrote "the tavern patrons", "the man at the bar", "the air in the room" | The legacy opening row "a lit doorway with a room's noise behind it" was shown with the party at the market. `stands-elsewhere` reads place names; Zhilvarnia has a tavern, and no sentence said "you are in it" |

## What the traditions do

**Rooms and things.** Inform 7 separates them: only the `going` action changes the room,
and it "depends on the direction the player goes, the room he starts from, the room he
intends to reach, whether there are any doors intervening" (Recipe Book §6.9). Going by
name is an author's extension that takes a *room*; the same page says nothing about
moving toward a thing inside the current room — in Inform, walking up to the counter is
not an action at all, because the player is already in the room with it. MUDs enumerate
exits; Evennia and LambdaMOO create rooms only by command (`@dig`/`dig`, already in
`docs/place-doors.md`). Ian Bicking's *Intra* (an LLM-driven text adventure, 2025) keeps
rooms as fixed game state with defined exits rather than letting the model generate
locations. The failure mode of the other choice is described for AI Dungeon 2 (TV Tropes,
a secondary source): the player "can randomly find themselves teleported to different
kingdoms"; AI Dungeon's own help page puts it down to story falling out of context.

**Time.** Inform keeps `the time of day` itself ("play ordinarily begins at 9 AM and each
turn takes one minute", WI §9.6) and descriptions ask it. CircleMUD's `weather.c` moves
`time_info.hours` and only then sends "The sun rises in the east" (hour 5) or "The night
has begun" (hour 22) — to outdoor rooms only. Evennia's ExtendedRoom shows only the
description text tagged for the current slot (morning, afternoon, evening, night). In all
three the clock decides and the text follows; none lets a description set the hour. The
research literature agrees on where models fail: ConStory-Bench (*Lost in Stories*, ACL
Findings 2026) finds consistency errors "most common in factual and temporal dimensions".

## What was adopted

- **Walking toward a thing is not a journey** (`judgement.keep_movement_in_the_scene`,
  run every planning attempt, before validation). A movement aimed *toward* something
  that is not a place here, or at a room's fitting (a door, a counter, a corner, "the
  storage area"), drops any `travel` to a place that does not exist and any `found` the
  player never declared; the turn becomes the narrated walk. The refusal's hint now says a
  fitting is not a place. Kept untouched: travel to any real place, a declared base, a
  place the words set out to find ("toward the back streets to find the Velvet Veil" —
  the 2026-09-30 "go anywhere" ruling), and going *through* a door.
- **The tell says what the engine knows**: "You walk away from the servant and the man,
  and the conversation is over." A conversation was open and walking off closed it; who
  was speaking is not engine state.
- **The clock owns the hour** (`gm/checks/time_of_day.py`). Narration claiming the present
  hour ("the midnight air", "the work of the morning", "the first hint of dawn", "it is
  evening", "the sun beats down") is checked against generous windows round the clock and
  repaired with no model call: the clock's own word where the wrong one stood ("the work
  of the night", "the first hint of dusk"), and a sentence with no word to swap (a verb
  claim, or first light at 1 a.m.) cut. Speech is never read.
- **The setting is checked by its furniture** (`gm/checks/setting_kind.py`). A taproom's
  fittings and people where the party's place is not a tavern or an inn, and a room's
  (the room, the rafters, the ceiling) where it has no roof (`places.is_indoors`), are
  found; one targeted rewrite per sentence, cut if it still fails. A tavern *across the
  square* is a view and is left alone.
- **The legacy opening stands where its words are set.** Each row of `opening.SITUATIONS`
  names the kinds of place it describes (`SITUATION_KINDS`, the start documents'
  `where.kinds` vocabulary), and a new campaign with no start document is placed in one.

## Refused, with reasons

- **Minting a place for every noun the player walks toward.** AI Dungeon's teleporting
  kingdoms are this; so were *the storage area* and *the smithy*.
- **Asking the model to keep the time straight in the prompt alone.** The brief already
  said "WHEN (fact): day 1, deep in the night (about midnight)" every turn of the items
  save, and the prose still went to morning and dawn. Instruction lost to habit — the
  CLAUDE.md rule.
- **A model rewrite for every wrong hour.** A one-word swap is right far more often than
  not, and costs nothing (item 26: every lane should avoid adding model calls).
- **Shifting an old save's clock on load to match its opening.** The owner's save opened
  "Evening" on a clock at 0. Moving the clock would move every person's residency slot
  (`first_seen`, `arrived`, `swayed`, cards' `opened_at`) out from under them, and the
  narrator was told "midnight" for all 22 turns of it. Such a save keeps its clock, and
  the time check now holds its prose to it.

## Replay (scratch script over every prose draft and shown beat; not committed)

| | items (62 texts) | market-talk (19 texts) |
|---|---|---|
| before: either new kind | 0 | 0 |
| `time-of-day`, at the save's own clock | 3 beats, 3 sentences | 0 |
| `time-of-day`, had the clock started at the opening's 19:00 | 5 beats, 5 sentences | 2 beats, 2 sentences |
| `wrong-kind-of-place` | 8 beats, 15 sentences, all at the market | 8 beats, 15 sentences, all at the market |

No `wrong-kind-of-place` fired in the 54 texts set at the docks, the storage area, the
counting house or the smithy. The planner filter, on the two measured rows: both plans of
row 52 and the plan of row 106 become `narrate_only`; the Velvet Veil row is unchanged.

## Not sourced

I could not find Fate Core's primary text on moving within a zone, a primary source for
Diku's `time_info` beyond CircleMUD's `weather.c`, or any record of AI Dungeon adding and
then abandoning a location model; the AI Dungeon claim above is a symptom reported by a
secondary source, not a design decision. The quotations from Inform's Recipe Book and from
*Lost in Stories* were checked against the pages; the critic pass was mine, not a second
agent's.

## Still open

- A legacy row whose kinds the town lacks (a work yard in a town with no workshops) still
  opens at the way in under its own words: Zhilvarnia stands two of twelve rows there.
- "Going through the side door" with nowhere behind it is still for the found/venture
  doors to answer; `play.places[].features` (docs/from-world-bible.md) would say where.
- Character speech about the hour ("the evening shift, three hours from now") is never
  checked, by design.

## Sources

- Inform 7, Recipe Book §6.9 "Going, Pushing Things in Directions":
  https://ganelson.github.io/inform-website/book/RB_6_9.html
- Inform 7, Writing with Inform §9.6 "The time of day": http://inform7.com/book/WI_9_6.html
- CircleMUD `weather.c`: https://github.com/Yuffster/CircleMUD/blob/master/src/weather.c
- Evennia ExtendedRoom contrib:
  https://www.evennia.com/docs/latest/Contribs/Contrib-Extended-Room.html
- Ian Bicking, "Intra: design notes on an LLM-driven text adventure":
  https://ianbicking.org/blog/2025/07/intra-llm-text-adventure
- TV Tropes, "AI Dungeon 2": https://tvtropes.org/pmwiki/pmwiki.php/VideoGame/AIDungeon2
- AI Dungeon, "Why does the AI forget or mix things up?":
  https://help.aidungeon.com/faq/why-does-the-ai-forget-or-mix-things-up
- *Lost in Stories: Consistency Bugs in Long Story Generation by LLMs*:
  https://arxiv.org/abs/2603.05890
