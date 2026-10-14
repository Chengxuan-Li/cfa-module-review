"""Extract private inputs with stable page/paragraph locators; never infer LOS automatically."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from pypdf import PdfReader


def extract(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        pages = []
        for i, page in enumerate(PdfReader(path).pages, 1):
            text = page.extract_text() or ''
            pages.append({'locator': f'PDF page {i}', 'text': text, 'needs_visual_or_ocr_review': len(text.strip()) < 40})
        return pages
    if suffix == '.docx':
        with ZipFile(path) as archive:
            root = ET.fromstring(archive.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        return [{'locator': f'paragraph {i}', 'text': ''.join(t.text or '' for t in p.findall('.//w:t', ns))}
                for i, p in enumerate(root.findall('.//w:p', ns), 1)]
    if suffix == '.rtf':
        from striprtf.striprtf import rtf_to_text
        return [{'locator': 'RTF document', 'text': rtf_to_text(path.read_text(encoding='utf-8'))}]
    if suffix in {'.txt', '.md'}:
        return [{'locator': 'pasted text', 'text': path.read_text(encoding='utf-8-sig')}]
    raise ValueError(f'Unsupported source {suffix}; convert legacy .doc to .docx first.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', help='JSON array of {id, role, path}; roles: curriculum, chinese, kaplan')
    p.add_argument('--out', required=True)
    args = p.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8-sig'))
    base = Path(args.manifest).resolve().parent
    result = [{**s, 'segments': extract(base / s['path'])} for s in manifest]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
