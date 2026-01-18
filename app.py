import streamlit as st
import random
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

def save(s):
    """Speichert den Spielzustand."""
    db.collection("games").document(st.session_state.gid).set(s)

def get_card_image(card):
    # Der Pfad, unter dem das Bild gesucht wird
    path = f"assets/card_{card['val']}_{card['color']}.png"
    
    # Prüfen, ob die Datei wirklich existiert
    if os.path.exists(path):
        return path
    else:
        # Falls das Bild fehlt: Ein grauer Platzhalter mit Text
        return f"https://via.placeholder.com/300x450.png?text=Karte+{card['val']}+{card['color']}+fehlt"
    
# --- BLOCK 2: LOGIN & SYNCHRONISATION ---

# 1. Login-Maske (Wird angezeigt, wenn der User noch nicht bekannt ist)
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

# 2. Echtzeit-Aktualisierung
# Die App prüft alle 3 Sekunden, ob es Änderungen in der Datenbank gibt
st_autorefresh(interval=3000, key="sync_refresh")

# Verbindung zum spezifischen Dokument in Firestore
doc_ref = db.collection("games").document(st.session_state.gid)
state = doc_ref.get().to_dict()

# 3. Raum-Initialisierung
if not state:
    if st.button("Neuen Spielraum eröffnen"):
        state = {
            "started": False,
            "host": st.session_state.user, # Der Ersteller wird fest als Host gespeichert
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

# 4. Globale Variablen für die folgenden Blöcke bereitstellen
players = state.get("players", {})
order = state.get("order", [])
host_name = state.get("host")

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

# --- BLOCK 4: DAS SPIELFELD (MITspieler-GRAFIKEN & NAMEN) ---

if state.get("started", False):
    # Hilfsvariablen
    players = state["players"]
    order = state["order"]
    curr_p_name = order[state["turn_idx"]]
    
    st.title("⚖️ ZWEIFELSFALL")

    # 1. SPIELFELD: Übersicht der Mitspieler in Spalten
    cols = st.columns(len(order))

    for i, name in enumerate(order):
        p_data = players[name]
        with cols[i]:
            # Wer ist aktuell am Zug?
            is_turn = (name == curr_p_name)
            border_color = "#FF4B4B" if is_turn else "#333"
            
            # Name des Spielers und Status-Indikator
            st.markdown(f"""
                <div style="text-align: center; border-bottom: 3px solid {border_color}; padding-bottom: 5px; margin-bottom: 10px;">
                    <b style="font-size: 1.1em;">{name}</b>
                </div>
            """, unsafe_allow_html=True)

            # Icons für Schutz oder Ausscheiden
            status_info = ""
            if not p_data["active"]: status_info += "💀 "
            if p_data.get("protected"): status_info += "🛡️ "
            if status_info: st.write(status_info)

            # Anzeige der obersten Karte im Ablagestapel
            if p_data["discard_stack"]:
                top_card = p_data["discard_stack"][-1]
                
                # Grafik anzeigen
                st.image(get_card_image(top_card), use_container_width=True)
                
                # Name der Karte unter der Grafik anzeigen
                c_name = get_card_display_name(top_card['val'], top_card['color'])
                st.markdown(f"<p style='text-align:center; font-size:0.9em; font-weight:bold; color:#ccc;'>{c_name}</p>", unsafe_allow_html=True)
            else:
                # Platzhalter für leeren Stapel
                st.markdown("""
                    <div style="aspect-ratio: 2/3; border: 2px dashed #444; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #444; font-size: 0.8em;">
                        Leer
                    </div>
                """, unsafe_allow_html=True)
            
            # Siegmarker
            st.markdown(f"<p style='text-align:center;'>⚪ {p_data['markers']}</p>", unsafe_allow_html=True)

    st.divider()

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
if state.get("started", False) and state["phase"] == "DRAW":
    if curr_p_name == st.session_state.user and len(me["hand"]) < 2:
        if st.button("🎴 Karte ziehen", use_container_width=True, type="primary"):
            if state["deck"]:
                me["hand"].append(state["deck"].pop())
                save(state); st.rerun()
            else:
                state["phase"] = "ROUND_END"
                save(state); st.rerun()

# --- BLOCK 7: FINALE KARTEN-EFFEKTE ---

if state.get("started", False) and state["phase"] == "EFFECT":
    if curr_p_name == st.session_state.user:
        # Die gespielte Karte liegt oben auf dem Ablagestapel
        played_card = me["discard_stack"][-1]
        val = played_card["val"]
        is_doubt = state.get("active_doubt", False) # Wurde in Block 5 gesetzt
        
        st.subheader(f"Effekt: {get_card_display_name(val, played_card['color'])}")

        # --- WERTE OHNE ZIELWAHL (0, 4, 7, 8) ---
        if val in [0, 4, 7, 8]:
            if val == 0:
                st.info("Haupteffekt: Du musst eine Karte ziehen.")
                if st.button("Karte ziehen & Zug beenden"):
                    if state["deck"]: me["hand"].append(state["deck"].pop())
                    state["phase"] = "NEXT"; save(state); st.rerun()
            
            elif val == 4:
                me["protected"] = True
                st.success("Immunität aktiv! Keiner kann dich als Ziel wählen.")
                if st.button("Zug beenden"): state["phase"] = "NEXT"; save(state); st.rerun()
            
            elif val == 8 and played_card["color"] == "Blau":
                st.error("Regelverstoß: Die blaue 8 darf niemals freiwillig gelegt werden!")
                # (Hier könnte man eine Strafe einbauen oder den Zug rückgängig machen)
                if st.button("Zug dennoch beenden"): state["phase"] = "NEXT"; save(state); st.rerun()
            
            else: # Karte 7 oder rote 8
                if st.button("Zug beenden"): state["phase"] = "NEXT"; save(state); st.rerun()

        # --- WERTE MIT ZIELWAHL (1, 2, 3, 5, 6) ---
        else:
            # Ziele filtern (aktiv und nicht geschützt)
            targets = [n for n in order if n != st.session_state.user and players[n]["active"] and not players[n].get("protected")]
            
            if not targets:
                st.warning("Keine gültigen Ziele verfügbar.")
                if st.button("Effekt verfällt & Beenden"): state["phase"] = "NEXT"; save(state); st.rerun()
            else:
                if val == 1: # ELIMINATOR
                    t_name = st.selectbox("Ziel wählen:", targets)
                    guess = st.number_input("Zahl raten (0-8):", 0, 8)
                    if st.button("Raten"):
                        if players[t_name]["hand"][0]["val"] == guess:
                            players[t_name]["active"] = False
                            st.success(f"Erfolg! {t_name} ist ausgeschieden.")
                            # Zweifelsfall-Bonus: Freiwilliger Extrazug
                            if is_doubt: st.session_state["extra_turn_granted"] = True
                        else:
                            st.error(f"Falsch! {t_name} hält nicht die {guess}.")
                        state["phase"] = "NEXT"; save(state); st.rerun()

                elif val == 2: # INFORMATION
                    t_name = st.selectbox("Ziel wählen:", targets)
                    if st.button("Karte geheim ansehen"):
                        card = players[t_name]["hand"][0]
                        st.info(f"{t_name} hält: {get_card_display_name(card['val'], card['color'])}")
                        # Zweifelsfall-Bonus: Zusätzliche Karte ziehen
                        if is_doubt and state["deck"]:
                            me["hand"].append(state["deck"].pop())
                            st.toast("Zweifel-Bonus: Eine Karte extra gezogen!")
                        if st.button("Verstanden"): state["phase"] = "NEXT"; save(state); st.rerun()

                elif val == 3: # DUELL
                    t_name = st.selectbox("Ziel wählen:", targets)
                    if st.button("Duell starten"):
                        v1, v2 = me["hand"][0]["val"], players[t_name]["hand"][0]["val"]
                        if v1 > v2: players[t_name]["active"] = False
                        elif v2 > v1: me["active"] = False
                        elif v1 == v2 and is_doubt: # Zweifel-Bonus: Sieg bei Gleichstand
                            players[t_name]["active"] = False
                        state["phase"] = "NEXT"; save(state); st.rerun()

                elif val == 5: # AUSTAUSCH
                    num_targets = 2 if is_doubt else 1
                    t_names = st.multiselect(f"Wähle {num_targets} Ziel(e):", targets, max_selections=num_targets)
                    if st.button("Austausch erzwingen") and len(t_names) == num_targets:
                        for tn in t_names:
                            # Karte ablegen (ohne Effekt) und neu ziehen
                            players[tn]["discard_stack"].append(players[tn]["hand"].pop())
                            if state["deck"]: players[tn]["hand"].append(state["deck"].pop())
                        state["phase"] = "NEXT"; save(state); st.rerun()

                elif val == 6: # TAUSCH
                    if is_doubt:
                        st.write("Zweifel-Bonus: Du siehst alle Handkarten:")
                        for n in targets:
                            c = players[n]["hand"][0]
                            st.write(f"**{n}:** {get_card_display_name(c['val'], c['color'])}")
                    t_name = st.selectbox("Tauschpartner wählen:", targets)
                    if st.button("Karten blind tauschen"):
                        me["hand"][0], players[t_name]["hand"][0] = players[t_name]["hand"][0], me["hand"][0]
                        state["phase"] = "NEXT"; save(state); st.rerun()

    # --- ÜBERGANG ZUM NÄCHSTEN ZUG ---
    if state["phase"] == "NEXT":
        # Abfrage des freiwilligen Extrazugs (Karte 1 Rot)
        if st.session_state.get("extra_turn_granted"):
            col_y, col_n = st.columns(2)
            if col_y.button("✅ Extrazug nutzen"):
                st.session_state["extra_turn_granted"] = False
                state["phase"] = "TEST"; save(state); st.rerun()
            if col_n.button("❌ Auf Extrazug verzichten"):
                st.session_state["extra_turn_granted"] = False
                # Geht dann in den normalen Wechsel unten
            else: st.stop()

        # Normaler Wechsel zum nächsten aktiven Spieler
        next_idx = (state["turn_idx"] + 1) % len(order)
        while not players[order[next_idx]]["active"]:
            next_idx = (next_idx + 1) % len(order)
        
        state["turn_idx"] = next_idx
        state["phase"] = "TEST"
        save(state); st.rerun()

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
