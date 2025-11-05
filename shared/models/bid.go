package models

import "time"

// Bid represents a single bid on an item
type Bid struct {
	ID        string    `json:"id"`
	ItemID    string    `json:"item_id"`
	UserID    string    `json:"user_id"`
	Amount    float64   `json:"amount"`
	Timestamp time.Time `json:"timestamp"`
	Status    string    `json:"status"` // "accepted", "rejected"
}

// BidStatus constants
const (
	BidStatusAccepted = "accepted"
	BidStatusRejected = "rejected"
)

// BidRequest represents the incoming bid request from API
type BidRequest struct {
	UserID string  `json:"user_id" binding:"required"`
	Amount float64 `json:"amount" binding:"required,gt=0"`
}

// BidResponse represents the API response after placing a bid
type BidResponse struct {
	Success     bool    `json:"success"`
	Message     string  `json:"message"`
	CurrentBid  float64 `json:"current_bid"`
	YourBid     float64 `json:"your_bid"`
	IsHighest   bool    `json:"is_highest"`
}

// BidEvent represents an event that gets published when a bid is accepted
// This is sent to:
// 1. Redis Pub/Sub (for real-time WebSocket broadcast)
// 2. NATS/Kafka (for archival to PostgreSQL)
type BidEvent struct {
	EventID     string    `json:"event_id"`
	ItemID      string    `json:"item_id"`
	BidID       string    `json:"bid_id"`
	UserID      string    `json:"user_id"`
	Amount      float64   `json:"amount"`
	PreviousBid float64   `json:"previous_bid"`
	Timestamp   time.Time `json:"timestamp"`
}
