# Arena Turnuvası Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kayıtlı oyuncuların açtığı, 15/30/60 dakikalık, 3+2 puanlı Arena turnuvaları; canlı sıralama ve gece çalışan hile kontrolü.

**Architecture:** Saf turnuva mantığı (puan, seri, sıralama, eşleştirme seçimi, yaşam döngüsü kararları) yeni `src/arena.py` modülünde, I/O'suz ve birim testli. Kalıcı durum PostgreSQL'de (`tournaments`, `tournament_players`, `games.tournament_id`). `src/server.py` motoru bağlar: Socket.IO olayları, arena kuyruğu, turnuva oyun odaları, mevcut saat döngüsünde yaşam döngüsü. Hile kontrolü `scripts/arena_cheat_check.py` + GitHub Actions; sunucudan herkese açık ve gizli anahtarla korunan uç noktalar üzerinden okur/işaretler. Unity istemcisine Turnuvalar ekranları.

**Tech Stack:** Python 3.10/3.12, Flask-SocketIO, psycopg2, pytest; Unity 6 (C#), dotnet test; Playwright e2e; GitHub Actions; Pascal Pons c4solver (yalnızca CI'da derlenir).

**Spec:** `docs/superpowers/specs/2026-11-19-arena-tournament-design.md`

## Global Constraints

- Turnuva süresi yalnızca `15`, `30`, `60` dakika; başlangıç "hemen" ya da en geç **24 saat** sonra.
- Açan ve katılan **kayıtlı** (token ile doğrulanmış, `auth=True`) olmalı; misafir yalnızca listeyi ve sıralamayı görür.
- Bir kullanıcının aynı anda en fazla **1** `scheduled` veya `running` turnuvası (açan olarak).
- Turnuva adı otomatik: `"<kullanıcı>'nın Arenası"`; serbest metin yok. (İstemci İngilizcede `"<user>'s Arena"` gösterir; sunucu yalnızca `creator` adını gönderir, adı istemci kurar.)
- Turnuva oyunları her zaman `time_control='3+2'`, puanlı (iki taraf `auth`), rövanş yok.
- Puan: galibiyet 2, beraberlik 1, yenilgi 0; 3. art arda galibiyetten itibaren galibiyet 4; seri sürerken (streak ≥ 2) beraberlik 2 ve seriyi sıfırlar; yenilgi 0 ve seriyi sıfırlar; hükmen galibiyet = galibiyet; ilk hamle iptali sayılmaz.
- Sıralama: puan ↓, oynanan oyun ↓, rating ↓.
- Başlangıçta < 2 katılımcı → 10 dk bekle (sunucunun fiilen başlattığı andan); hâlâ < 2 → `cancelled`.
- `ends_at`'ten sonra yeni eşleşme yok; turnuva en geç `ends_at + 15 dk`'da `finished`.
- Biten turnuva 7 gün listede; iptal edilen listeden düşer.
- Hile eşiği: ≥ 3 oyun, ≥ 20 kritik hamle, kritik hamlelerin %100'ü doğru → GitHub issue. İlk `BOOK_PLIES = 4` yarım hamle sayılmaz.
- Veritabanı şifresi GitHub'a verilmez; işaretleme uç noktası `ARENA_CHECK_SECRET` ortam değişkeniyle korunur (Render + GitHub secret; değeri sahip girer).
- Kod yorumları ASCII Türkçe; Unity metinleri diakritikli Türkçe + İngilizcesi `Loc.cs`'te; belgeler diakritikli Türkçe.
- `src/ai_vs_human.py` ve `unity/Assets/Scripts/AI/*` değişmez. Testler atlanmaz/zayıflatılmaz. Commit mesajları ASCII Türkçe, model adı yok, sonda `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Yeni Unity runtime `.cs` dosyaları `tests/csharp/asm/ConnectFourPro.Runtime.csproj`'a eklenir ve `.meta` alır.
- Yatay + dikey düzen (dikeyde en küçük yazı 18 pt).

## Review Focus

1. Sunucu turnuva oyunu sürerken yeniden başlar → oyun sonuçsuz düşer, turnuva `ends_at + 15 dk`'da biter, katılımcılar bağlanınca kuyruğa döner (Task 4 testi: `test_restart_restores_running_tournament`).
2. Oyuncu turnuva kuyruğundayken hızlı maça / oda kurmaya / ikinci turnuvaya girmeye çalışır → reddedilir ya da diğerinde duraklatılır; asla iki oyunda birden olmaz (Task 5 testi: `test_arena_player_cannot_quick_match`, `test_joining_second_queue_pauses_first`).
3. `ends_at` bir oyun ortasında gelir → oyun biter ve puanı sayılır, yeni eşleşme olmaz (Task 5 testi: `test_game_in_progress_at_end_still_scores`).
4. Kuyrukta tek oyuncu kalır ya da son rakibiyle tek başına kalır → uzun süre eşleşmez değil, başka rakip yoksa son rakiple eşleşir (Task 2 testi: `test_pick_pair_falls_back_to_last_opponent`).
5. Hile kontrolü kısa / zorunlu hamleli oyunlarda dürüst güçlü oyuncuyu işaretler → işaretlemez (Task 7 testi: `test_honest_short_games_not_flagged`).

---

### Task 1: Veritabanı şeması ve turnuva veri fonksiyonları

**Files:**
- Modify: `src/database.py` (`init_db` göçleri; yeni fonksiyonlar; `record_game`'e `tournament_id`)
- Test: `tests/integration/test_arena_db.py` (`pytestmark = pytest.mark.db`, `database` fixture'ı; yerelde atlanır, CI'da Postgres ile koşar)

**Interfaces:**
- Produces (hepsi `src/database.py`, hata/DB yoksa güvenli varsayılan döner):
  - `create_tournament(creator_username: str, duration_minutes: int, starts_at: datetime) -> Optional[int]`
  - `get_tournament(tid: int) -> Optional[Dict]` — anahtarlar: `id, creator, duration_minutes, starts_at, ends_at, started_at, status, created_at, cheat_checked_at`
  - `list_tournaments(now: datetime) -> List[Dict]` — `scheduled`/`running` + son 7 gündeki `finished`; `cancelled` yok
  - `active_tournament_of_creator(username: str) -> Optional[int]`
  - `set_tournament_status(tid: int, status: str, started_at: Optional[datetime] = None, ends_at: Optional[datetime] = None) -> bool`
  - `join_tournament(tid: int, username: str) -> bool` (zaten üyeyse True, `paused=False` yapar)
  - `set_player_paused(tid: int, username: str, paused: bool) -> bool`
  - `get_standings_rows(tid: int) -> List[Dict]` — her satır: `username, rating, score, games_played, streak, paused, recent` (`recent`: son 5 sonuç dizesi, `'W'/'D'/'L'`)
  - `apply_tournament_result(tid: int, username: str, points: int, new_streak: int, outcome: str) -> bool` (`outcome` ∈ `'W','D','L'`; `games_played+1`, `recent` sonuna ekle, 5'te kes)
  - `record_game(..., tournament_id: Optional[int] = None)` — yeni isteğe bağlı parametre
  - `tournament_games(tid: int) -> List[Dict]` — `game_id, player1, player2, winner, moves (list[int]), end_reason`
  - `finished_unchecked_tournaments() -> List[int]`; `mark_cheat_checked(tid: int) -> bool`
- Şema: `tournaments(id SERIAL PK, creator_id INT REFERENCES users, duration_minutes INT, starts_at TIMESTAMPTZ, ends_at TIMESTAMPTZ, started_at TIMESTAMPTZ NULL, status TEXT, created_at TIMESTAMPTZ DEFAULT now(), cheat_checked_at TIMESTAMPTZ NULL)`; `tournament_players(tournament_id INT REFERENCES tournaments, user_id INT REFERENCES users, score INT DEFAULT 0, games_played INT DEFAULT 0, streak INT DEFAULT 0, paused BOOL DEFAULT FALSE, recent TEXT DEFAULT '', joined_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY(tournament_id, user_id))`; `ALTER TABLE games ADD COLUMN IF NOT EXISTS tournament_id INT NULL`.

- [ ] **Step 1: Write failing DB tests** — `test_create_and_get_tournament` (ends_at = starts_at + duration), `test_list_hides_cancelled_and_old_finished` (8 günlük finished görünmez, 6 günlük görünür), `test_active_tournament_of_creator`, `test_join_is_idempotent_and_unpauses`, `test_apply_result_updates_score_streak_recent` (6 sonuçtan sonra `recent` uzunluğu 5), `test_record_game_with_tournament_id_and_tournament_games` (moves listesi `[3,3,4]` olarak döner), `test_mark_cheat_checked_removes_from_unchecked`.
- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/integration/test_arena_db.py -q` — Expected locally: skipped (no DB); in CI: FAIL (functions missing). Push branch to see CI fail if desired, or rely on CI after implementation.
- [ ] **Step 3: Implement** schema in `init_db()` (`CREATE TABLE IF NOT EXISTS`, `ALTER ... IF NOT EXISTS`, index on `tournament_players(tournament_id, score DESC)`), and the functions above. `delete_test_users()` must also delete their `tournament_players` and `tournaments` rows (tests truncate safely).
- [ ] **Step 4: Run full** `.venv/Scripts/python -m pytest -q` and `ruff check src tests benchmarks scripts` — Expected: PASS (DB tests skipped locally).
- [ ] **Step 5: Commit** — `git commit -m "Arena: veritabani semasi ve turnuva veri fonksiyonlari"`

### Task 2: Saf turnuva mantığı — `src/arena.py`

**Files:**
- Create: `src/arena.py`
- Test: `tests/unit/test_arena.py`

**Interfaces:**
- Produces:
  - `DURATIONS = (15, 30, 60)`; `MAX_START_DELAY = timedelta(hours=24)`; `MIN_PLAYERS = 2`; `START_WAIT = timedelta(minutes=10)`; `FINISH_GRACE = timedelta(minutes=15)`; `LIST_KEEP = timedelta(days=7)`
  - `score_result(outcome: str, streak: int) -> Tuple[int, int]` → `(points, new_streak)`; `outcome` ∈ `'W','D','L'`
  - `sort_standings(rows: List[Dict]) -> List[Dict]` — puan, oyun sayısı, rating azalan; her satıra `rank` (1'den) ve `on_fire = streak >= 2` ekler
  - `pick_pair(queue: List[str], last_opponent: Dict[str, str]) -> Optional[Tuple[str, str]]` — kuyruk sırasıyla ilk oyuncu için, son rakibi olmayan ilk adayı seçer; yoksa son rakiple eşler; < 2 ise None
  - `lifecycle_action(status: str, now: datetime, starts_at: datetime, ends_at: datetime, started_at: Optional[datetime], players: int, live_games: int) -> Optional[str]` → `'start'`, `'cancel'`, `'stop_pairing'`, `'finish'` ya da None
  - `validate_create(duration: Any, start_in_minutes: Any, now: datetime) -> Tuple[Optional[datetime], Optional[str]]` → `(starts_at, error_code)`; hata kodları `'bad_duration'`, `'bad_start'`

- [ ] **Step 1: Write failing tests**

```python
def test_score_win_streak():
    assert score_result('W', 0) == (2, 1)
    assert score_result('W', 1) == (2, 2)
    assert score_result('W', 2) == (4, 3)
def test_score_draw_and_loss():
    assert score_result('D', 0) == (1, 0)
    assert score_result('D', 1) == (1, 0)
    assert score_result('D', 2) == (2, 0)
    assert score_result('L', 5) == (0, 0)
def test_sort_standings_tiebreaks(): ...   # esit puan -> cok oyun ust; o da esitse rating ust; rank 1..n; on_fire
def test_pick_pair_avoids_last_opponent():
    assert pick_pair(['a', 'b', 'c'], {'a': 'b', 'b': 'a'}) == ('a', 'c')
def test_pick_pair_falls_back_to_last_opponent():
    assert pick_pair(['a', 'b'], {'a': 'b', 'b': 'a'}) == ('a', 'b')
def test_pick_pair_needs_two():
    assert pick_pair(['a'], {}) is None
def test_lifecycle(): ...   # scheduled+starts_at gecti -> 'start'; running, started_at+10dk gecti, players<2 -> 'cancel';
                           # running, players<2 ama 10 dk dolmadi -> None; now>=ends_at -> 'stop_pairing';
                           # now>=ends_at ve live_games==0 -> 'finish'; now>=ends_at+15dk -> 'finish' (live_games>0 olsa da)
def test_validate_create(): ...   # 15/30/60 ok; 20 -> 'bad_duration'; start 0 -> now; 1440 ok; 1441 -> 'bad_start'; -5 -> 'bad_start'
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/unit/test_arena.py -q` — Expected: FAIL (module missing)
- [ ] **Step 3: Implement** `src/arena.py` (no I/O, no imports from server).
- [ ] **Step 4: Run** same + full suite + ruff — Expected: PASS
- [ ] **Step 5: Commit** — `"Arena: puan, seri, siralama, eslestirme ve yasam dongusu mantigi"`

### Task 3: Sunucu — turnuva açma, listeleme, katılma, duraklatma

**Files:**
- Modify: `src/server.py` (yeni REST + Socket.IO olayları, `ERROR_CODES`)
- Test: `tests/integration/test_arena_server.py` (DB'li testler `pytest.mark.db`; DB gerektirmeyen doğrulamalar `no_database` ile)

**Interfaces:**
- Consumes: Task 1 fonksiyonları, Task 2 `validate_create`, `sort_standings`, `resolve_player`.
- Produces:
  - REST `GET /tournaments` → `{"tournaments": [{id, creator, duration_minutes, starts_at (ISO), ends_at, status, players}]}`
  - REST `GET /tournaments/<id>` → `{tournament: {...}, standings: [{rank, username, score, games_played, streak, on_fire, paused, recent}]}` (404 yoksa)
  - Socket `arena_create {token, duration, start_in_minutes}` → `arena_created {tournament}` ya da `error` (`code`: `'not_registered'`, `'bad_duration'`, `'bad_start'`, `'arena_limit'`)
  - Socket `arena_join {token, tournament_id}` → `arena_joined {tournament_id}`; socket `join_room(f"arena:{tid}")`; ardından odaya `arena_standings {tournament_id, standings}`
  - Socket `arena_watch {tournament_id}` (misafir dahil) → odaya katılır, `arena_standings` alır
  - Socket `arena_pause {tournament_id}` / `arena_resume {tournament_id}` → `paused` güncellenir, `arena_standings` yayılır
  - `def _broadcast_standings(tid: int) -> None` (Task 4–5 kullanır)
  - `ERROR_CODES` eklemeleri: `'Turnuva icin kayitli olmalisiniz': 'not_registered'`, `'Gecersiz turnuva suresi': 'bad_duration'`, `'Gecersiz baslangic zamani': 'bad_start'`, `'Zaten acik bir turnuvaniz var': 'arena_limit'`, `'Turnuva bulunamadi': 'arena_not_found'`, `'Turnuva bitti': 'arena_over'`

- [ ] **Step 1: Write failing tests** — `test_guest_cannot_create_arena` (code `not_registered`), `test_create_validates_duration_and_start`, `test_creator_limit_one_active`, `test_list_and_detail_endpoints`, `test_join_requires_registration`, `test_join_broadcasts_standings`, `test_guest_can_watch_standings`, `test_pause_resume_updates_standings`, `test_join_finished_tournament_rejected` (`arena_over`).
- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/integration/test_arena_server.py -q` — Expected: FAIL / skipped(db) locally
- [ ] **Step 3: Implement** handlers in `src/server.py` (thin: validation via `arena.py`, persistence via `database.py`).
- [ ] **Step 4: Run** full pytest + ruff — Expected: PASS
- [ ] **Step 5: Commit** — `"Arena (sunucu): turnuva acma, liste, katilma, duraklatma"`

### Task 4: Sunucu — yaşam döngüsü ve yeniden başlatma dayanıklılığı

**Files:**
- Modify: `src/server.py` (`enforce_move_deadlines` yanında `enforce_arena_lifecycle()`; bellek içi `ARENAS` önbelleği)
- Test: `tests/integration/test_arena_lifecycle.py` (zaman için `src/server.py`'ye `def _utcnow() -> datetime` yardımcısı eklenir; testler `monkeypatch.setattr(server, '_utcnow', ...)` ile ileri sarar ve `enforce_arena_lifecycle()`'ı doğrudan çağırır)

**Interfaces:**
- Consumes: Task 2 `lifecycle_action`, Task 1 durum fonksiyonları, Task 3 `_broadcast_standings`.
- Produces:
  - `ARENAS: Dict[int, Dict[str, Any]]` — `{'queue': List[str] (username), 'last_opponent': Dict[str,str], 'started_at', 'ends_at', 'pairing': bool}`; DB'den tembel yüklenir
  - `def enforce_arena_lifecycle() -> None` — saat döngüsü her turda çağırır; `lifecycle_action` sonucuna göre `set_tournament_status` + yayın `arena_state {tournament_id, status, ends_at}` (odaya `arena:{tid}`)
  - `def _load_arenas_from_db() -> None` — sunucu açılışında ve ilk turda `running` turnuvaları yükler; `started_at` boşsa şimdiki zaman yazılır (uyurken gelen başlangıç kuralı)

- [ ] **Step 1: Write failing tests** — `test_scheduled_starts_at_time`, `test_cancel_when_under_two_after_ten_minutes`, `test_wait_counts_from_actual_start` (starts_at 30 dk geçmiş, sunucu şimdi başlatır → hemen iptal edilmez), `test_stop_pairing_at_end_then_finish_when_no_games`, `test_finish_cap_fifteen_minutes`, `test_restart_restores_running_tournament` (ARENAS temizlenip `_load_arenas_from_db()` çağrılınca turnuva ve paused=false üyeler geri gelir).
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run** full pytest + ruff → PASS
- [ ] **Step 5: Commit** — `"Arena (sunucu): yasam dongusu ve yeniden baslatmada geri yukleme"`

### Task 5: Sunucu — arena kuyruğu, turnuva oyunları, puanlama

**Files:**
- Modify: `src/server.py` (`_new_room(..., tournament_id=...)`, `_finish_game`, `_abort_game`, `_start_rematch`, `on_quick_match_join`, `on_create_game`, `on_disconnect`, `on_connect`/kimlik bağlama)
- Test: `tests/integration/test_arena_games.py`

**Interfaces:**
- Consumes: Tasks 1–4; mevcut `_seat_second_player`, `_emit_game_start`, `_clock_fields`, `_first_move_pending`.
- Produces:
  - Oda alanı `room['tournament_id']: Optional[int]`; `game_joined` ve `game_start` olaylarına `tournament_id` eklenir.
  - `def _arena_pair_locked(tid: int) -> None` — `pick_pair` ile eşler, oda kurar (`time_control='3+2'`, `quick=True` → ilk hamle iptali geçerli), `last_opponent` günceller.
  - `_finish_game` içinde turnuva odasıysa: iki oyuncu için `score_result` → `apply_tournament_result`; `record_game(..., tournament_id=tid)`; `game_over` sonucuna `arena: {tournament_id, points: {p1, p2}}`; duraklatmamış ve bağlı oyuncular kuyruğa geri (pairing kapalıysa girmez); `_broadcast_standings(tid)`.
  - `_abort_game` turnuva odasında: puan/oyun sayısı değişmez; ilk hamleyi yapmayan oyuncu `set_player_paused(..., True)`; diğeri kuyruğa döner.
  - `on_rematch_request` turnuva odasında reddedilir (sessizce yok sayılır).
  - Dışlama: arena kuyruğundaki/turnuva oyunundaki oyuncu `quick_match_join` ve `create_game`'de `already_in_game` alır; başka turnuvanın kuyruğuna girmek önceki turnuvada `paused=True` yapar.
  - Kopma: kuyruktaki oyuncu kuyruktan düşer (paused değişmez); bağlanıp kimliğini doğrulayan ve `paused=False` olan üye, turnuva `pairing` iken `arena_join` ile tekrar kuyruğa girer (istemci otomatik gönderir, Task 8).

- [ ] **Step 1: Write failing tests** — `test_two_joined_players_get_paired_3plus2` (game_joined `tournament_id`, `time_control=='3+2'`), `test_win_scores_and_requeues`, `test_streak_third_win_four_points`, `test_draw_scores_one`, `test_forfeit_counts_as_win`, `test_first_move_abort_no_score_and_pauses_culprit`, `test_no_rematch_in_arena`, `test_avoid_immediate_rematch_with_three_players`, `test_arena_player_cannot_quick_match`, `test_joining_second_queue_pauses_first`, `test_game_in_progress_at_end_still_scores`, `test_no_pairing_after_end`, `test_tournament_game_recorded_with_tournament_id`.
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run** full pytest + ruff → PASS (mevcut hızlı maç / saat / iptal testleri dahil)
- [ ] **Step 5: Commit** — `"Arena (sunucu): kuyruk, turnuva oyunlari ve puanlama"`

### Task 6: Sunucu — hile kontrolü uç noktaları

**Files:**
- Modify: `src/server.py`, `src/config.py` (`ARENA_CHECK_SECRET = os.environ.get('ARENA_CHECK_SECRET')`)
- Test: `tests/integration/test_arena_check_api.py`

**Interfaces:**
- Produces:
  - `GET /tournaments/unchecked` → `{"tournament_ids": [...]}` (herkese açık)
  - `GET /tournaments/<id>/games` → `{"games": [{game_id, player1, player2, winner, moves, end_reason}]}` (herkese açık; yalnızca `finished` turnuva, değilse 409)
  - `POST /tournaments/<id>/checked` — başlık `X-Arena-Check-Secret` `ARENA_CHECK_SECRET`'e eşit olmalı (`hmac.compare_digest`); secret tanımsızsa 503, yanlışsa 403, doğruysa `mark_cheat_checked` → 200

- [ ] **Step 1: Write failing tests** — `test_games_endpoint_requires_finished`, `test_unchecked_list`, `test_mark_checked_requires_secret` (yok→503, yanlış→403, doğru→200 ve listeden düşer).
- [ ] **Step 2: Run** → FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run** full pytest + ruff → PASS
- [ ] **Step 5: Commit** — `"Arena (sunucu): hile kontrolu icin oyun ve isaretleme uc noktalari"`

### Task 7: Hile kontrolü betiği ve GitHub Actions iş akışı

**Files:**
- Create: `scripts/arena_cheat_check.py`, `.github/workflows/arena-cheat-check.yml`
- Test: `tests/unit/test_arena_cheat_check.py` (sahte oracle ile; gerçek çözücü gerekmez)

**Interfaces:**
- Produces (`scripts/arena_cheat_check.py`):
  - `BOOK_PLIES = 4`; `MIN_GAMES = 3`; `MIN_CRITICAL = 20`
  - `class Oracle` — `benchmarks/ai_quality_benchmark.py`'deki `Oracle` ile aynı arayüz (`scores(moves) -> List[Optional[int]]`); oradan import edilir ya da paylaşılan bir yardımcıya taşınır (benchmark davranışı değişmez).
  - `def critical_moves(oracle, moves: List[int]) -> List[Tuple[int, bool]]` — her yarım hamle için (ply ≥ `BOOK_PLIES`), pozisyonun skor işaretleri birden fazlaysa kritik; doğru = seçilen sütunun işareti en yüksek işarete eşit. Dönüş: `(ply_index, correct)`.
  - `def evaluate_player(oracle, games: List[Dict], username: str) -> Dict` → `{games, critical, correct, flagged}`; `flagged = games >= 3 and critical >= 20 and correct == critical`
  - `def main()` — argümanlar `--server`, `--solver-dir`, `--dry-run`; `/tournaments/unchecked` → her turnuva için `/games` → oyuncu başına değerlendirme → işaretlenen için `gh issue create` (başlık `Arena #<tid>: <kullanıcı> kritik hamlelerin %100'u` — aynı başlık açıksa tekrar açma: `gh issue list --search`) → `POST /checked` (`ARENA_CHECK_SECRET` ortamından).
- İş akışı: `schedule: cron '30 3 * * *'` + `workflow_dispatch`; `permissions: issues: write, contents: read`; Pons'u `git clone https://github.com/PascalPons/connect4` + `make`, `7x6.book`'u indir; ikisini `actions/cache` ile önbelleğe al (anahtar: Pons commit SHA); `CONNECT4_PUBLIC_SERVER_URL` değişkeni ve `ARENA_CHECK_SECRET` secret'ı yoksa `::notice::` ile atla.

- [ ] **Step 1: Write failing tests** — `test_critical_moves_skips_book_and_forced` (sahte oracle: ilk 4 ply kritik olsa da sayılmaz; tüm skorların işareti aynı olan pozisyon sayılmaz), `test_correct_is_sign_preserving`, `test_flag_requires_thresholds` (2 oyun/25 kritik → flagged False; 3 oyun/19 kritik → False; 3/20 tümü doğru → True; 3/20 biri yanlış → False), `test_honest_short_games_not_flagged`, `test_dry_run_creates_no_issue` (subprocess `gh` çağrısı taklit edilir).
- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/unit/test_arena_cheat_check.py -q` → FAIL
- [ ] **Step 3: Implement** script + workflow (`actionlint` varsa çalıştır; yoksa YAML'ı `python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))"` ile doğrula).
- [ ] **Step 4: Run** full pytest + ruff → PASS
- [ ] **Step 5: Commit** — `"Arena: gece calisan hile kontrolu betigi ve is akisi"`

### Task 8: Unity — protokol, soket ve AppController turnuva durumu

**Files:**
- Modify: `unity/Assets/Scripts/Net/Protocol/Protocol.cs`, `Net/GameSocket.cs`, `Net/ApiClient.cs`, `Game/AppController.cs`
- Create: `unity/Assets/Scripts/Game/ArenaModel.cs` (+ `.meta`, csproj satırı)
- Test: `tests/csharp/ArenaModelTests.cs`, `tests/csharp/AppControllerArenaTests.cs`

**Interfaces:**
- Consumes: Tasks 3–6 olay/REST sözleşmesi.
- Produces:
  - `AppScreen.Tournaments`, `AppScreen.Tournament` (enum'a eklenir)
  - `ArenaModel`: `TournamentSummary` (Id, Creator, DurationMinutes, StartsAt, EndsAt, Status, Players), `StandingRow` (Rank, Username, Score, GamesPlayed, Streak, OnFire, Paused, Recent), `static List<StandingRow> ParseStandings(JsonObject)`, `static string DisplayName(string creator, Lang lang)` → `"<c>'nın Arenası"` / `"<c>'s Arena"` (Türkçe ek ünlü uyumu gerekmez; sabit kalıp kullan)
  - `GameSocket`: `CreateArena(int duration, int startInMinutes)`, `JoinArena(int id)`, `WatchArena(int id)`, `PauseArena(int id)`, `ResumeArena(int id)`
  - `AppController`: `OpenTournaments()`, `OpenTournament(int id)`, `CreateTournament(int duration, int startInMinutes)`, `JoinTournament()`, `ToggleArenaPause()`, özellikler `Tournaments`, `CurrentTournament`, `Standings`, `ArenaSecondsLeft`, `InArenaGame`; turnuva oyunu bitince rövanş yerine "Sıradaki oyun" durumu (`ArenaNextGamePending`); bağlantı geri gelince `paused=false` ise otomatik `JoinArena`.
- [ ] **Step 1: Write failing tests** — standings parse, display name TR/EN, create flow emits `arena_create` with values, guest sees no create, join → `arena_join` and standings update on `arena_standings`, game_over with `arena` field → no rematch offered and next-game pending, reconnect re-joins when not paused, old server (no `arena_*` events) → no crash.
- [ ] **Step 2: Run** `dotnet test tests/csharp` → FAIL
- [ ] **Step 3: Implement**
- [ ] **Step 4: Run** `dotnet test tests/csharp` → PASS
- [ ] **Step 5: Commit** — `"Arena (istemci): protokol, soket ve uygulama durumu"`

### Task 9: Unity — Turnuvalar ekranları, Loc, e2e

**Files:**
- Modify: `unity/Assets/Scripts/UI/Views.cs` (yeni `TournamentsView`, `TournamentView`; `MenuView`'a "Turnuvalar"; `GameView`'da turnuva başlığı ve "Sıradaki oyun"), `Game/Loc.cs`, `tests/csharp/LocTests.cs`, `tests/csharp/ScreenLayoutTests.cs`, `tests/e2e/webgl.spec.mjs`
- Test: e2e adımı + C# düzen testleri

**Interfaces:**
- Consumes: Task 8 `AppController` API'si.
- Metinler (TR → EN): "Turnuvalar" → "Tournaments", "+ Turnuva Aç" → "+ Create Tournament", "Katıl" → "Join", "Duraklat" → "Pause", "Devam" → "Resume", "Hemen" → "Now", "Başlıyor" → "Starts", "kaldı" → "left", "oyuncu" → "players", "Sıradaki oyun" → "Next game", "Turnuva bitti" → "Tournament over", "İptal edildi" → "Cancelled", "Seri" → "Streak". 🔥 yazı tipinde yoksa (sohbetteki 💬 gibi) turuncu "×2" etiketi kullan.
- Düzen: spec bölüm 3'teki taslak; yatay + dikey; dikeyde en küçük yazı 18 pt.

- [ ] **Step 1: Write failing tests** — Loc anahtarları; ScreenLayout dikey/yatay sığma testleri yeni görünümler için.
- [ ] **Step 2: Run** `dotnet test tests/csharp` → FAIL
- [ ] **Step 3: Implement** görünümler.
- [ ] **Step 4: e2e** — `tests/e2e/webgl.spec.mjs`'e adım: iki **kayıtlı test kullanıcısı** gerekir (yerel sunucu + yerel/test DB; canlıda çalıştırılmaz) → A turnuva açar (15 dk, hemen), B katılır, A katılır, eşleşme olur, ikisi de 3:00 saat görür, sıralamada iki oyuncu görünür. DB yoksa adım `::notice` ile atlanır. Derle: `"C:\Program Files\Unity\Hub\Editor\6000.3.27f1\Editor\Unity.exe" -batchmode -nographics -quit -projectPath unity -buildTarget WebGL -executeMethod ConnectFourPro.EditorTools.ProjectSetup.BuildWebGL -logFile <log>`; yerel sunucu; `cd tests/e2e && BASE_URL=http://localhost:5000 node webgl.spec.mjs`; sonra `git checkout -- unity/ProjectSettings`.
- [ ] **Step 5: Run** `dotnet test tests/csharp`, full pytest → PASS
- [ ] **Step 6: Commit** — `"Arena (istemci): Turnuvalar ekranlari ve metinler"`

### Task 10: Yayın (sahip onaylı adımlar)

- [ ] PR → CI yeşil → birleştir (sahip onayı mevcut kurala göre).
- [ ] Sahip `ARENA_CHECK_SECRET` değerini Render ortam değişkenine ve GitHub secret'ına kendisi girer (değer sohbete yazılmaz).
- [ ] Render: "Deploy latest reference" (WebGL'li ikinci Docker imajından sonra); canlıda `/tournaments` 200 döner.
- [ ] `arena-cheat-check` iş akışını elle bir kez `--dry-run` ile çalıştır; çözücü derlenir, kitap iner, iş yeşil.
- [ ] itch.io yüklemesi ve devlog **ayrı sahip onayıyla**.
