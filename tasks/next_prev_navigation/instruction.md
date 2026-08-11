# Walk the working copy along the history

## Background
Jujutsu (`jj`) lets you move the working copy around the commit graph directly. Instead of checking out a branch, you move the working-copy commit itself so that it hangs off a different point in the history — one step back towards the ancestors, several steps back at once, or forward again towards the descendants. Each such move is recorded as its own entry in the repository's operation log, so the route the working copy took through the graph is part of the repository's recorded state, not just where it ended up.

## Requirements
The repository at `/home/user/myproject` has the linear history `A` -> `B` -> `C` -> `D`. The working copy is an empty commit whose parent is `D`.

Walk the working copy back down that history and then part of the way forward again, so that its parent becomes each of the following in turn, each one reached by a separate move:

1. `C`.
2. `A`, in a single move from `C` — stepping over `B` rather than stopping on it.
3. `B`.

## Constraints
- **Project path**: /home/user/myproject
- The final working copy commit must be empty, with `B` as its only parent.
- Each of the three positions above must be the result of its own operation, and the three operations must appear in the operation log in the order listed. Arriving at `B` in fewer moves does not satisfy this, and neither does reaching `A` by way of `B`.
- The four original commits must be left exactly as they are: still the linear history `A` -> `B` -> `C` -> `D`, with the same descriptions and the same file contents.
- When you are finished the repository must hold no commits other than those four and the working copy.