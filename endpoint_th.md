# Laya — Endpoint ทั้งหมดของ `laya-serve`

สำรวจจาก server ที่รันอยู่จริง (ยิงทุก path เพื่อดู status code ที่ได้จริง ไม่ได้อ่านจากเอกสารเท่านั้น)
คู่กับ [`readme_th.md`](readme_th.md) ที่เป็นวิธีติดตั้งและรัน

---

## สรุปรวดเดียว

| Endpoint | Method | ต้องมี API key | ที่มา |
|---|---|---|---|
| `/health` | `GET` | **ไม่ต้อง** | เขียนในโค้ด (`laya/serve.py`) |
| `/v1/systemone` | `POST` | **ต้อง** (ถ้าตั้ง `LAYA_API_KEY`) | เขียนในโค้ด (`laya/serve.py`) |
| `/docs` | `GET` | **ไม่ต้อง** | FastAPI สร้างให้เอง |
| `/redoc` | `GET` | **ไม่ต้อง** | FastAPI สร้างให้เอง |
| `/openapi.json` | `GET` | **ไม่ต้อง** | FastAPI สร้างให้เอง |
| `/docs/oauth2-redirect` | `GET` | **ไม่ต้อง** | FastAPI สร้างให้เอง |

**endpoint ที่ใช้งานจริงมีแค่ 2 ตัว** คือ `/health` กับ `/v1/systemone` อีก 4 ตัวเป็นของ FastAPI
ที่ติดมาเอง ไม่ได้เขียนไว้ในเอกสารโปรเจกต์ — ดู [ข้อควรระวังด้านความปลอดภัย](#ข้อควรระวังด้านความปลอดภัย)

**ไม่มี endpoint เหล่านี้** (ยิงแล้วได้ `404` ทั้งหมด): `/`, `/healthz`, `/v1/models`, `/metrics`, `/version`
ไม่มี batch endpoint แยก — ยัดหลายคำถามใน `questions` ของคำขอเดียวแทน

---

## 1. `GET /health`

เปิดไว้เสมอ ไม่ต้องใส่ key และยังตอบได้ตลอดแม้กำลัง inference อยู่ เพราะ forward pass ที่กิน CPU
รันอยู่บน worker แยก ไม่ได้อยู่บน event loop

```bash
curl -s localhost:8000/health
```

ผลจริง:

```json
{
  "status": "ok",
  "loaded": ["english", "multilingual"],
  "revisions": {
    "english": "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851",
    "multilingual": "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
  },
  "device": "cpu",
  "device_is_preference": false,
  "checkpoint_devices": {"english": "cpu", "multilingual": "cpu"},
  "cpu_fallbacks": {
    "english": {"count": 0, "last_reason": null},
    "multilingual": {"count": 0, "last_reason": null}
  }
}
```

| ฟิลด์ | ความหมาย |
|---|---|
| `status` | `ok` |
| `loaded` | checkpoint ที่อยู่ใน memory ตอนนี้ — ถ้า `LAYA_PRELOAD=0` จะเริ่มจาก `[]` แล้วเพิ่มขึ้นตามการใช้งาน |
| `revisions` | revision ของ artifact ที่โหลดมาจริง ใช้ยืนยันว่า deploy กำลังเสิร์ฟอะไรอยู่ |
| `device` | device ที่ checkpoint **คำนวณจริง** ไม่ใช่ที่ขอไว้ |
| `device_is_preference` | `true` = ยังไม่มี checkpoint ใน memory ค่า `device` จึงเป็นแค่ค่าที่ตั้งไว้ — `false` = เป็นของจริง |
| `checkpoint_devices` | device แยกตาม checkpoint |
| `cpu_fallbacks` | นับจำนวนครั้งที่ตกจาก GPU มา CPU + เหตุผลครั้งล่าสุด |

**`device` กับ `device_is_preference` อ่านคู่กัน** — ถ้าขอ GPU แล้วได้ CPU ฟิลด์นี้จะบอกตรง ๆ
container ที่ขอ GPU แต่ไม่ได้ จะฟ้องที่นี่ ไม่ใช่ปล่อยให้เงียบ

`POST /health` ได้ `405`

---

## 2. `POST /v1/systemone`

endpoint เดียวที่ทำงานจริง ใช้ wire protocol ของ TypeSafe Jev — client ที่เขียนไว้สำหรับ Jev
(`hs-jev`, `typesafe-sdk` หรือเขียนเอง) ชี้ base URL มาที่นี่แล้วใช้งานต่อได้เลย

```bash
curl -s localhost:8000/v1/systemone \
  -H 'content-type: application/json' \
  -H 'Authorization: Bearer <คีย์ของคุณ>' \
  -d '{
  "state": "I was charged twice this month, I want my money back today or I cancel",
  "questions": {
    "queue":   {"type":"choice","instructions":"Which team?",
                "criteria":{"billing":"billing and refunds","tech":"login and app issues","other":"everything else"}},
    "urgency": {"type":"score","instructions":"How urgent?","criteria":["calm","firm","angry","furious"]},
    "churn":   {"type":"noul","instructions":"Does the user threaten to cancel?"}
  }}'
```

### ฟิลด์ใน request body

| ฟิลด์ | จำเป็น | ความหมาย |
|---|---|---|
| `state` | **ใช่** | ข้อความ / email / ticket / JSON ที่จะให้ตัดสิน ใส่ได้ทั้ง string และ object — เป็น `null` หรือไม่มี = `400` |
| `questions` | **ใช่** | object คีย์ด้วย id คำถาม แต่ละข้อเป็น `choice` / `score` / `noul` |
| `model` | ไม่ | ระบุ checkpoint — **ค่าที่ไม่รู้จักไม่ error แต่หมายถึง "ให้ router เลือกเอง"** |
| `max_len` | ไม่ | งบ token ของ state (ค่าเริ่มต้น 1024 — **ตัดเอกสารยาวทิ้งเงียบ ๆ**) เพดานอยู่ที่ `LAYA_MAX_TOKEN_BUDGET` |
| `head_max_len` | ไม่ | งบ token ของข้อความตัวเลือก (ค่าเริ่มต้น 192) |

`model` รับ `english` / `multilingual` / `typed-decisions`, HF id เต็ม (`convaiinnovations/laya-multilingual`)
และ alias ของมัน ส่ง `jev-1` แบบ client ของ Jev มาก็ได้ ไม่พัง แค่แปลว่าให้ router ตัดสินใจ
แล้วบอกใน `routing` ว่าเลือกอะไรเพราะอะไร

### Response

```json
{
  "model": "laya-rl-agent",
  "answers": {
    "queue": {"type": "choice", "choice": "billing",
              "probabilities": {"billing": 0.952, "tech": 0.03, "other": 0.018},
              "confidence": 0.4534, "answer_confidence": 0.952,
              "action": {"act_probability": 1.0}}
  },
  "usage": {"input_tokens": 140, "output_tokens": 0},
  "routing": {"model": "english", "repo": "convaiinnovations/laya",
              "reason": "English Latin text",
              "detection": {"script": "latin", "language": "en", "is_english": true}}
}
```

`model` เป็นชื่อคงที่ของ decision head — **checkpoint ที่ตอบจริงอยู่ใน `routing.model`**
`output_tokens` เป็น 0 เสมอเพราะไม่มีการ generate

คำตอบแยกตามชนิด:

| ชนิด | คีย์ที่ได้ |
|---|---|
| `choice` | `choice` (ตัวที่ prob สูงสุด), `probabilities` รายตัวเลือก |
| `score` | `score` (ทศนิยม อยู่ระหว่างระดับได้), `probabilities` คีย์ `"0".."k-1"`, `legend` |
| `noul` | `noul` = ความน่าจะเป็นที่คำตอบคือ "ใช่" |
| ทุกชนิด | `confidence`, `answer_confidence`, `action.act_probability` |

> `confidence` กับ `answer_confidence` **คนละสเกล อย่าใช้ threshold เดียวกัน** —
> `answer_confidence` = `max(p)` คือตัวที่ calibrate ไว้ ส่วน `confidence` เป็น normalized entropy
> สำหรับ `choice`/`score` รายละเอียดอยู่ใน [`readme_th.md` ข้อ 8](readme_th.md#8-อ่านผลลัพธ์)

### Response header

```
HTTP/1.1 200 OK
content-type: application/json
server-timing: inference;dur=2812.89
x-inference-time-ms: 2812.89
```

วัดเฉพาะเวลา inference ไม่รวมเวลาอ่าน body — **คำขอแรกของแต่ละ checkpoint จะสูงมาก** (ตัวอย่าง 2812 ms)
เพราะรวมเวลาโหลด model ด้วย คำขอถัดไปจะเหลือหลักสิบ ms

### Method อื่น

| Method | ได้ |
|---|---|
| `POST` | ใช้งานจริง |
| `GET` | `405` |
| `OPTIONS` | `405` (ไม่มี CORS middleware — **เรียกตรงจาก browser ข้าม origin ไม่ได้**) |

### Error code

| ส่งอะไร | ได้ |
|---|---|
| ไม่มี key / key ผิด | `401 invalid or missing bearer token` |
| JSON พัง | `400 request body must be valid JSON` |
| ไม่มี `questions` | `400 request body must be an object with a 'questions' field` |
| `state` เป็น `null` หรือไม่มี | `400 'state' is required` |
| `type` ไม่รู้จัก | `422 question 'a': unknown type 'banana'; use one of ['choice','noul','score']` |
| ตัวเลือกยาวเกิน head budget | `422` บอกชื่อคำถามและสิ่งที่ต้องแก้ |
| เกิน limit | `413` บอกว่าชนข้อไหนและเกินเท่าไร |
| คำขอพร้อมกันเกิน `LAYA_MAX_CONCURRENT` | `503 server busy, try again later` + `Retry-After: 1` |
| ล้มเหลวอย่างอื่น | `500 inference failed` (คงที่เสมอ สาเหตุจริงอยู่ใน log) |

Limit ทั้งหมดถูกเช็ค **ก่อน** tokenize คำขอที่ใหญ่เกินจึงไม่กิน compute เลย:

| limit | ค่า |
|---|---|
| ขนาด body | 2 MiB (บังคับตอน stream — ปลอม `Content-Length` ไม่ผ่าน) |
| `state` | 50,000 ตัวอักษร |
| คำถามต่อคำขอ | 64 |
| ตัวเลือกต่อคำถาม `choice` | 100 |
| ระดับต่อคำถาม `score` | 32 |
| ตัวเลือกรวมทุกคำถาม | 512 |
| คำขอพร้อมกัน | 16 (`LAYA_MAX_CONCURRENT`) |

**โหลดเกินถูกปฏิเสธ ไม่ต่อคิว** โดยเจตนา — client ที่ถือ slot ไว้ระหว่างส่ง body ช้า ๆ จึงทำให้
`/health` อดตายไม่ได้ และ slot ที่คนถูกปฏิเสธปล่อยไว้ ตัวที่ retry เข้ามาใช้ได้ทันที

---

## 3–6. Endpoint ที่ FastAPI แถมมาให้

4 ตัวนี้ **ไม่ได้เขียนไว้ในโค้ดของ Laya** แต่ FastAPI สร้างให้เองเพราะ `laya/serve.py:367`
เรียก `FastAPI(...)` โดยไม่ได้สั่งปิด (`docs_url` / `redoc_url` / `openapi_url`)

| Endpoint | ได้อะไร |
|---|---|
| `GET /docs` | Swagger UI กดลองยิง API ได้จากหน้าเว็บ |
| `GET /redoc` | ReDoc เอกสารแบบอ่าน |
| `GET /openapi.json` | OpenAPI 3.1.0 schema |
| `GET /docs/oauth2-redirect` | หน้า callback ของ Swagger UI (ไม่ได้ใช้ เพราะ Laya ใช้ bearer ไม่ใช่ OAuth2) |

`/openapi.json` ยืนยันว่ามี route จริงแค่ 2 ตัว:

```json
{
  "openapi": "3.1.0",
  "info": {"title": "laya-serve", "version": "0.1.0"},
  "paths": {
    "/health": {"get": "..."},
    "/v1/systemone": {"post": "..."}
  }
}
```

---

## ข้อควรระวังด้านความปลอดภัย

**`/docs`, `/redoc`, `/openapi.json` ตอบ `200` โดยไม่ต้องใส่ API key** — `_check_auth` ถูกเรียก
ข้างใน handler ของแต่ละ route ไม่ใช่เป็น middleware ครอบทั้ง app ดังนั้น `LAYA_API_KEY`
คุ้มครองแค่ `/v1/systemone`

ทดสอบยืนยันแล้ว ทั้งที่ตั้ง `LAYA_API_KEY` ไว้:

```
/v1/systemone   POST 401     <- ต้องมี key
/docs           GET  200     <- ไม่ต้อง
/redoc          GET  200     <- ไม่ต้อง
/openapi.json   GET  200     <- ไม่ต้อง
/health         GET  200     <- ไม่ต้อง (เป็นดีไซน์: container healthcheck เรียกเอง)
```

**ที่รั่วได้จริงคืออะไร:** schema ของ API, `/health` (บอกว่าโหลด checkpoint อะไร revision ไหน
device อะไร) และหน้า Swagger UI ที่กดยิงได้ **ไม่รั่ว**: ตัว API key และผลลัพธ์ inference
(เพราะ `/v1/systemone` ยัง `401` อยู่)

**ตอนนี้ยังไม่เป็นปัญหา** เพราะ compose ผูก port ไว้กับ `127.0.0.1` เท่านั้น เข้าถึงได้แค่จากเครื่องนี้
**แต่ถ้าจะแก้ `LAYA_BIND_ADDRESS` ให้เครื่องอื่นเรียก** ควรจัดการก่อน โดยเลือกอย่างใดอย่างหนึ่ง:

1. **วางไว้หลัง reverse proxy** (nginx / Caddy / Traefik) แล้ว block `/docs`, `/redoc`, `/openapi.json`
   ที่ชั้นนั้น — ไม่ต้องแก้โค้ด Laya วิธีนี้ตรงไปตรงมาที่สุด
2. **ปิดที่โค้ด** — แก้ `laya/serve.py:367` เป็น `FastAPI(..., docs_url=None, redoc_url=None, openapi_url=None)`
   แต่กลายเป็น local patch ที่ต้องมาแก้ใหม่ทุกครั้งที่ `git pull`
3. **ไม่เปิดออกนอกเครื่องเลย** ให้ client เชื่อมผ่าน SSH tunnel หรือ VPN แทน

ไม่มี **CORS middleware** ด้วย (`OPTIONS` ได้ `405`) เรียกตรงจาก JavaScript ในหน้าเว็บคนละ origin
ไม่ได้ ต้องยิงผ่าน backend ของตัวเอง ซึ่งก็ดีกว่าอยู่แล้ว เพราะไม่ต้องเอา API key ไปไว้ฝั่ง browser

---

## สิ่งที่ไม่ใช่ HTTP endpoint

Laya มีวิธีเรียกอื่นที่ไม่ได้อยู่บน `laya-serve` — เผื่ออ่านเจอในเอกสารแล้วสับสน:

| วิธี | คืออะไร |
|---|---|
| **SDK** | `from laya import Router` เรียกใน Python process เดียวกัน ไม่ผ่าน HTTP — โหมด one-shot ใน `readme_th.md` ใช้ทางนี้ |
| **CLI** | `laya "ข้อความ" --preset triage` |
| **MCP server** | `laya[mcp]` — tool `laya_predict_batch` / `laya_route_batch` / `laya_decide` / `laya_status` คุยผ่าน MCP protocol ไม่ใช่ REST |
| **LangChain / LlamaIndex / CrewAI** | `laya[langchain]`, `laya[llamaindex]`, `laya[crewai]` |
| **TypeScript / Node / browser** | แพ็กเกจ `laya-ts` แยกอยู่ใน `laya-ts/` |

---

## วิธีสำรวจซ้ำเอง

```bash
# ดู route ทั้งหมดที่มีจริงจาก schema
curl -s localhost:8000/openapi.json | python -m json.tool

# ยิงทุก path ที่สงสัย ดู status code
for p in / /health /docs /redoc /openapi.json /v1/systemone /v1/models /metrics /version; do
  printf "%-16s GET %s\n" "$p" "$(curl -s -o /dev/null -w '%{http_code}' localhost:8000$p)"
done

# หา route ที่เขียนไว้ในโค้ด
grep -n '@app\.\(get\|post\|put\|delete\)' laya/serve.py
```

---

## อ่านต่อ

| ไฟล์ | เนื้อหา |
|---|---|
| [`readme_th.md`](readme_th.md) | วิธีติดตั้ง รัน ตั้ง API key แก้ปัญหา (ภาษาไทย) |
| `docs/http-api.md` | HTTP API ต้นฉบับ (อังกฤษ) |
| `laya/serve.py` | โค้ด server — route อยู่บรรทัด 389 (`/health`) และ 425 (`/v1/systemone`) |
| `BENCHMARKS.md` | ผลวัดและข้อจำกัดที่ทราบ |
