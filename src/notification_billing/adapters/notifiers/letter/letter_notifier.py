import base64
from typing import Any

from notification_billing.adapters.notifiers.base import BaseNotifier
from notification_billing.adapters.notifiers.email.microsoft_graph import MicrosoftGraphEmail
from notification_billing.core.application.services.letter_service import CordialLetterService

FIXED_RECIPIENT_EMAIL = "supervisoradm@amaralvasconcellos.com.br "

class LetterNotifier(BaseNotifier):
    def __init__(self, template_path: str, email_notifier: MicrosoftGraphEmail):
        super().__init__("internal", "letter")
        self.letter_service = CordialLetterService(template_path)
        self.email_notifier = email_notifier

    def send(self, context: dict[str, Any]) -> None:
        # 1. Gera a carta em memória (aceita override opcional)
        override_tpl = context.get("_template_path")
        letter_stream = self.letter_service.generate_letter(context, template_path=override_tpl)
        letter_bytes = letter_stream.read()

        encoded_file = base64.b64encode(letter_bytes).decode()
        patient_name = context.get("patient_name", "paciente")
        contract_id = context.get("contract_oralsin_id", "s/n")

        attachment = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": f"Notificacao_Amigavel_{patient_name.replace(' ', '_')}_Contrato_{contract_id}.docx",
            "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "contentBytes": encoded_file,
        }

        subject = f"Nova Carta de Cobrança Gerada para: {patient_name}"
        html_content = f"""
            <p>Olá,</p>
            <p>Uma nova carta de cobrança amigável foi gerada para o paciente <strong>{patient_name}</strong> (Contrato: {contract_id}).</p>
            <p>O documento está em anexo e pronto para impressão e envio.</p>
            <p>Este é um e-mail automático. Por favor, não responda.</p>
        """

        self.email_notifier.send(
            recipients=[FIXED_RECIPIENT_EMAIL],
            subject=subject,
            html=html_content,
            attachments=[attachment]
        )