"""unit test ของ jev.py — mock urlopen ทั้งหมด ห้ามยิง API จริง
รัน (bash บน VPS):  cd vps/deal-video/service && OPENROUTER_API_KEY=test python3 -m unittest test_jev -v
"""
import io, json, os, unittest, urllib.error

os.environ.setdefault('OPENROUTER_API_KEY', 'test-key')
import jev


class FakeResp:
    def __init__(self, body):
        self._b = json.dumps(body, ensure_ascii=False).encode('utf-8')
    def read(self):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def http_error(code):
    return urllib.error.HTTPError(jev.JEV_URL, code, 'err', {}, io.BytesIO(b'{"error":"x"}'))


def answers(tt=None, **claims):
    a = {}
    if tt is not None:
        a['tt_risk'] = tt
    for k, p in claims.items():
        a[k] = {'choice': 'claim' if p >= 0.5 else 'none', 'probabilities': {'claim': p, 'none': 1 - p}}
    return {'answers': a, 'usage': {'cost': 0.0001}}


class Base(unittest.TestCase):
    def setUp(self):
        jev._claim_cache.clear(); jev._tt_cache.clear(); jev._cooldown_until = 0.0
        jev.ENABLED = True
        self.calls = []
        self.clock = [1000.0]

    def opener_of(self, *responses):
        seq = list(responses)
        def opener(req, timeout=None):
            self.calls.append(json.loads(req.data.decode('utf-8')))
            r = seq.pop(0)
            if isinstance(r, Exception):
                raise r
            return FakeResp(r)
        return opener

    def kw(self, *responses):
        return dict(opener=self.opener_of(*responses), sleep=lambda s: None, now=lambda: self.clock[0])


class InterpretTests(Base):
    def test_tt_from_answer_uses_p_safe(self):
        r = jev.tt_from_answer({'choice': 'supplement', 'probabilities': {'safe': 0.2, 'supplement': 0.7, 'medical': 0.1}})
        self.assertEqual(r, {'prob': 0.8, 'choice': 'supplement'})
        r = jev.tt_from_answer({'choice': 'safe'})          # ไม่มี probabilities → choice = 1.0
        self.assertEqual(r, {'prob': 0.0, 'choice': 'safe'})
        self.assertIsNone(jev.tt_from_answer(None))
        self.assertIsNone(jev.tt_from_answer({}))

    def test_claim_from_answer(self):
        self.assertEqual(jev.claim_from_answer({'probabilities': {'claim': 0.73, 'none': 0.27}}), 0.73)
        self.assertEqual(jev.claim_from_answer({'choice': 'none'}), 0.0)
        self.assertEqual(jev.claim_from_answer({'choice': 'claim'}), 1.0)
        self.assertIsNone(jev.claim_from_answer({'choice': 5}))


class DecideTests(Base):
    def test_request_shape_and_auth(self):
        ans = jev.decide({'x': 1}, {'q': {'type': 'choice', 'instructions': 'i', 'criteria': {'a': 'A'}}},
                         **self.kw(answers(tt={'choice': 'safe'})))
        self.assertIn('tt_risk', ans)
        sent = self.calls[0]
        self.assertEqual(sent['model'], jev.MODEL)
        self.assertEqual(sent['state'], {'x': 1})
        self.assertEqual(list(sent['questions']), ['q'])

    def test_disabled_or_no_questions_skips_network(self):
        jev.ENABLED = False
        self.assertIsNone(jev.decide({}, {'q': {}}, **self.kw(answers())))
        jev.ENABLED = True
        self.assertIsNone(jev.decide({}, {}, **self.kw(answers())))
        self.assertEqual(self.calls, [])

    def test_retry_on_429_then_ok(self):
        ans = jev.decide({}, {'q': {}}, **self.kw(http_error(429), answers(tt={'choice': 'safe'})))
        self.assertIsNotNone(ans)
        self.assertEqual(len(self.calls), 2)

    def test_400_no_retry_and_cooldown(self):
        self.assertIsNone(jev.decide({}, {'q': {}}, **self.kw(http_error(400))))
        self.assertEqual(len(self.calls), 1)
        # อยู่ในช่วงพัก → ไม่ยิงเลย
        self.assertIsNone(jev.decide({}, {'q': {}}, **self.kw(answers(tt={'choice': 'safe'}))))
        self.assertEqual(len(self.calls), 1)
        # พ้นช่วงพัก → ยิงอีกครั้ง
        self.clock[0] += jev.COOLDOWN_S + 1
        self.assertIsNotNone(jev.decide({}, {'q': {}}, **self.kw(answers(tt={'choice': 'safe'}))))
        self.assertEqual(len(self.calls), 2)

    def test_5xx_twice_and_timeout_give_none(self):
        self.assertIsNone(jev.decide({}, {'q': {}}, **self.kw(http_error(503), http_error(503))))
        self.assertEqual(len(self.calls), 2)
        jev._cooldown_until = 0.0
        self.calls.clear()
        self.assertIsNone(jev.decide({}, {'q': {}}, **self.kw(TimeoutError('t'), TimeoutError('t'))))
        self.assertEqual(len(self.calls), 2)

    def test_reply_without_answers(self):
        self.assertIsNone(jev.decide({}, {'q': {}}, **self.kw({'foo': 1})))


class GateTests(Base):
    def test_deal_gate_primes_claim_cache_and_caches_tt(self):
        resp = answers(tt={'choice': 'supplement', 'probabilities': {'safe': 0.1, 'supplement': 0.9}}, claim_desc=0.8)
        g = jev.deal_gate('ไฟเบอร์ XS', 'อิ่มนาน หุ่นเป๊ะ', **self.kw(resp))
        self.assertEqual(g, {'prob': 0.9, 'choice': 'supplement'})
        self.assertEqual(list(self.calls[0]['questions']), ['tt_risk', 'claim_desc'])
        self.assertEqual(self.calls[0]['state'], {'product_name': 'ไฟเบอร์ XS', 'description': 'อิ่มนาน หุ่นเป๊ะ'})
        # desc อยู่ใน cache แล้ว → claim_prob ไม่ยิงซ้ำ · deal_gate ซ้ำก็ไม่ยิง
        self.assertEqual(jev.claim_prob('อิ่มนาน หุ่นเป๊ะ', **self.kw()), 0.8)
        self.assertEqual(jev.deal_gate('ไฟเบอร์ XS', 'อิ่มนาน หุ่นเป๊ะ', **self.kw()), g)
        self.assertEqual(len(self.calls), 1)

    def test_deal_gate_without_desc_asks_only_tt(self):
        g = jev.deal_gate('หูฟัง', '', **self.kw(answers(tt={'choice': 'safe', 'probabilities': {'safe': 0.97, 'medical': 0.03}})))
        self.assertEqual(g['prob'], 0.03)
        self.assertEqual(list(self.calls[0]['questions']), ['tt_risk'])

    def test_deal_gate_unavailable_returns_none(self):
        self.assertIsNone(jev.deal_gate('x', 'y', **self.kw(http_error(402))))

    def test_claim_probs_batches_and_caches(self):
        jev._claim_cache['เก่า'] = 0.1
        resp = answers(claim_a=0.9, claim_b=0.2)
        out = jev.claim_probs({'a': 'ลดสิวใน 3 วัน', 'b': 'สีดำ ขนาด 500ml', 'c': 'เก่า', 'd': ''}, **self.kw(resp))
        self.assertEqual(out, {'a': 0.9, 'b': 0.2, 'c': 0.1, 'd': None})
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(sorted(self.calls[0]['questions']), ['claim_a', 'claim_b'])
        self.assertEqual(self.calls[0]['state'], {'texts': {'a': 'ลดสิวใน 3 วัน', 'b': 'สีดำ ขนาด 500ml'}})
        # ครั้งถัดไปทุกตัวมาจาก cache
        out2 = jev.claim_probs({'a': 'ลดสิวใน 3 วัน', 'b': 'สีดำ ขนาด 500ml'}, **self.kw())
        self.assertEqual(out2, {'a': 0.9, 'b': 0.2})
        self.assertEqual(len(self.calls), 1)

    def test_claim_probs_unavailable_all_none(self):
        out = jev.claim_probs({'a': 'x', 'b': 'y'}, **self.kw(http_error(500), http_error(500)))
        self.assertEqual(out, {'a': None, 'b': None})

    def test_cache_bounded(self):
        for i in range(jev.CACHE_MAX + 20):
            jev._cache_put(jev._claim_cache, 't%d' % i, 0.0)
        self.assertEqual(len(jev._claim_cache), jev.CACHE_MAX)


if __name__ == '__main__':
    unittest.main()
