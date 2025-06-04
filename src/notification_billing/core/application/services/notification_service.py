from notification_billing.core.application.commands.notification_commands import RunAutomatedNotificationsCommand, SendManualNotificationCommand
from notification_billing.core.application.cqrs import CommandBus, QueryBus


class NotificationFacadeService:
    def __init__(
        self,
        command_bus: CommandBus,
        query_bus: QueryBus,
    ) -> None:
        self.commands = command_bus
        self.queries = query_bus

    def send_manual(
        self,
        patient_id: str,
        contract_id: str,
        channel: str,
        message_id: str,
    ) -> None:
        cmd = SendManualNotificationCommand(
            patient_id=patient_id,
            contract_id=contract_id,
            channel=channel,
            message_id=message_id,
        )
        self.commands.dispatch(cmd)

    def run_automated(self, clinic_id: str, batch_size: int = 10) -> None:
        cmd = RunAutomatedNotificationsCommand(
            clinic_id=clinic_id,
            batch_size=batch_size,
        )
        self.commands.dispatch(cmd)
