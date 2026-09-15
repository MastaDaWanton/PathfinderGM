# Fixtures

`pangrella-campaign.json` and `pangrella-campaign.sqlite3` are a **real** World Bible
export of the sample world that ships with the app — not mock data. Written by World Bible
1.9.0, schema `1.3`.

- 74 entities (1 world, 2 continents, 6 peoples, 6 nations, 12 settlements, 47 characters)
- 111 chronology events, most with full accounts
- 5 trade routes with acquisition / demand / conduct / friction
- 5 factions with aim / method / foothold / weakness
- 6 names in `unwritten` — mentioned but never written up

Develop and test against these rather than inventing fixtures: they carry the real
irregularities you have to survive, including `null` entity ids on unwritten figures, five
undated events, and prose that names things which do not exist.

To refresh, or to export a different world: open the world in World Bible and press
**Export for play**, or run in that repo —

```python
from agent_engine.campaign_export import write_bundle, write_sqlite
write_bundle('samples/pangrella', 'pangrella-campaign.json')
write_sqlite('samples/pangrella', 'pangrella-campaign.sqlite3')
```

`aurvantis-campaign.json` / `.sqlite3` are a **second** real export, added 2026-09-12,
and the one to test race handling against. Pangrella has a single people; Aurvantis has
sixteen, written by a different generator, and every race-card bug World Bible has fixed
so far was invisible until a second world existed. It carries the awkward cases on
purpose:

- **Human** and **Halfling** produce no racial trait at all, correctly — their own
  anatomy says "Ordinary five senses, no innate darkvision or scent". A race with nothing
  mechanical is a real answer, not a malformed card.
- **Undine** states underwater breathing in words the cue table does not recognise
  ("Can hold breath far longer than a human, sees clearly underwater"). See the ask at the
  end of `../docs/races-for-pathfinder-gm.md` in the World Bible repo.
- **Vanara** is the only card with a `movement` line, and it is the one race whose
  anatomy actually describes moving.
- All sixteen carry a well-formed `strengths[]` / `weakness` array.

Both carry `play.places[]` as of schema 1.3 — the places inside each settlement, with
`exits[]` as adjacency and no distances anywhere. Pangrella has 112 across 12 settlements,
Aurvantis 509 across 64. This replaces door one (the implied-spot table); doors two
(founded) and three (ventured) are untouched, and anything World Bible writes says
`origin: "world"` so the two authors never get confused.

The format is documented in `../docs/campaign-format.md`.
