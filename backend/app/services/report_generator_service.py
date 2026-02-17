from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

class ReportGeneratorService:
    def generate_meeting_report_pdf(self, meeting_data: dict) -> BytesIO:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph(f"Meeting Report: {meeting_data.get('title', 'N/A')}", styles['h1']))
        story.append(Spacer(1, 0.2 * 10))

        # Date and Time
        story.append(Paragraph(f"Date: {meeting_data.get('date', 'N/A')}", styles['Normal']))
        story.append(Paragraph(f"Time: {meeting_data.get('time', 'N/A')}", styles['Normal']))
        story.append(Spacer(1, 0.2 * 10))

        # Transcription
        story.append(Paragraph("Transcription:", styles['h2']))
        story.append(Paragraph(meeting_data.get('transcription', 'No transcription available.'), styles['Normal']))
        story.append(Spacer(1, 0.2 * 10))

        # Decisions
        story.append(Paragraph("Decisions:", styles['h2']))
        decisions = meeting_data.get('decisions', [])
        if decisions:
            for decision in decisions:
                story.append(Paragraph(f"- {decision}", styles['Normal']))
        else:
            story.append(Paragraph("No decisions recorded.", styles['Normal']))
        story.append(Spacer(1, 0.2 * 10))

        # Action Points
        story.append(Paragraph("Action Points:", styles['h2']))
        action_points = meeting_data.get('action_points', [])
        if action_points:
            for action in action_points:
                story.append(Paragraph(f"- {action}", styles['Normal']))
        else:
            story.append(Paragraph("No action points recorded.", styles['Normal']))
        story.append(Spacer(1, 0.2 * 10))

        doc.build(story)
        buffer.seek(0)
        return buffer