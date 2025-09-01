from django.db.models.signals import pre_save
from django.dispatch import receiver
from oralsin_core.adapters.utils.phone_utils import normalize_phone

from .models import PatientPhone


@receiver(pre_save, sender=PatientPhone)
def normalize_patient_phone_before_save(sender, instance: PatientPhone, **kwargs):
    norm = normalize_phone(instance.phone_number, default_region="BR", digits_only=True, with_plus=False)
    if not norm:
        raise ValueError(f"Telefone inválido: {instance.phone_number!r}")
    instance.phone_number = norm
