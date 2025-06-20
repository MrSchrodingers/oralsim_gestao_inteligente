"""
Main service for generating modern and complete PDF reports.
Enhanced system with a professional design and advanced features.
"""

import io
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, NextPageTemplate, PageBreak, Paragraph, Spacer, Table, TableStyle

from oralsin_core.core.application.dtos.dashboard_dto import DashboardDTO
from oralsin_core.core.application.services.utils.design_system import COLORS, get_advanced_styles
from oralsin_core.core.application.services.utils.formatters import (
    BrazilianFormatter,
    to_number,
)
from oralsin_core.core.application.services.utils.formatters import (
    formatter as default_formatter,
)
from oralsin_core.core.application.services.utils.kpi_cards import KPICardGenerator
from oralsin_core.core.application.services.utils.template import ModernDocumentTemplate
from plugins.django_interface.models import Clinic, ClinicData, ClinicPhone, User


class DashboardPDFService:
    """
    Main service for generating PDF reports with a modern design.
    
    Key Features:
    - Responsive and professional design
    - Organized multiple sections
    - Advanced charts and visualizations
    - Interactive KPI system
    - Complete Brazilian formatting
    """
    
    def __init__(self, formatter: BrazilianFormatter | None = None, logo_path: str | None = None):
        """
        Initializes the report service.
        
        Args:
            logo_path: Path to the logo file.
        """
        self.formatter = formatter or default_formatter
        self.logo_path = logo_path
        self.styles = get_advanced_styles()
        self.kpi_card_generator = KPICardGenerator()
        self.report_date = date.today()
    
    def build(
        self,
        user: User,
        clinic: Clinic,
        clinic_data: ClinicData,
        clinic_phones: ClinicPhone,
        dashboard: DashboardDTO,
        **kwargs: Any,
    ) -> bytes:
        """
        Generates the complete PDF report with all sections.
        
        Args:
            user: User data.
            clinic: Clinic information.
            clinic_data: Additional clinic data.
            clinic_phones: Contact phones.
            dashboard: Dashboard data.
            **kwargs: Additional parameters.
            
        Returns:
            bytes: Content of the generated PDF.
        """
        buffer = io.BytesIO()
        
        # Extract additional data
        collection_summary = kwargs.get("collection_summary")
        notification_summary = kwargs.get("notification_summary")
        last_notifications = kwargs.get("last_notifications")
        period_days = kwargs.get("periodDays", 30)
        
        # Configure document
        formatted_date = self.formatter.format_date(self.report_date, "curto")
        period_text = f"Últimos {period_days} dias"
        
        doc = ModernDocumentTemplate(
            buffer,
            title=f"Relatório Gerencial - {clinic.name}",
            author="Sistema Oralsin",
            subject=f"Dashboard Financeiro e Operacional - {formatted_date}",
            logo_path=self.logo_path,
            clinic_name=clinic.name,
            report_date=self.formatter.format_date(self.report_date, "numerico"),
            report_period=period_text,
            report_title="Relatório Gerencial",
            report_subtitle="Análise Financeira e Operacional",
            version="2.0"
        )
        
        # Available widths
        portrait_width = doc.get_available_width(is_landscape=False)
        landscape_width = doc.get_available_width(is_landscape=True)
        
        # Build the report content
        story: List[Flowable] = []
        
        # Cover page
        story.extend(self._build_cover_page(clinic, formatted_date, period_text))
        story.append(NextPageTemplate('PortraitPage'))
        story.append(PageBreak())
        
        # Executive summary
        story.extend(self._build_executive_summary(dashboard, collection_summary, portrait_width))
        
        # Main KPIs section
        story.extend(self._build_kpi_section(dashboard.stats, collection_summary, portrait_width))
        
        # Financial analysis
        story.extend(self._build_financial_analysis(dashboard, portrait_width))
        
        # Collection management
        story.extend(self._build_collection_management(collection_summary, portrait_width))
        
        # Patient communication
        story.extend(self._build_patient_communication(
            notification_summary, last_notifications, portrait_width
        ))
        
        # Detailed sections in landscape
        story.append(NextPageTemplate('LandscapePage'))
        story.append(PageBreak())
        story.extend(self._build_financial_details(dashboard, landscape_width))
        
        # Analysis and insights
        story.extend(self._build_insights_and_recommendations(dashboard, collection_summary, landscape_width))
        
        # Build the document
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _build_cover_page(self, clinic: Any, formatted_date: str, period: str) -> List[Flowable]:
        """Builds the report's cover page."""
        elements = [
            Spacer(1, 3 * cm),
            
            # Main title
            Paragraph("Relatório Gerencial", self.styles["ReportTitle"]),
            Paragraph("Completo", self.styles["ReportSubtitle"]),
            
            Spacer(1, 2 * cm),
            
            # Clinic information
            Paragraph(f"<b>Clínica:</b> {clinic.name}", self.styles["SectionSubtitle"]),
            Spacer(1, 0.8 * cm),
            
            # Period and date
            Paragraph(f"<b>Período de Análise:</b> {period}", self.styles["BodyTextHighlight"]),
            Paragraph(f"<b>Data de Geração:</b> {formatted_date}", self.styles["BodyTextHighlight"]),
            
            Spacer(1, 2.5 * cm),
            
            # Report description
            Paragraph("<b>Sobre Este Relatório</b>", self.styles["SubsectionTitle"]),
            Spacer(1, 0.5 * cm),
            
            Paragraph(
                "Este documento apresenta uma análise abrangente e detalhada dos principais "
                "indicadores de performance da clínica, incluindo métricas financeiras, "
                "operacionais e de relacionamento com pacientes. O relatório foi desenvolvido "
                "para fornecer insights estratégicos que auxiliem na tomada de decisões "
                "gerenciais e no crescimento sustentável do negócio.",
                self.styles["BodyText"]
            ),
            
            Spacer(1, 1.5 * cm),
            
            # Technical information
            Paragraph(
                f"<b>Sistema:</b> Oralsin - Gestão Inteligente para Clínicas Odontológicas<br/>"
                f"<b>Versão:</b> 2.0<br/>"
                f"<b>Gerado em:</b> {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
                self.styles["HelperText"]
            ),
        ]
        
        return elements
    
    def _build_executive_summary(self, dashboard: Any, collection_summary: Optional[Dict], 
                                     width: float) -> List[Flowable]:
        """Builds the executive summary with key insights."""
        elements = [
            Paragraph("Sumário Executivo", self.styles["SectionTitle"]),
            Spacer(1, 0.5 * cm)
        ]
        
        # Main highlights
        stats = dashboard.stats
        
        # Calculate important metrics
        collection_rate = to_number(getattr(stats, 'collectionRate', 0))
        total_receivables = to_number(getattr(stats, 'totalReceivables', 0))
        received_in_period = to_number(getattr(stats, 'paidThisMonth', 0))
        overdue_amount = to_number(getattr(stats, 'overduePayments', 0))
        
        # General clinic status
        if collection_rate >= 80:
            financial_status = "Excelente"
            status_color = COLORS.SUCCESS
        elif collection_rate >= 60:
            financial_status = "Bom"
            status_color = COLORS.INFO
        elif collection_rate >= 40:
            financial_status = "Regular"
            status_color = COLORS.WARNING
        else:
            financial_status = "Crítico"
            status_color = COLORS.ERROR
        
        # Summary text
        summary_text = f"""
        <b>Status Financeiro Geral:</b> <font color="{status_color}"><b>{financial_status}</b></font><br/><br/>
        
        <b>Principais Indicadores:</b><br/>
        • <b>Taxa de Cobrança:</b> {self.formatter.format_percentage(collection_rate/100)}<br/>
        • <b>Total a Receber:</b> {self.formatter.format_currency(total_receivables)}<br/>
        • <b>Recebido no Período:</b> {self.formatter.format_currency(received_in_period)}<br/>
        • <b>Valores em Atraso:</b> {self.formatter.format_currency(overdue_amount)}<br/><br/>
        
        <b>Observações Importantes:</b><br/>
        """
        
        # Add observations based on data
        observations = []
        
        if collection_rate < 50:
            observations.append("• <font color='#DC2626'>Atenção necessária na gestão de cobrança</font>")
        
        if total_receivables > 0 and overdue_amount > total_receivables * 0.3:
            observations.append("• <font color='#DC2626'>Alto volume de pagamentos em atraso</font>")
        
        if collection_summary and collection_summary.get('total_cases', 0) > 0:
            collection_cases = collection_summary.get('total_cases', 0)
            observations.append(
                f"• {self.formatter.pluralize(collection_cases, 'caso de cobrança ativo', 'casos de cobrança ativos')}"
            )
        
        if not observations:
            observations.append("• <font color='#059669'>Situação financeira dentro dos parâmetros esperados</font>")
        
        summary_text += "<br/>".join(observations)
        
        elements.append(Paragraph(summary_text, self.styles["BodyText"]))
        elements.append(Spacer(1, 1 * cm))
        
        return elements
    
    def _build_kpi_section(self, stats: Any, collection_summary: Optional[Dict], 
                               width: float) -> List[Flowable]:
        """Builds the main KPI section."""
        elements = [
            Paragraph("Indicadores de Performance (KPIs)", self.styles["SectionTitle"]),
            Spacer(1, 0.5 * cm)
        ]
        
        # Prepare KPI data
        main_kpis = [
            (
                "Total a Receber",
                self.formatter.format_currency(
                    getattr(stats, 'totalReceivables', 0), short_format=True
                ),
                COLORS.PRIMARY_BLUE
            ),
            (
                "Recebido no Período",
                self.formatter.format_currency(
                    getattr(stats, 'paidThisMonth', 0), short_format=True
                ),
                COLORS.SUCCESS
            ),
            (
                "Em Atraso",
                self.formatter.format_currency(
                    getattr(stats, 'overduePayments', 0), short_format=True
                ),
                COLORS.ERROR
            ),
            (
                "Taxa de Cobrança",
                self.formatter.format_percentage(
                    getattr(stats, 'collectionRate', 0) / 100
                ),
                COLORS.INFO
            ),
            (
                "Casos de Cobrança",
                str(collection_summary.get('total_cases', 0) if collection_summary else 0),
                COLORS.WARNING
            ),
            (
                "Dias Médios de Atraso",
                f"{getattr(stats, 'averageDaysOverdue', 0):.0f} dias",
                COLORS.ERROR
            ),
        ]
        
        # Create KPI grid
        kpi_grid = self.kpi_card_generator.create_kpi_grid(main_kpis, width, columns=3)
        elements.append(kpi_grid)
        elements.append(Spacer(1, 1 * cm))
        
        return elements
    
    def _build_financial_analysis(self, dashboard: Any, width: float) -> List[Flowable]:
        """Builds the financial analysis section with charts."""
        elements = [
            Paragraph("Análise Financeira", self.styles["SectionTitle"]),
            Spacer(1, 0.5 * cm)
        ]
        
        # Check for monthly data
        if hasattr(dashboard, 'monthlyReceivables') and dashboard.monthlyReceivables:
            elements.append(
                Paragraph("Evolução Mensal de Recebimentos", self.styles["SectionSubtitle"])
            )
            
            # Create chart
            chart = self._create_monthly_evolution_chart(dashboard.monthlyReceivables, width)
            if chart:
                elements.append(chart)
                elements.append(Spacer(1, 0.8 * cm))
            
            # Textual analysis of the data
            elements.extend(self._create_financial_textual_analysis(dashboard.monthlyReceivables))
        else:
            elements.append(
                Paragraph(
                    "Dados de evolução mensal não disponíveis para o período selecionado.",
                    self.styles["HelperText"]
                )
            )
        
        elements.append(Spacer(1, 1 * cm))
        return elements
    
    def _build_collection_management(self, summary: Optional[Dict], width: float) -> List[Flowable]:
        """Builds the collection management section."""
        elements = [
            Paragraph("Gestão de Cobrança", self.styles["SectionTitle"]),
            Spacer(1, 0.5 * cm)
        ]
        
        if not summary or not summary.get('by_status'):
            elements.append(
                Paragraph(
                    "Dados de cobrança não disponíveis para o período selecionado.",
                    self.styles["HelperText"]
                )
            )
            return elements
        
        # Collection status table
        elements.append(Paragraph("Distribuição por Status", self.styles["SectionSubtitle"]))
        
        # Table header
        header = [
            Paragraph("<b>Status da Cobrança</b>", self.styles["TableHeader"]),
            Paragraph("<b>Quantidade</b>", self.styles["TableHeader"]),
            Paragraph("<b>Valor Total</b>", self.styles["TableHeader"]),
            Paragraph("<b>Percentual</b>", self.styles["TableHeader"]),
            Paragraph("<b>Valor Médio</b>", self.styles["TableHeader"]),
        ]
        
        # Table data
        data_rows = [header]
        grand_total_value = sum(item.get('total_value', 0) for item in summary.get('by_status', []))
        
        for item in summary.get('by_status', []):
            status_name = item.get('status', 'N/A').replace('_', ' ').title()
            quantity = item.get('count', 0)
            total_value = item.get('total_value', 0)
            percentage = (total_value / grand_total_value * 100) if grand_total_value > 0 else 0
            average_value = total_value / quantity if quantity > 0 else 0
            
            # Icons for different statuses
            status_icons = {
                'Pending': '⏳',
                'In Progress': '🔄',
                'Completed': '✅',
                'Failed': '❌',
                'Cancelled': '🚫'
            }
            icon = status_icons.get(status_name, '📋')
            
            data_rows.append([
                Paragraph(f"{icon} {status_name}", self.styles["TableCell"]),
                Paragraph(self.formatter.format_number(quantity), self.styles["TableCellCenter"]),
                Paragraph(self.formatter.format_currency(total_value), self.styles["TableCellRight"]),
                Paragraph(self.formatter.format_percentage(percentage/100), self.styles["TableCellCenter"]),
                Paragraph(self.formatter.format_currency(average_value), self.styles["TableCellRight"]),
            ])
        
        # Total row
        total_quantity = sum(item.get('count', 0) for item in summary.get('by_status', []))
        total_avg_value = grand_total_value / total_quantity if total_quantity > 0 else 0

        data_rows.append([
            Paragraph("<b>TOTAL GERAL</b>", self.styles["TableCellHighlight"]),
            Paragraph(f"<b>{self.formatter.format_number(total_quantity)}</b>", self.styles["TableCellCenter"]),
            Paragraph(f"<b>{self.formatter.format_currency(grand_total_value)}</b>", self.styles["TableCellRight"]),
            Paragraph("<b>100%</b>", self.styles["TableCellCenter"]),
            Paragraph(f"<b>{self.formatter.format_currency(total_avg_value)}</b>", self.styles["TableCellRight"]),
        ])
        
        # Column widths
        column_widths = [
            width * 0.3,   # Status
            width * 0.15,  # Quantity
            width * 0.2,   # Total Value
            width * 0.15,  # Percentage
            width * 0.2    # Average Value
        ]
        
        table = self._create_styled_table(data_rows, column_widths)
        elements.append(table)
        elements.append(Spacer(1, 1 * cm))
        
        return elements
    
    def _build_patient_communication(self, notification_summary: Optional[Dict], 
                                         last_notifications: Any, width: float) -> List[Flowable]:
        """Builds the patient communication section."""
        elements = [
            Paragraph("Comunicação com Pacientes", self.styles["SectionTitle"]),
            Spacer(1, 0.5 * cm)
        ]
        
        if not notification_summary:
            elements.append(
                Paragraph(
                    "Dados de comunicação não disponíveis para o período selecionado.",
                    self.styles["HelperText"]
                )
            )
            return elements
        
        # Calculate total notifications (only numeric values)
        total_notifications = sum(
            v for v in notification_summary.values() 
            if isinstance(v, (int, float))
        )
        
        if total_notifications > 0:
            elements.append(Paragraph("Resumo de Comunicações", self.styles["SectionSubtitle"]))
            
            # Summary table by status
            notification_header = [
                Paragraph("<b>Status</b>", self.styles["TableHeader"]),
                Paragraph("<b>Quantidade</b>", self.styles["TableHeader"]),
                Paragraph("<b>Percentual</b>", self.styles["TableHeader"]),
                Paragraph("<b>Taxa de Sucesso</b>", self.styles["TableHeader"]),
            ]
            
            notification_rows = [notification_header]
            
            # Map status to icons and colors
            status_config = {
                'SENT': {'icon': '✅', 'name': 'Enviadas', 'color': COLORS.SUCCESS},
                'DELIVERED': {'icon': '📨', 'name': 'Entregues', 'color': COLORS.INFO},
                'READ': {'icon': '👁️', 'name': 'Lidas', 'color': COLORS.PRIMARY_BLUE},
                'ERROR': {'icon': '❌', 'name': 'Com Erro', 'color': COLORS.ERROR},
                'PENDING': {'icon': '⏳', 'name': 'Pendentes', 'color': COLORS.WARNING},
            }
            
            for status, quantity in notification_summary.items():
                if not isinstance(quantity, (int, float)):
                    continue
                
                config = status_config.get(status, {'icon': '📋', 'name': status.title(), 'color': COLORS.PRIMARY_TEXT})
                percentage = (quantity / total_notifications * 100)
                
                # Calculate success rate (simplified)
                if status in ['SENT', 'DELIVERED', 'READ']:
                    success_rate = "Alta"
                    rate_color = COLORS.SUCCESS
                elif status == 'ERROR':
                    success_rate = "Baixa"
                    rate_color = COLORS.ERROR
                else:
                    success_rate = "Média"
                    rate_color = COLORS.WARNING
                
                notification_rows.append([
                    Paragraph(f"{config['icon']} {config['name']}", self.styles["TableCell"]),
                    Paragraph(self.formatter.format_number(quantity), self.styles["TableCellCenter"]),
                    Paragraph(self.formatter.format_percentage(percentage/100), self.styles["TableCellCenter"]),
                    Paragraph(f"<font color='{rate_color}'>{success_rate}</font>", self.styles["TableCellCenter"]),
                ])
            
            # Total row
            notification_rows.append([
                Paragraph("<b>TOTAL</b>", self.styles["TableCellHighlight"]),
                Paragraph(f"<b>{self.formatter.format_number(total_notifications)}</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>100%</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>-</b>", self.styles["TableCellCenter"]),
            ])
            
            notification_widths = [width * 0.3, width * 0.25, width * 0.25, width * 0.2]
            notification_table = self._create_styled_table(notification_rows, notification_widths)
            elements.append(notification_table)
            elements.append(Spacer(1, 0.8 * cm))
        
        # Recent communications
        if last_notifications:
            elements.append(Paragraph("Comunicações Recentes", self.styles["SectionSubtitle"]))
            
            recent_header = [
                Paragraph("<b>Paciente</b>", self.styles["TableHeader"]),
                Paragraph("<b>Data/Hora</b>", self.styles["TableHeader"]),
                Paragraph("<b>Canal</b>", self.styles["TableHeader"]),
                Paragraph("<b>Status</b>", self.styles["TableHeader"]),
                Paragraph("<b>Tipo</b>", self.styles["TableHeader"]),
            ]
            
            recent_rows = [recent_header]
            
            # Limit to the 8 most recent notifications
            for notification in last_notifications[:8]:
                status_icon = "✅" if getattr(notification, 'success', False) else "❌"
                status_text = "Sucesso" if getattr(notification, 'success', False) else "Falha"
                status_color = COLORS.SUCCESS if getattr(notification, 'success', False) else COLORS.ERROR
                
                # Icons for different channels
                channel = getattr(notification, 'contact_type', 'N/A').upper()
                channel_icons = {
                    'EMAIL': '📧',
                    'SMS': '📱',
                    'WHATSAPP': '💬',
                    'PHONE': '📞'
                }
                channel_icon = channel_icons.get(channel, '📋')
                
                sent_at_date = getattr(notification, 'sent_at', None)
                formatted_date = sent_at_date.strftime("%d/%m %H:%M") if sent_at_date else "N/A"
                
                recent_rows.append([
                    Paragraph(getattr(notification, "patient_name", "N/A"), self.styles["TableCell"]),
                    Paragraph(formatted_date, self.styles["TableCellCenter"]),
                    Paragraph(f"{channel_icon} {channel.title()}", self.styles["TableCellCenter"]),
                    Paragraph(f"<font color='{status_color}'>{status_icon} {status_text}</font>", self.styles["TableCellCenter"]),
                    Paragraph(getattr(notification, 'message_type', 'N/A').title(), self.styles["TableCellCenter"]),
                ])
            
            recent_widths = [width * 0.3, width * 0.15, width * 0.15, width * 0.2, width * 0.2]
            recent_table = self._create_styled_table(recent_rows, recent_widths)
            elements.append(recent_table)
        
        elements.append(Spacer(1, 1 * cm))
        return elements
    
    def _build_financial_details(self, dashboard: Any, width: float) -> List[Flowable]:
        """Builds the detailed sections in landscape mode."""
        elements = [
            Paragraph("Detalhamento Financeiro", self.styles["SectionTitle"]),
            Spacer(1, 0.5 * cm)
        ]
        
        # Payments received
        elements.append(Paragraph("Pagamentos Recebidos no Período", self.styles["SectionSubtitle"]))
        
        if hasattr(dashboard, 'recentPayments') and dashboard.recentPayments:
            paid_header = [
                Paragraph("<b>Paciente</b>", self.styles["TableHeader"]),
                Paragraph("<b>Valor</b>", self.styles["TableHeader"]),
                Paragraph("<b>Data Pagamento</b>", self.styles["TableHeader"]),
                Paragraph("<b>Método</b>", self.styles["TableHeader"]),
                Paragraph("<b>Status</b>", self.styles["TableHeader"]),
                Paragraph("<b>Observações</b>", self.styles["TableHeader"]),
            ]
            
            paid_rows = [paid_header]
            total_received = 0
            
            for payment in dashboard.recentPayments[:15]:  # Limit to 15 records
                value = getattr(payment, 'amount', 0)
                if isinstance(value, str):
                    # Remove formatting if necessary
                    numeric_value = float(value.replace('R$', '').replace('.', '').replace(',', '.').strip())
                else:
                    numeric_value = float(value) if value else 0
                
                total_received += numeric_value
                
                paid_rows.append([
                    Paragraph(getattr(payment, 'patient', 'N/A'), self.styles["TableCell"]),
                    Paragraph(
                        self.formatter.format_currency(numeric_value),
                        self.styles["TableCellRight"],
                    ),
                    Paragraph(getattr(payment, 'date', 'N/A'), self.styles["TableCellCenter"]),
                    Paragraph(getattr(payment, 'method', 'N/A'), self.styles["TableCellCenter"]),
                    Paragraph(f"✅ {getattr(payment, 'status', 'Confirmado')}", self.styles["TableCellCenter"]),
                    Paragraph(getattr(payment, 'notes', '-'), self.styles["TableCell"]),
                ])
            
            # Total row
            paid_rows.append([
                Paragraph("<b>TOTAL RECEBIDO</b>", self.styles["TableCellHighlight"]),
                Paragraph(
                    f"<b>{self.formatter.format_currency(total_received)}</b>",
                    self.styles["TableCellRight"],
                ),
                Paragraph("<b>-</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>-</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>-</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>-</b>", self.styles["TableCell"]),
            ])
            
            paid_widths = [width * 0.25, width * 0.15, width * 0.12, width * 0.12, width * 0.12, width * 0.24]
            paid_table = self._create_styled_table(paid_rows, paid_widths)
            elements.append(paid_table)
        else:
            elements.append(
                Paragraph("Nenhum pagamento registrado no período.", self.styles["HelperText"])
            )
        
        elements.append(Spacer(1, 1 * cm))
        
        # Pending payments
        elements.append(Paragraph("Pagamentos Pendentes", self.styles["SectionSubtitle"]))
        
        if hasattr(dashboard, 'pendingPayments') and dashboard.pendingPayments:
            pending_header = [
                Paragraph("<b>Paciente</b>", self.styles["TableHeader"]),
                Paragraph("<b>Valor</b>", self.styles["TableHeader"]),
                Paragraph("<b>Vencimento</b>", self.styles["TableHeader"]),
                Paragraph("<b>Dias Atraso</b>", self.styles["TableHeader"]),
                Paragraph("<b>Status</b>", self.styles["TableHeader"]),
                Paragraph("<b>Ação Sugerida</b>", self.styles["TableHeader"]),
            ]
            
            pending_rows = [pending_header]
            total_pending = 0
            
            for payment in dashboard.pendingPayments[:20]:  # Limit to 20 records
                value = getattr(payment, 'amount', 0)
                if isinstance(value, str):
                    numeric_value = float(value.replace('R$', '').replace('.', '').replace(',', '.').strip())
                else:
                    numeric_value = float(value) if value else 0
                
                total_pending += numeric_value
                
                status = getattr(payment, 'status', '').lower()
                is_overdue = 'vencido' in status or 'overdue' in status
                
                # Determine color and action based on status
                if is_overdue:
                    value_color = COLORS.ERROR
                    status_icon = "🔴"
                    suggested_action = "Cobrança Urgente"
                else:
                    value_color = COLORS.WARNING
                    status_icon = "🟡"
                    suggested_action = "Lembrete"
                
                # Calculate overdue days (simulated)
                days_overdue = "N/A"
                if is_overdue:
                    # Here you could calculate the actual overdue days
                    days_overdue = "15+"  # Simulated value
                
                pending_rows.append([
                    Paragraph(getattr(payment, 'patient', 'N/A'), self.styles["TableCell"]),
                    Paragraph(
                        f"<font color='{value_color}'>{self.formatter.format_currency(numeric_value)}</font>",
                        self.styles["TableCellRight"],
                    ),
                    Paragraph(getattr(payment, 'date', 'N/A'), self.styles["TableCellCenter"]),
                    Paragraph(days_overdue, self.styles["TableCellCenter"]),
                    Paragraph(f"{status_icon} {getattr(payment, 'status', 'N/A')}", self.styles["TableCellCenter"]),
                    Paragraph(suggested_action, self.styles["TableCell"]),
                ])
            
            # Total row
            pending_rows.append([
                Paragraph("<b>TOTAL PENDENTE</b>", self.styles["TableCellHighlight"]),
                Paragraph(
                    f"<b>{self.formatter.format_currency(total_pending)}</b>",
                    self.styles["TableCellRight"],
                ),
                Paragraph("<b>-</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>-</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>-</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>-</b>", self.styles["TableCell"]),
            ])
            
            pending_widths = [width * 0.25, width * 0.15, width * 0.12, width * 0.12, width * 0.16, width * 0.2]
            pending_table = self._create_styled_table(pending_rows, pending_widths)
            elements.append(pending_table)
        else:
            elements.append(
                Paragraph("Nenhum pagamento pendente encontrado.", self.styles["HelperText"])
            )
        
        elements.append(Spacer(1, 1 * cm))
        return elements
    
    def _build_insights_and_recommendations(self, dashboard: Any, collection_summary: Optional[Dict], 
                                                width: float) -> List[Flowable]:
        """Builds the insights and recommendations section."""
        elements = [
            Paragraph("Insights e Recomendações", self.styles["SectionTitle"]),
            Spacer(1, 0.5 * cm)
        ]
        
        # Automatic data analysis
        stats = dashboard.stats
        collection_rate = to_number(getattr(stats, 'collectionRate', 0))
        overdue_amount = to_number(getattr(stats, 'overduePayments', 0))
        total_receivables = to_number(getattr(stats, 'totalReceivables', 0))
        
        insights = []
        recommendations = []
        
        # Generate insights based on data
        if collection_rate < 50:
            insights.append("📉 Taxa de cobrança abaixo do ideal (< 50%)")
            recommendations.append("Implementar processo de cobrança mais eficiente")
            recommendations.append("Revisar políticas de pagamento e prazos")
        elif collection_rate > 80:
            insights.append("📈 Excelente taxa de cobrança (> 80%)")
            recommendations.append("Manter as práticas atuais de cobrança")
        
        if total_receivables > 0 and (overdue_amount / total_receivables) > 0.3:
            insights.append("⚠️ Alto percentual de valores em atraso (> 30%)")
            recommendations.append("Priorizar cobrança de valores vencidos")
            recommendations.append("Considerar parcelamento para casos críticos")
        
        if collection_summary and collection_summary.get('total_cases', 0) > 50:
            insights.append("📊 Alto volume de casos de cobrança ativa")
            recommendations.append("Avaliar automação do processo de cobrança")
            recommendations.append("Considerar terceirização para casos complexos")
        
        # Add default insights if none are specific
        if not insights:
            insights.append("✅ Indicadores financeiros dentro da normalidade")
            recommendations.append("Continuar monitoramento regular dos KPIs")
            recommendations.append("Manter foco na qualidade do atendimento")
        
        # Insights section
        elements.append(Paragraph("Principais Insights", self.styles["SectionSubtitle"]))
        for insight in insights:
            elements.append(Paragraph(f"• {insight}", self.styles["BodyText"]))
        
        elements.append(Spacer(1, 0.8 * cm))
        
        # Recommendations section
        elements.append(Paragraph("Recomendações Estratégicas", self.styles["SectionSubtitle"]))
        for i, recommendation in enumerate(recommendations, 1):
            elements.append(Paragraph(f"{i}. {recommendation}", self.styles["BodyText"]))
        
        elements.append(Spacer(1, 1 * cm))
        
        # Suggested next steps
        elements.append(Paragraph("Próximos Passos Sugeridos", self.styles["SectionSubtitle"]))
        
        next_steps = [
            "Revisar este relatório mensalmente para acompanhar tendências",
            "Definir metas específicas para os KPIs identificados como críticos",
            "Implementar alertas automáticos para valores em atraso",
            "Treinar equipe em técnicas de cobrança eficiente",
            "Avaliar ferramentas de automação para otimizar processos"
        ]
        
        for i, step in enumerate(next_steps, 1):
            elements.append(Paragraph(f"{i}. {step}", self.styles["BodyText"]))
        
        return elements
    
    # Helper methods
    
    def _create_styled_table(self, data: List[List[Any]], column_widths: List[float]) -> Table:
        """Creates a table with a modern and professional style."""
        table = Table(data, colWidths=column_widths, repeatRows=1)
        
        style_commands = [
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), COLORS.PRIMARY_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), COLORS.WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Roboto-Bold'),
            
            # Table body
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.8, COLORS.MEDIUM_GRAY),
            ('BOX', (0, 0), (-1, -1), 1.2, COLORS.DARK_GRAY),
            
            # Padding
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]
        
        # Add alternating row colors
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_commands.append(('BACKGROUND', (0, i), (-1, i), COLORS.EXTRA_LIGHT_GRAY))
        
        # Highlight total row if it exists
        if len(data) > 1 and any('TOTAL' in str(cell) for cell in data[-1]):
            style_commands.extend([
                ('BACKGROUND', (0, len(data)-1), (-1, len(data)-1), COLORS.LIGHT_BLUE),
                ('FONTNAME', (0, len(data)-1), (-1, len(data)-1), 'Roboto-Bold'),
            ])
        
        table.setStyle(TableStyle(style_commands))
        return table
    
    def _create_monthly_evolution_chart(self, monthly_data: Any, width: float) -> Optional[Drawing]:
        """Creates a monthly evolution chart for receivables."""
        if not monthly_data:
            return None
        
        try:
            # Map months to Portuguese
            pt_months_map = {
                'Jan': 'Jan', 'Feb': 'Fev', 'Mar': 'Mar', 'Apr': 'Abr',
                'May': 'Mai', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
                'Sep': 'Set', 'Oct': 'Out', 'Nov': 'Nov', 'Dec': 'Dez'
            }
            
            def format_month(iso_month: str) -> str:
                try:
                    date_obj = datetime.strptime(iso_month, '%Y-%m')
                    en_month = date_obj.strftime('%b')
                    return pt_months_map.get(en_month, en_month)
                except:
                    return iso_month[:3]
            
            # Prepare data
            labels = [format_month(m.month) for m in monthly_data]
            forecasted_values = [float(getattr(r, 'receivable', 0)) for r in monthly_data]
            received_values = [float(getattr(r, 'paid', 0)) for r in monthly_data]
            
            # Check for valid data
            if not any(forecasted_values) and not any(received_values):
                return None
            
            # Create the drawing
            drawing = Drawing(width=width, height=10*cm)
            
            # Configure the chart
            chart = VerticalBarChart()
            chart.x = 60
            chart.y = 60
            chart.height = 7*cm
            chart.width = width - 120
            chart.data = [received_values, forecasted_values]
            chart.groupSpacing = 15
            chart.barSpacing = 3
            
            # Bar colors
            chart.bars[0].fillColor = COLORS.SUCCESS
            chart.bars[1].fillColor = COLORS.SECONDARY_BLUE
            
            # Y-axis configuration
            max_value = max(max(forecasted_values), max(received_values))
            chart.valueAxis.valueMin = 0
            chart.valueAxis.valueMax = max_value * 1.15
            chart.valueAxis.labelTextFormat = lambda v: self.formatter.format_currency(v, short_format=True)
            chart.valueAxis.labels.fontName = 'Roboto-Regular'
            chart.valueAxis.strokeColor = COLORS.DARK_GRAY
            
            # X-axis configuration
            chart.categoryAxis.categoryNames = labels
            chart.categoryAxis.labels.fontName = 'Roboto-Regular'
            chart.categoryAxis.strokeColor = COLORS.DARK_GRAY
            
            drawing.add(chart)
            
            # Add legend
            legend = Legend()
            legend.alignment = 'right'
            legend.x = width - 60
            legend.y = 9*cm
            legend.colorNamePairs = [
                (COLORS.SUCCESS, 'Valores Recebidos'),
                (COLORS.SECONDARY_BLUE, 'Valores Previstos')
            ]
            legend.fontName = 'Roboto-Regular'
            legend.fontSize = 10
            
            drawing.add(legend)
            
            return drawing
            
        except Exception as e:
            print(f"Error creating chart: {e}")
            return None
    
    def _create_financial_textual_analysis(self, monthly_data: Any) -> List[Flowable]:
        """Creates a textual analysis of the financial data."""
        elements = []
        
        try:
            if not monthly_data or len(monthly_data) < 2:
                return elements
            
            # Calculate metrics
            received_values = [float(getattr(r, 'paid', 0)) for r in monthly_data]
            
            # Trend of receipts
            if len(received_values) >= 2 and received_values[-2] > 0:
                variation = ((received_values[-1] - received_values[-2]) / received_values[-2] * 100)
                
                if variation > 10:
                    trend = f"📈 <font color='{COLORS.SUCCESS}'>Crescimento significativo</font> de {self.formatter.format_percentage(variation/100)} no último mês"
                elif variation > 0:
                    trend = f"📊 <font color='{COLORS.INFO}'>Crescimento moderado</font> de {self.formatter.format_percentage(variation/100)} no último mês"
                elif variation < -10:
                    trend = f"📉 <font color='{COLORS.ERROR}'>Queda significativa</font> de {self.formatter.format_percentage(abs(variation)/100)} no último mês"
                else:
                    trend = f"➡️ <font color='{COLORS.SECONDARY_TEXT}'>Estabilidade</font> nos recebimentos (variação de {self.formatter.format_percentage(abs(variation)/100)})"
                
                elements.append(Paragraph(f"<b>Tendência:</b> {trend}", self.styles["BodyText"]))
            
            # Average collection efficiency
            efficiencies = []
            for i, data in enumerate(monthly_data):
                forecasted = float(getattr(data, 'receivable', 0))
                received = float(getattr(data, 'paid', 0))
                if forecasted > 0:
                    efficiencies.append(received / forecasted * 100)
            
            if efficiencies:
                average_efficiency = sum(efficiencies) / len(efficiencies)
                elements.append(
                    Paragraph(
                        f"<b>Eficiência Média de Cobrança:</b> {self.formatter.format_percentage(average_efficiency/100)}",
                        self.styles["BodyText"]
                    )
                )
            
            elements.append(Spacer(1, 0.5 * cm))
            
        except Exception as e:
            print(f"Error in textual analysis: {e}")
        
        return elements