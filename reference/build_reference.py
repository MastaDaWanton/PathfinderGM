"""Build the machine-readable rules reference from the Pathfinder PDFs.

Run this once against your own copies of the books; the app then reads `reference/`
and never opens a PDF again. Re-run it if you replace a PDF — the outputs are derived
data, not source, and they are regenerated rather than hand-edited.

    python reference/build_reference.py --crb "H:/Pathfinder/Pathfinder_Core_Rulebook.pdf" \
                                        --gmg "H:/Pathfinder/...GameMastery Guide.pdf"

**What this deliberately does not do.** It does not dump the books. Two reasons, and
both matter:

  * The rules are Open Game Content under the OGL, but the PDFs also contain Product
    Identity — setting, deities, iconic characters, art and trade dress — which is not
    licensed and must not be redistributed. Extracting mechanics is fine; extracting
    everything is not. See OGL-NOTICE.md.
  * A 1,300-page prose dump is not more useful to an agent than the books were. A
    *section-to-page index* plus *structured mechanics* is what actually removes the
    need to open a PDF.

So the outputs are: a complete navigable index (every section and every table, with its
page), and structured JSON for the subsystems the engine implements.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - tooling only
    raise SystemExit("pypdf is needed to build the reference: python -m pip install pypdf")

HERE = Path(__file__).resolve().parent

BOOKS = {
    "crb": {"title": "Pathfinder Roleplaying Game Core Rulebook", "abbr": "CRB"},
    "gmg": {"title": "Pathfinder Roleplaying Game GameMastery Guide", "abbr": "GMG"},
}

TABLE_RE = re.compile(r"^table\s+([0-9]+)[–\-—]([0-9]+)\s*:?\s*(.*)$", re.I)


def outline_entries(reader: PdfReader) -> list[dict]:
    """Flatten the PDF outline into (depth, title, page).

    The books ship a real outline — 1,609 entries in the Core Rulebook, including every
    numbered table. That is a better index than anything text-scraping would produce,
    and it is free.
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
            out.append({"depth": depth, "title": title, "page": page})

    try:
        walk(reader.outline)
    except Exception:
        pass
    return out


def build_index(paths: dict[str, Path]) -> dict:
    index = {"books": {}}
    for key, path in paths.items():
        if path is None:
            continue
        reader = PdfReader(str(path))
        entries = outline_entries(reader)
        tables = []
        for e in entries:
            m = TABLE_RE.match(e["title"])
            if m:
                tables.append({
                    "number": f"{m.group(1)}-{m.group(2)}",
                    "title": m.group(3).strip() or e["title"],
                    "page": e["page"],
                })
        index["books"][key] = {
            **BOOKS[key],
            "source_file": path.name,
            "pdf_pages": len(reader.pages),
            "sections": entries,
            "tables": tables,
        }
    return index


def page_text(reader: PdfReader, first: int, last: int) -> str:
    return "\n".join((reader.pages[i].extract_text() or "") for i in range(first, last + 1))


def find_page(entries: list[dict], needle: str) -> int | None:
    needle = needle.lower()
    for e in entries:
        if e["title"].lower() == needle:
            return e["page"]
    for e in entries:
        if needle in e["title"].lower():
            return e["page"]
    return None


# --- Conditions -------------------------------------------------------------------

# The condition names as Appendix 2 lists them. Given explicitly rather than discovered,
# because a scraper that guesses at headings silently drops the ones it misparses, and a
# missing condition is a rule the engine will never apply.
CONDITION_NAMES = [
    "Bleed", "Blinded", "Broken", "Confused", "Cowering", "Dazed", "Dazzled", "Dead",
    "Deafened", "Disabled", "Dying", "Energy Drained", "Entangled", "Exhausted",
    "Fascinated", "Fatigued", "Flat-Footed", "Frightened", "Grappled", "Helpless",
    "Incorporeal", "Invisible", "Nauseated", "Panicked", "Paralyzed", "Petrified",
    "Pinned", "Prone", "Shaken", "Sickened", "Attached", "Staggered", "Stable",
    "Stunned", "Unconscious",
]


def extract_conditions(reader: PdfReader, entries: list[dict]) -> dict:
    start = find_page(entries, "Appendix 2: Conditions")
    if start is None:
        return {"source": None, "conditions": []}
    text = page_text(reader, start, min(start + 3, len(reader.pages) - 1))
    text = clean(text)

    # Each condition is "Name: description" running to the next condition's name.
    positions = []
    for name in CONDITION_NAMES:
        m = re.search(rf"\b{re.escape(name)}\s*:", text, re.I)
        if m:
            positions.append((m.start(), m.end(), name))
    positions.sort()

    conditions = []
    for i, (s, e, name) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        body = " ".join(text[e:end].split())
        conditions.append({"name": name, "key": name.lower(), "description": body})
    return {"source": {"book": "CRB", "section": "Appendix 2: Conditions",
                       "pdf_page": start},
            "conditions": conditions}


# Real English words of four letters or fewer, so the kerning repair can tell "who has
# not yet" (leave alone) from "s itu ation" (weld together). Not exhaustive — it only
# has to cover the short words that actually appear in rules prose.
SHORT_WORDS = set("""
a an as at be by do go he i if in is it me my no of on or so to up us we am are and but
for not the you your his her its own out off own per can may all any one two the was
were has had have does did who whom why how when what that this then than them they
their there here with from into upon over under back down each even ever from full
half hits into just keep kind last less like long lose made make many more most move
much must near need next none once only open take than that them time turn used uses
very well were when will with your area both call case cast dead deal does done draw
drop ends face fall feat feel feet fire foot free gain give goes gone good half hand
hard head hold hour idea item lets line list live loss lost mind name none note once
pick play plus port rate read real rest ride roll rule runs save seen sees self send
show side size skip slow some sort stop such sure tell term test thus told took type
turn used user view wall want ways wear well went were what when whip wide will wins
wise with word work year
""".split())


_EDGE = ".,;:()'\"!?–—-"


# Every English word of one or two letters. Unlike a list of *short* words this one can
# actually be complete, which is what makes the test below reliable: a one- or two-letter
# lowercase token that is not in here is not a word, it is the corner of one.
TINY_WORDS = {
    "a", "i", "am", "an", "as", "at", "be", "by", "do", "go", "ha", "he", "hi", "id",
    "if", "in", "is", "it", "la", "lo", "me", "mu", "my", "no", "of", "oh", "ok", "on",
    "or", "ox", "pi", "so", "to", "up", "us", "we", "ye", "ad", "ah", "aw", "ax", "eh",
    "el", "em", "en", "er", "ex", "fa", "hm", "jo", "ma", "na", "od", "oe", "of", "oi",
    "om", "op", "os", "ow", "oy", "pa", "re", "sh", "si", "ti", "uh", "um", "un", "ut",
    "xi", "ya", "yo", "za",
}


def _short(tok: str) -> bool:
    """A lowercase alphabetic piece of at most three letters, with no punctuation.

    Case matters: "AC", "CR" and "DC" are meant to be two letters, and an earlier
    version welded "to AC and" into "to ACand".
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
    Shipping that would mean the app's reference data contains words no search will ever
    match, so it is repaired here rather than left for every reader to trip over.
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


# --- Encounter design and XP ---------------------------------------------------------

def extract_encounter_tables(reader: PdfReader, entries: list[dict]) -> dict:
    start = find_page(entries, "Designing Encounters")
    out = {"source": {"book": "CRB", "section": "Designing Encounters",
                      "pdf_page": start}}
    if start is None:
        return out
    out["raw_pages"] = {}
    for p in range(start, min(start + 4, len(reader.pages))):
        out["raw_pages"][str(p)] = clean(reader.pages[p].extract_text() or "")
    return out


# --- CLI ------------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crb", type=Path, help="Core Rulebook PDF")
    ap.add_argument("--gmg", type=Path, help="GameMastery Guide PDF")
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args()

    paths = {k: v for k, v in (("crb", args.crb), ("gmg", args.gmg)) if v}
    if not paths:
        raise SystemExit("give at least one of --crb / --gmg")
    for p in paths.values():
        if not p.exists():
            raise SystemExit(f"no such file: {p}")

    args.out.mkdir(parents=True, exist_ok=True)

    index = build_index(paths)
    write(args.out / "index.json", index)
    write_index_markdown(args.out / "INDEX.md", index)

    if "crb" in paths:
        reader = PdfReader(str(paths["crb"]))
        entries = index["books"]["crb"]["sections"]
        write(args.out / "conditions.json", extract_conditions(reader, entries))
        write(args.out / "encounter-design.json",
              extract_encounter_tables(reader, entries))

    print("wrote reference to", args.out)


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  {path.name}: {path.stat().st_size // 1024} KB")


def write_index_markdown(path: Path, index: dict) -> None:
    lines = [
        "# Rules index",
        "",
        "Generated by `reference/build_reference.py` from the PDFs. **Do not hand-edit** —",
        "re-run the builder instead.",
        "",
        "Page numbers are *PDF page numbers*, zero-based, which is what a reader tool",
        "wants. They do not match the printed page numbers in the book's own footers.",
        "",
    ]
    for key, book in index["books"].items():
        lines += [
            f"## {book['title']} ({book['abbr']})",
            "",
            f"`{book['source_file']}` — {book['pdf_pages']} PDF pages, "
            f"{len(book['sections'])} sections, {len(book['tables'])} numbered tables.",
            "",
            "### Numbered tables",
            "",
            "| Table | Title | PDF page |",
            "|---|---|---|",
        ]
        for t in book["tables"]:
            lines.append(f"| {t['number']} | {t['title']} | {t['page']} |")
        lines += ["", "### Sections", ""]
        for s in book["sections"]:
            if s["depth"] > 2:
                continue
            lines.append(f"{'  ' * s['depth']}- {s['title']} — p{s['page']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {path.name}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
