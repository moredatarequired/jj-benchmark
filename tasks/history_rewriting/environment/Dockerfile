FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y curl tar git && \
    curl -fsSL https://github.com/jj-vcs/jj/releases/download/v0.38.0/jj-v0.38.0-x86_64-unknown-linux-musl.tar.gz | \
    tar -xz -C /usr/local/bin ./jj && \
    chmod +x /usr/local/bin/jj

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

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="A jj repository with a stack of commits."

RUN mkdir -p /home/user/repo && \
    cd /home/user/repo && \
    jj config set --user user.name "Test User" && \
    jj config set --user user.email "test@example.com" && \
    jj git init && \
    echo "old" > base.txt && \
    jj new -m "Base" && \
    echo "c1" > c1.txt && \
    jj new -m "Commit 1" && \
    echo "c2" > c2.txt && \
    jj new -m "Commit 2" && \
    echo "c3" > c3.txt && \
    jj new -m "Commit 3"

# Container contents:
#   - jj installed
#   - /home/user/repo initialized with a stack of 4 commits

# Where the agent starts. Harbor passes no `-w` to `docker exec` and no
# task.toml sets [environment] workdir, so the agent process inherits the
# image's working directory -- and with no WORKDIR anywhere in the chain up to
# the base image, that was the filesystem root. Pointing it at the project
# makes the starting state the one a developer actually has: standing in the
# repository the task is about. The instruction still names the absolute path,
# so nothing in the task or the verifier depends on this.
WORKDIR /home/user/repo

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
