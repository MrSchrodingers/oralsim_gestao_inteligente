import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings  # noqa: E402

from notification_billing.adapters.message_broker.rabbitmq import RabbitMQ, retry_consume  # noqa: E402


def run():
    """
    Ponto de entrada para o consumidor Pika. 
    Será chamado pelo `manage.py runscript rabbit_consumer_entrypoint`.
    """
    # 1) configura DI
    from notification_billing.adapters.config.composition_root import setup_di_container_from_settings
    setup_di_container_from_settings(settings)
    from notification_billing.adapters.config.composition_root import container
    from notification_billing.core.application.services.notification_service import NotificationFacadeService

    rabbit: RabbitMQ = container.rabbit()
    notification_service: NotificationFacadeService = container.notification_service()

    # 2) declara exchanges e DLX
    rabbit.declare_exchange("notifications", dlx="notifications.dlx")
    rabbit.declare_exchange("notifications.dlx", exchange_type="fanout")

    # 3) declara e vincula filas
    # filas
    rabbit.declare_queue("notifications.manual", dlx="notifications.dlx")
    rabbit.bind_queue("notifications.manual", "notifications", "manual")
    rabbit.declare_queue("notifications.automated", dlx="notifications.dlx")
    rabbit.bind_queue("notifications.automated", "notifications", "automated")
    # cada mensagem = 1 agendamento
    rabbit.declare_queue("notifications.schedule", dlx="notifications.dlx")
    rabbit.bind_queue("notifications.schedule", "notifications", "schedule")

    ch = rabbit.channel()

    # 4) define consumidores (funções marcadas com @retry_consume)
    @retry_consume(queue="notifications.manual")
    def on_manual(ch, method, props, payload):
        notification_service.send_manual(
            patient_id=payload["patient_id"],
            contract_id=payload["contract_id"],
            channel=payload["channel"],
            message_id=payload["message_id"],
        )

    @retry_consume(queue="notifications.automated")
    def on_automated(ch, method, props, payload):
        notification_service.enqueue_pending_schedules(clinic_id=payload["clinic_id"])

    @retry_consume(queue="notifications.schedule")
    def on_schedule(ch, method, props, payload):
        notification_service.process_single_schedule(schedule_id=payload["schedule_id"])
        
    ch.basic_consume(
        queue="notifications.manual",
        on_message_callback=on_manual,
    )
    ch.basic_consume(
        queue="notifications.automated",
        on_message_callback=on_automated,
    )
    ch.basic_consume(
        queue="notifications.schedule",
        on_message_callback=on_schedule,
    )

    print(" [*] Rabbit consumer iniciado. Aguardando mensagens…")
    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        print(" [*] Rabbit consumer interrompido pelo usuário.")
        ch.close()

if __name__ == "__main__":
    run()
