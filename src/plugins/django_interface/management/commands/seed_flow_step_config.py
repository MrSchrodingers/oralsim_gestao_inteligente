from django.core.management.base import BaseCommand
from django.db import transaction

from plugins.django_interface.models import FlowStepConfig

# Configuração de fluxo (steps 0 a 14)
FLOW_STEP_CONFIG = [
    { 'step_number': 0,  'channels': ['sms','whatsapp'],        'active': True,  'description': 'Semana 0 (Aviso): SMS + WhatsApp',     'cooldown_days': 7 },
    { 'step_number': 1,  'channels': ['sms','whatsapp'],        'active': True,  'description': 'Semana 1: SMS + WhatsApp',             'cooldown_days': 7 },
    { 'step_number': 2,  'channels': ['email','whatsapp'],      'active': True,  'description': 'Semana 2: Email + WhatsApp',           'cooldown_days': 7 },
    { 'step_number': 3,  'channels': ['sms', 'whatsapp'],       'active': True,  'description': 'Semana 3: SMS + WhatsApp',             'cooldown_days': 7 },
    { 'step_number': 4,  'channels': ['phonecall','email'],     'active': True,  'description': 'Semana 4: Ligação + Email',            'cooldown_days': 7 },
    { 'step_number': 5,  'channels': ['sms','whatsapp'],        'active': True,  'description': 'Semana 5: SMS + WhatsApp',             'cooldown_days': 7 },
    { 'step_number': 6,  'channels': ['letter'],                'active': True,  'description': 'Semana 6: Carta Amigável',             'cooldown_days': 7 },
    { 'step_number': 7,  'channels': ['email','whatsapp'],      'active': True,  'description': 'Semana 7: Email + WhatsApp',           'cooldown_days': 7 },
    { 'step_number': 8,  'channels': ['phonecall','email'],     'active': True,  'description': 'Semana 8: Ligação + Email',            'cooldown_days': 7 },
    { 'step_number': 9,  'channels': ['whatsapp'],              'active': True,  'description': 'Semana 9: WhatsApp',                   'cooldown_days': 7 },
    { 'step_number': 10, 'channels': ['sms', 'whatsapp'],       'active': True,  'description': 'Semana 10: SMS + WhatsApp',            'cooldown_days': 7 },
    { 'step_number': 11, 'channels': ['letter'],                'active': True,  'description': 'Semana 11: Carta Amigável',            'cooldown_days': 7 },
    { 'step_number': 12, 'channels': ['phonecall', 'whatsapp'], 'active': True,  'description': 'Semana 12: Ligação + WhatsApp',        'cooldown_days': 7 },
    { 'step_number': 13, 'channels': ['email', 'whatsapp'],     'active': True,  'description': 'Semana 13: Ligação + WhatsApp',        'cooldown_days': 7 },
    { 'step_number': 14, 'channels': ['whatsapp', 'email'],     'active': True,  'description': 'Cobrança Encerrada: WhatsApp + Email', 'cooldown_days': 7 },
    { 'step_number': 99, 'channels': ['whatsapp'],              'active': True,  'description': 'Primeiro contato: WhatsApp'          , 'cooldown_days': 7 },
]

class Command(BaseCommand):
    help = 'Seed de FlowStepConfig (steps de cobrança)'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('🌿 Iniciando seeding de FlowStepConfig...')
        created = updated = 0

        for cfg in FLOW_STEP_CONFIG:
            obj, created_flag = FlowStepConfig.objects.update_or_create(
                step_number=cfg['step_number'],
                defaults={
                    'channels': cfg['channels'],
                    'active': cfg['active'],
                    'description': cfg['description'],
                    'cooldown_days': cfg['cooldown_days'],
                }
            )

            if created_flag:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            "✅ Seeding concluído: {created} criados, {updated} atualizados."
        ))
