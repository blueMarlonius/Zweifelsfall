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
if not state["started"]:
    p = state["players"]
    if st.session_state.user not in p:
        if st.button("Teilnehmen"):
            p[st.session_state.user] = {"markers": 0, "active": True, "discard_stack": [], "hand": [], "protected": False, "test_done": False}
            state["order"].append(st.session_state.user); save(state); st.rerun()
    if state["order"] and state["order"][0] == st.session_state.user:
        if st.button("🔀 Zufällige Reihenfolge"): random.shuffle(state["order"]); save(state); st.rerun()
        if st.button("✅ SPIEL STARTEN"):
            state.update({"started": True, "deck": create_deck(), "phase": "TEST"})
            for name in state["order"]:
                state["players"][name].update({"active": True, "hand": [state["deck"].pop()], "discard_stack": [], "protected": False, "test_done": False})
            save(state); st.rerun()
    st.stop()

# --- 5. GAMEPLAY ---
players = state["players"]
me = players[st.session_state.user]
curr_p = state["order"][state["turn_idx"]]

st.title("⚖️ ZWEIFELSFALL")

# Anzeige Mitspieler
cols = st.columns(len(state["order"]))
for i, name in enumerate(state["order"]):
    with cols[i]:
        st.write(f"**{name}**")
        if not players[name]["active"]: st.error("Aus")
        elif players[name]["protected"]: st.caption("🛡️")
        if players[name]["discard_stack"]:
            top = players[name]["discard_stack"][-1]
            st.markdown(f"<div style='border:1px solid {'red' if top['color']=='Rot' else 'blue'}; text-align:center;'>{top['name']}</div>", unsafe_allow_html=True)

# Eigene Hand
st.divider()
st.subheader("Deine Hand")
h_cols = st.columns(2)
for i, c in enumerate(me["hand"]):
    with h_cols[i]: st.info(f"{c['name']} ({c['val']})")

if curr_p == st.session_state.user and me["active"]:
    # PHASE 1: TEST
    if state["phase"] == "TEST":
        has_red = me["discard_stack"] and me["discard_stack"][-1]["color"] == "Rot"
        if has_red and not me["test_done"]:
            st.warning("Überzeugungstest nötig!")
            if st.button("Testen"):
                test_c = state["deck"].pop()
                state["log"].append(f"⚖️ {st.session_state.user} testet: {test_c['color']}")
                if test_c["color"] == "Rot" and not any(c['val']==8 and c['color']=='Rot' for c in me['hand']):
                    me["active"] = False; state["phase"] = "NEXT"
                else:
                    me["test_done"] = True; state["phase"] = "DRAW"
                save(state); st.rerun()
        else:
            me["test_done"] = True; state["phase"] = "DRAW"; save(state); st.rerun()

    # PHASE 2: DRAW
    elif state["phase"] == "DRAW":
        if len(me["hand"]) < 2 and st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop()); save(state); st.rerun()
        if len(me["hand"]) == 2:
            st.write("Karte ausspielen:")
            for i, c in enumerate(me["hand"]):
                if st.button(f"{c['name']} legen", key=f"lay{i}"):
                    me["discard_stack"].append(me["hand"].pop(i))
                    me["protected"] = False
                    state["phase"] = "EFFECT"
                    save(state); st.rerun()

    # PHASE 3: EFFECT (FIX: Strikte Trennung von Blau und Rot/Zweifel)
    elif state["phase"] == "EFFECT":
        played = me["discard_stack"][-1]
        is_red = played["color"] == "Rot"
        st.success(f"Effekt: {played['name']} ({played['color']})")
        targets = [p for p in state["order"] if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]

        # SPEZIALFALL: PSYCHOLOGE (Wert 2)
        if played["val"] == 2:
            if "peek_done" not in state:
                target = st.selectbox("Ziel wählen:", targets)
                if st.button("Ansehen"):
                    state["peek_data"] = f"{target} hält eine {players[target]['hand'][0]['val']}"
                    state["peek_done"] = True; save(state); st.rerun()
            else:
                st.code(state["peek_data"])
                # HIER IST DIE KORREKTUR:
                if is_red:
                    st.warning("ZWEIFEL: Du MUSST eine Karte ziehen.")
                    if st.button("Zieh-Pflicht erfüllen"):
                        me["hand"].append(state["deck"].pop())
                        del state["peek_done"], state["peek_data"]; state["phase"] = "NEXT"; save(state); st.rerun()
                else:
                    if st.button("Zug beenden (kein Zweifel)"):
                        del state["peek_done"], state["peek_data"]; state["phase"] = "NEXT"; save(state); st.rerun()

        # SPEZIALFALL: AUFKLÄRER (Wert 1)
        elif played["val"] == 1:
            if "guess_done" not in state:
                target = st.selectbox("Ziel wählen:", targets)
                guess = st.number_input("Karte raten (0-8):", 0, 8)
                if st.button("Raten"):
                    if players[target]["hand"][0]["val"] == guess:
                        players[target]["active"] = False
                        state["log"].append(f"🎯 {target} wurde von {st.session_state.user} erraten!")
                    state["guess_done"] = True; save(state); st.rerun()
            else:
                if is_red:
                    st.info("ZWEIFEL-BONUS: Du darfst einen weiteren Zug machen.")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Zusatzzug"):
                            del state["guess_done"]; state["phase"] = "TEST"; save(state); st.rerun()
                    with col2:
                        if st.button("Verzichten"):
                            del state["guess_done"]; state["phase"] = "NEXT"; save(state); st.rerun()
                else:
                    if st.button("Zug beenden"):
                        del state["guess_done"]; state["phase"] = "NEXT"; save(state); st.rerun()

        # Andere Effekte
        else:
            if st.button("Effekt ausgeführt / Zug beenden"):
                state["phase"] = "NEXT"; save(state); st.rerun()

    elif state["phase"] == "NEXT":
        me["test_done"] = False
        state["turn_idx"] = (state["turn_idx"] + 1) % len(state["order"])
        state["phase"] = "TEST"; save(state); st.rerun()

with st.expander("Log"):
    for l in reversed(state.get("log", [])): st.write(l)
