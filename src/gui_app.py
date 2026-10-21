# =============================================================================
# MODULE: gui_app.py
# Connect Four Pro - Pygame istemcisi v6.0
# =============================================================================
"""
Ekranlar: Giris/Kayit, Ana Menu, AI zorluk secimi, Online Lobi, Rakip bekleme,
Oyun (AI / Online / Seyirci), Liderlik Tablosu, Mac Gecmisi.

Thread modeli:
  * Ana thread: Pygame dongusu; oyun durumunu YALNIZCA bu thread degistirir.
  * Ag olaylari ve HTTP cevaplari `post()` ile kuyruga birakilir, ana thread isler.
  * AI hamlesi ayri thread'de hesaplanir; sonuc oturum numarasiyla dogrulanir.

Kullanim:
    python gui_app.py                               # localhost:5000
    python gui_app.py https://abc123.ngrok-free.app # uzak sunucu
    (veya CONNECT4_SERVER ortam degiskeni)
"""

import os
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import json  # noqa: E402
import queue  # noqa: E402
import secrets  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from typing import Callable, List, Optional  # noqa: E402

import pygame  # noqa: E402

import config  # noqa: E402
from ai_vs_human import DIFFICULTY_DEPTHS, AIEngine  # noqa: E402
from game_core import COLS, PLAYER1_PIECE, PLAYER2_PIECE, ROWS, ConnectFourGame  # noqa: E402
from network_client import NetworkManager  # noqa: E402

log = config.get_logger("gui")
DEBUG = config.LOG_LEVEL == 'DEBUG'

# =============================================================================
# CONFIGURATION
# =============================================================================

CELL_SIZE = 80
BOARD_WIDTH = COLS * CELL_SIZE
BOARD_HEIGHT = ROWS * CELL_SIZE
BOARD_X, BOARD_Y = 20, 80
WINDOW_WIDTH = BOARD_WIDTH + 320
WINDOW_HEIGHT = BOARD_HEIGHT + 150
FPS = 60
ANALYSIS_DEPTH = 6
LEAVE_CONFIRM_SECONDS = 3


def resolve_server_url(argv: List[str]) -> str:
    url = argv[1] if len(argv) > 1 else config.CLIENT_SERVER_URL
    if not url.startswith('http'):
        url = 'http://' + url
    return url.rstrip('/')


SERVER_URL = resolve_server_url(sys.argv)

COLORS = {
    'bg': (26, 26, 46),
    'board': (15, 52, 96),
    'panel': (22, 33, 62),
    'red': (233, 69, 96),
    'yellow': (241, 196, 15),
    'white': (234, 234, 234),
    'gray': (127, 140, 141),
    'green': (46, 204, 113),
    'cell_bg': (10, 10, 21),
    'hover': (52, 152, 219),
    'button': (233, 69, 96),
    'waiting': (230, 126, 34),
    'playing': (46, 204, 113),
    'input_bg': (44, 62, 80),
    'input_active': (52, 152, 219),
    'win_highlight': (0, 255, 128),
}

AI_DEPTHS = DIFFICULTY_DEPTHS


# =============================================================================
# MAIN GUI CLASS
# =============================================================================

class ConnectFourGUI:
    def __init__(self, server_url: str = SERVER_URL):
        pygame.init()
        pygame.display.set_caption("Connect Four Pro")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.SysFont('segoeui', 36, bold=True)
        self.font_medium = pygame.font.SysFont('segoeui', 24)
        self.font_small = pygame.font.SysFont('segoeui', 18)
        self.font_tiny = pygame.font.SysFont('segoeui', 14)

        self.server_url = server_url
        self.events: "queue.Queue" = queue.Queue()

        self.state = "LOGIN"
        self.game = ConnectFourGame()
        self.ai: Optional[AIEngine] = None
        self.ai_thinking = False
        self.is_spectator = False

        # AI oturum yonetimi: eski AI thread'lerinin hamlelerini eler
        self.ai_session_id = 0
        self.ai_lock = threading.Lock()
        self.ai_cancel = threading.Event()        # Set edilince calisan arama durur
        self.pending_ai_move: Optional[int] = None
        self.pending_ai_session = -1

        # Kullanici
        self.username = ""
        self.user_id = None
        self.user_elo = config.DEFAULT_RATING
        self.is_guest = False
        self.opponent_name = "Rakip"
        self.opponent_elo = config.DEFAULT_RATING
        self.auth_pending = False

        # Online
        self.network = self._new_network()
        self.my_piece = PLAYER1_PIECE
        self.room_id: Optional[str] = None
        self.last_elo_change: Optional[int] = None
        self.final_status: Optional[str] = None   # Sunucunun game_over mesaji (yerel mesaj ezmez)
        self.leave_confirm_until = 0.0

        # Ekran verileri (arka planda cekilir)
        self.active_games: list = []
        self.last_lobby_refresh = 0.0
        self.lobby_fetching = False
        self.leaderboard_data: Optional[list] = None
        self.leaderboard_error = False
        self.history_data: Optional[list] = None
        self.history_error = False

        self.status_text = ""
        self.hover_col = -1
        self.buttons: list = []
        self.input_fields = {
            'username': {'value': '', 'active': False, 'rect': None},
            'password': {'value': '', 'active': False, 'rect': None},
        }
        self.active_input: Optional[str] = None

        # Tas dusme animasyonu
        self.animating = False
        self.anim_col = 0
        self.anim_y = 0.0
        self.anim_target_y = 0
        self.anim_piece = PLAYER1_PIECE
        self.anim_callback: Optional[Callable[[], None]] = None

        # Arka plan hamle analizi (Lichess tarzi) - online oyunlarda
        self.analysis_enabled = True
        self.analysis_data: list = []
        self.analysis_lock = threading.Lock()
        self.analysis_summary: Optional[dict] = None
        self.analysis_cancel = threading.Event()
        # Tek bir isci thread analizleri sirayla yapar (hamle basina thread acmak
        # GIL icin cizim dongusuyle yarisip FPS'i dusururdu)
        self.analysis_jobs: "queue.Queue" = queue.Queue()
        self.analysis_worker: Optional[threading.Thread] = None

        log.info("GUI hazir (sunucu: %s)", self.server_url)

    # =========================================================================
    # THREAD -> ANA THREAD KOPRUSU
    # =========================================================================

    def post(self, fn: Callable, *args) -> None:
        """Herhangi bir thread'den ana thread'de calistirilacak is ekler."""
        self.events.put((fn, args))

    def process_events(self) -> None:
        while True:
            try:
                fn, args = self.events.get_nowait()
            except queue.Empty:
                return
            try:
                fn(*args)
            except Exception:
                log.exception("Olay isleme hatasi: %s", getattr(fn, '__name__', fn))

    def run_in_background(self, work: Callable, on_done: Callable) -> None:
        """`work()` arka planda calisir; sonuc on_done(result, error) ile ana thread'e doner."""
        def runner():
            try:
                result = work()
            except Exception as e:
                self.post(on_done, None, e)
            else:
                self.post(on_done, result, None)
        threading.Thread(target=runner, daemon=True).start()

    def _new_network(self) -> NetworkManager:
        return NetworkManager(self.server_url, self.post, self)

    # =========================================================================
    # CIZIM YARDIMCILARI
    # =========================================================================

    def draw_text(self, text, font, color, x, y, center=True):
        surface = font.render(str(text), True, color)
        rect = surface.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surface, rect)

    def draw_button(self, text, x, y, w, h, color=None):
        pygame.draw.rect(self.screen, color or COLORS['button'], (x, y, w, h), border_radius=8)
        self.draw_text(text, self.font_small, COLORS['white'], x + w // 2, y + h // 2)
        return pygame.Rect(x, y, w, h)

    def draw_input_field(self, label, field_name, x, y, w, h, is_password=False):
        field = self.input_fields[field_name]
        self.draw_text(label, self.font_small, COLORS['gray'], x + w // 2, y - 15)
        color = COLORS['input_active'] if field['active'] else COLORS['input_bg']
        pygame.draw.rect(self.screen, color, (x, y, w, h), border_radius=6)
        pygame.draw.rect(self.screen, COLORS['white'], (x, y, w, h), 2, border_radius=6)
        display_text = '*' * len(field['value']) if is_password else (field['value'] or "...")
        self.draw_text(display_text, self.font_medium, COLORS['white'], x + w // 2, y + h // 2)
        field['rect'] = pygame.Rect(x, y, w, h)

    def draw_status_line(self, y=None, color=None):
        if self.status_text:
            self.draw_text(self.status_text, self.font_small, color or COLORS['gray'],
                           WINDOW_WIDTH // 2, y or WINDOW_HEIGHT - 30)

    def can_human_move(self) -> bool:
        if self.animating or self.game.game_over or self.is_spectator:
            return False
        if self.state == "PLAYING_AI":
            return self.game.current_player == PLAYER1_PIECE and not self.ai_thinking
        if self.state == "PLAYING_ONLINE":
            return self.game.current_player == self.my_piece
        return False

    # =========================================================================
    # OYUN EKRANI
    # =========================================================================

    def draw_board(self):
        bx, by = BOARD_X, BOARD_Y
        pygame.draw.rect(self.screen, COLORS['board'],
                         (bx - 10, by - 10, BOARD_WIDTH + 20, BOARD_HEIGHT + 20), border_radius=10)
        winning_positions = set(self.game.get_winning_positions())
        pulse = abs((time.time() * 3) % 2 - 1)

        for col in range(COLS):
            for row in range(ROWS):
                x = bx + col * CELL_SIZE + CELL_SIZE // 2
                y = by + (ROWS - 1 - row) * CELL_SIZE + CELL_SIZE // 2
                is_winning = (col, row) in winning_positions
                if is_winning:
                    glow_size = int(CELL_SIZE // 2 + 5 + pulse * 5)
                    pygame.draw.circle(self.screen, COLORS['win_highlight'], (x, y), glow_size)
                pygame.draw.circle(self.screen, COLORS['cell_bg'], (x, y), CELL_SIZE // 2 - 5)

                piece = self.game.get_cell(col, row)
                if piece:
                    color = COLORS['red'] if piece == PLAYER1_PIECE else COLORS['yellow']
                    pygame.draw.circle(self.screen, color, (x, y), CELL_SIZE // 2 - 8)
                    if is_winning:
                        pygame.draw.circle(self.screen, COLORS['white'], (x, y), CELL_SIZE // 2 - 8, 3)

        if self.hover_col >= 0 and self.can_human_move():
            pygame.draw.circle(self.screen, COLORS['hover'],
                               (bx + self.hover_col * CELL_SIZE + CELL_SIZE // 2, 50), CELL_SIZE // 2 - 10)

        if self.animating:
            color = COLORS['red'] if self.anim_piece == PLAYER1_PIECE else COLORS['yellow']
            pygame.draw.circle(self.screen, color,
                               (bx + self.anim_col * CELL_SIZE + CELL_SIZE // 2, int(self.anim_y)),
                               CELL_SIZE // 2 - 8)

    def _player_labels(self):
        """(p1_adi, p1_elo, p2_adi, p2_elo) - p2_elo None ise gosterilmez."""
        if self.state == "PLAYING_AI":
            depth = self.ai.depth if self.ai else '?'
            return self.username, self.user_elo, f"AI (D{depth})", None
        if self.is_spectator:
            return self.spectate_names[0], self.spectate_names[1], self.spectate_names[2], self.spectate_names[3]
        if self.my_piece == PLAYER1_PIECE:
            return self.username, self.user_elo, self.opponent_name, self.opponent_elo
        return self.opponent_name, self.opponent_elo, self.username, self.user_elo

    spectate_names = ("Oyuncu 1", config.DEFAULT_RATING, "Oyuncu 2", config.DEFAULT_RATING)

    def draw_info_panel(self):
        px, py = BOARD_WIDTH + 50, 80
        pygame.draw.rect(self.screen, COLORS['panel'], (px, py, 250, 360), border_radius=10)
        title = "IZLIYORSUNUZ" if self.is_spectator else "OYUN BILGISI"
        self.draw_text(title, self.font_medium, COLORS['waiting'] if self.is_spectator else COLORS['white'],
                       px + 125, py + 25)

        p1_name, p1_elo, p2_name, p2_elo = self._player_labels()
        for i, (piece, name, elo) in enumerate(((PLAYER1_PIECE, p1_name, p1_elo),
                                                (PLAYER2_PIECE, p2_name, p2_elo))):
            y = py + 70 + i * 60
            pygame.draw.circle(self.screen, COLORS['red'] if piece == PLAYER1_PIECE else COLORS['yellow'],
                               (px + 25, y), 15)
            self.draw_text(str(name)[:12], self.font_small, COLORS['white'], px + 50, y - 5, center=False)
            if elo is not None:
                self.draw_text(f"ELO: {elo}", self.font_tiny, COLORS['gray'], px + 50, y + 15, center=False)
            if self.game.current_player == piece and not self.game.game_over:
                self.draw_text("< SIRA", self.font_small, COLORS['green'], px + 210, y)

        if self.room_id:
            self.draw_text(f"Oda: {self.room_id}", self.font_medium, COLORS['hover'], px + 125, py + 200)
        self.draw_text(f"Hamle: {len(self.game.move_history)}", self.font_small, COLORS['gray'], px + 125, py + 235)

        if self.analysis_summary:
            s = self.analysis_summary
            self.draw_text("Hamle analizi (isabet)", self.font_tiny, COLORS['gray'], px + 125, py + 262)
            self.draw_text(f"Sen: %{s['my_accuracy']:.0f}   Rakip: %{s['opp_accuracy']:.0f}",
                           self.font_small, COLORS['white'], px + 125, py + 284)

        label = "Cikisi Onayla" if time.time() < self.leave_confirm_until else "Menu"
        return self.draw_button(label, px + 50, py + 305, 150, 40)

    def draw_game(self):
        if self.state == "PLAYING_ONLINE" and self.game.game_over:
            # Arka plan analizleri oyun bittikten sonra da tamamlanabilir
            self.analysis_summary = self.get_analysis_summary()
        self.screen.fill(COLORS['bg'])
        title = "CANLI YAYIN" if self.is_spectator else ("AI'ya Karsi" if self.state == "PLAYING_AI" else "Online Mac")
        self.draw_text(title, self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 30)
        self.draw_board()
        self.buttons = [('BACK', self.draw_info_panel())]
        pygame.draw.rect(self.screen, COLORS['panel'], (0, WINDOW_HEIGHT - 50, WINDOW_WIDTH, 50))
        self.draw_text(self.status_text, self.font_small, COLORS['white'], WINDOW_WIDTH // 2, WINDOW_HEIGHT - 25)

    # =========================================================================
    # DIGER EKRANLAR
    # =========================================================================

    def draw_login(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("CONNECT FOUR PRO", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 60)
        self.draw_text("Hosgeldiniz!", self.font_medium, COLORS['white'], WINDOW_WIDTH // 2, 110)
        cx, fw, fh = WINDOW_WIDTH // 2, 280, 45
        self.draw_input_field("Kullanici Adi", 'username', cx - fw // 2, 170, fw, fh)
        self.draw_input_field("Sifre", 'password', cx - fw // 2, 260, fw, fh, is_password=True)
        self.buttons = [
            ('DO_LOGIN', self.draw_button("Giris Yap", cx - 140, 340, 130, 45)),
            ('DO_REGISTER', self.draw_button("Kayit Ol", cx + 10, 340, 130, 45, COLORS['green'])),
        ]
        pygame.draw.line(self.screen, COLORS['gray'], (cx - 100, 420), (cx + 100, 420), 1)
        self.draw_text("veya", self.font_tiny, COLORS['gray'], cx, 420)
        self.buttons.append(('GUEST', self.draw_button("Misafir Olarak Devam", cx - 120, 450, 240, 45,
                                                       COLORS['panel'])))
        if self.status_text:
            ok = any(w in self.status_text.lower() for w in ('basarili', 'yapiliyor', 'olusturuluyor'))
            self.draw_status_line(WINDOW_HEIGHT - 40, COLORS['green'] if ok else COLORS['red'])

    def draw_menu(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("CONNECT FOUR PRO", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 50)
        if self.is_guest:
            self.draw_text(f"Misafir: {self.username}", self.font_small, COLORS['gray'], WINDOW_WIDTH // 2, 95)
        else:
            self.draw_text(self.username, self.font_medium, COLORS['white'], WINDOW_WIDTH // 2, 90)
            self.draw_text(f"ELO: {self.user_elo}", self.font_small, COLORS['green'], WINDOW_WIDTH // 2, 115)
        bw, bh, cx = 250, 48, WINDOW_WIDTH // 2 - 125
        items = [('AI', "Yapay Zekaya Karsi", None), ('LOBBY', "Online Lobi", None),
                 ('LEADERBOARD', "Liderlik Tablosu", None), ('HISTORY', "Mac Gecmisi", None),
                 ('LOGOUT', "Cikis Yap", COLORS['panel']), ('QUIT', "Oyunu Kapat", COLORS['gray'])]
        self.buttons = [(bid, self.draw_button(text, cx, 145 + i * 60, bw, bh, color))
                        for i, (bid, text, color) in enumerate(items)]
        self.draw_status_line()

    def draw_ai_select(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("ZORLUK SEVIYESI SEC", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 80)
        bw, bh, cx = 200, 50, WINDOW_WIDTH // 2 - 100
        self.buttons = []
        y = 180
        for name, depth in AI_DEPTHS.items():
            self.buttons.append((f'AI_{depth}', self.draw_button(f"{name} (D{depth})", cx, y, bw, bh)))
            y += 70
        self.buttons.append(('BACK', self.draw_button("Geri", cx, y + 30, bw, bh)))

    def draw_lobby(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("ONLINE LOBI", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 40)
        if time.time() - self.last_lobby_refresh > 2:
            self.refresh_active_games()
        self.buttons = [
            ('CREATE', self.draw_button("+ Yeni Oyun", 50, 80, 160, 45)),
            ('REFRESH', self.draw_button("Yenile", 230, 80, 100, 45)),
            ('BACK', self.draw_button("Geri", WINDOW_WIDTH - 150, 80, 100, 45)),
        ]
        pygame.draw.rect(self.screen, COLORS['panel'], (30, 140, WINDOW_WIDTH - 60, 35), border_radius=5)
        for txt, xpos in [("ODA", 80), ("OYUNCU 1", 200), ("OYUNCU 2", 380), ("DURUM", 530), ("ISLEM", 680)]:
            self.draw_text(txt, self.font_small, COLORS['white'], xpos, 157)
        y = 185
        if not self.active_games:
            self.draw_text("Aktif oyun yok. Yeni bir oyun olusturun!", self.font_medium, COLORS['gray'],
                           WINDOW_WIDTH // 2, 280)
        for i, g in enumerate(self.active_games[:8]):
            pygame.draw.rect(self.screen, COLORS['panel'] if i % 2 == 0 else COLORS['bg'], (30, y, WINDOW_WIDTH - 60, 45))
            rid = g.get('room_id', '?')
            self.draw_text(rid, self.font_small, COLORS['hover'], 80, y + 22)
            self.draw_text(f"{str(g.get('p1', '?'))[:8]} ({g.get('p1_elo', 0)})", self.font_small, COLORS['red'], 200, y + 22)
            if g.get('status') == 'WAITING':
                self.draw_text("Bekleniyor...", self.font_small, COLORS['waiting'], 380, y + 22)
                self.draw_text("Bekliyor", self.font_small, COLORS['waiting'], 530, y + 22)
                self.buttons.append((f'JOIN_{rid}', self.draw_button("Katil", 640, y + 5, 80, 35, COLORS['green'])))
            else:
                self.draw_text(f"{str(g.get('p2', '?'))[:8]} ({g.get('p2_elo', 0)})", self.font_small,
                               COLORS['yellow'], 380, y + 22)
                self.draw_text("Oyunda", self.font_small, COLORS['playing'], 530, y + 22)
                self.buttons.append((f'SPECTATE_{rid}', self.draw_button("Izle", 640, y + 5, 80, 35, COLORS['hover'])))
            y += 50
        self.draw_status_line()

    def draw_waiting(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("RAKIP BEKLENIYOR", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 150)
        if self.room_id:
            self.draw_text(f"Oda Kodu: {self.room_id}", self.font_large, COLORS['green'], WINDOW_WIDTH // 2, 250)
            self.draw_text("Rakip lobiden katilabilir!", self.font_medium, COLORS['white'], WINDOW_WIDTH // 2, 310)
        else:
            self.draw_text("Oda olusturuluyor...", self.font_medium, COLORS['white'], WINDOW_WIDTH // 2, 250)
        self.draw_text(f"Bekleniyor{'.' * (int(time.time() * 2) % 4)}", self.font_medium, COLORS['gray'],
                       WINDOW_WIDTH // 2, 380)
        self.buttons = [('BACK', self.draw_button("Iptal", WINDOW_WIDTH // 2 - 75, 450, 150, 45))]

    def draw_leaderboard(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("LIDERLIK TABLOSU", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 50)
        if self.leaderboard_error:
            self.draw_text("Sunucuya baglanilamadi", self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 200)
        elif self.leaderboard_data is None:
            self.draw_text("Yukleniyor...", self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 200)
        elif not self.leaderboard_data:
            self.draw_text("Henuz kayitli oyuncu yok", self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 200)
        else:
            for i, p in enumerate(self.leaderboard_data[:10]):
                self.draw_text(f"{i + 1}. {p['username']} - ELO: {p['rating']} (W:{p['wins']} L:{p['losses']})",
                               self.font_small, COLORS['yellow'] if i < 3 else COLORS['white'],
                               WINDOW_WIDTH // 2, 120 + i * 35)
        self.buttons = [('BACK', self.draw_button("Geri", WINDOW_WIDTH // 2 - 75, WINDOW_HEIGHT - 80, 150, 45))]

    def draw_history(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("MAC GECMISI", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 50)
        if self.is_guest:
            self.draw_text("Mac gecmisi sadece kayitli oyuncular icin tutulur.", self.font_medium,
                           COLORS['gray'], WINDOW_WIDTH // 2, 200)
        elif self.history_error:
            self.draw_text("Sunucuya baglanilamadi", self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 200)
        elif self.history_data is None:
            self.draw_text("Yukleniyor...", self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 200)
        elif not self.history_data:
            self.draw_text("Henuz online mac oynamadiniz.", self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 200)
        else:
            labels = {'win': ("KAZANDIN", COLORS['green']), 'loss': ("KAYBETTIN", COLORS['red']),
                      'draw': ("BERABERE", COLORS['yellow'])}
            for i, g in enumerate(self.history_data[:10]):
                y = 110 + i * 40
                opponent = g['player2'] if g['player1'] == self.username else g['player1']
                text, color = labels.get(g.get('result'), ("?", COLORS['gray']))
                try:
                    moves = len(json.loads(g.get('moves') or '[]'))
                except (ValueError, TypeError):
                    moves = 0
                date = (g.get('start_time') or '')[:16].replace('T', ' ')
                extra = " (hukmen)" if g.get('end_reason') == 'forfeit' else ""
                self.draw_text(date, self.font_small, COLORS['gray'], 60, y, center=False)
                self.draw_text(f"vs {opponent}", self.font_small, COLORS['white'], 260, y, center=False)
                self.draw_text(text + extra, self.font_small, color, 460, y, center=False)
                self.draw_text(f"{moves} hamle", self.font_small, COLORS['gray'], 680, y, center=False)
        self.buttons = [('BACK', self.draw_button("Geri", WINDOW_WIDTH // 2 - 75, WINDOW_HEIGHT - 80, 150, 45))]

    # =========================================================================
    # ARKA PLAN VERI CEKME
    # =========================================================================

    def refresh_active_games(self):
        """Lobi listesini arka planda yeniler (arayuzu bloklamaz)."""
        self.last_lobby_refresh = time.time()
        if self.lobby_fetching:
            return
        self.lobby_fetching = True

        def done(games, error):
            self.lobby_fetching = False
            if error is None:
                self.active_games = games
        self.run_in_background(self.network.fetch_active_games, done)

    def open_leaderboard(self):
        self.state = 'LEADERBOARD'
        self.leaderboard_data, self.leaderboard_error = None, False

        def done(data, error):
            self.leaderboard_data = data
            self.leaderboard_error = error is not None
        self.run_in_background(self.network.fetch_leaderboard, done)

    def open_history(self):
        self.state = 'HISTORY'
        self.history_data, self.history_error = None, False
        if self.is_guest:
            return

        def done(data, error):
            self.history_data = data
            self.history_error = error is not None
        self.run_in_background(lambda: self.network.fetch_history(self.username), done)

    def refresh_user_elo(self):
        if not self.username or self.is_guest:
            return

        def done(user, error):
            if user and user.get('rating') is not None:
                self.user_elo = user['rating']
        self.run_in_background(lambda: self.network.fetch_user(self.username), done)

    # =========================================================================
    # KIMLIK DOGRULAMA
    # =========================================================================

    def _credentials(self):
        return self.input_fields['username']['value'].strip(), self.input_fields['password']['value']

    def do_login(self):
        if self.auth_pending:
            return
        u, p = self._credentials()
        if not u or not p:
            self.set_status("Kullanici adi ve sifre gerekli!")
            return
        self.auth_pending = True
        self.set_status("Giris yapiliyor...")
        self.run_in_background(lambda: self.network.login(u, p), self._on_login_result)

    def _on_login_result(self, response, error):
        self.auth_pending = False
        if error is not None:
            self.set_status("Sunucuya baglanilamadi!")
        elif response.status_code == 200:
            user = response.json()['user']
            self._enter_menu(user['username'], user['user_id'], user.get('rating', config.DEFAULT_RATING), False)
            self.set_status(f"Hosgeldin {self.username}!")
        elif response.status_code == 401:
            self.set_status("Yanlis kullanici adi veya sifre!")
        elif response.status_code == 503:
            self.set_status("Sunucu veritabanina ulasamiyor. Misafir olarak devam edebilirsiniz.")
        else:
            self.set_status("Giris basarisiz!")

    def do_register(self):
        if self.auth_pending:
            return
        u, p = self._credentials()
        if not u or not p:
            self.set_status("Kullanici adi ve sifre gerekli!")
            return
        if len(u) < config.USERNAME_MIN_LENGTH or len(p) < config.PASSWORD_MIN_LENGTH:
            self.set_status(f"En az {config.USERNAME_MIN_LENGTH} karakter gerekli!")
            return
        self.auth_pending = True
        self.set_status("Hesap olusturuluyor...")
        self.run_in_background(lambda: self.network.signup(u, p), lambda r, e: self._on_register_result(u, r, e))

    def _on_register_result(self, username, response, error):
        self.auth_pending = False
        if error is not None:
            self.set_status("Sunucuya baglanilamadi!")
        elif response.status_code == 201:
            self._enter_menu(username, response.json().get('user_id'), config.DEFAULT_RATING, False)
            self.set_status(f"Kayit basarili! Hosgeldin {username}!")
        elif response.status_code == 409:
            self.set_status("Bu kullanici adi zaten alinmis!")
        elif response.status_code == 400:
            self.set_status("Gecersiz kullanici adi veya sifre (harf, rakam, _ . - kullanin)")
        elif response.status_code == 503:
            self.set_status("Sunucu veritabanina ulasamiyor.")
        else:
            self.set_status("Kayit basarisiz!")

    def guest_login(self):
        self._enter_menu(f"Misafir_{secrets.randbelow(10 ** 6):06d}", None, config.DEFAULT_RATING, True)
        self.set_status("")

    def _enter_menu(self, username, user_id, elo, is_guest):
        self.username, self.user_id, self.user_elo, self.is_guest = username, user_id, elo, is_guest
        self.state = "MENU"
        self.clear_inputs()
        log.info("Oturum acildi: %s (misafir=%s)", username, is_guest)

    def logout(self):
        self.username, self.user_id, self.user_elo, self.is_guest = "", None, config.DEFAULT_RATING, False
        self.state = "LOGIN"
        self.set_status("")
        self.clear_inputs()

    def clear_inputs(self):
        for f in self.input_fields.values():
            f['value'], f['active'] = '', False
        self.active_input = None

    # =========================================================================
    # AI YONETIMI
    # =========================================================================

    def invalidate_ai_session(self):
        """Calisan AI aramasini durdurur ve sonucunu gecersiz kilar (thread-safe)."""
        with self.ai_lock:
            self.ai_cancel.set()
            self.ai_cancel = threading.Event()
            self.ai_session_id += 1
            self.pending_ai_move = None
            self.pending_ai_session = -1
            self.ai_thinking = False
            self.ai = None

    def start_ai_game(self, depth):
        log.info("AI oyunu basliyor, derinlik=%d", depth)
        self.invalidate_ai_session()
        self.game = ConnectFourGame()
        with self.ai_lock:
            self.ai = AIEngine(PLAYER2_PIECE, depth=depth)
        self.my_piece = PLAYER1_PIECE
        self.state = "PLAYING_AI"
        self.is_spectator = False
        self.room_id = None
        self.analysis_summary = None
        self.set_status("Senin siran!")

    def ai_move(self, sid):
        """AI thread'i: hesaplar, sonucu oturum dogrulamasiyla birakir."""
        time.sleep(0.3)  # Hamleler arasinda dogal bir duraklama
        with self.ai_lock:
            if self.ai is None or sid != self.ai_session_id or self.state != "PLAYING_AI":
                return
            ai_ref, snapshot, cancel = self.ai, self.game.clone(), self.ai_cancel

        try:
            col = ai_ref.find_best_move(snapshot, cancel_event=cancel)
        except Exception:
            log.exception("AI hatasi")
            col = None

        with self.ai_lock:
            if sid != self.ai_session_id or self.state != "PLAYING_AI":
                return
            self.ai_thinking = False
            if col is not None:
                self.pending_ai_move = col
                self.pending_ai_session = sid

    def process_pending_ai_move(self):
        if self.pending_ai_move is None:
            return
        with self.ai_lock:
            valid = (self.ai is not None and self.state == "PLAYING_AI"
                     and self.pending_ai_session == self.ai_session_id)
            col = self.pending_ai_move
            self.pending_ai_move, self.pending_ai_session = None, -1
        if valid and not self.game.game_over and self.game.is_valid_location(col):
            self.animate_drop(col, self.game.next_row(col), PLAYER2_PIECE, lambda: self.finish_ai_move(col))

    def finish_ai_move(self, col):
        if self.state != "PLAYING_AI" or self.ai is None:
            return
        if not self.game.make_move(col):
            return
        if self.game.game_over:
            self.handle_game_over()
        else:
            self.set_status("Senin siran!")

    # =========================================================================
    # HAMLE ANALIZI (Lichess tarzi)
    # =========================================================================

    def start_background_analysis(self, game_state, move_num, player_piece, actual_col):
        """Hamle oncesi pozisyonda en iyi hamleyi arka planda hesaplar."""
        if not self.analysis_enabled:
            return
        self.analysis_jobs.put((self.analysis_cancel, game_state, move_num, player_piece, actual_col))
        if self.analysis_worker is None or not self.analysis_worker.is_alive():
            self.analysis_worker = threading.Thread(target=self._analysis_loop, daemon=True)
            self.analysis_worker.start()

    def _analysis_loop(self):
        while True:
            try:
                cancel, game_state, move_num, player_piece, actual_col = self.analysis_jobs.get(timeout=5)
            except queue.Empty:
                return  # Is yoksa thread kapanir; yeni is gelince yeniden baslar
            if cancel.is_set():
                continue
            try:
                best_col = AIEngine(player_piece, depth=ANALYSIS_DEPTH).find_best_move(game_state, cancel_event=cancel)
            except Exception:
                log.exception("Analiz hatasi")
                continue
            with self.analysis_lock:
                if cancel.is_set() or best_col is None:
                    continue  # Oyundan cikildi / baska oyuna gecildi
                self.analysis_data.append({
                    'move_num': move_num, 'player': player_piece,
                    'actual_col': actual_col, 'best_col': best_col,
                    'was_best': actual_col == best_col,
                })

    def get_analysis_summary(self):
        with self.analysis_lock:
            if not self.analysis_data:
                return None
            mine = [d for d in self.analysis_data if d['player'] == self.my_piece]
            theirs = [d for d in self.analysis_data if d['player'] != self.my_piece]

            def accuracy(moves):
                return sum(d['was_best'] for d in moves) / len(moves) * 100 if moves else 0.0
            return {
                'total_moves': len(self.analysis_data),
                'my_accuracy': accuracy(mine),
                'opp_accuracy': accuracy(theirs),
                'mistakes': [d for d in self.analysis_data if not d['was_best']],
            }

    # =========================================================================
    # ONLINE OYUN
    # =========================================================================

    def create_online_game(self):
        self.invalidate_ai_session()
        self.room_id = None
        self.state = "WAITING"
        self.set_status("")
        self.run_in_background(lambda: self.network.create_game(self.username),
                               lambda ok, err: ok or self._connection_failed())

    def join_online_game(self, room_id):
        self.invalidate_ai_session()
        self.room_id = room_id.upper()
        self.is_spectator = False
        self.set_status("Odaya katiliniyor...")
        self.run_in_background(lambda: self.network.join_game(self.room_id, self.username),
                               lambda ok, err: ok or self._connection_failed())

    def spectate_game(self, room_id):
        self.invalidate_ai_session()
        self.room_id = room_id.upper()
        self.is_spectator = True
        self._reset_online_game()
        self.state = "SPECTATING"
        self.set_status("Yayina baglaniliyor...")
        self.run_in_background(lambda: self.network.join_game(self.room_id, self.username),
                               lambda ok, err: ok or self._connection_failed())

    def _connection_failed(self):
        self.set_status("Sunucuya baglanilamadi!")
        if self.state in ("WAITING", "SPECTATING"):
            self.state = "LOBBY"

    def _cancel_analysis(self):
        with self.analysis_lock:
            self.analysis_cancel.set()
            self.analysis_cancel = threading.Event()
            self.analysis_data = []

    def _reset_online_game(self):
        self.game = ConnectFourGame()
        self.last_elo_change = None
        self.final_status = None
        self.analysis_summary = None
        self._cancel_analysis()

    # --- Sunucu olaylari (ana thread'de calisir) ---

    def on_game_created(self, data):
        self.room_id, self.my_piece = data['room_id'], data['player_piece']
        self.state, self.is_spectator = "WAITING", False
        self.set_status(f"Oda: {self.room_id}")

    def on_game_joined(self, data):
        self.room_id, self.my_piece = data['room_id'], data.get('player_piece', 0)
        if data.get('role') == 'spectator':
            self.is_spectator, self.state = True, "SPECTATING"
            p1, p2 = data.get('p1_info') or {}, data.get('p2_info') or {}
            self.spectate_names = (p1.get('username', 'Oyuncu 1'), p1.get('rating', config.DEFAULT_RATING),
                                   p2.get('username', 'Oyuncu 2'), p2.get('rating', config.DEFAULT_RATING))
            if 'current_state' in data:
                self.game.from_dict(data['current_state'])
            self.set_status("Canli izleniyor")
            return

        self.is_spectator = False
        oi = data.get('opponent_info') or {}
        self.opponent_name = oi.get('username', 'Rakip')
        self.opponent_elo = oi.get('rating', config.DEFAULT_RATING)
        if data.get('rejoined'):
            # Kopma sonrasi geri donus: oyunu sunucudaki durumdan surdur
            self.game.from_dict(data['current_state'])
            self.state = "PLAYING_ONLINE"
            self.animating = False
            self.set_status("Oyuna geri donuldu. " + ("Senin siran!" if self.game.current_player == self.my_piece
                                                       else "Rakibin sirasi..."))

    def on_game_start(self, data):
        log.info("Online oyun basliyor")
        self.invalidate_ai_session()
        self._reset_online_game()
        self.state = "PLAYING_ONLINE"
        self.is_spectator = False
        self.opponent_name = data.get('opponent_name') or 'Rakip'
        self.opponent_elo = data.get('opponent_elo', config.DEFAULT_RATING)
        self.set_status("Oyun basladi!" + (" Senin siran." if self.game.current_player == self.my_piece
                                           else " Rakibin sirasi."))

    def on_move_made(self, data):
        """
        Sunucu hamleyi odadaki herkese yayinlar. Socket.IO istemcisi olaylari ayri
        thread'lerde isledigi icin siralari karisabilir; hamle gecmisinin uzunluguna
        gore karar verilir:
          sunucu < local      -> eski olay, yok say
          sunucu == local     -> kendi hamlemin yankisi, sadece senkronize et
          sunucu == local + 1 -> rakibin yeni hamlesi, animasyonla uygula
          sunucu >  local + 1 -> arada kacan hamle var, durumu dogrudan al
        """
        col = data.get('col')
        if col is None or self.state not in ("PLAYING_ONLINE", "SPECTATING"):
            return
        if self.animating:  # Onceki animasyonu tamamla ki local durum guncel olsun
            self.anim_y = self.anim_target_y
            self.update_animation()

        server_len, local_len = len(data.get('history', [])), len(self.game.move_history)
        if server_len < local_len:
            return
        if server_len == local_len:
            self.game.from_dict(data)
            if self.game.game_over:
                self.handle_game_over()
            elif not self.is_spectator:
                self.set_status("Rakibin sirasi...")
            return
        if server_len > local_len + 1 or self.game.game_over:
            self.apply_network_move(data)
            return
        # Hamleyi yapan = local durumda sirasi gelen (sunucunun 'current' alani
        # kazandiran/berabere hamlede degismedigi icin guvenilir degil)
        mover = self.game.current_player
        self.animate_drop(col, self.game.next_row(col), mover, lambda: self.apply_network_move(data))

    def apply_network_move(self, data):
        col = data.get('col')
        if self.state == "PLAYING_ONLINE" and col is not None and len(self.game.move_history) < len(data['history']):
            self.start_background_analysis(self.game.clone(), len(self.game.move_history),
                                           self.game.current_player, col)
        self.game.from_dict(data)
        if self.game.game_over:
            self.handle_game_over()
        elif self.is_spectator:
            self.set_status("Canli izleniyor")
        elif self.game.current_player == self.my_piece:
            self.set_status("Senin siran!")
        else:
            self.set_status("Rakibin sirasi...")

    def on_game_over_network(self, data):
        w = data.get('winner')
        reason = data.get('reason', 'normal')
        if reason == 'forfeit' and not self.game.game_over:
            self.game.game_over, self.game.winner = True, w
        if not self.is_spectator and self.my_piece in (PLAYER1_PIECE, PLAYER2_PIECE):
            key = 'p1' if self.my_piece == PLAYER1_PIECE else 'p2'
            change = (data.get('elo_changes') or {}).get(key)
            new_rating = (data.get('new_ratings') or {}).get(key)
            if change:
                self.last_elo_change = change
                if new_rating is not None:
                    self.user_elo = new_rating
        if self.is_spectator:
            msg = "Kirmizi kazandi!" if w == PLAYER1_PIECE else ("Sari kazandi!" if w == PLAYER2_PIECE else "Berabere!")
            if reason == 'forfeit':
                msg += " (hukmen)"
        elif w is None:
            msg = "Berabere!"
        elif w == self.my_piece:
            msg = "Rakip oyunu terk etti - Kazandin!" if reason == 'forfeit' else "Kazandin!"
        else:
            msg = "Hukmen kaybettin." if reason == 'forfeit' else "Kaybettin."
        if self.last_elo_change:
            sign = '+' if self.last_elo_change > 0 else ''
            msg += f"  ELO {sign}{self.last_elo_change} ({self.user_elo})"
        self.final_status = msg
        self.set_status(msg)
        self.analysis_summary = self.get_analysis_summary()
        self.refresh_user_elo()

    def on_elo_update(self, data):
        self.user_elo = data.get('new_elo', self.user_elo)
        self.last_elo_change = data.get('change', 0)

    def on_opponent_disconnected(self, data):
        if self.state == "PLAYING_ONLINE" and not self.game.game_over:
            grace = data.get('grace_seconds', config.RECONNECT_GRACE_SECONDS)
            self.set_status(f"Rakibin baglantisi koptu! {grace} sn icinde donmezse kazanirsin.")
        elif self.is_spectator:
            self.set_status("Bir oyuncunun baglantisi koptu...")

    def on_opponent_reconnected(self, data):
        if self.state in ("PLAYING_ONLINE", "SPECTATING") and not self.game.game_over:
            turn = "Senin siran!" if self.game.current_player == self.my_piece else "Rakibin sirasi..."
            self.set_status("Rakip geri dondu. " + ("" if self.is_spectator else turn))

    def on_game_ended(self, data):
        if not self.game.game_over:
            self.set_status("Oda zaman asimi nedeniyle kapatildi.")

    def on_server_error(self, data):
        msg = data.get('msg', '') if isinstance(data, dict) else str(data)
        self.set_status(f"Hata: {msg}")
        if self.state in ("SPECTATING", "WAITING") and not self.game.move_history and msg == 'Oda bulunamadi':
            self.state = "LOBBY"

    # =========================================================================
    # OYUN MANTIGI
    # =========================================================================

    def handle_click(self, col):
        if not self.can_human_move():
            return
        if self.state == "PLAYING_AI":
            with self.ai_lock:
                if self.ai is None:
                    return
        if not self.game.is_valid_location(col):
            return
        self.animate_drop(col, self.game.next_row(col), self.game.current_player, lambda: self.finish_move(col))

    def animate_drop(self, col, row, piece, callback):
        self.animating, self.anim_col, self.anim_piece = True, col, piece
        self.anim_y = 50
        self.anim_target_y = BOARD_Y + (ROWS - 1 - row) * CELL_SIZE + CELL_SIZE // 2
        self.anim_callback = callback

    def update_animation(self):
        if not self.animating:
            return
        self.anim_y += 18
        if self.anim_y >= self.anim_target_y:
            self.anim_y, self.animating = self.anim_target_y, False
            callback, self.anim_callback = self.anim_callback, None
            if callback:
                callback()

    def finish_move(self, col):
        if self.state == "PLAYING_ONLINE":
            before = self.game.clone()
            if not self.game.make_move(col):
                return
            self.start_background_analysis(before, len(before.move_history), before.current_player, col)
            self.network.send_move(col)
            if not self.game.game_over:
                self.set_status("Rakibin sirasi...")
            return  # Oyun sonu mesaji sunucunun game_over olayiyla gelir

        if self.state != "PLAYING_AI" or not self.game.make_move(col):
            return
        if self.game.game_over:
            self.handle_game_over()
            return
        with self.ai_lock:
            if self.ai is not None and self.game.current_player == PLAYER2_PIECE:
                self.set_status("AI dusunuyor...")
                self.ai_thinking = True
                threading.Thread(target=self.ai_move, args=(self.ai_session_id,), daemon=True).start()

    def handle_game_over(self):
        w = self.game.winner
        if self.final_status and self.state != "PLAYING_AI":
            # Sunucunun sonucu (ELO dahil) animasyon bitmeden geldiyse onu koru
            self.set_status(self.final_status)
            return
        if self.state == "PLAYING_AI":
            self.set_status("Kazandin!" if w == PLAYER1_PIECE else ("AI kazandi!" if w == PLAYER2_PIECE else "Berabere!"))
        elif self.is_spectator:
            self.set_status("Kirmizi kazandi!" if w == PLAYER1_PIECE else ("Sari kazandi!" if w == PLAYER2_PIECE else "Berabere!"))
        else:
            self.set_status("Berabere!" if w is None else ("Kazandin!" if w == self.my_piece
                                                           else f"{self.opponent_name} kazandi!"))

    def set_status(self, text):
        self.status_text = text

    def request_back(self):
        """Menu/Geri/Iptal. Aktif online oyundan cikis onay ister (hukmen yenilgi)."""
        if self.state == "PLAYING_ONLINE" and not self.game.game_over:
            if time.time() > self.leave_confirm_until:
                self.leave_confirm_until = time.time() + LEAVE_CONFIRM_SECONDS
                self.set_status("Oyundan cikmak hukmen yenilgi sayilir. Onaylamak icin tekrar basin.")
                return
        self.reset_to_menu()

    def reset_to_menu(self):
        self.invalidate_ai_session()
        self._cancel_analysis()
        self.analysis_summary = None
        self.leave_confirm_until = 0.0
        if self.state in ("PLAYING_ONLINE", "WAITING"):
            self.network.leave_game()
        network, self.network = self.network, self._new_network()
        threading.Thread(target=network.disconnect, daemon=True).start()
        self.room_id, self.is_spectator = None, False
        self.animating = False
        self.game = ConnectFourGame()
        self.state = "MENU" if self.username else "LOGIN"
        self.set_status("")
        self.refresh_user_elo()

    def shutdown(self):
        self.invalidate_ai_session()
        self._cancel_analysis()
        if self.state in ("PLAYING_ONLINE", "WAITING"):
            self.network.leave_game()
        self.network.disconnect()
        pygame.quit()
        sys.exit()

    # =========================================================================
    # GIRDI
    # =========================================================================

    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.shutdown()
            elif e.type == pygame.MOUSEMOTION:
                self.hover_col = self._board_column(e.pos)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.handle_mouse_click(e.pos)
            elif e.type == pygame.KEYDOWN and self.state == "LOGIN":
                self.handle_login_key(e)

    def _board_column(self, pos) -> int:
        mx, my = pos
        if (self.state in ("PLAYING_AI", "PLAYING_ONLINE") and BOARD_X <= mx < BOARD_X + BOARD_WIDTH
                and BOARD_Y <= my <= BOARD_Y + BOARD_HEIGHT):
            return (mx - BOARD_X) // CELL_SIZE
        return -1

    def handle_mouse_click(self, pos):
        if self.state == "LOGIN":
            for name, field in self.input_fields.items():
                if field['rect'] and field['rect'].collidepoint(pos):
                    self._activate_input(name)
                    return
        for bid, rect in self.buttons:
            if rect.collidepoint(pos):
                self.handle_button_click(bid)
                return
        col = self._board_column(pos)
        if col >= 0:
            self.handle_click(col)

    def _activate_input(self, name):
        for field_name, field in self.input_fields.items():
            field['active'] = field_name == name
        self.active_input = name

    def handle_login_key(self, e):
        if self.active_input is None:
            return
        field = self.input_fields[self.active_input]
        if e.key == pygame.K_RETURN:
            if self.active_input == 'username':
                self._activate_input('password')
            else:
                self.do_login()
        elif e.key == pygame.K_TAB:
            self._activate_input('password' if self.active_input == 'username' else 'username')
        elif e.key == pygame.K_BACKSPACE:
            field['value'] = field['value'][:-1]
        elif e.unicode and e.unicode.isprintable() and len(field['value']) < config.USERNAME_MAX_LENGTH:
            field['value'] += e.unicode

    def handle_button_click(self, bid):
        actions = {
            'DO_LOGIN': self.do_login,
            'DO_REGISTER': self.do_register,
            'GUEST': self.guest_login,
            'LOGOUT': self.logout,
            'BACK': self.request_back,
            'REFRESH': lambda: (self.refresh_active_games(), self.set_status("Yenilendi")),
            'AI': lambda: setattr(self, 'state', 'AI_SELECT'),
            'LOBBY': self.open_lobby,
            'LEADERBOARD': self.open_leaderboard,
            'HISTORY': self.open_history,
            'CREATE': self.create_online_game,
            'QUIT': self.shutdown,
        }
        if bid in actions:
            actions[bid]()
        elif bid.startswith('AI_'):
            self.start_ai_game(int(bid.split('_')[1]))
        elif bid.startswith('JOIN_'):
            self.join_online_game(bid[len('JOIN_'):])
        elif bid.startswith('SPECTATE_'):
            self.spectate_game(bid[len('SPECTATE_'):])

    def open_lobby(self):
        self.state = 'LOBBY'
        self.set_status("")
        self.refresh_active_games()

    # =========================================================================
    # ANA DONGU
    # =========================================================================

    SCREENS = {'LOGIN': 'draw_login', 'MENU': 'draw_menu', 'AI_SELECT': 'draw_ai_select',
               'LOBBY': 'draw_lobby', 'WAITING': 'draw_waiting', 'LEADERBOARD': 'draw_leaderboard',
               'HISTORY': 'draw_history'}

    def draw(self):
        getattr(self, self.SCREENS.get(self.state, 'draw_game'))()

    def tick(self):
        """Tek kare: olaylar, animasyon, AI, cizim."""
        self.process_events()
        self.handle_events()
        self.update_animation()
        self.process_pending_ai_move()
        self.draw()
        pygame.display.flip()

    def run(self):
        while True:
            self.tick()
            self.clock.tick(FPS)


if __name__ == "__main__":
    ConnectFourGUI().run()
