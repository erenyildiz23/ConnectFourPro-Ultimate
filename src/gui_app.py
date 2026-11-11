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
    CONNECT4_MUTE=1 python gui_app.py               # sessiz (oyunda M tusu / menuden acilir)

Klavye: 1-7 hamle, Esc geri, M ses ac/kapat.
"""

import os

# CONNECT4_MUTE=1: ses kapali baslar ve SDL ses aygiti hic acilmaz (ses karti olmayan
# makinelerde ALSA uyarilari ve acilis gecikmesi olmaz). pygame import edilmeden okunmali.
CLIENT_MUTED = os.environ.get('CONNECT4_MUTE') == '1'
if CLIENT_MUTED:
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import json  # noqa: E402
import math  # noqa: E402
import queue  # noqa: E402
import secrets  # noqa: E402
import sys  # noqa: E402
from array import array  # noqa: E402
from collections import Counter  # noqa: E402
from functools import lru_cache  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from typing import Callable, List, Optional, Tuple  # noqa: E402

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
INFO_PANEL_X, INFO_PANEL_Y = BOARD_WIDTH + 50, 80
FPS = 60
ANALYSIS_DEPTH = 8
LEAVE_CONFIRM_SECONDS = 3
INPUT_PADDING = 10
# Tas dusme fizigi (Unity istemcisindeki BoardView ile ayni degerler), piksel ve saniye cinsinden
DROP_GRAVITY = 5200.0
DROP_START_SPEED = 300.0
HOVER_Y = 50              # Tahtanin ustunde bekleyen / dusmeye baslayan tasin merkezi
RING_WIDTH = 3
HOVER_LIGHTEN = 22        # Fare dugmenin uzerindeyken kanal basina aydinlatma
DIM_AMOUNT = 0.55         # Oyun dortluyle bitince diger taslarin arka plana karisma orani
TURN_TINT = 0.22          # Bilgi panelinde sirasi gelen oyuncunun satir vurgusu
LOBBY_REFRESH_SECONDS = 2
RECONNECT_WARN_SECONDS = 20   # Bu kadar surede geri donulemezse oyuncuya secenek hatirlatilir
# Kopma sonrasi odaya geri donus isteginin reddedildigini gosteren sunucu hatalari
REJOIN_REFUSED_ERRORS = ('Oda bulunamadi', 'Yeniden baglanma anahtari gecersiz')
LOBBY_RETURN_DELAY = 0.5  # Oyundan lobiye donuste ilk liste yenilemesinden once bekleme (sn)


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
    'button': (190, 40, 68),      # Tas kirmizisindan koyu: beyaz yazi 4.88:1
    'error': (255, 107, 129),     # Hata metni (panel uzerinde 5.8:1; tas kirmizisi 4.15:1 kalir)
    'waiting': (230, 126, 34),
    'playing': (46, 204, 113),
    'input_bg': (44, 62, 80),
    'input_active': (52, 152, 219),
    'win_highlight': (0, 255, 128),
}

AI_DEPTHS = DIFFICULTY_DEPTHS

# Hamle tuslari: 1-7 (ust sira ve sayisal tus takimi) -> sutun 0-6
COLUMN_KEYS = {base + i: i for base in (pygame.K_1, pygame.K_KP1) for i in range(COLS)}

# -----------------------------------------------------------------------------
# Ses efektleri: dosya yok, tonlar calisma aninda uretilir (yalnizca standart kutuphane).
# Tablo Unity istemcisindeki ToneSynth ile ayni tutulmalidir:
#   ad: (tepe genlik, [(frekans Hz, sure sn), ...]) ; 'drop' 220 -> 110 Hz kayan tek tondur.
# Tas inisi ile sonuc sesi ayni karede calabilir: drop + win = 0.85 (< -1 dBFS).
# -----------------------------------------------------------------------------
SFX_TONES = {
    'click': (0.15, [(880, 0.035)]),
    'drop': (0.45, [(220, 0.110)]),
    'turn': (0.30, [(659, 0.070), (880, 0.070)]),
    'start': (0.35, [(392, 0.080), (523, 0.080), (659, 0.080)]),
    'win': (0.40, [(523, 0.090), (659, 0.090), (784, 0.090), (1047, 0.250)]),
    'lose': (0.35, [(330, 0.160), (262, 0.160)]),
    'draw': (0.30, [(440, 0.100), (440, 0.100)]),
    'invalid': (0.20, [(110, 0.080)]),
}
SFX_ATTACK = 0.003                 # Dogrusal giris (sn)
SFX_FADE = 0.005                   # Sonda sifira inis: tik sesi olmasin
SFX_DROP_TAU = 0.030
SFX_DROP_PITCHES = (0.94, 1.0, 1.06)   # Ust uste hamlelerde ayni ses tekrarlanmasin


def render_sfx(name: str, rate: int = 44100, pitch: float = 1.0) -> array:
    """Efekti tek kanal, isaretli 16 bit ornekler olarak uretir."""
    peak, notes = SFX_TONES[name]
    samples = array('h')
    phase = 0.0
    for freq, duration in notes:
        count = round(duration * rate)
        tau = SFX_DROP_TAU if name == 'drop' else duration / 3
        for i in range(count):
            t = i / rate
            f = freq * pitch * (1 - 0.5 * i / count if name == 'drop' else 1)
            phase += 2 * math.pi * f / rate
            envelope = min(1.0, t / SFX_ATTACK) * math.exp(-t / tau)
            samples.append(int(32767 * peak * envelope * math.sin(phase)))
        phase = 0.0
    fade = min(len(samples), round(SFX_FADE * rate))
    for i in range(fade):
        samples[-1 - i] = int(samples[-1 - i] * i / fade)
    samples[0] = 0
    return samples


@lru_cache(maxsize=None)
def _sfx_buffer(name: str, rate: int, channels: int, pitch: float) -> bytes:
    mono = render_sfx(name, rate, pitch)
    return array('h', [v for v in mono for _ in range(channels)]).tobytes()


class Sfx:
    """Ses efektleri. Mikser yoksa veya ses kapaliysa sessizce hicbir sey yapmaz."""

    def __init__(self, muted: bool = False):
        self.muted = muted
        self.played: Counter = Counter()      # Istenen efektler (sessizken de sayilir; testler icin)
        self.sounds: dict = {}
        self.ok = False
        self._last_drop = -1
        try:
            fmt = pygame.mixer.get_init()
            if not fmt or fmt[1] != -16:        # Aygit yok ya da beklenmeyen ornek bicimi
                return
            rate, _, channels = fmt
            for name in SFX_TONES:
                pitches = SFX_DROP_PITCHES if name == 'drop' else (1.0,)
                self.sounds[name] = [pygame.mixer.Sound(buffer=_sfx_buffer(name, rate, channels, p))
                                     for p in pitches]
            self.ok = True
        except (pygame.error, NotImplementedError, AttributeError) as e:
            log.info("Ses kullanilamiyor: %s", e)
            self.sounds = {}

    def play(self, name: str) -> None:
        self.played[name] += 1
        if self.muted or not self.ok:
            return
        variants = self.sounds[name]
        index = 0
        if len(variants) > 1:
            index = secrets.choice([i for i in range(len(variants)) if i != self._last_drop])
            self._last_drop = index
        try:
            variants[index].play()
        except pygame.error:
            pass

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted


def relative_luminance(rgb) -> float:
    """WCAG bagil parlaklik (0 = siyah, 1 = beyaz)."""
    def channel(v):
        v = v / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    """WCAG kontrast orani (1..21)."""
    hi, lo = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def blend(base, toward, t):
    """base renginden toward rengine t (0..1) oraninda karisim."""
    return tuple(round(b + (o - b) * t) for b, o in zip(base, toward, strict=True))


def button_fill(color, hover=False):
    """Dugme dolgusu; fare uzerindeyken biraz acilir."""
    return tuple(min(255, c + HOVER_LIGHTEN) for c in color) if hover else tuple(color)


def on_color(fill):
    """Dolgu renginin uzerinde okunabilir yazi rengi: acik dolguda koyu, koyu dolguda beyaz."""
    return COLORS['bg'] if relative_luminance(fill) > 0.2 else COLORS['white']


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
        self.sfx = Sfx(muted=CLIENT_MUTED)
        self.result_sound_played = False

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
        self.auth_token: Optional[str] = None   # /login token'i; misafirde None
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
        # Baglanti durumu (UC-11)
        self.connection_down = False              # Kendi baglantimiz koptu, geri donus bekleniyor
        self.connection_lost_at = 0.0
        self.reconnect_warned = False
        self.room_closed = False                  # Oda artik yok: hamle gonderilemez
        self.opponent_deadline: Optional[float] = None   # Rakibin geri donmesi icin son an
        self.opponent_remaining = -1              # Durum satirinda gosterilen saniye

        # Ekran verileri (arka planda cekilir)
        self.active_games: list = []
        self.last_lobby_refresh = 0.0
        self.lobby_fetching = False
        self.leaderboard_data: Optional[list] = None
        self.leaderboard_error = False
        self.history_data: Optional[list] = None
        self.history_error = False

        self.status_text = ""
        self.status_tone = 'neutral'              # 'good' | 'bad' | 'neutral': durum satirinin rengi
        self.final_tone = 'neutral'
        self.hover_col = -1
        self.hovered_button: Optional[pygame.Rect] = None
        self.buttons: list = []
        self.input_fields = {
            'username': {'value': '', 'active': False, 'rect': None, 'text_rect': None,
                         'max_len': config.USERNAME_MAX_LENGTH},
            'password': {'value': '', 'active': False, 'rect': None, 'text_rect': None,
                         'max_len': config.PASSWORD_MAX_LENGTH},
        }
        self.active_input: Optional[str] = None
        self._activate_input('username')   # Acilista tiklamadan yazilabilsin

        # Tas dusme animasyonu
        self.animating = False
        self.anim_col = 0
        self.anim_y = 0.0
        self.anim_v = 0.0
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
        color = color or COLORS['button']
        rect = pygame.Rect(x, y, w, h)
        hover = rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen, button_fill(color, hover), rect, border_radius=8)
        if hover:
            self.hovered_button = rect
            pygame.draw.rect(self.screen, COLORS['white'], rect, 1, border_radius=8)
        self.draw_text(text, self.font_small, on_color(color), x + w // 2, y + h // 2)
        return rect

    def draw_input_field(self, label, field_name, x, y, w, h, is_password=False):
        field = self.input_fields[field_name]
        self.draw_text(label, self.font_small, COLORS['gray'], x + w // 2, y - 15)
        color = COLORS['input_active'] if field['active'] else COLORS['input_bg']
        pygame.draw.rect(self.screen, color, (x, y, w, h), border_radius=6)
        pygame.draw.rect(self.screen, COLORS['white'], (x, y, w, h), 2, border_radius=6)
        display_text = '*' * len(field['value']) if is_password else (field['value'] or "...")
        field['rect'] = pygame.Rect(x, y, w, h)
        # Metin kutuya sigmazsa kirpilir ve sonu gosterilir (128 karakterlik sifre pencereden genis)
        inner = field['rect'].inflate(-2 * INPUT_PADDING, 0)
        surface = self.font_medium.render(display_text, True, COLORS['white'])
        text_rect = surface.get_rect(center=field['rect'].center)
        if text_rect.width > inner.width:
            text_rect.right = inner.right
        field['text_rect'] = text_rect.clip(inner)
        previous_clip = self.screen.get_clip()
        self.screen.set_clip(inner)
        self.screen.blit(surface, text_rect)
        self.screen.set_clip(previous_clip)

    def draw_status_line(self, y=None):
        if self.status_text:
            self.draw_text(self.status_text, self.font_small, self.status_color(COLORS['gray']),
                           WINDOW_WIDTH // 2, y or WINDOW_HEIGHT - 30)

    def status_color(self, neutral=None):
        """Durum satirinin rengi: tona gore; oyunda sira oyuncudayken yesil (sira isareti)."""
        if self.status_tone == 'bad':
            return COLORS['error']
        if self.status_tone == 'good' or self.can_human_move():
            return COLORS['green']
        return neutral or COLORS['white']

    def can_human_move(self) -> bool:
        if self.animating or self.game.game_over or self.is_spectator:
            return False
        if self.state == "PLAYING_AI":
            return self.game.current_player == PLAYER1_PIECE and not self.ai_thinking
        if self.state == "PLAYING_ONLINE":
            # Baglanti yokken hamle sunucuya ulasmaz; yerelde de oynatilmaz
            return (self.game.current_player == self.my_piece
                    and not self.connection_down and not self.room_closed)
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
                x, y = self.cell_center(col, row)
                is_winning = (col, row) in winning_positions
                if is_winning:
                    glow_size = int(CELL_SIZE // 2 + 5 + pulse * 5)
                    pygame.draw.circle(self.screen, COLORS['win_highlight'], (x, y), glow_size)
                pygame.draw.circle(self.screen, COLORS['cell_bg'], (x, y), CELL_SIZE // 2 - 5)

                color = self.disc_color(col, row, winning_positions)
                if color:
                    pygame.draw.circle(self.screen, color, (x, y), CELL_SIZE // 2 - 8)
                    if is_winning:
                        pygame.draw.circle(self.screen, COLORS['white'], (x, y), CELL_SIZE // 2 - 8, 3)

        # Isaretler halka olarak cizilir: hucre merkezi (tasin rengi) degismez
        last = self.last_move_cell()
        if last is not None:
            pygame.draw.circle(self.screen, COLORS['white'], self.cell_center(*last),
                               CELL_SIZE // 2 - 8, RING_WIDTH)

        ghost = self.ghost_cell()
        if ghost is not None:
            color = self.piece_color(self.human_piece())
            pygame.draw.circle(self.screen, color,
                               (bx + ghost[0] * CELL_SIZE + CELL_SIZE // 2, HOVER_Y), CELL_SIZE // 2 - 10)
            pygame.draw.circle(self.screen, color, self.cell_center(*ghost), CELL_SIZE // 2 - 8, RING_WIDTH)

        if self.animating:
            pygame.draw.circle(self.screen, self.piece_color(self.anim_piece),
                               (bx + self.anim_col * CELL_SIZE + CELL_SIZE // 2, int(self.anim_y)),
                               CELL_SIZE // 2 - 8)

    @staticmethod
    def cell_center(col, row) -> Tuple[int, int]:
        return (BOARD_X + col * CELL_SIZE + CELL_SIZE // 2,
                BOARD_Y + (ROWS - 1 - row) * CELL_SIZE + CELL_SIZE // 2)

    @staticmethod
    def piece_color(piece):
        return COLORS['red'] if piece == PLAYER1_PIECE else COLORS['yellow']

    def disc_color(self, col, row, winning_positions=None):
        """Hucredeki tasin cizim rengi (bossa None). Oyun dortluyle bittiyse
        dortlunun disindaki taslar soluklasir; kazanan hat one cikar."""
        piece = self.game.get_cell(col, row)
        if not piece:
            return None
        if winning_positions is None:
            winning_positions = set(self.game.get_winning_positions())
        color = self.piece_color(piece)
        if winning_positions and (col, row) not in winning_positions:
            return blend(color, COLORS['cell_bg'], DIM_AMOUNT)
        return color

    def result_headline(self) -> Optional[Tuple[str, tuple]]:
        """Oyun bittiyse ekran basligina yazilacak (metin, renk); bitmediyse None."""
        if not self.game.game_over or self.state not in ("PLAYING_AI", "PLAYING_ONLINE", "SPECTATING"):
            return None
        w = self.game.winner
        if w is None:
            return "BERABERE", COLORS['white']
        if self.is_spectator:
            return ("KIRMIZI KAZANDI" if w == PLAYER1_PIECE else "SARI KAZANDI"), self.piece_color(w)
        if w == self.human_piece():
            return "KAZANDIN!", COLORS['green']
        return ("AI KAZANDI" if self.state == "PLAYING_AI" else "KAYBETTIN"), COLORS['red']

    def turn_highlight(self) -> Optional[Tuple[pygame.Rect, tuple]]:
        """Bilgi panelinde sirasi gelen oyuncunun satirinin arkasindaki (dikdortgen, renk)."""
        if self.game.game_over:
            return None
        piece = self.game.current_player
        y = INFO_PANEL_Y + 70 + (0 if piece == PLAYER1_PIECE else 1) * 60
        return (pygame.Rect(INFO_PANEL_X + 8, y - 26, 234, 52),
                blend(COLORS['panel'], self.piece_color(piece), TURN_TINT))

    def in_online_room(self) -> bool:
        return self.state in ("PLAYING_ONLINE", "WAITING", "SPECTATING")

    def human_piece(self) -> int:
        """Yerel oyuncunun tasi (AI oyununda her zaman kirmizi)."""
        return PLAYER1_PIECE if self.state == "PLAYING_AI" else self.my_piece

    def last_move_cell(self) -> Optional[Tuple[int, int]]:
        """Son oynanan tasin (sutun, satir) konumu; halka ile isaretlenir.

        Tas duserken ve oyun dortluyle bittiginde None (kazanan dortlu zaten vurgulanir).
        Hamle gecmisinden turetilir; yeniden baglanma / seyirci anlik durumunda da calisir.
        """
        if not self.game.move_history or self.animating or self.game.get_winning_positions():
            return None
        col = self.game.move_history[-1]
        return col, self.game.next_row(col) - 1

    def ghost_cell(self) -> Optional[Tuple[int, int]]:
        """Fare bir sutunun uzerindeyken tasin inecegi (sutun, satir); hamle yapilamiyorsa None."""
        col = self.hover_col
        if col < 0 or not self.can_human_move() or not self.game.is_valid_location(col):
            return None
        return col, self.game.next_row(col)

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
        px, py = INFO_PANEL_X, INFO_PANEL_Y
        pygame.draw.rect(self.screen, COLORS['panel'], (px, py, 250, 360), border_radius=10)
        highlight = self.turn_highlight()
        if highlight:
            pygame.draw.rect(self.screen, highlight[1], highlight[0], border_radius=8)
        title = "IZLIYORSUNUZ" if self.is_spectator else "OYUN BILGISI"
        self.draw_text(title, self.font_medium, COLORS['waiting'] if self.is_spectator else COLORS['white'],
                       px + 125, py + 25)

        p1_name, p1_elo, p2_name, p2_elo = self._player_labels()
        for i, (piece, name, elo) in enumerate(((PLAYER1_PIECE, p1_name, p1_elo),
                                                (PLAYER2_PIECE, p2_name, p2_elo))):
            y = py + 70 + i * 60
            pygame.draw.circle(self.screen, self.piece_color(piece), (px + 25, y), 15)
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

        hint = "Esc: cikis   M: ses" if self.is_spectator else "1-7: hamle   Esc: cikis   M: ses"
        self.draw_text(hint, self.font_tiny, COLORS['gray'], px + 125, py + 380)

        label = ("Cikisi Onayla" if time.time() < self.leave_confirm_until
                 else "Lobiye Don" if self.in_online_room() else "Menu")
        return self.draw_button(label, px + 50, py + 305, 150, 40)

    def draw_game(self):
        if self.state == "PLAYING_ONLINE" and self.game.game_over:
            # Arka plan analizleri oyun bittikten sonra da tamamlanabilir
            self.analysis_summary = self.get_analysis_summary()
        self.screen.fill(COLORS['bg'])
        title = "CANLI YAYIN" if self.is_spectator else ("AI'ya Karsi" if self.state == "PLAYING_AI" else "Online Mac")
        title_color = COLORS['red']
        headline = self.result_headline()
        if headline and not self.animating:
            title, title_color = headline     # Sonuc kucuk durum satirinda kalmasin
        self.draw_text(title, self.font_large, title_color, WINDOW_WIDTH // 2, 30)
        self.draw_board()
        self.buttons = [('BACK', self.draw_info_panel())]
        pygame.draw.rect(self.screen, COLORS['panel'], (0, WINDOW_HEIGHT - 50, WINDOW_WIDTH, 50))
        self.draw_text(self.status_text, self.font_small, self.status_color(), WINDOW_WIDTH // 2, WINDOW_HEIGHT - 25)

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
        self.draw_status_line(WINDOW_HEIGHT - 40)

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
                 ('MUTE', "Ses: Kapali" if self.sfx.muted else "Ses: Acik", COLORS['panel']),
                 ('LOGOUT', "Cikis Yap", COLORS['panel']), ('QUIT', "Oyunu Kapat", COLORS['gray'])]
        self.buttons = [(bid, self.draw_button(text, cx, 135 + i * 58, bw, bh, color))
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
        if time.time() - self.last_lobby_refresh > LOBBY_REFRESH_SECONDS:
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
            self.set_status("Kullanici adi ve sifre gerekli!", 'bad')
            return
        self.auth_pending = True
        self.set_status("Giris yapiliyor...")
        self.run_in_background(lambda: self.network.login(u, p), self._on_login_result)

    def _on_login_result(self, response, error):
        self.auth_pending = False
        if error is not None:
            self.set_status("Sunucuya baglanilamadi!", 'bad')
        elif response.status_code == 200:
            body = response.json()
            user = body['user']
            self._enter_menu(user['username'], user['user_id'], user.get('rating', config.DEFAULT_RATING), False,
                             body.get('token'))
            self.set_status(f"Hosgeldin {self.username}!", 'good')
        elif response.status_code == 401:
            self.set_status("Yanlis kullanici adi veya sifre!", 'bad')
        elif response.status_code == 429:
            self.set_status("Cok fazla deneme! Biraz sonra tekrar deneyin.", 'bad')
        elif response.status_code == 503:
            self.set_status("Sunucu veritabanina ulasamiyor. Misafir olarak devam edebilirsiniz.", 'bad')
        else:
            self.set_status("Giris basarisiz!", 'bad')

    def do_register(self):
        if self.auth_pending:
            return
        u, p = self._credentials()
        if not u or not p:
            self.set_status("Kullanici adi ve sifre gerekli!", 'bad')
            return
        if len(u) < config.USERNAME_MIN_LENGTH or len(p) < config.PASSWORD_MIN_LENGTH:
            self.set_status(f"Kullanici adi en az {config.USERNAME_MIN_LENGTH}, "
                            f"sifre en az {config.PASSWORD_MIN_LENGTH} karakter olmali!", 'bad')
            return
        self.auth_pending = True
        self.set_status("Hesap olusturuluyor...")
        self.run_in_background(lambda: self.network.signup(u, p), lambda r, e: self._on_register_result(u, r, e))

    def _on_register_result(self, username, response, error):
        self.auth_pending = False
        if error is not None:
            self.set_status("Sunucuya baglanilamadi!", 'bad')
        elif response.status_code == 201:
            body = response.json()
            self._enter_menu(username, body.get('user_id'), config.DEFAULT_RATING, False, body.get('token'))
            self.set_status(f"Kayit basarili! Hosgeldin {username}!", 'good')
        elif response.status_code == 409:
            self.set_status("Bu kullanici adi zaten alinmis!", 'bad')
        elif response.status_code == 400:
            self.set_status("Gecersiz kullanici adi veya sifre (harf, rakam, _ . - kullanin)", 'bad')
        elif response.status_code == 429:
            self.set_status("Cok fazla deneme! Biraz sonra tekrar deneyin.", 'bad')
        elif response.status_code == 503:
            self.set_status("Sunucu veritabanina ulasamiyor.", 'bad')
        else:
            self.set_status("Kayit basarisiz!", 'bad')

    def guest_login(self):
        self._enter_menu(f"Misafir_{secrets.randbelow(10 ** 6):06d}", None, config.DEFAULT_RATING, True)
        self.set_status("")

    def _enter_menu(self, username, user_id, elo, is_guest, token=None):
        self.username, self.user_id, self.user_elo, self.is_guest = username, user_id, elo, is_guest
        self.auth_token = token
        self.state = "MENU"
        self.clear_inputs()
        log.info("Oturum acildi: %s (misafir=%s)", username, is_guest)

    def logout(self):
        self.username, self.user_id, self.user_elo, self.is_guest = "", None, config.DEFAULT_RATING, False
        self.auth_token = None
        self.state = "LOGIN"
        self.set_status("")
        self.clear_inputs()
        self._activate_input('username')

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
        self.result_sound_played = False
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
        self.run_in_background(lambda: self.network.create_game(self.username, self.auth_token),
                               lambda ok, err: ok or self._connection_failed())

    def join_online_game(self, room_id):
        self.invalidate_ai_session()
        self.room_id = room_id.upper()
        self.is_spectator = False
        self.set_status("Odaya katiliniyor...")
        self.run_in_background(lambda: self.network.join_game(self.room_id, self.username, self.auth_token),
                               lambda ok, err: ok or self._connection_failed())

    def spectate_game(self, room_id):
        self.invalidate_ai_session()
        self.room_id = room_id.upper()
        self.is_spectator = True
        self._reset_online_game()
        self.state = "SPECTATING"
        self.set_status("Yayina baglaniliyor...")
        self.run_in_background(lambda: self.network.join_game(self.room_id, self.username, self.auth_token),
                               lambda ok, err: ok or self._connection_failed())

    def _connection_failed(self):
        self.set_status("Sunucuya baglanilamadi!", 'bad')
        if self.state in ("WAITING", "SPECTATING"):
            self.state = "LOBBY"

    def _cancel_analysis(self):
        with self.analysis_lock:
            self.analysis_cancel.set()
            self.analysis_cancel = threading.Event()
            self.analysis_data = []

    def _clear_connection_state(self):
        self.connection_down = self.reconnect_warned = self.room_closed = False
        self.opponent_deadline, self.opponent_remaining = None, -1

    def _reset_online_game(self):
        self.game = ConnectFourGame()
        self.result_sound_played = False
        self._clear_connection_state()
        self.last_elo_change = None
        self.final_status, self.final_tone = None, 'neutral'
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
            self.connection_down = self.reconnect_warned = self.room_closed = False
            if self.game.game_over:
                # Biz yokken oyun bitmis (or. sure dolup hukmen): "sira" mesaji yaniltici olurdu
                self.network.in_game = False
                self.opponent_deadline = None
                self.handle_game_over()
            else:
                self.set_status("Oyuna geri donuldu. " + ("Senin siran!" if self.game.current_player == self.my_piece
                                                           else "Rakibin sirasi..."))

    def on_game_start(self, data):
        log.info("Online oyun basliyor")
        self.invalidate_ai_session()
        self._reset_online_game()
        self.sfx.play('start')
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
            self.finish_animation(natural=False)

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
            self.sfx.play('turn')     # Rakip uzun dusunmus olabilir; baska yere bakan oyuncu duysun
        else:
            self.set_status("Rakibin sirasi...")

    def on_game_over_network(self, data):
        w = data.get('winner')
        reason = data.get('reason', 'normal')
        self._clear_connection_state()
        if reason == 'forfeit' and not self.game.game_over:
            self.game.game_over, self.game.winner = True, w
        self._play_result_once(w)
        if not self.is_spectator and self.my_piece in (PLAYER1_PIECE, PLAYER2_PIECE):
            key = 'p1' if self.my_piece == PLAYER1_PIECE else 'p2'
            change = (data.get('elo_changes') or {}).get(key)
            new_rating = (data.get('new_ratings') or {}).get(key)
            if change:
                self.last_elo_change = change
                if new_rating is not None:
                    self.user_elo = new_rating
        tone = 'neutral'
        if self.is_spectator:
            msg = "Kirmizi kazandi!" if w == PLAYER1_PIECE else ("Sari kazandi!" if w == PLAYER2_PIECE else "Berabere!")
            if reason == 'forfeit':
                msg += " (hukmen)"
        elif w is None:
            msg = "Berabere!"
        elif w == self.my_piece:
            msg, tone = ("Rakip oyunu terk etti - Kazandin!" if reason == 'forfeit' else "Kazandin!"), 'good'
        else:
            msg, tone = ("Hukmen kaybettin." if reason == 'forfeit' else "Kaybettin."), 'bad'
        if self.last_elo_change:
            sign = '+' if self.last_elo_change > 0 else ''
            msg += f"  ELO {sign}{self.last_elo_change} ({self.user_elo})"
        self.final_status, self.final_tone = msg, tone
        self.set_status(msg, tone)
        self.analysis_summary = self.get_analysis_summary()
        self.refresh_user_elo()

    def on_elo_update(self, data):
        self.user_elo = data.get('new_elo', self.user_elo)
        self.last_elo_change = data.get('change', 0)

    def on_opponent_disconnected(self, data):
        if self.connection_down:
            return  # Kopan biziz; soket kapanirken sunucunun oda duyurusu bize de ulasabilir
        if self.state == "PLAYING_ONLINE" and not self.game.game_over:
            grace = data.get('grace_seconds', config.RECONNECT_GRACE_SECONDS)
            self.opponent_deadline, self.opponent_remaining = time.time() + grace, grace
            self.set_status(f"Rakibin baglantisi koptu! {grace} sn icinde donmezse kazanirsin.", 'bad')
        elif self.is_spectator:
            self.set_status("Bir oyuncunun baglantisi koptu...", 'bad')

    def on_opponent_reconnected(self, data):
        self.opponent_deadline = None
        if self.state in ("PLAYING_ONLINE", "SPECTATING") and not self.game.game_over:
            turn = "Senin siran!" if self.game.current_player == self.my_piece else "Rakibin sirasi..."
            self.set_status("Rakip geri dondu. " + ("" if self.is_spectator else turn))

    def on_game_ended(self, data):
        if not self.game.game_over:
            self.room_closed = self.state == "PLAYING_ONLINE"
            self.opponent_deadline = None
            self.set_status("Oda zaman asimi nedeniyle kapatildi.", 'bad')

    def on_connection_lost(self, network=None):
        """Kendi soket baglantimiz beklenmedik sekilde koptu (istemci otomatik yeniden dener)."""
        if network is not None and network is not self.network:
            return  # Menuye donuste degistirilen eski baglanti
        if self.game.game_over:
            return
        if self.state == "PLAYING_ONLINE":
            self.connection_down, self.reconnect_warned = True, False
            self.connection_lost_at = time.time()
            self.opponent_deadline = None
            self.set_status("Baglanti koptu - yeniden baglaniliyor...", 'bad')
        elif self.state == "SPECTATING":
            self.set_status("Yayin baglantisi koptu. Lobiye donup tekrar izleyin.", 'bad')

    def update_connection_state(self):
        """Her karede: uzayan yeniden baglanmayi bildirir, rakibin kalan suresini sayar."""
        now = time.time()
        if (self.connection_down and not self.reconnect_warned
                and now - self.connection_lost_at > RECONNECT_WARN_SECONDS):
            # Kesin hukum degil: istemci denemeye devam edebilir, donus olursa mesaj silinir
            self.reconnect_warned = True
            self.set_status("Yeniden baglanma uzun suruyor. Bekleyebilir veya lobiye donebilirsiniz.", 'bad')
        if self.opponent_deadline is None:
            return
        if self.state != "PLAYING_ONLINE" or self.game.game_over:
            self.opponent_deadline = None
            return
        remaining = max(0, math.ceil(self.opponent_deadline - now))
        if remaining == self.opponent_remaining or self.connection_down or now < self.leave_confirm_until:
            return
        self.opponent_remaining = remaining
        if remaining:
            self.set_status(f"Rakibin baglantisi koptu! {remaining} sn icinde donmezse kazanirsin.", 'bad')
        else:
            self.set_status("Rakip geri donmedi, sonuc bekleniyor...")

    def on_server_error(self, data):
        msg = data.get('msg', '') if isinstance(data, dict) else str(data)
        if self.state == "PLAYING_ONLINE" and not self.game.game_over and msg in REJOIN_REFUSED_ERRORS:
            # Geri donus reddedildi: "yeniden baglaniliyor" durumunda takili kalma
            self._clear_connection_state()
            self.room_closed = True
            self.network.in_game = False
            self.set_status("Oyuna geri donulemedi: oda kapanmis. Lobiye donebilirsiniz.", 'bad')
            return
        self.set_status(f"Hata: {msg}", 'bad')
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
            # Sira oyuncudayken dolu sutun: tiklama sessizce yutulmaz
            if 0 <= col < COLS:
                self.set_status("Bu sutun dolu!", 'bad')
                self.sfx.play('invalid')
            return
        self.animate_drop(col, self.game.next_row(col), self.game.current_player, lambda: self.finish_move(col))

    def animate_drop(self, col, row, piece, callback):
        self.animating, self.anim_col, self.anim_piece = True, col, piece
        self.anim_y, self.anim_v = float(HOVER_Y), DROP_START_SPEED
        self.anim_target_y = BOARD_Y + (ROWS - 1 - row) * CELL_SIZE + CELL_SIZE // 2
        self.anim_callback = callback

    def update_animation(self):
        if not self.animating:
            return
        # Sabit adimli yercekimi (dt = 1/FPS). Duvar saati kullanilmaz: ekransiz testlerde
        # bir kare 1/60 sn'den cok kisa surer ve animasyon kare sayisiyla bitmelidir.
        dt = 1.0 / FPS
        self.anim_v += DROP_GRAVITY * dt
        self.anim_y += self.anim_v * dt
        if self.anim_y >= self.anim_target_y:
            self.finish_animation()

    def finish_animation(self, natural=True):
        """Tasi yerine oturtur ve hamle geri cagrisini calistirir.

        natural=False: animasyon yeni bir ag olayi yuzunden ileri sarildi (inis geri bildirimi yok).
        """
        if not self.animating:
            return
        self.anim_y, self.animating = self.anim_target_y, False
        if natural:
            self.sfx.play('drop')
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

    def _play_result_once(self, winner):
        """Sonuc sesi oyun basina bir kez (yerel bitis ve sunucu olayi iki sirayla da gelebilir)."""
        if self.result_sound_played:
            return
        self.result_sound_played = True
        if winner is None or self.is_spectator:
            self.sfx.play('draw')     # Seyirci icin taraf yok: notr ton
        else:
            self.sfx.play('win' if winner == self.human_piece() else 'lose')

    def handle_game_over(self):
        w = self.game.winner
        self._play_result_once(w)
        if self.final_status and self.state != "PLAYING_AI":
            # Sunucunun sonucu (ELO dahil) animasyon bitmeden geldiyse onu koru
            self.set_status(self.final_status, self.final_tone)
            return
        tone = 'neutral' if w is None or self.is_spectator else ('good' if w == self.human_piece() else 'bad')
        if self.state == "PLAYING_AI":
            self.set_status("Kazandin!" if w == PLAYER1_PIECE else ("AI kazandi!" if w == PLAYER2_PIECE else "Berabere!"),
                            tone)
        elif self.is_spectator:
            self.set_status("Kirmizi kazandi!" if w == PLAYER1_PIECE else ("Sari kazandi!" if w == PLAYER2_PIECE else "Berabere!"))
        else:
            self.set_status("Berabere!" if w is None else ("Kazandin!" if w == self.my_piece
                                                           else f"{self.opponent_name} kazandi!"), tone)

    def set_status(self, text, tone='neutral'):
        self.status_text, self.status_tone = text, tone

    def request_back(self):
        """Menu/Geri/Iptal. Aktif online oyundan cikis onay ister (hukmen yenilgi).

        Online ekranlardan (bekleme, oyun, izleme) gelindigi yere, lobiye donulur.
        """
        if self.state == "PLAYING_ONLINE" and not self.game.game_over and not self.room_closed:
            if time.time() > self.leave_confirm_until:
                self.leave_confirm_until = time.time() + LEAVE_CONFIRM_SECONDS
                self.set_status("Oyundan cikmak hukmen yenilgi sayilir. Onaylamak icin tekrar basin.", 'bad')
                return
        self.reset_to_menu(to_lobby=self.in_online_room())

    def reset_to_menu(self, to_lobby=False):
        left_room = self.room_id
        self.invalidate_ai_session()
        self._cancel_analysis()
        self.analysis_summary = None
        self.leave_confirm_until = 0.0
        self._clear_connection_state()
        if self.state in ("PLAYING_ONLINE", "WAITING"):
            self.network.leave_game()
        network, self.network = self.network, self._new_network()
        threading.Thread(target=network.disconnect, daemon=True).start()
        self.room_id, self.is_spectator = None, False
        self.animating = False
        self.game = ConnectFourGame()
        self.state = "MENU" if self.username else "LOGIN"
        self.set_status("")
        if to_lobby and self.username:
            self.state = "LOBBY"
            # Az once ayrilinan oda eski listede kalmasin; sunucu ayrilmayi islesin diye
            # ilk yenileme kisa bir sure sonra yapilir
            self.active_games = [g for g in self.active_games if g.get('room_id') != left_room]
            self.last_lobby_refresh = time.time() - (LOBBY_REFRESH_SECONDS - LOBBY_RETURN_DELAY)
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
            elif e.type == pygame.KEYDOWN:
                if self.state == "LOGIN":
                    self.handle_login_key(e)     # Giris ekraninda tuslar metin girisidir
                else:
                    self.handle_key(e)

    def handle_key(self, e):
        """Giris ekrani disindaki kisayollar: 1-7 hamle, Esc geri, M ses."""
        if e.key == pygame.K_ESCAPE:
            if self.state != "MENU":             # Ana menude Esc oyunu kapatmaz
                self.request_back()
        elif e.key == pygame.K_m:
            self.sfx.toggle_mute()
        elif e.key in COLUMN_KEYS and self.state in ("PLAYING_AI", "PLAYING_ONLINE"):
            self.handle_click(COLUMN_KEYS[e.key])  # Fare tiklamasiyla ayni kurallar

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
        elif e.unicode and e.unicode.isprintable() and len(field['value']) < field['max_len']:
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
            'MUTE': self.sfx.toggle_mute,
        }
        if bid != 'MUTE':
            self.sfx.play('click')
        if bid in actions:
            actions[bid]()
            if bid == 'MUTE' and not self.sfx.muted:
                self.sfx.play('click')    # Ses acildiginin duyulur onayi
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
        self.hovered_button = None
        getattr(self, self.SCREENS.get(self.state, 'draw_game'))()

    def tick(self):
        """Tek kare: olaylar, animasyon, AI, cizim."""
        self.process_events()
        self.handle_events()
        self.update_connection_state()
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
