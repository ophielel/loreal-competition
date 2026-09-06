import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.model import validate, enhance
from src import store


class ModelAndStoreTests(unittest.TestCase):
    def test_model_fabricated_evidence_rejected(self):
        value = dict(summary='摘要', intent='产品咨询', emotion='平稳', reply='回复', uncertainty='待核实', evidence_ids=['fake'])
        with self.assertRaises(ValueError):
            validate(value, {'m1'})

    def test_no_key_has_explicit_fallback(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertIn('model_error', enhance({}, 1, {'mode': 'rules'}))

    def test_task_dedup_and_persistence(self):
        with tempfile.TemporaryDirectory() as d, patch.object(store, 'DB', Path(d) / 'test.sqlite'):
            a = store.create_task('S1', 1, '核实退款', '核对工单')
            b = store.create_task('S1', 1, '核实退款', '核对工单')
            self.assertEqual(a['id'], b['id'])
            self.assertEqual(len(store.list_tasks()), 1)
            store.complete_task(a['id'])
            self.assertEqual(store.list_tasks()[0]['status'], '已完成')
