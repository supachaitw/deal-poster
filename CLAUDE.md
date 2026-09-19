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
| `E6i2xEAcaUsUFKWm` | Deal Poster v1 — โพสต์ดีลที่อนุมัติแล้ว | cron `0 0,6,9,12,15,18,21 * * *` — **สาย B อย่างเดียว**: "อนุมัติแล้ว"→Telegram(รูป binary)+FB→IG(**Reels** ถอยเป็นภาพได้)/Threads(create→**Settle 30 วิ**→publish)→[X ปิดอยู่]→Mark Posted→**Build Posted Alert**→LINE |
| `e8aD2wCvsVYmefrq` | Deal Caption Writer | cron `50 2-23/3 * * *` — **สาย A ที่แยกออกมา**: "ใหม่"→Claude แคปชัน→`Save Draft to Notion`→LINE preview |
| `Kq3cRuTbwF9cMkA1` | Deal Intake Form | `/form/deal-intake` — บังคับแค่ลิงก์ ช่องอื่นเว้นได้ (OG+Claude parse เหมือนสาย TG; ค่าที่กรอกชนะค่า parse) |
| `JUE23JTCBbCsW1lS` | Deal Intake Telegram | webhook `deal-intake-tg-x7k2`, บอท @sup_dealposter_bot |
| `731A7ASm8bI0F79B` | Deal Intake LINE | webhook `deal-intake-line-p9m4`, LINE OA "Paiyaa Bot" @558klaxp |
| `UXGp6aS7EclTqCtl` | Threads Token Keeper | จันทร์ 07:00 refresh token 60 วัน แล้ว PUT กลับ |
| `teJKfYg0xuG9OSfc` | Deal Landing Page | `https://deals.srv1277799.hstgr.cloud` (= `GET /webhook/deals`) — หน้า HTML รวมดีล ดึง Notion สด สำหรับใส่ไบโอ IG · **มีรูปสินค้า + แบ่งหน้าละ 50 (27 ส.ค. 69)** |
| `qHcCduq7ec3an1zk` | TikTok OAuth Callback | `GET /webhook/tt-oauth-cb-k4w8` — หน้ารับ `code`+`state` ตอน creator authorize แล้วให้ user copy ส่งให้ Claude (สร้าง 29 ส.ค. 69 รอใช้ใน Phase 0 TikTok) |

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
**ผลต่อการทดสอบ: ห้ามสร้างแถวทดสอบที่สถานะ "ใหม่" เด็ดขาด** (จะหลุดไปโพสต์ลงเพจจริง) — ทดสอบให้ลงที่ "รอตรวจ" เท่านั้น

Notion Deal Queue DB `589f80403f534993b49fd9fdd4d292ff` — สถานะ: ใหม่→(รอตรวจ)→อนุมัติแล้ว→โพสต์แล้ว
(กติกา: แคปชันเขียนเฉพาะรอบสถานะ "ใหม่"; price-reply เติมแถวที่ราคาลดว่าง สถานะ "ใหม่" หรือ "รอตรวจ")

**ราคาไม่ครบ ≠ บล็อกการโพสต์** (24 ส.ค. 69 — สินค้าบางตัวไม่มีราคาลด):
- intake ทั้ง 3 ทาง: `complete = !!name` (เดิม `!!(name && sale)`) → มีชื่อก็เข้าสถานะ "ใหม่" ได้เลย
- `Claude Write Caption`: ไม่มีราคา → สั่ง "ห้ามกล่าวถึงราคาหรือส่วนลดใด ๆ" (เดิมส่ง `null` เข้า prompt ตรง ๆ)
- `Build Caption` / `Split Approved`: มีทั้ง sale+full → `💥 เหลือ X (ลด Y%)` · มีแค่ sale → `💥 เหลือ X` · มีแค่ full → `💰 ราคา X` · ไม่มีเลย → ไม่มีบรรทัดราคา
- `Split Approved` สร้างแคปชันขั้นต่ำให้เองถ้าช่องแคปชันว่าง — **"อนุมัติแล้ว" = ต้องโพสต์เสมอ** (เดิม `.filter(i => i.json.caption)` ทิ้งเงียบ ๆ)

## Token / Credential (28 ส.ค. 2569)
- **Notion token ไม่ฝังใน workflow แล้ว** — ย้ายเข้า n8n credential **`Notion Deal Poster (Header Auth)`** (id `U5mfqJ7z2OV1c4PT`, type httpHeaderAuth) ครบทั้ง 12 จุดใน 5 workflow
  - Landing Page: โหนด `Query Posted Deals` แปลงจาก Code (fetch วนหน้า) → httpRequest ใช้ credential ดึงหน้าเดียว `page_size: 100` เรียงใหม่สุดก่อน — เทียบ HTML ก่อน/หลังแล้ว **byte-identical** (หน้า live แสดง 100 รายการล่าสุดเท่าเดิม)
  - **rotate Notion token**: สร้าง secret ใหม่ที่ notion.so/profile/integrations → แก้ค่าใน credential เดียวผ่าน n8n UI (Credentials → Notion Deal Poster) — ไม่ต้องแตะ workflow ใดเลย
- **Telegram bot token ยังฝังใน URL** (4 โหนด: `Post to Telegram`/`TG Send Text` ใน Poster, `TG Confirm`/`TG Help` ใน Intake TG) — **ย้ายเข้า credential ไม่ได้**: token อยู่ใน URL path ซึ่ง generic credential ของ n8n ฉีดให้ไม่ได้ และเปลี่ยนเป็น Telegram node จะเสีย batching 60 วิ (throttle ที่ตั้งใจ)
  - **rotate Telegram token**: BotFather → `/revoke` @sup_dealposter_bot ได้ token ใหม่ → GET สด 2 workflow (`E6i2xEAcaUsUFKWm`, `JUE23JTCBbCsW1lS`) → replace string `bot<เก่า>` → `bot<ใหม่>` → PUT + deactivate→activate
- ที่ยังฝังโดยตั้งใจ: FB page token (never-expire), Threads (Token Keeper หา token ด้วย regex จาก workflow — **ห้ามย้าย**), Anthropic key + LINE channel token (ยังฝัง — ผู้สมัครรอบถัดไปถ้าจะย้ายเพิ่ม ทำแบบเดียวกับ Notion ได้เพราะเป็น header ทั้งคู่)

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
ตัว endpoint วน `start_cursor` ดึง Notion ได้ถึง 5×100 แถว ส่งกลับ `items` ครบทุกสถานะ + `queue` + `rounds` (cache 60 วิ)
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
(ไฟล์จริง `/root/deals-proxy/{nginx.conf,deploy.sh}` · backup ใน `vps/` ของ repo นี้) — เลือกทำเป็น container แยก
เพื่อ **ไม่ต้องแตะหรือรีสตาร์ต container n8n** (n8n ล่ม = ทุก workflow ล่ม)
n8n เข้าถึงภายในได้ที่ `n8n:5678` (alias บน `n8n_default`) · Home Console live อยู่ `/root/home-console/html/index.html`

## เมื่อจบงานแต่ละครั้ง
export workflow ทั้ง 5 → sanitize → commit + push (ดู scripts เดิมใน session/README);
เครื่องอื่นเริ่มงาน: `git pull` ก่อนเสมอ
