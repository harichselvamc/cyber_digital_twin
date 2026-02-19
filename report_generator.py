from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

from analytics import evaluate_far_frr
import datetime


def generate_report(path="report.pdf"):

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=A4)

    data = evaluate_far_frr()

    elements = []

    elements.append(Paragraph(
        "Cognitive Digital Twin Authentication Report",
        styles['Title']
    ))

    elements.append(Spacer(1,20))

    elements.append(Paragraph(
        f"Generated: {datetime.datetime.now()}",
        styles['Normal']
    ))

    elements.append(Spacer(1,20))

    for k,v in data.items():
        elements.append(
            Paragraph(f"{k}: {v}", styles['Normal'])
        )

    doc.build(elements)

    return path
