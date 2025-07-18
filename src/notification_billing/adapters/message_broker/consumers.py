from django.conf import settings

from notification_billing.adapters.config.composition_root import setup_di_container_from_settings
from notification_billing.adapters.message_broker.rabbitmq import RabbitMQ, retry_consume
from notification_billing.core.application.services.notification_service import NotificationFacadeService


def start_consuming():
    setup_di_container_from_settings(settings)
    
    from notification_billing.adapters.config.composition_root import container
    rabbit: RabbitMQ = container.rabbit()
    notification_service: NotificationFacadeService = container.notification_service()

    # 1) declara exchanges e DLX
    rabbit.declare_exchange("notifications", dlx="notifications.dlx")
    rabbit.declare_exchange("notifications.dlx", exchange_type="fanout")

    # 2) declara e vincula filas
    # filas
    rabbit.declare_queue("notifications.manual", dlx="notifications.dlx")
    rabbit.bind_queue("notifications.manual", "notifications", "manual")
    rabbit.declare_queue("notifications.automated", dlx="notifications.dlx")
    rabbit.bind_queue("notifications.automated", "notifications", "automated")
    # cada mensagem = 1 agendamento
    rabbit.declare_queue("notifications.schedule", dlx="notifications.dlx")
    rabbit.bind_queue("notifications.schedule", "notifications", "schedule")

    ch = rabbit.channel()

    # 3) consumidor de envios manuais
    @retry_consume(queue="notifications.manual")
    def on_manual(ch, method, props, payload):
        notification_service.send_manual(
            patient_id=payload["patient_id"],
            contract_id=payload["contract_id"],
            channel=payload["channel"],
            message_id=payload["message_id"],
        )
        # opcional: log, métrica, etc.

    # 4) consumidor de envios automáticos
    @retry_consume(queue="notifications.automated")
    def on_automated(ch, method, props, payload):
        notification_service.enqueue_pending_schedules(clinic_id=payload["clinic_id"])

    @retry_consume(queue="notifications.schedule")
    def on_schedule(ch, method, props, payload):
        notification_service.process_single_schedule(schedule_id=payload["schedule_id"])
        
    ch.basic_consume(queue="notifications.manual", on_message_callback=on_manual)
    ch.basic_consume(queue="notifications.automated", on_message_callback=on_automated)
    ch.basic_consume(
        queue="notifications.schedule",
        on_message_callback=on_schedule,
    )

    ch.start_consuming()

if __name__ == "__main__":
    start_consuming()