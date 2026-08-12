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

RUN curl -fsSL \
    https://github.com/jj-vcs/jj/releases/download/v0.38.0/jj-v0.38.0-x86_64-unknown-linux-musl.tar.gz | \
    tar -xz -C /usr/local/bin ./jj && \
    chmod +x /usr/local/bin/jj

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="any-task-builder"
LABEL Description="jj log template task environment"

# The identity is configured BEFORE `jj git init`, which is what the other 39
# task images do. Order matters here and it is not cosmetic: `jj git init`
# creates the working-copy commit immediately, stamping it with the identity
# configured at that moment. Setting the identity afterwards leaves @ authored
# by " <>" -- jj says so itself ("This setting will only impact future commits.
# The author of the working copy will stay ' <>'.") -- and this task asks for a
# script that prints the author of @ as "Test User <test@example.com>", which
# would then be a string the repository does not contain. jj happens to fill
# the empty author in from config the first time it snapshots a change in the
# working copy, so the task was solvable by accident; an agent that inspected
# @'s author before creating any file saw " <>" and had every reason to
# conclude the required output could not come from a template.
RUN mkdir -p /home/user/project && \
    cd /home/user/project && \
    jj config set --user user.name "Test User" && \
    jj config set --user user.email "test@example.com" && \
    jj git init --colocate

# Container contents:
#   - jj installed in /usr/local/bin/jj
#   - /home/user/project initialized as a jj repo with user config
#   - the working-copy commit @ is authored by Test User <test@example.com>

# Where the agent starts. Harbor passes no `-w` to `docker exec` and no
# task.toml sets [environment] workdir, so the agent process inherits the
# image's working directory -- and with no WORKDIR anywhere in the chain up to
# the base image, that was the filesystem root. Pointing it at the project
# makes the starting state the one a developer actually has: standing in the
# repository the task is about. The instruction still names the absolute path,
# so nothing in the task or the verifier depends on this.
WORKDIR /home/user/project

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
