# The small true things

Group 7 of the fix pass after the 2026-09-19 play-test
(`docs/playtest-2026-09-18.md`, items 31, 32 and the price half of 24). Branch
`small-true-things`. Tests: `tests/test_small_true_things.py` (14).

Three items that are all visible in the first ten minutes of play, and one of them is a
regression from the day before.

## The stranger gives his name when he is asked (item 31)

**What was wrong.** Group 3 gave every promoted person a true name out of the world's own
pools. Then the narrator began *using* those names before anybody had asked — "Soren's
eyes narrow" — so the name was taken out of the brief entirely (`gm/prompts.py`, and
`docs/names-and-faces.md` records that reasoning). The other direction was never built:
`settle_introductions` only *replaces* a name the model has already offered, so asked
outright, a model with no name to give did the only thing left to it and refused. Several
scenes in, he was still "the stranger".

**Built.** Three pieces, none of which puts the name back into an ordinary brief.

- `judgement.names_asked_for(scene, player_text)` — who the player just asked, and what
  each of them gives. `_ASKS_A_NAME` (written for group 3's bare-answer case) detects the
  question; who was asked is settled the same way `apply_introductions` settles it — the
  unnamed person the player's own words name, else the only unnamed person here. Never the
  whole room: handing out six names is how the brief leaked them in the first place.
- `prompts.scene_brief(names_for=…)` — one extra clause on that person's line, for that
  turn only: "ASKED HIS NAME THIS TURN (fact — he answers with THIS name and no other)".
  An empty value is stated too: he will not give it, and why.
- `narration.give_the_name` — the deterministic backstop. A beat that still contains no
  name gets one plain sentence appended, before the hand-back rather than after the
  question. A name the model gave itself is left alone; its own sentence is better than
  ours. This is the rule about the rewrite losing not being the end of the road (46% of
  what the reviewer caught used to ship anyway).

**And whether he tells you is a fact.** `attitude.tells_their_name`: indifferent or
better gives a name, unfriendly or hostile refuses. Not a check — the Core Rulebook has no
roll for "what are you called" — so the track answers instead of a die, which is what the
track is for. Diplomacy already moves it (`docs/attitude.md`), so a refusal is legible and
actionable rather than the only thing the model could do. The player's own earlier ruling
stands: refusing is fine. What was wrong was that it happened for no reason.

## Nobody stands in a scene undescribed (item 32)

**What was wrong.** Four writers put people into a scene — the opening companion, the
keeper behind a counter (this is the Drenn Ironvale path), a scheme's cast, the `spawn` op
— and the description check covered none of them. `narration.faceless` was called in
exactly one loop, over the phrases `note_cast` booked from *this turn's* prose. Everyone
else could be referred to for the rest of the campaign with nothing ever describing them,
and there was no `described` flag on `Actor` to ask.

**Prior art, searched before the bit was added.** Inform 7 has held exactly this shape for
twenty years: a thing carries an *initial appearance*, "used until the first time the
player picks the ring up", and the switch is a one-bit either/or property — something is
**handled** "if it has at any point been held by the player"
([Writing with Inform 3.11](https://ganelson.github.io/inform-website/book/WI_3_11.html)).
The lesson taken from it is the one this app got wrong: the "has it been introduced yet"
state is *held on the object*, not recomputed from what the last paragraph happened to
contain. A per-turn recomputation can only ever see this turn, which is precisely why the
check covered one writer out of four.

**Built.** One bit and one rule.

- `Actor.described`, saved and loaded. The condition the check was always meant to ask is
  held rather than inferred.
- `judgement.settle_descriptions(scene, beat, player_text)` marks whoever the beat *did*
  describe and returns the refs it owes. Owed means: in the beat, or addressed by the
  player, and no sentence about them carries a body word. The view appends the world's own
  line for those — the resident's Appearance fact, or their people's body line — and marks
  them. Asked once, never again.
- **Keepers get a face where they are made** (`keepers.staff`), because nothing downstream
  can find them one: their `world_entity_id` is the synthetic `keeper:<place>`, so
  `names.resident_appearance` looks up a resident who does not exist and returns "". Their
  `true_name` is stamped there too — a shopkeeper is not a stranger keeping his name back.
- **And the hole item 32 exposed in `name_the_nameless`**: a person with a real name and no
  world id fell out of the loop before anything looked for an appearance. Everybody now
  leaves it with a face.

The two ad-hoc loops in `views._finish` (the faceless arrival, the person looked over)
became one, which is the same rule applied to everyone present instead of to the two cases
somebody had thought of.

## Free is a price (the price half of item 24)

**What was wrong.** Ten weapons carried `cost_gp: null`, and the outfitter skipped
anything costing nothing, so it stocked no club, no quarterstaff and no sling — while
three of the eleven class kits hand out a quarterstaff and one a club. A character who
lost one could not buy it back.

**Built.** `None` and `0.0` are now different facts: unknown, which nothing may sell, and
free, which anything may hand over. Four weapons are free in the book — club, quarterstaff,
sling and wooden stake all print "—" in the Cost column (Core Rulebook Table 6-4, confirmed
against d20pfsrd's weapon tables on 2026-09-19) — and they are named in
`tools/build_weapons.FREE_BY_NAME` so a re-import keeps the fact, with the committed index
brought into line by the same rule. The other six were simply imported without a price and
stay unpriced and unsellable; that is honest, and no worse than today. The outfitter stocks
a 0-gp row and prints it as "free".

One claim in the play-test record was wrong and is corrected here: the light crossbow is
**not** absent from `weapons.json`. It ships as `light-crossbow` at 35 gp and is reachable
under both spellings. The only real blocker was the null price.

## Measured live, five runs on a copy of the `masta` save

`/api/say` with "I turn to the woman in the corner and ask her what her name is", into the
brothel scene the 2026-09-18 session ended in — two women, a stranger, guards, and nobody
with a face. Each run on a fresh copy.

| Run | Result |
|---|---|
| 1 | The name is given — "'Gorvothor Kragnir,' her voice rasps" — and **a second woman volunteered hers to nobody**: "woman in the corner" matched both her and the woman, so `names_asked_for` offered two names and the backstop appended the second. Best-match added, ties answer not at all. |
| 2 | One name only, the other woman untouched. But the panel **kept "woman in the corner"** though she had said "you may call me Gorvothor": `introductions` read her speaker word as "low" (out of "a low, resonant grind"), her true name is two words so the equality missed the partial, and both women answered to "woman". The ref was known all along — `apply_introductions` now takes the person who was asked first. |
| 3 | The model refused outright and the backstop fired — and the panel kept the descriptor **again**, because `_BARE_NAME_ANSWER` read "the woman says" but not "the woman in the corner says". The engine's own sentence has to be legible to the engine. Widened. |
| 4 | **The chain, working**: model refusal, engine's line, panel renamed to Gorvothor Kragnir. And a new fault of taste: two appended body lines, word for word identical, because the export gives the Orc people exactly ONE body sentence. Capped at one a beat, never the same sentence twice. |
| 5 | Held. The model reached for "Most just call me the stranger" — our own placeholder, the 2026-09-18 failure itself — the engine's line overrode it, the panel shows Gorvothor Kragnir, and one body line was appended rather than two. |

Every one of those four defects was invisible to the unit tests and visible on the first
live turn, which is the measurement CLAUDE.md's "verify in the running app" is there for.
Each is now a test in `tests/test_small_true_things.py` naming the run that found it.

**And one defect found and NOT fixed here.** In run 5 the prose "Most just call me the
stranger" booked a *new person* named "stranger" into the ledger: `note_cast` reads the
whole beat including quoted speech, so somebody's own words about themselves create
somebody else. That is item 29's territory — nobody is invented, group 8 — and it is
recorded as item 34 rather than patched here, because reading only unquoted prose would
also stop a genuine announcement ("'Three raiders are coming!' he shouts") from booking
anyone, and that trade belongs with the rest of the spawn work.

## Not done here, on purpose

Item 24 proper — deleting `KITS` and letting the rolled purse stand alone — is group 10,
after the outfitter has been exercised in play with these prices in it.
