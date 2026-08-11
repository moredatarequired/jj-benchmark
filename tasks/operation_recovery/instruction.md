# Return a Repository to an Earlier State

## Background
Jujutsu (`jj`) keeps a record of every step it has taken in a repository — each commit, each rebase, each snapshot of the working copy. That record holds the complete repository state as it was after each step, so a repository can be put back the way it was at an earlier point, and the states in between are never thrown away.

## Requirements
The repository at `/home/user/project` holds five commits, described `Commit 1` through `Commit 5`, each adding one file, with an empty working-copy commit on top. The last three commits were a mistake. Put the repository back exactly as it was immediately after `Commit 2` was created — the point at which `Commit 2` existed and the working copy was the new empty commit sitting on top of it. The end state must satisfy all of the following:

1. `/home/user/project` holds `file1.txt` (containing `C1`) and `file2.txt` (containing `C2`); `file3.txt`, `file4.txt` and `file5.txt` are gone from it. Those two files are the whole content of the working copy — nothing else is recorded in it.
2. Exactly four commits are visible: the root commit, `Commit 1`, `Commit 2`, and the empty working-copy commit on top of `Commit 2`. Nothing described `Commit 3`, `Commit 4` or `Commit 5` is visible any more.
3. `Commit 1` and `Commit 2` are still the same two commits they are now — same commit IDs, same parents. Do not rewrite them or rebuild equivalents of them.
4. The working copy is the same empty, undescribed commit that was the working copy immediately after `Commit 2` was created: the same change ID, with `Commit 2` as its parent. Creating a fresh empty commit on top of `Commit 2` produces a different commit and does not satisfy this.
5. Nothing is erased. The discarded work must still be reachable through the repository's record of past steps, so do not delete, re-initialise, or prune anything.

## Constraints
- Project path: `/home/user/project`.