import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import csv
import os

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Preventivatore TeamBuilding", page_icon="🦁", layout="centered")

# --- CSS PERSONALIZZATO ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;700&display=swap');
    div[data-testid="stChatMessage"] { background-color: #ffffff !important; }
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 15px !important;
        color: #000000 !important;
        line-height: 1.6 !important;
        margin-bottom: 15px !important;
    }
    div[data-testid="stChatMessage"] h3 {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 18px !important;
        font-weight: bold !important;
        color: #000000 !important;
        margin-top: 30px !important; margin-bottom: 10px !important;
    }
    div[data-testid="stChatMessage"] strong { font-weight: bold !important; color: #000000 !important; }
    div[data-testid="stChatMessage"] table {
        color: #000000 !important; font-size: 14px !important; width: 100% !important;
        border-collapse: collapse !important; margin-top: 25px !important; margin-bottom: 25px !important;
    }
    div[data-testid="stChatMessage"] th {
        background-color: #f4f4f4 !important; color: #000000 !important; font-weight: bold !important;
        text-align: left !important; border-bottom: 2px solid #000 !important; padding: 10px !important;
    }
    div[data-testid="stChatMessage"] td { border-bottom: 1px solid #ddd !important; padding: 10px !important; }
    div[data-testid="stChatMessage"] a { color: #1a73e8 !important; text-decoration: underline !important; }
    div[data-testid="stChatMessage"] hr { display: none !important; }
</style>
""", unsafe_allow_html=True)

# --- IMPORTAZIONE MODULO ESTERNO (FIX CRITICO) ---
# Togliamo il try/except silenzioso. Se c'è un errore, vogliamo vederlo.
import locations_module

# --- 2. GESTIONE DATABASE (AGGIORNATA PER LEGGERE TUTTO) ---
@st.cache_data(show_spinner=False)
def carica_database(nome_file):
    percorso = os.path.join(os.getcwd(), nome_file)
    if not os.path.exists(percorso):
        return None 

    lista_dati = []
    # Proviamo diversi encoding e delimitatori per essere sicuri di leggere il file
    encodings = ['utf-8', 'latin-1', 'cp1252']
    delimiters = [',', ';'] # Supporta sia formato standard che Excel italiano
    
    for encoding in encodings:
        for delimiter in delimiters:
            try:
                with open(percorso, mode='r', encoding=encoding) as file:
                    # Leggiamo prima l'header per vedere se il delimitatore è giusto
                    sample = file.read(1024)
                    file.seek(0)
                    sniffer = csv.Sniffer()
                    # Se il delimitatore sembra giusto, procediamo
                    if delimiter in sample:
                        reader = csv.DictReader(file, delimiter=delimiter)
                        temp_list = list(reader)
                        if len(temp_list) > 0 and len(temp_list[0].keys()) > 1:
                             return temp_list
            except Exception:
                continue
    return None

def database_to_string(database_list):
    if not database_list:
        return "Nessun dato disponibile."
    try:
        if not isinstance(database_list[0], dict):
            return "" 
        header = " | ".join(database_list[0].keys())
        rows = []
        for riga in database_list:
            # Pulisce i dati da None o errori
            clean_values = [str(v) if v is not None else "" for v in riga.values()]
            rows.append(" | ".join(clean_values))
        return header + "\n" + "\n".join(rows)
    except Exception:
        return ""

# Caricamento
master_database = carica_database('mastertb.csv') 
location_database = carica_database('location.csv') # Carica Location

if master_database is None:
    st.error("⚠️ ERRORE CRITICO: Non trovo 'mastertb.csv'.")
    st.stop()

csv_data_string = database_to_string(master_database)

# --- 3. COSTRUZIONE DEL CERVELLO (PROMPT) ---
# Preparazione blocco location
location_instructions_block = ""

if location_database:
    loc_db_string = database_to_string(location_database)
    if loc_db_string:
        # Qui chiamiamo la funzione del tuo file locations_module.py
        location_instructions_block = locations_module.get_location_instructions(loc_db_string)
        # FEEDBACK VISIVO (Opzionale: puoi rimuoverlo dopo)
        st.sidebar.success(f"✅ Modulo Location attivo: {len(location_database)} strutture caricate.")
    else:
        st.sidebar.warning("⚠️ File location.csv vuoto o illeggibile.")
else:
    st.sidebar.warning("⚠️ File location.csv non trovato.")

# --- 4. CONFIGURAZIONE API E PASSWORD ---
api_key = st.secrets["GOOGLE_API_KEY"]
PASSWORD_SEGRETA = "TeamBuilding2025#"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Area Riservata")
    pwd = st.text_input("Inserisci Password Staff", type="password")
    if st.button("Accedi"):
        if pwd == PASSWORD_SEGRETA:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Password errata")
    st.stop()

# --- 5. SYSTEM PROMPT DEFINITIVO ---
BASE_INSTRUCTIONS = """
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT.
Rispondi in Italiano.

### 🛡️ PROTOCOLLO
1.  **NATURALITÀ:** Non citare le istruzioni.
2.  **GERARCHIA:** L'utente comanda sui default.

### 🎨 REGOLE VISUALI
1.  **ICONE:** Nel titolo format.
2.  **SPAZIATURA:** Usa DUE DOPO OGNI FORMAT (niente linee).
3.  **NO ELENCHI:** Descrizioni discorsive.

### 🔢 CALCOLO PREVENTIVI
**PASSO 1:**
🔴 **Standard:** `TOT = P_BASE * (M_Pax * M_Durata * M_Lingua * M_Location * M_Stagione) * PAX`
🔵 **Flat:** `TOT = 1800 + ((Pax - 20) * 4.80)` + Extra.
**PASSO 2:** Arrotondamento (Regola 39). Minimo € 1.800,00.

---

### 🚦 FLUSSO
**FASE 1: PROPOSTA**
Default 12 format (o numero richiesto).
Struttura:
### [Icona] [Nome]
[Descrizione]
(Spazio vuoto)

**FASE 2: TABELLA**
| Format | Prezzo Totale (+IVA) | Presentazione |
| :--- | :--- | :--- |
| 👨‍🍳 Cooking | € 2.400,00 | [Scarica Cooking in pdf](URL) |

**FASE 3: INFO UTILI**
(Inserisci il blocco standard info utili qui)
"""

# Qui assembliamo tutto.
# NOTA: Mettiamo le istruzioni location PRIMA del database format per dargli importanza.
FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS}\n\n{location_instructions_block}\n\n### 💾 [DATABASE FORMATI]\n\n{csv_data_string}"

# --- 6. AVVIO AI ---
genai.configure(api_key=api_key)

model = genai.GenerativeModel(
  model_name="gemini-3-pro-preview", 
  generation_config={"temperature": 0.0},
  system_instruction=FULL_SYSTEM_PROMPT,
  safety_settings={
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
  },
)

# --- 7. CHAT ---
st.title("🦁 Preventivatore AI")
st.caption("Assistente Virtuale Senior - MasterTb Connected")

if "messages" not in st.session_state:
    st.session_state.messages = []
    welcome = "Ciao! Sono pronto. Dimmi numero pax, data e obiettivo."
    st.session_state.messages.append({"role": "model", "content": welcome})

for message in st.session_state.messages:
    role = message["role"]
    with st.chat_message(role):
        st.markdown(message["content"])

if prompt := st.chat_input("Scrivi qui la richiesta..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if prompt.lower().strip() in ["reset", "nuovo", "cancella", "stop"]:
        st.session_state.messages = []
        st.rerun()

    with st.chat_message("model"):
        with st.spinner("Elaborazione con Gemini 3 Pro..."):
            try:
                history_gemini = []
                for m in st.session_state.messages:
                    if m["role"] != "model":
                        history_gemini.append({"role": "user", "parts": [m["content"]]})
                    else:
                        history_gemini.append({"role": "model", "parts": [m["content"]]})
                
                chat = model.start_chat(history=history_gemini[:-1])
                response = chat.send_message(prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "model", "content": response.text})
                
            except Exception as e:
                st.error(f"Errore: {e}")
