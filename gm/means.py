"""By what means: a deed the character has no means to do is refused, whatever it is.

Reported 2026-10-05: "getting rid of the regex has brought back the ability to use psychic
powers and alter memories through narration." And then, the same day, the rule this
module is: *"if it allows those things there are an infinite number of things it will
allow. whatever you do must catch anything that is not within the players power to do not
just psychic and memory stuff"*.

**Where it leaked** (reproduced live on a copy of the owner's save, a level-1 asura
wizard at the smithy, 2026-10-05):
  * "I make the smith forget he saw me" — no pattern of `judgement._PSYCHIC` lists
    "forget", so nothing fired; the plan made it a Diplomacy check, and a roll was asked
    for a memory wipe.
  * "I erase the apprentice's memory of me" — the pattern fired, and stood down: the plan
    had guessed `cast charm-person`, and the door stands down for any cast. The engine
    then refused the cast (not prepared), the turn dropped it as "an op nobody asked
    for", and the narrator wrote "the flicker of recognition … simply dissolves".
  * Neither is a phrasing to add. A list of forbidden deeds has no end, which the owner
    said in as many words, and `_CLAIMED_FACULTY`'s own comment had already said about
    its adjective list.

**The shape every tradition gives** (sources in docs/means-gate.md): the deed is read
for HOW it is done, not WHAT it is. Ordinary means — body, voice, skill, the things
carried — are anybody's to TRY, and the dice or the other person write the result
(play-by-post etiquette on autohitting: "you write the attempt, they write the result";
Dogs in the Vineyard's "say yes or roll the dice"). A named power is a permission the
sheet must hold (Fate's extras are permissions; GAS's "an ability that was never granted
cannot be activated", already this engine's rule). Anything else has no fictional
positioning, and in Apocalypse World the move simply does not trigger.

**How**: the reader (gm/interpret.py) writes `means` on every action — an enum the
sampler holds it to — and the power's name as the player's own words. Code then asks the
SHEET, a closed vocabulary, whether anything held covers it (`held_power`): a spell the
caster can reach, a class or path ability, a feat, a racial trait, a thing carried. A
`power` or `beyond` deed with nothing held behind it is refused (`overreach`). Code reads
no English here: only whether a held name's words stand in the player's words.

Where it lands:
  * every deed of the turn refused → the turn IS the refusal, printed, and no model is
    asked (`GMAgent.plan_turn`, beside `acts_to_ops.refusal`);
  * some refused, some ordinary → the plan's guesses for the refused part are struck and
    the engine's own ability door prints the refusal as a tell (`strike`);
  * the prose writing a power nobody used anyway → gm/checks/power_unbacked.py.
"""
from __future__ import annotations

import re

ORDINARY, POWER, BEYOND = "ordinary", "power", "beyond"


def _words(text) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+(?:'[a-z]+)?",
                            str(text or "").lower().replace("’", "'")))


# Words that say nothing about WHICH power: "my", "the", "spell". Stripped from a power's
# name before it is held against the sheet, so "my sleep spell" is Sleep and "the ring"
# is a ring. Structure, not meaning — the same list a catalogue lookup strips.
_FILLER = frozenset({"my", "the", "a", "an", "his", "her", "their", "own", "spell",
                     "spells", "ability", "abilities", "power", "powers", "magic",
                     "cantrip", "trait", "feat", "item", "of", "skill", "skills"})


def _contains(hay: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    n = len(needle)
    return n > 0 and any(hay[i:i + n] == needle for i in range(len(hay) - n + 1))


def _held_names(pc) -> list[tuple[str, str]]:
    """(kind, name) for everything on the sheet that could be a power or carry one."""
    from rules import class_abilities, leveling

    out: list[tuple[str, str]] = []
    try:
        out += [("ability", n) for n in leveling.usable_names(pc)]
    except Exception:  # noqa: BLE001 — a sheet that cannot list is a sheet with none
        pass
    try:
        out += [("ability", n) for n in class_abilities.names(pc)]
    except Exception:  # noqa: BLE001
        pass
    out += [("feat", str(f)) for f in getattr(pc, "feats", None) or ()]
    try:
        from rules.sheet import _racial_traits

        out += [("trait", str(t.get("name") or "")) for t in _racial_traits(pc)]
    except Exception:  # noqa: BLE001
        pass
    for slot in (getattr(pc, "slots", None) or {}).values():
        out += [("item", str(x)) for x in (slot or ()) if x]
    out += [("item", str(w)) for w in getattr(pc, "weapons", None) or ()]
    for store in ("gear", "goods", "inventory"):
        out += [("item", str(k)) for k in (getattr(pc, store, None) or {})]
    for key, stock in (getattr(pc, "stock", None) or {}).items():
        out += [("item", str(getattr(stock, "name", "") or key)),
                ("item", str(getattr(stock, "base", "") or ""))]
    out += [("skill", s) for s in _skill_names()]
    return [(k, n) for k, n in out if _words(n)]


def _skill_names() -> list[str]:
    """Every skill of the rules, held by every character. Measured 2026-10-08 (the deeds
    lane, local model): "I use the Heal skill" was read `means: power, power: Heal`, no
    spell, ability, feat or item was called Heal, and the gate refused it as "no spell,
    ability or item by that name" — the turn printed "Kesst Vayr has no powers yet". A
    skill is not a permission the sheet has to grant: the Core Rulebook lets anyone try
    an untrained skill, and the trained-only ones are refused by the check itself, with
    the reason (`Engine._op_check`: "cannot attempt … untrained. Nothing is rolled."), so
    this gate never has to know which is which."""
    from rules.tables import SKILLS

    # Not Fly: the Core Rulebook's Fly skill is for "a creature with a fly speed", so the
    # skill backs no flight on its own — the wings or the spell are what the sheet must
    # hold, and "I fly up to the bell tower" still asks for them.
    return [s for s in SKILLS if s != "fly"]


def held_power(scene, words, *, named: bool = True) -> tuple[str, str]:
    """(kind, name) of what this character holds that the words name, or ("", "").

    A spell through the one spell finder (`interpret.spell_named`: the whole catalogue,
    word-bounded, longest first, then only what this caster can reach). Everything else by
    its name's words standing in the player's words — and, when the words ARE a power's
    name (`named`: the reading's `power` slot), the other way round too: "my ring" is the
    ring of protection they wear, "my wings" is their fly speed (wings); "the potion of
    flying" is not their potion of cure light wounds.

    Not `named` (a deed's own words, read for a power it never named): spells, abilities
    and feats only. A thing carried or a trait line is never found in a deed's words —
    "I turn the water into wine" names the water they carry and is no power of it; those
    go to `which_power`, which is shown the deed whole."""
    from . import interpret

    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    said = _words(words)
    if pc is None or not said:
        return "", ""
    if named and ({"skill", "skills"} & set(said)):
        # "the Heal skill" is the skill, whatever spell shares its name (a cleric's Heal).
        core = tuple(w for w in said if w not in _FILLER)
        for name in _skill_names():
            if core and _words(name) == core:
                return "skill", name
    spell = interpret.spell_named(scene, " ".join(said))
    if spell is not None:
        return "spell", str(getattr(spell, "name", "") or getattr(spell, "id", ""))
    core = tuple(w for w in said if w not in _FILLER)
    best: tuple[int, str, str] | None = None
    for kind, name in _held_names(pc):
        if not named and kind not in ("ability", "feat"):
            continue
        held = _words(name)
        held_core = tuple(w for w in held if w not in _FILLER) or held
        if _contains(said, held_core) or (named and core and _contains(held, core)):
            if best is None or len(held_core) > best[0]:
                best = (len(held_core), kind, name)
    if best is not None:
        return best[1], best[2]
    return "", ""


# --- the one question code cannot answer by name ---------------------------------------
#
# "I fly over the wall" is the owner's asura's own wings — "fly speed equal to base speed
# (wings)" is a line of her race — and a rogue's fantasy. No word of the deed is the
# trait's name, so a name lookup refuses the asura; a word-overlap rule would be a regex
# by another name. So the sheet's own list is put to a model as an ENUM, "none" included
# (the coordinator's "named from an enum built from the sheet's own lists, plus 'none of
# mine'"), asked only of a deed nothing held was found for by name. The answer can only
# be something the sheet holds, by construction; code then takes it as the power. The
# same shape as `interpret.confirm_sale`: one targeted question, demonstrated, the frame's
# other fields not asked again.
#
# And a second way out, measured: on the regex gate's own corpus (tests/
# test_psychic_powers.py, 40 ordinary lines) the reader called five of them `beyond` —
# "I bend the bars", "I charm her with a story", "I charm the room with my manner", "I go
# with my gut" — and read "I remember the road to the coast" as a bare claim. The old
# regex spared all 40. So the same question offers ANYONE: a deed any person could
# attempt with body, words, wits and memory. One call still, asked only where a refusal
# was about to land — CLAUDE.md's shape, a targeted second question on what was found.
ANYONE = "anyone could try this"

_WHICH_SYSTEM = (
    "A player in a role-playing game says their character does something. Below is "
    "EVERYTHING the character has: their abilities, feats, the traits of their kind, and "
    "what they carry. Answer which ONE of them lets the character do the deed. Answer \""
    + ANYONE + "\" when any ordinary person could attempt it with their body, words, "
    "wits or memory — strength, a story, a hunch, remembering, persuading. Answer "
    "\"none\" when it needs a power and nothing listed does it. Only a thing that really "
    "does the deed counts: a sword does not make anyone invisible, being stealthy is not "
    "vanishing, and a bonus to a skill is not magic.")

_WHICH_DEMOS = [
    (["longsword", "Power Attack", "darkvision 60 ft", "Bless", "rope"],
     "see in the pitch-dark cellar", "darkvision 60 ft"),
    (["longsword", "Power Attack", "darkvision 60 ft", "Bless", "rope"],
     "make the guard forget me", "none"),
    (["dagger", "Alertness", "climb speed equal to base speed", "+2 stealth"],
     "turn into a mist and drift under the door", "none"),
    (["dagger", "Alertness", "climb speed equal to base speed", "+2 stealth"],
     "wrench the rusted gate off its hinges", ANYONE),
    (["spear", "fly speed equal to base speed (wings)", "Iron Will"],
     "fly up to the bell tower", "fly speed equal to base speed (wings)"),
    (["spear", "fly speed equal to base speed (wings)", "Iron Will"],
     "win the fishwives over with a bawdy song", ANYONE),
    (["spear", "fly speed equal to base speed (wings)", "Iron Will"],
     "make the fishwives adore me with a look", "none"),
    # The pair the first run with ANYONE confused: a mind worked on by will alone (the
    # model gave a bare "charm", "dominate", "will him to obey" away as anybody's) against
    # the same mind worked on by presence, which anybody may try.
    (["dagger", "Alertness", "climb speed equal to base speed", "+2 stealth"],
     "put the notion in the boatman's head that I am his captain", "none"),
    (["dagger", "Alertness", "climb speed equal to base speed", "+2 stealth"],
     "stare the boatman down until he looks away", ANYONE),
]


def _which_ask(names: list[str], deed: str) -> str:
    listed = "\n".join(f"- {n}" for n in names)
    return f"THE CHARACTER HAS:\n{listed}\n\nTHE DEED: {deed}"


def which_messages(names: list[str], deed: str) -> list[dict]:
    import json

    out = [{"role": "system", "content": _WHICH_SYSTEM}]
    for held, said, answer in _WHICH_DEMOS:
        out.append({"role": "user", "content": _which_ask(held, said)})
        out.append({"role": "assistant", "content": json.dumps({"power": answer})})
    out.append({"role": "user", "content": _which_ask(names, deed)})
    return out


def which_power(scene, deed: str, *, chat=None, model: str = "", host: str = "",
                provider: str = "ollama", api_key: str = "") -> tuple[str, str]:
    """(kind, name) of the held thing a model says does `deed`; (ORDINARY, "") when it
    says anyone could try it; ("", "") for "none" or a failed call (refused: the safe
    direction, the player can name the power or say how they try)."""
    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    if pc is None:
        return "", ""
    # Spells are not offered. A spell has a name, the refusal lists it, and a spell stood
    # behind a deed it does not do is the very leak this module is for: a wizard's "make
    # the smith forget he saw me" answered "Charm Person" would cast a charm and leave the
    # forgetting to the prose. A spell the deed's words name was found by name already.
    # Nor the skills: every character has every one, so "anyone could try this" already
    # answers for them, and thirty-odd more names would drown the sheet's own.
    held = [h for h in dict.fromkeys(_held_names(pc)) if h[0] != "skill"]
    names = [n for n in dict.fromkeys(n for _k, n in held)
             if n not in (ANYONE, "none")][:60]
    if chat is None:
        from . import client

        chat = client.chat
    if not model:
        from play import modelcfg

        cfg = modelcfg.for_role("interpreter")
        if not cfg.get("model"):
            cfg = modelcfg.for_role("narrator")
        model, host = cfg["model"], cfg["host"]
        provider, api_key = cfg.get("provider", "ollama"), cfg.get("api_key", "")
    schema = {"type": "object",
              "properties": {"power": {"type": "string",
                                       "enum": [*names, ANYONE, "none"]}},
              "required": ["power"]}
    try:
        reply = chat(which_messages(names, deed), model, host, as_json=True, think=False,
                     temperature=0.0, num_predict=40, provider=provider, api_key=api_key,
                     schema=schema)
        got = str((reply.json() or {}).get("power") or "")
    except Exception:  # noqa: BLE001 — a failed question refuses; the player can name it
        return "", ""
    if got == ANYONE:
        return ORDINARY, ""
    for kind, name in held:
        if name == got:
            return kind, name
    return "", ""


def judge(frame: dict | None, scene, ask=None, claim_ask=None) -> list[dict]:
    """Every deed of the reading done or tried now by a `power` or `beyond` means, each
    the action with either `held` ([kind, name]: what on the sheet stands behind it) or
    `refused_name` (the player's own words for what they reached for).

    Only deeds done or tried now (`interpret.acting`): a plan, a wish or a question owes
    nothing. An `ordinary` deed is never judged here — its result is the dice's or the
    other person's, and a declared result is the reading's `claims`, which the brief
    already hands the planner as not so. A deed stands when the sheet holds what it names
    (the `power` slot), when its own words name a spell, ability or feat held (a wizard's
    "I put the guard to sleep" is her Sleep), or when `ask` — `which_power`, one enum
    question over the sheet's own list — names something held that does it. Nothing
    stands on nothing.

    `ask` is None in the test suite (no model), and a deed found by no name is refused:
    the safe direction, since the refusal lists what they can use."""
    from . import interpret

    if not isinstance(frame, dict) or frame.get("error") or frame.get("question"):
        return []
    if scene is None or not hasattr(scene, "pc") or scene.pc() is None:
        return []
    out = []
    # Nothing done at all, only a thing declared so: "I know exactly where the bandit camp
    # is", "I decide that the smith owes me fifty gold". The reader writes no deed for
    # these, only a claim (measured: 3 of the corpus's first-pass misses were exactly this
    # shape), and a claim is the planner's to treat as not so — which the narrator was then
    # free to make so. A sentence that only claims has no attempt in it for the dice to
    # decide, so it is refused as the other overreach is, naming what could be TRIED. In
    # the interpreter's 302 labelled lines from real play no LABEL is claim-only.
    #
    # Not put to `which_power`: tried, and "I decide that the smith owes me fifty gold"
    # came back "anyone could try this" — anybody can try to decide a thing, and the
    # question is not whether saying it makes it so. "I remember the road to the coast",
    # which the reader also read as a bare claim, is remembering — a deed, which the
    # reader is now shown (interpret._DEMOS).
    #
    # Nor is every bare claim a declaration: on the interpreter's 302 labelled lines from
    # real play the reader wrote three claim-only frames, and two were plans — "I plan to
    # rob the counting house tonight", "I mean to kill him if he comes back". So a bare
    # claim is asked one closed question first (`claim_kind`): a plan, the character's own
    # state or nature, or a thing declared true about the world. Only the last is refused.
    if not frame.get("actions") and frame.get("claims"):
        claim = str(frame["claims"][0])
        if claim_ask is not None and claim_ask(claim) != DECLARES:
            return []
        return [{"span": claim, "act": "claim", "means": "claim", "refused_name": claim}]
    for a in frame.get("actions") or []:
        if not isinstance(a, dict) or not interpret.acting(a):
            continue
        means = str(a.get("means") or ORDINARY)
        if means not in (POWER, BEYOND):
            continue
        power = str(a.get("power") or "").strip()
        span = str(a.get("span") or "").strip()
        kind, name = held_power(scene, power) if power else ("", "")
        if not kind:
            kind, name = held_power(scene, span, named=False)
        if not kind and ask is not None:
            kind, name = ask(scene, span or power)
            # A power NAMED that the sheet does not hold is never anybody's to try:
            # "I drink my potion of flying" came back "anyone could try this", and anyone
            # can drink — a potion they do not have.
            if kind == ORDINARY and means == POWER:
                kind = ""
            if kind == ORDINARY:
                # Anybody's to try: judged no further, the dice decide it.
                continue
        if kind:
            out.append({**a, "held": [kind, name]})
        else:
            out.append({**a, "refused_name": power or span})
    return out


def overreach(frame: dict | None, scene, ask=None, claim_ask=None) -> list[dict]:
    """The deeds of `judge` that nothing held stands behind."""
    return [j for j in judge(frame, scene, ask, claim_ask) if j.get("refused_name")]


# --- a bare claim, asked what it is ---------------------------------------------------
INTENDS, SELF, DECLARES = "a plan", "about myself", "declared true"
CLAIM_KINDS = (INTENDS, SELF, DECLARES)

_CLAIM_SYSTEM = (
    "A player in a role-playing game typed one line that does nothing; it only states "
    "something. Say which it is: \"" + INTENDS + "\" (what they mean or plan to do "
    "later), \"" + SELF + "\" (how their character feels, looks, or what they are like), "
    "or \"" + DECLARES + "\" (a fact about the world, other people, or what the "
    "character knows or can do, stated as if saying it made it so).")

_CLAIM_DEMOS = [
    ("I mean to be on the first boat out tomorrow.", INTENDS),
    ("I'm soaked through and miserable.", SELF),
    ("The harbourmaster has always been in my debt.", DECLARES),
    ("I already know which warehouse the smugglers use.", DECLARES),
]


def claim_kind(claim: str, *, chat=None, model: str = "", host: str = "",
               provider: str = "ollama", api_key: str = "") -> str:
    """One of `CLAIM_KINDS`; DECLARES when the call fails (refused: the safe direction —
    the refusal names what to try instead)."""
    import json

    if chat is None:
        from . import client

        chat = client.chat
    if not model:
        from play import modelcfg

        cfg = modelcfg.for_role("interpreter")
        if not cfg.get("model"):
            cfg = modelcfg.for_role("narrator")
        model, host = cfg["model"], cfg["host"]
        provider, api_key = cfg.get("provider", "ollama"), cfg.get("api_key", "")
    msgs = [{"role": "system", "content": _CLAIM_SYSTEM}]
    for said, kind in _CLAIM_DEMOS:
        msgs += [{"role": "user", "content": said},
                 {"role": "assistant", "content": json.dumps({"kind": kind})}]
    msgs.append({"role": "user", "content": str(claim)})
    schema = {"type": "object", "properties": {"kind": {"type": "string",
                                                        "enum": list(CLAIM_KINDS)}},
              "required": ["kind"]}
    try:
        reply = chat(msgs, model, host, as_json=True, think=False, temperature=0.0,
                     num_predict=20, provider=provider, api_key=api_key, schema=schema)
        got = str((reply.json() or {}).get("kind") or "")
    except Exception:  # noqa: BLE001
        return DECLARES
    return got if got in CLAIM_KINDS else DECLARES


# The op a held power's use is, for the plan's must-contain list: a spell used is a
# `cast` the engine resolves, an ability a `use_ability`, a thing carried a `use_item`.
# A trait or a feat is the character's own body or training and has no door of its own.
HELD_OPS = {"spell": "cast", "ability": "use_ability", "skill": "check"}


def backed_ops(judged: list[dict]) -> list[str]:
    """The ops the player's held powers owe the turn. Declared, so a refusal only the
    player can fix ("did not prepare Charm Person today") ends the turn in their hands
    rather than being dropped as the plan's invention — which is how the owner's wizard's
    memory wipe reached the narrator (`GMAgent._players_refusal`)."""
    return list(dict.fromkeys(HELD_OPS[j["held"][0]] for j in judged
                              if j.get("held") and j["held"][0] in HELD_OPS))


def all_refused(frame: dict | None, refused: list[dict]) -> bool:
    """Whether every deed the turn does now is refused — the turn is then the refusal."""
    from . import interpret

    acting = [a for a in (frame or {}).get("actions") or []
              if isinstance(a, dict) and interpret.acting(a)]
    return bool(refused) and len(refused) >= len(acting)


def can_use(pc) -> str:
    """What this character CAN reach for, for a refusal that names the fix (the engine's
    ability door does the same for abilities; a caster's spells are added here, because
    "They can use: nothing yet" told the owner's wizard she had nothing at all)."""
    from rules import casting, class_abilities, leveling

    parts = []
    try:
        abilities = list(dict.fromkeys(leveling.usable_names(pc) + class_abilities.names(pc)))
    except Exception:  # noqa: BLE001
        abilities = []
    if abilities:
        parts.append("abilities: " + ", ".join(abilities))
    try:
        if casting.is_caster(pc):
            # Highest level first: twenty cantrips listed first cut a wizard's Sleep off
            # the end of the line.
            by_level = casting.known_spells(pc, up_to=casting.highest_spell_level(pc))
            known = [sp.name for lvl in sorted(by_level, reverse=True)
                     for sp in by_level[lvl]]
            if known:
                parts.append("spells: " + ", ".join(known[:16])
                             + (", …" if len(known) > 16 else ""))
    except Exception:  # noqa: BLE001
        pass
    return "; ".join(parts)


def refusal_text(refused: list[dict], scene) -> str:
    """The printed refusal when the turn is nothing but deeds out of reach. Says what was
    reached for in the player's words, why, and what they could do instead — the
    validator style: name the fix, not the fault."""
    pc = scene.pc()
    who = str(getattr(pc, "name", "") or "You")
    what = "; ".join(f"“{r['refused_name']}”" for r in refused[:3])
    named = [r for r in refused if r.get("means") == POWER and r.get("power")]
    if all(r.get("means") == "claim" for r in refused):
        return (f"{what}: saying so does not make it so. {who} can try to find it out "
                f"or bring it about — ask around, search, recall what they know, talk "
                f"someone round — and the dice decide.")
    if named and len(named) == len(refused):
        why = (f"{who} has no spell, ability or item by that name, so it cannot be "
               f"used")
    else:
        why = (f"that is beyond what an ordinary person can do, and nothing {who} has — "
               f"no spell, ability, trait or item — does it")
    have = can_use(pc)
    fix = (f" {who} can use — {have}." if have else
           f" {who} has no powers yet.")
    return (f"{what}: {why}.{fix} Anything a person could try — talking someone round, "
            f"lying, threatening, bribing, sneaking, fighting — is still {who}'s to "
            f"attempt; say how, and the dice decide.")


# The ops a plan writes as its guess at what a refused deed does. Nothing that moves a
# number, a mind, a body or a creature survives a refusal: `refuse_unknown_ability`
# learned it — told to drop only the fight-makers, the next probe came back with
# `ability_damage con 1d4` and it landed.
_GUESS_OPS = frozenset({"condition", "compel", "spawn", "save", "summon", "introduce"})


def strike(raw_intents, judged: list[dict], frame: dict | None, scene) -> list:
    """The plan with every guess at a refused deed struck, and the engine's ability door
    asked for each in the player's own words — it prints "<who> has no ability called
    <X>. They can use: …" as a tell, which the narrator is fed and the claims scrubber
    holds the prose to.

    A cast, ability or item op stands only where an ordinary or held deed of the reading
    stands behind it: the leak this exists for was the plan's own `cast charm-person` for
    "I erase the apprentice's memory of me", which a regex door took as the player's
    power and stood down for."""
    from rules.intents import AMOUNT_OPS

    from . import interpret

    refused = [j for j in judged or () if j.get("refused_name")]
    if not refused or not isinstance(raw_intents, list):
        return raw_intents
    pc = scene.pc()
    backed: set[str] = {" ".join(_words(j["held"][1])) for j in judged if j.get("held")}
    attacks = uses = False
    refused_spans = {str(r.get("span") or "") for r in refused}
    for a in (frame or {}).get("actions") or []:
        if not isinstance(a, dict) or not interpret.acting(a):
            continue
        if str(a.get("span") or "") in refused_spans:
            continue
        if a.get("act") == "attack":
            attacks = True
        if a.get("act") in ("use", "consume"):
            uses = True
        for words in (a.get("power"), a.get("object"), a.get("span")):
            kind, name = (held_power(scene, words, named=words != a.get("span"))
                          if words else ("", ""))
            if kind:
                backed.add(" ".join(_words(name)))
    kept = []
    for r in raw_intents:
        if not isinstance(r, dict):
            continue
        op = str(r.get("op", "")).lower()
        if op in AMOUNT_OPS or op in _GUESS_OPS:
            continue
        if op == "attack" and not attacks:
            continue
        if op in ("cast", "use_ability"):
            params = r.get("params") or {}
            named = str(params.get("spell") or params.get("ability") or "")
            kind, name = held_power(scene, named.replace("-", " ")) if named else ("", "")
            if not kind or " ".join(_words(name)) not in backed:
                continue
        if op == "use_item" and not (backed or uses):
            continue
        kept.append(r)
    for r in refused:
        kept.append({"op": "use_ability", "actor": pc.ref,
                     "because": f"the player reached for {r['refused_name']}",
                     "params": {"ability": r["refused_name"]}})
    return kept


# --- the page: a power on it that no tell backs -----------------------------------------
#
# The other half of the leak. "I erase the apprentice's memory of me" reached the narrator
# as a turn with nothing in it but `narrate_only`, and the page wrote "the flicker of
# recognition … simply dissolves". Whatever the forward gate refuses, the prose can still
# write the power working: the narrator is fed tells and nothing else about mechanics
# (law 3), and a page is not a tell. So the finished beat is read back with one closed
# question, the deed reader's shape (gm/deed_reader.py): which sentence, if any, has the
# player's character doing what no ordinary person can, that the rules did not resolve
# this turn. Code then holds the answer to the page — a sentence about the player — and
# gm/checks/power_unbacked.py repairs it. dungeonOne's issue #111 is this exact defect in
# another LLM-GM ("the player-visible reply cannot claim the refused result"), and its
# listed fixes are ours: an engine-authored fallback, and a check that the narration does
# not assert results the turn did not produce.

_UNBACKED_SYSTEM = (
    "You check one passage of a tabletop game, narrated to the player as \"you\". Find "
    "the first sentence in which the PLAYER'S character does or causes something no "
    "ordinary person can: reads or changes a mind or a memory, hears thoughts, compels "
    "someone by will alone, vanishes, flies, passes through solid things, conjures or "
    "summons, changes the weather, transforms, heals or harms by will, or knows what they "
    "could not know. It does not count when the RULES list says it happened this turn, or "
    "when it is one of the character's own GIFTS. Other people's magic does not count. "
    "Ordinary persuading, lying, fighting, luck, and someone believing or agreeing do not "
    "count. Answer its number, or 0 when there is none.")

_UNBACKED_DEMOS = [
    (["The guard keeps his post."], ["darkvision 60 ft"],
     ["You meet the guard's eyes and push, and the memory of your face slides out of his "
      "head.", "He blinks at the empty road as if he had never seen you.",
      "What do you do?"], "1"),
    (["You cast Sleep. The sentry fails his save and falls asleep."], [],
     ["You murmur the words and trace the sign in the air.",
      "The sentry's chin drops to his chest and he begins to snore.",
      "What do you do?"], "0"),
    (["You speak to the reeve. Bluff 21 against his Sense Motive 9: he believes you."], [],
     ["You tell the reeve you were at the mill all night.",
      "He nods slowly; the story sits well with him.", "What do you do?"], "0"),
]


def _unbacked_ask(rules: list[str], gifts: list[str], sentences: list[str]) -> str:
    page = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, 1))
    said = "\n".join(f"- {r}" for r in rules) or "- nothing magical"
    have = ", ".join(gifts) or "none"
    return (f"THE RULES SAY THIS HAPPENED:\n{said}\n\nTHE CHARACTER'S OWN GIFTS: {have}"
            f"\n\nPASSAGE, BY SENTENCE:\n{page}")


def unbacked_messages(rules, gifts, sentences) -> list[dict]:
    import json

    out = [{"role": "system", "content": _UNBACKED_SYSTEM}]
    for r, g, page, answer in _UNBACKED_DEMOS:
        out.append({"role": "user", "content": _unbacked_ask(r, g, page)})
        out.append({"role": "assistant", "content": json.dumps({"sentence": answer})})
    out.append({"role": "user", "content": _unbacked_ask(rules, gifts, sentences)})
    return out


def gifts_of(pc) -> list[str]:
    """What the character has that needs no op to work — the race's traits, feats,
    abilities — for the page reader to let stand."""
    if pc is None:
        return []
    return list(dict.fromkeys(n for k, n in _held_names(pc)
                              if k in ("trait", "feat", "ability")))[:40]


def read_unbacked(text: str, rules: list[str], gifts: list[str], *, chat=None,
                  model: str = "", host: str = "", provider: str = "ollama",
                  api_key: str = "", pc_name: str = "") -> tuple[str, str]:
    """(the first page sentence with the player doing what no ordinary person can and the
    rules did not resolve, an error). "" when there is none, when the reader names a
    sentence not about the player, or when the read fails (the error says so)."""
    from .checks._page import page_sentences
    from .deed_reader import about_the_player

    pairs = page_sentences(text)
    if not pairs:
        return "", ""
    if chat is None:
        from . import client

        chat = client.chat
    written = [w for w, _n in pairs]
    schema = {"type": "object",
              "properties": {"sentence": {"type": "string",
                                          "enum": [str(i) for i in range(len(written) + 1)]}},
              "required": ["sentence"]}
    try:
        reply = chat(unbacked_messages(rules, gifts, written), model, host, as_json=True,
                     think=False, temperature=0.0, num_predict=24, provider=provider,
                     api_key=api_key, schema=schema)
        at = int(str((reply.json() or {}).get("sentence") or "0"))
    except Exception as exc:  # noqa: BLE001 — a failed read must never lose the turn
        return "", f"{type(exc).__name__}: {str(exc)[:120]}"
    if not 1 <= at <= len(written):
        return "", ""
    if not about_the_player(written[at - 1], pairs[at - 1][1], "", pc_name):
        return "", ""
    return written[at - 1], ""
