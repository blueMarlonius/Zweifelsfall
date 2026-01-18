import streamlit as st
import random
import base64
from google.cloud import firestore
from google.oauth2 import service_account

# --- DATENBANK VERBINDUNG (ROBUST) ---
if "db" not in st.session_state:
    try:
        key_info = dict(st.secrets["textkey"])
        # Key-Reparatur
        raw_key = key_info["private_key"].replace("\\n", "\n")
        if "-----BEGIN PRIVATE KEY-----" in raw_key:
            header, footer = "-----BEGIN PRIVATE KEY-----\n", "\n-----END PRIVATE KEY-----\n"
            inner = raw_key.replace(header, "").replace(footer, "").replace("\n", "").replace(" ", "")
            missing_padding = len(inner) % 4
            if missing_padding: inner += "=" * (4 - missing_padding)
            key_info["private_key"] = header + inner + footer
            
        creds = service_account.Credentials.from_service_account_info(key_info)
        st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
    except Exception as e:
        st.error(f"Verbindungsfehler: {e}")
        st.stop()

db = st.session_state.db

# --- HILFSFUNKTIONEN FÜR FIRESTORE ---
def get_state(gid):
    if not gid: return None
    try:
        doc = db.collection("games").document(gid).get()
        return doc.to_dict() if doc.exists else None
    except Exception:
        return None # Gibt None zurück statt abzustürzen

def save_state(gid, state):
    db.collection("games").document(gid).set(state)

# --- SPIEL-KONFIGURATION ---
CARDS = []
for c in [(0,"Tradition","Blau"),(1,"Missionar","Blau"),(2,"Beichtvater","Blau"),(3,"Richter","Rot"),(4,"Eremit","Blau"),(5,"Abt","Rot"),(6,"Vision","Rot"),(7,"Wunder","Blau"),(8,"Gott","Blau")]:
    CARDS.extend([{"val":c[0],"name":c[1],"color":c[2]}] * 3)

# --- APP OBERFLÄCHE ---
st.set_page_config(page_title="Zweifelsfall", layout="centered")
st.title("⚖️ Zweifelsfall Online")

# --- NEUER STABILER LOGIN ---
if "user" not in st.session_state:
    with st.form("login_form"):
        st.subheader("Willkommen bei Zweifelsfall")
        name_input = st.text_input("Dein Name:")
        room_input = st.text_input("Spiel-Raum (z.B. Tisch1):")
        submit_button = st.form_submit_button("Dem Spiel beitreten")
        
        if submit_button:
            if name_input and room_input:
                st.session_state.user = name_input.strip()
                st.session_state.gid = room_input.strip()
                st.rerun()
            else:
                st.error("Bitte gib Namen UND Raum an!")
    st.stop() # Ganz wichtig: Hier stoppt die App, bis man eingeloggt ist!
    
else:
    state = get_state(st.session_state.gid)

    # SPIEL INITIALISIEREN
    if not state:
        if st.button("Neues Spiel im Raum erstellen"):
            deck = list(CARDS)
            random.shuffle(deck)
            new_state = {
                "deck": deck,
                "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "played": None}},
                "turn": st.session_state.user,
                "log": [f"{st.session_state.user} hat das Spiel gestartet."]
            }
            save_state(st.session_state.gid, new_state)
            st.rerun()
    else:
        # SPIELER-LOGIK
        players = state["players"]
        if st.session_state.user not in players:
            if st.button("Als Mitspieler beitreten"):
                state["players"][st.session_state.user] = {"hand": [state["deck"].pop()], "active": True, "played": None}
                save_state(st.session_state.gid, state)
                st.rerun()

        # PRÜFUNG: WER HAT GEWONNEN?
        active_players = [p for p in players if players[p]["active"]]
        if len(active_players) == 1:
            st.balloons()
            st.success(f"🏆 {active_players[0]} hat gewonnen!")
            if st.button("Neues Spiel"):
                db.collection("games").document(st.session_state.gid).delete()
                st.rerun()
            st.stop()

        # DAS SPIELFELD
        me = players[st.session_state.user]
        st.write(f"Du spielst als: **{st.session_state.user}**")
        st.write(f"Aktuell am Zug: **{state['turn']}**")

        if me["active"]:
            # SCHRITT 1: ZWEIFELSFALL TEST
            if me["played"] and me["played"]["color"] == "Rot":
                st.warning("⚠️ Rote Karte vor dir! Überzeugungstest nötig.")
                if st.button("Test-Karte ziehen"):
                    test_card = state["deck"].pop()
                    state["log"].append(f"TEST {st.session_state.user}: {test_card['name']} ({test_card['color']})")
                    if test_card["color"] == "Rot":
                        me["active"] = False
                        state["log"].append(f"💀 {st.session_state.user} scheitert!")
                        state["turn"] = active_players[(active_players.index(st.session_state.user)+1)%len(active_players)]
                    save_state(st.session_state.gid, state)
                    st.rerun()

            # SCHRITT 2: NORMALER ZUG
            elif state["turn"] == st.session_state.user:
                if len(me["hand"]) < 2:
                    if st.button("Karte ziehen"):
                        me["hand"].append(state["deck"].pop())
                        save_state(st.session_state.gid, state)
                        st.rerun()
                else:
                    st.write("Wähle dein Bekenntnis:")
                    c1, c2 = st.columns(2)
                    for i, card in enumerate(me["hand"]):
                        col = c1 if i == 0 else c2
                        if col.button(f"{card['name']} ({card['color']})", key=f"play_{i}"):
                            played = me["hand"].pop(i)
                            me["played"] = played
                            state["log"].append(f"📢 {st.session_state.user}: {played['name']}")
                            # Zug weitergeben
                            idx = (active_players.index(st.session_state.user) + 1) % len(active_players)
                            state["turn"] = active_players[idx]
                            save_state(st.session_state.gid, state)
                            st.rerun()
            
            # HANDKARTE
            st.write("---")
            st.subheader("Deine Handkarte:")
            st.info(f"**{me['hand'][0]['name']}** ({me['hand'][0]['color']})")
        else:
            st.error("Du bist ausgeschieden. Warte auf die nächste Runde.")

        if st.button("🔄 Aktualisieren"):
            st.rerun()
