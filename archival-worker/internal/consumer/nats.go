package consumer

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/aaronwang/bidding-app/archival-worker/internal/database"
	"github.com/aaronwang/bidding-app/shared/models"
	"github.com/nats-io/nats.go"
)

// NATSConsumer consumes bid events from NATS and persists to database
type NATSConsumer struct {
	conn *nats.Conn
	sub  *nats.Subscription
	db   *database.PostgresClient
}

// NewNATSConsumer creates a new NATS consumer
func NewNATSConsumer(natsURL string, db *database.PostgresClient) (*NATSConsumer, error) {
	conn, err := nats.Connect(natsURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to NATS: %w", err)
	}

	return &NATSConsumer{
		conn: conn,
		db:   db,
	}, nil
}

// Start begins consuming messages from NATS
// Subject pattern: "bid.events.*" subscribes to all item bid events
func (c *NATSConsumer) Start(ctx context.Context) error {
	// Subscribe to all bid events
	// Using wildcard "*" to match all items: bid.events.item1, bid.events.item2, etc.
	sub, err := c.conn.Subscribe("bid.events.*", func(msg *nats.Msg) {
		c.handleMessage(ctx, msg)
	})
	if err != nil {
		return fmt.Errorf("failed to subscribe: %w", err)
	}

	c.sub = sub
	fmt.Println("Subscribed to NATS subject: bid.events.*")

	// Keep consumer running until context is cancelled
	<-ctx.Done()
	return nil
}

// handleMessage processes a single bid event message
func (c *NATSConsumer) handleMessage(ctx context.Context, msg *nats.Msg) {
	// Parse the event
	var event models.BidEvent
	if err := json.Unmarshal(msg.Data, &event); err != nil {
		fmt.Printf("Failed to unmarshal event: %v\n", err)
		return
	}

	// Create a timeout context for database operations
	dbCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	// Persist to database
	if err := c.persistBidEvent(dbCtx, &event); err != nil {
		fmt.Printf("Failed to persist bid event %s: %v\n", event.EventID, err)
		// In production, you'd want retry logic or dead-letter queue here
		return
	}

	fmt.Printf("Persisted bid event %s (item: %s, user: %s, amount: $%.2f)\n",
		event.EventID, event.ItemID, event.UserID, event.Amount)

	// Acknowledge message
	msg.Ack()
}

// persistBidEvent writes the bid event to PostgreSQL
func (c *NATSConsumer) persistBidEvent(ctx context.Context, event *models.BidEvent) error {
	// Insert bid record
	if err := c.db.InsertBid(ctx, event); err != nil {
		return fmt.Errorf("failed to insert bid: %w", err)
	}

	// Update item's current bid
	if err := c.db.UpdateItemCurrentBid(ctx, event.ItemID, event.Amount, event.UserID); err != nil {
		return fmt.Errorf("failed to update item: %w", err)
	}

	return nil
}

// Close closes the NATS connection
func (c *NATSConsumer) Close() error {
	if c.sub != nil {
		c.sub.Unsubscribe()
	}
	c.conn.Close()
	return nil
}
