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
    for key in ("manual", "automated"):
        queue = f"notifications.{key}"
        rabbit.declare_queue(queue, dlx="notifications.dlx")
        rabbit.bind_queue(queue, "notifications", key)

    ch = rabbit.channel()

    # 4) define consumidores (funções marcadas com @retry_consume)
    @retry_consume()
    def on_manual(ch, method, props, payload):
        notification_service.send_manual(
            patient_id=payload["patient_id"],
            contract_id=payload["contract_id"],
            channel=payload["channel"],
            message_id=payload["message_id"],
        )

    @retry_consume()
    def on_automated(ch, method, props, payload):
        notification_service.run_automated(clinic_id=payload["clinic_id"])

    ch.basic_consume(
        queue="notifications.manual",
        on_message_callback=on_manual,
    )
    ch.basic_consume(
        queue="notifications.automated",
        on_message_callback=on_automated,
    )

    print(" [*] Rabbit consumer iniciado. Aguardando mensagens…")
    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        print(" [*] Rabbit consumer interrompido pelo usuário.")
        ch.close()

if __name__ == "__main__":
    run()
