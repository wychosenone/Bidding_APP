package models

import "time"

// Item represents an auction item
type Item struct {
	ID          string    `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	StartPrice  float64   `json:"start_price"`
	CurrentBid  float64   `json:"current_bid"`
	HighestBidderID string `json:"highest_bidder_id,omitempty"`
	Status      string    `json:"status"` // "active", "closed"
	StartTime   time.Time `json:"start_time"`
	EndTime     time.Time `json:"end_time"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// ItemStatus constants
const (
	ItemStatusActive = "active"
	ItemStatusClosed = "closed"
)
