# Laya gateway — API spec

API ของ `app.py` สำหรับส่งข้อความเข้า laya แล้วรับคำตอบกลับเป็น JSON
ฉบับ machine-readable (OpenAPI 3.1) อยู่ที่ [`openapi.yaml`](openapi.yaml) — import เข้า Postman / Swagger UI ได้
วิธีติดตั้งและรัน gateway ดู [README.md ข้อ 6](README.md#6-api-gateway-apppy)

ตัวอย่าง response และ error ในเอกสารนี้เก็บจาก gateway ที่รันจริง (laya 0.3.22, CPU, checkpoint
`english` + `multilingual`)

| Method | Path | ต้องใช้ token | หน้าที่ |
|---|---|---|---|
| `GET` | `/health` | ไม่ | เช็คว่า server พร้อม และโหลด checkpoint อะไรไว้ |
| `POST` | `/predict` | ถ้าตั้ง `LAYA_API_KEY` | ถามคำถามกับข้อความ 1 ชิ้น |
| `POST` | `/predict/batch` | ถ้าตั้ง `LAYA_API_KEY` | ถามหลายข้อความในครั้งเดียว (สูงสุด 256) |

- **Base URL**: `http://localhost:8080` (ค่า default ของ `compose.yaml`)
- **Content-Type**: `application/json` เข้ารหัส UTF-8
- **Authentication**: ถ้า server ตั้ง `LAYA_API_KEY` ไว้ ให้ส่ง header `Authorization: Bearer <key>`
  ถ้าไม่ได้ตั้ง ไม่ต้องส่ง header นี้
- **Concurrency**: gateway ประมวลผลทีละ request ถ้าส่งพร้อมกันหลาย request จะเข้าคิวรอ
  ถ้ามีหลายข้อความให้ใช้ `/predict/batch`

## GET /health

```json
{"status": "ok", "loaded": ["english", "multilingual"], "models": ["english", "multilingual"], "offline": true}
```

| field | ความหมาย |
|---|---|
| `loaded` | checkpoint ที่อยู่ในหน่วยความจำตอนนี้ |
| `models` | checkpoint ที่ส่งใน field `model` ได้ (มาจาก `LAYA_MODELS`) |
| `offline` | `true` ถ้า server รันด้วย `HF_HUB_OFFLINE=1` |

ระหว่างที่ server ยังเริ่มไม่เสร็จจะตอบ `503` พร้อม `{"detail": "starting"}`

## POST /predict

### Request

| field | type | บังคับ | ความหมาย |
|---|---|---|---|
| `state` | string / object / array | ใช่ | สิ่งที่จะให้ตัดสิน: ข้อความ หรือ object / array เช่น ticket, email, รายการ chat message |
| `questions` | object | ใช่ | คำถาม โดย key คือชื่อคำถามที่ตั้งเอง และจะกลับมาเป็น key ของ `answers` |
| `model` | string | ไม่ | บังคับ checkpoint ต้องเป็นค่าใน `models` ของ `/health` เท่านั้น ถ้าไม่ส่งจะเลือกตามภาษาให้เอง |
| `lang` | string | ไม่ | บอกภาษาแทนการตรวจเอง: รหัสภาษาอังกฤษ (`en`, `en-US`) ไป `english` ค่าอื่นทั้งหมดไป `multilingual` |
| `min_confidence` | number 0–1 | ไม่ | คำตอบที่ `answer_confidence` ต่ำกว่าค่านี้จะมี `low_confidence: true` เพิ่มมา |

คำถามแต่ละข้อมี 3 ชนิด:

| `type` | `criteria` | ได้คำตอบเป็น |
|---|---|---|
| `choice` | บังคับ — object `{ตัวเลือก: คำอธิบาย}` หรือ array ของชื่อตัวเลือก | ตัวเลือกที่น่าจะใช่ที่สุด |
| `score` | บังคับ — array ของระดับ เรียงจากต่ำไปสูง | คะแนนตามลำดับระดับ (เริ่มที่ 0) |
| `noul` | ไม่ต้องใส่ | ความน่าจะเป็นที่คำตอบคือ "ใช่" (0–1) |

ทุกข้อต้องมี `instructions` เป็นตัวคำถาม

```json
{
  "state": "Hi, we were billed twice for March. Please refund the duplicate today or we will cancel our plan.",
  "questions": {
    "department": {"type": "choice", "instructions": "Which department should handle this?",
                   "criteria": {"billing": "invoices, payments, refunds",
                                "technical": "bugs, outages, system errors",
                                "other": "everything else"}},
    "urgency":    {"type": "score", "instructions": "How urgent is this?",
                   "criteria": ["not urgent", "soon", "blocking"]},
    "churn_risk": {"type": "noul", "instructions": "Does the user threaten to cancel or leave?"}
  }
}
```

### Response `200`

```json
{
  "model": "laya-rl-agent",
  "answers": {
    "department": {"type": "choice", "choice": "billing",
                   "probabilities": {"billing": 0.9865, "technical": 0.008, "other": 0.0055},
                   "confidence": 0.9267, "answer_confidence": 0.9865,
                   "action": {"act_probability": 1.0}},
    "urgency":    {"type": "score", "score": 1.7722,
                   "legend": {"0": "not urgent", "1": "soon", "2": "blocking"},
                   "probabilities": {"0": 0.0389, "1": 0.15, "2": 0.8111},
                   "confidence": 0.4714, "answer_confidence": 0.8111,
                   "action": {"act_probability": 1.0}},
    "churn_risk": {"type": "noul", "noul": 0.879,
                   "confidence": 0.879, "answer_confidence": 0.879,
                   "action": {"act_probability": 1.0}}
  },
  "usage": {"input_tokens": 164, "output_tokens": 0, "state_tokens": 21,
            "state_tokens_dropped": 0, "truncated": false, "truncated_questions": []},
  "routing": {"model": "english", "repo": "convaiinnovations/laya", "reason": "English Latin text",
              "detection": {"script": "latin", "script_profile": {"latin": 1.0}, "language": "en",
                            "is_english": true, "language_undecided": false, "diacritic_rate": 0.0,
                            "non_latin_fraction": 0.0, "mixed_segment": null},
              "workflow": null}
}
```

**`answers.<ชื่อคำถาม>`**

| ชนิด | field | ความหมาย |
|---|---|---|
| `choice` | `choice` | ตัวเลือกที่ความน่าจะเป็นสูงสุด |
| | `probabilities` | ความน่าจะเป็นของแต่ละตัวเลือก |
| `score` | `score` | ค่าคาดหมายของลำดับระดับ มักเป็นทศนิยมระหว่างสองระดับ (1.77 = ระหว่าง `soon` กับ `blocking`) |
| | `legend` | ลำดับระดับ → ข้อความระดับที่ส่งมาใน `criteria` |
| | `probabilities` | ความน่าจะเป็นของแต่ละระดับ key เป็น `"0"`, `"1"`, ... |
| `noul` | `noul` | ความน่าจะเป็นที่คำตอบคือ "ใช่" |
| ทุกชนิด | `answer_confidence` | ความน่าจะเป็นของคำตอบที่รายงาน — ใช้ค่านี้ตั้ง threshold และ `min_confidence` เทียบกับค่านี้ |
| | `confidence` | คนละสูตรกับ `answer_confidence` (ใน `choice` / `score` คิดจาก entropy) ห้ามใช้ threshold เดียวกัน |
| | `low_confidence` | มีเฉพาะเมื่อส่ง `min_confidence` และ `answer_confidence` ต่ำกว่าค่านั้น ตัวคำตอบไม่ถูกแก้ |

**`usage`** — `truncated: true` แปลว่า `state` ยาวเกินและถูกตัด คำตอบมาจากข้อความแค่บางส่วน
(`state_tokens_dropped` คือจำนวน token ที่ถูกตัด, `truncated_questions` คือคำถามที่ถูกตัด)

**`routing`** — `model` คือ checkpoint ที่ตอบจริง `reason` คือเหตุผลที่เลือก (ไว้ให้คนอ่าน ไม่ควร parse)
`detection` เป็น `null` เมื่อส่ง `model` หรือ `lang` มาเอง

## POST /predict/batch

```json
{"requests": [<body แบบ /predict>, ...]}
```

`requests` ต้องมี 1–256 รายการ แต่ละรายการใช้คำถาม, `model`, `lang` ต่างกันได้

```json
{"results": [<response แบบ /predict>, ...]}
```

`results` เรียงตามลำดับของ `requests`

- **ผิดรายการเดียว ล้มทั้ง batch** — ได้ status เดียวกับที่รายการนั้นจะได้จาก `/predict` และไม่มีผลบางส่วนกลับมา
- **`min_confidence` ใน batch ไม่มีผล** — ส่งได้ไม่ error แต่จะไม่มี `low_confidence` กลับมา (ลองจริง: คำตอบที่
  `answer_confidence` 0.9654 กับ `min_confidence` 0.99 ไม่ถูก flag) ให้เทียบ `answer_confidence` เองฝั่ง client
  หรือใช้ `/predict`

## Errors

| status | เกิดเมื่อ | `detail` |
|---|---|---|
| `400` | `model` ไม่อยู่ใน `LAYA_MODELS` ของ server | string เช่น `model 'typed-decisions' is not served here; choose from ['english', 'multilingual']` |
| `401` | ตั้ง `LAYA_API_KEY` ไว้ แต่ token ไม่มีหรือไม่ตรง | `missing or invalid bearer token` |
| `422` | body ไม่ตรง schema: JSON เสีย, ขาด `state` / `questions`, `requests` ว่างหรือเกิน 256 | **array** ของ `{type, loc, msg, input}` |
| `422` | body ถูกรูปแบบ แต่ laya ไม่รับ: `type` ไม่รู้จัก, `criteria` ผิด, `min_confidence` นอกช่วง 0–1 | **string** เช่น `ValueError: question 'x': unknown type 'nope'; use one of ['choice', 'noul', 'score']` |
| `500` | inference ล้มเหลวด้วยสาเหตุอื่น | ไม่ใช่ JSON — body เป็นข้อความ `Internal Server Error` |
| `503` | `/health` ระหว่าง server กำลังเริ่ม | `starting` |

`422` มี `detail` สองรูปแบบ client ต้องเช็คว่าเป็น array หรือ string ก่อนอ่าน

## ข้อควรรู้

- **`model` ต้องสะกดตรงกับ `models` ใน `/health`** — alias หรือชื่อ Hugging Face เช่น
  `convaiinnovations/laya-multilingual` ได้ `400`
- **`lang` ไม่ถูกตรวจ** — ค่าที่ไม่ใช่รหัสภาษาจริง (เช่น `zz-not`) ถือเป็น "ไม่ใช่ภาษาอังกฤษ" และไป `multilingual`
- **`state` ว่าง และ `questions` ว่าง ไม่ error** — `state: ""` ยังได้คำตอบกลับมา (ที่ไม่มีความหมาย)
  ส่วน `questions: {}` ได้ `answers: {}` ถ้าต้องการกันกรณีนี้ต้องเช็คฝั่ง client
- **ภาษาไทยบน Windows** — อย่าพิมพ์ภาษาไทยใน `curl -d '...'` ตรง ๆ ให้เขียน body เป็นไฟล์ UTF-8 แล้วส่งด้วย
  `curl --data-binary @request.json` (ดู README.md ข้อ 6)

## ตัวอย่างการเรียก

```bash
curl -s localhost:8080/predict \
  -H 'content-type: application/json' -H 'Authorization: Bearer changeme' \
  --data-binary @request.json
```

```python
import requests

r = requests.post(
    "http://localhost:8080/predict",
    headers={"Authorization": "Bearer changeme"},
    json={
        "state": "โดนเก็บเงินซ้ำสองครั้งเดือนมีนาคม ขอคืนเงินวันนี้ ไม่งั้นจะยกเลิกแพ็กเกจ",
        "questions": {"churn_risk": {"type": "noul",
                                     "instructions": "Does the user threaten to cancel or leave?"}},
    },
    timeout=60,
)
r.raise_for_status()
answer = r.json()["answers"]["churn_risk"]
print(answer["noul"], answer["answer_confidence"])
```
