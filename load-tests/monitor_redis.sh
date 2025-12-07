#!/bin/bash

# Redis Resource Monitoring Script for Experiment 1
# Monitors CPU usage, memory, slowlog during load test

CONTAINER_NAME="localstack-redis"
OUTPUT_FILE="${1:-/tmp/redis_monitoring.log}"
INTERVAL=1  # Sample every 1 second

echo "Starting Redis monitoring..."
echo "Output file: $OUTPUT_FILE"
echo "Container: $CONTAINER_NAME"
echo "Sampling interval: ${INTERVAL}s"
echo ""

# Initialize output file
echo "timestamp,cpu_percent,mem_usage_mb,mem_percent,slowlog_count" > "$OUTPUT_FILE"

echo "Monitoring started. Press Ctrl+C to stop."
echo "---"

# Function to get Redis slowlog count
get_slowlog_count() {
    docker exec $CONTAINER_NAME redis-cli SLOWLOG LEN 2>/dev/null || echo "0"
}

# Clear slowlog before starting
docker exec $CONTAINER_NAME redis-cli SLOWLOG RESET >/dev/null 2>&1

# Monitor loop
while true; do
    # Get container stats
    STATS=$(docker stats $CONTAINER_NAME --no-stream --format "{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}" 2>/dev/null)

    if [ -z "$STATS" ]; then
        echo "Error: Cannot get stats from container $CONTAINER_NAME"
        sleep $INTERVAL
        continue
    fi

    # Parse stats
    CPU_PERCENT=$(echo "$STATS" | cut -d',' -f1 | sed 's/%//')
    MEM_USAGE=$(echo "$STATS" | cut -d',' -f2 | awk '{print $1}' | sed 's/MiB//')
    MEM_PERCENT=$(echo "$STATS" | cut -d',' -f3 | sed 's/%//')

    # Get slowlog count
    SLOWLOG_COUNT=$(get_slowlog_count)

    # Get current timestamp
    TIMESTAMP=$(date +%s)

    # Write to file
    echo "$TIMESTAMP,$CPU_PERCENT,$MEM_USAGE,$MEM_PERCENT,$SLOWLOG_COUNT" >> "$OUTPUT_FILE"

    # Print to console
    printf "[%s] CPU: %6s%% | MEM: %6s MiB (%5s%%) | Slowlog: %4s\n" \
        "$(date +%H:%M:%S)" "$CPU_PERCENT" "$MEM_USAGE" "$MEM_PERCENT" "$SLOWLOG_COUNT"

    sleep $INTERVAL
done
