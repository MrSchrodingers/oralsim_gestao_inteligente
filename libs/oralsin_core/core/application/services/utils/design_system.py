"""
Design System for PDF Reports
Centralized settings for colors, fonts, and visual styles.
"""

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ==============================================================================
# PROFESSIONAL COLOR PALETTE
# ==============================================================================

class ProfessionalColors:
    """A modern and accessible color palette for corporate reports."""
    
    # Primary Brand Colors
    PRIMARY_BLUE = HexColor("#1E40AF")      # Main corporate blue
    SECONDARY_BLUE = HexColor("#3B82F6")    # Lighter blue for highlights
    LIGHT_BLUE = HexColor("#DBEAFE")        # Very light blue for backgrounds
    
    # Text Colors
    PRIMARY_TEXT = HexColor("#111827")      # Soft black for main text
    SECONDARY_TEXT = HexColor("#374151")    # Dark gray for subtext
    TERTIARY_TEXT = HexColor("#6B7280")     # Medium gray for helper text
    LIGHT_TEXT = HexColor("#9CA3AF")        # Light gray for minor info
    
    # Status and Feedback Colors
    SUCCESS = HexColor("#059669")           # Green for positive values
    LIGHT_SUCCESS = HexColor("#D1FAE5")     # Light green for backgrounds
    WARNING = HexColor("#D97706")           # Orange for warnings
    LIGHT_WARNING = HexColor("#FED7AA")     # Light orange for backgrounds
    ERROR = HexColor("#DC2626")             # Red for negative values
    LIGHT_ERROR = HexColor("#FEE2E2")       # Light red for backgrounds
    INFO = HexColor("#0891B2")              # Cyan for information
    LIGHT_INFO = HexColor("#CFFAFE")        # Light cyan for backgrounds
    
    # Neutral Colors
    WHITE = colors.white
    EXTRA_LIGHT_GRAY = HexColor("#F9FAFB")  # Card backgrounds
    LIGHT_GRAY = HexColor("#F3F4F6")        # Alternative backgrounds
    MEDIUM_GRAY = HexColor("#E5E7EB")       # Soft borders
    DARK_GRAY = HexColor("#D1D5DB")         # Sharper borders
    
    # Chart Colors (Harmonious Palette)
    CHART_1 = HexColor("#3B82F6")           # Blue
    CHART_2 = HexColor("#10B981")           # Green
    CHART_3 = HexColor("#F59E0B")           # Yellow
    CHART_4 = HexColor("#EF4444")           # Red
    CHART_5 = HexColor("#8B5CF6")           # Purple
    CHART_6 = HexColor("#06B6D4")           # Cyan


class ProfessionalFonts:
    """Configuration and registration of fonts for the system."""
    
    def __init__(self):
        self.fonts_loaded = False
        self._load_fonts()
    
    def _load_fonts(self):
        """Loads custom fonts with a safe fallback."""
        try:
            # Attempt to load custom Roboto fonts
            pdfmetrics.registerFont(TTFont('Roboto-Thin', '/app/static/fonts/Roboto-Thin.ttf'))
            pdfmetrics.registerFont(TTFont('Roboto-Light', '/app/static/fonts/Roboto-Light.ttf'))
            pdfmetrics.registerFont(TTFont('Roboto-Regular', '/app/static/fonts/Roboto-Regular.ttf'))
            pdfmetrics.registerFont(TTFont('Roboto-Medium', '/app/static/fonts/Roboto-Medium.ttf'))
            pdfmetrics.registerFont(TTFont('Roboto-Bold', '/app/static/fonts/Roboto-Bold.ttf'))
            pdfmetrics.registerFont(TTFont('Roboto-Black', '/app/static/fonts/Roboto-Black.ttf'))
            
            self.THIN = 'Roboto-Thin'
            self.LIGHT = 'Roboto-Light'
            self.REGULAR = 'Roboto-Regular'
            self.MEDIUM = 'Roboto-Medium'
            self.BOLD = 'Roboto-Bold'
            self.BLACK = 'Roboto-Black'
            self.fonts_loaded = True
            
        except Exception as e:
            # Fallback to standard system fonts
            print(f"Warning: Custom fonts not found. Using standard fonts. Error: {e}")
            self.THIN = 'Helvetica'
            self.LIGHT = 'Helvetica'
            self.REGULAR = 'Helvetica'
            self.MEDIUM = 'Helvetica-Bold'
            self.BOLD = 'Helvetica-Bold'
            self.BLACK = 'Helvetica-Bold'


# Global instances of the settings
COLORS = ProfessionalColors()
FONTS = ProfessionalFonts()


def get_advanced_styles() -> dict[str, ParagraphStyle]:
    """
    Creates a complete set of professional typographic styles.
    
    Returns:
        dict: A dictionary with all available styles for the report.
    """
    
    styles = {
        # === MAIN STRUCTURE STYLES ===
        "ReportTitle": ParagraphStyle(
            name="ReportTitle",
            fontName=FONTS.BLACK,
            fontSize=36,
            textColor=COLORS.PRIMARY_BLUE,
            alignment=TA_LEFT,
            spaceAfter=20,
            spaceBefore=10,
            leading=44,
            leftIndent=0
        ),
        
        "ReportSubtitle": ParagraphStyle(
            name="ReportSubtitle",
            fontName=FONTS.LIGHT,
            fontSize=18,
            textColor=COLORS.SECONDARY_TEXT,
            alignment=TA_LEFT,
            spaceAfter=30,
            leading=24,
            leftIndent=0
        ),
        
        "ReportDescription": ParagraphStyle(
            name="ReportDescription",
            fontName=FONTS.REGULAR,
            fontSize=12,
            textColor=COLORS.PRIMARY_TEXT,
            alignment=TA_LEFT,
            spaceAfter=15,
            leading=18,
            leftIndent=0
        ),
        
        # === HEADER AND FOOTER STYLES ===
        "PageHeader": ParagraphStyle(
            name="PageHeader",
            fontName=FONTS.MEDIUM,
            fontSize=10,
            textColor=COLORS.TERTIARY_TEXT,
            alignment=TA_LEFT,
            leading=12
        ),
        
        "PageFooter": ParagraphStyle(
            name="PageFooter",
            fontName=FONTS.REGULAR,
            fontSize=9,
            textColor=COLORS.TERTIARY_TEXT,
            alignment=TA_CENTER,
            leading=11
        ),
        
        # === SECTION TITLE STYLES ===
        "SectionTitle": ParagraphStyle(
            name="SectionTitle",
            fontName=FONTS.BOLD,
            fontSize=22,
            textColor=COLORS.PRIMARY_BLUE,
            spaceBefore=25,
            spaceAfter=15,
            keepWithNext=1,
            leading=28,
            borderBottomWidth=2,
            borderBottomColor=COLORS.SECONDARY_BLUE,
            paddingBottom=8
        ),
        
        "SectionSubtitle": ParagraphStyle(
            name="SectionSubtitle",
            fontName=FONTS.MEDIUM,
            fontSize=16,
            textColor=COLORS.PRIMARY_TEXT,
            spaceBefore=18,
            spaceAfter=10,
            keepWithNext=1,
            leading=22
        ),
        
        "SubsectionTitle": ParagraphStyle(
            name="SubsectionTitle",
            fontName=FONTS.MEDIUM,
            fontSize=14,
            textColor=COLORS.SECONDARY_TEXT,
            spaceBefore=15,
            spaceAfter=8,
            keepWithNext=1,
            leading=18
        ),
        
        # === BODY TEXT STYLES ===
        "BodyText": ParagraphStyle(
            name="BodyText",
            fontName=FONTS.REGULAR,
            fontSize=11,
            textColor=COLORS.PRIMARY_TEXT,
            leading=16,
            spaceAfter=10,
            alignment=TA_LEFT
        ),
        
        "BodyTextHighlight": ParagraphStyle(
            name="BodyTextHighlight",
            fontName=FONTS.MEDIUM,
            fontSize=11,
            textColor=COLORS.PRIMARY_TEXT,
            leading=16,
            spaceAfter=10,
            alignment=TA_LEFT
        ),
        
        "HelperText": ParagraphStyle(
            name="HelperText",
            fontName=FONTS.REGULAR,
            fontSize=10,
            textColor=COLORS.TERTIARY_TEXT,
            leading=14,
            spaceAfter=8
        ),
        
        "NoteText": ParagraphStyle(
            name="NoteText",
            fontName=FONTS.LIGHT,
            fontSize=9,
            textColor=COLORS.LIGHT_TEXT,
            leading=12,
            spaceAfter=6,
            leftIndent=10
        ),
        
        # === KPI AND METRIC STYLES ===
        "GiantKPIValue": ParagraphStyle(
            name="GiantKPIValue",
            fontName=FONTS.BLACK,
            fontSize=32,
            alignment=TA_CENTER,
            leading=38,
            spaceAfter=5
        ),
        
        "LargeKPIValue": ParagraphStyle(
            name="LargeKPIValue",
            fontName=FONTS.BOLD,
            fontSize=26,
            alignment=TA_CENTER,
            leading=32,
            spaceAfter=4
        ),
        
        "MediumKPIValue": ParagraphStyle(
            name="MediumKPIValue",
            fontName=FONTS.BOLD,
            fontSize=20,
            alignment=TA_CENTER,
            leading=24,
            spaceAfter=3
        ),
        
        "KPILabel": ParagraphStyle(
            name="KPILabel",
            fontName=FONTS.MEDIUM,
            fontSize=11,
            textColor=COLORS.TERTIARY_TEXT,
            alignment=TA_CENTER,
            spaceBefore=2,
            leading=14
        ),
        
        "KPIDescription": ParagraphStyle(
            name="KPIDescription",
            fontName=FONTS.REGULAR,
            fontSize=9,
            textColor=COLORS.LIGHT_TEXT,
            alignment=TA_CENTER,
            leading=12
        ),
        
        # === TABLE STYLES ===
        "TableHeader": ParagraphStyle(
            name="TableHeader",
            fontName=FONTS.BOLD,
            fontSize=10,
            textColor=COLORS.WHITE,
            alignment=TA_CENTER,
            leading=14
        ),
        
        "TableCell": ParagraphStyle(
            name="TableCell",
            fontName=FONTS.REGULAR,
            fontSize=10,
            textColor=COLORS.PRIMARY_TEXT,
            leading=14,
            alignment=TA_LEFT
        ),
        
        "TableCellCenter": ParagraphStyle(
            name="TableCellCenter",
            fontName=FONTS.REGULAR,
            fontSize=10,
            textColor=COLORS.PRIMARY_TEXT,
            leading=14,
            alignment=TA_CENTER
        ),
        
        "TableCellRight": ParagraphStyle(
            name="TableCellRight",
            fontName=FONTS.REGULAR,
            fontSize=10,
            textColor=COLORS.PRIMARY_TEXT,
            leading=14,
            alignment=TA_RIGHT
        ),
        
        "TableCellHighlight": ParagraphStyle(
            name="TableCellHighlight",
            fontName=FONTS.MEDIUM,
            fontSize=10,
            textColor=COLORS.PRIMARY_TEXT,
            leading=14,
            alignment=TA_LEFT
        ),
        
        # === STATUS AND FEEDBACK STYLES ===
        "SuccessText": ParagraphStyle(
            name="SuccessText",
            fontName=FONTS.MEDIUM,
            fontSize=11,
            textColor=COLORS.SUCCESS,
            leading=16
        ),
        
        "WarningText": ParagraphStyle(
            name="WarningText",
            fontName=FONTS.MEDIUM,
            fontSize=11,
            textColor=COLORS.WARNING,
            leading=16
        ),
        
        "ErrorText": ParagraphStyle(
            name="ErrorText",
            fontName=FONTS.MEDIUM,
            fontSize=11,
            textColor=COLORS.ERROR,
            leading=16
        ),
        
        "InfoText": ParagraphStyle(
            name="InfoText",
            fontName=FONTS.MEDIUM,
            fontSize=11,
            textColor=COLORS.INFO,
            leading=16
        ),
        
        # === SPECIAL STYLES ===
        "Quote": ParagraphStyle(
            name="Quote",
            fontName=FONTS.LIGHT,
            fontSize=12,
            textColor=COLORS.SECONDARY_TEXT,
            alignment=TA_LEFT,
            leftIndent=20,
            rightIndent=20,
            spaceBefore=10,
            spaceAfter=10,
            leading=18,
            borderLeftWidth=3,
            borderLeftColor=COLORS.SECONDARY_BLUE,
            paddingLeft=15
        ),
        
        "Highlight": ParagraphStyle(
            name="Highlight",
            fontName=FONTS.MEDIUM,
            fontSize=12,
            textColor=COLORS.PRIMARY_BLUE,
            alignment=TA_CENTER,
            spaceBefore=15,
            spaceAfter=15,
            leading=18,
            borderWidth=1,
            borderColor=COLORS.LIGHT_BLUE,
            paddingTop=10,
            paddingBottom=10
        )
    }
    
    return styles