# Create a chain of commits in Jujutsu

## Background
In Jujutsu (`jj`), the working copy is always a commit. You can use `jj describe` to set the description of the current working copy commit, and `jj new` to create a new commit on top of the current one.

## Requirements
You have an initialized Jujutsu repository at `/home/user/myproject`.
Your task is to create a linear chain of 3 commits starting from the current working copy.

1. Modify the **current** working copy commit to have the description `commit 1`, and create a file `file1.txt` containing `first`.
2. Create a child commit with the description `commit 2`. In this commit, create a file `file2.txt` containing `second`.
3. Create another child commit with the description `commit 3`. In this commit, create a file `file3.txt` containing `third`.

At the end of the task, your working copy should be on the commit with description `commit 3`.

## Constraints
- Project path: `/home/user/myproject`
- Start command: `cd /home/user/myproject`
- Port: N/A
- Do not create any bookmarks, just use the anonymous commits.