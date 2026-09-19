# The GM's knowledge, the table's content, and the engine's small doors

Groups 5 and 6 of the fix pass after the 2026-09-18 play-test
(`docs/playtest-2026-09-18.md`, items 9, 22's setting and memory, 1/20, 3, 7, 22's
watcher). Branch `continue-and-guards`. Tests: `tests/test_knowledge_and_doors.py` (10).

## What the character would know (item 9)

The first `/gm` answer of the session: "my notes indicate that there is a shadow power in
the form of an old veterans' league that everyone in office refuses to cross." The
ruling: the information should be available, but only after the player is asked.

The research is in the play-test record: the Alexandrian's "Preempting Investigation";
GUMSHOE's "if you ask for it, you will get it"; Blades' common knowledge answered
outright and the rest by a roll; PF1e's own split — Knowledge (local) is what you know
(rulers and laws DC 10, common rumour DC 15, hidden organisations DC 20, "Try Again:
No") and Diplomacy (gather information) is finding out (1d4 hours, retryable); PF2e's
"some groups find it simpler to have players roll all secret checks … while others enjoy
the mystery — the switch is the table's"; BG3's "Hide Passive Rolls" set once per
campaign after players objected.

### Built

- **Tiers by key** (`gm_search.tier_of`): hidden — Secret, Shadow Power, Hidden Power,
  Conspiracy, Underworld…; rumour — Tension, Volatility, Rivals, Turning Point,
  Limitations, Weakness…; everything else public. An unknown key is public: the world's
  record is mostly the kind of thing anybody in the town could tell you. `dossier` and
  `passages` take `allow`, default public only; a section titled with a hidden key is
  kept too; `withheld_from` says what was kept.
- **`/gm`**: public facts answered. Rumour rides ONE secret Knowledge (local) roll per
  place (DC 15), remembered in `scene.said["knows:<place>:rumour"]` so re-asking is
  fruitless. Hidden never reaches the model. What was kept is remembered
  (`gm:withheld`), and the answer ends with the route: with the table rule
  `knowledge_offer` on, "There is more here your character wouldn't know yet. Say the
  word ('tell me anyway') if you want it, or find it out in play: ask around
  (Diplomacy, an hour or four)"; off, only the in-play route. "tell me anyway" re-asks
  the withheld question with every tier allowed. Known trade-off, accepted with the
  ruling: the offer tells the player a secret exists.
- **Two table settings** (`rules/houserules.py`, the shelf page): `knowledge_offer`
  (default off) and `content` — "fade" (default: when a scene turns to intimacy, say
  that time passes and pick the scene up after; a transition, not a stall) or
  "explicit". `prompts.content_line` puts the choice in every prose briefing. The app
  has a position now, and the guards no longer decide it by accident.
- **What was agreed** (item 22's memory): when coin changes hands the view writes
  "Kesst Vayr paid the woman 10 gp for the night" into `scene.said["agreements"]` from
  the engine's own tell and the player's own "for …"; `scene_now` carries it as fact
  until the party moves rooms. The negotiation and the payment can leave the window
  now; the agreement does not.

## The engine's small doors (group 6)

- **An `xp` op** (`_op_xp`, through `award_xp`, the one writer), and `/cheat` reading a
  wish that is a number in code before the model: "I gain 2000 experience" is an `xp`
  op, "I have 1000 gold" a `give` of gp (`judgement.cheat_intents`). Twice on
  2026-09-18 the cheat did nothing because no op carried experience.
- **The dice card** prints its total row only when there is more than one term ("Str x2
  +38" over "your modifier +38" was the same number twice), and the reason line wraps
  instead of clipping.
- **The giver in the room** (item 7): a card whose person is standing here goes quiet in
  two turns rather than twelve, and the pull says "X is standing here and has a reason
  to speak of it: they approach the player and say the first word about it". Presence
  was a listing; a listing makes nothing happen.
- **The watcher's scope**: a card advances only on a fact about it — one of its
  identity words or one of its people in the sentence. The water-rights card advanced
  from inside a brothel on "the current transaction is a private matter" and paid 200 XP;
  such an advance is now logged as refused.

## Measured live, four runs on a copy of the `masta` save

`/gm who runs this town?` → `/gm tell me anyway` → the same question again →
`/cheat I gain 2000 experience`.

| Run | Result |
|---|---|
| 1 | **500**: the sheet refuses an untrained Knowledge (local) roll. The Core Rulebook caps an untrained check at DC 10, under rumour's DC 15 — untrained means the character does not know, not that the app falls over. Caught. |
| 2 | The answer still named "an old veterans' league that holds significant shadow power": it came from the NARRATOR's brief, which the out-of-character call inherits. `gm_search.redact` added. |
| 3 | Still there: World Bible weaves a settlement's facts into its own paragraphs, and the Governance section restated what the league does. `gm_search.scrub` added — a sentence carrying two distinctive words of a withheld fact goes; the paragraph stays. |
| 4 | **The ruling, working.** "The town is governed by a local reeve … the day-to-day administration is handled by tax-farmers … — Some of what the town keeps, your character has not learned. Ask around in play: Diplomacy, an hour or four, and it can be tried again." Then "tell me anyway": "there is a shadow power in the form of an old veterans' league that no one in office will cross." Then the same question again: withheld once more, the roll remembered — PF1e's "Try Again: No". |

`/cheat I gain 2000 experience`: "You gain 2,000 XP for the author's word (2,465 of
2,000 for level 2). Enough to advance — it will settle with a night's rest", read in
code, the author's number kept, no model call. It did nothing twice on 2026-09-18.

Still owed live: a giver in the room across three quiet turns (item 7), and the
`knowledge_offer` rule turned on so the answer offers rather than only naming the route.
