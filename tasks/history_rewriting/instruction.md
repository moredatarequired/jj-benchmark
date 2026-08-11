# Rewrite History in a Jujutsu Stack

## Background
`jj` (Jujutsu) makes it easy to manage a "stack" of small commits. Changing a commit partway down the stack does not orphan the commits above it — its descendants are rewritten onto the updated version automatically.

## Requirements
- You have a `jj` repository at `/home/user/repo` with a linear stack of 4 commits: Base -> Commit 1 -> Commit 2 -> Commit 3.
- The Base commit has a file `base.txt` with content `old`.
- Edit the Base commit so that `base.txt` contains `new`.
- Observe that Commits 1, 2, and 3 are automatically rebased.
- You must end up with the same 4 commit structure, but with the modified base.

## Output
- Project path: `/home/user/repo`
- Start command: `cd /home/user/repo`
- Port: N/A