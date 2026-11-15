"""Inventory every place the front end turns a string into markup, and what goes into it.

The front end (play/static/js/**, and the inline <script> blocks of play/templates/play/*)
builds its pages as strings and hands them to `innerHTML`. Three kinds of text reach those
strings, and none of them is ours: what a model writes (narration, NPC names and speech,
item names it proposes), what a World Bible export carries (any string in a world file),
and what the player types or puts in homebrew. On a LAN game one player's typing is drawn
on another player's screen. An `<img src=x onerror=...>` that reaches a sink unescaped runs
as the app.

Mechanical on purpose (CLAUDE.md: detect mechanically). It tokenizes the JavaScript
(strings, templates with nested `${}`, regex literals, comments, brackets) and finds:

  sinks      `.innerHTML =` / `+=`, `.outerHTML =`, `.srcdoc =`, `insertAdjacentHTML(p, x)`,
             `document.write(x)`, `createContextualFragment(x)`, `parseFromString(x, ..)`;
  builders   every template literal or `+` chain with markup in its literal text, wherever
             it sits: most HTML is built in one function and sunk in another.

Each value interpolated into a builder, and each sink's right-hand side, is reduced to its
leaves (a ternary's two arms, both sides of `||`/`??`, the last of `&&`, every `+` operand),
and each leaf is classed:

  escaped    an escape call: `esc(x)`, `B.esc(x)`, `xs.map(esc)`
  literal    a string/number literal, true/false/null/undefined, `!x`, `typeof x`
  numeric    arithmetic or a comparison, `.length`, `.toFixed()`, `Math.*`, `Number()`
  composed   holds a markup template of its own, whose holes are classed where they are
  built      a call to a function whose every return is safe, a variable whose every
             assignment is safe, or a parameter every call site fills safely (resolved by
             name across the corpus, to a fixpoint)
  reviewed   a person read it and named why no outside text can be in it
             (`tools/html_sinks_reviewed.json`)
  leaf       anything else: unescaped, unexplained, a failure

shortcut: resolution is by name, not by binding (two functions called `row` are one), and
the scanner is not a parser: an ASI-split statement can end a right-hand side early, and a
`composed` leaf is trusted whole. Upgrade to a real parser (acorn under node) if one of
those ever hides a sink.

Run:  python tools/html_sinks.py            totals + every unreviewed leaf (exit 1 if any)
      python tools/html_sinks.py --all      every leaf with its class
      python tools/html_sinks.py --json F   the full inventory as JSON
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS_DIR = ROOT / "play" / "static" / "js"
TEMPLATES = ROOT / "play" / "templates" / "play"
REVIEWED = Path(__file__).resolve().parent / "html_sinks_reviewed.json"

KEYWORDS_BEFORE_REGEX = {"return", "typeof", "case", "in", "of", "new", "delete", "void",
                         "throw", "else", "do", "yield", "await", "instanceof"}
CHAIN_BREAKERS = {"return", "const", "let", "var", "if", "else", "for", "while", "case",
                  "throw", "yield", "in", "of", "instanceof", "function", "do", "switch",
                  "default", "break", "continue"}
PREFIX = {"!", "-", "+", "~", "new", "typeof", "await", "void", "delete", "..."}
ESC_NAME = re.compile(r"^(esc|escHtml|escape|escapeHtml|escAttr|escHTML)$")
HTMLISH = re.compile(r"<[a-zA-Z/!]|[\w-]=[\"']$")
# String methods whose result is as safe as the string they were called on.
PASS_THROUGH = {"toUpperCase", "toLowerCase", "trim", "trimStart", "trimEnd", "slice",
                "substring", "substr", "charAt", "padStart", "padEnd", "repeat", "toString",
                "concat", "at", "normalize", "filter", "sort", "reverse", "flat", "concat"}
PUNCT3 = ("===", "!==", "...", "**=", "<<=", ">>=", ">>>", "&&=", "||=", "??=")
PUNCT2 = ("=>", "==", "!=", "<=", ">=", "&&", "||", "??", "?.", "++", "--", "+=", "-=",
          "*=", "/=", "%=", "&=", "|=", "^=", "**", "<<", ">>")
SELECTOR_FNS = ("querySelector", "querySelectorAll", "closest", "matches", "getElementById",
                "$", "$$", "sel", "qs", "qsa")
ARRAY_METHODS = ("map", "forEach", "flatMap", "filter", "some", "every", "find", "findIndex")
# Methods whose result is a boolean or a number whatever they were called on.
BOOL_OR_NUM = ("includes", "has", "some", "every", "startsWith", "endsWith", "test", "indexOf",
               "lastIndexOf", "findIndex", "localeCompare", "isArray", "isFinite", "isInteger",
               "contains", "hasAttribute", "matches")
SAFE = {"escaped", "literal", "numeric", "composed", "built", "reviewed"}


@dataclass
class Tok:
    kind: str            # id num str tpl regex punct
    start: int
    end: int
    text: str
    line: int
    quasis: list = field(default_factory=list)
    holes: list = field(default_factory=list)


@dataclass
class Group:
    open: Tok
    items: list
    close: Tok | None
    kind = "group"

    @property
    def start(self):
        return self.open.start

    @property
    def end(self):
        return self.close.end if self.close else self.open.end

    @property
    def text(self):
        return self.open.text

    @property
    def line(self):
        return self.open.line


def is_p(x, *texts) -> bool:
    return x is not None and not isinstance(x, Group) and x.kind == "punct" and (not texts or x.text in texts)


def is_id(x, *texts) -> bool:
    return x is not None and not isinstance(x, Group) and x.kind == "id" and (not texts or x.text in texts)


def is_g(x, opener=None) -> bool:
    return isinstance(x, Group) and (opener is None or x.open.text == opener)


# --- tokenizer ------------------------------------------------------------------------------

class Scanner:
    def __init__(self, src: str, starts: list[int], end: int):
        self.s, self.starts, self.n, self.i = src, starts, end, 0

    def line_of(self, off: int) -> int:
        lo, hi = 0, len(self.starts)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.starts[mid] <= off:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def tokens(self, in_hole=False):
        s, out, depth = self.s, [], 0
        while self.i < self.n:
            c = s[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif s.startswith("//", self.i):
                nl = s.find("\n", self.i)
                self.i = self.n if nl < 0 else nl
            elif s.startswith("/*", self.i):
                e = s.find("*/", self.i + 2)
                self.i = self.n if e < 0 else e + 2
            elif s.startswith("<!--", self.i) or s.startswith("-->", self.i):
                self.i += 3 if s[self.i] == "-" else 4
            elif c in "\"'":
                out.append(self._string(c))
            elif c == "`":
                out.append(self._template())
            elif c.isdigit() or (c == "." and s[self.i + 1:self.i + 2].isdigit()):
                out.append(self._tok("num", re.compile(r"[0-9a-fA-FxXoObBn_.]+(e[-+]?\d+)?")
                                     .match(s, self.i).end()))
            elif c.isalpha() or c in "_$":
                out.append(self._tok("id", re.compile(r"[\w$]+").match(s, self.i).end()))
            elif c == "/" and self._regex_ok(out):
                out.append(self._regex())
            else:
                if in_hole and c == "{":
                    depth += 1
                elif in_hole and c == "}":
                    if depth == 0:
                        self.i += 1
                        return out
                    depth -= 1
                for p in PUNCT3 + PUNCT2:
                    if s.startswith(p, self.i):
                        out.append(self._tok("punct", self.i + len(p)))
                        break
                else:
                    out.append(self._tok("punct", self.i + 1))
        return out

    def _tok(self, kind, end):
        t = Tok(kind, self.i, end, self.s[self.i:end], self.line_of(self.i))
        self.i = end
        return t

    @staticmethod
    def _regex_ok(out):
        if not out:
            return True
        p = out[-1]
        if p.kind == "punct":
            return p.text not in (")", "]", "}", "++", "--")
        return p.kind == "id" and p.text in KEYWORDS_BEFORE_REGEX

    def _string(self, q):
        s, j = self.s, self.i + 1
        while j < self.n and s[j] != q and s[j] != "\n":
            j += 2 if s[j] == "\\" else 1
        t = Tok("str", self.i, j + 1, s[self.i:j + 1], self.line_of(self.i))
        self.i = j + 1
        return t

    def _regex(self):
        s, j, cls = self.s, self.i + 1, False
        while j < self.n and s[j] != "\n":
            ch = s[j]
            if ch == "\\":
                j += 2
                continue
            if ch == "[":
                cls = True
            elif ch == "]":
                cls = False
            elif ch == "/" and not cls:
                break
            j += 1
        j += 1
        while j < self.n and s[j].isalpha():
            j += 1
        t = Tok("regex", self.i, j, s[self.i:j], self.line_of(self.i))
        self.i = j
        return t

    def _template(self):
        s, start = self.s, self.i
        t = Tok("tpl", start, start, "", self.line_of(start))
        j, piece = self.i + 1, []
        while j < self.n:
            ch = s[j]
            if ch == "\\":
                piece.append(s[j:j + 2])
                j += 2
            elif ch == "`":
                j += 1
                break
            elif s.startswith("${", j):
                t.quasis.append("".join(piece))
                piece = []
                self.i = j + 2
                t.holes.append(group(self.tokens(in_hole=True)))
                j = self.i
            else:
                piece.append(ch)
                j += 1
        t.quasis.append("".join(piece))
        self.i, t.end, t.text = j, j, s[start:j]
        return t


def group(toks):
    """Nest brackets so each level reads as one flat list of operands and operators."""
    stack, opens = [[]], []
    for t in toks:
        if t.kind == "punct" and t.text in "([{":
            opens.append(t)
            stack.append([])
        elif t.kind == "punct" and t.text in ")]}" and opens:
            items = stack.pop()
            stack[-1].append(Group(opens.pop(), items, t))
        else:
            stack[-1].append(t)
    while opens:  # unbalanced: close what is left
        items = stack.pop()
        stack[-1].append(Group(opens.pop(), items, None))
    return stack[0]


def markupish(q: str) -> bool:
    """Literal text that is markup: a tag, or an attribute about to take a value. An
    attribute *selector* (`[data-slot="`) is not: escaping a value into a selector breaks
    the selector and protects nothing."""
    if re.search(r"<[a-zA-Z/!]", q):
        return True
    return bool(HTMLISH.search(q)) and not re.search(r"\[[\w-]+[~|^$*]?=[\"']?$", q)


def is_html_tpl(t) -> bool:
    return not isinstance(t, Group) and t.kind == "tpl" and any(markupish(q) for q in t.quasis)


def is_html_str(t) -> bool:
    return not isinstance(t, Group) and t.kind == "str" and markupish(t.text[1:-1])


def walk(items):
    for it in items:
        yield it
        if isinstance(it, Group):
            yield from walk(it.items)
        elif it.kind == "tpl":
            for h in it.holes:
                yield from walk(h)


def contains_html(items) -> bool:
    return any(is_html_tpl(x) or is_html_str(x) for x in walk(items))


def is_operand(it) -> bool:
    if isinstance(it, Group):
        return True
    if it.kind == "id":
        return it.text not in CHAIN_BREAKERS
    return it.kind in ("num", "str", "tpl", "regex")


def split_top(items, ops):
    parts, cur = [], []
    for it in items:
        if is_p(it, *ops):
            parts.append(cur)
            cur = []
        else:
            cur.append(it)
    parts.append(cur)
    return parts


def last_line(it):
    if isinstance(it, Group):
        return it.close.line if it.close else it.open.line
    return it.line + it.text.count("\n")


def expr_until_end(items, k):
    """One expression starting at items[k]: up to `;`, `,` or an ASI line break."""
    out, prev = [], None
    for it in items[k:]:
        if is_p(it, ";", ","):
            break
        if prev is not None and it.line > last_line(prev) and is_operand(prev) \
                and is_operand(it) and not is_g(it, "(") and not is_g(it, "["):
            break
        out.append(it)
        prev = it
    return out


# --- what the corpus defines ----------------------------------------------------------------

@dataclass
class Fn:
    name: str | None
    params: list[str]
    start: int
    end: int
    returns: list = field(default_factory=list)   # item lists
    file: str = ""
    array_cb: bool = False                        # xs.map((x, i) => ...): i is an index


@dataclass
class Site:
    file: str
    line: int
    site: str        # sink | builder
    sink: str        # innerHTML ... | template | concat
    items: list
    offset: int
    cls: str = ""
    text: str = ""
    why: str = ""


class Corpus:
    def __init__(self):
        self.fns: dict[str, list[Fn]] = {}
        self.all_fns: list[Fn] = []
        self.vars: dict[tuple[str, str], list] = {}      # (file, name) -> [(items, offset)]
        self.calls: dict[str, list] = {}                 # name -> [(file, offset, args)]
        self.passed_at: dict[str, list] = {}             # name -> [(file, offset)] used as a value
        self.sites: list[Site] = []
        self.srcs: dict[str, str] = {}
        self.sinks = self.builders = self.raw = 0
        self.reviewed = load_reviewed()
        self._memo: dict = {}
        self._scopes: dict = {}
        self.hits: set = set()
        self.esc_alias: dict = {}
        self._by_file: dict = {}

    # -- collection --
    def add_file(self, rel, src, spans):
        self.srcs[rel] = src
        starts = [0] + [m.end() for m in re.finditer("\n", src)]
        self.raw += sum(len(re.findall(r"innerHTML|insertAdjacentHTML|outerHTML", src[a:b]))
                        for a, b in spans)
        for a, b in spans:
            sc = Scanner(src, starts, b)
            sc.i = a
            self.visit(rel, group(sc.tokens()))

    def params_of(self, g):
        if not isinstance(g, Group):
            return [g.text] if is_id(g) else []
        names = []
        for part in split_top(g.items, (",",)):
            if part and is_id(part[0]):
                names.append(part[0].text)
            else:
                names.append("")      # destructured: not traced
        return names

    def visit(self, rel, level, selector=False, array_cb=False):
        self._array_cb = array_cb
        n = len(level)
        for k, it in enumerate(level):
            prev = level[k - 1] if k else None
            nxt = level[k + 1] if k + 1 < n else None
            # function NAME (params) { body }
            if is_id(it, "function") and k + 2 < n:
                j = k + 1
                name = None
                if is_id(level[j]):
                    name, j = level[j].text, j + 1
                elif k >= 2 and is_p(level[k - 1], "=", ":") and is_id(level[k - 2]):
                    name = level[k - 2].text
                elif k >= 2 and is_p(level[k - 1], "=", ":") and not isinstance(level[k - 2], Group) \
                        and level[k - 2].kind == "str":
                    name = level[k - 2].text[1:-1]
                if j + 1 < n and is_g(level[j], "(") and is_g(level[j + 1], "{"):
                    self.add_fn(rel, name, self.params_of(level[j]), level[j + 1], None)
            # method shorthand: NAME (params) { body } inside an object / class
            elif is_id(it) and is_g(nxt, "(") and k + 2 < n and is_g(level[k + 2], "{") \
                    and (prev is None or is_p(prev, ",", "{", ";", "}")) \
                    and it.text not in CHAIN_BREAKERS and it.text not in ("catch",):
                self.add_fn(rel, it.text, self.params_of(nxt), level[k + 2], None)
            # (params) => body   /   x => body
            elif is_p(it, "=>") and prev is not None:
                name = None
                b = k - 2
                if b >= 1 and is_p(level[b], "=", ":") and is_id(level[b - 1]):
                    name = level[b - 1].text
                elif b >= 1 and is_p(level[b], "=", ":") and not isinstance(level[b - 1], Group) \
                        and level[b - 1].kind == "str":
                    name = level[b - 1].text[1:-1]
                if is_g(nxt, "{"):
                    self.add_fn(rel, name, self.params_of(prev), nxt, None)
                elif nxt is not None:
                    body = expr_until_end(level, k + 1)
                    self.add_fn(rel, name, self.params_of(prev), None, body)
            # NAME = value, NAME += value (not a member, not a declaration of a function)
            if is_id(it) and is_p(nxt, "=", "+=", "||=", "??=") and not is_p(prev, ".", "?.") \
                    and it.text not in CHAIN_BREAKERS:
                rhs = expr_until_end(level, k + 2)
                if rhs and not is_id(rhs[0], "function") and not any(is_p(x, "=>") for x in rhs):
                    self.vars.setdefault((rel, it.text), []).append((rhs, it.start))
            # calls: NAME(args) and X.NAME(args)
            if is_id(it) and is_g(nxt, "(") and not is_id(prev, "function"):
                args = split_top(nxt.items, (",",)) if nxt.items else []
                self.calls.setdefault(it.text, []).append((rel, it.start, args))
            # a name passed as a value: xs.map(row), cb = row
            if is_id(it) and not is_g(nxt, "(") and not is_p(prev, ".", "?.") \
                    and (is_p(prev, "(", ",") or prev is None or is_g(prev)) and \
                    (nxt is None or is_p(nxt, ",", ")")):
                self.passed_at.setdefault(it.text, []).append((rel, it.start))
        if not selector:
            self.find_builders(rel, level)
        self.find_sinks(rel, level)
        for k, it in enumerate(level):
            if isinstance(it, Group):
                if it.open.text == "(":
                    # `xs.map(row)`: a bare name as a whole call argument
                    for part in split_top(it.items, (",",)):
                        if len(part) == 1 and is_id(part[0]):
                            self.passed_at.setdefault(part[0].text, []).append((rel, part[0].start))
                # A CSS selector built with `[data-x="${v}"]` is not markup.
                self.visit(rel, it.items, selector=k > 0 and is_id(level[k - 1], *SELECTOR_FNS),
                           array_cb=self.array_cb_kind(level, k))
                self._array_cb = False
            elif it.kind == "tpl":
                for h in it.holes:
                    self.visit(rel, h)

    @staticmethod
    def array_cb_kind(level, k):
        """`xs.map(cb)`: True. `["str", "dex"].map(cb)`: "literal", its element is ours."""
        if not (k > 0 and is_id(level[k - 1], *ARRAY_METHODS)):
            return False
        if k >= 3 and is_p(level[k - 2], ".") and is_g(level[k - 3], "[") and all(
                is_p(x, ",", "-") or (not isinstance(x, Group) and x.kind in ("str", "num"))
                for x in level[k - 3].items):
            return "literal"
        return True

    def add_fn(self, rel, name, params, body_group, expr):
        cb = getattr(self, "_array_cb", False)
        if body_group is not None:
            fn = Fn(name, params, body_group.start, body_group.end, file=rel, array_cb=cb)
            self.collect_returns(fn, body_group.items)
        else:
            if not expr:
                return
            fn = Fn(name, params, expr[0].start, expr[-1].end, [expr], file=rel, array_cb=cb)
        self.all_fns.append(fn)
        if name:
            self.fns.setdefault(name, []).append(fn)

    def collect_returns(self, fn, items):
        for k, it in enumerate(items):
            if is_id(it, "return"):
                e = expr_until_end(items, k + 1)
                if e:
                    fn.returns.append(e)
            elif is_g(it, "{") and not (k and (is_p(items[k - 1], "=>") or
                                               (k >= 2 and is_g(items[k - 1], "(") and
                                                (is_id(items[k - 2], "function") or
                                                 (k >= 3 and is_id(items[k - 3], "function")))))):
                self.collect_returns(fn, it.items)   # if/for blocks, not inner functions

    def add_site(self, rel, site, sink, items):
        if items:
            self.sites.append(Site(rel, items[0].line, site, sink, items, items[0].start))

    def find_builders(self, rel, level):
        for it in level:
            if is_html_tpl(it):
                self.builders += 1
                for h in it.holes:
                    self.add_site(rel, "builder", "template", h)
        # `+` chains with a markup string literal among their operands.
        ops, cur, want_op = [], [], False

        def close():
            nonlocal ops
            if len(ops) > 1 and any(len(o) == 1 and is_html_str(o[0]) for o in ops):
                self.builders += 1
                for o in ops:
                    if not (len(o) == 1 and not isinstance(o[0], Group) and o[0].kind in ("str", "tpl")):
                        self.add_site(rel, "builder", "concat", o)
            ops = []

        for it in level:
            if want_op and is_p(it, "+"):
                ops.append(cur)
                cur, want_op = [], False
                continue
            if not want_op:
                if (is_p(it) or is_id(it)) and it.text in PREFIX:
                    cur.append(it)
                    continue
                if is_operand(it):
                    cur.append(it)
                    want_op = True
                    continue
            else:
                if is_p(it, ".", "?.") or is_g(it, "(") or is_g(it, "[") or \
                        (is_id(it) and cur and is_p(cur[-1], ".", "?.")) or \
                        (not isinstance(it, Group) and it.kind == "tpl" and cur and is_id(cur[-1])):
                    cur.append(it)
                    continue
            # the chain ends here
            if cur and want_op:
                ops.append(cur)
            close()
            cur, want_op = [], False
            if is_operand(it):
                cur, want_op = [it], True
        if cur and want_op:
            ops.append(cur)
        close()

    def find_sinks(self, rel, level):
        n = len(level)
        for k, it in enumerate(level):
            if not is_id(it):
                continue
            prev = level[k - 1] if k else None
            nxt = level[k + 1] if k + 1 < n else None
            if not is_p(prev, ".", "?."):
                continue
            if it.text in ("innerHTML", "outerHTML", "srcdoc") and is_p(nxt, "=", "+="):
                self.sinks += 1
                self.add_site(rel, "sink", it.text, expr_until_end(level, k + 2))
            elif it.text in ("insertAdjacentHTML", "write", "writeln", "createContextualFragment",
                             "parseFromString") and is_g(nxt, "("):
                if it.text in ("write", "writeln") and not (k >= 2 and is_id(level[k - 2], "document")):
                    continue
                self.sinks += 1
                args = split_top(nxt.items, (",",))
                arg = args[1] if it.text == "insertAdjacentHTML" and len(args) > 1 else args[0]
                self.add_site(rel, "sink", it.text, arg)

    # -- resolution --
    def scope_at(self, rel, offset):
        """The functions enclosing `offset`, outermost first."""
        key = (rel, offset)
        if key not in self._scopes:
            if rel not in self._by_file:
                self._by_file[rel] = sorted((f for f in self.all_fns if f.file == rel),
                                            key=lambda f: (f.start, -f.end))
            self._scopes[key] = [f for f in self._by_file[rel] if f.start <= offset < f.end]
        return self._scopes[key]

    def text(self, rel, items):
        if not items:
            return ""
        return " ".join(self.srcs[rel][items[0].start:items[-1].end].split())

    def classify(self, rel, items, depth=0):
        """[(class, items, why)] for everything `items` can put on the page."""
        if not items:
            return []
        why = self.review_of(rel, items)
        if why:
            return [("reviewed", items, why)]
        if len(items) == 1 and is_g(items[0], "("):
            return self.classify(rel, items[0].items, depth)
        for ops in ((",",), ("=>",)):
            parts = split_top(items, ops)
            if len(parts) > 1:
                return self.classify(rel, parts[-1], depth)
        q = [i for i, x in enumerate(items) if is_p(x, "?")]
        if q:
            rest, d = items[q[0] + 1:], 0
            for k, x in enumerate(rest):
                if is_p(x, "?"):
                    d += 1
                elif is_p(x, ":"):
                    if d == 0:
                        return self.classify(rel, rest[:k], depth) + self.classify(rel, rest[k + 1:], depth)
                    d -= 1
        for ops in (("||", "??"),):
            parts = split_top(items, ops)
            if len(parts) > 1:
                return [x for p in parts for x in self.classify(rel, p, depth)]
        parts = split_top(items, ("&&",))
        if len(parts) > 1:
            return self.classify(rel, parts[-1], depth)
        parts = split_top(items, ("+",))
        if len(parts) > 1 and all(parts):
            # `a + 1` is addition, not a join: only a chain with a string in it concatenates.
            if any(len(p) == 1 and not isinstance(p[0], Group) and p[0].kind in ("str", "tpl")
                   for p in parts):
                return [x for p in parts for x in self.classify(rel, p, depth)]
            if any(len(p) == 1 and not isinstance(p[0], Group) and p[0].kind == "num" for p in parts):
                return [("numeric", items, "")]
            # `a + b`: safe if both are; otherwise one leaf, so a fix wraps the sum whole.
            if all(self.all_safe(rel, p, depth)[0] for p in parts):
                return [("built", items, "sum of safe parts")]
            return [("leaf", items, "a + b")]
        if len(items) == 1 and not isinstance(items[0], Group) and items[0].kind == "tpl" \
                and not is_html_tpl(items[0]):
            # A plain template inside markup is markup too: its holes are what reach the page.
            return [x for h in items[0].holes for x in self.classify(rel, h, depth)]
        cls, why = self.operand(rel, items, depth)
        return [(cls, items, why)]

    def review_of(self, rel, items):
        rv = self.reviewed.get(rel, {})
        if not rv or not items:
            return ""
        flat = self.text(rel, items)
        names = [f.name for f in self.scope_at(rel, items[0].start) if f.name]
        for key in [f"{names[-1] if names else 'top'}::{flat}", flat]:
            if key in rv:
                self.hits.add((rel, key))
                return rv[key]
        return ""

    def all_safe(self, rel, items, depth):
        bad = [(c, i, w) for c, i, w in self.classify(rel, items, depth) if c not in SAFE]
        return not bad, bad

    def operand(self, rel, items, depth):
        flat = self.text(rel, items)
        why = self.review_of(rel, items)
        if why:
            return "reviewed", why
        if len(items) == 1:
            x = items[0]
            if is_g(x, "("):
                bad = [c for c, _, _ in self.classify(rel, x.items, depth) if c not in SAFE]
                return ("leaf", "") if bad else ("built", "")
            if is_g(x, "["):
                return ("built", "") if self.all_safe(rel, x.items, depth)[0] else ("leaf", "")
            if not isinstance(x, Group):
                if x.kind in ("str", "num", "regex"):
                    return "literal", ""
                if x.kind == "tpl":
                    return "composed", ""
                if x.kind == "id" and x.text in ("true", "false", "null", "undefined", "NaN"):
                    return "literal", ""
        toks = [x for x in items if not isinstance(x, Group)]
        if len(items) > 1 and any(is_p(x, "-", "*", "/", "%", "**", "<", ">", "<=", ">=", "===",
                                       "!==", "==", "!=") for x in toks):
            return "numeric", ""
        if is_p(items[0], "!") or is_id(items[0], "typeof"):
            return "literal", ""
        if re.search(r"\.map\((\w+\.)*(esc|escHtml|escape|escapeHtml)\)", flat):
            return "escaped", ""
        last = items[-1]
        if is_g(last, "(") and len(items) >= 2 and is_id(items[-2]) and (
                ESC_NAME.match(items[-2].text) or items[-2].text in self.esc_alias.get(rel, ())):
            return "escaped", ""
        if len(items) >= 3 and is_g(items[-1], "(") and is_id(items[-2], *BOOL_OR_NUM) \
                and is_p(items[-3], ".", "?."):
            return "numeric", ""
        if re.search(r"(\.length|\.size|\.toFixed\([^()]*\)|\.toLocaleString\([^()]*\))$", flat) \
                or re.match(r"^(Math\.\w+|Number|parseInt|parseFloat|Math\.round)\s*\(", flat) \
                or re.match(r"^-?\d", flat):
            return "numeric", ""
        if contains_html(items):
            return "composed", ""
        if flat.endswith(".outerHTML"):
            return "built", "a DOM node serialized: the browser escapes its text"
        if depth > 12:
            return "leaf", "too deep"
        return self.resolve(rel, items, depth + 1)

    def resolve(self, rel, items, depth):
        """A name, a call, a `.map(...).join(...)`: follow it to its definitions."""
        # Strip a trailing `.join(x)` and pass-through string methods.
        while len(items) >= 3 and is_g(items[-1], "(") and is_id(items[-2]) and is_p(items[-3], ".", "?."):
            meth = items[-2].text
            args = items[-1].items
            # `.replace(/[^A-Za-z0-9_-]/g, "_")`: whatever it was, it is that class now.
            if meth == "replace" and args and not isinstance(args[0], Group) \
                    and args[0].kind == "regex" and re.match(r"/\[\^[\w\\-]*\]\+?/g", args[0].text):
                return "built", "reduced to a safe character class"
            if meth == "join" or meth in PASS_THROUGH:
                items = items[:-3]
                continue
            if meth in ("map", "flatMap"):
                cb = items[-1].items
                ok = self.callback_safe(rel, cb, depth)
                return ("built", "map callback") if ok else ("leaf", "map callback")
            break
        if not items:
            return "leaf", ""
        if len(items) == 1 and is_id(items[0]):
            return self.name_safe(rel, items[0].text, items[0].start, depth)
        if len(items) == 1 and isinstance(items[0], Group):
            return self.operand(rel, items, depth)
        # a call: NAME(...) or X.NAME(...)
        if is_g(items[-1], "(") and len(items) >= 2 and is_id(items[-2]):
            name = items[-2].text
            if name in ("String",) and len(items) == 2:
                args = split_top(items[-1].items, (",",))
                return ("built", "") if self.all_safe(rel, args[0], depth)[0] else ("leaf", "")
            if self.fn_safe(name, depth, rel):
                return "built", f"fn {name}"
            return "leaf", f"fn {name} unresolved" if name in self.fns else ""
        return "leaf", ""

    def callback_safe(self, rel, cb_items, depth):
        if len(cb_items) == 1 and is_id(cb_items[0]):
            return self.fn_safe(cb_items[0].text, depth, rel)
        # an inline arrow or function: its returns
        for f in self.all_fns:
            if f.file == rel and cb_items and f.start >= cb_items[0].start and f.end <= cb_items[-1].end:
                return all(self.all_safe(rel, r, depth)[0] for r in f.returns) if f.returns else False
        return False

    def fn_safe(self, name, depth, rel=None):
        """Every definition of NAME the call could mean returns something safe. A file's own
        definition shadows the others (a bench's local `sign` is not the table's)."""
        defs = self.fns.get(name)
        if not defs:
            return False
        own = [f for f in defs if f.file == rel]
        defs = own or defs
        key = ("fn", name, rel if own else None)
        if key in self._memo:
            return self._memo[key]
        for f in defs:
            if f"fn:{name}" in self.reviewed.get(f.file, {}):
                self.hits.add((f.file, f"fn:{name}"))
                return True
        self._memo[key] = True          # optimistic while recursing
        # A function that returns nothing prints "undefined": wrong, but not markup.
        ok = all(all(self.all_safe(f.file, r, depth)[0] for r in f.returns) for f in defs)
        self._memo[key] = ok
        return ok

    def name_safe(self, rel, name, offset, depth):
        scope = self.scope_at(rel, offset)
        for f in reversed(scope):
            if name in f.params:
                if f"param:{f.name}.{name}" in self.reviewed.get(rel, {}):
                    self.hits.add((rel, f"param:{f.name}.{name}"))
                    return "reviewed", self.reviewed[rel][f"param:{f.name}.{name}"]
                return self.param_safe(f, f.params.index(name), depth)
        vals = self.vars.get((rel, name))
        if vals:
            # The assignments in the innermost function (of those enclosing the use) that
            # assigns NAME at all: two functions' `rows` are two variables.
            def inner(off):
                fs = self.scope_at(rel, off)
                return fs[-1].start if fs else -1
            levels = [-1] + [f.start for f in scope]
            for lv in reversed(levels):
                here = [(r, o) for r, o in vals if inner(o) == lv]
                if here:
                    vals = here
                    break
            else:
                vals = vals
            files = [rel] * len(vals)
            key = ("var", rel, name, vals[0][1])
        else:
            # a global from another classic script (the table's files share one scope)
            pairs = [(v, f) for (f, nm), vs in self.vars.items() if nm == name and f != rel
                     for v in vs if not self.scope_at(f, v[1])]
            if not pairs:
                return "leaf", "no assignment found"
            vals, files = [p[0] for p in pairs], [p[1] for p in pairs]
            key = ("var", "*", name)
        if key in self._memo:
            return ("built", "var") if self._memo[key] else ("leaf", "var")
        self._memo[key] = True          # an accumulator refers to itself
        ok = all(self.all_safe(f, rhs, depth)[0] for (rhs, _), f in zip(vals, files))
        self._memo[key] = ok
        return ("built", "var") if ok else ("leaf", "var")

    def param_safe(self, fn, idx, depth):
        if fn.array_cb and idx == 1:
            return "numeric", "array index"
        if fn.array_cb == "literal" and idx == 0:
            return "literal", "element of a literal array"
        # A function nested in another is called only from inside that one: its calls, and
        # any passing of it as a value, are looked for there and nowhere else.
        outer = [f for f in self.scope_at(fn.file, fn.start) if f is not fn]
        span = (fn.file, outer[-1].start, outer[-1].end) if outer else None
        inside = lambda rel, off: span is None or (rel == span[0] and span[1] <= off < span[2])
        if not fn.name or any(inside(r, o) for r, o in self.passed_at.get(fn.name, ())):
            return "leaf", f"param {idx} of {'callback' if not fn.name else fn.name}"
        key = ("param", fn.file, fn.start, idx)
        if key in self._memo:
            return ("built", "") if self._memo[key] else ("leaf", "")
        self._memo[key] = True
        ok = True
        for crel, off, args in self.calls.get(fn.name, []):
            if not inside(crel, off):
                continue
            if idx < len(args) and args[idx]:
                if not self.all_safe(crel, args[idx], depth)[0]:
                    ok = False
                    break
        self._memo[key] = ok
        return ("built", f"param of {fn.name}") if ok else ("leaf", f"param {idx} of {fn.name}")

    def find_esc_aliases(self):
        """A file's own name for the escaper: `const e = s => String(s).replace(/[&<>"]/g, ..)`
        or `var esc = C.esc`. A call to it is an escape like any other."""
        self.esc_alias = {}
        for (rel, name), vals in self.vars.items():
            for rhs, _ in vals:
                t = self.text(rel, rhs)
                if re.fullmatch(r"(\w+\.)?(esc|escHtml|escape)", t):
                    self.esc_alias.setdefault(rel, set()).add(name)
        for fn in self.all_fns:
            if fn.name and fn.returns and all("&lt;" in self.text(fn.file, r) or "&lt;" in
                                              self.srcs[fn.file][fn.start:fn.end] for r in fn.returns):
                self.esc_alias.setdefault(fn.file, set()).add(fn.name)

    def finish(self):
        self.find_esc_aliases()
        for s in self.sites:
            s.text = self.text(s.file, s.items)
        out = []
        for s in self.sites:
            for cls, its, why in self.classify(s.file, s.items):
                if cls == "literal":
                    continue
                line = its[0].line if its else s.line
                out.append(Site(s.file, line, s.site, s.sink, its, its[0].start if its else 0,
                                cls, self.text(s.file, its), why))
        return out


def load_reviewed():
    if not REVIEWED.exists():
        return {}
    data = json.loads(REVIEWED.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def sources():
    for p in sorted(JS_DIR.rglob("*.js")):
        s = p.read_text(encoding="utf-8")
        yield p, s, [(0, len(s))]
    for p in sorted(TEMPLATES.glob("*.html")):
        html = p.read_text(encoding="utf-8")
        spans = [(m.start(1), m.end(1)) for m in
                 re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)]
        if spans:
            yield p, html, spans


def inventory():
    c = Corpus()
    for path, src, spans in sources():
        c.add_file(path.relative_to(ROOT).as_posix(), src, spans)
    leaves = c.finish()
    stale = [(f, k) for f, d in c.reviewed.items() for k in d if (f, k) not in c.hits]
    return {"sinks": c.sinks, "builders": c.builders, "raw_mentions": c.raw,
            "leaves": leaves, "stale": stale}


def counts(inv):
    out = {}
    for l in inv["leaves"]:
        out[l.cls] = out.get(l.cls, 0) + 1
    return out


def main(argv):
    inv = inventory()
    print(f"sink sites: {inv['sinks']}   markup builders: {inv['builders']}   "
          f"raw innerHTML/insertAdjacentHTML/outerHTML mentions: {inv['raw_mentions']}")
    print("interpolated values: " + ", ".join(f"{k} {v}" for k, v in sorted(counts(inv).items())))
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps(
            {"sinks": inv["sinks"], "builders": inv["builders"], "raw_mentions": inv["raw_mentions"],
             "leaves": [{k: getattr(l, k) for k in ("file", "line", "site", "sink", "cls", "text", "why")}
                        for l in inv["leaves"]]}, indent=1), encoding="utf-8")
    show = inv["leaves"] if "--all" in argv else [l for l in inv["leaves"] if l.cls == "leaf"]
    for l in show:
        why = f"  ({l.why})" if l.why else ""
        print(f"{l.file}:{l.line}: {l.cls:9} {l.site}/{l.sink}: {l.text[:150]}{why}")
    for f, t in inv["stale"]:
        print(f"STALE review (matches nothing now): {f}: {t}")
    return 1 if any(l.cls == "leaf" for l in inv["leaves"]) or inv["stale"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
