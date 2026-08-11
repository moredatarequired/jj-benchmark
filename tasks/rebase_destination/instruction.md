# Rebase a branch to a new destination

## Background
You have a Jujutsu (`jj`) repository located at `/home/user/myproject`. The repository contains a `main` bookmark and a `feature` bookmark. The `feature` bookmark diverges from `main`.

## Requirements
Move the commit that the `feature` bookmark points to so that its parent is the commit pointed to by the `main` bookmark, with `feature` still on the moved commit.

## Constraints
- Project path: `/home/user/myproject`