from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

# ───────────────────────────────────────────────
# DTOs para integração com API Oralsin
# ───────────────────────────────────────────────
    
class OralsinEnderecoDTO(BaseModel):
    logradouro: str
    numero: str
    complemento: str | None = None
    bairro: str | None = None
    cidade: str
    estado: str
    cep: str

class OralsinTelefoneDTO(BaseModel):
    telefoneResidencial: str | None = Field(None, alias='telefoneResidencial')
    telefoneCelular: str | None = Field(None, alias='telefoneCelular')
    telefoneComercial: str | None = Field(None, alias='telefoneComercial')
    telefoneContato: str | None = Field(None, alias='telefoneContato')
    nomeContato: str | None = Field(None, alias='nomeContato')
    email: str | None = None


class OralsinContratoDTO(BaseModel):
    idContrato: int 
    versaoContrato: int | None = None
    quantidadeParcelasFaltantes: int | None = None
    valorInadimplente: str | None = None
    valorContratoFinal: str | None = None
    dataContrato: str | None = None
    primeiroFaturamento: datetime | None = None
    obsNegociacao: str | None = None
    nomeFormaPagamento: str | None = None
    realizarGestaoRecebiveis: bool
    realizarCobrancaAmigavel: bool


class OralsinParcelaDTO(BaseModel):
    idContratoParcela: int
    numeroParcela: int
    dataVencimento: datetime
    valorParcela: str
    nomeStatusFinanceiro: str
    possivelCompensado: bool
    nomeFormaPagamento: str
    parcelaUnica: bool
    nomeInstituicao: str | None = None
    nomeStatus: str | None = None
    pagante: OralsinPaganteDTO | None = None
    

class OralsinPaganteContatoDTO(BaseModel):
    telefoneResidencial: str | None = None
    telefoneCelular: str | None = None
    telefoneComercial: str | None = None
    email: str | None = None

class OralsinPaganteEnderecoDTO(BaseModel):
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    cep: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    estado: str | None = None

class OralsinPaganteDTO(BaseModel):
    nomePagante: str
    contato: OralsinPaganteContatoDTO
    endereco: OralsinPaganteEnderecoDTO
    dataNascimento: date | None = None
    documentoPagante: str | None = None
    tipoDocumento: str | None = None
    grauParentesco: str | None = None
    
    @field_validator("dataNascimento", mode="before")
    @classmethod
    def _sanitize_payer_birthdate(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if not s or s.startswith("-") or s.startswith("0000"):
                return None
            s = s.replace("Z", "+00:00")
            try:
                return date.fromisoformat(s.split("T")[0].split(" ")[0])
            except Exception:
                return None
        return v

class OralsinContatoHistoricoDTO(BaseModel):
    dataHoraInseriu: datetime
    observacao: str | None = None
    dataHoraRetornar: datetime | None = None
    idContatoTipo: int | None = None
    descricao: str | None = None

    @field_validator("dataHoraRetornar", "dataHoraInseriu", mode="before")
    @classmethod
    def _sanitize_datetime(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            # 1) placeholders comuns inválidos vindos da API
            if s.startswith("-") or s.startswith("0000") or s in {
                "0000-00-00", "0000-00-00T00:00:00Z",
            }:
                return None
            # 2) normaliza 'Z' para offset aceito pelo fromisoformat
            s = s.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(s)
            except Exception:
                # Falhou? trate como ausente
                return None
        return v

class OralsinContatoHistoricoEnvioDTO(BaseModel):
    # idClinica: int
    idPaciente: int
    idContrato: int | None = None
    dataHoraInseriu: datetime
    observacao: str | None = None
    # contatoTipo: str | None = None
    idContatoTipo: int | None = None
    # descricao: str | None = None
    id_status_contato: int = Field(alias="idStatusContato", default=1) 
    data_hora_retornar: datetime | None = Field(alias="dataHoraRetornar", default=None)
    versao_contrato: str | None = Field(alias="versaoContrato", default=None)
    id_contrato_parcela: int | None = Field(alias="idContratoParcela", default=None)
    
    class Config:
        populate_by_name = True # Permite popular usando o nome do campo ou o alias
        json_encoders = {
            datetime: lambda v: v.strftime('%Y-%m-%d %H:%M:%S')
        }
 

class OralsinClinicByPatientDTO(BaseModel):
    idClinica: int
    nomeClinica: str
    idClinicaInicial: int
    nomeClinicaInicial: str
    statusTratamento: str


class OralsinPacienteDTO(BaseModel):
    idPaciente: int
    nomePaciente: str
    cpfPaciente: str
    clinica: OralsinClinicByPatientDTO
    enderecos: OralsinEnderecoDTO
    contrato: OralsinContratoDTO
    telefones: OralsinTelefoneDTO
    parcelas: list[OralsinParcelaDTO]
    dataNascimento: date | None = None
    contatoHistorico: list[OralsinContatoHistoricoDTO] | None = None
    
    @field_validator("dataNascimento", mode="before")
    @classmethod
    def _sanitize_patient_birthdate(cls, v):
        if v is None: return None
        if isinstance(v, str):
            s = v.strip().replace("Z", "+00:00")
            if not s or s.startswith("-") or s.startswith("0000"):
                return None
            try:
                return date.fromisoformat(s.split("T")[0].split(" ")[0])
            except Exception:
                return None
        return v
    
class OralsinClinicDTO(BaseModel):
    idClinica: int
    nomeClinica: str
    razaoSocial: str
    sigla: str
    estado: str
    idCidade: int
    logradouro: str
    cep: str = Field(..., alias='CEP')
    ddd: str
    cnpj: str
    ativo: int
    telefone1: str | None = None
    telefone2: str | None = None
    bairro: str | None = None
    numero: str | None = None 
    franquia: int | None = None
    timezone: str | None = None
    dataSafra: str | None = None
    dataPrimeiroFaturamento: str | None = None
    programaIndicaSin: int | None = None
    exibeLPOralsin: int | None = None
    urlLandpage: str | None = None
    urlLPOralsin: str | None = None
    urlFacebook: str | None = None
    urlChatFacebook: str | None = None
    urlWhatsapp: str | None = None
    emailLead: str | None = None
    nomeCidade: str | None = None


class PaginationLinkDTO(BaseModel):
    url: str | None
    label: str
    active: bool


class ClinicaSearchResponseDTO(BaseModel):
    current_page: int
    data: list[OralsinClinicDTO]
    first_page_url: str
    from_: int = Field(..., alias='from')
    last_page: int
    last_page_url: str
    links: list[PaginationLinkDTO]
    next_page_url: str | None
    path: str
    per_page: int
    prev_page_url: str | None
    to: int
    total: int


# ───────────────────────────────────────────────
# DTOs de Query
# ───────────────────────────────────────────────
class ClinicsQueryDTO(BaseModel):
    search: str | None = None
    idClinica: int | None = None 
    per_page: int = 15
    ativo: int = 1


class InadimplenciaQueryDTO(BaseModel):
    idClinica: int
    dataVencimentoInicio: date
    dataVencimentoFim: date
    
    def to_query_params(self) -> dict[str, str]:
        return {
            "idClinica": str(self.idClinica),
            "dataVencimentoInicio": self.dataVencimentoInicio.isoformat(),
            "dataVencimentoFim":    self.dataVencimentoFim.isoformat(),
        }


class ContratoDetalheQueryDTO(BaseModel):
    idContrato: int
    versaoContrato: int


# ───────────────────────────────────────────────
# DTOs de Response
# ───────────────────────────────────────────────
class ClinicsResponseDTO(ClinicaSearchResponseDTO):
    """Alias para manter compatibilidade."""
    pass


class InadimplenciaResponseDTO(BaseModel):
    success: bool
    data: list[OralsinPacienteDTO]


# ───────────────────────────────────────────────
# DTOs de Detalhe de Contrato
# ───────────────────────────────────────────────
class FormaPagamentoDTO(BaseModel):
    idFormaPagamento: int
    nomeFormaPagamento: str


class OralsinPacienteSimplifiedDTO(BaseModel):
    idPaciente: int
    nomePaciente: str
    cpfPaciente: str
    telefones: dict[str, str | None]
    endereco: OralsinEnderecoDTO


class OralsinClinicaSimplesDTO(BaseModel):
    idClinica: int
    nomeClinica: str
    cnpj: str | None = None


class OralsinContratoDetalhadoDTO(BaseModel):
    idContrato: int
    versaoContrato: str | None = None
    contratoStatus: str
    paciente: OralsinPacienteSimplifiedDTO
    clinica: OralsinClinicaSimplesDTO
    valorTotal: float
    dataAssinatura: date


class InadimplenciaContratoResponseDTO(BaseModel):
    success: bool
    data: OralsinContratoDetalhadoDTO
