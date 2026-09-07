import json
import unittest
from pathlib import Path
from src.engine import analyze, detect_risk, guard_reply, snapshot


def session(text, ticket=None):
    return {'id': 'S1', 'buyer': '张**', 'messages': [
        {'id': 'm1', 'role': '买家', 'text': text, 'time': '2026-05-01 10:00:00', 'seq': 1},
        {'id': 'm2', 'role': '客服', 'text': '已经退款成功', 'time': '2026-05-01 11:00:00', 'seq': 2}],
        'orders': [], 'tickets': [ticket] if ticket else []}


class EngineTests(unittest.TestCase):
    def test_future_ticket_and_reply_not_visible(self):
        s = session('退款怎么还没到', {'created': '2026-05-01 10:30:00'})
        result = snapshot(s, 1)
        self.assertEqual(len(result['messages']), 1)
        self.assertEqual(result['tickets'], [])

    def test_health_risk_requires_human(self):
        result = analyze(session('涂了以后脸肿了，已经去医院了'), 1)
        self.assertEqual(result['priority'], '高')
        self.assertTrue(result['human_required'])
        self.assertIn('m1', [e['id'] for e in result['evidence']])

    def test_labels_are_not_prediction_inputs(self):
        s = session('快递显示签收了，我没收到包裹')
        a = analyze(s, 1)
        s['label'] = '产品咨询'
        self.assertEqual(analyze(s, 1)['intent'], a['intent'])

    def test_empty_input_not_confident(self):
        s = session(''); s['messages'] = []
        self.assertEqual(analyze(s, 0)['intent'], '待确认')

    def test_greeting_abstains(self):
        self.assertEqual(analyze(session('您好，在吗'), 1)['intent'], '待确认')

    def test_no_medical_risk_downgrade_after_thanks(self):
        s = session('用后红肿，需要你们处理')
        s['messages'][1].update(role='买家', text='谢谢')
        self.assertEqual(analyze(s, 2)['priority'], '高')

    def test_later_health_risk_overrides_product_routing(self):
        s = session('想问问这款精华')
        s['messages'][1].update(role='买家', text='用过后红肿')
        self.assertEqual(analyze(s, 2)['priority'], '高')

    def test_completion_is_not_backdated(self):
        s = session('退款呢', {'created': '2026-05-01 09:00:00', 'completed': '2026-05-02 10:00:00', 'status': '已完结', 'fields': {'转账状态': '转账成功'}})
        t = snapshot(s, 1)['tickets'][0]
        self.assertEqual(t['status'], '历史状态待核实')
        self.assertNotIn('转账状态', t['fields'])

    def test_archive_explicitly_includes_later_ticket(self):
        s = session('退款呢', {'created': '2026-05-02 10:00:00', 'status': '已完结'})
        self.assertEqual(snapshot(s, 2)['tickets'], [])
        archive = snapshot(s, 3)
        self.assertTrue(archive['archived'])
        self.assertEqual(len(archive['tickets']), 1)

    def test_negated_allergy_is_not_an_occurred_risk(self):
        value = analyze(session('我没有过敏，只是想问这款面霜的成分'), 1)
        self.assertEqual(value['intent'], '产品咨询')
        self.assertFalse(any(r['risk_type'] == 'health' for r in value['risks']))
        self.assertEqual(value['risk_signals'][0]['semantic_state'], '否定')

    def test_hypothetical_allergy_is_product_consultation(self):
        value = analyze(session('这款精华会不会引起过敏？'), 1)
        self.assertEqual(value['intent'], '产品咨询')
        self.assertNotEqual(value['priority'], '高')
        self.assertEqual(value['risk_signals'][0]['semantic_state'], '假设/咨询')

    def test_negated_complaint_is_not_escalated(self):
        value = analyze(session('之前一直没有投诉，这次想查一下物流'), 1)
        self.assertFalse(any(r['risk_type'] == 'complaint' for r in value['risks']))

    def test_clear_discomfort_is_evidence_grounded(self):
        value = analyze(session('用了以后脸上像针扎一样，眼皮也鼓起来了'), 1)
        health = next(r for r in value['risks'] if r['risk_type'] == 'health')
        self.assertEqual(health['semantic_state'], '实际发生')
        self.assertEqual(health['evidence_ids'], ['m1'])
        self.assertEqual(value['priority'], '高')

    def test_polite_normal_dialogue_does_not_escalate(self):
        s = session('您好')
        s['messages'][1].update(role='买家', text='开发票，谢谢')
        value = analyze(s, 2)
        self.assertFalse(any(r['risk_type'] == 'emotion_escalation' for r in value['risks']))

    def test_all_deterministic_risks_have_evidence(self):
        value = analyze(session('一直没到账，我要投诉，上次也问过'), 1)
        self.assertTrue(value['risks'])
        self.assertTrue(all(r['evidence_ids'] for r in value['risks']))

    def test_unsupported_commitments_are_downgraded(self):
        for reply in ('已为您完成退款，明天一定到账。', '已经补发了。', '保证赔付100元。'):
            with self.subTest(reply=reply):
                checked = guard_reply(reply, session('请处理'))
                self.assertTrue(checked['blocked'])
                self.assertIn('核实', checked['reply'])

    def test_verification_language_is_not_blocked(self):
        checked = guard_reply('我先为您核实退款记录，确认后同步。', session('退款呢'))
        self.assertFalse(checked['blocked'])

    def test_service_item_uses_visible_order_without_reasking(self):
        s = session('退款一直没到，订单号 A123456')
        s['orders'] = [{'id': 'A123456', 'product': '精华', 'created': '2026-05-01 09:00:00',
                        'paid': '2026-05-01 09:01:00', 'shipped': None, 'tracking': '', 'carrier': None}]
        item = analyze(s, 1)['service_item']
        self.assertTrue(item['known_facts'])
        self.assertNotIn('关联订单或可查询单号', item['to_verify'])

    def test_all_official_replay_risks_have_visible_evidence(self):
        data = json.loads((Path(__file__).parents[1] / 'data/dataset.json').read_text(encoding='utf-8'))
        for s in data['sessions']:
            for cursor in range(len(s['messages']) + 1):
                snap = snapshot(s, cursor)
                visible = {m['id'] for m in snap['messages']} | {t.get('id') for t in snap['tickets']}
                for risk in analyze(s, cursor)['risks']:
                    self.assertTrue(risk['evidence_ids'], (s['id'], cursor, risk))
                    self.assertTrue(set(risk['evidence_ids']) <= visible, (s['id'], cursor, risk))


if __name__ == '__main__':
    unittest.main()
