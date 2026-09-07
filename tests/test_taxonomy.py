import unittest
from src.taxonomy import DEFINITIONS, strong_anchor


class TaxonomyTests(unittest.TestCase):
    def messages(self, *texts):
        return [dict(id=f'm{i}', role='买家', text=text) for i, text in enumerate(texts)]

    def test_refund_progress_and_separate_payment_are_distinct(self):
        self.assertEqual(strong_anchor(self.messages('退款成功了可是还没到账'))[0], '订单服务')
        self.assertEqual(strong_anchor(self.messages('退货运费报销怎么处理'))[0], '退款打款')

    def test_later_resolution_does_not_replace_primary_request(self):
        self.assertEqual(strong_anchor(self.messages('包裹破损了', '那就补发吧'))[0], '物流异常')

    def test_greeting_does_not_guess_from_seller(self):
        messages = self.messages('您好') + [dict(id='seller', role='客服', text='赠品补发了')]
        self.assertEqual(strong_anchor(messages), (None, None))

    def test_business_definitions_cover_all_baseline_labels(self):
        from src.engine import INTENTS
        self.assertEqual(set(DEFINITIONS), {x[0] for x in INTENTS} | {'待确认'})
