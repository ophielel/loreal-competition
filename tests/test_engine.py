import unittest
from src.engine import analyze, snapshot


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


if __name__ == '__main__':
    unittest.main()
