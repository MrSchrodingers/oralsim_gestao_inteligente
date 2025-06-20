"""
Utilities for formatting data in reports.
Helper functions for formatting currency, dates, numbers, and text.
"""

import locale
from datetime import date, datetime
from decimal import Decimal
from typing import Union

# Setting locale for Brazilian Portuguese
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'Portuguese_Brazil.1252')
    except locale.Error:
        print("Warning: pt_BR locale not available. Using default settings.")


class BrazilianFormatter:
    """Class for formatting data according to Brazilian standards."""
    
    # Mapping of months in Portuguese
    PORTUGUESE_MONTHS = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
    }
    
    ABBREVIATED_MONTHS = {
        1: "jan", 2: "fev", 3: "mar", 4: "abr",
        5: "mai", 6: "jun", 7: "jul", 8: "ago",
        9: "set", 10: "out", 11: "nov", 12: "dez"
    }
    
    WEEK_DAYS = {
        0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira",
        3: "quinta-feira", 4: "sexta-feira", 5: "sábado", 6: "domingo"
    }
    
    @staticmethod
    def format_currency(value: Union[int, float, Decimal, str], symbol: str = "R$", 
                        short_format: bool = False) -> str:
        """
        Formats monetary values in the Brazilian standard.
        
        Args:
            value: The value to be formatted.
            symbol: The currency symbol (default: R$).
            short_format: If True, uses abbreviated notation (k, M, B).
            
        Returns:
            str: The value formatted as Brazilian currency.
        """
        try:
            if value is None:
                return f"{symbol} 0,00"
            
            # Convert to float
            if isinstance(value, str):
                value = float(value.replace(',', '.').replace(symbol, '').strip())
            elif isinstance(value, Decimal):
                value = float(value)
            
            value = float(value)
            
            # Short format for large values
            if short_format:
                if abs(value) >= 1_000_000_000:
                    return f"{symbol} {value/1_000_000_000:.1f}B".replace('.', ',')
                elif abs(value) >= 1_000_000:
                    return f"{symbol} {value/1_000_000:.1f}M".replace('.', ',')
                elif abs(value) >= 1_000:
                    return f"{symbol} {value/1_000:.1f}k".replace('.', ',')
            
            # Full formatting
            formatted_value = f"{value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            return f"{symbol} {formatted_value}"
            
        except (ValueError, TypeError):
            return f"{symbol} 0,00"
    
    @staticmethod
    def format_number(number: Union[int, float], decimal_places: int = 0, 
                      use_thousands_separator: bool = True) -> str:
        """
        Formats numbers according to the Brazilian standard.
        
        Args:
            number: The number to be formatted.
            decimal_places: The number of decimal places.
            use_thousands_separator: Whether to use a thousands separator.
            
        Returns:
            str: The formatted number.
        """
        try:
            if number is None:
                return "0"
            
            number = float(number)
            
            if use_thousands_separator:
                if decimal_places > 0:
                    formatted = f"{number:,.{decimal_places}f}"
                else:
                    formatted = f"{number:,.0f}"
                # Adjust to Brazilian standard
                return formatted.replace(',', 'X').replace('.', ',').replace('X', '.')
            else:
                return f"{number:.{decimal_places}f}".replace('.', ',')
                
        except (ValueError, TypeError):
            return "0"
    
    @staticmethod
    def format_percentage(value: Union[int, float], decimal_places: int = 1) -> str:
        """
        Formats percentages.
        
        Args:
            value: The percentage value (e.g., 0.15 for 15%).
            decimal_places: The number of decimal places.
            
        Returns:
            str: The formatted percentage.
        """
        try:
            if value is None:
                return "0%"
            
            value = float(value)
            # If the value is already in percentage format (>1), do not multiply by 100
            if abs(value) > 1:
                percentage = value
            else:
                percentage = value * 100
                
            return f"{percentage:.{decimal_places}f}%".replace('.', ',')
            
        except (ValueError, TypeError):
            return "0%"
    
    @staticmethod
    def format_date(date_obj: Union[date, datetime, str], format_type: str = "completo") -> str:
        """
        Formats dates in Brazilian Portuguese.
        
        Args:
            date_obj: The date to be formatted.
            format_type: The format type ('completo', 'curto', 'numerico', 'mes_ano').
            
        Returns:
            str: The formatted date.
        """
        try:
            if isinstance(date_obj, str):
                # Try to convert string to datetime
                if 'T' in date_obj:  # ISO format
                    date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
                else:
                    date_obj = datetime.strptime(date_obj, '%Y-%m-%d')
            
            if isinstance(date_obj, datetime):
                date_obj = date_obj.date()
            
            if not isinstance(date_obj, date):
                return "Invalid date"
            
            if format_type == "completo":
                week_day = BrazilianFormatter.WEEK_DAYS[date_obj.weekday()]
                month = BrazilianFormatter.PORTUGUESE_MONTHS[date_obj.month]
                return f"{week_day}, {date_obj.day} de {month} de {date_obj.year}"
            
            elif format_type == "curto":
                month = BrazilianFormatter.PORTUGUESE_MONTHS[date_obj.month]
                return f"{date_obj.day} de {month} de {date_obj.year}"
            
            elif format_type == "numerico":
                return date_obj.strftime("%d/%m/%Y")
            
            elif format_type == "mes_ano":
                month = BrazilianFormatter.PORTUGUESE_MONTHS[date_obj.month]
                return f"{month.capitalize()} de {date_obj.year}"
            
            elif format_type == "abrev":
                month = BrazilianFormatter.ABBREVIATED_MONTHS[date_obj.month]
                return f"{date_obj.day}/{month}/{date_obj.year}"
            
            else:
                return date_obj.strftime("%d/%m/%Y")
                
        except (ValueError, AttributeError, KeyError, TypeError):
            return "Invalid date"
    
    @staticmethod
    def format_period(start_date: Union[date, datetime], 
                      end_date: Union[date, datetime]) -> str:
        """
        Formats a period between two dates.
        
        Args:
            start_date: The start date of the period.
            end_date: The end date of the period.
            
        Returns:
            str: The formatted period.
        """
        try:
            start_fmt = BrazilianFormatter.format_date(start_date, "numerico")
            end_fmt = BrazilianFormatter.format_date(end_date, "numerico")
            return f"{start_fmt} a {end_fmt}"
        except:
            return "Invalid period"
    
    @staticmethod
    def get_greeting() -> str:
        """
        Returns a greeting based on the current time.
        
        Returns:
            str: The appropriate greeting.
        """
        current_hour = datetime.now().hour
        
        if 5 <= current_hour < 12:
            return "Bom dia"
        elif 12 <= current_hour < 18:
            return "Boa tarde"
        else:
            return "Boa noite"
    
    @staticmethod
    def pluralize(quantity: int, singular_form: str, plural_form: str = None) -> str:
        """
        Pluralizes words based on the quantity.
        
        Args:
            quantity: The number to determine plural/singular.
            singular_form: The singular form of the word.
            plural_form: The plural form (if None, 's' is added).
            
        Returns:
            str: The word in the appropriate singular or plural form.
        """
        quantity = int(quantity)
        if quantity == 1:
            return f"{quantity} {singular_form}"
        else:
            plural_word = plural_form if plural_form else f"{singular_form}s"
            return f"{quantity} {plural_word}"
    
    @staticmethod
    def format_phone_number(phone_number: str) -> str:
        """
        Formats Brazilian phone numbers.
        
        Args:
            phone_number: The phone number.
            
        Returns:
            str: The formatted phone number.
        """
        try:
            # Remove non-numeric characters
            numbers = ''.join(filter(str.isdigit, str(phone_number)))
            
            if len(numbers) == 11:  # Mobile with area code
                return f"({numbers[:2]}) {numbers[2:7]}-{numbers[7:]}"
            elif len(numbers) == 10:  # Landline with area code
                return f"({numbers[:2]}) {numbers[2:6]}-{numbers[6:]}"
            else:
                return phone_number  # Return original if formatting fails
                
        except:
            return str(phone_number)


# Global formatter instance
formatter = BrazilianFormatter()