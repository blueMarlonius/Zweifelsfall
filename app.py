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
    (0, "Tradition", "Blau", "Wer diese Karte am Ende hält, verliert. Beim Ausspielen: Ziehe eine neue Karte.", "Glauben durch Bräuche der Vorfahren."),
    (0, "Indoktrination", "Rot", "Wer diese Karte am Ende hält, verliert. Beim Ausspielen: Ziehe eine neue Karte.", "Spiritualität als Unvernunft verspottet."),
    (1, "Missionar", "Blau", "Rate die Handkarte eines Gegners. Richtig? Er fliegt.", "Die frohe Botschaft teilen."),
    (1, "Aufklärer", "Rot", "Rate die Handkarte eines Gegners. Richtig? Er fliegt.", "Nur Beweisbares akzeptieren."),
    (2, "Beichtvater", "Blau", "Sieh dir die Handkarte eines Gegners an.", "Geständnis bringt Erleichterung."),
    (2, "Psychologe", "Rot", "Sieh dir die Handkarte eines Gegners an.", "Religion als Projektion von Wünschen."),
    (3, "Mystiker", "Blau", "Vergleiche Karten; der niedrigere Wert scheidet aus.", "Spüren einer transzendenten Realität."),
    (3, "Logiker", "Rot", "Vergleiche Karten; der niedrigere Wert scheidet aus.", "Schöpfer nicht mit Chaos vereinbar."),
    (4, "Eremit", "Blau", "Schutz vor allen Effekten bis zum nächsten Zug.", "Fokus auf das Wesentliche."),
    (4, "Stoiker", "Rot", "Schutz vor allen Effekten bis zum nächsten Zug.", "Welt objektiv akzeptieren."),
    (5, "Prediger", "Blau", "Ein Spieler legt seine Karte ab und zieht neu.", "Worte öffnen das Herz."),
    (5, "Reformator", "Rot", "Ein Spieler legt seine Karte ab und zieht neu.", "Dogmen halten Prüfung nicht stand."),
    (6, "Prophet", "Blau", "Tausche Karten mit einem Mitspieler.", "Visionen einer gerechteren Welt."),
    (6, "Agnostiker", "Rot", "Tausche Karten mit einem Mitspieler.", "Wahrheit bleibt unerreichbar."),
    (7, "Wunder/Zufall", "B/R", "Muss abgelegt werden, wenn man die 8 hält.", "Ereignisse jenseits der Wissenschaft."),
    (8, "Präsenz/Atheist", "B/R", "Wer sie am Ende hält, gewinnt. Nicht freiwillig ablegen.", "Vollkommenheit oder Endlichkeit.")
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

st_autorefresh(interval=4000, key="sync")
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

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

# --- GEWINNER-CHECK ---
alive = [p for p in players if players[p]["active"]]
if len(alive) == 1 and len(players) > 1:
    st.balloons()
    st.header(f"🏆 {alive[0]} hat gewonnen!")
    if st.button("Raum löschen & Beenden"):
        doc_ref.delete(); st.rerun()
    st.stop()

me = players[st.session_state.user]
st.markdown(f"<h1 style='text-align: center; color: #FFD700;'>Dran: {state['turn']}</h1>", unsafe_allow_html=True)

if me["active"]:
    # 1. ZIEHEN
    if state["turn"] == st.session_state.user and len(me["hand"]) == 1:
        if st.button("Karte ziehen 🃏", use_container_width=True):
            me["hand"].append(state["deck"].pop())
            me["protected"] = False
            save(state); st.rerun()

    # 2. HANDKARTEN
    cols = st.columns(len(me["hand"]))
    for i, card in enumerate(me["hand"]):
        with cols[i]:
            c_color = "#1E90FF" if card["color"] == "Blau" else "#FF4500"
            st.markdown(f"<div style='border:3px solid {c_color}; padding:10px; border-radius:10px;'><b>{card['name']} ({card['val']})</b></div>", unsafe_allow_html=True)
            if state["turn"] == st.session_state.user and len(me["hand"]) > 1:
                if st.button(f"Spielen", key=f"btn_{i}", use_container_width=True):
                    played = me["hand"].pop(i)
                    state["log"].append(f"📢 {st.session_state.user} spielt {played['name']}")
                    if played["val"] == 0: me["hand"].append(state["deck"].pop())
                    
                    if played["val"] in [1, 2, 3, 5, 6]:
                        st.session_state.pending_action = played
                        save(state); st.rerun()
                    else:
                        if played["val"] == 4: me["protected"] = True
                        idx = (alive.index(st.session_state.user) + 1) % len(alive)
                        state["turn"] = alive[idx]
                        save(state); st.rerun()

    # 3. AKTIONEN MIT BESTÄTIGUNG
    if "pending_action" in st.session_state:
        card = st.session_state.pending_action
        st.markdown(f"### Effekt von: {card['name']}")
        targets = [p for p in players if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]
        
        if not targets:
            st.warning("Kein Ziel möglich!")
            if st.button("Aktion ohne Effekt beenden"):
                idx = (alive.index(st.session_state.user) + 1) % len(alive)
                state["turn"] = alive[idx]
                del st.session_state.pending_action; save(state); st.rerun()
        else:
            target = st.selectbox("Wähle einen Mitspieler:", targets)
            
            # WERT 1 (Raten)
            if card["val"] == 1:
                guess = st.number_input("Karte raten (0-8):", 0, 8)
                if st.button("Rate-Angriff bestätigen"):
                    if players[target]["hand"][0]["val"] == guess:
                        players[target]["active"] = False
                        state["log"].append(f"🎯 Erfolg! {target} wurde entlarvt.")
                    else: state["log"].append(f"❌ Fehlversuch gegen {target}.")
                    idx = (alive.index(st.session_state.user) + 1) % len(alive)
                    state["turn"] = alive[idx]
                    del st.session_state.pending_action; save(state); st.rerun()

            # WERT 2 (Ansehen)
            if card["val"] == 2:
                st.info(f"{target} hält: {players[target]['hand'][0]['name']}")
                if st.button("Information bestätigen & Zug beenden"):
                    idx = (alive.index(st.session_state.user) + 1) % len(alive)
                    state["turn"] = alive[idx]
                    del st.session_state.pending_action; save(state); st.rerun()

            # WERT 3 (Vergleichen)
            if card["val"] == 3:
                if st.button("Vergleich bestätigen"):
                    v1, v2 = me["hand"][0]["val"], players[target]["hand"][0]["val"]
                    if v1 > v2: players[target]["active"] = False
                    elif v2 > v1: me["active"] = False
                    state["log"].append(f"⚔️ {st.session_state.user}({v1}) vs {target}({v2})")
                    # Turn-Logic nach Ausscheiden
                    new_alive = [p for p in players if players[p]["active"]]
                    state["turn"] = new_alive[0] if len(new_alive) > 0 else state["turn"]
                    del st.session_state.pending_action; save(state); st.rerun()

            # WERT 5 (Ablegen lassen)
            if card["val"] == 5:
                if st.button("Ablegen & Neu ziehen lassen"):
                    old_card = players[target]["hand"].pop()
                    players[target]["hand"].append(state["deck"].pop())
                    state["log"].append(f"♻️ {target} musste {old_card['name']} ablegen.")
                    idx = (alive.index(st.session_state.user) + 1) % len(alive)
                    state["turn"] = alive[idx]
                    del st.session_state.pending_action; save(state); st.rerun()

            # WERT 6 (Tauschen)
            if card["val"] == 6:
                if st.button("Tausch bestätigen"):
                    me["hand"][0], players[target]["hand"][0] = players[target]["hand"][0], me["hand"][0]
                    state["log"].append(f"🔄 Tausch zwischen {st.session_state.user} und {target}.")
                    idx = (alive.index(st.session_state.user) + 1) % len(alive)
                    state["turn"] = alive[idx]
                    del st.session_state.pending_action; save(state); st.rerun()

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
