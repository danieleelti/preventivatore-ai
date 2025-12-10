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
    if not database_list: return "Nessun dato disponibile."
    try:
        if not isinstance(database_list[0], dict): return "" 
        header = " | ".join(database_list[0].keys())
        rows = []
        for riga in database_list:
            clean_values = [str(v) if v is not None else "" for v in riga.values()]
            rows.append(" | ".join(clean_values))
        return header + "\n" + "\n".join(rows)
    except Exception: return ""

# --- CARICAMENTO DATI BASE (SOLO FORMAT) ---
master_database = carica_google_sheet('MasterTbGoogleAi') 

if master_database is None:
    st.error("⚠️ ERRORE CRITICO: Impossibile scaricare il database attività da Google Sheets.")
    st.stop()

csv_data_string = database_to_string(master_database)

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

# Variabile per le istruzioni location (vuota di default)
location_instructions_block = ""

with st.expander("⚙️ Impostazioni Provider & Modello AI", expanded=False):
    col_prov, col_mod = st.columns(2)
    with col_prov:
        provider = st.selectbox("Scegli Provider", ["Google Gemini", "Groq"])

    if provider == "Google Gemini":
        model_options = ["gemini-3-pro-preview", "gemini-2.0-flash-exp", "gemini-1.5-pro-latest", "gemini-1.5-flash"]
        if "gemini-3-pro-preview" not in model_options: model_options.insert(0, "gemini-3-pro-preview")
    elif provider == "Groq":
        model_options = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    
    with col_mod:
        selected_model_name = st.selectbox("Versione Modello", model_options)
    
    # --- CHECKBOX PER CARICAMENTO LOCATION ---
    st.markdown("---")
    use_location_db = st.checkbox("🏰 **Abilita Database Location** (Attiva solo se richiesto, rallenta l'avvio)", value=False)
    
    # LOGICA DI CARICAMENTO CONDIZIONALE
    if use_location_db:
        with st.spinner("Scaricamento Database Location in corso..."):
            location_database = carica_google_sheet('LocationGoogleAi')
            if location_database and locations_module:
                loc_db_string = database_to_string(location_database)
                location_instructions_block = locations_module.get_location_instructions(loc_db_string)
            elif not location_database:
                st.warning("⚠️ Impossibile caricare le Location.")
    
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
    st.warning("⚠️ Groq ha un limite di token basso. Se fallisce, usa Gemini.")

st.caption(f"Assistente Virtuale Senior - {provider}")

# --- 5. SYSTEM PROMPT ---
BASE_INSTRUCTIONS = """
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT. Rispondi in Italiano.

### 🛡️ PROTOCOLLO
1.  **USO DEL DATABASE:** Sei obbligato a usare i dati caricati da Google Sheets.
2.  **QUALIFICAZIONE:** Se mancano info (Pax, Data, Obiettivo), chiedile.

### 🎨 REGOLE VISUALI
1.  **ICONE:** Una emoji SOLO nel titolo del format.
2.  **HTML:** Usa i div HTML forniti per i titoli delle sezioni.

### 🔢 CALCOLO PREVENTIVI (RIGOROSO)
* Usa le colonne del DB per P_BASE.
* Applica i moltiplicatori (M_PAX, M_DURATA, M_LINGUA, M_LOCATION, M_STAGIONE).
* Formula Standard: `P_BASE * M_PAX * ... * PAX`
* Arrotonda e applica Min Spending 1800+IVA.

---
### 🚦 FLUSSO DI LAVORO (ORDINE OBBLIGATORIO)

**FASE 0: CHECK INFORMAZIONI**

**FASE 1: LA REGOLA DEL 12 (Presentazione Format)**
Proponi ESATTAMENTE 12 FORMAT divisi in 4 blocchi, seguendo questa struttura numerica RIGIDA:

⚠️ **TITOLI BLOCCHI HTML:**
<div class="block-header"><span class="block-title">NOME BLOCCO</span><span class="block-claim">Claim</span></div>

**BLOCCO 1: I BEST SELLER** (Devi proporre 4 format)
* **CRITERIO:** Valore più alto in **"Ranking"** o **"Voto"**.

**BLOCCO 2: LE NOVITÀ** (Devi proporre 4 format)
* **CRITERIO:** "Sì"/"True" in **"Novità"** o **"Anno"** recente.

**BLOCCO 3: VIBE & RELAX** (Devi proporre 2 format)
* **CRITERIO:** Tag "Relax", "Soft", "Atmosphere", "Cena" in **"Categoria"**/**"Tag"**.

**BLOCCO 4: SOCIAL** (Devi proporre 2 format)
* **CRITERIO:** Tag "Social", "Charity", "Creativo" in **"Categoria"**/**"Tag"**.

**Struttura Format:**
### [Emoji] [Nome]
[Descrizione basata sul DB]

**FASE 2: SUGGERIMENTO LOCATION (CONDIZIONALE)**
⚠️ **ATTENZIONE:** Se l'utente NON ha chiesto esplicitamente una location o "dove farlo", **SALTA COMPLETAMENTE QUESTA FASE**. Non scrivere nulla, nemmeno il titolo o avvisi.

*SE E SOLO SE* l'utente ha chiesto location:
Segui le istruzioni sottostanti:
{location_instructions_block}

**FASE 3: TABELLA RIEPILOGATIVA (⛔️ TASSATIVA ⛔️)**
DEVI OBBLIGATORIAMENTE GENERARE QUESTA TABELLA ALLA FINE DELLA RISPOSTA.
NON TERMINARE MAI LA RISPOSTA SENZA QUESTA TABELLA.

**⚠️ REGOLA LINK SCHEDA TECNICA (CRITICO - DO OR DIE):**
1. Cerca nel DB la colonna "Scheda Tecnica", "Link", "URL" o "Pdf".
2. **SANITIZZAZIONE URL:** Se l'URL contiene degli SPAZI, SOSTITUISCILI CON `%20`.
   - Esempio: `.../Green Energy.pdf` --> DEVE DIVENTARE `.../Green%20Energy.pdf`
3. Il testo del link deve essere sempre "NomeFormat.pdf".
4. FORMATO OBBLIGATORIO: `[NomeFormat.pdf](URL_SANITIZZATO_SENZA_SPAZI)`.

| Nome Format | Costo Totale (+IVA) | Scheda Tecnica |
| :--- | :--- | :--- |
| 👨‍🍳 Cooking | € 2.400,00 | [Cooking.pdf](URL_CON_PERCENTO_20) |
| ... | ... | ... |

*(Inserisci qui tutti i 12 format proposti con i relativi prezzi calcolati)*.

**FASE 4: INFO UTILI**
Copia il blocco standard (Format nostri, Location esclusa, Prezzo all inclusive, Assicurazione pioggia).
"""

# NOTA: location_instructions_block è già stato inserito sopra tramite f-string o accodamento
# Ma per sicurezza lo reiniettiamo nel prompt finale in modo pulito.
if not location_instructions_block:
    # Se il DB è spento, inserisco un blocco "silente" che si attiva SOLO se richiesto
    location_guardrail = """
    SE (E SOLO SE) L'UTENTE HA CHIESTO UNA LOCATION:
    Rispondi: "⚠️ Database Location spento. Per ricevere suggerimenti mirati sulle nostre location partner, attiva la spunta **'Abilita Database Location'** nel menu delle impostazioni in alto ⚙️ e riprova."
    ALTRIMENTI:
    Non scrivere nulla su location o database spento.
    """
    FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS}\n\n{location_guardrail}\n\n### 💾 [DATABASE FORMATI DA GOOGLE SHEETS]\n\n{csv_data_string}"
else:
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
                token_usage_info = ""

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
                    
                    # TOKEN COUNTER
                    if response.usage_metadata:
                        in_tok = response.usage_metadata.prompt_token_count
                        out_tok = response.usage_metadata.candidates_token_count
                        tot_tok = response.usage_metadata.total_token_count
                        token_usage_info = f"📊 **Token:** Input {in_tok} + Output {out_tok} = **{tot_tok} Totali**"

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
                    
                    # TOKEN COUNTER
                    if resp.usage:
                        in_tok = resp.usage.prompt_tokens
                        out_tok = resp.usage.completion_tokens
                        tot_tok = resp.usage.total_tokens
                        token_usage_info = f"📊 **Token:** Input {in_tok} + Output {out_tok} = **{tot_tok} Totali**"

                st.markdown(response_text, unsafe_allow_html=True) 
                
                # Visualizza info token singola richiesta
                if token_usage_info:
                    st.caption(token_usage_info)

                st.session_state.messages.append({"role": "model", "content": response_text})
                
            except Exception as e:
                err_msg = str(e)
                if "rate_limit_exceeded" in err_msg.lower() or "413" in err_msg:
                    st.error(f"❌ **ERRORE LIMITE GROQ**: Il database è troppo grande per il piano gratuito. **Usa Google Gemini.**")
                else:
                    st.error(f"Errore tecnico con {provider}: {e}")
