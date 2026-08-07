FROM ubuntu:24.04

RUN apt-get update && apt-get install -y curl git python3 python3-pip && \
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
LABEL Description="Environment with multiple operations."

RUN mkdir -p /home/user/project && \
    cd /home/user/project && \
    git init && \
    jj git init --colocate && \
    jj config set --user user.name "Alice" && \
    jj config set --user user.email "alice@example.com" && \
    echo "C1" > file1.txt && jj commit -m "Commit 1" && \
    echo "C2" > file2.txt && jj commit -m "Commit 2" && \
    echo "C3" > file3.txt && jj commit -m "Commit 3" && \
    echo "C4" > file4.txt && jj commit -m "Commit 4" && \
    echo "C5" > file5.txt && jj commit -m "Commit 5"

# Container contents:
#   - jj installed
#   - /home/user/project with 5 commits

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]