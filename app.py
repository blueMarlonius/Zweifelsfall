import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- SETUP & DB ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- KARTEN-LISTE ---
CARD_LIST = [
    (0, "Tradition", "Blau", "Verliert am Ende.", "Bräuche."),
    (0, "Indoktrination", "Rot", "Glaubenstest erzwingen.", "Umfeld."),
    (1, "Missionar", "Blau", "Raten.", "Hoffnung."),
    (1, "Aufklärer", "Rot", "Raten + ZWANG: Zusatzug.", "Vernunft."),
    (2, "Beichtvater", "Blau", "Ansehen.", "Erleichterung."),
    (2, "Psychologe", "Rot", "Ansehen + ZWANG: Karte ziehen.", "Projektion."),
    (3, "Mystiker", "Blau", "Vergleich.", "Stille."),
    (3, "Logiker", "Rot", "Vergleich + ZWANG: Sieg bei Gleichstand.", "Logik."),
    (4, "Eremit", "Blau", "Schutz.", "Einsamkeit."),
    (4, "Stoiker", "Rot", "Schutz.", "Akzeptanz."),
    (5, "Prediger", "Blau", "Ablegen.", "Worte."),
    (5, "Reformator", "Rot", "Ablegen + ZWANG: Zwei Ziele.", "Prüfung."),
    (6, "Prophet", "Blau", "Tausch.", "Vision."),
    (6, "Agnostiker", "Rot", "Tausch + ZWANG: Erst alles ansehen.", "Unerreichbar."),
    (7, "Wunder", "Blau", "Abwerfen bei 8.", "Wunder."),
    (7, "Zufall", "Rot", "Abwerfen bei 8.", "Zufall."),
    (8, "Präsenz", "Blau", "Siegkarte.", "Vollkommenheit."),
    (8, "Atheist", "Rot", "Siegkarte.", "Endlichkeit.")
]

def save(state): db.collection("games").document(st.session_state.gid).set(state)

# --- LOGIN ---
if "user" not in st.session_state:
    with st.form("login"):
        st.header("⚖️ Zweifelsfall")
        n, r = st.text_input("Name:"), st.text_input("Raum:")
        if st.form_submit_button("Beitreten"):
            st.session_state.user, st.session_state.gid = n.strip(), r.strip()
            st.rerun()
    st.stop()

st_autorefresh(interval=4000, key="sync")
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

# --- INIT ---
if not state:
    if st.button("Start"):
        deck = []
        for c in CARD_LIST: deck.extend([{"val":c[0],"name":c[1],"color":c[2],"eff":c[3],"txt":c[4]}] * 2)
        random.shuffle(deck)
        state = {"deck": deck, "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "protected": False, "in_test": False}}, "turn": st.session_state.user, "log": []}
        save(state); st.rerun()
    st.stop()

players = state["players"]
me = players[st.session_state.user]
alive = [p for p in players if players[p]["active"]]

if "winner" in state or len(alive) == 1:
    st.balloons(); st.header(f"🏆 Gewinner steht fest!"); 
    if st.button("Löschen"): doc_ref.delete(); st.rerun()
    st.stop()

# --- DER GLAUBENSTEST-CHECK AM ANFANG DES ZUGS ---
st.title(f"Dran: {state['turn']}")

if state["turn"] == st.session_state.user and me["active"]:
    if me["in_test"]:
        st.error("⚖️ GLAUBENSTEST! Du hast eine rote Karte vor dir liegen.")
        if st.button("Schicksalskarte ziehen...", use_container_width=True):
            test_card = state["deck"].pop()
            state["log"].append(f"⚖️ {st.session_state.user} zieht im Test: {test_card['name']} ({test_card['color']})")
            if test_card["color"] == "Rot":
                me["active"] = False
                state["log"].append(f"💀 Rot gezogen! {st.session_state.user} ist ausgeschieden.")
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
            else:
                st.success("Blau! Du darfst weiterspielen.")
                me["in_test"] = False
            save(state); st.rerun()
        st.stop()

    # NORMALER ZUG
    if len(me["hand"]) == 1 and len(state["deck"]) > 0:
        if st.button("Karte ziehen 🃏", use_container_width=True):
            me["hand"].append(state["deck"].pop()); me["protected"] = False
            save(state); st.rerun()

    # KARTEN SPIELEN
    cols = st.columns(len(me["hand"]))
    for i, card in enumerate(me["hand"]):
        with cols[i]:
            c_color = "#FF4500" if card["color"] == "Rot" else "#1E90FF"
            st.markdown(f"<div style='border:3px solid {c_color}; padding:10px; border-radius:10px;'><b>{card['name']}</b></div>", unsafe_allow_html=True)
            if len(me["hand"]) > 1 and st.button("Spielen", key=f"p_{i}"):
                played = me["hand"].pop(i)
                state["log"].append(f"📢 {st.session_state.user} legt {played['name']}")
                
                # Wenn Rot gelegt wird -> Markierung für nächsten Zug
                if played["color"] == "Rot":
                    me["in_test"] = True
                
                if played["val"] in [1, 2, 3, 5, 6]:
                    st.session_state.pending_action = played
                    save(state); st.rerun()
                else:
                    state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                    save(state); st.rerun()

# --- EFFEKT-LOGIK (Missionar, Psychologe etc.) ---
if "pending_action" in st.session_state:
    card = st.session_state.pending_action
    targets = [p for p in players if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]
    if targets:
        target = st.selectbox("Ziel:", targets)
        if st.button("Effekt bestätigen"):
            # Zwang für Rot
            if card["color"] == "Rot" and card["val"] == 1: # Aufklärer
                state["log"].append("⚖️ Zweifel: Zusatzug!")
                # Turn wechselt nicht
            else:
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
            
            del st.session_state.pending_action; save(state); st.rerun()
