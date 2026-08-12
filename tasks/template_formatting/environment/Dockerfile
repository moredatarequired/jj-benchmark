FROM ubuntu:24.04

# Pre-requisites
RUN apt-get update && apt-get install -y --no-install-recommends curl python3 python3-pip && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    pip3 install --break-system-packages uv && \
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

# Install target library
RUN curl -fsSL https://github.com/jj-vcs/jj/releases/download/v0.38.0/jj-v0.38.0-x86_64-unknown-linux-musl.tar.gz | \
    tar -xz -C /usr/local/bin ./jj && \
    chmod +x /usr/local/bin/jj

RUN mkdir -p /home/user/myproject && chmod 0755 /home/user && chmod 0755 /home/user/myproject

LABEL Author="any-task-builder"
LABEL Description="Empty environment with jj installed and an empty project directory."

# Container contents:
#   - jj installed in /usr/local/bin/jj
#   - /home/user/myproject directory ready for use

# Where the agent starts -- same reasoning as every other task here: without a
# WORKDIR the agent process lands at the filesystem root, because harbor passes
# no `-w` to `docker exec` and no task.toml sets [environment] workdir. This
# task ships no repository: the empty /home/user/myproject already in the image is
# where the agent runs `jj git init`,
# so this line lands the agent in the directory the instruction names.
WORKDIR /home/user/myproject

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
