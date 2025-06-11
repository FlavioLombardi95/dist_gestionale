from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
import random
import re
import logging
from functools import wraps, lru_cache
from typing import Dict, List, Optional, Tuple
import time

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ===============================
# CONFIGURAZIONE DATABASE
# ===============================

def configure_database():
    """Configura la connessione al database"""
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if DATABASE_URL:
        # Produzione: Supabase PostgreSQL
        if 'supabase.co' in DATABASE_URL and 'sslmode' not in DATABASE_URL:
            DATABASE_URL += '?sslmode=require'
        
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 10,
            'max_overflow': 20,
            'connect_args': {'sslmode': 'require'}
        }
        logger.info("🔗 Connesso a Supabase PostgreSQL")
    else:
        # Sviluppo: SQLite locale
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gestionale.db'
        logger.info("🔗 Usando SQLite locale per sviluppo")

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'static/uploads'

configure_database()
db = SQLAlchemy(app)

# Assicura che la cartella uploads esista
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ===============================
# MODELLI DATABASE
# ===============================

class Articolo(db.Model):
    """Modello per gli articoli di lusso"""
    
    __tablename__ = 'articoli'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, index=True)
    brand = db.Column(db.String(100), nullable=False, index=True)
    immagine = db.Column(db.String(200))
    colore = db.Column(db.String(50))
    materiale = db.Column(db.String(100))
    keywords = db.Column(db.Text)
    termini_commerciali = db.Column(db.Text)
    condizioni = db.Column(db.String(50), index=True)
    rarita = db.Column(db.String(50), index=True)
    vintage = db.Column(db.Boolean, default=False, index=True)
    target = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Articolo {self.nome} - {self.brand}>'

    def to_dict(self) -> Dict:
        """Converte l'articolo in dizionario per JSON"""
        return {
            'id': self.id,
            'nome': self.nome,
            'brand': self.brand,
            'immagine': self.immagine,
            'colore': self.colore or '',
            'materiale': self.materiale or '',
            'keywords': self._parse_keywords(),
            'termini_commerciali': self._parse_termini_commerciali(),
            'condizioni': self.condizioni or '',
            'rarita': self.rarita or '',
            'vintage': self.vintage or False,
            'target': self.target or '',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def _parse_keywords(self) -> List[str]:
        """Parsifica le keywords in lista"""
        if not self.keywords:
            return []
        return [kw.strip() for kw in self.keywords.split(',') if kw.strip()]

    def _parse_termini_commerciali(self) -> List[str]:
        """Parsifica i termini commerciali in lista"""
        if not self.termini_commerciali:
            return []
        return [term.strip() for term in self.termini_commerciali.split(',') if term.strip()]

    @staticmethod
    def validate_data(data: Dict) -> Tuple[bool, List[str]]:
        """Valida i dati dell'articolo"""
        errors = []
        
        if not data.get('nome', '').strip():
            errors.append('Nome articolo obbligatorio')
        
        if not data.get('brand', '').strip():
            errors.append('Brand obbligatorio')
            
        if not data.get('condizioni', '').strip():
            errors.append('Condizioni obbligatorie')
            
        if not data.get('rarita', '').strip():
            errors.append('Rarità obbligatoria')
            
        # Validazione valori specifici
        valid_condizioni = ['Eccellenti', 'Ottime', 'Buone', 'Discrete']
        if data.get('condizioni') and data['condizioni'] not in valid_condizioni:
            errors.append(f'Condizioni non valide. Valori permessi: {", ".join(valid_condizioni)}')
            
        valid_rarita = ['Comune', 'Raro', 'Molto Raro', 'Introvabile']
        if data.get('rarita') and data['rarita'] not in valid_rarita:
            errors.append(f'Rarità non valida. Valori permessi: {", ".join(valid_rarita)}')
        
        return len(errors) == 0, errors

# ===============================
# DECORATORI E MIDDLEWARE
# ===============================

def handle_errors(f):
    """Decoratore per gestire errori in modo uniforme"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Errore in {f.__name__}: {str(e)}")
            return jsonify({'error': str(e)}), 500
    return decorated_function

def log_request_info(f):
    """Decoratore per loggare informazioni sulle richieste"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        result = f(*args, **kwargs)
        end_time = time.time()
        
        logger.info(f"{request.method} {request.path} - {end_time - start_time:.3f}s")
        return result
    return decorated_function

# ===============================
# INIZIALIZZAZIONE DATABASE
# ===============================

def init_database():
    """Inizializza il database"""
    with app.app_context():
        try:
            if os.environ.get('DATABASE_URL'):
                # Produzione: crea solo tabelle mancanti
                db.create_all()
                logger.info("Database di produzione inizializzato")
            else:
                # Sviluppo locale: ricrea tutto
                db.drop_all()
                db.create_all()
                logger.info("Database di sviluppo inizializzato")
        except Exception as e:
            logger.error(f"Errore nell'inizializzazione del database: {e}")
            raise

init_database()

# ===============================
# FUNZIONI HELPER OTTIMIZZATE
# ===============================

@lru_cache(maxsize=128)
def get_tipo_articolo_cached(nome: str) -> str:
    """Versione cached per riconoscere il tipo di articolo"""
    return riconosci_tipo_articolo(nome)

@lru_cache(maxsize=256)
def get_genere_cached(tipo_articolo: str) -> str:
    """Versione cached per ottenere il genere"""
    generi = {
        'borsa': 'f', 'scarpe': 'f', 'vestito': 'm', 'top': 'm',
        'pantaloni': 'm', 'giacca': 'f', 'accessorio': 'm', 'generico': 'm'
    }
    return generi.get(tipo_articolo, 'm')

def riconosci_tipo_articolo(nome: str) -> str:
    """Riconosce il tipo di articolo dal nome"""
    nome_lower = nome.lower()
    
    # Mappatura ottimizzata con più varianti
    tipo_mapping = {
        'borsa': ['borsa', 'borse', 'bag', 'clutch', 'pochette', 'zaino', 'trolley', 'valigia', 'handbag', 'bauletto', 'tracolla', 'shopping'],
        'scarpe': ['scarpa', 'scarpe', 'sandalo', 'sandali', 'boot', 'stivale', 'stivali', 'sneaker', 'decollete', 'pump', 'mocassino', 'ballerina', 'ciabatta'],
        'vestito': ['vestito', 'abito', 'dress', 'gonna', 'skirt', 'tuta', 'jumpsuit'],
        'top': ['camicia', 'shirt', 'blusa', 'top', 'maglia', 't-shirt', 'polo', 'cardigan', 'maglione', 'felpa'],
        'pantaloni': ['pantalone', 'pantaloni', 'jeans', 'short', 'bermuda', 'leggings', 'jogger'],
        'giacca': ['giacca', 'blazer', 'coat', 'cappotto', 'giubbotto', 'parka', 'trench', 'mantello'],
        'accessorio': ['accessorio', 'accessori', 'cintura', 'belt', 'sciarpa', 'foulard', 'cappello', 'guanto', 'orologio', 'gioiello', 'collana', 'bracciale', 'anello']
    }
    
    for tipo, keywords in tipo_mapping.items():
        if any(keyword in nome_lower for keyword in keywords):
            return tipo
    
    # **FALLBACK INTELLIGENTE** - Se non trova corrispondenze, cerca parole chiave nel brand/context
    # Molti articoli di lusso hanno nomi specifici senza la parola tipo
    brand_context = {
        'chanel': 'borsa',  # Chanel è famosa per borse
        'hermès': 'borsa',  # Hermès principalmente borse
        'hermes': 'borsa',
        'louis vuitton': 'borsa',  # LV principalmente borse
        'gucci': 'borsa',   # Gucci principalmente borse
        'prada': 'borsa',   # Prada principalmente borse
    }
    
    for brand, tipo_default in brand_context.items():
        if brand in nome_lower:
            return tipo_default
    
    # Se proprio non riesce a identificare, usa "borsa" come default più probabile per articoli di lusso
    return 'borsa'

@lru_cache(maxsize=512)
def classifica_keywords_cached(keywords_str: str) -> Dict[str, List[str]]:
    """Versione cached per classificare le keywords"""
    keywords = [kw.strip().lower() for kw in keywords_str.split(',') if kw.strip()]
    return classifica_keywords(keywords)

def classifica_keywords(keywords: List[str]) -> Dict[str, List[str]]:
    """Classifica le keywords in categorie semantiche"""
    if not keywords:
        return {cat: [] for cat in ['colori', 'materiali', 'stili', 'caratteristiche', 'forme', 'dettagli', 'altre']}
    
    # Definizioni ottimizzate con set per lookup O(1)
    categorie = {
        'colori': {
            'nero', 'bianco', 'rosso', 'blu', 'verde', 'giallo', 'marrone', 'beige', 'rosa', 'viola',
            'arancione', 'grigio', 'oro', 'argento', 'celeste', 'azzurro', 'bordeaux', 'navy',
            'cammello', 'ecru', 'turchese', 'corallo'
        },
        'materiali': {
            'pelle', 'tessuto', 'cotone', 'seta', 'nylon', 'lino', 'jeans', 'velluto', 'camoscio',
            'canvas', 'paglia', 'lana', 'eco-pelle', 'vernice', 'gomma', 'lycra', 'poliestere',
            'cashmere', 'raso', 'tela', 'mesh', 'suede'
        },
        'stili': {
            'elegante', 'casual', 'sportivo', 'chic', 'vintage', 'moderno', 'classico', 'trendy',
            'glamour', 'minimale', 'bohemian', 'rock', 'sofisticato', 'raffinato', 'contemporaneo',
            'femminile', 'androgino'
        },
        'caratteristiche': {
            'comodo', 'versatile', 'pratico', 'resistente', 'leggero', 'morbido', 'durevole',
            'flessibile', 'elastico', 'traspirante', 'impermeabile', 'lussuoso', 'pregiato', 'esclusivo'
        },
        'forme': {
            'ampio', 'fitted', 'aderente', 'oversize', 'slim', 'largo', 'stretto', 'lungo',
            'corto', 'mini', 'midi', 'maxi'
        },
        'dettagli': {
            'tracolla', 'zip', 'bottoni', 'borchie', 'frange', 'pizzo', 'ricami', 'stampa',
            'monogramma', 'logo', 'catena', 'fibbia', 'lacci'
        }
    }
    
    risultato = {categoria: [] for categoria in categorie.keys()}
    risultato['altre'] = []
    
    for keyword in keywords:
        categorizzato = False
        for categoria, vocabolario in categorie.items():
            if keyword in vocabolario:
                risultato[categoria].append(keyword)
                categorizzato = True
                break
        
        if not categorizzato:
            risultato['altre'].append(keyword)
    
    return risultato

def concordanza_aggettivo(aggettivo: str, genere: str) -> str:
    """Converte aggettivi al genere corretto con cache - VERSIONE CORRETTA"""
    if not aggettivo or not genere:
        return aggettivo or ""
        
    # *** CORREZIONE: Validazione input ***    
    genere = genere.lower().strip()
    if genere not in ['m', 'f']:
        genere = 'm'  # Default maschio se genere non valido
        
    aggettivo = aggettivo.strip()
    if not aggettivo:
        return ""
        
    # **MAPPATURA ESTESA** - Aggiunti tutti gli aggettivi mancanti
    concordanze = {
        'nero': {'m': 'nero', 'f': 'nera'},
        'bianco': {'m': 'bianco', 'f': 'bianca'},
        'rosso': {'m': 'rosso', 'f': 'rossa'},
        'grigio': {'m': 'grigio', 'f': 'grigia'},
        'giallo': {'m': 'giallo', 'f': 'gialla'},
        'verde': {'m': 'verde', 'f': 'verde'},  # invariabile
        'blu': {'m': 'blu', 'f': 'blu'},  # invariabile
        'rosa': {'m': 'rosa', 'f': 'rosa'},  # invariabile
        'marrone': {'m': 'marrone', 'f': 'marrone'},  # invariabile
        'viola': {'m': 'viola', 'f': 'viola'},  # invariabile
        'beige': {'m': 'beige', 'f': 'beige'},  # invariabile
        'raro': {'m': 'raro', 'f': 'rara'},
        'nuovo': {'m': 'nuovo', 'f': 'nuova'},
        'usato': {'m': 'usato', 'f': 'usata'},
        'perfetto': {'m': 'perfetto', 'f': 'perfetta'},
        'iconico': {'m': 'iconico', 'f': 'iconica'},
        'esclusivo': {'m': 'esclusivo', 'f': 'esclusiva'},
        'stupendo': {'m': 'stupendo', 'f': 'stupenda'},
        'bello': {'m': 'bello', 'f': 'bella'},
        'magnifico': {'m': 'magnifico', 'f': 'magnifica'},
        'meraviglioso': {'m': 'meraviglioso', 'f': 'meravigliosa'},
        'splendido': {'m': 'splendido', 'f': 'splendida'},
        'fantastico': {'m': 'fantastico', 'f': 'fantastica'},
        'straordinario': {'m': 'straordinario', 'f': 'straordinaria'},
        'elegante': {'m': 'elegante', 'f': 'elegante'},  # invariabile
        'raffinato': {'m': 'raffinato', 'f': 'raffinata'},
        'classico': {'m': 'classico', 'f': 'classica'},
        'moderno': {'m': 'moderno', 'f': 'moderna'},
        'vintage': {'m': 'vintage', 'f': 'vintage'},  # invariabile
        'introvabile': {'m': 'introvabile', 'f': 'introvabile'},  # invariabile
        'ricercato': {'m': 'ricercato', 'f': 'ricercata'},
        'pregiato': {'m': 'pregiato', 'f': 'pregiata'},
        'realizzato': {'m': 'realizzato', 'f': 'realizzata'},
        'classificato': {'m': 'classificato', 'f': 'classificata'},
        'conservato': {'m': 'conservato', 'f': 'conservata'},
        'tenuto': {'m': 'tenuto', 'f': 'tenuta'},
        'garantito': {'m': 'garantito', 'f': 'garantita'},
        'dorato': {'m': 'dorato', 'f': 'dorata'},  # *** AGGIUNTO ***
        'argentato': {'m': 'argentato', 'f': 'argentata'},  # *** AGGIUNTO ***
        'metallico': {'m': 'metallico', 'f': 'metallica'},  # *** AGGIUNTO ***
    }
    
    aggettivo_lower = aggettivo.lower()
    if aggettivo_lower in concordanze:
        risultato = concordanze[aggettivo_lower].get(genere, aggettivo)
        # *** CORREZIONE: Mantieni la capitalizzazione originale se necessaria ***
        if aggettivo[0].isupper() and risultato:
            return risultato[0].upper() + risultato[1:] if len(risultato) > 1 else risultato.upper()
        return risultato
    
    # *** CORREZIONE: Regole automatiche più robuste ***
    try:
        if len(aggettivo_lower) >= 2:
            if aggettivo_lower.endswith('o') and genere == 'f':
                base = aggettivo_lower[:-1] + 'a'
                return base[0].upper() + base[1:] if aggettivo[0].isupper() else base
            elif aggettivo_lower.endswith('a') and genere == 'm':
                base = aggettivo_lower[:-1] + 'o'
                return base[0].upper() + base[1:] if aggettivo[0].isupper() else base
    except (IndexError, AttributeError):
        pass
    
    # Se non riesce a convertire, ritorna l'originale
    return aggettivo



# ===============================
# SISTEMA GENERAZIONE FRASI MULTI-STILE AVANZATO CON OTTIMIZZAZIONI
# ===============================

# Cache per memorizzare frasi generate ed evitare ripetizioni
FRASE_MEMORY_CACHE = {}
SEMANTIC_VARIATIONS_CACHE = {}

# ===============================
# NUOVO ALGORITMO MESSAGGI DIRETTI VESTIAIRE
# ===============================

def genera_messaggio_like_vestiaire(brand: str, nome: str, colore: str, materiale: str, 
                                   keywords_classificate: Dict, condizioni: str, rarita: str, 
                                   vintage: bool, target: str, termini_commerciali: List[str]) -> str:
    """
    🎯 ALGORITMO MIGLIORATO - Genera messaggi diretti naturali per like Vestiaire
    Con controllo ripetizioni e interpretazione semantica avanzata
    """
    
    # 📝 ANALISI SEMANTICA AVANZATA DEL NOME
    nome_analizzato = _analizza_nome_prodotto_intelligente(nome, brand)
    tipo_articolo = nome_analizzato['tipo']
    genere = get_genere_cached(tipo_articolo)
    nome_pulito = nome_analizzato['nome_pulito']
    modello = nome_analizzato['modello']
    
    # 🎯 SELEZIONE INTELLIGENTE PARAMETRI (non casuale ma semantica)
    parametri_rilevanti = _seleziona_parametri_intelligenti(
        colore, materiale, keywords_classificate, vintage, target, 
        condizioni, rarita, brand, tipo_articolo
    )
    
    # 🔥 COSTRUZIONE COMPONENTI CON CONTROLLO RIPETIZIONI
    saluto = "Ciao"
    
    # Descrizione prodotto ottimizzata
    desc_prodotto = _costruisci_descrizione_intelligente_vestiaire(
        brand, nome_pulito, modello, colore, materiale, condizioni, rarita, 
        vintage, genere, parametri_rilevanti, keywords_classificate
    )
    
    # Altri componenti
    scarsita = _costruisci_scarsita_naturale(genere)
    ringraziamento = _costruisci_ringraziamento_like()
    offerta = _costruisci_offerta_personalizzata()
    chiusura = _costruisci_chiusura_cortese()
    
    # 🎨 PATTERN MESSAGGI MIGLIORATI con logica più naturale
    messaggi_pattern = [
        f"{saluto}, è {desc_prodotto}, {scarsita}. {ringraziamento.capitalize()} {offerta}. {chiusura.capitalize()}!",
        f"{saluto}, {desc_prodotto}, {scarsita}. {offerta.capitalize()} {ringraziamento}!",
        f"{saluto}, è {desc_prodotto} e {scarsita}. {ringraziamento.capitalize()}, {offerta}. {chiusura.capitalize()}!",
        f"{saluto}, {desc_prodotto}, {scarsita}. {offerta.capitalize()}, {ringraziamento}!",
        f"{saluto}, è {desc_prodotto}, {scarsita}. {ringraziamento.capitalize()}, {offerta}!",
        f"{saluto}, {desc_prodotto} e {scarsita}. {offerta.capitalize()} {ringraziamento}!"
    ]
    
    messaggio = random.choice(messaggi_pattern)
    
    # Pulizia finale migliorata
    messaggio = _pulisci_messaggio_vestiaire_migliorato(messaggio, brand, nome_pulito)
    
    return messaggio

def _analizza_nome_prodotto_intelligente(nome: str, brand: str) -> Dict[str, str]:
    """🧠 ANALISI INTELLIGENTE del nome prodotto per evitare ripetizioni"""
    
    if not nome:
        return {
            'tipo': 'articolo',
            'nome_pulito': '',
            'modello': '',
            'brand_nel_nome': False
        }
    
    nome_lower = nome.lower()
    brand_lower = brand.lower()
    
    # 🔍 RIMUOVI BRAND DAL NOME se presente
    nome_senza_brand = nome
    brand_nel_nome = brand_lower in nome_lower
    
    if brand_nel_nome:
        # Rimuovi brand in tutte le sue forme
        nome_senza_brand = re.sub(rf'\b{re.escape(brand_lower)}\b', '', nome_lower, flags=re.IGNORECASE)
        nome_senza_brand = re.sub(r'\s+', ' ', nome_senza_brand).strip()
    
    # 🎯 IDENTIFICA TIPO ARTICOLO
    tipo_articolo = get_tipo_articolo_cached(nome)
    
    # 🧹 PULISCI NOME DA TIPO ARTICOLO
    nome_pulito = nome_senza_brand
    tipo_variants = [
        tipo_articolo, tipo_articolo + 's', tipo_articolo + 'e', 
        tipo_articolo.capitalize(), tipo_articolo.upper()
    ]
    
    for variant in tipo_variants:
        nome_pulito = re.sub(rf'\b{re.escape(variant)}\b', '', nome_pulito, flags=re.IGNORECASE)
    
    nome_pulito = re.sub(r'\s+', ' ', nome_pulito).strip()
    nome_pulito = re.sub(r'^[-\s:]+|[-\s:]+$', '', nome_pulito)
    
    # 🏷️ IDENTIFICA MODELLO (quello che rimane)
    modello = nome_pulito if nome_pulito and len(nome_pulito) > 2 else ''
    
    return {
        'tipo': tipo_articolo,
        'nome_pulito': nome_pulito,
        'modello': modello,
        'brand_nel_nome': brand_nel_nome
    }

def _seleziona_parametri_intelligenti(colore: str, materiale: str, keywords_classificate: Dict, 
                                    vintage: bool, target: str, condizioni: str, rarita: str,
                                    brand: str, tipo_articolo: str) -> Dict[str, any]:
    """🎯 SELEZIONE INTELLIGENTE dei parametri più rilevanti"""
    
    parametri = {
        'colore': None,
        'materiale': None,
        'keywords_rilevanti': [],
        'vintage': False,
        'target': None,
        'priorita_condizioni': 0,
        'priorita_rarita': 0
    }
    
    # 🎨 COLORE: Sempre rilevante se presente
    if colore and colore.strip():
        parametri['colore'] = colore.strip()
    
    # 🧵 MATERIALE: Sempre rilevante se presente
    if materiale and materiale.strip():
        parametri['materiale'] = materiale.strip()
    
    # 🏷️ KEYWORDS: Seleziona solo le più rilevanti per il tipo di articolo
    if keywords_classificate:
        keywords_rilevanti = []
        
        # Priorità per tipo articolo
        if tipo_articolo == 'borsa':
            keywords_rilevanti.extend(keywords_classificate.get('dettagli', [])[:2])
            keywords_rilevanti.extend(keywords_classificate.get('forme', [])[:1])
        elif tipo_articolo == 'scarpe':
            keywords_rilevanti.extend(keywords_classificate.get('stili', [])[:2])
            keywords_rilevanti.extend(keywords_classificate.get('caratteristiche', [])[:1])
        elif tipo_articolo in ['vestito', 'top', 'pantaloni']:
            keywords_rilevanti.extend(keywords_classificate.get('stili', [])[:1])
            keywords_rilevanti.extend(keywords_classificate.get('forme', [])[:2])
        
        parametri['keywords_rilevanti'] = keywords_rilevanti[:3]  # Max 3 keywords
    
    # 🕰️ VINTAGE: Sempre rilevante se true
    if vintage:
        parametri['vintage'] = True
    
    # 🎯 TARGET: Rilevante se specifico
    if target and target.strip() and target.strip() != 'Generale':
        parametri['target'] = target.strip()
    
    # 📊 PRIORITÀ CONDIZIONI E RARITÀ
    condizioni_priorita = {
        'Eccellenti': 3, 'Ottime': 2, 'Buone': 1, 'Discrete': 1
    }
    rarita_priorita = {
        'Introvabile': 3, 'Molto Raro': 2, 'Raro': 1, 'Comune': 0
    }
    
    parametri['priorita_condizioni'] = condizioni_priorita.get(condizioni, 1)
    parametri['priorita_rarita'] = rarita_priorita.get(rarita, 0)
    
    return parametri

def _costruisci_descrizione_intelligente_vestiaire(brand: str, nome_pulito: str, modello: str, 
                                                  colore: str, materiale: str, condizioni: str, 
                                                  rarita: str, vintage: bool, genere: str,
                                                  parametri: Dict, keywords_classificate: Dict) -> str:
    """🎯 COSTRUZIONE INTELLIGENTE della descrizione senza ripetizioni"""
    
    # 🏷️ COSTRUISCI NOME PRODOTTO
    if modello:
        nome_prodotto = f"{brand} {modello}"
    else:
        tipo_articolo = get_tipo_articolo_cached(nome_pulito) if nome_pulito else 'articolo'
        nome_prodotto = f"{brand} {tipo_articolo}"
    
    # 🎨 AGGETTIVI INTELLIGENTI basati su priorità
    aggettivi_condizioni = _get_aggettivi_condizioni_intelligenti(condizioni, parametri['priorita_condizioni'])
    aggettivi_rarita = _get_aggettivi_rarita_intelligenti(rarita, parametri['priorita_rarita'])
    
    # 🔗 COSTRUISCI DETTAGLI SENZA RIPETIZIONI
    dettagli = []
    
    # Aggiungi colore se rilevante
    if parametri['colore']:
        dettagli.append(_formatta_colore_intelligente(parametri['colore'], genere))
    
    # Aggiungi materiale se rilevante
    if parametri['materiale']:
        dettagli.append(_formatta_materiale_intelligente(parametri['materiale']))
    
    # Aggiungi keywords più rilevanti
    if parametri['keywords_rilevanti']:
        dettagli.extend(parametri['keywords_rilevanti'][:2])  # Max 2 per evitare sovraffollamento
    
    # Aggiungi vintage se rilevante
    if parametri['vintage']:
        dettagli.append(random.choice(['vintage', 'd\'epoca', 'storico']))
    
    # 📝 COSTRUISCI DESCRIZIONE FINALE
    articolo = "una" if genere == 'f' else "un"
    
    # Seleziona aggettivo principale
    aggettivo_principale = random.choice(aggettivi_rarita + aggettivi_condizioni)
    aggettivo_principale = concordanza_aggettivo(aggettivo_principale, genere)
    
    # Pattern intelligenti
    if dettagli:
        dettaglio_principale = dettagli[0]
        patterns = [
            f"{articolo} {nome_prodotto} {dettaglio_principale} {aggettivo_principale}",
            f"{articolo} {aggettivo_principale} {nome_prodotto} {dettaglio_principale}",
            f"{articolo} {nome_prodotto} {aggettivo_principale} {dettaglio_principale}",
            f"{articolo} splendido {nome_prodotto} {dettaglio_principale}"
        ]
    else:
        patterns = [
            f"{articolo} {nome_prodotto} {aggettivo_principale}",
            f"{articolo} {aggettivo_principale} {nome_prodotto}",
            f"{articolo} splendido {nome_prodotto}",
            f"{articolo} bellissimo {nome_prodotto}"
        ]
    
    return random.choice(patterns)

def _get_aggettivi_condizioni_intelligenti(condizioni: str, priorita: int) -> List[str]:
    """Aggettivi per condizioni basati su priorità"""
    if priorita >= 3:  # Eccellenti
        return ['perfetta', 'impeccabile', 'come nuova', 'stupenda']
    elif priorita >= 2:  # Ottime
        return ['bellissima', 'molto bella', 'ben conservata', 'splendida']
    elif priorita >= 1:  # Buone/Discrete
        return ['bella', 'interessante', 'particolare', 'carina']
    else:
        return ['interessante', 'particolare']

def _get_aggettivi_rarita_intelligenti(rarita: str, priorita: int) -> List[str]:
    """Aggettivi per rarità basati su priorità"""
    if priorita >= 3:  # Introvabile
        return ['rarissima', 'introvabile', 'unica', 'eccezionale', 'mitica']
    elif priorita >= 2:  # Molto Raro
        return ['molto rara', 'rara', 'speciale', 'ricercata']
    elif priorita >= 1:  # Raro
        return ['rara', 'particolare', 'speciale']
    else:
        return ['bella', 'interessante']

def _formatta_colore_intelligente(colore: str, genere: str) -> str:
    """Formattazione intelligente del colore"""
    colore_concordato = concordanza_aggettivo(colore, genere)
    
    colori_speciali = {
        'nero': 'total black' if random.random() < 0.3 else colore_concordato,
        'bianco': 'candido' if genere == 'm' else 'candida',
        'rosso': 'rosso acceso' if random.random() < 0.4 else colore_concordato,
        'blu': 'blu elegante' if random.random() < 0.3 else colore_concordato
    }
    
    return colori_speciali.get(colore.lower(), colore_concordato)

def _formatta_materiale_intelligente(materiale: str) -> str:
    """Formattazione intelligente del materiale"""
    materiali_speciali = {
        'pelle': random.choice(['in pelle', 'in vera pelle', 'in pelle pregiata']),
        'tessuto': random.choice(['in tessuto', 'in stoffa elegante']),
        'canvas': random.choice(['in canvas', 'in tela canvas']),
        'nylon': 'in nylon di qualità'
    }
    
    return materiali_speciali.get(materiale.lower(), f'in {materiale.lower()}')

def _costruisci_scarsita_naturale(genere: str) -> str:
    """Crea messaggio di scarsità naturale"""
    scarsita_patterns = [
        "ne abbiamo solo una",
        "ne abbiamo una sola", 
        "è l'ultima disponibile",
        "abbiamo solo questo pezzo",
        "è un pezzo unico",
        "ne è rimasta solo una" if genere == 'f' else "ne è rimasto solo uno"
    ]
    
    return random.choice(scarsita_patterns)

def _costruisci_ringraziamento_like() -> str:
    """Crea ringraziamento per il like"""
    ringraziamenti = [
        "per ringraziarti del tuo \"like\"",
        "per ringraziarti dell'interesse",
        "grazie per il tuo \"like\"", 
        "per il tuo interesse",
        "visto il tuo \"like\"",
        "dato il tuo interesse"
    ]
    
    return random.choice(ringraziamenti)

def _costruisci_offerta_personalizzata() -> str:
    """Crea offerta personalizzata"""
    offerte = [
        "ti sto inviando un'offerta con uno sconto in più",
        "ti stiamo inviando un'offerta con un ulteriore sconto solo per te",
        "ti stiamo facendo un'offerta speciale",
        "ti abbiamo riservato uno sconto esclusivo", 
        "ti stiamo preparando un'offerta personalizzata",
        "ti facciamo un prezzo speciale",
        "ti stiamo inviando un'offerta riservata"
    ]
    
    return random.choice(offerte)

def _costruisci_chiusura_cortese() -> str:
    """Crea chiusura cortese"""
    chiusure = [
        "il massimo che possiamo fare, in ogni caso grazie per l'interesse",
        "intanto grazie per il tuo \"like\"",
        "comunque grazie per l'attenzione",
        "speriamo ti piaccia la proposta",
        "fammi sapere se ti interessa",
        "spero possa interessarti",
        "grazie ancora per l'interesse mostrato",
        "sempre grazie per aver notato questo pezzo"
    ]
    
    return random.choice(chiusure)

def _pulisci_messaggio_vestiaire_migliorato(messaggio: str, brand: str, nome_pulito: str) -> str:
    """🧹 PULIZIA AVANZATA del messaggio con controllo ripetizioni specifiche"""
    if not messaggio:
        return ""
    
    # 🔍 CONTROLLO RIPETIZIONI SPECIFICHE
    brand_lower = brand.lower()
    
    # Pattern problematici da rimuovere
    patterns_problematici = [
        # Ripetizioni di brand
        (rf'\b{re.escape(brand_lower)}\s+{re.escape(brand_lower)}\b', brand, re.IGNORECASE),
        # Ripetizioni di articoli
        (r'\b(un|una)\s+(un|una)\b', r'\1', re.IGNORECASE),
        (r'\b(il|la|lo|gli|le)\s+(il|la|lo|gli|le)\b', r'\1', re.IGNORECASE),
        # Ripetizioni di preposizioni
        (r'\b(in|di|da|con|per)\s+(in|di|da|con|per)\b', r'\1', re.IGNORECASE),
        # Ripetizioni di aggettivi comuni
        (r'\b(bella|bello)\s+(bella|bello)\b', r'\1', re.IGNORECASE),
        (r'\b(rara|raro)\s+(rara|raro)\b', r'\1', re.IGNORECASE),
        # Spazi multipli
        (r'\s+', ' '),
        # Punteggiatura problematica
        (r'\s*,\s*,\s*', ', '),
        (r'\s*\.\s*\.\s*', '. '),
        (r'\s+([,.;:!?])', r'\1'),
        (r'([,.;:!?])\s*([,.;:!?])', r'\1')
    ]
    
    # Applica le correzioni
    messaggio_pulito = messaggio
    for pattern, replacement, *flags in patterns_problematici:
        flag = flags[0] if flags else 0
        messaggio_pulito = re.sub(pattern, replacement, messaggio_pulito, flags=flag)
    
    # 📝 CORREZIONI GRAMMATICALI SPECIFICHE
    correzioni_grammaticali = {
        'un offerta': "un'offerta",
        'un ulteriore': "un ulteriore", 
        'una ulteriore': "un'ulteriore",
        'è è': 'è',
        'e e': 'e',
        ', ,': ',',
        '. .': '.',
        ' .': '.',
        ' ,': ',',
        ' !': '!',
        ' ?': '?'
    }
    
    for errore, correzione in correzioni_grammaticali.items():
        messaggio_pulito = messaggio_pulito.replace(errore, correzione)
    
    # 🎨 MIGLIORAMENTI STILISTICI
    # Evita ripetizioni di "molto" vicine
    messaggio_pulito = re.sub(r'\bmolto\s+molto\b', 'molto', messaggio_pulito, flags=re.IGNORECASE)
    
    # Rimuovi parole duplicate adiacenti (generiche)
    parole_da_controllare = ['bella', 'bello', 'interessante', 'particolare', 'speciale', 'rara', 'raro']
    for parola in parole_da_controllare:
        pattern = rf'\b{parola}\s+{parola}\b'
        messaggio_pulito = re.sub(pattern, parola, messaggio_pulito, flags=re.IGNORECASE)
    
    # 🔤 CORREZIONE CAPITALIZZAZIONE
    messaggio_pulito = messaggio_pulito.strip()
    if messaggio_pulito:
        # Capitalizza inizio messaggio
        messaggio_pulito = messaggio_pulito[0].upper() + messaggio_pulito[1:]
        
        # Capitalizza dopo punto
        messaggio_pulito = re.sub(r'(\.\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), messaggio_pulito)
    
    # ✅ VALIDAZIONE FINALE
    # Se il messaggio è troppo corto o ha troppi problemi, usa fallback
    if len(messaggio_pulito) < 15 or messaggio_pulito.count('  ') > 2:
        return f"Ciao, è un bellissimo {brand} che ti piacerà! Te lo sto proponendo con uno sconto speciale per il tuo interesse. Fammi sapere!"
    
    return messaggio_pulito

def _pulisci_messaggio_vestiaire(messaggio: str) -> str:
    """Mantiene compatibilità con versione precedente"""
    return _pulisci_messaggio_vestiaire_migliorato(messaggio, "", "")

# ===============================
# SISTEMA CACHE PER MESSAGGI (semplificato)
# ===============================

# Cache per statistiche (solo se necessario)
FRASE_MEMORY_CACHE = {}

# ===============================
# MANTIENI COMPATIBILITÀ BACKWARD - RIMOSSE FUNZIONI SUPERFLUE
# ===============================

def pulisci_cache_frasi():
    """Pulisce la cache delle frasi per liberare memoria"""
    global FRASE_MEMORY_CACHE
    FRASE_MEMORY_CACHE.clear()
    logger.info("Cache frasi pulita - memoria liberata")

def _get_articolo_determinativo(genere: str, tipo: str) -> str:
    """Ottiene l'articolo determinativo corretto"""
    if genere == 'f':
        return 'la' if tipo != 'scarpe' else 'le'
    else:
        return 'il' if tipo not in ['pantaloni'] else 'i'

def _get_articolo_indeterminativo(genere: str, tipo: str) -> str:
    """Ottiene l'articolo indeterminativo corretto"""
    if genere == 'f':
        return 'una' if tipo != 'scarpe' else 'delle'
    else:
        return 'un' if tipo not in ['pantaloni'] else 'dei'

# ===============================
# ROUTES OTTIMIZZATE
# ===============================

@app.route('/')
@log_request_info
def index():
    """Homepage dell'applicazione"""
    return render_template('index.html')

@app.route('/api/articoli', methods=['GET'])
@handle_errors
@log_request_info
def get_articoli():
    """Ottiene tutti gli articoli con caching e paginazione opzionale"""
    try:
        # Parametri query opzionali
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 100, type=int)
        brand = request.args.get('brand')
        
        # Query ottimizzata
        query = Articolo.query
        
        if brand:
            query = query.filter(Articolo.brand == brand)
        
        # Ordina per data di creazione (più recenti prima)
        query = query.order_by(Articolo.created_at.desc())
        
        # Paginazione se richiesta
        if per_page < 100:
            articoli = query.paginate(page=page, per_page=per_page, error_out=False)
            result = [articolo.to_dict() for articolo in articoli.items]
            return jsonify({
                'articoli': result,
                'total': articoli.total,
                'pages': articoli.pages,
                'current_page': page
            })
        else:
            articoli = query.all()
            return jsonify([articolo.to_dict() for articolo in articoli])
            
    except Exception as e:
        logger.error(f"Errore nel recupero articoli: {e}")
        raise

@app.route('/api/articoli', methods=['POST'])
@handle_errors
@log_request_info
def create_articolo():
    """Crea un nuovo articolo con validazione avanzata"""
    try:
        data = request.form.to_dict()
        
        # Validazione dati
        is_valid, errors = Articolo.validate_data(data)
        if not is_valid:
            return jsonify({'error': 'Dati non validi', 'details': errors}), 400
        
        # Gestione file immagine
        filename = None
        file = request.files.get('immagine')
        if file and file.filename:
            # Validazione tipo file
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
                return jsonify({'error': 'Tipo di file non supportato'}), 400
            
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            logger.info(f"File salvato: {file_path}")

        # Conversione vintage
        vintage_value = data.get('vintage', 'false').lower()
        vintage_bool = vintage_value in ['true', '1', 'on', 'yes']

        # Creazione articolo
        articolo = Articolo(
            nome=data['nome'].strip(),
            brand=data['brand'].strip(),
            immagine=filename,
            colore=data.get('colore', '').strip(),
            materiale=data.get('materiale', '').strip(),
            keywords=data.get('keywords', '').strip(),
            termini_commerciali=data.get('termini_commerciali', '').strip(),
            condizioni=data.get('condizioni', '').strip(),
            rarita=data.get('rarita', '').strip(),
            vintage=vintage_bool,
            target=data.get('target', '').strip()
        )
        
        db.session.add(articolo)
        db.session.commit()
        
        logger.info(f"Articolo creato: {articolo.id} - {articolo.nome}")
        return jsonify(articolo.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Errore nella creazione articolo: {e}")
        raise

@app.route('/api/articoli/<int:id>', methods=['PUT'])
@handle_errors
@log_request_info
def update_articolo(id):
    """Aggiorna un articolo esistente"""
    try:
        articolo = Articolo.query.get_or_404(id)
        data = request.form.to_dict()
        
        # Validazione dati
        is_valid, errors = Articolo.validate_data(data)
        if not is_valid:
            return jsonify({'error': 'Dati non validi', 'details': errors}), 400
        
        # Aggiorna campi
        articolo.nome = data['nome'].strip()
        articolo.brand = data['brand'].strip()
        articolo.colore = data.get('colore', '').strip()
        articolo.materiale = data.get('materiale', '').strip()
        articolo.keywords = data.get('keywords', '').strip()
        articolo.termini_commerciali = data.get('termini_commerciali', '').strip()
        articolo.condizioni = data.get('condizioni', '').strip()
        articolo.rarita = data.get('rarita', '').strip()
        articolo.target = data.get('target', '').strip()
        
        # Conversione vintage
        vintage_value = data.get('vintage', 'false').lower()
        articolo.vintage = vintage_value in ['true', '1', 'on', 'yes']
        
        # Gestione nuova immagine
        file = request.files.get('immagine')
        if file and file.filename:
            # Elimina vecchia immagine
            if articolo.immagine:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], articolo.immagine)
                if os.path.exists(old_path):
                    os.remove(old_path)
                    logger.info(f"Vecchia immagine eliminata: {old_path}")
            
            # Salva nuova immagine
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            articolo.immagine = filename
            logger.info(f"Nuova immagine salvata: {file_path}")
        
        db.session.commit()
        logger.info(f"Articolo aggiornato: {articolo.id} - {articolo.nome}")
        return jsonify(articolo.to_dict())
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Errore nell'aggiornamento articolo {id}: {e}")
        raise

@app.route('/api/articoli/<int:id>', methods=['DELETE'])
@handle_errors
@log_request_info
def delete_articolo(id):
    """Elimina un articolo"""
    try:
        articolo = Articolo.query.get_or_404(id)
        
        # Elimina immagine se presente
        if articolo.immagine:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], articolo.immagine)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Immagine eliminata: {file_path}")
        
        db.session.delete(articolo)
        db.session.commit()
        
        logger.info(f"Articolo eliminato: {id}")
        return '', 204
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Errore nell'eliminazione articolo {id}: {e}")
        raise



@app.route('/api/stats', methods=['GET'])
@handle_errors
@log_request_info
def get_stats():
    """Ottiene statistiche sui dati"""
    try:
        total_articoli = Articolo.query.count()
        total_brands = db.session.query(Articolo.brand).distinct().count()
        articoli_vintage = Articolo.query.filter(Articolo.vintage == True).count()
        
        # Statistiche per rarità
        stats_rarita = db.session.query(
            Articolo.rarita, 
            db.func.count(Articolo.id)
        ).group_by(Articolo.rarita).all()
        
        # Statistiche per brand
        stats_brand = db.session.query(
            Articolo.brand, 
            db.func.count(Articolo.id)
        ).group_by(Articolo.brand).order_by(db.func.count(Articolo.id).desc()).all()
        
        return jsonify({
            'total_articoli': total_articoli,
            'total_brands': total_brands,
            'articoli_vintage': articoli_vintage,
            'stats_rarita': dict(stats_rarita),
            'stats_brand': dict(stats_brand)
        })
        
    except Exception as e:
        logger.error(f"Errore nel recupero statistiche: {e}")
        raise

@app.route('/api/genera-messaggio-like/<int:id>', methods=['GET'])
@handle_errors  
@log_request_info
def genera_messaggio_like(id):
    """Genera messaggio diretto per utenti che hanno messo like"""
    try:
        articolo = Articolo.query.get_or_404(id)
        
        # Estrai e processa i dati
        colore = articolo.colore.strip() if articolo.colore else ''
        materiale = articolo.materiale.strip() if articolo.materiale else ''
        keywords = articolo._parse_keywords()
        termini_commerciali = articolo._parse_termini_commerciali()
        condizioni = articolo.condizioni.strip() if articolo.condizioni else ''
        rarita = articolo.rarita.strip() if articolo.rarita else ''
        target = articolo.target.strip() if articolo.target else ''
        
        # Classifica keywords
        keywords_str = ','.join(keywords)
        keywords_classificate = classifica_keywords_cached(keywords_str) if keywords_str else {}
        
        # Genera messaggio per like
        messaggio = genera_messaggio_like_vestiaire(
            articolo.brand, articolo.nome, colore, materiale, keywords_classificate,
            condizioni, rarita, articolo.vintage, target, termini_commerciali
        )
        
        logger.info(f"Messaggio like generato per articolo {id}")
        return jsonify({
            'messaggio': messaggio,
            'tipo': 'like_response'
        })
        
    except Exception as e:
        logger.error(f"Errore nella generazione messaggio like per articolo {id}: {e}")
        raise

# ENDPOINT RIMOSSI: /api/statistiche-frasi e /api/pulisci-cache-frasi
# Non più necessari con il nuovo algoritmo semplificato per messaggi like
# La cache è minimale e non richiede gestione complessa

# ===============================
# ERROR HANDLERS
# ===============================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Risorsa non trovata'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Errore interno server: {error}")
    return jsonify({'error': 'Errore interno del server'}), 500

# ===============================
# MAIN
# ===============================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    debug = not os.environ.get('DATABASE_URL')  # Debug solo in locale
    
    logger.info(f"🚀 Avvio applicazione su porta {port} (debug: {debug})")
    app.run(debug=debug, port=port, host='0.0.0.0') 
