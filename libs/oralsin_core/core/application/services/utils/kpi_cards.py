"""
Components for creating modern and informative KPI cards.
"""

from typing import Any, List, Tuple

from oralsin_core.core.application.services.utils.design_system import COLORS, get_advanced_styles
from oralsin_core.core.application.services.utils.formatters import BrazilianFormatter
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Table, TableStyle


class KPICardGenerator:
    """Generator for KPI cards with a modern and responsive design."""
    
    def __init__(self):
        self.styles = get_advanced_styles()
    
    def create_simple_kpi_card(self, title: str, value: str, value_color: Any = COLORS.PRIMARY_BLUE,
                                   description: str = "", icon: str = "") -> Table:
        """
        Creates a simple KPI card with a title, value, and description.
        
        Args:
            title: The KPI title.
            value: The main KPI value.
            value_color: The color of the main value.
            description: An additional description (optional).
            icon: A text/emoji icon (optional).
            
        Returns:
            Table: A formatted KPI card.
        """
        # Create card elements
        elements = []
        
        # Icon (if provided)
        if icon:
            p_icon = Paragraph(f"<font size='16'>{icon}</font>", self.styles["KPILabel"])
            elements.append([p_icon])
        
        # Main value
        value_style = self.styles["MediumKPIValue"].clone('temp_value')
        value_style.textColor = value_color
        p_value = Paragraph(f"<b>{value}</b>", value_style)
        elements.append([p_value])
        
        # Title
        p_title = Paragraph(f"<b>{title}</b>", self.styles["KPILabel"])
        elements.append([p_title])
        
        # Description (if provided)
        if description:
            p_description = Paragraph(description, self.styles["KPIDescription"])
            elements.append([p_description])
        
        # Calculate row heights
        row_heights = []
        if icon:
            row_heights.append(0.8 * cm)
        row_heights.extend([1.2 * cm, 0.6 * cm])
        if description:
            row_heights.append(0.5 * cm)
        
        # Create the card table
        card = Table(elements, colWidths=['100%'], rowHeights=row_heights)
        
        # Apply modern style
        card_style = [
            ('BACKGROUND', (0, 0), (-1, -1), COLORS.WHITE),
            ('BOX', (0, 0), (-1, -1), 1.5, COLORS.MEDIUM_GRAY),
            ('ROUNDEDCORNERS', (0, 0), (-1, -1), [8, 8, 8, 8]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]
        
        card.setStyle(TableStyle(card_style))
        return card
    
    def create_comparative_kpi_card(self, title: str, current_value: str, previous_value: str,
                                        variation: float, is_currency: bool = True) -> Table:
        """
        Creates a KPI card with a comparison and trend indicator.
        
        Args:
            title: The KPI title.
            current_value: The current value.
            previous_value: The value from the previous period.
            variation: The percentage variation.
            is_currency: If the values are monetary.
            
        Returns:
            Table: A comparative KPI card.
        """
        formatter = BrazilianFormatter()
        # Determine variation color and icon
        if variation > 0:
            variation_color = COLORS.SUCCESS
            variation_icon = "↗"
            variation_text = f"+{formatter.format_percentage(variation/100)}"
        elif variation < 0:
            variation_color = COLORS.ERROR
            variation_icon = "↘"
            variation_text = f"{formatter.format_percentage(variation/100)}"
        else:
            variation_color = COLORS.TERTIARY_TEXT
            variation_icon = "→"
            variation_text = "0%"
        
        # Card elements
        elements = [
            # Current value
            [Paragraph(f"<b>{current_value}</b>", self.styles["MediumKPIValue"])],
            # Title
            [Paragraph(f"<b>{title}</b>", self.styles["KPILabel"])],
            # Comparison
            [Paragraph(
                f"<font color='{variation_color}'>{variation_icon} {variation_text}</font> vs período anterior",
                self.styles["KPIDescription"]
            )],
            # Previous value
            [Paragraph(f"Anterior: {previous_value}", self.styles["KPIDescription"])]
        ]
        
        card = Table(elements, colWidths=['100%'], 
                     rowHeights=[1.5 * cm, 0.6 * cm, 0.5 * cm, 0.4 * cm])
        
        card_style = [
            ('BACKGROUND', (0, 0), (-1, -1), COLORS.WHITE),
            ('BOX', (0, 0), (-1, -1), 1.5, COLORS.MEDIUM_GRAY),
            ('ROUNDEDCORNERS', (0, 0), (-1, -1), [8, 8, 8, 8]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]
        
        card.setStyle(TableStyle(card_style))
        return card
    
    def create_kpi_grid(self, kpis: List[Tuple[str, str, Any]], available_width: float,
                        columns: int = 3) -> Table:
        """
        Creates a grid of KPI cards organized into columns.
        
        Args:
            kpis: A list of tuples (title, value, color).
            available_width: The available width for the grid.
            columns: The number of columns in the grid.
            
        Returns:
            Table: A grid of KPIs.
        """
        # Create individual cards
        cards = []
        for title, value, color in kpis:
            card = self.create_simple_kpi_card(title, value, color)
            cards.append(card)
        
        # Organize into rows and columns
        rows = []
        for i in range(0, len(cards), columns):
            row = cards[i:i + columns]
            # Fill incomplete rows with empty cells
            while len(row) < columns:
                row.append("")
            rows.append(row)
        
        # Calculate column widths
        column_width = available_width / columns
        column_widths = [column_width] * columns
        
        # Create the grid table
        grid = Table(rows, colWidths=column_widths, 
                     rowHeights=[4 * cm] * len(rows))
        
        # Grid style
        grid_style = [
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]
        
        grid.setStyle(TableStyle(grid_style))
        return grid
    
    def create_detailed_kpi_card(self, title: str, main_value: str, 
                                     secondary_metrics: List[Tuple[str, str]],
                                     main_color: Any = COLORS.PRIMARY_BLUE) -> Table:
        """
        Creates a detailed KPI card with secondary metrics.
        
        Args:
            title: The main KPI title.
            main_value: The main highlighted value.
            secondary_metrics: A list of tuples (label, value) for secondary metrics.
            main_color: The color of the main value.
            
        Returns:
            Table: A detailed KPI card.
        """
        elements = []
        
        # Main value
        value_style = self.styles["LargeKPIValue"].clone('temp_detailed_value')
        value_style.textColor = main_color
        elements.append([Paragraph(f"<b>{main_value}</b>", value_style)])
        
        # Main title
        elements.append([Paragraph(f"<b>{title}</b>", self.styles["KPILabel"])])
        
        # Visual separator line
        elements.append([Paragraph("─" * 20, self.styles["KPIDescription"])])
        
        # Secondary metrics
        for label, value in secondary_metrics:
            metric_text = f"<b>{label}:</b> {value}"
            elements.append([Paragraph(metric_text, self.styles["HelperText"])])
        
        # Calculate heights
        row_heights = [1.8 * cm, 0.6 * cm, 0.3 * cm]
        row_heights.extend([0.4 * cm] * len(secondary_metrics))
        
        card = Table(elements, colWidths=['100%'], rowHeights=row_heights)
        
        card_style = [
            ('BACKGROUND', (0, 0), (-1, -1), COLORS.WHITE),
            ('BOX', (0, 0), (-1, -1), 1.5, COLORS.MEDIUM_GRAY),
            ('ROUNDEDCORNERS', (0, 0), (-1, -1), [8, 8, 8, 8]),
            ('VALIGN', (0, 0), (0, 2), 'MIDDLE'),     # Center value and title
            ('VALIGN', (0, 3), (-1, -1), 'TOP'),      # Align metrics to the top
            ('ALIGN', (0, 0), (0, 2), 'CENTER'),      # Center value and title
            ('ALIGN', (0, 3), (-1, -1), 'LEFT'),      # Align metrics to the left
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]
        
        card.setStyle(TableStyle(card_style))
        return card