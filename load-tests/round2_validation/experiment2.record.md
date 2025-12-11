# Test with 100 connections
python3 websocket_fanout_test.py \
  --connections 100 \
  --bids 10 \
  --interval 5 \
  --ws-url "ws://bidding-system-alb-1700264738.us-west-2.elb.amazonaws.com/ws" \
  --api-url "http://bidding-system-alb-1700264738.us-west-2.elb.amazonaws.com" \
  --item-id "experiment2_item"


Results:
```
R1

Starting fan-out test with 10 bids, 5s interval...
Watching 100 connections

Bid 1/10: $100.00 sent at 18:51:59.821
  Timeout: Only 0/100 clients received the event
Bid 2/10: $101.00 sent at 18:52:14.872
  Timeout: Only 0/100 clients received the event
Bid 3/10: $102.00 sent at 18:52:29.930
  Timeout: Only 0/100 clients received the event
Bid 4/10: $103.00 sent at 18:52:44.989
  Timeout: Only 0/100 clients received the event
Bid 5/10: $104.00 sent at 18:53:00.055
  Timeout: Only 0/100 clients received the event
Bid 6/10: $105.00 sent at 18:53:15.104
  Timeout: Only 0/100 clients received the event
Bid 7/10: $106.00 sent at 18:53:30.163
  Timeout: Only 0/100 clients received the event
Bid 8/10: $107.00 sent at 18:53:45.225
  Timeout: Only 0/100 clients received the event
Bid 9/10: $108.00 sent at 18:54:00.289
  Timeout: Only 0/100 clients received the event
Bid 10/10: $109.00 sent at 18:54:15.353
  Timeout: Only 0/100 clients received the event

No data collected


after the fix 

Bid 1/10: $113.00 sent at 19:13:20.348
  Event ID: 7e6fa412...
  Received by: 100/100 clients
  Latency - Min: 384.43ms, Median: 392.51ms, Max: 396.64ms
  P95: 396.57ms, P99: 396.64ms
Bid 2/10: $114.00 sent at 19:13:25.746
  Event ID: ff8315e5...
  Received by: 100/100 clients
  Latency - Min: 48.70ms, Median: 55.61ms, Max: 60.67ms
  P95: 60.44ms, P99: 60.67ms
Bid 3/10: $115.00 sent at 19:13:30.808
  Event ID: 2af08a31...
  Received by: 100/100 clients
  Latency - Min: 39.02ms, Median: 47.26ms, Max: 52.00ms
  P95: 51.97ms, P99: 52.00ms
Bid 4/10: $116.00 sent at 19:13:35.861
  Event ID: ac5c84fe...
  Received by: 100/100 clients
  Latency - Min: 44.36ms, Median: 48.71ms, Max: 53.73ms
  P95: 53.67ms, P99: 53.73ms
Bid 5/10: $117.00 sent at 19:13:40.917
  Event ID: b8e50ab9...
  Received by: 100/100 clients
  Latency - Min: 47.95ms, Median: 55.93ms, Max: 60.87ms
  P95: 60.84ms, P99: 60.87ms
Bid 6/10: $118.00 sent at 19:13:45.979
  Event ID: d35d6c88...
  Received by: 100/100 clients
  Latency - Min: 42.43ms, Median: 49.49ms, Max: 53.07ms
  P95: 52.93ms, P99: 53.07ms
Bid 7/10: $119.00 sent at 19:13:51.033
  Event ID: ee1040a6...
  Received by: 100/100 clients
  Latency - Min: 38.67ms, Median: 48.58ms, Max: 51.63ms
  P95: 51.61ms, P99: 51.63ms
Bid 8/10: $120.00 sent at 19:13:56.086
  Event ID: 76f05a62...
  Received by: 100/100 clients
  Latency - Min: 42.64ms, Median: 52.39ms, Max: 53.57ms
  P95: 53.53ms, P99: 53.57ms
Bid 9/10: $121.00 sent at 19:14:01.141
  Event ID: dcb5e867...
  Received by: 100/100 clients
  Latency - Min: 59.63ms, Median: 63.48ms, Max: 66.75ms
  P95: 66.69ms, P99: 66.75ms
Bid 10/10: $122.00 sent at 19:14:06.210
  Event ID: 51e06f12...
  Received by: 100/100 clients
  Latency - Min: 39.25ms, Median: 51.02ms, Max: 53.32ms
  P95: 53.28ms, P99: 53.32ms

============================================================
EXPERIMENT 2: WebSocket Fan-Out Test Results
============================================================
Configuration:
  Connections: 100
  Total bids sent: 10
  Total messages received: 1000

Overall Latency Statistics:
  Min: 38.67ms
  Median: 51.66ms
  Mean: 85.64ms
  Max: 396.64ms
  P50: 51.66ms
  P95: 392.51ms
  P99: 396.48ms


The script will automatically:
Check the current bid (currently $109)
Start bidding from $110 and increment
Successfully receive all messages
Summary of the fix:
Problem: Bids were rejected because they were lower than the current price ($109)
Solution: Modified the script to check the current price and start bidding from a higher amount
Buffer channel: Already correctly set to 10,000 (no change needed)

Connections: 500
bids: 5
interval: 5


Starting fan-out test with 5 bids, 5s interval...
Watching 500 connections

Current price: $126.00 (target: $99.00)
  Note: Can't bid lower than current, will start from $127.00
Starting bids from: $127.00

Bid 1/5: $127.00 sent at 20:16:27.953
  Event ID: 971174ca...
  Received by: 500/500 clients
  Latency - Min: 35.17ms, Median: 66.31ms, Max: 97.77ms
  P95: 96.83ms, P99: 97.72ms
Bid 2/5: $128.00 sent at 20:16:33.052
  Event ID: aa637e3c...
  Received by: 500/500 clients
  Latency - Min: 36.86ms, Median: 72.87ms, Max: 101.30ms
  P95: 100.72ms, P99: 101.27ms
Bid 3/5: $129.00 sent at 20:16:38.154
  Event ID: 190d6427...
  Received by: 500/500 clients
  Latency - Min: 37.30ms, Median: 67.27ms, Max: 100.36ms
  P95: 99.77ms, P99: 100.33ms
Bid 4/5: $130.00 sent at 20:16:43.256
  Event ID: 613407cd...
  Received by: 500/500 clients
  Latency - Min: 37.96ms, Median: 70.58ms, Max: 102.62ms
  P95: 99.88ms, P99: 102.56ms
Bid 5/5: $131.00 sent at 20:16:48.360
  Event ID: f588ac63...
  Received by: 500/500 clients
  Latency - Min: 37.83ms, Median: 66.84ms, Max: 100.93ms
  P95: 100.23ms, P99: 100.76ms

============================================================
EXPERIMENT 2: WebSocket Fan-Out Test Results
============================================================
Configuration:
  Connections: 500
  Total bids sent: 5
  Total messages received: 2500

Overall Latency Statistics:
  Min: 35.17ms
  Median: 70.22ms
  Mean: 70.23ms
  Max: 102.62ms
  P50: 70.23ms
  P95: 99.75ms
  P99: 101.00ms


1000 connections

Current price: $131.00 (target: $99.00)
  Note: Can't bid lower than current, will start from $132.00
Starting bids from: $132.00

Bid 1/5: $132.00 sent at 20:25:55.590
  Event ID: eeb3a0a2...
  Received by: 1000/1000 clients
  Latency - Min: 37.51ms, Median: 92.16ms, Max: 144.62ms
  P95: 142.05ms, P99: 144.43ms
Bid 2/5: $133.00 sent at 20:26:00.731
  Event ID: e992ad03...
  Received by: 1000/1000 clients
  Latency - Min: 46.35ms, Median: 118.48ms, Max: 189.61ms
  P95: 181.56ms, P99: 189.38ms
Bid 3/5: $134.00 sent at 20:26:05.919
  Event ID: 4fa68314...
  Received by: 1000/1000 clients
  Latency - Min: 49.85ms, Median: 119.84ms, Max: 188.93ms
  P95: 183.80ms, P99: 188.82ms
Bid 4/5: $135.00 sent at 20:26:11.107
  Event ID: 59a81e0f...
  Received by: 1000/1000 clients
  Latency - Min: 43.69ms, Median: 108.17ms, Max: 176.90ms
  P95: 170.32ms, P99: 176.81ms
Bid 5/5: $136.00 sent at 20:26:16.284
  Event ID: 770e4b81...
  Received by: 1000/1000 clients
  Latency - Min: 46.82ms, Median: 110.79ms, Max: 180.08ms
  P95: 176.76ms, P99: 179.64ms

============================================================
EXPERIMENT 2: WebSocket Fan-Out Test Results
============================================================
Configuration:
  Connections: 1000
  Total bids sent: 5
  Total messages received: 5000

Overall Latency Statistics:
  Min: 37.51ms
  Median: 109.73ms
  Mean: 111.30ms
  Max: 189.61ms
  P50: 109.73ms
  P95: 177.44ms
  P99: 188.59ms


5000 connections
Starting fan-out test with 5 bids, 5s interval...
Watching 5000 connections

Current price: $136.00 (target: $99.00)
  Note: Can't bid lower than current, will start from $137.00
Starting bids from: $137.00

Bid 1/5: $137.00 sent at 20:27:51.052
  Event ID: 4825f2eb...
  Received by: 5000/5000 clients
  Latency - Min: 35.11ms, Median: 397.07ms, Max: 3358.07ms
  P95: 959.81ms, P99: 2627.29ms
Bid 2/5: $138.00 sent at 20:27:59.412
  Event ID: fdb58a6f...
  Received by: 5000/5000 clients
  Latency - Min: 38.86ms, Median: 389.63ms, Max: 4502.08ms
  P95: 1271.58ms, P99: 2459.04ms
Bid 3/5: $139.00 sent at 20:28:08.916
  Event ID: ff1eac1e...
  Received by: 5000/5000 clients
  Latency - Min: 39.65ms, Median: 386.28ms, Max: 5335.84ms
  P95: 826.71ms, P99: 1812.98ms
Bid 4/5: $140.00 sent at 20:28:19.254
  Event ID: ac80f3fd...
  Received by: 5000/5000 clients
  Latency - Min: 42.42ms, Median: 398.93ms, Max: 3539.56ms
  P95: 1143.65ms, P99: 1907.52ms
Bid 5/5: $141.00 sent at 20:28:27.795
  Event ID: 5233e105...
  Received by: 5000/5000 clients
  Latency - Min: 39.70ms, Median: 381.63ms, Max: 5559.03ms
  P95: 831.28ms, P99: 1496.07ms

============================================================
EXPERIMENT 2: WebSocket Fan-Out Test Results
============================================================
Configuration:
  Connections: 5000
  Total bids sent: 5
  Total messages received: 25000

Overall Latency Statistics:
  Min: 35.11ms
  Median: 390.00ms
  Mean: 446.80ms
  Max: 5559.03ms
  P50: 390.00ms
  P95: 954.88ms
  P99: 2135.46ms


10000 connections
Current price: $141.00 (target: $99.00)
  Note: Can't bid lower than current, will start from $142.00
Starting bids from: $142.00

Bid 1/5: $142.00 sent at 20:32:44.593
  Event ID: 34d1a978...
  Received by: 9979/9979 clients
  Latency - Min: 36.31ms, Median: 724.38ms, Max: 6447.46ms
  P95: 1492.39ms, P99: 4789.41ms
Bid 2/5: $143.00 sent at 20:32:56.042
  Event ID: d6855780...
  Timeout: Only 9934/9979 clients received the event
  Received by: 9934/9979 clients
  Latency - Min: 44.89ms, Median: 606.85ms, Max: 10363.05ms
  P95: 3779.33ms, P99: 6714.76ms
Bid 3/5: $144.00 sent at 20:33:11.408
  Event ID: e81e6f0e...
  Filtered out 45 stale events from previous bids
  Received by: 9979/9979 clients
  Latency - Min: 44.53ms, Median: 740.07ms, Max: 9274.93ms
  P95: 2619.78ms, P99: 3892.60ms
Bid 4/5: $145.00 sent at 20:33:25.685
  Event ID: aa303ddb...
  Received by: 9979/9979 clients
  Latency - Min: 43.91ms, Median: 718.50ms, Max: 4464.54ms
  P95: 1514.94ms, P99: 2159.69ms
Bid 5/5: $146.00 sent at 20:33:35.153
  Event ID: 86b3cd3d...
  Timeout: Only 9978/9979 clients received the event
  Received by: 9978/9979 clients
  Latency - Min: 40.89ms, Median: 660.08ms, Max: 3697.51ms
  P95: 1308.63ms, P99: 1842.93ms

============================================================
EXPERIMENT 2: WebSocket Fan-Out Test Results
============================================================
Configuration:
  Connections: 9979
  Total bids sent: 5
  Total messages received: 49849

Overall Latency Statistics:
  Min: 36.31ms
  Median: 682.24ms
  Mean: 843.82ms
  Max: 10363.05ms
  P50: 682.24ms
  P95: 2177.13ms
  P99: 4405.72ms
```

