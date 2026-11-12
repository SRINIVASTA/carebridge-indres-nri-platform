from app.services.pdf_generator import generate_invoice_pdf, generate_visit_vitals_report_pdf
from app.utils.currency import calculate_invoice_totals, convert_from_inr, convert_to_inr


def test_currency_roundtrip() -> None:
    inr_amount = 8400.0
    usd_amount = convert_from_inr(inr_amount, "USD")
    assert usd_amount == 100.0
    assert convert_to_inr(usd_amount, "USD") == 8400.0


def test_invoice_gst_only_on_service_fee() -> None:
    # ₹1,000 service fee + ₹2,500 medicine actuals -> 18% GST applies ONLY to ₹1,000 (= ₹180)
    totals = calculate_invoice_totals(service_fee_inr=1000.0, out_of_pocket_inr=2500.0, gst_rate=0.18)
    assert totals["gst_inr"] == 180.0
    assert totals["out_of_pocket_inr"] == 2500.0
    assert totals["total_inr"] == 3680.0


def test_pdf_invoice_and_visit_report_generation() -> None:
    invoice_pdf = generate_invoice_pdf(
        invoice_number="CB-INV-9001",
        nri_name="Arjun Sharma",
        nri_email="arjun@example.com",
        parent_name="Dr. Raghavendra Sharma",
        parent_city="Visakhapatnam",
        currency="USD",
        line_items=[
            {"description": "Hospital Escort", "category": "MEDICAL_ESCORT", "amount_inr": 1500.0},
            {"description": "Pharmacy Receipt", "category": "ACTUALS", "amount_inr": 950.0},
        ],
        service_fee_inr=1500.0,
        out_of_pocket_inr=950.0,
    )
    assert isinstance(invoice_pdf, bytes)
    assert invoice_pdf.startswith(b"%PDF-")

    visit_pdf = generate_visit_vitals_report_pdf(
        parent_name="Dr. Raghavendra Sharma",
        parent_city="Visakhapatnam",
        care_manager_name="Ravi Kumar",
        visit_title="Routine Vitals Check",
        checkin_time="2026-11-12 10:00 UTC",
        gps_coords="17.7412, 83.3341",
        vitals={"systolic_bp": 122, "diastolic_bp": 78, "blood_sugar_mgdl": 110, "pulse_bpm": 70, "spo2_percent": 99},
        notes="Vitals normal.",
    )
    assert isinstance(visit_pdf, bytes)
    assert visit_pdf.startswith(b"%PDF-")
