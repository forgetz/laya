"""Populate a plain checkpoint directory that `compose.offline.yaml` can mount.

Run this once on a host with network access, then copy the result to the air-gapped host:

    python scripts/fetch_offline_checkpoints.py --out ./weights
    python scripts/fetch_offline_checkpoints.py --out ./weights --verify   # no network

Why a plain directory rather than a warmed Hub cache: `Agent.__init__` resolves a model spec
that names an existing directory before it considers a download, so a tree laid out as
`<out>/convaiinnovations/laya/...` needs none of the cache's `refs/`, `snapshots/` and `blobs/`
structure reproduced by hand -- which is the part that is easy to get wrong when the files are
downloaded through a browser. `snapshot_download(local_dir=...)` writes real files, not symlinks
into a blob store, so the tree survives `tar`, `scp` and a bind mount unchanged.

Only the four artifacts the loader opens are fetched, per checkpoint, matching the
`allow_patterns` in `Agent.__init__`: the bundle repository also carries sibling checkpoints,
and an unfiltered snapshot would download every one of them.

`local_dir` also leaves a `.cache/huggingface/` directory inside the tree, holding the download
metadata that lets a re-run resume instead of refetching. Nothing in the runtime reads it and it
is safe to delete before copying the tree to the serving host.
"""
import argparse
import os
import sys

# The published repository bundles all three checkpoints; `Router` addresses them by subfolder
# (`laya/router.py`). None is the repository root.
BUNDLE_REPO = "convaiinnovations/laya"
SUBFOLDERS = {
    "english": None,
    "multilingual": "multilingual",
    "typed-decisions": "typed-decisions",
}
DEFAULT_MODELS = ("english", "multilingual")

# Kept in the same order as the `allow_patterns` list in `Agent.__init__`, because that is the
# contract this script exists to satisfy.
ARTIFACTS = ("rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*")

# Paths the loader opens by name, relative to a checkpoint directory. `encoder/config.json` is
# on the list for a reason that is easy to miss: with the directory absent, `build_model()` falls
# back to `AutoConfig.from_pretrained(cfg["encoder"])`, which is a Hub id -- so an otherwise
# complete offline tree still reaches for the network on the base encoder.
REQUIRED = (
    "rl_agent_config.json",
    "model.safetensors",
    "tokenizer/tokenizer_config.json",
    "tokenizer/tokenizer.json",
    "encoder/config.json",
)


def checkpoint_dir(out: str, model: str) -> str:
    """Local directory for `model`, laid out the way the container resolves it.

    The mount point is `/home/laya/convaiinnovations`, and the container's working directory is
    `/home/laya`, so the repository id has to survive as a path: `convaiinnovations/laya`, with
    the subfolder below it exactly as the Hub stores it.
    """
    root = os.path.join(out, *BUNDLE_REPO.split("/"))
    sub = SUBFOLDERS[model]
    return os.path.join(root, sub) if sub else root


def patterns_for(models) -> list:
    """`allow_patterns` covering every requested checkpoint in one snapshot.

    Root patterns cannot leak into a subfolder: `fnmatch` anchors the pattern at the start of
    the path, so `tokenizer/*` does not match `multilingual/tokenizer/config.json`. That is what
    lets `english` and `multilingual` share a single download without pulling `typed-decisions`.
    """
    out = []
    for model in models:
        sub = SUBFOLDERS[model]
        prefix = "%s/" % sub if sub else ""
        out.extend(prefix + name for name in ARTIFACTS)
    return out


def patch_tokenizer_configs(dirs) -> bool:
    """Apply the loader's own `tokenizer_config.json` normalisation ahead of time.

    The server rewrites this file when `tokenizer_class` is unset or `extra_special_tokens` is a
    list. At revision 55cf4c4e neither published checkpoint is, so this is a no-op on a fresh
    download; it earns its place for a locally trained checkpoint or a later revision that does
    need the rewrite. Doing it here rather than in the container is what lets the bind mount stay
    read-only: on a `:ro` mount the server's own attempt degrades to a warning, and
    `AutoTokenizer` then fails with "'list' object has no attribute 'keys'", which does not name
    the cause.

    Imported rather than reimplemented so the two copies cannot drift; `laya.agent` pulls in
    torch, so a fetch-only host without it degrades to a note instead of failing the download.
    """
    try:
        from laya.agent import _fix_tokenizer_config
    except Exception as exc:                                  # noqa: BLE001 - any import failure
        print("note: tokenizer config not pre-patched (%s: %s)." % (type(exc).__name__, exc))
        print("      Mount the tree read-write and the server will patch it on first load.")
        return False
    for path in dirs:
        _fix_tokenizer_config(path)
    return True


def verify(out: str, models) -> list:
    """Missing required paths, as '<model>: <relative path>' strings. Touches no network."""
    missing = []
    for model in models:
        base = checkpoint_dir(out, model)
        for rel in REQUIRED:
            if not os.path.exists(os.path.join(base, *rel.split("/"))):
                missing.append("%s: %s" % (model, rel))
    return missing


def tree_bytes(path: str) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for fn in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fn))
            except OSError:
                pass
    return total


def human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.1f %s" % (size, unit)
        size /= 1024.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="./weights",
                        help="directory to create convaiinnovations/ under (default: ./weights)")
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS),
                        help="comma list of %s (default: %s)"
                             % ("/".join(SUBFOLDERS), ",".join(DEFAULT_MODELS)))
    parser.add_argument("--revision", default=None,
                        help="commit SHA, branch or tag to download instead of the Hub default")
    parser.add_argument("--verify", action="store_true",
                        help="check an existing tree and exit; downloads nothing")
    parser.add_argument("--no-patch", action="store_true",
                        help="skip the tokenizer_config.json normalisation (needs an rw mount)")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in models if m not in SUBFOLDERS]
    if unknown:
        parser.error("unknown checkpoint(s): %s; choose from %s"
                     % (", ".join(unknown), ", ".join(SUBFOLDERS)))
    if not models:
        parser.error("--models is empty")

    out = os.path.abspath(args.out)

    if not args.verify:
        from huggingface_hub import snapshot_download

        target = os.path.join(out, *BUNDLE_REPO.split("/"))
        print("downloading %s -> %s" % (", ".join(models), target))
        kw = {"allow_patterns": patterns_for(models), "local_dir": target}
        if args.revision:
            kw["revision"] = args.revision
        if os.environ.get("HF_TOKEN"):
            kw["token"] = os.environ["HF_TOKEN"]
        snapshot_download(BUNDLE_REPO, **kw)
        if not args.no_patch:
            patch_tokenizer_configs([checkpoint_dir(out, m) for m in models])

    missing = verify(out, models)
    if missing:
        print("\nINCOMPLETE -- the server would fail to load these:")
        for item in missing:
            print("  %s" % item)
        print("\nRe-run without --verify to fetch them.")
        return 1

    print("\nOK: %s under %s (%s)" % (", ".join(models), out, human(tree_bytes(out))))
    print("\nNext, on the host that serves:")
    print("  LAYA_WEIGHTS_PATH=%s \\" % out)
    print("    docker compose -f compose.yaml -f compose.http.yaml -f compose.offline.yaml \\")
    print("    up -d --wait laya-serve")
    print("\nLAYA_WEIGHTS_PATH names the directory containing convaiinnovations/, as above.")
    print("\nThe files must be readable by UID 10001, the user the image runs as.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
