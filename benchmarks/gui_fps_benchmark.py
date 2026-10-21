#!/usr/bin/env python3
"""
GUI kare hizi olcumu (NFR-05: >= 30 FPS).

Pygame istemcisi ekransiz (SDL dummy) ve GERCEK ana donguyle (tick + 60 FPS
siniri) calistirilir; ardisik kareler arasindaki sure olculur. Iki durum:
  * bos: oyun ekrani, AI calismiyor
  * AI aramada: Zor (D8) AI ayri thread'de arama yaparken. Bir kare araligi,
    o aralikta AI'nin dugum sayaci degistiyse "aramada" sayilir.

Not: Dummy surucude ekrana cizim (GPU/pencere yoneticisi) maliyeti yoktur; olcum
dongunun CPU maliyetini ve AI thread'iyle GIL cekismesini gosterir.
"""

import os
import time

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('LOG_LEVEL', 'WARNING')

import bench_common as bc  # noqa: E402
import gui_app  # noqa: E402

IDLE_SECONDS = 4.0
PLAY_SECONDS = 20.0
HUMAN_COLS = (3, 2, 4, 1, 5, 0, 6)


def run_loop(gui, seconds, play=False):
    """Gercek ana dongu; (kare_araligi_ms, ai_aramada) listesi dondurur."""
    intervals = []
    last_t = time.perf_counter()
    last_marker = None
    end = last_t + seconds
    while time.perf_counter() < end:
        if play:
            if gui.game.game_over:
                gui.start_ai_game(8)
            elif not gui.ai_thinking and gui.can_human_move():
                gui.handle_click(next(c for c in HUMAN_COLS if gui.game.is_valid_location(c)))
        gui.tick()
        gui.clock.tick(gui_app.FPS)
        now = time.perf_counter()
        ai = gui.ai
        marker = (id(ai), ai.nodes_evaluated) if ai else None
        searching = gui.ai_thinking and marker is not None and marker != last_marker
        intervals.append(((now - last_t) * 1000, searching))
        last_t, last_marker = now, marker
    return intervals


def describe(intervals):
    s = bc.summarize(intervals)
    if intervals:
        s['fps_mean'] = 1000 / s['mean']
        s['fps_worst_frame'] = 1000 / s['max']
        s['frames_over_33ms'] = sum(1 for x in intervals if x > 1000 / 30)
    return s


def main():
    gui = gui_app.ConnectFourGUI(server_url='http://127.0.0.1:1')
    gui.guest_login()
    gui.start_ai_game(8)

    idle = [ms for ms, _ in run_loop(gui, IDLE_SECONDS)]
    played = run_loop(gui, PLAY_SECONDS, play=True)
    searching = [ms for ms, busy in played if busy]
    gui.invalidate_ai_session()

    result = {'suite': 'gui_fps', 'environment': bc.environment_info(),
              'parameters': {'ai_depth': 8, 'fps_cap': gui_app.FPS, 'video_driver': os.environ['SDL_VIDEODRIVER']},
              'idle': describe(idle), 'ai_searching': describe(searching)}
    for name in ('idle', 'ai_searching'):
        s = result[name]
        bc.progress(f"  {name:<13} {s['fps_mean']:.1f} FPS ort | en uzun kare {s['max']:.1f} ms "
                    f"({s['fps_worst_frame']:.0f} FPS) | >33 ms kare: {s['frames_over_33ms']} / {s['n']}")
    path = bc.save_json('gui_fps_results.json', bc.rounded(result))
    bc.progress(f"Sonuc: {path}")


if __name__ == '__main__':
    main()
