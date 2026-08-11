# Fetch and Rebase with jj

## Background
`jj` (Jujutsu) allows you to seamlessly interact with Git remotes. In this task, you need to fetch new changes from a remote repository, rebase your local work onto the updated main branch, and push your changes back.

## Requirements
- Fetch the latest changes from the `origin` remote.
- Rebase the `feature` bookmark onto the updated `main` branch (which is tracked as `main@origin`).
- Push the `feature` bookmark to the `origin` remote.

## Constraints
- Project path: `/home/user/repo`