from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.utils.currency import CURRENCY_SYMBOLS, calculate_invoice_totals, convert_from_inr
from app.utils.datetime_helper import format_datetime_ist


def generate_invoice_pdf(
    invoice_number: str,
    nri_name: str,
    nri_email: str,
    parent_name: str,
    parent_city: str,
    currency: str,
    line_items: List[Dict[str, Any]],
    service_fee_inr: float,
    out_of_pocket_inr: float,
    issued_at: datetime | str | None = None,
) -> bytes:
    """
    Generate an itemized, transparent PDF invoice in IST separating CareBridge
    service fees (subject to 18% GST) from 100% actual out-of-pocket expenses.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    teal = colors.HexColor("#0D9488")
    slate_dark = colors.HexColor("#0F172A")
    slate_light = colors.HexColor("#F1F5F9")

    title_style = ParagraphStyle(
        "InvoiceTitle", parent=styles["Heading1"], textColor=teal, fontSize=20, spaceAfter=4
    )
    sub_style = ParagraphStyle(
        "SubHeader", parent=styles["Normal"], textColor=slate_dark, fontSize=10, leading=14
    )

    formatted_date = format_datetime_ist(issued_at)
    totals = calculate_invoice_totals(service_fee_inr, out_of_pocket_inr)
    curr = currency.upper()
    sym = CURRENCY_SYMBOLS.get(curr, "$")
    converted_total = convert_from_inr(totals["total_inr"], curr)

    elements = [
        Paragraph("CareBridge India — Official Tax Invoice & Receipt", title_style),
        Paragraph(
            f"<b>Invoice #:</b> {invoice_number} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"<b>Issued Date & Time:</b> {formatted_date}",
            sub_style,
        ),
        Spacer(1, 10),
        Paragraph(
            f"<b>Billed To (NRI):</b> {nri_name} ({nri_email})<br/>"
            f"<b>Care Beneficiary:</b> {parent_name} — {parent_city}, India",
            sub_style,
        ),
        Spacer(1, 14),
    ]

    # Line items table
    table_data = [["#", "Service / Expense Description", "Category", "Amount (INR)"]]
    for idx, item in enumerate(line_items, start=1):
        table_data.append(
            [
                str(idx),
                item.get("description", "Care Service"),
                item.get("category", "SERVICE"),
                f"INR {float(item.get('amount_inr', 0.0)):,.2f}",
            ]
        )

    item_table = Table(table_data, colWidths=[12 * mm, 92 * mm, 36 * mm, 34 * mm])
    item_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), teal),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, slate_light]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.extend([item_table, Spacer(1, 14)])

    # Totals summary table
    summary_data = [
        ["CareBridge Service Fee", f"INR {totals['service_fee_inr']:,.2f}"],
        ["GST (18% on Service Fee Only)", f"INR {totals['gst_inr']:,.2f}"],
        ["Out-of-Pocket Actuals (0% Markup)", f"INR {totals['out_of_pocket_inr']:,.2f}"],
        ["Total Payable / Paid (INR)", f"INR {totals['total_inr']:,.2f}"],
    ]
    if curr != "INR":
        summary_data.append([f"Equivalent Settled Amount ({curr})", f"{sym}{converted_total:,.2f}"])

    summary_table = Table(summary_data, colWidths=[120 * mm, 54 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, -2), (-1, -2), 1, slate_dark),
                ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), slate_light),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.extend(
        [
            summary_table,
            Spacer(1, 16),
            Paragraph(
                "<i>Note: Verified vendor bills and GPS check-in logs are archived in your "
                "CareBridge Health & Expense Vault.</i>",
                sub_style,
            ),
        ]
    )

    doc.build(elements)
    return buffer.getvalue()


def generate_visit_vitals_report_pdf(
    parent_name: str,
    parent_city: str,
    care_manager_name: str,
    visit_title: str,
    checkin_time: str,
    gps_coords: str,
    vitals: Dict[str, Any],
    notes: str,
) -> bytes:
    """Generate a post-visit Care Manager & Vitals summary PDF report with IST timestamp."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm)
    styles = getSampleStyleSheet()
    teal = colors.HexColor("#0D9488")

    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Heading1"], textColor=teal, fontSize=18, spaceAfter=6
    )
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14)

    formatted_checkin = format_datetime_ist(checkin_time)

    elements = [
        Paragraph("CareBridge India — Verified Visit & Vitals Summary", title_style),
        Paragraph(
            f"<b>Parent:</b> {parent_name} ({parent_city})<br/>"
            f"<b>Visit / Task:</b> {visit_title}<br/>"
            f"<b>Care Manager (Sahayak):</b> {care_manager_name}<br/>"
            f"<b>GPS Check-in Date & Time:</b> {formatted_checkin} ({gps_coords})",
            body_style,
        ),
        Spacer(1, 12),
    ]

    vitals_data = [
        ["Vital Sign", "Recorded Value", "Reference Note"],
        [
            "Blood Pressure",
            f"{vitals.get('systolic_bp', '-')}/{vitals.get('diastolic_bp', '-')} mmHg",
            "Target < 130/80 mmHg",
        ],
        [
            "Blood Sugar",
            f"{vitals.get('blood_sugar_mgdl', '-')} mg/dL",
            "Fasting / Post-meal logged",
        ],
        ["Pulse Rate", f"{vitals.get('pulse_bpm', '-')} bpm", "Normal 60–100 bpm"],
        ["SpO2 (Oxygen)", f"{vitals.get('spo2_percent', '-')}%", "Normal >= 95%"],
    ]

    t = Table(vitals_data, colWidths=[55 * mm, 55 * mm, 64 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), teal),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.extend(
        [
            t,
            Spacer(1, 12),
            Paragraph(f"<b>Care Manager Observations:</b><br/>{notes or 'No abnormalities noted.'}", body_style),
        ]
    )
    doc.build(elements)
    return buffer.getvalue()
