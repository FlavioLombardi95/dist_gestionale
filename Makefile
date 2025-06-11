# 🔧 Makefile - Sistema Messaggi Vestiaire
# Comandi rapidi per gestione e manutenzione

.PHONY: help maintenance setup dev deploy clean test stats push

# Colori per output
BLUE=\033[0;34m
GREEN=\033[0;32m
YELLOW=\033[1;33m
RED=\033[0;31m
NC=\033[0m # No Color

help: ## 📋 Mostra tutti i comandi disponibili
	@echo "$(BLUE)🔧 SISTEMA MESSAGGI VESTIAIRE - Comandi Disponibili$(NC)"
	@echo "=================================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)💡 Esempi d'uso:$(NC)"
	@echo "  make maintenance  # Manutenzione completa"
	@echo "  make dev         # Avvia sviluppo locale"
	@echo "  make deploy      # Deploy completo"

maintenance: ## 🔧 Esegue manutenzione completa del sistema
	@echo "$(BLUE)🔧 Avvio manutenzione sistema...$(NC)"
	@./scripts/maintenance.sh

setup: ## 📦 Setup iniziale - installa dipendenze
	@echo "$(BLUE)📦 Setup iniziale...$(NC)"
	@pip install -r requirements.txt
	@echo "$(GREEN)✅ Setup completato!$(NC)"

dev: ## 🚀 Avvia server di sviluppo locale (porta 3000)
	@echo "$(BLUE)🚀 Avvio server di sviluppo...$(NC)"
	@echo "$(YELLOW)💡 Applicazione disponibile su: http://localhost:3000$(NC)"
	@PORT=3000 python3 app.py

deploy: maintenance ## 🚀 Deploy completo (manutenzione + push)
	@echo "$(BLUE)🚀 Avvio deploy completo...$(NC)"
	@git add -A
	@git commit -m "🚀 DEPLOY: Sistema aggiornato - $(shell date '+%Y-%m-%d %H:%M')" || echo "Nessun cambiamento da committare"
	@git push
	@echo "$(GREEN)✅ Deploy completato!$(NC)"
	@echo "$(YELLOW)🌐 Applicazione live: https://dist-gestionale.onrender.com/$(NC)"

clean: ## 🧹 Pulizia file temporanei
	@echo "$(BLUE)🧹 Pulizia file temporanei...$(NC)"
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name ".DS_Store" -delete 2>/dev/null || true
	@[ -f "app.log" ] && > app.log || true
	@echo "$(GREEN)✅ Pulizia completata!$(NC)"

test: ## 🧪 Test rapido sintassi e funzionalità
	@echo "$(BLUE)🧪 Test sistema...$(NC)"
	@python3 -m py_compile app.py && echo "$(GREEN)✅ Sintassi app.py OK$(NC)" || echo "$(RED)❌ Errori sintassi$(NC)"
	@python3 -c "import app; print('✅ Import app.py OK')" 2>/dev/null || echo "$(RED)❌ Errori import$(NC)"

stats: ## 📊 Mostra statistiche sistema
	@echo "$(BLUE)📊 Statistiche Sistema Messaggi Vestiaire$(NC)"
	@echo "==========================================="
	@echo "📁 File principali:"
	@[ -f "app.py" ] && echo "   - app.py: $$(wc -l < app.py) righe ($$(du -h app.py | cut -f1))" || echo "   - app.py: NON TROVATO"
	@[ -f "templates/index.html" ] && echo "   - index.html: $$(wc -l < templates/index.html) righe" || echo "   - index.html: NON TROVATO"
	@echo ""
	@echo "🎯 Status:"
	@[ -f "app.py" ] && echo "   - Sistema ottimizzato: $$([ $$(wc -l < app.py) -lt 2000 ] && echo '✅ SÌ' || echo '⚠️  DA VERIFICARE')" || echo "   - Sistema: NON DISPONIBILE"
	@echo "   - Deploy URL: https://dist-gestionale.onrender.com/"
	@echo "   - Ultima modifica: $$(git log -1 --format='%cr' 2>/dev/null || echo 'N/A')"

push: clean ## ⚡ Push rapido (pulizia + commit + push)
	@echo "$(BLUE)⚡ Push rapido...$(NC)"
	@git add -A
	@git commit -m "⚡ QUICK UPDATE: $(shell date '+%Y-%m-%d %H:%M')" || echo "Nessun cambiamento da committare"
	@git push
	@echo "$(GREEN)✅ Push completato!$(NC)"

install: ## 🛠️ Installa sistema di automazione Git
	@echo "$(BLUE)🛠️ Installazione sistema automazione...$(NC)"
	@chmod +x .git/hooks/pre-push
	@chmod +x scripts/maintenance.sh
	@echo "$(GREEN)✅ Git Hooks attivati$(NC)"
	@echo "$(GREEN)✅ Script manutenzione pronto$(NC)"
	@echo "$(YELLOW)💡 Usa 'make help' per vedere tutti i comandi$(NC)"

# Regole di default
all: maintenance

# Alias comandi
m: maintenance
d: dev
s: stats
c: clean
p: push 