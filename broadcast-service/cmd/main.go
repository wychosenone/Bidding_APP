package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	redisClient "github.com/aaronwang/bidding-app/broadcast-service/internal/redis"
	wsHandler "github.com/aaronwang/bidding-app/broadcast-service/internal/websocket"
	"github.com/aaronwang/bidding-app/shared/config"
)

func main() {
	fmt.Println("Starting Broadcast Service...")

	// Load configuration
	cfg := loadConfig()

	// Initialize Redis subscriber
	fmt.Println("Connecting to Redis...")
	subscriber, err := redisClient.NewSubscriber(cfg.RedisAddr, cfg.RedisPassword, cfg.RedisDB)
	if err != nil {
		fmt.Printf("Failed to connect to Redis: %v\n", err)
		os.Exit(1)
	}
	defer subscriber.Close()
	fmt.Println("Connected to Redis")

	// Subscribe to all bid events using pattern matching
	ctx := context.Background()
	if err := subscriber.SubscribeToPattern(ctx, "bid_events:*"); err != nil {
		fmt.Printf("Failed to subscribe to Redis channels: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("Subscribed to bid events")

	// Initialize WebSocket manager
	wsManager := wsHandler.NewManager()

	// Start WebSocket manager (handles connection lifecycle)
	go wsManager.Run()
	fmt.Println("WebSocket manager started")

	// Create a channel for Redis messages
	messageChan := make(chan *redisClient.Message, 256)

	// Start Redis subscriber in a goroutine
	go func() {
		fmt.Println("Listening for Redis Pub/Sub messages...")
		if err := subscriber.Listen(ctx, messageChan); err != nil {
			fmt.Printf("Redis listener error: %v\n", err)
		}
	}()

	// Start message forwarder (Redis -> WebSocket)
	// This is the key integration point!
	go func() {
		fmt.Println("Starting message forwarder (Redis Pub/Sub -> WebSocket)...")
		for msg := range messageChan {
			// Forward Redis Pub/Sub message to WebSocket clients
			wsManager.Broadcast(msg.ItemID, []byte(msg.Payload))
		}
	}()

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
	ServerAddr    string
	RedisAddr     string
	RedisPassword string
	RedisDB       int
}

// loadConfig loads configuration from environment variables
func loadConfig() *Config {
	return &Config{
		ServerAddr:    config.GetEnv("SERVER_ADDR", ":8081"),
		RedisAddr:     config.GetEnv("REDIS_ADDR", "localhost:6379"),
		RedisPassword: config.GetEnv("REDIS_PASSWORD", ""),
		RedisDB:       config.GetEnvInt("REDIS_DB", 0),
	}
}
