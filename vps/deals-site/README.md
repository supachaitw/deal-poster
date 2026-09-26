# deals-site — เว็บดีลสาธารณะ (static)
ดูหัวข้อ "เว็บดีลสาธารณะตัวใหม่ (26 ก.ย. 2569)" ใน CLAUDE.md · ไฟล์จริงบน VPS: `/root/deals-site/{gen.py,s.css,deploy.sh}` + `/root/deals-proxy/nginx.conf`
- `gen.py` — Notion → HTML (stdlib only) · `python3 gen.py stats` = สถิติคลิก
- `s.css` — สไตล์ทั้งเว็บ (gen.py ฝัง hash เป็น `?v=`)
- `nginx.conf` — static + `/go` redirect map + image proxy `/img/{s,l}/`
- `deploy.sh` — สร้าง container `deals-proxy` ใหม่ + ติดตั้ง cron `*/10`
