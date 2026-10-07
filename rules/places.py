"""Where the party is standing, as something the engine can refuse.

The scene had four spatial authorities and none of them was derived from any other:
`location_id` (a World Bible entity), `spot` (free text), `biome` (a closed enum) and the
tactical `zones`/`positions`/`grid`. A merchant's stall and the square outside it are the
same location and the same biome, so walking out of one changed nothing the engine could
see: the merchant stayed in the scene, the brief went on describing his stall, and the
next beat put the player back inside a building they had left. The prose moved and the
state did not.

Every tradition that has solved this — Inform's containment, Diku's `IN_ROOM`, LambdaMOO's
`location`, the Z-machine's single parent pointer, Evennia, Godot's rooms owning their
occupants — holds exactly ONE spatial relation and derives everything else from it. This
module is that one relation's vocabulary.

**A place is generated, never invented.** World Bible describes a city and stops: the
children of a CITY in the export are CHARACTERs, so the rooms genuinely do not exist in
the world data and cannot simply be read. But a model minting place names per turn is
exactly the free-text `spot` this replaces — the narrator establishing a fact rather than
proposing one. So the app generates them: a small closed set per location, seeded off the
location's own durable id, so the same town has the same rooms in every session and after
every reload. The model chooses one that exists and is refused if it does not, which is
the courtesy the ref registry has always extended to people and never to places, though
`gm/prompts.py`'s own docstring has asked for it since it was written.

**The ground is inside the id.** `{location}~urban:the-market`,
`{location}~forest:the-approach`. Stage 8c wanted the biome read off the place and the
place seeded off the biome — a loop — and the review found the other way out: a
`Scene` holds no world by design, so `scene.biome` cannot look anything up, but it can
parse. `terrain_of(scene.at)` is the whole derivation, and the eleven readers that want
the canonical enum string get it from the one coordinate that has one writer.

World Bible ships them now (schema 1.3), and that promise is kept literally: an authored
list replaces a generated one at `home_set` and nothing else changes. Door two (a place the
player founds) and door three (ground gone into) are untouched, and the implied-spot table
is not consulted for a town whose author has spoken — six authored rooms are what the town
has, and adding a docks because the prose says "port" would be the generator arguing with
them. A world that ships none, which is every export at 1.2 or below, still gets the
generated set exactly as before.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from dataclasses import replace as _replace

# Three numbers, and they are three different things. They were two different sixes until
# 2026-09-15, when the World Bible side noticed the engine and the checker disagreed about
# what six counted — and the sharper version of that finding is that THIS app's own
# generator makes seven places for a settlement its own checker notes as over the limit,
# with no districts, no authored list and nothing minted in play. Measured, on a bare
# generated town whose words earn it a docks and a mine head.
#
# Fate caps a conflict at "two to four zones"; Inform's Recipe Book calls for "a small
# number of named positions". The ceiling is the point — an open-ended list is free text
# wearing a tuple, and every extra spot is somewhere the narrator can strand the player
# with nothing to do. What the ceiling protects is the size of the choice put in front of
# the player, which is why it is counted per parent and not per world.

# How many generic spots `_build` draws from the base table: three to six.
MOST_SPOTS = 6

# The character between a location and its ground inside a place id. Never a `:` — that
# already separates the ground from the spot — and never something a World Bible id can
# contain (twelve hex characters, measured against the fixture).
SEP = "~"

# --- what a settlement is made of --------------------------------------------------------
#
# "there is no town or city that has 2 places. 2 places is a rest stop... cities and towns
# have businesses and entertainment and leisure/recreation and religious establishments/
# cultural buildings...the list goes on and on" (2026-09-15).
#
# That was right, and the table it replaced was six rows — a market, a gate, a tavern, a
# temple, the back streets and the workshops — handed to a hamlet and a capital alike. Two
# things were wrong with it and they compounded:
#
#   - it had no trades, no civic life, no leisure, no utilities and no transport, so every
#     settlement in every world was the same six words;
#   - it never read `scale`, which the export has carried on every settlement all along.
#     Aurvantis ships 16 villages, 32 towns and 16 cities, and each of the 64 got six.
#
# So: a real vocabulary, each entry knowing the smallest settlement that plausibly has one,
# and a count that comes from the scale the world already stated.
#
# CATEGORY IS LOAD-BEARING, not decoration. Taking N rows off a seeded shuffle gives a town
# of nine warehouses; the builder takes one category at a time in turn, so a place to
# drink and a place to pray and a place to buy all arrive before a second tannery does.
#
# WHAT HAS NO RULE BEHIND IT YET is marked, because most of these are somewhere to stand
# and be described and nothing more. `docs/settlement-places.md` is the ledger and
# `tests/test_settlement_places.py` holds it to this table — the same bargain `not_yet`
# makes on a race document: said plainly rather than quietly implied.

# Smallest first. A settlement's scale is a word the export writes and these are its
# values; anything unrecognised reads as a town, which is the middle and the commonest.
SCALES = ("village", "town", "city")

# How many ROOMS a settlement of each scale holds — the places drawn from the table below,
# before the junctions a city adds on top. A village is a handful you can see across; a
# town is a high street; a city is quarters.
#
# A village and a town stay flat, everything adjacent to everything, because a settlement
# you can walk across is what a settlement is and a graph the player has to solve is a
# different game. That costs a town a wide prompt — nine rooms is eight exits — and that is
# the trade, taken deliberately.
#
# A city cannot take it. Eighteen rooms flat is seventeen exits in one prompt, which is
# exactly what Fate's two-to-four zones and Inform's "small number of named positions" are
# about, so a city is quartered instead: eighteen rooms plus a square and four crossings is
# twenty-three places, and nothing on the board offers more than six ways on.
# A village went from five to six on 2026-09-21, when it gained a guaranteed way in. The
# entrance is an ADDITION and not a replacement: at five, two guaranteed places left three
# slots for the four categories a player always reaches for — somewhere to buy, to sleep,
# to be quiet, and where nobody is watching — and `test_every_settlement_has_the_four_a
# _player_reaches_for` failed on the spot, which is the checker doing exactly its job.
PLACES_BY_SCALE = {"village": 6, "town": 9, "city": 18}

# (label, about, smallest scale, category, what reads it)
#
# The last field is what consults this place in play today. "" means nothing does — it is a
# room with a floor plan and a name, which a scene can happen in, and no rule looks at it.
# That is not a defect by itself; it is a promise, and the ledger keeps it.
SETTLEMENT_PLACES = (
    # --- buying, selling, making -----------------------------------------------------
    ("the market", "where the stalls are", "village", "trade", "market"),
    ("the smithy", "a hearth, an anvil, and the noise of both", "village", "trade",
     "crafting"),
    # The alchemist's laboratory (alchemy plan §14): glassware, a still, and a hood over
    # the fires — Distill, Sublime, Transmute and rare-and-above reagents, rented by the
    # hour. A village-floor row so a village whose own words name its alchemists can earn
    # one, and NEVER drawn by the fill (`ONLY_WHEN_NAMED`): a settlement has a laboratory
    # because it is a city, because its words say so, or because play founded one.
    ("the laboratory", "glass on every shelf, a still, and a hood over the fires",
     "village", "trade", "crafting"),
    ("the mill", "the wheel, and the sacks stacked against it", "village", "trade", ""),
    ("the workshops", "where the trades are", "town", "trade", "crafting"),
    ("the tannery", "the smell reaches the next street", "town", "trade", ""),
    ("the brewery", "vats, and the heat coming off them", "town", "trade", ""),
    ("the warehouses", "what the town is holding, and who for", "town", "trade", ""),
    ("the mine head", "where the ore comes up", "village", "trade", ""),
    ("the counting house", "ledgers, and somebody who knows what you owe", "city",
     "trade", ""),
    ("the merchants row", "the expensive street", "city", "trade", "market"),
    # --- who is in charge ------------------------------------------------------------
    ("the gate", "the way in and out", "town", "civic", "travel"),
    # A village has no walls and still has a way in. Asked for 2026-09-21: "every
    # city/town needs an entrance or two that is watched a village still has entry roads
    # that are likely watched as well." The history is on the player's side — walls and
    # ditches, "or sometimes just isolated gates, regulated trade and made collection of
    # taxes easier", so an unwalled settlement's entrance is about who is coming and what
    # they are carrying rather than about defence, which is why this is a road and not a
    # gate.
    ("the way in", "where the road reaches the first house, and whoever is watching it",
     "village", "civic", "travel"),
    ("the guardhouse", "where the watch is, and there are always more of them inside",
     "town", "civic", "wanted"),
    ("the guildhall", "where the trades meet", "town", "civic", ""),
    ("the library", "where the records are kept", "town", "civic", ""),
    ("the keep", "where the soldiers are, and the walls they hold", "town", "civic", ""),
    ("the moot hall", "where the arguments are had in public", "town", "civic", ""),
    ("the gaol", "a room with a lock on the outside", "town", "civic", "wanted"),
    ("the barracks", "where the watch sleeps and drills", "city", "civic", "wanted"),
    ("the courthouse", "where it is decided, and written down", "city", "civic", ""),
    ("the customs house", "what came in, and what was paid on it", "city", "civic", ""),
    # --- faith, and the dead ---------------------------------------------------------
    ("the shrine", "somewhere to be quiet", "village", "faith", ""),
    ("the graveyard", "the ones this place has already lost", "village", "faith", ""),
    ("the temple", "somewhere to be quiet, with a roof on it", "town", "faith", ""),
    ("the cathedral", "too large for the town under it", "city", "faith", ""),
    # --- drinking, watching, resting -------------------------------------------------
    ("the inn", "a bed, if you can pay for it", "village", "leisure", ""),
    ("the green", "the common ground, and what happens on it", "village", "leisure", ""),
    ("the tavern", "somewhere to sit down", "town", "leisure", ""),
    ("the bathhouse", "steam, and everybody business in it", "city", "leisure", ""),
    ("the theatre", "where the town watches itself", "city", "leisure", ""),
    ("the arena", "sand, and a crowd that paid to be there", "city", "leisure", ""),
    ("the gardens", "kept, and walled, and not for everybody", "city", "leisure", ""),
    # --- the things a place needs in order to exist at all ---------------------------
    ("the well", "where the water is", "village", "utility", ""),
    ("the granary", "what stands between this winter and the next", "town", "utility",
     ""),
    ("the midden", "where it all ends up", "town", "utility", ""),
    ("the cistern", "under the street, and older than it", "city", "utility", ""),
    # --- getting somewhere else ------------------------------------------------------
    ("the stables", "horses, and the people who know them", "village", "transport", ""),
    ("the docks", "where the boats come in", "town", "transport", ""),
    ("the bridge", "over the water", "town", "transport", ""),
    ("the carters yard", "what leaves at dawn, and on whose account", "city",
     "transport", ""),
    # --- where nobody is watching ----------------------------------------------------
    ("the lane", "round the back, and out of the light", "village", "hidden", ""),
    ("the back streets", "where nobody is watching", "town", "hidden", ""),
    ("the warrens", "a street plan nobody drew", "city", "hidden", ""),
)

# Every settlement has somewhere to buy, somewhere to sleep, somewhere to be quiet and
# somewhere nobody is watching, whatever else it has and whatever the seed says. A town
# with no bed in it is a town the player cannot rest in, and "the generator did not pick
# one" is not a reason a player can act on.
ESSENTIAL_CATEGORIES = ("trade", "leisure", "faith", "hidden")

# How many a category may contribute, past which the slots go elsewhere. Breadth-first
# fill keeps returning to whichever category has fewest, and the small ones have only
# three rows between them — so every city came out with all three hidden places and all
# three faiths, while the trades and the leisure it grows by went unbuilt. A city has one
# seedy quarter, not three.
#
# Uncapped is the default. Only the categories a settlement does not get more of by being
# larger are listed: a big city has more trades and more to do in the evening, and exactly
# as many middens as a small one.
CATEGORY_CAP = {"hidden": 2, "faith": 3, "utility": 2, "transport": 2}

# And these by name, because a category is not specific enough for them. "every town/city
# should have a guardhouse/barracks where a large number of guards are stationed at any
# time" (2026-09-15) — a settlement with nobody keeping order in it is one where the wanted
# state has nowhere to come from, and the player has nowhere to be arrested to.
#
# A village has no guardhouse on purpose: a hamlet of four hundred has a reeve and a horn,
# not a garrison, and inventing one would make every village a fort.
ALWAYS_BY_SCALE = {
    # The way in comes first, and a village has one now. Measured 2026-09-21 across the
    # three shipped worlds: eight of Aurvantis's sixteen villages had no entrance of any
    # kind, and a village's guaranteed set was one well. A settlement nobody can be seen
    # arriving at is also a settlement the LAW cannot watch — `_op_travel`'s warrant check
    # asks whether the party is leaving by the gate, and in a place with none it has never
    # once fired.
    "village": ("the way in", "the well"),
    "town": ("the gate", "the guardhouse", "the well", "the guildhall"),
    # A city has a smithy, whatever the seed (blacksmithing plan §10). Measured 2026-10-03
    # over 200 seeds per scale: the old fill gave a smithy to 0 of 200 villages, 0 of 200
    # towns and 0 of 200 cities. In a village and a town the guarantees and the four
    # essentials spend the budget before the fill starts; in a city the fill takes the
    # biggest thing a settlement is entitled to first, and the smithy is a village-floor
    # row — a city of fifty thousand had a theatre, an arena and a counting house and
    # nowhere to shoe a horse. The medieval record says otherwise: "almost every village
    # in Europe had its own smithy" (medievalists.net, "The medieval blacksmith and his
    # products"). A village and a town are NOT given one by scale, because their budgets
    # are where the four essentials live: every place guaranteed here is taken ahead of
    # the earned ones and the essentials, so a town with a smithy guaranteed and one spot
    # its words earned has nine places before "where nobody is watching" is reached. A
    # smaller settlement gets its smithy from its own words (`IMPLIED`), or through the
    # `found` door when play needs one (`smithy_here`).
    #
    # And a laboratory, the owner's ruling of 2026-10-06 (alchemy plan §21 open point 7):
    # "every city has a laboratory to rent". Distill, Sublime, Transmute and rare reagents
    # need one (`laboratory_here`), and measured the same day it was in 0 of the 82
    # settlements of the three shipped exports and in 0 of 200 generated cities (the row
    # did not exist). Prior art agrees on where they are: every hold capital in Skyrim
    # keeps an apothecary with an alchemy lab (UESP, "Skyrim:Alchemy Labs"), and the
    # Ultimate Campaign's Alchemy Lab room "counts as an alchemist's lab" for up to three
    # workers at once — a room a town keeps, not a tool you carry (aonprd Rules ID 1291).
    # Towns and villages get one from their own words or the `found` door, as the smithy.
    "city": ("the gate", "the guardhouse", "the barracks", "the well", "the guildhall",
             "the smithy", "the laboratory"),
}

# Rows a settlement only ever has by name — guaranteed by its scale (`ALWAYS_BY_SCALE`),
# earned by its own words (`IMPLIED`), or founded in play — and never drawn by the fill.
# The laboratory is the first: the plan's line is that a town or village has one "only
# when their own words imply it", and a row the fill could draw would hand one to a town
# on the seed's say-so. Kept out of the fill's rotation entirely, so adding the row moved
# nothing in a generated village or town (measured 2026-10-06 over 200 seeds per scale:
# 0 of 200 village sets and 0 of 200 town sets changed). Every generated city changed by
# exactly one place — the laboratory takes the slot of its last fill pick, as the smithy
# did on 2026-10-03 — and only a world that authors no places has generated cities.
ONLY_WHEN_NAMED = frozenset({"the laboratory"})

# What counts as a way in or out of a settlement, in one place. Read by the guarantee in
# `home_set` and by the engine's warrant check, so "is this the gate" cannot be answered
# two ways — the check used to compare the place's name against the literal word "gate",
# which no village could ever satisfy.
ENTRANCES = ("the gate", "the way in", "the bridge", "the docks",
             "the north crossing", "the east crossing",
             "the south crossing", "the west crossing")
# The guildhall joined the list 2026-09-16, and it was this app's own checker that put it
# there. `the-patron` is a shipped scheme whose `books` step fires `at($hall)`, and a
# settlement with no hall is one where that step never fires and the quest quietly stalls
# — the same failure as a `lodging` slot landing at the gatehouse, which was measured the
# same afternoon.
#
# Found by `test_what_this_app_builds_passes_this_app_s_own_checker`, which is the third
# time this shape of defect has appeared and the first time a test caught it before it
# was reported to somebody else as THEIR problem: every generated town and eight of forty
# generated cities had nowhere the trades meet, while the checker was about to start
# telling World Bible to provide one.

# Roughly how many people live there, for the feel of the place rather than for any rule.
# "some understanding of a population to help with the feel of the place [50,000+
# population for a city]" — so a city is 50,000 up, and the other two are scaled beneath
# it at the usual medieval proportions.
#
# Never a number the narrator is handed: the brief says "a city of some fifty thousand",
# and the third law is that no model is given a figure to do arithmetic on. `population`
# below turns the band into words.
POPULATION_BY_SCALE = {
    "village": (200, 1_200),
    "town": (2_000, 12_000),
    "city": (50_000, 250_000),
}

# Places that sell something or do something for money, and therefore need somebody
# standing in them. "any place that offers services or merchandise needs an NPC to man it"
# (2026-09-15).
#
# Three things per row, because they have three different jobs:
#
#   who    what the ledger says ought to be there, in the plural where the place has
#          more than one of them. Published to World Bible in the vocabulary.
#   title  the ONE person the engine stands behind the counter, and the name they wear
#          in a world that has no names to lend. A market has stallholders; the keeper
#          is the one who runs the pitch.
#   words  what the codex chooser is asked for (`rules/npcs.py`) — role words, first
#          one heaviest, in the bestiary's own spelling. "harbormaster" and "armorer"
#          are American because the stat blocks are; the prose beside them is not.
#
# `rules/keepers.py` is what reads the last two. Until 2026-09-16 nothing read any of
# it, and this comment said so.
STAFFED = {
    # The market's one person is its MASTER, who sells nothing (item 10 of the 2026-09-28
    # playtest: "the stallholder who runs the pitch" was both the authority and the only
    # seller). The sellers are the market's counters — `rules/market.py`, minted on need
    # by `keepers.stand_up` — and the master is `RUNNERS` below. A village's market has no
    # master (the owner, Q28): it is kept by its stallholders, and `keepers.staff` stands
    # nobody up there but the general store.
    #
    # The words are design D's "clerk" and "merchant" for the master's own block, and then
    # "stallholder" where D had "noble": the same words are what `rules/roster.py` offers
    # the plan as WHO THIS PLACE WOULD HOLD, and the crowd of a market is its
    # stallholders, not its nobility.
    "the market": ("stallholders at their stalls, and a master of the market over them",
                   "the master of the market",
                   ("clerk", "merchant", "stallholder")),
    "the smithy": ("a smith", "the smith", ("blacksmith", "smith", "armorer")),
    # The title is what makes the place a laboratory: "the alchemist" reads through the
    # occupation table (`lives.occupation_for`) as the `alchemist` occupation, whose
    # `alchemy` tag is what `kind_works_alchemy` asks. The keeper rents the hood and may
    # teach (alchemy plan §10.4, §14).
    "the laboratory": ("an alchemist, and whoever is paying for the hood", "the alchemist",
                       ("alchemist", "sage", "scholar")),
    "the mill": ("a miller", "the miller", ("miller", "farmer", "commoner")),
    "the workshops": ("the trades that work there", "the master of the workshops",
                      ("artisan", "craftsman", "laborer")),
    "the tannery": ("a tanner", "the tanner", ("laborer", "commoner")),
    "the brewery": ("a brewer", "the brewer", ("brewer", "laborer", "commoner")),
    "the warehouses": ("a warehouseman with a ledger", "the warehouseman",
                       ("dockworker", "laborer", "clerk")),
    "the counting house": ("a clerk, and whoever they answer to",
                           "the clerk of the counting house",
                           ("clerk", "moneylender", "merchant")),
    "the merchants row": ("shopkeepers who know what you can afford", "the shopkeeper",
                          ("shopkeeper", "merchant", "trader")),
    "the inn": ("an innkeeper", "the innkeeper", ("innkeeper", "barkeep", "merchant")),
    "the tavern": ("whoever is behind the bar", "the one behind the bar",
                   ("barkeep", "innkeeper", "bartender")),
    "the bathhouse": ("an attendant", "the attendant", ("commoner", "servant", "attendant")),
    "the theatre": ("a company, and somebody taking the money",
                    "the doorkeeper of the theatre",
                    ("performer", "entertainer", "acrobat")),
    "the arena": ("a master of the games", "the master of the games",
                  ("gladiator", "champion", "fighter")),
    "the gardens": ("a gardener who would rather you did not", "the gardener",
                    ("gardener", "servant", "commoner")),
    "the stables": ("an ostler", "the ostler", ("commoner", "ostler", "handler")),
    "the docks": ("a harbourmaster", "the harbourmaster",
                  ("harbormaster", "sailor", "captain")),
    "the carters yard": ("a carter taking bookings", "the carter",
                         ("teamster", "carter", "driver")),
    "the guardhouse": ("the watch", "the sergeant of the watch",
                       ("guard", "watch", "sergeant")),
    # NOT the entrances. Staffing them was tried on 2026-09-21 and `test_a_place_that
    # _sells_nothing_gets_nobody` refused it in its own words: "A keeper for every room
    # would put a person in every empty street. The gate is watched by the guardhouse,
    # not manned by a shopkeeper." STAFFED is for places that sell something or do
    # something for money; a way in is watched by the law, which is a different system
    # and the right one.
    "the barracks": ("the garrison", "the garrison sergeant",
                     ("guard", "officer", "soldier")),
    "the gaol": ("a gaoler", "the gaoler", ("jailer", "guard", "warden")),
    "the temple": ("whoever keeps it", "the priest", ("priest", "acolyte", "cleric")),
    "the cathedral": ("clergy, and a great many of them", "the priest of the cathedral",
                      ("priest", "bishop", "cleric")),
    "the guildhall": ("a clerk of the guild", "the clerk of the guild",
                      ("guild", "clerk", "master")),
    "the customs house": ("an officer who wants to see your papers",
                          "the customs officer", ("customs", "officer", "clerk")),
}


# Places whose one person RUNS the place rather than serving at it — an authority, not a
# shop (docs/design-d-people.md §4.8). The medieval clerk of the market "had control over
# prices, weights and measures" and kept a court; he did not trade. `keepers.keeps_a_counter`
# is false for the keeper of a place named here, whatever its category, and
# `rules/audience.py` decides when they will hear the player at all.
#
# Only the market is built (I2). The master of the workshops, the harbourmaster, the clerk
# of the counting house and the master of the games have the same shape and join this set
# one row at a time, each with its counters, when somebody builds them — adding one here
# before its sellers exist would shut a counter the player can use today.
RUNNERS = frozenset({"the market"})
# The smallest settlement whose market has a master. The owner, Q28 (2026-09-29): "town
# and up"; a village's market is kept by its stallholders and answers to the village's
# own authority.
MASTER_FROM = "town"
# Places outside the "trade" category whose keeper nonetheless sells across a counter.
# The stables are transport — they are how you leave — and the ostler sells the horses
# (d20pfsrd "Animals & Animal Gear"; the owner, 2026-09-29: "no renting just buy one").
SELLS_OUTSIDE_TRADE = frozenset({"the stables"})


def runs_it(label: str) -> bool:
    """Whether the keeper of this place is its authority rather than a seller."""
    return " ".join(str(label or "").split()).lower() in RUNNERS


def has_a_master(scale: str) -> bool:
    """Whether a market in a settlement of this scale has a master standing in it."""
    scale = scale if scale in SCALES else "town"
    return SCALES.index(scale) >= SCALES.index(MASTER_FROM)


def staffed(label: str) -> str:
    """Who ought to be standing in this place, or "" where nobody need be."""
    row = STAFFED.get(" ".join(str(label or "").split()).lower())
    return row[0] if row else ""


def category_of(label: str) -> str:
    """Which of the seven kinds of place this is, or "" for one the table has no row for.

    Read by `rules/keepers.py` to answer whether a keeper is somebody you can BUY from:
    a gaoler and a stallholder are both people standing in a room they keep, and only
    one of them has a counter.
    """
    want = " ".join(str(label or "").split()).lower()
    return next((cat for lbl, _a, _s, cat, _e in SETTLEMENT_PLACES if lbl == want), "")


def keeper_of(label: str) -> tuple[str, tuple[str, ...]]:
    """The one person behind the counter: (what they are called, the codex's words).

    ("", ()) for a place that sells nothing — a well has no keeper, and inventing one
    would put a person in every empty street.
    """
    row = STAFFED.get(" ".join(str(label or "").split()).lower())
    return (row[1], tuple(row[2])) if row else ("", ())


def population(scale: str) -> str:
    """How many people live there, in the words a narrator may use.

    A band and never a figure: the third law is that no model authors a number, and
    "fifty thousand" in a brief is a number the model will start doing arithmetic with.
    """
    low, high = POPULATION_BY_SCALE.get(scale, POPULATION_BY_SCALE["town"])
    if high <= 2_000:
        return "a few hundred people, and everyone knows everyone"
    if high <= 20_000:
        return "some thousands of people"
    return "tens of thousands of people, most of whom will never see you"


def what_it_is(scale: str) -> str:
    """"a village of a few hundred people, and everyone knows everyone".

    Reported 2026-09-22, after four sessions in Vormoor: *"I have never been aware that
    vormoor was a village. this should be one of the first things done when you are being
    dropped into a world."* And they were right in a way that is measurable —
    `population` above, which says exactly what a player wants to know here, had **no
    production caller anywhere in the app**. One test read it. The scale reached the
    narrator's brief ("HERE: Vormoor, a village.") and never reached the page or the
    opening, so the model knew what kind of place it was and the player did not.

    One composer, three readers — the opening, the brief and the panel — because three
    sentences saying this three ways is the drift CLAUDE.md names.
    """
    scale = " ".join(str(scale or "").split()).lower()
    if scale not in POPULATION_BY_SCALE:
        # Not a scale this app prices. Say the word the world used and claim no size:
        # a made-up population for a "hamlet" or a "district" is this app inventing a
        # fact about somebody else's world.
        return f"a {scale}" if scale else ""
    return f"a {scale} of {population(scale)}"

# The same for somewhere nobody lives. A ruin or a stretch of forest still needs more than
# one place to stand, or "I go deeper in" is unrepresentable.
_WILD = (
    ("the approach", "the way you came"),
    ("the heart of it", "as far in as this goes"),
    ("the edge", "where it thins out"),
    ("the high ground", "somewhere to see from"),
)

# --- door one: places the world implies ------------------------------------------------------
#
# "why did it not make a docks?" Vyrakon's export says "port access" and "cyclone-prone
# coastlines", and the settlement table had no harbour row, so the facts that justified
# one were never read. Each row: the words that imply the place, in the settlement's own
# facts and paragraphs, and the spot they imply. Read mechanically, deterministic,
# nothing the model authors — the world said it.
IMPLIED = (
    (("port", "harbour", "harbor", "dock", "docks", "quay", "wharf", "fishing", "ships",
      "shipping", "boats"), ("the docks", "where the boats come in")),
    (("river", "bridge", "ferry", "crossing"), ("the bridge", "over the water")),
    (("guild", "guilds", "guildhall"), ("the guildhall", "where the trades meet")),
    (("library", "archive", "archives", "scriptorium", "scribes"),
     ("the library", "where the records are kept")),
    (("walls", "fort", "fortress", "the keep", "a keep", "castle", "citadel", "garrison"),
     ("the keep", "where the soldiers are")),
    (("the mine", "a mine", "mines", "mining", "quarry", "ore"),
     ("the mine head", "where the ore comes up")),
    (("shrine", "temple", "cathedral", "priests", "prayers", "faith"),
     ("the shrine", "somewhere to be quiet")),
    (("the well", "a well", "wells", "wellhead", "cistern", "fountain"),
     ("the well", "where the water is")),
    # A settlement whose words name its smiths has a smithy (blacksmithing plan §10: the
    # town forge is where rare work, smelting and alloying happen). Last in the table on
    # purpose: earned spots are taken in table order up to `MOST_IMPLIED`, and a row added
    # at the top would have pushed a docks or a library out of towns that already earned
    # them.
    #
    # "forge" is a phrase cue ("a forge", "the forges") and its verb forms — "forged",
    # "forging", and "forges" as in "forges ahead" — are not cues at all. Measured 2026-10-03
    # across the three shipped exports' settlement facts and prose: "forged" fired twice
    # and "forging" six times, and all eight were metaphors — "alliances forged in ancient
    # traditions", "the great forging's aftermath". Not one was a smithy. "smiths" fired
    # once (Kestwick: "the smiths and the wool merchants both want..."), and that one is.
    (("smith", "smiths", "smithy", "smithies", "blacksmith", "blacksmiths", "a forge",
      "the forge", "the forges", "its forges", "anvil", "anvils", "ironworks", "farrier", "farriers",
      "foundry", "foundries", "metalworking", "metalworkers", "armourer", "armourers",
      "armorer", "armorers", "weaponsmith", "weaponsmiths", "bladesmith", "bladesmiths"),
     ("the smithy", "a hearth, an anvil, and the noise of both")),
    # A settlement whose words name its alchemists has a laboratory (alchemy plan §14:
    # towns and villages get one "only when their own words imply it"). After the smithy,
    # for the smithy's reason: a row above would push an earned docks or library out.
    #
    # Bare "alchemy" is NOT a cue: "the strange alchemy of trade" is how prose uses it as
    # a metaphor, and a metaphor earns no building. It cues as a phrase — "of alchemy",
    # "its alchemy". Measured 2026-10-06 across the three shipped exports' settlement
    # words: "alchemist" fired in 9 settlements, every one "a black-market alchemist
    # collective" (alchemists who must work somewhere), "alchemical" in 2 ("its trade in
    # alchemical explosives", "alchemical curiosities") and bare "alchemy" in none. All
    # eleven are authored, so the cue mints nothing there; `tools/check_places.py` notes
    # each for the author, which is the cue table's other job.
    # "apothecary" is NOT a cue: it is the herbal healer's word (content/people/
    # occupations.json `healer`), and an apothecary's shop is herbalism's.
    (("alchemist", "alchemists", "alchemical", "laboratory", "laboratories", "alembic",
      "alembics", "chymist", "chymists", "of alchemy", "its alchemy", "in alchemy"),
     ("the laboratory", "glass on every shelf, a still, and a hood over the fires")),
)
# Some cues are phrases, and that is the fix for a word that is also a common verb or
# adverb. Reported from the World Bible side on 2026-09-15 and then measured here against
# its 64-settlement export:
#
#   "well" fired in 64 of 64 — every one of them on "that works well enough in"
#   "keep" fired in 16 of 64 — every one of them on "tax-farmers who keep a cut of"
#
# Not one real well and not one real keep among them. That is worse than noise: a
# settlement is capped at `MOST_SPOTS`, so a phantom place takes a real one's slot.
#
# The reported fix was to swap the words — `well` to `wells`, and drop `keep` because the
# row already has `fortress` and `garrison`. That works and costs two real hits: "the
# well" is how prose names a village's only well, and `keep` is the exact word for the
# building. So the matcher learned phrases instead, which is four lines and keeps both.
# `mine` went the same way pre-emptively: it is also the possessive pronoun, it had not
# fired yet in either world, and finding out later costs a place.

# What a settlement's own words may earn it, at most. No longer a number of places added
# ON TOP of a generated set — `_wanted` folds the earned ones into the scale's own budget,
# ahead of the generic filler, so a port town spends a slot on its docks rather than
# growing one. Kept as a cap on how much of a settlement its prose may decide.
MOST_IMPLIED = 4

# What a settlement may hold, and the number a checker has to use. It was
# `MOST_SPOTS + MOST_IMPLIED` for about an hour on 2026-09-15, which was already an
# improvement on two files remembering two different sixes — and then the scale table
# replaced both: a settlement holds what its own size says it holds, and eight was still
# a village and a capital getting the same answer.
#
# The largest of the three is what a checker compares against, because it is the most a
# settlement of ANY size may hold. A village at 18 is as wrong as a city at 5, and that is
# a different check — `check_places.py` can ask the settlement its scale.
MOST_IN_A_SETTLEMENT = max(PLACES_BY_SCALE.values())

# --- door three: ground you go into ----------------------------------------------------------
#
# "what if i choose to explore the sewers or i go outside the city to a cave." The
# roguelike answer: not authored, GENERATED ON ENTRY FROM A SEED, so the same stairs lead
# to the same cellar next time. Each kind: the ground it stands on (the engine's own biome
# vocabulary), the spots it is made of, and how many hours the way there costs when it
# lies outside the settlement (0 for something under or inside it).
VENTURES: dict[str, dict] = {
    "sewers": {"label": "the sewers", "terrain": "underground", "hours": 0,
               "spots": (("the outfall", "where it meets the daylight"),
                         ("the main channel", "the way the water goes"),
                         ("the sump", "as low as it goes"))},
    "cellar": {"label": "the cellars", "terrain": "underground", "hours": 0,
               "spots": (("the stair", "the way down"),
                         ("the vaults", "where things are kept"))},
    "crypt": {"label": "the crypt", "terrain": "ruins", "hours": 0,
              "spots": (("the stair", "the way down"),
                        ("the niches", "where the dead are"),
                        ("the deep chamber", "as far in as this goes"))},
    "rooftops": {"label": "the rooftops", "terrain": "urban", "hours": 0,
                 "spots": (("the ridge", "the high way across"),
                           ("the gutter", "where it drops"))},
    "alley": {"label": "the back alley", "terrain": "urban", "hours": 0,
              "spots": ()},
    "cave": {"label": "the cave", "terrain": "underground", "hours": 2,
             "spots": (("the mouth", "the way in and out"),
                       ("the throat", "where the light goes"),
                       ("the deep chamber", "as far in as this goes"))},
    "mine": {"label": "the old mine", "terrain": "underground", "hours": 2,
             "spots": (("the adit", "the way in"),
                       ("the gallery", "where they dug"),
                       ("the flooded level", "as low as it goes"))},
    "ruins": {"label": "the ruins", "terrain": "ruins", "hours": 2,
              "spots": (("the gate", "the way in"),
                        ("the courtyard", "the open middle"),
                        ("the undercroft", "as low as it goes"))},
    "tower": {"label": "the tower", "terrain": "ruins", "hours": 1,
              "spots": (("the foot", "the way in"),
                        ("the top", "somewhere to see from"))},
}
# The slugs `setting_of` parses against: the reaches of open ground, and the ventures
# that lie away from the settlement rather than under it. Derived from the two tables
# above, never listed a second time.
_WILD_SLUGS = frozenset("-".join(label.split()) for label, _about in _WILD)
_AWAY_SLUGS = frozenset("-".join(spec["label"].split()) for spec in VENTURES.values()
                        if int(spec.get("hours") or 0) > 0)

# How many places may hang off one parent MINTED IN PLAY — a founded base, a venture's
# head. Read only against `scene.founded`, and deliberately not the same question as how
# many rooms a settlement holds: an alley of three and a sewer of four hang off a town of
# eight and none of those numbers constrains the others. The example in this comment used
# to read as though it did, which is half of why the checker and the engine ended up
# counting different things.
MOST_CHILDREN = 6

# The ground a settlement stands on, by construction. Four predicates used to answer
# "is this a town" — `biomes.from_world`'s `kind == "CITY"`, `_settled` here,
# `_at_market`'s `== "urban"` and the injector's `_SETTLEMENT_KINDS` — and the review
# measured them disagreeing: a village is settled to three of them and grassland to the
# fourth. The settlement set says `urban` and asks nobody.
URBAN = "urban"


@dataclass
class Place:
    """One spot a party can be standing in, and what leads out of it.

    A KIND, in the `Manifestation` mould — a scene-held dataclass with `as_dict` /
    `from_dict` — and deliberately NOT an `ActiveEffect`. A naive reading of law 2 says
    every change travels as an effect, but a place has no duration, no stacking policy,
    and removing one must not leave the party nowhere. Law 2 governs numbers that change
    and wear off.

    `exits` is the move vocabulary and the whole reason this is not a string: the engine
    can refuse a destination that is not on it. Adjacency only — Fate shipped weighted
    zone borders and then deleted them, and obstruction belongs in states and effects
    rather than in a cost table nobody would tune.
    """

    id: str = ""
    name: str = ""
    about: str = ""
    # For a place minted in play (doors two and three): the place it hangs off, who
    # holds it, and how it came to be — `found` (the player's declaration, with an
    # owner) or `venture` (ground gone into, generated from a seed) — the same
    # provenance rule every number carries. Empty on a generated place.
    parent: str = ""
    owner: str = ""
    origin: str = ""
    # Read off the id, never stored beside it. `biome` as a sibling field on the scene
    # is precisely what let "both are urban" defeat the transition.
    terrain: str = ""
    # Another ROOM in the same settlement that this one hangs off — a quarter's crossing,
    # or the square a crossing comes off. Empty for a place that hangs off nothing, which
    # is every place in a village or a town and the square itself in a city.
    #
    # Distinct from `parent`, which is the world ENTITY, and the distinction is load
    # bearing: `parent` is pinned to the entity by the id grammar and by `location_of`,
    # and three things depend on that. Asked for from the World Bible side on 2026-09-15
    # for exactly this reason, and generated here before it is authored anywhere.
    #
    # It carries no distance and no weight. A room is adjacent to its crossing and that is
    # all `within` says; the exits say the rest.
    within: str = ""
    exits: tuple[str, ...] = ()
    # What the world said this room is like underfoot: how big, how cluttered, what the
    # going is, how it is shaped upward — as a `floorplan.Shape`, built once when the
    # place is read and handed down to whatever lays the ground. None for a generated or
    # founded place, which means "derive it", exactly as before.
    #
    # NOT in `as_dict`, and that is the rule rather than an omission: an authored place is
    # re-read from the world every time (`_authored`), so storing its shape in a save
    # would be a second copy of a fact the export owns — the trap this module's whole
    # "derived, never stored" arrangement exists to avoid. Founded places, which ARE
    # stored, have no authored shape to lose.
    shape: "object | None" = None
    # How many floors this building has, as the levels themselves: (-1, 0, 1) is an
    # undercroft, a ground floor and an upstairs. The world writes `{"up": n, "down": n}`
    # on 177 of the 456 places it ships and this app generated its own answer off a seed
    # instead — Ashwatch's tavern is authored as one floor up and none down, and the
    # generator gave it an undercroft, an upper floor and a top floor. Empty derives, as
    # it always did; not saved, for the reason `shape` is not.
    floors: tuple[int, ...] = ()
    # True when the place is named but cannot be entered — Diku's `<room linked>` of -1,
    # "non-functional exits that display descriptions only". It lets the narrator write
    # "an alley runs east" without minting a node, and keeps the pressure that would
    # otherwise force the enumeration back open.
    described_only: bool = False
    # What a founded place IS when its name is its own: "the Driftwood Reach" is a
    # `tavern`. One of `KINDS`, the settlement table's own labels, so a founded place
    # is shaped, staffed and judged as its kind rather than as an unknown word. Empty
    # for a generated place, whose name is its kind already; an authored place carries
    # the world's own `kind` when it wrote one the app knows (`_authored_kind`).
    kind: str = ""
    # How far out a reach of a settlement's hinterland lies past the ring, in miles
    # (`geography.Reach`, `outskirts.hop_minutes`); 0 for every other place. A distance,
    # not a weight on an exit: Fate's deleted weighted borders priced crossing a line,
    # and this is the walk to ground three miles off, which the rules price already
    # (Table 7-8). Derived with the ring every time and NOT in `as_dict`, for the reason
    # `shape` is not: the world owns it.
    miles: float = 0.0

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "about": self.about,
                "terrain": self.terrain, "exits": list(self.exits),
                "described_only": self.described_only, "within": self.within,
                "parent": self.parent, "owner": self.owner, "origin": self.origin,
                "kind": self.kind}


def from_dict(d: dict) -> Place:
    kind = str(d.get("kind") or "").strip().lower()
    return Place(
        id=str(d.get("id") or ""), name=str(d.get("name") or ""),
        about=str(d.get("about") or ""), terrain=str(d.get("terrain") or ""),
        exits=tuple(str(x) for x in (d.get("exits") or ())),
        described_only=bool(d.get("described_only")),
        within=str(d.get("within") or ""),
        parent=str(d.get("parent") or ""), owner=str(d.get("owner") or ""),
        origin=str(d.get("origin") or ""), kind=kind,
        # Shaped as its kind, not as its name: derived here, like every shape a stored
        # place has, so a save carries the kind and never the floor plan.
        shape=shape_of_kind(kind, str(d.get("terrain") or "")),
    )


def shape_of_kind(kind: str, terrain: str = ""):
    """The floor plan of a place of this kind, or None for a place with no kind."""
    if not kind:
        return None
    from . import floorplan as floorplan_mod

    ground = str(terrain or "").strip().lower() or URBAN
    return floorplan_mod.shape_for(f"x{SEP}{ground}:{_slug('the ' + kind)}", ground)


# --- the id, and what it says ------------------------------------------------------------

def region_key(location_id: str, terrain: str) -> str:
    """`{location}~{terrain}`: the prefix every place on that ground shares."""
    return f"{str(location_id or '').strip()}{SEP}{str(terrain or '').strip().lower()}"


def terrain_of(place_id: str) -> str:
    """The ground a place id stands on, or "" when the id does not say.

    The parse IS `scene.biome`. No lookup, no world, no table — which is what lets a
    deep-copied Scene answer the question and a save written by an older build
    (`at == ""`) answer honestly with nothing.
    """
    head = str(place_id or "").split(":", 1)[0]
    if SEP not in head:
        return ""
    return head.rsplit(SEP, 1)[1].strip().lower()


def location_of(place_id: str) -> str:
    head = str(place_id or "").split(":", 1)[0]
    return head.rsplit(SEP, 1)[0] if SEP in head else head


# --- in, under, or outside ----------------------------------------------------------------
#
# The middle scale (docs/design-b-space.md, 17.1): between a settlement's rooms and a
# journey of days there is the ground just outside it — the outskirts, the fields, the
# shore, the head of each road out, and the crossroads where the roads part. Those are
# places like any other, filed under the settlement's id with their ground in the head as
# every place is, and marked by `@` at the head of their spot: `{loc}~farmland:@the-
# outskirts`. `@` cannot come out of `_slug` (it keeps `[a-z0-9 ]`) and no separator uses
# it (`~`, `:`, `^` and `/` are taken), so a ring id can never be mistaken for a room.
#
# Whether the party is IN the settlement, UNDER it or OUTSIDE it is then a parse of the
# id, never a field. The plan asked for `Scene.outside`; it was dropped at G0 (Q3) for the
# reason this repo already learned once — `scene.biome` stored beside `scene.at` was a
# sibling field, and removing it is what `test_nothing_writes_the_ground_beside_the_place`
# holds. Bobby's save of 2026-09-28, standing at `…~forest:the-approach`, parses as
# outside with no migration.
RING = "@"

# The kinds of place that belong on the road and not in the street. "I walk to the
# nearest crossroads" was refused on 2026-09-28 as "no such kind of place as
# 'crossroads'" (Bobby, turns 6 and 7): the kinds were the settlement table's, and the
# settlement table has no road. A bridge is both — the town's bridge is a way in, a bridge
# out on the road is a crossing — so it is here as well as in `KINDS`, and which one it
# is depends on the ground it is founded off (`fits_here`).
OUTSIDE_KINDS: dict[str, str] = {
    "road": "a stretch of road, and whoever is on it",
    "crossroads": "where roads part, and a post to say which way",
    "milestone": "a stone by the road, and what is cut in it",
    "ford": "where the road goes through the water rather than over it",
    "bridge": "a span over the water, and the road either side",
}
# The ones that need water under them, as `WATER_KINDS` does in town.
_OUTSIDE_WATER = frozenset({"ford", "bridge"})


def _spot_path(place_id: str) -> list[str]:
    """The spot of a place id, split at `/`, with any storey taken off."""
    pid = str(place_id or "")
    spot = pid.split(":", 1)[1] if ":" in pid else ""
    spot = spot.rsplit(STOREY, 1)[0] if STOREY in spot else spot
    return [s for s in spot.split("/") if s]


def setting_of(place_id: str) -> str:
    """"in", "under" or "outside": which side of the settlement's edge this place is.

    A pure parse, in four steps (docs/design-b-space.md §4):

    1. ground `urban` in the head → in (a storey is part of its building);
    2. the spot's root starts with `@` (the ring) or is one of the `_WILD` reaches of open
       ground → outside;
    3. a spot with no `/` at all → outside: an authored non-urban place, open ground;
    4. otherwise the place was minted under a town room on other ground, and it is
       outside when any step of its path is a venture that lies out of the settlement
       (`VENTURES` with hours: the cave, the old mine, the ruins, the tower), or when its
       ground is open ground (`OPEN_GROUND`: a mountain is never under a town), and
       under it otherwise (the sewers, the cellars, the crypt).

    An id that says nothing about its ground (an old save's `at == ""`, the world-less
    `here`) is `in`: that is where every campaign started before places had ground.
    """
    ground = terrain_of(place_id)
    if not ground or ground == URBAN:
        return "in"
    path = _spot_path(place_id)
    if not path:
        return "outside"
    root = path[0]
    if root.startswith(RING) or root in _WILD_SLUGS:
        return "outside"
    if len(path) == 1:
        return "outside"
    if any(step in _AWAY_SLUGS for step in path[1:]):
        return "outside"
    # Open ground is never under a town. A mountain founded off a town room or off a
    # place the world authored out in the land has a long path with no ring at its root,
    # and read "under Vormoor" until 2026-10-05; what lies under a town is underground,
    # ruins, or water (`OPEN_GROUND` is the rest).
    if ground in OPEN_GROUND:
        return "outside"
    return "under"


def is_ring(place_id: str) -> bool:
    """Whether this is one of a settlement's outside places (the outskirts, a road head)."""
    path = _spot_path(place_id)
    return bool(path) and path[0].startswith(RING)


# --- storeys ---------------------------------------------------------------------------
#
# A building's floors are PLACES, joined by stairs, and not a third dimension of the
# tactical grid. That is the shape every system that keeps verticality and stays legible
# settled on — Foundry's Levels, Caves of Qud's strata, Dwarf Fortress's z-levels are all
# stacked flat maps with a transition between them — and it is also the shape this app was
# already in: `mint` has had a branch for "a different ground under the same roof: the
# sewers under a town" since places were written. A storey is that, pointing up.
#
# The storey lives in the id, like the ground does, because the id is the one spatial
# authority and a second field would be the fifth one `docs/places-plan.md` refused. `^` is
# safe as the separator: `_slug` strips everything but `[a-z0-9 ]`, a location id is twelve
# hex characters, and a terrain is a single lower-case word, so nothing else can ever
# contain it.
STOREY = "^"

# What a floor is called, by how far it is from the ground one. "The undercroft" rather
# than "the cellar" deliberately: `VENTURES` already offers "the cellars" as somewhere you
# venture into from a town, and two places a player can reach by typing almost the same
# words is a way to pick the wrong one.
_STOREY_NAMES: dict[int, tuple[str, str]] = {
    2: ("the top floor", "as high as the stairs go"),
    1: ("the upper floor", "one flight up"),
    -1: ("the undercroft", "under the boards"),
}


def storey_of(place_id: str) -> int:
    """Which floor this id names, zero being the one you walk in on.

    Parsed, never stored — the same arrangement as `terrain_of`, so a deep-copied Scene
    can answer it and a save written before storeys existed answers 0, which is true.
    """
    tail = str(place_id or "").rsplit(STOREY, 1)
    if len(tail) < 2:
        return 0
    try:
        return int(tail[1])
    except ValueError:
        return 0


def base_of(place_id: str) -> str:
    """The building, with the floor taken off."""
    text = str(place_id or "")
    return text.rsplit(STOREY, 1)[0] if STOREY in text else text


def storey_id(place_id: str, level: int) -> str:
    """The id of a given floor of whatever building this id is in."""
    base = base_of(place_id)
    return base if not level else f"{base}{STOREY}{int(level)}"


def _floors(said) -> tuple[int, ...]:
    """`{"up": 1, "down": 0}` as the levels themselves: (0, 1).

    Fails soft to "nothing said", like everything else that reads an export: a building
    whose floor count cannot be read is a building this app counts for itself, which is
    what it did for every building until today. Capped at three each way, because the
    place graph is what a player walks and a nine-storey tower is a different feature.
    """
    if not isinstance(said, dict):
        return ()
    try:
        up = max(0, min(3, int(said.get("up") or 0)))
        down = max(0, min(3, int(said.get("down") or 0)))
    except (TypeError, ValueError):
        return ()
    return tuple(range(-down, up + 1)) if (up or down) else ()


def is_indoors(place_id: str, terrain: str = "", shape=None) -> bool:
    """Whether this place has a roof on it.

    Asked of `floorplan`, which already answers it: a shape with a `ceiling` is a room and
    one without is under the sky. One source, so a tavern cannot be indoors for the
    purposes of stairs and outdoors for the purposes of flying over it — which is exactly
    why the authored shape has to reach here too. A world that wrote `height: null` on its
    market has said the market has no roof, and a reader that answered from the table
    while the battlefield answered from the export would be two sources again.
    """
    from . import floorplan

    return floorplan.shape_for(place_id, terrain, shape).ceiling is not None


def storeys(place_id: str, terrain: str = "", shape=None,
            floors: tuple[int, ...] = ()) -> tuple[int, ...]:
    """Every floor this building has, in order, ground floor included.

    What the world said, when it said: `floors` is the export's own `{"up", "down"}`, and
    a house the author gave one upper floor gets one upper floor. Otherwise deterministic
    off the building's own id, like everything else about a place — the same tavern has
    the same number of floors for ever, and none of it is saved.

    Outdoors is always the single floor you are standing on, whatever else was written. A
    market has no upstairs, and the roof is the older authority of the two: the handoff
    tells an author that no place may claim storeys and open sky at once, and this is what
    happens to one that does.
    """
    if not is_indoors(place_id, terrain, shape):
        return (0,)
    if floors:
        return floors
    n = _seed(base_of(place_id))
    up = n % 3                 # nothing, one floor, or two
    down = (n >> 5) % 2        # and an undercroft, or not
    return tuple(range(-down, up + 1))


def storey_set(place: "Place") -> tuple["Place", ...]:
    """The floors above and below this one, as places, wired to the stairs.

    The ground floor is `place` itself and is not repeated. Each floor keeps the
    building's ground and parent — an upper room is still `urban` — because the terrain is
    about what the ground is made of and not about how far up it is.
    """
    levels = storeys(place.id, place.terrain, getattr(place, "shape", None),
                     getattr(place, "floors", ()))
    out: list[Place] = []
    for level in levels:
        if level == 0 or level not in _STOREY_NAMES:
            continue
        label, about = _STOREY_NAMES[level]
        reachable = [storey_id(place.id, other) for other in levels
                     if abs(other - level) == 1]
        out.append(Place(
            id=storey_id(place.id, level),
            name=f"{label} of {place.name}" if place.name else label,
            about=about, terrain=place.terrain, exits=tuple(reachable),
            parent=place.id, origin="storey", floors=levels,
            # The building's own ground floor, carried up. `floorplan._upstairs` derives
            # a floor from the shape below it — "the same footprint, divided up more" —
            # and handed nothing it would derive the upper rooms of a world-measured
            # tavern from the generic tavern in the table instead.
            shape=place.shape))
    return tuple(out)


def stairs_from(place_id: str, terrain: str = "", shape=None,
                floors: tuple[int, ...] = ()) -> tuple[str, ...]:
    """The ids one flight up and one flight down, where those floors exist.

    Only adjacent floors: you cannot step from the undercroft to the top of the house
    without passing the room between, which is the whole reason these are places joined by
    stairs rather than a coordinate anybody can name.

    The authored shape comes along for the same reason it reaches `storey_set`: the two
    have to agree about whether this building has floors at all. Read from different
    sources, `with_storeys` would mint an upstairs off the world's roof while this refused
    to let anybody climb to it.
    """
    here = storey_of(place_id)
    return tuple(storey_id(place_id, other)
                 for other in storeys(place_id, terrain, shape, floors)
                 if abs(other - here) == 1)


# --- the sets ----------------------------------------------------------------------------

def _seed(location_id: str) -> int:
    """A number that is the same for this location for ever.

    Not `hash()`: Python salts string hashing per process, so the same town would lay
    itself out differently after a restart — the class of bug the campaign save exists to
    prevent, arriving through the back door.
    """
    return int(hashlib.sha256(str(location_id or "nowhere").encode()).hexdigest()[:8], 16)


def _settled(location, terrain: str = "") -> bool:
    """Whether this is somewhere people live, and so which table it is made of.

    Falls back to the ground underfoot when the world entity is not to hand, which is
    derivation rather than a guess: `urban` means streets and yards, and the app's own
    biome table says so. An engine built without a world still has `scene.location_id`
    and the ground its place id carries, and between them that is enough.
    """
    kind = str(getattr(location, "kind", "") or "").upper()
    scale = str(getattr(location, "scale", "") or "").lower()
    if kind or scale:
        # Any word this app can read as one of its three sizes means somewhere people
        # live — including the other vocabulary's words, so a `metropolis` is not taken
        # for open ground the day the supplier stops translating on our behalf.
        return ("CITY" in kind or "SETTLEMENT" in kind or "TOWN" in kind
                or scale in PLACES_BY_SCALE or scale in SCALE_ALIASES)
    # A bare id with nothing said about its ground is a settlement. Every location a
    # campaign starts in is one (twelve of twelve in the fixture, all CITY), and the
    # alternative — reading the ground the party is CURRENTLY on — is what made a
    # world-less engine forget it had a town to go back to the moment the party
    # walked into the forest. Only an explicit non-urban hint makes a wild site.
    return str(terrain or "").lower() in ("", URBAN)


import re as _re

_WORDS = _re.compile(r"[a-z][a-z'-]+")


def _slug(label: str) -> str:
    return "-".join(_re.sub(r"[^a-z0-9 ]", "", str(label).lower()).split())


def _build(location_id: str, terrain: str, table) -> tuple[Place, ...]:
    n = 3 + _seed(location_id) % (min(MOST_SPOTS, len(table)) - 2)
    chosen = list(table[:n])
    prefix = region_key(location_id, terrain)
    ids = [f"{prefix}:{_slug(label)}" for label, _ in chosen]
    # Everywhere connects to everywhere else on one ground. A settlement is not a maze,
    # and a graph the player has to solve is a different game from the one this is.
    return tuple(
        Place(id=pid, name=label, about=about, terrain=terrain,
              exits=tuple(x for x in ids if x != pid))
        for pid, (label, about) in zip(ids, chosen)
    )


def _with_a_way_in(authored: tuple[Place, ...], here: str, location) -> tuple[Place, ...]:
    """An authored settlement that names no entrance gets one appended.

    This is a deliberate amendment to the rule stated at the top of this module — "six
    authored rooms are what the town has, and adding a docks because the prose says
    'port' would be the generator arguing with them" — and the reason it is not the same
    thing is that an entrance is structural rather than decorative.

    Measured 2026-09-21 on the shipped worlds: eight of Aurvantis's sixteen villages name
    no way in, and Vormoor is one of them. Two things follow from that, and both were
    reported from the table on the same day:

    * the narrator invents one. Asked to describe a settlement, it wrote "you stand under
      the gate" in a town whose only places are a well, a market, a guildhall, a lane and
      a green (item 45) — because a settlement obviously has a way in, and the brief's
      list said otherwise;
    * the LAW cannot work. `_op_travel`'s warrant check watches the gate, so being wanted
      in a village has never once shut anything.

    A docks is a flourish; a way in is the difference between a town somebody can arrive
    at and a town that is only ever an interior. Nothing is reordered, and a settlement
    that names any entrance — a gate, a bridge, a crossing, the docks — gets nothing
    added.

    The one authored thing that changes is the first place's exits, which gain the way
    in. Without that the entrance was a door with no handle on the inside: measured
    2026-09-23 on Aurvantis, all eight villages given a way in had it unreachable from
    every other place — `route` found no path, `travel` there fell back to a single
    unwalked step, and the brief's NEXT DOOR line never listed it. An exit is adjacency,
    and adjacency runs both ways.
    """
    if not _settled(location, ""):
        return authored                      # a wild site is not arrived at by a road
    named = {str(p.name or "").strip().lower() for p in authored}
    if named & set(ENTRANCES):
        return authored
    label, about, _scale, _cat, _reads = next(
        row for row in SETTLEMENT_PLACES if row[0] == "the way in")
    spot = _slug(label)
    place_id = f"{here}~{URBAN}:{spot}"
    # It carries its own shape like every other place in an authored set does. Without
    # one, three tests in `test_authored_shapes.py` raised on `p.shape.width` — the
    # invariant is that a place in one of these tuples can always be laid out, and a
    # generated addition is no exception to it.
    from dataclasses import replace

    from . import floorplan as floorplan_mod

    way = Place(id=place_id, name=label, about=about, terrain=URBAN,
                exits=tuple(p.id for p in authored[:1]), origin="generated",
                shape=floorplan_mod.shape_for(place_id, URBAN))
    first = replace(authored[0],
                    exits=tuple(authored[0].exits or ()) + (place_id,))
    return (first,) + tuple(authored[1:]) + (way,)


# What an authored settlement of a scale is given when its author listed none of it. The
# owner's ruling of 2026-10-04 (blacksmithing contracts §13.3): "every city gets a smithy,
# even when the world's author did not list one"; and of 2026-10-06 (alchemy plan §21
# open point 7): "every city has a laboratory to rent". Published in
# docs/place-vocabulary.json (`appended_to_authored`) so the author can see it happen and
# write their own instead.
APPENDED_TO_AUTHORED = {"city": ("the smithy", "the laboratory")}


def _with_a_smithy(authored: tuple[Place, ...], here: str,
                   location) -> tuple[Place, ...]:
    """An authored city that lists no smithy gets one appended — the second amendment to
    "an author who listed six rooms has said what the town has", after the way in, and for
    the same kind of reason: it is what the city is FOR in a rule the app runs, not a
    flourish.

    Measured 2026-10-04 on the shipped exports: a smithy in 5 of Aurvantis's 64 authored
    settlements (4 of its 16 cities, 1 of 32 towns, 0 of 16 villages) and in 0 of
    Pangrella's 12 (0 of its 6 cities). The forge's furnace work (Smelt, Alloy, Fold,
    Strengthen, rare metal) needs a smithy (`smithy_here`), so a player in eighteen of
    those twenty-two cities had no town forge to rent. A generated city already has one
    (`ALWAYS_BY_SCALE`); this gives an authored one the same. Towns and villages get one
    only when their own words imply it (`IMPLIED`) or through the `found` door — the
    owner's line, not this function's.

    The laboratory joined 2026-10-06 for the same reason: in 0 of the 22 authored cities
    (0 of all 76 authored settlements) of Aurvantis and Pangrella, while Distill,
    Sublime, Transmute and rare reagents need one (`laboratory_here`). An author's own
    laboratory by any name stands, as long as its kind is one whose keeper is an
    alchemist (`"kind": "laboratory"`, read by `_authored`).

    Attached as the way in is: its exits run to the first place, and the first place
    gains it, so it is reachable (an exit is adjacency, and adjacency runs both ways). In
    a quartered city (`within`), it hangs off the first place's own quarter.
    """
    wanted = APPENDED_TO_AUTHORED.get(scale_of(location), ())
    if not wanted or not _settled(location, "") or not authored:
        return authored
    from dataclasses import replace

    from . import floorplan as floorplan_mod

    out = list(authored)
    for label in wanted:
        row = next((r for r in SETTLEMENT_PLACES if r[0] == label), None)
        if row is None:
            continue
        probe = Place(id="", name=label, about="", terrain=URBAN, exits=())
        tags = place_tags(probe)
        if any(tags & place_tags(p) for p in out if tags):
            continue                        # the author wrote one: theirs stands
        place_id = f"{here}~{URBAN}:{_slug(label)}"
        if any(p.id == place_id for p in out):
            continue
        anchor = out[0]
        out[0] = replace(anchor, exits=tuple(anchor.exits or ()) + (place_id,))
        out.append(Place(id=place_id, name=label, about=row[1], terrain=URBAN,
                         exits=(anchor.id,), within=anchor.within or "",
                         origin="generated",
                         shape=floorplan_mod.shape_for(place_id, URBAN)))
    return tuple(out)


def home_set(location, terrain_hint: str = "") -> tuple[Place, ...]:
    """The location's own places — a settlement's rooms, or a wild site's reaches.

    `location` may be a world entity or a bare id. Only the id is load-bearing: it seeds
    the layout so a town has the same rooms in every session, and the rest sharpens the
    naming when it is available. A settlement is `urban` whatever the continent's facts
    say; a site that is not one stands on `terrain_hint`, which the engine reads off the
    world when it has one and off the party's current place when it does not. With no id
    at all the party still has to be somewhere, so there is exactly one place with no
    exits and no ground — which refuses every move rather than inventing a destination,
    the fail-closed direction.
    """
    here = str(getattr(location, "id", None) or location or "").strip()
    name = str(getattr(location, "name", "") or "").strip()
    if not here:
        return (Place(id="here", name=name or "here", about="", terrain="", exits=()),)
    # The authored list, when the world wrote one. This module has promised since it was
    # written that "when World Bible ships towns and the places in them, an authored list
    # replaces a generated one at `home_set` and nothing else changes" — this is that,
    # and nothing else changes.
    authored = _authored(location)
    if authored:
        return _with_a_smithy(_with_a_way_in(authored, here, location), here, location)
    hint = str(terrain_hint or "").strip().lower()
    if _settled(location, hint):
        return _settlement_set(here, scale_of(location), location)
    return _build(here, hint or "grassland", _WILD)


# Words other settlement vocabularies use for these three sizes. World Bible's generator
# knows six — metropolis, city, town, village, hamlet, outpost — and until 1.15.0 it
# flattened them to this app's three on the way out, so a capital shipped as `city` and
# the distinction was gone before it arrived.
#
# Ruled 2026-09-16: send the six, and this side maps them. A supplier that narrows its
# vocabulary to fit a consumer destroys something it cannot get back, and how many rooms a
# metropolis has is a question about how a scene is built — which is this side's business,
# exactly as `terrain_of` parses an id and never looks anything up. The mapping is the
# same one they were applying; it has simply moved to the end that can change it later.
#
# Everything unrecognised still reads as a town, which is the middle and the commonest,
# and never as a guess dressed up as a village.
SCALE_ALIASES = {
    "metropolis": "city",
    "hamlet": "village",
    "outpost": "village",
    "thorp": "village",
    "small town": "town",
    "large town": "town",
    "small city": "city",
    "large city": "city",
    "settlement": "town",
}


def scale_of(location) -> str:
    """How big the world says this settlement is, in this app's three words.

    The export has written this on every settlement since 1.0 and nothing here read it
    until 2026-09-15 — Aurvantis ships 16 villages, 32 towns and 16 cities, and all 64 of
    them got the same six places.
    """
    said = str(getattr(location, "scale", "") or "").strip().lower()
    if said in PLACES_BY_SCALE:
        return said
    return SCALE_ALIASES.get(said, "town")


def _wanted(scale: str, earned: tuple[tuple[str, str], ...],
            seed: int = 0) -> list[tuple]:
    """Which rows a settlement of this scale gets, in the order it gets them.

    Four passes, and the order is the whole design:

    1. **What this scale always has**, by name — a gate, a guardhouse, a well. A category
       is not specific enough for these: "civic" does not guarantee anybody keeping order,
       and a town with nowhere to be arrested to is a town the wanted state cannot reach.
    2. **What the world's own words earned.** A town whose paragraphs say scribes has a
       library before it has a second warehouse, because the world said so and the table
       did not.
    3. **One of each essential category** — somewhere to buy, to sleep, to be quiet, and
       where nobody is watching. A settlement missing one of those is missing something a
       player will reach for, and "the seed did not pick it" is not an answer.
    4. **Breadth before depth.** Each round takes from the category that has the FEWEST so
       far, so a town gets a gate and stables and a well before it gets a second tavern.
       Walking the categories in name order instead — which the first version did — gave a
       town two hidden places, two faith, no utility and no transport, because `civic` and
       `faith` sort before `transport` and the budget ran out on the way.
    """
    allowed = SCALES[:SCALES.index(scale) + 1]
    rows = [r for r in SETTLEMENT_PLACES if r[2] in allowed]
    by_label = {r[0]: r for r in rows}
    budget = PLACES_BY_SCALE[scale]

    picked: list[tuple] = []
    seen: set[str] = set()
    held: dict[str, int] = {}

    def take(row, capped: bool = True):
        if not row or row[0] in seen or len(picked) >= budget:
            return
        # The cap binds the fill pass only. A place this scale ALWAYS has, or one the
        # world's own words earned, is never refused for being the third of its kind.
        if capped and held.get(row[3], 0) >= CATEGORY_CAP.get(row[3], budget):
            return
        seen.add(row[0])
        held[row[3]] = held.get(row[3], 0) + 1
        picked.append(row)

    for label in ALWAYS_BY_SCALE.get(scale, ()):
        take(by_label.get(label), capped=False)
    for label, _about in earned[:MOST_IMPLIED]:
        take(by_label.get(label), capped=False)
    # The essentials and the fill draw; a row only ever had by name is not on offer to
    # either (`ONLY_WHEN_NAMED`), and is out of the rotation below so its presence moves
    # nothing else.
    rows = [r for r in rows if r[0] not in ONLY_WHEN_NAMED]
    for category in ESSENTIAL_CATEGORIES:
        take(next((r for r in rows if r[3] == category and r[0] not in seen), None),
             capped=False)
    # Within a category, the biggest thing this settlement is entitled to comes first. A
    # city that fills its leisure slot with "the inn" and its hidden slot with "the lane"
    # is a village repeated eighteen times — the first version did exactly that and came
    # out with three hidden places, no theatre and no baths.
    #
    # And WITHIN one floor, rotated by the settlement's own id, or every city in the world
    # is the same city. The first version had no seed anywhere: all sixteen of Aurvantis's
    # cities came out with the same eighteen rooms in the same order. The rotation is
    # inside the floor group so the scale preference still holds — a city varies among
    # city things, never by dropping down to a village thing.
    rank = {name: i for i, name in enumerate(SCALES)}
    ordered: list[tuple] = []
    for floor in reversed(SCALES):
        group = sorted((r for r in rows if r[2] == floor), key=lambda r: r[0])
        if group:
            turn = seed % len(group)
            ordered.extend(group[turn:] + group[:turn])
    rows = ordered
    categories = sorted({r[3] for r in rows})
    while len(picked) < budget:
        thinnest = sorted(categories, key=lambda c: (held.get(c, 0), c))
        before = len(picked)
        for category in thinnest:
            take(next((r for r in rows if r[3] == category and r[0] not in seen), None))
            if len(picked) >= budget:
                break
        if len(picked) == before:
            break                       # the scale has fewer rows than budget; that is fine
    return picked


def _settlement_set(location_id: str, scale: str, location) -> tuple[Place, ...]:
    """A settlement's places: as many as its scale says, and quartered if it is a city."""
    rows = _wanted(scale, implied_spots(location), _seed(location_id))
    prefix = region_key(location_id, URBAN)
    made = [(f"{prefix}:{_slug(label)}", label, about) for label, about, *_ in rows]
    if scale == "city":
        return _districted(prefix, made)
    ids = [pid for pid, _l, _a in made]
    return tuple(
        Place(id=pid, name=label, about=about, terrain=URBAN,
              exits=tuple(x for x in ids if x != pid))
        for pid, label, about in made
    )


# How many quarters a city is cut into, and therefore how wide its prompts get. Four plus a
# centre keeps every list at or under six: the square sees four crossings, a crossing sees
# the square and its own handful, a room sees its crossing and its neighbours.
CITY_QUARTERS = 4
_QUARTERS = ("the north crossing", "the east crossing", "the south crossing",
             "the west crossing")

# The junctions a settlement of each scale adds ON TOP of its rooms: the great square and
# its crossings. Published, because a checker on the other side cannot otherwise work out
# what a legal total looks like — and because this app's own checker could not either.
#
# Measured 2026-09-16, reported by the World Bible side and reproduced here against this
# app's OWN generator: a generated city is 18 rooms plus these 5, and `check_places.py`
# compared all 23 against a ceiling of 18 and noted every quartered city in both worlds.
# Twenty-two notes across two exports, every one of them wrong. The rule was already
# written down — "a crossing is structure, not something the town has" — and honoured in
# one of the two places that count places, which is the same two-counts-of-one-thing
# defect that produced the two different sixes in September.
JUNCTIONS_BY_SCALE = {"village": 0, "town": 0, "city": 1 + CITY_QUARTERS}


def _districted(prefix: str, made: list[tuple[str, str, str]]) -> tuple[Place, ...]:
    """A city as a centre, four crossings, and the rooms hanging off them.

    Eighteen rooms in one flat list is eighteen exits in one prompt, which is exactly what
    Fate's two-to-four zones and Inform's "small number of named positions" are about. So a
    city is not a list, it is a shape: `the great square` at the middle, four crossings off
    it, and each quarter's rooms off their crossing. Two or three hops from anywhere to
    anywhere, and nothing ever offers more than six ways on.

    **A crossing is a real room.** It is a street junction you can stand in, be described
    in and fight in — it has a floor plan like everything else. There is no district
    object and no new kind of thing, which is what keeps "a place is one room, not a
    building, and not a district" true.

    `within` is what carries the shape. It is the field World Bible asked for on
    2026-09-15, generated here first so the design is proved by something that runs before
    anybody authors to it.
    """
    square_id = f"{prefix}:{_slug('the great square')}"
    crossings = [(f"{prefix}:{_slug(q)}", q) for q in _QUARTERS[:CITY_QUARTERS]]
    # Round robin, so a quarter is a mix rather than all the trades in one corner.
    quarters: list[list[tuple[str, str, str]]] = [[] for _ in crossings]
    for i, row in enumerate(made):
        quarters[i % len(crossings)].append(row)

    out = [Place(id=square_id, name="the great square",
                 about="the middle of it, and everything comes through here",
                 terrain=URBAN, exits=tuple(cid for cid, _q in crossings))]
    for (cid, label), rooms in zip(crossings, quarters):
        room_ids = [pid for pid, _l, _a in rooms]
        out.append(Place(id=cid, name=label,
                         about="a junction, and the way into this quarter",
                         terrain=URBAN, within=square_id,
                         exits=(square_id, *room_ids)))
        for pid, rlabel, rabout in rooms:
            out.append(Place(id=pid, name=rlabel, about=rabout, terrain=URBAN,
                             within=cid,
                             exits=(cid, *(x for x in room_ids if x != pid))))
    return tuple(out)


def _authored(location) -> tuple[Place, ...]:
    """The places the world wrote for this location, or () when it wrote none.

    Door one and only door one. Founded and ventured places still join in `for_scene`
    exactly as they did, and the implied-spot table is not consulted — an author who
    listed six rooms has said what the town has, and adding a docks to it because the
    prose says "port" would be the generator arguing with them.

    Fails soft, one place at a time. An id that does not carry its ground is dropped
    rather than made into a place standing on nothing, because `terrain_of` parses the id
    and a place with no terrain gets an empty twenty-by-twenty field to fight in.
    `tools/check_places.py` reports exactly that before an export ships; this is what
    happens if one gets through anyway, and losing one room beats playing on a blank one.
    """
    from . import floorplan

    out: list[Place] = []
    for raw in getattr(location, "places", None) or ():
        if not isinstance(raw, dict):
            continue
        pid = str(raw.get("id") or "").strip()
        ground = terrain_of(pid)
        if not pid or not ground:
            continue
        out.append(Place(
            id=pid,
            name=str(raw.get("name") or "").strip() or pid.rsplit(":", 1)[-1],
            about=str(raw.get("about") or "").strip(),
            terrain=ground,
            exits=tuple(str(x) for x in (raw.get("exits") or []) if str(x).strip()),
            described_only=bool(raw.get("described_only")),
            # A room another room hangs off, when the world says so. Dropped rather than
            # kept when it names something that is not a place in this settlement: a
            # `within` pointing nowhere would put a room in a quarter that does not exist.
            within=str(raw.get("within") or ""),
            parent=str(raw.get("parent") or ""),
            # What it IS, when the world says so and the app knows the kind: "the
            # Glasshouse" with `"kind": "laboratory"` is a laboratory, its keeper an
            # alchemist. Promised to World Bible since 2026-10-04 ("the Anvil" with
            # `"kind": "smithy"`, docs/places-and-races-for-world-bible.md) and read by
            # nothing until 2026-10-06: an authored place's kind was its name or nothing,
            # so a world's own smithy by another name got a second one appended. A kind
            # the app does not know is dropped, never guessed at — the name still reads.
            kind=_authored_kind(raw.get("kind")),
            # How big, how cluttered, what the going is, how it is shaped upward — the
            # world's own answer where it wrote one, read through `floorplan` because
            # feet and squares are its units. The ground the table would have given is
            # passed in so the tell's phrase survives: the export's `about` is a line
            # about the settlement, not about the floor.
            shape=floorplan.from_world(
                raw, floorplan.shape_for(pid, ground)),
            floors=_floors(raw.get("storeys")),
            # Everything from the world says so, whatever the file claims: `origin` is
            # provenance, and a export that wrote "found" would otherwise hand the party
            # a place the engine believes they built themselves.
            origin="world",
        ))
    return tuple(out)


def _authored_kind(said) -> str:
    """An authored place's `kind`, folded through the kind words ("forge" → "smithy"),
    or "" when the app has no such settlement kind. Read only, never invented."""
    kind = kind_named(str(said or ""))
    return kind if kind in KINDS or kind in DWELLINGS else ""


def implied_spots(location) -> tuple[tuple[str, str], ...]:
    """The spots a settlement's own facts and paragraphs imply, in table order."""
    facts = getattr(location, "facts", None) or {}
    prose = getattr(location, "prose", "") or ""
    text = " ".join([*(str(v) for v in facts.values()), str(prose)]).lower()
    words = set(_WORDS.findall(text))
    out = []
    for cues, spot in IMPLIED:
        if any(_cue_fires(c, text, words) for c in cues):
            out.append(spot)
    return tuple(out)


def _cue_fires(cue: str, text: str, words: set) -> bool:
    """Whether one cue is in this settlement's words.

    A single word is asked of the word SET, which is what this always did and is why a
    cue can never match half of a longer word. A cue with a space in it is asked of the
    text, because a set of single words cannot answer a two-word question — and two-word
    cues are the whole reason this function exists. See the note under `IMPLIED`.
    """
    if " " in cue:
        return _re.search(rf"\b{_re.escape(cue)}\b", text) is not None
    return cue in words


def region_set(location_id: str, terrain: str) -> tuple[Place, ...]:
    """Open ground of one kind around a location: the forest outside the town.

    Derivable with nothing but the location id and a biome word, so a world-less test
    engine can stand in the forest and a save that predates places can be healed onto
    the ground it recorded.
    """
    # "nowhere" rather than the exitless fallback: a scene with no location can still
    # be stood on real ground for the foraging tables, and the id has to say which.
    here = str(getattr(location_id, "id", None) or location_id or "").strip() or "nowhere"
    return _build(here, str(terrain or "").strip().lower() or "grassland", _WILD)


def for_scene(location, at: str, terrain_hint: str = "",
              founded=(), ring=()) -> tuple[Place, ...]:
    """Every place the party can name from where they stand: home, plus the ground
    they are on if it is not home, plus what play has minted here (`founded`).

    The ONE derivation. `Engine.places()` and the scene brief both used to compute this
    separately — two copies of a rule, the trap CLAUDE.md names — and now both call here.
    Region places share the `_WILD` names, and only one region is ever current, so a
    name resolves to one place.

    Minted places are the stored exception to "derived, never stored" — they cannot be
    derived, since the player made them — and they join here by parent: a place hangs
    off the one it was made from, the parent gains an exit to it, and a name resolves
    against where the party stands, so "the alley" by the market and "the alley" by the
    library are two places with one word between them (LambdaMOO's rule: a room exists
    because it was dug from somewhere, with an owner and a link).

    `ring` is the settlement's outside places (`rules/outskirts.py`), handed in by the
    caller that has a world — this module has none. They join the home set with their
    exits both ways, so the gate leads out to the outskirts and the outskirts back in. A
    region of open ground joins only when the party stands on one of its reaches (never
    for standing on the ring: the fields are farmland, and grafting a farmland wilderness
    onto them would put "the heart of it" beside the fields), and its first reach is
    joined to the outskirts so the way back is walked, not jumped.
    """
    home = home_set(location, terrain_hint)
    ground = terrain_of(at)
    ring = tuple(ring or ())
    base = _with_ring(home, ring) if ring else home
    ids = {p.id for p in base}
    if is_ring(at) and len(_spot_path(at)) == 1 and at not in ids:
        # Stood on the outside by an engine that cannot build the ring (no world to hand):
        # the place is still real, and the id says enough to stand on it. A stretch of
        # road a journey stopped on is the case that matters — `place_party` validates
        # against this set.
        base = base + (Place(id=at, name="on the road" if "along-" in at else "outside",
                             about="", terrain=ground, exits=()),)
    elif not ground or ground == home[0].terrain or is_ring(at):
        pass
    elif home[0].id == "here":
        # No location at all, but the party has been stood on named ground: that
        # ground is all there is.
        base = region_set(location_of(at), ground)
    else:
        region = region_set(location_of(at), ground)
        outskirts = next((p for p in ring if p.name == "the outskirts"), None)
        if outskirts is not None and region:
            region = (_replace(region[0], exits=tuple(region[0].exits) + (outskirts.id,)),
                      ) + tuple(region[1:])
            base = tuple(_replace(p, exits=tuple(p.exits) + (region[0].id,))
                         if p.id == outskirts.id else p for p in base)
        base = base + region
    return with_founded(with_storeys(base), founded, at)


def _with_ring(home: tuple[Place, ...], ring: tuple[Place, ...]) -> tuple[Place, ...]:
    """The home set with the ring beside it, every town room a ring place names in its
    exits gaining the way back out — adjacency runs both ways (`_with_a_way_in`)."""
    ring_ids = {p.id for p in ring}
    back: dict[str, list[str]] = {}
    for p in ring:
        for x in p.exits:
            if x not in ring_ids:
                back.setdefault(x, []).append(p.id)
    joined = tuple(_replace(p, exits=tuple(p.exits) + tuple(
        x for x in back[p.id] if x not in p.exits)) if p.id in back else p for p in home)
    return joined + tuple(ring)


def with_storeys(base: tuple["Place", ...]) -> tuple["Place", ...]:
    """Every place in `base`, plus the floors of any of them that has floors.

    The ground floor gains its stairs as exits so the move vocabulary IS the exit list,
    which is the one thing every tradition surveyed agreed on. Added here rather than in
    `home_set` because a storey is reachable from where the party stands and `for_scene`
    is the one derivation of that — the same reasoning that put founded places here.
    """
    out = list(base)
    for place in base:
        if storey_of(place.id):
            continue                       # already a floor; do not stack floors on it
        upstairs = storey_set(place)
        if not upstairs:
            continue
        # `replace`, not a fresh `Place` with the fields typed out. Written out by hand
        # this dropped every field nobody remembered to list: `within` has been lost here
        # since districts arrived — a roofed room in a city quarter came back out of this
        # hanging off nothing — and the authored `shape` would have been the next one,
        # which would have handed an upstairs-having room back to the generic table it
        # was just read out of. One line that cannot go stale beats six that can.
        out[out.index(place)] = _replace(
            place, exits=tuple(place.exits) + tuple(p.id for p in upstairs
                                                    if abs(storey_of(p.id)) == 1))
        out.extend(upstairs)
    return tuple(out)


def with_founded(base: tuple[Place, ...], founded, at: str = "") -> tuple[Place, ...]:
    """Graft the minted places whose parent is in `base` — or whose parent is a minted
    place already grafted, or who ARE where the party stands — onto the set, wiring
    exits both ways. Minted places elsewhere in the world stay off the list, which is
    what keeps the model's choice small."""
    minted = [p if isinstance(p, Place) else from_dict(p) for p in (founded or ())]
    if not minted:
        return base
    out = {p.id: p for p in base}
    changed = True
    while changed:
        changed = False
        for m in minted:
            if m.id in out:
                continue
            reachable = (m.parent in out) or (at and (m.id == at or str(at).startswith(m.id + "/")))
            if not reachable:
                continue
            out[m.id] = m
            changed = True
    # Exits both ways between a minted place and its parent, and between a minted
    # place's own children and it; the derived set's exits are left as they were.
    result: dict[str, Place] = {}
    for pid, p in out.items():
        exits = list(p.exits)
        for q in out.values():
            if q.parent == pid and q.id != pid and q.id not in exits:
                exits.append(q.id)
        if p.parent and p.parent in out and p.parent not in exits:
            exits.append(p.parent)
        # Only the exits change. This rebuilt the Place field by field and dropped
        # every field it did not name — `shape`, `floors`, `within`, and then `kind`
        # the day it was added (2026-09-23) — so a town with one founded place lost
        # the authored floor plans of all its others, and a founded tavern lost what
        # made it a tavern the moment it was read back.
        result[pid] = _replace(p, exits=tuple(exits))
    return tuple(result.values())


def children_of(founded, parent_id: str) -> list[Place]:
    minted = [p if isinstance(p, Place) else from_dict(p) for p in (founded or ())]
    return [p for p in minted if p.parent == parent_id]


# --- a place's own ground ----------------------------------------------------------------
#
# "on a mountain still considered farmland" (the owner, 2026-10-05). "i go up the
# mountain" from the road to Grotburrow planned `found name="the mountain"` (its first try,
# `kind="mountain"`, was refused as no kind of place) and then `travel`; `mint` gave the
# child its parent's ground, so the id read `~farmland`, the header said "Farmland", the
# UNDERFOOT line said "open, with a wall or a hedge to it", and the narrator — told nothing
# about a mountain — wrote boulders "weathered by the desert sun".
#
# How the traditions do it: a DikuMUD/CircleMUD room carries its own sector type, one
# required number from a closed list, per room and never inherited from its zone (CircleMUD
# Builder's Manual, World Files: "A single number ... defining the type of terrain in the
# room"). Hexcrawl generators give a sub-hex the parent hex's dominant terrain as the
# default and let a feature inside it differ (DIY & Dragons, "Sub-Hex Crawling Mechanics
# part 2": roll the dominant terrain first, then the sub-hexes off a menu for it; Lesserton
# & Mor's seven independent rolls per sept-hex were the variability it set out to remove).
# Fate puts aspects on each zone, not on the scene alone. So: the place's own words name
# its ground from the closed biome list, and only a place whose words name none takes its
# parent's.
#
# A lexicon of its own rather than `biomes._LOOKUP`: that table reads bestiary and world
# prose, where "garden" is farmland, "market" is urban and "graveyard" is ruins — words
# that in a place's NAME mean a building in town. These are nouns a place out in the land
# is called by, and nothing else.
#
# Water is the bank of it. A place called "the river" is where the party stands beside the
# river, not in it: `water` is a place you swim in (biomes.py), and the move into it is a
# move between two places, as a storey is.
PLACE_GROUND: dict[str, str] = {
    "mountain": "mountain", "mountains": "mountain", "mountainside": "mountain",
    "peak": "mountain", "peaks": "mountain", "crag": "mountain", "crags": "mountain",
    "cliff": "mountain", "cliffs": "mountain", "summit": "mountain",
    "scree": "mountain", "volcano": "mountain",
    "hill": "hills", "hills": "hills", "hillside": "hills", "hilltop": "hills",
    "foothills": "hills", "downs": "hills", "moor": "hills", "moors": "hills",
    "moorland": "hills", "upland": "hills", "uplands": "hills", "highlands": "hills",
    "tor": "hills", "knoll": "hills",
    "forest": "forest", "forests": "forest", "woods": "forest", "woodland": "forest",
    "woodlands": "forest", "grove": "forest", "glade": "forest", "copse": "forest",
    "thicket": "forest", "treeline": "forest",
    "jungle": "jungle", "rainforest": "jungle",
    "swamp": "swamp", "swamps": "swamp", "marsh": "swamp", "marshes": "swamp",
    "bog": "swamp", "fen": "swamp", "fens": "swamp", "mire": "swamp",
    "wetland": "swamp", "wetlands": "swamp", "quagmire": "swamp",
    "desert": "desert", "dunes": "desert", "dune": "desert", "badlands": "desert",
    "wastes": "desert", "wasteland": "desert", "sands": "desert", "hardpan": "desert",
    "tundra": "tundra", "snowfield": "tundra", "icefield": "tundra", "glacier": "tundra",
    "coast": "coast", "shore": "coast", "shoreline": "coast", "beach": "coast",
    "strand": "coast", "cove": "coast", "riverbank": "coast", "riverside": "coast",
    "lakeside": "coast", "lakeshore": "coast", "waterside": "coast", "river": "coast",
    "stream": "coast", "brook": "coast", "creek": "coast", "lake": "coast",
    "pond": "coast", "tarn": "coast", "waterfall": "coast",
    "plains": "grassland", "plain": "grassland", "meadow": "grassland",
    "meadows": "grassland", "steppe": "grassland", "prairie": "grassland",
    "heath": "grassland", "heathland": "grassland", "grassland": "grassland",
    "grasslands": "grassland", "savanna": "grassland", "scrub": "grassland",
    "scrubland": "grassland",
    "farmland": "farmland", "fields": "farmland", "field": "farmland",
    "orchard": "farmland", "orchards": "farmland", "pasture": "farmland",
    "pastures": "farmland", "vineyard": "farmland", "farm": "farmland",
    "cave": "underground", "caves": "underground", "cavern": "underground",
    "caverns": "underground", "grotto": "underground", "tunnel": "underground",
    "tunnels": "underground", "mine": "underground", "mineshaft": "underground",
    "underground": "underground",
    "ruin": "ruins", "ruins": "ruins", "barrow": "ruins", "barrows": "ruins",
    "tomb": "ruins", "crypt": "ruins", "catacombs": "ruins", "battlefield": "ruins",
}
# Compound-aware, as `geography.ground_in` is: "Grotburrow" holds no burrow and the
# "mine head" no mine, because a letter or a hyphen either side refuses the match.
_PLACE_GROUND_RE = _re.compile(
    r"(?<![\w-])(" + "|".join(sorted(map(_re.escape, PLACE_GROUND), key=len, reverse=True))
    + r")(?![\w-])")
# The ground a place is OUTSIDE, as opposed to under a town: what lets an id with other
# ground and a long spot path still parse as outside (`setting_of`).
OPEN_GROUND = frozenset({"grassland", "farmland", "forest", "jungle", "swamp", "hills",
                         "mountain", "desert", "tundra", "coast"})


# Kind words that are as often an adjective or a landform in a name: "the green hills",
# "the sand bar", "the salt flat".
_NOT_A_BUILDING = frozenset({"green", "bar", "flat"})


def _building_named(text: str) -> bool:
    """Whether a name is a building's: the settlement table's kinds, a house, and every
    word people say for one. "the Forest Inn" is an inn, not a forest; "the hut on the
    hill" is a house."""
    words = {*KINDS, *DWELLINGS, *KIND_WORDS} - _NOT_A_BUILDING
    low = " ".join(str(text or "").lower().split())
    return any(_re.search(r"(?<![\w-])" + _re.escape(w) + r"(?![\w-])", low)
               for w in words if w)


def ground_named(text: str) -> str:
    """The ground a place's own words name, from the closed biome list, or "".

    The first ground word in the text wins, because a place's head noun comes first: "the
    cave in the hills" is a cave. A building's name names no ground (`_building_named`),
    and nothing here is ever `urban` — a settlement's ground is urban by construction.
    """
    low = " ".join(str(text or "").lower().split())
    if not low or _building_named(low):
        return ""
    m = _PLACE_GROUND_RE.search(low)
    return PLACE_GROUND[m.group(1)] if m else ""


def own_ground(name: str, about: str = "", kind: str = "") -> str:
    """The ground a place made in play stands on by its own words, or "" to take its
    parent's: its kind when the kind names ground ("mountain"), else its name, else what
    it was said to be. A place with a building's kind is a building and names none."""
    k = kind_named(kind)
    if k and (k in KINDS or k in DWELLINGS or k in OUTSIDE_KINDS):
        return ""
    return ground_named(k) or ground_named(name) or ground_named(about)


def ground_kind(kind: str) -> str:
    """The ground a plan's `kind` names when it is not a kind of place: "mountain"."""
    k = kind_named(kind)
    return "" if known_kind(k) else PLACE_GROUND.get(k, "")


def child_id(parent_id: str, label: str) -> str:
    """`{parent}/{slug}`: the id of a place made from another. The ground stays the
    parent's unless the child says otherwise — `terrain_of` reads the head."""
    return f"{parent_id}/{_slug(label)}"


def mint(parent: Place, label: str, about: str = "", *, terrain: str = "",
         owner: str = "", origin: str = "found", kind: str = "") -> Place:
    """A new place made from `parent`. The id carries the parent; the ground is the
    parent's unless given. `exits` are wired by `with_founded` at read time."""
    ground = str(terrain or "").strip().lower() or parent.terrain
    pid = child_id(parent.id, label)
    if ground and ground != parent.terrain and origin != "venture" \
            and setting_of(parent.id) == "outside":
        # Other ground out past the edge: the mountain off the road to Grotburrow. The
        # head carries the new ground and the spot keeps the parent's whole path, so
        # the id still parses as outside (`@` at its root, or a reach of open ground),
        # a road's stretch still reads as that road, and `for_scene` does not graft a
        # second wilderness of that ground beside it.
        #
        # Not for a venture, whose ids are seeded and saved: the cave off the outskirts
        # is `~underground:the-outskirts/the-cave` in every save that went in, and
        # minting it under a new id would make a second cave the next time.
        spot = "/".join(_spot_path(parent.id))
        pid = f"{region_key(location_of(parent.id), ground)}:{spot}/{_slug(label)}"
    elif ground and ground != parent.terrain:
        # A different ground under the same roof: the sewers under a town. The head of
        # the id says so, so `scene.biome` parses right when the party is down there.
        pid = f"{region_key(location_of(parent.id), ground)}:{_slug(parent.name)}/{_slug(label)}"
    kind = str(kind or "").strip().lower().removeprefix("the ")
    return Place(id=pid, name=label, about=about, terrain=ground, exits=(),
                parent=parent.id, owner=owner, origin=origin, kind=kind,
                shape=shape_of_kind(kind, ground))


# --- a place the page needs ---------------------------------------------------------------
#
# Ruled 2026-09-23, reversing the item-45 rule that a place the narrator names and the
# settlement does not list is an invention to be rewritten away: *"i dont mind it creating
# a dock so long as it remembers that it has a dock and remembers the tavern it put there
# ... what matters is the places being remembered, interesting, and at least make sense to
# be where they are."* The picture behind it was Vormoor's own opening — a village rising
# from the water on coral and driftwood stilts — beside a beat that had walked the player
# to the docks. A dock there makes sense. So a place is founded rather than refused, IF it
# makes sense, and this is the "makes sense": the kind has to be one the settlement table
# knows, the settlement has to be big enough for it, and a kind that needs water needs
# water. LambdaMOO's `@dig` is still the shape — a room exists because something created
# it — the page is now allowed to be that something, through the one door.
KINDS: dict[str, tuple] = {row[0].removeprefix("the "): row for row in SETTLEMENT_PLACES}

# Kinds a place can be FOUNDED as but that a settlement is never drawn with: somebody's
# house. Measured 2026-10-01, the owner's own turn and again on the scratch copy: "I take
# the key and head to the house 3 streets over" planned `found kind=house` then `travel`,
# and the engine answered "There is no such kind of place as 'house'" — the commonest
# building in any town was the one kind the table did not have, so the walk was refused
# and the prose walked the player there anyway. Not a SETTLEMENT_PLACES row: that table is
# also what a town's rooms are drawn from, and a new row would re-draw every world's
# towns. Any settlement has houses, so there is no scale to check.
DWELLINGS: dict[str, str] = {
    "house": "somebody's house, and whoever lives in it",
}
# The words a plan writes for a house, folded to the kind. The kind is the vocabulary;
# these are how people say it.
KIND_WORDS: dict[str, str] = {
    "home": "house", "cottage": "house", "residence": "house", "dwelling": "house",
    "townhouse": "house", "town house": "house", "hovel": "house", "shack": "house",
    "hut": "house", "manor": "house", "manor house": "house", "mansion": "house",
    "lodging": "house", "lodgings": "house", "apartment": "house", "flat": "house",
    "rooms": "house", "pub": "tavern", "alehouse": "tavern", "bar": "tavern",
    "alley": "lane", "alleyway": "lane", "shop": "workshops", "store": "workshops",
    "chapel": "shrine", "church": "temple", "jail": "gaol", "prison": "gaol",
    "stable": "stables", "warehouse": "warehouses", "dock": "docks", "harbour": "docks",
    "harbor": "docks", "cemetery": "graveyard",
    # A smith's place, said the ways people say it, so a plan's `found kind="forge"` mints
    # a smithy (blacksmithing plan §10: "your own smithy, founded through the places
    # system's `found` door"). Not "smith": that is the person, and `_said_as` reads these
    # as words naming a PLACE — "the smith hands you the tongs" would have the prose
    # standing in the smithy.
    "forge": "smithy", "blacksmith's": "smithy", "smithy's": "smithy",
    "ironworks": "smithy", "foundry": "smithy",
    # An alchemist's place, the same way (alchemy plan §14: "your own laboratory, founded
    # through the places system's `found` door"). Not "alchemist": that is the person —
    # and the market's alchemist counter. Not "apothecary": that is the herbal healer's
    # shop (content/people/occupations.json `healer`), and herbalism's. Not "alchemist's"
    # alone: "the alchemist's hands shake" names a person, and these are read as words
    # naming a PLACE (`_said_as`).
    "lab": "laboratory", "alchemy lab": "laboratory", "alchemist's lab": "laboratory",
    "alchemist's laboratory": "laboratory", "alchemical laboratory": "laboratory",
    "alchemists' laboratory": "laboratory",
}


def kind_named(kind: str) -> str:
    """The kind a plan's word names: "the cottage" → "house", "pub" → "tavern"."""
    k = " ".join(str(kind or "").split()).lower().removeprefix("the ")
    return KIND_WORDS.get(k, k)


def known_kind(kind: str) -> bool:
    """Whether a place can be founded as this kind anywhere at all."""
    k = kind_named(kind)
    return k in KINDS or k in DWELLINGS or k in OUTSIDE_KINDS


def kinds_said() -> str:
    """The vocabulary, for a refusal that names the fix."""
    return (f"{', '.join(sorted({*KINDS, *DWELLINGS}))}; and out on the road: "
            f"{', '.join(sorted(OUTSIDE_KINDS))}")


def _said_as(place) -> list[str]:
    """The words one place is called by: its name, and for a founded place its kind and
    every word people say for that kind ("tavern", "pub", "alehouse", "bar")."""
    out = [" ".join(str(getattr(place, "name", "") or "").split()).lower()
           .removeprefix("the ").strip()]
    kind = kind_named(getattr(place, "kind", "") or "")
    if kind:
        out.append(kind)
        out.extend(w for w, k in KIND_WORDS.items() if k == kind)
    return [w for w in out if w]


def words_for_here(place, known=(), outside: bool = True) -> tuple[str, ...]:
    """Every word that names where somebody standing in `place` is, lower-case and
    without its article: its own name and kind, then the same for each place it stands
    in, up the `parent` chain — the chamber is in the Velvet Veil, which is a tavern,
    which opens off the gate.

    Measured on the owner's save of 2026-10-01: 13 of the 17 `stands-elsewhere` findings
    were "there is no tavern in this place at all" while the party stood in the Velvet
    Veil — a place founded with `kind="tavern"` — or in its chamber. The prose naming
    the tavern was naming where they were. `parent` is followed only through places in
    `known`; a generated room's parent is the world entity, which is not a place.

    `outside=False` stops at the first parent that is a settlement room rather than a
    founded building: in the Velvet Veil you are in the tavern, but standing "before the
    gate" it opens off is having walked out of it — which is what the refused-move
    check needs to tell apart. The first word is always the place's own name.
    """
    by_id = {getattr(p, "id", ""): p for p in known or ()}
    out: list[str] = []
    seen: set[str] = set()
    at = place
    while at is not None and getattr(at, "id", "") not in seen:
        seen.add(getattr(at, "id", ""))
        out.extend(w for w in _said_as(at) if w not in out)
        at = by_id.get(getattr(at, "parent", "") or "")
        if at is not None and not outside and not getattr(at, "kind", ""):
            break
    return tuple(out)


def kinds_of(known) -> tuple[str, ...]:
    """The kinds of the founded places in `known`, with the words said for each: a town
    with the Velvet Veil in it has a tavern, though no place in it is NAMED the tavern."""
    out: list[str] = []
    for p in known or ():
        if getattr(p, "kind", ""):
            out.extend(w for w in _said_as(p)[1:] if w not in out)
    return tuple(out)

# Kinds that stand on water, and the words a settlement is described with when it has
# some. The generator's own cues (`IMPLIED`) are read first; these are the words a
# tide-and-stilt village gets described with instead — Vormoor's export says "coral and
# driftwood stilt-housing" and "water rights", and neither is a harbour word.
WATER_KINDS = frozenset({"docks", "bridge"})
_WATER_WORDS = frozenset({"water", "tide", "tides", "tidal", "stilt", "stilts", "coast",
                          "coastal", "sea", "shore", "lake", "estuary", "marsh", "canal",
                          "canals", "reef", "lagoon"})


def fits_here(kind: str, location, parent=None) -> str:
    """Why a place of this kind cannot be founded in this settlement, or "" when it can.

    A reason in words, because it becomes a refusal the plan can repair and a note the
    reviewer can quote. One step of scale is allowed upward — a village may have a
    town's inn — and not two: a village with a cathedral is the kind of place the
    ruling said had to "at least make sense".

    `parent` is the place it would hang off, and it decides the road's kinds
    (`OUTSIDE_KINDS`): a crossroads off the outskirts is a crossroads; a crossroads off
    the market is refused with the fix named — "go to the outskirts first" — because a
    crossroads is not in a town (the owner's ruling Q11). A bridge off a town room is
    the settlement's bridge, as it always was.
    """
    kind = kind_named(kind)
    outside = parent is not None and setting_of(getattr(parent, "id", "") or "") == "outside"
    if kind in DWELLINGS:
        name = str(getattr(location, "name", "") or "this place")
        if location is None or not _settled(location, ""):
            return f"{name} is not a settlement, and a {kind} is a settlement's place."
        return ""
    if kind in OUTSIDE_KINDS and (outside or kind not in KINDS):
        if not outside:
            where = str(getattr(parent, "name", "") or "the town") if parent is not None \
                else "the town"
            return (f"A {kind} is out on the road, not in {where}: go to the outskirts "
                    f"first, and it can be found from there.")
        if kind in _OUTSIDE_WATER:
            ground = str(getattr(parent, "terrain", "") or "")
            facts = getattr(location, "facts", None) or {}
            prose = getattr(location, "prose", "") or ""
            text = " ".join([*(str(v) for v in facts.values()), str(prose)]).lower()
            if ground not in ("coast", "swamp", "water") \
                    and not (set(_WORDS.findall(text)) & (_WATER_WORDS | {"river", "ford",
                                                                          "stream"})):
                name = str(getattr(location, "name", "") or "here")
                return f"Nothing the world says about {name} puts water across its roads."
        return ""
    row = KINDS.get(kind)
    if row is None:
        return f"There is no such kind of place as {kind!r}. The kinds are: {kinds_said()}."
    name = str(getattr(location, "name", "") or "this place")
    if location is None or not _settled(location, ""):
        return f"{name} is not a settlement, and a {kind} is a settlement's place."
    scale = scale_of(location)
    have = SCALES.index(scale) if scale in SCALES else 0
    need = SCALES.index(row[2]) if row[2] in SCALES else 0
    if need > have + 1:
        return f"A {scale} does not have a {kind}: that is a {row[2]}'s place."
    if kind in WATER_KINDS:
        facts = getattr(location, "facts", None) or {}
        prose = getattr(location, "prose", "") or ""
        text = " ".join([*(str(v) for v in facts.values()), str(prose)]).lower()
        words = set(_WORDS.findall(text))
        cues = next((c for c, spot in IMPLIED if spot[0] == f"the {kind}"), ())
        if not (any(_cue_fires(c, text, words) for c in cues) or words & _WATER_WORDS):
            return f"Nothing the world says about {name} puts water under a {kind}."
    return ""


def venture_set(parent: Place, kind: str) -> list[Place]:
    """The places a venture of `kind` from `parent` is made of: the venture itself and
    its seeded spots, all hanging off it. Generated on entry from the parent's id, so
    the same stairs lead to the same cellar next time."""
    spec = VENTURES[kind]
    head = mint(parent, spec["label"], f"{kind} off {parent.name}",
                terrain=spec["terrain"], origin="venture")
    spots = list(spec["spots"])
    if spots:
        n = max(1, min(len(spots), 2 + _seed(head.id) % max(1, len(spots) - 1)))
        spots = spots[:n]
    out = [head]
    for label, about in spots:
        out.append(Place(id=child_id(head.id, label), name=label, about=about,
                         terrain=head.terrain, exits=(), parent=head.id, origin="venture"))
    return out


def spots_for(location, terrain: str = "") -> tuple[Place, ...]:
    """The location's own places. Kept as the name stage 8a shipped under; `home_set`
    is the same function and the docstring lives there."""
    return home_set(location, terrain)


def find(places, wanted: str) -> Place | None:
    """The place the GM means, by id or by name, or None.

    Matched leniently on the way in and refused hard on the way out: "market", "the
    market" and the raw id all mean the same place, and anything else means none of them.
    """
    want = " ".join(str(wanted or "").split()).lower()
    if not want:
        return None
    for p in places or ():
        if want in (p.id.lower(), p.name.lower(), p.name.lower().removeprefix("the ")):
            return p
    # The GM's own dressing of a real place: "the merchant's gate" for "the gate", "the
    # old market" for "the market". Measured at the table, 2026-09-06: the plan wrote
    # `travel` to "the merchant's gate", the exact match failed, and the turn was a 502.
    # The last word decides, and only when exactly one place ends in it — "the back
    # streets" and "the street" would otherwise be a coin toss.
    head = want.split()[-1].rstrip("s") if want.split() else ""
    if len(head) >= 3:
        ending = [p for p in places or ()
                  if (p.name.lower().split() or [""])[-1].rstrip("s") == head]
        if len(ending) == 1:
            return ending[0]
    return None


def route(places, start: str, dest: str) -> tuple[str, ...]:
    """The way from one place to another, hop by hop, or () if there is none.

    The `exits` field has been the move vocabulary since this module was written and
    nothing has ever walked it. Measured 2026-09-21, live: the party stood at the
    roadside, said "I head into the city", and arrived at the market — a place two hops
    away through the gate and the square — with the prose describing a single step. The
    engine's own refusal for a multi-travel plan says why it cannot do better: "the
    engine has no route-finder to walk it there".

    This is that route-finder, and the tradition is unanimous about whose job it is.
    Inform ships `the best route from X to Y`, and its Recipe Book examples (Misadventure,
    Safari Guide) take ONE named room and derive the path themselves; Angband and DCSS
    compute the path to a named destination and walk it, interruptibly. In every one of
    them the traveller names a destination and the system finds the way. Here the model
    was being asked to hand over the way itself, which is the one thing it cannot know.

    Breadth-first, so the way returned is the shortest one, and ties break on the order
    the exits were written — which is stable, because the places are generated from the
    location's own durable id.

    Returns the hops AFTER `start`, ending at `dest`. An unreachable destination gives
    (), which is not the same as "no route exists to anywhere": measured across the two
    shipped worlds, 40 of 10,792 place pairs in Aurvantis have no path at all and eight
    exit links are one-way, so a caller that refused on () would refuse moves that work
    today. The caller's floor is the direct step it already took.
    """
    by = {p.id: p for p in places or ()}
    if start not in by or dest not in by or start == dest:
        return ()
    from collections import deque

    came: dict[str, str] = {start: ""}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        if cur == dest:
            break
        for nxt in by[cur].exits:
            if nxt in by and nxt not in came:
                came[nxt] = cur
                queue.append(nxt)
    if dest not in came:
        return ()
    walk = [dest]
    while came[walk[-1]]:
        walk.append(came[walk[-1]])
    return tuple(reversed(walk[:-1]))


# --- where the smith works (blacksmithing plan §10, contracts §8) ----------------------------
#
# The forge has two benches. The field kit — camp anvil, bellows, field hearth, bucket,
# whetstone — goes wherever the smith stands and does common and uncommon work. A SMITHY
# adds the furnace: Smelt, Alloy, Fold, Strengthen, and rare-and-above material. A smithy
# is either the town's (a place whose keeper is a smith, paid by the hour) or the player's
# own (founded through the `found` door and held as `holds.place.<slug>`).
#
# The 2026-08-25 ruling — "leave fixed tools alone until property ownership exists" — is
# retired by this: property ownership exists (the `found` door's holder effect), so a
# fixed installation now means something a character can own.
#
# Which one the party is at is READ OFF THE SCENE: its coordinate (`scene.at`), the place
# that coordinate names, that place's kind, its keeper and its holder. Never off the
# player's words — "I work at my forge" said in a meadow is a meadow, and the bench is the
# field kit. The same shape every place question here has: derived from the one
# coordinate, nothing stored beside it.
#
# **The smithy tag.** A place is not an actor and carries no effects (docs/place-doors.md:
# "the origin of a place is a field on the `Place`, not a tag"), so a place's tags are
# DERIVED from its kind, never stored: `place.<kind>` for any kind, and `place.smithy` for
# a kind whose keeper works at the forge by occupation (`content/people/occupations.json`,
# the `forge` tag — the smith today; an armourer or a world's own metalworker the day a
# row says so). Asked as a prefix question, as every state is (`has_place_tag`), so no
# caller matches the word "smithy" against a name.

SMITHY = "place.smithy"
# The occupation tag that makes a keeper a smith. One word in one table, so a world (or a
# later row) that adds an armourer tagged `forge` gets its armoury counted as a smithy
# with nothing here changed.
FORGE_WORK = "forge"

# --- where the alchemist works (alchemy plan §14, contracts §9) ------------------------------
#
# The forge's kit-and-smithy rule, mirrored. The alchemist's field kit (crucible, spirit
# lamp, a rack of vials) goes wherever the alchemist stands and does Dissolve, Calcine,
# Filter, React, Bottle and Assay on common and uncommon reagents. A LABORATORY adds
# Distill, Sublime and Transmute, rare-and-above reagents, +2 circumstance on every check
# (the book's alchemist's lab, aonprd "Alchemist's lab") and a fume hood against `toxic_to_handle`. It is
# the town's (a place whose keeper is an alchemist, rented by the hour) or the player's own
# (founded with kind `laboratory` and held as `holds.place.<slug>`).
#
# The same derivation as the smithy: `place.laboratory` for a place of kind `laboratory`,
# and for any kind whose keeper's occupation carries the `alchemy` tag — the `alchemist`
# (content/people/occupations.json) today, a world's own chymist the day a row says so.
# Every city has one (`ALWAYS_BY_SCALE`, `APPENDED_TO_AUTHORED`: the owner, 2026-10-06);
# a town or a village when its own words name its alchemists (`IMPLIED`) or play founds
# one. Never read from the player's words.
LAB = "place.laboratory"
ALCHEMY_WORK = "alchemy"


# Origins whose NAME somebody in play chose: the plan's `found`, the page's old door, and
# ground gone into. Their kind is the engine's validated `kind` field and nothing else.
_NAMED_IN_PLAY = frozenset({"found", "narrated", "venture"})


def _kind_of_place(place) -> str:
    """A place's kind: its own `kind` when it has one, else — for a place the world or
    the generator named — the table's name for it ("the smithy" → "smithy").

    A place minted in play is never read by its name. "my forge", founded with no kind,
    is a name the player chose; reading it as a smithy would be the player's words
    opening the furnace, which contracts §8 forbids. Its kind is what the `found` door
    validated, or it has none."""
    kind = kind_named(getattr(place, "kind", "") or "")
    if kind or str(getattr(place, "origin", "") or "") in _NAMED_IN_PLAY:
        return kind
    return kind_named(getattr(place, "name", "") or "")


def _occupation_works(work: dict | None, tag: str) -> bool:
    return bool(work) and tag in (work.get("tags") or ())


def _occupation_works_forge(work: dict | None) -> bool:
    return _occupation_works(work, FORGE_WORK)


def _kind_works(kind: str, tag: str) -> bool:
    """Whether the keeper of a place of this kind works at `tag` by occupation: the
    keeper's title (`STAFFED`) read through the occupation table (`lives.occupation_for`)."""
    title = keeper_of(f"the {kind_named(kind)}")[0] if kind else ""
    if not title:
        return False
    from . import lives

    return _occupation_works(lives.occupation_for(title), tag)


def kind_works_forge(kind: str) -> bool:
    """Whether the keeper of a place of this kind is a smith by occupation."""
    return _kind_works(kind, FORGE_WORK)


def kind_works_alchemy(kind: str) -> bool:
    """Whether the keeper of a place of this kind is an alchemist by occupation."""
    return _kind_works(kind, ALCHEMY_WORK)


# The place tags a keeper's trade derives, one row per craft that has a fixed bench: the
# occupation tag on the left, the place tag it makes on the right. A third craft's
# workroom is one row here and one occupation tag, nothing else.
_WORK_TAGS = ((FORGE_WORK, SMITHY), (ALCHEMY_WORK, LAB))


def place_tags(place) -> frozenset[str]:
    """The tags a place answers to, derived from its kind and never stored."""
    kind = _kind_of_place(place)
    if not kind:
        return frozenset()
    out = {f"place.{_slug(kind)}"}
    for work, tag in _WORK_TAGS:
        if _kind_works(kind, work):
            out.add(tag)
    return frozenset(out)


def has_place_tag(place, query: str) -> bool:
    """Exact match or dot-boundary prefix, the same question `Actor.has_state` asks."""
    q = str(query or "").strip().lower()
    return any(t == q or t.startswith(q + ".") for t in place_tags(place)) if q else False


def _place_at(scene, known=()) -> Place | None:
    """The place the scene's coordinate names, from what the scene holds.

    `known` is `Engine.places()` when the caller has it, which is the only way an
    authored place whose id is not its table name can be read — the scene holds no world.
    Without it: a founded place from `scene.founded`, else the generated place the id
    spells (`{loc}~urban:the-smithy` is "the smithy", which is how `keepers.label_of`
    reads it too). A floor above or below the ground one is not the forge: the anvil is
    where you walk in.
    """
    at = str(getattr(scene, "at", "") or "").strip()
    if not at or storey_of(at):
        return None
    for p in known or ():
        if getattr(p, "id", "") == at:
            return p
    for raw in getattr(scene, "founded", None) or ():
        d = raw.as_dict() if isinstance(raw, Place) else raw
        if isinstance(d, dict) and str(d.get("id") or "") == at:
            return from_dict(d)
    head, _sep, spot = at.partition(":")
    if not spot or SEP not in head or "/" in spot:
        return None
    return Place(id=at, name=spot.replace("-", " "), terrain=terrain_of(at))


def _actor(scene, ref: str):
    if not ref:
        return None
    people = getattr(scene, "people", None) or {}
    if ref in people:
        return people[ref]
    try:
        return (getattr(scene, "actors", None) or {}).get(ref)
    except Exception:
        return None


def _keeper_works(scene, place, keeper, work_tag: str, place_tag: str) -> bool:
    """The right trade keeps it: the person stood up there, when the population knows
    their work; else the work the place's keeper is stood up as."""
    if keeper is not None:
        from . import lives
        from . import population

        rec = population.of_ref(scene, getattr(keeper, "ref", "") or "")
        work = str(((rec or {}).get("life") or {}).get("work") or "")
        if work:
            row = next((o for o in lives.tables()["occupations"] if o.get("id") == work),
                       None)
            return _occupation_works(row, work_tag)
    return has_place_tag(place, place_tag)


def _keeper_works_forge(scene, place, keeper) -> bool:
    return _keeper_works(scene, place, keeper, FORGE_WORK, SMITHY)


def _workroom_here(scene, known, place_tag: str, work_tag: str, rate) -> dict | None:
    """The fixed bench the party is standing in, or None — the one reading behind
    `smithy_here` and `laboratory_here`, so the two benches cannot answer "is this one
    yours" two ways. `rate(owned_by_party=...)` is the market's answer for the craft.

    **Owned** first: a founded place carrying `place_tag` whose holder — the place's
    `owner` — answers `has_state("holds.place.<slug>")`. **Town** otherwise: urban ground
    whose keeper works at `work_tag` by occupation."""
    place = _place_at(scene, known)
    if place is None or not has_place_tag(place, place_tag):
        return None
    from . import keepers

    keeper = keepers.keeper_in(scene, place.id)
    keeper_ref = (getattr(keeper, "ref", None) or None) if keeper is not None else None
    founded = place.origin == "found" or any(
        str((raw.as_dict() if isinstance(raw, Place) else raw).get("id") or "") == place.id
        for raw in getattr(scene, "founded", None) or ())
    holder = _actor(scene, place.owner) if founded else None
    slug = place.id.rsplit("/", 1)[-1]
    if holder is not None and holder.has_state(f"holds.place.{slug}"):
        pc = scene.pc() if hasattr(scene, "pc") else None
        ours = pc is not None and getattr(pc, "ref", None) == getattr(holder, "ref", None)
        return {"kind": "owned", "place": place.id,
                "keeper": keeper_ref if ours else (getattr(holder, "ref", None) or keeper_ref),
                "rate_cp_per_hour": rate(owned_by_party=ours)}
    if terrain_of(place.id) != URBAN:
        return None
    if not _keeper_works(scene, place, keeper, work_tag, place_tag):
        return None
    return {"kind": "town", "place": place.id, "keeper": keeper_ref,
            "rate_cp_per_hour": rate(owned_by_party=False)}


def smithy_here(scene, known=()) -> dict | None:
    """The smithy the party is standing in, or None (contracts §8).

    {"kind": "owned" | "town", "place": id, "keeper": ref | None, "rate_cp_per_hour": int}

    **Owned** first: a founded place tagged `place.smithy` whose holder — the place's
    `owner` — answers `has_state("holds.place.<slug>")`. The owner field is the claim and
    the holder's effect is the fact: remove the effect (the place sold, seized, burnt)
    and the same building is no longer theirs, with nothing here to update. Free to its
    owner; anybody else's forge (a friend's, founded as theirs) is rented at the town's
    rate, from them.

    **Town** otherwise: a place in a settlement (urban ground) whose keeper is a smith by
    occupation. A smithy founded with no holder is the town's — "places must be
    creatable" (ruled 2026-10-03), so a settlement whose author listed no smithy gets one
    the first time play walks to it, and `keepers.staff` stands a smith up behind it.
    The keeper is None when nobody has been stood up yet, or the smith is gone; the
    forge is still there and still the town's.
    """
    from . import market

    return _workroom_here(scene, known, SMITHY, FORGE_WORK, market.forge_rate)


def laboratory_here(scene, known=()) -> dict | None:
    """The laboratory the party is standing in, or None (alchemy contracts §9).

    {"kind": "town" | "owned", "place": id, "keeper": ref | None,
     "rate_cp_per_hour": int, "fume_hood": True}

    Read exactly as `smithy_here` reads a forge (`_workroom_here`): **owned** when the
    place was founded and its holder carries `holds.place.<slug>` — free to the party,
    the town's rate to anybody else's — and **town** when it is urban ground kept by an
    alchemist by occupation (`ALCHEMY_WORK`), rented by the hour (`market.lab_rent`).
    Every laboratory has its fume hood: it is what makes the room a laboratory and not a
    kitchen with glass in it (alchemy plan §14, the protection against
    `toxic_to_handle`). The scene's coordinate decides, never the player's words — "I
    work in my laboratory" said in a meadow is a meadow, and the bench is the field kit.
    """
    from . import market

    here = _workroom_here(scene, known, LAB, ALCHEMY_WORK, market.lab_rate)
    if here is not None:
        here["fume_hood"] = True
    return here


def laboratory_in(known) -> Place | None:
    """The settlement's laboratory among `known` (`Engine.places()`), or None: the first
    ground-floor urban place tagged `place.laboratory` that nobody holds — the one a
    stranger can rent. For saying where to go, never for deciding the bench, which is
    `laboratory_here`'s and asks where the party stands."""
    for p in known or ():
        if storey_of(getattr(p, "id", "") or "") or terrain_of(getattr(p, "id", "")) != URBAN:
            continue
        if getattr(p, "owner", "") or not has_place_tag(p, LAB):
            continue
        return p
    return None


def laboratory_line(scene, known=(), location=None) -> str:
    """Where the alchemist can work, in one sentence for the bench to show — "" when the
    party is standing in a laboratory already (the bench says that itself).

    A city always has one (the owner, 2026-10-06), so this names it; a town or village
    without one says so in so many words, and says what still works: the field kit, and
    a laboratory of their own through the `found` door. Out of any settlement, there is
    no laboratory to rent. `location` is the settlement entity when the caller has the
    world, for its name; its scale is never needed — what decides is whether a
    laboratory is among `known`."""
    if laboratory_here(scene, known) is not None:
        return ""
    name = str(getattr(location, "name", "") or "").strip()
    lab = laboratory_in(known)
    if lab is not None:
        return (f"There is a laboratory to rent here: {lab.name}"
                f"{' in ' + name if name else ''}, by the hour.")
    if location is not None and not _settled(location, ""):
        return ("There is no laboratory out here. The field kit works anywhere; Distill, "
                "Sublime, Transmute and rare reagents wait for a laboratory.")
    where = name or "This place"
    return (f"{where} has no laboratory to rent. The field kit works anywhere; Distill, "
            f"Sublime, Transmute and rare reagents need a laboratory — a city's, or one "
            f"of your own.")


# The smith's field kit, as a carried thing. NOT in the goods tables yet: `rules/goods.py`
# and `content/rules/gear.json` belong to another lane this wave (contracts §1), so the
# row is named here and asked for in the lane report — until it lands, the kit is found
# by its name in the pack, which is how `gear.carried` finds everything else anyway.
FIELD_KIT = "smith's field kit"
# The names the fiction and a counter hand it over by. Never "field kit" alone: a healer
# carries a kit into the field too, and a bare "kit" opening the forge would be the
# player's words deciding the bench.
FIELD_KIT_NAMES = frozenset({
    FIELD_KIT, "smiths field kit", "smith's kit", "smithing kit", "blacksmith's kit",
    "blacksmiths kit", "field forge", "portable forge",
})


def _said(name) -> str:
    return " ".join(str(name or "").lower().replace("’", "'").split())


def _kit_name(name) -> bool:
    return _said(name) in FIELD_KIT_NAMES


def _carries(actor, names: frozenset, gear_key: str) -> bool:
    """Whether `actor` carries a thing called one of `names`: both stores a carried thing
    can be in, as `gear.carried` reads them, then `gear.holds` for the goods row."""
    if actor is None:
        return False
    for s in (getattr(actor, "stock", None) or {}).values():
        if int(getattr(s, "count", 0) or 0) > 0 and (
                _said(getattr(s, "base", "")) in names or _said(getattr(s, "name", "")) in names):
            return True
    for name, n in (getattr(actor, "goods", None) or {}).items():
        if int(n or 0) > 0 and _said(name) in names:
            return True
    try:
        from . import gear

        return bool(gear.holds(actor, gear_key))
    except Exception:
        return False


def has_field_kit(actor) -> bool:
    """Whether this actor carries the smith's field kit (contracts §8).

    Both stores a carried thing can be in, as `gear.carried` reads them: a counter's
    purchases in `stock` (`goods.deliver` files bought gear there under its name) and the
    fiction's handovers in `goods`. A count of nought is not carried — `take_stock`
    deletes an empty entry, but a `goods` row can sit at zero. Once the goods row exists
    with a `gear.json` entry, `gear.holds` answers too.
    """
    return _carries(actor, FIELD_KIT_NAMES, FIELD_KIT)


# The alchemist's field kit (alchemy plan §14: crucible, spirit lamp, a rack of vials, a
# funnel and cloth; proposed 25 gp, 5 lb, the Ultimate Equipment alchemy crafting kit's
# price and weight). Its goods row is lane H's (`content/rules/gear.json`, contracts §1);
# until it lands the kit is found by its name, as the smith's was.
ALCHEMY_KIT = "alchemist's field kit"
# Never "kit" or "field kit" alone, for the smith's reason. "travelling alchemy kit" is the
# alchemist world class's own level-1 tool (content/world-classes/alchemist.json), and the
# book's two portable things count: Ultimate Equipment's "alchemy crafting kit", and the
# Core Rulebook's 40 lb "alchemist's lab" carried in a pack, which does at least what the
# kit does — set down in a founded laboratory it is part of the room, not the pack.
ALCHEMY_KIT_NAMES = frozenset({
    ALCHEMY_KIT, "alchemists field kit", "alchemist's kit", "alchemists kit",
    "alchemy kit", "alchemy crafting kit", "travelling alchemy kit",
    "traveling alchemy kit", "alchemist's lab", "alchemists lab", "portable alchemy lab",
})


def has_alchemy_kit(actor) -> bool:
    """Whether this actor carries the alchemist's field kit (alchemy contracts §9): read
    from the pack exactly as `has_field_kit` reads the smith's."""
    return _carries(actor, ALCHEMY_KIT_NAMES, ALCHEMY_KIT)
