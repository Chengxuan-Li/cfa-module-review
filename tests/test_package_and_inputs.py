import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from xml.sax.saxutils import escape

import fitz
from test_pipeline import p, SKILL

spec = importlib.util.spec_from_file_location('extract_inputs', SKILL / 'scripts/extract_inputs.py')
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)

REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
DOCREL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def package(path, concepts, reverse=False, missing_target=False, altered_text=False, wrong_notes=False):
    """Tiny original package fixture: enough structure to exercise relationship/content checks."""
    def rels(items):
        return f'<Relationships xmlns="{REL}">' + ''.join(f'<Relationship Id="{i}" Type="{DOCREL}/{t}" Target="{v}"/>' for i,t,v in items) + '</Relationships>'
    def text_xml(text):
        return f'<p:sld xmlns:p="{p.NS["p"]}" xmlns:a="{p.NS["a"]}"><a:t>{escape(text)}</a:t></p:sld>'
    order = list(range(1,len(concepts)+1))
    if reverse:
        order.reverse()
    with ZipFile(path,'w') as z:
        z.writestr('[Content_Types].xml','<Types/>')
        z.writestr('_rels/.rels',rels([('root','officeDocument','ppt/presentation.xml')]))
        z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{p.NS["p"]}" xmlns:r="{DOCREL}"><p:sldIdLst>'+''.join(f'<p:sldId id="{255+i}" r:id="s{i}"/>' for i in order)+'<'+ '/p:sldIdLst><p:sldSz cx="12192000" cy="6858000"/></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels',rels([(f's{i}','slide',f'slides/slide{i}.xml') for i in order]))
        for i,c in enumerate(concepts,1):
            keys=['id','term_en','term_zh','summary_en','summary_zh','formula','variables','conditions','trap']
            if altered_text:
                keys.remove('formula')
            z.writestr(f'ppt/slides/slide{i}.xml',text_xml('\n'.join(c[k] for k in keys)))
            z.writestr(f'ppt/slides/_rels/slide{i}.xml.rels',rels([('n','notesSlide',f'../notesSlides/notesSlide{99 if missing_target else i}.xml')]))
            z.writestr(f'ppt/notesSlides/notesSlide{i}.xml',text_xml('Wrong note' if wrong_notes else c['id']+' '+c['notes']))


class PackageTests(unittest.TestCase):
    def setUp(self):
        base=json.loads((SKILL/'assets/minimal-concepts.json').read_text(encoding='utf-8'))['concepts'][0]
        self.concepts=[copy.deepcopy(base),copy.deepcopy(base)]
        self.concepts[1]['id']='TEST-02'

    def test_package_relationship_order_and_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'fixture.pptx'
            package(file,self.concepts)
            self.assertEqual(p.audit_pptx(file,self.concepts,'concise'),2)
            for kwargs, message in [({'reverse':True},'concept order'),({'missing_target':True},'Broken package relationship'),({'altered_text':True},'lost formula'),({'wrong_notes':True},'wrong notes')]:
                with self.subTest(kwargs=kwargs):
                    package(file,self.concepts,**kwargs)
                    with self.assertRaisesRegex(ValueError,message):
                        p.audit_pptx(file,self.concepts,'concise')


class InputTests(unittest.TestCase):
    def test_docx_paragraphs_include_table_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'fixture.docx'
            with ZipFile(file,'w') as z:
                z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Definition</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table value</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
            rows=extractor.extract(file)
            self.assertEqual([r['text'] for r in rows],['Definition','Table value'])
            self.assertEqual(rows[1]['locator'],'paragraph 2')

    def test_pdf_page_locators_and_ocr_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'fixture.pdf'
            doc=fitz.open()
            page=doc.new_page()
            page.insert_text((50,50),'Original synthetic text long enough to exercise the text extraction path.')
            doc.new_page()
            doc.save(file)
            doc.close()
            rows=extractor.extract(file)
            self.assertEqual(rows[1]['locator'],'PDF page 2')
            self.assertFalse(rows[0]['needs_visual_or_ocr_review'])
            self.assertTrue(rows[1]['needs_visual_or_ocr_review'])

    def test_rtf(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'fixture.rtf'
            file.write_text(r'{\rtf1\ansi Original \b example\b0 .}',encoding='utf-8')
            self.assertIn('Original example',extractor.extract(file)[0]['text'])

    def test_legacy_word_is_explicitly_rejected(self):
        with self.assertRaisesRegex(ValueError,'convert legacy'):
            extractor.extract('example.doc')


if __name__=='__main__':
    unittest.main()
