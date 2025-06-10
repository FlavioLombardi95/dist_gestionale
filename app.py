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
    
    # Mappatura ottimizzata
    tipo_mapping = {
        'borsa': ['borsa', 'borse', 'bag', 'clutch', 'pochette', 'zaino', 'trolley', 'valigia'],
        'scarpe': ['scarpa', 'scarpe', 'sandalo', 'sandali', 'boot', 'stivale', 'sneaker', 'decollete', 'pump'],
        'vestito': ['vestito', 'abito', 'dress', 'gonna', 'skirt'],
        'top': ['camicia', 'shirt', 'blusa', 'top', 'maglia', 't-shirt', 'polo'],
        'pantaloni': ['pantalone', 'pantaloni', 'jeans', 'short', 'bermuda'],
        'giacca': ['giacca', 'blazer', 'coat', 'cappotto', 'giubbotto', 'parka'],
        'accessorio': ['accessorio', 'accessori', 'cintura', 'belt', 'sciarpa', 'foulard', 'cappello']
    }
    
    for tipo, keywords in tipo_mapping.items():
        if any(keyword in nome_lower for keyword in keywords):
            return tipo
    
    return 'generico'

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
    """Converte aggettivi al genere corretto con cache"""
    if not aggettivo:
        return aggettivo
        
    # Mappatura ottimizzata
    concordanze = {
        'nero': {'m': 'nero', 'f': 'nera'},
        'bianco': {'m': 'bianco', 'f': 'bianca'},
        'rosso': {'m': 'rosso', 'f': 'rossa'},
        'grigio': {'m': 'grigio', 'f': 'grigia'},
        'giallo': {'m': 'giallo', 'f': 'gialla'},
        'raro': {'m': 'raro', 'f': 'rara'},
        'nuovo': {'m': 'nuovo', 'f': 'nuova'},
        'usato': {'m': 'usato', 'f': 'usata'},
        'perfetto': {'m': 'perfetto', 'f': 'perfetta'},
        'iconico': {'m': 'iconico', 'f': 'iconica'},
        'esclusivo': {'m': 'esclusivo', 'f': 'esclusiva'},
    }
    
    aggettivo_lower = aggettivo.lower()
    if aggettivo_lower in concordanze:
        return concordanze[aggettivo_lower].get(genere, aggettivo)
    
    return aggettivo

def genera_frase_stile_professionale(brand: str, nome: str, colore: str, materiale: str, 
                                   keywords_classificate: Dict, condizioni: str, rarita: str, 
                                   vintage: bool, target: str, termini_commerciali: List[str]) -> str:
    """Genera frasi professionali ottimizzate"""
    
    # Cache per tipo e genere
    tipo_articolo = get_tipo_articolo_cached(nome)
    genere = get_genere_cached(tipo_articolo)
    
    # Costruzione nome ottimizzata
    nome_completo_corretto = _costruisci_nome_corretto(nome, brand, tipo_articolo)
    
    # Descrizioni ottimizzate
    desc_materiali = _costruisci_descrizione_materiali(materiale, colore, keywords_classificate, genere)
    desc_condizioni = _costruisci_descrizione_condizioni(condizioni, genere)
    desc_rarita = _costruisci_descrizione_rarita(rarita, genere)
    desc_target = _costruisci_descrizione_target(target)
    
    # Aggettivo brand
    aggettivo_brand = _get_aggettivo_brand(brand, genere)
    
    # Articoli
    art_det = _get_articolo_determinativo(genere, tipo_articolo)
    art_indet = _get_articolo_indeterminativo(genere, tipo_articolo)
    
    # Template ottimizzati
    templates = _get_templates_frasi(
        nome_completo_corretto, desc_materiali, desc_condizioni, desc_rarita,
        desc_target, aggettivo_brand, art_det, art_indet, genere
    )
    
    # Selezione template valido
    frase_descrittiva = _seleziona_template_valido(templates, nome_completo_corretto, brand)
    
    # Call to action
    call_to_action = _genera_call_to_action(termini_commerciali)
    
    return f"{frase_descrittiva}\n{call_to_action}"

def _costruisci_nome_corretto(nome: str, brand: str, tipo_articolo: str) -> str:
    """Costruisce il nome grammaticalmente corretto"""
    nome_pulito = nome.replace(brand, '').strip()
    
    # Rimuovi varianti del tipo articolo
    varianti_tipo = [
        tipo_articolo.lower(), tipo_articolo.lower() + 's', tipo_articolo.lower() + 'e',
        tipo_articolo.capitalize(), tipo_articolo.upper()
    ]
    
    for variante in varianti_tipo:
        nome_pulito = nome_pulito.replace(variante, '').strip()
    
    nome_pulito = re.sub(r'\s+', ' ', nome_pulito).strip()
    
    if nome_pulito:
        return f"{tipo_articolo.lower()} {brand} {nome_pulito}".strip()
    else:
        return f"{tipo_articolo.lower()} {brand}".strip()

def _costruisci_descrizione_materiali(materiale: str, colore: str, keywords_classificate: Dict, genere: str) -> str:
    """Costruisce la descrizione dei materiali"""
    if not materiale and not colore:
        return ""
    
    if materiale and colore:
        colore_concordato = concordanza_aggettivo(colore, genere)
        if 'pelle' in materiale.lower():
            altri_materiali = [mat for mat in keywords_classificate.get('materiali', []) if mat != materiale.lower()]
            if altri_materiali:
                return f"in {altri_materiali[0]} e pelle {colore_concordato}"
            return f"in pelle {colore_concordato}"
        return f"in {materiale.lower()} {colore_concordato}"
    elif materiale:
        return f"in {materiale.lower()}"
    else:
        colore_concordato = concordanza_aggettivo(colore, genere)
        return f"color {colore_concordato}"

def _costruisci_descrizione_condizioni(condizioni: str, genere: str) -> str:
    """Costruisce la descrizione delle condizioni"""
    if not condizioni:
        return ""
    
    suffisso = 'a' if genere == 'f' else 'o'
    
    condizioni_map = {
        'Eccellenti': [
            "in condizioni eccellenti",
            "in perfette condizioni", 
            f"mantenut{suffisso} perfettamente"
        ],
        'Ottime': [
            "in ottime condizioni",
            f"ben conservat{suffisso}",
            f"tenut{suffisso} benissimo"
        ],
        'Buone': [
            "in buone condizioni",
            f"ben tenut{suffisso}"
        ],
        'Discrete': [
            "in discrete condizioni",
            f"usat{suffisso} ma funzionale"
        ]
    }
    
    return random.choice(condizioni_map.get(condizioni, ['in buone condizioni']))

def _costruisci_descrizione_rarita(rarita: str, genere: str) -> str:
    """Costruisce la descrizione della rarità"""
    if not rarita or rarita == 'Comune':
        return ""
    
    rarita_map = {
        'Introvabile': [concordanza_aggettivo('introvabile', genere)],
        'Molto Raro': [concordanza_aggettivo('raro', genere), f"molto {concordanza_aggettivo('raro', genere)}"],
        'Raro': [concordanza_aggettivo('raro', genere)]
    }
    
    options = rarita_map.get(rarita, [])
    return random.choice(options) if options else ""

def _costruisci_descrizione_target(target: str) -> str:
    """Costruisce la descrizione del target"""
    if not target:
        return ""
    
    target_map = {
        'Intenditrici': 'per intenditrici',
        'Collezionisti': 'per veri collezionisti', 
        'Amanti del vintage': 'per chi ama il vintage autentico',
        'Appassionati di lusso': 'per appassionati di lusso',
        'Chi ama distinguersi': 'per chi ama distinguersi'
    }
    
    return target_map.get(target, '')

def _get_aggettivo_brand(brand: str, genere: str) -> str:
    """Ottiene l'aggettivo concordato per il brand"""
    aggettivi_brand = {
        'Dior': ['iconica', 'mitica', 'leggendaria', 'raffinata'],
        'Chanel': ['intramontabile', 'classica', 'elegante', 'iconica'],
        'Louis Vuitton': ['iconica', 'elegante', 'prestigiosa'],
        'Hermès': ['leggendaria', 'esclusiva', 'prestigiosa'],
        'Gucci': ['distintiva', 'elegante', 'iconica'],
        'Prada': ['sofisticata', 'elegante', 'moderna']
    }
    
    aggettivo_base = random.choice(aggettivi_brand.get(brand, ['elegante', 'raffinata']))
    return concordanza_aggettivo(aggettivo_base, genere)

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

def _get_templates_frasi(nome_completo: str, desc_materiali: str, desc_condizioni: str, 
                        desc_rarita: str, desc_target: str, aggettivo_brand: str,
                        art_det: str, art_indet: str, genere: str) -> List[str]:
    """Ottiene la lista dei template per le frasi"""
    suffisso = 'a' if genere == 'f' else 'o'
    
    return [
        f"Eleganza senza tempo: quest{suffisso} {nome_completo} {desc_materiali} è un tesoro da collezione, {desc_condizioni}.",
        f"{aggettivo_brand.capitalize()} e {concordanza_aggettivo('iconico', genere)}, {art_det} {nome_completo} {desc_materiali} è perfett{suffisso} per chi cerca stile e unicità.",
        f"{art_indet.capitalize()} {nome_completo} {desc_rarita} e affascinante {desc_materiali}: {desc_condizioni}, pront{suffisso} per una nuova storia.",
        f"{art_det.capitalize()} mitic{suffisso} {nome_completo}: {desc_materiali}, {desc_condizioni}. Un classico che non tramonta.",
        f"Un tocco di classe: {nome_completo} {desc_materiali}, {desc_rarita} e {desc_condizioni}.",
        f"Perfett{suffisso} {desc_target}: {nome_completo} {desc_materiali}, {desc_condizioni}.",
        f"Stile vintage: {nome_completo} {desc_materiali} {desc_condizioni}. Un vero pezzo {desc_rarita}.",
        f"Vintage di lusso? Quest{suffisso} {nome_completo} {desc_materiali} fa al caso tuo. {desc_condizioni.capitalize()}.",
        f"Intramontabile e raffinat{suffisso}: {art_det} {nome_completo} {desc_materiali}, {desc_rarita}, bellissim{suffisso}.",
        f"Eleganza discreta e fascino vintage: {art_det} {nome_completo} {desc_materiali} è perfett{suffisso} per ogni occasione.",
        f"{desc_rarita.capitalize()}, elegante e {desc_condizioni}: quest{suffisso} {nome_completo} è un investimento di stile.",
        f"Finiture {desc_materiali}: {art_det} {nome_completo} è un pezzo da vera intenditrice.",
        f"Un pezzo cult {desc_target}: {nome_completo} {desc_materiali}, {desc_condizioni}.",
        f"Quest{suffisso} {nome_completo} ha tutto: eleganza, storia e rarità. {desc_condizioni.capitalize()}.",
        f"{art_indet.capitalize()} che non passa inosservat{suffisso}: {nome_completo} {desc_materiali}, {desc_rarita}.",
        f"Perfett{suffisso} {desc_target} del fascino discreto: {nome_completo} vintage, {desc_condizioni}.",
        f"Collezionabile e chic: {nome_completo} {desc_materiali}, {desc_condizioni}, un classico senza tempo.",
        f"{nome_completo.capitalize()} {desc_materiali}: {desc_rarita} in queste condizioni.",
        f"Semplicemente {concordanza_aggettivo('iconico', genere)}: {nome_completo} {desc_materiali}, perfett{suffisso} {desc_target}."
    ]

def _seleziona_template_valido(templates: List[str], nome_completo: str, brand: str) -> str:
    """Seleziona un template valido e lo pulisce"""
    templates_validi = []
    
    for template in templates:
        # Pulisci la frase
        frase_pulita = re.sub(r'\s+', ' ', template)
        frase_pulita = frase_pulita.replace(' ,', ',').replace('  ', ' ').strip()
        frase_pulita = frase_pulita.replace(': ,', ':').replace(', ,', ',')
        frase_pulita = frase_pulita.replace(' :', ':').replace('.,', '.').replace(',.', '.')
        
        # Filtra frasi malformate
        if not any(x in frase_pulita for x in [': ,', ': .', ' :', 'None', ', .', ' ,', '  ']):
            templates_validi.append(frase_pulita)
    
    if not templates_validi:
        return f"Elegante {nome_completo} {brand}, in ottime condizioni."
    
    return random.choice(templates_validi)

def _genera_call_to_action(termini_commerciali: List[str]) -> str:
    """Genera la call to action"""
    call_to_actions = [
        "Guarda tra i tuoi messaggi: c'è un'offerta ancora più vantaggiosa che ti abbiamo appena inviato.",
        "Ti abbiamo riservato un'offerta esclusiva con un ribasso extra.",
        "Dai un'occhiata alla nostra proposta scontata che ti abbiamo appena inviato.",
        "Controlla subito la tua casella: c'è un'offerta speciale con uno sconto in più per te.",
        "Approfitta dell'ulteriore sconto che ti abbiamo appena mandato.",
        "Ti abbiamo appena fatto arrivare un'offerta personale con uno sconto extra.",
        "Controlla i tuoi messaggi, ti aspetta un'ulteriore sorpresa.",
        "Diamo valore alla tua attenzione: ti abbiamo mandato uno sconto aggiuntivo.",
        "Guarda la proposta che ti abbiamo appena inviato, c'è un extra sconto incluso.",
        "Ti sta aspettando un'offerta con un ulteriore ribasso, già inviata!",
        "Dai un'occhiata all'offerta privata con sconto extra che ti abbiamo appena spedito.",
        "Controlla i tuoi messaggi, troverai uno sconto in più dedicato solo a te.",
        "Ti abbiamo appena inviato un'offerta speciale con un ulteriore ribasso.",
        "Guarda subito l'offerta personale con sconto aggiuntivo che ti abbiamo mandato.",
        "Nel tuo account c'è un ulteriore sconto riservato in esclusiva: appena inviato!",
        "Abbiamo preparato per te un'offerta scontata ancora più conveniente.",
        "Ti è stata inviata un'offerta con uno sconto supplementare: non lasciartela scappare.",
        "Guarda l'offerta extra che ti abbiamo appena riservato, è valida per poco.",
        "Abbiamo aggiunto uno sconto ulteriore per te: controlla la tua area offerte.",
        "Abbiamo appena applicato un ulteriore sconto alla tua offerta: non perdere!"
    ]
    
    # Aggiungi termini personalizzati se presenti
    if termini_commerciali:
        for termine in termini_commerciali:
            if 'sconto' in termine.lower():
                call_to_actions.extend([
                    f"Abbiamo attivato per te uno {termine} esclusivo: controlla subito!",
                    f"Ti abbiamo riservato uno {termine} speciale, già disponibile nel tuo account.",
                    f"Approfitta dello {termine} che ti abbiamo appena inviato."
                ])
            elif 'offerta' in termine.lower():
                call_to_actions.extend([
                    f"Abbiamo attivato per te un'{termine} esclusiva: controlla subito!",
                    f"Ti abbiamo riservato un'{termine} speciale, già disponibile nel tuo account.",
                    f"Approfitta dell'{termine} che ti abbiamo appena inviato."
                ])
    
    return random.choice(call_to_actions)

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
    """Genera una frase professionale per l'articolo"""
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
        
        # Classifica keywords con cache
        keywords_str = ','.join(keywords)
        keywords_classificate = classifica_keywords_cached(keywords_str) if keywords_str else {}
        
        # Genera la frase
        frase = genera_frase_stile_professionale(
            articolo.brand, articolo.nome, colore, materiale, keywords_classificate,
            condizioni, rarita, articolo.vintage, target, termini_commerciali
        )
        
        logger.info(f"Frase generata per articolo {id}")
        return jsonify({'frase': frase})
        
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
