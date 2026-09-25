# The review pass

*2026-09-25. A five-way critical review of master at 80535ca (engine and state, the model
pipeline, the web layer and saves, the test suite, the open-promise ledger), and the fix
pass that followed, in severity order, on branch `review-fixes`. Every claim below was
reproduced by probe or read in the code before it was fixed; each commit's message carries
its own measurement, and each fix has a test file named for the defect it prevents.*

---

## What was fixed

| # | defect, as measured | commit | test |
|---|---|---|---|
| 0 | three tests reached the live model; 61 campaign set-ups rolled unseeded dice; 26 test files leaned on pytest-django though requirements.txt says it is unused; a robustness case checked a route that never existed; the race cache missed a same-size edit inside one clock tick | ae3777a | `test_suite_isolation.py` |
| 1 | six of six friendly sentences ("the barmaid rushes over to you with a tankard") opened a fight and rolled her attack | 48f5e84 | `test_a_kindness_is_not_a_blow.py` |
| 2 | every save truncated and rewrote the only copy; ten more writers the same | 11a6df2, 82267ce | `test_a_save_is_never_half_written.py` |
| 3 | a turn that crashed after `engine.run` stayed half-applied in memory and the next turn saved it; a 503 lost the free actions | 01f05aa | `test_a_failed_turn_leaves_nothing_behind.py` |
| 4 | an NPC knocked out at full hit points left the campaign after three calls | 09aa709 | `test_the_unconscious_stay.py` |
| 5 | `GET /play/?new=1` reset the game from any web page | ada1bc5 | `test_a_link_cannot_end_the_game.py` |
| 6 | homebrew and roster ids became filenames unchecked (`..\..\models`) | 82267ce | `test_an_id_is_not_a_path.py` |
| 7 | a LAN guest had the host's full power; the pass never expired; the log held it | 863de68 | `test_a_guest_is_a_guest.py` |
| 8 | helpless counted as down: a bound foe ended the fight | e26408a | `test_helpless_is_still_in_the_fight.py` |
| 9 | the turn jumped to the wrong creature at five order-changing sites, and a holder leaving skipped their successor (the 09-20 fix had sat uncommitted in a worktree) | 38406c4 | `test_the_turn_stays_with_its_holder.py` |
| 10 | flat-footed, touch and lose-Dex did nothing against any of 7,133 bestiary creatures | 1e3b6c0 | `test_a_monster_can_be_caught_flat_footed.py` |
| 11 | "I say nothing and attack the guard" read as no violence | 12fd81a | `test_the_action_after_the_words.py` |
| 12 | nine quotation rules disagreed; the phantom elder could still be reproduced in curly quotes; a self-given name was rewritten in its own line | 5927fc7 | `test_one_quotation_scanner.py` |
| 13 | quitting killed a finishing turn; two docstrings promised otherwise | 254d037 | `test_quitting_lets_a_turn_land.py` |
| 14 | spell fog and walls stayed on the map after the fight; area ids were reused | 7306ae9 | `test_the_fog_goes_with_the_fight.py` |
| 15 | an unreachable model aborted the turn instead of reaching the fallback; a cut-off reply was invisible | 2392064 | `test_a_model_that_is_down_hands_on.py` |
| 16 | each NPC turn paid for a polish rewrite; the rewrite was never shown the tells | 1efd840 | `test_the_rewrite_sees_the_dice.py` |
| 17 | a cut flattened the paragraphs; a flagged sentence carrying speech was never cut | 677f556 | `test_a_cut_leaves_the_rest_as_it_was.py` |
| 18 | a failed scheme tick kept what it had changed; off-stage damage skipped the damage door | 8a9b74b | `test_a_scheme_that_fails_leaves_nothing.py` |
| 19 | lose-Dex and slowing were answered from row flags and literal tuples | d9e7a75 | `test_the_questions_are_tags.py` |
| 20 | two records hid in `scene.said`; `scene.log` grew without bound; an over-budget prompt went silently; "three exchanges" kept two | 00ecc8f | `test_the_scene_keeps_its_books.py` |
| 21 | seventeen loaders skipped a broken file without a word; a renamed rule would make saves unreadable | fb83b25 | `test_a_skipped_file_is_named.py` |
| 22 | a roster version bump would empty the shelf | fb3ed0b | `test_an_older_roster_still_reads.py` |
| 23 | force-killed runs leaked 40 MB unpack folders into %TEMP% | e6561ba | `test_old_unpacks_are_swept.py` |
| 24 | eight page reads skipped the careful JSON path; `?limit=x` was a 500; `busy()` left the action controls live | 35ac82f | `test_the_page_reads_every_answer.py` |
| — | a fight's prose founded places; `.test-data` kept 456 files across runs | 4e97cdb, 1964a9f | `test_a_place_the_page_made.py` |

Three corrections the pass made to itself, each caught by the full suite or a probe before
it was committed: the first backup-restore rolled back a save from a NEWER build, and then
one that parsed and failed the rules (a homebrew class edited under its character) — only a
file that no longer parses is restored now; the first model stub replaced `chat` itself and
broke seven tests of `chat`; and the first quotation scanner refused a close after a space,
which the real Korgath beat of 2026-09-24 uses.

**Verified live** on port 8942 with its own data directory and a real model: the table
loads with no console errors, a turn holds the `resolving` state and releases it, the save
lands by rename with `.json.1` beside it and no temp file, `/play/?new=1` archives nothing,
the traversal id is refused in words, and `?limit=many` answers 200.

## What was left, and why

- **The prose still writes game state by pattern.** About ten detectors change the scene
  from the finished prose (booking people, names, fights, places). The review's structural
  recommendation — the prose call returns segments with speaker refs from an enum, so the
  engine checks declared fields instead of guessing — is a redesign, and this project
  searches for how it has been solved before designing (CLAUDE.md). Not started.
- **An `Encounter` owner for initiative, sides and standing things.** Fix #9 gives the order
  two doors and a successor flag; the object that would own all of it is a refactor.
- **Suite speed** (~9-10 minutes). Most of it is content caches rebuilt each time a test
  moves `CAMPAIGN_DIR`. Keeping them across moves was tried on paper and refused: a test
  that writes homebrew after entering its directory would read a catalogue cached before
  the write. Parallel runs need per-worker data directories first.
- **67 source-text test pins.** One was converted (`test_the_crowd`); the rest still break
  on a rename with no behaviour change.
- **A replay corpus of recorded model output.** Needs real recorded sessions committed as
  fixtures; the saves that hold them live in the player's data directory.
- **A total turn budget and a Cancel button**, the 4.4k-line template's split into modules,
  and signing the installer — features and maintenance, not defects.
- **The open-promise ledger** (the world agent that ticks between scenes, factions, the
  level-up picker, stage 9) is product work, recorded in the review report of 2026-09-24.
