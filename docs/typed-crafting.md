# Typed crafting: the base item, made for real

Built 2026-10-28 on `feat/typed-crafting`. Code: `rules/typed_craft.py` (the chains),
`Engine._op_make` (the op), `gm/interpret.py` (the `craft` act), `gm/acts_to_ops.py`
(`_craft`), `play/views.py` (`_point_to_the_bench`), `gm/beat_verify.py` (the attempt).
Tests: `tests/test_typed_crafting.py`.

## The report and the ruling

> "My wife tries to level up blacksmithing through narration and didn't get real items or
> experience." — the owner, 2026-10-28

Reproduced before any change on gemma-4-12B: of eleven typed craft lines the reader filed
ten as `other` and one ("I enchant my sword") as `cast`. `other` owes no op. Nothing was
rolled, nothing spent, nothing made and no mastery paid, while the narrator wrote the work
done. The only craft op the plan could write, `craft`, paid mastery from a tier, stages
and risk the model chose and made no item: a door to mastery with nothing behind it.

The owner's ruling the same day: "we should try to direct people to the forge menu but i
think you should allow the crafting of the base weapons through narration" — and yes, the
same for every craft.

## Prior art (researched before the design)

- **Achaea** (Iron Realms): `FORGE FOR <descriptors> <weapon>` at a lit forge makes the
  whole item from one command; the older system made a crude item and refined it in a
  separate step. <https://wiki.achaea.com/Forging>, <https://wiki.achaea.com/Weaponsmithing>.
  Adopted: one typed line, the base item; finer work elsewhere.
- **DragonRealms**: seven to ten typed commands per item (`POUND INGOT WITH HAMMER`,
  `TURN … WITH TONGS` …), which players scripted away
  (<https://elanthipedia.play.net/Forging_guide>,
  <https://www.rpherbig.com/2016/10/31/why-are-we-writing-these-scripts.html>). Refused:
  the typed line never asks for the steps one by one.
- **Inform 7** check rules: an unmet requirement is named and the action stops before
  carry-out runs ("You can hardly photograph without a camera", WI §12.9,
  <https://ganelson.github.io/inform-website/book/WI_12_9.html>). Adopted: every refusal
  names what is missing and changes nothing.
- **Skyrim**: made at the forge, improved at another station
  (<https://en.uesp.net/wiki/Skyrim:Smithing>). The same base/finer split.
- **Kingdom Come: Deliverance**: auto-brew of a potion already brewed by hand; its
  Bundle Alchemist bonus "doesn't apply to autobrew"
  (<https://kingdomcomedeliverance.wiki.gg/wiki/Alchemy>). Adopted: the typed line pays
  the step's own mastery, never a quality bonus the minigame would have earned. Its gate
  (auto-brew only after a hand brew) conflicts with the ruling and was not adopted.
- **Friends & Fables**: "the sidebar is the truth"; items are made on the inventory
  screen, not in the narration (<https://arcanumrpgs.com/blog/friends-and-fables-guide/>).
  **Everweave** reviews record items added, duplicated and handed over unpaid by the GM.
  Adopted: the narrator never makes an item; only the engine's `make` effect does.
- **Pathfinder 1e Craft** (CRB; <https://aonprd.com/Skills.aspx?ItemName=Craft>): book
  DCs (simple 12, martial 15, exotic 18, armour 10 + AC), failure by 5 or more ruins half
  the raw materials, masterwork a separate DC 20 component. Each bench already encodes
  these; the typed line reuses them.
- Not sourced: Discworld MUD and Aardwolf crafting; whether any game auto-opens the
  detailed crafting screen after a quick craft or offers it on a button.

## The design

A typed craft walks **the bench's own chain** for the plainest form of the thing, one
step per player d20 (`_roll_or_suspend_stage`, the steps done riding the suspension in
`make_state`). The typed line chooses only what the bench leaves to the player — which
piece goes in which slot, and the minigame — and chooses them plainly:

- the plainest materials carried (common rank; a named common one honoured);
- no optional step, no catalyst, no masterwork aim;
- the minigame's place taken by **Sound** (quality index 1), the forge's own "plain"
  (`blacksmith._OLD_QUALITY_INDEX`, `work_name`'s unprefixed name), capped at the step's
  ceiling.

Each step is settled by the craft's settle functions, lifted out of the bench views so
the bench and the typed line share one copy: `blacksmith.settle_made/settle_miss`,
`crafting.settle_made/settle_miss`, `alchemist.settle_made/settle_miss`,
`leatherworker.settle_made/settle_miss`. Time passes and rent is paid as the bench does.

| Craft | Base chain | Place | Finer (refused to the bench) |
|---|---|---|---|
| Blacksmith | [Smelt at a smithy] → Forge → Assemble | smithy or smith's field kit | uncommon+ metal named, masterwork, finishes, quench/temper/hone, leather-based suits |
| Herbalist | Brew (infusion/decoction), Grind (powder, salve base), Grind → Mix (poultice) | anywhere | tincture, acetum, infused oil, salve, balm, cream, dried, extract, reduction |
| Alchemist | [Calcine or Dissolve] → Bottle, a known **book** formula | laboratory or alchemist's kit | the alchemist's own compounds, catalysts, refining |
| Leatherworker | Flense → Tan; for a pattern Cut → Stitch/Harden → Assemble | tannery or leatherworker's kit | uncommon+ hides named, curry, tool, dye, laminate, masterwork |
| Enchanter | none | — | every enchantment: a property is chosen at the circle on a vessel the craft requires to be masterwork |

A tan or a potion that waits on the clock goes In progress and the chain stops; typed
again once collected, it goes on from where the work stands. A chain whose step is
refused after an earlier step was worked keeps what was done and says where it stopped.
The make outcome's verdict is the work's — success only when the thing asked for landed.

**Which craft and how fine** are the reader's closed answers (`craft`, `work`), never
words read in code. What is made is the player's words, grounded in each craft's own
catalogue by its finders (`blacksmith.shape_info`, the herbal products, `formulae.all`,
`leatherworker.PRODUCTS`); the words left over are asked of the craft's catalogue of
materials, a closed vocabulary.

The reader's craft is checked against the catalogues (`typed_craft.craft_for`): a thing
only one other craft's catalogue names goes to that craft. Measured live: "I forge myself
a chain shirt with my field kit" came back `craft: leatherworker`.

## The pointer

Each tell ends: "Finer work is done at <the bench>." — naming none of the finer work.
Measured live: the first pointer listed it ("better metals, quenching and tempering,
honing, masterwork and finishes") on a REFUSED mithral longsword, and the planned beat
wrote "quenching and tempering the rare metal to create a masterwork blade". A refusal
tell opens "<name> makes nothing." After the beat the table adds one line per bench,
written by code, with the list and a button that opens the bench (`_point_to_the_bench`,
`typed_craft.bench_line`, `BENCH_DOORS`). The line's kind is `benchline`, never `bench`:
a beat's kind is its class, `.bench` is the herb bench's fixed full-screen layer, and
`tools/table_hit_test.js` caught a "bench" line covering the table's people buttons.
Offered, not opened: the counter opens itself on a purchase because a purchase can happen
nowhere else, but a typed craft has already happened, and a bench thrown open over the
table would cover the beat that says what was made.

## The narrator never makes items

- `craft` and `make` are code-only ops: out of the plan's op enum and dropped from a
  plan that writes one; the plan's own Craft check beside a make is dropped too.
- The plan's give of a crafted thing to the player is dropped by `drop_unread_gifts`:
  `craft` is not a getting act.
- `make` is an attempt in the read-back (`beat_verify._ATTEMPT_OPS`), refused or not: a
  page that shows the dagger forged when the engine spoiled or refused it is a
  contradiction.
- On a make's beat only, a call of its own asks what the page says the player made
  (`made_messages`), against the engine's `made` effects; anything else made is a
  `beat-makes-item` contradiction. Measured live: a refused longsword's beat ended "Your
  efforts produce nothing but a duller blade of common steel", which the attempt question
  passed.

## Left open

- A craft line the reader misses (read `other`) still owes nothing, and the made-things
  question is asked only on a beat with a make.
- Alchemy's Experiment, spell potions needing an essence the pack does not carry in a
  pourable form, and the leather patterns whose bodies need a tannery are reached only
  where the shelf already holds the right intermediate.
- The typed forge never alloys or strengthens; steel is used only when steel bars are
  carried.
