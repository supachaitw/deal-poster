# Deal Poster — คู่มือสำหรับ Claude (ทุกเครื่อง)

ระบบโพสต์ดีล Shopee/Lazada อัตโนมัติ รันบน n8n `https://n8n.srv1277799.hstgr.cloud` ทั้งหมด —
repo นี้เป็น **backup + จุดถ่ายทอดความรู้ระหว่างเครื่อง** ไม่ใช่ source ที่ deploy
(source of truth = workflow ใน n8n; แก้ผ่าน n8n public API แล้วค่อย export กลับมา commit)

**นั่งเครื่องใหม่/ย้ายเครื่อง → อ่าน [SETUP.md](SETUP.md) ก่อน** (clone, n8n API key, SSH key, ทะเบียน ID ทั้งหมด)
memory ของผู้ช่วยเป็นของแยกรายเครื่อง **ไม่ตามไปด้วย** — ความรู้ที่ต้องข้ามเครื่องเขียนลงไฟล์นี้เท่านั้น

## กติกาเหล็ก
- **git ทุก session ทุกเครื่อง**: `git pull origin dev` (หรือ main) ก่อนแตะไฟล์เสมอ ·
  `git status` ไม่สะอาดและไม่ใช่ของตัวเอง = หยุดถามก่อน ห้าม commit ทับ ·
  เสร็จเป็นชิ้นให้ commit ทันที อย่าค้าง working tree ข้ามวัน ·
  push โดน reject → `git pull --rebase` แล้ว push ใหม่ **ห้าม force push**
  (กฎชุดนี้มาจากบทเรียน expense-bot ที่ session แก้จากไฟล์เก่าแล้วทับฟีเจอร์หาย 2 รอบ)
- **ห้าม print token/secret ลง output หรือ commit ลง repo** — ใช้ใน script เท่านั้น, ไฟล์ใน `workflows/` ต้อง sanitize เป็น `REPLACE_*` ก่อน commit เสมอ (ดู pattern ใน git log)
  **หลุดมาแล้ว 3 ครั้ง (24 ส.ค. FB token · 27 ก.ย. Telegram token บางส่วน + Bitkub HMAC secret) → user สั่ง "ป้องกันตัวเองหน่อย" 27 ก.ย. 69 → มีกลไกบังคับแล้ว:**
  · **ของดิบจาก n8n API / `docker inspect` / env / `.env` ห้ามขึ้นจอตรง ๆ** — ต่อท่อ `| python3 scripts/redact.py` เสมอ หรือใช้ `python3 scripts/n8n_get.py <id> ["node"]` (แสดง node/jsCode หลัง redact · `--raw-to FILE` เขียนดิบลงไฟล์ไว้ patch โดยไม่พิมพ์)
  · **hook `.claude/hooks/guard_bash.py`** (PreToolUse ใน `.claude/settings.json`) **บล็อก**คำสั่ง Bash ที่แตะแหล่งความลับโดยไม่ผ่าน redact · python heredoc ที่แตะ n8n API ต้องมี `# noraw` (คำสัญญาว่าไม่ print ค่าดิบ — print ได้แค่ฟิลด์ที่เลือกแล้ว เช่น ชื่อ node/สถานะ/ความยาว) หรือ import redact · โดนบล็อกแล้ว**ห้ามเลี่ยง** ให้แก้คำสั่งตามข้อความ
  · `redact.py` จับทั้ง token รูปแบบรู้จัก (FB/Threads/Telegram/Anthropic/JWT/Bearer/Notion/…), ค่าของคีย์ชื่อ secret/token/key/password/authorization, และสตริงสุ่มยาว (hex ≥32 ยกเว้น Notion id ใน URL/`"id"`, base64 ≥48) · token รูปแบบใหม่ → เพิ่มใน `KNOWN` ที่นี่ + `SANITIZE`/`LEAK` ใน export_workflows.py
  · บทเรียนรูปแบบที่หลุด: (1) dump jsCode/params ทั้งก้อน "เพื่อดูโครง" (2) `str(url)[:45]` คิดว่าตัดสั้นพอแล้ว (3) print พารามิเตอร์ node แล้ว exclude แค่คีย์ `value` แต่ secret อยู่คีย์อื่น → **อย่าเลือก "ยกเว้นคีย์ที่รู้" ให้เลือก "พิมพ์เฉพาะคีย์ที่ต้องการ" แล้วผ่าน redact**
- n8n API key อยู่หน้า Notion **"🔐 Claude Daily Brief — Config"** — ดึงจากที่นั่น อย่า hardcode ที่อื่น
- แก้ workflow ผ่าน API: `PUT /api/v1/workflows/{id}` รับเฉพาะ `{name,nodes,connections,settings}` แล้วต้อง **deactivate→activate** ทุกครั้ง
- ⛔ **ห้าม PUT ไฟล์จาก `workflows/` เข้า n8n เด็ดขาด** — ไฟล์พวกนั้น sanitize แล้ว token เป็น `REPLACE_*` ยิงเข้าไปคือ**ทุกช่องทางตายพร้อมกัน** ต้องไล่ขอ token ใหม่ทีละอัน
  (ไฟล์ใน repo มีไว้อ่าน/เทียบ/กู้คืนตอน n8n ล่มเท่านั้น — กู้คืนต้องแทน `REPLACE_*` ด้วยค่าจริงก่อน ดู README)
- **ดึงสด GET ก่อน patch เสมอ** อย่าใช้สำเนาที่ดึงมาก่อนหน้าในมือ — เครื่อง/session อื่นอาจแก้ workflow เดียวกันไปแล้ว (24 ส.ค. 69 เกิดจริง: อีก session เพิ่ม `Build Posted Alert` + เปลี่ยน FB token ระหว่างที่อีกฝั่งกำลังทำงาน) PUT ทับ = งานเขาหายทันที ไม่มี merge ให้
- เขียน jsCode **หรือ expression** ของ node ผ่าน script ต้องใช้ **String.raw** เสมอ — เคยพัง 2 แบบ:
  (1) backslash ใน regex หาย → ทุกรอบ error + โพสต์ซ้ำ
  (2) ขึ้นบรรทัดใหม่กลายเป็น **newline จริงในสตริง single-quote ของ JS** ใน expression → JS parse ไม่ผ่าน n8n คืน `{"error":"invalid syntax"}` ทั้ง node (24 ส.ค. 69: FB+IG ล้มเงียบ 3 รอบ) — ต้องเป็น escape sequence เท่านั้น
  ก่อน deploy ให้ตรวจด้วย `new Function('return (' + inner + ')')` ว่า syntax ผ่าน
- ตอบผู้ใช้เป็นภาษาไทย โค้ด/คำสั่งเป็นอังกฤษ

## Workflows (n8n IDs)
| id | ชื่อ | หน้าที่ |
|---|---|---|
| `E6i2xEAcaUsUFKWm` | Deal Poster v1 — โพสต์ดีลที่อนุมัติแล้ว | cron `0 0,6,9,12,15,18,21 * * *` — **สาย B อย่างเดียว**: "อนุมัติแล้ว"→Telegram(รูป binary)+FB→IG(**Reels** ถอยเป็นภาพได้)/Threads(create→**Settle 30 วิ**→publish)→[X ปิดอยู่]→Mark Posted→**Build Posted Alert**→**Telegram** (`TG Posted Alert` chat_id `8336016992` — เปลี่ยนจาก LINE 24 ก.ย. 69) |
| `e8aD2wCvsVYmefrq` | Deal Caption Writer | cron `50 2-23/3 * * *` — **สาย A ที่แยกออกมา**: "ใหม่"→Claude แคปชัน+คำบรรยาย→`Save Draft to Notion`→[`LINE Preview` **ปิดอยู่**] |
| `Kq3cRuTbwF9cMkA1` | Deal Intake Form | `/form/deal-intake` — บังคับแค่ลิงก์ ช่องอื่นเว้นได้ (OG+Claude parse เหมือนสาย TG; ค่าที่กรอกชนะค่า parse) |
| `JUE23JTCBbCsW1lS` | Deal Intake Telegram | webhook `deal-intake-tg-x7k2`, บอท @sup_dealposter_bot |
| `731A7ASm8bI0F79B` | Deal Intake LINE | webhook `deal-intake-line-p9m4`, LINE OA "Paiyaa Bot" @558klaxp |
| `UXGp6aS7EclTqCtl` | Threads Token Keeper | จันทร์ 07:00 refresh token 60 วัน แล้ว PUT กลับ |
| `teJKfYg0xuG9OSfc` | Deal Landing Page | ~~`https://deals.srv1277799.hstgr.cloud`~~ **เลิกใช้ 26 ก.ย. 69 — เว็บจริงคือ https://paiyaadeals.com (static, ดูหัวข้อ "เว็บดีลสาธารณะตัวใหม่")** · workflow ยัง active เข้าได้ทาง n8n ตรง (= `GET /webhook/deals`) — หน้า HTML รวมดีล ดึง Notion สด สำหรับใส่ไบโอ IG · มีรูปสินค้า · **24 ก.ย. 69: โชว์แค่ 120 ดีลใหม่สุด · cache 10 นาทีใน staticData · ลิงก์การ์ดผ่าน `/webhook/go?d=` นับคลิก · สถิติที่ `/webhook/deals-stats`** (ดูหัวข้อด้านล่าง) |
| `qHcCduq7ec3an1zk` | TikTok OAuth Callback | `GET /webhook/tt-oauth-cb-k4w8` — หน้ารับ `code`+`state` ตอน creator authorize แล้วให้ user copy ส่งให้ Claude (สร้าง 29 ส.ค. 69 รอใช้ใน Phase 0 TikTok) |

**หน้ารวมดีลเปลี่ยนใหญ่ 24 ก.ย. 69 — ทำจาก session อื่น, repo ตามไม่ทันจนถึง 25 ก.ย.** (พบตอนเห็นหน้าเว็บมี 120 การ์ดทั้งที่ดึงมา 500)
- **โชว์แค่ 120 ดีลใหม่สุด**: `Build Page` ปิดท้าย `deals.slice(0, 120)` (คอมเมนต์ในโค้ด: ของเก่ากว่านั้นส่วนใหญ่เป็น flash sale หมดอายุแล้ว)
  หัวหน้าเขียน "ดีลล่าสุด 120 รายการ จากทั้งหมด N" → **N = จำนวนที่ Query ดึงได้ ไม่ใช่จำนวนการ์ด** · ตอนนี้ N ชน cap 500 (maxRequests 5) แล้ว = ปกติ ไม่ใช่บั๊ก
  · หน้าละ `PER=30` (เดิม 50) · การ์ดที่ชื่อมีคำว่า "ทดสอบ" ถูกกรองออก
- **cache ชั้นที่ 2 ใน n8n**: `Deals Webhook` → `Cache Check` (อ่าน `$getWorkflowStaticData('global')` ถ้า `builtAt` < 600 วิ ส่ง HTML เดิมทันที) → `Cached?` → ถ้าไม่ทันค่อย `Query Posted Deals` → `Build Page` เขียน `sd.page/builtAt/links/dealCount`
  · `?refresh=1` บังคับสร้างใหม่ · ซ้อนกับ cache 10 นาทีของ `deals-proxy` อีกชั้น → ดีลใหม่โผล่หน้าเว็บช้าได้ถึง ~20 นาที (ไม่ใช่อาการเสีย)
  · ⚠️ staticData เก็บใน DB ของ n8n ตอน execution จบ — ถ้า workflow ถูก PUT ทับ staticData **ยังอยู่** แต่ถ้า import ใหม่เป็น id อื่นจะหาย (แค่ cache/สถิติคลิก ไม่ใช่ข้อมูลหลัก)
- **นับคลิก**: การ์ดทุกใบลิงก์ไป `/webhook/go?d=<notion page id>` → `Count Click` เช็คว่า id อยู่ใน `sd.links` (ที่ `Build Page` เห็นตอนสร้างหน้า — กัน open redirect) นับ `sd.clicks[id]` แล้ว 302 ไปลิงก์ affiliate · id ไม่รู้จัก → กลับหน้า deals
  · Location ต้องเป็น URL เต็ม สร้างจาก header `x-forwarded-host` (relative path โหนด redirect เคยเขียนเพี้ยนเป็น `https://webhook/deals`)
  · ผลข้างเคียง: ดีลที่หลุดจาก 120 ใบล่าสุดแล้ว ลิงก์ `go?d=` เก่าที่คนแชร์ไว้จะพากลับหน้าแรกแทนร้าน (เพราะ `sd.links` สร้างใหม่ทุกรอบจาก 120 ใบที่โชว์)
- **หน้าสถิติ** `GET /webhook/deals-stats` (`Stats Webhook` → `Build Stats`) — ตาราง ดีล/ร้าน/จำนวนคลิก/ล่าสุด 200 แถว, รวม 7 วัน, แยกตาม host · ข้อมูลอยู่ใน staticData ล้วน ไม่ออกนอกเครื่อง · **ไม่มี auth** (เปิดผ่าน n8n ตรง ไม่ผ่าน traefik basic-auth) แต่ไม่มีอะไรลับ
- ⛔ **บั๊กที่มากับของใหม่ (พบ+แก้ 25 ก.ย. 69)**: `deals-proxy` เดิม proxy **ทุก path ไป `/webhook/deals`** → คลิกการ์ดจากโดเมน `deals.` (ที่อยู่ในไบโอ IG) ได้ **404 ทุกใบตั้งแต่ 24 ก.ย.** (ยิงตรง n8n ได้ 307 ปกติ จึงไม่มีใครเห็นตอนเทส)
  แก้ที่ `/root/deals-proxy/nginx.conf`: เพิ่ม `location = /webhook/go` ส่งต่อ `$is_args$args` ไป n8n ตรง **ไม่ cache** + `proxy_redirect off` + ส่ง `X-Forwarded-Host` (Count Click ใช้สร้าง URL กลับหน้าแรก)
  · conf เป็น bind-mount read-only → แก้ไฟล์บน host แล้ว `docker exec deals-proxy nginx -t && docker exec deals-proxy nginx -s reload` ไม่ต้อง recreate · backup ที่ `nginx.conf.bak-20260925` · repo: `vps/deals-proxy.nginx.conf`
  · ทดสอบ: `curl -sI 'https://deals.srv1277799.hstgr.cloud/webhook/go?d=<id>'` ต้องได้ 307 + `location` เป็นร้าน + `X-Cache-Status: BYPASS`
  · **บทเรียน: เพิ่ม path ใหม่ใน Landing Page ทีไร ต้องเพิ่ม location ใน deals-proxy ด้วยเสมอ** (`/webhook/deals-stats` ยังเข้าได้ทาง n8n ตรงเท่านั้น ตั้งใจไม่เปิดผ่าน `deals.`)

**Deal Poster v1 เปลี่ยน 24 ก.ย. 69 (session อื่น)**: `LINE Posted Alert` → **`TG Posted Alert`** (`api.telegram.org/bot…/sendMessage` chat_id `8336016992`) — แจ้งเตือน "โพสต์เสร็จ" ย้ายจาก LINE ไป Telegram
→ ~~LINE ไม่มีการแจ้งเตือนอะไรจากสายโพสต์เลยแล้ว~~ **27 ก.ย. 69 กลับมาส่ง LINE แบบสรุปต่อรอบ** (user: "โพสต์ทุกโพสต์ ส่ง LINE ได้ก็ส่ง ถ้ามีโควตา"):
  `TG Posted Alert` → **`Build LINE Summary`** (Code runOnceForAllItems: รวม `alert` ของทุกดีลในรอบเป็นข้อความเดียว + เรียก `GET /v2/bot/message/quota` และ `/quota/consumption` ด้วย `this.helpers.httpRequest` → `send = used < quota`) → **`LINE Quota OK?`** (IF) → **`LINE Posted Alert`** (push ไป user `U72a09a14…` เดิม, `onError: continueRegularOutput`)
  · **ทำไมต้องสรุปต่อรอบ**: LINE OA แพลนฟรี **300 ข้อความ/เดือน** (นับต่อ push ต่อผู้รับ ไม่นับความยาว) — ส่งรายดีล 14–42 ดีล/วัน หมดใน ~1 สัปดาห์ · สรุปต่อรอบ ≤ 7/วัน ≈ 217/เดือน พอดีโควตา · **ก.ย. 69 ใช้ครบ 300/300 แล้ว** (= สาเหตุ 429 "too many requests" 24 ก.ย.) → จนถึง 1 ต.ค. node จะเห็น `send:false` และไม่ยิง (ดูได้ใน runData ของ `Build LINE Summary`: `quota/used/send/err`)
  · วางไว้**ท้ายสุดของสาย** หลัง Mark Posted + TG → ต่อให้ LINE ล้มก็ไม่กระทบการโพสต์/มาร์ค (บทเรียน 24 ก.ย. ที่ LINE 429 ทำสาย IG ไม่รัน) · เช็คโควตาสด: `curl -H 'Authorization: Bearer <LINE token>' https://api.line.me/v2/bot/message/quota/consumption`
  · LINE channel token ตอนนี้ฝังใน Deal Poster v1 ด้วย (jsCode ของ Build LINE Summary + header ของ LINE Posted Alert) นอกจาก Intake LINE — rotate ต้องแก้ 2 workflow
· settings ทุก workflow มี `availableInMCP: false` เพิ่มมาเอง (n8n อัปเดตเวอร์ชัน) ไม่ใช่การแก้ของใคร

**รูปสินค้าบนหน้ารวมดีล (27 ส.ค. 69)** — เพิ่ม property **`รูป` (url)** ใน Notion เก็บ `og:image` ของดีล
- คนเขียนคือ node **`Mark Posted`** (เติม `รูป` ตอนมาร์ค "โพสต์แล้ว" ดึงจาก `$('Build Post Body').item.json.photoUrl` ที่สายโพสต์หามาแล้ว)
  เลือกจุดนี้จุดเดียวแทนแก้ intake ทั้ง 3 ทาง เพราะหน้ารวมดีลแสดงเฉพาะ "โพสต์แล้ว" → ครอบคลุมพอดี · ห่อ try/catch กัน item pairing หลุดแล้วทำ Mark Posted ล้ม (ล้ม = รอบหน้าโพสต์ซ้ำ)
- `Build Page` เติม `_tn` ต่อท้าย URL ของ Shopee CDN = **thumbnail เล็กลง ~10 เท่า** (245KB → 25KB) · Lazada (`lzd-img-push.slatic.net`) ไม่มี `_tn` ปล่อยรูปเดิม เล็กอยู่แล้ว
  `<img>` ใช้ `loading=lazy` + `referrerpolicy=no-referrer` + onerror fallback กลับไปรูปเต็มก่อนค่อยซ่อน
- ⚠️ **Shopee/Lazada CDN ให้ hotlink ได้ปกติ** (ต่างจากฝั่ง Meta/Telegram fetcher ที่โดนบล็อก) เทสต์แล้ว HTTP 200 ทั้งมีและไม่มี Referer
- ดีลเก่า 90 แถว backfill ครบแล้ว

**แบ่งหน้าละ 50 รายการ (27 ส.ค. 69)** — แถบเลื่อนหน้าอยู่ทั้งบนและล่าง แบ่งฝั่ง client ล้วน
(render การ์ดทั้งหมดครั้งเดียวแล้ว toggle `display` เหมือนการ์ดใน Home Console) การ์ดที่ซ่อนไม่โหลดรูป
เพราะ `loading=lazy` · ปุ่มสร้างด้วย DOM API ไม่ใช่ `innerHTML` เพราะสตริงซ้อนใน jsCode อยู่แล้ว
จะได้ไม่ต้องหนี quote ซ้อนชั้น · ข้อความไทยในสคริปต์ที่ฝังใช้ `\uXXXX` escape กัน encoding เพี้ยน
~~เพดาน 100 ดีล~~ **ปิดแล้ว (27 ส.ค. 69)** — `Query Posted Deals` เปลี่ยนจาก httpRequest เป็น
**Code node ที่วน `start_cursor`** จนครบ (สูงสุด 20 หน้า = 2,000 ดีล) ใช้ `this.helpers.httpRequest`
ยิง Notion ตรงในลูป · ⚠️ node นี้เลยมี Notion token ฝังใน **jsCode** (ไม่ใช่ header) — sanitize ต้องจับใน jsCode ด้วย

⛔ **ห้ามส่ง JSON ที่มีภาษาไทยผ่าน `curl -d '...'` ใน bash บนเครื่อง Windows** — console encode เป็น cp874
ทำให้ชื่อ property เพี้ยน (27 ส.ค. 69 เกิดจริง: สร้าง property ชื่อขยะแทน `รูป` แล้ว PATCH 90 แถวพังหมด
`"รูป is not a property that exists"`) ให้เขียน body ลงไฟล์ UTF-8 แล้ว `--data-binary @file` หรือใช้ Python `json.dumps(...).encode('utf-8')`

⚠️ **โครงสร้างเปลี่ยนไปแล้ว — พบ 7 ก.ย. 69 (session/เครื่องอื่นแก้ไว้ repo ตามไม่ทัน)**: สาย A ถูก**แยกออกจาก Deal Poster v1 ไปเป็น workflow `e8aD2wCvsVYmefrq`** และ
**ไม่มีขั้นอนุมัติด้วยมือแล้ว** — `Save Draft to Notion` PATCH สถานะเป็น **"อนุมัติแล้ว" ทันที** (เดิมเป็น "รอตรวจ" แล้วรอคนกด)
→ LINE Preview กลายเป็นแค่ "แจ้งให้ดู" ไม่ใช่ "ให้อนุมัติ" · แถวสถานะ "ใหม่" จะถูกโพสต์อัตโนมัติภายใน ~3 ชม.
  **อัปเดต 21 ก.ย. 69:** node `LINE Preview` ตอนนี้ `disabled: true` — ไม่มีแจ้งเตือนสาย A เข้า LINE เลย
  (ยังได้ `Build Posted Alert` ตอนโพสต์เสร็จตามเดิม) · ถ้าเงียบผิดปกติ อย่าไปไล่หา token LINE ก่อน เช็คโหนดนี้
**ผลต่อการทดสอบ: ห้ามสร้างแถวทดสอบที่สถานะ "ใหม่" เด็ดขาด** (จะหลุดไปโพสต์ลงเพจจริง) — ทดสอบให้ลงที่ "รอตรวจ" เท่านั้น

**หมวดเป็น "อื่นๆ" ทั้งคิว (พบ+แก้ 28 ก.ย. 69)** — user ส่งอาหาร 21 ดีล ทุกตัวได้หมวด อื่นๆ ทั้งที่ `Claude Parse` ตอบ `อาหาร` ถูก 21/21 · สาเหตุ: whitelist `const cats=[…]` ใน `Build Payload` (TG/LINE) มีแค่ 5 หมวด (ไม่มี อาหาร/กาแฟ/รถ/สัตว์เลี้ยง/Fitness) → ตกเป็น อื่นๆ · แก้: whitelist ทั้ง 3 intake = ตัวเลือก `หมวด` ใน Notion ทั้ง 10 · prompt Claude Parse ทั้ง 3 ให้เลือกจากรายการเต็ม + คำใบ้ (กาแฟ→กาแฟ, ขนม/อาหาร→อาหาร, ของใช้บ้าน/ครัว/สวน→บ้าน, อิเล็กทรอนิกส์→gadget) · คิว 21 ดีลแก้ให้แล้ว (อาหาร 18, กาแฟ 3 ตามคำว่า กาแฟ ในชื่อ) · **เพิ่มตัวเลือกหมวดใน Notion เมื่อไหร่ ต้องเพิ่มใน whitelist + prompt ทั้ง 3 workflow ด้วย** (CAT_HOOKS ใน server.py ก็อิงชื่อหมวดเดียวกัน)

Notion Deal Queue DB `589f80403f534993b49fd9fdd4d292ff` — สถานะ: ใหม่→(รอตรวจ)→อนุมัติแล้ว→โพสต์แล้ว
(กติกา: แคปชันเขียนเฉพาะรอบสถานะ "ใหม่"; price-reply เติมแถวที่ราคาลดว่าง สถานะ "ใหม่" หรือ "รอตรวจ")

**แถวที่ถูกสร้างตรงใน Notion ด้วยบัญชีผู้ใช้ ไม่ผ่าน intake (สังเกต 30 ก.ย. 69)** — ตั้งแต่ 28 ก.ย. 69 09:27 UTC มีแถวที่ `created_by` เป็น **user id `8366858a…` (บัญชีคน ไม่ใช่ integration n8n `dc1ff3a7…`)** เข้ามาเป็นชุด ๆ (28–30 ก.ย. รวม 113 แถว: โพสต์แล้ว 49 · อนุมัติแล้ว 39 · รอตรวจ 25) แคปชัน/คำบรรยาย/หมวด/ราคาลด ครบในสไตล์เดียวกับ Caption Writer แต่ไม่มี `รูป` และมักไม่มี `ราคาเต็ม` — น่าจะเป็น Claude ฝั่ง claude.ai ที่ต่อ Notion connector (ทำงานในนามบัญชีผู้ใช้) เขียนแถวให้ตรง ๆ · **ไม่มี workflow/สคริปต์บนเครื่องนี้เกี่ยว** (เช็ค execution ทั้ง 4 intake + Caption Writer และ transcript บนเครื่องแล้ว) · ระบบรับได้ปกติ: 49 แถวที่เป็น "อนุมัติแล้ว" ถูกโพสต์และ Mark Posted เติม `รูป` ครบ 49/49
· ⚠️ แถวที่ทางนั้นตั้งเป็น **"รอตรวจ" จะค้างตลอดกาล** — Caption Writer อ่านแค่ "ใหม่", Poster อ่านแค่ "อนุมัติแล้ว" ไม่มีอะไรแตะ "รอตรวจ" (30 ก.ย. 69 มี 25 แถว สร้าง 12:45–12:48 UTC ครบทุกช่องยกเว้นราคาเต็ม ไม่ซ้ำกับดีลเดิม) → ต้องให้ user ตัดสินว่าอนุมัติหรือทิ้ง (เปลี่ยนเป็น "อนุมัติแล้ว" ผ่านหน้า dealposter.html หรือ Notion)

**ราคาไม่ครบ ≠ บล็อกการโพสต์** (24 ส.ค. 69 — สินค้าบางตัวไม่มีราคาลด):
- intake ทั้ง 3 ทาง: `complete = !!name` (เดิม `!!(name && sale)`) → มีชื่อก็เข้าสถานะ "ใหม่" ได้เลย
- `Claude Write Caption`: ไม่มีราคา → สั่ง "ห้ามกล่าวถึงราคาหรือส่วนลดใด ๆ" (เดิมส่ง `null` เข้า prompt ตรง ๆ)
- `Build Caption` / `Split Approved`: มีทั้ง sale+full → `💥 เหลือ X (ลด Y%)` · มีแค่ sale → `💥 เหลือ X` · มีแค่ full → `💰 ราคา X` · ไม่มีเลย → ไม่มีบรรทัดราคา
- `Split Approved` สร้างแคปชันขั้นต่ำให้เองถ้าช่องแคปชันว่าง — **"อนุมัติแล้ว" = ต้องโพสต์เสมอ** (เดิม `.filter(i => i.json.caption)` ทิ้งเงียบ ๆ)

## แปลงลิงก์ Shopee ธรรมดาเป็น affiliate อัตโนมัติ (27 ก.ย. 2569) — ⛔ **ติดเกณฑ์ Shopee ยังขอ Open API ไม่ได้ (โค้ดพร้อม รอวันมีสิทธิ์)**
**27 ก.ย. 69 user เปิดหน้า help.shopee.co.th "ขั้นตอนการขอเปิด Affiliate Open API"**: ต้องยื่นฟอร์ม และเกณฑ์คือ (1) ยอดคำสั่งซื้อ affiliate **> 1,000 รายการ/เดือน** (2) มีเว็บ/ผู้ติดตามจำนวนมาก ส่ง Monthly visit / Reach / Engagement (3) เนื้อหาคุณภาพ ไม่ clickbait — ทีมงานตัดสินเป็นที่สิ้นสุด
→ บัญชีตอนนี้ (IG 1 follower, เว็บเพิ่งเปิด) ไม่ผ่านแน่ · **endpoint `/afflink` + intake patch เก็บไว้เฉย ๆ** (ไม่มี creds = ตอบ `no credentials` ใช้ลิงก์เดิม ไม่มีผลข้างเคียง) · ทางเลือกที่เสนอ user: (ก) กดแชร์จากปุ่ม affiliate ในแอป Shopee ("แชร์และรับค่าคอม") ได้ลิงก์ `s.shopee.co.th` เลย ไม่ต้องเข้าเว็บ (ข) เครือข่าย sub-affiliate เช่น Involve Asia / Accesstrade ที่มี deeplink API ให้ publisher ทั่วไป — เปลี่ยน backend ของ `/afflink` ไปเรียกแทนได้ (ยังไม่ได้ทำ/ยังไม่ได้ตรวจเงื่อนไข) (ค) ยื่นฟอร์มไว้ก่อนเผื่อผ่าน
→ **user เลือก (ก) 27 ก.ย. 69** · `Build Reply` (TG/LINE) เมื่อได้ลิงก์ Shopee ที่ไม่ใช่ affiliate จะเตือน: "ลิงก์นี้ยังไม่ใช่ลิงก์ affiliate (ค่าคอมจะไม่เข้า) — กดแชร์ด้วยปุ่ม 'แชร์และรับค่าคอม' แล้วส่งใหม่" (แถวยังถูกสร้างตามปกติ ไม่บล็อก)

(รายละเอียดเดิม — ยังใช้ได้ทันทีที่มี App ID/Secret)
user: "ส่งลิงก์ Shopee ไหนก็ได้ แล้วให้แปลงให้ เหมือนที่ทำมือในเว็บ affiliate" → ใช้ **Shopee Affiliate Open API** (ทางการ) ไม่ใช่กดเว็บแทนคน
- **endpoint ใน deal-video**: `POST http://deal-video:8080/afflink {url}` → `{ok, link, original, final, origin, reason}` (โค้ดใน `server.py` หัวข้อ Shopee affiliate link)
  ขั้นตอน: ไม่ใช่ Shopee → ข้าม · เป็น `s.shopee.co.th`/`shope.ee` อยู่แล้ว → คืนเดิม (`already affiliate`) · อื่น ๆ ตาม redirect ด้วย HEAD (แกะ `universal-link?redir=` ของ Shopee) → ต้องได้หน้าสินค้า `-i.<shop>.<item>` หรือ `/product/<shop>/<item>` หรือหน้าร้าน → เรียก GraphQL `generateShortLink(originUrl, subIds:["dealposter"])` ที่ `open-api.affiliate.shopee.co.th/graphql`
  ลายเซ็น: header `Authorization: SHA256 Credential=<appId>, Timestamp=<unix วินาที>, Signature=sha256(appId+timestamp+payload+secret)` (payload = JSON body ตรงตัวไบต์ต่อไบต์) · error code 10020 = ลายเซ็น/เวลาผิด · 10035 = บัญชียังไม่ได้สิทธิ์ Open API
  creds: `SHOPEE_AFF_APP_ID` / `SHOPEE_AFF_SECRET` ใน **`/root/deal-video/service/.env`** (ไม่อยู่ใน repo/n8n · เพิ่มแล้วต้อง `sh deploy.sh` เพราะ env ตรึงตอนสร้าง container) · ยังไม่มี = ตอบ `reason: no credentials` intake ใช้ลิงก์เดิม
  ⛔ **ลิงก์แชร์วิดีโอ Shopee (`th.shp.ee/...` → `sv.shopee.co.th/share-video/...`) แปลงไม่ได้** — หน้าไม่มี product id เลย (ตัวอย่างที่ user ส่งมาเป็นแบบนี้พอดี) ต้องแชร์จาก**หน้าสินค้า** · ตอบกลับในแชทจะบอกเหตุผล
- **intake ทั้ง 3 ทาง** (`Extract` ใน TG/LINE, `Prep` ใน Form): หลังหา `source` ถ้าเป็น shopee → `await this.helpers.httpRequest(... /afflink ...)` ใน try/catch → สำเร็จแทน `url` (เก็บ `origUrl`) · ไม่สำเร็จ `affNote` = เหตุผล · **ทุกอย่างปลายน้ำอ่าน `url` เดิม ไม่ต้องแก้ node อื่น** · `Build Reply` (TG/LINE) ต่อท้าย "🔗 แปลงเป็นลิงก์ affiliate ให้แล้ว" หรือ "⚠️ ยังไม่ใช่ลิงก์ affiliate (เหตุผล)"
- **ยังไม่ได้ทดสอบ intake จริงแบบ end-to-end** (ทดสอบแค่ endpoint จาก container + syntax ของ Code) เพราะทดสอบจริงต้องสร้างแถว Notion และไม่มี creds — รอบแรกที่ user ส่งลิงก์ Shopee ธรรมดา ให้ดู runData ของ `Extract` (`origUrl`/`affNote`) และ log `[afflink]` ใน `docker logs deal-video`
- วิธีขอ creds: เข้า https://affiliate.shopee.co.th → เมนู **Open API** (บางบัญชีต้องกดสมัคร/รออนุมัติ) → App ID + Secret → วางหน้า Notion Config หัวข้อ "Shopee Affiliate" แล้วใส่ .env · ทดสอบ: `docker exec deal-video python3 -c "import json,urllib.request;print(urllib.request.urlopen(urllib.request.Request('http://localhost:8080/afflink',json.dumps({'url':'https://shopee.co.th/product/<shop>/<item>'}).encode(),{'Content-Type':'application/json'})).read())"`
- Lazada ยังไม่ทำ (user ขอแค่ Shopee) — Lazada มี Open Platform แยกต่างหาก

**รอบ 15:00 น. 28 ก.ย. 69 ล้มทั้งรอบเพราะ Telegram ล่มชั่วคราว (exec 39651)** — `Post to Telegram` timeout 30 วิ ทั้ง 6 ดีล (onError continue → TG Verify sent=false ทุกตัว) → `TG Send Text` (fallback ข้อความ) ล้ม "connection closed unexpectedly" และ node นี้**ไม่มี onError** → execution error ตั้งแต่ขั้น TG → FB/Threads/Mark Posted ไม่รัน · ไม่มีอะไรโพสต์เลย (ดีล 6 ตัวยัง อนุมัติแล้ว ไปรอบ 18:00 ไม่ซ้ำ) · 08:24 UTC เช็คแล้ว n8n→api.telegram.org ปกติ = ล่มชั่วคราว ~10 นาที
→ แก้: `TG Send Text` ใส่ `onError: continueRegularOutput` (เหมือน Post to Telegram/FB/Threads/IG Reel) — Telegram ล่ม = ช่องอื่นยังโพสต์และมาร์คได้ · **บทเรียน: node httpRequest ทุกตัวในสายโพสต์ต้องมี onError continue** (ตัวที่ยังไม่มี: `Fetch Deal Image`/`Fetch Photo Bin`/`Query Approved Deals`/`Mark Posted` — ถ้า Notion ล่มก็ล้มทั้งรอบ ซึ่งถูกต้องอยู่แล้ว)

## Token / Credential (28 ส.ค. 2569)
- **Notion token ไม่ฝังใน workflow แล้ว** — ย้ายเข้า n8n credential **`Notion Deal Poster (Header Auth)`** (id `U5mfqJ7z2OV1c4PT`, type httpHeaderAuth) ครบทั้ง 12 จุดใน 5 workflow
  - Landing Page: โหนด `Query Posted Deals` แปลงจาก Code (fetch วนหน้า) → httpRequest ใช้ credential ดึงหน้าเดียว `page_size: 100` เรียงใหม่สุดก่อน — เทียบ HTML ก่อน/หลังแล้ว **byte-identical** (หน้า live แสดง 100 รายการล่าสุดเท่าเดิม)
    ⚠️ **การแปลงนี้ทำเพดาน 100 ดีลกลับมาเงียบ ๆ** (ตอน 27 ส.ค. เทียบ byte-identical เพราะตอนนั้นมี ≤100 ดีลพอดี) — user เห็นหน้ารวมดีลมีแค่ 2 หน้า 19 ก.ย. 69 ทั้งที่ Notion มี 365 แถว
    **แก้แล้ว 19 ก.ย. 69**: ใช้ **pagination ในตัว httpRequest v4.2** (`options.pagination`: mode `updateAParameterInEachRequest` body `start_cursor` = `{{ $response.body.next_cursor }}`, จบเมื่อ `!$response.body.has_more`, max 20 หน้า)
    → ยังใช้ credential เดิม ไม่ต้องเอา token กลับไปฝังใน Code · node คืน 1 item/หน้า ดังนั้น `Build Page` อ่าน `$input.all().flatMap(i => i.json.results)` แทน `$input.first()` · หน้า live ตอนนี้ 365 การ์ด = 8 หน้า โหลด ~2.6 วิ
  - **จำกัดขนาดหน้า + cache แล้ว 20 ก.ย. 69** (ตอบคำถาม "Notion มีลิมิตไหม ควรย้าย DB ไป VPS ไหม") — **ยังอยู่ Notion ต่อ ไม่ย้าย**
    เหตุผล: Notion ไม่ใช่แค่ที่เก็บ แต่เป็น **หน้าจอแก้/อนุมัติดีล** ด้วย · ข้อมูลจริงเล็กมาก (431 แถว, แคปชันเฉลี่ย 266 ตัวอักษร → ไม่ถึง 1 MB)
    **ลิมิตที่เป็นปัญหาจริงคือฝั่งอ่าน ไม่ใช่ฝั่งเก็บ**: API ดึงทีละ 100 แถว (อ่านทั้ง DB = ceil(n/100) requests) · rate limit ~3 req/วินาที/integration · แพลนฟรีคนเดียวเก็บได้ไม่จำกัด (เพดาน 1,000 block ใช้กับ workspace หลายคนเท่านั้น)
    อัตราโต **~14 ดีล/วัน** (ส.ค. 143 · ก.ย. 1–20 = 288) → ถ้าไม่ทำอะไรจะชนเพดาน 20 หน้า (2,000 แถว) ราวต้น ม.ค. 2570 และหน้าเว็บจะช้าขึ้นเรื่อย ๆ
    - `Query Posted Deals` เพิ่มเงื่อนไข **`โพสต์เมื่อ` ≥ 90 วันล่าสุด** (filter เป็น `and` + jsonBody เป็น expression `={{ new Date(Date.now() - 7776000000).toISOString().slice(0,10) }}`) — ดีลเก่าราคาเพี้ยน/ลิงก์อาจตาย ไม่ควรโชว์
    - `maxRequests` **20 → 5** = เพดานตั้งใจ 500 ดีลใหม่สุด (เรียง `โพสต์เมื่อ` desc อยู่แล้ว → ตัดหน้าท้ายคือตัดของเก่าสุด) · **กันคนละแบบ**: filter กันดีลเก่าตกค้างตอนโพสต์น้อย, cap กันหน้าบวมตอนโพสต์เยอะ
    - ⚠️ ทั้งสองอย่างนี้ **ยังไม่ตัดอะไรออกวันนี้** (ดีลเก่าสุด 17 ส.ค. = 34 วัน, 380 แถว < 500) — เทียบก่อน/หลังได้ 380 การ์ดเท่าเดิม ถ้าวันหลังเห็นจำนวนการ์ดนิ่งที่ ~500 แปลว่าชน cap ไม่ใช่บั๊ก
  - **rotate Notion token**: สร้าง secret ใหม่ที่ notion.so/profile/integrations → แก้ค่าใน credential เดียวผ่าน n8n UI (Credentials → Notion Deal Poster) — ไม่ต้องแตะ workflow ใดเลย
- **Telegram bot token ยังฝังใน URL** (4 โหนด: `Post to Telegram`/`TG Send Text` ใน Poster, `TG Confirm`/`TG Help` ใน Intake TG) — **ย้ายเข้า credential ไม่ได้**: token อยู่ใน URL path ซึ่ง generic credential ของ n8n ฉีดให้ไม่ได้ และเปลี่ยนเป็น Telegram node จะเสีย batching 60 วิ (throttle ที่ตั้งใจ)
  - **rotate Telegram token**: BotFather → `/revoke` @sup_dealposter_bot ได้ token ใหม่ → GET สด 2 workflow (`E6i2xEAcaUsUFKWm`, `JUE23JTCBbCsW1lS`) → replace string `bot<เก่า>` → `bot<ใหม่>` → PUT + deactivate→activate
- ที่ยังฝังโดยตั้งใจ: FB page token (never-expire), Threads (Token Keeper หา token ด้วย regex จาก workflow — **ห้ามย้าย**), Anthropic key + LINE channel token (ยังฝัง — ผู้สมัครรอบถัดไปถ้าจะย้ายเพิ่ม ทำแบบเดียวกับ Notion ได้เพราะเป็น header ทั้งคู่)

## Veo (Google) ฉากสินค้าเคลื่อนไหวแทนรูปนิ่ง — ทดลอง 2 ต.ค. 2569 (user: "ทำผ่าน API เลย ลอง 3 ดีลก่อน")
ที่มา: user ถาม "ขยับไปเป็นคลิปรีวิวสินค้าได้มั้ย เห็นเค้าใช้ Google Flow" → Flow ไม่มี API (กดมือ) จึงใช้ **Veo 3.1 ผ่าน Gemini API** key เดียวกับ Gemini TTS (`GOOGLE_AI_KEY`) · ราคา (ต.ค. 69) Lite $0.05/วิ ≈ $0.40/คลิป 8 วิ · Fast $0.10/วิ · Standard $0.40/วิ · โมเดลที่ key เห็น: `veo-3.1-{lite,fast,}-generate-preview` (method `predictLongRunning`)
- **โค้ด** `server.py`: `/render {"veo": true}` → `veo_clip()` ส่ง `product.jpg` เป็น image-to-video (9:16, 8 วิ, 720p) → poll operation ทุก 8 วิ (timeout `VEO_TIMEOUT` 240) → ดาวน์โหลด mp4 → ทำ **boomerang** (ไป-กลับ 16 วิ, `reverse` บัฟเฟอร์ ~260MB ยังอยู่ในลิมิต 700m) → เรนเดอร์หลักใช้ `-stream_loop -1` เป็นพื้นหลัง**เต็มเฟรม** แทน bg เบลอ+รูปซูม+กรอบขาว · เพิ่มแถบมืดบน/ล่าง 3 ขั้นให้ตัวหนังสืออ่านออก · ป้าย %/ราคา/บทพากย์/เพลง/CTA เหมือนเดิมทุกอย่าง · **ล้ม/402/ถูกกรอง → ถอยไปเรนเดอร์แบบเดิมอัตโนมัติ** (JSON `veo:{ok,error,gen_s}` · header `X-Veo` · log `[render] veo ok=… gen=…s err=…` และ `[timing] … veo=`) · env `VEO_MODEL` เปลี่ยนรุ่นได้ · backup `server.py.bak.20261002`
- **ผลเทส 2 ต.ค. 69**: สร้างสำเร็จ 3/3 (gen 44/45/79 วิ, render รวม 84/87/119 วิ, ไฟล์ 2.8–3.4MB ใหญ่กว่าเดิม ~3 เท่า) **แต่ 3 ดีลแรกเป็น Lazada ทั้งหมด → รูป `รูป` (og:image) ของ Lazada เป็นแบนเนอร์ creative-center** (การ์ดชมพูมีช่องดำ) ไม่ใช่รูปสินค้า → Veo ทำเป็น "แท็บเล็ต/กล่องชมพูที่มีแบนเนอร์พิมพ์อยู่" ใช้ไม่ได้ → ใส่กติกา **ข้าม Veo ถ้า img มี `lazada-creative-center`** (ตอบ `skip: lazada banner image`) · ส่งเฟรมตัวอย่างให้ user ดูทาง TG แล้ว (ไม่ส่งคลิปเพราะไม่ใช่ตัวแทนผลจริง)
  · เปลี่ยนไปเทส Shopee 3 ดีล (รูปสินค้าจริง: GOOJODOQ powerbank / เคส Aramid / JASMALI diffuser — ใน `/root/deal-video/veo_test_deals2.json`) → **HTTP 402 `RESOURCE_EXHAUSTED: Your prepayment credits are depleted`** — billing ของ AI Studio เป็นแบบเติมเงินล่วงหน้า หมดหลัง Veo 3 คลิป+TTS → fallback ทำงานถูก (คลิปปกติ 3/3) **แต่ Gemini TTS ก็ 402 ด้วย → ทุกคลิปในรอบโพสต์ใช้ Azure Niwat จนกว่า user เติมเครดิตที่ https://ai.studio/projects** (ดู log `gemini tts failed … HTTP 402 -> fallback azure niwat`)
  · **ค้างทำต่อเมื่อเติมเครดิตแล้ว**: รันเทส Shopee 3 ดีลซ้ำ (คำสั่งอยู่ใน transcript 2 ต.ค. — docker exec deal-video POST /render ด้วย deal + `veo:true, voice:true` แล้ว `docker cp` ออกมาที่ `/root/deal-video/veo_out/`) → ดูเฟรม (ffmpeg -ss ดึง 4 เฟรม hstack) ก่อนส่ง TG ให้ user ตัดสิน → ถ้าผ่านค่อยต่อ n8n: `IG Reel` ใส่ `veo:true` เฉพาะดีลเด่น 1 ตัว/รอบ (เวลา /render จะเป็น ~90–120 วิ ยังอยู่ในงบ 300 วิ/ดีลของ task) + ตั้งเพดานงบรายวัน
- **`bg_video: <url>` (2 ต.ค. 69)**: user มี Veo 3.1 Fast ใน Flow อีกที่ → สร้างเองแล้วส่งคลิปมาทาง Telegram (แชทบอท @sup_dealposter_bot = chat 8336016992) → ดึง `file_id` จาก execution ของ Deal Intake Telegram (webhook รับทุกข้อความ) → `getFile` → ส่ง URL `https://api.telegram.org/file/bot…/<path>` ให้ `/render {bg_video}` (ข้าม Veo ใช้ path boomerang เดิม) · prompt + รูปสินค้า 3 ดีลส่งให้ user แล้ว TG msg 1715–1719 (`VEO_PROMPT` ใน server.py)
  · **ผล 3 ดีล Shopee ด้วยคลิปที่ user สร้างใน Flow (2 ต.ค. 69 13:27–13:41 UTC)**: ทั้ง 3 ประกอบผ่าน (29–41 วิ/คลิป, ไฟล์ 2.4–3.5MB) ส่ง TG msg 1722 (ดีล 1 + 1723 แบบเดิมไว้เทียบ) / 1726 / 1727 · สินค้าตรงของจริงทั้ง 3 ตัวหนังสืออ่านออกบนแถบมืด · ข้อสังเกต: (1) user ส่งมาเป็น **แนวนอน 1280×720 ยาว 4–5 วิ** → ครอปกลางเป็น 9:16 สินค้าขยายเต็มจอชนบรรทัดชื่อ — ครั้งหน้าให้สร้าง 9:16 ตั้งแต่ใน Flow (2) โหมด Frames-to-Video เริ่มจากรูปต้นทางเป๊ะ → **ตัวหนังสือบนรูปสินค้าติดมาในวินาทีแรก** และโผล่อีกตอน boomerang วนกลับ — แก้ได้ด้วยใช้รูปเป็น Ingredient แทน หรือฝั่งเราตัดหัวคลิป ~0.5 วิ (ยังไม่ทำ) (3) คลิปที่ส่งผ่าน TG หา `file_id` จาก execution ของ Deal Intake Telegram (ล่าสุดที่ `message.video` มี) ต้องเทียบ `int(e['id'])` (API คืน id เป็น string) · ไฟล์ทั้งหมดอยู่ `/root/deal-video/veo_out/` (`flowN_src.mp4` ต้นฉบับ · `flowN_render.mp4` ผล · `*_tile.jpg` เฟรมตรวจ) · **รอ user ตัดสินว่าจะเดินต่อแบบไหน** (API อัตโนมัติหลังเติมเครดิต / user สร้างใน Flow เองแล้วส่งมา)
  · **หลังเติมเครดิต (13:44 UTC)** รัน API ซ้ำ 3 ดีล Shopee: สร้าง 46–47 วิ รวม 75–83 วิ/คลิป ส่ง TG 1730–1732 · API ขอ 9:16 ได้ตรง สินค้าอยู่ครึ่งบนไม่ชนตัวหนังสือ (ดีกว่าคลิป Flow แนวนอนของ user) · เฟรมแรก ~1 วิเป็นรูปนิ่งต้นทาง (API มีขอบดำ / Flow มีตัวหนังสือ) → **`VEO_TRIM`=1.0 วิ ตัดหัวก่อน boomerang** (deploy 13:55 UTC พร้อม CTA ใหม่ · ยืนยัน 14:30 UTC ด้วยดีล 3 bg_video: เฟรมแรกเป็นฉากเคลื่อนไหวแล้ว ไม่มีรูปนิ่ง/ขอบดำ) · deploy รอบ 14:28 UTC = server.py ที่มี review/publish/discard ขึ้นแล้ว sample.sh ผ่าน 2 โหมด
  · **เสียงอ่านชื่อเว็บเพี้ยน** (user: 'paiyaadeals.com' เพี้ยน) → ส่งเทียบ 4 แบบ TG 1733–1736 user เลือก A/B → บทพูด `CTAS` ทั้ง 8 สำนวนใช้ **'ป้ายยาดีล ดอทคอม'** (บนจอยัง paiyaadeals.com) · บทเรียน: **ชื่อเว็บ/URL ในบทพูดต้องเขียนเป็นคำอ่านไทย** TTS ทุกตัวอ่าน URL อังกฤษไม่เป็นธรรมชาติ
- **ขั้น review ก่อนโพสต์ (2 ต.ค. 69 user: "ตกลง ส่งให้ดูก่อนโพสต์ แล้วค่อยเปิดอัตโนมัติ")** — ดีล 1 ของ API (Veo Lite) วาดพาวเวอร์แบงค์เป็นคนละรุ่น (ของทรงเฉพาะ AI เดาด้านที่มองไม่เห็นผิด) → คลิป Veo ทุกตัวต้องผ่านตา user ก่อน:
  · `IG Reel`: `VEO = {enabled:true, perRound:1}` → run 0 ของรอบส่ง `veo:true, page_id, review:{url,chat_id,caption}` (+ telegram/tiktok เดิม) · token บอทรวมเป็น `TG_BOT` ตัวเดียว · output เพิ่ม `veoReview/veoPending/veo`
  · `server.py` `/render`: Veo สำเร็จ + มี review → เก็บ mp4+meta ไว้ **`/tiktok/pending/<page_id>.{mp4,json}`** (host `/root/deal-video/tiktok/pending/`) ส่ง TG caption บรรทัดแรก `#veo <id>` + วิธีตอบ **ไม่โพสต์ TikTok** · Veo ล้ม/ข้าม/เกินโควตา (`VEO_DAILY_MAX`=8/วัน นับใน `/tiktok/veo_count.json`) → ทำแบบเดิม (TG + TikTok ตรง) · pending > 48 ชม. ลบทิ้ง
  · **`POST /publish {id}`** → tt_post ด้วย tiktok opts ที่เก็บไว้ → ลบ pending · **`POST /discard {id}`** · 404 = ไม่มีคลิปค้าง
  · `Deal Intake Telegram`: `Extract` เห็น `message.reply_to_message.caption` มี `#veo <id>` → ข้อความ โพสต์/ลง/ok/ตกลง = `/publish`, ไม่/ทิ้ง/no/ยกเลิก = `/discard`, อื่น ๆ = บอกวิธีตอบ → คืน `veoReply` → node ใหม่ **`Veo Reply?`** (IF) → **`Build Veo Reply`** → `TG Confirm` (false → `Has URL?` เดิม) · **user ต้องกด Reply ที่ข้อความคลิป** พิมพ์ลอย ๆ ไม่นับ
  · ✅ **e2e ผ่าน 2 ต.ค. 69 14:37–14:41 UTC**: render veo+review (JASMALI, page_id veotest3) → review:true, TG msg 1737, pending มี 2 ไฟล์, veo_count 1 → webhook "โพสต์" → exec 41909: Extract veoReply ✅ → Veo Reply? → Build Veo Reply → TG Confirm (msg 1738) · log `tiktok=12.4s PUBLISH_COMPLETE (review publish veotest3)` · pending ว่าง → รอบสอง bg_video page_id veotest3b → webhook "ไม่" → 🗑 (msg 1742) ไฟล์หาย · ข้อความ 1737–1742 ในแชทเป็นของทดสอบ
  · ทดสอบ e2e: ยิง webhook `deal-intake-tg-x7k2` ด้วย update ปลอม `{message:{chat:{id:8336016992},text:'โพสต์',reply_to_message:{caption:'#veo <id>'}}}` (sandbox SELF_ONLY ไม่มีใครเห็น) · เปิดอัตโนมัติเต็มตัวทีหลัง = ตัด review ออก (ส่ง `tiktok` ตรงแทน) หลัง user พอใจความตรงของสินค้า
- **ทดสอบความตรงของสินค้า ดีล 1 (2 ต.ค. 69 14:44–14:50 UTC)** หลัง user ท้วงว่า Lite วาดพาวเวอร์แบงค์คนละรุ่น: (ก) **Fast + prompt เดิม → ตรงของจริง** (ก้อนม่วงเล็กมีหัวเสียบ, gen 55 วิ, $0.80) ส่ง TG 1745 · (ข) Lite + prompt สินค้านิ่ง+veo_desc → ได้แค่ซูมรูปต้นฉบับเบลอ ๆ พร้อมตัวหนังสือบนรูป ใช้ไม่ได้ → **ค่า default ควรเป็น Fast** (`VEO_MODEL` env หรือ `veo_model` ต่อคำขอ) ≈ ฿28/คลิป → **user เคาะ 2 ต.ค. 69: 'ใช้ Fast แต่ลดเหลือ 5 คลิป/วัน'** → default `VEO_MODEL`=fast, `VEO_DAILY_MAX`=5 (≈ ฿140/วัน ≈ ฿4,200/เดือน) · โควตานับตามวันไทย → 5 รอบแรก (00/06/09/12/15 น.) ได้ Veo รอบ 18/21 เป็นคลิปแบบเดิม+TikTok ตรง · deploy 14:56 UTC
  · **Fast คืนคลิปมีแถบดำบน/ล่างตลอด** (image-to-video จากรูปจัตุรัส) → `_boomerang` วัดแถบดำเองจากเฟรมเดียว (ffmpeg gray rawvideo → หาแถวบน/ล่างค่าเฉลี่ย < 24 → ครอปเฉพาะแถบเต็มความกว้าง ≥ 80px) · ⛔ `cropdetect` ของ ffmpeg ใช้ไม่ได้ (บนฉากสว่างคืนกล่องเล็กกลางเฟรม 404x406) · ทดสอบด้วยคลิป letterbox สังเคราะห์ (`file:///tiktok/test_lb.mp4` ผ่าน bg_video — urllib รับ file:// ได้) → `crop=720:428:0:426` ถูกต้อง · log `[render] veo crop=…`
- **user เคาะรอบสุดท้าย 2 ต.ค. 69: "ใช้ Fast 4 คลิป/วัน สลับกับผม gen ใน Flow เองแล้วส่งคลิปให้"** → `VEO_DAILY_MAX`=4 (รอบ 00/06/09/12 น. ได้ Veo API + review · รอบ 15/18/21 คลิปแบบเดิม + TikTok ตรง และ user ส่งคลิป Flow มาแทนได้)
  · **ทางรับคลิปที่ user สร้างเอง**: ทุก /render ที่มี `page_id` → service เก็บฟิลด์ดีล (name/sale/full/desc/cat/img + title=แคปชัน TG) ไว้ **`/tiktok/deals/<page_id>.json`** (7 วัน) และต่อท้าย caption คลิป TG ด้วย **`#d <page_id>`** · user **Reply ข้อความคลิปนั้นด้วยวิดีโอ** → `Extract` (Intake TG) เห็น `message.video` + `#d` → `getFile` (token `TG_BOT` ฝังใน Extract แล้ว — sanitize จับได้) → `POST /render {deal_id, bg_video:<tg file url>, voice:true, tiktok:{sandbox,SELF_ONLY}, telegram:{คลิปผลกลับ}}` → service เติมฟิลด์จากไฟล์ (`deal_id` ไม่พบ = 404) → ประกอบ + **ลง TikTok ตรงทันที** (user ทำเอง = อนุมัติแล้ว ไม่ผ่าน review) → ตอบ ✅/❌ · e2e ผ่าน 14:59 UTC (exec 41919: render 39 วิ + TG 4 วิ + TikTok 12 วิ PUBLISH_COMPLETE, msg 1746–1747 เป็นของทดสอบ)
  · ⛔ **พลาดตอนทดสอบ 2 ต.ค. 69 (ซ้ำบทเรียน 26 ก.ย.)**: จำลอง Reply ด้วย file_id ของคลิป Flow **ดีล 3 (JASMALI)** แต่ใส่ deal_id ของ **ดีล 1 (พาวเวอร์แบงค์)** → คลิปขวดน้ำหอมที่มีป้ายราคา/บทพากย์พาวเวอร์แบงค์ **ถูกลง TikTok sandbox จริง** (SELF_ONLY เห็นเฉพาะเจ้าของ · API ไม่มี endpoint ลบ → user ต้องลบเองในแอป แท็บ 🔒) · user เห็นแล้วท้วง "ภาพ คลิป ข้อความ ไม่ตรงกันเลย แต่ลง TikTok แล้ว" · **กฎ: ทดสอบ path ที่โพสต์ของจริง ต้องใช้คู่ (คลิป, ดีล) ที่ตรงกันเท่านั้น หรือส่ง `tiktok` เป็น undefined ตอนทดสอบ** · ในการใช้จริง ดีลถูกกำหนดจากข้อความที่ user Reply จึงไม่เกิดแบบนี้เองถ้า Reply ถูกข้อความ
  · **user ไม่เข้าใจว่าเอารูป/prompt จากไหน (2 ต.ค. 69, user ใช้ aipass.net เลือก Veo 3.1 Fast)** → service ส่ง **ข้อความรูปสินค้า + วิธีทำ 3 ขั้น + VEO_PROMPT + `#d <id>`** (`tg_send_photo` binary) เมื่อ IG Reel ขอ veo+review แต่ Veo ไม่ได้ (เกินโควตา 4/วัน = รอบ 15/18/21 น., ล้ม) และรูปไม่ใช่แบนเนอร์ Lazada → user เซฟรูป + วาง prompt ใน aipass (9:16) → **Reply คลิปกลับที่ข้อความรูปนั้น** (caption มี #d เหมือนกัน) → ประกอบ+ลง TikTok · JSON `photo_sent/photo_message_id` · log `[review] veo unavailable (...) -> photo for manual Veo` · ทดสอบ 15:17 UTC: msg 1748 (รูป+prompt) + 1749 (คลิปปกติ) deal `jasmali-demo` เก็บไว้ให้ user ลอง Reply คลิป Flow ของ JASMALI
  · ⚠️ caption TG ถูกตัดที่ 960 ตัวก่อนต่อ `#d` (tg_send_video จำกัด 1000) · ไฟล์ทดสอบ `/root/deal-video/tiktok/deals/dtest1.json` ลบได้
- **เลย์เอาต์โหมด Veo เปลี่ยน 2 ต.ค. 69 15:37 UTC** (user: "ตัวหนังสือบังสินค้า และภาพเคลื่อนนิดเดียว") → ฉาก Veo คมเฉพาะ**ช่องบน y 0–790** (zoompan ซูมช้า 1→1.16 ต่อเนื่องทั้งคลิป + crop กลาง) ส่วนล่างเป็น `bg.png` (รูปสินค้าเบลอ) ใต้ตัวหนังสือทั้งหมด (ชื่อ y≥836/ราคา/CTA) · input 1 ของ ffmpeg ในโหมดนี้ = bg.png (ไม่ใช่ fg.png) · ⛔ `crop` ด้วย expression `t` ใช้ซูมไม่ได้ (w/h ประเมินครั้งเดียว → ffmpeg 'Error initializing filters') ต้อง `zoompan=...:d=1` บนวิดีโอ · prompt เปลี่ยน push-in → "camera slowly orbits" ให้เคลื่อนไหวมากขึ้น · ตัวอย่างส่ง TG (JASMALI คลิปของ user, ไม่ลง TikTok) → user: "แถบสีดำบังสินค้าหมดเลย" (คลิปแนวนอนถูกซูม 1.78x เป็น 720x1280 ก่อนตัด 790 → ขวดโดนตัดครึ่ง) → **แก้ 15:44 UTC: `_boomerang` ทำช่องบน 720x790 จากต้นฉบับโดยตรง** `scale=720:790:force_original_aspect_ratio=increase,crop=720:790:(iw-720)/2:min(40\,ih-790)` — แนวนอนย่อให้สูง 790 พอดี (เห็นสินค้าเต็มตัว ตัดแค่ข้าง) · แนวตั้ง 9:16 ตัดส่วนบนจาก y 40 · zoompan `s=720x790` → user ดูคลิป Seedance (496x864) แล้ว: "แถบสีดำยังบังตัวสินค้าอยู่ เอาตัวหนังสือลง เอาสีดำออกเป็นแบบโปร่งใส ไม่ลดขนาดภาพ" → **เลย์เอาต์สุดท้าย 15:59 UTC (user: 'โอเคแล้ว ใช้แบบนี้' กับเวอร์ชันก่อน แต่สั่งแก้ต่อ)**: วิดีโอ**เต็มเฟรม 720x1280** (scale increase+crop กลาง = เห็นสินค้าเต็มความสูงเสมอ ไม่ว่าต้นฉบับแนวไหน) + zoompan 1→1.16 · **ไม่มีแถบมืด** · ตัวหนังสือทุกบรรทัดเลื่อนลง `DY`=150 (ชื่อ 986/1046, ราคาเดิม 1108, ราคาใหม่ 1186) + ขอบดำ `\bord3\3c&H000000&` (`OUT` ต่อท้าย tags ใน ev/ev2) · แถบ CTA บาง y 1222–1280 fs46 · ไม่มีบรรทัด @paiyaa_deals ในโหมดนี้ · โหมดปกติ (รูปนิ่ง) ไม่เปลี่ยน
  · **Seedance 2.0 Fast (aipass) ทดสอบ JASMALI**: 496x864 6 วิ — ขวดหมุน+กล้องเคลื่อนชัดกว่า Veo Fast มาก สินค้าตรง (ขวด/ก้าน/ฉลาก) แต่**กล่องหาย** (เลือกเก็บเฉพาะขวด) · ใช้กับ pipeline ได้ทันที (bg_video ไม่สนโมเดล)
- ✅ **รอบจริง 2 รอบแรก (3 ต.ค. 69)**: 00:00 น. exec 41966 (17:00–17:14 UTC, 6 ดีล, เพลงล้วน) — run 0 `veoReview:true` pending `3edfd547…6978` Veo Fast gen 71.7 วิ crop แถบดำ `720:720:0:280` render 89.5 วิ · review TG ส่ง 3.5 วิ · user ตอบ 'โพสต์' → `/publish` PUBLISH_COMPLETE sandbox · run 1–5 คลิปปกติ · Threads 2/2 · Mark Posted 6 · 06:00 น. exec 42098 (23:00–23:15 UTC) — Veo gen 55.2 วิ pending `…8174…4c08` (น้ำหอมสีชา) user ยังไม่ตอบ → ผมสั่ง `/publish` ให้เอง 01:00 UTC ตามคำสั่งใหม่ด้านล่าง (PUBLISH_COMPLETE) · veo_count 2026-10-03 = 2
- **ปิดขั้นรอตรวจ 3 ต.ค. 69 01:00 UTC (user: 'คลิปที่คุณสร้างให้ โพสต์ได้เลย ผมค่อยไปดูเอง')** → `server.py` เพิ่ม **`VEO_REVIEW`** (env, ค่าเริ่มต้น `0`): Veo สำเร็จ = ลง TikTok ตรง (sandbox SELF_ONLY จนผ่าน audit) + ส่งคลิปเข้า TG เป็นสำเนา caption นำหน้า `🎬 คลิป Veo (gen Ns) → ลง TikTok อัตโนมัติ` (เติมก่อนตัด 960 ตัว `#d` ท้ายไม่หาย · `deal_save` อ่าน caption เดิมก่อนเติม) · `VEO_REVIEW=1` ใน `.env` = กลับไปโหมด pending/reply เดิม · **n8n `IG Reel` ไม่ต้องแก้** ยังส่ง `review:{url,chat_id,caption}` เพราะ path 'รูป+prompt ให้ user ทำเอง' (รอบ 15/18/21) ใช้ url/chat_id จากมัน · `/publish`/`/discard`/`#veo` reply ยังอยู่ (ใช้กับ pending เก่า/โหมด 1) · deploy 00:58 UTC running=0 · backup `server.py.bak.20261003` · sample.sh ผ่าน 2 โหมด (พากย์ 17.1 / เพลง 11.7 วิ) · **ที่คลิปไปอยู่**: TikTok @sup.tw แท็บ 🔒 (SELF_ONLY) + แชท TG บอท · IG พักถึง 26 ต.ค. · FB/Threads เป็นรูปไม่ใช่คลิป
- ⚠️ Veo ใช้เวลา 1–3 นาที/คลิปและ service เรนเดอร์ทีละคำขอ → ห้ามใส่ `veo` ทุกดีล · TikTok/IG ต้องติดป้าย AI-generated (ตอนโพสต์ผ่าน TikTok API มีฟิลด์ให้ติด ยังไม่ได้ทำ) · บทพูดห้ามอ้างว่า "ใช้แล้วดี" (บทปัจจุบันไม่อ้างอยู่แล้ว)

## Facebook Reels ของเพจ — เริ่ม 3 ต.ค. 2569 (user: "คลิปเคลื่อนไหวนอกจาก TikTok ลงที่อื่นด้วยมั้ย" → "เริ่มเลย")
- **โค้ด** `server.py` `fb_reel_post(fr, mp4)`: `/render {fb_reel:{page_id, token, description}}` → `POST /{page}/video_reels upload_phase=start` (ได้ `video_id` + **`upload_url`**) → `POST <upload_url>` binary (header `Authorization: OAuth`, `offset: 0`, `file_size`) → `upload_phase=finish video_state=PUBLISHED description=…` → poll `GET /{video_id}?fields=status` ≤ 60 วิ จน `publishing_phase.status=complete` · ตอบ `fb_reel:{ok,video_id,post_id,status,phase,upload_s,error}` · log `[timing] fb_reel=…` · ล้ม = HTTP 502 (TG/TikTok ที่ส่งก่อนไม่กระทบ) · เก็บใน pending meta ด้วย → `/publish` (โหมด VEO_REVIEW=1) โพสต์ FB Reel ต่อจาก TikTok
  ⛔ **ต้องใช้ `upload_url` ที่ start คืนมา** — เดา path เองเป็น `rupload.facebook.com/video-reels/v21.0/<id>` ได้ 400 `InvalidEndpointError` (path จริง `video-upload`) · container ที่ start แล้วไม่ finish จะค้างเป็นวิดีโอไม่เผยแพร่ ไม่มีใครเห็น (เกิด 2 อัน 3 ต.ค. ตอนทดสอบ)
- **n8n `IG Reel`**: `FB_REELS = {enabled:true, perRound:1, page_id:'1330886503433772'}` → ดีลแรกของรอบ (`g.n ≤ perRound` เหมือน TikTok) ส่ง `fb_reel:{page_id, token: TOKEN, description: capT + '🔗 รวมดีลทั้งหมดที่ paiyaadeals.com'}` · **TOKEN ใน IG Reel = page token ของเพจ ป้ายยาดีลเด็ด อยู่แล้ว** (IG ใช้ page token · ตรวจ `/me` = 1330886503433772) ไม่ต้องย้าย token · output `fbReel:{ok,status,phase,video_id,error}` · ผลคือดีลแรกของรอบได้ **TikTok + FB Reels + TG** พร้อมกันจากคลิปเดียว
  · ผลข้างเคียงที่ยอมรับ: ดีลแรกของรอบขึ้นเพจ 2 แบบ (รูปจาก `Post to Facebook` + Reel) — ไม่ข้ามรูปเพราะ Threads ยืม URL รูปจาก FB (`FB Photo URL`) และ Threads โพสต์แค่ 2 ดีลแรก · ถ้าเพจเริ่มโดนจำกัดแบบ IG ให้ลด perRound/วัน ก่อนอื่น
- ✅ **Reel แรกของเพจ 3 ต.ค. 69 02:53 UTC**: ดีล CIVAGO แก้วกาแฟ ประกอบจากคลิป Seedance ที่ user ส่ง (496x864 7 วิ) + พากย์ → render 24 วิ · upload 4.3 วิ · ประมวลผลเสร็จใน 28 วิ `status=ready phase=complete` · video `1757202395578942` post `122115130545453222` · สำเนาส่ง TG แล้ว (ไม่ลง TikTok ซ้ำเพราะลงไปแล้ว 01:32 UTC) · deploy 02:49 UTC running=0 · backup `server.py.bak.20261003c` · sample.sh ผ่าน 2 โหมด
- ✅ **คลิปที่ user ส่งเองก็ลง FB Reels แล้ว (3 ต.ค. 69 03:11 UTC, user: 'ทำให้คลิปที่ผมส่งเองลง Facebook Reels ด้วย')** — ไม่ย้าย token ไป Intake TG: `IG Reel` ส่ง `fb_reel` **ทุกดีล** โดย `post: g.n <= perRound` (service โพสต์เฉพาะ post:true) → `deal_save` เก็บ `fb_reel{page_id,token,description}` ไว้ในไฟล์ดีล `/tiktok/deals/<page_id>.json` (chmod 600, 7 วัน) → path `deal_id` (Reply คลิป) คืน `fb_reel` ให้พร้อม post:true → คลิปของ user ลง TikTok + FB Reels + TG ในคำขอเดียว · ทดสอบ: render page_id fbtest1 post:false → ไฟล์มี fb_reel ครบ 3 คีย์ 600 และไม่โพสต์ · ⚠️ ดีลที่ไฟล์สร้างก่อน 03:11 UTC (iPad รอบ 09:00, CIVAGO ที่เขียนมือ) ไม่มี token → ส่งคลิปมาจะได้ TikTok อย่างเดียว · e2e จริงรอคลิปถัดไปที่ user ส่ง (ดู log `[timing] fb_reel`) · backup `server.py.bak.20261003d`
- **ยังไม่ทำ**: YouTube Shorts (user ต้องตั้ง Google Cloud OAuth เอง) · Threads วิดีโอ (ต้องฝากไฟล์บน paiyaadeals.com) · IG Reels กลับมา 27 ต.ค. · รอบจริงรอบแรกที่ fb_reel ผ่าน n8n = 12:00 น. 3 ต.ค. (exec ที่เริ่ม 05:00 UTC) → ดู runData `IG Reel` run 0 `fbReel.ok`

## TikTok โพสต์อัตโนมัติผ่าน Content Posting API — เริ่ม 28 ก.ย. 2569 (user: "เดินข้อ 2 เลย")
**คนละระบบกับ TikTok Shop Partner Center** (ที่ติดนิติบุคคล) — อันนี้คือ **TikTok for Developers** (developers.tiktok.com) สมัครแบบบุคคลได้ · บัญชีที่จะโพสต์ = **@sup.tw "Paiyaa deal"** (บัญชีเดิมของ user ที่ผูก TikTok Shop, 30 ผู้ติดตาม — **ห้ามเสนอเปิดบัญชีใหม่อีก** user ท้วงแล้ว 28 ก.ย.)
- **ข้อจำกัดที่ต้องรู้**: แอปที่ยังไม่ผ่าน audit โพสต์ได้แค่ `SELF_ONLY` และ **บัญชีต้องเป็น private ตอนโพสต์** (เปิดเป็น public ทีหลังแล้วค่อยเปลี่ยนคลิปทีละอันเป็น Everyone) · ≤ 5 user/24 ชม. · ผ่าน audit แล้วโพสต์ `PUBLIC_TO_EVERYONE` ได้ · **เพดาน ~15 โพสต์/บัญชี/24 ชม.** นับรวมที่โพสต์มือ · 6 คำขอ/นาที/user · ตั้งใจใช้แค่ **1 คลิป/รอบ (≤7/วัน)** กันโดนจำกัดแบบ IG
- **เตรียมฝั่งเราแล้ว 28 ก.ย. 69**: หน้า `https://paiyaadeals.com/terms` + `/privacy` (gen.py, ลิงก์ใน footer + sitemap · TikTok บังคับมี ToS/Privacy URL) · **redirect URI = `https://paiyaadeals.com/tt/callback`** → nginx proxy ไป n8n `qHcCduq7ec3an1zk` (`/webhook/tt-oauth-cb-k4w8`, หน้าโชว์ code+state ให้ copy) ทดสอบผ่านแล้ว · ไอคอน `/root/deal-video/tiktok/app-icon-1024.png` (ffmpeg drawtext "ป" บน #C63F1E) · ยืนยันโดเมน `paiyaadeals.com` ทำได้ 2 ทาง: DNS TXT ใน hPanel หรือไฟล์ที่ root ของเว็บ (วางใน `/root/deals-site/html/` — gen.py ไม่ลบไฟล์แปลกหน้า)
  ⛔ บทเรียนซ้ำ: `/root/deals-proxy/nginx.conf` เป็น bind-mount ไฟล์เดี่ยว — patch ด้วย tmp+rename แล้ว container ไม่เห็น (ต้อง `deploy.sh` recreate) → **แก้ไฟล์นี้ต้องเขียนทับในที่เท่านั้น** (`open(p,'w')` / editor) แล้ว `nginx -s reload` · และ `proxy_pass` ที่มีตัวแปร (`$args`) ต้องมี `resolver` ไม่งั้น 502 "no resolver defined" — ใช้ URI ตายตัว nginx ส่ง query string ต่อให้เอง
- **ขั้นตอนฝั่ง user** (ส่งให้แล้ว 28 ก.ย.): สร้างแอปที่ developers.tiktok.com → Manage apps → Connect an app · กรอก name "Paiyaa Deals Poster", category, description, icon, platform Web = `https://paiyaadeals.com`, ToS/Privacy URL ข้างบน · Add products: **Login Kit** (redirect URI ข้างบน) + **Content Posting API** (เปิด Direct Post) · scopes `user.info.basic` `video.publish` `video.upload` · URL properties: verify domain · Save → ได้ **Client key + Client secret** → วางหน้า Notion Config หัวข้อ "TikTok Developers" (ข้อความ ไม่ใช่รูป)
- **ขั้นตอนฝั่งเรา (ยังไม่ทำ)**: ใส่ key/secret ใน `/root/deal-video/service/.env` → สร้าง link authorize `https://www.tiktok.com/v2/auth/authorize/?client_key=…&scope=user.info.basic,video.publish,video.upload&response_type=code&redirect_uri=https://paiyaadeals.com/tt/callback&state=…` → user กดยอมรับด้วย @sup.tw (บัญชีต้อง private ตอนนั้น) → แลก token `POST https://open.tiktokapis.com/v2/oauth/token/` (access 24 ชม. / refresh 365 วัน) → เก็บ refresh token ใน .env หรือ Notion · deal-video เพิ่ม option `tiktok:{…}` ใน `/render`: `POST /v2/post/publish/creator_info/query/` → `POST /v2/post/publish/video/init/` (`FILE_UPLOAD`, chunk เดียวถ้า < 64MB) → `PUT upload_url` (Content-Range) → poll `POST /v2/post/publish/status/fetch/` · `privacy_level` = `SELF_ONLY` จนกว่า audit ผ่าน · `IG Reel` โหมด TikTok เปลี่ยนจาก `telegram:` เป็น `tiktok:` เฉพาะดีลแรกของรอบ ที่เหลือยังส่ง Telegram
- ✅ **Sandbox ผ่านแล้ว 28 ก.ย. 69 14:40 UTC**: user สร้าง Sandbox `paiyaa-test` (key/secret อยู่ Notion Config หัวข้อ "Sandbox" · `.env` = `TIKTOK_SB_*`; แอปหลักหัวข้อ "TikTok Developers" = `TIKTOK_*`) · ด่านที่เจอตามลำดับ: `non_sandbox_target` (ต้องเพิ่ม Target user `sup.tw` + กดรับคำเชิญในแอป) → `redirect_uri` (Sandbox ต้องใส่ Redirect URI ของตัวเอง) → `scope` (Sandbox ต้อง Add product Content Posting API ถึงจะมี `video.publish/upload` ให้ติ๊ก) → authorize ผ่าน → `tt_oauth.py exchange <code> --sandbox` ได้ token (scope ครบ 3, access 24 ชม., refresh 365 วัน) → `whoami` = "Paiyaa deal" → `tt_post.py <mp4> "<title>" --sandbox` : ครั้งแรก 403 `unaudited_client_can_only_post_to_private_accounts` (บัญชี public) → user ตั้ง private → **init 200 → PUT 1.0MB 2.5 วิ → PUBLISH_COMPLETE** (คลิป sample20 แบบ SELF_ONLY) · creator_info ตอน private: privacy_options = FOLLOWER_OF_CREATOR/MUTUAL_FOLLOW_FRIENDS/SELF_ONLY (ไม่มี PUBLIC), max 3600 วิ
  สคริปต์: `/root/deal-video/tiktok/tt_oauth.py` (exchange/refresh/whoami) + `tt_post.py` (creator_info → video/init FILE_UPLOAD chunk เดียว → PUT Content-Range → poll status/fetch) — repo `vps/deal-video/tiktok/` · ทั้งคู่ไม่พิมพ์ token · `--creator-only` ดูสิทธิ์/ตัวเลือก privacy โดยไม่โพสต์ · Sandbox เดโมเบื้องต้น (52 วิ) ที่อัปโหลดไว้ในช่อง App review = `/root/deal-video/tiktok/demo/paiyaa-tiktok-demo-prelim.mp4` (screenshot ผ่าน `zenika/alpine-chrome` บน network n8n_default + `--host-resolver-rules` ชี้ paiyaadeals.com ไป deals-proxy เพราะ container ต่อ IP สาธารณะตัวเองไม่ได้ · dir ต้อง chmod 777 ให้ user chrome เขียน)
- ✅ **ต่อระบบจริงแล้ว 28 ก.ย. 69 14:45 UTC** (deploy deal-video 14:40 gate running=0 · backup `server.py.bak.20260928b` · sample.sh ผ่าน):
  · `server.py`: `/render` รับ `tiktok:{mode:'sandbox'|'prod', privacy, title}` ได้พร้อม `telegram:` (เรนเดอร์ครั้งเดียว ส่งทั้งคู่) → `tt_post()` = creator_info → video/init FILE_UPLOAD → PUT → poll ≤60 วิ · ตอบ `tiktok:{ok,status,publish_id,error,upload_s,creator,privacy_options}` · HTTP 502 ถ้าอย่างใดอย่างหนึ่งล้ม · log `[timing] tiktok=… ok= status= err=` · **token อยู่ `/root/deal-video/tiktok/tokens.json`** (mount เป็น `/tiktok` ใน deploy.sh · service refresh เองเมื่อเหลือ < 30 นาที · `tt_oauth.py` เขียนไฟล์เดียวกัน) · client key/secret ใน `.env` (`TIKTOK_SB_*` sandbox / `TIKTOK_*` prod) · ทดสอบจริงจาก container: render 10.5 วิ + tiktok 12.2 วิ → PUBLISH_COMPLETE (SELF_ONLY)
  · n8n `IG Reel`: `TIKTOK_DIRECT = {enabled:true, mode:'sandbox', privacy:'SELF_ONLY', perRound:1}` → **ดีลแรกของรอบ (g.n ≤ perRound) ส่ง `tiktok:` ไปด้วย** ดีลอื่นส่ง Telegram อย่างเดียว · httpRequest ใส่ `ignoreHttpStatusErrors:true` (502 บางส่วนไม่ throw) · output เพิ่ม `tiktokPost:{ok,status,error,publish_id,mode,privacy}` · **ผ่าน audit แล้วเปลี่ยนเป็น `mode:'prod', privacy:'PUBLIC_TO_EVERYONE'`** (ต้อง authorize แอปหลักก่อน: `tt_oauth.py exchange <code>` ไม่ใส่ --sandbox · ลิงก์ authorize สร้างแบบเดียวกับ sandbox แต่ใช้ `TIKTOK_CLIENT_KEY`) แล้วค่อยพิจารณา perRound 1→2 (เพดาน TikTok ~15/วัน) · ตอนนี้บัญชี @sup.tw ต้อง **private** ไว้ ไม่งั้นดีลแรกทุกรอบได้ `init: unaudited_client_can_only_post_to_private_accounts` (Telegram ยังได้ปกติ)
  · **ผลรอบแรก 00:00 น. 29 ก.ย. 69 (exec 39865, 6 ดีล, 14 นาที)**: ทุกอย่างผ่าน (Threads 2/2 · Mark Posted 6 · Telegram คลิป 6/6 · render 8–14 วิ + telegram 2–3 วิ + tiktok 8–11 วิ ทุกดีล PUBLISH_COMPLETE) **แต่ perRound ไม่ทำงาน: ลง TikTok 6/6** (ควร 1) — สาเหตุ: `globalThis.__reel` **ไม่คงค่าข้าม task** (ตั้งแต่โครง #19 แต่ละ run ของ Loop Reels เป็น task ใหม่ของ task runner) → `g.n` = 1 ทุก run · ผลพลอยได้: gap 3 วิและงบรวม 480 วิ ก็ไม่เคยทำงานเช่นกัน (t0 รีเซ็ตทุก run) แต่ไม่มีผลเสีย
    **แก้แล้ว 17:30 UTC**: `g.n = $runIndex + 1` (`$runIndex` ของ Code node นับ 0,1,2,… ต่อ execution ใน loop) · `if (g.n > 1) await sleep(3000)` · syntax check ต้องห่อ `async function(){…}` เพราะโค้ดมี await · **บทเรียน: ใน Loop Reels ห้ามพึ่ง `globalThis` นับข้ามดีล ใช้ `$runIndex`** · รอบ 06:00 น. 29 ก.ย. ต้องได้ tiktokPost เฉพาะ run 0 · โควตา TikTok ~15/วัน: วันที่ 28 ใช้ไป 6 (รอบ 00:00) + ทดสอบ 3 → รอบ 06:00 ยังมีที่
    ✅ **ยืนยันรอบ 06:00 น. 29 ก.ย. 69 (exec 39996, 6 ดีล, 15 นาที, รอบพากย์ Gemini)**: IG Reel run 0 `tiktokPost.ok=true PUBLISH_COMPLETE` (sandbox/SELF_ONLY) · run 1–5 `tiktokPost` undefined · `tiktokClip=true` ทุก run ไม่มี reelError · log deal-video `[timing] tiktok` 1 บรรทัด (11.1 วิ) render 26–31 วิ + telegram 2–3 วิ ครบ 6 · Threads 2/2 · Mark Posted 6 — **perRound=1 ทำงานแล้ว** · ระบบ TikTok direct ถือว่านิ่ง ไม่ต้องตรวจรายรอบต่อ (ดูเฉพาะเมื่อ TG alert ผิดปกติ หรือหลัง audit ผ่านตอนสลับ prod)
- **audit**: หลังทดสอบ SELF_ONLY ผ่าน อัดวิดีโอเดโม (flow authorize → คลิปโผล่ในบัญชี) 1–5 ไฟล์ ≤ 50MB + คำอธิบายการใช้งาน → Submit for review (Draft → In Review → Live) รอหลายวันถึง ~2 สัปดาห์ · ผ่านแล้วเปลี่ยน `privacy_level` เป็น `PUBLIC_TO_EVERYONE`
  ✅ **ยื่น audit แล้ว 28 ก.ย. 69 ~22:00 น. ไทย — สถานะ In review** (app id `7690519133092300808` · หน้า `developers.tiktok.com/app/7690519133092300808/pending#app-review` มีปุ่ม Recall ถอนได้) · Demo video 2 ไฟล์: `paiyaa-tiktok-demo-prelim.mp4` (หลังบ้าน 52 วิ) + `IMG_7592.MP4` (user อัดหน้าจอ iPhone: เว็บ → กดลิงก์ authorize Sandbox → callback → แท็บ 🔒 ในโปรไฟล์) · คำอธิบายภาษาอังกฤษ (ใช้เฉพาะเจ้าของบัญชี @sup.tw, Direct Post 1 คลิป/รอบ, #ad, SELF_ONLY จนกว่าผ่าน)
  · การอัดเดโมทำให้ authorize Sandbox ซ้ำ → แลก code ใหม่ด้วย `tt_oauth.py exchange … --sandbox` แล้ว (tokens.json อัปเดต service ใช้ได้) · **ลิงก์ authorize ใช้ซ้ำได้** (state/PKCE ตายตัวใน .env) code ใช้ครั้งเดียว
  · บทเรียน: คลิป SELF_ONLY **ไม่ขึ้นแถบวิดีโอหลักของโปรไฟล์** อยู่ในแท็บ 🔒 (Private) — user หาไม่เจอตอนอัด · บอท Telegram รับไฟล์ได้ ≤ 20MB ส่งคลิปอัดหน้าจอผ่านบอทไม่ได้ ให้ user อัปโหลดเข้า App review เอง (≤ 5 ไฟล์ × 50MB)
  · **ถ้าถูกตีกลับ** จะมีอีเมล → แก้ตามที่แจ้งแล้ว Submit ใหม่ · **ผ่านแล้ว (Live)**: สร้างลิงก์ authorize แอปหลัก (`TIKTOK_CLIENT_KEY` + `TIKTOK_OAUTH_STATE`/`TIKTOK_CODE_VERIFIER`) ให้ user กด → `tt_oauth.py exchange <code>` (ไม่ใส่ --sandbox) → user เปิดบัญชี public ได้ → `IG Reel` `TIKTOK_DIRECT` เป็น `mode:'prod', privacy:'PUBLIC_TO_EVERYONE'` (ดู privacy_options จาก `tt_post.py --creator-only` ก่อน) · ไอคอนแอปที่ TikTok แสดงดูคล้าย "U" (ป ที่ font ไม่มี) ค่อยเปลี่ยนหลังผ่าน review อย่าแก้ระหว่างรอ

## TikTok Shop — ⛔ API ไปต่อไม่ได้ ใช้ Plan B แทน (สรุป 7 ก.ย. 2569)
**คำตอบ ticket `2026083004120200004` (TikTok ตอบ 1 ก.ย. 69) — ปิดประตู API สำหรับบุคคลธรรมดา:**
1. ผ่าน certification หมวด Creator collaborations **โดยไม่มีนิติบุคคลไม่ได้** ("you need to provide company certification/business license")
2. ทะเบียนพาณิชย์บุคคลธรรมดา — ยื่นให้ผู้อนุมัติพิจารณาได้ แต่ **กฎ "จดเกิน 1 ปี" มีผลด้วย**
3. **ไม่มี allowlist/test account ให้ลัด** — ต้องผ่าน onboarding review + publish แอปก่อนเท่านั้น
4. "Invalid app key" = แอปยังเป็น draft ตามที่วินิจฉัยไว้เป๊ะ

→ **ตัดสินใจ 7 ก.ย. 69: เดินสาย Plan B (ไม่ใช้ API)** · `lib/tiktok/*` + workflow `qHcCduq7ec3an1zk` เก็บไว้เฉย ๆ รอวันมีนิติบุคคล/ทะเบียนครบ 1 ปี

### ⛔ Plan B ก็ยังยิงไม่ได้ — **บัญชี TikTok ของ user เป็นฝั่ง seller ไม่มี affiliate** (สำรวจในแอป 8 ก.ย. 69)
ไล่ดูในแอป TikTok ครบทุกเมนูแล้ว **ไม่มีทางเข้าตลาดสินค้า affiliate เลย** → ไม่มีลิงก์ affiliate ให้เอามาป้อนระบบ:
- TikTok Shop Creator Center → toolkit หัวข้อ **"Find and manage products" มีปุ่มเดียวคือ `Manage products`** (ไม่มี marketplace/ตลาดสินค้าให้เลือกสินค้าคนอื่น)
- หน้า Showcase เขียนว่า **"Showcase products from your shop"** = โชว์สินค้า**ร้านตัวเอง** ไม่ใช่ affiliate ของคนอื่น · กด Add products → "No products in this category yet" (ร้านไม่มีสินค้า)
- แท็บ **Growth** มีแต่แคมเปญไลฟ์ ไม่มีปุ่มสมัคร affiliate
- เข้ากันได้กับเบาะแสตอนสมัคร Partner Center: อีเมล gmail ถูกล็อกด้วย **"not available for TikTok Shop sellers"** → บัญชีนี้ระบบมองเป็นผู้ขาย
- เกณฑ์ follower ที่เคยจดว่า 5,000 **ผิด** — 5,000 เป็นของ US ส่วนไทย/SEA ใช้ **1,000** (ต่ำกว่า 5,000 จะเข้า Affiliate Creator Pilot 30 วัน มีข้อจำกัด) · แต่เกณฑ์ไม่ใช่ประเด็นเพราะติดที่ประเภทบัญชี
- **สรุป: TikTok พับไปก่อนทั้ง 2 ทาง** (API ติด certification นิติบุคคล · Plan B ติดบัญชีไม่มี affiliate) — ถ้าจะรื้อต่อ ประเด็นที่ต้องเคลียร์คือ "บัญชีที่ผูกร้าน TikTok Shop สมัคร affiliate creator ได้ไหม หรือต้องใช้บัญชีที่ไม่ผูกร้าน"

### Plan B (ฝั่งโค้ด) — ทำเสร็จแล้ว 7 ก.ย. 69 (intake รู้จักลิงก์ TikTok, พร้อมรับเมื่อมีลิงก์)
user กด gen ลิงก์เองจากแอป TikTok (Affiliate center) → วางเข้า intake เดิม → ไหลเข้าสาย A/B ปกติ
- แก้ **intake ทั้ง 3 ทาง** (LINE `731A7ASm8bI0F79B` / TG `JUE23JTCBbCsW1lS` / Form `Kq3cRuTbwF9cMkA1`) — 16 จุด:
  - `Extract`/`Prep`: ตรวจ domain → `source` = tiktok (`tiktok.com`) / lazada (`lazada.` `lzd.co`) / shopee (`shopee.` `shp.ee`)
  - `Build Payload`/`Build Notion Payload`/`Build Parsed Payload`: เขียน property **`แหล่ง`** + placeholder ชื่อเปลี่ยนจาก "ดีลจาก Shopee" เป็น "ดีลจาก {source}"
  - `Claude Parse` prompt: "Shopee deal info" → "e-commerce deal info (Shopee, Lazada or TikTok Shop)"
  - `Build Reply` (LINE/TG): ถ้าเป็น tiktok เปลี่ยนข้อความทริคเป็นบอกให้พิมพ์ชื่อ+ราคามาเอง
  - เทสต์จริงผ่าน webhook TG แล้ว: ได้แถว `แหล่ง=tiktok` สถานะ "รอตรวจ" ถูกต้อง (แถวทดสอบชื่อ "[แถวทดสอบ TikTok — ลบทิ้งได้เลย]")
- **ลิงก์ TikTok ลง `ลิงก์Affiliate` (ไม่ใช่ `ลิงก์ตะกร้า`)** — เพราะสายโพสต์ทุกตัวอ่านช่องนี้ (`Split Approved` ถึงกับ `.filter(link)`) ถ้าแยกช่องต้องแก้ 6+ จุดโดยไม่ได้อะไรเพิ่ม · `ลิงก์ตะกร้า` สงวนไว้ให้ยุค API (ลิงก์ที่ generate มาปักตะกร้า)
- ⚠️ **หน้าสินค้า TikTok Shop ติด bot protection** — `shop.tiktok.com/view/product/…` ตอบหน้า **"Security Check"** ไม่มี og tag เลย (ต่างจาก `www.tiktok.com` ที่มี og ปกติ)
  → ดึงชื่อ/ราคา/รูปอัตโนมัติ**ไม่ได้** ผู้ใช้ต้องพิมพ์ชื่อ+ราคามากับลิงก์ · ไม่มีรูป = **IG ข้ามดีลนั้น** (IG โพสต์ข้อความล้วนไม่ได้) ส่วน TG/FB fallback เป็นข้อความอยู่แล้ว
  (`Fetch OG` ตั้ง `onError: continueRegularOutput` อยู่แล้วทั้ง 3 workflow → ลิงก์ที่ดึงไม่ได้ไม่ทำ intake ล้ม)

## TikTok Shop — provider ใหม่ (ประวัติการลุย API 29–30 ส.ค. 2569)
แผนรวม: sync ดีลจาก Affiliate Marketplace → แถว Notion สถานะ "ใหม่" → ไหลเข้าสาย A/B เดิม + gen ลิงก์ให้ user ปักตะกร้า
ตัดสินใจแล้ว (29 ส.ค.): **เพิ่ม property `ลิงก์ตะกร้า` แยกจาก `ลิงก์Affiliate`** และ **ดีล TikTok ไหลเข้าสายโพสต์ TG/FB/IG/Threads ด้วย**
- **Phase 0 (กำลังทำ)**: user สมัคร Partner Center + สร้างแอป + authorize — callback ใช้ workflow `qHcCduq7ec3an1zk` (URL: `https://n8n.srv1277799.hstgr.cloud/webhook/tt-oauth-cb-k4w8`)
- **ความคืบหน้า 30 ส.ค. 69**: สมัคร Partner Center ด้วย**อีเมลใหม่** (อีเมลเดิม gmail ผูกร้าน TikTok Shop → App developer ถูกล็อก "not available for TikTok Shop sellers") · Partner name **Paiyaa Deals**, region Thailand
  - แอปที่ใช้จริง: **Paiyaa Creator Poster** — Service ID `7679008369329063701`, App key `6l3qenknhf6n3`, Custom app, category **App developer → Customer Engagement → Creator collaborations** (⚠️ category เดียวในไทยที่มี scope `creator.*` — Marketing/Analytics ฯลฯ มีแต่ `seller.*`), target TH/Local, Redirect URL = webhook ข้างบน · **app secret อยู่หน้า Notion Config** (หัวข้อ TikTok)
  - แอปทิ้งร้าง (ใบแรก ผิด category): "Paiyaa Deal Poster" Service ID `7679561908684588820` — ไม่ใช้ อย่าสับสน
  - scope เปิดแล้ว 5 ตัว (สถานะ Awaiting review): `creator.affiliate_collaboration.read`, `creator.affiliate.share_link.read`, `creator.showcase.write`, `creator.showcase.read`, `seller.creator_marketplace.read`
  - **บล็อกอยู่ (30 ส.ค. 69) — โซ่ยืนยันครบแล้ว**: creator authorize ขึ้น "Invalid app key" ← แอปสถานะ **Draft** ต้อง **Publish** ก่อน (App & Service list มีสถานะ Draft/On/Off) ← Publish dialog ล็อกด้วย **"Partner registration review — awaiting submission"** ← submit ต้องผ่าน Certification (เอกสารกิจการจดเกิน 1 ปี) ← **user ไม่มีทะเบียนพาณิชย์**
    (หลักฐานว่า credential ใช้ได้: token endpoint ตอบ `36004004 invalid auth code` กับ auth_code ปลอม = รู้จักคู่ key/secret)
  - **ยื่น ticket แล้ว 30 ส.ค. 69** — **Ticket ID `2026083004120200004`** "Invalid app key blocks custom app publishing" (หมวด Migration/Developer Registration, ยื่น 11:51 สถานะ Unassigned) — ถาม: individual dev ผ่าน cert ได้ไหม / ทะเบียนพาณิชย์บุคคลธรรมดาใช้ได้ไหม+ติดกฎ 1 ปีไหม / ขอเข้า creator-auth allowlist หรือ Creator testing account / สาเหตุ Invalid app key · เช็คสถานะ: `https://partner.tiktokshop.com/ticket/center`
  - ข้อมูลจากบอต Partner Assistant: scope ทั้ง 4 สถานะภายในเป็น **Achieved** แล้ว · Affiliate API "inactive by default ต้องได้รับ approval + ส่ง app_key ให้ partner manager ขึ้นทะเบียนรับ creator authorization" · ISV ต้องเป็นนิติบุคคล มีกฎ reject ถ้า business license อายุ < 1 ปี · Creator testing account จำกัด beta member ขอผ่าน App Store Manager
  - **Plan B ถ้าบุคคลธรรมดาไปต่อไม่ได้**: ไม่ใช้ API เลย — user กด gen ลิงก์จากแอป TikTok (Affiliate center ในแอป) แล้ววางเข้า intake เดิม (LINE/TG/ฟอร์ม) → เพิ่มแค่ให้ intake รู้จักลิงก์ TikTok + ติด `แหล่ง=tiktok` · lib ที่เขียนไว้เก็บรอวันมีทาง · แผนสำรองอีกทาง: จดทะเบียนพาณิชย์บุคคลธรรมดา (~50 บาท) แล้วรอครบ 1 ปี
- **Phase 3 (Notion) — เพิ่ม property แล้ว 30 ส.ค. 69** ผ่าน Notion MCP (เลี่ยง curl+ไทยบน Windows ได้เลย): `แหล่ง` (select: shopee/lazada/tiktok) · `TTProductId` (rich_text) · `คอม%` (number) · `ลิงก์ตะกร้า` (url) — additive ล้วน workflow เดิมไม่กระทบ · **backfill `แหล่ง` ให้แถวเก่ายังไม่ทำ** (รอมีหน้าจอ/logic ที่ใช้ค่านี้จริงใน Phase 5 ค่อย backfill จาก domain ของลิงก์)
- **Phase 1 เสร็จแล้ว (30 ส.ค. 69)** — `lib/tiktok/sign.js` + `request.js` + unit tests 15 ตัว (`node --test lib/tiktok/sign.test.js lib/tiktok/request.test.js`)
  - **sign.js ตรวจกับ production แล้ว**: ลายเซ็นเรา → `36009005 access_token invalid` (ผ่านด่าน sign) · ลายเซ็นมั่ว → `106001 sign invalid`
  - อัลกอริทึม: `hex(HMAC_SHA256(secret, secret + path + {key}{value} เรียง ASCII (ตัด sign/access_token) + body ถ้าไม่ multipart + secret))` · token ส่งทาง header `x-tts-access-token` ไม่ร่วมคำนวณ sign · body ที่ sign ต้องเป็น string เดียวกับที่ส่งจริง byte-ต่อ-byte
  - `ttRequest`: host `https://open-api.tiktokglobalshop.com`, endpoint แบบ `{version}` placeholder, retry 429/5xx exponential+jitter, โยน `TokenExpiredError` เมื่อ code 105001/105002/36009005 (ไม่ retry — ให้คนเรียกไป refresh), `httpFn`/`now`/`sleep` inject ได้เพื่อเทสต์/ใช้กับ `this.helpers.httpRequest` ใน n8n
- ข้อเท็จจริงจาก docs (เช็ค 29 ส.ค. 69):
  - Creator authorization: ลิงก์ `https://shop.tiktok.com/alliance/creator/auth?app_key={key}&state={random}` (**state บังคับ** สำหรับ creator) → callback `?code=&state=` → แลก token: `GET https://auth.tiktok-shops.com/api/v2/token/get` (`app_key,app_secret,auth_code,grant_type=authorized_code`) → refresh: `GET https://auth.tiktok-shops.com/api/v2/token/refresh` (`grant_type=refresh_token`)
  - ตรวจหลังแลก token เสมอ: `code==0`, `user_type==1` (=creator), `granted_scopes` ครบ (creator ติ๊กเลือกบาง scope ได้ — สำเร็จ ≠ ได้ครบ) · error 105002=token หมดอายุ, 105005=ขาด scope, 101000=ใช้ token ผิดฝั่ง (seller/creator คนละใบ ห้ามสลับ)
  - access_token อายุ ~24 ชม., refresh_token ~1 ปี → Token Keeper ควร refresh ทุก ~12 ชม.
  - endpoint หลัก (ทุกตัว query `app_key,sign,timestamp` + header `x-tts-access-token`):
    - ค้นดีล: `POST /affiliate_creator/202405/open_collaborations/products/search` scope `creator.affiliate_collaboration.read` — page_size ≤ 20, filter `commission_rate_range`/`sales_price_range`/`category`/`title_keywords`, sort `commission_rate` ได้, แบ่งหน้าด้วย `page_token`
    - gen ลิงก์: `POST /affiliate_creator/202505/affiliate_sharing_links/general_publishers/generate_batch` scope `creator.affiliate.share_link.read` (⚠️ คนละ version: 202505)
    - **ปักตะกร้า (showcase) ผ่าน API ได้จริง**: `POST /affiliate_creator/202405/showcases/products/add` scope `creator.showcase.write` (add_type PRODUCT_ID/PRODUCT_LINK ≤ 20 ตัว/ครั้ง) — ที่ทำแทนไม่ได้คือปักลงคลิป/ไลฟ์รายอัน
  - เงื่อนไขฝั่ง creator: ต้องเป็น TikTok Shop Creator ที่มี Showcase แล้ว (SEA ต้อง 5K+ followers, 18+) · Affiliate API ใช้ไม่ได้ใน UK/EU (ไทยใช้ได้)
- แผนเต็ม (ไฟล์/phase/interface) อยู่ใน session log 29 ส.ค. — สรุปสั้น: `lib/tiktok/{sign,request}.js` + unit test (`node --test`), workflow `TikTok Token Keeper` + `TikTok Deal Sync`, Notion เพิ่ม `แหล่ง`(select) `TTProductId`(rich_text) `คอม%`(number) `ลิงก์ตะกร้า`(url)

## สถานะแพลตฟอร์ม (22 ส.ค. 2569)
- **Telegram** `@paiyaa_deals` ✅ — sendPhoto ต้องโหลดรูปเป็น binary แล้ว upload multipart (ส่ง URL ให้ Telegram ดึงเองไม่ได้ Shopee/Lazada CDN บล็อก); Lazada บางรูป `IMAGE_PROCESS_FAILED` → fallback sendMessage ทำงานอยู่
- **Facebook** ✅ (22 ส.ค. 2569) — เพจ **ป้ายยาดีลเด็ด** page_id `1330886503433772` · URL `facebook.com/paiyaa.deals` (ตั้ง username 25 ส.ค. 69), แอป "Paiyaa Pages" (2350093015523231)
  - **ตั้ง/แก้ username ผ่าน API ไม่ได้** — `POST /{page_id}?username=` คืน `(#3) Application does not have the capability` ไม่มี permission ไหนปลดล็อกได้ ต้องทำใน UI: `facebook.com/settings/?tab=profile` → แถว Username → Edit (FB จะขอ **รหัสผ่านยืนยัน** ก่อนบันทึก — ขั้นนี้ต้อง user พิมพ์เอง)
  - username ห้ามมี underscore (ต่างจากช่องอื่นที่ใช้ `paiyaa_deals`) ใช้ได้แค่ตัวอักษร ตัวเลข จุด ยาว ≥ 5
  - สาย FB แตกขนานจาก `Fetch Photo Bin` (คู่กับ Telegram): `Post to Facebook` (`POST /{page_id}/photos` multipart binary) → `FB Verify` → `FB Need Text?` → `FB Send Feed` (`POST /{page_id}/feed` message+link) — batching 60 วิทั้งคู่
  - **page token เป็นแบบ NEVER expires** (derive จาก long-lived user token) ฝังใน node — **ไม่ต้องมี token keeper**
  - วิธีได้ token (เผื่อทำใหม่): Access Token Tool ลิงก์ "need to grant permissions" ให้แค่ `public_profile` → ต้องไป Graph API Explorer → Add a Permission (`pages_show_list`+`pages_manage_posts`+`pages_read_engagement`) → Generate ใหม่ → perms ผูกกับคู่ user+app ดังนั้น token เดิมได้ scope เพิ่มเองด้วย → `GET /me/accounts` ได้ page token
  - (บัญชีมี 3 เพจ: ป้ายยาดีลเด็ด / EVE / G.S.B.Uniform — อีกสองอันไม่เกี่ยว; `Paiyaa` ไม่ใช่เพจ เป็น business portfolio ที่เลิกใช้แล้ว)
- **Instagram** `@paiyaa_deals` ✅ (24 ส.ค. 2569) — IG User id `17841440317177953` บัญชี **Business ผูกกับเพจ ป้ายยาดีลเด็ด**
  - เพจ FB ผูก IG ได้**บัญชีเดียว** → พอผูกตัวใหม่ `supachai_tw` (ส่วนตัว) หลุดออกเอง ไม่ต้องไปไล่ปลดที่ Business users (หน้านั้นติด enterprise permission กดไม่ได้อยู่แล้ว)
  - สาย IG แตกจาก `FB Photo URL`: `Build IG Caption` → `IG Has Image?` → `IG Create Media` (`POST /{ig}/media`) → `IG Publish` (`POST /{ig}/media_publish`) — 2-step เหมือน Threads, batching 60 วิ, ใช้รูปจาก FB CDN
  - **IG โพสต์ข้อความล้วนไม่ได้ ต้องมีรูปเสมอ** → ไม่มีรูป = ข้ามช่องนี้ (ไม่มี fallback แบบ TG/FB)
  - ⚠️ **ที่จริง IG ไม่เคยโพสต์ได้เลยตั้งแต่ต่อสายมา — โพสต์แรกจริงคือ 25 ส.ค. 69** (`media_count` เป็น 0 มาตลอด)
    node `Build IG Caption` โดน**บั๊ก String.raw ทั้ง 2 แบบพร้อมกัน**: บรรทัดที่ควรเป็น `split('\n')` / `join('\n')` กลายเป็น newline จริงคาอยู่ในสตริง single-quote
    ทำให้ `SyntaxError: Invalid or unexpected token` ทุกรอบ + `replace(/s/g,'')` ที่ backslash หายจาก `/\s/g`
    → **status ของ execution ขึ้น `error` แต่ TG/FB/Threads ที่รันไปก่อนแล้วยังสำเร็จ** จึงดูเหมือนปกติ ไม่มีใครเอะใจ
    บทเรียน: node code ที่แก้ผ่าน script ต้องตรวจ `new Function()` **แล้ว GET กลับมาตรวจซ้ำหลัง PUT** เสมอ
  - แคปชัน IG ต่างจากช่องอื่น (26 ส.ค. 69 ปรับอีกรอบ): **ตัดบรรทัดที่มี http ออก** (IG ไม่ทำลิงก์ในแคปชันให้กดได้ — ข้อจำกัดแพลตฟอร์ม แก้ฝั่งเราไม่ได้)
    แทนด้วย "🔗 กดลิงก์ในไบโอเพื่อไปที่ร้าน" · **ตัดหมายเหตุ `(ลิงก์ affiliate)`** ทิ้ง (ไม่มีลิงก์แล้วเขียนไว้ก็งง)
    · **ดึงแฮชแท็กจากเนื้อความไปรวมท้ายโพสต์ที่เดียวแล้ว dedupe** (เดิม `#ป้ายยา #ดีลเด็ด` โผล่ 2 ที่)
  - ⚠️ **ไบโอ IG: URL อยู่ในช่อง `biography` (ข้อความเฉย ๆ กดไม่ได้) ส่วนช่อง `website` ว่าง** — ต้องไปใส่ในแอป IG
    ที่ Edit profile → Links เอง (Graph API ไม่มี endpoint แก้โปรไฟล์) ไม่งั้น "ลิงก์ในไบโอ" ไม่มีอยู่จริง
  - perms ฝั่ง IG ติด**กับดักเดียวกับ Pages**: ต้องเพิ่ม `instagram_basic` + `instagram_content_publish` ที่ **App → Use cases** ก่อน Graph API Explorer ถึงจะเห็นให้ติ๊ก
  - **token ต้องเอาจาก Access Token Tool เท่านั้น** (ออก long-lived 60 วัน → derive page token ได้แบบ never-expire) — ตัวจาก **Graph API Explorer เป็น short-lived 1-2 ชม.** page token ที่ derive ต่อก็อายุสั้นตาม; และ "App Token" ที่โชว์ในหน้านั้น **ไม่ใช่ app secret** เอาไปแลก `fb_exchange_token` ไม่ได้ (`Error validating client secret`)
- **Threads** `@paiyaa_deals` (uid `28104225519212652`) ✅ **ย้ายจากบัญชีส่วนตัวแล้ว 24 ส.ค. 2569** — โพสต์เก่า 24 อัน + ผู้ติดตามยังค้างที่ `@supachai_tw` (uid เดิม 28066415776320239) ย้ายข้ามบัญชีไม่ได้
  - **รูปต้องส่งเป็น image_url ให้ Meta ไปดึงเอง อัปโหลด binary ไม่ได้** → Shopee/Lazada CDN บล็อก fetcher ของ Meta (`error_subcode 2207052 Media download has failed`) จึงต้อง**ยืมรูปที่อัปขึ้น FB แล้ว** (scontent CDN) ผ่าน node `FB Photo URL`
  - `Threads Publish` เคยเจอ `code 24 / subcode 4279009 "The requested resource does not exist"`
    = publish เร็วเกินไปหลัง create (container ยังไม่พร้อม) ไม่ใช่ token พัง — 25 ส.ค. รอบ 02:00Z พลาดไป 1 ดีล
    **แก้แล้ว 25 ส.ค. 69:** แทรก node **`Threads Settle`** (`n8n-nodes-base.wait`, 30 วิ) คั่น `Threads Create` → `Threads Publish`
    รอครั้งเดียวต่อรอบ ไม่ใช่ต่อดีล · ไม่ฝัง token ในโหนดนี้ (จะได้ไม่ไปกวน Token Keeper ที่หา token ด้วย regex)
    ถ้าทำเองนอก workflow ให้ poll `GET /v1.0/{creation_id}?fields=status` จน `FINISHED` แทน (แม่นกว่ารอเวลาตายตัว)
  - เคยโดน "API access blocked" ระดับแอป 21–23 ส.ค. หลังยิง 7 โพสต์ใน 1 นาที → แก้ด้วย throttle 3 ดีล/รอบ + 60 วิ/โพสต์ ปลดเองเมื่อ 23 ส.ค.
  - ขั้นตอนย้ายบัญชี (เผื่อทำอีก): เปิดโปรไฟล์ Threads ของ IG ตัวใหม่ → App roles เพิ่มเป็น **Threads Tester** → **ต้องไปกดรับคำเชิญในแอป Threads** (Settings → Website permissions → Invites) ไม่งั้นค้าง Pending → Use cases → Access the Threads API → Settings → **User Token Generator** เลือกแถวบัญชีใหม่
  - uid ฝังอยู่ **2 จุด** (`Build Threads Post`, `Threads Publish`) ต้องเปลี่ยนพร้อม token · **Token Keeper ไม่ต้องแตะ** (หา token ด้วย regex `THAA…` จาก workflow หลัก ไม่ผูกบัญชี)
- **X** ⏸ node "Post to X" `disabled:true` — X เป็น pay-per-use credits แล้ว บัญชี $0 user ยังไม่ซื้อ; node เป็น httpRequest + predefinedCredentialType `twitterOAuth1Api` (twitter node v2 ใช้ OAuth1 ไม่ได้), credential n8n `TsrgrCQlMXmi03F9`
- **บทเรียน Meta:** งานสร้างบัญชี/portfolio/appeal ต้องให้ user คลิกเอง (automation โดนแฟล็กมาแล้ว); งาน Graph API ปกติไม่โดน

## ⛔ IG จำกัดบัญชี 30 วัน (26 ก.ย. – 26 ต.ค. 2569) — "You can't share links" ฐาน prohibited commercial practices
user เห็นแจ้งเตือนในแอป 28 ก.ย. 69 · โพสต์ยังลงได้ แต่ลิงก์ (ไบโอ/สตอรี่/DM) ใช้ไม่ได้ · สาเหตุที่เข้าเกณฑ์สแปม: **ผู้ติดตาม 3 คน แต่โพสต์ 438 ชิ้น · 26–27 ก.ย. วันละ 27–31 โพสต์** ทั้งหมดเป็นโฆษณา · ทุกโพสต์ปิดด้วย "กดลิงก์ในไบโอ" · ไบโอมีแต่ URL · ดีลบางตัวลง 2 ครั้ง (Reels+ภาพ จากบั๊กเดิม)
**แก้แล้ว 28 ก.ย. 69 (รอบ #20)** — ฝั่งระบบ:
- **โหมด TikTok (28 ก.ย. 69 บ่าย, user เลือกข้อ 1)**: IG ยังพัก แต่ `IG Cap` ปล่อยทุกดีลเข้า `Loop Reels` → `IG Reel` มี `IG_PAUSED=true` + `TIKTOK_CLIPS=true` → ไม่สร้าง container IG แต่เรียก `/render` พร้อม `telegram:{url,chat_id,caption}` → **deal-video เรนเดอร์แล้วส่งคลิปเข้า Telegram (chat 8336016992) พร้อมแคปชัน** (เนื้อหา+CTA ชื่อเว็บ+#ad+เครดิตเพลง) ให้ user อัปโหลด TikTok เอง · ทดสอบแล้ว msg 1403 (23 วิ render 40 วิ) · ต่อดีล ~45–60 วิ (ไม่มี upload ไป Meta) · เปิด IG กลับ: `IG_PAUSED=false` + `IG Cap` → `slice(0,1)`
- ~~IG จำกัด 1 Reels/รอบ~~ → **พัก IG ทั้งหมดถึง 26 ต.ค. 69** (user ถาม "ก่อน 26 ต้องงดส่ง IG ไหม" → ตัดสินใจงด): node `IG Cap` มี `IG_PAUSED = true` คืนลิสต์ว่าง → Loop Reels/IG Reel/deal-video ไม่ทำงานเลย (ไม่เสียค่า Gemini ด้วย) · TG/FB/Threads(2/รอบ) ยังโพสต์ · **📅 27 ต.ค. 69 เป็นต้นไป**: เปิด Account status ในแอปว่าข้อจำกัดหายแล้ว → แก้ `IG Cap` เป็น `return $input.all().slice(0, 1);` (1 Reels/รอบ) แล้วค่อยขยับ · ยื่นทบทวนไม่ได้ (หน้า Request reviews ว่าง ปุ่มเทา = not eligible)
- **เลิกถอยไปโพสต์ภาพ**: ตัดสาย `IG Reel OK?` (false) → `IG Create Media` และ `disabled: true` ทั้ง `IG Create Media`/`IG Publish` (เก็บไว้เผื่อกลับมาใช้) — Reels ล้ม = IG ข้ามดีลนั้น
- **แคปชัน IG** (`Build IG Caption`): CTA หมุน 4 สำนวนตาม hash ชื่อ บอกชื่อเว็บเป็นข้อความ (`paiyaadeals.com`) + บรรทัด "ลิงก์พันธมิตร มีค่าคอมมิชชั่น #ad" · **บทพากย์** (`CTAS` ใน server.py 8 สำนวน) และ **CTA บนจอ** เลิกพูด/เขียน "ลิ้งค์ในไบโอ" → "ดูดีลนี้ที่ paiyaadeals.com"
- **Threads จำกัด 2 ดีล/รอบ (≤14/วัน) — ทำแล้ว 28 ก.ย. 69 (user: "ลด Threads ด้วย")**: `Build Threads Post` ใส่ `skip = $itemIndex >= 2` + `page_id` → node ใหม่ **`Threads Skip?`** (IF) → true ไป **`Threads Merge`** (merge v3 append, input 1) ตรง · false → Threads Create → Settle → Publish → Threads Merge (input 0) → `Mark Posted` (เดิมต่อจาก Threads Publish) · `Build Posted Alert` รู้จัก skip: แสดง "⏭ ข้าม (จำกัด 2 ดีล/รอบ)" และจับคู่ผล Threads Publish ตามลำดับเฉพาะดีลที่ไม่ข้าม (ไม่ใช้ idx ตรง ๆ แล้ว)
  **ผลรอบจริง 18:00 น. 28 ก.ย. 69 (exec 39716, 6 ดีล)**: Merge/Mark Posted **ผ่าน** — โพสต์แล้ว 6/6 + รูปครบ, alert 6, Merge ปล่อยของแม้ input skip ว่าง ✅ · **แต่ cap ไม่ทำงาน: ลง Threads 4 ดีล** เพราะ `Build Threads Post` รัน 2 รอบ (สาย `FB Photo URL` 4 ดีล + สาย `FB Send Feed` 2 ดีลที่รูป FB ล้ม → `FB Need Text?` แยกสาย) และ `$itemIndex` รีเซ็ตทุกรอบ → **แก้แล้ว 11:40 UTC**: skip ตัดสินจากลำดับของดีลใน `$('Split Approved')` (indexOf page_id) คงที่ทั้ง execution · บทเรียน: **ใน workflow นี้ node หลัง `FB Need Text?` รันได้ 2 รอบเสมอ อย่าใช้ `$itemIndex` นับข้ามดีล** (IG Reel ใช้ `g.n` ผ่าน globalThis อยู่แล้ว) · ยังต้องดูรอบถัดไปว่าได้ 2 พอดี
  ✅ **ยืนยันรอบ 21:00 น. 28 ก.ย. 69 (exec 39793, 6 ดีล, 15 นาที)**: Build Threads Post skip=[F,F,T,T,T,T] · Threads Create/Publish **2/2 พอดี** · Threads Merge 6 · Mark Posted 6 (id ไม่ซ้ำ, สถานะ โพสต์แล้ว ครบ) · alert ⏭ ถูกดีล 4 ตัว — cap ใช้ได้แล้ว
  **โหมด TikTok รอบแรก (รอบเดียวกัน)**: IG Cap ปล่อย 6 · Loop Reels 7 run (6+done) · IG Reel 6 run `tiktokClip=true voice=true` ทุกดีล · deal-video: Gemini ครบ 6/6 (Zubenelgenubi/Leda/Achird/Sulafat/Puck/Zubenelgenubi) render 25–33 วิ + telegram 2–3 วิ (1.0–1.8MB) ≈ 35 วิ/ดีล · คลิปเข้า Telegram 6/6 · ไม่มี 429/fallback
ฝั่ง user (ทำในแอป): กด Disagree/Request review · แก้ไบโอเป็นคำอธิบาย + เปิดเผยพันธมิตร · **ห้ามเลี่ยง** (ลิงก์ในคอมเมนต์/สตอรี่) จะโดนปิดบัญชี · หลัง 26 ต.ค. ค่อยพิจารณาเพิ่มจำนวน IG ทีละน้อย (เช่น 2/รอบ) และดูว่าโดนซ้ำไหม · ตรวจสถานะได้จาก API: `GET /{ig}?fields=followers_count,media_count,biography,website` + นับโพสต์/วันจาก `/{ig}/media`

## Reels จากรูปสินค้า — ทดลอง (19 ก.ย. 2569)
เหตุผล: IG มีผู้ติดตามแค่ 1 คน โพสต์ภาพนิ่งแทบไม่มีคนเห็น ส่วน Reels ถูกส่งไปหาคนที่ยังไม่ติดตามด้วย
- **ดึงคลิปจากร้านไม่ได้** — ลิงก์ Shopee 5/5 มีแต่ `og:image` ไม่มี `og:video` → **สร้างคลิปเองจากรูป**
- สคริปต์อยู่ `vps/deal-video/` (ตัวจริงบน VPS `/root/deal-video/sample/`):
  `render.sh` = คลิปแนวตั้ง 720×1280 ยาว 8 วิ (รูปซูมช้า + พื้นหลังเบลอ + ป้าย -X% + ราคา + แถว CTA) ใช้เวลาทำ ~17 วิบน VPS 1 core
  `post_reel.js` = โพสต์ Reels ด้วย **resumable upload** (`upload_type=resumable` → POST binary ไป `rupload.facebook.com` header `Authorization: OAuth` + `offset` + `file_size`)
  → **ไม่ต้องมี URL สาธารณะของไฟล์** (ต่างจาก image_url) · ถ้าจะทำ Threads ด้วยค่อยต้องหาที่ฝากไฟล์
- ⛔ **ห้ามใช้ `drawtext` เขียนภาษาไทย** — แม้ ffmpeg มี harfbuzz แต่ **วรรณยุกต์ที่ซ้อนบนสระบนหาย** ("นึ่ง"→"นึง", "จิ๋ว"→"จิว") ทั้งที่ข้อความต้นทางครบ
  ให้ใช้ **libass** (`ass=filename=subs.ass:fontsdir=...`) แทน · ขนาดฟอนต์ ASS เล็กกว่า drawtext ~1.5 เท่าที่ตัวเลขเดียวกัน ต้องชดเชย
  · `drawtext` ยังตีความ `%` เป็นรหัสพิเศษ (ป้าย `-61%` เพี้ยน) ถ้าจำเป็นต้องใช้ต้องใส่ `expansion=none`
- ฟอนต์ Kanit (Google Fonts, OFL) โหลดไว้ที่ `/root/deal-video/fonts/` · container n8n **ไม่มี ffmpeg** มีแต่ตัว host
- โพสต์ทดลองชิ้นแรก: https://www.instagram.com/reel/DddAjj4iMc6/ (media `17965755585178931`, ดีลหวดนึ่งข้าวเหนียว) — Meta ประมวลผลเสร็จในรอบ poll แรก (6 วิ)
- **ดึงยอดวิวผ่าน API ยังไม่ได้** — `/{media}/insights` ตอบ `(#10) Application does not have permission` ต้องเพิ่ม `instagram_manage_insights` (ขั้นตอนเดียวกับ perms อื่น: App → Use cases → Access Token Tool → เปลี่ยน token ใน workflow) · ระหว่างนี้ดูยอดในแอป IG เอา

### ✅ ต่อเข้า workflow อัตโนมัติแล้ว (19 ก.ย. 69) — IG โพสต์เป็น Reels ทุกดีล, ล้มเมื่อไหร่ถอยไปโพสต์ภาพ
สาย IG ใน `E6i2xEAcaUsUFKWm`: `IG Has Image?` → **`IG Reel`** (Code) → **`IG Reel OK?`** → true = จบ · false → `IG Create Media` (ภาพ แบบเดิม)
- **container `deal-video`** บน VPS (ซอร์ส `vps/deal-video/service/` · ของจริง `/root/deal-video/service/` · deploy ด้วย `deploy.sh`)
  = python:3.12-slim + ffmpeg(libass) + edge-tts · อยู่บน `n8n_default` **ไม่เปิด port/ไม่มี traefik** เรียกได้จากใน n8n เท่านั้น `http://deal-video:8080`
  `POST /render {name,sale,full,img[,upload:{url,token}]}` · `GET /health` · เรนเดอร์ทีละคลิป ~20 วิ (`--cpus 0.8 --memory 700m`)
- `IG Reel` ทำ: สร้าง container REELS (แคปชัน + **เครดิตเพลง CC BY แทรกอัตโนมัติ**) → ส่ง `uri` ของ rupload + token ให้ service **เรนเดอร์แล้วอัปโหลดเอง**
  → poll `status_code` ทุก 5 วิ จน FINISHED → `media_publish` · เว้น 30 วิระหว่างดีล · `onError: continueRegularOutput` + try/catch → ไม่มีทาง throw
- ⛔ **ส่งไฟล์ binary ออกจาก Code node ไม่ได้** — task runner (`N8N_RUNNERS_ENABLED`) serialize Buffer เพี้ยน อัปโหลดไปได้แต่ Meta ตอบ
  `Video Transcoding Error … progressive_video_not_ready` (ขาเข้า Code node รับ binary ได้ปกติเป็น Uint8Array) → จึงให้ service อัปโหลดเอง
- บทพูด **ไม่อ่านชื่อสินค้า** (ชื่อจริงยาว 30–98 ตัว ปนอังกฤษ/รหัสรุ่น อ่านแล้วแปลก) — พูดแค่ hook (สุ่มจาก 3 แบบตาม hash ชื่อ) + ราคาเป็นคำอ่าน + CTA
  ชื่อขึ้นจอ ตัดเป็น ≤ 2 บรรทัด × 26 ตัว (ตัดที่ช่องว่าง ไม่งั้นตัดแบบไม่แยกสระ/วรรณยุกต์ออกจากพยัญชนะ) + `…`
  ไม่มีราคาเต็ม = ไม่มีบรรทัดราคาเดิม/ป้าย % · TTS ล้ม = ได้คลิปมีแต่เพลง (`X-Voice: 0`) ไม่ถือว่าล้ม
- `Split Approved` ส่ง `sale`/`full` ต่อมาด้วยแล้ว (เดิมมีแค่ name/link/caption)
- ดูผลรายดีล: execution → runData ของ `IG Reel` (`reelOk`, `reelId`, `voice`, หรือ `reelError: <ขั้น>: …`)
- ⚠️ edge-tts ยังเป็นบริการไม่เป็นทางการ (ดูด้านล่าง) — ถ้าเริ่มล้มบ่อย `voice:false` จะโผล่ใน runData → ย้ายไป Azure Speech
- **รอบจริงรอบแรก 19 ก.ย. 69 15:00** → Reels ขึ้นสำเร็จ https://www.instagram.com/reel/DddiG--DhF8/ แต่ **ไม่มีเสียง** (edge-tts `NoAudioReceived` เป็นช่วง ๆ — ข้อความเดิมล้มแล้วผ่านเอง บางท่อนต้องลอง 4–6 ครั้ง)
  → เพิ่ม retry 8 ครั้งถอยเวลา (timeout รวม 150 วิ) · log บอกจำนวนครั้งที่ลอง: `docker logs deal-video | grep "tts seg"`
- ✅ **ย้ายไป Azure Speech (ทางการ) แล้ว 19 ก.ย. 69** — user สมัคร Azure, resource `paiyaa-tts` (rg `paiyaa`, region **`eastus`**, tier Free F0 = 0.5M ตัวอักษร/เดือน ไม่หมดอายุ)
  key อยู่ **หน้า Notion Config หัวข้อ "🔊 Azure Speech"** และบน VPS ที่ `/root/deal-video/service/.env` (`AZURE_SPEECH_KEY`/`AZURE_SPEECH_REGION`) — **ไฟล์ .env ไม่อยู่ใน repo** `deploy.sh` ส่งเข้า container ด้วย `--env-file`
  `server.py`: มี key → Azure REST (`/cognitiveservices/v1` SSML `<prosody rate pitch>` เสียง/พารามิเตอร์เดิมทุกอย่าง) retry 3 · ไม่มี key หรือ Azure ล้ม → ถอยไป edge-tts อัตโนมัติ
  log: `ok (azure)` ต่อท่อน · เทสต์ 3 คลิปติดกันได้เสียงครบ ไม่ต้อง retry เลย · ตั้งเครื่องใหม่/VPS ใหม่ → สร้าง .env จากค่าใน Notion ก่อน deploy

### ⛔ node IG Reel มีเพดาน 300 วิ — 6 ดีลไม่พอเวลา (เกิดจริง 20 ก.ย. 69 รอบ 09:00)
`IG Reel` เป็น **task เดียวของ task runner ทั้ง node** (ไม่ใช่ task ละ item) → รันเกิน 300 วิ = `Task execution timed out after 300 seconds`
- รอบนั้น 6 ดีล: ลง Reels สำเร็จ 3 ตัวแล้วโดนตัดกลางทาง → error output ปล่อย **item เดิมทั้ง 6 ตัว** (ผลรายดีลที่ทำไปแล้วหายหมด)
  → `IG Reel OK?` เห็นว่าไม่มี `reelOk` → โพสต์ภาพทั้ง 6 → **3 ดีลแรกได้ทั้ง Reels และภาพ (ซ้ำ)**
- `IG Publish` ตอบ error `subcode 2207085 Fatal/Generic Internal Error` ทั้ง 6 แต่ **ภาพขึ้นจริงครบทั้ง 6** (timestamp เดียวกันหมด) — error ตัวนี้เชื่อไม่ได้ ต้องเช็คที่ `GET /{ig}/media` เสมอ
- **แก้แล้ว 20 ก.ย. 69**: ใส่กันชนเวลาใน `IG Reel` — จับเวลาต่อ execution ด้วย `globalThis.__reel` (รีเซ็ตเมื่อ `$execution.id` เปลี่ยน · ห้ามใช้ตัวแปร global เปล่า ๆ จะค้างข้ามรอบ)
  ใช้ไปเกิน **200 วิ → ดีลที่เหลือถอยไปโพสต์ภาพทันที** (`reelError: budget: …`) ไม่เสี่ยงโดนตัดกลางทาง
  · ลดเวลารอระหว่างดีล 30 → **8 วิ** (เรนเดอร์เองกิน ~20 วิอยู่แล้ว) · poll สถานะ 5 → **3 วิ** → ต่อดีลเหลือ ~35 วิ (6 ดีล ≈ 210 วิ)

**เวอร์ชันมีเสียง (19 ก.ย. 69)** — `tts.py` + `build_av.py` ใน `vps/deal-video/`
- user เลือก**เสียงผู้หญิง** (Premwadee, บทแบบคุยกัน ค่ะ/น้า) → โพสต์แล้ว https://www.instagram.com/reel/DddcrKoCBKy/ (media `18078606824365969`, แคปชันมีเครดิตเพลง)
  สั่ง: `N8N_KEY=… node post_reel.js sample_female.mp4` (อ่าน `reel_caption.txt` ข้างไฟล์)
- เสียงพากย์: แบ่งบทเป็น 4 ท่อน (`vo` ใน texts.json) → สร้างเสียงทีละท่อน → **ตัดช่วงเงียบหัวท้าย** (`silenceremove` ไปกลับด้วย `areverse`)
  → วัดความยาวจริงแต่ละท่อน → **ตั้งเวลาข้อความบนจอให้ขึ้นตอนเสียงพูดถึง** (ราคาเก่า/ราคาใหม่/CTA) · ความยาวคลิปคำนวณจากเสียง (~11 วิ)
  ไม่ตัดเงียบ = คลิปยืดเป็น 15 วิ
- ตัว TTS รันใน **container `python:3.12-slim` ชั่วคราว** (`docker run --rm ... pip install edge-tts`) — host ไม่มี pip และ**ไม่ลงของบน host**
  ⚠️ `edge-tts` ใช้บริการอ่านออกเสียงของ Microsoft Edge แบบไม่เป็นทางการ — **ใช้ทำตัวอย่างได้ แต่ถ้าจะใช้จริงอัตโนมัติ**
  ให้ย้ายไป **Azure Speech (ทางการ)** เสียงเดียวกัน (`th-TH-PremwadeeNeural` หญิง / `th-TH-NiwatNeural` ชาย) free tier 0.5M ตัวอักษร/เดือน — ใช้จริงราว 40K/เดือน
- เพลง: **"Carefree" — Kevin MacLeod (incompetech.com) CC BY 4.0** ที่ `/root/deal-video/music/` ระดับ 0.14 ใต้เสียงพากย์
  ⚠️ **CC BY ต้องใส่เครดิตในแคปชันทุกโพสต์ที่ใช้** เช่น `🎵 Carefree — Kevin MacLeod (incompetech.com) · CC BY 4.0` · เพลงในคลังของ IG ใส่ผ่าน API ไม่ได้
- ความดัง: `loudnorm=I=-14:TP=-1.5` (มาตรฐานโซเชียล) — ก่อนใส่ได้ -22 dB เบาเกิน · วัดด้วย `ebur128`

### 🎙 บันทึกการปรับเสียง — **งานต่อเนื่อง ไม่ใช่งานปิดแล้ว**
> **วิธีได้ตัวอย่างให้เขาฟัง (ไม่ต้องรอรอบโพสต์):** `ssh hostinger 'sh /root/deal-video/sample.sh'`
> → ได้ `/root/deal-video/sample_voice.mp4` + `sample_music.mp4` จากดีลเดียวกัน แล้ว `scp` ลงมาฟัง
> ซอร์สอยู่ `vps/deal-video/sample.sh` · ส่ง JSON เป็น arg เพื่อเปลี่ยนดีลได้ · บังคับโหมดด้วยฟิลด์ `voice` ของ `/render`
> ⛔ **ส่ง JSON override ต้องเอาทุกฟิลด์ (name/sale/full/desc/img/cat) มาจากแถว Notion เดียวกัน** — 26 ก.ย. 69 เคยใส่ชื่อ "หวดนึ่ง" แต่แปะรูป Dr.PONG
> จากการ์ดแรกของหน้ารวมดีล → คลิปเสียงกับภาพคนละเรื่อง user เห็นแล้วสั่งลบด่วน (โชคดีเป็นแค่ตัวอย่างในแชทส่วนตัว) · วิธีที่ถูก: query Notion
> (`สถานะ=โพสต์แล้ว` + `หมวด` + `รูป` ไม่ว่าง) แล้วส่งทั้ง object · ถ้าอยากได้ hook ชนิดใดชนิดหนึ่ง ให้ import `server.py` แล้วรัน `script_for()` หาแถวที่ hash ตกชนิดนั้นก่อน
> **ส่งให้เขาฟังทาง Telegram ได้เลย (25 ก.ย. 69)**: `sendVideo` ไป chat_id `8336016992` (แชทเดียวกับ Posted Alert) ด้วย token ของบอทจาก node `TG Posted Alert`
> (อ่านจาก workflow ใน script ห้าม print) — ใช้เมื่อ session ส่งไฟล์ตรงไม่ได้ (Claude Code บนเว็บ/remote ไม่มี project thread) · ทำแล้ว msg 1099–1100
> ⚠️ 25 ก.ย. คลิปพากย์ยาว **17.2 วิ** (เพลงล้วน 11.4) — ฐานที่จดไว้หลังรอบ #7 คือ ~10.1 วิ ต้องดูว่าเป็นดีลนี้บทยาวเป็นพิเศษหรือ #7/#8 ยืดจริง (6 ดีล × 17 วิ + เรนเดอร์ ยังอยู่ในงบ 200 วิของ `IG Reel` แต่เฉียดขึ้น)
> **จำเป็นเพราะคิวดีลว่างเมื่อไหร่ก็ไม่มีคลิปให้ฟัง** (เกิดจริง 22 ก.ย. 69: คิวเหลือ 0 ทั้งวัน รอบโพสต์ได้ 0 ดีล)
>
> คำสั่งศุภชัย 19 ก.ย. 69: **"ในแต่ละครั้งที่ upload คลิปเสียง พยายามปรับให้เป็นธรรมชาติขึ้นเรื่อย ๆ"**
> ทุก session ที่แตะ Deal Poster → ดูตารางนี้ว่าลองอะไรไปแล้ว แล้วขยับอีกขั้น (ทีละจุด) + ส่งตัวอย่างให้เขาฟัง
> **Claude ฟังเสียงเองไม่ได้ ต้องให้เขาตัดสินเสมอ** · ปรับเสร็จจดผลลงตารางนี้

| รอบ | ปรับอะไร | ผล |
|---|---|---|
| 19 ก.ย. #1 | บทแบบคุยกัน (ค่ะ/นะ/น้า) + ตัวเลขเป็นคำอ่าน + EQ/คอมเพรส/เสียงสะท้อนห้อง | ดีขึ้น แต่ยัง "พูดติดกันไป" |
| 19 ก.ย. #2 | ลดความเร็วทุกท่อน (+14/+6/+10/+2 → +4/−6/−8/−6) + เว้นระหว่างท่อน 0.45–0.7 วิ | ยังติดกันในท่อนราคา |
| 19 ก.ย. #3 | หยุดหายใจกลางประโยค (เครื่องหมายคั่นในบท → ellipsis+space) | ผ่าน แต่ช่วงเว้นเยอะไปตอนวาง ellipsis ผิดแบบ |
| 19 ก.ย. #4 | ตัดจุดหยุดที่ไม่จำเป็น เหลือรอบตัวเลข + ช่วงท่อน 0.3–0.5 วิ + `บาท…เองค่ะ` ชิดขึ้น | ✅ "เกือบสมบูรณ์" |
| 19 ก.ย. #5 | คำว่า "ลิงก์" เสียงต่ำ → สะกดบทเป็น **"ลิ้งค์"** | ✅ ผ่าน |
| 20 ก.ย. #6 | **hook 5 แบบ / CTA 3 แบบ** (เดิม 3/2) + **ขยับ rate/pitch/ช่วงเว้นรายดีล** (`prosody_for`/`gap_for` สุ่มคงที่จาก hash ชื่อ ±2.5%/±2.5Hz/±0.08 วิ) + ดีลไม่มีราคาได้ท่อนกลาง (`NOPRICE`) แทนคลิปโล่ง 7 วิ | รอผลฟัง |
| 21 ก.ย. #7 | **บทพูดล้วน ไม่แตะเสียง/prosody/FX เลย** — hook 5→11 · CTA 3→6 · NOPRICE 2→4 · เพิ่มคำเชื่อมแบบคนพูด (`DESC_LEADS`) และท่อนราคาหลายสำนวน (`OLD_LINES`/`NEW_LINES`/`SALE_LINES`/`FULL_LINES`) เลือกด้วย hash ชื่อเหมือนเดิม → ชุดผสม **15 → 1,782 แบบ** | **รอ deploy + รอผลฟัง** |

✅ **รอบ #7+#8 deploy แล้ว 22 ก.ย. 69 11:35 UTC** (scp จาก Windows → ไฟล์ live เป็น CRLF แต่เนื้อหาตรง repo ทุกบรรทัด · เทียบด้วย `diff --strip-trailing-cr`)
⛔ **แต่รอบ #8 พาบั๊กมาด้วย — Reels ล้มทุกดีล 22–25 ก.ย. 69 (~3 วัน, ทุกรอบ)**: `forced` ถูกนิยามใน `render()` แต่ถูกใช้ใน `do_POST`
(header `X-Voice-Mode` และ JSON `voice_mode`) → **NameError หลังเรนเดอร์+อัปโหลดเสร็จแล้ว** service ตอบ 500 →
n8n เห็น `render+upload: Request failed with status code 500` → ถอยไปโพสต์ภาพทุกดีล (container REELS ที่อัปโหลดไว้ค้างเป็นกำพร้าใน IG)
ซ้ำร้าย ดีลละ ~40 วิถูกเผาไปเปล่า ๆ ก่อนถอย → รอบ 6 ดีลชนงบ 200 วิ 1–2 ดีลท้ายเป็น `budget:` ไปด้วย
· **แก้แล้ว 25 ก.ย. 69** (นิยาม `forced` ใน `do_POST` 1 บรรทัด, deploy ใหม่, `sample.sh` ผ่านทั้ง 2 โหมด) · backup `server.py.bak.20260925`
· **บทเรียน**: (1) deploy `server.py` ทีไรต้องรัน `sample.sh` ทันที — บั๊กนี้โผล่ตั้งแต่ request แรก แต่ไม่มีใครยิงเทส 3 วัน
  (2) ดู `runData` ของ `IG Reel` หลังรอบแรกที่ deploy เสมอ: `reelOk:false` ทุกดีล = พัง ไม่ใช่ปกติ · (3) Python ไม่มี compiler เตือนตัวแปรนอก scope → `python3 -m py_compile` ผ่านก็ยังพังได้ ต้องยิงจริง
· ประวัติ 24 ก.ย. 69 ที่เห็นในรายการ execution: รอบ 02:00–11:00 UTC สถานะ `error` ที่ `LINE Posted Alert` "too many requests" (LINE rate limit → เป็นเหตุให้ session นั้นย้าย alert ไป TG)
  และ **สาย IG ไม่ได้รันเลยในรอบพวกนั้น** (ลำดับ branch ของ executionOrder v1 ไป LINE ก่อน IG พอ error ก็จบ) · รอบ 14:00 UTC `crashed` "possible out-of-memory" ระหว่าง Post to Facebook (n8n ถูก restart ~15:00 UTC วันนั้น)

บทเรียนรอบ #7: ให้น้ำหนักคำเชื่อมเท่ากันทุกช่องไม่ได้ — รอบแรกตั้ง `DESC_LEADS` 4 ช่องเท่ากัน ลองรันกับดีลจริง
12 ตัวแล้วคำเชื่อมโผล่ 11/12 **จำเจกว่าเดิม** เพราะคนพูดจริงไม่ได้ขึ้นต้นด้วยคำเชื่อมทุกประโยค →
ถ่วงด้วยการใส่ `'%s'` เปล่าซ้ำหลายช่อง (ตอนนี้เปล่า 59% / มีคำเชื่อม 41%)
· วัดผลต่อความยาว: **+0.62 วิ/คลิป** (ฐาน ~9.5 → ~10.1) = 6 ดีล +3.7 วิ ยังห่างงบ 200 วิของ `IG Reel`

| 22 ก.ย. #8 | **สลับรอบ มีพากย์ / เพลงล้วน** (user ขอ) — `voice_for_round()` ใน `server.py` ตัดสินเองจากนาฬิกา **ไม่ต้องแตะ n8n** · payload ส่ง `"voice": true/false` มา = บังคับ (ไว้เทสมือ) · คลิปเงียบแบ่งเวลาข้อความตามความยาว (`silent_durs`) แทน 1.3 วิเท่ากันทุกท่อน | **รอ deploy + รอผลฟัง** |
| 26 ก.ย. #9 | **บทพูดจากเทรนด์ TikTok ไทย ก.ย. 69** (user สั่ง "สำรวจเทรนด์ที่กำลังนิยม" แล้วเคาะ "เอาทั้งหมด") — hook 11→19 (ตัด "โอเค…" ที่ทุกแหล่งปี 2026 บอกให้เลิก · เพิ่มสาย "บอกต่อ" ตามแฮชแท็กที่ติด 8/30 อันดับ · คำถามด้วยคำลงท้าย · ศัพท์ 2569 เทสมาก/ทำถึง/เริ่ด) + **hook 3 ชนิดใหม่เลือกด้วย hash**: `CAT_HOOKS` เรียกกลุ่มตาม `หมวด` (1/3 ของดีลที่มีหมวด) · `PCT_HOOKS` ชูตัวเลขส่วนลด ≥20% (ครึ่งหนึ่ง, แล้วท่อนราคาไม่พูด % ซ้ำ) · `DISCOUNT_HOOKS` urgency แบบไม่โกหก (1/5 ของดีลลด) · CTA 6→11 (ชวนติดตาม/เก็บไว้/"สาดไปสมาชิก") · NEW_LINES 3→6 (ฉ่ำ/ชีเสิร์ฟ) · OLD_LINES 3→5 · **n8n ส่ง `cat` เพิ่ม** (`Split Approved` อ่าน `หมวด` → `IG Reel` ใส่ใน body) · dry-run 14 ดีล: ชูตัวเลข 5 / ปกติ 5 / เรียกกลุ่ม 4 | **ฟังแล้ว 26 ก.ย.: "ชีเสิร์ฟ" กับ "เทส" เพี้ยน → ถอดออกแล้ว deploy ใหม่ 09:38 UTC** (hook เหลือ 17, NEW 5) · บทเรียน: **คำทับศัพท์อังกฤษในบท Azure ไทยอ่านเพี้ยน** ใช้ได้แต่ศัพท์ที่เป็นคำไทย (ทำถึง/เริ่ด/ฉ่ำ) · "แก็ดเจ็ต" ใน CAT_HOOKS เปลี่ยนเป็น "สายไอที" ด้วย (user สั่ง) |

**คำเพี้ยนมาจากช่อง `คำบรรยาย` ได้ด้วย ไม่ใช่แค่บทของเรา (26 ก.ย. 69)** — user ฟังตัวอย่างหมวด gadget แล้วสะดุด "เคสกระจก**อากาศแข็ง**" ซึ่งเป็น desc ที่ Haiku เขียนไว้ใน Notion (แปล "Tempered Glass" ตรงตัวจนได้คำที่ไม่มีในภาษาไทย) → แก้ที่ **prompt ของ `Claude Write Caption`** (`e8aD2wCvsVYmefrq`) เพิ่มกติกา desc: ใช้ได้เฉพาะคำไทยที่ใช้จริง · ห้ามแปลชื่ออังกฤษตรงตัว · ห้ามคำทับศัพท์สะกดไทย (เทส/ชีเสิร์ฟ/แก็ดเจ็ต) · ยี่ห้อ/รุ่นคงสะกดอังกฤษ (iPhone) ใส่เท่าที่จำเป็น
· **คำที่ในชื่อสินค้าเป็นอังกฤษ ให้คงอังกฤษทุกคำ ห้ามแปล ห้ามทับศัพท์** (user เคาะ 26 ก.ย.: "ถ้าเขียนเป็นภาษาอังกฤษ ไม่ต้องแปล" + "พูดและเขียนทับภาษาอังกฤษได้เลย" — ให้ Azure อ่านอังกฤษตรง ๆ ดีกว่าคำไทยที่แต่งขึ้น)
· ผล dry-run หลังปรับ: "เคส Luxury Tempered Glass สำหรับ iPhone 11 12 13 14 Pro Max 14 Plus" / "จอมอนิเตอร์ Arzopa ขนาด 27 นิ้ว 180Hz IPS ความละเอียด 2K QHD" · ตัวอย่างเสียงแบบนี้ส่งแล้ว `sample9_gadget_en.mp4` (TG msg 1199) รอ user ฟังว่าอ่านอังกฤษ+เลขรุ่นโอเคไหม
· ลองยิง Haiku ด้วย prompt ใหม่ 3 ชื่อ: "เคสกระจกเคลือบสำหรับ iPhone รุ่นต่าง ๆ" / "จอมอนิเตอร์เกมมิ่ง Arzopa ขนาด 27 นิ้ว…" — หายแล้ว · **มีผลเฉพาะดีลที่เข้าคิว "ใหม่" หลังจากนี้** แถวที่มี desc อยู่แล้วไม่ถูกเขียนใหม่
· บทเรียน: เวลาฟังตัวอย่างแล้วเจอคำเพี้ยน ให้แยกก่อนว่าคำนั้นอยู่ใน `server.py` (บทของเรา) หรือมาจาก Notion (`คำบรรยาย`/ชื่อ) — แก้คนละที่
· ตัวอย่างที่ส่งฟัง: `sample9_gadget_voice.mp4` (Luxury Tempered Glass Case iPhone, hook "สายไอที") TG msg 1198 + `home-console:/usr/share/nginx/html/samples/`

| 26 ก.ย. #10 | **ช้าลง + เว้นกว้างขึ้น** (user ฟัง #9 แล้ว: "ช่วงห่างระหว่างประโยคยังไม่ดี พูดให้ช้าลงนิดนึง") — `PROSODY` rate ลดอีก 4 ทุกท่อน (+4/−2/−6/−8/−6 → 0/−6/−10/−12/−10, pitch เดิม) · `GAP_AFTER` +0.15 ทุกช่วง (0.4/0.35/0.3/0.5 → 0.55/0.5/0.45/0.65) · ไม่แตะบท · deploy 11:14 UTC · backup `server.py.bak.20260926c` | ฟังแล้วยังติด 2 จุด → ทำต่อเป็น #11 |
| 26 ก.ย. #11 | **ตัวเลขเว้นวรรคกับหน่วย + "บาท | เอง" ห่างขึ้น** — user: "สี่สิบเอ็ด ออกเสียงเป็น สี่สิบเอ๊ด สูงไป" · ส่งเทียบ 3 แบบ (ติดกัน / เว้นวรรค `สี่สิบเอ็ด เปอร์เซ็นต์` / เลขอารบิก `41`) → **"B C ได้"** เลือกเว้นวรรค: `thai_words()`/`approx_words()` คืน `' คำอ่าน '` แล้ว `script_for` collapse ช่องว่างซ้ำ (ครอบทุกจุด: hook ชูตัวเลข/ราคาเก่า/ราคาใหม่/เปอร์เซ็นต์) · user: "บาทเอง ติดกันเกิน ไม่ธรรมชาติ" → `บาท…เอง` (0.1 วิ ที่ #4 เคยขอให้แคบ) กลับเป็น `บาท | เอง` (~0.33 วิ) ทั้ง 8 สำนวน · deploy 11:36 UTC (running=0 ตรวจแล้วจึงทำ) · `sample.sh` ผ่าน 2 โหมด (พากย์ 21.3 วิ / เพลง 11.9 วิ) · backup `server.py.bak.20260926d` · ตัวอย่าง `sample11_gadget.mp4` TG msg 1213 | user: "บาท…เอง ห่างเกินไป" → #12 |
| 26 ก.ย. #12 | **"บาท, เอง"** — วัดช่วงหยุดจริงด้วย ffprobe (ดูตารางล่าง) พบว่า `' | '` (= `'… '`) **ต่อท้าย "บาท" กลายเป็น 1.3 วิ** (ที่อื่น 0.17–0.31) เพราะ Azure ถือเป็นจบประโยค → ใช้ `', '` ได้ +0.33 วิ ค่ากลางระหว่างติดคำ (0.14) กับที่ user ว่าห่างเกิน (1.3) · 7 สำนวนราคา (NEW 5 + SALE 2) · deploy 11:52 UTC · sample.sh ผ่าน 2 โหมด (พากย์ 20.2 วิ) · ตัวอย่าง `sample12_gadget.mp4` TG msg 1216 | user: "เอง..นะ ตัด นะ ออก น่าจะใช้ได้แล้ว" → #13 |
| 26 ก.ย. #13 | **ตัด "น้า" ท้าย "เอง"** (2 สำนวน: `ลดมาเหลือ | %sบาท, เอง` และ `ราคาแค่ | %sบาท, เอง` · `เองค่ะ` คงเดิม) · **แต่พอ "เอง" กลายเป็นคำท้ายวลี ` \| ` (= `… `) ที่ตามมาก่อนท่อน % ยืดเป็น 1.34 วิ** (วัดแล้ว — เหมือนหลัง "บาท") user ฟัง #13 แล้วสั่งทันที "ขยับวรรคถัดมาเข้ามาใกล้อีกนิด" → #13b: ใน `script_for` ถ้าสำนวนราคาจบด้วย `เอง` ให้ tail % เริ่มด้วย `, ` แทน ` \| ` (0.58 วิ) · deploy 12:01 UTC · sample.sh ผ่าน 2 โหมด (พากย์ 20.4 วิ) · `sample13b_gadget.mp4` TG msg 1218 | user: "บาท,เอง ยังไม่ติดกัน แก้ให้ติดกันเลย" → #14 |
| 26 ก.ย. #14 | **"บาทเอง" ติดกัน ไม่มีตัวคั่นเลย** (5 บรรทัดโค้ด: NEW 3 + SALE 2 — `เอง`/`เองค่ะ`) · `บาท, ฉ่ำมาก` / `บาท, เท่านั้น` คงลูกน้ำ (คนละโครงประโยค) · tail % หลัง `เอง` ยังเป็น `, ` ตาม #13b · deploy 12:05 UTC · sample.sh ผ่าน 2 โหมด (พากย์ 19.9 วิ) · `sample14_gadget.mp4` TG msg 1219 | user ยังว่า "บาทเอง ยังไม่ต่อกันเหมือน บาทแน่ะ" → ตรวจด้วย `silencedetect` **ไม่มีช่วงเงียบระหว่าง บาท กับ เอง เลย** (ที่ได้ยินคือจังหวะอ่านคำ "เอง" ที่ขึ้นต้นด้วยสระ) ส่งเสียงท่อนนี้ให้ฟังซ้ำ → **"pr_P_now.mp3 ok" = ผ่าน** ค่าปัจจุบันคือค่าสุดท้ายของ บาท→เอง |

⛔ **`<prosody>` ซ้อนในประโยค (บีบ/กดเฉพาะคำ) ใช้ไม่ได้กับ Azure ไทย** — ลอง 26 ก.ย. 69 ครอบ "บาทเอง" ด้วย `<prosody rate="+20%">` → Azure **แทรกหยุด ~1.1 วิ ทั้งหน้าและหลัง** span (วัดด้วย silencedetect) ประโยคยืดจาก 5.4 → 7.6 วิ · ดังนั้นแนวคิด "กด pitch เฉพาะตัวเลข" (D/E/F #11) ก็มีปัญหาเดียวกัน ห้ามหยิบกลับมา · ปรับได้แค่ระดับทั้งท่อน (`PROSODY`) หรือเปลี่ยนคำ/ตัวคั่นเท่านั้น

สรุปเส้นทาง บาท→เอง ที่ user ตัดสินมาแล้ว (อย่าวนกลับ): `…` ติดคำ 0.14 (19 ก.ย. ขอแคบ → 26 ก.ย. "ติดกันเกิน") → `… ` 1.3 ("ห่างเกิน") → `, ` 0.33 ("ยังไม่ติดกัน") → **ไม่มีตัวคั่น = ค่าสุดท้าย** — คำว่า "ติดกันเกิน" รอบแรกจึงน่าจะหมายถึง "บาท…เอง" ที่ TTS อ่านสะดุด ไม่ใช่เร็วเกิน

**กฎที่ตกผลึกจาก #11–#13: คำที่ Azure มองเป็น "จบประโยค" (บาท / เอง / น่าจะรวมคำลงท้ายเดี่ยว ๆ อื่น) ตามด้วย `… ` = หยุด 1.3 วิ** — ` | ` ในบทจึงใช้ได้แค่กลางวลี ถ้าต้องคั่นหลังคำพวกนี้ใช้ `, ` (0.33–0.58) หรือ `…` ติดคำ (0.14) · เจอคำใหม่ที่สงสัยให้วัดตามวิธีในตารางก่อน อย่าเดา

**ตารางช่วงหยุดของ Azure th-TH-PremwadeeNeural (วัด 26 ก.ย. 69 ด้วย ffprobe, rate −11%)** — ใช้ตัดสินใจก่อนใส่เครื่องหมายในบท ไม่ต้องเดา:
| ตัวคั่น | หลัง "บาท" (จบวลี) | กลางประโยคทั่วไป |
|---|---|---|
| ไม่มี / ช่องว่างเดี่ยว | 0 | 0 |
| `…` ติดคำ / `……` / `-` ติดคำ | +0.09–0.14 | — |
| `,` ติดคำ / `, ` | +0.16 / **+0.33–0.43** | +0.62–0.74 |
| ` - ` / `; ` | +0.36 / +0.48 | — |
| `… ` (= ` \| ` ในบท) / ` …` / ช่องว่างคู่ | **+1.27–1.34** ⚠️ | +0.17–0.31 |
| `<break time="100–250ms"/>` | +1.44–1.58 (ไม่ตามค่าที่สั่ง ห้ามใช้) | — |

วิธีวัด: ยิง SSML ตรงจาก container (`docker exec deal-video python3 -` import `server` ใช้ `server.AZ_KEY`/`VOICE`/`prosody_for`) แล้ว `ffprobe -show_entries format=duration` เทียบกับประโยคเดียวกันที่ไม่มีตัวคั่น — ทำได้โดยไม่ต้องฟัง
⛔ **บทเรียน patch 26 ก.ย. (พลาด 2 รอบติด ส่งคลิปผิดเข้า TG 2 ครั้ง ต้องลบ msg 1214/1215)**: (1) `str.replace` ทั้งไฟล์โดนคอมเมนต์ที่มีสตริงเดียวกันด้วย → assert นับจำนวนพลาด (2) chain bash ยาวที่ python ล้มตรงกลางแล้ววิ่งต่อ deploy+ส่งของเดิม — `set -e` ในเครื่องมือนี้ไม่ช่วย ต้อง **แยกขั้น patch ให้ผ่านก่อนในคำสั่งเดียว** แล้วค่อย deploy ในคำสั่งถัดไป และใส่ `|| exit 1` / `if … exit` ทุกขั้นที่ตามมา

ทางเลือกที่ลองแล้วไม่ได้ใช้ (#11): กด pitch เฉพาะคำตัวเลขด้วย SSML `<prosody>` ซ้อน (มาร์กเกอร์ ‹ › ใน `thai_words` → แปลงใน `azure_tts`) ส่งเทียบ D/E/F (ทั้งท่อน +4Hz / ตัวเลข −8Hz / ทั้งคู่) แล้ว user ตอบเรื่องเว้นวรรคแทน → ถอยโค้ดออก ไม่ commit · ถ้าวันหลังเสียงสูงเพี้ยนที่คำอื่นค่อยหยิบกลับมา (โค้ดอยู่ใน transcript 26 ก.ย. ไม่ยาก ~10 บรรทัด)
· ⚠️ คลิปพากย์ยาวขึ้นเรื่อย ๆ: #9 16.5 → #10 19.9 → #11 21.3 วิ (ดีลเดียวกัน) · 6 ดีล/รอบ × (21 วิ + เรนเดอร์ ~20 วิ + poll) จะชนงบ 200 วิของ `IG Reel` ที่ ~4–5 ดีล — รอบ 18:00 วันนี้ (เพลงล้วน!) ก็ทำได้แค่ 4 ดีลแล้ว (236 วิ) → ถ้า Reels ต่อรอบสำคัญกว่าจังหวะพูด ต้องคุยเรื่องขยายงบ/ลดจำนวนดีลต่อรอบ

⛔ **บทเรียน deploy #10 (26 ก.ย. 69)**: สคริปต์ deploy ของผมพิมพ์ `running: 1` แต่ไม่ได้หยุด — recreate `deal-video` ตอน 11:14 UTC **ขณะรอบโพสต์ 18:00 น. (exec 38623) กำลังรัน** (รอบใช้ ~21 นาที เริ่ม 11:00) → ต่อไปให้เช็คแบบ **หยุดถ้าไม่ใช่ 0** (`[ "$n" = 0 ] || exit 1`) และอย่า deploy ในช่วง xx:00–xx:25 ของชั่วโมงที่มีรอบ (0/6/9/12/15/18/21 น. ไทย = 17/23/02/05/08/11/14 UTC) · ผลกระทบดูจาก runData `IG Reel` ของ exec นั้น

| 27 ก.ย. #15 | **เปลี่ยนตัวเสียงเป็น `th-TH-NiwatNeural` (ชาย)** — user ฟัง 8 เสียงแล้วเลือก H · บททั้งชุดเปลี่ยนคำลงท้าย ค่ะ/คะ→ครับ, นะคะ→นะครับ, น้า→นะ (29 บรรทัด ทำด้วย regex เฉพาะในสตริง ไม่แตะคอมเมนต์) · `PROSODY` pitch ลดครึ่ง (+4/+2/0/+6/+2) rate เดิม · ช่วงหยุดที่วัดไว้เป็นของ Premwadee — Niwat อาจต่าง ถ้าจังหวะเพี้ยนให้วัดใหม่ตามตาราง · deploy 02:23 UTC · sample.sh ผ่าน 2 โหมด (พากย์ 19.8 วิ) · backup `server.py.bak.20260927` · `sample15_niwat.mp4` TG msg 1259 | รอผลฟัง |

| 27 ก.ย. #16 | **สลับ 2 เสียงต่อดีล**: user "ใช้ Niwat สลับกับ K1" → `VOICES = {niwat, krit}` เลือกด้วย `voice_for(seed, d)` = `VOICE_ORDER[(h//53)%2]` (คงที่ตาม hash ชื่อ · 38 ดีล gadget แบ่ง 19/19) · payload `"tts": "niwat"|"krit"` บังคับได้ · `azure_tts(..., voice=)` + `xmlns:mstts` · log `[render] tts voice=<key>` และ `tts seg N ok (azure <key>)` · edge-tts สำรองใช้ Niwat เสมอ · deploy 02:49 UTC · ตัวอย่าง `sample16_krit.mp4` (29.5 วิ) / `sample16_niwat.mp4` (19.8 วิ) TG msg 1265–1266 | รอผลฟัง |

⚠️ **Krit (MAI-Voice-2) ช้ากว่า Niwat ~45%** วัดรายท่อน (วินาที, ก่อนตัดเงียบ): hook 2.6→3.1 · desc 6.7→**11.8** (อ่านคำอังกฤษ/เลขรุ่นช้ามาก) · old 3.3→4.6 · new 5.4→6.2 · cta 2.9→4.1 · รวม 20.8→29.9 · **ไม่รับ `<prosody rate>`** (rate −6% กับ 0% ยาวเท่ากัน) · ตัด ` | `/`…` ออกช่วยบางท่อน (รวม 24.3) แต่ CTA กลับยืดเป็น 7.1 — ไม่สม่ำเสมอ ไม่ได้ใช้ · เวลาสังเคราะห์เอง ~2 วิ/ท่อน (เท่า Niwat) → ที่กระทบคือ **ความยาวคลิป → เวลา encode → งบ 200 วิของ IG Reel** (ดีล Krit ≈ 30 วิ/คลิป encode ~33 วิ) ถ้า Reels ต่อรอบสำคัญ ให้ลดสัดส่วน Krit หรือใช้ Krit เฉพาะดีลที่ desc สั้น/ไม่มีอังกฤษ

| 27 ก.ย. #17 | **Gemini TTS เป็นเสียงหลัก** (user ฟัง 6 เสียง Gemini แล้ว "ok ทุกตัว") — `voice_for` คืน `gemini:<Voice>` สลับ 6 เสียง (Puck/Achird/Zubenelgenubi ชาย · Leda/Laomedeia/Sulafat หญิง) ตาม hash · เสียงหญิง `feminize()` แปลง ครับ→ค่ะ ตอนสังเคราะห์ · ยิงทีละท่อน (ทดสอบแบบยิงทั้งบทครั้งเดียวแล้วตัดด้วย silencedetect: **ไม่แม่น + คลิปยืด 27–34 วิ** ไม่ใช้) · ล้ม/429 → ถอยทั้งคลิปไป Azure Niwat + cooldown (รายวัน 6 ชม. / รายนาที 90 วิ) · deploy 08:13 UTC · backup `server.py.bak.20260927b` | **ยังไม่ได้ผลจริง — free tier 10 คำขอ/วัน** |

⛔ **Gemini TTS free tier = 10 คำขอ/วัน/โมเดล** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier 10` วัด 27 ก.ย. 69) ไม่ใช่ต่อนาทีอย่างที่คิด → ตัวอย่าง 6 + ทดสอบ 4 = หมดวันแรก · โพสต์จริงต้อง ~25–30 คำขอ/รอบ → **ต้องเปิด billing ในโปรเจกต์ Google Cloud ที่ออก key** (AI Studio → API keys → โปรเจกต์ → Billing) ถึงจะได้ Gemini จริง · ระหว่างนี้ทุกคลิปได้ Niwat (ดู log `gemini tts failed … (daily quota) -> fallback azure niwat`) · คลิป #17 ที่ส่ง TG (msg 1285–1286) เป็น Niwat ไม่ใช่ Gemini → ลบแล้ว · ~~ตัวอย่างคลิปเต็มเสียง Gemini ยังไม่มี~~ **user เปิด billing แล้ว 27 ก.ย. 69 ~09:40 UTC** → 429 ที่เหลือคือ **เพดานต่อนาที ~10 คำขอ** (quotaId `GenerateRequestsPerMinutePerProjectPerModel` ไม่มี FreeTier) → `_tts` เจอ 429 รายนาที: รอตาม `retryDelay` (≤20 วิ) ลองใหม่ 1 ครั้ง ค่อยถอย Azure + cooldown 60 วิ · รายวัน (FreeTier) → cooldown 6 ชม.
⛔ **ห้ามใส่คำสั่งสไตล์นำหน้าบท** — วัดจริง: ท่อน "สายไอที, ต้องดูอันนี้" ข้อความล้วน 2.4 วิ · นำหน้าด้วย "Say in a friendly…" 4.9 วิ · ไทยสั้น 4.1 วิ · ไทยยาว (ที่ใช้ตอนแรก) **13.5 วิ = อ่านคำสั่งออกเสียงทั้งดุ้น** (คลิปเต็มพองเป็น 72 วิ!) · `systemInstruction` ใช้กับโมเดล TTS ไม่ได้ (400) → `GEMINI_STYLE = ''` ใช้โทนธรรมชาติของเสียง (ตัวอย่าง 6 เสียงที่ user ok มีคำสั่งไทยยาวปน = น่าจะได้ยินคำสั่งถูกอ่านด้วย แต่ user ก็ ok) · deploy 09:52 UTC · **คลิปเต็ม Gemini จริง** `sample17_gemini_m.mp4` (Zubenelgenubi 21.8 วิ) / `sample17_gemini_f.mp4` (Sulafat 23.1 วิ) TG msg 1287–1288 ตรวจ log แล้ว 10/10 ท่อนเป็น Gemini · Gemini ยาวกว่า Niwat ~2–3 วิ/คลิป
**ผลรอบจริงรอบแรก 00:00 น. 28 ก.ย. 69 (exec 39300)**: 6 ดีล → Reels 4 (**Gemini ครบทุกท่อน 4/4 ดีล: Sulafat/Zubenelgenubi/Leda/Puck** ไม่มี 429 ไม่มี fallback) อีก 2 ดีลถอยไปภาพเพราะชนงบ 215 วิ (ใช้ไป 257) · จับเวลาจริงต่อดีล: **render 23–25 วิ** (TTS Gemini 4 ท่อน ~11 วิ + encode ~13 วิ · ดีลไม่มีราคา = 4 ท่อน) + **upload ไป rupload.facebook.com 22–23 วิ ต่อไฟล์ ~0.8–1.0MB (≈40KB/s!)** + n8n (สร้าง container/poll/publish/gap) ~18 วิ = **~64 วิ/ดีล** → งบ 215 ได้ 3–4 ดีล, งบ 300 (hard cap) ก็ได้แค่ 4 → **ต้องเปลี่ยนโครง: วน Loop Over Items ทีละดีล ให้ IG Reel เป็น task แยกต่อดีล (300 วิ/ดีล)** ดูรอบ #19

| 27 ก.ย. #18 | **ลดต้นทุน ffmpeg ให้ Reels ครบ 6 ดีล** (user สั่ง หลังรอบ 21:00 เพลงล้วนยังได้แค่ 4/6 ที่ ~58 วิ/ดีล) — (1) พื้นหลังเบลอ `bg.png` และรูปสินค้า `fg.png` 720² ทำครั้งเดียวก่อน encode (เดิม `boxblur=30:3` บน 720×1280 + `zoompan` บน 1200² ทุกเฟรม) (2) FPS 30→24 (3) คง preset veryfast — วัด idle คลิปเพลง 11.8 วิ: **14.7 → 9.7 วิ** ไฟล์ 745→751KB · ultrafast เร็วกว่าอีกนิด (9.3) แต่ไฟล์ 4.2MB อัปโหลดช้าลง ไม่เอา · คลิปพากย์ Gemini 22 วิ render รวม 32 วิ (TTS ~15 + encode ~17) · เพิ่ม log `[timing] render=… upload=…` + JSON `render_s/upload_s` ไว้แยกว่าช้าที่เรนเดอร์หรืออัปโหลด (รอบจริง 21:00 ใช้ 44 วิ/คลิปทั้งที่ idle 15 วิ — ยังไม่รู้ว่าเพราะ CPU ชนกับ n8n หรือ upload ไป Meta) · **n8n `IG Reel`: ช่องว่างระหว่างดีล 8→3 วิ, งบ 200→215 วิ** · env `X264_PRESET/X264_CRF/FPS` ไว้ทดลอง · deploy 15:06 UTC · backup `server.py.bak.20260927c` · ตัวอย่าง `sample18_music.mp4` TG msg 1336 (ให้ดูภาพ) | รอผลรอบ 00:00 (พากย์ Gemini) และรอบ 06:00 (เพลง) ว่าได้ครบ 6 ไหม |

| 28 ก.ย. #19 | **สาย IG เป็น loop ทีละดีล** — ผลรอบ 00:00 (Gemini จริง) ชี้ว่า ~64 วิ/ดีล (render 24 + upload ไป Meta 22 + n8n 18) → ต่อให้ใช้ hard cap 300 วิ ก็ได้แค่ 4 ดีล/task · แก้โครง: `IG Has Image?` → **`Loop Reels`** (splitInBatches v3, batch 1) → loop → `IG Reel` → กลับ Loop · done → `IG Reel OK?` (เดิม) = **IG Reel เป็น task แยกต่อดีล (300 วิ/ดีล)** · `IG Reel`: จับคู่ดีลด้วย `page_id` (Build IG Caption ส่งมาเพิ่ม) ก่อนถอยไป `.item` · gap 3 วิ นับจาก `g.n` (ใน loop `$itemIndex`=0 เสมอ) · งบรวมทั้งรอบ 480 วิ (กันรอบยืดผิดปกติ) · upload ช้าไม่ใช่แบนด์วิดท์ VPS (ส่ง 1MB ไป Cloudflare 0.1 วิ) แต่เป็นฝั่ง rupload ของ Meta ตอบช้า แก้ไม่ได้ | ✅ **ผ่านรอบจริง 06:00 น. 28 ก.ย. 69 (exec 39431, เพลงล้วน)**: 5 ดีล → **Reels 5/5** · Loop Reels วน 6 ครั้ง (5 loop + 1 done) · page_id ไม่ซ้ำ ครบทุกดีล · IG Create Media ไม่ถูกเรียกเลย (ไม่มีดีลถอยไปภาพ) · Build Posted Alert จับคู่ชื่อถูก 5/5 · ต่อดีล: render 8.5–10 วิ (#18 ได้ผล) + upload 21–23 วิ + n8n ~16 วิ ≈ 47 วิ · ทั้งรอบ 16 นาที |

| 3 ต.ค. #20 | **บทพูดไม่วนซ้ำ** (user: "บทพูดเริ่มซ้ำ ๆ เดิม ให้คิดบทพูดให้ทันสมัยอยู่เรื่อย ๆ") — 2 ชั้นใน `server.py`: (1) **pool เดิมเลือกแบบ LRU** — `pick(pool, h, recent)` อ่าน `/tiktok/script_log.jsonl` (host `/root/deal-video/tiktok/script_log.jsonl` · บันทึกแม่แบบ hook/cta/old/new ของทุกคลิป 40 ตัวล่าสุด) เลือกตัวที่ไม่ได้ใช้นานสุดก่อน เสมอกันค่อยใช้ตำแหน่ง hash → ดีลเดิม render ซ้ำก็ได้สำนวนใหม่ (ทดสอบ: 3 รอบ 2 ดีล ไม่ซ้ำเลย) · DESC_LEADS ยังใช้ hash (ถ่วงน้ำหนักช่องว่าง 59% ไว้) (2) **LLM เขียนบทรายดีล** `llm_script()` → Haiku (`LLM_SCRIPT_MODEL` ค่าเริ่มต้น claude-haiku-4-5-20251001) เขียน `hook/desc/cta` ตาม **`/root/deal-video/tiktok/script_style.txt`** (แนวเทรนด์ปัจจุบัน — **แก้ไฟล์นี้ได้เลยไม่ต้อง deploy** · ค่าเริ่มต้นใน `STYLE_DEFAULT`) + รายการ avoid จาก log · ด่านตรวจ `script_ok`: ห้ามตัวเลข/`?`/`#`/อิโมจิ/คำต้องห้าม (`SCRIPT_BANNED`: เทส ชีเสิร์ฟ แก็ดเจ็ต ไบโอ ลิงก์ ใช้แล้ว ถูกสุด ใกล้หมด โอเค) · อักษรอังกฤษใช้ได้เฉพาะคำที่อยู่ในชื่อสินค้า · CTA ต้องมี 'ป้ายยาดีล ดอทคอม' 1 ครั้ง · hook ชูตัวเลข (PCT) ยังใช้แม่แบบ · **ท่อนราคาเป็นแม่แบบเสมอ** (LLM ไม่พูดตัวเลข) · ไม่ผ่าน/ล้ม/timeout 12 วิ → pool + cooldown 10 นาที · log `[script] src=llm|pool hook=…` · ⛔ **LLM ยังไม่เปิด**: ต้องมี `ANTHROPIC_API_KEY` ในไฟล์ env ของ deal-video (ตอนนี้ไม่มี — auto-mode classifier ไม่ให้ผม copy key จาก workflow Caption Writer เข้าไฟล์ env · user ต้องวางเอง: ค่าจากหน้า Notion Config แล้ว `sh deploy.sh` ช่วง running=0) · ปิดชั่วคราว `LLM_SCRIPT=0` · deploy 01:46 UTC running=0 · backup `server.py.bak.20261003b` · sample.sh ผ่าน 2 โหมด · **งานประจำ: ทุก ~1 เดือน สำรวจเทรนด์ TikTok ไทยแล้วอัปเดต `script_style.txt`** (ครั้งล่าสุด 3 ต.ค. 69) | รอ key + รอผลฟัง |

**สลับยังไง** — `ROUND_HOURS = [0,6,9,12,15,18,21]` (ต้องตรงกับ cron ของ `E6i2xEAcaUsUFKWm` แก้ที่นั่นต้องแก้ที่นี่ด้วย)
พาริตี้ = `(วันที่นับจาก epoch + ลำดับรอบ) % 2` — **บวกวันด้วยเพราะถ้าใช้ลำดับรอบอย่างเดียว 00:00 จะมีพากย์ตลอดกาล**
แล้วเทียบผลไม่ได้เลย (โหมดผูกกับเวลาโพสต์ถาวร) · รอบ/วัน = 7 เป็นเลขคี่ → ข้ามวันแล้วยังสลับต่อเนื่อง ไม่ซ้ำสองรอบติด
ตรวจแล้ว 28 รอบ 4 วัน: ไม่มีรอบติดกันซ้ำแบบเดียวกันเลย · พากย์ 14 / เพลง 14
- เวลาไทยคำนวณด้วย `+7*3600` ตรง ๆ ไม่พึ่ง tzdata (คอนเทนเนอร์ `python:3.12-slim` ไม่มี) — ไทยไม่มี DST
- เพลงดังขึ้นเองอยู่แล้วเมื่อไม่มีพากย์ (`volume=0.14 if voiced else 0.5`) ไม่ต้องแก้เพิ่ม
- **เครดิตเพลง CC BY ยังต้องมีเหมือนเดิม** เพราะยังใช้เพลงอยู่ → node `IG Reel` ไม่ต้องแก้เลย
  (ถ้าวันหลังเปลี่ยนเป็น "เงียบสนิทไม่มีเพลง" ต้องไปตัดเครดิตออกจาก `IG Reel` ด้วย ไม่งั้นแคปชันโกหก)
- ดูโหมดรายคลิปได้จาก header `X-Voice` / `X-Voice-Mode` (`auto`|`req`), ฟิลด์ `voice_mode` ใน JSON ตอน upload,
  และ log `[render] voice=... (auto)` ใน `docker logs deal-video`

⛔ **กับดักที่เกือบหลุดไปคลิปจริง (เจอ 22 ก.ย. 69)**: ข้อความขึ้นจอเดิมดึงจาก `segs` ตัวเดียวกับบทพูด
พอรอบ #7 ใส่คำเชื่อม + ตัวคั่น `' | '` เข้าไปในท่อน `desc` จอจะขึ้นว่า `คือ | เคสไอโฟน…` ให้คนทั้งอินเทอร์เน็ตเห็น
(`' | '` เป็นสัญญาณให้ TTS หยุดหายใจ ไม่ใช่ข้อความ) → แก้เป็นเรียก `clean_desc(d.get('desc'))` ตรง ๆ ตอนเรนเดอร์จอ
**กฎ: อะไรที่เติมลงบทพูดเพื่อคุมน้ำเสียง ห้ามไหลไปโผล่บนจอ — เพิ่มท่อนพากย์ทีไรให้ไล่ดู ASS event ทุกครั้ง**

หมายเหตุรอบ #9: hook/CTA เป็น**เสียงล้วน ไม่ขึ้นจอ** (จอมีแค่แบรนด์/ชื่อ/คำบรรยาย/ราคา/CTA ตายตัว) จึงใส่ ` | ` และศัพท์วัยรุ่นได้โดยไม่ต้องกังวลกฎ "คำคุมเสียงห้ามหลุดขึ้นจอ" · ถ้าวันหลังจะเอา hook ขึ้นจอต้อง strip ` | ` ก่อน
· ⛔ บทเรียนตอนแก้: เขียนไฟล์ด้วย `open(p,'w')` แล้ว exception ก่อน `.write()` = **ไฟล์ว่างเปล่าทันที** (เกิดจริง 26 ก.ย. 69 กับ server.py ใน repo — กู้จาก git ได้เพราะ commit ไว้แล้ว) → เขียนลง `.new` แล้ว `os.replace` เสมอ
· แหล่งเทรนด์ที่ใช้: Krevio "7 สูตร hook 2026", Kapook พจนานุกรม Gen Z 2569, สถิติแฮชแท็ก TikTok ไทย 22 ก.ย. 69 (aclosetwriter), Opus/Zeely/Kineclip hook 2026 — ควรสำรวจใหม่ทุก ~1 เดือน ศัพท์เปลี่ยนเร็ว

**เปลี่ยนตัวเสียง (27 ก.ย. 69 — user: "ฟังแล้วรู้เลยว่าเป็น AI")** — สำรวจ `GET /cognitiveservices/voices/list` ที่ eastus: เสียงไทยแท้มี Premwadee/Achara (หญิง), Niwat (ชาย) และ **รุ่นใหม่ `th-TH-Nattapong:MAI-Voice-2` / `th-TH-Krit:MAI-Voice-2`** (ชาย มีสไตล์ friendlycheerful/excited/… ใช้ผ่าน `<mstts:express-as style=…>`) · เสียง multilingual/DragonHD (Emma/Ava/Xiaoxiao ฯลฯ 232 ตัว) พูดไทยได้เป็นภาษารอง · **ทุกตัวรวม HD/MAI สังเคราะห์ได้บน tier F0** (เทสแล้ว 8/8 ผ่าน) · ส่งตัวอย่างบทเดียวกัน 8 เสียง (A Achara · B Emma ML · C Ava ML · D Xiaoxiao ML · E Emma DragonHD · F Nattapong MAI · G Krit MAI · H Niwat) TG msg 1251–1258 → **user เลือก H = Niwat** (27 ก.ย. 69) · user: "Niwat ok สุดตอนนี้, Krit เกือบดี" → ส่ง Krit เพิ่ม 5 สไตล์ (K1 ไม่ใส่สไตล์ · K2 friendlycheerful · K3 encouraging · K4 curious · K5 friendlycheerful rate 0) TG msg 1260–1264 รอผล · ถ้าเลือก Krit: `azure_tts` ต้องเพิ่ม `xmlns:mstts` + ห่อ `<mstts:express-as style=…>` และควรวัดเวลาสังเคราะห์ (MAI-Voice-2 เป็นโมเดลใหญ่กว่า อาจช้ากว่า → กระทบงบ 200 วิของ IG Reel) · ถ้าเปลี่ยนเสียง: `VOICE` ใน server.py + ต้องปรับ `PROSODY` ใหม่ (ค่าเดิมจูนกับ Premwadee) + คำลงท้าย ค่ะ/ครับ ถ้าเป็นเสียงชาย + ถ้าใช้ MAI style ต้องเพิ่ม namespace mstts ใน SSML ของ `azure_tts` · ทางเลือกนอก Azure ถ้ายังไม่พอใจ: ElevenLabs (ไทยได้ ธรรมชาติมาก มีค่าใช้จ่าย), OpenAI TTS, Botnoi Voice (ไทยโดยเฉพาะ)

**Gemini TTS (Google AI Studio) — ทดลอง 27 ก.ย. 69** (user ถาม "Google studio voice ดีกว่ามั้ย") — key อยู่หน้า Notion Config หัวข้อ "Google AI Studio" (เป็นข้อความ) และ `/root/deal-video/service/.env` → `GOOGLE_AI_KEY` (ยังไม่ได้ recreate container = ยังไม่มีในตัว service · ใช้ทำตัวอย่างจาก host เท่านั้น)
- อ่าน key จาก Notion ด้วยสคริปต์ที่ดึงเฉพาะบล็อกใต้หัวข้อแล้วเขียน .env ตรง ไม่พิมพ์ (integration Deal Poster ต้องถูก Connect กับหน้า Config — user ทำแล้ว 27 ก.ย.) · ครั้งแรก user วางเป็นรูป อ่านไม่ได้ ต้องเป็นข้อความ
- โมเดล TTS ที่ key นี้เห็น: `gemini-2.5-flash-preview-tts`, `gemini-2.5-pro-preview-tts`, `gemini-3.1-flash-tts-preview`, **`gemini-3.8-flash-tts`**, `gemini-3.8-flash-lite-tts` · เรียก `POST /v1beta/models/<model>:generateContent` `responseModalities:['AUDIO']` + `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName` · ตอบ inlineData **mime `audio/wav`** (ไม่ใช่ raw L16 อย่างในเอกสารเก่า — ตอนทำตัวอย่างถอดด้วย `-f s16le` จึงมี header 44 ไบต์ปนหัวคลิปเป็นเสียงกริ๊กสั้น ๆ ถ้าเอาเข้าระบบต้องเช็ค mime แล้ว decode เป็น wav)
- คุมสไตล์ด้วยประโยคสั่งนำหน้าบท (ไม่มี SSML/prosody) · ตัวอย่าง 6 เสียง บทเดียวกับ Niwat/Krit: G1 Puck · G2 Achird · G3 Zubenelgenubi (ชาย) · G4 Leda · G5 Laomedeia · G6 Sulafat (หญิง) TG msg 1277–1282 **รอ user เลือก** · ยาว 22.6–25.6 วิ (Niwat 19.8) · สังเคราะห์ ~9 วิ/คลิปทั้งบท
- ⚠️ **free tier ชน 429 ที่คำขอที่ 5 ภายใน ~1 นาที** → ถ้าใช้จริง (5 ท่อน × 6 ดีล/รอบ) ต้องเปิด billing หรือสังเคราะห์ทั้งบทในคำขอเดียวแล้วหาเวลาขึ้นจอด้วย silencedetect · ต้องคง Azure Niwat เป็น fallback

**ไอเดียที่ยังไม่ได้ลอง** (คิวถัดไป): ขึ้นเสียงท้ายประโยคคำถาม · ใส่เสียงหายใจเบา ๆ ก่อน hook ·
ลองเสียง `th-TH-AcharaNeural` เทียบ Premwadee · ปรับ `aecho` ให้แห้งลงเมื่อฟังแล้วเหมือนอยู่ห้องโถง

⛔ **อย่าเพิ่งใส่ `?` ลงในบท** — รอบ #7 เลี่ยงไว้ตั้งใจ ยังไม่มีใครวัดว่า Azure เสียงไทยเติมหยุดกี่วินาทีต่อ `?`
(`<break>` เติม ~1.4 วิ/จุด · `, ` และ `… ` ≈ 0.33 · `. ` ไม่หยุด — `?` ยังไม่เคยวัด) ต้องวัดก่อนใช้:
`docker exec deal-video python3 -c "..."` เรนเดอร์ท่อนเดียวสองแบบ (มี `?` / ไม่มี) แล้วเทียบ duration
ภาษาไทยใช้คำลงท้าย (มั้ย/รึเปล่า/ใช่มั้ย) ทำน้ำเสียงคำถามได้อยู่แล้ว — รอบนี้ใช้วิธีนั้นแทน (hook "นี่ | กำลังหาอะไรแบบนี้อยู่รึเปล่า")

## คำบรรยายสินค้าในคลิป + คิวแคปชันตัน (21 ก.ย. 2569)

**คิวตัน — `page_size: 10` ไม่มี pagination.** 20 ก.ย. ดีลเข้าทาง Telegram **66 ตัวใน 3 ชั่วโมง** (18:00 น. 9 ตัว,
20:00 น. 54 ตัว, 21:00 น. 3 ตัว) แต่ `Query New Deals` ขอ Notion ทีละ 10 แถวและไม่เคยอ่าน `next_cursor`
→ ทุกรอบตั้งแต่ 20:50 ตอบ `has_more: true` ค้างไว้ ทยอยได้รอบละ 10 เท่านั้น (3 ชม./รอบ = 80 ตัว/วัน เพดานจริง)
แก้เป็น `page_size: 100` (สูงสุดที่ Notion ให้) **เฉย ๆ ไม่ได้วน cursor**

⛔ **กับดัก: `$response` / `$pageCount` resolve ได้เฉพาะในช่อง pagination ของโหนด HTTP Request — ใน `jsonBody` ไม่ได้**
รอบแรกลองใส่ `start_cursor` ใน body ด้วย `$pageCount > 0 ? {...} : {}` → n8n คืน `invalid syntax` **ทุกครั้งที่รัน**
โหนดตายตั้งแต่ Query (21 ก.ย. รอบ 20:50 ล้มทั้งรอบ exec 35878) · mock test ที่รัน jsCode ด้วย `new Function()`
**จับไม่ได้** เพราะมันตรวจ JS ไม่ได้ตรวจ scope ของ expression n8n — ของแบบนี้ต้องยิงรันจริงเท่านั้น
ถ้าวันไหนดีลเกิน 100 ตัวต่อ 3 ชม. จริงค่อยทำ pagination โดยใส่ cursor เป็น **body parameter ของ pagination**
(`parameters: [{type:'body', name:'start_cursor', value:'={{ $response.body.next_cursor }}'}]`) ซึ่งอยู่ใน scope
`Split New` ต้องแก้ด้วย: เดิมอ่าน `$json.results` = **ได้แค่หน้าแรก** ตอนนี้วน `$input.all()` + กัน page id ซ้ำ

**คอขวดย้ายไปอยู่ฝั่งโพสต์แทน (ตรวจ 21 ก.ย. 69).** สาย A คลายแล้ว แต่ `Deal Poster v1` ยังมีเพดานของมันเอง:
`Query Approved Deals` ขอ `page_size: 10` **ไม่มี `sorts`** → Notion คืนเรียง `last_edited` เก่าก่อน (FIFO
ไม่มีดีลไหนโดนแซงถาวร) แล้ว `Split Approved` ปิดท้าย **`.slice(0, 6)`** → **6 ดีล/รอบ × 7 รอบ = 42 ดีล/วัน**
วันที่ดีลเข้าเกินนั้น (20 ก.ย. เข้ามา 66) คิว "อนุมัติแล้ว" จะค้างข้ามวันเป็นเรื่องปกติ **ไม่ใช่อาการเสีย** —
ดูได้จาก `has_more: true` ใน runData ของ `Query Approved Deals` · ถ้าจะเร่ง ต้องคิดเผื่อ `IG Reel` ที่มี
budget 200 วิ/รอบอยู่แล้ว (ดีลเกินงบถอยไปโพสต์ภาพ) — เพิ่มจำนวนดีล = สัดส่วน Reels ต่อรอบลดลงตาม

**คำบรรยายสินค้า.** เพิ่ม property `คำบรรยาย` (rich_text) ใน Deal Queue · `Claude Write Caption` เปลี่ยนเป็นขอ
JSON `{caption, desc}` ครั้งเดียว (max_tokens 400→600) · `Build Caption` ดึงก้อน `{...}` ด้วย regex แล้ว parse
— **พังเมื่อไหร่ถอยไปใช้ทั้งก้อนเป็นแคปชันแบบเดิม** ดีลจึงไม่มีทางไม่มีแคปชัน · `Deal Poster` อ่านแล้วส่งเป็น `desc`
ให้ `deal-video`
- `server.py`: role ใหม่ `desc` แทรกหลัง hook — **ต้องเติมคีย์ใน `PROSODY`/`GAP_AFTER`/`ROLE_BITS` ครบทั้งสามตาราง**
  ขาดตารางใดตารางหนึ่ง = `KeyError` ตอนเรนเดอร์ ไม่ใช่ fallback · `clean_desc()` ตัดลิงก์/แฮชแท็ก/อีโมจิ และตัดที่
  90 ตัวด้วย `safe_cut` (กันสระลอย) · ไม่มี desc = ลำดับท่อนเท่าเดิมทุกประการ
- **บนจอใช้พื้นที่ร่วมกับบล็อกราคา** ไม่ได้เพิ่มที่ใหม่ — ช่วง y 800–1100 มีที่พอแค่ชื่อ (2 บรรทัด fs54) + ราคาใหม่ (fs150)
  เท่านั้น จึงเพิ่ม `ev2(start, end, …)` ให้คำบรรยายจบตอนราคาขึ้น (`ev` เดิมยืนถึงจบคลิปเสมอ) ·
  ดีลไม่มีราคา = คำบรรยายค้างถึงจบแทนจอโล่ง
- วัดแล้ว: คลิปยาว 7.9 → 9.5 วิ · desc ที่ Haiku คืนมามักเป็นการ**เล่าชื่อสินค้าซ้ำ** เพราะกติกาห้ามเดาสเปกที่ไม่อยู่ในชื่อ
  (ตั้งใจ — มันถูกพากย์ออกคลิปสาธารณะ) ถ้าจะให้เอนไปทางบอกประโยชน์ต้องแก้ prompt ไม่ใช่แก้ `server.py`

### กับดัก n8n CLI (เจอตอนไม่มี API key ในมือ)
⚠️ วิธีในหัวข้อ "กติกาเหล็ก" คือ `PUT /api/v1/workflows/{id}` — รอบนี้ใช้ CLI แทนเพราะยังไม่ได้หยิบ n8n API key
ผลเหมือนกันแต่กับดักคนละชุด ใครมี key อยู่แล้วใช้ API ตามเดิมจะเรียบกว่า
- `n8n import:workflow` **ปิด active ของ workflow ทุกครั้ง** ("Remember to activate later") ต้องต่อด้วย
  `n8n publish:workflow --id=…` เสมอ — ลืม = workflow ตายเงียบตอน n8n restart รอบถัดไป
- `--input=/tmp/x.json` คือ `/tmp` **ในคอนเทนเนอร์ n8n** ต้อง `docker cp` เข้าไปก่อน
- publish/import **ไม่มีผลจนกว่าจะ restart n8n** (CLI บอกเอง) — ตัว process ถือ workflow ที่ activate ไว้ใน memory
  DB เป็น `active=0` แต่ schedule ยังยิงจากของเก่าได้เรื่อย ๆ จนกว่าจะ restart
- `n8n execute --id` ใช้กับ workflow ที่มีแต่ Schedule Trigger **ไม่ได้** (ต้องมี Execute Workflow Trigger) และชน
  task broker port 5679 ของตัวที่รันอยู่ → ต้องใส่ `-e N8N_RUNNERS_BROKER_PORT=5779`
- **ไม่มีคำสั่ง `delete:workflow`** ใน 2.3.6 — workflow ชั่วคราวต้องไปลบใน UI เอง
- รอบนี้ **restart container n8n** (ขัดกับหัวข้อ deals-proxy ที่เลี่ยงไว้) กลับมาครบ 23 workflow ไม่มีตัวไหนพลาด
  แต่ถ้ามี execution ค้างอยู่จะโดนตัดกลางคัน — เช็ค `status in ('running','new','waiting')` ก่อนเสมอ
- จังหวะที่ปลอดภัย: Deal Poster ใช้เวลา **~21 นาที/รอบ** (09/12/15/18/21 น.) และ Caption Writer ยิง :50
  ของ 02/05/08/11/14/17/20/23 น. → ช่องว่างจริงคือ **xx:25–xx:45 ของชั่วโมงที่ไม่มีรอบโพสต์**

## ซ่อมย้อนหลัง (backfill) เมื่อบางช่องล้มแต่ Mark Posted ไปแล้ว
⛔ **ห้ามเปลี่ยนสถานะใน Notion กลับเป็น "อนุมัติแล้ว"** — รอบถัดไปจะยิงซ้ำทุกช่องรวมช่องที่สำเร็จไปแล้ว ไม่มีตัวกันซ้ำรายช่อง

ให้ยิง Graph API ตรงแทน โดยเลียนแบบ node ทีละขั้น (เคยทำจริง 25 ส.ค. 69 — ซ่อม FB+IG ของ 8 ดีลวันที่ 24 ส.ค.):
1. `GET` ลิงก์ affiliate ด้วย UA `TelegramBot (like TwitterBot)` → regex `property="og:image" content="..."` (= `Fetch Deal Image` + `Build Post Body`)
2. โหลดรูปด้วย UA `Mozilla/5.0` → `POST /{page_id}/photos` multipart พร้อมแคปชัน + ท้าย `🔗 รวมดีลทั้งหมด…`
3. `GET /{photo_id}?fields=images` → เอา `source` ที่ `width` มากสุด (รูปบน FB CDN — Meta ดึงจาก Shopee CDN ไม่ได้)
4. สร้างแคปชัน IG (ตัดบรรทัดที่มี `http` + ต่อท้ายแฮชแท็ก) → `POST /{ig}/media`
5. **poll `GET /{creation_id}?fields=status_code` จนได้ `FINISHED`** แล้วค่อย `POST /{ig}/media_publish`
6. เว้น 60 วิต่อดีล (throttle เดียวกับใน workflow)

ตรวจว่าช่องไหนล้มจริงด้วย `GET /api/v1/executions/{id}?includeData=true` แล้วดู `runData` รายโหนด —
node ที่ "ok" แต่ body มี `{"error": ...}` คือล้มเงียบ · เช็คซ้ำที่ปลายทางด้วย `GET /{page_id}/posts` และ `GET /{ig}/media`

## Monitoring
การ์ด "🛒 Deal Poster" บน Home Console `https://home.srv1277799.hstgr.cloud` (traefik basic-auth, user `admin`) —
endpoint `/api/dealposter` ใน container **`home-metrics`**; **ซอร์สตัวจริงคือ `/root/home-metrics/server.js`**
(ไฟล์ `/docker/n8n/home/metrics/server.js` เป็นของเก่าคนละตัว — เคยหลงมาแล้ว 23 ส.ค. 69)
ตัว endpoint วน `start_cursor` ดึง Notion ได้ถึง **20×100 แถว** ส่งกลับ `items` ครบทุกสถานะ + `queue` + `rounds` (cache 60 วิ)
**20 ก.ย. 69: 5 → 20 หน้า** (เดิม 500 แถว ตอนนั้นมี 431 อีก ~5 วันจะเกิน แล้วดีลที่ไม่ถูกแก้มานานจะหายจากหน้าเงียบ ๆ ไม่มี error)
⚠️ **ซอร์สมี 2 ที่ ต้อง sync ทั้งคู่**: `/root/home-metrics/server.js` (ที่ build ภาพจริง) และ `/docker/n8n/home/metrics/server.js`
(= build context ของ `docker-compose.home.yml`) — ถ้าแก้ที่เดียว วันหลังใครรัน `compose up --build` จะย้อนกลับเงียบ ๆ
⚠️ `home-metrics:base` **โดน prune หายจาก VPS แล้ว** → Dockerfile เดิม `FROM home-metrics:base` build ไม่ผ่าน
แก้เป็น `FROM node:22-alpine` ยืนด้วยตัวเอง (แอปใช้แต่ stdlib ไม่มี node_modules)
deploy: `docker build -t home-metrics:live /root/home-metrics` → `cd /docker/n8n && docker compose -f docker-compose.home.yml up -d --no-build --no-deps --force-recreate home-metrics`
(**ต้องมี `--no-build`** ไม่งั้น compose จะ build จาก `./home/metrics` แทน)

**ค่าลับย้ายออกจากซอร์สแล้ว 20 ก.ย. 69** — เดิม n8n API key + Notion token hardcode อยู่บรรทัด 135–136
(หลุดทุกครั้งที่มีใคร `cat`/`diff` ไฟล์ — เกิดจริงวันนั้น) ตอนนี้อ่านจาก `process.env` ที่ compose ส่งเข้ามาจาก
**`/root/home-metrics/.env`** (chmod 600 · ไม่อยู่ใน repo · ไม่อยู่ในภาพ docker) → ซอร์สไม่ต้อง sanitize ก่อน commit อีก
- **rotate**: `ssh hostinger "bash /root/home-metrics/rotate.sh"` — ถาม 2 ค่าแบบไม่โชว์บนจอ เขียน .env แล้วสร้าง container ใหม่ + ตรวจให้ว่าใช้ได้จริง
- ⛔ **`docker restart` ไม่อ่าน `env_file` ใหม่** — env ถูกตรึงตอน *สร้าง* container ไม่ใช่ตอน start
  rotate ด้วย `docker restart` = **ค่าเก่ายังค้าง แต่ทุกอย่างดูผ่านหมด** (เจอจริงตอนเทส 20 ก.ย. 69) ต้อง `compose up --force-recreate` เท่านั้น
- ⛔ Notion token ผิด **ไม่ทำให้ error** — `postJSONH` คืน body ที่ไม่มี `results` → `q.results || []` กลายเป็นลิสต์ว่าง
  `notionError` จึงว่างทั้งที่พัง → ตรวจ rotate ต้องดู **จำนวนแถว = 0** ด้วย ไม่ใช่ดูแค่ error
- token ของ **expense-bot / subs เป็น Notion integration คนละใบ** (ลายนิ้วมือต่างกัน) — rotate ตัวนี้ไม่กระทบ
หน้าเว็บ: Home Console มี 2 ซอร์ส — `/root/home-console/html/index.html` (**ตัว live**) กับ `/docker/n8n/home/index.html` (ของเก่า ธีมมืด) — แก้ต้องแก้ทั้งคู่
deploy หน้าเว็บ: `scp` ทับ `/root/home-console/html/index.html` แล้ว
`docker cp /root/home-console/html/index.html home-console:/usr/share/nginx/html/index.html` (ไม่ต้อง rebuild)
~~การ์ด Deal Poster บนหน้า Home~~ **ย้ายเป็นหน้าแยกแล้ว (27 ส.ค. 69)** — tile "Deal Poster" ในกลุ่มเครื่องมือ
เปิด `https://home.srv1277799.hstgr.cloud/dealposter.html` (แท็บใหม่ · basic-auth เดิมครอบอยู่)
หน้าใหม่มีครบ: รูปสินค้า (_tn), จัดกลุ่มสถานะ, ปุ่มอนุมัติ/ถอน/แคปชัน, แบ่งหน้า 50, refresh 120 วิ
`/api/dealposter` คืน `img` (property `รูป`) เพิ่มจากเดิม — ซอร์สหน้าอยู่ repo `home-console` ที่ `live/html/dealposter.html`

**อนุมัติดีลจากหน้าเว็บได้แล้ว (26 ส.ค. 69)** — ไม่ต้องเปิด Notion:
แถว "ใหม่/รอตรวจ" มีปุ่ม **✓ อนุมัติ** · แถว "อนุมัติแล้ว" มีปุ่ม **↩ ถอน** · ปุ่ม **แคปชัน** กางดูก่อนตัดสินใจ
หลังบ้านคือ `POST /api/dealposter/approve` body `{id,status}` ใน `home-metrics` → PATCH Notion ตรง
(whitelist 3 สถานะ · ไม่ใช่ POST = 405 · id/status ผิด = 400 · สำเร็จแล้วล้าง cache 60 วิทันที)
`/api/dealposter` เลยต้องคืน `id`,`caption`,`link` มาด้วย — อย่าลบออก หน้าเว็บใช้ `id` ยิง approve
ปลอดภัยด้วย basic-auth ของ traefik ที่ครอบ subdomain นี้อยู่แล้ว ไม่ได้เปิด endpoint สาธารณะเพิ่ม

## VPS (มี SSH key จากเครื่อง HP-AllInOne แล้ว — `ssh hostinger`)
key: `~/.ssh/id_ed25519_hostinger` (ed25519 ไม่มี passphrase) + alias ใน `~/.ssh/config` → `ssh hostinger '…'` · `scp hostinger:/path ./`
traefik `n8n-traefik-1` ใช้ **docker provider อย่างเดียว** (ไม่มี file provider) + `exposedbydefault=false` → subdomain ใหม่ต้องมี container ที่ติด label เอง;
DNS เป็น **wildcard** ทุก subdomain ชี้มา VPS อยู่แล้ว **ไม่ต้องเพิ่ม A record**; cert resolver ที่ใช้ทั้งเครื่อง = `mytlschallenge`
`deals-proxy` = nginx:alpine บน network `n8n_default` proxy ทุก path ไป `http://n8n:5678/webhook/deals`
**cache + gzip แล้ว 20 ก.ย. 69** — เดิมทุกคนที่เปิดหน้า = ยิง Notion ใหม่ทั้งชุด (5 requests ~4–5 วิ)
`proxy_cache` 10 นาที + `proxy_cache_key "deals-page"` เดียว (ทุก path คืนหน้าเดียวกัน · กันคนยิง `?x=random` ทำ cache บวม)
+ `proxy_cache_lock` (คนเปิดพร้อมกันตอนหมดอายุ ยิง Notion แค่คนเดียว) + `background_update`/`use_stale updating` (ต่ออายุเบื้องหลัง ไม่มีใครต้องรอ)
⚠️ ต้องมี `proxy_ignore_headers Cache-Control Expires Set-Cookie` ไม่งั้น header จาก n8n ทำให้ไม่ cache เลย
วัดจริง: **5.2 วิ → 0.21 วิ** (HIT) · **313 KB → 37 KB** ผ่านสาย (gzip) · ดู `X-Cache-Status` ใน response header ได้
· cache อยู่ในตัว container (ไม่ได้ทำ volume) → restart แล้วหายเป็นปกติ คนแรกที่เปิดสร้างใหม่ให้เอง
· ผลข้างเคียงที่ยอมรับ: ดีลที่เพิ่งโพสต์จะขึ้นหน้าเว็บช้าได้ถึง 10 นาที
(ไฟล์จริง `/root/deals-proxy/{nginx.conf,deploy.sh}` · backup ใน `vps/` ของ repo นี้ · **25 ก.ย. 69 เพิ่ม `location = /webhook/go` ไม่ cache** ดูหัวข้อหน้ารวมดีล 24 ก.ย.) — เลือกทำเป็น container แยก
เพื่อ **ไม่ต้องแตะหรือรีสตาร์ต container n8n** (n8n ล่ม = ทุก workflow ล่ม)
n8n เข้าถึงภายในได้ที่ `n8n:5678` (alias บน `n8n_default`) · Home Console live อยู่ `/root/home-console/html/index.html`

## เมื่อจบงานแต่ละครั้ง
export workflow **ทั้ง 8** → sanitize → commit + **push ทั้ง `origin` (GitLab) และ `github` (mirror)**;
เครื่องอื่นเริ่มงาน: `git pull origin main` ก่อนเสมอ
- **ใช้สคริปต์ `scripts/export_workflows.py`** (เพิ่ม 25 ก.ย. 69): ดึงทั้ง 8 ตัวจาก API → เก็บเฉพาะ `{name,nodes,connections,settings}` → แทน token ด้วย regex เป็น `REPLACE_*`
  → **ปฏิเสธเขียนไฟล์ถ้ายังเหลือสตริงหน้าตาเหมือน secret** · บน VPS: `set -a; . /root/home-metrics/.env; set +a; python3 scripts/export_workflows.py` · เครื่องอื่น: `N8N_KEY=… python3 scripts/export_workflows.py`
  ถ้ามี token รูปแบบใหม่เข้ามาในอนาคต (เช่น Azure/TikTok) ต้องเพิ่ม pattern ใน `SANITIZE` **และ** `LEAK` ทั้งคู่
- `git diff` หลัง export: diff ที่มีแต่ `availableInMCP`/ลำดับ key = format เฉย ๆ ไม่ต้องจด · diff ที่โหนดเพิ่ม/หาย/โค้ดเปลี่ยน = **มีคนแก้บน n8n โดยไม่จด → ต้องไล่ดูและจดลง CLAUDE.md** (เกิดแล้ว 7 ก.ย. และ 24 ก.ย. 69)
สแกน token ก่อน push ทุกครั้ง — `git log --all -p | grep -E` ไม่ใช่แค่ `git diff` เพราะ mirror พา**ทั้ง history**ไปด้วย

## เว็บดีลสาธารณะตัวใหม่ (26 ก.ย. 2569) — **https://paiyaadeals.com** (static site ไม่ผ่าน n8n ตอนคนเปิด)
**โดเมนจริง `paiyaadeals.com` จดที่ Hostinger 26 ก.ย. 69** (หมดอายุ 26 ก.ย. 70 · DNS zone ใน hPanel: A `@` → `72.62.248.226`, CNAME `www` → apex · ⚠️ user ยังไม่ได้เปิด auto-renew ตอนจด — เตือนก่อนหมดอายุ)
· traefik router `deals` รับ 3 โฮสต์ (ใบรับรองใบเดียว SAN ครบ) · nginx: `deals.srv1277799.hstgr.cloud` และ `www.` → **301** ไป `https://paiyaadeals.com$request_uri` (ลิงก์เก่า `/go?d=`/`/webhook/go` ยังใช้ได้) · `gen.py` `SITE` default = โดเมนใหม่ (canonical/og/sitemap/RSS)
· บทเรียน: เพิ่ม `server {}` ใหม่ใน nginx ต้องให้ block หลักมี **`default_server`** ไม่งั้น block ที่อยู่ก่อนกลายเป็น default (โดเมนเก่าเคย 301 ไปโดเมนที่ DNS ยังไม่ชี้ ~1 นาที) · ACME ล้มถ้า DNS ยังชี้ parking → recreate `deals-proxy` ให้ traefik ขอใหม่
แบบร่างที่ user อนุมัติ ("จัดไป"): Design canvas `https://claude.ai/artifact/EwwtwcNFiYKbcBwHhYSTQj` (หน้าแรกมือถือ / รายละเอียดดีล / เดสก์ท็อป / โครงสร้าง)
โทน: พื้นครีม `#FBF7F0` · ตัวอักษร `#23201C` · ราคา/CTA `#C63F1E` · ปุ่มสมัคร `#1F6E63` · Kanit (หัว/ราคา ตัวเดียวกับคลิป Reels) + Noto Sans Thai
- **โครง**: `/root/deals-site/gen.py` (ซอร์ส `vps/deals-site/`) ดึง Notion (สถานะ "โพสต์แล้ว" · `โพสต์เมื่อ` ≤ 90 วัน · ≤ 500 แถว) → เขียน HTML ลง `/root/deals-site/html/`
  ใช้เวลา ~3 วิ · **cron `*/10`** (`crontab -l | grep deals-site`, log `/root/deals-site/gen.log`) · container `deals-proxy` (nginx:alpine) เสิร์ฟไฟล์ตรง → ทุกหน้า ~40 ms (เดิม 3.4 วิตอน cache หมด)
  · deploy/สร้าง container ใหม่: `bash /root/deals-site/deploy.sh` · แก้แค่ nginx: แก้ `/root/deals-proxy/nginx.conf` แล้ว `docker exec deals-proxy sh -c 'nginx -t && nginx -s reload'`
- **หน้า**: `/` (ลดแรงวันนี้ = off ≥ 20% ใน 14 วัน top 6 · ดีลล่าสุด 48 ใบ + ปุ่ม "ดูดีลเพิ่ม" โหลด `/deals.json` ฝั่ง client · ค้นหาก็ใช้ไฟล์เดียวกัน) ·
  `/c/<beauty|home|fashion|gadget|food|auto|other>` หน้าหมวด · **`/d/<notion id ไม่มีขีด>` หน้าดีลรายชิ้น** (og:image + JSON-LD Product + ปุ่มแชร์ LINE/FB + ดีลคล้ายกัน) ·
  `/about` `/policy` `/sitemap.xml` `/rss.xml` `/robots.txt` · **ไม่มี `noindex` แล้ว** ตั้งใจให้ Google เก็บ
- **นับคลิก**: การ์ด/ปุ่มลิงก์ไป `/go?d=<id>` → nginx `map` จากไฟล์ `/root/deals-site/deals.map` (gen.py เขียนใหม่ทุกรอบ + reload nginx เฉพาะเมื่อเปลี่ยน) → 302 ไปลิงก์ affiliate
  · id เก่าแบบมีขีด (`/webhook/go?d=…` ที่เคยแชร์) ยังใช้ได้ (map มีทั้ง 2 แบบ) · id ไม่รู้จัก → หน้าแรก · **log `/root/deals-site/log/go.log`** (บันทึกเฉพาะ id ที่รู้จัก) · ดูสถิติ: `python3 /root/deals-site/gen.py stats`
  · สถิติเดิมใน n8n staticData (3 คลิก) ทิ้งไป
- ⛔ **บั๊กปุ่ม "ไปที่ร้าน" เด้งกลับหน้าแรก (พบ+แก้ 26 ก.ย. 69 21:05 น.)** — user เห็นหลายปุ่มกดแล้วไม่ไปร้าน · ยิงตรวจ `/go?d=` ทั้ง 454 id: พัง 12 = **ทุกดีลที่โพสต์หลัง 04:16 UTC** ของวันนั้น
  สาเหตุ: `deals.map` ถูก bind-mount **เป็นไฟล์เดี่ยว** แต่ `gen.py` เขียน `.tmp` แล้ว `os.replace` → inode ใหม่ · bind-mount ของไฟล์ผูกกับ inode เดิม → ในคอนเทนเนอร์เป็นไฟล์เก่าค้างตลอด (`nginx -s reload` ผ่านทุกรอบแต่โหลดของเก่า, `gen.log` ไม่มี error ให้เห็น) · เขียนทับในที่ (`cp`) ก็ไม่ช่วยเพราะ inode ที่ mount ถูก unlink ไปแล้ว
  แก้: map ย้ายไป **`/root/deals-site/map/deals.map`** และ mount **ทั้งโฟลเดอร์** (`-v $ROOT/map:/etc/nginx/map:ro`) · nginx.conf `include /etc/nginx/map/deals.map` · recreate ด้วย `deploy.sh` (ดาวน์ ~2 วิ) · ทดสอบบังคับ map เปลี่ยนแล้ว reload เห็นของใหม่จริง · ไฟล์เก่า `/root/deals-site/deals.map` ลบแล้ว
  **กฎ: bind-mount ไฟล์ที่มีคนเขียนแบบ atomic (tmp+rename) ไม่ได้ ต้อง mount โฟลเดอร์** (ใช้กับ nginx.conf ของ deals-proxy ด้วย — ตอนนี้แก้ด้วย editor ในที่จึงยังรอด แต่ถ้าวันไหนสคริปต์เขียนแบบ rename จะพังแบบเดียวกัน)
  ตรวจสุขภาพเร็ว ๆ: `grep -oE '^"[0-9a-f]{32}" "[^"]*"' /root/deals-site/map/deals.map` แล้ว curl `/go?d=<id>` ทุกตัว เทียบ `redirect_url` กับค่าใน map (สคริปต์อยู่ใน transcript 26 ก.ย.)
- **รูปสินค้าผ่านโดเมนเรา** `/img/s/<shopee seg>` และ `/img/l/<lazada path>` → nginx proxy + cache 14 วันใน `/root/deals-site/cache` → same-origin, เร็ว, และ **FB/LINE preview bot ดึง og:image ได้** (ดึงจาก Shopee CDN ตรงไม่ได้)
- **n8n `teJKfYg0xuG9OSfc` (Deal Landing Page) ไม่ถูกใช้จากโดเมน `deals.` แล้ว** — ยัง active อยู่ เข้าได้ทาง n8n ตรง (`/webhook/deals`, `/webhook/deals-stats`) เก็บไว้เป็น fallback ยังไม่ลบ
  · `/webhook/deals` บน `deals.` → 301 ไปหน้าแรก
- **แก้ดีไซน์**: แก้ `s.css`/template ใน `gen.py` ที่ repo → `cp` ไป `/root/deals-site/` → รัน `python3 /root/deals-site/gen.py` (CSS มี `?v=<hash>` cache-bust เอง) · ห้ามแก้ไฟล์ใน `html/` ตรง ๆ จะถูกทับใน 10 นาที
- ⚠️ ลิงก์ "เสนอดีล/ติดต่อ" ชี้ไปเพจ FB **ไม่ชี้ไปฟอร์ม intake** (ฟอร์มสร้างแถวสถานะ "ใหม่" ที่โพสต์อัตโนมัติ ถ้าเปิดสาธารณะ = ใครก็ยัดดีลลงเพจได้)
- **home. ใส่ basic-auth กลับแล้ว 26 ก.ย. 69** (ก่อนหน้านั้นเปิดสาธารณะทั้ง `home` และ `home-api` router มาระยะหนึ่ง — ปุ่มอนุมัติดีลใน `/dealposter.html` ยิงได้โดยไม่ต้อง login) ·
  `course.html` ยังสาธารณะผ่าน router `home-course` เหมือนเดิม · backup compose `docker-compose.home.yml.bak-20260926`

**ซ่อนดีลซ้ำจากเว็บ (26 ก.ย. 69)** — Notion เพิ่ม checkbox **`ซ่อนเว็บ`** · หน้า Deal Poster (`home./dealposter.html`) แถว "โพสต์แล้ว" มีปุ่ม **🚫 ซ่อนจากเว็บ / 👁 แสดงบนเว็บ**
→ `POST /api/dealposter/approve` รับ `{id, hide:true|false}` เพิ่ม (PATCH checkbox ไม่แตะสถานะ) · `gen.py` ข้ามแถวที่ติ๊ก + **dedupe อัตโนมัติ** (ลิงก์ affiliate เดียวกัน หรือชื่อเหมือนกัน → เก็บแถวใหม่สุด; รอบแรกตัดไป 48 จาก 500)
· ลบแถวใน Notion ก็หายจากเว็บเหมือนกัน (ภายใน 10 นาที) · server.js แก้ทั้ง 2 สำเนา + rebuild แล้ว · backup `server.js.bak-20260926`, `dealposter.html.bak-20260926`

**Google login แทน basic-auth ของ home. — ✅ เปิดใช้แล้ว 26 ก.ย. 69 09:50 UTC** (OAuth client อยู่หน้า Notion Config หัวข้อ "Google OAuth (home login" · ค่าอยู่ `/root/oauth2-proxy/.env`) — ซอร์ส `vps/oauth2-proxy/` · ของจริง `/root/oauth2-proxy/{docker-compose.yml,switch.sh,emails.txt,.env}`
- **2 ชั้น** (user สั่ง 26 ก.ย.): `home.` ทั้งหน้า = เฉพาะอีเมลใน `emails.txt` (**supachai.twr@gmail.com** — คนละอีเมลกับที่ใช้ใน Claude) ผ่าน container `oauth2-proxy` → middleware `google-auth` ·
  **`dp.srv1277799.hstgr.cloud`** = หน้า Deal Poster สำหรับคนอื่น login Google บัญชีไหนก็ได้ ผ่าน `oauth2-proxy-dp` → middleware `google-auth-dp` · เปิดได้แค่ `/dealposter.html` + `/hc-*` + `/api/dealposter*` (router `dp-page`/`dp-root`/`dp-api` ใน `docker-compose.home.yml`, `/` redirect ไป dealposter.html) path อื่น 404
  · cookie คนละชื่อ/คนละโดเมน (`_oauth2_home` @home. · `_oauth2_dp` @dp.) session ของคนอื่นใช้กับ home. ไม่ได้
- OAuth client **ใบเดียว** ใส่ redirect URI 2 อัน: `https://home.srv1277799.hstgr.cloud/oauth2/callback` และ `https://dp.srv1277799.hstgr.cloud/oauth2/callback` · consent screen ต้อง **Publish (In production)** ไม่งั้นบัญชีที่ไม่ใช่ test user ล็อกอิน dp. ไม่ได้ (scope แค่ email/profile ไม่ต้องผ่าน verification)
- ขั้นตอน: ใส่ `OAUTH2_PROXY_CLIENT_ID/SECRET` ใน `/root/oauth2-proxy/.env` → `bash /root/oauth2-proxy/switch.sh` (start proxy ทั้ง 2 → ตรวจ `/oauth2/auth`=401 และ `/oauth2/start`→google ทั้ง 2 โฮสต์ → ค่อยสลับ router `home`+`home-api` จาก `home-auth` เป็น `google-auth` + recreate) · ย้อนกลับ: `switch.sh rollback`
- ⚠️ ถ้า container oauth2-proxy ตายขณะ router ชี้ `google-auth` → traefik ปิด router = home. ไม่ตอบ (404) ให้ `switch.sh rollback` ชั่วคราว · label `dp-*` ใส่ในไฟล์ compose แล้วแต่จะมีผลตอน recreate ใน switch.sh (ก่อนหน้านั้น traefik log ว่าไม่พบ middleware `google-auth-dp` = ปกติ)
- คนอื่นที่ได้ dp. กดอนุมัติ/ถอน/ซ่อนดีลได้เท่ากับเจ้าของ (endpoint เดียวกัน) — ให้เฉพาะคนที่ไว้ใจ · จะจำกัดอีเมลทีหลัง: เปลี่ยน `OAUTH2_PROXY_EMAIL_DOMAINS: "*"` ของ `oauth2-proxy-dp` เป็น `AUTHENTICATED_EMAILS_FILE` แบบตัวแรก
- ทางเข้าเว็บ deals. จาก Home Console (26 ก.ย. 69): การ์ด **"เว็บดีลสาธารณะ"** ใน `index.html` (TILES) · ปุ่ม **🌐 เปิดเว็บดีล** บนหัวหน้า `dealposter.html` · ลิงก์ **เว็บ ↗** รายแถว (โพสต์แล้ว+ไม่ซ่อน) ไป `/d/<id ไม่มีขีด>` — ไฟล์ทั้งสองอยู่ใน repo `home-console` ซึ่ง **clone ไว้บน VPS แล้วที่ `/srv/claude/home-console`** (26 ก.ย. 69 · GitLab เท่านั้น ไม่มี GitHub mirror) แก้ live แล้ว `bash /srv/claude/home-console/sync.sh pull` → commit → push

**Home Console หน้าแรกใหม่ — ✅ ขึ้นแล้ว 26 ก.ย. 69** (ของเดิม `index.html.bak-20260926`, `hc-theme.css/js.bak-20260926`, `server.js.bak-20260926b`) · endpoint ใหม่ใน home-metrics: `/api/dealposter?summary=1` (queue/rounds/posted/hidden ไม่ส่ง items), `/api/dealsite` (อ่าน `/root/deals-site` ที่ mount ro เป็น `/dealsite` ใน compose: gen.log บรรทัดล่าสุด + นับ go.log), `/api/me` (อีเมลจาก header `X-Auth-Request-Email` ของ oauth2-proxy) · ธีมกลางเพิ่ม `paiyaa` เป็นค่าเริ่มต้น (ธีมเดิมยังเลือกได้จากปุ่ม 🎨) · Chart.js โหลดเฉพาะตอนกด "แสดงกราฟ" (จำสถานะใน localStorage `hc-chart-open`) · ค่าสมาชิกอ่าน `/data/subscriptions.json` ตรง เลิก iframe: แคนวาส `https://claude.ai/artifact/65Wi41NqV62XcwRYRUeYiz` · สเปกลงมือทำอยู่ repo home-console `docs/home-redesign-2026-09.md` (token เดียวกับ paiyaadeals.com, ตัด Chart.js/iframe ออกจากการโหลดแรก, Deal Poster+เว็บดีลขึ้นบนสุด, endpoint ใหม่ `/api/dealposter?summary=1` `/api/dealsite` `/api/me`)
