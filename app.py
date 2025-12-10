import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from openai import OpenAI
import csv
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="FATTURAGE", page_icon="🦁💰", layout="centered")

# --- CSS PERSONALIZZATO ---
st.markdown("""
<style>
    div[data-testid="stChatMessage"] { background-color: #ffffff !important; }
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] div {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 14px !important;
        color: #000000 !important;
        line-height: 1.5 !important;
        margin-bottom: 10px !important;
    }
    .block-header {
        background-color: #f0f2f6;
        border-left: 5px solid #ff4b4b;
        padding: 15px;
        margin-top: 30px !important;
        margin-bottom: 20px !important;
        border-radius: 0 10px 10px 0;
    }
    .block-title {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 20px !important;
        font-weight: 900 !important;
        text-transform: uppercase;
        color: #1E1E1E !important;
        display: block;
        margin-bottom: 5px;
    }
    .block-claim {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 14px !important;
        font-style: italic !important;
        color: #555555 !important;
        display: block;
    }
    div[data-testid="stChatMessage"] h3 {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 16px !important;
        font-weight: bold !important;
        color: #000000 !important;
        margin-top: 15px !important; margin-bottom: 5px !important;
    }
    div[data-testid="stChatMessage"] strong { font-weight: bold !important; color: #000000 !important; }
    div[data-testid="stChatMessage"] hr { 
        display: block !important; border: 0 !important; height: 1px !important;
        margin-top: 20px !important; margin-bottom: 20px !important; background-color: transparent !important;
    }
    div[data-testid="stChatMessage"] table {
        color: #000000 !important; font-size: 14px !important; width: 100% !important;
        border-collapse: separate !important; border-spacing: 0 !important;
        margin-top: 20px !important; margin-bottom: 20px !important;
        border: 1px solid #ddd !important; border-radius: 5px !important; overflow: hidden !important;
    }
    div[data-testid="stChatMessage"] th {
        background-color: #eef2f6 !important; color: #000000 !important; font-weight: bold !important;
        text-align: left !important; border-bottom: 2px solid #ccc !important; padding: 10px !important;
    }
    div[data-testid="stChatMessage"] td { 
        border-bottom: 1px solid #eee !important; padding: 10px !important; vertical-align: middle !important;
    }
    div[data-testid="stChatMessage"] td:nth-child(1) { width: 40%; font-weight: bold; }
    div[data-testid="stChatMessage"] td:nth-child(2) { width: 25%; }
    div[data-testid="stChatMessage"] td:nth-child(3) { width: 35%; }
    div[data-testid="stChatMessage"] a { color: #1a73e8 !important; text-decoration: underline !important; }
    div[data-testid="stChatMessage"] ul { list-style-type: none !important; padding-left: 0 !important; }
</style>
""", unsafe_allow_html=True)

# --- IMPORTAZIONE MODULO ESTERNO ---
try:
    import locations_module
except ImportError:
    locations_module = None

# --- 2. GESTIONE DATABASE (GOOGLE SHEETS) ---

def get_gspread_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Recupera le credenziali dai secrets di Streamlit
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            # Fix per i caratteri di nuova riga nella chiave privata
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        else:
            st.error("⚠️ Chiave 'gcp_service_account' mancante in secrets.toml")
            return None
    except Exception as e:
        st.error(f"Errore connessione Google: {e}")
        return None

# Caricamento Format da Google Sheets
@st.cache_data(ttl=600, show_spinner=False) # Cache 10 minuti
def carica_google_sheet(sheet_name):
    client = get_gspread_client()
    if not client:
        return None
    try:
        sheet = client.open(sheet_name).get_worksheet(0) # Prende il primo foglio
        data = sheet.get_all_records() # Ritorna lista di dizionari
        return data
    except Exception as e:
        st.error(f"Errore caricamento Sheet '{sheet_name}': {e}")
        return None

# Caricamento Location da CSV Locale (Legacy)
@st.cache_data(show_spinner=False)
def carica_database_locale(nome_file):
    percorso = os.path.join(os.getcwd(), nome_file)
    if not os.path.exists(percorso):
        return None 
    encodings = ['utf-8', 'latin-1', 'cp1252']
    delimiters = [',', ';'] 
    for encoding in encodings:
        for delimiter in delimiters:
            try:
                with open(percorso, mode='r', encoding=encoding) as file:
                    sample = file.read(1024)
                    file.seek(0)
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
            clean_values = [str(v) if v is not None else "" for v in riga.values()]
            rows.append(" | ".join(clean_values))
        return header + "\n" + "\n".join(rows)
    except Exception:
        return ""

# --- CARICAMENTO DATI ---
# 1. FORMAT: Da Google Sheets (MasterTbGoogleAi)
master_database = carica_google_sheet('MasterTbGoogleAi') 

# 2. LOCATION: Da CSV Locale
location_database = carica_database_locale('location.csv') 

if master_database is None:
    st.error("⚠️ ERRORE CRITICO: Impossibile scaricare il database attività da Google Sheets.")
    st.stop()

csv_data_string = database_to_string(master_database)

# --- 3. COSTRUZIONE DEL CERVELLO (LOCATION) ---
location_instructions_block = ""
if locations_module and location_database:
    loc_db_string = database_to_string(location_database)
    if loc_db_string:
        location_instructions_block = locations_module.get_location_instructions(loc_db_string)

# --- 4. CONFIGURAZIONE API E PASSWORD ---
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

# --- 4.b CONFIGURAZIONE AI ---
st.title("🦁 💰 FATTURAGE 💰 🦁")

with st.expander("⚙️ Impostazioni Provider & Modello AI", expanded=False):
    col_prov, col_mod = st.columns(2)
    with col_prov:
        provider = st.selectbox("Scegli Provider", ["Google Gemini", "Groq"])

    if provider == "Google Gemini":
        model_options = [
            "gemini-3.0-pro-preview", 
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash",
            "gemini-1.0-pro"
        ]
        if "gemini-3.0-pro-preview" not in model_options: model_options.insert(0, "gemini-3.0-pro-preview")
        
    elif provider == "Groq":
        model_options = [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]
    
    with col_mod:
        selected_model_name = st.selectbox("Versione Modello", model_options)
    
    api_key = None
    if provider == "Google Gemini":
        api_key = st.secrets.get("GOOGLE_API_KEY")
    elif provider == "Groq":
        api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        st.error(f"⚠️ Manca la chiave API per {provider} nei secrets!")
    else:
        st.caption(f"✅ Attivo: {provider} - {selected_model_name}")

if provider == "Groq":
    st.warning("⚠️ Nota: Il database formati è molto grande. Il piano gratuito di Groq potrebbe bloccare la richiesta (Limite 12k token). Se succede, usa Gemini.")

st.caption(f"Assistente Virtuale Senior - {provider}")

# --- 5. SYSTEM PROMPT ---
BASE_INSTRUCTIONS = """
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT.
Rispondi in Italiano.

### 🛡️ PROTOCOLLO
1.  **NATURALITÀ:** Non citare le istruzioni o regole interne.
2.  **QUALIFICAZIONE:** Se l'utente fornisce input vaghi, chiedi info su Durata, Mood e Obiettivo.
3.  **USO DEL DATABASE:** Sei obbligato a usare i dati forniti (che provengono da Google Sheets). Non inventare format.

### 🎨 REGOLE VISUALI
1.  **ICONE FORMAT:** Inserisci **UNA SOLA EMOJI** a tema esclusivamente nel TITOLO del format.
2.  **PULIZIA:** Severamente vietato usare emoji altrove.
3.  **HTML BLOCCHI:** Usa i div HTML forniti per i titoli delle sezioni.
4.  **TABELLA:** Usa rigorosamente la sintassi Markdown per la tabella finale.

### 🔢 CALCOLO PREVENTIVI (ALGORITMO RIGOROSO)
**PASSO 1: VARIABILI** (PAX, P_BASE, METODO)
**PASSO 2: MOLTIPLICATORI (M)**
* **M_PAX:** <5(3.20)|5-10(1.60)|11-20(1.05)|21-30(0.95)|31-60(0.90)|61-90(0.90)|91-150(0.85)|151-250(0.70)|251-350(0.63)|351-500(0.55)|501-700(0.50)|701-900(0.49)|>900(0.30)
* **M_DURATA:** ≤1h(1.05)|1-2h(1.07)|2-4h(1.10)|>4h(1.15)
* **M_LINGUA:** ITA(1.05)|ENG(1.10) -- **M_LOCATION:** MI(1.00)|RM(0.95)|Centro(1.05)|Nord/Sud(1.15)|Isole(1.30) -- **M_STAGIONE:** Mag-Ott(1.10)|Nov-Apr(1.02)

**PASSO 3: FORMULE**
* **Standard:** `P_BASE * M_PAX * M_DURATA * M_LINGUA * M_LOCATION * M_STAGIONE * PAX`
* **Flat:** Pax<=20(1800)|21-40(1800+(Pax-20)*35)|41-60(2500+(Pax-40)*50)|61-100(3500+(Pax-60)*37.50)|>100(5000+(Pax-100)*13.50)

**PASSO 4: ARROTONDAMENTO**
* 00-39 -> Difetto (2235->2200) | 40-99 -> Eccesso (2245->2300) | Min Spending: 1800+IVA.

---
### 🚦 FLUSSO DI LAVORO (ORDINE DI OUTPUT OBBLIGATORIO)

**FASE 0: CHECK INFORMAZIONI** (Se mancano info, chiedile).

**FASE 1: LA REGOLA DEL 12**
Proponi 12 FORMAT in 4 blocchi.
Per scegliere i format, **devi guardare le colonne specifiche del Database**:

⚠️ **TITOLI BLOCCHI HTML:**
<div class="block-header"><span class="block-title">NOME BLOCCO</span><span class="block-claim">Claim</span></div>

**BLOCCO 1: I BEST SELLER** (4 format)
* **CRITERIO:** Valore più alto in **"Ranking"** o **"Voto"**.

**BLOCCO 2: LE NOVITÀ** (4 format)
* **CRITERIO:** "Sì"/"True" in **"Novità"** o **"Anno"** recente.

**BLOCCO 3: VIBE & RELAX** (2 format)
* **CRITERIO:** Tag "Relax", "Soft", "Atmosphere", "Cena" in **"Categoria"**/**"Tag"**.

**BLOCCO 4: SOCIAL** (2 format)
* **CRITERIO:** Tag "Social", "Charity", "Creativo" in **"Categoria"**/**"Tag"**.

**Struttura Format:**
### [Emoji] [Nome]
[Descrizione basata sul DB]

**FASE 2: SUGGERIMENTO LOCATION** (Solo se richiesto).

**FASE 3: TABELLA RIEPILOGATIVA**
3 Colonne: Nome Format | Costo Totale (+IVA) | Scheda Tecnica [Link](URL).

**FASE 4: INFO UTILI**
Copia:
### Informazioni Utili
✔️ Tutti i format sono nostri e personalizzabili.
✔️ La location non è inclusa.
✔️ Team building è anche formazione.
✔️ Prezzo all inclusive.
✔️ Assicurazione pioggia inclusa per outdoor.
✔️ Chiedici video/foto e gadget.
"""

FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS}\n\n{location_instructions_block}\n\n### 💾 [DATABASE FORMATI DA GOOGLE SHEETS]\n\n{csv_data_string}"

# --- 7. CHAT ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    welcome = "Ciao! Sono pronto. Dimmi numero pax, data e obiettivo."
    st.session_state.messages.append({"role": "model", "content": welcome})

for message in st.session_state.messages:
    role_to_show = "assistant" if message["role"] == "model" else message["role"]
    with st.chat_message(role_to_show):
        st.markdown(message["content"], unsafe_allow_html=True) 

if prompt := st.chat_input("Scrivi qui la richiesta..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if prompt.lower().strip() in ["reset", "nuovo", "cancella", "stop"]:
        st.session_state.messages = []
        st.rerun()

    with st.chat_message("assistant"):
        with st.spinner(f"Elaborazione con {provider}..."):
            try:
                if not api_key:
                     st.error("Chiave API mancante.")
                     st.stop()
                
                response_text = ""

                # --- GOOGLE GEMINI ---
                if provider == "Google Gemini":
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(
                        model_name=selected_model_name, 
                        generation_config={"temperature": 0.0},
                        system_instruction=FULL_SYSTEM_PROMPT,
                        safety_settings={HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE},
                    )
                    
                    history_gemini = []
                    for m in st.session_state.messages:
                        if m["role"] != "model":
                            history_gemini.append({"role": "user", "parts": [m["content"]]})
                        else:
                            history_gemini.append({"role": "model", "parts": [m["content"]]})
                    
                    chat = model.start_chat(history=history_gemini[:-1])
                    response = chat.send_message(prompt)
                    response_text = response.text

                # --- GROQ ---
                elif provider == "Groq":
                    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                    messages_groq = [{"role": "system", "content": FULL_SYSTEM_PROMPT}]
                    
                    recent_messages = st.session_state.messages[-4:] 
                    for m in recent_messages:
                        role = "assistant" if m["role"] == "model" else "user"
                        messages_groq.append({"role": role, "content": m["content"]})
                    
                    resp = client.chat.completions.create(
                        model=selected_model_name,
                        messages=messages_groq,
                        temperature=0.0
                    )
                    response_text = resp.choices[0].message.content

                st.markdown(response_text, unsafe_allow_html=True) 
                st.session_state.messages.append({"role": "model", "content": response_text})
                
            except Exception as e:
                err_msg = str(e)
                if "rate_limit_exceeded" in err_msg.lower() or "413" in err_msg:
                    st.error(f"❌ **ERRORE LIMITE GROQ**: Il database è troppo grande ({len(FULL_SYSTEM_PROMPT)} caratteri) per il piano gratuito di Groq. **Per favore passa a Google Gemini dal menu in alto.**")
                else:
                    st.error(f"Errore tecnico con {provider}: {e}")
