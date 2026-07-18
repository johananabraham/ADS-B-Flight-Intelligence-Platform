/**
 * @file load_generator.cpp
 * @brief Load testing tool for Mode S Decoder service
 *
 * Sends bursts of Mode S messages to the decoder service and measures:
 * - Throughput (messages/sec)
 * - Latency (p50, p95, p99)
 * - Error rates
 *
 * Usage:
 *   load_generator --url http://localhost:8080/decode --rate 1000 --duration 60
 */

#include <iostream>
#include <vector>
#include <string>
#include <chrono>
#include <thread>
#include <atomic>
#include <algorithm>
#include <numeric>
#include <cstring>
#include <cstdlib>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <unistd.h>
#include <sstream>
#include <iomanip>
#include <mutex>

// Sample valid Mode S messages for testing
const std::vector<std::string> SAMPLE_MESSAGES = {
    "8D4840D6202CC371C32CE0576098",  // Aircraft ID
    "8D40621D58C382D690C8AC2863A7",  // Position
    "8DA05F219B06B6AF189400CBC33F",  // Velocity
    "8D4840D6202CC371C32CE0576098",
    "8D40621D58C382D690C8AC2863A7",
    "8DA05F219B06B6AF189400CBC33F",
};

struct LoadTestConfig {
    std::string host = "localhost";
    int port = 8080;
    std::string path = "/decode";
    int rate = 100;           // messages per second
    int duration_sec = 10;    // test duration
    int threads = 4;          // concurrent threads
    bool verbose = false;
};

struct LoadTestResults {
    std::atomic<uint64_t> requests_sent{0};
    std::atomic<uint64_t> requests_success{0};
    std::atomic<uint64_t> requests_failed{0};
    std::atomic<uint64_t> bytes_sent{0};
    std::atomic<uint64_t> bytes_received{0};

    std::mutex latency_mutex;
    std::vector<double> latencies_ms;

    void add_latency(double ms) {
        std::lock_guard<std::mutex> lock(latency_mutex);
        latencies_ms.push_back(ms);
    }
};

// Simple HTTP POST request
bool send_request(const LoadTestConfig& config, const std::string& body,
                  double& latency_ms, std::string& response) {
    auto start = std::chrono::high_resolution_clock::now();

    // Create socket
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return false;

    // Set timeout
    struct timeval timeout;
    timeout.tv_sec = 5;
    timeout.tv_usec = 0;
    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

    // Resolve host
    struct hostent* server = gethostbyname(config.host.c_str());
    if (!server) {
        close(sock);
        return false;
    }

    struct sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(config.port);
    memcpy(&addr.sin_addr.s_addr, server->h_addr, server->h_length);

    // Connect
    if (connect(sock, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(sock);
        return false;
    }

    // Build HTTP request
    std::ostringstream req;
    req << "POST " << config.path << " HTTP/1.1\r\n";
    req << "Host: " << config.host << ":" << config.port << "\r\n";
    req << "Content-Type: text/plain\r\n";
    req << "Content-Length: " << body.size() << "\r\n";
    req << "Connection: close\r\n";
    req << "\r\n";
    req << body;

    std::string request = req.str();

    // Send
    if (send(sock, request.c_str(), request.size(), 0) < 0) {
        close(sock);
        return false;
    }

    // Receive
    char buffer[4096];
    ssize_t bytes = recv(sock, buffer, sizeof(buffer) - 1, 0);
    close(sock);

    auto end = std::chrono::high_resolution_clock::now();
    latency_ms = std::chrono::duration<double, std::milli>(end - start).count();

    if (bytes <= 0) return false;

    buffer[bytes] = '\0';
    response = std::string(buffer);

    // Check for 200 OK
    return response.find("200 OK") != std::string::npos;
}

void worker_thread(const LoadTestConfig& config, LoadTestResults& results,
                   std::atomic<bool>& running, int thread_id) {
    int msg_idx = thread_id % SAMPLE_MESSAGES.size();

    while (running) {
        const std::string& msg = SAMPLE_MESSAGES[msg_idx];
        msg_idx = (msg_idx + 1) % SAMPLE_MESSAGES.size();

        double latency_ms;
        std::string response;

        results.requests_sent++;
        results.bytes_sent += msg.size();

        if (send_request(config, msg, latency_ms, response)) {
            results.requests_success++;
            results.bytes_received += response.size();
            results.add_latency(latency_ms);
        } else {
            results.requests_failed++;
        }

        // Rate limiting (approximate)
        int sleep_us = (1000000 * config.threads) / config.rate;
        std::this_thread::sleep_for(std::chrono::microseconds(sleep_us));
    }
}

void print_results(const LoadTestConfig& config, const LoadTestResults& results,
                   double elapsed_sec) {
    std::cout << "\n";
    std::cout << "═══════════════════════════════════════════════════════════\n";
    std::cout << "                    LOAD TEST RESULTS\n";
    std::cout << "═══════════════════════════════════════════════════════════\n\n";

    uint64_t sent = results.requests_sent;
    uint64_t success = results.requests_success;
    uint64_t failed = results.requests_failed;

    double throughput = sent / elapsed_sec;
    double success_rate = (sent > 0) ? (100.0 * success / sent) : 0;

    std::cout << "Configuration:\n";
    std::cout << "  Target:        " << config.host << ":" << config.port << config.path << "\n";
    std::cout << "  Target Rate:   " << config.rate << " msg/sec\n";
    std::cout << "  Duration:      " << config.duration_sec << " seconds\n";
    std::cout << "  Threads:       " << config.threads << "\n\n";

    std::cout << "Results:\n";
    std::cout << "  Total Requests:    " << sent << "\n";
    std::cout << "  Successful:        " << success << "\n";
    std::cout << "  Failed:            " << failed << "\n";
    std::cout << "  Success Rate:      " << std::fixed << std::setprecision(2) << success_rate << "%\n";
    std::cout << "  Actual Throughput: " << std::fixed << std::setprecision(1) << throughput << " msg/sec\n";
    std::cout << "  Data Sent:         " << (results.bytes_sent / 1024.0) << " KB\n";
    std::cout << "  Data Received:     " << (results.bytes_received / 1024.0) << " KB\n\n";

    // Calculate percentiles
    std::vector<double> latencies = results.latencies_ms;  // Copy for sorting
    if (!latencies.empty()) {
        std::sort(latencies.begin(), latencies.end());

        size_t n = latencies.size();
        double p50 = latencies[n * 50 / 100];
        double p95 = latencies[n * 95 / 100];
        double p99 = latencies[n * 99 / 100];
        double avg = std::accumulate(latencies.begin(), latencies.end(), 0.0) / n;
        double min_lat = latencies.front();
        double max_lat = latencies.back();

        std::cout << "Latency (ms):\n";
        std::cout << "  Min:    " << std::fixed << std::setprecision(2) << min_lat << "\n";
        std::cout << "  Avg:    " << std::fixed << std::setprecision(2) << avg << "\n";
        std::cout << "  p50:    " << std::fixed << std::setprecision(2) << p50 << "\n";
        std::cout << "  p95:    " << std::fixed << std::setprecision(2) << p95 << "\n";
        std::cout << "  p99:    " << std::fixed << std::setprecision(2) << p99 << "\n";
        std::cout << "  Max:    " << std::fixed << std::setprecision(2) << max_lat << "\n";
    }

    std::cout << "\n═══════════════════════════════════════════════════════════\n";

    // Summary line for easy copy-paste to resume
    std::cout << "\nResume bullet data: "
              << "Sustained " << static_cast<int>(throughput) << " msg/sec "
              << "at " << std::fixed << std::setprecision(1) << (latencies.empty() ? 0 : latencies[latencies.size() * 99 / 100])
              << "ms p99 latency\n";
}

void print_usage(const char* program) {
    std::cout << "Mode S Decoder Load Generator\n\n";
    std::cout << "Usage: " << program << " [OPTIONS]\n\n";
    std::cout << "Options:\n";
    std::cout << "  --host HOST      Target host (default: localhost)\n";
    std::cout << "  --port PORT      Target port (default: 8080)\n";
    std::cout << "  --path PATH      API path (default: /decode)\n";
    std::cout << "  --rate RATE      Target messages/sec (default: 100)\n";
    std::cout << "  --duration SEC   Test duration in seconds (default: 10)\n";
    std::cout << "  --threads N      Number of worker threads (default: 4)\n";
    std::cout << "  --verbose        Enable verbose output\n";
    std::cout << "  --help           Show this help\n";
}

int main(int argc, char* argv[]) {
    LoadTestConfig config;

    // Parse arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            print_usage(argv[0]);
            return 0;
        } else if (strcmp(argv[i], "--host") == 0 && i + 1 < argc) {
            config.host = argv[++i];
        } else if (strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
            config.port = std::atoi(argv[++i]);
        } else if (strcmp(argv[i], "--path") == 0 && i + 1 < argc) {
            config.path = argv[++i];
        } else if (strcmp(argv[i], "--rate") == 0 && i + 1 < argc) {
            config.rate = std::atoi(argv[++i]);
        } else if (strcmp(argv[i], "--duration") == 0 && i + 1 < argc) {
            config.duration_sec = std::atoi(argv[++i]);
        } else if (strcmp(argv[i], "--threads") == 0 && i + 1 < argc) {
            config.threads = std::atoi(argv[++i]);
        } else if (strcmp(argv[i], "--verbose") == 0 || strcmp(argv[i], "-v") == 0) {
            config.verbose = true;
        }
    }

    std::cout << "Mode S Decoder Load Generator\n";
    std::cout << "Target: " << config.host << ":" << config.port << config.path << "\n";
    std::cout << "Rate: " << config.rate << " msg/sec, Duration: " << config.duration_sec << "s\n";
    std::cout << "Threads: " << config.threads << "\n\n";

    // Check connectivity
    std::cout << "Checking connectivity...\n";
    double latency;
    std::string response;
    if (!send_request(config, SAMPLE_MESSAGES[0], latency, response)) {
        std::cerr << "Error: Cannot connect to " << config.host << ":" << config.port << "\n";
        std::cerr << "Make sure the decoder service is running.\n";
        return 1;
    }
    std::cout << "Connected! Initial latency: " << std::fixed << std::setprecision(2) << latency << "ms\n\n";

    // Run load test
    LoadTestResults results;
    std::atomic<bool> running{true};
    std::vector<std::thread> threads;

    std::cout << "Starting load test...\n";
    auto start_time = std::chrono::steady_clock::now();

    // Start worker threads
    for (int i = 0; i < config.threads; i++) {
        threads.emplace_back(worker_thread, std::ref(config), std::ref(results),
                            std::ref(running), i);
    }

    // Progress updates
    for (int i = 0; i < config.duration_sec; i++) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        uint64_t sent = results.requests_sent;
        double elapsed = i + 1;
        std::cout << "  [" << (i + 1) << "/" << config.duration_sec << "] "
                  << sent << " requests (" << static_cast<int>(sent / elapsed) << " msg/sec)\n";
    }

    // Stop workers
    running = false;
    for (auto& t : threads) {
        t.join();
    }

    auto end_time = std::chrono::steady_clock::now();
    double elapsed_sec = std::chrono::duration<double>(end_time - start_time).count();

    print_results(config, results, elapsed_sec);

    return 0;
}
