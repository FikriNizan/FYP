"""A4 export of the same structured sections rendered by the briefing preview."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

class UnsupportedPdfText(ValueError):
    pass


def render(payload):
    # Redistributable Bitstream Vera comes with ReportLab, so no OS font or network is needed.
    fonts = Path(reportlab.__file__).parent / 'fonts'
    for name, filename in [('BriefBody', 'Vera.ttf'), ('BriefBold', 'VeraBd.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily('BriefBody', normal='BriefBody', bold='BriefBold')
    body = ParagraphStyle('body', fontName='BriefBody', fontSize=9, leading=13,
                          spaceAfter=5, textColor=colors.HexColor('#343a40'), splitLongWords=True)
    title = ParagraphStyle('title', parent=body, fontName='BriefBold', fontSize=15,
                           leading=20, spaceAfter=8, keepWithNext=True)
    heading = ParagraphStyle('heading', parent=body, fontName='BriefBold', fontSize=10,
                             leading=14, spaceBefore=10, keepWithNext=True)
    technical = ParagraphStyle('technical', parent=body, fontSize=8, leading=12)
    story = []
    supported = pdfmetrics.getFont('BriefBody').face.charToGlyph

    def paragraph(text, style=body):
        if not all(ord(char) in supported or char in '\n\r\t' for char in text):
            raise UnsupportedPdfText('A character in this briefing is not supported by the PDF font. Use Print briefing / Save as PDF for this document.')
        # Saved notes/identifiers are plain text, never user-controlled ReportLab markup.
        return Paragraph(escape(text).replace('\n', '<br/>'), style)

    def add_section(value):
        story.append(paragraph(value['title'], heading))
        for text in value['paragraphs']:
            story.append(paragraph(text))
        for label, text in value['rows']:
            # Each row can split naturally across pages, including maximum-length notes.
            story.append(paragraph(label+': '+text))
        for item in value['items']:
            story.append(paragraph('• '+item))
        if value['title'] == 'Signals to investigate' and not value['items']:
            story.append(paragraph('No model signals were provided.'))

    for index, item in enumerate(payload['items']):
        if index:
            story.append(PageBreak())
        story.append(paragraph(item['name'], title))
        story.append(paragraph('Internal RM discussion brief · Review before sharing.', technical))
        story.append(paragraph('Customer '+item['customer_id']+' · Case '+item['case_id'], technical))
        if item['sample_note']:
            story.append(paragraph(item['sample_note']))
        for key in ['original', 'latest', 'activity', 'signals', 'operations', 'finance', 'decision']:
            add_section(item[key])
        story.append(paragraph('Questions for the customer', heading))
        if not item['questions']:
            story.append(paragraph('No evidence-linked question is available from the supplied measures. Review the case before preparing questions.'))
        for number, question in enumerate(item['questions'], 1):
            story.append(paragraph(f'{number}. '+question['text']))
            story.append(paragraph('Evidence: '+question['source']+' · '+question['month'], technical))
        story.append(paragraph('Evidence sources and identifiers', heading))
        for label, value in item['traceability']:
            story.append(paragraph(label+': '+value, technical))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('BriefBody', 8)
        canvas.setFillColor(colors.HexColor('#5f6a75'))
        canvas.drawString(16 * mm, 10 * mm, 'TxB Retention Studio · Internal use')
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, 'Page '+str(doc.page))
        canvas.restoreState()

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=16 * mm, bottomMargin=18 * mm,
                            title='TxB RM briefing', author='TxB Retention Studio', invariant=1)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
