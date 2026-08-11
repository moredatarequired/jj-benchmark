# Ignore Log Files in Jujutsu

## Background
You are working in a Jujutsu repository at `/home/user/myproject`. You realized that log files are being tracked by the version control system because Jujutsu automatically tracks new files.

## Requirements
1. Configure the repository to ignore all `.log` files (pattern `*.log`).
2. Untrack the existing `debug.log` file so it is no longer tracked by Jujutsu, but ensure it is not deleted from the disk.

## Constraints
- Project path: `/home/user/myproject`
- The `debug.log` file must remain on disk.
- The `.gitignore` file must be tracked by Jujutsu.