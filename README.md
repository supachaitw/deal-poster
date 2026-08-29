# Deal Poster — Shopee Affiliate Auto-Poster

ระบบโพสต์ดีล Shopee อัตโนมัติ: คัดดีล → AI เขียนแคปชัน → อนุมัติจากมือถือ → โพสต์ 3 แพลตฟอร์ม
ทั้งหมดรันบน n8n (`https://n8n.srv1277799.hstgr.cloud`) — repo นี้คือ backup ของ workflow (sanitized)

## ภาพรวม

```
ป้อนดีล (LINE / Telegram / เว็บฟอร์ม)
  └─ ดึงชื่อ+รูปจาก Shopee (og tags ผ่าน UA "TelegramBot") → แถวใน Notion Deal Queue
  └─ ราคาไม่ครบ → พิมพ์ "900 300" ตามในแชท → เติมแถวล่าสุดที่ราคาว่าง

ทุก 3 ชม. (9:00–21:00 Asia/Bangkok) — Deal Poster v1
  สาย A: สถานะ "ใหม่" → claude-haiku-4-5 เขียนแคปชัน → "รอตรวจ" → LINE preview (Paiyaa Bot)
  ผู้ใช้อนุมัติ: เปลี่ยนสถานะเป็น "อนุมัติแล้ว" ใน Notion
  สาย B: "อนุมัติแล้ว" → Telegram @paiyaa_deals (โหลดรูปเป็น binary แล้วอัปโหลด multipart —
          ส่ง URL ให้ Telegram ดึงเองไม่ได้เพราะ Shopee CDN บล็อก; ถ้ารูปพลาด fallback sendMessage)
          → X @SupachaiTW (ย่อ ≤280) → Threads @supachai_tw (2-step create/publish)
          → "โพสต์แล้ว" + timestamp → LINE ยืนยัน
```

## Workflows (`workflows/`)

| ไฟล์ | n8n id | หน้าที่ |
|---|---|---|
| `deal-poster-v1.json` | `E6i2xEAcaUsUFKWm` | ตัวหลัก: cron `0 9-21/3 * * *`, สาย A แคปชัน + สาย B โพสต์ 3 แพลตฟอร์ม |
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

DB `589f80403f534993b49fd9fdd4d292ff` — properties: สินค้า(title), ราคาเต็ม/ราคาลด(number),
ลิงก์Affiliate(url), หมวด(select: gadget/ความงาม/บ้าน/แฟชั่น/อื่นๆ),
สถานะ(select: ใหม่/รอตรวจ/อนุมัติแล้ว/โพสต์แล้ว), แคปชัน(rich_text), โพสต์เมื่อ(date)
ต้องแชร์ DB ให้ integration ผ่าน ⋯ → Connections

## Monitoring

การ์ด "🛒 Deal Poster" บน Home Console (`https://home.srv1277799.hstgr.cloud`) —
endpoint `/api/dealposter` ใน home-metrics (VPS `/docker/n8n/home/metrics/server.js`)
