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
  * Kayitli kimlik sadece /login (veya /signup) ile verilen imzali `token` ile
    kanitlanir; token'siz baglantilar misafirdir ve ELO'yu etkilemez
  * Yeniden baglanan misafir, oda olusturulurken/katilirken verilen
    `rejoin_token` ile koltugunu geri alir (baska misafir adini kullanamaz)
  * Baglantisi kopan oyuncu RECONNECT_GRACE_SECONDS icinde geri donebilir,
    donmezse rakip hukmen kazanir (NFR-08)
  * Hatali girisler kullanici adi basina, /login + /signup istekleri IP basina
    sinirlanir (HTTP 429 + Retry-After)
  * Bekleyen / hareketsiz / bitmis odalar otomatik temizlenir
  * Tum oda durumuna erisim tek bir kilitle korunur (thread-safe)
"""

import hmac
import math
import os
import random
import re
import secrets
import string
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, abort, jsonify, redirect, request, send_from_directory
from flask_socketio import SocketIO, close_room, emit, join_room, leave_room
from itsdangerous import BadSignature, URLSafeTimedSerializer

import config
import database as db
from game_core import PLAYER1_PIECE, PLAYER2_PIECE, ConnectFourGame, other_player

log = config.get_logger("server")

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
# cors_allowed_origins=None: tarayicidan sadece ayni origin (bkz. config.CORS_ALLOWED_ORIGINS)
socketio = SocketIO(app, cors_allowed_origins=config.CORS_ALLOWED_ORIGINS, async_mode='threading')

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

# Oturum token'i: SECRET_KEY ile imzali kullanici adi (SECRET_KEY ayarlanmazsa
# her sunucu baslangicinda degisir ve eski token'lar gecersiz olur)
_session_signer = URLSafeTimedSerializer(config.SECRET_KEY, salt='connect4-session')


# =============================================================================
# ISTEK SINIRLAMA
# =============================================================================

class AttemptLimiter:
    """Anahtar basina kayan pencerede deneme sayaci (bellek ici, thread-safe)."""

    MAX_KEYS = 10_000

    def __init__(self) -> None:
        self._attempts: Dict[str, List[float]] = {}   # anahtar -> deneme zamanlari
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: int) -> int:
        """
        Denemeyi sayar ve 0 dondurur; pencere icinde `limit` dolmussa saymaz ve
        beklenmesi gereken saniyeyi dondurur. limit/window <= 0 ise sinir kapalidir.
        """
        if limit <= 0 or window <= 0:
            return 0
        now = time.time()
        with self._lock:
            recent = [t for t in self._attempts.get(key, ()) if t > now - window]
            if len(recent) >= limit:
                self._attempts[key] = recent
                return max(1, math.ceil(recent[-limit] + window - now))
            if key not in self._attempts and len(self._attempts) >= self.MAX_KEYS:
                self._prune(now - window)
            recent.append(now)
            self._attempts[key] = recent
            return 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._attempts.clear()

    def _prune(self, cutoff: float) -> None:
        """Suresi dolan anahtarlari siler; yine de doluysa en eski yarisini atar."""
        self._attempts = {k: v for k, v in self._attempts.items() if v[-1] > cutoff}
        if len(self._attempts) >= self.MAX_KEYS:
            newest = sorted(self._attempts.items(), key=lambda kv: kv[1][-1])[self.MAX_KEYS // 2:]
            self._attempts = dict(newest)


LOGIN_LIMITER = AttemptLimiter()     # kullanici adi -> hatali girisler
AUTH_IP_LIMITER = AttemptLimiter()   # istemci IP'si -> /login + /signup istekleri


def _too_many_requests(retry_after: int):
    response = jsonify({'error': 'Too many attempts, try again later', 'retry_after': retry_after})
    response.status_code = 429
    response.headers['Retry-After'] = str(retry_after)
    return response


def _auth_ip_limited():
    """IP siniri dolduysa 429 yaniti, degilse None. X-Forwarded-For'a guvenilmez."""
    wait = AUTH_IP_LIMITER.hit(request.remote_addr or 'unknown',
                               config.AUTH_IP_MAX_REQUESTS, config.AUTH_IP_WINDOW_SECONDS)
    return _too_many_requests(wait) if wait else None


# =============================================================================
# YARDIMCI FONKSIYONLAR
# =============================================================================

def generate_room_id(length: int = 5) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def guest_info(username: str) -> Dict[str, Any]:
    return {'username': str(username), 'rating': config.DEFAULT_RATING,
            'wins': 0, 'losses': 0, 'guest': True}


def get_user_info(username: Optional[str]) -> Dict[str, Any]:
    """Kayitli kullanici bilgisi; kayitli degilse (misafir) varsayilan profil."""
    if username:
        user = db.get_user_by_username(str(username))
        if user:
            user['guest'] = False
            return user
    return guest_info(str(username))


def issue_session_token(username: str) -> str:
    return _session_signer.dumps(username)


def verify_session_token(token: Any) -> Optional[str]:
    """Gecerli ve suresi dolmamis token'in kullanici adi; degilse None."""
    if not isinstance(token, str) or not token or len(token) > 512:
        return None
    try:
        username = _session_signer.loads(token, max_age=config.SESSION_MAX_AGE)
    except BadSignature:   # SignatureExpired da BadSignature alt sinifidir
        return None
    return username if isinstance(username, str) else None


def resolve_player(data: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool, Optional[str]]:
    """
    Socket verisinden oyuncu kimligi: (kullanici, profil, kayitli_mi, hata_mesaji).
    `token` varsa kayitli kullanici odur ve `user_id` yok sayilir. Token yoksa
    `user_id` misafir adidir; kayitli bir kullanicinin adi misafir olarak kullanilamaz.
    """
    token = data.get('token') if isinstance(data, dict) else None
    if token is not None:
        username = verify_session_token(token)
        if not username:
            return None, None, False, 'Oturum gecersiz, tekrar giris yapin'
        user = db.get_user_by_username(username)
        if not user:
            return None, None, False, 'Oturum gecersiz, tekrar giris yapin'
        user['guest'] = False
        return username, user, True, None

    # Misafir adi rakibe ve lobide gosterilir: kullanici adiyla ayni karakter kumesi
    user_id = _clean_str(data, 'user_id', config.GUEST_NAME_MAX_LENGTH + 1)
    if not user_id or len(user_id) > config.GUEST_NAME_MAX_LENGTH or not _USERNAME_RE.match(user_id):
        return None, None, False, 'Gecersiz kullanici'
    if db.get_user_by_username(user_id):
        return None, None, False, 'Bu kullanici adi kayitli, giris yapin'
    return user_id, guest_info(user_id), False, None


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


def _new_room(p1_sid: str, p1_uid: str, p1_info: dict, p1_auth: bool = False) -> Dict[str, Any]:
    now = time.time()
    return {
        'game': ConnectFourGame(),
        # *_auth: kimlik token ile dogrulandi; *_rejoin: koltugu geri alma anahtari
        'p1_sid': p1_sid, 'p1_uid': p1_uid, 'p1_info': p1_info,
        'p1_auth': p1_auth, 'p1_rejoin': secrets.token_urlsafe(16),
        'p2_sid': None, 'p2_uid': None, 'p2_info': None,
        'p2_auth': False, 'p2_rejoin': None,
        'created_at': now,
        'last_move_at': now,
        'disconnected': {},      # piece -> kopma zamani (bitmis odada: ayrilma zamani)
        'end_reason': None,
        'result': None,          # Bitmis oyunun game_over yuku (sonradan donenlere gosterilir)
        'turn_deadline': None,   # Sirasi gelen oyuncunun son hamle zamani; None = sure yok
        'rematch': set(),        # Oyun bittikten sonra rovans isteyen koltuklar (piece)
        'game_no': 1,            # Odadaki kacinci oyun
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


def _seat_key(piece: int) -> str:
    return 'p1' if piece == PLAYER1_PIECE else 'p2'


def _clock_paused(room: dict) -> bool:
    """Sirasi gelen oyuncu hazir ama rakibi kopuk: bekleyen oyuncu rakibin yokluguyla
    cezalandirilmaz; kopuk oyuncuyu RECONNECT_GRACE_SECONDS sonunda hukmen yenilgi bitirir."""
    game = room['game']
    return (not game.game_over and room['p2_uid'] is not None
            and other_player(game.current_player) in room['disconnected'])


def _clock_fields(room: dict) -> Dict[str, Any]:
    """Istemci geri sayimi icin: kalan sure TAM saniye (saat farki onemsiz); sure yoksa None."""
    deadline = room.get('turn_deadline')
    if _clock_paused(room):
        deadline = None
    return {
        'move_time': config.MOVE_TIME_SECONDS,
        'turn_seconds_left': None if deadline is None else max(0, math.ceil(deadline - time.time())),
    }


def _start_turn_clock(room: dict) -> None:
    """Sirasi gelen oyuncu icin hamle suresini baslatir (sure kapaliysa/oyun bittiyse None)."""
    if config.MOVE_TIME_SECONDS > 0 and room['p2_uid'] and not room['game'].game_over:
        room['turn_deadline'] = time.time() + config.MOVE_TIME_SECONDS
    else:
        room['turn_deadline'] = None


def _deadline_passed(room: dict) -> bool:
    deadline = room.get('turn_deadline')
    return deadline is not None and time.time() > deadline + config.MOVE_TIME_GRACE_SECONDS


def get_user_waiting_game(user_id: str, authenticated: Optional[bool] = None) -> Optional[str]:
    with GAMES_LOCK:
        for room_id, room in GAMES.items():
            if (room['p1_uid'] == user_id and room['p2_uid'] is None
                    and (authenticated is None or room['p1_auth'] == authenticated)):
                return room_id
    return None


# =============================================================================
# OYUN SONU
# =============================================================================

def _finish_game(room_id: str, room: dict, reason: str = 'normal',
                 forfeit_loser: Optional[int] = None, detail: Optional[str] = None) -> None:
    """
    Oyunu sonlandirir: ELO gunceller, oyunu kaydeder, odaya game_over yayinlar.
    GAMES_LOCK tutulurken cagrilmalidir.
    """
    game: ConnectFourGame = room['game']
    if forfeit_loser is not None:
        game.game_over = True
        game.winner = other_player(forfeit_loser)
    room['end_reason'] = reason
    room['turn_deadline'] = None
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

    # Sadece iki kimligi de token ile dogrulanmis oyuncular puanlanir/kaydedilir
    rated = room['p1_auth'] and room['p2_auth']
    if rated and winner_uid and loser_uid:
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
    elif rated and game.winner is None and p2_uid:
        db.record_game(str(p1_uid), str(p2_uid), None, moves, reason)  # Beraberlik (FR-10)

    result = {
        'winner': game.winner,
        'winner_uid': winner_uid,
        'elo_changes': elo_changes,
        'new_ratings': new_ratings,     # Istemci olay sirasina bagli kalmadan ELO'yu gosterebilsin
        'move_count': len(game.move_history),
        'reason': reason,
        # Eski istemciler `reason`a bakar; ayrinti ('timeout', 'disconnect', 'leave') ek bilgidir
        'detail': detail,
    }
    room['result'] = result   # Oyuncu yokken biten oyuna sonradan donenlere game_joined'da verilir
    socketio.emit('game_over', result, to=room_id)


def _forfeit_after_grace(room_id: str, piece: int, disconnected_at: float) -> None:
    """Arka plan gorevi: oyuncu sure icinde donmezse rakip hukmen kazanir."""
    socketio.sleep(config.RECONNECT_GRACE_SECONDS)
    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if (not room or room['game'].game_over
                or room['disconnected'].get(piece) != disconnected_at):
            return  # Oyun bitti veya oyuncu geri dondu
        log.info("Oda %s: oyuncu %s geri donmedi, hukmen yenilgi", room_id, piece)
        _finish_game(room_id, room, reason='forfeit', forfeit_loser=piece, detail='disconnect')


def enforce_move_deadlines() -> int:
    """Hamle suresi dolan oyuncuyu hukmen yenik sayar. Bitirilen oyun sayisi."""
    finished = 0
    with GAMES_LOCK:
        for room_id, room in list(GAMES.items()):
            game = room['game']
            if (room['p2_uid'] is None or game.game_over or not _deadline_passed(room)
                    or _clock_paused(room)):
                continue
            log.info("Oda %s: oyuncu %s hamle suresini asti", room_id, game.current_player)
            _finish_game(room_id, room, reason='forfeit', forfeit_loser=game.current_player,
                         detail='timeout')
            finished += 1
    return finished


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

    def move_clock_loop():
        # Tek gorev tum odalara bakar; hamle basina gorev acilmaz
        while True:
            socketio.sleep(1)
            try:
                enforce_move_deadlines()
            except Exception:
                log.exception("Hamle suresi denetimi hatasi")

    socketio.start_background_task(cleanup_loop)
    log.info("Arka plan temizlik gorevi basladi")
    if config.MOVE_TIME_SECONDS > 0:
        socketio.start_background_task(move_clock_loop)
        log.info("Hamle suresi: %ds", config.MOVE_TIME_SECONDS)


# =============================================================================
# REST API
# =============================================================================

@app.route('/signup', methods=['POST'])
def signup():
    limited = _auth_ip_limited()
    if limited:
        return limited
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
        return jsonify({'message': 'Created', 'user_id': user_id,
                        'token': issue_session_token(username)}), 201
    return jsonify({'error': 'Username already taken'}), 409


@app.route('/login', methods=['POST'])
def login():
    limited = _auth_ip_limited()
    if limited:
        return limited
    username, password, error = validate_credentials(request.get_json(silent=True))
    if error:
        return jsonify({'error': error}), 400
    if not db.is_available():
        return jsonify({'error': 'Database unavailable'}), 503
    # Deneme, sifre kontrolunden ONCE sayilir (es zamanli tahminler siniri asamasin);
    # kilitliyken PBKDF2 calistirilmaz, basarili giris sayaci sifirlar.
    attempt_key = username[:64]
    wait = LOGIN_LIMITER.hit(attempt_key, config.LOGIN_MAX_FAILURES, config.LOGIN_LOCKOUT_SECONDS)
    if wait:
        log.warning("Giris kilitli: %s (%ds)", attempt_key, wait)
        return _too_many_requests(wait)
    user = db.verify_user(username, password)
    if user:
        LOGIN_LIMITER.reset(attempt_key)
        log.info("Giris: %s", username)
        return jsonify({'message': 'Success', 'user': user,
                        'token': issue_session_token(user['username'])}), 200
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


def _seat_left_finished(room_id: str, room: dict, piece: int) -> None:
    """Bitmis odada bir oyuncu ayrildi: rovans teklifi gecersiz. GAMES_LOCK tutulurken cagrilir."""
    room['disconnected'][piece] = time.time()
    room['rematch'].discard(piece)
    socketio.emit('rematch_unavailable', {'room_id': room_id, 'reason': 'opponent_left'}, to=room_id)


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
            elif room['game'].game_over:
                # Bitmis oyun: forfeit yok, sadece rovans artik mumkun degil
                _seat_left_finished(room_id, room, piece)
            else:
                now = time.time()
                room['disconnected'][piece] = now
                socketio.emit('opponent_disconnected', {
                    'msg': 'Rakip ayrildi',
                    'grace_seconds': config.RECONNECT_GRACE_SECONDS,
                }, to=room_id)
                socketio.start_background_task(_forfeit_after_grace, room_id, piece, now)


@socketio.on('create_game')
def on_create_game(data):
    user_id, user_info, authenticated, error = resolve_player(data)
    if error:
        emit('error', {'msg': error})
        return

    with GAMES_LOCK:
        # Kullanicinin onceki bekleyen odasi varsa sil (tek bekleyen oda kurali).
        # Misafir adi kanit olmadigindan baska baglantinin odasina dokunulmaz.
        existing = get_user_waiting_game(user_id, authenticated)
        if existing and not authenticated and GAMES[existing]['p1_sid'] != request.sid:
            emit('error', {'msg': 'Bu misafir adi kullanimda'})
            return
        if existing:
            GAMES.pop(existing, None)
            try:
                close_room(existing)
            except Exception:
                pass
        room_id = generate_room_id()
        while room_id in GAMES:
            room_id = generate_room_id()
        GAMES[room_id] = _new_room(request.sid, user_id, user_info, authenticated)
        rejoin_token = GAMES[room_id]['p1_rejoin']

    CONNECTED_USERS[request.sid] = user_id
    join_room(room_id)
    log.info("Oda %s olusturuldu: %s", room_id, user_id)
    emit('game_created', {'room_id': room_id, 'player_piece': PLAYER1_PIECE, 'your_info': user_info,
                          'rejoin_token': rejoin_token})


@socketio.on('join_game')
def on_join_game(data):
    room_id = (_clean_str(data, 'room_id', 10) or '').upper()
    if not _ROOM_ID_RE.match(room_id):
        emit('error', {'msg': 'Gecersiz istek'})
        return
    user_id, user_info, authenticated, error = resolve_player(data)
    if error:
        emit('error', {'msg': 'Gecersiz istek' if error == 'Gecersiz kullanici' else error})
        return

    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if room is None:
            emit('error', {'msg': 'Oda bulunamadi'})
            return
        game: ConnectFourGame = room['game']
        CONNECTED_USERS[request.sid] = user_id

        # 1) Oyunculardan biri geri donuyor (yeniden baglanma)
        own_piece = None
        for piece in (PLAYER1_PIECE, PLAYER2_PIECE):
            key = _seat_key(piece)
            if room[f'{key}_uid'] == user_id and room[f'{key}_auth'] == authenticated:
                own_piece = piece
                break
        if own_piece is not None:
            key = _seat_key(own_piece)
            if room['p2_uid'] is None:
                emit('error', {'msg': 'Kendi oyununuza katilamazsiniz'})
                return
            old_sid = _sid_of(room, own_piece)
            # Bir baglanti iki koltugu birden tutamaz
            if _sid_of(room, other_player(own_piece)) == request.sid:
                emit('error', {'msg': 'Bu oyuna zaten bagli durumdasiniz'})
                return
            # Misafirin adi kanit degildir; koltugu sadece anahtarin sahibi geri alir.
            given = data.get('rejoin_token') if isinstance(data, dict) else None
            token_ok = (isinstance(given, str) and given.isascii() and bool(room[f'{key}_rejoin'])
                        and hmac.compare_digest(given, room[f'{key}_rejoin']))
            seat_alive = own_piece not in room['disconnected'] and old_sid != request.sid
            # Sunucunun hala bagli saydigi koltuk icin kayitli oyuncu da anahtari gostermeli
            # (sizan bir oturum token'i canli oyuncuyu atamasin); kopuk koltuk icin token yeter
            proof = token_ok if seat_alive else (authenticated or token_ok)
            if seat_alive and not proof:
                emit('error', {'msg': 'Bu oyuna zaten bagli durumdasiniz'})
                return
            if not proof:
                emit('error', {'msg': 'Yeniden baglanma anahtari gecersiz'})
                return
            if seat_alive and old_sid:
                # Sunucu eski soketin oldugunu henuz fark etmedi (ping zaman asimi): kanitli
                # yeni baglanti koltugu devralir, eski soket odadan cikarilir
                emit('error', {'msg': 'Baska bir baglantidan oyuna girildi'}, to=old_sid)
                leave_room(room_id, sid=old_sid)
            was_disconnected = own_piece in room['disconnected']
            room['disconnected'].pop(own_piece, None)
            room[f'{key}_sid'] = request.sid
            join_room(room_id)
            if was_disconnected and not game.game_over and own_piece != game.current_player:
                _start_turn_clock(room)   # Bekleyen oyuncu doneni karsilayinca hemen suresiz kalmasin
            opponent_info = room['p2_info'] if own_piece == PLAYER1_PIECE else room['p1_info']
            log.info("Oda %s: %s yeniden baglandi", room_id, user_id)
            joined = {
                'room_id': room_id, 'player_piece': own_piece, 'role': 'player',
                'rejoined': True, 'current_state': game.to_dict(), 'opponent_info': opponent_info,
                'rejoin_token': room[f'{key}_rejoin'], 'game_no': room['game_no'],
                **_clock_fields(room),
            }
            if game.game_over:
                joined['result'] = room['result']   # Oyuncu yokken biten oyunun sonucu
            emit('game_joined', joined)
            if was_disconnected:
                emit('opponent_reconnected', {'msg': 'Rakip geri dondu'}, to=room_id, include_self=False)
            return

        join_room(room_id)

        # 2) Ikinci oyuncu olarak katil
        if room['p2_uid'] is None:
            room['p2_sid'], room['p2_uid'], room['p2_info'] = request.sid, user_id, user_info
            room['p2_auth'], room['p2_rejoin'] = authenticated, secrets.token_urlsafe(16)
            room['last_move_at'] = time.time()
            _start_turn_clock(room)
            p1_info = room['p1_info']
            log.info("Oda %s: %s P2 olarak katildi", room_id, user_id)

            emit('game_joined', {'room_id': room_id, 'player_piece': PLAYER2_PIECE,
                                 'role': 'player', 'opponent_info': p1_info,
                                 'rejoin_token': room['p2_rejoin']})
            for sid, opponent in ((room['p1_sid'], user_info), (request.sid, p1_info)):
                emit('game_start', {
                    'msg': 'Oyun Basladi!', 'p1_info': p1_info, 'p2_info': user_info,
                    'opponent_name': opponent.get('username', ''),
                    'opponent_elo': opponent.get('rating', config.DEFAULT_RATING),
                    **_clock_fields(room),
                }, to=sid)
            return

        # 3) Seyirci
        log.info("Oda %s: seyirci %s", room_id, user_id)
        spectator_view = {
            'room_id': room_id, 'player_piece': 0, 'role': 'spectator',
            'current_state': game.to_dict(),
            'p1_info': room['p1_info'], 'p2_info': room['p2_info'],
            'game_no': room['game_no'], **_clock_fields(room),
        }
        if game.game_over:
            spectator_view['result'] = room['result']
        emit('game_joined', spectator_view)


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
        if _deadline_passed(room) and not _clock_paused(room):
            # Izleyici gorevi henuz calismamis olsa bile gec gelen hamle gecersizdir
            _finish_game(room_id, room, reason='forfeit', forfeit_loser=player_piece, detail='timeout')
            return
        if not game.make_move(col):
            emit('error', {'msg': 'Gecersiz hamle!'})
            return

        room['last_move_at'] = time.time()
        _start_turn_clock(room)
        response = game.to_dict()
        response['col'] = col
        response.update(_clock_fields(room))
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
            _finish_game(room_id, room, reason='forfeit', forfeit_loser=piece, detail='leave')
        else:
            room[f'{_seat_key(piece)}_sid'] = None
            _seat_left_finished(room_id, room, piece)


@socketio.on('rematch_request')
def on_rematch_request(data=None):
    """Bitmis odada ayni rakiple yeni oyun: iki koltuk da istemeli; koltuklar yer degistirir."""
    room_id = (_clean_str(data, 'room_id', 10) or '').upper()
    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if room is None:
            emit('error', {'msg': 'Oda bulunamadi'})
            return
        piece = _piece_of(room, request.sid)
        if piece is None:
            emit('error', {'msg': 'Sadece oyuncular rovans isteyebilir'})
            return
        if not room['game'].game_over:
            emit('error', {'msg': 'Oyun devam ediyor'})
            return
        other = other_player(piece)
        if other in room['disconnected'] or _sid_of(room, other) is None:
            emit('rematch_unavailable', {'room_id': room_id, 'reason': 'opponent_left'})
            return
        if piece in room['rematch']:
            return   # Tekrarlanan istek yeni bir sey baslatmaz
        room['rematch'].add(piece)
        if other in room['rematch']:
            _start_rematch(room_id, room)
        else:
            emit('rematch_offered', {'room_id': room_id, 'from_piece': piece,
                                     'from': _uid_of(room, piece)}, to=room_id)


def _start_rematch(room_id: str, room: dict) -> None:
    """
    Ayni odada yeni oyun: onceki P2 kirmizi/P1 olur ve ilk hamleyi yapar (istemciler
    oyunu hep P1 baslatir varsayar). Rejoin anahtari ve kimlik koltukla birlikte tasinir.
    GAMES_LOCK tutulurken cagrilmalidir.
    """
    for field in ('sid', 'uid', 'info', 'auth', 'rejoin'):
        room[f'p1_{field}'], room[f'p2_{field}'] = room[f'p2_{field}'], room[f'p1_{field}']
    for key in ('p1', 'p2'):
        if room[f'{key}_auth']:   # Onceki oyunun ELO'su yeni oyunda gorunsun
            fresh = get_user_info(room[f'{key}_uid'])
            if not fresh.get('guest'):
                room[f'{key}_info'] = fresh

    now = time.time()
    room['game'] = ConnectFourGame()
    room['created_at'] = room['last_move_at'] = now
    room['disconnected'] = {}
    room['end_reason'] = None
    room['result'] = None
    room['rematch'] = set()
    room['game_no'] += 1
    _start_turn_clock(room)
    log.info("Oda %s: rovans basladi (oyun %d)", room_id, room['game_no'])

    p1_info, p2_info = room['p1_info'], room['p2_info']
    for piece, opponent in ((PLAYER1_PIECE, p2_info), (PLAYER2_PIECE, p1_info)):
        sid = _sid_of(room, piece)
        if not sid:
            continue   # to=None tum istemcilere yayin yapar
        socketio.emit('game_start', {
            'msg': 'Rovans basladi!', 'room_id': room_id, 'player_piece': piece,
            'rematch': True, 'game_no': room['game_no'],
            'p1_info': p1_info, 'p2_info': p2_info,
            'opponent_name': opponent.get('username', ''),
            'opponent_elo': opponent.get('rating', config.DEFAULT_RATING),
            **_clock_fields(room),
        }, to=sid)
    # Seyirciler (ve oyuncular) icin bos tahta + yeni koltuk dagilimi
    socketio.emit('rematch_started', {
        'room_id': room_id, 'game_no': room['game_no'], 'p1_info': p1_info, 'p2_info': p2_info,
        'current_state': room['game'].to_dict(), **_clock_fields(room),
    }, to=room_id)


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
