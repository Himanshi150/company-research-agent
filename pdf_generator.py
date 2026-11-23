"""Professional ReportLab PDF generation."""

from io import BytesIO
from datetime import date
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def linkify_urls(urls):
    if not isinstance(urls, list):
        return ""
    parts = []
    for url in urls:
        if isinstance(url, str) and url:
            safe = url.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f'<link href="{safe}" color="#2563EB">{safe}</link>')
    return "<br/>".join(parts)


def safe_text(value: Any) -> str:
    if value is None:
        return "Not publicly available"
    text = str(value).strip()
    if not text:
        return "Not publicly available"
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(A4[0] - 0.55 * inch, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def generate_pdf(report: Dict[str, Any]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=f"Company Research - {report.get('company_name', 'Company')}",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCustom", parent=styles["Title"], fontSize=22, leading=26, textColor=colors.HexColor("#0F172A"), alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name="SectionCustom", parent=styles["Heading2"], fontSize=13, leading=16, textColor=colors.HexColor("#1D4ED8"), spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="BodyCustom", parent=styles["BodyText"], fontSize=9.5, leading=13, textColor=colors.HexColor("#1E293B")))
    styles.add(ParagraphStyle(name="SmallCustom", parent=styles["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#475569") ))

    story = []
    company = safe_text(report.get("company_name", "Company"))
    story.append(Paragraph(company, styles["TitleCustom"]))
    story.append(Paragraph("Company Research Report", styles["Heading3"]))
    story.append(Paragraph(f"Generated: {date.today().isoformat()}", styles["SmallCustom"]))
    story.append(Spacer(1, 12))

    disclaimer = "Information is compiled from publicly available sources. Please independently verify important details."
    story.append(Paragraph(disclaimer, styles["SmallCustom"]))
    story.append(Spacer(1, 8))

    def section(title, body):
        story.append(Paragraph(title, styles["SectionCustom"]))
        story.append(Paragraph(body, styles["BodyCustom"]))

    section("Company Overview", safe_text(report.get("overview")))
    section("Industry", safe_text(report.get("industry")))

    story.append(Paragraph("Company Size & Locations", styles["SectionCustom"]))
    story.append(Paragraph(f"<b>Employee size:</b> {safe_text(report.get('employee_size'))}", styles["BodyCustom"]))
    story.append(Paragraph(f"<b>Headquarters:</b> {safe_text(report.get('headquarters'))}", styles["BodyCustom"]))
    locations = report.get("locations", [])
    location_text = ", ".join(safe_text(v) for v in locations) if locations else "Not publicly available"
    story.append(Paragraph(f"<b>Other locations:</b> {location_text}", styles["BodyCustom"]))

    story.append(Paragraph("Recent News", styles["SectionCustom"]))
    news = report.get("recent_news", [])
    if news:
        for item in news:
            headline = safe_text(item.get("headline"))
            when = safe_text(item.get("date"))
            summary = safe_text(item.get("summary"))
            sources = linkify_urls(item.get("source_urls", []))
            story.append(Paragraph(f"<b>{headline}</b> — {when}", styles["BodyCustom"]))
            story.append(Paragraph(summary, styles["BodyCustom"]))
            if sources:
                story.append(Paragraph(f"Sources: {sources}", styles["SmallCustom"]))
    else:
        story.append(Paragraph("Not publicly available", styles["BodyCustom"]))

    story.append(Paragraph("Key Decision-Makers", styles["SectionCustom"]))
    people = report.get("decision_makers", [])
    if people:
        for person in people:
            name = safe_text(person.get("name"))
            designation = safe_text(person.get("designation"))
            contact = safe_text(person.get("contact"))
            sources = linkify_urls(person.get("source_urls", []))
            story.append(Paragraph(f"<b>{name}</b> — {designation}", styles["BodyCustom"]))
            story.append(Paragraph(f"Contact: {contact}", styles["BodyCustom"]))
            if sources:
                story.append(Paragraph(f"Source: {sources}", styles["SmallCustom"]))
    else:
        story.append(Paragraph("Not publicly available", styles["BodyCustom"]))

    story.append(Paragraph("First Meeting Talking Points", styles["SectionCustom"]))
    talking_points = report.get("talking_points", [])
    if talking_points:
        for index, item in enumerate(talking_points, start=1):
            point = safe_text(item.get("point") if isinstance(item, dict) else item)
            sources = linkify_urls(item.get("source_urls", [])) if isinstance(item, dict) else ""
            story.append(Paragraph(f"{index}. {point}", styles["BodyCustom"]))
            if sources:
                story.append(Paragraph(f"Sources: {sources}", styles["SmallCustom"]))
    else:
        story.append(Paragraph("Not publicly available", styles["BodyCustom"]))

    story.append(PageBreak())
    story.append(Paragraph("Sources & References", styles["SectionCustom"]))
    sources = report.get("sources", [])
    if sources:
        for index, url in enumerate(sources, start=1):
            safe_url = url.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(f"{index}. <link href='{safe_url}' color='#2563EB'>{safe_url}</link>", styles["SmallCustom"]))
    else:
        story.append(Paragraph("Not publicly available", styles["BodyCustom"]))

    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    pdf = buffer.getvalue()
    buffer.close()
    if not pdf.startswith(b"%PDF"):
        raise RuntimeError("PDF generation failed.")
    return pdf
