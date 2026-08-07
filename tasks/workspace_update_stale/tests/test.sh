#!/bin/bash
# Use this file to install test dependencies and run the tests.
# It will be copied to /tests/test.sh and run from the working directory.

# There is nothing to install. pytest==8.4.1 and pytest-json-ctrf==0.3.5 are
# baked into every task image at build time (see environment/Dockerfile), and
# task.toml sets [verifier] network_mode = "no-network", so this script runs
# with no route off the container at all.
#
# It used to bootstrap uv from astral.sh and resolve three packages out of pypi
# on every single trial. When that stalled -- and the pypi path out of these
# containers stalls often -- no ctrf.json was ever written and harbor recorded
# reward 0 with no error, which is indistinguishable from the agent genuinely
# failing the task. A verifier that needs the network in order to say "no"
# cannot be trusted when it says "no".
mkdir -p /logs/verifier
# CTRF produces a standard test report in JSON format which is useful for logging.
python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_final_state.py -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
