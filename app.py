import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- 1. DATENBANK VERBINDUNG ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- 2. KARTEN-DEFINITION ---
CARD_LIST = [
    (0, "Tradition", "Blau", "Verliert am Ende. Ziehe neu.", "Bräuche der Vorfahren."),
    (0, "Indoktrination", "Rot", "Verliert am Ende. Ziehe neu.", "Spiritualität als Unvernunft."),
    (1, "Missionar", "Blau", "Handkarte raten.", "Frohe Botschaft."),
    (1, "Aufklärer", "Rot", "Raten. ZWANG: Zusatzug.", "Nur Beweisbares zählt."),
    (2, "Beichtvater", "Blau", "Karte ansehen.", "Geständnis hilft."),
    (2, "Psychologe", "Rot", "Ansehen. ZWANG: Ziehe Karte.", "Projektion von Wünschen."),
    (3, "Mystiker", "Blau", "Vergleich: Niedriger fliegt.", "Transzendenz spüren."),
    (3, "Logiker", "Rot", "Vergleich. ZWANG: Sieg bei Gleichstand.", "Logik schlägt Chaos."),
    (4, "Eremit", "Blau", "Schutz.", "Fokus auf Wesentliches."),
    (4, "Stoiker", "Rot", "Schutz.", "Welt akzeptieren."),
    (5, "Prediger", "Blau", "Ablegen lassen.", "Worte öffnen Herzen."),
    (5, "Reformator", "Rot", "Ablegen. ZWANG: Zwei Ziele.", "Prüfung der Dogmen."),
    (6, "Prophet", "Blau", "Tausch.", "Gerechtere Welt."),
    (6, "Agnostiker", "Rot", "Tausch. ZWANG: Erst ansehen.", "Wahrheit unerreichbar."),
    (7, "Wunder/Zufall", "B/R", "Abwerfen bei 8.", "Grenzen der Wissenschaft."),
    (8, "Präsenz/Atheist", "B/R", "Siegkarte. Unantastbar.", "Vollkommenheit vs. Endlichkeit.")
]

# --- 3. HILFSFUNKTIONEN ---
def save(s): db.collection("games").document(st.session_state.gid).set(s)

# --- 4. LOGIN ---
if "user" not in st.session_state:
    with st.form("login"):
        st.header("⚖️ Zweifelsfall")
        n, r = st.text_input("Name:"), st.text_input("Raum:")
        if st.form_submit_button("Beitreten"):
            st.session_state.user, st.session_state.gid = n.strip(), r.strip()
            st.rerun()
    st.stop()

st_autorefresh(interval=3000, key="sync")
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

# --- 5. INITIALISIERUNG ---
if not state:
    if st.button("Spielraum eröffnen"):
        deck = []
        for c in CARD_LIST: deck.extend([{"val":c[0],"name":c[1],"color":c[2],"eff":c[3],"txt":c[4]}] * 2)
        random.shuffle(deck)
        state = {"deck": deck, "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "in_test": False}}, "turn": st.session_state.user, "log": [], "started": False, "pending": None}
        save(state); st.rerun()
    st.stop()

players = state["players"]
if st.session_state.user not in players:
    if st.button("Mitspielen"):
        state["players"][st.session_state.user] = {"hand": [state["deck"].pop()], "active": True, "in_test": False}
        save(state); st.rerun()
    st.stop()

# --- 6. SPIELSTART & SIEG ---
alive = [p for p in players if players[p]["active"]]
if not state["started"]:
    st.info(f"Warten auf Spieler... ({len(players)})")
    if len(players) > 1 and st.button("JETZT STARTEN"):
        state["started"] = True; save(state); st.rerun()
    st.stop()

if len(alive) == 1:
    st.balloons(); st.header(f"🏆 {alive[0]} gewinnt!"); st.button("Reset", on_click=lambda: doc_ref.delete()); st.stop()

# --- 7. DER SPIELZUG ---
me = players[st.session_state.user]
st.subheader(f"Spieler: {st.session_state.user} | Dran: {state['turn']}")

if me["active"]:
    # A: GLAUBENSTEST
    if state["turn"] == st.session_state.user and me["in_test"]:
        st.error("⚖️ GLAUBENSTEST: Ziehe eine Schicksalskarte!")
        if st.button("Prüfung ablegen"):
            card = state["deck"].pop()
            state["log"].append(f"⚖️ {st.session_state.user} zieht {card['color']}.")
            if card["color"] == "Rot":
                me["active"] = False
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
            me["in_test"] = False
            save(state); st.rerun()
        st.stop()

    # B: KARTE ZIEHEN
    if state["turn"] == st.session_state.user and len(me["hand"]) == 1 and not state["pending"]:
        if st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop()); save(state); st.rerun()

    # C: KARTEN ANZEIGEN & SPIELEN
    cols = st.columns(len(me["hand"]))
    for i, c in enumerate(me["hand"]):
        with cols[i]:
            color = "#FF4500" if c["color"] == "Rot" else "#1E90FF"
            st.markdown(f"<div style='border:3px solid {color}; padding:10px; border-radius:10px;'><h4>{c['name']} ({c['val']})</h4><p><small>{c['eff']}</small></p><i><small>{c['txt']}</small></i></div>", unsafe_allow_html=True)
            if state["turn"] == st.session_state.user and len(me["hand"]) > 1 and not state["pending"]:
                if c["val"] != 8 and st.button("Spielen", key=f"play_{i}"):
                    played = me["hand"].pop(i)
                    state["log"].append(f"{st.session_state.user} spielt {played['name']}")
                    if played["color"] == "Rot": me["in_test"] = True
                    if played["val"] in [1,2,3,5,6]: state["pending"] = played
                    else: state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                    save(state); st.rerun()

    # D: EFFEKT BESTÄTIGEN
    if state["pending"] and state["turn"] == st.session_state.user:
        card = state["pending"]
        st.divider()
        st.write(f"Effekt von **{card['name']}**")
        targets = [p for p in players if p != st.session_state.user and players[p]["active"]]
        if targets:
            target = st.selectbox("Ziel wählen:", targets)
            if st.button("Aktion Bestätigen"):
                # Hier Logik für Aufklärer (1) - Roter Zwang zum Extrazug
                if card["color"] == "Rot" and card["val"] == 1:
                    state["log"].append("⚖️ Zweifel-Zwang: Extrazug!")
                else:
                    state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                state["pending"] = None
                save(state); st.rerun()

st.expander("Protokoll").write(state["log"])
