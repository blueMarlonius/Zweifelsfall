import streamlit as st
import random
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- SETUP & DB ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- KARTEN-LISTE (Vollständige Daten) ---
CARD_LIST = [
    (0, "Tradition", "Blau", "Wer diese Karte am Ende hält, verliert. Beim Ausspielen: Ziehe eine neue Karte.", "Menschen glauben an Gott, weil sie die Bräuche ihrer Vorfahren ehren und darin Geborgenheit finden."),
    (0, "Indoktrination", "Rot", "Wer diese Karte am Ende hält, verliert. Beim Ausspielen: Ziehe eine neue Karte.", "Menschen glauben nicht an Gott, weil sie in einem Umfeld aufgewachsen sind, das Spiritualität als Unvernunft verspottet."),
    (1, "Missionar", "Blau", "Rate die Handkarte eines Gegners. Richtig? Er fliegt.", "Menschen glauben an Gott, weil sie die frohe Botschaft der Hoffnung mit anderen teilen wollen."),
    (1, "Aufklärer", "Rot", "Rate die Handkarte eines Gegners. Richtig? Er fliegt. (ZWANG: Danach noch ein Zug).", "Menschen glauben nicht an Gott, weil die Vernunft uns lehrt, nur das zu akzeptieren, was beweisbar ist."),
    (2, "Beichtvater", "Blau", "Sieh dir die Handkarte eines Gegners an.", "Menschen glauben an Gott, weil das Geständnis ihrer Fehler ihnen seelische Erleichterung verschafft."),
    (2, "Psychologe", "Rot", "Sieh dir die Handkarte eines Gegners an. (ZWANG: Ziehe eine neue Karte).", "Menschen glauben nicht an Gott, weil sie erkennen, dass Religion oft nur eine Projektion menschlicher Wünsche ist."),
    (3, "Mystiker", "Blau", "Vergleiche Karten; der niedrigere Wert scheidet aus.", "Menschen glauben an Gott, weil sie in Momenten der Stille eine transzendente Realität spüren."),
    (3, "Logiker", "Rot", "Vergleiche Karten. (ZWANG: Sieg bei Gleichstand).", "Ein gütiger Schöpfer ist mathematisch nicht mit dem Chaos der Welt vereinbar."),
    (4, "Eremit", "Blau", "Schutz vor allen Effekten bis zum nächsten Zug.", "Menschen glauben an Gott, weil sie sich in der Einsamkeit auf das Wesentliche konzentrieren."),
    (4, "Stoiker", "Rot", "Schutz vor allen Effekten bis zum nächsten Zug.", "Menschen glauben nicht an Gott, weil sie lernen, die Welt so zu akzeptieren, wie sie objektiv ist."),
    (5, "Prediger", "Blau", "Ein Spieler legt seine Karte ab und zieht neu.", "Die Kraft der Worte öffnet ihr Herz für das Überirdische."),
    (5, "Reformator", "Rot", "Ein Spieler legt seine Karte ab und zieht neu. (ZWANG: Wähle zwei Spieler).", "Alte Dogmen halten einer modernen, kritischen Prüfung nicht stand."),
    (6, "Prophet", "Blau", "Tausche Karten mit einem Mitspieler.", "Visionen von einer gerechteren, göttlichen Welt."),
    (6, "Agnostiker", "Rot", "Tausche Karten mit einem Mitspieler. (ZWANG: Erst alle Karten ansehen).", "Die absolute Wahrheit bleibt für den menschlichen Verstand unerreichbar."),
    (7, "Wunder", "Blau", "Muss abgelegt werden, wenn man die 8 hält.", "Ereignisse, die jede wissenschaftliche Erklärung sprengen."),
    (7, "Zufall", "Rot", "Muss abgelegt werden, wenn man die 8 hält.", "Wir sind das Ergebnis von Milliarden Jahren chemischer Zufälle."),
    (8, "Die Präsenz (Gott)", "Blau", "Wer sie am Ende hält, gewinnt. Nicht freiwillig ablegbar.", "Die Vollkommenheit des Seins in allem erkennen."),
    (8, "Der Atheist (Die Leere)", "Rot", "Wer sie am Ende hält, gewinnt. Nicht freiwillig ablegbar.", "Gott als Trost für die eigene Endlichkeit.")
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
    if st.button("Spielraum erstellen"):
        deck = []
        for c in CARD_LIST: deck.extend([{"val":c[0],"name":c[1],"color":c[2],"eff":c[3],"txt":c[4]}] * 2)
        random.shuffle(deck)
        state = {"deck": deck, "players": {st.session_state.user: {"hand": [deck.pop()], "active": True, "protected": False, "in_test": False}}, "turn": st.session_state.user, "log": [], "started": False}
        save(state); st.rerun()
    st.stop()

players = state["players"]
if st.session_state.user not in players:
    if st.button("Raum beitreten"):
        state["players"][st.session_state.user] = {"hand": [state["deck"].pop()], "active": True, "protected": False, "in_test": False}
        save(state); st.rerun()
    st.stop()

# --- LOBBY ---
if not state.get("started", False):
    st.info(f"Warten auf Mitspieler... ({len(players)} im Raum)")
    if len(players) > 1 and st.button("Spiel jetzt starten"):
        state["started"] = True
        save(state); st.rerun()
    st.stop()

# --- SIEG-CHECK ---
alive = [p for p in players if players[p]["active"]]
if len(alive) == 1:
    st.balloons(); st.header(f"🏆 {alive[0]} hat gewonnen!"); 
    if st.button("Raum löschen"): doc_ref.delete(); st.rerun()
    st.stop()

me = players[st.session_state.user]
st.title(f"Dran: {state['turn']}")

# --- SPIELABLAUF ---
if me["active"]:
    # 1. GLAUBENSTEST (Muss am Anfang des Zugs gemacht werden, wenn man Rot gelegt hatte)
    if state["turn"] == st.session_state.user and me["in_test"]:
        st.error("⚖️ GLAUBENSTEST! Deine letzte Karte war Rot.")
        if st.button("Schicksalskarte ziehen (Rot = Raus, Blau = Weiter)", use_container_width=True):
            test_card = state["deck"].pop()
            state["log"].append(f"⚖️ {st.session_state.user} zieht im Test: {test_card['name']} ({test_card['color']})")
            if test_card["color"] == "Rot":
                me["active"] = False
                state["log"].append(f"💀 Die Leere verschlingt {st.session_state.user}.")
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
            else:
                st.success("Blau! Deine Überzeugung hält stand.")
                me["in_test"] = False
            save(state); st.rerun()
        st.stop()

    # 2. ZIEHEN
    if state["turn"] == st.session_state.user and len(me["hand"]) == 1 and len(state["deck"]) > 0:
        if st.button("Karte ziehen 🃏", use_container_width=True):
            me["hand"].append(state["deck"].pop()); me["protected"] = False
            save(state); st.rerun()

    # 3. HANDKARTEN ANZEIGEN (FIX: Texte wieder da!)
    cols = st.columns(len(me["hand"]))
    for i, card in enumerate(me["hand"]):
        with cols[i]:
            c_color = "#FF4500" if card["color"] == "Rot" else "#1E90FF"
            st.markdown(f"""
                <div style='border:3px solid {c_color}; padding:12px; border-radius:10px; background-color:#111; min-height:280px;'>
                    <h3 style='color:{c_color}; margin:0;'>{card['name']} ({card['val']})</h3>
                    <p style='font-size:0.9em; margin:8px 0;'><b>Effekt:</b> {card['eff']}</p>
                    <hr style='border:0.5px solid #333;'>
                    <p style='font-size:0.8em; color:#bbb; font-style:italic;'>"{card['txt']}"</p>
                </div>
            """, unsafe_allow_html=True)
            
            if state["turn"] == st.session_state.user and len(me["hand"]) > 1:
                if card["val"] == 8: st.caption("8: Unantastbar")
                elif st.button(f"Spielen", key=f"p_{i}", use_container_width=True):
                    played = me["hand"].pop(i)
                    state["log"].append(f"📢 {st.session_state.user} spielt {played['name']}")
                    if played["color"] == "Rot": me["in_test"] = True
                    if played["val"] == 0 and len(state["deck"]) > 0: me["hand"].append(state["deck"].pop())
                    
                    if played["val"] in [1, 2, 3, 5, 6]:
                        st.session_state.pending_action = played
                        save(state); st.rerun()
                    else:
                        if played["val"] == 4: me["protected"] = True
                        state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                        save(state); st.rerun()

    # 4. AKTIONEN
    if "pending_action" in st.session_state:
        card = st.session_state.pending_action
        st.divider()
        st.subheader(f"Effekt ausführen: {card['name']}")
        targets = [p for p in players if p != st.session_state.user and players[p]["active"] and not players[p]["protected"]]
        
        if targets:
            target = st.selectbox("Ziel wählen:", targets)
            if st.button("Effekt bestätigen"):
                # Zweifels-Logik (Beispiel Aufklärer)
                if card["color"] == "Rot" and card["val"] == 1:
                    state["log"].append("⚖️ ZWEIFEL: Du erhältst einen Zusatzzug!")
                else:
                    state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                del st.session_state.pending_action; save(state); st.rerun()
        else:
            if st.button("Kein Ziel - Zug beenden"):
                state["turn"] = alive[(alive.index(st.session_state.user)+1)%len(alive)]
                del st.session_state.pending_action; save(state); st.rerun()

with st.expander("Protokoll"):
    for l in reversed(state.get("log", [])): st.write(l)
