// =============================================================================
// webgl.spec.mjs - Connect Four Pro Ultimate
// Unity WebGL build'ini gercek Chromium'da, gercek sunucuya karsi oynayan
// uctan uca test (use case'ler: misafir girisi, AI maci, online mac, seyirci,
// turnuvalar)
// =============================================================================
//
// Kullanim (sunucu calisirken, build CONNECT4_WEB_BUILD'den sunuluyorken):
//   cd tests/e2e && npm ci && npx playwright install chromium
//   BASE_URL=http://localhost:5000 node webgl.spec.mjs
//
// Arena adimi (5f) iki kayitli test kullanicisi ister: sunucunun veritabani olmali
// (CI: postgres servisi). Kullanicilar /signup ile rastgele ad ve sifreyle kaydedilir;
// yalnizca yerel sunucuya (localhost) karsi calisir. Veritabani yoksa adim atlanir;
// E2E_REQUIRE_DB=1 iken (CI) atlama yerine test basarisiz olur.
//
// Arayuz canvas'a cizildigi icin DOM yoktur. Tiklamalar Unity tarafindaki
// yerlesimden hesaplanir (UI/UIKit.cs Place: 1280x720 referans, ust-orta
// merkezli; UI/BoardView.cs: tahta merkezi (-250, 375), hucre 80 px). Pencere
// 1280x720 oldugu icin CanvasScaler olcegi 1'dir. Tahtadaki taslar ekran
// goruntusunden piksel rengiyle okunur.

import { chromium } from 'playwright';
import { PNG } from 'pngjs';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const BASE = (process.env.BASE_URL || 'http://localhost:5000').replace(/\/$/, '');
const OUT = process.env.SCREENSHOT_DIR || 'screenshots';
const WIDTH = 1280, HEIGHT = 720;
fs.mkdirSync(OUT, { recursive: true });

// --- Yerlesim (unity/Assets/Scripts/UI/Views.cs ile ayni sayilar) ---
const at = (x, y) => ({ x: WIDTH / 2 + x, y });               // UIKit.Place koordinati -> ekran
const UI = {
  guest: at(0, 540),
  // Menu (Views.cs MenuView): Hizli Mac en ustte, sonra AI ve lobi (adim 66)
  menuQuick: at(0, 200), menuAI: at(0, 266), menuLobby: at(0, 332),
  easy: at(0, 200),
  lobbyCreate: at(-470, 110), lobbyRow0Action: at(470, 225),
  lobbyTime: at(-195, 110),   // "Yeni Oyun"un yanindaki Suresiz / 3+2 secimi
  lang: at(560, 50),   // dil dugmesi (GameBootstrap; yalnizca giris ve menu)
  replayOpen: at(400, 345), replayLast: at(520, 430),
  // Hazir sohbet (GameView): dugme tahta ile panel arasinda, panelin ilk dugmesi "İyi oyun!";
  // balon govdesi (140, 225 + i*70) 180 genis, yazinin solundaki dolgudan okunur
  chatOpen: at(135, 590), chatMsg0: at(322, 270),
  bubbleP1: at(62, 225), bubbleP2: at(62, 295),
  // Giris (LoginView): kullanici adi, sifre, "Giris Yap"
  loginUser: at(0, 255), loginPass: at(0, 340), loginButton: at(-82, 420),
  // Turnuvalar (Views.cs TournamentsView / TournamentView; menude 4. dugme)
  menuTournaments: at(0, 398),
  tCreate: at(-455, 110), tDur15: at(-130, 305), tSubmit: at(-90, 485),
  tRow0Action: at(500, 170), tPageAction: at(-470, 110),
};
const cellCenter = (col, row) => at(-250 - 280 + col * 80 + 40, 375 + 240 - row * 80 - 40);
const COLORS = { red: [233, 69, 96], yellow: [241, 196, 15], empty: [10, 10, 21], background: [26, 26, 46] };

let failures = 0;
const results = [];
function check(cond, msg) {
  results.push(`${cond ? 'OK  ' : 'FAIL'} ${msg}`);
  console.log(`${cond ? 'OK   ' : 'FAIL '}${msg}`);
  if (!cond) failures++;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

const browser = await chromium.launch({
  // Yazilimsal WebGL (GPU'suz CI makinesi)
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const consoleErrors = [];

// Tarayici dili sabit: oyun ilk acilista tarayici diline gore TR/EN secer (Game/Loc.cs)
async function openGame(name, viewport = { width: WIDTH, height: HEIGHT }, locale = 'en-US') {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 1, locale });
  const page = await context.newPage();
  page.name = name;
  page.logs = [];
  page.on('console', m => {
    page.logs.push(m.text());
    if (m.type() === 'error') consoleErrors.push(`[${name}] ${m.text()}`);
  });
  page.on('pageerror', e => consoleErrors.push(`[${name}] ${e.message}`));
  await page.goto(`${BASE}/play/`);
  // Yukleme ekrani kaybolana kadar (index.html: #loader)
  await page.waitForFunction(() => getComputedStyle(document.getElementById('loader')).display === 'none',
                             null, { timeout: 120000 });
  await sleep(1500);   // ilk kareler
  return page;
}

async function shot(page, file) {
  const buf = await page.screenshot({ path: path.join(OUT, file) });
  return PNG.sync.read(buf);
}

function colorAt(png, { x, y }) {
  // 5x5 ortalama: kenar yumusatmasindan etkilenmesin
  let r = 0, g = 0, b = 0, n = 0;
  for (let dy = -2; dy <= 2; dy++)
    for (let dx = -2; dx <= 2; dx++) {
      const i = ((Math.round(y) + dy) * png.width + Math.round(x) + dx) * 4;
      r += png.data[i]; g += png.data[i + 1]; b += png.data[i + 2]; n++;
    }
  return [r / n, g / n, b / n];
}
const near = (a, b, tol = 40) => a.every((v, i) => Math.abs(v - b[i]) <= tol);

function readBoard(png) {
  const board = [];
  for (let row = 0; row < 6; row++) {
    board.push([]);
    for (let col = 0; col < 7; col++) {
      const c = colorAt(png, cellCenter(col, row));
      board[row].push(near(c, COLORS.red) ? 'R' : near(c, COLORS.yellow) ? 'Y' : near(c, COLORS.empty) ? '.' : '?');
    }
  }
  return board;
}
const boardText = b => b.slice().reverse().map(r => r.join(' ')).join('\n');
const countOf = (b, ch) => b.flat().filter(c => c === ch).length;

// Unity girdiyi karede bir okur; yazilimsal WebGL'de kareler yavas oldugu icin
// bas-birak ayni karede kalirsa tiklama kacabilir. Imlec once butona gelir
// (hover), sonra kisa bir sure basili tutulur.
async function click(page, p, wait = 700) {
  await page.mouse.move(p.x, p.y);
  await sleep(200);
  await page.mouse.down();
  await sleep(150);
  await page.mouse.up();
  await sleep(wait);
}

// Unity'nin Debug.Log satirlarini bekler (Game/AppController.cs, Net/GameSocket.cs)
async function waitLog(page, re, timeout = 15000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (page.logs.some(l => re.test(l))) return true;
    await sleep(200);
  }
  return false;
}

async function guestLogin(page, pos = UI.guest) {
  for (let attempt = 0; attempt < 3; attempt++) {
    await click(page, pos, 300);
    if (await waitLog(page, /\[App\] Oturum acildi: Misafir_/, 5000)) return true;
  }
  return false;
}
const dropIn = (page, col, wait = 1200) => click(page, cellCenter(col, 3), wait);

async function waitForBoard(page, predicate, file, timeout = 15000) {
  const deadline = Date.now() + timeout;
  let board;
  while (Date.now() < deadline) {
    board = readBoard(await shot(page, file));
    if (predicate(board)) return board;
    await sleep(500);
  }
  return board;
}

// Kayitli kullaniciyla giris (LoginView alanlarina yazilir)
async function loginAs(page, user) {
  await click(page, UI.loginUser, 300);
  await page.keyboard.type(user.name, { delay: 40 });
  await click(page, UI.loginPass, 300);
  await page.keyboard.type(user.password, { delay: 40 });
  await click(page, UI.loginButton, 300);
  return waitLog(page, new RegExp(`\\[App\\] Oturum acildi: ${user.name} \\(misafir=False\\)`), 15000);
}

// Rastgele test kullanicisi (gercek hesap degil). Veritabani yoksa sunucu 503 doner.
async function signupTestUser(prefix) {
  const name = `e2e${prefix}_${crypto.randomBytes(4).toString('hex')}`;   // <= 20 karakter
  const password = crypto.randomBytes(12).toString('hex');
  try {
    const r = await fetch(`${BASE}/signup`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: name, password }),
    });
    return { ok: r.status === 201, status: r.status, name, password };
  } catch (e) {
    return { ok: false, status: String(e), name, password };
  }
}

async function activeGames() {
  const r = await fetch(`${BASE}/active_games`);
  return r.json();
}

try {
  // ---------------------------------------------------------------- 1. Yukleme
  const a = await openGame('A');
  await shot(a, '01-giris.png');
  check(true, 'oyun tarayicida yuklendi (WebGL)');
  check(a.logs.some(l => l.includes('[App] Hazir')), 'uygulama basladi ([App] Hazir)');
  const langLogs = (p, code) => p.logs.filter(l => l.includes(`[App] Dil: ${code}`)).length;
  check(langLogs(a, 'en') === 1, 'Ingilizce tarayicida oyun Ingilizce acildi');
  await click(a, UI.lang);
  check(await waitLog(a, /\[App\] Dil: tr/, 5000), 'dil dugmesi: Turkceye gecti');
  await shot(a, '01b-giris-tr.png');
  await click(a, UI.lang);
  const backToEn = Date.now() + 5000;
  while (langLogs(a, 'en') < 2 && Date.now() < backToEn) await sleep(200);
  check(langLogs(a, 'en') === 2, 'dil dugmesi: Ingilizceye geri dondu');
  const t = await openGame('TR', undefined, 'tr-TR');
  check(langLogs(t, 'tr') === 1, 'Turkce tarayicida oyun Turkce acildi');
  await shot(t, '01c-giris-tr-tarayici.png');
  await t.context().close();

  // ------------------------------------------------- 2. Misafir girisi -> menu
  check(await guestLogin(a), 'misafir girisi');
  await shot(a, '02-menu.png');

  // ------------------------------------------------------- 3. AI'ya karsi mac
  await click(a, UI.menuAI);
  await shot(a, '03-zorluk.png');
  await click(a, UI.easy, 1500);
  let board = readBoard(await shot(a, '04-ai-bos-tahta.png'));
  check(countOf(board, '.') === 42, 'AI maci bos tahtayla basladi\n' + boardText(board));

  await dropIn(a, 3);
  board = await waitForBoard(a, b => countOf(b, 'Y') === 1, '05-ai-ilk-hamle.png');
  check(board[0][3] === 'R', 'oyuncunun tasi 3. sutunun dibine dustu');
  check(countOf(board, 'Y') === 1, 'AI cevap verdi (1 sari tas)\n' + boardText(board));

  for (const col of [2, 4]) {
    const before = countOf(board, 'Y');
    await dropIn(a, col);
    board = await waitForBoard(a, b => countOf(b, 'Y') === before + 1, '06-ai-mac.png');
  }
  check(countOf(board, 'R') === 3 && countOf(board, 'Y') === 3, 'AI ile 3 tur oynandi\n' + boardText(board));
  await a.close();

  // ---------------------------------------------------------- 4. Online mac
  const p1 = await openGame('P1');
  check(await guestLogin(p1), 'P1 misafir girisi');
  await click(p1, UI.menuLobby, 1500);
  await shot(p1, '07-lobi.png');
  await click(p1, UI.lobbyCreate, 1500);
  check(await waitLog(p1, /\[GameSocket\] Sunucuya baglandi/), 'P1 Socket.IO ile baglandi');
  await sleep(1000);
  await shot(p1, '08-rakip-bekleniyor.png');
  let games = await activeGames();
  const waiting = games.find(g => g.status === 'WAITING');
  check(!!waiting, 'P1 oda olusturdu: ' + (waiting && waiting.room_id));

  const p2 = await openGame('P2');
  check(await guestLogin(p2), 'P2 misafir girisi');
  await click(p2, UI.menuLobby, 3500);                  // lobi listesi 2 sn'de bir yenilenir
  await shot(p2, '09-lobi-oda-gorunuyor.png');
  await click(p2, UI.lobbyRow0Action, 1000);
  await waitLog(p1, /\[App\] Online oyun basliyor/);
  await sleep(1000);
  games = await activeGames();
  check(games.some(g => g.status === 'PLAYING'), 'P2 lobiden odaya katildi, oyun basladi');

  // P1 (kirmizi) 3. sutunda dikey dortlu yapar; P2 (sari) 2. sutuna oynar
  const plan = [[p1, 3], [p2, 2], [p1, 3], [p2, 2]];
  for (const [page, col] of plan) await dropIn(page, col, 1500);
  board = await waitForBoard(p2, b => countOf(b, 'R') === 2 && countOf(b, 'Y') === 2, '10-online-p2.png');
  check(countOf(board, 'R') === 2 && countOf(board, 'Y') === 2, 'hamleler rakibin ekranina yansidi\n' + boardText(board));

  // ------------------------------------------------------------ 5. Seyirci
  const sp = await openGame('Seyirci');
  check(await guestLogin(sp), 'seyirci misafir girisi');
  await click(sp, UI.menuLobby, 3500);
  await click(sp, UI.lobbyRow0Action, 2500);            // oyundaki odada buton "Izle"
  board = await waitForBoard(sp, b => countOf(b, 'R') === 2 && countOf(b, 'Y') === 2, '11-seyirci.png');
  check(countOf(board, 'R') === 2 && countOf(board, 'Y') === 2, 'seyirci mevcut durumu gordu\n' + boardText(board));

  for (const [page, col] of [[p1, 3], [p2, 2], [p1, 3]]) await dropIn(page, col, 1500);
  // Oyun kazanilinca dortlu disindaki taslar soluk cizilir (UI/BoardView.cs DimAlpha):
  // kaybedenin taslari artik '?' okunur, bu yuzden kazanandan sonra yalnizca kirmizi sayilir.
  board = await waitForBoard(p1, b => countOf(b, 'R') === 4, '12-online-kazanan-p1.png');
  check(board[0][3] === 'R' && board[1][3] === 'R' && board[2][3] === 'R' && board[3][3] === 'R',
        'P1 dikey dortlu yapti\n' + boardText(board));
  await shot(p2, '13-online-kaybeden-p2.png');
  board = await waitForBoard(sp, b => countOf(b, 'R') === 4, '14-seyirci-son.png');
  check(countOf(board, 'R') === 4, 'seyirci oyunun sonunu canli gordu');
  games = await activeGames();
  check(!games.some(g => g.status === 'PLAYING'), 'biten oyun lobiden kalkti');

  // ------------------------------------------------------- 5b. Mac tekrari
  // Misafirlerin gecmisi tutulmaz: tekrar biten oyunun "Tekrari izle" dugmesiyle acilir
  // (UI/Views.cs GameView: panelde (400, 345); ReplayView: tahta ayni yerde, son (520, 430)).
  // Sayac kanvasa cizildigi icin ReplayView'in "[Replay] Hamle k / n" satirindan okunur.
  await click(p1, UI.replayOpen, 1000);
  check(await waitLog(p1, /\[App\] Tekrar acildi: 7 hamle/), 'P1 biten oyunun tekrarini acti (7 hamle)');
  check(await waitLog(p1, /\[Replay\] Hamle 0 \/ 7/), 'tekrar sayaci: 0 / 7');
  board = await waitForBoard(p1, b => countOf(b, '.') === 42, '14b-tekrar-bas.png');
  check(countOf(board, '.') === 42, 'tekrar bos tahtadan basladi\n' + boardText(board));
  await click(p1, UI.replayLast, 1000);
  check(await waitLog(p1, /\[Replay\] Hamle 7 \/ 7/), 'son dugmesiyle sayac 7 / 7 oldu');
  board = await waitForBoard(p1, b => countOf(b, 'R') === 4, '14c-tekrar-son.png');
  check(board[0][3] === 'R' && board[3][3] === 'R' && countOf(board, 'R') === 4,
        'tekrarin sonunda dikey dortlu gorunuyor\n' + boardText(board));
  await p1.keyboard.down('ArrowLeft');
  await sleep(150);
  await p1.keyboard.up('ArrowLeft');
  check(await waitLog(p1, /\[Replay\] Hamle 6 \/ 7/), 'sol ok bir hamle geri aldi (6 / 7)');
  board = await waitForBoard(p1, b => countOf(b, 'R') === 3 && countOf(b, 'Y') === 3, '14d-tekrar-geri.png');
  check(countOf(board, 'R') === 3 && countOf(board, 'Y') === 3, 'tahta 6. hamledeki durumda\n' + boardText(board));

  // ------------------------------------------------- 5b2. Sureli mac (3+2)
  // T1 lobide sure secimini 3+2'ye cevirir ve oda kurar; T2 lobiden katilir. Saat kanvasa
  // cizildigi icin GameView'in "[Game] Saat gorunuyor: 3:00 | 3:00" satiri ve AppController'in
  // her saat tasiyan sunucu olayinda yazdigi "[App] Saat 3+2: <P1> / <P2> (isleyen n)" satiri
  // okunur. T1 baslangic payi (5 sn) icinde oynar: ek sureyle saati 3:00'dan ayrilir
  // (paydaysa 3:02) ve saat T2'ye gecer.
  const t1 = await openGame('T1');
  check(await guestLogin(t1), 'T1 misafir girisi');
  await click(t1, UI.menuLobby, 1500);
  await click(t1, UI.lobbyTime, 800);
  check(await waitLog(t1, /\[App\] Sure secimi: 3\+2/, 5000), 'T1 lobide 3+2 secti');
  await shot(t1, '14s1-lobi-3+2-secimi.png');
  await click(t1, UI.lobbyCreate, 1500);
  check(await waitLog(t1, /\[GameSocket\] Sunucuya baglandi/), 'T1 Socket.IO ile baglandi');
  await sleep(1000);
  games = await activeGames();
  const timedRoom = games.find(g => g.status === 'WAITING');
  check(!!timedRoom && timedRoom.time_control === '3+2', 'T1 3+2 oda kurdu: ' + JSON.stringify(timedRoom));

  const t2 = await openGame('T2');
  check(await guestLogin(t2), 'T2 misafir girisi');
  await click(t2, UI.menuLobby, 3500);
  await shot(t2, '14s2-lobi-3+2-etiketi.png');
  await click(t2, UI.lobbyRow0Action, 1000);
  check(await waitLog(t1, /\[Game\] Saat gorunuyor: 3:00 \| 3:00/), 'T1 ekraninda iki saat 3:00 gorunuyor');
  check(await waitLog(t2, /\[Game\] Saat gorunuyor: 3:00 \| 3:00/), 'T2 ekraninda iki saat 3:00 gorunuyor');
  await shot(t2, '14s3-sureli-mac-t2.png');
  await dropIn(t1, 3, 1500);
  check(await waitLog(t2, /\[App\] Saat 3\+2: (?!3:00 )\d+:\d\d \/ 3:00 \(isleyen 2\)/),
        'hamleden sonra T1 saati degisti, saat T2\'de isliyor: ' +
        t2.logs.filter(l => l.includes('[App] Saat')).join(' ; '));
  board = await waitForBoard(t2, b => countOf(b, 'R') === 1, '14s4-sureli-mac-hamle.png');
  check(board[0][3] === 'R', 'T1 hamlesi T2 ekranina yansidi\n' + boardText(board));
  await t1.close();
  await t2.close();

  // ------------------------------------------------------- 5c. Hizli mac
  // Iki sayfa menude "Hizli Mac"a basar: ilk giren P1 (kirmizi), ikincisi P2 olur ve
  // ikisi de oda kodu girmeden oyun ekranina gecer (sunucu: quick_match_join kuyrugu).
  const q1 = await openGame('Q1');
  check(await guestLogin(q1), 'Q1 misafir girisi');
  await click(q1, UI.menuQuick, 1500);
  check(await waitLog(q1, /\[App\] Hizli eslesme: rakip araniyor/), 'Q1 hizli mac aramasina girdi');
  check(await waitLog(q1, /\[GameSocket\] Sunucuya baglandi/), 'Q1 Socket.IO ile baglandi');
  await sleep(1000);
  await shot(q1, '14e-hizli-mac-araniyor.png');
  check(!q1.logs.some(l => l.includes('[App] Online oyun basliyor')), 'Q1 tek basina eslesmedi (rakip araniyor)');

  const q2 = await openGame('Q2');
  check(await guestLogin(q2), 'Q2 misafir girisi');
  await click(q2, UI.menuQuick, 1500);
  check(await waitLog(q1, /\[App\] Online oyun basliyor/), 'Q1 eslesti, oyun ekranina gecti');
  check(await waitLog(q2, /\[App\] Online oyun basliyor/), 'Q2 eslesti, oyun ekranina gecti');
  board = await waitForBoard(q2, b => countOf(b, '.') === 42, '14f-hizli-mac-q2.png');
  check(countOf(board, '.') === 42, 'hizli mac bos tahtayla basladi\n' + boardText(board));
  games = await activeGames();
  check(games.some(g => g.status === 'PLAYING'), 'hizli mac odasi lobide oyunda gorunuyor');
  await dropIn(q1, 3, 1500);                              // ilk giren P1: ilk hamle onun
  board = await waitForBoard(q2, b => countOf(b, 'R') === 1, '14g-hizli-mac-hamle.png');
  check(board[0][3] === 'R', 'Q1 (kirmizi) hamlesi Q2 ekranina yansidi\n' + boardText(board));

  // ------------------------------------------------------- 5d. Hazir sohbet
  // Q1 "Sohbet"e basar, paneldeki ilk mesaji ("İyi oyun!") secer. Sunucu chat_message'i
  // odaya yayar; Q2'de P1 (ust) satirinin solunda beyaz balon 3 sn gorunur. Balon kanvasa
  // cizildigi icin hem AppController'in "[App] Sohbet: ..." satiri hem de balonun dolgusu
  // (Theme.White, yazinin solundaki bos kisim) piksel rengiyle denetlenir.
  const BUBBLE_WHITE = [234, 234, 234];
  await click(q1, UI.chatOpen, 1000);
  await shot(q1, '14h-sohbet-paneli.png');
  await click(q1, UI.chatMsg0, 300);
  check(await waitLog(q2, /\[App\] Sohbet: oyuncu 1 mesaj 0/, 5000), 'Q2 "İyi oyun!" mesajini aldi');
  check(await waitLog(q1, /\[App\] Sohbet: oyuncu 1 mesaj 0/, 5000), 'Q1 kendi mesajinin yankisini aldi');
  const bubblePng = await shot(q2, '14i-sohbet-balonu.png');
  check(near(colorAt(bubblePng, UI.bubbleP1), BUBBLE_WHITE, 25),
        `Q2 ekraninda P1 adinin yaninda balon gorunuyor (renk ${colorAt(bubblePng, UI.bubbleP1).map(Math.round)})`);
  check(!near(colorAt(bubblePng, UI.bubbleP2), BUBBLE_WHITE, 25), 'P2 satirinda balon yok');
  await sleep(3500);
  const goneP = await shot(q2, '14j-sohbet-balonu-gitti.png');
  check(!near(colorAt(goneP, UI.bubbleP1), BUBBLE_WHITE, 25), 'balon 3 sn sonra kayboldu');
  await q1.close();
  await q2.close();

  // ----------------------------------------------- 5e. Turnuvalar (misafir)
  // Misafir menude "Turnuvalar"a basar: liste ekrani acilir (bos ya da dolu), "+ Turnuva Aç"
  // dugmesi yoktur. Liste kanvasa cizildigi icin TournamentsView'in "[Turnuvalar] Liste: ..."
  // satiri ve dugmenin yerindeki arka plan rengi okunur. Veritabani gerekmez.
  const tg = await openGame('TurnuvaMisafir');
  check(await guestLogin(tg), 'turnuva: misafir girisi');
  await click(tg, UI.menuTournaments, 1500);
  check(await waitLog(tg, /\[Turnuvalar\] Liste: \d+ turnuva, acma dugmesi yok/, 10000),
        'misafir Turnuvalar listesini gordu, acma dugmesi yok: ' +
        tg.logs.filter(l => l.includes('[Turnuvalar]')).join(' ; '));
  const tgPng = await shot(tg, '14k-turnuvalar-misafir.png');
  check(near(colorAt(tgPng, UI.tCreate), COLORS.background, 12),
        `misafir ekraninda "+ Turnuva Aç" cizilmedi (renk ${colorAt(tgPng, UI.tCreate).map(Math.round)})`);
  await tg.close();

  // ------------------------------------- 5f. Arena turnuvasi (iki kayitli oyuncu)
  // A turnuva acar (15 dk, hemen), B listeden katilir, A sayfasindan katilir. Sunucu turnuvayi
  // en gec ~10 sn icinde baslatir ve ikisini eslestirir: ikisi de 3+2 saati (3:00) gorur. Bir
  // misafir seyirci turnuva sayfasini acar ve puan durumunda iki oyuncu gorur.
  const localServer = ['localhost', '127.0.0.1', '[::1]'].includes(new URL(BASE).hostname);
  const userA = localServer ? await signupTestUser('A') : { ok: false, status: 'yerel olmayan sunucu' };
  const userB = userA.ok ? await signupTestUser('B') : userA;
  if (!userA.ok || !userB.ok) {
    const why = `test kullanicisi kaydedilemedi (${userA.ok ? userB.status : userA.status}; ` +
                'sunucunun veritabani yok ya da sunucu yerel degil)';
    // CI (E2E_REQUIRE_DB=1) veritabaniyla calisir: atlama orada hata sayilir
    if (process.env.E2E_REQUIRE_DB === '1') check(false, 'arena: ' + why);
    else console.log(`::notice::Arena adimi atlandi: ${why}`);
  } else {
    const ta = await openGame('ArenaA');
    check(await loginAs(ta, userA), `arena: A (${userA.name}) giris yapti`);
    await click(ta, UI.menuTournaments, 1500);
    check(await waitLog(ta, /\[Turnuvalar\] Liste: \d+ turnuva, acma dugmesi var/, 10000), 'arena: A listede "+ Turnuva Aç" goruyor');
    await click(ta, UI.tCreate, 800);
    await click(ta, UI.tDur15, 500);
    await shot(ta, '14l-turnuva-ac-formu.png');
    await click(ta, UI.tSubmit, 1000);
    check(await waitLog(ta, /\[App\] Turnuva aciliyor: 15 dk, 0 dk sonra/, 5000), 'arena: A 15 dk, hemen baslayan turnuva istedi');
    check(await waitLog(ta, /\[App\] Turnuva acildi: \d+/, 10000), 'arena: sunucu turnuvayi acti (arena_created)');
    const created = ta.logs.find(l => /\[App\] Turnuva acildi: \d+/.test(l));
    const tid = created ? Number(created.match(/acildi: (\d+)/)[1]) : -1;
    await sleep(1000);
    await shot(ta, '14m-turnuva-sayfasi-a.png');

    const tb = await openGame('ArenaB');
    check(await loginAs(tb, userB), `arena: B (${userB.name}) giris yapti`);
    await click(tb, UI.menuTournaments, 1500);
    check(await waitLog(tb, /\[Turnuvalar\] Liste: [1-9]\d* turnuva, acma dugmesi var/, 10000), 'arena: B listede turnuvayi goruyor');
    await shot(tb, '14n-turnuvalar-b.png');
    await click(tb, UI.tRow0Action, 1000);
    check(await waitLog(tb, new RegExp(`\\[App\\] Turnuvaya katiliniyor: ${tid}\\b`), 5000), 'arena: B listeden katildi');
    await click(ta, UI.tPageAction, 1000);
    check(await waitLog(ta, new RegExp(`\\[App\\] Turnuvaya katiliniyor: ${tid}\\b`), 5000), 'arena: A sayfasindan katildi');

    check(await waitLog(ta, /\[App\] Online oyun basliyor/, 45000), 'arena: A eslesti, oyun basladi');
    check(await waitLog(tb, /\[App\] Online oyun basliyor/, 15000), 'arena: B eslesti, oyun basladi');
    check(await waitLog(ta, /\[Game\] Saat gorunuyor: 3:00 \| 3:00/), 'arena: A ekraninda iki saat 3:00');
    check(await waitLog(tb, /\[Game\] Saat gorunuyor: 3:00 \| 3:00/), 'arena: B ekraninda iki saat 3:00');
    await shot(ta, '14o-turnuva-oyunu-a.png');

    const ts = await openGame('ArenaSeyirci');
    check(await guestLogin(ts), 'arena: seyirci misafir girisi');
    await click(ts, UI.menuTournaments, 1500);
    check(await waitLog(ts, /\[Turnuvalar\] Liste: [1-9]\d* turnuva, acma dugmesi yok/, 10000), 'arena: seyirci listeyi gordu');
    await click(ts, UI.tRow0Action, 1500);                 // misafirde satir dugmesi "Izle"
    check(await waitLog(ts, new RegExp(`\\[Turnuva\\] Siralama: 2 oyuncu \\(turnuva ${tid}\\)`), 15000),
          'arena: puan durumunda iki oyuncu gorunuyor: ' + ts.logs.filter(l => l.includes('[Turnuva]')).join(' ; '));
    await shot(ts, '14p-turnuva-siralama.png');
    const detail = await (await fetch(`${BASE}/tournaments/${tid}`)).json();
    check(detail.standings && detail.standings.length === 2 && detail.tournament.status === 'running',
          'arena: sunucuda turnuva suruyor, 2 katilimci: ' + JSON.stringify(detail));
    await ts.close();
    await ta.close();
    await tb.close();
  }

  // ------------------------------------------------- 6. Dik (portrait) ekran
  // 540x960 pencere, deviceScaleFactor 1: canvas 9:16 ve CanvasScaler olcegi tam 1, yani
  // sayfa pikseli = (270 + x, y) (UI/Views.cs'deki P(...) koordinatlari, y ogenin merkezi).
  // Tahta (UI/BoardView.cs dik): hucre 72 px, merkez x = 270; hucre merkezi
  // x = 54 + 72*sutun, y = 525 - 72*satir (satir 0 altta).
  const atP = (x, y) => ({ x: 270 + x, y });
  const PUI = { guest: atP(0, 660), menuAI: atP(0, 418), easy: atP(0, 320) };   // dik menu adimi 78
  const pCell = (col, row) => ({ x: 54 + 72 * col, y: 525 - 72 * row });
  const readPortraitBoard = png => {
    const b = [];
    for (let row = 0; row < 6; row++) {
      b.push([]);
      for (let col = 0; col < 7; col++) {
        const c = colorAt(png, pCell(col, row));
        b[row].push(near(c, COLORS.red) ? 'R' : near(c, COLORS.yellow) ? 'Y' : near(c, COLORS.empty) ? '.' : '?');
      }
    }
    return b;
  };

  const pp = await openGame('Dik', { width: 540, height: 960 });
  const box = await pp.evaluate(() => {
    const r = document.getElementById('unity-canvas').getBoundingClientRect();
    return { w: r.width, h: r.height };
  });
  check(Math.round(box.w) === 540 && Math.round(box.h) === 960, `dik pencerede canvas 9:16 (${box.w}x${box.h})`);
  await shot(pp, '15-dik-giris.png');
  check(await guestLogin(pp, PUI.guest), 'dik: misafir girisi (dik konum)');
  await shot(pp, '16-dik-menu.png');
  await click(pp, PUI.menuAI);
  await click(pp, PUI.easy, 1500);
  let pboard = readPortraitBoard(await shot(pp, '17-dik-bos-tahta.png'));
  check(countOf(pboard, '.') === 42, 'dik: AI maci bos tahtayla basladi\n' + boardText(pboard));
  await click(pp, atP(0, 345), 1500);                   // sutun 3, tahtanin ustunde herhangi bir yer
  const pdeadline = Date.now() + 15000;
  while (Date.now() < pdeadline) {
    pboard = readPortraitBoard(await shot(pp, '18-dik-ilk-hamle.png'));
    if (countOf(pboard, 'Y') === 1) break;
    await sleep(500);
  }
  check(pboard[0][3] === 'R', 'dik: oyuncunun tasi 3. sutunun dibine dustu (dik hucre merkezinden okundu)\n' + boardText(pboard));
  check(countOf(pboard, 'Y') === 1, 'dik: AI cevap verdi (1 sari tas)');
  await pp.close();

  // ------------------------------------------- 7. Kare pencere (Review Focus 5)
  // 800x800: kare pencere yatay sayilir (index.html: yalnizca yukseklik > genislik dik;
  // ScreenLayout.For ayni kural). Canvas 16:9 (800x450) olmali; CanvasScaler olcegi (esleme 0.5)
  // sqrt((cw/1280)*(ch/720)) ile hesaplanir ve yatay misafir dugmesine tiklanir.
  const sp2 = await openGame('Kare', { width: 800, height: 800 });
  const sbox = await sp2.evaluate(() => {
    const r = document.getElementById('unity-canvas').getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height };
  });
  check(sbox.w > sbox.h && Math.round(sbox.w) === 800 && Math.round(sbox.h) === 450,
        `kare pencerede canvas yatay 16:9 (${sbox.w}x${sbox.h})`);
  const sScale = Math.sqrt((sbox.w / 1280) * (sbox.h / 720));
  const sPos = { x: sbox.x + sbox.w / 2 + 0 * sScale, y: sbox.y + 540 * sScale };
  console.log(`kare pencere: canvas ${sbox.w}x${sbox.h} @(${sbox.x},${sbox.y}), olcek ${sScale.toFixed(3)}`);
  await shot(sp2, '19-kare-giris.png');
  check(await guestLogin(sp2, sPos), 'kare pencere (800x800): yatay duzende misafir girisi calisti');
  await shot(sp2, '20-kare-menu.png');
  await sp2.close();
} catch (e) {
  check(false, 'beklenmeyen hata: ' + (e && e.stack || e));
} finally {
  await browser.close();
}

const relevantErrors = consoleErrors.filter(e => !/favicon|DevTools/.test(e));
check(relevantErrors.length === 0, 'tarayici konsolunda hata yok' +
      (relevantErrors.length ? ':\n  ' + relevantErrors.join('\n  ') : ''));
fs.writeFileSync(path.join(OUT, 'sonuc.txt'), results.join('\n') + '\n');
console.log(failures === 0 ? '\nTUM UCTAN UCA TESTLER GECTI' : `\n${failures} TEST BASARISIZ`);
process.exit(failures ? 1 : 0);
