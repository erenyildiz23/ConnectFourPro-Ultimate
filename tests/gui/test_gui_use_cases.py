"""
GUI uctan uca testleri: Pygame istemcisi (ekransiz) gercek sunucuya baglanir.
Her test bir use case'in (docs/USE_CASES.md) ana akisini kullanici gibi oynatir.
"""

import pytest

pygame = pytest.importorskip("pygame")

import requests  # noqa: E402

from conftest import wait_until  # noqa: E402
from game_core import PLAYER1_PIECE  # noqa: E402

pytestmark = pytest.mark.gui


def pump(guis, condition, timeout=10.0):
    """GUI'lerin ana dongusunu kosul saglanana kadar calistirir."""
    guis = guis if isinstance(guis, (list, tuple)) else [guis]

    def step():
        for g in guis:
            g.tick()
        return condition()
    assert wait_until(step, timeout=timeout, interval=0.005), \
        "GUI beklenen duruma gelmedi: " + " | ".join(f"{g.username}:{g.state}:{g.status_text!r}" for g in guis)


@pytest.fixture
def make_gui(live_server_url, server):
    import gui_app
    created = []

    def factory(url=live_server_url):
        g = gui_app.ConnectFourGUI(server_url=url)
        created.append(g)
        return g

    yield factory
    for g in created:
        g.invalidate_ai_session()
        g._cancel_analysis()
        g.network.disconnect()


def type_credentials(gui, username, password):
    gui.input_fields['username']['value'] = username
    gui.input_fields['password']['value'] = password


def register(gui, username, password="pw123"):
    type_credentials(gui, username, password)
    gui.handle_button_click('DO_REGISTER')
    pump(gui, lambda: gui.state == "MENU")


def play_turn(gui, others, col):
    """Sirasi gelen oyuncu olarak tiklar; hamlenin herkese ulasmasini bekler."""
    pump([gui] + others, gui.can_human_move)
    expected = len(gui.game.move_history) + 1
    gui.handle_click(col)
    pump([gui] + others, lambda: all(len(g.game.move_history) >= expected and not g.animating
                                     for g in [gui] + others))


# =============================================================================
# UC-01 / UC-02 / UC-03 / UC-04: Hesap islemleri
# =============================================================================

@pytest.mark.db
class TestAccountUseCases:
    def test_uc01_register_and_uc04_logout(self, make_gui, database):
        g = make_gui()
        register(g, "alice")
        assert g.username == "alice" and g.user_elo == 1200 and not g.is_guest
        assert "Kayit basarili" in g.status_text
        g.handle_button_click('LOGOUT')
        assert g.state == "LOGIN" and g.username == ""

    def test_uc01_duplicate_username(self, make_gui, database):
        database.create_user("alice", "pw123")
        g = make_gui()
        type_credentials(g, "alice", "other")
        g.handle_button_click('DO_REGISTER')
        pump(g, lambda: not g.auth_pending)
        assert g.state == "LOGIN" and "zaten alinmis" in g.status_text

    def test_uc02_login(self, make_gui, database):
        database.create_user("alice", "pw123")
        g = make_gui()
        type_credentials(g, "alice", "pw123")
        g.handle_button_click('DO_LOGIN')
        pump(g, lambda: g.state == "MENU")
        assert g.username == "alice" and "Hosgeldin" in g.status_text

    def test_uc02_wrong_password(self, make_gui, database):
        database.create_user("alice", "pw123")
        g = make_gui()
        type_credentials(g, "alice", "nope")
        g.handle_button_click('DO_LOGIN')
        pump(g, lambda: not g.auth_pending)
        assert g.state == "LOGIN" and "Yanlis" in g.status_text

    def test_uc02_empty_fields_rejected_locally(self, make_gui):
        g = make_gui()
        g.handle_button_click('DO_LOGIN')
        assert g.state == "LOGIN" and not g.auth_pending and "gerekli" in g.status_text


def test_uc02_server_unreachable(make_gui):
    g = make_gui(url="http://127.0.0.1:1")
    type_credentials(g, "alice", "pw123")
    g.handle_button_click('DO_LOGIN')
    pump(g, lambda: not g.auth_pending)
    assert g.state == "LOGIN" and g.status_text == "Sunucuya baglanilamadi!"


def test_uc03_guest(make_gui):
    g = make_gui()
    g.handle_button_click('GUEST')
    assert g.state == "MENU" and g.is_guest and g.username.startswith("Misafir_")


# =============================================================================
# UC-05: Yapay zekaya karsi oyna
# =============================================================================

class TestPlayVsAI:
    @pytest.mark.parametrize("difficulty", [2, 4])
    def test_uc05_full_game_against_ai(self, make_gui, difficulty):
        g = make_gui()
        g.handle_button_click('GUEST')
        g.handle_button_click('AI')
        assert g.state == "AI_SELECT"
        g.handle_button_click(f'AI_{difficulty}')
        assert g.state == "PLAYING_AI" and g.ai.depth == difficulty

        human_cols = [3, 2, 4, 1, 5, 0, 6] * 6
        while not g.game.game_over:
            pump(g, lambda: g.can_human_move() or g.game.game_over, timeout=15)
            if g.game.game_over:
                break
            col = next(c for c in human_cols if g.game.is_valid_location(c))
            human_cols.remove(col)
            g.handle_click(col)
            pump(g, lambda: not g.animating)

        assert g.status_text in ("Kazandin!", "AI kazandi!", "Berabere!")
        # AI hamleleri kurallara uygun ve sirayla yapildi
        assert all(0 <= c < 7 for c in g.game.move_history)

    def test_uc05_ai_cannot_move_for_human(self, make_gui):
        g = make_gui()
        g.handle_button_click('GUEST')
        g.start_ai_game(2)
        g.handle_click(3)
        g.handle_click(4)   # Animasyon/AI sirasinda ikinci tik yok sayilmali
        pump(g, lambda: len(g.game.move_history) == 2 and not g.animating, timeout=15)
        assert g.game.move_history[0] == 3 and g.game.current_player == PLAYER1_PIECE

    def test_uc05_leaving_while_ai_thinks_discards_stale_move(self, make_gui):
        g = make_gui()
        g.handle_button_click('GUEST')
        g.start_ai_game(6)
        g.handle_click(0)
        pump(g, lambda: g.ai_thinking)
        g.handle_button_click('BACK')
        assert g.state == "MENU"
        for _ in range(100):   # AI thread'i bitse bile hamlesi uygulanmamali
            g.tick()
        assert g.game.move_history == [] and g.pending_ai_move is None


# =============================================================================
# UC-06..UC-10, UC-12, UC-13, UC-16: Online oyun (iki istemci + seyirci)
# =============================================================================

@pytest.mark.db
class TestOnlineUseCases:
    def _start_online_match(self, make_gui):
        g1, g2 = make_gui(), make_gui()
        register(g1, "alice")
        register(g2, "bob")

        # UC-06: oda olustur
        g1.handle_button_click('LOBBY')
        g1.handle_button_click('CREATE')
        pump([g1], lambda: g1.state == "WAITING" and g1.room_id)
        room = g1.room_id

        # UC-07: lobide odayi gor, UC-08: katil
        g2.handle_button_click('LOBBY')
        pump([g1, g2], lambda: any(x['room_id'] == room for x in g2.active_games))
        g2.handle_button_click(f'JOIN_{room}')
        pump([g1, g2], lambda: g1.state == g2.state == "PLAYING_ONLINE")
        assert g1.opponent_name == "bob" and g2.opponent_name == "alice"
        assert g1.my_piece == 1 and g2.my_piece == 2
        return g1, g2, room

    def test_uc09_uc13_uc16_full_online_match(self, make_gui, database, monkeypatch):
        import gui_app
        # Ozellik testi: analiz derinligi hiz icin dusuruldu (D6 hizi benchmark'ta olculur)
        monkeypatch.setattr(gui_app, "ANALYSIS_DEPTH", 3)
        g1, g2, room = self._start_online_match(make_gui)

        # UC-10: ucuncu istemci izler
        s = make_gui()
        s.handle_button_click('GUEST')
        s.handle_button_click('LOBBY')
        pump([g1, g2, s], lambda: any(x['room_id'] == room and x['status'] == 'PLAYING' for x in s.active_games))
        s.handle_button_click(f'SPECTATE_{room}')
        pump([g1, g2, s], lambda: s.is_spectator and s.state == "SPECTATING" and s.spectate_names[0] == "alice")

        # UC-09: siradaki oyuncu disinda kimse hamle yapamaz
        g2.handle_click(1)
        assert g2.game.move_history == []

        for i, col in enumerate([0, 1, 0, 1, 0, 1, 0]):
            mover, other = (g1, g2) if i % 2 == 0 else (g2, g1)
            play_turn(mover, [other, s], col)

        pump([g1, g2, s], lambda: "ELO" in g1.status_text and "ELO" in g2.status_text
             and "kazandi" in s.status_text.lower())
        # UC-13: ELO ve sonuc
        assert g1.status_text.startswith("Kazandin!") and "ELO +15 (1215)" in g1.status_text
        assert g2.status_text.startswith("Kaybettin.") and "ELO -15 (1185)" in g2.status_text
        assert s.status_text == "Kirmizi kazandi!"
        assert g1.game.get_winning_positions() == [(0, 0), (0, 1), (0, 2), (0, 3)]
        assert s.game.move_history == g1.game.move_history == g2.game.move_history
        assert database.get_user_by_username("alice")['rating'] == 1215

        # UC-16: hamle analizi (her iki oyuncunun hamleleri)
        pump([g1], lambda: g1.analysis_summary and g1.analysis_summary['total_moves'] == 7, timeout=30)
        assert 0 <= g1.analysis_summary['my_accuracy'] <= 100

    def test_uc12_leaving_requires_confirmation_and_forfeits(self, make_gui, database):
        g1, g2, room = self._start_online_match(make_gui)
        play_turn(g1, [g2], 3)

        g1.handle_button_click('BACK')
        assert g1.state == "PLAYING_ONLINE" and "hukmen" in g1.status_text   # onay istendi
        g1.handle_button_click('BACK')
        assert g1.state == "MENU"

        pump([g1, g2], lambda: "terk etti" in g2.status_text)
        assert g2.status_text.startswith("Rakip oyunu terk etti - Kazandin!")
        assert database.get_user_by_username("bob")['wins'] == 1

    def test_uc06_cancel_waiting_room(self, make_gui, server, database):
        g = make_gui()
        register(g, "alice")
        g.handle_button_click('LOBBY')
        g.handle_button_click('CREATE')
        pump(g, lambda: g.room_id)
        room = g.room_id
        g.handle_button_click('BACK')
        assert g.state == "MENU"
        assert wait_until(lambda: room not in server.GAMES)


# =============================================================================
# UC-14 / UC-15: Liderlik tablosu ve mac gecmisi
# =============================================================================

@pytest.mark.db
class TestInformationUseCases:
    def test_uc14_leaderboard(self, make_gui, database):
        for name in ("alice", "bob", "carol"):
            database.create_user(name, "pw123")
        database.update_elo_by_username("carol", "alice")
        g = make_gui()
        g.handle_button_click('GUEST')
        g.handle_button_click('LEADERBOARD')
        pump(g, lambda: g.leaderboard_data is not None)
        assert [p['username'] for p in g.leaderboard_data] == ["carol", "bob", "alice"]

    def test_uc15_match_history(self, make_gui, database):
        database.create_user("bob", "pw123")
        g = make_gui()
        register(g, "alice")
        database.record_game("alice", "bob", "alice", "[0, 1, 0, 1, 0, 1, 0]")
        database.record_game("bob", "alice", "bob", "[3]", end_reason="forfeit")
        g.handle_button_click('HISTORY')
        pump(g, lambda: g.history_data is not None)
        assert [x['result'] for x in g.history_data] == ['loss', 'win']
        assert g.history_data[0]['end_reason'] == 'forfeit'

    def test_uc15_history_not_available_for_guest(self, make_gui):
        g = make_gui()
        g.handle_button_click('GUEST')
        g.handle_button_click('HISTORY')
        g.tick()
        assert g.state == "HISTORY" and g.history_data is None


class TestEventOrdering:
    """Socket.IO istemcisi olaylari ayri thread'lerde isler; sira karisabilir."""

    def _online_gui(self, make_gui, my_piece=2):
        g = make_gui(url="http://127.0.0.1:1")
        g.username, g.state, g.my_piece, g.room_id = "bob", "PLAYING_ONLINE", my_piece, "AB12C"
        return g

    @staticmethod
    def _event(moves):
        from game_core import ConnectFourGame
        data = ConnectFourGame.from_moves(moves).to_dict()
        data['col'] = moves[-1]
        return data

    def _settle(self, g):
        for _ in range(200):
            g.tick()
            if not g.animating:
                return

    def test_out_of_order_and_stale_moves(self, make_gui):
        g = self._online_gui(make_gui, my_piece=1)
        g.on_move_made(self._event([3]))          # kendi hamlemin yankisi (local bos) -> atlama ile
        self._settle(g)
        g.on_move_made(self._event([3, 4, 2]))    # once yeni olay geldi
        g.on_move_made(self._event([3, 4]))       # sonra eski olay
        self._settle(g)
        assert g.game.move_history == [3, 4, 2]

    def test_final_move_animated_with_winners_color(self, make_gui):
        g = self._online_gui(make_gui, my_piece=2)
        g.game = __import__('game_core').ConnectFourGame.from_moves([0, 1, 0, 1, 0, 1])
        g.on_move_made(self._event([0, 1, 0, 1, 0, 1, 0]))
        assert g.animating and g.anim_piece == PLAYER1_PIECE
        self._settle(g)
        assert g.game.game_over and g.game.winner == PLAYER1_PIECE

    def test_game_over_before_elo_update_still_shows_elo(self, make_gui):
        g = self._online_gui(make_gui, my_piece=2)
        g.on_game_over_network({'winner': 1, 'reason': 'normal', 'elo_changes': {'p1': 15, 'p2': -15},
                                'new_ratings': {'p1': 1215, 'p2': 1185}})
        assert g.status_text == "Kaybettin.  ELO -15 (1185)" and g.user_elo == 1185
        g.on_elo_update({'new_elo': 1185, 'change': -15})   # gec gelen olay mesaji bozmamali
        g.on_move_made(self._event([0, 1, 0, 1, 0, 1, 0]))   # son hamle en son geldi
        self._settle(g)
        assert g.status_text == "Kaybettin.  ELO -15 (1185)"


def test_live_server_uses_real_websocket(live_server_url):
    """Istemci HTTP long-polling'e dusmemeli (websocket-client kurulu olmali)."""
    import socketio
    assert requests.get(f"{live_server_url}/health").status_code == 200
    client = socketio.Client()
    client.connect(live_server_url, wait_timeout=5)
    try:
        assert client.transport() == 'websocket'
    finally:
        client.disconnect()
