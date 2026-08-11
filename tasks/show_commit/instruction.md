# Inspecting Commits with Jujutsu

## Background
You have a Jujutsu (jj) repository at `/home/user/project` with a few commits. You need to create a script to easily show the Git-format diff of specific commits and use it to extract patches for two specific commits.

## Requirements
1. Create a bash script at `/home/user/project/show_commit.sh`.
2. The script must take a single argument: a Jujutsu revset.
3. Given a revset, the script must print that revision's details together with its diff, and the diff must be in Git patch format — the output must contain a `diff --git a/<path> b/<path>` header for each changed file.
4. Make the script executable.
5. Run your script for the revset `description(substring:"Add configuration file")` and redirect the output to `/home/user/project/add_config.patch`.
6. Run your script for the revset `description(substring:"Update configuration file")` and redirect the output to `/home/user/project/update_config.patch`.

## Constraints
- Project path: `/home/user/project`
- The script must be executable.
- The output files must contain the Git-format diff.