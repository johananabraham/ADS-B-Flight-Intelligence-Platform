# Mode S / ADS-B Decoder

A high-performance C++ library and HTTP service for decoding Mode S transponder messages, specifically DF17 ADS-B messages.

## Features

- **CRC-24 Validation** - Mode S checksum with single-bit error correction
- **DF17 ADS-B Decoding** - Aircraft identification, position, velocity
- **CPR Position Decoding** - Global and local Compact Position Reporting
- **HTTP Service** - REST API with JSON output
- **Prometheus + Grafana** - Built-in metrics and a provisioned operations dashboard
- **Docker Support** - Containerized deployment with load balancing

## Quick Start

```bash
# Build
make

# Test CLI
./modes_decode 8D4840D6202CC371C32CE0576098
# Output: ICAO: 4840D6, Callsign: KLM1023

# Start HTTP server
./modes_server --port 8080

# Decode via API
curl -X POST http://localhost:8080/decode -d '8D4840D6202CC371C32CE0576098'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/decode` | POST | Decode hex-encoded Mode S message |
| `/health` | GET | Health check for load balancers |
| `/metrics` | GET | Prometheus metrics |

## Docker Deployment

```bash
# Single instance
docker build -t modes-decoder .
docker run -p 8080:8080 modes-decoder

# Multi-instance cluster with nginx
docker-compose up -d

# Include Prometheus and the pre-provisioned Grafana dashboard
docker compose --profile monitoring up -d
# Grafana: http://localhost:3001 (admin/admin)
```

## Load Testing

```bash
make tools
./load_generator --host localhost --port 8080 --rate 1000 --duration 60

# Reproducible failure-injection test: stops decoder2 during active load
./tests/fault_tolerance_test.sh

# Compare decoded fields against a local dump1090-fa installation
./tests/dump1090_validation.sh
```

## Performance

Tested on Apple Silicon (M-series):
- **HTTP throughput**: 393 requests/sec through nginx across three decoder instances
- **HTTP latency**: 1.4 ms p99 in the recorded load test
- **HTTP success rate**: 1,974/1,974 requests returned HTTP 200 in that run
- **Decoder correctness suite**: `validation_test` checks decoded fields against published Mode S/ADS-B reference values; this is separate from HTTP success and from dump1090 comparison
- **Live instance failure**: 3,783/3,788 HTTP requests succeeded (99.87%) while one of three decoder instances was stopped; health remained HTTP 200
- **dump1090 comparison**: callsign, altitude, ground speed, track, and vertical rate matched dump1090-fa 11.0 on published reference frames

See `docs/validation-results.md` for the exact scope and limitations of these results.

## Project Structure

```
decoder/
├── include/           # Header files
│   ├── modes.h        # Main decoder API
│   ├── crc.h          # CRC-24 API
│   └── server.h       # HTTP server API
├── src/               # Implementation
│   ├── decoder.cpp    # DF17 message parsing
│   ├── crc.cpp        # CRC-24 with lookup table
│   ├── cpr.cpp        # Position decoding
│   └── server.cpp     # HTTP server
├── tests/             # Unit tests (Google Test)
├── grafana/           # Provisioned datasource and operations dashboard
├── tools/             # Load testing tools
├── Dockerfile         # Container build
├── docker-compose.yml # Multi-instance deployment
└── Makefile           # Build system
```

## References

- RTCA DO-260B - ADS-B specification
- ICAO Annex 10 Volume IV - Mode S technical standards
- [The 1090 Megahertz Riddle](https://mode-s.org/decode/) - Excellent reference
