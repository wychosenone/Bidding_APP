.PHONY: help build run test clean stop logs

help:
	@echo "Available commands:"
	@echo "  make build       - Build all services"
	@echo "  make run         - Start all services with Docker Compose"
	@echo "  make stop        - Stop all services"
	@echo "  make logs        - View logs from all services"
	@echo "  make test        - Run load tests"
	@echo "  make clean       - Clean up containers, volumes, and binaries"

build:
	@echo "Building API Gateway..."
	cd api-gateway && go build -o bin/api-gateway ./cmd
	@echo "Building Broadcast Service..."
	cd broadcast-service && go build -o bin/broadcast-service ./cmd
	@echo "Building Archival Worker..."
	cd archival-worker && go build -o bin/archival-worker ./cmd
	@echo "All services built successfully"

run:
	@echo "Starting all services with Docker Compose..."
	cd infrastructure/docker && docker-compose up --build -d
	@echo "Services started. Check status with 'make logs'"

stop:
	@echo "Stopping all services..."
	cd infrastructure/docker && docker-compose down
	@echo "Services stopped"

logs:
	cd infrastructure/docker && docker-compose logs -f

test:
	@echo "Running load tests..."
	cd load-tests && locust -f locustfile.py

clean:
	@echo "Cleaning up..."
	cd infrastructure/docker && docker-compose down -v
	rm -f api-gateway/bin/*
	rm -f broadcast-service/bin/*
	rm -f archival-worker/bin/*
	@echo "Cleanup complete"

# Development commands
dev-api:
	cd api-gateway && go run ./cmd

dev-broadcast:
	cd broadcast-service && go run ./cmd

dev-archival:
	cd archival-worker && go run ./cmd
