from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

def register_roboto_family() -> None:
    """
    Registra Roboto no ReportLab (executar uma única vez).
    Usa getRegisteredFontNames() para checar, evitando o KeyError.
    """
    families = {
        "Roboto-Regular":     FONT_DIR / "Roboto-Regular.ttf",
        "Roboto-Bold":        FONT_DIR / "Roboto-Bold.ttf",
        "Roboto-Italic":      FONT_DIR / "Roboto-Italic.ttf",
        "Roboto-BoldItalic":  FONT_DIR / "Roboto-BoldItalic.ttf",
    }

    registered = pdfmetrics.getRegisteredFontNames()

    for name, path in families.items():
        if name not in registered:                # NÃO chama getFont()
            pdfmetrics.registerFont(TTFont(name, str(path)))

    # registra a família somente se o Regular já estiver disponível
    if "Roboto-Regular" in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFontFamily(
            "Roboto",
            normal="Roboto-Regular",
            bold="Roboto-Bold",
            italic="Roboto-Italic",
            boldItalic="Roboto-BoldItalic",
        )
