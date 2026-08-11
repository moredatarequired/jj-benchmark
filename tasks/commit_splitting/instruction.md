# Split a Commit in Jujutsu

## Background
A commit that bundles unrelated file changes is harder to review and harder to revert than the same work recorded as one commit per concern. Jujutsu can turn a single commit into a sequence of smaller commits without changing the tree that results.

## Requirements
- You have a repository in `/home/user/project` with a commit (described as `Combined changes`) that modifies `fileA.txt` and `fileB.txt`.
- Split this commit into two sequential commits.
- The first commit should contain only the changes to `fileA.txt` and have the description `Modify fileA`.
- The second commit should contain only the changes to `fileB.txt` and have the description `Modify fileB`.

## Constraints
- Project path: `/home/user/project`.