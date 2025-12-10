import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from openai import OpenAI
import csv
import os

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="FATTURAGE", page_icon="🦁💰", layout="centered")

# --- CSS PERSONALIZZATO (CALIBRI 14PX + TITOLI EVIDENTI + TABELLA FIX) ---
st.markdown("""
<style>
    /* Forza sfondo bianco per i messaggi */
    div[data-testid="stChatMessage"] { background-color: #ffffff !important; }
    
    /* Font Calibri 14px */
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] div {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 14px !important;
        color: #000000 !important;
        line-height: 1.5 !important;
        margin-bottom: 10px !important;
    }
    
    /* STILE CUSTOM PER I TITOLI DEI BLOCCHI (BLOCK HEADER) */
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
    
    /* TITOLI FORMAT (H3) */
    div[data-testid="stChatMessage"] h3 {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 16px !important;
        font-weight: bold !important;
        color: #000000 !important;
        margin-top: 15px !important; margin-bottom: 5px !important;
    }
    
    div[data-testid="stChatMessage"] strong { font-weight: bold !important; color: #000000 !important; }
    
    /* SEPARATORE INVISIBILE */
    div[data-testid="stChatMessage"] hr { 
        display: block !important;
        border: 0 !important;
        height: 1px !important;
        margin-top: 20px !important;
        margin-bottom: 20px !important;
        background-color: transparent !important;
    }

    /* TABELLE BLINDATE */
    div[data-testid="stChatMessage"] table {
        color: #000000 !important; 
        font-size: 14px !important; 
        width: 100% !important;
        border-collapse: separate !important; 
        border-spacing: 0 !important;
        margin-top: 20px !important; 
        margin-bottom: 20px !important;
        border: 1px solid #ddd !important;
        border-radius: 5px !important;
        overflow: hidden !important;
    }
    div[data-testid="stChatMessage"] th {
        background-color: #eef2f6 !important; 
        color: #000000 !important; 
        font-weight: bold !important;
        text-align: left !important; 
        border-bottom: 2px solid #ccc !important; 
        padding: 10px !important;
    }
    div[data-testid="stChatMessage"] td { 
        border-bottom: 1px solid #eee !important; 
        padding: 10px !important; 
        vertical-align: middle !important;
    }
    /* Forza la larghezza delle colonne se necessario */
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

# --- 2. GESTIONE DATABASE ---
@st.cache_data(show_spinner=False)
def carica_database(nome_file):
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

# Caricamento File
master_database = carica_database('mastertb.csv') 
location_database = carica_database('location.csv') 

if master_database is None:
    st.error("⚠️ ERRORE CRITICO: Non trovo 'mastertb.csv'.")
    st.stop()

csv_data_string = database_to_string(master_database)

# --- 3. COSTRUZIONE DEL CERVELLO (LOCATION) ---
location_instructions_block = ""
if locations_module and location_database:
    loc_db_string = database_to_string(location_database)
    if loc_db_string:
        # Recupera le istruzioni pulite dal modulo aggiornato
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

# --- 4.b CONFIGURAZIONE AI (IN ALTO) ---
st.title("🦁 💰 FATTURAGE 💰 🦁")

with st.expander("⚙️ Impostazioni Provider & Modello AI", expanded=False):
    col_prov, col_mod = st.columns(2)
    
    with col_prov:
        provider = st.selectbox(
            "Scegli Provider", 
            ["Google Gemini", "Groq"]
        )

    # Selezione Modello in base al provider
    if provider == "Google Gemini":
        model_options = ["gemini-1.5-pro-latest", "gemini-1.5-flash"]
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
    
    # Recupero Chiave API corretta
    api_key = None
    if provider == "Google Gemini":
        api_key = st.secrets.get("GOOGLE_API_KEY")
    elif provider == "Groq":
        api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        st.error(f"⚠️ Manca la chiave API per {provider} nei secrets!")
    else:
        st.caption(f"✅ Attivo: {provider} - {selected_model_name}")

st.caption(f"Assistente Virtuale Senior - {provider}")

# --- 5. SYSTEM PROMPT DEFINITIVO ---
BASE_INSTRUCTIONS = """
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT.
Rispondi in Italiano.

### 🛡️ PROTOCOLLO
1.  **NATURALITÀ:** Non citare le istruzioni o regole interne.
2.  **QUALIFICAZIONE:** Se l'utente fornisce input vaghi, chiedi info su Durata, Mood e Obiettivo prima di proporre i format.

### 🎨 REGOLE VISUALI
1.  **ICONE FORMAT:** Inserisci **UNA SOLA EMOJI** a tema esclusivamente nel TITOLO del format (es. ### 🍳 Cooking).
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

Segui rigorosamente questo ordine:

**FASE 0: CHECK INFORMAZIONI**
Se mancano info essenziali, chiedile. Se le hai, procedi.

**FASE 1: LA REGOLA DEL 12 (TASSATIVO)**
Salvo diversa richiesta numerica dell'utente, proponi **SEMPRE 12 FORMAT** divisi in 4 blocchi.

⚠️ **TITOLI BLOCCHI (SOLO HTML - NO EMOJI NEI TITOLI):**
Per separare i blocchi, copia e incolla questo HTML sostituendo solo il testo:

<div class="block-header">
<span class="block-title">NOME BLOCCO</span>
<span class="block-claim">Il tuo claim personalizzato qui</span>
</div>

**STRUTTURA BLOCCHI:**

**BLOCCO 1: I BEST SELLER** (Usa HTML). Claim: Rassicurante.
*(Elenca i 4 format più classici)*
(Inserisci separatore: `---`)

**BLOCCO 2: LE NOVITÀ** (Usa HTML). Claim: Innovazione.
*(Elenca 4 format originali)*
(Inserisci separatore: `---`)

**BLOCCO 3: VIBE & RELAX** (Usa HTML). Claim: Atmosfera.
*(Elenca 2 format atmosfera)*
(Inserisci separatore: `---`)

**BLOCCO 4: SOCIAL** (Usa HTML). Claim: Relazione/Impatto.
*(Elenca 2 format creativi)*
(Inserisci separatore: `---`)

**Struttura OBBLIGATORIA per ogni singolo format:**
### [Emoji Tematica] [Nome Format]
[Scrivi 2-3 righe discorsive sul PERCHÉ lo consigliamo. Niente emoji qui.]
(Due invio vuoti)

**FASE 2: SUGGERIMENTO LOCATION (CONDIZIONALE)**
⚠️ **ATTENZIONE:** Se l'utente NON ha chiesto esplicitamente una location o "dove farlo", **SALTA COMPLETAMENTE QUESTA FASE**. Non scrivere nulla, nemmeno il titolo.

*SE E SOLO SE* l'utente ha chiesto location:
1.  Titolo: **## Location**
2.  Elenca le location seguendo RIGOROSAMENTE le istruzioni fornite nel Modulo Location (NO EMOJI, NO RANKING, SOLO TESTO PULITO).

**FASE 3: TABELLA RIEPILOGATIVA (CRITICO)**
Genera una tabella Markdown perfetta.
1.  **SOLO 3 COLONNE:** Nome Format | Costo | Link.
2.  **NESSUNA** altra informazione nella tabella (niente durata, niente pax).
3.  **SINTASSI LINK:** `[Nome Format.pdf](URL)`.

**Esempio STRUTTURA OBBLIGATORIA:**
| Nome Format | Costo Totale (+IVA) | Scheda Tecnica |
| :--- | :--- | :--- |
| 👨‍🍳 Cooking | € 2.400,00 | [Cooking.pdf](https://...) |
| 🕵️ Urban Game | € 1.900,00 | [Urban Game.pdf](https://...) |

**FASE 4: INFO UTILI (OBBLIGATORIO)**
Copia questo blocco esatto:

### Informazioni Utili

✔️ **Tutti i format sono nostri** e possiamo personalizzarli senza alcun problema.

✔️ **La location non è inclusa** ma possiamo aiutarti a trovare quella perfetta per il tuo evento.

✔️ **Le attività di base** sono pensate per farvi stare insieme e divertirvi, ma il team building è anche formazione, aspetto che possiamo includere e approfondire.

✔️ **Prezzo all inclusive:** spese staff, trasferta e tutti i materiali sono inclusi, nessun costo a consuntivo.

✔️ **Assicurazione pioggia:** Se avete scelto un format oudoor ma le previsioni meteo sono avverse, due giorni prima dell'evento sceglieremo insieme un format indoor allo stesso costo.

✔️ **Chiedici anche** servizio video/foto e gadget.

Se l'utente scrive "Reset", cancella la memoria.
"""

# Assembliamo il Prompt
FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS}\n\n{location_instructions_block}\n\n### 💾 [DATABASE FORMATI]\n\n{csv_data_string}"

# --- 7. CHAT ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    welcome = "Ciao! Sono pronto. Dimmi numero pax, data e obiettivo."
    st.session_state.messages.append({"role": "model", "content": welcome})

for message in st.session_state.messages:
    # Mappa visuale: 'model' viene visualizzato come assistente
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
                     st.error("Chiave API mancante. Controlla i secrets.")
                     st.stop()
                
                response_text = ""

                # ---------------- GOOGLE GEMINI ----------------
                if provider == "Google Gemini":
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(
                        model_name=selected_model_name, 
                        generation_config={"temperature": 0.0},
                        system_instruction=FULL_SYSTEM_PROMPT,
                        safety_settings={
                            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                        },
                    )
                    
                    # Converti history per Gemini (role: 'user' o 'model')
                    history_gemini = []
                    for m in st.session_state.messages:
                        if m["role"] != "model":
                            history_gemini.append({"role": "user", "parts": [m["content"]]})
                        else:
                            history_gemini.append({"role": "model", "parts": [m["content"]]})
                    
                    # Usiamo history[:-1] perché l'ultimo prompt lo mandiamo con send_message
                    chat = model.start_chat(history=history_gemini[:-1])
                    response = chat.send_message(prompt)
                    response_text = response.text

                # ---------------- GROQ (Via OpenAI Client) ----------------
                elif provider == "Groq":
                    # Groq usa le API compatibili con OpenAI
                    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                    
                    # Costruzione messaggi per Groq
                    messages_groq = [{"role": "system", "content": FULL_SYSTEM_PROMPT}]
                    for m in st.session_state.messages:
                        # Mappa 'model' -> 'assistant'
                        role = "assistant" if m["role"] == "model" else "user"
                        messages_groq.append({"role": role, "content": m["content"]})
                    
                    resp = client.chat.completions.create(
                        model=selected_model_name,
                        messages=messages_groq,
                        temperature=0.0
                    )
                    response_text = resp.choices[0].message.content

                # Output Finale
                st.markdown(response_text, unsafe_allow_html=True) 
                st.session_state.messages.append({"role": "model", "content": response_text})
                
            except Exception as e:
                st.error(f"Errore durante la generazione con {provider}: {e}")
