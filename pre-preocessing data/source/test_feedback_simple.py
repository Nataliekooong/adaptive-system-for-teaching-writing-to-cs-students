import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import feedback as core
import feedback_simple as simple
import test_feedback


class SinglePassTests(unittest.TestCase):
    def test_single_call_failure_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            records, out = Path(tmp)/'records.jsonl', Path(tmp)/'out.jsonl'
            rows = test_feedback.FeedbackTests.records([
                'Cars cause pollution in crowded city streets every day.',
                'People need safer alternatives that actually reduce daily driving.',
            ])
            records.write_text(''.join(core.dumps(r)+'\n' for r in rows))
            args = SimpleNamespace(records=str(records), output=str(out), batch_size=16,
                                   dataset='all', limit=2, budget_usd=1, model=core.MODEL,
                                   min_target_words=6)
            good = 'How could you connect your claim about road safety to a specific example that supports your reasoning?'
            result = {'id': 'mock', 'choices': [{'finish_reason': 'stop', 'message': {'content': core.dumps({'feedback': [{'id':0,'text':good},{'id':1,'text':'Too short.'}]})}}]}
            with patch.dict('os.environ', {'DEEPSEEK_API_KEY':'test'}), patch.object(simple.APIClient, 'call', return_value=result) as call:
                with self.assertRaises(SystemExit):
                    simple.generate(args)
                self.assertEqual(call.call_count, 1)
                sent = json.loads(call.call_args.args[0][1]['content'])
                self.assertEqual(len(sent['essay_paragraphs']), 2)
                with self.assertRaises(SystemExit):
                    simple.generate(args)
                self.assertEqual(call.call_count, 1)
            saved = list(core.read_jsonl(out))
            self.assertEqual(len(saved), 1)
            self.assertNotIn('review_status', saved[0])
            self.assertEqual(len(list(core.read_jsonl(out.with_suffix('.errors.jsonl')))),1)

    def test_replay_recovers_unwritten_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'out.jsonl'
            rows = test_feedback.FeedbackTests.records(['Cars cause pollution in crowded city streets every day.'])
            records=Path(tmp)/'records.jsonl'
            records.write_text(core.dumps(rows[0])+'\n')
            good='How could you connect your claim about road safety to a specific example that supports your reasoning?'
            result={'id':'mock','choices':[{'finish_reason':'stop','message':{'content':core.dumps({'feedback':[{'id':0,'text':good}]})}}]}
            core.append(out.with_suffix('.usage.jsonl'),{'config_hash':simple.fingerprint(16, core.MODEL, 6),'usd_peak_upper':0.001,'target_ids':[rows[0]['id']],'response':result})
            args=SimpleNamespace(records=str(records),output=str(out),batch_size=16,dataset='all',limit=1,budget_usd=1,model=core.MODEL,min_target_words=6)

    def test_short_headings_stay_in_context_but_are_not_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            records, out = Path(tmp)/'records.jsonl', Path(tmp)/'out.jsonl'
            rows = test_feedback.FeedbackTests.records(['Distracted Driving:', 'Cars cause pollution in cities every day.'])
            records.write_text(''.join(core.dumps(r)+'\n' for r in rows))
            args = SimpleNamespace(records=str(records), output=str(out), batch_size=16,
                                   dataset='all', limit=2, budget_usd=1, model=core.MODEL,
                                   min_target_words=6)
            good = 'How could you connect your claim about road safety to a specific example that supports your reasoning?'
            result = {'id': 'mock', 'choices': [{'finish_reason': 'stop', 'message': {'content': core.dumps({'feedback': [{'id': 0, 'text': good}]})}}]}
            with patch.dict('os.environ', {'DEEPSEEK_API_KEY': 'test'}), patch.object(simple.APIClient, 'call', return_value=result) as call:
                simple.generate(args)
            self.assertEqual(call.call_count, 1)
            sent = json.loads(call.call_args.args[0][1]['content'])
            self.assertEqual(len(sent['essay_paragraphs']), 2)
            self.assertEqual(sent['essay_paragraphs'][0]['text'], 'Distracted Driving:')
            self.assertEqual(sent['targets'], [{'id': 0, 'paragraph_index': 1}])
            self.assertEqual(len(list(core.read_jsonl(out))), 1)
            with patch.dict('os.environ',{'DEEPSEEK_API_KEY':'test'}),patch.object(simple.APIClient,'call') as call:
                simple.generate(args)
                call.assert_not_called()
            self.assertEqual(list(core.read_jsonl(out))[0]['feedback'],good)

if __name__ == '__main__':
    unittest.main()
