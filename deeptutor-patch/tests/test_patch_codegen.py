"""Local guard for patch.py's GENERATED code — NO /app, NO engine, NO deps.

`py_compile patch.py` only proves the patch SCRIPT parses; it does NOT prove the
code patch.py injects into upstream files is valid Python. This test closes that
gap for the turn_runtime edits: it safely extracts the replacement string blocks
from patch.py via `ast` (parse only — patch.py is never executed, so its /app file
I/O never runs), wraps each at its real indentation, and compile()s it. A syntax /
indentation error in an injected block fails here, locally.

Runnable with plain pytest:
    pytest deeptutor-patch/tests/test_patch_codegen.py -v
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_PATCH = pathlib.Path(__file__).resolve().parents[1] / "patch.py"


def _extract_str_consts(names: set[str]) -> dict[str, str]:
    """Return {assigned_name: string value} for top-level `NAME = <str literal>`
    assignments in patch.py. Adjacent/implicit-concatenated and triple-quoted
    literals fold to one ast.Constant at parse time, so literal_eval handles them."""
    tree = ast.parse(_PATCH.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in names:
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                continue
            if isinstance(value, str):
                found[target.id] = value
    return found


_BLOCKS = _extract_str_consts({"P3_TAIL_METHOD", "RUN_SETUP_NEW", "RUN_FIN_NEW"})

# Each block lives at a specific spot in turn_runtime; wrap it so it compiles in
# the SAME structural/indentation context patch.py injects it into.
_SCAFFOLDS = {
    # A full method at class-body (4-space) indent.
    "P3_TAIL_METHOD": "class _C:\n{block}\n",
    # _run_turn body lines at 8-space indent.
    "RUN_SETUP_NEW": "class _C:\n    async def _run_turn(self):\n{block}\n",
    # The finally: clause at 8 spaces — give it a matching try at 8.
    "RUN_FIN_NEW": (
        "class _C:\n    async def _run_turn(self):\n"
        "        try:\n            pass\n{block}\n"
    ),
}


def test_all_target_blocks_were_found():
    # Guard against a rename in patch.py silently skipping the compile checks.
    assert set(_BLOCKS) == {"P3_TAIL_METHOD", "RUN_SETUP_NEW", "RUN_FIN_NEW"}, (
        f"extracted only {sorted(_BLOCKS)} — did a constant get renamed in patch.py?"
    )


@pytest.mark.parametrize("name", ["P3_TAIL_METHOD", "RUN_SETUP_NEW", "RUN_FIN_NEW"])
def test_injected_block_is_valid_python(name):
    """compile() checks syntax + indentation (not name resolution), which is exactly
    what we need: the injected block must be well-formed Python in context."""
    block = _BLOCKS[name]
    source = _SCAFFOLDS[name].format(block=block)
    compile(source, f"<{name}>", "exec")  # raises SyntaxError on a bad block


def test_heartbeat_wiring_present():
    """The F1 fix must actually be in the injected code (regression guard)."""
    setup = _BLOCKS["RUN_SETUP_NEW"]
    fin = _BLOCKS["RUN_FIN_NEW"]
    assert "_hb_task" in setup and "touch_turn" in setup and "_heartbeat" in setup
    assert "_hb_task" in fin and ".cancel()" in fin
