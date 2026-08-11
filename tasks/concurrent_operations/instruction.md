# Simulating and Resolving Concurrent Operations in Jujutsu

## Background
Jujutsu (`jj`) uses an operation log to enable lock-free concurrency. It is possible to simulate divergent operations by running commands at a specific past operation using the `--at-operation=<operation ID>` flag.

## Requirements
1. In the repository at `/home/user/repo`, there is a change that was originally created with the description `Feature X`.
2. The repository currently has its description updated to `Feature X - variant 1`.
3. You need to simulate a concurrent operation by describing the commit as `Feature X - variant 2` at the exact operation ID where the `Feature X` commit was originally created (before it was updated to `variant 1`).
4. Trigger the operation log merge to see the divergence.
5. Resolve the divergence by keeping only the `Feature X - variant 2` commit and abandoning the `Feature X - variant 1` commit.

## Constraints
- Project path: `/home/user/repo`
- The final state must have only one visible commit for the `Feature X` change, with the description `Feature X - variant 2`.