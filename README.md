# 💬 Sistema Messaggi Vestiaire - Gestionale Articoli Luxury

Sistema intelligente per generare messaggi diretti personalizzati da inviare agli utenti che mettono "like" sui prodotti del tuo store Vestiaire. Ottimizzato per convertire interesse in vendite attraverso comunicazione naturale e personalizzata.

## 🎯 Funzionalità Principali

- **Generazione Messaggi Like**: Crea messaggi diretti naturali per utenti che mettono like sui prodotti
- **Algoritmo Parametri Casuali**: Utilizza automaticamente 2-3 parametri diversi per ogni messaggio (colore, materiale, keywords, vintage, target)
- **150+ Variazioni**: Sistema con oltre 150 combinazioni possibili per massima naturalezza
- **Accordi Grammaticali**: Gestione automatica maschio/femmina
- **Interfaccia Semplificata**: Focus esclusivo sui messaggi Like, zero distrazioni

## 🚀 Deploy Live

**Applicazione attiva su**: https://dist-gestionale.onrender.com/

## ⚡ Uso Rapido

1. **Accedi all'applicazione** tramite il link sopra
2. **Compila i dati del prodotto** (brand, tipo, colore, materiale, etc.)
3. **Click su "Messaggio Like"** per generare il messaggio personalizzato
4. **Copia e invia** il messaggio all'utente che ha messo like

## 🛠️ Installazione Locale

### Prerequisiti
- Python 3.8+
- pip (gestore pacchetti Python)

### Setup Rapido
```bash
# Clona il repository
git clone [URL_REPOSITORY]

# Installa le dipendenze
pip install -r requirements.txt

# Avvia l'applicazione
PORT=3000 python3 app.py
```

L'applicazione sarà disponibile su: http://localhost:3000

## 📦 Dipendenze Principali

- **Flask 2.3.3**: Framework web leggero
- **SQLAlchemy 3.0.5**: ORM per database
- **Pillow 10.2.0**: Gestione immagini
- **Gunicorn 21.2.0**: Server WSGI per produzione

## 🏗️ Architettura

```
├── app.py                 # Applicazione Flask principale (1800 righe ottimizzate)
├── templates/
│   └── index.html         # Interfaccia utente responsive
├── static/               # Assets statici (CSS, JS, immagini)
├── requirements.txt      # Dipendenze Python
├── Procfile             # Configurazione deploy Render
└── gunicorn_config.py   # Configurazione server produzione
```

## 🎨 Esempi di Messaggi Generati

- *"Ciao! Ho notato il tuo interesse per questa Prada vintage in pelle nera. È un pezzo davvero speciale e raro, difficile da trovare in queste condizioni. Per ringraziarti del like, ti sto preparando un'offerta esclusiva!"*

- *"Ciao! Vedo che ti piace questa Gucci in canvas beige - ottima scelta! È un modello iconico in condizioni eccellenti, ne abbiamo solo una. Ti invio subito un'offerta speciale riservata solo a te!"*

## 🔄 Funzionalità Algoritmo

### Selezione Parametri Casuali
- **2-3 parametri** selezionati automaticamente per ogni messaggio
- **Varietà massima**: ogni messaggio è unico
- **Naturalezza**: evita ripetizioni meccaniche

### Pattern Messaggio
- **7 strutture diverse** di messaggio
- **Ringraziamento personalizzato** per il like
- **Creazione urgenza** (pezzi unici, scorte limitate)
- **Call-to-action** per offerte esclusive

## 📊 Ottimizzazioni Recenti

- ✅ **Codice ridotto del 20%** (da 2250 a 1800 righe)
- ✅ **Rimosso sistema storytelling luxury** non utilizzato
- ✅ **Focus esclusivo messaggi Like**
- ✅ **Performance migliorate**
- ✅ **Zero codice ridondante**

## 🚀 Deploy e Produzione

### Render.com (Attuale)
- **Deploy automatico** da git push
- **URL produzione**: https://dist-gestionale.onrender.com/
- **Configurazione**: `Procfile` + `gunicorn_config.py`

### Variabili Ambiente
```bash
DATABASE_URL=sqlite:///instance/gestionale.db  # Locale
# DATABASE_URL=postgresql://...                # Produzione (se necessario)
```

## 🔧 Sviluppo

### Struttura Codice Principale
- `genera_messaggio_like_vestiaire()`: Algoritmo principale messaggi
- `crea_descrizione_avanzata()`: Generazione descrizioni naturali
- `crea_ringraziamento_like()`: Pattern ringraziamenti
- `crea_offerta_personalizzata()`: Generazione offerte

### API Endpoints
- `GET /`: Interfaccia principale
- `POST /api/genera-messaggio-like/<id>`: Genera messaggio per prodotto

## 📈 Conversioni e Risultati

Il sistema è progettato per:
- ✅ **Convertire like in interesse attivo**
- ✅ **Personalizzare ogni comunicazione**
- ✅ **Creare urgenza e scarsità**
- ✅ **Mantenere tone of voice naturale**
- ✅ **Ottimizzare tasso di risposta**

## 🛡️ Sicurezza e Privacy

- **Database locale SQLite** per sviluppo
- **Sessioni sicure** Flask
- **Validazione input** su tutti i campi
- **No dati sensibili** in repository

## 🆘 Support

Per supporto, miglioramenti o bug report, contatta lo sviluppatore.

---

**Ultima ottimizzazione**: June 2025 - Sistema Messaggi Vestiaire v2.0