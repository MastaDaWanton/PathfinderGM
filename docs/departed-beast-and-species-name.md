# The beast that left and stayed, and the kind that gave itself as a name

*Design record, 2026-10-09. Branch `fix/departed-beast-and-species-name`. The code is
`rules/bestiary.py` (`ground_stated`, `search(stated=)`, `kind_word`, `kind_names`,
`is_a_person`, `instantiate`), `rules/gathering.py`, `rules/ontheway.py`,
`rules/openings.py`, `rules/engine.py` (`_gathering_encounter`, `_a_person`),
`gm/judgement.py` (`name_the_nameless`), `gm/mentions.py` (`what_they_are`),
`gm/beat_verify.py` (`facts_from`, the `left` question, `_shows`), `gm/beat_reader.py`
(`what_not_who`, `name_refusal`), `gm/checks/kind_as_name.py` and
`play/aftermath/name_given.py`. The tests are
`tests/test_departed_beast_and_species_name.py`; the bench rows are the
`gone-while-you-slept`, `still-there-at-dawn` and `has-not-moved` beats of
`tests/beat_verify/gold.py`.*

## The report

The owner, playing 0.2.12, Aurvantis: *"A beast that should have left / I was told it left
by the narration and the figure but it stayed in the scene. then it introduced itself as
its species like it was a name."* The save (sammy.json) has the whole path.

## The real path

1. **Prospecting.** `Engine._gathering_encounter` rolled the forage's creature band and
   `gathering.creature_for` drew **`aelzeldra`** from the bestiary: not a species but a
   named hag of a Society adventure (PFS 1-50, CR 6 monstrous humanoid), one of the 6,406
   spreadsheet rows whose ground is a guess (`biomes_from: floor`, "any"). The tell said
   *"you find an Aelzeldra there before you. The Aelzeldra holds the ground between you and
   the seam"* — her name dressed as a kind. She arrived as c28, named "Aelzeldra",
   faceless (`_bring_in` asks `_a_person`, and a monstrous humanoid is not one).
2. **The next turn.** `judgement.name_the_nameless`, run on every turn, had no copy of that
   rule: a capitalised name is "not a descriptor", so she got her template's name as a
   true name and the town people's body line — *"Goblin: Small, wiry, sharp-toothed …"* —
   which every brief after that gave the narrator as fact.
3. **The rest.** The player slept twelve hours in front of her. The engine's rule for a
   creature holding its ground (`state.holding-ground`, owner ruling D1) lifts it only
   for a fight or a player who closes on it, so she stayed. The narrator wrote *"The
   Aelzeldra is gone. There is no sign of the beast"*, then, extending a short draft, *"The
   Aelzeldra stands there, its small, wiry frame"* and a voice from a "figure" — whom the
   beat reader minted as c29, a Goblin. The line *"The beast is gone, little crawler."* was
   booked to c28 herself.
4. **Why the read back missed it.** Both readers were shown her as
   **"c28: Aelzeldra — human"** (the sheet's default race). Replayed on her own beat, the
   read back found no departure at all, 0 of 3 — the live result; shown "monstrous
   humanoid", it read *"The Aelzeldra is gone."* as her leaving 3 of 3. And even when the
   first read had it, the second read refused it: asked *"does this sentence say that
   Aelzeldra goes out of the place?"*, gemma said no 3 of 3.
5. **"I am Aelzeldra."** The engine's record was her own name; the page gave it. What was
   wrong is that the game had met her as a kind.

## Prior art

- **The Bestiary's own encounter tables** (legacy.aonprd.com/bestiary/encounterTables.html)
  list kinds only — "1d6 trolls", "1 vampire" — never a named individual; Archives of
  Nethys' "Create Random Encounter Tables" (aonprd.com Rules ID 2388) builds tables from
  the territory's creatures and CR. Named villains are placed by an adventure, not rolled.
- Inform 7 and NCP-Bench as cited in docs/narrator-after-defeat.md: the description comes
  from where the world model holds things, and the page is audited against that ledger.
- Could not source: any published treatment of a game narrator writing a present
  character gone.

## Decided

**The departure: the narrator's, not the world's.** The engine already has the rule for
this creature — it holds until struck or closed on — so a page that sends it away is a
contradiction, and the engine does not apply it. The read back's `left` slot is the door
that judges it ("presence": *X is still here*), and it needed two things to work: the
readers told what the creature is (`mentions.what_they_are`, one copy for both readers:
its creature type for a creature that is no person, the world's people for a person who
has one), and the second read's question asked the way departures are written — *"has
gone — left, or no longer here?"* (probed: the old wording 0/2 on "is gone"; *"…is no
longer here?"* 2/2 on it but 0/2 on "a boy … slips out into the rain"; this wording 2/2 on
both and 0/2 on two sentences that keep the creature there). Whether a creature holding a
seam should leave of its own accord while the player sleeps in front of it is a rule the
owner has not made; nothing here invents one.

**The name: a kind is drawn as a kind, called by its kind, and never a name.**
- *What the land holds* (`bestiary.ground_stated`): every door that draws a creature out
  of the land — the forage, the road, the night, the caravan's land foes — draws only a
  block whose ground is somebody's own words (a printed Bestiary Environment line, or a
  homebrew author's). In the owner's hills at fifth level that is 46 of the 197 the forage
  could draw; 151 were spreadsheet guesses, among them Aelzeldra, Thora Petska, Doctor
  Oathsday, Mrs. Pedipalp, a Restraining Chair and a Supply Sack. Every biome but the
  planes keeps 18 to 116 from first to twelfth level.
- *Called by its kind* (`bestiary.kind_word`): a printed kind with no name of its own goes
  by its kind, lower-case, as the hand-written townsfolk do — "wyvern", "dire wolf" (the
  index's "Wolf, Dire" said the way prose says it). Every name reader in the app takes a
  capitalised name for a proper one. A spreadsheet row's name is left as written: that is
  where named individuals live, and nothing in the data says which rows are which.
- *No people's face or name for a creature* (`bestiary.is_a_person`, the one copy, asked
  by `_bring_in`, `person_words` and now `name_the_nameless`, which also puts back a save
  that already holds one: a face in `appearance_for`'s own "<people>: …" shape, a true name
  that is only the template's name).
- *Never what they are as who they are* (`beat_reader.what_not_who`): the world's peoples
  (non-humanoid ones included — Pangrella's Khra'gix and Khy'vyr are refused like Korvu)
  and the rulebook's races, and the person's own kind (`bestiary.kind_names`: the
  hand-written template's word, the creature type, a printed block's name). `name_refusal`
  asks it first; `name_given` asks it too; and `gm/checks/kind_as_name.py` reads the beat
  reader's `names` and `lines` — a person giving their own kind as their name in their own
  line — and repairs it with one targeted rewrite (their real name if the world holds one,
  else no name), the backstop cutting the line with its speech clause.

**Found on the way, and fixed because the fix exposed it.** With the borrowed Goblin face
gone from the hag, the narrator wrote the real goblin (c29) as "the goblin" — a Goblin in
its brief, "guildhand, human" to the readers — and the absent check of 43199e3 took him
for "goblin with a scarred cheek", held across town: an `absent` finding on the goblin in
6 of 6 name-turn replays, one rewritten to *"The goblin is nowhere to be seen"* while he
talked. The readers are shown a person's people now (6 → 2 of 6), and the absent check's
second read lists the people as the first read does — what they are, and "not here" —
instead of by name alone: on the eight goblin sentences, two asks each, the away goblin
was confirmed 16 of 16 before and 2 of 16 after.

## Measured

Live replays through `/api/say` (Django's client, the browser's view) on copies of the
owner's own saves in a scratch data root, gemma-4-12B heretic; "before" is master fa478ec
(0.2.12), "after" this branch. Ollama was shared with other sessions.

**The rest turn** (sammy.json.2, "i lay on the ground and rest watching the aelzeldra"):

| | before (6) | after (6) |
|---|---|---|
| a draft that wrote the creature gone | 1 | 1 |
| …caught and repaired (`beat-presence`) | 0 | 1 |
| the final page saying it is gone while the engine holds it | **1** | **0** |
| a second body made out of the creature's own epithet ("the beast") | 1 | 0 |
| the creature's face in the brief a Goblin's | 6 | 0 |

The after run's repair read *"The Aelzeldra is here—not moved, but simply still there,
leaving only a patch of disturbed earth"* — agreeing with the engine, clumsily. One after
run met a gourd leshy in the night (`ontheway.night`), a printed kind, named "gourd leshy".

**The name turn** (sammy.json.1, "My name is Sammy, What is your name"):

| | before (6) | after, first (6) | after, with the people shown (6) |
|---|---|---|---|
| the hag giving "Aelzeldra" as her name | 1 (cut as narration in quotes) | 0 | 0 |
| an `absent` finding on the goblin standing there | 0 | 6 | 2 |

**A kind on the seam** (the same save with c28 made a gargoyle, the kind the fixed forage
could draw, told of by its kind; "My name is Sammy. What is your name?"):

| | before (6) | after (6) |
|---|---|---|
| the gargoyle given a Goblin's name and face by the engine | 6 ("Vora Kragnir") | 0 |
| …and that name on the page | 6 | 0 |
| a second body made of it | 1 ("second Vora Kragnir") | 0 |
| the kind given as a name | 0 | 0 |
| a name invented on the page | 0 | 1 ("Varkas", not taken) |

**The read back bench** (`tools/beat_verify_bench.py`, 2 runs, 59 beats: the 55 of
docs/narrator-after-defeat.md and four seam beats). After the second read: clean beats
falsely alarmed **0 of 82**; `presence` P 1.00 R 2/2 (it was 0/3 with the old question, on
the seam beat alone); `absent` P 1.00 R 6/6; harm 2/6, hour 6/6, trade 8/8, hands 8/10,
move 4/6 — each as on master. The absent check's new people list did not cost the
departed raiders: 6 of 6 kept.

**On our own server** (`manage.py runserver` on a free port, the scratch root seeded from
sammy.json.2, the turn posted as the browser posts it): the panel's `scene.actors` held
c28 "Aelzeldra", Holding Ground, before and after — the panel and the map figure were
never wrong; only the page was. The first live rest turn wrote *"the beast is no longer
within your immediate sight … the first light is your only companion"*, and the reader
filed it as an hour. The `left` line now says "or whom it says is no longer there": the
bench reads that sentence as a departure 2 of 2, and the second read refuses it 2 of 2 —
out of sight is not quite gone, and the engine holds the creature "far". So that softer
wording still ships.

Four more rest turns on our own server after that change, a fresh copy of the save each:

| run | the draft | what shipped |
|---|---|---|
| 0 | the creature asleep where it stood | the same |
| 1 | *"The Aelzeldra is gone, leaving nothing but a scar in the earth"* | caught (`beat-presence`): *"The Aelzeldra is still here, standing amidst the heavy, lingering silence"* — but the page still ends *"You are alone on the high ground"* |
| 2 | still there, "a presence in the morning mist" | the same |
| 3 | *"The Aelzeldra is no longer a looming shadow … it is a memory of the hunt … You are alone on the ridge"* | **shipped**: the read back found no departure in it |

All told on this branch, eleven live rest turns (six replays, five on the server): four
drafts sent the creature away, two were caught and repaired, two shipped — both oblique
("no longer within your immediate sight"; "a memory of the hunt … you are alone"). On
master, six replays: one draft sent it away (*"it is gone"*), and it shipped.

## Not done

- **Oblique departures still ship** (2 of 4 drafts that sent the creature away, above):
  "it is a memory of the hunt", "you are alone on the ridge". The read back has no slot for
  "nobody else is here", and a sentence that only implies a departure is what its second
  read is built to refuse. The input side — the narrator told after a long rest that a
  creature holding its ground is still there — was not changed: the brief already says
  "Conditions: holding ground", and master's narrator kept it there 5 of 6 times.
- **The owner's save keeps "Aelzeldra"** as c28's name: she IS Aelzeldra in the book, and
  nothing in a save says which wild creature was drawn as a kind. Her borrowed face and
  true name are put back on load; the old tell stays in the transcript.
- **A kind-named creature is a descriptor to the mention finder**, as the thug and the
  watchman always were: "The Clockwork Spy's limbs" no longer gets a certain ref from its
  name, and who the sentence means is the beat reader's answer (off in the suite). The
  measured boards of the creature-closing tests keep the name they were measured with.
  Not measured live for the NPC-turn checks (`closing_claimed` and its neighbours).
- **Spreadsheet rows still go by their written names** when the planner or a scheme spawns
  one ("Bandit", "Ogre Brute" capitalised). Telling a named individual from a kind among
  the 6,406 needs a field the content does not carry — the same work the licensing
  decision (docs/bestiary-licensing.md) waits on. World Bible: the world's own creatures,
  when they come, should arrive marked as kinds or as somebody.
- **A creature holding its ground through a long rest** does what the stance says: nothing.
  If it should wander off, attack the sleeper or be checked by the camp's watch roll, that
  is the owner's rule to make.
- **The remaining absent misreading** (2 of 6): the narrator calls c29 "the goblin" while
  another person's whole name is "goblin with a scarred cheek". The names are the world's
  descriptors; nothing here renames anyone.
- **An invented name on the page** ("Varkas", 1 of 6 after) is not recorded and not
  repaired: it is no kind and no people, and inventing names is the namer's
  (`settle_introductions`) territory.
