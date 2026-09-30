"""Smoke test for the PyPI `laya` package, following https://huggingface.co/convaiinnovations/laya.

    python -m venv .venv && .venv/Scripts/python -m pip install laya
    .venv/Scripts/python test_laya.py

Checkpoints download from the Hub on first use (into the Hugging Face cache).

Offline, from the folder `download_model.py` wrote (see README.md):

    .venv/Scripts/python test_laya.py --weights weights
"""
import argparse
import os
import time

ap = argparse.ArgumentParser()
ap.add_argument("--weights", help="folder containing convaiinnovations/; runs fully offline")
cli = ap.parse_args()
if cli.weights:
    # Before laya (and huggingface_hub) is imported: the flag is read at import time.
    os.environ["HF_HUB_OFFLINE"] = "1"
    # Router() asks for "convaiinnovations/laya", which laya resolves as a path relative to the
    # working directory before it considers a download.
    os.chdir(cli.weights)
    print("offline, weights from", os.getcwd())

import laya  # noqa: E402
from laya import Router  # noqa: E402

state = ("Hi, we were billed twice for March. Please refund the duplicate today "
         "or we will cancel our plan.")
questions = {
    "department": {"type": "choice", "instructions": "Which department should handle this?",
                   "criteria": {"billing": "invoices, payments, refunds",
                                "technical": "bugs, outages, system errors",
                                "other": "everything else"}},
    "urgency": {"type": "score", "instructions": "How urgent is this?",
                "criteria": ["not urgent", "soon", "blocking"]},
    "churn_risk": {"type": "noul", "instructions": "Does the user threaten to cancel or leave?"},
}

print("laya", getattr(laya, "__version__", "?"))

# 1. Route mode (recommended on the model card)
router = Router()
t = time.perf_counter()
result = router.predict(state, questions)
print("\n[Router] %.0f ms (includes first load)" % ((time.perf_counter() - t) * 1000))
answers = result["answers"]
print("  model      :", result["routing"]["model"])
print("  department :", answers["department"]["choice"])
print("  urgency    :", answers["urgency"]["score"])
print("  churn_risk :", answers["churn_risk"]["noul"])
assert answers["department"]["choice"] == "billing", answers["department"]
assert result["routing"]["model"] == "english", result["routing"]
assert answers["churn_risk"]["noul"] > 0.5, answers["churn_risk"]

# Thai input should route to the multilingual checkpoint
thai = "โดนเก็บเงินซ้ำสองครั้งเดือนมีนาคม ขอคืนเงินวันนี้ ไม่งั้นจะยกเลิกแพ็กเกจ"
r_th = router.predict(thai, questions)
print("\n[Router, Thai]")
print("  model      :", r_th["routing"]["model"])
print("  department :", r_th["answers"]["department"]["choice"])
print("  churn_risk :", r_th["answers"]["churn_risk"]["noul"])

# 2. Single-model mode
agent = laya.load("convaiinnovations/laya")
t = time.perf_counter()
single = agent.predict(state, questions)["answers"]
print("\n[laya.load] %.0f ms" % ((time.perf_counter() - t) * 1000))
print("  department :", single["department"]["choice"])
print("  urgency    :", single["urgency"]["score"])
print("  churn_risk :", single["churn_risk"]["noul"])
assert single["department"]["choice"] == "billing", single["department"]

print("\nOK")
