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
                'content': core.dumps({'feedback': [{'id': 0, 'text': good}, {'id': 1, 'text': good}]})}}]}
            args = SimpleNamespace(drafts=str(drafts), output=str(out), batch_size=8, dataset='all',
                                   model=core.MODEL, min_words=6, limit=2, budget_usd=1)
            with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test'}), \
                    patch.object(draft.APIClient, 'call', return_value=result) as call:
                draft.generate(args)
            self.assertEqual(call.call_count, 1)
            labeled = list(core.read_jsonl(out))
            self.assertEqual(len(labeled), 2)
            self.assertTrue(all(r['draft'] and r['feedback'] == good for r in labeled))
            export = Path(tmp)/'sft.jsonl'
            draft.export_sft(SimpleNamespace(labeled=str(out), export=str(export), dataset='all'))
            sft = list(core.read_jsonl(export))
            self.assertEqual(set(sft[0]) >= {'assignment', 'draft', 'feedback'}, True)


if __name__ == '__main__':
    unittest.main()
