/**
 * @file server.h
 * @brief Lightweight HTTP/TCP server for Mode S decoder service
 *
 * Provides a simple REST API for decoding Mode S messages:
 *   POST /decode - Decode a single hex-encoded message
 *   GET /health  - Health check endpoint
 *   GET /metrics - Prometheus metrics endpoint
 */

#ifndef SERVER_H
#define SERVER_H

#include <string>
#include <functional>
#include <atomic>
#include <cstdint>

namespace modes {
namespace server {

/**
 * @brief Metrics collected by the server
 */
struct ServerMetrics {
    std::atomic<uint64_t> messages_received{0};
    std::atomic<uint64_t> messages_decoded{0};
    std::atomic<uint64_t> crc_failures{0};
    std::atomic<uint64_t> decode_errors{0};
    std::atomic<uint64_t> total_decode_time_us{0};  // Microseconds

    void reset() {
        messages_received = 0;
        messages_decoded = 0;
        crc_failures = 0;
        decode_errors = 0;
        total_decode_time_us = 0;
    }
};

/**
 * @brief Server configuration
 */
struct ServerConfig {
    int port = 8080;
    int backlog = 128;
    int max_connections = 100;
    bool verbose = false;
};

/**
 * @brief Simple HTTP server for Mode S decoding
 */
class DecoderServer {
public:
    DecoderServer(const ServerConfig& config = ServerConfig{});
    ~DecoderServer();

    // Non-copyable
    DecoderServer(const DecoderServer&) = delete;
    DecoderServer& operator=(const DecoderServer&) = delete;

    /**
     * @brief Start the server (blocks until stop() is called)
     * @return 0 on success, -1 on error
     */
    int run();

    /**
     * @brief Stop the server gracefully
     */
    void stop();

    /**
     * @brief Get current metrics
     */
    const ServerMetrics& metrics() const { return metrics_; }

    /**
     * @brief Check if server is running
     */
    bool is_running() const { return running_; }

private:
    ServerConfig config_;
    ServerMetrics metrics_;
    std::atomic<bool> running_{false};
    int server_fd_{-1};

    void handle_client(int client_fd);
    std::string handle_request(const std::string& request);
    std::string handle_decode(const std::string& body);
    std::string handle_health();
    std::string handle_metrics();
    std::string build_response(int status, const std::string& content_type,
                               const std::string& body);
};

/**
 * @brief Start a decoder server in the foreground
 * @param port Port to listen on
 * @param verbose Enable verbose logging
 * @return Exit code
 */
int start_server(int port, bool verbose = false);

} // namespace server
} // namespace modes

#endif // SERVER_H
