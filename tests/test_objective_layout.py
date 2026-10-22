import copy
import json
import unittest
from pathlib import Path
from PIL import ImageFont

from test_pipeline import p, SKILL


class ObjectiveLayoutTests(unittest.TestCase):
    def test_packaged_objective_fixture_validates(self):
        data = json.loads((SKILL / 'assets/objectives-concepts.json').read_text(encoding='utf-8'))
        p.validate(data)
        self.assertEqual(data['language_profile'], 'bilingual-knowledge-english-examples')

    def setUp(self):
        self.data = json.loads((SKILL / 'assets/minimal-concepts.json').read_text(encoding='utf-8'))
        source = self.data['sources'][0]['id']
        self.data.update(layout='objectives', learning_objectives=[dict(
            id='LO1', text_en='Compare two quantities.', text_zh='比较两个数量',
            short_zh='比较两个数量', source=source, locator='Synthetic example')])
        c = self.data['concepts'][0]
        c.update(objective_id='LO1', notes='比较数量的定义、单位和适用条件。', trap='易错点：先核对单位。',
                 review_blocks=[dict(label='关系比较', condition='公式条件：数量范围和单位相同。', formula='R = A / B'),
                                dict(label='变量解释', text='A 与 B 为同范围数量。')])
        c['equation_terms'] = [dict(text='A', role='assets'), dict(text='B', role='cost')]
        c['example']['prompt'] = '同一期间有两项数量，计算其比率。'
        c['example']['interpretation'] = '比率反映两项数量之间的关系。'
        c['example']['solution'] = 'R = 2'

    def test_objective_coverage_and_order(self):
        p.validate(self.data)
        self.data['learning_objectives'].append({**self.data['learning_objectives'][0], 'id':'LO2'})
        with self.assertRaisesRegex(ValueError, 'every selected'):
            p.validate(self.data)
        second = copy.deepcopy(self.data['concepts'][0])
        second.update(id='TEST-02', objective_id='LO2')
        self.data['concepts'].append(second)
        p.validate(self.data)
        self.data['concepts'].reverse()
        with self.assertRaisesRegex(ValueError, 'syllabus order'):
            p.validate(self.data)

    def test_each_formula_requires_chinese_guidance(self):
        block = self.data['concepts'][0]['review_blocks'][0]
        del block['condition']
        with self.assertRaisesRegex(ValueError, 'guidance must be Chinese'):
            p.validate(self.data)
        block['condition'] = 'Condition: 同一期间。'
        with self.assertRaisesRegex(ValueError, 'English scaffolding'):
            p.validate(self.data)

    def bilingual_data(self):
        data = copy.deepcopy(self.data)
        data['language_profile'] = 'bilingual-knowledge-english-examples'
        c = data['concepts'][0]
        for block, label in zip(c['review_blocks'], ['Relationship', 'Terms']):
            block['label_en'] = label
            if block.get('text'):
                block['text_en'] = 'A and B cover the same scope.'
        c.update(recall_en='Compare scope and units.', recall_zh='比较范围与单位。')
        c['example'].update(prompt='Compare two quantities in the same period.',
                            interpretation='The ratio compares the quantities.')
        return data

    def test_bilingual_profile_requires_actual_paired_statements(self):
        data = self.bilingual_data()
        p.validate(data)
        del data['concepts'][0]['review_blocks'][1]['text_en']
        with self.assertRaisesRegex(ValueError, 'English counterpart'):
            p.validate(data)

    def test_bilingual_profile_requires_english_examples(self):
        data = self.bilingual_data()
        data['concepts'][0]['example']['prompt'] += ' 同一期间。'
        with self.assertRaisesRegex(ValueError, 'entirely English'):
            p.validate(data)

    @unittest.skipUnless(Path('C:/Windows/Fonts/msyh.ttc').exists(), 'Windows CJK font is unavailable')
    def test_bilingual_columns_and_cards_preserve_shared_content(self):
        plan = p.make_plan(p.validate(self.bilingual_data()), 'C:/Windows/Fonts/msyh.ttc', 'Microsoft YaHei')
        cores = []
        for variant in p.VARIANTS:
            slide = plan[variant][0]
            cores.append([b for b in slide['boxes'] if '-block-' in b['name']])
            en = next(b for b in cores[-1] if '-block-1-en-' in b['name'])
            zh = next(b for b in cores[-1] if '-block-1-text-' in b['name'])
            self.assertEqual(en['y'], zh['y'])
            self.assertLess(en['x'] + en['w'], zh['x'])
            card = next(c for c in slide['cards'] if c['name'] == 'knowledge-1')
            self.assertLess(en['x'] + en['w'], card['language_divider'])
            self.assertLess(card['language_divider'], zh['x'])
            self.assertGreaterEqual(min(b['size'] for b in cores[-1]), 24)
        self.assertEqual(cores[0], cores[1])

    @unittest.skipUnless(Path('C:/Windows/Fonts/msyh.ttc').exists(), 'Windows CJK font is unavailable')
    def test_shared_content_and_guidance_before_formula(self):
        plan = p.make_plan(p.validate(self.data), 'C:/Windows/Fonts/msyh.ttc', 'Microsoft YaHei')
        common = []
        for variant in p.VARIANTS:
            boxes = plan[variant][0]['boxes']
            blocks = [b for b in boxes if '-block-' in b['name']]
            common.append(blocks)
            condition = next(b for b in blocks if '-condition-' in b['name'])
            formula = next(b for b in blocks if '-formula-' in b['name'])
            self.assertLess(condition['y'], formula['y'])
            self.assertGreaterEqual(min(b['size'] for b in blocks), 24)
            self.assertIn('Compare two quantities.', plan[variant][0]['notes'])
        self.assertEqual(common[0], common[1])

    @unittest.skipUnless(Path('C:/Windows/Fonts/msyh.ttc').exists(), 'Windows CJK font is unavailable')
    def test_overloaded_knowledge_group_is_rejected(self):
        self.data['concepts'][0]['review_blocks'] *= 8
        with self.assertRaisesRegex(ValueError, 'overflows'):
            p.make_plan(self.data, 'C:/Windows/Fonts/msyh.ttc', 'Microsoft YaHei')

    @unittest.skipUnless(Path('C:/Windows/Fonts/msyh.ttc').exists(), 'Windows CJK font is unavailable')
    def test_chinese_closing_punctuation_stays_with_previous_token(self):
        font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 24)
        text = '同一单位。分母范围一致，才能比较。'
        lines = p.wrap(text, font, font.getlength('同一单位'))
        self.assertEqual(''.join(lines), text)
        self.assertTrue(all(line[0] not in '。，、；：！？）》】」』' for line in lines))
        self.assertTrue(all(font.getlength(line) <= font.getlength('同一单位') for line in lines))


if __name__ == '__main__':
    unittest.main()
