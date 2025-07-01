import base64
from typing import Any

from notification_billing.adapters.notifiers.base import BaseNotifier
from notification_billing.adapters.notifiers.email.brevo import BrevoEmail

# from notification_billing.adapters.notifiers.email.sendgrid import SendGridEmail
from notification_billing.core.application.services.letter_service import CordialLetterService

FIXED_RECIPIENT_EMAIL = "mrschrodingers@gmail.com"

class LetterNotifier(BaseNotifier):
    """
    Um notificador que gera uma carta a partir de um template DOCX e a envia
    como um anexo de e-mail para um destinatário fixo.
    """

    def __init__(self, template_path: str, email_notifier: BrevoEmail):
        super().__init__("internal", "letter")
        self.letter_service = CordialLetterService(template_path)
        self.email_notifier = email_notifier

    def send(self, context: dict[str, Any]) -> None:
        """
        Gera a carta e a envia por e-mail.

        Args:
            context: Dicionário com os dados para preencher o template da carta.
        """
        # 1. Gera a carta em memória
        letter_stream = self.letter_service.generate_letter(context)
        letter_bytes = letter_stream.read()

        # 2. Prepara o anexo para a API do SendGrid
        encoded_file = base64.b64encode(letter_bytes).decode()
        
        patient_name = context.get("patient_name", "paciente")
        contract_id = context.get("contract_oralsin_id", "s/n")
        
        attachment = {
            "content": encoded_file,
            "name": f"Notificacao_Amigavel_{patient_name.replace(' ', '_')}_Contrato_{contract_id}.docx",
            "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "disposition": "attachment"
        }

        # 3. Define o conteúdo do e-mail
        subject = f"Nova Carta de Cobrança Gerada para: {patient_name}"
        html_content = f"""
            <p>Olá,</p>
            <p>Uma nova carta de cobrança amigável foi gerada para o paciente <strong>{patient_name}</strong> (Contrato: {contract_id}).</p>
            <p>O documento está em anexo e pronto para impressão e envio.</p>
            <p>Este é um e-mail automático. Por favor, não responda.</p>
        """

        # 4. Envia o e-mail com o anexo
        self.email_notifier.send(
            recipients=[FIXED_RECIPIENT_EMAIL],
            subject=subject,
            html=html_content,
            attachments=[attachment]
        )