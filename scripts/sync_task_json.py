#!/usr/bin/env python3
"""Regenerate bootstrap/task.json task_description from instruction.md.

The JSON duplicates instruction.md, and the JSON is what the harness actually
hands the agent -- so hand-editing the instruction alone silently leaves the
agent on the old text. `scripts/lint_tasks.py` fails CI on that drift; run this
after every instruction.md edit instead of touching the JSON by hand.

Each file's existing trailing-newline state is preserved: 49 of the 53 task.json
files end without one, 4 end with one, and normalising either way would produce
a diff on files this script did not otherwise need to change.
"""
import json
import pathlib

TASKS = pathlib.Path(__file__).resolve().parent.parent / "tasks"


def main() -> None:
    changed = []
    for task_dir in sorted(TASKS.iterdir()):
        path = task_dir / "bootstrap/task.json"
        instruction = task_dir / "instruction.md"
        if not path.is_file() or not instruction.is_file():
            continue
        before = path.read_text(encoding="utf-8")
        data = json.loads(before)
        data["task_description"] = instruction.read_text(encoding="utf-8")
        # ensure_ascii=False keeps non-ASCII (e.g. undo_mistaken_rebase's em dash)
        # literal rather than \u-escaped, matching the committed files.
        after = json.dumps(data, indent=2, ensure_ascii=False)
        if before.endswith("\n"):
            after += "\n"
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed.append(task_dir.name)

    print(f"{len(changed)} task.json file(s) updated")
    for name in changed:
        print(f"  {name}")


if __name__ == "__main__":
    main()
