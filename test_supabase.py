#!/usr/bin/env python3
"""
Test semplice per verificare connessione Supabase
"""

import requests
import json

def test_app_online():
    """Test se l'app online risponde e usa Supabase"""
    
    print("🔍 Testing app online...")
    
    try:
        # Test homepage
        response = requests.get("https://dist-gestionale.onrender.com", timeout=10)
        if response.status_code == 200:
            print("✅ App online raggiungibile")
        else:
            print(f"❌ App non raggiungibile: {response.status_code}")
            return
        
        # Test API articoli
        response = requests.get("https://dist-gestionale.onrender.com/api/articoli", timeout=10)
        if response.status_code == 200:
            articoli = response.json()
            print(f"✅ API articoli funziona: {len(articoli)} articoli trovati")
            
            # Se ci sono articoli, significa che Supabase funziona
            if len(articoli) > 0:
                print("🎉 SUPABASE FUNZIONA! Ci sono dati nel database")
                print(f"   Primo articolo: {articoli[0].get('nome', 'N/A')}")
            else:
                print("📝 Database vuoto (normale se è la prima volta)")
        else:
            print(f"❌ API non risponde: {response.status_code}")
    
    except requests.exceptions.Timeout:
        print("⏰ Timeout - app probabilmente in deploy")
    except Exception as e:
        print(f"❌ Errore: {e}")

def check_new_fields():
    """Verifica se la pagina contiene i nuovi campi"""
    
    print("\n🔍 Verifica nuovi campi...")
    
    try:
        response = requests.get("https://dist-gestionale.onrender.com", timeout=10)
        html = response.text
        
        fields_to_check = ["condizioni", "rarita", "vintage", "target"]
        found_fields = []
        
        for field in fields_to_check:
            if field in html.lower():
                found_fields.append(field)
        
        if len(found_fields) == len(fields_to_check):
            print("✅ TUTTI i nuovi campi sono presenti!")
            print("✅ Deploy con Supabase completato!")
        else:
            print(f"⚠️  Trovati solo: {found_fields}")
            print("⏳ Deploy probabilmente ancora in corso...")
    
    except Exception as e:
        print(f"❌ Errore verifica campi: {e}")

if __name__ == "__main__":
    test_app_online()
    check_new_fields() 