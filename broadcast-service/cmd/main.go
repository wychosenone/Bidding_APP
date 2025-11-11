package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/nats-io/nats.go"

	wsHandler "github.com/aaronwang/bidding-app/broadcast-service/internal/websocket"
	"github.com/aaronwang/bidding-app/shared/config"
	"github.com/aaronwang/bidding-app/shared/models"
)

func main() {
	fmt.Println("Starting Broadcast Service...")

	// Load configuration
	cfg := loadConfig()

	// Connect to NATS
	fmt.Println("Connecting to NATS...")
	natsConn, err := nats.Connect(cfg.NatsURL)
	if err != nil {
		fmt.Printf("Failed to connect to NATS: %v\n", err)
		os.Exit(1)
	}
	defer natsConn.Close()
	fmt.Println("Connected to NATS")

	// Initialize WebSocket manager
	wsManager := wsHandler.NewManager()

	// Start WebSocket manager (handles connection lifecycle)
	go wsManager.Run()
	fmt.Println("WebSocket manager started")

	// Subscribe to all bid events using NATS wildcard
	// bid_events.* matches bid_events.item1, bid_events.item2, etc.
	fmt.Println("Subscribing to NATS bid events...")
	_, err = natsConn.Subscribe("bid_events.*", func(msg *nats.Msg) {
		forwardStart := time.Now()

		// Parse the bid event
		var bidEvent models.BidEvent
		if err := json.Unmarshal(msg.Data, &bidEvent); err != nil {
			fmt.Printf("Error unmarshaling bid event: %v\n", err)
			return
		}

		// Extract itemID from subject (bid_events.{itemID})
		// Subject format: "bid_events.item123"
		itemID := bidEvent.ItemID

		// Direct broadcast to all WebSocket clients watching this item
		wsManager.BroadcastDirect(itemID, msg.Data)

		forwardElapsed := time.Since(forwardStart).Microseconds()
		fmt.Printf("[NATS→WS] Forwarded bid for item %s in %dµs\n", itemID, forwardElapsed)
	})
	if err != nil {
		fmt.Printf("Failed to subscribe to NATS: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("Subscribed to bid events via NATS")

	// Initialize HTTP server for WebSocket connections
	handler := wsHandler.NewHandler(wsManager)
	router := handler.SetupRoutes()

	server := &http.Server{
		Addr:         cfg.ServerAddr,
		Handler:      router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start HTTP server in goroutine
	go func() {
		fmt.Printf("Broadcast Service listening on %s\n", cfg.ServerAddr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Printf("Server error: %v\n", err)
			os.Exit(1)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	fmt.Println("\nShutting down server...")

	// Graceful shutdown
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := server.Shutdown(shutdownCtx); err != nil {
		fmt.Printf("Server forced to shutdown: %v\n", err)
	}

	fmt.Println("Server stopped gracefully")
}

// Config holds application configuration
type Config struct {
	ServerAddr string
	NatsURL    string
}

// loadConfig loads configuration from environment variables
func loadConfig() *Config {
	return &Config{
		ServerAddr: config.GetEnv("SERVER_ADDR", ":8081"),
		NatsURL:    config.GetEnv("NATS_URL", "nats://localhost:4222"),
	}
}
