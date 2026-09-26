"""No module-level name is silently defined twice.

Measured 2026-09-25: a second `_AIMED_AT` (who an insult is spoken at) was added 3,800
lines below the first (an attack's victim) in gm/judgement.py. Python took the later one
for the whole module, and four misaimed-attack repairs broke with a `TypeError` in code
nobody had touched. In a file this long a name collision is invisible to the eye and
obvious to the AST.

A rebinding that READS the old value — `SITUATIONS = tuple(... for s in SITUATIONS ...)`
in play/opening.py — builds on it and is allowed.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _rebound_blind(tree) -> list[str]:
    seen: set[str] = set()
    out = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.value is not None:
            names, value = [node.target.id], node.value
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names, value = [node.name], None
        else:
            continue
        reads = {n.id for n in ast.walk(value) if isinstance(n, ast.Name)} if value else set()
        for name in names:
            if name in seen and name not in reads:
                out.append(f"{name} (line {node.lineno})")
            seen.add(name)
    return out


def test_no_module_level_name_is_silently_redefined():
    problems = []
    for folder in ("gm", "rules", "play", "world"):
        for path in sorted(Path(folder).glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for hit in _rebound_blind(tree):
                problems.append(f"{path}: {hit}")
    assert not problems, "defined twice, the first silently lost:\n" + "\n".join(problems)
