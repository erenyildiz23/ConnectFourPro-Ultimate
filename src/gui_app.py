# =============================================================================
# MODULE: gui_app.py
# Connect Four Pro - Pygame GUI Client v4.1
# Features: Login/Register, Online Lobby, Spectate, FIXED AI
# =============================================================================

import os
# Disable audio BEFORE importing pygame
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
# CONFIGURATION
# =============================================================================

CELL_SIZE = 80
BOARD_WIDTH = COLS * CELL_SIZE
BOARD_HEIGHT = ROWS * CELL_SIZE
WINDOW_WIDTH = BOARD_WIDTH + 320
WINDOW_HEIGHT = BOARD_HEIGHT + 150

SERVER_URL = 'http://localhost:5000'

# Colors
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
        
        @self.sio.event
        def disconnect():
            self.connected = False
        
        @self.sio.on('game_created')
        def on_game_created(data):
            self.room_id = data['room_id']
            self.my_piece = data['player_piece']
            self.gui.on_game_created(data)
        
        @self.sio.on('game_joined')
        def on_game_joined(data):
            self.room_id = data['room_id']
            self.my_piece = data['player_piece']
            self.gui.on_game_joined(data)
        
        @self.sio.on('game_start')
        def on_game_start(data):
            self.gui.on_game_start(data)
        
        @self.sio.on('move_made')
        def on_move_made(data):
            self.gui.on_move_made(data)
        
        @self.sio.on('game_over')
        def on_game_over(data):
            self.gui.on_game_over_network(data)
        
        @self.sio.on('elo_update')
        def on_elo_update(data):
            self.gui.on_elo_update(data)
        
        @self.sio.on('opponent_disconnected')
        def on_opponent_disconnected(data):
            self.gui.on_opponent_disconnected()
        
        @self.sio.on('error')
        def on_error(data):
            self.gui.set_status(f"Hata: {data.get('msg', '')}")
    
    def connect_to_server(self):
        if self.connected:
            return True
        try:
            self.sio.connect(SERVER_URL, wait_timeout=5)
            time.sleep(0.5)
            return self.connected
        except:
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
        self.ai_session_id = 0
        
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
        self.pending_ai_move = None
        self.pending_ai_session = -1
    
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
    
    def draw_board(self):
        bx, by = 20, 80
        pygame.draw.rect(self.screen, COLORS['board'], (bx-10, by-10, BOARD_WIDTH+20, BOARD_HEIGHT+20), border_radius=10)
        for col in range(COLS):
            for row in range(ROWS):
                x = bx + col * CELL_SIZE + CELL_SIZE // 2
                y = by + (ROWS - 1 - row) * CELL_SIZE + CELL_SIZE // 2
                pygame.draw.circle(self.screen, COLORS['cell_bg'], (x, y), CELL_SIZE // 2 - 5)
                idx = col * (ROWS + 1) + row
                if (self.game.bitboards[PLAYER1_PIECE] >> idx) & 1:
                    pygame.draw.circle(self.screen, COLORS['red'], (x, y), CELL_SIZE // 2 - 8)
                elif (self.game.bitboards[PLAYER2_PIECE] >> idx) & 1:
                    pygame.draw.circle(self.screen, COLORS['yellow'], (x, y), CELL_SIZE // 2 - 8)
        
        if self.hover_col >= 0 and not self.animating and not self.game.game_over and not self.is_spectator:
            can_play = (self.state == "PLAYING_AI" and self.game.current_player == PLAYER1_PIECE and not self.ai_thinking) or \
                       (self.state == "PLAYING_ONLINE" and self.game.current_player == self.my_piece)
            if can_play:
                pygame.draw.circle(self.screen, COLORS['hover'], (bx + self.hover_col * CELL_SIZE + CELL_SIZE//2, 50), CELL_SIZE//2 - 10)
        
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
        return self.draw_button("Menu", px+50, py+270, 150, 40)
    
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
        for i, (txt, x) in enumerate([("ODA",80),("OYUNCU 1",200),("OYUNCU 2",380),("DURUM",530),("ISLEM",680)]):
            self.draw_text(txt, self.font_small, COLORS['white'], x, 157)
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
                self.user_elo = r.json().get('user', {}).get('rating', self.user_elo)
        except:
            pass
    
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
    
    def logout(self):
        self.username, self.user_id, self.user_elo, self.is_guest = "", None, 1200, False
        self.state = "LOGIN"
        self.set_status("")
        self.clear_inputs()
    
    def clear_inputs(self):
        for f in self.input_fields.values():
            f['value'], f['active'] = '', False
        self.active_input = None
    
    def invalidate_ai_session(self):
        """Completely disable and invalidate any pending AI operations"""
        self.ai_session_id += 1
        self.pending_ai_move = None
        self.pending_ai_session = -1
        self.ai_thinking = False
        self.ai = None  # CRITICAL: Set AI to None to prevent any operations
    
    def start_ai_game(self, depth):
        self.invalidate_ai_session()
        self.game = ConnectFourGame()
        self.ai = AIEngine(PLAYER2_PIECE, depth=depth)
        self.my_piece = PLAYER1_PIECE
        self.state = "PLAYING_AI"
        self.is_spectator = False
        self.status_text = "Senin siran!"
    
    def create_online_game(self):
        self.invalidate_ai_session()
        self.ai = None  # Explicitly clear AI
        self.pending_ai_move = None  # Clear any pending moves
        if not self.network.create_game(self.username):
            self.set_status("Sunucuya baglanilamadi!")
    
    def join_online_game(self, room_id):
        self.invalidate_ai_session()
        self.ai = None  # Explicitly clear AI
        self.pending_ai_move = None  # Clear any pending moves
        self.room_id = room_id.upper()
        self.is_spectator = False
        if not self.network.join_game(self.room_id, self.username):
            self.set_status("Odaya katilamadi!")
    
    def spectate_game(self, room_id):
        self.invalidate_ai_session()
        self.ai = None  # Explicitly clear AI
        self.pending_ai_move = None  # Clear any pending moves
        self.room_id = room_id.upper()
        self.is_spectator = True
        if self.network.join_game(self.room_id, self.username):
            self.state = "SPECTATING"
    
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
        # CRITICAL: Completely disable AI for online games
        self.invalidate_ai_session()
        self.ai = None
        self.pending_ai_move = None
        self.ai_thinking = False
        
        self.game = ConnectFourGame()
        self.state, self.is_spectator = "PLAYING_ONLINE", False
        oi = data.get('p2_info' if self.my_piece == PLAYER1_PIECE else 'p1_info', {})
        self.opponent_name = data.get('opponent_name', oi.get('username', 'Rakip'))
        self.opponent_elo = oi.get('rating', 1200)
        self.set_status("Oyun basladi!" + (" Senin siran." if self.game.current_player == self.my_piece else " Rakibin sirasi."))
    
    def on_move_made(self, data):
        col = data.get('col')
        if col is not None:
            row = self.game.heights[col] - col * (ROWS + 1)
            self.animate_drop(col, row, self.game.current_player, lambda: self.apply_network_move(data))
    
    def apply_network_move(self, data):
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
        self.set_status(f"{'Kazandin' if c>0 else 'Kaybettin'}! ELO {'+' if c>0 else ''}{c} ({self.user_elo})")
    
    def on_opponent_disconnected(self):
        self.set_status("Rakip baglantisi koptu!")
    
    def handle_click(self, col):
        if self.animating or self.game.game_over or self.is_spectator:
            return
        if self.state == "PLAYING_AI" and (self.game.current_player != PLAYER1_PIECE or self.ai_thinking):
            return
        if self.state == "PLAYING_ONLINE" and self.game.current_player != self.my_piece:
            return
        if not self.game.is_valid_location(col):
            return
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
        if not self.game.make_move(col):
            return
        if self.game.game_over:
            self.handle_game_over()
            return
        # ONLINE MODE - NO AI!
        if self.state == "PLAYING_ONLINE":
            self.network.send_move(col)
            self.set_status("Rakibin sirasi...")
            return
        # AI MODE ONLY - with strict checks
        if self.state == "PLAYING_AI" and self.ai is not None and self.game.current_player == PLAYER2_PIECE:
            self.set_status("AI dusunuyor...")
            self.ai_thinking = True
            sid = self.ai_session_id
            threading.Thread(target=self.ai_move, args=(sid,), daemon=True).start()
    
    def ai_move(self, sid):
        time.sleep(0.3)
        # AGGRESSIVE CHECKS - AI must exist and state must be correct
        if self.ai is None:
            return
        if sid != self.ai_session_id:
            return
        if self.state != "PLAYING_AI":
            return
        
        col = self.ai.find_best_move(self.game)
        
        # RE-CHECK after calculation (state may have changed during calculation)
        if self.ai is None:
            return
        if sid != self.ai_session_id:
            return
        if self.state != "PLAYING_AI":
            return
        
        self.ai_thinking = False
        if col is not None and not self.game.game_over:
            self.pending_ai_move, self.pending_ai_session = col, sid
    
    def execute_ai_move(self, col):
        # STRICT CHECKS
        if self.ai is None:
            return
        if self.state != "PLAYING_AI":
            return
        if self.game.game_over or not self.game.is_valid_location(col):
            return
        row = self.game.heights[col] - col * (ROWS + 1)
        self.animate_drop(col, row, PLAYER2_PIECE, lambda: self.finish_ai_move(col))
    
    def finish_ai_move(self, col):
        # STRICT CHECKS
        if self.ai is None:
            return
        if self.state != "PLAYING_AI":
            return
        if not self.game.make_move(col):
            return
        if self.game.game_over:
            self.handle_game_over()
        else:
            self.set_status("Senin siran!")
    
    def handle_game_over(self):
        w = self.game.winner
        if w == PLAYER1_PIECE:
            self.set_status("Kazandin!" if self.state=="PLAYING_AI" or self.my_piece==1 else f"{self.opponent_name} kazandi!")
        elif w == PLAYER2_PIECE:
            self.set_status("AI kazandi!" if self.state=="PLAYING_AI" else ("Kazandin!" if self.my_piece==2 else f"{self.opponent_name} kazandi!"))
        else:
            self.set_status("Berabere!")
    
    def set_status(self, text):
        self.status_text = text
    
    def reset_to_menu(self):
        self.invalidate_ai_session()
        self.ai = None
        self.network.disconnect()
        self.network = NetworkManager(self)
        self.room_id, self.is_spectator = None, False
        self.game = ConnectFourGame()
        self.state = "MENU"
        self.refresh_user_elo()
    
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
            'LOGOUT': self.logout, 'BACK': self.reset_to_menu, 'REFRESH': lambda: (self.refresh_active_games(), self.set_status("Yenilendi")),
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
    
    def run(self):
        while True:
            self.handle_events()
            self.update_animation()
            # AI move with STRICT VALIDATION
            if self.pending_ai_move is not None:
                if self.ai is not None and self.state == "PLAYING_AI" and self.pending_ai_session == self.ai_session_id:
                    col = self.pending_ai_move
                    self.pending_ai_move = self.pending_ai_session = None
                    self.execute_ai_move(col)
                else:
                    # Discard stale/invalid AI move
                    self.pending_ai_move = self.pending_ai_session = None
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