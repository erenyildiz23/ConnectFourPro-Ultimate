# =============================================================================
# MODULE: server.py - v3.0
# Connect Four Pro - Flask-SocketIO Sunucusu
# =============================================================================
"""
REST API (kimlik dogrulama, liderlik tablosu, lobi, mac gecmisi) +
Socket.IO (oda yonetimi, gercek zamanli hamleler, seyirci modu) +
Unity WebGL istemcisi (/play).

Ozellikler:
  * Sunucu tarafli hamle dogrulama; hamleyi sadece tasin sahibi yapabilir
  * Baglantisi kopan oyuncu RECONNECT_GRACE_SECONDS icinde geri donebilir,
    donmezse rakip hukmen kazanir (NFR-08)
  * Bekleyen / hareketsiz / bitmis odalar otomatik temizlenir
  * Tum oda durumuna erisim tek bir kilitle korunur (thread-safe)
"""

import os
import random
import re
import string
import threading
import time
from typing import Any, Dict, Optional, Tuple

from flask import Flask, abort, jsonify, redirect, request, send_from_directory
from flask_socketio import SocketIO, close_room, emit, join_room, leave_room

import config
import database as db
from game_core import PLAYER1_PIECE, PLAYER2_PIECE, ConnectFourGame, other_player

log = config.get_logger("server")

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Werkzeug istek loglari cok gurultulu
config.get_logger("werkzeug").setLevel("ERROR")

# room_id -> oda sozlugu (bkz. _new_room)
GAMES: Dict[str, Dict[str, Any]] = {}
# sid -> username
CONNECTED_USERS: Dict[str, str] = {}
GAMES_LOCK = threading.RLock()

# Geriye donuk uyumluluk (testler/benchmark'lar bu adlari kullanabilir)
WAITING_TIMEOUT = config.WAITING_TIMEOUT
INACTIVE_TIMEOUT = config.INACTIVE_TIMEOUT
CLEANUP_INTERVAL = config.CLEANUP_INTERVAL

_USERNAME_RE = re.compile(r'^[\w.-]+$', re.UNICODE)
_ROOM_ID_RE = re.compile(r'^[A-Z0-9]{5}$')


# =============================================================================
# YARDIMCI FONKSIYONLAR
# =============================================================================

def generate_room_id(length: int = 5) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def get_user_info(username: Optional[str]) -> Dict[str, Any]:
    """Kayitli kullanici bilgisi; kayitli degilse (misafir) varsayilan profil."""
    if username:
        user = db.get_user_by_username(str(username))
        if user:
            user['guest'] = False
            return user
    return {'username': str(username), 'rating': config.DEFAULT_RATING,
            'wins': 0, 'losses': 0, 'guest': True}


def validate_credentials(data: Any) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """(username, password, hata_mesaji) dondurur."""
    if not isinstance(data, dict):
        return None, None, 'Invalid JSON body'
    username = data.get('username')
    password = data.get('password')
    if not isinstance(username, str) or not isinstance(password, str):
        return None, None, 'Username and password required'
    username = username.strip()
    if not username or not password:
        return None, None, 'Username and password required'
    return username, password, None


def _clean_str(data: Any, key: str, max_len: int = 64) -> Optional[str]:
    """Socket verisinden guvenli string alani."""
    if not isinstance(data, dict):
        return None
    value = data.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:max_len] if value else None


def _new_room(p1_sid: str, p1_uid: str, p1_info: dict) -> Dict[str, Any]:
    now = time.time()
    return {
        'game': ConnectFourGame(),
        'p1_sid': p1_sid, 'p1_uid': p1_uid, 'p1_info': p1_info,
        'p2_sid': None, 'p2_uid': None, 'p2_info': None,
        'created_at': now,
        'last_move_at': now,
        'disconnected': {},      # piece -> kopma zamani
        'end_reason': None,
    }


def _piece_of(room: dict, sid: str) -> Optional[int]:
    if room['p1_sid'] == sid:
        return PLAYER1_PIECE
    if room['p2_sid'] == sid:
        return PLAYER2_PIECE
    return None


def _uid_of(room: dict, piece: int) -> Optional[str]:
    return room['p1_uid'] if piece == PLAYER1_PIECE else room['p2_uid']


def _sid_of(room: dict, piece: int) -> Optional[str]:
    return room['p1_sid'] if piece == PLAYER1_PIECE else room['p2_sid']


def get_user_waiting_game(user_id: str) -> Optional[str]:
    with GAMES_LOCK:
        for room_id, room in GAMES.items():
            if room['p1_uid'] == user_id and room['p2_uid'] is None:
                return room_id
    return None


# =============================================================================
# OYUN SONU
# =============================================================================

def _finish_game(room_id: str, room: dict, reason: str = 'normal',
                 forfeit_loser: Optional[int] = None) -> None:
    """
    Oyunu sonlandirir: ELO gunceller, oyunu kaydeder, odaya game_over yayinlar.
    GAMES_LOCK tutulurken cagrilmalidir.
    """
    game: ConnectFourGame = room['game']
    if forfeit_loser is not None:
        game.game_over = True
        game.winner = other_player(forfeit_loser)
    room['end_reason'] = reason
    room['last_move_at'] = time.time()

    p1_uid, p2_uid = room['p1_uid'], room['p2_uid']
    winner_uid = loser_uid = None
    if game.winner is not None:
        winner_uid = _uid_of(room, game.winner)
        loser_uid = _uid_of(room, other_player(game.winner))

    log.info("Oyun bitti: oda=%s kazanan=%s neden=%s", room_id, game.winner, reason)
    elo_changes = {'p1': 0, 'p2': 0}
    new_ratings = {'p1': None, 'p2': None}
    moves = str(game.move_history)

    if winner_uid and loser_uid:
        change = db.update_elo_by_username(str(winner_uid), str(loser_uid))['winner_change']
        winner_key = 'p1' if game.winner == PLAYER1_PIECE else 'p2'
        loser_key = 'p2' if winner_key == 'p1' else 'p1'
        elo_changes[winner_key], elo_changes[loser_key] = change, -change
        db.record_game(str(p1_uid), str(p2_uid), str(winner_uid), moves, reason)

        if change:  # Misafir oyunlarinda ELO bildirimi gonderilmez
            for key, piece in (('p1', PLAYER1_PIECE), ('p2', PLAYER2_PIECE)):
                new_ratings[key] = get_user_info(_uid_of(room, piece)).get('rating', config.DEFAULT_RATING)
                sid = _sid_of(room, piece)
                if sid and piece not in room['disconnected']:
                    socketio.emit('elo_update', {
                        'new_elo': new_ratings[key],
                        'change': elo_changes[key],
                        'winner': piece == game.winner,
                    }, to=sid)
    elif game.winner is None and p2_uid:
        db.record_game(str(p1_uid), str(p2_uid), None, moves, reason)  # Beraberlik (FR-10)

    socketio.emit('game_over', {
        'winner': game.winner,
        'winner_uid': winner_uid,
        'elo_changes': elo_changes,
        'new_ratings': new_ratings,     # Istemci olay sirasina bagli kalmadan ELO'yu gosterebilsin
        'move_count': len(game.move_history),
        'reason': reason,
    }, to=room_id)


def _forfeit_after_grace(room_id: str, piece: int, disconnected_at: float) -> None:
    """Arka plan gorevi: oyuncu sure icinde donmezse rakip hukmen kazanir."""
    socketio.sleep(config.RECONNECT_GRACE_SECONDS)
    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if (not room or room['game'].game_over
                or room['disconnected'].get(piece) != disconnected_at):
            return  # Oyun bitti veya oyuncu geri dondu
        log.info("Oda %s: oyuncu %s geri donmedi, hukmen yenilgi", room_id, piece)
        _finish_game(room_id, room, reason='forfeit', forfeit_loser=piece)


# =============================================================================
# OTOMATIK TEMIZLIK
# =============================================================================

def cleanup_old_games() -> int:
    """Bitmis, rakip bekleyen ve hareketsiz odalari siler. Silinen oda sayisi."""
    now = time.time()
    to_delete = []
    with GAMES_LOCK:
        for room_id, room in GAMES.items():
            idle = now - room['last_move_at']
            if room['game'].game_over:
                if idle > config.FINISHED_TIMEOUT:
                    to_delete.append(room_id)
            elif room['p2_uid'] is None:
                if now - room['created_at'] > config.WAITING_TIMEOUT:
                    to_delete.append(room_id)
            elif idle > config.INACTIVE_TIMEOUT:
                to_delete.append(room_id)

        for room_id in to_delete:
            socketio.emit('game_ended', {'reason': 'timeout'}, to=room_id)
            try:
                close_room(room_id, namespace='/')
            except Exception:
                pass
            GAMES.pop(room_id, None)

    if to_delete:
        log.info("Temizlik: %d oda silindi, aktif: %d", len(to_delete), len(GAMES))
    return len(to_delete)


def start_cleanup_thread() -> None:
    def cleanup_loop():
        while True:
            socketio.sleep(config.CLEANUP_INTERVAL)
            try:
                cleanup_old_games()
            except Exception:
                log.exception("Temizlik hatasi")

    socketio.start_background_task(cleanup_loop)
    log.info("Arka plan temizlik gorevi basladi")


# =============================================================================
# REST API
# =============================================================================

@app.route('/signup', methods=['POST'])
def signup():
    username, password, error = validate_credentials(request.get_json(silent=True))
    if error:
        return jsonify({'error': error}), 400
    if not (config.USERNAME_MIN_LENGTH <= len(username) <= config.USERNAME_MAX_LENGTH):
        return jsonify({'error': f'Username must be {config.USERNAME_MIN_LENGTH}-'
                                 f'{config.USERNAME_MAX_LENGTH} characters'}), 400
    if not _USERNAME_RE.match(username) or username.lower().startswith('misafir_'):
        return jsonify({'error': 'Username contains invalid characters'}), 400
    if not (config.PASSWORD_MIN_LENGTH <= len(password) <= config.PASSWORD_MAX_LENGTH):
        return jsonify({'error': f'Password must be {config.PASSWORD_MIN_LENGTH}-'
                                 f'{config.PASSWORD_MAX_LENGTH} characters'}), 400
    if not db.is_available():
        return jsonify({'error': 'Database unavailable'}), 503

    user_id = db.create_user(username, password)
    if user_id:
        log.info("Yeni kullanici: %s", username)
        return jsonify({'message': 'Created', 'user_id': user_id}), 201
    return jsonify({'error': 'Username already taken'}), 409


@app.route('/login', methods=['POST'])
def login():
    username, password, error = validate_credentials(request.get_json(silent=True))
    if error:
        return jsonify({'error': error}), 400
    if not db.is_available():
        return jsonify({'error': 'Database unavailable'}), 503
    user = db.verify_user(username, password)
    if user:
        log.info("Giris: %s", username)
        return jsonify({'message': 'Success', 'user': user}), 200
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/user/<username>', methods=['GET'])
def get_user(username):
    user = db.get_user_by_username(username)
    if user:
        return jsonify({'user': user}), 200
    return jsonify({'error': 'User not found'}), 404


@app.route('/user/<username>/games', methods=['GET'])
def get_user_games(username):
    if not db.get_user_by_username(username):
        return jsonify({'error': 'User not found'}), 404
    limit = min(max(request.args.get('limit', 20, type=int), 1), 100)
    return jsonify({'games': db.get_user_games(username, limit)}), 200


@app.route('/leaderboard', methods=['GET'])
def leaderboard():
    limit = min(max(request.args.get('limit', 10, type=int), 1), 100)
    return jsonify(db.get_top_players(limit=limit)), 200


@app.route('/active_games', methods=['GET'])
def active_games():
    games_list = []
    with GAMES_LOCK:
        for room_id, room in GAMES.items():
            if room['game'].game_over:
                continue
            p1, p2 = room['p1_info'], room['p2_info']
            games_list.append({
                'room_id': room_id,
                'p1': p1.get('username', 'Player1'),
                'p1_elo': p1.get('rating', config.DEFAULT_RATING),
                'p2': p2.get('username') if p2 else 'Bekleniyor...',
                'p2_elo': p2.get('rating', config.DEFAULT_RATING) if p2 else 0,
                'status': 'PLAYING' if room['p2_uid'] else 'WAITING',
                'move_count': len(room['game'].move_history),
            })
    return jsonify(games_list), 200


@app.route('/cleanup', methods=['POST'])
def manual_cleanup():
    removed = cleanup_old_games()
    return jsonify({'message': 'Cleanup completed', 'removed': removed, 'active_games': len(GAMES)}), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'database': db.is_available(),
        'active_games': len(GAMES),
        'connected_users': len(CONNECTED_USERS),
    }), 200


# =============================================================================
# UNITY WEBGL ISTEMCISI
# =============================================================================
# Oyun ayni origin'den sunuldugu icin REST ve Socket.IO icin CORS gerekmez.
# Unity build'i Gzip ile sikistirilir (Decompression Fallback kapali); tarayicinin
# dosyalari kendisi acabilmesi icin .gz dosyalari Content-Encoding: gzip ve asil
# dosya turunun Content-Type'i ile gonderilir.

_WEB_CONTENT_TYPES = {
    '.wasm': 'application/wasm',
    '.js': 'application/javascript',
    '.data': 'application/octet-stream',
    '.json': 'application/json',
    '.symbols.json': 'application/json',
}


def _web_content_type(name: str) -> Optional[str]:
    for ext in sorted(_WEB_CONTENT_TYPES, key=len, reverse=True):
        if name.endswith(ext):
            return _WEB_CONTENT_TYPES[ext]
    return None


@app.route('/')
def root():
    return redirect('/play/')


@app.route('/play')
def play_redirect():
    return redirect('/play/')


@app.route('/play/', defaults={'path': 'index.html'})
@app.route('/play/<path:path>')
def play(path):
    build_dir = os.path.abspath(config.WEB_BUILD_DIR)
    if not os.path.isfile(os.path.join(build_dir, 'index.html')):
        return jsonify({'error': 'WebGL build bulunamadi',
                        'hint': 'Unity ile build alin (docs/KURULUM.md) veya CONNECT4_WEB_BUILD ayarlayin',
                        'build_dir': build_dir}), 404
    full = os.path.abspath(os.path.join(build_dir, path))
    if not full.startswith(build_dir + os.sep) or not os.path.isfile(full):
        abort(404)

    response = send_from_directory(build_dir, path, conditional=True)
    name = path.lower()
    if name.endswith('.gz') or name.endswith('.br'):
        response.headers['Content-Encoding'] = 'gzip' if name.endswith('.gz') else 'br'
        content_type = _web_content_type(name[:-3])
        if content_type:
            response.headers['Content-Type'] = content_type
    else:
        content_type = _web_content_type(name)
        if content_type:
            response.headers['Content-Type'] = content_type
    if name.endswith('index.html'):
        response.headers['Cache-Control'] = 'no-cache'
    return response


# =============================================================================
# SOCKET.IO OLAYLARI
# =============================================================================

@socketio.on('connect')
def on_connect():
    log.debug("Baglandi: %s", request.sid)


@socketio.on('latency_ping')
def on_latency_ping(data=None):
    """RTT olcumu icin yanki (benchmark ve baglanti kontrolu)."""
    emit('latency_pong', data)


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    CONNECTED_USERS.pop(sid, None)
    log.debug("Ayrildi: %s", sid)

    with GAMES_LOCK:
        for room_id, room in list(GAMES.items()):
            piece = _piece_of(room, sid)
            if piece is None:
                continue
            if room['p2_uid'] is None:
                log.info("Oda %s silindi (kurucu beklerken ayrildi)", room_id)
                GAMES.pop(room_id, None)
            elif not room['game'].game_over:
                now = time.time()
                room['disconnected'][piece] = now
                socketio.emit('opponent_disconnected', {
                    'msg': 'Rakip ayrildi',
                    'grace_seconds': config.RECONNECT_GRACE_SECONDS,
                }, to=room_id)
                socketio.start_background_task(_forfeit_after_grace, room_id, piece, now)


@socketio.on('create_game')
def on_create_game(data):
    user_id = _clean_str(data, 'user_id', config.USERNAME_MAX_LENGTH + 20)
    if not user_id:
        emit('error', {'msg': 'Gecersiz kullanici'})
        return

    user_info = get_user_info(user_id)
    with GAMES_LOCK:
        # Kullanicinin onceki bekleyen odasi varsa sil (tek bekleyen oda kurali)
        existing = get_user_waiting_game(user_id)
        if existing:
            GAMES.pop(existing, None)
            try:
                close_room(existing)
            except Exception:
                pass
        room_id = generate_room_id()
        while room_id in GAMES:
            room_id = generate_room_id()
        GAMES[room_id] = _new_room(request.sid, user_id, user_info)

    CONNECTED_USERS[request.sid] = user_id
    join_room(room_id)
    log.info("Oda %s olusturuldu: %s", room_id, user_id)
    emit('game_created', {'room_id': room_id, 'player_piece': PLAYER1_PIECE, 'your_info': user_info})


@socketio.on('join_game')
def on_join_game(data):
    room_id = (_clean_str(data, 'room_id', 10) or '').upper()
    user_id = _clean_str(data, 'user_id', config.USERNAME_MAX_LENGTH + 20)
    if not _ROOM_ID_RE.match(room_id) or not user_id:
        emit('error', {'msg': 'Gecersiz istek'})
        return

    user_info = get_user_info(user_id)
    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if room is None:
            emit('error', {'msg': 'Oda bulunamadi'})
            return
        game: ConnectFourGame = room['game']
        CONNECTED_USERS[request.sid] = user_id

        # 1) Oyunculardan biri geri donuyor (yeniden baglanma)
        own_piece = (PLAYER1_PIECE if room['p1_uid'] == user_id else
                     PLAYER2_PIECE if room['p2_uid'] == user_id else None)
        if own_piece is not None:
            if room['p2_uid'] is None:
                emit('error', {'msg': 'Kendi oyununuza katilamazsiniz'})
                return
            if own_piece not in room['disconnected'] and _sid_of(room, own_piece) != request.sid:
                emit('error', {'msg': 'Bu oyuna zaten bagli durumdasiniz'})
                return
            room['disconnected'].pop(own_piece, None)
            room['p1_sid' if own_piece == PLAYER1_PIECE else 'p2_sid'] = request.sid
            join_room(room_id)
            opponent_info = room['p2_info'] if own_piece == PLAYER1_PIECE else room['p1_info']
            log.info("Oda %s: %s yeniden baglandi", room_id, user_id)
            emit('game_joined', {
                'room_id': room_id, 'player_piece': own_piece, 'role': 'player',
                'rejoined': True, 'current_state': game.to_dict(), 'opponent_info': opponent_info,
            })
            emit('opponent_reconnected', {'msg': 'Rakip geri dondu'}, to=room_id, include_self=False)
            return

        join_room(room_id)

        # 2) Ikinci oyuncu olarak katil
        if room['p2_uid'] is None:
            room['p2_sid'], room['p2_uid'], room['p2_info'] = request.sid, user_id, user_info
            room['last_move_at'] = time.time()
            p1_info = room['p1_info']
            log.info("Oda %s: %s P2 olarak katildi", room_id, user_id)

            emit('game_joined', {'room_id': room_id, 'player_piece': PLAYER2_PIECE,
                                 'role': 'player', 'opponent_info': p1_info})
            for sid, opponent in ((room['p1_sid'], user_info), (request.sid, p1_info)):
                emit('game_start', {
                    'msg': 'Oyun Basladi!', 'p1_info': p1_info, 'p2_info': user_info,
                    'opponent_name': opponent.get('username', ''),
                    'opponent_elo': opponent.get('rating', config.DEFAULT_RATING),
                }, to=sid)
            return

        # 3) Seyirci
        log.info("Oda %s: seyirci %s", room_id, user_id)
        emit('game_joined', {
            'room_id': room_id, 'player_piece': 0, 'role': 'spectator',
            'current_state': game.to_dict(),
            'p1_info': room['p1_info'], 'p2_info': room['p2_info'],
        })


@socketio.on('make_move')
def on_make_move(data):
    room_id = (_clean_str(data, 'room_id', 10) or '').upper()
    col = data.get('col') if isinstance(data, dict) else None
    player_piece = data.get('player_piece') if isinstance(data, dict) else None

    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if room is None:
            emit('error', {'msg': 'Oda bulunamadi'})
            return
        game: ConnectFourGame = room['game']

        if room['p2_uid'] is None:
            emit('error', {'msg': 'Rakip bekleniyor!'})
            return
        # Hamleyi gonderen baglanti gercekten o tasin sahibi mi?
        if player_piece not in (PLAYER1_PIECE, PLAYER2_PIECE) or request.sid != _sid_of(room, player_piece):
            emit('error', {'msg': 'Bu oyunda hamle yapma yetkiniz yok!'})
            return
        if not isinstance(col, int) or isinstance(col, bool):
            emit('error', {'msg': 'Gecersiz hamle!'})
            return
        if game.game_over:
            emit('error', {'msg': 'Oyun bitti'})
            return
        if game.current_player != player_piece:
            emit('error', {'msg': 'Sira sizde degil!'})
            return
        if not game.make_move(col):
            emit('error', {'msg': 'Gecersiz hamle!'})
            return

        room['last_move_at'] = time.time()
        response = game.to_dict()
        response['col'] = col
        emit('move_made', response, to=room_id)

        if game.game_over:
            _finish_game(room_id, room)


@socketio.on('leave_game')
def on_leave_game(data):
    """Oyuncu bilerek ayrilir: aktif oyunda hukmen yenilgi, bekleyen odada oda silinir."""
    room_id = (_clean_str(data, 'room_id', 10) or '').upper()
    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if room is None:
            return
        piece = _piece_of(room, request.sid)
        leave_room(room_id)
        if piece is None:
            return  # Seyirci
        if room['p2_uid'] is None:
            GAMES.pop(room_id, None)
            log.info("Oda %s iptal edildi", room_id)
        elif not room['game'].game_over:
            if piece == PLAYER1_PIECE:
                room['p1_sid'] = None
            else:
                room['p2_sid'] = None
            room['disconnected'][piece] = time.time()
            log.info("Oda %s: oyuncu %s oyunu terk etti", room_id, piece)
            _finish_game(room_id, room, reason='forfeit', forfeit_loser=piece)


# =============================================================================
# SUNUCU BASLATMA
# =============================================================================

def main() -> None:
    db_ok = db.init_db()
    log.info("=" * 50)
    log.info("CONNECT FOUR PRO SERVER v3.0")
    log.info("Dinleniyor: http://%s:%d", config.SERVER_HOST, config.SERVER_PORT)
    log.info("Veritabani: %s", "bagli" if db_ok else "YOK (sadece misafir modu)")
    log.info("Yeniden baglanma suresi: %ds", config.RECONNECT_GRACE_SECONDS)
    log.info("=" * 50)
    start_cleanup_thread()
    socketio.run(app, host=config.SERVER_HOST, port=config.SERVER_PORT,
                 debug=False, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.info("Sunucu kapatiliyor...")
