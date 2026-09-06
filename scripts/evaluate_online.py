"""Run the unchanged application adapter; persist every response for offline scoring."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'deliverables/qwen-v2-eval-20260906'
sys.path.insert(0, str(ROOT))
from src import model
from src.engine import analyze

LOCAL = threading.local()
STOP = threading.Event()
RATE_LOCK = threading.Lock()
NEXT_CALL = 0.0
ORIGINAL_OPEN = model.urlopen


def estimate_cost(prompt, completion):
    return (prompt * 0.2 + completion * 0.8) / 1000000


def score(rows, field):
    classes = sorted({r['label'] for r in rows})
    details = []
    for label in classes:
        tp = sum(r['label'] == label and r.get(field) == label for r in rows)
        support = sum(r['label'] == label for r in rows)
        predicted = sum(r.get(field) == label for r in rows)
        p, r = tp / predicted if predicted else 0, tp / support
        details.append({'label': label, 'support': support, 'precision': p,
                        'recall': r, 'f1': 2*p*r/(p+r) if p+r else 0})
    return {'samples': len(rows), 'accuracy': sum(r.get(field) == r['label'] for r in rows)/len(rows),
            'macro_f1': sum(r['f1'] for r in details)/len(details), 'by_class': details}


def recording_open(request, timeout):
    global NEXT_CALL
    with RATE_LOCK:
        time.sleep(max(0, NEXT_CALL - time.monotonic()))
        NEXT_CALL = time.monotonic() + 1.1
    if STOP.is_set():
        raise RuntimeError('Run stopped')
    LOCAL.request = json.loads(request.data)
    try:
        with ORIGINAL_OPEN(request, timeout=timeout) as response:
            body = response.read()
        LOCAL.raw = json.loads(body)
        return io.BytesIO(body)
    except HTTPError as exc:
        try:
            error = json.loads(exc.read()).get('error', {})
        except Exception:
            error = {}
        # Never save headers, keys, or raw exception/request representations.
        message = str(error.get('message', ''))[:500]
        key = os.environ.get('DASHSCOPE_API_KEY', '')
        if key:
            message = message.replace(key, '[REDACTED]')
        LOCAL.error = {'http_status': exc.code, 'code': error.get('code'), 'message': message}
        STOP.set()
        raise
    except Exception as exc:
        detail = str(getattr(exc, 'reason', type(exc).__name__))[:300]
        secret = os.environ.get('DASHSCOPE_API_KEY', '')
        LOCAL.error = {'type': type(exc).__name__, 'detail': detail.replace(secret, '[REDACTED]') if secret else detail}
        STOP.set()
        raise


def one(task):
    session, scenario, cursor = task
    LOCAL.raw, LOCAL.error, LOCAL.request = None, None, None
    if STOP.is_set():
        return None
    baseline = analyze(session, cursor)
    start = time.perf_counter()
    enhanced = model.enhance(session, cursor, baseline)
    raw = LOCAL.raw
    parsed = None
    if raw:
        try:
            parsed = json.loads(raw['choices'][0]['message']['content'])
        except (KeyError, ValueError, TypeError):
            pass
    valid = 'model_error' not in enhanced
    skipped = enhanced.get('model_error_code') == 'no_buyer_evidence'
    row = {'id': session['id'], 'scenario': scenario, 'cursor': cursor, 'label': session['label'],
           'rules': baseline['intent'], 'qwen_raw': parsed.get('intent') if isinstance(parsed, dict) else ('待确认' if skipped else None),
           'hybrid': enhanced['intent'], 'valid': valid, 'skipped': skipped, 'error': LOCAL.error,
           'latency_ms': round((time.perf_counter()-start)*1000),
           'usage': raw.get('usage', {}) if raw else {}, 'raw_response': raw,
           'request': LOCAL.request, 'hybrid_result': enhanced,
           'rules_health_gate': any(r['title'] == '使用不适需优先关注' for r in baseline['risks'])}
    return row


def report(rows, total, status, metadata):
    prompt = sum(r['usage'].get('prompt_tokens', 0) for r in rows)
    completion = sum(r['usage'].get('completion_tokens', 0) for r in rows)
    result = {**metadata, 'status': status, 'completed': len(rows), 'planned': total,
              'valid_responses': sum(r['valid'] for r in rows), 'prompt_tokens': prompt,
              'model_responses': sum(r['raw_response'] is not None for r in rows),
              'skipped_no_buyer': sum(r.get('skipped', False) for r in rows),
              'completion_tokens': completion, 'estimated_list_price_cny': estimate_cost(prompt, completion),
              'billing_note': 'List-price estimate only; free allowance, cache discounts and actual balance unknown.',
              'scenarios': {}}
    for scenario in ('first_message', 'full_conversation'):
        group = [r for r in rows if r['scenario'] == scenario]
        if group:
            result['scenarios'][scenario] = {field: score(group, field) for field in ('rules', 'qwen_raw', 'hybrid')}
    result['errors'] = [{'id': r['id'], 'scenario': r['scenario'], 'error': r['error']} for r in rows if not r['valid'] and not r.get('skipped')]
    temporary = OUT / 'summary.tmp'
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(OUT / 'summary.json')
    return result


def main():
    global OUT
    args = argparse.ArgumentParser()
    args.add_argument('--pilot', action='store_true', help='Two fixed sessions per class; resume full run without this flag.')
    args.add_argument('--output', type=Path, default=OUT)
    args.add_argument('--limit', type=int, default=276)
    args.add_argument('--workers', type=int, default=3)
    options = args.parse_args()
    OUT = options.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    if not model.configured():
        raise SystemExit('DASHSCOPE_API_KEY is required in process environment')
    os.environ['QWEN_MODEL'] = 'qwen3.7-flash-2026-07-15'
    os.environ['QWEN_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    content = (ROOT / 'data/dataset.json').read_bytes()
    sessions = json.loads(content)['sessions']
    source_files = ['src/model.py', 'src/engine.py', 'src/taxonomy.py']
    fingerprint = hashlib.sha256(content + b''.join((ROOT/f).read_bytes() for f in source_files)).hexdigest()
    pilot_ids = []
    for label in sorted({s['label'] for s in sessions}):
        group = sorted((s for s in sessions if s['label'] == label),
                       key=lambda s: hashlib.sha256(('pilot-v2:'+s['id']).encode()).hexdigest())
        pilot_ids.extend(s['id'] for s in group[:2])
    metadata = {'model': 'qwen3.7-flash-2026-07-15', 'base_url': os.environ['QWEN_BASE_URL'], 'fingerprint': fingerprint,
                'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'started_utc': datetime.now(timezone.utc).isoformat(),
                'pilot_session_ids': pilot_ids, 'source_files': source_files,
                'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'price_source': 'https://help.aliyun.com/zh/model-studio/qwen3-7-flash',
                'limitations': ['Same-source MOCK diagnostic, not held-out evaluation.',
                    'Official session label is used even for first-message cases without sufficient evidence.',
                    'Qwen raw intent is extracted before adapter validation; hybrid includes rule fallback.',
                    'Hybrid and Qwen intent may match; hybrid safety routing is separate from intent.',
                    'No gold emotion, risk or semantic evidence labels; no claim of those accuracy metrics.']}
    checkpoint = OUT / 'responses.jsonl'
    rows = [json.loads(line) for line in checkpoint.read_text(encoding='utf-8').splitlines()] if checkpoint.exists() else []
    if (OUT / 'summary.json').exists():
        previous = json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
        if previous['fingerprint'] != fingerprint:
            raise SystemExit('Source or dataset changed; use a new output directory.')
        metadata['started_utc'] = previous['started_utc']
    done = {(r['id'], r['scenario']) for r in rows}
    tasks = [(s, scenario, cursor) for s in sessions for scenario, cursor in
             [('first_message', 1), ('full_conversation', len(s['messages']))]]
    total = len(tasks)
    pending = [t for t in tasks if (t[0]['id'], t[1]) not in done
               and (not options.pilot or t[0]['id'] in pilot_ids)][:max(0, options.limit-len(rows))]
    model.urlopen = recording_open
    status = 'running'
    report(rows, total, status, metadata)
    with ThreadPoolExecutor(max_workers=options.workers) as pool, checkpoint.open('a', encoding='utf-8') as output, (OUT/'attempts.jsonl').open('a', encoding='utf-8') as attempts:
        for offset in range(0, len(pending), options.workers):
            batch = list(pool.map(one, pending[offset:offset+options.workers]))
            for row in batch:
                if row is None:
                    continue
                attempts.write(json.dumps(row, ensure_ascii=False)+'\n')
                attempts.flush()
                if row['raw_response'] is None and not row.get('skipped'):
                    continue
                output.write(json.dumps(row, ensure_ascii=False)+'\n')
                output.flush()
                os.fsync(output.fileno())
                rows.append(row)
            summary = report(rows, total, status, metadata)
            print(json.dumps({k: summary[k] for k in ('completed','planned','valid_responses','estimated_list_price_cny')}), flush=True)
            if STOP.is_set():
                status = 'stopped_on_error'
                break
            if summary['estimated_list_price_cny'] >= 1:
                status = 'stopped_at_1_cny_estimate'
                break
    if status == 'running':
        status = 'complete' if len(rows) == total else 'pilot_complete'
    summary = report(rows, total, status, metadata)
    print(json.dumps({'status': status, 'completed': len(rows), 'validation_failures': len(summary['errors'])}, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
