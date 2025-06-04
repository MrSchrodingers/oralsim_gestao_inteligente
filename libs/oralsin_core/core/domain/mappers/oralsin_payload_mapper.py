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
    def map_covered_clinic(cls, dto: OralsinClinicDTO) -> CoveredClinicEntity:
        try:
            return CoveredClinicEntity(
                id=cls._uuid(),
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
                is_notification_enabled=True,
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
                remaining_installments=dto.quantidadeParcelasFaltantes or 0,
                overdue_amount=float(dto.valorInadimplente or 0),
                first_billing_date=dto.primeiroFaturamento,
                negotiation_notes=dto.obsNegociacao or "",
                payment_method=pm,
                valor_contrato_final=float(dto.valorContratoFinal or 0),
                realizar_cobranca=dto.realizarCobranca,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("map_contract", error=str(exc), dto=dto.dict())
            raise MappingError(exc) from exc

    @classmethod
    def map_installments(
        cls,
        parcelas: list[OralsinParcelaDTO],
        parcela_detalhe: OralsinParcelaAtualDetalheDTO | None,
        contract_id: uuid.UUID,
    ) -> list[InstallmentEntity]:
        current_id = parcela_detalhe.idContratoParcela if parcela_detalhe else None
        version = parcela_detalhe.versaoContrato if parcela_detalhe else 1

        out: list[InstallmentEntity] = []
        for p in parcelas:
            out.append(
                InstallmentEntity(
                    id=cls._uuid(),
                    contract_id=contract_id,
                    contract_version=version,
                    installment_number=p.numeroParcela,
                    oralsin_installment_id=p.idContratoParcela,
                    due_date=p.dataVencimento.date(),
                    installment_amount=float(p.valorParcela),
                    received=p.possivelCompensado,
                    installment_status=p.nomeStatusFinanceiro,
                    is_current=p.idContratoParcela == current_id,
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
        Mapeia uma parcela (se detalhada, infere 'numeroParcela' cruzando pelo idContratoParcela).
        """
        # Se veio de detalhe, falta o numeroParcela
        if isinstance(dto, OralsinParcelaAtualDetalheDTO):
            if not parcelas:
                raise ValueError("Precisa de 'parcelas' para extrair numeroParcela da parcelaAtualDetalhe")
            # Busca o número da parcela pelo idContratoParcela
            matching = next((p for p in parcelas if p.idContratoParcela == dto.idContratoParcela), None)
            if not matching:
                raise MappingError(f"Não encontrou numeroParcela para idContratoParcela={dto.idContratoParcela}")
            installment_number = matching.numeroParcela
            nome_status_financeiro = matching.nomeStatusFinanceiro
            valor_parcela = matching.valorParcela
            possivel_compensado = matching.possivelCompensado
        else:
            installment_number = dto.numeroParcela
            nome_status_financeiro = dto.nomeStatusFinanceiro
            valor_parcela = dto.valorParcela
            possivel_compensado = dto.possivelCompensado

        contract_version = getattr(dto, "versaoContrato", 1)
        oralsin_installment_id = getattr(dto, "idContratoParcela", None)
        due_date = dto.dataVencimento.date() if hasattr(dto.dataVencimento, "date") else dto.dataVencimento

        return InstallmentEntity(
            id=cls._uuid(),
            contract_id=contract_id,
            contract_version=contract_version,
            installment_number=installment_number,
            oralsin_installment_id=oralsin_installment_id,
            due_date=due_date,
            installment_amount=float(valor_parcela),
            received=possivel_compensado,
            installment_status=nome_status_financeiro,
            is_current=bool(isinstance(dto, OralsinParcelaAtualDetalheDTO)),
        )
