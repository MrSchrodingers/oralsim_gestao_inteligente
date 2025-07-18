"""
Modern and responsive PDF document template.
Base class for creating documents with a professional layout.
"""

import io
from datetime import date, datetime
from typing import Any

from oralsin_core.core.application.services.utils.design_system import COLORS, get_advanced_styles
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph


class ModernDocumentTemplate(BaseDocTemplate):
    """
    PDF document template with a modern and professional design.
    
    Features:
    - Responsive layout for portrait and landscape
    - Customizable header and footer
    - Consistent color system and typography
    - Support for logo and branding
    """
    
    def __init__(self, file_obj: str | io.BytesIO, **kwargs: Any):
        """
        Initializes the document template.
        
        Args:
            file_obj: File path or in-memory buffer.
            **kwargs: Additional document parameters.
        """
        self.allowSplitting = 1
        
        # Document settings
        self.logo_path = kwargs.pop("logo_path", None)
        self.clinic_name = kwargs.pop("clinic_name", "Clínica Odontológica")
        self.report_date = kwargs.pop("report_date", date.today().strftime("%d/%m/%Y"))
        self.report_period = kwargs.pop("report_period", "Período não especificado")
        self.report_title = kwargs.pop("report_title", "Relatório Gerencial")
        self.report_subtitle = kwargs.pop("report_subtitle", "")
        self.author = kwargs.pop("author", "Sistema Oralsin")
        self.version = kwargs.pop("version", "1.0")
        
        # Page settings
        page_size = kwargs.get("pagesize", A4)
        super().__init__(file_obj, pagesize=page_size, **kwargs)
        
        # Optimized margins for better space utilization
        self.left_margin = 2.2 * cm
        self.right_margin = 2.2 * cm
        self.top_margin = 3.2 * cm
        self.bottom_margin = 2.8 * cm
        
        # Configure frames for different orientations
        self._setup_page_templates()
        
        # Document styles
        self.styles = get_advanced_styles()
    
    def _setup_page_templates(self):
        """Configures page templates for portrait and landscape."""
        
        # Main frame for portrait pages
        portrait_frame = Frame(
            self.left_margin,
            self.bottom_margin,
            self.width,
            self.height,
            id='portrait_frame',
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0
        )
        
        # Frame for landscape pages
        landscape_frame = Frame(
            self.left_margin,
            self.bottom_margin,
            self.pagesize[1] - self.left_margin - self.right_margin,
            self.pagesize[0] - self.top_margin - self.bottom_margin,
            id='landscape_frame',
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0
        )
        
        # Add page templates
        self.addPageTemplates([
            PageTemplate(
                id='PortraitPage',
                frames=[portrait_frame],
                onPage=self._draw_page_layout,
                pagesize=A4
            ),
            PageTemplate(
                id='LandscapePage',
                frames=[landscape_frame],
                onPage=self._draw_page_layout,
                pagesize=landscape(A4)
            ),
        ])
    
    def _draw_page_layout(self, canvas: Any, doc: Any) -> None:
        """
        Draws the page layout with a modern header and footer.
        
        Args:
            canvas: The ReportLab canvas for drawing.
            doc: The current document.
        """
        canvas.saveState()
        
        # Determine if the page is in landscape mode
        is_landscape = doc.pagesize[0] > doc.pagesize[1]
        page_width, page_height = doc.pagesize
        
        # Draw header
        self._draw_header(canvas, page_width, page_height, is_landscape)
        
        # Draw footer
        self._draw_footer(canvas, page_width, page_height, doc.page)
        
        canvas.restoreState()
    
    def _draw_header(self, canvas: Any, width: float, height: float, is_landscape: bool):
        """
        Draws the page header with logo and information.
        
        Args:
            canvas: The canvas for drawing.
            width: The page width.
            height: The page height.
            is_landscape: If the page is in landscape mode.
        """
        header_y = height - 1.8 * cm
        
        # Draw logo (if available)
        if self.logo_path:
            try:
                canvas.drawImage(
                    self.logo_path,
                    self.left_margin,
                    header_y - 0.6 * cm,
                    width=4 * cm,
                    height=1.2 * cm,
                    preserveAspectRatio=True,
                    mask='auto'
                )
            except Exception:
                # Fallback: draw the clinic name as text
                logo_text = Paragraph(
                    f"<b>{self.clinic_name}</b>",
                    self.styles["PageHeader"]
                )
                logo_text.drawOn(canvas, self.left_margin, header_y)
        
        # Report information on the right side
        header_info = f"""
        <b>{self.report_title}</b><br/>
        {self.report_subtitle}<br/>
        <font size="8">{self.report_period} • {self.report_date}</font>
        """
        
        p_info = Paragraph(header_info.strip(), self.styles["PageHeader"])
        info_width, info_height = p_info.wrapOn(canvas, width / 2.5, 3 * cm)
        p_info.drawOn(
            canvas,
            width - self.right_margin - info_width,
            header_y - info_height / 2
        )
        
        # Decorative header line
        self._draw_decorative_line(
            canvas,
            self.left_margin,
            width - self.right_margin,
            height - self.top_margin + 1.2 * cm,
            COLORS.PRIMARY_BLUE,
            2.5
        )
    
    def _draw_footer(self, canvas: Any, width: float, height: float, page_number: int):
        """
        Draws the page footer with system information.
        
        Args:
            canvas: The canvas for drawing.
            width: The page width.
            height: The page height.
            page_number: The current page number.
        """
        footer_y = 1.8 * cm
        
        # Decorative footer line
        self._draw_decorative_line(
            canvas,
            self.left_margin,
            width - self.right_margin,
            footer_y + 0.8 * cm,
            COLORS.DARK_GRAY,
            0.8
        )
        
        # Footer text
        generation_date = datetime.now().strftime("%d/%m/%Y às %H:%M")
        footer_text = f"""
        <b>Oralsin</b> • Sistema de Gestão Odontológica • 
        Página {page_number} • Gerado em {generation_date} • 
        Versão {self.version}
        """
        
        p_footer = Paragraph(footer_text.strip(), self.styles["PageFooter"])
        footer_width, _ = p_footer.wrapOn(canvas, self.width, 1.5 * cm)
        p_footer.drawOn(
            canvas,
            self.left_margin + (self.width - footer_width) / 2,
            footer_y
        )
    
    def _draw_decorative_line(self, canvas: Any, x1: float, x2: float, y: float,  # noqa: PLR0913
                                color: Any, thickness: float):
        """
        Draws a decorative line.
        
        Args:
            canvas: The canvas for drawing.
            x1: The starting X position.
            x2: The ending X position.
            y: The Y position.
            color: The line color.
            thickness: The line thickness.
        """
        canvas.setStrokeColor(color)
        canvas.setLineWidth(thickness)
        canvas.line(x1, y, x2, y)
    
    def get_available_width(self, is_landscape: bool = False) -> float:
        """
        Returns the available width for content.
        
        Args:
            is_landscape: Whether to consider landscape mode.
            
        Returns:
            float: The available width in points.
        """
        if is_landscape:
            return landscape(A4)[0] - self.left_margin - self.right_margin
        else:
            return A4[0] - self.left_margin - self.right_margin
    
    def get_available_height(self, is_landscape: bool = False) -> float:
        """
        Returns the available height for content.
        
        Args:
            is_landscape: Whether to consider landscape mode.
            
        Returns:
            float: The available height in points.
        """
        if is_landscape:
            return landscape(A4)[1] - self.top_margin - self.bottom_margin
        else:
            return A4[1] - self.top_margin - self.bottom_margin
