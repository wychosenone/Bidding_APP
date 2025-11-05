package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/aaronwang/bidding-app/api-gateway/internal/handlers"
	redisClient "github.com/aaronwang/bidding-app/api-gateway/internal/redis"
	"github.com/aaronwang/bidding-app/api-gateway/internal/service"
	"github.com/aaronwang/bidding-app/shared/config"
	"github.com/nats-io/nats.go"
)

func main() {
	fmt.Println("Starting API Gateway...")

	// Load configuration from environment variables
	cfg := loadConfig()

	// Initialize Redis client
	fmt.Println("Connecting to Redis...")
	redis, err := redisClient.NewClient(cfg.RedisAddr, cfg.RedisPassword, cfg.RedisDB)
	if err != nil {
		fmt.Printf("Failed to connect to Redis: %v\n", err)
		os.Exit(1)
	}
	defer redis.Close()
	fmt.Println("Connected to Redis")

	// Initialize NATS connection
	fmt.Println("Connecting to NATS...")
	natsConn, err := nats.Connect(cfg.NatsURL)
	if err != nil {
		fmt.Printf("Failed to connect to NATS: %v\n", err)
		os.Exit(1)
	}
	defer natsConn.Close()
	fmt.Println("Connected to NATS")

	// Initialize services
	biddingService := service.NewBiddingService(redis, natsConn)

	// Initialize HTTP handlers
	handler := handlers.NewHandler(biddingService)
	router := handler.SetupRoutes()

	// Create HTTP server
	server := &http.Server{
		Addr:         cfg.ServerAddr,
		Handler:      router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start server in a goroutine
	go func() {
		fmt.Printf("API Gateway listening on %s\n", cfg.ServerAddr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			fmt.Printf("Server error: %v\n", err)
			os.Exit(1)
		}
	}()

	// Wait for interrupt signal for graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	fmt.Println("\nShutting down server...")

	// Graceful shutdown with 30 second timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
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
	NatsURL       string
}

// loadConfig loads configuration from environment variables
func loadConfig() *Config {
	return &Config{
		ServerAddr:    config.GetEnv("SERVER_ADDR", ":8080"),
		RedisAddr:     config.GetEnv("REDIS_ADDR", "localhost:6379"),
		RedisPassword: config.GetEnv("REDIS_PASSWORD", ""),
		RedisDB:       config.GetEnvInt("REDIS_DB", 0),
		NatsURL:       config.GetEnv("NATS_URL", "nats://localhost:4222"),
	}
}
