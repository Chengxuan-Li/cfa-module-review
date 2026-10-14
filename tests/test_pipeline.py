import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import fitz

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/cfa-bilingual-review'
spec = importlib.util.spec_from_file_location('pipeline', SKILL / 'scripts/pipeline.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((SKILL / 'assets/minimal-concepts.json').read_text(encoding='utf-8'))

    def test_valid_synthetic_contract(self):
        self.assertEqual(p.validate(self.data)['concepts'][0]['id'], 'TEST-01')

    def test_wrong_calculation_rejected(self):
        self.data['concepts'][0]['example']['checks'][0]['expected'] = 4
        with self.assertRaisesRegex(ValueError, 'arithmetic failed'):
            p.validate(self.data)

    def test_result_must_be_displayed(self):
        self.data['concepts'][0]['example']['solution'] = 'R = 3'
        with self.assertRaisesRegex(ValueError, 'displayed solution'):
            p.validate(self.data)

    def test_missing_curriculum_inputs_rejected(self):
        self.data['mode'] = 'curriculum'
        with self.assertRaisesRegex(ValueError, 'three input roles'):
            p.validate(self.data)

    def test_source_and_id_failures(self):
        self.data['concepts'][0]['references'][0]['source'] = 'UNKNOWN'
        with self.assertRaisesRegex(ValueError, 'unknown source'):
            p.validate(self.data)
        self.data['concepts'][0]['references'][0]['source'] = 'SYN'
        self.data['concepts'].append(copy.deepcopy(self.data['concepts'][0]))
        with self.assertRaisesRegex(ValueError, 'unique'):
            p.validate(self.data)

    def test_unresolved_conflict_rejected(self):
        self.data['issues'] = [{'status': 'unresolved', 'claim': 'Ambiguous formula'}]
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            p.validate(self.data)

    def test_no_code_execution(self):
        for expression in ['__import__("os")', '(1).__class__', '[1][0]', '2**100', '1/0']:
            with self.subTest(expression=expression), self.assertRaises((ValueError, ZeroDivisionError)):
                p.calculate(expression, {})

    def test_qualitative_example(self):
        self.data['concepts'][0]['example'].update(kind='qualitative', checks=[])
        p.validate(self.data)

    @unittest.skipUnless(Path('C:/Windows/Fonts/msyh.ttc').exists(), 'Windows CJK font is unavailable')
    def test_layout_overflow_rejected_without_shrinking(self):
        self.data['concepts'][0]['summary_en'] = 'This is excessively long content. ' * 50
        with self.assertRaisesRegex(ValueError, 'overflows'):
            p.make_plan(self.data, 'C:/Windows/Fonts/msyh.ttc', 'Microsoft YaHei')

    @unittest.skipUnless(Path('C:/Windows/Fonts/msyh.ttc').exists(), 'Windows CJK font is unavailable')
    def test_font_family_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'does not match'):
            p.make_plan(self.data, 'C:/Windows/Fonts/msyh.ttc', 'Nonexistent font')

    @unittest.skipUnless(Path('C:/Windows/Fonts/msyh.ttc').exists(), 'Windows CJK font is unavailable')
    def test_handout_three_up_and_partial_page(self):
        self.data['title'] = 'Synthetic pagination test'
        concepts = [copy.deepcopy(self.data['concepts'][0]) for _ in range(4)]
        for i, c in enumerate(concepts):
            c.update(id=f'TEST-{i+1:02}', notes=f'Unique note for slide {i+1}. Check the denominator and the units.')
        self.data['concepts'] = concepts
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = fitz.open()
            for c in concepts:
                page = source.new_page(width=960, height=540)
                page.insert_text((60, 60), c['id'], fontsize=28)
            source.save(tmp / 'slides.pdf')
            source.close()
            p.handout(tmp / 'slides.pdf', self.data, 'concise', tmp / 'handout.pdf', 'C:/Windows/Fonts/msyh.ttc')
            self.assertEqual(p.audit_handout(tmp / 'handout.pdf', concepts), 2)
            with fitz.open(tmp / 'handout.pdf') as doc:
                self.assertNotIn('TEST-02', doc[1].get_text())
                self.assertEqual(doc[0].rect, fitz.Rect(0, 0, 612, 792))
            with self.assertRaisesRegex(ValueError, 'thumbnail order'):
                p.audit_handout(tmp / 'handout.pdf', list(reversed(concepts)))

    @unittest.skipUnless(Path('C:/Windows/Fonts/msyh.ttc').exists(), 'Windows CJK font is unavailable')
    def test_long_handout_note_fails(self):
        self.data['concepts'][0]['notes'] = 'A lengthy explanatory note. ' * 150
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'notes overflow'):
                p.handout(Path(tmp) / 'unused.pdf', self.data, 'concise', Path(tmp) / 'out.pdf', 'C:/Windows/Fonts/msyh.ttc')


if __name__ == '__main__':
    unittest.main()
