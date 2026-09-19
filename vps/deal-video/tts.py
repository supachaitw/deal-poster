# รันใน container python:3.12-slim (มี edge-tts) — สร้างไฟล์เสียงพากย์ทีละท่อน vo_0.mp3 ... vo_N.mp3
import asyncio, json
import edge_tts

t = json.load(open('texts.json', encoding='utf-8'))

async def main():
    for i, seg in enumerate(t['vo']):
        await edge_tts.Communicate(seg, t['voice'], rate='+12%').save('vo_%d.mp3' % i)
        print('vo_%d.mp3 ok' % i)

asyncio.run(main())
