package service

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/aaronwang/bidding-app/shared/models"
	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"

	redisClient "github.com/aaronwang/bidding-app/api-gateway/internal/redis"
)

// BiddingService handles the business logic for bidding operations
type BiddingService struct {
	redis      *redisClient.Client
	nats       *nats.Conn
	js         jetstream.JetStream // JetStream context for persistent messaging
	priceCache sync.Map            // Local cache for current bid prices (itemID -> float64)
}

// NewBiddingService creates a new bidding service
func NewBiddingService(redis *redisClient.Client, natsConn *nats.Conn) (*BiddingService, error) {
	// Create JetStream context
	js, err := jetstream.New(natsConn)
	if err != nil {
		return nil, fmt.Errorf("failed to create JetStream context: %w", err)
	}

	// Ensure the stream exists (create if not)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	_, err = js.CreateOrUpdateStream(ctx, jetstream.StreamConfig{
		Name:        "BID_EVENTS",
		Description: "Stream for bid events archival",
		Subjects:    []string{"bid.events.*"},
		Storage:     jetstream.FileStorage,  // Persistent storage
		Retention:   jetstream.WorkQueuePolicy, // Each message consumed once
		MaxAge:      24 * time.Hour,          // Keep messages for 24 hours
		Replicas:    1,                        // Single replica for dev
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create/update stream: %w", err)
	}
	fmt.Println("[JETSTREAM] Stream 'BID_EVENTS' ready")

	return &BiddingService{
		redis: redis,
		nats:  natsConn,
		js:    js,
	}, nil
}

// PlaceBid handles the complete bid placement workflow:
// 1. Validate bid (business rules)
// 2. Pre-filter using local cache (fast rejection)
// 3. Attempt atomic update in Redis
// 4. If successful, publish to Redis Pub/Sub for real-time broadcast
// 5. If successful, publish to NATS for archival
func (s *BiddingService) PlaceBid(ctx context.Context, itemID string, req *models.BidRequest) (*models.BidResponse, error) {
	// Business validation
	if req.Amount <= 0 {
		return &models.BidResponse{
			Success: false,
			Message: "Bid amount must be positive",
		}, nil
	}

	// Pre-filter: Check local cache before calling Redis
	// This reduces Redis load by quickly rejecting bids that are obviously too low
	if cachedPrice, ok := s.priceCache.Load(itemID); ok {
		cachedValue := cachedPrice.(float64)
		if req.Amount <= cachedValue {
			// Bid appears too low based on cache, but verify with Redis
			// This prevents stale cache from incorrectly rejecting valid bids
			actualPrice, _, err := s.redis.GetItemBid(ctx, itemID)
			if err != nil {
				// Redis error, proceed with cache value
				fmt.Printf("[CACHE-FILTER] Redis error, using cached price: %v\n", err)
				actualPrice = cachedValue
			} else if actualPrice != cachedValue {
				// Cache was stale! Update it with actual Redis value
				fmt.Printf("[CACHE-SYNC] Cache mismatch - cached: $%.2f, actual: $%.2f, updating cache\n",
					cachedValue, actualPrice)
				s.priceCache.Store(itemID, actualPrice)
			}

			// Final decision based on actual Redis price
			if req.Amount <= actualPrice {
				fmt.Printf("[CACHE-FILTER] Rejected bid $%.2f (current price: $%.2f) for item %s\n",
					req.Amount, actualPrice, itemID)
				return &models.BidResponse{
					Success:    false,
					Message:    fmt.Sprintf("Bid too low. Current highest bid is $%.2f", actualPrice),
					CurrentBid: actualPrice,
					YourBid:    req.Amount,
					IsHighest:  false,
				}, nil
			}
			// Bid is actually higher than Redis price, continue to atomic update
		}
	}

	// Passed pre-filter: attempt atomic bid in Redis
	result, err := s.redis.PlaceBid(ctx, itemID, req.UserID, req.Amount)
	if err != nil {
		return nil, fmt.Errorf("failed to place bid: %w", err)
	}

	// Check if bid was successful
	if !result.Success {
		// Update cache with current price (even on failure, to keep cache fresh)
		s.priceCache.Store(itemID, result.CurrentBid)

		return &models.BidResponse{
			Success:    false,
			Message:    fmt.Sprintf("Bid too low. Current highest bid is $%.2f", result.CurrentBid),
			CurrentBid: result.CurrentBid,
			YourBid:    req.Amount,
			IsHighest:  false,
		}, nil
	}

	// Update cache with new successful bid
	s.priceCache.Store(itemID, req.Amount)
	fmt.Printf("[CACHE-UPDATE] Updated cache for item %s: $%.2f\n", itemID, req.Amount)

	// Bid successful! Create event for downstream systems
	bidEvent := &models.BidEvent{
		EventID:     uuid.New().String(),
		ItemID:      itemID,
		BidID:       uuid.New().String(),
		UserID:      req.UserID,
		Amount:      req.Amount,
		PreviousBid: result.PreviousBid,
		Timestamp:   time.Now().UTC(),
	}

	// Publish to NATS for real-time broadcast (non-blocking, best effort)
	// NATS is much faster than Redis Pub/Sub (~1ms vs ~40ms)
	go func() {
		eventJSON, err := json.Marshal(bidEvent)
		if err != nil {
			fmt.Printf("Warning: failed to marshal bid event for NATS: %v\n", err)
			return
		}

		subject := fmt.Sprintf("bid_events.%s", itemID)
		if err := s.nats.Publish(subject, eventJSON); err != nil {
			fmt.Printf("Warning: failed to publish bid event to NATS: %v\n", err)
		} else {
			fmt.Printf("[NATS] Published bid event to subject: %s\n", subject)
		}
	}()

	// Publish to NATS for archival (async, non-blocking)
	// This demonstrates the key architectural principle: write path doesn't depend on archival
	go func() {
		if err := s.publishToArchivalQueue(bidEvent); err != nil {
			// Log error but don't fail the bid
			fmt.Printf("Warning: failed to publish to archival queue: %v\n", err)
		}
	}()

	return &models.BidResponse{
		Success:    true,
		Message:    "Bid placed successfully!",
		CurrentBid: req.Amount,
		YourBid:    req.Amount,
		IsHighest:  true,
		EventID:    bidEvent.EventID,
	}, nil
}

// GetItemBid retrieves the current highest bid for an item
func (s *BiddingService) GetItemBid(ctx context.Context, itemID string) (*models.Item, error) {
	bid, bidderID, err := s.redis.GetItemBid(ctx, itemID)
	if err != nil {
		return nil, fmt.Errorf("failed to get item bid: %w", err)
	}

	// In a real system, you'd fetch full item details from a cache or database
	// For this demo, we return minimal info
	return &models.Item{
		ID:              itemID,
		CurrentBid:      bid,
		HighestBidderID: bidderID,
		Status:          models.ItemStatusActive,
	}, nil
}

// publishToArchivalQueue publishes bid event to NATS JetStream for archival persistence
// Uses JetStream for guaranteed delivery (at-least-once semantics)
func (s *BiddingService) publishToArchivalQueue(event *models.BidEvent) error {
	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// Publish to JetStream subject
	// Subject naming: "bid.events.{itemID}" allows for future routing/filtering
	subject := fmt.Sprintf("bid.events.%s", event.ItemID)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// JetStream Publish waits for acknowledgment from server
	// This ensures the message is persisted before returning
	ack, err := s.js.Publish(ctx, subject, data)
	if err != nil {
		return fmt.Errorf("failed to publish to JetStream: %w", err)
	}

	fmt.Printf("[JETSTREAM] Published to %s, seq=%d\n", subject, ack.Sequence)
	return nil
}
