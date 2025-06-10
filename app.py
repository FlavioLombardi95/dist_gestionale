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
    """Classifica le keywords in categorie"""
    keywords_lower = [kw.strip().lower() for kw in keywords if kw.strip()]
    
    colori = ['nero', 'bianco', 'rosso', 'blu', 'verde', 'giallo', 'marrone', 'beige', 'rosa', 'viola', 'arancione', 'grigio', 'oro', 'argento', 'celeste', 'azzurro', 'bordeaux', 'navy', 'cammello', 'ecru']
    
    materiali = ['pelle', 'tessuto', 'cotone', 'seta', 'nylon', 'lino', 'jeans', 'velluto', 'camoscio', 'canvas', 'paglia', 'lana', 'eco-pelle', 'vernice', 'gomma', 'lycra', 'poliestere', 'cashmere', 'raso', 'tela']
    
    stili = ['elegante', 'casual', 'sportivo', 'chic', 'vintage', 'moderno', 'classico', 'trendy', 'glamour', 'minimale', 'bohemian', 'rock', 'sofisticato', 'raffinato', 'contemporaneo']
    
    caratteristiche = ['comodo', 'versatile', 'pratico', 'resistente', 'leggero', 'impermeabile', 'traspirante', 'morbido', 'durevole', 'flessibile', 'elastico', 'aderente', 'ampio', 'fitted']
    
    risultato = {
        'colori': [kw for kw in keywords_lower if kw in colori],
        'materiali': [kw for kw in keywords_lower if kw in materiali],
        'stili': [kw for kw in keywords_lower if kw in stili],
        'caratteristiche': [kw for kw in keywords_lower if kw in caratteristiche],
        'altre': [kw for kw in keywords_lower if kw not in colori + materiali + stili + caratteristiche]
    }
    
    return risultato

def evita_ripetizioni_brand(testo, brand, nome):
    """Evita ripetizioni del brand se già presente nel nome dell'articolo"""
    brand_lower = brand.lower()
    nome_lower = nome.lower()
    
    # Se il brand è già nel nome, usa solo il nome nell'articolo
    if brand_lower in nome_lower:
        return testo.replace(brand, "").replace("  ", " ").strip()
    
    return testo

def genera_frase_intelligente(brand, nome, keywords_classificate, frase_precedente=None):
    """Genera una frase intelligente evitando ripetizioni"""
    
    # Schemi di frase avanzati
    schemi_descrittivi = [
        "Un capolavoro di stile dove {elemento1} incontra {elemento2} per un risultato {aggettivo}.",
        "L'eleganza prende forma attraverso {elemento1} e {elemento2}, creando un'esperienza {aggettivo}.",
        "Quando {elemento1} si fonde con {elemento2}, nasce qualcosa di veramente {aggettivo}.",
        "Scopri l'armonia perfetta tra {elemento1} e {elemento2} in questo pezzo {aggettivo}.",
        "Un design che celebra {elemento1} e {elemento2} per uno stile {aggettivo}.",
        "La bellezza si esprime attraverso {elemento1} unito a {elemento2}, per un look {aggettivo}.",
        "Stile e sostanza si incontrano: {elemento1} e {elemento2} per un risultato {aggettivo}."
    ]
    
    schemi_senza_keywords = [
        f"Un pezzo iconico che rappresenta l'eccellenza di {brand}.",
        f"L'arte del design secondo {brand}: qualità e stile inconfondibili.",
        f"Un capolavoro di fattura che incarna lo spirito di {brand}.",
        f"Eleganza pura firmata {brand}: quando il lusso incontra la perfezione.",
        f"Un articolo che racconta la storia e la passione di {brand}.",
        f"Il meglio della tradizione {brand} in un pezzo unico.",
        f"Qualità superiore e design ricercato: l'essenza di {brand}."
    ]
    
    frase_promozionale = "Ti invitiamo a cogliere questa occasione esclusiva con un'offerta speciale a tempo limitato!"
    
    # Se non ci sono keywords, usa schemi senza keywords
    tutte_keywords = sum(keywords_classificate.values(), [])
    if not tutte_keywords:
        schema = random.choice(schemi_senza_keywords)
        frase_completa = f"{schema} {frase_promozionale}"
        return evita_ripetizioni_brand(frase_completa, brand, nome)
    
    # Seleziona elementi per la frase evitando ripetizioni
    elementi_disponibili = []
    aggettivi = ['unico', 'straordinario', 'raffinato', 'esclusivo', 'elegante', 'sofisticato', 'inconfondibile', 'memorabile', 'distintivo', 'prezioso']
    
    # Raccogli elementi da diverse categorie
    if keywords_classificate['colori']:
        elementi_disponibili.extend([f"il colore {col}" for col in keywords_classificate['colori']])
    if keywords_classificate['materiali']:
        elementi_disponibili.extend([f"il {mat}" for mat in keywords_classificate['materiali']])
    if keywords_classificate['stili']:
        elementi_disponibili.extend([f"lo stile {stile}" for stile in keywords_classificate['stili']])
    if keywords_classificate['caratteristiche']:
        elementi_disponibili.extend([f"la caratteristica {car}" for car in keywords_classificate['caratteristiche']])
    if keywords_classificate['altre']:
        elementi_disponibili.extend(keywords_classificate['altre'])
    
    # Seleziona elementi per la frase
    if len(elementi_disponibili) >= 2:
        elementi_selezionati = random.sample(elementi_disponibili, 2)
    elif len(elementi_disponibili) == 1:
        elementi_selezionati = [elementi_disponibili[0], f"la qualità {brand}"]
    else:
        elementi_selezionati = [f"l'eleganza {brand}", "la qualità superiore"]
    
    # Genera la frase
    schema = random.choice(schemi_descrittivi)
    aggettivo = random.choice(aggettivi)
    
    frase_descrittiva = schema.format(
        elemento1=elementi_selezionati[0],
        elemento2=elementi_selezionati[1],
        aggettivo=aggettivo
    )
    
    # Combina le frasi
    frase_completa = f"{frase_descrittiva} {frase_promozionale}"
    
    # Evita ripetizioni del brand
    frase_finale = evita_ripetizioni_brand(frase_completa, brand, nome)
    
    # Se la frase è identica alla precedente, prova un altro schema
    if frase_finale == frase_precedente and len(schemi_descrittivi) > 1:
        schema_alternativo = random.choice([s for s in schemi_descrittivi if s != schema])
        frase_descrittiva = schema_alternativo.format(
            elemento1=elementi_selezionati[1],  # Inverti l'ordine
            elemento2=elementi_selezionati[0],
            aggettivo=random.choice([a for a in aggettivi if a != aggettivo])
        )
        frase_finale = f"{frase_descrittiva} {frase_promozionale}"
        frase_finale = evita_ripetizioni_brand(frase_finale, brand, nome)
    
    return frase_finale

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
