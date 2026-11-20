# Research notes, lane fix/hex-travel (playtest 2026-11-20 items 3, 4, 10, 11, 12, 13)

Written before the code, per the owner's instruction of 2026-11-20. Each item: the rule, how
other traditions solved it, what was chosen and what was rejected.

## Item 3: trapped in the ruins (hex move out of a site; parent loop; raw id)

**What the save shows.** `founded` in campaigns/shadow.json: the forest hex
(`~forest:@hex-m52-35`) has parent = the grassland hex, and the grassland hex has parent =
the forest hex. `_op_hex_move` set `held["parent"] = <where the party stands>` on every move,
so out to the grassland and back made a two-place loop. `places.with_founded` grafts a founded
place only when its parent is already in the set (or it IS where the party stands), so with
the party in the ruins neither hex joined the set: the hex move's first step, a `travel` up to
the forest hex, was refused "There is no <raw id> here to go to", followed by every place the
set held (the town's whole list, since a hex is filed under its nearest town).

**Sources.**
- PennMUSH `move.c` (sources.debian.org/src/pennmush/1.8.0p4-1/src/move.c/): `moveit`
  refuses a move whose destination is held by the thing moved (`recursive_member(where, what,
  0)`, commented "Don't move something into something it's holding"; "indirectly" is read
  from the function's name, its body was not seen). The containment tree is never allowed a loop.
- LambdaMOO Programmer's Manual (tecfa.unige.ch/guides/MOO/ProgMan/ProgrammersManual_48.html):
  `move()` raises `E_RECMOVE`, "recursive move", when the move would make a containment loop.
  The server source line was not checked.
- Evennia issue 454 (code.google.com/archive/p/evennia/issues/454), "Prevent location or
  destination=self" (2014): a request to check nesting before a location is set. (An earlier
  draft of this note said it recorded a regression; a critic pass found no such text.)
- Ultimate Campaign, Exploration (legacy.aonprd.com/ultimateCampaign/campaignSystems/
  exploration.html): a hex is a fixed cell of the map; travel from hex to hex is costed by
  terrain. My inference, not the rule's words: nothing in it makes "the way back" a property
  of the hex; the hex map, not a parent chain, joins hexes.

**Chosen.** (1) The guard every MUD tradition has: a hex is never re-parented under a place
that already descends from it (the cycle check, PennMUSH's shape). (2) `with_founded` also
grafts every place up the founded parent chain from where the party stands (cycle-safe),
so the way up out of a site is always there: the hex a site opens off is reachable from inside
it whatever the hex's own parent says. (3) A load-time repair: a founded parent loop is cut at
its oldest member (first in `founded`), whose parent is cleared; the chain repair in (2) keeps
it reachable from below. (4) The travel refusal names a place by its name, never its id, and
its list is the short "next door first" list `_where_to` already builds (exits of where the
party stands, then the way out, capped at eight), not the whole set.

**Added after the first live check.** With the hex reachable, "I leave the ruins" was then
planned as a travel to Branford's outskirts and walked twelve miles in "a few minutes' walk":
a hex was filed under its town, so the town's whole set was one step from it. Standing in a
hex of open ground (not a town's own hex) or in its site, the set is now that hex and what
hangs off it (`places._out_in_a_hex`); the town is at another scale, reached by the map's
move, which is where Ultima VI-era overworlds and the `outskirts.py` note already put it.
A second live run planned "I leave the ruins" as travels to the gate and the courtyard (the
place enum rides in a `contains` Ollama does not enforce, memory ollama-schema-enforcement);
the reading said leaving the venture and there is one way out, so `judgement.
out_of_the_venture` rewrites those travels to it. The third live run walked out to the hex.

**Rejected.** Never re-parenting at all: a hex last founded from another town's ground would
then not be in the set when the party stands beside it (the reason the re-parent was written).
Grafting every founded hex onto every set: the set is the planner's choice list, and the code
says why it is kept small ("what keeps the model's choice small"). A repair that rebuilds the
whole hex chain from the map: more code for no case the cut does not already cover.

## Item 4: the move narration

**Sources.**
- The Alexandrian, "Hexcrawl Addendum: Describing Travel" (thealexandrian.net/wordpress/51221/):
  the two failures are long-and-boring and short-and-boring; describe one vector up to the next
  interruption (a landmark, a destination, an encounter, the end of the day); build it as
  foundation (terrain, distance, time), then landmarks in order, then a little unkeyed detail,
  then frame the endpoint (the page's "You've reached [location]... now what"). The end of a watch is called a
  trap as a stopping point.
- The Alexandrian, "Hexcrawl Part 2: Wilderness Travel" (thealexandrian.net/wordpress/17333/):
  a visible location is spotted automatically on entering the hex; hidden ones need a check;
  checks are once per watch (the page does not define the watch's length).
- Ultimate Campaign, Exploration: 5 hours a hex on plains and 8 elsewhere at speed 30;
  landmarks are revealed on entering the hex.
- Forbidden Lands, travel (secondary summaries only; the rulebook itself was not reachable:
  docs.google.com handout and scribd "Journeys handout"): the day is four quarter days; one
  traveller leads the way and one keeps watch, and the roll is reported as the result of that
  role. I could not confirm the exact wording from the primary book.
- The One Ring 2e (reviews at gamingtrend.com and enworld.org, not the rulebook): a journey is
  one sequence; events interrupt it and cost fatigue; reviewers say the book gives little
  flavour text for describing events. Not primary; used only for "the journey is one thing,
  told once, with its cost".
- The Angry GM, "The Power of Editing" (theangrygm.com/the-power-of-editing/): the GM edits
  hours of travel down to what matters and ends the day on the decision (make camp?).
- inkle's 80 Days postmortem (gamedeveloper.com/business/postmortem-inkle-s-i-80-days-i-): the
  journey tracked only a few core stats (money, health, time) across legs; early builds felt
  like "the travelling itself feeling like a chore" when the text got in the way.

**What the 0.4.4 page did against that.** The consequence block was the travel tell (place
doc, "You are at X now. X: Open forest, 12 miles east of Branford, in Faerholt March.") plus
the hex's own lines: the doc is the long-and-boring failure, the "in Faerholt March" in it is
what the narrator took as the forest's name, the bare "(27)" is a number not shown as a roll,
the re-said "broken walls show here" on the walk back repeats a landmark already found, and
there is no endpoint.

**Chosen.** The hex step's arrival sentences from `travel` (the ground change, "You are at",
the place doc, "It takes") are not said for a hex step; `hex_move` says its own, in the
Alexandrian's order: foundation (hours, ground, bearing, the part of the day set out in and
stopped in, from the clock: `residency.day_part`), the cost (the body toll line that exists),
the landmarks (only sites seen for the first time; a site already found in the hex you stop in
is said once more briefly because it is where the player can go in), with the Perception roll
shown the way every other roll is shown ("Perception d20 12+15 = 27"). The endpoint is the
hand-back question the spoken turn always ends with, added when the closing lacks one. What
passes on the road (meetings, escorts left behind) still comes from `travel`, untouched.

**Rejected.** Weather, light and food lines written into the tell: the engine has no standing
weather (only the road's weather meeting) and the narrator may not author state (law 3); the
body toll already says what hunger and fatigue cost. Per-watch narration (one beat a watch):
the Alexandrian calls the watch boundary a trap. Asking the model to "describe the day": the
CLAUDE.md lesson is that instruction loses to the material in the feed, so the material is
what changed.

## Item 10: "2 hours away" on entering the site in your own hex

**Sources.** Ultimate Campaign, Exploration: travel through a hex is costed per hex, and a
landmark is revealed on entering it. That reaching a site inside the hex has no separate
time is my inference: the rule gives none.
The Alexandrian part 2: a keyed location is found during the watch spent in the hex.

**Chosen.** A venture whose parent is a hex place (the site in the hex you stand in) costs no
hours and says none; the hours a venture kind carries are for a site reached from a town's
ground ("a cave in the hills outside it"), where the walk out is not otherwise paid.
**Rejected.** Charging the hours and only hiding the words: the time would still pass with
nothing on the page saying why (law 3's spirit: a number nobody saw).

## Item 11: the /gm footer naming a town in the ruins

**Source.** Core Rulebook, Diplomacy, Gather Information (d20pfsrd.com/skills/diplomacy/):
"spend at least 1d4 hours canvassing people at local taverns, markets, and gathering places";
it can be retried. The advice the footer gives presumes people to ask.

**Chosen.** Out on a hex (or in a hex's site) "here" is not the town: the town's dossier is
not handed in as the default grounding of a question that names nothing, so its withheld
facts are not counted and the town's footer is not printed. A question that names the town
still finds it through the world search. **Rejected.** Rewording the footer for every kind of
place: there is no fact store for a ruin to withhold from; the defect is the town's facts
answering for the ruins.

## Item 12: broken gathering templates

**Sources.** Inform 7 manual §3.18 "Articles and proper names"
(ganelson.github.io/inform-website/book/WI_3_18.html): a thing's printed name is used with
articles the system supplies, and a proper-named thing takes none (the section does not
discuss capitals). NetHack's objnam.c header (nethack.fandom.com/wiki/Source:Objnam.c) says
it puts articles in front of names and makes plurals; the helper bodies were not checked.

**Chosen.** "there are no stones for foci in barrows, battlefields and cursed ground" used a
ground's DESCRIPTION as a place name: say the place the party stands in instead ("the ruins
hold no stones for foci to find", which also avoids is/are on mass nouns like "ore"). The
spoiled-hour line pasted a capitalised item name ("Water") mid-sentence: it now reads "the
water was spoiled in the getting", lower-cased with an article, one template for both
branches. #127 ("collecting six the stranger from its remains") is the model's sentence over
an engine tell; traced below in the report from the save's turn log.

## Item 13: "the two pyraustas at the forest's edge"

**Finding.** Not invented by the narrator: the save's turn log for that walk holds the engine's
own passed meeting, "At the woods, two pyraustas are near the way; they let you pass"
(`passed_meetings: [{"at": "the woods", "kind": "creature"}]`). The pyrausta is a real
Pathfinder creature (aonprd.com MonsterDisplay "Pyrausta": Bestiary 5 p. 200, CR 1/4,
Environment "any warm", organization solitary, pair or swarm). **But** Branford's land reads
"temperate, four clear seasons, reliable rainfall" (`geography.land_around`), and the bestiary
draw (`gathering.draw_for`, `ontheway._the_land`) filters by biome only, never by climate,
though `bestiary.search` takes a `climate`. The narration is correct to the engine; the
engine's draw put a warm-only creature in a temperate wood. That climate gap is in every
wilderness draw (road, night, forage, venture, dungeon), outside this lane's hex code, and is
reported for its own lane rather than built here.

## Second pass

A critic subagent re-fetched the sources on 2026-11-20 and found four overclaims (Evennia
454, the watch's length, Inform's capitals, PennMUSH's "indirectly"); each is corrected
above. Forbidden Lands, The One Ring, the Angry GM and 80 Days were not re-checked.
