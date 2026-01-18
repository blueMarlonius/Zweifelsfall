import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- DATENBANK VERBINDUNG ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- KARTEN-DATEN (Vollständige Texte) ---
CARD_LIST = [
    (0, "Tradition", "Blau", "Wer diese Karte am Ende hält, verliert. Beim Ausspielen: Ziehe eine neue Karte.", "Menschen glauben an Gott, weil sie die Bräuche ihrer Vorfahren ehren und darin Geborgenheit finden."),
    (0, "Indoktrination", "Rot", "Wer diese Karte am Ende hält, verliert. Beim Ausspielen: Ziehe eine neue Karte.", "Menschen glauben nicht an Gott, weil sie in einem Umfeld aufgewachsen sind, das Spiritualität als Unvernunft verspottet."),
    (1, "Missionar", "Blau", "Rate die Handkarte eines Gegners. Richtig? Er fliegt.", "Menschen glauben an Gott, weil sie die frohe Botschaft der Hoffnung mit anderen teilen wollen."),
    (1, "Aufklärer", "Rot", "Rate die Handkarte eines Gegners. Richtig? Er fliegt.", "Menschen glauben nicht an Gott, weil die Vernunft uns lehrt, nur das zu akzeptieren, was beweisbar ist."),
    (2, "Beichtvater", "Blau", "Sieh dir die Handkarte eines Gegners an.", "Menschen glauben an Gott, weil das Geständnis ihrer Fehler ihnen seelische Erleichterung verschafft."),
    (2, "Psychologe", "Rot", "Sieh dir die Handkarte eines Gegners an.", "Menschen glauben nicht an Gott, weil sie erkennen, dass Religion oft nur eine Projektion menschlicher Wünsche ist."),
    (3, "Mystiker", "Blau", "Vergleiche Karten; der niedrigere Wert scheidet aus.", "Menschen glauben an Gott, weil sie in Momenten der Stille eine transzendente Realität spüren."),
    (3, "Logiker", "Rot", "Vergleiche Karten; der niedrigere Wert scheidet aus.", "Ein gütiger Schöpfer ist mathematisch nicht mit dem Chaos der Welt vereinbar."),
    (4, "Eremit", "Blau", "Schutz vor allen Effekten bis zum nächsten Zug.", "Menschen glauben an Gott, weil sie sich in der Einsamkeit auf das Wesentliche konzentrieren."),
    (4, "Stoiker", "Rot", "Schutz vor allen Effekten bis zum nächsten Zug.", "Menschen glauben nicht an Gott, weil sie lernen, die Welt so zu akzeptieren, wie sie objektiv ist."),
    (5, "Prediger", "Blau", "Ein Spieler legt seine Karte ab und zieht neu.", "Die Kraft der Worte öffnet ihr Herz für das Überirdische."),
    (5, "Reformator", "Rot", "Ein Spieler legt seine Karte ab und zieht neu.", "Alte Dogmen halten einer modernen, kritischen Prüfung nicht stand."),
    (6, "Prophet", "Blau", "Tausche Karten mit einem Mitspieler.", "Visionen von einer gerechteren, göttlichen Welt."),
    (6, "Agnostiker", "Rot", "Tausche Karten mit einem Mitspieler.", "Die absolute Wahrheit bleibt für den Verstand unerreichbar."),
    (7, "Wunder", "Blau", "Muss abgelegt werden, wenn man die 8 hält.", "Ereignisse, die jede wissenschaftliche Erklärung sprengen."),
    (7, "Zufall", "Rot", "Muss abgelegt werden, wenn man die 8 hält.", "Wir sind das Ergebnis von Milliarden Jahren chemischer Zufälle."),
    (8, "Präsenz (Gott)", "Blau", "Wer sie am Ende hält, gewinnt. Nicht freiwillig ablegbar.", "Die Vollkommenheit des Seins in allem erkennen."),
    (8, "Atheist (Die Leere)", "Rot", "Wer sie am Ende hält, gewinnt.", "Gott als Trost für die eigene Endlichkeit.")
]

def save(state): db.collection("games").document(st.session_state.gid).set(state)

# --- LOGIN ---
if "user" not in st.session_state:
    with st.form("login"):
        st.header("⚖️ Zweifelsfall")
        n, r = st.text_input("Dein Name:"), st.text_input("Spiel-Raum:")
        if st.form_submit_button("Beitreten"):
            st.session_state.user, st.session_state.gid = n.strip(), r.strip()
            st.rerun()
    st.stop()

st_autorefresh(interval=4000, key="sync")
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

# --- INITIALISIERUNG ---
if not state:
    if st.button("Neues Spiel starten"):
        deck = []
        for c in CARD_LIST: deck.extend([{"val":c[0],"name":c[1],"color":c[2],"eff":c[3],"txt":c[4]}] * 2)
        random.shuffle(deck)
        state = {"deck": deck, "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "protected": False}}, "turn": st.session_state.user, "log": []}
        save(state); st.rerun()
    st.stop()

players = state["players"]
if st.session_state.user not in players:
    if st.button("Beitreten"):
        state["players"][st.session_state.user] = {"hand": [state["deck"].pop()], "active": True, "protected": False}
        save(state); st.rerun()
    st.stop()

# --- GEWINNER ---
alive = [p for p in players if players[p]["active"]]
if len(alive) == 1 and len(players) > 1:
    st.balloons()
    st.header(f"🏆 {alive[0]} hat gewonnen!")
    if st.button("Raum löschen"): doc_ref.delete(); st.rerun()
    st.stop()

me = players[st.session_state.user]
st.markdown(f"<h1 style='text-align: center;'>Dran: {state['turn']}</h1>", unsafe_allow_html=True)

if me["active"]:
    # 1. ZIEHEN
    if state["turn"] == st.session_state.user and len(me["hand"]) == 1:
        if st.button("Karte ziehen 🃏", use_container_width=True):
            me["hand"].append(state["deck"].pop())
            me["protected"] = False
            save(state); st.rerun()

    # 2. HANDKARTEN ANZEIGEN
    cols = st.columns(len(me["hand"]))
    for i, card in enumerate(me["hand"]):
        with cols[i]:
            c_color = "#1E90FF" if card["color"] == "Blau" else "#FF4500"
            # HIER WIRD DER TEXT WIEDER ANGEZEIGT:
            st.markdown(f"""<div style='border:3px solid {c_color}; padding:10px; border-radius:10px; background-color:#111; min-height:250px;'>
                <h3 style='color:{c_color}; margin:0;'>{card['name']} ({card['val']})</h3>
                <p style='font-size:0.8em; margin:5px 0;'><b>Effekt:</b> {card['eff']}</p>
                <hr style='margin:5px 0; border:0.5px solid #333;'>
                <i style='font-size:0.75em; color:#bbb;'>"{card['txt']}"</i>
                </div>""", unsafe_allow_html=True)
            
            if state["turn"] == st.session_state.user and len(me["hand"]) > 1:
                if st.button(f"Spielen", key=f"btn_{i}", use_container_width=True):
                    played = me["hand"].pop(i)
                    state["log"].append(f"📢 {st.session_state.user} spielt {played['name']}")
                    if played["val"] == 0: me["hand"].append(state["deck"].pop())
                    if played["val"] in [1, 2, 3, 5, 6]:
                        st.session_state.pending_action = played
                        save(state); st.rerun()
                    else:
                        if played["val"] == 4: me["protected"] = True
                        idx = (alive.index(st.session_state.user) + 1) % len(alive)
                        state["turn"] = alive[idx]
                        save(state); st.rerun()

    # 3. AKTIONEN
    if "pending_action" in st.session_state:
        card = st.session_state.pending_action
        st.divider()
        targets = [p for p in players if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]
        
        if not targets:
            st.warning("Kein Ziel möglich!")
            if st.button("Zug ohne Effekt beenden"):
                idx = (alive.index(st.session_state.user) + 1) % len(alive)
                state["turn"] = alive[idx]
                del st.session_state.pending_action; save(state); st.rerun()
        else:
            target = st.selectbox("Ziel wählen:", targets)
            if card["val"] == 1:
                g = st.number_input("Raten (0-8):", 0, 8)
                if st.button("Angriff bestätigen"):
                    if players[target]["hand"][0]["val"] == g: players[target]["active"] = False
                    state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                    del st.session_state.pending_action; save(state); st.rerun()
            if card["val"] == 2:
                st.info(f"{target} hält: {players[target]['hand'][0]['name']}")
                if st.button("Gesehen & Beenden"):
                    state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                    del st.session_state.pending_action; save(state); st.rerun()
            if card["val"] == 3:
                if st.button("Vergleich bestätigen"):
                    v1, v2 = me["hand"][0]["val"], players[target]["hand"][0]["val"]
                    if v1 > v2: players[target]["active"] = False
                    elif v2 > v1: me["active"] = False
                    new_alive = [p for p in players if players[p]["active"]]
                    state["turn"] = new_alive[0] if len(new_alive) > 0 else state["turn"]
                    del st.session_state.pending_action; save(state); st.rerun()
            if card["val"] == 6:
                if st.button("Tausch bestätigen"):
                    me["hand"][0], players[target]["hand"][0] = players[target]["hand"][0], me["hand"][0]
                    state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                    del st.session_state.pending_action; save(state); st.rerun()
else:
    st.error("Warte auf das Ende der Runde...")

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
