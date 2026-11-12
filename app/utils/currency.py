from typing import Dict

# Fallback exchange rates (1 unit of foreign currency in INR)
STATIC_RATES_TO_INR: Dict[str, float] = {
    "INR": 1.0,
    "USD": 84.0,
    "GBP": 108.5,
    "EUR": 91.2,
}

CURRENCY_SYMBOLS: Dict[str, str] = {
    "INR": "₹",
    "USD": "$",
    "GBP": "£",
    "EUR": "€",
}


def convert_from_inr(amount_inr: float, target_currency: str = "USD") -> float:
    """Convert an INR amount to target currency (USD, GBP, EUR, INR)."""
    rate = STATIC_RATES_TO_INR.get(target_currency.upper(), 84.0)
    if rate <= 0:
        return amount_inr
    return round(amount_inr / rate, 2)


def convert_to_inr(amount: float, source_currency: str = "USD") -> float:
    """Convert foreign currency into INR."""
    rate = STATIC_RATES_TO_INR.get(source_currency.upper(), 84.0)
    return round(amount * rate, 2)


def format_currency(amount_inr: float, target_currency: str = "USD") -> str:
    """Return formatted display string in target currency alongside INR if foreign."""
    curr = target_currency.upper()
    symbol = CURRENCY_SYMBOLS.get(curr, "$")
    if curr == "INR":
        return f"₹{amount_inr:,.2f}"
    converted = convert_from_inr(amount_inr, curr)
    return f"{symbol}{converted:,.2f} (₹{amount_inr:,.0f})"


def calculate_invoice_totals(service_fee_inr: float, out_of_pocket_inr: float, gst_rate: float = 0.18) -> Dict[str, float]:
    """
    Calculate transparent CareBridge totals:
    - GST applies ONLY to CareBridge service fees.
    - Out-of-pocket actuals (medicines, hospital bills, cab) pass through at 0% markup/GST.
    """
    gst_inr = round(service_fee_inr * gst_rate, 2)
    total_inr = round(service_fee_inr + gst_inr + out_of_pocket_inr, 2)
    return {
        "service_fee_inr": round(service_fee_inr, 2),
        "gst_inr": gst_inr,
        "out_of_pocket_inr": round(out_of_pocket_inr, 2),
        "total_inr": total_inr,
    }
