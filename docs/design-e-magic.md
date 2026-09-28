# Design E — magic: areas, aims, harm, preparation

Phase 0 research for Lane E of `docs/fix-plan-2026-09-28.md`. Read-only sweep; nothing
here is built. Every claim about the code was read on branch `fixes-2026-09-28`
(93ac2d4); every claim about the rules cites the page it came from, and where a claim
could not be sourced it says so.

---

## 1. Items covered

| Item | What the player saw | Measured cause |
|---|---|---|
| 21.1 (backend) | The Cast button sends; the player wants it to attach a spell to the input as a chip and write the use | `/api/say` takes only `text`; `/api/cast` takes `spell` + `at` (a ref) and nothing else (`play/views.py` `cast_act`) |
| 21.2 | "Burning hands into the tree tops" cannot be expressed | `cast` params are `at, level, defensively, square, choose` (`rules/intents.py:406`); no aim at a direction, point or object; no reader of flammable terrain |
| 21.4 | A wizard with 50 spells in the book and none prepared | nothing prepares at creation; **and `Actor.rest` wipes `self.prepared = {}` every night** (`rules/sheet.py:3305`), so every prepared caster also *wakes* with nothing — new finding, see §4.7 |
| 22.1 | Burning Hands resolved `targets: []`, `1d4 — 1`, the man at 4/4 | `_op_cast` takes targets only from `intent.target` / `params.at`; `grid.cone/line/burst` are used only by `_squares_for` (manifestations). Live save: PC at (4,7), c8 at (1,8), 15 ft apart — **a west cone from `grid.cone` contains (1,8)**; the geometry existed, nothing asked it |
| 22.2 | Harmful magic started no fight | `_op_cast` never calls `_ensure_encounter` (it is called from `_op_attack` and four spawn/ambush paths only) |
| 22.3 | Nothing moved attitude | no harm → attitude rule anywhere; `judgement.note_heat` counts damage only from `op in ("attack","damage")`, so a spell's damage does not even reach the crowd |

Scale of the gap, measured over the 3,040 spells: 96 spells with an `area` roll damage
dice at CL 5. By parsed shape: burst 25, spread 17, cone 16, radius 10, cube 7, line 6,
square 2, emanation 2, unparsed 11 (e.g. scourge-of-the-horsemen "30-foot burst" — no
"radius", so `spells.parse_area` misses it). Every one of them resolves today exactly as
Burning Hands did.

---

## 2. Prior art

### 2.1 The rulebook (PF1e Core Rulebook, via Archives of Nethys)

**Aiming a Spell** ([aonprd.com/Rules.aspx?ID=228](https://www.aonprd.com/Rules.aspx?ID=228);
[legacy magic chapter](https://legacy.aonprd.com/coreRulebook/magic.html)):

- Target vs Area are different headings. A targeted spell is cast "on creatures or objects,
  as defined by the spell itself". An area spell's caster chooses only the origin: "you
  select the point where the spell originates" and otherwise does not control what is
  affected. So an area spell has no target list to fill in; **the geometry decides**.
- "The point of origin of a spell is always a grid intersection." A square is in the area
  when its far edge is inside it; touching only the near edge does not count.
- Burst: affects "whatever it catches in its area, including creatures that you can't
  see". Spread: like a burst "but can turn corners". Emanation: a burst that keeps
  radiating.
- Cone: "shoots away from you in a quarter-circle in the direction you designate", starting
  "from any corner of your square". Line: the same, in a line. Cylinder: a horizontal
  circle, shooting down.
- Areas catch objects too: "affects objects within an area you select" is the object form.
- Line of effect: "a straight, unblocked path"; a burst needs it from the origin to each
  square.

**Burning Hands** ([SpellDisplay Burning Hands](https://www.aonprd.com/SpellDisplay.aspx?ItemName=Burning%20Hands)):
Range 15 ft., Area cone-shaped burst, Reflex half. The cone's length is the range line —
which is why `parse_area` correctly refuses to invent a length and the cone must take it
from `range_value`. On objects: "Flammable materials burn if the flames touch them", and
burning items can be put out "as a full-round action". Duration instantaneous.

**Catching on Fire** ([Rules ID=331](https://aonprd.com/Rules.aspx?ID=331)): the risk is for
creatures exposed to "burning oil, bonfires, and noninstantaneous magic fires"; DC 15
Reflex, 1d6 now and each round until a save succeeds. **So Burning Hands itself does not
set a creature alight** — it is instantaneous. Standing in brush it lit is a bonfire.

**Forest Fires (CR 6)** ([Rules ID=293](https://aonprd.com/Rules.aspx?ID=293)): three
dangers (heat 1d6/round, catching on fire, smoke); a leading edge at 120 ft/round in a
moderate wind; burns 2d4 × 10 minutes. **Smoke** (environment chapter): Fortitude DC 15,
+1 per previous check, 1d6 nonlethal after two consecutive rounds of choking, and smoke
gives concealment. **No rule could be found for how a small ignition grows into a forest
fire** — the CRB describes a fire already burning. Said plainly, because it decides §4.4.

**Forest terrain** ([legacy environment chapter](https://legacy.aonprd.com/coreRulebook/environment.html)):
a typical trunk "has AC 4, hardness 5, and 150 hp"; light undergrowth doubles movement
and gives concealment; heavy undergrowth 30% miss chance. The canopy is described only as
platforms "far above the surface floor" — **no height is given**.

**Objects** ([Smashing an Object, ID=126](https://aonprd.com/Rules.aspx?ID=126)): energy
attacks deal half damage to most objects, halved before hardness; "Fire might do full
damage against parchment, cloth". "Nonmagical, unattended items never make saving
throws." Items carried or worn by a creature are "assumed to survive a magical attack"
unless the spell says otherwise (magic chapter). So a CL 1 Burning Hands (1d4, halved,
minus hardness 5) does nothing to a trunk, and lights the dry stuff around it.

**What counts as an attack.** Invisibility defines it: an attack includes "any spell
targeting a foe or whose area or effect includes a foe"
([Invisibility](https://www.aonprd.com/SpellDisplay.aspx?ItemName=Invisibility)); "actions
directed at unattended objects" do not count. This is the book's own line between the
two halves of item 21: fire into the canopy is not an attack; fire whose cone contains the
man is.

**Attitudes.** The CRB Diplomacy table gives only DCs by attitude
([Diplomacy](https://www.aonprd.com/Skills.aspx?ItemName=Diplomacy)); I could **not** find
a PF1e rule that says "a creature you attack becomes hostile". What the book does say:
Diplomacy is "ineffective in combat and against creatures that intend to harm you";
Charm Person gives +5 to the save when the creature is "threatened or attacked by you",
and "any act ... that threatens the charmed person breaks the spell"
([Charm Person](https://www.aonprd.com/SpellDisplay.aspx?ItemName=Charm%20Person)). The
descriptive glosses often quoted for the track ("will take risks to hurt you") are the
3.5 SRD's; the d20srd page refused the fetch (403), so that attribution is unverified.

**Starting a fight** ([combat chapter](https://legacy.aonprd.com/coreRulebook/combat.html)):
initiative is rolled when combat begins; if some combatants are unaware, a surprise round
happens first, in which aware combatants take "a standard or move action" — casting is a
standard action — and the unaware do not act.

**Preparation** (magic chapter): a wizard rests 8 hours, then studies (1 hour for all
spells). Until then the wizard has only spells "already had prepared from the previous day
and has not yet used", and may "abandon some or all of them to make room". **Uncast
spells survive the night in 1e.** `Actor.rest` contradicts this.

### 2.2 Implementations

- **Foundry VTT, PF1 system + Advanced Templates PF1**
  ([ckl-advanced-templates-pf1](https://github.com/dmrickey/ckl-advanced-templates-pf1)).
  The module exists because default placement allows area effects that "don't follow the
  rules": it adds circles on grid intersections, cones and lines that originate from the
  caster, and burst/emanation/spread as distinct kinds. "Allow 15' Alternate Cone" is a GM
  setting said to follow a Paizo FAQ, and non-standard cone rotations are off by default
  for RAW. **Auto-targeting is a player-toggled option** ("Target Tokens in Template") —
  a preview that marks tokens, not a rule the system enforces.
- **Walled Templates** ([fvtt-walled-templates](https://github.com/caewok/fvtt-walled-templates)):
  walls may block, not block, or "spread around corners" (the spread rule); auto-targeting
  has four modes, from disabled to always; and a token counts as caught either when its
  centre point is inside or when a set percentage of its area is covered. Two definitions,
  left to the table.
- **Midi-QOL (dnd5e)** ([tposney/midi-qol](https://github.com/tposney/midi-qol)):
  "Auto target on template draw" with always / ignore-defeated / walls-block, and a note to
  enable only one sort of template targeting, because the system, midi and DF-QoL each
  shipped their own. Issue #446 reports cone and cube auto-targeting as unreliable at the
  edges ([issue 446](https://gitlab.com/tposney/midi-qol/-/issues/446)).
- **Avrae** (Discord): the player lists every target by hand with `-t`; no geometry
  ([Avrae player guide](https://avrae.readthedocs.io/en/latest/cheatsheets/pc_combat.html)).
  Our current shape — and item 22 is what it costs with no human doing the listing.
- **Roll20**: no first-party area auto-targeting could be sourced; not claimed.
- **Skyrim** ([UESP Crime](https://en.uesp.net/wiki/Skyrim:Crime)): assault is a witnessed
  crime (40 gold); a hostile spell effect on an NPC counts; allies take three hits before
  turning hostile; killing every witness before they report wipes the bounty.
- **RimWorld** ([Social](https://rimworldwiki.com/wiki/Social)): a landed hit in a social
  fight gives "Harmed me", −15 opinion for 10 days — the same −15 as "Insulted".
  `rules/provocation.py` already maps RimWorld's −15 to `INSULT = 10` on regard's 0–100.
- **Divinity: Original Sin 2** ([fextralife, Environmental Effects](https://divinityoriginalsin2.wiki.fextralife.com/Environmental+Effects)):
  fire interacts with typed surfaces (oil and poison explode), water puts it out into
  steam, and a fire surface that times out leaves smoke. Whether vegetation burns could
  not be confirmed from the fetched pages.
- **Pathfinder: Kingmaker** (community reports on the Steam forums, secondary): a prepared
  caster's memorised list persists and is re-prepared on rest; a reported bug left slots
  empty after rest when bonus slots from buffs flickered.
- **Baldur's Gate 3** (secondary: Siliconera, EIP guides): prepared spells can be changed
  any time out of combat rather than only on a long rest.
- **Attaching a structured thing to free text**: VS Code Copilot Chat's `#`-mentions and
  paperclip attach a file or symbol to a typed prompt as a chip
  ([Add context to chat](https://code.visualstudio.com/docs/chat/copilot-chat-context)).
  The model gets the words and the structured reference separately.

---

## 3. Tried and abandoned, and why

1. **Leaving area targeting to the humans.** Every VTT that auto-targets ships it as an
   option (Advanced Templates, Walled Templates, Midi-QOL), because a human GM can overrule
   the edge cases. We have no human GM: a toggle here is a toggle between the engine
   deciding and the model deciding, and the model deciding is how the man was burned in
   prose. **Take:** one rule, the book's, always on — and make the decision visible
   (cells on the map, names in the tell) so the player can dispute it the way a table
   would.
2. **Competing definitions of "caught".** Walled Templates offers centre-point *or* area
   percentage; Midi-QOL warns against enabling two targeting systems. **Take:** one
   function, `areas.lay`, the book's "far edge" rule, and nothing else in the codebase
   computes membership (the §8 ratchet).
3. **Square-centred bursts.** Measured here: `grid.burst((10,10), 20)` returns **61**
   squares; measuring from a grid intersection with the far-corner rule gives **44** for
   20 ft, **12** for 10 ft, **4** for 5 ft. The square-centred shape is 39% larger than
   the rule. The difference is exactly what Advanced Templates exists to fix. `_squares_for`
   (fog cloud and friends) carries the same defect today.
4. **The 15-ft cone.** Advanced Templates keeps an "alternate" 15-ft cone behind a setting,
   said to follow a Paizo FAQ; I could not find that entry in the CRB FAQ
   ([paizo.com FAQ](https://paizo.com/paizo/faq/v5748nruor1fm)). `grid.cone` gives 11
   squares for a cardinal 15-ft cone and 12 for a diagonal one. **Not changed;** an owner
   question (§9), since a table argument cannot be settled from an unfound FAQ.
5. **Walls and cones without line of effect.** Foundry's templates needed a whole module
   to stop at walls. `grid.line_of_sight` treats `obscuring` (fog, smoke) as opaque, but
   **line of effect is not blocked by fog**, only by solid barriers. **Take:** `areas.py`
   tests line of effect against `blocked` only, and does its own flood for spreads.
6. **Preparing only on a rest.** BG3 relaxed 5e's long-rest preparation to any time out
   of combat (secondary source). Kingmaker keeps a persistent memorised list and
   re-prepares it on rest. Both moved away from a blank page every morning. **Take:** a
   remembered loadout, re-prepared on rest, and the Spells tab still free to change it at
   any time out of a fight (it already is).
7. **"Harm = a regard nudge".** RimWorld's −15 for a hit equals its −15 for an insult —
   burning a man as mild as calling him a coward. **Take:** harm moves a stranger a step,
   to hostile; regard numbers only for people already on your side (§4.5).
8. **Fire that spreads by fiat**, and DOS2 surface spam players modded down
   ([Steam thread](https://steamcommunity.com/app/435150/discussions/0/2935742047976273017/)).
   **Take:** a burning patch with a sourced lifetime and no spread (§4.4).

---

## 4. Recommended design

### 4.1 The `aim` param

One new optional `cast` param, `aim`, a string in a closed grammar:

| Form | Meaning | Where it comes from |
|---|---|---|
| `ref:<ref>` | a creature present | the chip plus "at the man", the interpreter's target, the combat bar |
| `self` | the caster | touch, "centred on you" |
| `dir:<n\|ne\|e\|se\|s\|sw\|w\|nw\|up\|down>` | a direction from the caster (map axes) | the map UI; derived from a ref or object when the spell is a cone or line |
| `point:<x>,<y>[,<z>]` | a grid intersection: the top-left corner of cell (x, y) | a map click |
| `object:<words>` | a prop lying here, or a terrain feature | "into the tree tops", "at the cart" |

Legacy stays: `at` is read as `ref:<at>`; `square` stays as the manifestation centre and is
read as `point:` when there is no `aim`. `rules/intents.py` adds `"aim"` to the cast's
optional params. Parsing lives in `areas.parse_aim(text) -> Aim`
(`Aim(kind, ref, direction, cell, words)`).

**Validation (`_check_cast`, E-owned)** raises with a `code` the plan loop can act on:

- `ref:` not in the scene → `no_such_target`;
- `point:` off the grid, beyond `spells.range_feet`, or with no line of effect from the
  caster → `out_of_range` or `no_line_of_effect`;
- `object:` matching nothing here → `no_such_object`. The message lists what is here, in
  the classbuilder style ("Nothing here called 'the well'. Here: undergrowth, trees,
  canopy, a broken cart.");
- a spell with a counted `targets` line (e.g. "one creature") given `dir:` or `point:` →
  `wrong_aim` ("Magic Missile picks out creatures; name one");
- an area spell with no aim and no target → `no_aim`.

The existing refusals gain codes too: `unprepared`, `no_slots`, `not_known`,
`not_on_list`, `too_high`, `ability_too_low`. `IntentError.__init__` gains
`code: str = ""`. Lane A's plan-loop short-circuit (21.3) keys on
`exc.code in PLAYER_FIXABLE`. Matching the message text would be law one's error again,
one layer up.

**Converting** (`areas.resolve`): a cone or line given `ref:`/`object:` takes the map
direction whose cone contains the thing, nearest the axis first; a burst given `ref:`
centres on the intersection nearest the creature. Directions stay **internal** — the world
has no bearings (item 19.5), so the tell names what was aimed at ("at the man in a stained
leather jerkin", "up into the canopy"), never "westward".

### 4.2 `rules/areas.py` — the one place membership is decided

Pure functions. They read `Scene` (grid, positions, actors, props, `at`) and never write.

```python
@dataclass(frozen=True)
class Area:
    shape: str            # cone | line | burst | spread | emanation | cylinder | cube | none
    origin: tuple         # a cell (x, y, z); for bursts the intersection = top-left corner of it
    length_ft: int        # cone/line length, burst radius, cube side
    direction: str        # for cone/line: one of grid.DIRECTIONS or up/down
    cells: frozenset      # (x, y, z) cells the area covers, after line of effect
    measured: bool        # False = no grid here; cells empty, membership by aim only

def shape_of(spell, caster_level) -> dict       # parse_area + the cone's length from range,
                                                # "30-foot burst", line length; {} = prose
def lay(scene, caster_ref, spell, cl, aim) -> Area
def caught(scene, area, *, exclude=()) -> list[str]            # creature refs, volume overlap
def objects_caught(scene, area, spell) -> list[dict]           # see below
def features_here(scene) -> dict[str, frozenset]               # feature word -> cells
def resolve(scene, caster_ref, spell, cl, aim) -> Aim          # ref/object -> direction/cell
def aim_from_words(scene, caster_ref, words, spell) -> str | None   # deterministic grounding
```

**Geometry, by the book:**

- **Cone**: origin at the caster's square, as `grid.cone` does, and the caster's own square
  excluded. For horizontal directions `grid.cone`'s cells are reused unchanged (its
  quarter-circle reading and its 5-10-5 edge are already tested). They are extruded
  vertically by the same "spread no wider than depth" rule, so a flier in front of the
  caster is caught and nothing below `z = 0` is. `up`/`down` build the same wedge about
  the vertical axis. This is a house rule, marked the way `grid.distance` marks its
  vertical: the CRB states no vertical clause for cones.
- **Line**: `grid.line`, origin the caster.
- **Burst / emanation / radius**: **from a grid intersection**, a square included when its
  far corner is within the radius by 5-10-5 counting (44 / 12 / 4 squares at 20 / 10 /
  5 ft). Sphere to `z ≥ 0` as `grid.burst` already argues.
- **Spread**: the same radius, flooded from the origin around `blocked` cells, so it turns
  corners.
- **Cylinder**: `grid.cylinder`. **Cube / square**: side from the text, origin the chosen
  intersection.
- **Line of effect**: a cell is dropped when every corner line from the origin to it
  crosses a `blocked` cell (walls, trunks). `obscuring` never blocks it (smoke and fog do
  not stop fire). Bursts and cones are filtered; spreads are flooded instead.
- **Membership**: a creature is caught when any cell of its `grid.volume` is in
  `area.cells`. That is the far-edge rule applied to footprints, since a cell is either
  wholly in or wholly out.

**Objects caught** returns records of three kinds:

- `{"kind": "prop", "name", "square", "burns": bool}` for unheld props at this place whose
  square is in the area. `burns` is true for fire-descriptor spells on props whose name or
  material words say cloth, parchment, paper, rope, straw, thatch, oil or dry wood. This is
  the "Fire might do full damage" list, plus the spell's own "flammable materials".
- `{"kind": "feature", "name": "undergrowth"|"canopy"|"trees"|..., "cells": n, "burns": bool}`.
  Features are **derived from the place's floorplan terrain**, never from world names:
  in `forest`/`jungle`/`swamp` the `difficult` squares are undergrowth and the `blocked`
  squares are trunks; the canopy is the cells over the trunks from `CANOPY_FROM` up. The
  canopy's height is a house rule, because the CRB gives none (§9). `grassland` rough is
  dry grass; `farmland` rough is hedge. A closed table, `areas.FEATURES`, keyed on
  `floorplan.BY_TERRAIN` names.
- Attended objects are **not listed**: carried and worn items survive by the CRB default.

**Outside a map** (`scene.has_grid` false): `measured = False`, no cells. `caught` is
the `ref:` aim alone (theatre of the mind: the named creature is in it, nobody else).
Features are still known from the terrain, so "into the canopy" still finds the canopy,
and a manifestation lands "in the fiction only", as `_manifest` already says.

### 4.3 Per-creature saves and damage (22.1)

`_op_cast` changes at one seam. Where it computes
`targets = intent.targets() or [params.at]`, a spell with a parseable `shape_of` computes
`area = areas.lay(...)`, `targets = areas.caught(scene, area)` and
`objects = areas.objects_caught(...)`. Everything after — the dice rolled once, a save per
creature through `_roll_or_suspend_stage`, half on a save through `_apply_damage`,
troops, heal, `_hp_state_effects` — is **unchanged**. That loop was already the book's
("rolled ONCE ... everyone in the area saves against that number"); it was starved of
names. Each save also records an effect,
`{"kind": "save", "ref", "save", "total", "dc", "saved": bool}`, so a check can tell
"half" from "full" without parsing a tell. A spell whose area will not parse keeps today's
path and says `measured: false`.

The slot is still spent once, before anything is laid. A cast whose area catches only
the caster's companions is resolved normally; friendly fire is 1e.

### 4.4 No victim, and what burns (22.4's engine half, 21.2)

When `caught` is empty, **nothing is rolled**. There is nobody to save and nothing to
apply damage to, and objects of this kind take no damage roll: flammable materials
simply burn. The dice line `"1d4 — 1."` is omitted. The outcome carries `no_victim: true`
and the tell names it: "Bobby casts Burning Hands up into the canopy; the flames reach
nobody." Lane A's `empty_roll` check then has an engine fact to hold the prose to.

For a fire-descriptor spell, each `burns: true` object or feature is lit through one
executor, `Engine._ignite(objects, ctx)`, inside `_op_cast`'s riders. It places a
`Manifestation(what="burning undergrowth", terrain="none", squares=...)` and a second
`Manifestation(what="smoke", terrain="obscuring", squares=...)`. Its hazards come from
**new hazards.json rows (I3)** wired as `on_enter` wards the way `_manifest` already does:

- `burning-brush`: creatures in or entering the burning cells, per CRB Catching on Fire
  (DC 15 Reflex, 1d6, bonfire exposure) — `source` cites ID=331 and Burning Hands' text;
- `smoke`: CRB Smoke Effects (Fort DC 15 +1 per previous, 1d6 nonlethal after two
  rounds, concealment).

Lifetime: the only sourced duration is the forest fire's "2d4 × 10 minutes". **No
spread**, because no spread rate at this scale could be sourced. Escalation to the CR 6
Forest Fire is an owner question. A patch too far away is told as falling short: "the
flames fall short of the canopy". Nothing burns, and nothing is invented.

### 4.5 Harm opens the fight (22.2) and moves attitude (22.3)

**Harmful** = the spell's plan rolls damage (`plan["kind"] == "damage"` with dice), and
the area or target includes a creature not on the caster's side. That is Invisibility's
definition of an attack. Conditions (hold person, sleep) are deliberately out for now:
charm person is a Will-save spell too, and a charm opening a fight would be absurd. §9.

**The battle gate.** The shipped law is "first violence opens the fight, never resolves
it" (`tests/test_battle_gate.py`). A harmful cast with no fight running follows it
exactly as `_op_attack` does:

1. `areas.lay` + `caught` first (pure; nothing spent).
2. `_ensure_encounter(caster, target=caught_foes[0])`, then `join_fight(r)` and
   `rally(r)` for every other caught foe. `_ensure_encounter` takes one target, and an
   area's other victims would otherwise stay bystanders.
3. The caster keeps the turn (`scene.turn`, `scene.acted`), as the attack gate does.
4. Return an outcome with `{"kind": "battle_joined", "ref", "target", "op": "cast",
   "params": {"spell", "aim"}}` and no slot spent. The combat bar can then offer "cast
   as declared" in one click (Lane F, §5).

This is 1e's surprise round in the engine's existing shape: the aware initiator holds the
first action. The alternative is resolving the cast in the same batch as the surprise
action. It is defensible from the combat chapter and it breaks a shipped law, so it is an
owner question, not a default. The gate check must sit **before** the slot spend at the
top of `_op_cast`, and must honour `self._battle_joined` for a cast riding a
`begin_encounter`. Casts inside a running encounter resolve as today, plus: a caught
bystander is brought in with `join_fight` + `rally`, like a swing at a bystander.

**Attitude, as an ActiveEffect.** A new helper in `rules/attitude.py`:

```python
def harmed(engine, victim, by, source: str) -> dict | None
```

It is called for each caught creature when the cast resolves; a saved or resisted spell
counts, since being caught is the attack.

- A stranger, or anyone not travelling with the caster: `engine._set_attitude(victim,
  HOSTILE, rounds=None, source="spell:<id>")`. This is the one applicator, and it is an
  ActiveEffect. `rounds=None` also drops regard to the hostile floor, so the grudge
  outlives the hour. `_set_attitude` clears any charm: Charm Person's own "any act ... that
  threatens" rule, for free.
- A companion (`states.TRAVELS_WITH_YOU`, or friendly and up): **no step**. Instead
  `nudge_regard(victim, -HARMED, "harmed by <caster>")`, with `HARMED = provocation.INSULT`
  (10). That is RimWorld's "Harmed me" equal to its "Insulted", in the mapping this
  codebase already made.
- Already hostile: nothing.
- The tell is `attitude.said(...)` in words; the effect record is
  `{"kind": "attitude", "ref", "from", "to", "why": "harmed"}`.

**Witnesses** (conscious, not caught): no regard change (unsourced). They react through
the machinery that exists:

- `note_heat` must count damage effects from `op == "cast"`; one token in
  `gm/judgement.py:5733`.
- `_ensure_encounter` already calls `rally(target)` and `_law_joins()`, and ends the
  conversation (`end_talk("a fight starts")`).

A witnessed-assault crime ladder, `_witnessed_break_in` generalised, would apply equally
to swords, which make nobody "suspected" today. It is an owner question for both doors
together, not a spell-only rule.

**The sword door.** `_op_attack` has no attitude rule either. Adding `harmed()` to casts
alone would make fire cost a relationship and a rapier not. §6 asks for the one-line call
in `_op_attack`'s damage path.

### 4.6 The attachments → intent path (21.1)

1. **`/api/say`** (S3 stores, E acts) takes `attachments:
   [{"kind": "spell", "id": "burning-hands", "aim": "object:canopy"?}]`. `aim` is optional;
   the map picker supplies it. With an attachment, empty `text` is allowed and becomes
   "I cast Burning Hands." for the transcript.
2. **Before any model call**, `views.say` builds the skeleton
   `{"op": "cast", "actor": pc, "params": {"spell": id}, "because": "the player attached
   it"}` and dry-validates it in a snapshot. A refusal whose `code` is player-fixable
   (`unprepared`, `no_slots`, `not_known`, `not_your_turn`) returns 422
   `{"hint": for_a_person, "fix": {"kind": "prepare", "spell": id}}` at once. That means
   zero model calls, no transcript line, and no retry loop: the seven refused plans of
   item 21 become one sentence and a button.
3. **Aim**: the attachment's own `aim`; else `areas.aim_from_words(scene, pc, text,
   spell)`. That is deterministic grounding: an actor's name or head noun present → `ref:`;
   a feature or prop word present ("tree tops" → canopy) → `object:`; "up/overhead/into the
   sky" → `dir:up`. When the interpreter's reading has a `cast` act, its target or object
   span is preferred (I3 wires `interpret.ops_for`).
4. **The plan**: `agent.attachments` rides into the planner, as `agent.false_claim` does.
   `declared_ops` then requires `cast`, and `judgement.inject_cast(raw, text, scene,
   attached=...)` replaces or adds the cast with the chip's spell id. **The chip beats the
   words and the model** on which spell; the aim from step 3 is set if found.
5. **"If they write nothing, the model infers the use"**: an unresolved aim goes into the
   plan's declared `cast` as an `aim` property whose **enum is the legal aims here**:
   refs present, `self`, features and props here, `dir:up`. Ollama enforces enums
   (memory: ollama-schema-enforcement, 6/6). The model chooses; it cannot invent one. An
   aim still missing after that is refused `no_aim` to the player. Building the enum is
   E's `areas.legal_aims(scene, pc, spell)`; the schema line in `prompts._declared_op` is
   I3.
6. **`/api/cast`** (`cast_act`) takes `aim` alongside `at`, validated the same way.

The chip carries a spell id, never a name, so "one route for typed and attached casts"
holds: a typed "I cast burning hands at him" still goes through `inject_cast`'s name
match and reaches the same `cast` op, the same `aim`, the same `areas.lay`.

### 4.7 `casting.ensure_prepared(actor)` (21.4)

**The defect under the defect.** `Actor.rest` sets `self.prepared = {}`. Its comment
guards against keeping spells already cast, but `_op_cast` has unprepared the cast copy
since item 25. So the line now only destroys the uncast spells 1e says survive, and
guarantees every prepared caster wakes empty.

```python
def ensure_prepared(actor, *, kept: dict | None = None, reason: str = "rest") -> dict:
    """-> {"kept": {id: n}, "added": {id: n}, "empty": {level: n}, "from": "loadout"|"book"|"none"}"""
def empty_slots(actor) -> dict[int, int]       # slots_for minus prepared, per level > 0
def remember_loadout(actor) -> None            # called by /api/prepare after every change
```

Policy, in 1e's order:

1. Prepared casters only (`caster_data.kind == "prepared"`); spontaneous casters return
   at once. Level 0 is skipped (the engine already treats cantrips as unprepared-free).
2. **Kept**: `_op_rest` captures `kept = dict(actor.prepared)` *before* `actor.rest(kind)`
   and hands it in. The uncast spells survive, as the book says. (The cleaner fix is
   deleting sheet.py:3305; §6.)
3. **Refill** each level's remaining room (`slots_for` minus kept) from `actor.loadout`,
   the last preparation the player made (Kingmaker's persistent list).
4. **No loadout ever** (a fresh character): for `prepare_from == "spellbook"` casters,
   fill from the book **in the book's own order** (the order the player added spells),
   one of each distinct spell before any repeat. List casters (cleric, druid; 1,143 spells)
   get no invented choice: leave empty, and let the warning and prompt carry it. §9 asks
   whether the owner prefers a default for them too.
5. Domain slots (`domain:` ids) are kept, never auto-filled.
6. The tell is written by `_op_rest`: "Bobby prepares Burning Hands ×2 and Magic Missile
   from the book." Empty levels: "Level 1 slots stand empty: nothing is prepared in two
   of them."

Callers: `_op_rest` (E, Phase 2) and `campaign.new_campaign` (I1, Phase 3). The 1e study
hour (15 min per quarter of the slots) is **not** added to the rest clock in this pass,
because the rest already runs to dawn. Noted as a deliberate omission.

---

## 5. What the Phase-1 seams must provide

**`/api/say` (S3)** — accepts, validates and stores:

```
attachments: list[{"kind": "spell", "id": str, "aim": str (optional)}]   # max 1 spell
```

Validation: `kind == "spell"`, `id` a known spell id (`spells.get`), `aim` either absent
or matching `areas.AIM_PATTERN` (S3 may hold a copy of the regex; E owns the canonical
one). Persisted on the turn log entry as `attachments` (the same list), and on the agent
as `agent.attachments` for the turn only. Empty `text` is legal when `attachments` is
non-empty.

**S1 (sole owner of `agent.py` in Phase 1)**: pass `getattr(self, "attachments", None)`
into `judgement.declared_ops(..., attached=...)` and `judgement.inject_cast(...,
attached=...)`, both as keyword arguments defaulting to None. That keeps the call sites
byte-identical in behaviour with nothing attached, which is the inert-seam proof.

**Persisted fields** (S4, or sheet save/load if S4 does not own `Actor`):

- `Actor.loadout: dict[str, int]`, default `{}` on old saves; written by
  `casting.remember_loadout`.
- No new Scene field. Burning terrain is `Scene.manifests` + `Scene.wards`, which are
  already saved.

**Outcome fields the cast op emits** (the register entries Lane A checks against). All
live on the existing `kind: "cast"` effect unless marked:

| Field | Type | Meaning |
|---|---|---|
| `aim` | `{"kind": "ref"\|"self"\|"direction"\|"point"\|"object"\|"none", "value": str, "said": str}` | what was aimed at; `said` = the player's words for it |
| `area` | `{"shape": str, "length_ft": int, "origin": [x,y,z], "cells": int, "measured": bool}` | the laid area (cells as a count on the outcome; the list goes to the map state) |
| `targets` | `list[str]` | **unchanged name**, now = `caught` (Lane A's existing reader keeps working) |
| `caught` | `list[str]` | creature refs in the area |
| `caught_objects` | `list[{"kind": "prop"\|"feature", "name": str, "burns": bool}]` | things in the area |
| `no_victim` | `bool` | no creature caught; nothing rolled |
| `harmful` | `bool` | §4.5 definition |
| `fell_short` | `bool` | the aimed-at object is beyond the spell's reach |
| separate effect `{"kind": "save", "ref", "save", "total", "dc", "saved"}` | | one per saving creature |
| separate effect `{"kind": "attitude", "ref", "from", "to", "why": "harmed"}` | | one per attitude moved |
| separate effect `{"kind": "battle_joined", "op": "cast", "ref", "target", "params"}` | | the gate's deferral |
| separate effect `{"kind": "manifest", ...}` | | existing shape, for fire and smoke |

`/api/state` gains `scene.grid.areas`: the last cast's cells, for the map to draw once
(Lane F), and `pc.casting.empty_slots: {level: n}` for the sheet warning.

**Brief lines** (S2 registry, a member `gm/brief/burning.py`, I3): while a fire
manifestation stands, one line, in words:
`BURNING HERE (fact): the undergrowth nearby is alight, and the smoke from it drifts
through the trees.` No numbers, no compass. The narrator otherwise learns everything from
the cast's tell.

**`IntentError.code`**: `str`, default `""`. The values listed in §4.1 form the register
entry `PLAYER_FIXABLE = {"unprepared", "no_slots", "not_known", "not_your_turn",
"no_aim", "out_of_range", "no_such_object"}`, which E defines in `rules/intents.py` and
A imports.

---

## 6. Owned edits — Lane E list, confirmed and amended

Confirmed as the plan states:

- `rules/areas.py` (new);
- `casting.ensure_prepared` (+ `empty_slots`, `remember_loadout`);
- `_op_cast`;
- the cast branch of `_check_legality` (`_check_cast`);
- the rest method (`_op_rest`);
- `intents` cast schema;
- `attitude` (`harmed`, `HARMED`);
- `views.say`;
- `views.cast_act`.

Amendments:

1. **`Engine._squares_for`** to E. It is reached only through `_op_cast`'s riders, and it
   carries the square-centred burst (61 vs 44). Switch it to `areas.burst_cells`.
2. **`Engine._ignite`** (new method, E) beside `_manifest`.
3. **`rules/intents.py` `IntentError`** (`code` kwarg): E, the file's Phase-2 owner already.
4. **`gm/judgement.inject_cast`** and **`note_heat`** to E. Neither is in A's or D's list;
   `note_heat` is one token (`"cast"` in the op tuple).
5. **`gm/agent.py` call sites** to S1 in Phase 1 (§5), so no Phase-2 lane touches
   agent.py for this.
6. **`views.prepare_spells`** (calls `remember_loadout`) and **`views._state`**
   (`empty_slots`, `grid.areas`): E is already sole owner of views.py in Phase 2.
7. **`rules/sheet.py` `Actor.rest` line 3305**: delete the wipe. Nobody owns sheet.py in
   Phase 2. Either E takes this one method, or `_op_rest` works around it with `kept`
   (§4.7), which works but leaves a comment that is now false. **Recommend E takes it.**
8. **`_op_attack`, one call** to `attitude.harmed` where damage lands, so sword and spell
   obey one rule. Nobody owns `_op_attack` in Phase 2; recommend E, as a named one-line
   hunk. If refused, the harm rule ships for casts only and the doc says so.
9. **Not E**: `rules/grid.py` stays read-only. `areas.py` builds on it without edits.

Phase 3 scope, amended:

- **I3** keeps: `interpret.ops_for` (a `cast` act's target or object span → `aim`; and
  an `object`/`place` slot for `cast` in `ACT_SLOTS`, since "into the tree tops" arrived as
  a *target* and a `place` slot does not exist for `cast`); hazards.json rows
  `burning-brush` and `smoke` (and `forest-fire` only if the owner rules for escalation);
  `10-spells.js` sends `aim`; `gm/brief/burning.py`.
- I3 **adds** the `aim` enum in `prompts._declared_op` (it needs prompts.py for that one
  function), and a check that manifestations tick in minutes out of combat. Their
  docstring says they are "cleared with the encounter", and a fire lit outside a fight must
  outlive that.
- I3 **drops** "the rest-method prep call": `_op_rest` is E's in Phase 2 and the call
  lands there.
- **I1** keeps `campaign.new_campaign` → `ensure_prepared(reason="start")`.

---

## 7. World-agnostic notes

- Features come from `floorplan.BY_TERRAIN`'s closed vocabulary (forest, jungle, swamp,
  grassland, farmland…) and the grid's own `blocked`/`difficult` sets. Never from a world's
  place names or fact labels. A world with no forests still gets "undergrowth" wherever
  its terrain is forest; a place that falls through to open ground has no features, and
  "into the canopy" is refused with the list of what is here.
- The loadout fallback reads the character's own book order, not the world or a taste
  table.
- Harm and attitude read `states` and `attitude.TRACK` only; no people is special-cased
  (memory: the-world-owns-its-own-races).
- Directions are map axes, used internally; the tell and prose never get a compass word
  (item 19.5).
- Tests run across the three worlds via the `worlds` fixture. The area and harm tests use
  a synthetic forest place and a synthetic grassland, so neither depends on Aurvantis.

---

## 8. Tests and the live script

Unit tests (lane prefix `test_e_`), each docstring naming the measurement:

1. **`test_e_burning_hands_finds_the_man`**: Bobby's board, PC (4,7), c8 (1,8) 4/4 hp,
   Burning Hands prepared, `aim: ref:c8`, a running encounter so the gate is not in play.
   Assert `caught == targets == ["c8"]`; one `save` effect for c8; a `damage` effect for
   c8 unless the save succeeded on a rolled 1 (half of 1 is 0, so assert on the `save`
   record rather than on hp). Docstring: "measured 2026-09-28: 1d4 = 1, targets [], the
   man at 4/4 — the cone that contained him was never laid".
2. **`test_e_first_harmful_cast_opens_the_fight_and_defers`**: the same board, no
   encounter. Encounter live, c8 on the other side, `battle_joined` with `op: cast` and
   the aim in params, slot **not** spent, c8 hp unchanged, PC holds the turn.
3. **`test_e_harm_makes_a_stranger_hostile_as_an_effect`**: after test 1, `attitude.of(c8)
   == HOSTILE`, the change is an ActiveEffect with `source "spell:burning-hands"`, and
   removing it by source restores the prior step. A companion caught instead loses
   `HARMED` regard and keeps its step.
4. **`test_e_no_victim_rolls_nothing`**: `aim: dir:up` in the synthetic forest, nobody
   aloft. `no_victim` is true, no rolls, the tell has no dice line, and `caught_objects`
   holds `canopy` with `burns` (or `fell_short` under the chosen canopy height).
5. **`test_e_bursts_measure_from_an_intersection`** (44/12/4; docstring: `grid.burst`
   gave 61) and **`test_e_line_of_effect_ignores_smoke_not_trunks`**.
6. **`test_e_rest_keeps_what_was_not_cast`**: prepare 2, cast 1, rest → 1 kept + 1 from
   the loadout (docstring: `Actor.rest` wiped `prepared`). Plus
   `test_e_fresh_wizard_is_prepared_from_book_order` and
   `test_e_list_caster_is_warned_not_guessed`.
7. **`test_e_attached_unprepared_spell_answers_in_one_sentence`**: views.say with an
   attachment for an unprepared spell → 422 with `fix.kind == "prepare"`, and the model
   stub is called **zero** times. Docstring: seven plan attempts, a hand-off and a
   narrate_only for one refusal.
8. **Ratchet `test_e_one_area_function`**: no module but `rules/areas.py` and
   `rules/grid.py` calls `grid.cone|line|burst|cylinder` (`_squares_for` goes through areas).
9. `tests/test_three_laws.py` and `tests/test_battle_gate.py` unchanged and green.

**Live `cast-area` script** (`tools/narrator_audit.py`, R0 writes it; run once in the
serial queue):

- *Setup*: a fresh wizard from the synthetic world placed in a forest place;
  `ensure_prepared` (no manual prep); a stranger 15 ft away on the grid, a second 40 ft
  away, a companion beside the PC.
- *Step A*: say "I burn the stranger" with attachment `burning-hands`. **Pass**:
  `battle_joined` (op cast), encounter live, zero model retries on legality.
- *Step B*: combat cast with the declared aim. **Pass**: `caught` contains the stranger
  and not the far man; a `save` record; the stranger's hp is lower unless saved-to-zero;
  attitude hostile as an effect; `note_heat` kind `violence`; Lane A's `empty_roll` and
  victim checks raise no finding; the prose names no one hurt outside `caught`.
- *Step C*: new scene, say "into the tree tops" with the attachment. **Pass**:
  `no_victim` true, no dice line, the canopy in `caught_objects`, fire and smoke
  manifests (or `fell_short`), no encounter, no attitude effects, prose describes no
  wound, soot or knockback on anyone.
- *Step D*: attachment for an unprepared spell. **Pass**: 422, zero model calls.
- *Step E*: attachment with empty text and one stranger present. **Pass**: a legal `aim`
  from the enum, and the cast resolves or defers per the gate.
- *Pass overall*: A–E all pass on two of two runs, on a quiet Ollama.

---

## 9. Open questions for the owner

1. **Gate or surprise round?** Recommended: a first harmful cast *defers* like a first
   swing (the shipped battle-gate law), with "cast as declared" one click away.
   Alternative: resolve it as the aware caster's surprise-round standard action (CRB
   combat chapter). This changes a shipped law, so it is yours.
2. **Canopy height.** The CRB gives none. Proposed house rule: the canopy starts at 10 ft
   (level 2), so a 15-ft cone upward reaches its underside. Or: canopies are out of reach
   of anything shorter than 30 ft.
3. **Fire escalation.** A lit canopy or brush in a forest: stays a patch (2d4 × 10 min,
   no spread; recommended), or becomes the CRB Forest Fire (CR 6, 120 ft/round) after
   some delay nobody has sourced?
4. **Harm by conditions.** Should hold person, sleep and color spray count as harm
   (fight + hostile), or only damage (recommended for now)?
5. **Companions caught.** A regard loss of 10 (RimWorld "Harmed me" = "Insulted", by this
   codebase's mapping), or Skyrim's three hits before hostile?
6. **Grudges fade?** Provocation's grudge recovers with time (`provocation.recover`).
   Should a burn's hostility, or only talk mend it (recommended)?
7. **Assault as a crime**, for swords and spells together: the break-in ladder
   (suspected → wanted) when a watcher sees you harm a non-hostile person?
8. **List casters' first morning.** A cleric with nothing chosen: leave empty with a
   warning and prompt (recommended), or a default from the whole list? On what
   principle?
9. **The 15-ft cone**: keep `grid.cone`'s 11 squares, or adopt the "alternate" cone
   Advanced Templates attributes to a Paizo FAQ, which I could not find?
10. **Study time**: add the 1e preparation hour to the rest clock?

---

### Sources

- Aiming a Spell — https://www.aonprd.com/Rules.aspx?ID=228 ; CRB magic chapter —
  https://legacy.aonprd.com/coreRulebook/magic.html
- Burning Hands — https://www.aonprd.com/SpellDisplay.aspx?ItemName=Burning%20Hands
- Catching on Fire — https://aonprd.com/Rules.aspx?ID=331 ; Forest Fires —
  https://aonprd.com/Rules.aspx?ID=293 ; CRB environment —
  https://legacy.aonprd.com/coreRulebook/environment.html
- Smashing an Object — https://aonprd.com/Rules.aspx?ID=126
- Invisibility — https://www.aonprd.com/SpellDisplay.aspx?ItemName=Invisibility ; Charm
  Person — https://www.aonprd.com/SpellDisplay.aspx?ItemName=Charm%20Person
- Diplomacy — https://www.aonprd.com/Skills.aspx?ItemName=Diplomacy ;
  http://legacy.aonprd.com/corerulebook/skills/diplomacy.html
- CRB combat chapter — https://legacy.aonprd.com/coreRulebook/combat.html
- Paizo CRB FAQ — https://paizo.com/paizo/faq/v5748nruor1fm (no cone entry found)
- Advanced Templates PF1 — https://github.com/dmrickey/ckl-advanced-templates-pf1
- Walled Templates — https://github.com/caewok/fvtt-walled-templates
- Midi-QOL — https://github.com/tposney/midi-qol ; issue 446 —
  https://gitlab.com/tposney/midi-qol/-/issues/446
- Avrae — https://avrae.readthedocs.io/en/latest/cheatsheets/pc_combat.html
- Skyrim crime — https://en.uesp.net/wiki/Skyrim:Crime
- RimWorld social — https://rimworldwiki.com/wiki/Social
- DOS2 environmental effects — https://divinityoriginalsin2.wiki.fextralife.com/Environmental+Effects
- DOS2 surface complaints — https://steamcommunity.com/app/435150/discussions/0/2935742047976273017/
- Kingmaker preparation (community) — https://steamcommunity.com/app/640820/discussions/0/1608274347715439615
- BG3 preparation (secondary) — https://www.siliconera.com/how-to-prepare-spells-in-baldurs-gate-3/
- VS Code chat context — https://code.visualstudio.com/docs/chat/copilot-chat-context
