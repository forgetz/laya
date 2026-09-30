# Laya API gateway with the checkpoints baked in: the build downloads them, the container then
# runs with HF_HUB_OFFLINE=1 and never talks to the Hub.
#
#   docker build -t laya-gateway src
#   docker run --rm -p 8080:8080 laya-gateway
#
# Optional build args: MODELS (default english,multilingual), REVISION (Hub commit to pin).
# For higher Hub rate limits during the build:
#   docker build --secret id=hf_token,env=HF_TOKEN -t laya-gateway src
#
# Behind a corporate proxy:
#   docker build --build-arg HTTPS_PROXY=http://proxy.corp:8080 \
#                --build-arg HTTP_PROXY=http://proxy.corp:8080 -t laya-gateway src
# HTTP_PROXY / HTTPS_PROXY / NO_PROXY (and lowercase) are Docker's predefined build args: every
# RUN sees them without an ARG line, and they are left out of `docker history`, so credentials
# in the URL do not end up in the image. pip, huggingface_hub (httpx) and hf-xet all read them.
# A proxy that re-signs TLS needs its root CA: put the .crt file(s) in src/certs/.
# If the Hub download still fails through the proxy, add --build-arg HF_HUB_DISABLE_XET=1.
FROM python:3.11-slim-bookworm

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    TOKENIZERS_PARALLELISM=false

# Corporate root CAs, trusted before anything goes over the network. Only *.crt (PEM) files are
# picked up; with none present this is a no-op. Every client is pointed at the system bundle,
# because pip, httpx and requests would otherwise use certifi's copy and ignore the addition.
COPY certs/ /usr/local/share/ca-certificates/corp/
RUN update-ca-certificates
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt

# CPU wheel from the PyTorch index: the PyPI default on Linux is the CUDA build (several GB).
ARG TORCH_VERSION=2.14.0
ARG TORCH_INDEX=cpu
RUN pip install "torch==${TORCH_VERSION}" --index-url "https://download.pytorch.org/whl/${TORCH_INDEX}"

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt && pip check

RUN groupadd --gid 10001 laya && useradd --uid 10001 --gid laya --create-home laya \
    && chown laya:laya /app
USER laya
WORKDIR /app

# The download is its own layer, before app.py is copied, so editing the gateway does not
# re-download 1.4 GB. Owned by the runtime user so laya can patch a tokenizer config if needed.
ARG MODELS=english,multilingual
ARG REVISION=
# 1 = download through plain HTTPS instead of hf-xet's chunked protocol; the fallback when a
# proxy lets the Hub API through but not the Xet storage endpoints.
ARG HF_HUB_DISABLE_XET=
COPY --chown=laya:laya download_model.py /app/download_model.py
RUN --mount=type=secret,id=hf_token,uid=10001,required=false \
    HF_TOKEN="$(cat /run/secrets/hf_token 2>/dev/null || true)" \
    HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET}" \
    python download_model.py --out /app/weights --models "${MODELS}" \
        ${REVISION:+--revision "${REVISION}"} \
    && rm -rf /app/weights/convaiinnovations/laya/.cache

COPY --chown=laya:laya app.py /app/app.py

# Offline from here on: a missing file fails immediately instead of waiting on the network.
ENV HF_HUB_OFFLINE=1 \
    LAYA_WEIGHTS=/app/weights \
    LAYA_MODELS=${MODELS} \
    OMP_NUM_THREADS=4 \
    PORT=8080

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=2m --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['PORT'], timeout=4)"

CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
