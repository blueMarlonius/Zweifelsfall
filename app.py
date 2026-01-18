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

# --- 2. KARTEN-DEFINITION (32 STÜCK NACH ANLEITUNG) ---
# [cite: 16, 21]
CARD_DATA = {
    0: ("Tradition", "Indoktrination", "Verlierer am Ende.", "Menschen glauben (nicht), weil..."),
    1: ("Missionar", "Aufklärer", "Karte raten.", "Menschen glauben (nicht), weil..."),
    2: ("Beichtvater", "Psychologe", "Karte ansehen.", "Menschen glauben (nicht), weil..."),
    3: ("Mystiker", "Logiker", "Vergleich.", "Menschen glauben (nicht), weil..."),
    4: ("Eremit", "Stoiker", "Schutz.", "Menschen glauben (nicht), weil..."),
    5: ("Prediger", "Reformator", "Ablegen lassen.", "Menschen glauben (nicht), weil..."),
    6: ("Prophet", "Agnostiker", "Tausch.", "Menschen glauben (nicht), weil..."),
    7: ("Wunder", "Zufall", "Abwurf bei 8.", "Menschen glauben (nicht), weil..."),
    8: ("Gott", "Atheist", "Siegkarte.", "Menschen glauben (nicht), weil...")
}

def create_deck():
    counts = {0:1, 1:3, 2:3, 3:2, 4:2, 5:2, 6:1, 7:1, 8:1}
    deck = []
    for val, num in counts.items():
        for color in ["Blau", "Rot"]:
            for _ in range(num):
                name = CARD_DATA[val][0 if color=="Blau" else 1]
                deck.append({
                    "val": val, "name": name, "color": color, 
                    "eff": CARD_DATA[val][2], "txt": CARD_DATA[val][3]
                })
    random.shuffle(deck)
    return deck

def save(s): db.collection("games").document(st.session_state.gid).set(s)

# --- 3. LOGIN & LOBBY ---
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
        state = {"started": False, "players": {}, "order": [], "deck": [], "log": [], "turn_idx": 0, "phase": "LOBBY", "check_stack": []}
        save(state); st.rerun()
    st.stop()

# Lobby-Verwaltung (max 5 Spieler)
if not state["started"]:
    players = state["players"]
    if st.session_state.user not in players and len(players) < 5:
        if st.button("Mitspielen"):
            players[st.session_state.user] = {"markers": 0, "active": True, "discard_stack": [], "hand": []}
            state["order"].append(st.session_state.user)
            save(state); st.rerun()
    
    st.write(f"Spieler ({len(players)}/5):", ", ".join(state["order"]))
    if state["order"] and state["order"][0] == st.session_state.user:
        if st.button("Zufällige Reihenfolge"): random.shuffle(state["order"]); save(state); st.rerun()
        if st.button("SPIEL STARTEN"):
            state["started"] = True
            # Runde initialisieren
            deck = create_deck()
            deck.pop() # [cite: 22]
            for p in state["order"]:
                state["players"][p].update({"active": True, "hand": [deck.pop()], "discard_stack": []})
            state["deck"] = deck
            state["phase"] = "TEST" # Phase 1 startet
            save(state); st.rerun()
    st.stop()

# --- 4. SPIEL-LOGIK ---
players = state["players"]
order = state["order"]
curr_p_name = order[state["turn_idx"]]
me = players[st.session_state.user]
alive = [p for p in order if players[p]["active"]]

# UI: STATUS-ANZEIGE
st.title("⚖️ ZWEIFELSFALL")
cols = st.columns(len(order))
for i, p_name in enumerate(order):
    p_data = players[p_name]
    with cols[i]:
        st.write(f"**{p_name}** ({p_data['markers']}⚪)")
        if not p_data["active"]: st.error("Ausgeschieden")
        if p_data["discard_stack"]:
            top = p_data["discard_stack"][-1]
            color = "#FF4500" if top["color"] == "Rot" else "#1E90FF"
            st.markdown(f"<div style='border:3px solid {color}; padding:5px; text-align:center;'>{top['name']} ({top['val']})</div>", unsafe_allow_html=True)

# PRÜFSTAPEL ANZEIGEN
if state["check_stack"]:
    with st.expander("Gemeinsamer Prüfstapel", expanded=True):
        st.write(f"Letzte Karte: {state['check_stack'][-1]['name']} ({state['check_stack'][-1]['color']})")

# AKTIVER ZUG
if curr_p_name == st.session_state.user and me["active"]:
    # PHASE 1: ÜBERZEUGUNGSTEST [cite: 27, 28]
    if state["phase"] == "TEST":
        st.subheader("Phase 1: Überzeugungstest")
        if me["discard_stack"] and me["discard_stack"][-1]["color"] == "Rot":
            st.warning("Dein persönlicher Ablagestapel zeigt ROT!")
            if st.button("Prüfkarte ziehen"):
                test_card = state["deck"].pop()
                state["check_stack"].append(test_card)
                state["log"].append(f"⚖️ {st.session_state.user} zieht {test_card['color']} im Test.")
                
                # Spezialsieg rote 8 
                if test_card["color"] == "Rot" and any(c['val'] == 8 and c['color'] == 'Rot' for c in me['hand']):
                    state["log"].append(f"🌟 SPEZIALSIEG durch rote 8!")
                    # Logik für Rundenende hier...
                elif test_card["color"] == "Rot":
                    me["active"] = False
                    state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
                    state["phase"] = "TEST"
                else:
                    state["phase"] = "DRAW"
                save(state); st.rerun()
        else:
            state["phase"] = "DRAW"; save(state); st.rerun()

    # PHASE 2: ZIEHEN & AUSSPIELEN [cite: 30, 31]
    if state["phase"] == "DRAW":
        if len(me["hand"]) == 1:
            if st.button("Karte ziehen"):
                me["hand"].append(state["deck"].pop()); save(state); st.rerun()
        
        if len(me["hand"]) == 2:
            st.subheader("Schritt 2: Ausspielen")
            c_cols = st.columns(2)
            for i, card in enumerate(me["hand"]):
                with c_cols[i]:
                    st.info(f"{card['name']} ({card['color']})")
                    if st.button("Wählen", key=f"sel_{i}"):
                        played = me["hand"].pop(i)
                        me["discard_stack"].append(played) # [cite: 31]
                        state["phase"] = "EFFECT"
                        save(state); st.rerun()

    # PHASE 3: BEKENNTNIS & EFFEKT 
    if state["phase"] == "EFFECT":
        played = me["discard_stack"][-1]
        st.subheader("Schritt 3: Bekenntnis")
        st.success(f"🗣️ {played['txt']}")
        if st.button("Effekt ausführen & Zug beenden"):
            state["log"].append(f"💬 {st.session_state.user} bekennt: {played['name']}")
            state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
            state["phase"] = "TEST"
            save(state); st.rerun()

# RUNDENENDE LOGIK [cite: 35-38]
if len(alive) <= 1 or len(state["deck"]) == 0:
    st.divider()
    if st.button("Runde auswerten"):
        # Gewinner-Berechnung nach Anleitung [cite: 13, 38]
        # (Logik für höchste Karte & Summe Ablagestapel hier einfügen)
        pass

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
