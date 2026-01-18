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

# --- KARTEN-DATEN (Vollständig aus PDF) ---
CARD_LIST = [
    (0, "Tradition", "Blau", "Wer sie am Ende hält, verliert. Ziehe neu.", "Glaube durch Bräuche der Vorfahren."),
    (0, "Indoktrination", "Rot", "Wer sie am Ende hält, verliert. Ziehe neu.", "Spiritualität als Unvernunft verspottet."),
    (1, "Missionar", "Blau", "Rate Handkarte eines Gegners. Richtig? Er fliegt.", "Botschaft der Hoffnung teilen."),
    (1, "Aufklärer", "Rot", "Rate Handkarte. (Im Zweifel: Danach noch ein Zug).", "Nur Akzeptanz des Beweisbaren."),
    (2, "Beichtvater", "Blau", "Sieh dir die Handkarte eines Gegners an.", "Geständnis bringt Erleichterung."),
    (2, "Psychologe", "Rot", "Sieh dir Handkarte an. (Zusatzkarte möglich).", "Religion als Projektion von Wünschen."),
    (3, "Mystiker", "Blau", "Vergleiche Karten; der niedrigere Wert fliegt.", "Spüren einer transzendenten Realität."),
    (3, "Logiker", "Rot", "Vergleiche Karten; (Sieg bei Gleichstand).", "Gott mathematisch nicht vereinbar."),
    (4, "Eremit", "Blau", "Schutz vor Effekten bis zum nächsten Zug.", "Fokus auf das Wesentliche."),
    (4, "Stoiker", "Rot", "Schutz vor Effekten bis zum nächsten Zug.", "Welt objektiv akzeptieren."),
    (5, "Prediger", "Blau", "Ein Spieler legt Karte ab und zieht neu.", "Worte öffnen das Herz."),
    (6, "Prophet", "Blau", "Tausche Karten mit einem Mitspieler.", "Visionen einer gerechteren Welt."),
    (7, "Wunder", "Blau", "Muss abgelegt werden, wenn man die 8 hält.", "Ereignisse jenseits der Wissenschaft."),
    (8, "Präsenz (Gott)", "Blau", "Wer sie am Ende hält, gewinnt.", "Vollkommenheit in allem erkennen."),
    (8, "Atheist (Die Leere)", "Rot", "Wer sie am Ende hält, gewinnt.", "Trost für die eigene Endlichkeit.")
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

    # 2. HANDKARTEN
    cols = st.columns(len(me["hand"]))
    for i, card in enumerate(me["hand"]):
        with cols[i]:
            c_color = "#1E90FF" if card["color"] == "Blau" else "#FF4500"
            st.markdown(f"<div style='border:2px solid {c_color}; padding:10px; border-radius:10px;'><b>{card['name']} ({card['val']})</b><br><small>{card['eff']}</small></div>", unsafe_allow_html=True)
            if state["turn"] == st.session_state.user and len(me["hand"]) > 1:
                if st.button("Spielen", key=f"btn_{i}"):
                    played = me["hand"].pop(i)
                    state["log"].append(f"📢 {st.session_state.user} bekennt: {played['name']}")
                    
                    if played["val"] in [1, 2, 3, 5, 6]:
                        st.session_state.pending_action = played
                    else:
                        if played["val"] == 4: me["protected"] = True
                        alive = [p for p in players if players[p]["active"]]
                        state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                        save(state); st.rerun()

    # 3. AKTIONEN AUSFÜHREN
    if "pending_action" in st.session_state:
        card = st.session_state.pending_action
        targets = [p for p in players if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]
        
        if not targets:
            st.warning("Kein gültiges Ziel verfügbar!")
            if st.button("Zug beenden"): del st.session_state.pending_action; st.rerun()
        else:
            target = st.selectbox("Ziel wählen:", targets)
            
            # WERT 1: Raten
            if card["val"] == 1:
                guess = st.number_input("Handkarte raten (0-8):", 0, 8)
                if st.button("Raten!"):
                    if players[target]["hand"][0]["val"] == guess:
                        players[target]["active"] = False
                        state["log"].append(f"🎯 Erfolg! {target} fliegt raus.")
                    del st.session_state.pending_action; save(state); st.rerun()
            
            # WERT 6: Tauschen
            if card["val"] == 6:
                if st.button("Karten tauschen"):
                    me["hand"][0], players[target]["hand"][0] = players[target]["hand"][0], me["hand"][0]
                    state["log"].append(f"🔄 {st.session_state.user} hat mit {target} getauscht.")
                    del st.session_state.pending_action; save(state); st.rerun()

else:
    st.error("Du bist ausgeschieden.")

with st.expander("Protokoll"):
    for l in reversed(state["log"]): st.write(l)
