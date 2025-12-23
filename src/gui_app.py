# =============================================================================
# MODULE: gui_app.py
# Connect Four Pro - Pygame GUI Client v3.0
# Features: Login/Register Screen, Online Lobby, Spectate, Fixed AI
# =============================================================================

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

# AI Difficulty Settings
AI_DEPTHS = {
    'Kolay': 2,
    'Orta': 4,
    'Zor': 6
}

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
            print("[NET] Connected to server")
        
        @self.sio.event
        def disconnect():
            self.connected = False
            print("[NET] Disconnected")
        
        @self.sio.on('game_created')
        def on_game_created(data):
            print(f"[NET] Game created: {data}")
            self.room_id = data['room_id']
            self.my_piece = data['player_piece']
            self.gui.on_game_created(data)
        
        @self.sio.on('game_joined')
        def on_game_joined(data):
            print(f"[NET] Game joined: {data}")
            self.room_id = data['room_id']
            self.my_piece = data['player_piece']
            self.gui.on_game_joined(data)
        
        @self.sio.on('game_start')
        def on_game_start(data):
            print(f"[NET] Game started: {data}")
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
            print(f"[NET] Error: {data}")
            self.gui.set_status(f"Hata: {data.get('msg', '')}")
    
    def connect_to_server(self):
        if self.connected:
            return True
        try:
            self.sio.connect(SERVER_URL, wait_timeout=5)
            time.sleep(0.5)
            return self.connected
        except Exception as e:
            print(f"[NET] Connection failed: {e}")
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
            self.sio.emit('make_move', {
                'room_id': self.room_id,
                'col': col,
                'player_piece': self.my_piece
            })
    
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
        
        # Game state - START WITH LOGIN SCREEN
        self.state = "LOGIN"
        self.game = ConnectFourGame()
        self.ai = None
        self.ai_thinking = False
        self.ai_should_stop = False  # FLAG TO STOP AI THREAD
        self.is_spectator = False
        
        # Player info
        self.username = ""
        self.user_id = None
        self.user_elo = 1200
        self.opponent_name = "Rakip"
        self.opponent_elo = 1200
        self.is_guest = False
        
        # Network
        self.network = NetworkManager(self)
        self.my_piece = PLAYER1_PIECE
        self.room_id = None
        
        # Lobby data
        self.active_games = []
        self.last_lobby_refresh = 0
        
        # UI state
        self.status_text = ""
        self.hover_col = -1
        self.buttons = []
        
        # Input fields for login
        self.input_fields = {
            'username': {'value': '', 'active': False, 'rect': None},
            'password': {'value': '', 'active': False, 'rect': None}
        }
        self.active_input = None
        
        # Animation
        self.animating = False
        self.anim_col = 0
        self.anim_row = 0
        self.anim_y = 0
        self.anim_target_y = 0
        self.anim_piece = PLAYER1_PIECE
        self.anim_callback = None
        self.pending_ai_move = None
    
    # =========================================================================
    # DRAWING METHODS
    # =========================================================================
    
    def draw_text(self, text, font, color, x, y, center=True):
        surface = font.render(str(text), True, color)
        rect = surface.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surface, rect)
    
    def draw_button(self, text, x, y, w, h, hover=False, color=None):
        if color is None:
            color = COLORS['button_hover'] if hover else COLORS['button']
        pygame.draw.rect(self.screen, color, (x, y, w, h), border_radius=8)
        self.draw_text(text, self.font_small, COLORS['white'], x + w//2, y + h//2)
        return pygame.Rect(x, y, w, h)
    
    def draw_input_field(self, label, field_name, x, y, w, h, is_password=False):
        field = self.input_fields[field_name]
        
        # Label
        self.draw_text(label, self.font_small, COLORS['gray'], x + w//2, y - 15)
        
        # Input box
        color = COLORS['input_active'] if field['active'] else COLORS['input_bg']
        pygame.draw.rect(self.screen, color, (x, y, w, h), border_radius=6)
        pygame.draw.rect(self.screen, COLORS['white'], (x, y, w, h), 2, border_radius=6)
        
        # Text
        display_text = '*' * len(field['value']) if is_password else field['value']
        if not display_text and not field['active']:
            display_text = "..."
        self.draw_text(display_text, self.font_medium, COLORS['white'], x + w//2, y + h//2)
        
        # Store rect for click detection
        field['rect'] = pygame.Rect(x, y, w, h)
        return field['rect']
    
    def draw_board(self):
        board_x = 20
        board_y = 80
        
        # Board background
        pygame.draw.rect(self.screen, COLORS['board'], 
                        (board_x - 10, board_y - 10, BOARD_WIDTH + 20, BOARD_HEIGHT + 20),
                        border_radius=10)
        
        # Draw cells and pieces
        for col in range(COLS):
            for row in range(ROWS):
                x = board_x + col * CELL_SIZE + CELL_SIZE // 2
                y = board_y + (ROWS - 1 - row) * CELL_SIZE + CELL_SIZE // 2
                
                # Cell background
                pygame.draw.circle(self.screen, COLORS['cell_bg'], (x, y), CELL_SIZE // 2 - 5)
                
                # Piece
                idx = col * (ROWS + 1) + row
                if (self.game.bitboards[PLAYER1_PIECE] >> idx) & 1:
                    pygame.draw.circle(self.screen, COLORS['red'], (x, y), CELL_SIZE // 2 - 8)
                elif (self.game.bitboards[PLAYER2_PIECE] >> idx) & 1:
                    pygame.draw.circle(self.screen, COLORS['yellow'], (x, y), CELL_SIZE // 2 - 8)
        
        # Hover indicator
        if self.hover_col >= 0 and not self.animating and not self.game.game_over and not self.is_spectator:
            can_play = False
            if self.state == "PLAYING_AI" and self.game.current_player == PLAYER1_PIECE and not self.ai_thinking:
                can_play = True
            elif self.state == "PLAYING_ONLINE" and self.game.current_player == self.my_piece:
                can_play = True
            
            if can_play:
                x = board_x + self.hover_col * CELL_SIZE + CELL_SIZE // 2
                pygame.draw.circle(self.screen, COLORS['hover'], (x, 50), CELL_SIZE // 2 - 10)
        
        # Animating piece
        if self.animating:
            x = board_x + self.anim_col * CELL_SIZE + CELL_SIZE // 2
            color = COLORS['red'] if self.anim_piece == PLAYER1_PIECE else COLORS['yellow']
            pygame.draw.circle(self.screen, color, (x, int(self.anim_y)), CELL_SIZE // 2 - 8)
    
    def draw_info_panel(self):
        panel_x = BOARD_WIDTH + 50
        panel_y = 80
        
        # Panel background
        pygame.draw.rect(self.screen, COLORS['panel'], 
                        (panel_x, panel_y, 250, 320), border_radius=10)
        
        # Title
        if self.is_spectator:
            self.draw_text("IZLIYORSUNUZ", self.font_medium, COLORS['waiting'], panel_x + 125, panel_y + 25)
        else:
            self.draw_text("OYUN BILGISI", self.font_medium, COLORS['white'], panel_x + 125, panel_y + 25)
        
        # Player 1
        pygame.draw.circle(self.screen, COLORS['red'], (panel_x + 25, panel_y + 70), 15)
        if self.state == "PLAYING_AI":
            p1_name = self.username
            p1_elo = self.user_elo
        else:
            if self.my_piece == PLAYER1_PIECE:
                p1_name = self.username
                p1_elo = self.user_elo
            else:
                p1_name = self.opponent_name
                p1_elo = self.opponent_elo
        self.draw_text(f"{p1_name[:10]}", self.font_small, COLORS['white'], panel_x + 50, panel_y + 65, center=False)
        self.draw_text(f"ELO: {p1_elo}", self.font_tiny, COLORS['gray'], panel_x + 50, panel_y + 85, center=False)
        if self.game.current_player == PLAYER1_PIECE and not self.game.game_over:
            self.draw_text("< SIRA", self.font_small, COLORS['green'], panel_x + 200, panel_y + 70)
        
        # Player 2
        pygame.draw.circle(self.screen, COLORS['yellow'], (panel_x + 25, panel_y + 130), 15)
        if self.state == "PLAYING_AI":
            p2_name = f"AI (D{self.ai.depth if self.ai else '?'})"
            p2_elo = "-"
        else:
            if self.my_piece == PLAYER2_PIECE:
                p2_name = self.username
                p2_elo = self.user_elo
            else:
                p2_name = self.opponent_name
                p2_elo = self.opponent_elo
        self.draw_text(f"{p2_name[:10]}", self.font_small, COLORS['white'], panel_x + 50, panel_y + 125, center=False)
        if p2_elo != "-":
            self.draw_text(f"ELO: {p2_elo}", self.font_tiny, COLORS['gray'], panel_x + 50, panel_y + 145, center=False)
        if self.game.current_player == PLAYER2_PIECE and not self.game.game_over:
            self.draw_text("< SIRA", self.font_small, COLORS['green'], panel_x + 200, panel_y + 130)
        
        # Room ID
        if self.state in ["WAITING", "PLAYING_ONLINE", "SPECTATING"] and self.room_id:
            self.draw_text(f"Oda: {self.room_id}", self.font_medium, COLORS['hover'], panel_x + 125, panel_y + 200)
        
        # Move count
        move_count = len(self.game.move_history)
        self.draw_text(f"Hamle: {move_count}", self.font_small, COLORS['gray'], panel_x + 125, panel_y + 240)
        
        # Back button
        return self.draw_button("Menu", panel_x + 50, panel_y + 270, 150, 40)
    
    # =========================================================================
    # LOGIN SCREEN
    # =========================================================================
    
    def draw_login(self):
        self.screen.fill(COLORS['bg'])
        
        # Title
        self.draw_text("CONNECT FOUR PRO", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 60)
        self.draw_text("Hosgeldiniz!", self.font_medium, COLORS['white'], WINDOW_WIDTH // 2, 110)
        
        # Input fields
        center_x = WINDOW_WIDTH // 2
        field_w, field_h = 280, 45
        
        self.draw_input_field("Kullanici Adi", 'username', 
                             center_x - field_w//2, 170, field_w, field_h)
        self.draw_input_field("Sifre", 'password', 
                             center_x - field_w//2, 260, field_w, field_h, is_password=True)
        
        # Buttons
        btn_w, btn_h = 130, 45
        self.buttons = []
        self.buttons.append(('DO_LOGIN', self.draw_button("Giris Yap", center_x - btn_w - 10, 340, btn_w, btn_h)))
        self.buttons.append(('DO_REGISTER', self.draw_button("Kayit Ol", center_x + 10, 340, btn_w, btn_h, color=COLORS['green'])))
        
        # Divider
        pygame.draw.line(self.screen, COLORS['gray'], (center_x - 100, 420), (center_x + 100, 420), 1)
        self.draw_text("veya", self.font_tiny, COLORS['gray'], center_x, 420)
        
        # Guest button
        self.buttons.append(('GUEST', self.draw_button("Misafir Olarak Devam", center_x - 120, 450, 240, 45, color=COLORS['panel'])))
        
        # Status
        if self.status_text:
            color = COLORS['green'] if 'basarili' in self.status_text.lower() else COLORS['red']
            self.draw_text(self.status_text, self.font_small, color, WINDOW_WIDTH // 2, WINDOW_HEIGHT - 40)
    
    # =========================================================================
    # MENU SCREENS
    # =========================================================================
    
    def draw_menu(self):
        self.screen.fill(COLORS['bg'])
        
        # Title
        self.draw_text("CONNECT FOUR PRO", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 50)
        
        # User info
        if self.is_guest:
            self.draw_text(f"Misafir: {self.username}", self.font_small, COLORS['gray'], WINDOW_WIDTH // 2, 95)
        else:
            self.draw_text(f"{self.username}", self.font_medium, COLORS['white'], WINDOW_WIDTH // 2, 90)
            self.draw_text(f"ELO: {self.user_elo}", self.font_small, COLORS['green'], WINDOW_WIDTH // 2, 115)
        
        # Buttons
        btn_w, btn_h = 250, 50
        center_x = WINDOW_WIDTH // 2 - btn_w // 2
        
        self.buttons = []
        self.buttons.append(('AI', self.draw_button("Yapay Zekaya Karsi", center_x, 160, btn_w, btn_h)))
        self.buttons.append(('LOBBY', self.draw_button("Online Lobi", center_x, 225, btn_w, btn_h)))
        self.buttons.append(('LEADERBOARD', self.draw_button("Liderlik Tablosu", center_x, 290, btn_w, btn_h)))
        self.buttons.append(('LOGOUT', self.draw_button("Cikis Yap", center_x, 355, btn_w, btn_h, color=COLORS['panel'])))
        self.buttons.append(('QUIT', self.draw_button("Oyunu Kapat", center_x, 420, btn_w, btn_h, color=COLORS['gray'])))
        
        # Status
        if self.status_text:
            self.draw_text(self.status_text, self.font_small, COLORS['gray'], WINDOW_WIDTH // 2, WINDOW_HEIGHT - 30)
    
    def draw_ai_select(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("ZORLUK SEVIYESI SEC", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 80)
        
        btn_w, btn_h = 200, 50
        center_x = WINDOW_WIDTH // 2 - btn_w // 2
        
        self.buttons = []
        y = 180
        for name, depth in AI_DEPTHS.items():
            self.buttons.append((f'AI_{depth}', self.draw_button(f"{name} (D{depth})", center_x, y, btn_w, btn_h)))
            y += 70
        
        self.buttons.append(('BACK', self.draw_button("Geri", center_x, y + 30, btn_w, btn_h)))
    
    def draw_lobby(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("ONLINE LOBI", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 40)
        
        # Refresh
        if time.time() - self.last_lobby_refresh > 2:
            self.refresh_active_games()
            self.last_lobby_refresh = time.time()
        
        # Buttons
        self.buttons = []
        self.buttons.append(('CREATE', self.draw_button("+ Yeni Oyun", 50, 80, 160, 45)))
        self.buttons.append(('REFRESH', self.draw_button("Yenile", 230, 80, 100, 45)))
        self.buttons.append(('BACK', self.draw_button("Geri", WINDOW_WIDTH - 150, 80, 100, 45)))
        
        # Header
        pygame.draw.rect(self.screen, COLORS['panel'], (30, 140, WINDOW_WIDTH - 60, 35), border_radius=5)
        self.draw_text("ODA", self.font_small, COLORS['white'], 80, 157)
        self.draw_text("OYUNCU 1", self.font_small, COLORS['white'], 200, 157)
        self.draw_text("OYUNCU 2", self.font_small, COLORS['white'], 380, 157)
        self.draw_text("DURUM", self.font_small, COLORS['white'], 530, 157)
        self.draw_text("ISLEM", self.font_small, COLORS['white'], 680, 157)
        
        # Games list
        y = 185
        if not self.active_games:
            self.draw_text("Aktif oyun yok. Yeni bir oyun olusturun!", 
                          self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 280)
        else:
            for i, game in enumerate(self.active_games[:8]):
                row_color = COLORS['panel'] if i % 2 == 0 else COLORS['bg']
                pygame.draw.rect(self.screen, row_color, (30, y, WINDOW_WIDTH - 60, 45))
                
                room_id = game.get('room_id', '?')
                self.draw_text(room_id, self.font_small, COLORS['hover'], 80, y + 22)
                
                p1 = game.get('p1', '?')
                p1_elo = game.get('p1_elo', 0)
                self.draw_text(f"{p1[:8]} ({p1_elo})", self.font_small, COLORS['red'], 200, y + 22)
                
                p2 = game.get('p2', 'Bekleniyor...')
                p2_elo = game.get('p2_elo', 0)
                if p2 == 'Bekleniyor...':
                    self.draw_text(p2, self.font_small, COLORS['waiting'], 380, y + 22)
                else:
                    self.draw_text(f"{p2[:8]} ({p2_elo})", self.font_small, COLORS['yellow'], 380, y + 22)
                
                status = game.get('status', 'WAITING')
                if status == 'WAITING':
                    self.draw_text("Bekliyor", self.font_small, COLORS['waiting'], 530, y + 22)
                    btn = self.draw_button("Katil", 640, y + 5, 80, 35, color=COLORS['green'])
                    self.buttons.append((f'JOIN_{room_id}', btn))
                else:
                    self.draw_text("Oyunda", self.font_small, COLORS['playing'], 530, y + 22)
                    btn = self.draw_button("Izle", 640, y + 5, 80, 35, color=COLORS['hover'])
                    self.buttons.append((f'SPECTATE_{room_id}', btn))
                
                y += 50
        
        if self.status_text:
            self.draw_text(self.status_text, self.font_small, COLORS['gray'], WINDOW_WIDTH // 2, WINDOW_HEIGHT - 30)
    
    def draw_waiting(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("RAKIP BEKLENIYOR", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 150)
        
        if self.room_id:
            self.draw_text(f"Oda Kodu: {self.room_id}", self.font_large, COLORS['green'], WINDOW_WIDTH // 2, 250)
            self.draw_text("Rakip lobiden katilabilir!", self.font_medium, COLORS['white'], WINDOW_WIDTH // 2, 310)
        
        dots = "." * (int(time.time() * 2) % 4)
        self.draw_text(f"Bekleniyor{dots}", self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 380)
        
        self.buttons = []
        self.buttons.append(('BACK', self.draw_button("Iptal", WINDOW_WIDTH // 2 - 75, 450, 150, 45)))
    
    def draw_leaderboard(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("LIDERLIK TABLOSU", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 50)
        
        try:
            response = requests.get(f"{SERVER_URL}/leaderboard", timeout=3)
            if response.status_code == 200:
                players = response.json()
                y = 120
                for i, p in enumerate(players[:10]):
                    prefix = ["1.", "2.", "3."][i] if i < 3 else f"{i+1}."
                    text = f"{prefix} {p['username']} - ELO: {p['rating']} (W:{p['wins']} L:{p['losses']})"
                    color = COLORS['yellow'] if i < 3 else COLORS['white']
                    self.draw_text(text, self.font_small, color, WINDOW_WIDTH // 2, y)
                    y += 35
            else:
                self.draw_text("Veri alinamadi", self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 200)
        except:
            self.draw_text("Sunucuya baglanilamadi", self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 200)
        
        self.buttons = []
        self.buttons.append(('BACK', self.draw_button("Geri", WINDOW_WIDTH // 2 - 75, WINDOW_HEIGHT - 80, 150, 45)))
    
    def draw_game(self):
        self.screen.fill(COLORS['bg'])
        
        if self.is_spectator:
            title = "CANLI YAYIN"
        elif self.state == "PLAYING_AI":
            title = "AI'ya Karsi"
        else:
            title = "Online Mac"
        self.draw_text(title, self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 30)
        
        self.draw_board()
        back_btn = self.draw_info_panel()
        
        self.buttons = [('BACK', back_btn)]
        
        pygame.draw.rect(self.screen, COLORS['panel'], (0, WINDOW_HEIGHT - 50, WINDOW_WIDTH, 50))
        self.draw_text(self.status_text, self.font_small, COLORS['white'], WINDOW_WIDTH // 2, WINDOW_HEIGHT - 25)
    
    # =========================================================================
    # NETWORK / LOBBY
    # =========================================================================
    
    def refresh_active_games(self):
        try:
            response = requests.get(f"{SERVER_URL}/active_games", timeout=2)
            if response.status_code == 200:
                self.active_games = response.json()
        except:
            pass
    
    # =========================================================================
    # AUTH
    # =========================================================================
    
    def do_login(self):
        username = self.input_fields['username']['value'].strip()
        password = self.input_fields['password']['value']
        
        if not username or not password:
            self.set_status("Kullanici adi ve sifre gerekli!")
            return
        
        try:
            response = requests.post(f"{SERVER_URL}/login",
                                    json={'username': username, 'password': password},
                                    timeout=5)
            if response.status_code == 200:
                data = response.json()
                user = data['user']
                self.username = user['username']
                self.user_id = user['user_id']
                self.user_elo = user.get('rating', 1200)
                self.is_guest = False
                self.state = "MENU"
                self.set_status(f"Hosgeldin {self.username}!")
                self.clear_inputs()
            else:
                self.set_status("Yanlis kullanici adi veya sifre!")
        except requests.exceptions.ConnectionError:
            self.set_status("Sunucuya baglanilamadi!")
        except Exception as e:
            self.set_status(f"Hata: {str(e)[:30]}")
    
    def do_register(self):
        username = self.input_fields['username']['value'].strip()
        password = self.input_fields['password']['value']
        
        if not username or not password:
            self.set_status("Kullanici adi ve sifre gerekli!")
            return
        
        if len(username) < 3:
            self.set_status("Kullanici adi en az 3 karakter olmali!")
            return
        
        if len(password) < 3:
            self.set_status("Sifre en az 3 karakter olmali!")
            return
        
        try:
            response = requests.post(f"{SERVER_URL}/signup",
                                    json={'username': username, 'password': password},
                                    timeout=5)
            if response.status_code == 201:
                self.username = username
                self.user_id = response.json().get('user_id')
                self.user_elo = 1200
                self.is_guest = False
                self.state = "MENU"
                self.set_status(f"Kayit basarili! Hosgeldin {username}!")
                self.clear_inputs()
            elif response.status_code == 409:
                self.set_status("Bu kullanici adi zaten alinmis!")
            else:
                self.set_status("Kayit basarisiz!")
        except requests.exceptions.ConnectionError:
            self.set_status("Sunucuya baglanilamadi!")
        except Exception as e:
            self.set_status(f"Hata: {str(e)[:30]}")
    
    def guest_login(self):
        self.username = f"Misafir_{int(time.time()) % 10000}"
        self.user_id = None
        self.user_elo = 1200
        self.is_guest = True
        self.state = "MENU"
        self.set_status("")
        self.clear_inputs()
    
    def logout(self):
        self.username = ""
        self.user_id = None
        self.user_elo = 1200
        self.is_guest = False
        self.state = "LOGIN"
        self.set_status("")
        self.clear_inputs()
    
    def clear_inputs(self):
        self.input_fields['username']['value'] = ''
        self.input_fields['password']['value'] = ''
        self.input_fields['username']['active'] = False
        self.input_fields['password']['active'] = False
        self.active_input = None
    
    # =========================================================================
    # GAME LOGIC
    # =========================================================================
    
    def start_ai_game(self, depth):
        # STOP ANY RUNNING AI THREAD
        self.ai_should_stop = True
        time.sleep(0.1)
        
        self.game = ConnectFourGame()
        self.ai = AIEngine(PLAYER2_PIECE, depth=depth)
        self.my_piece = PLAYER1_PIECE
        self.state = "PLAYING_AI"
        self.is_spectator = False
        self.ai_should_stop = False
        self.ai_thinking = False
        self.pending_ai_move = None
        self.status_text = "Senin siran! Bir sutun sec."
    
    def create_online_game(self):
        # STOP AI
        self.ai_should_stop = True
        self.ai = None
        self.pending_ai_move = None
        
        self.set_status("Oda olusturuluyor...")
        if self.network.create_game(self.username):
            pass
        else:
            self.set_status("Sunucuya baglanilamadi!")
    
    def join_online_game(self, room_id):
        # STOP AI
        self.ai_should_stop = True
        self.ai = None
        self.pending_ai_move = None
        
        self.set_status("Odaya katiliniyor...")
        self.room_id = room_id.upper()
        self.is_spectator = False
        if not self.network.join_game(self.room_id, self.username):
            self.set_status("Odaya katilamadi!")
    
    def spectate_game(self, room_id):
        # STOP AI
        self.ai_should_stop = True
        self.ai = None
        self.pending_ai_move = None
        
        self.set_status("Mac izleniyor...")
        self.room_id = room_id.upper()
        self.is_spectator = True
        if self.network.join_game(self.room_id, self.username):
            self.state = "SPECTATING"
        else:
            self.set_status("Maca baglanilamadi!")
    
    def on_game_created(self, data):
        self.room_id = data['room_id']
        self.my_piece = data['player_piece']
        self.state = "WAITING"
        self.is_spectator = False
        self.set_status(f"Oda olusturuldu: {self.room_id}")
    
    def on_game_joined(self, data):
        self.room_id = data['room_id']
        self.my_piece = data.get('player_piece', 0)
        role = data.get('role', 'player')
        
        if role == 'spectator':
            self.is_spectator = True
            self.state = "SPECTATING"
            if 'current_state' in data:
                self.game.from_dict(data['current_state'])
            p1_info = data.get('p1_info', {})
            self.opponent_name = p1_info.get('username', 'P1')
            self.opponent_elo = p1_info.get('rating', 1200)
            self.set_status("Maci izliyorsunuz")
        else:
            self.is_spectator = False
            opponent_info = data.get('opponent_info', {})
            self.opponent_name = opponent_info.get('username', 'Rakip')
            self.opponent_elo = opponent_info.get('rating', 1200)
            self.set_status(f"Oyuna katildin! Rakip: {self.opponent_name}")
    
    def on_game_start(self, data):
        self.game = ConnectFourGame()
        self.state = "PLAYING_ONLINE"
        self.is_spectator = False
        
        # ENSURE AI IS OFF
        self.ai = None
        self.ai_should_stop = True
        self.pending_ai_move = None
        
        if self.my_piece == PLAYER1_PIECE:
            opp_info = data.get('p2_info', {})
            self.opponent_name = data.get('opponent_name', opp_info.get('username', 'Rakip'))
            self.opponent_elo = opp_info.get('rating', 1200)
        else:
            opp_info = data.get('p1_info', {})
            self.opponent_name = data.get('opponent_name', opp_info.get('username', 'Rakip'))
            self.opponent_elo = opp_info.get('rating', 1200)
        
        if self.game.current_player == self.my_piece:
            self.set_status("Oyun basladi! Senin siran.")
        else:
            self.set_status("Oyun basladi! Rakibin sirasi.")
    
    def on_move_made(self, data):
        col = data.get('col')
        if col is not None:
            piece = self.game.current_player
            row = self.game.heights[col] - col * (ROWS + 1)
            self.animate_drop(col, row, piece, lambda: self.apply_network_move(data))
    
    def apply_network_move(self, data):
        self.game.from_dict(data)
        
        if self.game.game_over:
            self.handle_game_over()
        elif self.is_spectator:
            self.set_status("Mac devam ediyor...")
        elif self.game.current_player == self.my_piece:
            self.set_status("Senin siran!")
        else:
            self.set_status("Rakibin sirasi...")
    
    def on_game_over_network(self, data):
        winner = data.get('winner')
        
        if self.is_spectator:
            if winner == PLAYER1_PIECE:
                self.set_status("Kirmizi kazandi!")
            elif winner == PLAYER2_PIECE:
                self.set_status("Sari kazandi!")
            else:
                self.set_status("Berabere!")
        else:
            if winner == self.my_piece:
                self.set_status("Kazandin! Tebrikler!")
            elif winner is None:
                self.set_status("Berabere!")
            else:
                self.set_status("Kaybettin. Bir dahaki sefere!")
    
    def on_elo_update(self, data):
        new_elo = data.get('new_elo', self.user_elo)
        change = data.get('change', 0)
        self.user_elo = new_elo
        
        if change > 0:
            self.set_status(f"Kazandin! ELO +{change} ({new_elo})")
        elif change < 0:
            self.set_status(f"Kaybettin. ELO {change} ({new_elo})")
    
    def on_opponent_disconnected(self):
        self.set_status("Rakip baglantisi koptu!")
    
    def handle_click(self, col):
        if self.animating or self.game.game_over or self.is_spectator:
            return
        
        # STRICT STATE CHECK
        if self.state == "PLAYING_AI":
            if self.game.current_player != PLAYER1_PIECE or self.ai_thinking:
                return
        elif self.state == "PLAYING_ONLINE":
            if self.game.current_player != self.my_piece:
                self.set_status("Rakibin sirasi!")
                return
        else:
            return
        
        if not self.game.is_valid_location(col):
            return
        
        row = self.game.heights[col] - col * (ROWS + 1)
        piece = self.game.current_player
        self.animate_drop(col, row, piece, lambda: self.finish_move(col))
    
    def animate_drop(self, col, row, piece, callback):
        self.animating = True
        self.anim_col = col
        self.anim_row = row
        self.anim_piece = piece
        self.anim_y = 50
        self.anim_target_y = 80 + (ROWS - 1 - row) * CELL_SIZE + CELL_SIZE // 2
        self.anim_callback = callback
    
    def update_animation(self):
        if not self.animating:
            return
        
        self.anim_y += 18
        
        if self.anim_y >= self.anim_target_y:
            self.anim_y = self.anim_target_y
            self.animating = False
            if self.anim_callback:
                self.anim_callback()
    
    def finish_move(self, col):
        if not self.game.make_move(col):
            return
        
        if self.game.game_over:
            self.handle_game_over()
            return
        
        # ONLY SEND MOVE FOR ONLINE - NOT AI!
        if self.state == "PLAYING_ONLINE":
            self.network.send_move(col)
            self.set_status("Rakibin sirasi...")
            return  # DON'T TRIGGER AI!
        
        # AI MOVE - ONLY IN AI MODE
        if self.state == "PLAYING_AI" and self.game.current_player == PLAYER2_PIECE:
            self.set_status("AI dusunuyor...")
            self.ai_thinking = True
            self.ai_should_stop = False
            threading.Thread(target=self.ai_move, daemon=True).start()
    
    def ai_move(self):
        """AI thread - with stop flag check"""
        time.sleep(0.3)
        
        # CHECK IF WE SHOULD STOP
        if self.ai_should_stop or self.state != "PLAYING_AI":
            self.ai_thinking = False
            return
        
        col = self.ai.find_best_move(self.game)
        self.ai_thinking = False
        
        # DOUBLE CHECK BEFORE QUEUING
        if col is not None and not self.game.game_over and self.state == "PLAYING_AI" and not self.ai_should_stop:
            self.pending_ai_move = col
    
    def execute_ai_move(self, col):
        # TRIPLE CHECK
        if self.state != "PLAYING_AI" or self.ai_should_stop:
            self.pending_ai_move = None
            return
        if self.game.game_over or not self.game.is_valid_location(col):
            return
        
        row = self.game.heights[col] - col * (ROWS + 1)
        self.animate_drop(col, row, PLAYER2_PIECE, lambda: self.finish_ai_move(col))
    
    def finish_ai_move(self, col):
        if self.state != "PLAYING_AI" or self.ai_should_stop:
            return
        if not self.game.make_move(col):
            return
        
        if self.game.game_over:
            self.handle_game_over()
        else:
            self.set_status("Senin siran!")
    
    def handle_game_over(self):
        if self.game.winner == PLAYER1_PIECE:
            if self.state == "PLAYING_AI":
                self.set_status("Kazandin! Tebrikler!")
            elif self.is_spectator:
                self.set_status("Kirmizi kazandi!")
            else:
                winner_name = self.username if self.my_piece == PLAYER1_PIECE else self.opponent_name
                self.set_status(f"{winner_name} kazandi!")
        elif self.game.winner == PLAYER2_PIECE:
            if self.state == "PLAYING_AI":
                self.set_status("AI kazandi. Tekrar dene!")
            elif self.is_spectator:
                self.set_status("Sari kazandi!")
            else:
                winner_name = self.username if self.my_piece == PLAYER2_PIECE else self.opponent_name
                self.set_status(f"{winner_name} kazandi!")
        else:
            self.set_status("Berabere!")
    
    def set_status(self, text):
        self.status_text = text
    
    def reset_to_menu(self):
        """Clean reset to menu"""
        self.ai_should_stop = True
        self.ai = None
        self.pending_ai_move = None
        self.ai_thinking = False
        self.network.disconnect()
        self.network = NetworkManager(self)
        self.room_id = None
        self.is_spectator = False
        self.game = ConnectFourGame()
        self.state = "MENU"
    
    # =========================================================================
    # EVENT HANDLING
    # =========================================================================
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.ai_should_stop = True
                self.network.disconnect()
                pygame.quit()
                sys.exit()
            
            elif event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                if self.state in ["PLAYING_AI", "PLAYING_ONLINE"]:
                    if 20 <= mx <= 20 + BOARD_WIDTH and 80 <= my <= 80 + BOARD_HEIGHT:
                        self.hover_col = (mx - 20) // CELL_SIZE
                    else:
                        self.hover_col = -1
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                
                # Check input fields (login screen)
                if self.state == "LOGIN":
                    for field_name, field in self.input_fields.items():
                        if field['rect'] and field['rect'].collidepoint(mx, my):
                            # Deactivate all, activate clicked
                            for f in self.input_fields.values():
                                f['active'] = False
                            field['active'] = True
                            self.active_input = field_name
                            return
                
                # Check buttons
                for btn_id, rect in self.buttons:
                    if rect.collidepoint(mx, my):
                        self.handle_button_click(btn_id)
                        return
                
                # Check board click
                if self.state in ["PLAYING_AI", "PLAYING_ONLINE"]:
                    if 20 <= mx <= 20 + BOARD_WIDTH and 80 <= my <= 80 + BOARD_HEIGHT:
                        col = (mx - 20) // CELL_SIZE
                        self.handle_click(col)
            
            elif event.type == pygame.KEYDOWN:
                # Handle input for login screen
                if self.state == "LOGIN" and self.active_input:
                    field = self.input_fields[self.active_input]
                    if event.key == pygame.K_RETURN:
                        # Tab to next field or submit
                        if self.active_input == 'username':
                            self.input_fields['username']['active'] = False
                            self.input_fields['password']['active'] = True
                            self.active_input = 'password'
                        else:
                            self.do_login()
                    elif event.key == pygame.K_TAB:
                        # Switch fields
                        if self.active_input == 'username':
                            self.input_fields['username']['active'] = False
                            self.input_fields['password']['active'] = True
                            self.active_input = 'password'
                        else:
                            self.input_fields['password']['active'] = False
                            self.input_fields['username']['active'] = True
                            self.active_input = 'username'
                    elif event.key == pygame.K_BACKSPACE:
                        field['value'] = field['value'][:-1]
                    elif event.key == pygame.K_ESCAPE:
                        field['active'] = False
                        self.active_input = None
                    else:
                        if len(field['value']) < 20 and event.unicode.isprintable():
                            field['value'] += event.unicode
    
    def handle_button_click(self, btn_id):
        if btn_id == 'DO_LOGIN':
            self.do_login()
        
        elif btn_id == 'DO_REGISTER':
            self.do_register()
        
        elif btn_id == 'GUEST':
            self.guest_login()
        
        elif btn_id == 'AI':
            self.state = "AI_SELECT"
        
        elif btn_id.startswith('AI_'):
            depth = int(btn_id.split('_')[1])
            self.start_ai_game(depth)
        
        elif btn_id == 'LOBBY':
            self.state = "LOBBY"
            self.refresh_active_games()
            self.last_lobby_refresh = time.time()
        
        elif btn_id == 'CREATE':
            self.create_online_game()
        
        elif btn_id.startswith('JOIN_'):
            room_id = btn_id.replace('JOIN_', '')
            self.join_online_game(room_id)
        
        elif btn_id.startswith('SPECTATE_'):
            room_id = btn_id.replace('SPECTATE_', '')
            self.spectate_game(room_id)
        
        elif btn_id == 'REFRESH':
            self.refresh_active_games()
            self.set_status("Lobi yenilendi")
        
        elif btn_id == 'LEADERBOARD':
            self.state = "LEADERBOARD"
        
        elif btn_id == 'LOGOUT':
            self.logout()
        
        elif btn_id in ['BACK']:
            self.reset_to_menu()
        
        elif btn_id == 'QUIT':
            self.ai_should_stop = True
            self.network.disconnect()
            pygame.quit()
            sys.exit()
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
    def run(self):
        while True:
            self.handle_events()
            self.update_animation()
            
            # AI move - STRICT CHECK
            if self.pending_ai_move is not None:
                if self.state == "PLAYING_AI" and not self.ai_should_stop:
                    col = self.pending_ai_move
                    self.pending_ai_move = None
                    self.execute_ai_move(col)
                else:
                    self.pending_ai_move = None
            
            # Draw
            if self.state == "LOGIN":
                self.draw_login()
            elif self.state == "MENU":
                self.draw_menu()
            elif self.state == "AI_SELECT":
                self.draw_ai_select()
            elif self.state == "LOBBY":
                self.draw_lobby()
            elif self.state == "WAITING":
                self.draw_waiting()
            elif self.state == "LEADERBOARD":
                self.draw_leaderboard()
            elif self.state in ["PLAYING_AI", "PLAYING_ONLINE", "SPECTATING"]:
                self.draw_game()
            
            pygame.display.flip()
            self.clock.tick(60)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    app = ConnectFourGUI()
    app.run()