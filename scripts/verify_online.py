"""Recheck saved predictions through the real adapter, with network replaced by replay."""
import argparse
import io
import json
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import model
from src.engine import analyze
from scripts.evaluate_online import score, estimate_cost


def verify(out):
    rows = [json.loads(x) for x in (out/'responses.jsonl').read_text(encoding='utf-8').splitlines()]
    summary = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    sessions = {s['id']: s for s in json.loads((ROOT/'data/dataset.json').read_text(encoding='utf-8'))['sessions']}
    assert len(rows) == len({(r['id'], r['scenario']) for r in rows}) == summary['completed']
    if summary['status'] == 'complete':
        assert len(rows) == len(sessions)*2
    old_open = model.urlopen
    old_environment = dict(os.environ)
    os.environ.update(DASHSCOPE_API_KEY='offline-placeholder', QWEN_MODEL=summary['model'], QWEN_BASE_URL=summary['base_url'])
    calls = 0
    try:
        for row in rows:
            s = sessions[row['id']]
            assert row['cursor'] == (1 if row['scenario']=='first_message' else len(s['messages']))
            assert row['label'] == s['label']
            baseline = analyze(s, row['cursor'])
            assert baseline['intent'] == row['rules']
            def replay(request, timeout):
                nonlocal calls
                calls += 1
                assert row['raw_response'] is not None
                assert json.loads(request.data) == row['request']
                return io.BytesIO(json.dumps(row['raw_response']).encode())
            model.urlopen = replay
            model.CACHE.clear()
            value = model.enhance(s, row['cursor'], baseline)
            assert ('model_error' not in value) == row['valid']
            for field in ('intent', 'model_intent', 'intent_source', 'priority', 'risks', 'reply', 'action', 'guard'):
                assert value.get(field) == row['hybrid_result'].get(field), (row['id'], field)
        for scenario, methods in summary['scenarios'].items():
            group = [r for r in rows if r['scenario']==scenario]
            for field, metrics in methods.items():
                assert score(group, field) == metrics
        prompt = sum(r['usage'].get('prompt_tokens', 0) for r in rows)
        completion = sum(r['usage'].get('completion_tokens', 0) for r in rows)
        assert (prompt, completion) == (summary['prompt_tokens'], summary['completion_tokens'])
        assert estimate_cost(prompt, completion) == summary['estimated_list_price_cny']
    finally:
        model.urlopen = old_open
        model.CACHE.clear()
        os.environ.clear()
        os.environ.update(old_environment)
    result = {'verified': True, 'scenarios': len(rows), 'replayed_responses': calls, 'network_calls': 0,
              'checks': ['exact request replay', 'business and safety outputs', 'unique coverage', 'metrics', 'token accounting']}
    (out/'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    verify(parser.parse_args().output.resolve())
