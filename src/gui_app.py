# =============================================================================
# MODULE: gui_app.py
# Connect Four Pro - Pygame GUI Client
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
WINDOW_WIDTH = BOARD_WIDTH + 300
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
        
        # Game state
        self.state = "MENU"
        self.game = ConnectFourGame()
        self.ai = None
        self.ai_thinking = False
        
        # Player info
        self.username = "Misafir"
        self.user_id = None
        self.opponent_name = "Rakip"
        
        # Network
        self.network = NetworkManager(self)
        self.my_piece = PLAYER1_PIECE
        self.room_id = None
        
        # UI state
        self.status_text = "Hosgeldiniz!"
        self.hover_col = -1
        self.input_text = ""
        self.input_active = False
        self.input_label = ""
        self.buttons = []
        
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
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surface, rect)
    
    def draw_button(self, text, x, y, w, h, hover=False):
        color = COLORS['button_hover'] if hover else COLORS['button']
        pygame.draw.rect(self.screen, color, (x, y, w, h), border_radius=8)
        self.draw_text(text, self.font_medium, COLORS['white'], x + w//2, y + h//2)
        return pygame.Rect(x, y, w, h)
    
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
        if self.hover_col >= 0 and not self.animating and not self.game.game_over:
            if self.state in ["PLAYING_AI", "PLAYING_ONLINE"]:
                can_play = (self.state == "PLAYING_AI" and self.game.current_player == PLAYER1_PIECE and not self.ai_thinking) or \
                          (self.state == "PLAYING_ONLINE" and self.game.current_player == self.my_piece)
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
                        (panel_x, panel_y, 230, 300), border_radius=10)
        
        # Title
        self.draw_text("OYUN BILGISI", self.font_medium, COLORS['white'], panel_x + 115, panel_y + 30)
        
        # Player 1
        pygame.draw.circle(self.screen, COLORS['red'], (panel_x + 30, panel_y + 80), 15)
        if self.state == "PLAYING_AI":
            p1_name = self.username
        else:
            p1_name = self.username if self.my_piece == PLAYER1_PIECE else self.opponent_name
        self.draw_text(p1_name[:12], self.font_small, COLORS['white'], panel_x + 55, panel_y + 80, center=False)
        if self.game.current_player == PLAYER1_PIECE and not self.game.game_over:
            self.draw_text("< SIRA", self.font_small, COLORS['green'], panel_x + 180, panel_y + 80)
        
        # Player 2
        pygame.draw.circle(self.screen, COLORS['yellow'], (panel_x + 30, panel_y + 120), 15)
        if self.state == "PLAYING_AI":
            p2_name = f"AI (D{self.ai.depth if self.ai else '?'})"
        else:
            p2_name = self.opponent_name if self.my_piece == PLAYER1_PIECE else self.username
        self.draw_text(p2_name[:12], self.font_small, COLORS['white'], panel_x + 55, panel_y + 120, center=False)
        if self.game.current_player == PLAYER2_PIECE and not self.game.game_over:
            self.draw_text("< SIRA", self.font_small, COLORS['green'], panel_x + 180, panel_y + 120)
        
        # Room ID (for online)
        if self.state in ["WAITING", "PLAYING_ONLINE"] and self.room_id:
            self.draw_text(f"Oda: {self.room_id}", self.font_medium, COLORS['hover'], panel_x + 115, panel_y + 180)
        
        # Back button
        return self.draw_button("Menu", panel_x + 40, panel_y + 240, 150, 40)
    
    # =========================================================================
    # SCREEN METHODS
    # =========================================================================
    
    def draw_menu(self):
        self.screen.fill(COLORS['bg'])
        
        # Title
        self.draw_text("CONNECT FOUR PRO", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 80)
        self.draw_text(f"Hos geldin, {self.username}!", self.font_small, COLORS['gray'], WINDOW_WIDTH // 2, 120)
        
        # Buttons
        btn_w, btn_h = 250, 50
        center_x = WINDOW_WIDTH // 2 - btn_w // 2
        
        self.buttons = []
        self.buttons.append(('AI', self.draw_button("Yapay Zekaya Karsi", center_x, 180, btn_w, btn_h)))
        self.buttons.append(('ONLINE', self.draw_button("Online Oyna", center_x, 250, btn_w, btn_h)))
        self.buttons.append(('LEADERBOARD', self.draw_button("Liderlik Tablosu", center_x, 320, btn_w, btn_h)))
        self.buttons.append(('LOGIN', self.draw_button("Giris Yap", center_x, 390, btn_w, btn_h)))
        self.buttons.append(('QUIT', self.draw_button("Cikis", center_x, 460, btn_w, btn_h)))
        
        # Status
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
    
    def draw_online_menu(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("ONLINE OYUN", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 80)
        
        btn_w, btn_h = 250, 50
        center_x = WINDOW_WIDTH // 2 - btn_w // 2
        
        self.buttons = []
        self.buttons.append(('CREATE', self.draw_button("Yeni Oda Olustur", center_x, 180, btn_w, btn_h)))
        self.buttons.append(('JOIN', self.draw_button("Odaya Katil", center_x, 250, btn_w, btn_h)))
        self.buttons.append(('BACK', self.draw_button("Geri", center_x, 350, btn_w, btn_h)))
        
        self.draw_text(self.status_text, self.font_small, COLORS['gray'], WINDOW_WIDTH // 2, WINDOW_HEIGHT - 30)
    
    def draw_waiting(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("RAKIP BEKLENIYOR", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 150)
        
        if self.room_id:
            self.draw_text(f"Oda Kodu: {self.room_id}", self.font_large, COLORS['green'], WINDOW_WIDTH // 2, 250)
            self.draw_text("Bu kodu rakibinle paylas!", self.font_medium, COLORS['white'], WINDOW_WIDTH // 2, 310)
        
        # Animated dots
        dots = "." * (int(time.time() * 2) % 4)
        self.draw_text(f"Bekleniyor{dots}", self.font_medium, COLORS['gray'], WINDOW_WIDTH // 2, 380)
        
        self.buttons = []
        self.buttons.append(('BACK', self.draw_button("Iptal", WINDOW_WIDTH // 2 - 75, 450, 150, 45)))
    
    def draw_input_dialog(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text(self.input_label, self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 150)
        
        # Input box
        box_w, box_h = 300, 50
        box_x = WINDOW_WIDTH // 2 - box_w // 2
        box_y = 250
        
        color = COLORS['hover'] if self.input_active else COLORS['panel']
        pygame.draw.rect(self.screen, color, (box_x, box_y, box_w, box_h), border_radius=8)
        pygame.draw.rect(self.screen, COLORS['white'], (box_x, box_y, box_w, box_h), 2, border_radius=8)
        
        # Input text
        display_text = self.input_text if self.input_text else "..."
        self.draw_text(display_text, self.font_medium, COLORS['white'], WINDOW_WIDTH // 2, box_y + box_h // 2)
        
        self.buttons = []
        self.buttons.append(('SUBMIT', self.draw_button("Tamam", WINDOW_WIDTH // 2 - 130, 350, 120, 45)))
        self.buttons.append(('CANCEL', self.draw_button("Iptal", WINDOW_WIDTH // 2 + 10, 350, 120, 45)))
        
        self.input_active = True
    
    def draw_leaderboard(self):
        self.screen.fill(COLORS['bg'])
        self.draw_text("LIDERLIK TABLOSU", self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 50)
        
        try:
            response = requests.get(f"{SERVER_URL}/leaderboard", timeout=3)
            if response.status_code == 200:
                players = response.json()
                y = 120
                for i, p in enumerate(players[:10]):
                    text = f"{i+1}. {p['username']} - ELO: {p['rating']} (W:{p['wins']} L:{p['losses']})"
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
        
        # Header
        title = "AI'ya Karsi" if self.state == "PLAYING_AI" else "Online Oyun"
        self.draw_text(title, self.font_large, COLORS['red'], WINDOW_WIDTH // 2, 30)
        
        # Board and info
        self.draw_board()
        back_btn = self.draw_info_panel()
        
        self.buttons = [('BACK', back_btn)]
        
        # Status bar
        pygame.draw.rect(self.screen, COLORS['panel'], (0, WINDOW_HEIGHT - 50, WINDOW_WIDTH, 50))
        self.draw_text(self.status_text, self.font_small, COLORS['white'], WINDOW_WIDTH // 2, WINDOW_HEIGHT - 25)
    
    # =========================================================================
    # GAME LOGIC
    # =========================================================================
    
    def start_ai_game(self, depth):
        self.game = ConnectFourGame()
        self.ai = AIEngine(PLAYER2_PIECE, depth=depth)
        self.my_piece = PLAYER1_PIECE
        self.state = "PLAYING_AI"
        self.status_text = "Senin siran! Bir sutun sec."
    
    def create_online_game(self):
        self.set_status("Oda olusturuluyor...")
        if self.network.create_game(self.username):
            pass  # Wait for game_created event
        else:
            self.set_status("Sunucuya baglanilamadi!")
    
    def join_online_game(self, room_id):
        self.set_status("Odaya katiliniyor...")
        self.room_id = room_id.upper()
        if not self.network.join_game(self.room_id, self.username):
            self.set_status("Odaya katilamadi!")
    
    def on_game_created(self, data):
        self.room_id = data['room_id']
        self.my_piece = data['player_piece']
        self.state = "WAITING"
        self.set_status(f"Oda olusturuldu: {self.room_id}")
    
    def on_game_joined(self, data):
        self.room_id = data['room_id']
        self.my_piece = data['player_piece']
        role = data.get('role', 'player')
        
        if role == 'spectator':
            self.set_status("Izleyici olarak katildin")
            if 'current_state' in data:
                self.game.from_dict(data['current_state'])
            self.state = "PLAYING_ONLINE"
        else:
            opponent_info = data.get('opponent_info', {})
            self.opponent_name = opponent_info.get('username', 'Rakip')
            self.set_status(f"Oyuna katildin! Rakip: {self.opponent_name}")
    
    def on_game_start(self, data):
        self.game = ConnectFourGame()
        self.state = "PLAYING_ONLINE"
        
        # Get opponent name
        if self.my_piece == PLAYER1_PIECE:
            self.opponent_name = data.get('opponent_name', data.get('p2_info', {}).get('username', 'Rakip'))
        else:
            self.opponent_name = data.get('opponent_name', data.get('p1_info', {}).get('username', 'Rakip'))
        
        if self.game.current_player == self.my_piece:
            self.set_status("Oyun basladi! Senin siran.")
        else:
            self.set_status("Oyun basladi! Rakibin sirasi.")
    
    def on_move_made(self, data):
        col = data.get('col')
        if col is not None:
            # Only animate if it's opponent's move
            if self.game.current_player != self.my_piece:
                row = self.game.heights[col] - col * (ROWS + 1)
                piece = self.game.current_player
                self.animate_drop(col, row, piece, lambda: self.apply_network_move(data))
            else:
                self.apply_network_move(data)
    
    def apply_network_move(self, data):
        self.game.from_dict(data)
        
        if self.game.game_over:
            self.handle_game_over()
        elif self.game.current_player == self.my_piece:
            self.set_status("Senin siran!")
        else:
            self.set_status("Rakibin sirasi...")
    
    def on_game_over_network(self, data):
        winner = data.get('winner')
        if winner == self.my_piece:
            self.set_status("Kazandin! Tebrikler!")
        elif winner is None:
            self.set_status("Berabere!")
        else:
            self.set_status("Kaybettin. Bir dahaki sefere!")
    
    def on_opponent_disconnected(self):
        self.set_status("Rakip baglantisi koptu!")
    
    def handle_click(self, col):
        if self.animating or self.game.game_over:
            return
        
        # Check if it's player's turn
        if self.state == "PLAYING_AI":
            if self.game.current_player != PLAYER1_PIECE or self.ai_thinking:
                return
        elif self.state == "PLAYING_ONLINE":
            if self.game.current_player != self.my_piece:
                self.set_status("Rakibin sirasi!")
                return
        
        if not self.game.is_valid_location(col):
            return
        
        # Get target row
        row = self.game.heights[col] - col * (ROWS + 1)
        piece = self.game.current_player
        
        # Animate and make move
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
        
        # Drop with acceleration
        self.anim_y += 15
        
        if self.anim_y >= self.anim_target_y:
            self.anim_y = self.anim_target_y
            self.animating = False
            if self.anim_callback:
                self.anim_callback()
    
    def finish_move(self, col):
        if not self.game.make_move(col):
            return
        
        # Check game over
        if self.game.game_over:
            self.handle_game_over()
            return
        
        # Send move for online
        if self.state == "PLAYING_ONLINE":
            self.network.send_move(col)
            self.set_status("Rakibin sirasi...")
        
        # AI move
        if self.state == "PLAYING_AI" and self.game.current_player == PLAYER2_PIECE:
            self.set_status("AI dusunuyor...")
            self.ai_thinking = True
            threading.Thread(target=self.ai_move, daemon=True).start()
    
    def ai_move(self):
        time.sleep(0.3)
        col = self.ai.find_best_move(self.game)
        self.ai_thinking = False
        
        if col is not None and not self.game.game_over:
            self.pending_ai_move = col
    
    def execute_ai_move(self, col):
        if self.game.game_over or not self.game.is_valid_location(col):
            return
        
        row = self.game.heights[col] - col * (ROWS + 1)
        self.animate_drop(col, row, PLAYER2_PIECE, lambda: self.finish_ai_move(col))
    
    def finish_ai_move(self, col):
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
            else:
                winner_name = self.username if self.my_piece == PLAYER1_PIECE else self.opponent_name
                self.set_status(f"{winner_name} kazandi!")
        elif self.game.winner == PLAYER2_PIECE:
            if self.state == "PLAYING_AI":
                self.set_status("AI kazandi. Tekrar dene!")
            else:
                winner_name = self.username if self.my_piece == PLAYER2_PIECE else self.opponent_name
                self.set_status(f"{winner_name} kazandi!")
        else:
            self.set_status("Berabere!")
    
    def set_status(self, text):
        self.status_text = text
    
    # =========================================================================
    # EVENT HANDLING
    # =========================================================================
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
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
                if self.state in ["INPUT_JOIN", "INPUT_LOGIN_USER", "INPUT_LOGIN_PASS"]:
                    if event.key == pygame.K_RETURN:
                        self.handle_button_click('SUBMIT')
                    elif event.key == pygame.K_ESCAPE:
                        self.handle_button_click('CANCEL')
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    else:
                        if len(self.input_text) < 20 and event.unicode.isprintable():
                            self.input_text += event.unicode
    
    def handle_button_click(self, btn_id):
        if btn_id == 'AI':
            self.state = "AI_SELECT"
        
        elif btn_id.startswith('AI_'):
            depth = int(btn_id.split('_')[1])
            self.start_ai_game(depth)
        
        elif btn_id == 'ONLINE':
            self.state = "ONLINE_MENU"
        
        elif btn_id == 'CREATE':
            self.create_online_game()
        
        elif btn_id == 'JOIN':
            self.state = "INPUT_JOIN"
            self.input_label = "ODA KODUNU GIR"
            self.input_text = ""
        
        elif btn_id == 'LEADERBOARD':
            self.state = "LEADERBOARD"
        
        elif btn_id == 'LOGIN':
            self.state = "INPUT_LOGIN_USER"
            self.input_label = "KULLANICI ADI"
            self.input_text = ""
        
        elif btn_id == 'SUBMIT':
            if self.state == "INPUT_JOIN":
                if self.input_text:
                    self.join_online_game(self.input_text)
                    self.state = "WAITING"
            elif self.state == "INPUT_LOGIN_USER":
                self.temp_username = self.input_text
                self.state = "INPUT_LOGIN_PASS"
                self.input_label = "SIFRE"
                self.input_text = ""
            elif self.state == "INPUT_LOGIN_PASS":
                self.try_login(self.temp_username, self.input_text)
        
        elif btn_id in ['CANCEL', 'BACK']:
            if self.state in ["PLAYING_AI", "PLAYING_ONLINE", "WAITING"]:
                self.network.disconnect()
                self.network = NetworkManager(self)
                self.room_id = None
            self.state = "MENU"
        
        elif btn_id == 'QUIT':
            self.network.disconnect()
            pygame.quit()
            sys.exit()
    
    def try_login(self, username, password):
        try:
            response = requests.post(f"{SERVER_URL}/login", 
                                    json={'username': username, 'password': password},
                                    timeout=3)
            if response.status_code == 200:
                data = response.json()
                self.username = data['user']['username']
                self.user_id = data['user']['user_id']
                self.set_status(f"Giris basarili! Hosgeldin {self.username}")
                self.state = "MENU"
            else:
                # Try to register
                reg_response = requests.post(f"{SERVER_URL}/signup",
                                            json={'username': username, 'password': password},
                                            timeout=3)
                if reg_response.status_code == 201:
                    self.username = username
                    self.set_status(f"Kayit basarili! Hosgeldin {username}")
                    self.state = "MENU"
                else:
                    self.set_status("Giris hatasi!")
                    self.state = "MENU"
        except Exception as e:
            self.set_status(f"Baglanti hatasi: {str(e)[:20]}")
            self.state = "MENU"
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
    def run(self):
        while True:
            self.handle_events()
            self.update_animation()
            
            # Check for pending AI move
            if self.pending_ai_move is not None:
                col = self.pending_ai_move
                self.pending_ai_move = None
                self.execute_ai_move(col)
            
            # Draw current state
            if self.state == "MENU":
                self.draw_menu()
            elif self.state == "AI_SELECT":
                self.draw_ai_select()
            elif self.state == "ONLINE_MENU":
                self.draw_online_menu()
            elif self.state == "WAITING":
                self.draw_waiting()
            elif self.state == "LEADERBOARD":
                self.draw_leaderboard()
            elif self.state.startswith("INPUT_"):
                self.draw_input_dialog()
            elif self.state in ["PLAYING_AI", "PLAYING_ONLINE"]:
                self.draw_game()
            
            pygame.display.flip()
            self.clock.tick(60)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    app = ConnectFourGUI()
    app.run()
