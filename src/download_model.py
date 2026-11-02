"""Download Laya checkpoints into a plain folder so they can be used offline.

    python download_model.py                      # english + multilingual -> ./weights
    python download_model.py --models english,multilingual,typed-decisions
    python download_model.py --verify             # check an existing folder, no network
    python download_model.py --check              # compare the folder with the Hub, no download

Result (the layout `Router()` expects, relative to the folder you run from):

    weights/convaiinnovations/laya/
        rl_agent_config.json, model.safetensors, tokenizer/, encoder/
        multilingual/  (same four entries)
        revisions.json  (the Hub commit each checkpoint was last verified against)

Only `huggingface_hub` is needed, which `pip install laya` already brings in. Set HF_TOKEN
for higher Hub rate limits.
"""
import argparse
import fnmatch
import hashlib
import json
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
REVISIONS_FILE = "revisions.json"
HERE = os.path.dirname(os.path.abspath(__file__))


def checkpoint_dir(out, model):
    root = os.path.join(out, *REPO.split("/"))
    return os.path.join(root, SUBFOLDERS[model]) if SUBFOLDERS[model] else root


def missing_files(out, models):
    return ["%s: %s" % (m, rel) for m in models for rel in REQUIRED
            if not os.path.exists(os.path.join(checkpoint_dir(out, m), *rel.split("/")))]


def patterns_for(models):
    # `fnmatch` anchors at the start of the path, so the root patterns do not pull in the
    # subfolders of checkpoints nobody asked for.
    patterns = []
    for m in models:
        prefix = SUBFOLDERS[m] + "/" if SUBFOLDERS[m] else ""
        patterns += [prefix + a for a in ARTIFACTS]
    return patterns


def file_hash(path, algo, header=b""):
    digest = hashlib.new(algo, header)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 ** 2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def matches_hub(path, sibling):
    """Whether the local file is byte-for-byte the one on the Hub, from the digest the Hub reports."""
    if not os.path.isfile(path) or os.path.getsize(path) != sibling.size:
        return False
    if sibling.lfs:
        return file_hash(path, "sha256") == sibling.lfs.sha256
    # Files outside LFS only carry their git blob id, which is the SHA-1 of a header plus the bytes.
    return file_hash(path, "sha1", b"blob %d\0" % sibling.size) == sibling.blob_id


def stale_files(target, info, models):
    """Hub files the requested checkpoints need that are absent or different under `target`."""
    patterns = patterns_for(models)
    return [s.rfilename for s in info.siblings
            if any(fnmatch.fnmatch(s.rfilename, p) for p in patterns)
            and not matches_hub(os.path.join(target, *s.rfilename.split("/")), s)]


def read_revisions(target):
    try:
        with open(os.path.join(target, REVISIONS_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def record_revisions(target, models, sha):
    revisions = read_revisions(target)
    revisions.update({m: sha for m in models})
    with open(os.path.join(target, REVISIONS_FILE), "w", encoding="utf-8") as f:
        json.dump(revisions, f, indent=2, sort_keys=True)


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
    p.add_argument("--check", action="store_true",
                   help="compare the folder with the Hub; no download, exit 1 if it is behind")
    args = p.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    bad = [m for m in models if m not in SUBFOLDERS]
    if bad or not models:
        p.error("unknown or empty --models %s; choose from %s" % (bad, ", ".join(SUBFOLDERS)))
    out = os.path.abspath(args.out)

    target = os.path.join(out, *REPO.split("/"))
    token = os.environ.get("HF_TOKEN") or None

    if not args.verify:
        from huggingface_hub import HfApi, hf_hub_download, snapshot_download

        # Resolve "latest" to one commit up front, so every file below comes from the same
        # snapshot even if the Hub moves mid-download, and carries the digests to compare with.
        info = HfApi().model_info(REPO, revision=args.revision, files_metadata=True, token=token)
        print("hub revision: %s%s" % (info.sha, " (requested)" if args.revision else " (latest)"))

        if args.check:
            stale = stale_files(target, info, models)
            if stale:
                print("\nBEHIND the Hub, run update_model.bat:")
                for name in stale:
                    print("  " + name)
                return 1
            print("\nUP TO DATE: %s match %s" % (", ".join(models), info.sha))
            return 0

        print("downloading %s -> %s" % (", ".join(models), target))
        snapshot_download(REPO, allow_patterns=patterns_for(models), local_dir=target,
                          revision=info.sha, token=token)
        # snapshot_download trusts its own cache metadata and file times, so a local file changed
        # behind its back can be skipped. Fetch again whatever does not match the Hub's digest.
        for name in stale_files(target, info, models):
            print("re-downloading " + name)
            hf_hub_download(REPO, name, local_dir=target, revision=info.sha, token=token,
                            force_download=True)
        stale = stale_files(target, info, models)
        if stale:
            print("\nMISMATCH with the Hub:")
            for name in stale:
                print("  " + name)
            return 1
        record_revisions(target, models, info.sha)

    missing = missing_files(out, models)
    if missing:
        print("\nINCOMPLETE:")
        for item in missing:
            print("  " + item)
        return 1
    print("\nOK: %s in %s (%.1f GB)" % (", ".join(models), out, folder_size(out) / 1024 ** 3))
    revisions = read_revisions(target)
    for m in models:
        print("  %s: revision %s" % (m, revisions.get(m, "unknown (run update_model.bat to record it)")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
