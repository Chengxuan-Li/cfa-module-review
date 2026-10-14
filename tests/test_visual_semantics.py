import json
import unittest
from test_pipeline import p, SKILL


class SemanticTests(unittest.TestCase):
    def test_token_boundaries_and_longest_match(self):
        terms = [dict(text='A',role='assets',aliases=[]),dict(text='Average assets',role='assets',aliases=[]),dict(text='L',role='liabilities',aliases=[])]
        runs = p.color_runs('Average assets = A + L; ANALYSIS',terms,{'assets':'blue','liabilities':'orange'},'black')
        self.assertEqual(''.join(r['text'] for r in runs),'Average assets = A + L; ANALYSIS')
        self.assertEqual([r['text'] for r in runs if r['color']=='blue'],['Average assets','A'])
        self.assertTrue(runs[-1]['text'].endswith('ANALYSIS'))
        self.assertEqual(runs[-1]['color'],'black')

    def test_conflicting_aliases_rejected(self):
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            p.color_runs('A',[dict(text='A',role='assets'),dict(text='A',role='equity')],{},'black')

    def test_balance_sheet_totals_and_equation(self):
        data=json.loads((SKILL/'assets/minimal-concepts.json').read_text(encoding='utf-8'))
        sheet=dict(entity='Test',date='2025-12-31',unit='USD m',assets='a',liabilities='l',equity='e',rows=[
            dict(id='ca',label='Current assets',amount=4,role='assets'),
            dict(id='nca',label='Noncurrent assets',amount=6,role='assets'),
            dict(id='a',label='Assets',amount=10,role='assets',components=['ca','nca']),
            dict(id='l',label='Liabilities',amount=7,role='liabilities'),
            dict(id='e',label='Equity',amount=3,role='equity')])
        data['concepts'][0]['example']['balance_sheet']=sheet
        p.validate(data)
        sheet['rows'][0]['amount']=5
        with self.assertRaisesRegex(ValueError,'subtotal'):
            p.validate(data)
        sheet['rows'][0]['amount']=4
        sheet['rows'][4]['amount']=4
        with self.assertRaisesRegex(ValueError,'does not balance'):
            p.validate(data)


if __name__=='__main__':
    unittest.main()
