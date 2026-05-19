"""
组装毕设论文终稿.docx
封面 由 generate_cover.cjs 生成（封面与声明.docx）
正文 从 .md 文件转换
"""
import re
from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

BASE = r"F:\bishe\论文"

# --- Font constants ---
FONT_HEI = "SimHei"    # 黑体 — titles
FONT_SONG = "SimSun"   # 宋体 — body
FONT_FANG = "FangSong" # 仿宋 — cover fields
FONT_KAITI = "KaiTi"   # 楷体 — abstract labels

def set_font(run, name, size_pt, bold=False):
    """Set run font with both ascii and east-asian"""
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

def set_line_spacing(para, multiple=1.5):
    """Set paragraph line spacing"""
    pPr = para._element.find(qn('w:pPr'))
    if pPr is None:
        pPr = OxmlElement('w:pPr')
        para._element.insert(0, pPr)
    spacing = pPr.find(qn('w:spacing'))
    if spacing is None:
        spacing = OxmlElement('w:spacing')
        pPr.append(spacing)
    spacing.set(qn('w:line'), str(int(multiple * 240)))
    spacing.set(qn('w:lineRule'), 'auto')

def set_first_line_indent(para, indent_chars=2, font_size_pt=12):
    """Set first line indent (2 chars for body text).

    w:firstLine uses twips (1/20 of a point), NOT EMU.
    2 chars at 12pt = 24pt = 480 twips.
    """
    pPr = para._element.find(qn('w:pPr'))
    if pPr is None:
        pPr = OxmlElement('w:pPr')
        para._element.insert(0, pPr)
    ind = pPr.find(qn('w:ind'))
    if ind is None:
        ind = OxmlElement('w:ind')
        pPr.append(ind)
    ind.set(qn('w:firstLine'), str(font_size_pt * indent_chars * 20))

def add_body_para(doc, text, first_indent=True):
    """Add a body paragraph with standard formatting"""
    p = doc.add_paragraph()
    if first_indent:
        set_first_line_indent(p)
    set_line_spacing(p, 1.5)
    run = p.add_run(text)
    set_font(run, FONT_SONG, 12)
    return p

def add_heading_styled(doc, text, level):
    """Add a chapter/section heading.

    Uses Word built-in Heading style so TOC can recognize it,
    then overrides run font to match Chinese thesis formatting.
    """
    p = doc.add_paragraph()
    # Apply built-in heading style for TOC recognition
    p.style = doc.styles[f'Heading {level}']
    set_line_spacing(p, 1.5)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if level == 1 else WD_ALIGN_PARAGRAPH.LEFT
    if level == 1:
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(12)
        size = 16
        bold = True
    elif level == 2:
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)
        size = 14
        bold = True
    elif level == 3:
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(3)
        size = 12
        bold = True
    run = p.add_run(text)
    set_font(run, FONT_HEI, size, bold)
    return p


def add_toc(doc):
    """Insert TOC page, then a section break separating front matter from body.

    User needs to right-click → Update Field in Word to generate the actual TOC.
    """
    # "目录" title (NOT using Heading style to avoid self-reference)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_line_spacing(p, 1.5)
    run = p.add_run('目录')
    set_font(run, FONT_HEI, 16, bold=True)

    # TOC field code
    toc_p = doc.add_paragraph()
    _add_fld_char(toc_p, 'begin')
    _add_instr_text(toc_p, ' TOC \\o "1-3" \\h \\z \\u ')
    _add_fld_char(toc_p, 'separate')
    run = toc_p.add_run('（请在Word中右键此区域 → 更新域 → 更新整个目录）')
    set_font(run, FONT_SONG, 10)
    _add_fld_char(toc_p, 'end')

    # Section break: front matter ends, main body begins
    doc.add_section()


def _add_fld_char(para, fld_char_type):
    """Helper: add a w:fldChar element to a paragraph"""
    run = para.add_run()
    el = OxmlElement('w:fldChar')
    el.set(qn('w:fldCharType'), fld_char_type)
    run._element.append(el)


def _add_instr_text(para, text):
    """Helper: add a w:instrText element to a paragraph"""
    run = para.add_run()
    el = OxmlElement('w:instrText')
    el.set(qn('xml:space'), 'preserve')
    el.text = text
    run._element.append(el)

def add_table_from_md(doc, lines, start_idx):
    """Parse and add a markdown table. Returns (table_element, end_line_idx)"""
    # Collect table lines
    table_lines = []
    i = start_idx
    while i < len(lines) and lines[i].strip().startswith('|'):
        table_lines.append(lines[i].strip())
        i += 1

    if len(table_lines) < 2:
        return None, start_idx

    # Parse rows
    rows = []
    for tl in table_lines:
        cells = [c.strip() for c in tl.strip('|').split('|')]
        # Skip separator line like |---|---|
        if all(re.match(r'^[-:]+$', c.strip()) for c in cells):
            continue
        rows.append(cells)

    if not rows:
        return None, i - 1

    # Create table
    num_cols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=num_cols, style='Table Grid')

    # Set font for all cells
    for row_idx, row_data in enumerate(rows):
        for col_idx, cell_text in enumerate(row_data):
            if col_idx < num_cols:
                cell = table.rows[row_idx].cells[col_idx]
                cell.text = ''
                p = cell.paragraphs[0]
                run = p.add_run(cell_text)
                is_header = (row_idx == 0)
                set_font(run, FONT_HEI if is_header else FONT_SONG, 9 if is_header else 9)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                # Add shading to header
                if is_header:
                    shading = OxmlElement('w:shd')
                    shading.set(qn('w:fill'), 'D9E2F3')
                    shading.set(qn('w:val'), 'clear')
                    cell._element.find(qn('w:tcPr')).append(shading)

    return table, i - 1

def add_abstract_section(doc, md_path, is_english=False):
    """Add abstract with special formatting"""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    if is_english:
        # English abstract
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('# '):
                continue
            if line.startswith('**') and line.endswith('**'):
                # Keywords
                p = doc.add_paragraph()
                run = p.add_run(line.replace('**', ''))
                set_font(run, 'Times New Roman', 12)
                set_line_spacing(p, 1.5)
            else:
                p = doc.add_paragraph()
                set_first_line_indent(p)
                run = p.add_run(line)
                set_font(run, 'Times New Roman', 12)
                set_line_spacing(p, 1.5)
    else:
        # Chinese abstract
        # Title
        heading_found = False
        for line in lines:
            line = line.strip()
            if not line and not heading_found:
                continue
            if line.startswith('# '):
                add_heading_styled(doc, line[2:], 1)
                heading_found = True
                continue
            if line.startswith('**') and line.endswith('**') and '关键词' in line:
                p = doc.add_paragraph()
                run = p.add_run(line.replace('**', ''))
                set_font(run, FONT_HEI, 12, bold=True)
                set_line_spacing(p, 1.5)
            elif line:
                # Normal paragraph
                # Remove leading full-width spaces
                cleaned = line.lstrip('　 ')
                add_body_para(doc, cleaned)

    doc.add_page_break()

def parse_md_body(doc, md_path):
    """Parse a markdown chapter file and add to document"""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Skip mermaid code blocks
        if stripped.startswith('```'):
            # Skip until closing ```
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                i += 1
            i += 1  # skip closing ```
            # Add figure placeholder
            continue

        # Skip HTML tags (figure placeholders)
        if stripped.startswith('<p align') or stripped.startswith('<b>图') or stripped.startswith('</p>'):
            i += 1
            continue

        # Headings
        if stripped.startswith('# '):
            # Chapter title level
            text = stripped[2:]
            # Remove numbering like "第1章" to keep it cleaner
            add_heading_styled(doc, text, 1)
            i += 1
            continue
        elif stripped.startswith('## '):
            text = stripped[3:]
            add_heading_styled(doc, text, 2)
            i += 1
            continue
        elif stripped.startswith('### '):
            text = stripped[4:]
            add_heading_styled(doc, text, 3)
            i += 1
            continue

        # Tables
        if stripped.startswith('|'):
            table, next_i = add_table_from_md(doc, lines, i)
            if table:
                p = doc.add_paragraph()  # spacer
                i = next_i + 1
                continue

        # Bold text markers
        # **text** → bold
        # Regular paragraph
        cleaned = stripped.lstrip('　 ')

        if cleaned.startswith('**') and '**' in cleaned[2:]:
            # Bold leading text
            p = doc.add_paragraph()
            set_first_line_indent(p)
            set_line_spacing(p, 1.5)

            # Parse bold segments **bold** and regular text
            segments = re.split(r'(\*\*[^*]+\*\*)', cleaned)
            for seg in segments:
                if seg.startswith('**') and seg.endswith('**'):
                    run = p.add_run(seg[2:-2])
                    set_font(run, FONT_HEI, 12, bold=True)
                elif seg:
                    run = p.add_run(seg)
                    set_font(run, FONT_SONG, 12)
            i += 1
            continue

        # Table/figure captions (like "表2-1 xxx")
        if re.match(r'^(表\d|图\d)', cleaned):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(cleaned)
            set_font(run, FONT_HEI, 10, bold=True)
            i += 1
            continue

        # Formula or equation
        if cleaned.startswith('CCR1') or cleaned.startswith('饱和度和i') or cleaned.startswith('式（'):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_line_spacing(p, 1.5)
            run = p.add_run(cleaned)
            set_font(run, FONT_SONG, 12)
            i += 1
            continue

        # Normal body paragraph
        add_body_para(doc, cleaned)
        i += 1

    doc.add_page_break()


def configure_sections(doc):
    """Setup headers, footers, and page numbers for all sections.

    Section 0: Front matter — no header, Roman numeral page numbers (I,II,III…)
    Section 1: Main body — header with school name, Arabic page numbers from 1
    """
    # --- Section 0: Front matter (abstracts + TOC) ---
    _setup_front_matter(doc.sections[0])

    # --- Section 1: Main body ---
    _setup_body_section(doc.sections[1])


def _setup_front_matter(section):
    """No header, Roman numeral page numbers centered in footer."""
    section.different_first_page_header_footer = False
    # Header: empty
    header = section.header
    header.is_linked_to_previous = False
    # Footer: Roman numerals
    footer = section.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_page_field(fp, format_type='roman')


def _setup_body_section(section):
    """Header: school name + thin line. Footer: Arabic page numbers, restart at 1."""
    section.different_first_page_header_footer = False

    # Header
    header = section.header
    header.is_linked_to_previous = False
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = hp.add_run('应急管理大学本科毕业设计（论文）')
    set_font(run, FONT_SONG, 9)
    # Thin bottom border on header paragraph
    _add_paragraph_border(hp)

    # Footer: Arabic page numbers, restart from 1
    footer = section.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_page_field(fp, format_type='decimal')
    # Restart page numbering at 1
    sectPr = section._sectPr
    pgNumType = OxmlElement('w:pgNumType')
    pgNumType.set(qn('w:start'), '1')
    sectPr.append(pgNumType)


def _add_page_field(para, format_type='decimal'):
    """Insert a PAGE field code into a paragraph.

    format_type: 'decimal' → 1,2,3…  'roman' → I,II,III…
    """
    _add_fld_char(para, 'begin')
    instr = ' PAGE \\* ROMAN ' if format_type == 'roman' else ' PAGE '
    _add_instr_text(para, instr)
    _add_fld_char(para, 'separate')
    _add_fld_char(para, 'end')


def _add_paragraph_border(para):
    """Add a thin bottom border to a paragraph (used for header underline)."""
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


def main():
    global doc
    doc = Document()

    # Set default font
    style = doc.styles['Normal']
    style.font.name = FONT_SONG
    style.font.size = Pt(12)
    style.paragraph_format.line_spacing = 1.5

    # Configure built-in heading styles (font fallback for TOC)
    for i in range(1, 4):
        hs = doc.styles[f'Heading {i}']
        hs.font.name = FONT_HEI
        hs.font.size = Pt({1: 16, 2: 14, 3: 12}[i])
        hs.font.bold = True

    # ===== 中文摘要 =====
    add_abstract_section(doc, os.path.join(BASE, '中文摘要.md'), is_english=False)

    # ===== 英文摘要 =====
    add_abstract_section(doc, os.path.join(BASE, '英文摘要.md'), is_english=True)

    # ===== 目录 =====
    add_toc(doc)

    # ===== 正文五章 =====
    chapters = [
        '第1章-绪论.md',
        '第2章-需求分析.md',
        '第3章-系统设计.md',
        '第4章-详细设计与实现.md',
        '第5章-测试.md',
    ]
    for ch_file in chapters:
        path = os.path.join(BASE, ch_file)
        if os.path.exists(path):
            print(f"Processing: {ch_file}")
            parse_md_body(doc, path)
        else:
            print(f"WARNING: {ch_file} not found")

    # ===== 结论 =====
    conclusion_path = os.path.join(BASE, '结论.md')
    if os.path.exists(conclusion_path):
        print("Processing: 结论.md")
        parse_md_body(doc, conclusion_path)

    # ===== 参考文献 =====
    ref_path = os.path.join(BASE, '参考文献.md')
    if os.path.exists(ref_path):
        print("Processing: 参考文献.md")
        parse_md_body(doc, ref_path)

    # ===== 致谢 =====
    thanks_path = os.path.join(BASE, '致谢.md')
    if os.path.exists(thanks_path):
        print("Processing: 致谢.md")
        parse_md_body(doc, thanks_path)

    # ===== 附录 =====
    appendix_path = os.path.join(BASE, '附录.md')
    if os.path.exists(appendix_path):
        print("Processing: 附录.md")
        parse_md_body(doc, appendix_path)

    # Save (section headers/footers configured post-merge)
    output = os.path.join(BASE, '正文.docx')
    doc.save(output)
    print(f"\nDone: {output}")


if __name__ == '__main__':
    main()
