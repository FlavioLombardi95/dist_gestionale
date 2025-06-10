from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
import random
import re

app = Flask(__name__)

# Configurazione database: Supabase PostgreSQL con SSL
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # Supabase connessioni:
    # - Direct connection: db.[ref].supabase.co:5432 (IPv6 only) 
    # - Session mode: aws-0-[region].pooler.supabase.com:5432 (IPv4/IPv6) ← Render
    # - Transaction mode: aws-0-[region].pooler.supabase.com:6543 (IPv4/IPv6)
    
    # Assicuriamoci che sia in formato corretto
    if 'supabase.co' in DATABASE_URL and 'sslmode' not in DATABASE_URL:
        DATABASE_URL += '?sslmode=require'
    
    # Ensure postgresql:// format
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,  # Verifica connessioni prima dell'uso
        'pool_recycle': 300,    # Ricrea connessioni ogni 5 minuti
        'connect_args': {
            'sslmode': 'require'  # SSL richiesto per Supabase
        }
    }
    print(f"🔗 Connesso a Supabase PostgreSQL")
else:
    # Fallback a SQLite per sviluppo locale
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gestionale.db'
    print(f"🔗 Usando SQLite locale per sviluppo")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)

# Assicuriamoci che la cartella uploads esista
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class Articolo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    immagine = db.Column(db.String(200))
    colore = db.Column(db.String(50))
    materiale = db.Column(db.String(100))
    keywords = db.Column(db.Text)
    termini_commerciali = db.Column(db.Text)
    condizioni = db.Column(db.String(50))
    rarita = db.Column(db.String(50))
    vintage = db.Column(db.Boolean, default=False)
    target = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'brand': self.brand,
            'immagine': self.immagine,
            'colore': self.colore or '',
            'materiale': self.materiale or '',
            'keywords': self.keywords.split(',') if self.keywords else [],
            'termini_commerciali': self.termini_commerciali.split(',') if self.termini_commerciali else [],
            'condizioni': self.condizioni or '',
            'rarita': self.rarita or '',
            'vintage': self.vintage or False,
            'target': self.target or ''
        }

with app.app_context():
    # In produzione non droppiamo le tabelle, solo le creiamo se non esistono
    if os.environ.get('DATABASE_URL'):
        # Produzione: crea solo tabelle mancanti
        db.create_all()
    else:
        # Sviluppo locale: ricrea tutto
        db.drop_all()
        db.create_all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/articoli', methods=['GET'])
def get_articoli():
    articoli = Articolo.query.all()
    return jsonify([articolo.to_dict() for articolo in articoli])

@app.route('/api/articoli', methods=['POST'])
def create_articolo():
    data = request.form
    file = request.files.get('immagine')
    
    if file:
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    else:
        filename = None

    # Converti vintage da stringa a boolean
    vintage_value = data.get('vintage', 'false').lower()
    vintage_bool = vintage_value in ['true', '1', 'on', 'yes']

    articolo = Articolo(
        nome=data['nome'],
        brand=data['brand'],
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
    
    return jsonify(articolo.to_dict())

@app.route('/api/articoli/<int:id>', methods=['PUT'])
def update_articolo(id):
    articolo = Articolo.query.get_or_404(id)
    data = request.form
    
    articolo.nome = data['nome']
    articolo.brand = data['brand']
    articolo.colore = data.get('colore', '').strip()
    articolo.materiale = data.get('materiale', '').strip()
    articolo.keywords = data.get('keywords', '').strip()
    articolo.termini_commerciali = data.get('termini_commerciali', '').strip()
    articolo.condizioni = data.get('condizioni', '').strip()
    articolo.rarita = data.get('rarita', '').strip()
    
    # Converti vintage da stringa a boolean
    vintage_value = data.get('vintage', 'false').lower()
    vintage_bool = vintage_value in ['true', '1', 'on', 'yes']
    articolo.vintage = vintage_bool
    
    articolo.target = data.get('target', '').strip()
    
    file = request.files.get('immagine')
    if file:
        # Elimina vecchia immagine se esiste
        if articolo.immagine:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], articolo.immagine)
            if os.path.exists(old_path):
                os.remove(old_path)
        
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        articolo.immagine = filename
    
    db.session.commit()
    return jsonify(articolo.to_dict())

@app.route('/api/articoli/<int:id>', methods=['DELETE'])
def delete_articolo(id):
    articolo = Articolo.query.get_or_404(id)
    
    if articolo.immagine:
        path = os.path.join(app.config['UPLOAD_FOLDER'], articolo.immagine)
        if os.path.exists(path):
            os.remove(path)
    
    db.session.delete(articolo)
    db.session.commit()
    return '', 204

def format_keywords(keywords):
    # Rimuove spazi e capitalizza solo la prima lettera
    return [kw.strip().lower() for kw in keywords if kw.strip()]

def classifica_keywords(keywords):
    """Classifica le keywords in categorie semantiche"""
    keywords_lower = [kw.strip().lower() for kw in keywords if kw.strip()]
    
    colori = ['nero', 'bianco', 'rosso', 'blu', 'verde', 'giallo', 'marrone', 'beige', 'rosa', 'viola', 'arancione', 'grigio', 'oro', 'argento', 'celeste', 'azzurro', 'bordeaux', 'navy', 'cammello', 'ecru', 'turchese', 'corallo']
    
    materiali = ['pelle', 'tessuto', 'cotone', 'seta', 'nylon', 'lino', 'jeans', 'velluto', 'camoscio', 'canvas', 'paglia', 'lana', 'eco-pelle', 'vernice', 'gomma', 'lycra', 'poliestere', 'cashmere', 'raso', 'tela', 'mesh', 'suede']
    
    stili = ['elegante', 'casual', 'sportivo', 'chic', 'vintage', 'moderno', 'classico', 'trendy', 'glamour', 'minimale', 'bohemian', 'rock', 'sofisticato', 'raffinato', 'contemporaneo', 'femminile', 'androgino']
    
    caratteristiche_positive = ['comodo', 'versatile', 'pratico', 'resistente', 'leggero', 'morbido', 'durevole', 'flessibile', 'elastico', 'traspirante', 'impermeabile', 'lussuoso', 'pregiato', 'esclusivo']
    
    forme_dimensioni = ['ampio', 'fitted', 'aderente', 'oversize', 'slim', 'largo', 'stretto', 'lungo', 'corto', 'mini', 'midi', 'maxi']
    
    dettagli_design = ['tracolla', 'zip', 'bottoni', 'borchie', 'frange', 'pizzo', 'ricami', 'stampa', 'monogramma', 'logo', 'catena', 'fibbia', 'lacci']
    
    risultato = {
        'colori': [kw for kw in keywords_lower if kw in colori],
        'materiali': [kw for kw in keywords_lower if kw in materiali],
        'stili': [kw for kw in keywords_lower if kw in stili],
        'caratteristiche': [kw for kw in keywords_lower if kw in caratteristiche_positive],
        'forme': [kw for kw in keywords_lower if kw in forme_dimensioni],
        'dettagli': [kw for kw in keywords_lower if kw in dettagli_design],
        'altre': [kw for kw in keywords_lower if kw not in colori + materiali + stili + caratteristiche_positive + forme_dimensioni + dettagli_design]
    }
    
    return risultato

def riconosci_tipo_articolo(nome):
    """Riconosce il tipo di articolo dal nome"""
    nome_lower = nome.lower()
    
    if any(word in nome_lower for word in ['borsa', 'borse', 'bag', 'clutch', 'pochette', 'zaino', 'trolley', 'valigia']):
        return 'borsa'
    elif any(word in nome_lower for word in ['scarpa', 'scarpe', 'sandalo', 'sandali', 'boot', 'stivale', 'sneaker', 'decollete', 'pump']):
        return 'scarpe'
    elif any(word in nome_lower for word in ['vestito', 'abito', 'dress', 'gonna', 'skirt']):
        return 'vestito'
    elif any(word in nome_lower for word in ['camicia', 'shirt', 'blusa', 'top', 'maglia', 't-shirt', 'polo']):
        return 'top'
    elif any(word in nome_lower for word in ['pantalone', 'pantaloni', 'jeans', 'short', 'bermuda']):
        return 'pantaloni'
    elif any(word in nome_lower for word in ['giacca', 'blazer', 'coat', 'cappotto', 'giubbotto', 'parka']):
        return 'giacca'
    elif any(word in nome_lower for word in ['accessorio', 'accessori', 'cintura', 'belt', 'sciarpa', 'foulard', 'cappello']):
        return 'accessorio'
    else:
        return 'generico'

def genera_frase_stile_professionale(brand, nome, colore, materiale, keywords_classificate, condizioni, rarita, vintage, target, termini_commerciali):
    """Genera frasi professionali con grammatica italiana corretta"""
    
    # Riconosci il tipo di articolo e genere
    tipo_articolo = riconosci_tipo_articolo(nome)
    
    # Definisci genere degli articoli
    generi = {
        'borsa': 'f',     # femminile
        'scarpe': 'f',    # femminile plurale
        'vestito': 'm',   # maschile
        'top': 'm',       # maschile
        'pantaloni': 'm', # maschile plurale
        'giacca': 'f',    # femminile
        'accessorio': 'm', # maschile
        'generico': 'm'   # default maschile
    }
    
    genere = generi.get(tipo_articolo, 'm')
    
    # Funzione per concordare aggettivi
    def concordanza_aggettivo(aggettivo, genere_target):
        """Converte aggettivi al genere corretto"""
        maschili_femminili = {
            'nero': {'m': 'nero', 'f': 'nera'},
            'bianco': {'m': 'bianco', 'f': 'bianca'},
            'rosso': {'m': 'rosso', 'f': 'rossa'},
            'blu': {'m': 'blu', 'f': 'blu'},  # invariabile
            'verde': {'m': 'verde', 'f': 'verde'},  # invariabile
            'marrone': {'m': 'marrone', 'f': 'marrone'},  # invariabile
            'beige': {'m': 'beige', 'f': 'beige'},  # invariabile
            'grigio': {'m': 'grigio', 'f': 'grigia'},
            'rosa': {'m': 'rosa', 'f': 'rosa'},  # invariabile
            'giallo': {'m': 'giallo', 'f': 'gialla'},
            'viola': {'m': 'viola', 'f': 'viola'},  # invariabile
            'raro': {'m': 'raro', 'f': 'rara'},
            'nuovo': {'m': 'nuovo', 'f': 'nuova'},
            'usato': {'m': 'usato', 'f': 'usata'},
            'perfetto': {'m': 'perfetto', 'f': 'perfetta'},
            'elegante': {'m': 'elegante', 'f': 'elegante'},  # invariabile
            'iconico': {'m': 'iconico', 'f': 'iconica'},
            'esclusivo': {'m': 'esclusivo', 'f': 'esclusiva'},
            'introvabile': {'m': 'introvabile', 'f': 'introvabile'}  # invariabile
        }
        
        if aggettivo.lower() in maschili_femminili:
            return maschili_femminili[aggettivo.lower()][genere_target]
        return aggettivo  # se non trovato, restituisce così com'è
    
    # Articoli determinativi
    def articolo_determinativo(genere_target, tipo):
        if genere_target == 'f':
            return 'la' if tipo != 'scarpe' else 'le'
        else:
            return 'il' if tipo not in ['pantaloni'] else 'i'
    
    def articolo_indeterminativo(genere_target, tipo):
        if genere_target == 'f':
            return 'una' if tipo != 'scarpe' else 'delle'
        else:
            return 'un' if tipo not in ['pantaloni'] else 'dei'
    
    # Nome pulito senza ripetizioni di brand
    nome_pulito = nome.replace(brand, '').strip()
    # Evita ripetizione del tipo articolo se già presente
    if tipo_articolo.lower() in nome_pulito.lower():
        nome_semplificato = nome_pulito
    else:
        nome_semplificato = f"{tipo_articolo} {nome_pulito}".strip()
    
    # Costruisci descrizione materiali con concordanza corretta
    desc_materiali = ""
    if materiale and colore:
        colore_concordato = concordanza_aggettivo(colore, genere)
        if 'pelle' in materiale.lower() and any(mat in keywords_classificate['materiali'] for mat in ['tela', 'canvas', 'tessuto']):
            altri_materiali = [mat for mat in keywords_classificate['materiali'] if mat != materiale.lower()]
            if altri_materiali:
                desc_materiali = f"in {altri_materiali[0]} e pelle {colore_concordato}"
            else:
                desc_materiali = f"in pelle {colore_concordato}"
        else:
            desc_materiali = f"in {materiale.lower()} {colore_concordato}"
    elif materiale:
        desc_materiali = f"in {materiale.lower()}"
    elif colore:
        colore_concordato = concordanza_aggettivo(colore, genere)
        desc_materiali = f"color {colore_concordato}"
    
    # Descrizione condizioni con concordanza
    desc_condizioni = ""
    if condizioni:
        condizioni_concordate = {
            'Eccellenti': [
                f"in condizioni eccellenti",
                f"in perfette condizioni", 
                f"mantenut{('a' if genere == 'f' else 'o')} perfettamente"
            ],
            'Ottime': [
                f"in ottime condizioni",
                f"ben conservat{('a' if genere == 'f' else 'o')}",
                f"tenut{('a' if genere == 'f' else 'o')} benissimo"
            ],
            'Buone': [
                f"in buone condizioni",
                f"ben tenut{('a' if genere == 'f' else 'o')}"
            ],
            'Discrete': [
                f"in discrete condizioni",
                f"usat{('a' if genere == 'f' else 'o')} ma funzionale"
            ]
        }
        desc_condizioni = random.choice(condizioni_concordate.get(condizioni, ['in buone condizioni']))
    
    # Descrizione rarità con concordanza
    desc_rarita = ""
    if rarita and rarita != 'Comune':
        rarita_concordata = {
            'Introvabile': [concordanza_aggettivo('introvabile', genere)],
            'Molto Raro': [concordanza_aggettivo('raro', genere), f"molto {concordanza_aggettivo('raro', genere)}"],
            'Raro': [concordanza_aggettivo('raro', genere)]
        }
        options = rarita_concordata.get(rarita, [])
        if options:
            desc_rarita = random.choice(options)
    
    # Aggettivi premium per brand di lusso (concordati)
    aggettivi_brand = {
        'Dior': ['iconica', 'mitica', 'leggendaria', 'raffinata'],
        'Chanel': ['intramontabile', 'classica', 'elegante', 'iconica'],
        'Louis Vuitton': ['iconica', 'elegante', 'prestigiosa'],
        'Hermès': ['leggendaria', 'esclusiva', 'prestigiosa'],
        'Gucci': ['distintiva', 'elegante', 'iconica'],
        'Prada': ['sofisticata', 'elegante', 'moderna']
    }
    
    aggettivo_brand_base = random.choice(aggettivi_brand.get(brand, ['elegante', 'raffinata']))
    aggettivo_brand = concordanza_aggettivo(aggettivo_brand_base, genere)
    
    # Target specifici
    desc_target = ""
    if target:
        target_map = {
            'Intenditrici': 'per intenditrici',
            'Collezionisti': 'per veri collezionisti', 
            'Amanti del vintage': 'per chi ama il vintage autentico',
            'Appassionati di lusso': 'per appassionati di lusso',
            'Chi ama distinguersi': 'per chi ama distinguersi'
        }
        desc_target = target_map.get(target, '')
    
    # Template delle frasi con grammatica corretta
    art_det = articolo_determinativo(genere, tipo_articolo)
    art_indet = articolo_indeterminativo(genere, tipo_articolo)
    
    templates = [
        f"Eleganza senza tempo firmata {brand}: quest{('a' if genere == 'f' else 'o')} {nome_semplificato} {desc_materiali} è un tesoro da collezione, {desc_condizioni}.",
        f"{aggettivo_brand.capitalize()} e {concordanza_aggettivo('iconico', genere)}, {art_det} {brand} {nome_semplificato} {desc_materiali} è perfett{('a' if genere == 'f' else 'o')} per chi cerca stile e unicità.",
        f"{art_indet.capitalize()} {nome_semplificato} {desc_rarita} e affascinante {desc_materiali}, firmat{('a' if genere == 'f' else 'o')} {brand}: {desc_condizioni}, pront{('a' if genere == 'f' else 'o')} per una nuova storia.",
        f"{art_det.capitalize()} mitic{('a' if genere == 'f' else 'o')} {brand} {nome_semplificato}: {desc_materiali}, {desc_condizioni}. Un classico che non tramonta.",
        f"Un tocco di classe firmato {brand}: {nome_semplificato} {desc_materiali}, {desc_rarita} e {desc_condizioni}.",
        f"Perfett{('a' if genere == 'f' else 'o')} {desc_target}: {brand} {nome_semplificato} {desc_materiali}, {desc_condizioni}.",
        f"Stile {brand.lower()} in chiave vintage: {nome_semplificato} {desc_materiali} {desc_condizioni}. Un vero pezzo {desc_rarita}.",
        f"Vintage di lusso? Quest{('a' if genere == 'f' else 'o')} {brand} {nome_semplificato} {desc_materiali} fa al caso tuo. {desc_condizioni.capitalize()}.",
        f"Intramontabile e raffinat{('a' if genere == 'f' else 'o')}: {art_det} {brand} {nome_semplificato} {desc_materiali}, {desc_rarita}, bellissim{('a' if genere == 'f' else 'o')}.",
        f"Eleganza discreta e fascino vintage: {art_det} {brand} {nome_semplificato} {desc_materiali} è perfett{('a' if genere == 'f' else 'o')} per ogni occasione.",
        f"{desc_rarita.capitalize()}, elegante e {desc_condizioni}: quest{('a' if genere == 'f' else 'o')} {brand} {nome_semplificato} è un investimento di stile.",
        f"Finiture {desc_materiali} e firma {brand}: {art_det} {nome_semplificato} è {art_indet} {tipo_articolo} da vera intenditrice.",
        f"Un pezzo cult {desc_target}: {brand} {nome_semplificato} {desc_materiali}, {desc_condizioni}.",
        f"Quest{('a' if genere == 'f' else 'o')} {brand} {nome_semplificato} ha tutto: eleganza, storia e rarità. {desc_condizioni.capitalize()}.",
        f"{art_indet.capitalize()} {brand} che non passa inoservat{('a' if genere == 'f' else 'o')}: {nome_semplificato} {desc_materiali}, {desc_rarita}.",
        f"Perfett{('a' if genere == 'f' else 'o')} {desc_target} del fascino discreto: {brand} {nome_semplificato} vintage, {desc_condizioni}.",
        f"Collezionabile e chic: {brand} {nome_semplificato} {desc_materiali}, {desc_condizioni}, un classico senza tempo.",
        f"{tipo_articolo.capitalize()} {brand} {nome_semplificato} {desc_materiali}: {desc_rarita} in queste condizioni.",
        f"Semplicemente {concordanza_aggettivo('iconico', genere)}: {brand} {nome_semplificato} {desc_materiali}, perfett{('a' if genere == 'f' else 'o')} {desc_target}."
    ]
    
    # Pulisci e filtra template
    templates_validi = []
    for template in templates:
        # Pulisci la frase
        frase_pulita = re.sub(r'\s+', ' ', template)
        frase_pulita = frase_pulita.replace(' ,', ',').replace('  ', ' ').strip()
        frase_pulita = frase_pulita.replace(': ,', ':').replace(', ,', ',')
        frase_pulita = frase_pulita.replace(' :', ':').replace('.,', '.').replace(',.', '.')
        
        # Aggiungi solo se non ha parti vuote o malformate
        if not any(x in frase_pulita for x in [': ,', ': .', ' :', 'None', ', .', ' ,', '  ']):
            templates_validi.append(frase_pulita)
    
    if not templates_validi:
        frase_descrittiva = f"Elegante {nome_semplificato} {brand}, {desc_condizioni}."
    else:
        frase_descrittiva = random.choice(templates_validi)
    
    # === CALL TO ACTION ===
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
    
    # Termini commerciali personalizzati
    if termini_commerciali:
        # termini_commerciali è già una lista, non serve split
        termini_disponibili = [t.strip() for t in termini_commerciali if t.strip()]
        if termini_disponibili:
            termine = random.choice(termini_disponibili)
            call_to_actions.extend([
                f"Abbiamo attivato per te una {termine} esclusiva: controlla subito!",
                f"Ti abbiamo riservato una {termine} speciale, già disponibile nel tuo account.",
                f"Approfitta della {termine} che ti abbiamo appena inviato."
            ])
    
    call_to_action = random.choice(call_to_actions)
    
    # Combina frase descrittiva + call to action
    frase_finale = f"{frase_descrittiva}\n{call_to_action}"
    
    return frase_finale

@app.route('/api/genera-frase/<int:id>', methods=['GET'])
def genera_frase(id):
    articolo = Articolo.query.get_or_404(id)
    
    # Estrai tutti i dati dall'articolo
    colore = articolo.colore.strip() if articolo.colore else ''
    materiale = articolo.materiale.strip() if articolo.materiale else ''
    keywords = articolo.keywords.split(',') if articolo.keywords else []
    termini_commerciali = articolo.termini_commerciali.split(',') if articolo.termini_commerciali else []
    condizioni = articolo.condizioni.strip() if articolo.condizioni else ''
    rarita = articolo.rarita.strip() if articolo.rarita else ''
    vintage = articolo.vintage
    target = articolo.target.strip() if articolo.target else ''
    
    # Classifica le keywords
    keywords_classificate = classifica_keywords(keywords)
    
    # Genera la frase in stile professionale
    frase = genera_frase_stile_professionale(
        articolo.brand, 
        articolo.nome, 
        colore, 
        materiale, 
        keywords_classificate, 
        condizioni,
        rarita,
        vintage,
        target,
        termini_commerciali
    )
    
    return jsonify({'frase': frase})

if __name__ == '__main__':
    app.run(debug=True) 
