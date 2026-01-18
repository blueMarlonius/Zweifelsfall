import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account

# --- DATENBANK VERBINDUNG ---
if "db" not in st.session_state:
    if "textkey" not in st.secrets:
        st.error("❌ 'textkey' nicht in Secrets gefunden.")
        st.stop()
    
    try:
        key_info = dict(st.secrets["textkey"])
        
        # REPARATUR DES KEYS: Wichtig für den b64decode Fehler!
        if "private_key" in key_info:
            key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
            
        creds = service_account.Credentials.from_service_account_info(key_info)
        st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
    except Exception as e:
        st.error(f"❌ Fehler bei der Key-Verarbeitung: {e}")
        st.stop()

db = st.session_state.db

# --- SPIEL-DATEN (32 Karten laut Anleitung) ---
def build_deck():
    # val, name, color, effect
    base_cards = [
        (0, "Tradition", "Blau", "Wer sie am Ende hält, verliert."),
        (1, "Missionar", "Blau", "Rate Handkarte eines Gegners."),
        (2, "Beichtvater", "Blau", "Sieh dir eine Handkarte an."),
        (3, "Richter", "Rot", "Vergleiche Handkarten."),
        (4, "Eremit", "Blau", "Schutz bis zum nächsten Zug."),
        (5, "Abt", "Rot", "Gegner muss Karte ablegen."),
        (6, "Vision", "Rot", "Tausche Karte mit Mitspieler."),
        (7, "Wunder", "Blau", "Ablegen, wenn man die 8 hält."),
        (8, "Gott", "Blau", "Wer sie am Ende hält, gewinnt.")
    ]
    deck = []
    for c in base_cards:
        # Wir füllen auf ca. 32 Karten auf
        count = 4 if c[0] == 1 else 3 
        for _ in range(count):
            deck.append({"val": c[0], "name": c[1], "color": c[2], "text": c[3]})
    random.shuffle(deck)
    return deck

# --- HILFSFUNKTIONEN ---
def get_state(gid):
    doc = db.collection("games").document(gid).get()
    return doc.to_dict()

def save_state(gid, state):
    db.collection("games").document(gid).set(state)

# --- APP OBERFLÄCHE ---
st.set_page_config(page_title="Zweifelsfall Multiplayer", page_icon="⚖️")
st.title("⚖️ Zweifelsfall")

if "user" not in st.session_state:
    st.session_state.user = st.text_input("Dein Name:").strip()
    st.session_state.gid = st.text_input("Spiel-Raum Name:").strip()
    if st.button("Beitreten"):
        if st.session_state.user and st.session_state.gid:
            st.rerun()
else:
    gid = st.session_state.gid
    state = get_state(gid)

    if not state:
        if st.button("Neues Spiel starten"):
            deck = build_deck()
            state = {
                "deck": deck,
                "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "played": None}},
                "turn": st.session_state.user,
                "log": [f"Spiel von {st.session_state.user} gestartet."]
            }
            save_state(gid, state)
            st.rerun()
    else:
        players = state["players"]
        if st.session_state.user not in players:
            if st.button("Mitspielen"):
                state["players"][st.session_state.user] = {"hand": [state["deck"].pop()], "active": True, "played": None}
                save_state(gid, state)
                st.rerun()

        me = players[st.session_state.user]
        
        # Spielanzeige
        st.sidebar.write(f"Raum: **{gid}**")
        st.sidebar.write(f"Dran: **{state['turn']}**")
        
        if me["active"]:
            # SCHRITT 1: Überzeugungstest
            if me["played"] and me["played"]["color"] == "Rot":
                st.warning("Prüfe deine Überzeugung (Zweifelsfall)!")
                if st.button("Test-Karte ziehen"):
                    test = state["deck"].pop()
                    state["log"].append(f"{st.session_state.user} testet: {test['name']} ({test['color']})")
                    if test["color"] == "Rot":
                        me["active"] = False
                        state["log"].append(f"💀 {st.session_state.user} ist ausgeschieden!")
                        # Nächster Spieler
                        alive = [p for p in players if players[p]["active"]]
                        state["turn"] = alive[0] if alive else ""
                    save_state(gid, state)
                    st.rerun()
            
            # SCHRITT 2: Normaler Zug
            elif state["turn"] == st.session_state.user:
                if len(me["hand"]) < 2:
                    if st.button("Karte ziehen"):
                        me["hand"].append(state["deck"].pop())
                        save_state(gid, state)
                        st.rerun()
                else:
                    cols = st.columns(2)
                    for i, card in enumerate(me["hand"]):
                        if cols[i].button(f"{card['name']} ({card['color']})"):
                            played = me["hand"].pop(i)
                            me["played"] = played
                            state["log"].append(f"📢 {st.session_state.user} bekennt: {played['name']}")
                            # Zug weitergeben
                            alive = [p for p in players if players[p]["active"]]
                            idx = (alive.index(st.session_state.user) + 1) % len(alive)
                            state["turn"] = alive[idx]
                            save_state(gid, state)
                            st.rerun()
            
            st.write("---")
            st.subheader("Deine Handkarte:")
            st.success(f"{me['hand'][0]['name']} (Wert {me['hand'][0]['val']})")
        else:
            st.error("Du bist ausgeschieden.")

        if st.button("🔄 Aktualisieren"):
            st.rerun()
