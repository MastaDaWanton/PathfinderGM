# Research, lane fix/way-forward (2026-11-25): items 5, O2, O3, O5

Playtest log: `pgm-work/playtest-2026-11-23.md`. Owner items (O*) outrank mine.

## 5 / O2: the way forward cannot be found or inspected

**What happened.** In the tower, "I search the area for the way down" was read as
`search, sought "the way down", seeking "a place"`. `Engine._sought` found no place named
"the way down", and `_player_finds` found nothing *hidden*, because the locked trapdoor had
already been found on arrival. So the tell said "does not find it here" about a trapdoor
named on arrival. In the narthex, "I look around for the different ways to go, inspecting
them" (seeking `anything`) answered the same way, in a room with three ways out. Nothing in
the engine could describe a way on at all. The only text about a door was the arrival's
"X leads to Y; it is stuck".

**The rule (PF1e).**
- Perception: "Intentionally searching for stimulus is a move action." Hearing a creature
  walk is DC 10; "Through a closed door" adds +5; distance adds +1 per 10 ft.
  https://www.d20pfsrd.com/skills/perception/
- Doors (CRB Environment, dungeons): "A closed door blocks line of sight." Good doors
  "rarely have enough of a gap for an explorer to see the area beyond"; a poor door may
  let a character "peek under or over" it at the GM's discretion. Strong wooden door:
  break DC 16 stuck, 18 locked (the strong-wooden-door stat block; the same page's Doors table gives 23/25, so the page contradicts itself; the engine keeps its existing `DOOR` numbers and this lane changes none). Picking a lock "often falls within the range of 20 to 30".
  Secret door: Perception DC 20 typical, DC 30 well hidden. https://www.d20pfsrd.com/gamemastering/environment/dungeons/
- So by the book, looking at a way on shows the door and its state. Through an open
  doorway the room beyond is in line of sight (when there is light). Through a closed door
  you see nothing, and can only listen.

**Traditions.**
- *DikuMUD and CircleMUD exits.* Every exit carries its own "general description", which
  "is only seen when a player looks in the direction of the exit" (`look north`), plus a
  door flag (none, pickable lock, unpickable lock) and keywords that `look`, `open` and
  `close` use. The door is written into both rooms. CircleMUD building manual,
  https://www.circlemud.org/cdp/building/building-3.html (flag 0 is also used for secret
  and trap doors). The original DikuMUD dbsup.doc was not read. **Taken:** a way on is something you look at, and it answers with its
  door and what is beyond it.
- *Inform 7 Exit Lister* (Eric Eve): an EXITS command and a status-line
  list. A door marked "not apparent" stays off the list until the secret exit is found.
  Eve's documentation (section 3.2) warns that in pitch darkness the lister "could potentially
  give too much information away".
  https://rileypb.github.io/I7extdocs/10.1/Extensions/Eric%20Eve/Exit%20Lister-eg1.html
  **Taken:** list only the ways the engine already shows (a hidden way down stays hidden
  until it is found). In the dark, name the ways but tell nothing of what lies beyond.
- *Graham Nelson, "A Bill of Player's Rights"* (The Craft of Adventure; date not checked), right 1:
  "a room with three exits, two of which lead to instant death and the third to treasure,
  is unreasonable without some hint." Right 8: "Not to have to type exactly the right
  verb". https://www.agiwiki.sierrahelp.com/index.php/The_Craft_of_Adventure_-_A_Bill_of_Player%27s_Rights
  **Taken:** the player gets something to choose by. "Look around for the ways to go",
  "search for the way down" and "inspect the door" all reach the same answer.
- *What was abandoned.* Old text adventures had exits that were only in the room's prose,
  or not stated at all ("guess the exit"). The Exit Lister extensions and MUD autoexits
  exist because players asked for them. I could not find a primary source saying a
  particular game *removed* listed exits, so this is reported as convention, not a
  measured abandonment.

**Chosen.** One engine answer, `dungeons.way_line`, for one way on from where the party
stands. It reads only the engine's record:
- where the way leads;
- the door and its state, with the book's way to open it;
- a found trap on it;
- whether the party has been there;
- what is in sight beyond, only through an open way and only when the searcher can see.

The answer reaches the player three ways:
- a search the reader files under the new closed `seeking: a way on` lists every way on
  from here, after the usual Perception roll. That roll still finds a hidden way down, and
  traps here and one room on.
- a search or look that names one way on answers about that way only;
- a search for a place that is not here also lists the ways on, so "the way down" read as
  `a place` still answers.

**Rejected.**
- Listening through a door for what is beyond (DC 10 +5 through a door). The rooms are
  stocked on first entry (rules/dungeons.py `arrived`), so before entry there is nobody to
  hear. Hearing them would mean stocking on inspection, which changes when encounters
  exist. That is an owner call, listed in the report.
- A keyword list of "exit words" in code. The owner ruled that models read and code
  validates. The reader names the kind (`a way on`), and code matches only names the
  engine holds (place names, door nouns, as `dungeons.shut_door_named` already does).
- Showing the room beyond a *closed* door. Ruled out by "A closed door blocks line of
  sight."

## O3: no way to reach the area 3D map in a dungeon or non-town site

**What happened.** `play/atlas.py _sites` counted a site only when its root id was
`underground:` (sewers, cellars, caves, mines). The tower on its hex is a `ruins:`
venture. The rooms under its trapdoor are founded rooms with origin `dungeon` beneath
`the-tower/`. So the tower's dungeon was never sent: measured on the owner's save,
`known_places.sites == []` while standing in the death room. The Site board, its
"Down" arrow and its crumb could not appear. The ruins, crypt and tower ventures were all
cut off the same way.

**Prior art.**
- Every Infinity Engine CRPG (Baldur's Gate and others) gives each area, dungeon level or
  building its own area map, opened from the same map button as the world map. I know this
  from play and did not source it from a primary document.
- Mudlet's mapper divides one map into areas (https://wiki.mudlet.org/w/Manual:Mapper).
  Switching between them as the player walks in is left to the game's script, so this is not
  evidence for automatic switching.
- The existing code already does this for underground sites: walking into a site opens
  the Site map (`16-tab-map.js renderBoard`).

**Chosen.** A site's root is any venture head off the land that is not town ground: an
underground place whose parent is not underground (as before), or a `venture`-origin
place whose parent is not a venture and whose ground is not urban (the rooftops and the
back alley stay on the town chart). The walk-in rule that already exists then opens the
tower's Site map, with its way down and way up, unchanged. Two strings that said
"underground" now say what is true of any site. **Rejected:** a separate "dungeon map"
button. The Site level and its crumb already exist, and a second door to the same view is
a second thing to keep in step.

## O5: a found pit trap does not show on the map

**What happened.** The search at t=231 set the room that moves' trap `found: True`, and
the arrival tell said "the party steps round a pit trap they found". But neither the
chart nor the Site board carried any trap field, so no map could show it.

**Prior art.**
- *Darkest Dungeon*: the wiki says traps on corridor tiles show on the map as a purple
  spiderweb. That scouting is what reveals them, and that only a scouted trap can be
  disarmed, come from a guide and a Steam thread that could not be re-read (not primary:
  https://twinfinite.net/guides/darkest-dungeon-disarm-traps-how/ ,
  https://darkestdungeon.wiki.gg/wiki/Dungeon_map).
- *PF1e*: a trap found by Perception is known and can then be disarmed or avoided (CRB
  Traps; the engine's `dungeons.searched`).
- *Inform 7 Exit Lister*: something not apparent until found, then shown.

**Chosen.** Knowledge only, shown once found: `dungeons.found_trap` names a found, armed
trap in a room or on its door. It rides on the room on the Site board, and on the chart's
node:
- the Site board marks the room;
- hovering the room names the trap;
- the slip says it when the room is pressed.

It is sent whether or not the room has been entered, because it was found from the next
room. An unfound trap is never sent (the fog rule: nothing unknown reaches the DOM).
**Rejected:** showing a sprung or disarmed trap. It is no longer a danger, and the arrival
tell no longer mentions it either.

## Found while verifying live (owner save, port 8972)

- **The reader often names no kind.** The owner's own #214 line, replayed, was read with
  no `seeking` at all. A search whose words name nothing on the record, with nothing hidden
  found, now also lists the ways on (seeking `anything` or `a place`). It says it "finds
  nothing here by that name", and does not claim the thing is missing.
- **The ways were told but never reached the page.** `beat_verify.found_nothing` read a
  successful search with no effect as one that found nothing. The slot was then told to
  "write it finding nothing", and it invented "hidden seams". The ways now ride as the
  act's `room_facts`, the same must-tell an arrival's trace uses.
- **"The room that moves" was cut as furniture.** `gm/checks/setting_kind.py` read "the
  room" under the open sky (these rooms are `ruins`, which is item 1, another lane's) and
  cut the sentence naming the way there. The same false alarm "repaired" the owner's t=231
  line to "the hall that moves". A cue inside a longer place name the engine holds is now
  that place's name.
