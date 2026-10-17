"""Synthetic resumes generated locally; no real customer files."""
from pathlib import Path
from docx import Document
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from pypdf import PdfWriter

def create_resumes(folder: Path):
    folder.mkdir(parents=True,exist_ok=True)
    lines=["合成测试简历", "学历：本科", "雅思 IELTS 6.5分", "出生日期：2000-01-02"]
    doc=Document()
    for line in lines:doc.add_paragraph(line)
    doc.save(folder/"m2_resume.docx")
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c=Canvas(str(folder/"m2_resume_text.pdf"));c.setFont("STSong-Light",12)
    for i,line in enumerate(lines):c.drawString(60,780-i*24,line)
    c.save()
    pdf=PdfWriter();pdf.add_blank_page(width=595,height=842)
    with (folder/"m2_resume_scanned.pdf").open("wb") as out:pdf.write(out)
