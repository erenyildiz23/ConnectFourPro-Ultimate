#!/usr/bin/env python3
# =============================================================================
# VISUALIZATION & REPORT v4.0
# results/*.json -> visualization_outputs/*.png + RESULTS.md
# =============================================================================
"""
Sadece olculmus veriler kullanilir. Bir sonuc dosyasi yoksa ilgili grafikler
uretilmez ve raporda "olculmedi" olarak gecer - varsayilan/ornek veri YOKTUR.

Kullanim:  python visualize_all_results.py
"""

import os
from typing import List, Optional

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

import bench_common as bc  # noqa: E402

# --- Palet (dataviz referans paleti, acik tema; validate_palette.js ile dogrulandi) ---
SURFACE = '#fcfcfb'
INK = '#0b0b0b'
INK_2 = '#52514e'
GRID = '#e4e3df'
S1, S2, S3 = '#2a78d6', '#eb6834', '#1baf7a'          # kategorik sira: mavi, turuncu, turkuaz
CRITICAL = '#d03b3b'
DIVERGING = LinearSegmentedColormap.from_list('blue_gray_red', ['#e34948', '#f0efec', '#2a78d6'])

plt.rcParams.update({
    'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE,
    'axes.edgecolor': GRID, 'axes.labelcolor': INK_2, 'axes.titlecolor': INK,
    'axes.titlesize': 13, 'axes.titleweight': 'bold', 'axes.labelsize': 11,
    'xtick.color': INK_2, 'ytick.color': INK_2, 'text.color': INK,
    'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.8, 'axes.axisbelow': True,
    'axes.spines.top': False, 'axes.spines.right': False,
    'lines.linewidth': 2, 'lines.markersize': 7, 'legend.frameon': False,
    'font.size': 10, 'figure.dpi': 110,
})

FIGURES: List[str] = []


def save(fig, name):
    os.makedirs(bc.FIGURES_DIR, exist_ok=True)
    fig.savefig(os.path.join(bc.FIGURES_DIR, name), dpi=200, bbox_inches='tight')
    plt.close(fig)
    FIGURES.append(name)
    bc.progress(f"  [OK] {name}")


def target_line(ax, y, label, horizontal=True):
    (ax.axhline if horizontal else ax.axvline)(y, color=CRITICAL, linestyle='--', linewidth=1.2)
    if horizontal:
        ax.annotate(label, xy=(1, y), xycoords=('axes fraction', 'data'), xytext=(-4, 4),
                    textcoords='offset points', ha='right', va='bottom', color=INK_2, fontsize=9)
    else:
        ax.annotate(label, xy=(y, 1), xycoords=('data', 'axes fraction'), xytext=(4, -4),
                    textcoords='offset points', ha='left', va='top', color=INK_2, fontsize=9)


def bar_labels(ax, bars, fmt):
    for b in bars:
        ax.annotate(fmt(b.get_height()), (b.get_x() + b.get_width() / 2, b.get_height()),
                    xytext=(0, 3), textcoords='offset points', ha='center', va='bottom', fontsize=8.5, color=INK)


# =============================================================================
# AI
# =============================================================================

def ai_charts(ai):
    lat = ai['latency_summary']
    depths = sorted(int(d) for d in lat)
    mean = [lat[str(d)]['mean'] for d in depths]
    p95 = [lat[str(d)]['p95'] for d in depths]
    nodes = [lat[str(d)]['mean_nodes'] for d in depths]
    us_node = [lat[str(d)]['us_per_node'] for d in depths]

    fig, ax = plt.subplots(figsize=(8, 4.6))
    bars = ax.bar(depths, mean, color=S1, width=0.5, label='Ortalama')
    # p95 noktalari cubugun sagina kaydirilir: degerle cakismasin
    ax.plot([d + 0.33 for d in depths], p95, 'o', color=S2, label='p95', zorder=3)
    ax.set_yscale('log')
    ax.set_xticks(depths)
    ax.set_xlabel('Arama derinligi')
    ax.set_ylabel('Hamle suresi (ms, log)')
    ax.set_title('AI hamle suresi - derinlige gore')
    ax.axhline(500, color=CRITICAL, linestyle='--', linewidth=1.2)
    ax.annotate('NFR-01 siniri: 500 ms', xy=(0, 500), xycoords=('axes fraction', 'data'), xytext=(4, 4),
                textcoords='offset points', ha='left', va='bottom', color=INK_2, fontsize=9)
    bar_labels(ax, bars, lambda v: f'{v:.1f}' if v < 100 else f'{v:.0f}')
    ax.legend(loc='center left')
    save(fig, 'ai_latency_vs_depth.png')

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    a1.semilogy(depths, nodes, 'o-', color=S1)
    for d, n in zip(depths, nodes, strict=True):
        a1.annotate(f'{n:,.0f}', (d, n), xytext=(0, 7), textcoords='offset points', ha='center', fontsize=8.5)
    a1.set_xticks(depths)
    a1.set_xlabel('Arama derinligi')
    a1.set_ylabel('Ziyaret edilen dugum (log)')
    a1.set_title('Ortalama dugum sayisi')
    a2.bar(depths, us_node, color=S1, width=0.6)
    a2.set_xticks(depths)
    a2.set_xlabel('Arama derinligi')
    a2.set_ylabel('Dugum basina sure (us)')
    a2.set_title('Dugum basina maliyet')
    bar_labels(a2, a2.patches, lambda v: f'{v:.0f}')
    fig.tight_layout()
    save(fig, 'ai_computational_complexity.png')

    acc = ai.get('scenario_accuracy_percent', {})
    if acc:
        sdepths = sorted(int(d) for d in acc)
        fig, ax = plt.subplots(figsize=(7, 4))
        bars = ax.bar(sdepths, [acc[str(d)] for d in sdepths], color=S1, width=0.6)
        bar_labels(ax, bars, lambda v: f'%{v:.0f}')
        n_sc = len({r['scenario'] for r in ai['scenario_results']})
        ax.set_ylim(0, 110)
        ax.set_xticks(sdepths)
        ax.set_xlabel('Arama derinligi')
        ax.set_ylabel('Dogru hamle orani (%)')
        ax.set_title(f'Taktik senaryolar ({n_sc} senaryo, cevaplar kesin aramayla dogrulandi)')
        save(fig, 'ai_scenarios.png')

    t = ai.get('tournament')
    if t:
        m = t['score_matrix_percent']
        tdepths = sorted(int(d) for d in m)
        grid = np.array([[m[str(r)][str(c)] for c in tdepths] for r in tdepths])
        fig, ax = plt.subplots(figsize=(6.4, 5.2))
        im = ax.imshow(grid, cmap=DIVERGING, vmin=0, vmax=100)
        ax.grid(False)
        ax.set_xticks(range(len(tdepths)), [f'D{d}' for d in tdepths])
        ax.set_yticks(range(len(tdepths)), [f'D{d}' for d in tdepths])
        ax.set_xlabel('Rakip derinlik')
        ax.set_ylabel('Oyuncu derinlik')
        games = t['results'][f'{tdepths[0]}-{tdepths[1]}']
        per = sum(games.values())
        ax.set_title(f'Turnuva puani (%) - eslesme basina {per} oyun')
        for i in range(len(tdepths)):
            for j in range(len(tdepths)):
                ax.text(j, i, f'{grid[i, j]:.0f}', ha='center', va='center', fontsize=10, color=INK)
        cb = fig.colorbar(im, ax=ax, fraction=0.046)
        cb.set_label('Puan % (galibiyet + beraberlik/2)', color=INK_2)
        save(fig, 'tournament_heatmap.png')


# =============================================================================
# AG
# =============================================================================

def network_charts(net):
    proto = net['protocol']
    ws, rest = proto['websocket_ping'], proto['rest_health']
    metrics = ['mean', 'median', 'p95', 'p99']
    labels = ['Ortalama', 'Medyan', 'p95', 'p99']
    x = np.arange(len(metrics))
    fig, ax = plt.subplots(figsize=(8, 4.4))
    b1 = ax.bar(x - 0.19, [ws[m] for m in metrics], 0.36, color=S1, label='WebSocket (latency_ping)')
    b2 = ax.bar(x + 0.19, [rest[m] for m in metrics], 0.36, color=S2, label='REST (GET /health)')
    bar_labels(ax, list(b1) + list(b2), lambda v: f'{v:.2f}')
    ax.set_xticks(x, labels)
    ax.set_ylabel('Gidis-donus suresi (ms)')
    ax.set_title(f"Protokol karsilastirmasi - veritabanisiz uc noktalar (n={ws['n']})")
    ax.legend(loc='upper left')
    save(fig, 'protocol_comparison.png')

    ops = net['operations']
    names = {'ws_create_game': 'WS create_game', 'rest_active_games': 'REST /active_games',
             'rest_signup_validation': 'REST /signup (dogrulama)', 'rest_leaderboard': 'REST /leaderboard',
             'rest_login': 'REST /login (PBKDF2)'}
    keys = sorted(ops, key=lambda k: ops[k]['mean'])
    fig, ax = plt.subplots(figsize=(8, 3.8))
    y = np.arange(len(keys))
    ax.barh(y, [ops[k]['mean'] for k in keys], color=S1, height=0.55, label='Ortalama')
    ax.plot([ops[k]['p95'] for k in keys], y, 'o', color=S2, label='p95')
    ax.set_xscale('log')
    ax.set_yticks(y, [names.get(k, k) for k in keys])
    for yi, k in zip(y, keys, strict=True):
        right = max(ops[k]['mean'], ops[k]['p95'])
        ax.annotate(f"{ops[k]['mean']:.1f} ms", (right, yi), xytext=(8, 0), textcoords='offset points',
                    va='center', fontsize=8.5)
    ax.set_xlim(right=max(max(ops[k]['p95'] for k in keys), 100) * 3)
    ax.set_xlabel('Sure (ms, log)')
    ax.set_title('Islem gecikmeleri')
    ax.legend(loc='lower right')
    target_line(ax, 100, 'NFR-07: 100 ms', horizontal=False)
    save(fig, 'operation_latency.png')

    pay = net['payload']
    fig, ax = plt.subplots(figsize=(7, 4))
    sizes = [p['payload_bytes'] for p in pay]
    ax.plot(sizes, [p['mean'] for p in pay], 'o-', color=S1, label='Ortalama')
    ax.plot(sizes, [p['p95'] for p in pay], 's--', color=S2, label='p95')
    ax.set_xscale('log', base=2)
    ax.set_xticks(sizes, [f'{s // 1024} KB' if s >= 1024 else f'{s} B' for s in sizes])
    ax.set_xlabel('Mesaj boyutu')
    ax.set_ylabel('Gidis-donus suresi (ms)')
    ax.set_title('WebSocket: mesaj boyutu - gecikme')
    ax.legend()
    save(fig, 'payload_vs_latency.png')

    conc = net['concurrency']
    rest_c, ws_c = conc['rest_leaderboard'], conc['websocket_ping']
    clients = [r['clients'] for r in rest_c]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    series = [('REST /leaderboard (DB)', rest_c, S1, 'o-'), ('WebSocket ping', ws_c, S2, 's-')]
    for label, rows, color, style in series:
        axes[0].plot(clients, [r['throughput_rps'] for r in rows], style, color=color, label=label)
        axes[1].plot(clients, [r.get('mean', 0) for r in rows], style, color=color, label=label)
        axes[2].plot(clients, [r['error_rate_percent'] for r in rows], style, color=color, label=label)
    axes[0].set_title('Verim')
    axes[0].set_ylabel('Istek / sn')
    target_line(axes[0], 500, 'NFR-04: 500 istek/sn')
    axes[1].set_title('Ortalama gecikme')
    axes[1].set_ylabel('ms')
    axes[2].set_title('Hata orani')
    axes[2].set_ylabel('%')
    axes[2].set_ylim(-0.5, max(5, max(r['error_rate_percent'] for _, rows, _, _ in series for r in rows) * 1.2))
    for a in axes:
        a.set_xscale('log')
        a.set_xticks(clients, [str(c) for c in clients])
        a.set_xlabel('Eszamanli istemci')
    axes[0].legend(loc='upper left')
    fig.suptitle(f"Eszamanlilik ({net['parameters']['duration_per_level_s']:.0f} sn / seviye)",
                 fontweight='bold', color=INK)
    fig.tight_layout()
    save(fig, 'concurrency_analysis.png')

    games = net['concurrent_games']
    k = [g['games'] for g in games]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    a1.plot(k, [g.get('mean', 0) for g in games], 'o-', color=S1, label='Ortalama')
    a1.plot(k, [g.get('p95', 0) for g in games], 's--', color=S2, label='p95')
    a1.set_xlabel('Eszamanli oyun (baglanti = 2 x oyun)')
    a1.set_ylabel('Hamle gidis-donus (ms)')
    a1.set_title('Hamle gecikmesi')
    a1.legend()
    bars = a2.bar([str(v) for v in k], [g['completion_percent'] for g in games], color=S1, width=0.55)
    bar_labels(a2, bars, lambda v: f'%{v:.0f}')
    a2.set_ylim(0, 110)
    a2.set_xlabel('Eszamanli oyun')
    a2.set_ylabel('Tamamlanan oyun (%)')
    a2.set_title('Oyun tamamlanma orani')
    fig.tight_layout()
    save(fig, 'concurrent_games.png')


def locust_charts(loc):
    tests = loc['tests']
    users = [t['users'] for t in tests]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    b = axes[0].bar([str(u) for u in users], [t['rps'] for t in tests], color=S1, width=0.55)
    bar_labels(axes[0], b, lambda v: f'{v:.0f}')
    axes[0].set_title('Verim')
    axes[0].set_ylabel('Istek / sn')
    x = np.arange(len(users))
    axes[1].bar(x - 0.19, [t['median_ms'] for t in tests], 0.36, color=S1, label='Medyan')
    axes[1].bar(x + 0.19, [t['p95_ms'] for t in tests], 0.36, color=S2, label='p95')
    axes[1].set_xticks(x, [str(u) for u in users])
    axes[1].set_title('Yanit suresi')
    axes[1].set_ylabel('ms')
    axes[1].legend()
    b = axes[2].bar([str(u) for u in users], [t['error_rate_percent'] for t in tests], color=S1, width=0.55)
    bar_labels(axes[2], b, lambda v: f'%{v:.2f}')
    axes[2].set_title('Hata orani')
    axes[2].set_ylabel('%')
    axes[2].set_ylim(0, max(1, max(t['error_rate_percent'] for t in tests) * 1.4))
    for a in axes:
        a.set_xlabel('Sanal kullanici')
    fig.suptitle(f"Locust yuk testi ({tests[0]['run_time']} / seviye)", fontweight='bold', color=INK)
    fig.tight_layout()
    save(fig, 'locust_load.png')


# =============================================================================
# NFR DEGERLENDIRMESI + RAPOR
# =============================================================================

def nfr_rows(ai, net, loc, fps):
    rows = []

    def add(req, target, measured, ok, note=''):
        rows.append((req, target, measured, 'GECTI' if ok else 'KALDI', note))

    if ai:
        d6 = ai['latency_summary'].get('6')
        if d6:
            add('NFR-01 AI D6 yanit suresi', '< 500 ms (ortalama)', f"ort {d6['mean']:.0f} ms, p95 {d6['p95']:.0f} ms",
                d6['mean'] < 500, '' if d6['p95'] < 500 else 'p95 sinirin uzerinde')
    if net:
        ws = net['protocol']['websocket_ping']
        add('NFR-02 WebSocket gecikmesi', '< 5 ms (ortalama)', f"ort {ws['mean']:.2f} ms, p99 {ws['p99']:.2f} ms",
            ws['mean'] < 5, f"tasima: {net['protocol']['transport']}")
        conc_rows = net['concurrency']['rest_leaderboard'] + net['concurrency']['websocket_ping']
        games = net['concurrent_games']
        max_conn = max([r['clients'] for r in conc_rows] + [g['connections'] for g in games])
        errors = sum(r['errors'] for r in conc_rows) + sum(g['errors'] for g in games)
        ok = errors == 0 and all(g['completion_percent'] == 100 for g in games)
        add('NFR-03 Eszamanli baglanti', '>= 50, hatasiz',
            f"{max_conn} eszamanli baglantiya kadar {errors} hata", ok and max_conn >= 50,
            '' if max_conn >= 50 else 'yetersiz olcum: 50 seviyesi test edilmedi')
        rest_max = max(r['throughput_rps'] for r in net['concurrency']['rest_leaderboard'])
        ws_max = max(r['throughput_rps'] for r in net['concurrency']['websocket_ping'])
        add('NFR-04 Sunucu verimi', '> 500 istek/sn', f"REST (DB) {rest_max:.0f}, WS {ws_max:.0f} istek/sn",
            rest_max > 500, 'REST, veritabani okuyan uc nokta')
        ops = net['operations']
        worst = max(ops['rest_leaderboard']['mean'], ops['rest_login']['mean'])
        add('NFR-07 Veritabani islemleri', '< 100 ms', f"leaderboard {ops['rest_leaderboard']['mean']:.1f} ms, "
            f"login {ops['rest_login']['mean']:.1f} ms", worst < 100, 'login sureyi PBKDF2 belirler')
    if fps:
        s = fps['ai_searching']
        add('NFR-05 GUI kare hizi', '>= 30 FPS', f"AI ararken ort {s['fps_mean']:.0f} FPS, p99 kare {s['p99']:.0f} ms",
            s['fps_mean'] >= 30, 'ekransiz (SDL dummy) olcum')
    if loc:
        worst = max(loc['tests'], key=lambda t: t['users'])
        add('Locust yuk testi', 'hata < %1', f"{worst['users']} kullanici: %{worst['error_rate_percent']:.2f} hata, "
            f"p95 {worst['p95_ms']:.0f} ms", worst['error_rate_percent'] < 1, '')
    return rows


def summary_dashboard(rows):
    fig, ax = plt.subplots(figsize=(13, 0.6 + 0.48 * len(rows)))
    ax.axis('off')
    table = ax.table(cellText=[r[:4] for r in rows], colLabels=['Gereksinim', 'Hedef', 'Olculen', 'Sonuc'],
                     loc='center', cellLoc='left', colWidths=[0.26, 0.17, 0.45, 0.10])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.6)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor(GRID)
        if r == 0:
            cell.set_text_props(fontweight='bold', color=INK)
            cell.set_facecolor('#f0efec')
        elif c == 3:
            cell.set_text_props(fontweight='bold', color=INK)
            cell.set_facecolor('#d8efd8' if rows[r - 1][3] == 'GECTI' else '#f6d5d5')
    ax.set_title('Gereksinim dogrulama ozeti (olculmus degerler)', pad=12)
    save(fig, 'summary_dashboard.png')


def fmt_env(env):
    return (f"{env['cpu']} ({env['logical_cpus']} mantiksal cekirdek), {env['platform']}, "
            f"Python {env['python']}, commit `{env['git_commit']}`, {env['timestamp']}")


def write_report(ai, net, loc, fps, rows):
    L = ["# Connect Four Pro - Performans Sonuclari", "",
         "> Bu dosya `benchmarks/visualize_all_results.py` tarafindan `results/*.json` dosyalarindan "
         "otomatik uretilir. Tum sayilar olculmustur; ornek/varsayilan veri yoktur.", ""]

    L += ["## Ortam", ""]
    for name, data in (('AI', ai), ('Ag', net), ('Locust', loc), ('GUI', fps)):
        L.append(f"- **{name}:** " + (fmt_env(data['environment']) if data else 'olculmedi'))
    L += ["", "Sunucu, istemciler (yuk ureticileri) ve PostgreSQL ayni makinede calisti; sunucu Flask-SocketIO "
          "`threading` modunda (Werkzeug). Sonuclar donanima baglidir, farkli makinede yeniden olculmelidir.", ""]

    L += ["## Gereksinim dogrulama", "", "| Gereksinim | Hedef | Olculen | Sonuc | Not |", "|---|---|---|---|---|"]
    L += [f"| {r[0]} | {r[1]} | {r[2]} | **{r[3]}** | {r[4]} |" for r in rows]
    L += ["", "![Ozet](visualization_outputs/summary_dashboard.png)", ""]

    if ai:
        p = ai['parameters']
        L += ["## AI performansi", "",
              f"Yontem: derinlik basina {p['iterations_per_depth']} rastgele pozisyon (erken/orta/gec oyun esit, "
              f"tohum {p['seed']}); tum derinlikler ayni pozisyonlarda olculdu. Acilis kitabi kapali (saf arama).", "",
              "| Derinlik | Ortalama (ms) | Std (ms) | Medyan | p95 (ms) | Maks (ms) | Ort. dugum | Ort. budama | us/dugum |",
              "|---|---|---|---|---|---|---|---|---|"]
        for d in sorted(ai['latency_summary'], key=int):
            s = ai['latency_summary'][d]
            L.append(f"| {d} | {s['mean']:.2f} | {s['stdev']:.2f} | {s['median']:.2f} | {s['p95']:.2f} | "
                     f"{s['max']:.2f} | {s['mean_nodes']:,.0f} | {s['mean_cutoffs']:,.0f} | {s['us_per_node']:.1f} |")
        L += ["", "![AI gecikme](visualization_outputs/ai_latency_vs_depth.png)",
              "![AI karmasiklik](visualization_outputs/ai_computational_complexity.png)", "",
              "### Taktik senaryolar", "",
              "Dogru cevap kumesi 4 yari-hamlelik kesin aramayla (zorla kazanc/kayip) hesaplandi.", ""]
        sdepths = sorted({r['depth'] for r in ai['scenario_results']})
        L += ["| Senaryo | Dogru hamle(ler) | " + " | ".join(f"D{d}" for d in sdepths) + " |",
              "|---|---|" + "---|" * len(sdepths)]
        for name in dict.fromkeys(r['scenario'] for r in ai['scenario_results']):
            rs = {r['depth']: r for r in ai['scenario_results'] if r['scenario'] == name}
            cells = [('OK' if rs[d]['correct'] else f"X ({rs[d]['move']})") for d in sdepths]
            L.append(f"| {name} | {rs[sdepths[0]]['acceptable']} | " + " | ".join(cells) + " |")
        acc = ai['scenario_accuracy_percent']
        L += ["| **Dogruluk** | | " + " | ".join(f"**%{acc[str(d)]:.0f}**" for d in sdepths) + " |", "",
              "![Senaryolar](visualization_outputs/ai_scenarios.png)", ""]
        t = ai['tournament']
        L += ["### Turnuva", "",
              f"Her eslesme {len(t['openings'])} farkli rastgele acilistan (4 yari-hamle), her acilis renkler "
              f"degistirilerek iki kez oynandi. Toplam {t['games']} oyun. Kazanan oyunlarda ilk oyuncunun "
              f"kazanma orani: %{t['first_player_win_rate_percent']:.0f}.", "",
              "| Eslesme | 1. derinlik galibiyet | 2. derinlik galibiyet | Beraberlik |", "|---|---|---|---|"]
        for key, s in t['results'].items():
            a, b = key.split('-')
            L.append(f"| D{a} vs D{b} | {s['d1_wins']} | {s['d2_wins']} | {s['draws']} |")
        L += ["", "![Turnuva](visualization_outputs/tournament_heatmap.png)", ""]

    if net:
        pr = net['protocol']
        L += ["## Ag performansi", "",
              f"Socket.IO tasima katmani: **{pr['transport']}**. Protokol karsilastirmasinda iki uc nokta da "
              "veritabanina dokunmaz; fark yalnizca protokol maliyetidir.", "",
              "| Olcum | n | Ortalama | Medyan | p95 | p99 | Jitter (ms) |", "|---|---|---|---|---|---|---|"]
        for name, s in (('WebSocket latency_ping', pr['websocket_ping']), ('REST GET /health', pr['rest_health'])):
            L.append(f"| {name} | {s['n']} | {s['mean']:.3f} | {s['median']:.3f} | {s['p95']:.3f} | "
                     f"{s['p99']:.3f} | {s['jitter']:.3f} |")
        L += ["", "| Islem | Ortalama (ms) | p95 (ms) | Hata |", "|---|---|---|---|"]
        for k, s in net['operations'].items():
            L.append(f"| {k} | {s['mean']:.2f} | {s['p95']:.2f} | {s['failures']} |")
        L += ["", "![Protokol](visualization_outputs/protocol_comparison.png)",
              "![Islemler](visualization_outputs/operation_latency.png)",
              "![Mesaj boyutu](visualization_outputs/payload_vs_latency.png)", "",
              "### Eszamanlilik", "", "| Istemci | REST istek/sn | REST ort (ms) | REST hata % | WS istek/sn | "
              "WS ort (ms) | WS hata % |", "|---|---|---|---|---|---|---|"]
        for r, w in zip(net['concurrency']['rest_leaderboard'], net['concurrency']['websocket_ping'], strict=True):
            L.append(f"| {r['clients']} | {r['throughput_rps']:.0f} | {r.get('mean', 0):.2f} | "
                     f"{r['error_rate_percent']:.2f} | {w['throughput_rps']:.0f} | {w.get('mean', 0):.2f} | "
                     f"{w['error_rate_percent']:.2f} |")
        L += ["", "![Eszamanlilik](visualization_outputs/concurrency_analysis.png)", "",
              "### Eszamanli oyunlar", "", "Her oda iki WebSocket istemcisi; rastgele yasal hamlelerle tam oyun.", "",
              "| Oyun | Baglanti | Tamamlanan | Hamle RTT ort (ms) | p95 (ms) | p99 (ms) | Hamle/sn |",
              "|---|---|---|---|---|---|---|"]
        for g in net['concurrent_games']:
            L.append(f"| {g['games']} | {g['connections']} | {g['completed']}/{g['games']} | {g.get('mean', 0):.2f} | "
                     f"{g.get('p95', 0):.2f} | {g.get('p99', 0):.2f} | {g['moves_per_second']:.0f} |")
        L += ["", "![Eszamanli oyunlar](visualization_outputs/concurrent_games.png)", ""]

    if loc:
        L += ["## Locust yuk testi", "", "Profiller: Casual %30, Active %50, Power %20 (REST API).", "",
              "| Kullanici | Istek | Hata % | Istek/sn | Medyan (ms) | Ortalama (ms) | p95 (ms) | p99 (ms) |",
              "|---|---|---|---|---|---|---|---|"]
        for t in loc['tests']:
            L.append(f"| {t['users']} | {t['requests']} | {t['error_rate_percent']:.2f} | {t['rps']:.1f} | "
                     f"{t['median_ms']:.0f} | {t['mean_ms']:.0f} | {t['p95_ms']:.0f} | {t['p99_ms']:.0f} |")
        L += ["", "![Locust](visualization_outputs/locust_load.png)", ""]

    if fps:
        L += ["## GUI kare hizi", "", "Gercek ana dongu (60 FPS siniri), ekransiz SDL surucusu; kareler arasi sure.", "",
              "| Durum | Ort. FPS | p99 kare (ms) | En uzun kare (ms) | >33 ms kare |", "|---|---|---|---|---|"]
        for name, label in (('idle', 'Bos'), ('ai_searching', 'AI (D6) ararken')):
            s = fps[name]
            L.append(f"| {label} | {s['fps_mean']:.1f} | {s['p99']:.1f} | {s['max']:.1f} | "
                     f"{s['frames_over_33ms']} / {s['n']} |")
        L.append("")

    with open(os.path.join(bc.BENCH_DIR, 'RESULTS.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    bc.progress("  [OK] RESULTS.md")


def load(name) -> Optional[dict]:
    data = bc.load_json(name)
    bc.progress(f"  {'[OK]' if data else '[--]'} {name}")
    return data


def main():
    bc.progress("Sonuclar okunuyor:")
    ai, net = load('ai_results.json'), load('network_results.json')
    loc, fps = load('locust_results.json'), load('gui_fps_results.json')
    bc.progress("Grafikler:")
    if ai:
        ai_charts(ai)
    if net:
        network_charts(net)
    if loc:
        locust_charts(loc)
    rows = nfr_rows(ai, net, loc, fps)
    if rows:
        summary_dashboard(rows)
    write_report(ai, net, loc, fps, rows)


if __name__ == '__main__':
    main()
