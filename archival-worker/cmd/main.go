package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"github.com/aaronwang/bidding-app/archival-worker/internal/consumer"
	"github.com/aaronwang/bidding-app/archival-worker/internal/database"
	"github.com/aaronwang/bidding-app/shared/config"
)

func main() {
	fmt.Println("Starting Archival Worker...")

	// Load configuration
	cfg := loadConfig()

	// Initialize PostgreSQL client
	fmt.Println("Connecting to PostgreSQL...")
	db, err := database.NewPostgresClient(cfg.PostgresURL)
	if err != nil {
		fmt.Printf("Failed to connect to PostgreSQL: %v\n", err)
		os.Exit(1)
	}
	defer db.Close()
	fmt.Println("Connected to PostgreSQL")

	// Initialize database schema
	fmt.Println("Initializing database schema...")
	ctx := context.Background()
	if err := db.InitSchema(ctx); err != nil {
		fmt.Printf("Failed to initialize schema: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("Database schema initialized")

	// Initialize NATS consumer
	fmt.Println("Connecting to NATS...")
	natsConsumer, err := consumer.NewNATSConsumer(cfg.NatsURL, db)
	if err != nil {
		fmt.Printf("Failed to create NATS consumer: %v\n", err)
		os.Exit(1)
	}
	defer natsConsumer.Close()
	fmt.Println("Connected to NATS")

	// Create context for graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Start consuming messages
	go func() {
		fmt.Println("Starting to consume bid events from NATS...")
		if err := natsConsumer.Start(ctx); err != nil {
			fmt.Printf("Consumer error: %v\n", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	fmt.Println("\nShutting down worker...")
	cancel()

	fmt.Println("Worker stopped gracefully")
}

// Config holds application configuration
type Config struct {
	PostgresURL string
	NatsURL     string
}

// loadConfig loads configuration from environment variables
func loadConfig() *Config {
	return &Config{
		PostgresURL: config.GetEnv("POSTGRES_URL", "postgres://bidding:password@localhost:5432/bidding?sslmode=disable"),
		NatsURL:     config.GetEnv("NATS_URL", "nats://localhost:4222"),
	}
}
