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
+1 for complimenting the Shady Sands cook, +2 for returning to Irwin, −1 for a Junktown jail fine
(−3 if you cannot pay it), +5/+10 for the large endings (https://fallout.wiki/wiki/Karma_(Fallout)).

**A second track for who knows.** Town reputation is per town and separate from karma: killing a
good NPC −5, a child −8, an evil NPC +2 (`REP_TOWN_KILL_*` in `REPPOINT.H`; the Town reputation
page gives only the tiers); tiers Idolized 30+ down to Vilified −30
(https://fallout.wiki/wiki/Town_reputation).

**Reputation titles are ratios over kill counters, not sums of karma** (`REPPOINT.H`): Champion
needs at least 25 kills with evil kills over 3× good kills and no Childkiller; Berserker needs good
kills over 2× evil kills. In the **original Fallout** (not Fallout 2) Berserker was broken: its
effect is better reactions from bad characters and worse from good ones, but "no characters are
actually flagged as bad ones, meaning reactions are decreased for all NPCs"
(https://fallout.wiki/wiki/Berserker): the defect was in the data that said who was bad, not in
the numbers.

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
penalty ("by default, no Karma is lost for killing Good/Very Good characters"), and the page's
notes give letting a follower make the kill as a way round the penalty (same page). **Witnesses:** none for karma;
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
points; **it has witness rules**: being caught stealing (−2 each) and killing a faction member
openly (−30 each) move it, a one-hit kill with a silent weapon from hiding does not
(https://fallout.wiki/wiki/Reputation_(Fallout:_New_Vegas)).

**The director, in his own words.** Josh Sawyer: karma "has very little effect. It's mostly just
there for player feedback, a stat like 'Number of Corpses Eaten'"
(https://fallout.wiki/wiki/Fallout:_New_Vegas_developer_statements/Joshua_Sawyer_Formspring_posts/2011),
and later, "the Karma system was vestigial in New Vegas. If we're trying to encourage players to
form their own opinions about factions and individuals, having a design layer that assigns
(essentially) alignment is weird"
(https://fallout.wiki/wiki/Fallout:_New_Vegas_developer_statements/Factions). After his GDC 2012
talk he clarified: "When I was discussing karma/reputation displays of +1/-1, I wasn't championing
karma systems, but I was championing visible changes in the GUI for all of what I call 'Indirect
Reaction Systems' (e.g. karma, reputation, influence, etc.). I think mechanical clarity is more
important than immersion"
(https://fallout.wiki/wiki/Fallout:_New_Vegas_Developer_Statements/Interviews/Choice_Architecture,_Player_Expression,_and_Narrative_Design_in_Fallout:_New_Vegas).

**What he retuned himself** (his JSawyer mod changelog, 10.9.2011 and 12.26.2011,
https://gist.github.com/dbb/3748244): "fKarmaModKillingEvilActor from 100 to 5" **and, in the
same entry, "fKarmaModKillingVeryEvilActor from 2 to 30"**, so killing the very evil was raised,
not cut, and the pair now rises with how evil the victim is; "All (known) Feral Ghouls set to
Neutral alignment"; a dozen named NPCs and groups given Good or Evil alignments where they had
been Neutral; and "Set all Powder Ganger factions to Evil to prevent karma loss for stealing from
them". **Only the Powder Ganger line states a reason.** Why the kill values were rebalanced, and
whether ghouls were being farmed, the changelog does not say.

**Lesson.** The director kept killing evil as a karma gain and rebalanced it by how evil the
victim was; most of his retuning was relabelling who is good and who is evil, which is the same
place Fallout 1's Berserker broke. Who-saw-it belongs on a separate, witnessed track. Visible
+1/−1 changes are good feedback, and he said so while saying he was not championing karma.

## 4. Fallout 4: karma dropped, companion affinity kept

**No developer explanation for dropping karma was found** in anything reachable (Todd Howard,
Pagliarulo, The Making of Fallout 4 statements page); only player speculation exists. It is not
claimed here that Bethesda said why.

**Affinity numbers** (https://fallout.wiki/wiki/Affinity): up to 1100 from 0 (the −1000 floor
could not be confirmed); loved +35, liked
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
good creature go Compassion/Justice +1. Cheating the blind reagent seller is reported as ten each
of Honesty, Justice and Honor
(https://bumbershootsoft.wordpress.com/2017/09/29/hacking-the-virtues-becoming-the-avatar-in-five-easy-steps/),
but xu4 compiles that case out (`#if 0`) with the comment "This doesn't match the penalty in
U4DOS, which is based on price": the −10 is **disputed**.

**Intent.** The only bad-faith signal is **who attacked first**: the penalty fires when you start
the fight with a good creature or a person not set to attack you; if they attack you, killing them
costs nothing (https://wiki.ultimacodex.com/wiki/Virtues_in_Ultima_IV).

**Anti-grinding.** `virtueIncreaseTimeout()` lets a timed gain count only once per 16-move block,
and the block is **one shared window** (`saveGame->lastvirtue`), not one per kind of act. **Only
three gains are timed**: giving to a beggar (+2), a humble answer (+10), and Hawkwind or
meditation (+3). The other gains (killing evil, sparing a good creature, finding an item,
destroying the skull) are untimed, and **no penalty is ever timed**. It still leaked: "it's
possible to, say, raise Compassion to Avatar level just by giving over and over to the same beggar
in the same town" (https://www.filfre.net/2014/07/ultima-iv/). **Witnesses:** none; the numbers
were hidden, Hawkwind describes progress "in vague generalities" (Maher's description, not
Garriott's).

**Why it exists.** Garriott built it after Ultima III fan letters which, in Maher's summary (not
the fans' words), entailed "lots of murdering, stealing, and all-around reprehensible behavior".
Garriott, as Maher quotes him without naming the original source: "If someone spends 100 hours
playing my game, I have 100 hours of the input that makes that person what they are"
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
safe −20, desecrating the dead −10; disarming a duellist +10, donating to camp +10. (Helping in a
chance encounter at +5 to +10, and a greeting bump about every third person, are **unsourced**:
the guide says helping strangers raises honor but gives no number.) Killing an innocent −5,
"ramps up to −10" in a killing streak **(excerpt)**: escalation for a pattern, not diminishing
returns.

**Witnesses.** In RDR2 "bandanas or masks have no effect on" honor; in RDR1 "when our face is
covered, all the actions we perform, positive or negative - do not affect our level of honor"
(https://www.gamepressure.com/newsroom/these-rdr2-mechanic-worked-much-better-in-first-game/z74676).
Witnesses drive the separate wanted and bounty system (same article; the Red Dead Fandom
"Eyewitness" page **(excerpt)**). That RDR2 honor needs no witness at all is consistent with
these sources but was not found stated outright.

**Accidents: no forgiveness rule, and the complaints that follow.** Steam threads report honor
lost for an NPC shot by accident while hunting, a dog that ran into a trotting horse scored as
animal cruelty, self-defence costing honor, and "abandonment" when the game would not let a player
carry both a pelt and an injured stranger
(https://steamcommunity.com/app/1174180/discussions/0/1735508653171835990,
https://steamcommunity.com/app/1174180/discussions/0/4297070247695565768). These are exactly the
owner's "funny accident to a source of frustration".

**What Rockstar says now.** Rob Nelson (Rockstar North) on GTA VI's Criminal Profile, as Inven
reports IGN's interview (2026-10-07,
https://www.invenglobal.com/articles/26913/gta-6-full-interview-with-rockstars-rob-nelson-reveals-new-details).
In Nelson's own words: "There isn't a right or wrong way to play this game, but consistent sorts of
actions may have an impact in terms of how the world reacts to you and how the narrative plays
out." The rest is **Inven's paraphrase**, not his words: the profile is different from RDR2's
honour system; doing what a mission demands, or dealing with someone who picks a fight, does not
count against the player; it shifts only when players consistently go beyond what is necessary.
He did **not** say honor was abandoned.

**RDR1** (https://www.ireddead.com/rdr/guides/honor-rankings): defend a stagecoach +400, help a
stranger +50 (only if nobody is killed), kill an outlaw +10; kill a civilian −50, crack a safe
−100, bribe a lawman −400, or −1000 with a bounty of $500 or more. (The −1000..+1000 range is
**unconfirmed**: the guide gives seven ranks but no endpoints.) Large values throughout: RDR2
shrank the petty end to −1.

**Lesson.** Self-judged deeds with no intent check produced the accident complaints. The newest
Rockstar design, as reported, exempts self-defence and what the situation demands.

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
A BioWare cinematic designer, John Ebenger, later tweeted that "something like" 92% of players were
Paragon, and allowed in replies that the figure may date from near release, before second
playthroughs (https://www.kitguru.net/gaming/matthew-wilson/over-90-percent-of-mass-effect-players-chose-the-paragon-path/,
reporting the tweet; the tweet itself was not fetched).

**Critique.** The meter cannot read motive: "I've killed thousands of people, but I wasn't RUDE to
any of them, so I can't intimidate this guy" (https://www.shamusyoung.com/twentysidedtale/?p=28160,
written about ME1).
No BioWare statement on why ME1 used two meters rather than one slider was found.

**Lesson.** Once a meter gates anything, players optimise toward one pole; BioWare's first fix was
to sum the sides and its last was to delete the meter. A display-only number avoids the cause.

## 8. Knights of the Old Republic: value depends on where you already stand

0 to 100 from 50. The value of a deed depends on the current position: a "high light" deed is +1
for a very-light character and +10 for a very-dark one, and the mirror for dark deeds
(https://www.gamebanshee.com/starwarskotorii/alignmentcharts.php, KOTOR II's chart). KOTOR 1
scales the same way (the scaling lives in `UT_AdjustCharacterAlignment`, and the K1 manual prints
a table of it:
https://deadlystream.com/topic/5037-how-do-the-dark-side-and-light-point-values-work/), but **K1's
actual values are unconfirmed**; the thread gives no numbers. Mastery at an extreme gave cheaper
powers (the KOTOR II chart page), and a blogger summarising Kotaku's Q&A with Chris Avellone
writes that "the morality system rewards only going strongly lightside or darkside" as **"one of
my big problems with the KOTOR games"**: the words are the blogger's, not Avellone's, and what
Avellone himself said was not found
(https://jedibyknight.com/2015/04/25/qa-with-kotor-ii-lead-writer-chris-avellone/). Repeatable
dialogue with no cooldown (bribing Roland Wann over and over) farmed dark points without limit
(https://www.gamebanshee.com/starwarskotor/strategies/lotsofdarkpoints.php).

**Lesson.** Rewards at the poles push players to the poles. Without a per-act cooldown, repeatable
acts are farmed.

## 9. inFAMOUS: the middle abandoned, the mechanical choice abandoned

Nate Fox on neutral karma: "We had [neutral karma] initially, but we found that people wanted to be
really good or really evil. No one cared about the middle"
(https://www.destructoid.com/neutral-karma-not-in-infamous-because-no-one-cared-about-it/). For
inFAMOUS 2, Brian Fleming said fans found the first game's choices "too mechanical", and the
abstract "should we take this food or give it away?" question gave way to choosing an ally
(https://blog.playstation.com/2011/02/11/what-goes-around-comes-around-more-on-the-infamous-2-karma-system/).
Nate Fox on inFAMOUS 2: "all around the world we put in these karmic opportunities. Things that,
you can completely ignore them when you play the game"
(https://www.gamedeveloper.com/business/welcome-to-new-marais-thinking-change-in-i-infamous-2-i-;
whether they were new in 2 or carried over from 1 is not said there). A critic, not a developer,
observes that "crowd interaction changed the moment the point threshold broke"
(https://gamesbeat.com/ive-been-bad-now-prove-it/).

**Lesson.** The middle and the abstract two-option moral moment were what Sucker Punch moved away
from; small, ignorable acts placed in the world were what inFAMOUS 2 offered. (Threshold flips
are a critic's complaint, and by that critic's account inFAMOUS 2 kept them.) Here every deed is found in the world: the
engine never stages a moral choice.

## 10. Kingdom Come: Deliverance: what the world knows

Reputation per location (12) and per group (soldiers, traders, villagers, quarrymen, monks),
maximum 100, each trader starts at 50; no per-act numbers are published
(https://kingdomcomedeliverance.wiki.gg/wiki/Reputation). Crime runs on witnesses, who remember you;
fines run 10 to 300 groschen (https://kingdomcomedeliverance.wiki.gg/wiki/Crime). One forum poster
(others in the thread agree) reports being treated as a criminal "the following morning" after an
unwitnessed killing, while unwitnessed robbery, murder and theft at other times cost nothing, and
calls it inconsistent: "the carefully planned, isolated and remote murder can have devastating
effects on your reputation and treatment in remote places while a mass-murder in the day could go
completely unnoticed"
(https://forum.kingdomcomerpg.com/t/crime-witness-mechanics-and-consequences-of-conversation/55679).
No Warhorse reply is in the thread, and no Warhorse explanation was found.

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
prison" is **1 step** toward evil; "torturing a hostage for information" **2 steps**; "Extreme,
deliberate acts, such as burning down an orphanage full of children just for the fun of it,
should push the character fully into that alignment, regardless of the character's original
position" (the book's own example carries its motive). **"For minor infractions, the GM can just issue a warning"**: the book's zero.
Crossing into a new alignment costs −1 on attacks, saves and checks for a week. No frequency
limit, and no rule for accidents.

**Intent is priced.** Atonement (CRB p.245, https://www.aonprd.com/SpellDisplay.aspx?ItemName=Atonement):
"If the atoning creature committed the evil act unwittingly or under some form of compulsion,
atonement operates normally at no cost to you"; for deliberate misdeeds the caster must "expend
2,500 gp in rare incense and offerings"; the subject must be "truly repentant". **An unwitting
misdeed still needs the spell**: it is cheaper, not free. The paladin falls if she
"ever willingly commits an evil act" (https://www.aonprd.com/ClassDisplay.aspx?ItemName=Paladin):
the trigger is the will, not the outcome.

**A pattern, not one act, and a short one.** The [evil] spell sidebar is **Horror Adventures**
(PZO1135, 2016), reproduced at https://www.d20pfsrd.com/magic/ (not checked on Archives of
Nethys): "Casting an evil spell is an evil act, but for most characters simply casting such a
spell once isn't enough to change her alignment"; it changes only for "a truly abhorrent act" or a
pattern of evil castings over a long period. And it puts numbers on the pattern: "typically
casting two evil spells is enough to turn a good creature nongood, and three or more evil spells
move the caster from nongood to evil", and "the greater the amount of time between castings, the
less likely alignment will change". The book says the advice also applies to spells with the
other alignment descriptors (paraphrased; the earlier wording "the same advice applies" is not
verbatim). Sacrificing a sentient creature makes the caster evil in almost every circumstance
(first critic pass; see §13).

**Owlcat (Wrath of the Righteous).** Dialogue shifts go through `UnitAlignment.Shift(direction,
value, provider)` (the method a fan mod patches; that *every* shift goes through it is not
confirmed). A purely Good option shifts in the plain "Good" direction, which pulls a Lawful or
Chaotic Good character toward Neutral Good, so a paladin who kept picking good answers risked
leaving her class, in the mod author's account
(https://github.com/RealityMachina/FixAlignmentShifts: "Because taking a (Good) option shouldn't
make you fail being a Paladin"; the mod rewrites the direction to the character's own Lawful or
Chaotic Good. It targets Wrath; whether Kingmaker behaves the same is unconfirmed, and no Owlcat
statement calling it a defect was found). Wrath's mythic paths force an
alignment and can break class requirements: "being a Lawful Evil Monk and choosing Gold Dragon
will force you into Neutral Good, which in turn will prevent class progression"
(https://pathfinderwrathoftherighteous.wiki.fextralife.com/Mythic_Path). **The size of a single
shift and the wheel's scale could not be confirmed**, nor any Owlcat statement on tuning.

**Lesson.** The book itself ranks acts in small integer steps (warning, 1, 2, extreme), prices
intent (unwitting cheap, deliberate dear), and says one act is not a character: two or three acts
make a pattern, and time between them counts against it. And a number that a class reads (the
paladin) is where the Wrath complaint hurt: one more reason to keep this number read by nothing.

## 12. MUDs, RimWorld, Dwarf Fortress

**DikuMUD, Merc, ROM** (alignment −1000..1000; good ≥350, evil ≤−350). The only big source of
change is the victim's alignment at the kill. DikuMUD Alfa `change_alignment`
(https://github.com/Seifert69/DikuMUD/blob/master/dm-dist-alfa/fight.c): kill something far from
you and move toward its opposite by (difference − 650)/4; kill something near your own alignment
and **your alignment halves toward 0**. Merc 2.1 `xp_compute`
(https://github.com/alexmchale/merc-mud/blob/master/src/fight.c) keeps a fixed rule ((difference −
500)/4, or a quarter of the way back toward 0); only ROM 2.4
(https://github.com/avinson/rom24-quickmud/blob/master/src/fight.c) scales the change by experience
and level, and its comment on the near-alignment branch reads "improve this someday". ROM also
takes 1 point of alignment per hit with a vampiric weapon: the one small per-act cost found. Worn
items flagged anti-good or anti-evil zap the wearer ("You are zapped by $p", ROM `fight.c`). **In the MUDs killing evil makes you good,
mechanically; Pathfinder says no such thing.** (No sourced complaint about alignment grinding was
found.)

**RimWorld** (https://rimworldwiki.com/wiki/Thoughts; source via
https://github.com/Chillu1/RimWorldDecompiled): every remembered act has a mood value, a duration,
a stack limit and a **stack multiplier of 0.75**: the first instance counts 1, the second 0.75,
the third 0.5625 (`ThoughtHandler.MoodOffsetOfGroup`); when the stack is full a new instance renews
the oldest instead of adding. Justified execution −2, an execution "in cold blood" −5, I butchered
a humanlike −6, all six days. These are the moods of colonists who learn of the act, not a score
on the actor. Repetition counts for less, and memory fades.

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
   started against them (GTA VI's rule as reported); an accident costs nothing or next to nothing
   (the book's warning, and atonement's unwitting misdeed, which still needs the spell but not the
   2,500 gp; RDR2's complaints are what happens otherwise). The engine can tell aim from spill structurally (the plan's §5).
3. **Count only the player's own acts** (Fallout 2's `source_obj == dude_obj`).
4. **Gate the repeatable act per person and per day**, good and bad alike (Ultima IV's beggar was
   farmed through one shared time-only gate; KOTOR had no cooldown at all; Fallout 4 cools per
   action; Horror Adventures says the time between evil castings counts; the owner's "funny
   accident" argues the same for bad acts).
5. **What you did is not what the world knows.** Record witnesses, but never let them change the
   value (RDR2 honor; Fallout karma), and leave the world's knowledge to the renown system the
   owner has already ruled is a world system (New Vegas reputation, KCD, Dwarf Fortress).
6. **Show it, plainly.** Sawyer championed visible +1/−1 changes (while saying he was not
   championing karma itself); a number with words beside it and the list of rows it is the sum of.
7. **Read by nothing.** The gating failures in §7, §8 and §11 (ME2's Charm options, KOTOR's
   mastery, Wrath's paladin drift) came from a meter that something read. The others had other
   causes: inFAMOUS's were staged choices and a middle nobody played; KOTOR's Roland Wann farm was
   a missing cooldown. The owner's "I dont want it to affect anything yet" removes the first cause
   outright; the day gate (item 4) and found-in-the-world deeds answer the others.

## What to refuse, with reasons

- **Killing evil creatures as a good deed** (the MUD rule, and Fallout's: +5 in Fallout 2, and
  still +5 / +30 after Sawyer's retune). Pathfinder does not say it, and it would make every fight
  a source of points, which no small-values design survives. (The earlier claim that Sawyer cut it "because
  it was farmed" was wrong: his changelog gives no reason, and it raised the very-evil kill.)
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

**Plan changed by this pass.** `docs/deeds-plan.md` was edited in §2 (five rows), §7's spell and
accident rows, §8.5's test docstring, §13.1, §13.3 and open point 2. One conclusion lost its
evidence and was re-founded: "killing a foe is never a deed" had leaned on Sawyer cutting
killing-evil karma "because it was farmed"; his changelog gives no reason and *raised* the
very-evil kill from 2 to 30, so the row now rests on the book's silence and the MUDs and Fallout
as the counter-example. The rule itself stands. The other changes soften support without moving
a decision: an unwitting misdeed under atonement is cheap, not free (the accident row's 0 is still
the plan's own call); "every failure came from a gating meter" holds for three of the five cases,
not all; Horror Adventures adds a time-between-acts precedent that supports the day gate; Burn's
save avoids catching fire, not the damage, and borrowing save DCs as skill DCs for the skinning
round is now labelled the plan's extension.

**Method.** Two critic passes, 2026-10-08. The first re-read the primary sources for the claims
carrying the most weight (Fallout 3, New Vegas, Fallout 4, xu4, Mass Effect, inFAMOUS, the
Pathfinder books, RimWorld, the MUD sources) and edited nothing; its verdicts are applied here and
marked **P1**. The second (**P2**) checked what P1 did not, re-read the xu4, Diku, Merc and ROM
sources directly (`party.cpp` `adjustKarma`; `fight.c` in each), applied every correction to the
body, and checked the plan's §13. The Fandom wikis stayed closed (HTTP 402); strategywiki answered
403. "Confirmed" means the source was fetched and says it; "corrected" means the body text was
changed to match the source; "unconfirmed" means no fetched source says it, and the body says so.

| # | Claim (section) | Verdict | Source |
|---|---|---|---|
| 1 | FO2 karma per kill: good −10, child −15, evil +5, neutral 0 (§1) | confirmed (P1, P2) | `REPPOINT.H`, fallout.wiki |
| 2 | Karma titles at ±250/500/750/1000 (§1) | confirmed (P1, P2) | `REPPOINT.H` `KARMA_*` defines |
| 3 | FO1 quest karma: cook +1, Irwin +2, endings +5/+10 (§1) | confirmed (P2) | fallout.wiki Karma_(Fallout) |
| 4 | Junktown jail "−1 or −3" (§1) | corrected (P2): −1 per fine, −3 if you cannot pay | same |
| 5 | Town reputation −5/−8/+2 (§1) | confirmed (P1, P2); citation corrected: the numbers are `REP_TOWN_KILL_*` in `REPPOINT.H`, the Town reputation page has only the tiers | `REPPOINT.H` |
| 6 | Town tiers Idolized 30+ … Vilified −30 (§1) | confirmed (P2) | fallout.wiki Town_reputation |
| 7 | Champion / Berserker are kill ratios (§1) | confirmed (P2) | `REPPOINT.H` |
| 8 | Berserker broken (§1) | corrected (P1, P2): the original Fallout only, and the bug is in its reaction effect ("reactions are decreased for all NPCs") | fallout.wiki Berserker |
| 9 | Only `source_obj == dude_obj` counts; companions, planted explosives, super stimpak do not (§1) | confirmed (P1, P2) | `REPPOINT.H`; fallout.wiki Childkiller |
| 10 | FO3 values: theft −5 per container, terminal −5, good creature −25, non-evil −100, very evil +100, church +1/cap, water +50, Megaton +200/−1000 (§2) | confirmed (P1) | fallout.wiki Karma_(Fallout_3) |
| 11 | FO3 non-evil kills cost karma only by faction flag; followers kill penalty-free (§2) | corrected (P2): the flag rule is verbatim; "penalty-free" softened to the page's noted workaround | same |
| 12 | Pagliarulo's "black and white … really wasn't working" lines (§2) | confirmed (P1) | vagrantbard.com interview |
| 13 | The "fork" complaint (§2) | unconfirmed (as the body already said) | none found |
| 14 | NV karma: theft −5, terminal −1, non-evil creature −25 (§3) | confirmed (P1) | fallout.wiki Karma_(Fallout:_New_Vegas) |
| 15 | NV reputation bumps 1–5 map to 1/2/4/7/12; Fame and Infamy separate (§3) | confirmed (P2) | fallout.wiki Reputation_(Fallout:_New_Vegas) |
| 16 | NV witness rules, −2 / −30 "(excerpt)", "a silenced kill does not" (§3) | corrected (P1, P2): values seen on the page, "(excerpt)" dropped; the exemption is a one-hit kill with a silent weapon from hiding | same |
| 17 | Sawyer: "Number of Corpses Eaten"; "vestigial" (§3) | confirmed (P1), verbatim | fallout.wiki developer statements |
| 18 | Sawyer's GDC clarification (§3) | corrected (P1, P2): the quote dropped his "I wasn't championing karma systems" and "mechanical clarity is more important than immersion" | fallout.wiki, Choice Architecture page |
| 19 | JSawyer: KillingEvil 100→5 so ghoul farming stopped; monsters stopped counting; director made combat worthless to karma (§3, refusals) | **corrected** (P1, P2): no reason is given for 100→5; the same entry raises KillingVeryEvil 2→30; "(known)" ghouls set Neutral with no reason; only the Powder Ganger line states a reason | gist.github.com/dbb/3748244 |
| 20 | FO4 affinity: Small 0.5 / Normal 1 / Large 1.5; "CA_Size_Small"; same action not twice in a row; max 1100 from 0 (§4) | confirmed (P1) | fallout.wiki Affinity |
| 21 | FO4 affinity floor −1000 (§4) | unconfirmed (P1); body marked | — |
| 22 | FO4 cooldown of two game hours; no Bethesda reason for dropping karma (§4) | unconfirmed (as the body already said) | — |
| 23 | Ultima IV: start 50, +5 per gypsy answer, floor 1, cap 99 (§5) | confirmed (P1) | xu4 source |
| 24 | Ultima IV per-act values: beggar +2, chest −1 (cities), brag −5, humble +10, attack good −5, flee −2, kill evil +1 half the time, spare +1 (§5) | confirmed (P1, P2) | xu4 `party.cpp` `adjustKarma` |
| 25 | Reagent cheat −10 each (§5) | corrected (P1, P2): disputed; xu4 compiles it out with "This doesn't match the penalty in U4DOS, which is based on price" | xu4 `party.cpp` |
| 26 | "Only the good acts are timed" (§5) | **corrected** (P1, P2): only beggar, humble and Hawkwind/meditation are timed, through one shared 16-move window; other gains are untimed; penalties never timed | xu4 `party.cpp` `virtueIncreaseTimeout` |
| 27 | Penalty only for fights you start (§5) | confirmed (P2): "If they attack you, you can kill them without any loss in virtue" | wiki.ultimacodex.com Virtues_in_Ultima_IV |
| 28 | Same-beggar farming; Hawkwind "in vague generalities" (§5) | confirmed (P2) | filfre.net, Ultima IV |
| 29 | Fan letters "described" murdering and stealing (§5) | corrected (P1, P2): Maher's summary, not the fans' words | filfre.net, The Road to IV |
| 30 | Garriott's "100 hours" (§5) | confirmed as Maher's quotation (P2); Maher names no original source | same |
| 31 | Ultima V/VI one karma from 75; VII none; IX unique unrepeatable events; no reason given (§5) | confirmed (P2) | wiki.ultimacodex.com Karma |
| 32 | RDR2: 17 ranks −8..+8, ±320, 40 a rank (§6) | confirmed (P2) | newsweek.com guide |
| 33 | RDR2 per act: −1 ×3, safe −20, desecrate −10, disarm duellist +10, donate +10 (§6) | confirmed (P2) | segmentnext.com guide |
| 34 | RDR2 chance encounter +5..+10; greeting bump every third person (§6) | unconfirmed (P1, P2); body marked | the guide gives no number |
| 35 | RDR2 innocent −5 ramping to −10 (§6) | unconfirmed (excerpt, as the body already said) | — |
| 36 | RDR2 masks do not shield honor; RDR1 bandana froze it (§6) | confirmed (P2) | gamepressure.com |
| 37 | RDR2 honor moves with no witness; witnesses drive only wanted/bounty (§6) | unconfirmed as stated (P2): consistent with the sources, not said outright; body softened | gamepressure.com; Fandom "Eyewitness" (excerpt) |
| 38 | Steam accident complaints: hunting shot, dog into horse, self-defence, pelt vs stranger (§6) | confirmed (P2) | the two Steam threads |
| 39 | Nelson's GTA VI lines quoted (§6) | corrected (P1, P2): Inven's paraphrase of IGN's 2026-10-07 interview; quote marks removed; his own sentence quoted | invenglobal.com |
| 40 | RDR1 values +400/+50/+10/−50/−100/−400..−1000 (§6) | confirmed (P2), with the guide's conditions added | ireddead.com |
| 41 | RDR1 range −1000..+1000 (§6) | unconfirmed (P2); body marked | the guide gives no endpoints |
| 42 | ME1/ME2 two meters that only rise (§7) | unconfirmed (excerpt, as the body already said; search summaries agree) | — |
| 43 | Weekes on ME3 Reputation; Walters on Andromeda (§7) | confirmed (P1), verbatim | blog.bioware.com; gamingbolt.com |
| 44 | ~92% Paragon (§7) | confirmed (P2), with caveats added: John Ebenger's tweet, "something like", possibly near-release data; tweet not fetched | kitguru.net |
| 45 | Shamus Young's "RUDE" critique (§7) | corrected (P1): written about ME1, now said | shamusyoung.com |
| 46 | KOTOR II: 0–100 from 50; high light +1 very light, +10 very dark (§8) | confirmed (P2) | gamebanshee.com KOTOR II chart |
| 47 | KOTOR 1 uses the same values (§8) | unconfirmed (P2): the position scaling is confirmed for K1 (its manual prints a table), the values are not | deadlystream.com |
| 48 | Avellone: system "rewards only going strongly lightside or darkside" (§8) | **corrected** (P2): the blogger's own complaint ("one of my big problems"), not Avellone's words | jedibyknight.com |
| 49 | Roland Wann bribed or threatened over and over (§8) | confirmed (P2) | gamebanshee.com |
| 50 | Nate Fox, "No one cared about the middle" (§9) | confirmed (P1) | PlayStation.Blog, via destructoid.com |
| 51 | Fleming: choices "too mechanical"; the food example (§9) | confirmed (P1, P2) | blog.playstation.com |
| 52 | "Unmarked" karmic opportunities "were added" in inFAMOUS 2 (§9) | corrected (P2): Fox says they are placed in the world and can be ignored; "unmarked" and "added" not supported | gamedeveloper.com |
| 53 | Threshold flips; Sucker Punch moved away from them (§9) | corrected (P2): a critic's observation, and he says inFAMOUS 2 kept them | gamesbeat.com |
| 54 | KCD: 12 locations, groups, max 100, traders 50 (§10) | confirmed (P2); quarrymen added | kingdomcomedeliverance.wiki.gg |
| 55 | KCD witnesses remember; fines 10–300 groschen (§10) | confirmed (P2) | same, Crime |
| 56 | KCD "players report" overnight loss for unseen killings, unseen theft free (§10) | corrected (P2): one poster with agreement; both unseen killings and theft were sometimes free | forum.kingdomcomerpg.com |
| 57 | CRB p.168: "no hard and fast mechanic"; "in a friendly manner" (§11) | confirmed (P2) | aonprd.com Rules ID 115 |
| 58 | CRB definitions of good and evil (§11) | confirmed (P2), verbatim | legacy.aonprd.com |
| 59 | Nothing in the CRB calls killing evil good (§11) | unconfirmed (P2): the alignment pages do not; a negative across the whole book cannot be confirmed | — |
| 60 | UC track 1–9; GM decides; orc 1 step; hostage 2; orphanage; warning; −1 for a week (§11) | confirmed (P1, P2); the orphanage quote extended to "just for the fun of it" | legacy.aonprd.com ultimateCampaign |
| 61 | UC has no frequency limit and no accident rule (§11) | confirmed (P2) for the alignment page | same |
| 62 | UC pp.134–137 (§11) | unconfirmed (P2): the legacy page prints no page numbers | — |
| 63 | Atonement: unwitting misdeeds "cost nothing" (§11, synthesis) | **corrected** (P1, P2): the spell is still needed; only the 2,500 gp is waived | aonprd.com Atonement, CRB p.245 |
| 64 | Paladin falls if she "ever willingly commits an evil act" (§11) | confirmed (P2), verbatim | aonprd.com Paladin |
| 65 | The [evil] spell sidebar: source, pattern, "the same advice applies" (§11) | **corrected** (P1, P2): Horror Adventures; two castings make good nongood, three make evil, time between lowers it; the descriptor line is paraphrase | d20pfsrd.com/magic; search excerpts of the book |
| 66 | Owlcat: every shift through `UnitAlignment.Shift`; a known defect; Kingmaker and Wrath (§11) | corrected (P2): the signature is confirmed from the mod's Harmony patch; "every", "known defect" and Kingmaker are not | github.com/RealityMachina/FixAlignmentShifts |
| 67 | Wrath's mythic paths force alignment and break classes (§11) | confirmed (P2) | wrath fextralife wiki |
| 68 | Diku: (diff − 650)/4, else halve toward 0 (§12) | confirmed (P1, P2) | DikuMUD Alfa `fight.c` |
| 69 | Merc 2.1 scales by experience and level (§12) | corrected (P1, P2): fixed (diff − 500)/4; only ROM scales | merc-mud `fight.c` |
| 70 | ROM "improve this someday"; anti-good/evil zap; good ≥350, evil ≤−350 (§12) | confirmed (P1, P2); ROM's −1 per vampiric hit added | rom24-quickmud `fight.c`; merc `merc.h` |
| 71 | RimWorld 0.75 stack multiplier; full stack renews oldest (§12) | confirmed (P1) | RimWorld decompiled `ThoughtHandler` |
| 72 | RimWorld execution −2 / −5, butchered −6, six days (§12) | confirmed (P1); clarified as the moods of colonists who learn of it | rimworldwiki.com Thoughts |
| 73 | Dwarf Fortress: 32 reputations, 0–100, by report or rumour, v53.16 (§12) | confirmed (P2) | dwarffortresswiki.org Reputation |
| 74 | Synthesis 7: every failure in §7–9 and §11 came from a gating meter | **corrected** (P1, P2): true of ME2 Charm, KOTOR mastery, Wrath's paladin; inFAMOUS's were staged choices and an ignored middle; Roland Wann was a missing cooldown | the sections above |
| 75 | UW p.142 Harvesting Poisons: Survival DC 15 + CR, 10 min, surgical tools, all lost on failure, 1d3 doses on failure by 5 unless poison use; dead under 24 h; doses capped at Con mod (plan §13.1) | confirmed (P1, P2) | aonprd.com Harvesting Poisons |
| 76 | "The one 1e harvesting rule with a risk to the harvester" (plan §13.1) | corrected (P2): the one found for the dead; Milking Venom risks a bite from the living | same |
| 77 | CRB multiple doses: "This increase is cumulative"; duration by half (plan §13.1) | corrected (P2): AoN's CRB p.557 text has no such sentence, and limits contact and injury poisons to one dose at a time (UW's 1d3 overrides); d20pfsrd's differing text noted | aonprd.com Poison; d20pfsrd.com |
| 78 | UW p.162 Trophies and Treasures and MHH Harvest Parts have no hazard (plan §13.1) | confirmed (P2); Harvest Parts is a feat, MHH p.24 | aonprd.com Rules ID 2428; Harvest Parts feat |
| 79 | Burn: Reflex save at 10 + ½ racial HD + Con (plan §13.1) | corrected (P2): the damage is automatic on a hit; the save only avoids catching fire | aonprd.com UMR Burn |
| 80 | Heat: "its mere touch deals additional fire damage" (plan §13.1) | confirmed (P2) | aonprd.com UMR Heat |
| 81 | Acid 1d6 a round, 10d6 immersed; flask 1d6 (plan §13.1) | confirmed (P2); flask is UE p.107, direct hit | d20pfsrd.com environment; aonprd.com Acid |
| 82 | Poison UMR DC 10 + ½ racial HD + Con (plan §13.3) | confirmed (P2) | aonprd.com UMR Poison |
| 83 | No 1e rule speaks of a dead creature's acid or fire (plan §13.1) | unconfirmed (P2): none in the three harvesting texts; a negative across the line cannot be confirmed; plan softened | — |

**Counts.** 83 claims: **48 confirmed, 23 corrected, 12 unconfirmed.** Four of the unconfirmed
were already marked so by the research itself (the "fork" complaint, Fallout 4's cooldown and
Bethesda's reason, RDR2's −5 to −10 streak, ME's rising meters); the other eight are now marked in
the body or the plan. Six corrections are in bold: the ones that changed what a section
concluded.
