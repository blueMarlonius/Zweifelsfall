import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- DATENBANK VERBINDUNG ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- KARTEN-DATEN ---
CARD_LIST = [
    (0, "Tradition/Indoktrination", "B/R", "Wer sie am Ende hält, verliert. Beim Ausspielen: Ziehe neu.", "Hintergrund: Sozialisation und Umfeld."),
    (1, "Missionar/Aufklärer", "B/R", "Rate Handkarte eines Gegners. Richtig? Er fliegt.", "Hintergrund: Überzeugung und Beweisbarkeit."),
    (2, "Beichtvater/Psychologe", "B/R", "Sieh dir die Handkarte eines Gegners an.", "Hintergrund: Erleichterung und Projektion."),
    (3, "Mystiker/Logiker", "B/R", "Vergleiche Karten; der niedrigere Wert scheidet aus.", "Hintergrund: Transzendenz vs. Mathematik."),
    (4, "Eremit/Stoiker", "B/R", "Schutz vor allen Effekten bis zum nächsten Zug.", "Hintergrund: Wesentliches und Akzeptanz."),
    (5, "Prediger/Reformator", "B/R", "Ein Spieler legt seine Karte ab und zieht neu.", "Hintergrund: Herzensöffnung vs. Dogmenkritik."),
    (6, "Prophet/Agnostiker", "B/R", "Tausche Karten mit einem Mitspieler.", "Hintergrund: Visionen vs. Unerreichbarkeit."),
    (7, "Wunder/Zufall", "B/R", "Muss abgelegt werden, wenn man die 8 hält.", "Hintergrund: Wissenschaftliche Grenzen."),
    (8, "Präsenz/Atheist", "B/R", "Wer sie am Ende hält, gewinnt. Darf nicht abgelegt werden!", "Hintergrund: Vollkommenheit vs. Endlichkeit.")
]

def save(state): db.collection("games").document(st.session_state.gid).set(state)

# --- LOGIN & SYNC ---
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

# --- INITIALISIERUNG ---
if not state:
    if st.button("Neues Spiel starten"):
        deck = []
        for c in CARD_LIST: deck.extend([{"val":c[0],"name":c[1],"color":c[2],"eff":c[3],"txt":c[4]}] * 2)
        random.shuffle(deck)
        state = {"deck": deck, "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "protected": False}}, "turn": st.session_state.user, "log": []}
        save(state); st.rerun()
    st.stop()

players = state["players"]
if st.session_state.user not in players:
    if st.button("Beitreten"):
        state["players"][st.session_state.user] = {"hand": [state["deck"].pop()], "active": True, "protected": False}
        save(state); st.rerun()
    st.stop()

alive = [p for p in players if players[p]["active"]]
me = players[st.session_state.user]

# --- SPIELFELD ---
st.markdown(f"<h1 style='text-align: center;'>Dran: {state['turn']}</h1>", unsafe_allow_html=True)

if me["active"]:
    # ZIEHEN
    if state["turn"] == st.session_state.user and len(me["hand"]) == 1:
        if st.button("Karte ziehen 🃏", use_container_width=True):
            me["hand"].append(state["deck"].pop())
            me["protected"] = False
            save(state); st.rerun()

    # HANDKARTEN
    cols = st.columns(len(me["hand"]))
    has_8 = any(c["val"] == 8 for c in me["hand"])
    
    for i, card in enumerate(me["hand"]):
        with cols[i]:
            c_color = "#1E90FF" if "Blau" in card["name"] or i%2==0 else "#FF4500" # Vereinfachte Farblogik für Demo
            st.markdown(f"<div style='border:3px solid {c_color}; padding:10px; border-radius:10px; background-color:#111; min-height:180px;'><b>{card['name']} ({card['val']})</b><br><small>{card['eff']}</small></div>", unsafe_allow_html=True)
            
            # LOGIK: 8 darf NICHT abgelegt werden
            if state["turn"] == st.session_state.user and len(me["hand"]) > 1:
                if card["val"] == 8:
                    st.warning("⚠️ Diese Karte darf nicht abgelegt werden.")
                else:
                    if st.button(f"Spielen", key=f"btn_{i}", use_container_width=True):
                        played = me["hand"].pop(i)
                        state["log"].append(f"📢 {st.session_state.user} spielt {played['name']}")
                        
                        if played["val"] == 0: me["hand"].append(state["deck"].pop())
                        
                        if played["val"] in [1, 2, 3, 5, 6]:
                            st.session_state.pending_action = played
                            save(state); st.rerun()
                        else:
                            if played["val"] == 4: me["protected"] = True
                            state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                            save(state); st.rerun()

    # AKTIONEN (Bestätigungs-Buttons)
    if "pending_action" in st.session_state:
        card = st.session_state.pending_action
        st.divider()
        targets = [p for p in players if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]
        
        if not targets:
            st.warning("Kein Ziel verfügbar!")
            if st.button("Ohne Effekt beenden"):
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                del st.session_state.pending_action; save(state); st.rerun()
        else:
            target = st.selectbox("Ziel wählen:", targets)
            # Hier die Button-Logik für 1, 2, 3, 5, 6 (wie im vorherigen Code)
            if st.button(f"Effekt von {card['name']} bestätigen"):
                # ... (hier die spezifische Logik ausführen)
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                del st.session_state.pending_action; save(state); st.rerun()

else:
    st.error("Warte auf die nächste Runde.")

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
