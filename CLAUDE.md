# Deal Poster — คู่มือสำหรับ Claude (ทุกเครื่อง)

ระบบโพสต์ดีล Shopee/Lazada อัตโนมัติ รันบน n8n `https://n8n.srv1277799.hstgr.cloud` ทั้งหมด —
repo นี้เป็น **backup + จุดถ่ายทอดความรู้ระหว่างเครื่อง** ไม่ใช่ source ที่ deploy
(source of truth = workflow ใน n8n; แก้ผ่าน n8n public API แล้วค่อย export กลับมา commit)

## กติกาเหล็ก
- **git ทุก session ทุกเครื่อง**: `git pull origin dev` (หรือ main) ก่อนแตะไฟล์เสมอ ·
  `git status` ไม่สะอาดและไม่ใช่ของตัวเอง = หยุดถามก่อน ห้าม commit ทับ ·
  เสร็จเป็นชิ้นให้ commit ทันที อย่าค้าง working tree ข้ามวัน ·
  push โดน reject → `git pull --rebase` แล้ว push ใหม่ **ห้าม force push**
  (กฎชุดนี้มาจากบทเรียน expense-bot ที่ session แก้จากไฟล์เก่าแล้วทับฟีเจอร์หาย 2 รอบ)
- **ห้าม print token/secret ลง output หรือ commit ลง repo** — ใช้ใน script เท่านั้น, ไฟล์ใน `workflows/` ต้อง sanitize เป็น `REPLACE_*` ก่อน commit เสมอ (ดู pattern ใน git log)
- n8n API key อยู่หน้า Notion **"🔐 Claude Daily Brief — Config"** — ดึงจากที่นั่น อย่า hardcode ที่อื่น
- แก้ workflow ผ่าน API: `PUT /api/v1/workflows/{id}` รับเฉพาะ `{name,nodes,connections,settings}` แล้วต้อง **deactivate→activate** ทุกครั้ง
- เขียน jsCode/expression ผ่าน script ต้องใช้ **String.raw** — ระวัง **newline จริงในสตริง JS** ของ expression ด้วย (n8n ตอบ `{"error":"invalid syntax"}` ทั้ง node หาสาเหตุยากมาก) ใช้ `
` แบบ escape เท่านั้น
- (เดิม) เขียน jsCode ของ Code node ผ่าน script ต้องใช้ **String.raw** (เคยพัง: backslash ใน regex หาย ทำให้ทุกรอบ error + โพสต์ซ้ำ)
- ตอบผู้ใช้เป็นภาษาไทย โค้ด/คำสั่งเป็นอังกฤษ

## Workflows (n8n IDs)
| id | ชื่อ | หน้าที่ |
|---|---|---|
| `E6i2xEAcaUsUFKWm` | Deal Poster v1 | cron `0 9-21/3 * * *` Asia/Bangkok — สาย A: Notion "ใหม่"→Claude แคปชัน→"รอตรวจ"→LINE preview; สาย B: "อนุมัติแล้ว"→Telegram(รูป binary)→[X ปิดอยู่]→Threads(2-step)→Mark Posted→**Build Posted Alert**→LINE (แจ้งผลรายช่อง TG/FB/Threads ทีละดีล) |
| `Kq3cRuTbwF9cMkA1` | Deal Intake Form | `/form/deal-intake` — บังคับแค่ลิงก์ ช่องอื่นเว้นได้ (OG+Claude parse เหมือนสาย TG; ค่าที่กรอกชนะค่า parse) |
| `JUE23JTCBbCsW1lS` | Deal Intake Telegram | webhook `deal-intake-tg-x7k2`, บอท @sup_dealposter_bot |
| `731A7ASm8bI0F79B` | Deal Intake LINE | webhook `deal-intake-line-p9m4`, LINE OA "Paiyaa Bot" @558klaxp |
| `UXGp6aS7EclTqCtl` | Threads Token Keeper | จันทร์ 07:00 refresh token 60 วัน แล้ว PUT กลับ |
| `teJKfYg0xuG9OSfc` | Deal Landing Page | `https://deals.srv1277799.hstgr.cloud` (= `GET /webhook/deals`) — หน้า HTML รวมดีล 30 อันล่าสุด ดึง Notion สด สำหรับใส่ไบโอ IG |

Notion Deal Queue DB `589f80403f534993b49fd9fdd4d292ff` — สถานะ: ใหม่→รอตรวจ→อนุมัติแล้ว→โพสต์แล้ว
(กติกา: แคปชันเขียนเฉพาะรอบสถานะ "ใหม่"; price-reply เติมเฉพาะแถวที่ราคาลดว่าง)

## สถานะแพลตฟอร์ม (22 ส.ค. 2569)
- **Telegram** `@paiyaa_deals` ✅ — sendPhoto ต้องโหลดรูปเป็น binary แล้ว upload multipart (ส่ง URL ให้ Telegram ดึงเองไม่ได้ Shopee/Lazada CDN บล็อก); Lazada บางรูป `IMAGE_PROCESS_FAILED` → fallback sendMessage ทำงานอยู่
- **Facebook** ✅ (22 ส.ค. 2569) — เพจ **ป้ายยาดีลเด็ด** page_id `1330886503433772`, แอป "Paiyaa Pages" (2350093015523231)
  - สาย FB แตกขนานจาก `Fetch Photo Bin` (คู่กับ Telegram): `Post to Facebook` (`POST /{page_id}/photos` multipart binary) → `FB Verify` → `FB Need Text?` → `FB Send Feed` (`POST /{page_id}/feed` message+link) — batching 60 วิทั้งคู่
  - **page token เป็นแบบ NEVER expires** (derive จาก long-lived user token) ฝังใน node — **ไม่ต้องมี token keeper**
  - วิธีได้ token (เผื่อทำใหม่): Access Token Tool ลิงก์ "need to grant permissions" ให้แค่ `public_profile` → ต้องไป Graph API Explorer → Add a Permission (`pages_show_list`+`pages_manage_posts`+`pages_read_engagement`) → Generate ใหม่ → perms ผูกกับคู่ user+app ดังนั้น token เดิมได้ scope เพิ่มเองด้วย → `GET /me/accounts` ได้ page token
  - (บัญชีมี 3 เพจ: ป้ายยาดีลเด็ด / EVE / G.S.B.Uniform — อีกสองอันไม่เกี่ยว; `Paiyaa` ไม่ใช่เพจ เป็น business portfolio ที่เลิกใช้แล้ว)
- **Instagram** `@paiyaa_deals` ✅ (24 ส.ค. 2569) — IG User id `17841440317177953` บัญชี **Business ผูกกับเพจ ป้ายยาดีลเด็ด**
  - เพจ FB ผูก IG ได้**บัญชีเดียว** → พอผูกตัวใหม่ `supachai_tw` (ส่วนตัว) หลุดออกเอง ไม่ต้องไปไล่ปลดที่ Business users (หน้านั้นติด enterprise permission กดไม่ได้อยู่แล้ว)
  - สาย IG แตกจาก `FB Photo URL`: `Build IG Caption` → `IG Has Image?` → `IG Create Media` (`POST /{ig}/media`) → `IG Publish` (`POST /{ig}/media_publish`) — 2-step เหมือน Threads, batching 60 วิ, ใช้รูปจาก FB CDN
  - **IG โพสต์ข้อความล้วนไม่ได้ ต้องมีรูปเสมอ** → ไม่มีรูป = ข้ามช่องนี้ (ไม่มี fallback แบบ TG/FB)
  - แคปชัน IG ต่างจากช่องอื่น: **ตัดบรรทัดที่มี http ออก** (IG ไม่ทำลิงก์ในแคปชันให้กดได้ — ข้อจำกัดแพลตฟอร์ม แก้ฝั่งเราไม่ได้) แทนด้วย "ลิงก์ในไบโอ" + แฮชแท็ก; ไบโอชี้ไป `https://deals.srv1277799.hstgr.cloud`
  - perms ฝั่ง IG ติด**กับดักเดียวกับ Pages**: ต้องเพิ่ม `instagram_basic` + `instagram_content_publish` ที่ **App → Use cases** ก่อน Graph API Explorer ถึงจะเห็นให้ติ๊ก
  - **token ต้องเอาจาก Access Token Tool เท่านั้น** (ออก long-lived 60 วัน → derive page token ได้แบบ never-expire) — ตัวจาก **Graph API Explorer เป็น short-lived 1-2 ชม.** page token ที่ derive ต่อก็อายุสั้นตาม; และ "App Token" ที่โชว์ในหน้านั้น **ไม่ใช่ app secret** เอาไปแลก `fb_exchange_token` ไม่ได้ (`Error validating client secret`)
- **Threads** `@supachai_tw` (uid 28066415776320239) ✅ กลับมาโพสต์ได้ 23 ส.ค. (เคยโดน "API access blocked" ระดับแอป 21–23 ส.ค. หลังยิง 7 โพสต์ใน 1 นาที → แก้ด้วย throttle 3 ดีล/รอบ + 60 วิ/โพสต์)
  - **รูปต้องส่งเป็น image_url ให้ Meta ไปดึงเอง อัปโหลด binary ไม่ได้** → Shopee/Lazada CDN บล็อก fetcher ของ Meta (`error_subcode 2207052 Media download has failed`) จึงต้อง**ยืมรูปที่อัปขึ้น FB แล้ว** (scontent CDN) ผ่าน node `FB Photo URL`
  - ⚠️ ยังอยู่บนบัญชี**ส่วนตัว** — ถ้าจะย้ายไป `@paiyaa_deals` ต้องเปิด Threads ของ IG ตัวใหม่ + ขอ token ใหม่ (ผู้ติดตามเริ่มจาก 0 โพสต์เก่าย้ายไม่ได้)
- **Instagram** (ทางอ้อม) — เพจ FB เปิด cross-post ไป IG `supachai_tw` อัตโนมัติ **เราไม่มี node IG** ; IG ไม่ทำลิงก์ในแคปชันให้กดได้ (ข้อจำกัดแพลตฟอร์ม) → แก้ด้วยหน้า `/webhook/deals` ใส่ไบโอ + ต่อท้ายแคปชันเฉพาะฝั่ง FB/IG
- **X** ⏸ node "Post to X" `disabled:true` — X เป็น pay-per-use credits แล้ว บัญชี $0 user ยังไม่ซื้อ; node เป็น httpRequest + predefinedCredentialType `twitterOAuth1Api` (twitter node v2 ใช้ OAuth1 ไม่ได้), credential n8n `TsrgrCQlMXmi03F9`
- **บทเรียน Meta:** งานสร้างบัญชี/portfolio/appeal ต้องให้ user คลิกเอง (automation โดนแฟล็กมาแล้ว); งาน Graph API ปกติไม่โดน

## Monitoring
การ์ด "🛒 Deal Poster" บน Home Console `https://home.srv1277799.hstgr.cloud` (traefik basic-auth, user `admin`) —
endpoint `/api/dealposter` ใน container **`home-metrics`**; **ซอร์สตัวจริงคือ `/root/home-metrics/server.js`**
(ไฟล์ `/docker/n8n/home/metrics/server.js` เป็นของเก่าคนละตัว — เคยหลงมาแล้ว 23 ส.ค. 69)
ตัว endpoint วน `start_cursor` ดึง Notion ได้ถึง 5×100 แถว ส่งกลับ `items` ครบทุกสถานะ + `queue` + `rounds` (cache 60 วิ)
หน้าเว็บ: Home Console มี 2 ซอร์ส — `/root/home-console/html/index.html` (**ตัว live**) กับ `/docker/n8n/home/index.html` (ของเก่า ธีมมืด) — แก้ต้องแก้ทั้งคู่
deploy หน้าเว็บ: `scp` ทับ `/root/home-console/html/index.html` แล้ว
`docker cp /root/home-console/html/index.html home-console:/usr/share/nginx/html/index.html` (ไม่ต้อง rebuild)
การ์ด Deal Poster แบ่งหน้า 50 รายการ/หน้า มีปุ่มย้อนหลัง/ถัดไป (23 ส.ค. 69) — แบ่งฝั่ง client ล้วน ไม่แตะ API

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
