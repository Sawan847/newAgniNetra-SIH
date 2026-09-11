"""Prototype incident reports: observed evidence, missing values and analyst review."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def generate_incident_pdf(
    hotspot_data: dict[str, Any], prediction_data: dict | None = None,
    facility_data: dict | None = None, spectral_data: dict | None = None,
    risk_data: dict | None = None, verification_data: dict | None = None,
) -> BytesIO:
    """Render only supplied facts; nulls must never become confidence or imagery."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=40, rightMargin=40,
                            topMargin=36, bottomMargin=36, title="AgniNetra incident review")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Cell", fontName="Helvetica", fontSize=9, leading=12))
    story = [Paragraph("AgniNetra | Incident review", styles["Title"]),
             Paragraph("SIH26162 PROTOTYPE - analyst verification required", styles["Normal"]),
             Paragraph(f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}", styles["Normal"]), Spacer(1, 12)]

    def text(value):
        return escape("Unavailable" if value is None or value == "" else str(value))

    def number(value, suffix="", multiplier=1, precision=2):
        return "Unavailable" if value is None else f"{float(value) * multiplier:.{precision}f}{suffix}"

    def section(title, rows):
        story.append(Paragraph(title, styles["Heading2"]))
        cells = [[Paragraph(text(k), styles["Cell"]), Paragraph(text(v), styles["Cell"])] for k, v in rows]
        table = Table(cells, colWidths=[160, A4[0] - 240], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef3f8")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.extend([table, Spacer(1, 5)])

    h, p, f, s, r = hotspot_data, prediction_data or {}, facility_data or {}, spectral_data or {}, risk_data or {}
    section("1. Observed thermal detection", [
        ("Event / source", f"{h.get('event_id', 'Unavailable')} / {h.get('source') or 'Unavailable'}"),
        ("Latitude / longitude", f"{number(h.get('latitude'), precision=5)} / {number(h.get('longitude'), precision=5)}"),
        ("Acquisition (UTC)", f"{h.get('acq_date') or 'Unavailable'} {h.get('acq_time') or ''}"),
        ("Satellite / instrument", f"{h.get('satellite') or 'Unavailable'} / {h.get('instrument') or 'Unavailable'}"),
        ("FRP / brightness I4", f"{number(h.get('frp'), ' MW')} / {number(h.get('brightness'), ' K')}"),
        ("FIRMS confidence (source / encoding)", h.get('confidence')),
        ("Scan / track", f"{number(h.get('scan'), ' km')} / {number(h.get('track'), ' km')}"),
    ])
    section("2. Classification and model", [
        ("Assigned class", p.get('predicted_class') or 'Unclassified'),
        ("Stage 1 / model identifier", f"{p.get('stage1_prediction') or 'Unavailable'} / {p.get('model_version') or 'Unavailable'}"),
        ("Model confidence", number(p.get('confidence'), '%', 100)),
        ("Analyst review", (verification_data or {}).get('verified_class') or 'No review recorded'),
    ])
    section("3. Geospatial and satellite evidence", [
        ("Nearest mapped facility", f.get('name')),
        ("Facility distance", number(f.get('distance_m'), ' m')),
        ("Polygon containment", 'Inside mapped polygon' if f.get('is_inside') else 'Not established'),
        ("Sentinel-2 NDVI / NBR", f"{number(s.get('ndvi'))} / {number(s.get('nbr'))}"),
        ("Cloud fraction / land-cover code", f"{number(s.get('cloud_cover_percentage'), '%')} / {s.get('land_cover_class') if s.get('land_cover_class') is not None else 'Unavailable'}"),
    ])
    section("4. Review priority", [
        ("Heuristic triage score", number(r.get('risk_score'), ' / 100')),
        ("Suggested action", r.get('recommendation') or 'Review the available evidence and data gaps.'),
    ])
    story.append(Paragraph(
        "This student prototype is not an official incident confirmation or emergency dispatch. "
        "A thermal anomaly does not establish an accidental industrial fire, gas leak or explosion. "
        "Missing values indicate unavailable evidence. Model scores require independent validation; "
        "the triage score is an unvalidated heuristic. NASA FIRMS and OpenStreetMap are source data providers.",
        styles["Cell"]))
    doc.build(story)
    buffer.seek(0)
    return buffer
