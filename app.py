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
    0: ("Tradition", "Indoktrination", "Verlust am Ende. Ausspielen: Ziehe Karte.", "Menschen glauben (nicht), weil..."),
    1: ("Missionar", "Aufklärer", "Rate Karte. Zweifel: Freiwilliger Extrazug.", "Menschen glauben (nicht), weil..."),
    2: ("Beichtvater", "Psychologe", "Sieh Karte an. Zweifel: MUSS Karte ziehen.", "Menschen glauben (nicht), weil..."),
    3: ("Mystiker", "Logiker", "Vergleich. Zweifel: Sieg bei Gleichstand.", "Menschen glauben (nicht), weil..."),
    4: ("Eremit", "Stoiker", "Schutz vor Effekten.", "Menschen glauben (nicht), weil..."),
    5: ("Prediger", "Reformator", "Ablegen lassen. Zweifel: Zwei tauschen.", "Menschen glauben (nicht), weil..."),
    6: ("Prophet", "Agnostiker", "Tausch. Zweifel: Erst alle ansehen.", "Menschen glauben (nicht), weil..."),
    7: ("Wunder", "Zufall", "Abwurfzwang bei 8.", "Menschen glauben (nicht), weil..."),
    8: ("Gott", "Atheist", "Siegkarte.", "Menschen glauben (nicht), weil...")
}

def create_deck():
    counts = {0:1, 1:3, 2:3, 3:2, 4:2, 5:2, 6:1, 7:1, 8:1}
    deck = []
    for val, num in counts.items():
        for color in ["Blau", "Rot"]:
            for _ in range(num):
                name = CARD_DATA[val][0 if color=="Blau" else 1]
                deck.append({"val": val, "name": name, "color": color, "txt": CARD_DATA[val][3], "eff": CARD_DATA[val][2]})
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
        state = {"started": False, "players": {}, "order": [], "deck": [], "log": [], "turn_idx": 0, "phase": "LOBBY", "check_stack": []}
        save(state); st.rerun()
    st.stop()

# --- 4. LOBBY ---
if not state["started"]:
    if st.session_state.user not in state["players"] and len(state["players"]) < 5:
        if st.button("Mitspielen"):
            state["players"][st.session_state.user] = {"markers": 0, "active": True, "discard_stack": [], "hand": [], "protected": False}
            state["order"].append(st.session_state.user); save(state); st.rerun()
    st.write("Spieler:", ", ".join(state["order"]))
    if state["order"] and state["order"][0] == st.session_state.user and len(state["players"]) > 1:
        if st.button("SPIEL STARTEN"):
            state["started"] = True; state["deck"] = create_deck(); state["deck"].pop()
            for n in state["order"]: state["players"][n].update({"active": True, "hand": [state["deck"].pop()], "discard_stack": []})
            state["phase"] = "TEST"; save(state); st.rerun()
    st.stop()

# --- 5. SPIEL-INTERFACE ---
players = state["players"]
order = state["order"]
curr_p = order[state["turn_idx"]]
me = players[st.session_state.user]
alive = [p for p in order if players[p]["active"]]

st.title("⚖️ ZWEIFELSFALL")

# Anzeige der Mitspieler
cols = st.columns(len(order))
for i, name in enumerate(order):
    p_data = players[name]
    with cols[i]:
        st.markdown(f"**{name}** ({p_data['markers']}⚪)")
        if not p_data["active"]: st.error("Aus")
        elif p_data["protected"]: st.caption("🛡️ Schutz")
        if p_data["discard_stack"]:
            top = p_data["discard_stack"][-1]
            st.markdown(f"<div style='border:2px solid {'red' if top['color']=='Rot' else 'blue'}; padding:5px; border-radius:5px; font-size:0.7em;'>{top['name']}</div>", unsafe_allow_html=True)

# DEINE HANDKARTEN (Immer sichtbar)
st.divider()
st.subheader("Deine Hand")
h_cols = st.columns(5)
for i, h_card in enumerate(me["hand"]):
    with h_cols[i]:
        st.markdown(f"<div style='background: #222; padding: 10px; border-radius: 5px; border: 2px solid {'red' if h_card['color']=='Rot' else 'blue'};'><b>{h_card['name']}</b><br>Wert: {h_card['val']}</div>", unsafe_allow_html=True)

# --- DER ZUG ---
if curr_p == st.session_state.user and me["active"]:
    # PHASE 1: TEST
    if state["phase"] == "TEST":
        if me["discard_stack"] and me["discard_stack"][-1]["color"] == "Rot":
            st.warning("⚠️ Überzeugungstest nötig!")
            if st.button("Testkarte ziehen"):
                test_c = state["deck"].pop()
                state["check_stack"].append(test_c)
                state["log"].append(f"⚖️ {st.session_state.user} testet: {test_c['color']}")
                if test_c["color"] == "Rot" and not any(c['val'] == 8 and c['color'] == 'Rot' for c in me['hand']):
                    me["active"] = False
                    state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
                elif test_c["color"] == "Rot" and any(c['val'] == 8 and c['color'] == 'Rot' for c in me['hand']):
                    state["log"].append("🌟 Spezialsieg!")
                state["phase"] = "DRAW"; save(state); st.rerun()
        else:
            state["phase"] = "DRAW"; save(state); st.rerun()

    # PHASE 2: ZIEHEN & AUSSPIELEN
    elif state["phase"] == "DRAW":
        if len(me["hand"]) == 1 and st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop()); save(state); st.rerun()
        elif len(me["hand"]) == 2:
            st.write("Wähle eine Karte zum Ausspielen:")
            p_cols = st.columns(2)
            for i, c in enumerate(me["hand"]):
                with p_cols[i]:
                    st.write(f"**{c['name']}**")
                    if st.button("Wählen", key=f"p_{i}"):
                        played = me["hand"].pop(i)
                        me["discard_stack"].append(played)
                        me["protected"] = False
                        state["phase"] = "EFFECT"
                        save(state); st.rerun()

    # PHASE 3: EFFEKT
    elif state["phase"] == "EFFECT":
        played = me["discard_stack"][-1]
        is_doubt = played["color"] == "Rot"
        st.success(f"Bekenntnis: {played['txt']}")
        targets = [p for p in order if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]

        if played["val"] == 0:
            if st.button("Bonus-Karte ziehen"): 
                me["hand"].append(state["deck"].pop()); state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 1:
            target = st.selectbox("Ziel:", targets)
            guess = st.number_input("Karte raten (0-8):", 0, 8)
            if st.button("Raten"):
                if players[target]["hand"][0]["val"] == guess:
                    players[target]["active"] = False
                    state["log"].append(f"🎯 {target} wurde eliminiert!")
                if is_doubt: state["bonus_ready"] = True
                else: state["phase"] = "NEXT"
                save(state); st.rerun()
            if state.get("bonus_ready"):
                st.warning("Aufklärer-Bonus: Du darfst einen weiteren Zug machen!")
                if st.button("Zusatzzug starten"):
                    del state["bonus_ready"]; state["phase"] = "TEST"; save(state); st.rerun()
                if st.button("Verzichten"):
                    del state["bonus_ready"]; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 2:
            target = st.selectbox("Ansehen:", targets)
            if st.button("Ansehen"):
                state["peek_res"] = f"{target} hat: {players[target]['hand'][0]['name']} ({players[target]['hand'][0]['val']})"
                save(state); st.rerun()
            if "peek_res" in state:
                st.code(state["peek_res"])
                if is_doubt:
                    st.warning("Psychologen-Zwang: Ziehe eine Karte!")
                    if st.button("Karte ziehen"):
                        me["hand"].append(state["deck"].pop()); del state["peek_res"]; state["phase"] = "NEXT"; save(state); st.rerun()
                elif st.button("Zug beenden"):
                    del state["peek_res"]; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 3:
            target = st.selectbox("Vergleichen:", targets)
            if st.button("Vergleichen"):
                my_v, t_v = me["hand"][0]["val"], players[target]["hand"][0]["val"]
                if my_v > t_v: players[target]["active"] = False
                elif t_v > my_v: me["active"] = False
                elif is_doubt: players[target]["active"] = False; state["log"].append("Zweifel-Sieg bei Gleichstand!")
                state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 4:
            if st.button("Schutz aktivieren"): me["protected"] = True; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 5:
            if not is_doubt:
                target = st.selectbox("Ablegen lassen:", targets)
                if st.button("Bestätigen"): players[target]["hand"] = [state["deck"].pop()]; state["phase"] = "NEXT"; save(state); st.rerun()
            else:
                p1 = st.selectbox("Spieler 1:", order); p2 = st.selectbox("Spieler 2:", order)
                if st.button("Tauschen"):
                    players[p1]["hand"], players[p2]["hand"] = players[p2]["hand"], players[p1]["hand"]
                    state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 6:
            if is_doubt:
                if st.button("Alle Karten sehen"): state["all_see"] = True; save(state); st.rerun()
                if state.get("all_see"):
                    for p in targets: st.write(f"{p}: {players[p]['hand'][0]['val']}")
            target = st.selectbox("Tauschpartner:", targets)
            if st.button("Tauschen"):
                me["hand"], players[target]["hand"] = players[target]["hand"], me["hand"]
                if "all_see" in state: del state["all_see"]
                state["phase"] = "NEXT"; save(state); st.rerun()

        else:
            if st.button("Zug beenden"): state["phase"] = "NEXT"; save(state); st.rerun()

    # PHASE NEXT
    elif state["phase"] == "NEXT":
        state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
        state["phase"] = "TEST"; save(state); st.rerun()

# RUNDENAUSWERTUNG
if state["started"] and (len(alive) <= 1 or len(state["deck"]) == 0):
    if st.button("Runde auswerten"):
        # ... (Auswertungs-Logik wie zuvor)
        pass

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
