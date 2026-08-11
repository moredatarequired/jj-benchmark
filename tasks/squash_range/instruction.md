# Squash a Range of Commits

## Background
In Jujutsu (`jj`), you can use `jj squash` to move changes from one or more commits into another commit. By using revsets, you can squash a range of commits into a target commit in a single command.

## Requirements
- You have a `jj` repository at `/home/user/myproject`.
- It contains a commit with the description `feat: initial structure`.
- It has two child commits with descriptions `fix: syntax error` and `fix: logic error`.
- There is a descendant commit `feat: add more stuff`.
- Squash the two `fix` commits into the `feat: initial structure` commit using a single `jj squash` command with a range or revset.

## Constraints
- Project path: `/home/user/myproject`