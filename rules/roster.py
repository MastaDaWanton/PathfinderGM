"""Who would be here: the people a place holds, offered instead of four templates.

Reported 2026-09-19: *"Enemy/NPC spawns should not be random but based on the situation and
narration should match it."*

**There is no randomness in the spawn path at all** — no `random` import anywhere in it,
and `_free_spot_at` and `npcs.choose` are both explicitly deterministic. The complaint is
about *appropriateness*, and it is well founded: who appears was decided by three regexes
over the player's own sentence falling through to a literal `"thug"`, and the model was
offered exactly **four** hand-written templates while 7,133 stat blocks sat loaded and
reachable.

The situational material was written and unread:

- `places.STAFFED` — 25 rows of who is at each kind of place and what to search the
  bestiary with (`"the guardhouse": ("the watch", "the sergeant of the watch", ("guard",
  "watch", "sergeant"))`). Its only caller in the repo was a tooling script.
- `places.category_of` — seven kinds of place, read only to decide whether a keeper has a
  counter.
- `npcs.choose` with a CR band around the party.
- The world's own residents, and the live cards' people.

**Prior art.** Left 4 Dead's Director is the reference design: it places enemies "based
upon each player's current situation, status, skill, and location" with [structured
unpredictability](https://steamcommunity.com/sharedfiles/filedetails/?id=147309463), over a
set of **threat locations the map author placed**. This app already has both halves — the
places ARE the authored locations, and the cards and the settlement's own tension are the
intensity. What it lacked was the roster: a list of who belongs here, so the model picks
from something real instead of inventing.

One measured limit on ambition, from the shipped export: all 739 places carry
`terrain: "urban"` and all 256 cast entries carry the role `"Person"`, so neither terrain
nor cast role can discriminate. The place **slug** is the usable key — which is exactly
what `STAFFED` and `floorplan.BY_SPOT` are already keyed on.
"""
from __future__ import annotations

from . import npcs, places as places_mod


def _label(place_id: str) -> str:
    """The table's own name for a place, read off its id: "the market".

    `keepers.label_of` is the one parser for this — the slug was made by `places._slug`, so
    the way back is dashes to spaces and a storey suffix is not part of the name — and a
    second copy here would be the drift CLAUDE.md warns about. Imported inside the function
    because `keepers` imports `places`, and this module is below both.
    """
    from . import keepers

    return keepers.label_of(place_id)

# What a place holds when its own row says nothing: people, going about the day. Deliberately
# not "thug" — the old fallback made every unnamed arrival an assailant, which is how a
# market crowd turned into a brawl on the strength of one regex.
BYSTANDERS = ("commoner", "townsfolk", "laborer")
# Who turns up where the table has no row but the category says what kind of place it is.
# Seven categories, the same seven `places.category_of` answers with.
BY_CATEGORY = {
    "trade": ("merchant", "trader", "shopkeeper"),
    "craft": ("artisan", "craftsman", "laborer"),
    "civic": ("clerk", "official", "guard"),
    "faith": ("priest", "acolyte"),
    "law": ("guard", "watchman", "sergeant"),
    "drink": ("barkeep", "patron", "commoner"),
    "road": ("traveler", "drover", "commoner"),
}


def words_for(place_id: str, label: str = "") -> tuple[str, ...]:
    """The bestiary words for whoever belongs at this place, in order of specificity.

    The place's own `STAFFED` row first — it is the most specific thing anybody wrote down
    — then its category, then people going about their business.
    """
    name = " ".join(str(label or _label(place_id) or "").split()).lower()
    row = places_mod.STAFFED.get(name)
    if row:
        return tuple(row[2])
    cat = places_mod.category_of(name)
    if cat and cat in BY_CATEGORY:
        return BY_CATEGORY[cat]
    return BYSTANDERS


def who_would_be_here(scene, world=None, level: int = 1, limit: int = 6) -> list[dict]:
    """The roster for this place: who could plausibly be standing here, with a stat block.

    In order, because the order is the whole point — the more specific a source is about
    THIS place, the earlier it comes:

    1. **The place's own staffing** (`places.STAFFED`), which is somebody's written opinion
       about this kind of room.
    2. **The live cards' people**, because an open matter with a person attached is the most
       situational thing in the scene.
    3. **The settlement's residents**, who are the people the world says live here.
    4. **The category**, and then people going about the day.

    Each is resolved against the corpus by `npcs.choose` inside the CR band around the
    party, so nothing in the list is a creature the party cannot meaningfully meet. Returns
    `[{"who": …, "template": …, "why": …}]`, and `why` is what the brief prints — the model
    is being told who this place holds, not asked to guess.
    """
    out: list[dict] = []
    seen: set[str] = set()

    def add(who: str, why: str) -> None:
        who = " ".join(str(who or "").split())
        if not who or who.lower() in seen or len(out) >= limit:
            return
        got = npcs.choose(who, max(1, int(level or 1))) or {}
        template = str(got.get("id") or "guildhand")
        seen.add(who.lower())
        out.append({"who": who, "template": template, "why": why})

    at = str(getattr(scene, "at", "") or "")
    label = _label(at)
    row = places_mod.STAFFED.get(label)
    if row:
        # The row's own sentence is the honest `why`: "stallholders, and one who runs the
        # pitch" says more about the market than any word this module could compose.
        for word in row[2]:
            add(word, f"{label}: {row[0]}")

    # The people an open matter names. A card with somebody attached is the most
    # situational thing in the scene, which is what "based on the situation" means.
    for card in (getattr(scene, "cards", None) or []):
        if not isinstance(card, dict):
            continue
        for ref in (card.get("people") or []):
            actor = (getattr(scene, "actors", {}) or {}).get(str(ref))
            if actor is not None and not actor.is_pc:
                add(str(actor.name), f"named by the open matter {card.get('title') or ''}".strip())

    # And a couple of the world's own people, by NAME.
    #
    # By name and not by role word, which the first version got wrong and the measurement
    # caught: in the shipped Pangrella export a resident's `Role` fact is prose — "Innovative
    # developer and expert in magnetic shift adaptation", "High King's Representative" — and
    # handing that to `npcs.choose` returned a Drummond-and-Neville and an Initiate of Flame.
    # (Aurvantis writes clean roles: guildmaster, law-speaker, harbor-reeve. Neither export
    # can be relied on, so neither is.) A resident's stat block comes from the codex path
    # world characters already use, which remembers the block under their entity id so the
    # numbers are the same next session.
    #
    # Two of them, not six: they are a flavour of who might be met, and a roster swamped by
    # names is one the model cannot choose from. The place's own staffing comes first.
    if world is not None and getattr(scene, "location_id", None):
        try:
            residents = world.residents(scene.location_id)
        except Exception:
            residents = []
        town = getattr(world.get(scene.location_id), "name", "this town")
        for ent in residents[:2]:
            role = str(dict(getattr(ent, "facts", {}) or {}).get("Role") or "").strip()
            name = " ".join(str(getattr(ent, "name", "") or "").split())
            if not name or name.lower() in seen or len(out) >= limit:
                continue
            words = [w for w in role.lower().split() if len(w) > 3][:3]
            seen.add(name.lower())
            out.append({"who": name,
                        "template": npcs.block_for(str(getattr(ent, "id", "") or name),
                                                   words or list(BYSTANDERS),
                                                   max(1, int(level or 1)), name),
                        "why": f"lives in {town}" + (f" — {role}" if role else "")})

    for word in (BY_CATEGORY.get(places_mod.category_of(label)) or BYSTANDERS):
        add(word, f"{label or 'here'}: people going about the day")
    return out[:limit]


def brief_line(roster: list[dict]) -> str:
    """The roster as one line of fact for the brief, or "".

    Replaces the four hand-written templates the model was offered. It is a list of who is
    PLAUSIBLY here, not a claim that they are: the engine still has to be told to create
    anybody, and item 29's rule about whose word somebody exists on is untouched.
    """
    if not roster:
        return ""
    bits = "; ".join(f"{r['who']} ({r['template']})" for r in roster)
    return ("WHO THIS PLACE WOULD HOLD (fact — if somebody new appears, they are one of "
            f"these, and `spawn` takes the template in brackets): {bits}.")
