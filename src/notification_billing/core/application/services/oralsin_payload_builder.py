from typing import Literal

from django.utils import timezone
from oralsin_core.core.application.dtos.oralsin_dtos import OralsinContatoHistoricoEnvioDTO

from plugins.django_interface.models import ContactHistory

ContactType = Literal["phonecall", "sms", "whatsapp", "email", "letter"]
_CONTACT_TYPE_DESC: dict[ContactType, str] = {
"phonecall": "Ligação telefônica",
"sms": "SMS",
"whatsapp": "WhatsApp",
"email": "E-mail",
"letter": "Carta Amigável"
}

def build_oralsin_payload(history: ContactHistory) -> OralsinContatoHistoricoEnvioDTO:
    """
    Constrói o payload para a API Oralsin a partir de um objeto ContactHistory.
    
    IMPORTANTE: Para performance ideal, o objeto 'history' deve ser buscado
    com .select_related('patient', 'clinic', 'contract', 'message', 'schedule__installment').
    """
    
    # --- 1. Acesse os dados pré-carregados para evitar novas consultas ---
    # Estes acessos agora são praticamente instantâneos e não tocam no banco.
    patient = history.patient
    clinic = history.clinic
    contract = history.contract
    schedule = history.schedule
    
    # --- 2. Extraia informações dos objetos relacionados de forma segura ---
    message_desc = history.message.content if history.message else "Sem mensagem registrada"
    
    # Acessa a parcela através do agendamento (schedule)
    installment = schedule.installment if schedule else None
    
    # --- 3. Construa o DTO com os dados extraídos ---
    return OralsinContatoHistoricoEnvioDTO(
        # idClinica=clinic.oralsin_clinic_id,
        idPaciente=patient.oralsin_patient_id,
        idContrato=getattr(contract, "oralsin_contract_id", None),
        dataHoraInseriu=history.sent_at or timezone.now(),
        observacao=history.observation or "",
        # contatoTipo=_CONTACT_TYPE_DESC.get(history.contact_type, history.contact_type),
        # descricao=message_desc,
        idStatusContato=1,
        
        # A data de retorno vem diretamente do agendamento ligado ao histórico
        dataHoraRetornar=schedule.scheduled_date if schedule else None,
        
        # A versão do contrato vem diretamente do contrato ligado ao histórico
        versaoContrato=getattr(contract, "contract_version", None),
        
        # O ID da parcela vem da parcela ligada ao agendamento
        idContratoParcela=getattr(installment, "oralsin_installment_id", None)
    )