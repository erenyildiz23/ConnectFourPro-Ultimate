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
  lang: at(560, 50),   // dil dugmesi (GameBootstrap; yalnizca giris ve menu)
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

  // ------------------------------------------------- 6. Dik (portrait) ekran
  // 540x960 pencere, deviceScaleFactor 1: canvas 9:16 ve CanvasScaler olcegi tam 1, yani
  // sayfa pikseli = (270 + x, y) (UI/Views.cs'deki P(...) koordinatlari, y ogenin merkezi).
  // Tahta (UI/BoardView.cs dik): hucre 72 px, merkez x = 270; hucre merkezi
  // x = 54 + 72*sutun, y = 525 - 72*satir (satir 0 altta).
  const atP = (x, y) => ({ x: 270 + x, y });
  const PUI = { guest: atP(0, 660), menuAI: atP(0, 340), easy: atP(0, 320) };
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
