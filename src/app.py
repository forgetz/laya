"""HTTP gateway in front of laya's Router.

    uvicorn app:app --host 0.0.0.0 --port 8080

Endpoints:
    GET  /health          -> which checkpoints are loaded
    POST /predict         -> {"state": ..., "questions": {...}, "model"?: ..., "lang"?: ...}
    POST /predict/batch   -> {"requests": [<predict body>, ...]}

Environment:
    LAYA_WEIGHTS   folder containing convaiinnovations/ (default: ./weights next to this file).
                   Set it empty to let laya use the Hugging Face cache / Hub instead.
    LAYA_MODELS    checkpoints to preload and accept (default: english,multilingual)
    LAYA_DEVICE    cpu / cuda / mps (default: laya picks)
    LAYA_API_KEY   when set, every request except /health needs `Authorization: Bearer <key>`
"""
import hmac
import os
import threading
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Union

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

HERE = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = os.environ.get("LAYA_WEIGHTS", os.path.join(HERE, "weights"))
MODELS = [m.strip() for m in os.environ.get("LAYA_MODELS", "english,multilingual").split(",") if m.strip()]
DEVICE = os.environ.get("LAYA_DEVICE") or None
API_KEY = os.environ.get("LAYA_API_KEY", "")

state: Dict[str, Any] = {}
# One forward at a time: CPU inference is already parallel inside torch, and the Router loads
# checkpoints lazily, which is not something two threads should race on.
lock = threading.Lock()


@asynccontextmanager
async def lifespan(_app):
    if WEIGHTS:
        # Router() names checkpoints "convaiinnovations/laya[/<subfolder>]", and laya resolves a
        # name that is an existing directory (relative to the working directory) before it
        # considers a download. HF_HUB_OFFLINE must already be set by then (see Dockerfile).
        os.chdir(WEIGHTS)
    from laya import Router

    router = Router(device=DEVICE)
    # Load before serving, so a missing checkpoint fails startup rather than the first request.
    router.preload(MODELS)
    state["router"] = router
    yield
    state.clear()


app = FastAPI(title="Laya gateway", lifespan=lifespan)


def require_key(authorization: Optional[str] = Header(None)):
    if not API_KEY:
        return
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token.encode(), API_KEY.encode()):
        raise HTTPException(401, "missing or invalid bearer token")


class PredictRequest(BaseModel):
    state: Union[str, Dict[str, Any], List[Any]] = Field(..., description="text, or a chat/state object")
    questions: Dict[str, Any]
    model: Optional[str] = Field(None, description="force a checkpoint; default routes by language")
    lang: Optional[str] = None
    min_confidence: Optional[float] = None


class BatchRequest(BaseModel):
    requests: List[PredictRequest] = Field(..., min_length=1, max_length=256)


def _kwargs(req: PredictRequest) -> Dict[str, Any]:
    if req.model is not None and req.model not in MODELS:
        raise HTTPException(400, "model %r is not served here; choose from %s" % (req.model, MODELS))
    kw = {"state": req.state, "questions": req.questions}
    for name in ("model", "lang", "min_confidence"):
        value = getattr(req, name)
        if value is not None:
            kw[name] = value
    return kw


def _run(fn, *args, **kwargs):
    try:
        with lock:
            return fn(*args, **kwargs)
    except (ValueError, TypeError, KeyError) as exc:
        # laya validates questions/state and raises these for bad input.
        raise HTTPException(422, "%s: %s" % (type(exc).__name__, exc))


@app.get("/health")
def health():
    router = state.get("router")
    if router is None:
        raise HTTPException(503, "starting")
    return {"status": "ok", "loaded": list(router.loaded), "models": MODELS,
            "offline": os.environ.get("HF_HUB_OFFLINE") == "1"}


@app.post("/predict", dependencies=[Depends(require_key)])
def predict(req: PredictRequest):
    kw = _kwargs(req)
    return _run(state["router"].predict, **kw)


@app.post("/predict/batch", dependencies=[Depends(require_key)])
def predict_batch(req: BatchRequest):
    items = [_kwargs(r) for r in req.requests]
    return {"results": _run(state["router"].predict_batch, items)}
