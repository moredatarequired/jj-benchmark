# Record the Evolution of the Working-Copy Change

## Background
In Jujutsu (`jj`), a change keeps its identity while the commit it points to is replaced every time the change is described, amended, or rebased. The superseded commits are not thrown away: the repository still remembers every commit a change has ever pointed to, even though those versions no longer show up in the ordinary log.

## Requirements
- The repository is at `/home/user/repo`. Its working-copy change has already gone through several revisions.
- Write a report of that change's complete evolution to `/home/user/obslog.txt`: every version the change has pointed to, from the commit it points to now all the way back to the version that first created it, each version identified by its commit ID and carrying its description.
- Leave the repository itself unchanged while you do it: no new commits, no edits to `file.txt`, no description changes. Anything that alters the working-copy change adds a further version to its evolution, which would make a report saved earlier incomplete.

## Constraints
- Project path: `/home/user/repo`
- Output file: `/home/user/obslog.txt`
- Exact formatting is not checked. The report is inspected for the commit ID and description of every version of the change, so any faithful rendering is accepted. Commit IDs may appear abbreviated (at least the first 8 characters) or in full.