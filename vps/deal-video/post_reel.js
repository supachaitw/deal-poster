// ทดลองโพสต์ Reels 1 ชิ้นลง @paiyaa_deals ด้วย resumable upload (ไม่ต้องมี URL สาธารณะของไฟล์)
// ไม่พิมพ์ token ออกหน้าจอ
const fs = require('fs');
const path = require('path');
const DIR = __dirname;
const IG = '17841440317177953';
const V = 'v21.0';
const N8N_KEY = process.env.N8N_KEY;

const sleep = ms => new Promise(r => setTimeout(r, ms));
const mask = s => String(s).replace(/EAA[A-Za-z0-9]+/g, '<TOKEN>');

async function main() {
  // GET สดจาก n8n เสมอ (ห้ามใช้สำเนาเก่า) → page token ของ Post to Facebook
  const wf = await (await fetch('https://n8n.srv1277799.hstgr.cloud/api/v1/workflows/E6i2xEAcaUsUFKWm',
    { headers: { 'X-N8N-API-KEY': N8N_KEY } })).json();
  const fb = wf.nodes.find(n => n.name === 'Post to Facebook');
  const TOKEN = fb.parameters.bodyParameters.parameters.find(p => p.name === 'access_token').value;
  if (!TOKEN || !TOKEN.startsWith('EAA')) throw new Error('page token not found');

  // ไฟล์คลิประบุทาง argv ได้ (ค่าเริ่มต้น sample.mp4) เช่น node post_reel.js sample_female.mp4
  const video = fs.readFileSync(path.join(DIR, process.argv[2] || 'sample.mp4'));
  const caption = fs.readFileSync(path.join(DIR, 'reel_caption.txt'), 'utf8');

  // 1) สร้าง container แบบ resumable
  const form = new URLSearchParams({
    media_type: 'REELS', upload_type: 'resumable', share_to_feed: 'true',
    caption, access_token: TOKEN,
  });
  const c = await (await fetch(`https://graph.facebook.com/${V}/${IG}/media`, { method: 'POST', body: form })).json();
  if (!c.id) throw new Error('create failed: ' + mask(JSON.stringify(c)));
  console.log('1) container:', c.id);

  // 2) อัปโหลด binary ไป rupload
  const upUrl = c.uri || `https://rupload.facebook.com/ig-api-upload/${V}/${c.id}`;
  const up = await (await fetch(upUrl, {
    method: 'POST',
    headers: { Authorization: 'OAuth ' + TOKEN, offset: '0', file_size: String(video.length) },
    body: video,
  })).json();
  console.log('2) upload:', mask(JSON.stringify(up)), `(${video.length} bytes)`);
  if (up.success === false || up.error) throw new Error('upload failed');

  // 3) รอ Meta ประมวลผลจน FINISHED (Reels เป็น async)
  let st = {};
  for (let i = 0; i < 40; i++) {
    await sleep(6000);
    st = await (await fetch(`https://graph.facebook.com/${V}/${c.id}?fields=status_code,status&access_token=${TOKEN}`)).json();
    console.log(`3) status #${i + 1}:`, st.status_code, st.status ? '| ' + st.status : '');
    if (st.status_code === 'FINISHED' || st.status_code === 'ERROR' || st.status_code === 'EXPIRED') break;
  }
  if (st.status_code !== 'FINISHED') throw new Error('not finished: ' + mask(JSON.stringify(st)));

  // 4) publish
  const pub = await (await fetch(`https://graph.facebook.com/${V}/${IG}/media_publish`, {
    method: 'POST', body: new URLSearchParams({ creation_id: c.id, access_token: TOKEN }),
  })).json();
  if (!pub.id) throw new Error('publish failed: ' + mask(JSON.stringify(pub)));
  console.log('4) published media id:', pub.id);

  // 5) ยืนยันปลายทาง
  const m = await (await fetch(`https://graph.facebook.com/${V}/${pub.id}?fields=permalink,media_type,media_product_type,timestamp&access_token=${TOKEN}`)).json();
  console.log('5) verify:', JSON.stringify(m));
  fs.writeFileSync(path.join(DIR, 'reel_result.json'), JSON.stringify({ container: c.id, media: pub.id, ...m }, null, 2));
}

main().catch(e => { console.error('FAILED:', mask(e.message)); process.exit(1); });
