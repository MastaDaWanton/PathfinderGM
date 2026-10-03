# Rules and the opening: research for playtest items 23–25 (2026-10-03)

Lane E of `docs/playtest-2026-10-03.md`. This was searched before any code was written. A
second pass then re-checked the claims the code depends on. Quotes are kept short, and
anything that could not be sourced is marked as such.

## 23. The Diplomacy DC

**What the book says.** Archives of Nethys, Diplomacy
(https://www.aonprd.com/Skills.aspx?ItemName=Diplomacy), re-fetched on the second pass:

- **Influence Attitude.** The DC is hostile 25, unfriendly 20, indifferent 15, friendly
  10 or helpful 0, each "+ creature's Cha modifier". Failing by 5 or more lowers the
  attitude one step, and an attitude can be influenced only "once in a 24-hour period".
  `rules/attitude.py` already had all of this, and it was right.
- **Make Request.** This needs an attitude "at least indifferent". It is "an additional
  Diplomacy check, using the creature's current attitude to determine the base DC", plus
  a modifier: simple advice −5, simple aid +0, important secret +10 or more, and so on.

**Circumstance.** The "Favorable and Unfavorable Conditions" passage, with its four
options (+2 or −2 on the check, −2 or +2 on the DC), is 3.5 SRD text
(https://www.d20srd.org/srd/skills/usingSkills.htm). PF1e's Core Rulebook did not carry
it over:

- d20pfsrd's Skills page has no such rule (checked on the second pass).
- A Paizo thread found no PF1e copy of it (https://paizo.com/threads/rzs2oxql).
- PF1e's nearest rule is the GM's fiat: "simply grant a player a +2 or a –2 bonus or
  penalty" (CRB p. 403, quoted in https://paizo.com/threads/rzs2qk6d).

**Haggling.** It is not Diplomacy in the Core Rulebook. Goods sell for half price
(https://aonprd.com/Rules.aspx?ID=109). The bargaining rules are in Ultimate Campaign
(https://aonprd.com/Rules.aspx?ID=1339): Appraise, or Sense Motive against Bluff, then the
seller's Diplomacy at DC 15/20/25 + the buyer's Cha. That is lane A's to build.

**Adopted.**

- The influence DC is used for any Diplomacy check aimed at a person.
  `judgement.aim_the_sway` names the subject from the player's words, the conversation
  tag, or the only person present, and drops the plan's `dc` and `circumstance` before
  validation.
- The circumstance arithmetic is kept, because it is the 3.5 DC option and gives the same
  odds. Its record now says what ran: "DC lowered by 2 to 8 for a favourable
  circumstance". It used to say "+2 circumstance", which is the book's wording for a
  bonus on the check.
- The attitude DC's record now names its basis: "DC 17 (indifferent 15, Cha +2)".

**Not modelled, on purpose for now.** Make Request is not a separate path. At
indifferent, a simple-aid request (+0) costs the same DC as influencing, so the clerk's
price is identical either way. The two differ in what follows: a failed request is just
refused, while a failed influence by 5 or more costs a step. The engine treats every
targeted Diplomacy check as influence, so the replayed flirt cost the clerk's goodwill
(indifferent to unfriendly). Telling the two apart needs the request's kind, which is a
judgement about the player's words. Recorded as open.

**Refused.** Applying the plan's ±2 circumstance to the attitude DC. The CRB's +2/−2 is
the GM's fiat for when nobody knows the rule. Here the rule is known and has a table, and
the plan proposing its own discount is exactly what law three forbids.

## 24. "/gm what is the veil?"

**What other tools do.**

- **Avrae** (the D&D Discord bot) makes the user name the domain: `!spell`, `!monster`
  and so on. Within a domain it tries exact match, then substring, then fuzzy, and offers
  a choice list when unsure
  (https://raw.githubusercontent.com/avrae/avrae/master/utils/functions.py).
- **AI Dungeon's Story Cards** fire on keyword matches and warn about short triggers that
  appear in common words (https://help.aidungeon.com/faq/story-cards).
- **FIREBALL** (Zhu et al. 2023, https://arxiv.org/abs/2305.01528) found that models
  given game state beat models given dialog history alone.
- **Discourse context.** Gale, Church and Yarowsky (1992,
  https://aclanthology.org/H92-1045/) found a word keeps one sense within one discourse
  "98%" of the time. That is the reason to read the word from the story it came from.
- **Conversational QA.** QuAC (https://arxiv.org/abs/1808.07036) and CoQA
  (https://arxiv.org/abs/1808.07042) have questions that are "only meaningful within the
  dialog context".

**Could not source.** No product or paper documents handling "X is both a rules term and
a story term". I could not confirm how Friends & Fables, Everweave or Fables.gg answer
rules questions, and "context-first retrieval" as a named practice is unconfirmed.

**Adopted** (`gm_answers.story_first`). If a lookup finds a rules entry and the recent
story used the term, the answer:

1. quotes the sentences that used it, labelled by source (the narration, the player's own
   line, or a suggestion the GM offered);
2. says plainly when only a suggestion has named it;
3. offers the entry in one line, with the question that fetches it.

The window is the last 40 transcript entries and the suggestions of the last 4 prose rows.
Asides do not count. A question that names the catalogue ("the spell veil") is answered
as before, Avrae-style, because the user picked the domain. A spell or feat on the
character's own sheet also goes to the rules.

**Refused.** Asking a model whether "veil" means the spell or the story's veil. That is
the guess this door exists to avoid, and it would add a model call (item 26).

## 25. The opening card

**What other traditions do.**

- **Blades in the Dark.** "Make it about the obstacle, not the method", and "Not every
  situation and obstacle requires a clock" (https://bladesinthedark.com/progress-clocks).
  Progress ticks by effect level (https://bladesinthedark.com/effect).
- **Dungeon World.** Grim portents are checked off when the change happens in play, and
  the GM moves include "Offer an opportunity, with or without cost"
  (https://www.dungeonworldsrd.com/gamemastering/).
- **Apocalypse World.** The countdown advances "when it makes sense to", and conditions
  that depend on the PCs go under an "if". This is from a secondary write-up; the
  primary text was not reached.
- **Bethesda's Creation Kit.** Quest stages are set explicitly, and objectives are
  displayed and completed by script, with targets and compass markers
  (https://fallout.wiki/wiki/Resource:Creation_Kit/Quest). The way to satisfy an
  objective is in reach by construction.
- **Emily Short on salience narrative.** It can "pathfind its way towards the next
  trigger topic"
  (https://emshort.blog/2016/04/12/beyond-branching-quality-based-and-salience-based-narrative-structures/).

**What was tried and abandoned.**

- Failbetter removed the "flash grind" deck refresh in 2020, calling it "something that
  we never designed or intended"
  (https://www.failbettergames.com/news/upcoming-balance-changes-to-fallen-london).
- Alexis Kennedy dropped the term "QBN" for resource narratives
  (https://weatherfactory.biz/qbn-to-resource-narratives/).
- Apocalypse World 2e replaced fronts with the threat map. Baker's reasons could not be
  reached (403).

The lesson for us: progress that comes from repetition (grind) is the failure. A step
should land once.

**The measurement.**

- The card collected six approaches and finished at clock 0/4.
- Its eleven keys did not include *bed*, because `keys_from` drops three-letter words.
- The town had a tavern with three people in it, and the card never said so.
- The purse was `{}` from the first turn.

**Decision on "Is there anything I can do for some coin?"** It advances the card, but
only because the errand says "a bed you can **pay for**" and the purse cannot cover one.
The obstacle is the money (Blades), not the method. With coin in hand the same line is
not about the bed (`cards.about`). The price is the Core Rulebook's common inn stay, 5 sp,
"a place on a raised, heated floor and the use of a blanket and a pillow" (d20pfsrd
Hirelings, Servants & Services, citing PZO1110). Ultimate Equipment's page prints the poor
stay as 2 gp; the CRB has it at 2 sp, and that value is not used.

**Adopted** (`rules/cards.py`, the errand-need section).

- An errand's need is read off its own words. Only lodging is wired: it is the measured
  case.
- The need's words become keys.
- The place that meets the need comes from the settlement's own place set (the
  `lodging` slot, `schemes.PLACE_KINDS`) and goes on the card from the opening: "Beds are
  let at the tavern."
- Three steps each land once:
  - asking after a bed;
  - asking for paid work while unable to pay;
  - arriving where beds are let.
- A night's `rest` there settles the card.
- Talk alone fills the clock to one short of full and stops (Bethesda: an objective
  completes on its own stage).
- New data World Bible should send is recorded in `docs/from-world-bible.md`
  (`play.places[].lodging`).

**Not done.**

- Resting at the tavern does not charge for the room. Coin is lane A's.
- The opening frame still says "a lit doorway with a room's noise behind it" while the
  engine stands the party in the market. The setting is lane B's.
- Errands other than lodging (a meal, paid work, a cart) have no need row yet.
