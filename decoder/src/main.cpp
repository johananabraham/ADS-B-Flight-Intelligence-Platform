/**
 * @file main.cpp
 * @brief CLI tool for testing Mode S decoder
 *
 * Usage:
 *   modes_decode <hex_message>
 *   modes_decode --file <filename>
 *   echo "8D4840D6202CC371C32CE0576098" | modes_decode --stdin
 */

#include "modes.h"
#include <algorithm>
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cstring>

void print_usage(const char* program) {
    std::cerr << "Usage: " << program << " [OPTIONS] [HEX_MESSAGE]\n"
              << "\n"
              << "Options:\n"
              << "  --file <filename>  Read messages from file (one per line)\n"
              << "  --stdin            Read messages from stdin\n"
              << "  --verbose          Print detailed decoding info\n"
              << "  --help             Show this help message\n"
              << "\n"
              << "Examples:\n"
              << "  " << program << " 8D4840D6202CC371C32CE0576098\n"
              << "  " << program << " --file messages.txt\n"
              << "  cat messages.txt | " << program << " --stdin\n";
}

void print_message(const modes::DecodedMessage& msg, bool verbose) {
    if (!msg.valid) {
        std::cout << "INVALID: CRC check failed\n";
        return;
    }

    std::cout << "DF: " << modes::df_to_string(msg.downlink_format)
              << " (" << static_cast<int>(msg.downlink_format) << ")\n";
    std::cout << "ICAO: " << std::hex << std::uppercase << msg.icao_address << std::dec << "\n";

    if (msg.downlink_format == modes::DownlinkFormat::DF17 ||
        msg.downlink_format == modes::DownlinkFormat::DF18) {
        std::cout << "Type Code: " << modes::tc_to_string(msg.type_code)
                  << " (" << static_cast<int>(msg.type_code) << ")\n";
    }

    // Print identification data
    if (msg.identification) {
        std::cout << "Callsign: " << msg.identification->callsign << "\n";
        std::cout << "Category: " << static_cast<int>(msg.identification->category) << "\n";
    }

    // Print position data
    if (msg.position) {
        std::cout << "Altitude: " << msg.position->altitude << " ft";
        if (msg.position->altitude_gnss) {
            std::cout << " (GNSS)";
        } else {
            std::cout << " (Baro)";
        }
        std::cout << "\n";

        std::cout << "CPR Format: " << (msg.position->cpr_format == modes::CPRFormat::EVEN ? "Even" : "Odd") << "\n";
        std::cout << "CPR Lat: " << msg.position->lat_cpr << "\n";
        std::cout << "CPR Lon: " << msg.position->lon_cpr << "\n";

        if (msg.position->latitude && msg.position->longitude) {
            std::cout << "Position: " << *msg.position->latitude << ", "
                      << *msg.position->longitude << "\n";
        }
    }

    // Print velocity data
    if (msg.velocity) {
        if (msg.velocity->ground_speed) {
            std::cout << "Ground Speed: " << *msg.velocity->ground_speed << " kt\n";
        }
        if (msg.velocity->heading) {
            std::cout << "Heading: " << *msg.velocity->heading << "°\n";
        }
        if (msg.velocity->vertical_rate) {
            std::cout << "Vertical Rate: " << *msg.velocity->vertical_rate << " ft/min";
            if (msg.velocity->vertical_rate_source_baro) {
                std::cout << " (Baro)";
            } else {
                std::cout << " (GNSS)";
            }
            std::cout << "\n";
        }
    }

    if (verbose) {
        std::cout << "Raw: ";
        for (size_t i = 0; i < msg.msg_len; i++) {
            printf("%02X", msg.raw_msg[i]);
        }
        std::cout << "\n";
    }

    std::cout << "---\n";
}

void process_message(const std::string& hex, bool verbose) {
    // Skip empty lines and comments
    if (hex.empty() || hex[0] == '#') {
        return;
    }

    // Remove any leading * and trailing ; (dump1090 format)
    std::string clean_hex = hex;
    if (!clean_hex.empty() && clean_hex[0] == '*') {
        clean_hex = clean_hex.substr(1);
    }
    size_t semicolon = clean_hex.find(';');
    if (semicolon != std::string::npos) {
        clean_hex = clean_hex.substr(0, semicolon);
    }

    // Remove whitespace
    clean_hex.erase(std::remove_if(clean_hex.begin(), clean_hex.end(), ::isspace),
                    clean_hex.end());

    if (clean_hex.empty()) {
        return;
    }

    std::cout << "Input: " << clean_hex << "\n";
    modes::DecodedMessage msg = modes::decode_hex(clean_hex);
    print_message(msg, verbose);
}

int main(int argc, char* argv[]) {
    bool verbose = false;
    bool from_stdin = false;
    std::string filename;
    std::string hex_message;

    // Parse arguments
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            print_usage(argv[0]);
            return 0;
        } else if (strcmp(argv[i], "--verbose") == 0 || strcmp(argv[i], "-v") == 0) {
            verbose = true;
        } else if (strcmp(argv[i], "--stdin") == 0) {
            from_stdin = true;
        } else if (strcmp(argv[i], "--file") == 0 || strcmp(argv[i], "-f") == 0) {
            if (i + 1 < argc) {
                filename = argv[++i];
            } else {
                std::cerr << "Error: --file requires a filename\n";
                return 1;
            }
        } else if (argv[i][0] != '-') {
            hex_message = argv[i];
        } else {
            std::cerr << "Unknown option: " << argv[i] << "\n";
            print_usage(argv[0]);
            return 1;
        }
    }

    // Process input
    if (!hex_message.empty()) {
        // Single message from command line
        process_message(hex_message, verbose);
    } else if (from_stdin) {
        // Read from stdin
        std::string line;
        while (std::getline(std::cin, line)) {
            process_message(line, verbose);
        }
    } else if (!filename.empty()) {
        // Read from file
        std::ifstream file(filename);
        if (!file.is_open()) {
            std::cerr << "Error: Cannot open file " << filename << "\n";
            return 1;
        }
        std::string line;
        while (std::getline(file, line)) {
            process_message(line, verbose);
        }
    } else {
        print_usage(argv[0]);
        return 1;
    }

    return 0;
}
