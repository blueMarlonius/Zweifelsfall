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
    st.header(f"Lobby ({len(p_names)}/5)")
    for name in p_names: st.write(f"👤 {name}")
    if st.session_state.user not in state["players"] and len(p_names) < 5:
        if st.button("Beitreten"):
            state["players"][st.session_state.user] = {"markers": 0, "active": True, "discard_stack": [], "hand": [], "protected": False}
            state["order"].append(st.session_state.user); save(state); st.rerun()
    if p_names and p_names[0] == st.session_state.user:
        if st.button("Zufällige Reihenfolge"): random.shuffle(state["order"]); save(state); st.rerun()
        if st.button("SPIEL STARTEN"):
            state.update({"started": True, "deck": create_deck(), "phase": "TEST"})
            for n in state["order"]: state["players"][n].update({"active": True, "hand": [state["deck"].pop()], "discard_stack": []})
            save(state); st.rerun()
    st.stop()

# --- 5. GAMEPLAY ---
players = state["players"]
me = players[st.session_state.user]
curr_p = state["order"][state["turn_idx"]]

st.title("⚖️ ZWEIFELSFALL")

# --- WER IST IM ZWEIFEL? ---
# WICHTIG: Der Zweifel wird durch die Karte bestimmt, die VOR dem aktuellen Ausspielen dort lag.
was_in_doubt = False
if me["discard_stack"]:
    if me["discard_stack"][-1]["color"] == "Rot":
        was_in_doubt = True

if curr_p == st.session_state.user and me["active"]:
    # PHASE 1: TEST (Nur wenn Rot VORHER da lag)
    if state["phase"] == "TEST":
        if was_in_doubt:
            st.warning("⚠️ Du bist im Zweifelsfall! Überzeugungstest...")
            if st.button("Testkarte ziehen"):
                test_c = state["deck"].pop()
                state["log"].append(f"⚖️ {st.session_state.user} testet: {test_c['color']}")
                if test_c["color"] == "Rot":
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
            cols = st.columns(2)
            for i, c in enumerate(me["hand"]):
                with cols[i]:
                    st.write(f"**{c['name']}**")
                    if st.button("Ausspielen", key=f"l{i}"):
                        # Merken, ob man VOR dem Legen im Zweifel war
                        state["active_doubt"] = was_in_doubt 
                        me["discard_stack"].append(me["hand"].pop(i))
                        state["phase"] = "EFFECT"; save(state); st.rerun()

    # PHASE 3: EFFECT
    elif state["phase"] == "EFFECT":
        played = me["discard_stack"][-1]
        # Der Bonus/Zwang triggert NUR, wenn man SCHON im Zweifel WAR (active_doubt)
        # ODER (laut manchen Regeln) wenn die NEUE Karte rot ist. 
        # Ich programmiere es jetzt so: Zweifel = Die rote Karte liegt bereits vor dir.
        is_doubt_active = state.get("active_doubt", False)
        
        st.info(f"Karte: {played['name']} | Status: {'Zweifelsfall!' if is_doubt_active else 'Sicher'}")
        targets = [p for p in state["order"] if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]

        if played["val"] == 2: # Psychologe
            if "pk_d" not in state:
                target = st.selectbox("Ziel:", targets)
                if st.button("Ansehen"):
                    state["pk_v"] = f"{target} hat eine {players[target]['hand'][0]['val']}"
                    state["pk_d"] = True; save(state); st.rerun()
            else:
                st.code(state["pk_v"])
                # FIX: Nur wenn man im Zweifel WAR, kommt der Zwang
                if is_doubt_active:
                    st.warning("Zweifels-Zwang: Ziehe eine Karte!")
                    if st.button("Karte ziehen"):
                        me["hand"].append(state["deck"].pop())
                        del state["pk_d"], state["pk_v"]; state["phase"] = "NEXT"; save(state); st.rerun()
                else:
                    if st.button("Zug beenden"):
                        del state["pk_d"], state["pk_v"]; state["phase"] = "NEXT"; save(state); st.rerun()

        else:
            if st.button("Zug beenden"): state["phase"] = "NEXT"; save(state); st.rerun()

    elif state["phase"] == "NEXT":
        state["turn_idx"] = (state["turn_idx"] + 1) % len(state["order"])
        state["phase"] = "TEST"; save(state); st.rerun()
