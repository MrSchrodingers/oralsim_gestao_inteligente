import locale
from datetime import date

from oralsin_core.core.domain.repositories.address_repository import AddressRepository
from oralsin_core.core.domain.repositories.clinic_data_repository import ClinicDataRepository
from oralsin_core.core.domain.repositories.clinic_repository import ClinicRepository
from oralsin_core.core.domain.repositories.contract_repository import ContractRepository
from oralsin_core.core.domain.repositories.installment_repository import InstallmentRepository
from oralsin_core.core.domain.repositories.patient_repository import PatientRepository


class LetterContextBuilder:                 
    def __init__(self,  # noqa: PLR0913
        patient_repo: PatientRepository,
        contract_repo: ContractRepository,
        installment_repo: InstallmentRepository,
        clinic_repo: ClinicRepository,
        clinic_data_repo: ClinicDataRepository,
        address_repo: AddressRepository,
    ):
        self.patient_repo = patient_repo
        self.contract_repo = contract_repo
        self.installment_repo = installment_repo
        self.clinic_repo = clinic_repo
        self.clinic_data_repo = clinic_data_repo
        self.address_repo = address_repo

    @staticmethod
    def _format_zip_code(zip_code: str | None) -> str:
        """
        Formata o CEP para o padrão XXXXX-XXX se ele for um CEP válido de 8 dígitos.
        """
        if zip_code and len(zip_code) == 8 and zip_code.isdigit():  # noqa: PLR2004
            return f"{zip_code[:5]}-{zip_code[5:]}"
        return zip_code or ""
      
    def build(self, *, patient_id: str, contract_id: str, clinic_id: str,
              installment_id: str | None = None, current_installment: bool = False) -> dict:

        patient   = self.patient_repo.find_by_id(patient_id)
        contract  = self.contract_repo.find_by_id(contract_id)
        inst = ( self.installment_repo.get_current_installment(contract_id)
                 if current_installment else
                 self.installment_repo.find_by_id(installment_id) )

        clinic        = self.clinic_repo.find_by_id(clinic_id)
        clinic_data   = self.clinic_data_repo.find_by_clinic(clinic_id)
        patient_addr  = ( self.address_repo.find_by_id(patient.address.id)
                          if patient and patient.address.id else None )
        clinic_addr   = ( self.address_repo.find_by_id(clinic_data.address.id)
                          if clinic_data and clinic_data.address.id else None )

        try:
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        except locale.Error:
            locale.setlocale(locale.LC_TIME, '') 

        return {
            # — Paciente
            "patient_name": patient.name if patient else "",
            "patient_cpf":  patient.cpf if patient else "Não informado",
            "patient_address": str(patient_addr) if patient_addr else "Endereço não informado",
            "patient_address_street":       patient_addr.street if patient_addr else "",
            "patient_address_number":       patient_addr.number if patient_addr else "",
            "patient_address_city":         patient_addr.city if patient_addr else "",
            "patient_address_neighborhood": patient_addr.neighborhood if patient_addr else "",
            "patient_address_complement":   patient_addr.complement if patient_addr else "",
            "patient_address_state":        patient_addr.state if patient_addr else "",
            "patient_address_zip_code":     f"CEP {self._format_zip_code(patient_addr.zip_code)}" if patient_addr else "",

            # — Contrato / parcela
            "contract_oralsin_id": contract.oralsin_contract_id if contract else "N/A",
            "installment_number":  inst.installment_number if inst else "",
            "installment_amount":  f"{inst.installment_amount:.2f}".replace('.', ',') if inst else "0,00",
            "installment_due_date": inst.due_date.strftime('%d/%m/%Y') if inst else "",

            # — Clínica
            "clinic_name":  clinic.name if clinic else "",
            "clinic_cnpj":  clinic.cnpj if clinic else "Não informado",
            "clinic_address_street":       clinic_addr.street if clinic_addr else "",
            "clinic_address_number":       clinic_addr.number if clinic_addr else "",
            "clinic_address_neighborhood": clinic_addr.neighborhood if clinic_addr else "",
            "clinic_address_city":         clinic_addr.city if clinic_addr else "",
            "clinic_address_state":        clinic_addr.state if clinic_addr else "",
            "clinic_address_zip_code":     f"{self._format_zip_code(clinic_addr.zip_code)}" if clinic_addr else "",

            # — Data de geração
            "today_date": date.today().strftime('%d de %B de %Y'),
        }
