import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
from datetime import datetime
import pytz

# Configurazione Foglio di salvataggio
SHEET_NAME_OUTPUT = "PreventiviInviatiAi"

def get_db_connection():
    """Recupera la connessione a Google Sheets usando i secrets di Streamlit."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            return client
        else:
            st.error("❌ Credenziali mancanti nei secrets.")
            return None
    except Exception as e:
        st.error(f"❌ Errore connessione DB: {e}")
        return None

def salva_preventivo(cliente, utente, pax, data_evento, citta, contenuto):
    """Salva una riga nel foglio PreventiviInviatiAi."""
    client = get_db_connection()
    if not client:
        return False

    try:
        sheet = client.open(SHEET_NAME_OUTPUT).get_worksheet(0)
        
        # Gestione Data e Ora Italia
        tz_ita = pytz.timezone('Europe/Rome')
        now = datetime.now(tz_ita)
        data_oggi = now.strftime("%Y-%m-%d")
        ora_oggi = now.strftime("%H:%M:%S")

        # Preparazione Riga
        # Colonne: Nome Cliente | Utente | Data Prev | Ora Prev | Pax | Data Evento | Città | Contenuto
        row = [
            cliente,
            utente,      # <--- NUOVA COLONNA
            data_oggi,
            ora_oggi,
            pax,
            data_evento,
            citta,
            contenuto
        ]

        sheet.append_row(row)
        return True

    except Exception as e:
        st.error(f"❌ Errore durante il salvataggio su Sheet: {e}")
        return False
