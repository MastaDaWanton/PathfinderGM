# Fixtures

`pangrella-campaign.json` and `pangrella-campaign.sqlite3` are a **real** World Bible
export of the sample world that ships with the app — not mock data. Written by World Bible
1.4.0, schema `1.0`.

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

The format is documented in `../docs/campaign-format.md`.
