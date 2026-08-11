# Diffing Revisions in Jujutsu

## Background
You are working in a `jj` repository. Jujutsu can show the changes introduced by a revision, and can also show the cumulative difference between any two revisions rather than only the working copy against its parent.

## Repository State
- `commit A`: adds `hello.txt` with the text "Hello". Bookmark: `start`.
- `commit B`: modifies `hello.txt` to "Hello World". Bookmark: `middle`.
- `commit C`: modifies `hello.txt` to "Hello World!". Bookmark: `end`.
- `commit D`: modifies `hello.txt` to "Hello World!!!". Working copy is here.

## Requirements
1. Output the diff between the revision pointed to by the `start` bookmark and the revision pointed to by the `end` bookmark.
2. Save the output to a file named `diff_output.txt` in the root of the repository.
3. The diff must be in Git patch format: the saved output must contain a `diff --git` header and the `--- a/hello.txt` / `+++ b/hello.txt` file markers.

## Constraints
- Project path: `/home/user/myproject`
- Use only `jj` commands.