import json
from pathlib import Path
import unittest

import feedback as f


class FeedbackTests(unittest.TestCase):
    @staticmethod
    def records(texts, essay_id='one'):
        context = [{'paragraph_index': i, 'text': text} for i, text in enumerate(texts)]
        return [{'id': essay_id + str(i), 'dataset': 'test', 'essay_id': essay_id,
                 'paragraph_index': i, 'source_paragraph_index': i, 'text': text,
                 'unit_type': 'natural_paragraph', 'assignment': '',
                 'essay_paragraph_count': len(texts), 'essay_hash': f.digest(f.dumps(context))}
                for i, text in enumerate(texts)]

    def test_full_context_survives_batch_boundaries(self):
        rows = self.records(['Businesspeople and students agree.', 'Why do they agree?', 'Here is the explanation.'])
        groups = list(f.batches(f.contextual_records(rows), 1))
        for group in groups:
            prompt = json.loads(f.messages(group)[1]['content'])
            self.assertEqual(len(prompt['essay_paragraphs']), 3)
            self.assertEqual(len(prompt['targets']), 1)
            self.assertEqual(prompt['essay_paragraphs'][2]['text'], 'Here is the explanation.')

    def test_rejects_incomplete_and_legacy_records(self):
        rows = self.records(['First.', 'Second.'])
        with self.assertRaises(ValueError):
            list(f.contextual_records(rows[:1]))
        rows[0]['unit_type'] = 'short_paragraph'
        with self.assertRaises(ValueError):
            list(f.contextual_records(rows))

    def test_separate_essays_do_not_share_context(self):
        groups = list(f.batches(f.contextual_records(self.records(['First.']) + self.records(['Second.'], 'two')), 16))
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[1][0]['essay_paragraphs'], [{'paragraph_index': 0, 'text': 'Second.'}])

    def test_observed_quality_failures(self):
        fixtures = json.loads((Path(__file__).parent/'quality_regression_cases.json').read_text())
        for row in fixtures:
            with self.subTest(number=row['original_line']):
                self.assertTrue(f.quality_flags(row['feedback'], row))
                with self.assertRaises(ValueError):
                    f.validate(f.dumps({'feedback': [{'id': 0, 'text': row['feedback']}]}), [row], f.segmenter())

    def test_requests_for_evidence_are_not_assertions(self):
        row = {'text': 'Cars cause pollution.'}
        self.assertEqual(f.quality_flags('What statistic could you cite to support your claim about pollution?', row), [])
        row['text'] = 'Cars account for 12 percent of emissions.'
        self.assertEqual(f.quality_flags('How does your quoted statistic support your claim?', row), [])

    def test_paragraph_boundaries_and_coverage(self):
        essay = {'essay_id': 'x', 'text': 'First sentence. Second sentence.\n\nThird sentence.'}
        units = f.natural_paragraphs(essay)
        self.assertEqual([u['text'] for u in units], ['First sentence. Second sentence.', 'Third sentence.'])
        self.assertEqual([u['source_paragraph_index'] for u in units], [0, 1])
        self.assertTrue(all(essay['text'][u['start']:u['end']] == u['text'] for u in units))

    def test_sefora_keeps_internal_linebreaks(self):
        bodies = ['First line\ncontinues here.', 'Next paragraph.']
        essay = {'essay_id': 'x', 'paragraph_bodies': bodies, 'text': '\n\n'.join(bodies)}
        self.assertEqual([u['text'] for u in f.natural_paragraphs(essay)], bodies)

    def test_long_paragraph_remains_intact(self):
        text = 'A complete sentence with several words. ' * 100
        units = f.natural_paragraphs({'essay_id': 'x', 'text': text})
        self.assertEqual([u['text'] for u in units], [text.strip()])

    def test_abbreviation_and_spans(self):
        text = 'Dr. Smith agrees. Why does this matter?'
        spans = f.segmenter().segment(text)
        self.assertEqual(len(spans), 2)
        self.assertTrue(all(text[s.start:s.end] == s.sent for s in spans))

    def test_validation(self):
        good = 'How could you connect your claim about road safety to a specific example that supports your reasoning?'
        self.assertEqual(f.validate(f.dumps({'feedback': [{'id': 0, 'text': good}]}), [{'text': 'Cars matter.'}], f.segmenter()), {0: good})
        for items in [[], [{'id': 0, 'text': 'Too short.'}], [{'id': 0, 'text': good}]*2]:
            with self.assertRaises(ValueError):
                f.validate(f.dumps({'feedback': items}), [{'text': 'Cars matter.'}], f.segmenter())



if __name__ == '__main__':
    unittest.main()
