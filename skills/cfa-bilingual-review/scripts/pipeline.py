"""Validate concepts, generate paired decks, render final PPTX, and impose Letter handouts."""
import argparse
import ast
import hashlib
import io
import json
import math
import operator
import os
import posixpath
from pathlib import Path
import re
import shutil
import subprocess
import sys
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import fitz
from PIL import ImageFont
from fontTools.ttLib import TTFont as FontToolsFont
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = ('concise', 'expanded')
FINAL_NAMES = {f'review-{v}{suffix}' for v in VARIANTS for suffix in ('.pptx', '-handout.pdf')}
NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def calculate(expression, variables):
    """Arithmetic only. Never execute input code or allow calls/attributes."""
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow}
    require(len(expression) <= 300, 'Calculation too long')
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name) and node.id in variables:
            value = variables[node.id]
            require(type(value) in (int, float) and math.isfinite(value), 'Invalid numeric input')
            return value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            a, b = visit(node.left), visit(node.right)
            require(abs(a) < 1e15 and abs(b) < 1e15, 'Calculation input too large')
            if isinstance(node.op, ast.Pow):
                require(abs(b) <= 12, 'Exponent outside supported range')
            result = ops[type(node.op)](a, b)
            require(type(result) in (int, float) and math.isfinite(result), 'Nonfinite calculation')
            return result
        raise ValueError('Only numbers, variables and arithmetic are allowed')
    return visit(ast.parse(expression, mode='eval').body)


def validate(data):
    roles = json.loads((ROOT / 'assets/theme.json').read_text())['roles']
    require(data.get('schema_version') == 1, 'Expected schema_version 1')
    require(data.get('mode') in ('curriculum', 'public-demo'), 'mode must be curriculum or public-demo')
    for key in ('title', 'scope', 'curriculum_year', 'level'):
        require(isinstance(data.get(key), str) and data[key].strip(), f'Missing {key}')
    sources = data.get('sources', [])
    require(sources and len({s['id'] for s in sources}) == len(sources), 'Source IDs must be unique and nonempty')
    ids = {s['id'] for s in sources}
    for s in sources:
        require(all(s.get(k) for k in ('id', 'role', 'title', 'location')), f'Incomplete source: {s}')
    if data['mode'] == 'curriculum':
        require({'curriculum', 'chinese', 'kaplan'} <= {s['role'] for s in sources}, 'Curriculum mode requires all three input roles')
    require(not any(x.get('status') != 'resolved' for x in data.get('issues', [])), 'Resolve or omit disputed claims before building; unresolved issues remain')
    concepts = data.get('concepts', [])
    require(concepts and len({c['id'] for c in concepts}) == len(concepts), 'Concept IDs must be unique and nonempty')
    objective_layout = data.get('layout') == 'objectives'
    bilingual = data.get('language_profile') == 'bilingual-knowledge-english-examples'
    require(not bilingual or objective_layout, 'Bilingual knowledge requires the objectives layout')
    objectives = data.get('learning_objectives', [])
    if objective_layout:
        require(objectives and len({o['id'] for o in objectives}) == len(objectives), 'Learning objective IDs must be unique')
        for objective in objectives:
            require(all(objective.get(k) for k in ('id', 'text_en', 'text_zh', 'short_zh', 'source', 'locator')), 'Incomplete learning objective')
            require(objective['source'] in ids, 'Unknown learning objective source')
        objective_order = [o['id'] for o in objectives]
        positions = [objective_order.index(c['objective_id']) if c.get('objective_id') in objective_order else -1 for c in concepts]
        require(-1 not in positions and positions == sorted(positions) and set(positions) == set(range(len(objectives))), 'Group slides by every selected learning objective in syllabus order')
    for c in concepts:
        keys = ('id', 'module', 'los', 'term_en', 'term_zh', 'trap', 'notes', 'expanded_notes')
        if not objective_layout:
            keys += ('summary_en', 'summary_zh', 'formula', 'variables', 'conditions', 'expanded')
        for key in keys:
            require(isinstance(c.get(key), str) and c[key].strip(), f'{c.get("id")}: missing {key}')
        require(re.search(r'[\u4e00-\u9fff]', c['term_zh']), f'{c["id"]}: Chinese text missing')
        if objective_layout:
            require(c.get('review_blocks'), f'{c["id"]}: missing review blocks')
            for block in c['review_blocks']:
                require(block.get('label') and (block.get('text') or block.get('formula')), 'A review block needs a label and content')
                if bilingual:
                    require(block.get('label_en'), 'Bilingual blocks need English labels')
                    if block.get('text'):
                        require(block.get('text_en') and re.search(r'[A-Za-z]', block['text_en']), 'Every Chinese knowledge statement needs its English counterpart')
                        require(re.search(r'[\u4e00-\u9fff]', block['text']) and not re.search(r'[\u4e00-\u9fff]', block['text_en']), 'Keep knowledge languages in their respective columns')
                if block.get('formula'):
                    require(block.get('condition') and re.search(r'[\u4e00-\u9fff]', block['condition']), 'Formula guidance must be Chinese')
            guidance = [c['trap'], *[b['condition'] for b in c['review_blocks'] if b.get('condition')]]
            if not bilingual:
                guidance.append(c.get('example', {}).get('prompt', ''))
            for value in guidance:
                require(re.search(r'[\u4e00-\u9fff]', value), 'Guidance and traps must contain Chinese')
                require(not re.search(r'\b(?:Condition|Original example|Source example|Assume|Compare|Ignore)\b', value, re.I), 'Use Chinese guidance without English scaffolding')
            if bilingual:
                require(c.get('recall_en') and c.get('recall_zh'), 'Bilingual recall needs both languages')
                for field in ('prompt', 'solution', 'interpretation'):
                    value = c.get('example', {}).get(field, '')
                    require(value and re.search(r'[A-Za-z]', value) and not re.search(r'[\u4e00-\u9fff]', value), 'Examples must be entirely English')
        require(c.get('references'), f'{c["id"]}: no source references')
        for r in c['references']:
            require(r['source'] in ids and r.get('locator'), f'{c["id"]}: unknown source or missing locator')
        e = c.get('example', {})
        formula_text = '\n'.join(b.get('formula', '') for b in c['review_blocks']) if objective_layout else c['formula']
        for term in c.get('equation_terms', []):
            require(term.get('role') in roles and term.get('text') in formula_text, f'{c["id"]}: invalid equation term or color role')
        if e.get('balance_sheet'):
            sheet = e['balance_sheet']
            require(sheet.get('date') and sheet.get('entity') and sheet.get('unit'), 'Balance sheet needs entity, date and currency unit')
            rows = sheet.get('rows', [])
            require(1 <= len(rows) <= 5, 'Compact balance sheet supports at most five rows; split larger statements')
            row_ids = {r['id'] for r in rows}
            require(len(row_ids) == len(rows), 'Balance-sheet row IDs must be unique')
            for row in rows:
                require(row.get('label') and row.get('role') in roles and type(row.get('amount')) in (int, float) and math.isfinite(row['amount']), 'Invalid balance-sheet row')
                if bilingual:
                    require(re.search(r'[A-Za-z]', row['label']) and not re.search(r'[\u4e00-\u9fff]', row['label']), 'Example balance-sheet labels must be English')
            values = {r['id']: r['amount'] for r in rows}
            for row in rows:
                if row.get('components'):
                    require(all(k in row_ids and k != row['id'] for k in row['components']), 'Unknown balance-sheet component')
                    require(math.isclose(sum(values[k] for k in row['components']), row['amount'], abs_tol=1e-8), 'Balance-sheet subtotal does not reconcile')
            require(all(sheet.get(k) in row_ids for k in ('assets', 'liabilities', 'equity')), 'Balance sheet must identify A, L and E totals')
            require(math.isclose(values[sheet['assets']], values[sheet['liabilities']] + values[sheet['equity']], abs_tol=1e-8), 'Balance sheet does not balance')
        require(e.get('origin') in ('original', 'source'), f'{c["id"]}: label example origin')
        require(all(e.get(k) for k in ('prompt', 'solution', 'interpretation')), f'{c["id"]}: incomplete example')
        if e['origin'] == 'source':
            require(e.get('reference', {}).get('source') in ids and e['reference'].get('locator'), 'Sourced example needs its own locator')
        require(e.get('kind', 'numeric') in ('numeric', 'qualitative'), 'Example kind must be numeric or qualitative')
        if e.get('kind', 'numeric') == 'numeric':
            require(e.get('checks'), f'{c["id"]}: numeric example needs arithmetic checks')
        for check in e.get('checks', []):
            require(type(check.get('expected')) in (int, float), 'Expected value must be numeric')
            actual = calculate(check['expression'], check.get('inputs', {}))
            tolerance = check.get('tolerance', 1e-8)
            require(0 <= tolerance <= 0.01, 'Tolerance must be between 0 and 0.01')
            require(math.isclose(actual, check['expected'], abs_tol=tolerance, rel_tol=1e-9),
                    f'{c["id"]}: example arithmetic failed: {actual} != {check["expected"]}')
            require(check.get('display') and check['display'] in e['solution'], 'Each checked result must appear in the displayed solution')
    return data


def color_runs(text, terms, palette, base_color):
    """Longest-token matching with Latin boundaries; leave operators and unrelated text neutral."""
    aliases = {}
    for term in terms:
        for token in [term['text'], *term.get('aliases', [])]:
            require(token not in aliases or aliases[token] == term['role'], f'Ambiguous color mapping: {token}')
            aliases[token] = term['role']
    if not aliases:
        return [{'text': text, 'color': base_color}]
    pattern = '|'.join((r'(?<![A-Za-z0-9_])' if re.match(r'[A-Za-z0-9_]', token) else '') + re.escape(token) +
                       (r'(?![A-Za-z0-9_])' if re.search(r'[A-Za-z0-9_]$', token) else '')
                       for token in sorted(aliases, key=len, reverse=True))
    result, cursor = [], 0
    for match in re.finditer(pattern, text):
        if match.start() > cursor:
            result.append({'text': text[cursor:match.start()], 'color': base_color})
        result.append({'text': match.group(), 'color': palette[aliases[match.group()]]})
        cursor = match.end()
    if cursor < len(text):
        result.append({'text': text[cursor:], 'color': base_color})
    return result


def wrap(text, font, width):
    """Wrap Latin words and individual CJK characters without shrinking fonts."""
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        tokens = []
        for token in re.findall(r'[\u2e80-\u9fff\uff00-\uffef]|[^\u2e80-\u9fff\uff00-\uffef\s]+|[ \t]+', paragraph):
            if token in '。，、；：！？）》】」』' and tokens and tokens[-1].strip():
                tokens[-1] += token
            else:
                tokens.append(token)
        for token in tokens:
            require(font.getlength(token.strip()) <= width, f'Unbreakable text exceeds layout: {token}')
            if line and font.getlength(line + token) > width:
                lines.append(line.rstrip())
                line = token.lstrip()
            else:
                line += token
        lines.append(line.rstrip())
    return lines


def make_plan(data, font_file, family):
    theme = json.loads((ROOT / 'assets/theme.json').read_text())
    result = {'font_family': family, 'theme': theme, 'concise': [], 'expanded': []}
    font = FontToolsFont(font_file, fontNumber=0)
    font_names = {n.toUnicode().casefold() for n in font['name'].names if n.nameID in (1, 16)}
    require(family.casefold() in font_names, f'Font family {family} does not match selected font file')
    supported = set().union(*(t.cmap.keys() for t in font['cmap'].tables))
    font.close()
    # Check only visible text, not serialized field names or URL metadata.
    for variant in VARIANTS:
        for index, c in enumerate(data['concepts'], 1):
            boxes = []
            def add(name, text, x, y, w, h, size=24, color=None, bold=False, semantic=False):
                missing = {ch for ch in text if not ch.isspace() and ord(ch) not in supported}
                require(not missing, f'Missing glyphs in {family}: {missing}')
                measured = ImageFont.truetype(str(font_file), size)
                lines = wrap(text, measured, w - 8)
                step = math.ceil(size * (1.3 if data.get('language_profile') == 'bilingual-knowledge-english-examples' else 1.43))
                require(len(lines) * step <= h, f'{c["id"]}/{variant}/{name} overflows ({len(lines)} lines); split the concept in BOTH variants or shorten wording')
                for j, line in enumerate(lines):
                    if line:
                        boxes.append(dict(name=f'{c["id"]}-{name}-{j}', text=line, x=x, y=y+j*step,
                                          w=w, h=step, size=size, color=color or theme['ink'], bold=bold,
                                          runs=color_runs(line, c.get('equation_terms', []) if semantic else [], theme['roles'], color or theme['ink'])))
                return len(lines) * step
            expanded = variant == 'expanded'
            cards = []
            if data.get('layout') == 'objectives':
                objective = next(o for o in data['learning_objectives'] if o['id'] == c['objective_id'])
                if data.get('language_profile') == 'bilingual-knowledge-english-examples':
                    cards = plan_bilingual_slide(c, objective, expanded, add, theme, index, len(data['concepts']), data['mode'])
                else:
                    plan_objective_slide(c, objective, expanded, add, theme, index, len(data['concepts']), data['mode'])
                sheet = c['example'].get('balance_sheet') if expanded else None
            else:
                plan_legacy_slide(c, data, expanded, add, font_file, supported, theme)
                sheet = c['example'].get('balance_sheet') if expanded else None
            if sheet:
                widths = (390, 114) if data.get('layout') == 'objectives' else (366, 94)
                for row in sheet['rows']:
                    for value, width in zip((row['label'], str(row['amount'])), widths):
                        require(all(ch.isspace() or ord(ch) in supported for ch in value), 'Missing balance-sheet glyph')
                        require(ImageFont.truetype(str(font_file), 24).getlength(value) <= width, 'Balance-sheet cell exceeds its column')
            source_map = {s['id']: s for s in data['sources']}
            refs_text = '\n'.join(f'[{r["source"]}] {source_map[r["source"]]["title"]}; {r["locator"]}: '
                                  + source_map[r['source']]['location']
                                  + (f'; retrieved {source_map[r["source"]]["retrieved"]}' if source_map[r['source']].get('retrieved') else '')
                                  for r in c['references'])
            notes = c['notes'] + ('\n' + c['expanded_notes'] if expanded else '')
            provenance = f'{c["id"]}\n{data["title"]}\nScope: {data["scope"]}\nModule: {c["module"]}\nLOS: {c["los"]}\n'
            if data.get('layout') == 'objectives':
                provenance += f'Learning outcome: {objective["text_en"]}\n学习目标：{objective["text_zh"]}\n{objective["source"]}: {objective["locator"]}\n'
            result[variant].append({'id': c['id'], 'boxes': boxes, 'balance_sheet': sheet, 'expanded': expanded,
                                    'cards': cards, 'language_profile': data.get('language_profile'),
                                    'layout': data.get('layout', 'legacy'), 'formula_width': 608 if expanded else 1128,
                                    'notes': provenance + notes + '\n' + refs_text})
    return result


def plan_bilingual_slide(c, objective, expanded, add, theme, index, count, mode):
    """Aligned English/Chinese knowledge rows with explicit card boundaries."""
    add('objective', f'{objective["id"]}  {objective["short_zh"]}', 60, 18, 1156, 29, 20, theme['accent'], True)
    add('title', c['term_en'], 60, 52, 1156, 51, 34, bold=True)
    title = c['term_zh'] + ('（公开资料示例）' if mode == 'public-demo' else '')
    add('chinese-title', title, 60, 107, 1156, 36, 24, theme['accent'])
    cards, y = [], 164
    for n, block in enumerate(c['review_blocks']):
        start = y
        label = block['label'] if block['label_en'] in block['label'] else block['label'] + '\n' + block['label_en']
        label_height = add(f'block-{n}-label', label, 60, y, 180, 128, 24, theme['accent'], True)
        if block.get('condition'):
            y += add(f'block-{n}-condition', block['condition'], 258, y, 950, 128, 24)
        if block.get('formula'):
            y += add(f'block-{n}-formula', block['formula'], 258, y, 950, 140, 26, semantic=True)
        divider_y = y
        if block.get('text'):
            en_height = add(f'block-{n}-en', block['text_en'], 258, y, 452, 160, 24, semantic=True)
            zh_height = add(f'block-{n}-text', block['text'], 752, y, 456, 160, 24, semantic=True)
            y += max(en_height, zh_height)
        bottom = max(y, start + label_height)
        cards.append(dict(name=f'knowledge-{n}', x=48, y=start-5, w=1180, h=bottom-start+10,
                          label_divider=247, language_divider=731 if block.get('text') else None,
                          language_y=divider_y, language_h=bottom-divider_y))
        y = bottom + 12
    sheet = c['example'].get('balance_sheet') if expanded else None
    require(y <= (355 if sheet else 500), f'{c["id"]}: bilingual knowledge group overflows; shorten paired wording or split both variants')
    if expanded:
        label = 'Worked example (source)' if c['example']['origin'] == 'source' else 'Worked example (original)'
        if sheet:
            cards.append(dict(name='example',x=48,y=359,w=1180,h=296))
            add('example-label', label + ' - Balance sheet', 60, 365, 1150, 32, 24, theme['accent'], True)
            add('example', c['example']['prompt'], 60, 407, 568, 96, 24, semantic=True)
            add('solution', c['example']['solution'], 60, 511, 568, 105, 26, semantic=True)
            add('interpretation', c['example']['interpretation'], 60, 620, 568, 32, 24)
        else:
            cards.append(dict(name='example',x=48,y=504,w=1180,h=151,label_divider=628))
            add('example-label', label, 60, 510, 1150, 32, 24, theme['accent'], True)
            three_lines = len(c['example']['solution'].splitlines()) == 3
            add('example', c['example']['prompt'], 60, 549, 546, 64 if three_lines else 96, 24, semantic=True)
            add('solution', c['example']['solution'], 646, 549, 562, 102 if three_lines else 68, 26, semantic=True)
            add('interpretation', c['example']['interpretation'], 60 if three_lines else 646, 621, 546 if three_lines else 562, 32, 24)
    else:
        cards.append(dict(name='recall',x=48,y=504,w=1180,h=151,label_divider=731))
        add('recall-label', 'Review / 复习要点', 60, 510, 1150, 32, 24, theme['accent'], True)
        add('recall-en', c['recall_en'], 60, 549, 650, 96, 24)
        add('recall-zh', c['recall_zh'], 752, 549, 456, 96, 24)
    cards.append(dict(name='trap',x=48,y=661,w=1180,h=37))
    add('trap', c['trap'], 60, 665, 1150, 32, 24)
    refs = ', '.join(dict.fromkeys(r['source'] for r in c['references']))
    add('reference', f'{c["id"]}   {refs}     {index:02}/{count:02}',60,704,1156,16,11,theme['muted'])
    return cards


def plan_objective_slide(c, objective, expanded, add, theme, index, count, mode):
    """Full-width knowledge groups, with Chinese guidance preceding each formula."""
    add('objective', f'{objective["id"]}  {objective["short_zh"]}', 60, 18, 1156, 29, 20, theme['accent'], True)
    add('title', c['term_en'], 60, 52, 1156, 51, 34, bold=True)
    chinese_title = c['term_zh'] + ('（公开资料示例）' if mode == 'public-demo' else '')
    add('chinese-title', chinese_title, 60, 107, 1156, 36, 24, theme['accent'])
    y = 160
    for n, block in enumerate(c['review_blocks']):
        start = y
        label_height = add(f'block-{n}-label', block['label'], 60, y, 196, 140, 24, theme['accent'], True)
        if block.get('condition'):
            y += add(f'block-{n}-condition', block['condition'], 270, y, 946, 140, 24)
        if block.get('formula'):
            y += add(f'block-{n}-formula', block['formula'], 270, y, 946, 140, 26, semantic=True)
        if block.get('text'):
            y += add(f'block-{n}-text', block['text'], 270, y, 946, 210, 24, semantic=True)
        y = max(y, start + label_height) + 8
    sheet = c['example'].get('balance_sheet') if expanded else None
    require(y <= (326 if sheet else 476), f'{c["id"]}: objective knowledge group overflows; split the group without shrinking')
    if expanded:
        label = '例题（教材）' if c['example']['origin'] == 'source' else '例题（原创）'
        if sheet:
            add('example-label', label + '：资产负债表', 60, 333, 1156, 35, 24, theme['accent'], True)
            add('example', c['example']['prompt'], 60, 377, 568, 105, 24, semantic=True)
            add('solution', c['example']['solution'], 60, 492, 568, 114, 26, semantic=True)
            add('interpretation', c['example']['interpretation'], 60, 610, 568, 35, 24)
        else:
            add('example-label', label, 60, 487, 1156, 35, 24, theme['accent'], True)
            three_lines = len(c['example']['solution'].splitlines()) == 3
            add('example', c['example']['prompt'], 60, 530, 546, 70 if three_lines else 105, 24, semantic=True)
            add('solution', c['example']['solution'], 646, 530, 570, 114 if three_lines else 76, 26, semantic=True)
            add('interpretation', c['example']['interpretation'], 60 if three_lines else 646, 612, 546 if three_lines else 570, 35, 24)
    else:
        add('recall-label', '复习要点', 60, 487, 196, 35, 24, theme['accent'], True)
        add('recall', c['notes'], 270, 487, 946, 150, 24)
    add('trap', c['trap'], 60, 665, 1156, 35, 24)
    refs = ', '.join(dict.fromkeys(r['source'] for r in c['references']))
    add('reference', f'{c["id"]}   {refs}     {index:02}/{count:02}', 60, 704, 1156, 16, 11, theme['muted'])


def plan_legacy_slide(c, data, expanded, add, font_file, supported, theme):
    w = 608 if expanded else 1128
    add('title', c['term_en'], 60, 35, 1156, 60, 38, bold=True)
    add('chinese-title', c['term_zh'], 60, 96, 1156, 49, 30, theme['accent'])
    add('summary-en', c['summary_en'], 60, 165, w, 106, 24)
    add('summary-zh', c['summary_zh'], 60, 273, w, 69, 24)
    add('formula', c['formula'], 76, 352, w-32, 80, 28, semantic=True)
    add('variables', c['variables'], 60, 438, w, 70, 24, semantic=True)
    add('conditions', c['conditions'], 60, 520, w, 70, 24)
    add('trap', c['trap'], 60, 598, w, 70, 24)
    refs = ', '.join(dict.fromkeys(r['source'] for r in c['references']))
    label = f'{c["id"]}   {refs}' + ('   Public-source demo / 非官方示例' if data['mode'] == 'public-demo' else '')
    add('reference', label, 60, 681, 1156, 25, 16, theme['muted'])
    sheet = c['example'].get('balance_sheet') if expanded else None
    if expanded and sheet:
        add('expanded', c['expanded'], 728, 165, 492, 70, 24)
        sheet_label = 'Original balance sheet / 示例资产负债表' if c['example']['origin'] == 'original' else 'Source balance sheet / 来源资产负债表'
        add('example-label', sheet_label, 728, 245, 492, 35, 24, theme['accent'], True)
        add('example', c['example']['prompt'], 728, 285, 492, 70, 24)
        add('solution', c['example']['solution'], 728, 602, 492, 38, 26, semantic=True)
        add('interpretation', c['example']['interpretation'], 728, 642, 492, 35, 24)
    elif expanded:
        add('expanded', c['expanded'], 728, 165, 492, 140, 24)
        add('example-label', 'Original example' if c['example']['origin'] == 'original' else 'Source example', 728, 317, 492, 35, 24, theme['accent'], True)
        add('example', c['example']['prompt'], 728, 365, 492, 105, 24, semantic=True)
        add('solution', c['example']['solution'], 728, 485, 492, 100, 26, semantic=True)
        add('interpretation', c['example']['interpretation'], 728, 598, 492, 70, 24)


def audit_pptx(path, concepts, variant, family=None):
    with ZipFile(path) as z:
        require(z.testzip() is None, f'Corrupt ZIP: {path}')
        names = set(z.namelist())
        require({'[Content_Types].xml', '_rels/.rels', 'ppt/presentation.xml', 'ppt/_rels/presentation.xml.rels'} <= names, 'Missing required PowerPoint package parts')
        def relationships(part):
            relpath = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part)+'.rels')
            if relpath not in names:
                return {}
            return {r.get('Id'): (r.get('Type'), posixpath.normpath(posixpath.join(posixpath.dirname(part), r.get('Target'))).lstrip('/'))
                    for r in ET.fromstring(z.read(relpath)) if r.get('TargetMode') != 'External'}
        for name in z.namelist():
            if name.endswith(('.xml', '.rels')):
                ET.fromstring(z.read(name))
            if name.endswith('.rels'):
                base = '' if name == '_rels/.rels' else posixpath.dirname(posixpath.dirname(name))
                for rel in ET.fromstring(z.read(name)):
                    if rel.get('TargetMode') != 'External':
                        target = posixpath.normpath(posixpath.join(base, rel.get('Target'))).lstrip('/')
                        require(target in names, f'Broken package relationship: {name} -> {target}')
        if family:
            theme = ET.fromstring(z.read('ppt/theme/theme1.xml'))
            for kind in ('majorFont', 'minorFont'):
                require(theme.find(f'.//a:{kind}/a:latin', NS).get('typeface') == family, 'Theme font mismatch')
        presentation = ET.fromstring(z.read('ppt/presentation.xml'))
        size = presentation.find('p:sldSz', NS)
        require(size is not None and (int(size.get('cx')), int(size.get('cy'))) == (12192000, 6858000), 'Unexpected PowerPoint dimensions')
        rels = relationships('ppt/presentation.xml')
        slides = [rels[n.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')][1]
                  for n in presentation.findall('p:sldIdLst/p:sldId', NS)]
        require(len(slides) == len(concepts), 'Slide count mismatch')
        normalize = lambda t: re.sub(r'\s+', '', t)
        for i, (name, c) in enumerate(zip(slides, concepts), 1):
            root = ET.fromstring(z.read(name))
            if family:
                for node in root.findall('.//a:latin', NS) + root.findall('.//a:ea', NS):
                    require(node.get('typeface') in (family, '+mj-lt', '+mn-lt', '+mj-ea', '+mn-ea', ''), f'Slide {i}: unexpected font {node.get("typeface")}')
            text = normalize(''.join(root.itertext()))
            keys = ['term_en', 'term_zh', 'trap'] if c.get('review_blocks') else ['term_en', 'term_zh', 'summary_en', 'summary_zh', 'formula', 'variables', 'conditions', 'trap']
            if variant == 'expanded' and not c.get('review_blocks'):
                keys.append('expanded')
            for k in keys:
                require(normalize(c[k]) in text, f'Slide {i}: lost {k}')
            for block in c.get('review_blocks', []):
                for key in ('label', 'label_en', 'condition', 'formula', 'text', 'text_en'):
                    if block.get(key):
                        require(normalize(block[key]) in text, f'Slide {i}: lost review block {key}')
            if c.get('recall_en') and variant == 'concise':
                for key in ('recall_en', 'recall_zh'):
                    require(normalize(c[key]) in text, f'Slide {i}: lost bilingual recall')
            require(c['id'] in text, f'Slide {i}: wrong concept order')
            if variant == 'expanded':
                for k in ('prompt', 'solution', 'interpretation'):
                    require(normalize(c['example'][k]) in text, f'Slide {i}: lost example {k}')
                if c['example'].get('balance_sheet'):
                    tables = root.findall('.//a:tbl', NS)
                    require(len(tables) == 1, f'Slide {i}: expected an editable balance-sheet table')
                    table_text = normalize(''.join(tables[0].itertext()))
                    for row in c['example']['balance_sheet']['rows']:
                        require(normalize(row['label']) in table_text and str(row['amount']) in table_text, f'Slide {i}: balance-sheet row missing')
            notes_parts = [target for kind, target in relationships(name).values() if kind.endswith('/notesSlide')]
            require(len(notes_parts) == 1, f'Slide {i}: missing or ambiguous notes relationship')
            notes = normalize(''.join(ET.fromstring(z.read(notes_parts[0])).itertext()))
            require(normalize(c['notes']) in notes and c['id'] in notes, f'Slide {i}: wrong notes')
            if variant == 'expanded':
                require(normalize(c['expanded_notes']) in notes, f'Slide {i}: missing expanded notes')
            for sp in root.findall('.//p:sp', NS):
                xf = sp.find('p:spPr/a:xfrm', NS)
                if xf is not None:
                    off, ext = xf.find('a:off', NS), xf.find('a:ext', NS)
                    require(0 <= int(off.get('x')) and 0 <= int(off.get('y')) and
                            int(off.get('x'))+int(ext.get('cx')) <= 12192000 and
                            int(off.get('y'))+int(ext.get('cy')) <= 6858000, 'Off-slide shape')
    return len(slides)


def render(deck, folder, renderer, soffice):
    folder.mkdir(parents=True, exist_ok=True)
    if renderer == 'powerpoint':
        require(os.name == 'nt', 'PowerPoint COM rendering requires Windows')
        subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'scripts/render_powerpoint.ps1'),
                        '-Deck', str(deck), '-RenderDir', str(folder)], check=True, timeout=240)
    else:
        binary = shutil.which(soffice) or (soffice if Path(soffice).is_file() else None)
        require(binary, 'LibreOffice missing: install it and pass --soffice PATH')
        profile = (folder / 'lo-profile').resolve().as_uri()
        subprocess.run([binary, f'-env:UserInstallation={profile}', '--headless', '--convert-to', 'pdf', '--outdir', str(folder), str(deck)], check=True, timeout=240)
        generated = folder / (deck.stem + '.pdf')
        require(generated.is_file(), 'LibreOffice failed to create PDF')
        generated.rename(folder / 'slides.pdf')
    with fitz.open(folder / 'slides.pdf') as pdf:
        for i, page in enumerate(pdf, 1):
            page.get_pixmap(matrix=fitz.Matrix(1.667, 1.667)).save(folder / f'slide-{i:03}.png')


def handout(slides_path, data, variant, dest, font_file):
    """Compose full vector slide pages and real notes; not a standard slide PDF export."""
    pdfmetrics.registerFont(TTFont('ReviewNotes', str(font_file), subfontIndex=0))
    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=(612, 792), invariant=1)
    style = ParagraphStyle('notes', fontName='ReviewNotes', fontSize=9.5, leading=13, wordWrap='CJK')
    count = len(data['concepts'])
    for start in range(0, count, 3):
        cv.setFont('ReviewNotes', 10)
        cv.drawString(30, 770, f'{data["title"]} - {variant}')
        for slot, c in enumerate(data['concepts'][start:start+3]):
            top = 750 - slot * 238
            cv.setFont('ReviewNotes', 10)
            cv.drawString(438, top-12, c['id'])
            notes = c['notes'] + (' ' + c['expanded_notes'] if variant == 'expanded' else '')
            class NotesMetrics:
                def getlength(self, value):
                    return pdfmetrics.stringWidth(value, 'ReviewNotes', 9.5)
            # Pre-wrap with the same CJK punctuation rules as the slides. ReportLab's
            # CJK auto-wrap can otherwise strand closing punctuation at line starts.
            note_lines = wrap(notes, NotesMetrics(), 142)
            paragraph = Paragraph('<br/>'.join(escape(line) for line in note_lines), style)
            _, height = paragraph.wrap(144, 204)
            require(height <= 204, f'{c["id"]}: handout notes overflow; edit notes without dropping essential explanation')
            paragraph.drawOn(cv, 438, top-27-height)
        cv.setFont('ReviewNotes', 8)
        cv.drawString(30, 18, 'Public-source demonstration; selected topics only.' if data['mode'] == 'public-demo' else data['scope'][:100])
        cv.drawRightString(582, 18, str(start//3 + 1))
        cv.showPage()
    cv.save()
    notes_pdf = fitz.open(stream=buf.getvalue(), filetype='pdf')
    with fitz.open(slides_path) as slides:
        require(len(slides) == count, 'Rendered slide count mismatch')
        for i in range(count):
            top = 42 + (i % 3)*238
            frame = fitz.Rect(30, top, 426, top+222.75)
            notes_pdf[i//3].show_pdf_page(frame, slides, i)
            notes_pdf[i//3].draw_rect(frame, color=(0.18, 0.28, 0.33), width=1.5, overlay=True)
    # Module bookmarks make book-length handouts navigable without changing pages.
    module_starts = [(i, c['module']) for i, c in enumerate(data['concepts'])
                     if i == 0 or c['module'] != data['concepts'][i-1]['module']]
    notes_pdf.set_toc([[1, title, i//3+1] for i, title in module_starts])
    notes_pdf.save(dest, garbage=4, deflate=True)
    notes_pdf.close()


def audit_handout(path, concepts):
    with fitz.open(path) as pdf:
        require(len(pdf) == math.ceil(len(concepts)/3), 'Wrong handout pagination')
        for pno, page in enumerate(pdf):
            require(abs(page.rect.width-612) < .01 and abs(page.rect.height-792) < .01, 'Handout is not Letter portrait')
            for slot, c in enumerate(concepts[pno*3:pno*3+3]):
                top = 42 + slot*238
                thumbnail = page.get_text(clip=fitz.Rect(30, top, 426, top+222.75))
                require(c['id'] in thumbnail, f'Wrong thumbnail order for {c["id"]}')
                note = page.get_text(clip=fitz.Rect(438, top, 584, top+225))
                require(c['id'] in note and len(note.strip()) > len(c['id'])+20, f'Wrong notes for {c["id"]}')
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        require(page.rect.contains(fitz.Rect(span['bbox'])), 'Text outside PDF page')
        return len(pdf)


def build(args):
    data = validate(json.loads(Path(args.concepts).read_text(encoding='utf-8-sig')))
    out, work = Path(args.out).resolve(), Path(args.work).resolve()
    require(out != work and out not in work.parents and work not in out.parents, 'Output and work directories must be separate siblings')
    require(not out.exists() or not any(out.iterdir()), 'Output directory must be empty; choose a fresh path')
    require(not work.exists() or not any(work.iterdir()), 'Work directory must be empty; choose a fresh path')
    font_file = Path(args.font_file)
    require(font_file.is_file(), 'Font file missing; pass --font-file with an installed CJK TrueType font')
    require(Path(args.artifact_module).is_file(), 'Set --artifact-module to Codex @oai/artifact-tool/dist/artifact_tool.mjs')
    plan = make_plan(data, font_file, args.font_family)
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    (work / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    drafts = work / 'decks'
    subprocess.run([args.node, str(ROOT / 'scripts/build_decks.mjs'), str(work / 'plan.json'), str(drafts), args.artifact_module], check=True, timeout=240)
    report = {'mode': data['mode'], 'scope': data['scope'], 'concept_count': len(data['concepts']),
              'renderer': args.renderer, 'font_family': args.font_family, 'font_file': str(font_file),
              'visual_review': 'pending: inspect every slide and every handout page', 'variants': {}}
    for variant in VARIANTS:
        deck = drafts / f'review-{variant}.pptx'
        count = audit_pptx(deck, data['concepts'], variant, args.font_family)
        folder = work / variant
        render(deck, folder, args.renderer, args.soffice)
        # Verify the renderer preserved every concept, English title, and CJK glyph text.
        with fitz.open(folder / 'slides.pdf') as rendered:
            require(len(rendered) == count, 'Render count mismatch')
            for page, c in zip(rendered, data['concepts']):
                normalized = re.sub(r'\s+', '', page.get_text())
                require(c['id'] in normalized and re.sub(r'\s+', '', c['term_zh']) in normalized, 'Renderer lost CJK text or concept ID')
        pdf_path = work / f'review-{variant}-handout.pdf'
        handout(folder / 'slides.pdf', data, variant, pdf_path, font_file)
        pages = audit_handout(pdf_path, data['concepts'])
        with fitz.open(pdf_path) as pdf:
            for i, page in enumerate(pdf, 1):
                page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(folder / f'handout-{i:03}.png')
        report['variants'][variant] = {'slides': count, 'handout_pages': pages, 'arithmetic': 'passed', 'content_and_notes': 'passed'}
    # Publish only after BOTH variants pass; keep diagnostics outside the final directory.
    for variant in VARIANTS:
        shutil.copy2(drafts / f'review-{variant}.pptx', out)
        shutil.copy2(work / f'review-{variant}-handout.pdf', out)
    require({p.name for p in out.iterdir()} == FINAL_NAMES, 'Expected exactly four final artifacts')
    report['sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    (work / 'validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('concepts')
    p.add_argument('--out', required=True)
    p.add_argument('--work', required=True)
    p.add_argument('--node', default='node')
    p.add_argument('--artifact-module', default=os.environ.get('ARTIFACT_TOOL_MODULE', ''))
    p.add_argument('--font-file', default='C:/Windows/Fonts/msyh.ttc')
    p.add_argument('--font-family', default='Microsoft YaHei')
    p.add_argument('--renderer', choices=['powerpoint', 'libreoffice'], default='powerpoint' if os.name == 'nt' else 'libreoffice')
    p.add_argument('--soffice', default='soffice')
    args = p.parse_args()
    try:
        build(args)
    except (ValueError, FileNotFoundError, subprocess.SubprocessError) as error:
        p.exit(1, f'Build failed: {error}\n')


if __name__ == '__main__':
    main()
