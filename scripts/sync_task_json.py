#!/usr/bin/env python3
"""Regenerate bootstrap/task.json task_name and task_description.

The JSON duplicates instruction.md, and the JSON is what the harness actually
hands the agent -- so hand-editing the instruction alone silently leaves the
agent on the old text. `scripts/lint_tasks.py` fails CI on that drift; run this
after every instruction.md edit instead of touching the JSON by hand.

task_name is regenerated from the DIRECTORY NAME for the same reason: a task
directory copied from another one inherits the original's task_name, which
lint_tasks.py rejects, and hand-fixing it is exactly the step that gets
forgotten. (The `tasks/<name>_terse/` prompt-variant arms this used to name as
the worked example are gone, along with the variant machinery; copying a
directory to start a new task is still the way the drift happens.) The directory
name is the name harbor uses (LocalTaskId resolves it from the path), so it is
the authority here too.

Each file's existing trailing-newline state is preserved: task.json files in
this tree disagree about whether they end with one, and normalising either way
would produce a diff on files this script did not otherwise need to change.
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
        data["task_name"] = task_dir.name
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
