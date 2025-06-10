#!/usr/bin/env python3
"""
Script per configurazione iniziale Supabase
Crea tabelle con indici ottimizzati e policies di sicurezza
"""

import os
import psycopg2
from urllib.parse import urlparse

def setup_supabase():
    """Configura il database Supabase con ottimizzazioni"""
    
    # Connessione Supabase
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL non trovato. Configura prima la variabile ambiente.")
        return
    
    # Parse URL
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    # Aggiungi SSL se mancante
    if 'sslmode' not in database_url:
        database_url += '?sslmode=require'
    
    url = urlparse(database_url)
    
    try:
        # Connetti a Supabase
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port,
            database=url.path[1:],
            user=url.username,
            password=url.password,
            sslmode='require'
        )
        cursor = conn.cursor()
        
        print("🔗 Connesso a Supabase!")
        
        # Crea tabella articoli con indici ottimizzati
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articolo (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                brand VARCHAR(100) NOT NULL,
                immagine VARCHAR(200),
                colore VARCHAR(50),
                materiale VARCHAR(100),
                keywords TEXT,
                termini_commerciali TEXT,
                condizioni VARCHAR(50),
                rarita VARCHAR(50),
                vintage BOOLEAN DEFAULT FALSE,
                target VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Crea indici per performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articolo_brand ON articolo(brand);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articolo_condizioni ON articolo(condizioni);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articolo_rarita ON articolo(rarita);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articolo_vintage ON articolo(vintage);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articolo_created_at ON articolo(created_at);")
        
        # Abilita Row Level Security (RLS) per sicurezza
        cursor.execute("ALTER TABLE articolo ENABLE ROW LEVEL SECURITY;")
        
        # Policy per permettere tutte le operazioni (per ora)
        cursor.execute("""
            CREATE POLICY IF NOT EXISTS "Permetti tutto per ora" ON articolo
            FOR ALL USING (true);
        """)
        
        conn.commit()
        print("✅ Tabelle create con successo!")
        print("✅ Indici ottimizzati creati!")
        print("✅ Row Level Security abilitata!")
        
        # Verifica connessione
        cursor.execute("SELECT COUNT(*) FROM articolo;")
        count = cursor.fetchone()[0]
        print(f"📊 Articoli attualmente nel database: {count}")
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        conn.rollback()
    
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    setup_supabase() 