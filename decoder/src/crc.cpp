/**
 * @file crc.cpp
 * @brief Mode S CRC-24 checksum implementation
 */

#include "crc.h"
#include <array>

namespace modes {
namespace crc {

// Precomputed CRC table for byte-at-a-time processing
static std::array<uint32_t, 256> crc_table;
static bool table_initialized = false;

/**
 * @brief Initialize the CRC lookup table
 *
 * Precomputes CRC values for all possible byte values to speed up
 * computation from O(8n) bit operations to O(n) table lookups.
 */
static void init_table() {
    if (table_initialized) return;

    for (uint32_t i = 0; i < 256; i++) {
        uint32_t crc = i << 16;

        for (int j = 0; j < 8; j++) {
            if (crc & 0x800000) {
                crc = (crc << 1) ^ GENERATOR;
            } else {
                crc = crc << 1;
            }
        }

        crc_table[i] = crc & 0xFFFFFF;
    }

    table_initialized = true;
}

uint32_t compute(const uint8_t* data, size_t len) {
    init_table();

    uint32_t crc = 0;

    // Process all bytes except the last 3 (which contain the CRC in the message)
    // For computing CRC of data only, we process all bytes
    for (size_t i = 0; i < len; i++) {
        uint8_t byte = data[i];
        uint8_t index = ((crc >> 16) ^ byte) & 0xFF;
        crc = (crc << 8) ^ crc_table[index];
        crc &= 0xFFFFFF;
    }

    return crc;
}

uint32_t validate(const uint8_t* data, size_t len) {
    // For validation, compute CRC over entire message including the 3-byte CRC field
    // A valid message will produce a syndrome of 0 (for DF17/18) or ICAO address (for DF11)
    return compute(data, len);
}

bool is_valid(const uint8_t* data, size_t len, uint8_t df) {
    uint32_t syndrome = validate(data, len);

    // For DF17 and DF18, CRC should be exactly 0
    if (df == 17 || df == 18) {
        return syndrome == 0;
    }

    // For DF11, the syndrome equals the ICAO address
    // We consider it valid if the syndrome is non-zero (a real ICAO address)
    // The caller should verify the ICAO address is reasonable
    if (df == 11) {
        // ICAO addresses are 24-bit, so any non-zero value could be valid
        // We can't fully validate without additional context
        return true;
    }

    // For other DF types with PI field (Parity/Interrogator), different rules apply
    // DF0, DF4, DF5, DF16, DF20, DF21 use the PI field differently
    // For simplicity, we check if syndrome matches expected patterns
    return syndrome == 0;
}

uint32_t extract(const uint8_t* data, size_t len) {
    if (len < 3) return 0;

    // CRC is the last 24 bits (3 bytes) of the message
    return ((uint32_t)data[len - 3] << 16) |
           ((uint32_t)data[len - 2] << 8) |
           ((uint32_t)data[len - 1]);
}

int fix_single_bit_error(uint8_t* data, size_t len) {
    init_table();

    // Compute the syndrome of the received message
    uint32_t syndrome = validate(data, len);

    if (syndrome == 0) {
        // No error
        return -1;
    }

    // Try flipping each bit and check if syndrome becomes 0
    // This is O(n*8) but could be optimized with syndrome lookup tables
    for (size_t byte_idx = 0; byte_idx < len; byte_idx++) {
        for (int bit_idx = 7; bit_idx >= 0; bit_idx--) {
            // Flip the bit
            data[byte_idx] ^= (1 << bit_idx);

            // Check if this fixes the CRC
            if (validate(data, len) == 0) {
                return static_cast<int>(byte_idx * 8 + (7 - bit_idx));
            }

            // Flip it back
            data[byte_idx] ^= (1 << bit_idx);
        }
    }

    // No single-bit fix found
    return -1;
}

} // namespace crc
} // namespace modes
