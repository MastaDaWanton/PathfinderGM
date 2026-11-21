# Research note, 2026-11-20, lane fix/battle-board

Items 8, 9, 16 and 18 of the owner's 0.4.4 playtest (pgm-work/playtest-2026-11-20.md).

## Item 8: free rotation on the 3D battle board

**What happened.** The 3D board (play/static/js/scene3d.js) turned only in four fixed
quarter-turns (`Scene3D.TURNS = 4`). The owner could not see figures standing between walls
and asked for free rotation.

**Sources.**
- XCOM 2. The unmodded game turns the camera in fixed steps on Q/E. I could not source
  the size of the step. The first mod on the XCOM 2 Nexus, *Free Camera Rotation*
  (wghost81), turns the camera freely while Q/E is held. Its own fixed step is 45° per
  press, and a 2024 Steam comment says the free mode needed `bAnalogMode=true` on a fresh
  install. Search snippets show both a fixed and a free mode, but I could not read the
  changelog (HTTP 429), so I could not confirm when the two were split.
  https://www.nexusmods.com/xcom2/mods/1 ,
  https://steamcommunity.com/sharedfiles/filedetails/changelog/616359783 . Firaxis shipped
  fixed steps, and players added free rotation with a mod. The mod kept a fixed step
  alongside it.
- Divinity: Original Sin 2. Free camera rotation, plus a hotkey that outlines characters
  through what hides them. One player (Hobocop) says the outline toggle, used together
  with "being able to rotate the camera to any angle you want", "pretty much erases
  visibility issues with models overlapping each other". The thread itself is asking for
  a first-person camera.
  https://steamcommunity.com/app/435150/discussions/0/1728701877521893679 ; Nexus script
  for tilt on the middle button: https://www.nexusmods.com/divinityoriginalsin2/mods/69 .
  Larian's own implementation of the outline is not documented: I could not source how
  it works.
- TaleSpire. A fan guide says you rotate by holding the middle button and dragging
  (https://talestavern.com/?p=7558). It is not Bouncyrock's documentation, so I could not
  confirm it.
- Foundry VTT core is a flat canvas: right-drag pans, the wheel zooms
  (https://foundryvtt.com/article/controls). A community module adds rotation in 45° steps
  (https://foundryvtt.com/packages/rotate-camera-8d).
- BEACON (itch.io; the forum page dates the thread to May 2018): the player saw their own
  silhouette through foreground terrain but not the enemies, and asked for rotation. The
  developer refused rotation as "a lot of rework" for the existing levels and promised
  enemy silhouettes instead.
  https://itch.io/t/225127/issue-enemies-and-terrain-obscured-by-high-elevation-areas-in-the-foreground-no-ability-to-rotate-camera-to-compensate . This is the one place I found rotation turned down, and the
  reason was the cost of authored levels. Our board is generated and drawn from the grid
  payload, so that cost does not apply here.
- Already in the code (scene3d.js, 2026-11-11): Baldur's Gate 3 cuts a hole round the
  character; DOS2/Torchlight 2 draw a silhouette; XCOM 2 fades walls, which players
  call unreadable. The board already draws an X-ray ghost of any figure two-thirds
  hidden, and an outline over any reachable square that is hidden.

**Chosen.** Free rotation, while the quarter-turn buttons stay (the XCOM mod keeps a fixed step
too):
- right-button drag on the board turns it (the middle button and the left drag already
  pan, and the wheel already zooms); a two-finger twist turns it on a touch screen; with
  the board focused, `Q`/`E` turn it 15°, and *Turn left / Turn right* still go to the next
  quarter-turn;
- the turn is a real angle, so `turned()` is a rotation matrix, not a loop of swaps;
- the frame (viewBox) is the box of the board's circumscribed circle, the same at every
  angle, so the board does not grow and shrink while it turns. At a quarter-turn a square
  board's box is exactly the old one, because the diamond's width is its diagonal;
- the hidden-figure ghost and hidden-square outline already work at any angle (they are
  measured from the projected faces after the sort), so nothing new was needed for them.

**Rejected.**
- *Keeping only the four quarter-turns.* The old comment cited XCOM's legibility worry.
  But the owner asked for free rotation, and the XCOM modding record shows players wanted
  it. The snap stays as the buttons' behaviour.
- *Fading or cutting away walls near the camera.* XCOM 2's translucent walls are the thing
  the 2026-11-11 work replaced, because players could not read them. A cut-away hole
  (BG3) needs a depth buffer, which this painter's-sort SVG does not have.
- *Rewriting the board in Three.js* (it is vendored for the Places tabletop). That is a
  rewrite of a renderer that works, and free rotation does not need it.

## Item 9: squares named like the board names them

**What happened.** The staged move chip said "Move to 4,5", and the transcript said
"move to (4,5)". The board prints squares as letter-number, like E6 (`sqName`).

**Sources.** Chess algebraic notation (file letter plus rank number) is the old tradition
of naming a square so it can be said aloud. Roll20 users asked for edge coordinates on
square grids the way hex grids have labels
(https://app.roll20.net/forum/permalink/2652871). This is a forum request, not a Roll20
feature. The owner's own ruling (2026-11-12, quoted in rules/fixtures.py `square_said`)
put the coordinates on the map "so that the user can be precise about where he wants to
stand". No PF1e rule governs how squares are named.

**Chosen.** The board's own name everywhere the player reads a square: `sqName` in the
plan chip, the said line, the reach warning and the flask-aim tooltip, and
`fixtures.square_name` in the server's person-voice refusals (the engine's "Click square"
and the combat panel's own reach and coup-de-grâce refusals) and the blood-pool tell.
The model-voice refusal keeps `[x, y]`, because it is a JSON op for a model, not a page
line. Checked: `combat_act` never reads the label for a square. The square travels in
`params.square`; the label goes only to the transcript, the thread and the narrator.
`square_said` reads only spoken turns (gm/acts_to_ops.py, gm/interpret.py).

**Rejected.** Writing both forms ("E6 (4,5)"). That shows two coordinate systems on one
page.

## Item 16: fight text defects

**(a) The distance said twice** (#71, "It stops twenty feet away from you... The ghoran is
still 20 feet from you."). The closing-claimed backstop (gm/checks/closing_claimed.py) cut
the sentence that had the creature reach the player, then added the engine's distance
without checking whether the kept text already said it. **Chosen:** add the line only when
the kept text does not already give that distance in feet, as digits or as the number word
(`rules/words.number`). This checks the narration against the engine's own number. It does
not read the player's English. *Rejected:* dropping the backstop line, which would leave a
beat with nothing about the distance once the false sentence is cut.

**(b) "The second lizard moves to near"** (#107). This came from the engine's own NPC move
tell, `f"{actor.name} moves to {zone}"`. A zone is an internal distance band. The PC's
version was already changed (2026-11-12) because the zone words were read as "near
somebody". **Chosen:** say the feet walked, then how far that leaves them from the player,
in feet ("moves 15 ft and is 10 ft from Shadow"). This is the same shape as
`_toward_tell`. The zone stays on the effect record for the code that reads it.

**(c) "giant cockroach is still down, but the bleeding has stopped."** (#108). Two defects.
- Lower case: the round-top bleeding lines used the bare bestiary name. **Chosen:** the
  `_the_creature` article for a bestiary creature, as the stance tells already do.
- The stale report: the cockroach fell dying at #89. An hour of essence-gathering later, it
  was still dying, and the next fight's rounds bled it and reported it. **Rule:** CRB, Injury
  and Death: "A dying character loses 1 hit point every round. This continues until the
  character dies or becomes stable", with the DC 10 Constitution check "on all subsequent
  turns" (https://www.d20pfsrd.com/gamemastering/combat/ , Dying and Stable Characters and
  Recovery). Nothing limits this to combat. **Chosen:** the clock's one door
  (`Scene.advance`) bleeds every dying non-player by the stretch's rounds out of a fight,
  through the same `Actor.bleed_out` the rounds use. It stops when they stabilise or die
  and tells which (the "comes round" record beside it is the pattern). The player's own
  dying stays with play/downed.py. *Rejected:* hiding the line because the creature is not
  in this fight. A creature bleeding in the room is real, and the defect was that time had
  not touched it.

## Item 18: an attack of opportunity never named

**What happened.** At #114 the third lizard closed on Shadow, which provoked. Shadow's attack
of opportunity killed it, and the page said only "You strike the third lizard. The third
lizard is dead." The engine's tell was the bare "Shadow hits the third lizard for 16
bludgeoning", with `because: they moved out of reach` left on the record.

**Rule.** CRB: "Moving out of a threatened square usually provokes attacks of opportunity
from threatening opponents"
(https://www.d20pfsrd.com/gamemastering/combat/ , Moving).

**Traditions.** Pathfinder: Wrath of the Righteous and BG3 name attacks of opportunity
in their combat logs. The forum reports I found are about a crowded log
(https://steamcommunity.com/app/1184370/discussions/0/3758852249520589072), and I could
not source the exact log wording. In MUDs the flee attack is its own message, but I could
not find the CircleMUD source line, so that is unsourced.

**Chosen.** The attack tell for a reaction (`params.reaction`) begins by saying what it is:
"Shadow takes an attack of opportunity on the third lizard: ..." The narrator is fed tells
only (law three), so naming it in the tell is the one place that reaches the page, both
through the narrator and through the blow backstop that writes the tell itself. The tell
still begins with the attacker's name, which `_blows_from` reads.
*Rejected:* a separate page-only line, which would be a second channel beside the tells.

## Second pass

A critic subagent re-fetched the sources. It confirmed the three PF1e quotes word for word, and the Foundry and Roll20 claims. It corrected three things, all fixed above: the XCOM fixed step (45° is the mod's step, and the unmodded step is unsourced), the DOS2 quote (it was a misquote; Hobocop's real words are now quoted), and the BEACON URL. Still unverified: the TaleSpire binding, the date the XCOM mod split its two modes, and the exact wording of Wrath of the Righteous's attack-of-opportunity log line.
