# ------------------------------------------------------------
# Variáveis reutilizáveis
# ------------------------------------------------------------
COMPOSE      := cd .. && docker compose
APP_SERVICE  := app
MANAGE       := $(COMPOSE) exec $(APP_SERVICE) python manage.py
TIME_ECHO    := @echo "✅ Concluído às $$(date '+%H:%M:%S')"

# ------------------------------------------------------------
# Alvos auxiliares
# ------------------------------------------------------------
.PHONY: help rebuild-app seed-complete test-notifications rebuild-all

help:
	@echo ""
	@echo "Alvos disponíveis:"
	@echo "  rebuild-app        → Reconstrói somente o serviço 'app' e aplica migrações"
	@echo "  seed-complete      → Execução de todos os seeds (flow cfg, messages, dados, schedules…)"
	@echo "  test-notifications → Roda testes de notificação (modo real, sem mocks)"
	@echo "  rebuild-all        → Derruba tudo, remove volumes e sobe do zero (build completo)"
	@echo "  sync-old-debts     → Sincroniza dívidas com due_date > 90 dias e busca pacientes no Pipeboard"
	@echo ""

# ------------------------------------------------------------
# 1) Reconstruir apenas o container 'app'
# ------------------------------------------------------------
rebuild-app:
	clear
	$(COMPOSE) up -d --build --no-deps --force-recreate --remove-orphans $(APP_SERVICE)
	$(TIME_ECHO)

# ------------------------------------------------------------
# 2) Seed completo do ambiente (usa rebuild-app como pré‐requisito)
# ------------------------------------------------------------
seed-complete:
	$(MANAGE) seed_flow_step_config
	$(MANAGE) seed_messages
	$(MANAGE) seed_data --admin-email matheus@admin.com --admin-pass matheus@admin 
	$(TIME_ECHO)

# ------------------------------------------------------------
# 3) Teste de notificações (modo real, sem mocks)
# ------------------------------------------------------------
test-notifications:
	$(COMPOSE) exec \
		-e REAL_NOTIFIER_FLOW=true \
		-e MOCK_NOTIFIERS=false \
		$(APP_SERVICE) \
		python manage.py test --pattern="test_notifications.py" --verbosity=2
	$(TIME_ECHO)

# ------------------------------------------------------------
# 4) Rebuild completo (derruba, limpa volumes e recompila tudo)
# ------------------------------------------------------------
rebuild-all:
	clear
	$(COMPOSE) down --volumes --remove-orphans || true 
	$(COMPOSE) up -d --build

# ------------------------------------------------------------
# 5) Sincronizar dívidas antigas para a clínica 47
# ------------------------------------------------------------
sync-old-debts:
	$(MANAGE) sync_old_debts --clinic-id 2
	@echo "✅ Executado às $$(date '+%H:%M:%S')"
