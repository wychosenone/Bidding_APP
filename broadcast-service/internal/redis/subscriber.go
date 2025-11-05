package redis

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/redis/go-redis/v9"
)

// Subscriber wraps Redis Pub/Sub functionality
type Subscriber struct {
	client *redis.Client
	pubsub *redis.PubSub
}

// NewSubscriber creates a new Redis Pub/Sub subscriber
func NewSubscriber(addr, password string, db int) (*Subscriber, error) {
	rdb := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: password,
		DB:       db,
	})

	// Test connection
	ctx := context.Background()
	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	return &Subscriber{
		client: rdb,
	}, nil
}

// SubscribeToItem subscribes to bid events for a specific item
// Pattern: "bid_events:{itemID}"
func (s *Subscriber) SubscribeToItem(ctx context.Context, itemID string) error {
	channel := fmt.Sprintf("bid_events:%s", itemID)
	s.pubsub = s.client.Subscribe(ctx, channel)
	return nil
}

// SubscribeToPattern subscribes to all bid events using pattern matching
// Pattern: "bid_events:*" subscribes to all items
func (s *Subscriber) SubscribeToPattern(ctx context.Context, pattern string) error {
	s.pubsub = s.client.PSubscribe(ctx, pattern)
	return nil
}

// Listen starts listening for messages and sends them to the provided channel
// This is a blocking operation - run in a goroutine
func (s *Subscriber) Listen(ctx context.Context, messageChan chan<- *Message) error {
	if s.pubsub == nil {
		return fmt.Errorf("not subscribed to any channel")
	}

	// Channel returns raw Redis messages
	ch := s.pubsub.Channel()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case msg := <-ch:
			// Parse the message
			var event map[string]interface{}
			if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
				fmt.Printf("Warning: failed to parse message: %v\n", err)
				continue
			}

			// Extract item ID from the channel name
			// Channel format: "bid_events:{itemID}"
			itemID := extractItemIDFromChannel(msg.Channel)

			// Send to WebSocket handler
			messageChan <- &Message{
				ItemID:  itemID,
				Payload: msg.Payload,
				Event:   event,
			}
		}
	}
}

// Message represents a parsed Pub/Sub message
type Message struct {
	ItemID  string
	Payload string                 // Raw JSON payload
	Event   map[string]interface{} // Parsed event data
}

// extractItemIDFromChannel extracts item ID from channel name
// Example: "bid_events:item123" -> "item123"
func extractItemIDFromChannel(channel string) string {
	prefix := "bid_events:"
	if len(channel) > len(prefix) {
		return channel[len(prefix):]
	}
	return ""
}

// Close closes the subscriber
func (s *Subscriber) Close() error {
	if s.pubsub != nil {
		s.pubsub.Close()
	}
	return s.client.Close()
}
