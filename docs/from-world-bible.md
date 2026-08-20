# Handoff: what World Bible is, and what it hands you

Written at the end of the World Bible session that built the export, so the next
conversation starts warm. Read `campaign-format.md` next — that is the actual contract.

## What World Bible is

A Django + Electron desktop app that generates internally-consistent worlds for fiction and
tabletop play using local Ollama models. Repo: `H:\coding\WorldBible0.0`, released at
https://github.com/MastaDaWanton/World-Bible (currently 1.4.0).

- **File-native.** A world is a directory of JSON files. The files *are* the data — there
  is no database copy. Worlds live in `Documents\World Bibles\`.
- **Six tiers**, each generated knowing everything above it:
  `WORLD → CONTINENT → {PEOPLE, NATION} → CITY → CHARACTER`. `CITY` covers every settlement
  scale from metropolis to outpost. `PEOPLE` is an ethnic group, not a place — it may span
  several nations or belong to none.
- **A global layer on top:** a chronology of dated events with full accounts, trade routes
  between settlements, and cross-border factions.
- Generating a world takes about an hour on a local model. **A finished sample ships with
  the app**, and a copy of it is in `fixtures/` here.

## What you get

`Export for play` in World Bible writes two files into the world's folder:

- `<world>-campaign.json` — the contract. Self-contained, versioned, readable anywhere.
- `<world>-campaign.sqlite3` — the same data in tables, for querying rather than walking.

Both are in `fixtures/`, generated from the shipped sample world (Pangrella): 74 entities,
111 events, 5 trade routes, 5 factions, 47 characters.

Exporting is instant and calls no model. It is a full snapshot every time — there is no
incremental sync, so diff by `id` if you need to know what changed.

## The three things that matter most

1. **Save state against `id`, never a name or path.** Every entity carries a durable
   12-character id, written into the world's own files once and never changed. Renaming is
   a supported operation in World Bible that rewrites names *and folder paths* everywhere.
   A campaign that recorded "the party is in Mirabalos" by name breaks the first time the
   author renames that city.

2. **Check `schema_version` before reading anything.** Minor bumps add fields you can
   ignore; a major bump means refuse to load rather than guess.

3. **The `play` layer carries no rules.** `settlements`, `cast`, `travel`, `conflicts`,
   `timeline` — the shapes a session needs, keyed by the same ids, with no levels, stat
   blocks, encounter budgets or dice. **Turning any of it into Pathfinder is this app's
   job.** That boundary was chosen deliberately: baking one ruleset into World Bible would
   be a promise it cannot keep, and there is a test in that repo asserting no rules
   vocabulary leaks in.

## Known gaps in the data

Be defensive about these. They are real, they are documented, and they are not yours to fix
from here:

- **Section rewrites can invent places and people.** The faction rebuild is grounded
  against the world's real names, but a section rewrite is not — one produced "Aviari's
  Spire" and "Elyria's Forge", neither of which exists. Treat any name in prose as
  possibly fictional-within-the-fiction.
- **`entity_id` may be `null`** on a chronology figure or a route endpoint. That means the
  thing is named but has never been written up. Those names are collected in `unwritten`
  — offer them as blanks to fill rather than treating the reference as a dead end.
- **Missing-place detection only reads structured fields** (route endpoints). A place
  invented purely inside a faction's prose is not caught, so `unwritten` is not exhaustive.
- **No maps, no coordinates, no distances.** Places relate through containment
  (`parent_id`) and trade (`play.travel`), not geometry. If the game needs travel time, it
  has to invent it.
- **Years can be `null`** for undated events; the timeline sorts those last.

## Things worth stealing

Patterns from World Bible that solved problems this app will hit too:

- **Per-field locks.** A generated entry usually has one part worth keeping and three worth
  another try. Locking the whole entry to protect one of them means never improving the
  rest, so every field — and every individual moment in an event — locks on its own, and
  regeneration skips what is pinned.
- **One instruction box, two buttons.** "Rewrite" replaces, "More detail" appends, and both
  obey the same typed instruction. Users type what they want and press whichever button;
  having one of the two ignore the box was a real bug.
- **Cancellable background jobs with live progress.** Generation blocks nothing; every long
  job can be cancelled and reports where it is.
- **Snapshot before every write.** Every save and regeneration writes a history snapshot
  first, so any step is undoable.
- **Pin what does not exist yet.** When generation names something that has no entry,
  record it as pending with a parent rather than dropping it, and offer to create it later.
