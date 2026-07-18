/**
 * @file crc.h
 * @brief Mode S CRC-24 checksum implementation
 *
 * Mode S uses a 24-bit CRC with generator polynomial:
 * G(x) = x^24 + x^23 + x^22 + x^21 + x^20 + x^19 + x^18 + x^17 +
 *        x^16 + x^15 + x^14 + x^13 + x^12 + x^10 + x^3 + 1
 *
 * This corresponds to the polynomial value 0x1FFF409 (25 bits with leading 1)
 * or 0xFFF409 (24 bits without leading 1).
 *
 * For DF11, DF17, and DF18 messages, the CRC is XORed with the ICAO address
 * (for DF11) or simply appended (for DF17/18).
 */

#ifndef CRC_H
#define CRC_H

#include <cstdint>
#include <cstddef>

namespace modes {
namespace crc {

// CRC-24 generator polynomial for Mode S
// x^24 + x^23 + x^22 + x^21 + x^20 + x^19 + x^18 + x^17 +
// x^16 + x^15 + x^14 + x^13 + x^12 + x^10 + x^3 + 1
constexpr uint32_t GENERATOR = 0x1FFF409;

/**
 * @brief Compute CRC-24 checksum for Mode S message
 *
 * Computes the CRC over the message bytes. For a valid message,
 * computing the CRC over all bytes including the checksum should yield 0.
 *
 * @param data Pointer to message data
 * @param len Length of message in bytes (including 3-byte CRC)
 * @return 24-bit CRC value
 */
uint32_t compute(const uint8_t* data, size_t len);

/**
 * @brief Validate a Mode S message CRC
 *
 * For DF17/18 (extended squitter), the last 24 bits are the CRC.
 * A valid message will have CRC remainder of 0.
 *
 * For DF11 (all-call reply), the CRC is XORed with the ICAO address.
 * Returns the syndrome which equals the ICAO address for valid messages.
 *
 * @param data Pointer to message data
 * @param len Length of message in bytes
 * @return 0 for valid DF17/18, ICAO address for valid DF11, non-zero otherwise
 */
uint32_t validate(const uint8_t* data, size_t len);

/**
 * @brief Check if a message has valid CRC
 *
 * @param data Pointer to message data
 * @param len Length of message in bytes
 * @param df Downlink format (needed to determine CRC interpretation)
 * @return true if CRC is valid
 */
bool is_valid(const uint8_t* data, size_t len, uint8_t df);

/**
 * @brief Extract the CRC field from a message
 *
 * @param data Pointer to message data
 * @param len Length of message in bytes
 * @return 24-bit CRC value from message
 */
uint32_t extract(const uint8_t* data, size_t len);

/**
 * @brief Fix single-bit errors in a message
 *
 * Mode S CRC can detect and correct single-bit errors.
 * This function attempts to fix single-bit errors in messages.
 *
 * @param data Pointer to message data (will be modified if fix found)
 * @param len Length of message in bytes
 * @return Bit position of fix (0-based), or -1 if no single-bit fix found
 */
int fix_single_bit_error(uint8_t* data, size_t len);

} // namespace crc
} // namespace modes

#endif // CRC_H
