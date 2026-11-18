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
# cors_allowed_origins=None: tarayicidan sadece ayni origin (bkz. config.CORS_ALLOWED_ORIGINS);
# ayni ayar REST API'nin CORS basliklarini da belirler (bkz. _cors_headers)
# cors_credentials=False: kimlik cerezle degil mesajdaki token'la tasinir. engineio'nun varsayilani
# (True) Access-Control-Allow-Credentials gonderir; `*` ile bu, her siteye kimlik bilgili erisim olurdu
socketio = SocketIO(app, cors_allowed_origins=config.CORS_ALLOWED_ORIGINS, cors_credentials=False,
                    async_mode='threading')

# Werkzeug istek loglari cok gurultulu
config.get_logger("werkzeug").setLevel("ERROR")

# room_id -> oda sozlugu (bkz. _new_room)
GAMES: Dict[str, Dict[str, Any]] = {}
# sid -> username
CONNECTED_USERS: Dict[str, str] = {}
GAMES_LOCK = threading.RLock()
# Hizli eslesme kuyrugu (GAMES_LOCK altinda degisir): {'sid', 'uid', 'info', 'auth'};
# ilk giren P1 olur. Ayni kimlik (uid, auth) ve ayni soket kuyrukta en fazla bir kez bulunur.
QUICK_QUEUE: List[Dict[str, Any]] = []

# Hazir sohbet: gecerli mesaj kimlikleri 0..QUICK_CHAT_COUNT-1; soket basina en az
# CHAT_MIN_INTERVAL saniye arayla. LAST_CHAT_AT: sid -> son kabul edilen mesajin zamani
QUICK_CHAT_COUNT = 8
CHAT_MIN_INTERVAL = 2.0
LAST_CHAT_AT: Dict[str, float] = {}

# Sureli mac (satranc saati): ad -> {'base': baslangic saniyesi, 'inc': hamle basina ek sure}.
# Bilinmeyen ad suresiz oda demektir. Hizli eslesme her zaman QUICK_TIME_CONTROL kurar.
TIME_CONTROLS: Dict[str, Dict[str, int]] = {'3+2': {'base': 180, 'inc': 2}}
QUICK_TIME_CONTROL = '3+2'

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


# Socket hata mesajlari: 'msg' eski istemciler (pygame) icin Turkce ASCII kalir;
# 'code' sabittir, Unity istemcisi metni secili dilde kendisi gosterir.
ERROR_CODES = {
    'Oturum gecersiz, tekrar giris yapin': 'session_invalid',
    'Gecersiz kullanici': 'invalid_user',
    'Bu kullanici adi kayitli, giris yapin': 'name_registered',
    'Bu misafir adi kullanimda': 'guest_name_taken',
    'Gecersiz istek': 'invalid_request',
    'Oda bulunamadi': 'room_not_found',
    'Kendi oyununuza katilamazsiniz': 'own_game',
    'Bu oyuna zaten bagli durumdasiniz': 'already_connected',
    'Yeniden baglanma anahtari gecersiz': 'bad_resume_token',
    'Baska bir baglantidan oyuna girildi': 'replaced_by_other_connection',
    'Rakip bekleniyor!': 'waiting_opponent',
    'Bu oyunda hamle yapma yetkiniz yok!': 'not_a_player',
    'Gecersiz hamle!': 'invalid_move',
    'Oyun bitti': 'game_over',
    'Sira sizde degil!': 'not_your_turn',
    'Sadece oyuncular rovans isteyebilir': 'rematch_players_only',
    'Oyun devam ediyor': 'game_in_progress',
    'Zaten bir oyundasiniz': 'already_in_game',
}


def _emit_error(msg: str, **kwargs: Any) -> None:
    """Hata olayini msg + sabit code ile gonderir."""
    emit('error', {'msg': msg, 'code': ERROR_CODES.get(msg, 'error')}, **kwargs)


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


def _parse_time_control(value: Any) -> Optional[str]:
    """Istemcinin gonderdigi sure adi; bilinmeyen/gecersiz deger None (suresiz)."""
    return value if isinstance(value, str) and value in TIME_CONTROLS else None


def _new_room(p1_sid: str, p1_uid: str, p1_info: dict, p1_auth: bool = False,
              time_control: Optional[str] = None) -> Dict[str, Any]:
    now = time.time()
    tc = TIME_CONTROLS.get(time_control) if time_control else None
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
        # Satranc saati: time_control None = suresiz oda (turn_deadline/MOVE_TIME_SECONDS isler).
        # clock: piece -> kalan saniye (sirasi gelenin degeri clock_turn_started'tan beri
        # gecen sure dusulmeden tutulur); clock_turn_started: sira baslangici (pay dahil)
        'time_control': dict(tc) if tc else None,
        'clock': {PLAYER1_PIECE: float(tc['base']), PLAYER2_PIECE: float(tc['base'])} if tc else None,
        'clock_turn_started': None,
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


def _now() -> float:
    """Satranc saati hesaplarinin zamani (testler sahte saatle degistirir)."""
    return time.time()


def _time_control_name(room: dict) -> Optional[str]:
    tc = room.get('time_control')
    if not tc:
        return None
    return next((name for name, value in TIME_CONTROLS.items() if value == tc), None)


def _clock_running(room: dict) -> int:
    """Saati isleyen koltuk (1/2); suresiz, bekleyen, bitmis ya da duraklatilmis odada 0."""
    if (not room.get('time_control') or room['p2_uid'] is None or room['game'].game_over
            or room.get('clock_turn_started') is None or _clock_paused(room)):
        return 0
    return room['game'].current_player


def _clock_left(room: dict, piece: int) -> float:
    """Koltugun anlik kalan suresi (saniye, eksi olabilir). Baslangic payi dusulmez."""
    left = room['clock'][piece]
    if _clock_running(room) == piece:
        left -= max(0.0, _now() - room['clock_turn_started'])
    return left


def _clock_settle(room: dict) -> None:
    """Sirasi gelenin o ana kadar harcadigi sureyi saatine isler ve sira baslangicini simdiye
    ceker (baslangic payi bitmediyse korunur). Duraklatma durumu (kopma/donus) degismeden ve
    hamleden once cagrilir; duraklatilmis aralik boylece kimseye yazilmaz. GAMES_LOCK altinda."""
    if (not room.get('time_control') or room['game'].game_over
            or room.get('clock_turn_started') is None):
        return
    piece = _clock_running(room)
    if piece:
        room['clock'][piece] = _clock_left(room, piece)
    room['clock_turn_started'] = max(_now(), room['clock_turn_started'])


def _reset_chess_clock(room: dict) -> None:
    """Sureli odada iki saati baslangic suresine kurar; saat CLOCK_START_DELAY_SECONDS sonra isler."""
    tc = room.get('time_control')
    if not tc:
        return
    room['clock'] = {PLAYER1_PIECE: float(tc['base']), PLAYER2_PIECE: float(tc['base'])}
    room['clock_turn_started'] = _now() + config.CLOCK_START_DELAY_SECONDS


def _clock_flagged(room: dict) -> bool:
    """Sureli odada sirasi gelenin suresi gecikme payi da dahil bitti mi?"""
    if not room.get('time_control') or room['p2_uid'] is None or room['game'].game_over:
        return False
    piece = room['game'].current_player
    return _clock_left(room, piece) + config.MOVE_TIME_GRACE_SECONDS < 0


def _clock_fields(room: dict) -> Dict[str, Any]:
    """Istemci geri sayimi icin: kalan sure TAM saniye (saat farki onemsiz); sure yoksa None.
    Satranc saati alanlari (time_control, clock_p1/p2, clock_running, clock_delay) eklenir;
    suresiz odada None/0'dir ve eski alanlar (move_time, turn_seconds_left) aynen kalir.
    Sureli odada eski alanlar yalnizca saat okuyamayan eski istemciler (pygame, eski WebGL)
    icindir: turn_seconds_left = isleyen koltugun kalan suresi + kalan baslangic payi (pay
    bitince saat islemeye baslar, sayac tam saat sifira indiginde 0 olur); duraklamada,
    bekleyen/bitmis odada None (sayac gizlenir). move_time 0: eski istemciler rakip donunce
    sayaci hamle suresiyle yeniden kurmasin. Yeni istemci time_control varken bunlari kullanmaz."""
    deadline = room.get('turn_deadline')
    if _clock_paused(room):
        deadline = None
    fields = {
        'move_time': config.MOVE_TIME_SECONDS,
        'turn_seconds_left': None if deadline is None else max(0, math.ceil(deadline - time.time())),
        'time_control': _time_control_name(room),
        'clock_p1': None, 'clock_p2': None, 'clock_running': 0, 'clock_delay': 0,
    }
    if room.get('time_control'):
        fields['clock_p1'] = max(0, math.ceil(_clock_left(room, PLAYER1_PIECE)))
        fields['clock_p2'] = max(0, math.ceil(_clock_left(room, PLAYER2_PIECE)))
        fields['clock_running'] = _clock_running(room)
        if fields['clock_running']:
            # Baslangic payindan kalan tam saniye: istemci bu sure boyunca geri saymaz
            fields['clock_delay'] = max(0, math.ceil(room['clock_turn_started'] - _now()))
        running = fields['clock_running']
        fields['move_time'] = 0
        fields['turn_seconds_left'] = (fields[f'clock_{_seat_key(running)}'] + fields['clock_delay']
                                       if running else None)
    return fields


def _start_turn_clock(room: dict) -> None:
    """Sirasi gelen oyuncu icin hamle suresini baslatir (sure kapaliysa/oyun bittiyse None).
    Sureli odada hamle basina sinir yoktur, satranc saati turn_deadline'in yerine gecer."""
    if (config.MOVE_TIME_SECONDS > 0 and room['p2_uid'] and not room['game'].game_over
            and not room.get('time_control')):
        room['turn_deadline'] = time.time() + config.MOVE_TIME_SECONDS
    else:
        room['turn_deadline'] = None


def _deadline_passed(room: dict) -> bool:
    deadline = room.get('turn_deadline')
    return deadline is not None and time.time() > deadline + config.MOVE_TIME_GRACE_SECONDS


def _seat_second_player(room: dict, sid: str, uid: str, info: dict, auth: bool) -> None:
    """Bekleyen odaya P2'yi oturtur ve oyunu baslatir. GAMES_LOCK tutulurken cagrilir."""
    _quick_remove_locked(sid)   # Koltuk alan soket hizli eslesme kuyrugunda kalmaz
    room['p2_sid'], room['p2_uid'], room['p2_info'] = sid, uid, info
    room['p2_auth'], room['p2_rejoin'] = auth, secrets.token_urlsafe(16)
    room['last_move_at'] = time.time()
    _start_turn_clock(room)
    _reset_chess_clock(room)   # Saat ilk hamleyle degil, P2 katilinca (paydan sonra) isler


def _emit_game_start(room: dict) -> None:
    """Iki oyuncuya game_start gonderir (her biri rakibinin adini/ELO'sunu gorur)."""
    p1_info, p2_info = room['p1_info'], room['p2_info']
    for sid, opponent in ((room['p1_sid'], p2_info), (room['p2_sid'], p1_info)):
        emit('game_start', {
            'msg': 'Oyun Basladi!', 'p1_info': p1_info, 'p2_info': p2_info,
            'opponent_name': opponent.get('username', ''),
            'opponent_elo': opponent.get('rating', config.DEFAULT_RATING),
            **_clock_fields(room),
        }, to=sid)


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
    _clock_settle(room)   # Biten oyunun saati son haliyle donar
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
    """Hamle suresi (suresiz oda: turn_deadline) ya da satranc saati (sureli oda) dolan
    oyuncuyu hukmen yenik sayar. Bitirilen oyun sayisi."""
    finished = 0
    with GAMES_LOCK:
        for room_id, room in list(GAMES.items()):
            game = room['game']
            if room['p2_uid'] is None or game.game_over:
                continue
            if room.get('time_control'):
                # Duraklatilmis saat azalmaz; kopuk sirasi gelenin saati ise isler
                expired = _clock_flagged(room)
            else:
                expired = _deadline_passed(room) and not _clock_paused(room)
            if not expired:
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
    # Hamle suresi kapali (0) olsa da calisir: sureli odalarin satranc saatini de denetler
    socketio.start_background_task(move_clock_loop)
    log.info("Hamle suresi: %ds (satranc saati denetimi acik)", config.MOVE_TIME_SECONDS)


# =============================================================================
# REST API: CORS
# =============================================================================
# Oyun baska bir origin'den (ornegin itch.io) sunuldugunda tarayici REST
# yanitlarini ancak Access-Control-Allow-Origin ile okur. Ayar Socket.IO ile
# ortaktir (config.CORS_ALLOWED_ORIGINS); bos ise hicbir CORS basligi eklenmez
# (bugunku ayni-origin davranisi). Cerez kullanilmaz (token JSON govdesinde
# gider), bu yuzden Allow-Credentials gonderilmez. /play/ dosyalari ve
# /socket.io (python-engineio kendi CORS'unu yapar) bu kuraldan etkilenmez.

_CORS_ALLOW_METHODS = 'GET, POST, OPTIONS'
_CORS_ALLOW_HEADERS = 'Content-Type, Authorization'
_CORS_MAX_AGE = '600'


def _cors_origin_for(origin: Optional[str]) -> Optional[str]:
    """Istegin Origin'ine verilecek Access-Control-Allow-Origin degeri (yoksa None)."""
    allowed = config.CORS_ALLOWED_ORIGINS
    if not allowed or not origin:
        return None
    if allowed == '*':
        return '*'
    # Tam eslesme: tarayicinin Origin basligi sema://host[:port] bicimindedir (sonda / yok);
    # 'https://x/' veya 'http://' surumu listedeki 'https://x' ile eslesmez
    return origin if origin in allowed else None


def _is_api_path(path: str) -> bool:
    return not (path == '/play' or path.startswith('/play/') or path.startswith('/socket.io'))


def _apply_cors(response, allow_origin: str):
    response.headers['Access-Control-Allow-Origin'] = allow_origin
    response.headers['Access-Control-Allow-Methods'] = _CORS_ALLOW_METHODS
    response.headers['Access-Control-Allow-Headers'] = _CORS_ALLOW_HEADERS
    # 429 yanitindaki bekleme suresi istemci kodundan okunabilsin
    response.headers['Access-Control-Expose-Headers'] = 'Retry-After'
    return response


@app.before_request
def _cors_preflight():
    """Izinli origin'den gelen OPTIONS on istegini rota/kisitlayiciya girmeden yanitlar."""
    if request.method != 'OPTIONS' or not _is_api_path(request.path):
        return None
    allow_origin = _cors_origin_for(request.headers.get('Origin'))
    if not allow_origin or not request.headers.get('Access-Control-Request-Method'):
        return None
    response = app.response_class(status=204)
    response.headers['Access-Control-Max-Age'] = _CORS_MAX_AGE
    return response   # basliklar _cors_headers'ta eklenir


@app.after_request
def _cors_headers(response):
    """API yanitlarina (4xx/5xx/429 dahil) CORS basliklarini ekler."""
    if not config.CORS_ALLOWED_ORIGINS or not _is_api_path(request.path):
        return response
    # Yanit origin'e gore degistigi icin onbellekler ayri saklamali
    response.vary.add('Origin')
    allow_origin = _cors_origin_for(request.headers.get('Origin'))
    if allow_origin:
        _apply_cors(response, allow_origin)
    return response


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
                'time_control': _time_control_name(room),   # "3+2" ya da None (suresiz)
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
# Oyun buradan sunuldugunda ayni origin'dir: REST ve Socket.IO icin CORS gerekmez
# (baska origin'den, ornegin itch.io'dan sunulan build icin bkz. REST API: CORS).
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
    # index.html ve sunucu adresi (server-config.js) her acilista dogrulanir: adres
    # degisince tarayici eski adresi onbellekten kullanmasin
    if name.endswith('index.html') or name == 'server-config.js':
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
    LAST_CHAT_AT.pop(sid, None)
    log.debug("Ayrildi: %s", sid)

    with GAMES_LOCK:
        _quick_remove_locked(sid)
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
                _clock_settle(room)   # Rakibi kopan sirasi gelenin saati bundan sonra durur
                room['disconnected'][piece] = now
                # Saat alanlari: sunucu bekleyen oyuncunun saatini durdurdu; herkes (seyirci dahil) esitlenir
                socketio.emit('opponent_disconnected', {
                    'msg': 'Rakip ayrildi',
                    'grace_seconds': config.RECONNECT_GRACE_SECONDS,
                    **_clock_fields(room),
                }, to=room_id)
                socketio.start_background_task(_forfeit_after_grace, room_id, piece, now)


@socketio.on('create_game')
def on_create_game(data):
    user_id, user_info, authenticated, error = resolve_player(data)
    if error:
        _emit_error(error)
        return

    with GAMES_LOCK:
        # Kullanicinin onceki bekleyen odasi varsa sil (tek bekleyen oda kurali).
        # Misafir adi kanit olmadigindan baska baglantinin odasina dokunulmaz.
        existing = get_user_waiting_game(user_id, authenticated)
        if existing and not authenticated and GAMES[existing]['p1_sid'] != request.sid:
            _emit_error('Bu misafir adi kullanimda')
            return
        if existing:
            _drop_waiting_room(existing)
        _quick_remove_locked(request.sid)   # Oda kuran soket hizli eslesme kuyrugundan cikar
        room_id = generate_room_id()
        while room_id in GAMES:
            room_id = generate_room_id()
        # Alan yoksa ya da bilinmiyorsa oda suresizdir (eski istemciler etkilenmez)
        time_control = _parse_time_control(data.get('time_control') if isinstance(data, dict) else None)
        GAMES[room_id] = _new_room(request.sid, user_id, user_info, authenticated, time_control)
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
        _emit_error('Gecersiz istek')
        return
    user_id, user_info, authenticated, error = resolve_player(data)
    if error:
        _emit_error('Gecersiz istek' if error == 'Gecersiz kullanici' else error)
        return

    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if room is None:
            _emit_error('Oda bulunamadi')
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
                _emit_error('Kendi oyununuza katilamazsiniz')
                return
            old_sid = _sid_of(room, own_piece)
            # Bir baglanti iki koltugu birden tutamaz
            if _sid_of(room, other_player(own_piece)) == request.sid:
                _emit_error('Bu oyuna zaten bagli durumdasiniz')
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
                _emit_error('Bu oyuna zaten bagli durumdasiniz')
                return
            if not proof:
                _emit_error('Yeniden baglanma anahtari gecersiz')
                return
            if seat_alive and old_sid:
                # Sunucu eski soketin oldugunu henuz fark etmedi (ping zaman asimi): kanitli
                # yeni baglanti koltugu devralir, eski soket odadan cikarilir
                _emit_error('Baska bir baglantidan oyuna girildi', to=old_sid)
                leave_room(room_id, sid=old_sid)
            was_disconnected = own_piece in room['disconnected']
            _clock_settle(room)   # Duraklatilmis aralik kimsenin saatine yazilmaz
            room['disconnected'].pop(own_piece, None)
            room[f'{key}_sid'] = request.sid
            if not game.game_over:
                _quick_remove_locked(request.sid)   # Aktif koltuga donen soket kuyruktan cikar
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
                # Saat alanlari: duraklayan saat yeniden isler; herkes (seyirci dahil) esitlenir
                emit('opponent_reconnected', {'msg': 'Rakip geri dondu', **_clock_fields(room)},
                     to=room_id, include_self=False)
            return

        join_room(room_id)

        # 2) Ikinci oyuncu olarak katil
        if room['p2_uid'] is None:
            _seat_second_player(room, request.sid, user_id, user_info, authenticated)
            log.info("Oda %s: %s P2 olarak katildi", room_id, user_id)

            emit('game_joined', {'room_id': room_id, 'player_piece': PLAYER2_PIECE,
                                 'role': 'player', 'opponent_info': room['p1_info'],
                                 'rejoin_token': room['p2_rejoin'], **_clock_fields(room)})
            _emit_game_start(room)
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


# =============================================================================
# HIZLI ESLESME
# =============================================================================

def _drop_waiting_room(room_id: str) -> None:
    """Bekleyen odayi siler (tek bekleyen oda kurali). GAMES_LOCK tutulurken cagrilir."""
    GAMES.pop(room_id, None)
    try:
        close_room(room_id)
    except Exception:
        pass


def _quick_remove_locked(sid: str) -> bool:
    """Soketi hizli eslesme kuyrugundan cikarir; cikardiysa True. GAMES_LOCK altinda cagrilir."""
    before = len(QUICK_QUEUE)
    QUICK_QUEUE[:] = [entry for entry in QUICK_QUEUE if entry['sid'] != sid]
    return len(QUICK_QUEUE) != before


def _seated_in_active_game(sid: str) -> bool:
    """Soket baslamis ve bitmemis bir macta koltuk tutuyor mu? GAMES_LOCK altinda cagrilir."""
    return any(_piece_of(room, sid) is not None and room['p2_uid'] is not None
               and not room['game'].game_over
               for room in GAMES.values())


def _quick_pair_locked() -> None:
    """Kuyrukta iki oyuncu varsa ilk ikisini eslestirir: ilk giren P1, ikincisi P2.
    Iki tarafa da game_joined (quick: True) ve game_start gider. GAMES_LOCK altinda cagrilir."""
    # Bu arada aktif bir maca oturan soket (or. rovans) eslestirilmez, kuyruktan duser
    for entry in [e for e in QUICK_QUEUE if _seated_in_active_game(e['sid'])]:
        _quick_remove_locked(entry['sid'])
        emit('quick_match_cancelled', {}, to=entry['sid'])
    while len(QUICK_QUEUE) >= 2:
        p1, p2 = QUICK_QUEUE.pop(0), QUICK_QUEUE.pop(0)
        room_id = generate_room_id()
        while room_id in GAMES:
            room_id = generate_room_id()
        # Hizli mac her zaman sureli (3+2); saat P2 oturunca paydan sonra isler
        room = _new_room(p1['sid'], p1['uid'], p1['info'], p1['auth'], QUICK_TIME_CONTROL)
        _seat_second_player(room, p2['sid'], p2['uid'], p2['info'], p2['auth'])
        GAMES[room_id] = room
        log.info("Oda %s: hizli eslesme %s - %s", room_id, p1['uid'], p2['uid'])

        for piece, entry, opponent in ((PLAYER1_PIECE, p1, p2), (PLAYER2_PIECE, p2, p1)):
            CONNECTED_USERS[entry['sid']] = entry['uid']
            join_room(room_id, sid=entry['sid'])
            emit('game_joined', {'room_id': room_id, 'player_piece': piece, 'role': 'player',
                                 'opponent_info': opponent['info'],
                                 'rejoin_token': room[f'{_seat_key(piece)}_rejoin'],
                                 'quick': True, **_clock_fields(room)}, to=entry['sid'])
        _emit_game_start(room)


@socketio.on('quick_match_join')
def on_quick_match_join(data):
    user_id, user_info, authenticated, error = resolve_player(data)
    if error:
        _emit_error(error)
        return

    sid = request.sid
    with GAMES_LOCK:
        if _seated_in_active_game(sid):
            _emit_error('Zaten bir oyundasiniz')
            return
        # Tek bekleyen oda kurali (create_game ile ayni): kendi bekleyen odasi silinir;
        # misafir adi kanit olmadigindan baska baglantinin odasina dokunulmaz.
        existing = get_user_waiting_game(user_id, authenticated)
        if existing and not authenticated and GAMES[existing]['p1_sid'] != sid:
            _emit_error('Bu misafir adi kullanimda')
            return
        if existing:
            _drop_waiting_room(existing)

        # Ayni soket ayni kimlikle tekrar girerse sirasi korunur (yenileme)
        if any(e['sid'] == sid and e['uid'] == user_id and e['auth'] == authenticated
               for e in QUICK_QUEUE):
            emit('quick_match_waiting', {})
            return
        same_identity = [e for e in QUICK_QUEUE
                         if e['sid'] != sid and e['uid'] == user_id and e['auth'] == authenticated]
        # Misafir adi kanit degildir: kuyruktaki baska canli baglantinin misafiri atilamaz
        if same_identity and not authenticated:
            _emit_error('Bu misafir adi kullanimda')
            return
        # Kayitli kullanicinin (token kanitli) yeni soketi eski kaydin yerini alir
        replaced = [e['sid'] for e in same_identity]
        QUICK_QUEUE[:] = [e for e in QUICK_QUEUE if e['sid'] != sid and e['sid'] not in replaced]
        for old_sid in replaced:
            emit('quick_match_cancelled', {}, to=old_sid)

        QUICK_QUEUE.append({'sid': sid, 'uid': user_id, 'info': user_info, 'auth': authenticated})
        CONNECTED_USERS[sid] = user_id
        log.info("Hizli eslesme kuyrugu: %s (%d kisi)", user_id, len(QUICK_QUEUE))
        _quick_pair_locked()
        if any(e['sid'] == sid for e in QUICK_QUEUE):
            emit('quick_match_waiting', {})


@socketio.on('quick_match_cancel')
def on_quick_match_cancel(data=None):
    with GAMES_LOCK:
        _quick_remove_locked(request.sid)
    emit('quick_match_cancelled', {})


@socketio.on('chat_quick')
def on_chat_quick(data):
    """Hazir sohbet mesaji: sadece odadaki oyuncular gonderir; gecersiz istek sessizce yok sayilir."""
    room_id = (_clean_str(data, 'room_id', 10) or '').upper()
    msg_id = data.get('msg_id') if isinstance(data, dict) else None
    # bool, int'in alt sinifi: True/False mesaj kimligi sayilmaz
    if not isinstance(msg_id, int) or isinstance(msg_id, bool) or not 0 <= msg_id < QUICK_CHAT_COUNT:
        return
    sid = request.sid
    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if room is None:
            return
        piece = _piece_of(room, sid)
        if piece is None:
            return
        now = time.time()
        last = LAST_CHAT_AT.get(sid)
        if last is not None and now - last < CHAT_MIN_INTERVAL:
            return
        LAST_CHAT_AT[sid] = now
    socketio.emit('chat_message', {'room_id': room_id, 'from_piece': piece, 'msg_id': msg_id},
                  to=room_id)


@socketio.on('make_move')
def on_make_move(data):
    room_id = (_clean_str(data, 'room_id', 10) or '').upper()
    col = data.get('col') if isinstance(data, dict) else None
    player_piece = data.get('player_piece') if isinstance(data, dict) else None

    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if room is None:
            _emit_error('Oda bulunamadi')
            return
        game: ConnectFourGame = room['game']

        if room['p2_uid'] is None:
            _emit_error('Rakip bekleniyor!')
            return
        # Hamleyi gonderen baglanti gercekten o tasin sahibi mi?
        if player_piece not in (PLAYER1_PIECE, PLAYER2_PIECE) or request.sid != _sid_of(room, player_piece):
            _emit_error('Bu oyunda hamle yapma yetkiniz yok!')
            return
        if not isinstance(col, int) or isinstance(col, bool):
            _emit_error('Gecersiz hamle!')
            return
        if game.game_over:
            _emit_error('Oyun bitti')
            return
        if game.current_player != player_piece:
            _emit_error('Sira sizde degil!')
            return
        if (_deadline_passed(room) and not _clock_paused(room)) or _clock_flagged(room):
            # Izleyici gorevi henuz calismamis olsa bile gec gelen hamle gecersizdir
            _finish_game(room_id, room, reason='forfeit', forfeit_loser=player_piece, detail='timeout')
            return
        _clock_settle(room)   # Hamlecinin harcadigi sure saatine islenir
        if not game.make_move(col):
            _emit_error('Gecersiz hamle!')
            return

        room['last_move_at'] = time.time()
        _start_turn_clock(room)
        if room.get('time_control'):
            # Ek sure hamleciye; rakibin sirasi simdi baslar (baslangic payi sadece ilk sirada)
            room['clock'][player_piece] += room['time_control']['inc']
            room['clock_turn_started'] = _now()
        response = game.to_dict()
        response['col'] = col
        response.update(_clock_fields(room))
        emit('move_made', response, to=room_id)

        if game.game_over:
            _finish_game(room_id, room)


@socketio.on('leave_game')
def on_leave_game(data):
    """
    Oyuncu bilerek ayrilir: aktif oyunda hukmen yenilgi, bekleyen odada oda silinir.

    Donus degeri Socket.IO onayi (ack) olarak istemciye gider: `leave_game`den hemen sonra
    kopan istemci, onay gelmeden baglantiyi kapatirsa kopma olayi once islenebilir ve ayrilma
    istegi hic calismaz (rakip 'disconnect' ile, sure sonunda hukmen kazanir). Onay bekleyen
    istemci bu yarisi yasamaz. Koltuk sid ile baglidir: kopma koltugun sid'ini silmez, bu
    yuzden ayni baglantinin gecikmis `leave_game`i yine kendi koltugunu bulur; koltugu
    devralan yeni baglantinin eski sid'i veya baska bir baglanti hicbir koltuk bulamaz.
    """
    room_id = (_clean_str(data, 'room_id', 10) or '').upper()
    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if room is None:
            return {'ok': False}
        piece = _piece_of(room, request.sid)
        leave_room(room_id)
        if piece is None:
            return {'ok': False}  # Seyirci veya koltugu olmayan baglanti
        if room['p2_uid'] is None:
            GAMES.pop(room_id, None)
            log.info("Oda %s iptal edildi", room_id)
        elif not room['game'].game_over:
            if piece == PLAYER1_PIECE:
                room['p1_sid'] = None
            else:
                room['p2_sid'] = None
            _clock_settle(room)
            room['disconnected'][piece] = time.time()
            log.info("Oda %s: oyuncu %s oyunu terk etti", room_id, piece)
            _finish_game(room_id, room, reason='forfeit', forfeit_loser=piece, detail='leave')
        else:
            room[f'{_seat_key(piece)}_sid'] = None
            _seat_left_finished(room_id, room, piece)
        return {'ok': True}


@socketio.on('rematch_request')
def on_rematch_request(data=None):
    """Bitmis odada ayni rakiple yeni oyun: iki koltuk da istemeli; koltuklar yer degistirir."""
    room_id = (_clean_str(data, 'room_id', 10) or '').upper()
    with GAMES_LOCK:
        room = GAMES.get(room_id)
        if room is None:
            _emit_error('Oda bulunamadi')
            return
        piece = _piece_of(room, request.sid)
        if piece is None:
            _emit_error('Sadece oyuncular rovans isteyebilir')
            return
        if not room['game'].game_over:
            _emit_error('Oyun devam ediyor')
            return
        if piece in room['disconnected']:
            return   # Kopmus baglantinin gecikmis istegi: hayalet koltukla rovans baslamasin
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
    _reset_chess_clock(room)   # Rovansta saatler sifirlanir (yine baslangic payiyla)
    log.info("Oda %s: rovans basladi (oyun %d)", room_id, room['game_no'])
    # Rovansla aktif maca donen soket hizli eslesme kuyrugunda kalamaz (iki canli mac olmasin)
    for key in ('p1', 'p2'):
        sid = room[f'{key}_sid']
        if sid and _quick_remove_locked(sid):
            socketio.emit('quick_match_cancelled', {}, to=sid)

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
