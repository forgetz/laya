"""Check download_model's comparison with the Hub. No network, no checkpoints.

    python test_download_model.py
"""
import hashlib
import os
import tempfile
from types import SimpleNamespace as NS

from download_model import matches_hub, read_revisions, record_revisions, stale_files

SMALL, BIG = b"small config\n", b"pretend weights"
info = NS(siblings=[
    NS(rfilename="rl_agent_config.json", size=len(SMALL), lfs=None,
       blob_id=hashlib.sha1(b"blob %d\0" % len(SMALL) + SMALL).hexdigest()),
    NS(rfilename="model.safetensors", size=len(BIG), lfs=NS(sha256=hashlib.sha256(BIG).hexdigest()), blob_id="x"),
    NS(rfilename="multilingual/model.safetensors", size=1, lfs=NS(sha256="y"), blob_id="y"),
    NS(rfilename="README.md", size=1, lfs=None, blob_id="z"),
])

with tempfile.TemporaryDirectory() as d:
    def write(name, data):
        with open(os.path.join(d, name), "wb") as f:
            f.write(data)

    # Absent files are stale; files of checkpoints nobody asked for and docs are not considered.
    assert stale_files(d, info, ["english"]) == ["rl_agent_config.json", "model.safetensors"]

    write("rl_agent_config.json", SMALL)
    write("model.safetensors", BIG)
    assert stale_files(d, info, ["english"]) == []
    assert stale_files(d, info, ["english", "multilingual"]) == ["multilingual/model.safetensors"]

    # Same size, different bytes: this is what a check on names or sizes would miss.
    write("model.safetensors", b"X" * len(BIG))
    assert not matches_hub(os.path.join(d, "model.safetensors"), info.siblings[1])
    write("rl_agent_config.json", b"X" * len(SMALL))
    assert stale_files(d, info, ["english"]) == ["rl_agent_config.json", "model.safetensors"]

    # Updating one checkpoint keeps the record of the others.
    record_revisions(d, ["english", "multilingual"], "aaa")
    record_revisions(d, ["english"], "bbb")
    assert read_revisions(d) == {"english": "bbb", "multilingual": "aaa"}

print("OK")
