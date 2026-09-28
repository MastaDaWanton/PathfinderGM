# Baseline and harness for the 2026-09-28 fix pass

Task R0 of `docs/fix-plan-2026-09-28.md` (Phase 0). What the suite measured before anything
was changed, what the harness adds, and what it could not do.

## The suite before any edit

| | |
|---|---|
| Commit | `93ac2d4` (branch `fixes-2026-09-28`, clean tree) |
| Command | `python -m pytest` from the repo root (`pytest.ini` adds `-q -p no:django`; testpaths `tests`) |
| Python / pytest | 3.13.7 / 9.1.1 |
| Result | **5689 passed, 2 skipped, 1 xfailed**, 0 failed, 0 errors |
| Time | 230.68 s reported by pytest; 237 s wall |
| Test files | 262 `tests/test_*.py` |

Nothing failed, so there is nothing to record verbatim. No Ollama and no server were used.

## The suite after the harness

| | |
|---|---|
| Command | `python -m pytest` |
| Result | **5727 passed, 2 skipped, 1 xfailed**, 0 failed, 0 errors |
| Time | 212.14 s reported by pytest; 215 s wall |
| Existing tests | 5689 passed, 2 skipped, 1 xfailed — unchanged |
| New tests | 38, all passing: 14 in `tests/test_harness_worlds.py`, 24 in `tests/test_replay_bobby_corpus.py` |

## What the harness adds

### A third world: `fixtures/synthetic-world.json`

Calvessa, a hand-built schema-1.5 export (not written by World Bible; it says so in its
`generated_by` and `_about`). One continent (Lathwe), two peoples (Fenwic, Carrow), two
nations, six settlements, nine people, six routes, ten authored places. It differs from
Aurvantis on purpose:

| Aurvantis (measured) | Synthetic |
|---|---|
| 64 of 64 settlements `kind: CITY` | kinds `VILLAGE` ×3, `TOWN` ×2, `CITY` ×1, each equal to its `scale` |
| "the city's" in all 64 settlements' stock sentences | each settlement uses its own scale word only |
| 256 of 256 `play.cast` roles "Person" | healer, ferryman, smith, trader, fisher, harbourmaster, magistrate, scribe, shepherd — each equal to the person's own `Role` fact |
| facts keyed Geography / Biomes / Urban Life / Tension | Terrain, Landscape, Climate, Daily Life, Customs, Conflict (all keys the code already reads somewhere) |
| 132 of 132 travel rows carry `miles` and `crosses` | two rows carry neither (one of them has no `by` either) |
| — | Marrowby is a port (authored docks); Oakhollow has no cast; four settlements ship no `play.places` and are generated |
| 80 name pools | two pools, one per people; residents' Identity prose names their people so `names.people_of` resolves |

It loads through `world.loader.load` / `load_cached`, and a campaign starts on it and
round-trips through save and load (`new_campaign(..., world_source=...)`, the same path
`/api/start` takes). `tools/check_places.py` reports **0 problems** on it and notes only
places the consumer would build or mint (no gate in Marrowby, no guildhall anywhere).
Checked by hand on every loader path found: `places.home_set` / `scale_of`,
`journey.legs_from` / `is_port`, `names.pool_for` / `people_of`, `keepers.name_for`,
`biomes.from_world`, `cards.from_world`, `races.from_world`, `opening.starting_place`,
`prompts.scene_brief`, `GMAgent._known_names`.

**What it already shows** (found while checking it, not fixed — no product module was
touched in Phase 0):

- `rules/biomes.py:329` gives `urban` only when `kind == "CITY"`: Brindle Ford, Kestwick and
  every other village and town read `['water', 'hills']`, with no `urban`. Most of the rest
  of the code accepts `CITY`/`TOWN`/`VILLAGE`/`SETTLEMENT`; this line and
  `play/library.py:87` (`world.of_kind("CITY")`, which lists only Caddonbury) do not.
- `gm/prompts.py:932` lifts only Urban Life, Social Classes, Architecture, Governance,
  Formal Power, Shadow Power, Tension and Daily Norms into the brief. The synthetic world's
  Landscape, Daily Life, Customs and Conflict never reach the narrator; its Architecture and
  Governance do.
- `rules/keepers.name_for` draws given names from the whole cast regardless of people: the
  keeper of a Fenwic village's well is "Garrow Marl" (Garrow is a Carrow name). Oakhollow,
  with no cast, takes its families from other towns.
- `opening.starting_place` picks Caddonbury for every seed — item 2's determinism on a
  second world, and here it lands on the city, not the last village.

### The `worlds` fixture

`tests/conftest.py` gains `WORLD_EXPORTS` and a parametrised `worlds` fixture yielding each
of Aurvantis, Pangrella and the synthetic world through `load_cached`, with the ids
`aurvantis`, `pangrella`, `synthetic`. Additions only; nothing existing changed. The World
is the shared cached object — tests read it and must not mutate it.
`tests/test_harness_worlds.py` proves each world loads, has settlements and people with
places, starts a campaign and round-trips; and that the synthetic world keeps the shapes
above (kind equals scale, real roles, alternate fact keys, a mileage-free route read as
`derived`, one port, one cast-less village, local name pools).

### The Bobby replay corpus: `tests/replays/bobby-2026-09-28/`

Extracted read-only from `%LOCALAPPDATA%\PathfinderGM\campaigns\bobby.json` and `.1`–`.3`
(the shell could see them; per the sandbox note in memory, this is the view this session's
test server wrote to, which is where the playtest was played). `turns.json` holds the 13
player lines with their beats, `said`/`added` records and turn-log entries (plan intents,
outcomes, rejections, reading, prose repairs, mention and speech-tag counts; raw model
replies left out). `saves.json` holds the scene's people and the PC's prepared spells and
spellbook at each of the four files. `cases.json` names eleven cases:

| Case | Item | Turn | Evidence the test checks |
|---|---|---|---|
| `drenn-hails` | 13 | 4 | two `said` records `who: c4, to: you`; `hails_tagged == []`, `hails_guessed == []` |
| `watchman-face-through` | 4 | 3 | beats 1–2 say "watchman", never "through"; beat 3 says "the way through" and carries the spliced face |
| `crossroads-refused-but-moved` | 17.5 | 6 | every travel/found refused, no move effect; prose "You are standing where the paths diverge." |
| `path-away-refused-but-moved` | 17.5 | 7 | same; prose "You are now on the outskirts" |
| `leave-village-stopped` | 16 | 5 | reading `leave: outside it`; travel to the way in; `met: patrol`, "You get no further."; prose arrives |
| `forest-filed-under-vormoor` | 20 | 9 | biome forest at `bde94b038cba~forest:the-approach` |
| `watchman-line-booked-as-bobby` | 6 | 3 | a `say` with words the player never typed, told "Bobby speaks" |
| `girl-spawned-from-ask-about` | 5 | 3 | reading target "him"; spawn "girl", engaged |
| `unprepared-burning-hands` | 21.3 | 12 | 7 legality refusals over 7 attempts and two models; degraded to `narrate_only`; `.3` has `prepared: {}` with Burning Hands in the book |
| `tree-tops-false-claim` | 21.5 | 12 | nobody-reacts repair: "produce a tree tops" |
| `spells-tab-no-targets` | 22 | 13 | `/api/cast` outcome `targets: []`, one roll of 1, tell ends "1d4 — 1."; prose "his face blackened by soot"; c8 at 4/4 |

`tests/replays/__init__.py` is the loader (`turns`, `turn`, `saves`, `save`, `case`,
`beat_text`, `said`, `outcomes`). `tests/test_replay_bobby_corpus.py` checks the corpus
loads and that each case carries its evidence. These tests assert the recording, not the
code, so they pass today and keep passing after the fixes; G2's replay proofs are separate
tests that run the fixed detectors over the same beats.

**Not recoverable from these files:** item 14 (Drenn with no square beside the player).
All four saves were written after the party had reached the forest.

**Committing it is the owner's call** (the folder's README says why: the repository is
public and `tests/test_replay_corpus.py` records "never a player's saves"). It is not
committed.

`tests/test_replay_corpus.py` already existed (the audit-recording corpus in
`tests/replay/`), so the new test file is `test_replay_bobby_corpus.py` rather than the name
the task suggested.

### Audit scripts: `tools/narrator_audit.py`

Three scripts added to `SCRIPTS`; nothing else in the tool changed, and none was run (they
need Ollama).

- `leave-town` (items 16, 17, 19, 20): leave and stand outside; get a bearing; the nearest
  crossroads and its signposts; the road away until the walls are gone; the land around;
  into the nearest trees; back to the gate; the watchman again (a face kept); across town to
  the market (a walk that costs time); out by the road until nightfall.
- `market-seek` (items 5, 9): ask about the herb girl in the market; go and find her; ask what
  she sells and her name; ask about the old man who mends nets by the water; go and find him
  (the spawn honours "old man"); find whoever runs the market.
- `cast-area` (items 21, 22): into the empty air (a roll that reaches nobody is told so); at
  the nearest man; at two together; into the dry brush; Sleep on the crowd (unprepared: one
  refusal); stand and watch.

Two things the live queue needs to know:

- **`--world` is parsed and ignored.** `audit()` takes a `world` argument and never uses it;
  every run starts on `settings.WORLD_EXPORT` (Aurvantis). G2's "three worlds" cannot be
  run through this tool until that is wired (a tools-only change, for whichever Phase-1/2
  task owns the live queue).
- **`cast-area` needs a caster with a book.** All three pregens have empty spellbooks
  (`fixtures/pc-thessaly.json` is a wizard with none). Run it with `--character` pointing at
  a wizard whose book holds Burning Hands (prepared) and Sleep (not prepared), for instance a
  copy of Bobby's sheet from the character shelf. Until Lane E's default preparation lands,
  every cast line will be the unprepared refusal.

### `starts` — the steps, because the tool cannot run it

`audit()` plays N turns of one campaign, begun with `begin_with(load_pc(character))`, whose
campaign id is the character's slug and whose opening seed comes from that id (item 3's
cause). Thirty runs of the same character therefore give one start thirty times. The script
needs thirty **fresh** campaigns, which the tool cannot express. Intended steps, for the
live queue once Lane C's per-campaign seed exists:

1. For each of the three worlds, and for seeds 1–30: start a new campaign with a fresh seed
   and a distinct campaign id, rotating the three pregens and at least seven backgrounds
   (bonesetter, pit fighter, caravan hand, ferryman, gate watch, innkeeper's child,
   thief-taker).
2. Record, with no model turn yet: start settlement (id, name, scale), start kind (the
   start document's id), where (town / tavern / road), the opening's first named person,
   who each background tie names, and whether a scheme opened at hour zero.
3. Play two turns: "I look around and take stock of where I am." then "I ask the person
   nearest me what is going on here." Score both with `narration.review`.
4. Measure (G2): at least 5 distinct start settlements and at least 8 distinct start kinds
   across the 30 seeds; no opening in a village or town using city, sprawling, metropolis,
   tens of thousands, districts, thoroughfares or crowds; the first named person spread
   across the cast (item 8: Drenn Ironvale in every Aurvantis run today); background-tied
   people greet the player as known.
5. Run serially on a quiet Ollama, one server per port, and write the counts here.

## Files

Created: `fixtures/synthetic-world.json`, `tests/test_harness_worlds.py`,
`tests/replays/__init__.py`, `tests/replays/bobby-2026-09-28/{turns.json, saves.json,
cases.json, README.md}`, `tests/test_replay_bobby_corpus.py`, this file.
Changed: `tests/conftest.py` (appended the `worlds` fixture), `tools/narrator_audit.py`
(three entries in `SCRIPTS`). No product module was touched; nothing is committed.
