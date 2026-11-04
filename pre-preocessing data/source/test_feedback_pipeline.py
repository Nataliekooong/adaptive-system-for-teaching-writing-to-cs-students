import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error

import feedback as core
import feedback_pipeline as pipeline
import test_feedback

GOOD = 'How could you connect your claim about road safety to a specific example that supports your reasoning?'
STRENGTH = 'Your opening question gives readers a clear focus; how does this choice prepare them to consider your argument about road safety?'


def candidate(i, paragraph, mode='improvement'):
    return {'id': i, 'mode': mode, 'paragraph_role': 'claim',
            'observation': 'The claim needs supporting evidence.' if mode == 'improvement' else 'The opening question establishes focus.',
            'evidence': [{'paragraph_index': paragraph['paragraph_index'], 'quote': paragraph['text']}],
            'context_already_addresses_issue': False if mode == 'improvement' else None,
            'context_note': 'No example supports the claim elsewhere.' if mode == 'improvement' else 'The essay develops the opening question.',
            'feedback': GOOD if mode == 'improvement' else STRENGTH}


def review(i, paragraph, passed=True):
    checks = {name: True for name in pipeline.CHECKS}
    checks['context_respected'] = passed
    return {'id': i, 'passed': passed, 'checks': checks,
            'reason': 'The feedback is grounded in the target.' if passed else 'The essay already explains this connection; choose a different issue or reflect on the strength.',
            'evidence': [{'paragraph_index': paragraph['paragraph_index'], 'quote': paragraph['text']}]}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = test_feedback.FeedbackTests.records(['Cars matter.', 'Road safety matters.'])
        self.records = self.root/'records.jsonl'
        self.records.write_text(''.join(core.dumps(r)+'\n' for r in self.rows))
        self.args = SimpleNamespace(records=str(self.records), output=str(self.root/'output.jsonl'),
                                    batch_size=16, limit=0, budget_usd=1, retry_failed=False, dataset='all')
        self.requests = []
        self.responses = []
        self.transform = lambda phase, data, items: items

    def fake_urlopen(self, req, **kwargs):
        payload = json.loads(req.data)
        phase = 'review' if payload['messages'][0]['content'] == pipeline.REVIEWER_SYSTEM else 'generate'
        data = json.loads(payload['messages'][1]['content'])
        self.requests.append((phase, data))
        self.assertEqual(len(data['essay_paragraphs']), 2)
        if phase == 'generate':
            items = [candidate(t['id'], data['essay_paragraphs'][t['paragraph_index']]) for t in data['targets']]
        else:
            self.assertTrue(all(set(c) == {'id', 'mode', 'feedback'} for c in data['candidates']))
            self.assertNotIn('observation', core.dumps(data))
            items = [review(t['id'], data['essay_paragraphs'][t['paragraph_index']]) for t in data['targets']]
        items = self.transform(phase, data, items)
        result = {'id': f'mock-{len(self.requests)}', 'usage': {'prompt_tokens': 100, 'completion_tokens': 40},
                  'choices': [{'finish_reason': 'stop', 'message': {'content': core.dumps({
                      'candidates' if phase == 'generate' else 'reviews': items})}}]}
        self.responses.append(result)
        return io.BytesIO(json.dumps(result).encode())

    def run_pipeline(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'mock-not-a-real-key'}), patch('urllib.request.urlopen', side_effect=self.fake_urlopen):
            pipeline.generate(self.args)

    def output(self):
        path = Path(self.args.output)
        return list(core.read_jsonl(path)) if path.exists() else []

    def states(self):
        return pipeline.Journal(self.root/'output.audit.jsonl', pipeline.fingerprint(16)).states

    def test_strength_path_and_resume_keep_full_essay(self):
        def transform(phase, data, items):
            if phase == 'generate':
                return [candidate(t['id'], data['essay_paragraphs'][t['paragraph_index']], 'strength_reflection') for t in data['targets']]
            return items
        self.transform = transform
        self.args.limit = 1
        self.run_pipeline()
        self.run_pipeline()
        self.run_pipeline()
        self.assertEqual([phase for phase, _ in self.requests], ['generate', 'review', 'generate', 'review'])
        self.assertEqual([d['targets'][0]['paragraph_index'] for _, d in self.requests], [0, 0, 1, 1])
        self.assertEqual(len(self.output()), 2)
        for row in self.output():
            self.assertEqual(row['feedback_mode'], 'strength_reflection')
            self.assertEqual(row['review_status'], 'approved')
            self.assertNotIn('observation', row)
            self.assertNotIn('essay_paragraphs', row)
        usage = list(core.read_jsonl(self.root/'output.usage.jsonl'))
        self.assertEqual(len(usage), 4)
        self.assertEqual({u['phase'] for u in usage}, {'generate', 'review'})

    def test_only_rejected_target_is_regenerated(self):
        reviews = 0
        def transform(phase, data, items):
            nonlocal reviews
            if phase == 'review':
                reviews += 1
                if reviews == 1:
                    items[1] = review(1, data['essay_paragraphs'][1], False)
            return items
        self.transform = transform
        self.run_pipeline()
        self.assertEqual([(p, [t['paragraph_index'] for t in d['targets']]) for p, d in self.requests],
                         [('generate', [0, 1]), ('review', [0, 1]), ('generate', [1]), ('review', [1])])
        self.assertIn('already explains', self.requests[2][1]['revision_requests'][0]['review_findings'])
        self.assertEqual(len(self.output()), 2)
        self.assertEqual(self.states()['one0']['generation_attempts'], 1)
        self.assertEqual(self.states()['one1']['generation_attempts'], 2)

    def test_invalid_candidate_does_not_discard_good_target(self):
        def transform(phase, data, items):
            if len(self.requests) == 1:
                items[1]['feedback'] = 'Too short.'
            return items
        self.transform = transform
        self.run_pipeline()
        self.assertEqual([(p, [t['paragraph_index'] for t in d['targets']]) for p, d in self.requests],
                         [('generate', [0, 1]), ('review', [0]), ('generate', [1]), ('review', [1])])
        self.assertEqual(len(self.output()), 2)

    def test_missing_review_is_retried_without_regenerating(self):
        def transform(phase, data, items):
            if len(self.requests) == 2:
                return items[:1]
            return items
        self.transform = transform
        self.run_pipeline()
        self.assertEqual([p for p, _ in self.requests], ['generate', 'review', 'review'])
        self.assertEqual(self.requests[2][1]['targets'], [{'id': 0, 'paragraph_index': 1}])
        self.assertEqual(len(self.output()), 2)

    def test_review_rejects_inconsistent_verdict_and_fabricated_evidence(self):
        row = next(core.contextual_records(self.rows))
        item = review(0, row)
        item['checks']['grounded'] = False
        with self.assertRaises(ValueError):
            pipeline.check_review(item, row)
        item = review(0, row)
        item['evidence'][0]['quote'] = 'This quotation does not exist.'
        with self.assertRaises(ValueError):
            pipeline.check_review(item, row)

    def test_grounding_and_mode_validation(self):
        row = next(core.contextual_records(self.rows))
        item = candidate(0, row)
        item['context_already_addresses_issue'] = True
        with self.assertRaises(ValueError):
            pipeline.check_candidate(item, row, core.segmenter())
        item = candidate(0, row, 'strength_reflection')
        self.assertEqual(pipeline.check_candidate(item, row, core.segmenter())['mode'], 'strength_reflection')
        item['evidence'][0]['quote'] = 'Invented evidence'
        with self.assertRaises(ValueError):
            pipeline.check_candidate(item, row, core.segmenter())

    def test_interruption_resumes_review_without_regeneration(self):
        def transform(phase, data, items):
            if phase == 'review':
                raise urllib.error.URLError('simulated timeout')
            return items
        self.transform = transform
        with self.assertRaises(SystemExit):
            self.run_pipeline()
        self.assertEqual(self.output(), [])
        self.transform = lambda phase, data, items: items
        self.run_pipeline()
        self.assertEqual([p for p, _ in self.requests], ['generate', 'review', 'review'])
        self.assertEqual(len(self.output()), 2)

    def test_approved_audit_recovers_if_output_write_interrupted(self):
        real_append = core.append
        def append(path, obj):
            if Path(path) == Path(self.args.output):
                raise OSError('simulated output write failure')
            return real_append(path, obj)
        with patch('feedback.append', side_effect=append), self.assertRaises(OSError):
            self.run_pipeline()
        self.assertEqual(len(self.requests), 2)
        self.run_pipeline()
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(len(self.output()), 2)

    def test_exhausted_targets_are_separate_and_not_silently_retried(self):
        def transform(phase, data, items):
            if phase == 'review':
                return [review(t['id'], data['essay_paragraphs'][t['paragraph_index']], False) for t in data['targets']]
            return items
        self.transform = transform
        with self.assertRaises(SystemExit) as raised:
            self.run_pipeline()
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(len(self.requests), 6)
        self.assertEqual(self.output(), [])
        self.assertEqual(len(list(core.read_jsonl(self.root/'output.needs_review.jsonl'))), 2)
        with self.assertRaises(SystemExit):
            self.run_pipeline()
        self.assertEqual(len(self.requests), 6)
        self.args.retry_failed = True
        self.transform = lambda phase, data, items: items
        self.run_pipeline()
        self.assertEqual(len(self.output()), 2)
        self.assertEqual(list(core.read_jsonl(self.root/'output.needs_review.jsonl')), [])

    def test_budget_stop_makes_no_calls_and_does_not_spend_attempt(self):
        self.args.budget_usd = 1e-10
        with self.assertRaises(SystemExit):
            self.run_pipeline()
        self.assertEqual(self.requests, [])
        self.assertEqual(self.states(), {})

    def test_duplicate_and_missing_ids_fail_only_affected_targets(self):
        items, errors = pipeline.items_by_id(core.dumps({'reviews': [{'id': 0}, {'id': 1}, {'id': 1}]}), 'reviews', 3)
        self.assertEqual(set(errors), {1, 2})
        self.assertIn(0, items)

    def test_missing_single_focus_is_not_implicitly_approved(self):
        row = next(core.contextual_records(self.rows))
        item = review(0, row)
        del item['checks']['single_focus']
        with self.assertRaisesRegex(ValueError, "missing \\['single_focus'\\]"):
            pipeline.check_review(item, row)
        self.assertNotIn('single_focus', item['checks'])

    def test_matching_redundant_index_is_accepted_but_wrong_index_is_not(self):
        row = next(core.contextual_records(self.rows))
        item = candidate(0, row)
        item['paragraph_index'] = 0
        normalized = pipeline.check_candidate(item, row, core.segmenter())
        self.assertNotIn('paragraph_index', normalized)
        item['paragraph_index'] = 1
        with self.assertRaisesRegex(ValueError, 'must match target'):
            pipeline.check_candidate(item, row, core.segmenter())
        item = candidate(0, row)
        del item['paragraph_role']
        with self.assertRaisesRegex(ValueError, 'missing fields.*paragraph_role'):
            pipeline.check_candidate(item, row, core.segmenter())

    def test_wrong_evidence_index_reports_actual_location_without_rewriting_it(self):
        row = next(core.contextual_records(self.rows))
        evidence = [{'paragraph_index': 0, 'quote': 'Road safety matters.'}]
        with self.assertRaisesRegex(ValueError, 'occurs in paragraph_index \\[1\\]'):
            pipeline.check_evidence(evidence, row)
        self.assertEqual(evidence[0]['paragraph_index'], 0)

    def test_old_format_failure_resumes_review_only_and_ignores_new_targets(self):
        # Reproduce the old v5 log format: a valid candidate exhausted reviewer
        # schema retries; there is no explicit failure_kind in saved snapshots.
        row = self.rows[1]
        config = pipeline.fingerprint(16)
        state = {'status': 'candidate_ready', 'generation_attempts': 1,
                 'review_attempts': 3, 'candidate': candidate(0, row),
                 'candidate_request_id': 'old-generator-request', 'review': None,
                 'failure': 'All seven review checks must be booleans'}
        log = self.root/'output.audit.jsonl'
        core.append(log, {'config_hash': config, 'id': row['id'], 'event': 'review_invalid', 'state': state})
        core.append(log, {'config_hash': config, 'id': row['id'], 'event': 'review_attempts_exhausted',
                          'state': {**state, 'status': 'needs_review'}})
        self.args.retry_failed = True
        self.args.failed_only = True
        self.run_pipeline()
        self.assertEqual([phase for phase, _ in self.requests], ['review'])
        self.assertEqual(self.requests[0][1]['targets'], [{'id': 0, 'paragraph_index': 1}])
        self.assertEqual([r['id'] for r in self.output()], ['one1'])
        self.assertEqual(self.output()[0]['request_id'], 'old-generator-request')
        self.assertEqual(self.states()['one1']['generation_attempts'], 1)
        self.run_pipeline()
        self.assertEqual(len(self.requests), 1)


if __name__ == '__main__':
    unittest.main()
