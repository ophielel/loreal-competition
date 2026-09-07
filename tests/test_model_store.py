import tempfile
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from src.model import validate, enhance
from src.model import CACHE
from src.engine import analyze
from src import model, store


class ModelAndStoreTests(unittest.TestCase):
    def tearDown(self):
        model.RUNTIME_CONFIG = None
        CACHE.clear()

    def fake_session(self):
        return {'id':'S1','buyer':'测试','messages':[{'id':'m1','role':'买家','text':'用了面膜后发红','time':'2026-01-01 10:00:00','seq':1}], 'orders':[], 'tickets':[]}

    def test_valid_model_response_and_cache(self):
        CACHE.clear()
        s=self.fake_session()
        result=dict(summary='买家反馈发红',intent='不良反应',emotion='焦急',reply='将交由专员核实',uncertainty='需核实',evidence_ids=['m1'])
        response={'choices':[{'message':{'content':json.dumps(result)}}], 'usage':{'total_tokens':100}}
        with patch.dict('os.environ',{'DASHSCOPE_API_KEY':'unit-test-placeholder'},clear=True), patch('src.model.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as request:
            first=enhance(s,1,analyze(s,1))
            second=enhance(s,1,analyze(s,1))
            self.assertEqual(first['mode'],'qwen')
            self.assertTrue(second['cache_hit'])
            self.assertEqual(second['call_tokens'],0)
            self.assertEqual(request.call_count,1)

    def test_malformed_model_response_falls_back(self):
        CACHE.clear()
        s=self.fake_session()
        with patch.dict('os.environ',{'DASHSCOPE_API_KEY':'unit-test-placeholder'},clear=True), patch('src.model.urlopen',return_value=io.BytesIO(b'{}')):
            result=enhance(s,1,analyze(s,1))
            self.assertEqual(result['mode'],'rules')
            self.assertIn('model_error',result)

    def test_model_cannot_downgrade_health_workflow(self):
        CACHE.clear()
        s=self.fake_session()
        result=dict(summary='买家咨询',intent='产品咨询',emotion='平稳',reply='请核实',uncertainty='不确定',evidence_ids=['m1'])
        response={'choices':[{'message':{'content':json.dumps(result)}}]}
        with patch.dict('os.environ',{'DASHSCOPE_API_KEY':'unit-test-placeholder'},clear=True), patch('src.model.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
            value=enhance(s,1,analyze(s,1))
            self.assertEqual(value['priority'],'高')
            self.assertEqual(value['action'],'优先转专员核实')

    def test_model_fabricated_evidence_rejected(self):
        value = dict(summary='摘要', intent='产品咨询', emotion='平稳', reply='回复', uncertainty='待核实', evidence_ids=['fake'])
        with self.assertRaises(ValueError):
            validate(value, {'m1'})

    def test_no_key_has_explicit_fallback(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertIn('model_error', enhance({}, 1, {'mode': 'rules'}))

    def test_runtime_configuration_keeps_key_private(self):
        model.configure('sk-memory-only', 'qwen-plus', 'https://example.com/v1')
        public = model.public_config()
        self.assertTrue(public['configured'])
        self.assertEqual(public['key_source'], 'memory')
        self.assertNotIn('api_key', public)
        self.assertNotIn('sk-memory-only', json.dumps(public))

    def test_task_dedup_and_persistence(self):
        with tempfile.TemporaryDirectory() as d, patch.object(store, 'DB', Path(d) / 'test.sqlite'):
            a = store.create_task('S1', 1, '核实退款', '核对工单')
            b = store.create_task('S1', 1, '核实退款', '核对工单')
            self.assertEqual(a['id'], b['id'])
            self.assertEqual(len(store.list_tasks()), 1)
            store.complete_task(a['id'])
            self.assertEqual(store.list_tasks()[0]['status'], '已完成')
