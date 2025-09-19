from __future__ import annotations
import uuid
from django.db import transaction
from oralsin_core.core.domain.entities.payer_entity import PayerEntity
from oralsin_core.core.domain.repositories.payer_repository import PayerRepository
from plugins.django_interface.models import Payer, PayerPhone, Patient, Address

class PayerRepoImpl(PayerRepository):
    @transaction.atomic
    def upsert(self, payer_entity: PayerEntity) -> PayerEntity:
        """
        Cria ou atualiza um pagador. A chave para a atualização é a combinação de
        (patient_id, nome e documento).
        """
        defaults = {
            "name": payer_entity.name,
            "document": payer_entity.document,
            "document_type": payer_entity.document_type,
            "relationship": payer_entity.relationship,
            "email": payer_entity.email,
            "is_patient_the_payer": payer_entity.is_patient_the_payer,
        }

        # Salva ou atualiza o endereço se existir
        if payer_entity.address:
            address_model, _ = Address.objects.update_or_create(
                street__iexact=payer_entity.address.street,
                number=payer_entity.address.number,
                zip_code=payer_entity.address.zip_code,
                defaults={
                    "street": payer_entity.address.street,
                    "complement": payer_entity.address.complement,
                    "neighborhood": payer_entity.address.neighborhood,
                    "city": payer_entity.address.city,
                    "state": payer_entity.address.state,
                }
            )
            defaults["address_id"] = address_model.id
        
        # Identifica o Payer a ser atualizado/criado
        if payer_entity.is_patient_the_payer:
            # Se o pagador é o paciente, a chave é apenas o patient_id
            payer_model, created = Payer.objects.update_or_create(
                patient_id=payer_entity.patient_id,
                is_patient_the_payer=True,
                defaults=defaults
            )
        else:
            # Se for um terceiro, a chave é mais complexa
             payer_model, created = Payer.objects.update_or_create(
                patient_id=payer_entity.patient_id,
                name=payer_entity.name,
                document=payer_entity.document,
                defaults=defaults
            )
        
        # Sincroniza os telefones
        if payer_entity.phones:
            PayerPhone.objects.filter(payer=payer_model).delete()
            PayerPhone.objects.bulk_create([
                PayerPhone(
                    payer=payer_model,
                    phone_number=phone.phone_number,
                    phone_type=phone.phone_type,
                ) for phone in payer_entity.phones
            ])
            
        payer_entity.id = payer_model.id
        return payer_entity

    def find_by_patient_id(self, patient_id: uuid.UUID) -> list[PayerEntity]:
        # Implementação para buscar pagadores (não mostrada para brevidade)
        raise NotImplementedError