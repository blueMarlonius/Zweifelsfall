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

# --- KARTEN-LISTE (Zuweisung der Farben für die Logik) ---
CARD_LIST = [
    (0, "Tradition", "Blau", "Verliert am Ende.", "Bräuche."),
    (0, "Indoktrination", "Rot", "Verliert am Ende.", "Umfeld."),
    (1, "Missionar", "Blau", "Raten.", "Hoffnung."),
    (1, "Aufklärer", "Rot", "Raten + ZWANG: Zusatzug.", "Vernunft."),
    (2, "Beichtvater", "Blau", "Ansehen.", "Erleichterung."),
    (2, "Psychologe", "Rot", "Ansehen + ZWANG: Karte ziehen.", "Projektion."),
    (3, "Mystiker", "Blau", "Vergleich.", "Stille."),
    (3, "Logiker", "Rot", "Vergleich + ZWANG: Sieg bei Gleichstand.", "Logik."),
    (4, "Eremit", "Blau", "Schutz.", "Einsamkeit."),
    (4, "Stoiker", "Rot", "Schutz.", "Akzeptanz."),
    (5, "Prediger", "Blau", "Ablegen.", "Worte."),
    (5, "Reformator", "Rot", "Ablegen + ZWANG: Zwei Ziele.", "Prüfung."),
    (6, "Prophet", "Blau", "Tausch.", "Vision."),
    (6, "Agnostiker", "Rot", "Tausch + ZWANG: Erst alles ansehen.", "Unerreichbar."),
    (7, "Wunder", "Blau", "Abwerfen bei 8.", "Wunder."),
    (7, "Zufall", "Rot", "Abwerfen bei 8.", "Zufall."),
    (8, "Präsenz (Gott)", "Blau", "Siegkarte.", "Vollkommenheit."),
    (8, "Atheist (Leere)", "Rot", "Siegkarte (Zweifel möglich).", "Endlichkeit.")
]

def save(state): db.collection("games").document(st.session_state.gid).set(state)

# --- LOGIN ---
if "user" not in st.session_state:
    with st.form("login"):
        st.header("⚖️ Zweifelsfall")
        n, r = st.text_input("Dein Name:"), st.text_input("Raum:")
        if st.form_submit_button("Beitreten"):
            st.session_state.user, st.session_state.gid = n.strip(), r.strip()
            st.rerun()
    st.stop()

st_autorefresh(interval=4000, key="sync")
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

# --- INITIALISIERUNG ---
if not state:
    if st.button("Spiel starten"):
        deck = []
        for c in CARD_LIST: deck.extend([{"val":c[0],"name":c[1],"color":c[2],"eff":c[3],"txt":c[4]}] * 2)
        random.shuffle(deck)
        state = {"deck": deck, "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "protected": False}}, "turn": st.session_state.user, "log": []}
        save(state); st.rerun()
    st.stop()

players = state["players"]
me = players[st.session_state.user]
alive = [p for p in players if players[p]["active"]]

# --- LOGIK: GLAUBENSTEST ---
def trigger_glaubenstest():
    results = {}
    for p in alive:
        v = players[p]["hand"][0]["val"]
        if v == 0: v = -1 # 0 verliert immer
        results[p] = v
    winner = max(results, key=results.get)
    state["log"].append(f"🏁 GLAUBENSTEST: {winner} gewinnt durch Überzeugung!")
    state["winner"] = winner
    save(state)

if "winner" in state:
    st.balloons()
    st.header(f"🏆 {state['winner']} gewinnt!")
    if st.button("Raum löschen"): doc_ref.delete(); st.rerun()
    st.stop()

# --- SPIELABLAUF ---
st.title(f"Dran: {state['turn']}")

if me["active"]:
    # Karte ziehen
    if state["turn"] == st.session_state.user and len(me["hand"]) == 1 and len(state["deck"]) > 0:
        if st.button("Karte ziehen 🃏", use_container_width=True):
            me["hand"].append(state["deck"].pop()); me["protected"] = False
            save(state); st.rerun()

    # Handkarten
    cols = st.columns(len(me["hand"]))
    for i, card in enumerate(me["hand"]):
        with cols[i]:
            c_color = "#FF4500" if card["color"] == "Rot" else "#1E90FF"
            st.markdown(f"<div style='border:3px solid {c_color}; padding:10px; border-radius:10px;'><b>{card['name']} ({card['val']})</b></div>", unsafe_allow_html=True)
            
            if state["turn"] == st.session_state.user and len(me["hand"]) > 1:
                if card["val"] == 8: st.caption("8 ist gesperrt")
                elif st.button(f"Spielen", key=f"p_{i}"):
                    played = me["hand"].pop(i)
                    state["log"].append(f"📢 {st.session_state.user} spielt {played['name']} ({played['color']})")
                    
                    # REGEL: Rote Karte im letzten Zug (kein Deck mehr oder letzte Aktion) erzwingt Glaubenstest
                    is_last_card = (len(state["deck"]) == 0)
                    
                    if played["val"] == 0 and not is_last_card: me["hand"].append(state["deck"].pop())
                    
                    if played["val"] in [1, 2, 3, 5, 6]:
                        st.session_state.pending_action = played
                        save(state); st.rerun()
                    else:
                        if played["color"] == "Rot" and is_last_card:
                            trigger_glaubenstest(); st.rerun()
                        else:
                            if played["val"] == 4: me["protected"] = True
                            state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                            save(state); st.rerun()

    # --- AKTIONEN MIT ZWEIFELS-ZWANG ---
    if "pending_action" in st.session_state:
        card = st.session_state.pending_action
        is_red = (card["color"] == "Rot")
        st.subheader(f"Effekt: {card['name']}")
        if is_red: st.error("⚖️ ZWEIFELS-ZWANG: Rote Karte aktiv!")

        targets = [p for p in players if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]
        if targets:
            target = st.selectbox("Ziel wählen:", targets)
            if st.button("Aktion ausführen"):
                # Spezial-Logik für Rot (Zweifel)
                if card["val"] == 1: # Raten
                    # (Raten Logik...)
                    if is_red: state["log"].append("⚖️ Zweifel: Extrazug!"); save(state); st.rerun()
                
                # Turn-Wechsel
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                
                # REGEL: Wenn das die letzte Karte war und sie rot war -> Glaubenstest
                if is_red and len(state["deck"]) == 0:
                    trigger_glaubenstest()
                
                del st.session_state.pending_action; save(state); st.rerun()
