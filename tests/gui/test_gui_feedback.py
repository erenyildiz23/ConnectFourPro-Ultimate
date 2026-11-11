"""
Arayuz geri bildirimi testleri (sunucu gerekmez): renk kontrasti, tas dusme animasyonu,
son hamle / inis isaretleri, sonuc basligi, sira vurgusu, klavye.
Cizimi suren durum ve geometri dogrulanir; piksel okunmaz.
"""

import pytest

pygame = pytest.importorskip("pygame")

import gui_app  # noqa: E402
from game_core import PLAYER1_PIECE, PLAYER2_PIECE, ConnectFourGame  # noqa: E402

pytestmark = pytest.mark.gui

COLORS = gui_app.COLORS


@pytest.fixture
def gui():
    """Sunucuya baglanmayan istemci (misafir, ana menude)."""
    g = gui_app.ConnectFourGUI(server_url="http://127.0.0.1:1")
    g.handle_button_click('GUEST')
    yield g
    g.invalidate_ai_session()
    g._cancel_analysis()
    g.network.disconnect()


def press(g, key, text=''):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=text))
    g.tick()


# =============================================================================
# Dugme yazisi kontrasti (WCAG 4.5:1)
# =============================================================================

class TestContrast:
    @pytest.mark.parametrize("fill", ['button', 'green', 'hover', 'gray', 'panel'])
    def test_button_label_is_readable_on_every_fill(self, fill):
        color = COLORS[fill]
        assert gui_app.contrast_ratio(gui_app.on_color(color), color) >= 4.5

    def test_disc_colours_unchanged(self):
        assert COLORS['red'] == (233, 69, 96) and COLORS['yellow'] == (241, 196, 15)

    def test_error_text_is_readable(self):
        for background in ('bg', 'panel'):
            assert gui_app.contrast_ratio(COLORS['error'], COLORS[background]) >= 4.5

    def test_contrast_formula(self):
        assert gui_app.contrast_ratio((255, 255, 255), (0, 0, 0)) == pytest.approx(21)
        assert gui_app.contrast_ratio((234, 234, 234), (46, 204, 113)) == pytest.approx(1.75, abs=0.01)


# =============================================================================
# Tas dusme animasyonu: sabit adimli yercekimi
# =============================================================================

class TestDropFeel:
    def _drop(self, g, row):
        g.start_ai_game(2)
        landed = []
        g.animate_drop(3, row, PLAYER1_PIECE, lambda: landed.append(True))
        ys = [g.anim_y]
        while g.animating:
            g.tick()
            ys.append(g.anim_y)
            assert len(ys) < 100
        return ys, landed

    def test_disc_accelerates_and_lands_within_budget(self, gui):
        ys, landed = self._drop(gui, row=0)
        deltas = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
        # Son kare hedefe kirpilir; digerlerinde adim surekli buyur (ivme)
        assert all(deltas[i + 1] > deltas[i] for i in range(len(deltas) - 2))
        assert len(deltas) == 22                     # alt satir: 0.37 sn (Unity ile ayni)
        assert ys[-1] == gui.anim_target_y == gui.cell_center(3, 0)[1]
        assert landed == [True]                      # geri cagri tam bir kez

    def test_top_row_drop_is_not_a_teleport(self, gui):
        ys, landed = self._drop(gui, row=5)
        assert len(ys) - 1 == 7 and landed == [True]

    def test_fast_forward_runs_callback_once(self, gui):
        gui.start_ai_game(2)
        landed = []
        gui.animate_drop(3, 0, PLAYER1_PIECE, lambda: landed.append(True))
        gui.tick()
        gui.finish_animation(natural=False)
        gui.finish_animation(natural=False)
        assert landed == [True] and not gui.animating and gui.anim_y == gui.anim_target_y


# =============================================================================
# Son hamle halkasi
# =============================================================================

class TestLastMoveMarker:
    @pytest.mark.parametrize("moves, cell", [
        ([], None),
        ([3, 3, 4], (4, 0)),
        ([3, 3], (3, 1)),
        ([0] * 6, (0, 5)),                       # dolu sutun
        ([0, 1, 0, 1, 0, 1, 0], None),           # kazanildi: dortlu vurgusu yeterli
    ])
    def test_last_move_cell(self, gui, moves, cell):
        gui.start_ai_game(2)
        gui.game = ConnectFourGame.from_moves(moves)
        assert gui.last_move_cell() == cell
        gui.tick()                               # cizim hata vermemeli

    def test_marker_follows_the_actual_last_move(self, gui):
        gui.start_ai_game(2)
        gui.handle_click(3)
        assert gui.last_move_cell() is None      # tas duserken isaret yok
        while gui.animating:
            gui.tick()
        assert gui.last_move_cell() == (3, 0)

    def test_marker_works_from_a_snapshot(self, gui):
        """Seyirci / yeniden baglanma: durum animasyonsuz yuklenir."""
        gui.state, gui.is_spectator = "SPECTATING", True
        gui.game.from_dict(ConnectFourGame.from_moves([2, 2, 5]).to_dict())
        assert gui.last_move_cell() == (5, 0)


# =============================================================================
# Hover: inis hucresi, kendi rengi, dolu sutun
# =============================================================================

class TestHover:
    def test_ghost_marks_landing_cell(self, gui):
        gui.start_ai_game(2)
        gui.hover_col = 3
        assert gui.ghost_cell() == (3, 0)
        gui.game = ConnectFourGame.from_moves([3, 3])
        assert gui.ghost_cell() == (3, 2)
        gui.hover_col = -1
        assert gui.ghost_cell() is None
        gui.tick()

    def test_hover_uses_own_colour(self, gui):
        gui.start_ai_game(2)
        assert gui.piece_color(gui.human_piece()) == COLORS['red']
        gui.state, gui.my_piece = "PLAYING_ONLINE", PLAYER2_PIECE
        assert gui.piece_color(gui.human_piece()) == COLORS['yellow']

    def test_full_column_shows_no_ghost_and_explains_click(self, gui):
        gui.start_ai_game(2)
        gui.game = ConnectFourGame.from_moves([0] * 6)     # sira kirmizida, sutun 0 dolu
        gui.hover_col = 0
        assert gui.ghost_cell() is None
        gui.handle_click(0)
        assert gui.game.move_history == [0] * 6 and not gui.animating
        assert gui.status_text == "Bu sutun dolu!"
        for _ in range(20):
            gui.tick()

    def test_no_ghost_and_no_full_column_status_when_not_my_turn(self, gui):
        gui.start_ai_game(2)
        gui.game = ConnectFourGame.from_moves([0] * 6)
        gui.ai_thinking = True
        gui.set_status("AI dusunuyor...")
        gui.hover_col = 3
        assert gui.ghost_cell() is None
        gui.handle_click(0)
        assert gui.status_text == "AI dusunuyor..."
        gui.ai_thinking = False


# =============================================================================
# Oyun sonu: baslik, soluk taslar, renkli durum satiri
# =============================================================================

P1_WIN = [0, 1, 0, 1, 0, 1, 0]
P2_WIN = [6, 1, 0, 1, 0, 1, 2, 1]          # sari dikey dortlu


def online(g, my_piece, moves=()):
    g.state, g.my_piece, g.room_id, g.is_spectator = "PLAYING_ONLINE", my_piece, "AB12C", False
    g.game = ConnectFourGame.from_moves(list(moves))
    return g


class TestResultPayoff:
    def test_no_headline_before_game_over(self, gui):
        assert gui.result_headline() is None                       # menude
        gui.start_ai_game(2)
        assert gui.result_headline() is None
        gui.tick()

    @pytest.mark.parametrize("my_piece, expected", [
        (PLAYER1_PIECE, ("KAZANDIN!", COLORS['green'])),
        (PLAYER2_PIECE, ("KAYBETTIN", COLORS['red'])),
    ])
    def test_online_headline(self, gui, my_piece, expected):
        online(gui, my_piece, P1_WIN)
        assert gui.result_headline() == expected
        for _ in range(30):
            gui.tick()

    def test_ai_headline(self, gui):
        gui.start_ai_game(2)
        gui.game = ConnectFourGame.from_moves(P1_WIN)
        assert gui.result_headline() == ("KAZANDIN!", COLORS['green'])
        gui.game = ConnectFourGame.from_moves(P2_WIN)
        assert gui.game.winner == PLAYER2_PIECE
        assert gui.result_headline() == ("AI KAZANDI", COLORS['red'])

    def test_forfeit_headline_and_tone(self, gui):
        online(gui, PLAYER2_PIECE, [3])
        gui.on_game_over_network({'winner': 2, 'reason': 'forfeit'})
        assert gui.result_headline() == ("KAZANDIN!", COLORS['green'])
        assert gui.status_tone == 'good' and gui.status_color() == COLORS['green']

    def test_loss_status_is_red_and_survives_late_final_move(self, gui):
        online(gui, PLAYER2_PIECE, P1_WIN[:-1])
        gui.on_game_over_network({'winner': 1, 'reason': 'normal'})
        assert gui.status_tone == 'bad' and gui.status_color() == COLORS['error']
        gui.set_status("Rakibin sirasi...")
        gui.game = ConnectFourGame.from_moves(P1_WIN)
        gui.handle_game_over()                                     # sunucunun sonucu tonuyla geri gelir
        assert gui.status_text == "Kaybettin." and gui.status_tone == 'bad'

    def test_spectator_and_draw_headlines(self, gui):
        import conftest
        online(gui, 0, P2_WIN)
        gui.state, gui.is_spectator = "SPECTATING", True
        assert gui.result_headline() == ("SARI KAZANDI", COLORS['yellow'])
        online(gui, PLAYER1_PIECE, conftest.DRAW_SEQUENCE)
        assert gui.game.game_over and gui.game.winner is None
        assert gui.result_headline() == ("BERABERE", COLORS['white'])
        gui.tick()

    def test_only_non_winning_discs_are_dimmed(self, gui):
        online(gui, PLAYER1_PIECE, P1_WIN[:-1])
        assert gui.disc_color(0, 0) == COLORS['red'] and gui.disc_color(1, 0) == COLORS['yellow']
        assert gui.disc_color(3, 0) is None
        gui.game = ConnectFourGame.from_moves(P1_WIN)
        assert all(gui.disc_color(0, row) == COLORS['red'] for row in range(4))
        dimmed = gui.disc_color(1, 0)
        assert dimmed == gui_app.blend(COLORS['yellow'], COLORS['cell_bg'], gui_app.DIM_AMOUNT)
        assert sum(dimmed) < sum(COLORS['yellow']) * 0.6

    def test_status_tone_replaces_substring_colouring(self, gui):
        gui.logout()
        gui.handle_button_click('DO_LOGIN')                        # bos alanlar
        assert gui.status_tone == 'bad' and gui.status_color(COLORS['gray']) == COLORS['error']
        gui.set_status("Yenilendi")
        assert gui.status_color(COLORS['gray']) == COLORS['gray']
        gui.set_status("Kayit basarili!", 'good')
        assert gui.status_color(COLORS['gray']) == COLORS['green']
        gui.tick()


# =============================================================================
# Sira isareti ve dugme vurgusu
# =============================================================================

class TestTurnCueAndButtons:
    def test_status_is_green_only_on_my_turn(self, gui):
        gui.start_ai_game(2)
        assert gui.status_color() == COLORS['green']
        gui.ai_thinking = True
        gui.set_status("AI dusunuyor...")
        assert gui.status_color() == COLORS['white']
        gui.ai_thinking = False
        online(gui, PLAYER2_PIECE, [3])
        gui.set_status("Oyuna geri donuldu. Senin siran!")
        assert gui.status_color() == COLORS['green']
        online(gui, PLAYER2_PIECE, [3, 3])
        assert gui.status_color() == COLORS['white']

    def test_band_sits_behind_the_player_to_move(self, gui):
        gui.start_ai_game(2)
        rect1, color1 = gui.turn_highlight()
        gui.game = ConnectFourGame.from_moves([3])
        rect2, color2 = gui.turn_highlight()
        assert rect2.y - rect1.y == 60 and rect1.x == rect2.x
        assert color1 == gui_app.blend(COLORS['panel'], COLORS['red'], gui_app.TURN_TINT)
        assert color2 == gui_app.blend(COLORS['panel'], COLORS['yellow'], gui_app.TURN_TINT)
        gui.tick()
        gui.game = ConnectFourGame.from_moves(P1_WIN)
        assert gui.turn_highlight() is None
        gui.tick()

    def test_button_under_pointer_is_highlighted(self, gui, monkeypatch):
        gui.tick()
        assert gui.hovered_button is None                          # fare (0, 0)'da
        bid, rect = gui.buttons[0]
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: rect.center)
        gui.tick()
        assert gui.hovered_button == rect
        assert gui_app.button_fill(COLORS['button'], True) == (212, 62, 90)
        assert gui_app.button_fill(COLORS['button']) == COLORS['button']
        assert gui_app.button_fill((250, 250, 250), True) == (255, 255, 255)
        gui.handle_mouse_click(rect.center)                        # tiklama ayni cagride calisir
        assert gui.state == "AI_SELECT"

    def test_back_label_and_target_depend_on_origin(self, gui):
        gui.start_ai_game(2)
        assert not gui.in_online_room()
        gui.handle_button_click('BACK')
        assert gui.state == "MENU"
        gui.state = "LEADERBOARD"
        gui.handle_button_click('BACK')
        assert gui.state == "MENU"
        online(gui, PLAYER1_PIECE, P1_WIN)
        assert gui.in_online_room()
        gui.active_games = [{'room_id': 'AB12C'}, {'room_id': 'ZZ999'}]
        gui.handle_button_click('BACK')
        assert gui.state == "LOBBY" and gui.active_games == [{'room_id': 'ZZ999'}]


# =============================================================================
# UC-11: kendi baglantinin kopmasi, geri donus, rakibin geri sayimi
# =============================================================================

class TestConnectionState:
    def test_lost_connection_blocks_moves_until_rejoin(self, gui):
        online(gui, PLAYER1_PIECE)
        assert gui.can_human_move()
        gui.on_connection_lost(gui.network)
        assert gui.connection_down and not gui.can_human_move()
        assert gui.status_text == "Baglanti koptu - yeniden baglaniliyor..." and gui.status_tone == 'bad'
        gui.handle_click(3)
        assert gui.game.move_history == [] and not gui.animating

        state = ConnectFourGame.from_moves([3, 4]).to_dict()
        gui.on_game_joined({'room_id': 'AB12C', 'player_piece': 1, 'role': 'player', 'rejoined': True,
                            'current_state': state, 'opponent_info': {'username': 'bob', 'rating': 1200}})
        assert not gui.connection_down and gui.can_human_move()
        assert gui.status_text == "Oyuna geri donuldu. Senin siran!"

    def test_event_from_replaced_connection_is_ignored(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_connection_lost(gui._new_network())      # menuye donuste birakilan eski baglanti
        assert not gui.connection_down and gui.status_text == ""

    def test_loss_after_game_over_or_outside_a_game_is_ignored(self, gui):
        gui.on_connection_lost(gui.network)             # menude
        assert not gui.connection_down and gui.status_text == ""
        online(gui, PLAYER1_PIECE, P1_WIN)
        gui.set_status("Kazandin!", 'good')
        gui.on_connection_lost(gui.network)
        assert not gui.connection_down and gui.status_text == "Kazandin!"

    def test_spectator_is_told_to_rejoin_from_lobby(self, gui):
        online(gui, 0, [3])
        gui.state, gui.is_spectator = "SPECTATING", True
        gui.on_connection_lost(gui.network)
        assert "Yayin baglantisi koptu" in gui.status_text and not gui.connection_down

    def test_long_reconnect_shows_non_final_hint_once(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_connection_lost(gui.network)
        gui.tick()
        assert gui.status_text == "Baglanti koptu - yeniden baglaniliyor..."
        gui.connection_lost_at -= gui_app.RECONNECT_WARN_SECONDS + 1
        gui.tick()
        assert "uzun suruyor" in gui.status_text and gui.connection_down
        gui.set_status("x")
        gui.tick()
        assert gui.status_text == "x"                   # ipucu tekrarlanmaz

    def test_rejoin_after_game_ended_shows_result_not_turn(self, gui):
        """Sure dolup hukmen bittikten sonra geri donus: sunucu bitmis durumu gonderir."""
        online(gui, PLAYER1_PIECE, [3])
        gui.opponent_name = "bob"
        gui.on_connection_lost(gui.network)
        state = ConnectFourGame.from_moves([3]).to_dict()
        state.update(game_over=True, winner=2)
        gui.on_game_joined({'room_id': 'AB12C', 'player_piece': 1, 'role': 'player', 'rejoined': True,
                            'current_state': state, 'opponent_info': {'username': 'bob'}})
        assert not gui.connection_down and gui.game.game_over
        assert gui.status_text == "bob kazandi!" and gui.status_tone == 'bad'
        assert gui.result_headline() == ("KAYBETTIN", COLORS['red'])
        assert not gui.network.in_game

    @pytest.mark.parametrize("msg", ["Oda bulunamadi", "Yeniden baglanma anahtari gecersiz"])
    def test_refused_rejoin_unblocks_screen_with_clear_message(self, gui, msg):
        online(gui, PLAYER1_PIECE, [3, 4])
        gui.on_connection_lost(gui.network)
        gui.on_server_error({'msg': msg})
        assert not gui.connection_down and gui.room_closed
        assert gui.status_text == "Oyuna geri donulemedi: oda kapanmis. Lobiye donebilirsiniz."
        assert not gui.can_human_move()                 # oda yok: hamle gonderilemez
        gui.connection_lost_at -= 100
        gui.tick()
        assert "geri donulemedi" in gui.status_text     # "uzun suruyor" ipucu artik gelmez
        gui.handle_button_click('BACK')                 # kaybedilecek oyun yok: onay istenmez
        assert gui.state == "LOBBY" and not gui.room_closed

    def test_other_server_errors_keep_generic_message(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_server_error({'msg': 'Sira sizde degil'})
        assert gui.status_text == "Hata: Sira sizde degil" and not gui.room_closed

    def test_opponent_grace_period_counts_down(self, gui):
        online(gui, PLAYER1_PIECE, [3])
        gui.on_opponent_disconnected({'grace_seconds': 30})
        assert "30 sn" in gui.status_text and gui.status_tone == 'bad'
        gui.opponent_deadline -= 11.5
        gui.tick()
        assert gui.status_text == "Rakibin baglantisi koptu! 19 sn icinde donmezse kazanirsin."
        gui.leave_confirm_until = gui_app.time.time() + 3          # cikis onayi mesaji ezilmez
        gui.set_status("onay")
        gui.opponent_deadline -= 5
        gui.tick()
        assert gui.status_text == "onay"
        gui.leave_confirm_until = 0.0
        gui.opponent_deadline -= 60
        gui.tick()
        assert gui.status_text == "Rakip geri donmedi, sonuc bekleniyor..."
        gui.on_game_over_network({'winner': 1, 'reason': 'forfeit'})
        gui.tick()
        assert gui.opponent_deadline is None and gui.status_text.startswith("Rakip oyunu terk etti")

    def test_own_drop_is_not_reported_as_opponents(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_connection_lost(gui.network)
        gui.on_opponent_disconnected({'grace_seconds': 30})        # oda duyurusu kapanan sokete de ulasti
        assert gui.status_text == "Baglanti koptu - yeniden baglaniliyor..." and gui.opponent_deadline is None
        online(gui, PLAYER1_PIECE)
        gui._clear_connection_state()
        gui.on_opponent_disconnected({'grace_seconds': 30})        # ters sira
        gui.on_connection_lost(gui.network)
        gui.tick()
        assert gui.status_text == "Baglanti koptu - yeniden baglaniliyor..." and gui.opponent_deadline is None

    def test_countdown_stops_when_opponent_returns(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_opponent_disconnected({'grace_seconds': 30})
        gui.on_opponent_reconnected({})
        gui.opponent_remaining = -1
        gui.tick()
        assert gui.opponent_deadline is None and gui.status_text == "Rakip geri dondu. Senin siran!"


class TestNetworkManagerDisconnect:
    def _manager(self):
        import network_client
        posted = []

        class Handler:
            def on_connection_lost(self, network):
                pass
        manager = network_client.NetworkManager("http://127.0.0.1:1", lambda fn, *args: posted.append(args), Handler())
        return manager, posted, manager.sio.handlers['/']['disconnect']

    def test_unexpected_drop_in_a_room_is_reported(self):
        manager, posted, on_disconnect = self._manager()
        on_disconnect()
        assert posted == []                              # odada degil: bildirilecek bir sey yok
        manager.room_id, manager.in_game, manager.connected = "AB12C", True, True
        on_disconnect()
        assert posted == [(manager,)] and not manager.connected

    def test_own_disconnect_is_not_reported(self):
        manager, posted, on_disconnect = self._manager()
        manager.room_id, manager.in_game = "AB12C", True
        manager.disconnect()
        on_disconnect()
        assert posted == []


# =============================================================================
# Klavye: 1-7 hamle, Esc geri
# =============================================================================

class TestKeyboard:
    def test_digit_drops_in_that_column(self, gui):
        gui.start_ai_game(2)
        press(gui, pygame.K_4, '4')
        assert gui.animating and gui.anim_col == 3
        while gui.animating:
            gui.tick()
        assert gui.game.move_history[0] == 3

    def test_keypad_digit_and_out_of_range_keys(self, gui):
        gui.start_ai_game(2)
        press(gui, pygame.K_8, '8')
        press(gui, pygame.K_0, '0')
        assert not gui.animating
        press(gui, pygame.K_KP7, '7')
        assert gui.animating and gui.anim_col == 6

    def test_digit_ignored_when_not_my_turn(self, gui):
        gui.start_ai_game(2)
        gui.ai_thinking = True
        press(gui, pygame.K_4, '4')
        assert not gui.animating and gui.game.move_history == []
        gui.ai_thinking = False
        gui.state, gui.is_spectator = "SPECTATING", True
        press(gui, pygame.K_4, '4')
        assert not gui.animating

    def test_digits_do_nothing_outside_a_game(self, gui):
        press(gui, pygame.K_1, '1')
        assert gui.state == "MENU" and not gui.animating

    @pytest.mark.parametrize("state", ["AI_SELECT", "LOBBY", "LEADERBOARD", "HISTORY", "PLAYING_AI"])
    def test_escape_goes_back_to_menu(self, gui, state):
        gui.state = state
        press(gui, pygame.K_ESCAPE)
        assert gui.state == "MENU"
        press(gui, pygame.K_ESCAPE)                       # ana menude Esc bir sey yapmaz
        assert gui.state == "MENU"

    def test_escape_needs_confirmation_in_live_online_game(self, gui):
        online(gui, PLAYER1_PIECE, [3])
        press(gui, pygame.K_ESCAPE)
        assert gui.state == "PLAYING_ONLINE" and "hukmen" in gui.status_text
        press(gui, pygame.K_ESCAPE)
        assert gui.state == "LOBBY"

    def test_keys_are_text_on_login_screen(self, gui):
        gui.logout()
        press(gui, pygame.K_m, 'm')
        press(gui, pygame.K_1, '1')
        press(gui, pygame.K_ESCAPE)
        assert gui.state == "LOGIN" and gui.input_fields['username']['value'] == "m1"
        assert not gui.sfx.muted


# =============================================================================
# Ses efektleri (dosyasiz, numpy'siz)
# =============================================================================

class TestSfxRender:
    @pytest.mark.parametrize("name", sorted(gui_app.SFX_TONES))
    def test_waveform_is_bounded_and_click_free(self, name):
        rate = 44100
        peak, notes = gui_app.SFX_TONES[name]
        samples = gui_app.render_sfx(name, rate)
        assert len(samples) == sum(round(d * rate) for _, d in notes)
        assert max(abs(v) for v in samples) <= 0.5 * 32767
        assert max(abs(v) for v in samples) > 0.3 * peak * 32767       # sessiz degil
        assert samples[0] == 0 and abs(samples[-1]) < 300

    def test_loudest_overlap_keeps_headroom(self):
        tones = gui_app.SFX_TONES
        assert tones['drop'][0] + max(tones[n][0] for n in ('win', 'lose', 'draw', 'turn')) <= 0.891

    def test_other_sample_rate_and_stereo_buffer(self):
        assert len(gui_app.render_sfx('click', 22050)) == round(0.035 * 22050)
        mono = gui_app.render_sfx('click', 22050)
        stereo = gui_app._sfx_buffer('click', 22050, 2, 1.0)
        assert len(stereo) == len(mono) * 2 * 2


class TestSfx:
    def test_works_under_headless_mixer(self):
        sfx = gui_app.Sfx()
        assert sfx.ok and set(sfx.sounds) == set(gui_app.SFX_TONES)
        for name in gui_app.SFX_TONES:
            for _ in range(4):
                sfx.play(name)
        assert sfx.played['drop'] == 4

    @pytest.mark.parametrize("fmt", [None, (44100, 8, 2), (44100, 32, 2)])
    def test_no_mixer_or_unexpected_format_is_silent(self, monkeypatch, fmt):
        monkeypatch.setattr(pygame.mixer, "get_init", lambda: fmt)
        sfx = gui_app.Sfx()
        assert not sfx.ok
        sfx.play('drop')
        assert sfx.played['drop'] == 1

    def test_mixer_error_is_swallowed(self, monkeypatch):
        def broken(*args, **kwargs):
            raise pygame.error("mixer not initialized")
        monkeypatch.setattr(pygame.mixer, "Sound", broken)
        sfx = gui_app.Sfx()
        assert not sfx.ok
        sfx.play('win')

    def _spy(self, sfx):
        calls = []

        class Spy:
            def __init__(self, tag):
                self.tag = tag

            def play(self):
                calls.append(self.tag)
        sfx.sounds = {name: [Spy((name, i)) for i in range(len(variants))] for name, variants in sfx.sounds.items()}
        return calls

    def test_muted_counts_but_does_not_play(self):
        sfx = gui_app.Sfx(muted=True)
        calls = self._spy(sfx)
        sfx.play('drop')
        assert calls == [] and sfx.played['drop'] == 1
        assert sfx.toggle_mute() is False
        sfx.play('drop')
        assert len(calls) == 1

    def test_consecutive_drops_use_different_variants(self):
        sfx = gui_app.Sfx()
        calls = self._spy(sfx)
        for _ in range(20):
            sfx.play('drop')
        assert all(calls[i] != calls[i + 1] for i in range(19))
        assert len(set(calls)) == 3


class TestSfxHooks:
    def test_drop_click_invalid_and_result(self, gui):
        played = gui.sfx.played
        clicks = played['click']                           # fixture: misafir girisi
        gui.handle_button_click('AI')
        assert played['click'] == clicks + 1
        gui.start_ai_game(2)
        gui.handle_click(3)
        while gui.animating:
            gui.tick()
        assert played['drop'] == 1
        gui.invalidate_ai_session()
        gui.state = "PLAYING_AI"
        gui.game = ConnectFourGame.from_moves([0] * 6)
        gui.ai = object()
        gui.handle_click(0)
        assert played['invalid'] == 1
        gui.game = ConnectFourGame.from_moves(P1_WIN)
        gui.handle_game_over()
        gui.handle_game_over()
        assert played['win'] == 1 and played['lose'] == 0
        gui.start_ai_game(2)                               # yeni oyun: sonuc sesi yeniden calabilir
        gui.game = ConnectFourGame.from_moves(P2_WIN)
        gui.handle_game_over()
        assert played['lose'] == 1

    def test_spectator_and_draw_get_neutral_tone(self, gui):
        online(gui, 0, [3])
        gui.state, gui.is_spectator = "SPECTATING", True
        gui.on_game_over_network({'winner': 1, 'reason': 'forfeit'})
        assert gui.sfx.played['draw'] == 1 and gui.sfx.played['win'] == gui.sfx.played['lose'] == 0

    def test_mute_toggle_from_menu_and_keyboard(self, gui):
        assert not gui.sfx.muted
        gui.tick()
        assert 'MUTE' in [bid for bid, _ in gui.buttons]
        gui.handle_button_click('MUTE')
        assert gui.sfx.muted
        press(gui, pygame.K_m, 'm')
        assert not gui.sfx.muted
        gui.start_ai_game(2)
        press(gui, pygame.K_m, 'm')
        assert gui.sfx.muted

    def test_connect4_mute_env_starts_muted_without_audio_device(self):
        """CONNECT4_MUTE=1: pygame import edilmeden once sahte ses surucusu secilir."""
        import os
        import subprocess
        import sys
        code = ("import os, gui_app; g = gui_app.ConnectFourGUI(server_url='http://127.0.0.1:1'); "
                "print(os.environ['SDL_AUDIODRIVER'], g.sfx.muted)")
        for mute, expected in (("1", "dummy True"), ("0", "unset False")):
            env = {k: v for k, v in os.environ.items() if k != 'SDL_AUDIODRIVER'}
            env.update(CONNECT4_MUTE=mute, SDL_VIDEODRIVER='dummy', LOG_LEVEL='WARNING',
                       PYTHONPATH=os.path.dirname(gui_app.__file__))
            if mute == "0":
                code = code.replace("os.environ['SDL_AUDIODRIVER']", "os.environ.get('SDL_AUDIODRIVER', 'unset')")
            out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
            assert out.returncode == 0, out.stderr
            assert out.stdout.strip().splitlines()[-1] == expected
