"""The labelled beats the round-trip check (gm/beat_verify.py) is measured against.

Built 2026-10-03 for lane V of the structured turn (docs/beat-verify.md). Every passage is
prose the narrator really wrote, cut to the few sentences a label needs — the owner's
saves are never committed, so only these short excerpts are. Sources:

  * kesst:<n>   the owner's save of 2026-10-03 as played on the merged branch (the live
                check of docs/playtest-2026-10-03.md), turn n. A passage marked "draft" is
                the beat before a check repaired it: the shipped text with the flagged
                sentence (the `truth-checks` row) put back where it stood.
  * talk:<n>    the market-talk copy of the same save played live, turn n.
  * bobby:<n>   the Bobby corpus of 2026-09-28 (tests/replays), turn n.

Each beat carries the ENGINE's side as `gm.beat_verify.Facts` takes it (the place the beat
began, where the engine holds the party now, the pack after the turn, the people here, the
clock, this turn's outcomes) and two labels written by hand:

  * `claims` — what the passage's NARRATION claims happened, in the engine's vocabulary.
    A claim marked `opt` is defensible either way: the scorer neither rewards nor
    punishes it. A slot given as a list accepts any of its values.
  * `alarms` — the contradictions and omissions a correct comparison raises, by category;
    `may_alarm` lists categories where an alarm is defensible but not required.

Conventions:
  * moving about inside the place (to the anvil, the counter, toward somebody) is NOT a
    move; stepping out into a street the engine has no place for is a move to
    "somewhere not listed".
  * looking down, kneeling, a hand resting on a thing, the tension leaving shoulders is
    not harm, and not a thing changing hands.
  * a thing the player already holds being shouldered or tucked away is no change.
  * speech claims nothing: "'The payment is yours,'" is a character talking.
"""
from __future__ import annotations

ZH_PLACES = ("the market", "the docks", "the tavern", "the counting house",
             "the great square", "the north crossing", "the east crossing",
             "the south crossing", "the storage area", "the smithy")
# Founded places and what they are, for the regex harness's Place objects.
ZH_KINDS = {"the smithy": ("smithy", "the counting house"),
            "the storage area": ("warehouses", "the docks")}
# The scripted sessions of 2026-09-25 (tests/replay), on the Pangrella fixture's Zhilvarnia.
PG_PLACES = ("the market", "the gate", "the north crossing", "the west crossing",
             "the great square", "the docks", "the approach")
VM_PLACES = ("the way in", "the market", "the well", "the guildhall", "the lane",
             "the green", "the upper floor of the guildhall", "the approach", "the edge")

KESST = ["pc", "Kesst Vayr", "", True]
SMITH = ["c13", "the smith", "Korvu"]
CLERK = ["c12", "the clerk of the counting house", "Korvu"]
LABORER = ["c11", "lone laborer", "Korvu"]
SERVANT = ["c1", "the servant carrying jugs two at a time", ""]
COAT = ["c4", "man in the heavy coat", "Korvu"]
BOBBY = ["pc", "Bobby", "", True]
JERKIN = ["c8", "man in a stained leather jerkin", "commoner"]
WATCH = ["c1", "the watchman waving traffic through", "Orc"]

PG_C2 = ["c2", "Commoner", "commoner"]
PG_C3 = ["c3", "Commoner", "commoner"]
PG_LEATHER = ["c4", "man in a stained leather", "commoner", False, "down"]
PG_DESP = ["c7", "desperate stranger", "commoner"]

REFUSED_SALE = {"intent_id": "i2", "op": "sell", "status": "refused", "effects": [],
                "tell": "The smith's counter is not open yet; it opens at first light."}


# The caravan ambush on the road out of Xylorvotha (the fixture world), 2026-10-09: the
# player beaten, robbed and left, and the Continue after (docs/narrator-after-defeat.md).
# The raiders are held off stage ("made-off") — "away" to the read back.
XY_PLACES = ("the road to Kalixiri",)
XY_TAM = ["pc", "Tam a", "", True]
XY_MASTER = ["c1", "Vyraxys Vexarion", "trader"]
XY_DROVER = ["c2", "the drover", "commoner"]
XY_DROVER2 = ["c3", "the second drover", "commoner"]
XY_RAIDER = ["c4", "the raider", "", False, "away"]
XY_RAIDER2 = ["c5", "the second raider", "", False, "away"]
XY_PEOPLE = (XY_TAM, XY_MASTER, XY_DROVER, XY_DROVER2, XY_RAIDER, XY_RAIDER2)


# The owner's ore seam on the ridgelines above an Aurvantis town (sammy.json, 2026-10-09):
# a creature holding the seam (`state.holding-ground`), the player asleep in front of it
# for twelve hours. The engine kept it there; the narrator wrote it gone.
RG_PLACES = ("the ridgelines", "the outskirts", "the road to Blackline")
RG_SAMMY = ["pc", "Sammy", "", True]
RG_HOLDER = ["c28", "Aelzeldra", "monstrous humanoid"]
RG_REST = {"intent_id": "i1", "op": "rest", "status": "resolved",
           "tell": "Sammy rests for 12 hours.",
           "effects": [{"ref": "pc", "kind": "rest", "hours": 12}]}


# The market brawl of the 2026-10-16 report, as the engine held it: nobody grappled, nobody
# down, one blow a turn (gold beats "cond-*").
FB_WOMAN = ["c4", "woman with the braid", "commoner"]
FB_MISS = {"intent_id": "i1", "op": "attack", "status": "resolved", "effects": [],
           "tell": "Kesst Vayr's attack with the dagger misses the woman with the braid "
                   "(6 against AC 10)."}
FB_HIT = {"intent_id": "i1", "op": "attack", "status": "resolved",
          "tell": "Kesst Vayr hits the woman with the braid for 3 bludgeoning.",
          "effects": [{"ref": "c4", "kind": "damage", "amount": 3}]}
FB_GRAPPLE = {"intent_id": "n1", "op": "attack", "status": "resolved",
              "tell": "The woman with the braid grapples Kesst Vayr by 3: both of you gain "
                      "the grappled condition.",
              "effects": [{"ref": "pc", "kind": "condition", "condition": "grappled"},
                          {"ref": "c4", "kind": "condition", "condition": "grappled"}]}
FB_TRIP = {"intent_id": "i1", "op": "attack", "status": "resolved",
           "tell": "Kesst Vayr trips the woman with the braid by 4: she is prone.",
           "effects": [{"ref": "c4", "kind": "condition", "condition": "prone"}]}


# What kind of place each bench place is (`places.settings_for` of the place the game
# would hold): the same answers the game's own function gives for these places on the
# Pangrella and Aurvantis fixtures (tests/test_setting_read.py pins them there).
_ST, _IN, _TV, _CO, _UN, _SH = ("a town street, square or market", "inside a building",
                                "a tavern or inn", "open country", "underground",
                                "aboard a ship or boat")
PLACE_SETTINGS = {
    "the market": (_ST,), "the docks": (_ST, _SH), "the tavern": (_IN, _TV),
    "the counting house": (_IN,), "the great square": (_ST,), "the north crossing": (_ST,),
    "the east crossing": (_ST,), "the south crossing": (_ST,), "the west crossing": (_ST,),
    "the storage area": (_IN,), "the smithy": (_IN,), "the gate": (_ST, _CO),
    "the approach": (_CO,), "the edge": (_CO,), "the way in": (_ST, _CO), "the well": (_ST,),
    "the guildhall": (_IN,), "the lane": (_ST,), "the green": (_ST, _CO),
    "the upper floor of the guildhall": (_IN,), "the road to Kalixiri": (_CO,),
    "the ridgelines": (_CO,), "the outskirts": (_ST, _CO), "the road to Blackline": (_CO,),
}


def settings_of(beat) -> tuple[str, ...]:
    """The union of where the beat began, where it ends and what its walk passed through,
    as `facts_from` builds it."""
    if "settings" in beat:
        return tuple(beat["settings"])
    out: set[str] = set()
    for name in (beat["start"], beat["end"], *beat.get("went_by", ())):
        got = PLACE_SETTINGS.get(name)
        if got is None:
            return ()
        out |= set(got)
    return tuple(sorted(out))


def places_of(beat) -> tuple[str, ...]:
    return {"VM": VM_PLACES, "PG": PG_PLACES, "XY": XY_PLACES,
            "RG": RG_PLACES}.get(beat["world"], ZH_PLACES)


def facts(beat):
    """The beat's engine side as `gm.beat_verify.Facts` — the shape `facts_from(ctx)`
    builds in the game, so the bench compares exactly what the game compares."""
    from gm import beat_verify as bv

    people = tuple(bv.Person(ref=p[0], name=p[1], what=p[2],
                             pc=bool(p[3]) if len(p) > 3 else False,
                             down=len(p) > 4 and p[4] in ("down", "dead"),
                             dead=len(p) > 4 and p[4] == "dead",
                             # "away": held elsewhere in town (`beat_reader.away_people`).
                             here=not (len(p) > 4 and p[4] == "away"),
                             # The conditions the engine holds on them after the turn.
                             holds=tuple(p[5]) if len(p) > 5 else ())
                   for p in beat["people"])
    return bv.Facts(start=beat["start"], end=beat["end"], places=places_of(beat),
                    went_by=tuple(beat["went_by"]), pack=tuple(beat["pack"]),
                    props=tuple(beat["props"]), people=people, clock=beat["clock"],
                    outcomes=tuple(beat["outcomes"]), pc_ref="pc",
                    in_fight=bool(beat.get("fight")), settings=settings_of(beat),
                    blows=tuple(beat.get("blows") or ()),
                    arms=tuple(beat.get("arms") or ()))


def by_id(beat_id: str) -> dict:
    return next(b for b in GOLD if b["id"] == beat_id)


def C(cat: str, opt: bool = False, **slots) -> dict:
    return {"cat": cat, **slots, **({"opt": True} if opt else {})}


def B(id: str, source: str, text: str, *, start: str, end: str = "", world: str = "ZH",
      people=(), pack=(), props=(), clock=None, outcomes=(), went_by=(), player: str = "",
      reading=None, claims=(), alarms=(), may_alarm=(), fight: bool = False) -> dict:
    return {"id": id, "source": source, "text": text, "start": start, "end": end or start,
            "fight": fight,
            "world": world, "people": [list(p) for p in people], "pack": list(pack),
            "props": list(props), "clock": clock, "outcomes": list(outcomes),
            "went_by": list(went_by), "player": player, "reading": reading or {},
            "claims": list(claims), "alarms": list(alarms), "may_alarm": list(may_alarm)}


GOLD = [
    # --- the known cases (docs/playtest-2026-10-03.md, "what the live check found") ------
    B("anvil", "kesst:22 draft",
      "The heavy crate meets the dirt with a dull thud, the wood groaning under its own "
      "weight as it settles in the center of the floor. You move toward the anvil, the "
      "massive block of iron standing like a monument in the center of the room. The "
      "hammer-blows of the smiths continue, a steady, rhythmic pulse that seems to vibrate "
      "through the very soles of your boots.",
      start="the smithy", people=(KESST, SMITH), pack=("pouch", "coins"), props=("crate",),
      clock=88, player="I set the crate down on the ground and walk over toward the anvil.",
      reading={"actions": [{"act": "go", "place": "the anvil"}]},
      outcomes=[{"intent_id": "i2", "op": "give", "status": "resolved",
                 "tell": "Kesst Vayr sets down crate; it lies here.",
                 "effects": [{"ref": "pc", "kind": "give", "item": "crate", "how": "set_down",
                              "from": "pc", "to": ""}]}],
      claims=[C("hands", item="crate", **{"from": "pc"}, to=["the floor", "nobody"])]),
    B("takes-the-crate", "kesst:24",
      "You heave the crate back onto your shoulder; the weight is solid and reassuring, "
      "the wood rough against your palms. Beside you, the smith, Korvu, reaches out with a "
      "hand calloused into leather and takes the crate from you. He doesn't say a word of "
      "thanks, but he grips the handles with a steady, practiced hold. The transaction is "
      "finished, and the heavy door to the smithy is behind you.",
      start="the smithy", people=(KESST, SMITH), pack=("pouch", "crate"), clock=88,
      player="I pick the crate back up, then tip the coins from the pouch into my coin purse.",
      reading={"actions": [{"act": "take", "object": "the crate"},
                           {"act": "take", "object": "the coins"}]},
      outcomes=[{"intent_id": "i3", "op": "give", "status": "resolved",
                 "tell": "Kesst Vayr takes the crate.",
                 "effects": [{"ref": "pc", "kind": "give", "item": "crate", "how": "took",
                              "from": "", "to": "pc"}]}],
      claims=[C("hands", opt=True, item="crate", **{"from": ["the floor", "nobody"]}, to="pc"),
              C("hands", item="crate", **{"from": "pc"}, to="c13"),
              C("trade", item=["crate", "something else"], seller="pc", buyer="c13",
                settled=True),
              C("move", opt=True, place="somewhere not listed")],
      alarms=["hands", "trade"], may_alarm=["move"]),
    B("finalized", "kesst:25 draft",
      "The transaction is finalized. The heavy clink of the coin is the only thing that "
      "breaks the silence of the forge. Korvu takes the crate with a grunt, his grip steady "
      "as he turns toward the quenching vats in the rear. Outside, the pre-dawn light is "
      "just beginning to bleed into the gray, and the sounds of the city's waking drift "
      "through the cracks in the masonry. You stand on the threshold between the heavy "
      "labor of the forge and the open road ahead.",
      start="the smithy", people=(KESST, SMITH), pack=("pouch", "crate"), clock=88,
      player="I agree to sell the crate to the smith for whatever it is worth.",
      reading={"actions": [{"act": "sell", "object": "the crate", "target": "the smith"}]},
      outcomes=[REFUSED_SALE],
      claims=[C("trade", item=["crate", "something else"], seller="pc", buyer="c13",
                settled=True),
              C("hands", item="crate", **{"from": "pc"}, to="c13"),
              C("hour", part=["before dawn", "dawn"])],
      alarms=["trade", "hands", "hour"]),
    B("settled", "kesst:27 draft",
      "You thrust the heavy crate forward across the workbench and gesture toward it with "
      "a firm nod. The transition from the commerce of the counting house to the soot of "
      "the smithy is sharp; the transaction is settled, and the exchange is complete. The "
      "smith grunts and looks the crate over.",
      start="the smithy", people=(KESST, SMITH), pack=("pouch", "crate"), clock=88,
      player="I agree to sell the crate to the smith for whatever it is worth.",
      reading={"actions": [{"act": "sell", "object": "the crate", "target": "the smith"}]},
      outcomes=[REFUSED_SALE],
      claims=[C("trade", item=["crate", "something else"], seller="pc", buyer="c13",
                settled=True)],
      alarms=["trade"]),
    B("street", "kesst:21 draft",
      "The coins are heavy in your purse, a weight you'll have to carry, and the Brunt of "
      "the Weight is left behind on the dirt floor of the forge, its purpose finished. You "
      "step out of the heat of the smithy and into the cool, damp air of the street. The "
      "heavy thud of boots in the hall behind you has grown louder. You turn your collar up "
      "against the draft and begin to move through the pre-dawn gloom of the district.",
      start="the smithy", people=(KESST, SMITH),
      pack=("brunt of the weight", "crate", "pouch", "coins"), clock=88,
      player="I transfer the coins from the pouch into my coin purse. I also drop the Brunt "
             "of the weight on the ground and leave it behind.",
      reading={"actions": [{"act": "give", "target": "the Brunt of the weight",
                            "place": "the ground"}, {"act": "leave", "place": "behind"}]},
      outcomes=[{"intent_id": "i2", "op": "give", "status": "resolved",
                 "tell": "the smith takes Brunt of the weight.",
                 "effects": [{"ref": "c13", "kind": "give", "item": "Brunt of the weight"}]}],
      claims=[C("move", place="somewhere not listed"),
              C("hands", item="brunt of the weight", **{"from": "pc"},
                to=["the floor", "nobody"]),
              C("hour", part=["before dawn", "night"])],
      # The engine handed the brunt to the smith and left the player a copy (playtest
      # item 5, since fixed): against that state the page's drop IS a contradiction, and
      # the hour is one at 01:28 only if read as "before dawn".
      # Stepping out into the street is a setting the engine does not hold either: the
      # same defect as the move, read a second way.
      alarms=["move", "hands"], may_alarm=["hour", "setting"]),
    B("first-hint-of-dawn", "kesst:19",
      "The leather pouch is heavy in your palm, the weight of the coins shifting with every "
      "movement. You pull the drawstring and tip the contents into your hand. The clerk "
      "watches you, his expression unreadable. 'The payment is yours,' he repeats, the "
      "words almost a warning. Outside, the first hint of dawn is beginning to grey the "
      "edges of the windows, and the heavy thud of boots can be heard starting in the "
      "corridors behind the main hall.",
      start="the counting house", people=(KESST, CLERK), pack=("crate", "pouch"), clock=80,
      player="I take the pouch and count the coins.",
      outcomes=[{"intent_id": "i2", "op": "give", "status": "resolved",
                 "tell": "Kesst Vayr takes pouch.",
                 "effects": [{"ref": "pc", "kind": "give", "item": "pouch"}]}],
      claims=[C("hands", opt=True, item="pouch", **{"from": ["c12", "nobody"]}, to="pc"),
              C("hour", part="dawn")],
      alarms=["hour"]),
    B("morning-at-the-docks", "kesst:7",
      "The transition from the crowded streets is marked first by the knot of voices at "
      "the north crossing, then the vast, echoing openness of the great square, and "
      "finally the heavy, hanging architecture of the east crossing. Now, the air is thick "
      "with the smell of brine and drying timber. The docks are a forest of masts and the "
      "frantic, rhythmic work of the morning; crates are being winched from the hulls. "
      "Amidst the shouting of sailors, a man is struggling with a heavy, sodden crate near a "
      "stack of hempen rope, his hands bleeding where the wood has splintered.",
      start="the market", end="the docks", people=(KESST,), clock=32,
      went_by=("the north crossing", "the great square", "the east crossing"),
      player="I Walk to the docks",
      reading={"actions": [{"act": "go", "place": "the docks"}]},
      outcomes=[{"intent_id": "i1", "op": "travel", "status": "resolved",
                 "tell": "You are at the docks now.",
                 "effects": [{"kind": "biome", "place": "x~urban:the-docks",
                              "was_place": "x~urban:the-market",
                              "went_by": ["the north crossing", "the great square",
                                          "the east crossing"]}]}],
      claims=[C("move", place=["the docks", "the north crossing", "the great square",
                               "the east crossing"]),
              C("hour", part="morning"),
              C("harm", opt=True, who="someone not listed", how="hurt")],
      alarms=["hour"]),
    B("eyes-drop", "kesst:17",
      "The clerk's eyes drop to the floor for a heartbeat, as if measuring the distance "
      "between your voice and his ears, before he looks back up. He leans over the "
      "counter, the wood groaning slightly under his weight. He reaches out and places a "
      "large, calloused hand on the edge of the crate, his grip steady.",
      start="the counting house", people=(KESST, CLERK),
      pack=("brunt of the weight", "crate"), clock=80,
      player="I lean in and whisper, \"I just need it handled quietly.\""),
    B("payment-is-yours", "kesst:18",
      "He produces a small, leather pouch from beneath the counter; the weight of the coin "
      "inside is unmistakable. He slides it across the wood toward you, the metal clinking "
      "with a dull, heavy sound. 'The payment is yours. The crate is mine. The record is "
      "sealed.' He takes the paper back from you, and the transaction is finalized in the "
      "eyes of the guild.",
      start="the counting house", people=(KESST, CLERK),
      pack=("brunt of the weight", "crate"), clock=80,
      player="I tell the clerk to give me the money and he can have the crate and sign the "
             "sheet.",
      reading={"actions": [{"act": "talk", "target": "the clerk"}]},
      # No sell resolved: the crate stayed in the pack for six more turns.
      claims=[C("hands", opt=True, item="something else", **{"from": "c12"}, to="pc"),
              C("trade", item=["crate", "something else"], seller="pc", buyer="c12",
                settled=True)],
      alarms=["trade"]),
    B("counter-and-go", "kesst:13",
      "You set the heavy crate down upon the counter with a thud that vibrates through the "
      "wood, the man's eyes narrowing as he takes it from your hands. You turn your back on "
      "the man and the exchange; you pass through the docks and move into the shadow of the "
      "east crossing. The walk brings you into the great square, before you pass under the "
      "arch of the south crossing and into the counting house.",
      start="the storage area", end="the counting house", people=(KESST, CLERK),
      pack=("brunt of the weight", "crate"), clock=80,
      went_by=("the docks", "the east crossing", "the great square", "the south crossing"),
      player="I take the crate to the man in the counting house who will buy it from me.",
      reading={"actions": [{"act": "take", "object": "the crate"},
                           {"act": "go", "place": "the man in the counting house"}]},
      outcomes=[{"intent_id": "i1", "op": "travel", "status": "resolved",
                 "tell": "You are at the counting house now.",
                 "effects": [{"kind": "biome", "place": "x~urban:the-counting-house",
                              "was_place": "x~urban:the-docks/the-storage-area",
                              "went_by": ["the docks", "the east crossing",
                                          "the great square", "the south crossing"]}]},
                {"intent_id": "i2", "op": "give", "status": "resolved",
                 "tell": "Kesst Vayr takes crate.",
                 "effects": [{"ref": "pc", "kind": "give", "item": "crate"}]}],
      claims=[C("move", place=["the counting house", "the south crossing"]),
              C("hands", item="crate", **{"from": "pc"}, to=["someone not listed", "c12"]),
              C("hands", opt=True, item="crate", **{"from": "pc"}, to="the floor")],
      alarms=["hands"]),
    B("picked-up-unresolved", "kesst:23",
      "You grip the edges of the wood and heave the heavy crate from the dirt. You tip the "
      "leather pouch over your purse, letting the coins clatter into the pocket.",
      start="the smithy", people=(KESST, SMITH), pack=("pouch", "coins"), props=("crate",),
      clock=88,
      player="I pick the crate back up, then tip the coins from the pouch into my coin purse.",
      reading={"actions": [{"act": "take", "object": "the crate"},
                           {"act": "take", "object": "the coins"}]},
      # Only narrate_only resolved: the deeds repair wrote a pick-up the engine never made.
      claims=[C("hands", item="crate", **{"from": ["the floor", "nobody"]}, to="pc"),
              C("hands", opt=True, item="coins", **{"from": ["pc", "nobody"]}, to="pc")],
      alarms=["hands"]),

    # --- clean beats: every one must raise nothing -----------------------------------------
    B("stranger-pack", "kesst:9",
      "You step into the heavy pack and haul the weight onto your own shoulders, the rough "
      "grain of the leather biting into your collar as the merchant's eyes widen and his "
      "mouth hangs open. You don't wait for him to find his voice; you turn and walk away, "
      "leaving him and the man behind him as the docks fall away. The storage area is a "
      "forest of high, timber-framed buildings. A few paces ahead, a lone laborer is "
      "struggling with a stubborn, oversized crate at the base of a loading ramp.",
      start="the docks", end="the storage area", people=(KESST, LABORER),
      pack=("brunt of the weight",), clock=40,
      player="I take the brunt of the weight and move it toward the storage area.",
      reading={"actions": [{"act": "take", "object": "the brunt of the weight"},
                           {"act": "go", "place": "the storage area"}]},
      outcomes=[{"intent_id": "i2", "op": "travel", "status": "resolved",
                 "tell": "You are at the storage area now.",
                 "effects": [{"kind": "biome", "place": "x~urban:the-docks/the-storage-area",
                              "was_place": "x~urban:the-docks"}]},
                {"intent_id": "i4", "op": "give", "status": "resolved",
                 "tell": "Kesst Vayr takes brunt of the weight.",
                 "effects": [{"ref": "pc", "kind": "give", "item": "brunt of the weight"}]}],
      claims=[C("move", place="the storage area"),
              C("hands", item=["brunt of the weight", "something else"],
                **{"from": ["someone not listed", "nobody"]}, to="pc")]),
    B("into-the-smithy", "kesst:20",
      "The heavy door of the ledger-room clicks shut behind you, muffling the clerk's "
      "unfinished sentence as you step into the heat of the forge. You are inside the "
      "smithy now. Near the main anvil, a pair of smiths are working in tandem, one holding "
      "a heavy piece of bronze while the other strikes it with a heavy mallet. You tuck the "
      "coins into your pouch and move toward the side door.",
      start="the counting house", end="the smithy", people=(KESST, SMITH),
      pack=("brunt of the weight", "crate", "pouch", "coins"), clock=88,
      player="I pocket the coins and head for the side door.",
      outcomes=[{"intent_id": "i2", "op": "travel", "status": "resolved",
                 "tell": "You are at the smithy now.",
                 "effects": [{"kind": "biome", "place": "x~urban:the-counting-house/the-smithy",
                              "was_place": "x~urban:the-counting-house"}]},
                {"intent_id": "i3", "op": "give", "status": "resolved",
                 "tell": "Kesst Vayr takes coins.",
                 "effects": [{"ref": "pc", "kind": "give", "item": "coins"}]}],
      claims=[C("move", place="the smithy"),
              C("hands", opt=True, item="coins", **{"from": ["pc", "nobody"]}, to="pc")]),
    B("midnight-air", "talk:5",
      "The market is a cavern of shadows and hushed whispers under the weight of the "
      "midnight air. The scent of stale spice and damp timber hangs heavy in the "
      "atmosphere. Around you, the stalls are mostly silent, their colorful awnings drooping "
      "like tired eyelids.",
      start="the market", people=(KESST, SERVANT, COAT), clock=0,
      player="I ask him who the master of the docks is.",
      claims=[C("hour", part="night")]),
    B("first-light-wait", "kesst:28",
      "The hours bleed into one another in a heavy, metallic silence. Outside, the city "
      "wakes, and the first faint light of dawn begins to gray the windows of the smithy. "
      "The crate sits before you, a solid weight in the center of the room. When the first "
      "real light breaks, the heavy door creaks open. A man enters, his face still weary "
      "from the night, and he stops before the workbench, his eyes falling on the crate.",
      start="the smithy", people=(KESST, SMITH), pack=("pouch",), props=("crate",),
      clock=360, player="I wait in the smithy until first light.",
      outcomes=[{"intent_id": "i2", "op": "advance_time", "status": "resolved",
                 "tell": "272 minutes pass.", "effects": [{"kind": "time"}]}],
      claims=[C("hour", part="dawn"),
              C("arrived", who=["someone not listed", "c13"])],
      # "A man enters" while the smith stood there: the playtest's "re-entered a present
      # person as a newcomer". Defensible to flag, not required.
      may_alarm=["presence"]),
    B("sold", "kesst:32",
      "You stand firm, the weight of the transaction settling between you. He finally "
      "closes his hand around one of the shards. 'Then it is settled,' he says. 'The terms "
      "are signed in the work.' He looks back at you, the deal concluded.",
      start="the smithy", people=(KESST, SMITH), pack=("pouch",), clock=360,
      player="I tell the smith, \"It's a deal. You can have the crate.\"",
      outcomes=[{"intent_id": "i3", "op": "sell", "status": "resolved",
                 "tell": "Kesst Vayr sells the crate to the smith for 7 silver pieces, 5 "
                         "copper pieces.",
                 "effects": [{"ref": "pc", "kind": "sold", "item": "crate", "to": "c13"}]}],
      claims=[C("trade", item=["crate", "something else"], seller="pc", buyer="c13",
                settled=True)]),
    B("looking-for-work", "kesst:3",
      "The man's fist is still trembling slightly, and he looks at you with a mixture of "
      "suspicion and a strange, weary curiosity. He looks at the cup on the floor, then back "
      "at your face, and his voice drops to a low, gravelly rumble. 'You're looking for "
      "work, then?' He gestures with a jerk of his head toward the door. He doesn't move to "
      "strike you again, but he doesn't offer a hand either.",
      start="the market", people=(KESST, SERVANT, COAT), clock=0,
      player="\"Is there anything I can do to earn some coin?\""),
    B("man-on-the-stool", "kesst:0",
      "The man on the stool blinks, his eyes darting to the door, then to the man at the "
      "bar, and finally back to you. In the distance, the steady thrum of the docks and the "
      "distant tolling of a bell provide the only constant. You stand your ground, the smell "
      "of stale ale and damp wood clinging to the room.",
      start="the market", people=(KESST, SERVANT, COAT), clock=0,
      player="What is going on?",
      # The market-talk taproom (gm/checks/setting_kind.py's own measurement): a bar and
      # a room round a party the engine held at the market. Labelled 2026-10-16 when the
      # read back learned the kind of place.
      alarms=["setting"]),
    B("rapier", "talk:7",
      "The heavy fabric of his coat creaks like old timber as he shifts his weight, the "
      "sound cutting through the quiet of the night. When you ask where a rapier might be "
      "sharpened, he doesn't point toward the center of the market, but instead gestures "
      "toward the far end of the promenade where the shadows of the warehouse district "
      "begin to stretch. He leans back again, his posture signaling that his advice is "
      "finished.",
      start="the market", people=(KESST, SERVANT, COAT), clock=0,
      player="I ask the man in the heavy coat where I could get my rapier sharpened.",
      claims=[C("hour", part="night")]),
    B("broken-tide", "talk:8",
      "A dry, rasping grunt escapes the man in the heavy coat, the sound of a person who has "
      "finished their part in the exchange. He turns his head toward the end of the "
      "promenade. He turns his gaze away from you, looking back toward the market center as "
      "if he is ready to let you go, the heavy wool of his coat seemingly swallowing the dim "
      "light around him.",
      start="the market", people=(KESST, SERVANT, COAT), clock=0,
      player="\"Who is he, and where exactly can I find him?\""),
    B("laborer", "kesst:10",
      "The laborer, his face etched with the deep lines of a life spent under heavy loads, "
      "stops his struggle and looks up. He sees the size of the crate you carry, the way the "
      "leather straps dig into your shoulders, and he offers a short, appreciative grunt. "
      "'That's a heavy one for a single back,' he says. 'The main gate's been jammed since "
      "the morning tide.'",
      start="the storage area", people=(KESST, LABORER), pack=("brunt of the weight",),
      clock=40, player="I approach the laborer to see if he needs help",
      outcomes=[{"intent_id": "i1", "op": "move", "status": "resolved",
                 "tell": "Kesst Vayr moves to near (30 ft).",
                 "effects": [{"ref": "pc", "kind": "position", "from": [3, 6], "to": [0, 6]}]}]),
    B("evening-shift", "kesst:11",
      "Korvu leans his head back against the timber post. He watches a speck of dust dance "
      "in a shaft of light between the rafters before he speaks. 'The evening shift starts "
      "when the sun hits the spire of the counting house,' he says. He looks at your crate "
      "again, then at the dirt on your boots.",
      start="the storage area", people=(KESST, LABORER), pack=("brunt of the weight",),
      clock=40, player="I ask him about the 'evening shift' he mentioned."),
    B("sell-it-to-me", "kesst:12",
      "Korvu watches you for a long moment. The mention of coin makes him let out a short, "
      "dry chuckle that turns into a cough. 'Sell it to me?' he says. 'I'm just a man with a "
      "shovel and a heavy list of debts.' He leans closer, the smell of old sweat and dry "
      "earth clinging to him.",
      start="the storage area", people=(KESST, LABORER), pack=("brunt of the weight",),
      clock=40, player="I try to sell the crate to Korvu for coin",
      reading={"actions": [{"act": "sell", "object": "the crate", "target": "Korvu"}]}),
    B("flirt", "kesst:14",
      "You lean against the counter, the wood smooth and cool beneath your palms, and let a "
      "slow, practiced smile play across your lips. You catch the clerk's eye as you gesture "
      "to the heavy crate. The clerk stops his work, the scale settling, and he looks at "
      "you. The air between you hums, the dust motes dancing in the shafts of light as he "
      "considers the offer of the crate.",
      start="the counting house", people=(KESST, CLERK),
      pack=("brunt of the weight", "crate"), clock=80,
      player="I smile and flirt with the clerk and offer the crate for coin.",
      reading={"actions": [{"act": "sell", "object": "the crate"}]},
      claims=[C("trade", opt=True, item="crate", seller="pc", buyer="c12", settled=False)]),
    B("silence", "kesst:15",
      "The silence stretches, heavy and thick as the dust in the air. The clerk remains "
      "still, his hand still resting on the scale. He looks at the crate, then back to your "
      "face. Finally, he lets out a breath that is almost a sigh, and the tension in his "
      "shoulders drops just enough for him to lean forward.",
      start="the counting house", people=(KESST, CLERK),
      pack=("brunt of the weight", "crate"), clock=80,
      player="I simply watch him, letting the silence do the work."),
    B("lid", "kesst:29",
      "The man at the workbench, the smith, does not look up from the crate as you speak. "
      "He reaches out, his fingers hooking under the edge of the lid. The wood of the lid "
      "groans as he heaves it back just a few inches, and the smell of something sharp and "
      "metallic wafts out into the cool morning air.",
      start="the smithy", people=(KESST, SMITH), pack=("pouch",), props=("crate",),
      clock=360,
      player="I tell the smith I'd like to sell him the crate, and agree to whatever it's "
             "worth.",
      claims=[C("hour", part=["morning", "dawn"])]),
    B("pry-bar", "kesst:30",
      "The smith's grip on the pry-bar tightens as he hears your words. He jams the iron "
      "bar into the seam of the lid and heaves. The wood doesn't just crack; it splinters "
      "with a violent, explosive pop that sends a spray of splinters across the workbench. "
      "The smith stares at the shards, his eyes widening, the pry-bar still gripped in his "
      "shaking hands.",
      start="the smithy", people=(KESST, SMITH), pack=("pouch",), props=("crate",),
      clock=360, player="\"It's a deal. You can have the crate.\""),

    # --- the Bobby corpus (no clock was kept then: the hour is not judged) -----------------
    B("gates-receive", "bobby:5",
      "The dusty road stretches out behind you, the path through the well now a memory in "
      "the haze. You stand at the way in, the gates of Vormoor open to receive you. The "
      "morning sun is beginning to bake the dust of the road into a fine powder. Near the "
      "main gate, the watchmen are making their rounds, their heavy boots thudding against "
      "the cobblestones.",
      world="VM", start="the market", end="the way in", people=(BOBBY, WATCH),
      went_by=("the well",),
      player="I leave the village and stand outside it. I look around to get a bearing of "
             "where I am and where another larger city might be.",
      outcomes=[{"intent_id": "i1", "op": "travel", "status": "resolved",
                 "tell": "The way there ran through the well. You are at the way in now.",
                 "effects": [{"kind": "biome", "place": "v~urban:the-way-in",
                              "was_place": "v~urban:the-market", "went_by": ["the well"],
                              "met": "patrol"}]}],
      claims=[C("move", place="the way in"), C("hour", opt=True, part="morning")]),
    B("paths-diverge", "bobby:6",
      "You pause at the entrance to the village, the wide road of the way in stretching "
      "behind you. To your left, the main thoroughfare branches off, leading toward the "
      "heart of the settlement where the market and the guildhall stand. The watchman gives "
      "you a nod as you stand at this junction. You are standing where the paths diverge.",
      world="VM", start="the way in", people=(BOBBY, WATCH),
      player="I walk to the nearest crossroads and look for directions to other places",
      reading={"actions": [{"act": "go", "place": "the nearest crossroads"}]},
      outcomes=[{"intent_id": "i1", "op": "found", "status": "refused",
                 "tell": "There is no such kind of place as 'crossroads'."},
                {"intent_id": "i2", "op": "travel", "status": "refused",
                 "tell": "There is no the nearest crossroads here to go to."}],
      claims=[C("move", place="somewhere not listed")],
      alarms=["move"]),
    B("outskirts", "bobby:7",
      "You turn your back to the village, seeking the signs of the world beyond the way in. "
      "The path leading out of Vormoor is a wide, scar-like track that stretches toward the "
      "high country. The silence of the open road is heavy, broken only by the occasional "
      "cry of a scavenger bird and the crunch of gravel beneath your feet. You are now on "
      "the outskirts, where the immediate reach of Vormoor's presence fades into the "
      "distance.",
      world="VM", start="the way in", people=(BOBBY, WATCH),
      player="I take the path away from town until I see signage of other destinations",
      reading={"actions": [{"act": "go", "place": "the path away from town"}]},
      outcomes=[{"intent_id": "i1", "op": "found", "status": "refused",
                 "tell": "There is no such kind of place as 'road'."},
                {"intent_id": "i2", "op": "travel", "status": "refused",
                 "tell": "There is no the crossroads here to go to."}],
      claims=[C("move", place=["somewhere not listed", "the approach", "the edge"])],
      alarms=["move"]),
    B("approach", "bobby:9",
      "The open expanse of the plains falls away as the timber crowds in. You have left the "
      "highway behind, moving into the shadow of the gnarled trees. You are at the approach, "
      "where the path narrows. Leaning against a moss-covered stone is a man in a stained "
      "leather jerkin, methodically sharpening a heavy skinning knife.",
      world="VM", start="the way in", end="the approach", people=(BOBBY, JERKIN),
      player="I head west into the gnarled dense trees",
      outcomes=[{"intent_id": "i1", "op": "travel", "status": "resolved",
                 "tell": "You are at the approach now.",
                 "effects": [{"kind": "biome", "place": "v~forest:the-approach",
                              "was_place": "v~urban:the-way-in"}]}],
      claims=[C("move", place="the approach")]),
    B("burning-hands", "bobby:13",
      "A brilliant, searing cone of orange and white heat surges toward him. His eyes "
      "widen, his mouth opening in a silent cry as the heat licks across his face and the "
      "heavy leather of his tunic. When the magic finally collapses, the man is thrown "
      "backward by the concussive force of the heat. He hits the ground hard, his face "
      "blackened by soot, his hands clutching his scorched arms as he gasps for breath. He "
      "grips his sword hilt with both hands, his stance wide and defiant.",
      world="VM", start="the approach", people=(BOBBY, JERKIN),
      player="I cast Burning Hands",
      outcomes=[{"intent_id": "i1", "op": "cast", "status": "resolved",
                 "tell": "Bobby casts Burning Hands. 1d4 - 1.",
                 "rolls": [{"label": "Burning Hands damage", "total": 1}],
                 "effects": [{"ref": "pc", "kind": "cast", "name": "Burning Hands",
                              "targets": []}]}],
      claims=[C("harm", who="c8", how="hurt"),
              C("harm", opt=True, who="c8", how="down"),
              # The body's conditions (2026-10-16), labelled before the slot ran: "He
              # hits the ground hard" with nothing knocking him down in the engine.
              C("condition", opt=True, who="c8", condition="prone")],
      alarms=["harm"], may_alarm=["condition"]),
    B("whetstone", "bobby:10",
      "The man studies you, his gaze lingering on the way your hands rest on your gear. He "
      "gestures with the whetstone toward a fork in the path. He leans back against the "
      "mossy stone, his posture relaxed but his eyes remain sharp.",
      world="VM", start="the approach", people=(BOBBY, JERKIN),
      player="I say to the man \"lost implies I had a particular destination in mind.\""),
    B("cart-owner", "bobby:1",
      "The watchman stands by the stone wall, the heavy leather of his gloves creaking as "
      "he shifts his weight. The merchant has moved further down the line, distracted by a "
      "shouting fish-seller. He spits a thick glob of phlegm into the dirt and gestures with "
      "a heavy thumb toward the cart.",
      world="VM", start="the way in", people=(BOBBY, WATCH),
      player="I look for the owner of the stalled cart",
      claims=[C("left", opt=True, who="someone not listed")]),
    B("no-fire", "bobby:12",
      "The air is still, and the woods are heavy with the scent of damp earth and pine. But "
      "no fire erupts in the canopy. The man in the stained leather jerkin suddenly halts. "
      "He stands, his heavy frame tensing as he takes a step forward, his hand gripping the "
      "hilt of the blade he was just sharpening.",
      world="VM", start="the approach", people=(BOBBY, JERKIN),
      player="I cast burning hands into the tree tops"),
    B("morning-mist", "bobby:3",
      "He leans back against the stone, his presence a solid, immovable weight in the "
      "morning mist. He gestures toward the town center, a broad, sweeping motion of his "
      "arm. You can see the path toward the market now.",
      world="VM", start="the way in", people=(BOBBY, WATCH),
      player="I ask him about the girl in the market.",
      claims=[C("hour", opt=True, part="morning")]),

    # --- HELD OUT: labelled before any run, never shown to the prompt or the questions ------
    # The scripted sessions of 2026-09-25 (tests/replay/*-gemma4-12b.jsonl.gz), recorded
    # with the narrator of the day. The confirmation questions and the quote rules were
    # shaped on the beats above; these say whether that shaping generalises.
    B("ho-fist-misses-floor", "fight:13 (held out)",
      "The crowd's tension breaks as he commits to the strike, and your fist meets his face "
      "in a blunt, heavy strike. The impact sends his head snapping back, the force of your "
      "punch throwing his balance wide as he stumbles into the nearest table. The wood "
      "groans and shatters under the weight of his fall. He hits the ground hard, the air "
      "leaving his lungs in a wheeze, and the crowd falls into a stunned, heavy silence.",
      world="PG", start="the west crossing", people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      player="I punch him again.",
      outcomes=[{"intent_id": "i1", "op": "attack", "status": "resolved",
                 "tell": "Kesst Vayr's attack misses Commoner (9 against AC 10).",
                 "effects": []}],
      claims=[C("harm", who=["c2", "c3"], how="hurt"),
              C("harm", opt=True, who=["c2", "c3"], how="down"),
              C("condition", opt=True, who=["c2", "c3"], condition="prone")],
      alarms=["harm"], may_alarm=["condition"]),
    B("ho-sickening-thud", "fight:14 (held out)",
      "The man's head snaps back from your blow, and he falls, the back of his head hitting "
      "the cobblestones with a sickening thud. He doesn't move. The crowd is frozen, a wall "
      "of faces and eyes watching the blood pool around the man in the stained leather.",
      world="PG", start="the west crossing", people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      player="I keep hitting him.",
      outcomes=[{"intent_id": "i1", "op": "attack", "status": "resolved",
                 "tell": "Kesst Vayr's attack misses Commoner (6 against AC 10).",
                 "effects": []}],
      claims=[C("harm", who=["c2", "c3", "c4"], how=["hurt", "down", "dead"]),
              C("harm", opt=True, who=["c2", "c3", "c4"], how=["down", "dead", "hurt"]),
              C("condition", opt=True, who=["c2", "c3", "c4"], condition="prone")],
      alarms=["harm"], may_alarm=["condition"]),
    B("ho-first-fall", "fight:3 (held out)",
      "The man's head snaps back from the force of your fist, his body reeling into the "
      "heavy crate with a dull thud. He collapses into the mud, the air leaving his lungs in "
      "a wet gasp as he hits the ground, and the heavy thud of his body against the wood is "
      "the only sound in the sudden, ringing silence of the square.",
      world="PG", start="the west crossing",
      people=(KESST, ["c4", "man in a stained leather", "commoner", False, "down"]),
      player="I punch him again.",
      outcomes=[{"intent_id": "i1", "op": "attack", "status": "resolved",
                 "tell": "Kesst Vayr hits man in a stained leather for 7 piercing. man in a "
                         "stained leather is unconscious and dying.",
                 "effects": [{"ref": "c4", "kind": "damage", "amount": 7},
                             {"ref": "c4", "kind": "condition", "condition": "unconscious"},
                             {"ref": "c4", "kind": "condition", "condition": "dying"}]}],
      claims=[C("harm", who="c4", how="hurt"), C("harm", who="c4", how="down"),
              C("condition", opt=True, who="c4", condition="prone")]),
    B("ho-lies-still", "fight:6 (held out)",
      "The man in stained leather lies still beneath you, the dirt of the west crossing "
      "mingling with the blood on his tunic. The crowd has halted; the heavy, rhythmic thump "
      "of boots on cobblestone echoes from the nearest lane as the local watch responds to "
      "the outcry.",
      world="PG", start="the west crossing", people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      player="I stand over him and tell him to stay down.",
      outcomes=[{"intent_id": "i2", "op": "say", "status": "resolved", "tell": "",
                 "effects": [{"kind": "said", "to": ""}]},
                {"intent_id": "n1", "op": "attack", "status": "resolved",
                 "tell": "Commoner's attack misses Kesst Vayr (5 against AC 15).",
                 "effects": []}],
      claims=[C("harm", opt=True, who="c4", how=["down", "hurt"]),
              C("condition", opt=True, who="c4", condition="prone")]),
    B("ho-stool-misses", "fight:8 npc (held out)",
      "The commoner swings the heavy stool with a desperate, panicked grunt, but the wood "
      "whistles through the air and strikes only empty space. The intruder remains "
      "untouched, their stance unbroken by the clumsy blow.",
      world="PG", start="the west crossing", people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      outcomes=[{"intent_id": "n1", "op": "attack", "status": "resolved",
                 "tell": "Commoner's attack misses Kesst Vayr (6 against AC 15).",
                 "effects": []}]),
    B("ho-shove-lands", "fight:8 npc (held out)",
      "The commoner lunges forward and slams their weight into you, their heavy hands "
      "striking your chest with enough force to knock the wind from your lungs. You stumble "
      "back a few paces, your footing momentarily faltering as they struggle to clear the "
      "path.",
      world="PG", start="the west crossing", people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      outcomes=[{"intent_id": "n1", "op": "attack", "status": "resolved",
                 "tell": "Commoner hits Kesst Vayr for 2 bludgeoning.",
                 "effects": [{"ref": "pc", "kind": "damage", "amount": 2}]}],
      claims=[C("harm", who="pc", how="hurt")]),
    B("ho-swing-misses", "fight:12 npc (held out)",
      "The commoner lunges forward with a desperate, frantic swing, but their strike misses "
      "your guard entirely. The blade whistles through the air, narrowly missing your "
      "shoulder and clattering harmlessly against the stone behind you.",
      world="PG", start="the west crossing", people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      outcomes=[{"intent_id": "n1", "op": "attack", "status": "resolved",
                 "tell": "Commoner's attack misses Kesst Vayr (13 against AC 15).",
                 "effects": []}]),
    B("ho-grasp-short", "fight:14 npc (held out)",
      "The commoner lunges forward, their voice cracking as they reach out to seize the "
      "intruder's attention and demand an answer. Their grasp falls short, however, and they "
      "stumble slightly as they fail to make contact with you.",
      world="PG", start="the west crossing", people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      outcomes=[{"intent_id": "n1", "op": "attack", "status": "resolved",
                 "tell": "Commoner's attack misses Kesst Vayr (9 against AC 15).",
                 "effects": []}]),
    B("ho-blow-lands", "fight:13 npc (held out)",
      "The commoner lunges forward, slamming their weight into the intruder with a "
      "desperate, heavy shove. The blow catches you squarely in the chest, knocking the "
      "wind from your lungs and sending you reeling back.",
      world="PG", start="the west crossing", people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      outcomes=[{"intent_id": "n1", "op": "attack", "status": "resolved",
                 "tell": "Commoner hits Kesst Vayr for 4 bludgeoning.",
                 "effects": [{"ref": "pc", "kind": "damage", "amount": 4}]}],
      claims=[C("harm", who="pc", how="hurt")]),
    B("ho-satchel", "fight:8 (held out)",
      "The man's satchel is heavy with the weight of stolen coin and trade-papers, and you "
      "snatch it from the dirt. His own blood is still wet on the leather. The crowd's roar "
      "has turned into a tense, watchful hush; they see you standing over him with the bag.",
      world="PG", start="the west crossing", people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      player="I take what he was carrying.",
      outcomes=[{"intent_id": "i1", "op": "use_item", "status": "refused",
                 "tell": "Kesst Vayr is not carrying the man's satchel.", "effects": []}],
      # The satchel is on no ledger the engine keeps, so nothing can judge the snatch: a
      # known limit, shared with the regex check it replaces (it reads the pack only).
      claims=[C("hands", item="something else",
                **{"from": ["the floor", "c4", "nobody", "someone not listed"]}, to="pc")]),
    B("ho-life-extinguished", "fight:10 (held out)",
      "The man in stained leather lies still at your feet, the blood from his wound staining "
      "the stones of the west crossing. A few feet away, the commoner, the one who gripped "
      "the stool, is watching you with wide eyes, his chest heaving. The air is thick with "
      "the smell of iron and the sudden, heavy silence of a crowd that has seen a life "
      "extinguished.",
      world="PG", start="the west crossing", people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      player="I find somewhere quiet and sit down.",
      outcomes=[{"intent_id": "i1", "op": "narrate_only", "status": "refused",
                 "tell": "No somewhere quiet is here.", "effects": []}],
      claims=[C("harm", opt=True, who="c4", how=["dead", "down", "hurt"])],
      may_alarm=["harm"]),
    B("ho-at-the-gate", "town:5 (held out)",
      "The air of the smithy's district fades, replaced by the salt-tang of the docks and "
      "the heavy, humid press of the gate's outer perimeter. You pass the merchant's row. "
      "Now, you stand at the gate. The massive timbered archway looms overhead, its "
      "underside scarred by the passage of heavy wagons.",
      world="PG", start="the market", end="the gate", people=(KESST,),
      player="I leave the shop and walk out towards the gate.",
      outcomes=[{"intent_id": "i1", "op": "travel", "status": "resolved",
                 "tell": "You are at the gate now.",
                 "effects": [{"kind": "biome", "place": "p~urban:the-gate",
                              "was_place": "p~urban:the-market"}]}],
      claims=[C("move", place="the gate")]),
    B("ho-grassland", "town:7 (held out)",
      "The sudden shift in the ground is a physical jolt; the cobblestones and the heavy, "
      "oppressive atmosphere of the city gates fall away, replaced by the wide, open sweep "
      "of the grassland. You are at the approach now, where the city's shadow finally "
      "yields to the vastness of the plains.",
      world="PG", start="the gate", end="the approach", people=(KESST,),
      player="I walk out into the grassland beyond the wall.",
      outcomes=[{"intent_id": "i1", "op": "travel", "status": "resolved",
                 "tell": "You are at the approach now.",
                 "effects": [{"kind": "biome", "place": "p~plains:the-approach",
                              "was_place": "p~urban:the-gate"}]}],
      claims=[C("move", place="the approach")]),
    B("ho-squabble-at-the-gate", "town:15 (held out)",
      "You leave the heat of the smithy behind and move into the bustle of the market, where "
      "the air is thick with the scent of spices and the calls of vendors. The crowd thins "
      "as you reach the transition to the gate, and the open space of the entryway forces a "
      "sudden halt. In the center of the thoroughfare, two men are grappling.",
      world="PG", start="the market", end="the gate", went_by=("the market",),
      people=(KESST,),
      player="I leave the shop and walk out towards the gate.",
      outcomes=[{"intent_id": "i1", "op": "travel", "status": "resolved",
                 "tell": "The way there ran through the market. You are at the gate now.",
                 "effects": [{"kind": "biome", "place": "p~urban:the-gate",
                              "was_place": "p~urban:the-market", "went_by": ["the market"]}]}],
      claims=[C("move", opt=True, place=["the gate", "the market"])]),
    # --- after the defeat (2026-10-09, before the fix; docs/narrator-after-defeat.md) ---
    B("defeat-lunges", "defeat:before-a-1",
      "The raider, his jaw bruised and swelling from your blow, ignores the pain and lunges "
      "again, his rapier whistling through the air toward the edge of the wagon's frame. "
      "Vyraxys is a whirlwind of motion on the box, shouting orders that are half-lost to "
      "the wind. The second raider is a blur of motion further down the line, and the sound "
      "of steel meeting wood rings out like a hammer on an anvil. The raider in front of you "
      "lunges again, his blade aimed not at your chest, but at the axle of the wagon.",
      world="XY", start="the road to Kalixiri", people=XY_PEOPLE, clock=780,
      player="I take no action.",
      claims=[C("shown", who="c4"), C("shown", who="c5"),
              C("shown", opt=True, who="c1"),
              C("harm", opt=True, who="c4", how="hurt")],
      alarms=["absent"]),
    B("defeat-buckler", "defeat:before-a-4",
      "The raider is close now, his shadow falling over you as he lunges with the rapier. "
      "You throw your weight into a desperate parry, the blade clanging against your "
      "buckler, the vibration numbing your arm. Vyraxys shouts a command, and the horses "
      "rear, their heavy hooves churning the dirt into a choking cloud. The second raider is "
      "visible now, a blur of motion as he leaps from the dunes toward the lead wagon.",
      world="XY", start="the road to Kalixiri", people=XY_PEOPLE, clock=780,
      player="I take no action.",
      claims=[C("shown", who="c4"), C("shown", who="c5"),
              C("shown", opt=True, who="c1"),
              C("arrived", opt=True, who="c5")],
      alarms=["absent"]),
    B("defeat-replayed", "defeat:before-a-2",
      "The raider's blade is a blur of motion, and you feel the steel bite deep into your "
      "side, carving through the leather of your doublet and the flesh beneath. You throw "
      "your fist in a desperate reflex; your knuckles slam into the raider's jaw with a "
      "sickening crunch. He grunts, his head snapping back slightly, but the impact doesn't "
      "break his grip or his stride. The raider is closing the distance, his rapier held low "
      "and ready, his eyes locked on yours.",
      world="XY", start="the road to Kalixiri", people=XY_PEOPLE, clock=780,
      player="I take no action.",
      claims=[C("shown", who="c4"), C("harm", who="pc", how="hurt"),
              C("harm", opt=True, who="c4", how="hurt")],
      alarms=["absent"]),
    B("defeat-backed-away", "defeat:before-a-3",
      "Vyraxys is still on the box, his face tight with the strain of the defense, his voice "
      "hoarse from shouting. The raider who struck you has backed away into the haze of the "
      "dust, and the second raider is nowhere to be seen, likely having escaped into the "
      "scrub with the stolen coin.",
      world="XY", start="the road to Kalixiri", people=XY_PEOPLE, clock=780,
      player="I take no action.",
      claims=[C("shown", opt=True, who="c4"), C("shown", opt=True, who="c1"),
              C("left", opt=True, who=["c4", "c5"])],
      # Backing away into the dust an hour after he left is him here, just; saying so is
      # defensible, not required.
      may_alarm=["absent"]),
    B("defeat-gone", "defeat:after-a-4",
      "You are slumped against the wooden frame of the second wagon, your breath coming in "
      "shallow, ragged hitches. Vyraxys is atop the lead wagon, his hands raw from gripping "
      "the reins, watching the horizon where the raiders vanished. He looks down at you, his "
      "expression a mix of grim relief and frustration. 'We'll find those bastards "
      "eventually; they can't have taken your coin and gotten away with it.'",
      world="XY", start="the road to Kalixiri", people=XY_PEOPLE, clock=780,
      player="I take no action.",
      claims=[C("harm", opt=True, who="pc", how="hurt"), C("shown", opt=True, who="c1")]),
    # --- somebody the engine keeps here, written gone (2026-10-09, the owner's report: "I
    # was told it left by the narration … but it stayed in the scene") ---------------------
    B("gone-while-you-slept", "sammy:rest draft",
      "You wake on the hard ground, the taste of dust and dry earth still in your mouth. The "
      "air of the morning is sharp and thin, smelling of mineral and old stone. The "
      "Aelzeldra is gone. There is no sign of the beast, no scrap of fur or iron left "
      "behind; only the long, jagged scar of the vein you sought remains, cold and silent in "
      "the dawn light. You are alone on the ridge as the first light of day touches the "
      "rolling hills.",
      world="RG", start="the ridgelines", people=(RG_SAMMY, RG_HOLDER), clock=36360,
      player="i lay on the ground and rest watching the aelzeldra", outcomes=[RG_REST],
      claims=[C("left", who="c28"), C("left", opt=True, who="c28"),
              C("hour", opt=True, part=["dawn", "morning"]),
              C("hour", opt=True, part=["dawn", "morning"]),
              C("hour", opt=True, part=["dawn", "morning"])],
      alarms=["presence"]),
    B("out-of-sight", "sammy:rest live (the fixed branch, own server)",
      "Somewhere in the distance, the low, rhythmic rumble of the Aelzeldra's breathing has "
      "faded into the morning haze, and the beast is no longer within your immediate sight. "
      "The sun is a pale, rising coin on the horizon, casting long shadows across the rocky "
      "ground. You are still here, still alive, and the first light is your only companion.",
      world="RG", start="the ridgelines", people=(RG_SAMMY, RG_HOLDER), clock=36360,
      player="i lay on the ground and rest watching the aelzeldra", outcomes=[RG_REST],
      # Out of sight is not quite gone (the engine holds it "far"): reading it as a
      # departure, and alarming, are both defensible; neither is required.
      claims=[C("left", opt=True, who="c28"),
              C("hour", opt=True, part=["dawn", "morning"]),
              C("hour", opt=True, part=["dawn", "morning"]),
              C("hour", opt=True, part=["dawn", "morning"])],
      may_alarm=["presence"]),
    B("still-there-at-dawn", "sammy:rest replay",
      "You wake as the first gray light of morning filters through the haze, the air tasting "
      "of dust and ancient stone. The Aelzeldra is still there, a silhouette of iron against "
      "the waking world, its presence a constant, looming weight.",
      world="RG", start="the ridgelines", people=(RG_SAMMY, RG_HOLDER), clock=36360,
      player="i lay on the ground and rest watching the aelzeldra", outcomes=[RG_REST],
      claims=[C("hour", opt=True, part=["dawn", "morning"])]),
    B("has-not-moved", "sammy:rest replay",
      "A few feet away, the Aelzeldra remains a silent, looming shadow against the morning "
      "light. It has not moved in the time you were unconscious, though it seems to have "
      "settled deeper into its stance, its presence a constant, oppressive weight in the air.",
      world="RG", start="the ridgelines", people=(RG_SAMMY, RG_HOLDER), clock=36360,
      player="i lay on the ground and rest watching the aelzeldra", outcomes=[RG_REST],
      claims=[C("hour", opt=True, part=["dawn", "morning"])]),
    # --- the body's conditions (2026-10-16, the owner's wife's market brawl on 0.2.19) ----
    # The report's beats, paraphrased short (the save is never committed): across three
    # beats a woman's hands reached for the player's throat, dug into it, and tightened
    # round it, and the engine grappled nobody. Beside them, the true holds and falls the
    # engine DID make, and the shapes a reader must not take for a condition.
    *[B(i, s, t, start="the market", world="PG", fight=True, clock=600,
        # A grapple is both bodies' (CRB p.199: "both you and the target gain the
        # grappled condition"); a fall is only hers.
        people=(["pc", "Kesst Vayr", "", True, "",
                 h4 if "grappled" in (h4 or ()) else ()],
                ["c4", "woman with the braid", "commoner", False, "", h4 or ()]),
        outcomes=o, claims=c, alarms=a, may_alarm=m)
      for i, s, t, o, c, a, m, h4 in (
        ("cond-grab-attempt", "report:10 (paraphrased)",
         "The thrown clump of hair passes her cheek. She recoils, her eyes narrowing, and "
         "lunges at you, her hands reaching to grab you by the throat.",
         [FB_MISS], [], [], [], None),
        ("cond-fingers-dig", "report:13 (paraphrased)",
         "Your dagger skids past her hip and clatters against a clay pot. She is inches "
         "from you, her fingers digging into your throat, her face twisted in a snarl.",
         [FB_MISS], [C("condition", who="pc", condition="grappled"),
                     C("harm", opt=True, who="pc", how="hurt")],
         ["condition"], ["harm"], None),
        ("cond-grip-tightens", "report:17 (paraphrased)",
         "Her fingers tighten around your throat as she leans in close. Her grip is meant "
         "to crush the wind out of you.",
         [FB_MISS], [C("condition", who="pc", condition="grappled"),
                     C("condition", opt=True, who="pc", condition="grappled"),
                     C("harm", opt=True, who="pc", how="hurt")],
         ["condition"], ["harm"], None),
        ("cond-aim-off-feet", "report:npc-45 draft (paraphrased)",
         "She eyes you coldly. She swings her club at you, aiming to knock you off your "
         "feet before you can move.",
         [], [], [], [], None),
        ("cond-held-true", "synthetic",
         "She hooks an arm round your neck and drags you into a crushing hold. You strain "
         "against her, but her grip does not give.",
         [FB_GRAPPLE], [C("condition", who="pc", condition="grappled"),
                        C("condition", opt=True, who="c4", condition="grappled"),
                        C("harm", opt=True, who="pc", how="hurt")], [], [], ("grappled",)),
        ("cond-trip-true", "synthetic",
         "Your heel hooks behind her ankle and she lands flat on her back in the dirt.",
         [FB_TRIP], [C("condition", who="c4", condition="prone"),
                     C("harm", opt=True, who="c4", how="hurt")], [], [], ("prone",)),
        ("cond-sprawl-invented", "synthetic",
         "Your fist cracks into her jaw and sends her sprawling across the stones.",
         [FB_HIT], [C("harm", who="c4", how="hurt"),
                    C("condition", who="c4", condition="prone")], ["condition"], [], None),
        ("cond-stunned-invented", "synthetic",
         "The pommel catches her temple. She staggers back, momentarily stunned.",
         [FB_HIT], [C("harm", who="c4", how="hurt"),
                    C("condition", who="c4", condition=["stunned", "dazed"])],
         ["condition"], [], None),
        ("cond-stunned-silence", "synthetic",
         "Your swing goes wide of her shoulder, and a stunned silence falls over the "
         "watching crowd.",
         [FB_MISS], [], [], [], None),
      )],
    # Held out: real beats of the grapple fights in the recordings (tests/replay
    # *-fight-bodies-*), labelled before any run. The engine held both men grappled and
    # nobody pinned: "pinned" for a grapple is the narrator's word and arguably the
    # rules' overclaim, so either answer is accepted and an alarm is defensible.
    B("ho-pinned-in-a-grapple", "fight-bodies-plain:6 npc (held out)",
      "Pinned and struggling against your grip, the man with a thick grunts with effort, "
      "trying to wrench his arm free to reach for something closer.",
      world="PG", start="the market", fight=True,
      people=(["pc", "Kesst Vayr", "", True, "", ("grappled",)],
              ["c3", "man with a thick", "commoner", False, "", ("grappled",)]),
      outcomes=[{"intent_id": "n1", "op": "attack", "status": "resolved", "effects": [],
                 "tell": "man with a thick's attack misses Kesst Vayr (13 against AC 13 "
                         "with cover)."}],
      claims=[C("condition", opt=True, who="c3", condition=["grappled", "pinned"])],
      may_alarm=["condition"]),
    B("ho-pinioned-strikes", "fight-bodies:7 npc (held out)",
      "Pinioned and struggling against your grip, Borin Lyraxys spits a mouthful of blood "
      "and lashes out with a desperate, short-range strike, trying to break your hold.",
      world="PG", start="the market", fight=True,
      people=(["pc", "Kesst Vayr", "", True, "", ("grappled",)],
              ["c2", "Borin Lyraxys", "human", False, "", ("grappled",)]),
      outcomes=[{"intent_id": "n1", "op": "attack", "status": "resolved", "effects": [],
                 "tell": "Borin Lyraxys's attack misses Kesst Vayr (12 against AC 13 with "
                         "cover)."}],
      claims=[C("condition", opt=True, who="c2", condition=["grappled", "pinned"]),
              C("harm", opt=True, who="c2", how="hurt")],
      may_alarm=["condition"]),
    B("ho-grip-to-pin", "fight:8 npc (held out)",
      "The commoner slams into you with desperate force, the blow heavy and jarring as "
      "they aim to pin your arms. Their grip is frantic, intended to pin you against the "
      "ground and stifle your movements.",
      world="PG", start="the west crossing", fight=True,
      people=(KESST, PG_C2, PG_C3, PG_LEATHER, PG_DESP),
      outcomes=[{"intent_id": "n1", "op": "attack", "status": "resolved",
                 "tell": "Commoner hits Kesst Vayr for 2 bludgeoning.",
                 "effects": [{"ref": "pc", "kind": "damage", "amount": 2}]}],
      claims=[C("harm", who="pc", how="hurt"),
              C("condition", opt=True, who="pc", condition=["grappled", "pinned"])],
      may_alarm=["condition"]),
    # --- the kind of place (2026-10-16): beats labelled with `setting`, scored for the
    # setting claims; every other beat is scored for setting ALARMS only. The report's
    # market fight (0.2.19, free narrator) set a blow on "the wooden planks of the deck";
    # its pot and crate are scenery and set nothing wrong.
    *[B(i, src, text, world="PG", start=at, fight=fight, people=(KESST, FB_WOMAN),
        outcomes=outs, claims=claims, alarms=alarms, may_alarm=may)
      | {"setting": True}
      for i, src, at, fight, text, outs, claims, alarms, may in (
        ("set-deck-in-market", "report:fight (paraphrased)", "the market", True,
         "The woman with the braid swings the heavy club two-handed. The heavy weapon "
         "whistles through the air past your ear, thudding uselessly into the wooden planks "
         "of the deck. She drags it free with a grunt, her eyes never leaving yours.",
         [FB_MISS], [C("setting", kind=_SH)], ["setting"], []),
        ("set-timber-stall", "synthetic", "the market", True,
         "Your dagger skids off her guard and bites into the timber post of a fishmonger's "
         "stall. Behind her the awnings sway, and the crowd has drawn back to the edges of "
         "the square.",
         [FB_MISS], [C("setting", kind=_ST), C("setting", opt=True, kind=_ST)], [], []),
        ("set-pot-shatters", "report:fight (paraphrased)", "the market", True,
         "Your dagger skids past her hip and clatters against a clay pot on the nearest "
         "stall; the pot shatters into shards that spray outward across the cobbles.",
         [FB_MISS], [C("setting", opt=True, kind=_ST)], [], []),
        ("set-crate-of-nails", "report:fight (paraphrased)", "the market", True,
         "To your left, a heavy wooden crate sits partially overturned, its contents of "
         "iron nails spilled across the cobbles. The woman circles to your right.",
         [], [C("setting", opt=True, kind=_ST)], [], []),
        ("set-tavern-across", "synthetic", "the market", False,
         "Across the square, the tavern door bangs open and two men stagger out into the "
         "lamplight. The stalls around you are shuttered for the night.",
         [], [C("setting", opt=True, kind=_ST),
              C("arrived", opt=True, who="someone not listed"),
              C("hour", opt=True, part="night")], [], []),
        ("set-ship-in-speech", "synthetic", "the market", False,
         "'We sail at dawn,' she says, 'and the deck of my ship is no place for a fool like "
         "you.' She turns back to her stall and starts stacking crates.",
         [], [C("setting", opt=True, kind=_ST)], [], []),
        ("set-forest-in-the-market", "synthetic", "the market", True,
         "Branches whip at your face as you push on through the undergrowth after her, "
         "roots snagging at your boots.",
         [], [C("setting", kind=_CO), C("move", opt=True, place="somewhere not listed")],
         ["setting"], ["move"]),
      )],
    B("set-taproom-at-the-market", "talk:0 draft", world="ZH",
      text=("Behind him, the tavern patrons have stopped their drinking; the clatter of mugs "
            "has died away. The air in the room feels thick. The man on the stool blinks, his "
            "eyes darting to the door, then to the man at the bar, and finally back to you. "
            "The stalls stand dark around you."),
      start="the market", people=(KESST, COAT), clock=1200,
      claims=[C("setting", kind=[_TV, _IN]), C("setting", opt=True, kind=[_TV, _IN]),
              C("setting", opt=True, kind=[_TV, _IN]), C("setting", opt=True, kind=_ST)],
      alarms=["setting"]) | {"setting": True},
    B("set-leans-on-the-bar", "talk:4 draft", world="ZH",
      text=("He leans back against the bar, the wood groaning under his weight. He doesn't "
            "move toward you, but the heavy atmosphere of the tavern seems to press in on the "
            "two of you."),
      start="the market", people=(KESST, COAT), clock=1200,
      claims=[C("setting", kind=[_TV, _IN]), C("setting", opt=True, kind=[_TV, _IN])],
      alarms=["setting"]) | {"setting": True},
    B("set-smithy-rafters", "synthetic", world="ZH",
      text=("Smoke curls up into the blackened rafters, and the anvil rings under the smith's "
            "hammer. Korvu does not look up from the work."),
      start="the smithy", people=(KESST, SMITH), clock=600,
      claims=[C("setting", kind=_IN)]) | {"setting": True},
    B("set-docks-planks", "synthetic", world="ZH",
      text=("Her boots drum on the planks of the jetty as she backs toward the moored boats, "
            "and gulls scatter off the pilings."),
      start="the docks", people=(KESST, FB_WOMAN), clock=600,
      claims=[C("setting", opt=True, kind=[_ST, _SH])]) | {"setting": True},
    B("set-tunnel-on-the-road", "synthetic", world="XY",
      text=("Water drips from the low stone ceiling of the tunnel, and the torchlight "
            "shivers on the wet walls. The drover mutters a prayer behind you."),
      start="the road to Kalixiri", people=(XY_TAM, XY_DROVER), clock=600,
      claims=[C("setting", kind=[_UN, _IN]), C("setting", opt=True, kind=[_UN, _IN])],
      alarms=["setting"]) | {"setting": True},
    # --- what the player's blows were struck with (2026-10-17), labelled before any run.
    # The live check of 2026-10-16: the shard refused, an unarmed strike rolled, and "The
    # shard bites deep into the soft tissue of his shoulder." Kesst carries a rapier and a
    # dagger (fixtures/pc-kesst.json); `blows` is what the engine struck with.
    *[B(i, src, text, world="PG", start="the market", fight=True, people=(KESST, FB_WOMAN),
        outcomes=[FB_HIT if hit else FB_MISS],
        # The blow's wound and a thrown thing on the floor are other categories' and are
        # not what these rows label: either answer is accepted.
        claims=[*claims, *[C("harm", opt=True, who=["c4", "pc", "someone not listed"],
                             how=["hurt", "down"])] * 2,
                C("hands", opt=True, item="something else", **{"from": "pc"},
                  to=["the floor", "nobody"])],
        alarms=alarms, may_alarm=[*may, "harm"])
      | {"blows": list(blows), "arms": list(dict.fromkeys(["rapier", "dagger", "unarmed strike", *blows]))}
      for i, src, text, hit, blows, claims, alarms, may in (
        ("sw-shard-live", "live:2026-10-16 (turn 3, verbatim)",
         "The shard is not there, but your reach is. You close the distance and lunge, "
         "your arm moving with the desperate weight of your fatigue. The shard bites deep "
         "into the soft tissue of his shoulder, and the man's body buckles as the air is "
         "driven from his lungs. He collapses into a heap of heavy wool and dull pain, his "
         "head hitting the stones with a muffled thud.",
         True, ("unarmed strike",), [C("weapon", weapon="something else")], ["weapon"], []),
        ("sw-shard-on-a-punch", "live:2026-10-16 (turn 3, cut short)",
         "You close the distance and lunge. The shard bites deep into the soft tissue of "
         "his shoulder, and the man's body buckles.",
         True, ("unarmed strike",), [C("weapon", weapon="something else")], ["weapon"], []),
        ("sw-fist-true", "synthetic",
         "Your fist cracks into her jaw and her head snaps back.",
         True, ("unarmed strike",), [C("weapon", weapon="unarmed strike")], [], []),
        ("sw-knee-true", "synthetic",
         "You drive your knee into her ribs, and she doubles over with a grunt.",
         True, ("unarmed strike",), [C("weapon", weapon="unarmed strike")], [], []),
        ("sw-rapier-true", "synthetic",
         "Your rapier darts in under her guard and opens a line across her forearm.",
         True, ("rapier",), [C("weapon", weapon="rapier")], [], []),
        ("sw-blade-vague", "synthetic",
         "Your blade flicks out and bites into her arm.",
         True, ("rapier",), [C("weapon", opt=True, weapon=["rapier", "not shown"])], [],
         ["weapon"]),
        ("sw-dagger-for-rapier", "synthetic",
         "You whip the dagger from your belt and plunge it into her side.",
         True, ("rapier",), [C("weapon", weapon="dagger")], ["weapon"], []),
        ("sw-rapier-miss-on-a-punch", "synthetic",
         "Your rapier hisses past her ear, a hand's breadth wide.",
         False, ("unarmed strike",), [C("weapon", weapon="rapier")], ["weapon"], []),
        ("sw-bottle-on-rapier", "synthetic",
         "You snatch a bottle off the stall and smash it over her head.",
         True, ("rapier",), [C("weapon", weapon="something else")], ["weapon"], []),
        ("sw-kettle-true", "live:2026-10-16 (turn 6, paraphrased)",
         "You hurl the heavy iron kettle; it clatters across the stones, missing her by a "
         "foot.",
         False, ("heavy iron kettle",), [C("weapon", weapon="heavy iron kettle")], [], []),
        ("sw-kettle-as-fist", "synthetic",
         "Your fist slams into her cheek and she reels.",
         True, ("heavy iron kettle",), [C("weapon", weapon="unarmed strike")], ["weapon"],
         []),
        ("sw-not-shown", "synthetic",
         "Your blow lands hard and she staggers back a step, gasping.",
         True, ("rapier",), [C("weapon", opt=True, weapon="not shown")], [], []),
        ("sw-her-blow-only", "synthetic",
         "She swings her cudgel and it cracks against your shoulder. You stagger.",
         False, ("unarmed strike",), [], [], []),
        ("sw-miss-with-dagger-true", "synthetic",
         "Your dagger skids past her hip and clatters against the cobbles.",
         False, ("dagger",), [C("weapon", weapon="dagger")], [], []),
        ("sw-shard-and-fist", "synthetic",
         "You swing at her and your knuckles graze her chin. Then you rake the jagged "
         "shard across her forearm.",
         True, ("unarmed strike",), [C("weapon", weapon="unarmed strike"),
                                     C("weapon", weapon="something else")], ["weapon"],
         []),
        ("sw-pommel-of-rapier", "synthetic",
         "You reverse your rapier and crack the pommel against her temple.",
         True, ("rapier",), [C("weapon", weapon="rapier")], [], []),
        ("sw-elbow-on-rapier", "synthetic",
         "You slam your elbow into her throat and she chokes.",
         True, ("rapier",), [C("weapon", weapon="unarmed strike")], ["weapon"], []),
        # Held out: written after the first run, before the demonstrations were changed,
        # and never run while changing them.
        ("sw-ho-stool-on-a-punch", "synthetic (held out)",
         "You step in close. The stool's leg cracks against his skull and he staggers.",
         True, ("unarmed strike",), [C("weapon", weapon="something else")], ["weapon"], []),
        ("sw-ho-headbutt-true", "synthetic (held out)",
         "You slam your forehead into the bridge of her nose.",
         True, ("unarmed strike",), [C("weapon", weapon="unarmed strike")], [], []),
        ("sw-ho-rapier-for-dagger", "synthetic (held out)",
         "You lunge, and the long, thin rapier blade skewers her sleeve to the post.",
         False, ("dagger",), [C("weapon", weapon="rapier")], ["weapon"], []),
        ("sw-ho-dagger-true", "synthetic (held out)",
         "You flip the dagger and drive it down toward her collarbone, but she wrenches "
         "aside.",
         False, ("dagger",), [C("weapon", weapon="dagger")], [], []),
        ("sw-ho-kick-on-rapier", "synthetic (held out)",
         "You kick her knee out from under her, and she drops to one leg.",
         True, ("rapier",), [C("weapon", weapon="unarmed strike")], ["weapon"], []),
        ("sw-ho-flat-of-rapier", "synthetic (held out)",
         "You slap the flat of your rapier across her cheek.",
         True, ("rapier",), [C("weapon", weapon="rapier")], [], []),
        ("sw-ho-rock-on-dagger", "synthetic (held out)",
         "You lunge. The rock in your fist slams into her temple.",
         True, ("dagger",), [C("weapon", weapon="something else")], ["weapon"], []),
        ("sw-ho-vague-true", "synthetic (held out)",
         "You strike, and she reels back clutching her arm.",
         True, ("rapier",), [C("weapon", opt=True, weapon="not shown")], [], []),
      )],
]


# --- 2026-10-16: an unlisted thing given by the floor, and the attempts -------------------
#
# Item 1 (gold "pay-*", "scenery-*", "no-trade-*"): on 0.2.20 the smith refused to pay —
# "says no and pays nothing: nothing changes hands" — and the page had him toss "a piece of
# coarse, stained leather … into the dirt between you. 'There's your pay.'" The read back
# heard it (`something else`, c4 -> the floor) and skipped it: only a hand-over INTO the
# player's hands was judged. The same beat's "the trade is finished" was cut as a sale
# nobody made, on a turn that had no trade at all.
#
# Item 2 (gold "att-*" and the held-out "ho-att-*"): a check or a save told the other way
# round. Outcomes carry `actor`, as `Engine._resolve_one` stamps it.
CARTER = ["c1", "the carter", "human"]
SMITH4 = ["c4", "the smith", "Korvu"]
GUARD1 = ["c1", "the guard by the mounting block", "Korvu"]
INNKEEP = ["c2", "the innkeeper", "human"]
GATEGUARD = ["c3", "the gate guard", "human"]
APPRENTICE = ["c5", "the tanner's apprentice", "Korvu"]


def _req(ref: str, kind: str, granted: bool, paid: bool = False, why: str = "") -> dict:
    """A Diplomacy request as `Engine._make_request` records it."""
    effects = [{"kind": "request", "ref": ref, "request": kind, "granted": granted}]
    if paid:
        effects.insert(0, {"ref": "pc", "kind": "give", "item": "coin", "count": 10,
                           "how": "paid", "from": ref, "to": "pc"})
    return {"intent_id": "i4", "op": "check", "status": "resolved", "actor": "pc",
            "verdict": "success" if granted else "failure",
            "rolls": [{"label": "Diplomacy check", "visibility": "player"}],
            "effects": effects, "because": why,
            "tell": "Kesst Vayr asks for " + ("payment for the work. " if kind == "payment"
                                               else "a favour. ")
                    + ("They agree." if granted else "They say no: nothing changes hands.")}


def _chk(label: str, ok: bool, why: str = "", op: str = "check", actor: str = "pc",
         effects=()) -> dict:
    return {"intent_id": "i1", "op": op, "status": "resolved", "actor": actor,
            "verdict": "success" if ok else "failure",
            "rolls": [{"label": label, "visibility": "player"}], "effects": list(effects),
            "because": why, "tell": f"{label}: {'made' if ok else 'missed'}."}


AID_FAILED = {"intent_id": "i3", "op": "check", "status": "resolved", "actor": "pc",
              "verdict": "success",
              "rolls": [{"label": "Strength check to help the smith", "visibility": "player"},
                        {"label": "the smith Strength check", "visibility": "hidden"}],
              "effects": [{"kind": "aid", "ref": "c4", "made": False, "bonus": 0,
                           "task_dc": 10, "done": True}],
              "because": "the player helps the smith with it",
              "tell": "Kesst Vayr misses the Strength check to help the smith by 1: no help. "
                      "the smith makes the Strength check by 4: the attempt succeeds."}
SAID_TO_SMITH = {"intent_id": "i2", "op": "say", "status": "resolved",
                 "effects": [{"kind": "said", "who": "pc", "to": "c4", "words": "Pay me."}],
                 "tell": "Kesst Vayr speaks to the smith."}

GOLD += [
    # --- item 1 ---------------------------------------------------------------------------
    B("pay-tossed-in-dirt", "integ:29 (0.2.20 live, the shipped beat, trade sentence as "
      "drafted)",
      "You reach out to assist him, but your limbs feel heavy and your muscles lack the "
      "strength to lighten the load; the smith's effort remains his alone as he heaves the "
      "cart, his thick muscles bunching under the soot-stained skin of his arms. The cart "
      "groans and settles into its frame with a heavy thud that vibrates through the "
      "ground. You demand fair pay for the work. He doesn't even seem to consider the "
      "request; he just shakes his head slowly. 'Work is work,' his voice grinds like stone "
      "against stone. He reaches into a pouch at his belt, but he doesn't pull out a coin; "
      "he pulls out a piece of coarse, stained leather. He tosses it into the dirt between "
      "you. 'There's your pay. Keep it if you want it, or throw it away.' He turns back to "
      "his work, the heavy hammer in his hand looking like an extension of his arm. You are "
      "still here, and the trade is finished.",
      start="the gate", world="PG", people=(KESST, GUARD1, SMITH4), clock=1809,
      player="I help the smith lift his cart, then ask him for fair pay for the work.",
      outcomes=[SAID_TO_SMITH, AID_FAILED, _req("c4", "payment", False,
                                                why="the player asks the smith for payment")],
      claims=[C("hands", item="something else", **{"from": "c4"},
                to=["the floor", "nobody", "pc"]),
              C("trade", opt=True, item="something else", seller=["pc", "c4"],
                buyer=["pc", "c4", "c1"], settled=[True, False]),
              C("attempt", attempt="a1", shown="fails"),
              C("attempt", attempt="a2", shown="succeeds"),
              C("attempt", opt=True, attempt="a3", shown=["fails", "succeeds"])],
      alarms=["hands"], may_alarm=["attempt"]),
    B("pay-coin-dropped", "synthetic (item 1)",
      "The carter shakes his head at the idea of paying. Then he fishes a copper bit out of "
      "his apron and drops it in the dust at your feet. 'For your trouble,' he mutters, and "
      "turns back to his mule.",
      start="the road to Kalixiri", world="XY", people=(XY_TAM, CARTER),
      outcomes=[_req("c1", "payment", False)],
      claims=[C("hands", item="something else", **{"from": "c1"},
                to=["the floor", "nobody", "pc"]),
              C("attempt", opt=True, attempt="a1", shown=["fails", "succeeds"])],
      alarms=["hands"], may_alarm=["attempt"]),
    B("pay-purse-on-counter", "synthetic (item 1)",
      "The innkeeper looks at you for a long moment. Then he takes a small purse from under "
      "the counter and sets it down on the wood in front of you, and nods at it.",
      start="the tavern", people=(KESST, INNKEEP),
      outcomes=[_req("c2", "payment", False)],
      claims=[C("hands", item="something else", **{"from": "c2"},
                to=["the floor", "nobody", "pc"]),
              C("attempt", attempt="a1", shown="succeeds")],
      alarms=["hands", "attempt"]),
    B("pay-held-out", "synthetic (item 1)",
      "Grudgingly, the smith digs two coppers out of his apron and holds them out to you "
      "on his open palm.",
      start="the gate", world="PG", people=(KESST, SMITH4),
      outcomes=[_req("c4", "payment", False)],
      claims=[C("hands", opt=True, item="something else", **{"from": "c4"},
                to=["pc", "the floor", "nobody"]),
              C("attempt", attempt="a1", shown="succeeds")],
      alarms=["attempt"], may_alarm=["hands"]),
    B("scenery-feather", "synthetic (item 1, scenery)",
      "A crow on the roof ridge drops a feather; it spirals down into the dirt beside you. "
      "The carter goes on brushing his mule and does not look up.",
      start="the road to Kalixiri", world="XY", people=(XY_TAM, CARTER),
      outcomes=[_req("c1", "payment", False)],
      claims=[C("hands", opt=True, item="something else", **{"from": "someone not listed"},
                to=["the floor", "nobody"]),
              C("attempt", opt=True, attempt="a1", shown=["fails"])]),
    B("scenery-hammer", "synthetic (item 1, scenery)",
      "The smith shakes his head and sets his hammer down on the anvil. 'No coin for help I "
      "never asked for,' he says, and wipes his hands on his apron.",
      start="the gate", world="PG", people=(KESST, SMITH4),
      outcomes=[_req("c4", "payment", False)],
      claims=[C("hands", opt=True, item="something else", **{"from": "c4"},
                to=["the floor", "nobody"]),
              C("attempt", attempt="a1", shown="fails")]),
    B("scenery-scrap-heap", "synthetic (item 1, scenery)",
      "The smith tosses a bent nail onto the scrap heap behind the anvil and reaches for "
      "another rod, saying nothing.",
      start="the gate", world="PG", people=(KESST, SMITH4),
      outcomes=[_req("c4", "payment", False)],
      claims=[C("hands", opt=True, item="something else", **{"from": "c4"},
                to=["the floor", "nobody"]),
              C("attempt", opt=True, attempt="a1", shown=["fails"])]),
    B("pay-paid-true", "synthetic (item 1, true)",
      "The tanner's apprentice grunts, counts three coppers out of his pouch and drops them "
      "into your palm. 'Fair's fair,' he says.",
      start="the gate", world="PG", people=(KESST, APPRENTICE),
      outcomes=[_req("c5", "payment", True, paid=True)],
      claims=[C("hands", opt=True, item=["something else", "coin"], **{"from": "c5"},
                to="pc"),
              C("attempt", attempt="a1", shown="succeeds")]),
    B("no-trade-finished", "synthetic (item 1, the false trade alarm)",
      "The tanner's apprentice shrugs and turns back to his rods. You are still here, and "
      "the trade is finished.",
      start="the gate", world="PG", people=(KESST, APPRENTICE),
      outcomes=[_req("c5", "payment", False)],
      claims=[C("trade", opt=True, item="something else", seller=["pc", "c5"],
                buyer=["pc", "c5"], settled=[True, False]),
              C("attempt", opt=True, attempt="a1", shown=["fails"])]),
    # --- item 2 ---------------------------------------------------------------------------
    B("att-lift-told-success", "synthetic (item 2)",
      "You set your shoulder under the tail of the cart and heave, and it rises out of the "
      "rut and rolls free onto the firm road.",
      start="the road to Kalixiri", world="XY", people=(XY_TAM, CARTER),
      outcomes=[_chk("Strength check", False, "the player lifts the cart out of the rut")],
      claims=[C("attempt", attempt="a1", shown="succeeds")], alarms=["attempt"]),
    B("att-lift-told-fail-true", "synthetic (item 2, true)",
      "You heave until your arms shake, but the wheel stays sunk in the rut and the cart "
      "does not move.",
      start="the road to Kalixiri", world="XY", people=(XY_TAM, CARTER),
      outcomes=[_chk("Strength check", False, "the player lifts the cart out of the rut")],
      claims=[C("attempt", attempt="a1", shown="fails")]),
    B("att-lift-success-told-fail", "synthetic (item 2)",
      "You strain against the cart with everything you have, but it will not budge an "
      "inch, and you step back, breathing hard.",
      start="the road to Kalixiri", world="XY", people=(XY_TAM, CARTER),
      outcomes=[_chk("Strength check", True, "the player lifts the cart out of the rut")],
      claims=[C("attempt", attempt="a1", shown="fails")], alarms=["attempt"]),
    B("att-lift-success-true", "synthetic (item 2, true)",
      "The cart lurches up out of the mud under your shoulder and rolls clear onto the "
      "road. The carter whistles.",
      start="the road to Kalixiri", world="XY", people=(XY_TAM, CARTER),
      outcomes=[_chk("Strength check", True, "the player lifts the cart out of the rut")],
      claims=[C("attempt", attempt="a1", shown="succeeds")]),
    B("att-favour-told-agreed", "synthetic (item 2)",
      "The innkeeper thinks it over, rubbing his jaw, then nods. 'All right. I'll fetch the "
      "key to the cellar for you myself.'",
      start="the tavern", people=(KESST, INNKEEP),
      outcomes=[_req("c2", "favour", False, why="the player asks for the cellar key")],
      claims=[C("attempt", attempt="a1", shown="succeeds")], alarms=["attempt"]),
    B("att-favour-refused-true", "synthetic (item 2, true)",
      "The innkeeper laughs without humour. 'The cellar key? Not for you, not tonight.'",
      start="the tavern", people=(KESST, INNKEEP),
      outcomes=[_req("c2", "favour", False, why="the player asks for the cellar key")],
      claims=[C("attempt", attempt="a1", shown="fails")]),
    B("att-sway-told-won", "synthetic (item 2)",
      "The gate guard's frown melts away. He laughs, claps you on the shoulder and waves "
      "you through like an old friend.",
      start="the gate", world="PG", people=(KESST, GATEGUARD),
      outcomes=[_chk("Diplomacy check", False, "the player tries to win the guard over")],
      claims=[C("attempt", attempt="a1", shown="succeeds")], alarms=["attempt"]),
    B("att-sway-failed-true", "synthetic (item 2, true)",
      "The gate guard hears you out with a face like a shut door, and does not move out of "
      "the gateway.",
      start="the gate", world="PG", people=(KESST, GATEGUARD),
      outcomes=[_chk("Diplomacy check", False, "the player tries to win the guard over")],
      claims=[C("attempt", attempt="a1", shown="fails")]),
    B("att-save-passed-told-failed", "synthetic (item 2)",
      "The venom floods your veins like ice water, and your legs buckle under you as the "
      "sickness takes hold.",
      start="the road to Kalixiri", world="XY", people=(XY_TAM, CARTER),
      outcomes=[_chk("Fortitude save", True, "the spider's venom", op="save")],
      claims=[C("attempt", attempt="a1", shown="fails"),
              C("harm", opt=True, who="pc", how=["hurt", "down"])],
      alarms=["attempt"], may_alarm=["harm"]),
    B("att-save-passed-true", "synthetic (item 2, true)",
      "Your arm burns where the fangs went in, but the sickness passes and your head "
      "clears.",
      start="the road to Kalixiri", world="XY", people=(XY_TAM, CARTER),
      outcomes=[_chk("Fortitude save", True, "the spider's venom", op="save")],
      claims=[C("attempt", attempt="a1", shown="succeeds"),
              C("harm", opt=True, who="pc", how="hurt")]),
    B("att-save-failed-told-passed", "synthetic (item 2)",
      "You shake off the creeping dread and stand your ground, steady as the stones under "
      "your feet.",
      start="the gate", world="PG", people=(KESST, GATEGUARD),
      outcomes=[_chk("Will save", False, "the wraith's dread", op="save")],
      claims=[C("attempt", attempt="a1", shown="succeeds")], alarms=["attempt"]),
    B("att-save-failed-true", "synthetic (item 2, true)",
      "Cold terror floods you, and your feet carry you back a step before you can stop "
      "them.",
      start="the gate", world="PG", people=(KESST, GATEGUARD),
      outcomes=[_chk("Will save", False, "the wraith's dread", op="save")],
      claims=[C("attempt", attempt="a1", shown="fails")]),
    B("att-climb-told-success", "synthetic (item 2)",
      "You find handholds in the old mortar and pull yourself up and over the top of the "
      "wall.",
      start="the gate", world="PG", people=(KESST, GATEGUARD),
      outcomes=[_chk("Climb check", False, "the player climbs the wall")],
      claims=[C("attempt", attempt="a1", shown="succeeds"),
              C("move", opt=True, place="somewhere not listed")],
      alarms=["attempt"], may_alarm=["move"]),
    B("att-stealth-told-success", "synthetic (item 2)",
      "You slip past the gate guard in the shadow of the arch; he never turns his head.",
      start="the gate", world="PG", people=(KESST, GATEGUARD),
      outcomes=[_chk("Stealth check", False, "the player sneaks past the guard")],
      claims=[C("attempt", attempt="a1", shown="succeeds")], alarms=["attempt"]),
    B("att-lock-unsure", "synthetic (item 2, not shown)",
      "You crouch at the door and set your picks to the lock. Somewhere down the street a "
      "dog barks twice and falls quiet.",
      start="the gate", world="PG", people=(KESST, GATEGUARD),
      outcomes=[_chk("Disable Device check", False, "the player picks the lock")],
      claims=[]),
    # --- item 2, held out: real beats from this session's live runs, cut to the sentences
    # the label needs, labelled before any run (scratch saves; `actor` added as the stamp
    # now records it).
    B("ho-att-intimidate", "bugs4/fightlive (held out)",
      "You tower over him, your voice a rasping command that cuts through the din of the "
      "shouting crowd. He hears you, and for a heartbeat, the twitching of his muscles "
      "halts as he stares up at you.",
      start="the tavern", people=(KESST, ["c2", "the one behind the bar", "human"]),
      outcomes=[_chk("Intimidate check", True, "the player tells him to stay down")],
      claims=[C("attempt", opt=True, attempt="a1", shown="succeeds")]),
    B("ho-att-tracks-found", "bugs4/live (held out)",
      "You move toward the knoll, your eyes scanning the trampled paths and the signs of "
      "passage left by the seasons and the travelers. A few yards from where the rider "
      "sits, the ground shows a clear, recent path—not from a person, but from a heavy "
      "cart, the wheels having carved deep, distinct ruts into the earth. The tracks lead "
      "straight toward the knoll.",
      start="the road to Kalixiri", world="XY", people=(XY_TAM, ["c2", "the rider", "human"]),
      outcomes=[dict(_chk("Kesst Vayr Survival (tracks)", False, op="track"),
                     effects=[{"ref": "pc", "kind": "tracks", "ground": "firm", "dc": 15,
                               "found": []}])],
      claims=[C("attempt", attempt="a1", shown="succeeds")], alarms=["attempt"]),
    B("ho-att-perform", "data/sammy (held out)",
      "You strike a final, definitive pose, one hand gripped tight on the hilt of your "
      "blade. Silence falls over the gate. Then the goblin with the scarred cheek lets out "
      "a wild, barking laugh that echoes off the archway. 'Not bad, outsider! Not bad at "
      "all!'",
      start="the gate", world="PG", people=(KESST, ["c2", "goblin with the scarred cheek",
                                                    "goblin"]),
      outcomes=[_chk("Perform check", True)],
      claims=[C("attempt", attempt="a1", shown="succeeds")]),
    B("ho-att-ore", "data-hinterland/sammy (held out)",
      "You spend the better part of the evening digging into the rocky soil, your hands "
      "becoming raw and stained with the grime of the earth. You manage to pull four chunks "
      "of copper ore from a vein, the metal heavy and dull in your pack.",
      start="the ridgelines", world="RG", people=(RG_SAMMY,),
      outcomes=[_chk("Survival check", True)],
      claims=[C("attempt", attempt="a1", shown="succeeds"),
              C("hour", opt=True, part="evening"),
              C("hands", opt=True, item="something else",
                **{"from": ["the floor", "nobody", "someone not listed"]}, to="pc")]),
    B("ho-att-aid-lift", "fos/live-data (held out)",
      "The smith grunts as you grip the edge of the cart. You lean your weight into it, and "
      "together you heave. The wheels groan, the axle groans, and then the cart gives with "
      "a heavy, shuddering lurch forward, settling into its proper place with a resounding "
      "thud of wood on stone. 'Stronger than you look, girl,' he grunts.",
      start="the gate", world="PG", people=(KESST, SMITH4),
      outcomes=[dict(AID_FAILED, effects=[{"kind": "aid", "ref": "c4", "made": True,
                                           "bonus": 2, "task_dc": 10, "done": True}])],
      claims=[C("attempt", attempt="a1", shown="succeeds"),
              C("attempt", attempt="a2", shown="succeeds")]),
    B("ho-att-wagon-fails", "fos/live-data (held out)",
      "You press your shoulder against the frame of the wagon, bracing your feet against "
      "the stone. The cart doesn't move; it only gives a hollow, grinding shudder that "
      "vibrates through your shoulder and up into your jaw.",
      start="the gate", world="PG", people=(KESST, SMITH4),
      outcomes=[_chk("Strength check", False)],
      claims=[C("attempt", attempt="a1", shown="fails")]),
    B("ho-att-old-tracks", "leather-final (held out)",
      "Instead of a clear trail, the earth offers only a mocking ambiguity. You realize "
      "with a jolt of unease that the tracks you were following are old—perhaps days, if "
      "not weeks, old.",
      start="the road to Kalixiri", world="XY", people=(XY_TAM,),
      outcomes=[_chk("Survival check", False)],
      claims=[C("attempt", attempt="a1", shown="fails")]),
    B("ho-att-bluff-doubted", "mindgate/sammy (held out)",
      "The lie hangs in the air, brittle as dry glass. 'You're a long way from home, then,' "
      "he says. 'If you weren't here, you'd have a lot of explaining to do about why "
      "you're currently standing in my district.' He waits, his eyes searching yours for "
      "the first crack in the story.",
      start="the gate", world="PG", people=(KESST, GATEGUARD),
      outcomes=[_chk("Bluff check", False, "the player claims to have never been here")],
      claims=[C("attempt", opt=True, attempt="a1", shown="fails")]),
    B("ho-att-paid-coin", "rr-live-data (held out)",
      "He pulls out a single, heavy silver coin and presses it into your palm. 'Fair "
      "enough,' he grunts. 'A day's labor for a day's weight.'",
      start="the gate", world="PG", people=(KESST, APPRENTICE),
      outcomes=[_req("c5", "payment", True, paid=True)],
      claims=[C("attempt", attempt="a1", shown="succeeds"),
              C("hands", opt=True, item=["something else", "coin"], **{"from": "c5"}, to="pc")]),
    B("ho-att-favour-granted", "rr-live-data (held out)",
      "He waits a beat, the rhythm of the hammers providing a heavy backbeat to his "
      "decision. 'I'll speak for you. If you're looking for a special commission, tell him "
      "you've been talking to me.' He gives a short nod of his head as if sealing a pact.",
      start="the gate", world="PG", people=(KESST, APPRENTICE),
      outcomes=[_req("c5", "favour", True)],
      claims=[C("attempt", attempt="a1", shown="succeeds")]),
    B("ho-att-apron-refused", "rr-live-data (held out)",
      "He lets out a short, dry breath and shakes his head. 'My apron is my skin,' he "
      "says. 'If I give it to you, I have nothing to protect me from the next blast.'",
      start="the gate", world="PG", people=(KESST, APPRENTICE),
      outcomes=[_req("c5", "favour", False)],
      claims=[C("attempt", attempt="a1", shown="fails")]),
    B("ho-att-apple-unseen", "spoken-theft (held out)",
      "You reach out and snag the apple from the fruit seller's basket. Their eyes are "
      "fixed on a scale, and they don't seem to notice the theft. The apple is heavy and "
      "cool in your hand.",
      start="the market", world="PG", people=(KESST, ["c2", "the fruit seller", "Korvu"]),
      outcomes=[_chk("Stealth check", True)],
      claims=[C("attempt", attempt="a1", shown="succeeds"),
              C("hands", opt=True, item="something else",
                **{"from": ["c2", "the floor", "someone not listed"]}, to="pc")]),
    B("ho-att-bandage", "spoken-theft (held out)",
      "You press the linen against the ragged tear in his side, and the pressure stops the "
      "welling of red. He doesn't move, but the frantic pulse in his neck steadies as the "
      "bleeding slows.",
      start="the market", world="PG", people=(KESST, ["c6", "the wounded porter", "Korvu",
                                                      False, "down"]),
      outcomes=[_chk("Heal check", True, effects=[{"kind": "condition", "ref": "c6",
                                                    "condition": "stable"}])],
      claims=[C("attempt", attempt="a1", shown="succeeds")]),
]
