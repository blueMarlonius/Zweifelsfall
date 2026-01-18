import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- DB SETUP ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- KARTEN-DATEN ---
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

def save(s): db.collection("games").document(st.session_state.gid).set(s)

# --- LOGIN ---
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

# --- INITIALISIERUNG ---
if not state:
    if st.button("Spielraum eröffnen"):
        deck = []
        for c in CARD_LIST: deck.extend([{"val":c[0],"name":c[1],"color":c[2],"eff":c[3],"txt":c[4]}] * 2)
        random.shuffle(deck)
        state = {"deck": deck, "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "in_test": False}}, "turn": st.session_state.user, "log": [], "started": False, "pending": None}
        save(state); st.rerun()
    st.stop()

players = state.get("players", {})
if st.session_state.user not in players:
    if st.button("Mitspielen"):
        state["players"][st.session_state.user] = {"hand": [state["deck"].pop()], "active": True, "in_test": False}
        save(state); st.rerun()
    st.stop()

# --- LOBBY & SIEG ---
alive = [p for p in players if players[p].get("active")]
if not state.get("started"):
    st.info(f"Warten auf Spieler... ({len(players)})")
    if len(players) > 1 and st.button("JETZT STARTEN"):
        state["started"] = True; save(state); st.rerun()
    st.stop()

if len(alive) == 1:
    st.balloons(); st.header(f"🏆 {alive[0]} gewinnt!"); 
    if st.button("Spiel beenden"): doc_ref.delete(); st.rerun()
    st.stop()

me = players.get(st.session_state.user)

# --- DER SPIELZUG ---
st.title(f"Dran: {state.get('turn')}")

if me.get("active"):
    # PHASE 1: GLAUBENSTEST (Tritt erst zu Beginn des nächsten eigenen Zugs ein)
    if state.get("turn") == st.session_state.user and me.get("in_test"):
        st.error("🚨 DEIN NÄCHSTER ZUG: GLAUBENSTEST!")
        st.write("Du hast in deinem letzten Zug eine rote Karte gelegt. Jetzt entscheidet das Schicksal.")
        if st.button("Prüfung ablegen (Karte ziehen)", use_container_width=True):
            test_card = state["deck"].pop()
            state["log"].append(f"⚖️ Test für {st.session_state.user}: {test_card['color']} gezogen.")
            if test_card["color"] == "Rot":
                me["active"] = False
                state["log"].append(f"💀 {st.session_state.user} ist am Zweifel gescheitert.")
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
            else:
                st.success("Überstanden! Du darfst deinen Zug machen.")
                me["in_test"] = False
            save(state); st.rerun()
        st.stop() # Verhindert Ziehen/Spielen während des Tests

    # PHASE 2: NORMALER ZUG (Ziehen)
    if state.get("turn") == st.session_state.user and len(me.get("hand", [])) == 1 and not state.get("pending"):
        if st.button("Karte ziehen 🃏", use_container_width=True):
            me["hand"].append(state["deck"].pop()); save(state); st.rerun()

    # PHASE 3: KARTEN ANZEIGEN & SPIELEN
    cols = st.columns(len(me.get("hand", [])))
    for i, c in enumerate(me.get("hand", [])):
        with cols[i]:
            color = "#FF4500" if c["color"] == "Rot" else "#1E90FF"
            st.markdown(f"<div style='border:3px solid {color}; padding:10px; border-radius:10px; background:#111; min-height:220px;'><b>{c['name']} ({c['val']})</b><br><small>{c['eff']}</small><br><br><i style='font-size:0.8em; color:gray;'>{c['txt']}</i></div>", unsafe_allow_html=True)
            
            if state.get("turn") == st.session_state.user and len(me["hand"]) > 1 and not state.get("pending"):
                if c["val"] != 8 and st.button("Spielen", key=f"p_{i}", use_container_width=True):
                    played = me["hand"].pop(i)
                    state["log"].append(f"📢 {st.session_state.user} spielt {played['name']}")
                    # Markierung für den NÄCHSTEN ZUG setzen
                    if played["color"] == "Rot": me["in_test"] = True
                    
                    if played["val"] in [1,2,3,5,6]: state["pending"] = played
                    else: state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                    save(state); st.rerun()

    # PHASE 4: EFFEKTE
    if state.get("pending") and state.get("turn") == st.session_state.user:
        card = state["pending"]
        targets = [p for p in players if p != st.session_state.user and players[p].get("active")]
        if targets:
            target = st.selectbox("Ziel wählen:", targets)
            if st.button("Effekt ausführen"):
                if card["color"] == "Rot" and card["val"] == 1:
                    state["log"].append("⚖️ Aufklärer-Zweifel: Extrazug!")
                else:
                    state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                state["pending"] = None
                save(state); st.rerun()

with st.expander("Spielprotokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
