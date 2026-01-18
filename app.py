import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- DATENBANK & SETUP ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- KARTEN-DATEN (Mit allen Details aus dem PDF) ---
CARD_LIST = [
    (0, "Tradition", "Blau", "Wer sie am Ende hält, verliert. Ziehe neu.", "Glaube durch Bräuche."),
    (0, "Indoktrination", "Rot", "Wer sie am Ende hält, verliert. Ziehe neu.", "Spiritualität als Unvernunft."),
    (1, "Missionar", "Blau", "Rate Handkarte. Richtig? Er fliegt.", "Botschaft der Hoffnung."),
    (1, "Aufklärer", "Rot", "Rate Handkarte. (Zweifel: Danach noch ein Zug).", "Nur Beweisbares zählt."),
    (2, "Beichtvater", "Blau", "Sieh dir Handkarte an.", "Geständnis bringt Erleichterung."),
    (2, "Psychologe", "Rot", "Sieh dir Handkarte an. (Zweifel: Ziehe Karte).", "Religion als Projektion."),
    (3, "Mystiker", "Blau", "Vergleich: Niedrigerer Wert fliegt.", "Transzendente Realität spüren."),
    (3, "Logiker", "Rot", "Vergleich. (Zweifel: Sieg bei Gleichstand).", "Schöpfer unlogisch."),
    (4, "Eremit", "Blau", "Schutz bis zum nächsten Zug.", "Fokus auf das Wesentliche."),
    (4, "Stoiker", "Rot", "Schutz bis zum nächsten Zug.", "Welt objektiv akzeptieren."),
    (5, "Prediger", "Blau", "Spieler legt ab und zieht neu.", "Worte öffnen das Herz."),
    (5, "Reformator", "Rot", "Spieler legt ab. (Zweifel: Wähle zwei Spieler).", "Dogmenkritik."),
    (6, "Prophet", "Blau", "Tausche Karten mit Mitspieler.", "Visionen göttlicher Welt."),
    (6, "Agnostiker", "Rot", "Tausche Karten. (Zweifel: Erst Karten ansehen).", "Wahrheit unerreichbar."),
    (7, "Wunder/Zufall", "B/R", "Ablegen, wenn man die 8 hält.", "Wissenschaftliche Grenzen."),
    (8, "Präsenz/Atheist", "B/R", "Siegkarte. Darf nicht abgelegt werden.", "Vollkommenheit vs. Endlichkeit.")
]

def save(state): db.collection("games").document(st.session_state.gid).set(state)

# --- LOGIN ---
if "user" not in st.session_state:
    with st.form("login"):
        st.header("⚖️ Zweifelsfall")
        n, r = st.text_input("Name:"), st.text_input("Raum:")
        if st.form_submit_button("Beitreten"):
            st.session_state.user, st.session_state.gid = n.strip(), r.strip()
            st.rerun()
    st.stop()

st_autorefresh(interval=4000, key="sync")
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

if not state:
    if st.button("Neues Spiel starten"):
        deck = []
        for c in CARD_LIST: deck.extend([{"val":c[0],"name":c[1],"color":c[2],"eff":c[3],"txt":c[4]}] * 2)
        random.shuffle(deck)
        state = {"deck": deck, "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "protected": False}}, "turn": st.session_state.user, "log": []}
        save(state); st.rerun()
    st.stop()

players, me = state["players"], state["players"][st.session_state.user]
alive = [p for p in players if players[p]["active"]]

# --- GEWINNER ---
if len(alive) == 1 and len(players) > 1:
    st.balloons(); st.header(f"🏆 {alive[0]} hat gewonnen!"); 
    if st.button("Raum löschen"): doc_ref.delete(); st.rerun()
    st.stop()

st.title(f"Dran: {state['turn']}")

if me["active"]:
    # ZIEHEN
    if state["turn"] == st.session_state.user and len(me["hand"]) == 1:
        if st.button("Karte ziehen 🃏", use_container_width=True):
            me["hand"].append(state["deck"].pop()); me["protected"] = False
            save(state); st.rerun()

    # HANDKARTEN
    cols = st.columns(len(me["hand"]))
    for i, card in enumerate(me["hand"]):
        with cols[i]:
            st.markdown(f"<div style='border:2px solid gray; padding:10px; border-radius:10px;'><b>{card['name']} ({card['val']})</b></div>", unsafe_allow_html=True)
            if state["turn"] == st.session_state.user and len(me["hand"]) > 1:
                if card["val"] == 8: st.caption("Sperre: 8")
                elif st.button(f"Spielen", key=f"p_{i}"):
                    played = me["hand"].pop(i)
                    state["log"].append(f"📢 {st.session_state.user} spielt {played['name']}")
                    if played["val"] == 0: me["hand"].append(state["deck"].pop())
                    if played["val"] in [1, 2, 3, 5, 6]:
                        st.session_state.pending_action = played
                        save(state); st.rerun()
                    else:
                        if played["val"] == 4: me["protected"] = True
                        state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                        save(state); st.rerun()

    # --- ZWEIFELSFALL AKTIONEN ---
    if "pending_action" in st.session_state:
        card = st.session_state.pending_action
        st.divider()
        st.subheader(f"Effekt: {card['name']}")
        
        # Zweifel Checkbox (nur wenn Karte Rot ist oder PDF es vorsieht)
        nutze_zweifel = st.checkbox("Zweifelsfall-Regel nutzen? (Erweiterter Effekt)")
        
        targets = [p for p in players if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]
        if not targets:
            if st.button("Kein Ziel - Zug beenden"):
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                del st.session_state.pending_action; save(state); st.rerun()
        else:
            target = st.selectbox("Ziel wählen:", targets)
            
            if st.button("Aktion bestätigen"):
                # Logik mit Zweifel
                if card["val"] == 1: # Aufklärer
                    # Raten Logik hier (vereinfacht für Platz)
                    if nutze_zweifel: 
                        state["log"].append("⚖️ Zweifel! Zusatzug gewährt.")
                        # Turn bleibt bei mir
                    else:
                        state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                
                elif card["val"] == 2 and nutze_zweifel:
                    me["hand"].append(state["deck"].pop())
                    state["log"].append("⚖️ Zweifel! Psychologe zieht Karte.")
                    state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]

                elif card["val"] == 3: # Logiker
                    v1, v2 = me["hand"][0]["val"], players[target]["hand"][0]["val"]
                    if v1 > v2 or (v1 == v2 and nutze_zweifel):
                        players[target]["active"] = False
                        state["log"].append(f"⚖️ Sieg durch Logik!")
                    elif v2 > v1: me["active"] = False
                    state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]

                # Turn beenden und aufräumen
                del st.session_state.pending_action; save(state); st.rerun()

st.expander("Protokoll").write(state.get("log", []))
