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
LABEL Description="jj task environment with a range of commits to be squashed."

# Combining several commits into one is a command that needs a description it
# was not given, so jj opens an editor pre-filled with the destination's
# description followed by each source's. This image ships no editor, and the
# agent's shell has no TTY, so an interactive editor cannot work here even if
# one were installed: with no editor the command dies on "Failed to run editor
# 'nano': No such file or directory", and with nano installed it dies on
# "Standard input is not a terminal". Either way the environment, not the
# agent, decides the task is unsolvable by its most natural form -- while
# tests/test_final_state.py explicitly accepts the description that form
# produces. Pointing ui.editor at `true` makes the edit step a no-op that
# exits 0, so jj keeps the text it pre-filled (JJ: comment lines stripped) and
# the command succeeds. This is what an EDITOR=true CI environment does. It
# changes nothing for the forms that pass a description on the command line,
# which keep working exactly as before.
#
# The value is quoted so that jj stores the *string* "true": `jj config set`
# parses its argument as TOML, so a bare true is stored as a boolean and then
# rejected at use time with "Invalid type or value for ui.editor".
#
# Config, not $JJ_EDITOR: the environment variable outranks ui.editor, so it
# would also silently override an agent that points ui.editor at a script of
# its own to control the combined description. A config default is overridable
# -- by the agent's own `jj config set`, by --config, by $JJ_EDITOR -- which is
# what a default should be.
#
# --user, not --repo: ui.editor is a preference of the environment rather than
# a property of this repository, and a scratch repo the agent creates while
# experimenting should behave the same way. Both scopes live under $HOME in jj
# v0.38 (--repo writes $HOME/.config/jj/repos/<hash>/config.toml), so this adds
# no assumption the bootstrap's own --repo user.name did not already make.
RUN jj config set --user ui.editor '"true"'

RUN mkdir -p /home/user/myproject && \
    cd /home/user/myproject && \
    jj git init --colocate && \
    jj config set --repo user.name "Test User" && \
    jj config set --repo user.email "test@example.com" && \
    echo "initial" > main.txt && \
    jj describe -m "initial commit" && \
    jj bookmark create main && \
    jj new -m "feat: initial structure" && \
    echo "structure" > structure.txt && \
    jj bookmark create feature && \
    jj new -m "fix: syntax error" && \
    echo "syntax fixed" > structure.txt && \
    jj new -m "fix: logic error" && \
    echo "logic fixed" > structure.txt && \
    jj new -m "feat: add more stuff" && \
    echo "more stuff" > stuff.txt

# Container contents:
#   - jj installed in /usr/local/bin
#   - jj's ui.editor set to `true`, so description edits are non-interactive
#   - /home/user/myproject  — jj project with initialized repository
#   - Commit stack with feature and fix commits

# Where the agent starts. Harbor passes no `-w` to `docker exec` and no
# task.toml sets [environment] workdir, so the agent process inherits the
# image's working directory -- and with no WORKDIR anywhere in the chain up to
# the base image, that was the filesystem root. Pointing it at the project
# makes the starting state the one a developer actually has: standing in the
# repository the task is about. The instruction still names the absolute path,
# so nothing in the task or the verifier depends on this.
WORKDIR /home/user/myproject

CMD ["/bin/bash", "-c", "trap : TERM INT; sleep infinity & wait"]
