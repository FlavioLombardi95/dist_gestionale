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
    # Supabase richiede SSL - aggiungiamo sslmode se mancante
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
        vintage=data.get('vintage', False),
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
    articolo.vintage = data.get('vintage', False)
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
    """Genera frasi professionali nello stile degli esempi forniti"""
    
    # Riconosci il tipo di articolo
    tipo_articolo = riconosci_tipo_articolo(nome)
    
    # Costruisci descrizione materiali intelligente
    desc_materiali = ""
    if materiale and colore:
        if 'pelle' in materiale.lower() and any(mat in keywords_classificate['materiali'] for mat in ['tela', 'canvas', 'tessuto']):
            # Combinazione intelligente come negli esempi "tela e pelle nera"
            altri_materiali = [mat for mat in keywords_classificate['materiali'] if mat != materiale.lower()]
            if altri_materiali:
                desc_materiali = f"in {altri_materiali[0]} e {materiale.lower()} {colore.lower()}"
            else:
                desc_materiali = f"in {materiale.lower()} {colore.lower()}"
        else:
            desc_materiali = f"in {materiale.lower()} {colore.lower()}"
    elif materiale:
        desc_materiali = f"in {materiale.lower()}"
    elif colore:
        desc_materiali = f"nel colore {colore.lower()}"
    
    # Descrizione condizioni
    desc_condizioni = ""
    if condizioni:
        condizioni_map = {
            'Eccellenti': ['in condizioni eccellenti', 'in perfette condizioni', 'condizioni top', 'mantenuta perfettamente'],
            'Ottime': ['in ottime condizioni', 'ben conservata', 'tenuta benissimo', 'ben mantenuta'],
            'Buone': ['in buone condizioni', 'ben tenuta', 'conservata bene'],
            'Discrete': ['in discrete condizioni', 'usata ma funzionale']
        }
        desc_condizioni = random.choice(condizioni_map.get(condizioni, ['in buone condizioni']))
    
    # Descrizione rarità
    desc_rarita = ""
    if rarita and rarita != 'Comune':
        rarita_map = {
            'Introvabile': ['introvabile', 'ormai introvabile', 'molto difficile da trovare'],
            'Molto Raro': ['molto raro', 'raro', 'difficile da trovare', 'pezzo raro'],
            'Raro': ['raro', 'modello raro']
        }
        options = rarita_map.get(rarita, [])
        if options:
            desc_rarita = random.choice(options)
    
    # Aggettivi premium per brand di lusso
    aggettivi_brand = {
        'Dior': ['iconica', 'mitica', 'leggendaria', 'raffinata'],
        'Chanel': ['intramontabile', 'classica', 'elegante', 'iconica'],
        'Louis Vuitton': ['iconica', 'elegante', 'prestigiosa'],
        'Hermès': ['leggendaria', 'esclusiva', 'prestigiosa'],
        'Gucci': ['distintiva', 'elegante', 'iconica'],
        'Prada': ['sofisticata', 'elegante', 'moderna']
    }
    
    aggettivo_brand = random.choice(aggettivi_brand.get(brand, ['elegante', 'raffinata']))
    
    # Target specifici
    desc_target = ""
    if target:
        target_map = {
            'Intenditrici': 'Per intenditrici',
            'Collezionisti': 'Per veri collezionisti', 
            'Amanti del vintage': 'Per chi ama il vintage autentico',
            'Appassionati di lusso': 'Per appassionati di lusso',
            'Chi ama distinguersi': 'Per chi ama distinguersi'
        }
        desc_target = target_map.get(target, '')
    
    # Nome pulito senza brand
    nome_pulito = nome.replace(brand, '').strip()
    if not nome_pulito:
        nome_pulito = tipo_articolo
    
    # Template delle frasi (stile degli esempi)
    templates = [
        f"Eleganza senza tempo firmata {brand}: questa {nome_pulito} {desc_materiali} è un tesoro da collezione, {desc_condizioni}.",
        f"{aggettivo_brand.capitalize()} e iconica, la {brand} {nome_pulito} {desc_materiali} è perfetta per chi cerca stile e unicità.",
        f"Una {tipo_articolo} {desc_rarita} e affascinante {desc_materiali}, firmata {brand}: {desc_condizioni}, pronta per una nuova storia.",
        f"La mitica {brand} {nome_pulito}: {desc_materiali}, {desc_condizioni}. Un classico che non tramonta.",
        f"Un tocco di classe firmato {brand}: {nome_pulito} {desc_materiali}, {desc_rarita} e {desc_condizioni}.",
        f"{desc_target} di vintage e lusso: {brand} {nome_pulito} {desc_materiali}, {desc_condizioni}, {desc_rarita}.",
        f"Stile {brand.lower()} in chiave vintage: {nome_pulito} {desc_materiali} {desc_condizioni}. Un vero pezzo {desc_rarita}.",
        f"Un accessorio unico per chi ama distinguersi: {tipo_articolo} {brand} {nome_pulito} {desc_materiali}, {desc_condizioni} e {desc_rarita}.",
        f"Vintage di lusso? Questa {brand} {nome_pulito} {desc_materiali} fa al caso tuo. {desc_condizioni.capitalize()}, modello {desc_rarita}.",
        f"Intramontabile e raffinata: la {tipo_articolo} {brand} {nome_pulito} {desc_materiali}, {desc_rarita}, bellissima.",
        f"Eleganza discreta e fascino vintage: la {brand} {nome_pulito} {desc_materiali} è perfetta per ogni occasione.",
        f"{desc_rarita.capitalize()}, elegante e {desc_condizioni}: questa {brand} {nome_pulito} è un investimento di stile.",
        f"Finiture {desc_materiali} e firma {brand}: la {nome_pulito} è una {tipo_articolo} da vera intenditrice.",
        f"Un pezzo cult {desc_target.lower()}: {brand} {nome_pulito} {desc_materiali}, {desc_condizioni}.",
        f"Questa {brand} {nome_pulito} ha tutto: eleganza, storia e rarità. {desc_condizioni.capitalize()}, pronta per te.",
        f"Una {brand} che non passa inosservata: {nome_pulito} {desc_materiali}, {desc_rarita} e {desc_condizioni}.",
        f"{desc_target} del fascino discreto e della classe {brand}: {nome_pulito} vintage, {desc_condizioni}.",
        f"Collezionabile e chic: {brand} {nome_pulito} {desc_materiali}, {desc_condizioni}, un classico senza tempo.",
        f"{tipo_articolo.capitalize()} {brand} {nome_pulito} {desc_materiali}: {desc_rarita} in queste condizioni.",
        f"Semplicemente iconica: {brand} {nome_pulito} {desc_materiali}, perfetta {desc_target.lower()} del vintage esclusivo."
    ]
    
    # Pulisci e filtra template
    templates_validi = []
    for template in templates:
        # Pulisci la frase
        frase_pulita = re.sub(r'\s+', ' ', template)
        frase_pulita = frase_pulita.replace(' ,', ',').replace('  ', ' ').strip()
        frase_pulita = frase_pulita.replace(': ,', ':').replace(', ,', ',')
        
        # Aggiungi solo se non ha parti vuote
        if not any(x in frase_pulita for x in [': ,', ': .', ' :', 'None', ', .']):
            templates_validi.append(frase_pulita)
    
    if not templates_validi:
        frase_descrittiva = f"Elegante {tipo_articolo} {brand} {nome_pulito}, {desc_condizioni}."
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
