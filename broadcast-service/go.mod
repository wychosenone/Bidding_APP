module github.com/aaronwang/bidding-app/broadcast-service

go 1.25.1

replace github.com/aaronwang/bidding-app/shared => ../shared

require (
	github.com/aaronwang/bidding-app/shared v0.0.0-00010101000000-000000000000
	github.com/google/uuid v1.6.0
	github.com/gorilla/mux v1.8.1
	github.com/gorilla/websocket v1.5.3
	github.com/redis/go-redis/v9 v9.16.0
)

require (
	github.com/cespare/xxhash/v2 v2.3.0 // indirect
	github.com/dgryski/go-rendezvous v0.0.0-20200823014737-9f7001d12a5f // indirect
)
