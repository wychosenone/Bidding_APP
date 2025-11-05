package handlers

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/aaronwang/bidding-app/api-gateway/internal/service"
	"github.com/aaronwang/bidding-app/shared/models"
	"github.com/gorilla/mux"
)

// Handler contains HTTP request handlers
type Handler struct {
	biddingService *service.BiddingService
}

// NewHandler creates a new HTTP handler
func NewHandler(biddingService *service.BiddingService) *Handler {
	return &Handler{
		biddingService: biddingService,
	}
}

// SetupRoutes configures all HTTP routes
func (h *Handler) SetupRoutes() *mux.Router {
	router := mux.NewRouter()

	// Health check
	router.HandleFunc("/health", h.HealthCheck).Methods("GET")

	// API routes
	api := router.PathPrefix("/api/v1").Subrouter()
	api.HandleFunc("/items/{id}", h.GetItem).Methods("GET")
	api.HandleFunc("/items/{id}/bid", h.PlaceBid).Methods("POST")

	// Middleware
	router.Use(loggingMiddleware)
	router.Use(corsMiddleware)

	return router
}

// HealthCheck returns service health status
func (h *Handler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	respondJSON(w, http.StatusOK, map[string]string{
		"status":  "healthy",
		"service": "api-gateway",
		"time":    time.Now().UTC().Format(time.RFC3339),
	})
}

// GetItem retrieves current bid information for an item
func (h *Handler) GetItem(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	itemID := vars["id"]

	if itemID == "" {
		respondError(w, http.StatusBadRequest, "Item ID is required")
		return
	}

	ctx := r.Context()
	item, err := h.biddingService.GetItemBid(ctx, itemID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "Failed to retrieve item")
		return
	}

	respondJSON(w, http.StatusOK, item)
}

// PlaceBid handles bid placement requests
func (h *Handler) PlaceBid(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	itemID := vars["id"]

	if itemID == "" {
		respondError(w, http.StatusBadRequest, "Item ID is required")
		return
	}

	// Parse request body
	var bidReq models.BidRequest
	if err := json.NewDecoder(r.Body).Decode(&bidReq); err != nil {
		respondError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Validate request
	if bidReq.UserID == "" {
		respondError(w, http.StatusBadRequest, "User ID is required")
		return
	}
	if bidReq.Amount <= 0 {
		respondError(w, http.StatusBadRequest, "Bid amount must be positive")
		return
	}

	// Place bid
	ctx := r.Context()
	response, err := h.biddingService.PlaceBid(ctx, itemID, &bidReq)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "Failed to place bid")
		return
	}

	// Return appropriate status code
	statusCode := http.StatusOK
	if response.Success {
		statusCode = http.StatusCreated
	}

	respondJSON(w, statusCode, response)
}

// respondJSON sends a JSON response
func respondJSON(w http.ResponseWriter, statusCode int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(data)
}

// respondError sends an error response
func respondError(w http.ResponseWriter, statusCode int, message string) {
	respondJSON(w, statusCode, map[string]string{
		"error": message,
	})
}

// loggingMiddleware logs all HTTP requests
func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		duration := time.Since(start)

		// In production, use proper structured logging (e.g., zerolog, zap)
		println(time.Now().Format(time.RFC3339), r.Method, r.RequestURI, duration.String())
	})
}

// corsMiddleware adds CORS headers (for development)
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}
