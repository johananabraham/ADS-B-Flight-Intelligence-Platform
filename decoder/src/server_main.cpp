/**
 * @file server_main.cpp
 * @brief Entry point for Mode S Decoder HTTP service
 *
 * Usage:
 *   modes_server [--port PORT] [--verbose]
 */

#include "server.h"
#include <iostream>
#include <cstring>
#include <cstdlib>

void print_usage(const char* program) {
    std::cout << "Mode S Decoder HTTP Service\n\n";
    std::cout << "Usage: " << program << " [OPTIONS]\n\n";
    std::cout << "Options:\n";
    std::cout << "  --port PORT    Port to listen on (default: 8080)\n";
    std::cout << "  --verbose      Enable verbose logging\n";
    std::cout << "  --help         Show this help message\n";
    std::cout << "\n";
    std::cout << "Endpoints:\n";
    std::cout << "  POST /decode   Decode a hex-encoded Mode S message\n";
    std::cout << "  GET  /health   Health check (for load balancer)\n";
    std::cout << "  GET  /metrics  Prometheus metrics\n";
    std::cout << "\n";
    std::cout << "Example:\n";
    std::cout << "  curl -X POST http://localhost:8080/decode \\\n";
    std::cout << "       -d '8D4840D6202CC371C32CE0576098'\n";
}

int main(int argc, char* argv[]) {
    int port = 8080;
    bool verbose = false;

    // Parse arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            print_usage(argv[0]);
            return 0;
        } else if (strcmp(argv[i], "--port") == 0 || strcmp(argv[i], "-p") == 0) {
            if (i + 1 < argc) {
                port = std::atoi(argv[++i]);
                if (port <= 0 || port > 65535) {
                    std::cerr << "Error: Invalid port number\n";
                    return 1;
                }
            } else {
                std::cerr << "Error: --port requires a value\n";
                return 1;
            }
        } else if (strcmp(argv[i], "--verbose") == 0 || strcmp(argv[i], "-v") == 0) {
            verbose = true;
        } else {
            std::cerr << "Unknown option: " << argv[i] << "\n";
            print_usage(argv[0]);
            return 1;
        }
    }

    // Check for PORT environment variable (for Docker)
    const char* env_port = std::getenv("PORT");
    if (env_port) {
        int ep = std::atoi(env_port);
        if (ep > 0 && ep <= 65535) {
            port = ep;
        }
    }

    return modes::server::start_server(port, verbose);
}
