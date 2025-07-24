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
                cnpj="",
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
                oralsin_clinic_id=dto.idClinica, 
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
            suffixes = [
                r"\(C\+P\)",
                r"\(E\+P\)",
                r"\( V \)",
                r"\(EP\)",
                r"\(C\+PP\)",
                r"\(V\)",
                r"\(C\)",
                r"\(J\)",
                r"\(CP\)",
                r"\(C P\)",
                r"\(F\)"
            ]
            pattern = re.compile("|".join(suffixes))
            name = dto.nomePaciente
            cleaned_name = pattern.sub("", name).strip()
            return PatientEntity(
                id=cls._uuid(),
                oralsin_patient_id=dto.idPaciente,
                clinic_id=clinic_id,
                name=cleaned_name,
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
                     ("commercial",dto.telefoneComercial),
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
    def _is_paid(dto: OralsinParcelaDTO) -> bool:
        """
        Verifica se o status financeiro da parcela é considerado pago.
        A regra agora foca exclusivamente nos status 'Compensado' ou 'Caixa Clinica'.
        """
        return is_paid_status(dto.nomeStatusFinanceiro)

    @classmethod
    def map_installments(
        cls,
        parcelas: list[OralsinParcelaDTO],
        contrato_version: int,
        contract_id: uuid.UUID,
    ) -> list[InstallmentEntity]:
        """
        Mapeia DTOs de parcela para Entidades, incluindo o novo campo 'agendado'.

        A responsabilidade de definir a flag 'is_current' foi removida
        desta camada e é calculada posteriormente, com base na nova regra de negócio.
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

            normalized_status = str(p.nomeStatus).strip().lower()
            is_scheduled = normalized_status == 'agendado'
            is_paid = cls._is_paid(p) and normalized_status == 'baixado'
            
            out.append(
                InstallmentEntity(
                    id=cls._uuid(),
                    contract_id=contract_id,
                    contract_version=version,
                    installment_number=p.numeroParcela,
                    oralsin_installment_id=p.idContratoParcela,
                    due_date=p.dataVencimento.date(),
                    installment_amount=float(p.valorParcela),
                    received=is_paid,
                    payment_method=pm,
                    installment_status=p.nomeStatusFinanceiro,
                    schedule=is_scheduled,
                    is_current=False,
                )
            )
        return out