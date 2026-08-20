"""Build the machine-readable rules reference from the Pathfinder PDFs.

Point it at the directory holding the books and it writes `reference/`; the app then
reads that and never opens a PDF again. Re-run it when you add or replace a book — the
outputs are derived data, not source, and they are regenerated rather than hand-edited.

    python reference/build_reference.py --library "H:/Pathfinder"

**What this deliberately does not do.** It does not dump the books. Two reasons, and
both matter:

  * The rules are Open Game Content under the OGL, but the PDFs also contain Product
    Identity — setting, deities, iconic characters, art and trade dress — which is not
    licensed and must not be redistributed. Extracting mechanics and an index is fine;
    extracting everything is not. See OGL-NOTICE.md.
  * A dump of eighteen books is not more useful to an agent than the books were. A
    *name-to-page index* plus *structured mechanics* is what actually removes the need
    to open a PDF.

So the outputs are: a complete navigable index of every book, a flat lookup across all
of them, and structured JSON for the subsystems the engine implements.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - tooling only
    raise SystemExit("pypdf is needed to build the reference: python -m pip install pypdf")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from books import identify  # noqa: E402

HERE = Path(__file__).resolve().parent

TABLE_RE = re.compile(r"^table\s+([0-9]+)[–\-—]([0-9]+)\s*:?\s*(.*)$", re.I)
# "CR 5", "CR 1/2", "CR 13" as printed in a stat block header.
CR_RE = re.compile(r"\bCR\s+(\d+(?:/\d+)?)\b")

# Outline entries that are structure, not content — skipped when harvesting names.
NOT_CONTENT = {
    "front cover", "back cover", "cover", "credits", "title page", "table of contents",
    "contents", "introduction", "index", "front matter", "ogl", "open game license",
    "open game licence", "appendix", "glossary", "inside front cover",
    "inside back cover", "advertisement", "ads",
}


# --- Outline -------------------------------------------------------------------------

def outline_entries(reader: PdfReader) -> list[dict]:
    """Flatten the PDF outline into (depth, title, page).

    The books ship real outlines and they are extraordinarily good: 1,609 entries in the
    Core Rulebook including every numbered table, 461 in Bestiary 1 covering every
    monster, 2,788 in Ultimate Equipment covering every item. That is a better index than
    any text-scraping would produce, and it is free.
    """
    out: list[dict] = []

    def walk(items, depth=0):
        for it in items:
            if isinstance(it, list):
                walk(it, depth + 1)
                continue
            try:
                title = " ".join(str(it.title).split())
                page = reader.get_destination_page_number(it)
            except Exception:
                continue
            if title:
                out.append({"depth": depth, "title": title, "page": page})

    try:
        walk(reader.outline)
    except Exception:
        pass
    return out


def numbered_tables(entries: list[dict]) -> list[dict]:
    tables = []
    for e in entries:
        m = TABLE_RE.match(e["title"])
        if m:
            tables.append({
                "number": f"{m.group(1)}-{m.group(2)}",
                "title": m.group(3).strip() or e["title"],
                "page": e["page"],
            })
    return tables


def content_entries(entries: list[dict]) -> list[dict]:
    """The outline entries that name a thing — a monster, an item, a feat, a spell.

    Anything shallow is a chapter and anything in NOT_CONTENT is front matter; what is
    left is the stuff you actually look up.
    """
    out = []
    for e in entries:
        title = e["title"]
        low = title.lower().strip()
        if low in NOT_CONTENT or TABLE_RE.match(title):
            continue
        if len(low) <= 1:            # the A/B/C letter dividers in Ultimate Equipment
            continue
        if e["depth"] < 1:
            continue
        out.append(e)
    return out


# --- Creature CR -----------------------------------------------------------------------

def _name_variants(title: str) -> list[str]:
    """How the book might print a name the outline gives as "Bear, Dire".

    Deliberately does *not* fall back to the head word alone. "Barghest, Greater" would
    then match plain "Barghest" and inherit its CR 4, when the greater barghest is worth
    considerably more — and a wrong CR is worse than a missing one, because the encounter
    builder will act on it without knowing to doubt it.
    """
    if "," not in title:
        return [title]
    head, tail = title.split(",", 1)
    return [title, f"{tail.strip()} {head.strip()}"]


def _squash(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def name_candidates(before: str) -> list[str]:
    """Every plausible creature name in the text just before a `CR n`.

    One rule, not a cascade. Earlier versions tried to decide *which* shape a header was
    — "Aboleth ABOLETh" doubled by the running margin, or "AChAIERAI" standing alone —
    and every fix for one shape broke the other: repairing the aboleth lost the ghoul,
    repairing the ghoul lost the aboleth.

    Since `_canonical` now discards anything the outline does not confirm, guessing is
    unnecessary. This yields the trailing one, two and three alphabetic words and lets
    the outline decide which of them is real. Wrong guesses cost nothing because they
    match nothing.
    """
    words = [w for w in re.split(r"\s+", before.strip()) if w]
    tail: list[str] = []
    for w in reversed(words):
        if not re.fullmatch(r"[A-Za-z'’\-]{2,}", w):
            break
        tail.insert(0, w)
        if len(tail) == 4:
            break
    return [" ".join(tail[i:]) for i in range(len(tail))]


def _undouble(raw: str) -> str:
    """Collapse a name the page repeats: "Ghoul ghOUL" -> "Ghoul".

    Bestiary pages carry a running header in the margin, and the text layer emits it
    immediately before the stat-block header of the same creature. Left alone this
    produced "Ghoul Ghoul" and "Troll Troll", which then match nothing.
    """
    s = " ".join(raw.split())
    letters = re.sub(r"[^a-z]", "", s.lower())
    n = len(letters)
    for parts in (2, 3):
        if n and n % parts == 0:
            unit = letters[: n // parts]
            if unit * parts == letters:
                kept, count = [], 0
                for ch in s:
                    kept.append(ch)
                    if ch.isalpha():
                        count += 1
                    if count == len(unit):
                        break
                return "".join(kept).strip()
    return s


def _canonical(raw: str, on_page: list[dict]) -> str | None:
    """The outline's spelling of this name, or None if the outline does not have it.

    Returning None — and dropping the creature — is deliberate. Two heuristics are at
    work in the scan, one for headers the page prints twice ("Aboleth ABOLETh") and one
    for headers that stand alone ("AChAIERAI"), and tuning either one kept breaking the
    other: fixing the aboleth lost the ghoul, and fixing the ghoul lost the aboleth.

    Requiring the name to appear in the outline *on the same page* ends that. It is a
    fact about the book rather than a guess about its typography, so it cannot silently
    mis-price anything. The cost is coverage in books whose outlines are organised by
    family rather than by creature, and that is the right way round: a missing creature
    is a gap, a wrong CR is a lie the encounter builder will act on.
    """
    squashed = _squash(raw)
    if not squashed:
        return None
    for e in on_page:
        for variant in _name_variants(e["title"]):
            if _squash(variant) == squashed:
                return e["title"]
    return None


def scan_statblocks(reader: PdfReader, entries: list[dict], limit_pages: int) -> list[dict]:
    """Find every creature by its stat-block header, page by page.

    This replaced an approach that walked the *outline* and looked for a CR beside each
    name. That worked for Bestiary 1 and collapsed on Bestiary 2, which found 63 of 379:
    its outline is organised by family, so "Aeon" and "Agathion" are lore pages carrying
    no stat block at all while the actual creatures sit on later pages under names the
    outline never lists.

    Scanning for the header instead is independent of how good a book's outline is, which
    also makes it the only approach that works for the Codex, whose outline is 26 entries
    for the whole book. The outline is still used, but only to recover the properly-cased
    spelling of a name the display font mangled.
    """
    by_page: dict[int, list[dict]] = {}
    for e in entries:
        if e["page"] < limit_pages:
            by_page.setdefault(e["page"], []).append(e)

    out: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for page in range(min(limit_pages, len(reader.pages))):
        try:
            text = reader.pages[page].extract_text() or ""
        except Exception:
            continue
        flat = " ".join(text.split())
        if "CR" not in flat:
            continue
        for m in CR_RE.finditer(flat):
            window = flat[max(0, m.start() - 60):m.start()]
            name = None
            for candidate in name_candidates(window):
                name = _canonical(_undouble(candidate), by_page.get(page, []))
                if name:
                    break
            if name is None:
                continue
            key = (name.lower(), page)
            if key in seen:
                continue
            seen.add(key)
            out.append({"name": name, "page": page, "cr": m.group(1)})

    out.sort(key=lambda c: (c["page"], c["name"]))
    return out


def creature_entries(reader: PdfReader, entries: list[dict], limit_pages: int) -> list[dict]:
    """Every creature with its CR, read from the stat-block header next to its name.

    Encounter building for a *single* PC is an open question in docs/architecture.md and
    cannot be attempted without knowing what each creature is worth. The outline gives
    names and pages; CR only exists in the text, so this is the one place the builder
    reads whole pages.

    The CR is anchored to the creature's *name*, not simply taken as the first on the
    page. Bestiary pages routinely carry two or three stat blocks, and taking the first
    CR gave the second and third monsters the first one's rating — which would quietly
    mis-price a third of every encounter built from it.
    """
    by_page: dict[int, list[dict]] = {}
    for e in entries:
        if e["page"] < limit_pages:
            by_page.setdefault(e["page"], []).append(e)

    out: list[dict] = []
    for page, on_page in sorted(by_page.items()):
        try:
            text = reader.pages[page].extract_text() or ""
        except Exception:
            text = ""
        flat = " ".join(text.split())
        all_crs = CR_RE.findall(flat)

        for e in on_page:
            cr = None
            best = None
            for variant in _name_variants(e["title"]):
                # Every occurrence, not just the first. The page carries a running
                # header, so the text reads "Troll TROLL CR 5": the first match is the
                # header and the stat block is a few characters further on. Taking the
                # *closest* CR to any occurrence lands on the stat block every time.
                for m in re.finditer(re.escape(variant), flat, re.I):
                    after = CR_RE.search(flat, m.end())
                    if not after:
                        continue
                    gap = after.start() - m.end()
                    if best is None or gap < best[0]:
                        best = (gap, after.group(1))
            # A stat-block header reads "DIRE BEAR CR 7" — the CR sits right against the
            # name. Anything further away is the *next* creature's header, which is how
            # the dire bear came out sharing the grizzly's CR 4 on a page holding both.
            if best and best[0] <= 5:
                cr = best[1]
            # A page with exactly one outline entry and exactly one CR is unambiguous
            # even when the name did not match (it is often set in a display face the
            # text layer mangles).
            if cr is None and len(on_page) == 1 and len(set(all_crs)) == 1:
                cr = all_crs[0]
            out.append({"name": e["title"], "page": page, "cr": cr})

    out.sort(key=lambda c: (c["page"], c["name"]))
    return out


# --- Typography ------------------------------------------------------------------------

_EDGE = ".,;:()'\"!?–—-"

# Real English words of four letters or fewer, used only to keep the ligature repair from
# joining two ordinary words.
SHORT_WORDS = set("""
a an as at be by do go he i if in is it me my no of on or so to up us we am are and but
for not the you your his her its own out off per can may all any one two was were has
had have does did who whom why how when what that this then than them they their there
here with from into upon over under back down each even ever full half hits just keep
kind last less like long lose made make many more most move much must near need next
none once only open take time turn used uses very well will area both call case cast
dead deal done draw drop ends face fall feat feel feet fire foot free gain give goes
gone good hand hard head hold hour idea item lets line list live loss lost mind name
note pick play plus port rate read real rest ride roll rule runs save seen sees self
send show side size skip slow some sort stop such sure tell term test thus told took
type user view wall want ways wear went whip wide wins wise word work year
""".split())

# Every English word of one or two letters. Unlike a list of *short* words this one can
# actually be complete, which is what makes the fragment test below reliable.
TINY_WORDS = {
    "a", "i", "am", "an", "as", "at", "be", "by", "do", "go", "ha", "he", "hi", "id",
    "if", "in", "is", "it", "la", "lo", "me", "mu", "my", "no", "of", "oh", "ok", "on",
    "or", "ox", "pi", "so", "to", "up", "us", "we", "ye", "ad", "ah", "aw", "ax", "eh",
    "el", "em", "en", "er", "ex", "fa", "hm", "jo", "ma", "na", "od", "oe", "oi",
    "om", "op", "os", "ow", "oy", "pa", "re", "sh", "si", "ti", "uh", "um", "un", "ut",
    "xi", "ya", "yo", "za",
}


def _short(tok: str) -> bool:
    """A lowercase alphabetic piece of at most three letters, with no punctuation.

    Case matters: "AC", "CR" and "DC" are meant to be two letters, and an earlier version
    welded "to AC and" into "to ACand".
    """
    return bool(tok) and tok.isalpha() and tok.islower() and len(tok) <= 3


def _repair_kerning(text: str) -> str:
    """Rejoin words the PDF's text layer broke apart: "s itu ation" -> "situation".

    The test is not "does this look like a word" — no dictionary of short words can be
    complete, and an earlier version that tried welded "with a dog" into "with adog" and
    "not yet acted" into "not yetacted".

    What is reliable is the *shape* of the damage. A kerned break produces three or more
    consecutive pieces, and at least one of them is a one- or two-letter token that is
    not an English word. `TINY_WORDS` can be exhaustive at that length, so that test does
    not degrade. Ordinary prose ("with a dog", "he is in") never trips it.
    """
    toks = text.split(" ")
    definite = [
        bool(t) and t.isalpha() and t.islower() and len(t) <= 2 and t not in TINY_WORDS
        for t in toks
    ]

    out: list[str] = []
    i = 0
    while i < len(toks):
        if not definite[i]:
            out.append(toks[i])
            i += 1
            continue

        # Grow outwards from the anchor. Leftwards only over another certain fragment or
        # a lone letter — a lone letter may be a real word ("a") and still be the head of
        # a broken one ("a lw ays"). Never over an ordinary short word, which is how
        # "to the s itu ation" lost its "to the".
        start = i
        while start > 0 and _short(toks[start - 1]) and (
            definite[start - 1] or len(toks[start - 1]) == 1
        ):
            start -= 1
        end = i + 1
        while end < len(toks) and _short(toks[end]):
            end += 1

        pieces = toks[start:end]
        # A tail is only wanted when the pieces so far are too few letters to be the
        # whole word: "s"+"itu" needs "ation", but "a"+"lw"+"ays" is already "always"
        # and must not swallow the next word.
        if sum(len(p) for p in pieces) <= 4 and end < len(toks):
            tail = toks[end]
            bare = tail.strip(_EDGE)
            if bare.isalpha() and bare.islower():
                pieces = pieces + [tail]
                end += 1

        if len(pieces) >= 3:
            out[len(out) - (i - start):] = []      # drop any pieces already emitted
            out.append("".join(pieces))
            i = end
        else:
            out.append(toks[i])
            i += 1
    return " ".join(out)


def clean(text: str) -> str:
    """Undo the PDF's typography so regexes and humans can both read it.

    The books are typeset with ligatures and tight kerning, and the text layer comes out
    with words broken apart: "f lat-footed", "inf lict", "s itu ation", "c re atures".
    Shipping that would mean the reference contains words no search will ever match.
    """
    text = text.replace("\ufffd", "'").replace("\u2019", "'")

    # The fi/fl/ft ligature family, where the "f" is torn from what follows it. Two
    # shapes: a bare "f" ("f lat-footed"), and a word left ending in f ("inf lict").
    text = re.sub(r"\bf\s+(?=(?:l|i|t|b|f)[a-z])", "f", text)

    def join_ligature(m: re.Match) -> str:
        head, rest = m.group(1), m.group(2)
        # "of light" and "if lying" are two real words; "inf lict" is one broken one.
        if head.lower() in TINY_WORDS or head.lower() in SHORT_WORDS:
            return m.group(0)
        return head + rest

    text = re.sub(r"\b([a-z]{2,}f) ((?:l|i|t)[a-z]{2,})", join_ligature, text)

    text = _repair_kerning(text)

    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# --- Targeted extractions from the Core Rulebook ---------------------------------------

CONDITION_NAMES = [
    "Bleed", "Blinded", "Broken", "Confused", "Cowering", "Dazed", "Dazzled", "Dead",
    "Deafened", "Disabled", "Dying", "Energy Drained", "Entangled", "Exhausted",
    "Fascinated", "Fatigued", "Flat-Footed", "Frightened", "Grappled", "Helpless",
    "Incorporeal", "Invisible", "Nauseated", "Panicked", "Paralyzed", "Petrified",
    "Pinned", "Prone", "Shaken", "Sickened", "Staggered", "Stable", "Stunned",
    "Unconscious",
]


def find_page(entries: list[dict], needle: str) -> int | None:
    needle = needle.lower()
    for e in entries:
        if e["title"].lower() == needle:
            return e["page"]
    for e in entries:
        if needle in e["title"].lower():
            return e["page"]
    return None


def page_text(reader: PdfReader, first: int, last: int) -> str:
    return "\n".join((reader.pages[i].extract_text() or "") for i in range(first, last + 1))


def extract_conditions(reader: PdfReader, entries: list[dict]) -> dict:
    start = find_page(entries, "Appendix 2: Conditions")
    if start is None:
        return {"source": None, "conditions": []}
    text = clean(page_text(reader, start, min(start + 3, len(reader.pages) - 1)))

    positions = []
    for name in CONDITION_NAMES:
        m = re.search(rf"\b{re.escape(name)}\s*:", text, re.I)
        if m:
            positions.append((m.start(), m.end(), name))
    positions.sort()

    conditions = []
    for i, (s, e, name) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        conditions.append({
            "name": name, "key": name.lower(),
            "description": " ".join(text[e:end].split()),
        })
    return {"source": {"book": "CRB", "section": "Appendix 2: Conditions",
                       "pdf_page": start},
            "conditions": conditions}


def extract_encounter_tables(reader: PdfReader, entries: list[dict]) -> dict:
    start = find_page(entries, "Designing Encounters")
    out = {"source": {"book": "CRB", "section": "Designing Encounters", "pdf_page": start}}
    if start is None:
        return out
    out["raw_pages"] = {
        str(p): clean(reader.pages[p].extract_text() or "")
        for p in range(start, min(start + 4, len(reader.pages)))
    }
    return out


# --- Per-book build ---------------------------------------------------------------------

def build_book(path: Path, meta: dict, with_cr: bool) -> dict:
    reader = PdfReader(str(path))
    entries = outline_entries(reader)
    tables = numbered_tables(entries)
    contents = content_entries(entries)

    book = {
        **meta,
        "source_file": path.name,
        "pdf_pages": len(reader.pages),
        "counts": {
            "sections": len(entries),
            "tables": len(tables),
            "entries": len(contents),
        },
        "tables": tables,
        "sections": entries,
    }

    if meta["kind"] == "bestiary" and with_cr:
        # The *full* outline, not the filtered content list: plenty of monsters sit at
        # depth 0 and filtering them out left the scanner with no name to match
        # against, which silently halved coverage.
        book["creatures"] = scan_statblocks(reader, entries, len(reader.pages))
        book["counts"]["creatures"] = len(book["creatures"])

    if meta["kind"] == "equipment":
        book["items"] = [{"name": e["title"], "page": e["page"]} for e in contents]
        book["counts"]["items"] = len(book["items"])

    return book, reader, entries


# --- CLI ----------------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--library", type=Path, default=Path("H:/Pathfinder"),
                    help="directory holding the PDFs")
    ap.add_argument("--out", type=Path, default=HERE)
    # Indexing every book is a second's work; reading creature CRs means extracting the
    # text of every bestiary page and takes minutes. They are separated so a re-index is
    # cheap and the slow part can be done a book at a time.
    ap.add_argument("--cr", default="all",
                    help="which bestiaries to read CRs for: 'all', 'none', or a "
                         "comma-separated list of slugs")
    args = ap.parse_args()

    if args.cr.strip().lower() == "all":
        wants_cr = lambda slug: True                                  # noqa: E731
    elif args.cr.strip().lower() in ("none", ""):
        wants_cr = lambda slug: False                                 # noqa: E731
    else:
        wanted = {s.strip() for s in args.cr.split(",") if s.strip()}
        wants_cr = lambda slug: slug in wanted                        # noqa: E731

    if not args.library.is_dir():
        raise SystemExit(f"no such directory: {args.library}")

    pdfs = sorted(args.library.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"no PDFs in {args.library}")

    books_dir = args.out / "books"
    books_dir.mkdir(parents=True, exist_ok=True)

    catalogue = []
    lookup: dict[str, list] = {}
    unknown = []

    for path in pdfs:
        meta = identify(path.name)
        if meta is None:
            unknown.append(path.name)
            continue
        started = time.monotonic()
        try:
            book, reader, entries = build_book(path, meta, with_cr=wants_cr(meta["slug"]))
        except Exception as exc:
            print(f"  !! {path.name}: {exc}")
            continue

        out_path = books_dir / f"{meta['slug']}.json"
        if meta["kind"] == "bestiary" and "creatures" not in book and out_path.exists():
            try:
                previous = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                previous = {}
            if previous.get("creatures"):
                book["creatures"] = previous["creatures"]
                book["headings"] = previous.get("headings", [])
                book["counts"]["creatures"] = len(book["creatures"])
                book["counts"]["carried_over"] = True
        write(out_path, book)
        took = time.monotonic() - started
        print(f"     {book['counts']['sections']} sections, "
              f"{book['counts']['tables']} tables, "
              f"{book['counts']['entries']} entries"
              + (f", {book['counts'].get('creatures', 0)} creatures"
                 if "creatures" in book["counts"] else "")
              + f"  [{took:.0f}s]")

        catalogue.append({
            "slug": meta["slug"], "title": meta["title"], "abbr": meta["abbr"],
            "kind": meta["kind"], "source_file": path.name,
            "pdf_pages": book["pdf_pages"], "counts": book["counts"],
        })

        for e in content_entries(entries):
            lookup.setdefault(e["title"].lower(), []).append(
                {"book": meta["abbr"], "slug": meta["slug"], "page": e["page"],
                 "name": e["title"]}
            )

        # The Core Rulebook is also the source for the engine's own tables.
        if meta["kind"] == "core":
            write(args.out / "conditions.json", extract_conditions(reader, entries))
            write(args.out / "encounter-design.json",
                  extract_encounter_tables(reader, entries))

    write(args.out / "index.json", {
        "books": catalogue,
        "totals": {
            "books": len(catalogue),
            "pdf_pages": sum(b["pdf_pages"] for b in catalogue),
            "sections": sum(b["counts"]["sections"] for b in catalogue),
            "tables": sum(b["counts"]["tables"] for b in catalogue),
            "entries": sum(b["counts"]["entries"] for b in catalogue),
        },
        "unrecognised_files": unknown,
    })
    write(args.out / "lookup.json", lookup)
    write_index_markdown(args.out / "INDEX.md", catalogue, lookup, unknown)

    if unknown:
        print("\n  not in the catalogue (add them to reference/books.py):")
        for u in unknown:
            print("   -", u)


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    size = path.stat().st_size
    unit = f"{size // 1024} KB" if size < 1024 * 1024 else f"{size / 1048576:.1f} MB"
    print(f"  {path.relative_to(HERE) if HERE in path.parents else path.name}: {unit}")


def write_index_markdown(path: Path, catalogue: list[dict], lookup: dict,
                         unknown: list[str]) -> None:
    lines = [
        "# Rules reference index",
        "",
        "Generated by `reference/build_reference.py`. **Do not hand-edit** — re-run the",
        "builder instead.",
        "",
        "Page numbers are *PDF page numbers*, zero-based, which is what a reader tool",
        "wants. They do not match the printed numbers in the books' own footers.",
        "",
        "| Book | | Kind | PDF pages | Sections | Tables | Named entries | Creatures |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for b in catalogue:
        c = b["counts"]
        creatures = c.get("creatures")
        lines.append(
            f"| {b['title']} | `{b['abbr']}` | {b['kind']} | {b['pdf_pages']} | "
            f"{c['sections']} | {c['tables']} | {c['entries']} | "
            f"{creatures if creatures is not None else '—'} |"
        )
    totals = {
        "pdf_pages": sum(b["pdf_pages"] for b in catalogue),
        "sections": sum(b["counts"]["sections"] for b in catalogue),
        "tables": sum(b["counts"]["tables"] for b in catalogue),
        "entries": sum(b["counts"]["entries"] for b in catalogue),
    }
    lines += [
        f"| **{len(catalogue)} books** | | | **{totals['pdf_pages']}** | "
        f"**{totals['sections']}** | **{totals['tables']}** | **{totals['entries']}** |",
        "",
        "## How to look something up",
        "",
        "`lookup.json` maps a lowercased name to every book and page it appears in —",
        f"{len(lookup)} distinct names across the library. That is the fast path: one",
        "file, one dictionary hit, and you know which book and which page.",
        "",
        "`books/<slug>.json` has the full outline for a single book, plus its numbered",
        "tables. Bestiaries also carry a `creatures` list with CR where it could be read",
        "from the stat block; Ultimate Equipment carries an `items` list.",
        "",
    ]
    if unknown:
        lines += ["## Not indexed", "",
                  "These files are in the library but not in `reference/books.py`:", ""]
        lines += [f"- `{u}`" for u in unknown] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {path.name}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
