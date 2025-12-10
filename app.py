import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from openai import OpenAI
import csv
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import save  # Modulo di salvataggio

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="FATTURAGE", page_icon="🦁💰", layout="wide")

# --- CSS PERSONALIZZATO ---
st.markdown("""
<style>
    /* Stile generale messaggi */
    div[data-testid="stChatMessage"] { background-color: #ffffff !important; border: 1px solid #f0f2f6; border-radius: 10px; padding: 15px; }
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] div {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 15px !important;
        color: #000000 !important;
        line-height: 1.6 !important;
    }
    
    /* Intestazioni Blocchi (HTML generato dall'AI) */
    .block-header {
        background-color: #f8f9fa;
        border-left: 5px solid #ff4b4b;
        padding: 15px;
        margin-top: 25px !important;
        margin-bottom: 15px !important;
        border-radius: 0 8px 8px 0;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .block-title {
        font-family: 'Arial Black', sans-serif !important;
        font-size: 18px !important;
        font-weight: 900 !important;
        text-transform: uppercase;
        color: #333 !important;
        display: block;
        margin-bottom: 4px;
    }
    .block-claim {
        font-family: 'Arial', sans-serif !important;
        font-size: 13px !important;
        font-style: italic !important;
        color: #666 !important;
        display: block;
    }

    /* Tabelle */
    div[data-testid="stChatMessage"] table {
        width: 100% !important;
        border-collapse: collapse !important;
        border: 1px solid #e0e0e0 !important;
        font-size: 14px !important;
    }
    div[data-testid="stChatMessage"] th {
        background-color: #f1f3f4 !important;
        color: #000 !important;
        font-weight: bold;
        text-align: left;
        padding: 12px !important;
        border-bottom: 2px solid #ddd !important;
    }
    div[data-testid="stChatMessage"] td {
        padding: 10px !important;
        border-bottom: 1px solid #eee !important;
    }
    
    /* Sidebar Button */
    .stButton button {
        background-color: #ff4b4b !important;
        color: white !important;
        font-weight: bold !important;
        border: none !important;
        width: 100%;
        height: 50px;
        font-size: 16px !important;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- IMPORTAZIONE MODULO ESTERNO ---
try:
    import locations_module
except ImportError:
    locations_module = None

# --- FUNZIONE CALLBACK PER ABILITARE LOCATION ---
def enable_locations_callback():
    st.session_state.enable_locations_state = True

# --- 2. GESTIONE DATABASE (GOOGLE SHEETS) ---
def get_gspread_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
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

@st.cache_data(ttl=600, show_spinner=False)
def carica_google_sheet(sheet_name):
    client = get_gspread_client()
    if not client: return None
    try:
        sheet = client.open(sheet_name).get_worksheet(0)
        data = sheet.get_all_records()
        return data
    except Exception as e:
        st.error(f"Errore caricamento Sheet '{sheet_name}': {e}")
        return None

def database_to_string(database_list):
    """Converte la lista di dizionari in stringa per il prompt con sanitizzazione link."""
    if not database_list: return "Nessun dato disponibile."
    try:
        if not isinstance(database_list[0], dict): return "" 
        sanitized_list = []
        for riga in database_list:
            clean_riga = {}
            for k, v in riga.items():
                val_str = str(v) if v is not None else ""
                if val_str.strip().lower().startswith("http") and " " in val_str:
                    val_str = val_str.replace(" ", "%20")
                clean_riga[k] = val_str
            sanitized_list.append(clean_riga)
        header = " | ".join(sanitized_list[0].keys())
        rows = []
        for riga in sanitized_list:
            clean_values = list(riga.values())
            rows.append(" | ".join(clean_values))
        return header + "\n" + "\n".join(rows)
    except Exception: return ""

# --- CARICAMENTO DATI BASE ---
master_database = carica_google_sheet('MasterTbGoogleAi') 
if master_database is None:
    st.error("⚠️ ERRORE CRITICO: Impossibile scaricare il database attività da Google Sheets.")
    st.stop()
csv_data_string = database_to_string(master_database)

# --- 4. CONFIGURAZIONE LOGIN SICURO ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None

if not st.session_state.authenticated:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("🔒 Area Riservata")
        pwd = st.text_input("Inserisci Password Staff", type="password")
        
        if st.button("Accedi"):
            users_db = st.secrets.get("passwords", {})
            if pwd in users_db:
                st.session_state.authenticated = True
                st.session_state.username = users_db[pwd]
                st.session_state.messages = [] 
                st.rerun()
            else:
                st.error("Password errata")
    st.stop()

# --- 4.b INIZIALIZZAZIONE SESSION STATE ---
if "enable_locations_state" not in st.session_state:
    st.session_state.enable_locations_state = False 
if "total_tokens_used" not in st.session_state:
    st.session_state.total_tokens_used = 0

if "messages" not in st.session_state or not st.session_state.messages:
    st.session_state.messages = []
    
    if st.session_state.username == "Francesca":
        welcome_msg = "Ciao squirtina..." 
    else:
        welcome_msg = f"Ciao **{st.session_state.username}**! Usa la barra laterale a sinistra per compilare i dati."
        
    st.session_state.messages.append({"role": "model", "content": welcome_msg})

# --- SIDEBAR ---
with st.sidebar:
    st.title("🦁 FATTURAGE 2.0")
    st.caption(f"Utente: **{st.session_state.username}**") 
    st.markdown("---")
    
    st.subheader("📝 Dati Brief")
    cliente_input = st.text_input("Nome Cliente *", placeholder="es. Azienda Rossi SpA")
    col_pax, col_data = st.columns(2)
    with col_pax: pax_input = st.text_input("N. Pax", placeholder="50")
    with col_data: data_evento_input = st.text_input("Data", placeholder="12 Maggio")
    citta_input = st.text_input("Città / Location", placeholder="Milano / Villa Reale")
    durata_input = st.text_input("Durata Attività", placeholder="es. 2-3 ore")
    obiettivo_input = st.text_area("Obiettivo / Mood / Note", placeholder="Descrivi l'obiettivo...", height=100)

    st.markdown("###")
    generate_btn = st.button("🚀 GENERA PREVENTIVO", type="primary")
    st.markdown("---")

    with st.expander("⚙️ Impostazioni Avanzate", expanded=False):
        use_location_db = st.checkbox("🏰 Abilita Database Location", key="enable_locations_state")
        st.markdown("---")
        provider = st.selectbox("Provider AI", ["Google Gemini", "Groq"])
        if provider == "Google Gemini":
            model_options = ["gemini-3-pro-preview", "gemini-2.0-flash-exp", "gemini-1.5-pro-latest", "gemini-1.5-flash"]
            if "gemini-3-pro-preview" not in model_options: model_options.insert(0, "gemini-3-pro-preview")
        elif provider == "Groq":
            model_options = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"]
        selected_model_name = st.selectbox("Modello", model_options)
        
        api_key = st.secrets.get("GOOGLE_API_KEY") if provider == "Google Gemini" else st.secrets.get("GROQ_API_KEY")
        if not api_key: st.error(f"⚠️ Manca API Key per {provider}")

location_instructions_block = ""
if use_location_db:
    with st.spinner("Caricamento Location..."):
        location_database = carica_google_sheet('LocationGoogleAi')
        if location_database and locations_module:
            loc_db_string = database_to_string(location_database)
            location_instructions_block = locations_module.get_location_instructions(loc_db_string)
        elif not location_database:
            st.sidebar.warning("⚠️ Errore caricamento Location")

# --- 5. SYSTEM PROMPT ---
context_brief = f"DATI BRIEF: Cliente: {cliente_input}, Pax: {pax_input}, Data: {data_evento_input}, Città: {citta_input}, Durata: {durata_input}, Obiettivo: {obiettivo_input}."

BASE_INSTRUCTIONS = f"""
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT. Rispondi in Italiano.
{context_brief}

### 🛡️ PROTOCOLLO
1.  **USO DEL DATABASE:** Usa SOLO i dati caricati (NON inventare).
2.  **QUALIFICAZIONE:** Se il brief è insufficiente, chiedi info.

### 🎨 REGOLE VISUALI (TASSATIVE)
1.  **ICONE:** Inserisci un'emoji SOLO nel titolo del format (es. "### 🍳 Cooking").
2.  **HTML:** Usa ESCLUSIVAMENTE il codice HTML fornito per i titoli delle sezioni (Blocchi).
3.  **DIVIETO:** NON scrivere mai "BLOCCO 1", "BLOCCO 2", ecc. come testo semplice. Usa solo l'HTML.

### 🔢 CALCOLO PREVENTIVI (ALGORITMO OBBLIGATORIO)
Usa rigorosamente questi passaggi. NON inventare prezzi.

**1. IDENTIFICA I MOLTIPLICATORI:**
* **M_PAX (Numero Partecipanti):**
    * < 5 pax: x3.20
    * 5-10 pax: x1.60
    * 11-20 pax: x1.05
    * 21-30 pax: x0.95
    * 31-60 pax: x0.90
    * 61-90 pax: x0.90
    * 91-150 pax: x0.85
    * 151-250 pax: x0.70
    * > 250 pax: x0.60
* **M_STAGIONE:**
    * Maggio, Giugno, Luglio, Settembre, Ottobre, Dicembre: x1.10
    * Gennaio, Febbraio, Marzo, Aprile, Agosto, Novembre: x1.02
* **M_LOCATION:**
    * Milano (città): x1.00
    * Roma (città): x0.95
    * Centro Italia: x1.05
    * Nord/Sud Italia (Fuori MI/RM): x1.15
    * Isole: x1.30
* **M_DURATA:**
    * Fino a 2h: x1.00
    * Mezza giornata (2-4h): x1.10
    * Giornata intera (>4h): x1.20

**2. APPLICA LA FORMULA BASE:**
`PREZZO_GREZZO = (Prezzo_Listino_CSV * M_PAX * M_STAGIONE * M_LOCATION * M_DURATA) * Numero_Pax`

**3. REGOLA MINIMUM SPENDING:**
Se `PREZZO_GREZZO` è inferiore a € 1.800,00 -> Il prezzo diventa **€ 1.800,00**.

**4. REGOLA ARROTONDAMENTO (CRITICO):**
Devi arrotondare il totale usando questa logica matematica:
`PREZZO_FINALE = ARROTONDA((PREZZO_GREZZO + 60) / 100) * 100`
*(In pratica: se le ultime due cifre sono 00-39 arrotonda per difetto al 100, se sono 40-99 arrotonda per eccesso al 100).*

---
### 🚦 FLUSSO DI LAVORO (ORDINE OBBLIGATORIO)

**FASE 0: CHECK INFORMAZIONI**

**FASE 1: LA REGOLA DEL 12 (Presentazione Format)**
Proponi 12 FORMAT divisi in 4 categorie.
⚠️ **PRIORITÀ:** Se l'utente chiede un format specifico, INCLUDILO SEMPRE.

**PER OGNI CATEGORIA, USA QUESTO HTML ESATTO PER IL TITOLO:**
<div class="block-header"><span class="block-title">TITOLO CATEGORIA</span><span class="block-claim">CLAIM</span></div>

Le categorie sono:
1.  **I BEST SELLER** (4 format - Ranking Alto). Claim: "I più amati dai nostri clienti".
2.  **LE NOVITÀ** (4 format - Novità/Anno recente). Claim: "Freschi di lancio".
3.  **VIBE & RELAX** (2 format - Relax/Atmosphere). Claim: "Atmosfera e condivisione".
4.  **SOCIAL** (2 format - Social/Charity). Claim: "Impatto positivo".

**Struttura Singolo Format:**
### [Emoji] [Nome Format]
[Descrizione breve basata sul DB]

**FASE 2: SUGGERIMENTO LOCATION**
{location_instructions_block}

**FASE 3: TABELLA RIEPILOGATIVA (TASSATIVA)**
Usa questo HTML per il titolo:
<div class="block-header"><span class="block-title">TABELLA RIEPILOGATIVA</span><span class="block-claim">Brief: {pax_input} pax | {data_evento_input} | {citta_input}</span></div>

**LINK SCHEDA TECNICA (REGOLA SUPREMA):**
* Copia URL esatto dal DB. NON modificarlo.
* Testo Link: NomeFormat.pdf (Tutto attaccato).
* Formato: `[NomeSenzaSpazi.pdf](URL_ESATTO)`.

| Nome Format | Costo Totale (+IVA) | Scheda Tecnica |
| :--- | :--- | :--- |
| 👨‍🍳 Cooking | € 2.400,00 | [Cooking.pdf](URL_ESATTO) |

**FASE 4: INFO UTILI (OBBLIGATORIO)**
Riporta questo blocco ESATTAMENTE così com'è:

### Informazioni Utili

✔️ **Tutti i format sono nostri** e possiamo personalizzarli senza alcun problema.

✔️ **La location non è inclusa** ma possiamo aiutarti a trovare quella perfetta per il tuo evento.

✔️ **Le attività di base** sono pensate per farvi stare insieme e divertirvi, ma il team building è anche formazione, aspetto che possiamo includere e approfondire.

✔️ **Prezzo all inclusive:** spese staff, trasferta e tutti i materiali sono inclusi, nessun costo a consuntivo.

✔️ **Assicurazione pioggia:** Se avete scelto un format oudoor ma le previsioni meteo sono avverse, due giorni prima dell'evento sceglieremo insieme un format indoor allo stesso costo.

✔️ **Chiedici anche** servizio video/foto e gadget.
"""

if not location_instructions_block:
    location_guardrail_silent = "ISTRUZIONE PER FASE 2: NON SCRIVERE NULLA. SALTA QUESTA FASE."
    FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS.replace('{location_instructions_block}', location_guardrail_silent)}\n\n### 💾 [DATABASE FORMATI]\n\n{csv_data_string}"
else:
    FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS.replace('{location_instructions_block}', location_instructions_block)}\n\n### 💾 [DATABASE FORMATI]\n\n{csv_data_string}"

# --- 6. GESTIONE INPUT ---
prompt_to_process = None
if generate_btn:
    if not cliente_input:
        st.sidebar.error("Inserisci il Nome Cliente!")
    else:
        prompt_to_process = f"Ciao, sono {cliente_input}. Vorrei un preventivo per {pax_input} persone, data {data_evento_input}, a {citta_input}. Durata: {durata_input}. Obiettivo: {obiettivo_input}."
        
        welcome_user = f"Ciao **{st.session_state.username}**!"
        if st.session_state.username == "Francesca":
             welcome_user = "Ciao squirtina..."
             
        st.session_state.messages = [{"role": "model", "content": f"{welcome_user} Elaboro la proposta per **{cliente_input}**."}]

chat_input = st.chat_input("Chiedi una modifica...")
if chat_input: prompt_to_process = chat_input

# --- 7. RENDERING CHAT ---
st.title("🦁 💰 FATTURAGE 💰 🦁")
for message in st.session_state.messages:
    role_to_show = "assistant" if message["role"] == "model" else message["role"]
    with st.chat_message(role_to_show): st.markdown(message["content"], unsafe_allow_html=True)

# --- 8. ELABORAZIONE AI ---
if prompt_to_process:
    st.session_state.messages.append({"role": "user", "content": prompt_to_process})
    with st.chat_message("user"): st.markdown(prompt_to_process)

    # Controllo Location
    keywords_location = ["location", "dove", "villa", "castello", "spazio", "hotel", "tenuta", "cascina", "posto"]
    is_location_request = any(k in prompt_to_process.lower() for k in keywords_location)
    
    should_generate = True
    if is_location_request and not st.session_state.enable_locations_state:
        should_generate = False
        with st.chat_message("assistant"):
            st.warning("⚠️ **Il Database Location è spento.**")
            st.button("🟢 ATTIVA DATABASE LOCATION", on_click=enable_locations_callback)

    if should_generate:
        with st.chat_message("assistant"):
            with st.spinner(f"Elaborazione con {provider}..."):
                try:
                    if not api_key: st.error("Chiave API mancante."); st.stop()
                    
                    response_text = ""
                    token_usage_info = ""

                    if provider == "Google Gemini":
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel(model_name=selected_model_name, generation_config={"temperature": 0.0}, system_instruction=FULL_SYSTEM_PROMPT, safety_settings={HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE})
                        
                        history_gemini = []
                        for m in st.session_state.messages:
                            if m["role"] != "model": history_gemini.append({"role": "user", "parts": [m["content"]]})
                            else: history_gemini.append({"role": "model", "parts": [m["content"]]})
                        
                        chat = model.start_chat(history=history_gemini[:-1])
                        response = chat.send_message(prompt_to_process)
                        response_text = response.text
                        
                        if response.usage_metadata:
                            tot = response.usage_metadata.total_token_count
                            token_usage_info = f"📊 Token: {tot}"

                    elif provider == "Groq":
                        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                        messages_groq = [{"role": "system", "content": FULL_SYSTEM_PROMPT}]
                        for m in st.session_state.messages[-6:]:
                            role = "assistant" if m["role"] == "model" else "user"
                            messages_groq.append({"role": role, "content": m["content"]})
                        
                        resp = client.chat.completions.create(model=selected_model_name, messages=messages_groq, temperature=0.0)
                        response_text = resp.choices[0].message.content
                        if resp.usage: token_usage_info = f"📊 Token: {resp.usage.total_tokens}"

                    st.markdown(response_text, unsafe_allow_html=True) 
                    if token_usage_info: st.caption(token_usage_info)
                    st.session_state.messages.append({"role": "model", "content": response_text})
                    
                except Exception as e:
                    st.error(f"Errore: {e}")

# --- PULSANTE SALVATAGGIO ---
if st.session_state.messages and st.session_state.messages[-1]["role"] == "model":
    last_response = st.session_state.messages[-1]["content"]
    st.divider()
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("💾 SALVA SU GOOGLE SHEET", use_container_width=True):
            if save.salva_preventivo(cliente_input, st.session_state.username, pax_input, data_evento_input, citta_input, last_response):
                st.success(f"✅ Preventivo per {cliente_input} salvato!")
            else:
                st.error("Errore salvataggio.")
    with c2:
        with st.expander("📋 CLICCA QUI PER COPIARE IL TESTO"):
            st.code(last_response, language="markdown")
