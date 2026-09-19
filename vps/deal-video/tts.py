# รันใน container python:3.12-slim (มี edge-tts) — สร้างเสียงพากย์ทีละท่อนของทุก variant
# ไฟล์ออก: vo_<variant>_<i>.mp3 · แต่ละท่อนตั้ง rate/pitch แยกกัน ให้จังหวะไม่แบนแบบอ่านรวด
import asyncio, json
import edge_tts

t = json.load(open('texts.json', encoding='utf-8'))

async def main():
    for name, v in t['variants'].items():
        for i, seg in enumerate(v['vo']):
            await edge_tts.Communicate(seg, v['voice'], rate=v['rate'][i], pitch=v['pitch'][i]) \
                .save('vo_%s_%d.mp3' % (name, i))
        print(name, 'ok', len(v['vo']), 'segments')

asyncio.run(main())
