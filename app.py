import streamlit as st
import random
import base64
from google.cloud import firestore
from google.oauth2 import service_account

# --- DATENBANK VERBINDUNG ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])

db = st.session_state.db

# --- KARTEN-DATENBANK (BASIEREND AUF DEINEM PDF) ---
# Format: (Wert, Name, Farbe, Effekt-Text, Satz)
CARD_LIST = [
    (0, "Tradition", "Blau", "Wer sie am Ende hält, verliert. Ziehe beim Ausspielen neu.", "Menschen glauben an Gott, weil sie die Bräuche ihrer Vorfahren ehren."),
    (0, "Indoktrination", "Rot", "Wer sie am Ende hält, verliert. Ziehe beim Ausspielen neu.", "Menschen glauben nicht an Gott, weil sie in einem Umfeld aufgewachsen sind, das Spiritualität verspottet."),
    (1, "Missionar", "Blau", "Rate die Handkarte eines Gegners. Richtig? Er fliegt.", "Menschen glauben an Gott, weil sie die frohe Botschaft teilen wollen."),
    (1, "Aufklärer", "Rot", "Rate Handkarte. Richtig? Gegner fliegt. (Im Zweifel: Danach noch ein Zug).", "Menschen glauben nicht an Gott, weil die Vernunft uns lehrt, nur Beweisbares zu akzeptieren."),
    (2, "Beichtvater", "Blau", "Sieh dir die Handkarte eines Gegners an.", "Menschen glauben an Gott, weil das Geständnis Erleichterung verschafft."),
    (2, "Psychologe", "Rot", "Sieh dir die Handkarte an. (Im Zweifel: Ziehe zusätzlich eine Karte).", "Religion ist oft nur eine Projektion menschlicher Wünsche."),
    (3, "Mystiker", "Blau", "Vergleiche Karten; der niedrigere Wert scheidet aus.", "Menschen spüren in der Stille eine transzendente Realität."),
    (4, "Eremit", "Blau", "Schutz vor allen Effekten bis zum nächsten Zug.", "Konzentration auf das Wesentliche in der Einsamkeit."),
    (5, "Prediger", "Blau", "Ein Spieler legt seine Karte ab und zieht neu.", "Die Kraft der Worte öffnet das Herz."),
    (6, "Prophet", "Blau", "Tausche Karten mit einem Mitspieler.", "Visionen von einer gerechteren Welt."),
    (7, "Wunder", "Blau", "Muss abgelegt werden, wenn man die 8 hält.", "Ereignisse, die jede Erklärung sprengen."),
    (8, "Präsenz (Gott)", "Blau", "Wer sie am Ende hält, gewinnt. Nicht freiwillig ablegbar.", "Vollkommenheit des Seins in allem erkennen.")
] # Du kannst die restlichen Karten (Logiker, Stoiker etc.) nach dem gleichen Muster ergänzen.

# --- HILFSFUNKTIONEN ---
def save(state): db.collection("games").document(st.session_state.gid).set(state)

# --- LOGIN ---
if "user" not in st.session_state:
    with st.form("login"):
        name = st.text_input("Dein Name:")
        room = st.text_input("Spiel-Raum:")
        if st.form_submit_button("Start"):
            st.session_state.user, st.session_state.gid = name, room
            st.rerun()
    st.stop()

state = db.collection("games").document(st.session_state.gid).get().to_dict()

# --- SPIELSTART ---
if not state:
    if st.button("Spiel eröffnen"):
        deck = []
        for c in CARD_LIST: deck.extend([{"val":c[0],"name":c[1],"color":c[2],"eff":c[3],"txt":c[4]}] * 2)
        random.shuffle(deck)
        state = {"deck": deck, "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "protected": False}}, "turn": st.session_state.user, "log": []}
        save(state); st.rerun()
    st.stop()

# --- SPIEL-LOGIK ---
players = state["players"]
me = players.get(st.session_state.user)

if not me:
    if st.button("Mitspielen"):
        state["players"][st.session_state.user] = {"hand": [state["deck"].pop()], "active": True, "protected": False}
        save(state); st.rerun()
    st.stop()

# --- DAS SPIELFELD ---
st.subheader(f"Raum: {st.session_state.gid} | Am Zug: {state['turn']}")

if me["active"]:
    # Handkarten anzeigen
    st.write("### Deine Hand")
    for i, card in enumerate(me["hand"]):
        color_hex = "#1E90FF" if card["color"] == "Blau" else "#FF4500"
        with st.container():
            st.markdown(f"<div style='border:2px solid {color_hex}; padding:10px; border-radius:10px;'><b>{card['name']} ({card['val']})</b><br><small>{card['eff']}</small><br><i>'{card['txt']}'</i></div>", unsafe_allow_html=True)
            
            # Karte spielen
            if state["turn"] == st.session_state.user and len(me["hand"]) > 1:
                if st.button(f"Spiele {card['name']}", key=f"play_{i}"):
                    played = me["hand"].pop(i)
                    state["log"].append(f"{st.session_state.user} spielt {played['name']}: {played['txt']}")
                    
                    # EFFEKT-LOGIK (Beispiele)
                    if played["val"] == 1: # Missionar
                        st.session_state.action = ("guess", played)
                    elif played["val"] == 2: # Beichtvater
                        st.session_state.action = ("look", played)
                    elif played["val"] == 4: # Eremit
                        me["protected"] = True
                    
                    # Zug-Ende (einfach)
                    others = [p for p in players if p != st.session_state.user and players[p]["active"]]
                    state["turn"] = others[0] if others else st.session_state.user
                    save(state); st.rerun()

    # Aktive Effekte (Menüs)
    if "action" in st.session_state:
        act_type, card = st.session_state.action
        st.write("---")
        target = st.selectbox("Wähle ein Opfer:", [p for p in players if p != st.session_state.user and players[p]["active"]])
        
        if act_type == "guess":
            guess_val = st.number_input("Rate den Wert (0-8):", 0, 8)
            if st.button("Raten!"):
                if players[target]["hand"][0]["val"] == guess_val:
                    players[target]["active"] = False
                    state["log"].append(f"🎯 Erfolg! {target} wurde entlarvt.")
                del st.session_state.action; save(state); st.rerun()
        
        if act_type == "look":
            if st.button("Karte ansehen"):
                st.info(f"{target} hält: {players[target]['hand'][0]['name']}")
                if st.button("Verstanden"): 
                    del st.session_state.action; st.rerun()

    # Karte ziehen
    if state["turn"] == st.session_state.user and len(me["hand"]) == 1:
        if st.button("Karte ziehen"):
            me["hand"].append(state["deck"].pop())
            me["protected"] = False
            save(state); st.rerun()

# Log
with st.expander("Spielprotokoll"):
    for entry in reversed(state["log"]): st.write(entry)
