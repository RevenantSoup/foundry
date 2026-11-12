#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
python_bin="${SMOKE_PYTHON:-$repo_root/.venv/bin/python}"
if [[ ! -x "$python_bin" ]]; then python_bin=python3; fi
base_url="${FOUNDRY_SMOKE_URL:-http://localhost:3000}"
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT
check() {
  local label="$1"; shift
  echo "CHECK: $label"
  if "$@"; then echo "PASS: $label"; else echo "FAIL: $label" >&2; exit 1; fi
}
check "pytest" "$python_bin" -m pytest -q
check "Next.js build" npm --prefix web run build
build_args=(--build-arg BUILDKIT_INLINE_CACHE=1)
for image in foundry-assets foundry-cli foundry-web; do
  if docker image inspect "$image" >/dev/null 2>&1; then build_args+=(--cache-from "$image"); fi
done
if [[ -n "${FOUNDRY_DOCKER_CA_FILE:-}" ]]; then
  build_args+=(--secret "id=proxy_ca,src=$FOUNDRY_DOCKER_CA_FILE")
fi
check "Docker CLI build" docker build "${build_args[@]}" --target cli -t foundry-cli .
check "Docker web build" docker build "${build_args[@]}" -t foundry-web .
check "health HTTP" curl -fsS --max-time 30 "$base_url/api/health" -o "$temporary/health.json"
check "health DB" "$python_bin" -c 'import json,sys;d=json.load(open(sys.argv[1]));assert d["status"]=="ok" and d["db"]=="ok" and d["version"]' "$temporary/health.json"
code="$(curl -sS --max-time 30 -o "$temporary/catalog.html" -w '%{http_code}' "$base_url/datasets")"
check "public marketplace HTTP 200" test "$code" = 200
curl -fsS --max-time 30 "$base_url/api/datasets?limit=1" -o "$temporary/datasets.json"
curl -fsS --max-time 30 "$base_url/api/demo" -o "$temporary/demo.json"
dataset_id="$("$python_bin" -c 'import json,sys;a=json.load(open(sys.argv[1]))["items"];b=json.load(open(sys.argv[2]))["items"];d=(a or b);assert d,"Seed a labeled demo (isolated data root) or package a licensed dataset before smoke testing";print(d[0]["id"])' "$temporary/datasets.json" "$temporary/demo.json")"
code="$(curl -sS --max-time 30 -o "$temporary/detail.html" -w '%{http_code}' "$base_url/datasets/$dataset_id")"
check "public dataset detail HTTP 200" test "$code" = 200
check "dataset detail API" curl -fsS --max-time 30 "$base_url/api/datasets/$dataset_id" -o "$temporary/detail.json"
code="$(curl -sS --max-time 30 -o "$temporary/unauthorized.json" -w '%{http_code}' "$base_url/api/v1/datasets")"
check "buyer API requires key (401)" test "$code" = 401
echo "PASS: all local launch smoke checks"
