# Naming a far town is a journey, from anywhere (2026-11-21, fix/journey-words)

The travel lane found two items live on a copy of the owner's save (Shadow, at the ruins
east of Branford on the region map's hexes).

1. "I leave the ruins and set out on the road to Brackgate" founded "the road to
   Brackgate" as a new place in the ruins: 8 minutes, and no journey. "I take the long road
   to Brackgate, a journey of days" did start the journey. No Journey chip is offered on a
   hex.
2. After a passage was booked, or after "set sail", the plan added a `travel` ashore to the
   docks. Booking took 2 turns.

## What the logs showed (travel-pacing-data, shadow.json turn_log)

- Row 224, item 1: **the reader was right.** It read `leave: the ruins` +
  `journey: Brackgate`. The fault came after that. `interpret.ops_for` maps one action at a
  time (`acts_to_ops.table`), so the leave owed a `travel` of its own. The schema then asked
  the plan for a travel. The plan wrote `found` "the road to Brackgate" (kind road, parent
  the ruins) and a travel into it. The journey ran third and was refused: "already
  travelled this turn".
- Rows 224, 234 and 245, item 2: every reading was `journey` (book passage, set sail, set
  sail). The plan added `travel` to "the docks" or "the deck" each time. The guard written
  for exactly this case (`acts_to_ops.apply`'s `journeying`, "the plan's travel struck")
  only fired for a reading `go` that owed a journey, never for a reading `journey`. So the
  walk ashore stood, took the party off the ship it had just boarded, and the sail needed
  another turn.

So neither item was a misreading. Both were ops the code added, or failed to strike,
beside a correct reading. That is why no reader demonstration was added: the reader already
reads this line correctly, and a demonstration for a line read correctly adds prompt volume
and fixes nothing.

## Sources and what each says

- **PF1e CRB, Movement > Overland** (d20pfsrd "Movement", Table: Terrain and Overland
  Movement). Overland movement is counted in hours and days, and highway, road and trackless
  ground change the speed. Local movement is counted in rounds and minutes. Two scales, two
  procedures. This is from memory of the CRB table; I did not re-fetch it this session.
- **Inform 7, Writing with Inform §7.13**
  (ganelson.github.io/inform-website/book/WI_7_13.html, fetched). `going` is between
  adjacent rooms over map connections. The page does not cover travel to a distant room by
  name.
- **Inform 7 Recipe Book, "Compassless" example** (search summary only; the example text
  was not read). `Understand "go to [any room]" as going by name`. The named trip is turned
  into ordinary going, "so normal movement rules apply". It is one command to a named
  destination, held to the same rules as a step.
- **Emily Short's Approaches extension**
  (rileypb.github.io/I7extdocs/10.1/Extensions/Emily%20Short/Approaches.html, fetched).
  "GO TO [room]" is its own action, `approaching`. It walks a route the player has already
  visited, prints the path, and stops at an obstacle. Names of unvisited rooms are
  deliberately not understood, "to protect the game's secrets". Lesson: the destination is
  matched against the world's real rooms, and a name the world does not hold is never
  invented as a room.
- **MUD clients and Aardwolf** (zuggsoft.com zMUD speedwalking help; aardwolf.com wiki
  Help/Run, fetched). `run` is a speedwalk string of the six basic directions. It "only
  works with the six basic directions", not portals or custom exits. A separate `runto
  <area>` exists for going to another area. A forum report that `run` cannot cross areas
  could not be confirmed on the help page.
- **Morrowind against Oblivion fast travel** (gamesradar "Morrowind's mass transit"; fan
  forums, which are opinion, not design statements). Morrowind's silt striders and boats
  are boarded at a fixed point, and paying is the whole trip: there is no separate walk.
  Oblivion's map travel works from anywhere outdoors. What players complained about in
  Oblivion was the loss of exploration, not the convenience. This app keeps both
  properties: a journey takes days and can be met on the road (ontheway), and it can be
  started from wherever the party stands.

## Chosen

- **A journey is the turn's one move.** When any action of the reading owes a journey,
  any travel or found owed or built beside it is dropped (`acts_to_ops.table`), and the
  plan's own travel or found is struck (`apply`'s `journeying`, now for any act). The
  engine already refused the second move; this stops it from being written. It mirrors
  Morrowind's boat, where boarding is the trip.
- **And nothing puts the walk back.** The first live replay of the booking, run after the
  strike was in, went 7 attempts out of 7 refused. The old regex backstop
  `judgement.inject_travel` adds a travel whenever the plan has none. Here it added "Back
  within Branford", and `refuse_leaving_in_place` then refused it. A plan that carries a
  journey now counts as already moving.
- **Destinations are matched against the world's real names** (`journey.named`: the
  town's name, or the road head the ring names after it, "the road to {To}" or "the way to
  {To}"). Exact equality, never a substring, and never a reading of the player's English.
  A reading `go` to a road head that no place here is called (out on a hex) owes the
  journey. `journey.find` falls back to it, so a journey "to the road to Brackgate" finds
  Brackgate. This follows Approaches: names are matched against the world's rooms.
- **The engine never mints a real far town.** `validate` refuses a `found`, or a travel to
  an unheld place, whose name is a far town or its road head. The code is `far_town`, and
  the journey op to write is named in the refusal. `_op_found` refuses the same at run time.
- **Journey chips on hexes.** In a town, the chips are the roads offered at their heads.
  On a hex, every land road is offered (`exits._rows_from`), and its time is the share of
  the road still ahead (`Engine.road_share_left`, from the travel-pacing fix). Passages are
  not offered on a hex: a ship is boarded at the docks.

## Rejected

- **A reader demonstration for "leave X and set out on the road to Y".** The reader got
  it right. See above.
- **Rewording ROADS OUT's "by sea, from the docks"**, which likely invites the plan's walk
  to the docks. Prompt wording is the fix that "failed and kept failing" (CLAUDE.md). The
  strike detects the walk mechanically, and the brief line stays true.
- **Turning a travel to a far town into a journey silently, in validation.** The house
  rule is that validators refuse with the fix named, and the reading's own journey already
  covers the typed path.
- **Substring matching ("Brack" for Brackgate)**, which `journey.find` does for the GM's
  dressing. A founded tavern named after a town would then be refused. The match is exact.

## Second pass

I re-read each claim against what was actually fetched:
- I first wrote that Aardwolf `run` "cannot cross areas". The help page does not say that;
  only a user report does. Corrected above.
- The Compassless example was seen only through a search summary, and is marked so.
- The PF1e overland table was not re-fetched this session, and is marked so. Nothing here
  depends on its numbers: the journey's arithmetic is unchanged.
- The Morrowind and Oblivion material is fan opinion and is used only as an illustration.

**Order of work, said plainly:** for item 1 the code was traced and written before the web
sweep. The sweep came after, and did not change the design.
