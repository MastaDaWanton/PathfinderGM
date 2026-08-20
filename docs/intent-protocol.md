# The GM-to-engine intent protocol

The core interface of the app. The GM agent declares *what the fiction calls for*; the
engine decides *what happens*. This document defines the boundary, the wire shapes, and
the mechanical checks that keep the GM on its side of it.

Read `architecture.md` first — this is the detailed design of one line in it: **the GM
proposes; the engine disposes.**

---

## 1. The line

The single most important thing here is which side of the boundary a given number lives
on. The rule:

> **The GM supplies what the fiction determines. The engine supplies what the sheet
> determines.**

| The GM may declare | The engine alone decides |
|---|---|
| That a Reflex save is called for | The PC's Reflex modifier, and every term in it |
| Who is acting, and on what | Whether that actor can act at all (dead, stunned, out of actions) |
| That the orc attacks the PC | The orc's attack bonus, iteratives, crit range, damage dice |
| How hard something is, as a **band** | The DC integer that band maps to |
| That a circumstance helps or hinders | That "helps" is worth exactly +2 |
| Which spell an NPC casts | Its save DC, its caster level, whether the slot exists |
| That time passes, roughly | Buff expiry, condition durations, the world clock |
| That a hazard deals fire damage | How much, and who it catches |

If the GM emits a number the engine also owns, **the engine ignores it and logs the
discrepancy.** It is not an error and it does not stop the turn — models will do this, and
a turn that dies because the model said "+7" is worse than one that quietly overrides it.
But the log is the early-warning that a prompt has drifted.

This applies to whole *parameters*, not just values. `ENGINE_OWNED_PARAMS` in
`rules/intents.py` lists the ones the GM keeps supplying — `damage_type`, `dice`,
`damage_roll`, `attack_bonus`, `target_ac` and friends — and they are dropped and
recorded on the intent. A param that is merely **unrecognised** is still rejected
outright, and the difference matters: a dropped engine-owned param is a value we can
already compute, while an unknown one is a mechanic the GM believes it applied and we
have never heard of.

Hard-rejecting the first kind cost five consecutive attempts to attack a guard in live
play, over three params the engine reads off the weapon anyway.

### Why bands and not integers

The GM does not pick DCs as numbers. It picks from the PF1e difficulty table's own
vocabulary, and code maps the word to the number:

| Band | DC |
|---|---|
| `very_easy` | 0 |
| `easy` | 5 |
| `average` | 10 |
| `tough` | 15 |
| `challenging` | 20 |
| `formidable` | 25 |
| `heroic` | 30 |
| `nearly_impossible` | 40 |

A model asked for a calibrated integer gives you DC 18, then DC 17 for the same wall an
hour later, then DC 25 for a locked door because the scene felt tense. A model asked to
choose one of eight words is doing a classification task, which it is good at, and the
calibration lives in code where it can be tuned once.

An explicit `{"value": 18}` is still accepted — it is the natural thing to write and the
user's own example — but the engine **clamps it** to the band range plausible for the PC's
level and records the clamp. Supervised, not forbidden.

Circumstance modifiers are the same shape: a closed enum, not a number.
`favorable` → +2, `unfavorable` → −2, per 1e's standard circumstance modifier. The GM
cannot invent +7 because there is nowhere to put a 7.

---

## 2. The turn cycle

```
  player types
       │
       ▼
  ┌─────────────────────────────────────────┐
  │ GM CALL 1  ──►  { narration, intents[] }│   the expensive call
  └─────────────────────────────────────────┘
       │
       ▼
  VALIDATE (code, instant)  ──► reject / repair-call / accept
       │
       ▼
  RESOLVE (code, instant)
       │
       ├── needs a player roll? ──► suspend, raise dice popup, resume on input
       │
       ▼
  outcomes[] — rolls itemised, verdicts, state deltas, one `tell` each
       │
       ▼
  ┌─────────────────────────────────────────┐
  │ GM CALL 2  ──►  consequence narration   │   short; streams; often <150 tokens
  └─────────────────────────────────────────┘
```

Two model calls per mechanical turn, and **zero for a turn that is only talk** — which is
most turns. Call 1 carries the world and campaign context and is the one worth optimising.
Call 2 is handed a small packet of facts and asked only to say them well; it needs almost
no context and can run on the cheap model if the expensive one is slow.

The split is at the point of mechanical uncertainty. Call 1's narration must contain only
what is true regardless of how the dice land — the wind-up, never the landing. That is
enforceable (§5), which is why the split is here and not somewhere more convenient.

---

## 3. Intent

```json
{
  "op": "save",
  "actor": "pc",
  "target": null,
  "because": "the gantry pin shears under her weight",
  "params": {
    "save": "reflex",
    "dc": { "band": "challenging" },
    "on_failure": { "damage": "2d6", "type": "bludgeoning" },
    "on_success": { "damage": "half" }
  },
  "visibility": "player"
}
```

**Envelope fields**

| Field | Meaning |
|---|---|
| `op` | One of the ops below. Closed set. |
| `actor` | A ref (§3.1). Who is doing it. |
| `target` | A ref, a list of refs, or `null`. |
| `because` | One clause of fiction. Carried into the outcome so call 2 keeps the thread, and written to the player-visible log so any roll can be explained. |
| `params` | Op-specific; every op's params are a closed schema. |
| `visibility` | `player` — the player rolls it on the popup. `hidden` — the engine rolls it and the player never sees the number. Defaulted by op, overridable by the GM. |

### 3.1 Refs

Never a name. `"pc"`, or a 12-char World Bible entity id (`"94fb91cb2a3d"`), or an
encounter-local combatant id (`"c3"`) for things that exist only in this fight.

This is the `Ground every name` lesson from World Bible with teeth: the engine has a
registry of refs it knows, and **an intent naming a ref that is not in it is rejected
outright.** The GM cannot cause the orc that does not exist to attack. If it wants a new
NPC on the board it must ask for one with `spawn`, which goes through the same validation
and gets a real id.

### 3.2 Ops (v1)

| Op | Params | Notes |
|---|---|---|
| `check` | `skill`, `dc`, `opposed_by?`, `circumstance?`, `aid?` | Skill and ability checks. `opposed_by` makes it a contest; the engine rolls both sides. |
| `save` | `save`, `dc`, `on_success?`, `on_failure?` | Fort / Ref / Will. |
| `attack` | `weapon?`, `full_attack`, `power_attack?`, `manoeuvre?` | Engine owns BAB, iteratives, size, proficiency, crit range and every modifier. **Defaults to `player` visibility** — the PC rolls their own to-hit *and* their own damage. `power_attack` is the GM declaring a tactical choice; the −1/+2 and its scaling are the engine's. `manoeuvre` resolves as CMB against the target's CMD — see below. |
| `cast` | `spell`, `at?` | Engine checks the slot exists, computes DC and caster level, and **emits the derived saves and attacks itself** — the GM does not get to also declare them. |
| `damage` | `amount`, `type`, `to` | Environmental and untyped sources only; weapon damage rides on `attack`. |
| `condition` | `condition`, `to`, `duration` | Applied conditions and buffs, with duration in rounds/minutes so the engine can expire them. |
| `begin_encounter` | `sides`, `surprise?` | Rolls initiative for everyone, establishes the turn order. |
| `move` | `who`, `zone` | `engaged` / `near` / `far`. No grid, per the architecture decision. |
| `spawn` | `from_entity_id?`, `template`, `count` | Puts a creature on the board and returns its ref. |
| `advance_time` | `amount`, `unit` | Ticks durations, rest, and the world clock. |
| `narrate_only` | — | **Explicit.** Says "this turn had no mechanics." |

`narrate_only` exists so that an empty `intents` list is unambiguously a *failure* rather
than a quiet "nothing happened". Without it, a model that forgets to emit intents is
indistinguishable from a conversation beat, and that failure would be invisible. With it,
it is a one-line assertion.

---

## 4. Outcome

What resolution produces, and what call 2 is handed.

```json
{
  "intent_id": "i1",
  "op": "save",
  "status": "resolved",
  "rolls": [
    {
      "ref": "pc",
      "die": "1d20",
      "raw": 9,
      "modifiers": [
        { "value": 2, "source": "base Reflex (Rogue 1)" },
        { "value": 3, "source": "Dex" }
      ],
      "total": 14,
      "visibility": "player"
    }
  ],
  "dc": 20,
  "verdict": "failure",
  "margin": -6,
  "effects": [
    { "ref": "pc", "kind": "damage", "amount": 8, "type": "bludgeoning", "hp_after": 1 }
  ],
  "tell": "Kesst fails the Reflex save by 6. Kesst takes 8 bludgeoning damage.",
  "because": "the gantry pin shears under her weight"
}
```

- **`rolls[].modifiers` is itemised, always.** This is the entire payoff of the project: 1e
  bookkeeping made visible instead of trusted. It also makes the engine auditable — a wrong
  total is traceable to the term that produced it, and a test can assert on the terms.
- **`verdict` and `margin` are machine values.** Degrees of success come from `margin`;
  nothing downstream re-derives success from prose.
- **`tell` is a fact, not narration.** One or two flat sentences stating what happened,
  written by code from the outcome. Call 2's job is to make it good; call 2 is never given
  the option of making it *different*. If the GM model dies mid-turn, the `tell` is shown
  raw and play continues.
- **Hidden rolls produce a `tell` with the numbers stripped.** The guard's Perception 22
  becomes "the guard's head comes up — he's heard something." The GM never receives the
  number it might leak.

### 3.3 Combat manoeuvres

A manoeuvre is resolved exactly like a to-hit roll, with two substitutions: **CMB in
place of the attack bonus, and the target's CMD in place of its AC** (CRB pp. 198–201).
So it rides on the `attack` op rather than getting one of its own, and the player rolls
it like any other attack.

```json
{ "op": "attack", "actor": "pc", "target": "c1",
  "because": "she goes for his legs",
  "params": { "manoeuvre": "trip" } }
```

The GM names the manoeuvre and nothing else. The engine owns:

- **CMB** = BAB + Str + *special* size modifier — Dex instead of Str for Tiny or smaller.
- **CMD** = 10 + BAB + Str + Dex + special size modifier, with no Dex when flat-footed,
  and any penalty to AC carried across.
- The special size modifier runs **opposite** to the one for attack and AC: Small is −1
  here and +1 there.
- A natural 20 always succeeds and a natural 1 always fails.
- An incapacitated target is manoeuvred automatically, with no roll at all; a stunned one
  gives +4.
- The consequence, including degrees — trip that fails by 10 puts *you* on the ground,
  overrun by 5 knocks the target down, grapple grapples you both.

Legality is checked before anything is rolled: most manoeuvres only work on a target at
most one size category larger, and you cannot trip someone already prone.

### 4.1 What the player rolls

**The player rolls every die that is theirs**, and nothing else. For an attack that is
the to-hit, the critical confirmation if one is threatened, and the damage — so a single
attack can suspend three times, and a full attack once more per iterative. All of it is
one intent; the progress lives in the continuation.

The reverse is equally strict: **no roll that is not the PC's own can be player-visible.**
An NPC's attack, save or check is rolled by the engine and reaches the GM only as a
`tell`. The engine demotes any `player` visibility on a non-PC actor rather than trusting
the GM to get it right.

The player also never sees anyone else's numbers. Hidden rolls are stripped at the view
boundary, not hidden in the template — a number that never reaches the browser cannot be
read out of the page source either.

A damage pool comes back as **one number**, not one per die: you roll two dice, look at
them, and say "nine". The prompt carries `die`, `min` and `max` so the popup knows what it
is asking for; the engine still owns every modifier.

### 4.2 The suspend point

Player rolls make resolution a state machine, not a function. `resolve()` returns either an
`Outcome` or:

```json
{
  "status": "awaiting_player_roll",
  "prompt": { "label": "Reflex save", "die": "1d20", "modifier": 5,
              "breakdown": [...], "because": "the gantry pin shears" },
  "continuation": "<opaque resume token>"
}
```

The turn holds. The popup shows the player *what they are rolling and why*, with the
modifier already itemised, and the player rolls it. On resume, the engine continues the
same intent list from where it stopped — a list can contain several player rolls and
several hidden ones interleaved, and the order is preserved.

Hidden rolls never suspend. They resolve inline, and the player learns about them only
through narration.

---

## 5. Validation — the four mechanical checks

Every one of these is code that runs on the GM's emission before anything is resolved.
None of them is an instruction in a prompt. This is the World Bible lesson applied to the
core loop: **detect mechanically, repair with a targeted call.**

1. **Schema.** Unknown `op`, missing params, wrong types → rejected.
2. **Ref registry.** Every `actor`/`target` must be a ref the engine already knows.
   Invented names → rejected.
3. **Legality.** The actor must be able to act; the spell slot must exist; the manoeuvre
   must be available. A dead orc does not attack.
4. **The outcome-claim detector.** Call 1's narration is scanned for mechanical assertions —
   "hits", "misses", "you take N damage", "you succeed/fail", "the blade bites", a bare
   number adjacent to `damage`/`HP`. **The GM is not allowed to state an outcome, and this
   is how we know.**

Only check 4 gets a repair call, and it is targeted and narrow: *"remove the outcome claim
from this sentence; change nothing else."* Checks 1–3 are hard rejections with a
regenerate, because a malformed intent has no repairable content.

Check 4 is the one that makes the architecture's central promise true. "A persuasive model
narrating a hit that actually missed" is not prevented by asking the model not to — it is
prevented by looking, in code, every single turn, and by a test that documents exactly
which phrasings got through before the detector existed.

---

## 6. Worked example

Pangrella, the fixture's home town — 21 of the 47 cast live there, and its `Tension` fact
reads *"Tensions between winged nobility and merchant castes."* The PC is trying to slip
into a guild workshop at night.

**Player:** *I wait for the lamp to swing away, then go over the wall.*

**Call 1 emits:**

```json
{
  "narration": "The lamp on its chain sweeps the yard wall, pauses at the top of its arc, and starts back. Behind it a guildhand leans in the doorway, half-asleep over a cup.",
  "intents": [
    { "op": "check", "actor": "pc", "because": "going over the wall while the lamp is away",
      "params": { "skill": "stealth", "opposed_by": { "ref": "c1", "skill": "perception" },
                  "circumstance": { "value": "favorable", "why": "the lamp is at the far end of its swing" } },
      "visibility": "player" }
  ]
}
```

Note what the GM did *not* do: it did not say she gets over the wall, it did not give the
guildhand a Perception bonus, it did not turn "favorable" into +2, and it referred to the
guildhand as `c1` — a ref the engine minted when the NPC entered the scene.

**Validation:** narration scanned — no outcome claim. `c1` is registered. Schema fine.

**Resolution:** the engine rolls the guildhand's Perception first and **hidden** —
1d20+3 → 19 — so the prompt is fully formed before anything suspends and a resume can
never re-roll it. Then the opposed check needs the player's roll, so it suspends. Popup:
*Stealth, 1d20+9 — +1 rank, +3 class skill, +3 Dex, +2 Stealthy — beat 17.* (19, less 2
for the favourable circumstance.) Player rolls 13 → 22. Verdict `success`, margin +5.

**Call 2** is handed the `tell` — *"Kesst beats the guildhand's perception by 5"* — plus
`because`, and writes two sentences of prose. It is never told the 19.

---

## 7. Deliberately not in v1

- **No readied actions or held actions.** They need an interrupt model in the state machine
  and there is no cheap version.
- **No attacks of opportunity.** They follow from movement, and movement is zones for now;
  getting AoOs right without a grid is its own design.
- **No multi-intent atomicity.** If intent 3 of 5 fails validation, intents 1–2 have already
  applied. Acceptable now; will need a transaction when combat gets long.
- **No GM-authored damage on `attack`.** Weapon damage comes from the sheet, always.

---

## 8. Who writes what

The architecture doc's warning — *two writers, one save* — resolved for the state this
protocol touches:

| State | Owner | The other one may |
|---|---|---|
| HP, conditions, buffs, durations, initiative, zones, inventory, XP | **Engine** | read |
| The clock (what time it is) | **Engine** | read |
| Faction influence, NPC disposition, standing, hooks, what-moved-while-you-were-away | **World agent** | read |
| Scene transcript and the roll log | **Engine** (append-only) | read |

No field has two writers. The world agent never touches a hit point; the engine never
touches a faction's standing. When play should shift a faction — a burned bridge — the
engine emits an *event* to the world agent's queue and the world agent decides what it
means.
