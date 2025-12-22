# =============================================================================
# Connect Four Pro - Simplified GUI
# =============================================================================

import pygame
import sys
import threading
import socketio
import requests
import time
import os
import platform
from game_core import ConnectFourGame, ROWS, COLS, PLAYER1_PIECE, PLAYER2_PIECE
from ai_vs_human import AIEngine

# =============================================================================
# CONSTANTS & COLORS
# =============================================================================

SQUARESIZE = 90
PANEL_WIDTH = 280
WIDTH = COLS * SQUARESIZE + PANEL_WIDTH
HEIGHT = (ROWS + 1) * SQUARESIZE + 60
RADIUS = 38
SERVER_URL = 'http://localhost:5000'

# Colors
COLORS = {
    'bg': (15, 15, 25),
    'board': (25, 80, 180),
    'panel': (30, 30, 40),
    'text': (240, 240, 240),
    'text_dim': (150, 150, 160),
    'p1': (220, 50, 50),
    'p2': (255, 220, 0),
    'accent': (0, 200, 150),
    'success': (50, 200, 80),
    'warning': (255, 180, 0),
    'danger': (220, 60, 60),
}

# =============================================================================
# SIMPLE UI COMPONENTS
# =============================================================================

class Button:
    def __init__(self, x, y, w, h, text, color, font_size=22):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.font = pygame.font.SysFont("Segoe UI", font_size, bold=True)
        self.room_id = None

    def draw(self, screen, mouse_pos):
        hovered = self.rect.collidepoint(mouse_pos)
        color = tuple(min(255, c + 30) for c in self.color) if hovered else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, (60, 60, 70), self.rect, 2, border_radius=8)
        txt = self.font.render(self.text, True, COLORS['text'])
        screen.blit(txt, (self.rect.centerx - txt.get_width()//2, self.rect.centery - txt.get_height()//2))

    def clicked(self, pos):
        return self.rect.collidepoint(pos)


class InputBox:
    def __init__(self, x, y, w, h, placeholder='', is_password=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = ''
        self.placeholder = placeholder
        self.is_password = is_password
        self.active = False
        self.font = pygame.font.SysFont("Segoe UI", 24)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.unicode.isprintable():
                self.text += event.unicode

    def draw(self, screen):
        color = COLORS['accent'] if self.active else (60, 60, 70)
        pygame.draw.rect(screen, (35, 35, 45), self.rect, border_radius=6)
        pygame.draw.rect(screen, color, self.rect, 2, border_radius=6)
        display = '●' * len(self.text) if self.is_password and self.text else (self.text or self.placeholder)
        txt_color = COLORS['text'] if self.text else COLORS['text_dim']
        txt = self.font.render(display, True, txt_color)
        screen.blit(txt, (self.rect.x + 12, self.rect.centery - txt.get_height()//2))


# =============================================================================
# NETWORK CLIENT
# =============================================================================

class NetworkClient:
    def __init__(self, gui):
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=5)
        self.gui = gui
        self.connected = False
        self.user_data = None

        # Register all socket events
        for event, handler in [
            ('connect', lambda: self._set_status("Sunucuya bağlandı", connected=True)),
            ('disconnect', lambda: self._set_status("Bağlantı kesildi", connected=False)),
            ('game_created', self._on_game_created),
            ('game_joined', self._on_game_joined),
            ('game_start', self._on_game_start),
            ('move_made', self._on_move_made),
            ('game_over', lambda d: setattr(self.gui, 'state', 'GAME_OVER')),
            ('elo_update', self._on_elo_update),
            ('error', lambda d: self._set_status(f"Hata: {d.get('msg', '?')}")),
        ]:
            self.sio.on(event, handler)

    def _set_status(self, msg, connected=None):
        self.gui.status_message = msg
        if connected is not None:
            self.connected = connected

    def _on_game_created(self, data):
        self.gui.room_id = data['room_id']
        self.gui.my_piece = data['player_piece']
        self.gui.opponent_name = "Bekleniyor..."
        self.gui.start_game('PLAYING_ONLINE')

    def _on_game_joined(self, data):
        self.gui.room_id = data['room_id']
        self.gui.my_piece = data['player_piece']
        self.gui.is_spectator = data.get('role') == 'spectator'
        if self.gui.is_spectator and 'current_state' in data:
            self.gui.game.from_dict(data['current_state'])
        self.gui.start_game('PLAYING_ONLINE')

    def _on_game_start(self, data):
        self.gui.opponent_name = data.get('opponent_name', 'Rakip')
        self.gui.opponent_elo = data.get('opponent_elo', 1000)
        self.gui.status_message = "OYUN BAŞLADI!"

    def _on_move_made(self, data):
        col = data.get('col')
        current = data.get('current')
        mover = PLAYER1_PIECE if current == PLAYER2_PIECE else PLAYER2_PIECE
        if col is not None and (self.gui.is_spectator or mover != self.gui.my_piece):
            self.gui.pending_anim = (col, mover)
        self.gui.pending_state = data

    def _on_elo_update(self, data):
        if self.user_data:
            self.gui.elo_change = data.get('change', 0)
            self.user_data['rating'] = data.get('new_elo', self.user_data.get('rating', 1000))

    def login(self, username, password):
        try:
            r = requests.post(f"{SERVER_URL}/login", json={'username': username, 'password': password}, timeout=5)
            if r.status_code == 200:
                self.user_data = r.json()['user']
                return True
            self.gui.status_message = r.json().get('error', 'Giriş başarısız')
        except:
            self.gui.status_message = "Sunucuya bağlanılamıyor"
        return False

    def register(self, username, password):
        try:
            r = requests.post(f"{SERVER_URL}/signup", json={'username': username, 'password': password}, timeout=5)
            self.gui.status_message = "Kayıt başarılı!" if r.status_code == 201 else r.json().get('error', 'Kayıt başarısız')
        except:
            self.gui.status_message = "Sunucuya bağlanılamıyor"

    def connect_socket(self):
        if not self.connected:
            try:
                self.sio.connect(SERVER_URL)
            except:
                self.gui.status_message = "WebSocket bağlantı hatası"

    def get_data(self, endpoint):
        try:
            r = requests.get(f"{SERVER_URL}/{endpoint}", timeout=5)
            return r.json() if r.status_code == 200 else []
        except:
            return []

    def emit(self, event, data):
        self.sio.emit(event, data)

    def get_user_id(self):
        return self.user_data.get('user_id') or self.user_data.get('username') if self.user_data else None


# =============================================================================
# MAIN GUI CLASS
# =============================================================================

class GUI:
    def __init__(self):
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        pygame.init()
        pygame.display.set_caption("Connect 4 Pro")

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME)
        self.clock = pygame.time.Clock()
        self.fonts = {
            'title': pygame.font.SysFont("Segoe UI", 42, bold=True),
            'big': pygame.font.SysFont("Segoe UI", 32, bold=True),
            'med': pygame.font.SysFont("Segoe UI", 24),
            'small': pygame.font.SysFont("Segoe UI", 18),
        }

        # Window dragging
        self.dragging = False
        self.drag_start_pos = (0, 0)
        self.is_windows = platform.system() == 'Windows'

        self.network = NetworkClient(self)
        self.game = ConnectFourGame()
        self.state = "LOGIN"
        self.status_message = "Sunucuya bağlanın"

        # Game state
        self.room_id = None
        self.my_piece = None
        self.opponent_name = ""
        self.opponent_elo = 1000
        self.is_spectator = False
        self.elo_change = 0
        self.pending_anim = None
        self.pending_state = None

        # AI
        self.ai = None
        self.ai_thinking = False
        self.ai_depth = 4
        self.ai_result = None

        self._init_ui()

    def _init_ui(self):
        cx = WIDTH // 2
        # Login
        self.input_user = InputBox(cx-150, 220, 300, 50, "Kullanıcı adı")
        self.input_pass = InputBox(cx-150, 290, 300, 50, "Şifre", is_password=True)
        self.btn_login = Button(cx-150, 360, 140, 50, "GİRİŞ", COLORS['success'])
        self.btn_register = Button(cx+10, 360, 140, 50, "KAYIT", COLORS['accent'])

        # Menu
        self.btn_ai = Button(cx-180, 220, 360, 60, "YEREL: VS AI", COLORS['warning'])
        self.btn_online = Button(cx-180, 300, 360, 60, "ONLİNE LOBBY", COLORS['success'])
        self.btn_leader = Button(cx-180, 380, 360, 60, "LİDERLİK TABLOSU", COLORS['accent'])

        # AI difficulty
        self.btn_easy = Button(cx-180, 220, 360, 60, "KOLAY (Depth 2)", COLORS['success'])
        self.btn_medium = Button(cx-180, 300, 360, 60, "ORTA (Depth 4)", COLORS['warning'])
        self.btn_hard = Button(cx-180, 380, 360, 60, "ZOR (Depth 6)", COLORS['danger'])

        # Lobby
        self.btn_create = Button(50, 100, 200, 50, "YENİ OYUN", COLORS['accent'])
        self.btn_refresh = Button(WIDTH-170, 100, 120, 50, "YENİLE", COLORS['warning'])
        self.room_buttons = []

        # Common
        self.btn_back = Button(20, 20, 100, 40, "< GERİ", (60, 60, 70), 18)
        self.btn_menu = Button(cx-100, 400, 200, 50, "ANA MENÜ", COLORS['accent'])

    def start_game(self, mode, depth=4):
        self.game = ConnectFourGame()
        self.state = mode
        if mode != 'PLAYING_ONLINE':
            self.is_spectator = False
        if mode == 'PLAYING_AI':
            self.ai_depth = depth
            self.ai = AIEngine(PLAYER2_PIECE, depth)
            self.ai_thinking = False
            self.status_message = f"AI Zorluk: Depth {depth}"
        self._update_title()

    def _update_title(self):
        name = self.network.user_data.get('username', 'Player') if self.network.user_data else 'Player'
        if self.state == 'PLAYING_ONLINE':
            opp = self.opponent_name or "Waiting..."
            mode = " [SPECTATOR]" if self.is_spectator else ""
            pygame.display.set_caption(f"Connect 4 Pro - {name} vs {opp}{mode}")
        elif self.state == 'PLAYING_AI':
            pygame.display.set_caption(f"Connect 4 Pro - {name} vs AI (D{self.ai_depth})")
        else:
            pygame.display.set_caption("Connect 4 Pro")

    def run_ai(self):
        self.ai_thinking = True
        self.status_message = "AI düşünüyor..."
        def think():
            time.sleep(0.3)
            self.ai_result = self.ai.find_best_move(self.game)
            self.ai_thinking = False
        threading.Thread(target=think, daemon=True).start()

    def animate_drop(self, col, piece):
        color = COLORS['p1'] if piece == PLAYER1_PIECE else COLORS['p2']
        row = self.game.heights[col] % (ROWS + 1)
        y_target = (HEIGHT - 60) - int(row * SQUARESIZE + SQUARESIZE // 2)
        y, velocity = SQUARESIZE // 2, 0

        while y < y_target:
            velocity += 2
            y = min(y + velocity, y_target)
            self._draw_board()
            cx = int(col * SQUARESIZE + SQUARESIZE // 2)
            pygame.draw.circle(self.screen, color, (cx, int(y)), RADIUS)
            pygame.display.flip()
            pygame.time.wait(5)

    def _draw_board(self):
        self.screen.fill(COLORS['bg'])

        # Top bar
        pygame.draw.rect(self.screen, (25, 25, 35), (0, 0, COLS*SQUARESIZE, SQUARESIZE))
        self.btn_back.draw(self.screen, pygame.mouse.get_pos())
        txt = self.fonts['small'].render(self.status_message, True, COLORS['warning'] if "düşünüyor" in self.status_message else COLORS['text'])
        self.screen.blit(txt, (130, 25))

        # Board
        pygame.draw.rect(self.screen, COLORS['board'], (0, SQUARESIZE, COLS*SQUARESIZE, ROWS*SQUARESIZE), border_radius=10)

        for c in range(COLS):
            for r in range(ROWS):
                cx = int(c * SQUARESIZE + SQUARESIZE // 2)
                cy = int((r + 1) * SQUARESIZE + SQUARESIZE // 2)
                pygame.draw.circle(self.screen, COLORS['bg'], (cx, cy), RADIUS)

                log_r = ROWS - 1 - r
                mask = 1 << (c * (ROWS + 1) + log_r)
                if self.game.bitboards[PLAYER1_PIECE] & mask:
                    pygame.draw.circle(self.screen, COLORS['p1'], (cx, cy), RADIUS)
                elif self.game.bitboards[PLAYER2_PIECE] & mask:
                    pygame.draw.circle(self.screen, COLORS['p2'], (cx, cy), RADIUS)

        # Winning highlight
        if self.game.winning_mask:
            for c in range(COLS):
                for r in range(ROWS):
                    if self.game.winning_mask & (1 << (c * (ROWS + 1) + r)):
                        cx = int(c * SQUARESIZE + SQUARESIZE // 2)
                        cy = HEIGHT - 60 - int(r * SQUARESIZE + SQUARESIZE // 2)
                        pygame.draw.circle(self.screen, COLORS['text'], (cx, cy), RADIUS + 5, 4)

        # Side panel
        self._draw_panel()

        # Bottom bar
        pygame.draw.rect(self.screen, (25, 25, 35), (0, HEIGHT-60, WIDTH, 60))
        if self.network.user_data:
            info = f"User: {self.network.user_data.get('username', '?')} | ELO: {self.network.user_data.get('rating', 1000)}"
            txt = self.fonts['small'].render(info, True, COLORS['text'])
            self.screen.blit(txt, (WIDTH - txt.get_width() - 20, HEIGHT - 40))

    def _draw_panel(self):
        px = COLS * SQUARESIZE + 15
        pw = PANEL_WIDTH - 30

        # Players panel
        pygame.draw.rect(self.screen, COLORS['panel'], (px, 10, pw, 250), border_radius=10)

        if self.state == 'PLAYING_ONLINE':
            p1 = self.network.user_data.get('username', 'P1') if self.my_piece == PLAYER1_PIECE else self.opponent_name
            p2 = self.opponent_name if self.my_piece == PLAYER1_PIECE else self.network.user_data.get('username', 'P2')
        else:
            p1 = self.network.user_data.get('username', 'Oyuncu') if self.network.user_data else 'Oyuncu'
            p2 = f"AI (D{self.ai_depth})"

        y = 30
        for i, (name, color, label) in enumerate([(p1, COLORS['p1'], 'KIRMIZI'), (p2, COLORS['p2'], 'SARI')]):
            piece = PLAYER1_PIECE if i == 0 else PLAYER2_PIECE
            is_turn = self.game.current_player == piece

            # Card background
            card_color = tuple(max(0, c - (100 if not is_turn else 80)) for c in color)
            pygame.draw.rect(self.screen, card_color, (px+10, y, pw-20, 70), border_radius=8)
            if is_turn:
                pygame.draw.rect(self.screen, color, (px+10, y, pw-20, 70), 3, border_radius=8)

            pygame.draw.circle(self.screen, color, (px + 35, y + 35), 15)
            self.screen.blit(self.fonts['med'].render(name[:12], True, COLORS['text']), (px + 60, y + 10))
            self.screen.blit(self.fonts['small'].render(label, True, color), (px + 60, y + 38))
            if is_turn:
                self.screen.blit(self.fonts['small'].render("SIRA", True, COLORS['warning']), (px + pw - 55, y + 38))
            y += 100

        # Move history
        pygame.draw.rect(self.screen, COLORS['panel'], (px, 270, pw, HEIGHT - 340), border_radius=8)
        self.screen.blit(self.fonts['small'].render("HAMLELER", True, COLORS['text_dim']), (px + 10, 278))

        y = 305
        for i, col in enumerate(self.game.move_history[-10:]):
            color = COLORS['p1'] if (len(self.game.move_history) - 10 + i) % 2 == 0 else COLORS['p2']
            txt = self.fonts['small'].render(f"{len(self.game.move_history)-9+i}. Sütun {col+1}", True, color)
            self.screen.blit(txt, (px + 10, y))
            y += 22

    def _draw_game_over(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        if self.game.winner == PLAYER1_PIECE:
            result, color = "KIRMIZI KAZANDI!", COLORS['p1']
        elif self.game.winner == PLAYER2_PIECE:
            result, color = "SARI KAZANDI!", COLORS['p2']
        else:
            result, color = "BERABERE!", COLORS['text']

        txt = self.fonts['title'].render(result, True, color)
        self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, 180))

        if self.elo_change:
            elo_color = COLORS['success'] if self.elo_change > 0 else COLORS['danger']
            txt = self.fonts['med'].render(f"ELO: {'+' if self.elo_change > 0 else ''}{self.elo_change}", True, elo_color)
            self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, 250))

        self.btn_menu.draw(self.screen, pygame.mouse.get_pos())

    def run(self):
        while True:
            mouse = pygame.mouse.get_pos()
            events = pygame.event.get()

            for e in events:
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    # Check if clicking on draggable area (top bar)
                    if e.pos[1] < SQUARESIZE and e.pos[0] < COLS * SQUARESIZE:
                        self.dragging = True
                        self.drag_start_pos = e.pos
                elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                    self.dragging = False

            if self.dragging and self.is_windows:
                try:
                    import ctypes
                    import ctypes.wintypes
                    # Get current mouse position
                    point = ctypes.wintypes.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
                    # Move window
                    hwnd = pygame.display.get_wm_info()['window']
                    ctypes.windll.user32.SetWindowPos(
                        hwnd, 0,
                        point.x - self.drag_start_pos[0],
                        point.y - self.drag_start_pos[1],
                        0, 0, 0x0001 | 0x0004
                    )
                except Exception:
                    pass

            # Route to state handler
            handler = getattr(self, f'_handle_{self.state.lower()}', None)
            if handler:
                handler(events, mouse)

            pygame.display.flip()
            self.clock.tick(60)

    def _handle_login(self, events, mouse):
        self.screen.fill(COLORS['bg'])

        txt = self.fonts['title'].render("CONNECT 4 PRO", True, COLORS['accent'])
        self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, 100))

        self.input_user.draw(self.screen)
        self.input_pass.draw(self.screen)
        self.btn_login.draw(self.screen, mouse)
        self.btn_register.draw(self.screen, mouse)

        txt = self.fonts['small'].render(self.status_message, True, COLORS['danger'] if "Hata" in self.status_message else COLORS['text'])
        self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, 430))

        for e in events:
            self.input_user.handle_event(e)
            self.input_pass.handle_event(e)
            if e.type == pygame.MOUSEBUTTONDOWN:
                if self.btn_login.clicked(e.pos):
                    if self.network.login(self.input_user.text, self.input_pass.text):
                        self.network.connect_socket()
                        self.state = "MENU"
                elif self.btn_register.clicked(e.pos):
                    self.network.register(self.input_user.text, self.input_pass.text)

    def _handle_menu(self, events, mouse):
        self.screen.fill(COLORS['bg'])

        txt = self.fonts['big'].render("ANA MENÜ", True, COLORS['text'])
        self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, 120))

        for btn in [self.btn_ai, self.btn_online, self.btn_leader]:
            btn.draw(self.screen, mouse)

        if self.network.user_data:
            info = f"Hoşgeldin, {self.network.user_data.get('username', '?')}! | ELO: {self.network.user_data.get('rating', 1000)}"
            txt = self.fonts['med'].render(info, True, COLORS['success'])
            self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, HEIGHT - 80))

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                if self.btn_ai.clicked(e.pos): self.state = "AI_SELECT"
                elif self.btn_online.clicked(e.pos):
                    self._refresh_lobby()
                    self.state = "LOBBY"
                elif self.btn_leader.clicked(e.pos): self.state = "LEADERBOARD"

    def _handle_ai_select(self, events, mouse):
        self.screen.fill(COLORS['bg'])
        self.btn_back.draw(self.screen, mouse)

        txt = self.fonts['big'].render("ZORLUK SEÇİN", True, COLORS['text'])
        self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, 120))

        for btn in [self.btn_easy, self.btn_medium, self.btn_hard]:
            btn.draw(self.screen, mouse)

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                if self.btn_back.clicked(e.pos): self.state = "MENU"
                elif self.btn_easy.clicked(e.pos): self.start_game('PLAYING_AI', 2)
                elif self.btn_medium.clicked(e.pos): self.start_game('PLAYING_AI', 4)
                elif self.btn_hard.clicked(e.pos): self.start_game('PLAYING_AI', 6)

    def _refresh_lobby(self):
        games = self.network.get_data('active_games')
        self.room_buttons = []
        y = 180
        for game in games[:6]:
            is_waiting = 'WAITING' in game.get('status', '')
            color = COLORS['success'] if is_waiting else COLORS['accent']
            action = "KATIL" if is_waiting else "İZLE"
            text = f"[{game['room_id']}] {game['p1']} vs {game.get('p2', '...')} - {action}"
            btn = Button(50, y, WIDTH-100, 45, text, color, 18)
            btn.room_id = game['room_id']
            self.room_buttons.append(btn)
            y += 55

    def _handle_lobby(self, events, mouse):
        self.screen.fill(COLORS['bg'])
        self.btn_back.draw(self.screen, mouse)

        txt = self.fonts['big'].render("ONLİNE LOBİ", True, COLORS['text'])
        self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, 30))

        self.btn_create.draw(self.screen, mouse)
        self.btn_refresh.draw(self.screen, mouse)

        if not self.room_buttons:
            txt = self.fonts['med'].render("Aktif oyun yok. Yeni oluşturun!", True, COLORS['text_dim'])
            self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, 250))
        else:
            for btn in self.room_buttons:
                btn.draw(self.screen, mouse)

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                if self.btn_back.clicked(e.pos): self.state = "MENU"
                elif self.btn_create.clicked(e.pos):
                    self.network.emit('create_game', {'user_id': self.network.get_user_id()})
                elif self.btn_refresh.clicked(e.pos):
                    self._refresh_lobby()
                else:
                    for btn in self.room_buttons:
                        if btn.clicked(e.pos):
                            self.network.emit('join_game', {'room_id': btn.room_id, 'user_id': self.network.get_user_id()})

    def _handle_leaderboard(self, events, mouse):
        self.screen.fill(COLORS['bg'])
        self.btn_back.draw(self.screen, mouse)

        txt = self.fonts['big'].render("LİDERLİK TABLOSU", True, COLORS['warning'])
        self.screen.blit(txt, (WIDTH//2 - txt.get_width()//2, 60))

        data = self.network.get_data('leaderboard')
        y = 140
        for i, p in enumerate(data[:10]):
            color = [(255,215,0), (192,192,192), (205,127,50)][i] if i < 3 else COLORS['text']
            txt = self.fonts['med'].render(f"#{i+1}  {p['username'][:15]}  -  ELO: {p['rating']}  -  Wins: {p['wins']}", True, color)
            self.screen.blit(txt, (80, y))
            y += 40

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and self.btn_back.clicked(e.pos):
                self.state = "MENU"

    def _handle_playing_online(self, events, mouse):
        # Process pending updates from socket thread
        if self.pending_anim:
            col, piece = self.pending_anim
            self.pending_anim = None
            self.animate_drop(col, piece)
        if self.pending_state:
            self.game.from_dict(self.pending_state)
            self.pending_state = None

        self._draw_board()

        if self.game.game_over:
            self.state = "GAME_OVER"
            return

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                if self.btn_back.clicked(e.pos):
                    self.state = "MENU"
                elif not self.is_spectator and e.pos[0] < COLS * SQUARESIZE:
                    col = e.pos[0] // SQUARESIZE
                    if self.game.is_valid_location(col) and self.game.current_player == self.my_piece:
                        self.network.emit('make_move', {'room_id': self.room_id, 'col': col, 'player_piece': self.my_piece})

    def _handle_playing_ai(self, events, mouse):
        # Process AI move
        if self.ai_result is not None:
            self.animate_drop(self.ai_result, PLAYER2_PIECE)
            self.game.make_move(self.ai_result)
            self.ai_result = None
            self.status_message = "Senin sıran!"

        self._draw_board()

        if self.game.game_over:
            self.state = "GAME_OVER"
            return

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                if self.btn_back.clicked(e.pos):
                    self.state = "MENU"
                elif e.pos[0] < COLS * SQUARESIZE and not self.ai_thinking:
                    col = e.pos[0] // SQUARESIZE
                    if self.game.is_valid_location(col) and self.game.current_player == PLAYER1_PIECE:
                        self.animate_drop(col, PLAYER1_PIECE)
                        self.game.make_move(col)
                        if not self.game.game_over:
                            self.run_ai()

    def _handle_game_over(self, events, mouse):
        self._draw_board()
        self._draw_game_over()

        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and self.btn_menu.clicked(e.pos):
                self.elo_change = 0
                self.state = "MENU"


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        SERVER_URL = sys.argv[1]
    GUI().run()
