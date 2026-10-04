---
name: tiktok-analyze
description: วิเคราะห์คลิป TikTok หรือ Instagram Reel จากลิงก์ที่ user ส่งมา (ดาวน์โหลด ถอดเสียง/ข้อความบนจอ แยกโครง Hook/Promise/Body/Open loop/CTA เทคนิคตัดต่อ) แล้วเทียบกับคลิปดีลของเราและเสนอว่าจะเอาอะไรมาปรับใช้ใน deal-video · ใช้เมื่อ user ส่งลิงก์ vt.tiktok.com / tiktok.com / instagram.com/reel และพูดว่า "วิเคราะห์" "ดูให้หน่อย" "น่าสนใจ" "เค้าทำยังไง"
---

# วิเคราะห์คลิป TikTok แล้วปรับใช้กับคลิปดีล

## ขั้นตอน (บน VPS, cwd = /srv/claude/deal-poster)
1. `sh scripts/tt_analyze.sh "<ลิงก์>" ["คำถามเพิ่ม"]` → ได้ผู้โพสต์/ความยาว/คำบรรยาย + `/tmp/tt_an/tile.jpg` (เฟรมทุก 6 วิ) + บทวิเคราะห์จาก Gemini 2.5 Flash (ถอดคำพูด+ข้อความบนจอตามเวลา, เทคนิค, โครงตัดต่อ, โครง Hook/Promise/Body/Open loop/CTA)
   - key Gemini อยู่ใน container `deal-video` เท่านั้น สคริปต์ไม่พิมพ์ key · ไฟล์วิดีโอชั่วคราวใน `/tiktok` ถูกลบท้ายสคริปต์
   - **Instagram**: หน้า HTML ตรง ๆ เป็น shell ล็อกอิน (ไม่มี video_url) → สคริปต์ใช้ `docker run zenika/alpine-chrome --dump-dom` เปิด `/reel/<code>/embed/captioned/` แล้วอ่าน `<video src>` (ผ่าน 4 ต.ค. 69 กับ Reel สาธารณะ) · โพสต์ส่วนตัว/รูปภาพ = ขอไฟล์จาก user
   - `docker exec` ที่ป้อน python ทาง heredoc ต้องมี `-i` ไม่งั้นสคริปต์เงียบไม่มี output (พลาดแล้ว 4 ต.ค. 69)
   - ลิงก์สั้น `vt.tiktok.com` ถูก resolve ให้เอง · ถ้าไม่มี `playAddr` (slideshow/ต้องล็อกอิน) ให้ขอ user ส่งไฟล์มาทาง Telegram แล้วดึงด้วย `getFile` ตามวิธีในหัวข้อ Veo ของ CLAUDE.md
2. เปิด `tile.jpg` ด้วย Read ดูจริงว่าเฟรมตรงกับที่ Gemini บรรยาย (Gemini บางครั้งเดาสิ่งที่ไม่มีในภาพ)
3. ถ้าคลิปเป็น **สอนเทคนิค AI/วิดีโอ** → ทดสอบเทคนิคนั้นผ่าน API ของเราก่อนสรุป (Gemini image / Veo ผ่าน `docker exec deal-video python3 -c …` ใช้ `veo_test:true`/`storyboard_test:true` ไม่กินโควตา) · ถ้าเป็น **โครงเรื่อง/บทพูด** → เทียบกับท่อนพากย์ปัจจุบันใน `server.py` (`script_for`: hook → promise → desc → loop → old → new → cta) และ `/root/deal-video/tiktok/script_style.txt`
4. ตอบ user เป็นไทย: (ก) คลิปสอนอะไร 3–6 ข้อ (ข) ตารางเทียบ "ท่อนตามสูตร / ของเรา / ช่องว่าง" (ค) ข้อเสนอปรับที่แก้ได้จริง ระบุไฟล์/จุด (บท = prompt ใน `llm_script` + pool + `script_style.txt` · จอ = ASS events ใน `render()` · ภาพ = `veo_prompt_for`/`storyboard_prompt_for`) และผลต่อความยาวคลิป/ต้นทุน · **อย่าแก้จนกว่า user สั่ง** ("ลองปรับใช้" = ทำได้เลยกับดีลใหม่)
5. เมื่อแก้แล้ว: ทดสอบ render จริงในคอนเทนเนอร์ (ไม่ส่ง tiktok/fb_reel) → ดูเฟรม → deploy ตาม gate (running=0, นอก xx:00–xx:25 ของชั่วโมงรอบ) → `sample.sh` → commit · จดสรุปเทคนิค+ผลลงหัวข้อที่เกี่ยวใน CLAUDE.md (เทรนด์/บทพูดอยู่ตาราง "บันทึกการปรับเสียง" · ภาพอยู่หัวข้อ Veo)

## กรอบวิเคราะห์โครงคลิปสั้น (จาก @itshowardwang 3 ต.ค. 69 + กติกาของเรา)
| ท่อน | หน้าที่ | ของเรา (server.py) |
|---|---|---|
| Hook (0–2 วิ) | หยุดนิ้ว — สถานการณ์/เรียกกลุ่ม/หลักฐาน | `hook` (Sonnet หรือ pool HOOKS/CAT/PCT/DISCOUNT) ขึ้นจอเป็นวลีเหลืองในช่องชื่อ |
| Promise | บอกว่าดูจบได้อะไร ดึงถึงวิ 10 | `promise` (Sonnet หรือ PROMISES/PROMISES_NOPRICE) |
| Body | เนื้อหาเป็นก้อน | `desc` (คำบรรยายจาก Notion) |
| Open loop | "ยังไม่ถึงจุดพีค" ก่อนก้อนถัดไป | `loop` ก่อนท่อนราคา (Sonnet หรือ LOOPS) ขึ้นจอเหลืองแทนคำบรรยาย |
| จุดพีค | ของเรา = ราคา | `old`/`new` (แม่แบบเสมอ LLM ไม่พูดตัวเลข) |
| CTA | เจาะจง + บอกว่าได้อะไร | `cta` ต้องมี "ป้ายยาดีล ดอทคอม" 1 ครั้ง |
| จอ | progress bar · คำสำคัญทีละวลี | แถว "● เปิด ● สินค้า ● ราคา ● ไปดู" ใต้แบรนด์ y168 · วลี hook/promise/loop |

## skill ที่เกี่ยว
- `channel-profile` — หลัก bio 5 ระดับ + ร่าง bio ของทุกช่อง (จาก Reel @its.howardwang)
- `deal-picking` — หลักเลือกสินค้า 5 ประเภท A–E (ขายดี/ใหม่/สิ้นเปลือง/คอมสูง/ประจำช่อง) ใช้ตอนตัดสินว่าดีลไหนควรเป็นดีลแรกของรอบหรือควรหาสินค้าแบบไหนมาลง

## กติกาที่ห้ามลืม
- ไม่พิมพ์ key/token (สคริปต์นี้ไม่แตะ n8n/.env จึงไม่ต้อง redact แต่ถ้าดึงไฟล์จาก Telegram ต้อง `# noraw` + `| python3 scripts/redact.py`)
- คำที่เติมในบทเพื่อคุมเสียง (`' | '`, `…`) ห้ามหลุดขึ้นจอ — ใช้ `shown()` ใน render() ล้างก่อน
- บทห้ามมีตัวเลข/`?`/คำต้องห้าม (`SCRIPT_BANNED`) และคำอังกฤษนอกชื่อสินค้า → ผ่าน `script_ok`
- ทดสอบ path ที่โพสต์จริงต้องใช้คู่ (คลิป, ดีล) ที่ตรงกัน หรือไม่ส่ง `tiktok`/`fb_reel`
