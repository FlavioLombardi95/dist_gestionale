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

def genera_frase_stile_professionale(brand: str, nome: str, colore: str, materiale: str, 
                                   keywords_classificate: Dict, condizioni: str, rarita: str, 
                                   vintage: bool, target: str, termini_commerciali: List[str]) -> str:
    """Genera frasi professionali ottimizzate - wrapper per il nuovo sistema"""
    return genera_frase_personalizzata(brand, nome, colore, materiale, keywords_classificate,
                                     condizioni, rarita, vintage, target, termini_commerciali, 'elegante')

# ===============================
# SISTEMA GENERAZIONE FRASI MULTI-STILE AVANZATO CON OTTIMIZZAZIONI
# ===============================

# Cache per memorizzare frasi generate ed evitare ripetizioni
FRASE_MEMORY_CACHE = {}
SEMANTIC_VARIATIONS_CACHE = {}

def genera_frase_personalizzata_ottimizzata(brand: str, nome: str, colore: str, materiale: str, 
                                          keywords_classificate: Dict, condizioni: str, rarita: str, 
                                          vintage: bool, target: str, termini_commerciali: List[str], 
                                          stile: str = 'elegante') -> str:
    """Sistema ottimizzato di generazione frasi con memoria anti-ripetizione e scoring avanzato"""
    
    # Cache per tipo e genere
    tipo_articolo = get_tipo_articolo_cached(nome)
    genere = get_genere_cached(tipo_articolo)
    
    # Analisi contestuale avanzata
    keywords_analizzate = _analisi_contestuale_keywords(keywords_classificate, tipo_articolo, brand)
    
    # Costruzione componenti ottimizzati
    nome_completo = _costruisci_nome_avanzato_con_variazioni(nome, brand, tipo_articolo, stile)
    desc_materiali = _costruisci_descrizione_materiali_avanzata_ottimizzata(
        materiale, colore, keywords_analizzate, genere, stile, tipo_articolo
    )
    desc_condizioni = _costruisci_descrizione_condizioni_avanzata(condizioni, genere, stile)
    desc_rarita = _costruisci_descrizione_rarita_avanzata(rarita, genere, stile)
    desc_target = _costruisci_descrizione_target_avanzata(target, stile)
    
    # Aggettivi brand dinamici
    aggettivo_brand = _genera_aggettivo_dinamico_brand(brand, genere, stile, keywords_analizzate)
    
    # Articoli grammaticali
    art_det = _get_articolo_determinativo(genere, tipo_articolo)
    art_indet = _get_articolo_indeterminativo(genere, tipo_articolo)
    
    # Template con scoring avanzato
    templates_con_score = _get_templates_con_scoring(
        stile, nome_completo, desc_materiali, desc_condizioni, desc_rarita,
        desc_target, aggettivo_brand, art_det, art_indet, genere, vintage,
        keywords_analizzate, tipo_articolo
    )
    
    # *** CORREZIONE: Cache key robusta senza caratteri problematici ***
    def clean_for_cache(text):
        if not text:
            return 'none'
        # Rimuovi caratteri speciali e sostituisci spazi con underscores
        import re
        cleaned = re.sub(r'[^\w\s-]', '', str(text))
        cleaned = re.sub(r'\s+', '_', cleaned.strip())
        return cleaned[:50] if cleaned else 'none'  # Limita lunghezza
    
    cache_key = f"{clean_for_cache(brand)}_{clean_for_cache(nome)}_{clean_for_cache(colore)}_{clean_for_cache(materiale)}_{clean_for_cache(stile)}"
    
    # Selezione template con memoria
    frase_principale = _seleziona_template_con_memoria(
        templates_con_score, nome_completo, brand, stile, cache_key
    )
    
    # Call to action con variazioni
    call_to_action = _genera_call_to_action_con_variazioni(termini_commerciali, stile, cache_key)
    
    # Pulizia finale
    frase_completa = f"{frase_principale}\n{call_to_action}"
    frase_finale = _pulizia_finale_frase(frase_completa)
    
    # **AGGIORNAMENTO CACHE PER STATISTICHE**
    if cache_key not in FRASE_MEMORY_CACHE:
        FRASE_MEMORY_CACHE[cache_key] = []
    FRASE_MEMORY_CACHE[cache_key].append(frase_finale)
    
    # Mantieni solo le ultime 10 frasi per articolo
    if len(FRASE_MEMORY_CACHE[cache_key]) > 10:
        FRASE_MEMORY_CACHE[cache_key] = FRASE_MEMORY_CACHE[cache_key][-10:]
    
    # Auto-pulizia cache se diventa troppo grande
    if len(FRASE_MEMORY_CACHE) > 1000:
        keys_to_remove = list(FRASE_MEMORY_CACHE.keys())[:-500]  # Mantieni solo ultimi 500
        for key in keys_to_remove:
            del FRASE_MEMORY_CACHE[key]
    
    return frase_finale

def _analisi_contestuale_keywords(keywords_classificate: Dict, tipo_articolo: str, brand: str) -> Dict:
    """Analisi contestuale avanzata delle keywords con sinonimi e contesti"""
    
    # Espansione semantica per categoria
    espansioni_semantiche = {
        'colori': {
            'nero': ['elegante', 'raffinato', 'classico', 'sofisticato'],
            'bianco': ['puro', 'essenziale', 'minimalista', 'pulito'],
            'rosso': ['passionale', 'vivace', 'energico', 'accattivante'],
            'oro': ['prezioso', 'lussuoso', 'esclusivo', 'regale'],
            'argento': ['moderno', 'contemporaneo', 'chic', 'elegante']
        },
        'materiali': {
            'pelle': ['pregiata', 'morbida', 'resistente', 'naturale'],
            'seta': ['setosa', 'fluida', 'preziosa', 'delicata'],
            'cashmere': ['soffice', 'calda', 'lussuosa', 'pregiata'],
            'cotone': ['naturale', 'traspirante', 'confortevole', 'versatile']
        },
        'stili': {
            'vintage': ['autentico', 'storico', 'caratteristico', 'unico'],
            'moderno': ['contemporaneo', 'attuale', 'innovativo', 'trendy'],
            'classico': ['intramontabile', 'elegante', 'raffinato', 'senza tempo']
        }
    }
    
    # Contesti specifici per brand
    contesti_brand = {
        'Chanel': ['iconico', 'intramontabile', 'parigino', 'couture'],
        'Hermès': ['artigianale', 'esclusivo', 'leggendario', 'prezioso'],
        'Louis Vuitton': ['viaggiatore', 'distintivo', 'prestigioso', 'raffinato'],
        'Gucci': ['italiano', 'creativo', 'audace', 'innovativo'],
        'Prada': ['minimale', 'sofisticato', 'moderno', 'intellettuale']
    }
    
    # Contesti per tipo articolo
    contesti_tipo = {
        'borsa': ['funzionale', 'elegante', 'pratica', 'versatile'],
        'scarpe': ['confortevoli', 'stilose', 'raffinate', 'distintive'],
        'vestito': ['femminile', 'elegante', 'sofisticato', 'chic'],
        'accessorio': ['distintivo', 'caratteristico', 'personale', 'unico']
    }
    
    # Arricchisci le keywords con contesti
    keywords_analizzate = keywords_classificate.copy()
    
    # Aggiungi contesti semantici
    keywords_analizzate['contesti_semantici'] = []
    keywords_analizzate['brand_context'] = contesti_brand.get(brand, [])
    keywords_analizzate['tipo_context'] = contesti_tipo.get(tipo_articolo, [])
    
    # Espandi le keywords esistenti
    for categoria, keywords in keywords_classificate.items():
        if categoria in espansioni_semantiche:
            for keyword in keywords:
                if keyword in espansioni_semantiche[categoria]:
                    keywords_analizzate['contesti_semantici'].extend(
                        espansioni_semantiche[categoria][keyword]
                    )
    
    # Rimuovi duplicati
    keywords_analizzate['contesti_semantici'] = list(set(keywords_analizzate['contesti_semantici']))
    
    return keywords_analizzate

def _costruisci_nome_avanzato_con_variazioni(nome: str, brand: str, tipo_articolo: str, stile: str) -> str:
    """Costruzione nome con variazioni semantiche per stile"""
    nome_base = _costruisci_nome_avanzato(nome, brand, tipo_articolo)
    
    # Variazioni per stile
    if stile == 'emotivo':
        prefissi_emotivi = ['meraviglioso', 'stupendo', 'magnifico', 'splendido']
        if random.random() < 0.3:  # 30% di probabilità
            return f"{random.choice(prefissi_emotivi)} {nome_base}"
    
    elif stile == 'esclusivo':
        prefissi_esclusivi = ['prestigioso', 'esclusivo', 'ricercato', 'selezionato']
        if random.random() < 0.4:  # 40% di probabilità
            return f"{random.choice(prefissi_esclusivi)} {nome_base}"
    
    return nome_base

def _costruisci_descrizione_materiali_avanzata_ottimizzata(
    materiale: str, colore: str, keywords_analizzate: Dict, genere: str, 
    stile: str, tipo_articolo: str
) -> str:
    """Descrizione materiali ottimizzata con contesti semantici"""
    
    if not materiale and not colore:
        # Usa contesti semantici se disponibili
        contesti = keywords_analizzate.get('contesti_semantici', [])
        if contesti and random.random() < 0.3:
            return f"dal carattere {random.choice(contesti)}"
        return ""
    
    # Descrizione base
    desc_base = _costruisci_descrizione_materiali_avanzata(
        materiale, colore, keywords_analizzate, genere, stile
    )
    
    # Arricchimento con contesti
    contesti_brand = keywords_analizzate.get('brand_context', [])
    contesti_tipo = keywords_analizzate.get('tipo_context', [])
    
    # Aggiungi contesto brand se appropriato
    if contesti_brand and random.random() < 0.25 and stile in ['elegante', 'esclusivo']:
        contesto = random.choice(contesti_brand)
        if desc_base:
            desc_base += f", dal design {contesto}"
        else:
            desc_base = f"dal design {contesto}"
    
    # Aggiungi contesto tipo se appropriato
    elif contesti_tipo and random.random() < 0.2:
        contesto = random.choice(contesti_tipo)
        if desc_base:
            desc_base += f" e {contesto}"
        else:
            desc_base = f"dal carattere {contesto}"
    
    return desc_base

def _genera_aggettivo_dinamico_brand(brand: str, genere: str, stile: str, keywords_analizzate: Dict) -> str:
    """Generazione dinamica di aggettivi brand basata su contesto"""
    
    # Aggettivi base per stile
    aggettivo_base = _get_aggettivo_brand_per_stile(brand, genere, stile)
    
    # Probabilità di variazione basata su keywords
    contesti_semantici = keywords_analizzate.get('contesti_semantici', [])
    brand_context = keywords_analizzate.get('brand_context', [])
    
    # Usa contesti per variazioni creative
    if contesti_semantici and random.random() < 0.3:
        contesto = random.choice(contesti_semantici)
        # Combina aggettivo base con contesto
        combinazioni = [
            f"{aggettivo_base} e {contesto}",
            f"{contesto} e {aggettivo_base}",
            contesto if random.random() < 0.5 else aggettivo_base
        ]
        return random.choice(combinazioni)
    
    return aggettivo_base

def _get_templates_con_scoring(stile: str, nome_completo: str, desc_materiali: str, 
                              desc_condizioni: str, desc_rarita: str, desc_target: str, 
                              aggettivo_brand: str, art_det: str, art_indet: str, 
                              genere: str, vintage: bool, keywords_analizzate: Dict,
                              tipo_articolo: str) -> List[Dict]:
    """Template con sistema di scoring avanzato"""
    
    # Template base
    templates_base = _get_templates_per_stile(
        stile, nome_completo, desc_materiali, desc_condizioni, desc_rarita,
        desc_target, aggettivo_brand, art_det, art_indet, genere, vintage
    )
    
    # Sistema di scoring
    templates_con_score = []
    
    for template in templates_base:
        score = _calcola_score_template(
            template, keywords_analizzate, stile, tipo_articolo, vintage
        )
        templates_con_score.append({
            'template': template,
            'score': score
        })
    
    # Ordina per score (migliori prima)
    templates_con_score.sort(key=lambda x: x['score'], reverse=True)
    
    return templates_con_score

def _calcola_score_template(template: str, keywords_analizzate: Dict, stile: str, 
                           tipo_articolo: str, vintage: bool) -> float:
    """Calcola score di qualità per un template"""
    score = 1.0
    
    # Bonus per lunghezza ottimale (80-200 caratteri)
    lunghezza = len(template)
    if 80 <= lunghezza <= 200:
        score += 0.3
    elif lunghezza < 50:
        score -= 0.2
    elif lunghezza > 250:
        score -= 0.1
    
    # Bonus per presenza di keywords rilevanti
    contesti_semantici = keywords_analizzate.get('contesti_semantici', [])
    brand_context = keywords_analizzate.get('brand_context', [])
    
    for contesto in contesti_semantici[:3]:  # Primi 3 contesti più rilevanti
        if contesto.lower() in template.lower():
            score += 0.15
    
    for contesto in brand_context[:2]:  # Primi 2 contesti brand
        if contesto.lower() in template.lower():
            score += 0.1
    
    # Bonus per coerenza con stile
    parole_stile = {
        'elegante': ['raffinato', 'elegante', 'classe', 'sofisticato'],
        'emotivo': ['cuore', 'sogno', 'emozione', 'fascino'],
        'amichevole': ['bello', 'fantastico', 'perfetto', 'speciale'],
        'professionale': ['qualità', 'certificato', 'specifiche', 'articolo'],
        'esclusivo': ['esclusivo', 'privilegio', 'lusso', 'élite']
    }
    
    parole_stile_corrente = parole_stile.get(stile, [])
    for parola in parole_stile_corrente:
        if parola.lower() in template.lower():
            score += 0.1
    
    # Bonus per menzione vintage se appropriato
    if vintage and 'vintage' in template.lower():
        score += 0.2
    
    # Penalità per ripetizioni eccessive di parole
    parole = template.lower().split()
    parole_uniche = set(parole)
    if len(parole) > 0:
        rapporto_unicità = len(parole_uniche) / len(parole)
        if rapporto_unicità < 0.7:
            score -= 0.15
    
    return max(score, 0.1)  # Score minimo

def _seleziona_template_con_memoria(templates_con_score: List[Dict], nome_completo: str, 
                                   brand: str, stile: str, cache_key: str) -> str:
    """Selezione template con sistema anti-ripetizione"""
    
    # Frasi già generate per questo articolo
    frasi_precedenti = FRASE_MEMORY_CACHE.get(cache_key, [])
    
    # Filtra template già usati (controllo similarità)
    templates_disponibili = []
    
    for template_data in templates_con_score:
        template = template_data['template']
        
        # Controlla similarità con frasi precedenti
        is_troppo_simile = False
        for frase_precedente in frasi_precedenti:
            similarità = _calcola_similarita_frasi(template, frase_precedente)
            if similarità > 0.7:  # Soglia di similarità
                is_troppo_simile = True
                break
        
        if not is_troppo_simile:
            templates_disponibili.append(template_data)
    
    # Se tutti i template sono troppo simili, usa comunque i migliori
    if not templates_disponibili:
        templates_disponibili = templates_con_score[:3]
    
    # Selezione pesata sui migliori template
    if len(templates_disponibili) >= 3:
        # 60% probabilità per il migliore, 30% per il secondo, 10% per il terzo
        pesi = [0.6, 0.3, 0.1]
        templates_pesati = templates_disponibili[:3]
    else:
        # Distribuzione uniforme
        pesi = [1.0 / len(templates_disponibili)] * len(templates_disponibili)
        templates_pesati = templates_disponibili
    
    # Selezione pesata
    template_selezionato = random.choices(templates_pesati, weights=pesi)[0]
    
    # Pulizia finale
    frase_pulita = _pulizia_finale_frase(template_selezionato['template'])
    
    # Fallback se pulizia fallisce
    if not frase_pulita or len(frase_pulita) < 20:
        fallbacks = {
            'elegante': f"Raffinato {nome_completo}, un classico dell'eleganza.",
            'emotivo': f"Un {nome_completo} che conquista il cuore.",
            'amichevole': f"Bellissimo {nome_completo}, perfetto per te!",
            'professionale': f"Articolo {nome_completo} di qualità certificata.",
            'esclusivo': f"Esclusivo {nome_completo} per pochi eletti."
        }
        return fallbacks.get(stile, f"Elegante {nome_completo} {brand}.")
    
    return frase_pulita

def _calcola_similarita_frasi(frase1: str, frase2: str) -> float:
    """Calcola similarità tra due frasi (semplice confronto parole)"""
    if not frase1 or not frase2:
        return 0.0
    
    # Tokenizzazione semplice
    parole1 = set(frase1.lower().split())
    parole2 = set(frase2.lower().split())
    
    # Jaccard similarity
    intersezione = len(parole1.intersection(parole2))
    unione = len(parole1.union(parole2))
    
    return intersezione / unione if unione > 0 else 0.0

def _genera_call_to_action_con_variazioni(termini_commerciali: List[str], stile: str, cache_key: str) -> str:
    """Call to action con sistema di variazioni"""
    
    # Call to action base
    call_actions_base = _genera_call_to_action_per_stile(termini_commerciali, stile)
    
    # Sistema di variazioni temporali
    variazioni_temporali = [
        "Controlla subito", "Dai un'occhiata ora", "Verifica immediatamente",
        "Non perdere tempo", "Affrettati a vedere", "Scopri subito"
    ]
    
    # Variazioni per urgenza
    variazioni_urgenza = [
        "questa occasione unica", "questa opportunità esclusiva", 
        "questa proposta speciale", "questo affare irripetibile",
        "questa offerta limitata"
    ]
    
    # Probabilità di variazione basata su cache
    if cache_key in FRASE_MEMORY_CACHE and len(FRASE_MEMORY_CACHE[cache_key]) > 2:
        # Articolo con molte frasi generate -> più variazioni
        if random.random() < 0.4:
            variazione_temporale = random.choice(variazioni_temporali)
            variazione_urgenza = random.choice(variazioni_urgenza)
            return f"{variazione_temporale} {variazione_urgenza} nel tuo account!"
    
    return call_actions_base

def _pulizia_finale_frase(frase: str) -> str:
    """Pulizia finale ottimizzata della frase"""
    if not frase:
        return ""
    
    # Pulizia avanzata step by step
    frase_pulita = re.sub(r'\s+', ' ', frase)
    frase_pulita = frase_pulita.replace(' ,', ',').replace('  ', ' ').strip()
    frase_pulita = frase_pulita.replace(': ,', ':').replace(', ,', ',').replace(' :', ':')
    frase_pulita = frase_pulita.replace('.,', '.').replace(',.', '.').replace('..', '.')
    frase_pulita = frase_pulita.replace('  ', ' ').replace(' .', '.')
    
    # *** CORREZIONE: Rimuovi pattern problematici con regex più accurate ***
    pattern_problematici = [
        (r'\b(\w+)\s+\1\b', r'\1'),  # Parole duplicate -> mantieni solo la prima
        (r'\s+([,.;:])', r'\1'),      # Spazi prima punteggiatura
        (r'([,.;:])\s*([,.;:])', r'\1'),  # Punteggiatura doppia -> mantieni solo la prima
        (r'\b(in|di|da|con|per)\s+\1\b', r'\1'),  # Preposizioni duplicate
        (r'\b(il|la|lo|le|gli|i)\s+\1\b', r'\1'),  # Articoli duplicati
        (r'\s*\n\s*', '\n'),  # Pulizia line breaks
        (r'\n{3,}', '\n\n'),  # Max 2 line breaks consecutivi
    ]
    
    for pattern, replacement in pattern_problematici:
        frase_pulita = re.sub(pattern, replacement, frase_pulita, flags=re.IGNORECASE)
    
    # *** CORREZIONE: Gestione sicura della capitalizzazione ***
    if frase_pulita:
        # Capitalizza ogni riga separatamente
        righe = frase_pulita.split('\n')
        righe_pulite = []
        for riga in righe:
            riga = riga.strip()
            if riga:
                riga = riga[0].upper() + riga[1:] if len(riga) > 1 else riga.upper()
            righe_pulite.append(riga)
        frase_pulita = '\n'.join(righe_pulite)
    
    # *** CORREZIONE: Validazione finale ***
    frase_pulita = frase_pulita.strip()
    
    # Assicurati che non ci siano spazi doppi residui
    while '  ' in frase_pulita:
        frase_pulita = frase_pulita.replace('  ', ' ')
    
    return frase_pulita

def pulisci_cache_frasi():
    """Pulisce la cache delle frasi per liberare memoria"""
    global FRASE_MEMORY_CACHE
    FRASE_MEMORY_CACHE.clear()
    logger.info("Cache frasi pulita - memoria liberata")

# ===============================
# MANTIENI COMPATIBILITÀ BACKWARD
# ===============================

def genera_frase_personalizzata(brand: str, nome: str, colore: str, materiale: str, 
                               keywords_classificate: Dict, condizioni: str, rarita: str, 
                               vintage: bool, target: str, termini_commerciali: List[str], 
                               stile: str = 'elegante') -> str:
    """Alias per compatibilità che punta alla versione ottimizzata"""
    return genera_frase_personalizzata_ottimizzata(
        brand, nome, colore, materiale, keywords_classificate, condizioni, 
        rarita, vintage, target, termini_commerciali, stile
    )

def _costruisci_nome_avanzato(nome: str, brand: str, tipo_articolo: str) -> str:
    """Costruzione nome più intelligente e raffinata"""
    nome_pulito = nome.replace(brand, '').strip()
    
    # Rimuovi varianti più sofisticate
    varianti_tipo = [
        tipo_articolo.lower(), tipo_articolo.lower() + 's', tipo_articolo.lower() + 'e',
        tipo_articolo.lower() + 'i', tipo_articolo.capitalize(), tipo_articolo.upper(),
        f"{tipo_articolo.lower()}:", f"{tipo_articolo.lower()}-"
    ]
    
    for variante in varianti_tipo:
        nome_pulito = re.sub(rf'\b{re.escape(variante)}\b', '', nome_pulito, flags=re.IGNORECASE)
    
    # Pulizia avanzata
    nome_pulito = re.sub(r'\s+', ' ', nome_pulito).strip()
    nome_pulito = re.sub(r'^[-\s:]+|[-\s:]+$', '', nome_pulito)
    
    # Costruzione intelligente
    if nome_pulito and nome_pulito.lower() not in [brand.lower(), tipo_articolo.lower()]:
        if len(nome_pulito.split()) == 1 and len(nome_pulito) < 4:
            return f"{tipo_articolo.lower()} {brand}"
        return f"{tipo_articolo.lower()} {brand} {nome_pulito}".strip()
    else:
        return f"{tipo_articolo.lower()} {brand}".strip()

def _costruisci_descrizione_materiali_avanzata(materiale: str, colore: str, keywords_classificate: Dict, genere: str, stile: str) -> str:
    """Descrizione materiali adattata allo stile"""
    if not materiale and not colore:
        return ""
    
    # Estrai dettagli aggiuntivi
    dettagli_extra = keywords_classificate.get('materiali', [])
    
    if materiale and colore:
        colore_concordato = concordanza_aggettivo(colore, genere)
        
        if stile == 'elegante':
            if 'pelle' in materiale.lower():
                return f"in pregiata pelle {colore_concordato}"
            return f"in raffinato {materiale.lower()} {colore_concordato}"
        
        elif stile == 'emotivo':
            if 'pelle' in materiale.lower():
                return f"dalla morbida pelle {colore_concordato}"
            return f"dal magnifico {materiale.lower()} {colore_concordato}"
        
        elif stile == 'amichevole':
            # *** CORREZIONE: Gestione sicura del suffisso ***
            stupendo_concordato = concordanza_aggettivo('stupendo', genere)
            return f"in {materiale.lower()} {colore_concordato} {stupendo_concordato}"
        
        elif stile == 'professionale':
            return f"realizzat{concordanza_aggettivo('realizzato', genere)[-1]} in {materiale.lower()} {colore_concordato}"
        
        elif stile == 'esclusivo':
            if dettagli_extra:
                return f"in esclusivo {materiale.lower()} {colore_concordato} con {dettagli_extra[0]}"
            return f"in esclusivo {materiale.lower()} {colore_concordato}"
    
    elif materiale:
        if stile == 'elegante':
            return f"in pregiato {materiale.lower()}"
        elif stile == 'emotivo':
            return f"dal bellissimo {materiale.lower()}"
        elif stile == 'esclusivo':
            return f"in esclusivo {materiale.lower()}"
        else:
            return f"in {materiale.lower()}"
    
    elif colore:
        colore_concordato = concordanza_aggettivo(colore, genere)
        if stile == 'emotivo':
            return f"dal color {colore_concordato} che cattura l'occhio"
        else:
            return f"color {colore_concordato}"
    
    return ""

def _costruisci_descrizione_condizioni_avanzata(condizioni: str, genere: str, stile: str) -> str:
    """Descrizione condizioni personalizzata per stile"""
    if not condizioni:
        return ""
    
    suffisso = 'a' if genere == 'f' else 'o'
    
    condizioni_map = {
        'elegante': {
            'Eccellenti': [f"in condizioni eccellenti", f"perfettamente conservat{suffisso}", f"impeccabile"],
            'Ottime': [f"in ottime condizioni", f"splendidamente conservat{suffisso}"],
            'Buone': [f"in buone condizioni", f"ben conservat{suffisso}"],
            'Discrete': [f"in discrete condizioni", f"con segni di vissuto"]
        },
        'emotivo': {
            'Eccellenti': [f"in condizioni da sogno", f"perfett{suffisso} come il primo giorno", f"che ti farà innamorare"],
            'Ottime': [f"bellissim{suffisso} e ben conservat{suffisso}", f"che conquista al primo sguardo"],
            'Buone': [f"con tutto il suo fascino intatto", f"ricch{suffisso} di personalità"],
            'Discrete': [f"con il fascino dell'autenticità", f"pien{suffisso} di storia"]
        },
        'amichevole': {
            'Eccellenti': [f"praticamente come nuov{suffisso}!", f"in condizioni fantastiche"],
            'Ottime': [f"davvero ben tenut{suffisso}", f"in gran bella forma"],
            'Buone': [f"ancora molto bell{suffisso}", f"con tanto da dare"],
            'Discrete': [f"con qualche segno del tempo", f"ma ancora molto valid{suffisso}"]
        },
        'professionale': {
            'Eccellenti': [f"classificat{suffisso} in condizioni eccellenti", f"con grado di conservazione A+"],
            'Ottime': [f"in ottime condizioni generali", f"ben mantenut{suffisso}"],
            'Buone': [f"in buone condizioni d'uso", f"funzionalmente perfett{suffisso}"],
            'Discrete': [f"in condizioni discrete", f"con normali segni d'uso"]
        },
        'esclusivo': {
            'Eccellenti': [f"in stato di conservazione museale", f"di rara perfezione"],
            'Ottime': [f"di eccezionale fattura e conservazione", f"dal fascino immutato"],
            'Buone': [f"dal carattere distintivo preservato", f"con nobili segni del tempo"],
            'Discrete': [f"con il fascino dell'autenticità", f"testimone di storie vissute"]
        }
    }
    
    options = condizioni_map.get(stile, condizioni_map['elegante']).get(condizioni, [f"in {condizioni.lower()} condizioni"])
    return random.choice(options)

def _costruisci_descrizione_rarita_avanzata(rarita: str, genere: str, stile: str) -> str:
    """Descrizione rarità personalizzata per stile"""
    if not rarita or rarita == 'Comune':
        return ""
    
    rarita_map = {
        'elegante': {
            'Introvabile': [concordanza_aggettivo('introvabile', genere), f"di rara bellezza"],
            'Molto Raro': [f"molto {concordanza_aggettivo('raro', genere)}", f"di eccezionale rarità"],
            'Raro': [concordanza_aggettivo('raro', genere), f"difficile da trovare"]
        },
        'emotivo': {
            'Introvabile': [f"un vero tesoro nascosto", f"quasi impossibile da trovare"],
            'Molto Raro': [f"un pezzo che fa battere il cuore", f"di una rarità che emoziona"],
            'Raro': [f"speciale e ricercato", f"che sa come conquistare"]
        },
        'amichevole': {
            'Introvabile': [f"una vera chicca!", f"praticamente impossibile da scovare"],
            'Molto Raro': [f"super raro e ricercato", f"che non si trova facilmente"],
            'Raro': [f"abbastanza raro", f"non comune da trovare"]
        },
        'professionale': {
            'Introvabile': [f"classificat{concordanza_aggettivo('classificato', genere)[-1]} come introvabile", f"di altissima rarità"],
            'Molto Raro': [f"ad alta rarità sul mercato", f"molto {concordanza_aggettivo('ricercato', genere)}"],
            'Raro': [f"{concordanza_aggettivo('ricercato', genere)} dai collezionisti", concordanza_aggettivo('raro', genere)]
        },
        'esclusivo': {
            'Introvabile': [f"di leggendaria rarità", f"dal valore inestimabile"],
            'Molto Raro': [f"di esclusiva rarità", f"per pochissimi eletti"],
            'Raro': [f"di selezionata rarità", f"per veri intenditori"]
        }
    }
    
    options = rarita_map.get(stile, rarita_map['elegante']).get(rarita, [])
    return random.choice(options) if options else ""

def _costruisci_descrizione_target_avanzata(target: str, stile: str) -> str:
    """Descrizione target personalizzata per stile"""
    if not target:
        return ""
    
    target_map = {
        'elegante': {
            'Intenditrici': ['per raffinati palati femminili', 'per conoscitrici di stile'],
            'Collezionisti': ['per prestigiosi collezionisti', 'per appassionati di rarità'],
            'Amanti del vintage': ['per cultori del vintage autentico', 'per chi apprezza la storia'],
            'Appassionati di lusso': ['per veri amanti del lusso', 'per intenditori di eccellenza'],
            'Chi ama distinguersi': ['per personalità distintive', 'per chi non accetta compromessi']
        },
        'emotivo': {
            'Intenditrici': ['per cuori che sanno riconoscere la bellezza', 'per anime raffinate'],
            'Collezionisti': ['per chi colleziona emozioni', 'per chi ama i tesori rari'],
            'Amanti del vintage': ['per chi si innamora delle storie del passato', 'per romantici del vintage'],
            'Appassionati di lusso': ['per chi vive il lusso con il cuore', 'per spiriti che sognano in grande'],
            'Chi ama distinguersi': ['per chi vuole brillare di luce propria', 'per personalità uniche']
        },
        'amichevole': {
            'Intenditrici': ['perfetto per te che sai cosa vuoi', 'ideale per il tuo stile'],
            'Collezionisti': ['una chicca per la tua collezione', 'che amerai aggiungere alla tua raccolta'],
            'Amanti del vintage': ['che ti farà innamorare del passato', 'perfetto per il tuo guardaroba vintage'],
            'Appassionati di lusso': ['per coccolarti con stile', 'che ti farà sentire speciale'],
            'Chi ama distinguersi': ['per essere sempre al top', 'che ti renderà unica']
        },
        'professionale': {
            'Intenditrici': ['riservato a esperte del settore', 'per competenti valutazioni'],
            'Collezionisti': ['destinato a collezioni specializzate', 'per portfolio di valore'],
            'Amanti del vintage': ['catalogato per esperti vintage', 'per archivi storici'],
            'Appassionati di lusso': ['selezionato per clientela qualificata', 'per investimenti di prestigio'],
            'Chi ama distinguersi': ['riservato a segmenti premium', 'per positioning esclusivo']
        },
        'esclusivo': {
            'Intenditrici': ['riservato alle più esigenti', 'per élite femminile'],
            'Collezionisti': ['per collezioni di altissimo livello', 'riservato ai grandi collezionisti'],
            'Amanti del vintage': ['per i più raffinati cultori vintage', 'esclusivo per veri intenditori'],
            'Appassionati di lusso': ['per i vertici del lusso mondiale', 'riservato alla clientela VIP'],
            'Chi ama distinguersi': ['per personalità di spicco', 'riservato a chi comanda le tendenze']
        }
    }
    
    options = target_map.get(stile, target_map['elegante']).get(target, [])
    return random.choice(options) if options else ""

def _get_aggettivo_brand_per_stile(brand: str, genere: str, stile: str) -> str:
    """Aggettivi brand personalizzati per stile"""
    
    brand_stili = {
        'elegante': {
            'Dior': ['iconica', 'raffinata', 'leggendaria', 'distintiva'],
            'Chanel': ['intramontabile', 'classica', 'elegante', 'senza tempo'],
            'Louis Vuitton': ['prestigiosa', 'elegante', 'iconica', 'raffinata'],
            'Hermès': ['leggendaria', 'esclusiva', 'prestigiosa', 'sublime'],
            'Gucci': ['distintiva', 'elegante', 'iconica', 'sofisticata'],
            'Prada': ['sofisticata', 'elegante', 'moderna', 'raffinata']
        },
        'emotivo': {
            'Dior': ['che fa sognare', 'dal fascino irresistibile', 'che emoziona', 'magnetica'],
            'Chanel': ['dal fascino eterno', 'che conquista il cuore', 'indimenticabile', 'ammaliante'],
            'Louis Vuitton': ['che fa innamorare', 'dal fascino regale', 'che incanta', 'seducente'],
            'Hermès': ['da sogno', 'che toglie il fiato', 'celestiale', 'mozzafiato'],
            'Gucci': ['che cattura l\'anima', 'affascinante', 'che strega', 'irresistibile'],
            'Prada': ['che stupisce', 'coinvolgente', 'che colpisce', 'travolgente']
        },
        'amichevole': {
            'Dior': ['fantastica', 'meravigliosa', 'stupenda', 'eccezionale'],
            'Chanel': ['bellissima', 'favolosa', 'grandiosa', 'splendida'],
            'Louis Vuitton': ['fantastica', 'incredibile', 'straordinaria', 'magnifica'],
            'Hermès': ['pazzesca', 'incredibile', 'super', 'favolosa'],
            'Gucci': ['stupenda', 'fantastica', 'bellissima', 'grandiosa'],
            'Prada': ['figata', 'bellissima', 'cool', 'fantastica']
        },
        'professionale': {
            'Dior': ['riconosciuta', 'certificata', 'autentica', 'originale'],
            'Chanel': ['documentata', 'verificata', 'garantita', 'accertata'],
            'Louis Vuitton': ['autenticata', 'certificata', 'originale', 'garantita'],
            'Hermès': ['verificata', 'autentica', 'documentata', 'certificata'],
            'Gucci': ['originale', 'autentica', 'verificata', 'garantita'],
            'Prada': ['certificata', 'autentica', 'originale', 'documentata']
        },
        'esclusivo': {
            'Dior': ['di suprema eleganza', 'regale', 'maestosa', 'principesca'],
            'Chanel': ['di rara perfezione', 'aristocratica', 'nobile', 'sublime'],
            'Louis Vuitton': ['di lusso assoluto', 'imperiale', 'regale', 'magnifica'],
            'Hermès': ['di eccellenza suprema', 'leggendaria', 'mitica', 'divina'],
            'Gucci': ['di straordinaria classe', 'principesca', 'nobile', 'magnifica'],
            'Prada': ['di raffinatezza suprema', 'aristocratica', 'sublime', 'regale']
        }
    }
    
    stile_aggettivi = brand_stili.get(stile, brand_stili['elegante'])
    aggettivi = stile_aggettivi.get(brand, ['elegante', 'raffinata', 'bella', 'pregiata'])
    aggettivo_base = random.choice(aggettivi)
    
    return concordanza_aggettivo(aggettivo_base, genere)

def _get_templates_per_stile(stile: str, nome_completo: str, desc_materiali: str, desc_condizioni: str, 
                            desc_rarita: str, desc_target: str, aggettivo_brand: str,
                            art_det: str, art_indet: str, genere: str, vintage: bool) -> List[str]:
    """Template specifici per ogni stile"""
    
    suffisso = 'a' if genere == 'f' else 'o'
    
    templates_per_stile = {
        'elegante': [
            f"Raffinatezza senza tempo: quest{suffisso} {nome_completo} {desc_materiali} rappresenta l'eccellenza, {desc_condizioni}.",
            f"{aggettivo_brand.capitalize()} e {concordanza_aggettivo('senza tempo', genere)}, {art_det} {nome_completo} {desc_materiali} è l'incarnazione dell'eleganza.",
            f"{art_indet.capitalize()} {nome_completo} {desc_rarita} {desc_materiali}: {desc_condizioni}, un classico dell'eleganza.",
            f"Eleganza pura: {nome_completo} {desc_materiali}, {desc_condizioni}. Un capolavoro di stile.",
            f"L'essenza del lusso: quest{suffisso} {nome_completo} {desc_materiali} è {desc_rarita} e {desc_condizioni}.",
            f"Perfett{suffisso} {desc_target}: {nome_completo} {desc_materiali}, raffinat{suffisso} e {desc_condizioni}.",
            f"Intramontabile eleganza: {art_det} {nome_completo} {desc_materiali}, {desc_rarita}, è {desc_condizioni}.",
            f"Classe innata: quest{suffisso} {nome_completo} {desc_materiali} incarna la perfezione, {desc_condizioni}."
        ],
        
        'emotivo': [
            f"Un incontro che toglie il fiato: quest{suffisso} magnific{suffisso} {nome_completo} {desc_materiali} {desc_condizioni}.",
            f"Il tuo cuore batterà forte: {art_det} {nome_completo} {desc_materiali} è {aggettivo_brand} e {desc_condizioni}.",
            f"Amore a prima vista: {nome_completo} {desc_materiali}, {desc_rarita} e {desc_condizioni}.",
            f"Un sogno che diventa realtà: quest{suffisso} {nome_completo} {desc_materiali} ti farà innamorare.",
            f"L'emozione di possedere un tesoro: {art_det} {nome_completo} {desc_materiali}, {desc_condizioni}.",
            f"Per chi sa riconoscere la bellezza: {nome_completo} {desc_materiali}, {desc_rarita} e {desc_condizioni}.",
            f"Un pezzo che racconta storie: {art_det} {nome_completo} {desc_materiali} {desc_condizioni}.",
            f"Il fascino che conquista: quest{suffisso} {nome_completo} {desc_materiali} è davvero {desc_rarita}."
        ],
        
        'amichevole': [
            f"Che bellezza! Quest{suffisso} {nome_completo} {desc_materiali} è proprio {desc_condizioni}.",
            f"Ti piacerà sicuramente: {art_det} {nome_completo} {desc_materiali} è {aggettivo_brand} e {desc_condizioni}!",
            f"Dai un'occhiata a quest{suffisso}: {nome_completo} {desc_materiali}, {desc_rarita} e {desc_condizioni}.",
            f"Perfett{suffisso} per te: {art_det} {nome_completo} {desc_materiali} è proprio quello che cercavi!",
            f"Una vera scoperta: quest{suffisso} {nome_completo} {desc_materiali} {desc_condizioni}.",
            f"Te ne innamorerai: {nome_completo} {desc_materiali}, {desc_rarita} e {desc_condizioni}.",
            f"Un affare da non perdere: {art_det} {nome_completo} {desc_materiali}, {desc_condizioni}!",
            f"Guarda che meraviglia: quest{suffisso} {nome_completo} {desc_materiali} è davvero speciale."
        ],
        
        'professionale': [
            f"Articolo di qualità: {nome_completo} {desc_materiali}, {desc_condizioni}, con certificazione di autenticità.",
            f"Specifiche tecniche: {art_det} {nome_completo} {desc_materiali} è {desc_condizioni} e {desc_rarita}.",
            f"Articolo {concordanza_aggettivo(aggettivo_brand, 'm')}: {nome_completo} {desc_materiali}, classificat{suffisso} {desc_condizioni}.",
            f"Dettagli del prodotto: quest{suffisso} {nome_completo} {desc_materiali} presenta ottime caratteristiche.",
            f"Articolo da collezione: {art_det} {nome_completo} {desc_materiali}, {desc_rarita} e {desc_condizioni}.",
            f"Scheda prodotto: {nome_completo} {desc_materiali}, {desc_condizioni}, {desc_target}.",
            f"Caratteristiche principali: {art_det} {nome_completo} {desc_materiali} è {desc_condizioni}.",
            f"Valutazione: quest{suffisso} {nome_completo} {desc_materiali} è classificat{suffisso} come {desc_rarita}."
        ],
        
        'esclusivo': [
            f"Per pochi eletti: quest{suffisso} {nome_completo} {desc_materiali} è di rara magnificenza, {desc_condizioni}.",
            f"Lusso supremo: {art_det} {nome_completo} {desc_materiali} rappresenta l'apice dell'eccellenza.",
            f"Esclusività assoluta: {nome_completo} {desc_materiali}, {desc_rarita} e {desc_condizioni}.",
            f"Privilegio riservato: quest{suffisso} {nome_completo} {desc_materiali} è per {desc_target}.",
            f"Rarità di classe: {art_det} {nome_completo} {desc_materiali}, {desc_condizioni}, è {desc_rarita}.",
            f"Eccellenza riservata: {nome_completo} {desc_materiali}, {aggettivo_brand} e {desc_condizioni}.",
            f"Status symbol: quest{suffisso} {nome_completo} {desc_materiali} definisce l'esclusività.",
            f"Per connoisseur: {art_det} {nome_completo} {desc_materiali} è {desc_rarita} e {desc_condizioni}."
        ]
    }
    
    return templates_per_stile.get(stile, templates_per_stile['elegante'])

def _seleziona_template_intelligente(templates: List[str], nome_completo: str, brand: str, stile: str) -> str:
    """Selezione intelligente del template con controlli qualità avanzati"""
    templates_validi = []
    
    for template in templates:
        # Pulizia avanzata
        frase_pulita = re.sub(r'\s+', ' ', template)
        frase_pulita = frase_pulita.replace(' ,', ',').replace('  ', ' ').strip()
        frase_pulita = frase_pulita.replace(': ,', ':').replace(', ,', ',').replace(' :', ':')
        frase_pulita = frase_pulita.replace('.,', '.').replace(',.', '.').replace('..', '.')
        frase_pulita = frase_pulita.replace('  ', ' ').replace(' .', '.')
        
        # Controlli qualità
        problemi = [
            ': ,', ': .', ' :', 'None', ', .', ' ,', '  ', 
            'e e ', 'il il ', 'la la ', 'un un ', 'una una ',
            f'{brand} {brand}', 'è è', 'in in'
        ]
        
        # Verifica lunghezza minima e massima
        if len(frase_pulita) < 20 or len(frase_pulita) > 300:
            continue
            
        # Verifica assenza di problemi
        if not any(problema in frase_pulita for problema in problemi):
            # Verifica coerenza grammaticale base
            if frase_pulita.count('.') <= 2 and frase_pulita.count(',') <= 5:
                templates_validi.append(frase_pulita)
    
    # Fallback intelligente per stile
    if not templates_validi:
        fallbacks = {
            'elegante': f"Raffinato {nome_completo}, un classico dell'eleganza.",
            'emotivo': f"Un {nome_completo} che conquista il cuore.",
            'amichevole': f"Bellissimo {nome_completo}, perfetto per te!",
            'professionale': f"Articolo {nome_completo} di qualità certificata.",
            'esclusivo': f"Esclusivo {nome_completo} per pochi eletti."
        }
        return fallbacks.get(stile, f"Elegante {nome_completo} {brand}.")
    
    return random.choice(templates_validi)

def _genera_call_to_action_per_stile(termini_commerciali: List[str], stile: str) -> str:
    """Call to action personalizzate per stile"""
    
    call_to_actions_per_stile = {
        'elegante': [
            "Ti aspetta un'offerta raffinata nella tua area riservata.",
            "Abbiamo preparato per te una proposta esclusiva: controlla subito.",
            "Una sorpresa elegante ti attende tra i tuoi messaggi privati.",
            "La tua offerta personalizzata è pronta: dai un'occhiata.",
            "Ti abbiamo riservato condizioni vantaggiose in esclusiva."
        ],
        
        'emotivo': [
            "Il tuo cuore batterà forte per l'offerta che ti abbiamo inviato!",
            "Una sorpresa meravigliosa ti aspetta: controlla i tuoi messaggi.",
            "Abbiamo pensato a te con un'offerta speciale che ti emozionerà.",
            "Ti farà sorridere l'offerta personalizzata che troverai nel tuo account.",
            "Una bella sorpresa ti aspetta: l'abbiamo appena inviata!"
        ],
        
        'amichevole': [
            "Hey, controlla i tuoi messaggi: c'è una super offerta per te!",
            "Ti abbiamo fatto un prezzo speciale, vai a vedere!",
            "Psst... c'è uno sconto extra solo per te, dai un'occhiata!",
            "Buone notizie: ti abbiamo riservato un'offerta fantastica!",
            "Corri a controllare: c'è una sorpresa che ti piacerà!"
        ],
        
        'professionale': [
            "Consultare l'area personale per visualizzare l'offerta dedicata.",
            "Proposta commerciale personalizzata disponibile nel proprio account.",
            "Offerta riservata attiva: verificare i messaggi ricevuti.",
            "Condizioni agevolate applicate: consultare i dettagli nell'area privata.",
            "Proposta esclusiva elaborata: disponibile per la valutazione."
        ],
        
        'esclusivo': [
            "Un privilegio riservato a lei: l'offerta esclusiva è nel suo account privato.",
            "L'abbiamo selezionata per un'opportunità unica: controlli immediatamente.",
            "Riservato esclusivamente: la sua offerta personalizzata l'attende.",
            "Accesso privilegiato: la proposta esclusiva è stata attivata per lei.",
            "Status riservato: la sua offerta di classe è pronta per la consultazione."
        ]
    }
    
    call_actions = call_to_actions_per_stile.get(stile, call_to_actions_per_stile['elegante'])
    
    # Aggiungi termini personalizzati se presenti
    if termini_commerciali and stile != 'professionale':
        for termine in termini_commerciali[:2]:  # Max 2 termini
            if 'sconto' in termine.lower():
                if stile == 'emotivo':
                    call_actions.append(f"Ti emozionerà lo {termine} che ti abbiamo riservato!")
                elif stile == 'amichevole':
                    call_actions.append(f"Fantastico! Ti abbiamo fatto uno {termine} speciale!")
                elif stile == 'esclusivo':
                    call_actions.append(f"Privilegio esclusivo: le abbiamo riservato uno {termine} d'élite.")
            elif 'offerta' in termine.lower():
                if stile == 'emotivo':
                    call_actions.append(f"Il tuo cuore salterà per l'{termine} che ti aspetta!")
                elif stile == 'amichevole':
                    call_actions.append(f"Wow! C'è un'{termine} pazzesca che ti abbiamo preparato!")
                elif stile == 'esclusivo':
                    call_actions.append(f"Accesso riservato: la sua {termine} esclusiva è attiva.")
    
    return random.choice(call_actions)

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

@app.route('/api/genera-frase/<int:id>', methods=['GET'])
@handle_errors
@log_request_info
def genera_frase(id):
    """Genera una frase personalizzata per l'articolo con stile selezionabile"""
    try:
        articolo = Articolo.query.get_or_404(id)
        
        # Parametro stile dalla query string
        stile = request.args.get('stile', 'elegante')
        
        # Validazione stili disponibili
        stili_disponibili = ['elegante', 'emotivo', 'amichevole', 'professionale', 'esclusivo']
        if stile not in stili_disponibili:
            stile = 'elegante'
        
        # Estrai e processa i dati
        colore = articolo.colore.strip() if articolo.colore else ''
        materiale = articolo.materiale.strip() if articolo.materiale else ''
        keywords = articolo._parse_keywords()
        termini_commerciali = articolo._parse_termini_commerciali()
        condizioni = articolo.condizioni.strip() if articolo.condizioni else ''
        rarita = articolo.rarita.strip() if articolo.rarita else ''
        target = articolo.target.strip() if articolo.target else ''
        
        # Classifica keywords con cache
        keywords_str = ','.join(keywords)
        keywords_classificate = classifica_keywords_cached(keywords_str) if keywords_str else {}
        
        # Genera la frase con lo stile selezionato
        frase = genera_frase_personalizzata_ottimizzata(
            articolo.brand, articolo.nome, colore, materiale, keywords_classificate,
            condizioni, rarita, articolo.vintage, target, termini_commerciali, stile
        )
        
        logger.info(f"Frase generata per articolo {id} con stile '{stile}'")
        return jsonify({
            'frase': frase,
            'stile': stile,
            'stili_disponibili': stili_disponibili
        })
        
    except Exception as e:
        logger.error(f"Errore nella generazione frase per articolo {id}: {e}")
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

@app.route('/api/statistiche-frasi', methods=['GET'])
@handle_errors
@log_request_info
def get_statistiche_frasi():
    """Ottiene statistiche sulle frasi generate"""
    try:
        total_articoli_con_frasi = len(FRASE_MEMORY_CACHE)
        total_frasi_generate = sum(len(frasi) for frasi in FRASE_MEMORY_CACHE.values())
        
        # Statistiche per stile (dalle cache keys)
        stats_stili = {}
        for cache_key in FRASE_MEMORY_CACHE:
            if '_' in cache_key:
                parts = cache_key.split('_')
                if len(parts) >= 5:  # brand_nome_colore_materiale_stile
                    stile = parts[-1]
                    stats_stili[stile] = stats_stili.get(stile, 0) + len(FRASE_MEMORY_CACHE[cache_key])
        
        # *** CORREZIONE: PARSING CORRETTO CACHE KEY *** - Articoli più attivi (con più frasi generate)
        articoli_attivi = {}  # Uso dict per raggruppare
        
        for cache_key, frasi in FRASE_MEMORY_CACHE.items():
            if '_' in cache_key:
                try:
                    # *** PARSING MIGLIORATO: gestisce nomi con underscores ***
                    parts = cache_key.split('_')
                    if len(parts) >= 5:  # brand_nome_colore_materiale_stile
                        brand = parts[0]
                        stile = parts[-1]
                        materiale = parts[-2] if parts[-2] != 'none' else ''
                        colore = parts[-3] if parts[-3] != 'none' else ''
                        
                        # Il nome è tutto quello che rimane nel mezzo
                        nome_parts = parts[1:-3]  # Tutto tranne brand, colore, materiale, stile
                        nome = '_'.join(nome_parts) if nome_parts else 'Articolo sconosciuto'
                        nome = nome.replace('_', ' ')  # Riconverti underscores in spazi
                        
                        # Creo identificatore unico per articolo
                        articolo_id = f"{brand} - {nome}".strip()
                        if not articolo_id.endswith(' - '):
                            if articolo_id not in articoli_attivi:
                                articoli_attivi[articolo_id] = 0
                            articoli_attivi[articolo_id] += len(frasi)
                except (IndexError, AttributeError) as e:
                    # In caso di errore, salta questo elemento
                    continue
        
        # Converto in lista e ordino
        articoli_lista = [
            {'nome': nome, 'frasi_generate': count} 
            for nome, count in articoli_attivi.items()
        ]
        articoli_lista.sort(key=lambda x: x['frasi_generate'], reverse=True)
        
        return jsonify({
            'total_articoli_con_frasi': total_articoli_con_frasi,
            'total_frasi_generate': total_frasi_generate,
            'stats_stili': stats_stili,
            'articoli_piu_attivi': articoli_lista[:10],  # Top 10
            'dimensione_cache': len(FRASE_MEMORY_CACHE)
        })
        
    except Exception as e:
        logger.error(f"Errore nel recupero statistiche frasi: {e}")
        raise

@app.route('/api/pulisci-cache-frasi', methods=['POST'])
@handle_errors
@log_request_info
def pulisci_cache_frasi_endpoint():
    """Endpoint per pulire la cache delle frasi"""
    try:
        pulisci_cache_frasi()
        
        logger.info("Cache frasi pulita manualmente")
        return jsonify({
            'message': 'Cache delle frasi pulita con successo',
            'nuova_dimensione_cache': len(FRASE_MEMORY_CACHE)
        })
        
    except Exception as e:
        logger.error(f"Errore nella pulizia cache frasi: {e}")
        raise

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
