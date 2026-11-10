"""A4 export of the same structured sections rendered by the briefing preview.

Layout mirrors frontend/src/pages/Briefing.jsx and the print rules in
frontend/src/pages/briefing.css: header, at-a-glance strip, paired context blocks,
aligned label/value rows, questions and an identifiers appendix. Colours are the
DESIGN.md tokens (ink, muted, nav, line, canvas, warning).
"""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INK, MUTED, NAV = colors.HexColor('#343a40'), colors.HexColor('#5f6a75'), colors.HexColor('#132742')
LINE, CANVAS = colors.HexColor('#e5e9ef'), colors.HexColor('#f1f4f6')
WARN, WARN_BG = colors.HexColor('#80550d'), colors.HexColor('#fdf6e7')
PAGE_MARGIN = 16 * mm
WIDTH = A4[0] - 2 * PAGE_MARGIN
GAP = 8 * mm


class UnsupportedPdfText(ValueError):
    pass


def render(payload):
    # Bundled static Open Sans (SIL OFL): no OS font, variable axes or runtime network.
    fonts = Path(__file__).resolve().parent / 'fonts'
    for name, filename in [('BriefBody', 'OpenSans-Regular.ttf'), ('BriefBold', 'OpenSans-Bold.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily('BriefBody', normal='BriefBody', bold='BriefBold')

    def style(name, **kw):
        base = dict(fontName='BriefBody', fontSize=8.5, leading=12.5, textColor=INK, splitLongWords=True)
        base.update(kw)
        return ParagraphStyle(name, **base)

    body = style('body', spaceAfter=4)
    note = style('note', fontSize=8, leading=11.5, textColor=MUTED, spaceAfter=4)
    eyebrow = style('eyebrow', fontName='BriefBold', fontSize=7, leading=9, textColor=MUTED, spaceAfter=2)
    title = style('title', fontName='BriefBold', fontSize=18, leading=22, textColor=NAV, spaceAfter=3)
    meta = style('meta', fontSize=7.5, leading=10.5, textColor=MUTED)
    badge = style('badge', fontName='BriefBold', fontSize=7, leading=9.5, textColor=MUTED, alignment=2)
    heading = style('heading', fontName='BriefBold', fontSize=10.5, leading=14, textColor=NAV, spaceBefore=11, spaceAfter=2, keepWithNext=True)
    heading_tight = style('heading_tight', fontName='BriefBold', fontSize=10.5, leading=14, textColor=NAV, spaceBefore=0, spaceAfter=2, keepWithNext=True)
    label = style('label', fontSize=8, textColor=MUTED)
    value = style('value', fontName='BriefBold', alignment=2)
    value_left = style('value_left', alignment=0)
    tile_label = style('tile_label', fontName='BriefBold', fontSize=6.5, leading=8.5, textColor=MUTED)
    tile_value = style('tile_value', fontName='BriefBold', fontSize=10.5, leading=14, textColor=NAV)
    tile_note = style('tile_note', fontSize=7, leading=9.5, textColor=MUTED)
    ident = style('ident', fontSize=7, leading=10)
    supported = pdfmetrics.getFont('BriefBody').face.charToGlyph

    def paragraph(text, st=body):
        if not all(ord(char) in supported or char in '\n\r\t' for char in text):
            raise UnsupportedPdfText('A character in this briefing is not supported by the PDF font. Use Print briefing / Save as PDF for this document.')
        # Saved notes/identifiers are plain text, never user-controlled ReportLab markup.
        return Paragraph(escape(text).replace('\n', '<br/>'), st)

    def rule(color=LINE, thickness=.6, after=4):
        hr = HRFlowable(width='100%', thickness=thickness, color=color, spaceBefore=0, spaceAfter=after)
        hr.keepWithNext = True
        return hr

    def rows_table(rows, width, long=False, id_style=False):
        """Aligned label/value rows. Short values align right (financial schedule); long notes wrap left."""
        if not rows:
            return []
        left, right = (width * .30, width * .70) if long or id_style else (width * .56, width * .44)
        vst = ident if id_style else value_left if long else value
        data = [[paragraph(k, label), paragraph(v, vst)] for k, v in rows]
        table = Table(data, colWidths=[left, right], hAlign='LEFT')
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, -1), .5, LINE),
            ('TOPPADDING', (0, 0), (-1, -1), 3.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (0, -1), 8), ('RIGHTPADDING', (1, 0), (1, -1), 0)]))
        return [table]

    def block(value_, width, first=False, long_rows=False):
        """One titled section: heading, rule, notes, rows, bullet items."""
        parts = [paragraph(value_['title'], heading_tight if first else heading), rule()]
        for text in value_['paragraphs']:
            parts.append(paragraph(text, body if value_['rows'] or value_['items'] else body))
        parts += rows_table(value_['rows'], width, long=long_rows or value_['title'] == 'Signals to investigate')
        for item in value_['items']:
            parts.append(paragraph('\u2022 ' + item))
        if value_['title'] == 'Signals to investigate' and not value_['items'] and not value_['rows']:
            parts.append(paragraph('No model signals were provided.'))
        return parts

    def text_size(value_):
        return sum(len(t) for t in value_['paragraphs']) + sum(len(a) + len(b) for a, b in value_['rows'])

    def pair(a, b):
        """Two blocks side by side, like the screen layout; stacked when notes are long enough to risk an unsplittable cell."""
        if text_size(a) + text_size(b) > 1100:
            return block(a, WIDTH, first=True) + block(b, WIDTH)
        col = (WIDTH - GAP) / 2
        table = Table([[block(a, col, first=True), '', block(b, col, first=True)]], colWidths=[col, GAP, col], hAlign='LEFT')
        table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                   ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
        return [Spacer(1, 8), table]

    story = []
    for index, item in enumerate(payload['items']):
        if index:
            story.append(PageBreak())
        head = Table([[[paragraph('RM DISCUSSION BRIEF', eyebrow), paragraph(item['name'], title if len(item['name']) <= 60 else style('title_long', fontName='BriefBold', fontSize=13 if len(item['name']) <= 140 else 10.5, leading=17 if len(item['name']) <= 140 else 14, textColor=NAV, spaceAfter=3)),
                        paragraph(' \u00b7 '.join(['Customer ' + item['customer_id'], 'Case ' + item['case_id'][:12]]
                                                  + (['Prepared ' + item['prepared_on']] if item.get('prepared_on') else [])), meta)],
                       paragraph('INTERNAL USE\nReview before sharing', badge)]], colWidths=[WIDTH - 34 * mm, 34 * mm])
        head.setStyle(TableStyle([('VALIGN', (0, 0), (0, 0), 'TOP'), ('VALIGN', (1, 0), (1, 0), 'TOP'),
                                  ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 0),
                                  ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        story += [head, Spacer(1, 6), HRFlowable(width='100%', thickness=1.6, color=NAV, spaceAfter=8)]
        if item.get('sample_note'):
            sample = Table([[paragraph(item['sample_note'], style('sample', textColor=WARN, spaceAfter=0))]], colWidths=[WIDTH])
            sample.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), WARN_BG), ('BOX', (0, 0), (-1, -1), .6, WARN),
                                        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                                        ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
            story += [sample, Spacer(1, 8)]
        glance = item.get('glance') or []
        if glance:
            tile = (WIDTH - 3 * 3 * mm) / 4
            cells = [[paragraph(g['label'].upper(), tile_label), paragraph(g['value'], tile_value), paragraph(g.get('note') or '', tile_note)] for g in glance]
            strip = Table([cells], colWidths=[tile] * len(cells), hAlign='LEFT')
            commands = [('BACKGROUND', (0, 0), (-1, -1), CANVAS), ('BOX', (0, 0), (-1, -1), .6, LINE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]
            commands += [('LINEBEFORE', (i, 0), (i, 0), .6, LINE) for i in range(1, len(cells))]
            strip.setStyle(TableStyle(commands))
            story.append(strip)
            if item.get('risk_definition'):
                story += [Spacer(1, 4), paragraph(item['risk_definition'], note)]
        story += pair(item['original'], item['latest'])
        story += block(item['activity'], WIDTH)
        story += block(item['signals'], WIDTH)
        story += pair(item['operations'], item['finance'])
        story += block(item['decision'], WIDTH, long_rows=True)
        if item.get('followups'):
            story += [paragraph(item['followups']['title'], style('sub', fontName='BriefBold', fontSize=8.5, textColor=INK, spaceBefore=6, spaceAfter=2, keepWithNext=True))]
            story += rows_table(item['followups']['rows'], WIDTH, long=True)
        story += [paragraph('Questions for the customer', heading), rule()]
        if not item['questions']:
            story.append(paragraph('No evidence-linked question is available from the supplied measures. Review the case before preparing questions.'))
        for number, question in enumerate(item['questions'], 1):
            qrow = Table([[paragraph(str(number), style('qn', fontName='BriefBold', textColor=NAV)),
                           [paragraph(question['text'], style('qt', spaceAfter=1)), paragraph('Evidence: ' + question['source'] + ' \u00b7 ' + question['month'], note)]]],
                         colWidths=[7 * mm, WIDTH - 7 * mm], hAlign='LEFT')
            qrow.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                      ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
            story.append(qrow)
        story += [paragraph('Evidence sources and identifiers', heading), rule()]
        story += rows_table(item['traceability'], WIDTH, id_style=True)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(.6)
        canvas.line(PAGE_MARGIN, 14 * mm, A4[0] - PAGE_MARGIN, 14 * mm)
        canvas.setFont('BriefBody', 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(PAGE_MARGIN, 10 * mm, 'TxB Retention Studio \u00b7 Internal use \u00b7 Review before sharing')
        canvas.drawRightString(A4[0] - PAGE_MARGIN, 10 * mm, 'Page ' + str(doc.page))
        canvas.restoreState()

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=PAGE_MARGIN, rightMargin=PAGE_MARGIN,
                            topMargin=PAGE_MARGIN, bottomMargin=20 * mm,
                            title='TxB RM briefing', author='TxB Retention Studio', invariant=1)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
