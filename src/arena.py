"""Arena turnuvasi saf mantigi (I/O yok, sunucu/veritabani importu yok)."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

DURATIONS = (15, 30, 60)
MAX_START_DELAY = timedelta(hours=24)
MIN_PLAYERS = 2
START_WAIT = timedelta(minutes=10)
FINISH_GRACE = timedelta(minutes=15)
LIST_KEEP = timedelta(days=7)

STREAK_ON = 2  # bu seriden itibaren puanlar cift
ARENA_NEXT_GAME_DELAY = 4  # sn: oyun bitince siradaki eslesmeden once bekleme (spec 8.3)


def score_result(outcome: str, streak: int) -> Tuple[int, int]:
    """(puan, yeni_seri) dondurur. outcome: 'W', 'D' ya da 'L'."""
    if outcome == 'W':
        return (4 if streak >= STREAK_ON else 2), streak + 1
    if outcome == 'D':
        return (2 if streak >= STREAK_ON else 1), 0
    if outcome == 'L':
        return 0, 0
    raise ValueError("bilinmeyen sonuc: %r" % (outcome,))


def sort_standings(rows: List[Dict]) -> List[Dict]:
    """Puan, oyun sayisi, rating azalan; rank ve on_fire ekler (girdiyi degistirmez)."""
    ordered = sorted(rows, key=lambda r: (-r['score'], -r['games_played'], -r['rating'], r['username']))
    out = []
    for i, row in enumerate(ordered, start=1):
        item = dict(row)
        item['rank'] = i
        item['on_fire'] = item['streak'] >= STREAK_ON
        out.append(item)
    return out


def pick_pair(queue: List[str], last_opponent: Dict[str, str]) -> Optional[Tuple[str, str]]:
    """Kuyruktaki ilk oyuncuya son rakibi olmayan ilk adayi eslestirir; yoksa kuyruktaki ikinciyi."""
    if len(queue) < 2:
        return None
    a = queue[0]
    for b in queue[1:]:
        if last_opponent.get(a) != b and last_opponent.get(b) != a:
            return a, b
    return a, queue[1]


def order_colors(a: str, b: str, balance: Dict[str, int],
                 last_was_p1: Dict[str, bool]) -> Tuple[str, str]:
    """Eslesen ikiliden (P1, P2) sirasi: ilk hamle dengesi (P1 - P2 sayisi) dusuk olan
    baslar; esitlikte son oyununda ikinci olan baslar; yine esitse sira korunur."""
    ba, bb = balance.get(a, 0), balance.get(b, 0)
    if ba != bb:
        return (a, b) if ba < bb else (b, a)
    if last_was_p1.get(a) and not last_was_p1.get(b):
        return b, a
    return a, b


def lifecycle_action(status: str, now: datetime, starts_at: datetime, ends_at: datetime,
                     started_at: Optional[datetime], players: int, live_games: int) -> Optional[str]:
    """Turnuva icin yapilacak adim: 'start', 'cancel', 'stop_pairing', 'finish' ya da None."""
    if status == 'scheduled':
        return 'start' if now >= starts_at else None
    if status == 'running':
        if now >= ends_at + FINISH_GRACE:
            return 'finish'
        if now >= ends_at:
            return 'finish' if live_games == 0 else 'stop_pairing'
        if players < MIN_PLAYERS and started_at is not None and now >= started_at + START_WAIT:
            return 'cancel'
    return None


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_create(duration: Any, start_in_minutes: Any, now: datetime) -> Tuple[Optional[datetime], Optional[str]]:
    """(starts_at, hata_kodu) dondurur; hata kodlari 'bad_duration', 'bad_start'."""
    if not _is_int(duration) or duration not in DURATIONS:
        return None, 'bad_duration'
    max_minutes = int(MAX_START_DELAY.total_seconds() // 60)
    if not _is_int(start_in_minutes) or not 0 <= start_in_minutes <= max_minutes:
        return None, 'bad_start'
    return now + timedelta(minutes=start_in_minutes), None
