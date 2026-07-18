# Mode S Decoder Makefile
# Alternative to CMake for quick builds

CXX = clang++
CXXFLAGS = -std=c++17 -Wall -Wextra -Wpedantic -O2
INCLUDES = -Iinclude

# Source files
LIB_SRCS = src/crc.cpp src/decoder.cpp src/cpr.cpp
SERVER_SRCS = src/server.cpp
LIB_OBJS = $(LIB_SRCS:.cpp=.o)
SERVER_OBJS = $(SERVER_SRCS:.cpp=.o)

# Targets
LIB = libmodes.a
CLI = modes_decode
SERVER = modes_server
LOADGEN = load_generator

.PHONY: all clean test server docker tools

all: $(LIB) $(CLI) $(SERVER)

tools: $(LOADGEN)

# Static library
$(LIB): $(LIB_OBJS)
	ar rcs $@ $^

# Object files
src/%.o: src/%.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

# CLI tool
$(CLI): src/main.cpp $(LIB)
	$(CXX) $(CXXFLAGS) $(INCLUDES) $< -L. -lmodes -o $@

# HTTP Server
$(SERVER): src/server_main.cpp $(SERVER_OBJS) $(LIB)
	$(CXX) $(CXXFLAGS) $(INCLUDES) src/server_main.cpp $(SERVER_OBJS) -L. -lmodes -o $@

# Load Generator Tool
$(LOADGEN): tools/load_generator.cpp
	$(CXX) $(CXXFLAGS) $< -o $@

# Quick test with known messages
test: $(CLI)
	@echo "=== Testing valid DF17 messages ==="
	./$(CLI) 8D4840D6202CC371C32CE0576098
	./$(CLI) 8D40621D58C382D690C8AC2863A7
	./$(CLI) 8DA05F219B06B6AF189400CBC33F
	@echo ""
	@echo "=== Testing invalid message (modified CRC) ==="
	./$(CLI) 8D4840D6202CC371C32CE0576099 || true
	@echo ""
	@echo "All tests passed!"

# Test the server
test-server: $(SERVER)
	@echo "Starting server on port 8080..."
	@echo "Test with: curl -X POST http://localhost:8080/decode -d '8D4840D6202CC371C32CE0576098'"
	./$(SERVER) --verbose

# Build Docker image
docker:
	docker build -t modes-decoder:latest .

# Run Docker container
docker-run: docker
	docker run -p 8080:8080 --rm modes-decoder:latest

# Run load test (server must be running)
load-test: $(LOADGEN)
	@echo "Make sure modes_server is running on port 8080"
	./$(LOADGEN) --host localhost --port 8080 --rate 500 --duration 10

clean:
	rm -f $(LIB_OBJS) $(SERVER_OBJS) $(LIB) $(CLI) $(SERVER) $(LOADGEN)
	rm -rf build

# Install cmake via: brew install cmake
cmake-build:
	mkdir -p build && cd build && cmake .. && make

help:
	@echo "Available targets:"
	@echo "  all         - Build library, CLI tool, and server (default)"
	@echo "  tools       - Build load testing tools"
	@echo "  test        - Run quick tests with known messages"
	@echo "  test-server - Start the HTTP server for manual testing"
	@echo "  load-test   - Run load test (server must be running)"
	@echo "  docker      - Build Docker image"
	@echo "  docker-run  - Build and run Docker container"
	@echo "  clean       - Remove build artifacts"
	@echo "  cmake-build - Build using CMake (requires: brew install cmake)"
