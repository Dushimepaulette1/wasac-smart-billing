"""Build the report PDF from its HTML without a browser. See docs/report/requirements.txt."""
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/report/technical_report.html"
TARGET = SOURCE.with_name("Mubazi_Technical_Report.pdf")
WIDTH = 178 * mm


class Element:
    def __init__(self, tag, attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Element("document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in ("img", "br", "meta", "link", "hr", "path", "rect", "line"):
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def markup(node):
    if isinstance(node, str):
        return escape(node)
    text = "".join(markup(c) for c in node.children)
    if node.tag == "code":
        return f'<font name="Courier">{text}</font>'
    if node.tag in ("b", "i", "strong", "em"):
        tag = {"strong": "b", "em": "i"}.get(node.tag, node.tag)
        return f"<{tag}>{text}</{tag}>"
    if node.tag == "br":
        return "<br/>"
    return text


body = ParagraphStyle("ReportBody", fontName="Times-Roman", fontSize=10, leading=12, spaceAfter=4)
small = ParagraphStyle("ReportSmall", parent=body, fontSize=8, leading=9.6, spaceAfter=0)
head = ParagraphStyle("ReportHeading", parent=body, fontName="Times-Bold", fontSize=11, leading=13,
                      spaceBefore=7, spaceAfter=3, keepWithNext=True, textColor=colors.HexColor("#1c3f66"))
title = ParagraphStyle("ReportTitle", parent=head, fontSize=17, leading=20)
caption = ParagraphStyle("ReportCaption", parent=small, textColor=colors.HexColor("#44505e"), spaceAfter=5)


def architecture():
    drawing = Drawing(WIDTH, 74)
    boxes = [(0, 16, 110, ["Household / staff", "React on Vercel", "Basic phone / USSD"]),
             (153, 16, 186, ["FastAPI on Render", "Vision, rules, review", "Billing and corrections"]),
             (380, 16, 123, ["Neon PostgreSQL", "MTN payment interface", "SMS interface"])]
    for x, y, width, labels in boxes:
        drawing.add(Rect(x, y, width, 53, strokeColor=colors.HexColor("#1c3f66"), fillColor=colors.HexColor("#eef3f8")))
        for row, label in enumerate(labels):
            drawing.add(String(x+width/2, y+39-row*13, label, textAnchor="middle", fontSize=9))
    for a, b in ((110, 153), (339, 380)):
        drawing.add(Line(a, 42, b, 42, strokeColor=colors.HexColor("#1c3f66")))
        drawing.add(Line(b-5, 45, b, 42))
        drawing.add(Line(b-5, 39, b, 42))
    return drawing


def render(node):
    if isinstance(node, str):
        return []
    if node.tag in ("head", "style", "script"):
        return []
    if node.tag == "svg":
        return [architecture()]
    if node.tag in ("h1", "h2", "h3", "p", "li"):
        content = markup(node).strip()
        if node.tag == "li":
            content = "• " + content
        return [Paragraph(content, title if node.tag == "h1" else head if node.tag.startswith("h") else body)]
    if node.tag == "table":
        rows = [r for r in node.children if isinstance(r, Element) and r.tag == "tr"]
        values = [[Paragraph(markup(c), small) for c in r.children
                   if isinstance(c, Element) and c.tag in ("td", "th")] for r in rows]
        count = len(values[0])
        proportions = {4: [0.20, 0.25, 0.13, 0.42], 3: [0.20, 0.38, 0.42]}.get(count, [1/count]*count)
        table = Table(values, colWidths=[WIDTH*x for x in proportions], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4edf5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#b9c3cf")),
            ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return [table, Spacer(1, 5)]
    if node.tag == "div" and node.attrs.get("class") == "fig":
        images = []
        widths = []
        for item in node.children:
            if not isinstance(item, Element) or item.tag != "img":
                continue
            width = WIDTH * float(item.attrs.get("style", "width:100%").split("width:")[1].split("%")[0]) / 100
            image = Image(str(SOURCE.parent/item.attrs["src"]))
            image.drawHeight *= width/image.drawWidth
            image.drawWidth = width
            if image.drawHeight > 135:
                scale = 135/image.drawHeight
                image.drawWidth *= scale
                image.drawHeight *= scale
            images.append(image)
            widths.append(width+4)
        return [Table([images], colWidths=widths, hAlign="LEFT")] if images else []
    if node.tag == "div" and node.attrs.get("class") in ("cap", "by"):
        return [Paragraph(markup(node), caption)]
    result = []
    for child in node.children:
        result.extend(render(child))
    return result


def footer(canvas, document):
    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, 210*mm, 297*mm, fill=1, stroke=0)
    canvas.setFont("Times-Roman", 8)
    canvas.setFillColor(colors.HexColor("#44505e"))
    canvas.drawString(16*mm, 9*mm, "Mubazi — final prototype; real, simulated and historical evidence distinguished")
    canvas.drawRightString(194*mm, 9*mm, str(document.page))


if __name__ == "__main__":
    parser = Document()
    parser.feed(SOURCE.read_text())
    document = SimpleDocTemplate(str(TARGET), pagesize=(210*mm, 297*mm), leftMargin=16*mm,
                                 rightMargin=16*mm, topMargin=13*mm, bottomMargin=15*mm,
                                 title="Mubazi Technical Report", author="Dushime Paulette")
    document.build(render(parser.root), onFirstPage=footer, onLaterPages=footer)
    print(f"Wrote {TARGET}")
