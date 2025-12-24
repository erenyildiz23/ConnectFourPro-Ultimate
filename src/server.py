# =============================================================================
# MODÜL: server.py - PROFESSIONAL EDITION v2.1
# Connect Four Pro - Flask-SocketIO Server
# Features: Auto-cleanup, Duplicate game prevention
# =============================================================================

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, close_room
import random
import string
import logging
import sys
import time
import threading
import os

import database as db
from game_core import ConnectFourGame, PLAYER1_PIECE, PLAYER2_PIECE

# =============================================================================
# KONFİGÜRASYON
# =============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'production_secret_key_c4_2024')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Aktif oyunlar
GAMES = {}

# Bağlı kullanıcılar (sid -> user_data)
CONNECTED_USERS = {}

# Cleanup settings
WAITING_TIMEOUT = 300  # 5 dakika bekleyen oyun silinir
INACTIVE_TIMEOUT = 600  # 10 dakika hareketsiz oyun silinir
CLEANUP_INTERVAL = 60   # Her 60 saniyede bir kontrol

# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def generate_room_id(length=5) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def get_user_info(user_id):
    try:
        user = db.get_user_by_username(str(user_id))
        if user:
            return user
        users = db.get_top_players(limit=100)
        for u in users:
            if str(u.get('user_id')) == str(user_id) or u.get('username') == str(user_id):
                return u
    except:
        pass
    return {'username': str(user_id), 'rating': 1200, 'wins': 0, 'losses': 0}

def calculate_elo_change(winner_rating, loser_rating, k=30):
    expected = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    change = int(k * (1 - expected))
    return max(change, 10)

def get_user_active_games(user_id):
    """Kullanıcının aktif oyunlarını bul"""
    active = []
    for room_id, g_data in GAMES.items():
        if g_data['p1_uid'] == user_id or g_data['p2_uid'] == user_id:
            active.append(room_id)
    return active

def get_user_waiting_game(user_id):
    """Kullanıcının bekleyen oyununu bul"""
    for room_id, g_data in GAMES.items():
        if g_data['p1_uid'] == user_id and g_data['p2_uid'] is None:
            return room_id
    return None

def cleanup_old_games():
    """Eski ve tamamlanmış oyunları temizle"""
    now = time.time()
    to_delete = []
    
    for room_id, g_data in list(GAMES.items()):
        game = g_data['game']
        created_at = g_data.get('created_at', now)
        last_move = g_data.get('last_move_at', created_at)
        
        # 1. Tamamlanmış oyunları 1 dakika sonra sil
        if game.game_over:
            if now - last_move > 60:
                to_delete.append(room_id)
                continue
        
        # 2. Bekleyen oyunları WAITING_TIMEOUT sonra sil
        if g_data['p2_uid'] is None:
            if now - created_at > WAITING_TIMEOUT:
                to_delete.append(room_id)
                continue
        
        # 3. Hareketsiz oyunları INACTIVE_TIMEOUT sonra sil
        if now - last_move > INACTIVE_TIMEOUT:
            to_delete.append(room_id)
    
    for room_id in to_delete:
        print(f"[CLEANUP] Removing stale game: {room_id}")
        try:
            # Odadaki herkese bildir
            socketio.emit('game_ended', {'reason': 'timeout'}, to=room_id)
            close_room(room_id)
        except:
            pass
        if room_id in GAMES:
            del GAMES[room_id]
    
    if to_delete:
        print(f"[CLEANUP] Removed {len(to_delete)} stale games. Active: {len(GAMES)}")

def start_cleanup_thread():
    """Background cleanup thread"""
    def cleanup_loop():
        while True:
            time.sleep(CLEANUP_INTERVAL)
            try:
                cleanup_old_games()
            except Exception as e:
                print(f"[CLEANUP ERROR] {e}")
    
    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    print("[CLEANUP] Background cleanup thread started")

def print_banner():
    print(f"\n{'='*60}")
    print(f"   CONNECT FOUR PRO SERVER v2.1")
    print(f"   Flask-SocketIO Hybrid Architecture")
    print(f"{'='*60}")
    print(f"[+] OS: {sys.platform}")
    print(f"[+] Mode: Multi-Player + Spectator + Auto-Cleanup")
    print(f"[+] Waiting Timeout: {WAITING_TIMEOUT}s")
    print(f"[+] Inactive Timeout: {INACTIVE_TIMEOUT}s")
    print(f"[+] Listening: http://0.0.0.0:5000")
    print("-" * 60)

# =============================================================================
# REST API ENDPOINTS
# =============================================================================

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    if len(username) < 3:
        return jsonify({'error': 'Username too short (min 3 chars)'}), 400
        
    user_id = db.create_user(username, password)
    if user_id:
        print(f"[USER] New user registered: {username}")
        return jsonify({'message': 'Created', 'user_id': user_id}), 201
    return jsonify({'error': 'Username already taken'}), 409

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    user = db.verify_user(username, password)
    if user:
        print(f"[USER] Login: {username}")
        return jsonify({'message': 'Success', 'user': user}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/user/<username>', methods=['GET'])
def get_user(username):
    user = db.get_user_by_username(username)
    if user:
        return jsonify({'user': user}), 200
    return jsonify({'error': 'User not found'}), 404

@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    limit = request.args.get('limit', 10, type=int)
    players = db.get_top_players(limit=limit)
    return jsonify(players), 200

@app.route('/active_games', methods=['GET'])
def active_games():
    games_list = []
    for room_id, g_data in GAMES.items():
        p1_info = get_user_info(g_data['p1_uid'])
        p2_info = get_user_info(g_data['p2_uid']) if g_data['p2_uid'] else None
        
        games_list.append({
            'room_id': room_id,
            'p1': p1_info.get('username', 'Player1'),
            'p1_elo': p1_info.get('rating', 1200),
            'p2': p2_info.get('username', 'Bekleniyor...') if p2_info else 'Bekleniyor...',
            'p2_elo': p2_info.get('rating', 1200) if p2_info else 0,
            'status': 'PLAYING' if g_data['p2_uid'] else 'WAITING',
            'move_count': len(g_data['game'].move_history)
        })
    return jsonify(games_list), 200

@app.route('/cleanup', methods=['POST'])
def manual_cleanup():
    """Manuel temizleme endpoint'i"""
    cleanup_old_games()
    return jsonify({'message': 'Cleanup completed', 'active_games': len(GAMES)}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'active_games': len(GAMES),
        'connected_users': len(CONNECTED_USERS)
    }), 200

# =============================================================================
# SOCKET.IO EVENT HANDLERS
# =============================================================================

@socketio.on('connect')
def on_connect():
    print(f"[SOCKET] Connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    print(f"[SOCKET] Disconnected: {sid}")
    
    if sid in CONNECTED_USERS:
        del CONNECTED_USERS[sid]
    
    # Kullanıcının oyunlarını kontrol et
    for room_id, g_data in list(GAMES.items()):
        if g_data['p1_sid'] == sid:
            # P1 ayrıldı
            if g_data['p2_uid'] is None:
                # Bekleyen oyun - direkt sil
                print(f"[ROOM] {room_id} deleted (creator left while waiting)")
                del GAMES[room_id]
            else:
                # Aktif oyun - rakibe bildir
                emit('opponent_disconnected', {'msg': 'Rakip ayrıldı'}, to=room_id)
        elif g_data['p2_sid'] == sid:
            # P2 ayrıldı - rakibe bildir
            emit('opponent_disconnected', {'msg': 'Rakip ayrıldı'}, to=room_id)

@socketio.on('create_game')
def on_create_game(data):
    user_id = data.get('user_id')
    
    # Kullanıcının zaten bekleyen oyunu var mı?
    existing_game = get_user_waiting_game(user_id)
    if existing_game:
        # Eski oyunu sil
        print(f"[ROOM] Deleting user's previous waiting game: {existing_game}")
        try:
            close_room(existing_game)
        except:
            pass
        if existing_game in GAMES:
            del GAMES[existing_game]
    
    room_id = generate_room_id()
    while room_id in GAMES:
        room_id = generate_room_id()
    
    game = ConnectFourGame()
    
    GAMES[room_id] = {
        'game': game,
        'p1_sid': request.sid,
        'p1_uid': user_id,
        'p2_sid': None,
        'p2_uid': None,
        'created_at': time.time(),
        'last_move_at': time.time()
    }
    
    join_room(room_id)
    
    user_info = get_user_info(user_id)
    print(f"[ROOM] {room_id} Created by {user_info.get('username', user_id)}")
    
    emit('game_created', {
        'room_id': room_id,
        'player_piece': PLAYER1_PIECE,
        'your_info': user_info
    })

@socketio.on('join_game')
def on_join_game(data):
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    
    if room_id not in GAMES:
        emit('error', {'msg': 'Oda bulunamadı'})
        return
    
    g_data = GAMES[room_id]
    game = g_data['game']
    
    # Kendi oyununa katılmaya çalışıyor mu?
    if g_data['p1_uid'] == user_id:
        emit('error', {'msg': 'Kendi oyununuza katılamazsınız'})
        return
    
    join_room(room_id)
    user_info = get_user_info(user_id)
    
    if g_data['p2_uid'] is None:
        # Player 2 olarak katıl
        g_data['p2_sid'] = request.sid
        g_data['p2_uid'] = user_id
        g_data['last_move_at'] = time.time()
        
        p1_info = get_user_info(g_data['p1_uid'])
        
        print(f"[ROOM] {room_id}: {user_info.get('username', user_id)} joined as P2")
        
        emit('game_joined', {
            'room_id': room_id,
            'player_piece': PLAYER2_PIECE,
            'role': 'player',
            'opponent_info': p1_info
        })
        
        # P1'e oyunun başladığını bildir
        emit('game_start', {
            'msg': 'Oyun Başladı!',
            'p1_info': p1_info,
            'p2_info': user_info,
            'opponent_name': user_info.get('username', str(user_id)),
            'opponent_elo': user_info.get('rating', 1200)
        }, to=g_data['p1_sid'])
        
        # P2'ye oyunun başladığını bildir
        emit('game_start', {
            'msg': 'Oyun Başladı!',
            'p1_info': p1_info,
            'p2_info': user_info,
            'opponent_name': p1_info.get('username', str(g_data['p1_uid'])),
            'opponent_elo': p1_info.get('rating', 1200)
        }, to=request.sid)
        
    else:
        # Spectator olarak katıl
        print(f"[ROOM] {room_id}: Spectator ({user_info.get('username', user_id)}) joined")
        
        emit('game_joined', {
            'room_id': room_id,
            'player_piece': 0,
            'role': 'spectator',
            'current_state': game.to_dict(),
            'p1_info': get_user_info(g_data['p1_uid']),
            'p2_info': get_user_info(g_data['p2_uid'])
        })

@socketio.on('make_move')
def on_make_move(data):
    room_id = data.get('room_id')
    col = data.get('col')
    player_piece = data.get('player_piece')
    
    if room_id not in GAMES:
        return
        
    g_data = GAMES[room_id]
    game = g_data['game']
    
    if g_data['p2_uid'] is None:
        emit('error', {'msg': 'Rakip bekleniyor!'}, to=request.sid)
        return
    
    if game.current_player != player_piece:
        emit('error', {'msg': 'Sıra sizde değil!'}, to=request.sid)
        return
    
    if game.make_move(col):
        g_data['last_move_at'] = time.time()
        
        response = game.to_dict()
        response['col'] = col
        
        emit('move_made', response, to=room_id)
        
        if game.game_over:
            handle_game_over(room_id, g_data, game)

def handle_game_over(room_id, g_data, game):
    print(f"[GAME OVER] Room: {room_id}, Winner: {game.winner}")
    
    p1_uid = g_data['p1_uid']
    p2_uid = g_data['p2_uid']
    
    winner_uid = None
    loser_uid = None
    
    if game.winner == PLAYER1_PIECE:
        winner_uid = p1_uid
        loser_uid = p2_uid
    elif game.winner == PLAYER2_PIECE:
        winner_uid = p2_uid
        loser_uid = p1_uid
    
    elo_changes = {'p1': 0, 'p2': 0}
    
    if winner_uid and loser_uid:
        # ELO güncelle (username bazlı)
        result = db.update_elo_by_username(str(winner_uid), str(loser_uid))
        elo_change = result.get('winner_change', 15)
        
        if winner_uid == p1_uid:
            elo_changes['p1'] = elo_change
            elo_changes['p2'] = -elo_change
        else:
            elo_changes['p1'] = -elo_change
            elo_changes['p2'] = elo_change
        
        # Oyunu kaydet
        db.record_game(str(p1_uid), str(p2_uid), str(winner_uid), str(game.move_history))
        
        # Güncel ELO değerlerini al
        new_p1_info = get_user_info(p1_uid)
        new_p2_info = get_user_info(p2_uid)
        
        emit('elo_update', {
            'new_elo': new_p1_info.get('rating', 1200),
            'change': elo_changes['p1'],
            'winner': winner_uid == p1_uid
        }, to=g_data['p1_sid'])
        
        emit('elo_update', {
            'new_elo': new_p2_info.get('rating', 1200),
            'change': elo_changes['p2'],
            'winner': winner_uid == p2_uid
        }, to=g_data['p2_sid'])
    
    emit('game_over', {
        'winner': game.winner,
        'winner_uid': winner_uid,
        'elo_changes': elo_changes,
        'move_count': len(game.move_history)
    }, to=room_id)

@socketio.on('leave_game')
def on_leave_game(data):
    """Oyundan ayrıl"""
    room_id = data.get('room_id')
    if room_id in GAMES:
        leave_room(room_id)
        emit('player_left', {'sid': request.sid}, to=room_id)

# =============================================================================
# SUNUCU BAŞLATMA
# =============================================================================

if __name__ == '__main__':
    db.init_db()
    print_banner()
    start_cleanup_thread()
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")