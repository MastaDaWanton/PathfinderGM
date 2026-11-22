# Skills-mind lane, 2026-11-22 (round 2): research notes

The owner asked for "the skill checks". This lane covers the mind, social and knowledge
skills. The rows are in `content/rules/skill-uses.json` and the doors in
`rules/skilluses.py` (the "Round 2" section).

## Rules text

All rules text comes from d20pfsrd.com/skills/<skill>, read 2026-11-22. Each row quotes it
in `source`.

| Skill | What was used |
|---|---|
| Sense Motive | hunch DC 20; sense enchantment DC 25, or 15 if dominated; "Retry? No, though you may make a Sense Motive check for each Bluff check made against you"; at least 1 minute |
| Knowledge | answering a question: DC 10, 15, or 20 to 30; no action; no retry; untrained, no DC above 10 |
| Appraise | DC 20 for a common item; made by 5, magic or not; missed by less than 5, within 20%; missed by 5 or more, "wildly inaccurate"; a standard action; asking again gives the same result |
| Spellcraft | identify a spell as it is cast: 15 + spell level, no action, "clearly see", no retry; identify a magic item: 15 + caster level, once per day |
| Perform | earn money by the table: DC 10 1d10 cp, 15 1d10 sp, 20 3d10 sp, 25 1d6 gp, 30 3d6 gp; +2 to the DC for each previous failure |
| Use Magic Device | wand DC 20, scroll 20 + caster level. **Not built**: the game has no wand or scroll item. Potions are the only item that holds a spell (`goods.alchemy_stock`). |
| Linguistics | one language per rank; decipher DC 20/25/30; forgery opposed. **Not built**: the game has no language barrier and no forged or foreign writing. |
| Handle Animal | handle DC 10 (move), push DC 25 (full-round), teach 15/20. **Not built**: see "Refused" below. |

## Prior art

- **Who is lying is authored data, not inference.** ZA/UM's dev blog, "On skill checks"
  (discoelysium.com/devblog/2016/09/19/on-skill-checks), describes passive checks as extra
  voices written into specific dialogue lines. Its lie example is a check on an authored
  line. I could not confirm from a primary source which skill Disco Elysium uses for lie
  detection: a GamePressure guide says Drama, and the dev blog does not name one. Here,
  each scheme's secret card names who keeps it (`kept_by`), and the engine reads that
  field. `the-sealed-letter`'s clerk is listed in his secret card and does not know what
  he carries. He shows why reading the facts would mark the wrong person as a liar.
- **Owlcat folded Sense Motive into Perception and dropped active Knowledge.** The Wrath of
  the Righteous fan wiki (pathfinderwrathoftherighteous.wiki.fextralife.com/Skills) says
  Perception covers telling when people are lying. A Kingmaker player guide says Owlcat
  chose not to let characters find things out actively with Knowledge. Both are
  secondary sources, and I found no Owlcat changelog. We diverge on purpose: the world
  export is a large record of facts, and the /gm door already sorts them into tiers
  (`play/gm_search.py`). An active Knowledge check can answer from that record without
  inventing anything.
- **The tiers already existed.** The /gm door uses Knowledge (local)'s own DCs: rulers and
  laws DC 10, common rumour DC 15, hidden organisations DC 20 (docs/knowledge-and-doors.md).
  The in-play answer uses the same DCs, so the two doors agree.

## Refused, with reasons

- **Handle Animal on a companion's turn.** The owner ruled on 2026-10-01 that companions
  obey spoken orders in character, with no control interface (gm/companions.py). A roll
  that decides whether an animal companion obeys would replace that ruling. Owner call.
- **Linguistics languages known.** A list of languages would have nothing to read it:
  nothing in the engine bars speech or text by language. That is the promise the honesty
  ledger forbids.

## Owner calls made by the book (RAW)

1. **Sense Motive retry.** One read of a person a day (`knows.sensed.<ref>`, 14,400
   rounds). The CRB allows a new check for each Bluff made against you, but the engine has
   no event for "this NPC just lied again".
2. **A wildly inaccurate appraisal.** The CRB says "subject to GM discretion". The engine
   uses a hidden roll between 0.4 and 2.5 times the true worth (the row's `wild`).
3. **Perform pay outside a prosperous city.** The CRB states pay only for "a prosperous
   city". The table applies in any settlement.
4. **Which Knowledge answers a question.** The field comes from the record's fact keys
   (the row's `fields`). For example, Cosmology is filed under planes and Hierarchy under
   nobility. The plan's own field is used only when the subject has facts in it.
5. **A person's `Secret` is never lore.** The CRB's Knowledge (local) covers "notable
   figures", not their secrets.
6. **A cast nobody identified names no spell.** The cast's tell replaces the spell's name
   with "a spell". The effect records keep the spell id for the engine.
