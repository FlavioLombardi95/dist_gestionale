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

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'brand': self.brand,
            'immagine': self.immagine,
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

@app.route('/api/genera-frase/<int:id>', methods=['GET'])
def genera_frase(id):
    articolo = Articolo.query.get_or_404(id)
    keywords = articolo.keywords.split(',') if articolo.keywords else []
    brand = articolo.brand
    
    if not keywords:
        return jsonify({'frase': 'Nessuna parola chiave disponibile'})
    
    # Schemi fraseologici descrittivi/emozionali
    schemi = [
        f"{brand}: {{keyword1}} e {{keyword2}} si fondono in un articolo che trasmette {{keyword3}}.",
        f"Lasciati conquistare dall'eleganza di {brand}, dove {{keyword1}} e {{keyword2}} incontrano la {{keyword3}}.",
        f"Con {brand}, ogni dettaglio racconta una storia di {{keyword1}}, {{keyword2}} e {{keyword3}}.",
        f"Scopri la magia di {brand}: {{keyword1}}, {{keyword2}} e un tocco di {{keyword3}} per emozionare ogni giorno.",
        f"{brand} presenta un articolo che unisce {{keyword1}}, {{keyword2}} e {{keyword3}} in un'esperienza unica."
    ]
    
    schema = random.choice(schemi)
    selected_keywords = random.sample(keywords, min(3, len(keywords)))
    frase1 = schema.format(
        keyword1=selected_keywords[0].strip(),
        keyword2=selected_keywords[1].strip() if len(selected_keywords) > 1 else selected_keywords[0].strip(),
        keyword3=selected_keywords[2].strip() if len(selected_keywords) > 2 else selected_keywords[0].strip()
    )
    frase2 = "Ti abbiamo inviato un'offerta ad un prezzo ulteriormente scontato, cogli subito questa occasione irripetibile!"
    frase = frase1 + " " + frase2
    return jsonify({'frase': frase})

if __name__ == '__main__':
    app.run(debug=True) 