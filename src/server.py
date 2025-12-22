# =============================================================================
# MODÜL: server.py - PROFESSIONAL EDITION v2.0
# Connect Four Pro - Flask-SocketIO Server
# =============================================================================

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, close_room
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

# Logging ayarları
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Aktif oyunlar
GAMES = {}

# Bağlı kullanıcılar (sid -> user_data)
CONNECTED_USERS = {}

# =============================================================================
# YARDIMCI FONKSİYONLAR
# =============================================================================

def generate_room_id(length=5) -> str:
    """Benzersiz oda ID'si oluştur"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def get_user_info(user_id):
    """Kullanıcı bilgilerini veritabanından al"""
    try:
        users = db.get_top_players(limit=100)  # Tüm kullanıcıları al
        for user in users:
            if str(user.get('user_id')) == str(user_id) or user.get('username') == str(user_id):
                return user
    except:
        pass
    return {'username': str(user_id), 'rating': 1000, 'wins': 0, 'losses': 0}

def calculate_elo_change(winner_rating, loser_rating, k=30):
    """ELO değişimini hesapla"""
    expected = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    change = int(k * (1 - expected))
    return max(change, 10)  # Minimum 10 puan

def print_banner():
    print(f"\n{'='*60}")
    print(f"   CONNECT FOUR PRO SERVER v2.0")
    print(f"   Flask-SocketIO Hybrid Architecture")
    print(f"{'='*60}")
    print(f"[+] OS: {sys.platform}")
    print(f"[+] Mode: Multi-Player + Spectator")
    print(f"[+] Features: Real-time ELO, Player Info")
    print(f"[+] Listening: http://0.0.0.0:5000")
    print("-" * 60)

# =============================================================================
# REST API ENDPOINTS
# =============================================================================

@app.route('/signup', methods=['POST'])
def signup():
    """Yeni kullanıcı kaydı"""
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
    """Kullanıcı girişi"""
    data = request.get_json()
    user = db.verify_user(data.get('username'), data.get('password'))
    if user:
        print(f"[USER] Login: {user['username']} (ELO: {user['rating']})")
        return jsonify({'message': 'OK', 'user': user}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/user/<user_id>', methods=['GET'])
def get_user(user_id):
    """Kullanıcı bilgilerini getir (anlık ELO için)"""
    user = get_user_info(user_id)
    if user:
        return jsonify({'user': user}), 200
    return jsonify({'error': 'User not found'}), 404

@app.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    """Liderlik tablosu"""
    limit = request.args.get('limit', 10, type=int)
    data = db.get_top_players(limit=limit)
    return jsonify(data), 200

@app.route('/active_games', methods=['GET'])
def get_active_games():
    """Aktif oyunları listele"""
    game_list = []
    for room_id, g_data in list(GAMES.items()):
        if g_data['game'].game_over:
            continue
            
        # Durum belirleme
        status = "WAITING" if g_data['p2_uid'] is None else "PLAYING"
        
        # Oyuncu isimleri
        p1_info = get_user_info(g_data['p1_uid'])
        p2_info = get_user_info(g_data['p2_uid']) if g_data['p2_uid'] else None
        
        game_list.append({
            'room_id': room_id,
            'status': status,
            'p1': p1_info.get('username', str(g_data['p1_uid'])),
            'p2': p2_info.get('username', 'Bekleniyor...') if p2_info else 'Bekleniyor...',
            'p1_elo': p1_info.get('rating', 1000),
            'p2_elo': p2_info.get('rating', 1000) if p2_info else 0
        })
    return jsonify(game_list), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Sunucu sağlık kontrolü"""
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
    """Yeni WebSocket bağlantısı"""
    print(f"[SOCKET] Connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    """WebSocket bağlantısı koptu"""
    sid = request.sid
    print(f"[SOCKET] Disconnected: {sid}")
    
    # Bağlı kullanıcıyı temizle
    if sid in CONNECTED_USERS:
        del CONNECTED_USERS[sid]
    
    # Aktif oyunlardan çıkar (opsiyonel)
    for room_id, g_data in list(GAMES.items()):
        if g_data['p1_sid'] == sid or g_data['p2_sid'] == sid:
            # Rakibe bildir
            emit('opponent_disconnected', {'msg': 'Rakip bağlantısı koptu'}, to=room_id)

@socketio.on('create_game')
def on_create_game(data):
    """Yeni oyun odası oluştur"""
    room_id = generate_room_id()
    while room_id in GAMES:
        room_id = generate_room_id()
    
    user_id = data.get('user_id')
    game = ConnectFourGame()
    
    GAMES[room_id] = {
        'game': game,
        'p1_sid': request.sid,
        'p1_uid': user_id,
        'p2_sid': None,
        'p2_uid': None,
        'created_at': time.time()
    }
    
    join_room(room_id)
    
    # Kullanıcı bilgilerini al
    user_info = get_user_info(user_id)
    
    print(f"[ROOM] {room_id} Created by {user_info.get('username', user_id)}")
    
    emit('game_created', {
        'room_id': room_id,
        'player_piece': PLAYER1_PIECE,
        'your_info': user_info
    })

@socketio.on('join_game')
def on_join_game(data):
    """Oyuna katıl (oyuncu veya izleyici olarak)"""
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    
    if room_id not in GAMES:
        emit('error', {'msg': 'Oda bulunamadı'})
        return
    
    g_data = GAMES[room_id]
    game = g_data['game']
    join_room(room_id)
    
    # Kullanıcı bilgileri
    user_info = get_user_info(user_id)
    
    if g_data['p2_uid'] is None:
        # Player 2 olarak katıl
        g_data['p2_sid'] = request.sid
        g_data['p2_uid'] = user_id
        
        print(f"[ROOM] {room_id}: Player 2 ({user_info.get('username', user_id)}) Joined")
        
        # Player 1'in bilgilerini al
        p1_info = get_user_info(g_data['p1_uid'])
        
        # Player 2'ye bildir
        emit('game_joined', {
            'room_id': room_id,
            'player_piece': PLAYER2_PIECE,
            'role': 'player',
            'your_info': user_info,
            'opponent_info': p1_info
        })
        
        # Her iki oyuncuya oyun başladı bildir
        emit('game_start', {
            'msg': 'Oyun Başladı!',
            'p1_info': p1_info,
            'p2_info': user_info,
            'opponent_name': user_info.get('username', str(user_id)),
            'opponent_elo': user_info.get('rating', 1000)
        }, to=g_data['p1_sid'])
        
        emit('game_start', {
            'msg': 'Oyun Başladı!',
            'p1_info': p1_info,
            'p2_info': user_info,
            'opponent_name': p1_info.get('username', str(g_data['p1_uid'])),
            'opponent_elo': p1_info.get('rating', 1000)
        }, to=request.sid)
        
    else:
        # Spectator olarak katıl
        print(f"[ROOM] {room_id}: Spectator ({user_info.get('username', user_id)}) Joined")
        
        emit('game_joined', {
            'room_id': room_id,
            'player_piece': 0,  # 0 = Spectator
            'role': 'spectator',
            'current_state': game.to_dict(),
            'p1_info': get_user_info(g_data['p1_uid']),
            'p2_info': get_user_info(g_data['p2_uid'])
        })

@socketio.on('make_move')
def on_make_move(data):
    """Hamle yap"""
    room_id = data.get('room_id')
    col = data.get('col')
    player_piece = data.get('player_piece')
    
    if room_id not in GAMES:
        return
        
    g_data = GAMES[room_id]
    game = g_data['game']
    
    # Rakip bekleniyor mu?
    if g_data['p2_uid'] is None:
        emit('error', {'msg': 'Rakip bekleniyor!'}, to=request.sid)
        return
    
    # Sıra kontrolü
    if game.current_player != player_piece:
        emit('error', {'msg': 'Sıra sizde değil!'}, to=request.sid)
        return
    
    # Hamleyi uygula
    if game.make_move(col):
        response = game.to_dict()
        response['col'] = col
        
        # Tüm odaya bildir
        emit('move_made', response, to=room_id)
        
        # Oyun bitti mi?
        if game.game_over:
            handle_game_over(room_id, g_data, game)

def handle_game_over(room_id, g_data, game):
    """Oyun sonu işlemleri"""
    print(f"[GAME OVER] Room: {room_id}, Winner: {game.winner}")
    
    p1_uid = g_data['p1_uid']
    p2_uid = g_data['p2_uid']
    
    # Kazanan belirleme
    winner_uid = None
    loser_uid = None
    
    if game.winner == PLAYER1_PIECE:
        winner_uid = p1_uid
        loser_uid = p2_uid
    elif game.winner == PLAYER2_PIECE:
        winner_uid = p2_uid
        loser_uid = p1_uid
    
    # ELO güncellemesi
    elo_changes = {'p1': 0, 'p2': 0}
    
    if winner_uid and loser_uid:
        winner_info = get_user_info(winner_uid)
        loser_info = get_user_info(loser_uid)
        
        # ELO değişimi hesapla
        elo_change = calculate_elo_change(
            winner_info.get('rating', 1000),
            loser_info.get('rating', 1000)
        )
        
        # Veritabanını güncelle
        db.update_game_result(p1_uid, p2_uid, winner_uid, str(game.move_history))
        
        # ELO değişimlerini belirle
        if winner_uid == p1_uid:
            elo_changes['p1'] = elo_change
            elo_changes['p2'] = -elo_change
        else:
            elo_changes['p1'] = -elo_change
            elo_changes['p2'] = elo_change
        
        # Güncel ELO değerlerini al
        new_p1_info = get_user_info(p1_uid)
        new_p2_info = get_user_info(p2_uid)
        
        # Player 1'e ELO güncellemesi bildir
        emit('elo_update', {
            'new_elo': new_p1_info.get('rating', 1000),
            'change': elo_changes['p1'],
            'winner': winner_uid == p1_uid
        }, to=g_data['p1_sid'])
        
        # Player 2'ye ELO güncellemesi bildir
        emit('elo_update', {
            'new_elo': new_p2_info.get('rating', 1000),
            'change': elo_changes['p2'],
            'winner': winner_uid == p2_uid
        }, to=g_data['p2_sid'])
    
    # Oyun sonucu bildir
    emit('game_over', {
        'winner': game.winner,
        'winner_uid': winner_uid,
        'elo_changes': elo_changes,
        'move_count': len(game.move_history)
    }, to=room_id)

# =============================================================================
# SUNUCU BAŞLATMA
# =============================================================================

if __name__ == '__main__':
    # Veritabanını başlat
    db.init_db()
    
    # Banner yazdır
    print_banner()
    
    # Sunucuyu başlat
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")