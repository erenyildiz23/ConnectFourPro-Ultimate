import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json

# Veri yükle
with open('/mnt/c/Users/Eren/Desktop/ConnectFour/ai_test_results/full_results_20251212_114420.json') as f:
    data = json.load(f)

latency_df = pd.DataFrame(data['latency_results'])
tournament_df = pd.DataFrame(data['tournament_results'])
scenario_df = pd.DataFrame(data['scenario_results'])

# Style
sns.set_style("whitegrid")
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1. Latency vs Depth
latency_grouped = latency_df.groupby('depth')['latency_ms'].agg(['mean', 'std'])
axes[0, 0].errorbar(latency_grouped.index, latency_grouped['mean'], 
                     yerr=latency_grouped['std'], marker='o', capsize=5, linewidth=2)
axes[0, 0].set_xlabel('Minimax Depth', fontsize=11)
axes[0, 0].set_ylabel('Response Time (ms)', fontsize=11)
axes[0, 0].set_title('Alpha-Beta Pruning: Depth vs Latency', fontweight='bold')
axes[0, 0].grid(True, alpha=0.3)

# 2. Alpha-Beta Cutoff Ratio
cutoff_ratio = latency_df[latency_df['cutoffs'] > 0].shape[0] / len(latency_df) * 100
axes[0, 1].bar(['Pruned', 'Not Pruned'], 
               [cutoff_ratio, 100 - cutoff_ratio], color=['#2ecc71', '#e74c3c'])
axes[0, 1].set_ylabel('Ratio (%)', fontsize=11)
axes[0, 1].set_title('Alpha-Beta Pruning Effectiveness', fontweight='bold')
axes[0, 1].set_ylim([0, 100])

# 3. Tournament Results
tournament_summary = tournament_df.groupby('winner_depth').size()
axes[1, 0].bar(tournament_summary.index, tournament_summary.values, color=['#3498db', '#e67e22'])
axes[1, 0].set_xlabel('Winner Depth', fontsize=11)
axes[1, 0].set_ylabel('Number of Wins', fontsize=11)
axes[1, 0].set_title('Tournament: Depth 2 vs Depth 3 (100 games)', fontweight='bold')

# 4. Nodes Evaluated vs Latency
axes[1, 1].scatter(latency_df['nodes_evaluated'], latency_df['latency_ms'], alpha=0.6, s=50)
axes[1, 1].set_xlabel('Number of Nodes Evaluated', fontsize=11)
axes[1, 1].set_ylabel('Response Time (ms)', fontsize=11)
axes[1, 1].set_title('Computational Complexity: Nodes vs Latency', fontweight='bold')
axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('ai_performance_analysis.png', dpi=300, bbox_inches='tight')
plt.show()