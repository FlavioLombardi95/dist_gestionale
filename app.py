from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
import random
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gestionale.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)

# Assicuriamoci che la cartella uploads esista
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class Articolo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    immagine = db.Column(db.String(200))
    keywords = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    colore = db.Column(db.String(50))
    materiale = db.Column(db.String(50))

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'brand': self.brand,
            'immagine': self.immagine,
            'colore': self.colore,
            'materiale': self.materiale,
            'keywords': self.keywords.split(',') if self.keywords else []
        }

with app.app_context():
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
        colore=data.get('colore', ''),
        materiale=data.get('materiale', ''),
        keywords=data['keywords']
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
    articolo.colore = data.get('colore', '')
    articolo.materiale = data.get('materiale', '')
    articolo.keywords = data['keywords']
    
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

def estrai_colore_materiale(keywords):
    colori = [
        'nero', 'bianco', 'rosso', 'blu', 'verde', 'giallo', 'marrone', 'beige', 'rosa', 'viola', 'arancione', 'grigio', 'oro', 'argento', 'celeste', 'azzurro'
    ]
    materiali = [
        'pelle', 'tessuto', 'cotone', 'seta', 'nylon', 'lino', 'jeans', 'velluto', 'camoscio', 'canvas', 'paglia', 'lana', 'eco-pelle', 'vernice', 'gomma'
    ]
    colore = next((k for k in keywords if k in colori), None)
    materiale = next((k for k in keywords if k in materiali), None)
    return colore, materiale

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

def crea_descrizione_semantica(tipo_articolo, keywords_classificate, brand):
    """Crea una descrizione semantica basata sul tipo di articolo e keywords"""
    
    # Template semantici per ogni tipo di articolo
    templates = {
        'borsa': {
            'base': "Una borsa che",
            'con_materiale': "realizzata in {materiale}",
            'con_colore': "nella raffinata tonalità {colore}",
            'con_stile': "dallo stile {stile}",
            'con_caratteristiche': "caratterizzata da {caratteristica}",
            'con_dettagli': "impreziosita da {dettaglio}",
            'conclusioni': [
                "perfetta per ogni occasione",
                "ideale per chi ama l'eleganza discreta",
                "un must-have per il guardaroba moderno",
                "che unisce funzionalità e stile"
            ]
        },
        'scarpe': {
            'base': "Un paio di scarpe",
            'con_materiale': "realizzate in {materiale}",
            'con_colore': "nel colore {colore}",
            'con_stile': "dal design {stile}",
            'con_caratteristiche': "pensate per garantire {caratteristica}",
            'con_dettagli': "arricchite da {dettaglio}",
            'conclusioni': [
                "per camminare con sicurezza e stile",
                "che completano perfettamente ogni look",
                "ideali per chi non rinuncia al comfort",
                "per essere sempre al passo con le tendenze"
            ]
        },
        'vestito': {
            'base': "Un vestito",
            'con_materiale': "in {materiale}",
            'con_colore': "nel colore {colore}",
            'con_stile': "dallo stile {stile}",
            'con_caratteristiche': "pensato per valorizzare {caratteristica}",
            'con_dettagli': "impreziosito da {dettaglio}",
            'conclusioni': [
                "che esalta la femminilità",
                "perfetto per ogni occasione speciale",
                "per sentirsi sempre eleganti",
                "che fa la differenza nel guardaroba"
            ]
        },
        'generico': {
            'base': "Un articolo",
            'con_materiale': "realizzato in {materiale}",
            'con_colore': "nel colore {colore}",
            'con_stile': "dallo stile {stile}",
            'con_caratteristiche': "che offre {caratteristica}",
            'con_dettagli': "caratterizzato da {dettaglio}",
            'conclusioni': [
                "che rappresenta l'eccellenza del design",
                "perfetto per chi ama distinguersi",
                "ideale per completare il proprio stile",
                "che unisce qualità e raffinatezza"
            ]
        }
    }
    
    # Usa template generico se il tipo non è trovato
    template = templates.get(tipo_articolo, templates['generico'])
    
    # Costruisci la descrizione passo dopo passo
    parti_frase = [template['base']]
    
    # Aggiungi materiale se presente
    if keywords_classificate['materiali']:
        materiale = random.choice(keywords_classificate['materiali'])
        parti_frase.append(template['con_materiale'].format(materiale=materiale))
    
    # Aggiungi colore se presente
    if keywords_classificate['colori']:
        colore = random.choice(keywords_classificate['colori'])
        parti_frase.append(template['con_colore'].format(colore=colore))
    
    # Aggiungi stile se presente
    if keywords_classificate['stili']:
        stile = random.choice(keywords_classificate['stili'])
        parti_frase.append(template['con_stile'].format(stile=stile))
    
    # Aggiungi caratteristiche se presenti
    if keywords_classificate['caratteristiche']:
        caratteristica = random.choice(keywords_classificate['caratteristiche'])
        if caratteristica in ['comodo', 'pratico', 'versatile']:
            caratteristica = f"il massimo {caratteristica}"
        elif caratteristica in ['resistente', 'durevole']:
            caratteristica = f"una {caratteristica} eccezionale"
        parti_frase.append(template['con_caratteristiche'].format(caratteristica=caratteristica))
    
    # Aggiungi dettagli se presenti
    if keywords_classificate['dettagli']:
        dettaglio = random.choice(keywords_classificate['dettagli'])
        parti_frase.append(template['con_dettagli'].format(dettaglio=dettaglio))
    
    # Aggiungi conclusione appropriata
    conclusione = random.choice(template['conclusioni'])
    
    # Unisci le parti in modo naturale
    if len(parti_frase) == 1:
        descrizione = f"{parti_frase[0]} {conclusione}"
    elif len(parti_frase) == 2:
        descrizione = f"{parti_frase[0]} {parti_frase[1]}, {conclusione}"
    else:
        # Unisci le parti centrali con virgole, l'ultima con "e"
        inizio = parti_frase[0]
        mezzo = ", ".join(parti_frase[1:-1])
        fine = parti_frase[-1]
        if mezzo:
            descrizione = f"{inizio} {mezzo} e {fine}, {conclusione}"
        else:
            descrizione = f"{inizio} {fine}, {conclusione}"
    
    return descrizione.capitalize()

def genera_frase_intelligente(brand, nome, keywords_classificate, frase_precedente=None):
    """Genera una frase intelligente con interpretazione semantica"""
    
    # Riconosci il tipo di articolo
    tipo_articolo = riconosci_tipo_articolo(nome)
    
    # Se non ci sono keywords, usa frasi specifiche per brand
    tutte_keywords = sum(keywords_classificate.values(), [])
    if not tutte_keywords:
        frasi_brand = [
            f"Un pezzo iconico firmato {brand} che rappresenta l'eccellenza del design italiano.",
            f"La qualità superiore di {brand} si esprime in questo articolo dal fascino intramontabile.",
            f"Un capolavoro di stile che porta la firma inconfondibile di {brand}.",
            f"L'eleganza di {brand} prende vita in questo pezzo dal carattere unico.",
            f"Un articolo che incarna perfettamente lo spirito innovativo di {brand}.",
        ]
        frase_descrittiva = random.choice(frasi_brand)
    else:
        # Crea descrizione semantica
        frase_descrittiva = crea_descrizione_semantica(tipo_articolo, keywords_classificate, brand)
    
    # Frase promozionale variabile
    frasi_promozionali = [
        "Approfitta ora della nostra offerta esclusiva: un'occasione irripetibile per aggiungere questo pezzo unico alla tua collezione!",
        "Ti invitiamo a cogliere questa opportunità speciale con uno sconto eccezionale, disponibile solo per un periodo limitato!",
        "Non perdere questa occasione unica: abbiamo preparato per te un'offerta speciale che non potrai rifiutare!",
        "Questa è l'occasione perfetta per rendere tuo questo articolo esclusivo, grazie alla nostra proposta vantaggiosa!"
    ]
    
    frase_promozionale = random.choice(frasi_promozionali)
    
    # Combina le frasi
    frase_completa = f"{frase_descrittiva} {frase_promozionale}"
    
    # Evita ripetizioni del brand
    frase_finale = evita_ripetizioni_brand(frase_completa, brand, nome)
    
    # Se è identica alla precedente, prova una variante
    if frase_finale == frase_precedente and len(frasi_promozionali) > 1:
        frase_promozionale_alt = random.choice([f for f in frasi_promozionali if f != frase_promozionale])
        frase_finale = f"{frase_descrittiva} {frase_promozionale_alt}"
        frase_finale = evita_ripetizioni_brand(frase_finale, brand, nome)
    
    return frase_finale

def evita_ripetizioni_brand(testo, brand, nome):
    """Evita ripetizioni del brand se già presente nel nome dell'articolo"""
    brand_lower = brand.lower()
    nome_lower = nome.lower()
    
    # Se il brand è già nel nome, rimuovi le ripetizioni extra
    if brand_lower in nome_lower:
        # Conta quante volte appare il brand nel testo
        occorrenze = testo.lower().count(brand_lower)
        if occorrenze > 1:
            # Sostituisci le occorrenze successive con "la maison" o "il brand"
            testo_parti = testo.split(brand)
            if len(testo_parti) > 2:
                testo = brand.join(testo_parti[:2]) + "la maison".join(testo_parti[2:])
    
    return testo.replace("  ", " ").strip()

@app.route('/api/genera-frase/<int:id>', methods=['GET'])
def genera_frase(id):
    articolo = Articolo.query.get_or_404(id)
    keywords = articolo.keywords.split(',') if articolo.keywords else []
    
    # Classifica le keywords
    keywords_classificate = classifica_keywords(keywords)
    
    # Genera la frase intelligente
    frase = genera_frase_intelligente(articolo.brand, articolo.nome, keywords_classificate)
    
    return jsonify({'frase': frase})

if __name__ == '__main__':
    app.run(debug=True) 
