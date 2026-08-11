# Output Author Name and Email with jj log Template

## Background
Jujutsu (`jj`) supports a functional template language to customize the output of commands like `jj log`. You can use it to extract specific information from commits, such as the author's name and email.

## Requirements
Write a `jj log` command that outputs the author's name and email of the current working copy commit (`@`), formatted exactly as `Author: Name <email>`, without the revision graph or any other information.

## Constraints
- Project path: `/home/user/project`
- The script `/home/user/project/get_author.sh` must be executable and contain the `jj log` command.
- The output of the script must be exactly `Author: Name <email>` (e.g., `Author: Test User <test@example.com>`) followed by a newline.