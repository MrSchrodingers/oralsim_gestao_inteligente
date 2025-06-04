from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal


class FormatterService:
    """
    Utility service for formatting numbers, dates and currencies
    in Brazilian style (e.g. R$ 1.234,56 and DD/MM/YYYY).
    """

    def __init__(self, currency_symbol: str = "R$"):
        self.currency_symbol = currency_symbol

    def format_currency(self, amount: Decimal | float | int) -> str:
        """
        Format a numeric value as a BRL currency string,
        e.g. R$ 1.234,56
        """
        # ensure Decimal and two‐decimal precision
        amt = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # US style grouping; we'll swap comma/dot for Brazilian style
        us_str = f"{amt:,.2f}"  # e.g. "1,234.56"
        integer_part, decimal_part = us_str.split(".")
        # swap: US grouping comma → temp, decimal point → comma, temp → dot
        integer_brl = integer_part.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{self.currency_symbol} {integer_brl},{decimal_part}"

    def format_date(self, d: date | datetime) -> str:
        """
        Format a date (or datetime) as DD/MM/YYYY.
        """
        if isinstance(d, datetime):
            d = d.date()
        return d.strftime("%d/%m/%Y")

    def format_percentage(self, pct: float | int) -> str:
        """
        Format a ratio or percentage as an integer with '%' symbol.
        """
        return f"{pct:.0f}%"
