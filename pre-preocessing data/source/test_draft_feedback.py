import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import draft_feedback as draft
import feedback as core
import test_feedback


class DraftFeedbackTests(unittest.TestCase):
    def test_prefixes_are_cumulative_and_skip_short(self):
        rows = test_feedback.FeedbackTests.records([
            'Title:',
            'Cars cause pollution in crowded city streets every day.',
            'People need safer transit options that cut daily driving demand.',
        ])
        prefixes = list(draft.draft_prefixes(rows, min_words=6))
        self.assertEqual([p['paragraphs_included'] for p in prefixes], [2, 3])
        self.assertTrue(prefixes[0]['draft'].startswith('Title:'))
        self.assertIn('Cars cause pollution', prefixes[0]['draft'])
        self.assertIn('People need safer', prefixes[1]['draft'])
        self.assertEqual(prefixes[0]['draft'].count('\n\n'), 1)

    def test_inner_double_quotes_still_parse(self):
        raw = ('{"feedback":[{"id":0,"text":"Your draft ends by saying driverless cars '
               '"could bring some problems" without naming any specific hazard from the article?"}]}')
        text = draft.loads_model_json(raw)['feedback'][0]['text']
        self.assertIn('"could bring some problems"', text)
        valid = ('{"feedback":[{"id":0,"text":"How could you connect your claim about pollution '
                 'to a concrete local example that readers can evaluate?"}]}')
        self.assertEqual(draft.loads_model_json(valid), json.loads(valid))

    def test_paragraph_labels_must_match_blank_lines(self):
        one = 'The blimp quotation sits inside this single block of the draft.'
        two = one + '\n\nThe new conclusion only repeats the NASA budget point.'
        named = ('Your final paragraph describes the blimp without explaining how that '
                 'quotation shows Venus is worth studying despite the dangers?')
        self.assertIsNone(draft.unsupported_paragraph_label(named, one))
        self.assertIsNone(draft.unsupported_paragraph_label(named, two))
        last = ('Your last paragraph says life on Mars does not exist, but which photo '
                'in the article actually supports that stronger claim about the planet?')
        self.assertIsNone(draft.unsupported_paragraph_label(last, one))
        second = ('Your second paragraph repeats the NASA point instead of tying the '
                  'mesa claim to the evidence you quoted earlier on?')
        self.assertTrue(draft.unsupported_paragraph_label(second, one))
        self.assertIsNone(draft.unsupported_paragraph_label(second, two))
        plain = ('How could you connect your claim about pollution to a concrete local '
                 'example that readers can evaluate?')
        self.assertIsNone(draft.unsupported_paragraph_label(plain, one))

    def test_batches_take_one_prefix_per_essay(self):
        def prefixes(essay_id):
            texts = [
                f'{essay_id} opening states a claim with enough words to keep.',
                f'{essay_id} second paragraph adds evidence and a short ending.',
            ]
            return list(draft.draft_prefixes(test_feedback.FeedbackTests.records(texts, essay_id), 6))

        groups = list(draft.batches(prefixes('venus') + prefixes('cars'), 8))
        self.assertEqual([[p['essay_id'] for p in group] for group in groups], [
            ['venus', 'cars'],
            ['venus', 'cars'],
        ])
        self.assertEqual([p['paragraphs_included'] for p in groups[0]], [1, 1])
        self.assertEqual([p['paragraphs_included'] for p in groups[1]], [2, 2])

    def test_messages_send_whole_draft_not_span(self):
        rows = [{
            'id': 'a', 'assignment': 'Argue about cars.',
            'draft': 'Cars cause pollution in cities.\n\nBuses could help.',
            'text': 'Cars cause pollution in cities.\n\nBuses could help.',
        }]
        payload = json.loads(draft.messages(rows)[1]['content'])
        self.assertEqual(payload['targets'][0]['draft'], rows[0]['draft'])
        self.assertNotIn('essay_paragraphs', payload)
        self.assertNotIn('span', payload)

    def test_prepare_and_generate_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = Path(tmp)/'natural.jsonl'
            drafts = Path(tmp)/'drafts.jsonl'
            out = Path(tmp)/'labeled.jsonl'
            rows = test_feedback.FeedbackTests.records([
                'Cars cause pollution in crowded city streets every day.',
                'People need safer transit options that cut daily driving demand.',
            ])
            records.write_text(''.join(core.dumps(r)+'\n' for r in rows))
            draft.prepare_drafts(SimpleNamespace(records=str(records), drafts=str(drafts), min_words=6))
            prepared = list(core.read_jsonl(drafts))
            self.assertEqual(len(prepared), 2)
            good = 'How could you connect your claim about pollution to a concrete local example that readers can evaluate?'
            result = {'id': 'mock', 'choices': [{'finish_reason': 'stop', 'message': {
                'content': core.dumps({'feedback': [{'id': 0, 'text': good}]})}}]}
            args = SimpleNamespace(drafts=str(drafts), output=str(out), batch_size=8, dataset='all',
                                   model=core.MODEL, min_words=6, limit=2, budget_usd=1)
            with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test'}), \
                    patch.object(draft.APIClient, 'call', return_value=result) as call:
                draft.generate(args)
            self.assertEqual(call.call_count, 2)
            labeled = list(core.read_jsonl(out))
            self.assertEqual(len(labeled), 2)
            self.assertEqual(set(labeled[0]), {'id', 'config_hash', 'assignment', 'draft', 'feedback'})
            self.assertTrue(all(r['draft'] and r['feedback'] == good for r in labeled))
            export = Path(tmp)/'sft.jsonl'
            draft.export_sft(SimpleNamespace(labeled=str(out), export=str(export), dataset='all'))
            sft = list(core.read_jsonl(export))
            self.assertEqual(set(sft[0]), {'assignment', 'draft', 'feedback'})

    def test_resume_skips_finished_rows_and_replays_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            drafts, out = Path(tmp)/'drafts.jsonl', Path(tmp)/'labeled.jsonl'
            rows = test_feedback.FeedbackTests.records([
                'Cars cause pollution in crowded city streets every day.',
                'People need safer transit options that cut daily driving demand.',
            ])
            prefixes = list(draft.draft_prefixes(rows, min_words=6))
            drafts.write_text(''.join(core.dumps(r)+'\n' for r in prefixes))
            good = 'How could you connect your claim about pollution to a concrete local example that readers can evaluate?'
            result = {'id': 'mock', 'choices': [{'finish_reason': 'stop', 'message': {
                'content': core.dumps({'feedback': [{'id': 0, 'text': good}]})}}]}
            args = SimpleNamespace(drafts=str(drafts), output=str(out), batch_size=8, dataset='all',
                                   model=core.MODEL, min_words=6, limit=2, budget_usd=1)
            with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test'}), \
                    patch.object(draft.APIClient, 'call', return_value=result) as call:
                draft.generate(args)
                draft.generate(args)
                self.assertEqual(call.call_count, 2)
            out.unlink()
            for prefix in prefixes:
                core.append(out.with_suffix('.usage.jsonl'), {
                    'config_hash': draft.fingerprint(8, core.MODEL, 6), 'usd_peak_upper': 0.001,
                    'target_ids': [prefix['id']], 'response': result})
            with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test'}), \
                    patch.object(draft.APIClient, 'call', return_value=result) as call:
                draft.generate(args)
                call.assert_not_called()
            restored = list(core.read_jsonl(out))
            self.assertEqual([r['feedback'] for r in restored], [good, good])
            self.assertEqual(set(restored[0]), {'id', 'config_hash', 'assignment', 'draft', 'feedback'})


if __name__ == '__main__':
    unittest.main()
