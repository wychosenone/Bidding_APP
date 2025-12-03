#!/usr/bin/env python3
"""
Experiment 1 Visualization Script
Generates comprehensive charts comparing Lua vs Optimistic Locking strategies
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

# Data extracted from experiment logs
users = [100, 500, 1000, 2000, 10000]

# Lua Script Strategy Results
lua_rps = [8512.44, 13002.77, 12761.56, 11908.28, 9747.94]
lua_p50 = [0, 24, 59, 120, 130]
lua_p95 = [3, 46, 110, 270, 650]
lua_p99 = [9, 65, 160, 370, 1300]
lua_total_requests = [254156, 389553, 386989, 382206, 413126]

# Optimistic Locking Strategy Results
opt_rps = [8545.20, 12709.17, 12661.96, 12017.57, 10410.09]
opt_p50 = [1, 24, 59, 120, 130]
opt_p95 = [3, 47, 120, 270, 500]
opt_p99 = [8, 68, 160, 380, 710]
opt_total_requests = [254772, 380856, 384317, 387406, 432804]

# Set up the style
plt.style.use('seaborn-v0_8-whitegrid')
fig = plt.figure(figsize=(16, 14))

# Color palette
lua_color = '#2E86AB'  # Blue
opt_color = '#E94F37'  # Red

# 1. Throughput Comparison (Bar Chart)
ax1 = fig.add_subplot(2, 2, 1)
x = np.arange(len(users))
width = 0.35

bars1 = ax1.bar(x - width/2, lua_rps, width, label='Lua Script', color=lua_color, alpha=0.8)
bars2 = ax1.bar(x + width/2, opt_rps, width, label='Optimistic Locking', color=opt_color, alpha=0.8)

ax1.set_xlabel('Concurrent Users', fontsize=12)
ax1.set_ylabel('Requests per Second (RPS)', fontsize=12)
ax1.set_title('Throughput Comparison: Lua vs Optimistic Locking', fontsize=14, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(users)
ax1.legend(loc='upper right')
ax1.set_ylim(0, 15000)

# Add value labels on bars
for bar in bars1:
    height = bar.get_height()
    ax1.annotate(f'{height:.0f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom', fontsize=8)
for bar in bars2:
    height = bar.get_height()
    ax1.annotate(f'{height:.0f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom', fontsize=8)

# 2. Latency Comparison - P99 (Line Chart)
ax2 = fig.add_subplot(2, 2, 2)
ax2.plot(users, lua_p99, 'o-', color=lua_color, linewidth=2, markersize=8, label='Lua P99')
ax2.plot(users, opt_p99, 's-', color=opt_color, linewidth=2, markersize=8, label='Optimistic P99')
ax2.plot(users, lua_p95, 'o--', color=lua_color, linewidth=1.5, markersize=6, alpha=0.6, label='Lua P95')
ax2.plot(users, opt_p95, 's--', color=opt_color, linewidth=1.5, markersize=6, alpha=0.6, label='Optimistic P95')

ax2.set_xlabel('Concurrent Users', fontsize=12)
ax2.set_ylabel('Latency (ms)', fontsize=12)
ax2.set_title('Latency Comparison: P95 and P99 Percentiles', fontsize=14, fontweight='bold')
ax2.set_xscale('log')
ax2.set_yscale('log')
ax2.legend(loc='upper left')
ax2.grid(True, which="both", ls="-", alpha=0.2)

# Add annotations for key points
ax2.annotate(f'{lua_p99[-1]}ms', (users[-1], lua_p99[-1]), textcoords="offset points", xytext=(10, 5), fontsize=9)
ax2.annotate(f'{opt_p99[-1]}ms', (users[-1], opt_p99[-1]), textcoords="offset points", xytext=(10, -10), fontsize=9)

# 3. Throughput Scaling (Line Chart)
ax3 = fig.add_subplot(2, 2, 3)
ax3.plot(users, lua_rps, 'o-', color=lua_color, linewidth=2.5, markersize=10, label='Lua Script')
ax3.plot(users, opt_rps, 's-', color=opt_color, linewidth=2.5, markersize=10, label='Optimistic Locking')

# Add peak indicator
peak_lua_idx = np.argmax(lua_rps)
peak_opt_idx = np.argmax(opt_rps)
ax3.annotate(f'Peak: {lua_rps[peak_lua_idx]:.0f} RPS',
            xy=(users[peak_lua_idx], lua_rps[peak_lua_idx]),
            xytext=(users[peak_lua_idx]+200, lua_rps[peak_lua_idx]+500),
            arrowprops=dict(arrowstyle='->', color=lua_color),
            fontsize=10, color=lua_color)

ax3.set_xlabel('Concurrent Users', fontsize=12)
ax3.set_ylabel('Requests per Second (RPS)', fontsize=12)
ax3.set_title('Throughput Scaling Under Load', fontsize=14, fontweight='bold')
ax3.set_xscale('log')
ax3.legend(loc='upper right')
ax3.axhline(y=10000, color='green', linestyle='--', alpha=0.5, label='10K RPS Target')
ax3.fill_between(users, 10000, 15000, alpha=0.1, color='green')
ax3.set_ylim(0, 15000)

# 4. P50 vs P99 Latency Distribution
ax4 = fig.add_subplot(2, 2, 4)

# Create grouped data for each user count
x_positions = np.arange(len(users))
width = 0.2

ax4.bar(x_positions - 1.5*width, lua_p50, width, label='Lua P50', color=lua_color, alpha=0.5)
ax4.bar(x_positions - 0.5*width, lua_p99, width, label='Lua P99', color=lua_color, alpha=0.9)
ax4.bar(x_positions + 0.5*width, opt_p50, width, label='Opt P50', color=opt_color, alpha=0.5)
ax4.bar(x_positions + 1.5*width, opt_p99, width, label='Opt P99', color=opt_color, alpha=0.9)

ax4.set_xlabel('Concurrent Users', fontsize=12)
ax4.set_ylabel('Latency (ms)', fontsize=12)
ax4.set_title('Latency Distribution: P50 vs P99', fontsize=14, fontweight='bold')
ax4.set_xticks(x_positions)
ax4.set_xticklabels(users)
ax4.legend(loc='upper left', ncol=2)
ax4.set_yscale('log')

plt.tight_layout()
plt.savefig('/Users/aaronwang/workspace/Bidding_APP/load-tests/experiment1_visualization.png', dpi=150, bbox_inches='tight')
print("Saved: experiment1_visualization.png")

# Create a second figure for additional analysis
fig2 = plt.figure(figsize=(14, 6))

# 5. Performance Difference Analysis
ax5 = fig2.add_subplot(1, 2, 1)
rps_diff = [(lua - opt) / opt * 100 for lua, opt in zip(lua_rps, opt_rps)]
colors = ['green' if d > 0 else 'red' for d in rps_diff]
bars = ax5.bar(range(len(users)), rps_diff, color=colors, alpha=0.7)
ax5.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
ax5.set_xticks(range(len(users)))
ax5.set_xticklabels(users)
ax5.set_xlabel('Concurrent Users', fontsize=12)
ax5.set_ylabel('RPS Difference (%)', fontsize=12)
ax5.set_title('Lua vs Optimistic: Throughput Difference\n(Positive = Lua faster)', fontsize=14, fontweight='bold')

for bar, diff in zip(bars, rps_diff):
    height = bar.get_height()
    ax5.annotate(f'{diff:+.1f}%',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3 if height >= 0 else -12),
                textcoords="offset points",
                ha='center', va='bottom' if height >= 0 else 'top',
                fontsize=10, fontweight='bold')

# 6. Total Requests Processed
ax6 = fig2.add_subplot(1, 2, 2)
x = np.arange(len(users))
width = 0.35

bars1 = ax6.bar(x - width/2, [r/1000 for r in lua_total_requests], width, label='Lua Script', color=lua_color, alpha=0.8)
bars2 = ax6.bar(x + width/2, [r/1000 for r in opt_total_requests], width, label='Optimistic Locking', color=opt_color, alpha=0.8)

ax6.set_xlabel('Concurrent Users', fontsize=12)
ax6.set_ylabel('Total Requests (thousands)', fontsize=12)
ax6.set_title('Total Requests Processed (30s test)', fontsize=14, fontweight='bold')
ax6.set_xticks(x)
ax6.set_xticklabels(users)
ax6.legend(loc='upper right')

for bar in bars1 + bars2:
    height = bar.get_height()
    ax6.annotate(f'{height:.0f}K',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha='center', va='bottom', fontsize=8)

plt.tight_layout()
plt.savefig('/Users/aaronwang/workspace/Bidding_APP/load-tests/experiment1_analysis.png', dpi=150, bbox_inches='tight')
print("Saved: experiment1_analysis.png")

# Create summary table
print("\n" + "="*80)
print("EXPERIMENT 1: WRITE CONTENTION TEST - COMPLETE RESULTS")
print("="*80)
print(f"\n{'Users':<10} {'Lua RPS':<12} {'Opt RPS':<12} {'Diff %':<10} {'Lua P99':<10} {'Opt P99':<10}")
print("-"*64)
for i, u in enumerate(users):
    diff = (lua_rps[i] - opt_rps[i]) / opt_rps[i] * 100
    print(f"{u:<10} {lua_rps[i]:<12.2f} {opt_rps[i]:<12.2f} {diff:+.2f}%{'':>3} {lua_p99[i]:<10} {opt_p99[i]:<10}")

print("\n" + "="*80)
print("KEY FINDINGS:")
print("="*80)
print(f"1. Peak Throughput (Lua):       {max(lua_rps):,.0f} RPS at {users[np.argmax(lua_rps)]} users")
print(f"2. Peak Throughput (Optimistic): {max(opt_rps):,.0f} RPS at {users[np.argmax(opt_rps)]} users")
print(f"3. Performance Difference:       < 6.4% across all test cases")
print(f"4. Zero Failures:                Both strategies achieved 0% error rate")
print(f"5. Correctness:                  All tests passed - no lost updates")
print(f"6. Bottleneck:                   Locust client CPU (90%+), not Redis")
print("="*80)

# plt.show()  # Disabled for non-interactive mode
print("\nVisualization complete!")
