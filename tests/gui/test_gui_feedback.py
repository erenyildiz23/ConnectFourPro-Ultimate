"""
Arayuz geri bildirimi testleri (sunucu gerekmez): renk kontrasti, tas dusme animasyonu,
son hamle / inis isaretleri, sonuc basligi, sira vurgusu, klavye.
Cizimi suren durum ve geometri dogrulanir; piksel okunmaz.
"""

import copy
import time

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


# =============================================================================
# Yardimcilar: arka plan AI'sini bekleyen dongu
# =============================================================================

def settle(g, condition, timeout=15.0):
    """Kosul saglanana kadar kareleri isletir (AI thread'i duvar saatiyle calisir)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        g.tick()
        if condition():
            return
        time.sleep(0.005)
    raise AssertionError(f"zaman asimi: {g.state} {g.status_text!r} {g.game.move_history}")


def human_move(g, col):
    """Insan hamlesi + AI cevabi tamamlanana kadar bekler."""
    before = len(g.game.move_history)
    g.handle_click(col)
    settle(g, lambda: len(g.game.move_history) >= before + 2 and not g.animating and not g.ai_thinking)


# =============================================================================
# B1: Kolay seviyesinin hata politikasi (arama sonrasi, deterministik)
# =============================================================================

CYCLE = [c % 7 for c in range(20)]        # Kazanani olmayan 20 hamlelik gecerli dizi


class TestKolaySlip:
    def test_fmix32_matches_murmur3_finalizer(self):
        assert gui_app.fmix32(0) == 0 and gui_app.fmix32(1) == 0x514E28B7
        assert gui_app.fmix32(2 ** 32 + 1) == 0x514E28B7        # 32 bite kirpilir

    def test_only_kolay_slips_and_rate_is_forty_percent(self):
        game = ConnectFourGame.from_moves(CYCLE[:3])
        assert gui_app.SLIP_PERMILLE == {2: 400}
        for depth in (1, 3, 4, 8):
            assert all(gui_app.slip_move(game, depth, seed) is None for seed in range(300))
        slips = sum(gui_app.slip_move(game, 2, seed) is not None for seed in range(2000))
        assert 0.36 * 2000 <= slips <= 0.44 * 2000

    def test_slips_are_valid_spread_and_a_pure_function_of_seed_and_ply(self):
        game = ConnectFourGame.from_moves([0] * 6 + [1] * 6)               # sutun 0 ve 1 dolu
        cols = set()
        for seed in range(400):
            col = gui_app.slip_move(game, 2, seed)
            assert col == gui_app.slip_move(game.clone(), 2, seed)         # ayni (tohum, hamle sirasi) -> ayni karar
            if col is not None:
                assert game.is_valid_location(col)
                cols.add(col)
        assert cols == {2, 3, 4, 5, 6}

    def test_slips_do_not_come_in_long_streaks(self):
        """Dogrusal tohumlu uretecler 9 hamle ust uste hata sonra 13 hamle hatasiz verirdi."""
        for seed in (1, 2, 3, 12345, 2 ** 31):
            pattern = [gui_app.slip_move(ConnectFourGame.from_moves(CYCLE[:ply]), 2, seed) is not None
                       for ply in range(20)]
            longest = run = 0
            for slipped in pattern:
                run = run + 1 if slipped else 0
                longest = max(longest, run)
            assert 2 <= sum(pattern) <= 14 and longest <= 5, (seed, pattern)

    def test_never_skips_its_own_immediate_win(self):
        game = ConnectFourGame.from_moves([0, 6, 1, 6, 2, 6, 5])           # sari (AI) sira onda, 6. sutunda kazanir
        assert game.current_player == PLAYER2_PIECE
        assert all(gui_app.slip_move(game, 2, seed) is None for seed in range(500))
        # Kontrol: ayni tohumlar kazanc yokken hata yapar
        quiet = ConnectFourGame.from_moves([0, 6, 1, 6, 2, 3, 5])
        assert any(gui_app.slip_move(quiet, 2, seed) is not None for seed in range(50))

    def test_finished_game_has_no_slip(self):
        assert gui_app.slip_move(ConnectFourGame.from_moves(P1_WIN), 2, 0) is None

    def test_ai_reply_applies_the_slip_after_the_search(self, gui):
        """Gercek AI thread'i: Kolay'da cevap slip_move'un sutunudur, kitap hamlesi (3) degil."""
        slip_seed = next(s for s in range(500) if gui_app.slip_move(ConnectFourGame.from_moves([0]), 2, s) not in (None, 3))
        calm_seed = next(s for s in range(500) if gui_app.slip_move(ConnectFourGame.from_moves([0]), 2, s) is None)
        gui.start_ai_game(2, ai_starts=False)
        gui.ai_seed = slip_seed
        human_move(gui, 0)
        assert gui.game.move_history == [0, gui_app.slip_move(ConnectFourGame.from_moves([0]), 2, slip_seed)]
        gui.start_ai_game(2, ai_starts=False)
        gui.ai_seed = calm_seed
        human_move(gui, 0)
        assert gui.game.move_history == [0, 3]

    def test_orta_never_slips_in_the_real_game(self, gui):
        gui.start_ai_game(4, ai_starts=False)
        human_move(gui, 0)
        assert gui.game.move_history == [0, 3]          # kitap hamlesi, hata yok


# =============================================================================
# B2: ilk hamleyi secme ve Yeni Oyun
# =============================================================================

class TestAIFirstMoveAndNewGame:
    def test_toggle_on_difficulty_screen_decides_the_starter(self, gui):
        gui.handle_button_click('AI')
        gui.tick()
        assert 'AI_FIRST_TOGGLE' in [bid for bid, _ in gui.buttons]
        assert not gui.ai_starts_next
        gui.handle_button_click('AI_FIRST_TOGGLE')
        assert gui.ai_starts_next
        gui.handle_button_click('AI_4')
        assert gui.state == "PLAYING_AI" and gui.ai_starts and gui.game.current_player == PLAYER2_PIECE
        assert gui.ai_thinking and gui.status_text == "AI dusunuyor..." and not gui.can_human_move()
        settle(gui, lambda: gui.can_human_move())
        assert gui.game.move_history == [3] and gui.status_text == "Senin siran!"
        assert gui.my_piece == PLAYER1_PIECE and gui.human_piece() == PLAYER1_PIECE   # insan hep kirmizi

    def test_human_first_by_default(self, gui):
        gui.start_ai_game(4)
        assert not gui.ai_starts and gui.can_human_move() and gui.game.move_history == []

    def test_new_game_button_alternates_the_starter_and_keeps_depth(self, gui):
        gui.start_ai_game(4, ai_starts=False)
        human_move(gui, 0)
        gui.tick()
        assert 'NEW_AI_GAME' in [bid for bid, _ in gui.buttons]      # oyun sirasinda da gorunur
        gui.handle_button_click('NEW_AI_GAME')
        assert gui.state == "PLAYING_AI" and gui.ai.depth == 4 and gui.ai_starts
        settle(gui, lambda: gui.can_human_move())
        assert gui.game.move_history == [3]
        gui.handle_button_click('NEW_AI_GAME')
        assert not gui.ai_starts and gui.game.move_history == [] and gui.can_human_move()

    def test_new_game_while_disc_falls_leaves_no_stale_move(self, gui):
        gui.start_ai_game(4, ai_starts=False)
        gui.handle_click(0)
        assert gui.animating
        gui.handle_button_click('NEW_AI_GAME')                       # AI baslar
        assert not gui.animating and gui.anim_callback is None
        settle(gui, lambda: gui.can_human_move())
        for _ in range(60):
            gui.tick()
        assert gui.game.move_history == [3]                          # eski tasin geri cagrisi yeni oyuna sizmadi

    def test_new_game_while_ai_thinks_discards_its_old_move(self, gui):
        gui.start_ai_game(6, ai_starts=False)
        gui.handle_click(0)
        settle(gui, lambda: gui.ai_thinking)
        gui.handle_button_click('NEW_AI_GAME')
        settle(gui, lambda: gui.can_human_move(), timeout=30)
        for _ in range(60):
            gui.tick()
        assert gui.game.move_history == [3]


# =============================================================================
# B3: Geri Al (yalnizca AI oyununda)
# =============================================================================

class TestUndo:
    def test_undo_restores_the_exact_position(self, gui):
        gui.start_ai_game(4)
        start = copy.deepcopy(gui.game.to_dict())
        assert not gui.can_undo()
        human_move(gui, 3)
        assert gui.game.move_history == [3, 3] and gui.can_undo()
        gui.handle_button_click('UNDO')
        assert gui.game.to_dict() == start and gui.can_human_move()
        assert gui.status_text == "Hamle geri alindi. Senin siran!"
        assert gui.ai is not None and gui.ai.depth == 4 and not gui.can_undo()

    def test_undo_takes_back_only_the_last_round(self, gui):
        gui.start_ai_game(4)
        human_move(gui, 3)
        human_move(gui, 1)
        first_round = gui.game.move_history[:2]
        gui.undo_ai_move()
        assert gui.game.move_history == first_round and gui.game.current_player == PLAYER1_PIECE

    def test_refused_while_a_disc_falls_or_ai_thinks(self, gui):
        gui.start_ai_game(6)
        human_move(gui, 3)
        gui.handle_click(1)
        assert gui.animating and not gui.can_undo()
        gui.undo_ai_move()
        assert gui.animating and gui.game.move_history == [3, 3]       # hicbir sey degismedi
        settle(gui, lambda: gui.ai_thinking)
        before = list(gui.game.move_history)
        assert not gui.can_undo()
        gui.undo_ai_move()
        assert gui.game.move_history == before and gui.ai_thinking
        settle(gui, lambda: gui.can_human_move(), timeout=30)
        assert len(gui.game.move_history) == 4 and gui.can_undo()

    def test_undo_while_ai_reply_is_pending_is_refused(self, gui):
        gui.start_ai_game(4)
        gui.handle_click(3)
        settle(gui, lambda: gui.pending_ai_move is not None or len(gui.game.move_history) == 2)
        gui.pending_ai_move = 3
        assert not gui.can_undo()
        gui.pending_ai_move = None

    def test_undo_after_game_over_reopens_the_game(self, gui):
        gui.start_ai_game(4)
        gui.game = ConnectFourGame.from_moves(P1_WIN)                  # insan kazandi
        assert gui.game.game_over and not gui.can_human_move()
        gui.handle_game_over()
        gui.undo_ai_move()
        assert not gui.game.game_over and gui.game.get_winning_positions() == []
        assert gui.game.move_history == P1_WIN[:6] and gui.can_human_move()
        assert gui.result_headline() is None
        gui.game = ConnectFourGame.from_moves(P2_WIN)                  # AI kazandi: yine insanin sirasina doner
        gui.undo_ai_move()
        assert gui.game.move_history == P2_WIN[:6] and gui.game.current_player == PLAYER1_PIECE
        gui.game = ConnectFourGame.from_moves(P2_WIN)                   # yeniden bitince sonuc sesi tekrar calar
        gui.handle_game_over()
        assert gui.sfx.played['win'] == 1 and gui.sfx.played['lose'] == 1

    def test_undo_when_the_ai_started(self, gui):
        gui.start_ai_game(4, ai_starts=True)
        settle(gui, lambda: gui.can_human_move())
        assert gui.game.move_history == [3] and not gui.can_undo()     # henuz insan hamlesi yok
        human_move(gui, 0)
        assert len(gui.game.move_history) == 3 and gui.can_undo()
        gui.undo_ai_move()
        assert gui.game.move_history == [3] and gui.can_human_move() and gui.ai_starts

    def test_undo_is_not_a_reroll_on_kolay(self, gui):
        seed = next(s for s in range(500) if gui_app.slip_move(ConnectFourGame.from_moves([0]), 2, s) not in (None, 3))
        gui.start_ai_game(2, ai_starts=False)
        gui.ai_seed = seed
        human_move(gui, 0)
        reply = gui.game.move_history[1]
        gui.undo_ai_move()
        assert gui.ai_seed == seed                                      # tohum geri almayla degismez
        human_move(gui, 0)
        assert gui.game.move_history == [0, reply]

    def test_undo_not_available_online_or_for_spectators(self, gui):
        online(gui, PLAYER1_PIECE, [3, 4])
        assert not gui.can_undo() and 'UNDO' not in [a[0] for a in gui.action_buttons()]
        press(gui, pygame.K_u, 'u')
        assert gui.game.move_history == [3, 4]
        gui.tick()
        assert 'UNDO' not in [bid for bid, _ in gui.buttons]
        gui.handle_button_click('UNDO')
        assert gui.game.move_history == [3, 4]

    def test_keyboard_u_and_panel_buttons_in_ai_game(self, gui):
        gui.start_ai_game(4)
        human_move(gui, 3)
        gui.tick()
        assert [bid for bid, _ in gui.buttons] == ['BACK', 'UNDO', 'NEW_AI_GAME']
        press(gui, pygame.K_u, 'u')
        assert gui.game.move_history == []


# =============================================================================
# B4: sade zorluk etiketleri ve ilk hamle ipucu
# =============================================================================

class TestOnboarding:
    def test_difficulty_labels_are_plain_language_and_ascii(self, gui):
        gui.handle_button_click('AI')
        gui.tick()
        ids = [bid for bid, _ in gui.buttons]
        assert ids == ['AI_FIRST_TOGGLE', 'AI_2', 'AI_4', 'AI_8', 'BACK']      # kimlikler ve derinlikler ayni
        labels = gui_app.DIFFICULTY_LABELS
        assert set(labels) == set(gui_app.AI_DEPTHS) == {'Kolay', 'Orta', 'Zor'}
        for text in list(labels.values()) + [gui_app.COACH_TEXT]:
            assert text.isascii() and "(D" not in text
        widths = {bid: rect.width for bid, rect in gui.buttons if bid.startswith('AI_') and bid != 'AI_FIRST_TOGGLE'}
        assert set(widths.values()) == {420}

    @pytest.mark.parametrize("depth, name", [(2, "Kolay"), (4, "Orta"), (8, "Zor")])
    def test_opponent_label_uses_the_level_name(self, gui, depth, name):
        gui.start_ai_game(depth)
        assert gui._player_labels()[2] == f"AI - {name}"

    def test_coaching_line_on_empty_board_then_turn_messages(self, gui):
        gui.start_ai_game(4)
        assert gui.status_text == gui_app.COACH_TEXT and "Kirmizi sensin" in gui.status_text
        assert gui.status_color() == COLORS['green']                       # sira sende
        human_move(gui, 3)
        assert gui.status_text == "Senin siran!"


# =============================================================================
# B5: isabet olcusu: esit iyi hamleler ve kitap hamlesi hata sayilmaz
# =============================================================================

class TestAccuracyMetric:
    def test_every_equal_winning_column_counts(self):
        game = ConnectFourGame.from_moves([2, 2, 3, 3, 4, 4])              # 1 ve 5 sutunlari kazanir
        assert gui_app.best_columns(game, depth=2) == [1, 5]

    def test_book_move_counts_even_when_search_prefers_another(self):
        game = ConnectFourGame.from_moves([1])                              # kitap 2, D8 yalnizca 3 der
        best = gui_app.best_columns(game, depth=gui_app.ANALYSIS_DEPTH)
        assert 2 in best and 3 in best

    def test_single_forced_block_and_cancel(self):
        game = ConnectFourGame.from_moves([0, 6, 1, 6, 2])                  # sari sirada: kirmizinin 3'teki dortlusu engellenmeli
        assert gui_app.best_columns(game, depth=2) == [3]                   # zorunlu blok tek hamle
        import threading
        stop = threading.Event()
        stop.set()
        assert gui_app.best_columns(ConnectFourGame(), depth=2, cancel_event=stop) is None

    def test_search_result_is_still_one_of_the_columns(self):
        for moves in ([], [3], [3, 3, 2], [0, 1, 2, 3, 4]):
            game = ConnectFourGame.from_moves(moves)
            best = gui_app.best_columns(game, depth=3)
            chosen = gui_app.AIEngine(game.current_player, depth=3, use_opening_book=False).find_best_move(game)
            assert chosen in best and best == sorted(best) and all(game.is_valid_location(c) for c in best)

    def test_analysis_loop_marks_equivalent_and_book_moves_as_best(self, gui):
        gui.state, gui.my_piece = "PLAYING_ONLINE", PLAYER1_PIECE
        win = ConnectFourGame.from_moves([2, 2, 3, 3, 4, 4])
        book = ConnectFourGame.from_moves([1])
        gui.start_background_analysis(win, 6, PLAYER1_PIECE, 5)             # 5 de kazandirir (motor 1 doner)
        gui.start_background_analysis(book, 1, PLAYER2_PIECE, 2)            # kitap hamlesi
        gui.start_background_analysis(book, 1, PLAYER2_PIECE, 0)            # kotu hamle
        deadline = time.time() + 30
        while len(gui.analysis_data) < 3 and time.time() < deadline:
            time.sleep(0.02)
        by_col = {(d['move_num'], d['actual_col']): d for d in gui.analysis_data}
        assert by_col[(6, 5)]['was_best'] and 5 in by_col[(6, 5)]['best_cols']
        assert by_col[(1, 2)]['was_best'] and not by_col[(1, 0)]['was_best']
        assert all(d['best_col'] in d['best_cols'] for d in gui.analysis_data)
        gui.my_piece = PLAYER1_PIECE
        assert gui.get_analysis_summary()['my_accuracy'] == 100.0


# =============================================================================
# A1: rovans (sunucu olaylari elle verilir; canli akis test_gui_use_cases.py'de)
# =============================================================================

class TestRematchClient:
    @pytest.fixture
    def finished(self, gui):
        online(gui, PLAYER1_PIECE, P1_WIN)
        gui.on_game_over_network({'winner': 1, 'reason': 'normal', 'elo_changes': {'p1': 15, 'p2': -15},
                                  'new_ratings': {'p1': 1215, 'p2': 1185}})
        gui.sent = []
        gui.network.request_rematch = lambda: gui.sent.append(1) or True
        return gui

    def test_button_and_key_only_after_an_online_game_ended(self, gui):
        online(gui, PLAYER1_PIECE, [3])
        gui.tick()
        assert 'REMATCH' not in [bid for bid, _ in gui.buttons] and not gui.can_request_rematch()
        online(gui, PLAYER1_PIECE, P1_WIN)
        gui.tick()
        assert 'REMATCH' in [bid for bid, _ in gui.buttons] and gui.can_request_rematch()

    def test_no_button_for_spectators_or_ai_games(self, gui):
        online(gui, 0, P1_WIN)
        gui.state, gui.is_spectator = "SPECTATING", True
        gui.tick()
        assert 'REMATCH' not in [bid for bid, _ in gui.buttons] and not gui.can_request_rematch()
        gui.start_ai_game(2)
        gui.game = ConnectFourGame.from_moves(P1_WIN)
        gui.tick()
        assert 'REMATCH' not in [bid for bid, _ in gui.buttons] and not gui.can_request_rematch()
        press(gui, pygame.K_r, 'r')
        assert gui.state == "PLAYING_AI"

    def test_button_and_key_send_one_request(self, finished):
        g = finished
        g.handle_button_click('REMATCH')
        assert g.sent == [1] and g.rematch_state == 'requested'
        assert g.status_text == "Rovans istendi, rakip bekleniyor"
        g.handle_button_click('REMATCH')                          # ikinci tiklama yeni istek gondermez
        press(g, pygame.K_r, 'r')
        assert g.sent == [1]
        g.tick()
        assert not g.can_request_rematch()                        # dugme pasif ama yerinde

    def test_key_r_requests_rematch(self, finished):
        press(finished, pygame.K_r, 'r')
        assert finished.sent == [1]

    def test_offer_texts_follow_from_piece(self, finished):
        g = finished
        g.on_rematch_offered({'room_id': 'AB12C', 'from_piece': PLAYER2_PIECE})
        assert g.rematch_state == 'offered' and g.status_text == "Rakip rovans istiyor"
        assert g.can_request_rematch()
        g.handle_button_click('REMATCH')                          # karsilik verince baslar
        assert g.sent == [1] and g.status_text == "Rovans baslatiliyor..."
        g.on_rematch_offered({'room_id': 'AB12C', 'from_piece': PLAYER1_PIECE})
        assert g.rematch_state == 'requested' and g.status_text == "Rovans istendi, rakip bekleniyor"

    def test_unavailable_disables_button_and_keeps_result(self, finished):
        g = finished
        g.on_rematch_unavailable({'room_id': 'AB12C', 'reason': 'opponent_left'})
        assert g.rematch_state == 'unavailable' and not g.can_request_rematch()
        assert g.status_text == "Kazandin!  ELO +15 (1215)  |  Rakip ayrildi, rovans yapilamaz"
        g.tick()
        assert 'REMATCH' in [bid for bid, _ in g.buttons]         # gorunur ama pasif
        g.handle_button_click('REMATCH')
        press(g, pygame.K_r, 'r')
        assert g.sent == []

    def test_opponent_leaving_the_finished_game_disables_it_at_once(self, gui):
        online(gui, PLAYER2_PIECE, [3])
        gui.on_game_over_network({'winner': 2, 'reason': 'forfeit', 'detail': 'leave'})
        assert gui.rematch_state == 'unavailable' and not gui.can_request_rematch()

    def test_offer_arriving_before_the_final_animation_survives_it(self, gui):
        online(gui, PLAYER2_PIECE, P1_WIN[:-1])
        gui.on_game_over_network({'winner': 1, 'reason': 'normal'})
        gui.on_rematch_offered({'from_piece': PLAYER1_PIECE})
        gui.game = ConnectFourGame.from_moves(P1_WIN)
        gui.handle_game_over()
        assert gui.status_text == "Rakip rovans istiyor"

    def test_rematch_game_start_resets_everything_and_swaps_seats(self, gui):
        online(gui, PLAYER1_PIECE, P1_WIN)
        gui.network.my_piece, gui.network.in_game = PLAYER1_PIECE, False
        gui.on_game_over_network({'winner': 1, 'reason': 'normal', 'elo_changes': {'p1': 15, 'p2': -15},
                                  'new_ratings': {'p1': 1215, 'p2': 1185}})
        gui.rematch_state = 'requested'
        gui.animating, gui.anim_callback = True, lambda: pytest.fail("eski animasyon yeni oyuna sizdi")
        assert gui.last_elo_change == 15 and gui.sfx.played['win'] == 1
        gui.on_game_start({'rematch': True, 'game_no': 2, 'player_piece': PLAYER2_PIECE, 'opponent_name': 'bob',
                           'opponent_elo': 1185, 'move_time': 30, 'turn_seconds_left': 30})
        assert gui.my_piece == PLAYER2_PIECE and gui.network.my_piece == PLAYER2_PIECE
        assert gui.network.in_game                                  # otomatik geri donus yine calisir
        assert gui.game.move_history == [] and not gui.game.game_over and not gui.animating
        assert gui.result_headline() is None and gui.last_move_cell() is None
        assert gui.last_elo_change is None and gui.final_status is None and gui.rematch_state == 'idle'
        assert gui.game_no == 2 and gui.status_text == "Rovans basladi! Rakibin sirasi." and gui.opponent_elo == 1185
        assert gui.sfx.played['start'] == 1
        gui._play_result_once(PLAYER1_PIECE)                        # sonuc sesi bayragi sifirlandi
        assert gui.sfx.played['lose'] == 1
        assert gui.turn_seconds_left() == 30
        gui.tick()
        assert 'REMATCH' not in [bid for bid, _ in gui.buttons]

    def test_new_seat_decides_who_moves_first(self, gui):
        online(gui, PLAYER2_PIECE, P1_WIN)
        gui.on_game_start({'rematch': True, 'game_no': 2, 'player_piece': PLAYER1_PIECE})
        assert gui.can_human_move() and gui.status_text == "Rovans basladi! Senin siran."

    def test_spectator_follows_rematch_started(self, gui):
        online(gui, 0, P1_WIN)
        gui.state, gui.is_spectator = "SPECTATING", True
        gui.on_game_over_network({'winner': 1, 'reason': 'normal'})
        gui.on_rematch_started({'room_id': 'AB12C', 'game_no': 2, 'p1_info': {'username': 'bob', 'rating': 1185},
                                'p2_info': {'username': 'alice', 'rating': 1215},
                                'current_state': ConnectFourGame().to_dict(), 'move_time': 0,
                                'turn_seconds_left': None})
        assert gui.game.move_history == [] and gui.result_headline() is None and gui.state == "SPECTATING"
        assert gui.spectate_names == ('bob', 1185, 'alice', 1215) and gui.game_no == 2
        assert gui.sfx.played['draw'] == 1
        gui._play_result_once(PLAYER1_PIECE)
        assert gui.sfx.played['draw'] == 2                          # sonuc sesi yeni oyun icin yeniden hazir

    def test_players_ignore_the_room_broadcast_except_for_the_clock(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_rematch_started({'game_no': 2, 'current_state': ConnectFourGame().to_dict(),
                                'move_time': 30, 'turn_seconds_left': 20})
        assert gui.game.move_history == [] and gui.turn_seconds_left() == 20 and not gui.is_spectator

    def test_rejoin_into_a_newer_game_resets_per_game_state(self, gui):
        online(gui, PLAYER1_PIECE, P1_WIN)
        gui.on_game_over_network({'winner': 1, 'reason': 'normal', 'elo_changes': {'p1': 15, 'p2': -15},
                                  'new_ratings': {'p1': 1215, 'p2': 1185}})
        gui.on_connection_lost(gui.network)
        state = ConnectFourGame.from_moves([3]).to_dict()
        gui.on_game_joined({'room_id': 'AB12C', 'player_piece': PLAYER2_PIECE, 'role': 'player', 'rejoined': True,
                            'current_state': state, 'game_no': 2, 'opponent_info': {'username': 'bob'},
                            'move_time': 0, 'turn_seconds_left': None})
        assert gui.my_piece == PLAYER2_PIECE and gui.game.move_history == [3] and gui.game_no == 2
        assert gui.last_elo_change is None and gui.final_status is None and gui.can_human_move()


class TestNetworkRematch:
    def _manager(self):
        import network_client
        posted = []
        manager = network_client.NetworkManager("http://127.0.0.1:1", lambda fn, *args: posted.append((fn.__name__, args)),
                                                gui_app.ConnectFourGUI.__new__(gui_app.ConnectFourGUI))
        return manager, posted

    def test_new_events_are_forwarded(self):
        manager, posted = self._manager()
        for event, method in (('rematch_offered', 'on_rematch_offered'), ('rematch_unavailable', 'on_rematch_unavailable'),
                              ('rematch_started', 'on_rematch_started')):
            manager.sio.handlers['/'][event]({'room_id': 'AB12C'})
            assert posted[-1][0] == method

    def test_rematch_game_start_updates_piece_and_rejoin_flag(self):
        manager, posted = self._manager()
        manager.my_piece, manager.in_game = PLAYER1_PIECE, False
        manager.sio.handlers['/']['game_start']({'rematch': True, 'player_piece': PLAYER2_PIECE})
        assert manager.my_piece == PLAYER2_PIECE and manager.in_game
        manager.my_piece = PLAYER1_PIECE
        manager.sio.handlers['/']['game_start']({'msg': 'Oyun Basladi!'})          # ilk oyun: dokunmaz
        assert manager.my_piece == PLAYER1_PIECE

    def test_request_rematch_emits_only_when_connected(self):
        manager, _ = self._manager()
        sent = []
        manager.sio.emit = lambda *args: sent.append(args)
        assert not manager.request_rematch() and sent == []
        manager.connected, manager.room_id = True, "AB12C"
        assert manager.request_rematch() and sent == [('rematch_request', {'room_id': 'AB12C'})]


# =============================================================================
# A2: hamle suresi geri sayimi
# =============================================================================

def move_event(moves):
    """Sunucunun move_made yuku (hamle gecmisi + son sutun)."""
    data = ConnectFourGame.from_moves(moves).to_dict()
    data['col'] = moves[-1]
    return data


class TestMoveClock:
    def test_counts_down_locally_and_never_below_zero(self, gui):
        online(gui, PLAYER1_PIECE)
        assert gui.turn_seconds_left() is None                      # sayac yok
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': 30})
        assert gui.move_time == 30 and gui.turn_seconds_left() == 30
        gui.turn_deadline -= 4.2
        assert gui.turn_seconds_left() == 26
        gui.turn_deadline -= 100
        assert gui.turn_seconds_left() == 0
        gui.tick()                                                  # cizim hata vermemeli

    def test_null_means_no_countdown(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': 30})
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': None})
        assert gui.turn_seconds_left() is None and gui.move_time == 30
        gui.on_game_start({'move_time': 0, 'turn_seconds_left': None})
        assert gui.turn_seconds_left() is None and gui.move_time == 0

    def test_old_server_without_fields_has_no_clock(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_game_start({'msg': 'Oyun Basladi!'})
        gui.on_move_made(move_event([3]))
        assert gui.turn_seconds_left() is None and gui.move_time == 0

    def test_move_made_resets_the_clock_but_stale_events_do_not(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': 30})
        gui.turn_deadline -= 12
        event = move_event([3])
        event.update(move_time=30, turn_seconds_left=29)
        gui.on_move_made(event)
        assert gui.turn_seconds_left() == 29
        gui.turn_deadline -= 12
        gui.on_move_made(move_event([3, 4]) | {'move_time': 30, 'turn_seconds_left': 30})
        gui.on_move_made(event)                                     # gecikmis eski olay saati geri sarmaz
        assert gui.turn_seconds_left() == 30

    def test_hidden_when_game_is_over(self, gui):
        online(gui, PLAYER1_PIECE, [3])
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': 30})
        online(gui, PLAYER1_PIECE, P1_WIN)
        assert gui.turn_seconds_left() is None
        gui.tick()
        online(gui, PLAYER2_PIECE, [3])
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': 30})
        gui.on_game_over_network({'winner': 1, 'reason': 'forfeit', 'detail': 'timeout'})
        assert gui.turn_seconds_left() is None and gui.turn_deadline is None

    def test_warning_colour_and_single_sound_only_on_my_last_seconds(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': 30})
        gui.tick()
        assert not gui.turn_warning() and gui.sfx.played['warn'] == 0
        gui.turn_deadline -= 20                                     # 10 sn kaldi
        gui.tick()
        gui.tick()
        assert gui.turn_seconds_left() == 10 and gui.turn_warning() and gui.sfx.played['warn'] == 1
        gui.turn_deadline -= 5
        gui.tick()
        assert gui.sfx.played['warn'] == 1                          # ayni sirada tekrar calmaz
        gui.game = ConnectFourGame.from_moves([3])                  # kendi hamlem; sunucu yankisi gelir
        gui.on_move_made(move_event([3]) | {'move_time': 30, 'turn_seconds_left': 4})
        gui.tick()                                                  # rakibin sirasi: kendi uyarim yok
        assert not gui.turn_warning() and gui.sfx.played['warn'] == 1

    def test_opponents_last_seconds_do_not_warn_me(self, gui):
        online(gui, PLAYER2_PIECE)                                  # sira kirmizida (rakip)
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': 3})
        gui.tick()
        assert gui.turn_seconds_left() == 3 and not gui.turn_warning() and gui.sfx.played['warn'] == 0

    def test_new_turn_can_warn_again(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': 8})
        gui.tick()
        assert gui.sfx.played['warn'] == 1
        online(gui, PLAYER1_PIECE, [3, 4])
        gui.on_move_made(move_event([3, 4, 2, 5]) | {'move_time': 30, 'turn_seconds_left': 9})
        gui.tick()
        assert gui.sfx.played['warn'] == 2

    def test_spectator_sees_the_clock_without_warning(self, gui):
        online(gui, 0, [3])
        gui.state, gui.is_spectator = "SPECTATING", True
        gui.on_game_joined({'room_id': 'AB12C', 'role': 'spectator', 'player_piece': 0,
                            'current_state': ConnectFourGame.from_moves([3]).to_dict(),
                            'move_time': 30, 'turn_seconds_left': 7})
        gui.tick()
        assert gui.turn_seconds_left() == 7 and not gui.turn_warning() and gui.sfx.played['warn'] == 0

    def test_rejoin_restores_the_clock(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_connection_lost(gui.network)
        gui.on_game_joined({'room_id': 'AB12C', 'player_piece': 1, 'role': 'player', 'rejoined': True,
                            'current_state': ConnectFourGame.from_moves([3, 4]).to_dict(),
                            'move_time': 30, 'turn_seconds_left': 12, 'game_no': 1,
                            'opponent_info': {'username': 'bob'}})
        assert gui.turn_seconds_left() == 12

    def test_clock_pauses_while_opponent_is_away_on_my_turn(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': 25})
        gui.on_opponent_disconnected({'grace_seconds': 30})
        assert gui.turn_seconds_left() is None                      # sunucu da saati durdurur
        gui.on_opponent_reconnected({})
        assert gui.turn_seconds_left() == 30                        # dondugunde sunucu saati bastan baslatir

    def test_clock_keeps_running_when_the_absent_opponent_is_the_one_to_move(self, gui):
        online(gui, PLAYER1_PIECE)
        gui.on_game_start({'move_time': 30, 'turn_seconds_left': 25})
        gui.game = ConnectFourGame.from_moves([3])                  # sira rakipte
        gui.on_opponent_disconnected({'grace_seconds': 30})
        assert gui.turn_seconds_left() == 25
        gui.on_opponent_reconnected({})
        assert gui.turn_seconds_left() == 25

    def test_warn_tone_exists_in_the_sound_table(self):
        assert 'warn' in gui_app.SFX_TONES


# =============================================================================
# A3 / A4: hukmen sonucunun nedeni ve rejoin'de sunucunun sonucu
# =============================================================================

class TestForfeitDetail:
    @pytest.mark.parametrize("detail, mine, text, tone", [
        ('timeout', PLAYER2_PIECE, "Sure doldu - hukmen kaybettin.", 'bad'),
        ('timeout', PLAYER1_PIECE, "Rakibin suresi doldu - Kazandin!", 'good'),
        ('disconnect', PLAYER2_PIECE, "Baglanti kopmasi nedeniyle hukmen kaybettin.", 'bad'),
        ('disconnect', PLAYER1_PIECE, "Rakibin baglantisi koptu - Kazandin!", 'good'),
        ('leave', PLAYER2_PIECE, "Hukmen kaybettin.", 'bad'),
        ('leave', PLAYER1_PIECE, "Rakip oyunu terk etti - Kazandin!", 'good'),
        (None, PLAYER2_PIECE, "Hukmen kaybettin.", 'bad'),                  # eski sunucu: bugunku metinler
        (None, PLAYER1_PIECE, "Rakip oyunu terk etti - Kazandin!", 'good'),
    ])
    def test_player_texts(self, gui, detail, mine, text, tone):
        online(gui, mine, [3])
        gui.on_game_over_network({'winner': 1, 'reason': 'forfeit', 'detail': detail})
        assert gui.status_text == text and gui.status_tone == tone
        assert gui.result_headline()[0] == ("KAZANDIN!" if tone == 'good' else "KAYBETTIN")

    @pytest.mark.parametrize("detail, suffix", [('timeout', " (sure doldu)"), ('disconnect', " (baglanti koptu)"),
                                                ('leave', " (hukmen)"), (None, " (hukmen)")])
    def test_spectator_texts(self, gui, detail, suffix):
        online(gui, 0, [3])
        gui.state, gui.is_spectator = "SPECTATING", True
        gui.on_game_over_network({'winner': 1, 'reason': 'forfeit', 'detail': detail})
        assert gui.status_text == "Kirmizi kazandi!" + suffix

    def test_normal_result_ignores_detail_and_keeps_elo(self, gui):
        online(gui, PLAYER2_PIECE, P1_WIN)
        gui.on_game_over_network({'winner': 1, 'reason': 'normal', 'detail': None,
                                  'elo_changes': {'p1': 15, 'p2': -15}, 'new_ratings': {'p1': 1215, 'p2': 1185}})
        assert gui.status_text == "Kaybettin.  ELO -15 (1185)"


class TestJoinedResult:
    def _joined(self, mine, result, **extra):
        data = {'room_id': 'AB12C', 'player_piece': mine, 'role': 'player', 'rejoined': True,
                'current_state': dict(ConnectFourGame.from_moves([3]).to_dict(), game_over=True,
                                      winner=PLAYER2_PIECE),
                'opponent_info': {'username': 'bob'}, 'game_no': 1}
        if result is not None:
            data['result'] = result
        data.update(extra)
        return data

    def test_server_result_with_elo_is_shown_on_rejoin(self, gui):
        online(gui, PLAYER1_PIECE, [3])
        gui.on_connection_lost(gui.network)
        result = {'winner': 2, 'reason': 'forfeit', 'detail': 'timeout', 'elo_changes': {'p1': -15, 'p2': 15},
                  'new_ratings': {'p1': 1185, 'p2': 1215}, 'move_count': 1}
        gui.on_game_joined(self._joined(PLAYER1_PIECE, result))
        assert gui.status_text == "Sure doldu - hukmen kaybettin.  ELO -15 (1185)" and gui.status_tone == 'bad'
        assert gui.user_elo == 1185 and gui.last_elo_change == -15
        assert gui.result_headline() == ("KAYBETTIN", COLORS['red']) and not gui.connection_down
        assert not gui.network.in_game and gui.sfx.played['lose'] == 1

    def test_without_result_todays_text_stays(self, gui):
        online(gui, PLAYER1_PIECE, [3])
        gui.on_connection_lost(gui.network)
        gui.on_game_joined(self._joined(PLAYER1_PIECE, None))
        assert gui.status_text == "bob kazandi!" and gui.status_tone == 'bad'

    def test_spectator_joining_a_finished_room_gets_the_result(self, gui):
        gui.spectate_game = None
        gui.state, gui.is_spectator = "SPECTATING", True
        state = dict(ConnectFourGame.from_moves(P1_WIN).to_dict())
        gui.on_game_joined({'room_id': 'AB12C', 'role': 'spectator', 'player_piece': 0, 'current_state': state,
                            'p1_info': {'username': 'a'}, 'p2_info': {'username': 'b'}, 'game_no': 1,
                            'result': {'winner': 1, 'reason': 'normal', 'detail': None}})
        assert gui.status_text == "Kirmizi kazandi!" and gui.result_headline()[0] == "KIRMIZI KAZANDI"
