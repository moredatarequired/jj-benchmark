# Jujutsu Git Integration

## Background
Jujutsu (`jj`) is a modern VCS that uses a Git backend by default, allowing developers to use `jj` locally while interacting with standard Git remotes.

## Requirements
1. Clone the bare Git repository located at `/home/user/remote.git` into `/home/user/repo`.
2. Inside `/home/user/repo`, create a new file named `feature.txt` with the text `hello world`.
3. Create a bookmark named `my-feature`.
4. Push the bookmark to the `origin` remote.

## Constraints
- Project path: `/home/user/repo`
- You must use `jj` commands instead of `git` commands for repository operations.