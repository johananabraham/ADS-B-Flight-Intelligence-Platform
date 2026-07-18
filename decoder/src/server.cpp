/**
 * @file server.cpp
 * @brief HTTP server implementation for Mode S decoder service
 */

#include "server.h"
#include "modes.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <cstring>
#include <sstream>
#include <chrono>
#include <iostream>
#include <thread>
#include <iomanip>

namespace modes {
namespace server {

// Global server pointer for signal handling
static DecoderServer* g_server = nullptr;

static void signal_handler(int sig) {
    if (g_server && (sig == SIGINT || sig == SIGTERM)) {
        std::cout << "\nShutting down server...\n";
        g_server->stop();
    }
}

DecoderServer::DecoderServer(const ServerConfig& config)
    : config_(config) {
}

DecoderServer::~DecoderServer() {
    stop();
}

int DecoderServer::run() {
    // Create socket
    server_fd_ = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd_ < 0) {
        std::cerr << "Error: Failed to create socket\n";
        return -1;
    }

    // Allow address reuse
    int opt = 1;
    if (setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        std::cerr << "Warning: Failed to set SO_REUSEADDR\n";
    }

    // Bind
    struct sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(config_.port);

    if (bind(server_fd_, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        std::cerr << "Error: Failed to bind to port " << config_.port << "\n";
        close(server_fd_);
        return -1;
    }

    // Listen
    if (listen(server_fd_, config_.backlog) < 0) {
        std::cerr << "Error: Failed to listen\n";
        close(server_fd_);
        return -1;
    }

    // Set up signal handling
    g_server = this;
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    running_ = true;
    std::cout << "Mode S Decoder Server listening on port " << config_.port << "\n";
    std::cout << "Endpoints:\n";
    std::cout << "  POST /decode  - Decode a hex-encoded Mode S message\n";
    std::cout << "  GET  /health  - Health check\n";
    std::cout << "  GET  /metrics - Prometheus metrics\n";

    // Accept loop
    while (running_) {
        struct sockaddr_in client_addr{};
        socklen_t client_len = sizeof(client_addr);

        // Use select with timeout to allow checking running_ flag
        fd_set read_fds;
        FD_ZERO(&read_fds);
        FD_SET(server_fd_, &read_fds);

        struct timeval timeout{};
        timeout.tv_sec = 1;
        timeout.tv_usec = 0;

        int ready = select(server_fd_ + 1, &read_fds, nullptr, nullptr, &timeout);
        if (ready < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (ready == 0) continue;  // Timeout

        int client_fd = accept(server_fd_, (struct sockaddr*)&client_addr, &client_len);
        if (client_fd < 0) {
            if (errno == EINTR) continue;
            std::cerr << "Warning: Failed to accept connection\n";
            continue;
        }

        // Handle client (simple synchronous handling for now)
        handle_client(client_fd);
        close(client_fd);
    }

    close(server_fd_);
    server_fd_ = -1;
    g_server = nullptr;

    std::cout << "Server stopped.\n";
    return 0;
}

void DecoderServer::stop() {
    running_ = false;
}

void DecoderServer::handle_client(int client_fd) {
    // Read request (simple implementation, assumes small requests)
    char buffer[8192];
    ssize_t bytes_read = recv(client_fd, buffer, sizeof(buffer) - 1, 0);

    if (bytes_read <= 0) {
        return;
    }

    buffer[bytes_read] = '\0';
    std::string request(buffer);

    // Handle the request
    std::string response = handle_request(request);

    // Send response
    send(client_fd, response.c_str(), response.size(), 0);
}

std::string DecoderServer::handle_request(const std::string& request) {
    // Parse HTTP request (minimal parsing)
    std::istringstream iss(request);
    std::string method, path, version;
    iss >> method >> path >> version;

    if (config_.verbose) {
        std::cout << method << " " << path << "\n";
    }

    // Route the request
    if (method == "GET" && path == "/health") {
        return handle_health();
    } else if (method == "GET" && path == "/metrics") {
        return handle_metrics();
    } else if (method == "POST" && path == "/decode") {
        // Extract body (after \r\n\r\n)
        size_t body_start = request.find("\r\n\r\n");
        std::string body;
        if (body_start != std::string::npos) {
            body = request.substr(body_start + 4);
        }
        return handle_decode(body);
    } else if (method == "GET" && path == "/") {
        std::string html = R"(<!DOCTYPE html>
<html>
<head><title>Mode S Decoder Service</title></head>
<body>
<h1>Mode S Decoder Service</h1>
<p>Endpoints:</p>
<ul>
<li>POST /decode - Decode a hex-encoded Mode S message</li>
<li>GET /health - Health check</li>
<li>GET /metrics - Prometheus metrics</li>
</ul>
</body>
</html>
)";
        return build_response(200, "text/html", html);
    }

    return build_response(404, "text/plain", "Not Found");
}

std::string DecoderServer::handle_decode(const std::string& body) {
    metrics_.messages_received++;

    // Trim whitespace
    std::string hex = body;
    hex.erase(0, hex.find_first_not_of(" \t\r\n"));
    hex.erase(hex.find_last_not_of(" \t\r\n") + 1);

    if (hex.empty()) {
        metrics_.decode_errors++;
        return build_response(400, "application/json",
            R"({"error": "Missing hex message in request body"})");
    }

    // Time the decode operation
    auto start = std::chrono::high_resolution_clock::now();
    DecodedMessage msg = decode_hex(hex);
    auto end = std::chrono::high_resolution_clock::now();

    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
    metrics_.total_decode_time_us += duration.count();

    if (!msg.valid) {
        metrics_.crc_failures++;
        return build_response(200, "application/json",
            R"({"valid": false, "error": "CRC check failed"})");
    }

    metrics_.messages_decoded++;

    // Build JSON response
    std::ostringstream json;
    json << std::fixed << std::setprecision(6);
    json << "{\n";
    json << "  \"valid\": true,\n";
    json << "  \"downlink_format\": " << static_cast<int>(msg.downlink_format) << ",\n";
    json << "  \"icao\": \"" << std::hex << std::uppercase << msg.icao_address << std::dec << "\",\n";
    json << "  \"type_code\": " << static_cast<int>(msg.type_code);

    if (msg.identification) {
        json << ",\n  \"identification\": {\n";
        json << "    \"callsign\": \"" << msg.identification->callsign << "\",\n";
        json << "    \"category\": " << static_cast<int>(msg.identification->category) << "\n";
        json << "  }";
    }

    if (msg.position) {
        json << ",\n  \"position\": {\n";
        json << "    \"altitude\": " << msg.position->altitude << ",\n";
        json << "    \"altitude_gnss\": " << (msg.position->altitude_gnss ? "true" : "false") << ",\n";
        json << "    \"cpr_format\": \"" << (msg.position->cpr_format == CPRFormat::EVEN ? "even" : "odd") << "\",\n";
        json << "    \"cpr_lat\": " << msg.position->lat_cpr << ",\n";
        json << "    \"cpr_lon\": " << msg.position->lon_cpr;
        if (msg.position->latitude && msg.position->longitude) {
            json << ",\n    \"latitude\": " << *msg.position->latitude;
            json << ",\n    \"longitude\": " << *msg.position->longitude;
        }
        json << "\n  }";
    }

    if (msg.velocity) {
        json << ",\n  \"velocity\": {\n";
        json << "    \"type\": " << static_cast<int>(msg.velocity->type);
        if (msg.velocity->ground_speed) {
            json << ",\n    \"ground_speed\": " << *msg.velocity->ground_speed;
        }
        if (msg.velocity->heading) {
            json << ",\n    \"heading\": " << *msg.velocity->heading;
        }
        if (msg.velocity->vertical_rate) {
            json << ",\n    \"vertical_rate\": " << *msg.velocity->vertical_rate;
        }
        json << "\n  }";
    }

    json << "\n}\n";

    return build_response(200, "application/json", json.str());
}

std::string DecoderServer::handle_health() {
    return build_response(200, "application/json",
        R"({"status": "healthy", "service": "modes-decoder"})");
}

std::string DecoderServer::handle_metrics() {
    // Prometheus exposition format
    std::ostringstream metrics;

    uint64_t received = metrics_.messages_received;
    uint64_t decoded = metrics_.messages_decoded;
    uint64_t crc_fail = metrics_.crc_failures;
    uint64_t errors = metrics_.decode_errors;
    uint64_t total_time = metrics_.total_decode_time_us;

    metrics << "# HELP modes_messages_received_total Total messages received\n";
    metrics << "# TYPE modes_messages_received_total counter\n";
    metrics << "modes_messages_received_total " << received << "\n\n";

    metrics << "# HELP modes_messages_decoded_total Total messages successfully decoded\n";
    metrics << "# TYPE modes_messages_decoded_total counter\n";
    metrics << "modes_messages_decoded_total " << decoded << "\n\n";

    metrics << "# HELP modes_crc_failures_total Total CRC validation failures\n";
    metrics << "# TYPE modes_crc_failures_total counter\n";
    metrics << "modes_crc_failures_total " << crc_fail << "\n\n";

    metrics << "# HELP modes_decode_errors_total Total decode errors (malformed input)\n";
    metrics << "# TYPE modes_decode_errors_total counter\n";
    metrics << "modes_decode_errors_total " << errors << "\n\n";

    metrics << "# HELP modes_decode_time_microseconds_total Total decode time in microseconds\n";
    metrics << "# TYPE modes_decode_time_microseconds_total counter\n";
    metrics << "modes_decode_time_microseconds_total " << total_time << "\n\n";

    if (decoded > 0) {
        double avg_latency = static_cast<double>(total_time) / static_cast<double>(decoded);
        metrics << "# HELP modes_decode_latency_avg_microseconds Average decode latency\n";
        metrics << "# TYPE modes_decode_latency_avg_microseconds gauge\n";
        metrics << "modes_decode_latency_avg_microseconds " << avg_latency << "\n\n";
    }

    double success_rate = (received > 0) ?
        static_cast<double>(decoded) / static_cast<double>(received) * 100.0 : 0.0;
    metrics << "# HELP modes_decode_success_rate Decode success rate percentage\n";
    metrics << "# TYPE modes_decode_success_rate gauge\n";
    metrics << "modes_decode_success_rate " << success_rate << "\n";

    return build_response(200, "text/plain; version=0.0.4", metrics.str());
}

std::string DecoderServer::build_response(int status, const std::string& content_type,
                                          const std::string& body) {
    std::string status_text;
    switch (status) {
        case 200: status_text = "OK"; break;
        case 400: status_text = "Bad Request"; break;
        case 404: status_text = "Not Found"; break;
        case 500: status_text = "Internal Server Error"; break;
        default: status_text = "Unknown"; break;
    }

    std::ostringstream response;
    response << "HTTP/1.1 " << status << " " << status_text << "\r\n";
    response << "Content-Type: " << content_type << "\r\n";
    response << "Content-Length: " << body.size() << "\r\n";
    response << "Connection: close\r\n";
    response << "\r\n";
    response << body;

    return response.str();
}

int start_server(int port, bool verbose) {
    ServerConfig config;
    config.port = port;
    config.verbose = verbose;

    DecoderServer server(config);
    return server.run();
}

} // namespace server
} // namespace modes
