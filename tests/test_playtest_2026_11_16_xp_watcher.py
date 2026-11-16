"""Story XP, the watcher and what leaks off-screen: the 2026-11-16 playtest (0.3.8).

* #16, #27, #47: 600 XP of story awards in four turns for doing nothing. The watcher
  "resolved" a dock-work card nobody worked, a fight card the fight had already paid, a
  faction's world card and a card it had opened for a walk already walked, at 200 XP each.
* #27: that award was titled "A fraternal organization of skilled salt harvesters and
  refiners, bound by", a faction description cut mid-sentence.
* #51: the watcher read the narrator's invented "hidden passage" and made it world memory.
* #23: a watcher fact moved a scheme's secret card the player had never heard of.
* #17: "Eren Vynsar is gone; what Eren Vynsar carried lies where the body fell: rapier,
  chain shirt" printed on the docks, of a body at the tavern known only from gossip.

Synthetic scenes; the save itself is private.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from rules import bestiary, cards
from rules.engine import Outcome
from rules.sheet import load_pc


@pytest.fixture
def campaign(tmp_path):
    from gm import watcher
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        watcher._reset()
        yield cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        cm._LIVE.clear()
        watcher._reset()


def _somebody(c, name="the harbourmaster"):
    return c.scene.add(bestiary.instantiate("commoner-level-1", scene=c.scene, name=name))


def _resolve(c, card):
    from gm import watcher

    now = cards.find(c.scene, card.id)
    watcher._apply_cards(c, {"changes": [{"id": card.id, "action": "resolve", "fact": "",
                                          "was": [now.stage, now.clock]}]})


def test_a_card_the_player_never_worked_pays_nothing_when_it_closes(campaign):
    """#16: "You gain 200 XP for moving a matter along: Dock Labor Inquiry", a card the
    watcher opened and closed with nothing the player did on it. CRB p.397: XP goes "to
    each PC that participated"."""
    c = campaign
    pc = c.scene.pc()
    who = _somebody(c)
    card = cards.open_card(c.scene, cards.Card(id="play-1", title="Dock Labor Inquiry",
                                               people=[who.ref], origin="watcher"), turn=1)
    xp = pc.xp
    _resolve(c, card)
    assert not cards.find(c.scene, card.id).live
    assert pc.xp == xp
    assert not [t for t in c.transcript if "XP" in str(t.get("text", ""))]


def test_a_card_the_players_own_deed_landed_on_pays_when_it_closes(campaign):
    """The other side of #16: the owner's "i should be receiving EXP for ... resolving
    situations" still holds for a situation the player had a hand in. A tell of the
    player's own act naming one of the card's people is their part in it; somebody
    else's act naming the same person is not."""
    c = campaign
    pc = c.scene.pc()
    who = _somebody(c)
    card = cards.open_card(c.scene, cards.Card(id="play-1", title="Dock Labor Inquiry",
                                               people=[who.ref], origin="watcher"), turn=1)
    theirs = Outcome(intent_id="i1", op="talk", actor=who.ref,
                     tell=f"{who.name} shouts at the dockhands to load faster.")
    cards.touch_from_outcomes(c.scene, [theirs], turn=2)
    assert not cards.took_part(cards.find(c.scene, card.id))
    mine = Outcome(intent_id="i1", op="talk", actor=pc.ref,
                   tell=f"{pc.name} speaks to {who.name}, to the effect that she wants work.")
    cards.touch_from_outcomes(c.scene, [mine], turn=3)
    assert cards.took_part(cards.find(c.scene, card.id))
    xp = pc.xp
    _resolve(c, card)
    assert pc.xp > xp
    # And the record survives a save.
    assert cards.Card.from_dict(cards.find(c.scene, card.id).as_dict()).worked == 3


def test_the_watcher_opens_no_card_with_nobody_on_it(campaign):
    """#47/#51: "The Path to the Main Channel" for a walk already walked and "The Hidden
    Passage" for a find nobody made, both with no people: a card nobody is on can only be
    moved, closed and paid on the watcher's own word."""
    from gm import watcher

    c = campaign
    before = len(cards.load(c.scene))
    watcher._apply_cards(c, {"changes": [], "new": {
        "title": "The Path to the Main Channel", "people": [],
        "facts": ["The traveler has reached the main channel."]}})
    assert len(cards.load(c.scene)) == before
    who = _somebody(c)
    watcher._apply_cards(c, {"changes": [], "new": {
        "title": "Dock Labor Inquiry", "people": [who.ref],
        "facts": ["The harbourmaster has work on the docks."]}})
    assert len(cards.load(c.scene)) == before + 1


def test_the_watcher_reads_tells_never_the_narration(campaign):
    """#51: the narrator wrote "Your methodical search reveals a hidden passage concealed
    within the masonry" over a search the engine found nothing on, and the watcher made
    the passage world memory. What the cards job is shown is the engine's tells."""
    from gm import watcher

    c = campaign
    c.transcript.append({"who": "player", "text": "I search the wall for a passage."})
    c.transcript.append({"who": "gm", "kind": "setup",
                         "text": "Your methodical search reveals a hidden passage "
                                 "concealed within the masonry."})
    c.turn_log.append({"kind": "turn", "outcomes": [
        {"op": "check", "status": "resolved", "actor": "pc",
         "tell": "Kesst makes the survival check by 4."},
        {"op": "travel", "status": "refused", "tell": "There is no road to the passage."}]})
    seen = watcher._what_happened(c)
    assert seen == ["Kesst makes the survival check by 4."]
    assert not [s for s in seen if "passage" in s]


def test_the_watcher_is_not_shown_a_secret_card(campaign):
    """#23: "The news of the death at the tavern begins to circulate among the local
    authorities" was laid on a scheme's secret plan card the player never heard of."""
    from gm import watcher

    c = campaign
    who = _somebody(c)
    cards.open_card(c.scene, cards.Card(id="scheme-x-plan-1", title="Somebody's plan",
                                        origin="scheme:x", secret=True,
                                        people=[who.ref]), turn=1)
    cards.open_card(c.scene, cards.Card(id="play-1", title="Dock Labor Inquiry",
                                        people=[who.ref], origin="watcher"), turn=1)
    turns = sum(1 for e in c.turn_log if e.get("kind") == "turn")
    watcher._LAST_LOOK[c.id] = turns - 10
    watcher._LAST_CARD_LOOK[c.id] = turns - 10
    jobs = [j for j in watcher._jobs_for(c) if j["job"] == "cards"]
    shown = {k["id"] for j in jobs for k in j["cards"]}
    assert "play-1" in shown and "scheme-x-plan-1" not in shown


def test_a_faction_card_is_titled_with_the_factions_name():
    """#27: World Bible titles a faction's card with its description's first seventy
    characters, cut mid-sentence; the award line printed the stump."""
    from world import loader

    world = loader.load_cached("fixtures/pangrella-campaign.json")
    titles = {k.id: k.title for k in cards.from_world(world)}
    assert titles["the-guild-of-saltmakers-sons"] == "The Guild of Saltmakers' Sons"
    assert not titles["the-guild-of-saltmakers-sons"].endswith("bound by")
    # A title that is its whole first sentence stays as written.
    assert titles["pangrella-strain"] == "Tensions between winged nobility and merchant castes"


def test_a_body_elsewhere_ages_out_without_a_word_to_the_player(campaign):
    """#17: a death at the tavern, heard only as gossip on the docks, printed "Eren Vynsar
    is gone; what Eren Vynsar carried lies where the body fell: rapier, chain shirt". The
    gear is still left where it fell; only the line is the player's to hear."""
    c = campaign
    engine = c.engine()
    away = bestiary.instantiate("commoner-level-1", scene=c.scene, name="Eren Vynsar")
    away.weapons = ["rapier"]
    c.scene.arrive(away, place_id=f"{c.scene.at}/the-tavern")
    away.die("test")
    here = c.scene.add(bestiary.instantiate("commoner-level-1", scene=c.scene, name="Bram"))
    here.weapons = ["club"]
    here.die("test")
    said = []
    for _ in range(4):
        said += engine.tidy_the_fallen()
    assert away.ref not in c.scene.people and here.ref not in c.scene.people
    assert not [s for s in said if "Eren Vynsar" in s]
    assert [s for s in said if "Bram" in s]
    assert any(p.get("owner") == away.ref for p in c.scene.props)
