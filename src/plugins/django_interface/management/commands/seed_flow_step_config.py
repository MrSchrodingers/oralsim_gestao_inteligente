from django.core.management.base import BaseCommand
from django.db import transaction

from plugins.django_interface.models import FlowStepConfig

# Configuração de fluxo (steps 0 a 14)
FLOW_STEP_CONFIG = [
    { 'step_number': 0,  'channels': ['whatsapp' ], 'active': True,  'description': 'Semana 0: WhatsApp',         'cooldown_days': 7 },
    { 'step_number': 1,  'channels': ['whatsapp', 'sms'], 'active': True,  'description': 'Semana 1: WhatsApp + SMS',         'cooldown_days': 7 },
    { 'step_number': 2,  'channels': ['phonecall'],        'active': True,  'description': 'Semana 2: WhatsApp',               'cooldown_days': 7 },
    { 'step_number': 3,  'channels': ['email'],           'active': True,  'description': 'Semana 3: E-mail',                 'cooldown_days': 7 },
    { 'step_number': 4,  'channels': ['whatsapp'],        'active': True,  'description': 'Semana 4: WhatsApp',               'cooldown_days': 7 },
    { 'step_number': 5,  'channels': ['phonecall'],       'active': True,  'description': 'Semana 5: Ligação',                'cooldown_days': 7 },
    { 'step_number': 6,  'channels': ['whatsapp','sms'],  'active': True,  'description': 'Semana 6: WhatsApp + SMS',         'cooldown_days': 7 },
    { 'step_number': 7,  'channels': ['whatsapp'],        'active': True,  'description': 'Semana 7: WhatsApp',               'cooldown_days': 7 },
    { 'step_number': 8,  'channels': ['whatsapp'],        'active': True,  'description': 'Semana 8: WhatsApp',               'cooldown_days': 7 },
    { 'step_number': 9,  'channels': ['phonecall'],       'active': True,  'description': 'Semana 9: Ligação',                'cooldown_days': 7 },
    { 'step_number': 10, 'channels': ['phonecall'],       'active': True,  'description': 'Semana 10: Ligação',               'cooldown_days': 7 },
    { 'step_number': 11, 'channels': ['phonecall'],       'active': True,  'description': 'Semana 11: Ligação',               'cooldown_days': 7 },
    { 'step_number': 12, 'channels': ['phonecall'],             'active': True,  'description': 'Semana 12: SMS',                   'cooldown_days': 7 },
    { 'step_number': 13, 'channels': ['phonecall'],             'active': True,  'description': 'Semana 13: Ligação',               'cooldown_days': 7 },
    { 'step_number': 14, 'channels': ['phonecall'],       'active': True,  'description': 'Cobrança Encerrada: SMS',         'cooldown_days': 7 },
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
