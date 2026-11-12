#!/bin/sh
set -eu
if [ "$#" -gt 0 ]; then exec "$@"; fi
poll="${FOUNDRY_SCHEDULE_POLL_SECONDS:-300}"
case "$poll" in ''|*[!0-9]*|0) echo "Invalid FOUNDRY_SCHEDULE_POLL_SECONDS" >&2; exit 1;; esac
trap 'exit 0' TERM INT
while :; do
  foundry --root "${FOUNDRY_ROOT:-/data}" run-scheduled || status=$?
  sleep "$poll" &
  wait "$!" || true
done
