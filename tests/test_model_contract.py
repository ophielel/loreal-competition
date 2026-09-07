"""Model contract regressions using synthetic evidence and no external calls."""
import io
import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from src.engine import POLICIES, analyze
from src.model import CACHE, enhance, validate


def response(**changes):
    value = dict(summary='买家咨询产品', intent='产品咨询', emotion='平稳',
                 reply='请核实产品信息', uncertainty='待核实', evidence_ids=['b1'])
    return {**value, **changes}


def session(*texts):
    return {'id': 'synthetic', 'messages': [
        {'id': f'b{i}', 'role': '买家', 'text': text, 'seq': i,
         'time': f'2026-01-01 10:0{i}:00'} for i, text in enumerate(texts, 1)
    ], 'orders': [], 'tickets': []}


def wire(value):
    return io.BytesIO(json.dumps({'choices': [{'message': {
        'content': json.dumps(value)}}], 'usage': {'total_tokens': 42}}).encode())


class ValidatorContractTests(unittest.TestCase):
    def test_visible_seller_context_is_allowed_with_buyer_support(self):
        value = validate(response(evidence_ids=['b1', 's1']),
                         {'b1', 's1'}, buyer_ids={'b1'})
        self.assertEqual(value['evidence_ids'], ['b1', 's1'])

    def test_seller_only_and_invisible_evidence_are_rejected(self):
        for ids in (['s1'], ['b1', 'future'], ['invented']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                validate(response(evidence_ids=ids), {'b1', 's1'}, buyer_ids={'b1'})

    def test_non_objects_are_rejected_with_validation_error(self):
        for value in (None, [], 'response', 42):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(value, {'b1'})

    def test_evidence_requires_array_and_known_enums(self):
        for changes in ({'evidence_ids': 'b1'}, {'evidence_ids': []},
                        {'intent': '自动赔付'}, {'emotion': '快乐'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate(response(**changes), {'b1'})

    def test_empty_uncertainty_is_normalized_but_missing_is_rejected(self):
        self.assertTrue(validate(response(uncertainty=''), {'b1'})['uncertainty'].strip())
        missing = response()
        del missing['uncertainty']
        for value in (missing, response(uncertainty=None)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(value, {'b1'})

    def test_summary_and_reply_limits_match_published_contract(self):
        validate(response(summary='字' * 200, reply='字' * 300), {'b1'})
        for changes in ({'summary': '字' * 201}, {'reply': '字' * 301}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate(response(**changes), {'b1'})

    def test_optional_intent_evidence_must_reference_visible_buyers(self):
        validate(response(), {'b1'})  # Older clients omit this field.
        validate(response(intent_evidence_ids=['b1']), {'b1', 's1'}, buyer_ids={'b1'})
        for ids in ([], 'b1', ['s1'], ['future']):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                validate(response(intent_evidence_ids=ids), {'b1', 's1'}, buyer_ids={'b1'})

    def test_intent_evidence_must_be_visible_even_if_buyer_inventory_is_broader(self):
        # A caller may know buyer roles across a whole session; visibility still wins.
        with self.assertRaises(ValueError):
            validate(response(intent_evidence_ids=['future']), {'b1'},
                     buyer_ids={'b1', 'future'})


class HybridContractTests(unittest.TestCase):
    def setUp(self):
        CACHE.clear()
        self.env = patch.dict('os.environ', {'DASHSCOPE_API_KEY': 'unit-test-placeholder'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(CACHE.clear)

    def test_agreement_retains_model_mode_and_reports_intent_provenance(self):
        s = session('这款面霜适合什么肤质？')
        with patch('src.model.urlopen', return_value=wire(response())):
            value = enhance(s, 1, analyze(s, 1))
        self.assertEqual(value['mode'], 'qwen')
        self.assertEqual(value['model_intent'], '产品咨询')
        self.assertEqual(value['intent_source'], 'agreement')
        self.assertTrue(value['hybrid_reason'])

    def test_health_gate_preserves_safe_reply_and_business_intent(self):
        s = session('我要退货', '使用后脸肿了')
        baseline = analyze(s, 2)
        baseline['intent'] = '售后退货'
        with patch('src.model.urlopen', return_value=wire(response(
                intent='售后退货', reply='继续使用看看', evidence_ids=['b1', 'b2']))):
            value = enhance(s, 2, baseline)
        self.assertEqual(value['intent'], '售后退货')
        self.assertEqual(value['priority'], '高')
        self.assertEqual(value['action'], baseline['action'])
        self.assertEqual(value['guard'], baseline['guard'])
        self.assertEqual(value['reply'], POLICIES['不良反应'][2])

    def test_enhance_accepts_buyer_and_seller_evidence_from_visible_snapshot(self):
        s = session('这款面霜适合什么肤质？')
        s['messages'].append({'id': 's1', 'role': '客服', 'text': '请提供肤质信息',
                              'seq': 2, 'time': '2026-01-01 10:02:00'})
        with patch('src.model.urlopen', return_value=wire(response(evidence_ids=['b1', 's1']))):
            value = enhance(s, 2, analyze(s, 2))
        self.assertEqual(value['mode'], 'qwen')
        self.assertNotIn('model_error', value)

    def test_future_evidence_in_model_output_falls_back_at_early_cursor(self):
        s = session('这款面霜适合什么肤质？', '谢谢')
        baseline = analyze(s, 1)
        with patch('src.model.urlopen', return_value=wire(response(evidence_ids=['b1', 'b2']))):
            value = enhance(s, 1, baseline)
        self.assertEqual(value['mode'], 'rules')
        self.assertEqual(value['intent'], baseline['intent'])
        self.assertIn('model_error', value)

    def test_model_health_intent_cannot_upgrade_non_current_semantics(self):
        examples = [
            ('我没有过敏，只想问面霜成分', '否定'),
            ('这款精华会不会引起过敏？', '假设/咨询'),
            ('以前有过敏史，现在只是咨询成分', '既往情况'),
        ]
        for text, semantic_state in examples:
            CACHE.clear()
            s = session(text)
            baseline = analyze(s, 1)
            self.assertEqual(baseline['risk_signals'][0]['semantic_state'], semantic_state)
            with self.subTest(state=semantic_state), patch('src.model.urlopen', return_value=wire(response(
                    intent='不良反应', evidence_ids=['b1'], intent_evidence_ids=['b1']))):
                value = enhance(s, 1, baseline)
                self.assertNotEqual(value['priority'], '高')
                self.assertFalse(any(r.get('risk_type') == 'model_health' for r in value['risks']))
                self.assertIn('未升级当前风险', value['uncertainty'])

    def test_cache_reapplies_health_routing_to_current_baseline(self):
        s = session('这款面霜适合什么肤质？')
        baseline = analyze(s, 1)
        guarded = deepcopy(baseline)
        guarded.update(priority='高', action=POLICIES['不良反应'][0],
                       guard=POLICIES['不良反应'][1], reply=POLICIES['不良反应'][2])
        guarded['risks'].append({'risk_type': 'health', 'title': '使用不适需优先关注',
                                 'semantic_state': '实际发生', 'actionable': True, 'level': '高',
                                 'detail': '需核实', 'evidence_ids': ['b1']})
        with patch('src.model.urlopen', return_value=wire(response())) as request:
            enhance(s, 1, baseline)
            value = enhance(s, 1, guarded)
        self.assertTrue(value['cache_hit'])
        self.assertEqual(value['call_tokens'], 0)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(value['priority'], '高')
        self.assertEqual(value['action'], guarded['action'])
        self.assertEqual(value['guard'], guarded['guard'])
        self.assertEqual(value['reply'], guarded['reply'])


if __name__ == '__main__':
    unittest.main()
