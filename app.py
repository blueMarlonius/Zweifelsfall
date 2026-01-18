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

# --- 2. KARTEN-DEFINITIONEN (VOLLSTÄNDIG) ---
CARD_DATA = {
    0: ("Tradition", "Indoktrination", "Menschen glauben (nicht), weil es schon immer so war.", "Verlust am Ende. Ausspielen: Ziehe Karte."),
    1: ("Missionar", "Aufklärer", "Menschen glauben (nicht), weil sie überzeugt wurden.", "Rate Karte. Zweifel: Freiwilliger Extrazug."),
    2: ("Beichtvater", "Psychologe", "Menschen glauben (nicht), weil sie Trost suchen.", "Sieh Karte an. Zweifel: MUSS Karte ziehen."),
    3: ("Mystiker", "Logiker", "Menschen glauben (nicht), weil es sich richtig anfühlt.", "Vergleich. Zweifel: Sieg bei Gleichstand."),
    4: ("Eremit", "Stoiker", "Menschen glauben (nicht), weil sie Ruhe brauchen.", "Schutz vor Effekten."),
    5: ("Prediger", "Reformator", "Menschen glauben (nicht), weil sie Führung brauchen.", "Ablegen lassen. Zweifel: Zwei tauschen."),
    6: ("Prophet", "Agnostiker", "Menschen glauben (nicht), weil sie Visionen haben.", "Tausch. Zweifel: Erst alle ansehen."),
    7: ("Wunder", "Zufall", "Menschen glauben (nicht), weil Unfassbares geschah.", "Abwurfzwang bei 8."),
    8: ("Gott", "Atheist", "Die finale Antwort.", "Siegkarte.")
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

# --- 3. LOGIN & SYNC ---
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
    for name in p_names: st.write(f"👤 {name}")
    if st.session_state.user not in state["players"] and len(p_names) < 5:
        if st.button("Beitreten"):
            state["players"][st.session_state.user] = {"markers": 0, "active": True, "discard_stack": [], "hand": [], "protected": False}
            state["order"].append(st.session_state.user); save(state); st.rerun()
    if p_names and p_names[0] == st.session_state.user:
        if st.button("Zufällige Reihenfolge"): random.shuffle(state["order"]); save(state); st.rerun()
        if st.button("SPIEL STARTEN"):
            state.update({"started": True, "deck": create_deck(), "phase": "TEST"})
            for n in state["order"]:
                state["players"][n].update({"active": True, "hand": [state["deck"].pop()], "discard_stack": []})
            save(state); st.rerun()
    st.stop()

# --- 5. GAMEPLAY ---
players = state["players"]
me = players[st.session_state.user]
curr_p = state["order"][state["turn_idx"]]

# Zweifel-Prüfung (Lag Rot vor dem Zug?)
was_in_doubt = False
if me["discard_stack"] and me["discard_stack"][-1]["color"] == "Rot":
    was_in_doubt = True

st.title("⚖️ ZWEIFELSFALL")

# Anzeige Mitspieler (Ablagestapel)
st.subheader("Spielfeld")
cols = st.columns(len(state["order"]))
for i, name in enumerate(state["order"]):
    p_data = players[name]
    with cols[i]:
        st.markdown(f"**{name}** ({p_data['markers']} ⚪)")
        if not p_data["active"]: st.error("Aus")
        elif p_data["protected"]: st.caption("🛡️")
        if p_data["discard_stack"]:
            top = p_data["discard_stack"][-1]
            st.markdown(f"""<div style="border:2px solid {'red' if top['color']=='Rot' else 'blue'}; padding:5px; border-radius:5px; font-size:0.8em; background:#222;">
                <b>{top['name']}</b> ({top['val']})</div>""", unsafe_allow_html=True)

# Deine Handkarten (Vollständiger Text)
st.divider()
st.subheader("Deine Hand")
h_cols = st.columns(2)
for i, c in enumerate(me["hand"]):
    with h_cols[i]:
        st.markdown(f"""<div style="border:3px solid {'red' if c['color']=='Rot' else 'blue'}; padding:15px; border-radius:10px; background:#111;">
            <h3 style="margin:0;">{c['name']} ({c['val']})</h3>
            <p style="font-style:italic; color:#aaa;">{c['quote']}</p>
            <hr>
            <p><b>Effekt:</b> {c['effect']}</p>
            </div>""", unsafe_allow_html=True)

# --- DER ZUG ---
if curr_p == st.session_state.user and me["active"]:
    if state["phase"] == "TEST":
        if was_in_doubt:
            st.warning("Überzeugungstest nötig!")
            if st.button("Testkarte ziehen"):
                test_c = state["deck"].pop()
                state["log"].append(f"⚖️ {st.session_state.user} testet: {test_c['color']}")
                if test_c["color"] == "Rot":
                    me["active"] = False; state["phase"] = "NEXT"
                else: state["phase"] = "DRAW"
                save(state); st.rerun()
        else: state["phase"] = "DRAW"; save(state); st.rerun()

    elif state["phase"] == "DRAW":
        if len(me["hand"]) < 2 and st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop()); save(state); st.rerun()
        if len(me["hand"]) == 2:
            st.write("Wähle eine Karte zum Ausspielen:")
            for i, c in enumerate(me["hand"]):
                if st.button(f"{c['name']} ausspielen", key=f"play_{i}"):
                    state["active_doubt"] = was_in_doubt
                    me["discard_stack"].append(me["hand"].pop(i))
                    me["protected"] = False; state["phase"] = "EFFECT"; save(state); st.rerun()

    elif state["phase"] == "EFFECT":
        played = me["discard_stack"][-1]
        is_doubt = state.get("active_doubt", False)
        targets = [p for p in state["order"] if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]

        if played["val"] == 0:
            if st.button("Bonuskarte ziehen"): me["hand"].append(state["deck"].pop()); state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 1: # Aufklärer
            target = st.selectbox("Ziel wählen:", targets) if targets else None
            guess = st.number_input("Karte raten (0-8):", 0, 8)
            if st.button("Bestätigen") and target:
                if players[target]["hand"][0]["val"] == guess:
                    players[target]["active"] = False; state["log"].append(f"🎯 {target} eliminiert!")
                if is_doubt: state["bonus_ready"] = True
                else: state["phase"] = "NEXT"
                save(state); st.rerun()
            if state.get("bonus_ready"):
                if st.button("Zusatzzug"): del state["bonus_ready"]; state["phase"] = "TEST"; save(state); st.rerun()
                if st.button("Verzichten"): del state["bonus_ready"]; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 2: # Psychologe
            if "pk_v" not in state:
                target = st.selectbox("Ansehen:", targets) if targets else None
                if st.button("Karte ansehen") and target:
                    state["pk_v"] = f"{target} hat: {players[target]['hand'][0]['name']} ({players[target]['hand'][0]['val']})"
                    save(state); st.rerun()
            else:
                st.code(state["pk_v"])
                if is_doubt:
                    if st.button("Pflicht: Karte ziehen"):
                        me["hand"].append(state["deck"].pop()); del state["pk_v"]; state["phase"] = "NEXT"; save(state); st.rerun()
                elif st.button("Beenden"): del state["pk_v"]; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 3: # Logiker
            target = st.selectbox("Vergleichen:", targets) if targets else None
            if st.button("Vergleichen") and target:
                my_v, t_v = me["hand"][0]["val"], players[target]["hand"][0]["val"]
                if my_v > t_v: players[target]["active"] = False
                elif t_v > my_v: me["active"] = False
                elif is_doubt: players[target]["active"] = False # Sieg bei Gleichstand
                state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 4: # Stoiker
            if st.button("Schutz aktivieren"): me["protected"] = True; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 6: # Agnostiker
            target = st.selectbox("Tauschen:", targets) if targets else None
            if st.button("Tauschen") and target:
                me["hand"], players[target]["hand"] = players[target]["hand"], me["hand"]
                state["phase"] = "NEXT"; save(state); st.rerun()

        else:
            if st.button("Zug beenden"): state["phase"] = "NEXT"; save(state); st.rerun()

    elif state["phase"] == "NEXT":
        state["turn_idx"] = (state["turn_idx"] + 1) % len(state["order"])
        state["phase"] = "TEST"; save(state); st.rerun()

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
