import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- DB SETUP ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- KARTEN-DEFINITION ---
CARD_DIST = {0: 1, 1: 3, 2: 3, 3: 2, 4: 2, 5: 2, 6: 1, 7: 1, 8: 1}
CARD_TEXTS = {
    0: ("Tradition", "Indoktrination", "Wer diese Karte am Ende hält, verliert.", "Menschen glauben (nicht), weil..."),
    1: ("Missionar", "Aufklärer", "Rate die Handkarte eines Gegners.", "Menschen glauben (nicht), weil..."),
    2: ("Beichtvater", "Psychologe", "Sieh dir eine Karte an.", "Menschen glauben (nicht), weil..."),
    3: ("Mystiker", "Logiker", "Vergleiche Handkarten.", "Menschen glauben (nicht), weil..."),
    4: ("Eremit", "Stoiker", "Schutz bis zum nächsten Zug.", "Menschen glauben (nicht), weil..."),
    5: ("Prediger", "Reformator", "Ein Spieler legt seine Karte ab.", "Menschen glauben (nicht), weil..."),
    6: ("Prophet", "Agnostiker", "Tausche Karten.", "Menschen glauben (nicht), weil..."),
    7: ("Wunder", "Zufall", "Abwerfen bei 8.", "Menschen glauben (nicht), weil..."),
    8: ("Präsenz", "Atheist", "Siegkarte.", "Menschen glauben (nicht), weil...")
}

def create_deck():
    deck = []
    for val, count in CARD_DIST.items():
        names = CARD_TEXTS[val]
        for _ in range(count):
            deck.append({"val": val, "name": names[0], "color": "Blau", "eff": names[2], "txt": f"Glaube: {names[3]}"})
            deck.append({"val": val, "name": names[1], "color": "Rot", "eff": names[2], "txt": f"Skepsis: {names[3]}"})
    random.shuffle(deck)
    return deck

def save(s): db.collection("games").document(st.session_state.gid).set(s)

# --- LOGIN ---
if "user" not in st.session_state:
    with st.form("login"):
        st.header("⚖️ ZWEIFELSFALL")
        n, r = st.text_input("Dein Name:"), st.text_input("Raum-ID:")
        if st.form_submit_button("Eintreten"):
            st.session_state.user, st.session_state.gid = n.strip(), r.strip()
            st.rerun()
    st.stop()

st_autorefresh(interval=3000, key="sync")
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

# --- INITIALISIERUNG ---
if not state:
    if st.button("Spiel erstellen"):
        state = {
            "started": False, "players": {}, "order": [], "deck": [], 
            "log": [], "turn": 0, "round_active": False, "markers": {}, "game_over": False
        }
        save(state); st.rerun()
    st.stop()

# --- LOBBY & REIHENFOLGE ---
if not state["started"]:
    st.subheader(f"Lobby: {st.session_state.gid}")
    players = state["players"]
    if st.session_state.user not in players and len(players) < 5:
        if st.button("Teilnehmen"):
            players[st.session_state.user] = {"markers": 0, "active": True}
            state["order"].append(st.session_state.user)
            save(state); st.rerun()
    
    st.write("Spielerreihenfolge:")
    for i, p in enumerate(state["order"]): st.write(f"{i+1}. {p}")
    
    if state["order"] and state["order"][0] == st.session_state.user:
        if st.button("Zufällige Reihenfolge"):
            random.shuffle(state["order"]); save(state); st.rerun()
        if st.button("REIHENFOLGE BESTÄTIGEN & STARTEN"):
            state["started"] = True
            state["round_active"] = True
            # Runde initialisieren
            deck = create_deck()
            state["buried"] = deck.pop() # Eine Karte weglegen [cite: 22]
            for p in state["order"]:
                state["players"][p].update({"hand": [deck.pop()], "active": True, "played": None})
            state["deck"] = deck
            state["turn"] = 0
            save(state); st.rerun()
    st.stop()

# --- SPIEL-LOGIK ---
players = state["players"]
order = state["order"]
curr_player_name = order[state["turn"]]
me = players[st.session_state.user]
alive = [p for p in order if players[p]["active"]]

# RUNDEN-ENDE CHECK
if state["round_active"] and (len(alive) == 1 or len(state["deck"]) == 0):
    winner = ""
    if len(alive) == 1: winner = alive[0]
    else: # Höchste Karte gewinnt [cite: 38]
        winner = max(alive, key=lambda x: players[x]["hand"][0]["val"])
    
    players[winner]["markers"] += 1
    state["log"].append(f"🏆 Rundenende! {winner} gewinnt einen Sinnmarker.")
    state["round_active"] = False
    
    if players[winner]["markers"] >= 3:
        state["game_over"] = True
    save(state); st.rerun()

# --- ANZEIGE ---
st.title("⚖️ ZWEIFELSFALL")
cols = st.columns(len(order))
for i, p_name in enumerate(order):
    p_data = players[p_name]
    with cols[i]:
        st.write(f"**{p_name}** ({p_data['markers']} ⚪)")
        if not p_data["active"]: st.error("Ausgeschieden")
        if p_data.get("played"):
            c = p_data["played"]
            color = "red" if c["color"] == "Rot" else "blue"
            st.markdown(f"<div style='border:2px solid {color}; padding:5px; font-size:0.8em;'>{c['name']}<br>{c['val']}</div>", unsafe_allow_html=True)

# AKTIONEN
if state["round_active"] and curr_player_name == st.session_state.user and me["active"]:
    # SCHRITT 1: ÜBERZEUGUNGSTEST [cite: 27, 28]
    if me.get("played") and me["played"]["color"] == "Rot" and not state.get("test_done"):
        st.warning("Überzeugungstest!")
        if st.button("Karte vom Stapel aufdecken"):
            test_c = state["deck"].pop()
            state["log"].append(f"⚖️ {st.session_state.user} deckt {test_c['color']} auf.")
            if test_c["color"] == "Rot":
                me["active"] = False
                state["turn"] = (state["turn"] + 1) % len(order)
            state["test_done"] = True
            save(state); st.rerun()
        st.stop()

    # SCHRITT 2: ZIEHEN & SPIELEN [cite: 29, 30, 31]
    if len(me["hand"]) == 1:
        if st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop()); save(state); st.rerun()
    
    if len(me["hand"]) == 2:
        st.write("Karte wählen:")
        c1, c2 = st.columns(2)
        for i, card in enumerate(me["hand"]):
            with [c1, c2][i]:
                st.info(f"{card['name']} ({card['color']})\n\n{card['eff']}")
                if st.button("Spielen", key=f"play_{i}"):
                    played = me["hand"].pop(i)
                    me["played"] = played
                    state["log"].append(f"💬 {st.session_state.user}: {played['name']} - {played['txt']}")
                    state["turn"] = (state["turn"] + 1) % len(order)
                    state["test_done"] = False # Reset für nächsten Zug
                    save(state); st.rerun()

# --- NÄCHSTE RUNDE ODER RANG LISTE ---
if not state["round_active"]:
    if state["game_over"]:
        st.header("🏁 SPIEL ENDE")
        # Rangliste
        ranks = sorted(players.items(), key=lambda x: x[1]["markers"], reverse=True)
        for i, (name, data) in enumerate(ranks):
            st.write(f"{i+1}. {name}: {data['markers']} Sinnmarker")
        if st.button("Neustart"): doc_ref.delete(); st.rerun()
    else:
        st.write("Nächste Runde starten?")
        if st.button("Ja"):
            deck = create_deck()
            state["buried"] = deck.pop()
            for p in order:
                players[p].update({"hand": [deck.pop()], "active": True, "played": None})
            state["deck"] = deck
            state["round_active"] = True
            save(state); st.rerun()

with st.expander("Protokoll"):
    for l in reversed(state["log"]): st.write(l)
