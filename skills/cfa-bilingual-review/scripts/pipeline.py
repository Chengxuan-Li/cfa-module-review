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
    for c in concepts:
        for key in ('id', 'module', 'los', 'term_en', 'term_zh', 'summary_en', 'summary_zh',
                    'formula', 'variables', 'conditions', 'trap', 'expanded', 'notes', 'expanded_notes'):
            require(isinstance(c.get(key), str) and c[key].strip(), f'{c.get("id")}: missing {key}')
        require(re.search(r'[\u4e00-\u9fff]', c['term_zh'] + c['summary_zh']), f'{c["id"]}: Chinese text missing')
        require(c.get('references'), f'{c["id"]}: no source references')
        for r in c['references']:
            require(r['source'] in ids and r.get('locator'), f'{c["id"]}: unknown source or missing locator')
        e = c.get('example', {})
        for term in c.get('equation_terms', []):
            require(term.get('role') in roles and term.get('text') in c['formula'], f'{c["id"]}: invalid equation term or color role')
        if e.get('balance_sheet'):
            sheet = e['balance_sheet']
            require(sheet.get('date') and sheet.get('entity') and sheet.get('unit'), 'Balance sheet needs entity, date and currency unit')
            rows = sheet.get('rows', [])
            require(1 <= len(rows) <= 5, 'Compact balance sheet supports at most five rows; split larger statements')
            row_ids = {r['id'] for r in rows}
            require(len(row_ids) == len(rows), 'Balance-sheet row IDs must be unique')
            for row in rows:
                require(row.get('label') and row.get('role') in roles and type(row.get('amount')) in (int, float) and math.isfinite(row['amount']), 'Invalid balance-sheet row')
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
        for token in re.findall(r'[\u2e80-\u9fff\uff00-\uffef]|[^\u2e80-\u9fff\uff00-\uffef\s]+|[ \t]+', paragraph):
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
                step = math.ceil(size * 1.43)
                require(len(lines) * step <= h, f'{c["id"]}/{variant}/{name} overflows ({len(lines)} lines); split the concept in BOTH variants or shorten wording')
                for j, line in enumerate(lines):
                    if line:
                        boxes.append(dict(name=f'{c["id"]}-{name}-{j}', text=line, x=x, y=y+j*step,
                                          w=w, h=step, size=size, color=color or theme['ink'], bold=bold,
                                          runs=color_runs(line, c.get('equation_terms', []) if semantic else [], theme['roles'], color or theme['ink'])))
            expanded = variant == 'expanded'
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
                for row in sheet['rows']:
                    for value, width in ((row['label'], 366), (str(row['amount']), 94)):
                        require(all(ch.isspace() or ord(ch) in supported for ch in value), 'Missing balance-sheet glyph')
                        require(ImageFont.truetype(str(font_file),24).getlength(value) <= width,
                                'Balance-sheet cell exceeds its column; shorten the label or split the statement')
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
            source_map = {s['id']: s for s in data['sources']}
            refs_text = '\n'.join(f'[{r["source"]}] {source_map[r["source"]]["title"]}; {r["locator"]}: '
                                  + source_map[r['source']]['location']
                                  + (f'; retrieved {source_map[r["source"]]["retrieved"]}' if source_map[r['source']].get('retrieved') else '')
                                  for r in c['references'])
            notes = c['notes'] + ('\n' + c['expanded_notes'] if expanded else '')
            provenance = f'{c["id"]}\n{data["title"]}\nScope: {data["scope"]}\nModule: {c["module"]}\nLOS: {c["los"]}\n'
            result[variant].append({'id': c['id'], 'boxes': boxes, 'balance_sheet': sheet, 'expanded': expanded,
                                    'formula_width': w, 'notes': provenance + notes + '\n' + refs_text})
    return result


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
            keys = ['term_en', 'term_zh', 'summary_en', 'summary_zh', 'formula', 'variables', 'conditions', 'trap']
            if variant == 'expanded':
                keys.append('expanded')
            for k in keys:
                require(normalize(c[k]) in text, f'Slide {i}: lost {k}')
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
            paragraph = Paragraph(escape(notes), style)
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
            notes_pdf[i//3].show_pdf_page(fitz.Rect(30, top, 426, top+222.75), slides, i)
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
