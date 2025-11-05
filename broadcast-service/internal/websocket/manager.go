package websocket

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// Manager manages all WebSocket connections
type Manager struct {
	// Map of itemID -> set of connections watching that item
	// Using sync.Map for concurrent access
	subscribers sync.Map // map[string]map[*Client]bool

	// Channels for managing connections
	register   chan *Client
	unregister chan *Client
	broadcast  chan *BroadcastMessage

	// Mutex for thread-safe operations
	mu sync.RWMutex
}

// Client represents a WebSocket client connection
type Client struct {
	ID     string
	ItemID string
	Conn   *websocket.Conn
	Send   chan []byte
}

// BroadcastMessage represents a message to broadcast to all clients watching an item
type BroadcastMessage struct {
	ItemID  string
	Payload []byte
}

// NewManager creates a new WebSocket manager
func NewManager() *Manager {
	return &Manager{
		register:   make(chan *Client),
		unregister: make(chan *Client),
		broadcast:  make(chan *BroadcastMessage, 256), // Buffered for high throughput
	}
}

// Run starts the manager's main loop
// This should run in a goroutine
func (m *Manager) Run() {
	for {
		select {
		case client := <-m.register:
			m.registerClient(client)

		case client := <-m.unregister:
			m.unregisterClient(client)

		case message := <-m.broadcast:
			m.broadcastToItem(message.ItemID, message.Payload)
		}
	}
}

// RegisterClient adds a client to the manager
func (m *Manager) RegisterClient(client *Client) {
	m.register <- client
}

// UnregisterClient removes a client from the manager
func (m *Manager) UnregisterClient(client *Client) {
	m.unregister <- client
}

// Broadcast sends a message to all clients watching an item
func (m *Manager) Broadcast(itemID string, payload []byte) {
	m.broadcast <- &BroadcastMessage{
		ItemID:  itemID,
		Payload: payload,
	}
}

// registerClient adds a client to the subscribers map
func (m *Manager) registerClient(client *Client) {
	// Get or create the subscriber set for this item
	subscribers, _ := m.subscribers.LoadOrStore(client.ItemID, &sync.Map{})
	subscriberMap := subscribers.(*sync.Map)

	// Add client to the set
	subscriberMap.Store(client, true)

	fmt.Printf("Client %s subscribed to item %s\n", client.ID, client.ItemID)

	// Start goroutine to handle writes for this client
	go client.writePump()
}

// unregisterClient removes a client and closes its connection
func (m *Manager) unregisterClient(client *Client) {
	if subscribers, ok := m.subscribers.Load(client.ItemID); ok {
		subscriberMap := subscribers.(*sync.Map)
		subscriberMap.Delete(client)
	}

	close(client.Send)
	client.Conn.Close()

	fmt.Printf("Client %s unsubscribed from item %s\n", client.ID, client.ItemID)
}

// broadcastToItem sends a message to all clients watching a specific item
func (m *Manager) broadcastToItem(itemID string, payload []byte) {
	if subscribers, ok := m.subscribers.Load(itemID); ok {
		subscriberMap := subscribers.(*sync.Map)

		count := 0
		subscriberMap.Range(func(key, value interface{}) bool {
			client := key.(*Client)
			select {
			case client.Send <- payload:
				count++
			default:
				// Client's send channel is full, disconnect them
				// This prevents one slow client from blocking others
				m.UnregisterClient(client)
			}
			return true
		})

		fmt.Printf("Broadcasted to %d clients watching item %s\n", count, itemID)
	}
}

// GetSubscriberCount returns the number of clients watching an item
func (m *Manager) GetSubscriberCount(itemID string) int {
	if subscribers, ok := m.subscribers.Load(itemID); ok {
		subscriberMap := subscribers.(*sync.Map)
		count := 0
		subscriberMap.Range(func(_, _ interface{}) bool {
			count++
			return true
		})
		return count
	}
	return 0
}

// writePump pumps messages from the Send channel to the websocket connection
func (c *Client) writePump() {
	ticker := time.NewTicker(54 * time.Second)
	defer func() {
		ticker.Stop()
		c.Conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.Send:
			c.Conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				// Channel closed
				c.Conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			// Send message
			if err := c.Conn.WriteMessage(websocket.TextMessage, message); err != nil {
				return
			}

		case <-ticker.C:
			// Send ping to keep connection alive
			c.Conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.Conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

// readPump pumps messages from the websocket connection to handle client input
func (c *Client) readPump(unregister chan *Client) {
	defer func() {
		unregister <- c
	}()

	c.Conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.Conn.SetPongHandler(func(string) error {
		c.Conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})

	for {
		_, message, err := c.Conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				fmt.Printf("WebSocket error: %v\n", err)
			}
			break
		}

		// Handle client messages (e.g., subscriptions, heartbeats)
		// For now, we just log them
		var msg map[string]interface{}
		if err := json.Unmarshal(message, &msg); err == nil {
			fmt.Printf("Client %s sent: %v\n", c.ID, msg)
		}
	}
}

// StartReadPump starts the read pump for this client
func (c *Client) StartReadPump(unregister chan *Client) {
	go c.readPump(unregister)
}
