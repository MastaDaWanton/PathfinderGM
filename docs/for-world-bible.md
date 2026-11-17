# What Pathfinder GM needs from World Bible

**Written 2026-09-10, from the Pathfinder GM side.** The mirror of
`docs/from-world-bible.md`, which describes what World Bible hands over today. This one
describes what it does not hand over yet, in the order it would be easiest to build.

Canonical copy: `H:\coding\PathfinderGM\docs\for-world-bible.md` (under version control).
Working copy for the World Bible side: `H:\coding\WorldBible0.0\docs\for-pathfinder-gm.md`.
If they disagree, the Pathfinder GM copy is right — it sits next to the consumer that has
to eat this data.

## How to use this document

You are probably a session working in `H:\coding\WorldBible0.0`. You do not need to read
the Pathfinder GM codebase to do any of this work, and you should not need to run it.
Everything you need is here:

1. Read **The boundary** and **The GAS framework** first. They are short, and every
   schema below is shaped by them. Getting a field's *type* right and its *spirit* wrong
   is the failure mode — a `size` field containing `-2` instead of `"small"` passes JSON
   validation and breaks the consumer's whole design.
2. Pick the lowest-numbered ask that is not done.
3. Build it, ship it in the export, and check it against **Done when** at the end of that
   section.

Each ask carries: why we want it, the exact schema, a worked example against the shipped
Pangrella sample, what Pathfinder GM does today in its absence, and what "done" means.

**The consumer already reads asks 1 and 2 when they are present.** Those two are not
speculative work — write the key and the app switches from derived to authored on the next
import, with no change on our side.

---

## The boundary that must not move

`docs/campaign-format.md` states it and there is a test in the World Bible repo asserting
it: **the `play` layer carries no rules.** No levels, no stat blocks, no encounter
budgets, no dice, no DCs, no modifiers, no prices. Turning any of it into Pathfinder is
Pathfinder GM's job.

This was chosen deliberately, and it is not a limitation to route around. Baking one
ruleset into World Bible would be a promise it cannot keep — the same world should be
playable under a different ruleset by a different consumer.

So the rule for every field in every schema below:

> **World Bible supplies words. Pathfinder GM prices them.**

A people's size is `"small"`, never `-2 Strength`. A race's sight is
`"they see in the dark as well as in daylight"`, never `darkvision 60 ft.`. A situation
card's fact is a sentence the narrator may state as true, never a clock with a number on
it. If you find yourself wanting to write a number, the field is wrong — write the word
that implies it and let the consumer's own tables do the arithmetic.

There is exactly one exception, and it is not a rule: **durable ids**. Those are yours,
they are already how everything is referenced, and nothing works without them.

---

## The GAS framework, and why the shape of your data matters

Pathfinder GM's architecture converged with Unreal's **Gameplay Ability System** before
anyone here knew its name. GAS is where the design gets checked, not where it came from.
You do not need to know GAS to build any of this, but you do need to know the shape,
because it explains why every schema below looks the way it does.

### The one sentence

**The model proposes, the engine disposes.**

A local language model narrates the game. A rules engine owns every number. The model can
suggest that something happens; only the engine decides whether it did, and by how much.
Nothing a model writes lands on a character sheet without a document behind it.

### The three laws

Everything that changes a number, grants a state, or reaches the narrator obeys these.

**1. One vocabulary.** Every state anything can be in is a **hierarchical, dot-separated
tag**:

```
state.down.dead          buff.stance.blood-rage        attitude.friendly
state.fear.shaken        knows.way-past-gate           situation.world.salt-levy
holds.place.marras-house role.guard                    state.wanted.5bbd0c40345f
```

Systems ask **prefix questions** — `has_state("state.down")` answers for
`state.down.dead` and `state.down.dying` alike — and never compare condition strings.
Unknown keys self-tag, so homebrew and world-authored content participate without being
registered anywhere first.

*What this means for you:* any tag you write in an export must be dot-separated and
hierarchical, general-to-specific, lower-case, hyphens inside a segment. Put the world's
own id in the leaf when the tag is about one thing (`situation.world.salt-levy`). Never
invent a tag family that already exists under another name.

**2. One applicator.** Every change to a number travels as an **effect** — a document
with a duration, modifiers, granted tags, a stacking policy and a source. Remove the
effect and its contribution evaporates; nothing is ever "added and hopefully subtracted".
One store, one ticker, one modifier funnel.

*What this means for you:* nothing you ship is applied directly to anything. It becomes a
document the engine reads, validates, and turns into effects itself. That is why your
side can stay entirely descriptive.

**3. Severed tells.** Every effect emits a **tell** — one prose-ready sentence of what the
engine decided. The narrator is fed tells and nothing else about mechanics. Prose that
states a mechanic no tell backs is an "outcome claim" and gets cut by a scrubber.

*What this means for you:* the sentences you write in `facts[]`, `about`, `body[]` and
`senses[]` are handed to a narrator as **things it may state as true**. They must read as
prose, be self-contained, and contain no mechanics. One sentence per entry. A fact with a
digit in it is refused by the consumer's validator.

### The Rosetta, if you ever read GAS material

| GAS | Pathfinder GM |
|---|---|
| GameplayTags | the tag vocabulary (`rules/states.py`) |
| GameplayEffect | `ActiveEffect` |
| GameplayAbility | ability documents |
| AbilitySystemComponent | `Actor.apply_effect` / `Actor.tick_effects` |
| Attribute aggregator | typed modifiers + stacking channels |
| GameplayCues | tells |
| Server authority | model proposes, engine disposes |

### Deliberately refused from GAS — do not import these

- **Prediction and replication.** A third of GAS is netcode for a problem a
  single-player, single-authority, turn-based game does not have.
- **Additive-then-multiplicative aggregation.** Pathfinder 1e's typed bonuses are the
  rule instead: same named type takes the best, dodge and circumstance and untyped stack,
  penalties always stack.
- **Cosmetic fire-and-forget cues.** The presentation layer here is a language model that
  will invent a belt if you let it. Tells *constrain* the narrator; they never decorate.

### The one idea to carry into every schema below

Everything the game runs on is **a document**: a spell, a feat, a class ability, a race, a
situation card, a place, a scheme. Same grammar family, same treatment — a validator
refuses a bad one **with the fix named**, and no model ever authors a number.

When you add a list to the export, you are adding a new kind of document. It should look
like the others: a durable `id`, a human `name` or `title`, and a body made of words.

---

## Delivery: where it goes and how to ship it

Everything below is a new key inside the existing `play` object of
`<world>-campaign.json`, written by the same exporter, alongside `settlements`, `cast`,
`travel`, `conflicts` and `timeline`. Same file, same builder, same instant no-model
export.

```json
{
  "schema_version": "1.1",
  "play": {
    "settlements": [ ... ],
    "cast": [ ... ],
    "races":  [ ... ],
    "cards":  [ ... ],
    "places": [ ... ]
  }
}
```

**Bump `schema_version` MINOR for every one of these.** They only add keys, and the rule
in `docs/campaign-format.md` is ordinary semver: MINOR adds fields a consumer may ignore,
MAJOR changes or removes the meaning of an existing field and must be refused by a
consumer not written for it. None of the asks below is a MAJOR change. If you find
yourself changing the meaning of an existing field, stop and raise it — a MAJOR bump means
every existing campaign save refuses to load.

**Ids.** Every entity already carries a durable 12-character hex id. New documents get
their own ids in their own namespace: a slug is fine and preferable for things a human
will read in a file (`salt-levy`, `korvu`, `the-docks`), as long as it is unique within
the export and stable across re-exports. **Stability matters more than beauty** — a
campaign save keys off these, and an id that changes on re-export silently detaches
whatever the player had done with it.

**The export must stay a projection.** Exporting is instant and calls no model today, and
that should remain true. If a list needs generation, generate it into the world's own
files as a normal World Bible entity or section — where the author can see it, lock
fields, and regenerate it — and let the exporter project it. **Do not generate at export
time.** An export that calls a model is an export that is slow, non-deterministic, and
different every time it runs.

**Also write it to the sqlite3 sibling**, one table per list, same builder.

**How to check your work without running Pathfinder GM.** For asks 1 and 2, the consumer
falls back to deriving the list when the key is absent, so the fastest check is: does your
authored list look like a *better* version of what the fallback would have produced? The
fallbacks are described in each section. For all asks, re-export the shipped Pangrella
sample and read the JSON — it is the same world Pathfinder GM tests against
(`fixtures/pangrella-campaign.json`: 74 entities, 111 events, 5 trade routes, 5 factions,
47 characters).

---

# THE LEDGER: what is asked, what is delivered, what is next

**Kept current at the top of the file, because an ask list whose statuses are stale is
worse than none — somebody builds a thing that shipped a month ago.** Last read
2026-09-16.

| # | Ask | State |
|---|---|---|
| 1 | `play.races[]` | **delivered** (schema 1.1, extended 1.2). Read; 16 cards in Aurvantis |
| 2 | `play.cards[]` | **delivered** (1.1). 22 cards in Pangrella |
| 3 | `play.places[]` | **delivered** (1.3), tier 1 and tier 2 both read since 2026-09-16 |
| 4 | Resources, materials, ingredients | **not started.** Still the largest gap |
| 5 | `play.schemes[]` | **not started, and deliberately last** |
| 6 | `play.travel[].miles` | **not started.** 0 of 5 legs in Pangrella carry one |
| 7 | `play.names[]` | **built, and empty.** See below |
| 8 | **Where the water is** | **new, and now the sharpest.** See below |
| 9 | A vocabulary for versatile and lucky | **this side's**, listed so it is not lost |
| 13 | Each nation's coin | **new, 2026-10-17.** Names only, no numbers. See below |
| 14 | No Pathfinder setting terms in world prose | **new, 2026-10-30.** Aurvantis says "the First World" twice. See below |
| 15 | `fixtures` on a place | **new, 2026-11-11.** Optional; the consumer reads it today. See below |

## 7. `play.names[]` — naming material (built; needs back-filling)

The supplier built this the same day it was asked for, in the shape asked for:

```json
{"home_id": "5bbd0c40345f", "family": ["Sootspar", "Halloran"], "given": ["Bregan"]}
```

`people_id` for a people, `home_id` for a settlement, ten to twenty of each. **Both
shipped worlds export `"names": []`** until they are regenerated or back-filled, which
needs about eighty local model calls on the supplier's side.

Why it matters more than it sounds: this app now puts a keeper in every place that sells
something — 88 of Pangrella's 192 places, seven per settlement — and names them from the
world's own stock. The supplier's own measurement is worse than the one that prompted the
ask: **ten distinct surnames across 256 characters** in Aurvantis. Harvesting the cast was
never going to work. Until the pools land, a town's shopkeepers share two family names.

## 8. Where the water is

**The ruling (2026-09-16): continents are separated by water unless otherwise specified.**
This app implements that off the tree the export already carries, so nothing is blocked —
but two things would make it real rather than inferred.

**8a. Which settlements are on the water.** Nothing in the export says. Measured: Aurvantis
has 11 ports out of 64, and every one of them is this app's own cue table minting a docks
out of the settlement's prose ("a port town with a quay"). **Pangrella has none out of
12** — and the reason is a genuine interaction worth knowing: Pangrella's places are
authored, an authored list replaces the generated one by design, and so the cue that was
the only way to spot a port never fires. *Authoring places removed the one signal this app
had for what is coastal.*

Either shape works and the first is smaller:

```json
"settlements": [{"id": "...", "coastal": true, "on": "sea"}]
```
`on` is one of `sea`, `river`, `lake` — a river port is not a deep-water port — or omit
the whole key for inland, which is the safe default and what everything reads today.

Or simply **author a docks place** in coastal settlements; this app already knows that
word and will read it with no change at either end.

**8b. Which routes are sea and which are land.** `play.travel[]` is an edge list of trade
relationships, and this app had been reading every one as a road. Measured: **48 of
Aurvantis's 48 legs cross a continent boundary**, and 2 of Pangrella's 5. That is not a
defect in the export — "Brackgate sells tempered steel to Ashwatch" was never a claim that
you can walk there — but it means every journey in Aurvantis is currently a sea crossing by
inference. One optional field settles it per route:

```json
"travel": [{"from_id": "...", "to_id": "...", "by": "sea"}]
```
`by` is `road`, `sea` or `river`. **A stated `road` is already the "otherwise specified"**
and is read today: a world that writes a road between two landmasses has said there is an
isthmus or a causeway, and a thing the world says beats a thing this app worked out.

**8c. Ports and the ships in them (asked 2026-11-13, when passage became playable).**
Passage is bought at a port and sailed to another (docs/ships.md, "Taking passage"). Until
an export says which settlements are ports, this app decides it the way 8a describes: a
settlement is a port when its places include the docks, the harbour, the quay or the
wharf — authored, or minted by the cue table from the settlement's own words ("port",
"harbour", "quay", "ships", "fishing"…). Measured on the shipped exports that day:
**Pangrella has 4 ports of 12** (Mirabalos and Elyrielle on one continent, Zhilvarnia and
Khalmorin on the other), Aurvantis 23 of 64. Between ports on different continents with no
stated route, this app offers a passage of its own and prices its days by the tree; that
is how Pangrella's two continents are reachable by ship from either side. The ask, in
order of value:

```json
"settlements": [{"id": "...", "port": true, "on": "sea"}],
"travel":      [{"from_id": "...", "to_id": "...", "by": "sea", "miles": 420}]
```
`port` (with 8a's `on`) beats the docks cue outright. A stated sea route with `miles`
replaces the derived passage between those two ports, so its days and its fare (1 sp a
mile a head, CRB Table 6-9) are the world's rather than the tree's. Optionally
`"vessels": [{"kind": "sailing ship", "name": "..."}]` on a port — `kind` one of Table
7-49's five — would name the regulars this app otherwise derives from the port's id.
**Sea danger** is ask 16's `volatility`, read off the two ports' own ratings (the worse
of the two) until a world has sea regions to put it on.

**8d. Where an inland crossing boards (2026-11-14).** A stated sea route from an inland
town is now walked to a harbour first, by the quickest stated road to a port. Measured on
Aurvantis: 13 of 52 inland sea legs (and all 3 of Pangrella's) have **no road to any
port**, so this app walks a derived day to a coast it cannot name. Either fixes it, the
first smaller: `"leaves_from_id": "<port settlement id>"` on the sea route, or a stated
road from that town to a port.

**Not asked for:** coastlines as geometry, sea routes as waypoints, or anything with
coordinates in it. The boundary holds — the world says which places touch water, and this
app decides what crossing it costs.

## 9. Versatile and lucky — this side's gap, recorded here so it is not lost

The supplier is right that two of the three race cards this app called content problems are
not. A Human "physically unremarkable and highly variable" and a Halfling with "unusually
good luck" produce no usable trait because **this app's cue vocabulary has twelve words and
none of them means versatile or lucky** — and both are expressible in 1e (a bonus feat and
a skill rank; a +1 luck bonus on all saves). That is work for this side, not content for
theirs.

## 10. The SQLite mirror is a version behind the JSON

Small, mechanical, and the kind of thing that costs somebody a day six months from now.

The 1.5 JSON carries three new fields. The SQLite mirror in the same export carries none
of them. Checked on the shipped pair:

```
races        id, name, people_id, size, speed, body, senses, movement, about,
             strengths, weakness          <- no `grants`
trade_routes id, origin, destination, origin_id, destination_id, commodity,
             sought_as, acquisition, demand, conduct, friction   <- no `by`
```

So a consumer that reads the database gets a 1.4 world stamped 1.5, and gets it silently.
That is precisely the failure the version number exists to prevent — `schema_version` is
a promise about the export, and half the export is not keeping it.

Pathfinder GM reads the JSON and is not affected. This is filed because the next consumer
will not be, and because the two halves drifting apart once means the mechanism that
should have kept them together is not there.

**Done when** the two halves are generated from one description of the shape, so a field
added to one cannot be missing from the other, and `grants` and `by` are in both.

## 11. WITHDRAWN — "three races have a bite Pathfinder does not give them"

Kept as a heading rather than deleted, because the reason it was wrong is worth more than
the ask was.

For about an hour on 2026-09-16 this ledger asked the supplier to take the bite off
Aurvantis's Goblin, Half-Orc and Orc cards, on the grounds that Pathfinder gives those
races no natural attack. `check_race_cards.py` had a table of the core races to flag it.

> *"These races are specific to this world even if they are called Orcs, so it's okay if
> they're different."*

Which is this project's oldest rule — **a thing the world said beats a thing this app
worked out** — and the check was that rule backwards: measuring a world against a
rulebook it never agreed to, on the strength of a name. An Aurvantis orc is Aurvantis's.
The table is gone and the note with it.

What survives is not about the bite and is not a table. See ask 12.

## 12. Write the description from the tags, not the tags from the description

This is the one that matters, and the consumer side of it shipped on 2026-09-16.

> *"We should not need to interpret anatomy on import. We should receive exactly the
> anatomy as our engine will read it, and World Bible should also write the description
> from those tags."*

**What changed here.** When a card states `grants[]`, this app now reads the tags and
**nothing** out of the prose — not a trait, not a sense, not a natural weapon. The regex
table that used to do the interpreting is still there for a 1.4 card and is no longer
consulted for a 1.5 one. `docs/race-cues.json` gained a `grants` block listing the exact
tag names; `check_race_cards.py` validates against it and reports a tag neither side
knows rather than dropping it.

Measured the day it shipped: **all 16 Aurvantis cards produce the same tags either way**,
because the supplier generates `grants[]` by running the same vocabulary over the same
prose. So this changes nothing about today's export, on purpose. What it changes is who
is allowed to be wrong: when the generator gets better at anatomy, the engine follows
without a regex changing here, and when it gets something wrong the error is visible in a
field a person can read instead of buried in a pattern match.

**What is asked of the supplier.** Pick the tags first, from the people. Then write the
body, senses and movement sentences to describe what those tags are. Not the other way
round.

The direction matters because of what running it backwards costs, and the cost is not
that the result is wrong — a world's half-orcs may bite, and Aurvantis's do. The cost is
that **the world cannot decline.** "Sometimes visible tusks" became a bite attack, and
the only way to have had no bite was to stop describing their faces. A rule nobody can
refuse is a rule nobody chose, and by the time it reaches a character sheet there is
nothing left that says it was ever a guess.

The Goblin card is the tell. It states `natural.bite` and its body reads "A hooked beak,
strong enough to break bone" — a sentence that exists to justify the tag. Run the other
way that card would have started from "these goblins bite" and the beak would be a fact
about goblins rather than a rationalisation. Same output, and only one of them was
decided by anybody.

**Done when** `grants[]` is chosen before the prose is written, and the checker's two
cross-cover notes — a tag no sentence describes, a sentence describing a tag that is not
stated — stay at zero for reasons rather than by coincidence.

---

# The asks, easiest to hardest

## 1. `play.races[]` — the world's own peoples as playable races

**Easiest by a distance. The contract is already written, the consumer already reads it,
and the underlying data already exists in every world you generate.**

### Why

A player creating a character should pick from the peoples of *this* world, not from a
generic fantasy list. World Bible already writes a `people_anatomy` section for each
`PEOPLE` — Anatomy, Body, Senses, Lifecycle. That is a race description in everything but
name. It just has no machine-readable shape, so the consumer has to guess it out of prose.

### Shape

`play.races[]`, each entry:

| Field | Meaning |
|---|---|
| `id` | durable, unique within the export (`korvu`) |
| `name` | the people's name as the world shows it |
| `people_id` | the 12-char id of the `PEOPLE` entity this is the body of |
| `size` | `small`, `medium` or `large` — **a word, not a modifier** |
| `speed` | `slow`, `normal` or `fast` — a word |
| `body[]` | short sentences about the body plan: limbs, wings, hide, what it cannot do |
| `senses[]` | short sentences about what they perceive, and in what conditions |
| `movement[]` | short sentences about how they move: climb, swim, fly, burrow |
| `about` | one paragraph, the prose a character-creation screen shows |

### Worked example, from the shipped sample

The Korvu (`fd4449bc9a64`) carry these facts today:

```
Anatomy:   Korvu have avian-like wings and bodies.
Body:      Korvu have four limbs ending in sharp talons.
Senses:    Korvu have enhanced echolocation abilities.
Lifecycle: Female Korvu give birth to 2-4 hatchlings after a 9-month gestation period
```

which should export as:

```json
{
  "id": "korvu",
  "name": "Korvu",
  "people_id": "fd4449bc9a64",
  "size": "medium",
  "speed": "normal",
  "body": [
    "They have avian bodies and broad wings.",
    "Four limbs, each ending in sharp talons."
  ],
  "senses": [
    "They hunt and navigate by echolocation, and are not troubled by the dark."
  ],
  "movement": [
    "They fly, though not for long at a stretch."
  ],
  "about": "Nomadic pastoralists of the Pangrellan grasslands, matrilineal and clan-ranked, master auramancers working in resonant crystal — and second-class citizens among the settled powers who buy their work."
}
```

Note what did *not* happen: nobody wrote `fly 30 ft. (average)`, `+2 Dex`, `low-light
vision`, or a racial point cost. The consumer's Race Builder table does all of that from
the words — `wings` in a `movement[]` sentence becomes a flight speed priced at 4 RP
against the Advanced Race Guide.

### What Pathfinder GM does today without it

`rules/races.py:from_world` derives one race per `PEOPLE` that carries an anatomy, by
running a cue table over the raw fact prose. A `PEOPLE` **without** an anatomy is offered
as a *heritage* of some other body rather than a race, which is the right call — an ethnic
group of somebody else's body is not a separate species.

It works, but it is reading sentences written for a human reader and hoping the cue words
are in them. An authored list is better because you know which peoples are meant to be
playable and which are not, and because you can say "they cannot swim" — a negative that
no cue table will ever infer.

### Done when

- Every `PEOPLE` with a `people_anatomy` section has a `play.races[]` entry.
- A `PEOPLE` without one has **no** entry (the consumer will treat it as a heritage).
- No entry contains a digit in `size`, `speed`, `body[]`, `senses[]` or `movement[]`.
- `people_id` resolves to a real entity in `entities`.
- Re-exporting twice produces identical `id`s.

---

## 2. `play.cards[]` — situation cards

**The contract is written and the consumer already reads it. Harder than races only
because it needs judgement about *which* situations matter, rather than a projection of
one entity's facts.**

### Why

A situation card is an index card of facts about one live situation, kept by the engine
and shown to the narrator whenever that situation is in play. It is how the world's own
tensions reach the table without dumping the whole world into a prompt — which does not
fit and would not be read.

The world already contains the raw material: settlement `tension`, faction `conflicts`
(aim, method, holdings, weakness), chronology events, and `unwritten` names. Nothing on a
card is invented; a card is a *selection*.

### Shape

`play.cards[]`, each entry:

| Field | Meaning |
|---|---|
| `id` | durable, unique within the export (`salt-levy`) |
| `title` | one line under 80 characters: "The salt levy is due and nobody can pay it" |
| `facts[]` | up to **eight** short sentences the narrator may state as true |
| `keys[]` | trigger words; optional — the consumer derives them from title and facts when absent |
| `tags[]` | hierarchical, dot-separated; the consumer prefixes `situation.world` to any that does not already begin with `situation.` |
| `people[]` | entity ids of the people this situation is about |
| `place` | the entity id of the settlement or region it belongs to |
| `clock` | optional; a word about how much time is left, never a number of rounds |
| `secret` | `true` if the players do not know this yet |
| `always_on` | `true` if the card should be in front of the narrator every turn, not just when triggered |

### Worked example, from the shipped sample

Pangrella (`5bbd0c40345f`) carries
`tension: "Tensions between winged nobility and merchant castes"`:

```json
{
  "id": "winged-nobility-and-the-castes",
  "title": "The winged nobility and the merchant castes are barely speaking",
  "facts": [
    "The nobility fly; the merchant castes do not, and both know what that is worth.",
    "Fine ironwork and windcatchers leave Pangrella under a noble seal.",
    "The merchant castes have the coin and none of the standing.",
    "Nothing has been said openly, which is the point."
  ],
  "keys": ["noble", "nobility", "merchant", "caste", "seal", "windcatcher"],
  "tags": ["situation.world.caste", "situation.world.pangrella"],
  "people": [],
  "place": "5bbd0c40345f",
  "clock": "",
  "secret": false,
  "always_on": true
}
```

Every one of those facts is a sentence a narrator could say out loud. None is a rule, a
number, or an instruction to the model.

### Rules for facts

- **One sentence each.** Two sentences in one entry is the commonest defect.
- **No digits.** The consumer's validator refuses a fact containing one.
- **Only names the world knows.** A fact naming a person or place that is not in
  `entities` will be refused. This matters because World Bible's own section rewrites are
  known to invent names — see **Known gaps** below.
- **True as written.** A fact is handed to the narrator as licence. "The baron may be
  lying" is a fine fact; "the baron is lying" on a non-secret card is a spoiler.
- **A secret card's facts are the truth**, and the players have not learned them yet.

### What Pathfinder GM does today without it

`rules/cards.py:from_world` derives cards from every export: the starting settlement's
strain from its own `Tension`/`Cause` facts, and one secret card per `unwritten` hook.
That is two thin sources out of a world full of them — no faction conflict becomes a card,
no chronology event does, and no settlement but the starting one.

### Done when

- The starting settlement of any world has at least one card, and it is at least as good
  as the derived one.
- Every faction in `conflicts` has produced at least one card.
- No fact contains a digit; no fact names an entity absent from `entities`.
- Cards carry `secret: true` where the players genuinely do not know, and the export's
  human-readable side does not leak them.

---

## 3. `play.places[]` — the places inside a town

> **Superseded in detail by `docs/places-and-races-for-world-bible.md` (2026-09-15).**
> That document is what to build from: it carries the corrected id grammar, the room's
> shape and height, and the three tiers to ship in. What follows is the original ask, kept
> because the reasoning is still the reasoning. Two things in it have since changed —
> the id format below gained the `~terrain` segment it is shown with here, and a place now
> also carries how big it is, how high, and how it is shaped upward.

**The first ask with no written contract yet, and the first that needs real generation
rather than projection. Propose the schema below or something close to it; the consumer's
existing `Place` shape is what it has to fit.**

### Why

This is the one that changes play the most.

Measured 2026-09-01 against the live saves: **a `CITY` in the current export has no
sub-places at all.** The children of Zhilvarnia in the world tree are three `CHARACTER`s.
So a city is a single point, and standing "in Pangrella" is as specific as the game can
be.

Pathfinder GM works around this with three doors — a table of implied spots read from the
settlement's own words, places the player founds in play, and ground they venture into —
and that workaround was always meant to be temporary. Its cost is that a place is
**discovered**, never **authored**: the game cannot ground the narrator against a list of
places the way it grounds it against a list of people, because there is no list.

There is one hard design constraint here, and it is settled, so do not design against it:

> **World Bible cannot author every place, and Pathfinder GM must still be able to make
> one during play. One format, two authors.**

Whatever you ship must be the *same shape* the app writes when the fiction reaches
somewhere nobody authored. That is why the schema below carries an `origin` field.

### Shape

`play.places[]`, each entry:

| Field | Meaning |
|---|---|
| `id` | durable and unique within the export. Prefix with the settlement id so two towns may both have a market: `5bbd0c40345f~urban:the-market` |
| `name` | what people call it, lower case, article included: `"the market"`, `"the mine head"` |
| `about` | one short sentence: what it is for, what it is like. Prose the narrator may use |
| `parent` | the 12-char entity id of the settlement or region containing it |
| `terrain` | one word — `urban`, `forest`, `hills`, `coast`, `underground`, … |
| `exits[]` | the ids of the places you can walk to from here. **Adjacency only, no distances or weights** |
| `described_only` | `true` for a place that is named in prose but cannot be entered — "an alley runs east" — so the narrator may mention it without the engine minting a node |
| `origin` | always `"world"` for anything you export. The app writes `"found"` or `"venture"` for its own |

**Do not ship distances or weighted borders.** Fate shipped weighted zone borders and then
deleted them; the consumer refuses them by design, and obstruction belongs in states and
effects rather than a cost table nobody would tune.

### Worked example

```json
[
  {"id": "5bbd0c40345f~urban:the-market", "name": "the market",
   "about": "Windcatchers turning over every stall, and ironwork under noble seal.",
   "parent": "5bbd0c40345f", "terrain": "urban",
   "exits": ["5bbd0c40345f~urban:the-gate", "5bbd0c40345f~urban:the-workshops"],
   "described_only": false, "origin": "world"},

  {"id": "5bbd0c40345f~urban:the-workshops", "name": "the workshops",
   "about": "Where the trades are, and where the castes outnumber the nobility.",
   "parent": "5bbd0c40345f", "terrain": "urban",
   "exits": ["5bbd0c40345f~urban:the-market"],
   "described_only": false, "origin": "world"}
]
```

### What a settlement needs at minimum

The consumer's fallback table produces roughly this set, and an authored one should not be
poorer: somewhere to buy (**the market**), somewhere to sleep (**the tavern** or lodging),
somewhere to leave by (**the gate**), somewhere quiet (**the temple** or shrine), somewhere
the trades are (**the workshops**), and somewhere nobody is watching (**the back streets**).
Then whatever this particular town actually has — a port town gets **the docks**, a mining
town **the mine head**, a river town **the bridge**.

The world's own words should drive the extras. Vyrakon's export says "port access" and
"cyclone-prone coastlines"; a settlement with those words in its facts should have a
harbour, and the reason the consumer built an implied-spot table at all was a session
asking "why did it not make a docks?"

**Every place must be reachable.** A place with an empty `exits[]` that nothing else exits
to is a place no party can stand in.

### What Pathfinder GM does today without it

Three doors, all staying regardless of what you ship:

1. **Implied** — a fixed table of cue words read from the settlement's own facts
   (`port`/`harbour`/`quay` → the docks; `mine`/`quarry`/`ore` → the mine head), plus a
   generated base set per settlement scale.
2. **Founded** — the player declares a base ("we set up at Marra's house") and the engine
   mints it with an owner.
3. **Ventured** — ground gone into (the sewers, a cave) generated from a seed.

Authored places would replace door one and leave doors two and three exactly as they are.

### Done when

- Every `CITY` in the sample world has at least four places, all mutually reachable.
- Place ids are stable across two consecutive exports.
- Every `parent` resolves to a real entity; every id in `exits[]` resolves to a real place.
- Settlements whose facts mention a port, a mine, a river or a library have the matching
  place.
- No place carries a distance, a travel time, or a numeric weight.

---

## 4. Resources, materials and ingredients

**The largest gap between "what the world says" and "what the game can use", and the ask
that most needs a conversation before code.**

### Why

The export already tells us what a town trades. Pangrella:

```json
"sells": "Fine ironwork and crafted windcatchers",
"buys":  "Luminous crystals from Khra'gixx caverns"
```

**Nothing in Pathfinder GM reads those two fields.** They are free prose, and the game's
market shelf comes from `content/materials` — the app's own built-in tables, identical in
every world. So a world can be about the salt trade and the game will still sell you the
same quicklime it sells everywhere.

This is the ask from 2026-09-01: *resources, materials and ingredients, derived from the
generated world and formatted to ship straight in.*

### The hard part, stated plainly

Every other ask on this list is a shape problem. This one is a **shared vocabulary**
problem, and that is why it is fourth rather than second.

For a town's `sells` to mean something mechanically, both sides have to agree on what a
thing *is*. Pathfinder GM already has a materials shelf with ids, prices and crafting
uses, shared across four crafting benches. World Bible generates prose. Bridging them is
one of:

- **(a) World Bible names its resources from a shared list.** Precise, immediately usable,
  and it drags a rules-adjacent vocabulary into World Bible — which brushes against the
  boundary rule.
- **(b) World Bible ships its resources as documents with descriptive words, and the
  consumer maps them onto its own shelf** the way it already maps a people's anatomy onto
  the Race Builder. Keeps the boundary clean; a mapping layer can always be wrong.
- **(c) Both: a resource document carries the world's own words *and* an optional
  `kind` from a small, stable, deliberately rules-free vocabulary** (`ore`, `stone`,
  `timber`, `hide`, `cloth`, `herb`, `crystal`, `salt`, `grain`, `spice`, `oil`, `dye`).

**(c) is the recommendation.** The `kind` list is a dozen nouns any world has, it is not
Pathfinder-specific, it does not carry a price or a DC, and it gives the consumer enough
to route a resource onto the right bench without guessing from prose.

### Proposed shape, to be agreed before building

`play.resources[]`:

| Field | Meaning |
|---|---|
| `id` | durable, unique (`resonant-crystal`) |
| `name` | the world's own name for it |
| `kind` | one word from the small vocabulary above |
| `about` | one sentence: what it is and what it is good for |
| `found_at[]` | entity ids of settlements or regions that produce it |
| `wanted_at[]` | entity ids that buy it |
| `rarity` | `common`, `uncommon` or `rare` — **a word** |

and a corresponding change to `play.settlements[]`, keeping the prose and adding ids:

```json
"sells": "Fine ironwork and crafted windcatchers",
"sells_ids": ["ironwork", "windcatcher"],
"buys": "Luminous crystals from Khra'gixx caverns",
"buys_ids": ["resonant-crystal"]
```

Additive, so no MAJOR bump and no existing consumer breaks.

### What Pathfinder GM does today without it

`rules/market.py:everything_priced` builds the stall shelf from every material any bench
prices, deduplicated — the app's own content, world-independent. Trade routes are read for
travel, not for goods.

### Done when

- The bridging approach is **agreed with the user** before any code is written.
- Every settlement's `sells`/`buys` prose has at least one corresponding id.
- Every id in `sells_ids`/`buys_ids` resolves to a `play.resources[]` entry.
- No resource carries a price, a weight in pounds, a craft DC, or a rarity number.

---

## 5. `play.schemes[]` — quests as documents

**Hardest, and deliberately last. Pathfinder GM has explicitly ordered this after
hand-written schemes have been played end to end in both worlds. Do not start it before
then.**

### Why it is last

A scheme is the richest document in the system: slots, storylet steps with tag-query
criteria, outcomes with effects, and a fairness contract about foreshadowing. The plan
(`docs/quest-schemes-plan.md`, build order §6.10) is explicit — hand-written schemes in
`content/schemes/`, played through in both worlds, and *only then* schemes in the export.

There is a second, firmer constraint: **never the watcher.** The off-turn model that
advances situation cards must not author schemes. A scheme is authored content, by a human
or by World Bible's own generation with an author reviewing it — never improvised by a
model mid-play.

### Shape, for when the time comes

| Field | Meaning |
|---|---|
| `id`, `title`, `about` | `about` is for the editing bench, never shown to the narrator |
| `slots` | roles and places **with no names** — `{"role": "giver", "wants": {...}}` |
| `cards` | the visible quest card(s) and the secret card(s) it opens, with `$slot` placeholders |
| `steps` | storylets: `{id, criteria[], action, tell, once}` |
| `outcomes` | named endings, their effects, and what they open next |
| `fairness` | which tags the brief must have carried before a twist may fire |

The load-bearing idea is **slots**. A scheme names no one. It says "a giver who wants
something kept quiet" and "a place to sleep", and the consumer fills those from the
world's own cast and places at the moment the scheme opens, then freezes them. That is
what lets one scheme run in any world — and it is why asks 1–4 come first: a scheme is
only as good as the cast, places and resources it can draw on.

### Done when

Not applicable yet. Revisit once Pathfinder GM reports hand-written schemes played end to
end in two different worlds.

---

## 6. `play.travel[].miles` — how far apart two settlements are

**The one ask that adds a number to the `play` layer, and the reasoning for the exception
is below. Small, entirely optional, and the app already works without it.**

### Why

Pathfinder GM can now leave a town. Until 2026-09-14 it could not: `Scene.location_id` was
written once when a campaign began and never again, so a world shipping twelve settlements
was played in exactly one of them. There is a `journey` op now, and it charges the road to
the clock — days pass, the body gets thirsty, effects expire, the world moves on.

What it cannot do is know how long the road is. A route in the export carries `carrying`
and `friction`, both prose. So the app answers in one of two ways:

- **exact** — the world said how many miles, and Pathfinder 1e's overland table does the
  arithmetic against the traveller's speed and the ground;
- **derived** — it did not, and the time comes from how far apart the two settlements sit
  in the world's own containment tree. That answer is reported to the player in **days on
  the road and never in miles**, because a mileage nobody wrote down would be this app
  inventing a fact about your world.

Derived is perfectly playable. Exact is better, and it is three optional fields.

### Shape

Additive to the entries already in `play.travel[]`:

| Field | Meaning |
|---|---|
| `miles` | integer, the length of the road. Crow-flight or road, whichever you mean — say which once, in the contract, not per record |
| `road` | one of `highway`, `road`, `trail`, `none`. This is the column Pathfinder's overland table needs and neither program has |
| `crosses[]` | the terrain the route passes through, in your own words — `forest`, `hills`, `swamp`. The consumer maps them to its own and says so when it cannot |

```json
{"from_id": "58b90a214ada", "to_id": "5bbd0c40345f",
 "from": "Zhilgoroth", "to": "Pangrella",
 "carrying": "Resonant crystal; high-quality winged livestock",
 "friction": "...",
 "miles": 90, "road": "road", "crosses": ["hills", "forest"]}
```

### Why this is allowed to be a number, when rule 1 says not to write numbers

Rule 1 in "What not to do" forbids numbers in the `play` layer, and every example it gives
is a **rules** quantity — sizes as modifiers, speeds in feet, clocks in rounds, prices,
DCs, rarity as a percentage. A distance between two towns is not one of those. It is the
same kind of fact as a settlement's `scale` or its terrain: true regardless of which game
reads it, and expressible without a word of Pathfinder vocabulary.

Rule 2 is untouched. Every conversion — miles to hours, terrain to a multiplier, an extra
hour of marching to a Constitution check — happens on Pathfinder GM's side of the file.
**Do not ship hours or days.** Those depend on who is walking, which is the consumer's
business and not yours.

### What not to do

- **Do not add coordinates.** `agent_engine/world_map.py` is a containment diagram — ring
  radius encodes depth in the tree, and the module says so itself: "a claim about
  structure, not about latitude". Exporting those x/y as geography would produce confident,
  precise, wrong distances, and nothing downstream would look wrong.
- **Do not guess a length.** An absent `miles` is handled honestly. A made-up one is not
  recoverable, because the consumer cannot tell it from a real one.
- **Do not weight the edges inside a town.** The town map's "adjacency only, and the save
  refuses a distance" rule stays exactly as it is. Which room you are in is a discrete
  fact; how far the market is from the gate in feet is not a number the world file needs.

### Done when

An export carries `miles` on at least one route, Pathfinder GM reports that journey as
`exact`, and the tell names the distance instead of only the days.

---

## 13. Each nation's coin — names, never numbers

**Why.** Neither shipped world names a currency, so this app coins one. Measured
2026-10-17 on a Pangrella save at Khalmorin's inn: the sheet read "12 Winged silver
pieces" and the room's tell read "5 Saltmakers' silver pieces" — the sheet coined its name
from the town's facts, the room charge from the world's first faction. That half is fixed
on this side (`goods.coins_here`, one answer for every purse line and tell). What it
exposed is the half only the export can fix: the coined names are guesses at a word
somebody in the world would use. In Pangrella **all 12 cities** were named after the first
word of a fact — "Winged", "Clan", "Clans", "Four", "Patrilineal" — and a live transcript
recorded "180 Clans gold pieces". Since 2026-10-17 the coin is named after the town's
nation instead (Kaldrimia, Ashgate, Saltholm), which is what the traditions do — Golarion's
coins are named per nation (Absalom's silver "weight", Cheliax's own) and most nations
accept each other's at face value under a common standard; the Forgotten Realms name them
per minting state (Cormyr's "lion", Waterdeep's "dragon") and take pure, standard-weight
coin anywhere
(https://pathfinderwiki.com/wiki/List_of_currencies,
https://forgottenrealms.fandom.com/wiki/Currency). A nation's name in front of "silver
piece" is honest but plain; the world can do better.

**Shape.** One entry per nation that strikes coin, keyed by the nation's entity id. Names
only: the ratios stay the Core Rulebook's (10 copper to a silver, 10 silver to a gold, 10
gold to a platinum), because every shipped price is written in them. A denomination the
nation does not strike is simply left out, and the book's name is used for it.

```json
"coinage": [
  {"nation_id": "…", "copper": "thumb", "silver": "falcon", "gold": "lion",
   "platinum": "tricrown", "about": "Struck in the capital; the lion is on the gold."}
]
```

**What Pathfinder GM does without it.** Names the purse after the nation the party stands
in, and falls back to the old coined word, then the book's names, where there is none.

**What it does not answer, and is this side's call.** A purse here is a count of copper,
silver, gold and platinum (`Actor.purse`); it does not record who struck the coins, so a
purse walked from Kaldrimia into Kyraxys is renamed at the border. Both traditions say
coins keep their mint's name in another country. Recording it would make the purse
`{nation_id: {denomination: count}}`, with spending and change-making across mints — a
cost paid for a difference no price in the game depends on (the common standard means a
Kaldrimian silver buys what a Kyraxian one does). Left as the owner's decision; the export
above is needed either way.

**Done when** both shipped worlds carry `coinage[]` for every nation that has a town.

---

## 14. No Pathfinder setting terms in world prose

**Why.** This app took Paizo's setting names out of everything it ships (2026-10-29 and
2026-10-30, `docs/bestiary-licensing.md` §7): Golarion's gods, places, peoples and
organisations, the myth names it adopted, and the names it uses for its planes. The plane
of the fey is "the fey realm" in every spell, feat and stat block here now. The export
still says the old word: `fixtures/aurvantis-campaign.json` has "the First World" twice,
in the world's `Reality` fact ("Material world and the First World sit close together")
and in a cosmology paragraph ("The First World, home of the fey, sits close enough to
Aurvantis…"). The narrator reads both, so the game says one name for the plane in its
rules and another in its world.

"First World" is not Paizo's property as words — the owner chose to rename the plane names
for consistency, not because each is protected — so this is a request for the world to
name its own planes, not a licence rule.

**Shape.** No new field. In any prose the export carries (facts, cosmology, places,
cards), name the world's planes in the world's own words or plainly ("the fey realm",
"the realm of the dead"), and avoid the names the Pathfinder setting gives its planes:
the First World, the Boneyard, the Maelstrom, Axis, Elysium, Nirvana, Abaddon, the Great
Beyond, the River of Souls, the Akashic Record — and every Golarion god, nation or people.
A model given freedom writes them because its training saw Pathfinder; detect them
mechanically (the deny-list in this repo's `tools/content_provenance.py` is a usable
starting list) and repair the sentence with a targeted call, rather than instructing the
model not to.

Not affected: a person's given name that happens to be an English word. Aurvantis's
name pools hold "Maelstrom" nine times as a given name, which is the world's own choice.

**What Pathfinder GM does without it.** Reads the prose as it is. Nothing here rewrites a
world's text, and nothing should: the world is the author.

**Done when** a scan of both shipped exports with the deny-list finds no Pathfinder plane,
god or place name outside a person's given name.

# Known gaps — not asks yet, but on the list

These are documented in `docs/from-world-bible.md` and Pathfinder GM codes defensively
around them. None is urgent. All would be welcome.

- **No maps, coordinates or distances.** Places relate by containment and trade, not
  geometry. Encounter maps are generated rather than imported, and that stays true — a
  place's floor plan is derived from its own durable id, so the same room is the same room
  in every session without a byte of it crossing the file.
  **Travel time is no longer invented in the dark**: ask 6 above asks for `miles` on the
  routes you already write, and until it arrives a journey is timed from the containment
  tree and reported in days rather than miles. If full geometry ever appears, say so before
  shipping it — "distance exists now" changes how travel and encounters work.
- **`entity_id` can be `null`** on a chronology figure or a trade-route endpoint: named,
  never written up. Collected in `unwritten`, which Pathfinder GM turns into secret cards
  — so this gap is currently *useful*, and closing it entirely would remove a source of
  hooks. Better: keep `unwritten` and make it exhaustive.
- **`unwritten` is not exhaustive.** Missing-place detection only reads structured fields,
  so a place invented purely inside a faction's prose is never caught.
- **Section rewrites can invent places and people.** The faction rebuild is grounded
  against the world's real names; a section rewrite is not. One produced "Aviari's Spire"
  and "Elyria's Forge", neither of which exists. This is the gap that most affects the
  asks above — an invented name reaching a situation card is refused by the consumer's
  validator, so ungrounded rewrites turn directly into dropped cards.
- **Years can be `null`** for undated events; the timeline sorts those last.

## 15. `fixtures` on a place — the named things on its floor

*Asked 2026-11-11, and the consumer reads it the day it appears (`rules/floorplan.from_world`
→ `rules/fixtures.py`). Optional: a place without it is typed from this app's own table.*

The tactical map now names what its solid, rough and raised squares ARE — the bar, the
tables, the barrels, the stair up to the gallery — so the board, the narrator and the
rules agree on one room. Today the choice is made from the place's kind (a library gets
bookshelves, a storehouse crates and barrels, a tavern a bar, tables and a hearth); a world
that wants its own smithy to be racks and barrels rather than a hearth says so with one list.

**Shape.** One more optional field on each `play.places[]` entry, beside `clutter` and
`vertical`:

| Field | Meaning |
|---|---|
| `fixtures` | a list of kind words from the closed list below, most important first: `["counter", "table", "hearth"]` |

The closed list (`content/rules/fixtures.json`, the one copy — read it rather than this
table if they disagree): `stair`, `gallery`, `door`, `window`, `table`, `counter` (a bar
or a shop counter), `barrel`, `crate`, `rack`, `bookshelf`, `hearth`, `chandelier`,
`cart`, `crane`, `water`, `rubble`.

```json
{"id": "5bbd0c40345f~urban:the-tavern", "name": "the tavern",
 "clutter": "some", "footing": "firm", "vertical": "ledge",
 "size_ft": {"width": 60, "depth": 50, "height": 10},
 "fixtures": ["counter", "table", "hearth", "barrel"]}
```

**Rules for it.**
- **Words from the list, nothing else.** A word outside it is dropped, not guessed at, and
  the place falls back to its kind's own row. No counts, no positions, no sizes: the
  consumer places them on the room's own geometry, and `clutter` is still what says how
  much solid stuff there is.
- **Order matters**: the biggest solid clump becomes the first kind, the next the second,
  and so on round the list. Put the one thing the room is known for first (a tavern's bar).
- **Naming fixtures never reshapes a room.** A place that ships `fixtures` and none of the
  shape fields keeps the shape the consumer would have derived.
- `stair` and `gallery` need not be listed: a `ledge` place's raised band is always a
  gallery, and the consumer puts a stair at its foot.
- `door`, `window`, `chandelier` and `crane` are in the vocabulary now and are not yet
  placed by the consumer (phase 2, which needs walls with sides and doors with state).

**What Pathfinder GM does without it.** Types every place from its own table by kind and
terrain. A place kind the table does not know gets nothing named but its gallery.

---

# What not to do

A short list, because each of these would cost a rework rather than a fix.

1. **Do not write numbers into the `play` layer.** Not sizes as modifiers, not speeds in
   feet, not clocks in rounds, not prices, not DCs, not rarity as a percentage.
2. **Do not bake Pathfinder vocabulary into World Bible.** No `darkvision`, no `CR`, no
   `1d6`, no ability score names. There is a test in the World Bible repo asserting this
   and it should stay passing.
3. **Do not generate at export time.** Generate into the world's files where the author
   can see and lock it; the exporter projects.
4. **Do not let ids change between exports.** A campaign save keys off them.
5. **Do not make a MAJOR schema bump** to add any of this. Every ask here is additive.
6. **Do not design places as discovery-only or authored-only.** Both routes are permanent
   and that is a settled decision.
7. **Do not have a model author a scheme, ever.**
8. **Do not let Pathfinder's setting names into world prose** (ask 14): no "First World",
   no Golarion god, place or people.

---

# Summary

| # | Ask | Contract | Consumer ready | Effort |
|---|---|---|---|---|
| 1 | `play.races[]` | written | **yes — reads it today** | small |
| 2 | `play.cards[]` | written | **yes — reads it today** | small–medium |
| 3 | `play.places[]` | proposed here | no — needs the key wired up | medium |
| 4 | resources / materials | proposed here, needs agreement | no | large |
| 5 | `play.schemes[]` | sketched | no — and blocked on our side | largest |

Asks 1 and 2 are the ones to do first, and not only because they are easiest: the consumer
already reads both, so each one flips from derived to authored the day it appears in an
export, with no coordinated release and nothing to change on the Pathfinder GM side.

## 16. `volatility` — how dangerous a place is

*Asked 2026-11-13 by the owner. The consumer reads it the day it appears
(`world/loader.py` → `rules/volatility.py`). Optional: without it a town reads as
settled (1) and everything else as uneasy (2), which is how every world played before.*

The owner's ruling: a place's danger rating moves the chance of meeting monsters, bandits
and catastrophe there: a road through a lawless march is ambushed more often than one
between two quiet market towns, and a sea crossing in a stormy strait is likelier to end
in a wreck than one across a calm gulf. The world knows which places are which; this app
cannot guess it from prose without inventing it.

**Shape.** One optional integer, `0`–`4`, on any entity (a `CONTINENT`, `NATION` or
`CITY`), and on any `play.places[]` row:

| value | word | what it means at the table |
|---|---|---|
| `0` | calm | patrolled, peaceful; trouble is rare |
| `1` | settled | ordinary town life; the default for a settlement |
| `2` | uneasy | the published wandering-encounter rates; the default for open ground and sea |
| `3` | dangerous | bandit country, a monster's range, a strait known for storms |
| `4` | lawless | war, a cursed waste, a sea nobody crosses twice |

A place takes its own row's value first, then its settlement's, then the nation's and the
continent's (`parent_id` up the tree), so one number on a nation covers every city in it
that does not say otherwise. Sea between continents takes the value of the nearer coast's
nation until the export has sea regions of its own (see ask 2's ports and vessels).

```json
{"id": "431bd046b7d5", "kind": "NATION", "name": "Kaldrimia", "volatility": 3}
{"id": "5bbd0c40345f~urban:the-temple", "name": "the temple", "volatility": 0}
```

**Rule 1 still holds.** The rating is a word on a five-step scale, not a probability:
what each step does to each table (road meetings, night camps, storms at sea) is this
app's, in `rules/volatility.py` and the tables that read it. On land, since 2026-11-13:
calm a third of the published rate, settled a half, dangerous one and a half times,
lawless twice, on the road's creatures and weather, the street's thieves and trouble,
the night camp, a forage's creatures and a ventured place's inhabitant
(docs/encounter-budget.md, "Danger and how often"). Only a stated value moves anything.

### Done when

An export carries `volatility` on at least its nations, `tools/check_places.py` accepts
0–4 and nothing else, and a city in a nation rated 4 is measured meeting more trouble on
its roads than one rated 0.


## 17. `water` — how rough a wet place's water is

*Asked 2026-11-14 (fix/water-everywhere). The consumer reads it the day it appears
(`rules/water.roughness`, off the place's own `play.places[]` row). Optional: without it
every lake, river and sea reads as calm water, which is how every world played before.*

Every water a character is in now asks the Pathfinder Swim check, and its difficulty is
the water's roughness: calm, rough or stormy. A storm at sea already makes it stormy. What
this app cannot know is which of the world's own waters are fast: a millrace, a river in
its gorge, the rapids below a falls. The Core Rulebook says fast rivers are always at
least rough and whitewater rapids are stormy; the world knows which rivers those are, and
this app cannot guess it from prose without inventing it.

**Shape.** One optional word on any `play.places[]` row whose ground is wet (`water` or
`underwater`): `"calm"`, `"rough"` or `"stormy"`. Anything else reads as calm.

| value | what it is in the world |
|---|---|
| `calm` | a lake, a pond, a placid river, a sheltered harbour; the default |
| `rough` | a fast river, a tide race, open sea in a hard wind |
| `stormy` | whitewater rapids, a whirlpool's edge, a sea that is always breaking |

```json
{"id": "5bbd0c40345f~water:the-gorge", "name": "the gorge", "water": "rough"}
```

**Rule 1 still holds.** The word is the world's; the DC (10, 15, 20) and everything else a
Swim check does are this app's, in `rules/water.py`.

### Done when

An export carries `water` on at least one fast river or rapids place, `tools/check_places.py`
accepts the three words and nothing else, and a character swimming there is measured
rolling against DC 15 or 20 instead of 10.


## 19. `good` on a trade route — what it carries, in words

*Asked 2026-11-14 (feat/trade-goods). The consumer reads it the day it appears
(`rules/trade.route_row` → `row_of_good`). Optional: without it the route's `commodity`
prose is filed by this app's word table (`trade.WORDS`), which is how every world plays
today.*

A party can now buy a route's commodity in bulk at its origin and sell it dear at its
destination. The price is the Pathfinder Trade Goods table's (Core Rulebook p.140), and the
app has to choose the row. From prose it can only guess. "Tempered steel" becomes iron,
"Turmoil-era tea blends" becomes coffee, and "river-borne trade goods" matches no row, so
it is never offered. The world knows what each commodity is and roughly what it is worth.

**Shape.** One optional object on each `trade_routes[]` entry:

| Field | Meaning |
|---|---|
| `kind` | `food`, `spice`, `cloth`, `hide`, `metal`, `stone`, `timber`, `fuel`, `livestock` or `other` |
| `worth` | `cheap`, `common`, `dear` or `precious`: dear for its kind, not dear in coin |
| `service` | `true` when the "commodity" is not a thing you can carry: mercenary contracts, river tolls, message relays, a black market |

```json
{"origin": "Ashwatch", "destination": "Steelline", "commodity": "tempered steel",
 "sought_as": "tempered steel", "good": {"kind": "metal", "worth": "common"}}
{"origin": "Harforge", "destination": "Harpost", "commodity": "mercenary contracts",
 "good": {"service": true}}
```

**Rule 1 still holds.** Words, never prices. `kind` × `worth` picks a row of the book's
table (`trade.GOOD_ROWS`: metal goes iron, copper, silver, gold; food goes wheat, tobacco,
salt, saffron). The price, the unit and the weight are the row's. So a world never has to
say how heavy a bale is, or in what it is counted. `other` has no row and is not offered.

**What Pathfinder GM does without it.** Reads the commodity's words against
`trade.WORDS`, first match by priority, and says so in the code where the match is a
judgement (ore and steel are iron; gems, pearls and coral are gold by the pound).

### Done when

An Aurvantis export carries `good` on every route, and `river-borne trade goods` and
`novelty trade goods` are measured offered at their origins. `mercenary contracts` stays
unoffered.


## 20. `volume` on a trade route — how much moves along it

*Asked 2026-11-14 (feat/trade-goods). The consumer reads it the day it appears
(`rules/trade.volume`). Optional: without it a market's stock and appetite are its
settlement's base value's worth of the good, which is how every world plays today.*

A market's price moves with every unit the party buys or sells. It refills over a week,
and it cannot sell more than it holds. How much it holds is now the settlement's size,
read from its scale. The world knows better: a salt road that feeds a whole kingdom
moves more salt than one village's cellar.

**Shape.** One optional word on each `trade_routes[]` entry: `"trickle"`, `"steady"` or
`"heavy"`. Anything else reads as steady.

| value | at the table |
|---|---|
| `trickle` | a pack train now and then: half the usual stock at both ends |
| `steady` | the default |
| `heavy` | a road or a sea lane that never empties: twice the stock at both ends |

```json
{"origin": "Saltmere", "destination": "Brackgate", "commodity": "salt", "volume": "heavy"}
```

**Rule 1 still holds.** The word is the world's. The halving and the doubling are this
app's, in `trade.VOLUME_WORDS`.

### Done when

At least the heaviest routes of an export carry `volume`, and a heavy route's origin is
measured selling twice the units before its price tops out.


## 21. `goods` on a settlement — what it makes and wants, as goods

*Asked 2026-11-14 (feat/trade-goods). The consumer reads it the day it appears
(`rules/trade._settlement_goods`). Optional: without it the settlement's one `sells` and one
`buys` line of prose are read by the word table, which is how every world plays today.*

`play.settlements[].sells` and `buys` are one line of prose each, so a town that makes
salt *and* smoked fish can only say one of them. A town that wants iron but has no route
bringing it is only known to want it if that line happens to say so. This generalises the
`trade.goods[]` row proposed in docs/from-world-bible.md, and supersedes it.

**Shape.** One optional object on each `play.settlements[]` row, with two lists of goods
in ask 19's words plus a name:

```json
{"id": "c0a1f5e20013", "name": "Marrowby", "sells": "salt", "buys": "wool",
 "goods": {"sells": [{"name": "salt", "kind": "food", "worth": "dear"},
                     {"name": "smoked fish", "kind": "food", "worth": "cheap"}],
           "buys":  [{"name": "fleeces", "kind": "cloth", "worth": "common"},
                     {"name": "iron tools", "kind": "metal", "worth": "cheap"}]}}
```

**Rules for it.**
- `sells` is what the place makes or ships, sold cheap there. `buys` is what it is short
  of, bought dear there. A place that both makes and wants a thing is not short of it.
- Keep `sells` and `buys` as the one-line summaries: other readers use them.
- `name` is the world's own word, shown to the player; `kind` and `worth` choose the row.

**Rule 1 still holds.** Words only. The cheap and dear prices are the book's row times
this app's factors (`trade.SUPPLY_FACTOR`, `DEMAND_FACTOR`).

### Done when

An export carries `goods` on its settlements, and a settlement that sells two goods is
measured offering both at its market.


## 22. `anchors` on a settlement — where ships lie off a town with no docks

*Asked 2026-11-15 (fix/shore-and-sea). The consumer reads it the day it appears
(`rules/journey.calls_off`). Optional: without it this app works it out as described
below, which is how every world plays today.*

The owner's ruling of 2026-11-14: a ship lying off a coastal town that has no docks can be
reached by swimming out or by a rowboat, and then boarded and sailed exactly as from a
quay. Something has to say that a ship is there. Today this app reads the world's own
routes: a stated `by: "sea"` travel row from a settlement on the water (its `coast`, or a
water phrase in its land facts) that has no docks is a ship's call, and she calls **once a
week** on a day fixed by the route. Measured on Aurvantis: 6 of its 41 dockless
settlements qualify (Pilfnook, Kraghold, Vormoor, Halhollow, Faeanor, Tidecrest), with 9
calls between them; on Pangrella, Kalixiri's one. The weekly call and the distance she
lies off (a cable, about 600 feet) are this app's numbers. Three of the six read as being
"on the water" only because their land facts name a canal, which says nothing about the
sea.

**Shape.** One optional object on a `play.settlements[]` row:

| Field | Meaning |
|---|---|
| `coastal` | `true` when the town is on the sea (ask 8a's `coastal`, read here too) |
| `anchorage` | `true` when ships lie off it to take on passengers; `false` when none ever do |
| `calls` | `"daily"`, `"weekly"`, `"monthly"` or `"seasonal"`: how often a ship on each of its sea routes lies off |

```json
{"id": "bde94b038cba", "name": "Vormoor", "coastal": true, "anchorage": true,
 "calls": "weekly"}
```

**Rule 1 still holds.** Words, never days or distances: which day a ship calls, how far
off she lies and what the boat out costs (Ultimate Equipment's rowboat, 2 cp a mile) are
this app's.

### Done when

An export carries `anchorage` on its coastal towns without docks, a town marked `false` is
measured offering no ship off its shore, and a `"daily"` one offers her every day.


## 23. `current` and `flooded` on a wet place — moving water and floods

*Asked 2026-11-15 (fix/shore-and-sea). The consumer reads it the day it appears
(`rules/water.current`, `rules/water.roughness`). Optional: without it every water is
still water, and nothing floods.*

The Core Rulebook has rules for moving water and for floods that this app now runs, and
cannot place without the world. Fast-moving water asks "a DC 15 Swim check or a DC 15
Strength check to avoid going under", and a failed check costs 1d3 nonlethal damage a
round, or 1d6 lethal over rocks and cascades. A flood makes every Swim check "one step
harder", calm to rough and rough to stormy. Ask 17's `water` word says how rough a water
is; it cannot say whether it moves, or whether it is in flood.

**Shape.** Two optional fields on any `play.places[]` row whose ground is wet, beside
ask 17's `water`:

| Field | Values | What it is in the world |
|---|---|---|
| `current` | `"fast"` or `"rapids"` | a fast river or tide race; whitewater over rocks |
| `flooded` | `true` | the water is in flood now |

```json
{"id": "5bbd0c40345f~water:the-ford", "name": "the ford", "water": "calm",
 "current": "fast", "flooded": true}
```

A fast current makes the water at least rough and rapids make it stormy, by the same CRB
paragraph. A flood is a fact of a season, so a world that does not track seasons should
leave it out rather than set it once for ever.

**Rule 1 still holds.** Words only. The DCs and damage dice are the book's, in
`rules/water.py`.

### Done when

An export carries `current` on at least one river place, `tools/check_places.py` accepts
the two words and `true`, and a swimmer there is measured taking the current's damage on
a failed check.

## 24. `customs` on a settlement — whether it taxes goods coming in

*Asked 2026-11-15 (fix/merchant-road). The consumer reads it the day it appears
(`rules/trade.levies_customs`). Optional: without it a town levies customs when this app
has given it a customs house among its places, which is how every world plays today (1 of
Pangrella's 12 settlements, 2 of Aurvantis's 64).*

Towns taxed goods at their gates: France's octroi, England's murage and petty custom. This
app now takes the levy when the party's cargo comes into a town that keeps a customs
house (an eightieth of its book value, `trade.CUSTOMS_SHARE`, England's petty custom of
1303). Which towns do that is a fact about the world, not about the size of a city: a free
port levies nothing, and a toll town on a river levies whatever its size.

**Shape.** One optional word on each `play.settlements[]` row: `"levied"` or `"free"`.
Anything else reads as unsaid.

```json
{"id": "c0a1f5e20013", "name": "Marrowby", "customs": "levied"}
```

**Rule 1 still holds.** The word is the world's. The rate is this app's.

### Done when

An export carries `customs` on the settlements that tax goods (and `free` on any port the
world means to be a free port), and a party landing cargo at a `levied` town is measured
paying the levy, and at a `free` one paying none.

## 25. `dungeons` on a place — the ways deeper a world knows of

*Asked 2026-11-15 (feat/hidden-dungeons). Optional: without it a venture rolls for its
own way down (`rules/dungeons.py`: a seeded d100 off the venture's id, 20% on uneasy
ground, moved by `volatility`, ask 16), which is how every world plays today.*

The owner: "perhaps a percentage roll to turn any of those ventures into a full dungeon,
like you go to the cave and you find a boulder that has broken revealing a small gap and a
passage". The roll is the app's fallback. A world that knows where its old works lie — the
barrow under the hill the ballads name, the drowned mine its people will not reopen — should
be able to say so, and the app should find that dungeon there every time, at the depth and
in the theme the world gave it, instead of rolling.

**Shape.** An optional list on any `play.places[]` row or settlement entity:

```json
{"id": "5bbd0c40345f", "name": "Pangrella",
 "dungeons": [{"under": "cave", "name": "the Sunken Barrow", "depth": 2,
               "theme": "tomb", "about": "a barrow older than the town, sealed by its builders"}]}
```

| field | what it is |
|---|---|
| `under` | the venture kind it lies under: `cave`, `mine`, `ruins`, `crypt`, `sewers`, `cellar` or `tower` (never `rooftops`, never `alley`) |
| `name` | what it is called, a proper name in the world's own words |
| `depth` | how many levels, `1`–`3` |
| `theme` | one word from `tomb`, `lair`, `mine`, `temple`, `vault`, `warren` — what the rooms are drawn from |
| `about` | one sentence, the world's own prose |

**Rule 1 still holds.** The world names it, places it and says what it is. The rooms, the
doors, the traps, the creatures and the treasure are this app's: drawn from the bestiary
by the ground, the CRB's traps and door DCs, and the CRB's treasure per encounter at the
party's level. No number in this ask reaches a die.

### Done when

An export carries `dungeons` on at least one place, `tools/check_places.py` accepts the
fields above and nothing else, and a party venturing into that kind of ground there finds
the named way down every time, with the given number of levels.


## 26. `climate` on a sea route — what waters a crossing sails

*Asked 2026-11-15 (fix/threats-morale-ships). Optional: without it a crossing reads the two
ports' own Climate facts and uses one only when it names a single climate
(`Engine._waters_climates`), which is how every world plays today.*

Playtest 2026-11-15 #89: a penguin ("cold oceans") came up at the rail on a crossing between
Zhilvarnia and Mirabalos in a desert-and-silk world. The only climate either port carries is
its continent's ("temperate near the equator, polar at the edges"; "variable with latitude
and season"), a whole continent's span, which says nothing about one stretch of sea, so the
app cannot keep cold-water creatures out of warm water.

**Shape.** One optional word on a `travel` row whose `by` is `sea`:

```json
{"from": "6953424c8a82", "to": "7ef5e373c993", "by": "sea", "climate": "warm"}
```

| field | what it is |
|---|---|
| `climate` | `cold`, `temperate` or `warm`: the waters the crossing sails (`rules/biomes.CLIMATES`) |

**Rule 1 still holds.** A word, never a temperature: which creatures live in those waters is
the Bestiary's Environment line (`biomes.parse_environment`).

### Done when

An export carries `climate` on its sea routes, and a crossing marked `warm` never meets a
creature whose Environment line says cold oceans.

## 27. `title` on a faction's card — the faction's name, not its description cut short

*Asked 2026-11-16 (fix/xp-and-watcher). Optional: without it the app re-titles a card whose
title is a cut-off prefix of its own first fact with the faction's name, found by the card's
id (`cards._world_title`), which is how every world plays today.*

Playtest 2026-11-16 #27: a story award read "for moving a matter along: A fraternal
organization of skilled salt harvesters and refiners, bound by". The faction's public card in
`play.cards[]` is titled with the first seventy characters of its description, cut in the
middle of the sentence, and its secret card the same way with its aim ("The Guild aims to
monopolize the Pangrellan salt trade by establishing a"). A settlement's strain card has the
same cut when its tension runs long ("…over control").

**Shape.** No new field: `title` on every `play.cards[]` row is a whole name or a whole
phrase, never a sentence cut at a length.

| card | `title` |
|---|---|
| a faction's public card | the faction's `name`: "The Guild of Saltmakers' Sons" |
| a faction's secret card | a short phrase of its own: "What the Guild of Saltmakers' Sons wants" |
| a settlement's strain | the tension as one whole phrase, shortened by wording, not by length |

### Done when

No `play.cards[]` title is a strict prefix of one of that card's own facts.

## 28. `ruins` on a place — who built the old works, when, and what ended them

*Asked 2026-11-16 (feat/dungeon-story). Optional: without it a dungeon's history is drawn
from the app's own authored rows (`content/dungeons/builders.json`), grounded where it can
be in the world's PEOPLE, NATION and faction names and its oldest dated chronology events
(`rules/dungeons.py` `_world_sources`), which is how every world plays today.*

The owner: "A proper dungeon cannot just be random rooms and it must hold a cohesive
story/pattern." Every way down now carries a concept chosen before any room: who built it
and for what, how old it is, how it was ruined, who used it after, who holds it now, why it
is still unlooted, and what the town says of it. The app can only guess the first four
from names: a tomb "of the Korvu" because the Korvu are the continent's people, "in the days
of the Founding of Pangrella" because that is one of the world's oldest events. It cannot
know that the Korvu buried their dead in the sinkholes their Founding Story names, or that
the Shattering of the Citadel is what emptied the old works under Vyrakon. A world that
knows its own ruins should be able to say so, and the app should then tell that history in
the rooms instead of a guessed one.

**Shape.** An optional list on any settlement entity or `play.places[]` row, beside ask 25's
`dungeons` (the two may be one row: a `dungeons` entry may carry these fields too):

```json
{"id": "5bbd0c40345f", "name": "Pangrella",
 "ruins": [{"under": "crypt", "built_by": "fd4449bc9a64", "built_for": "tomb",
            "when": "event:Founding of Pangrella", "ended_by": "flood",
            "after": ["e1a2b3c4d5e6"],
            "about": "The first Korvu dead were laid under the sinkholes, until the water came up."}]}
```

| field | what it is |
|---|---|
| `under` | the venture kind it lies under: `cave`, `mine`, `ruins`, `crypt`, `sewers`, `cellar` or `tower` |
| `built_by` | the id of the PEOPLE, NATION or faction that built it (never a free-text name) |
| `built_for` | one word: `tomb`, `temple`, `smuggling`, `garrison`, `mine`, `retreat`, `drains`, `treasury`, `prison`, `natural`, `monastery` |
| `when` | `event:<chronology event name>`, or one word: `recent`, `old`, `ancient` |
| `ended_by` | one word: `flood`, `fire`, `plague`, `collapse`, `war`, `sealed`, `quarrel`, `abandoned` |
| `after` | ids of PEOPLE, NATION or factions that used it later, oldest first; may be empty |
| `about` | one sentence, the world's own prose |

**Rule 1 still holds.** Ids and words, never numbers: what lives there now, its creatures,
traps, doors and treasure stay the app's (the ruin tag, the bestiary through the encounter
budget, the CRB's traps and treasure). Ask 14 still holds too: no Pathfinder setting names
in `about`.

### Done when

An export carries `ruins` on at least one settlement, `tools/check_places.py` accepts the
fields above and nothing else, and a way down found under that settlement names those
builders, that age and that ending in its rooms' traces, every time.

## 30. An inn in every settlement's `play.places[]` — somewhere a traveller can sleep

*Asked 2026-11-17 (fix/inns-and-jobs; 29 left free for feat/travel-pacing). Optional:
without it the app appends `the inn` to every authored settlement that lists no inn, and
`the tavern` beside it to a city (`places.APPENDED_TO_AUTHORED`, published in
`docs/place-vocabulary.json`), which is how every world plays today.*

Playtest 2026-11-17b #4/#7/#8: in Mirabalos (Pangrella's export, a city of 23 places) "head
to an inn in the city" walked the player aboard her own ship twice, the harbourmaster named
the gardens as a place to rest, and the city's own news spoke of "the death at the tavern"
that its place list did not hold. Measured that day: no inn or tavern in 8 of Pangrella's 12
settlements (all 6 towns, 2 of 6 cities). A settlement with nowhere to let a bed is one the
rest door cannot price a night in (CRB Goods and Services, inn stay 2 sp / 5 sp / 2 gp).

**Shape.** No new field: a row in `play.places[]` for each place that lets beds, under a
name of the world's own, with the kind the app reads (`"kind": "inn"` or `"kind": "tavern"`),
and, when the world knows it, the optional word `lodging` (docs/from-world-bible.md, "Where
beds are let"):

```json
{"id": "7ef5e373c993~urban:the-salt-lantern", "name": "the Salt Lantern",
 "kind": "inn", "lodging": "common", "parent": "7ef5e373c993",
 "about": "Where the caravans' drivers sleep, two to a bed."}
```

| scale | at least |
|---|---|
| village | one inn (or one tavern that lets beds) |
| town | one inn |
| city | one inn and one tavern |

**Rule 1 still holds.** A word, never a price: the stay's cost, the meals and the drink
are the app's (CRB Goods and Services, "Food, Drink, and Lodging").

### Done when

Every settlement in an export holds an inn or tavern row of its own, `tools/check_places.py`
reports none appended for lodging.
