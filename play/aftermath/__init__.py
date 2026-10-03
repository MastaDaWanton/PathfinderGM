"""After-the-beat steps: one module per step, found by filename (docs/fix-interfaces.md §2.3).

A step reads a beat the page has just been given and writes what follows from it into the
engine's own records — a speaker who addressed the player gets a body, a person placed
elsewhere becomes a population record, a line spoken becomes a conversation-log entry. It
returns turn-log rows; it never edits the prose.

**Why a registry and not another block in `_finish`.** Four Phase-2 lanes (A, D, F and C
through the opening) each wanted a few lines at the end of `views._finish`, a function one
lane owns. A shared list to append to is the conflict every one of them would have hit, so
there is no list: a module dropped into this package is a member.

**Two stages, because the plan's one hook site was wrong** (§1.1 P3). The plan put the
hook "after the said/hails block"; the hails are not there. `_finish` runs
`apply_introductions`, then `hailed_by` → `join_talk`, and only much later appends the beat
and writes the speech-tags row. A speaker made real has to exist before `hailed_by` reads
the page (A), and a log entry needs the beat's transcript index (F). So:

  * ``"people"`` runs immediately before the `hailed_by` loop. `said` is the LIVE
    `agent.last_said`, and this stage alone may fill an empty `who` (adding ``"made"``);
  * ``"beat"`` runs after the speech-tags row, before `c.history.append`. `said` is the
    records kept on the beat, and `beat_index` is that beat's place in the transcript.

**The member contract** (a module that breaks it is refused with the fix named)::

    STAGE: str                        # "people" | "beat"
    ORDER: int                        # run order within the stage; ties by module name
    DOORS: frozenset[str]             # optional; default {"turn", "carry_on"}
    def step(ctx: AfterBeat) -> list[dict]      # turn-log rows

A module whose name starts with `_` is a helper, never a member.

**Discovery** is `pkgutil.iter_modules` over the package's own `__path__`, never a glob of
the directory beside `__file__`, which lies once the app is frozen (CLAUDE.md). Frozen,
PyInstaller answers `iter_modules` from the bundle, which holds only what the spec
collected — `pathfindergm.spec` names this package in `DISCOVERED_PACKAGES`.

**A step never costs the turn.** `run` catches any exception a member raises, and any
break of the contract, as ``{"kind": "aftermath-error", "member", "error"}`` — the shape
`gm.checks` gives its own broken members — and carries on with the next member. The rows
are the turn log's; a failed bookkeeping step is a line in it, not a 500.
"""
from __future__ import annotations

import copy
import dataclasses
import importlib
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:  # pragma: no cover - names for the annotations only
    from gm.mentions import Attribution
    from play.campaign import Campaign
    from rules.engine import Outcome, Scene
    from world.loader import World

STAGES = ("people", "beat")
# `_finish`'s two doors and the opening's. Continue is a door of its own because a step
# that logs the player's words must know there were none (design F: "Continue records
# nothing").
ALL_DOORS = frozenset({"turn", "carry_on", "opening"})
DEFAULT_DOORS = frozenset({"turn", "carry_on"})


@dataclass(frozen=True)
class AfterBeat:
    """Everything a step may read about the beat just written (§2.3, field for field).

    Derived values are not fields, as in `gm.checks.BeatContext`: members reach the
    engine through `campaign.engine()`, and a second copy of a fact the engine holds is
    the parallel store law two forbids. `people` and `talking_after` are snapshots taken
    when the stage starts, so every member of a stage reads the same room even when an
    earlier member changed it."""
    stage: str                      # "people" | "beat"
    door: str                       # "turn" | "carry_on" | "opening"
    campaign: "Campaign"            # members reach the engine through campaign.engine()
    scene: "Scene"
    world: "World | None"
    text: str                       # the beat as it stands at this stage
    said: list[dict]                # "people": the LIVE agent.last_said; "beat": the records kept on the beat
    player_text: str                # "" for buttons and the opening
    attachments: tuple[dict, ...]
    reading: Mapping | None
    attribution: "Attribution | None"
    outcomes: tuple["Outcome", ...]
    people: Mapping[str, Mapping]   # ref -> {"name", "pronouns", "is_pc"}, snapshot at stage start
    talking_after: tuple[str, ...]  # engine.talking_to() refs at stage start
    beat_index: int | None          # None in "people" (the beat is not appended yet)
    turn: int


class AftermathContractError(TypeError):
    """A member module that does not keep the contract above, raised with the module and
    the fix named. `registered()` raises it, so the suite fails on a malformed member;
    `run()` turns it into an `aftermath-error` row, so the packaged game never does."""


def _short(module: ModuleType) -> str:
    return module.__name__.rsplit(".", 1)[-1]


def _doors(module: ModuleType) -> frozenset:
    return getattr(module, "DOORS", DEFAULT_DOORS)


def _validate(module: ModuleType) -> None:
    name = f"play.aftermath.{_short(module)}"
    stage = getattr(module, "STAGE", None)
    if stage not in STAGES:
        raise AftermathContractError(f"{name}: STAGE must be one of {STAGES} "
                                     f"(got {stage!r}); set e.g. `STAGE = \"beat\"`")
    order = getattr(module, "ORDER", None)
    if not isinstance(order, int) or isinstance(order, bool):
        raise AftermathContractError(f"{name}: ORDER must be an int (got {order!r}); "
                                     f"set e.g. `ORDER = 50`")
    doors = _doors(module)
    if not isinstance(doors, frozenset) or not doors or not doors <= ALL_DOORS:
        raise AftermathContractError(f"{name}: DOORS must be a non-empty frozenset drawn "
                                     f"from {sorted(ALL_DOORS)} (got {doors!r}), or left "
                                     f"out for the default {sorted(DEFAULT_DOORS)}")
    if not callable(getattr(module, "step", None)):
        raise AftermathContractError(f"{name}: needs `def step(ctx) -> list[dict]`")


def _discover() -> tuple[list[ModuleType], list[dict]]:
    """The members, and a row for each module that could not be imported or validated."""
    members, broken = [], []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"{__name__}.{info.name}")
            _validate(module)
        except Exception as exc:  # noqa: BLE001 — sorted out by the caller
            broken.append({"kind": "aftermath-error", "member": info.name,
                           "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                           "exc": exc})
            continue
        members.append(module)
    # (STAGE, ORDER, name): the stage first so a listing reads in the order `_finish`
    # runs them; within a stage two lanes that pick one ORDER still get one answer.
    members.sort(key=lambda m: (STAGES.index(m.STAGE), m.ORDER, _short(m)))
    return members, broken


def registered() -> tuple[ModuleType, ...]:
    """The member modules, sorted by (STAGE, ORDER, module name).

    Discovered afresh on every call, over the package's own `__path__`, never cached: the
    directory is the registry. A module that cannot be imported, or breaks the contract,
    raises here — this is what the tests call."""
    members, broken = _discover()
    if broken:
        raise broken[0]["exc"]
    return tuple(members)


def _said_snapshot(said) -> list[dict]:
    return copy.deepcopy([dict(r) for r in (said or [])])


def _said_kept(before: list[dict], after, stage: str) -> str:
    """What a member did to `said` that it may not do, or "".

    The changes allowed are the "people" stage's, and only two — both A's `speaker_real`
    (§2.3): giving an empty `who` a ref and saying so with `"made"`, and ADDING a record
    for a line nobody tagged, which says so with `"made"` equal to its `who` and `"from":
    "page"`. The second was added after the Phase-2 live gate (G2, 2026-09-29): a beat
    with no tags at all has no record to fill, and "a man in a stained leather apron" who
    spoke twice to the player was left with nothing to carry his lines. Everything else is
    the page's record of who said which line, and a bookkeeping step does not get to
    rewrite it.

    And a third, after the 2026-09-30 playtest (item 1): ADDING a record for a line the
    page attributes to somebody already on the board ("'…,' the cage owner says"), which
    says so with `"from": "page"` and has no `"made"` — nobody was made. 6 of 43 real NPC
    lines were missing from the log because the attribution found the speaker and had no
    door to write the line through."""
    after = list(after or [])
    if stage == "people" and len(after) > len(before):
        extra = after[len(before):]
        if all(isinstance(r, dict) and r.get("who") and r.get("from") == "page"
               and r.get("made", r.get("who")) == r.get("who")
               and str(r.get("line") or "").strip()
               for r in extra):
            after = after[:len(before)]
    if len(after) != len(before):
        return f"said went from {len(before)} records to {len(after)}"
    for i, (was, now) in enumerate(zip(before, after)):
        if was == now:
            continue
        if stage == "people" and not was.get("who") and now.get("who"):
            rest_was = {k: v for k, v in was.items() if k not in ("who", "made")}
            rest_now = {k: v for k, v in now.items() if k not in ("who", "made")}
            if rest_was == rest_now:
                continue
        return f"said[{i}] was changed beyond giving an empty `who` a ref"
    return ""


def run(stage: str, ctx: AfterBeat) -> list[dict]:
    """Every member of `stage` that opted in to `ctx.door`, in order; their rows.

    Never raises. A member's exception, a return that is not a list of dicts, or a change
    to `said` the stage does not allow becomes one `aftermath-error` row naming the member
    — and a `said` it damaged is put back — and the next member runs."""
    if ctx.stage != stage:
        ctx = dataclasses.replace(ctx, stage=stage)
    rows: list[dict] = []
    members, broken = _discover()
    rows += [{k: v for k, v in b.items() if k != "exc"} for b in broken]
    for member in members:
        if member.STAGE != stage or ctx.door not in _doors(member):
            continue
        before = _said_snapshot(ctx.said)
        try:
            out = member.step(ctx)
            if out is None:
                out = []
            if not isinstance(out, list) or not all(isinstance(r, dict) for r in out):
                raise AftermathContractError(
                    f"play.aftermath.{_short(member)}.step returned {type(out).__name__}; "
                    f"it must return a list of turn-log row dicts")
            broke = _said_kept(before, ctx.said, stage)
            if broke:
                raise AftermathContractError(f"play.aftermath.{_short(member)}: {broke}")
        except Exception as exc:  # noqa: BLE001 — a broken step must not lose the turn
            if isinstance(ctx.said, list) and _said_snapshot(ctx.said) != before:
                ctx.said[:] = before
            rows.append({"kind": "aftermath-error", "member": _short(member),
                         "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            continue
        rows.extend(out)
    return rows


# --- building a context -------------------------------------------------------------------

def people_of(scene) -> dict[str, dict]:
    """ref -> {"name", "pronouns", "is_pc"} for everybody the scene holds, as it stands."""
    return {ref: {"name": str(getattr(a, "name", "") or ""),
                  "pronouns": str(getattr(a, "pronouns", "") or ""),
                  "is_pc": bool(getattr(a, "is_pc", False))}
            for ref, a in (getattr(scene, "actors", None) or {}).items()}


def talking_refs(engine) -> tuple[str, ...]:
    try:
        return tuple(a.ref for a in engine.talking_to())
    except Exception:  # noqa: BLE001 — a snapshot is never worth failing a turn over
        return ()


def context(stage: str, door: str, campaign, *, engine=None, text: str = "",
            said=None, player_text: str = "", attachments=(), reading=None,
            attribution=None, outcomes=(), beat_index: int | None = None,
            turn: int | None = None) -> AfterBeat:
    """One `AfterBeat`, with the snapshots taken now. `said` is passed through as the
    same list object — the "people" stage's LIVE `agent.last_said` must stay live."""
    scene = campaign.scene
    engine = engine if engine is not None else campaign.engine()
    if not isinstance(reading, Mapping) or "error" in reading:
        reading = None
    return AfterBeat(
        stage=stage, door=door, campaign=campaign, scene=scene,
        world=getattr(campaign, "world", None), text=str(text or ""),
        said=said if isinstance(said, list) else list(said or []),
        player_text=str(player_text or ""),
        attachments=tuple(dict(a) for a in (attachments or ())),
        reading=reading, attribution=attribution, outcomes=tuple(outcomes or ()),
        people=people_of(scene), talking_after=talking_refs(engine),
        beat_index=beat_index,
        turn=int(turn if turn is not None else len(getattr(campaign, "transcript", []) or [])))


def _read_opening(campaign, engine, text: str, said: list[dict], chat=None):
    """The opening beat read by the beat reader (gm/beat_reader.py), as a turn's beat is
    read in `GMAgent._groom`: the opening has no agent, so the narrator's own model is
    asked here. Measured on Sam's save (2026-09-30, item 1): the cage owner's two opening
    lines — "'Went down in the second and has not got up,' the cage owner says" — never
    reached the conversation log; the patterns that booked them retired with the reader.
    None when the reader is off and no `chat` is given (the suite)."""
    from gm import beat_reader

    if not beat_reader.ENABLED and chat is None:
        return None
    cfg = {}
    if chat is None:
        from play import modelcfg

        cfg = modelcfg.for_role("narrator")
    return beat_reader.read(text, campaign.scene, engine=engine, said=said, chat=chat,
                            model=cfg.get("model", ""), host=cfg.get("host", ""),
                            provider=cfg.get("provider", "ollama"),
                            api_key=cfg.get("api_key", ""))


def after_opening(campaign, *, chat=None) -> list[dict]:
    """Both stages over a new campaign's opening beat, with `door="opening"`.

    INERT in Phase 1: nothing calls it. Lane C calls it at the end of `new_campaign` in
    Phase 2, so an opening companion's first lines can be logged (Q48); a member opts in by
    naming "opening" in its DOORS. The rows are returned, not appended — the caller owns
    the turn log it writes them to."""
    transcript = list(getattr(campaign, "transcript", None) or [])
    at = next((i for i in range(len(transcript) - 1, -1, -1)
               if transcript[i].get("who") == "gm"), None)
    beat = transcript[at] if at is not None else {}
    text = str(beat.get("text") or "")
    engine = campaign.engine()
    rows: list[dict] = []
    # The opening has no agent, so the "people" stage reads a copy of the beat's own
    # records as its live list, and what it fills in is written back onto the beat.
    #
    # And the records the written opening's own speaker tags made (`opening_prose.write`
    # keeps them on the campaign): they were thrown away, so the opening's lines never
    # reached the log (2026-09-30 playtest, item 1). Only the lines that still stand on
    # the page — the opening is groomed after the tags are lifted.
    from gm import speech

    kept = list(beat.get("said") or [])
    if not kept:
        lines = speech.lines(text)
        kept = [dict(r) for r in (getattr(campaign, "_opening_said", None) or [])
                if isinstance(r, dict) and r.get("line")
                and any(speech.speaker([r], ln) for ln in lines)]
        if kept and at is not None:
            transcript[at]["said"] = [dict(r) for r in kept]
    live = [dict(r) for r in kept]
    reading = _read_opening(campaign, engine, text, live, chat=chat) if text else None
    if reading is not None and reading.mentions:
        rows.append(reading.as_log())
    rows += run("people", context("people", "opening", campaign, engine=engine, text=text,
                                  said=live, attribution=reading))
    if at is not None and live != list(beat.get("said") or []):
        transcript[at]["said"] = live
    rows += run("beat", context("beat", "opening", campaign, engine=engine, text=text,
                                said=list(beat.get("said") or []), beat_index=at,
                                attribution=reading))
    return rows
