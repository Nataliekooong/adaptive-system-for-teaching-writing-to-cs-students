"""Single-pass paragraph feedback: no reviewer and no automatic retries."""
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

import feedback as core

VERSION = 'paragraph_single_pass_v1'


def fingerprint(batch_size, model=core.MODEL, min_target_words=6):
    return core.digest(core.dumps([VERSION, model, core.SYSTEM, batch_size, min_target_words]))


class APIClient:
    def __init__(self, key, out, budget, config_hash, model):
        self.key, self.out, self.budget, self.config_hash = key, Path(out), budget, config_hash
        self.model = model
        _, self.peak = core.model_prices(model)
        self.usage_path = self.out.with_suffix('.usage.jsonl')
        self.spent = 0
        if self.usage_path.exists():
            for entry in core.read_jsonl(self.usage_path):
                if entry.get('config_hash') != config_hash:
                    raise SystemExit('Usage belongs to another configuration; use a new --output.')
                self.spent += entry['usd_peak_upper']

    def call(self, messages, max_tokens, rows):
        peak = self.peak
        reserve = (sum(len(m['content'].encode()) for m in messages)*peak['input']
                   + max_tokens*peak['output'] + 100*peak['input'])/1e6
        if self.spent + reserve > self.budget:
            raise SystemExit(f'Budget threshold reached; cumulative peak estimate ${self.spent:.6f}.')
        payload = {'model': self.model, 'messages': messages, 'thinking': {'type': 'disabled'},
                   'response_format': {'type': 'json_object'}, 'max_tokens': max_tokens, 'stream': False}
        req = urllib.request.Request('https://api.deepseek.com/chat/completions',
            data=core.dumps(payload).encode(), headers={'Authorization': 'Bearer '+self.key,
                                                      'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            raise SystemExit(f'API HTTP {exc.code}; stopped without automatic retry.') from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise SystemExit('Network/response failure; no automatic retry. Check provider usage before resuming.') from exc
        usage = result.get('usage')
        if not isinstance(usage, dict) or 'prompt_tokens' not in usage or 'completion_tokens' not in usage:
            raise SystemExit('Missing usage; stopped. Check provider billing before resuming.')
        hit = usage.get('prompt_cache_hit_tokens', usage.get('prompt_tokens_details', {}).get('cached_tokens', 0))
        miss = usage.get('prompt_cache_miss_tokens', usage['prompt_tokens']-hit)
        cost = (hit*peak['cached'] + miss*peak['input'] + usage['completion_tokens']*peak['output'])/1e6
        self.spent += cost
        # Keep the response so interrupted output writes can be recovered without another API call.
        core.append(self.usage_path, {'time': time.time(), 'config_hash': self.config_hash,
            'phase': 'generate', 'model': self.model, 'request_id': result.get('id'), 'usage': usage,
            'usd_peak_upper': cost, 'target_ids': [r['id'] for r in rows], 'response': result})
        return result


def save_response(result, rows, out, config, seg, completed, failed, model):
    try:
        choice = result['choices'][0]
        if choice.get('finish_reason') != 'stop':
            raise ValueError('Incomplete model response')
        obj = json.loads(choice['message']['content'])
        if not isinstance(obj, dict) or set(obj) != {'feedback'} or not isinstance(obj['feedback'], list):
            raise ValueError('Invalid JSON schema')
        items = {}
        for item in obj['feedback']:
            if not isinstance(item, dict) or type(item.get('id')) is not int or not 0 <= item['id'] < len(rows):
                raise ValueError('Invalid target ID')
            if item['id'] in items:
                raise ValueError('Duplicate target ID')
            items[item['id']] = item
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        items, batch_error = {}, str(exc)
    else:
        batch_error = None
    for i, row in enumerate(rows):
        if row['id'] in completed or row['id'] in failed:
            continue
        try:
            if batch_error:
                raise ValueError(batch_error)
            if i not in items:
                raise ValueError('Missing feedback')
            item = {**items[i], 'id': 0}
            text = core.validate(core.dumps({'feedback': [item]}), [row], seg, screen_quality=False)[0]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            core.append(out.with_suffix('.errors.jsonl'), {'id': row['id'], 'config_hash': config,
                'error': str(exc), 'candidate': items.get(i), 'request_id': result.get('id')})
            failed.add(row['id'])
            continue
        core.append(out, {**{k: v for k, v in row.items() if k != 'essay_paragraphs'},
            'feedback': text, 'model': model, 'format_status': 'valid',
            'config_hash': config, 'request_id': result.get('id')})
        completed.add(row['id'])


def generate(args):
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    model = getattr(args, 'model', core.MODEL)
    min_words = getattr(args, 'min_target_words', 6)
    config = fingerprint(args.batch_size, model, min_words)
    completed, failed = set(), set()
    for path, target in [(out, completed), (out.with_suffix('.errors.jsonl'), failed)]:
        if path.exists():
            for row in core.read_jsonl(path):
                if row.get('config_hash') != config:
                    raise SystemExit('Output belongs to another configuration; use a new --output.')
                target.add(row['id'])
    records = list(core.contextual_records(core.read_jsonl(args.records)))
    indexed = {r['id']: r for r in records}
    seg = core.segmenter()
    usage_path = out.with_suffix('.usage.jsonl')
    if usage_path.exists():
        for entry in core.read_jsonl(usage_path):
            if entry.get('config_hash') != config:
                raise SystemExit('Usage belongs to another configuration; use a new --output.')
            save_response(entry['response'], [indexed[i] for i in entry['target_ids']],
                          out, config, seg, completed, failed, model)
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        raise SystemExit('Set DEEPSEEK_API_KEY in your environment; no key is read from files.')
    client = APIClient(key, out, args.budget_usd, config, model)
    selected = 0
    skipped_short = 0
    before_ok, before_bad = len(completed), len(failed)
    scoped = [r for r in records if args.dataset == 'all' or r['dataset'] == args.dataset]
    for batch in core.batches(scoped, args.batch_size):
        rows = []
        for r in batch:
            if r['id'] in completed or r['id'] in failed:
                continue
            if not core.eligible_feedback_target(r, min_words):
                skipped_short += 1
                continue
            rows.append(r)
        if args.limit:
            rows = rows[:max(0, args.limit-selected)]
        if not rows:
            if args.limit and selected >= args.limit:
                break
            continue
        selected += len(rows)
        result = client.call(core.messages(rows), max(256, len(rows)*100), rows)
        save_response(result, rows, out, config, seg, completed, failed, model)
        print(f'Selected {selected}; generated {len(completed)-before_ok}; format errors {len(failed)-before_bad}; model {model}; cumulative peak-priced USD ${client.spent:.6f}', flush=True)
    print(f'Finished: {len(completed)-before_ok} generated; {len(failed)-before_bad} format errors; skipped {skipped_short} short non-targets (min_words={min_words}). Output: {out}')
    if failed:
        print(f'{len(failed)} total format failures remain in {out.with_suffix(".errors.jsonl")}; not automatically retried.')
        raise SystemExit(2)


def estimate(args):
    totals = {}
    model = getattr(args, 'model', core.MODEL)
    min_words = getattr(args, 'min_target_words', 6)
    off, peak = core.model_prices(model)
    records = (r for r in core.read_jsonl(args.records) if args.dataset == 'all' or r['dataset'] == args.dataset)
    skipped_short = 0
    for batch in core.batches(core.contextual_records(records), args.batch_size):
        rows = []
        for r in batch:
            if not core.eligible_feedback_target(r, min_words):
                skipped_short += 1
                continue
            rows.append(r)
        if not rows:
            continue
        stat = totals.setdefault(rows[0]['dataset'], {'paragraphs': 0, 'requests': 0, 'input_tokens_estimate': 0, 'output_tokens_estimate': 0})
        stat['paragraphs'] += len(rows)
        stat['requests'] += 1
        stat['input_tokens_estimate'] += math.ceil(sum(len(m['content']) for m in core.messages(rows))/3.5)+16
        stat['output_tokens_estimate'] += args.output_tokens*len(rows)
    for stat in totals.values():
        cost = (stat['input_tokens_estimate']*off['input'] + stat['output_tokens_estimate']*off['output'])/1e6
        stat.update(usd_off_peak=round(cost,4), usd_peak=round(cost*2,4))
    report = {'version': VERSION, 'model': model, 'min_target_words': min_words,
        'skipped_short_non_targets': skipped_short,
        'prices_usd_per_million_off_peak': off,
        'prices_usd_per_million_peak': peak, 'datasets': totals,
        'assumptions': 'Single generation, no reviewer/retries; short headings/fragments below min_target_words stay in essay context but are not targets; input chars/3.5, no cache discount; output tokens per target includes JSON.',
        'output_tokens_per_target': args.output_tokens,
        'total_usd_off_peak': round(sum(s['usd_off_peak'] for s in totals.values()),4),
        'total_usd_peak': round(sum(s['usd_peak'] for s in totals.values()),4)}
    Path(args.report).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
