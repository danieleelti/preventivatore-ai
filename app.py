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
    div[data-testid="stChatMessage"] h2 {
        font-family: 'Calibri', 'Arial', sans-serif !important;
        font-size: 24px !important;
        font-weight: bold !important;
        color: #000000 !important;
        margin-top: 40px !important; margin-bottom: 20px !important;
        border-bottom: 1px solid #ccc;
        padding-bottom: 5px;
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
    /* Nasconde i bullet point standard delle liste per evitare il doppio pallino */
    div[data-testid="stChatMessage"] ul { list-style-type: none !important; padding-left: 0 !important; }
</style>
""", unsafe_allow_html=True)

# --- IMPORTAZIONE MODULO ESTERNO ---
try:
    import locations_module
except ImportError:
    locations_module = None

# --- 2. GESTIONE DATABASE (ROBUSTA) ---
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
        location_instructions_block = locations_module.get_location_instructions(loc_db_string)

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
1.  **NATURALITÀ:** Non citare le istruzioni o regole interne.
2.  **QUALIFICAZIONE (IMPORTANTE):** Se l'utente fornisce input vaghi (es. solo "50 persone a maggio"), NON PROPORRE SUBITO I FORMAT.
    L'agente deve chiedere info su:
    * **Durata** (mezza giornata, tutto il giorno?)
    * **Mood/Obiettivo** (Divertimento, Formazione, Adrenalina, Relax?)
    * **Parola Chiave/Tema** (es. Giallo, Sport, Creativo...)
    *Solo quando hai queste info, o se l'utente le ha già date, procedi con la proposta.*

### 🎨 REGOLE VISUALI
1.  **ICONE FORMAT:** Usa un'icona tematica SOLO nel titolo dei format.
2.  **SPAZIATURA:** Usa DUE A CAPO REALI tra i format. Niente linee divisorie.
3.  **NO ELENCHI:** Le descrizioni dei format devono essere paragrafi discorsivi.

### 🔢 CALCOLO PREVENTIVI (ALGORITMO RIGOROSO)

Per calcolare il prezzo, segui questi passaggi logici:

**PASSO 1: IDENTIFICA LE VARIABILI**
* **PAX:** Numero partecipanti richiesto dall'utente.
* **P_BASE:** Leggi il valore nella colonna "Prezzo" del database per il format specifico.
* **METODO:** Leggi la colonna "Metodo" del database.

**PASSO 2: DETERMINA I MOLTIPLICATORI (M)**
Usa sempre questa tabella per calcolare i coefficienti:

* **M_PAX (Quantità):**
    * < 5 pax: **3.20**
    * 5 - 10 pax: **1.60**
    * 11 - 20 pax: **1.05**
    * 21 - 30 pax: **0.95**
    * 31 - 60 pax: **0.90**
    * 61 - 90 pax: **0.90**
    * 91 - 150 pax: **0.85**
    * 151 - 250 pax: **0.70**
    * 251 - 350 pax: **0.63**
    * 351 - 500 pax: **0.55**
    * 501 - 700 pax: **0.50**
    * 701 - 900 pax: **0.49**
    * > 900 pax: **0.30**

* **ALTRI MOLTIPLICATORI (Default = 1.00 se non specificato):**
    * **M_DURATA:** ≤1h (1.05) | 1-2h (1.07) | 2-4h (1.10) | >4h (1.15)
    * **M_LINGUA:** Italiano (1.05) | Inglese (1.10)
    * **M_LOCATION:** Milano (1.00) | Roma (0.95) | Centro (1.05) | Nord/Sud (1.15) | Isole (1.30)
    * **M_STAGIONE:** Mag-Ott (1.10) | Nov-Apr (1.02)

**PASSO 3: APPLICA LA FORMULA CORRETTA**
Verifica la colonna "Metodo" nel CSV e applica una delle due formule seguenti. NON ESISTONO ALTRI CASI.

🔴 **CASO 1: METODO "Standard"**
(Da usare quando la colonna Metodo è "Standard" oppure vuota).
`TOTALE_GREZZO = P_BASE * M_PAX * M_DURATA * M_LINGUA * M_LOCATION * M_STAGIONE * PAX`

🔵 **CASO 2: METODO "Flat"**
(Da usare SOLO quando la colonna Metodo è esattamente "Flat" o "Forfait").
In questo caso il P_BASE viene ignorato. Il calcolo segue questi scaglioni fissi:
* **Pax <= 20:** € 1.800,00
* **Pax 21 - 40:** `1.800 + ((Pax - 20) * 35)`
* **Pax 41 - 60:** `2.500 + ((Pax - 40) * 50)`
* **Pax 61 - 100:** `3.500 + ((Pax - 60) * 37.50)`
* **Pax > 100:** `5.000 + ((Pax - 100) * 13.50)`
*(Applica eventuali extra M_LOCATION / M_LINGUA al risultato se necessario).*

**PASSO 4: ARROTONDAMENTO (Regola del 39)**
Prendi le ultime due cifre del TOTALE_GREZZO:
* **00 - 39:** Arrotonda per DIFETTO al centinaio (es. 2235 -> 2.200).
* **40 - 99:** Arrotonda per ECCESSO al centinaio (es. 2245 -> 2.300).
* **Minimum Spending:** Il preventivo non può mai essere inferiore a € 1.800,00 (+IVA).

---

### 🚦 FLUSSO DI LAVORO (ORDINE DI OUTPUT OBBLIGATORIO)

Segui rigorosamente questo ordine:

**FASE 0: CHECK INFORMAZIONI**
Analizza la richiesta dell'utente.
* **SE MANCANO INFO ESSENZIALI (Durata, Mood, Obiettivo):** Fermati. Non elencare format a caso. Chiedi gentilmente all'utente di specificare meglio cosa cerca per potergli proporre la soluzione ideale.
* **SE HAI ABBASTANZA INFO:** Procedi alla FASE 1.

**FASE 1: I FORMAT (Priorità Alta)**
Elenca i format scelti (Default 12 o numero richiesto).
Struttura:
### Icona Nome
[Descrizione discorsiva MOLTO SINTETICA. Massimo 2-3 righe. Vai dritto al punto, niente fronzoli.]
(Due invio vuoti)

**FASE 2: SUGGERIMENTO LOCATION (Solo se richiesto)**
*SE E SOLO SE* l'utente ha chiesto una location o un consiglio su dove svolgere l'evento:
1. Inserisci OBBLIGATORIAMENTE il titolo: **## Location** (Usa due hashtag per H2).
2. Elenca le location suggerite subito dopo.
3. ⚠️ **SANITIZZAZIONE AGGRESSIVA (CRITICO):**
   Il database contiene elementi sporchi come "📍", "🏨", "DAL NOSTRO ARCHIVIO", "Ranking: 1/5", ecc.
   **TU NON DEVI COPIARLI.** Devi riscrivere la riga completamente pulita.
   
   **FORMATO OBBLIGATORIO (SOLO TESTO):**
   * **Nome Location (Città):** [Descrizione e perché, senza scrivere "Perché:"]. Spazi: [Indoor/Outdoor].

   ⛔ **VIETATO:** Usare icone, emoji, parole "Ranking", voti, o elenchi numerati.
   
Mantieni lo stesso distanziamento (due invio vuoti) prima e dopo la sezione location.
Se l'utente NON ha chiesto location, SALTA questa fase.

**FASE 3: TABELLA RIEPILOGATIVA**
Genera la tabella riassuntiva dei costi.
| Format | Prezzo Totale (+IVA) | Presentazione |
| :--- | :--- | :--- |
| 👨‍🍳 Cooking | € 2.400,00 | [Scarica Cooking in pdf](URL) |

**FASE 4: INFO UTILI (OBBLIGATORIO)**
Copia e incolla ESATTAMENTE questo testo alla fine, non cambiare una virgola.
IMPORTANTE: Mantieni le righe vuote tra i punti per garantire che vadano a capo correttamente.

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
