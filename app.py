import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- DB & SETUP ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- KARTEN-LISTE (32 Karten laut PDF) ---
DECK_TEMPLATE = [
    (0, "Tradition/Indoktrination", "B/R", "Verliert am Ende.", "Menschen glauben (nicht), weil..."),
    (1, "Missionar/Aufklärer", "B/R", "Raten. (Zweifel: Extrazug)", "Menschen glauben (nicht), weil..."),
    (2, "Beichtvater/Psychologe", "B/R", "Ansehen. (Zweifel: Karte ziehen)", "Menschen glauben (nicht), weil..."),
    (3, "Mystiker/Logiker", "B/R", "Vergleich.", "Menschen glauben (nicht), weil..."),
    (4, "Eremit/Stoiker", "B/R", "Schutz.", "Menschen glauben (nicht), weil..."),
    (5, "Prediger/Reformator", "B/R", "Ablegen lassen.", "Menschen glauben (nicht), weil..."),
    (6, "Prophet/Agnostiker", "B/R", "Tausch.", "Menschen glauben (nicht), weil..."),
    (7, "Wunder/Zufall", "B/R", "Ablegen bei 8.", "Menschen glauben (nicht), weil..."),
    (8, "Präsenz/Atheist", "B/R", "Siegkarte.", "Menschen glauben (nicht), weil...")
]

def save(s): db.collection("games").document(st.session_state.gid).set(s)

# --- LOGIN ---
if "user" not in st.session_state:
    with st.form("login"):
        st.header("⚖️ ZWEIFELSFALL")
        n, r = st.text_input("Name:"), st.text_input("Raum:")
        if st.form_submit_button("Beitreten"):
            st.session_state.user, st.session_state.gid = n.strip(), r.strip()
            st.rerun()
    st.stop()

st_autorefresh(interval=3000, key="sync")
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

# --- INITIALISIERUNG ---
if not state:
    if st.button("Neues Spiel"):
        deck = [] # 32 Karten mischen [cite: 16, 21]
        for val, name, _, eff, txt in DECK_TEMPLATE:
            # Vereinfacht: Jede Karte existiert mehrmals (insg. 32)
            for color in ["Blau", "Rot"]:
                deck.append({"val": val, "name": name, "color": color, "eff": eff, "txt": txt})
        random.shuffle(deck)
        deck.pop() # Eine Karte verdeckt beiseite [cite: 22]
        state = {
            "deck": deck, 
            "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "visible_card": None}},
            "turn": st.session_state.user, "log": [], "started": False, "pending_eff": None
        }
        save(state); st.rerun()
    st.stop()

players = state.get("players", {})
if st.session_state.user not in players:
    if st.button("Raum beitreten"):
        state["players"][st.session_state.user] = {"hand": [state["deck"].pop()], "active": True, "visible_card": None}
        save(state); st.rerun()
    st.stop()

# --- LOBBY & SIEG ---
alive = [p for p in players if players[p].get("active")]
if not state.get("started"):
    st.info(f"Spieler: {len(players)}/4")
    if len(players) > 1 and st.button("Starten"):
        state["started"] = True; save(state); st.rerun()
    st.stop()

if len(alive) == 1:
    st.balloons(); st.header(f"🏆 {alive[0]} gewinnt die Runde!"); 
    st.button("Neu starten", on_click=lambda: doc_ref.delete()); st.stop()

me = players[st.session_state.user]
st.title(f"Dran: {state['turn']}")

# --- SCHRITT 1: ÜBERZEUGUNGSTEST --- [cite: 27]
if state["turn"] == st.session_state.user and me["active"]:
    # Nur wenn eine rote Karte offen vor dir liegt! 
    if me.get("visible_card") and me["visible_card"]["color"] == "Rot":
        st.warning("⚠️ ÜBERZEUGUNGSTEST: Rot liegt vor dir!")
        if st.button("Test-Karte ziehen"):
            test_card = state["deck"].pop()
            state["log"].append(f"⚖️ {st.session_state.user} testet: {test_card['color']}")
            if test_card["color"] == "Rot":
                me["active"] = False
                state["log"].append(f"💀 {st.session_state.user} scheidet aus!")
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
            save(state); st.rerun()
        st.stop()

    # SCHRITT 2 & 3: ZIEHEN UND BEKENNTNIS [cite: 29, 32]
    if len(me["hand"]) == 1 and not state.get("pending_eff"):
        if st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop()); save(state); st.rerun()

    if len(me["hand"]) == 2:
        cols = st.columns(2)
        for i, card in enumerate(me["hand"]):
            with cols[i]:
                color_code = "red" if card["color"] == "Rot" else "blue"
                st.markdown(f"<div style='border:3px solid {color_code}; padding:10px;'>{card['name']} ({card['color']})</div>", unsafe_allow_html=True)
                if st.button(f"Ausspielen", key=f"play_{i}"):
                    played = me["hand"].pop(i)
                    me["visible_card"] = played # Ersetzt die alte Karte 
                    state["log"].append(f"💬 {st.session_state.user} bekennt: '{played['txt']}'")
                    state["pending_eff"] = played
                    save(state); st.rerun()

    # EFFEKTE
    if state.get("pending_eff"):
        card = state["pending_eff"]
        st.info(f"Effekt: {card['eff']}")
        targets = [p for p in players if p != st.session_state.user and players[p]["active"]]
        if targets:
            target = st.selectbox("Ziel wählen:", targets)
            if st.button("Bestätigen"):
                # Hier Kartenspezifische Logik einfügen...
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                state["pending_eff"] = None
                save(state); st.rerun()

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
