# Track an Ignored File in Jujutsu (jj)

## Background
In `jj` (Jujutsu), new files are automatically tracked and included in the working copy commit. However, files that match patterns in `.gitignore` are ignored and not automatically tracked. Sometimes, you may need to explicitly track a specific file that is otherwise ignored, without modifying the `.gitignore` rules.

## Requirements
- Explicitly track the ignored file `app.log` in the repository.
- Do not modify the existing `.gitignore` file.
- Finalize the current working copy by creating a new commit with the message "Track log file".

## Constraints
- Project path: `/home/user/project`