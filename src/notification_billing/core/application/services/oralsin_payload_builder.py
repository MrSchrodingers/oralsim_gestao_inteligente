from typing import Literal

from django.utils import timezone
from oralsin_core.core.application.dtos.oralsin_dtos import OralsinContatoHistoricoEnvioDTO

from plugins.django_interface.models import Clinic, ContactHistory, Contract, Installment, Message, Patient

ContactType = Literal["phonecall", "sms", "whatsapp", "email", "letter"]
_CONTACT_TYPE_DESC: dict[ContactType, str] = {
    "phonecall": "Ligação telefônica",
    "sms": "SMS",
    "whatsapp": "WhatsApp",
    "email": "E-mail",
    "letter": "Carta Amigável"
}

def build_oralsin_payload(history: ContactHistory) -> OralsinContatoHistoricoEnvioDTO:
    patient = Patient.objects.get(id=history.patient_id)
    clinic  = Clinic.objects.get(id=history.clinic_id)
    installment = Installment.objects.get(contract_id=history.contract_id, is_current=True)
    contract = (
        Contract.objects.filter(id=history.contract_id).first()
        if history.contract_id else None
    )
    
    

    message_desc = "Sem mensagem registrada"
    if history.message_id:
        msg = Message.objects.filter(id=history.message_id).first()
        if msg and getattr(msg, "content", None):
            message_desc = msg.content

    return OralsinContatoHistoricoEnvioDTO(
        idClinica=clinic.oralsin_clinic_id,
        idPaciente=patient.oralsin_patient_id,
        idContrato=getattr(contract, "oralsin_contract_id", None),
        dataHoraInseriu=history.sent_at or timezone.now(),
        observacao=history.observation or "",
        contatoTipo=_CONTACT_TYPE_DESC.get(history.contact_type, history.contact_type),
        descricao=message_desc,
        
        idStatusContato=1,  # Fixo como 1 para "contato bem sucedido"
        dataHoraRetornar=history.sent_at or timezone.now(), 
        versaoContrato=getattr(contract, "contract_version", None),
        idContratoParcela=getattr(installment, "oralsin_installment_id", None) 
    )
