package websocket

import (
	"fmt"
	"net/http"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	// Allow all origins for development (use proper CORS in production)
	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

// Handler handles WebSocket connections
type Handler struct {
	manager *Manager
}

// NewHandler creates a new WebSocket handler
func NewHandler(manager *Manager) *Handler {
	return &Handler{
		manager: manager,
	}
}

// SetupRoutes configures WebSocket routes
func (h *Handler) SetupRoutes() *mux.Router {
	router := mux.NewRouter()

	// WebSocket endpoint: /ws/items/{id}
	router.HandleFunc("/ws/items/{id}", h.HandleWebSocket)

	// Health check
	router.HandleFunc("/health", h.HealthCheck).Methods("GET")

	// Stats endpoint
	router.HandleFunc("/stats/items/{id}", h.GetStats).Methods("GET")

	return router
}

// HandleWebSocket upgrades HTTP connection to WebSocket
func (h *Handler) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	itemID := vars["id"]

	if itemID == "" {
		http.Error(w, "Item ID is required", http.StatusBadRequest)
		return
	}

	// Upgrade connection to WebSocket
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		fmt.Printf("Failed to upgrade connection: %v\n", err)
		return
	}

	// Create client
	client := &Client{
		ID:     uuid.New().String(),
		ItemID: itemID,
		Conn:   conn,
		Send:   make(chan []byte, 256), // Buffered channel for non-blocking sends
	}

	// Register client with manager
	h.manager.RegisterClient(client)

	// Start reading from client (handles disconnects)
	client.StartReadPump(h.manager.unregister)

	// Send welcome message
	welcomeMsg := fmt.Sprintf(`{"type":"connected","itemId":"%s","clientId":"%s"}`, itemID, client.ID)
	client.Send <- []byte(welcomeMsg)
}

// HealthCheck returns service health
func (h *Handler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"status":"healthy","service":"broadcast-service"}`)
}

// GetStats returns statistics for an item
func (h *Handler) GetStats(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	itemID := vars["id"]

	count := h.manager.GetSubscriberCount(itemID)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"itemId":"%s","subscribers":%d}`, itemID, count)
}
