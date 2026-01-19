import streamlit as st
import random
import streamlit as st
import os
from google.cloud import firestore
from google.oauth2 import service_account
from streamlit_autorefresh import st_autorefresh

# --- 1. DATENBANK-VERBINDUNG ---
if "db" not in st.session_state:
    key_info = dict(st.secrets["textkey"])
    key_info["private_key"] = key_info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_info)
    st.session_state.db = firestore.Client(credentials=creds, project=key_info["project_id"])
db = st.session_state.db

# --- 2. HELFER-FUNKTIONEN ---
def create_deck():
    """Erstellt ein Deck nur aus Werten und Farben."""
    # Anzahl der Karten pro Wert (0 bis 8)
    counts = {0:1, 1:3, 2:3, 3:2, 4:2, 5:2, 6:1, 7:1, 8:1}
    deck = []
    for val, num in counts.items():
        for color in ["Blau", "Rot"]:
            for _ in range(num):
                # Die Karte speichert KEINEN Text, nur Logik-Daten
                deck.append({
                    "val": val, 
                    "color": color
                })
    random.shuffle(deck)
    return deck

def save(state):
    # Nur speichern, wenn wir eine gültige Raum-ID haben
    if "gid" in st.session_state:
        db.collection("games").document(st.session_state.gid).set(state)
        
@st.cache_data(show_spinner=False)  # Das 'False' ist entscheidend!
def get_card_image(card):
    if not card: 
        return "https://via.placeholder.com/300x450.png?text=Keine+Karte"
    v = card.get('val', 0)
    c = card.get('color', 'Blau')
    path = f"assets/card_{v}_{c}.png"
    if os.path.exists(path):
        return path
    return f"https://via.placeholder.com/300x450.png?text={v}+{c}"    

# --- BLOCK 2: LOGIN, DATEN & REFRESH (KOMPLETT) ---

# 1. Login-Maske
if "user" not in st.session_state:
    with st.form("login_form"):
        st.header("⚖️ ZWEIFELSFALL - Login")
        name = st.text_input("Dein Name:")
        room = st.text_input("Raum-ID (z.B. Geheimraum):")
        if st.form_submit_button("Raum betreten"):
            if name and room:
                st.session_state.user = name.strip()
                st.session_state.gid = room.strip()
                st.rerun()
            else:
                st.error("Bitte gib einen Namen und eine Raum-ID an!")
    st.stop()

# 2. Daten aus Firestore laden
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

# 3. Raum-Initialisierung falls neu
if not state:
    if st.button("Neuen Spielraum eröffnen"):
        state = {
            "started": False,
            "host": st.session_state.user,
            "players": {},
            "order": [],
            "deck": [],
            "log": ["Raum wurde erstellt."],
            "turn_idx": 0,
            "phase": "LOBBY"
        }
        save(state)
        st.rerun()
    st.stop()

# 4. Globale Variablen definieren (Wichtig für alle folgenden Blöcke!)
players = state.get("players", {})
order = state.get("order", [])
host_name = state.get("host")
me = players.get(st.session_state.user)

# Wer ist gerade dran?
curr_p_name = None
if state.get("started") and order:
    curr_p_name = order[state["turn_idx"]]

# 5. Intelligenter Refresh
# Wir aktualisieren automatisch, wenn:
# - Das Spiel noch nicht gestartet ist (Lobby-Modus)
# - ODER ich nicht an der Reihe bin
do_refresh = True
if state.get("started") and curr_p_name == st.session_state.user:
    do_refresh = False

    
# --- BLOCK 3: LOBBY & MANUELLE REIHENFOLGE ---

if not state.get("started", False):
    st.header(f"🏠 Lobby: {st.session_state.gid}")
    
    # 1. Spielerliste anzeigen
    st.subheader(f"Teilnehmer ({len(order)}/5)")
    
    for i, name in enumerate(order):
        # Goldener Rahmen für den Host, grauer für andere
        is_host = (name == host_name)
        box_style = "solid #FFD700" if is_host else "solid #555"
        
        with st.container():
            st.markdown(f"""
                <div style="border-left: 5px {box_style}; padding-left: 15px; margin: 10px 0;">
                    <span style="font-size: 1.2em; font-weight: bold;">{name}</span>
                    <br><span style="font-size: 0.8em; color: #888;">{'RAUMLEITUNG' if is_host else 'SPIELER'}</span>
                </div>
            """, unsafe_allow_html=True)
            
            # Manuelle Sortierung: Nur der Host sieht die Pfeile
            if st.session_state.user == host_name:
                col1, col2, col3 = st.columns([1, 1, 4])
                with col1:
                    if i > 0:
                        if st.button("↑", key=f"up_{name}"):
                            order[i], order[i-1] = order[i-1], order[i]
                            state["order"] = order
                            save(state); st.rerun()
                with col2:
                    if i < len(order) - 1:
                        if st.button("↓", key=f"down_{name}"):
                            order[i], order[i+1] = order[i+1], order[i]
                            state["order"] = order
                            save(state); st.rerun()

    st.divider()

    # 2. Aktionen
    # Beitritt-Button (nur für Leute, die noch nicht in der Liste sind)
    if st.session_state.user not in players and len(order) < 5:
        if st.button("Beitreten", use_container_width=True, type="primary"):
            state["players"][st.session_state.user] = {
                "markers": 0, "active": True, "discard_stack": [], 
                "hand": [], "protected": False
            }
            state["order"].append(st.session_state.user)
            save(state); st.rerun()

    # Start-Bereich für den Host
    if st.session_state.user == host_name:
        st.subheader("Host-Kontrolle")
        if st.button("🔀 Zufällig mischen", use_container_width=True):
            random.shuffle(state["order"])
            save(state); st.rerun()
            
        if st.button("✅ SPIEL STARTEN", use_container_width=True, type="primary"):
            if len(order) >= 2:
                # Vorbereitungen für den Start
                deck = create_deck()
                state.update({
                    "started": True,
                    "deck": deck,
                    "phase": "TEST",
                    "turn_idx": 0,
                    "log": ["Das Spiel wurde gestartet!"]
                })
                # Jedem Spieler eine Startkarte geben
                for p_name in order:
                    state["players"][p_name].update({
                        "active": True,
                        "hand": [state["deck"].pop()],
                        "discard_stack": [],
                        "protected": False
                    })
                save(state); st.rerun()
            else:
                st.error("Mindestens 2 Spieler erforderlich!")
    else:
        st.info("Warten auf den Hoster...")

    st.stop() # Verhindert das Laden des Spielfelds, solange wir in der Lobby sind

# --- BLOCK 4: DAS SPIELFELD (MIT FEHLER-KORREKTUR) ---

if state.get("started", False):
    st.title("⚖️ ZWEIFELSFALL")

    @st.fragment(run_every=3)
    def show_opponents_fragment():
        # 1. Daten frisch aus Firestore laden
        f_doc = db.collection("games").document(st.session_state.gid).get()
        if not f_doc.exists: 
            return
        f_state = f_doc.to_dict()
        
        # 2. Intelligenter Refresh
        current_hash = f"{f_state.get('phase')}-{f_state.get('turn_idx')}-{len(f_state.get('deck', []))}"
        if "last_hash" in st.session_state and st.session_state.last_hash != current_hash:
            st.session_state.last_hash = current_hash
            st.rerun() 
        st.session_state.last_hash = current_hash

        # 3. Variablen vorbereiten
        f_players = f_state.get("players", {})
        f_order = f_state.get("order", [])
        f_curr_p = f_order[f_state["turn_idx"]] if f_order else ""

        # 4. Das Spielfeld zeichnen
        cols = st.columns(len(f_order))
        for i, name in enumerate(f_order):
            p_data = f_players.get(name, {})
            with cols[i]:
                is_turn = (name == f_curr_p)
                border_color = "#FF4B4B" if is_turn else "#333"
                
                st.markdown(f"""
                    <div style="text-align: center; border-bottom: 3px solid {border_color}; padding-bottom: 5px; margin-bottom: 10px;">
                        <b style="font-size: 1.1em;">{name}</b>
                    </div>
                """, unsafe_allow_html=True)

                status_info = ""
                if not p_data.get("active", True): status_info += "💀 "
                if p_data.get("protected"): status_info += "🛡️ "
                if status_info: 
                    st.markdown(f"<div style='text-align:center;'>{status_info}</div>", unsafe_allow_html=True)

                # --- KORRIGIERTER KARTEN-ABSCHNITT ---
                stack = p_data.get("discard_stack", [])
                if stack and len(stack) > 0:
                    top_card = stack[-1]
                    # Sicherstellen, dass top_card ein Dictionary mit Daten ist
                    if top_card and isinstance(top_card, dict):
                        st.image(get_card_image(top_card), use_container_width=True)
                        
                        # Sicherer Aufruf der Namens-Funktion
                        val = top_card.get('val', 0)
                        col = top_card.get('color', 'Blau')
                        try:
                            c_name = get_card_display_name(val, col)
                            st.markdown(f"<p style='text-align:center; font-size:0.8em; font-weight:bold; color:#ccc;'>{c_name}</p>", unsafe_allow_html=True)
                        except:
                            st.markdown(f"<p style='text-align:center; font-size:0.8em;'>Karte {val}</p>", unsafe_allow_html=True)
                else:
                    st.markdown('<div style="height:120px; border:2px dashed #444; border-radius:10px; display:flex; align-items:center; justify-content:center; color:#444; font-size:0.8em; margin-bottom:10px;">Leer</div>', unsafe_allow_html=True)
                
                st.markdown(f"<p style='text-align:center;'>⚪ {p_data.get('markers', 0)}</p>", unsafe_allow_html=True)

    show_opponents_fragment()
    st.divider()
# --- ENDE BLOCK 4 ---
# --- BLOCK 5: DEINE HANDKARTEN (NUR GRAFIK & NAME) ---

def get_card_display_name(val, color):
    """Gibt ausschließlich den Namen der Karte zurück."""
    names = {
        0: ("Tradition", "Indoktrination"), 1: ("Missionar", "Aufklärer"),
        2: ("Beichtvater", "Psychologe"), 3: ("Mystiker", "Logiker"),
        4: ("Eremit", "Stoiker"), 5: ("Prediger", "Reformator"),
        6: ("Prophet", "Agnostiker"), 7: ("Wunder", "Zufall"), 8: ("Gott", "Atheist")
    }
    return names[val][0] if color == "Blau" else names[val][1]

if state.get("started", False):
    me = players[st.session_state.user]
    
    if me["active"]:
        st.subheader("Deine Hand")
        
        # Spalten für die Handkarten (max. 2)
        h_cols = st.columns(2)
        
        for i, card in enumerate(me["hand"]):
            with h_cols[i]:
                # 1. Die Grafik aus dem Ordner /assets
                st.image(get_card_image(card), use_container_width=True)
                
                # 2. Nur der Name der Karte fett gedruckt
                c_name = get_card_display_name(card['val'], card['color'])
                st.markdown(f"<p style='text-align:center; font-weight:bold; font-size:1.1em; margin-top:-5px;'>{c_name}</p>", unsafe_allow_html=True)
                
                # 3. Interaktion (Nur wenn man am Zug ist und eine Karte ziehen musste)
                if curr_p_name == st.session_state.user and state["phase"] == "DRAW":
                    if len(me["hand"]) == 2:
                        st.markdown("<br>", unsafe_allow_html=True) # Abstand zum Button
                        if st.button(f"{c_name} legen", key=f"play_{i}", use_container_width=True, type="primary"):
                            # Zweifel-Status des eigenen Stapels prüfen, bevor die neue Karte draufkommt
                            was_in_doubt = (me["discard_stack"][-1]["color"] == "Rot") if me["discard_stack"] else False
                            state["active_doubt"] = was_in_doubt
                            
                            # Karte bewegen: Hand -> Ablagestapel
                            me["discard_stack"].append(me["hand"].pop(i))
                            me["protected"] = False
                            state["phase"] = "EFFECT"
                            save(state)
                            st.rerun()
    else:
        st.info("Du bist in dieser Runde ausgeschieden.")

# --- BLOCK 6: AUTOMATISCHE PRÜFUNGEN (PHASE: TEST) ---

if state.get("started", False) and state["phase"] == "TEST":
    if curr_p_name == st.session_state.user:
        hand_vals = [c["val"] for c in me["hand"]]
        
        # 1. DIE SPERR-REGEL (7 & 8)
        # Wenn man 8 und 7 hat, MUSS man die 7 sofort ablegen
        if 8 in hand_vals and 7 in hand_vals:
            st.warning("Sperr-Regel: Du hältst die 7 und die 8. Du musst die 7 ablegen!")
            if st.button("7 zwangsweise ablegen"):
                # Finde den Index der 7 in der Hand
                idx7 = next(i for i, c in enumerate(me["hand"]) if c["val"] == 7)
                me["discard_stack"].append(me["hand"].pop(idx7))
                state["phase"] = "DRAW" # Danach normal ziehen
                save(state); st.rerun()
        
        # 2. DER SPEZIALSIEG DER ROTEN 8
        # Wenn die Handkarte Rot ist (Überzeugungstest verloren) UND man die 8 (Rot) hält
        elif len(me["hand"]) == 1 and me["hand"][0]["color"] == "Rot" and me["hand"][0]["val"] == 8:
            st.balloons()
            st.success("SPEZIALSIEG! Du hältst die rote 8 und hast den Überzeugungstest verloren!")
            state["log"].append(f"Spezialsieg durch {st.session_state.user}!")
            state["phase"] = "GAME_OVER"
            state["winner"] = st.session_state.user
            save(state); st.rerun()

        # 3. NORMALER ÜBERGANG ZUM ZIEHEN
        else:
            state["phase"] = "DRAW"
            save(state); st.rerun()

# --- ZIEHEN-PHASE (DRAW) ---
# --- OPTIMIERT: ZIEHEN ---
if state["phase"] == "DRAW" and curr_p_name == st.session_state.user:
    st.info("--- DEIN ZUG: Bitte Karte ziehen ---")
    # Der Button wird in einer Spalte zentriert, damit man ihn nicht übersieht
    if st.button("🎴 KARTE VOM STAPEL ZIEHEN", use_container_width=True, type="primary"):
        with st.spinner("Ziehe..."):
            if state["deck"]:
                new_card = state["deck"].pop()
                me["hand"].append(new_card)
                state["phase"] = "PLAY" # Sofort zur nächsten Phase wechseln
                save(state)
                st.rerun() # Sofortige Aktualisierung ohne Refresh-Warten
# --- ZWISCHENBLOCK: HANDKARTEN ANZEIGEN (PHASE: PLAY) ---
if state.get("started", False) and state["phase"] == "PLAY":
    if curr_p_name == st.session_state.user:
        st.subheader("Deine Handkarten")
        st.write("Wähle eine Karte, um ihren Effekt zu nutzen:")
        
        # Spalten für die Karten
        h_cols = st.columns(len(me["hand"]))
        
        for i, card in enumerate(me["hand"]):
            with h_cols[i]:
                st.image(get_card_image(card), use_container_width=True)
                c_name = get_card_display_name(card['val'], card['color'])
                
                # Der entscheidende Button mit Rerun
                if st.button(f"{c_name} spielen", key=f"play_{i}_{card['val']}", use_container_width=True):
                    # 1. Zweifel-Check (war die letzte Karte auf dem Stapel Rot?)
                    was_doubt = (me["discard_stack"][-1]["color"] == "Rot") if me["discard_stack"] else False
                    state["active_doubt"] = was_doubt
                    
                    # 2. Karte verschieben
                    me["discard_stack"].append(me["hand"].pop(i))
                    me["protected"] = False # Immunität erlischt beim eigenen Zug
                    
                    # 3. In die Effekt-Phase wechseln (dein Block 7)
                    state["phase"] = "EFFECT"
                    
                    save(state)
                    st.rerun() # Zwingt die App, sofort Block 7 anzuzeigen
    else:
        st.info(f"Warte darauf, dass {curr_p_name} eine Karte spielt...")

# --- BLOCK 7: FINALE KARTEN-EFFEKT-LOGIK (KOMPLETT & STABIL) ---

if state.get("started", False) and state["phase"] == "EFFECT":
    if curr_p_name == st.session_state.user:
        # Die gespielte Karte liegt oben auf dem Ablagestapel
        played_card = me["discard_stack"][-1]
        val = played_card["val"]
        is_doubt = state.get("active_doubt", False) 
        
        st.subheader(f"Effekt: {get_card_display_name(val, played_card['color'])}")

        # --- WERTE OHNE ZIELWAHL (0, 4, 7, 8) ---
        if val in [0, 4, 7, 8]:
            if val == 0:
                st.info("Haupteffekt: Du musst eine Karte ziehen.")
                if st.button("Karte ziehen & Zug beenden", key="btn_0"):
                    if state["deck"]:
                        me["hand"].append(state["deck"].pop())
                    state["phase"] = "NEXT"
                    save(state)
                    st.rerun()
            
            elif val == 4:
                me["protected"] = True
                st.success("Immunität aktiv! Keiner kann dich im nächsten Zug als Ziel wählen.")
                if st.button("Zug beenden", key="btn_4"):
                    state["phase"] = "NEXT"
                    save(state)
                    st.rerun()
            
            elif val == 8 and played_card["color"] == "Blau":
                st.error("Regelverstoß: Die blaue 8 darf niemals freiwillig gelegt werden!")
                if st.button("Strafe akzeptieren & Beenden", key="btn_8b"):
                    state["phase"] = "NEXT"
                    save(state)
                    st.rerun()
            
            else: # Karte 7 oder rote 8 (Kein aktiver Effekt)
                if st.button("Zug beenden", key="btn_78"):
                    state["phase"] = "NEXT"
                    save(state)
                    st.rerun()

        # --- WERTE MIT ZIELWAHL (1, 2, 3, 5, 6) ---
        else:
            # Ziele filtern (aktiv und nicht geschützt)
            targets = [n for n in order if n != st.session_state.user and players[n]["active"] and not players[n].get("protected")]
            
            if not targets:
                st.warning("Keine gültigen Ziele verfügbar.")
                if st.button("Effekt verfällt & Beenden", key="btn_no_target"):
                    state["phase"] = "NEXT"
                    save(state)
                    st.rerun()
            else:
                if val == 1: # ELIMINATOR
                    t_name = st.selectbox("Ziel wählen:", targets, key="sel_1")
                    guess = st.number_input("Zahl raten (0-8):", 0, 8, key="num_1")
                    if st.button("Raten", key="btn_1"):
                        if players[t_name]["hand"][0]["val"] == guess:
                            players[t_name]["active"] = False
                            st.success(f"Erfolg! {t_name} ist ausgeschieden.")
                            if is_doubt:
                                st.session_state["extra_turn_granted"] = True
                        else:
                            st.error(f"Falsch! {t_name} behält seine Karte.")
                        state["phase"] = "NEXT"
                        save(state)
                        st.rerun()

                elif val == 2: # INFORMATION (BEICHTVATER)
                    t_name = st.selectbox("Ziel wählen:", targets, key="sel_2")
                    if st.button("Karte geheim ansehen", key="btn_2_show"):
                        st.session_state["show_card_active"] = True

                    if st.session_state.get("show_card_active"):
                        card = players[t_name]["hand"][0]
                        st.info(f"**{t_name}** hält diese Karte:")
                        st.image(get_card_image(card), width=150)
                        st.write(f"Name: {get_card_display_name(card['val'], card['color'])}")
                        
                        if is_doubt and state["deck"]:
                            st.warning("✨ Zweifel-Bonus: Du darfst eine Karte extra ziehen!")

                        if st.button("Verstanden & Zug beenden", key="btn_2_fin"):
                            if is_doubt and state["deck"]:
                                me["hand"].append(state["deck"].pop())
                            st.session_state["show_card_active"] = False
                            state["phase"] = "NEXT"
                            save(state)
                            st.rerun()

                elif val == 3: # DUELL
                    t_name = st.selectbox("Ziel wählen:", targets, key="sel_3")
                    if st.button("Duell starten", key="btn_3"):
                        v1 = me["hand"][0]["val"]
                        v2 = players[t_name]["hand"][0]["val"]
                        if v1 > v2:
                            players[t_name]["active"] = False
                            st.success(f"Du hast gewonnen! {t_name} ist raus.")
                        elif v2 > v1:
                            me["active"] = False
                            st.error("Du hast das Duell verloren und bist raus!")
                        elif v1 == v2:
                            if is_doubt:
                                players[t_name]["active"] = False
                                st.success("Gleichstand! Dank Zweifel-Bonus gewinnst du.")
                            else:
                                st.info("Gleichstand! Nichts passiert.")
                        state["phase"] = "NEXT"
                        save(state)
                        st.rerun()

                elif val == 5: # AUSTAUSCH
                    t_name = st.selectbox("Ziel wählen:", targets, key="sel_5")
                    if st.button("Austausch erzwingen", key="btn_5"):
                        players[t_name]["discard_stack"].append(players[t_name]["hand"].pop())
                        if state["deck"]:
                            players[t_name]["hand"].append(state["deck"].pop())
                        state["phase"] = "NEXT"
                        save(state)
                        st.rerun()

                elif val == 6: # TAUSCH
                    t_name = st.selectbox("Ziel wählen:", targets, key="sel_6")
                    if is_doubt:
                        st.write("Zweifel-Bonus: Du siehst die Handkarte vor dem Tausch:")
                        c_target = players[t_name]["hand"][0]
                        st.write(f"**{t_name}** hält: {get_card_display_name(c_target['val'], c_target['color'])}")
                    
                    if st.button("Karten blind tauschen", key="btn_6"):
                        me["hand"][0], players[t_name]["hand"][0] = players[t_name]["hand"][0], me["hand"][0]
                        state["phase"] = "NEXT"
                        save(state)
                        st.rerun()

# --- ÜBERGANG ZUM NÄCHSTEN ZUG (AUSSERHALB DER EFFECT-PHASE) ---

if state.get("started") and state["phase"] == "NEXT":
    # 1. Extrazug-Logik (Karte 1 Rot)
    if st.session_state.get("extra_turn_granted"):
        st.warning("Du hast einen Extrazug durch den Zweifelsfall-Bonus!")
        col1, col2 = st.columns(2)
        if col1.button("✅ Extrazug nutzen", key="extra_yes"):
            st.session_state["extra_turn_granted"] = False
            state["phase"] = "TEST" # Zurück zur Prüfung (8er etc.)
            save(state)
            st.rerun()
        if col2.button("❌ Auf Extrazug verzichten", key="extra_no"):
            st.session_state["extra_turn_granted"] = False
            # Code läuft weiter zum normalen Wechsel
        else:
            st.stop()

    # 2. Den nächsten aktiven Spieler finden
    current_idx = state["turn_idx"]
    next_idx = (current_idx + 1) % len(order)
    
    safety_counter = 0
    while not players[order[next_idx]]["active"] and safety_counter < len(order):
        next_idx = (next_idx + 1) % len(order)
        safety_counter += 1
    
    # 3. Status für neue Runde setzen
    state["turn_idx"] = next_idx
    state["phase"] = "TEST" 
    state["active_doubt"] = False
    
    # Schutz des Spielers aufheben, der JETZT dran kommt
    players[order[next_idx]]["protected"] = False
    
    state["log"].append(f"Zug beendet. {order[next_idx]} ist am Zug.")
    save(state)
    st.rerun()
                                
# --- BLOCK 8: RUNDENENDE & SIEGERERMITTLUNG ---

if state.get("started", False) and state["phase"] == "ROUND_END":
    st.header("🏁 Das Rundenende")
    
    # 1. ZWEIKARTEN-WAHL (Regel für 0 oder 2-Rot)
    # Jeder aktive Spieler, der 2 Karten hat, muss eine wählen
    active_players = [n for n in order if players[n]["active"]]
    needs_to_choose = [n for n in active_players if len(players[n]["hand"]) > 1]

    if needs_to_choose:
        current_chooser = needs_to_choose[0]
        if st.session_state.user == current_chooser:
            st.warning("Du hast zwei Karten! Wähle eine für den Vergleich aus.")
            cols = st.columns(2)
            for i, card in enumerate(players[current_chooser]["hand"]):
                with cols[i]:
                    st.image(get_card_image(card), use_container_width=True)
                    if st.button(f"Diese Karte wählen", key=f"final_choice_{i}"):
                        # Die gewählte Karte behalten, die andere abwerfen
                        chosen_card = players[current_chooser]["hand"].pop(i)
                        players[current_chooser]["hand"] = [chosen_card]
                        save(state); st.rerun()
        else:
            st.info(f"Warten auf {current_chooser}, bis eine Karte gewählt wurde...")
        st.stop()

    # 2. DER FINALE VERGLEICH
    if st.button("Ergebnis anzeigen"):
        results = []
        for name in active_players:
            final_card = players[name]["hand"][0]
            val = final_card["val"]
            
            # Die giftige 0 Regel
            if val == 0:
                score = -1 # Verliert sofort
            else:
                # Score berechnen: Wert der Karte + (Punkte im Stapel / 100 für Gleichstand)
                discard_score = sum([c["val"] for c in players[name]["discard_stack"]])
                score = val + (discard_score / 100.0)
            
            results.append({"name": name, "score": score, "val": val})

        # Sortieren nach Score
        results.sort(key=lambda x: x["score"], reverse=True)
        winner = results[0]["name"]
        
        # Sieg anzeigen
        st.balloons()
        st.success(f"🏆 {winner} hat die Runde gewonnen!")
        
        for res in results:
            status = "💀 (Giftige 0!)" if res["score"] == -1 else f"Wert: {res['val']}"
            st.write(f"**{res['name']}**: {status}")

        if st.button("Nächste Runde vorbereiten"):
            # Spielzustand zurücksetzen
            state.update({
                "started": False,
                "phase": "LOBBY",
                "deck": [],
                "order": order # Reihenfolge bleibt gleich
            })
            # Siegmarker erhöhen
            players[winner]["markers"] += 1
            # Hände leeren
            for p in players.values():
                p["hand"] = []
                p["discard_stack"] = []
                p["active"] = True
            save(state); st.rerun()

# --- BLOCK 9: GAME OVER (Spezialsieg der 8) ---
if state.get("phase") == "GAME_OVER":
    st.balloons()
    st.header(f"👑 SPEZIALSIEG!")
    st.success(f"{state.get('winner')} hat durch die Rote 8 sofort gewonnen!")
    if st.button("Zurück zur Lobby"):
        state.update({"started": False, "phase": "LOBBY"})
        save(state); st.rerun()

# Ganz unten in deiner app.py, außerhalb jeglicher Einrückung:

st.divider() # Eine Trennlinie
with st.container():
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("🔄 Seite neu laden", use_container_width=True):
            st.rerun()
    with c1:
        st.caption("Spiel-ID: " + st.session_state.get("gid", "Unbekannt"))

# Optional: Ein fixer Button in der Sidebar (bleibt immer links sichtbar)
with st.sidebar:
    st.header("Menü")
    if st.button("📜 Spielregeln"):
        st.info("Hier stehen die Regeln für den Zweifelsfall...")
    if st.button("🚪 Raum verlassen"):
        st.session_state.clear()
        st.rerun()
