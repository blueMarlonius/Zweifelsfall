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
        if st.button("Teilnehmen"):
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

# Anzeige der Mitspieler (Oben)
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

# DEINE HANDKARTEN (Immer sichtbar für dich)
st.divider()
st.subheader("Deine Hand")
h_cols = st.columns(5)
for i, h_card in enumerate(me["hand"]):
    with h_cols[i]:
        st.markdown(f"<div style='background: #222; padding: 10px; border-radius: 5px; border: 1px solid gray;'><b>{h_card['name']}</b><br>Wert: {h_card['val']}<br><small>{h_card['color']}</small></div>", unsafe_allow_html=True)

# --- DER ZUG ---
if curr_p == st.session_state.user and me["active"]:
    st.info(f"📍 Du bist am Zug (Phase: {state['phase']})")
    
    # PHASE 1: TEST
    if state["phase"] == "TEST":
        if me["discard_stack"] and me["discard_stack"][-1]["color"] == "Rot":
            st.warning("⚠️ Überzeugungstest nötig!")
            if st.button("Prüfkarte vom Nachziehstapel ziehen"):
                test_c = state["deck"].pop()
                state["check_stack"].append(test_c)
                state["log"].append(f"⚖️ {st.session_state.user} zieht {test_c['color']} im Test.")
                if test_c["color"] == "Rot":
                    if any(c['val'] == 8 and c['color'] == 'Rot' for c in me['hand']):
                        state["log"].append("🌟 Spezialsieg durch Rote 8!")
                    else:
                        me["active"] = False
                        state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
                state["phase"] = "DRAW"; save(state); st.rerun()
        else:
            state["phase"] = "DRAW"; save(state); st.rerun()

    # PHASE 2: ZIEHEN & AUSSPIELEN
    elif state["phase"] == "DRAW":
        if len(me["hand"]) == 1:
            if st.button("Karte ziehen 🃏"):
                me["hand"].append(state["deck"].pop()); save(state); st.rerun()
        elif len(me["hand"]) == 2:
            st.write("Wähle die Karte, die du auf deinen Ablagestapel legst:")
            p_cols = st.columns(2)
            for i, c in enumerate(me["hand"]):
                with p_cols[i]:
                    st.write(f"**{c['name']}**")
                    if st.button("Ausspielen", key=f"p_{i}"):
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
            if st.button("Sofort nachziehen"): me["hand"].append(state["deck"].pop()); state["phase"] = "NEXT"; save(state); st.rerun()
        
        elif played["val"] == 2: # Beichtvater / Psychologe Fix
            target = st.selectbox("Wessen Karte ansehen?", targets)
            if st.button("Ansehen"):
                state["peek_card"] = f"{target} hält: {players[target]['hand'][0]['name']} ({players[target]['hand'][0]['val']})"
                save(state); st.rerun()
            
            if "peek_card" in state:
                st.code(state["peek_card"])
                if is_doubt:
                    st.warning("Zweifel: Du MUSST zusätzlich eine Karte ziehen!")
                    if st.button("Bonus-Karte ziehen"):
                        me["hand"].append(state["deck"].pop())
                        del state["peek_card"]; state["phase"] = "NEXT"; save(state); st.rerun()
                elif st.button("Zug beenden"):
                    del state["peek_card"]; state["phase"] = "NEXT"; save(state); st.rerun()

        elif played["val"] == 4:
            if st.button("Schutz aktivieren"): me["protected"] = True; state["phase"] = "NEXT"; save(state); st.rerun()

        # Andere Effekte (vereinfacht)
        else:
            if st.button("Effekt erledigt - Zug beenden"): state["phase"] = "NEXT"; save(state); st.rerun()

    # PHASE NEXT
    elif state["phase"] == "NEXT":
        state["turn_idx"] = (state["turn_idx"] + 1) % len(order)
        state["phase"] = "TEST"; save(state); st.rerun()

with st.expander("Spielprotokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
