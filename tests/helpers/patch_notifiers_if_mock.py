import os
from unittest.mock import patch

def patch_notifiers_if_mock():
    """
    Se MOCK_NOTIFIERS=true, patcha todos os notifiers para mock.
    """
    if os.getenv("MOCK_NOTIFIERS", "false").lower() == "true":
        patches = [
            patch("notification_billing.adapters.notifiers.email.sendgrid.SendGridEmail.send", autospec=True),
            patch("notification_billing.adapters.notifiers.sms.assertiva.AssertivaSMS.send", autospec=True),
            patch("notification_billing.adapters.notifiers.whatsapp.debtapp.DebtAppWhatsapp.send", autospec=True),
        ]
        for p in patches:
            p.start()
        return patches
    return []
