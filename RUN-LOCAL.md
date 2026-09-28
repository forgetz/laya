# Laya — local Docker setup (CPU)

Host: Windows 11 + Docker Desktop, no NVIDIA GPU (Intel Iris Xe) → CPU wheels (`TORCH_INDEX=cpu`, torch 2.14.0).
Defaults live in `.env` (gitignored). Images: `laya-laya`, `laya-laya-serve` (1.76 GB each, shared layers).
Weights are cached in the named volume `laya_model-cache`, so only the first run downloads.

## HTTP server (`laya-serve`)

```bash
docker compose -f compose.yaml -f compose.http.yaml up -d --wait laya-serve
curl -s localhost:8000/health
curl -s localhost:8000/v1/systemone \
  -H 'content-type: application/json' \
  -H "Authorization: Bearer $LAYA_API_KEY" \
  --data @examples/docker/request.json
docker compose -f compose.yaml -f compose.http.yaml logs -f laya-serve
docker compose -f compose.yaml -f compose.http.yaml down
```

## Auth

`LAYA_API_KEY` is set in `.env`, so `/v1/systemone` requires `Authorization: Bearer <key>`
and answers `401` without it or with a wrong one. `/health` stays open — the container
healthcheck calls it. The key lives only in `.env`, which is gitignored; never copy it into
a tracked file. Recreate the container after changing it (`up -d --wait laya-serve`).

Still bound to `127.0.0.1:8000`. To let other hosts reach it, set `LAYA_BIND_ADDRESS` in
`.env` — and prefer `LAYA_API_KEY_FILE` with a mounted secret file (readable by UID 10001)
over the plain value, so the key is not in the container's environment.

`LAYA_PRELOAD=0` (the default here) means the first request per checkpoint pays for its
download and load; the server is healthy before that. Set `LAYA_PRELOAD=1` to load up front —
it pulls the whole checkpoint family on first boot.

## One-shot SDK request

The `laya` service runs the SDK directly, so it needs no API key.

```bash
docker compose run --rm laya                       # bundled examples/docker/request.json
docker compose run --rm \
  --volume "$PWD/my-request.json:/inputs/request.json:ro" \
  --env LAYA_REQUEST_FILE=/inputs/request.json laya
```

## Rebuild after pulling changes

```bash
docker compose -f compose.yaml -f compose.http.yaml build
```

## If this machine ever gets an NVIDIA GPU

Install the NVIDIA Container Toolkit, then add `-f compose.cuda.yaml` and rebuild
(the wheel index is a build arg, so a runtime `-e` cannot switch CPU↔CUDA):

```bash
docker compose -f compose.yaml -f compose.http.yaml -f compose.cuda.yaml up --build -d --wait laya-serve
```

Full option table: `docs/docker.md`.
