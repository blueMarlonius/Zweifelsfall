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
        state = {"started": False, "players": {}, "order": [], "deck": [], "log": [], "turn_idx": 0, "phase": "LOBBY"}
        save(state); st.rerun()
    st.stop()

# --- 4. LOBBY ---
if not state["started"]:
    p = state["players"]
    if st.session_state.user not in p and len(p) < 5:
        if st.button("Teilnehmen"):
            p[st.session_state.user] = {"markers": 0, "active": True, "discard_stack": [], "hand": [], "protected": False}
            state["order"].append(st.session_state.user); save(state); st.rerun()
    
    st.write("Wartende Spieler:", ", ".join(state["order"]))
    
    if state["order"] and state["order"][0] == st.session_state.user:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔀 Zufällige Reihenfolge"):
                random.shuffle(state["order"]); save(state); st.rerun()
        with col2:
            if st.button("✅ SPIEL STARTEN"):
                state["started"] = True; state["deck"] = create_deck(); state["deck"].pop()
                for name in state["order"]:
                    state["players"][name].update({"active": True, "hand": [state["deck"].pop()], "discard_stack": [], "protected": False})
                state["phase"] = "TEST"; save(state); st.rerun()
    st.stop()

# --- 5. SPIEL-INTERFACE ---
players = state["players"]
order = state["order"]
curr_p = order[state["turn_idx"]]
me = players[st.session_state.user]
alive = [p_name for p_name in order if players[p_name]["active"]]

st.title("⚖️ ZWEIFELSFALL")

# Spieleranzeige
cols = st.columns(len(order))
for i, name in enumerate(order):
    p_data = players[name]
    with cols[i]:
        st.markdown(f"**{name}** ({p_data['markers']}⚪)")
        if not p_data["active"]: st.error("Ausgeschieden")
        elif p_data["protected"]: st.caption("🛡️ Geschützt")
        if p_data["discard_stack"]:
            top = p_data["discard_stack"][-1]
            st.markdown(f"<div style='border:2px solid {'red' if top['color']=='Rot' else 'blue'}; padding:5px; border-radius:5px; font-size:0.75em;'>{top['name']}</div>", unsafe_allow_html=True)

st.divider()
st.subheader("Deine Hand")
h_cols = st.columns(5)
for i, h_card in enumerate(me["hand"]):
    with h_cols[i]:
        st.markdown(f"<div style='background: #333; padding: 10px; border-radius: 5px; border: 2px solid {'red' if h_card['color']=='Rot' else 'blue'};'><b>{h_card['name']}</b> ({h_card['val']})</div>", unsafe_allow_html=True)

# --- DER ZUG ---
if curr_p == st.session_state.user and me["active"]:
    # PHASE 1: TEST
    if state["phase"] == "TEST":
        has_red = me["discard_stack"] and me["discard_stack"][-1]["color"] == "Rot"
        if has_red:
            st.warning("⚠️ Überzeugungstest nötig!")
            if st.button("Testkarte ziehen"):
                test_c = state["deck"].pop()
                state["log"].append(f"⚖️ {st.session_state.user} zieht {test_c['color']} im Test.")
                if test_c["color"] == "Rot" and not any(c['val'] == 8 and c['color'] == 'Rot' for c in me['hand']):
                    me["active"] = False; state["phase"] = "NEXT"
                else:
                    state["phase"] = "DRAW"
                save(state); st.rerun()
        else: state["phase"] = "DRAW"; save(state); st.rerun()

    # PHASE 2: ZIEHEN & AUSSPIELEN
    elif state["phase"] == "DRAW":
        if len(me["hand"]) == 1 and st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop()); save(state); st.rerun()
        elif len(me["hand"]) == 2:
            st.write("Karte wählen:")
            p_cols = st.columns(2)
            for i, c in enumerate(me["hand"]):
                with p_cols[i]:
                    st.write(f"**{c['name']}**")
                    if st.button("Ausspielen", key=f"play_{i}"):
                        played = me["hand"].pop(i); me["discard_stack"].append(played)
                        me["protected"] = False; state["phase"] = "EFFECT"; save(state); st.rerun()

    # PHASE 3: EFFEKTE (ALLE KARTEN FIXIERT)
    elif state["phase"] == "EFFECT":
        played = me["discard_stack"][-1]
        is_doubt = played["color"] == "Rot"
        st.success(f"Bekenntnis: {played['txt']}")
        
        # Mögliche Ziele (nicht man selbst, aktiv, nicht geschützt)
        targets = [p for p in order if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]

        if played["val"] == 0:
            if st.button("Sofort nachziehen"):
                me["hand"].append(state["deck"].pop()); state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 1:
            target = st.selectbox("Ziel wählen:", targets) if targets else None
            guess = st.number_input("Karte raten (0-8):", 0, 8)
            if st.button("Bestätigen") and target:
                if players[target]["hand"][0]["val"] == guess:
                    players[target]["active"] = False; state["log"].append(f"🎯 {target} eliminiert!")
                if is_doubt: state["bonus"] = True
                else: state["phase"] = "NEXT"
                save(state); st.rerun()
            if state.get("bonus"):
                st.info("Bonus-Zug möglich!")
                if st.button("Zusatzzug"): del state["bonus"]; state["phase"] = "TEST"; save(state); st.rerun()
                if st.button("Verzichten"): del state["bonus"]; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 2: # Psychologe
            target = st.selectbox("Ansehen:", targets) if targets else None
            if st.button("Karte sehen") and target:
                state["peek"] = f"{target} hält: {players[target]['hand'][0]['name']} ({players[target]['hand'][0]['val']})"
                save(state); st.rerun()
            if "peek" in state:
                st.code(state["peek"])
                if is_doubt:
                    if st.button("Bonus-Karte ziehen"):
                        me["hand"].append(state["deck"].pop()); del state["peek"]; state["phase"] = "NEXT"; save(state); st.rerun()
                elif st.button("Zug beenden"):
                    del state["peek"]; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 3: # Mystiker
            target = st.selectbox("Vergleichen:", targets) if targets else None
            if st.button("Vergleichen") and target:
                my_v = max(c['val'] for c in me["hand"])
                t_v = max(c['val'] for c in players[target]["hand"])
                if my_v > t_v: players[target]["active"] = False
                elif t_v > my_v: me["active"] = False
                elif is_doubt: players[target]["active"] = False
                state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 4: # Eremit
            if st.button("Schutz aktivieren"):
                me["protected"] = True; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 5: # Prediger
            if not is_doubt:
                target = st.selectbox("Karte ablegen lassen:", targets) if targets else None
                if st.button("Ausführen") and target:
                    players[target]["hand"] = [state["deck"].pop()]; state["phase"] = "NEXT"; save(state); st.rerun()
            else:
                p1 = st.selectbox("Spieler 1:", order); p2 = st.selectbox("Spieler 2:", order)
                if st.button("Hände tauschen"):
                    players[p1]["hand"], players[p2]["hand"] = players[p2]["hand"], players[p1]["hand"]
                    state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 6: # Prophet
            if is_doubt:
                if st.button("Alle Karten sehen"): state["see_all"] = True; save(state); st.rerun()
                if state.get("see_all"):
                    for p in targets: st.write(f"{p}: {players[p]['hand'][0]['val']}")
            target = st.selectbox("Tauschpartner:", targets) if targets else None
            if st.button("Karte tauschen") and target:
                me["hand"], players[target]["hand"] = players[target]["hand"], me["hand"]
                if "see_all" in state: del state["see_all"]
                state["phase"] = "NEXT"; save(state); st.rerun()

        else:
            if st.button("Zug beenden"): state["phase"] = "NEXT"; save(state); st.rerun()

    # PHASE NEXT
    elif state["phase"] == "NEXT":
        state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
        state["phase"] = "TEST"; save(state); st.rerun()

# --- 6. RUNDENAUSWERTUNG ---
if state["started"] and (len(alive) <= 1 or len(state["deck"]) == 0):
    if st.button("Ergebnis auswerten"):
        qualified = [p for p in alive if players[p]["hand"][0]["val"] != 0]
        if not qualified: winner = max(alive, key=lambda x: sum(c['val'] for c in players[x]['discard_stack']))
        else:
            max_v = max(players[p]["hand"][0]["val"] for p in qualified)
            ws = [p for p in qualified if players[p]["hand"][0]["val"] == max_v]
            winner = max(ws, key=lambda x: sum(c['val'] for c in players[x]['discard_stack']))
        players[winner]["markers"] += 1
        state["started"] = False; save(state); st.rerun()

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
