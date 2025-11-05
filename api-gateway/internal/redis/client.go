package redis

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

// Client wraps the Redis client with bidding-specific operations
type Client struct {
	client *redis.Client
	// Lua script for atomic compare-and-set bid operation
	bidScript *redis.Script
}

// NewClient creates a new Redis client
func NewClient(addr, password string, db int) (*Client, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: password,
		DB:       db,
	})

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	// Define Lua script for atomic bid operation
	// This script runs atomically on Redis server - no race conditions!
	bidScript := redis.NewScript(`
		-- KEYS[1]: item:{itemID}:current_bid (current highest bid amount)
		-- KEYS[2]: item:{itemID}:highest_bidder (current highest bidder ID)
		-- ARGV[1]: new bid amount
		-- ARGV[2]: bidder user ID

		-- Get current bid (returns nil if doesn't exist)
		local current_bid = redis.call('GET', KEYS[1])

		-- If no current bid, initialize with 0
		if not current_bid then
			current_bid = 0
		else
			current_bid = tonumber(current_bid)
		end

		local new_bid = tonumber(ARGV[1])

		-- Compare: new bid must be higher than current
		if new_bid > current_bid then
			-- Set new highest bid
			redis.call('SET', KEYS[1], new_bid)
			-- Set new highest bidder
			redis.call('SET', KEYS[2], ARGV[2])
			-- Return success with previous bid
			return {1, current_bid}
		else
			-- Bid too low, return failure with current bid
			return {0, current_bid}
		end
	`)

	return &Client{
		client:    rdb,
		bidScript: bidScript,
	}, nil
}

// BidResult represents the result of a bid operation
type BidResult struct {
	Success     bool
	PreviousBid float64
	CurrentBid  float64
}

// PlaceBid atomically attempts to place a bid on an item
// Returns BidResult indicating success/failure and relevant bid amounts
func (c *Client) PlaceBid(ctx context.Context, itemID, userID string, amount float64) (*BidResult, error) {
	keys := []string{
		fmt.Sprintf("item:%s:current_bid", itemID),
		fmt.Sprintf("item:%s:highest_bidder", itemID),
	}

	// Execute Lua script atomically
	result, err := c.bidScript.Run(ctx, c.client, keys, amount, userID).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to execute bid script: %w", err)
	}

	// Parse result
	// Result is [success_flag, previous_bid]
	resultArray, ok := result.([]interface{})
	if !ok || len(resultArray) != 2 {
		return nil, fmt.Errorf("unexpected script result format")
	}

	success := resultArray[0].(int64) == 1
	previousBid := float64(resultArray[1].(int64))

	currentBid := previousBid
	if success {
		currentBid = amount
	}

	return &BidResult{
		Success:     success,
		PreviousBid: previousBid,
		CurrentBid:  currentBid,
	}, nil
}

// GetItemBid retrieves the current highest bid for an item
func (c *Client) GetItemBid(ctx context.Context, itemID string) (float64, string, error) {
	pipe := c.client.Pipeline()

	bidCmd := pipe.Get(ctx, fmt.Sprintf("item:%s:current_bid", itemID))
	bidderCmd := pipe.Get(ctx, fmt.Sprintf("item:%s:highest_bidder", itemID))

	_, err := pipe.Exec(ctx)
	if err != nil && err != redis.Nil {
		return 0, "", fmt.Errorf("failed to get item bid: %w", err)
	}

	var bid float64
	if bidCmd.Err() == nil {
		if err := bidCmd.Scan(&bid); err != nil {
			bid = 0
		}
	}

	var bidder string
	if bidderCmd.Err() == nil {
		bidder = bidderCmd.Val()
	}

	return bid, bidder, nil
}

// PublishBidEvent publishes a bid event to Redis Pub/Sub
// This will be picked up by the broadcast service for real-time WebSocket updates
func (c *Client) PublishBidEvent(ctx context.Context, itemID string, event interface{}) error {
	eventJSON, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	channel := fmt.Sprintf("bid_events:%s", itemID)
	return c.client.Publish(ctx, channel, eventJSON).Err()
}

// Close closes the Redis connection
func (c *Client) Close() error {
	return c.client.Close()
}
