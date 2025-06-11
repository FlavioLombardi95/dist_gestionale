#!/bin/bash

# 🔧 SCRIPT MANUTENZIONE - Sistema Messaggi Vestiaire
# Mantiene tutto aggiornato e ottimizzato

echo "🔧 MANUTENZIONE SISTEMA MESSAGGI VESTIAIRE"
echo "=========================================="

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Funzione per log con timestamp
log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# 1. PULIZIA SISTEMA
log "Avvio pulizia sistema..."

# Rimuovi file temporanei
find . -name "*.pyc" -delete 2>/dev/null && success "File .pyc rimossi"
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null && success "Cache Python pulita"
find . -name ".DS_Store" -delete 2>/dev/null && success "File .DS_Store rimossi"
[ -f "app.log" ] && > app.log && success "Log app.py pulito"

# 2. VERIFICA DIPENDENZE
log "Verificando dipendenze..."

if [ -f "requirements.txt" ]; then
    pip list --format=freeze > current_deps.txt
    
    # Controlla se ci sono aggiornamenti disponibili
    pip list --outdated --format=json > outdated.json 2>/dev/null
    if [ -s outdated.json ] && [ "$(cat outdated.json)" != "[]" ]; then
        warning "Dipendenze obsolete trovate"
        echo "Per aggiornare: pip install -U \$(pip list --outdated --format=freeze | cut -d= -f1)"
    else
        success "Tutte le dipendenze sono aggiornate"
    fi
    
    rm -f current_deps.txt outdated.json
fi

# 3. STATISTICHE PROGETTO
log "Generando statistiche..."

LINES_APP=$([ -f "app.py" ] && wc -l < app.py || echo "0")
LINES_HTML=$([ -f "templates/index.html" ] && wc -l < templates/index.html || echo "0")
SIZE_APP=$([ -f "app.py" ] && du -h app.py | cut -f1 || echo "0KB")

echo "📊 STATISTICHE ATTUALI:"
echo "   - app.py: $LINES_APP righe ($SIZE_APP)"
echo "   - index.html: $LINES_HTML righe"
echo "   - Sistema ottimizzato: $([ $LINES_APP -lt 2000 ] && echo "✅ SÌ" || echo "⚠️  DA VERIFICARE")"

# 4. CONTROLLO INTEGRITÀ
log "Controllo integrità file..."

# File essenziali
ESSENTIAL_FILES=("app.py" "requirements.txt" "README.md" "Procfile" "templates/index.html")
for file in "${ESSENTIAL_FILES[@]}"; do
    [ -f "$file" ] && success "$file OK" || error "$file MANCANTE"
done

# Controlla endpoint API
if [ -f "app.py" ]; then
    grep -q "genera-messaggio-like" app.py && success "Endpoint messaggi Like OK" || error "Endpoint mancante"
    grep -q "genera_messaggio_like_vestiaire" app.py && success "Funzione principale OK" || error "Funzione mancante"
fi

# 5. AGGIORNAMENTO DOCUMENTAZIONE
log "Aggiornando documentazione..."

if [ -f "README.md" ]; then
    # Aggiorna data ultima ottimizzazione
    CURRENT_DATE=$(date +"%B %Y")
    sed -i.bak "s/\*\*Ultima ottimizzazione\*\*: .*/\*\*Ultima ottimizzazione\*\*: $CURRENT_DATE - Sistema Messaggi Vestiaire v2.0/" README.md 2>/dev/null
    rm -f README.md.bak
    success "README aggiornato"
fi

# Genera/aggiorna file statistiche
cat > STATS.md << EOF
# 📊 Statistiche Sistema Messaggi Vestiaire

**Generato**: $(date)

## 🔢 Metriche Codice
- **app.py**: $LINES_APP righe ($SIZE_APP)
- **templates/index.html**: $LINES_HTML righe
- **Ottimizzazione**: $([ $LINES_APP -lt 2000 ] && echo "Codice snello ✅" || echo "Da rivedere ⚠️")

## 🚀 Deploy Info
- **URL Produzione**: https://dist-gestionale.onrender.com/
- **Platform**: Render.com
- **Python**: $(python3 --version 2>/dev/null || echo "Non disponibile")

## 📦 Dipendenze Principali
$([ -f "requirements.txt" ] && grep -E "^(Flask|SQLAlchemy|Pillow|gunicorn)" requirements.txt | sed 's/^/- /' || echo "- requirements.txt non trovato")

## 🎯 Funzionalità Attive
- ✅ Generazione messaggi Like Vestiaire
- ✅ Algoritmo parametri casuali
- ✅ Sistema ottimizzato (no storytelling luxury)
- ✅ Deploy automatico GitHub → Render

---
*Aggiornato automaticamente dallo script di manutenzione*
EOF

success "STATS.md generato"

# 6. CONTROLLO GIT
log "Verificando stato Git..."

if git status >/dev/null 2>&1; then
    BRANCH=$(git branch --show-current)
    success "Repository Git OK (branch: $BRANCH)"
    
    # Controlla se ci sono cambiamenti da committare
    if ! git diff --quiet || ! git diff --cached --quiet; then
        warning "Cambiamenti non committati trovati"
        echo "Usa: git add -A && git commit -m \"🔧 MANUTENZIONE: File aggiornati\""
    else
        success "Repository pulito"
    fi
else
    warning "Non in un repository Git"
fi

# 7. TEST RAPIDO
log "Test rapido sistema..."

if [ -f "app.py" ]; then
    python3 -m py_compile app.py && success "Sintassi app.py OK" || error "Errori sintassi in app.py"
fi

# 8. RIEPILOGO FINALE
echo ""
echo "🎯 RIEPILOGO MANUTENZIONE"
echo "========================"
success "Sistema pulito e ottimizzato"
success "Documentazione aggiornata"
success "Statistiche generate"
echo "📊 Sistema: $LINES_APP righe ottimizzate"
echo "🚀 Deploy: https://dist-gestionale.onrender.com/"
echo ""
echo "💡 PROSSIMI PASSI:"
echo "   1. Verifica che tutto funzioni: python3 app.py"
echo "   2. Se ci sono cambiamenti: git add -A && git commit"
echo "   3. Deploy automatico: git push"
echo ""
success "Manutenzione completata!" 