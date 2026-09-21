# Deal Poster — Shopee Affiliate Auto-Poster

ระบบโพสต์ดีล Shopee/Lazada อัตโนมัติ: ป้อนดีล → AI เขียนแคปชัน + อนุมัติเอง → โพสต์ 4 ช่องทาง
(Telegram / Facebook / Instagram / Threads — X ปิดอยู่)
ทั้งหมดรันบน n8n (`https://n8n.srv1277799.hstgr.cloud`) — repo นี้คือ backup ของ workflow (sanitized)

## ภาพรวม

```
ป้อนดีล (LINE / Telegram / เว็บฟอร์ม)
  └─ ดึงชื่อ+รูปจาก Shopee (og tags ผ่าน UA "TelegramBot") → แถวใน Notion Deal Queue
  └─ ราคาไม่ครบ → พิมพ์ "900 300" ตามในแชท → เติมแถวล่าสุดที่ราคาว่าง

สาย A — Deal Caption Writer: :50 ของ 02/05/08/11/14/17/20/23 น. (Asia/Bangkok)
  สถานะ "ใหม่" → claude-haiku-4-5 เขียนแคปชัน+คำบรรยาย → ตั้ง "อนุมัติแล้ว" **อัตโนมัติ**
  (node `LINE Preview` ปิดอยู่ — ไม่มีขั้นให้คนกดอนุมัติแล้ว อนุมัติเองจากหน้าเว็บได้ถ้าต้องการ)

สาย B — Deal Poster v1: 00/06/09/12/15/18/21 น. (Asia/Bangkok, เว้นรอบตี 3) = 7 รอบ/วัน
  **เพดาน 6 ดีล/รอบ** (`Split Approved` ลงท้าย `.slice(0, 6)`) → สูงสุด 42 ดีล/วัน
  คิวยาวกว่านั้นไม่หาย แค่รอรอบถัดไป — Notion คืนเรียง last_edited เก่าก่อน (FIFO)
  "อนุมัติแล้ว" → Telegram @paiyaa_deals (โหลดรูปเป็น binary แล้วอัปโหลด multipart —
          ส่ง URL ให้ Telegram ดึงเองไม่ได้เพราะ Shopee CDN บล็อก; ถ้ารูปพลาด fallback sendMessage)
          → Facebook เพจ ป้ายยาดีลเด็ด (/photos multipart, ไม่มีรูป → /feed)
          → Instagram @paiyaa_deals (**Reels** เรนเดอร์จากรูป ถ้าล้ม/หมดงบเวลา → โพสต์ภาพ)
          → Threads @paiyaa_deals (create → Settle 30 วิ → publish, ยืมรูปจาก FB CDN)
          → [X ปิดอยู่ — บัญชีเป็น pay-per-use ยังไม่ได้ซื้อเครดิต]
          → "โพสต์แล้ว" + timestamp → LINE ยืนยัน
```

## Workflows (`workflows/`)

| ไฟล์ | n8n id | หน้าที่ |
|---|---|---|
| `deal-poster-v1.json` | `E6i2xEAcaUsUFKWm` | สายโพสต์: cron `0 0,6,9,12,15,18,21 * * *` (tz Asia/Bangkok) → Telegram/FB/IG/Threads · 6 ดีล/รอบ |
| `deal-caption-writer.json` | `e8aD2wCvsVYmefrq` | สายแคปชัน (แยกออกมาจากตัวหลัก): cron `50 2-23/3 * * *` → เขียนแคปชัน + ตั้งสถานะ "อนุมัติแล้ว" อัตโนมัติ |
| `deal-intake-form.json` | `Kq3cRuTbwF9cMkA1` | เว็บฟอร์ม `/form/deal-intake` → แถวใหม่สถานะ "ใหม่" |
| `deal-intake-telegram.json` | `JUE23JTCBbCsW1lS` | DM @sup_dealposter_bot: ลิงก์→og→Claude parse→แถว; ตัวเลข→เติมราคา |
| `deal-intake-line.json` | `731A7ASm8bI0F79B` | เหมือน Telegram แต่ผ่าน Paiyaa Bot (กรอง userId เจ้าของ) |
| `threads-token-keeper.json` | `UXGp6aS7EclTqCtl` | จันทร์ 07:00 refresh Threads token (60 วัน) แล้ว PUT กลับเข้า workflow หลัก |
| `deal-landing-page.json` | `teJKfYg0xuG9OSfc` | https://deals.srv1277799.hstgr.cloud (= `GET /webhook/deals`) → หน้ารวมดีลล่าสุด 30 รายการ สำหรับไบโอ Instagram |
| `tiktok-oauth-callback.json` | `qHcCduq7ec3an1zk` | `GET /webhook/tt-oauth-cb-k4w8` → หน้ารับ code ตอน TikTok creator authorize (Phase 0 ของ provider TikTok Shop) |

## Secrets (ถูกแทนที่เป็น placeholder ก่อน commit)

| Placeholder | ที่มา |
|---|---|
| `REPLACE_N8N_API_KEY` | หน้า Notion "🔐 Claude Daily Brief — Config" |
| `REPLACE_NOTION_TOKEN` | integration "GSBuniform Orders" (`ntn_…`) |
| `REPLACE_ANTHROPIC_API_KEY` | `sk-ant-…` (แชร์กับ workflow GSBuniform) |
| `REPLACE_LINE_CHANNEL_TOKEN` | LINE OA "Paiyaa Bot" @558klaxp — Developers Console → Messaging API |
| `REPLACE_TELEGRAM_BOT_TOKEN` | @sup_dealposter_bot (จาก @BotFather) |
| `REPLACE_THREADS_TOKEN` | Meta app "Paiyaa Poster" → Threads use case → User Token Generator |

X (Twitter) ไม่อยู่ใน JSON — เป็น n8n credential แยก (`twitterOAuth1Api`, ชื่อ "X Paiyaa (OAuth1)")

## Restore

1. Import JSON ทีละไฟล์เข้า n8n (หรือ `POST /api/v1/workflows`)
2. แทน placeholder ทุกตัวด้วยค่าจริง (string replace ใน nodes)
3. สร้าง X credential: `POST /api/v1/credentials` type `twitterOAuth1Api`
   body `{consumerKey, consumerSecret, oauthTokenData:{oauth_token, oauth_token_secret}}`
4. Activate — webhook/form node ที่สร้างผ่าน API ต้องมี `webhookId` (uuid) ใน node ไม่งั้น 404
5. Telegram: `setWebhook` → `…/webhook/deal-intake-tg-x7k2`; LINE: ใส่ webhook URL + เปิด Use webhook ใน console

## Notion Deal Queue

DB `589f80403f534993b49fd9fdd4d292ff` — properties: สินค้า(title), ราคาเต็ม/ราคาลด/คอม%(number),
ลิงก์Affiliate/ลิงก์ตะกร้า/รูป(url), TTProductId(rich_text),
หมวด(select: gadget/ความงาม/บ้าน/แฟชั่น/อาหาร/รถ/สัตว์เลี้ยง/Fitness/กาแฟ/อื่นๆ),
แหล่ง(select: shopee/lazada/tiktok), สถานะ(select: ใหม่/รอตรวจ/อนุมัติแล้ว/โพสต์แล้ว),
แคปชัน/คำบรรยาย(rich_text), โพสต์เมื่อ(date)
ต้องแชร์ DB ให้ integration ผ่าน ⋯ → Connections

⚠️ **`รูป` ถูกเขียนโดย `Mark Posted` ตอนโพสต์สำเร็จ** (เอา `photoUrl` ที่ `Build Post Body` ดึง og:image มา)
→ แถวที่ `รูป` ว่าง แปลว่า **ยังไม่ถูกโพสต์** ไม่ใช่ "ไม่มีรูปเลยโพสต์ไม่ได้" — อย่าไล่ผิดทาง
(ตรวจ 21 ก.ย. 69: รอบ 21:00 น. Notion คืนมา 10 แถว `รูป` ว่างทั้งหมด แล้ว 6 แถวแรกโพสต์ผ่านครบ)

## Monitoring

การ์ด "🛒 Deal Poster" บน Home Console (`https://home.srv1277799.hstgr.cloud`) —
endpoint `/api/dealposter` ใน home-metrics (VPS `/docker/n8n/home/metrics/server.js`)
