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


def places_of(beat) -> tuple[str, ...]:
    return {"VM": VM_PLACES, "PG": PG_PLACES, "XY": XY_PLACES}.get(beat["world"], ZH_PLACES)


def facts(beat):
    """The beat's engine side as `gm.beat_verify.Facts` — the shape `facts_from(ctx)`
    builds in the game, so the bench compares exactly what the game compares."""
    from gm import beat_verify as bv

    people = tuple(bv.Person(ref=p[0], name=p[1], what=p[2],
                             pc=bool(p[3]) if len(p) > 3 else False,
                             down=len(p) > 4 and p[4] in ("down", "dead"),
                             dead=len(p) > 4 and p[4] == "dead",
                             # "away": held elsewhere in town (`beat_reader.away_people`).
                             here=not (len(p) > 4 and p[4] == "away"))
                   for p in beat["people"])
    return bv.Facts(start=beat["start"], end=beat["end"], places=places_of(beat),
                    went_by=tuple(beat["went_by"]), pack=tuple(beat["pack"]),
                    props=tuple(beat["props"]), people=people, clock=beat["clock"],
                    outcomes=tuple(beat["outcomes"]), pc_ref="pc")


def by_id(beat_id: str) -> dict:
    return next(b for b in GOLD if b["id"] == beat_id)


def C(cat: str, opt: bool = False, **slots) -> dict:
    return {"cat": cat, **slots, **({"opt": True} if opt else {})}


def B(id: str, source: str, text: str, *, start: str, end: str = "", world: str = "ZH",
      people=(), pack=(), props=(), clock=None, outcomes=(), went_by=(), player: str = "",
      reading=None, claims=(), alarms=(), may_alarm=()) -> dict:
    return {"id": id, "source": source, "text": text, "start": start, "end": end or start,
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
      alarms=["move", "hands"], may_alarm=["hour"]),
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
      player="What is going on?"),
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
              C("harm", opt=True, who="c8", how="down")],
      alarms=["harm"]),
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
              C("harm", opt=True, who=["c2", "c3"], how="down")],
      alarms=["harm"]),
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
              C("harm", opt=True, who=["c2", "c3", "c4"], how=["down", "dead", "hurt"])],
      alarms=["harm"]),
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
      claims=[C("harm", who="c4", how="hurt"), C("harm", who="c4", how="down")]),
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
      claims=[C("harm", opt=True, who="c4", how=["down", "hurt"])]),
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
]
