"""Download Laya checkpoints into a plain folder so they can be used offline.

    python download_model.py                      # english + multilingual -> ./weights
    python download_model.py --models english,multilingual,typed-decisions
    python download_model.py --verify             # check an existing folder, no network

Result (the layout `Router()` expects, relative to the folder you run from):

    weights/convaiinnovations/laya/
        rl_agent_config.json, model.safetensors, tokenizer/, encoder/
        multilingual/  (same four entries)

Only `huggingface_hub` is needed, which `pip install laya` already brings in. Set HF_TOKEN
for higher Hub rate limits.
"""
import argparse
import os
import sys

REPO = "convaiinnovations/laya"
# The published repository bundles every checkpoint; the Router addresses them by subfolder.
SUBFOLDERS = {"english": None, "multilingual": "multilingual", "typed-decisions": "typed-decisions"}
# What the loader opens. `encoder/` matters: without it laya fetches the base encoder config from
# the Hub, so an otherwise complete folder still needs the network.
ARTIFACTS = ("rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*")
REQUIRED = ("rl_agent_config.json", "model.safetensors", "tokenizer/tokenizer.json",
            "tokenizer/tokenizer_config.json", "encoder/config.json")
HERE = os.path.dirname(os.path.abspath(__file__))


def checkpoint_dir(out, model):
    root = os.path.join(out, *REPO.split("/"))
    return os.path.join(root, SUBFOLDERS[model]) if SUBFOLDERS[model] else root


def missing_files(out, models):
    return ["%s: %s" % (m, rel) for m in models for rel in REQUIRED
            if not os.path.exists(os.path.join(checkpoint_dir(out, m), *rel.split("/")))]


def folder_size(path):
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(path) for f in fs)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=os.path.join(HERE, "weights"),
                   help="folder to create convaiinnovations/ under (default: src/weights)")
    p.add_argument("--models", default="english,multilingual",
                   help="comma list of %s" % "/".join(SUBFOLDERS))
    p.add_argument("--revision", help="commit SHA, branch or tag (default: latest)")
    p.add_argument("--verify", action="store_true", help="only check the folder; no download")
    args = p.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    bad = [m for m in models if m not in SUBFOLDERS]
    if bad or not models:
        p.error("unknown or empty --models %s; choose from %s" % (bad, ", ".join(SUBFOLDERS)))
    out = os.path.abspath(args.out)

    if not args.verify:
        from huggingface_hub import snapshot_download

        # One snapshot for all requested checkpoints. `fnmatch` anchors at the start of the path,
        # so the root patterns do not pull in the subfolders of checkpoints nobody asked for.
        patterns = []
        for m in models:
            prefix = SUBFOLDERS[m] + "/" if SUBFOLDERS[m] else ""
            patterns += [prefix + a for a in ARTIFACTS]
        target = os.path.join(out, *REPO.split("/"))
        print("downloading %s -> %s" % (", ".join(models), target))
        snapshot_download(REPO, allow_patterns=patterns, local_dir=target,
                          revision=args.revision, token=os.environ.get("HF_TOKEN") or None)

    missing = missing_files(out, models)
    if missing:
        print("\nINCOMPLETE:")
        for item in missing:
            print("  " + item)
        return 1
    print("\nOK: %s in %s (%.1f GB)" % (", ".join(models), out, folder_size(out) / 1024 ** 3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
