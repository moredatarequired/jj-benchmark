# Edit Commit Message in Jujutsu

## Background
Jujutsu (`jj`) is a modern VCS that makes it easy to modify the history of a repository. It allows editing the commit message (description) of any commit in the history without checking it out, and automatically rebases descendants.

## Requirements
- Find the commit with the description "Add file B" in the repository history.
- Change its description to "Add second file".
- Create a new commit on top of the current working copy with the description "Add file D" and add a new file `d.txt` containing the text "d".

## Constraints
- Project path: /home/user/repo