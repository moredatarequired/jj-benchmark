# Customize jj log output with Templates

## Background
Jujutsu (`jj`) provides a powerful functional templating language to customize the output of commands like `jj log`. You can define template aliases and use them to change the default output of `jj log`.

## Requirements
1. Initialize a new `jj` repository in the existing directory `/home/user/myproject`.
2. Configure the repository's author identity: user name `Test User`, email `test@example.com`.
3. Build the history so that the finished repository holds exactly three commits: the root commit, a commit described `Initial commit` directly above it, and a commit described `Second commit` directly above that. Both described commits must be authored by the identity from requirement 2.
4. The `Second commit` commit must be the working copy itself. Do not leave any further commit above it — not even an empty, undescribed one — so the default log listing shows exactly those three commits, newest first: `Second commit`, then `Initial commit`, then the root commit.
5. Configure the repository-level `jj` config to define a custom template alias named `'custom_log'` under `[template-aliases]`.
   The alias should format a commit as: `<short_commit_id> | <author_email_local_part> | <first_line_of_description>\n`
   where `<short_commit_id>` is the commit id abbreviated to exactly 12 characters
   (e.g., `1234567890ab | test | Initial commit\n`, and the root commit therefore renders as `000000000000 |  |`).
6. Configure the default log template in the same config to use your `custom_log` alias (under `[templates]` set `log = 'custom_log'`).

## Constraints
- Project path: `/home/user/myproject`
- The repository must be a `jj` repository using the default Git backend.