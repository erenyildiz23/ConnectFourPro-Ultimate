# =============================================================================
# MODÜL: gui_app.py
# =============================================================================
# GÜNCELLEME: Komut satırından sunucu URL'i alabilir
# Kullanım:
#   python gui_app.py                              # localhost:5000 (varsayılan)
#   python gui_app.py http://localhost:5000        # açık localhost
#   python gui_app.py https://abc123.ngrok-free.app # ngrok URL
# =============================================================================

import pygame
import sys
import threading
import socketio
import requests
import math
import time
from game_core import ConnectFourGame, ROWS, COLS, PLAYER1_PIECE, PLAYER2_PIECE
from ai_vs_human import AIEngine

# --- SABİTLER ---
BLUE=(20,50,180); BLACK=(15,15,20); RED=(220,40,40); YELLOW=(240,220,60)
WHITE=(240,240,240); GREEN=(40,200,40); GRAY=(100,100,100); ORANGE=(255, 165, 0)
SQUARESIZE=100
WIDTH=COLS*SQUARESIZE + 250 
HEIGHT=(ROWS+1)*SQUARESIZE
RADIUS=44

# --- SUNUCU URL AYARI ---
# Komut satırından parametre verilmişse onu kullan, yoksa localhost
if len(sys.argv) > 1:
    SERVER_URL = sys.argv[1]
    # URL formatı kontrolü
    if not SERVER_URL.startswith('http'):
        SERVER_URL = 'http://' + SERVER_URL
    print(f"[CONFIG] Uzak sunucuya bağlanılıyor: {SERVER_URL}")
else:
    SERVER_URL = 'http://localhost:5000'
    print(f"[CONFIG] Yerel sunucuya bağlanılıyor: {SERVER_URL}")

# --- UI YARDIMCILARI ---

class Button:
    def __init__(self, x, y, w, h, text, color, text_color=BLACK, font_size=24):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text; self.color = color; self.text_color = text_color
        self.font = pygame.font.SysFont("Arial", font_size, bold=True)
        self.room_id = None

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        pygame.draw.rect(screen, WHITE, self.rect, 2)
        txt = self.font.render(self.text, True, self.text_color)
        screen.blit(txt, (self.rect.centerx - txt.get_width()//2, self.rect.centery - txt.get_height()//2))

    def is_clicked(self, pos): return self.rect.collidepoint(pos)

class InputBox:
    def __init__(self, x, y, w, h, text='', is_password=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = GRAY; self.text = text; self.is_password = is_password
        self.active = False
        self.font = pygame.font.SysFont("Arial", 32)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            self.color = WHITE if self.active else GRAY
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            else: self.text += event.unicode

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect, 0 if self.active else 2)
        disp = "*" * len(self.text) if self.is_password else self.text
        screen.blit(self.font.render(disp, True, BLACK if self.active else WHITE), (self.rect.x+5, self.rect.y+5))

# --- AĞ İSTEMCİSİ ---

class NetworkClient:
    def __init__(self, gui):
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=5, reconnection_delay=1)
        self.gui = gui; self.connected = False; self.user_data = None
        
        self.sio.on('connect', self._on_connect)
        self.sio.on('disconnect', self._on_disconnect)
        self.sio.on('game_created', self.on_created)
        self.sio.on('game_joined', self.on_joined)
        self.sio.on('game_start', self.on_start)
        self.sio.on('move_made', self.on_move)
        self.sio.on('error', lambda d: setattr(self.gui, 'status_message', d['msg']))

    def _on_connect(self):
        self.connected = True
        print(f"[SOCKET] Bağlantı kuruldu: {SERVER_URL}")
        
    def _on_disconnect(self):
        self.connected = False
        print("[SOCKET] Bağlantı kesildi")

    def login(self, u, p):
        try:
            r = requests.post(f"{SERVER_URL}/login", json={'username':u, 'password':p}, timeout=10)
            if r.status_code==200: self.user_data=r.json()['user']; return True
            self.gui.status_message = r.json().get('error', 'Giriş başarısız')
        except requests.exceptions.Timeout:
            self.gui.status_message = "Sunucu yanıt vermiyor"
        except requests.exceptions.ConnectionError:
            self.gui.status_message = "Sunucuya bağlanılamıyor"
        except Exception as e: 
            self.gui.status_message = f"Hata: {str(e)[:30]}"
        return False

    def register(self, u, p):
        try:
            r = requests.post(f"{SERVER_URL}/signup", json={'username':u, 'password':p}, timeout=10)
            if r.status_code==201: self.gui.status_message="Hesap oluşturuldu!"; return True
            self.gui.status_message = r.json().get('error', 'Kayıt başarısız')
        except requests.exceptions.Timeout:
            self.gui.status_message = "Sunucu yanıt vermiyor"
        except requests.exceptions.ConnectionError:
            self.gui.status_message = "Sunucuya bağlanılamıyor"
        except Exception as e: 
            self.gui.status_message = f"Hata: {str(e)[:30]}"
        return False

    def get_leaderboard(self):
        try: return requests.get(f"{SERVER_URL}/leaderboard", timeout=10).json()
        except: return []

    def get_active_games(self):
        try:
            r = requests.get(f"{SERVER_URL}/active_games", timeout=10)
            if r.status_code == 200: return r.json()
        except: pass
        return []

    def connect_socket(self): 
        if not self.connected: 
            try: 
                print(f"[SOCKET] Bağlanılıyor: {SERVER_URL}")
                self.sio.connect(SERVER_URL, transports=['websocket', 'polling'], wait_timeout=10)
            except Exception as e:
                print(f"[SOCKET] Bağlantı hatası: {e}")
                self.gui.status_message = "Socket bağlantısı başarısız"

    # Socket Callbacks
    def on_created(self, d): 
        self.gui.room_id=d['room_id']; self.gui.my_online_piece=d['player_piece']
        self.gui.status_message=f"Oda: {d['room_id']}"
        self.gui.start_online_game(False) 
        
    def on_joined(self, d):
        self.gui.room_id=d['room_id']
        self.gui.my_online_piece=d['player_piece']
        
        role = d.get('role')
        self.gui.is_spectator = (role == 'spectator')
        
        if self.gui.is_spectator:
            self.gui.status_message = "İZLEYİCİ MODU"
            self.gui.start_online_game(True)
            if 'current_state' in d:
                self.gui.game_core.from_dict(d['current_state'])
        else: 
            self.gui.status_message = "Rakip Bekleniyor..."
            self.gui.start_online_game(False)
            
    def on_start(self, d): 
        if not self.gui.is_spectator:
            self.gui.status_message = "OYUN BAŞLADI!"
        
    def on_move(self, d):
        moved_col = d.get('col')
        current_player = d.get('current')
        
        mover = PLAYER1_PIECE if d['current'] == PLAYER2_PIECE else PLAYER2_PIECE
        
        if moved_col is not None:
            if self.gui.is_spectator or mover != self.gui.my_online_piece:
                self.gui.animate_drop(moved_col, mover)
                
        self.gui.game_core.from_dict(d)

    # Actions
    def create(self): 
        self.sio.emit('create_game', {'user_id': self.user_data['user_id']})
        
    def join(self, rid): 
        self.sio.emit('join_game', {'room_id': rid, 'user_id': self.user_data['user_id']})
        
    def move(self, col): 
        self.sio.emit('make_move', {'room_id': self.gui.room_id, 'col': col, 'player_piece': self.gui.my_online_piece})

# --- ANA GUI ---

class GUI:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(f"Connect 4 Pro - {SERVER_URL}")
        self.font = pygame.font.SysFont("Arial", 40, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 20)
        self.network = NetworkClient(self)
        self.game_state = "LOGIN"; self.status_message = "Hazır"; self.hint_col = None
        self.is_spectator = False
        self.ai_thinking = False
        self.game_core = ConnectFourGame()

        # Login Ekranı
        self.in_u = InputBox(WIDTH//2-100, 200, 200, 40, 'test')
        self.in_p = InputBox(WIDTH//2-100, 280, 200, 40, 'test', is_password=True)
        self.btn_log = Button(WIDTH//2-110, 350, 100, 50, "Giriş", GREEN)
        self.btn_reg = Button(WIDTH//2+10, 350, 100, 50, "Kayıt", BLUE)
        
        # Ana Menü
        self.btn_menu_pve = Button(WIDTH//2-100, 200, 200, 60, "vs AI", GREEN)
        self.btn_menu_net = Button(WIDTH//2-100, 280, 200, 60, "Online", BLUE)
        self.btn_menu_ldr = Button(WIDTH//2-100, 360, 200, 60, "Liderlik", ORANGE)
        
        # AI Seçim
        self.btn_ai_easy = Button(WIDTH//2-100, 200, 200, 50, "Kolay (D2)", GREEN)
        self.btn_ai_med = Button(WIDTH//2-100, 270, 200, 50, "Orta (D4)", YELLOW)
        self.btn_ai_hard = Button(WIDTH//2-100, 340, 200, 50, "Zor (D6)", RED)
        
        # Lobi
        self.btn_create_pvp = Button(WIDTH//2-100, 80, 200, 50, "Yeni Oyun Kur", GREEN)
        self.btn_refresh = Button(WIDTH//2+110, 80, 100, 50, "Yenile", GRAY)
        self.room_buttons = []
        
        # Ortak
        self.btn_back = Button(20, 20, 80, 40, "Geri", GRAY)
        self.btn_reset = Button(WIDTH//2-80, 300, 160, 60, "Menüye Dön", GREEN)
        
        # Oyun
        self.room_id = None
        self.my_online_piece = None
        self.player_piece = PLAYER1_PIECE
        self.ai_piece = PLAYER2_PIECE
        self.ai_engine = None

    def start_local_ai(self, depth):
        self.game_core = ConnectFourGame()
        self.ai_engine = AIEngine(self.ai_piece, depth)
        self.game_state = "PLAYING_AI"
        self.status_message = f"AI Derinlik: {depth}"
        
    def start_online_game(self, is_spectator):
        self.game_core = ConnectFourGame()
        self.is_spectator = is_spectator
        self.game_state = "PLAYING_ONLINE"
        
    def run_ai(self):
        self.ai_thinking = True
        col = self.ai_engine.get_best_move(self.game_core)
        self.ai_move_res = col
        self.ai_thinking = False
    
    def update_lobby_list(self):
        games = self.network.get_active_games()
        self.room_buttons = []
        y = 150
        for g in games:
            status_txt = "BEKLIYOR" if g['status'] == "WAITING" else "OYUNDA"
            color = GREEN if g['status'] == "WAITING" else ORANGE
            btn = Button(WIDTH//2-150, y, 300, 45, f"{g['room_id']} | {g['p1']} vs {g['p2']} [{status_txt}]", color, WHITE, 18)
            btn.room_id = g['room_id']
            self.room_buttons.append(btn)
            y += 55

    def draw_history_panel(self):
        panel_x = COLS * SQUARESIZE + 10
        pygame.draw.rect(self.screen, (30, 30, 40), (panel_x, 0, 240, HEIGHT))
        
        # Başlık
        title = self.small_font.render("HAMLE GEÇMİŞİ", True, WHITE)
        self.screen.blit(title, (panel_x + 60, 10))
        
        # Durum
        status_color = GREEN if "BAŞLADI" in self.status_message else YELLOW
        status = self.small_font.render(self.status_message[:25], True, status_color)
        self.screen.blit(status, (panel_x + 10, 40))
        
        # Sunucu bilgisi
        server_short = SERVER_URL.replace('https://', '').replace('http://', '')[:20]
        server_txt = self.small_font.render(f"Srv: {server_short}", True, GRAY)
        self.screen.blit(server_txt, (panel_x + 10, HEIGHT - 30))
        
        # Hamle listesi
        y = 70
        for i, move in enumerate(self.game_core.move_history[-15:]):  # Son 15 hamle
            player = "🔴" if i % 2 == 0 else "🟡"
            txt = self.small_font.render(f"{i+1}. {player} Sütun {move+1}", True, WHITE)
            self.screen.blit(txt, (panel_x + 10, y))
            y += 25
            
        self.btn_back.draw(self.screen)

    def draw_board(self):
        self.screen.fill(BLACK)
        
        # Mouse pozisyonu ile önizleme
        mouse_x = pygame.mouse.get_pos()[0]
        if mouse_x < COLS * SQUARESIZE:
            preview_col = mouse_x // SQUARESIZE
            if not self.is_spectator and self.game_core.is_valid_location(preview_col):
                color = RED if self.game_core.current_player == PLAYER1_PIECE else YELLOW
                pygame.draw.circle(self.screen, color, (preview_col * SQUARESIZE + 50, 50), RADIUS, 3)
        
        # Tahta
        for c in range(COLS):
            for r in range(ROWS):
                pygame.draw.rect(self.screen, BLUE, (c*SQUARESIZE, (r+1)*SQUARESIZE, SQUARESIZE, SQUARESIZE))
                
                piece = self.game_core.get_piece(r, c)
                if piece == 0:
                    color = BLACK
                elif piece == PLAYER1_PIECE:
                    color = RED
                else:
                    color = YELLOW
                    
                pygame.draw.circle(self.screen, color, (int(c*SQUARESIZE+50), int((r+1)*SQUARESIZE+50)), RADIUS)
        
        # Son hamle vurgusu
        if self.game_core.move_history:
            last_col = self.game_core.move_history[-1]
            last_row = self.game_core.heights[last_col] - 1
            if 0 <= last_row < ROWS:
                y_pos = (last_row + 1) * SQUARESIZE + 50
                pygame.draw.circle(self.screen, WHITE, (int(last_col*SQUARESIZE+50), y_pos), RADIUS+5, 5)

        self.draw_history_panel()
        pygame.display.update()

    def animate_drop(self, col, piece):
        color = RED if piece == PLAYER1_PIECE else YELLOW
        row_logic = self.game_core.heights[col] % (ROWS+1)
        y_target = HEIGHT - int(row_logic*SQUARESIZE + 50)
        
        y = 50; v = 0
        while y < y_target:
            v += 2; y += v; self.draw_board()
            if y > y_target: y = y_target
            pygame.draw.circle(self.screen, color, (int(col*SQUARESIZE+50), int(y)), RADIUS)
            pygame.display.flip(); pygame.time.wait(5)

    def draw_game_over(self):
        s = pygame.Surface((WIDTH, HEIGHT)); s.set_alpha(200); s.fill(BLACK)
        self.screen.blit(s, (0,0))
        
        res = "BERABERE!"
        if self.game_core.winner == PLAYER1_PIECE: res = "KIRMIZI KAZANDI!"
        elif self.game_core.winner == PLAYER2_PIECE: res = "SARI KAZANDI!"
        
        color = RED if self.game_core.winner == PLAYER1_PIECE else (YELLOW if self.game_core.winner == PLAYER2_PIECE else WHITE)
        lbl = self.font.render(res, True, color)
        self.screen.blit(lbl, (WIDTH//2 - lbl.get_width()//2, 200))
        
        # Winner ELO
        if self.game_state == "GAME_OVER" and not self.is_spectator and "online" in self.status_message.lower():
             elo_msg = "ELO Güncellendi (+/- 15)"
             self.screen.blit(self.small_font.render(elo_msg, True, WHITE), (WIDTH//2 - 80, 250))

        self.btn_reset.draw(self.screen)
        pygame.display.update()

    def run(self):
        clock = pygame.time.Clock()
        while True:
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT: sys.exit()

            if self.game_state == "LOGIN":
                self.screen.fill(BLACK)
                self.screen.blit(self.font.render("CONNECT 4 PRO", True, BLUE), (WIDTH//2-120, 100))
                self.in_u.draw(self.screen); self.in_p.draw(self.screen)
                self.btn_log.draw(self.screen); self.btn_reg.draw(self.screen)
                self.screen.blit(self.small_font.render(self.status_message, True, RED), (WIDTH//2-50, 430))
                
                # Sunucu bilgisi
                srv_txt = self.small_font.render(f"Sunucu: {SERVER_URL}", True, GRAY)
                self.screen.blit(srv_txt, (WIDTH//2 - srv_txt.get_width()//2, HEIGHT - 40))
                
                pygame.display.update()
                for e in events:
                    self.in_u.handle_event(e); self.in_p.handle_event(e)
                    if e.type == pygame.MOUSEBUTTONDOWN:
                        if self.btn_log.is_clicked(e.pos) and self.network.login(self.in_u.text, self.in_p.text):
                            self.network.connect_socket(); self.game_state = "MENU"
                        if self.btn_reg.is_clicked(e.pos): self.network.register(self.in_u.text, self.in_p.text)

            elif self.game_state == "MENU":
                self.screen.fill(BLACK)
                self.screen.blit(self.font.render("ANA MENÜ", True, WHITE), (WIDTH//2-80, 100))
                self.btn_menu_pve.draw(self.screen); self.btn_menu_net.draw(self.screen); self.btn_menu_ldr.draw(self.screen)
                if self.network.user_data:
                    u = self.network.user_data
                    self.screen.blit(self.small_font.render(f"Kullanıcı: {u['username']} | ELO: {u['rating']}", True, GREEN), (20, HEIGHT-30))
                pygame.display.update()
                for e in events:
                    if e.type == pygame.MOUSEBUTTONDOWN:
                        if self.btn_menu_pve.is_clicked(e.pos): self.game_state = "AI_SELECT"
                        if self.btn_menu_net.is_clicked(e.pos): 
                            self.update_lobby_list()
                            self.game_state = "LOBBY"
                        if self.btn_menu_ldr.is_clicked(e.pos): self.game_state = "LEADERBOARD"

            elif self.game_state == "AI_SELECT":
                self.screen.fill(BLACK)
                self.btn_back.draw(self.screen)
                self.screen.blit(self.font.render("ZORLUK SEÇİN", True, WHITE), (WIDTH//2-120, 100))
                self.btn_ai_easy.draw(self.screen); self.btn_ai_med.draw(self.screen); self.btn_ai_hard.draw(self.screen)
                pygame.display.update()
                for e in events:
                    if e.type == pygame.MOUSEBUTTONDOWN:
                        if self.btn_back.is_clicked(e.pos): self.game_state = "MENU"
                        if self.btn_ai_easy.is_clicked(e.pos): self.start_local_ai(2)
                        if self.btn_ai_med.is_clicked(e.pos): self.start_local_ai(4)
                        if self.btn_ai_hard.is_clicked(e.pos): self.start_local_ai(6)

            elif self.game_state == "LOBBY":
                self.screen.fill(BLACK)
                self.btn_back.draw(self.screen)
                self.screen.blit(self.font.render("OYUN LOBİSİ", True, WHITE), (WIDTH//2-100, 20))
                
                self.btn_create_pvp.draw(self.screen)
                self.btn_refresh.draw(self.screen)
                
                # Liste
                if not self.room_buttons:
                    self.screen.blit(self.small_font.render("Aktif oyun yok. Yeni kur!", True, GRAY), (WIDTH//2-100, 250))
                else:
                    for btn in self.room_buttons: btn.draw(self.screen)
                
                self.screen.blit(self.small_font.render(self.status_message, True, YELLOW), (50, HEIGHT-50))
                pygame.display.update()
                
                for e in events:
                    if e.type == pygame.MOUSEBUTTONDOWN:
                        if self.btn_back.is_clicked(e.pos): self.game_state = "MENU"
                        if self.btn_create_pvp.is_clicked(e.pos): self.network.create()
                        if self.btn_refresh.is_clicked(e.pos): self.update_lobby_list()
                        
                        for btn in self.room_buttons:
                            if btn.is_clicked(e.pos): self.network.join(btn.room_id)

            elif self.game_state == "LEADERBOARD":
                self.network.gui = self 
                self.screen.fill(BLACK); self.btn_back.draw(self.screen)
                self.screen.blit(self.font.render("EN İYİ 10 OYUNCU", True, ORANGE), (WIDTH//2-130, 50))
                data = self.network.get_leaderboard(); y = 120
                
                header = f"{'SIRA':<5} {'İSİM':<15} {'ELO':<10} {'G.':<5}"
                self.screen.blit(self.small_font.render(header, True, GRAY), (WIDTH//2-150, y))
                y += 40
                for i, p in enumerate(data):
                    color = YELLOW if i == 0 else (WHITE if i < 3 else GRAY)
                    text = f"{i+1:<5} {p['username']:<15} {p['rating']:<10} {p['wins']:<5}"
                    self.screen.blit(self.small_font.render(text, True, color), (WIDTH//2-150, y))
                    y += 35
                pygame.display.update()
                
                for e in events:
                    if e.type == pygame.MOUSEBUTTONDOWN and self.btn_back.is_clicked(e.pos): self.game_state = "MENU"

            elif "PLAYING" in self.game_state:
                self.draw_board()
                
                if self.game_core.game_over:
                    self.game_state = "GAME_OVER"; continue

                # Local AI Hamlesi
                if self.game_state == "PLAYING_AI" and hasattr(self, 'ai_move_res'):
                    if self.ai_move_res is not None:
                        self.animate_drop(self.ai_move_res, self.ai_piece)
                        self.game_core.make_move(self.ai_move_res)
                    del self.ai_move_res
                
                for e in events:
                    if e.type == pygame.MOUSEBUTTONDOWN and not self.is_spectator:
                         if self.btn_back.is_clicked(e.pos): self.game_state = "MENU"
                         
                         if e.pos[0] < COLS*SQUARESIZE: 
                             col = int(e.pos[0]/SQUARESIZE)
                             if 0 <= col < COLS and self.game_core.is_valid_location(col):
                                 # Online Hamle
                                 if self.game_state == "PLAYING_ONLINE" and self.game_core.current_player == self.network.gui.my_online_piece:
                                     self.network.move(col)
                                 # Local AI Hamle
                                 elif self.game_state == "PLAYING_AI" and self.game_core.current_player == self.player_piece and not getattr(self, 'ai_thinking', False):
                                     self.animate_drop(col, self.player_piece); self.game_core.make_move(col)
                                     if not self.game_core.game_over: threading.Thread(target=self.run_ai).start()
            
            elif self.game_state == "GAME_OVER":
                self.draw_board(); self.draw_game_over()
                for e in events:
                    if e.type == pygame.MOUSEBUTTONDOWN and self.btn_reset.is_clicked(e.pos): self.game_state = "MENU"
            
            clock.tick(30)

if __name__ == "__main__": 
    print("="*50)
    print("   CONNECT FOUR PRO - CLIENT")
    print("="*50)
    GUI().run()