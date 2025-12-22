#!/usr/bin/env python3
# =============================================================================
# TEST RESULTS VISUALIZATION - THESIS QUALITY
# Connect Four Pro - Performance Analysis Visualization
# =============================================================================

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import json
import os
from datetime import datetime

# Matplotlib settings - Thesis quality
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 12
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.dpi'] = 150

# Color palette
COLORS = {
    'primary': '#2E86AB',
    'secondary': '#A23B72',
    'success': '#28A745',
    'warning': '#F18F01',
    'danger': '#C73E1D',
    'info': '#17A2B8',
    'light': '#F8F9FA',
    'dark': '#343A40',
    'p1': '#E63946',  # Red (Player 1)
    'p2': '#F4A261',  # Yellow/Orange (Player 2)
}

# Output directory
OUTPUT_DIR = 'visualization_outputs'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# =============================================================================
# 1. LOAD TEST RESULTS (50, 100, 200 Users)
# =============================================================================

def visualize_load_test_results():
    """Visualize load test results for 50, 100, 200 concurrent users"""
    
    # Test data
    users = [50, 100, 200]
    
    # Metrics
    rps = [47.5, 82.9, 140.5]
    avg_latency = [42.3, 68.5, 142.8]
    p95_latency = [78, 145, 385]
    p99_latency = [125, 285, 720]
    error_rate = [0.0, 0.3, 4.56]
    success_rate = [100, 99.7, 95.44]
    
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle('Load Test Results - 50/100/200 Concurrent Users', fontsize=16, fontweight='bold')
    
    # 1. Throughput (RPS)
    ax1 = axes[0, 0]
    bars1 = ax1.bar(users, rps, color=[COLORS['success'], COLORS['warning'], COLORS['danger']], 
                    edgecolor='white', linewidth=2)
    ax1.set_xlabel('Concurrent Users')
    ax1.set_ylabel('Requests Per Second')
    ax1.set_title('Throughput (RPS)')
    ax1.set_xticks(users)
    for bar, val in zip(bars1, rps):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, 
                f'{val}', ha='center', va='bottom', fontweight='bold')
    
    # 2. Average Latency
    ax2 = axes[0, 1]
    bars2 = ax2.bar(users, avg_latency, color=[COLORS['success'], COLORS['warning'], COLORS['danger']],
                    edgecolor='white', linewidth=2)
    ax2.set_xlabel('Concurrent Users')
    ax2.set_ylabel('Latency (ms)')
    ax2.set_title('Average Latency')
    ax2.set_xticks(users)
    ax2.axhline(y=100, color='red', linestyle='--', alpha=0.7, label='Target (100ms)')
    ax2.legend()
    for bar, val in zip(bars2, avg_latency):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, 
                f'{val}ms', ha='center', va='bottom', fontweight='bold')
    
    # 3. Error Rate
    ax3 = axes[0, 2]
    colors3 = [COLORS['success'] if e < 1 else (COLORS['warning'] if e < 5 else COLORS['danger']) for e in error_rate]
    bars3 = ax3.bar(users, error_rate, color=colors3, edgecolor='white', linewidth=2)
    ax3.set_xlabel('Concurrent Users')
    ax3.set_ylabel('Error Rate (%)')
    ax3.set_title('Error Rate')
    ax3.set_xticks(users)
    ax3.axhline(y=1, color='orange', linestyle='--', alpha=0.7, label='Warning (1%)')
    ax3.axhline(y=5, color='red', linestyle='--', alpha=0.7, label='Critical (5%)')
    ax3.legend()
    for bar, val in zip(bars3, error_rate):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                f'{val}%', ha='center', va='bottom', fontweight='bold')
    
    # 4. Latency Percentiles
    ax4 = axes[1, 0]
    x = np.arange(len(users))
    width = 0.25
    bars4a = ax4.bar(x - width, avg_latency, width, label='Avg', color=COLORS['primary'])
    bars4b = ax4.bar(x, p95_latency, width, label='P95', color=COLORS['warning'])
    bars4c = ax4.bar(x + width, p99_latency, width, label='P99', color=COLORS['danger'])
    ax4.set_xlabel('Concurrent Users')
    ax4.set_ylabel('Latency (ms)')
    ax4.set_title('Latency Percentiles')
    ax4.set_xticks(x)
    ax4.set_xticklabels(users)
    ax4.legend()
    
    # 5. Success Rate Gauge-style
    ax5 = axes[1, 1]
    colors5 = [COLORS['success'] if s >= 99 else (COLORS['warning'] if s >= 95 else COLORS['danger']) for s in success_rate]
    bars5 = ax5.barh(users, success_rate, color=colors5, edgecolor='white', linewidth=2)
    ax5.set_xlabel('Success Rate (%)')
    ax5.set_ylabel('Concurrent Users')
    ax5.set_title('Success Rate')
    ax5.set_xlim(90, 101)
    ax5.axvline(x=99, color='green', linestyle='--', alpha=0.7, label='Target (99%)')
    ax5.legend()
    for bar, val in zip(bars5, success_rate):
        ax5.text(val - 0.5, bar.get_y() + bar.get_height()/2, 
                f'{val}%', ha='right', va='center', fontweight='bold', color='white')
    
    # 6. Trend Line
    ax6 = axes[1, 2]
    ax6.plot(users, avg_latency, 'o-', color=COLORS['primary'], linewidth=2, markersize=10, label='Avg Latency')
    ax6.fill_between(users, avg_latency, alpha=0.3, color=COLORS['primary'])
    ax6.plot(users, p95_latency, 's--', color=COLORS['warning'], linewidth=2, markersize=8, label='P95 Latency')
    ax6.set_xlabel('Concurrent Users')
    ax6.set_ylabel('Latency (ms)')
    ax6.set_title('Latency Scaling Trend')
    ax6.legend()
    ax6.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/load_test_results.png', dpi=300, bbox_inches='tight')
    plt.savefig(f'{OUTPUT_DIR}/load_test_results.pdf', bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/load_test_results.png")
    plt.close()


# =============================================================================
# 2. REAL USER TEST RESULTS
# =============================================================================

def visualize_real_user_test():
    """Visualize real user test results for 8 participants"""
    
    # Usability survey data
    categories = ['Ease of\nUse', 'Visual\nDesign', 'Response\nTime', 
                  'AI Difficulty\nBalance', 'Multiplayer\nExperience', 'Overall\nSatisfaction']
    scores = [4.6, 4.4, 4.8, 4.5, 4.7, 4.6]
    responses = [
        [5, 4, 5, 4, 5, 4, 5, 5],
        [4, 5, 4, 4, 5, 4, 5, 4],
        [5, 5, 4, 5, 5, 5, 5, 5],
        [4, 5, 5, 4, 4, 5, 5, 4],
        [5, 5, 4, 5, 5, 4, 5, 5],
        [5, 4, 5, 4, 5, 5, 5, 4]
    ]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle('Real User Test Results (n=8)', fontsize=16, fontweight='bold')
    
    # 1. Radar Chart - Usability
    ax1 = fig.add_subplot(2, 2, 1, projection='polar')
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    scores_plot = scores + [scores[0]]
    angles += angles[:1]
    
    ax1.plot(angles, scores_plot, 'o-', linewidth=2, color=COLORS['primary'])
    ax1.fill(angles, scores_plot, alpha=0.25, color=COLORS['primary'])
    ax1.set_xticks(angles[:-1])
    ax1.set_xticklabels(categories, size=9)
    ax1.set_ylim(0, 5)
    ax1.set_title('Usability Scores', pad=20)
    
    # 2. Bar Chart - Average Scores
    ax2 = axes[0, 1]
    colors = [COLORS['success'] if s >= 4.5 else COLORS['warning'] for s in scores]
    bars = ax2.barh(categories, scores, color=colors, edgecolor='white', linewidth=2)
    ax2.set_xlim(3.5, 5.1)
    ax2.set_xlabel('Score (1-5)')
    ax2.set_title('Average Scores by Category')
    ax2.axvline(x=4.0, color='gray', linestyle='--', alpha=0.5, label='Good (4.0)')
    ax2.axvline(x=4.5, color='green', linestyle='--', alpha=0.5, label='Excellent (4.5)')
    for bar, val in zip(bars, scores):
        ax2.text(val + 0.05, bar.get_y() + bar.get_height()/2, 
                f'{val:.1f}', va='center', fontweight='bold')
    ax2.legend(loc='lower right')
    
    # 3. AI Game Results
    ax3 = axes[1, 0]
    difficulties = ['Easy\n(Depth 2)', 'Medium\n(Depth 4)', 'Hard\n(Depth 6)']
    player_wins = [10, 7, 2]
    ai_wins = [2, 8, 8]
    
    x = np.arange(len(difficulties))
    width = 0.35
    bars3a = ax3.bar(x - width/2, player_wins, width, label='Player Won', color=COLORS['success'])
    bars3b = ax3.bar(x + width/2, ai_wins, width, label='AI Won', color=COLORS['danger'])
    ax3.set_ylabel('Number of Games')
    ax3.set_title('AI Difficulty Level vs Game Results')
    ax3.set_xticks(x)
    ax3.set_xticklabels(difficulties)
    ax3.legend()
    
    for bars in [bars3a, bars3b]:
        for bar in bars:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2, height + 0.2, 
                    f'{int(height)}', ha='center', va='bottom', fontweight='bold')
    
    # 4. Performance Metrics
    ax4 = axes[1, 1]
    metrics = ['Client FPS', 'Network\nLatency', 'AI Response\n(D6)', 'Memory\nUsage']
    values = [58.4, 23.5, 342.5, 85]
    targets = [30, 100, 500, 200]
    
    x = np.arange(len(metrics))
    width = 0.35
    
    # Normalize for comparison
    normalized_values = [v/t*100 for v, t in zip(values, targets)]
    colors4 = [COLORS['success'] if nv <= 100 else COLORS['warning'] for nv in normalized_values]
    
    bars4 = ax4.bar(x, values, width, color=colors4, edgecolor='white', linewidth=2, label='Measured')
    ax4.bar(x + width, targets, width, color='lightgray', edgecolor='white', linewidth=2, label='Target/Limit')
    
    ax4.set_ylabel('Value')
    ax4.set_title('Performance Metrics vs Targets')
    ax4.set_xticks(x + width/2)
    ax4.set_xticklabels(metrics)
    ax4.legend()
    
    # Annotations
    units = ['fps', 'ms', 'ms', 'MB']
    for i, (bar, val, unit) in enumerate(zip(bars4, values, units)):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, 
                f'{val}{unit}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/real_user_test_results.png', dpi=300, bbox_inches='tight')
    plt.savefig(f'{OUTPUT_DIR}/real_user_test_results.pdf', bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/real_user_test_results.png")
    plt.close()


# =============================================================================
# 3. AI PERFORMANCE ANALYSIS
# =============================================================================

def visualize_ai_performance():
    """Visualize AI performance test results"""
    
    # Test data
    depths = [1, 2, 3, 4, 5, 6]
    latency_avg = [0.6, 2.3, 7.2, 19.2, 92.4, 355.58]
    latency_std = [0.15, 0.42, 1.83, 4.21, 24.67, 128.45]
    nodes_evaluated = [7, 32, 198, 547, 2847, 11428]
    cutoff_rate = [0, 45, 72, 78, 85, 90]  # Alpha-beta pruning efficiency
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('AI Performance Analysis - Minimax + Alpha-Beta Pruning', fontsize=16, fontweight='bold')
    
    # 1. Latency vs Depth (with error bars)
    ax1 = axes[0, 0]
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(depths)))
    bars1 = ax1.bar(depths, latency_avg, yerr=latency_std, capsize=5, 
                    color=colors, edgecolor='white', linewidth=2)
    ax1.set_xlabel('Search Depth')
    ax1.set_ylabel('Response Time (ms)')
    ax1.set_title('AI Response Time vs Search Depth')
    ax1.axhline(y=500, color='red', linestyle='--', alpha=0.7, label='Target Limit (500ms)')
    ax1.legend()
    
    for bar, val in zip(bars1, latency_avg):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + latency_std[depths.index(bar.get_x() + bar.get_width()/2)] + 10, 
                f'{val:.1f}ms', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # 2. Nodes Evaluated (Log Scale)
    ax2 = axes[0, 1]
    ax2.bar(depths, nodes_evaluated, color=COLORS['primary'], edgecolor='white', linewidth=2)
    ax2.set_xlabel('Search Depth')
    ax2.set_ylabel('Nodes Evaluated (log scale)')
    ax2.set_title('Computational Complexity vs Depth')
    ax2.set_yscale('log')
    
    # Theoretical worst case line
    theoretical_worst = [7**d for d in depths]
    ax2.plot(depths, theoretical_worst, 'r--', linewidth=2, label=f'Theoretical O(7^d)')
    ax2.legend()
    
    for i, (d, n) in enumerate(zip(depths, nodes_evaluated)):
        ax2.text(d, n * 1.5, f'{n:,}', ha='center', va='bottom', fontsize=9)
    
    # 3. Alpha-Beta Pruning Efficiency
    ax3 = axes[1, 0]
    bars3 = ax3.bar(depths, cutoff_rate, color=COLORS['success'], edgecolor='white', linewidth=2)
    ax3.set_xlabel('Search Depth')
    ax3.set_ylabel('Pruning Efficiency (%)')
    ax3.set_title('Alpha-Beta Pruning Node Reduction')
    ax3.set_ylim(0, 100)
    
    for bar, val in zip(bars3, cutoff_rate):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, 
                f'{val}%', ha='center', va='bottom', fontweight='bold')
    
    # 4. Latency vs Nodes (Scatter with trend)
    ax4 = axes[1, 1]
    scatter = ax4.scatter(nodes_evaluated, latency_avg, c=depths, cmap='viridis', 
                         s=200, edgecolors='white', linewidths=2)
    
    # Trend line
    z = np.polyfit(nodes_evaluated, latency_avg, 1)
    p = np.poly1d(z)
    x_line = np.linspace(0, max(nodes_evaluated) * 1.1, 100)
    ax4.plot(x_line, p(x_line), 'r--', alpha=0.7, label=f'Linear Trend')
    
    ax4.set_xlabel('Nodes Evaluated')
    ax4.set_ylabel('Response Time (ms)')
    ax4.set_title('Computational Complexity Analysis')
    ax4.legend()
    
    cbar = plt.colorbar(scatter, ax=ax4)
    cbar.set_label('Search Depth')
    
    # Depth labels
    for i, (x, y, d) in enumerate(zip(nodes_evaluated, latency_avg, depths)):
        ax4.annotate(f'D{d}', (x, y), textcoords="offset points", xytext=(10, 5), fontsize=10)
    
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/ai_performance_analysis.png', dpi=300, bbox_inches='tight')
    plt.savefig(f'{OUTPUT_DIR}/ai_performance_analysis.pdf', bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/ai_performance_analysis.png")
    plt.close()


# =============================================================================
# 4. NETWORK PROTOCOL COMPARISON
# =============================================================================

def visualize_network_comparison():
    """Compare WebSocket vs REST API performance"""
    
    # Test data
    metrics = ['Mean', 'Median (P50)', 'P95', 'P99']
    websocket = [1.38, 1.22, 1.75, 5.78]
    rest_api = [2.04, 1.85, 2.45, 5.21]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('WebSocket vs REST API Performance Comparison', fontsize=16, fontweight='bold')
    
    # 1. Grouped Bar Chart
    ax1 = axes[0]
    x = np.arange(len(metrics))
    width = 0.35
    
    bars1a = ax1.bar(x - width/2, websocket, width, label='WebSocket', color=COLORS['primary'])
    bars1b = ax1.bar(x + width/2, rest_api, width, label='REST API', color=COLORS['secondary'])
    
    ax1.set_xlabel('Metric')
    ax1.set_ylabel('Latency (ms)')
    ax1.set_title('Latency Comparison')
    ax1.set_xticks(x)
    ax1.set_xticklabels(metrics)
    ax1.legend()
    
    # 2. Improvement Percentage
    ax2 = axes[1]
    improvement = [(r - w) / r * 100 for w, r in zip(websocket, rest_api)]
    colors2 = [COLORS['success'] if i > 0 else COLORS['danger'] for i in improvement]
    bars2 = ax2.bar(metrics, improvement, color=colors2, edgecolor='white', linewidth=2)
    ax2.set_xlabel('Metric')
    ax2.set_ylabel('Improvement (%)')
    ax2.set_title('WebSocket Improvement over REST')
    ax2.axhline(y=0, color='black', linewidth=0.5)
    
    for bar, val in zip(bars2, improvement):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
                f'{val:.1f}%', ha='center', va='bottom', fontweight='bold')
    
    # 3. Box Plot Style
    ax3 = axes[2]
    data = [websocket, rest_api]
    bp = ax3.boxplot(data, labels=['WebSocket', 'REST API'], patch_artist=True)
    bp['boxes'][0].set_facecolor(COLORS['primary'])
    bp['boxes'][1].set_facecolor(COLORS['secondary'])
    ax3.set_ylabel('Latency (ms)')
    ax3.set_title('Latency Distribution')
    
    # Add mean markers
    means = [np.mean(websocket), np.mean(rest_api)]
    ax3.scatter([1, 2], means, color='red', marker='D', s=100, zorder=5, label='Mean')
    ax3.legend()
    
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/network_comparison.png', dpi=300, bbox_inches='tight')
    plt.savefig(f'{OUTPUT_DIR}/network_comparison.pdf', bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/network_comparison.png")
    plt.close()


# =============================================================================
# 5. TOURNAMENT HEATMAP
# =============================================================================

def visualize_tournament_heatmap():
    """AI vs AI tournament results heatmap"""
    
    # Win rates (row AI vs column AI)
    depths = ['D2', 'D3', 'D4', 'D5', 'D6']
    win_rates = np.array([
        [50, 35, 30, 25, 0],    # D2 vs others
        [65, 50, 40, 35, 30],   # D3 vs others
        [70, 60, 50, 45, 25],   # D4 vs others
        [75, 65, 55, 50, 40],   # D5 vs others
        [100, 70, 75, 60, 50],  # D6 vs others
    ])
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    im = ax.imshow(win_rates, cmap='RdYlGn', vmin=0, vmax=100)
    
    # Axis labels
    ax.set_xticks(np.arange(len(depths)))
    ax.set_yticks(np.arange(len(depths)))
    ax.set_xticklabels(depths)
    ax.set_yticklabels(depths)
    ax.set_xlabel('Opponent Depth')
    ax.set_ylabel('AI Depth')
    ax.set_title('AI Tournament Win Rates (%)\n(Row AI vs Column AI)', fontsize=14, fontweight='bold')
    
    # Text annotations
    for i in range(len(depths)):
        for j in range(len(depths)):
            text_color = 'white' if win_rates[i, j] > 60 or win_rates[i, j] < 40 else 'black'
            ax.text(j, i, f'{win_rates[i, j]}%', ha='center', va='center', 
                   color=text_color, fontsize=12, fontweight='bold')
    
    # Colorbar
    cbar = ax.figure.colorbar(im, ax=ax)
    cbar.ax.set_ylabel('Win Rate (%)', rotation=-90, va="bottom")
    
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/tournament_heatmap.png', dpi=300, bbox_inches='tight')
    plt.savefig(f'{OUTPUT_DIR}/tournament_heatmap.pdf', bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/tournament_heatmap.png")
    plt.close()


# =============================================================================
# 6. SCALABILITY ANALYSIS
# =============================================================================

def visualize_scalability():
    """System scalability analysis"""
    
    # Concurrency test data
    connections = [1, 5, 10, 20, 50]
    throughput = [502, 489, 623, 658, 827]
    latency = [1.99, 9.73, 14.82, 27.94, 54.17]
    error_rate = [0, 0, 0, 0, 0]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('System Scalability Analysis', fontsize=16, fontweight='bold')
    
    # 1. Throughput Scaling
    ax1 = axes[0]
    ax1.plot(connections, throughput, 'o-', color=COLORS['primary'], linewidth=2, markersize=10)
    ax1.fill_between(connections, throughput, alpha=0.3, color=COLORS['primary'])
    ax1.set_xlabel('Concurrent Connections')
    ax1.set_ylabel('Throughput (RPS)')
    ax1.set_title('Throughput Scaling')
    ax1.axhline(y=500, color='green', linestyle='--', alpha=0.7, label='Target (500 RPS)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Latency Scaling
    ax2 = axes[1]
    ax2.plot(connections, latency, 's-', color=COLORS['warning'], linewidth=2, markersize=10)
    ax2.fill_between(connections, latency, alpha=0.3, color=COLORS['warning'])
    ax2.set_xlabel('Concurrent Connections')
    ax2.set_ylabel('Average Latency (ms)')
    ax2.set_title('Latency vs Concurrency')
    ax2.axhline(y=100, color='red', linestyle='--', alpha=0.7, label='Target Limit (100ms)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. System Stability
    ax3 = axes[2]
    success_rate = [100 - e for e in error_rate]
    bars3 = ax3.bar(connections, success_rate, color=COLORS['success'], edgecolor='white', linewidth=2)
    ax3.set_xlabel('Concurrent Connections')
    ax3.set_ylabel('Success Rate (%)')
    ax3.set_title('System Stability')
    ax3.set_ylim(95, 101)
    ax3.axhline(y=99, color='orange', linestyle='--', alpha=0.7, label='Target (99%)')
    ax3.legend()
    
    for bar in bars3:
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() - 1, 
                '100%', ha='center', va='top', fontweight='bold', color='white')
    
    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/scalability_analysis.png', dpi=300, bbox_inches='tight')
    plt.savefig(f'{OUTPUT_DIR}/scalability_analysis.pdf', bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/scalability_analysis.png")
    plt.close()


# =============================================================================
# 7. SUMMARY DASHBOARD
# =============================================================================

def visualize_summary_dashboard():
    """Display all results in a single dashboard"""
    
    fig = plt.figure(figsize=(16, 12))
    fig.suptitle('Connect Four Pro - Performance Summary Dashboard', fontsize=18, fontweight='bold')
    
    # Grid layout
    gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
    
    # 1. AI Response Time (top-left)
    ax1 = fig.add_subplot(gs[0, 0:2])
    depths = [1, 2, 3, 4, 5, 6]
    latency = [0.6, 2.3, 7.2, 19.2, 92.4, 355.58]
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(depths)))
    ax1.bar(depths, latency, color=colors)
    ax1.set_xlabel('Depth')
    ax1.set_ylabel('Response Time (ms)')
    ax1.set_title('AI Response Time')
    ax1.axhline(y=500, color='red', linestyle='--', alpha=0.7)
    
    # 2. Network Comparison (top-right)
    ax2 = fig.add_subplot(gs[0, 2:4])
    protocols = ['WebSocket', 'REST API']
    latencies = [1.38, 2.04]
    bars2 = ax2.bar(protocols, latencies, color=[COLORS['primary'], COLORS['secondary']])
    ax2.set_ylabel('Mean Latency (ms)')
    ax2.set_title('Protocol Comparison')
    for bar, val in zip(bars2, latencies):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05, 
                f'{val}ms', ha='center', va='bottom', fontweight='bold')
    
    # 3. Load Test Results (middle-left)
    ax3 = fig.add_subplot(gs[1, 0:2])
    users = [50, 100, 200]
    error_rates = [0, 0.3, 4.56]
    colors3 = [COLORS['success'], COLORS['warning'], COLORS['danger']]
    ax3.bar(users, error_rates, color=colors3, width=30)
    ax3.set_xlabel('Concurrent Users')
    ax3.set_ylabel('Error Rate (%)')
    ax3.set_title('Load Test Error Rates')
    ax3.set_xticks(users)
    
    # 4. User Satisfaction (middle-right)
    ax4 = fig.add_subplot(gs[1, 2:4])
    categories = ['Ease', 'Design', 'Response', 'AI', 'Multi', 'Overall']
    scores = [4.6, 4.4, 4.8, 4.5, 4.7, 4.6]
    ax4.barh(categories, scores, color=COLORS['success'])
    ax4.set_xlim(3.5, 5)
    ax4.set_xlabel('Score (1-5)')
    ax4.set_title('User Satisfaction')
    ax4.axvline(x=4.5, color='green', linestyle='--', alpha=0.5)
    
    # 5. Key Metrics (bottom)
    ax5 = fig.add_subplot(gs[2, :])
    ax5.axis('off')
    
    # Key metrics table
    metrics_data = [
        ['Metric', 'Value', 'Target', 'Status'],
        ['AI Response (D6)', '355.58 ms', '< 500 ms', '✅ PASS'],
        ['WebSocket Latency', '1.38 ms', '< 5 ms', '✅ PASS'],
        ['Max Concurrent', '50 users', '≥ 50', '✅ PASS'],
        ['Throughput', '827 RPS', '> 500 RPS', '✅ PASS'],
        ['User Satisfaction', '4.6 / 5.0', '> 4.0', '✅ PASS'],
    ]
    
    table = ax5.table(cellText=metrics_data[1:], colLabels=metrics_data[0],
                     loc='center', cellLoc='center',
                     colColours=[COLORS['light']]*4,
                     cellColours=[[COLORS['light']]*4 for _ in range(5)])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    
    # Style the table
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(fontweight='bold')
            cell.set_facecolor(COLORS['primary'])
            cell.set_text_props(color='white')
        if col == 3 and row > 0:
            cell.set_facecolor('#d4edda')  # Light green for PASS
    
    plt.savefig(f'{OUTPUT_DIR}/summary_dashboard.png', dpi=300, bbox_inches='tight')
    plt.savefig(f'{OUTPUT_DIR}/summary_dashboard.pdf', bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/summary_dashboard.png")
    plt.close()


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Generate all visualizations"""
    print("="*60)
    print("CONNECT FOUR PRO - TEST RESULTS VISUALIZATION")
    print("="*60)
    print(f"Output directory: {OUTPUT_DIR}/")
    print("-"*60)
    
    # Run all visualizations
    visualize_load_test_results()
    visualize_real_user_test()
    visualize_ai_performance()
    visualize_network_comparison()
    visualize_tournament_heatmap()
    visualize_scalability()
    visualize_summary_dashboard()
    
    print("-"*60)
    print(f"✅ All visualizations completed!")
    print(f"📁 Outputs: {OUTPUT_DIR}/")
    print("="*60)
    
    # File listing
    print("\nGenerated files:")
    for f in os.listdir(OUTPUT_DIR):
        size = os.path.getsize(f'{OUTPUT_DIR}/{f}') / 1024
        print(f"  - {f} ({size:.1f} KB)")


if __name__ == "__main__":
    main()
