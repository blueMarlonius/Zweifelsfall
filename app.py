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

# --- 2. KARTEN-DEFINITION ---
CARD_DATA = {
    0: ("Tradition", "Indoktrination", "Verlust am Ende.", "Menschen glauben (nicht), weil..."),
    1: ("Missionar", "Aufklärer", "Karte raten.", "Menschen glauben (nicht), weil..."),
    2: ("Beichtvater", "Psychologe", "Karte ansehen.", "Menschen glauben (nicht), weil..."),
    3: ("Mystiker", "Logiker", "Vergleich (Niedriger fliegt).", "Menschen glauben (nicht), weil..."),
    4: ("Eremit", "Stoiker", "Schutz vor Effekten.", "Menschen glauben (nicht), weil..."),
    5: ("Prediger", "Reformator", "Karte ablegen lassen.", "Menschen glauben (nicht), weil..."),
    6: ("Prophet", "Agnostiker", "Karten tauschen.", "Menschen glauben (nicht), weil..."),
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

# --- 4. SPIEL-START & LOBBY ---
if not state:
    if st.button("Spielraum erstellen"):
        state = {"started": False, "players": {}, "order": [], "deck": [], "log": [], "turn_idx": 0, "phase": "LOBBY", "check_stack": []}
        save(state); st.rerun()
    st.stop()

if not state["started"]:
    p = state["players"]
    if st.session_state.user not in p and len(p) < 5:
        if st.button("Teilnehmen"):
            p[st.session_state.user] = {"markers": 0, "active": True, "discard_stack": [], "hand": [], "protected": False}
            state["order"].append(st.session_state.user)
            save(state); st.rerun()
    st.write("Warten auf Start...", ", ".join(state["order"]))
    if state["order"] and state["order"][0] == st.session_state.user and len(p) > 1:
        if st.button("STARTEN"):
            state["started"] = True
            deck = create_deck()
            state["buried"] = deck.pop()
            for name in state["order"]:
                state["players"][name].update({"active": True, "hand": [deck.pop()], "discard_stack": [], "protected": False})
            state["deck"] = deck; state["phase"] = "TEST"
            save(state); st.rerun()
    st.stop()

# --- 5. HAUPT-LOGIK ---
players = state["players"]
order = state["order"]
curr_p = order[state["turn_idx"]]
me = players[st.session_state.user]
alive = [p for p in order if players[p]["active"]]

st.title("⚖️ ZWEIFELSFALL")
cols = st.columns(len(order))
for i, name in enumerate(order):
    with cols[i]:
        st.write(f"**{name}** ({players[name]['markers']}⚪)")
        if not players[name]["active"]: st.error("Aus")
        elif players[name]["protected"]: st.caption("🛡️ Schutz")
        if players[name]["discard_stack"]:
            top = players[name]["discard_stack"][-1]
            st.markdown(f"<div style='border:2px solid {'red' if top['color']=='Rot' else 'blue'}; padding:5px; text-align:center;'>{top['name']} ({top['val']})</div>", unsafe_allow_html=True)

# --- PHASEN-ABLAUF ---
if curr_p == st.session_state.user and me["active"]:
    # PHASE 1: TEST [cite: 27, 28]
    if state["phase"] == "TEST":
        if me["discard_stack"] and me["discard_stack"][-1]["color"] == "Rot":
            if st.button("Überzeugungstest: Karte ziehen"):
                test_c = state["deck"].pop()
                state["check_stack"].append(test_c)
                if test_c["color"] == "Rot":
                    if any(c['val'] == 8 and c['color'] == 'Rot' for c in me['hand']): # Spezialsieg rote 8 
                        state["log"].append(f"🌟 Spezialsieg für {st.session_state.user}!")
                        # (Rundensieg-Logik hier...)
                    else:
                        me["active"] = False
                        state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
                state["phase"] = "DRAW"
                save(state); st.rerun()
        else:
            state["phase"] = "DRAW"; save(state); st.rerun()

    # PHASE 2: ZIEHEN & AUSSPIELEN [cite: 29, 31]
    if state["phase"] == "DRAW":
        if len(me["hand"]) == 1 and st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop())
            # Auto-Abwurf Karte 7 bei 8 im Besitz [cite: 7]
            vals = [c['val'] for c in me['hand']]
            if 7 in vals and 8 in vals:
                idx = next(i for i, c in enumerate(me["hand"]) if c['val'] == 7)
                me["discard_stack"].append(me["hand"].pop(idx))
                state["log"].append(f"⚠️ {st.session_state.user} musste die 7 ablegen.")
            save(state); st.rerun()
        if len(me["hand"]) == 2:
            st.subheader("Karte ausspielen")
            c1, c2 = st.columns(2)
            for i, c in enumerate(me["hand"]):
                with [c1, c2][i]:
                    if st.button(f"{c['name']} ({c['color']})", key=f"p{i}"):
                        me["discard_stack"].append(me["hand"].pop(i))
                        me["protected"] = False
                        state["phase"] = "EFFECT"
                        save(state); st.rerun()

    # PHASE 3: EFFEKT [cite: 33, 34]
    if state["phase"] == "EFFECT":
        played = me["discard_stack"][-1]
        is_doubt = played["color"] == "Rot"
        st.info(f"Bekenntnis: {played['txt']}")
        
        targets = [p for p in order if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]
        
        if played["val"] == 0: # Tradition/Indoktrination
            if st.button("Karte nachziehen"):
                me["hand"].append(state["deck"].pop())
                state["phase"] = "END"; save(state); st.rerun()
        
        elif played["val"] == 1: # Missionar/Aufklärer [cite: 1]
            target = st.selectbox("Ziel:", targets) if targets else None
            guess = st.number_input("Karte raten (0-8):", 0, 8)
            if st.button("Raten") and target:
                if players[target]["hand"][0]["val"] == guess:
                    players[target]["active"] = False
                    state["log"].append(f"🎯 {target} wurde erraten!")
                if is_doubt: st.warning("Bonus: Du darfst einen weiteren Zug machen (freiwillig)!")
                state["phase"] = "END"; save(state); st.rerun()
        
        elif played["val"] == 4: # Eremit/Stoiker [cite: 4]
            if st.button("Schutz aktivieren"):
                me["protected"] = True
                state["phase"] = "END"; save(state); st.rerun()
        
        # ... (Weitere Effekte 2, 3, 5, 6 entsprechend einfügen)
        
        if st.button("Zug beenden", key="end"):
            state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
            state["phase"] = "TEST"
            save(state); st.rerun()

# --- 6. RUNDENAUSWERTUNG [cite: 35-38] ---
if state["started"] and (len(alive) <= 1 or len(state["deck"]) == 0):
    st.divider()
    if st.button("ERGEBNIS ANZEIGEN"):
        # 1. 0er Check
        qualified = [p for p in alive if players[p]["hand"][0]["val"] != 0]
        if not qualified: winner = max(alive, key=lambda x: sum(c['val'] for c in players[x]['discard_stack']))
        else:
            # 2. Höchster Wert [cite: 13]
            max_val = max(players[p]["hand"][0]["val"] for p in qualified)
            winners = [p for p in qualified if players[p]["hand"][0]["val"] == max_val]
            # 3. Tie-Breaker: Summe Ablagestapel 
            winner = max(winners, key=lambda x: sum(c['val'] for c in players[x]['discard_stack']))
        
        players[winner]["markers"] += 1
        state["log"].append(f"🏆 {winner} gewinnt die Runde!")
        state["started"] = False # Pause bis zum Neustart
        save(state); st.rerun()

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
