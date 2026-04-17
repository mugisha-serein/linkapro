from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    _initialized = False

    def ready(self):
        """
        CROSS-CUTTING INITIALIZATION ENTRYPOINT

        PURPOSE:
        - Wire runtime hooks
        - Register signals
        - Initialize event subscriptions
        - Avoid business logic execution
        """

        # Prevent duplicate initialization (important in dev server reloads)
        if CoreConfig._initialized:
            return

        CoreConfig._initialized = True

        # -----------------------------
        # 1. Register domain signals
        # -----------------------------
        self._register_signals()

        # -----------------------------
        # 2. Initialize event system
        # -----------------------------
        self._init_event_bus()

        # -----------------------------
        # 3. Optional: warm container
        # -----------------------------
        self._warm_container()

        # -----------------------------
        # 4. Observability setup
        # -----------------------------
        self._init_logging()

    # -----------------------------
    # INTERNAL BOOTSTRAP METHODS
    # -----------------------------

    def _register_signals(self):
        import core.signals.user_signals
        import core.signals.auth_signals

    def _init_event_bus(self):
        """
        Initialize domain event subscriptions.
        (No business logic, only wiring)
        """
        from infrastructure.events.event_bus import EventBus
        from infrastructure.events.subscribers import register_subscribers

        bus = EventBus.get_instance()
        register_subscribers(bus)

    def _warm_container(self):
        """
        OPTIONAL: preload DI container for faster first request
        """
        from cross_cutting.container import Container

        self.container = Container.default()

    def _init_logging(self):
        """
        Attach audit/security logging hooks.
        """
        import logging

        logger = logging.getLogger("security")
        logger.info("Security subsystem initialized")