import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account

# --- DATENBANK VERBINDUNG ---
if "db" not in st.session_state:
    key_dict = st.secrets["textkey"]
    creds = service_account.Credentials.from_service_account_info(key_dict)
    st.session_state.db = firestore.Client(credentials=creds)

db = st.session_state.db

# --- KARTEN-LOGIK ---
CARDS = [
    {"val": 0, "name": "Tradition", "color": "Blau", "text": "Wer sie am Ende hält, verliert."},
    {"val": 1, "name": "Missionar", "color": "Blau", "text": "Rate Karte: Richtig? Gegner fliegt."},
    {"val": 2, "name": "Beichtvater", "color": "Blau", "text": "Sieh dir eine Handkarte an."},
    {"val": 4, "name": "Eremit", "color": "Blau", "text": "Schutz bis zum nächsten Zug."},
    {"val": 8, "name": "Gott", "color": "Blau", "text": "Wer sie am Ende hält, gewinnt."}
] # Du kannst hier alle weiteren Karten aus deinem PDF ergänzen!

def get_game(gid):
    doc = db.collection("games").document(gid).get()
    return doc.to_dict()

def save_game(gid, data):
    db.collection("games").document(gid).set(data)

# --- APP OBERFLÄCHE ---
st.set_page_config(page_title="Zweifelsfall Online")
st.title("🃏 Zweifelsfall Multiplayer")

if "my_name" not in st.session_state:
    st.session_state.my_name = st.text_input("Dein Name:")
    st.session_state.gid = st.text_input("Spiel-ID (z.B. Tisch1):")
    if st.button("Spiel beitreten"):
        st.rerun()

if "my_name" in st.session_state:
    gid = st.session_state.gid
    game = get_game(gid)

    if not game:
        if st.button("Neues Spiel für alle starten"):
            deck = CARDS * 4
            random.shuffle(deck)
            new_game = {
                "deck": deck,
                "players": {st.session_state.my_name: {"hand": [deck.pop()], "active": True, "played": None}},
                "turn": st.session_state.my_name,
                "log": ["Spiel gestartet!"]
            }
            save_game(gid, new_game)
            st.rerun()
    else:
        # Spieler-Logik
        players = game["players"]
        if st.session_state.my_name not in players:
            if st.button("Platz am Tisch nehmen"):
                game["players"][st.session_state.my_name] = {"hand": [game["deck"].pop()], "active": True, "played": None}
                save_game(gid, game)
                st.rerun()

        # SPIELFELD
        st.write(f"### 🚩 Am Zug: {game['turn']}")
        
        # Handkarte anzeigen
        me = players[st.session_state.my_name]
        if me["active"]:
            st.subheader("Deine Handkarte:")
            st.info(f"{me['hand'][0]['name']} ({me['hand'][0]['color']}) - {me['hand'][0]['text']}")
            
            if game["turn"] == st.session_state.my_name:
                if len(me["hand"]) == 1:
                    if st.button("Karte ziehen"):
                        me["hand"].append(game["deck"].pop())
                        save_game(gid, game)
                        st.rerun()
                else:
                    st.write("Wähle eine Karte zum Ausspielen:")
                    for i, card in enumerate(me["hand"]):
                        if st.button(f"Spiele {card['name']}", key=f"btn{i}"):
                            played = me["hand"].pop(i)
                            me["played"] = played
                            game["log"].append(f"{st.session_state.my_name} spielt {played['name']}")
                            # Hier nächsten Spieler setzen
                            p_list = [p for p in players if players[p]["active"]]
                            idx = (p_list.index(st.session_state.my_name) + 1) % len(p_list)
                            game["turn"] = p_list[idx]
                            save_game(gid, game)
                            st.rerun()
        else:
            st.error("Du bist ausgeschieden.")

        st.write("---")
        if st.button("🔄 Ansicht aktualisieren"):
            st.rerun()
