import csv
import os

def carica_dati(nome_file):
    """
    Legge un file CSV e lo trasforma in una lista di dizionari.
    Gestisce automaticamente le intestazioni delle colonne.
    """
    percorso_file = os.path.join(os.path.dirname(__file__), nome_file)
    
    lista_dati = []
    
    try:
        # Apre il file in lettura, usando utf-8 per accenti e simboli corretti
        with open(percorso_file, mode='r', encoding='utf-8') as file:
            # DictReader usa la prima riga del CSV come chiavi (intestazioni)
            reader = csv.DictReader(file, delimiter=',') # NOTA: Se il tuo CSV usa virgole, cambia delimiter=','
            
            for riga in reader:
                lista_dati.append(riga)
                
        print(f"✅ Caricato {nome_file}: {len(lista_dati)} righe.")
        return lista_dati

    except FileNotFoundError:
        print(f"❌ Errore: Il file {nome_file} non è stato trovato.")
        return []
    except Exception as e:
        print(f"❌ Errore generico su {nome_file}: {e}")
        return []

# --- CARICAMENTO DEI DATABASE ---
# Qui eseguiamo il caricamento vero e proprio
print("--- Inizio caricamento Database ---")

master_database = carica_dati('mastertb.csv')
faq_database = carica_dati('faq.csv')
location_database = carica_dati('location.csv')

print("--- Caricamento completato ---\n")
