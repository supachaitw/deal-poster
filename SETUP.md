# เริ่มงาน Deal Poster จากเครื่องใหม่

เช็กลิสต์สำหรับย้ายเครื่อง/นั่งเครื่องอื่น — ทำครบแล้วทำงานต่อได้ทันทีเหมือนเครื่องเดิม
(อ่าน [CLAUDE.md](CLAUDE.md) ควบคู่ด้วย — ที่นั่นคือความรู้ทั้งหมดของระบบ ไฟล์นี้คือขั้นตอนติดตั้ง)

## สิ่งที่ **ไม่** ต้องทำ
- **ไม่ต้องติดตั้ง n8n / Node / Docker** — ทุก workflow รันบน VPS แก้ผ่าน public API ล้วน
- **ไม่ต้องย้าย token ของแพลตฟอร์ม** — ฝังอยู่ใน node บน n8n แล้ว (FB page token ไม่มีวันหมดอายุ, Threads มี keeper refresh ทุกจันทร์)
- **ไม่ต้อง copy private key ข้ามเครื่อง** — สร้างใหม่ต่อเครื่องปลอดภัยกว่า (ดูขั้นที่ 3)

## 1. Clone repo
```bash
git clone https://gitlab.com/supachai.taweerat/deal-poster.git
cd deal-poster
git config user.name "Supachai Taweerat"
git config user.email "supachai.taweerat@gmail.com"
```
- auth GitLab: ครั้งแรก Windows จะเด้ง Credential Manager ให้ล็อกอิน (หรือใช้ Personal Access Token แทนรหัสผ่าน)
- git identity **ไม่ได้ตั้ง global** ตั้งราย repo ทุกเครื่อง ไม่งั้น `git commit` จะ error "Author identity unknown"

## 2. n8n API key
อยู่หน้า Notion **"🔐 Claude Daily Brief — Config"** (ใต้ Password Manager) หัวข้อ `n8n API`
```bash
curl -H "X-N8N-API-KEY: <key>" https://n8n.srv1277799.hstgr.cloud/api/v1/workflows?limit=5
```
ได้ 200 = ใช้ได้ · ทุกการแก้ workflow ใช้คีย์นี้ตัวเดียว

## 3. SSH เข้า VPS (ถ้าต้องแตะ traefik / Home Console / deals-proxy)
สร้าง key ใหม่ของเครื่องนั้น แล้วฝากไว้ที่ VPS ครั้งเดียว — **ห้าม copy private key จากเครื่องเก่า**
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_hostinger -N '' -C "$(hostname)-claude@deal-poster"
ssh-copy-id -i ~/.ssh/id_ed25519_hostinger.pub root@srv1277799.hstgr.cloud
```
> ⚠️ รันใน **Git Bash** เท่านั้น (`C:\Program Files\Git\git-bash.exe`) — PowerShell กิน quote/`;` ทำคำสั่งพังแบบงง ๆ

แล้วเพิ่ม alias ใน `~/.ssh/config`:
```
Host hostinger
    HostName srv1277799.hstgr.cloud
    User root
    IdentityFile ~/.ssh/id_ed25519_hostinger
    IdentitiesOnly yes
```
ทดสอบ: `ssh hostinger 'hostname'` → ต้องได้ `srv1277799` โดยไม่ถามรหัส

## 4. Notion (ถ้าจะให้ Claude อ่าน/แก้คิวดีลได้เอง)
ต่อ Notion connector ในเครื่องนั้น แล้วใช้ Deal Queue DB `589f80403f534993b49fd9fdd4d292ff`
(ตัว workflow ใช้ integration token ของตัวเองอยู่แล้ว ส่วนนี้แค่ให้ผู้ช่วยเข้าถึงได้)

## 5. บอกผู้ช่วยให้อ่าน context
เปิด session ใหม่แล้วสั่ง: *"อ่าน CLAUDE.md กับ SETUP.md ใน repo นี้ก่อน แล้วสรุปสถานะระบบให้ฟัง"*

⚠️ **memory ของผู้ช่วยเป็นของแยกรายเครื่อง ไม่ตามมา** — ความรู้ที่ต้องข้ามเครื่องให้เขียนลง `CLAUDE.md` เสมอ (นี่คือเหตุผลที่ repo นี้มีอยู่)

---

## ทะเบียนบัญชี/ID ที่ใช้บ่อย
| อะไร | ค่า |
|---|---|
| n8n | `https://n8n.srv1277799.hstgr.cloud` |
| หน้ารวมดีล (ไบโอ IG) | `https://deals.srv1277799.hstgr.cloud` |
| ฟอร์มลงดีล | `https://n8n.srv1277799.hstgr.cloud/form/deal-intake` |
| Home Console | `https://home.srv1277799.hstgr.cloud` (basic-auth user `admin`) |
| Notion Deal Queue | `589f80403f534993b49fd9fdd4d292ff` |
| Telegram | ช่อง `@paiyaa_deals` · บอทรับดีล `@sup_dealposter_bot` |
| Facebook | เพจ ป้ายยาดีลเด็ด `1330886503433772` · แอป Paiyaa Pages `2350093015523231` |
| Instagram | `@paiyaa_deals` IG User id `17841440317177953` |
| Threads | `@paiyaa_deals` uid `28104225519212652` · แอป Paiyaa Poster `1730166771434587` |
| LINE OA | Paiyaa Bot `@558klaxp` |
| VPS | `root@srv1277799.hstgr.cloud` (Hostinger, มี browser terminal ใน hPanel เผื่อ ssh ใช้ไม่ได้) |

## ถ้า token พัง (เผื่อต้องออกใหม่)
- **Facebook / Instagram** — Access Token Tool → User Token ของแอป Paiyaa Pages → `GET /me/accounts` หรือ `GET /{page_id}?fields=access_token` ได้ page token ที่ไม่มีวันหมดอายุ
  ⚠️ token จาก **Graph API Explorer อายุ 1-2 ชม.** ใช้ฝังใน workflow ไม่ได้ · perms ต้องเพิ่มที่ **App → Use cases** ก่อนถึงจะติ๊กได้
- **Threads** — App Dashboard → Use cases → Access the Threads API → Settings → User Token Generator (บัญชีต้องเป็น Threads Tester และ **กดรับคำเชิญในแอป Threads** ก่อน)
- **Anthropic / Notion / LINE / Telegram** — ดูตาราง Secrets ใน [README.md](README.md)

## กติกาที่ทำให้ไม่พังข้ามเครื่อง
1. `git pull` ก่อนแตะไฟล์เสมอ · เสร็จเป็นชิ้น commit ทันที · push โดน reject → `git pull --rebase` **ห้าม force**
2. แก้ workflow ผ่าน API แล้วต้อง **deactivate→activate** ทุกครั้ง ไม่งั้น instance ที่รันอยู่ยังใช้ของเก่า
3. export → **sanitize เป็น `REPLACE_*`** → ค่อย commit · สแกน token ก่อน push ทุกครั้ง
4. เขียน jsCode/expression ผ่าน script ใช้ **String.raw** + ตรวจด้วย `new Function()` ก่อน deploy

## ค้างอยู่ (สำหรับคนที่มาต่อ)
- repo `home-console` มีงานค้างยังไม่ commit และ **`index.html` ตัว live บน VPS ยังไม่มีใน git** — ดึงกลับด้วย
  `scp hostinger:/root/home-console/html/index.html .` แล้ว commit (ถ้า container หายตอนนี้คือ deploy กลับไม่ได้)
- ดีล 8 รายการของวันที่ 24 ส.ค. ถูกมาร์ค "โพสต์แล้ว" ทั้งที่ Facebook/Instagram พลาด (บั๊ก newline) — ถ้าจะโพสต์ย้อนหลังต้องเปลี่ยนสถานะกลับเอง และจะซ้ำที่ Telegram/Threads
