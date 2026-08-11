# Conflict Resolution in jj

## Background
Jujutsu (`jj`) treats conflicts as first-class objects, meaning a commit with conflicts can be recorded and rebased just like any other commit. You don't have to resolve conflicts immediately during a rebase. Instead, you can resolve them later by editing the file to remove conflict markers, and `jj` will automatically detect the resolution.

## Requirements
1. Rebase the bookmark `feature-b` onto the bookmark `feature-a`.
2. This will result in a conflict in `file.txt`.
3. Resolve the conflict in `file.txt` so that the conflicting line reads `Feature A and Feature B`.
4. Verify the conflict is resolved.

## Constraints
- Project path: `/home/user/myproject`
- The final `file.txt` should contain exactly three lines:
  `Line 1`
  `Feature A and Feature B`
  `Line 3`
- The repository must have no remaining conflicts.