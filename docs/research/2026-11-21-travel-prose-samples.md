# Travel prose: before and after (2026-11-21)

These are real beats from the travel bench (docs/research/2026-11-21-travel-prose.md §4):

- **Before** is master 72d08db0 (0.4.8).
- **After** is feat/travel-prose.
- The forced-march night is from a scratch merge with feat/hex-travel-to's work in
  progress. The before for it is the owner's screenshot.

Each pair is the same chain and step, with the same Ollama seeds. The engine's dice can
differ between the arms, so where a pair's tells differ, it is said.

"The record" is the GM's disclosure under the beat. It is folded by default, and one
click opens it. On the after side it holds every roll, DC and figure, word for word as
the engine wrote them. The Perception roll is also in the Rolls panel.

---

## 1. A forest hex: out of the ruins (the owner's own save)

**Before.** The page showed the prose and then the pasted block:

> You emerge from the ruins and leave the clockwork spy behind in the dust. You trek for
> hours through the dense woods, the sun tracking across the sky until it begins to dip
> toward the horizon in the evening. Near the edge of the great forest, an aasimar
> appears in your path and offers a silent nod of passage before you continue your
> journey into the twilight.
>
> You come out of the ruins. Left behind: the clockwork spy. Eight hours on foot east
> through the forest, to the forest 48 miles east of Branford. You set out in the middle
> of the day and stop in the evening. At the forest 48 miles east of Branford, an aasimar
> is near the way; it lets you pass, and you walk on. Looking over the land (Perception
> d20 12+16 = 28), nothing new stands out.

**After.** This came from the live app on port 8976, with the dice popup rolled by hand.
The page showed the prose, then "The record", folded:

> You leave the ruins behind, leaving the clockwork spy in the debris. You trek east
> through the old-growth deciduous forest of the Faerholt March for eight hours, the
> dense timber of the western spine pressing in on both sides. By evening, you reach the
> woods forty-eight miles from Branford. You look over the land, but nothing new stands
> out in the gathering twilight.
>
> ▸ The record

**What changed:**

- The world's own words came in: "old-growth deciduous forest" and "the Faerholt March".
- The roll and the repeated "48 miles east of Branford" left the page.
- **A known slip remains.** "the western spine" is the world's phrase for its whole
  land ("thick forest along the western spine"), told as if it were here.

## 2. A grassland hex, a second world (Pangrella)

**Before:**

> You trek across the expanse of grass as the sun dips low, the long journey finally
> coming to a halt as the evening shadows stretch. As you scan the horizon, your eyes
> catch the jagged silhouettes of broken walls rising from the earth in the distance.
>
> Five hours on foot east through the grassland, to the grassland 24 miles east of
> Mirabalos. You set out in the evening and stop in the late evening. Looking over the
> land (Perception d20 12+4 = 16): broken walls show to the east.

**After:**

> You trek east across the Pangrellan grasslands, the long journey through Kaldrimia
> culminating in the late evening as you reach the plains twenty-four miles of
> Mirabalos. You stop as the light fades over the steppe. To the east, the jagged
> remains of broken walls emerge from the grass against the darkening horizon.

**A slip:** "twenty-four miles of Mirabalos" lost its bearing ("east of").

## 3. A forced-march night (the owner's screenshot, then feat/hex-travel-to merged with this lane)

**Before** (the owner's screenshot from feat/hex-travel-to; the hourly lines were in the
story pane):

> Five hours on foot south-east through the grassland, to the grassland 48 miles east of
> Branford. You set out in the evening and stop in the dead of night. Hour nine on the
> way, a forced march: Shadow Constitution 15 vs DC 10, holds up. Hour ten … Constitution
> 18 vs DC 12, holds up. [… five of these …] Looking over the land (Perception d20 7+16 =
> 23): a cave mouth opens in the ground to the east.

**After.** This is the scratch merge, pushing on with `march`: eight hours past the day,
three of the eight checks failed, and every check is in the record.

> You push through the dense timber of the western spine, your limbs heavy and slow as
> the small hours arrive in the thick woods of the Faerholt March. After a grueling march
> that leaves you weary, a sprite appears and grants you passage through the brush. You
> scan the surrounding trees, but nothing new stands out in the gloom.
>
> ▸ The record (opened):
> Eight hours on foot east through the forest, to the forest 60 miles east of Branford.
> You set out in the evening and stop in the small hours. Hour nine on the way, a forced
> march: Shadow Constitution 30 vs DC 10, holds up. Hour ten on the way, a forced march:
> Shadow Constitution 17 vs DC 12, holds up. Hour eleven … 14 vs DC 14, holds up. Hour
> twelve … 22 vs DC 16, holds up. Hour thirteen … 11 vs DC 18, fails: 1 non-lethal,
> fatigued. Hour fourteen … 24 vs DC 20, holds up. Hour fifteen … 13 vs DC 22, fails: 2
> non-lethal, fatigued. Hour sixteen … 12 vs DC 24, fails: 2 non-lethal, fatigued. At the
> forest 60 miles east of Branford, a sprite is near the way; it lets you pass, and you
> walk on. Looking over the land (Perception d20 12+16 = 28), nothing new stands out.

The next night of the same walk (all eight checks failed, then a giant centipede):

> You push through the old-growth deciduous forest of the Faerholt March, your body
> heavy and slow from a grueling journey of many hours. By midday, your muscles ache with
> exhaustion, and you come to a halt as a giant centipede blocks your path. Looking
> across the terrain, you spot a cave mouth opening in the ground to the southeast.

**What is still missing:** the prose does not say WHEN Shadow faltered, because the tell
still hands the narrator eight hourly lines. `rules.march_said` writes the one sentence
that would ("A forced march, eight hours past the day's walking: Shadow falters in hour
thirteen and is left fatigued."). It waits on feat/hex-travel-to putting that sentence
in the tell in place of the hourly lines (lane report).

## 4. A journey of days (Aurvantis, Fizspark to Caelholt)

The two arms met different weather: before, nothing on the road; after, the weather
turned on the third day.

**Before:**

> You travel the road to Caelholt, leaving the memories of Fizspark and its many
> merchants behind as the path stretches out before you. After seven days and a bit of
> travel through shifting weather, you find yourself near the outskirts with Caelholt
> ahead of you. The tension regarding illicit smuggling routes hangs heavy in the air
> along the road leading to the gate.

**After:**

> You travel the road toward Caelholt, leaving the faces of the shopkeepers and the
> dealings of the market behind you. The journey takes you across rolling downs and
> through river-valley farmland, passing the base of the hills. On the third day, a
> sudden turn in the weather forces you to hunker down for four hours until the skies
> clear. Signs of strained tensions over smuggling routes are visible in the guarded
> fortifications and the watchful eyes of the sentries at the gate.

**A slip:** the scorers marked the sentries (invented people), which came from the
town's open matter, not from THE WAY.

## 5. Arriving in a town (Aurvantis, walking on into Vormoor's market)

This beat was not changed by the lane: an arrival inside a town keeps WHAT IS HERE TO SEE.
It is here so the owner can judge the whole road.

**Before:**

> You offer the man in the clean leather a final nod and turn away, leaving his words
> about the cave behind as you focus on the road ahead. You continue your journey toward
> Vormoor, the steady rhythm of your stride marking the distance between your past and
> your destination. You walk past the man in the clean leather and travel toward Vormoor,
> passing the well where a queue of villagers waits to draw water. You arrive at the
> bustling market. Tensions over the village's limited water rights are palpable in the
> air as the crowd gathers near the well.

**After:**

> You leave the man in the clean leather behind as you walk the final stretch toward the
> village. You pass the well, where the morning queue for water is already forming, and
> find yourself standing within the market. Tensions over water rights linger in the air
> like a heavy mist over the market's stalls. The Orc keeper of the market stall
> continues his work, focused on the goods before him.

## 6. A sea passage (Aurvantis, Scrapden to Ledgernook)

The arms met different seas. Before, a warship hailed the ship on day four. After, a
storm hit on day ten.

**Before:**

> The Storm Compass casts off and makes way. Three quiet days pass at sea until, on the
> fourth day out of Scrapden, a warship flying Cinderwarren's colours, the Deep Wager,
> comes down on you on patrol, hails you from a cable off, and lets you go. The deckhand
> continues to tend the rigging in silence.

**After:**

> The Storm Compass casts off and makes way toward Ledgernook. After nine quiet days at
> sea, a sudden storm descends, whipping black water over the rail and obscuring
> everything past the bow. You ride out the tempest, which lasts until the ship is safe
> once more. The deckhand continues to adjust the coil of rope, their movements steady
> and silent.

**An omission:** both arms dropped "Ledgernook is N days on". The scorers marked it in
both.

The voyage that went straight through, 14 days, after:

> The Storm Compass casts off, leaving the safety of the docks behind as you sail for
> fourteen days across the open water. When the ship finally reaches Ledgernook and ties
> up at the quay, you step back onto the docks. You stand on the solid ground of the
> Undertide Warrens in the cool light of the early morning.
>
> (It went on with a harbourmaster's rumour: the arrival's own aside slot, not the
> voyage.)

The before side of that pair met a warship and was not this voyage.
