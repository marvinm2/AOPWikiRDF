#!/usr/bin/env bash
# Shared helpers for the monthly Zenodo deposit workflow.
#
# Every Zenodo call goes through zenodo_api so a non-2xx response fails the
# step with the response body attached. Calling curl directly and piping into
# jq hides the real problem: Zenodo answers a transient error with a JSON
# object, jq then dies on it with a bare "exit code 5" and no diagnostic.
#
# Requires ZENODO_TOKEN in the environment. Sourced, not executed.

ZENODO_API="https://zenodo.org/api"

# Retry transient Zenodo errors (HTTP 408/429/500/502/503/504 and timeouts).
# curl treats these as transient and backs off between attempts.
ZENODO_RETRY=(--retry 5 --retry-delay 15 --retry-connrefused)

# zenodo_api <method> <url> [extra curl args...]
# Writes the response body to stdout; returns non-zero on transport failure or
# a non-2xx status, with the status and body on stderr.
zenodo_api() {
  local method="$1" url="$2"
  shift 2

  local body status rc=0
  body=$(mktemp)

  # "|| rc=$?" rather than a bare assignment: under set -e a failing command
  # substitution would kill the function before the status could be reported.
  status=$(curl -sS "${ZENODO_RETRY[@]}" \
                -H "Authorization: Bearer ${ZENODO_TOKEN}" \
                -X "$method" "$url" "$@" \
                -o "$body" -w '%{http_code}') || rc=$?

  if [[ $rc -ne 0 ]]; then
    echo "::error::curl exited $rc for $method $url" >&2
    rm -f "$body"
    return 1
  fi

  if [[ "$status" != 2* ]]; then
    echo "::error::Zenodo returned HTTP $status for $method $url" >&2
    head -c 2000 "$body" >&2
    echo >&2
    rm -f "$body"
    return 1
  fi

  cat "$body"
  rm -f "$body"
}

# require_json_type <json> <type> <context>
# Fails with the offending payload when the response is not the shape the
# caller is about to index into.
require_json_type() {
  local json="$1" expected="$2" context="$3"
  if ! jq -e --arg t "$expected" 'type == $t' <<<"$json" >/dev/null 2>&1; then
    echo "::error::${context}: expected a JSON ${expected}, got:" >&2
    head -c 2000 <<<"$json" >&2
    echo >&2
    return 1
  fi
}
