# Design D: people, markets and quests

Phase 0 research and design for Lane D of `docs/fix-plan-2026-09-28.md`. It covers items
5, 9, 10, 12 and 15 of `docs/playtest-2026-09-28.md`. It also covers the Phase 3 market
task (I2) and the hooks-and-ties task (I4) where they depend on this lane.

It was written read-only. Every cause below was checked against the code on
`fixes-2026-09-28` or against the Bobby save (`%LOCALAPPDATA%\PathfinderGM\campaigns\bobby.json`:
turn_log entries 12 and 16, transcript beats 4–8, the scene's people, population, schemes
and cards). Where a claim could not be sourced, the text says so.

---

## 1. Items covered

| Item | Defect | Measured cause |
|---|---|---|
| 5.1 | "I ask him about the girl in the market" spawned a guildhand called *girl* beside the player | The reading was right (`talk`, target "him"). `interpret.target_of` drops bare pronouns, so `person_sought` returned "". `inject_company` then fell through to `_ADDRESSES`, which took "him about the girl in the market" as the addressee, and `_CIVILIANS` found "girl" (turn_log 12). |
| 5.2 | The girl did not exist at the market | Nothing records a person that an NPC places elsewhere. On the next turn the finder searched for `["girl", "work:guard", "describ"]`. The clause "that the watchman described" was read as her description, because `population.find` strips only "who" clauses. Result: `population-miss` (turn_log 18). |
| 5.3 | The spawn ignored the word "girl" | `_op_spawn` passes the name to `instantiate`. That gave pronouns they/them, race human (the template's) and an Orc appearance (the local people's). |
| 9.1 | The market keeper was the first person met there | `keepers.staff` mints the keeper on arrival. The brief lists her in WHO IS HERE like anyone else. |
| 9.2 | The quest pull overrode the player's search | `thread_to_pull` scored the card "present", because Drenn was at the market from hour 0 and the scheme had put him there. It added "they approach the player and say the first word". The reading's `seek` target was never consulted. |
| 10 | A market is one person | `places.STAFFED["the market"]` names one keeper, "the stallholder who runs the pitch". She is both the authority and the only seller the trade panel can open across. |
| 12 | Drenn's cold pitch | The pull carries only the title and the open objective, never the reward. The pitch's "lost not through carelessness" is **not** the secret card leaking. It is the scheme's `grants_on_open` `say`, which put *"Drenn Ironvale looked away when asked how the Power leaf was lost"* on Bobby's sheet at hour 0, before he had met Drenn. It reached the brief through `actor.noticed()` (confirmed on the save's PC effects). Bobby's tie says Drenn *taught* him, but `acquaint` only binds the opening companion. |
| 15 | The suggestion said "her" when a man spoke | The suggestions are the model's own. Drenn is they/them because no world character carries a gender. The prose called him "a man". The brief states no pronouns for NPCs, and nothing checks a suggestion's pronoun against who the player is dealing with. |

---

## 2. Prior art, by tradition

### Medieval market regulation: who actually ran a market

- **The clerk of the market regulated. They did not trade.** The clerk kept a court at every market, "for the punishment of minor crimes", with control over prices, weights and measures. Blackstone called it "the most inferior court of criminal jurisdiction in the kingdom" (https://en.wikipedia.org/wiki/Court_of_the_clerk_of_the_market).
- **Disputes went to piepowder.** The court of piepowders ("dusty feet") was held on the spot during a fair or market. Merchants sat as judges over contract disputes, theft and violence (https://en.wikipedia.org/wiki/Court_of_piepowders; read from the search summary, not fetched in full).
- **One town's records show the same shape** (Victoria County History, Colchester, https://www.british-history.ac.uk/vch/essex/vol9/pp269-274):
  - Henry VI granted the clerkship of the market to the bailiffs in 1447.
  - A salaried deputy clerk was added in 1557 "for the more speedy punishment of offenders".
  - The market tolls were leased to a contractor from 1310 until about 1800.
  - Masters or overseers of butchers, leather workers and the fish market were appointed from 1443.
  - Most usefully, in 1562 "Outsiders had standings assigned to them, according to their crafts."
  - A piepowder court sat only occasionally, between 1448 and 1482.

**What this gives the design.** Four roles are separate: the authority (clerk or bailiff), a deputy who takes the ordinary business, the toll-taker, and the traders. Stalls are grouped by trade. The authority is busy with measures, tolls and disputes. It does not sell.

### Pathfinder 1e: the market as an aggregate

The GameMastery Guide gives each **settlement** a base value (a 75% chance an item at or below it is on sale) and a **purchase limit**, "the most money a shop in the settlement can spend" on one item. The limit runs from 500 gp for a thorp to 2,500 gp for a village and 100,000 gp for a metropolis. The stat block lists NOTABLE NPCS as role first, then name, e.g. "Captain of the Guard Jiranda Hollis" (https://legacy.aonprd.com/gameMasteryGuide/settlements.html).

So in 1e, the market's capacity belongs to the place and its people are listed by office. This app already caps each stall's till (`market.purse`, 150–400 gp for an uncommon stall). That sits well under a village's 2,500 gp limit.

### CRPGs: splitting town trade across vendors

All from search summaries, not fetched pages:

- **Mount & Blade**: four dealers per town (armour, arms, horses, goods) and a separate Guildmaster who gives work (https://strategywiki.org/wiki/Mount&Blade/Towns).
- **Skyrim**: a steward stands before the authority — "The Jarl is, as you can imagine, very busy." (https://en.uesp.net/wiki/Skyrim:Proventus_Avenicci). The busy master with a go-between.
- **Daggerfall**: reputation "determines which people will talk to you" (https://en.uesp.net/wiki/Daggerfall:Reputation).
- **Morrowind**: per-merchant barter gold, reset daily (https://en.uesp.net/wiki/Morrowind:Commerce) — the shape of `market.can_pay`.
- Already in the code: CircleMUD's room-bound shopkeeper, and Ultima Online's abandoned shop economy (`rules/keepers.py`). Kenshi and Ultima VII's vendor splits were not researched.

### Quest-hook craft

- **The Alexandrian.** *Don't Prep Plots*: a situation, not a sequence (https://thealexandrian.net/wordpress/4147/roleplaying-games/dont-prep-plots). *A Plague of Patrons*: one job offer is a fragile node; use several hooks and **proactive nodes**, "the nodes that come looking for the PCs" (https://thealexandrian.net/wordpress/46727/roleplaying-games/ask-the-alexandrian-4-a-plague-of-patrons). *The Lion, the Witch, and the Scenario Hook*: the player may refuse (https://thealexandrian.net/wordpress/44541/roleplaying-games/the-lion-the-witch-and-the-scenario-hook). *Rumor tables, part 2*: news arrives **proactively**, **reactively** or **opportunistically**, mentioned "in the general conversation" (https://thealexandrian.net/wordpress/48549/roleplaying-games/hexcrawl-tool-rumor-tables-part-2-hearing-rumors).
- **The Angry GM.** The opening scene tells the PCs how to win, sells the motivation and shows the exits; he dismisses the cold open (https://theangrygm.com/your-mission-is-to-start-an-adventure/).
- **Disco Elysium** tasks come "through conversations with NPCs and by encountering situations" (https://discoelysium.fandom.com/wiki/Tasks). **The Witcher 3**'s contracts come mostly from notice boards (https://witcher.fandom.com/wiki/Notice_board). **Skyrim's courier** delivers quest letters. All fan sources, not design statements.
- **Not researched:** Pentiment, Kingdom Come: Deliverance, and Sly Flourish beyond a search summary. I make no claim about them.

### Interactive fiction: the person mentioned but not present

- **Inform's scope token.** An ordinary grammar token matches only what is in scope. "If the action needs to work on things that aren't within the player's sight or reach", Inform uses an `[any thing]` token (Recipe Book §6.2, https://ganelson.github.io/inform-website/book/RB_6_2.html). The I7 Handbook applies it to *asking about* absent people and things (https://inform-7-handbook.readthedocs.io/en/latest/chapter_5_creating_characters/conversations%2C_part_ii_asktellgiveshow/).
- **Eric Eve's Epistemology** gives every thing two flags, *seen* and *familiar*. A familiar thing is one the player knows about "for other reasons", such as something they have heard of but not found. Seen or familiar counts as *known* (Recipe Book §5.5, https://ganelson.github.io/inform-website/book/RB_5_5.html).

This is exactly items 5.1 and 5.2. **Asking about is not addressing.** The girl the watchman spoke of is *familiar*: she exists, somewhere named, and is not yet *seen*.

---

## 3. Tried and abandoned, and why

1. **Autonomous NPC goals (Oblivion's Radiant AI).** Secondary sources report the system was dialled back before release, because goal-driven NPCs killed and robbed each other (Escapist, https://www.escapistmagazine.com/oblivion-npcs-brought-their-world-to-life-then-they-nearly-killed-it/; SlashGear). I could not reach a primary interview that says so. Wikipedia's Radiant AI article does not. **Lesson taken:** a person's wants never decide on their own that they walk up to the player. The engine picks the approach from a closed table.
2. **The quest-giver who pushes regardless (Fallout 4's Preston Garvey).** Players report urgent, endless settlement requests and banish him; mods exist to switch them off (Nexus mod 24940; Steam threads). A Forbes column, "How To Fix Fallout 4's Maddening, Never-Ending Radiant Quests", returned 403, and I did not read it. Whether Bethesda patched the pacing I could not confirm. **Lesson taken:** a pull that fires whatever the player is doing is the defect item 9.2 describes. The pull yields, and it rests.
3. **The single patron job.** The Alexandrian does not call it abandoned, but fragile. **Taken:** several approaches to one situation (overheard, go-between, sent word).
4. **In medias res as the default opening.** The Angry GM advises against it unless it adds something specific. A stranger bursting in with an errand is the cold-open gambit. **Taken:** no approach row lets a stranger open cold.
5. **The simulated shopkeeper economy (Ultima Online).** Already refused in `keepers.py`. **Kept:** stall lines are drawn, never stocked from a simulation.
6. **In this codebase:**
   - Staffing the entrances, tried on 2026-09-21 and refused by its own test.
   - `inject_company`'s regex addressee. It was already narrowed twice (the 2026-09-27 asking-around fix) and is one of the detectors the interpreter exists to retire. **Taken:** gate it on the reading. The regex becomes a fallback only when there is no reading.

---

## 4. Recommended design, per item

### 4.1 Asking about someone is not addressing them (5.1)

The change is in `judgement.inject_company`.

- **When a reading exists, it decides.** Look for a `talk` or `seek` act whose target is not a bare pronoun and contains a civilian word.
  - If the target is a pronoun ("him"), the addressee is somebody already present, and the function returns the intents unchanged.
  - The words after `about`, `for`, `regarding`, `whether`, `if`, `where` and `what` are the *topic*, never the addressee.
- **`_ADDRESSES` is the fallback only when there is no reading.** Its capture stops at those same words, and a pronoun addressee returns unchanged.

This is Inform's rule: the topic token reaches out of scope, and the person token does not.

### 4.2 The mentioned-elsewhere person: a population record at a place (5.2)

The Epistemology shape: **familiar, not seen.**

- **Detect in the aftermath** (`play/aftermath/mentioned_elsewhere.py`), over the beat's `said` records from NPC refs only: a person phrase (a `population._PERSON_WORDS` word, a gendered noun or an occupation) joined by `in/at/by/near` to the **name of a place this settlement really has** (`engine.places()`, not `scene.at`). A pronoun line from the same speaker ("She's in the market") binds to their last person phrase. A place not on the list makes nothing: the engine, not the model, owns geography.
- **Record only when the finder has nobody** (`population.find` returns NONE over every ring): `population.note(scene, phrase, spot=<place id>, heard_from=<ref>, hint=<the speaker's words about them>)`, with `seen: False`. `hint` feeds the life roll ("her stall" makes a stallholder); the phrase stays the speaker's words, which the player will paraphrase.
- **Where she is needs no new code:** `residency.resolve(WORK)` already returns `spot`, so she is at the market in her working slots and home at night.
- **The finder drops the source clause:** `population.find` strips `that`/`whom` clauses as it strips `who`, so "the girl that the watchman described" searches "the girl".
- **The brief says she is found.** `embody_sought` runs before the plan, while the party is still at the gate, so after a `travel` she is HERE with no body. `gm/brief/sought.py` states the post-resolution answer for the reading's `seek` target — "THE ONE THE PLAYER CAME LOOKING FOR (fact): the girl in the market is here — <face>." (ELSEWHERE and NOWHERE stay with the existing `absent` line.) Addressing her next turn embodies her through `embody_sought`.

### 4.3 A spawn honours the player's word (5.3)

A new pure module, `rules/person_words.py`: `from_words(phrase, world=None, location_id="") -> {"gender", "pronouns", "age", "minor": bool, "people_id"}`, read from the synonym groups' gendered nouns, `lives`' old/young words, and a people's name from `play.races`/`play.names` ("an elf girl"). `_op_spawn` (after `_bring_in`), `population.embody`/`note` and the mention recorder all use it to set `gender` and `pronouns` — identity fields like the name, not mechanical states — and to pass the age word to the life roll.

- **The body matches the people:** with no people named, the people whose body line `appearance_for` drew becomes the actor's `world_people_id` and race, so "human, with an Orc face" cannot happen.
- **The name matches the gender** only once the world ships gender per given name; until then `names.true_name` is unchanged, by the standing ruling.
- **"Girl" as a child** is an owner question (§9.1): `lives` maps it to the child occupation and the brief says IS A CHILD. Recommended: a young adult unless "child", "little" or kin words say otherwise.

### 4.4 Keepers stay in the background until dealt with (9.1)

A keeper is still minted on arrival; the trade panel needs a body.

**Dealt with** is asked of existing state, never a new flag (second law): the keeper holds `talk.with-you`, the regard effect or any `bond.*` tag, or is this turn's `talk`/`seek`/`buy` target, or is the seller `_trade_offer` opens. For each present keeper not dealt with, `gm/brief/keepers_in_background.py` says: "IN THE BACKGROUND (fact): Ashla Ironvale (c3) is at her pitch and busy with it. She does not approach the player or speak first; if the player turns to her, she answers." `gm/checks/keeper_forward.py` raises `keeper-forward` (weight 2) for an unprompted `say` to the player from such a keeper. First introductions then come only from the start, the background, or whoever the player looked for.

### 4.5 The pull yields to the seek (9.2)

`cards.thread_to_pull` learns the reading. It fetches it lazily, as `gm.interpret.reading_of(player_text)` — a cache lookup, imported inside the function (the precedent is `engine.py:1642`). So the `play/views.py` call site needs no change.

**The rule.** When the reading has a `seek`, `call_on` or `talk` act whose target resolves (`scope.look_for`) to anybody but the card's people, the approach is `waits`: the giver is present and busy, nothing about the matter is said, and `yielded` is `True`.

**The check** `gm/checks/pull_yields.py` raises `pull-took-the-beat` (weight 3) when the reading seeks somebody, the beat does not answer it (no sought head noun, finder's HERE name or `absent` line on the page), and one of the pull's people has a `say` line. The repair asks for the search to be answered first and the giver left at their business. The deterministic backstop is the existing `not_here` sentence, or §4.2's HERE line, printed by the engine.

### 4.6 The hook rebuilt as ingredients, and the approach table (12)

A new pure module, `rules/hooks.py`, owned by Lane D, provides:

- `relationship(scene, actor) -> "tied" | "known" | "stranger"`;
- `scene_state(scene, card, reading) -> str`;
- `approach(relationship, state, card) -> str`;
- `ingredients(card, scene, world) -> dict`;
- `render(ingredients, approach) -> str` (the pull's `text`).

**Relationship.** Engine facts only:

| Relationship | Condition |
|---|---|
| **tied** | The giver holds `bond.knows-you` whose effect source starts `background:`, or the PC's tie record names the giver's `world_entity_id` (Lane C). |
| **known** | Any other `bond.knows-you`, or the regard effect with talks ≥ 1, or a population record with `last_met`. |
| **stranger** | Neither of the above. |

**Ingredients.** The pull dict gains these keys, all words and no numbers:

| Key | Content |
|---|---|
| `giver` | `{"ref", "name", "role"}`. The role is the entity's own `Role` fact (Drenn: "healer"), else their life's work name, else the codex words. |
| `to_player` | The relationship, plus `tie`: the tie sentence itself ("You learned it from Drenn Ironvale…"), or "". |
| `want` | The open objective, as now. |
| `offer` | `card.reward` in the world's words. It never reached the narrator before; this is the fix for "no offer". |
| `motive` | Why they want it, as they would say it. From the scheme card's optional `hook.motive` (§6), else "". |
| `doing` | What they are doing right now. From `hook.doing`, else their work at this hour ("tending a pitch"), else "". |
| `withholds` | A behaviour, never a fact: `hook.withholds` ("looks away when asked how it was lost"). Offered **only when the giver is being asked** (approach `asked`). |

The secret card's facts are **never** in the pull. What it is not told it cannot tell: the 2026-09-25 "hidden facts may direct, never tell" ruling.

**The approach table,** chosen by the engine. "Busy" means seeking someone else or in conversation with another; "elsewhere" includes a shut hour.

| Scene | Stranger | Known | Tied |
|---|---|---|---|
| Giver present, player free | `overheard` | `greets` | `greets` |
| Giver present, player busy | `waits` | `waits` | `waits` |
| Giver elsewhere in town | `go_between` | `go_between` | `sends_word` (once), then `go_between` |
| Player turned to the giver | `asked` | `asked` | `asked` |
| In a fight | no pull (as now) | no pull | no pull |

What each approach tells the prose, in `render`:

- **`overheard`**: the giver is seen doing the thing (`doing`), in the background, speaking to somebody else or to nobody. Nobody addresses the player, and the player may step in.
- **`go_between`**: somebody the player is already dealing with mentions the giver's trouble in passing, in one sentence of their own. This is the Alexandrian's opportunistic rumour. The giver is not brought on stage.
- **`sends_word`**: a runner or a note says the giver asks the player to come by. It goes through the scheme `news` carrier `kin` or `courier`, which already exist.
- **`greets`**: the giver greets the player as someone they know, *by the tie* ("the bonesetter they taught"). Only after the greeting may they raise it, as a favour between people who know each other: motive first, then the offer.
- **`waits`**: present and busy; nothing said.
- **`asked`**: they say what they want, why, and what they offer, in their own words. `withholds` shows as behaviour if the player asks how.

**There is no cold approach by a stranger.** That row does not exist. A stranger reaches for the player only through an engine event (a theft in progress, a fight), which is another system's business.

**Pacing.** An approach other than `waits` and `asked` shows once per `REST_TURNS`. The card records each approach (`Card.approaches`), and the next one is the one not yet used. That gives the variety the "shape of the prompt" lesson calls for.

**The demonstration.** The fix plan calls for a worked hook scene, uncopyable. There is one short demonstration per approach, in `content/hooks/approaches.json`, set in a situation no world shares (a ferry landing, a lost net). `render` appends it as "like this, never these words", and only on a card's first approach. It is policed by Lane A's `brief_verbatim` check and by a test that no demonstration shares a content word with either fixture's names.

**Checks.**

`gm/checks/hook_leaks.py` raises two findings:
- **`hook-secret-on-page`**, weight 3. Two or more *distinctive* identity keys of the scheme's secret card (its keys minus the visible card's) appear in a giver's line.
- **`giver-asks-own-answer`**, weight 2. A giver's line is a question containing the lost item or the objective's place, together with where, hidden or find. That is Drenn asking Bobby where his own leaf is.

`gm/checks/giver_knows_you.py` raises one finding:
- **`greets-known-as-stranger`**, weight 2. A present tied or known person, or a pull giver, introduces themselves by name, says "stranger", or uses a first-meeting formula ("you have the look of", "who are you") to the player. The repair carries the tie sentence.

**Scheme content (the-lost-thing).**

- `opens` becomes `["at($market)", "since(campaign) >= 1d"]`. The first market visit is then the player's own.
- The `grants_on_open` block with its `say` moves into a step, `criteria: ["at($market)", "present($giver)"]`, with a silent tell. The player no longer "noticed" something about a man he had not met.
- A proper `event:talk($giver)` criterion needs `schemes._events_from` to read `say` outcomes. That is I4's, because `schemes.py` belongs to Lane C in Phase 2.

### 4.7 Suggestions follow who the player is dealing with (15)

**The pronoun source.** Every NPC in the brief gets a pronoun line from a new section, `gm/brief/pronouns.py` — "SPEAK OF THEM AS (fact): Drenn Ironvale (c4) he/him; …". It covers only actors whose pronouns are *set*, and "set" needs a policy (§9.2).

**Recommended policy:**
1. The player's or plan's word at entry (§4.3).
2. The world's gender field, when World Bible ships one.
3. Otherwise, the **first gendered reference the page makes to them**. The page is what the player read, and keeping it consistent with itself is not a guess from a name. This is adopted once, by the aftermath member `play/aftermath/pronouns_adopted.py`, from the beat's bound mentions (the cast ledger's phrase, "a man in a suit"), and held from then on.

**The repair** is `play/aftermath/suggestion_pronouns.py`, on `c.suggestions` after the prose. It finds who the player is dealing with (the `talk.with-you` actor, else this beat's `to=you` speaker, else the reading's `talk` target). A third-person pronoun outside quotes whose family fits **no one present** is rewritten to that actor's; one that fits another present person is kept; one that cannot be squared drops its suggestion. Logged as `suggestion-pronoun`.

### 4.8 The market as stallholders and a master (10; built in Phase 3, I2)

**Stallholders are who you trade with.**

- **Stall lines** (`content/rules/stall-lines.json`) group the market's GEAR staples as Colchester grouped its standings, "according to their crafts": `provisions`, `cord-and-canvas`, `light`, `tools`, `vessels`, `cloth`, `sundries`. Scale folds lines onto fewer people — a village two holders (food; everything else), a town four, a city one per line — through `market.holder_of(line, scale) -> str`.
- **A stallholder is minted on first need and kept** (residency's idiom): `world_entity_id = "keeper:<market id>#<holder>"`, staffed once (`scene.staffed` gets the same key), named by `keepers.name_for` on that id, anonymous in the panel ("the woman at the rope stall") until dealt with. `keepers.place_of` strips the `#…` suffix, so hours, `shut_here` and `keeps_a_counter` work unchanged.

**How the panel picks a seller.** `_trade_offer` matches the want against every line (`goods.match_want`), mints that line's holder through the arrival door if absent, and returns `{"open": True, "want", "line"}`. `_merchant_here` prefers that holder; `_stall_of` keys shelf and till by holder (Morrowind's per-merchant gold); `market.on_sale(counter_kind="market:<line>")` stocks only the line. With no want, the panel opens on the stallholder the player is talking with, else offers the line list. It never opens on the master.

**The market master is an authority, not a shop.**

- **`STAFFED["the market"]` gets a title and words.** The title is `"the master of the market"`; the words are `("clerk", "merchant", "noble")`. The row gains a category marker, so `keeps_a_counter` is false for them.
- **Old saves.** An existing `keeper:<market>` actor becomes the master on load. No shelf moves; the lines are drawn anyway.
- **What occupies them,** in words by slot (`keepers.occupation(master, clock) -> str`): setting out pitches and taking the stall money at first light, walking the rows with the measures until noon, hearing a quarrel in the afternoon, the day's count at evening — flavoured by the settlement's own `sells`/`buys`.
- **The brief** section `gm/brief/market_master.py` (I2) states the occupation, adds "busy; does not seek the player out", and says what earns a hearing.

**Availability and the hearing.** A new module, `rules/audience.py` (I2), provides:

`hearing(scene, master, pc, player_text, reading) -> {"granted": bool, "why": str, "line": str}`

A hearing is granted by any of:

| Ground | Condition |
|---|---|
| `regard` | The master is friendly or better toward the PC (`attitude.step_of`). |
| `tie` | The PC's background tie has place `market` (stallholder, apprenticed, pit-fighter) or the guild (guild-clerk). This is read from the background document's `ties[].place` via the PC's `background:<id>` effect. |
| `their_business` | The player brings something the master cares about, detected by `audience.matter_of(player_text, reading) -> "pitch" \| "dispute" \| "theft" \| "measure" \| ""`: a dispute or theft at this market, a false measure, asking for a pitch, or the PC being wanted here. |
| `asked_well` | A Diplomacy *request* for an audience succeeds. The DC comes from `attitude.influence_dc`, it takes a minute, and it is once a day (the influence cooldown's shape). |

Otherwise the player is **brushed off**. The line names when the master will be free (the evening count), shaped like `keepers.shut_line`, and offers the nearest stallholder for ordinary questions. Being brushed off costs no regard (§9.6).

This reuses the `call_on` knock's gates — attitude step, a standing welcome, the hour — without calling `Engine._knock`, which is outside I2's ownership.

**The check** `gm/checks/master_unprompted.py` (I2) raises `master-approaches`, weight 2, when the master has a `say` line to a player who has not addressed them and has no hearing ground.

**The same split for the other runners-not-servers** (the master of the workshops, the harbourmaster, the clerk of the counting house, the master of the games) is marked in STAFFED by the same category, and shares `audience.hearing`. Only the market is built in I2. The others are one table row each afterwards.

---

## 5. What the Phase-1 seams must provide

### S1 — `gm/checks/`: the `BeatContext` fields Lane D reads

| Field | Type | Used by |
|---|---|---|
| `text` | `str` (final prose) | all |
| `scene` | `Scene` | all |
| `world` | `World \| None` | pull_yields, hook_leaks |
| `outcomes` | `list[Outcome]` | pull_yields (travel happened) |
| `reading` | `dict \| None` (interpreter frame) | pull_yields, keeper_forward, master_unprompted |
| `player_text` | `str` | all |
| `pull` | `dict \| None` (the `thread_to_pull` result, with the new keys in §4.6) | pull_yields, hook_leaks, giver_knows_you |
| `sought` | `dict` (`scope.look_for` result after resolution for `person_sought`: `scope`, `who`, `record`, `ref`, `line`) | pull_yields |
| `said` | `list[dict]` (`{"who": ref, "to": ref, "line": str}` from `gm/speech`) | keeper_forward, hook_leaks, giver_knows_you, master_unprompted |
| `turn` | `int` | pacing reads |

**Member contract:** `ORDER: int` and `def check(ctx: BeatContext, out) -> None`, which appends `Finding(id, detail, hint, weight)`.

### S2 — `gm/brief/`: the brief context

`BriefContext` carries `world`, `scene`, `location`, `here`, `known`, `turn`, `player_text: str`, `reading: dict | None`, `recent: list[str]`.

**Member contract:** `ORDER: int`, `def section(ctx) -> str` (with "" meaning nothing).

Lane D members: `sought.py` (ORDER 30), `keepers_in_background.py` (40), `ties.py` (50), `pronouns.py` (60).

- **`ties.py`** replaces the plan's `hook.py`. The hook text stays in the pull, last in the prompt, where D6/D7 measured it working. What the brief needs is who each present person is to the player, in the tie's own sentence.
- **I2 adds** `market_master.py` (45).

### S3 — `play/aftermath/`: the aftermath context

`AftermathContext` carries `c` (the campaign, so `c.suggestions` can be mutated), `scene`, `world`, `engine`, `text: str`, `said: list[dict]`, `outcomes`, `reading`, `player_text: str`, `turn: int`.

**Member contract:** `ORDER`, `def step(ctx) -> list[dict]`, returning turn-log rows.

- **The hook must run after `c.suggestions` is set.** Today that happens at `views.py:1951`, which is before ≈2215, so it holds.
- Lane D members: `mentioned_elsewhere.py`, `pronouns_adopted.py`, `suggestion_pronouns.py`.

### S4 — persisted state

All of these live inside dicts the save already carries (`scene.population`, `scene.cards`), so they need **no new Scene field and no save/load code**. Only tolerant reads (`.get` with defaults) are required, and S4 records them in the register.

| Where | Key | Type | Default |
|---|---|---|---|
| population record | `seen` | `bool` | `True` when absent |
| population record | `heard_from` | `str` (ref) | `""` |
| population record | `heard_at` | `int` (clock minutes) | absent |
| Card (`as_dict`/`from_dict`, cards.py, D) | `approaches` | `list[{"turn": int, "approach": str}]` | `[]` |

Actor `gender` and `pronouns` already exist.

**The arrival door (S4's `arrive()`)** must be what `_op_spawn`, `population.embody` and the stallholder mint go through, so every newcomer gets a square (item 14).

### Outcome and effect fields

| Source | Field | Type |
|---|---|---|
| `_op_spawn` effect `spawn.actors[]` | `pronouns` | `str` |
| `_op_spawn` effect `spawn.actors[]` | `from_words` | the `person_words` dict |
| aftermath row | `{"kind": "heard-of", "record": id, "spot": place_id, "from": ref}` | — |
| aftermath row | `{"kind": "suggestion-pronoun", "before": str, "after": str}` | — |
| pull dict | `approach` | `str` |
| pull dict | `yielded` | `bool` |
| pull dict | `giver` | `dict` |
| pull dict | `to_player` | `dict` |
| pull dict | `offer`, `motive`, `doing`, `withholds` | `str` |

The pull dict keeps `title`, `text`, `keys`, `people` and `why`. The turn log's `"pull"` title row belongs to Lane E's file (`views.py`). Recording `approach` beside it is a one-line request to E, or it waits for I4.

### API payload keys (I2)

- **`POST /api/trade` request:** `{"want": str, "line": str?}`.
- **`POST /api/trade` response adds:** `"line": str`, `"lines": [{"id": str, "label": str, "seller": str}]` and `"seller": {"ref": str, "name": str}`.
- **Turn response `trade`:** `{"open": bool, "want": str, "line": str}`.
- **`POST /api/trade/do`** accepts `"line"`.

---

## 6. Owned edits: confirming or amending Lane D and I2

### Lane D (Phase 2) — confirmed, with amendments

- **Confirmed:**
  - `judgement.inject_company` (§4.1);
  - `_op_spawn` (§4.3);
  - `rules/cards.py`: `thread_to_pull` and `salience` (the reading), Card `approaches`;
  - `rules/population.py`: `note(spot=, heard_from=, hint=)`, `find` strips `that`/`whom`, `embody` uses `person_words`, `where_now` for an unseen record;
  - `content/schemes/the-lost-thing.json` (opens and the grant move, §4.6);
  - `gm/checks/pull_yields.py`, `hook_leaks.py`, `giver_knows_you.py`;
  - `gm/brief/keepers_in_background.py`.
- **Amended (new files):**
  - `rules/hooks.py` and `rules/person_words.py`;
  - `content/hooks/approaches.json`;
  - `gm/brief/sought.py`, `ties.py` and `pronouns.py` (`hook.py` is dropped);
  - `gm/checks/keeper_forward.py`;
  - `play/aftermath/mentioned_elsewhere.py`, `pronouns_adopted.py` and `suggestion_pronouns.py`.
- **"Suggestions take pronouns from actors"** is not an edit to `agent.py` (Lane A's). It is the aftermath member.
- **Stays Lane C's in Phase 2:** knows-you on every tied person (`backgrounds.acquaint`) and the PC's structured tie record. D only reads them, through `hooks.relationship`, which treats "no record" as stranger. The Bobby replay's `greets` row therefore passes only after C merges. G2 should expect that.

### I2 (Phase 3) — confirmed, with amendments

- **Confirmed:** `places.STAFFED` (the market row and a category marker), `rules/market.py`, `rules/keepers.py`, the `views` trade functions, and `gm/checks/master_unprompted.py`.
- **Adds:**
  - `rules/audience.py`;
  - `content/rules/stall-lines.json`;
  - `gm/brief/market_master.py`;
  - `goods.stocked_at` gains line filtering. `goods.py` is not in any lane's list today; I2 should own it.
  - `_trade_offer`, `_merchant_here` and `_stall_of` are trade functions and are I2's. `_buying_note` names the seller.

### I4 — confirmed, with additions

I4 adds:

- `schemes._events_from` emits a `talk` event from `say` outcomes;
- `schemes.validate` checks a quest card's `hook` fields for slots and digits;
- the-lost-thing's grant step gains `event:talk($giver)`;
- the `greets` row is verified with C's knows-you.

---

## 7. World-agnostic notes and World Bible asks

### Nothing keys on Aurvantis

- **Place names** come from `engine.places()`.
- **Person words** come from `content/people/synonyms.json` and `occupations.json`.
- **Peoples** come from `play.names` / `play.races`.
- **Roles** come from the entity's own `Role` fact. Pangrella's roles are long phrases ("Innovative developer and expert in magnetic shift adaptation"), so `hooks.ingredients` takes the role as the world wrote it and never matches it against a list.
- **The master's flavour** reads `play.settlements[].sells/buys`. Both fixtures ship these (Vormoor "iron"; Pangrella "Fine ironwork and crafted windcatchers"). The synthetic world should ship neither, and the occupation lines must then read fine without them.

A world with no market place makes no stallholders, and `_trade_offer` behaves as today.

### Asks for `docs/from-world-bible.md`

| Need | Best shape |
|---|---|
| How a settlement's trade is staffed | `play.settlements[].trade = {"stalls": [{"line": "cord and canvas", "about": "<one sentence>"}], "authority": {"title": "clerk of the market", "answers_to": "<office>"}, "market_days": "<words>"}`. Words, not numbers. Lines as the world's own trades. |
| Gender per name, or per character | `play.names[].given` as `[{"name": "Kael", "gender": "male" \| "female" \| ""}]`, or split lists; `play.cast[].gender` (already requested 2026-09-27). |
| Real roles on the cast | `play.cast[].role` = the entity's own role word (already in the playtest's table). |
| A character's standing | `play.cast[].standing`: "notable" / "common". Lets the engine pick a market master from the cast, rather than mint one, when the world wrote one. |
| Hooks | `play.cards[]` with `giver`, `want`, `offer`, `motive`, `withholds` (the §4.6 ingredients), so a world's own hooks arrive with the same shape as a scheme's. |

---

## 8. Tests and the live `market-seek` script

Every test runs across the three worlds through the R0 `worlds` fixture. Each docstring names the measurement it prevents.

| Test | Asserts | Measurement in the docstring |
|---|---|---|
| `test_d_asking_about_is_not_addressing` | "I ask him about the girl in the market." with reading `talk/him` at a gate: no spawn; with no reading, the regex stops at the topic | turn_log 12: c2 *girl*, Korvin Korvath, they/them, human with an Orc face |
| `test_d_heard_of_is_recorded_at_the_place` | a `said` row from c1 naming "the girl in the market" makes one record, `spot` = market, `seen` false; a place the town lacks makes none | beat 4, and nothing recorded |
| `test_d_heard_of_is_found_on_arrival` | after `travel` to the market in a working slot, "the girl that the watchman described" is HERE and the sought line names her | the miss `["girl", "work:guard", "describ"]` |
| `test_d_spawn_honours_the_word` | "girl": she/her, young, race agrees with the face's people; "an old man": he/him, old | c2's they/them and mismatched race |
| `test_d_pull_yields_to_the_seek` | giver present, reading seeks another: `approach == "waits"`, `yielded`, no approach instruction | beat 8 |
| `test_d_pull_check_on_the_bobby_beat` | the replayed beat 8 with its reading raises `pull-took-the-beat` | beat 8 |
| `test_d_no_cold_approach_by_a_stranger` | over every state, a stranger never gets `greets` or an address-first line | "You! You have the look of…" |
| `test_d_hook_carries_its_ingredients` | the reward is in the text; the secret card's distinctive keys never are; `withholds` only under `asked` | no offer reached the narrator |
| `test_d_tied_giver_greets_by_the_tie` | a tied giver's text carries the tie sentence (skipped with a reason until C merges) | Drenn greeted his own student as a stranger |
| `test_d_keeper_stays_back` | an undealt-with keeper is in the background line; after a `talk` she is not | Ashla first met at the market |
| `test_d_suggestion_pronouns` | "I ask her what she's looking for" with only a he/him Drenn talking becomes "him"/"he" | item 15 |
| `test_d_no_noticed_line_before_meeting` | the-lost-thing grants no `knows.*` before the giver is present | Bobby "noticed" Drenn at hour 0 |
| `test_i2_*` | rope finds the cord stall; the master brushes off a stranger and hears a stallholder background; the panel never opens on the master | item 10 |

### Live script `market-seek` (tools/narrator_audit.py, R0 writes it; serial queue)

**Setup.** Start in each world's first settlement that has a market. The setup writes one heard-of record through `population.note(spot=market, heard_from=<opening companion>)`, the same door the aftermath uses, so the run does not depend on the model inventing the girl.

The run is 3 seeds × 3 worlds. It passes when all of these hold:

1. **"I ask <them> about the girl in the market."**
   - 0 of 9 turns add an actor.
   - 0 spawn intents in the turn log.
2. **"I head to the market and look for the girl <they> described."**
   - The party is at the market.
   - `sought.scope == "here"` in ≥ 8 of 9.
   - The beat names her head noun or phrase in ≥ 8 of 9.
   - `pull-took-the-beat` is unrepaired in 0.
   - No `say` line from a scheme giver or an undealt-with keeper in ≥ 8 of 9.
3. **"I talk to her."**
   - She is embodied with she/her in 9 of 9.
   - The conversation opens (a hail) in ≥ 8 of 9.
4. **Across all turns,** 0 suggestions carry a pronoun that fits nobody present.

**G3 additions (I2):**

- "I buy a coil of rope." The panel's seller is the cord-and-canvas holder in 9 of 9, never the master.
- "I ask to speak to the master of the market." A stranger is brushed off with a named time in ≥ 8 of 9. A stallholder-background character is heard in ≥ 8 of 9.

**Baseline to record before any Lane D code:** the same script on master 5cabed1. Expected: step 1 spawns, and step 2 misses.

---

## 9. Open questions for the owner

1. **Does "girl" mean a child by default?** Today `lives` makes her a minor, and the brief says IS A CHILD. **Recommended:** a young adult unless "child", "little" or kin words say otherwise.
2. **Pronouns for people the world gives no gender** (every Aurvantis and Pangrella character):
   - (a) adopt the page's first gendered reference and hold it — **recommended**; the page stays true to itself, with no guess from a name;
   - (b) a seeded roll at entry, stated in the brief before the first description;
   - (c) leave them they/them and cut gendered prose.
3. **A village market: a master, or the reeve's man on market days?** **Recommended:** a master at town scale and up; a village's market is kept by its stallholders, and its authority is the settlement's `governed_by` office, not standing in the market.
4. **Does an NPC's line make a person real?** §4.2 records the girl the watchman spoke of as a heard-of person. The alternative is scope's NOWHERE when the player arrives. **Recommended:** yes, within this settlement and at a real place, never beyond it.
5. **May a stranger ever come looking for the player** — a desperate parent, a scheme marked urgent? **Recommended:** only through an engine event (theft, fight, a runner the engine sends). Never for an errand.
6. **Should being brushed off by the master cost regard?** **Recommended:** no. Pressing after a refusal may, through the existing Diplomacy failure.
7. **Adopt the GameMastery Guide purchase limit** (village 2,500 gp … metropolis 100,000 gp) as a cap over the stall tills? Today's tills are far below it, so it would bind nothing yet.
8. **When should the-lost-thing open?** "Day two, at the market" is proposed. Or should only a start document (Lane C) open it?
