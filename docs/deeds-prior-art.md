# Deeds: prior art

Written 2026-10-08, before any design, per the standing instruction (CLAUDE.md, "Search the
internet for how this has already been solved"). The plan that uses it is `docs/deeds-plan.md`
(cited there as **PA §n**).

**The ruling being researched** (owner, 2026-10-08, `docs/leatherworking-questions.md`, plan open
point 11): *"Build out a deeds system that tracks good or bad things you do, most actions should
only have a small impact, otherwise people will not mean to do certain things and it goes from a
funny accident to a source of frustration very quickly if they are punished too heavily. for now
just track this as a number positive for good deed and -negative for bad deeds. you should be able
to look at this number in your sheet but i dont want it to affect anything yet."*

So the questions put to every tradition were: what number does one act move, how are accidental
or ambiguous acts handled, does anybody have to see it, is there a cap or diminishing rule, and
**what was tried and abandoned, and why**.

**Method and its limits.** Three research passes ran in parallel (computer RPG karma; morality
meters; Pathfinder and MUD alignment, plus the harvesting rules Part 3 of the plan needs), then a
critic pass checked the claims that carry weight (§13). Primary sources were preferred: game
script headers and open-source recreations (Fallout 2's `REPPOINT.H`, the xu4 Ultima IV source,
the DikuMUD/Merc/ROM `fight.c` files, RimWorld's decompiled `ThoughtHandler`), developer blogs and
interviews, and Archives of Nethys for Pathfinder. **The Fandom wikis (Fallout, Red Dead, Mass
Effect, KOTOR, inFAMOUS, KCD) answered every fetch with HTTP 402**, GameFAQs and NMA with 403, so:
Fallout numbers come from the independent fallout.wiki; Red Dead 2 numbers come from two published
guides and search excerpts of the Fandom page, and are marked as such. A value marked
**(excerpt)** was read only in a search engine's summary of a page, never fetched.

---

## 1. Fallout 1 and 2: small fixed values, a separate local track

**Numbers.** Fallout 2's own script header `REPPOINT.H` (https://fallout.wiki/wiki/REPPOINT.H):
killing a good critter **−10**, a child **−15**, an evil critter **+5**, a neutral one **0**.
Karma titles sit at ±250 / ±500 / ±750 / ±1000; the start is 0. Fallout 1's quest karma is tiny:
+1 for complimenting the Shady Sands cook, +2 for returning to Irwin, −1 or −3 for Junktown jail
fines, +5/+10 for the large endings (https://fallout.wiki/wiki/Karma_(Fallout)).

**A second track for who knows.** Town reputation is per town and separate from karma: killing a
good NPC −5, a child −8, an evil NPC +2; tiers Idolized 30+ down to Vilified −30
(https://fallout.wiki/wiki/Town_reputation).

**Reputation titles are ratios over kill counters, not sums of karma** (`REPPOINT.H`): Champion
needs at least 25 kills with evil kills over 3× good kills and no Childkiller; Berserker needs good
kills over 2× evil kills. Berserker was effectively broken because "no characters are actually
flagged as bad ones" (https://fallout.wiki/wiki/Berserker): the defect was in the data that said
who was good, not in the numbers.

**Accidents.** Every macro is gated on `source_obj == dude_obj`: only the player's own kills
count. Companion kills, planted explosives and the super stimpak do not raise Childkiller
(https://fallout.wiki/wiki/Childkiller). **Witnesses:** none; karma moves unseen.

**Lesson.** Small fixed values per category of act worked. Who-knows lived on a second, local
track. The failure was mislabelled actors.

## 2. Fallout 3: a flat value per act, and the designers' own doubts

**Numbers** (https://fallout.wiki/wiki/Karma_(Fallout_3)): range −1000 to +1000; bands Very Good
≥750, Good 250–749, Neutral −249..249, Evil, Very Evil ≤−750. **Theft −5 per instance**, counted
per container opened, not per item and not by value. Hacking an owned terminal −5. Killing a good
creature −25, a non-evil character −100, a Very Evil one +100. Church donation +1 per cap, Purified
Water to a beggar **+50**, quest good acts +50 or more. Megaton: disarm +200, detonate −1000.

**The "fork" complaint could not be sourced** in any form. What the numbers do show is the shape of
the complaint: a fork and a fortune both cost −5, and one murder equals twenty thefts. And one
bottle of water to a beggar (+50) erases ten thefts.

**Ambiguity.** Killing a non-evil NPC costs karma only if the NPC's faction is flagged to give a
penalty, and followers may kill for you penalty-free (same page). **Witnesses:** none for karma;
forum consensus is that karma is "a tally of all you've done... whether or not anyone was around"
(threads not fetchable). **Shown:** the points are internal; only the title appears
(https://fallout.wiki/wiki/Karma).

**What the lead designer said.** Emil Pagliarulo: "When we first started development... we were
really focused on the good and the evil, and tracking that with the Karma system", then "the black
and white nature of the Karma system really wasn't working for us"; the "neutral" area "led to a
lot of internal discussions, even disagreements, about how to track this type of behavior"
(https://vagrantbard.com/2011/05/30/interview-emil-pagliarulo-lead-designer-and-writer-for-fallout-3/).

**Lesson.** A flat value per act ignores what was taken. Large rare values (+50, −1000) in the
same counter as small repeatable ones swamp them: if small is the point, keep quest-sized numbers
out.

## 3. Fallout: New Vegas: karma becomes vestigial, reputation does the work

**Karma** keeps Fallout 3's bands; theft −5, an owned terminal −1 (down from −5), killing a
non-evil creature −25 (https://fallout.wiki/wiki/Karma_(Fallout:_New_Vegas)). **Reputation** is
per faction on two separate axes, Fame and Infamy; script bumps of size 1–5 map to 1, 2, 4, 7, 12
points; **it has witness rules**: being caught stealing and killing a faction member openly move
it, a silenced kill does not (https://fallout.wiki/wiki/Reputation_(Fallout:_New_Vegas); the +2
and +30 infamy values are **(excerpt)**).

**The director, in his own words.** Josh Sawyer: karma "has very little effect. It's mostly just
there for player feedback, a stat like 'Number of Corpses Eaten'"
(https://fallout.wiki/wiki/Fallout:_New_Vegas_developer_statements/Joshua_Sawyer_Formspring_posts/2011),
and later, "the Karma system was vestigial in New Vegas. If we're trying to encourage players to
form their own opinions about factions and individuals, having a design layer that assigns
(essentially) alignment is weird"
(https://fallout.wiki/wiki/Fallout:_New_Vegas_developer_statements/Factions). After his GDC 2012
talk he clarified that he was "championing visible changes in the GUI for all of what I call
'Indirect Reaction Systems' (e.g. karma, reputation, influence, etc.)"
(https://fallout.wiki/wiki/Fallout:_New_Vegas_Developer_Statements/Interviews/Choice_Architecture,_Player_Expression,_and_Narrative_Design_in_Fallout:_New_Vegas).

**What he retuned himself** (his JSawyer mod changelog, https://gist.github.com/dbb/3748244):
"fKarmaModKillingEvilActor from 100 to 5"; "All (known) Feral Ghouls set to Neutral alignment", so
farming ghouls no longer bought good karma; Powder Gangers set to Evil "to prevent karma loss for
stealing". (The changelog also lists `fKarmaModKillingVeryEvilActor` "from 2 to 30"; what that
setting means beside the other could not be confirmed.)

**Lesson.** The director's own fix was to make routine combat almost worthless to the counter and
to stop monsters counting at all. Who-saw-it belongs on a separate, witnessed track. A visible
+1/−1 is good feedback.

## 4. Fallout 4: karma dropped, companion affinity kept

**No developer explanation for dropping karma was found** in anything reachable (Todd Howard,
Pagliarulo, The Making of Fallout 4 statements page); only player speculation exists. It is not
claimed here that Bethesda said why.

**Affinity numbers** (https://fallout.wiki/wiki/Affinity): −1000 to 1100 from 0; loved +35, liked
+15, disliked −15, hated −35, each multiplied by a size scalar: Small 0.5, Normal 1, Large 1.5.
"Most repeatable actions are of type CA_Size_Small." And "it is not possible to perform the same
action several times in a row"; different actions can be chained. Only companions in range react.
(The cooldown's length, two game hours in one excerpt, could not be confirmed.)

**Lesson.** Repeatable trivial acts are halved by design and cooled down per kind of act: the
cleanest prior art for "small values, no grinding".

## 5. Ultima IV: tiny values, a cap, a time gate on good acts only

Read from the xu4 open-source recreation (github.com/xu4-engine/u4: `party.cpp`, `game.cpp`,
`combat.cpp`), which flags in its own comments two places it differs from the DOS original.

**Numbers.** Each virtue starts at 50 (plus 5 per gypsy answer favouring it), floor 1, **cap 99**.
Per act: giving to a beggar Compassion **+2** whatever the amount (1 gp counts); stealing an
unattended chest in a city Honesty/Justice/Honor **−1** each; bragging Humility −5; a humble answer
+10; attacking a good creature or a non-hostile townsperson Compassion/Justice/Honor **−5** each;
fleeing an evil foe Valor −2; killing an evil foe Valor **+1, half the time**; letting a fleeing
good creature go Compassion/Justice +1. Cheating the blind reagent seller cost ten each of Honesty,
Justice and Honor (https://bumbershootsoft.wordpress.com/2017/09/29/hacking-the-virtues-becoming-the-avatar-in-five-easy-steps/).

**Intent.** The only bad-faith signal is **who attacked first**: the penalty fires when you start
the fight with a good creature or a person not set to attack you; if they attack you, killing them
costs nothing (https://wiki.ultimacodex.com/wiki/Virtues_in_Ultima_IV).

**Anti-grinding.** `virtueIncreaseTimeout()` lets a gain count only once per 16 moves. **Only the
good acts are timed; penalties never are.** It still leaked: "it's possible to... raise Compassion
to Avatar level just by giving over and over to the same beggar"
(https://www.filfre.net/2014/07/ultima-iv/). **Witnesses:** none; the numbers were hidden, Hawkwind
describes progress "in vague generalities" (Maher's description, not Garriott's).

**Why it exists.** Garriott built it after Ultima III fan letters described "lots of murdering,
stealing, and all-around reprehensible behavior": "If someone spends 100 hours playing my game, I
have 100 hours of the input that makes that person what they are"
(https://www.filfre.net/2014/07/the-road-to-iv/).

**Abandoned later in the series** (https://wiki.ultimacodex.com/wiki/Karma): Ultima V and VI
folded the eight counters into one karma score starting at 75; Ultima VII dropped formal karma
scoring; Ultima IX brought one score back where "almost all karma modifiers are triggered by
unique, unrepeatable events". No stated reason was found.

**Lesson.** Values of 1 to 5 on a scale of 99 carried a whole game's moral system. Judge only the
fights the player started. Gate the repeatable good act (the same beggar) per person, not just per
time: the time gate alone was farmed.

## 6. Red Dead Redemption 1 and 2: honor, and the accident complaints

**RDR2 numbers** (secondary sources): 17 ranks −8..+8 over an internal −320..+320, 40 points a rank
(https://www.newsweek.com/red-dead-2-redemption-rdr2-easy-honor-guide-ranks-rewards-unlocks-bonuses-1206359).
Per act (https://segmentnext.com/red-dead-redemption-2-honor-and-fame-guide-honor-actions-fame-titles/):
looting a knocked-out person **−1**, stealing a hitched horse −1, scaring a civilian −1, robbing a
safe −20, desecrating the dead −10; helping in a chance encounter +5 to +10, disarming a duellist
+10, donating to camp +10. Greeting gives a bump about every third person. Killing an innocent −5,
"ramps up to −10" in a killing streak **(excerpt)**: escalation for a pattern, not diminishing
returns.

**Witnesses.** In RDR2 honor moves whether or not anyone sees; masks do not help. In RDR1 the
bandana froze honor entirely (https://www.gamepressure.com/newsroom/these-rdr2-mechanic-worked-much-better-in-first-game/z74676).
Witnesses drive only the separate wanted and bounty system.

**Accidents: no forgiveness rule, and the complaints that follow.** Steam threads report honor
lost for an NPC shot by accident while hunting, a dog that ran into a trotting horse scored as
animal cruelty, self-defence costing honor, and "abandonment" when the game would not let a player
carry both a pelt and an injured stranger
(https://steamcommunity.com/app/1174180/discussions/0/1735508653171835990,
https://steamcommunity.com/app/1174180/discussions/0/4297070247695565768). These are exactly the
owner's "funny accident to a source of frustration".

**What Rockstar says now.** Rob Nelson on GTA VI's Criminal Profile (Inven, summarising IGN): it
"is different from RDR2's honour system"; "doing what a mission demands, or dealing with someone
who picks a fight, won't count against the player"; the profile moves only if you "consistently go
beyond what's necessary" (https://www.invenglobal.com/articles/26913/gta-6-full-interview-with-rockstars-rob-nelson-reveals-new-details).
He did **not** say honor was abandoned; that framing is one outlet's. Whether the lines are verbatim
or paraphrased could not be confirmed.

**RDR1** (https://www.ireddead.com/rdr/guides/honor-rankings): −1000..+1000; defend a stagecoach
+400, help a stranger +50, kill an outlaw +10; kill a civilian −50, crack a safe −100, bribe a
lawman −400 to −1000. Large values throughout: RDR2 shrank the petty end to −1.

**Lesson.** Self-judged deeds with no intent check produced the accident complaints. The newest
Rockstar design exempts self-defence and what the situation demands.

## 7. Mass Effect: two meters, then one, then none

**Mechanics.** ME1 and ME2 kept two separate meters that only rise, so Paragon never cost Renegade
**(excerpt)**. BioWare's own blog (Patrick Weekes) on why ME3 changed: "In Mass Effect 2, if you
wanted to get the hardest Charm options, you had to play an almost completely Paragon character...
Many players felt like they had to play pure Paragon to avoid being penalized by the loss of a
dialog option." ME3's Reputation is Paragon plus Renegade, and missions give reputation that does
not "carry a Paragon or Renegade flavor" (https://blog.bioware.com/2012/03/01/reputation-in-mass-effect-3/).

**Andromeda dropped it.** Mac Walters: "you know which way you're moving the stick on every
conversation. You don't have to think about it, because you're just going to hit Paragon every
time" (https://gamingbolt.com/mass-effect-andromeda-dev-explains-replacement-of-renegadeparagon-system).
A BioWare cinematic designer later said about 92% of players were Paragon
(https://www.kitguru.net/gaming/matthew-wilson/over-90-percent-of-mass-effect-players-chose-the-paragon-path/,
reporting a tweet).

**Critique.** The meter cannot read motive: "I've killed thousands of people, but I wasn't RUDE to
any of them, so I can't intimidate this guy" (https://www.shamusyoung.com/twentysidedtale/?p=28160).
No BioWare statement on why ME1 used two meters rather than one slider was found.

**Lesson.** Once a meter gates anything, players optimise toward one pole; BioWare's first fix was
to sum the sides and its last was to delete the meter. A display-only number avoids the cause.

## 8. Knights of the Old Republic: value depends on where you already stand

0 to 100 from 50. The value of a deed depends on the current position: a "high light" deed is +1
for a very-light character and +10 for a very-dark one, and the mirror for dark deeds
(https://www.gamebanshee.com/starwarskotorii/alignmentcharts.php, KOTOR II's chart; that KOTOR 1
uses the same values is **(excerpt)**; the scaling lives in `UT_AdjustCharacterAlignment`,
https://deadlystream.com/topic/5037-how-do-the-dark-side-and-light-point-values-work/). Mastery at
an extreme gave stat bonuses and cheaper powers, so the system "rewards only going strongly
lightside or darkside" (Avellone, known only through a blog's paraphrase,
https://jedibyknight.com/2015/04/25/qa-with-kotor-ii-lead-writer-chris-avellone/). Repeatable
dialogue with no cooldown (bribing Roland Wann over and over) farmed dark points without limit
(https://www.gamebanshee.com/starwarskotor/strategies/lotsofdarkpoints.php).

**Lesson.** Rewards at the poles push players to the poles. Without a per-act cooldown, repeatable
acts are farmed.

## 9. inFAMOUS: the middle abandoned, the mechanical choice abandoned

Nate Fox on neutral karma: "We had [neutral karma] initially, but we found that people wanted to be
really good or really evil. No one cared about the middle"
(https://www.destructoid.com/neutral-karma-not-in-infamous-because-no-one-cared-about-it/). For
inFAMOUS 2, Brian Fleming said fans found the first game's choices "too mechanical", and the
abstract "take this food or give it away" moment gave way to siding with people
(https://blog.playstation.com/2011/02/11/what-goes-around-comes-around-more-on-the-infamous-2-karma-system/);
unmarked "karmic opportunities" in the world were added
(https://www.gamedeveloper.com/business/welcome-to-new-marais-thinking-change-in-i-infamous-2-i-).
Thresholds that unlock powers made the world flip at once when crossed
(https://gamesbeat.com/ive-been-bad-now-prove-it/).

**Lesson.** Forced two-option moral moments and threshold flips were what Sucker Punch moved away
from; small acts found in the world were what they kept. Here every deed is found in the world: the
engine never stages a moral choice.

## 10. Kingdom Come: Deliverance: what the world knows

Reputation per location (12) and per group (soldiers, traders, villagers, monks), maximum 100,
traders start at 50; no per-act numbers are published
(https://kingdomcomedeliverance.wiki.gg/wiki/Reputation). Crime runs on witnesses, who remember you;
fines run 10 to 300 groschen (https://kingdomcomedeliverance.wiki.gg/wiki/Crime). Players report
reputation lost overnight after unseen killings while unseen theft costs nothing, and call it
inconsistent: a "carefully planned, isolated and remote murder can have devastating effects...
while a mass-murder in the day could go completely unnoticed"
(https://forum.kingdomcomerpg.com/t/crime-witness-mechanics-and-consequences-of-conversation/55679).
No Warhorse explanation was found.

**Lesson.** Splitting what you did from what the world knows is right; a hidden, inconsistent rule
for unseen acts reads to players as a bug. Say plainly which one a number is.

## 11. Pathfinder 1e and Owlcat's games: the book's own answers

**The Core Rulebook has no alignment mechanic.** "There's no hard and fast mechanic by which you
can measure alignment"; the GM tells the player "in a friendly manner" when they act out of
alignment (CRB p.168, https://aonprd.com/Rules.aspx?ID=115). Good implies "altruism, respect for
life, and a concern for the dignity of sentient beings"; evil, "hurting, oppressing, and killing
others" (https://legacy.aonprd.com/coreRulebook/additionalRules.html). **Nothing in the Core
Rulebook says killing evil creatures is a good act** (it simply does not address it).

**Ultimate Campaign's optional alignment track** (pp.134–137,
http://legacy.aonprd.com/ultimateCampaign/campaignSystems/alignment.html): each axis 1–9. The GM
decides whether an act "is enough to shift" the character, "and if so by how much". The book's own
examples: "executing a captured orc combatant so the PCs don't have to haul it to a distant
prison" is **1 step** toward evil; "torturing a hostage for information" **2 steps**; an extreme
deliberate act ("burning down an orphanage full of children") moves the character straight into
that alignment. **"For minor infractions, the GM can just issue a warning"**: the book's zero.
Crossing into a new alignment costs −1 on attacks, saves and checks for a week. No frequency
limit, and no rule for accidents.

**Intent is priced.** Atonement (CRB p.245, https://www.aonprd.com/SpellDisplay.aspx?ItemName=Atonement):
unwitting or compelled misdeeds cost nothing extra; for deliberate ones the caster spends 2,500 gp
on incense and offerings; the subject must be "truly repentant". The paladin falls if she
"ever willingly commits an evil act" (https://www.aonprd.com/ClassDisplay.aspx?ItemName=Paladin):
the trigger is the will, not the outcome.

**A pattern, not one act.** The [evil] spell sidebar (on d20pfsrd attributed to PZO1135; not
checked on Archives of Nethys): "Casting an evil spell is an evil act, but for most characters
simply casting such a spell once isn't enough to change her alignment"; only "a truly abhorrent
act" or "a pattern ... over a long period" changes it, and "the same advice applies" to the other
descriptors (https://www.d20pfsrd.com/magic/).

**Owlcat (Kingmaker, Wrath).** Every shift goes through `UnitAlignment.Shift(direction, value,
provider)`; a known defect made "Good" mean Neutral Good, so a lawful good paladin who kept picking
good answers drifted out of her class (https://github.com/RealityMachina/FixAlignmentShifts: "taking
a (Good) option shouldn't make you fail being a Paladin"). Wrath's late mythic paths set alignment
outright and can break class requirements
(https://pathfinderwrathoftherighteous.wiki.fextralife.com/Mythic_Path). **The size of a single
shift and the wheel's scale could not be confirmed**, nor any Owlcat statement on tuning.

**Lesson.** The book itself ranks acts in small integer steps (warning, 1, 2, extreme), prices
intent (unwitting free, deliberate dear), and says one act is not a character: only patterns are.
And a number that a class reads (the paladin) is where the Owlcat defect hurt: one more reason to
keep this number read by nothing.

## 12. MUDs, RimWorld, Dwarf Fortress

**DikuMUD, Merc, ROM** (alignment −1000..1000; good ≥350, evil ≤−350). The only big source of
change is the victim's alignment at the kill. DikuMUD Alfa `change_alignment`
(https://github.com/Seifert69/DikuMUD/blob/master/dm-dist-alfa/fight.c): kill something far from
you and move toward its opposite by (difference − 650)/4; kill something near your own alignment
and **your alignment halves toward 0**. Merc 2.1 `xp_compute`
(https://github.com/alexmchale/merc-mud/blob/master/src/fight.c) and ROM 2.4
(https://github.com/avinson/rom24-quickmud/blob/master/src/fight.c) scale the change by experience
and level; ROM's comment on the formula reads "improve this someday". Worn items flagged anti-good
or anti-evil zap the wearer when alignment crosses. **In the MUDs killing evil makes you good,
mechanically; Pathfinder says no such thing.** (No sourced complaint about alignment grinding was
found.)

**RimWorld** (https://rimworldwiki.com/wiki/Thoughts; source via
https://github.com/Chillu1/RimWorldDecompiled): every remembered act has a mood value, a duration,
a stack limit and a **stack multiplier of 0.75**: the first instance counts 1, the second 0.75,
the third 0.5625 (`ThoughtHandler.MoodOffsetOfGroup`); when the stack is full a new instance renews
the oldest instead of adding. Justified execution −2, an execution "in cold blood" −5, I butchered
a humanlike −6, all six days. Repetition counts for less, and memory fades.

**Dwarf Fortress** adventure mode (https://dwarffortresswiki.org/index.php/Reputation, v53.16):
32 named reputation types (Hero, Murderer, Protector of the Weak, Thief...), each 0–100 with word
bands, earned when deeds are **reported or spread as rumours**: DF keeps separate named tracks of
what is known, not one signed number of what was done.

**Lesson.** The 0.75 stack is the best-documented diminishing rule; DF is the model for a future
renown system (named, spread by people), not for this number.

---

## What the sweep says to do

1. **Small integers, ranked in steps** (Ultima IV's 1–5 of 99; RDR2's −1 for petty acts; the
   book's warning / 1 step / 2 steps / extreme). No act at quest scale in the same counter
   (Fallout 3's +50 water and −1000 Megaton swamp everything small).
2. **Intent decides, in code.** Judge the fights the player started (Ultima IV), not the ones
   started against them (GTA VI's stated rule); an accident costs nothing or next to nothing (the
   book's warning and atonement's free unwitting misdeed; RDR2's complaints are what happens
   otherwise). The engine can tell aim from spill structurally (the plan's §5).
3. **Count only the player's own acts** (Fallout 2's `source_obj == dude_obj`).
4. **Gate the repeatable act per person and per day**, good and bad alike (Ultima IV's beggar was
   farmed through a time-only gate; KOTOR had no cooldown at all; Fallout 4 cools per action; the
   owner's "funny accident" argues the same for bad acts).
5. **What you did is not what the world knows.** Record witnesses, but never let them change the
   value (RDR2 honor; Fallout karma), and leave the world's knowledge to the renown system the
   owner has already ruled is a world system (New Vegas reputation, KCD, Dwarf Fortress).
6. **Show it, plainly.** Sawyer championed visible +1/−1 changes; a number with words beside it
   and the list of rows it is the sum of.
7. **Read by nothing.** Every documented failure in §7–9 and §11 (ME2 Charm, KOTOR mastery,
   inFAMOUS powers, Owlcat's paladin) came from a meter that gated something. The owner's "I dont
   want it to affect anything yet" is the one design choice the whole sweep agrees with.

## What to refuse, with reasons

- **Killing evil creatures as a good deed** (the MUD rule). Pathfinder does not say it, and New
  Vegas's director cut it from 100 to 5 because it was farmed.
- **A clamp on the total** (Ultima's 99, Fallout's ±1000). A clamped total stops being the sum of
  the rows the player can read.
- **Value scaling by position** (KOTOR). It makes the same act worth different amounts and
  explains itself to nobody; worth reconsidering only if the number ever gates something.
- **Escalation by streak** (RDR2's −5 to −10). It punishes harder exactly when a player is
  having a bad, chaotic fight: the frustration the owner named.
- **Staged two-option moral moments** (inFAMOUS 1, Mass Effect's wheel). The engine records what
  the player did in the world; it never asks them to pick a pole.
- **Witnessed-only deeds** (RDR1's bandana, KCD's hidden rule). That is renown's job.

---

## 13. Critic pass

*(Recorded below after the second pass; see the end of this file.)*
