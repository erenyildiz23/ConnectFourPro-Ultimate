# =============================================================================
# MODULE: gui_app.py
# Connect Four Pro - Pygame GUI Client v5.0
# Features: Login/Register, Online Lobby, Spectate, COMPLETELY FIXED AI
# Debug: Extensive logging to find AI interference bug
# =============================================================================

import os
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
import sys
import threading
import time
import requests
import socketio

from game_core import ConnectFourGame, ROWS, COLS, PLAYER1_PIECE, PLAYER2_PIECE
from ai_vs_human import AIEngine

# =============================================================================
# DEBUG FLAG - Set to False to disable console logs
# =============================================================================
DEBUG = True

def log(msg):
    if DEBUG:
        print(f"[GUI] {msg}")

# =============================================================================
# CONFIGURATION
# =============================================================================

CELL_SIZE = 80
BOARD_WIDTH = COLS * CELL_SIZE
BOARD_HEIGHT = ROWS * CELL_SIZE
WINDOW_WIDTH = BOARD_WIDTH + 320
WINDOW_HEIGHT = BOARD_HEIGHT + 150

SERVER_URL = 'http://localhost:5000'

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
    'button_hover': (255, 107, 107),
    'waiting': (230, 126, 34),
    'playing': (46, 204, 113),
    'input_bg': (44, 62, 80),
    'input_active': (52, 152, 219),
    'win_highlight': (0, 255, 128),  # Winning pieces glow
}

AI_DEPTHS = {'Kolay': 2, 'Orta': 4, 'Zor': 6}

# =============================================================================
# NETWORK MANAGER
# =============================================================================

class NetworkManager:
    def __init__(self, gui):
        self.gui = gui
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=5)
        self.connected = False
        self.room_id = None
        self.my_piece = None
        self._setup_events()
    
    def _setup_events(self):
        @self.sio.event
        def connect():
            self.connected = True
            log("Network connected")
        
        @self.sio.event
        def disconnect():
            self.connected = False
            log("Network disconnected")
        
        @self.sio.on('game_created')
        def on_game_created(data):
            log(f"Game created: {data.get('room_id')}")
            self.room_id = data['room_id']
            self.my_piece = data['player_piece']
            self.gui.on_game_created(data)
        
        @self.sio.on('game_joined')
        def on_game_joined(data):
            log(f"Game joined: {data.get('room_id')}, role={data.get('role')}")
            self.room_id = data['room_id']
            self.my_piece = data['player_piece']
            self.gui.on_game_joined(data)
        
        @self.sio.on('game_start')
        def on_game_start(data):
            log("Game start received!")
            self.gui.on_game_start(data)
        
        @self.sio.on('move_made')
        def on_move_made(data):
            log(f"Move received: col={data.get('col')}")
            self.gui.on_move_made(data)
        
        @self.sio.on('game_over')
        def on_game_over(data):
            log(f"Game over: winner={data.get('winner')}")
            self.gui.on_game_over_network(data)
        
        @self.sio.on('elo_update')
        def on_elo_update(data):
            log(f"ELO update: {data}")
            self.gui.on_elo_update(data)
        
        @self.sio.on('opponent_disconnected')
        def on_opponent_disconnected(data):
            log("Opponent disconnected")
            self.gui.on_opponent_disconnected()
        
        @self.sio.on('error')
        def on_error(data):
            log(f"Server error: {data}")
            self.gui.set_status(f"Hata: {data.get('msg', '')}")
    
    def connect_to_server(self):
        if self.connected:
            return True
        try:
            self.sio.connect(SERVER_URL, wait_timeout=5)
            time.sleep(0.5)
            return self.connected
        except Exception as e:
            log(f"Connection failed: {e}")
            return False
    
    def create_game(self, user_id):
        if self.connect_to_server():
            self.sio.emit('create_game', {'user_id': user_id})
            return True
        return False
    
    def join_game(self, room_id, user_id):
        if self.connect_to_server():
            self.sio.emit('join_game', {'room_id': room_id, 'user_id': user_id})
            return True
        return False
    
    def send_move(self, col):
        if self.connected and self.room_id:
            log(f"Sending move: col={col}")
            self.sio.emit('make_move', {'room_id': self.room_id, 'col': col, 'player_piece': self.my_piece})
    
    def disconnect(self):
        if self.connected:
            try:
                self.sio.disconnect()
            except:
                pass
        self.room_id = None
        self.my_piece = None

# =============================================================================
# MAIN GUI CLASS
# =============================================================================

class ConnectFourGUI:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Connect Four Pro")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.SysFont('segoeui', 36, bold=True)
        self.font_medium = pygame.font.SysFont('segoeui', 24)
        self.font_small = pygame.font.SysFont('segoeui', 18)
        self.font_tiny = pygame.font.SysFont('segoeui', 14)
        
        self.state = "LOGIN"
        self.game = ConnectFourGame()
        self.ai = None
        self.ai_thinking = False
        self.is_spectator = False
        
        # AI SESSION MANAGEMENT - Key to preventing stale moves
        self.ai_session_id = 0
        self.ai_lock = threading.Lock()  # Thread safety
        
        self.username = ""
        self.user_id = None
        self.user_elo = 1200
        self.opponent_name = "Rakip"
        self.opponent_elo = 1200
        self.is_guest = False
        
        self.network = NetworkManager(self)
        self.my_piece = PLAYER1_PIECE
        self.room_id = None
        
        self.active_games = []
        self.last_lobby_refresh = 0
        self.status_text = ""
        self.hover_col = -1
        self.buttons = []
        
        self.input_fields = {
            'username': {'value': '', 'active': False, 'rect': None},
            'password': {'value': '', 'active': False, 'rect': None}
        }
        self.active_input = None
        
        self.animating = False
        self.anim_col = 0
        self.anim_y = 0
        self.anim_target_y = 0
        self.anim_piece = PLAYER1_PIECE
        self.anim_callback = None
        
        # Pending AI move with session check
        self.pending_ai_move = None
        self.pending_ai_session = -1
        
        # Background Analysis (Lichess-style) - runs silently during online games
        self.analysis_enabled = True  # Enable/disable analysis
        self.analysis_data = []       # List of {move_num, player, col, best_move, eval_score}
        self.analysis_thread = None
        self.analysis_lock = threading.Lock()
        
        log("GUI initialized")
    
    # =========================================================================
    # DRAWING
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
        pygame.draw.rect(self.screen, color, (x, y, w, h), border_radius=8)
        self.draw_text(text, self.font_small, COLORS['white'], x + w//2, y + h//2)
        return pygame.Rect(x, y, w, h)
    
    def draw_input_field(self, label, field_name, x, y, w, h, is_password=False):
        field = self.input_fields[field_name]
        self.draw_text(label, self.font_small, COLORS['gray'], x + w//2, y - 15)
        color = COLORS['input_active'] if field['active'] else COLORS['input_bg']
        pygame.draw.rect(self.screen, color, (x, y, w, h), border_radius=6)
        pygame.draw.rect(self.screen, COLORS['white'], (x, y, w, h), 2, border_radius=6)
        display_text = '*' * len(field['value']) if is_password else (field['value'] or "...")
        self.draw_text(display_text, self.font_medium, COLORS['white'], x + w//2, y + h//2)
        field['rect'] = pygame.Rect(x, y, w, h)
    
    def get_winning_positions(self):
        """Get list of (col, row) tuples for winning pieces"""
        if not self.game.game_over or self.game.winner is None:
            return []
        
        positions = []
        mask = self.game.winning_mask
        if mask == 0:
            return []
        
        for col in range(COLS):
            for row in range(ROWS):
                idx = col * (ROWS + 1) + row
                if (mask >> idx) & 1:
                    positions.append((col, row))
        return positions
    
    def draw_board(self):
        bx, by = 20, 80
        pygame.draw.rect(self.screen, COLORS['board'], (bx-10, by-10, BOARD_WIDTH+20, BOARD_HEIGHT+20), border_radius=10)
        
        # Get winning positions for highlight
        winning_positions = self.get_winning_positions()
        
        for col in range(COLS):
            for row in range(ROWS):
                x = bx + col * CELL_SIZE + CELL_SIZE // 2
                y = by + (ROWS - 1 - row) * CELL_SIZE + CELL_SIZE // 2
                
                # Check if this is a winning position
                is_winning = (col, row) in winning_positions
                
                # Cell background (with glow effect for winners)
                if is_winning:
                    # Pulsing glow effect
                    pulse = abs((time.time() * 3) % 2 - 1)  # 0 to 1 oscillation
                    glow_size = int(CELL_SIZE // 2 + 5 + pulse * 5)
                    pygame.draw.circle(self.screen, COLORS['win_highlight'], (x, y), glow_size)
                
                pygame.draw.circle(self.screen, COLORS['cell_bg'], (x, y), CELL_SIZE // 2 - 5)
                
                # Pieces
                idx = col * (ROWS + 1) + row
                if (self.game.bitboards[PLAYER1_PIECE] >> idx) & 1:
                    pygame.draw.circle(self.screen, COLORS['red'], (x, y), CELL_SIZE // 2 - 8)
                    if is_winning:
                        pygame.draw.circle(self.screen, COLORS['white'], (x, y), CELL_SIZE // 2 - 8, 3)
                elif (self.game.bitboards[PLAYER2_PIECE] >> idx) & 1:
                    pygame.draw.circle(self.screen, COLORS['yellow'], (x, y), CELL_SIZE // 2 - 8)
                    if is_winning:
                        pygame.draw.circle(self.screen, COLORS['white'], (x, y), CELL_SIZE // 2 - 8, 3)
        
        # Hover indicator
        if self.hover_col >= 0 and not self.animating and not self.game.game_over and not self.is_spectator:
            can_play = (self.state == "PLAYING_AI" and self.game.current_player == PLAYER1_PIECE and not self.ai_thinking) or \
                       (self.state == "PLAYING_ONLINE" and self.game.current_player == self.my_piece)
            if can_play:
                pygame.draw.circle(self.screen, COLORS['hover'], (bx + self.hover_col * CELL_SIZE + CELL_SIZE//2, 50), CELL_SIZE//2 - 10)
        
        # Animating piece
        if self.animating:
            color = COLORS['red'] if self.anim_piece == PLAYER1_PIECE else COLORS['yellow']
            pygame.draw.circle(self.screen, color, (bx + self.anim_col * CELL_SIZE + CELL_SIZE//2, int(self.anim_y)), CELL_SIZE//2 - 8)
    
    def draw_info_panel(self):
        px, py = BOARD_WIDTH + 50, 80
        pygame.draw.rect(self.screen, COLORS['panel'], (px, py, 250, 320), border_radius=10)
        title = "IZLIYORSUNUZ" if self.is_spectator else "OYUN BILGISI"
        self.draw_text(title, self.font_medium, COLORS['waiting'] if self.is_spectator else COLORS['white'], px+125, py+25)
        
        pygame.draw.circle(self.screen, COLORS['red'], (px+25, py+70), 15)
        p1_name = self.username if (self.state == "PLAYING_AI" or self.my_piece == PLAYER1_PIECE) else self.opponent_name
        p1_elo = self.user_elo if (self.state == "PLAYING_AI" or self.my_piece == PLAYER1_PIECE) else self.opponent_elo
        self.draw_text(p1_name[:10], self.font_small, COLORS['white'], px+50, py+65, center=False)
        self.draw_text(f"ELO: {p1_elo}", self.font_tiny, COLORS['gray'], px+50, py+85, center=False)
        if self.game.current_player == PLAYER1_PIECE and not self.game.game_over:
            self.draw_text("< SIRA", self.font_small, COLORS['green'], px+200, py+70)
        
        pygame.draw.circle(self.screen, COLORS['yellow'], (px+25, py+130), 15)
        if self.state == "PLAYING_AI":
            p2_name = f"AI (D{self.ai.depth if self.ai else '?'})"
        else:
            p2_name = self.username if self.my_piece == PLAYER2_PIECE else self.opponent_name
        p2_elo = self.user_elo if self.my_piece == PLAYER2_PIECE else self.opponent_elo
        self.draw_text(p2_name[:10], self.font_small, COLORS['white'], px+50, py+125, center=False)
        if self.state != "PLAYING_AI":
            self.draw_text(f"ELO: {p2_elo}", self.font_tiny, COLORS['gray'], px+50, py+145, center=False)
        if self.game.current_player == PLAYER2_PIECE and not self.game.game_over:
            self.draw_text("< SIRA", self.font_small, COLORS['green'], px+200, py+130)
        
        if self.room_id:
            self.draw_text(f"Oda: {self.room_id}", self.font_medium, COLORS['hover'], px+125, py+200)
        self.draw_text(f"Hamle: {len(self.game.move_history)}", self.font_small, COLORS['gray'], px+125, py+240)
        
        # Debug info
        if DEBUG:
            self.draw_text(f"State: {self.state}", self.font_tiny, COLORS['gray'], px+125, py+280)
            self.draw_text(f"AI: {'ON' if self.ai else 'OFF'}", self.font_tiny, COLORS['gray'], px+125, py+295)
        
        return self.draw_button("Menu", px+50, py+270 if not DEBUG else py+310, 150, 40)
    
    # =========================================================================
    # SCREENS
    # =========================================================================
    
    def draw_login(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("CONNECT FOUR PRO", self.font_large, COLORS['red'], WINDOW_WIDTH//2, 60)
        self.draw_text("Hosgeldiniz!", self.font_medium, COLORS['white'], WINDOW_WIDTH//2, 110)
        cx, fw, fh = WINDOW_WIDTH//2, 280, 45
        self.draw_input_field("Kullanici Adi", 'username', cx-fw//2, 170, fw, fh)
        self.draw_input_field("Sifre", 'password', cx-fw//2, 260, fw, fh, is_password=True)
        self.buttons = []
        self.buttons.append(('DO_LOGIN', self.draw_button("Giris Yap", cx-140, 340, 130, 45)))
        self.buttons.append(('DO_REGISTER', self.draw_button("Kayit Ol", cx+10, 340, 130, 45, COLORS['green'])))
        pygame.draw.line(self.screen, COLORS['gray'], (cx-100, 420), (cx+100, 420), 1)
        self.draw_text("veya", self.font_tiny, COLORS['gray'], cx, 420)
        self.buttons.append(('GUEST', self.draw_button("Misafir Olarak Devam", cx-120, 450, 240, 45, COLORS['panel'])))
        if self.status_text:
            color = COLORS['green'] if 'basarili' in self.status_text.lower() else COLORS['red']
            self.draw_text(self.status_text, self.font_small, color, WINDOW_WIDTH//2, WINDOW_HEIGHT-40)
    
    def draw_menu(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("CONNECT FOUR PRO", self.font_large, COLORS['red'], WINDOW_WIDTH//2, 50)
        if self.is_guest:
            self.draw_text(f"Misafir: {self.username}", self.font_small, COLORS['gray'], WINDOW_WIDTH//2, 95)
        else:
            self.draw_text(self.username, self.font_medium, COLORS['white'], WINDOW_WIDTH//2, 90)
            self.draw_text(f"ELO: {self.user_elo}", self.font_small, COLORS['green'], WINDOW_WIDTH//2, 115)
        bw, bh, cx = 250, 50, WINDOW_WIDTH//2 - 125
        self.buttons = [
            ('AI', self.draw_button("Yapay Zekaya Karsi", cx, 160, bw, bh)),
            ('LOBBY', self.draw_button("Online Lobi", cx, 225, bw, bh)),
            ('LEADERBOARD', self.draw_button("Liderlik Tablosu", cx, 290, bw, bh)),
            ('LOGOUT', self.draw_button("Cikis Yap", cx, 355, bw, bh, COLORS['panel'])),
            ('QUIT', self.draw_button("Oyunu Kapat", cx, 420, bw, bh, COLORS['gray']))
        ]
        if self.status_text:
            self.draw_text(self.status_text, self.font_small, COLORS['gray'], WINDOW_WIDTH//2, WINDOW_HEIGHT-30)
    
    def draw_ai_select(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("ZORLUK SEVIYESI SEC", self.font_large, COLORS['red'], WINDOW_WIDTH//2, 80)
        bw, bh, cx = 200, 50, WINDOW_WIDTH//2 - 100
        self.buttons = []
        y = 180
        for name, depth in AI_DEPTHS.items():
            self.buttons.append((f'AI_{depth}', self.draw_button(f"{name} (D{depth})", cx, y, bw, bh)))
            y += 70
        self.buttons.append(('BACK', self.draw_button("Geri", cx, y+30, bw, bh)))
    
    def draw_lobby(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("ONLINE LOBI", self.font_large, COLORS['red'], WINDOW_WIDTH//2, 40)
        if time.time() - self.last_lobby_refresh > 2:
            self.refresh_active_games()
            self.last_lobby_refresh = time.time()
        self.buttons = [
            ('CREATE', self.draw_button("+ Yeni Oyun", 50, 80, 160, 45)),
            ('REFRESH', self.draw_button("Yenile", 230, 80, 100, 45)),
            ('BACK', self.draw_button("Geri", WINDOW_WIDTH-150, 80, 100, 45))
        ]
        pygame.draw.rect(self.screen, COLORS['panel'], (30, 140, WINDOW_WIDTH-60, 35), border_radius=5)
        for txt, xpos in [("ODA",80),("OYUNCU 1",200),("OYUNCU 2",380),("DURUM",530),("ISLEM",680)]:
            self.draw_text(txt, self.font_small, COLORS['white'], xpos, 157)
        y = 185
        if not self.active_games:
            self.draw_text("Aktif oyun yok. Yeni bir oyun olusturun!", self.font_medium, COLORS['gray'], WINDOW_WIDTH//2, 280)
        else:
            for i, g in enumerate(self.active_games[:8]):
                pygame.draw.rect(self.screen, COLORS['panel'] if i%2==0 else COLORS['bg'], (30, y, WINDOW_WIDTH-60, 45))
                rid = g.get('room_id','?')
                self.draw_text(rid, self.font_small, COLORS['hover'], 80, y+22)
                self.draw_text(f"{g.get('p1','?')[:8]} ({g.get('p1_elo',0)})", self.font_small, COLORS['red'], 200, y+22)
                p2 = g.get('p2', 'Bekleniyor...')
                if p2 == 'Bekleniyor...':
                    self.draw_text(p2, self.font_small, COLORS['waiting'], 380, y+22)
                else:
                    self.draw_text(f"{p2[:8]} ({g.get('p2_elo',0)})", self.font_small, COLORS['yellow'], 380, y+22)
                status = g.get('status', 'WAITING')
                if status == 'WAITING':
                    self.draw_text("Bekliyor", self.font_small, COLORS['waiting'], 530, y+22)
                    self.buttons.append((f'JOIN_{rid}', self.draw_button("Katil", 640, y+5, 80, 35, COLORS['green'])))
                else:
                    self.draw_text("Oyunda", self.font_small, COLORS['playing'], 530, y+22)
                    self.buttons.append((f'SPECTATE_{rid}', self.draw_button("Izle", 640, y+5, 80, 35, COLORS['hover'])))
                y += 50
        if self.status_text:
            self.draw_text(self.status_text, self.font_small, COLORS['gray'], WINDOW_WIDTH//2, WINDOW_HEIGHT-30)
    
    def draw_waiting(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("RAKIP BEKLENIYOR", self.font_large, COLORS['red'], WINDOW_WIDTH//2, 150)
        if self.room_id:
            self.draw_text(f"Oda Kodu: {self.room_id}", self.font_large, COLORS['green'], WINDOW_WIDTH//2, 250)
            self.draw_text("Rakip lobiden katilabilir!", self.font_medium, COLORS['white'], WINDOW_WIDTH//2, 310)
        self.draw_text(f"Bekleniyor{'.'*(int(time.time()*2)%4)}", self.font_medium, COLORS['gray'], WINDOW_WIDTH//2, 380)
        self.buttons = [('BACK', self.draw_button("Iptal", WINDOW_WIDTH//2-75, 450, 150, 45))]
    
    def draw_leaderboard(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("LIDERLIK TABLOSU", self.font_large, COLORS['red'], WINDOW_WIDTH//2, 50)
        try:
            r = requests.get(f"{SERVER_URL}/leaderboard", timeout=3)
            if r.status_code == 200:
                y = 120
                for i, p in enumerate(r.json()[:10]):
                    prefix = ["1.","2.","3."][i] if i < 3 else f"{i+1}."
                    self.draw_text(f"{prefix} {p['username']} - ELO: {p['rating']} (W:{p['wins']} L:{p['losses']})", 
                                  self.font_small, COLORS['yellow'] if i<3 else COLORS['white'], WINDOW_WIDTH//2, y)
                    y += 35
        except:
            self.draw_text("Sunucuya baglanilamadi", self.font_medium, COLORS['gray'], WINDOW_WIDTH//2, 200)
        self.buttons = [('BACK', self.draw_button("Geri", WINDOW_WIDTH//2-75, WINDOW_HEIGHT-80, 150, 45))]
    
    def draw_game(self):
        self.screen.fill(COLORS['bg'])
        title = "CANLI YAYIN" if self.is_spectator else ("AI'ya Karsi" if self.state=="PLAYING_AI" else "Online Mac")
        self.draw_text(title, self.font_large, COLORS['red'], WINDOW_WIDTH//2, 30)
        self.draw_board()
        self.buttons = [('BACK', self.draw_info_panel())]
        pygame.draw.rect(self.screen, COLORS['panel'], (0, WINDOW_HEIGHT-50, WINDOW_WIDTH, 50))
        self.draw_text(self.status_text, self.font_small, COLORS['white'], WINDOW_WIDTH//2, WINDOW_HEIGHT-25)
    
    # =========================================================================
    # NETWORK
    # =========================================================================
    
    def refresh_active_games(self):
        try:
            r = requests.get(f"{SERVER_URL}/active_games", timeout=2)
            if r.status_code == 200:
                self.active_games = r.json()
        except:
            pass
    
    def refresh_user_elo(self):
        if not self.username or self.is_guest:
            return
        try:
            r = requests.get(f"{SERVER_URL}/user/{self.username}", timeout=2)
            if r.status_code == 200:
                new_elo = r.json().get('user', {}).get('rating', self.user_elo)
                if new_elo != self.user_elo:
                    log(f"ELO updated: {self.user_elo} -> {new_elo}")
                    self.user_elo = new_elo
        except:
            pass
    
    # =========================================================================
    # AUTH
    # =========================================================================
    
    def do_login(self):
        u, p = self.input_fields['username']['value'].strip(), self.input_fields['password']['value']
        if not u or not p:
            self.set_status("Kullanici adi ve sifre gerekli!")
            return
        try:
            r = requests.post(f"{SERVER_URL}/login", json={'username': u, 'password': p}, timeout=5)
            if r.status_code == 200:
                user = r.json()['user']
                self.username, self.user_id, self.user_elo = user['username'], user['user_id'], user.get('rating', 1200)
                self.is_guest = False
                self.state = "MENU"
                self.set_status(f"Hosgeldin {self.username}!")
                self.clear_inputs()
                log(f"Logged in as {self.username}, ELO={self.user_elo}")
            else:
                self.set_status("Yanlis kullanici adi veya sifre!")
        except:
            self.set_status("Sunucuya baglanilamadi!")
    
    def do_register(self):
        u, p = self.input_fields['username']['value'].strip(), self.input_fields['password']['value']
        if not u or not p:
            self.set_status("Kullanici adi ve sifre gerekli!")
            return
        if len(u) < 3 or len(p) < 3:
            self.set_status("En az 3 karakter gerekli!")
            return
        try:
            r = requests.post(f"{SERVER_URL}/signup", json={'username': u, 'password': p}, timeout=5)
            if r.status_code == 201:
                self.username, self.user_id, self.user_elo, self.is_guest = u, r.json().get('user_id'), 1200, False
                self.state = "MENU"
                self.set_status(f"Kayit basarili! Hosgeldin {u}!")
                self.clear_inputs()
                log(f"Registered as {self.username}")
            elif r.status_code == 409:
                self.set_status("Bu kullanici adi zaten alinmis!")
            else:
                self.set_status("Kayit basarisiz!")
        except:
            self.set_status("Sunucuya baglanilamadi!")
    
    def guest_login(self):
        self.username = f"Misafir_{int(time.time())%10000}"
        self.user_id, self.user_elo, self.is_guest = None, 1200, True
        self.state = "MENU"
        self.set_status("")
        self.clear_inputs()
        log(f"Guest login: {self.username}")
    
    def logout(self):
        log("Logout")
        self.username, self.user_id, self.user_elo, self.is_guest = "", None, 1200, False
        self.state = "LOGIN"
        self.set_status("")
        self.clear_inputs()
    
    def clear_inputs(self):
        for f in self.input_fields.values():
            f['value'], f['active'] = '', False
        self.active_input = None
    
    # =========================================================================
    # AI MANAGEMENT - CRITICAL SECTION
    # =========================================================================
    
    def invalidate_ai_session(self):
        """Thread-safe AI invalidation"""
        with self.ai_lock:
            self.ai_session_id += 1
            self.pending_ai_move = None
            self.pending_ai_session = -1
            self.ai_thinking = False
            self.ai = None
            log(f"AI invalidated, new session: {self.ai_session_id}")
    
    def start_ai_game(self, depth):
        log(f"Starting AI game, depth={depth}")
        self.invalidate_ai_session()
        self.game = ConnectFourGame()
        with self.ai_lock:
            self.ai = AIEngine(PLAYER2_PIECE, depth=depth)
        self.my_piece = PLAYER1_PIECE
        self.state = "PLAYING_AI"
        self.is_spectator = False
        self.analysis_data = []  # Clear analysis
        self.status_text = "Senin siran!"
    
    # =========================================================================
    # BACKGROUND ANALYSIS (Lichess-style)
    # =========================================================================
    
    def start_background_analysis(self, game_state, move_num, player_piece, actual_col):
        """Start background analysis for a position (non-blocking)"""
        if not self.analysis_enabled:
            return
        
        def analyze():
            try:
                # Create a temporary AI for analysis (depth 6 for good analysis)
                analyzer = AIEngine(player_piece, depth=6)
                game_copy = game_state.clone()
                
                # Find best move for this position
                best_col = analyzer.find_best_move(game_copy)
                
                # Calculate evaluation score
                eval_score = analyzer.score_position(game_copy, player_piece)
                
                # Store analysis result
                with self.analysis_lock:
                    self.analysis_data.append({
                        'move_num': move_num,
                        'player': player_piece,
                        'actual_col': actual_col,
                        'best_col': best_col,
                        'eval_score': eval_score,
                        'was_best': actual_col == best_col
                    })
                    log(f"Analysis: Move {move_num}, Actual={actual_col}, Best={best_col}, {'✓' if actual_col == best_col else '✗'}")
            except Exception as e:
                log(f"Analysis error: {e}")
        
        # Run in background thread (daemon so it won't block shutdown)
        threading.Thread(target=analyze, daemon=True).start()
    
    def get_analysis_summary(self):
        """Get summary of game analysis"""
        with self.analysis_lock:
            if not self.analysis_data:
                return None
            
            total_moves = len(self.analysis_data)
            best_moves = sum(1 for d in self.analysis_data if d['was_best'])
            accuracy = (best_moves / total_moves * 100) if total_moves > 0 else 0
            
            # Separate by player
            p1_moves = [d for d in self.analysis_data if d['player'] == PLAYER1_PIECE]
            p2_moves = [d for d in self.analysis_data if d['player'] == PLAYER2_PIECE]
            
            p1_accuracy = (sum(1 for d in p1_moves if d['was_best']) / len(p1_moves) * 100) if p1_moves else 0
            p2_accuracy = (sum(1 for d in p2_moves if d['was_best']) / len(p2_moves) * 100) if p2_moves else 0
            
            return {
                'total_moves': total_moves,
                'best_moves': best_moves,
                'accuracy': accuracy,
                'p1_accuracy': p1_accuracy,
                'p2_accuracy': p2_accuracy,
                'mistakes': [d for d in self.analysis_data if not d['was_best']]
            }
    
    def create_online_game(self):
        log("Creating online game")
        self.invalidate_ai_session()
        if not self.network.create_game(self.username):
            self.set_status("Sunucuya baglanilamadi!")
    
    def join_online_game(self, room_id):
        log(f"Joining game: {room_id}")
        self.invalidate_ai_session()
        self.room_id = room_id.upper()
        self.is_spectator = False
        if not self.network.join_game(self.room_id, self.username):
            self.set_status("Odaya katilamadi!")
    
    def spectate_game(self, room_id):
        log(f"Spectating game: {room_id}")
        self.invalidate_ai_session()
        self.room_id = room_id.upper()
        self.is_spectator = True
        if self.network.join_game(self.room_id, self.username):
            self.state = "SPECTATING"
    
    # =========================================================================
    # NETWORK EVENTS
    # =========================================================================
    
    def on_game_created(self, data):
        self.room_id, self.my_piece = data['room_id'], data['player_piece']
        self.state, self.is_spectator = "WAITING", False
        self.set_status(f"Oda: {self.room_id}")
    
    def on_game_joined(self, data):
        self.room_id, self.my_piece = data['room_id'], data.get('player_piece', 0)
        if data.get('role') == 'spectator':
            self.is_spectator, self.state = True, "SPECTATING"
            if 'current_state' in data:
                self.game.from_dict(data['current_state'])
        else:
            self.is_spectator = False
            oi = data.get('opponent_info', {})
            self.opponent_name, self.opponent_elo = oi.get('username', 'Rakip'), oi.get('rating', 1200)
    
    def on_game_start(self, data):
        log("=== ONLINE GAME STARTING ===")
        # CRITICAL: Completely disable AI
        self.invalidate_ai_session()
        
        self.game = ConnectFourGame()
        self.state = "PLAYING_ONLINE"
        self.is_spectator = False
        self.analysis_data = []  # Clear previous analysis
        
        oi = data.get('p2_info' if self.my_piece == PLAYER1_PIECE else 'p1_info', {})
        self.opponent_name = data.get('opponent_name', oi.get('username', 'Rakip'))
        self.opponent_elo = oi.get('rating', 1200)
        
        log(f"State={self.state}, AI={self.ai}, opponent={self.opponent_name}")
        self.set_status("Oyun basladi!" + (" Senin siran." if self.game.current_player == self.my_piece else " Rakibin sirasi."))
    
    def on_move_made(self, data):
        col = data.get('col')
        if col is not None:
            log(f"Network move: col={col}, state={self.state}")
            row = self.game.heights[col] - col * (ROWS + 1)
            self.animate_drop(col, row, self.game.current_player, lambda: self.apply_network_move(data))
    
    def apply_network_move(self, data):
        # Get current state BEFORE updating (for analysis)
        move_num = len(self.game.move_history)
        current_player = self.game.current_player
        col = data.get('col')
        
        # Start background analysis BEFORE applying move
        if self.state == "PLAYING_ONLINE" and col is not None:
            game_before_move = self.game.clone()
            self.start_background_analysis(game_before_move, move_num, current_player, col)
        
        # Apply the move
        self.game.from_dict(data)
        
        if self.game.game_over:
            self.handle_game_over()
        elif self.game.current_player == self.my_piece:
            self.set_status("Senin siran!")
        else:
            self.set_status("Rakibin sirasi...")
    
    def on_game_over_network(self, data):
        w = data.get('winner')
        if self.is_spectator:
            self.set_status("Kirmizi kazandi!" if w==1 else ("Sari kazandi!" if w==2 else "Berabere!"))
        else:
            self.set_status("Kazandin!" if w==self.my_piece else ("Berabere!" if w is None else "Kaybettin."))
        self.refresh_user_elo()
    
    def on_elo_update(self, data):
        self.user_elo = data.get('new_elo', self.user_elo)
        c = data.get('change', 0)
        log(f"ELO changed: {c}, new={self.user_elo}")
        self.set_status(f"{'Kazandin' if c>0 else 'Kaybettin'}! ELO {'+' if c>0 else ''}{c} ({self.user_elo})")
    
    def on_opponent_disconnected(self):
        self.set_status("Rakip baglantisi koptu!")
    
    # =========================================================================
    # GAME LOGIC
    # =========================================================================
    
    def handle_click(self, col):
        if self.animating or self.game.game_over or self.is_spectator:
            return
        
        # STRICT STATE CHECKS
        if self.state == "PLAYING_AI":
            if self.game.current_player != PLAYER1_PIECE:
                return
            if self.ai_thinking:
                return
            with self.ai_lock:
                if self.ai is None:
                    return
        elif self.state == "PLAYING_ONLINE":
            if self.game.current_player != self.my_piece:
                return
        else:
            return
        
        if not self.game.is_valid_location(col):
            return
        
        log(f"Player click: col={col}, state={self.state}")
        row = self.game.heights[col] - col * (ROWS + 1)
        self.animate_drop(col, row, self.game.current_player, lambda: self.finish_move(col))
    
    def animate_drop(self, col, row, piece, callback):
        self.animating, self.anim_col, self.anim_piece = True, col, piece
        self.anim_y, self.anim_target_y = 50, 80 + (ROWS-1-row) * CELL_SIZE + CELL_SIZE//2
        self.anim_callback = callback
    
    def update_animation(self):
        if not self.animating:
            return
        self.anim_y += 18
        if self.anim_y >= self.anim_target_y:
            self.anim_y, self.animating = self.anim_target_y, False
            if self.anim_callback:
                self.anim_callback()
    
    def finish_move(self, col):
        log(f"finish_move: col={col}, state={self.state}")
        
        if not self.game.make_move(col):
            return
        
        # ONLINE MODE - ALWAYS SEND MOVE FIRST (even if game over!)
        if self.state == "PLAYING_ONLINE":
            log("Online mode - sending move to server")
            self.network.send_move(col)
            
            if self.game.game_over:
                log("Game ended - waiting for server confirmation")
                # Don't call handle_game_over here - wait for server's game_over event
            else:
                self.set_status("Rakibin sirasi...")
            return
        
        # AI MODE
        if self.state == "PLAYING_AI":
            if self.game.game_over:
                self.handle_game_over()
                return
            
            with self.ai_lock:
                if self.ai is not None and self.game.current_player == PLAYER2_PIECE:
                    log("AI mode - starting AI thread")
                    self.set_status("AI dusunuyor...")
                    self.ai_thinking = True
                    sid = self.ai_session_id
                    threading.Thread(target=self.ai_move, args=(sid,), daemon=True).start()
    
    def ai_move(self, sid):
        """AI calculation thread with extensive safety checks"""
        log(f"AI thread started, session={sid}")
        time.sleep(0.3)
        
        # PRE-CHECK
        with self.ai_lock:
            if self.ai is None:
                log(f"AI thread aborted: ai is None")
                return
            if sid != self.ai_session_id:
                log(f"AI thread aborted: session mismatch ({sid} vs {self.ai_session_id})")
                return
            if self.state != "PLAYING_AI":
                log(f"AI thread aborted: wrong state ({self.state})")
                return
            ai_ref = self.ai  # Get reference while locked
        
        # CALCULATE (outside lock)
        try:
            col = ai_ref.find_best_move(self.game)
        except Exception as e:
            log(f"AI error: {e}")
            col = None
        
        # POST-CHECK
        with self.ai_lock:
            if self.ai is None:
                log(f"AI thread post-check: ai is None")
                self.ai_thinking = False
                return
            if sid != self.ai_session_id:
                log(f"AI thread post-check: session mismatch")
                self.ai_thinking = False
                return
            if self.state != "PLAYING_AI":
                log(f"AI thread post-check: wrong state ({self.state})")
                self.ai_thinking = False
                return
            
            self.ai_thinking = False
            if col is not None and not self.game.game_over:
                log(f"AI move ready: col={col}")
                self.pending_ai_move = col
                self.pending_ai_session = sid
    
    def execute_ai_move(self, col):
        log(f"execute_ai_move: col={col}")
        with self.ai_lock:
            if self.ai is None:
                log("execute_ai_move aborted: ai is None")
                return
            if self.state != "PLAYING_AI":
                log(f"execute_ai_move aborted: wrong state ({self.state})")
                return
        if self.game.game_over or not self.game.is_valid_location(col):
            return
        row = self.game.heights[col] - col * (ROWS + 1)
        self.animate_drop(col, row, PLAYER2_PIECE, lambda: self.finish_ai_move(col))
    
    def finish_ai_move(self, col):
        log(f"finish_ai_move: col={col}")
        with self.ai_lock:
            if self.ai is None:
                log("finish_ai_move aborted: ai is None")
                return
            if self.state != "PLAYING_AI":
                log(f"finish_ai_move aborted: wrong state ({self.state})")
                return
        if not self.game.make_move(col):
            return
        if self.game.game_over:
            self.handle_game_over()
        else:
            self.set_status("Senin siran!")
    
    def handle_game_over(self):
        w = self.game.winner
        log(f"Game over: winner={w}")
        
        # Show analysis summary for online games
        if self.state == "PLAYING_ONLINE" and self.analysis_data:
            summary = self.get_analysis_summary()
            if summary:
                log(f"Analysis Summary: {summary['total_moves']} moves, {summary['accuracy']:.1f}% accuracy")
                log(f"  P1 Accuracy: {summary['p1_accuracy']:.1f}%")
                log(f"  P2 Accuracy: {summary['p2_accuracy']:.1f}%")
                if summary['mistakes']:
                    log(f"  Mistakes: {len(summary['mistakes'])}")
        
        if w == PLAYER1_PIECE:
            self.set_status("Kazandin!" if self.state=="PLAYING_AI" or self.my_piece==1 else f"{self.opponent_name} kazandi!")
        elif w == PLAYER2_PIECE:
            self.set_status("AI kazandi!" if self.state=="PLAYING_AI" else ("Kazandin!" if self.my_piece==2 else f"{self.opponent_name} kazandi!"))
        else:
            self.set_status("Berabere!")
    
    def set_status(self, text):
        self.status_text = text
    
    def reset_to_menu(self):
        log("Reset to menu")
        self.invalidate_ai_session()
        self.network.disconnect()
        self.network = NetworkManager(self)
        self.room_id, self.is_spectator = None, False
        self.game = ConnectFourGame()
        self.state = "MENU"
        self.refresh_user_elo()
    
    # =========================================================================
    # EVENTS
    # =========================================================================
    
    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.invalidate_ai_session()
                self.network.disconnect()
                pygame.quit()
                sys.exit()
            elif e.type == pygame.MOUSEMOTION:
                mx, my = e.pos
                if self.state in ["PLAYING_AI", "PLAYING_ONLINE"] and 20 <= mx <= 20+BOARD_WIDTH and 80 <= my <= 80+BOARD_HEIGHT:
                    self.hover_col = (mx - 20) // CELL_SIZE
                else:
                    self.hover_col = -1
            elif e.type == pygame.MOUSEBUTTONDOWN:
                mx, my = e.pos
                if self.state == "LOGIN":
                    for fn, f in self.input_fields.items():
                        if f['rect'] and f['rect'].collidepoint(mx, my):
                            for ff in self.input_fields.values():
                                ff['active'] = False
                            f['active'] = True
                            self.active_input = fn
                            return
                for bid, rect in self.buttons:
                    if rect.collidepoint(mx, my):
                        self.handle_button_click(bid)
                        return
                if self.state in ["PLAYING_AI", "PLAYING_ONLINE"] and 20 <= mx <= 20+BOARD_WIDTH and 80 <= my <= 80+BOARD_HEIGHT:
                    self.handle_click((mx - 20) // CELL_SIZE)
            elif e.type == pygame.KEYDOWN and self.state == "LOGIN" and self.active_input:
                f = self.input_fields[self.active_input]
                if e.key == pygame.K_RETURN:
                    if self.active_input == 'username':
                        self.input_fields['username']['active'] = False
                        self.input_fields['password']['active'] = True
                        self.active_input = 'password'
                    else:
                        self.do_login()
                elif e.key == pygame.K_TAB:
                    self.active_input = 'password' if self.active_input == 'username' else 'username'
                    for fn, ff in self.input_fields.items():
                        ff['active'] = fn == self.active_input
                elif e.key == pygame.K_BACKSPACE:
                    f['value'] = f['value'][:-1]
                elif e.unicode.isprintable() and len(f['value']) < 20:
                    f['value'] += e.unicode
    
    def handle_button_click(self, bid):
        actions = {
            'DO_LOGIN': self.do_login, 'DO_REGISTER': self.do_register, 'GUEST': self.guest_login,
            'LOGOUT': self.logout, 'BACK': self.reset_to_menu, 
            'REFRESH': lambda: (self.refresh_active_games(), self.set_status("Yenilendi")),
            'AI': lambda: setattr(self, 'state', 'AI_SELECT'),
            'LOBBY': lambda: (setattr(self, 'state', 'LOBBY'), self.refresh_active_games()),
            'LEADERBOARD': lambda: setattr(self, 'state', 'LEADERBOARD'),
            'CREATE': self.create_online_game,
            'QUIT': lambda: (self.invalidate_ai_session(), self.network.disconnect(), pygame.quit(), sys.exit())
        }
        if bid in actions:
            actions[bid]()
        elif bid.startswith('AI_'):
            self.start_ai_game(int(bid.split('_')[1]))
        elif bid.startswith('JOIN_'):
            self.join_online_game(bid.replace('JOIN_', ''))
        elif bid.startswith('SPECTATE_'):
            self.spectate_game(bid.replace('SPECTATE_', ''))
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
    def run(self):
        log("Main loop starting")
        while True:
            self.handle_events()
            self.update_animation()
            
            # AI move with STRICT VALIDATION
            if self.pending_ai_move is not None:
                with self.ai_lock:
                    valid = (self.ai is not None and 
                            self.state == "PLAYING_AI" and 
                            self.pending_ai_session == self.ai_session_id)
                
                if valid:
                    col = self.pending_ai_move
                    self.pending_ai_move = None
                    self.pending_ai_session = -1
                    self.execute_ai_move(col)
                else:
                    log(f"Discarding stale AI move (state={self.state}, ai={self.ai is not None})")
                    self.pending_ai_move = None
                    self.pending_ai_session = -1
            
            # Draw
            screens = {'LOGIN': self.draw_login, 'MENU': self.draw_menu, 'AI_SELECT': self.draw_ai_select,
                      'LOBBY': self.draw_lobby, 'WAITING': self.draw_waiting, 'LEADERBOARD': self.draw_leaderboard}
            if self.state in screens:
                screens[self.state]()
            elif self.state in ["PLAYING_AI", "PLAYING_ONLINE", "SPECTATING"]:
                self.draw_game()
            
            pygame.display.flip()
            self.clock.tick(60)

if __name__ == "__main__":
    ConnectFourGUI().run()