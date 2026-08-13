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
LABEL Description="jj project whose middle commit deleted a still-needed file by mistake."

# The three files of the initial commit. Written by three here-documents queued
# on one command line: the shell reads their bodies in the order the redirects
# appear, so main.py, legacy.py and settings.toml land in that order.
RUN mkdir -p /home/user/myproject && \
    cd /home/user/myproject && \
    git init && \
    git config user.name "Your Name" && \
    git config user.email "your@email.com" && \
    jj git init --colocate && \
    jj config set --user user.name "Your Name" && \
    jj config set --user user.email "your@email.com" && \
    cat >main.py <<'MAIN' && cat >legacy.py <<'LEGACY' && cat >settings.toml <<'SETTINGS'
from legacy import old_helper


def main():
    print(old_helper())
MAIN
def old_helper():
    return "legacy"
LEGACY
[server]
host = "127.0.0.1"
port = 8080

[logging]
level = "info"
SETTINGS

# The commit at the heart of the task: dropping the legacy module was intended,
# deleting settings.toml along with it was not.
RUN cd /home/user/myproject && \
    jj commit -m "Initial commit" && \
    rm legacy.py settings.toml && \
    cat >main.py <<'MAIN'
def main():
    print("running")
MAIN

# A descendant commit, so that fixing the commit above has to carry it along.
RUN cd /home/user/myproject && \
    jj commit -m "remove legacy module" && \
    cat >main.py <<'MAIN'
import logging


def main():
    logging.info("start")
    print("running")
MAIN

# Uncommitted work in the working copy, which must survive the fix.
RUN cd /home/user/myproject && \
    jj commit -m "add logging" && \
    cat >notes.txt <<'NOTES'
todo: review the release checklist
NOTES

# Container contents:
#   - jj installed in /usr/local/bin/jj.
#   - /home/user/myproject — jj repo with four commits above the root:
#       Initial commit        (main.py, legacy.py, settings.toml)
#       remove legacy module  (deletes legacy.py and, by mistake, settings.toml;
#                              rewrites main.py)
#       add logging           (rewrites main.py)
#       @                     (no description, adds notes.txt)

# Where the agent starts. Harbor passes no `-w` to `docker exec` and no
# task.toml sets [environment] workdir, so the agent process inherits the
# image's working directory -- and with no WORKDIR anywhere in the chain up to
# the base image, that was the filesystem root. Pointing it at the project
# makes the starting state the one a developer actually has: standing in the
# repository the task is about. The instruction still names the absolute path,
# so nothing in the task or the verifier depends on this.
WORKDIR /home/user/myproject

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]