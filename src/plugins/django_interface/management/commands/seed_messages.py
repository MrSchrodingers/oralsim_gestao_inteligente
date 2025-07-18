from django.core.management.base import BaseCommand
from django.db import transaction

from plugins.django_interface.models import Message

# ----------------------------------------------------------------------------
# REGUA DE COMUNICAÇÃO TOTALMENTE REVISADA E INDIVIDUALIZADA POR ETAPA
# ----------------------------------------------------------------------------
NOTIFICATION_MESSAGES_DATA = [
    # Step 0 – Lembrete de Vencimento
    {
        "type": "sms",
        "content": "Ola, {{ nome }}. Lembrete: sua parcela de {{ valor }} vence em {{ vencimento }}. Se ja pagou, desconsidere. Duvidas, contate-nos.",
        "step": 0
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Lembrete de Vencimento de Parcela</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Este é um lembrete amigável de que sua parcela no valor de <strong>{{ valor }}</strong> tem o vencimento programado para <strong>{{ vencimento }}</strong>.</p>"
            "<p>Caso já tenha efetuado o pagamento, por favor, desconsidere esta mensagem. Estamos à disposição para qualquer esclarecimento.</p>"
            "<p>Atenciosamente,<br/>Departamento Financeiro</p>"
        ),
        "step": 0
    },
    {
        "type": "whatsapp",
        "content": (
            "Olá, {{ nome }}! 😊\n\n"
            "Passando para lembrar que sua parcela de *{{ valor }}* vence no dia *{{ vencimento }}*.\n\n"
            "Se o pagamento já foi realizado, pode ignorar esta mensagem. Qualquer dúvida, é só chamar!"
        ),
        "step": 0
    },
    # Step 1 – 1º Aviso Pós-Vencimento (Tom Solícito)
    {
        "type": "sms",
        "content": "Ola, {{ nome }}. Identificamos que a parcela de {{ valor }}, vencida em {{ vencimento }}, esta em aberto. Podemos ajudar? Contate-nos para regularizar.",
        "step": 1
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Identificamos uma Pendência de Pagamento</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Constatamos em nosso sistema que a sua parcela no valor de <strong>{{ valor }}</strong>, com vencimento em <strong>{{ vencimento }}</strong>, ainda não foi liquidada.</p>"
            "{% if total_parcelas_em_atraso > 1 %}<p>Notamos também que há um total de <strong>{{ total_parcelas_em_atraso }} parcelas</strong> pendentes em seu nome.</p>{% endif %}"
            "<p>Entendemos que imprevistos acontecem e estamos à disposição para ajudá-lo(a) a regularizar a situação. Por favor, entre em contato.</p>"
            "<p>Atenciosamente,<br/>Equipe de Relacionamento</p>"
        ),
        "step": 1
    },
    {
        "type": "whatsapp",
        "content": (
            "Olá, {{ nome }}. Tudo bem?\n\n"
            "Notamos que sua parcela de *{{ valor }}* (venc. *{{ vencimento }}*) consta como pendente. "
            "{% if total_parcelas_em_atraso > 1 %}No momento, existem *{{ total_parcelas_em_atraso }} parcelas* em aberto. {% endif %}"
            "Ocorreu algum problema?\n\n"
            "Estamos aqui para ajudar a resolver. Se precisar de uma 2ª via ou de outras informações, conte conosco! 👍"
        ),
        "step": 1
    },
    # Step 2 – 2º Aviso (Tom um pouco mais direto)
    {
        "type": "sms",
        "content": "Prezado(a) {{ nome }}, sua parcela de {{ valor }} (venc. {{ vencimento }}) continua em aberto. Por favor, regularize sua pendencia.",
        "step": 2
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Segundo Aviso de Parcela Vencida</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Escrevemos novamente para informar que a pendência referente à parcela de <strong>{{ valor }}</strong> (vencida em <strong>{{ vencimento }}</strong>) persiste.</p>"
            "<p>É importante regularizar sua situação para evitar o acúmulo de encargos. Se já realizou o pagamento, por favor, nos envie o comprovante.</p>"
            "<p>Atenciosamente,<br/>Departamento Financeiro</p>"
        ),
        "step": 2
    },
    {
        "type": "whatsapp",
        "content": (
            "Prezado(a) {{ nome }},\n\n"
            "Este é o nosso segundo aviso sobre a parcela de *{{ valor }}* vencida em *{{ vencimento }}*."
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "Por favor, dê atenção a esta pendência."
        ),
        "step": 2
    },
    # Step 3 – 3º Aviso (Aumento da Formalidade)
    {
        "type": "sms",
        "content": "AVISO: {{ nome }}, o debito de {{ valor }} (venc. {{ vencimento }}) permanece. Solicitamos contato para quitacao ou negociacao da divida.",
        "step": 3
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: AVISO - Débito em Aberto</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Apesar dos contatos anteriores, a parcela de <strong>{{ valor }}</strong>, vencida em <strong>{{ vencimento }}</strong>, continua pendente.</p>"
            "<p>Solicitamos um contato de sua parte para a quitação do débito ou para discutirmos as opções de negociação disponíveis.</p>"
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Cordialmente,<br/>Departamento de Cobrança</p>"
        ),
        "step": 3
    },
    {
        "type": "whatsapp",
        "content": (
            "Prezado(a) {{ nome }},\n\n"
            "Seu débito de *{{ valor }}* (vencimento em *{{ vencimento }}*) ainda não foi regularizado. "
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "Solicitamos que entre em contato para darmos andamento à quitação ou negociação da dívida."
        ),
        "step": 3
    },
    # Step 4 – Tom mais Sério e Formal
    {
        "type": "sms",
        "content": "NOTIFICACAO: {{ nome }}, a pendencia de {{ valor }} (venc. {{ vencimento }}) requer sua atencao imediata. Evite o avanco do processo de cobranca.",
        "step": 4
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Notificação Formal de Pendência Financeira</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Esta é uma notificação formal sobre a sua pendência financeira no valor de <strong>{{ valor }}</strong>, vencida em <strong>{{ vencimento }}</strong>.</p>"
            "<p>A ausência de pagamento até esta data nos preocupa. É fundamental que sua situação seja regularizada para evitar o avanço para as próximas etapas administrativas de cobrança.</p>"
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Aguardamos seu contato.<br/>Gerência de Contas</p>"
        ),
        "step": 4
    },
    {
        "type": "whatsapp",
        "content": (
            "⚠️ *Notificação de Pendência*\n\n"
            "{{ nome }}, sua dívida de *{{ valor }}*, vencida em *{{ vencimento }}*, requer sua atenção imediata. "
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "A regularização é necessária para evitar o avanço no processo de cobrança."
        ),
        "step": 4
    },
    # Step 5 – Aviso de Urgência
    {
        "type": "sms",
        "content": "URGENTE: {{ nome }}, seu debito de {{ valor }} (venc. {{ vencimento }}) precisa ser regularizado com urgencia. Contate-nos para evitar maiores transtornos.",
        "step": 5
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Ação Urgente Requerida - Débito Pendente</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>O seu débito de <strong>{{ valor }}</strong>, vencido em <strong>{{ vencimento }}</strong>, permanece sem solução. A regularização desta pendência é agora tratada como <strong>urgente</strong>.</p>"
            "<p>A falta de um acordo ou pagamento nos obrigará a adotar as medidas administrativas cabíveis. Entre em contato para evitar transtornos.</p>"
           "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Atenciosamente,<br/>Setor de Recuperação de Crédito</p>"
        ),
        "step": 5
    },
    {
        "type": "whatsapp",
        "content": (
            "🚨 *URGENTE* 🚨\n\n"
            "{{ nome }}, a regularização do seu débito de *{{ valor }}* (vencido em *{{ vencimento }}*) é necessária com *urgência*. "
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "Entre em contato conosco para evitar maiores transtornos."
        ),
        "step": 5
    },
    # Step 6 – Tom Firme e Direto
    {
        "type": "sms",
        "content": "NOTIFICACAO: {{ nome }}, o debito de {{ valor }} (venc. {{ vencimento }}) ainda consta em aberto. Sua regularizacao imediata e necessaria.",
        "step": 6
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Necessidade de Regularização Imediata de Débito</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Informamos que a pendência financeira de <strong>{{ valor }}</strong> (vencimento em <strong>{{ vencimento }}</strong>) ainda se encontra em aberto em nossos registros.</p>"
            "<p>Reforçamos a necessidade de regularização imediata do valor para que seu contrato não sofra maiores sanções.</p>"
           "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Aguardamos seu retorno,<br/>Departamento de Cobrança</p>"
        ),
        "step": 6
    },
    {
        "type": "whatsapp",
        "content": (
            "Prezado(a) {{ nome }},\n\n"
            "Seu débito no valor de *{{ valor }}* (venc. *{{ vencimento }}*) ainda consta em aberto. "
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "É necessária a regularização imediata da sua situação."
        ),
        "step": 6
    },
    # Step 7 – Débito Persistente
    {
        "type": "sms",
        "content": "AVISO: {{ nome }}, a persistencia do debito de {{ valor }} (venc. {{ vencimento }}) e preocupante. Pedimos seu contato em ate 48h.",
        "step": 7
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Débito Persistente em Seu Contrato</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>A persistência do débito de <strong>{{ valor }}</strong>, vencido em <strong>{{ vencimento }}</strong>, é motivo de grande preocupação e requer sua ação.</p>"
            "<p>Solicitamos que entre em contato conosco no prazo máximo de 48 horas para apresentar uma solução para esta pendência.</p>"
           "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Atenciosamente,<br/>Gerência de Contas</p>"
        ),
        "step": 7
    },
    {
        "type": "whatsapp",
        "content": (
            "Prezado(a) {{ nome }},\n\n"
            "A persistência do seu débito de *{{ valor }}* (vencido em *{{ vencimento }}*) nos preocupa. Pedimos, por favor, que nos contate em até 48 horas para resolvermos esta questão."
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
        ),
        "step": 7
    },
    # Step 8 – Reiteração de Pendência
    {
        "type": "sms",
        "content": "REITERAMOS: {{ nome }}, sua pendencia de {{ valor }} (venc. {{ vencimento }}) nao foi resolvida. A regularizacao e imprescindivel.",
        "step": 8
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Reiteramos a Necessidade de Regularização do seu Débito</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Reiteramos que a pendência financeira de <strong>{{ valor }}</strong> (vencimento em <strong>{{ vencimento }}</strong>) ainda não foi resolvida.</p>"
            "<p>É imprescindível que o pagamento seja efetuado para que possamos manter a regularidade do seu contrato.</p>"
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Atenciosamente,<br/>Setor de Recuperação de Crédito</p>"
        ),
        "step": 8
    },
    {
        "type": "whatsapp",
        "content": (
            "REITERAMOS, {{ nome }}:\n"
            "Sua pendência de *{{ valor }}* (vencida em *{{ vencimento }}*) ainda não foi resolvida. A regularização é imprescindível."
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
        ),
        "step": 8
    },
    # Step 9 – Penúltimo Aviso Administrativo
    {
        "type": "sms",
        "content": "PENULTIMO AVISO: {{ nome }}, debito de {{ valor }} (venc. {{ vencimento }}). O nao pagamento levara a medidas administrativas severas. Contato URGENTE.",
        "step": 9
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Penúltimo Aviso Administrativo de Cobrança</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Este é o penúltimo aviso administrativo referente ao débito de <strong>{{ valor }}</strong>, vencido em <strong>{{ vencimento }}</strong>.</p>"
            "<p>A ausência de uma resolução imediata nos levará a tomar as medidas administrativas mais severas previstas em contrato. Aguardamos seu contato em caráter de URGÊNCIA.</p>"
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Setor de Cobrança Especial</p>"
        ),
        "step": 9
    },
    {
        "type": "whatsapp",
        "content": (
            "🚨 *Penúltimo Aviso Administrativo* 🚨\n\n"
            "{{ nome }}, este é o penúltimo aviso sobre seu débito de *{{ valor }}* (vencido em *{{ vencimento }}*). O não pagamento resultará em medidas administrativas severas. Seu contato é *urgente*."
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
        ),
        "step": 9
    },
    # Step 10 – Último Aviso Administrativo
    {
        "type": "sms",
        "content": "ULTIMO AVISO: {{ nome }}, debito de {{ valor }} (venc. {{ vencimento }}). O proximo passo sera o apontamento do seu nome em orgaos de credito. Contate-nos JA.",
        "step": 10
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: ÚLTIMO AVISO ADMINISTRATIVO ANTES DE NEGATIVAÇÃO</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Este é o <strong>último aviso administrativo</strong> que receberá sobre a dívida de <strong>{{ valor }}</strong> (vencimento em <strong>{{ vencimento }}</strong>).</p>"
            "<p>Caso a pendência não seja sanada em 24 horas, seu CPF será encaminhado para inclusão nos cadastros de órgãos de proteção ao crédito (SPC/Serasa). </p>"
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Aproveite esta última oportunidade para uma resolução amigável.</p>"
        ),
        "step": 10
    },
    {
        "type": "whatsapp",
        "content": (
            "‼️ *ÚLTIMO AVISO ADMINISTRATIVO* ‼️\n\n"
            "{{ nome }}, débito de *{{ valor }}* (vencido em *{{ vencimento }}*). O próximo passo será o apontamento do seu nome em órgãos de proteção ao crédito. Contate-nos *imediatamente*."
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
        ),
        "step": 10
    },
    # Step 11 – Notificação Pré-Jurídica
    {
        "type": "sms",
        "content": "NOTIFICACAO EXTRAJUDICIAL: {{ nome }}, debito de {{ valor }} (venc. {{ vencimento }}). Nao havendo acordo, o caso sera encaminhado ao depto juridico.",
        "step": 11
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Notificação Extrajudicial de Débito</strong>"
            "<p><strong>NOTIFICAÇÃO EXTRAJUDICIAL</strong></p>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Serve a presente para <strong>notificá-lo(a) extrajudicialmente</strong> sobre o débito vencido em <strong>{{ vencimento }}</strong>, no valor de <strong>{{ valor }}</strong>.</p>"
            "<p>Não havendo a quitação ou um acordo formalizado no prazo improrrogável de 48 horas, o caso será encaminhado ao nosso departamento jurídico para ajuizamento da competente ação de execução.</p>"
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Setor Jurídico</p>"
        ),
        "step": 11
    },
    {
        "type": "whatsapp",
        "content": (
            "⚖️ *Notificação Extrajudicial* ⚖️\n\n"
            "Prezado(a) {{ nome }}, seu débito de *{{ valor }}* (venc. *{{ vencimento }}*) não foi quitado. Não havendo acordo em 48h, o caso será encaminhado ao departamento jurídico para as devidas providências."
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
        ),
        "step": 11
    },
    # Step 12 – Aviso de Encaminhamento para Negativação
    {
        "type": "sms",
        "content": "AVISO DE NEGATIVACAO: {{ nome }}, seu CPF foi encaminhado para inclusao nos orgaos de protecao ao credito devido ao debito de {{ valor }}.",
        "step": 12
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Comunicado de Inclusão em Órgãos de Proteção ao Crédito</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Em razão da não regularização do débito de <strong>{{ valor }}</strong>, vencido em <strong>{{ vencimento }}</strong>, informamos que seu CPF foi encaminhado para inclusão nos cadastros de inadimplentes dos órgãos de proteção ao crédito.</p>"  # noqa: E501
            "<p>A regularização do débito é a única medida que pode reverter esta ação.</p>"
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Departamento de Cobrança</p>"
        ),
        "step": 12
    },
    {
        "type": "whatsapp",
        "content": (
            "*AVISO DE NEGATIVAÇÃO*\n\n"
            "{{ nome }}, informamos que, devido ao não pagamento do débito de *{{ valor }}*, seu CPF foi encaminhado para inclusão nos órgãos de proteção ao crédito (SPC/Serasa)."
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
        ),
        "step": 12
    },
    # Step 13 – Última Oportunidade de Acordo
    {
        "type": "sms",
        "content": "ULTIMA OPORTUNIDADE: {{ nome }}, antes do ajuizamento da acao, oferecemos uma ultima oportunidade de acordo para o debito de {{ valor }}. Contate-nos HOJE.",
        "step": 13
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Última Oportunidade de Acordo Amigável</strong>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Antes de darmos início às medidas judiciais para a recuperação do crédito de <strong>{{ valor }}</strong>, oferecemos uma última oportunidade para um acordo amigável.</p>"
            "<p>Esta é a sua chance final de evitar custas processuais e outras complicações legais. Entre em contato conosco no dia de hoje.</p>"
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
            "<p>Setor de Conciliação</p>"
        ),
        "step": 13
    },
    {
        "type": "whatsapp",
        "content": (
            "*ÚLTIMA OPORTUNIDADE*\n\n"
            "{{ nome }}, antes do ajuizamento da ação judicial para a cobrança do seu débito de *{{ valor }}*, estamos oferecendo uma última oportunidade de acordo. Entre em contato *hoje*."
            "{% if total_parcelas_em_atraso > 1 %} Lembramos que seu contrato possui um total de *{{ total_parcelas_em_atraso }} parcelas* em atraso.{% endif %}\n\n"
        ),
        "step": 13
    },
    # Step 14 – Comunicado Final de Encaminhamento Jurídico
    {
        "type": "sms",
        "content": "COMUNICADO FINAL: {{ nome }}, seu debito de {{ valor }} foi encaminhado para o depto juridico. A cobranca sera feita exclusivamente por via judicial.",
        "step": 14
    },
    {
        "type": "email",
        "content": (
            "<strong>Assunto: Comunicado Final - Débito Encaminhado para Ação Judicial</strong>"
            "<p><strong>COMUNICADO FINAL</strong></p>"
            "<p>Prezado(a) {{ nome }},</p>"
            "<p>Esgotadas todas as tentativas de resolução amigável do débito de <strong>{{ valor }}</strong>, comunicamos oficialmente que o seu caso foi transferido ao nosso departamento jurídico.</p>"
            "<p>A partir desta data, a cobrança do referido valor será conduzida exclusivamente por via judicial. Quaisquer futuras comunicações sobre este assunto serão formais e legais.</p>"
            "<p>Sem mais.</p>"
        ),
        "step": 14
    },
    {
        "type": "whatsapp",
        "content": (
            "📋 *Comunicado Final de Cobrança Administrativa*\n\n"
            "Prezado(a) {{ nome }}, informamos que o processo de cobrança amigável referente ao débito de *{{ valor }}* está encerrado. O caso foi encaminhado ao departamento jurídico para início das medidas judiciais."
        ),
        "step": 14
    }
]

class Command(BaseCommand):
    help = 'Seed de templates de notificação (Message) com mensagens individualizadas e profissionais.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('🌿 Iniciando seeding de Message templates individualizados...')
        
        created_count = 0
        updated_count = 0
        
        # Itera sobre a lista de dados e cria ou atualiza cada mensagem.
        for entry in NOTIFICATION_MESSAGES_DATA:
            obj, created = Message.objects.update_or_create(
                type=entry['type'],
                step=entry['step'],
                clinic=None,  # São templates padrão
                is_default=True,
                defaults={'content': entry['content']}
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeding concluído! Templates criados: {created_count}, Templates atualizados: {updated_count}"
        ))