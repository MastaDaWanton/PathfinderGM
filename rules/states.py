"""The state vocabulary: every condition, as hierarchical tags.

Stage 1 of docs/states-effects-tells.md. Conditions have been flat strings, and every
question about them was its own hand-rolled test: lootability checked `hp <= 0 or
has_condition("unconscious")`, the walking-dead prose cut built a name list from
`hp <= 0`, `can_act` read a flag off the condition table, and the three drifted — a
petrified actor was lootable by one test and alive by another. A tag hierarchy makes
them one question with one answer: "anything under `state.down`?"

The vocabulary is additive and homebrew-safe on purpose. A key nobody registered
self-tags under `condition.<key>`, so an authored class's new state participates in
prefix queries the day it is written, and nothing anywhere matches exact strings.

Tags are dot-paths. A query matches a tag when it names the tag exactly or a prefix of
it at a dot boundary: `state.down` matches `state.down.dead` and not `state.downhill`.
"""
from __future__ import annotations

# Every shipped condition, with the tags it grants. Two families carry most questions:
#   state.down.*    — out of the fight and beyond objecting: lootable, un-attackable
#                     in any meaningful sense, and never again an actor in prose.
#   state.unable.*  — cannot take actions right now (may still be very much alive).
# They overlap where 1e overlaps them: the dying are both down and unable; the
# stunned are unable and emphatically not down.
#
# `state.down.fallen` is the narrower half of `state.down`: a body on the floor whose
# story resolves on its own — it bleeds out, it stabilises, it is already dead. The
# other two members of the family are living creatures held in place, and the difference
# decides who gets quietly removed from the scene. Without it `tidy_the_fallen` aged a
# petrified enemy out as a corpse two turns after the fight, statue and all, and
# `downed.resolve` offered a paralyzed character a nap they would never wake from.
#
# The `recovery.*` family says what ENDS a state, which is a fact about the condition and
# so belongs here rather than in a list at each site that ends things. Four sites carried
# the same four names — heal, rest, the downed resolution and resurrection — and the
# copies had already drifted: travel forgot `stable`, and only resurrection is entitled
# to remove `dead`.
#
#   recovery.hit-points  being back above 0 hit points undoes it
#   recovery.rest        a night's sleep ends it: the stale states that otherwise
#                        quietly poison every roll for the rest of the campaign
#
# Sweeping an existing `state.*` family instead is the trap, and it is one keystroke
# from the obvious implementation: `state.unable` contains `dead`, so a night's sleep
# would raise a corpse; `state.held` contains `paralyzed`, so it would cure paralysis;
# `state.senses` contains `blinded` and `deafened`, which in 1e end only with a spell.
# Beside the condition families, the situation cards (`rules/cards.py`) carry tags in the
# same vocabulary and are asked the same prefix questions:
#
#   situation.errand   why the character came here today (the opening's card)
#   situation.strain   what is wrong with this place, from the export's own facts
#   situation.hook     the world's unwritten hooks — the GM's, secret
#   situation.world    authored by World Bible and shipped with the world
#   situation.play     arose in play
#
# And the places a person holds (`rules/places.py`, door two): founding a place with an
# owner grants that owner `holds.place.<slug>` through the one applicator, source
# `place:<id>`, so "does anyone here hold a place?" is `has_state("holds.place")`.
#
# `race.<id>`, `sense.*`, `immune.*`, `move.*`, `natural.*`, `weakness.*` — a race
# document's tags (rules/races.py), held through `Actor.standing_tags` the way a feat's
# are: `has_state("race.elf")` is the feat prerequisite's question, and
# `has_state("sense.darkvision")` is the one a dark room will ask. The race string on
# the sheet is the store, never the question. The readers that exist today:
# `immune.<energy>` and `resist.<energy>.<n>` in `Actor.immune_to` / `resistance`,
# `ferocity` in `Actor.apply_hp_state`, `move.<mode>.<ft>` and `sense.*` on the sheet's
# body block and in the narrator's brief, `proficient.*` in `Actor.is_proficient`. An
# eidolon evolution (content/races/evolutions.json) grants these through the race
# document's `expand`; what has no reader yet is on its `not_yet` line.
#
# A card that puts a state on a person does it as an ActiveEffect through the one
# applicator, source `card:<id>`, so `has_state("situation")` on an actor answers for
# every card-granted tag the way it answers for a condition.
#
# `deed.*` — the player character's good and bad deeds (rules/deeds.py,
# docs/deeds-plan.md): `deed.theft`, `deed.violence.unprovoked`, `deed.kill.captive`,
# `deed.mercy.saved`, `deed.harvest.good-outsider` and the rest of
# content/rules/deeds.json. The same vocabulary and the same matcher (`matches`), asked
# as prefix questions — `deeds.of(pc, "deed.kill")` — and never as strings. NOT a state
# anybody holds: a deed is a row of `Actor.deeds`, the ledger, written only by
# `deeds.record`, so there is no TAGS row and `has_state("deed")` answers nothing. When a
# later system makes deeds matter it grants a state of its own through the applicator (a
# renown tag, a `knows.*` on a witness); nothing reads the ledger yet (the owner,
# 2026-10-08), and tests/test_deeds.py holds that.
#
# The law's opinion of a person, per town (docs/wanted.md, docs/quest-schemes-plan.md
# §6.6):
#
#   state.wanted.<town>     the watch has a name and a warrant: the gate is shut to
#                           them, the counter charges them for silence or refuses,
#                           and a guard who sees a fight start takes the other side
#   state.suspected.<town>  the lesser: a name on the watch's lips. Prices up, a
#                           warning at the gate, and nothing refused
#
# `<town>` is `town_tag(location_id)` — the world's durable id for the settlement,
# lowered and made safe for a tag path — and never the town's name: two towns can share
# a name and one town can be renamed, and either would make a warrant land on the
# wrong ground. Skyrim keeps its bounty per hold for the same reason (a Falkreath crime
# is nothing to a Winterhold guard) and it is the shape a scheme wants: "A Small Favour"
# makes you wanted where the favour went wrong, not everywhere.
#
# Not in TAGS and not in the condition table, on purpose. A condition key is one fixed
# state with one fixed set of tags; these are a FAMILY with the town in the leaf, so
# there is no row to write. They exist only as an `ActiveEffect` through the one
# applicator (kind `situation`, `until-dismissed`, tags `("state.wanted.<town>",)`),
# with a source that says who said so — `scheme:<id>/<outcome>` or `rule:<id>` — and
# `Actor.remove_effects(source=...)` is how a name gets cleared: the one record goes
# and every bite evaporates, which `tests/test_wanted.py` proves. `wanted_tag` and
# `suspected_tag` are the only writers of the tag text, so a grant and a reader cannot
# spell the town differently.
#
# Under `state.*` because it IS a state of the actor that readers refuse on — the gate
# is a refusal with the fix named — but deliberately outside `state.down`,
# `state.unable` and every `recovery.*` family: a warrant does not stop an action, and
# a night's sleep must not clear it. `test_a_warrant_is_not_slept_off` holds that line.
#
#   role.guard   whoever keeps the law here — the watchman template carries it by
#                kind, and a document or the GM may grant it to a named person. The
#                reader is `Engine._law_joins`: a fight that starts in the town where
#                the player is wanted brings every guard in on the other side.
#
#   role.bystander  somebody the prose put in the room who is not in the fight: a
#                   merchant at his stall, the boy by the well. Granted when the cast
#                   ledger promotes a person to an actor (`judgement.promote_cast`), and
#                   lifted by the one door into a fight (`Engine.join_fight`) or by a
#                   blow given or taken (`Engine._op_attack`). Readers: `_can_be_fought`
#                   and everything that fills "him" onto a body — measured 2026-09-18
#                   with the map open, nine non-player actors on a five-by-five board,
#                   seven of them bystanders, every one a fightable target for the
#                   planner and a candidate for a pronoun, and a boy at 4 hp died to a
#                   thrown chunk of wood meant for the man who had drawn on the player.
#   bond.knows-you   somebody who knew this character before the game started. Granted
#                    at campaign start by `backgrounds.acquaint` when a background tie
#                    bound a place in the settlement the game opens in — eleven of the
#                    fourteen shipped backgrounds are local ("You kept a pitch at the
#                    market and the neighbours still nod"), and the person standing
#                    beside the player was a stranger in all fourteen. Reported
#                    2026-09-22: "if you have picked a background and are know to the
#                    place you start then the person you start next to does not need to
#                    be a stranger."
#
#   bond.travels-with-you   somebody who comes when the party moves. Granted and lifted
#                    by the `company` op, read by `_op_travel` and `_op_journey`, which
#                    shed every non-PC not named in `with` — so before this, a friend
#                    who agreed to come along was left standing in the market the moment
#                    the player walked to the green. Inform's Van Helsing (Recipe Book
#                    7.13, Traveling Characters) is the same rule from the other side:
#                    an every-turn rule that routes the follower to the player's room.
#
# What carried gear grants (content/rules/gear.json, rules/gear.py; the owner,
# 2026-10-01), held through `Actor.standing_tags` while the thing is in the pack — the
# pack is the store, as the feat list is for a feat's tags:
#
#   gear.bedding       something to sleep in: spares the sleeping-rough fatigue
#                      (`Engine._op_rest`, the camp rule `sleeping-rough`)
#   gear.shelter       a tent: the night's encounter chance is the row's `camp` scale,
#                      and with gear.bedding or gear.warmth the sleeper counts as
#                      protected from the cold (the camp rule `cold-ground`)
#   gear.warmth        a blanket: the other half of that protection
#   gear.writing       ink and paper: a note or a map can be written (`/api/write`)
#   gear.fire-lighting flint and steel; nothing reads it yet (no fire in the engine)
#   gear.rope          a rope; nothing reads it yet (no climb DC or bind op takes it)
BEDDING = "gear.bedding"
SHELTER = "gear.shelter"
WRITING = "gear.writing"
WANTED = "state.wanted"
SUSPECTED = "state.suspected"
GUARD = "role.guard"
BYSTANDER = "role.bystander"
KNOWS_YOU = "bond.knows-you"
TRAVELS_WITH_YOU = "bond.travels-with-you"
# Non-lethal damage that will not mend until a need is met (CRB p.444, Starvation and
# Thirst: "cannot be recovered until the character gets food or water, as needed—not even
# magic that restores hit points heals this damage"). Granted by the `withheld` effect
# `survival` lands with the damage, one per need, and lifted by eating or drinking:
#
#   heal.withheld.thirst   until they drink
#   heal.withheld.hunger   until they eat
#
# Not `state.*` (it stops and impairs nothing — the non-lethal itself does that) and no
# `recovery.*`: a night's sleep is exactly what it must survive.
WITHHELD = "heal.withheld"
# The condition key that grants it — the one name every writer uses, so the tag has
# one writer's vocabulary and `test_no_new_site_matches_a_condition_by_name` sees no
# new literal.
BYSTANDER_KEY = "bystander"

# What an ITEM is made of (enchanting plan §16, contracts §3.3; the cross-craft ruling
# "there are spells that affect metal", leatherworking Q7.3). Tags of a thing, not of a
# person: `rules/item_tags.py` derives them from the item's pieces and asks them through
# `matches`, never `==`, so "is it metal?" is one prefix question whatever the metal is.
#
#   material.<substance>.<material>   every piece: material.metal.cold-iron,
#                                     material.wood.ash, material.leather.wolf-pelt
#   material.<substance>              the family alone, asked by prefix: material.metal
#   material.main.<material>          the most prevalent material (the book's "only the
#                                     most prevalent", the main piece: head or body),
#                                     which the cold iron surcharge asks
#
# Before this, metal was a name list (`armour.METAL_ARMOUR`, `METAL_SHIELDS`): a forged
# mithral-on-darkwood shield was metal by its name and a forged noqual breastplate only
# because "breastplate" was on the list. The substance is read off the material's own
# `kind` (metal, alloy, hide...), so a world's own metals answer the same question
# (World Bible exports `kind`; docs/enchanting-revamp-plan.md §20). Foundry's PF1 system
# models the same split (its material registry gives each material a `baseMaterial`,
# steel or wood, and keeps surface treatments as `addon` materials beside it), which is
# why a finish such as alchemical silvering adds no substance tag here.
MATERIAL = "material"
MATERIAL_MAIN = "material.main"
METAL = "material.metal"
# Iron and its alloys, beside the piece's own leaf: `material.metal.ferrous` is a flag on
# the family, read off the metal document's `ferrous: true` (lane D set it on the eleven
# iron and steel metals), so "is it iron?" is one prefix question whatever the iron is
# called. Rusting grasp's target ("any iron or iron alloy item", CRB). No material is
# called "ferrous", so the leaf cannot collide with a piece's own.
METAL_FERROUS = "material.metal.ferrous"

# What a creature has on it that is metal (leatherworking plan §18.5; the owner's Q7.3,
# "armor and weapons both need a metal tag because there are spells that affect metal").
# Standing tags, live-read off what is worn, wielded and carried (`item_tags.bearer_tags`
# through `Actor.standing_tags`), so the druid's rule, heat and chill metal and shocking
# grasp all ask `has_state` by prefix (law 1) and taking the suit off is the tag gone.
#
#   wears.armour.metal[.ferrous]   the suit on the body has a metal piece (iron among them)
#   wears.shield.metal[.ferrous]   the shield on the arm does
#   wields.metal[.ferrous]         the weapon in hand does
#   carries.metal[.ferrous]        anything at all on them does — worn, wielded or packed
#                                  (heat metal's "minimum damage" for a creature that is
#                                  only carrying metal)
#   body.metal[.ferrous]           the creature IS metal (an iron golem): shocking grasp's
#                                  third clause and rusting grasp's ferrous creature. Asked
#                                  here; no stat block grants it yet (plan §5.3's bestiary
#                                  pass), so today nothing answers it.
WEARS_ARMOUR_METAL = "wears.armour.metal"
WEARS_SHIELD_METAL = "wears.shield.metal"
WIELDS_METAL = "wields.metal"
CARRIES_METAL = "carries.metal"
BODY_METAL = "body.metal"
FERROUS_LEAF = "ferrous"
# The roots `Actor.bearer_tags` writes under. `has_state` walks what is worn and packed
# only for a query under one of these, because the walk is the costly part of the answer.
# `body` is not among them: `body.metal` is a creature's own tag (its stat block's, read by
# `standing_tags` already), never something it wears.
BEARER_ROOTS = frozenset({"wears", "wields", "carries"})

# What a class's prohibition suspends while it holds (a class document's `prohibits`
# block, `rules/classfeatures.py`): CRB Druid, "unable to cast druid spells or use any of
# her supernatural or spell-like class abilities while doing so and for 24 hours
# thereafter". Laid on the creature as `suspended.<entry>` by one ActiveEffect with origin
# `rule:prohibited-metal`; the cast door asks `suspended.casting.class` and the class
# ability door `suspended.ability.<su|sp>.class`. Class casting only: a wand or a scroll
# is not "her" spell, and an item's power goes through its own door.
SUSPENDED = "suspended"
SUSPENDS: tuple[str, ...] = ("casting.class", "ability.su.class", "ability.sp.class")
# The book's three kinds of special ability (CRB, Special Abilities): extraordinary,
# supernatural, spell-like. A class ability document says which it is (`ability_type`).
ABILITY_TYPES: tuple[str, ...] = ("ex", "su", "sp")

# What a cursed item is and what it does to whoever bears it (enchanting plan §11; lane F,
# `rules/curses.py`, `content/rules/curses.json`). Two kinds of tag under one root:
#
#   curse.<row>[.<sub>...]       which curse an item carries — `curse.drawback.blurred`,
#                                `curse.intermittent.dependent.night` — written once, by
#                                `curses.roll` (the curse record's `tags`). A tag of the
#                                ITEM's record, never laid on a person: it names what is
#                                hidden until the item is identified, and a person's tags
#                                reach the sheet.
#   curse.bars-casting.<what>    what the drawback stops its bearer doing while the item
#                                is held or worn, laid on the BEARER through the layer's
#                                `tags` (`Actor._worn_tags`) and answered in BLOCKS below:
#                                `.arcane`, `.divine`, or `.any`. `.any` is a sibling and
#                                not the bare family on purpose: tags answer by prefix, so
#                                a bare `curse.bars-casting` row in BLOCKS would also
#                                answer for an `.arcane` tag and stop a cleric praying.
#
# Asked by prefix like every other family (`matches`), never by `==`.
CURSE = "curse"
CURSE_BARS = "curse.bars-casting"
CURSE_BARS_ANY = "curse.bars-casting.any"
CURSE_BARS_ARCANE = "curse.bars-casting.arcane"
CURSE_BARS_DIVINE = "curse.bars-casting.divine"
# The substances a piece can be. Fixed so a reader can name a family without guessing
# its spelling; `item_tags` refuses (by test) a substance not on the list.
SUBSTANCES: tuple[str, ...] = ("metal", "wood", "leather", "bone", "horn", "cloth", "cord",
                               "stone", "glass")


def material_leaf(material_id) -> str:
    """A material id made safe as a tag leaf: lowered, and anything but a letter, digit
    or hyphen folded to a hyphen — a dot would read as a level of family (`town_tag`'s
    rule, for the same reason)."""
    return town_tag(material_id)


def material_tag(substance: str, material_id) -> str:
    """`material.<substance>.<material>` — the one writer of the tag text."""
    return f"{MATERIAL}.{substance}.{material_leaf(material_id)}"


def main_material_tag(material_id) -> str:
    return f"{MATERIAL_MAIN}.{material_leaf(material_id)}"


def suspended_tag(entry: str) -> str:
    """`suspended.<entry>` — the one writer of the tag a prohibition lays."""
    return f"{SUSPENDED}.{str(entry or '').strip().lower()}"

TAGS: dict[str, tuple[str, ...]] = {
    # Not under `state.*`: a bystander is stopped from nothing and impaired in
    # nothing, and no `recovery.*` — a night's sleep does not make a merchant a
    # combatant. It is a fact about whose fight this is, and it is READ.
    "bystander":   ("role.bystander",),
    "dead":        ("state.down.dead", "state.down.fallen", "state.unable"),
    "dying":       ("state.down.dying", "state.down.fallen", "state.unable",
                    "state.helpless", "recovery.hit-points", "state.exposed"),
    "unconscious": ("state.down.unconscious", "state.down.fallen", "state.unable",
                    "state.helpless", "recovery.hit-points", "state.exposed"),
    "stable":      ("state.down.stable", "state.down.fallen", "state.unable",
                    "recovery.hit-points"),
    "petrified":   ("state.down.petrified", "state.unable", "state.helpless"),
    # A construct at 0 to -10 hit points, by the owner's house rule (2026-10-01; see
    # BROKEN_BELOW_ZERO below): down and helpless like the unconscious, but never dying
    # and never bleeding. `recovery.hit-points`, so a repair that lifts it above 0 ends
    # it through the same sweep a cure uses; NOT `state.down.fallen`, whose bodies
    # resolve on their own — a broken machine lies there until somebody mends it.
    # Appendix 2's own "broken" is an ITEM condition (half hit points, -2), which no
    # creature here ever carries; this row is the creature's, and says it is the house's.
    "broken":      ("state.down.broken", "state.unable", "state.helpless",
                    "recovery.hit-points", "state.exposed"),
    # Helpless has always carried `can_act: False` in the condition row and no
    # `state.unable` tag, so the flag and the vocabulary disagreed about it: the tag
    # layer said a bound prisoner could act and the row said they could not.
    # And NOT under `state.down`, which it was until 2026-09-25: `is_down` read true
    # for a bound prisoner, so attacks on him were held back as "already down" and
    # `sides_standing` stopped counting his side — a foe made helpless by any of the ten
    # spell specs that apply it ENDED THE FIGHT, paralysis wearing off or not. 1e keeps a
    # helpless creature in the fight: it is the one a coup de grace is for.
    # `state.helpless` is the family `is_helpless` asks — 1e's "immobilized, unconscious,
    # or otherwise incapacitated" — granted by every row that is helpless.
    "helpless":    ("state.unable.helpless", "state.helpless", "state.exposed"),
    "paralyzed":   ("state.unable.paralyzed", "state.held", "state.helpless", "state.exposed"),
    "pinned":      ("state.held.pinned", "recovery.rest", "state.exposed"),
    "grappled":    ("state.held.grappled", "recovery.rest"),
    "stunned":     ("state.unable.stunned", "state.exposed"),
    "dazed":       ("state.unable.dazed", "recovery.rest"),
    "cowering":    ("state.unable.cowering", "recovery.rest", "state.exposed"),
    # Nauseated is impaired, not unable: 1e allows it "a single move action per turn"
    # and stops the rest. The condition row carried `can_act: False`, which the engine's
    # guard read as a block on attack, move AND check — denying the one action the rules
    # allow. What it stops is stated in BLOCKS rather than by a boolean that cannot say.
    "nauseated":   ("state.impaired.nauseated", "recovery.rest"),
    "staggered":   ("state.impaired.staggered", "recovery.rest"),
    "disabled":    ("state.impaired.disabled", "recovery.hit-points"),
    "fatigued":    ("state.impaired.fatigued",),
    "exhausted":   ("state.impaired.exhausted", "state.slowed"),
    "sickened":    ("state.impaired.sickened", "recovery.rest"),
    "shaken":      ("state.fear.shaken", "recovery.rest"),
    "frightened":  ("state.fear.frightened", "recovery.rest"),
    "panicked":    ("state.fear.panicked", "recovery.rest"),
    "fascinated":  ("state.unable.fascinated", "recovery.rest"),
    "confused":    ("state.impaired.confused",),
    "blinded":     ("state.senses.blinded", "state.exposed"),
    "deafened":    ("state.senses.deafened",),
    "dazzled":     ("state.senses.dazzled", "recovery.rest"),
    "invisible":   ("state.hidden.invisible",),
    "prone":       ("state.position.prone", "recovery.rest"),
    "flat-footed": ("state.position.flat-footed", "recovery.rest", "state.exposed"),
    "bleed":       ("state.wound.bleeding",),
    "entangled":   ("state.held.entangled", "recovery.rest", "state.slowed"),
    # The tanglefoot bag's second half (CRB, Goods and Services): "the target is glued to
    # the floor and unable to move" on a failed DC 15 Reflex save, until it breaks free
    # (`Engine._op_break_free`: DC 17 Strength, or 15 slashing to the goo) or the goo
    # "becomes brittle and fragile after 2d4 rounds" (the duration). Under `state.held`
    # with grappled and pinned; speed 0 is asked of the tag by `Actor.speed_feet` and the
    # move op, never by the key. Not an Appendix 2 condition, so it has no row in
    # `tables.CONDITIONS` (tests/test_reference.py refuses a condition the book does not
    # print) and needs none: the entangled it comes with carries the -2 and -4, and glued
    # adds only "cannot move". No `recovery.rest`: a night's sleep does not unstick it.
    "glued":       ("state.held.glued",),
    # Alchemist's fire's next round (CRB): "On the round following a direct hit, the
    # target takes an additional 1d6 points of damage ... a full-round action to attempt
    # to extinguish the flames". The effect carries its own `periodic` fire
    # (`Engine._burn`), and the `extinguish` op asks this tag. Not a condition of the
    # book's either (the hazard row "catching on fire" is the same state), so it lives
    # here alone, as `holding ground` does.
    "burning":     ("state.burning",),
    # The stances play has already minted. Buffs, not states: they are worn by choice.
    "blood armament": ("buff.stance.blood-armament",),
    "blood rage":     ("buff.stance.blood-rage",),
    "coagulated plate": ("buff.stance.coagulated-plate",),
    # The price of coming back: somebody paid the priests, and now the debt sits
    # on the character. Clockless — the world decides when it is called in.
    "life debt": ("state.obligation.life-debt",),
    # A creature met while gathering that has the ground the player wanted and keeps it:
    # it neither comes at them nor gives way (playtest 2026-09-30, item 8). The old
    # games' reaction roll in its middle band — B/X's "uncertain", Holmes's "make
    # another offer, roll again" — held as a state rather than re-rolled every turn, so
    # the NPC loop, the intent gate and the brief all read one fact. Granted by
    # `Engine._gathering_encounter` (source `gathering:<expedition>`), lifted by
    # `Engine._holding_ground_settles` when the creature is drawn into a fight or the
    # player closes on it and the reaction comes out otherwise. NOT under
    # `state.unable`: it stops no action by incapacity, it is a choice the creature is
    # making, so it lives outside BLOCKS and the gate that reads it says why in words.
    # No `recovery.*`: a night's sleep does not move a creature off its ground.
    "holding ground": ("state.holding-ground",),
    # 1e's attitude track, in the book's own order. `rules/effectspec.py` has offered
    # an `attitude` effect type since the spell import — thirty-three spells set one,
    # charm person among them — and it shipped `engine=False` with the note "no check
    # in the app consults an attitude yet", because there was nowhere for the answer
    # to live. Here is the somewhere.
    #
    # And since 2026-09-16 the checks do consult it: `rules/attitude.py` moves a creature
    # along this track on a Diplomacy or Intimidate check, by the Core Rulebook's own
    # tables, and the counter refuses a player the keeper dislikes (docs/attitude.md).
    # The effect type is `engine=True` now, and that note is gone rather than left to
    # read as true.
    #
    # Not under `state.*`: an attitude stops no action and impairs no roll. It is a
    # fact about how somebody feels towards you, and its whole job is to be READ — by
    # the brief, so the narrator writes the merchant as a merchant who likes you, and
    # by whatever later asks whether this creature would fight. And no `recovery.*`:
    # what ends a charm is the effect's own clock, not a night's sleep, and putting
    # one here would have every sweep in the app cure infatuation.
    "hostile":     ("attitude.hostile",),
    "unfriendly":  ("attitude.unfriendly",),
    "indifferent": ("attitude.indifferent",),
    "friendly":    ("attitude.friendly",),
    "helpful":     ("attitude.helpful",),
    "devoted":     ("attitude.devoted",),
}

# The track in the book's order, worst to best. Ordered because the question asked of
# it is nearly always a comparison — "friendly or better" — and a set cannot answer it.
#
# `devoted` is the step past the book's track, added 2026-09-24 for the player's ask —
# "talk with them and increase that attitude until they Idolize/Love me". No check
# reaches it: Diplomacy stops at helpful as the book says (`attitude.moved`), and only
# regard, the standing relationship kept on the person (`attitude.regard_of`), climbs
# there.
ATTITUDES: tuple[str, ...] = (
    "hostile", "unfriendly", "indifferent", "friendly", "helpful", "devoted")

# In conversation with the player: granted by `Engine.join_talk` when the player
# addresses somebody or somebody addresses them, lifted by `leave_talk`, by walking
# away, or by the person leaving, falling, or drawing. Read by the craft and rest
# refusals, the brief, and the talk panel. A tag on the PERSON, not a flag on the
# scene, so who is in the conversation is the same question as every other state.
TALKING = "talk.with-you"
# The forage encounter's stance (TAGS["holding ground"]), named once for its readers.
HOLDING_GROUND = "state.holding-ground"
HOLDING_GROUND_KEY = "holding ground"
# How somebody stands towards the player over time — the number the talk panel shows
# and the baseline the attitude track falls back to when no check or spell is holding
# a step. Held as one effect (`attitude.set_regard`) whose `amount` is the score.
REGARD = "bond.regard"
# What a lie left behind in the listener (owner ruling 2026-10-01, `rules/bluff.py`).
# `belief.claim.<kind>`: they believe the player is what the player claimed — held until
# dismissed, source `lie:<kind>`, so the day the truth comes out removing it by source is
# the whole undo. Read so the same claim believed twice moves them once. `belief.liar`:
# they have caught the player lying, and a later lie to them is at -10 (Ultimate
# Intrigue p.182). Not under `state.*` or `attitude.*`: neither stops an action or IS a
# step of the track; both are facts about what somebody believes, and are READ.
BELIEVES_CLAIM = "belief.claim"
CAUGHT_LYING = "belief.liar"

# What a body IS, in the Bestiary's own terms: `type.<creature type>` and
# `subtype.<word>`, held through `Actor.standing_tags` off the stat block the creature was
# made from (`creature_type`, `subtype`) and off the printed trait bundle — a homebrew
# block that prints only "Immune construct traits" is a construct all the same.
#
# Added 2026-10-01 for the owner's Clockwork Spy. A Magic Missile left it at -1 hit points
# and the engine said "unconscious and dying"; the next turn it "bled out where it fell" —
# a machine bleeding — because `apply_hp_state` asked `-Con` of a body with no
# Constitution, and a missing score reads as 10. The book (Bestiary, Creature Types,
# read on d20pfsrd 2026-10-01):
#
#   Construct: "Immediately destroyed when reduced to 0 hit points or less." "Immunity to
#   bleed ..." "A construct cannot be raised or resurrected."
#   Undead:    "Immediately destroyed when reduced to 0 hit points." "Not at risk of death
#              from massive damage."
#
# So there is no dying rung for either type. Undead keep the book: the bottom of their
# ladder is 0, the same threshold a troop has, through the same `Actor.death_floor`.
#
# CONSTRUCTS DO NOT, by the owner's HOUSE RULE (2026-10-01, content/rules/repairs.json):
# "Broken, then fixable and claimable — House rule: a construct at 0 to -10 is broken, not
# destroyed (destroyed only past that). Anyone with the skill can mend it with a Craft or
# Knowledge (engineering) check, which heals it. A second, harder check rewrites its
# loyalty so it becomes yours: it follows you, obeys, and you can name it." So a
# construct between 0 and the row's floor (-10) is `broken` — the condition below, under
# `state.down` so it is out of the fight, helpless and inert, and under
# `recovery.hit-points` so mending it above 0 lifts it — and is destroyed (`dead`) only
# past the floor. No dying, no bleeding, no Constitution anywhere in it.
#
# Asked as a prefix question (`has_state(CONSTRUCT)`) and never by matching a name or a
# `notes` line. NOT read off a race document's `type`, on purpose: a PC of a world's
# construct people would be a far larger ruling, and the Advanced Race Guide's
# construct-type terms for a player race could not be confirmed here.
TYPE = "type"
SUBTYPE = "subtype"
CONSTRUCT = "type.construct"
UNDEAD = "type.undead"
DESTROYED_AT_ZERO: tuple[str, ...] = (UNDEAD,)
BROKEN_BELOW_ZERO: tuple[str, ...] = (CONSTRUCT,)
# The condition key the house rule writes, named once so its writers are not literals.
BROKEN_KEY = "broken"
# A construct whose loyalty the player rewrote (`Engine._op_repair`'s claim, the house
# rule's "a second, harder check ... it becomes yours"). Granted through the one
# applicator beside `bond.travels-with-you` and the `devoted` step of the attitude track,
# source `claim:<ref>`; read by the `rename` op (only what is yours takes a name from you)
# and by `gm/checks/repair_claimed.py` (the page may say it obeys you once this is held).
OWNED_BY_YOU = "bond.owned-by-you"
# The Bestiary's trait bundles name their type: a block that prints the bundle and no
# `creature_type` still answers the type question.
TRAIT_TYPES: dict[str, str] = {"construct traits": "construct", "undead traits": "undead"}


def type_word(raw) -> str | None:
    """A stat block's creature type as the book's closed vocabulary spells it
    (`effectspec.CREATURE_TYPES`, "magical-beast"), or None when the words name none of the
    thirteen. The bestiary files spell it several ways: "magical beast", "advanced magical
    beast", and core.json's truncated "magical" (107 blocks) and "monstrous" (55), measured
    2026-10-08. A type contained in the words wins (longest first), then a type the words
    begin. Lane F wrote this reader for Grade (`knowledge._type_word`); it lives here so the
    tag writer below reads a type the same way (lane C found `type.magical` on 107 beasts)."""
    import re as _re

    from .effectspec import CREATURE_TYPES

    words = " ".join(_re.findall(r"[a-z]+", str(raw or "").lower()))
    if not words:
        return None
    for t in sorted(CREATURE_TYPES, key=len, reverse=True):
        if f" {t.replace('-', ' ')} " in f" {words} ":
            return t
    for t in CREATURE_TYPES:
        if t.replace("-", " ").startswith(words):
            return t
    return None


def type_tags(creature_type="", subtype="", immunities=()) -> tuple[str, ...]:
    """`type.<x>` / `subtype.<y>` for a stat block's own words — the one writer of the
    tag text, so a reader and a writer cannot spell a type differently. A type is the
    book's word when the words name one (`type_word`); a type outside the thirteen (a
    world's own) keeps its words."""
    import re as _re

    def leaf(word) -> str:
        return "-".join(_re.findall(r"[a-z0-9]+", str(word or "").lower()))

    out: list[str] = []
    kind = type_word(creature_type) or leaf(creature_type)
    if kind:
        out.append(f"{TYPE}.{kind}")
    for word in _re.split(r"[,;]", str(subtype or "")):
        if leaf(word):
            out.append(f"{SUBTYPE}.{leaf(word)}")
    for printed in immunities or ():
        bundle = TRAIT_TYPES.get(str(printed or "").strip().lower())
        if bundle and f"{TYPE}.{bundle}" not in out:
            out.append(f"{TYPE}.{bundle}")
    return tuple(out)


def destroyed_at_zero(actor) -> bool:
    """Whether this body is destroyed, not dying, at 0 hit points (undead)."""
    return bool(actor is not None and any(actor.has_state(t) for t in DESTROYED_AT_ZERO))


def breaks_below_zero(actor) -> bool:
    """Whether this body is broken, not dying, between 0 and its floor (constructs, by
    the owner's house rule)."""
    return bool(actor is not None and any(actor.has_state(t) for t in BROKEN_BELOW_ZERO))


def believes_claim_tag(kind: str) -> str:
    return f"{BELIEVES_CLAIM}.{kind}"


def attitude_of(actor, default: str = "") -> str:
    """Where this creature sits on the track, or `default` if nobody has said.

    One reader for one question, so no site ever matches `"friendly"` as a string —
    the same rule every other family here lives under.
    """
    for step in reversed(ATTITUDES):
        if actor is not None and actor.has_state(f"attitude.{step}"):
            return step
    return default


def town_tag(location_id) -> str:
    """The tag leaf for a settlement: its durable id, lowered, with anything that is
    not a letter, a digit or a hyphen folded to a hyphen. A dot in particular must go —
    it is the boundary `matches` splits on, so an id carrying one would read as two
    levels of family."""
    text = str(location_id or "").strip().lower()
    out = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in text).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out


def wanted_tag(location_id) -> str:
    """`state.wanted.<town>` — the one spelling, for granters and readers alike."""
    return f"{WANTED}.{town_tag(location_id)}"


def suspected_tag(location_id) -> str:
    return f"{SUSPECTED}.{town_tag(location_id)}"


def standing_with_the_law(actor, location_id) -> str:
    """"wanted", "suspected" or "" — what this town's watch holds against this person.

    One reader for one question, the same rule `attitude_of` lives under, so no gate,
    counter or guard ever spells the tag itself. A warrant in another town answers
    nothing here: the query carries the town, and `has_state` is a prefix match at a
    dot boundary, so `state.wanted.abc` does not answer for `state.wanted.abcd`.
    """
    if actor is None or not town_tag(location_id):
        return ""
    if actor.has_state(wanted_tag(location_id)):
        return "wanted"
    if actor.has_state(suspected_tag(location_id)):
        return "suspected"
    return ""


# Two families that are questions, not places in the tree, added 2026-09-25 so that no
# reader has to name conditions: `state.exposed` — denied Dex (and dodge) to AC, on every
# row that carried the `lose_dex_to_ac` flag; `state.slowed` — moves at half speed
# (entangled, exhausted). `tests/test_the_questions_are_tags.py` pins each family to the
# rows it replaced.
#
# Tags the vocabulary once granted a key and no longer does. A saved condition keeps the
# tags it was written with (`activeeffect._tags_on_load` unions, so a document's own tags
# survive a reload), which means a withdrawal has to be named or it never reaches a save
# already on disk. Each entry is the key and exactly what left it, never a family.
WITHDRAWN: dict[str, tuple[str, ...]] = {
    # 2026-09-25: a helpless creature is in the fight, not down — see TAGS above.
    "helpless": ("state.down.helpless",),
}


def tags_for(key: str) -> tuple[str, ...]:
    """The tags a condition key grants. Unknown keys self-tag, so homebrew plays."""
    key = (key or "").strip().lower()
    if not key:
        return ()
    known = TAGS.get(key)
    if known:
        return known
    return (f"condition.{key.replace(' ', '-')}",)


def matches(tag: str, query: str) -> bool:
    """Whether `tag` answers `query` — exact, or prefix at a dot boundary."""
    return tag == query or tag.startswith(query + ".")


def any_match(keys, query: str) -> bool:
    """Whether any condition key in `keys` grants a tag answering `query`."""
    q = (query or "").strip().lower()
    return any(matches(t, q) for k in keys for t in tags_for(k))


# What a state stops an actor DOING, as opposed to what it makes them.
#
# This replaces the `can_act` boolean that sat on the condition rows. A boolean has to
# answer "can this creature act?" with one bit, and 1e's incapacities are not all total:
# a nauseated character may take a single move action and nothing else, so the flag
# blocked all three of the ops the engine guards and denied them the one the rules
# allow. Naming the ops lets the vocabulary say what each state actually stops.
#
# The flag and the tag tree also drifted, because both were hand-written and nothing
# compared them: measured across the 31 shipped conditions they disagreed on three —
# `fascinated` (tagged unable, flagged able), `helpless` (flagged unable, untagged) and
# `nauseated` (flagged unable, and wrongly). There is now one list, and
# `test_the_vocabulary_is_the_only_authority_on_acting` keeps it the only one.
#
# Keys are tag prefixes, so an unregistered homebrew state under `state.unable.*`
# stops actions the day it is written without being added here.
ACTIONS: tuple[str, ...] = ("attack", "move", "check", "cast")

BLOCKS: dict[str, frozenset[str]] = {
    # Unable is total, and always has been: this is the family the ten conditions that
    # take no turn at all belong to.
    "state.unable": frozenset(ACTIONS + ("any",)),
    # "The only action such a character can take is a single move action per turn."
    "state.impaired.nauseated": frozenset(("attack", "check", "cast")),
    # A cursed item's drawback (CRB, Cursed Items, the drawback table: "character cannot
    # cast arcane spells", "... divine spells", "... any spells"), held while the item is
    # held or worn (`Actor._worn_tags`, lane F's `bars`). The arcane and divine bars stop
    # only that tradition's casting, which is asked as its own action, `cast.arcane` or
    # `cast.divine` (`Actor.barred_from_casting`) — never the whole `cast`, or an
    # arcane-barred cleric could not pray.
    CURSE_BARS_ANY: frozenset(("cast", "cast.arcane", "cast.divine")),
    CURSE_BARS_ARCANE: frozenset(("cast.arcane",)),
    CURSE_BARS_DIVINE: frozenset(("cast.divine",)),
}


def stops(tags, action: str = "any") -> bool:
    """Whether a state carrying `tags` stops `action`.

    `action` is one of ACTIONS, or "any" for the general question — may this creature
    take *any* action at all. "any" is answered only by a state that stops everything,
    which is why a nauseated character is not "unable" while still being refused an
    attack.

    Takes the tags an effect actually carries rather than re-deriving them from its
    key, because the two are not the same thing: an ability document may append its own
    tags on top of `tags_for` (`rules/engine.py`, `_apply_ability_document`), and
    `Actor.has_state` reads the carried tags. A second derivation here would be a
    second vocabulary — the exact fault this stage exists to remove.

    One question with one answer, asked by the turn gate (`play/views.py`), the intent
    guard (`rules/engine.py`) and the sheet alike. They used to answer it separately:
    a petrified character was handed a turn by the first, planned by the GM, and then
    refused by the second as a legality error — which regenerates rather than repairs,
    so the turn burned the retry loop and died as a 502 the player saw as a blank page.
    """
    want = (action or "any").strip().lower()
    return any(want in stopped and matches(str(tag), prefix)
               for tag in tags or ()
               for prefix, stopped in BLOCKS.items())


def blocking(keys, action: str = "any") -> str:
    """The condition key that stops `action`, or "" — for a caller holding only keys.

    Prefer `stops` with the effect's own tags where they are to hand.
    """
    return next((k for k in keys or () if stops(tags_for(k), action)), "")


# What an immunity, written as a stat block writes it, actually protects against.
#
# 1e attaches immunity to what an effect IS — a sleep effect, a fear effect, a poison —
# and not to the condition it happens to produce, and the difference is the whole reason
# this is a table rather than a string comparison. 469 shipped creatures are immune to
# sleep, and sleep immunity does NOT stop a creature falling unconscious from hit-point
# loss, non-lethal damage or a coup de grâce; 759 carry "undead traits", which is a
# bundle the Bestiary defines once and every entry then refers to.
#
# Keys are the words stat blocks use. Values are the condition keys and the descriptors
# they cover; a descriptor is matched against what an EFFECT declares itself to be, so
# "immune to fear" stops a fear effect that would shake you and leaves the shaken you get
# from something else alone.
# Written once and spliced into all four places below that used to repeat it.
#
# They repeated it, and the repetition had a hole in every copy: `dominate person` is a
# mind-affecting compulsion in the Core Rulebook and the word "dominate" appeared in
# none of them, so 759 creatures with undead traits were immune to charm and wide open
# to domination. Found 2026-09-09 while gating the same families against being handed
# out for free — the table was asked what a condition IS and could not answer for the
# two words a player reaches for first.
_MIND_AFFECTING: tuple[str, ...] = (
    "confused", "confusion", "fascinated", "fascinate", "charm", "charmed",
    "compulsion", "compelled", "dominate", "dominated", "domination",
    "suggestion", "mind-affecting")
_SLEEP: tuple[str, ...] = ("sleep", "asleep", "sleeping")

IMMUNITY_COVERS: dict[str, tuple[str, ...]] = {
    "sleep": _SLEEP,
    "paralysis": ("paralyzed", "paralysis"),
    "stun": ("stunned", "stun"),
    "fear": ("shaken", "frightened", "panicked", "cowering", "fear"),
    "mind-affecting": _MIND_AFFECTING,
    "mind affecting": _MIND_AFFECTING,
    "poison": ("poison", "nauseated", "sickened"),
    "disease": ("disease",),
    "bleed": ("bleed",),
    "fatigue": ("fatigued",),
    "exhaustion": ("exhausted", "fatigued"),
    "nausea": ("nauseated",),
    "blindness": ("blinded",),
    "deafness": ("deafened",),
    "death effects": ("death",),
    "energy drain": ("energy drain",),
    # Not a condition but a lethality, asked by `Actor.take_damage` under the key
    # "nonlethal": three shipped stat blocks print it bare, and the two bundles below
    # carry it because the Bestiary says so ("not subject to nonlethal damage").
    "nonlethal damage": ("nonlethal",),
    # The Bestiary's own bundle, expanded once here rather than in every consumer.
    # "nonlethal" joined both 2026-09-27, the day punches first dealt it: until then
    # every blow was lethal and a skeleton punched was a skeleton hurt, which was the
    # right answer for the wrong reason.
    "undead traits": (*_SLEEP, "paralyzed", "paralysis", "stunned", "stun",
                      "disease", "poison", "fatigued", "exhausted",
                      *_MIND_AFFECTING, "bleed", "death", "nauseated", "sickened",
                      "nonlethal"),
    "construct traits": (*_SLEEP, "paralyzed", "paralysis", "stunned", "stun",
                         "disease", "poison", "fatigued", "exhausted",
                         *_MIND_AFFECTING, "bleed", "death", "nauseated",
                         "sickened", "nonlethal"),
    "elemental traits": (*_SLEEP, "paralyzed", "paralysis", "stunned", "stun",
                         "poison", "bleed"),
}


# The families that change a MIND rather than a body, named the way 1e names them.
#
# Asked of the same data `IMMUNITY_COVERS` holds, from the other side: that table says
# what an immunity protects against, and this says what a condition IS. Sharing the
# table is the point — a homebrew charm that "immune to mind-affecting" would stop is
# the same charm this refuses to hand out for free, and two lists would drift.
#
# Deliberately NOT here: `dazed`, `stunned`, `staggered`, `nauseated`. All four can be
# mind-affecting in 1e when a spell causes them and all four can equally be a blow to
# the head, so gating them would refuse ordinary violence for having a mental cousin.
# The line is drawn at families that can ONLY be somebody's mind being altered.
MIND_FAMILIES: tuple[str, ...] = ("mind-affecting", "fear", "sleep")

# What each family is called when a refusal has to say what was attempted.
_MIND_CALLED: dict[str, str] = {
    "mind-affecting": "a mind-affecting effect",
    "fear": "a fear effect",
    "sleep": "a sleep effect",
}


def touches_the_mind(condition_key: str = "", descriptors=()) -> str:
    """What this condition changes about somebody's mind, or "" if it changes none.

    Three questions, because a mind can be reached three ways in this vocabulary and
    only the first two are registered anywhere:

      * an `attitude.*` tag — how a creature FEELS about you, which is the one the
        exploit reached for: nothing on a sheet stops a hostile guard being written
        helpful.
      * a `state.fear.*` tag — shaken, frightened, panicked.
      * the mind-affecting family itself — charm, compulsion, confusion, fascination.
        Asked by name and not by tag on purpose: `charmed` and `dominated` are not in
        `TAGS` at all, so they self-tag to `condition.charmed` and a prefix question
        would sail straight past the two words a player is most likely to use.

    The stem match is the same courtesy `immunity_blocks` extends and for the same
    reason: "dominated", "domination" and "dominate person" are one idea, and a table
    that only knew one spelling would be a table with a hole in it.
    """
    key = (condition_key or "").strip().lower()
    said = {str(d).strip().lower() for d in (descriptors or ()) if str(d).strip()}

    for tag in tags_for(key):
        if matches(tag, "attitude"):
            return "an attitude"
        if matches(tag, "state.fear"):
            return "a fear effect"

    for family in MIND_FAMILIES:
        covers = IMMUNITY_COVERS.get(family, ())
        if said & set(covers) or family in said:
            return _MIND_CALLED[family]
        for member in covers:
            if not key:
                break
            if key == member:
                return _MIND_CALLED[family]
            # "charm" covers "charmed"; "compulsion" covers "compelled" through the
            # shared stem, the way the immunity table covers "petrification".
            stem = min(len(key), len(member), 5)
            if stem >= 4 and key[:stem] == member[:stem]:
                return _MIND_CALLED[family]
    return ""


def immunity_blocks(immunities, condition_key: str = "",
                    descriptors=()) -> str:
    """Which immunity stops this condition, or "" if none does.

    Answers with the immunity's own words so a refusal can print them. Both halves are
    consulted: the condition a creature cannot suffer, and the descriptors the effect
    declares itself to carry — an effect that says it is a fear effect is stopped by
    immunity to fear whatever condition it was going to apply.
    """
    key = (condition_key or "").strip().lower()
    said = {str(d).strip().lower() for d in (descriptors or ()) if str(d).strip()}
    for raw in immunities or ():
        name = " ".join(str(raw).split()).strip().lower()
        covers = IMMUNITY_COVERS.get(name)
        if covers is None:
            # An unlisted immunity still protects against its own name, so a homebrew
            # "immune to petrification" works the day it is written — the same
            # self-tagging courtesy `tags_for` extends to an unregistered condition.
            covers = (name,)
        if key and key in covers:
            return str(raw)
        if said & set(covers):
            return str(raw)
        # A stat block writes the noun and the condition table holds the adjective:
        # "immune to petrification" against the `petrified` condition. Matched on a
        # five-character stem, which is long enough that `sleep` does not answer for
        # `slept-in` and short enough that every inflection in the corpus lands.
        if key and len(name) >= 5 and (key.startswith(name[:5])
                                       or name.startswith(key[:5])):
            return str(raw)
    return ""
