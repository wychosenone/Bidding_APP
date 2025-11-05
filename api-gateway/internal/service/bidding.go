package service

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/aaronwang/bidding-app/shared/models"
	"github.com/google/uuid"
	"github.com/nats-io/nats.go"

	redisClient "github.com/aaronwang/bidding-app/api-gateway/internal/redis"
)

// BiddingService handles the business logic for bidding operations
type BiddingService struct {
	redis *redisClient.Client
	nats  *nats.Conn
}

// NewBiddingService creates a new bidding service
func NewBiddingService(redis *redisClient.Client, natsConn *nats.Conn) *BiddingService {
	return &BiddingService{
		redis: redis,
		nats:  natsConn,
	}
}

// PlaceBid handles the complete bid placement workflow:
// 1. Validate bid (business rules)
// 2. Attempt atomic update in Redis
// 3. If successful, publish to Redis Pub/Sub for real-time broadcast
// 4. If successful, publish to NATS for archival
func (s *BiddingService) PlaceBid(ctx context.Context, itemID string, req *models.BidRequest) (*models.BidResponse, error) {
	// Business validation
	if req.Amount <= 0 {
		return &models.BidResponse{
			Success: false,
			Message: "Bid amount must be positive",
		}, nil
	}

	// Attempt atomic bid in Redis
	result, err := s.redis.PlaceBid(ctx, itemID, req.UserID, req.Amount)
	if err != nil {
		return nil, fmt.Errorf("failed to place bid: %w", err)
	}

	// Check if bid was successful
	if !result.Success {
		return &models.BidResponse{
			Success:    false,
			Message:    fmt.Sprintf("Bid too low. Current highest bid is $%.2f", result.CurrentBid),
			CurrentBid: result.CurrentBid,
			YourBid:    req.Amount,
			IsHighest:  false,
		}, nil
	}

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

	// Publish to Redis Pub/Sub for real-time broadcast (non-blocking, best effort)
	// Even if this fails, the bid is still recorded in Redis
	go func() {
		pubCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()
		if err := s.redis.PublishBidEvent(pubCtx, itemID, bidEvent); err != nil {
			// Log error but don't fail the bid
			fmt.Printf("Warning: failed to publish bid event to Redis Pub/Sub: %v\n", err)
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

// publishToArchivalQueue publishes bid event to NATS for archival persistence
// This is fire-and-forget to keep the write path fast
func (s *BiddingService) publishToArchivalQueue(event *models.BidEvent) error {
	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// Publish to NATS subject
	// Subject naming: "bid.events.{itemID}" allows for future routing/filtering
	subject := fmt.Sprintf("bid.events.%s", event.ItemID)

	if err := s.nats.Publish(subject, data); err != nil {
		return fmt.Errorf("failed to publish to NATS: %w", err)
	}

	return nil
}
