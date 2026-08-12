# Squash a Range of Commits

## Background
In Jujutsu (`jj`), the changes recorded in several commits can be combined into a single commit, after which the source commits no longer appear in the log. Revsets let one operation name a whole range of source commits rather than one at a time.

## Requirements
- You have a `jj` repository at `/home/user/myproject`.
- It contains a commit with the description `feat: initial structure`.
- It has two child commits with descriptions `fix: syntax error` and `fix: logic error`.
- There is a descendant commit `feat: add more stuff`.
- Combine the two `fix` commits into the `feat: initial structure` commit. Afterwards exactly four commits must remain in the log (the root commit, `initial commit`, `feat: initial structure`, and `feat: add more stuff`), and `feat: initial structure` must carry both fixes.

## Constraints
- Project path: `/home/user/myproject`