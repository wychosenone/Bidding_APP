module github.com/aaronwang/bidding-app/archival-worker

go 1.23.0

replace github.com/aaronwang/bidding-app/shared => ../shared

require (
	github.com/aaronwang/bidding-app/shared v0.0.0-00010101000000-000000000000
	github.com/lib/pq v1.10.9
	github.com/nats-io/nats.go v1.47.0
)

require (
	github.com/klauspost/compress v1.18.0 // indirect
	github.com/nats-io/nkeys v0.4.11 // indirect
	github.com/nats-io/nuid v1.0.1 // indirect
	golang.org/x/crypto v0.37.0 // indirect
	golang.org/x/sys v0.32.0 // indirect
)
