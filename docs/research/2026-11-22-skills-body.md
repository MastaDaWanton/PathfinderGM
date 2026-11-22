# Body and movement skill uses — research note (round 2, 2026-11-22)

The lane: Acrobatics (jump, soften a fall, balance), Climb as movement, Escape Artist beyond
the grapple, Fly, Ride and mounted combat, Heal's treat poison and treat disease, and the
companions' rest. Built in `rules/bodyskills.py`, rows in `content/rules/skill-uses.json`.

## Primary text read (2026-11-22)

- d20pfsrd.com/skills/fly, /ride, /climb, /acrobatics, /heal, /escape-artist — the Core
  Rulebook's skill entries. Each row's `source` quotes what it uses.
- aonprd.com, Acrobatics (the soften-fall sentence) and Rules, Mounted Combat (CRB p.201).
- Couldn't source: the falling rules' own page (aonprd Rules ID=331 is Catching on Fire).
  `content/rules/hazards.json`'s falling row already quotes them, so I used that row.
- Couldn't source either: what a failed *balance* check does by 4 or less. In 3.5, missing
  by 4 or less meant you could not move and missing by 5 or more meant you fell. Neither
  PF1 page I read says that. They only say "falling or being knocked prone" (from the
  "damage while balancing" sentence). So any miss is a fall here (see owner calls).

## Prior art

- Owlcat's Kingmaker/WotR merged Climb and Swim into Athletics and turned jumps and climbs
  into scripted map interactions. Nobody climbs as a way of moving. Lane E's note covers
  their use categories. Their choice is a reason to keep the table's ids per use. It is
  not a reason to cut uses, because the owner chose to build Ride rather than cut it.
- Foundry PF1 has the skill rolls with no consequences. Mounted combat is a note on the
  sheet, and Mounted Combat is a feat entry the player rolls by hand. PCGen models none of
  it at play time. I could not confirm whether either one ever automated mounting and then
  dropped it.
- The engine's own precedent counted for more than either. The `hazard` op's
  "one scalar only the fiction supplies, with bounds" sets the shape for a jump's
  `distance_ft` and a drop's `height_ft`. The DC bands are the Climb table:
  0/5/10/15/20/25/30 are the same numbers.

## How each use maps to the tag framework

- Climbing: `state.position.climbing` (+ `state.exposed.climbing`, which `loses_dex_to_ac`
  already reads). A creature with a climb speed keeps its Dex. `recovery.rest` sweeps it.
- Balancing: `state.position.balancing` + `state.exposed.balancing`, lasting the round.
- Mounted: `state.position.mounted` on the rider and `state.position.ridden` on the steed.
  The rider's square is the steed's (`carry_rider`, `Scene.occupied` lets the two share).
- Behind the mount: `state.position.mount-cover`, with +4 AC. `states.BLOCKS` stops attack
  and cast.
- Treated: `care.treated.<poison|disease>` carries a +4 competence save term `when`
  `{"against": kind}`. `Actor._afflicted` rolls in that context and then spends the term.
- Tied up and manacled: the `state.held.bound[.manacles]` tags the escape reads. No condition row is added, because `CONDITIONS` holds only Appendix 2 (tests/test_reference.py), and no door lays them yet (a grapple's tie-up isn't built). A net or an entangle (`state.held.entangled`) is reachable today.
- A flier pinned by wind: `state.held.wind` for a round, refused by `_op_move`.

## Owner calls (RAW taken where nobody has ruled)

1. **Treat poison/disease on a tie fails.** The CRB says "exceeds the DC", so the check has
   to beat the DC, not equal it.
2. **One Heal check helps the next save.** RAW, the healer rolls again at every save. Here
   one made check gives +4 to the next save and is then spent.
3. **Running start.** Out of a fight, a jumper always has one. In a fight, a jumper has one
   if they already made a move this round. The 10 straight feet are not measured.
4. **A jump is capped at a double move (2 × speed) in a fight.** The CRB only says "maximum
   movement for the round".
5. **Wings.** Only a fly speed from a stat block or a people plummets on a Fly check missed
   by 5 or more. A spell or potion's flight is not wings.
6. **Any failed balance check is a fall**, into the drop if there is one, else prone.
   See "Couldn't source" above.
7. **Rope with no binder present is DC 20** (20 + a CMB of +0).
8. **Climb out of a fight rolls each quarter-speed stretch in turn.** It does not take 10.
   The book lets a climber take 10 when not threatened, and that is the player's choice
   to make.
9. **A rider moving on the mount spends the rider's move**, so the rider gets one blow
   after it, which matches the book's "If your mount moves more than 5 feet, you can only
   make a single melee attack". The difference: the book leaves the rider's own move action
   free (to spur or draw), and here it is spent.

## What does not fit the engine, said plainly

- **The mounted charge.** The engine has no charge action, so there is no charge bonus and
  no charge AC penalty for a mount either.
- **Fighting with or controlling a mount in battle** (Ride DC 10 / DC 20). A mount has no
  "frightened by combat" behaviour for control to suppress. Combat training isn't recorded
  either: `goods.deliver` drops "(combat-trained)" from the name. Not built, and the Ride
  card's `not_yet` says so.
- **Checks triggered by being hit** (staying in the saddle, the climber's and balancer's
  re-checks, a winged flier's DC 10). Each needs a hook inside the one damage funnel,
  `_apply_damage`, which every lane shares. Not built, and each card's `not_yet` names it.
- **A mount falling under its rider.** When a steed goes down, `mount_of` stops answering,
  but no soft-fall check is rolled. The soft fall is rolled when a leap throws the rider.
- **Guide with knees.** The engine doesn't model hands in a way it could enforce.
- **The jump doesn't place the body.** A made jump is a made check. On the map, the move op
  still walks the body.
- **Bareback −5.** Saddles aren't goods, so every rider is treated as having one.
