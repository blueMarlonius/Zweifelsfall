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

# --- KARTEN-DATEN (Alle 32 Karten-Typen aus dem PDF) ---
CARD_LIST = [
    (0, "Tradition", "Blau", "Wer sie am Ende hält, verliert. Ziehe beim Ausspielen neu.", "Menschen glauben an Gott, weil sie die Bräuche ihrer Vorfahren ehren."), [cite: 5, 6, 8]
    (0, "Indoktrination", "Rot", "Wer sie am Ende hält, verliert. Ziehe beim Ausspielen neu.", "Spiritualität wird als Unvernunft verspottet."), [cite: 10, 11, 13]
    (1, "Missionar", "Blau", "Rate die Handkarte eines Gegners. Richtig? Er fliegt.", "Die frohe Botschaft der Hoffnung teilen."), [cite: 15, 16]
    (1, "Aufklärer", "Rot", "Rate Handkarte. (Im Zweifel: Danach noch ein Zug).", "Nur das akzeptieren, was beweisbar ist."), [cite: 18, 19]
    (2, "Beichtvater", "Blau", "Sieh dir die Handkarte eines Gegners an.", "Geständnis der Fehler verschafft Erleichterung."), [cite: 21, 22, 23]
    (2, "Psychologe", "Rot", "Sieh dir Handkarte an. (Im Zweifel: Ziehe zusätzlich eine Karte).", "Religion als Projektion menschlicher Wünsche."), [cite: 25, 26, 27]
    (3, "Mystiker", "Blau", "Vergleiche Karten; der niedrigere Wert scheidet aus.", "Spüren einer transzendenten Realität."), [cite: 29, 30, 31]
    (3, "Logiker", "Rot", "Vergleiche Karten; (Im Zweifel: Sieg bei Gleichstand).", "Ein gütiger Schöpfer ist mathematisch nicht vereinbar."), [cite: 32, 33, 34]
    (4, "Eremit", "Blau", "Schutz vor allen Effekten bis zum nächsten Zug.", "Einsamkeit hilft, sich auf das Wesentliche zu konzentrieren."), [cite: 36, 37]
    (4, "Stoiker", "Rot", "Schutz vor allen Effekten bis zum nächsten Zug.", "Die Welt objektiv akzeptieren, wie sie ist."), [cite: 38, 39]
    (5, "Prediger", "Blau", "Ein Spieler legt seine Karte ab und zieht neu.", "Die Kraft der Worte öffnet das Herz."), [cite: 41, 42, 43]
    (6, "Prophet", "Blau", "Tausche Karten mit einem Mitspieler.", "Visionen von einer gerechteren Welt."), [cite: 49, 50, 51]
    (7, "Wunder", "Blau", "Muss abgelegt werden, wenn man die 8 hält.", "Ereignisse, die wissenschaftliche Erklärungen sprengen."), [cite: 58, 59, 60]
    (8, "Präsenz (Gott)", "Blau", "Wer sie am Ende hält, gewinnt. Nicht freiwillig ablegbar.", "Vollkommenheit des Seins erkennen."), [cite: 67, 68, 70]
    (8, "Atheist (Die Leere)", "Rot", "Wer sie am Ende hält, gewinnt.", "Gott als Trost für die eigene Endlichkeit.") [cite: 72, 73, 74]
]

def save(state): db.collection("games").document(st.session_state.gid).set(state)

# --- LOGIN ---
if "user" not in st.session_state:
    with st.form("login"):
        st.header("⚖️ Zweifelsfall")
        n = st.text_input("Dein Name:")
        r = st.text_input("Spiel-Raum:")
        if st.form_submit_button("Beitreten"):
            st.session_state.user, st.session_state.gid = n.strip(), r.strip()
            st.rerun()
    st.stop()

# --- DATEN SYNC ---
st_autorefresh(interval=5000, key="sync")
doc = db.collection("games").document(st.session_state.gid).get()
state = doc.to_dict()

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

me = players[st.session_state.user]

# --- SPIEL-INTERFACE ---
st.write(f"Raum: **{st.session_state.gid}** | Dran: **{state['turn']}**")

if me["active"]:
    # 1. ZIEHEN
    if state["turn"] == st.session_state.user and len(me["hand"]) == 1:
        if st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop())
            me["protected"] = False
            save(state); st.rerun()

    # 2. SPIELEN
    cols = st.columns(len(me["hand"]))
    for i, card in enumerate(me["hand"]):
        with cols[i]:
            c_color = "#1E90FF" if card["color"] == "Blau" else "#FF4500"
            st.markdown(f"<div style='border:2px solid {c_color}; padding:5px; border-radius:5px;'><b>{card['name']}</b></div>", unsafe_allow_html=True)
            if state["turn"] == st.session_state.user and len(me["hand"]) > 1:
                if st.button("Spielen", key=f"btn_{i}"):
                    played = me["hand"].pop(i)
                    state["log"].append(f"📢 {st.session_state.user} bekennt: {played['name']}")
                    
                    # Interaktive Aktionen
                    if played["val"] in [1, 2, 3, 5, 6]:
                        st.session_state.pending_action = (played, i)
                    else:
                        if played["val"] == 4: me["protected"] = True
                        alive = [p for p in players if players[p]["active"]]
                        state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                        save(state); st.rerun()

    # 3. INTERAKTIVE MENÜS
    if "pending_action" in st.session_state:
        card, _ = st.session_state.pending_action
        target = st.selectbox("Ziel wählen:", [p for p in players if p != st.session_state.user and players[p]["active"]])
        
        if card["val"] == 1: # Missionar/Aufklärer [cite: 16, 18]
            guess = st.number_input("Wert raten (0-8):", 0, 8)
            if st.button("Bestätigen"):
                if players[target]["hand"][0]["val"] == guess:
                    players[target]["active"] = False
                    state["log"].append(f"🎯 Erfolg! {target} fliegt raus.")
                del st.session_state.pending_action
                save(state); st.rerun()

        if card["val"] == 2: # Beichtvater 
            st.info(f"{target} hat die Karte: {players[target]['hand'][0]['name']}")
            if st.button("Ok"): 
                del st.session_state.pending_action; st.rerun()

else:
    st.error("Ausgeschieden.")

with st.expander("Protokoll"):
    for l in reversed(state["log"]): st.write(l)
