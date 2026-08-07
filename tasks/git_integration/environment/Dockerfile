FROM ubuntu:24.04

# Avoid tzdata interactive prompt during package installation
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y curl git python3 python3-pip && \
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y nodejs && \
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh && \
    curl -fsSL https://github.com/jj-vcs/jj/releases/download/v0.38.0/jj-v0.38.0-x86_64-unknown-linux-musl.tar.gz | \
    tar -xz -C /usr/local/bin ./jj && \
    chmod +x /usr/local/bin/jj && \
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

RUN mkdir -p /home/user && chmod 0755 /home/user

LABEL Author="pochi"
LABEL Description="Environment with jj installed and a local bare Git repository for cloning and pushing."

# Set up global git and jj config, and the bare git repository
RUN git config --global user.name "Your Name" && \
    git config --global user.email "your@email.com" && \
    jj config set --user user.name "Your Name" && \
    jj config set --user user.email "your@email.com" && \
    mkdir -p /tmp/init_repo && \
    cd /tmp/init_repo && \
    git init && \
    echo "Initial commit" > readme.md && \
    git add readme.md && \
    git commit -m "Initial commit" && \
    git clone --bare /tmp/init_repo /home/user/remote.git && \
    rm -rf /tmp/init_repo

# Container contents:
#   - jj installed in /usr/local/bin/jj
#   - git installed
#   - /home/user/remote.git  — bare git repository with one commit

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
