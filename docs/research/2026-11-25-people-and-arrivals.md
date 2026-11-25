# Lane fix/people-and-arrivals: research notes (2026-11-25)

Playtest 2026-11-23, items O4, O1, 14, 15, 16, 17, 19, 20. Sources were read by a research
pass (WebSearch/WebFetch) and checked a second time against the primary pages where they
carry the decision. UESP returned 403 throughout, so every Elder Scrolls claim below rests
on forum threads, and is marked that way.

## O4: a stranger's first meeting, not a rumour

**Seen.** #218: the lost scholar's first line was "The folk in Branford speak often of the
old mine just off the woods". Turn log row 347: the matter slot carried the rumour card
"What Branford says of the old mine off the woods" with `approach: go_between` and the
scholar as the carrier (`cards._rumour_pull` → `cards._carrier`). Nothing in the plan asked
him to notice the stranger at all; with the matter slot taken, the aside slot was dropped.

**Sources.**
- PF1e Diplomacy (https://www.d20pfsrd.com/skills/diplomacy/). The rules separate meeting
  a person from gathering talk. Meeting is a starting attitude, hostile through helpful,
  and changing it takes a minute of interaction. Gathering Information takes 1d4 hours
  "canvassing people at local taverns, markets, and gathering places". No rule has a
  stranger hand over rumours as a greeting.
- The Alexandrian, "Rumor Tables Part 2" (https://thealexandrian.net/?p=48549). Rumours
  reach players in three ways: proactive (pushed sparingly when the players arrive in a
  town), reactive (the player goes looking) and opportunistic (worked into NPC talk). A
  rumour lands when it is an NPC's own story.
- Emily Short, "Modeling conversation flow: beginnings and endings"
  (https://emshort.blog/2009/08/10/modeling-conversation-flow-beginnings-and-endings-using-scenes/).
  Characters "should greet one another before launching into other discussion". One of
  her openings is the NPC acknowledging the player's arrival and greeting them. Topics come
  after the opening.
- MUD mobprogs (stonia.ttu.ee/builder/mobprogram.txt; night.lensmoor.net/pages/mobprg.html;
  the Avendar page first cited now returns 404): `greet_prog` fires when a PC enters, and
  only if the mob saw them come in (`all_greet_prog` fires regardless). It is a separate
  trigger from `speech_prog`, which answers keywords.
- Oblivion (forum only: nexusmods topic 34972, a GOG thread): "Rumors" was a topic the
  player chose, and every class of NPC gave the same lines. Players complained, and Skyrim
  narrowed rumours to innkeepers and quest hooks. That this was deliberate is unconfirmed.

**Chosen.**
1. Talk of elsewhere is carried only by somebody the player has already spoken with
   (`cards._carrier`: never a `hooks.relationship` STRANGER). The owner said rumours are
   what you get once talking, not a greeting, and the rules and the Alexandrian say the
   same.
2. A stranger the party has just come upon gets a first-meeting reply slot
   (`planned._first_meeting`). This happens on a beat that brought the party somewhere
   (`came_somewhere`: a walk, a venture, a hex), for one person who can speak and is not
   of the party. They react to the stranger as their own situation makes them: the first
   clause of the engine's notes, plus "far from any town" when they are out on a hex or
   below ground. They may ask who the player is and what they want here, or say who they
   are, and say nothing of news or other places. It happens once per person (`MET_KEY`).
   The ref goes on the slot as a reply speaker, so the speech tag, `hailed_by` and
   `join_talk` treat it as the person speaking to the player, and a conversation opens.

**Rejected.**
- Banning rumour pulls below ground only (`setting_of == "under"`). The tower's rooms read
  as "ruins" outside (lane senses-and-light, item 1), and the owner asked for every NPC
  met anywhere.
- An enum of reactions chosen by code (wary/afraid/welcoming). Code would decide a
  character's temperament from words. The model reads the person's situation, and the
  slot's own checks hold the result (no job invented; the reply is the speaker's).
- Listing "raider or thief" in the ask. The prompt's shape becomes the output's shape
  (CLAUDE.md), and every stranger would fear robbers.

**Owner call (provisional).** A stranger in town no longer mentions town talk in passing on
their own. Rumours now come from people already spoken with, from asking, and from the
board. If town life reads thinner, the fix would be an overheard bark, attributed to a
speaker the player does not address, and not a greeting.

## O1: a creature's look on first sight

**Seen.** The ramidreju, the clockwork spy, the chickens and the poltergeist came on as
names only. The face backstop (`views._finish`) skips a body with no `appearance`, and
creatures (`bestiary.has_a_people` false) never get one. `settle_descriptions` also
counted "a tiny clockwork spy hovering" as described, because a body word was present.

**Sources.**
- CircleMUD builder's manual (https://circlemud.org/cdp/building/building.txt). A mob has
  three texts: a short description used in action messages, a long description shown in
  the room listing, and a detailed description shown on `look at`. The engine owns all
  three.
- Inform 7 WI 3.11 (https://ganelson.github.io/inform-website/book/WI_3_11.html). A thing's
  "initial appearance" is used until it is first taken. Its "description" appears on
  EXAMINE.
- The Alexandrian, description formulas
  (https://thealexandrian.net/wordpress/47328/roleplaying-games/random-gm-tip-description-formulas):
  a visible sign of an ability, then one physical trait, then a verb.
- PF1e Knowledge (https://www.d20pfsrd.com/skills/knowledge/): identifying a monster is
  DC 10 + CR. Hiding the name behind a check is a further step this lane does not take.
  The pages already name creatures, and the owner asked for the look, not for the name to
  be hidden.

**Chosen** (`gm/creature_look.py`). Code supplies the facts from the record: size beside a
man and kind, subtype, natural weapons from the melee line, and ways of moving. One schema
call writes one or two sentences of what is seen. Code validates the result: no number, no
second person (a look is not a deed), and no size that contradicts the record (the house's
closed size question, `checks.creature_size.ask`/`contradicts`). If it fails, there is one
rewrite with the fault named, and after that a plain line built from the facts. It is
written once per kind and kept in `scene.said`, and placed by `narration.place_the_face`
the way a face is. A second creature of a described kind is marked described and gets no
second line. Creatures here and seen are owed a look whether or not the page named them
(`judgement.creatures_unseen_described`), and a body word no longer counts as described
for them.

**Rejected.**
- A look written per individual creature. Two chickens have one look, and the ruling on
  individual faces (npc-faces-are-individual) is about people.
- Free text from the model's own memory of the monster with no check. The validators are
  why the look can be shown.

**Limit.** The look is placed on the player's own turn door (`_finish`). A creature that
first appears in an enemy-turn beat is described on the player's next beat.

## 14: the /gm aside pulled unrelated characters

**Seen.** "/gm I have tried to read the repeating words but I get nothing" got three
characters back from BM25 (-7.9 each, on common words), all with names not in the question.

**Sources.** Inform scope, WI 18.29
(https://ganelson.github.io/inform-website/book/WI_18_29.html): a thing out of scope is not
a candidate at all. Shi et al. 2023 (arXiv 2302.00093): irrelevant context in the prompt
"dramatically" lowers accuracy. Their context was injected into math problems, not
retrieved, so the case here rests on analogy. Self-RAG (arXiv 2310.11511): retrieve on demand.

**Chosen.** A question with no proper name keeps a `character` hit only when a word of that
character's name is in the question (`gm_search.search`). Events, places and peoples are
still found by their words ("the salt fever" still finds The Salt Fever).

**Rejected.** Raising the BM25 threshold. The Rosalies scored -7.9, as strong as a real
phrase hit like "Long Peace" (-7.8).

## 15: the same sentence twice

**Seen.** #171: "Ramidreju falls to the ground, unconscious and dying. The creature collapses
to the ground, unconscious and dying."

**Sources.** Holtzman et al. 2019 (arXiv 1904.09751) and Welleck et al. 2019 (arXiv
1908.04319): repetition is a decoding/training property. arXiv 2607.09791: a
multiplicative repetition penalty at theta=1.3 cut schema-valid JSON from 97% to 23%, and the narrator
writes JSON slots. NovelAI has a separate phrase-level penalty
(https://docs.novelai.net/en/text/phrasereppen).

**Chosen.** A deterministic page check, `narration.said_twice` / `drop_said_twice`, run in
`GMAgent._page_pass`. It cuts a later narration sentence that has the same last four words
as an earlier one, the same numbers, and three in five of its own words already said.
Speech is exempt. Measured over the 1,539 GM lines in the owner's ten saves: 1 hit, #171.
Two earlier, looser rules hit 34 and then 5 lines, mostly engine records differing by a
number or one word ("+47 str" / "+47 con").

**Rejected.** A repetition penalty, because of the JSON risk above.

## 16: the player's words echoed as speech

**Seen.** #175, a narrate_only turn: 'You lean over the fallen beast … "I finish the
ramidreju."' The doing slot is told 'The player said: "…". Show the player starting on it …
in what they do or say', and it printed the line as dialogue.

**Sources.** AI Dungeon (https://help.aidungeon.com/faq/say-mode): the player's words are
quoted only in Say mode, which the player chooses. Inform WI 7.6: a conversation table's topic
column "is not meant to be printed out again".

**Chosen.** `planned.echoed`. In a slot carrying the player's line (the lead act slot or
the doing slot), and when nothing was speech (no say, and no quote marks typed), a sentence
that quotes three or more of the player's words in their own order is cut. A slot left with
nothing is asked once more with the fault named.

## 17: a creature made out of an idiom

**Seen.** #194. The gathering excursion's closing tell read "When the work is done, Shadow
makes for one last stand of the same". The spot was a "stand" (of oak, of reeds:
`gathering.spot_for`). The closing came back as "A shadow coalesces … rising to offer one
final, defiant stand". The excursion's closing is the consequence call, and no beat-verify
row was logged for that door.

**Sources.** Wiseman et al. 2017 (arXiv 1707.08052) and Nan et al. 2021 (arXiv 2102.09130):
extract the output's entities and compare them with the source. Kasner & Dušek 2024 (in
the project's own research record): sparse input invites invention.

**Chosen.** The root is the tell's wording, so the tell no longer says "one last": "heads a
little way off, to another stand of the same" (`play/craft_views.py`).

**Not done.** Running beat-verify over the excursion's closing. That door has no beat
reader today, and adding one is a larger change than this lane's item. Flagged in the
report.

## 19: "if he wishes to leave" told as "you wish to leave"

**Seen.** #223. The tell kept the words ("to the effect that the way out is clear is he
wishes to leave"). The say slot wrote "you tell the scholar that the way out is clear and
you wish to leave".

**Sources.** Lee et al. 2020, "Converting the point of view of messages"
(arXiv 2010.02600): turning "tell Bob I love him" around is a task with its own 46,565-line
dataset. Pronoun person changes force verb agreement changes. The deictic shift study
(Cambridge, Language and Cognition): indirect speech takes the reporter's perspective.
I found no measurement of this error in LLM game narration.

**Chosen.** `planned._pronouns_kept`, which compares closed words only. If the player's
words name somebody by he/she/they and the slot names nobody that way, the slot is asked
once with the fault named. Otherwise the engine's own line, which keeps the words as said,
stands in.

**Rejected.** Rewriting the player's words into direct speech in code (him → you). That
means reading the referent of every pronoun, which the owner ruled out ("no regex reading
English").

## 20: "a ghost's body"

**Seen.** #278. The dungeon's revelation read "the ghost's own body lies where it fell", and
the page wrote "a ghost's body, which bears a knife".

**Sources.** The PF1e ghost template (https://www.d20pfsrd.com/bestiary/monster-listings/templates/ghost/):
a ghost is incorporeal. Its "physical remains" stay behind, as the items it valued do. The
GameMastery Guide's haunts are tied to an area, not to a body.

**Chosen.** The revelation names the corpse as a thing of its own: "a skeleton lies where it
fell, the remains of the one who became the ghost" (`content/dungeons/tags.json`). How
procedural dressing tools record who a corpse belonged to could not be sourced.

## Second pass

A critic subagent re-fetched every source the decisions rest on. Nine of them were
confirmed. The corrections it found are made above: the Emily Short wording was a
paraphrase set in quote marks, the Avendar page is 404 and has been re-cited, the Shi et
al. claim now uses their framing, and the penalty setting is named.

The research pass flagged two claims as unsourced: Oblivion's rumours came from forum
complaints only, and no dressing-tool practice was found. Both are marked that way above.
I re-read the d20pfsrd ghost template and the Diplomacy page against what is claimed here.
The ghost page's own wording is "the ghost's physical remains", so "the ghost's body" is
not wrong by the book. The fix is that the page should read as a corpse, not that the
original wording broke a rule.
