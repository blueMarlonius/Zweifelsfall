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

# --- 2. KARTEN-DEFINITIONEN (Texte & Effekte laut Anleitung) ---
CARD_DATA = {
    0: ("Tradition", "Indoktrination", "Verlust am Ende. Beim Ausspielen: Ziehe sofort eine Karte.", "Menschen glauben (nicht), weil..."),
    1: ("Missionar", "Aufklärer", "Rate die Karte eines Gegners. Zweifel: Freiwilliger Extrazug.", "Menschen glauben (nicht), weil..."),
    2: ("Beichtvater", "Psychologe", "Sieh dir eine Karte an. Zweifel: MUSS Karte ziehen.", "Menschen glauben (nicht), weil..."),
    3: ("Mystiker", "Logiker", "Vergleich (Niedriger fliegt). Zweifel: Sieg bei Gleichstand.", "Menschen glauben (nicht), weil..."),
    4: ("Eremit", "Stoiker", "Schutz vor Effekten bis zum nächsten Zug.", "Menschen glauben (nicht), weil..."),
    5: ("Prediger", "Reformator", "Spieler muss Karte ablegen. Zweifel: Zwei Spieler tauschen lassen.", "Menschen glauben (nicht), weil..."),
    6: ("Prophet", "Agnostiker", "Tausche Karten mit Mitspieler. Zweifel: Erst alle Karten ansehen.", "Menschen glauben (nicht), weil..."),
    7: ("Wunder", "Zufall", "Kein Effekt. Aber: Abwurfzwang bei 8.", "Menschen glauben (nicht), weil..."),
    8: ("Gott", "Atheist", "Siegkarte. Unantastbar.", "Menschen glauben (nicht), weil...")
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
        if st.button("JETZT STARTEN"):
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

# Anzeige der Spieler
cols = st.columns(len(order))
for i, name in enumerate(order):
    p_data = players[name]
    with cols[i]:
        st.markdown(f"**{name}** ({p_data['markers']}⚪)")
        if not p_data["active"]: st.error("Ausgeschieden")
        if p_data["discard_stack"]:
            top = p_data["discard_stack"][-1]
            c_color = "red" if top["color"] == "Rot" else "blue"
            st.markdown(f"<div style='border:2px solid {c_color}; padding:5px; font-size:0.8em; border-radius:5px;'>{top['name']} ({top['val']})</div>", unsafe_allow_html=True)

# --- DER ZUG ---
if curr_p == st.session_state.user and me["active"]:
    st.divider()
    
    # PHASE 1: TEST
    if state["phase"] == "TEST":
        if me["discard_stack"] and me["discard_stack"][-1]["color"] == "Rot":
            st.warning("Überzeugungstest erforderlich!")
            if st.button("Prüfkarte ziehen"):
                test_c = state["deck"].pop(); state["check_stack"].append(test_c)
                state["log"].append(f"⚖️ {st.session_state.user} testet: {test_c['color']}")
                if test_c["color"] == "Rot":
                    if any(c['val'] == 8 and c['color'] == 'Rot' for c in me['hand']):
                        state["log"].append("🌟 Spezialsieg durch Rote 8!"); state["winner_round"] = st.session_state.user
                    else:
                        me["active"] = False; state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
                state["phase"] = "DRAW"; save(state); st.rerun()
        else: state["phase"] = "DRAW"; save(state); st.rerun()

    # PHASE 2: ZIEHEN & AUSSPIELEN
    if state["phase"] == "DRAW":
        if len(me["hand"]) == 1 and st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop()); save(state); st.rerun()
        if len(me["hand"]) == 2:
            st.write("Wähle eine Karte zum Ausspielen:")
            c_cols = st.columns(2)
            for i, c in enumerate(me["hand"]):
                with c_cols[i]:
                    st.markdown(f"**{c['name']} ({c['val']})**\n\n*{c['eff']}*")
                    if st.button("Ausspielen", key=f"play_{i}"):
                        played = me["hand"].pop(i); me["discard_stack"].append(played); me["protected"] = False
                        state["log"].append(f"💬 {st.session_state.user} bekennt: {played['name']}")
                        state["phase"] = "EFFECT"; save(state); st.rerun()

    # PHASE 3: EFFEKTE (Hier passiert die Magie)
    if state["phase"] == "EFFECT":
        played = me["discard_stack"][-1]
        is_doubt = played["color"] == "Rot"
        st.subheader(f"Effekt: {played['name']}")
        st.write(f"Vorgelesen: *{played['txt']}*")
        
        targets = [p for p in order if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]

        if played["val"] == 0: # Tradition
            if st.button("Bonus-Karte ziehen"):
                me["hand"].append(state["deck"].pop()); state["phase"] = "NEXT"; save(state); st.rerun()
        
        elif played["val"] == 1: # Missionar / Aufklärer
            target = st.selectbox("Ziel wählen:", targets)
            guess = st.number_input("Karte raten (0-8):", 0, 8)
            if st.button("Raten"):
                if players[target]["hand"][0]["val"] == guess:
                    players[target]["active"] = False; state["log"].append(f"🎯 {target} wurde eliminiert!")
                state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 2: # Beichtvater / Psychologe
            target = st.selectbox("Wessen Karte ansehen?", targets)
            if st.button("Karte ansehen"):
                st.write(f"{target} hält: {players[target]['hand'][0]['name']} ({players[target]['hand'][0]['val']})")
                if is_doubt: 
                    st.warning("Zweifels-Bonus: Du musst eine Karte nachziehen!")
                    if st.button("Zwanghaft ziehen"): me["hand"].append(state["deck"].pop()); state["phase"] = "NEXT"; save(state); st.rerun()
                else:
                    if st.button("Zug beenden"): state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 3: # Mystiker / Logiker
            target = st.selectbox("Mit wem vergleichen?", targets)
            if st.button("Vergleichen"):
                my_val = me["hand"][0]["val"]; target_val = players[target]["hand"][0]["val"]
                if my_val > target_val: players[target]["active"] = False
                elif target_val > my_val: me["active"] = False
                elif is_doubt: st.success("Gleichstand! Dank Zweifel gewinnst du."); players[target]["active"] = False
                state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 4: # Eremit
            if st.button("Schutz aktivieren"):
                me["protected"] = True; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 5: # Prediger / Reformator
            if not is_doubt:
                target = st.selectbox("Wer muss ablegen?", targets)
                if st.button("Ablegen lassen"):
                    players[target]["hand"] = [state["deck"].pop()]; state["phase"] = "NEXT"; save(state); st.rerun()
            else: # Reformator Bonus: Tausch zweier Spieler
                p1 = st.selectbox("Spieler 1:", order); p2 = st.selectbox("Spieler 2:", order)
                if st.button("Tauschen lassen"):
                    players[p1]["hand"], players[p2]["hand"] = players[p2]["hand"], players[p1]["hand"]
                    state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 6: # Prophet / Agnostiker
            if is_doubt:
                if st.button("Alle Handkarten ansehen"):
                    for p in targets: st.write(f"{p}: {players[p]['hand'][0]['name']}")
            target = st.selectbox("Tauschpartner:", targets)
            if st.button("Karten tauschen"):
                me["hand"], players[target]["hand"] = players[target]["hand"], me["hand"]
                state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] in [7, 8]:
            if st.button("Zug beenden"): state["phase"] = "NEXT"; save(state); st.rerun()

    # PHASE NEXT: ZUGABSCHLUSS
    if state["phase"] == "NEXT":
        state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
        state["phase"] = "TEST"; save(state); st.rerun()

# --- 6. RUNDEN-AUSWERTUNG ---
if state["started"] and (len(alive) <= 1 or len(state["deck"]) == 0):
    st.divider()
    if st.button("Runde auswerten & Sinnmarker vergeben"):
        # Gewinner-Ermittlung nach Anleitung
        qualified = [p for p in alive if players[p]["hand"][0]["val"] != 0]
        if not qualified: winner = max(alive, key=lambda x: sum(c['val'] for c in players[x]['discard_stack']))
        else:
            max_val = max(players[p]["hand"][0]["val"] for p in qualified)
            winners = [p for p in qualified if players[p]["hand"][0]["val"] == max_val]
            winner = max(winners, key=lambda x: sum(c['val'] for c in players[x]['discard_stack']))
        
        players[winner]["markers"] += 1
        state["started"] = False; state["log"].append(f"🏆 {winner} gewinnt die Runde!"); save(state); st.rerun()

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
