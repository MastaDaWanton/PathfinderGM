# Fix interfaces — the register for the 2026-09-28 fix pass

The Phase 0 critic pass over `docs/design-a-truth.md` … `docs/design-f-ui.md`, written
against `docs/fix-plan-2026-09-28.md` and `docs/fix-baseline-2026-09-28.md`. It has four
parts. §1 checks the designs' claims against the code and the sources. §2 is the interface
register: every Phase 1–3 task builds against it, and a change after G0 needs the owner's
sign-off. §3 amends the plan. §4 lists the owner's questions.

Method: code claims were read at `93ac2d4` (branch `fixes-2026-09-28`), with read-only
Python one-liners where a number was at stake. Sources were re-fetched where a design
decision rests on them (AoN Aiming a Spell, AoN Movement, the CRB magic chapter,
d20pfsrd Heal, Inform WI §12.9, the Fate Veteran's Guide). Nothing else was run, and no
design or plan file was edited.

---

## 1. Verification ledger

Verdicts: **CONFIRMED**; **WRONG** (the correction follows); **OVERCLAIM** (true in part,
stated too broadly); **UNVERIFIED** (not re-checked in this pass; the design's word stands).

### 1.1 The plan itself

| # | Claim | Verdict | Finding |
|---|---|---|---|
| P1 | S4 owns "the `Scene` class only (lines 142–1500)" | WRONG | `Scene` runs from 142 to **1556**. `Outcome` (1558), `_refuse` (10968) and `_rehydrate` (11917) lie outside it, and §2.6 needs all three. They are named explicitly in §3.1. |
| P2 | S1's hook goes in `narration.review()`, and `BeatContext` is built at `_groom`'s call sites | WRONG as a seam | `review()` is called only inside `GMAgent.polish` (agent.py 1491–1564). `polish` runs only when `rewrite=True`, and **before** `mentions.attribute` (agent.py 1227). A hook there never sees the attribution, and it misses every `rewrite=False` beat. `_groom`'s four callers (`plan_turn` 676, `npc_turn` 867, `narrate_turn` 1990, `narrate_outcome` 2222) hold the outcomes, but `_groom` does not receive them. The run site is moved in §2.1. This also settles A's open question 3. |
| P3 | S3's aftermath hook goes "after the `said`/hails block (≈2215)" | OVERCLAIM | The line is right, but the hails are not there. `_finish` runs `record_people` (2078), then `apply_introductions` (2103), then **`hailed_by` → `join_talk` (2112)**, then `settle_descriptions` (2125). Only after those come the kept `said` (2194), the transcript append (2204) and the speech-tags row (2206–2215). A needs a step *before* 2112, and F needs one *after* 2204. The answer is two stages (§2.3). |
| P4 | S4: "`seed` always set to a fresh random value at creation" | WRONG, and dangerous | C's trap is CONFIRMED. `Campaign.engine()` (campaign.py **182**) returns `Engine(self.scene, Dice(self.seed), …)`, and `Dice` is `random.Random(seed)`. Product code has 31 call sites (views 17, craft_views 8, watcher 3, campaign 2, downed 1). With a fixed seed, every call replays the same rolls. The plan's field is **withdrawn**; `Scene.story_seed` replaces it (§2.4). |
| P5 | The integration branch starts from local master `5cabed1` | OVERCLAIM | R0's harness is **uncommitted**: `fixtures/synthetic-world.json`, `tests/replays/`, `tests/test_harness_worlds.py`, the `conftest.py` fixture and the `narrator_audit.py` scripts. So is `93ac2d4`'s catalogue (it is on `fixes-2026-09-28`, not master). A worktree cut from `5cabed1` has no `worlds` fixture and no corpus. See Q1 and Q2. |
| P6 | "`play/views.py`: E only" in Phase 2 | OVERCLAIM | A needs one line in `_finish` (the `settle_descriptions` call gains `attribution=`), and `_finish` is none of E's functions. §3.2 splits views.py by method. |

### 1.2 Design A — the page tells the truth

| # | Claim | Verdict | Finding |
|---|---|---|---|
| A1 | `_mentions` keys a person on the last word (judgement.py 6490) | CONFIRMED | It takes the last word of three letters or more. Run over `opening.SITUATIONS`, the last word is wrong for **12 of 12** ("through", "you" ×2, "door", …). |
| A2 | `mentions._head` is wrong on 10 of 12 | CONFIRMED | It is right only for "woman" and "foreman". It returns "clearing", "ahead", "through", "minding", "two", "harness", "sharing", "round" and "you". |
| A3 | `_merge_declared` mints a `say` with `because: "the player's words commit the turn to it"` | CONFIRMED | agent.py 2074/2090. |
| A4 | `_PRODUCE` counts `hands` as a verb | CONFIRMED | judgement.py 3036–3039: `hand\|hands`. |
| A5 | `_name_stems` drops "man" | CONFIRMED | narration.py 1040 drops words of three letters or fewer (`len(w) <= 3`). |
| A6 | The attribution runs after `polish` | CONFIRMED | agent.py 1210 → 1227. |
| A7 | The brief labels the face "use it when they are first described" | CONFIRMED | prompts.py 1167. `faces.py` alone does not remove this label; the one line has to change too (§3.2). |
| A8 | `own_prose` reads `setup` beats only | CONFIRMED | |
| A9 | Inform WI §12.9: "If any of our checks fail, we should say why and stop the action." | CONFIRMED | Fetched. A's own caveat stands: the unreachable-report point comes from §12.2's ordering, not from §12.9's wording. |
| A10 | "20 quotations on the whole beat, 14 sentence by sentence" | UNVERIFIED | R0's corpus confirms the headline: `hails_tagged: []` beside two `to: you` records (case `drenn-hails`). |
| A11 | `Outcome.for_a_person` is new | CONFIRMED, one omission | The design does not mention that `IntentError.for_a_person` **already exists** (intents.py 612). The register reuses it, not a second field. |
| A12 | Re3, PDNC, RotoWire and FIREBALL figures | UNVERIFIED | A and F quote different PDNC-follow-up numbers (0.94–0.96 against 98.6 % explicit). They cite different papers (2307.03734 and 2406.11380), so there is no contradiction. |

### 1.3 Design B — space

| # | Claim | Verdict | Finding |
|---|---|---|---|
| B1 | In-town hops are free; only urban↔non-urban costs 60 min | CONFIRMED | engine.py 7208–7209. |
| B2 | **Roads priced as trackless** | CONFIRMED | 0 of 132 Aurvantis `play.travel` rows carry `road`. `legs_from` reads only `row.get("road")` (journey.py 313), so `pace(ground, "")` takes column 2. Measured: Vormoor→Dustgate is 38 h, and 27 h with the road column; Scrapden is 51 h → 37 h. |
| B3 | **The warrant tests only the destination** | OVERCLAIM | engine.py 7136–7142 also fires on `open_road`: a *biome* travel from urban to non-urban ground, unless the PC holds `knows.way-past-gate`. The real gap is a `place=` travel to non-urban ground (`want` empty), which skips both tests. That is exactly how B's ring places will be entered, so the fix is still needed. Its correct scope: **any travel whose destination setting is `outside`**. |
| B4 | **`biomes.detect` reads "ash-fields" as grassland; "its regex has no trailing `\b`"** | CONFIRMED cause, WRONG fix | `detect("ash-fields")` returns `['grassland']`. Vormoor's `from_world` gives `['urban','desert','grassland','mountain']`. The cause is `\bfield` matching as a prefix after the hyphen. A bare trailing `\b` breaks every plural ("canyons", "mountains", "fields"). And once plurals are allowed back (`s?\b`), "ash-fields" still matches. The correct matcher is compound-aware: `(?<![\w-])field(?:s)?\b`. Put it in `geography` only, because `biomes.detect`'s default feeds the forage and herb tables. |
| B5 | A stopped-short journey stands at `region_set(origin)[0]` | CONFIRMED | engine.py 6794–6795. |
| B6 | "the approach" is captioned with the gate's words | CONFIRMED | `floorplan.BY_SPOT['the-approach']` reads "the way in, and little to hide behind". |
| B7 | ROADS OUT gives names only (prompts.py 926) | CONFIRMED | 926–930. The fact-key loop follows at 931 (see R0-3). |
| B8 | `@` cannot come out of `_slug` | CONFIRMED | places.py 845 keeps `[a-z0-9 ]`. |
| B9 | The `scene.biome` ratchet exists | CONFIRMED | `tests/test_one_spatial_authority.py:81`. |
| B10 | PF1e local movement is 300 ft/min at speed 30, "for characters exploring an area" | CONFIRMED | AoN ID=50, fetched: "Characters exploring an area use local movement, measured in feet per minute." Table 7-8's highway / road-or-trail / trackless columns are confirmed too. |
| B11 | Fate removed weighted zone borders | CONFIRMED, one overclaim | The Veteran's Guide says "Zone borders have been replaced by the use of situation aspects". The name "Barrier Rating" and the stated reason ("a general mechanism already covered obstacles") are not on that page. |
| B12 | `02-state.js:216` prints location · scale · biome | CONFIRMED | |

### 1.4 Design C — starts

| # | Claim | Verdict | Finding |
|---|---|---|---|
| C1 | **Every `engine()` call builds a fresh `Dice(self.seed)`** | CONFIRMED | See P4. The design cites line 181; the line is 182. |
| C2 | The trusted provenance door is at engine.py 1877 | CONFIRMED | `validate(…, origin=…)`. |
| C3 | **`_op_check` has no heal branch; nothing stabilises by Heal** | CONFIRMED | No heal, stable or dying branch in 3565–3876. `_op_heal` restores hp only. `Actor.bleed_out` is the patient's own Con check. |
| C4 | PF1e first aid is Heal DC 15, a standard action | CONFIRMED | d20pfsrd Heal, fetched: "A stable character regains no hit points but stops losing them." |
| C5 | `POPULATION_BY_SCALE` (places.py 253) is far above the GameMastery Guide bands | CONFIRMED (code) / UNVERIFIED (GMG, not re-fetched) | |
| C6 | Aurvantis ships 64 per-town name pools | CONFIRMED | 80 pools, 64 of them with `home_id`. |
| C7 | The fallback is `cast[len(taken) % len(cast)]` | CONFIRMED | schemes.py 523. |

### 1.5 Design D — people

| # | Claim | Verdict | Finding |
|---|---|---|---|
| D1 | `interpret.target_of` drops bare pronouns | CONFIRMED | interpret.py 453. `inject_company` is at judgement.py 5820. |
| D2 | **The "not through carelessness" leak is the scheme's open grant, not the secret card** | CONFIRMED, and it corrects the playtest | `the-lost-thing` opens `at($market)`, `since(campaign) >= 0h`, with `grants_on_open` `say: "$giver looked away when asked how the $lost was lost"`. That reaches the brief through `Actor.noticed()` (sheet.py 2811 → prompts.py 1067). The secret card ("$giver did not lose it") was not the path. |
| D3 | The pull tells the giver to approach and speak (cards.py 686) | CONFIRMED | |
| D4 | `c.suggestions` is set before the aftermath | CONFIRMED | views.py 1951, before 2112. |
| D5 | `interpret.reading_of` exists | CONFIRMED | interpret.py 319. |
| D6 | GMG purchase limits; Colchester VCH; the CRPG vendor summaries | UNVERIFIED | Not re-fetched. D marks the CRPG claims as search summaries. |

### 1.6 Design E — magic

| # | Claim | Verdict | Finding |
|---|---|---|---|
| E1 | **`Actor.rest` wipes `prepared`** | CONFIRMED | sheet.py 3305: `self.prepared = {}`. The comment's premise is obsolete: `_op_cast` already spends the prepared copy (`casting.unprepare`, engine.py ~9115, "item 25"). |
| E2 | In 1e, uncast prepared spells survive the night | CONFIRMED | CRB magic chapter, fetched: "…the ones that he already had prepared from the previous day and has not yet used." |
| E3 | The cast params are `at, level, defensively, square, choose` | CONFIRMED | intents.py 406. |
| E4 | `_op_cast` takes targets only from `intent.target` or `params.at`, and never calls `_ensure_encounter` | CONFIRMED | engine.py 9136. There are five non-attack call sites (manoeuvre 4646, journey, travel, gathering, venture), not "four". Minor. |
| E5 | Only `_squares_for` uses `grid.cone`, `line` and `burst` | CONFIRMED | engine.py 9496–9539. |
| E6 | **`grid.burst((10,10),20)` gives 61 squares; the intersection rule gives 44 / 12 / 4** | CONFIRMED | 61 when run. 44/12/4 follows by arithmetic from the fetched rule: from an intersection, a square is in when its far corner is within the radius, counting `max + ⌊min/2⌋`. No published template count was found. |
| E7 | `grid.cone`'s cells are "reused unchanged" because its quarter-circle reading is already tested | OVERCLAIM | AoN (fetched) says a cone "starts from any corner of your square". `grid.cone` measures from the square's centre, which is the same defect E fixes for bursts. By the same far-corner count, a diagonal 15-ft cone from a corner is **6** squares; `grid.cone` gives **12** (run). E's question 9 frames this only as the unfound "alternate cone" FAQ, so it is widened in Q41. Bobby's case (c8 at (1,8), PC at (4,7), west) is inside both readings, so item 22's test is unaffected. |
| E8 | `note_heat` counts damage only from `attack`/`damage` ops | CONFIRMED | judgement.py 5733. |
| E9 | `_ensure_encounter` ends talk, rallies and calls the law | CONFIRMED | |
| E10 | `provocation.INSULT = 10`; `nudge_regard`, `step_of`, `influence_dc` and `_set_attitude(target, key, rounds, source)` exist | CONFIRMED | |
| E11 | `IntentError` has no `code` | CONFIRMED | It carries `check`, `index` and `for_a_person`. |
| E12 | Burning Hands, Catching on Fire, Smoke, Forest Fires, Invisibility, Charm Person; the 96 area-damage spells | UNVERIFIED | Not re-fetched or re-run; consistent with the CRB as known. One recommendation: the `save` effect should carry `saved: bool` only. The number already lives on the save `Roll` with its visibility, and a DC or total in an effect is a number outside the roll's visibility rule. The register adopts this. |

### 1.7 Design F — UI

| # | Claim | Verdict | Finding |
|---|---|---|---|
| F1 | **`_castable_summary` offers the whole book when nothing is prepared** | CONFIRMED (read; not replayed) | sheet.py 4197/4220: `if prepared and not left: continue`. `{}` is falsy, so every book spell is returned with `left: None`. |
| F2 | The aside is at table.html 1626; the Spells tab's Cast button posts `/api/cast` | CONFIRMED | 02-state.js ~348–356. |
| F3 | `speech.lift` wraps an untagged inner text in quotes | CONFIRMED | speech.py 245–247. |
| F4 | The clock starts at the opening hour × 60 | CONFIRMED | campaign.py 525. |
| F5 | — | NOTE | `Scene.said: dict` **already exists**: it is the narrator backstop's line rotation (engine.py ~280). No new field may be called `said`. |
| F6 | New scripts and packages survive packaging | CONFIRMED in part | `pathfindergm.spec` already has `collect_submodules("gm")` and `collect_submodules("play")`, which collect `gm.checks`, `gm.brief` and `play.aftermath`. Discovery at runtime must still be proven in the packaged build (G1, §3.5). |

### 1.8 R0's findings

| # | Claim | Verdict |
|---|---|---|
| R0-1 | biomes.py 329 gives `urban` only for `kind == "CITY"` | CONFIRMED |
| R0-2 | play/library.py 87 lists `of_kind("CITY")` only | CONFIRMED |
| R0-3 | The brief lifts a fixed list of fact keys (prompts.py 931–934), so Landscape, Daily Life, Customs and Conflict never arrive | CONFIRMED |
| R0-4 | All three pregens have empty spellbooks | CONFIRMED: `pc-thessaly.json` is a wizard with 0 spells |
| R0-5 | `--world` is parsed and ignored | CONFIRMED in part: parsed at 725 and passed at 735; the body was not re-read |

**Overclaims and errors, in one line each:** P1 (the Scene range), P2 (the review hook
site), P3 (hails before the hook), P4 (the fixed seed), P5 (the base lacks the harness),
P6 (views ownership), B3 (the warrant gap is narrower), B4 (the trailing-`\b` fix), B11
(the Barrier Rating wording), E4 (four paths is really five), E7 (the cone kept a defect
E fixed for bursts).

---

## 2. The interface register

### 2.0 Conventions for every entry below

- **A new persisted key is written only when it differs from its default**, and read with
  `.get(key, default)`. An old save then round-trips byte-identically, which is what the
  G1 proof tests.
- **A new outcome or effect key is emitted only when set.** `Outcome.as_dict` and
  `_rehydrate` follow the same rule.
- **A registry member is a module discovered by filename** (`pkgutil.iter_modules` over the
  package `__path__`). Names starting with `_` are helpers, never members. Members are
  sorted by `(ORDER, module name)`. No registry has a list to edit.
- Imports go inside functions in the large files. No member imports an unmerged lane.

### 2.1 Narrator checks — `gm/checks/` (S1)

**Where they run.** In `GMAgent._groom`, immediately after `self.attribution =
mentions_mod.attribute(…)` (agent.py 1227), and never inside `review()`:

```python
if ctx is not None:
    ctx = dataclasses.replace(ctx, text=text, attribution=self.attribution)
    text, rows = self._truth_pass(ctx)
```

`_groom` gains the keyword `ctx: BeatContext | None = None`. Each of its four callers
builds a context. `_truth_pass` calls `checks.run(ctx)` and hands the findings to
`self._repair_sentences(text, findings, ctx)`. S1 ships that as a stub returning the text
unchanged; Lane A fills it in.

```python
# gm/checks/__init__.py
@dataclass(frozen=True)
class BeatContext:
    door: str                         # "plan" | "turn" | "npc" | "outcome"  (_groom's four callers)
    text: str                         # the draft when the checks run (after polish and attribution)
    player_text: str
    engine: "Engine"                  # read-only by contract: here(), places(), talking_to()
    scene: "Scene"
    world: "World | None"
    location: object | None           # the settlement entity
    reading: Mapping | None           # agent.reading (the interpreter frame)
    outcomes: tuple["Outcome", ...]   # ALL of resolution.outcomes, refused and tell-less included
    tells: tuple[str, ...]            # what _groom already calls `facts`
    said: tuple[Mapping, ...]         # speech.lift records for this draft (a copy of agent.last_said)
    attribution: "Attribution | None"
    brief: str                        # the whole brief as sent
    brief_facts: Mapping[str, Mapping]  # keyed by brief-section module name (§2.2)
    pull: Mapping | None              # thread_to_pull's dict, as passed to _groom
    was_at: str                       # scene.at when plan_turn began (agent._was_at, set by S1)
    acting: str                       # the NPC ref on npc_turn, else ""
    turn: int
```

**Derived values are not fields.** `here` is `engine.here()`, `known` is `engine.places()`
and `in_fight` is `scene.in_encounter`. The settlement's scale word is
`places.scale_of(location)`. The scaffold 4-grams come from `gm.brief.scaffold()`. D's
sought result is `gm/checks/_sought.py` (D's helper module).

**Why `brief_facts` is a dict.** A's table names no consumer for its `list[str]`. B's two
checks read the Land and the roads the brief actually printed, and a dict keyed by section
lets a check read what the model was shown instead of deriving it a second time or parsing
strings, which would be law one's error again.

How the values reach the agent without cross-lane signatures: S3 sets `agent.brief_facts`
and `agent.attachments` before `narrate_turn`, the way `agent.buying` is set today, and S1
reads them with `getattr(self, …, default)`.

**The member contract:**

```python
ORDER: int
KINDS: frozenset[str]                 # every Finding.kind the module can emit
DOORS: frozenset[str]                 # a subset of {"plan", "turn", "npc", "outcome"}
def find(ctx: BeatContext) -> list[Finding]
def backstop(ctx: BeatContext, text: str, findings: list[Finding]) -> tuple[str, list[str]]  # optional
```

`narration.Finding` gains `sentences: tuple[str, ...] = ()` (S1). `checks.run(ctx)` drops a
finding whose non-empty `sentences` were all flagged already by a heavier finding.
`checks.registered() -> tuple[ModuleType, …]`.

**The shared helper, delivered in Phase 1.** `gm/checks/_people.py: head_of(name: str) ->
str` is S1's, pure, tested on the twelve companions and **wired into nothing**. From Phase 2
Lane A owns the module: it wires `head_of` into `_mentions`, `faceless`, `_name_stems` and
`mentions._head`, and adds `about(ctx, ref) -> list[str]` and `spans_in_context(text)`.
D and F import `head_of` from Phase 2 on. This answers F's open question 10.

### 2.2 Brief sections — `gm/brief/` (S2)

```python
@dataclass(frozen=True)
class BriefContext:
    world; scene; location
    here: "Place | None"; known: tuple["Place", ...]
    recent_events: list | None; recent: list[str] | None
    secret: bool; turn: int; names_for: object | None; absent: str; buying: str
    reading: Mapping | None; player_text: str
```

**The member contract:**

```python
ORDER: int
SLOT: str                           # "place" | "people"
SCAFFOLD: tuple[str, ...]           # the section's fixed words (A's brief_verbatim reads these)
def section(ctx: BriefContext) -> tuple[str, dict]   # (text including its own leading "\n"/indent, facts); ("", {}) = nothing
```

`scene_brief(…, reading=None, player_text="", report: dict | None = None)`. The `report`
dict is filled as `report["facts"][module] = facts`, the `prompts.pack` pattern. The
returned string does not change.

**The slots:**

- `"place"` replaces prompts.py 857–934: the HERE / PLACES / UNDERFOOT block, ROADS OUT
  and the fact-key loop.
- `"people"` sits after the WHO IS HERE loop and before `pc = scene.pc()` (≈1221).

**S2 moves three blocks.** B's request is granted: otherwise Phase-2 members would
duplicate lines that no Phase-2 lane may delete. Each move is ordered to reproduce today's
bytes exactly:

- `here.py` (place, ORDER 10);
- `roads_out.py` (place, ORDER 20);
- `place_facts.py` (place, ORDER 40; the fact-key loop, for R0-3).

`test_the_place_the_brief_states_comes_from_the_engine` is repointed at them.
`gm.brief.scaffold() -> frozenset[tuple[str, ...]]` returns the 4-grams of every member's
`SCAFFOLD`.

| Member | Slot / ORDER | Lane |
|---|---|---|
| `here.py`, `roads_out.py` (moved) | place 10, 20 | S2 → B |
| `land_around.py` | place 30 | B |
| `place_facts.py` (moved) | place 40 | S2 → C (key lexicon, `display_key`, `in_its_own_words`) |
| `faces.py` | people 20 | A |
| `sought.py`, `keepers_in_background.py`, `ties.py`, `pronouns.py` | people 30, 40, 50, 60 | D (`hook.py` is dropped) |
| `market_master.py` | people 45 | I2 |
| `burning.py` | place 50 | I3 |

**Callers.** S1 passes `reading` and `player_text` at agent.py 302, 737 and 813. S3 does
the same at views.py 1591 and 1891, and reads `report` into `agent.brief_facts`.

### 2.3 After-the-beat steps — `play/aftermath/` (S3)

```python
@dataclass(frozen=True)
class AfterBeat:
    stage: str                      # "people" | "beat"
    door: str                       # "turn" | "carry_on" | "opening"
    campaign: "Campaign"            # members reach the engine through campaign.engine()
    scene: "Scene"
    world: "World | None"
    text: str                       # the beat as it stands at this stage
    said: list[dict]                # "people": the LIVE agent.last_said; "beat": the records kept on the beat
    player_text: str                # "" for buttons and the opening
    attachments: tuple[dict, ...]
    reading: Mapping | None
    attribution: "Attribution | None"
    outcomes: tuple["Outcome", ...]
    people: Mapping[str, Mapping]   # ref -> {"name", "pronouns", "is_pc"}, snapshot at stage start
    talking_after: tuple[str, ...]  # engine.talking_to() refs at stage start
    beat_index: int | None          # None in "people" (the beat is not appended yet)
    turn: int
```

**The member contract:**

```python
STAGE: str
ORDER: int
DOORS: frozenset[str] = {"turn", "carry_on"}
def step(ctx: AfterBeat) -> list[dict]      # returns turn-log rows
```

`aftermath.run(stage, ctx) -> list[dict]` catches any exception as
`{"kind": "aftermath-error", "member", "error"}`. S3 appends the rows to `c.turn_log` only
when there are any.

**The call sites in `_finish`:**

- **`"people"`**: immediately before `for ref in judgement.hailed_by(…)` (≈2112), after
  `apply_introductions`. This meets A's requirement that `speaker_real` runs before
  `hailed_by`. This stage alone may set `who` (and add `"made": ref`) on a `said` record
  whose `who` is empty; nothing else in `said` may change.
- **`"beat"`**: after the `speech-tags` row (≈2215), before `c.history.append`. It needs
  `beat_index` and the kept `said` (F). `c.suggestions` is already set (D).

**The opening.** `aftermath.after_opening(campaign) -> list[dict]` runs both stages with
`door="opening"`. S3 writes it (inert); Lane C calls it at the end of `new_campaign` in
Phase 2. Members opt in through `DOORS`.

`clock_before` and `clock_after` from F's draft are dropped. No member uses them: the
client arms the clock itself (§2.10), and log entries take `t = scene.clock_minutes`.

| Member | Stage / ORDER | Lane |
|---|---|---|
| `speaker_real.py` | people 10 | A (if Q5 says yes) |
| `mentioned_elsewhere.py` | beat 20 | D |
| `pronouns_adopted.py`, `suggestion_pronouns.py` | beat 30, 40 | D |
| `conversation_log.py` | beat 50 | F |

### 2.4 Persisted fields (S4, Phase 1; each defaults tolerantly, per §2.0)

| Field | Type | Default / old save | Owner of writes |
|---|---|---|---|
| `Scene.story_seed` | `int` | Old save: `opening._seed_from(campaign.id)`, set in `load`. New: `seed if seed is not None else secrets.randbits(31)` | C |
| `Campaign.story_seed` | read-only property → `scene.story_seed` | — | — |
| `Campaign.seed` | **unchanged** (`None` = fresh entropy per `engine()`) | — | nobody |
| `Scene.start` | `dict` `{"id", "kind", "where", "slots": {name: ref}, "hand_off": {…}, "tells": [str]}` | `{}` (then `situation_for` takes the legacy path, byte-identical) | C |
| `Campaign.start_id` | read-only property → `scene.start.get("id", "")` | — (**not a stored mirror**: no parallel store) | — |
| `Scene.spoken_for` | `list[str]` (world entity ids) | `[]`; `load` fills it from the scheme slots on an old save | C |
| `Scene.acquainted` | `list[str]` (entity ids a background tie names) | `[]` | C (D reads it for "tied") |
| `Scene.conversation_log` | `list[dict]`, the Entry of §2.10 | `[]`; unknown entry keys kept | F |
| `Scene.conversation_seq` | `int` | `0` | F |
| `Scene.outside` | **dropped** (B §3.7; Q3) | — | — |
| `Actor.described_as` | `list[str]`, at most 2 sentences | `[]` (sheet.py `to_dict`/`from_dict`) | A |
| `Actor.loadout` | `dict[str, int]` | `{}` (sheet.py `to_dict`/`from_dict`) | E |
| population record `seen`, `heard_from`, `heard_at` | `bool`, `str`, `int` | `True`, `""`, absent | D (reads only; no save code) |
| `Card.approaches` | `list[{"turn": int, "approach": str}]` | `[]` | D (`cards.py`) |
| transcript `said[]` `made` | `str` ref | absent | A |
| player beat and turn-log `attachments` | `[{"kind": "spell", "id", "name", "aim"?}]` | absent | S3 / E |

### 2.5 The arrival door (S4)

```python
Scene.arrive(actor: Actor, *, zone: str = "near", at: tuple | None = None,
             place_id: str | None = None, source: str = "") -> Actor
```

- With `place_id` absent or equal to `scene.at`, it behaves exactly like today's `add`
  (square assigned when there is a grid and the actor is not the PC).
- Otherwise the actor is recorded at that place with no square.
- `Scene.move(ref, place_id)` assigns a square whenever the destination is the party's
  place and there is a grid (item 14's root). `Scene.add` stays as a thin alias of
  `arrive`.
- Both call `backgrounds.recognise(scene, actor) -> str`. That is a **new function** in
  Phase 1 (S4), which applies `bond.knows-you` (source `background:<id>`) when
  `actor.world_entity_id in scene.acquainted`. It is inert until C writes `acquainted`.
- A guard test fails when any non-PC actor at `scene.at` on a gridded scene has no
  position.

### 2.6 Refusals: one code, one payload

`IntentError` (rules/intents.py, S4 in Phase 1):

- It gains `code: str = ""` and `fix: dict | None = None`.
- `fixable_by` is a **property**, `"player" if code in PLAYER_FIXABLE else "plan"`. This
  unifies A's `fixable_by` and E's `code`: one stored field, one derived.
- The existing `for_a_person` is the player's sentence.

```python
PLAYER_FIXABLE = frozenset({
    "unprepared", "no_slots", "not_known", "not_on_list", "too_high", "ability_too_low",
    "not_your_turn", "no_aim", "out_of_range", "no_line_of_effect", "no_such_object",
    "no_such_weapon", "out_of_reach", "absent_ground"})
# Plan-fixable (the loop retries): "no_such_target", "wrong_aim", and every uncoded refusal.
```

The rule for adding to the set: a code is player-fixable when the refusing fact is the
character's own state or the player's own words, never the plan's choice of ref or param.

`Outcome` (S4) gains `code: str = ""`, `for_a_person: str = ""` and `fix: dict | None =
None`, emitted only when set. `Engine._refuse(intent, why, *, code="", for_a_person="",
fix=None)` changes only its signature in S4.

Codes are placed as follows:

| Lane | Where the codes go |
|---|---|
| E | `_check_cast` |
| A | the non-cast raises in `_check_legality` and `_reach_refusal` |
| B | its refused-ground outcome (`code="absent_ground"`) |

`fix` shapes: `{"kind": "prepare", "spell": id}` and `{"kind": "go", "place": name}`
(B's "go to the outskirts first").

`TurnPlan.refusal: dict | None = {"text", "code", "fix"}` belongs to A (agent.py). The
loop ends on the first refusal with `code in PLAYER_FIXABLE` on an op the player
declared. An op the player never declared is dropped, and the loop continues.

**On the wire** (pending Q4; this is the recommended shape): `/api/say` and `/api/cast`
answer **HTTP 422** with

```json
{"error": "<text>", "refusal": {"text": str, "code": str, "fix": {...} | null}}
```

No transcript beat is added, the clock does not move and no NPC acts. The player's line is
popped the way the 502 path pops it, and the client keeps the input and the chip (F).
Both routes render into this one shape: E's pre-model dry validation of an attachment,
and A's plan-loop stop. If Q4 rules that a refusal costs the turn, the fallback is a
transcript beat of kind `"refusal"` and HTTP 200.

### 2.7 Outcome and effect fields

| Effect or record | New keys (emitted only when set) | Producer |
|---|---|---|
| `travel` → effect `kind: "biome"` | `minutes: int`, `went_by_about: [{"name", "about"}]`, `setting` and `was_setting` (`"in"`/`"under"`/`"outside"`), `direction` (`"out"`/`"in"`/`"along"`), `stopped_short: bool`, `meant_for: str`, `met_refs: [ref]`, `grounded` (`"near"`/`"beyond"`/`"unknown"`), `road_to: to_id`. `went_by` stays names. | B |
| refused biome | outcome `status: "refused"`, `code: "absent_ground"`, `for_a_person`, `fix`; effect `{"kind": "refused-ground", "biome", "near": [..], "beyond": [..]}` | B |
| `journey` | `from_id`, `setting`, `direction`, `place` on every branch | B |
| `found` | `setting` | B |
| `cast` effect | `aim: {"kind": "ref"\|"self"\|"direction"\|"point"\|"object"\|"none", "value": str, "said": str}`; `area: {"shape", "length_ft", "origin": [x, y, z], "cells": int, "measured": bool}`; `targets` (**same name**, now equal to `caught`); `caught: [ref]`; `caught_objects: [{"kind": "prop"\|"feature", "name", "burns": bool}]`; `no_victim: bool` (**replaces A's `reached_nobody`**); `harmful: bool`; `fell_short: bool` | E |
| separate effects on `cast` | `{"kind": "save", "ref", "save", "saved": bool}` (no DC or total: §1.6 E12); `{"kind": "attitude", "ref", "from", "to", "why": "harmed"}`; `{"kind": "battle_joined", "op": "cast", "ref", "target", "params": {"spell", "aim"}}`; `{"kind": "manifest", …}` (existing shape) | E |
| `spawn.actors[]` | `pronouns: str`, `from_words: {"gender", "pronouns", "age", "minor", "people_id"}` | D |
| pull dict | `approach`, `yielded: bool`, `giver: {"ref", "name", "role"}`, `to_player: {"relationship", "tie"}`, `offer`, `motive`, `doing`, `withholds` (all words) | D |
| turn-log rows | `{"kind": "heard-of", "record", "spot", "from"}`, `{"kind": "suggestion-pronoun", "before", "after"}` (D); `{"kind": "vocal-miss"}` (F); `{"kind": "aftermath-error", …}` (S3). S3 also copies `approach` and `yielded` into the existing pull row when present. | as named |

The cast param: `aim: str` matching

```
areas.AIM_PATTERN = r"^(ref:[A-Za-z0-9_-]+|self|dir:(n|ne|e|se|s|sw|w|nw|up|down)|point:\d+,\d+(,\d+)?|object:[^\n]{1,60})$"
```

S3 may hold a copy for validation; E owns the canonical one. The legacy `at` is read as
`ref:<at>`, and `square` as `point:` when there is no `aim`.

### 2.8 `rules/geography.py` — pure functions (S5 writes all of them in Phase 1)

```python
@dataclass(frozen=True)
class Land:  settlement_id: str; near: tuple[str, ...]; beyond: tuple[str, ...]
             words: tuple[tuple[str, str], ...]; climate: str; water: str; coast: bool
             source: str                              # "exact" | "derived" | "unknown"
def land_around(world, settlement) -> Land
def grounded(land: Land, biome: str) -> tuple[str, str]   # ("near"|"beyond"|"absent"|"unknown", redirect words)

@dataclass(frozen=True)
class Road:  to_id: str; to_name: str; to_kind: str; how: str   # "road"|"river"|"sea"|"sea-after-road"
             time_words: str; crosses: tuple[str, ...]; crosses_words: str
             leaves_from: str; bearing: str; source: str
def roads_out(world, settlement, speed_ft: int = 30) -> tuple[Road, ...]   # wraps journey.legs_from + hours_for

@dataclass(frozen=True)
class Where: setting: str; label: str; detail: str   # setting "in"|"under"|"outside"|"road"
def where(world, scene, here) -> Where
def walk_words(minutes: int) -> str

def role_of(world, cast_row) -> str                  # Role/Occupation/Profession/Position/Title, else a non-generic row.role, else ""
def in_its_own_words(text: str, scale: str) -> str   # "the city('s)" -> the scale word; never "the city of X"; unchanged for "" or "city"
def display_key(key: str) -> str                     # "Urban Life" -> "Daily life"
```

- **Phase 1 behaviour.** `where()` must reproduce today's panel exactly: `label =
  "{location} · {scale}"` (or the name alone), `detail = scene.biome`, and `setting = "in"`
  on urban ground, else `"outside"`. The rest are unwired.
- **Fact-key reading.** It uses the lexicon *geography, terrain, landscape, biome,
  climate, region, environment, topography, land*, case-insensitive. The ground matcher is
  compound-aware (§1.3 B4).
- **G1's assertion is sharpened** per B §5: Vormoor has `near == ("farmland",)`, `beyond`
  begins with `"mountain"`, three road legs, two sea legs and no bearing. The synthetic
  mileage-free leg yields no invented road facts.
- **Phase 2 ownership is split by function** (§3.2).

### 2.9 Other new functions every lane may code against

| Signature | Lane / phase |
|---|---|
| `interpret.travel_choices(frame, scene, places, location) -> tuple[str, ...]`. Phase 1 returns today's tuple; `agent.turn_schema(places=…)` routes through it | S1 → B |
| `residency.day_part(clock: int) -> str`, wrapping `_PARTS[slot_of(clock)]` | S5 |
| `places.setting_of(place_id) -> "in" \| "under" \| "outside"`; `places.OUTSIDE_KINDS`; `fits_here(kind, location, parent=None)` | B |
| `areas.lay`, `caught`, `objects_caught`, `features_here`, `resolve`, `aim_from_words`, `legal_aims(scene, pc, spell)`, `burst_cells`, `shape_of` (E §4.2) | E |
| `casting.ensure_prepared(actor, *, kept=None, reason="rest") -> dict`; `empty_slots(actor) -> dict[int, int]`; `remember_loadout(actor)` | E |
| `attitude.harmed(engine, victim, by, source) -> dict \| None`; `HARMED = provocation.INSULT` | E |
| `judgement.declared_ops(…, attached=None)` and `inject_cast(…, attached=None)`: the **keyword only** in Phase 1 (S1), the bodies in Phase 2 (E) | S1 → E |
| `openings.validate(doc) -> list[str]`, `choose(world, pc, rng) -> (town, doc)`, `placeable(doc) -> str`, `offer(world, pc)`; `names.town_pool(world, location_id)`; `keepers.name_for(place, world, taken=frozenset(), *, salt=None)`; `begin_with(character, world_source, start_town=None, start_id=None)`; `firstaid.stabilise(engine, healer, patient) -> Outcome` | C |
| `hooks.relationship(scene, actor) -> "tied" \| "known" \| "stranger"` (tied = `world_entity_id in scene.acquainted` or a `bond.knows-you` whose source starts `background:`); `scene_state`, `approach`, `ingredients`, `render`; `person_words.from_words(phrase, world=None, location_id="")`; `population.note(scene, phrase, *, spot, heard_from, hint)` | D |
| `speech.vocalisations(text, said, people) -> list[dict]` | F |
| `judgement.own_words_only(raw, player_text, reading) -> list`; `settle_descriptions(scene, beat, player_text="", attribution=None)`; `GMAgent._repair_sentences(text, findings, ctx) -> tuple[str, list[str], list[Attempt]]` | A (the stub from S1) |

### 2.10 API

**`/api/state`.** All keys are added by S3 in Phase 1 from the fields and helpers above.
Phase-2 lanes change values, never shapes.

| Key | Shape |
|---|---|
| `scene.where_label`, `scene.where_detail`, `scene.setting` | `str`, from `geography.where` |
| `scene.conversation` | `{"people": [{"ref", "name", "present", "talking", "lines", "last"}], "recent": [Entry], "seq": int}`; empty is `{"people": [], "recent": [], "seq": 0}`. People are ordered talking, then present, then by `last` descending, at most 30; `recent` holds the last 80 entries |
| `scene.day_part` | `str` |
| `scene.grid.areas` | `[{"spell": id, "cells": [[x, y, z], …]}]`: the latest turn's casts; `[]` in Phase 1; E fills it |
| `spellcasting` (top level) | `{"kind": "prepared"\|"spontaneous"\|"", "nothing_prepared": bool, "empty_slots": {"<level>": int}}`. It **merges F's `spellcasting` and E's `pc.casting.empty_slots`**. `empty_slots` is `{}` until E |
| `start` (top level) | `{"id", "kind", "hand_off"}` from `scene.start`; `{}` when empty |
| transcript player beat | `attachments: [{"kind": "spell", "id", "name", "aim"?}]` |
| ~~`scene.clock_minutes_before`~~ | **dropped**: the client arms the clock on its own POST (F) |

Entry: `{"n": int, "t": int, "beat": int, "who": ref|"you", "name": str, "to": "you"|ref|"",
"kind": "line"|"vocal", "text": str, "among": [ref], "src":
"tag"|"player"|"tag-adjacent"|"named"|"pronoun"}`.

**`POST /api/say`:**

```json
{"text": str, "carry_on"?: bool, "attachments"?: [{"kind": "spell", "id": str, "aim"?: str}]}
```

- It answers 400, with a sentence, when there is more than one attachment, the kind is not
  `spell`, `spells.get(id)` fails, the spell is not in the PC's book, known or prepared
  list, `aim` does not match `AIM_PATTERN`, or an attachment is combined with
  `carry_on`, `/gm` or `/cheat`.
- Empty `text` is legal with an attachment; the shown line is then `"I cast {name}."`.
  `player_input.check` runs only on non-empty text.
- Phase 1 stores the attachments and does not act on them (E acts in Phase 2).
- A refusal is the 422 shape of §2.6.

**`POST /api/cast`** (E): takes `aim` alongside `at`, with the same validation and the same
refusal shape.

**`GET /api/conversation?with=<ref|all>&before=<n>&limit=<≤200>`** (S3) returns
`{"entries": [Entry], "more": bool}`, oldest first. An unknown ref returns an empty list.

**Trade** (I2, Phase 3):

- `POST /api/trade` takes `{"want", "line"?}` and adds `line`, `lines: [{"id", "label",
  "seller"}]` and `seller: {"ref", "name"}` to the response.
- The turn response's `trade` becomes `{"open", "want", "line"}`.
- `/api/trade/do` accepts `line`.

### 2.11 Frontend mount points (S6) and the lanes' hooks

Mount points: `<aside id="panels">`, `#panelbar` with `button.panelbtn[data-panel]`, and
`section.panel#panel-{sheet,scene,conversation,map,rolls}`. Each panel has `.panelhead >
button.paneltoggle[aria-expanded] + button.panelclose` and `.panelbody#panel-<id>-body`.
Also: `#convo` (`#convo-people`, `#convo-log`, `#convo-latest`) above `#talk`, `#edgetabs`,
`#clockpop` inside `main`, `#clocksay`, `#spellbtn`, `#spellpop[popover]`, `#attachments`
before `#input`, `#saystatus`, the pre-paint `body.drawer` script, and `07`–`10` loaded via
`{% asset %}` (`08`–`10` as stubs).

S6 edits in `02-state.js`:

- `render()` keeps `prev` and calls `runRenderHooks(s, prev)` before `if (hold) return`;
- `post()` dispatches `table:posted {url, clockBefore}`;
- the beat renderer draws `b.attachments`;
- the sheet line prints `where_label · where_detail` when present, and today's text
  otherwise.

In `01-core.js`, S6 replaces `showSheet` and the drawer branches with `Panels` calls
(edited, not shadowed). `07-panels.js` exports `onRender(fn)` and `Panels = {open, close,
collapse, expand, forward, mode}`.

---

## 3. Plan amendments

### 3.1 Phase 1 scope changes

| Task | Adds to the plan's scope | Drops |
|---|---|---|
| S1 | `_groom(ctx=)` and `_truth_pass` (run site §2.1); `BeatContext` at the four `_groom` callers; `agent._was_at`; the `_repair_sentences` stub; `scene_brief(reading=, player_text=, report=)` at agent.py 302, 737 and 813; `turn_schema` through `interpret.travel_choices` (the new function, in interpret.py); `attached=` passed to `declared_ops`/`inject_cast` **and** that keyword added to both signatures in judgement.py (params only); `narration.Finding.sentences`; `gm/checks/_people.head_of` (unwired) | the hook inside `review()` |
| S2 | move `here.py`, `roads_out.py` and `place_facts.py` out of `scene_brief` (byte-identical); the `"people"` slot; `report` facts; `gm.brief.scaffold()` | — |
| S3 | two aftermath stages and `after_opening`; the full `/api/state` key set of §2.10; `GET /api/conversation`; the `attachments` validation and storage; `agent.brief_facts` and `agent.attachments`; `scene_brief` kwargs at views.py 1591 and 1891; `approach`/`yielded` copied into the pull row | `scene.clock_minutes_before` |
| S4 | `Scene` 142–**1556**; `Scene.arrive` and `move`; the §2.4 Scene fields and their save/load; `rules/sheet.py`: the `Actor` dataclass fields plus `to_dict`/`from_dict` (for `described_as` and `loadout`); `rules/intents.py`: `IntentError.code`/`fix`/`fixable_by` and `PLAYER_FIXABLE`; `rules/engine.py`: `Outcome` fields, `_rehydrate`, the `_refuse` signature; `backgrounds.recognise` (new function) | `Scene.outside`, the fixed `Campaign.seed`, the stored `start_id` |
| S5 | all of §2.8 including C's three functions; `residency.day_part`; `tools/narrator_audit.py: audit()` honours `--world` (R0-5); `docs/from-world-bible.md`: **every** export ask from the six designs, written once so no Phase-2 lane edits that doc | — |
| S6 | `01-core.js` (`showSheet` and the drawer branches) and the four `02-state.js` hooks of §2.11, including B's `where_label` line. That answers B's question 9: S6 in Phase 1, F in Phase 2, by function | — |

### 3.2 Phase 2 ownership, by method (replaces the plan's table)

| File | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| `rules/engine.py` | `_check_legality` (`code=` on the non-cast raises only), `_reach_refusal` | `_op_travel`, `_op_found`, `_op_venture`, `_op_journey`, `places`, `_terrain_hint`, `_march` | `_op_check` (the first-aid branch only) | `_op_spawn` | `_op_cast`, `_check_cast`, `_op_rest`, `_squares_for`, `_ignite` (new), and in `_op_attack` the one `attitude.harmed(...)` call (if Q37 says yes) | — |
| `gm/judgement.py` | `hailed_by`, `_mentions`, `settle_descriptions`, `false_possession`, `own_words_only` (new) | — | — | `inject_company` | `inject_cast`, `declared_ops`, `note_heat` | — |
| `gm/agent.py`, `gm/narration.py`, `gm/mentions.py`, `gm/checks/_people.py` | all | — | — | — | — | — |
| `gm/prompts.py` | line 1167 only (the "first described" label) | — | — | — | — | — |
| `gm/interpret.py` | — | `ops_for`, `travel_choices`, `_WHAT_EACH_IS` | — | — | — | — |
| `gm/speech.py` | — | — | — | — | — | `vocalisations` (new) |
| `play/views.py` | `_finish`: the `settle_descriptions` call line only | — | — | — | `say`, `cast_act`, `prepare_spells`, and in `_state` the values of `spellcasting.empty_slots` and `scene.grid.areas` | — |
| `play/campaign.py` (not save/load) | — | — | `new_campaign`, `begin_with`, `_bind_background`, `open_the_story`, `opening_text` | — | — | — |
| `play/opening.py`, `opening_prose.py`, `play/library.py` | — | — | all | — | — | — |
| `rules/geography.py` | — | `land_around`, `grounded`, `roads_out`, `where`, `walk_words` | `role_of`, `in_its_own_words`, `display_key` | — | — | — |
| `rules/places.py`, `floorplan.py`, `journey.py` (`legs_from`), `biomes.py` (`from_world`; `detect` additive only), `ontheway.py`, `outskirts.py` (new) | — | all | — | — | — | — |
| `rules/schemes.py`, `backgrounds.py`, `keepers.py`, `names.py` (`town_pool`), `openings.py`, `firstaid.py` (new), `content/openings/` | — | — | all | — | — | — |
| `rules/cards.py`, `population.py`, `hooks.py`, `person_words.py`, `content/schemes/`, `content/hooks/` | — | — | — | all | — | — |
| `rules/intents.py` (cast schema), `attitude.py`, `casting.py`, `areas.py` (new); `rules/sheet.py`: `Actor.rest` (the 3305 line and its comment), `_castable_summary`; a new fixture `fixtures/pc-caster.json` (a wizard with a book; `pc-thessaly.json` untouched) | — | — | — | — | all | — |
| `rules/grid.py` | read-only for every lane | | | | | |
| Frontend | — | — | — | — | — | CSS for the three components in `table.html`; `08`–`10`; `02-state.js` `.castbtn` handler; `04-combat-and-turns.js` `takeTurn` and `#sayform.onsubmit` |
| `tools/narrator_audit.py` | — | — | the `starts` mode (fresh campaigns per seed) | — | — | — |

**Overlap check.** No method or line appears under two lanes. E's `_squares_for` and
`_op_cast` are separate from B's travel methods and D's `_op_spawn`. C's `_op_check`
branch is untouched by anyone else. `_check_legality` hands the cast branch to
`_check_cast` (engine.py 2342), so A's raises and E's are in different methods. In
`sheet.py`, S4 (Phase 1: the dataclass and serialisers) and E (Phase 2: `rest` and
`_castable_summary`) are separated by phase and by function. In `views.py`, A owns one line
of `_finish` and E owns four other functions. In `02-state.js`, S6 (Phase 1) and F
(Phase 2, the `.castbtn` handler) are separated by phase and by function. Every new file
has one lane.

### 3.3 Phase 3 amendments

- **I1** keeps `openings.py` placement for `where: road`, `content/openings/road-*.json`
  and `new_campaign → casting.ensure_prepared(reason="start")`. It **takes** the
  `opens_scheme` wiring, because I1 owns `openings.py` and `campaign.py` and I4 would
  otherwise collide with it.
- **I2** adds `rules/audience.py`, `content/rules/stall-lines.json`,
  `gm/brief/market_master.py` and `goods.stocked_at` (goods.py has no other owner), as
  well as `_trade_offer`, `_merchant_here`, `_stall_of`, the trade endpoints,
  `places.STAFFED`, `market.py`, `keepers.py` and `gm/checks/master_unprompted.py`.
- **I3** drops "the rest-method prep call" (E does it in `_op_rest`). It adds
  `prompts._declared_op` (the `aim` enum), `interpret.ops_for`/`ACT_SLOTS` (cast
  object→aim), `hazards.json` `burning-brush` and `smoke`, `gm/brief/burning.py`,
  manifestation expiry in minutes outside a fight, `10-spells.js` sending `aim`, and the
  area overlay in `03-offers-and-map.js` (`scene.grid.areas`).
- **I4** keeps `cards.thread_to_pull`'s "known to you" row, `schemes._events_from` (a
  `talk` event from `say` outcomes), `schemes.validate` for `hook` fields and the
  lost-thing grant step's `event:talk($giver)`.

### 3.4 Every new defect assigned

| Defect | Found by | Owner | Note |
|---|---|---|---|
| Roads priced as trackless | B | **B, Phase 2** (`journey.legs_from`) | A behaviour change for live campaigns: Q12 |
| Warrant bypass through the way in | B | **B, Phase 2** (`_op_travel`) | Scope corrected in §1.3 B3: any travel to `outside` ground |
| "ash-fields" read as grassland | B | **B, Phase 2** (`geography`'s matcher) | Compound-aware, not a trailing `\b` (§1.3 B4) |
| A stopped-short journey lands beside the town it left | B | **B, Phase 2** (`_op_journey`) | Stands at `@along-the-road-to-{to_id}` |
| `biomes.py:329` gives `urban` only to `CITY` | R0 | **B, Phase 2** (`biomes.from_world`) | Use the settled-kind set, as the rest of the code does |
| `play/library.py:87` lists `CITY` only | R0 | **C, Phase 2** | One line, the same kind set |
| Brief fact keys miss Landscape, Daily Life, Customs and Conflict | R0 | **S2** moves the loop into `place_facts.py` (byte-identical); **C, Phase 2** adds the key lexicon, `display_key` and `in_its_own_words` | |
| Keeper given names ignore the people | R0 | **C, Phase 2** (`keepers.name_stock`) | Given names from the people's own pool, as families from the town pool |
| `narrator_audit --world` ignored | R0 | **S5, Phase 1** (`audit()` only) | G2's three-world queue needs it |
| Pregens have empty spellbooks | R0 | **E, Phase 2** | A new `fixtures/pc-caster.json` for `cast-area`; existing pregens untouched |
| Burst geometry 61 vs 44 | E | **E, Phase 2** (`areas.burst_cells`, `_squares_for`) | Fog cloud and friends shrink as well: say so in the tests |
| Cone geometry 12 vs 6 (a diagonal 15-ft cone) | this pass | **E, Phase 2**, pending Q41 | |
| Rest wipes prepared spells | E | **E, Phase 2** (`Actor.rest` line 3305) | Delete the wipe and fix the comment; `kept` becomes unnecessary |
| `_castable_summary` offers the whole book | F | **E, Phase 2** | Test: a prepared caster with nothing prepared offers only cantrips |
| No Heal DC 15 stabilise (`_op_check`) | C | **C, Phase 2** (`rules/firstaid.py` plus the `_op_check` branch) | Confirm at G0 (Q8). The bonesetter and ferryman starts depend on it |
| The scheme's open-grant leak | D | **D, Phase 2** (`the-lost-thing.json`) | The grant moves to a step with `present($giver)`; the `event:talk` criterion is I4's |
| `IntentError.for_a_person` already exists | this pass | register | Reused, not duplicated |
| **The pregens have no background** (`fixtures/pc-kesst.json`, `pc-borin.json`, `pc-thessaly.json`: `background: ""`), so no background-shaped start can be exercised. Owner, 2026-09-28: "give them backgrounds or its not an accurate test of the new origin/start" | owner | **C, Phase 2** (the three fixtures; C owns `backgrounds.py` and the starts) | Proposed: Kesst (rogue) thief-taker, Borin (fighter) caravan hand (exercises I1's road start), Thessaly (wizard) bonesetter (the owner's own example start). Tests that pin the pregens' current sheets move with it |
| **The opening names the architecture instead of describing the room.** "among Wooden Khy'vyr-style homes and Kelvaxian desert architecture" tells the player nothing they can picture. Owner, 2026-09-28: "we need descriptions of what the room looks like" | owner | **C, Phase 2** (`opening.compose`, `opening_prose.material`/`problems`) | The first paragraph describes the spot the party actually stands in: the start place's own shape (`floorplan.describe`, the brief's UNDERFOOT line), what it is made of, its light, sound and smell, with the world's architecture fact turned into what you see there rather than quoted as a label. A check in `problems()`: a first paragraph with no concrete physical detail of the immediate spot is rewritten; the template floor carries the spot's description instead of the raw fact list |
| **The template splices facts ungrammatically**: "Zhilvarnia keeps to Council of Elders advises on land use and trade", "The day here is Daily markets, communal gatherings and clan rituals" | owner (same screenshot) | **C, Phase 2** (`opening.the_world_here`, `who_you_are`) | Facts are sentences or lists; the template must not splice either into a fixed frame. Test on all three worlds' first settlements |
| `AfterBeat.player_text` carries the Spells-tab and combat-panel labels as if typed (§2.3 wants `""` for buttons); S3 could not reach the callers | S3 (Phase 1) | **E, Phase 2** (`views.cast_act` and the combat panel's `_finish` call pass `player_text=""`) | A's `own_words_only` and D's sought reading must not treat "I cast Burning Hands" from a button as the player's words |
| **`prove_build`'s feat check is stale**: "no longsword attack row on the sheet: ['unarmed strike']". The prover creates a fighter with Weapon Focus (longsword) and no weapon; since "The kit and the purse" (afd4ec2) a class no longer hands out a kit, so the character owns no longsword. Reproduced identically on master 5cabed1 through the same view: pre-existing, not Phase 1 | lead, G1 | **lead, before G4** (`tools/prove_build.py`: create with `begin: false`, buy the longsword through `/api/outfit/<id>/buy`, then begin) | Side finding: buying on the outfit page after a campaign has begun changes the roster entry but not the running campaign's sheet (`weapons: [unarmed, longsword]` on the roster, sheet still `unarmed strike`). Ask the owner whether the outfit page should be reachable mid-campaign at all |
| `scope.in_the_room` counts a word shared by a name and a true name, so a keeper sharing the giver's family name wins ties; and it reads "the girl that the watchman described" as the watchman while he is present | Lane D (Phase 2) | **I4, Phase 3** (`rules/scope.py`; D worked around it in `hooks.resolve_target` only) | Blocks the market-seek live script's "find the girl" step reading right |
| How a party comes to have a mount (owned, bought at the stables, hired) — designed in `docs/design-b-space.md` §10, not built; no published hire price for a horse was found | Lane B (Phase 2) | **I2, Phase 3** (the stables join the shops) | Owner question at P3: a hire price for a horse |
| `travel` has no `pace` param, so riding speeds journeys only, not short trips out of town | Lane B (Phase 2) | **I3, Phase 3** (`rules/intents.py` travel schema, beside I3's other intents edits) | |
| Which conditions count as harm: Lane E's `HARMFUL_STATES` excludes charm and magical sleep (`asleep`) | Lane E (Phase 2) | **I3, Phase 3** | **Owner, 2026-09-28: "yes if the people who saw are not friendly."** Charm and magical sleep count as harm when the source is perceived AND the reaction is taken only by witnesses (the victim included) whose attitude toward the caster is below friendly; a friendly or helpful onlooker does not turn on the caster for it. Add the two families to `HARMFUL_STATES` with that witness gate in `attitude.harmed` |
| Animal and tack prices for I2's stables | owner | **I2, Phase 3** | **Owner's source (2026-09-28): d20pfsrd "Animals & Animal Gear".** Light horse 75 gp (combat-trained 110), heavy horse 200 (300), pony 30 (45), camel 150, riding dog 150, donkey or mule 8; saddles riding 10 / military 20 / pack 5 (exotic 30 / 60 / 15); bit and bridle 2 gp; saddlebags 4 gp; harness 2 gp; stabling 5 sp a day; feed 5 cp a day; barding ×22 cost (Medium). The page gives NO hire price: ask the owner for a rule at P3 (e.g. a daily rate derived from the purchase price, or buy-and-sell-back) |
| Only the player's harmful cast defers through the battle gate; an NPC's harmful cast opens the fight and resolves (the engine cannot roll a deferred NPC spell later) | Lane E (Phase 2) | recorded | Consistent with an NPC that chose to attack |
| Live verification of starts must run with a prose model configured: the Phase-1 verification server (scratch data, no model) showed only the template floor | lead | **G2 live queue** | Seed the scratch data dir with the owner's model settings (copied, never the saves) |
| The brief's IN CONVERSATION WITH block sits inside the WHO IS HERE loop, so it prints once per visible actor | S2 (Phase 1) | **A, Phase 2** (`gm/prompts.py`, that block only, beside its line-1167 grant) | Left byte-identical in Phase 1 on purpose; a test records the per-actor repeat before the fix |
| Scene fields must never be named `said` | this pass | register | `Scene.said` is the backstop rotation |

**Out of scope, recorded:** `biomes.detect`'s default matching (its herb and forage
callers are unmeasured); population bands against the GameMastery Guide (Q23); the GMG
purchase limit (Q30); the start picker UI in `home_views` (Q20).

### 3.5 Gates, restated

**G1:**

- With the check and aftermath registries **empty**, `_groom` output, `review()` findings
  and `_finish`'s turn-log rows are byte-identical across the Bobby corpus and the audit
  recordings.
- With **only S2's three moved members registered**, `scene_brief` is byte-identical.
- The existing `/api/state` keys are byte-identical, and the new keys are present at
  their defaults.
- Old saves round-trip byte-identically. New keys are omitted at default.
- **The packaged build discovers the same members as the source tree**, one test per
  registry, run through `prove_shell --packaged`.

**G2:** the "unprepared cast" replay passes on a 422 carrying `refusal.code ==
"unprepared"` and zero plan retries.

### 3.6 Merge orders

- **Phase 1: S4 → S5 → S1 → S2 → S3 → S6.** S3 is cut, or rebased, **after S4 and S5
  merge**: its `/api/state` reads their fields and `geography.where`. S1, S2, S6 and S5 cut
  from the base.
- **Phase 2: A → B → E → C → D → F** (C moves before D). D's `hooks.relationship` and its
  `greets` test read `scene.acquainted` and the `background:` knows-you effect, both of
  which C writes. With C first, D's merge proves its own skipped test. Nothing of C's
  reads D.
- **Phase 3: I2 → I3 → I1 → I4** (unchanged).
- **Base:** local master `5cabed1` **plus** a commit of `93ac2d4`'s docs and R0's harness
  (Q1, Q2). Tag that commit as the Phase-1 base.

---

## 4. Owner questions

**G0 ANSWERED 2026-09-28 by the owner: "accept all recommendations, keep bobby data out,
start phase 1".** Q1 (b): the base is 5cabed1 plus the docs and R0's harness. Q2 (b): the
Bobby corpus stays out of the repository (`.gitignore`); `replays.available()` makes its
tests skip, and each worktree copies it from the main checkout. Q3 yes, Q4 (a), Q5 yes to
both with the stated limits, Q6 cap 300 and no backfill, Q7 agree, Q8 Lane C in Phase 2.
Q9–49 are asked when their lane or integration task starts.

**PHASE-2 ANSWERS 2026-09-28 by the owner.** Every P2 question not named below takes the
register's recommendation (including the pregen backgrounds: Kesst thief-taker, Borin caravan
hand, Thessaly bonesetter). The owner's own rulings, which OVERRIDE the recommendations:

- **Q20 (Lane C) — build the path, label it.** "make the button/path for it and then label it
  not built yet." Lane C adds the start/town picker's entry point on the new-campaign screen
  and the backend path it will call (`begin_with(..., start_town=, start_id=)` already in
  §2.9), with the control visibly labelled as not built yet; "Surprise me" stays the working
  default. `home_views`/`home.html` join Lane C's files for this one control.
- **Q11 (Lane B) — a crossroads is not in a town.** "crossroads are place[s] not in a town
  where all the roads leave to different places." A crossroads is an OUTSIDE place on the road
  network, out past the settlement, where the roads toward different destinations part; it is
  not one of the settlement's own places and not a ring member beside the fields. Journeys
  along those roads pass through it. Generated where two or more of a settlement's roads lead
  to different destinations; one per such fork.
- **Q13 (Lane B) — journeys take days, and a horse changes it.** "travel between settlement[s]
  should take days without a horse, half the time with a horse and a third of the full time if
  you gallop on the horse the whole way [horse fatigue should kick in if the journey is too
  far]." Journey time: on foot = the world's distance at walking pace in days; riding = half;
  galloping the whole way = a third, with the mount's fatigue applied by rule when the journey
  is too long for that pace (Lane B researches PF1e mount/forced-march/hustle rules for the
  fatigue and its thresholds, and how a party comes to have a mount — owned, bought at the
  stables, hired). Ground beyond the near land follows the same pace rule rather than a flat
  4-hour band.
- **Q34 (Lane E) — unpleasant conditions count, but only when you are seen.** "conditions that
  cause harm or unpleasantness should count but only if you are seen casting or causing the
  condition … if i shoot a blowdart from concealment or [pass] a stealth check then nobody saw
  that I did it so no one dislikes me for it or tries to fight me. The same would apply to
  conditions like nauseated or sickened." Harm = damage OR a harmful/unpleasant condition
  (nauseated, sickened, and the like). Attitude loss, witnesses' reactions and the battle gate
  apply ONLY when the source is perceived: an attacker in concealment/hidden, or who beats the
  observers' Perception with Stealth (PF1e sniping rules for the attack from hiding — Lane E
  sources the exact penalty), is not identified; the victim knows they were hurt, not by whom.
  This applies to swords and spells alike (Q37 stands).
- **Q42 (Lane F) — a conversation tray, out of the panel.** "Yes but it should be openable and
  closeable while the buttons to ignore or leave conversation should be there as well. It
  should be removed from the panel." The conversation becomes its own openable/closeable tray
  (the map tray's idiom), carrying the log AND the Ignore / Take your leave controls; the
  Conversation panel is removed from the sidebar panel set (S6's `#panel-conversation` and its
  bar button go; `#talk`'s controls move into the tray). Phone: the badged edge tab opens it.

- **The outfit page, and where gear is bought (answered 2026-09-28).** "outfit page should
  not be reachable but there should be stores that carry all of those items in town split
  between a general goods store and armorer and a weaponsmith. add an alchemist and have the
  rest split up between random market stalls."
  - **Lane C, Phase 2:** the outfit page is for character creation only. Once a character's
    campaign has begun, nothing links to it and `/api/outfit/<id>/buy` refuses with the
    reason named (409), so the roster and the running sheet cannot drift apart again.
    `outfit_views.py` and the outfit link join Lane C's files.
  - **I2, Phase 3 (widened):** every item the outfit catalogue sells is buyable in play, from
    a real counter: a **general goods store**, an **armorer**, a **weaponsmith**, an
    **alchemist**, and the rest spread across **market stalls** chosen by lot (seeded, so a
    town keeps its stalls). Each is a place with a keeper through the existing staffing and
    trade machinery (`places.STAFFED`, `goods`, `market`, the trade panel). Which of the four
    shops a village has versus a town or city is I2's design, put to the owner at P3.

49 questions, deduplicated. **G0** means it must be answered before Phase 1 starts. **P2**
means before the named lane starts. **P3** means before the integration task starts.
Resolved by this register, so not asked: A's attribution order (§2.1), B's `02-state.js`
owner (§3.1), F's helper name (§2.1), who owns first aid (a confirmation, Q8),
`clock_minutes_before` (dropped), `hook.py` → `ties.py`.

### Seams, persistence and base (G0)

| # | Question | Options | Designs recommend | Blocks | When |
|---|---|---|---|---|---|
| 1 | The base branch | (a) `5cabed1` bare; (b) `5cabed1` plus a commit of `93ac2d4` and R0's harness | (b): the plan's (a) has no `worlds` fixture | the Phase-1 base tag | **G0** |
| 2 | Commit the Bobby replay corpus? The repo is public, and it holds extracts of a player's save | (a) commit as is; (b) keep it out, and replay tests skip when absent (copy it into each worktree); (c) commit a scrubbed copy | (b) or (c) | G1 and G2 replay proofs | **G0** |
| 3 | Drop `Scene.outside` and derive the setting from the place id | yes / no | yes (B; the repo's own `scene.biome` ratchet) | S4 | **G0** |
| 4 | Does a player-fixable refusal cost the turn? | (a) no: 422, no clock, no NPC turn; (b) yes: a `refusal` beat | (a) (A; an IF parser error takes no turn) | S3 API, A, E | **G0** |
| 5 | Can the page make a person exist? (A §9.1 + D §9.4, one question) | (a) a speaker addressing the player gets a body through the arrival door; (b) a person an NPC places elsewhere becomes a population record, familiar and not seen; each yes or no | yes to both: (a) only when matched to this beat's record, (b) only at a real place in this settlement | the aftermath `"people"` stage; A `speaker_real`; D `mentioned_elsewhere` | **G0** |
| 6 | The conversation log's cap, and backfill from the `said` on old beats | cap 300 / other; backfill yes / no | 300; no backfill in v1 | S4's defaults | **G0** |
| 7 | The phone never auto-opens the drawer for a conversation (a badged edge tab instead); panels default to open | agree / other | agree (F) | S6 `Panels.forward` | **G0** |
| 8 | First aid (Heal DC 15 stabilises) built by Lane C as `rules/firstaid.py` plus the `_op_check` branch | C, Phase 2 / a Phase-1 task / not built | C, Phase 2 | C's two flagship starts | **G0** (confirm) |

### Truth (Lane A)

| # | Question | Options | Recommend | Blocks | When |
|---|---|---|---|---|---|
| 9 | Face drift without contradiction: flag *new* body details on a described person? | brief only / also flag | brief only (the false-positive risk) | `face_kept.py` | P2 (A) |

### Space (Lane B)

| # | Question | Options | Recommend | Blocks | When |
|---|---|---|---|---|---|
| 10 | Minute bands: village 2, town 4, city 8 per hop; half a mile per ring hop | accept / tune | accept | B's travel minutes | P2 (B) |
| 11 | A generated crossroads wherever two or more roads leave | yes / no | yes | the ring | P2 (B) |
| 12 | Read `by: "road"` as the road column (live journeys get about 30 % shorter) | yes / no | yes | `legs_from` | P2 (B) |
| 13 | `beyond` ground reachable at a 4-hour band, or only by a journey? | 4 h / journey | 4 h | `grounded` | P2 (B) |
| 14 | Bobby stands in an absent forest | load as "near Vormoor · forest" / heal onto the fields | load as is | the old-save label | P2 (B) |
| 15 | Walking back along a stopped road costs the hours walked | yes / no | yes | `_march` | P2 (B) |
| 16 | Sea legs from a non-port stilt village | leave from the shore / add a landing | the shore | the ring | P2 (B) |

### Starts and variety (Lane C)

| # | Question | Options | Recommend | Blocks | When |
|---|---|---|---|---|---|
| 17 | Losable starts: an untreated patient bleeds out by the engine's rule | yes / no | yes | `called-to-the-cage` | P2 (C) |
| 18 | Does a place's keeper differ between campaigns in one world? (C §9.4; D keeps them stable within one) | differ / same | differ (salted by `story_seed`) | `keepers.name_for` | P2 (C) |
| 19 | Weighting toward one's own people (×3) and exile away from it (×⅓) | yes / no | yes | `openings.choose` | P2 (C) |
| 20 | A start/town picker ("Surprise me" by default) | Phase 2 / later | later, out of scope (`home_views` has no owner) | — | P2 (C) |
| 21 | The quiet floor: keep three quiet starts at half weight | keep / retire at 12+ documents | keep | the start set | P2 (C) |
| 22 | When does "The lost thing" open? (C §9.9 + D §9.8, one question) | day two at the market / only through a start's `opens_scheme` / both | day two; starts may also open it | D's content, I1's wiring | P2 (D) |
| 23 | Population bands: the app's village 200–1,200 against the GMG's 61–200 | change / keep | out of scope, recorded | — | any |
| 24 | The first road starts: the caravan attack and the road-in | agree / other | agree | I1 | P3 (I1) |

### People and markets (Lane D, I2)

| # | Question | Options | Recommend | Blocks | When |
|---|---|---|---|---|---|
| 25 | Is "girl" a child by default? | child / young adult unless "child", "little" or kin words say so | young adult | `person_words` | P2 (D) |
| 26 | Pronouns for people the world gives no gender (also used by F's pronoun tier and A's `about()`) | (a) adopt the page's first gendered reference and hold it; (b) a seeded roll at entry; (c) they/them and cut gendered prose | (a) | `pronouns_adopted`, `pronouns.py` | P2 (D) |
| 27 | May a stranger come looking for the player? | only through an engine event / also for an errand | an engine event only | the approach table | P2 (D) |
| 28 | A village market: a master, or the settlement's own authority? | master at every scale / at town scale and up | town and up | I2 | P3 (I2) |
| 29 | Does being brushed off by the master cost regard? | yes / no | no | `audience` | P3 (I2) |
| 30 | Adopt the GMG purchase limit as a cap over stall tills? | yes / no | out of scope: it binds nothing today | — | P3 (I2) |

### Magic (Lane E, I3)

| # | Question | Options | Recommend | Blocks | When |
|---|---|---|---|---|---|
| 31 | A first harmful cast: defer through the shipped battle gate, or resolve as a surprise-round action? (It changes a shipped law.) | gate / surprise round | gate | `_op_cast` and the `battle_joined` field | P2 (E) |
| 32 | Canopy height (the CRB gives none) | 10 ft / 30 ft / other | 10 ft | `areas.FEATURES` | P2 (E) |
| 33 | Fire escalation | a patch (2d4 × 10 min, no spread) / the CRB forest fire after a delay | a patch | I3 hazards | P3 (I3) |
| 34 | Do conditions count as harm (hold person, sleep, color spray)? | damage only / conditions too | damage only | `harmful` | P2 (E) |
| 35 | A companion caught in the area | −10 regard / three hits before hostile | −10 | `attitude.harmed` | P2 (E) |
| 36 | Does a burn's hostility fade with time? | fades / only talk mends it | only talk | `harmed` | P2 (E) |
| 37 | **The sword door**: does `_op_attack` call the same `attitude.harmed` (E owns the one line)? | yes / casts only | yes | ownership of `_op_attack`'s line | P2 (E) |
| 38 | Assault as a crime, swords and spells together (suspected → wanted when watched) | now / later | later | — | P2 (E) |
| 39 | A list caster's first morning (a cleric with nothing chosen) | empty with a warning / a default | empty with a warning | `ensure_prepared` | P2 (E) |
| 40 | Add the 1e study hour to the rest clock? | yes / no | no (the rest runs to dawn already) | `_op_rest` | P2 (E) |
| 41 | **Cone geometry.** `grid.cone` is square-centred: 12 squares for a diagonal 15-ft cone against 6 by the book's corner rule. The unfound "alternate cone" FAQ is a separate matter | keep `grid.cone` / lay cones from a corner in `areas.py`, as bursts are | the corner rule in `areas.py`, one rule for every shape | `areas.lay` | P2 (E) |

### The table's furniture (Lane F)

| # | Question | Options | Recommend | Blocks | When |
|---|---|---|---|---|---|
| 42 | An in-page wide Conversation tray | yes / the panel is enough | the panel is enough | — | P2 (F) |
| 43 | Log the player's unquoted speech ("I ask him about the girl")? | an indirect italic row / quoted words only | quoted only | `conversation_log` | P2 (F) |
| 44 | NPC indirect speech ("Drenn asks where you're headed") | log it / narration | narration | `conversation_log` | P2 (F) |
| 45 | The clock face: a heavier strip at twelve? brass or dark? hour hand capped at two turns? dusk tint? | per option | twelve identical strips, brass, capped, no tint | `09-clock.js` | P2 (F) |
| 46 | No target picker in the Spells popover (21.1 supersedes item 11's picker) | agree / keep a picker | agree | `10-spells.js` | P2 (F) |
| 47 | Route the combat bar's Cast… through the same picker, and who owns `#cb-cast`? | yes, F / no | yes, F (Phase 2) | `04-combat-and-turns.js` | P2 (F) |
| 48 | Log the opening companion's first lines? | yes / no | yes, through `after_opening` (C's call) | `conversation_log`'s `DOORS` | P2 (F) |
| 49 | Spells button visibility: `spellcasting.kind` rather than `pc.castable` | agree / other | agree (F1's defect makes `castable` unreliable until E) | `#spellbtn` | P2 (F) |

**Totals: 49 questions; 8 must be answered at G0 (1–8).** The rest wait for their lane or
integration task.
