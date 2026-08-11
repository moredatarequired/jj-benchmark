# Customize jj log output with Templates

## Background
Jujutsu (`jj`) provides a powerful functional templating language to customize the output of commands like `jj log`. You can define template aliases and use them to change the default output of `jj log`.

## Requirements
1. Initialize a new `jj` repository in the existing directory `/home/user/myproject`.
2. Configure the repository's author identity: user name `Test User`, email `test@example.com`.
3. Create an initial commit with description "Initial commit".
4. Create a new commit with the description "Second commit".
5. Configure the repository-level `jj` config (`/home/user/myproject/.jj/repo/config.toml`) to define a custom template alias named `'custom_log'` under `[template-aliases]`.
   The alias should format a commit as: `<short_commit_id> | <author_email_local_part> | <first_line_of_description>\n`
   (e.g., `12345678 | test | Initial commit\n`).
   *Hint: Use `commit_id.short()`, `author.email().local()`, and `description.first_line()` functions.*
6. Configure the default log template in the same config file to use your `custom_log` alias (under `[templates]` set `log = 'custom_log'`).

## Constraints
- Project path: `/home/user/myproject`
- The repository must be a `jj` repository using the default Git backend.