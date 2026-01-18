import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- 1. SETUP & DATENBANK ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- 2. KARTEN-DEFINITIONEN ---
CARD_DATA = {
    0: ("Tradition", "Indoktrination", "Menschen glauben (nicht), weil es schon immer so war.", "Verlust am Ende. Ausspielen: Ziehe eine Karte."),
    1: ("Missionar", "Aufklärer", "Menschen glauben (nicht), weil sie überzeugt wurden.", "Rate eine Handkarte. Zweifel: Du erhältst einen freiwilligen Extrazug."),
    2: ("Beichtvater", "Psychologe", "Menschen glauben (nicht), weil sie Trost suchen.", "Sieh dir eine Handkarte an. Zweifel: Du MUSST eine Karte ziehen."),
    3: ("Mystiker", "Logiker", "Menschen glauben (nicht), weil es sich richtig anfühlt.", "Vergleiche Handkarten; der niedrigere Wert fliegt raus. Zweifel: Sieg bei Gleichstand."),
    4: ("Eremit", "Stoiker", "Menschen glauben (nicht), weil sie Ruhe brauchen.", "Du bist bis zu deinem nächsten Zug vor allen Effekten geschützt."),
    5: ("Prediger", "Reformator", "Menschen glauben (nicht), weil sie Führung brauchen.", "Ein Spieler legt seine Handkarte ab und zieht neu. Zweifel: Zwei Spieler tun dies."),
    6: ("Prophet", "Agnostiker", "Menschen glauben (nicht), weil sie Visionen haben.", "Tausche deine Handkarte mit einem Mitspieler. Zweifel: Erst alle Karten ansehen."),
    7: ("Wunder", "Zufall", "Menschen glauben (nicht), weil Unfassbares geschah.", "Wenn du diese Karte und die 8 auf der Hand hast, musst du diese ablegen."),
    8: ("Gott", "Atheist", "Die finale Antwort.", "Siegkarte. Wer diese am Ende hält, gewinnt meist die Runde.")
}

def create_deck():
    counts = {0:1, 1:3, 2:3, 3:2, 4:2, 5:2, 6:1, 7:1, 8:1}
    deck = []
    for val, num in counts.items():
        for color in ["Blau", "Rot"]:
            for _ in range(num):
                names = CARD_DATA[val]
                name = names[0] if color == "Blau" else names[1]
                deck.append({"val": val, "name": name, "color": color, "quote": names[2], "effect": names[3]})
    random.shuffle(deck)
    return deck

def save(s): db.collection("games").document(st.session_state.gid).set(s)

# --- 3. LOGIN ---
if "user" not in st.session_state:
    with st.form("login"):
        st.header("⚖️ ZWEIFELSFALL")
        n, r = st.text_input("Name:"), st.text_input("Raum-ID:")
        if st.form_submit_button("Beitreten"):
            st.session_state.user, st.session_state.gid = n.strip(), r.strip()
            st.rerun()
    st.stop()

st_autorefresh(interval=3000, key="sync")
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

if not state:
    if st.button("Spielraum erstellen"):
        state = {"started": False, "players": {}, "order": [], "deck": [], "log": [], "turn_idx": 0, "phase": "LOBBY"}
        save(state); st.rerun()
    st.stop()

# --- 4. LOBBY ---
if not state.get("started", False):
    p_names = state.get("order", [])
    st.header(f"Lobby: {st.session_state.gid} ({len(p_names)}/5)")
    for name in p_
