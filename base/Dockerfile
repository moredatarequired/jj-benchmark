# Shared base for every task environment.
#
# Bakes in Claude Code so harbor's agent adapter skips its per-trial install, which
# was 45% of total run time (24.8s median in every one of 53 containers). The adapter
# checks `command -v claude` and skips installing when it is already present.
#
# Build with scripts/build-base.sh before running the benchmark. Task Dockerfiles
# reference it as `FROM jj-bench-base:0.38.0`.

FROM ubuntu:24.04

ARG JJ_VERSION=0.38.0
ARG CLAUDE_CODE_VERSION=latest

# procps is required: Claude Code's node-tree-kill shells out to ps/pgrep.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates git tar python3 python3-pip procps nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# jj for whichever architecture this image is built for. uname -m yields the same
# strings jj uses in its release assets: x86_64 and aarch64.
RUN arch="$(uname -m)" \
    && curl -fsSL "https://github.com/jj-vcs/jj/releases/download/v${JJ_VERSION}/jj-v${JJ_VERSION}-${arch}-unknown-linux-musl.tar.gz" \
        | tar -xz -C /usr/local/bin ./jj \
    && chmod +x /usr/local/bin/jj \
    && jj --version

RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force \
    && claude --version
