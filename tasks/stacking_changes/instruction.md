# Stacking Changes with Jujutsu (jj)

## Background
Jujutsu (`jj`) is a modern version control system that treats the working copy as a permanent commit and makes it easy to manage a "stack" of small commits. Changing a commit partway down the stack does not orphan the commits above it — its descendants are rewritten onto the updated version automatically.

## Requirements
In the repository at `/home/user/repo`, there is a linear history of commits on top of the initial commit:
1. Commit with description "Add feature 1" (adds `feature1.txt`)
2. Commit with description "Add feature 2" (adds `feature2.txt`)
3. Commit with description "Add feature 3" (adds `feature3.txt`)

Your task is to modify the commit "Add feature 1" to also include a new file `feature1-docs.txt` with the exact content `Docs for feature 1`, without breaking the descendants. The final working copy must be at the tip of the stack (the descendant of "Add feature 3").

## Constraints
- Project path: `/home/user/repo`
- The repository is a `jj` repository.
- You must not abandon any of the three commits.
- The content of `feature1-docs.txt` must be exactly `Docs for feature 1`.