import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import csv
import os

# --- 1. CONFIGURAZIONE PAGINA (PRIMA RIGA OBBLIGATORIA) ---
st.set_page_config(page_title="Preventivatore TeamBuilding", page_icon="🦁", layout="centered")

# --- 2. GESTIONE DATABASE (Caricamento Sicuro) ---
@st.cache_data(show_spinner=False)
def carica_database(nome_file):
    percorso = os.path.join(os.getcwd(), nome_file)
    
    if not os.path.exists(percorso):
        return None 

    lista_dati = []
    # Tentiamo diverse codifiche per evitare errori
    encodings = ['utf-8', 'latin-1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(percorso, mode='r', encoding=encoding) as file:
                # Google Sheets usa la virgola
                reader = csv.DictReader(file, delimiter=',')
                for riga in reader:
                    lista_dati.append(riga)
            return lista_dati
        except UnicodeDecodeError:
            continue
        except Exception:
            return None 
    return None

# Funzione per trasformare la lista in testo per l'AI
def database_to_string(database_list):
    if not database_list:
        return "Nessun dato disponibile."
    # Prende le chiavi (intestazioni) dal primo elemento
    header = " | ".join(database_list[0].keys())
    rows = []
    for riga in database_list:
        # Unisce i valori di ogni riga
        rows.append(" | ".join(str(v) for v in riga.values()))
    return header + "\n" + "\n".join(rows)

# --- CARICAMENTO EFFETTIVO ---
# Usiamo i nomi in MINUSCOLO come hai impostato su GitHub
master_database = carica_database('mastertb.csv') 
faq_database = carica_database('faq.csv')
location_database = carica_database('location.csv')

# --- CONTROLLI DI SICUREZZA ---
if master_database is None:
    st.error("⚠️ ERRORE CRITICO: Non trovo 'mastertb.csv'. Verifica che il file su GitHub sia scritto TUTTO MINUSCOLO.")
    st.stop()

# Prepariamo i dati per il prompt dell'AI
csv_data_string = database_to_string(master_database)

# Gestione opzionale degli altri file
if faq_database is None:
    st.warning("⚠️ Attenzione: 'faq.csv' non caricato.")
    faq_database = [] 

if location_database is None:
    st.warning("⚠️ Attenzione: 'location.csv' non caricato.")
    location_database = []


# --- 3. CONFIGURAZIONE API E PASSWORD ---
api_key = st.secrets["GOOGLE_API_KEY"]
PASSWORD_SEGRETA = "TeamBuilding2025#"

# Login
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

# --- 4. IL CERVELLO (PROMPT) ---
BASE_INSTRUCTIONS = """
SEI IL SENIOR EVENT MANAGER DI TEAMBUILDING.IT.
Strumento ad uso interno. Rispondi in Italiano.

### 🎯 OBIETTIVO
Massimizzare la conversione.
1.  Proporre i format giusti (Regola dei 12).
2.  Calcolare il **COSTO TOTALE DELL'EVENTO** (non a persona).
3.  Non mostrare mai i calcoli e i moltiplicatori

---

### 🔢 MOTORE DI CALCOLO PREVENTIVI (Formula Totale)
Quando richiesto, calcola il prezzo usando i dati del [DATABASE INTERNO] fornito alla fine.

**PASSO 1: Trova i dati nel Database**
Cerca il format e prendi:
* `P_BASE` (Prezzo indicato dopo "Pricing:")
* `METODO` (Standard o Flat)

**PASSO 2: Seleziona la Formula**

🔴 **SE METODO = "Standard" (o vuoto):**
La formula per il **TOTALE** è:
`TOTALE = P_BASE * (Moltiplicatore Pax * Moltiplicatore Durata * Moltiplicatore Lingua * Moltiplicatore Location * Moltiplicatore Stagione) * NUMERO PARTECIPANTI`

**TABELLA MOLTIPLICATORI:**
* **M_PAX (Quantità):**
    * < 5: x 3.20
    * 5 - 10: x 1.60
    * 11 - 20: x 1.05
    * 21 - 30: x 0.95
    * 31 - 60: x 0.90
    * 61 - 90: x 0.90
    * 91 - 150: x 0.85
    * 151 - 250: x 0.70
    * 251 - 350: x 0.63
    * 351 - 500: x 0.55
    * 501 - 700: x 0.50
    * 701 - 900: x 0.49
    * > 900: x 0.30
* **M_DURATA:** ≤1h (x 1.05) | 1-2h (x 1.07) | 2-4h (x 1.10) | >4h (x 1.15)
* **M_LINGUA:** Italiano (x 1.05) | Inglese (x 1.10)
* **M_LOCATION:** Milano (x 1.00) | Roma (x 0.95) | Centro (x 1.05) | Nord/Sud (x 1.15) | Isole (x 1.30)
* **M_STAGIONE:** Mag-Ott (x 1.10) | Nov-Apr (x 1.02)

🔵 **SE METODO = "Flat":**
Usa l'interpolazione lineare sul totale.
* Formula Base: `1800 + ((Numero Partecipanti - 20) * 4.80)`
* Eccezione: Se nel database c'è scritto "Costo Fisso: X", somma quel valore al risultato.
* A questo totale, applica SOLO i moltiplicatori Location e Lingua.

**PASSO 3: REGOLA MINIMUM SPENDING (Fondamentale)**
Se il TOTALE calcolato è inferiore a **€ 1.800,00**, il preventivo finale è **€ 1.800,00**.

---

### 🚦 FLUSSO DI LAVORO

**COMANDO SPECIALE "RESET" o "NUOVO":**
Se l'utente scrive "Reset", "Nuovo" o "Stop", DIMENTICA tutti i dati precedenti e ricomincia.

FASE 0: INTERVISTA
Se mancano i dati (Pax, Data, Obiettivo), chiedili subito.

FASE 1: LA PROPOSTA STRATEGICA (La Regola dei 12)
Proponi sempre una rosa di 12 FORMAT selezionati dal Database:
1. I 4 BEST SELLER
2. LE 4 NOVITÀ
3. I 2 VIBE
4. I 2 SOCIAL

**Output visivo per ogni format:**
    > 🏆 **[Nome Format]**
    > 📄 **Scheda:** [Link PDF Ita]
    > 💡 *Perché:* [Motivazione]

**FASE 2: IL PREVENTIVO **
Mostra solo il **TOTALE** stimato. Non mostrare i calcoli matematici.
"""

# Uniamo le istruzioni con il contenuto del CSV convertito in stringa
FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS}\n\n### 💾 [DATABASE FORMAT AGGIORNATO]\n\n{csv_data_string}"

# --- 5. CONFIGURAZIONE AI ---
genai.configure(api_key=api_key)

generation_config = {
  "temperature": 0.0, 
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
}

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

model = genai.GenerativeModel(
  model_name="gemini-3-pro-preview", 
  generation_config={"temperature": 0.0},
  system_instruction=FULL_SYSTEM_PROMPT, # <--- CORRETTO: Usiamo la variabile che esiste davvero!
  safety_settings=safety_settings,
)

# --- 6. INTERFACCIA CHAT ---
st.title("🦁 Preventivatore AI")
st.caption("Assistente Virtuale Senior - MasterTb Connected")

if "messages" not in st.session_state:
    st.session_state.messages = []
    welcome = "Ciao! Ho caricato il nuovo Database MasterTb. Sono pronto. Dimmi numero pax, data e obiettivo."
    st.session_state.messages.append({"role": "model", "content": welcome})

# Mostra cronologia
for message in st.session_state.messages:
    role = message["role"]
    with st.chat_message(role):
        st.markdown(message["content"])

# Input Utente
if prompt := st.chat_input("Scrivi qui la richiesta..."):
    # 1. Aggiungi user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Gestione RESET
    if prompt.lower().strip() in ["reset", "nuovo", "cancella", "stop"]:
        st.session_state.messages = []
        st.rerun()

    # 3. Genera risposta AI
    with st.chat_message("model"):
        with st.spinner("Elaborazione con Gemini 3.0..."):
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


