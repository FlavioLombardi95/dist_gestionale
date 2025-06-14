from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime, timezone
import random
import re
import logging
from functools import wraps, lru_cache
from typing import Dict, List, Optional, Tuple
import time
from sqlalchemy.exc import OperationalError, DisconnectionError

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
    """Configura la connessione al database con fallback automatico"""
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Per test locale, forza Supabase se richiesto
    FORCE_SUPABASE = os.environ.get('FORCE_SUPABASE', 'false').lower() == 'true'
    
    if DATABASE_URL or FORCE_SUPABASE:
        try:
            # Se non c'è DATABASE_URL ma FORCE_SUPABASE è true, mostra istruzioni
            if not DATABASE_URL and FORCE_SUPABASE:
                logger.error("❌ FORCE_SUPABASE attivo ma DATABASE_URL non configurato!")
                logger.error("📋 Per usare Supabase, configura DATABASE_URL con:")
                logger.error("   export DATABASE_URL='postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres'")
                logger.error("🔗 Ottieni l'URL da: Supabase Dashboard → Settings → Database → Connection string")
                raise Exception("DATABASE_URL richiesto per FORCE_SUPABASE")
            
            # Produzione: Supabase PostgreSQL - Configurazione ottimizzata
            if 'supabase.co' in DATABASE_URL and 'sslmode' not in DATABASE_URL:
                DATABASE_URL += '?sslmode=require'
            
            if DATABASE_URL.startswith('postgres://'):
                DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
            
            app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_pre_ping': True,
                'pool_recycle': 300,      # Aumentato a 5 minuti
                'pool_size': 5,           # Aumentato a 5 connessioni base
                'max_overflow': 10,       # Aumentato a 15 connessioni totali
                'pool_timeout': 30,       # Aumentato timeout a 30s
                'pool_reset_on_return': 'commit',
                'connect_args': {
                    'sslmode': 'require',
                    'connect_timeout': 30,    # Timeout connessione 30s
                    'application_name': 'gestionale_vintage',
                    'keepalives_idle': 600,   # Keep-alive ogni 10 minuti
                    'keepalives_interval': 30,
                    'keepalives_count': 3
                }
            }
            
            # Test connessione con retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    from sqlalchemy import create_engine, text
                    test_engine = create_engine(DATABASE_URL, **app.config['SQLALCHEMY_ENGINE_OPTIONS'])
                    
                    logger.info(f"🔄 Tentativo connessione Supabase {attempt + 1}/{max_retries}...")
                    
                    # Test con timeout più lungo
                    with test_engine.connect() as test_conn:
                        result = test_conn.execute(text('SELECT 1 as test'))
                        test_result = result.fetchone()
                        test_conn.commit()
                        
                        if test_result and test_result[0] == 1:
                            logger.info("✅ Connesso a Supabase PostgreSQL (testato)")
                            test_engine.dispose()
                            return  # Successo!
                    
                    test_engine.dispose()
                    
                except Exception as test_error:
                    logger.warning(f"❌ Tentativo {attempt + 1} fallito: {test_error}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(2 ** attempt)  # Backoff esponenziale
                    else:
                        raise test_error
            
        except Exception as e:
            logger.error(f"❌ Errore connessione Supabase dopo {max_retries} tentativi: {e}")
            
            # Solo fallback se non stiamo forzando Supabase
            if not FORCE_SUPABASE:
                logger.warning("🔄 Fallback a SQLite per alta disponibilità")
                
                # FALLBACK: SQLite in produzione per alta disponibilità
                app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gestionale_production.db'
                app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                    'pool_pre_ping': True,
                    'pool_recycle': 3600,
                    'pool_size': 5,
                    'max_overflow': 10
                }
                logger.info("🔗 Usando SQLite di emergenza in produzione")
            else:
                logger.error("💥 FORCE_SUPABASE attivo - non uso fallback SQLite")
                raise e
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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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
            # Chiudi connessioni in caso di errore
            try:
                db.session.rollback()
                db.session.close()
            except:
                pass
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
                
                # Aggiungi dati di test per sviluppo locale
                articoli_test = [
                    Articolo(
                        nome="Borsa Speedy 30",
                        brand="Louis Vuitton",
                        colore="Marrone",
                        materiale="Canvas Monogram",
                        keywords="borsa, speedy, monogram, classica",
                        termini_commerciali="autentica, vintage, collezione",
                        condizioni="Ottime",
                        rarita="Comune",
                        vintage=True,
                        target="Donna"
                    ),
                    Articolo(
                        nome="Sciarpa Cashmere",
                        brand="Hermès",
                        colore="Blu Navy",
                        materiale="Cashmere",
                        keywords="sciarpa, cashmere, elegante",
                        termini_commerciali="lusso, artigianale, francese",
                        condizioni="Eccellenti",
                        rarita="Raro",
                        vintage=False,
                        target="Unisex"
                    ),
                    Articolo(
                        nome="Orologio Submariner",
                        brand="Rolex",
                        colore="Nero",
                        materiale="Acciaio Inossidabile",
                        keywords="orologio, submariner, diving, automatico",
                        termini_commerciali="investimento, collezione, svizzero",
                        condizioni="Eccellenti",
                        rarita="Molto Raro",
                        vintage=False,
                        target="Uomo"
                    ),
                    Articolo(
                        nome="Sneakers Air Jordan 1",
                        brand="Nike",
                        colore="Rosso e Bianco",
                        materiale="Pelle",
                        keywords="sneakers, jordan, basketball, retro",
                        termini_commerciali="limited edition, streetwear, iconica",
                        condizioni="Buone",
                        rarita="Raro",
                        vintage=True,
                        target="Unisex"
                    ),
                    Articolo(
                        nome="Giacca Blazer",
                        brand="Chanel",
                        colore="Nero",
                        materiale="Tweed",
                        keywords="giacca, blazer, elegante, formale",
                        termini_commerciali="haute couture, parigina, sartoriale",
                        condizioni="Eccellenti",
                        rarita="Molto Raro",
                        vintage=False,
                        target="Donna"
                    )
                ]
                
                for articolo in articoli_test:
                    db.session.add(articolo)
                
                db.session.commit()
                logger.info(f"✅ Database di sviluppo inizializzato con {len(articoli_test)} articoli di test")
        except Exception as e:
            logger.error(f"Errore nell'inizializzazione del database: {e}")
            raise

init_database()

# ===============================
# GESTIONE CONNESSIONI DATABASE
# ===============================

@app.teardown_appcontext
def close_db_session(error):
    """Chiude la sessione database dopo ogni richiesta"""
    try:
        db.session.remove()
    except Exception as e:
        logger.warning(f"Errore nella chiusura sessione DB: {e}")

@app.after_request
def after_request(response):
    """Cleanup dopo ogni richiesta"""
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Errore nel commit: {e}")
    finally:
        db.session.close()
    return response

# Circuit Breaker per Supabase
SUPABASE_CIRCUIT_BREAKER = {
    'failures': 0,
    'last_failure': 0,
    'threshold': 5,  # Dopo 5 fallimenti consecutivi
    'timeout': 300   # Aspetta 5 minuti prima di riprovare
}

def is_circuit_open():
    """Controlla se il circuit breaker è aperto"""
    if SUPABASE_CIRCUIT_BREAKER['failures'] >= SUPABASE_CIRCUIT_BREAKER['threshold']:
        if time.time() - SUPABASE_CIRCUIT_BREAKER['last_failure'] < SUPABASE_CIRCUIT_BREAKER['timeout']:
            return True
        else:
            # Reset dopo timeout
            SUPABASE_CIRCUIT_BREAKER['failures'] = 0
    return False

def record_failure():
    """Registra un fallimento nel circuit breaker"""
    SUPABASE_CIRCUIT_BREAKER['failures'] += 1
    SUPABASE_CIRCUIT_BREAKER['last_failure'] = time.time()
    logger.warning(f"Circuit breaker: {SUPABASE_CIRCUIT_BREAKER['failures']} fallimenti")

def record_success():
    """Registra un successo (reset circuit breaker)"""
    SUPABASE_CIRCUIT_BREAKER['failures'] = 0

def retry_db_operation(func, max_retries=2, delay=0.5):
    """Retry automatico per operazioni database con circuit breaker"""
    
    # Se circuit breaker è aperto, fallisci immediatamente
    if is_circuit_open():
        logger.warning("Circuit breaker aperto - operazione saltata")
        raise Exception("Database temporaneamente non disponibile")
    
    for attempt in range(max_retries):
        try:
            result = func()
            record_success()  # Reset circuit breaker su successo
            return result
            
        except (OperationalError, DisconnectionError) as e:
            error_msg = str(e).lower()
            
            if "max client connections reached" in error_msg or "connection" in error_msg:
                record_failure()
                
                if attempt < max_retries - 1:
                    wait_time = delay * (2 ** attempt)  # Backoff esponenziale
                    logger.warning(f"Tentativo {attempt + 1} fallito, retry tra {wait_time}s: {e}")
                    time.sleep(wait_time)
                    
                    # Forza chiusura connessioni
                    try:
                        db.session.close()
                        db.engine.dispose()
                    except:
                        pass
                    continue
                else:
                    logger.error(f"Tutti i {max_retries} tentativi falliti: {e}")
                    raise
            else:
                record_failure()
                raise
                
        except Exception as e:
            record_failure()
            logger.error(f"Errore non recuperabile: {e}")
            raise

# ===============================
# FUNZIONI HELPER OTTIMIZZATE
# ===============================

@lru_cache(maxsize=128)
def get_tipo_articolo_cached(nome: str) -> str:
    """Versione cached per riconoscere il tipo di articolo"""
    return riconosci_tipo_articolo(nome)

@lru_cache(maxsize=256)
def get_genere_cached(tipo_articolo: str) -> str:
    """🎯 MAPPATURA COMPLETA prodotto-genere per concordanza perfetta"""
    tipo_lower = tipo_articolo.lower()
    
    # Mappatura completa prodotti femminili (ESPANSA)
    generi_femminili = {
        'borsa', 'borsetta', 'pochette', 'clutch', 'tracolla', 'shopper', 'bauletto',
        'scarpe', 'scarpa', 'decolletè', 'sneakers', 'ballerine', 'sandali', 'stivali',
        'giacca', 'giacchin', 'blazer', 'giacchetta',
        'camicia', 'camicetta', 'blusa', 'canotta', 'top',
        'gonna', 'minigonna', 'gonna lunga',
        'felpa', 'felpin', 'hoodie', 'maglia', 'maglietta', 't-shirt', 'tshirt',
        'cintura', 'cintola',
        'sciarpa', 'sciarpina', 'foulard', 'stola', 'pashmina',
        'collana', 'collanina', 'catenina',
        'valigia', 'valigetta', 'trolley',
        'spilla', 'spilletta'
    }
    
    # Mappatura completa prodotti maschili (ESPANSA)
    generi_maschili = {
        'orologio', 'orologin', 'cronografo', 'segnatempo', 'watch',
        'portafoglio', 'portafogli', 'portamonete', 'wallet',
        'occhiali', 'occhiale', 'sunglasses', 'glasses',
        'piumino', 'puffer', 'down jacket',
        'anello', 'anellino', 'ring', 'fedina',
        'cappello', 'cappellin', 'berretto', 'basco',
        'cappotto', 'cappottin', 'paltò', 'montgomery',
        'giubbotto', 'giubotto', 'giubbino', 'bomber',
        'pantalone', 'pantaloni', 'jeans', 'jean',
        'costume', 'boxer', 'slip',
        'zaino', 'zainettin', 'marsupio',
        'bracciale', 'braccialetto',
        'gemello', 'gemelli', 'bottone',
        'articolo', 'pezzo', 'capo', 'accessorio', 'vestito'
    }
    
    # Controllo diretto
    if tipo_lower in generi_femminili:
        return 'f'
    elif tipo_lower in generi_maschili:
        return 'm'
    
    # Controllo per suffissi e pattern
    if any(tipo_lower.endswith(suff) for suff in ['ina', 'etta']):
        return 'f'
    elif any(tipo_lower.endswith(suff) for suff in ['ino', 'etto', 'one']):
        return 'm'
    
    # Default per parole generiche - SEMPRE maschile
    return 'm'

def riconosci_tipo_articolo(nome: str) -> str:
    """Riconosce il tipo di articolo dal nome con priorità per riconoscimento diretto"""
    nome_lower = nome.lower()
    
    # CONTROLLO DIRETTO per tipi principali (priorità massima - ESPANSO)
    if 'orologio' in nome_lower or 'watch' in nome_lower:
        return 'orologio'
    if 'portafoglio' in nome_lower or 'wallet' in nome_lower:
        return 'portafoglio'
    if 'bracciale' in nome_lower or 'bracelet' in nome_lower or 'love' in nome_lower:  # NUOVO
        return 'bracciale'
    if 'cintura' in nome_lower or 'belt' in nome_lower or 'cinta' in nome_lower:  # NUOVO
        return 'cintura'
    if 'collana' in nome_lower or 'necklace' in nome_lower or 'chain' in nome_lower:  # NUOVO
        return 'collana'
    if 'borsa' in nome_lower or 'bag' in nome_lower:
        return 'borsa'
    if 'scarpa' in nome_lower or 'scarpe' in nome_lower or 'sneakers' in nome_lower or 'stivali' in nome_lower:
        return 'scarpe'
    if 'giacca' in nome_lower or 'blazer' in nome_lower or 'jacket' in nome_lower or 'cappotto' in nome_lower or 'trench' in nome_lower:
        return 'giacca'
    if 'piumino' in nome_lower or 'down' in nome_lower or 'giubbotto' in nome_lower:  # NUOVO
        return 'piumino'
    if 'anello' in nome_lower or 'ring' in nome_lower:
        return 'anello'
    if 'felpa' in nome_lower or 'hoodie' in nome_lower or 'sweatshirt' in nome_lower:
        return 'felpa'
    if 'camicia' in nome_lower or 'shirt' in nome_lower:
        return 'camicia'
    
    # Mappatura ottimizzata con più varianti (ESPANSA)
    tipo_mapping = {
        'borsa': ['borsa', 'borse', 'bag', 'clutch', 'pochette', 'zaino', 'trolley', 'valigia', 'handbag', 'bauletto', 'tracolla', 'shopping'],
        'scarpe': ['scarpa', 'scarpe', 'sandalo', 'sandali', 'boot', 'stivale', 'stivali', 'sneaker', 'sneakers', 'decollete', 'pump', 'mocassino', 'ballerina', 'ciabatta'],
        'orologio': ['orologio', 'watch', 'cronografo', 'segnatempo'],
        'portafoglio': ['portafoglio', 'portafogli', 'wallet', 'portamonete'],
        'occhiali': ['occhiali', 'occhiale', 'sunglasses', 'glasses'],
        'piumino': ['piumino', 'puffer', 'giubbotto', 'giacca', 'down jacket'],
        'vestito': ['vestito', 'abito', 'dress', 'gonna', 'skirt', 'tuta', 'jumpsuit'],
        'top': ['camicia', 'shirt', 'blusa', 'top', 'maglia', 't-shirt', 'polo', 'cardigan', 'maglione', 'felpa'],
        'pantaloni': ['pantalone', 'pantaloni', 'jeans', 'short', 'bermuda', 'leggings', 'jogger'],
        'giacca': ['giacca', 'blazer', 'coat', 'cappotto', 'giubbotto', 'parka', 'trench', 'mantello'],
        'anello': ['anello', 'ring', 'fedina', 'fede'],
        'felpa': ['felpa', 'hoodie', 'sweatshirt', 'pullover'],
        'camicia': ['camicia', 'shirt', 'blusa', 'chemise'],
        'accessorio': ['accessorio', 'accessori', 'cintura', 'belt', 'sciarpa', 'foulard', 'cappello', 'guanto', 'gioiello', 'collana', 'bracciale']
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
    
    # Controllo finale per parole che indicano tipi generici
    if 'articolo' in nome_lower or 'pezzo' in nome_lower or 'capo' in nome_lower:
        return 'articolo'
    
    # Se proprio non riesce a identificare, usa "articolo" come default neutro
    return 'articolo'

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

def concordanza_aggettivo(aggettivo: str, genere: str, tipo_articolo: str = "") -> str:
    """Converte aggettivi al genere corretto con gestione plurali - VERSIONE CORRETTA"""
    if not aggettivo or not genere:
        return aggettivo or ""
        
    # *** CORREZIONE: Validazione input ***    
    genere = genere.lower().strip()
    if genere not in ['m', 'f']:
        genere = 'm'  # Default maschio se genere non valido
        
    aggettivo = aggettivo.strip()
    if not aggettivo:
        return ""
    
    # *** NUOVA GESTIONE PLURALI ***
    is_plural = tipo_articolo in ['scarpe', 'occhiali', 'pantaloni']
        
            # **MAPPATURA ESTESA** - Con supporto plurali
    concordanze = {
        'nero': {'m': 'nero', 'f': 'nera', 'mp': 'neri', 'fp': 'nere'},
        'bianco': {'m': 'bianco', 'f': 'bianca', 'mp': 'bianchi', 'fp': 'bianche'},
        'rosso': {'m': 'rosso', 'f': 'rossa', 'mp': 'rossi', 'fp': 'rosse'},
        'grigio': {'m': 'grigio', 'f': 'grigia', 'mp': 'grigi', 'fp': 'grigie'},
        'giallo': {'m': 'giallo', 'f': 'gialla', 'mp': 'gialli', 'fp': 'gialle'},
        'verde': {'m': 'verde', 'f': 'verde', 'mp': 'verdi', 'fp': 'verdi'},
        'blu': {'m': 'blu', 'f': 'blu', 'mp': 'blu', 'fp': 'blu'},
        'rosa': {'m': 'rosa', 'f': 'rosa', 'mp': 'rosa', 'fp': 'rosa'},
        'marrone': {'m': 'marrone', 'f': 'marrone', 'mp': 'marroni', 'fp': 'marroni'},
        'viola': {'m': 'viola', 'f': 'viola', 'mp': 'viola', 'fp': 'viola'},
        'beige': {'m': 'beige', 'f': 'beige', 'mp': 'beige', 'fp': 'beige'},
        'raro': {'m': 'raro', 'f': 'rara', 'mp': 'rari', 'fp': 'rare'},
        'nuovo': {'m': 'nuovo', 'f': 'nuova', 'mp': 'nuovi', 'fp': 'nuove'},
        'usato': {'m': 'usato', 'f': 'usata', 'mp': 'usati', 'fp': 'usate'},
        'perfetto': {'m': 'perfetto', 'f': 'perfetta', 'mp': 'perfetti', 'fp': 'perfette'},
        'iconico': {'m': 'iconico', 'f': 'iconica', 'mp': 'iconici', 'fp': 'iconiche'},
        'esclusivo': {'m': 'esclusivo', 'f': 'esclusiva', 'mp': 'esclusivi', 'fp': 'esclusive'},
        'stupendo': {'m': 'stupendo', 'f': 'stupenda', 'mp': 'stupendi', 'fp': 'stupende'},
        'bello': {'m': 'bello', 'f': 'bella', 'mp': 'belli', 'fp': 'belle'},
        'magnifico': {'m': 'magnifico', 'f': 'magnifica', 'mp': 'magnifici', 'fp': 'magnifiche'},
        'meraviglioso': {'m': 'meraviglioso', 'f': 'meravigliosa', 'mp': 'meravigliosi', 'fp': 'meravigliose'},
        'splendido': {'m': 'splendido', 'f': 'splendida', 'mp': 'splendidi', 'fp': 'splendide'},
        'fantastico': {'m': 'fantastico', 'f': 'fantastica', 'mp': 'fantastici', 'fp': 'fantastiche'},
        'straordinario': {'m': 'straordinario', 'f': 'straordinaria', 'mp': 'straordinari', 'fp': 'straordinarie'},
        'elegante': {'m': 'elegante', 'f': 'elegante', 'mp': 'eleganti', 'fp': 'eleganti'},
        'raffinato': {'m': 'raffinato', 'f': 'raffinata', 'mp': 'raffinati', 'fp': 'raffinate'},
        'classico': {'m': 'classico', 'f': 'classica', 'mp': 'classici', 'fp': 'classiche'},
        'moderno': {'m': 'moderno', 'f': 'moderna', 'mp': 'moderni', 'fp': 'moderne'},
        'vintage': {'m': 'vintage', 'f': 'vintage', 'mp': 'vintage', 'fp': 'vintage'},
        'introvabile': {'m': 'introvabile', 'f': 'introvabile', 'mp': 'introvabili', 'fp': 'introvabili'},
        'ricercato': {'m': 'ricercato', 'f': 'ricercata', 'mp': 'ricercati', 'fp': 'ricercate'},
        'pregiato': {'m': 'pregiato', 'f': 'pregiata', 'mp': 'pregiati', 'fp': 'pregiate'},
        'realizzato': {'m': 'realizzato', 'f': 'realizzata', 'mp': 'realizzati', 'fp': 'realizzate'},
        'classificato': {'m': 'classificato', 'f': 'classificata', 'mp': 'classificati', 'fp': 'classificate'},
        'conservato': {'m': 'conservato', 'f': 'conservata', 'mp': 'conservati', 'fp': 'conservate'},
        'tenuto': {'m': 'tenuto', 'f': 'tenuta', 'mp': 'tenuti', 'fp': 'tenute'},
        'garantito': {'m': 'garantito', 'f': 'garantita', 'mp': 'garantiti', 'fp': 'garantite'},
        'dorato': {'m': 'dorato', 'f': 'dorata', 'mp': 'dorati', 'fp': 'dorate'},
        'argentato': {'m': 'argentato', 'f': 'argentata', 'mp': 'argentati', 'fp': 'argentate'},
        'metallico': {'m': 'metallico', 'f': 'metallica', 'mp': 'metallici', 'fp': 'metalliche'},
        # Aggettivi con forme tronche per gli errori visti
        'bell': {'m': 'bello', 'f': 'bella', 'mp': 'belli', 'fp': 'belle'},
        'ottim': {'m': 'ottimo', 'f': 'ottima', 'mp': 'ottimi', 'fp': 'ottime'}, 
        'particolar': {'m': 'particolare', 'f': 'particolare', 'mp': 'particolari', 'fp': 'particolari'},
        'rarissim': {'m': 'rarissimo', 'f': 'rarissima', 'mp': 'rarissimi', 'fp': 'rarissime'},
        'unic': {'m': 'unico', 'f': 'unica', 'mp': 'unici', 'fp': 'uniche'},
        'special': {'m': 'speciale', 'f': 'speciale', 'mp': 'speciali', 'fp': 'speciali'},
        'splendid': {'m': 'splendido', 'f': 'splendida', 'mp': 'splendidi', 'fp': 'splendide'},
        'meraviglios': {'m': 'meraviglioso', 'f': 'meravigliosa', 'mp': 'meravigliosi', 'fp': 'meravigliose'},
        'rar': {'m': 'raro', 'f': 'rara', 'mp': 'rari', 'fp': 'rare'},
        'ricercat': {'m': 'ricercato', 'f': 'ricercata', 'mp': 'ricercati', 'fp': 'ricercate'},
    }
    
    aggettivo_lower = aggettivo.lower()
    if aggettivo_lower in concordanze:
        # Seleziona la forma corretta (singolare o plurale)
        if is_plural:
            chiave_forma = 'fp' if genere == 'f' else 'mp'
        else:
            chiave_forma = genere
        
        risultato = concordanze[aggettivo_lower].get(chiave_forma, aggettivo)
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
# SISTEMA ANTI-RIPETIZIONE CROSS-SESSIONE
# ===============================

# Cache per tracking messaggi recenti (limitata per performance)
MESSAGGI_RECENTI_CACHE = {}
MAX_CACHE_SIZE = 100

def _track_messaggio_generato(articolo_id: int, pattern_usato: str):
    """Traccia i pattern usati recentemente per evitare ripetizioni"""
    global MESSAGGI_RECENTI_CACHE
    
    # Mantieni cache limitata
    if len(MESSAGGI_RECENTI_CACHE) > MAX_CACHE_SIZE:
        # Rimuovi il più vecchio
        oldest_key = next(iter(MESSAGGI_RECENTI_CACHE))
        del MESSAGGI_RECENTI_CACHE[oldest_key]
    
    MESSAGGI_RECENTI_CACHE[articolo_id] = {
        'pattern': pattern_usato,
        'timestamp': datetime.now().isoformat()
    }

def _get_pattern_non_utilizzato_recentemente(patterns: List[str], articolo_id: int) -> str:
    """Seleziona un pattern non utilizzato recentemente per questo articolo"""
    
    if articolo_id not in MESSAGGI_RECENTI_CACHE:
        return random.choice(patterns)
    
    ultimo_pattern = MESSAGGI_RECENTI_CACHE[articolo_id]['pattern']
    
    # Filtra i pattern diversi dall'ultimo usato
    pattern_alternativi = [p for p in patterns if p != ultimo_pattern]
    
    if pattern_alternativi:
        return random.choice(pattern_alternativi)
    else:
        # Se tutti sono stati usati, scegli casualmente
        return random.choice(patterns)

# ===============================
# RANDOMNESS PESATA PER QUALITÀ
# ===============================

def _scelta_pesata(opzioni: List[str], pesi: List[float] = None) -> str:
    """Scelta casuale con pesi per favorire opzioni di maggiore qualità"""
    if not pesi or len(pesi) != len(opzioni):
        return random.choice(opzioni)
    
    return random.choices(opzioni, weights=pesi, k=1)[0]

def _costruisci_ringraziamento_like_pesato() -> str:
    """Ringraziamenti con pesi basati su naturalezza percepita"""
    ringraziamenti = [
        "per ringraziarti del tuo \"like\"",
        "per ringraziarti dell'interesse", 
        "grazie per il tuo \"like\"",
        "per il tuo interesse",
        "visto il tuo \"like\"",
        "dato il tuo interesse"
    ]
    
    # Pesi: più naturali = peso maggiore
    pesi = [0.25, 0.20, 0.15, 0.15, 0.15, 0.10]
    
    return _scelta_pesata(ringraziamenti, pesi)

def _costruisci_offerta_personalizzata_pesata() -> str:
    """Offerte con pesi basati su efficacia commerciale (ESPANSO)"""
    offerte = [
        "ti sto inviando un'offerta con uno sconto in più",
        "ti stiamo inviando un'offerta con un ulteriore sconto solo per te", 
        "ti stiamo facendo un'offerta speciale",
        "ti abbiamo riservato uno sconto esclusivo",
        "ti stiamo preparando un'offerta personalizzata",
        "ti facciamo un prezzo speciale",
        "ti stiamo inviando un'offerta riservata",
        "ti preparo subito un preventivo vantaggioso",
        "ti invio una proposta commerciale dedicata",
        "ti riservo una quotazione esclusiva",
        "ti dedico uno sconto riservato",
        "ti propongo una soluzione su misura",
        "ti offro condizioni privilegiate",
        "ti invio immediatamente una proposta speciale"
    ]
    
    # Pesi bilanciati per ridurre ripetizioni
    pesi = [0.12, 0.12, 0.10, 0.10, 0.08, 0.10, 0.08, 0.08, 0.07, 0.07, 0.06, 0.06, 0.06, 0.06]
    
    return _scelta_pesata(offerte, pesi)

def _costruisci_chiusura_cortese_pesata() -> str:
    """Chiusure con pesi basati su cordialità"""
    chiusure = [
        "fammi sapere se ti interessa",
        "spero possa interessarti", 
        "speriamo ti piaccia la proposta",
        "grazie ancora per l'interesse mostrato",
        "intanto grazie per il tuo \"like\"",
        "sempre grazie per aver notato questo pezzo",
        "comunque grazie per l'attenzione",
        "il massimo che possiamo fare, in ogni caso grazie per l'interesse"
    ]
    
    # Pesi: più personali e dirette = peso maggiore
    pesi = [0.20, 0.18, 0.15, 0.12, 0.12, 0.10, 0.08, 0.05]
    
    return _scelta_pesata(chiusure, pesi)

# ===============================
# TEMPLATE STRUTTURATI PER TIPO TARGET  
# ===============================

def _get_template_per_target(target: str, saluto: str, desc_prodotto: str, 
                           scarsita: str, ringraziamento: str, 
                           offerta: str, chiusura: str) -> List[str]:
    """Template messaggi ottimizzati per tipo di target"""
    
    if target and 'Lusso' in target:
        # Template più eleganti per target luxury
        return [
            f"{saluto}, è {desc_prodotto}, {scarsita}. {ringraziamento.capitalize()} {offerta}. {chiusura.capitalize()}.",
            f"{saluto}, {desc_prodotto} e {scarsita}. {offerta.capitalize()}, {ringraziamento}.",
            f"{saluto}, è {desc_prodotto}, {scarsita}. {ringraziamento.capitalize()}, {offerta}."
        ]
    elif target and 'Vintage' in target:
        # Template più nostalgici per vintage lovers
        return [
            f"{saluto}, {desc_prodotto} e {scarsita}. {offerta.capitalize()} {ringraziamento}!",
            f"{saluto}, è {desc_prodotto}, {scarsita}. {ringraziamento.capitalize()}, {offerta}!",
            f"{saluto}, {desc_prodotto}, {scarsita}. {offerta.capitalize()}, {ringraziamento}!"
        ]
    else:
        # Template generici bilanciati
        return [
            f"{saluto}, è {desc_prodotto}, {scarsita}. {ringraziamento.capitalize()} {offerta}. {chiusura.capitalize()}!",
            f"{saluto}, {desc_prodotto}, {scarsita}. {offerta.capitalize()} {ringraziamento}!",
            f"{saluto}, è {desc_prodotto} e {scarsita}. {ringraziamento.capitalize()}, {offerta}. {chiusura.capitalize()}!",
            f"{saluto}, {desc_prodotto}, {scarsita}. {offerta.capitalize()}, {ringraziamento}!",
            f"{saluto}, è {desc_prodotto}, {scarsita}. {ringraziamento.capitalize()}, {offerta}!",
            f"{saluto}, {desc_prodotto} e {scarsita}. {offerta.capitalize()} {ringraziamento}!"
        ]

def genera_messaggio_like_vestiaire(brand: str, nome: str, colore: str, materiale: str, 
                                   keywords_classificate: Dict, condizioni: str, rarita: str, 
                                   vintage: bool, target: str, termini_commerciali: List[str],
                                   articolo_id: int = None) -> str:
    """
    🎯 ALGORITMO ULTRA-OTTIMIZZATO - Genera messaggi diretti naturali per like Vestiaire
    Con controllo ripetizioni, randomness pesata e template strutturati
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
    
    # Descrizione prodotto ottimizzata con tipo corretto
    desc_prodotto = _costruisci_descrizione_intelligente_vestiaire(
        brand, nome_pulito, modello, colore, materiale, condizioni, rarita, 
        vintage, genere, parametri_rilevanti, keywords_classificate, tipo_articolo
    )
    
    # Altri componenti con randomness pesata
    scarsita = _costruisci_scarsita_naturale(genere)
    ringraziamento = _costruisci_ringraziamento_like_pesato()
    offerta = _costruisci_offerta_personalizzata_pesata()
    chiusura = _costruisci_chiusura_cortese_pesata()
    
    # 🎨 TEMPLATE STRUTTURATI per tipo target
    messaggi_pattern = _get_template_per_target(
        target, saluto, desc_prodotto, scarsita, 
        ringraziamento, offerta, chiusura
    )
    
    # 🔄 SELEZIONE CON ANTI-RIPETIZIONE CROSS-SESSIONE
    if articolo_id:
        messaggio = _get_pattern_non_utilizzato_recentemente(messaggi_pattern, articolo_id)
        _track_messaggio_generato(articolo_id, messaggio)
    else:
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
                                                  parametri: Dict, keywords_classificate: Dict, 
                                                  tipo_corretto: str = None) -> str:
    """🎯 COSTRUZIONE NATURALE della descrizione con grammatica perfetta"""
    
    # 🏷️ USA TIPO ARTICOLO CORRETTO PASSATO COME PARAMETRO
    if tipo_corretto:
        tipo_articolo = tipo_corretto
    elif nome_pulito:
        # Se il nome è già un tipo di articolo valido, usalo direttamente
        nome_lower = nome_pulito.lower()
        if nome_lower in ['articolo', 'borsa', 'scarpe', 'orologio', 'portafoglio', 'giacca', 'pantalone', 'pantaloni']:
            tipo_articolo = nome_lower
        else:
            # Altrimenti riconosci il tipo dal nome completo
            tipo_articolo = riconosci_tipo_articolo(nome_pulito)
    else:
        # Fallback
        tipo_articolo = 'articolo'
    
    # 🎨 SELEZIONA AGGETTIVI QUALITATIVI INTELLIGENTI
    aggettivi_qualita = []
    
    # Aggettivi per condizioni (max 1)
    if parametri['priorita_condizioni'] >= 3:
        aggettivi_qualita.extend(['splendid', 'perfett', 'stupend'])
    elif parametri['priorita_condizioni'] >= 2:
        aggettivi_qualita.extend(['bellissim', 'ottim'])
    elif parametri['priorita_condizioni'] >= 1:
        aggettivi_qualita.extend(['bell', 'interessant'])
    
    # Aggettivi per rarità (max 1)
    if parametri['priorita_rarita'] >= 3:
        aggettivi_qualita.extend(['rarissim', 'introvabil', 'unic', 'eccezional'])
    elif parametri['priorita_rarita'] >= 2:
        aggettivi_qualita.extend(['rar', 'special', 'ricercat'])
    elif parametri['priorita_rarita'] >= 1:
        aggettivi_qualita.extend(['particolar', 'special'])
    
    # Se non ci sono aggettivi specifici, usa generici
    if not aggettivi_qualita:
        aggettivi_qualita = ['bell', 'interessant', 'particolar']
    
    # Seleziona UN SOLO aggettivo principale
    aggettivo_base = random.choice(aggettivi_qualita)
    aggettivo_principale = concordanza_aggettivo(aggettivo_base, genere, tipo_articolo)
    
    # 🎨 COSTRUISCI DESCRIZIONE COLORE/MATERIALE INTELLIGENTE  
    dettagli_fisici = []
    
    # Gestione colore intelligente (SISTEMA AVANZATO) - PREVENZIONE RIPETIZIONI
    if parametri['colore']:
        colore_originale = parametri['colore'].lower().strip()
        
        # Correzioni auto-typos comuni
        correzioni_colori = {
            'ora': 'oro',
            'argentio': 'argento',
            'griggio': 'grigio',
            'azzuro': 'azzurro',
            'violla': 'viola'
        }
        colore_originale = correzioni_colori.get(colore_originale, colore_originale)
        
        # SISTEMA ANTI-RIPETIZIONE: se il colore è già nel nome del prodotto, usa alternative
        colore_nel_nome = any(colore_originale in part.lower() for part in [nome_pulito or '', modello or ''])
        
        # Gestione colori specifici con concordanza - PLURALI CORRETTI
        if 'nero' in colore_originale or 'black' in colore_originale:
            if colore_nel_nome:
                dettagli_fisici.append('total black' if genere == 'm' else 'elegante')
            elif genere == 'f' and tipo_articolo not in ['scarpe']:
                dettagli_fisici.append(random.choice(['nera', 'in nero']))
            elif tipo_articolo in ['scarpe']:
                dettagli_fisici.append(random.choice(['nere', 'total black']))
            else:
                dettagli_fisici.append(random.choice(['nero', 'total black', 'in nero']))
        elif 'bianco' in colore_originale or 'white' in colore_originale:
            if colore_nel_nome:
                dettagli_fisici.append('candido' if genere == 'm' else 'candida')
            elif genere == 'f' and tipo_articolo not in ['scarpe']:
                dettagli_fisici.append(random.choice(['bianca', 'in bianco']))
            elif tipo_articolo in ['scarpe']:
                dettagli_fisici.append(random.choice(['bianche', 'total white']))
            else:
                dettagli_fisici.append(random.choice(['bianco', 'in bianco']))
        elif 'rosso' in colore_originale or 'red' in colore_originale:
            if colore_nel_nome:
                dettagli_fisici.append('intenso' if genere == 'm' else 'intensa')
            elif genere == 'f' and tipo_articolo not in ['scarpe']:
                dettagli_fisici.append(random.choice(['rossa', 'rosso acceso']))
            elif tipo_articolo in ['scarpe']:
                dettagli_fisici.append(random.choice(['rosse', 'rosso fuoco']))
            else:
                dettagli_fisici.append(random.choice(['rosso', 'rosso acceso']))
        elif 'grigio' in colore_originale or 'gray' in colore_originale:
            if colore_nel_nome:
                dettagli_fisici.append('elegante')
            elif genere == 'f':
                dettagli_fisici.append(random.choice(['grigia', 'grigio perla']))
            else:
                dettagli_fisici.append(random.choice(['grigio', 'grigio antracite']))
        elif 'oro' in colore_originale or 'gold' in colore_originale:
            if colore_nel_nome:
                dettagli_fisici.append('prezioso')
            else:
                dettagli_fisici.append(random.choice(['dorato', 'color oro', 'oro']))
        elif 'argento' in colore_originale or 'silver' in colore_originale:
            if colore_nel_nome:
                dettagli_fisici.append('brillante')
            else:
                dettagli_fisici.append(random.choice(['argentato', 'color argento', 'argento']))
        elif 'beige' in colore_originale or 'tan' in colore_originale:
            if colore_nel_nome:
                dettagli_fisici.append('elegante')
            else:
                dettagli_fisici.append(random.choice(['color sabbia', 'tortora', 'beige']))
        elif 'marrone' in colore_originale or 'brown' in colore_originale:
            if colore_nel_nome:
                dettagli_fisici.append('cioccolato' if genere == 'm' else 'elegante')
            elif genere == 'f':
                dettagli_fisici.append(random.choice(['cioccolato', 'mogano']))
            else:
                dettagli_fisici.append(random.choice(['mogano', 'cioccolato']))
        elif 'rosa' in colore_originale or 'pink' in colore_originale:
            if colore_nel_nome:
                dettagli_fisici.append('delicato')
            else:
                dettagli_fisici.append(random.choice(['rosa antico', 'color rosa', 'rosa']))
        elif 'blu' in colore_originale or 'blue' in colore_originale:
            if colore_nel_nome:
                dettagli_fisici.append('intenso')
            else:
                dettagli_fisici.append(random.choice(['blu navy', 'color blu', 'blu']))
        else:
            # Altri colori - evita ripetizioni
            if not colore_nel_nome:
                dettagli_fisici.append(concordanza_aggettivo(colore_originale, genere, tipo_articolo))
    
    # Materiale (solo se diverso dal colore)
    if parametri['materiale'] and parametri['materiale'].lower() not in ['nero', 'bianco', 'rosso']:
        materiale_formato = _formatta_materiale_intelligente(parametri['materiale'])
        if materiale_formato not in dettagli_fisici:
            dettagli_fisici.append(materiale_formato)
    
    # Vintage (solo se rilevante)
    if parametri['vintage']:
        dettagli_fisici.append(random.choice(['vintage', 'd\'epoca']))
    
    # 📝 COSTRUISCI FRASI NATURALI
    articolo_giusto = _get_articolo_indeterminativo_corretto(genere, tipo_articolo)
    
    # 📝 COSTRUZIONE COMPLETAMENTE NATURALE
    
    # Costruisci il nome prodotto nel modo giusto
    if modello and len(modello) > 2 and modello.lower() != nome_pulito.lower():
        # Ha un modello specifico diverso dal nome: "borsa Louis Vuitton Speedy"
        nome_prodotto_base = f"{tipo_articolo} {brand} {modello}"
    elif nome_pulito and nome_pulito.lower() not in ['articolo', 'borsa', 'scarpe', 'orologio', 'portafoglio']:
        # Ha un nome specifico che non è un tipo generico: "borsa Louis Vuitton Classic Flap"
        nome_prodotto_base = f"{tipo_articolo} {brand} {nome_pulito}"
    else:
        # Nome generico: "articolo Louis Vuitton" o "borsa Louis Vuitton"
        nome_prodotto_base = f"{tipo_articolo} {brand}"
    
    # Pattern più naturali in italiano
    if dettagli_fisici:
        dettaglio = dettagli_fisici[0]
        
        # Costruzioni naturali italiane
        patterns_naturali = [
            f"{aggettivo_principale} {nome_prodotto_base} {dettaglio}",
            f"{nome_prodotto_base} {aggettivo_principale} {dettaglio}",
            f"{nome_prodotto_base} {dettaglio} {aggettivo_principale}",
            f"splendid{_get_desinenza_genere(genere)} {nome_prodotto_base} {dettaglio}"
        ]
    else:
        # Senza dettagli
        patterns_naturali = [
            f"{aggettivo_principale} {nome_prodotto_base}",
            f"{nome_prodotto_base} {aggettivo_principale}",
            f"splendid{_get_desinenza_genere(genere)} {nome_prodotto_base}",
            f"meraviglios{_get_desinenza_genere(genere)} {nome_prodotto_base}"
        ]
    
    descrizione_base = random.choice(patterns_naturali)
    
    # Aggiungi articolo corretto all'inizio
    return f"{articolo_giusto} {descrizione_base}"

def _get_desinenza_genere(genere: str) -> str:
    """Ottiene la desinenza corretta per genere"""
    return 'a' if genere == 'f' else 'o'



def _formatta_materiale_intelligente(materiale: str) -> str:
    """Formattazione materiale naturale senza preposizioni ridondanti"""
    materiale_lower = materiale.lower().strip()
    
    # Materiali che appaiono meglio senza preposizioni
    materiali_naturali = {
        'pelle': 'in pelle',
        'vera pelle': 'in vera pelle', 
        'pelle di vitello': 'in pelle di vitello',
        'canvas': 'canvas',
        'tela': 'in tela',
        'seta': 'in seta',  
        'cotone': 'in cotone',
        'lana': 'in lana',
        'cashmere': 'in cashmere',
        'nylon': 'in nylon',
        'poliestere': 'in poliestere'
    }
    
    return materiali_naturali.get(materiale_lower, f'in {materiale_lower}')

def _costruisci_scarsita_naturale(genere: str) -> str:
    """Crea messaggio di scarsità naturale (ESPANSO)"""
    if genere == 'f':
        scarsita_patterns = [
            "ne abbiamo solo una",
            "ne abbiamo una sola", 
            "è l'ultima disponibile",
            "ne è rimasta solo una",
            "è un pezzo unico",
            "ne abbiamo disponibile solo questa",
            "è l'unica che abbiamo",
            "abbiamo solo questo esemplare",
            "ne è rimasto solo questo pezzo",
            "è una delle ultime rimaste",
            "difficile da trovare in queste condizioni",
            "ne possediamo solo una",
            "è l'ultima del suo genere"
        ]
    else:
        scarsita_patterns = [
            "ne abbiamo solo uno",
            "ne abbiamo uno solo", 
            "è l'ultimo disponibile",
            "ne è rimasto solo uno",
            "è un pezzo unico",
            "ne abbiamo disponibile solo questo",
            "è l'unico che abbiamo",
            "abbiamo solo questo esemplare",
            "ne è rimasto solo questo pezzo",
            "è uno degli ultimi rimasti",
            "difficile da trovare in queste condizioni",
            "ne possediamo solo uno",
            "è l'ultimo del suo genere"
        ]
    
    return random.choice(scarsita_patterns)

def _pulisci_messaggio_vestiaire_migliorato(messaggio: str, brand: str, nome_pulito: str) -> str:
    """🧹 PULIZIA +CONCORDANZA INTELLIGENTE brand-prodotto"""
    if not messaggio:
        return ""
    
    # 🎯 IDENTIFICA IL TIPO DI PRODOTTO per concordanza corretta
    tipo_prodotto = riconosci_tipo_articolo(nome_pulito)
    genere_prodotto = get_genere_cached(tipo_prodotto)
    
    # 🔍 CORREZIONI GRAMMATICALI SPECIFICHE INTELLIGENTI
    brand_lower = brand.lower()
    
    # CORREZIONI DINAMICHE basate su genere del prodotto
    patterns_problematici = [
        # CORREZIONI PRIORITARIE per apostrofi errati 
        (r'\bun\'\s+(articolo|orologio|portafoglio)\b', r'un \1', 0),
        (r'\bè un\'\s+(articolo|orologio|portafoglio)\b', r'è un \1', 0),
        (r'\bè un\'\s+\w+\s+(articolo|orologio|portafoglio)\b', r'è un \2', 0),
        (r'\bun\'\s+\w+\s+(articolo|orologio|portafoglio)\b', r'un \1', 0),
        
        # CORREZIONI PRIORITARIE per scarpe plurali con colori (MIGLIORATO)
        (r'\bscarpe\s+\w+\s+(\w+)\s+rosso\s+acceso\b', lambda m: m.group(0).replace('rosso acceso', 'rosse accese'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+(\w+)\s+rosso\b', lambda m: m.group(0).replace('rosso', 'rosse'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+(\w+)\s+nero\b', lambda m: m.group(0).replace('nero', 'nere'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+(\w+)\s+bianco\b', lambda m: m.group(0).replace('bianco', 'bianche'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+(\w+)\s+grigio\b', lambda m: m.group(0).replace('grigio', 'grigie'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+(\w+)\s+(\w+)a\b', lambda m: m.group(0).replace(m.group(2)+'a', m.group(2)+'e') if m.group(2) in ['ross', 'ner', 'bianc', 'grigi'] else m.group(0), re.IGNORECASE),
        (r'\bscarpe\s+\w+.*ne abbiamo solo una\b', lambda m: m.group(0).replace('ne abbiamo solo una', 'ne abbiamo solo queste'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+bell(\w)\s+grigio\b', lambda m: m.group(0).replace('bell'+m.group(1)+' grigio', 'belle grigie'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+interessanti\s+rossa\b', lambda m: m.group(0).replace('rossa', 'rosse'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+intirissanti\s+\w+\s+grigia\b', lambda m: m.group(0).replace('intirissanti', 'interessanti').replace('grigia', 'grigie'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+nera\s+bella\b', lambda m: m.group(0).replace('nera bella', 'nere e belle'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+biance\s+bella\b', lambda m: m.group(0).replace('biance bella', 'bianche e belle'), re.IGNORECASE),
        
        # CORREZIONI PRIORITARIE per scarpe con aggettivi
        (r'\bdelle\s+(interessante|speciale|particolare)\s+scarpe\b', lambda m: f"delle scarpe {m.group(1).replace('e', 'i') if m.group(1).endswith('e') else m.group(1)+'i'}", re.IGNORECASE),
        (r'\b(interessante|speciale|particolare)\s+scarpe\b', lambda m: f"scarpe {m.group(1).replace('e', 'i') if m.group(1).endswith('e') else m.group(1)+'i'}", re.IGNORECASE),
        
        # CORREZIONI PRIORITARIE verbo essere + scarpe
        (r'\bè delle\s+\w+\s+scarpe\b', lambda m: m.group(0).replace('è delle', 'sono delle'), re.IGNORECASE),
        (r'\bè l\'ultima disponibile.*scarpe\b', lambda m: m.group(0).replace("è l'ultima disponibile", "sono le ultime disponibili"), re.IGNORECASE), 
        
        # Correzioni articoli base
        (r'\buna articolo\b', 'un articolo', 0),
        (r'\bun borsa\b', 'una borsa', 0), 
        (r'\bun scarpe\b', 'delle scarpe', 0),
        (r'\buna orologio\b', 'un orologio', 0),
        (r'\buna pantaloni\b', 'dei pantaloni', 0),
        
        # CORREZIONI CONCORDANZA BRAND-PRODOTTO INTELLIGENTI
        # Per prodotti femminili (borse, scarpe, giacche...)
        (rf'\b{re.escape(brand)}\s+nera\b' if genere_prodotto == 'f' else 'SKIP', f'{brand} nera', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+rara\b' if genere_prodotto == 'f' else 'SKIP', f'{brand} rara', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+ricercata\b' if genere_prodotto == 'f' else 'SKIP', f'{brand} ricercata', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+bellissima\b' if genere_prodotto == 'f' else 'SKIP', f'{brand} bellissima', re.IGNORECASE),
        
        # Per prodotti maschili (articoli, orologi, portafogli...)
        (rf'\b{re.escape(brand)}\s+nero\b' if genere_prodotto == 'm' else 'SKIP', f'{brand} nero', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+raro\b' if genere_prodotto == 'm' else 'SKIP', f'{brand} raro', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+ricercato\b' if genere_prodotto == 'm' else 'SKIP', f'{brand} ricercato', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+bellissimo\b' if genere_prodotto == 'm' else 'SKIP', f'{brand} bellissimo', re.IGNORECASE),
        
        # CORREZIONI PER ERRORI VISTI NEI TEST
        (rf'\b{re.escape(brand)}\s+nera\b' if genere_prodotto == 'm' else 'SKIP', f'{brand} nero', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+rara\b' if genere_prodotto == 'm' else 'SKIP', f'{brand} raro', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+ricercata\b' if genere_prodotto == 'm' else 'SKIP', f'{brand} ricercato', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+bellissima\b' if genere_prodotto == 'm' else 'SKIP', f'{brand} bellissimo', re.IGNORECASE),
        
        # Forme aggettivali tronche (MIGLIORATO) - CORREZIONI PRIORITARIE
        (r'\bbellissim\b', 'bellissimo' if genere_prodotto == 'm' else 'bellissima', 0),
        (r'\brarissim\b', 'rarissimo' if genere_prodotto == 'm' else 'rarissima', 0),
        (r'\bricercat\b', 'ricercato' if genere_prodotto == 'm' else 'ricercata', 0),
        (r'\bsplendid\b', 'splendido' if genere_prodotto == 'm' else 'splendida', 0),
        (r'\bmeraviglios\b', 'meraviglioso' if genere_prodotto == 'm' else 'meravigliosa', 0),
        (r'\bottim\b', 'ottimo' if genere_prodotto == 'm' else 'ottima', 0),
        (r'\bstupend\b', 'stupendo' if genere_prodotto == 'm' else 'stupenda', 0),
        (r'\bperfett\b', 'perfetto' if genere_prodotto == 'm' else 'perfetta', 0),
        (r'\binteressant\b', 'interessante', 0),
        (r'\bintirissant\b', 'interessanti', 0),  # correzione typo
        (r'\bintirissanti\b', 'interessanti', 0),  # correzione typo plurale
        (r'\bspecial\b', 'speciale', 0),
        
        # CORREZIONI SPECIFICHE PER ERRORI RILEVATI NEI TEST
        (r'\binteressante\s+(\w+)\s+interessant\b', lambda m: f'interessanti {m.group(1)}', re.IGNORECASE),  # plurale
        (r'\binteressant\s+(\w+)\b', lambda m: f'interessante {m.group(1)}', re.IGNORECASE),  # singolare
        (r'\bun\'\s+interessant\s+(\w+)\b', lambda m: f'un interessante {m.group(1)}', re.IGNORECASE),
        
        # CORREZIONI AGGRESSIVE PER ERRORI TEST (priorità massima)
        (r'\bun\'\s+interessante\s+(\w+)\b', lambda m: f'degli interessanti {m.group(1)}' if m.group(1) == 'occhiali' else f'un interessante {m.group(1)}', re.IGNORECASE),
        (r'\buna\s+interessante\s+(\w+)\b', lambda m: f'una interessante {m.group(1)}', re.IGNORECASE),
        (r'\buna\s+bellissimo\s+(\w+)\b', lambda m: f'una bellissima {m.group(1)}', re.IGNORECASE),
        (r'\bè una\s+bellissimo\s+(\w+)\b', lambda m: f'è una bellissima {m.group(1)}', re.IGNORECASE),
        
        # CORREZIONI ARTICOLI SPECIFICHE per "articolo" e "occhiali" 
        (r'\buna\s+(bellissima?|splendida?|speciale|ottima?|rara?|particolare|meravigliosa?)\s+(articolo|borsa|giacca|felpa|camicia)\b', 
         lambda m: f"un{'a' if m.group(2) in ['borsa', 'giacca', 'felpa', 'camicia'] else ''} {concordanza_aggettivo(m.group(1), 'f' if m.group(2) in ['borsa', 'giacca', 'felpa', 'camicia'] else 'm')} {m.group(2)}", re.IGNORECASE),
        (r'\bun\'\s+(bellissima?|splendida?|speciale|ottima?|rara?|particolare|meravigliosa?)\s+(articolo|borsa|giacca|felpa|camicia)\b', 
         lambda m: f"un{'a' if m.group(2) in ['borsa', 'giacca', 'felpa', 'camicia'] else ''} {concordanza_aggettivo(m.group(1), 'f' if m.group(2) in ['borsa', 'giacca', 'felpa', 'camicia'] else 'm')} {m.group(2)}", re.IGNORECASE),
        (r'\bun\'\s+articolo\b', 'un articolo', re.IGNORECASE),
        (r'\bun\'\s+occhiali\b', 'degli occhiali', re.IGNORECASE),
        (r'\buna\s+occhiali\b', 'degli occhiali', re.IGNORECASE),
        (r'\bè un\'\s+occhiali\b', 'sono degli occhiali', re.IGNORECASE),
        (r'\bè un\'\s+(\w+)\s+occhiali\b', lambda m: f'sono degli {m.group(1)} occhiali', re.IGNORECASE),
        (r'\bocchiali\s+\w+\s+perfetto\b', lambda m: m.group(0).replace('perfetto', 'perfetti'), re.IGNORECASE),
        (r'\bsono\s+degli\s+(\w+)\s+occhiali\b', lambda m: f'sono degli occhiali {m.group(1)}' if m.group(1) in ['splendidi', 'perfetti', 'bellissimi', 'splendido', 'perfetto', 'bellissimo'] else m.group(0), re.IGNORECASE),
        (r'\bdegli\s+(splendid[oi]|perfett[oi]|bellissim[oi])\s+occhiali\b', lambda m: f"degli occhiali {m.group(1).replace('o', 'i')}", re.IGNORECASE),
        (r'\bocchiali\s+(splendido|perfetto|bellissimo)\b', lambda m: f"occhiali {m.group(1).replace('o', 'i')}", re.IGNORECASE),
        (r'\bun\'\s+perfetto\s+anello\b', 'un perfetto anello', re.IGNORECASE),
        (r'\bun\'\s+anello\s+(\w+)\s+perfetto\b', lambda m: f'un anello {m.group(1)} perfetto', re.IGNORECASE),
        (r'\buna particolar articolo\b', 'un particolare articolo', 0),
        (r'\buna ottim articolo\b', 'un ottimo articolo', 0),
        
        # Correzioni spazi e typos (ESPANSE)
        (r'\bquotazion(\w+)\b', lambda m: 'quotazione ' + m.group(1), 0),
        (r'\bfelpa\s+\w+\s+grigio\s+perla\s+bella\b', lambda m: m.group(0).replace('grigio perla bella', 'grigia e bella'), re.IGNORECASE),
        (r'\bgiacco\s+\w+\s+cammella\b', lambda m: m.group(0).replace('cammella', 'color cammello'), re.IGNORECASE),
        (r'\buna bell articolo\b', 'un bel articolo', 0),
        
        # CORREZIONI BRAND-ARTICOLO per concordanza perfetta
        (rf'\b{re.escape(brand)}\s+(nera?|rara?|ricercata?|bellissima?|splendida?|speciale)\s+articolo\b', 
         lambda m: f"{brand} {concordanza_aggettivo(m.group(1), 'm')}", re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+(nera?|rara?|ricercata?|bellissima?|splendida?|ottima?|particolare)\b(?!\s+articolo)', 
         lambda m: f"{brand} {concordanza_aggettivo(m.group(1), genere_prodotto)}", re.IGNORECASE),
        
        # CORREZIONI SPECIFICHE BRAND-AGGETTIVO per gli errori visti
        (rf'\b{re.escape(brand)}\s+bellissima\b', f'{brand} {"bellissimo" if genere_prodotto == "m" else "bellissima"}', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+ottima\b', f'{brand} {"ottimo" if genere_prodotto == "m" else "ottima"}', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+nera\b', f'{brand} {"nero" if genere_prodotto == "m" else "nera"}', re.IGNORECASE),
        
        # CORREZIONI FINALI AGGRESSIVE per concordanza con "articolo"
        (r'\barticolo\s+\w+\s+ottima\b', lambda m: m.group(0).replace('ottima', 'ottimo'), re.IGNORECASE),
        (r'\barticolo\s+\w+\s+bellissima\b', lambda m: m.group(0).replace('bellissima', 'bellissimo'), re.IGNORECASE),
        (r'\barticolo\s+\w+\s+nera\b', lambda m: m.group(0).replace('nera', 'nero'), re.IGNORECASE),
        (r'\barticolo\s+\w+\s+\w+\s+ottima\b', lambda m: m.group(0).replace('ottima', 'ottimo'), re.IGNORECASE),
        
        # CORREZIONI per "borsa" (femminile)
        (r'\bborsa\s+\w+\s+ottimo\b', lambda m: m.group(0).replace('ottimo', 'ottima'), re.IGNORECASE),
        (r'\bborsa\s+\w+\s+nero\b', lambda m: m.group(0).replace('nero', 'nera'), re.IGNORECASE),
        (r'\bborsa\s+\w+\s+bellissimo\b', lambda m: m.group(0).replace('bellissimo', 'bellissima'), re.IGNORECASE),
        
        # CORREZIONI per "scarpe" (femminile plurale)
        (r'\bscarpe\s+\w+\s+bellissimo\b', lambda m: m.group(0).replace('bellissimo', 'bellissime'), re.IGNORECASE),
        (r'\bbellissimo\s+scarpe\b', 'bellissime scarpe', re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+ottimo\b', lambda m: m.group(0).replace('ottimo', 'ottime'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+nero\b', lambda m: m.group(0).replace('nero', 'nere'), re.IGNORECASE),
        (r'\bè delle scarpe\b', 'sono delle scarpe', re.IGNORECASE),
        
        # CORREZIONI per "orologio" e "portafoglio" (maschili)
        (r'\borologio\s+\w+\s+bianca\b', lambda m: m.group(0).replace('bianca', 'bianco'), re.IGNORECASE),
        (r'\borologio\s+\w+\s+candida\b', lambda m: m.group(0).replace('candida', 'bianco'), re.IGNORECASE),
        (r'\bportafoglio\s+\w+\s+candida\b', lambda m: m.group(0).replace('candida', 'bianco'), re.IGNORECASE),
        (r'\barticolo\s+\w+\s+bianca\b', lambda m: m.group(0).replace('bianca', 'bianco'), re.IGNORECASE),
        
        # CORREZIONI numerosità per prodotti maschili
        (r'\b(orologio|portafoglio|articolo)\s+\w+.*ne abbiamo solo una\b', lambda m: m.group(0).replace('solo una', 'solo uno'), re.IGNORECASE),
        (r'\b(orologio|portafoglio|articolo)\s+\w+.*ne è rimasta solo una\b', lambda m: m.group(0).replace('rimasta solo una', 'rimasto solo uno'), re.IGNORECASE),
        
        # CORREZIONE articoli indeterminativi errati
        (r'\bun\'\s+(orologio|articolo|portafoglio)\b', r'un \1', re.IGNORECASE),
        (r'\bun\'\s+(ottimo|speciale|splendido)\s+(orologio|articolo|portafoglio)\b', r'un \1 \2', re.IGNORECASE),
        (r'\bun\'\s+(bello|bell)\s+(orologio|articolo|portafoglio)\b', r"un bell'\2", re.IGNORECASE),
        (r'\bè un\'\s+(bello|bell)\s+(orologio|articolo|portafoglio)\b', r"è un bell'\2", re.IGNORECASE),
        (r'\bè un\'\s+(interessante|speciale|particolare)\s+(orologio|articolo|portafoglio)\b', r'è un \1 \2', re.IGNORECASE),
        (r'\bun\'\s+(interessante|speciale|particolare)\s+(orologio|articolo|portafoglio)\b', r'un \1 \2', re.IGNORECASE),
        (r'\bè un\'\s+(interessante)\s+(articolo)\b', r'è un interessante articolo', re.IGNORECASE),
        (r'\bun\'\s+splendido\b', 'un splendido', re.IGNORECASE),
        
        # CORREZIONI per scarpe con verbo essere e plurali
        (r'\bè delle\s+(interessante|speciale|particolare)\s+scarpe\b', lambda m: f"sono delle scarpe {m.group(1).replace('e', 'i') if m.group(1).endswith('e') else m.group(1)+'i'}", re.IGNORECASE),
        (r'\bdelle\s+(splendida|bella|interessante|speciale|particolare)\s+scarpe\b', lambda m: f"delle {m.group(1).replace('a', 'e') if m.group(1).endswith('a') else m.group(1).replace('e', 'i') if m.group(1).endswith('e') else m.group(1)+'i'} scarpe", re.IGNORECASE),
        
        # CORREZIONI per aggettivi tronchi senza desinenza
        (r'\binteressant\b', 'interessante', re.IGNORECASE),
        (r'\bparticolar\b', 'particolare', re.IGNORECASE),
        (r'\bspecial\b', 'speciale', re.IGNORECASE),
        
        # CORREZIONI plurali per scarpe (femminile plurale)
        (r'\bscarpe\s+\w+\s+bella\b', lambda m: m.group(0).replace('bella', 'belle'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+\w+\s+bella\b', lambda m: m.group(0).replace('bella', 'belle'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+\w+\s+interessante\b', lambda m: m.group(0).replace('interessante', 'interessanti'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+interessante\b', lambda m: m.group(0).replace('interessante', 'interessanti'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+\w+\s+speciale\b', lambda m: m.group(0).replace('speciale', 'speciali'), re.IGNORECASE),
        
        # CORREZIONI numerosità per prodotti maschili singolari
        (r'\b(articolo|orologio|portafoglio)\s+\w+.*ne abbiamo una sola\b', lambda m: m.group(0).replace('una sola', 'uno solo'), re.IGNORECASE),
        (r'\b(articolo|orologio|portafoglio)\s+\w+.*ne abbiamo solo una\b', lambda m: m.group(0).replace('solo una', 'solo uno'), re.IGNORECASE),
        (r'\b(articolo|orologio|portafoglio)\s+\w+.*è l\'ultima disponibile\b', lambda m: m.group(0).replace("l'ultima disponibile", "l'ultimo disponibile"), re.IGNORECASE),
        
        # CORREZIONI per scarpe plurali
        (r'\bscarpe\s+\w+\s+rossa\b', lambda m: m.group(0).replace('rossa', 'rosse'), re.IGNORECASE),
        (r'\bscarpe\s+\w+\s+argenta\b', lambda m: m.group(0).replace('argenta', 'argentate'), re.IGNORECASE),
        (r'\bscarpe\s+\w+.*ne abbiamo una sola\b', lambda m: m.group(0).replace('ne abbiamo una sola', 'ne abbiamo solo queste'), re.IGNORECASE),
        (r'\bscarpe\s+\w+.*ne è rimasta solo una\b', lambda m: m.group(0).replace('ne è rimasta solo una', 'ne sono rimaste solo queste'), re.IGNORECASE),
        
        # CORREZIONI colori per prodotti maschili (orologio, articolo, portafoglio)
        (r'\b(orologio|articolo|portafoglio)\s+\w+.*rossa\b', lambda m: m.group(0).replace('rossa', 'rosso'), re.IGNORECASE),
        (r'\b(orologio|articolo|portafoglio)\s+\w+.*argenta\b', lambda m: m.group(0).replace('argenta', 'argentato'), re.IGNORECASE),
        
        # CORREZIONI colori per prodotti femminili (borsa)
        (r'\bborsa\s+\w+.*argenta\b', lambda m: m.group(0).replace('argenta', 'argentata'), re.IGNORECASE),
        
        # ERRORI ortografici comuni
        (r'\bora\b(?=\s*,|\s*e|\s*$)', 'oro', re.IGNORECASE),
        
        # Pattern specifici per brand-aggettivo-articolo
        (rf'\b{re.escape(brand)}\s+bellissima\s+nera\b', f'{brand} bellissimo nero', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+ottima\s+nera\b', f'{brand} ottimo nero', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+nera\s+ottima\b', f'{brand} nero ottimo', re.IGNORECASE),
        (rf'\b{re.escape(brand)}\s+nera\s+bellissima\b', f'{brand} nero bellissimo', re.IGNORECASE),
        
        # Altri errori specifici
        (r'\bunic rossa\b', 'unica rossa', 0),
        (r'\bspecial rossa\b', 'speciale rossa', 0),
        (r'\bottima in nero\b', 'ottimo in nero', 0),
        
        # Ripetizioni ringraziamenti
        (r'Grazie per il tuo "like"[^.]*\. Intanto grazie per il tuo "like"', 'Grazie per il tuo "like"', 0),
        (r'per ringraziarti[^.]*\. [^.]*grazie[^.]*', lambda m: m.group(0).split('.')[0] + '.', 0),
        
        # Ripetizioni colore
        (r'\btotal black\s+nera?\b', 'total black', re.IGNORECASE),
        (r'\bnera?\s+total black\b', 'total black', re.IGNORECASE),
        (r'\bbianca?\s+candida?\b', 'bianca', re.IGNORECASE),
        (r'\brossa?\s+rosso acceso\b', 'rosso acceso', re.IGNORECASE),
        
        # Ripetizioni di brand
        (rf'\b{re.escape(brand_lower)}\s+{re.escape(brand_lower)}\b', brand, re.IGNORECASE),
        
        # Ripetizioni di articoli
        (r'\b(un|una)\s+(un|una)\b', r'\1', re.IGNORECASE),
        (r'\b(il|la|lo|gli|le)\s+(il|la|lo|gli|le)\b', r'\1', re.IGNORECASE),
        
        # Spazi e punteggiatura
        (r'\s+', ' '),
        (r'\s*,\s*,\s*', ', '),
        (r'\s*\.\s*\.\s*', '. '),
        (r'\s+([,.;:!?])', r'\1'),
        (r'([,.;:!?])\s*([,.;:!?])', r'\1')
    ]
    
    # Applica le correzioni (filtra pattern SKIP)
    messaggio_pulito = messaggio
    for pattern, replacement, *flags in patterns_problematici:
        if pattern == 'SKIP':  # Salta pattern condizionali non applicabili
            continue
        flag = flags[0] if flags else 0
        try:
            messaggio_pulito = re.sub(pattern, replacement, messaggio_pulito, flags=flag)
        except re.error:
            continue  # Salta pattern invalidi
    
    # 🎨 CORREZIONI STILISTICHE AVANZATE
    correzioni_manuali = {
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
    
    for errore, correzione in correzioni_manuali.items():
        messaggio_pulito = messaggio_pulito.replace(errore, correzione)
    
    # 🔤 CAPITALIZZAZIONE CORRETTA
    messaggio_pulito = messaggio_pulito.strip()
    if messaggio_pulito:
        # Capitalizza inizio messaggio
        messaggio_pulito = messaggio_pulito[0].upper() + messaggio_pulito[1:]
        
        # Capitalizza dopo punto
        messaggio_pulito = re.sub(r'(\.\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), messaggio_pulito)
    
    # ✅ VALIDAZIONE FINALE
    # Se il messaggio è troppo corto o problematico, usa fallback
    if len(messaggio_pulito) < 15 or messaggio_pulito.count('  ') > 2:
        return f"Ciao, è un bellissimo {brand} che ti piacerà! Ti sto inviando un'offerta speciale per il tuo interesse. Fammi sapere!"
    
    return messaggio_pulito

def _get_articolo_indeterminativo_corretto(genere: str, tipo: str) -> str:
    """Articoli indeterminativi grammaticalmente corretti - CORREZIONE APOSTROFI"""
    if genere == 'f':
        if tipo in ['scarpe', 'sneakers']:
            return 'delle'
        else:
            return 'una'
    else:
        if tipo in ['pantaloni', 'jeans']:
            return 'dei'
        elif tipo in ['occhiali', 'occhiale']:
            return 'degli'
        elif tipo.startswith(('a', 'e', 'i', 'o', 'u')):
            # CORREZIONE: "accessorio" deve essere "uno", non "un'"
            if tipo in ['accessorio', 'anello', 'orologio']:
                return 'uno'
            return "un'"  # Solo per parole femminili che iniziano per vocale
        else:
            return 'un'

# ===============================
# SISTEMA CACHE PER MESSAGGI (semplificato)
# ===============================

# FUNZIONI LEGACY RIMOSSE - SI USANO SOLO QUELLE PESATE

# ===============================
# MANTIENI COMPATIBILITÀ BACKWARD - RIMOSSE FUNZIONI SUPERFLUE
# ===============================

def pulisci_cache_frasi():
    """Pulisce la cache delle frasi per liberare memoria"""
    global MESSAGGI_RECENTI_CACHE
    MESSAGGI_RECENTI_CACHE.clear()
    logger.info("Cache messaggi recenti pulita - memoria liberata")

def get_articolo_unificato(genere: str, tipo: str, determinativo: bool = True) -> str:
    """FUNZIONE UNIFICATA per articoli determinativi e indeterminativi - OTTIMIZZATA"""
    if determinativo:
        if genere == 'f':
            return 'la' if tipo not in ['scarpe', 'borse'] else 'le'
        return 'il' if tipo not in ['pantaloni', 'occhiali'] else 'gli'
    else:
        if genere == 'f':
            return 'una' if tipo not in ['scarpe', 'borse'] else 'delle'
        return 'un' if tipo not in ['pantaloni', 'occhiali'] else 'degli'

# COMPATIBILITÀ LEGACY (da rimuovere gradualmente)
def _get_articolo_determinativo(genere: str, tipo: str) -> str:
    return get_articolo_unificato(genere, tipo, True)

def _get_articolo_indeterminativo(genere: str, tipo: str) -> str:
    return get_articolo_unificato(genere, tipo, False)

# ===============================
# ROUTES OTTIMIZZATE
# ===============================

@app.route('/')
@log_request_info
def index():
    """Homepage dell'applicazione"""
    return render_template('index.html')

@app.route('/static/js/sw.js')
def service_worker():
    """Service Worker per PWA con fallback"""
    try:
        return app.send_static_file('js/sw.js'), 200, {'Content-Type': 'application/javascript'}
    except Exception as e:
        logger.warning(f"Service worker non trovato: {e}")
        return "// Service worker non disponibile", 200, {'Content-Type': 'application/javascript'}

@app.route('/static/manifest.json')
def manifest():
    """Manifest per PWA con fallback"""
    try:
        return app.send_static_file('manifest.json')
    except Exception as e:
        logger.warning(f"Manifest non trovato: {e}")
        return jsonify({"name": "Vintage & Modern", "short_name": "V&M"}), 200

@app.route('/static/css/styles.css')
def styles_css():
    """CSS principale con fallback per Render"""
    try:
        return app.send_static_file('css/styles.css')
    except Exception as e:
        logger.warning(f"CSS non trovato: {e}")
        return "/* CSS non disponibile */", 200, {'Content-Type': 'text/css'}

@app.route('/static/js/performance.js')
def performance_js():
    """Performance JS con fallback per Render"""
    try:
        return app.send_static_file('js/performance.js')
    except Exception as e:
        logger.warning(f"Performance JS non trovato: {e}")
        return "// Performance JS non disponibile", 200, {'Content-Type': 'application/javascript'}

@app.route('/health')
def health_check():
    """Health check per monitoraggio sistema"""
    try:
        # Test connessione database con timeout
        from sqlalchemy import text
        result = db.session.execute(text('SELECT 1'))
        result.close()
        db.session.commit()
        
        db_status = "OK"
        db_url = str(db.engine.url)
        
        if "postgresql" in db_url:
            db_type = "PostgreSQL (Supabase)"
        elif "sqlite" in db_url:
            if "production" in db_url:
                db_type = "SQLite (Fallback)"
            else:
                db_type = "SQLite (Development)"
        else:
            db_type = "Unknown"
            
    except Exception as e:
        db_status = f"ERROR: {str(e)[:100]}"
        db_type = "DISCONNECTED"
        
        # Cleanup in caso di errore
        try:
            db.session.rollback()
            db.session.close()
        except:
            pass
    
    circuit_status = "OPEN" if is_circuit_open() else "CLOSED"
    
    health_status = {
        'status': 'OK' if db_status == 'OK' else 'DEGRADED',
        'database': {
            'status': db_status,
            'type': db_type,
            'circuit_breaker': circuit_status,
            'failures': SUPABASE_CIRCUIT_BREAKER['failures']
        },
        'system': {
            'fallback_active': 'sqlite' in db_type.lower(),
            'high_availability': True
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    return jsonify(health_status), 200, {'Content-Type': 'application/json'}

@app.route('/api/articoli', methods=['GET'])
@log_request_info
def get_articoli():
    """Ottiene tutti gli articoli con caching e paginazione opzionale"""
    def _get_articoli_query():
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
        
        # SEMPRE restituisci array per compatibilità frontend
        articoli = query.all()
        return [articolo.to_dict() for articolo in articoli]
    
    try:
        result = retry_db_operation(_get_articoli_query)
        logger.info(f"📦 Caricati {len(result)} articoli")
        return jsonify(result), 200
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Errore nel recupero articoli: {error_msg}")
        
        # Restituisci array vuoto in caso di errore per evitare crash frontend
        return jsonify([]), 200

@app.route('/api/articoli', methods=['POST'])
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
            try:
                # Validazione tipo file
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
                    return jsonify({'error': 'Tipo di file non supportato'}), 400
                
                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                logger.info(f"File salvato: {file_path}")
            except Exception as file_error:
                logger.warning(f"Errore salvataggio file: {file_error}")
                # Continua senza immagine invece di fallire
                filename = None

        # Conversione vintage
        vintage_value = data.get('vintage', 'false').lower()
        vintage_bool = vintage_value in ['true', '1', 'on', 'yes']

        # Creazione articolo con retry
        def _create_articolo():
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
            return articolo
        
        # Usa retry per operazioni database
        articolo = retry_db_operation(_create_articolo)
        
        logger.info(f"✅ Articolo creato con successo: {articolo.id} - {articolo.nome}")
        
        # Risposta sempre valida
        response_data = {
            'success': True,
            'message': 'Articolo creato con successo',
            'articolo': articolo.to_dict()
        }
        
        return jsonify(response_data), 201
        
    except Exception as e:
        # Cleanup in caso di errore
        try:
            db.session.rollback()
            db.session.close()
        except:
            pass
            
        error_msg = str(e)
        logger.error(f"❌ Errore nella creazione articolo: {error_msg}")
        
        # Risposta di errore strutturata
        return jsonify({
            'success': False,
            'error': 'Errore nella creazione dell\'articolo',
            'details': error_msg[:200]  # Limita lunghezza errore
        }), 500

@app.route('/api/articoli/<int:id>', methods=['PUT'])
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
        logger.info(f"✅ Articolo aggiornato: {articolo.id} - {articolo.nome}")
        
        return jsonify({
            'success': True,
            'message': 'Articolo aggiornato con successo',
            'articolo': articolo.to_dict()
        }), 200
        
    except Exception as e:
        try:
            db.session.rollback()
            db.session.close()
        except:
            pass
            
        error_msg = str(e)
        logger.error(f"❌ Errore nell'aggiornamento articolo {id}: {error_msg}")
        
        return jsonify({
            'success': False,
            'error': 'Errore nell\'aggiornamento dell\'articolo',
            'details': error_msg[:200]
        }), 500

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
            condizioni, rarita, articolo.vintage, target, termini_commerciali, id
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
    # Render usa PORT environment variable, default 3000 per locale
    port = int(os.environ.get('PORT', 3000))
    debug = not os.environ.get('DATABASE_URL')  # Debug solo in locale
    
    logger.info(f"🚀 Avvio applicazione su porta {port} (debug: {debug})")
    
    # Configurazione ottimizzata per Render
    if os.environ.get('DATABASE_URL'):
        # Produzione Render: configurazione ottimizzata
        app.run(debug=False, port=port, host='0.0.0.0', threaded=True)
    else:
        # Sviluppo locale
        app.run(debug=debug, port=port, host='0.0.0.0') 
