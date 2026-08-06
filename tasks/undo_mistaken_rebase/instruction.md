# Undo a Mistaken Rebase in jj

## Background
Jujutsu (`jj`) records every repository operation in an operation log, so any change to the
repository can be reverted after the fact — including a rebase that has already completed.

The repository at `/home/user/repo` has the linear history `base` -> `A` -> `B`, with the
bookmark `main` on `A`.

## Requirements
1. Rebase commit `B` onto `base`. This is the mistake you are going to revert.
2. Undo that rebase, returning the repository to the state it was in beforehand.

## Constraints
- Project path: `/home/user/repo`
- Both steps must actually be performed: the operation log must show the rebase, and then the
  undo that reverted it.
- Afterwards the history must be exactly `base` -> `A` -> `B` again, with `main` on `A` and the
  file `f` holding `base`, `A`, and `B` in those respective commits.
