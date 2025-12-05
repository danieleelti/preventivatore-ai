import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pandas as pd

# --- IMPORT DATABASE ---
# Questo importerà le variabili già "piene" di dati dal file loader.py
from loader import master_database
from loader import faq_database
from loader import location_database

# Ora puoi usare 'master_database' esattamente come facevi prima
# Esempio di test (puoi cancellarlo dopo):
# print(f"Il primo elemento del master è: {master_database[0]}")

# --- 1. QUESTA DEVE ESSERE LA PRIMA RIGA DI STREAMLIT ---
st.set_page_config(page_title="Preventivatore TeamBuilding", page_icon="🦁", layout="centered")

# --- CONFIGURAZIONE API ---
api_key = st.secrets["GOOGLE_API_KEY"]

# PASSWORD PER LO STAFF
PASSWORD_SEGRETA = "TeamBuilding2025#"

# --- CARICAMENTO DATABASE CSV ---
@st.cache_data(ttl=600) # Cache per non ricaricare il CSV ad ogni click, si aggiorna ogni 10 min
def load_database():
    try:
        df = pd.read_csv("MasterTb.csv", sep=None, engine='python')
        # Converte il CSV in una stringa Markdown ben formattata per l'AI
        return df.to_markdown(index=False)
    except Exception as e:
        return None

csv_data = load_database()

if csv_data is None:
    st.error("⚠️ ERRORE CRITICO: Non trovo il file 'MasterTb.csv'. Caricalo nella repo di GitHub!")
    st.stop()

# --- IL CERVELLO (SYSTEM PROMPT PARTE FISSA) ---
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

*Esempio logica: (80€ * 1.1 * 1.0) * 20 persone = 1.760€ (che poi diventa 1.800€ per il minimo).*

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
Se l'utente scrive "Reset", "Nuovo" o "Stop", DIMENTICA tutti i dati precedenti (Pax, Data, Location) e ricomincia dalla FASE 0 salutando come se fosse un nuovo cliente.

FASE 0: INTERVISTA
Se l'utente non ti da i dati (Pax, Data, Obiettivo, tempo a disposizione per l'attività), chiedili subito. Non fare preventivi al buio.

FASE 1: LA PROPOSTA STRATEGICA (La Regola dei 12)
Proponi sempre una rosa di 12 FORMAT selezionati dal Database, distribuiti tassativamente così:

1. I 4 BEST SELLER (Le Certezze): Scegli prioritariamente tra questi format (se adatti alla richiesta):
CSI Project, Chain Reaction, Escape Box, AperiBuilding, Cooking, Treasure Hunt, Sarabanda, Cinema, Lego Building, Actors Studio, Cartoon Car Race, Cocktail Building, Affresco, Squid Game, Bike Building, Bootcamp, Enigma, Olympic Games, Leonardo da Vinci.

2. LE 4 NOVITÀ (L'Innovazione): Scegli dal Database i format etichettati come "Novità: si" o quelli più tecnologici (es. AI, VR).

3. I 2 VIBE: Scegli quelli che meglio sposano l'emozione richiesta (Relax, Adrenalina, Creatività...).

4. I 2 SOCIAL: Scegli format CSR/Beneficenza (es. Animal House, Energy for Africa...).

VINCOLI:
Inverno (Nov-Mar): NO Outdoor (salvo richiesta esplicita).
Pasti: NO Outdoor durante pranzi/cene.
Varietà: Non proporre sempre gli stessi 4. Ruota le opzioni se possibile.

* **Output visivo per ogni format:**
    > 🏆 **[Nome Format]**
    > 📄 **Scheda:** [Link PDF Ita cliccabile]
    > 💡 *Perché:* [Motivazione]
    > ⚠️ *Note:* [Note se presenti]

**FASE 2: IL PREVENTIVO **
Mostra solo il **TOTALE** stimato. Non mostrare i calcoli matematici.
*Esempio output:* "Il costo totale per [Nome Format] per [N] persone è di **€ 2.200,00 + IVA**".

**FASE 3: OVERRIDE OPERATORE**
L'operatore comanda. Se dice "Sconta 10%" o "Fai 2000€", esegui ignorando le regole sopra.
"""

# Uniamo le istruzioni con il contenuto del CSV
FULL_SYSTEM_PROMPT = f"{BASE_INSTRUCTIONS}\n\n### 💾 [DATABASE FORMAT AGGIORNATO]\n\n{csv_data}"

# --- CODICE TECNICO ---
genai.configure(api_key=api_key)

generation_config = {
  "temperature": 0.0, 
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
}

# --- CONFIGURAZIONE SICUREZZA ---
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# Utilizziamo Gemini 2.0 Flash Exp (il più avanzato attualmente disponibile)
# Se hai accesso a una beta privata chiamata "gemini-3.0", modifica il nome qui sotto.
model = genai.GenerativeModel(
  model_name="gemini-2.0-flash-exp", 
  generation_config=generation_config,
  system_instruction=FULL_SYSTEM_PROMPT,
  safety_settings=safety_settings,
)

# Login Semplice
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

# App Vera e Propria
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
        with st.spinner("Elaborazione con Gemini 2.0..."):
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



