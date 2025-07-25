from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from notification_billing.core.domain.entities.contact_schedule_entity import ContactScheduleEntity


class ContactScheduleRepository(ABC):
    @abstractmethod
    def has_schedule_for_patient(self, patient_id: str) -> bool:
        """
        Verifica de forma eficiente se já existe QUALQUER agendamento
        (independente do status) para um determinado paciente.
        Retorna True se o paciente já teve algum contato agendado, False caso contrário.
        """
        ... 
        
    @abstractmethod
    def get_by_patient_contract(self, patient_id: str, contract_id: str) -> ContactScheduleEntity | None:
        """Recupera um agendamento pelo ID do paciente e do contrato."""
        ...

    @abstractmethod
    def find_pending_by_channel(self, clinic_id: str, channel: str) -> list[ContactScheduleEntity]:
        """Busca agendamentos pendentes para uma clínica e canal específicos."""
        ...

    @abstractmethod
    def bulk_update_status(self, schedule_ids: list[UUID], new_status: str) -> None:
        """Atualiza o status de múltiplos agendamentos em lote."""
        ...
    
    @abstractmethod
    def find_by_id(self, schedule_id: str) -> ContactScheduleEntity | None:
        """Recupera um agendamento pelo seu ID."""
        ...
    
    @abstractmethod
    def filter(self, **filtros) -> list[ContactScheduleEntity]:
        """Filtro de agendamentos."""
        ...
    @abstractmethod
    def cancel_pending_for_patient(patient_id: str) -> None:
        """Cancela/Pendura outros agendamentos ativos do paciente"""
        ...
        
    @abstractmethod
    def set_status_done(schedule_id: str) -> ContactScheduleEntity:
        """Marca o agendamento atual como concluído."""
        ...
        
    @abstractmethod
    def stream_pending(
        self,
        clinic_id: str,
        *,
        only_pending: bool = True,
        chunk_size: int = 100,
    ):
        """Gerador com SELECT … SKIP LOCKED para alto throughput."""
        ...
        
    @abstractmethod
    def list_pending(self, clinic_id: str) -> list[ContactScheduleEntity]:
        """Lista agendamentos cuja data já expirou."""
        ...

    @abstractmethod
    def save(self, schedule: ContactScheduleEntity) -> ContactScheduleEntity:
        """Cria ou atualiza um agendamento."""
        ...

    @abstractmethod
    def upsert(self, *, patient_id, contract_id, clinic_id, # noqa
               installment_id, step, scheduled_dt):
        """Cria ou atualiza um agendamento."""
        ...

    @abstractmethod
    def has_pending(self, patient_id: str, contract_id: str) -> bool:
        """Verifica se o paciente possui agendamentos pendentes."""
        ...
        
    @abstractmethod
    def delete(self, schedule_id: str) -> None:
        """Remove um agendamento."""
        ...

    @abstractmethod
    def get_status_summary_by_clinic(self, clinic_id: str) -> dict[str, Any]:
        """
        Calcula um sumário de agendamentos de contato para uma clínica,
        agrupando tanto por status quanto por canal de comunicação.
        """
        ...
