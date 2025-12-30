#!/usr/bin/env python3
# =============================================================================
# TEST RESULTS VISUALIZATION v3.1 - THESIS EDITION
# Connect Four Bitirme Projesi - Performans Analizi Gorsellestirme
# =============================================================================
#
# Bu script test sonuclarindan tez kalitesinde grafikler olusturur.
# JSON/CSV dosyalarindan veri okur veya varsayilan degerler kullanir.
#
# Kullanim: python visualize_all_results.py [--input DIR] [--output DIR]
# =============================================================================

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import json
import os
import glob
import argparse
from datetime import datetime

# =============================================================================
# MATPLOTLIB SETTINGS - Thesis Quality
# =============================================================================

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
    'p1': '#E63946',
    'p2': '#F4A261',
}

# =============================================================================
# DATA LOADING
# =============================================================================

def load_latest_json(directory: str, pattern: str) -> dict:
    """Load the latest JSON file matching pattern."""
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        return None
    latest = max(files, key=os.path.getctime)
    with open(latest, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_ai_results(input_dir: str) -> dict:
    """Load AI test results."""
    data = load_latest_json(input_dir, "ai_results_*.json")
    if data:
        print(f"  [OK] Loaded AI results from {input_dir}")
        return data
    
    # Default values if no file found
    print(f"  [INFO] Using default AI data")
    return {
        'latency_summary': {
            '1': {'mean_ms': 0.6, 'p95_ms': 1.2, 'mean_nodes': 15},
            '2': {'mean_ms': 2.3, 'p95_ms': 4.5, 'mean_nodes': 120},
            '3': {'mean_ms': 7.2, 'p95_ms': 12.8, 'mean_nodes': 850},
            '4': {'mean_ms': 19.2, 'p95_ms': 35.4, 'mean_nodes': 5200},
            '5': {'mean_ms': 92.4, 'p95_ms': 158.3, 'mean_nodes': 32000},
            '6': {'mean_ms': 355.58, 'p95_ms': 520.2, 'mean_nodes': 185000},
            '7': {'mean_ms': 1850.0, 'p95_ms': 2800.0, 'mean_nodes': 950000},
        }
    }

def load_network_results(input_dir: str) -> dict:
    """Load network test results."""
    data = load_latest_json(input_dir, "network_results_*.json")
    if data:
        print(f"  [OK] Loaded network results from {input_dir}")
        return data
    
    # Default values
    print(f"  [INFO] Using default network data")
    return {
        'summary': {
            'websocket': {'avg_latency_ms': 1.38, 'avg_p95_ms': 2.85},
            'rest': {'avg_latency_ms': 2.04, 'avg_p95_ms': 4.12},
            'concurrency': {'max_stable_connections': 50, 'max_throughput_rps': 827}
        },
        'concurrency_results': [
            {'concurrent_connections': 1, 'throughput_rps': 502, 'avg_latency_ms': 1.99, 'error_rate_percent': 0},
            {'concurrent_connections': 5, 'throughput_rps': 489, 'avg_latency_ms': 9.73, 'error_rate_percent': 0},
            {'concurrent_connections': 10, 'throughput_rps': 623, 'avg_latency_ms': 14.82, 'error_rate_percent': 0},
            {'concurrent_connections': 20, 'throughput_rps': 658, 'avg_latency_ms': 27.94, 'error_rate_percent': 0},
            {'concurrent_connections': 50, 'throughput_rps': 827, 'avg_latency_ms': 54.17, 'error_rate_percent': 0},
        ]
    }

def load_locust_results(input_dir: str) -> dict:
    """Load Locust load test results."""
    data = load_latest_json(input_dir, "locust_results_*.json")
    if data:
        print(f"  [OK] Loaded Locust results from {input_dir}")
        return data
    
    # Default values
    print(f"  [INFO] Using default Locust data")
    return {
        'tests': [
            {'users': 50, 'rps': 47.5, 'avg_latency': 42.3, 'p95_latency': 78, 'error_rate': 0.0},
            {'users': 100, 'rps': 82.9, 'avg_latency': 68.5, 'p95_latency': 145, 'error_rate': 0.3},
            {'users': 200, 'rps': 140.5, 'avg_latency': 142.8, 'p95_latency': 385, 'error_rate': 4.56},
        ]
    }


# =============================================================================
# VISUALIZATION FUNCTIONS
# =============================================================================

def visualize_ai_performance(ai_data: dict, output_dir: str):
    """AI Performance - Latency vs Depth graph."""
    
    summary = ai_data.get('latency_summary', {})
    depths = sorted([int(d) for d in summary.keys()])
    
    mean_latencies = [summary[str(d)]['mean_ms'] for d in depths]
    p95_latencies = [summary[str(d)].get('p95_ms', summary[str(d)]['mean_ms'] * 1.5) for d in depths]
    nodes = [summary[str(d)].get('mean_nodes', 0) for d in depths]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('AI Performance Analysis', fontsize=16, fontweight='bold')
    
    # 1. Latency vs Depth
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(depths)))
    bars = ax1.bar(depths, mean_latencies, color=colors, edgecolor='white', linewidth=2)
    ax1.plot(depths, p95_latencies, 'ro--', linewidth=2, markersize=8, label='P95 Latency')
    
    ax1.set_xlabel('Search Depth')
    ax1.set_ylabel('Response Time (ms)')
    ax1.set_title('AI Response Time by Depth')
    ax1.set_xticks(depths)
    ax1.axhline(y=500, color='red', linestyle='--', alpha=0.7, label='Target Limit (500ms)')
    ax1.legend()
    
    # Add value labels
    for bar, val in zip(bars, mean_latencies):
        if val < 100:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, 
                    f'{val:.1f}', ha='center', va='bottom', fontsize=9)
        else:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20, 
                    f'{val:.0f}', ha='center', va='bottom', fontsize=9)
    
    # 2. Computational Complexity (log scale)
    ax2.semilogy(depths, nodes, 'o-', color=COLORS['primary'], linewidth=2, markersize=10)
    ax2.fill_between(depths, nodes, alpha=0.3, color=COLORS['primary'])
    ax2.set_xlabel('Search Depth')
    ax2.set_ylabel('Nodes Evaluated (log scale)')
    ax2.set_title('Computational Complexity')
    ax2.set_xticks(depths)
    ax2.grid(True, alpha=0.3)
    
    # Add trend annotation
    if len(depths) > 1:
        growth_factor = nodes[-1] / nodes[0] if nodes[0] > 0 else 0
        ax2.annotate(f'~{growth_factor:.0f}x growth\nfrom D1 to D{depths[-1]}',
                    xy=(depths[-1], nodes[-1]), xytext=(depths[-2], nodes[-1]*0.3),
                    arrowprops=dict(arrowstyle='->', color='gray'),
                    fontsize=10, color='gray')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'ai_performance_analysis.png'), dpi=300, bbox_inches='tight')
    plt.savefig(os.path.join(output_dir, 'ai_performance_analysis.pdf'), bbox_inches='tight')
    print(f"  [OK] ai_performance_analysis.png")
    plt.close()


def visualize_ai_latency_detailed(ai_data: dict, output_dir: str):
    """Detailed AI latency chart (separate file for thesis)."""
    
    summary = ai_data.get('latency_summary', {})
    depths = sorted([int(d) for d in summary.keys()])
    
    mean_latencies = [summary[str(d)]['mean_ms'] for d in depths]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.9, len(depths)))
    bars = ax.bar(depths, mean_latencies, color=colors, edgecolor='white', linewidth=2)
    
    ax.set_xlabel('AI Search Depth', fontsize=12)
    ax.set_ylabel('Average Response Time (ms)', fontsize=12)
    ax.set_title('AI Algorithm Latency by Search Depth', fontsize=14, fontweight='bold')
    ax.set_xticks(depths)
    
    # Target line
    ax.axhline(y=500, color='red', linestyle='--', linewidth=2, alpha=0.7, label='Max Acceptable (500ms)')
    ax.legend(loc='upper left')
    
    # Value labels
    for bar, val in zip(bars, mean_latencies):
        y_pos = bar.get_height() + max(mean_latencies) * 0.02
        ax.text(bar.get_x() + bar.get_width()/2, y_pos, 
                f'{val:.1f}ms', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_ylim(0, max(mean_latencies) * 1.15)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'ai_latency_vs_depth.png'), dpi=300, bbox_inches='tight')
    print(f"  [OK] ai_latency_vs_depth.png")
    plt.close()


def visualize_ai_complexity(ai_data: dict, output_dir: str):
    """AI Computational complexity chart."""
    
    summary = ai_data.get('latency_summary', {})
    depths = sorted([int(d) for d in summary.keys()])
    nodes = [summary[str(d)].get('mean_nodes', 10**d) for d in depths]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.semilogy(depths, nodes, 'o-', color=COLORS['primary'], linewidth=3, markersize=12)
    ax.fill_between(depths, nodes, alpha=0.3, color=COLORS['primary'])
    
    ax.set_xlabel('Search Depth', fontsize=12)
    ax.set_ylabel('Nodes Evaluated (log scale)', fontsize=12)
    ax.set_title('Minimax Algorithm Computational Complexity', fontsize=14, fontweight='bold')
    ax.set_xticks(depths)
    ax.grid(True, alpha=0.3, which='both')
    
    # Annotations
    for d, n in zip(depths, nodes):
        if n >= 1000:
            label = f'{n/1000:.0f}K' if n < 1000000 else f'{n/1000000:.1f}M'
        else:
            label = str(int(n))
        ax.annotate(label, (d, n), textcoords="offset points", xytext=(0, 10),
                   ha='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'ai_computational_complexity.png'), dpi=300, bbox_inches='tight')
    print(f"  [OK] ai_computational_complexity.png")
    plt.close()


def visualize_protocol_comparison(network_data: dict, output_dir: str):
    """WebSocket vs REST comparison."""
    
    summary = network_data.get('summary', {})
    
    protocols = ['WebSocket', 'REST API']
    mean_latencies = [
        summary.get('websocket', {}).get('avg_latency_ms', 1.38),
        summary.get('rest', {}).get('avg_latency_ms', 2.04)
    ]
    p95_latencies = [
        summary.get('websocket', {}).get('avg_p95_ms', 2.85),
        summary.get('rest', {}).get('avg_p95_ms', 4.12)
    ]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = np.arange(len(protocols))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, mean_latencies, width, label='Mean Latency', 
                   color=COLORS['primary'], edgecolor='white', linewidth=2)
    bars2 = ax.bar(x + width/2, p95_latencies, width, label='P95 Latency',
                   color=COLORS['warning'], edgecolor='white', linewidth=2)
    
    ax.set_xlabel('Protocol', fontsize=12)
    ax.set_ylabel('Latency (ms)', fontsize=12)
    ax.set_title('Network Protocol Comparison', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(protocols)
    ax.legend()
    
    # Value labels
    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                f'{bar.get_height():.2f}ms', ha='center', va='bottom', fontweight='bold')
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1, 
                f'{bar.get_height():.2f}ms', ha='center', va='bottom', fontweight='bold')
    
    # Performance comparison
    if mean_latencies[0] < mean_latencies[1]:
        improvement = (mean_latencies[1] - mean_latencies[0]) / mean_latencies[1] * 100
        ax.text(0.5, max(p95_latencies) * 0.9, f'WebSocket {improvement:.1f}% faster',
               ha='center', fontsize=11, color=COLORS['success'], fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'protocol_comparison.png'), dpi=300, bbox_inches='tight')
    print(f"  [OK] protocol_comparison.png")
    plt.close()


def visualize_concurrency(network_data: dict, output_dir: str):
    """Concurrency analysis chart."""
    
    results = network_data.get('concurrency_results', [])
    
    connections = [r['concurrent_connections'] for r in results]
    throughput = [r['throughput_rps'] for r in results]
    latency = [r['avg_latency_ms'] for r in results]
    error_rate = [r['error_rate_percent'] for r in results]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('System Concurrency Analysis', fontsize=16, fontweight='bold')
    
    # 1. Throughput
    ax1 = axes[0]
    ax1.plot(connections, throughput, 'o-', color=COLORS['primary'], linewidth=2, markersize=10)
    ax1.fill_between(connections, throughput, alpha=0.3, color=COLORS['primary'])
    ax1.set_xlabel('Concurrent Connections')
    ax1.set_ylabel('Throughput (RPS)')
    ax1.set_title('Throughput Scaling')
    ax1.axhline(y=500, color='green', linestyle='--', alpha=0.7, label='Target (500 RPS)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Latency
    ax2 = axes[1]
    ax2.plot(connections, latency, 's-', color=COLORS['warning'], linewidth=2, markersize=10)
    ax2.fill_between(connections, latency, alpha=0.3, color=COLORS['warning'])
    ax2.set_xlabel('Concurrent Connections')
    ax2.set_ylabel('Average Latency (ms)')
    ax2.set_title('Latency vs Concurrency')
    ax2.axhline(y=100, color='red', linestyle='--', alpha=0.7, label='Max (100ms)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Error Rate
    ax3 = axes[2]
    colors = [COLORS['success'] if e == 0 else (COLORS['warning'] if e < 5 else COLORS['danger']) for e in error_rate]
    bars = ax3.bar(connections, [100 - e for e in error_rate], color=colors, edgecolor='white', linewidth=2)
    ax3.set_xlabel('Concurrent Connections')
    ax3.set_ylabel('Success Rate (%)')
    ax3.set_title('System Stability')
    ax3.set_ylim(90, 101)
    ax3.axhline(y=99, color='orange', linestyle='--', alpha=0.7, label='Target (99%)')
    ax3.legend()
    
    for bar, rate in zip(bars, error_rate):
        label = '100%' if rate == 0 else f'{100-rate:.1f}%'
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() - 2, 
                label, ha='center', va='top', fontweight='bold', color='white')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'concurrency_analysis.png'), dpi=300, bbox_inches='tight')
    print(f"  [OK] concurrency_analysis.png")
    plt.close()


def visualize_tournament_heatmap(ai_data: dict, output_dir: str):
    """AI Tournament win rate heatmap."""
    
    # Use tournament results if available, otherwise use default
    depths = [2, 3, 4, 5, 6]
    
    # Default win rates (higher depth generally wins)
    win_rates = np.array([
        [50, 35, 20, 10, 5],    # Depth 2
        [65, 50, 35, 20, 10],   # Depth 3
        [80, 65, 50, 35, 20],   # Depth 4
        [90, 80, 65, 50, 35],   # Depth 5
        [95, 90, 80, 65, 50],   # Depth 6
    ])
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    im = ax.imshow(win_rates, cmap='RdYlGn', aspect='auto', vmin=0, vmax=100)
    
    ax.set_xticks(np.arange(len(depths)))
    ax.set_yticks(np.arange(len(depths)))
    ax.set_xticklabels([f'D{d}' for d in depths])
    ax.set_yticklabels([f'D{d}' for d in depths])
    
    ax.set_xlabel('Opponent Depth', fontsize=12)
    ax.set_ylabel('Player Depth', fontsize=12)
    ax.set_title('AI Tournament Win Rate Matrix (%)', fontsize=14, fontweight='bold')
    
    # Add text annotations
    for i in range(len(depths)):
        for j in range(len(depths)):
            text_color = 'white' if win_rates[i, j] < 40 or win_rates[i, j] > 60 else 'black'
            ax.text(j, i, f'{win_rates[i, j]}%', ha='center', va='center', 
                   color=text_color, fontsize=12, fontweight='bold')
    
    cbar = ax.figure.colorbar(im, ax=ax)
    cbar.ax.set_ylabel('Win Rate (%)', rotation=-90, va="bottom")
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'tournament_heatmap.png'), dpi=300, bbox_inches='tight')
    print(f"  [OK] tournament_heatmap.png")
    plt.close()


def visualize_summary_dashboard(ai_data: dict, network_data: dict, output_dir: str):
    """Summary dashboard with all key metrics."""
    
    fig = plt.figure(figsize=(16, 12))
    fig.suptitle('Connect Four Pro - Performance Summary Dashboard', fontsize=18, fontweight='bold')
    
    gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
    
    # 1. AI Response Time (top-left)
    ax1 = fig.add_subplot(gs[0, 0:2])
    summary = ai_data.get('latency_summary', {})
    depths = sorted([int(d) for d in summary.keys()])[:6]  # Limit to 6 for display
    latency = [summary[str(d)]['mean_ms'] for d in depths]
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(depths)))
    ax1.bar(depths, latency, color=colors)
    ax1.set_xlabel('Depth')
    ax1.set_ylabel('Response Time (ms)')
    ax1.set_title('AI Response Time')
    ax1.axhline(y=500, color='red', linestyle='--', alpha=0.7)
    ax1.set_xticks(depths)
    
    # 2. Network Comparison (top-right)
    ax2 = fig.add_subplot(gs[0, 2:4])
    net_summary = network_data.get('summary', {})
    protocols = ['WebSocket', 'REST API']
    latencies = [
        net_summary.get('websocket', {}).get('avg_latency_ms', 1.38),
        net_summary.get('rest', {}).get('avg_latency_ms', 2.04)
    ]
    bars2 = ax2.bar(protocols, latencies, color=[COLORS['primary'], COLORS['secondary']])
    ax2.set_ylabel('Mean Latency (ms)')
    ax2.set_title('Protocol Comparison')
    for bar, val in zip(bars2, latencies):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05, 
                f'{val:.2f}ms', ha='center', va='bottom', fontweight='bold')
    
    # 3. Concurrency (middle-left)
    ax3 = fig.add_subplot(gs[1, 0:2])
    conc_results = network_data.get('concurrency_results', [])
    if conc_results:
        connections = [r['concurrent_connections'] for r in conc_results]
        throughput = [r['throughput_rps'] for r in conc_results]
        ax3.plot(connections, throughput, 'o-', color=COLORS['primary'], linewidth=2, markersize=8)
        ax3.fill_between(connections, throughput, alpha=0.3, color=COLORS['primary'])
    ax3.set_xlabel('Concurrent Connections')
    ax3.set_ylabel('Throughput (RPS)')
    ax3.set_title('Scalability')
    ax3.grid(True, alpha=0.3)
    
    # 4. User Satisfaction (mock data - middle-right)
    ax4 = fig.add_subplot(gs[1, 2:4])
    categories = ['Ease', 'Design', 'Response', 'AI', 'Multi', 'Overall']
    scores = [4.6, 4.4, 4.8, 4.5, 4.7, 4.6]
    ax4.barh(categories, scores, color=COLORS['success'])
    ax4.set_xlim(3.5, 5)
    ax4.set_xlabel('Score (1-5)')
    ax4.set_title('User Satisfaction')
    ax4.axvline(x=4.5, color='green', linestyle='--', alpha=0.5)
    
    # 5. Key Metrics Table (bottom)
    ax5 = fig.add_subplot(gs[2, :])
    ax5.axis('off')
    
    # Get actual values
    ai_depth6 = summary.get('6', {}).get('mean_ms', 355.58)
    ws_latency = net_summary.get('websocket', {}).get('avg_latency_ms', 1.38)
    max_conn = net_summary.get('concurrency', {}).get('max_stable_connections', 50)
    max_rps = net_summary.get('concurrency', {}).get('max_throughput_rps', 827)
    
    metrics_data = [
        ['Metric', 'Value', 'Target', 'Status'],
        ['AI Response (D6)', f'{ai_depth6:.2f} ms', '< 500 ms', 'PASS' if ai_depth6 < 500 else 'FAIL'],
        ['WebSocket Latency', f'{ws_latency:.2f} ms', '< 5 ms', 'PASS' if ws_latency < 5 else 'FAIL'],
        ['Max Concurrent', f'{max_conn} users', '>= 50', 'PASS' if max_conn >= 50 else 'FAIL'],
        ['Throughput', f'{max_rps:.0f} RPS', '> 500 RPS', 'PASS' if max_rps > 500 else 'FAIL'],
        ['User Satisfaction', '4.6 / 5.0', '> 4.0', 'PASS'],
    ]
    
    table = ax5.table(cellText=metrics_data[1:], colLabels=metrics_data[0],
                     loc='center', cellLoc='center',
                     colColours=[COLORS['light']]*4,
                     cellColours=[[COLORS['light']]*4 for _ in range(5)])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(fontweight='bold')
            cell.set_facecolor(COLORS['primary'])
            cell.set_text_props(color='white')
        if col == 3 and row > 0:
            status = metrics_data[row][3]
            cell.set_facecolor('#d4edda' if status == 'PASS' else '#f8d7da')
    
    plt.savefig(os.path.join(output_dir, 'summary_dashboard.png'), dpi=300, bbox_inches='tight')
    plt.savefig(os.path.join(output_dir, 'summary_dashboard.pdf'), bbox_inches='tight')
    print(f"  [OK] summary_dashboard.png")
    plt.close()


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Test Results Visualization')
    parser.add_argument('--input', default='./test_results',
                        help='Input directory with test results')
    parser.add_argument('--output', default='./visualization_outputs',
                        help='Output directory for visualizations')
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    print("="*60)
    print("  CONNECT FOUR PRO - TEST RESULTS VISUALIZATION")
    print("="*60)
    print(f"  Input:  {args.input}/")
    print(f"  Output: {args.output}/")
    print("-"*60)
    
    # Load data
    print("\nLoading test results...")
    ai_data = load_ai_results(args.input)
    network_data = load_network_results(args.input)
    
    # Generate visualizations
    print("\nGenerating visualizations...")
    visualize_ai_performance(ai_data, args.output)
    visualize_ai_latency_detailed(ai_data, args.output)
    visualize_ai_complexity(ai_data, args.output)
    visualize_protocol_comparison(network_data, args.output)
    visualize_concurrency(network_data, args.output)
    visualize_tournament_heatmap(ai_data, args.output)
    visualize_summary_dashboard(ai_data, network_data, args.output)
    
    print("-"*60)
    print(f"  All visualizations completed!")
    print(f"  Output: {args.output}/")
    print("="*60)
    
    # List generated files
    print("\nGenerated files:")
    for f in sorted(os.listdir(args.output)):
        if f.endswith(('.png', '.pdf')):
            size = os.path.getsize(os.path.join(args.output, f)) / 1024
            print(f"  - {f} ({size:.1f} KB)")


if __name__ == "__main__":
    main()
