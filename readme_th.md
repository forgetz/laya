# Laya — คู่มือรัน (ภาษาไทย)

Laya เป็น **decision engine แบบ non-autoregressive** ตอบคำถามมีชนิด (typed questions) บนข้อความใด ๆ
ด้วย forward pass เดียว รองรับ 100+ ภาษารวมถึงภาษาไทย ไม่มีการ generate ข้อความ จึงไม่มีอะไรต้อง parse
และไม่มีอาการ hallucinate

เอกสารนี้เป็นวิธีรันด้วย Docker ทุกคำสั่งและผลลัพธ์ในนี้ทดสอบจริงบน Windows 11 + Docker Desktop (CPU)

---

## สารบัญ

1. [ต้องมีอะไรก่อน](#1-ต้องมีอะไรก่อน)
2. [ติดตั้ง (build image)](#2-ติดตั้ง-build-image)
3. [โหมดที่ 1 — รันครั้งเดียวจบ (one-shot)](#3-โหมดที่-1--รันครั้งเดียวจบ-one-shot)
4. [โหมดที่ 2 — HTTP server](#4-โหมดที่-2--http-server)
5. [ตั้ง API key](#5-ตั้ง-api-key)
6. [เรียก API](#6-เรียก-api)
7. [คำถาม 3 ชนิด](#7-คำถาม-3-ชนิด)
8. [อ่านผลลัพธ์](#8-อ่านผลลัพธ์)
9. [Error และ limit](#9-error-และ-limit)
10. [ตัวแปรตั้งค่า](#10-ตัวแปรตั้งค่า)
11. [รันแบบ offline](#11-รันแบบ-offline)
12. [ถ้ามี NVIDIA GPU](#12-ถ้ามี-nvidia-gpu)
13. [แก้ปัญหา](#13-แก้ปัญหา)
14. [คำสั่งที่ใช้บ่อย](#14-คำสั่งที่ใช้บ่อย)

---

## 1. ต้องมีอะไรก่อน

- **Docker Desktop** หรือ Docker Engine + **Compose v2** ขึ้นไป
- **RAM 8 GB** และ **พื้นที่ว่าง 10 GB** (image 1.76 GB + weights)
- ไม่ต้องลง Python หรือ PyTorch บนเครื่อง — อยู่ใน container ทั้งหมด
- ไม่ต้องมีบัญชี Hugging Face — checkpoint ที่ใช้เป็น public

**เรื่อง GPU:** ถ้าไม่มี NVIDIA GPU (เช่นมีแค่ Intel Iris Xe / AMD / Apple) ให้ใช้ CPU ตามเอกสารนี้
Apple MPS, AMD/ROCm และ Intel GPU **ใช้ใน container ไม่ได้** ต้องมี NVIDIA + NVIDIA Container Toolkit
เท่านั้น ดู [ข้อ 12](#12-ถ้ามี-nvidia-gpu)

เช็คว่าพร้อม:

```bash
docker --version
docker compose version
```

---

## 2. ติดตั้ง (build image)

```bash
git clone https://github.com/NandhaKishorM/laya.git
cd laya
```

สร้างไฟล์ `.env` ที่ root (ไฟล์นี้อยู่ใน `.gitignore` แล้ว ไม่หลุดขึ้น git):

```ini
# CPU
LAYA_DEVICE=cpu
LAYA_TORCH_INDEX=cpu
LAYA_MODEL=auto
OMP_NUM_THREADS=8          # ตั้งไม่เกินจำนวน core จริง

# HTTP server
LAYA_PORT=8000
LAYA_BIND_ADDRESS=127.0.0.1
LAYA_PRELOAD=0
LAYA_LOG_LEVEL=info
```

แล้ว build:

```bash
docker compose -f compose.yaml -f compose.http.yaml build
```

ใช้เวลาหลายนาที (ดาวน์โหลด torch wheel) ได้ image 2 ตัว ขนาด 1.76 GB ใช้ layer ร่วมกัน:

```
laya-laya          1.76GB     # one-shot
laya-laya-serve    1.76GB     # HTTP server
```

> **`OMP_NUM_THREADS`** ตั้งเกิน physical core จะช้าลงอย่างเห็นได้ชัด ไม่ใช่เร็วขึ้น
> เครื่อง 12 core ตั้ง 8 กำลังดี

---

## 3. โหมดที่ 1 — รันครั้งเดียวจบ (one-shot)

เหมาะกับลองเล่น หรือ batch job ที่ไม่ต้องมี server ค้างไว้ **ไม่ต้องใช้ API key**

```bash
docker compose run --rm laya
```

ใช้ไฟล์ตัวอย่าง `examples/docker/request.json` แล้วพิมพ์ JSON ออกมา
**รอบแรกจะดาวน์โหลด checkpoint (หลายนาที)** รอบต่อไปใช้ของที่ cache ไว้

ผลลัพธ์จริง (ตัดมาบางส่วน):

```json
{
  "answers": {
    "department":       {"choice": "billing", "answer_confidence": 0.9419},
    "urgency":          {"score": 1.0057, "legend": {"0": "not urgent", "1": "needs attention soon", "2": "critical"}},
    "refund_requested": {"noul": 0.8838}
  },
  "usage":   {"input_tokens": 167, "output_tokens": 0},
  "routing": {"model": "english", "reason": "English Latin text"}
}
```

ใช้ไฟล์คำขอของตัวเอง:

```bash
docker compose run --rm \
  --volume "$PWD/my-request.json:/inputs/request.json:ro" \
  --env LAYA_REQUEST_FILE=/inputs/request.json laya
```

---

## 4. โหมดที่ 2 — HTTP server

เหมาะกับใช้งานจริง — โหลด model ค้างไว้ รับคำขอซ้ำ ๆ ได้เร็ว

```bash
docker compose -f compose.yaml -f compose.http.yaml up -d --wait laya-serve
```

`--wait` จะรอจน healthcheck ผ่านก่อนคืน prompt เช็คสถานะ:

```bash
docker compose -f compose.yaml -f compose.http.yaml ps
curl -s localhost:8000/health
```

```
laya-laya-serve-1   Up (healthy)   127.0.0.1:8000->8000/tcp
{"status":"ok","loaded":["english"],"device":"cpu","checkpoint_devices":{"english":"cpu"}}
```

ดู log / ปิด:

```bash
docker compose -f compose.yaml -f compose.http.yaml logs -f laya-serve
docker compose -f compose.yaml -f compose.http.yaml down
```

**`LAYA_PRELOAD=0`** (ค่าที่แนะนำไว้ข้างบน) = server พร้อมทันที แต่คำขอแรกของแต่ละ checkpoint
ต้องรอดาวน์โหลด+โหลด model เอง จะเห็นว่า `loaded` ใน `/health` ค่อย ๆ เพิ่มขึ้นตามการใช้งาน
ตั้ง `LAYA_PRELOAD=1` ถ้าอยากโหลดล่วงหน้า แต่บูตแรกจะดึง checkpoint **ทั้งตระกูล**

---

## 5. ตั้ง API key

API **ไม่มี auth เลย** จนกว่าจะตั้ง `LAYA_API_KEY` ด้วยเหตุนี้ `compose.http.yaml` จึงผูก port
ไว้กับ `127.0.0.1` เท่านั้นเป็นค่าเริ่มต้น

เพิ่มใน `.env`:

```ini
LAYA_API_KEY=ใส่คีย์ของคุณที่นี่
```

แล้ว **recreate container** — แก้ `.env` เฉย ๆ ไม่มีผลกับ container ที่รันอยู่:

```bash
docker compose -f compose.yaml -f compose.http.yaml up -d --wait laya-serve
```

ตรวจว่าบังคับใช้จริง (ต้องได้ `401`):

```bash
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/v1/systemone \
  -H 'content-type: application/json' --data @examples/docker/request.json
```

**ข้อควรรู้**

- `/health` **เปิดไว้เสมอ** ไม่ต้องใส่ key เพราะ healthcheck ของ container เรียกเอง — แต่ก็หมายความว่า
  ใครเข้าถึง port ได้จะเห็นว่ามี checkpoint อะไรโหลดอยู่
- อย่าเขียนคีย์ลงไฟล์ที่ track ใน git ให้อยู่ใน `.env` เท่านั้น
- ถ้าจะเปิดให้เครื่องอื่นเรียก: ตั้ง `LAYA_API_KEY` **ก่อน** แล้วค่อยแก้ `LAYA_BIND_ADDRESS`
  และควรใช้ `LAYA_API_KEY_FILE` ชี้ไปไฟล์ secret ที่ mount เข้ามา (UID 10001 ต้องอ่านได้) แทนการใส่ค่าตรง ๆ
  — entrypoint จะอ่านไฟล์ตอน start แล้วลบตัวแปร `_FILE` ทิ้ง คีย์จะไม่ค้างใน environment ของ container

---

## 6. เรียก API

มีแค่ **2 endpoint**

| Endpoint | Auth | ใช้ทำอะไร |
|---|---|---|
| `GET /health` | ไม่ต้อง | สถานะ + checkpoint ที่โหลดอยู่ |
| `POST /v1/systemone` | ต้องมี Bearer | ถามคำถาม (ยัดได้ถึง 64 ข้อในคำขอเดียว) |

ไม่มี endpoint batch แยก — ถ้าจะถามหลายข้อให้ใส่ใน `questions` ของคำขอเดียว จะใช้ forward pass ร่วมกัน

### curl

```bash
curl -s localhost:8000/v1/systemone \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <คีย์ของคุณ>' \
  -d '{
  "state": "I was charged twice this month, I want my money back today or I cancel",
  "questions": {
    "queue":   {"type":"choice","instructions":"Which team?",
                "criteria":{"billing":"billing and refunds","tech":"login and app issues","other":"everything else"}},
    "urgency": {"type":"score","instructions":"How urgent?",
                "criteria":["calm","firm","angry","furious"]},
    "churn":   {"type":"noul","instructions":"Does the user threaten to cancel?"}
  }}'
```

ผลจริง:

```
queue  : billing   (answer_confidence 0.952)
urgency: 1.56      legend {0:calm, 1:firm, 2:angry, 3:furious}
churn  : 0.882
routing: english | "English Latin text"
usage  : {input_tokens: 140, output_tokens: 0}
```

### ภาษาไทย — router เลือก checkpoint ให้เอง

ไม่ต้องใส่ `model` เลย Laya ตรวจ script และภาษาแล้วส่งข้อความที่ไม่ใช่อังกฤษไป `laya-multilingual` อัตโนมัติ

```bash
curl -s localhost:8000/v1/systemone \
  -H 'content-type: application/json' -H 'Authorization: Bearer <คีย์ของคุณ>' \
  -d '{
  "state": {"body":"ถูกตัดเงินค่าสมาชิกซ้ำสองรอบ ขอเงินคืนด่วนวันนี้ ไม่งั้นจะยกเลิกบริการ"},
  "questions": {
    "department":  {"type":"choice","instructions":"แผนกไหนควรรับเรื่องนี้?",
                    "criteria":{"billing":"ใบแจ้งหนี้ การชำระเงิน การคืนเงิน",
                                "technical":"บั๊ก ระบบล่ม","sales":"ราคา สัญญาใหม่"}},
    "churn_risk":  {"type":"noul","instructions":"ผู้ใช้ขู่จะยกเลิกบริการหรือไม่?"}
  }}'
```

ผลจริง:

```json
{
  "answers": {
    "department": {"choice": "billing", "probabilities": {"billing": 0.9267, "technical": 0.0628, "sales": 0.0105}},
    "churn_risk": {"noul": 1.0}
  },
  "routing": {
    "model": "multilingual",
    "reason": "non-Latin script (thai, 100% of letters); the English checkpoint cannot read it"
  }
}
```

> **เขียน `criteria` ให้ละเอียด** ผลแม่นกว่ามาก ในการทดสอบ คำอธิบายสั้น ๆ แบบคำเดียวให้คำตอบผิดได้
> ขณะที่คำอธิบายที่ยกตัวอย่างชัดเจน (เช่น `"ใบแจ้งหนี้ การชำระเงิน การคืนเงิน"` แทนที่จะเป็น `"การเงิน"`)
> ตอบถูกที่ความเชื่อมั่น 0.93

### `state` ใส่ได้ทั้ง string และ object

```json
"state": "ข้อความเปล่า ๆ"
"state": {"subject": "ขอคืนเงิน", "body": "...", "channel": "email"}
```

### บังคับ checkpoint และเอกสารยาว

```bash
curl -s -D- localhost:8000/v1/systemone \
  -H 'content-type: application/json' -H 'Authorization: Bearer <คีย์ของคุณ>' \
  -d '{"model":"multilingual","max_len":8192,
       "state":"<เอกสารยาว>",
       "questions":{"risk":{"type":"noul","instructions":"มีข้อกำหนดการยกเลิกสัญญาไหม?"}}}'
```

- `model` รับ `english` / `multilingual` / `typed-decisions` หรือ HF id เต็ม
  **ค่าอื่นไม่ error แต่หมายถึง "ให้ router เลือกเอง"** ปกติไม่ต้องใส่
- **`max_len` ต้องใส่เอง** ค่าเริ่มต้นคือ 1024 token ซึ่ง **ตัดเอกสารยาวทิ้งเงียบ ๆ**
  `laya-multilingual` อ่านได้ถึง 8192 แต่ความแม่นยำหลังราว 4,000 token เริ่มแปรปรวน ควรวัดกับข้อมูลตัวเอง
- ตอบกลับมาพร้อม header `server-timing: inference;dur=66.71` และ `x-inference-time-ms: 66.71`

### PowerShell (Windows)

> ใน **PowerShell 5.1** คำว่า `curl` เป็น alias ของ `Invoke-WebRequest` ถ้าจะใช้ syntax แบบ curl จริง
> ต้องพิมพ์ `curl.exe` หรือใช้วิธีนี้:

```powershell
$body = @{
  state = "I was charged twice, refund me today"
  questions = @{
    dept = @{ type="choice"; instructions="Which team?"
              criteria=@{ billing="refunds"; tech="app issues" } }
  }
} | ConvertTo-Json -Depth 6

$r = Invoke-RestMethod -Uri http://localhost:8000/v1/systemone -Method Post `
       -ContentType 'application/json' `
       -Headers @{ Authorization = 'Bearer <คีย์ของคุณ>' } -Body $body

$r.answers.dept.choice     # billing
$r.routing.model           # english
```

**`-Depth 6` จำเป็น** — `ConvertTo-Json` ใช้ depth 2 เป็นค่าเริ่มต้น ทำให้ `criteria` กลายเป็น string แล้วพัง

### Python

```python
import requests

r = requests.post(
    "http://localhost:8000/v1/systemone",
    headers={"Authorization": "Bearer <คีย์ของคุณ>"},
    json={
        "state": "ถูกตัดเงินซ้ำสองรอบ ขอคืนเงินด่วน",
        "questions": {
            "dept": {"type": "choice", "instructions": "แผนกไหน?",
                     "criteria": {"billing": "ใบแจ้งหนี้ การชำระเงิน การคืนเงิน",
                                  "technical": "บั๊ก ระบบล่ม"}},
            "urgent": {"type": "noul", "instructions": "เร่งด่วนหรือไม่?"},
        },
    },
    timeout=60,
)
r.raise_for_status()
d = r.json()
print(d["answers"]["dept"]["choice"], d["answers"]["dept"]["answer_confidence"])
print(d["routing"]["model"], d["routing"]["reason"])
```

---

## 7. คำถาม 3 ชนิด

| ชนิด | `criteria` | ได้อะไรกลับมา |
|---|---|---|
| `choice` | **object** `{ชื่อตัวเลือก: คำอธิบาย}` | `choice` (ตัวที่ prob สูงสุด) + `probabilities` รายตัวเลือก |
| `score` | **array** เรียงจากน้อยไปมาก | `score` เป็นทศนิยม (ค่าคาดหวัง อยู่ระหว่างระดับได้) + `probabilities` คีย์ `"0".."k-1"` + `legend` |
| `noul` | **ไม่ต้องมี** | `noul` = ความน่าจะเป็นที่คำตอบคือ "ใช่" |

ทุกชนิดได้ `confidence`, `answer_confidence` และ `action.act_probability` มาด้วย

```json
"urgency": {"type": "score", "instructions": "ด่วนแค่ไหน?", "criteria": ["ไม่ด่วน", "ควรรีบ", "บล็อกงาน"]}
"refund":  {"type": "noul", "instructions": "ผู้ใช้ขอเงินคืนหรือไม่?"}
```

`score` คืนค่าเป็นทศนิยม เช่น `1.56` หมายถึงอยู่ระหว่าง `firm` กับ `angry` — ถ้าต้องการระดับเดียว
ให้ปัดเอง หรือดู `probabilities` ประกอบ

---

## 8. อ่านผลลัพธ์

```json
{
  "model": "laya-rl-agent",
  "answers": {"...": "คำตอบแต่ละข้อ"},
  "usage": {"input_tokens": 140, "output_tokens": 0},
  "routing": {"model": "english", "repo": "convaiinnovations/laya",
              "reason": "English Latin text", "detection": {"script": "latin", "language": "en"}}
}
```

- `model` เป็นชื่อคงที่ของ decision head ไม่ใช่ checkpoint — **checkpoint ที่ตอบจริงอยู่ใน `routing.model`**
- `routing.reason` บอกว่าทำไมเลือก checkpoint นั้น มีประโยชน์มากเวลา debug ว่าทำไมผลไม่ตรงคาด
- `output_tokens` เป็น 0 เสมอ เพราะไม่มีการ generate

### `confidence` กับ `answer_confidence` คนละอย่าง — อย่าใช้ threshold เดียวกัน

| ฟิลด์ | ความหมาย | ใช้ทำอะไร |
|---|---|---|
| `answer_confidence` | `max(p)` ความน่าจะเป็นของคำตอบที่เลือก | **ตัวนี้คือตัวที่ calibrate ไว้** ใช้ตั้ง threshold |
| `confidence` | `choice`/`score`: normalized entropy `1 - H(p)/log(k)` — `noul`: เท่ากับ `answer_confidence` | คนละสเกล ใช้วัดความกระจายของ probability |

**ข้อควรระวัง** ตอนโหลด checkpoint อาจเห็น warning นี้ใน log:

```
RuntimeWarning: laya: this checkpoint ships invalid temperatures or values outside [0.5, 5];
using choice:11+=0.1005... -> 0.5. Treat confidence from the affected entries as uncalibrated.
```

เป็นเรื่องของ checkpoint ต้นทาง ไม่ใช่การตั้งค่าผิด — แปลว่า `confidence` ของ entry ที่ได้รับผลกระทบ
**ยังไม่ calibrate** ตัว `choice` / `noul` ไม่กระทบ ถ้าจะเอา `answer_confidence` ไปตัดสินใจอัตโนมัติ
ต้องวัดกับข้อมูลของตัวเองก่อน ดู `BENCHMARKS.md`

> **ถ้าย้ายมาจาก TypeSafe Jev:** Jev นิยาม confidence เป็น `(n*p_max - 1)/(n - 1)`
> threshold เดิมจะให้ผลต่างกันบน Laya

---

## 9. Error และ limit

ทดสอบจริงแล้วทั้งหมด:

| ส่งอะไร | ได้ |
|---|---|
| ไม่มี key / key ผิด | `401 invalid or missing bearer token` |
| JSON พัง | `400 request body must be valid JSON` |
| ไม่มี `questions` | `400 request body must be an object with a 'questions' field` |
| `state` เป็น `null` หรือไม่มี | `400 'state' is required` |
| `type` ไม่รู้จัก | `422 question 'a': unknown type 'banana'; use one of ['choice','noul','score']` |
| ตัวเลือกยาวเกิน head budget | `422` บอกชื่อคำถามและสิ่งที่ต้องแก้ |
| เกิน limit ข้างล่าง | `413` บอกว่าชนข้อไหนและเกินเท่าไร |
| คำขอพร้อมกันเกิน `LAYA_MAX_CONCURRENT` | `503 server busy` + `Retry-After: 1` — **ปฏิเสธเลย ไม่ต่อคิว** |
| inference ล้มเหลวอย่างอื่น | `500 inference failed` (ข้อความคงที่เสมอ สาเหตุจริงอยู่ใน log ของ server) |

| limit | ค่า |
|---|---|
| ขนาด body | 2 MiB (บังคับตอน stream — ปลอม `Content-Length` ไม่ผ่าน) |
| `state` | 50,000 ตัวอักษร |
| จำนวนคำถามต่อคำขอ | 64 |
| ตัวเลือกต่อคำถาม `choice` | 100 |
| ระดับต่อคำถาม `score` | 32 |
| ตัวเลือกรวมทุกคำถาม | 512 |
| คำขอพร้อมกัน | 16 (`LAYA_MAX_CONCURRENT`) |

> limit ตัวเลือกเป็นการกัน amplification ที่ชั้น HTTP เท่านั้น ตัว model ยังบีบ token ตัวเลือกลง
> `head_max_len=192` อยู่ดี คำถามที่ผ่าน limit HTTP จึงยังโดน `422` ได้ถ้าข้อความตัวเลือกรวมกันเกิน budget

ถ้าได้ `500` ให้ดู log — ข้อความ error ที่ส่งกลับ client ถูกทำให้คงที่โดยเจตนา เพื่อไม่ให้ path, weight
หรือสถานะ memory หลุดออกไป:

```bash
docker compose -f compose.yaml -f compose.http.yaml logs --tail 50 laya-serve
```

---

## 10. ตัวแปรตั้งค่า

ตั้งใน `.env`, shell หรือ `environment` ของ service ก็ได้

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `LAYA_DEVICE` | `cpu` / `cuda` | device ที่ใช้ |
| `LAYA_MODEL` | `auto` | `auto` / `english` / `multilingual` / `typed-decisions` |
| `LAYA_MODEL_PATH` | ไม่ตั้ง | path ของ checkpoint ใน container (ใช้แทน `LAYA_MODEL` ตั้งพร้อมกันไม่ได้) |
| `LAYA_REQUEST_FILE` | ไฟล์ตัวอย่าง | path ไฟล์ JSON คำขอ (โหมด one-shot) |
| `OMP_NUM_THREADS` | `4` | จำนวน thread CPU — **ห้ามเกิน physical core** |
| `LAYA_PORT` | `8000` | port (ทั้งใน container และที่ publish ออกมา) |
| `LAYA_BIND_ADDRESS` | `127.0.0.1` | host ที่ผูก port |
| `LAYA_API_KEY` / `_FILE` | ไม่ตั้ง | บังคับ `Authorization: Bearer <key>` |
| `LAYA_PRELOAD` | `0` (ใน compose นี้) | `1` = โหลด checkpoint ตอน start |
| `LAYA_MODELS` | ทั้งหมด | จำกัดว่าจะ preload ตัวไหน |
| `LAYA_MAX_CONCURRENT` | `16` | คำขอพร้อมกันสูงสุด เกินได้ `503` |
| `LAYA_AUTO_TASK` | `0` | route ไป typed-decisions อัตโนมัติ |
| `LAYA_MAX_LOADED` | `2` | จำนวน checkpoint ใน memory พร้อมกัน — ตั้ง `3` ถ้าเปิด `LAYA_AUTO_TASK` ไม่งั้นจะ reload ทุกครั้งที่สลับ |
| `LAYA_CUDA_AMP` / `LAYA_CPU_AMP` | ไม่ตั้ง | `fp16`/`bf16` — ว่างไว้ = ใช้ `amp_dtype` ของ checkpoint |
| `HF_TOKEN` / `_FILE` | ไม่ตั้ง | credential Hugging Face (checkpoint public ไม่ต้องใช้) |
| `HF_HUB_OFFLINE` | `0` | `1` = ใช้แต่ของที่ cache แล้ว ไม่ยิงไป Hub เลย |
| `LAYA_WEIGHTS_PATH` | ไม่ตั้ง | **`compose.offline.yaml` เท่านั้น** — directory ที่มี `convaiinnovations/` อยู่ข้างใน ดู [ข้อ 11](#11-รันแบบ-offline) |
| `LAYA_TORCH_INDEX` | `cpu` | **build arg** — `cpu` / `cu128` / `cu130` |

> `LAYA_TORCH_INDEX` เป็น **build arg** ไม่ใช่ runtime — สลับ CPU ↔ CUDA ด้วย `-e` ไม่ได้ ต้อง rebuild

ตารางเต็มอยู่ใน `docs/docker.md` และ `docs/http-api.md`

---

## 11. รันแบบ offline

เครื่องที่รันไม่ต้องต่อเน็ตเลย แต่ต้องต่อ **2 ครั้งก่อน** เพื่อเตรียมของ: ครั้งแรกตอน build image
([ข้อ 2](#2-ติดตั้ง-build-image)) ครั้งที่สองตอนโหลด checkpoint ตามข้างล่างนี้

วิธีนี้ไม่ใช้ Hugging Face cache — วาง checkpoint เป็น **directory ธรรมดา** แล้ว bind mount เข้าไป
เพราะ `Agent.__init__` จะเช็คก่อนว่า model spec ตรงกับ directory ที่มีอยู่จริงไหม ถ้าตรงก็ใช้เลย
ไม่แตะ Hub จึงไม่ต้องไปสร้างโครง `refs/` `snapshots/` `blobs/` ของ cache ให้ถูกเองซึ่งพลาดง่าย

### 11.1 เตรียมไฟล์ (เครื่องที่มีเน็ต)

```bash
pip install -r requirements-offline.txt   # ข้ามได้ถ้าเครื่องนี้ติดตั้ง laya อยู่แล้ว
python scripts/fetch_offline_checkpoints.py --out ./weights
```

`requirements-offline.txt` มีแต่ `huggingface_hub` ตัวเดียว ไม่ลาก torch มา เครื่องที่ทำหน้าที่
โหลดไฟล์เฉย ๆ จึงไม่ต้องลง laya ทั้งชุด — แลกกับที่สคริปต์จะข้ามขั้น pre-patch
`tokenizer_config.json` (มัน import `laya.agent`) แล้วขึ้น `note:` บอกไว้ ซึ่งไม่เป็นไรกับ
checkpoint ที่ publish อยู่ ดู [ข้อ 11.5](#115-กับดัก) ถ้าเจอ warning เรื่อง patch ตอนรัน

โหลด `english` + `multilingual` เฉพาะ 4 อย่างที่ตัวโหลดเปิดอ่านจริง ไม่ดึง `typed-decisions` ติดมา
ถ้าอยากได้ครบสามตัวใส่ `--models english,multilingual,typed-decisions`

ได้โครงนี้ (ถ้าจะโหลดมือจากหน้าเว็บ `huggingface.co/convaiinnovations/laya` ก็จัดให้ตรงแบบนี้):

```
weights/convaiinnovations/laya/
├── rl_agent_config.json
├── model.safetensors
├── tokenizer/           ← tokenizer.json, tokenizer_config.json
├── encoder/             ← config.json
└── multilingual/
    ├── rl_agent_config.json
    ├── model.safetensors
    ├── tokenizer/
    └── encoder/
```

> **`encoder/` ขาดไม่ได้** — ถ้าไม่มี `build_model()` จะ fallback ไปโหลด base encoder
> (ModernBERT / mmBERT) จาก Hub ทำให้ยังต้องใช้เน็ตอยู่ทั้งที่ไฟล์อื่นครบแล้ว

สคริปต์จะทิ้ง `.cache/huggingface/` ไว้ในโครงด้วย เป็น metadata สำหรับ resume ตอน re-run
runtime ไม่ได้อ่าน ลบทิ้งก่อนคัดลอกได้

### 11.2 ย้ายไปเครื่อง offline

```bash
# เครื่องที่มีเน็ต
docker save laya-laya-serve:latest | gzip > laya-serve.tar.gz
tar czf laya-weights.tar.gz weights/

# เครื่อง offline
gunzip -c laya-serve.tar.gz | docker load
tar xzf laya-weights.tar.gz
python scripts/fetch_offline_checkpoints.py --out ./weights --verify   # ไม่ใช้เน็ต
```

`--verify` บอกเป็นรายไฟล์ว่าอะไรขาด และคืน exit code 1 ถ้าไม่ครบ ใช้ใน CI ได้

### 11.3 รัน

```bash
LAYA_WEIGHTS_PATH=./weights docker compose \
  -f compose.yaml -f compose.http.yaml -f compose.offline.yaml up -d --wait laya-serve
```

`LAYA_WEIGHTS_PATH` ชี้ไปที่ directory ที่ **มี `convaiinnovations/` อยู่ข้างใน** (คือ `./weights`)
ไม่ใช่ตัว `convaiinnovations/` เอง

one-shot ใช้ไฟล์ชุดเดิมทั้งสาม แค่เปลี่ยน service:

```bash
LAYA_WEIGHTS_PATH=./weights docker compose \
  -f compose.yaml -f compose.http.yaml -f compose.offline.yaml run --rm laya
```

> ต้องใส่ `compose.http.yaml` ด้วย**ทุกครั้ง** แม้จะรัน one-shot เพราะ `compose.offline.yaml`
> override service `laya-serve` และมีแต่ `compose.http.yaml` ที่ให้ build context กับ service นั้น
> ถ้าขาดไป Compose จะปฏิเสธทั้ง project:
> `service "laya-serve" has neither an image nor a build context specified`

GPU ต่อ `-f compose.cuda.yaml` ไว้ท้ายสุด

`compose.offline.yaml` ตั้งให้เองแล้ว 3 อย่าง:

| ตัวแปร | ค่า | ทำไม |
|---|---|---|
| `HF_HUB_OFFLINE` | `1` | ตัดทุก request ไป Hub รวมถึงการเช็ค revision ที่ทำทุกครั้งที่สร้าง Agent — ไฟล์ขาดจะ error ทันที ไม่แขวนรอ timeout |
| `LAYA_PRELOAD` | `1` | โหลดทั้งสอง checkpoint **ก่อน** bind port ไฟล์ขาดจะทำให้ `up --wait` fail ไม่ใช่ไปพังตอนคำขอแรกของลูกค้า |
| `LAYA_MODELS` | `english,multilingual` | ต้องตรงกับที่ mount ไว้ ถ้าปล่อยว่างจะ preload ทั้งตระกูลรวม `typed-decisions` ที่ไม่ได้โหลดมา |

### 11.4 ตรวจสอบ

```bash
curl -s localhost:8000/health
```

```
{"status":"ok","loaded":["english","multilingual"],"device":"cpu", ...}
```

`loaded` ต้องมีครบทั้งสองตัวตั้งแต่คำขอแรก เพราะ preload แล้ว

### 11.5 กับดัก

**mount เป็น `:ro`** — `compose.offline.yaml` ตั้งไว้แบบนี้ และใช้ได้กับ checkpoint ที่ publish อยู่
(revision `55cf4c4e` ทั้งสองตัวประกาศ `tokenizer_class: PreTrainedTokenizerFast` และ
`extra_special_tokens` เป็น dict อยู่แล้ว จึงไม่มีอะไรต้องแก้) แต่ถ้าเจอ warning
`laya: could not patch .../tokenizer_config.json` ใน log ให้ถอด `:ro` ออก — แปลว่า checkpoint
นั้นต้องการการแก้ไฟล์จริง และบน mount read-only มันจะเตือนเฉย ๆ แล้วไปพังที่ `AutoTokenizer`
ด้วย error ที่ไม่บอกสาเหตุ (`'list' object has no attribute 'keys'`)

**permission** — container รันเป็น UID 10001 ไฟล์ต้องอ่านได้:
```bash
chmod -R a+rX weights/            # หรือ chown -R 10001:10001 weights/
```

**`LAYA_MODEL_PATH` ใช้กับ `laya-serve` ไม่ได้** — มีแต่โหมด one-shot ที่อ่าน ส่วน `laya-serve`
สร้าง Router จาก `LAYA_DEVICE` / `LAYA_MODELS` / `LAYA_PRELOAD` / `LAYA_AUTO_TASK` /
`LAYA_MAX_LOADED` เท่านั้น ไม่มี env ไหนชี้ path ได้ — นั่นคือเหตุผลที่ต้องใช้ bind mount

**`LAYA_REVISION`** — ไม่ต้องตั้ง ไม่มีผลกับวิธีนี้เพราะไม่ได้ผ่าน `snapshot_download` เลย
ถ้าจะ pin ให้ใส่ที่สคริปต์ตอนโหลดแทน: `--revision <sha>`

**rebuild image ยังต้องต่อเน็ต** — torch wheel + PyPI เก็บ `laya-serve.tar.gz` ไว้ หรือทำ local mirror

---

## 12. ถ้ามี NVIDIA GPU

ต้องมี driver NVIDIA ที่เข้ากันได้ + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
image GPU ใช้ PyTorch CUDA 12.8 (บน Windows ต้องตั้ง WSL2 GPU ของ Docker Desktop ให้เรียบร้อย)

```bash
# one-shot
docker compose -f compose.yaml -f compose.cuda.yaml run --build --rm laya

# HTTP server
docker compose -f compose.yaml -f compose.http.yaml -f compose.cuda.yaml up --build -d --wait laya-serve
```

เช็คว่า container เห็น GPU โดยไม่ต้องโหลด weights:

```bash
docker compose -f compose.yaml -f compose.cuda.yaml run --rm laya python -c \
  'import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))'
```

- เลือก GPU ตัวอื่นด้วย `LAYA_GPU_ID` (index หรือ UUID ของ host) — ใน container จะเห็นเป็น device `0`
- **ต้อง rebuild ทุกครั้งที่สลับระหว่าง CPU กับ CUDA**
- DGX Spark (Linux ARM64 + CUDA 13.0) ใช้ `compose.spark.yaml` แทน `compose.cuda.yaml`
- Laya ยัง fallback ไป CPU ได้เองหลัง error เรื่อง memory หรือ inference — ดู `cpu_fallbacks` ใน `/health`
  และ warning ใน log ว่าเกิดขึ้นหรือไม่

---

## 13. แก้ปัญหา

**คำขอแรกช้ามาก (หลายนาที)** — ปกติ กำลังดาวน์โหลด checkpoint รอบต่อไปจะเร็ว
weights เก็บใน volume ชื่อ `laya_model-cache`

```bash
docker volume ls | grep laya
```

**แก้ `.env` แล้วไม่มีอะไรเปลี่ยน** — ต้อง recreate container:

```bash
docker compose -f compose.yaml -f compose.http.yaml up -d --wait laya-serve
```

**ได้ `401` ทั้งที่ใส่ key แล้ว** — เช็คว่าค่าที่ compose อ่านได้ตรงกับที่ตั้งไว้:

```bash
docker compose -f compose.yaml -f compose.http.yaml config | grep LAYA_API_KEY
```

**`predict` พังด้วย `Failed to find C compiler`** — image ตั้ง `TORCH_DISABLE_NATIVE_JIT=1` ไว้แล้ว
ถ้าเจอบน bare-metal ให้ตั้งตัวแปรนี้เอง (PyTorch 2.14 เปลี่ยนบาง CUDA op ไปใช้ Triton kernel
ที่ต้อง compile ตอน inference ครั้งแรก — container จะรายงานว่า healthy แล้วทุกคำขอล้มเหลว)

**ผลลัพธ์ไม่ตรงคาด** — ดู `routing.reason` ก่อนว่าใช้ checkpoint ถูกตัวไหม แล้วค่อยเขียน `criteria`
ให้ละเอียดขึ้น ถ้า input ยาวให้ตั้ง `max_len` เพราะค่าเริ่มต้น 1024 ตัดข้อความทิ้งเงียบ ๆ

**ช้ากว่าที่คาดบน CPU** — เช็ค `OMP_NUM_THREADS` ว่าไม่เกิน physical core

**พื้นที่เต็ม** — ลบ cache weights (ต้องดาวน์โหลดใหม่):

```bash
docker compose -f compose.yaml -f compose.http.yaml down
docker volume rm laya_model-cache
```

---

## 14. คำสั่งที่ใช้บ่อย

```bash
# build / rebuild หลัง git pull
docker compose -f compose.yaml -f compose.http.yaml build

# one-shot
docker compose run --rm laya

# HTTP server
docker compose -f compose.yaml -f compose.http.yaml up -d --wait laya-serve
docker compose -f compose.yaml -f compose.http.yaml ps
docker compose -f compose.yaml -f compose.http.yaml logs -f laya-serve
docker compose -f compose.yaml -f compose.http.yaml down

# offline (ดูข้อ 11)
python scripts/fetch_offline_checkpoints.py --out ./weights          # เครื่องที่มีเน็ต
python scripts/fetch_offline_checkpoints.py --out ./weights --verify # เครื่อง offline
LAYA_WEIGHTS_PATH=./weights docker compose \
  -f compose.yaml -f compose.http.yaml -f compose.offline.yaml up -d --wait laya-serve

# ทดสอบ
curl -s localhost:8000/health
curl -s localhost:8000/v1/systemone \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <คีย์ของคุณ>' \
  --data @examples/docker/request.json
```

---

## อ่านต่อ

| ไฟล์ | เนื้อหา |
|---|---|
| `docs/docker.md` | Docker ครบทุก option, secret file, checkpoint ที่ fine-tune เอง |
| `docs/http-api.md` | HTTP API แบบละเอียด |
| `docs/docker-platforms.md` | ARM64, DGX Spark, Apple Silicon |
| `BENCHMARKS.md` | ผลวัดและ **ข้อจำกัดที่ทราบ** — อ่านก่อนเอาไปใช้ตัดสินใจอัตโนมัติ |
| `README.md` | เอกสารต้นฉบับ (อังกฤษ) รวม SDK, fine-tuning, LangChain, MCP |

Laya อยู่ภายใต้ Apache-2.0
