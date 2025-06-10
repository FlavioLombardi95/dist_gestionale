#!/usr/bin/env python3
"""
Script per migrare dati da SQLite a PostgreSQL
Usa questo script se hai già dati in SQLite che vuoi trasferire
"""

import sqlite3
import psycopg2
import os
from urllib.parse import urlparse

def migrate_data():
    # Connessione SQLite
    sqlite_conn = sqlite3.connect('gestionale.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    # Connessione PostgreSQL (da variabile ambiente)
    postgres_url = os.environ.get('DATABASE_URL')
    if not postgres_url:
        print("❌ DATABASE_URL non trovato nelle variabili ambiente")
        return
    
    # Parse URL PostgreSQL
    if postgres_url.startswith('postgres://'):
        postgres_url = postgres_url.replace('postgres://', 'postgresql://', 1)
    
    url = urlparse(postgres_url)
    pg_conn = psycopg2.connect(
        host=url.hostname,
        port=url.port,
        database=url.path[1:],
        user=url.username,
        password=url.password
    )
    pg_cursor = pg_conn.cursor()
    
    try:
        # Leggi dati da SQLite
        sqlite_cursor.execute("SELECT * FROM articolo ORDER BY id")
        articoli = sqlite_cursor.fetchall()
        
        print(f"🔄 Trovati {len(articoli)} articoli da migrare...")
        
        # Inserisci in PostgreSQL
        for articolo in articoli:
            pg_cursor.execute("""
                INSERT INTO articolo (
                    nome, brand, immagine, colore, materiale, keywords, 
                    termini_commerciali, condizioni, rarita, vintage, target, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, articolo[1:])  # Salta l'ID per permettere auto-increment
        
        pg_conn.commit()
        print(f"✅ Migrazione completata! {len(articoli)} articoli trasferiti.")
        
    except Exception as e:
        print(f"❌ Errore durante la migrazione: {e}")
        pg_conn.rollback()
    
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    migrate_data() 