# Almaz.Silver — boshqaruv Makefile
# Ishlatish: `make <target>`. Ro'yxat: `make help`.
# Serverда ishga tushiriladi (docker compose bor joyда).

# --- Sozlanadigan (override: make <t> EMAIL=... API=...) ---
EMAIL ?= admin@almazsilver.uz
PASS  ?= admin123
PGUSER ?= almaz
PGDB   ?= almaz
DC = docker compose

# Konteyner ichida login qilib token oladigan + so'rov yuboradigan python snippet.
# Login muvaffaqiyatsiz bo'lsa aniq xabar beradi (parol boshqa bo'lsa: make <t> EMAIL=... PASS=...)
define API_PY
$(DC) exec -T api python -c "import httpx,sys,json; b='http://localhost:8000'; \
r=httpx.post(b+'/auth/login',json={'email':'$(EMAIL)','password':'$(PASS)'},timeout=15); \
t=r.json().get('access_token'); \
sys.exit('LOGIN XATO ('+str(r.status_code)+'): admin parol boshqami? -> make <target> EMAIL=... PASS=...') if not t else None; \
h={'Authorization':'Bearer '+t}; $(1)"
endef

.DEFAULT_GOAL := help

# ==================== Yordam ====================
.PHONY: help
help: ## Barcha komandalar ro'yxati
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	 | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ==================== Hayotiy sikl ====================
.PHONY: up down restart build rebuild ps logs logs-api logs-worker
up: ## Servislarni ko'tarish (build + migratsiya + seed avtomatik)
	$(DC) up -d --build
down: ## To'xtatish
	$(DC) down
restart: ## Qayta ishga tushirish
	$(DC) restart
build: ## Image qurish
	$(DC) build
rebuild: ## Qayta qurish + ko'tarish
	$(DC) up -d --build --force-recreate
ps: ## Servislar holati
	$(DC) ps
logs: ## Hamma loglar (kuzatish)
	$(DC) logs -f --tail=100
logs-api: ## Faqat API loglari
	$(DC) logs -f --tail=100 api
logs-worker: ## Celery worker loglari
	$(DC) logs -f --tail=100 worker

# ==================== Migratsiya / seed / shell ====================
.PHONY: migrate seed demo-seed seed-integrations shell psql redis-cli
migrate: ## alembic upgrade head
	$(DC) exec -T api alembic upgrade head
seed: ## Asosiy seed (rol/permission/settings/admin)
	$(DC) exec -T api python -m app.seed
demo-seed: ## Demo ma'lumot (12 mahsulot, 7 buyurtma, ...)
	$(DC) exec -T api python -m app.demo_seed
seed-integrations: ## Integration config qatorlarini yaratish (placeholder)
	$(DC) exec -T api python -m app.seed_integrations
shell: ## API konteyner ichiga bash
	$(DC) exec api bash
psql: ## PostgreSQL psql
	$(DC) exec postgres psql -U $(PGUSER) -d $(PGDB)
redis-cli: ## Redis CLI
	$(DC) exec redis redis-cli

# ==================== Health ====================
.PHONY: health ready
health: ## /health
	$(DC) exec -T api python -c "import httpx;print(httpx.get('http://localhost:8000/health').json())"
ready: ## /health/ready (DB+Redis)
	$(DC) exec -T api python -c "import httpx;print(httpx.get('http://localhost:8000/health/ready').json())"

# ==================== Integration configlar ====================
.PHONY: integrations ig-config tg-config
integrations: ## Barcha integration_config (DB)
	$(DC) exec -T postgres psql -U $(PGUSER) -d $(PGDB) -c \
	 "SELECT provider,key,left(coalesce(value,''),16) AS value_head,is_active FROM integration_config ORDER BY provider,key;"
ig-config: ## Instagram configlar (token sozlanganmi?)
	$(DC) exec -T postgres psql -U $(PGUSER) -d $(PGDB) -c \
	 "SELECT key,left(coalesce(value,''),18) AS value_head,is_active,updated_at FROM integration_config WHERE provider='instagram' ORDER BY key;"
tg-config: ## Telegram configlar
	$(DC) exec -T postgres psql -U $(PGUSER) -d $(PGDB) -c \
	 "SELECT key,left(coalesce(value,''),18) AS value_head,is_active FROM integration_config WHERE provider='telegram' ORDER BY key;"

# ==================== Webhook eventlar (Meta/Telegram nima yuborgan) ====================
.PHONY: events ig-events tg-events ig-events-raw
events: ## Oxirgi 15 webhook event (hamma)
	$(DC) exec -T postgres psql -U $(PGUSER) -d $(PGDB) -c \
	 "SELECT created_at,provider,status,coalesce(note,'') FROM integration_event ORDER BY created_at DESC LIMIT 15;"
ig-events: ## Instagram eventlar — Meta umuman yuboryaptimi? (BO'SH bo'lsa muammo Meta tomonда)
	$(DC) exec -T postgres psql -U $(PGUSER) -d $(PGDB) -c \
	 "SELECT created_at,status,left(raw::text,120) AS raw_head FROM integration_event WHERE provider='instagram' ORDER BY created_at DESC LIMIT 10;"
ig-events-raw: ## Oxirgi Instagram event to'liq JSON (parse muammosini ko'rish)
	$(DC) exec -T postgres psql -U $(PGUSER) -d $(PGDB) -t -c \
	 "SELECT jsonb_pretty(raw) FROM integration_event WHERE provider='instagram' ORDER BY created_at DESC LIMIT 1;"
tg-events: ## Telegram eventlar
	$(DC) exec -T postgres psql -U $(PGUSER) -d $(PGDB) -c \
	 "SELECT created_at,status,left(raw::text,120) FROM integration_event WHERE provider='telegram' ORDER BY created_at DESC LIMIT 10;"

# ==================== To'liq self-test ====================
.PHONY: test-webhooks
test-webhooks: ## TG+IG to'liq test (config + ulanish + imzolangan POST -> ingest)
	$(DC) exec -T api python -m app.webhook_selftest

# ==================== Instagram webhook debug ====================
.PHONY: ig-verify ig-subscribe ig-check
ig-verify: ## GET verify handshake'ni LOKAL sinash (verify_token DB'dan) — challenge qaytishi kerak
	@$(call API_PY,\
	 vt=httpx.get(b+'/integrations/configs',params={'provider':'instagram'},headers=h,timeout=15).json(); \
	 tok=next((x['value'] for x in vt['items'] if x['key']=='verify_token'),None); \
	 print('verify_token(DB):', (tok or 'YO\'Q — avval sozlang!')[:20]); \
	 r=httpx.get(b+'/webhooks/instagram',params={'hub.mode':'subscribe','hub.verify_token':tok,'hub.challenge':'TEST123'},timeout=15); \
	 print('handshake:', r.status_code, repr(r.text), '-> OK' if r.text=='TEST123' else '-> XATO (verify_token mos emas)'))
ig-subscribe: ## Akkauntni webhook eventlariga obuna qilish (me/subscribed_apps) — MAJBURIY qadam
	@$(call API_PY,print('subscribe:', httpx.post(b+'/integrations/instagram/subscribe',headers=h,timeout=30).json()))
ig-check: ig-config ig-events ## Instagram to'liq tekshiruv (config + eventlar + maslahat)
	@echo ""
	@echo "── Tekshiruv tartibi ──────────────────────────────────────"
	@echo "1) ig-config: access_token / verify_token / app_secret sozlanganmi?"
	@echo "2) ig-events: BO'SH bo'lsa -> Meta hech narsa yubormayapti:"
	@echo "     - Meta konsolда Callback URL = https://<domen>/webhooks/instagram ?"
	@echo "     - Verify token DB'dagi bilan bir xilmi? (make ig-verify)"
	@echo "     - Obuna qilinganmi? (make ig-subscribe)  <-- ko'p unutiladi"
	@echo "3) ig-events'да status='received' bor, lekin xabar ishlanmasa -> make ig-events-raw"
	@echo "     (is_echo bo'lsa e'tiborsiz; graph.instagram.com token to'g'rimi?)"

# ==================== Telegram webhook ====================
.PHONY: tg-info tg-me tg-set-webhook tg-delete-webhook
tg-info: ## Telegram getWebhookInfo (ulanganmi, oxirgi xato)
	@$(call API_PY,print(json.dumps(httpx.get(b+'/integrations/telegram/webhook-info',headers=h,timeout=15).json(),indent=2,ensure_ascii=False)))
tg-me: ## Qaysi bot ulangan (getMe)
	@$(call API_PY,print(httpx.get(b+'/integrations/telegram/me',headers=h,timeout=15).json()))
tg-set-webhook: ## Webhook o'rnatish: make tg-set-webhook URL=https://<domen>/webhooks/telegram
	@$(call API_PY,print(httpx.post(b+'/integrations/telegram/set-webhook',headers=h,json={'url':'$(URL)'},timeout=15).json()))
tg-delete-webhook: ## Webhook o'chirish
	@$(call API_PY,print(httpx.post(b+'/integrations/telegram/delete-webhook',headers=h,timeout=15).json()))
