# Insert a New Commit in a jj Stack

## Background
You have a `jj` repository with a stack of commits at `/home/user/myproject`. The commit graph looks like this: `A` -> `B` -> `C`. You need to insert a new commit between `A` and `B` without breaking the descendants.

## Requirements
- Insert a new commit that is a child of the commit with the description "commit A" and a parent of the commit with the description "commit B".
- The new commit must contain a new file named `feature.txt` with the exact text `new feature\n`.
- The descendants (`B` and `C`) must be rebased on top of this new commit.
- The working copy should be left at the tip of the stack (the new version of `C`).

## Constraints
- Project path: `/home/user/myproject`
- Do not modify the contents of the existing commits `A`, `B`, or `C`.
- The final stack should be `A` -> `New Commit` -> `B'` -> `C'`.