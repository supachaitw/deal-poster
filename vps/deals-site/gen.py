#!/usr/bin/env python3
"""deals-site generator — Notion Deal Queue -> static HTML for paiyaadeals.com

Runs on the VPS host from cron every 10 minutes (see deploy.sh). stdlib only.
  python3 gen.py            build site into $OUT (default /root/deals-site/html)
  python3 gen.py stats      print click counts parsed from nginx go.log

Secrets: Notion token from $NOTION_TOKEN or DP_NOTION in /root/home-metrics/.env. Never printed.
"""
import os, re, sys, json, html, hashlib, datetime, urllib.request, urllib.parse, subprocess, collections

ROOT = os.environ.get('DEALS_ROOT', '/root/deals-site')
OUT = os.environ.get('OUT', ROOT + '/html')
SITE = os.environ.get('SITE_URL', 'https://paiyaadeals.com')   # 26 ก.ย. 69 โดเมนจริง (deals.srv… 301 มาที่นี่)
DB = '589f80403f534993b49fd9fdd4d292ff'
DAYS = 90
MAX_PAGES = 5
INDEX_CARDS = 48
BRAND = 'ป้ายยาดีลเด็ด'
TG = 'https://t.me/paiyaa_deals'
IG = 'https://www.instagram.com/paiyaa_deals'
FB = 'https://www.facebook.com/paiyaa.deals'
TH = 'https://www.threads.net/@paiyaa_deals'
CATS = [  # (notion name, slug, label)
    ('ความงาม', 'beauty', 'ความงาม'), ('บ้าน', 'home', 'ของใช้ในบ้าน'), ('แฟชั่น', 'fashion', 'แฟชั่น'),
    ('gadget', 'gadget', 'Gadget'), ('อาหาร', 'food', 'อาหาร'), ('รถ', 'auto', 'ของใช้ในรถ'), ('อื่นๆ', 'other', 'อื่น ๆ'),
]
CAT_SLUG = {n: s for n, s, _ in CATS}
CAT_LABEL = {s: l for _, s, l in CATS}
TZ = datetime.timezone(datetime.timedelta(hours=7))
TH_MONTHS = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']


def token():
    t = os.environ.get('NOTION_TOKEN')
    if t:
        return t.strip()
    for line in open('/root/home-metrics/.env', encoding='utf-8'):
        if line.startswith('DP_NOTION='):
            return line.split('=', 1)[1].strip().strip('"').strip("'")
    sys.exit('no Notion token')


def notion_query(tok):
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=DAYS)).date().isoformat()
    body = {
        'page_size': 100,
        'filter': {'and': [
            {'property': 'สถานะ', 'select': {'equals': 'โพสต์แล้ว'}},
            {'property': 'โพสต์เมื่อ', 'date': {'on_or_after': since}},
        ]},
        'sorts': [{'property': 'โพสต์เมื่อ', 'direction': 'descending'}],
    }
    rows, cursor = [], None
    for _ in range(MAX_PAGES):
        if cursor:
            body['start_cursor'] = cursor
        req = urllib.request.Request(
            'https://api.notion.com/v1/databases/%s/query' % DB,
            data=json.dumps(body).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + tok, 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'})
        r = json.load(urllib.request.urlopen(req, timeout=30))
        rows += r.get('results', [])
        if not r.get('has_more'):
            break
        cursor = r.get('next_cursor')
    return rows


def rich(p):
    return ''.join(x.get('plain_text', '') for x in (p or {}).get('rich_text', []) or [])


def to_deal(p):
    pr = p.get('properties', {})
    name = ''.join(x.get('plain_text', '') for x in pr.get('สินค้า', {}).get('title', [])).strip()
    link = (pr.get('ลิงก์Affiliate') or {}).get('url') or ''
    if not name or not link or 'ทดสอบ' in name:
        return None
    if (pr.get('ซ่อนเว็บ') or {}).get('checkbox'):   # ติ๊ก 'ซ่อนเว็บ' ใน Notion / ปุ่มบนหน้า Deal Poster = ไม่ขึ้นเว็บ
        return None
    host = (re.match(r'^https?://([^/?#]+)', link) or [None, ''])[1].lower()
    src = ((pr.get('แหล่ง') or {}).get('select') or {}).get('name') or ''
    if not src:
        src = 'lazada' if ('lazada' in host or 'lzd.co' in host) else 'tiktok' if 'tiktok' in host else 'shopee'
    full = (pr.get('ราคาเต็ม') or {}).get('number')
    sale = (pr.get('ราคาลด') or {}).get('number')
    off = round((1 - sale / full) * 100) if (full and sale and full > sale) else 0
    cat = ((pr.get('หมวด') or {}).get('select') or {}).get('name') or 'อื่นๆ'
    when = ((pr.get('โพสต์เมื่อ') or {}).get('date') or {}).get('start') or ''
    return {
        'id': p['id'].replace('-', ''), 'nid': p['id'], 'name': name, 'link': link, 'full': full, 'sale': sale,
        'off': off, 'save': (full - sale) if off else 0, 'cat': cat, 'slug': CAT_SLUG.get(cat, 'other'),
        'when': when, 'img': (pr.get('รูป') or {}).get('url') or '', 'caption': rich(pr.get('แคปชัน')),
        'desc': rich(pr.get('คำบรรยาย')), 'src': src, 'store': {'lazada': 'Lazada', 'tiktok': 'TikTok Shop'}.get(src, 'Shopee'),
    }


# ---------- helpers ----------
def esc(s):
    return html.escape(str(s if s is not None else ''), quote=True)


def money(n):
    if n is None:
        return ''
    return ('{:,.0f}' if float(n).is_integer() else '{:,.2f}').format(n)


def img_url(u, thumb=False):
    """Route product images through our own domain (/img/…): cached by nginx, same-origin, and
    fetchable by Facebook/LINE preview bots (Shopee/Lazada CDN block them)."""
    if not u:
        return ''
    m = re.match(r'^https?://down-th\.img\.susercontent\.com/file/(.+)$', u)
    if m:
        seg = m.group(1)
        if thumb and '.' not in seg and not seg.endswith('_tn'):
            seg += '_tn'
        return '/img/s/' + seg
    m = re.match(r'^https?://lzd-img-push\.slatic\.net/(.+)$', u)
    if m:
        return '/img/l/' + m.group(1)
    return u


def th_date(iso, with_time=True):
    if not iso:
        return ''
    try:
        d = datetime.datetime.fromisoformat(iso.replace('Z', '+00:00'))
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        d = d.astimezone(TZ)
    except ValueError:
        return iso
    s = '%d %s %d' % (d.day, TH_MONTHS[d.month], d.year + 543)
    return s + (' · %02d:%02d น.' % (d.hour, d.minute) if with_time and 'T' in iso else '')


def clean_caption(d):
    """Caption text for the detail page: drop link lines, hashtags, the price line (shown separately)."""
    txt = d['desc'].strip() or d['caption']
    out = []
    for line in txt.splitlines():
        t = line.strip()
        if not t or 'http' in t or t.startswith('#') or t.startswith('💥') or t.startswith('👉') or t.startswith('🔗'):
            continue
        t = re.sub(r'\(ลิงก์ affiliate\)', '', t).strip()
        t = re.sub(r'#\S+', '', t).strip()
        if t:
            out.append(t)
    return out[:6]


def safe_map_value(u):
    return re.sub(r'[\s"\';$\\{}]', lambda m: urllib.parse.quote(m.group(0)), u)


def write(path, s):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(s)


# ---------- HTML pieces ----------
def svg(name, color='currentColor', size=18):
    P = {
        'search': '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
        'send': '<path d="M22 2L11 13"/><path d="M22 2L15 22l-4-9-9-4z"/>',
        'arrow': '<path d="M5 12h14"/><path d="M13 6l6 6-6 6"/>',
        'back': '<path d="M15 5l-7 7 7 7"/>',
        'bolt': '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
        'check': '<path d="M20 6L9 17l-5-5"/>',
        'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        'shield': '<path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/>',
        'copy': '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
        'share': '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/>',
    }[name]
    return ('<svg width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="2.2" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>') % (size, size, color, P)


def card(d, big=False):
    off = '<span class="off">-%d%%</span>' % d['off'] if d['off'] else ''
    was = '<s>%s ฿</s>' % money(d['full']) if d['off'] else ''
    price = '<b>%s ฿</b>' % money(d['sale']) if d['sale'] is not None else ('<b>%s ฿</b>' % money(d['full']) if d['full'] else '')
    save = '<span class="save">ประหยัด %s ฿</span>' % money(d['save']) if (big and d['off']) else ''
    thumb = img_url(d['img'], thumb=True)
    im = '<img src="%s" alt="" loading="lazy" decoding="async" width="300" height="200">' % esc(thumb) if thumb else '<span class="noimg"></span>'
    return ('<a class="card%s" href="/d/%s">'
            '<span class="ph">%s%s<span class="src">%s</span></span>'
            '<span class="cb"><span class="nm">%s</span><span class="pr">%s %s</span>%s<span class="go">ดูดีล %s</span></span></a>'
            ) % (' big' if big else '', d['id'], im, off, esc(d['store']), esc(d['name']), price, was, save, svg('arrow', '#C63F1E', 14))


def header(q=''):
    return ('<header class="top"><a class="logo" href="/"><span>ป้ายยา</span>ดีลเด็ด</a>'
            '<form class="srch" action="/" role="search"><label class="sr" for="q">ค้นหาสินค้า</label>'
            '<input id="q" name="q" type="search" placeholder="ค้นหา เช่น เคสไอโฟน, วิตามิน" value="%s" autocomplete="off">'
            '<button type="submit" aria-label="ค้นหา">%s</button></form>'
            '<a class="tgb" href="%s" rel="noopener">%s<span>รับดีล</span></a></header>') % (esc(q), svg('search', '#fff', 18), TG, svg('send', '#fff', 16))


def chips(counts, active='all'):
    out = ['<nav class="chips" aria-label="หมวดหมู่"><a href="/"%s>ทั้งหมด</a>' % (' class="on"' if active == 'all' else '')]
    for n, s, l in CATS:
        if counts.get(n):
            out.append('<a href="/c/%s"%s>%s <small>%d</small></a>' % (s, ' class="on"' if active == s else '', l, counts[n]))
    out.append('</nav>')
    return ''.join(out)


def subscribe():
    return ('<section class="sub" id="subscribe"><h2>ดีลดีหมดเร็ว<br>รับแจ้งเตือนก่อนใคร</h2>'
            '<p>ส่งเฉพาะดีลที่คัดแล้ว วันละไม่เกิน 7 รอบ ไม่มีสแปม</p>'
            '<a class="btn w" href="%s" rel="noopener">%s Telegram @paiyaa_deals</a>'
            '<div class="soc"><a href="%s" rel="noopener">Instagram</a><a href="%s" rel="noopener">Facebook</a><a href="%s" rel="noopener">Threads</a></div></section>'
            ) % (TG, svg('send', '#1F6E63', 18), IG, FB, TH)


def trust():
    rows = [('check', '#C63F1E', '#FBE9E3', 'คัดทีละชิ้น ไม่ใช่บอทกวาดทุกอย่าง', 'ดีลที่ขึ้นหน้านี้ผ่านการดูราคาและร้านมาแล้ว'),
            ('clock', '#1F6E63', '#E3F0EC', 'ราคาคือราคาตอนโพสต์', 'แฟลชเซลเปลี่ยนเร็ว กดเข้าไปเช็คราคาล่าสุดที่ร้านก่อนสั่ง'),
            ('shield', '#23201C', '#F1EBE2', 'คุณจ่ายเท่าเดิม', 'ลิงก์เป็น affiliate ร้านแบ่งค่าคอมให้เราเล็กน้อย ราคาที่คุณจ่ายไม่เปลี่ยน')]
    return '<section class="trust"><h2>ทำไมต้องดูดีลที่นี่</h2>' + ''.join(
        '<div class="tr"><span class="ic" style="background:%s">%s</span><p><b>%s</b><br><span>%s</span></p></div>' % (bg, svg(i, c), t, s)
        for i, c, bg, t, s in rows) + '</section>'


def footer():
    return ('<footer class="ft"><nav><a href="/about">เกี่ยวกับเรา</a><a href="/policy">นโยบายลิงก์ affiliate</a><a href="%s" rel="noopener">ติดต่อ</a></nav>'
            '<p>%s ไม่ใช่ร้านค้า ไม่รับชำระเงิน การสั่งซื้อและการรับประกันเป็นของร้านบน Shopee / Lazada</p>'
            '<p>© %d %s</p></footer>') % (FB, BRAND, datetime.date.today().year + 543, BRAND)


def page(title, body, desc='', path='/', og_img='', ld='', extra_head='', noindex=False):
    og = ''
    if og_img:
        og = '<meta property="og:image" content="%s"><meta name="twitter:card" content="summary_large_image">' % esc(og_img)
    return ('<!doctype html><html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title><meta name="description" content="%s">%s'
            '<link rel="canonical" href="%s%s"><meta property="og:type" content="website"><meta property="og:site_name" content="%s">'
            '<meta property="og:title" content="%s"><meta property="og:description" content="%s"><meta property="og:url" content="%s%s"><meta property="og:locale" content="th_TH">%s'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Kanit:wght@500;600;700&family=Noto+Sans+Thai:wght@400;500;600&display=swap">'
            '<link rel="stylesheet" href="/s.css?v=%s"><link rel="alternate" type="application/rss+xml" title="%s" href="/rss.xml">'
            '<link rel="icon" href="/favicon.svg" type="image/svg+xml">%s%s</head><body>%s</body></html>'
            ) % (esc(title), esc(desc), '<meta name="robots" content="noindex">' if noindex else '', SITE, esc(path), BRAND,
                 esc(title), esc(desc), SITE, esc(path), og, CSS_V, BRAND, ld, extra_head, body)


SEARCH_JS = r"""<script>(function(){var q=document.getElementById('q'),grid=document.getElementById('grid'),more=document.getElementById('more'),info=document.getElementById('info'),all=null,busy=false;
function m(n){return n==null?'':(Number(n)%1?Number(n).toLocaleString('th-TH',{maximumFractionDigits:2}):Number(n).toLocaleString('th-TH'))}
function e(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function card(d){return '<a class="card" href="/d/'+d.id+'"><span class="ph">'+(d.i?'<img src="'+e(d.i)+'" alt="" loading="lazy" decoding="async" width="300" height="200">':'<span class="noimg"></span>')+(d.o?'<span class="off">-'+d.o+'%</span>':'')+'<span class="src">'+e(d.st)+'</span></span><span class="cb"><span class="nm">'+e(d.n)+'</span><span class="pr"><b>'+m(d.s!=null?d.s:d.f)+' ฿</b> '+(d.o?'<s>'+m(d.f)+' ฿</s>':'')+'</span><span class="go">ดูดีล →</span></span></a>'}
function load(cb){if(all)return cb(all);if(busy)return;busy=true;fetch('/deals.json').then(function(r){return r.json()}).then(function(j){all=j;busy=false;cb(j)}).catch(function(){busy=false})}
function render(list,label){grid.innerHTML=list.map(card).join('')||'<p class="empty">ไม่พบดีลที่ตรงกับคำค้น ลองคำสั้นลง</p>';if(info)info.textContent=label;if(more)more.style.display='none';window.scrollTo({top:grid.offsetTop-90,behavior:'smooth'})}
function search(s){s=s.trim().toLowerCase();if(!s)return;load(function(j){var r=j.filter(function(d){return d.n.toLowerCase().indexOf(s)>-1||(d.c||'').toLowerCase().indexOf(s)>-1});render(r,'ค้นหา "'+s+'" พบ '+r.length+' รายการ')})}
if(q){q.form.addEventListener('submit',function(ev){ev.preventDefault();search(q.value)});var p=new URLSearchParams(location.search).get('q');if(p){q.value=p;search(p)}}
if(more){more.addEventListener('click',function(){load(function(j){var have=grid.querySelectorAll('.card').length;var next=j.slice(have,have+48);grid.insertAdjacentHTML('beforeend',next.map(card).join(''));if(have+next.length>=j.length)more.style.display='none';else more.textContent='ดูดีลเพิ่ม (อีก '+(j.length-have-next.length)+' รายการ)'})})}
})();</script>"""

DETAIL_JS = r"""<script>(function(){var b=document.getElementById('cp');if(!b)return;b.addEventListener('click',function(){var u=location.href;(navigator.clipboard?navigator.clipboard.writeText(u):Promise.reject()).then(function(){b.textContent='คัดลอกแล้ว'},function(){prompt('คัดลอกลิงก์',u)})})})();</script>"""


def build(deals, now):
    counts = collections.Counter(d['cat'] for d in deals)
    upd = '%02d:%02d น.' % (now.hour, now.minute)
    recent = [d for d in deals if d['off'] >= 20 and d['when'] >= (now - datetime.timedelta(days=14)).date().isoformat()]
    hot = sorted(recent, key=lambda d: -d['off'])[:6]
    if len(hot) < 3:
        hot = sorted([d for d in deals if d['off']], key=lambda d: -d['off'])[:6]
    hot_ids = {d['id'] for d in hot}

    # ----- index -----
    latest = deals[:INDEX_CARDS]
    body = header() + '<main class="wrap">'
    body += ('<section class="hero"><h1>ดีลเด็ดวันนี้<br>คัดแล้วจาก Shopee และ Lazada</h1>'
             '<p>อัปเดตทุก 3 ชั่วโมง · %d ดีลใน %d วันล่าสุด · ราคาที่เห็นคือราคาตอนโพสต์ กดไปเช็คราคาสดที่ร้านได้เลย</p></section>'
             ) % (len(deals), DAYS)
    body += chips(counts)
    if hot:
        body += ('<section class="hot"><div class="sh"><h2>%s ลดแรงวันนี้</h2><a href="#latest">ดูทั้งหมด</a></div><div class="row">%s</div></section>'
                 ) % (svg('bolt', '#C63F1E', 20), ''.join(card(d, big=True) for d in hot))
    body += ('<section class="latest" id="latest"><div class="sh"><h2>ดีลล่าสุด</h2><span id="info">อัปเดต %s</span></div>'
             '<div class="grid" id="grid">%s</div>%s</section>'
             ) % (upd, ''.join(card(d) for d in latest),
                  '<button type="button" class="btn o" id="more">ดูดีลเพิ่ม (อีก %d รายการ)</button>' % (len(deals) - len(latest)) if len(deals) > len(latest) else '')
    body += subscribe() + trust() + '</main>' + footer() + SEARCH_JS
    ld = json.dumps({'@context': 'https://schema.org', '@type': 'WebSite', 'name': BRAND, 'url': SITE + '/',
                     'potentialAction': {'@type': 'SearchAction', 'target': SITE + '/?q={q}', 'query-input': 'required name=q'}}, ensure_ascii=False)
    write('index.html', page('%s — รวมดีล Shopee Lazada คัดแล้ว อัปเดตทุก 3 ชั่วโมง' % BRAND, body,
                             'รวมดีลลดราคาจาก Shopee และ Lazada คัดทีละชิ้น อัปเดตทุก 3 ชั่วโมง ราคาที่คุณจ่ายเท่าเดิม', '/',
                             ld='<script type="application/ld+json">%s</script>' % ld))

    # ----- category pages -----
    for n, s, l in CATS:
        items = [d for d in deals if d['cat'] == n]
        if not items:
            continue
        body = header() + '<main class="wrap">' + ('<section class="hero"><h1>ดีล%s</h1><p>%d รายการใน %d วันล่าสุด · อัปเดต %s</p></section>' % (l, len(items), DAYS, upd))
        body += chips(counts, s)
        body += '<section class="latest"><div class="grid" id="grid">%s</div></section>' % ''.join(card(d) for d in items)
        body += subscribe() + '</main>' + footer() + SEARCH_JS
        write('c/%s.html' % s, page('ดีล%s — %s' % (l, BRAND), body, 'ดีลลดราคาหมวด%s จาก Shopee และ Lazada คัดแล้ว %d รายการ' % (l, len(items)), '/c/' + s))

    # ----- detail pages -----
    by_cat = collections.defaultdict(list)
    for d in deals:
        by_cat[d['cat']].append(d)
    for d in deals:
        similar = [x for x in by_cat[d['cat']] if x['id'] != d['id']][:4]
        lines = clean_caption(d)
        price = ('<div class="price"><b>%s ฿</b>%s</div>' % (money(d['sale'] if d['sale'] is not None else d['full']),
                 '<s>%s ฿</s>' % money(d['full']) if d['off'] else '')) if (d['sale'] is not None or d['full']) else ''
        badges = '<span class="bg dark">%s</span><a class="bg" href="/c/%s">%s</a>' % (esc(d['store']), d['slug'], CAT_LABEL.get(d['slug'], d['cat']))
        if d['off']:
            badges += '<span class="bg teal">ประหยัด %s ฿</span>' % money(d['save'])
        go = '/go?d=' + d['id']
        cta = '<a class="btn p" href="%s" rel="nofollow sponsored noopener">ไปที่ร้านบน %s %s</a>' % (go, esc(d['store']), svg('arrow', '#fff'))
        full_img = img_url(d['img'])
        body = ('<header class="top dt"><a class="back" href="/">%s ดีลทั้งหมด</a><a class="logo" href="/"><span>ป้ายยา</span>ดีลเด็ด</a><a class="tgb" href="%s" rel="noopener">%s<span>รับดีล</span></a></header>'
                ) % (svg('back', '#23201C', 20), TG, svg('send', '#fff', 16))
        body += '<main class="wrap deal">'
        body += '<div class="hero-img">%s%s</div>' % (
            '<img src="%s" alt="%s" width="600" height="315" decoding="async">' % (esc(full_img), esc(d['name'])) if full_img else '<span class="noimg"></span>',
            '<span class="off big">-%d%%</span>' % d['off'] if d['off'] else '')
        body += '<section class="db"><div class="badges">%s</div><h1>%s</h1>%s%s<p class="note">เปิดในแอป %s ได้เลย · ราคาตอนโพสต์ %s ราคาสดดูที่ร้าน</p></section>' % (
            badges, esc(d['name']), price, cta, esc(d['store']), th_date(d['when']))
        if lines:
            body += '<section class="why"><h2>ทำไมถึงป้ายยาชิ้นนี้</h2>%s' % ''.join('<p>%s</p>' % esc(t) for t in lines)
        else:
            body += '<section class="why">'
        body += ('<dl><div><dt>ร้าน</dt><dd>%s</dd></div><div><dt>โพสต์เมื่อ</dt><dd>%s</dd></div>%s<div><dt>เห็นก่อนใครที่</dt><dd><a href="%s" rel="noopener">Telegram @paiyaa_deals</a></dd></div></dl></section>'
                 ) % (esc(d['store']), th_date(d['when']), '<div><dt>ส่วนลด</dt><dd>%d%% (ประหยัด %s ฿)</dd></div>' % (d['off'], money(d['save'])) if d['off'] else '', TG)
        u = urllib.parse.quote(SITE + '/d/' + d['id'], safe='')
        body += ('<section class="share"><h2>ส่งต่อให้เพื่อน</h2><div class="sb"><button type="button" id="cp">%s คัดลอกลิงก์</button>'
                 '<a href="https://social-plugins.line.me/lineit/share?url=%s" rel="noopener">แชร์ LINE</a>'
                 '<a href="https://www.facebook.com/sharer/sharer.php?u=%s" rel="noopener">แชร์ Facebook</a></div></section>') % (svg('copy', '#23201C', 16), u, u)
        if similar:
            body += '<section class="latest"><div class="sh"><h2>ดีลคล้ายกัน</h2><a href="/c/%s">ดูหมวด%s</a></div><div class="grid">%s</div></section>' % (
                d['slug'], CAT_LABEL.get(d['slug'], ''), ''.join(card(x) for x in similar))
        body += '</main>' + footer()
        body += ('<div class="sticky"><div class="sp"><b>%s ฿</b>%s</div><a class="btn p" href="%s" rel="nofollow sponsored noopener">ไปที่ร้าน %s %s</a></div>'
                 ) % (money(d['sale'] if d['sale'] is not None else d['full']), '<s>%s ฿</s>' % money(d['full']) if d['off'] else '', go, esc(d['store']), svg('arrow', '#fff')) if (d['sale'] is not None or d['full']) else ''
        body += DETAIL_JS
        ldp = {'@context': 'https://schema.org', '@type': 'Product', 'name': d['name'], 'url': SITE + '/d/' + d['id']}
        if full_img:
            ldp['image'] = SITE + full_img
        if d['sale'] is not None or d['full']:
            ldp['offers'] = {'@type': 'Offer', 'priceCurrency': 'THB', 'price': d['sale'] if d['sale'] is not None else d['full'], 'url': SITE + go, 'availability': 'https://schema.org/InStock'}
        desc = ('%s ลดเหลือ %s ฿ จาก %s ฿ (ลด %d%%)' % (d['name'], money(d['sale']), money(d['full']), d['off'])) if d['off'] else (
            '%s ราคา %s ฿' % (d['name'], money(d['sale'] if d['sale'] is not None else d['full'])) if (d['sale'] is not None or d['full']) else d['name'])
        title = ('%s ลด %d%% เหลือ %s ฿' % (d['name'][:70], d['off'], money(d['sale']))) if d['off'] else d['name'][:90]
        write('d/%s.html' % d['id'], page(title + ' — ' + BRAND, body, desc + ' · ' + BRAND, '/d/' + d['id'],
                                         og_img=(SITE + full_img) if full_img else '',
                                         ld='<script type="application/ld+json">%s</script>' % json.dumps(ldp, ensure_ascii=False),
                                         extra_head='<meta property="product:price:amount" content="%s"><meta property="product:price:currency" content="THB">' % (d['sale'] if d['sale'] is not None else d['full'] or '')))

    # ----- static pages -----
    about = ('<section class="hero"><h1>เกี่ยวกับ %s</h1><p>เพจรวมดีลลดราคาจาก Shopee และ Lazada ที่คัดทีละชิ้นด้วยมือ โพสต์วันละไม่เกิน 7 รอบ ทั้งบนเว็บนี้ Telegram Instagram Facebook และ Threads</p></section>'
             '<section class="why"><h2>เราทำอะไร</h2><p>ไล่ดูดีลจากร้านต่าง ๆ แล้วเลือกเฉพาะที่ราคาดีจริง ลดจริง เอามารวมไว้หน้าเดียว พร้อมลิงก์ไปร้านโดยตรง</p>'
             '<h2>เราไม่ทำอะไร</h2><p>เราไม่ใช่ร้านค้า ไม่รับชำระเงิน ไม่จัดส่ง ไม่รับประกันสินค้า ทุกอย่างเป็นของร้านบนแพลตฟอร์มนั้น ๆ</p>'
             '<h2>ติดต่อ</h2><p>ทักได้ที่ <a href="%s" rel="noopener">Facebook ป้ายยาดีลเด็ด</a> หรือ <a href="%s" rel="noopener">Telegram @paiyaa_deals</a></p></section>') % (BRAND, FB, TG)
    write('about.html', page('เกี่ยวกับเรา — ' + BRAND, header() + '<main class="wrap">' + about + subscribe() + '</main>' + footer(), 'เพจรวมดีล Shopee Lazada คัดด้วยมือ', '/about'))
    policy = ('<section class="hero"><h1>นโยบายลิงก์ affiliate</h1><p>ความโปร่งใสเรื่องรายได้ของเว็บนี้</p></section>'
              '<section class="why"><p>ลิงก์ "ไปที่ร้าน" ทุกลิงก์บนเว็บนี้เป็นลิงก์ affiliate ของ Shopee หรือ Lazada เมื่อคุณกดลิงก์แล้วซื้อสินค้า ร้านหรือแพลตฟอร์มจะแบ่งค่าคอมมิชชันเล็กน้อยให้เรา <b>ราคาที่คุณจ่ายไม่เปลี่ยน</b> และเราไม่เห็นข้อมูลการสั่งซื้อของคุณ</p>'
              '<p>ราคาและส่วนลดที่แสดงคือค่าที่บันทึกไว้ตอนโพสต์ แฟลชเซลอาจหมดหรือเปลี่ยนราคาได้ทุกเมื่อ กรุณาตรวจสอบราคาล่าสุดที่หน้าร้านก่อนสั่งซื้อ</p>'
              '<p>เว็บนี้นับจำนวนคลิกออกไปยังร้านเพื่อดูว่าดีลไหนคนสนใจ ไม่เก็บชื่อ อีเมล หรือข้อมูลส่วนตัวใด ๆ และไม่ใช้คุกกี้ติดตาม</p></section>')
    write('policy.html', page('นโยบายลิงก์ affiliate — ' + BRAND, header() + '<main class="wrap">' + policy + '</main>' + footer(), 'ลิงก์บนเว็บเป็น affiliate ราคาที่คุณจ่ายเท่าเดิม', '/policy'))
    write('404.html', page('ไม่พบหน้านี้ — ' + BRAND, header() + '<main class="wrap"><section class="hero"><h1>ไม่พบดีลนี้</h1><p>ดีลอาจหมดอายุหรือถูกถอดออกแล้ว</p><a class="btn p" href="/">ดูดีลล่าสุด</a></section></main>' + footer(), '', '/404', noindex=True))

    # ----- data files -----
    write('deals.json', json.dumps([{'id': d['id'], 'n': d['name'], 'c': d['cat'], 's': d['sale'], 'f': d['full'], 'o': d['off'],
                                     'i': img_url(d['img'], thumb=True), 'st': d['store'], 't': d['when']} for d in deals], ensure_ascii=False, separators=(',', ':')))
    urls = [('/', now.date().isoformat(), 'hourly', '1.0')] + [('/c/' + s, now.date().isoformat(), 'hourly', '0.8') for n, s, _ in CATS if counts.get(n)]
    urls += [('/d/' + d['id'], (d['when'] or '')[:10] or now.date().isoformat(), 'weekly', '0.6') for d in deals] + [('/about', '', 'monthly', '0.3'), ('/policy', '', 'monthly', '0.3')]
    write('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(
        '<url><loc>%s%s</loc>%s<changefreq>%s</changefreq><priority>%s</priority></url>' % (SITE, u, '<lastmod>%s</lastmod>' % lm if lm else '', cf, pr)
        for u, lm, cf, pr in urls) + '</urlset>')
    write('robots.txt', 'User-agent: *\nAllow: /\nDisallow: /go\nSitemap: %s/sitemap.xml\n' % SITE)
    write('rss.xml', '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>%s</title><link>%s/</link><description>ดีลลดราคา Shopee Lazada คัดแล้ว</description>%s</channel></rss>' % (
        BRAND, SITE, ''.join('<item><title>%s</title><link>%s/d/%s</link><guid>%s/d/%s</guid><description>%s</description>%s</item>' % (
            esc(d['name']), SITE, d['id'], SITE, d['id'], esc(('ลดเหลือ %s ฿ จาก %s ฿ (ลด %d%%)' % (money(d['sale']), money(d['full']), d['off'])) if d['off'] else ('ราคา %s ฿' % money(d['sale'] if d['sale'] is not None else d['full']))),
            '<pubDate>%s</pubDate>' % datetime.datetime.fromisoformat(d['when'].replace('Z', '+00:00')).strftime('%a, %d %b %Y %H:%M:%S %z') if 'T' in d['when'] else '') for d in deals[:50])))
    write('favicon.svg', '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#C63F1E"/><text x="16" y="22" text-anchor="middle" font-family="Kanit,sans-serif" font-size="17" font-weight="700" fill="#fff">ป</text></svg>')

    # ----- nginx redirect map (id -> affiliate url), both id forms -----
    lines = []
    for d in deals:
        v = safe_map_value(d['link'])
        lines.append('"%s" "%s";' % (d['id'], v))
        lines.append('"%s" "%s";' % (d['nid'], v))
    return '\n'.join(lines) + '\n'


CSS_V = ''


def dedupe(deals):
    """Same affiliate link or same (normalised) name posted twice -> keep the newest only (rows are newest-first)."""
    seen_link, seen_name, out = set(), set(), []
    for d in deals:
        key = re.sub(r'\s+', ' ', d['name'].strip().lower())
        if d['link'] in seen_link or key in seen_name:
            continue
        seen_link.add(d['link']); seen_name.add(key); out.append(d)
    return out



def main():
    global CSS_V
    if len(sys.argv) > 1 and sys.argv[1] == 'stats':
        return stats()
    here = os.path.dirname(os.path.abspath(__file__))
    css = open(os.path.join(here, 's.css'), encoding='utf-8').read()
    CSS_V = hashlib.md5(css.encode('utf-8')).hexdigest()[:8]
    now = datetime.datetime.now(TZ)
    rows = notion_query(token())
    deals = dedupe([d for d in (to_deal(p) for p in rows) if d])
    os.makedirs(OUT, exist_ok=True)
    write('s.css', css)
    mp = build(deals, now)
    # map อยู่ในโฟลเดอร์ที่ mount ทั้งโฟลเดอร์ — เดิม mount ไฟล์เดี่ยว /root/deals-site/deals.map แล้ว os.replace เปลี่ยน inode
    # → container เห็นไฟล์เก่าค้าง (26 ก.ย. 69 ค้างที่ 04:16 UTC ดีลใหม่ทุกตัวกด 'ไปที่ร้าน' แล้วเด้งกลับหน้าแรก) reload กี่รอบก็ไม่ช่วย
    map_dir = os.path.join(ROOT, 'map'); os.makedirs(map_dir, exist_ok=True)
    map_path = os.path.join(map_dir, 'deals.map')
    old = open(map_path, encoding='utf-8').read() if os.path.exists(map_path) else ''
    if old != mp:
        with open(map_path + '.tmp', 'w', encoding='utf-8') as f:
            f.write(mp)
        os.replace(map_path + '.tmp', map_path)
        if os.environ.get('NO_RELOAD') != '1':
            r = subprocess.run(['docker', 'exec', 'deals-proxy', 'sh', '-c', 'nginx -t && nginx -s reload'], capture_output=True, text=True)
            print('nginx reload:', 'ok' if r.returncode == 0 else r.stderr.strip()[:300])
    # prune detail pages of deals no longer listed
    keep = {d['id'] + '.html' for d in deals}
    ddir = os.path.join(OUT, 'd')
    if os.path.isdir(ddir):
        for f in os.listdir(ddir):
            if f not in keep:
                os.remove(os.path.join(ddir, f))
    print('%s built %d deals (%d rows, hidden/dup removed %d) -> %s' % (now.strftime('%Y-%m-%d %H:%M'), len(deals), len(rows), len(rows) - len(deals), OUT))


def stats():
    log = os.path.join(ROOT, 'log', 'go.log')
    if not os.path.exists(log):
        return print('no clicks yet')
    names = {}
    try:
        for d in json.load(open(os.path.join(OUT, 'deals.json'), encoding='utf-8')):
            names[d['id']] = d['n']
    except Exception:
        pass
    c, week = collections.Counter(), collections.Counter()
    cutoff = (datetime.datetime.now(TZ) - datetime.timedelta(days=7)).isoformat()
    for line in open(log, encoding='utf-8', errors='replace'):
        parts = line.split(' ', 2)
        if len(parts) < 2:
            continue
        i = parts[1].replace('-', '')
        c[i] += 1
        if parts[0] >= cutoff:
            week[i] += 1
    print('clicks total %d · 7 days %d · deals clicked %d' % (sum(c.values()), sum(week.values()), len(c)))
    for i, n in c.most_common(40):
        print('%5d  %4d  %s' % (n, week[i], names.get(i, i)[:70]))


if __name__ == '__main__':
    main()
