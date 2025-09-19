from typing import Literal

from django.utils import timezone
from oralsin_core.core.application.dtos.oralsin_dtos import OralsinContatoHistoricoEnvioDTO

from plugins.django_interface.models import ContactHistory

ContactType = Literal["phonecall", "sms", "whatsapp", "email", "letter"]
_CONTACT_TYPE_DESC: dict[ContactType, str] = {
    "phonecall": "Ligacao telefonica",
    "sms": "SMS",
    "whatsapp": "WhatsApp",
    "email": "E-mail",
    "letter": "Carta Amigavel"
}
_ID_CONTACT: dict[str, int] = {
    "email":            40, # "Envio de E-mail"
    "phonecall":        47, # "Cobrança via Telefone"
    "phonecall_fail":   48, # "Telefone Não Atende"
    "fail_phone":       50, # "Telefone Inexistente"
    "sms":              3,  # "Caixa Postal"
    "whatsapp":         46, # "Cobrança via WhatsApp"
    "letter":           57, # "Envio Carta Cobrança"
}


def build_oralsin_payload(history: ContactHistory) -> OralsinContatoHistoricoEnvioDTO:
    """
    Constrói o payload para a API Oralsin a partir de um objeto ContactHistory.
    A lógica agora diferencia entre o paciente e um pagador terceiro.
    
    IMPORTANTE: Para performance ideal, o objeto 'history' deve ser buscado
    com .select_related(
        'patient', 'clinic', 'contract', 'message', 
        'schedule__installment', 'schedule__installment__payer'
    ).
    """
    
    # --- 1. Acesse os dados pré-carregados de forma segura ---
    patient = history.patient
    contract = history.contract
    schedule = history.schedule
    
    if not patient or not patient.oralsin_patient_id:
        raise ValueError(f"Histórico {history.id} está sem paciente ou ID Oralsin do paciente.")

    # --- 2. Lógica para determinar o alvo do contato (Paciente ou Pagador) ---
    installment = schedule.installment if schedule else None
    payer = installment.payer if installment else None
    
    payer_info_for_observation = ""
    # A condição verifica se existe um pagador e se ele NÃO é o próprio paciente.
    if payer and not payer.is_patient_the_payer:
        relationship = f" ({payer.relationship})" if payer.relationship else ""
        payer_info_for_observation = f" | Destinatário: {payer.name}{relationship}"

    # --- 3. Construção da observação e definição do ID do contato ---
    contact_type_description = _CONTACT_TYPE_DESC.get(history.contact_type, history.contact_type)
    observacao_descritiva = f"Mensagem enviada por {contact_type_description}{payer_info_for_observation}"
    
    # Usa o ID do tipo de contato, com um fallback genérico para segurança.
    id_contact = _ID_CONTACT.get(history.contact_type, 1)

    # --- 4. Construção final do DTO ---
    return OralsinContatoHistoricoEnvioDTO(
        # IDs principais sempre se referem ao titular da dívida (Paciente/Contrato)
        idPaciente=patient.oralsin_patient_id,
        idContrato=getattr(contract, "oralsin_contract_id", None),
        versaoContrato=getattr(contract, "contract_version", None),
        
        # O ID da parcela vem da parcela ligada ao agendamento
        idContratoParcela=getattr(installment, "oralsin_installment_id", None),
        
        # Dados do histórico
        dataHoraInseriu=history.sent_at or timezone.now(),
        observacao=observacao_descritiva,
        idStatusContato=id_contact,
    )