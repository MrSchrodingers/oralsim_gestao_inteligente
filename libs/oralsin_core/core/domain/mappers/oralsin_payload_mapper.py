from __future__ import annotations

import re
import uuid
from datetime import date

import structlog

from oralsin_core.core.application.dtos.oralsin_dtos import (
    OralsinClinicByPatientDTO,
    OralsinClinicDTO,
    OralsinContratoDTO,
    OralsinEnderecoDTO,
    OralsinPacienteDTO,
    OralsinParcelaAtualDetalheDTO,
    OralsinParcelaDTO,
    OralsinTelefoneDTO,
)
from oralsin_core.core.application.services.payment_status_classifier import is_paid_status
from oralsin_core.core.domain.entities.address_entity import AddressEntity
from oralsin_core.core.domain.entities.clinic_data_entity import ClinicDataEntity
from oralsin_core.core.domain.entities.clinic_entity import ClinicEntity
from oralsin_core.core.domain.entities.clinic_phone_entity import ClinicPhoneEntity
from oralsin_core.core.domain.entities.contract_entity import ContractEntity
from oralsin_core.core.domain.entities.covered_clinics import CoveredClinicEntity
from oralsin_core.core.domain.entities.installment_entity import InstallmentEntity
from oralsin_core.core.domain.entities.patient_entity import PatientEntity
from oralsin_core.core.domain.entities.patient_phone_entity import PatientPhoneEntity
from oralsin_core.core.domain.entities.payment_method_entity import PaymentMethodEntity

logger = structlog.get_logger(__name__)


class MappingError(Exception):
    """Erro no mapeamento DTO ➜ Entity."""


class OralsinPayloadMapper:
    # ───────────────────────── helpers ──────────────────────────
    @staticmethod
    def _uuid() -> uuid.UUID:
        return uuid.uuid4()

    @staticmethod
    def _split_logradouro(logradouro: str) -> tuple[str, str]:
        """
        Tenta separar “Rua Algo, 123” ⇒ (“Rua Algo”, “123”).
        Caso não encontre número, devolve (“Rua Algo, 123”, "").
        """
        m = re.match(r"^(.*?),\s*([\w\-]+)$", logradouro.strip())
        return (m.group(1), m.group(2)) if m else (logradouro, "")

    # ───────────────────────── clínicas ─────────────────────────
    @classmethod
    def map_clinic_by_patient(cls, dto: OralsinClinicByPatientDTO) -> ClinicEntity:
        try:
            return ClinicEntity(
                id=cls._uuid(),
                oralsin_clinic_id=dto.idClinica,
                name=dto.nomeClinica,
                cnpj="",                 # não vem nesse DTO
            )
        except Exception as exc:  # pragma: no cover
            logger.error("map_clinic_by_patient", error=str(exc), dto=dto.dict())
            raise MappingError(exc) from exc

    @classmethod
    def map_covered_clinic(cls, dto: OralsinClinicDTO, clinic_id: uuid.UUID,) -> CoveredClinicEntity:
        try:
            return CoveredClinicEntity(
                id=cls._uuid(),
                clinic_id=clinic_id, 
                oralsin_clinic_id=dto.idClinica,
                name=dto.nomeClinica,
                cnpj=dto.cnpj,
                corporate_name=dto.razaoSocial,
                acronym=dto.sigla,
                active=bool(dto.ativo),
            )
        except Exception as exc:  # pragma: no cover
            logger.error("map_covered_clinic", error=str(exc), dto=dto.dict())
            raise MappingError(exc) from exc

    @classmethod
    def map_clinic_data(cls, dto: OralsinClinicDTO,
                        clinic_id: uuid.UUID) -> ClinicDataEntity:
        try:
            # separa logradouro → rua, numero
            rua, numero = cls._split_logradouro(dto.logradouro)

            address = cls.map_address(
                OralsinEnderecoDTO(
                    logradouro=rua or "",
                    numero=numero or "",
                    complemento=None,
                    bairro=dto.bairro or "",
                    cidade=dto.nomeCidade or "",
                    estado=dto.estado or "",
                    cep=dto.cep or "",
                )
            )
            return ClinicDataEntity(
                id=cls._uuid(),
                clinic_id=clinic_id,
                oralsin_clinic_id=dto.idClinica,      # ← agora incluímos
                corporate_name=dto.razaoSocial,
                acronym=dto.sigla,
                address=address,
                active=bool(dto.ativo),
                franchise=bool(dto.franquia),
                timezone=dto.timezone,
                first_billing_date=(
                    date.fromisoformat(dto.dataPrimeiroFaturamento)
                    if dto.dataPrimeiroFaturamento else None
                ),
            )
        except Exception as exc:  # pragma: no cover
            logger.error("map_clinic_data", error=str(exc), dto=dto.dict())
            raise MappingError(exc) from exc

    # ───────────────────────── endereço ─────────────────────────
    @classmethod
    def map_address(cls, dto: OralsinEnderecoDTO) -> AddressEntity:
        try:
            return AddressEntity(
                id=cls._uuid(),
                street=dto.logradouro,
                number=dto.numero,
                complement=dto.complemento,
                neighborhood=dto.bairro,
                city=dto.cidade,
                state=dto.estado,
                zip_code=dto.cep,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("map_address", error=str(exc), dto=dto.dict())
            raise MappingError(exc) from exc

    # ───────────────── paciente + telefones ─────────────────────
    @classmethod
    def map_patient(cls, dto: OralsinPacienteDTO,
                    clinic_id: uuid.UUID) -> PatientEntity:
        try:
            address = cls.map_address(dto.enderecos)
            return PatientEntity(
                id=cls._uuid(),
                oralsin_patient_id=dto.idPaciente,
                clinic_id=clinic_id,
                name=dto.nomePaciente,
                cpf=dto.cpfPaciente,
                address=address,
                contact_name=dto.telefones.nomeContato or "",
                email=dto.telefones.email or "",
            )
        except Exception as exc:  # pragma: no cover
            logger.error("map_patient", error=str(exc), dto=dto.dict())
            raise MappingError(exc) from exc

    @classmethod
    def map_patient_phones(cls, dto: OralsinTelefoneDTO,
                           patient_id: uuid.UUID) -> list[PatientPhoneEntity]:
        out: list[PatientPhoneEntity] = []
        for t, n in [("home", dto.telefoneResidencial),
                     ("mobile", dto.telefoneCelular),
                     ("commercial", dto.telefoneComercial),
                     ("contact", dto.telefoneContato)]:
            if n:
                out.append(
                    PatientPhoneEntity(id=cls._uuid(),
                                       patient_id=patient_id,
                                       phone_number=n,
                                       phone_type=t)
                )
        return out

    @classmethod
    def map_clinic_phones(cls, dto: OralsinClinicDTO,
                          clinic_id: uuid.UUID) -> list[ClinicPhoneEntity]:
        out: list[ClinicPhoneEntity] = []
        for t, n in [("primary", dto.telefone1), ("secondary", dto.telefone2)]:
            if n:
                out.append(
                    ClinicPhoneEntity(id=cls._uuid(),
                                      clinic_id=clinic_id,
                                      phone_number=n,
                                      phone_type=t)
                )
        return out

    # ───────────────── contrato + parcelas ──────────────────────
    @classmethod
    def map_contract(cls, dto: OralsinContratoDTO,
                    patient_id: uuid.UUID,
                    clinic_id: uuid.UUID) -> ContractEntity:
        try:
            pm: PaymentMethodEntity | None = None
            if dto.nomeFormaPagamento:
                pm = PaymentMethodEntity(
                    id=cls._uuid(),
                    oralsin_payment_method_id=0,
                    name=dto.nomeFormaPagamento,
                )
            return ContractEntity(
                id=cls._uuid(),
                oralsin_contract_id=dto.idContrato,
                patient_id=patient_id,
                clinic_id=clinic_id,
                status="ativo",
                contract_version=str(dto.versaoContrato),
                remaining_installments=dto.quantidadeParcelasFaltantes or 0,
                overdue_amount=float(dto.valorInadimplente or 0),
                first_billing_date=dto.primeiroFaturamento,
                negotiation_notes=dto.obsNegociacao or "",
                payment_method=pm,
                final_contract_value=float(dto.valorContratoFinal or 0),
                do_notifications=dto.realizarCobranca,
                do_billings=dto.realizarCobrancaAmigavel,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("map_contract", error=str(exc), dto=dto.dict())
            raise MappingError(exc) from exc


    @staticmethod
    def _is_paid(dto) -> bool:
        venc_date = dto.dataVencimento.date()
        not_future_due = venc_date <= date.today()
        return is_paid_status(dto.nomeStatusFinanceiro) and not_future_due
        
    @classmethod
    def map_installments(
        cls,
        parcelas: list[OralsinParcelaDTO],
        contrato_version: int,
        contract_id: uuid.UUID,
    ) -> list[InstallmentEntity]:
        """
        [CORRIGIDO] Mapeia DTOs de parcela para Entidades.

        A responsabilidade de definir a flag 'is_current' foi removida
        desta camada e centralizada exclusivamente no SyncInadimplenciaHandler.
        """
        version = str(contrato_version)
        out: list[InstallmentEntity] = []
        seen_ids = set()
        for p in parcelas:
            if p.idContratoParcela in seen_ids:
                continue
            seen_ids.add(p.idContratoParcela)

            pm = None
            if p.nomeFormaPagamento:
                pm = PaymentMethodEntity(
                    id=cls._uuid(),
                    oralsin_payment_method_id=0,
                    name=p.nomeFormaPagamento,
                )
            
            out.append(
                InstallmentEntity(
                    id=cls._uuid(),
                    contract_id=contract_id,
                    contract_version=version,
                    installment_number=p.numeroParcela,
                    oralsin_installment_id=p.idContratoParcela,
                    due_date=p.dataVencimento.date(),
                    installment_amount=float(p.valorParcela),
                    received=cls._is_paid(p),
                    payment_method=pm,
                    installment_status=p.nomeStatusFinanceiro
                )
            )
        return out

    @classmethod
    def map_installment(
        cls,
        dto: OralsinParcelaAtualDetalheDTO | OralsinParcelaDTO,
        contract_id: uuid.UUID,
        parcelas: list[OralsinParcelaDTO] = None,
    ) -> InstallmentEntity:
        """
        Mapeia uma única parcela. Se for a 'parcelaAtualDetalhe', infere dados
        faltantes (como 'numeroParcela') a partir da lista completa de 'parcelas'.
        A flag 'is_current' é marcada como True apenas se o DTO for do tipo
        'OralsinParcelaAtualDetalheDTO'.
        """
        is_current_dto = isinstance(dto, OralsinParcelaAtualDetalheDTO)

        if is_current_dto:
            if not parcelas:
                raise ValueError(
                    "A lista 'parcelas' é necessária para mapear uma 'OralsinParcelaAtualDetalheDTO'."
                )
            # Busca a parcela correspondente na lista para obter todos os dados.
            matching = next(
                (p for p in parcelas if p.idContratoParcela == dto.idContratoParcela),
                None,
            )
            if not matching:
                raise MappingError(
                    f"Não foi possível encontrar a parcela correspondente ao 'idContratoParcela={dto.idContratoParcela}' na lista de parcelas."
                )
            
            # Usa os dados da parcela correspondente que é mais completa.
            source_dto = matching
            oralsin_installment_id = dto.idContratoParcela
        else:
            source_dto = dto
            oralsin_installment_id = dto.idContratoParcela

        pm = None
        if getattr(source_dto, "nomeFormaPagamento", None):
            pm = PaymentMethodEntity(
                id=cls._uuid(),
                oralsin_payment_method_id=0,
                name=source_dto.nomeFormaPagamento,
            )

        return InstallmentEntity(
            id=cls._uuid(),
            contract_id=contract_id,
            contract_version=str(getattr(dto, "versaoContrato", 1)),
            installment_number=source_dto.numeroParcela,
            oralsin_installment_id=oralsin_installment_id,
            due_date=source_dto.dataVencimento.date(),
            installment_amount=float(source_dto.valorParcela),
            received=cls._is_paid(source_dto),
            payment_method=pm,
            installment_status=source_dto.nomeStatusFinanceiro,
            is_current=False,
        )