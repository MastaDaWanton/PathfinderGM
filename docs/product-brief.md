# What we are building

Captured at the end of the World Bible session, in the user's own words and from their own
reference point. The open questions at the bottom are genuinely open — ask rather than
assume.

## The one-line version

**A Pathfinder 1e game you play like OOC.ai — a GM that knows your world, runs the real
rules, and does the bookkeeping — all running locally on your own machine.**

## The reference: OOC.ai

> "OOC: The Playable Anime"

https://ooc.ai — a hosted platform of user-created, AI-narrated interactive stories.
Observed directly rather than described second-hand:

- **Everything is a "title"** — a self-contained playable scenario with its own premise,
  setting and cast. *Lumencia Academy* ("an imperial academy of sword and sorcery"),
  *Dice of Fate: A reverse Isekai* ("Become a Constellation. Watch over your character and
  shape who they become").
- **Play is a chat loop** — free text, with slash commands as a recent feature. The app's
  navigation splits **Story** and **Character**, so the sheet is a first-class view beside
  the narrative rather than buried in it.
- **Story-first, rules-light.** One title is billed as its "First AIRPG", so mechanics are
  a new arrival there, not the foundation.
- **A marketplace** — rankings, trending, tags, certified creators, a credit currency, play
  counts in the millions. Hosted, phone-first, metered per interaction.

Take the *feel*: a story you drop into and keep playing, that answers anything you type,
with your character always in view.

## The three things that make this different

### 1. Pathfinder 1e underneath — the actual thesis

Not narration that sounds like a game. The rules genuinely run.

**1e specifically, and knowingly.** In the user's words: it *"has a lot more GM workload but
is widely considered more fun to play."* That sentence is the product. The reason 1e is
heavy — tracked buffs, stacking modifiers, iterative attacks, size and manoeuvre rules,
crafting and item pricing, encounter maths — is exactly the burden a computer should carry.
**The app should absorb the workload that makes 1e hard to run, and leave the depth that
makes it fun to play.** Any design choice that trades away rules depth to make the app
simpler is going the wrong way; the complexity is the point, it just should not fall on a
person.

### 2. A GM with working knowledge of a real world

Not a world improvised turn by turn. World Bible supplies a finished, internally consistent
setting — 74 entities, 111 dated events, real trade routes and factions in the sample —
with durable ids, containment, cross-references and a system-agnostic play layer. The GM
should answer "who runs this town?" and "what happened here?" from the book, not from
invention. See `from-world-bible.md` and `campaign-format.md`; `fixtures/` has a real one.

### 3. It runs locally

Ollama on the user's own machine. No account, no metering, no data leaving the box —
a hard requirement carried over from World Bible.

This is the sharpest constraint in the project. The reference product is built on metered
hosted inference answering instantly; a local model takes seconds to minutes. **The pacing
of play has to be designed around that, not patched over afterwards.** It also cuts the
other way in our favour: rules resolution is code, not generation. Anything the rules can
decide should be decided by the rules — instant, exact, free — with the model reserved for
narration and NPC voice.

## The rules content is open, and machine-readable

Pathfinder 1e is Open Game Content under the **OGL 1.0a**, which is what makes this legal
and practical. Monsters, items, spells, classes and feats are all available:

| Source | What it gives |
|---|---|
| [d20PFSRD](https://www.d20pfsrd.com/) | The fullest 1e SRD. Its [bestiary](https://www.d20pfsrd.com/bestiary/), [magic item](https://www.d20pfsrd.com/magic-items/magic-items-db/) and spell databases export to CSV, and there are [bulk downloads](https://www.d20pfsrd.com/extras/downloads/). Names are altered in places for OGL compliance — expect that when matching. |
| [Pathfinder Reference Document](https://legacy.aonprd.com/indices/bestiary.html) | Paizo's own reference via Archives of Nethys, useful for checking a stat block against the source of truth. |
| [Noobulater/pathfinder-srd](https://github.com/Noobulater/pathfinder-srd) | The SRD as JSON. Verify coverage and freshness before depending on it. |

Evaluate these properly before committing — completeness, licence attribution
requirements, and how much cleaning each needs. **The OGL requires the licence to travel
with the content**, so plan attribution into whatever ships.

## Open questions — settle these first

The user was asked which aspects of OOC.ai they wanted and gave no preference, so these are
undecided:

1. **How deep does resolution go?** Full 1e combat with a grid, initiative, AoOs and
   conditions — or narrative scenes where the rules are consulted at the moments that turn
   on them?
2. **Solo or party?** One character with the app as GM, or a party it also voices?
3. **What is a "title" here?** Does the player pick a starting situation in their world, or
   does the app propose scenarios from what the world already holds — a faction's aim, a
   route's friction, an event's aftermath?
4. **Character creation** — full 1e build (race, class, feats, skills, gear), or a guided
   subset to start?
5. **Pacing against a local model.** Likely the biggest design constraint in the app: what
   is generated, what is computed, and what is pre-generated between sessions?
