/**
 * @file test_crc.cpp
 * @brief Unit tests for Mode S CRC-24 implementation
 */

#include <gtest/gtest.h>
#include "crc.h"
#include <cstdint>
#include <vector>

// Helper to convert hex string to bytes
std::vector<uint8_t> hex_to_bytes(const std::string& hex) {
    std::vector<uint8_t> bytes;
    for (size_t i = 0; i < hex.length(); i += 2) {
        uint8_t byte = static_cast<uint8_t>(std::stoul(hex.substr(i, 2), nullptr, 16));
        bytes.push_back(byte);
    }
    return bytes;
}

class CRCTest : public ::testing::Test {
protected:
    // Known valid DF17 messages (from dump1090 captures)
    // These messages have valid CRC (syndrome = 0)
    std::vector<std::string> valid_df17_messages = {
        "8D4840D6202CC371C32CE0576098",  // Aircraft identification
        "8D40621D58C382D690C8AC2863A7",  // Airborne position
        "8D485020994409940838175B284F",  // Airborne velocity
        "8DA05F219B06B6AF189400CBC33F",  // Airborne velocity
        "8D40621D58C386435CC412692AD6",  // Airborne position (odd frame)
    };

    // Invalid messages (modified CRC)
    std::vector<std::string> invalid_messages = {
        "8D4840D6202CC371C32CE0576099",  // Last byte changed
        "8D4840D6202CC371C32CE0576198",  // Bit flipped
        "8D4840D6202CC371C32CE0576097",  // CRC modified
    };
};

TEST_F(CRCTest, ValidDF17MessagesSyndromeZero) {
    for (const auto& hex : valid_df17_messages) {
        auto bytes = hex_to_bytes(hex);
        uint32_t syndrome = modes::crc::validate(bytes.data(), bytes.size());
        EXPECT_EQ(syndrome, 0u) << "Failed for message: " << hex;
    }
}

TEST_F(CRCTest, InvalidMessagesNonZeroSyndrome) {
    for (const auto& hex : invalid_messages) {
        auto bytes = hex_to_bytes(hex);
        uint32_t syndrome = modes::crc::validate(bytes.data(), bytes.size());
        EXPECT_NE(syndrome, 0u) << "Should be invalid: " << hex;
    }
}

TEST_F(CRCTest, IsValidDF17) {
    for (const auto& hex : valid_df17_messages) {
        auto bytes = hex_to_bytes(hex);
        EXPECT_TRUE(modes::crc::is_valid(bytes.data(), bytes.size(), 17))
            << "Failed for message: " << hex;
    }
}

TEST_F(CRCTest, IsInvalidDF17) {
    for (const auto& hex : invalid_messages) {
        auto bytes = hex_to_bytes(hex);
        EXPECT_FALSE(modes::crc::is_valid(bytes.data(), bytes.size(), 17))
            << "Should be invalid: " << hex;
    }
}

TEST_F(CRCTest, ExtractCRC) {
    // Test CRC extraction from a known message
    auto bytes = hex_to_bytes("8D4840D6202CC371C32CE0576098");
    uint32_t extracted_crc = modes::crc::extract(bytes.data(), bytes.size());
    // The last 3 bytes are 0x57, 0x60, 0x98
    EXPECT_EQ(extracted_crc, 0x576098u);
}

TEST_F(CRCTest, SingleBitErrorCorrection) {
    // Take a valid message
    auto bytes = hex_to_bytes("8D4840D6202CC371C32CE0576098");

    // Flip one bit
    bytes[5] ^= 0x01;

    // Verify it's now invalid
    EXPECT_FALSE(modes::crc::is_valid(bytes.data(), bytes.size(), 17));

    // Attempt correction
    int bit_pos = modes::crc::fix_single_bit_error(bytes.data(), bytes.size());

    // Should find and fix the error
    EXPECT_GE(bit_pos, 0);

    // Should now be valid
    EXPECT_TRUE(modes::crc::is_valid(bytes.data(), bytes.size(), 17));
}

TEST_F(CRCTest, NoErrorReturnsNegative) {
    auto bytes = hex_to_bytes("8D4840D6202CC371C32CE0576098");

    // Message is already valid, should return -1
    int bit_pos = modes::crc::fix_single_bit_error(bytes.data(), bytes.size());
    EXPECT_EQ(bit_pos, -1);
}

TEST_F(CRCTest, ComputeCRCConsistent) {
    // Compute CRC of message without the CRC field
    auto bytes = hex_to_bytes("8D4840D6202CC371C32CE0");  // Without last 3 bytes
    uint32_t computed = modes::crc::compute(bytes.data(), bytes.size());

    // The computed CRC should match the original CRC field
    EXPECT_EQ(computed, 0x576098u);
}

TEST_F(CRCTest, GeneratorPolynomialCorrect) {
    // Verify the generator polynomial constant
    EXPECT_EQ(modes::crc::GENERATOR, 0x1FFF409u);
}

TEST_F(CRCTest, ShortMessage) {
    // Test with short (56-bit) message
    auto bytes = hex_to_bytes("00000000000000");  // 7 bytes
    uint32_t crc = modes::crc::compute(bytes.data(), bytes.size());
    // Just verify it doesn't crash and returns something
    EXPECT_LT(crc, 0x1000000u);  // CRC should be 24 bits
}

TEST_F(CRCTest, AllZerosMessage) {
    std::vector<uint8_t> zeros(14, 0);
    uint32_t crc = modes::crc::compute(zeros.data(), zeros.size());
    EXPECT_EQ(crc, 0u);  // All zeros should produce zero CRC
}

TEST_F(CRCTest, ExtractCRCShortBuffer) {
    std::vector<uint8_t> short_buf = {0x01, 0x02};
    uint32_t crc = modes::crc::extract(short_buf.data(), short_buf.size());
    EXPECT_EQ(crc, 0u);  // Should handle gracefully
}
