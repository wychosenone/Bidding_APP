package database

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/aaronwang/bidding-app/shared/models"
	_ "github.com/lib/pq"
)

// PostgresClient wraps the PostgreSQL database connection
type PostgresClient struct {
	db *sql.DB
}

// NewPostgresClient creates a new PostgreSQL client
func NewPostgresClient(connStr string) (*PostgresClient, error) {
	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// Configure connection pool
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	return &PostgresClient{db: db}, nil
}

// InitSchema creates the necessary database tables
func (c *PostgresClient) InitSchema(ctx context.Context) error {
	schema := `
	CREATE TABLE IF NOT EXISTS items (
		id VARCHAR(255) PRIMARY KEY,
		name VARCHAR(255) NOT NULL,
		description TEXT,
		start_price DECIMAL(10, 2) NOT NULL,
		current_bid DECIMAL(10, 2) DEFAULT 0,
		highest_bidder_id VARCHAR(255),
		status VARCHAR(50) DEFAULT 'active',
		start_time TIMESTAMP NOT NULL,
		end_time TIMESTAMP NOT NULL,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);

	CREATE TABLE IF NOT EXISTS bids (
		id VARCHAR(255) PRIMARY KEY,
		item_id VARCHAR(255) NOT NULL,
		user_id VARCHAR(255) NOT NULL,
		amount DECIMAL(10, 2) NOT NULL,
		status VARCHAR(50) DEFAULT 'accepted',
		timestamp TIMESTAMP NOT NULL,
		created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
	);

	CREATE INDEX IF NOT EXISTS idx_bids_item_id ON bids(item_id);
	CREATE INDEX IF NOT EXISTS idx_bids_user_id ON bids(user_id);
	CREATE INDEX IF NOT EXISTS idx_bids_timestamp ON bids(timestamp);
	`

	_, err := c.db.ExecContext(ctx, schema)
	if err != nil {
		return fmt.Errorf("failed to create schema: %w", err)
	}

	return nil
}

// InsertBid inserts a bid record into the database
func (c *PostgresClient) InsertBid(ctx context.Context, event *models.BidEvent) error {
	query := `
		INSERT INTO bids (id, item_id, user_id, amount, timestamp, status)
		VALUES ($1, $2, $3, $4, $5, $6)
		ON CONFLICT (id) DO NOTHING
	`

	_, err := c.db.ExecContext(
		ctx,
		query,
		event.BidID,
		event.ItemID,
		event.UserID,
		event.Amount,
		event.Timestamp,
		models.BidStatusAccepted,
	)

	if err != nil {
		return fmt.Errorf("failed to insert bid: %w", err)
	}

	return nil
}

// UpdateItemCurrentBid updates the current bid for an item
func (c *PostgresClient) UpdateItemCurrentBid(ctx context.Context, itemID string, amount float64, bidderID string) error {
	query := `
		UPDATE items
		SET current_bid = $1,
		    highest_bidder_id = $2,
		    updated_at = CURRENT_TIMESTAMP
		WHERE id = $3
	`

	result, err := c.db.ExecContext(ctx, query, amount, bidderID, itemID)
	if err != nil {
		return fmt.Errorf("failed to update item: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		// Item doesn't exist, create it (in a real system, items would be pre-created)
		return c.createItemIfNotExists(ctx, itemID)
	}

	return nil
}

// createItemIfNotExists creates a placeholder item if it doesn't exist
func (c *PostgresClient) createItemIfNotExists(ctx context.Context, itemID string) error {
	query := `
		INSERT INTO items (id, name, description, start_price, start_time, end_time)
		VALUES ($1, $2, $3, $4, $5, $6)
		ON CONFLICT (id) DO NOTHING
	`

	now := time.Now()
	_, err := c.db.ExecContext(
		ctx,
		query,
		itemID,
		fmt.Sprintf("Item %s", itemID),
		"Auto-generated item",
		0.0,
		now,
		now.Add(24*time.Hour),
	)

	return err
}

// GetBidHistory retrieves the bid history for an item
func (c *PostgresClient) GetBidHistory(ctx context.Context, itemID string, limit int) ([]*models.Bid, error) {
	query := `
		SELECT id, item_id, user_id, amount, timestamp, status
		FROM bids
		WHERE item_id = $1
		ORDER BY timestamp DESC
		LIMIT $2
	`

	rows, err := c.db.QueryContext(ctx, query, itemID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query bids: %w", err)
	}
	defer rows.Close()

	var bids []*models.Bid
	for rows.Next() {
		bid := &models.Bid{}
		err := rows.Scan(
			&bid.ID,
			&bid.ItemID,
			&bid.UserID,
			&bid.Amount,
			&bid.Timestamp,
			&bid.Status,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan bid: %w", err)
		}
		bids = append(bids, bid)
	}

	return bids, nil
}

// Close closes the database connection
func (c *PostgresClient) Close() error {
	return c.db.Close()
}
