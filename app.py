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
    0: ("Tradition", "Indoktrination", "Verlust am Ende. Ausspielen: Ziehe Karte."),
    1: ("Missionar", "Aufklärer", "Rate Karte. Zweifel: Freiwilliger Extrazug."),
    2: ("Beichtvater", "Psychologe", "Sieh Karte an. Zweifel: MUSS Karte ziehen."),
    3: ("Mystiker", "Logiker", "Vergleich. Zweifel: Sieg bei Gleichstand."),
    4: ("Eremit", "Stoiker", "Schutz vor Effekten."),
    5: ("Prediger", "Reformator", "Ablegen lassen. Zweifel: Zwei tauschen."),
    6: ("Prophet", "Agnostiker", "Tausch. Zweifel: Erst alle ansehen."),
    7: ("Wunder", "Zufall", "Abwurfzwang bei 8."),
    8: ("Gott", "Atheist", "Siegkarte.")
}

def create_deck():
    counts = {0:1, 1:3, 2:3, 3:2, 4:2, 5:2, 6:1, 7:1, 8:1}
    deck = []
    for val, num in counts.items():
        for color in ["Blau", "Rot"]:
            for _ in range(num):
                name = CARD_DATA[val][0 if color=="Blau" else 1]
                deck.append({"val": val, "name": name, "color": color})
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

# --- 4. LOBBY (Reparierte Anzeige) ---
if not state.get("started", False):
    st.header(f"🏠 Lobby: {st.session_state.gid}")
    p_names = state.get("order", [])
    
    st.subheader(f"Spieler: {len(p_names)} / 5")
    for name in p_names:
        st.write(f"👤 {name}")

    if st.session_state.user not in state["players"] and len(p_names) < 5:
        if st.button("Beitreten"):
            state["players"][st.session_state.user] = {"markers": 0, "active": True, "discard_stack": [], "hand": [], "protected": False}
            state["order"].append(st.session_state.user); save(state); st.rerun()

    if p_names and p_names[0] == st.session_state.user:
        st.divider()
        if st.button("🔀 Zufällige Reihenfolge"): random.shuffle(state["order"]); save(state); st.rerun()
        if st.button("✅ SPIEL STARTEN", type="primary"):
            state.update({"started": True, "deck": create_deck(), "phase": "TEST"})
            for n in state["order"]:
                state["players"][n].update({"active": True, "hand": [state["deck"].pop()], "discard_stack": []})
            save(state); st.rerun()
    st.stop()

# --- 5. GAMEPLAY ---
players = state["players"]
me = players[st.session_state.user]
curr_p = state["order"][state["turn_idx"]]

# Zweifel-Check nach Anleitung: Lag VOR dem Zug eine rote Karte offen da? [cite: 18, 27]
was_in_doubt = False
if me["discard_stack"] and me["discard_stack"][-1]["color"] == "Rot":
    was_in_doubt = True

st.title("⚖️ ZWEIFELSFALL")

# Eigene Hand (Immer sichtbar)
st.subheader("Deine Hand")
h_cols = st.columns(2)
for i, c in enumerate(me["hand"]):
    with h_cols[i]:
        st.markdown(f"<div style='border:2px solid {'red' if c['color']=='Rot' else 'blue'}; padding:10px;'>{c['name']} ({c['val']})</div>", unsafe_allow_html=True)

if curr_p == st.session_state.user and me["active"]:
    # PHASE 1: TEST
    if state["phase"] == "TEST":
        if was_in_doubt: # [cite: 27]
            st.warning("Überzeugungstest!")
            if st.button("Testkarte ziehen"):
                test_c = state["deck"].pop()
                if test_c["color"] == "Rot": # [cite: 28]
                    me["active"] = False; state["phase"] = "NEXT"
                else: state["phase"] = "DRAW"
                save(state); st.rerun()
        else:
            state["phase"] = "DRAW"; save(state); st.rerun()

    # PHASE 2: DRAW
    elif state["phase"] == "DRAW":
        if len(me["hand"]) < 2 and st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop()); save(state); st.rerun()
        if len(me["hand"]) == 2:
            st.write("Karte ausspielen:")
            for i, c in enumerate(me["hand"]):
                if st.button(f"{c['name']} legen", key=f"lay{i}"):
                    state["active_doubt"] = was_in_doubt # Status merken [cite: 2]
                    me["discard_stack"].append(me["hand"].pop(i))
                    state["phase"] = "EFFECT"; save(state); st.rerun()

    # PHASE 3: EFFECT
    elif state["phase"] == "EFFECT":
        played = me["discard_stack"][-1]
        targets = [p for p in state["order"] if p != st.session_state.user and players[p]["active"]]
        
        # Logik-Fix: Zwangseffekt nur, wenn man bereits im Zweifel WAR [cite: 2]
        if played["val"] == 2: # Psychologe
            if "pk_d" not in state:
                target = st.selectbox("Ziel wählen:", targets)
                if st.button("Ansehen"):
                    state["pk_v"] = f"{target} hat eine {players[target]['hand'][0]['val']}"
                    state["pk_d"] = True; save(state); st.rerun()
            else:
                st.code(state["pk_v"])
                if state.get("active_doubt"): # Nur bei echtem Zweifel [cite: 18]
                    st.warning("Zweifels-Zwang: Ziehe eine Karte!")
                    if st.button("Pflicht-Karte ziehen"):
                        me["hand"].append(state["deck"].pop())
                        del state["pk_d"], state["pk_v"]; state["phase"] = "NEXT"; save(state); st.rerun()
                elif st.button("Zug beenden"):
                    del state["pk_d"], state["pk_v"]; state["phase"] = "NEXT"; save(state); st.rerun()
        else:
            if st.button("Zug beenden"): state["phase"] = "NEXT"; save(state); st.rerun()

    elif state["phase"] == "NEXT":
        state["turn_idx"] = (state["turn_idx"] + 1) % len(state["order"])
        state["phase"] = "TEST"; save(state); st.rerun()
