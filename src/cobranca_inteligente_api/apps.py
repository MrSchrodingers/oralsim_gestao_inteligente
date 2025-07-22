from django.apps import AppConfig


class BillingConfig(AppConfig):
    name = "cobranca_inteligente_api"
    verbose_name = "Cobranca Inteligente API"

    def ready(self):
        from django.conf import settings

        # ─── DI containers ──────────────────────────────────────────
        from oralsin_core.adapters.config.composition_root import (
            setup_di_container_from_settings as build_core_container,
        )

        from cordial_billing.adapters.config.composition_root import (
            setup_di_container_from_settings as build_cb_container,
        )
        from notification_billing.adapters.config.composition_root import (
            setup_di_container_from_settings as build_nb_container,
        )

        core_container = build_core_container(settings)
        _nb_container   = build_nb_container(settings)
        _cb_container   = build_cb_container(settings)

        # ─── Registra handlers extras ───────────────────────────────
        from oralsin_core.core.application.queries.dashboard_queries import (
            GetDashboardSummaryQuery,
        )
        from oralsin_core.core.application.services.utils.fonts import register_roboto_family
        register_roboto_family()
        import notification_billing.adapters.message_broker.oralsin_contact_history_publisher  # noqa: F401

        core_container.query_bus().register(
            GetDashboardSummaryQuery,
            core_container.dashboard_handler(),
        )
