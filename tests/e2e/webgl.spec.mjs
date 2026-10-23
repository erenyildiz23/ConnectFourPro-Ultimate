// =============================================================================
// webgl.spec.mjs - Connect Four Pro Ultimate
// Unity WebGL build'ini gercek Chromium'da, gercek sunucuya karsi oynayan
// uctan uca test (use case'ler: misafir girisi, AI maci, online mac, seyirci)
// =============================================================================
//
// Kullanim (sunucu calisirken, build CONNECT4_WEB_BUILD'den sunuluyorken):
//   cd tests/e2e && npm ci && npx playwright install chromium
//   BASE_URL=http://localhost:5000 node webgl.spec.mjs
//
// Arayuz canvas'a cizildigi icin DOM yoktur. Tiklamalar Unity tarafindaki
// yerlesimden hesaplanir (UI/UIKit.cs Place: 1280x720 referans, ust-orta
// merkezli; UI/BoardView.cs: tahta merkezi (-250, 375), hucre 80 px). Pencere
// 1280x720 oldugu icin CanvasScaler olcegi 1'dir. Tahtadaki taslar ekran
// goruntusunden piksel rengiyle okunur.

import { chromium } from 'playwright';
import { PNG } from 'pngjs';
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
  menuAI: at(0, 200), menuLobby: at(0, 266),
  easy: at(0, 200),
  lobbyCreate: at(-470, 110), lobbyRow0Action: at(470, 225),
};
const cellCenter = (col, row) => at(-250 - 280 + col * 80 + 40, 375 + 240 - row * 80 - 40);
const COLORS = { red: [233, 69, 96], yellow: [241, 196, 15], empty: [10, 10, 21] };

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

async function openGame(name) {
  const context = await browser.newContext({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1 });
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

async function guestLogin(page) {
  for (let attempt = 0; attempt < 3; attempt++) {
    await click(page, UI.guest, 300);
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
  board = await waitForBoard(p1, b => countOf(b, 'R') === 4, '12-online-kazanan-p1.png');
  check(board[0][3] === 'R' && board[1][3] === 'R' && board[2][3] === 'R' && board[3][3] === 'R',
        'P1 dikey dortlu yapti\n' + boardText(board));
  await shot(p2, '13-online-kaybeden-p2.png');
  board = await waitForBoard(sp, b => countOf(b, 'R') === 4, '14-seyirci-son.png');
  check(countOf(board, 'R') === 4, 'seyirci oyunun sonunu canli gordu');
  games = await activeGames();
  check(!games.some(g => g.status === 'PLAYING'), 'biten oyun lobiden kalkti');
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
