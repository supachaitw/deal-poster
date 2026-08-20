# Deal Poster — คู่มือสำหรับ Claude (ทุกเครื่อง)

ระบบโพสต์ดีล Shopee/Lazada อัตโนมัติ รันบน n8n `https://n8n.srv1277799.hstgr.cloud` ทั้งหมด —
repo นี้เป็น **backup + จุดถ่ายทอดความรู้ระหว่างเครื่อง** ไม่ใช่ source ที่ deploy
(source of truth = workflow ใน n8n; แก้ผ่าน n8n public API แล้วค่อย export กลับมา commit)

## กติกาเหล็ก
- **ห้าม print token/secret ลง output หรือ commit ลง repo** — ใช้ใน script เท่านั้น, ไฟล์ใน `workflows/` ต้อง sanitize เป็น `REPLACE_*` ก่อน commit เสมอ (ดู pattern ใน git log)
- n8n API key อยู่หน้า Notion **"🔐 Claude Daily Brief — Config"** — ดึงจากที่นั่น อย่า hardcode ที่อื่น
- แก้ workflow ผ่าน API: `PUT /api/v1/workflows/{id}` รับเฉพาะ `{name,nodes,connections,settings}` แล้วต้อง **deactivate→activate** ทุกครั้ง
- เขียน jsCode ของ Code node ผ่าน script ต้องใช้ **String.raw** (เคยพัง: backslash ใน regex หาย ทำให้ทุกรอบ error + โพสต์ซ้ำ)
- ตอบผู้ใช้เป็นภาษาไทย โค้ด/คำสั่งเป็นอังกฤษ

## Workflows (n8n IDs)
| id | ชื่อ | หน้าที่ |
|---|---|---|
| `E6i2xEAcaUsUFKWm` | Deal Poster v1 | cron `0 9-21/3 * * *` Asia/Bangkok — สาย A: Notion "ใหม่"→Claude แคปชัน→"รอตรวจ"→LINE preview; สาย B: "อนุมัติแล้ว"→Telegram(รูป binary)→[X ปิดอยู่]→Threads(2-step)→Mark Posted→LINE |
| `Kq3cRuTbwF9cMkA1` | Deal Intake Form | `/form/deal-intake` |
| `JUE23JTCBbCsW1lS` | Deal Intake Telegram | webhook `deal-intake-tg-x7k2`, บอท @sup_dealposter_bot |
| `731A7ASm8bI0F79B` | Deal Intake LINE | webhook `deal-intake-line-p9m4`, LINE OA "Paiyaa Bot" @558klaxp |
| `UXGp6aS7EclTqCtl` | Threads Token Keeper | จันทร์ 07:00 refresh token 60 วัน แล้ว PUT กลับ |

Notion Deal Queue DB `589f80403f534993b49fd9fdd4d292ff` — สถานะ: ใหม่→รอตรวจ→อนุมัติแล้ว→โพสต์แล้ว
(กติกา: แคปชันเขียนเฉพาะรอบสถานะ "ใหม่"; price-reply เติมเฉพาะแถวที่ราคาลดว่าง)

## สถานะแพลตฟอร์ม (19 ส.ค. 2569)
- **Telegram** `@paiyaa_deals` ✅ — sendPhoto ต้องโหลดรูปเป็น binary แล้ว upload multipart (ส่ง URL ให้ Telegram ดึงเองไม่ได้ Shopee/Lazada CDN บล็อก); Lazada บางรูป `IMAGE_PROCESS_FAILED` → fallback sendMessage ทำงานอยู่
- **Threads** `@supachai_tw` (uid 28066415776320239) ✅ — Meta app "Paiyaa Poster" (1730166771434587), token THAA ฝังใน node, keeper refresh อัตโนมัติ
- **X** ⏸ node "Post to X" `disabled:true` — X เป็น pay-per-use credits แล้ว บัญชี $0 user ยังไม่ซื้อ; node เป็น httpRequest + predefinedCredentialType `twitterOAuth1Api` (twitter node v2 ใช้ OAuth1 ไม่ได้), credential n8n `TsrgrCQlMXmi03F9`
- **Facebook** 🔜 — restriction ปลดแล้ว (21 ส.ค. 2569). **เพจเป้าหมายคือ `ป้ายยาดีลเด็ด` เท่านั้น** (บัญชีมี 3 เพจ: ป้ายยาดีลเด็ด / EVE / G.S.B.Uniform — อีกสองอันไม่เกี่ยว; `Paiyaa` ไม่ใช่เพจ เป็น business portfolio 1709298406839669 ซึ่ง **เลิกใช้แล้ว**)
  - **ต้นตอที่ติดมานาน**: perms ของ Pages ไม่ได้อยู่ที่ Login config แต่อยู่ที่ **App → Use cases → Manage Pages → Permissions** → กด Add ที่นั่น (`pages_manage_posts` + `pages_read_engagement` = Ready for testing แล้ว, `pages_show_list` มีอยู่เดิม) → จากนั้น Graph API Explorer จะเห็น perms ครบ
  - เส้นทางที่ใช้: **user token → page token** ของแอป "Paiyaa Pages" (2350093015523231) — dev mode ใช้ได้เพราะ user เป็น admin ทั้งแอปและเพจ **ไม่ต้องใช้ portfolio / system user / App Review**
  - เหลือ: user กด Generate Access Token + Get Page Access Token (ป้ายยาดีลเด็ด) → copy → แลก long-lived → เพิ่ม node "Post to Facebook" (`POST /{page_id}/photos` หรือ `/feed`) ต่อจาก Post to Telegram
- **บทเรียน Meta:** งานสร้างบัญชี/portfolio/appeal ต้องให้ user คลิกเอง (automation โดนแฟล็กมาแล้ว); งาน Graph API ปกติไม่โดน

## Monitoring
การ์ด "🛒 Deal Poster" บน Home Console `https://home.srv1277799.hstgr.cloud` —
endpoint `/api/dealposter` ใน home-metrics (VPS `/docker/n8n/home/metrics/server.js`);
Home Console มี 2 ซอร์ส: `/root/home-console/html/` (ตัว live, deploy ด้วย docker cp) และ `/docker/n8n/home/` — แก้ต้องแก้ทั้งคู่

## เมื่อจบงานแต่ละครั้ง
export workflow ทั้ง 5 → sanitize → commit + push (ดู scripts เดิมใน session/README);
เครื่องอื่นเริ่มงาน: `git pull` ก่อนเสมอ
