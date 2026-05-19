"""
Merge 封面与声明.docx + 正文.docx → 终稿.docx
Handles section-level header/footer/page-number config post-merge.
"""
import copy
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = r"F:\bishe\论文"
FONT_SONG = "SimSun"

def set_font(run, name, size_pt, bold=False):
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.font.name = name
    r = run._element
    rPr = r.find(qn('w:rPr'))
    if rPr is None:
        rPr = OxmlElement('w:rPr')
        r.insert(0, rPr)
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:eastAsia'), name)
    rFonts.set(qn('w:ascii'), name)
    rFonts.set(qn('w:hAnsi'), name)

def add_fld_char(para, fld_char_type):
    run = para.add_run()
    el = OxmlElement('w:fldChar')
    el.set(qn('w:fldCharType'), fld_char_type)
    run._element.append(el)

def add_instr_text(para, text):
    run = para.add_run()
    el = OxmlElement('w:instrText')
    el.set(qn('xml:space'), 'preserve')
    el.text = text
    run._element.append(el)

def add_page_field(para, format_type='decimal'):
    add_fld_char(para, 'begin')
    instr = ' PAGE \\* ROMAN ' if format_type == 'roman' else ' PAGE '
    add_instr_text(para, instr)
    add_fld_char(para, 'separate')
    # Default visible text between separate and end (Word replaces with actual page num)
    run = para.add_run()
    run.text = '1'
    add_fld_char(para, 'end')

def add_paragraph_border(para):
    pPr = para._element.find(qn('w:pPr'))
    if pPr is None:
        pPr = OxmlElement('w:pPr')
        para._element.insert(0, pPr)
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '4')
    bottom.set(qn('w:space'), '4')
    bottom.set(qn('w:color'), '000000')
    pBdr.append(bottom)
    pPr.append(pBdr)

def configure_merged_sections(doc):
    """Post-merge: configure headers, footers, page numbers.

    Merged document sections:
      0: Cover        — no header/footer
      1: Title page   — no header/footer
      2: Declaration  — no header/footer
      3: Front matter — no header, Roman page nums
      4: Main body    — header + Arabic page nums from 1
    """
    sections = doc.sections
    print(f"Total sections: {len(sections)}")

    if len(sections) < 5:
        print("WARNING: expected >=5 sections, section config may be wrong")
        return

    # --- Section 3: Front matter (abstracts + TOC) ---
    sec_fm = sections[3]
    # Header: empty
    hdr = sec_fm.header
    hdr.is_linked_to_previous = False
    # Footer: Roman numeral page numbers, centered, start at I
    ftr = sec_fm.footer
    ftr.is_linked_to_previous = False
    fp = ftr.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_field(fp, format_type='roman')
    # Roman numerals start at I
    sectPr = sec_fm._sectPr
    pgNumType = OxmlElement('w:pgNumType')
    pgNumType.set(qn('w:start'), '1')
    sectPr.append(pgNumType)

    # --- Section 4: Main body ---
    sec_body = sections[4]
    # Header: school name + underline
    hdr = sec_body.header
    hdr.is_linked_to_previous = False
    hp = hdr.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = hp.add_run('应急管理大学本科毕业设计（论文）')
    set_font(run, FONT_SONG, 9)
    add_paragraph_border(hp)

    # Footer: Arabic page numbers, restart at 1
    ftr = sec_body.footer
    ftr.is_linked_to_previous = False
    fp = ftr.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_page_field(fp, format_type='decimal')
    # Restart page numbering
    sectPr = sec_body._sectPr
    pgNumType = OxmlElement('w:pgNumType')
    pgNumType.set(qn('w:start'), '1')
    sectPr.append(pgNumType)

    print("Section headers/footers configured.")


# === Main ===
print("Loading cover...")
cover = Document(r'F:\bishe\论文\封面与声明.docx')
print(f"Cover sections: {len(cover.sections)}")

print("Loading body...")
body = Document(r'F:\bishe\论文\正文.docx')
print(f"Body sections: {len(body.sections)}")
print(f"Body paragraphs: {len(body.paragraphs)}")

# Merge: insert page break, then deep-copy all body elements
print("Merging...")
# Page break to separate declaration from abstract
pb_para = OxmlElement('w:p')
pb_run = OxmlElement('w:r')
pb_br = OxmlElement('w:br')
pb_br.set(qn('w:type'), 'page')
pb_run.append(pb_br)
pb_para.append(pb_run)
cover.element.body.append(copy.deepcopy(pb_para))

for bp in body.element.body:
    el = copy.deepcopy(bp)
    cover.element.body.append(el)

print(f"Post-merge body children: {len(cover.element.body)}")

# Save intermediate, re-open to get correct section count
tmp = r'F:\bishe\论文\_tmp_merged.docx'
cover.save(tmp)

print("Re-opening merged to configure sections...")
merged = Document(tmp)
print(f"Merged sections: {len(merged.sections)}")

configure_merged_sections(merged)

output = r'F:\bishe\论文\终稿-标准格式.docx'
merged.save(output)
print(f"\nDone: {output}")
