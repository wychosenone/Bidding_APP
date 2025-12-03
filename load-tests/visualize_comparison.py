#!/usr/bin/env python3
"""
Visualization script for LocalStack vs AWS Performance Comparison
Generates charts for the Final Mastery Assignment
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

# Data from test results
users = [100, 500, 1000, 2000, 10000]

# LocalStack Results (Lua Script)
localstack_rps = [8512.44, 13002.77, 12761.56, 11908.28, 9747.94]
localstack_p50 = [0, 24, 59, 120, 130]
localstack_p95 = [3, 46, 110, 270, 650]
localstack_p99 = [9, 65, 160, 370, 1300]

# AWS Results
aws_rps = [3606.74, 10256.11, 10736.97, 11083.92, 9734.95]
aws_p50 = [22, 40, 78, 120, 480]
aws_p95 = [30, 91, 230, 540, 3000]
aws_p99 = [37, 110, 350, 740, 3900]

# Create figure with subplots
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('LocalStack vs AWS Performance Comparison\nReal-time Bidding System - Experiment 1', fontsize=14, fontweight='bold')

# Colors
localstack_color = '#2ecc71'  # Green
aws_color = '#e74c3c'  # Red

# 1. Throughput Comparison (Bar Chart)
ax1 = axes[0, 0]
x = np.arange(len(users))
width = 0.35

bars1 = ax1.bar(x - width/2, localstack_rps, width, label='LocalStack', color=localstack_color, edgecolor='black')
bars2 = ax1.bar(x + width/2, aws_rps, width, label='AWS', color=aws_color, edgecolor='black')

ax1.set_xlabel('Concurrent Users')
ax1.set_ylabel('Requests Per Second (RPS)')
ax1.set_title('Throughput Comparison')
ax1.set_xticks(x)
ax1.set_xticklabels(users)
ax1.legend()
ax1.grid(axis='y', alpha=0.3)

# Add value labels on bars
for bar in bars1:
    height = bar.get_height()
    ax1.annotate(f'{height:,.0f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=8)
for bar in bars2:
    height = bar.get_height()
    ax1.annotate(f'{height:,.0f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=8)

# 2. P50 Latency Comparison (Line Chart)
ax2 = axes[0, 1]
ax2.plot(users, localstack_p50, 'o-', color=localstack_color, linewidth=2, markersize=8, label='LocalStack P50')
ax2.plot(users, aws_p50, 's-', color=aws_color, linewidth=2, markersize=8, label='AWS P50')
ax2.set_xlabel('Concurrent Users')
ax2.set_ylabel('Latency (ms)')
ax2.set_title('Median Latency (P50) Comparison')
ax2.set_xscale('log')
ax2.set_xticks(users)
ax2.set_xticklabels(users)
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3. P99 Latency Comparison (Line Chart with log scale)
ax3 = axes[1, 0]
ax3.plot(users, localstack_p99, 'o-', color=localstack_color, linewidth=2, markersize=8, label='LocalStack P99')
ax3.plot(users, aws_p99, 's-', color=aws_color, linewidth=2, markersize=8, label='AWS P99')
ax3.set_xlabel('Concurrent Users')
ax3.set_ylabel('Latency (ms)')
ax3.set_title('Tail Latency (P99) Comparison')
ax3.set_xscale('log')
ax3.set_yscale('log')
ax3.set_xticks(users)
ax3.set_xticklabels(users)
ax3.legend()
ax3.grid(True, alpha=0.3, which='both')

# 4. Performance Ratio (AWS/LocalStack)
ax4 = axes[1, 1]
rps_ratio = [aws/local * 100 for aws, local in zip(aws_rps, localstack_rps)]
latency_ratio = [aws/local if local > 0 else aws for aws, local in zip(aws_p99, localstack_p99)]

x = np.arange(len(users))
width = 0.35

# Plot RPS ratio
ax4_twin = ax4.twinx()
bars3 = ax4.bar(x - width/2, rps_ratio, width, label='Throughput (AWS % of LocalStack)', color='#3498db', alpha=0.7)
line, = ax4_twin.plot(x + width/4, latency_ratio, 'D-', color='#9b59b6', linewidth=2, markersize=8, label='P99 Latency Ratio (AWS/LocalStack)')

ax4.set_xlabel('Concurrent Users')
ax4.set_ylabel('AWS Throughput (% of LocalStack)', color='#3498db')
ax4_twin.set_ylabel('P99 Latency Ratio', color='#9b59b6')
ax4.set_title('AWS Performance Relative to LocalStack')
ax4.set_xticks(x)
ax4.set_xticklabels(users)
ax4.axhline(y=100, color='gray', linestyle='--', alpha=0.5, label='Parity (100%)')
ax4.set_ylim(0, 120)
ax4_twin.set_ylim(0, 5)

# Combined legend
lines1, labels1 = ax4.get_legend_handles_labels()
lines2, labels2 = ax4_twin.get_legend_handles_labels()
ax4.legend(lines1 + [line], labels1 + labels2, loc='upper right', fontsize=8)
ax4.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('localstack_vs_aws_comparison.png', dpi=150, bbox_inches='tight')
print("Saved: localstack_vs_aws_comparison.png")

# Create a second figure for detailed analysis
fig2, axes2 = plt.subplots(1, 2, figsize=(14, 5))
fig2.suptitle('Network Latency Impact Analysis', fontsize=14, fontweight='bold')

# 1. Latency Percentiles Stacked (LocalStack)
ax5 = axes2[0]
x = np.arange(len(users))
width = 0.25

ax5.bar(x - width, localstack_p50, width, label='P50', color='#27ae60')
ax5.bar(x, localstack_p95, width, label='P95', color='#f39c12')
ax5.bar(x + width, localstack_p99, width, label='P99', color='#c0392b')

ax5.set_xlabel('Concurrent Users')
ax5.set_ylabel('Latency (ms)')
ax5.set_title('LocalStack Latency Distribution')
ax5.set_xticks(x)
ax5.set_xticklabels(users)
ax5.legend()
ax5.grid(axis='y', alpha=0.3)

# 2. Latency Percentiles Stacked (AWS)
ax6 = axes2[1]
ax6.bar(x - width, aws_p50, width, label='P50', color='#27ae60')
ax6.bar(x, aws_p95, width, label='P95', color='#f39c12')
ax6.bar(x + width, aws_p99, width, label='P99', color='#c0392b')

ax6.set_xlabel('Concurrent Users')
ax6.set_ylabel('Latency (ms)')
ax6.set_title('AWS Latency Distribution')
ax6.set_xticks(x)
ax6.set_xticklabels(users)
ax6.legend()
ax6.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('latency_distribution_comparison.png', dpi=150, bbox_inches='tight')
print("Saved: latency_distribution_comparison.png")

# Create summary statistics table as image
fig3, ax7 = plt.subplots(figsize=(12, 6))
ax7.axis('off')

# Table data
table_data = [
    ['100', '8,512', '3,607', '-57.6%', '9ms', '37ms', '4.1x'],
    ['500', '13,003', '10,256', '-21.1%', '65ms', '110ms', '1.7x'],
    ['1,000', '12,762', '10,737', '-15.9%', '160ms', '350ms', '2.2x'],
    ['2,000', '11,908', '11,084', '-6.9%', '370ms', '740ms', '2.0x'],
    ['10,000', '9,748', '9,735', '-0.1%', '1,300ms', '3,900ms', '3.0x'],
]

columns = ['Users', 'LocalStack RPS', 'AWS RPS', 'RPS Diff', 'LocalStack P99', 'AWS P99', 'Latency Ratio']

table = ax7.table(cellText=table_data,
                  colLabels=columns,
                  loc='center',
                  cellLoc='center',
                  colColours=['#3498db']*7)

table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.2, 1.8)

# Style header
for i in range(len(columns)):
    table[(0, i)].set_text_props(weight='bold', color='white')

# Color code the RPS difference column
for i, row in enumerate(table_data):
    diff = float(row[3].replace('%', ''))
    if diff < -30:
        table[(i+1, 3)].set_facecolor('#ffcccc')
    elif diff < -10:
        table[(i+1, 3)].set_facecolor('#ffe6cc')
    else:
        table[(i+1, 3)].set_facecolor('#ccffcc')

ax7.set_title('LocalStack vs AWS: Complete Comparison Summary\n', fontsize=14, fontweight='bold')

plt.savefig('comparison_summary_table.png', dpi=150, bbox_inches='tight', facecolor='white')
print("Saved: comparison_summary_table.png")

print("\nAll visualizations generated successfully!")
print("\nKey Findings:")
print(f"  - LocalStack peak throughput: {max(localstack_rps):,.0f} RPS (at 500 users)")
print(f"  - AWS peak throughput: {max(aws_rps):,.0f} RPS (at 2000 users)")
print(f"  - Average AWS throughput ratio: {sum(aws_rps)/sum(localstack_rps)*100:.1f}% of LocalStack")
print(f"  - AWS P99 latency is {sum(aws_p99)/sum(localstack_p99):.1f}x higher than LocalStack on average")
