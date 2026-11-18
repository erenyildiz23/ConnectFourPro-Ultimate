# Online özellikler: uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Hedef:** Unity WebGL istemcisine ve Flask-SocketIO sunucusuna dört özellik
eklemek: maç tekrarı, hızlı eşleşme, hazır sohbet ve 3+2 satranç saati.

**Mimari:** Sunucu otoritesi korunur; oda durumu bellekte (`GAMES`,
`GAMES_LOCK`). Yeni olaylar sadece ekleme yapar, eski olaylar ve alanlar
değişmez. İstemcide her özellik `AppController`'da durum ve komut olarak,
`Views.cs`'te görünüm olarak yer alır.

**Teknoloji:** Python 3.10/3.12 (Flask-SocketIO, pytest), Unity
6000.3.27f1 (C#, NUnit ile `tests/csharp`), Playwright (`tests/e2e`).

**Spec:** `docs/superpowers/specs/2026-11-18-online-features-design.md`

## Genel kısıtlar

- `src/ai_vs_human.py` ve `unity/Assets/Scripts/AI/AIEngine.cs` dosyalarına
  dokunulmaz.
- Kod yorumları ASCII Türkçe; Unity metinleri diakritikli Türkçe ve her
  yeni metnin `Loc.cs`'te İngilizce karşılığı olur; pygame metinleri ASCII.
- Yeni sunucu hata mesajları `ERROR_CODES`'a kod ile eklenir:
  `'Zaten bir oyundasiniz': 'already_in_game'`.
- Eski istemci uyumu: `create_game` içinde `time_control` alanı yoksa oda
  süresizdir ve bugünkü gibi davranır. `move_time` ve `turn_seconds_left`
  alanları süresiz odada aynı anlamı taşır.
- Hiçbir test atlanmaz ya da gevşetilmez. Commit'lerde model adı geçmez.
  Commit sonu: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Her özellik ayrı dalda ve ayrı PR'da olur (`feat/replay`,
  `feat/quick-match`, `feat/quick-chat`, `feat/clock`). Her dal bir öncekinin
  merge edildiği `main`'den açılır.
- Komutlar:
  - Python: `.venv/Scripts/python -m pytest -q`
  - C#: `dotnet test tests/csharp`
  - E2E: `tests/e2e` içinde `npx playwright test` (WebGL build gerekir)

## Dikkat edilecekler

1. Hızlı eşleşmede iki sekmede aynı misafir adıyla kuyruğa girmek: aynı
   kimlik kendisiyle eşleşmemeli, ikinci giriş ilkinin yerini almalı.
2. Kuyrukta beklerken sekmeyi kapatmak: kopan soket kuyruktan düşmeli,
   sonraki oyuncu hayalet bir rakiple eşleşmemeli.
3. Saatin bittiği an ile hamlenin geldiği an çakışınca: gecikme payı
   (`MOVE_TIME_GRACE_SECONDS`) içindeki hamle geçerli, dışındaki
   "süre doldu" ile biter.
4. Rövanş: saatler 3:00'a döner, renkler değişir, sohbet balonu temizlenir.
5. Tekrar ekranında bozuk ya da boş hamle listesi: "İzle" düğmesi
   görünmez, çökme olmaz.

---

### Task 1: Geçmiş kaydında hamle listesi (dal `feat/replay`)

**Dosyalar:**
- Değiştir: `unity/Assets/Scripts/Net/Protocol/Protocol.cs` (`HistoryEntry`)
- Test: `tests/csharp/ProtocolTests.cs`

**Arayüz:**
- Üretir: `HistoryEntry.Moves : List<int>` (boş liste olabilir).
  `MoveCount` bu durumda `Moves.Count`'a eşittir.

- [ ] Başarısız testleri yaz:
  - `HistoryEntryParsesMoveList`: `"moves":"[3, 3, 4]"` →
    `Moves == {3,3,4}`, `MoveCount == 3`.
  - `HistoryEntryBadMovesGivesEmptyList`: `"moves":"bozuk"` ve `null`
    → `Moves` boş, `MoveCount == 0`.
  - `HistoryEntryRejectsOutOfRangeColumns`: `"[3, 9]"` → `Moves` boş
    (0–6 dışı sütun tüm listeyi geçersiz yapar).
- [ ] `dotnet test tests/csharp --filter HistoryEntry` → FAIL.
- [ ] `ListFrom`'da listeyi `List<int>` olarak sakla; sayı olmayan ya da
  aralık dışı bir değer varsa listeyi boşalt.
- [ ] Testler → PASS. Commit.

### Task 2: Tekrar modeli

**Dosyalar:**
- Oluştur: `unity/Assets/Scripts/Game/ReplayModel.cs`
- Test: `tests/csharp/ReplayModelTests.cs`

**Arayüz:**
- `public sealed class ReplayModel`
  - `ReplayModel(IReadOnlyList<int> moves, string p1, string p2, string resultText)`
  - `int Index` (0..Count), `int Count`, `bool Playing`
  - `GameState State` (Index'teki konum; `GameState.FromMoves` ile)
  - `void First()`, `void Prev()`, `void Next()`, `void Last()`,
    `void TogglePlay()`, `void Tick(float dt)`
  - `const float StepSeconds = 0.8f`

- [ ] Başarısız testleri yaz:
  - `StartsAtZeroWithEmptyBoard`
  - `NextAndPrevClampToBounds`: Count=3; 5×Next → Index 3; 5×Prev → 0.
  - `StateMatchesPrefix`: Index=2 iken `State.MoveHistory == moves[0..2]`.
  - `TickAdvancesEveryStepWhilePlaying`: TogglePlay, Tick(0.79) → 0,
    Tick(0.02) → 1, Tick(1.6) → 3.
  - `PlayingStopsAtEnd`: sona gelince `Playing == false`.
  - `TogglePlayAtEndRestartsFromZero`.
- [ ] FAIL → uygula → PASS. Commit.

### Task 3: Tekrar ekranı ve girişleri

**Dosyalar:**
- Değiştir: `unity/Assets/Scripts/Game/AppController.cs` (`AppScreen.Replay`,
  `Replay` özelliği, `OpenReplay(HistoryEntry)`,
  `OpenReplayOfLastGame()`, `CanReplayLastGame`, geri dönüşte önceki ekran)
- Değiştir: `unity/Assets/Scripts/UI/Views.cs` (`ReplayView`; `HistoryView`
  satırlarına "İzle"; `GameView` oyun sonu düğmesi "Tekrarı izle")
- Değiştir: `unity/Assets/Scripts/Game/GameBootstrap.cs` (görünüm kaydı ve
  klavye: ← → Boşluk Esc)
- Değiştir: `unity/Assets/Scripts/Game/Loc.cs` (yeni metinler)
- Test: `tests/csharp/AppControllerReplayTests.cs`,
  `tests/csharp/LocTests.cs`, `tests/e2e/webgl.spec.mjs`

**Arayüz:**
- Kullanır: `ReplayModel` (Görev 2), `HistoryEntry.Moves` (Görev 1).
- Üretir: `AppController.Replay : ReplayModel`,
  `AppController.ReplayReturnScreen : AppScreen`.

- [ ] Başarısız testleri yaz:
  - `OpenReplayFromHistoryShowsReplayScreen`: ekran `Replay`,
    `Replay.Count == entry.Moves.Count`.
  - `ReplayBackReturnsToHistory` / `...ToGameOverScreen`.
  - `CannotReplayEmptyMoveList`: `OpenReplay` boş listede ekranı
    değiştirmez.
  - `CanReplayLastGameOnlyAfterOnlineGameOver`.
  - `LocTests`: her yeni metnin İngilizcesi var ("İzle" → "Watch",
    "Tekrarı izle" → "Watch replay", "Hamle {n} / {n}" → "Move {n} / {n}").
- [ ] FAIL → uygula → PASS.
- [ ] E2E: misafirlerin geçmişi tutulmadığı için e2e testi
  `CanReplayLastGame` yolunu kullanır: iki misafir sayfası online maç
  oynar, biri dörtlü yapar, "Tekrarı izle"ye basılır, ⏭ ile sona
  gelinince sayaç "n / n" olur.
- [ ] `dotnet test` + Unity WebGL build + e2e → PASS. Commit, PR,
  CI yeşil, merge.

### Task 4: Hızlı eşleşme kuyruğu, sunucu (dal `feat/quick-match`)

**Dosyalar:**
- Değiştir: `src/server.py`
- Test: `tests/integration/test_quick_match.py` (yeni)

**Arayüz:**
- Olaylar:
  - `quick_match_join {user_id, token?}` → `quick_match_waiting {}`
  - `quick_match_cancel {}` → `quick_match_cancelled {}`
  - Eşleşince iki tarafa da `game_joined {room_id, player_piece,
    role:'player', opponent_info, rejoin_token, quick:true}` ve ardından
    mevcut biçimde `game_start`.
- Yardımcılar: `QUICK_QUEUE: list[dict]` (`sid`, `uid`, `info`, `auth`),
  `_quick_pair_locked() -> None` (`GAMES_LOCK` altında çağrılır).
- Oda kurulurken `_new_room` kullanılır; Görev 8 burada `time_control`
  verecek. Şimdilik oda süresizdir.

- [ ] Başarısız testleri yaz:
  - `test_two_players_get_matched`: a ve b katılır → ikisi de
    `game_joined` (taşlar 1 ve 2, `rejoin_token` dolu, `quick` True) ve
    `game_start` alır; `GAMES`'te tek oda vardır.
  - `test_first_waits`: tek oyuncu `quick_match_waiting` alır.
  - `test_cancel_removes_from_queue`: a katılır, iptal eder, b katılır →
    b bekler.
  - `test_disconnect_removes_from_queue`.
  - `test_same_identity_not_matched_with_itself`: aynı `user_id` ile iki
    soket → eşleşme yok, kuyrukta tek kayıt (sonuncusu).
  - `test_join_removes_own_waiting_room`.
  - `test_seated_player_cannot_queue`: aktif maçtaki soket →
    `error` `already_in_game`.
  - `test_registered_vs_registered_quick_match_is_rated`: iki token'lı
    kullanıcı; bitince `elo_update` gelir.
- [ ] `pytest tests/integration/test_quick_match.py` → FAIL → uygula →
  PASS. Tüm `pytest` → PASS. Commit.

### Task 5: Hızlı eşleşme, istemci

**Dosyalar:**
- Değiştir: `Net/Protocol/Protocol.cs` (`SocketEvents.QuickMatchJoin`,
  `QuickMatchCancel`, `QuickMatchWaiting`, `QuickMatchCancelled`;
  `ServerEvents` listesine eklenir)
- Değiştir: `Net/GameSocket.cs` (`JoinQuickMatch(userId, token)`,
  `CancelQuickMatch()`)
- Değiştir: `Game/AppController.cs` (`StartQuickMatch()`,
  `CancelQuickMatch()`, `QuickMatchSearching`)
- Değiştir: `UI/Views.cs` (Menü: "Hızlı Maç" düğmesi en üstte; `WaitingView`
  aranırken "Rakip aranıyor..." ve İptal)
- Değiştir: `Game/Loc.cs`
- Test: `tests/csharp/GameSocketTests.cs`,
  `tests/csharp/AppControllerQuickMatchTests.cs`, `LocTests.cs`, e2e

- [ ] Başarısız testleri yaz:
  - `QuickMatchEmitsJoinWithIdentity`
  - `QuickMatchWaitingShowsSearchingScreen`
  - `CancelEmitsCancelAndReturnsToMenu`
  - `MatchedGameJoinedStartsOnlineGame`: `game_joined` + `game_start` →
    ekran `PlayingOnline`, `MyPiece` doğru, `RejoinToken` saklanmış.
  - `ConnectionFailureWhileSearchingReturnsToMenuWithStatus`
- [ ] FAIL → uygula → PASS. E2E: iki sayfa "Hızlı Maç"a basar → ikisi de
  oyun ekranına geçer. Build + e2e → PASS. Commit, PR, merge, Render'a
  deploy.

### Task 6: Hazır sohbet, sunucu (dal `feat/quick-chat`)

**Dosyalar:**
- Değiştir: `src/server.py`
- Test: `tests/integration/test_quick_chat.py` (yeni)

**Arayüz:**
- `chat_quick {room_id, msg_id}` → odaya
  `chat_message {room_id, from_piece, msg_id}`.
- `QUICK_CHAT_COUNT = 8`, `CHAT_MIN_INTERVAL = 2.0`,
  `LAST_CHAT_AT: dict[sid, float]` (kopunca silinir).

- [ ] Başarısız testleri yaz:
  - `test_player_message_reaches_room`: rakip ve seyirci
    `chat_message` alır, `from_piece` doğru.
  - `test_spectator_cannot_send`
  - `test_invalid_msg_id_ignored` (parametreli: -1, 8, "1", True, None)
  - `test_rate_limited`: art arda iki mesaj → tek yayın; zaman 2,1 sn
    ileri alınınca (`monkeypatch` ile `server.time.time`) ikinci geçer.
  - `test_works_after_game_over`
  - `test_unknown_room_ignored`
- [ ] FAIL → uygula → PASS. Commit.

### Task 7: Hazır sohbet, istemci

**Dosyalar:**
- Oluştur: `Game/QuickChat.cs` (`public static readonly string[] Messages`
  — spec'teki 8 Türkçe mesaj, sırasıyla)
- Değiştir: `Protocol.cs` (`ChatQuick`, `ChatMessage`), `GameSocket.cs`
  (`SendQuickChat(int id)`), `AppController.cs` (`SendQuickChat(int)`,
  `ChatBubble : (int piece, int msgId)?`, 3 sn sonra temizlenir; rövanş ve
  ekran değişiminde temizlenir; yerel gönderimde de 2 sn sınır),
  `Views.cs` (`GameView`: 💬 düğmesi, 8 düğmeli panel, adın yanında balon),
  `Loc.cs` (8 mesajın İngilizcesi spec'teki gibi)
- Test: `tests/csharp/AppControllerChatTests.cs`, `LocTests.cs`, e2e

- [ ] Başarısız testleri yaz:
  - `SendQuickChatEmitsId`
  - `LocalRateLimitBlocksSecondSendWithin2s`
  - `IncomingChatShowsBubbleForSender` ve `BubbleExpiresAfter3s`
  - `SpectatorHasNoChatButton` (`CanChat == false`)
  - `InvalidIncomingIdIgnored`
  - `LocTests`: 8 mesajın İngilizcesi.
- [ ] FAIL → uygula → PASS. E2E: A "İyi oyun!" gönderir, B'nin sayfasında
  balon görünür. Build + e2e → PASS. Commit, PR, merge, deploy.

### Task 8: Satranç saati, sunucu (dal `feat/clock`)

**Dosyalar:**
- Değiştir: `src/server.py`, `src/config.py`
- Test: `tests/integration/test_clock.py` (yeni)

**Arayüz:**
- `config.CLOCK_START_DELAY_SECONDS = 5`
- `TIME_CONTROLS = {'3+2': {'base': 180, 'inc': 2}}`
- Oda alanları: `time_control` (`None` ya da sözlük), `clock` (`{1: float,
  2: float}` kalan saniye), `clock_turn_started` (float; sıra başlangıcı,
  başlangıç payı dahil).
- `_clock_fields` ek alanları: `time_control` (`"3+2"` ya da `None`),
  `clock_p1`, `clock_p2` (kalan tam saniye, `ceil`), `clock_running`
  (1/2/0). Sıradaki oyuncunun değeri anlık hesaplanır.
- `create_game` isteğe bağlı `time_control: "3+2"` alır; bilinmeyen değer
  süresiz sayılır. Hızlı eşleşme her zaman `"3+2"` kurar.
- Süreli odada `turn_deadline` kullanılmaz. `enforce_move_deadlines` süreli
  odada `clock` bitişini denetler (`kalan + grace < 0` → `_finish_game(...,
  reason='forfeit', detail='timeout')`). `move_clock_loop` her zaman çalışır.
- `/active_games` öğelerine `time_control` eklenir.

- [ ] Başarısız testleri yaz (zaman `monkeypatch` ile sahte saate bağlanır):
  - `test_untimed_room_unchanged`: alanlar `time_control: None`,
    `clock_p1: None`; eski `move_time`/`turn_seconds_left` aynı.
  - `test_timed_room_reports_full_clocks_at_start`: 180/180, `clock_running`
    1, P2'nin `game_joined`'unda da alanlar var.
  - `test_start_delay_not_charged`: başlangıçtan 4 sn sonra hamle →
    P1 182 (180 + 2 ek süre).
  - `test_increment_after_move`: 10 sn (5 pay + 5) sonra hamle → P1 177.
  - `test_flag_fall_forfeits`: P1 sırada, 186 sn + grace ilerletilir,
    `enforce_move_deadlines()` → `game_over` `reason forfeit`,
    `detail timeout`, kazanan 2.
  - `test_move_within_grace_accepted`, `test_move_after_grace_forfeits`.
  - `test_waiting_player_clock_pauses_when_mover_opponent_disconnected`.
  - `test_disconnected_mover_clock_keeps_running`.
  - `test_rematch_resets_clocks`.
  - `test_quick_match_is_timed`.
  - `test_active_games_lists_time_control`.
  - `test_unknown_time_control_is_untimed`.
- [ ] FAIL → uygula → PASS. Tüm `pytest` → PASS. Commit.

### Task 9: Satranç saati, istemci

**Dosyalar:**
- Oluştur: `Game/ClockFormat.cs` (`public static string Format(int seconds)`
  → `"3:00"`, `"0:09"`; negatif → `"0:00"`)
- Değiştir: `Protocol.cs` (`ActiveGame.TimeControl`), `GameSocket.cs`
  (`CreateGame(userId, token, string timeControl = null)`),
  `AppController.cs` (`TimeControl`, `ClockSeconds(int piece) : int?`
  yerel geri sayımla; `ClockWarning(int piece)` 10 sn altı;
  `CreateOnlineGame(string timeControl)`), `Views.cs` (Lobi: "Oda kur" yanında
  Süresiz/3+2 seçimi; lobi listesinde "3+2" etiketi; `GameView`: iki adın
  yanında saat), `Loc.cs`
- Test: `tests/csharp/ClockFormatTests.cs`,
  `tests/csharp/AppControllerClockTests.cs`, `ProtocolTests.cs`,
  `LocTests.cs`, e2e

- [ ] Başarısız testleri yaz:
  - `FormatsMinutesAndSeconds` (180→"3:00", 9→"0:09", 0 ve -3→"0:00")
  - `OldServerHasNoClock`: alan yok → `ClockSeconds(1) == null`.
  - `RunningClockCountsDownLocally`: `clock_running 1`, 2 sn ilerle →
    P1 2 eksik, P2 sabit.
  - `MoveMadeResyncsClocks`
  - `WarningUnder10Seconds`
  - `CreateTimedRoomSendsTimeControl`
  - `ActiveGameParsesTimeControl`
- [ ] FAIL → uygula → PASS. E2E: 3+2 oda kurulur, katılan iki sayfada da
  "3:00" görünür, hamleden sonra saat değişir. Build + e2e → PASS.
  Commit, PR, merge.

### Task 10: Yayın

- [ ] Render'da "Deploy latest reference"; canlı sunucuda hızlı eşleşme,
  sohbet ve saat Socket.IO ile denenir.
- [ ] `-cf4DecompressionFallback` ile WebGL build,
  `scripts/make_itch_zip.py` ile paket, butler ile `html5` kanalına yükleme.
- [ ] itch sayfası açıklamasına yeni özellikler eklenir; devlog yazılır.
