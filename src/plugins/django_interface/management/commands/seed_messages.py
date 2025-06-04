from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from plugins.django_interface.models import Message

NOTIFICATION_MESSAGES_DATA =  [
            # Step 0 – Aviso de vencimento
            {
              "type": "sms",
              "content": "Prezado(a) {{ nome }}, seu pagamento de {{ valor }} vence em {{ vencimento }}. Por favor, verifique e efetue o pagamento. Em caso de dúvidas, ligue para {{ telefone }}.",
              "step": 0
            },
            {
              "type": "email",
              "content": (
                "<p>Prezado(a) <strong>{{ nome }}</strong>,</p>"
                "<p>Este é um lembrete de que seu pagamento no valor de <strong>{{ valor }}</strong> vence em <strong>{{ vencimento }}</strong>.</p>"
                "<p>Por favor, providencie o pagamento o quanto antes ou entre em contato pelo telefone <strong>{{ telefone }}</strong> para mais informações.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 0
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! 😊\n"
                "Seu pagamento de {{ valor }} vence em {{ vencimento }}. "
                "Se precisar de ajuda, ligue para {{ telefone }}. Obrigado!"
              ),
              "step": 0
            },
            # Step 1 – Primeira notificação de dívida
            {
              "type": "sms",
              "content": "Olá {{ nome }}! Notamos que o valor de {{ valor }} com vencimento em {{ vencimento }} ainda não foi pago. Se precisar de ajuda, estamos à disposição.",
              "step": 1
            },
            {
              "type": "email",
              "content": (
                "<p>Olá <strong>{{ nome }}</strong>,</p>"
                "<p>Verificamos que o valor de <strong>{{ valor }}</strong>, com vencimento em <strong>{{ vencimento }}</strong>, ainda não foi quitado.</p>"
                "<p>Caso precise de alguma informação ou suporte para realizar o pagamento, estamos prontos para ajudar.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 1
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! Tudo bem?\n"
                "Estamos lembrando que o valor de {{ valor }} com vencimento em {{ vencimento }} ainda está pendente. "
                "Se precisar, conte conosco! 😊"
              ),
              "step": 1
            },
            # Steps 2 a 14 – Notificações de cobrança escalonadas
            # Para cada step, aumentamos a urgência e a formalidade da mensagem.
            # Step 2
            {
              "type": "sms",
              "content": "Olá {{ nome }}, notamos que o débito de {{ valor }} (vencido em {{ vencimento }}) permanece pendente. Solicitamos sua atenção imediata.",
              "step": 2
            },
            {
              "type": "email",
              "content": (
                "<p>Olá <strong>{{ nome }}</strong>,</p>"
                "<p>Identificamos que o débito de <strong>{{ valor }}</strong>, vencido em <strong>{{ vencimento }}</strong>, ainda não foi quitado.</p>"
                "<p>Pedimos que entre em contato ou regularize seu débito o mais breve possível.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 2
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! ⚠️\n"
                "Seu débito de {{ valor }} (vencido em {{ vencimento }}) ainda está pendente. "
                "Entre em contato para regularizar sua situação."
              ),
              "step": 2
            },
            # Step 3
            {
              "type": "sms",
              "content": "Prezado(a) {{ nome }}, seu débito de {{ valor }} vencido em {{ vencimento }} continua pendente. Solicitamos sua atenção imediata.",
              "step": 3
            },
            {
              "type": "email",
              "content": (
                "<p>Prezado(a) <strong>{{ nome }}</strong>,</p>"
                "<p>Constatamos que o débito de <strong>{{ valor }}</strong> vencido em <strong>{{ vencimento }}</strong> permanece em aberto.</p>"
                "<p>Por favor, providencie o pagamento ou entre em contato para esclarecimentos.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 3
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! 👀\n"
                "Seu débito de {{ valor }} (vencido em {{ vencimento }}) ainda não foi regularizado. "
                "Entre em contato o quanto antes."
              ),
              "step": 3
            },
            # Step 4
            {
              "type": "sms",
              "content": "Olá {{ nome }}, lembramos que o débito de {{ valor }} (vencido em {{ vencimento }}) ainda está em aberto. Por favor, regularize sua situação.",
              "step": 4
            },
            {
              "type": "email",
              "content": (
                "<p>Olá <strong>{{ nome }}</strong>,</p>"
                "<p>Reiteramos que o débito de <strong>{{ valor }}</strong>, com vencimento em <strong>{{ vencimento }}</strong>, permanece pendente.</p>"
                "<p>Sua regularização é essencial para evitar maiores transtornos.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 4
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! ⚠️\n"
                "Lembramos que o débito de {{ valor }} vencido em {{ vencimento }} ainda não foi pago. "
                "Por favor, regularize sua situação."
              ),
              "step": 4
            },
            # Step 5
            {
              "type": "sms",
              "content": "Prezado(a) {{ nome }}, seu débito de {{ valor }} (vencido em {{ vencimento }}) persiste. Favor providenciar o pagamento com urgência.",
              "step": 5
            },
            {
              "type": "email",
              "content": (
                "<p>Prezado(a) <strong>{{ nome }}</strong>,</p>"
                "<p>Observamos que o débito de <strong>{{ valor }}</strong> vencido em <strong>{{ vencimento }}</strong> ainda não foi regularizado.</p>"
                "<p>Solicitamos que entre em contato imediatamente para resolver essa pendência.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 5
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! 🚨\n"
                "Seu débito de {{ valor }} (vencido em {{ vencimento }}) ainda está em aberto. "
                "Entre em contato com urgência para regularizar sua situação."
              ),
              "step": 5
            },
            # Step 6
            {
              "type": "sms",
              "content": "Olá {{ nome }}, a dívida de {{ valor }} (vencida em {{ vencimento }}) continua pendente. Favor regularizar o pagamento.",
              "step": 6
            },
            {
              "type": "email",
              "content": (
                "<p>Olá <strong>{{ nome }}</strong>,</p>"
                "<p>Notamos que o débito de <strong>{{ valor }}</strong> vencido em <strong>{{ vencimento }}</strong> permanece sem pagamento.</p>"
                "<p>Pedimos que regularize seu débito ou entre em contato para mais informações.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 6
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! ⚠️\n"
                "Seu débito de {{ valor }} (vencido em {{ vencimento }}) ainda está pendente. "
                "Regularize-o o quanto antes ou entre em contato."
              ),
              "step": 6
            },
            # Step 7
            {
              "type": "sms",
              "content": "Prezado(a) {{ nome }}, este é um aviso: o débito de {{ valor }} (vencido em {{ vencimento }}) não foi quitado. Favor efetuar o pagamento.",
              "step": 7
            },
            {
              "type": "email",
              "content": (
                "<p>Prezado(a) <strong>{{ nome }}</strong>,</p>"
                "<p>Este é um aviso importante de que o débito de <strong>{{ valor }}</strong> vencido em <strong>{{ vencimento }}</strong> permanece em aberto.</p>"
                "<p>Solicitamos que regularize a situação imediatamente para evitar transtornos.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 7
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! ⚠️\n"
                "Aviso: seu débito de {{ valor }} (vencido em {{ vencimento }}) ainda não foi quitado. "
                "Entre em contato imediatamente."
              ),
              "step": 7
            },
            # Step 8
            {
              "type": "sms",
              "content": "Olá {{ nome }}, seu débito de {{ valor }} (vencido em {{ vencimento }}) permanece em aberto. Por favor, efetue o pagamento o quanto antes.",
              "step": 8
            },
            {
              "type": "email",
              "content": (
                "<p>Olá <strong>{{ nome }}</strong>,</p>"
                "<p>Reiteramos que o débito de <strong>{{ valor }}</strong>, com vencimento em <strong>{{ vencimento }}</strong>, ainda não foi regularizado.</p>"
                "<p>É imprescindível que o pagamento seja efetuado para evitar medidas administrativas.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 8
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! ⚠️\n"
                "Seu débito de {{ valor }} (vencido em {{ vencimento }}) ainda está pendente. "
                "Regularize-o o quanto antes ou entre em contato."
              ),
              "step": 8
            },
            # Step 9
            {
              "type": "sms",
              "content": "Prezado(a) {{ nome }}, este é o penúltimo aviso: o débito de {{ valor }} (vencido em {{ vencimento }}) não foi pago.",
              "step": 9
            },
            {
              "type": "email",
              "content": (
                "<p>Prezado(a) <strong>{{ nome }}</strong>,</p>"
                "<p>Esta é a penúltima notificação informando que o débito de <strong>{{ valor }}</strong> vencido em <strong>{{ vencimento }}</strong> permanece sem pagamento.</p>"
                "<p>Solicitamos que regularize sua situação imediatamente para evitar medidas mais drásticas.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 9
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! 🚨\n"
                "Penúltimo aviso: seu débito de {{ valor }} (vencido em {{ vencimento }}) ainda está pendente. "
                "Entre em contato imediatamente!"
              ),
              "step": 9
            },
            # Step 10
            {
              "type": "sms",
              "content": "Olá {{ nome }}, último aviso antes de medidas administrativas: o débito de {{ valor }} (vencido em {{ vencimento }}) precisa ser quitado.",
              "step": 10
            },
            {
              "type": "email",
              "content": (
                "<p>Olá <strong>{{ nome }}</strong>,</p>"
                "<p>Este é o último aviso para a regularização do débito de <strong>{{ valor }}</strong>, vencido em <strong>{{ vencimento }}</strong>.</p>"
                "<p>Caso o pagamento não seja efetuado, medidas administrativas poderão ser iniciadas.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 10
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! 🚨\n"
                "Último aviso: seu débito de {{ valor }} (vencido em {{ vencimento }}) deve ser quitado imediatamente para evitar medidas administrativas."
              ),
              "step": 10
            },
            # Step 11
            {
              "type": "sms",
              "content": "Prezado(a) {{ nome }}, seu débito de {{ valor }} (vencido em {{ vencimento }}) não foi pago. Entre em contato para evitar ações legais.",
              "step": 11
            },
            {
              "type": "email",
              "content": (
                "<p>Prezado(a) <strong>{{ nome }}</strong>,</p>"
                "<p>Informamos que o débito de <strong>{{ valor }}</strong> vencido em <strong>{{ vencimento }}</strong> continua em aberto.</p>"
                "<p>Solicitamos que entre em contato imediatamente para regularizar sua situação, a fim de evitar ações legais.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 11
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! ⚠️\n"
                "Aviso legal: seu débito de {{ valor }} (vencido em {{ vencimento }}) não foi pago. "
                "Regularize sua situação para evitar medidas legais."
              ),
              "step": 11
            },
            # Step 12
            {
              "type": "sms",
              "content": "Olá {{ nome }}, notamos que o débito de {{ valor }} (vencido em {{ vencimento }}) permanece pendente. Esta é a notificação final.",
              "step": 12
            },
            {
              "type": "email",
              "content": (
                "<p>Olá <strong>{{ nome }}</strong>,</p>"
                "<p>Esta é a notificação final informando que o débito de <strong>{{ valor }}</strong>, com vencimento em <strong>{{ vencimento }}</strong>, continua sem pagamento.</p>"
                "<p>Medidas administrativas serão tomadas se não houver regularização imediata.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 12
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! ⚠️\n"
                "Notificação final: seu débito de {{ valor }} (vencido em {{ vencimento }}) permanece pendente. "
                "Entre em contato imediatamente para evitar medidas administrativas."
              ),
              "step": 12
            },
            # Step 13
            {
              "type": "sms",
              "content": "Prezado(a) {{ nome }}, este é o último lembrete: o débito de {{ valor }} (vencido em {{ vencimento }}) continua sem pagamento.",
              "step": 13
            },
            {
              "type": "email",
              "content": (
                "<p>Prezado(a) <strong>{{ nome }}</strong>,</p>"
                "<p>Este é o último lembrete sobre o débito de <strong>{{ valor }}</strong>, vencido em <strong>{{ vencimento }}</strong>.</p>"
                "<p>Solicitamos que entre em contato imediatamente para regularizar sua situação e evitar consequências legais.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 13
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! ⚠️\n"
                "Último lembrete: seu débito de {{ valor }} (vencido em {{ vencimento }}) ainda não foi regularizado. "
                "Entre em contato imediatamente."
              ),
              "step": 13
            },
            # Step 14 – Cobrança encerrada
            {
              "type": "sms",
              "content": "Olá {{ nome }}, seu débito de {{ valor }} (vencido em {{ vencimento }}) permanece pendente. "
                         "Esta cobrança foi encerrada. Entre em contato imediatamente para evitar consequências legais.",
              "step": 14
            },
            {
              "type": "email",
              "content": (
                "<p>Prezado(a) <strong>{{ nome }}</strong>,</p>"
                "<p>Após diversas notificações, informamos que o débito de <strong>{{ valor }}</strong> vencido em <strong>{{ vencimento }}</strong> permanece sem pagamento.</p>"
                "<p>Esta cobrança foi encerrada e medidas legais poderão ser tomadas. Entre em contato imediatamente para evitar maiores transtornos.</p>"
                "<p>Atenciosamente,<br/>Equipe de Cobrança</p>"
              ),
              "step": 14
            },
            {
              "type": "whatsapp",
              "content": (
                "Olá {{ nome }}! 🚨\n"
                "Cobrança encerrada: seu débito de {{ valor }} (vencido em {{ vencimento }}) continua pendente. "
                "Entre em contato imediatamente para evitar consequências legais."
              ),
              "step": 14
          }
        ]

class Command(BaseCommand):
    help = 'Seed de templates de notificação (Message)'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('🌿 Iniciando seeding de Message templates...')
        created = 0
        skipped = 0
        now = timezone.now()

        for entry in NOTIFICATION_MESSAGES_DATA:
            obj, created_flag = Message.objects.update_or_create(
                type=entry['type'],
                step=entry['step'],
                clinic=None,
                defaults={
                    'content': entry['content'],
                    'is_default': True,
                    'updated_at': now,
                }
            )
            if created_flag:
                created += 1
                obj.created_at = now
                obj.save(update_fields=['created_at'])
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Templates criados: {created}, atualizados (pulados criação): {skipped}"
        ))
        self.stdout.write(self.style.SUCCESS('✅ Seeding de Message templates concluído.'))
