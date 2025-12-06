package consumer

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/aaronwang/bidding-app/archival-worker/internal/database"
	"github.com/aaronwang/bidding-app/shared/models"
	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
)

// NATSConsumer consumes bid events from NATS JetStream and persists to database
type NATSConsumer struct {
	conn     *nats.Conn
	js       jetstream.JetStream
	consumer jetstream.Consumer
	db       *database.PostgresClient
}

// NewNATSConsumer creates a new NATS JetStream consumer
func NewNATSConsumer(natsURL string, db *database.PostgresClient) (*NATSConsumer, error) {
	conn, err := nats.Connect(natsURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to NATS: %w", err)
	}

	// Create JetStream context
	js, err := jetstream.New(conn)
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to create JetStream context: %w", err)
	}

	return &NATSConsumer{
		conn: conn,
		js:   js,
		db:   db,
	}, nil
}

// Start begins consuming messages from NATS JetStream
func (c *NATSConsumer) Start(ctx context.Context) error {
	// Get or create the consumer for the BID_EVENTS stream
	consumer, err := c.js.CreateOrUpdateConsumer(ctx, "BID_EVENTS", jetstream.ConsumerConfig{
		Name:          "archival-worker",
		Durable:       "archival-worker", // Durable consumer survives restarts
		FilterSubject: "bid.events.*",
		AckPolicy:     jetstream.AckExplicitPolicy, // Manual acknowledgment
		AckWait:       30 * time.Second,            // Redeliver if not acked in 30s
		MaxDeliver:    5,                           // Max 5 delivery attempts
		DeliverPolicy: jetstream.DeliverAllPolicy,  // Start from beginning
	})
	if err != nil {
		return fmt.Errorf("failed to create consumer: %w", err)
	}
	c.consumer = consumer
	fmt.Println("[JETSTREAM] Consumer 'archival-worker' ready on stream 'BID_EVENTS'")

	// Consume messages
	msgs, err := consumer.Messages()
	if err != nil {
		return fmt.Errorf("failed to get message iterator: %w", err)
	}

	fmt.Println("[JETSTREAM] Starting message consumption...")

	for {
		select {
		case <-ctx.Done():
			msgs.Stop()
			return nil
		default:
			msg, err := msgs.Next()
			if err != nil {
				if ctx.Err() != nil {
					return nil // Context cancelled, clean shutdown
				}
				fmt.Printf("[JETSTREAM] Error getting next message: %v\n", err)
				continue
			}
			c.handleMessage(ctx, msg)
		}
	}
}

// handleMessage processes a single bid event message from JetStream
func (c *NATSConsumer) handleMessage(ctx context.Context, msg jetstream.Msg) {
	// Parse the event
	var event models.BidEvent
	if err := json.Unmarshal(msg.Data(), &event); err != nil {
		fmt.Printf("[JETSTREAM] Failed to unmarshal event: %v\n", err)
		// Nak with delay to retry later
		msg.NakWithDelay(5 * time.Second)
		return
	}

	// Create a timeout context for database operations
	dbCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	// Persist to database
	updated, err := c.persistBidEvent(dbCtx, &event)
	if err != nil {
		fmt.Printf("[JETSTREAM] Failed to persist bid event %s: %v\n", event.EventID, err)
		// Nak with delay to retry later
		msg.NakWithDelay(5 * time.Second)
		return
	}

	// Get message metadata for logging
	meta, _ := msg.Metadata()
	if updated {
		fmt.Printf("[JETSTREAM] Persisted bid event %s (item: %s, user: %s, amount: $%.2f, seq: %d) - UPDATED current_bid\n",
			event.EventID, event.ItemID, event.UserID, event.Amount, meta.Sequence.Stream)
	} else {
		fmt.Printf("[JETSTREAM] Persisted bid event %s (item: %s, user: %s, amount: $%.2f, seq: %d) - SKIPPED (higher bid exists)\n",
			event.EventID, event.ItemID, event.UserID, event.Amount, meta.Sequence.Stream)
	}

	// Acknowledge successful processing
	if err := msg.Ack(); err != nil {
		fmt.Printf("[JETSTREAM] Failed to ack message: %v\n", err)
	}
}

// persistBidEvent writes the bid event to PostgreSQL
// Returns (updated bool, error) - updated indicates if item's current_bid was changed
func (c *NATSConsumer) persistBidEvent(ctx context.Context, event *models.BidEvent) (bool, error) {
	// Insert bid record (always insert - this is the audit trail)
	if err := c.db.InsertBid(ctx, event); err != nil {
		return false, fmt.Errorf("failed to insert bid: %w", err)
	}

	// Update item's current bid (conditional - only if this bid is higher)
	updated, err := c.db.UpdateItemCurrentBid(ctx, event.ItemID, event.Amount, event.UserID)
	if err != nil {
		return false, fmt.Errorf("failed to update item: %w", err)
	}

	return updated, nil
}

// Close closes the NATS connection
func (c *NATSConsumer) Close() error {
	c.conn.Close()
	return nil
}
