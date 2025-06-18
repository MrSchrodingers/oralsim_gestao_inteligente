# libs/oralsin_core/core/application/services/dashboard_pdf_service.py

from __future__ import annotations

import io
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
import math
from typing import Any

from reportlab.graphics.charts.axes import XCategoryAxis
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepInFrame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from oralsin_core.core.application.dtos.dashboard_dto import DashboardDTO, StatsDTO
from oralsin_core.core.domain.services.formatter_service import FormatterService
from plugins.django_interface.models import Clinic, ClinicData, ClinicPhone, User

# --------------------------------------------------------------------------
#  Cores e Fontes Modernizadas
# --------------------------------------------------------------------------
ORALSIN_PRIMARY_BLUE = HexColor("#004A99")
ORALSIN_ACCENT_BLUE = HexColor("#0D6EFD")
TEXT_COLOR_DARK = HexColor("#212529")
TEXT_COLOR_MEDIUM = HexColor("#495057")
TEXT_COLOR_LIGHT = HexColor("#6C757D")
BORDER_COLOR = HexColor("#DEE2E6")
BACKGROUND_LIGHT = HexColor("#F8F9FA")
WHITE = colors.white
SUCCESS_GREEN = HexColor("#198754")
DANGER_RED = HexColor("#DC3545")
WARNING_YELLOW = HexColor("#FFC107")

try:
    pdfmetrics.registerFont(TTFont('Roboto-Regular', '/app/static/fonts/Roboto-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('Roboto-Medium', '/app/static/fonts/Roboto-Medium.ttf'))
    pdfmetrics.registerFont(TTFont('Roboto-Bold', '/app/static/fonts/Roboto-Bold.ttf'))
    ROBOTO_REGULAR = 'Roboto-Regular'
    ROBOTO_MEDIUM = 'Roboto-Medium'
    ROBOTO_BOLD = 'Roboto-Bold'
except Exception:
    ROBOTO_REGULAR = 'Helvetica'
    ROBOTO_MEDIUM = 'Helvetica-Bold'
    ROBOTO_BOLD = 'Helvetica-Bold'


def get_modern_styles() -> dict[str, ParagraphStyle]:
    """Cria um conjunto de estilos de parágrafo modernos para o relatório."""
    return {
        "DocTitle": ParagraphStyle(name="DocTitle", fontName=ROBOTO_BOLD, fontSize=28, textColor=ORALSIN_PRIMARY_BLUE, alignment=TA_LEFT, spaceAfter=12),
        "PageHeader": ParagraphStyle(name="PageHeader", fontName=ROBOTO_REGULAR, fontSize=9, textColor=TEXT_COLOR_MEDIUM, alignment=TA_LEFT),
        "PageFooter": ParagraphStyle(name="PageFooter", fontName=ROBOTO_REGULAR, fontSize=8, textColor=TEXT_COLOR_LIGHT, alignment=TA_CENTER),
        "SectionTitle": ParagraphStyle(name="SectionTitle", fontName=ROBOTO_BOLD, fontSize=18, textColor=ORALSIN_PRIMARY_BLUE, spaceBefore=12, spaceAfter=10, keepWithNext=1, leading=22),
        "SubSectionTitle": ParagraphStyle(name="SubSectionTitle", fontName=ROBOTO_MEDIUM, fontSize=14, textColor=TEXT_COLOR_DARK, spaceBefore=8, spaceAfter=6, keepWithNext=1, leading=18),
        "BodyText": ParagraphStyle(name="BodyText", fontName=ROBOTO_REGULAR, fontSize=10, textColor=TEXT_COLOR_DARK, leading=14, spaceAfter=6),
        "BodyTextMuted": ParagraphStyle(name="BodyTextMuted", fontName=ROBOTO_REGULAR, fontSize=9, textColor=TEXT_COLOR_MEDIUM, leading=12),
        "KPIValue": ParagraphStyle(name="KPIValue", fontName=ROBOTO_BOLD, fontSize=22, alignment=TA_CENTER, leading=26),
        "KPILabel": ParagraphStyle(name="KPILabel", fontName=ROBOTO_REGULAR, fontSize=9, textColor=TEXT_COLOR_MEDIUM, alignment=TA_CENTER, spaceBefore=2, leading=12),
        "TableHeader": ParagraphStyle(name="TableHeader", fontName=ROBOTO_MEDIUM, fontSize=9, textColor=WHITE, alignment=TA_CENTER, leading=12),
        "TableCell": ParagraphStyle(name="TableCell", fontName=ROBOTO_REGULAR, fontSize=9, textColor=TEXT_COLOR_DARK, leading=12),
        "TableCellRight": ParagraphStyle(name="TableCellRight", fontName=ROBOTO_REGULAR, fontSize=9, textColor=TEXT_COLOR_DARK, leading=12, alignment=TA_RIGHT),
    }

# --------------------------------------------------------------------------
#  Template do Documento com Cabeçalho e Rodapé Modernizados
# --------------------------------------------------------------------------
class ModernReportDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        self.allowSplitting = 1
        super().__init__(filename, **kwargs)
        self.logo_path = kwargs.get("logo_path")
        self.clinic_name = kwargs.get("clinic_name", "Relatório de Gestão")
        self.report_date_str = kwargs.get("report_date_str", date.today().strftime("%d/%m/%Y"))
        self.styles = get_modern_styles()

        self.leftMargin = 2*cm
        self.rightMargin = 2*cm
        self.topMargin = 2.5*cm
        self.bottomMargin = 2*cm

        main_frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id='main_frame')
        landscape_frame = Frame(self.leftMargin, self.bottomMargin, A4[1] - self.leftMargin - self.rightMargin, A4[0] - self.topMargin - self.bottomMargin, id='landscape_frame_main')

        self.addPageTemplates([
            PageTemplate(id='PortraitPage', frames=[main_frame], onPage=self._draw_header_footer, pagesize=A4),
            PageTemplate(id='LandscapePage', frames=[landscape_frame], onPage=self._draw_header_footer_landscape, pagesize=landscape(A4))
        ])

    def _draw_common_header_elements(self, canvas, doc, page_width, page_height):
        canvas.saveState()
        canvas.setStrokeColor(ORALSIN_PRIMARY_BLUE)
        canvas.setLineWidth(1.5)
        canvas.line(self.leftMargin, page_height + self.topMargin - 0.5*cm, self.leftMargin + page_width, page_height + self.topMargin - 0.5*cm)

        if self.logo_path:
            canvas.drawImage(self.logo_path, self.leftMargin, page_height + self.topMargin - 1.7*cm, width=3.5*cm, height=1*cm, preserveAspectRatio=True, mask='auto')

        header_clinic_text = Paragraph(self.clinic_name, self.styles["PageHeader"])
        header_date_text = Paragraph(f"Relatório de: {self.report_date_str}", self.styles["PageHeader"])
        
        w_clinic, h_clinic = header_clinic_text.wrapOn(canvas, page_width / 2, 0.5*cm)
        header_clinic_text.drawOn(canvas, self.leftMargin + page_width - w_clinic, page_height + self.topMargin - 1.0*cm)

        w_date, h_date = header_date_text.wrapOn(canvas, page_width / 2, 0.5*cm)
        header_date_text.drawOn(canvas, self.leftMargin + page_width - w_date, page_height + self.topMargin - 1.0*cm - h_clinic - 0.1*cm)

        canvas.restoreState()

    def _draw_common_footer_elements(self, canvas, doc, page_width):
        canvas.saveState()
        canvas.setStrokeColor(BORDER_COLOR)
        canvas.setLineWidth(0.5)
        canvas.line(self.leftMargin, self.bottomMargin - 0.3*cm, self.leftMargin + page_width, self.bottomMargin - 0.3*cm)

        footer_text = Paragraph(f"Página {doc.page}  |  Oralsin Gestão Inteligente", self.styles["PageFooter"])
        w, h = footer_text.wrapOn(canvas, page_width, self.bottomMargin)
        footer_text.drawOn(canvas, self.leftMargin + (page_width - w)/2, self.bottomMargin - 0.3*cm - h)
        canvas.restoreState()

    def _draw_header_footer(self, canvas, doc):
        self._draw_common_header_elements(canvas, doc, doc.width, doc.height)
        self._draw_common_footer_elements(canvas, doc, doc.width)

    def _draw_header_footer_landscape(self, canvas, doc):
        self._draw_common_header_elements(canvas, doc, doc.width, doc.height)
        self._draw_common_footer_elements(canvas, doc, doc.width)

# --------------------------------------------------------------------------
#  Serviço Principal de Geração de PDF Modernizado
# --------------------------------------------------------------------------
class DashboardPDFService:
    def __init__(self, formatter: FormatterService, logo_path: str):
        self._fmt = formatter
        self._logo_path = logo_path
        self.styles = get_modern_styles()
        self.report_date = date.today()

    def build(self, user: User, clinic: Clinic, clinic_data: ClinicData, clinic_phones: ClinicPhone, dashboard: DashboardDTO, **kwargs: Any) -> bytes:
        buffer = io.BytesIO()
        doc = ModernReportDocTemplate(
            buffer,
            title=f"Relatório de Gestão - {clinic.name}",
            author="Oralsin Gestão Inteligente",
            logo_path=self._logo_path,
            clinic_name=clinic.name,
            report_date_str=self.report_date.strftime("%d/%m/%Y")
        )

        collection_summary = kwargs.get("collection_summary")
        notification_summary = kwargs.get("notification_summary")
        last_notifications = kwargs.get("last_notifications")

        story: list[Flowable] = []
        story.extend(self._build_cover_page(clinic))
        story.append(NextPageTemplate('PortraitPage'))
        story.append(PageBreak())

        story.extend(self._build_kpi_section(dashboard.stats, collection_summary))
        story.append(Spacer(1, 0.8 * cm))
        story.extend(self._build_collection_funnel_section(collection_summary))
        story.append(Spacer(1, 0.8 * cm))
        story.extend(self._build_communication_section(notification_summary, last_notifications))
        
        story.append(NextPageTemplate('LandscapePage'))
        story.append(PageBreak())
        story.extend(self._build_financial_details_section(dashboard))
        story.append(NextPageTemplate('PortraitPage'))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    def _build_cover_page(self, clinic: Clinic) -> list[Flowable]:
        report_date_str = self.report_date.strftime("%d de %B de %Y").capitalize()
        return [
            Spacer(1, 6 * cm),
            Paragraph("Relatório de Gestão Financeira e Operacional", self.styles["DocTitle"]),
            Spacer(1, 1 * cm),
            Paragraph(f"<b>Clínica:</b> {clinic.name}", self.styles["SubSectionTitle"]),
            Paragraph(f"<b>Data de Emissão:</b> {report_date_str}", self.styles["SubSectionTitle"]),
            Spacer(1, 0.5 * cm),
            Paragraph("Análise consolidada dos principais indicadores financeiros e operacionais da clínica para a tomada de decisão estratégica.", self.styles["BodyText"]),
        ]
    
    def _create_kpi_card(self, label: str, value: Any, value_color: HexColor) -> Table:
        p_value = Paragraph(str(value), self.styles["KPIValue"])
        p_value.style.textColor = value_color
        p_label = Paragraph(label, self.styles["KPILabel"])
        card_table = Table([[p_value], [p_label]], rowHeights=[1.2*cm, 0.8*cm])
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BACKGROUND_LIGHT),
            ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        return card_table

    def _build_kpi_section(self, stats: StatsDTO, collection_summary: dict | None) -> list[Flowable]:
        collection_cases = collection_summary.get('total_cases', 0) if collection_summary else 0
        kpis_data = [
            ("Total a Receber", stats.totalReceivables, SUCCESS_GREEN),
            ("Pagos no Mês", stats.paidThisMonth, SUCCESS_GREEN),
            ("Pagamentos Vencidos", stats.overduePayments, DANGER_RED),
            ("Taxa de Cobrança", f"{stats.collectionRate}%", ORALSIN_ACCENT_BLUE),
            ("Casos de Cobrança", str(collection_cases), WARNING_YELLOW),
            ("Dias Médios Atraso", str(stats.averageDaysOverdue), DANGER_RED),
        ]
        
        kpi_cards = [self._create_kpi_card(label, value, color) for label, value, color in kpis_data]
        col_width = (A4[0] - 4*cm) / 3 
        kpi_table = Table([kpi_cards[i:i+3] for i in range(0, len(kpi_cards), 3)], colWidths=[col_width, col_width, col_width], hAlign='LEFT')
        kpi_table.setStyle(TableStyle([('RIGHTPADDING', (0,0), (-2,-1), 0.5*cm)]))

        return [Paragraph("Painel de Indicadores Chave (KPIs)", self.styles["SectionTitle"]), KeepInFrame(A4[0] - 4*cm, 10*cm, [kpi_table])]

    def _build_styled_table(self, data_rows: list[list[Any]], col_widths: list[float]) -> Table:
        table = Table(data_rows, colWidths=col_widths, repeatRows=1)
        base_style = [
            ('BACKGROUND', (0,0), (-1,0), ORALSIN_PRIMARY_BLUE),
            ('TEXTCOLOR', (0,0), (-1,0), WHITE),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), ROBOTO_MEDIUM),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('TOPPADDING', (0,0), (-1,0), 8),
            ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ]
        for i in range(1, len(data_rows)):
            if i % 2 != 0:
                base_style.append(('BACKGROUND', (0,i), (-1,i), BACKGROUND_LIGHT))
        table.setStyle(TableStyle(base_style))
        return table
        
    def _build_collection_funnel_section(self, summary: dict | None) -> list[Flowable]:
        title = Paragraph("Funil de Cobrança", self.styles["SectionTitle"])
        if not summary or not summary.get('by_status'):
            return [title, Paragraph("Dados de cobrança indisponíveis.", self.styles["BodyTextMuted"])]

        header = [Paragraph(h, self.styles["TableHeader"]) for h in ["Status da Cobrança", "Nº de Casos", "Valor Total"]]
        data_rows = [header] + [
            [
                Paragraph(item['status'].replace('_', ' ').capitalize(), self.styles["TableCell"]),
                Paragraph(str(item['count']), self.styles["TableCellRight"]),
                Paragraph(self._fmt.format_currency(item['total_value']), self.styles["TableCellRight"]),
            ] for item in summary.get('by_status', [])
        ]
        
        page_width = A4[0] - 4*cm
        col_widths = [page_width * 0.5, page_width * 0.2, page_width * 0.3]
        return [title, self._build_styled_table(data_rows, col_widths)]

    def _build_communication_section(self, notif_summary: dict | None, last_notifications: Sequence | None) -> list[Flowable]:
        title = Paragraph("Eficiência da Comunicação", self.styles["SectionTitle"])
        if not notif_summary:
            return [title, Paragraph("Dados de notificação indisponíveis.", self.styles["BodyTextMuted"])]

        status_header = [Paragraph(h, self.styles["TableHeader"]) for h in ["Status", "Quantidade"]]
        status_data = [status_header,
            [Paragraph("Pendente", self.styles["TableCell"]), Paragraph(str(notif_summary.get('PENDING', 0)), self.styles["TableCellRight"])],
            [Paragraph("Enviado", self.styles["TableCell"]), Paragraph(str(notif_summary.get('SENT', 0)), self.styles["TableCellRight"])],
            [Paragraph("Com Erro", self.styles["TableCell"]), Paragraph(str(notif_summary.get('ERROR', 0)), self.styles["TableCellRight"])],
        ]
        page_width = A4[0] - 4*cm
        status_table = self._build_styled_table(status_data, [page_width*0.7, page_width*0.3])
        elements = [title, status_table, Spacer(1, 0.8*cm)]

        if last_notifications:
            last_notif_title = Paragraph("Últimas Notificações Enviadas", self.styles["SubSectionTitle"])
            last_notif_header = [Paragraph(h, self.styles["TableHeader"]) for h in ["Paciente", "Data", "Canal", "Status"]]
            last_notif_data = [last_notif_header] + [
                [
                    Paragraph(getattr(n, 'patient_name', 'N/A'), self.styles["TableCell"]),
                    Paragraph(n.sent_at.strftime('%d/%m/%Y %H:%M'), self.styles["TableCell"]),
                    Paragraph(n.channel, self.styles["TableCell"]),
                    Paragraph(n.status, self.styles["TableCell"]),
                ] for n in last_notifications
            ]
            last_notif_cols = [page_width*0.35, page_width*0.25, page_width*0.15, page_width*0.25]
            elements.extend([last_notif_title, self._build_styled_table(last_notif_data, last_notif_cols)])

        return elements

    def _build_financial_details_section(self, d: DashboardDTO) -> list[Flowable]:
        elements = [Paragraph("Detalhes Financeiros", self.styles["SectionTitle"])]
        landscape_width = A4[1] - 4*cm
        col_widths = [landscape_width * 0.4, landscape_width * 0.2, landscape_width * 0.2, landscape_width * 0.2]
        style_pending_value = ParagraphStyle(name='PendingValue', parent=self.styles['TableCellRight'], textColor=DANGER_RED)

        elements.append(Paragraph("Pagamentos Recebidos Recentemente", self.styles["SubSectionTitle"]))
        if d.recentPayments:
            header = [Paragraph(h, self.styles["TableHeader"]) for h in ["Paciente", "Valor", "Data", "Status"]]
            data = [header] + [[Paragraph(p.patient), Paragraph(p.amount, self.styles['TableCellRight']), Paragraph(p.date), Paragraph(p.status)] for p in d.recentPayments]
            elements.append(self._build_styled_table(data, col_widths))
        else:
             elements.append(Paragraph("Nenhum pagamento recente.", self.styles["BodyTextMuted"]))

        elements.extend([Spacer(1, 0.8 * cm), Paragraph("Próximos Pagamentos Pendentes", self.styles["SubSectionTitle"])])
        if d.pendingPayments:
            header = [Paragraph(h, self.styles["TableHeader"]) for h in ["Paciente", "Valor", "Vencimento", "Status"]]
            data = [header] + [[Paragraph(p.patient), Paragraph(p.amount, style_pending_value), Paragraph(p.date), Paragraph(p.status)] for p in d.pendingPayments]
            elements.append(self._build_styled_table(data, col_widths))
        else:
             elements.append(Paragraph("Nenhum pagamento pendente.", self.styles["BodyTextMuted"]))

        elements.append(Spacer(1, 0.8 * cm))
        chart = self._build_receivables_chart(d.monthlyReceivables, landscape_width)
        if chart:
            elements.append(chart)
        return elements

    def _build_receivables_chart(
        self,
        monthly_data: Sequence | None,
        available_width: float
    ) -> Flowable | None:
        """
        Gráfico Previsto × Realizado blindado contra listas de pontos ímpares.
        Se alguma série acabar com número ímpar de valores, é descartada.
        """
        from reportlab.graphics.shapes import Drawing, String

        if not monthly_data:
            return None

        # ---------- helpers ----------
        def _is_num(v):
            return isinstance(v, (int, float, Decimal)) and math.isfinite(float(v))  # noqa: UP038

        def _clean(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
            """Garante tamanho ≥ 2 e lista achatada par."""
            if len(points) < 2:
                return []
            flat_len = len(points) * 2      # (x,y) sempre dois valores
            return points if flat_len % 2 == 0 else []

        # ---------- coleta ----------
        receivables = _clean(
            [(i, float(r.receivable))
             for i, r in enumerate(monthly_data) if _is_num(r.receivable)]
        )
        paids = _clean(
            [(i, float(r.paid))
             for i, r in enumerate(monthly_data) if _is_num(r.paid)]
        )

        series, legend_pairs = [], []
        if receivables:
            series.append(receivables)
            legend_pairs.append((ORALSIN_ACCENT_BLUE, "Previsto"))
        if paids:
            series.append(paids)
            legend_pairs.append((SUCCESS_GREEN, "Realizado"))

        # Nada digno de plotar
        if len(series) < 1:
            return None

        # ---------- desenho ----------
        drawing = Drawing(width=available_width, height=250)
        drawing.add(
            String(
                available_width / 2,
                230,
                "Evolução Mensal: Previsto vs. Realizado",
                textAnchor="middle",
                fontName=ROBOTO_MEDIUM,
                fontSize=12,
                fillColor=TEXT_COLOR_DARK,
            )
        )

        max_val = max(v for s in series for _, v in s)
        lp = LinePlot()
        lp.x, lp.y, lp.height, lp.width = 50, 40, 180, available_width - 70
        lp.data = series

        for idx, (color, _) in enumerate(legend_pairs):
            lp.lines[idx].strokeColor = color
            lp.lines[idx].strokeWidth = 2 if idx == 0 else 1.5

        lp.yValueAxis.valueMin = 0
        lp.yValueAxis.valueMax = max_val * 1.15
        lp.yValueAxis.valueStep = lp.yValueAxis.valueMax / 5
        lp.yValueAxis.labelTextFormat = (
            lambda v: self._fmt.format_currency(v).replace("R$ ", "")
        )
        lp.yValueAxis.labels.fontName = ROBOTO_REGULAR

        lp.xValueAxis = XCategoryAxis()
        lp.xValueAxis.categoryNames = [m.month for m in monthly_data]
        lp.xValueAxis.labels.boxAnchor = "ne"
        lp.xValueAxis.labels.angle = 30
        lp.xValueAxis.labels.dx, lp.xValueAxis.labels.dy = 8, -2
        lp.xValueAxis.labels.fontName = ROBOTO_REGULAR

        drawing.add(lp)

        legend = Legend()
        legend.alignment = "right"
        legend.x, legend.y = available_width - 100, 230
        legend.colorNamePairs = legend_pairs
        drawing.add(legend)

        return drawing