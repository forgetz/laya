# Laya แบบ offline (pip install laya)

ใช้ `laya` จาก PyPI ตามหน้า [huggingface.co/convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya)
แต่โหลด model มาเก็บไว้ในโฟลเดอร์ `weights/` ก่อน แล้วรันโดยไม่ต่อเน็ตเลย

| ไฟล์ | หน้าที่ |
|---|---|
| `download_model.py` | โหลด checkpoint มาไว้ที่ `weights/` (ต้องต่อเน็ต ทำครั้งเดียว) |
| `test_laya.py` | ทดสอบ laya — ใส่ `--weights weights` เพื่อรันแบบ offline |
| `app.py` | API gateway (FastAPI) ส่งค่าเข้า laya — ดู[ข้อ 6](#6-api-gateway-apppy) |
| `Dockerfile` | image ของ gateway ที่โหลด model มาตอน build |
| `requirements.txt` | laya + fastapi + uvicorn สำหรับ gateway |
| `compose.yaml` | Docker Compose สำหรับ build + รัน gateway |
| `certs/` | วาง root CA ขององค์กร (`*.crt`) ถ้า proxy ถอด TLS — ดู[ข้อ 7](#7-ใช้หลัง-proxy-ขององค์กร) |

คำสั่งด้านล่างเขียนสำหรับ Windows (PowerShell / Git Bash) และรันจากในโฟลเดอร์ `src/`
บน Linux/macOS ให้เปลี่ยน `.venv/Scripts/python` เป็น `.venv/bin/python`

---

## 1. ติดตั้ง (ต้องต่อเน็ต)

ต้องใช้ Python 3.10 ขึ้นไป

```bash
cd src
python -m venv .venv
.venv/Scripts/python -m pip install laya
```

## 2. โหลด model มาไว้ที่ `weights/` (ต้องต่อเน็ต)

```bash
.venv/Scripts/python download_model.py
```

โหลด `english` + `multilingual` ประมาณ **1.4 GB** (ลองจริงใช้ราว 4 นาที) ได้โครงนี้:

```
weights/convaiinnovations/laya/
├── rl_agent_config.json
├── model.safetensors
├── tokenizer/            ← tokenizer.json, tokenizer_config.json
├── encoder/              ← config.json
└── multilingual/         ← ข้างในมี 4 อย่างเหมือนกัน
```

ตัวเลือกเพิ่มเติม:

```bash
.venv/Scripts/python download_model.py --models english,multilingual,typed-decisions  # เอาครบ 3 ตัว
.venv/Scripts/python download_model.py --revision <commit-sha>                       # pin version
.venv/Scripts/python download_model.py --verify                                      # เช็คว่าครบ ไม่ใช้เน็ต
```

`--verify` บอกเป็นรายไฟล์ว่าอะไรขาด และคืน exit code 1 ถ้าไม่ครบ
ถ้าโดนจำกัด rate จาก Hub ให้ตั้ง `HF_TOKEN` ก่อนรัน

> `encoder/` ขาดไม่ได้ — ถ้าไม่มี laya จะไปโหลด config ของ base encoder จาก Hub
> ทำให้ยังต้องใช้เน็ตทั้งที่ไฟล์อื่นครบแล้ว

สคริปต์จะทิ้ง `weights/convaiinnovations/laya/.cache/` ไว้ด้วย (ไว้ resume ตอนโหลดซ้ำ)
ตอนรันไม่ได้ใช้ ลบทิ้งได้

## 3. รันแบบ offline

```bash
.venv/Scripts/python test_laya.py --weights weights
```

ผลที่ได้ (ลองจริงบน CPU, `HF_HOME` ชี้ไปโฟลเดอร์ว่างเพื่อยืนยันว่าไม่ได้ใช้ cache หรือเน็ต):

```
offline, weights from ...\src\weights
[Router] 7883 ms (includes first load)
  model      : english
  department : billing
  urgency    : 1.7722
  churn_risk : 0.879
[Router, Thai]
  model      : multilingual
  department : billing
  churn_risk : 0.0346
[laya.load] 549 ms
  ...
OK
```

`--weights` ทำ 2 อย่างก่อน import laya:

1. ตั้ง `HF_HUB_OFFLINE=1` — ตัดทุก request ไป Hub ถ้าไฟล์ขาดจะ error ทันที ไม่ค้างรอ timeout
2. `cd` เข้า `weights/` — `Router()` เรียก model ด้วยชื่อ `convaiinnovations/laya` และ laya จะเช็คก่อนว่า
   ชื่อนั้นเป็นโฟลเดอร์ที่มีอยู่จริงหรือเปล่า (relative กับ cwd) ถ้าใช่ก็โหลดจากไฟล์เลย ไม่แตะ Hub

## 4. ใช้ในโค้ดของคุณเอง

```python
import os
os.environ["HF_HUB_OFFLINE"] = "1"       # ต้องตั้งก่อน import laya
os.chdir(r"C:\path\to\src\weights")       # โฟลเดอร์ที่มี convaiinnovations/ อยู่ข้างใน

from laya import Router
router = Router()
result = router.predict("We were billed twice, refund or we cancel.", {
    "churn_risk": {"type": "noul", "instructions": "Does the user threaten to cancel or leave?"},
})
print(result["answers"]["churn_risk"]["noul"])
```

ถ้าไม่อยาก `chdir` และใช้ checkpoint ตัวเดียว ให้ใส่ path เต็มกับ `laya.load` ได้เลย:

```python
import laya
agent = laya.load(r"C:\path\to\src\weights\convaiinnovations\laya")                # english
agent_ml = laya.load(r"C:\path\to\src\weights\convaiinnovations\laya\multilingual")  # multilingual
```

หรือตั้งจาก shell แทนในโค้ด:

```powershell
# PowerShell
$env:HF_HUB_OFFLINE = "1"
```

```bash
# Git Bash / Linux
export HF_HUB_OFFLINE=1
```

## 5. ย้ายไปเครื่องที่ไม่มีเน็ตเลย

บนเครื่องปลายทาง `pip install laya` ใช้ไม่ได้ ต้องเตรียม 2 อย่างจากเครื่องที่มีเน็ต

```bash
# เครื่องที่มีเน็ต — OS และเวอร์ชัน Python ต้องตรงกับเครื่องปลายทาง เพราะ wheel ผูกกับ platform
pip download laya -d wheelhouse/
.venv/Scripts/python download_model.py
```

คัดลอก `wheelhouse/`, `weights/` และไฟล์ `.py` ในโฟลเดอร์นี้ไปที่เครื่องปลายทาง แล้ว:

```bash
# เครื่อง offline
python -m venv .venv
.venv/Scripts/python -m pip install --no-index --find-links wheelhouse/ laya
.venv/Scripts/python download_model.py --verify    # ไม่ใช้เน็ต
.venv/Scripts/python test_laya.py --weights weights
```

## 6. API gateway (`app.py`)

HTTP API ครอบ `Router` ของ laya ใช้ `weights/` แบบ offline เหมือนข้อ 3

| Method | Path | Body |
|---|---|---|
| `GET` | `/health` | – แสดง checkpoint ที่โหลดแล้ว |
| `POST` | `/predict` | `{"state": ..., "questions": {...}, "model"?: "english", "lang"?: "th", "min_confidence"?: 0.5}` |
| `POST` | `/predict/batch` | `{"requests": [<body แบบ /predict>, ...]}` (สูงสุด 256) |

ผลที่ได้คือ dict ที่ `router.predict()` คืนมาตรง ๆ (`answers`, `routing`, ...)
ถ้าไม่ส่ง `model` จะเลือก checkpoint ตามภาษาให้เอง

ตัวแปรตั้งค่า:

| ตัวแปร | default | ความหมาย |
|---|---|---|
| `LAYA_WEIGHTS` | `./weights` ข้าง `app.py` | โฟลเดอร์ที่มี `convaiinnovations/` อยู่ข้างใน |
| `LAYA_MODELS` | `english,multilingual` | checkpoint ที่โหลดตอน start และยอมให้เรียก (ตัวอื่นตอบ 400) |
| `LAYA_DEVICE` | ให้ laya เลือก | `cpu` / `cuda` / `mps` |
| `LAYA_API_KEY` | ว่าง = ไม่ต้องใช้ key | ถ้าตั้ง ทุก endpoint ยกเว้น `/health` ต้องส่ง `Authorization: Bearer <key>` |

รันบนเครื่อง (หลังทำข้อ 1–2):

```bash
.venv/Scripts/python -m pip install -r requirements.txt
HF_HUB_OFFLINE=1 .venv/Scripts/uvicorn app:app --port 8080
```

### รันเป็น container — build แล้วได้ model ติดมาใน image

```bash
docker build -t laya-gateway src
docker run -d --name laya-gateway -p 8080:8080 -e LAYA_API_KEY=changeme laya-gateway
```

- ตอน **build** `Dockerfile` จะรัน `download_model.py` โหลด model ลง `/app/weights` ใน image เลย
  (ต้องต่อเน็ตตอน build) ส่วนตอน **run** ตั้ง `HF_HUB_OFFLINE=1` ไว้ ไม่ต่อ Hub อีก
- ขั้นโหลด model เป็น layer แยกก่อน copy `app.py` แก้ gateway แล้ว build ใหม่จึงไม่โหลด 1.4 GB ซ้ำ
- build arg: `--build-arg MODELS=english,multilingual,typed-decisions`, `--build-arg REVISION=<sha>`
- ใช้ HF token ตอน build โดยไม่ให้ติดไปใน image: `docker build --secret id=hf_token,env=HF_TOKEN ...`
- torch ใช้ wheel CPU จาก index ของ PyTorch (ของ PyPI บน Linux เป็น build CUDA ใหญ่หลาย GB)
- container รันเป็น UID 10001 และมี `HEALTHCHECK` ยิง `/health`
- ลองจริง: build ใช้ราว 6 นาที (โหลด model ราว 4 นาที) image ขนาด 4.6 GB, container healthy
  ภายใน ~12 วินาที และรันด้วย `--network none` ได้ ยืนยันว่าไม่ต้องใช้เน็ตตอนรัน
- ย้ายไปเครื่อง offline: `docker save laya-gateway | gzip > laya-gateway.tar.gz` แล้ว
  `docker load` ที่ปลายทาง ไม่ต้องเตรียม `weights/` แยก

### รันด้วย Docker Compose (`compose.yaml`)

```bash
cd src
docker compose up -d --build --wait     # build (โหลด model) + start แล้วรอจน healthy
docker compose logs -f                  # ดู log
docker compose down                     # หยุด
```

ตั้งค่าผ่าน environment หรือไฟล์ `src/.env`:

```
LAYA_API_KEY=changeme          # ว่าง = ไม่ต้องใช้ key
LAYA_PORT=8080                 # port บน host (ที่ใช้เรียก API)
LAYA_CONTAINER_PORT=8080       # port ที่ uvicorn ฟังอยู่ใน container
LAYA_BIND_ADDRESS=127.0.0.1    # 0.0.0.0 = เปิดให้เครื่องอื่นเรียกได้ (ควรตั้ง LAYA_API_KEY ด้วย)
LAYA_MODELS=english,multilingual
LAYA_REVISION=                 # pin commit ของ model ตอน build
OMP_NUM_THREADS=4
```

- `LAYA_MODELS` / `LAYA_REVISION` มีผลตอน **build** (โหลดอะไรเข้า image) — เปลี่ยนแล้วต้อง `--build` ใหม่
- HF token ตอน build: `HF_TOKEN=hf_xxx docker compose build` — ส่งเป็น build secret ไม่ติดไปใน image
- port: `LAYA_BIND_ADDRESS:LAYA_PORT` บน host → `LAYA_CONTAINER_PORT` ใน container เช่น
  `LAYA_PORT=9000 LAYA_BIND_ADDRESS=0.0.0.0 docker compose up -d --wait` แล้วเรียก `http://<ip เครื่อง>:9000`
- ค่า default ผูก port ไว้ที่ `127.0.0.1` เท่านั้น (เครื่องอื่นเรียกไม่ได้) เพราะถ้าไม่ตั้ง `LAYA_API_KEY`
  API จะไม่มีการยืนยันตัวตน
- `restart: unless-stopped` — container ขึ้นเองหลัง reboot Docker

ทดสอบ:

```bash
curl -s localhost:8080/health
curl -s localhost:8080/predict \
  -H 'content-type: application/json' -H 'Authorization: Bearer changeme' \
  -d '{"state": "We were billed twice. Refund it or we cancel.",
       "questions": {"churn_risk": {"type": "noul", "instructions": "Does the user threaten to cancel?"}}}'
```

> **ข้อความภาษาไทยบน Windows** — ถ้าพิมพ์ภาษาไทยใน `curl -d '...'` ตรง ๆ จาก Git Bash / PowerShell
> ตัวอักษรอาจเพี้ยนก่อนถึง API (ลองจริง: ได้ `english` / `other` แทน `multilingual` / `billing`)
> ให้เขียน body เป็นไฟล์ UTF-8 แล้วส่ง `curl --data-binary @request.json -H 'content-type: application/json'`
> แทน — ปัญหาอยู่ที่ command line ไม่ใช่ที่ gateway

## 7. ใช้หลัง proxy ขององค์กร

ต้องต่อเน็ตแค่ตอน **build** (pip + โหลด model) container ที่รันแล้วไม่ต่อเน็ตเลย จึงตั้ง proxy แค่ตอน build

### Docker Compose

ใส่ใน `src/.env` (หรือ export ใน shell):

```
HTTP_PROXY=http://proxy.corp.local:8080
HTTPS_PROXY=http://proxy.corp.local:8080
NO_PROXY=localhost,127.0.0.1,.corp.local
```

```bash
docker compose build
docker compose up -d --wait
```

ถ้า proxy ต้อง login ใส่ใน URL ได้: `http://user:password@proxy.corp.local:8080`
(อักขระพิเศษใน password ต้อง URL-encode เช่น `@` → `%40`) — Docker ถือ `HTTP_PROXY` / `HTTPS_PROXY` /
`NO_PROXY` เป็น build arg พิเศษ จะ**ไม่**บันทึกลง `docker history` ของ image ส่วน `.env` อยู่ใน `.gitignore`

ไม่ตั้งตัวแปรเหล่านี้ = ไม่ส่งไปเลย (ไม่ใช่ส่งค่าว่าง) proxy ที่ตั้งไว้ใน Docker Desktop จึงยังใช้ได้ตามเดิม

### docker build ตรง ๆ

```bash
docker build \
  --build-arg HTTP_PROXY=http://proxy.corp.local:8080 \
  --build-arg HTTPS_PROXY=http://proxy.corp.local:8080 \
  -t laya-gateway src
```

### proxy ที่ถอด TLS (SSL inspection)

ถ้า build แล้วเจอ `CERTIFICATE_VERIFY_FAILED` หรือ `self-signed certificate in certificate chain`
แปลว่า proxy เซ็น certificate ใหม่ด้วย CA ขององค์กร — ขอไฟล์ root CA จากทีม IT แล้ววางใน
`src/certs/` เป็นไฟล์ PEM นามสกุล `.crt` (ดู `certs/README.md` ถ้าได้มาเป็น `.cer`) แล้ว build ใหม่
Dockerfile จะเพิ่มเข้า trust store ของระบบ และชี้ pip / huggingface_hub / requests ไปใช้ bundle นั้น

### ถ้าโหลด model ยังไม่ผ่าน

Hugging Face โหลดไฟล์ใหญ่ผ่านระบบ Xet (โดเมน `*.xethub.hf.co`) บาง proxy ปล่อย `huggingface.co`
แต่บล็อกโดเมนนี้ ให้ปิด Xet แล้วโหลดผ่าน HTTPS ธรรมดาแทน:

```bash
HF_HUB_DISABLE_XET=1 docker compose build
```

โดเมนที่ proxy ต้องอนุญาต (ลองจริงจาก log ของ proxy ตอน build):

| โดเมน | ใช้ทำอะไร |
|---|---|
| `download.pytorch.org`, `download-r2.pytorch.org` | torch (CPU wheel) |
| `pypi.org`, `files.pythonhosted.org` | laya, fastapi, uvicorn และ dependency |
| `huggingface.co` | API + ไฟล์เล็ก (config, tokenizer) |
| `cas-server.xethub.hf.co` | Xet — ที่อยู่ของไฟล์ model ใหญ่ (ปิดได้ด้วย `HF_HUB_DISABLE_XET=1`) |
| `us.aws.cdn.hf.co` (หรือ `*.cdn.hf.co` ตามภูมิภาค) | CDN ที่ส่งเนื้อไฟล์ model |

ลองจริง: build แบบ `--no-cache` ผ่าน proxy ทดสอบ ทุก request ออกผ่าน proxy ตามตารางนี้ ผ่านใน ~7 นาที
และตรวจแล้วว่า URL ของ proxy ไม่ติดไปใน `docker history` หรือ env ของ image

### ข้อควรรู้เรื่อง proxy

- **ดึง base image (`python:3.11-slim`)** ทำโดย Docker daemon ไม่ได้ใช้ตัวแปรข้างบน — ตั้งที่
  Docker Desktop → Settings → Resources → Proxies หรือบน Linux ตั้ง `proxies` ใน `/etc/docker/daemon.json`
  หรือ drop-in ของ systemd แล้ว restart docker
- **proxy ที่ `127.0.0.1` บน host** — ขั้น build อยู่ใน network แยก มองไม่เห็น localhost ของ host
  ใช้ `host.docker.internal` (Docker Desktop) หรือ IP จริงของเครื่องแทน
- **รันนอก Docker** (`download_model.py`, `pip install`): ตั้ง `HTTPS_PROXY` / `HTTP_PROXY` ใน shell
  ได้เหมือนกัน ถ้ามี CA ขององค์กรให้ตั้ง `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` / `PIP_CERT` ชี้ไปที่ไฟล์นั้นด้วย

```powershell
# PowerShell
$env:HTTPS_PROXY = "http://proxy.corp.local:8080"
$env:HTTP_PROXY  = "http://proxy.corp.local:8080"
.venv/Scripts/python download_model.py
```

## ข้อควรรู้

- **รันครั้งแรกช้ากว่าปกติ** — ครั้งแรกต้องโหลด model เข้าหน่วยความจำ (ข้างบนราว 8 วินาที)
  ครั้งต่อไปใน process เดียวกันเหลือไม่ถึง 1 วินาที
- **warning เรื่อง temperature** — ทุกครั้งที่โหลดจะเห็น
  `this checkpoint ships invalid temperatures ... choice:11+ ... -> 0.5` เป็นค่าจากตัว checkpoint เอง
  ใช้งานได้ปกติ แต่ค่า confidence ของคำถาม `choice` ที่มีตัวเลือก 11 ข้อขึ้นไปยังไม่ได้ calibrate
- **ภาษาไทยกับ churn_risk** — ข้อความทดสอบภาษาไทย ("...ไม่งั้นจะยกเลิกแพ็กเกจ") ได้ `churn_risk` 0.035
  ขณะที่ข้อความเดียวกันภาษาอังกฤษได้ 0.879 ผลนี้เหมือนกันทั้ง online และ offline
  ถ้าจะใช้กับลูกค้าไทยควรทดสอบคำถามของตัวเองก่อน
- `weights/` และ `.venv/` อยู่ใน `.gitignore` ของ repo แล้ว ไม่ถูก commit
