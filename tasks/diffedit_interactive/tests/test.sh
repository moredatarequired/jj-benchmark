#!/bin/bash
# Use this file to install test dependencies and run the tests.
# It will be copied to /tests/test.sh and run from the working directory.

# uv's default HTTP read timeout is 30s, and the pypi path out of this
# container stalls past it often enough to lose whole trials: the dependency
# install fails, no ctrf.json is ever written, and harbor records reward 0 with
# no error -- indistinguishable from the agent genuinely failing the task. Both
# knobs are read from the environment by uv, and both defer to a value the
# caller already set (e.g. harbor's --ve UV_HTTP_TIMEOUT=300), so this is a
# floor, not an override. 300s x 3 attempts can outlast the 600s verifier
# timeout in task.toml; that is deliberate -- a trial killed by the verifier
# timeout is reported as an error, which is the outcome we want over a silent 0.
export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-300}"
export UV_HTTP_RETRIES="${UV_HTTP_RETRIES:-2}"
curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh
source $HOME/.local/bin/env
# CTRF produces a standard test report in JSON format which is useful for logging.
uvx \
  --with pytest==8.4.1 \
  --with pytest-json-ctrf==0.3.5 \
  --with pochi-verifier \
  pytest --ctrf /logs/verifier/ctrf.json /tests/test_final_state.py -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
