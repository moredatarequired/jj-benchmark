# Split a Commit in Jujutsu

## Background
`jj split` can take a single commit with changes in multiple files and turn it into two separate commits.

## Requirements
- You have a repository in `/home/user/project` with a commit (described as `Combined changes`) that modifies `fileA.txt` and `fileB.txt`.
- Split this commit into two sequential commits.
- The first commit should contain only the changes to `fileA.txt` and have the description `Modify fileA`.
- The second commit should contain only the changes to `fileB.txt` and have the description `Modify fileB`.

## Constraints
- Project path: `/home/user/project`.