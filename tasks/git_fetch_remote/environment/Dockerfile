FROM ubuntu:24.04

RUN apt-get update -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        curl ca-certificates git python3 python3-pip bash && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Verifier dependencies, pinned and installed at build time so that
# tests/test.sh needs no network access at all. scripts/lint_tasks.py checks
# these pins against the ones tests/test.sh expects.
#
# Deliberately not from apt: python3-pytest is 7.4, which misses the pin, and
# being dpkg-managed it also blocks pip from replacing its pluggy. pip on
# ubuntu:22.04 (22.0.2) predates --break-system-packages; it also predates
# PEP 668, so the plain install is the correct call there, and the fallback
# keeps this one layer working on both bases.
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip && \
    rm -rf /var/lib/apt/lists/* && \
    ( python3 -m pip install --break-system-packages --no-cache-dir \
          pytest==8.4.1 pytest-json-ctrf==0.3.5 || \
      python3 -m pip install --no-cache-dir \
          pytest==8.4.1 pytest-json-ctrf==0.3.5 )

RUN curl -fsSL https://github.com/jj-vcs/jj/releases/download/v0.44.0/jj-v0.44.0-x86_64-unknown-linux-musl.tar.gz | \
    tar -xz -C /usr/local/bin ./jj && \
    chmod +x /usr/local/bin/jj

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="jj git fetch and rebase task environment"

RUN git config --global user.name "Test User" && \
    git config --global user.email "test@example.com" && \
    jj config set --user user.name "Test User" && \
    jj config set --user user.email "test@example.com" && \
    mkdir -p /home/user/remote.git && \
    cd /home/user/remote.git && \
    git init --bare && \
    cd /home/user && \
    git clone /home/user/remote.git remote_work && \
    cd remote_work && \
    git checkout -b main && \
    echo "Initial commit" > file.txt && \
    git add file.txt && \
    git commit -m "Initial commit" && \
    git push origin main && \
    cd /home/user && \
    jj git clone /home/user/remote.git repo && \
    cd repo && \
    jj bookmark create feature && \
    echo "Feature commit" > feature.txt && \
    jj commit -m "Feature commit" && \
    cd /home/user/remote_work && \
    echo "Update main" > file.txt && \
    git add file.txt && \
    git commit -m "Update main" && \
    git push origin main && \
    rm -rf /home/user/remote_work

# Container contents:
#   - jj installed
#   - /home/user/repo: jj repository with feature bookmark
#   - /home/user/remote.git: bare Git repository with an updated main branch
#   - /home/user/AGENTS.md (+ CLAUDE.md symlink): project conventions for the agent

# Project conventions for coding agents. Deliberately placed in /home/user, the
# PARENT of the project directory, and never inside the repository: two verifiers
# assert an exact tracked-file set, so a committed AGENTS.md caps a correct solve
# below 1.0. What makes it reach the agent is the filename CLAUDE.md, not the
# symlink: captured on Claude Code 2.1.235 inside the built task image,
# /home/user/CLAUDE.md arrives in the assembled system prompt under `Contents of
# /home/user/CLAUDE.md (project instructions, checked into the codebase):`, and a
# bare AGENTS.md is not delivered, at that position or at the project root;
# reproduced on Claude Code 2.1.42 against a replica of the layout. How the
# harness finds the file was not measured, only that it arrives -- evidence in
# results/2026-08-14-baseline-24.md:40-52. The `ln -s` spelling below is pinned
# by scripts/lint_tasks.py, so all 24 copies stay byte-identical and comparable;
# AGENTS.md is the real file so the note also suits agents reading that name.
RUN printf '%s\n' \
      '# Contributing' \
      '' \
      'This project uses Jujutsu (`jj`) for version control. Please use `jj` for all' \
      'version control work in this repository; `git` should not be used for it.' \
      > /home/user/AGENTS.md && \
    ln -s AGENTS.md /home/user/CLAUDE.md

# Where the agent starts. Harbor passes no `-w` to `docker exec` and no
# task.toml sets [environment] workdir, so the agent process inherits the
# image's working directory -- and with no WORKDIR anywhere in the chain up to
# the base image, that was the filesystem root. Pointing it at the project
# makes the starting state the one a developer actually has: standing in the
# repository the task is about. The instruction still names the absolute path,
# so nothing in the task or the verifier depends on this.
WORKDIR /home/user/repo

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
