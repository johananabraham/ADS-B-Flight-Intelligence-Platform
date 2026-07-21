/**
 * @file validation_test.cpp
 * @brief Decoder accuracy validation against known-correct reference values
 *
 * These test cases use messages with known correct decoded values from:
 * - "The 1090 Megahertz Riddle" by Junzi Sun (mode-s.org/decode)
 * - RTCA DO-260B examples
 *
 * This validates decoded fields against published reference values, not just
 * CRC validity. It is not a side-by-side dump1090 comparison.
 */

#include <gtest/gtest.h>
#include "modes.h"
#include <cmath>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

// Helper to check floating point equality
bool approx_eq(double a, double b, double eps = 0.01) {
    return std::abs(a - b) < eps;
}

class DecoderValidationTest : public ::testing::Test {};

/**
 * Test Case 1: Aircraft Identification
 * Source: The 1090MHz Riddle, Chapter 4
 * Message: 8D4840D6202CC371C32CE0576098
 * Expected: ICAO=4840D6, Callsign=KLM1023, TC=4 (Category A)
 */
TEST_F(DecoderValidationTest, AircraftIdentification_KLM1023) {
    modes::DecodedMessage msg = modes::decode_hex("8D4840D6202CC371C32CE0576098");

    ASSERT_TRUE(msg.valid) << "CRC validation failed";
    EXPECT_EQ(msg.icao_address, 0x4840D6u);
    EXPECT_EQ(msg.downlink_format, modes::DownlinkFormat::DF17);
    EXPECT_EQ(static_cast<int>(msg.type_code), 4);

    ASSERT_TRUE(msg.identification.has_value());
    EXPECT_EQ(msg.identification->callsign, "KLM1023");
}

/**
 * Test Case 2: Airborne Position (Even Frame)
 * Source: The 1090MHz Riddle, Chapter 6
 * Message: 8D40621D58C382D690C8AC2863A7
 * Expected: ICAO=40621D, Alt=38000ft, CPR Even, TC=11
 */
TEST_F(DecoderValidationTest, AirbornePosition_EvenFrame) {
    modes::DecodedMessage msg = modes::decode_hex("8D40621D58C382D690C8AC2863A7");

    ASSERT_TRUE(msg.valid) << "CRC validation failed";
    EXPECT_EQ(msg.icao_address, 0x40621Du);
    EXPECT_EQ(static_cast<int>(msg.type_code), 11);

    ASSERT_TRUE(msg.position.has_value());
    EXPECT_EQ(msg.position->cpr_format, modes::CPRFormat::EVEN);
    EXPECT_EQ(msg.position->altitude, 38000);  // 38000 feet
    EXPECT_FALSE(msg.position->altitude_gnss);  // Barometric
}

/**
 * Test Case 3: Airborne Position (Odd Frame)
 * Source: The 1090MHz Riddle, Chapter 6
 * Message: 8D40621D58C386435CC412692AD6
 * Expected: ICAO=40621D, Alt=38000ft, CPR Odd, TC=11
 */
TEST_F(DecoderValidationTest, AirbornePosition_OddFrame) {
    modes::DecodedMessage msg = modes::decode_hex("8D40621D58C386435CC412692AD6");

    ASSERT_TRUE(msg.valid) << "CRC validation failed";
    EXPECT_EQ(msg.icao_address, 0x40621Du);

    ASSERT_TRUE(msg.position.has_value());
    EXPECT_EQ(msg.position->cpr_format, modes::CPRFormat::ODD);
    EXPECT_EQ(msg.position->altitude, 38000);
}

/**
 * Test Case 4: Airborne Velocity (Ground Speed)
 * Source: The 1090MHz Riddle, Chapter 5
 * Message: 8D485020994409940838175B284F
 * Expected: ICAO=485020, GS=159kt, Heading=182.88°, VR=-832 ft/min
 */
TEST_F(DecoderValidationTest, AirborneVelocity_GroundSpeed) {
    modes::DecodedMessage msg = modes::decode_hex("8D485020994409940838175B284F");

    ASSERT_TRUE(msg.valid) << "CRC validation failed";
    EXPECT_EQ(msg.icao_address, 0x485020u);
    EXPECT_EQ(static_cast<int>(msg.type_code), 19);

    ASSERT_TRUE(msg.velocity.has_value());
    EXPECT_EQ(msg.velocity->type, modes::VelocityType::GROUND_SPEED);

    // Ground speed should be approximately 159 knots
    ASSERT_TRUE(msg.velocity->ground_speed.has_value());
    EXPECT_TRUE(approx_eq(*msg.velocity->ground_speed, 159.0, 2.0))
        << "Ground speed: " << *msg.velocity->ground_speed << " (expected ~159)";

    // Heading should be approximately 182.88 degrees
    ASSERT_TRUE(msg.velocity->heading.has_value());
    EXPECT_TRUE(approx_eq(*msg.velocity->heading, 182.88, 1.0))
        << "Heading: " << *msg.velocity->heading << " (expected ~182.88)";

    // Vertical rate should be -832 ft/min (descending)
    ASSERT_TRUE(msg.velocity->vertical_rate.has_value());
    EXPECT_TRUE(approx_eq(*msg.velocity->vertical_rate, -832.0, 100.0))
        << "Vertical rate: " << *msg.velocity->vertical_rate << " (expected ~-832)";
}

/**
 * Test Case 5: Another Velocity Message
 * Source: The 1090MHz Riddle
 * Message: 8DA05F219B06B6AF189400CBC33F
 * Validates velocity decoding on a different aircraft
 */
TEST_F(DecoderValidationTest, AirborneVelocity_A05F21) {
    modes::DecodedMessage msg = modes::decode_hex("8DA05F219B06B6AF189400CBC33F");

    ASSERT_TRUE(msg.valid) << "CRC validation failed";
    EXPECT_EQ(msg.icao_address, 0xA05F21u);
    EXPECT_EQ(static_cast<int>(msg.type_code), 19);

    ASSERT_TRUE(msg.velocity.has_value());

    // Should have vertical rate
    EXPECT_TRUE(msg.velocity->vertical_rate.has_value());
    if (msg.velocity->vertical_rate.has_value()) {
        // Verify it's a reasonable value (not obviously wrong)
        EXPECT_GT(*msg.velocity->vertical_rate, -10000);
        EXPECT_LT(*msg.velocity->vertical_rate, 10000);
    }
}

/**
 * Test Case 6: CRC Rejection
 * Modified message - should fail CRC
 */
TEST_F(DecoderValidationTest, CRCRejection_ModifiedMessage) {
    // Original: 8D4840D6202CC371C32CE0576098
    // Modified last byte: 98 -> 99
    modes::DecodedMessage msg = modes::decode_hex("8D4840D6202CC371C32CE0576099");

    EXPECT_FALSE(msg.valid) << "Should reject invalid CRC";
}

/**
 * Test Case 7: ICAO Address Extraction
 * Verify correct byte extraction for multiple messages
 */
TEST_F(DecoderValidationTest, ICAOAddressExtraction) {
    struct TestCase {
        std::string hex;
        uint32_t expected_icao;
    };

    std::vector<TestCase> cases = {
        {"8D4840D6202CC371C32CE0576098", 0x4840D6},
        {"8D40621D58C382D690C8AC2863A7", 0x40621D},
        {"8DA05F219B06B6AF189400CBC33F", 0xA05F21},
        {"8D485020994409940838175B284F", 0x485020},
    };

    for (const auto& tc : cases) {
        modes::DecodedMessage msg = modes::decode_hex(tc.hex);
        ASSERT_TRUE(msg.valid) << "CRC failed for " << tc.hex;
        EXPECT_EQ(msg.icao_address, tc.expected_icao)
            << "ICAO mismatch for " << tc.hex;
    }
}

/**
 * Test Case 8: Type Code Extraction
 */
TEST_F(DecoderValidationTest, TypeCodeExtraction) {
    // TC 4 = Aircraft ID Category A
    modes::DecodedMessage id_msg = modes::decode_hex("8D4840D6202CC371C32CE0576098");
    ASSERT_TRUE(id_msg.valid);
    EXPECT_EQ(static_cast<int>(id_msg.type_code), 4);

    // TC 11 = Airborne Position
    modes::DecodedMessage pos_msg = modes::decode_hex("8D40621D58C382D690C8AC2863A7");
    ASSERT_TRUE(pos_msg.valid);
    EXPECT_EQ(static_cast<int>(pos_msg.type_code), 11);

    // TC 19 = Airborne Velocity
    modes::DecodedMessage vel_msg = modes::decode_hex("8D485020994409940838175B284F");
    ASSERT_TRUE(vel_msg.valid);
    EXPECT_EQ(static_cast<int>(vel_msg.type_code), 19);
}

/**
 * Test Case 9: CPR Global Position Decode
 * Using known even/odd pair that should decode to a specific location
 * Source: The 1090MHz Riddle, Chapter 6
 */
TEST_F(DecoderValidationTest, CPRGlobalDecode) {
    // Even frame
    modes::DecodedMessage even_msg = modes::decode_hex("8D40621D58C382D690C8AC2863A7");
    // Odd frame
    modes::DecodedMessage odd_msg = modes::decode_hex("8D40621D58C386435CC412692AD6");

    ASSERT_TRUE(even_msg.valid);
    ASSERT_TRUE(odd_msg.valid);
    ASSERT_TRUE(even_msg.position.has_value());
    ASSERT_TRUE(odd_msg.position.has_value());

    // Attempt global decode
    modes::AirbornePosition even_pos = *even_msg.position;
    modes::AirbornePosition odd_pos = *odd_msg.position;

    bool success = modes::decode_cpr_global(even_pos, odd_pos);

    ASSERT_TRUE(success);
    ASSERT_TRUE(even_pos.latitude.has_value());
    ASSERT_TRUE(even_pos.longitude.has_value());

    // Expected position: approximately 52.26°N, 3.92°E (over Netherlands)
    // Allow reasonable tolerance
    double lat = *even_pos.latitude;
    double lon = *even_pos.longitude;

    EXPECT_GT(lat, 50.0) << "Latitude too low";
    EXPECT_LT(lat, 55.0) << "Latitude too high";
    EXPECT_GT(lon, 2.0) << "Longitude too low";
    EXPECT_LT(lon, 6.0) << "Longitude too high";
}

/**
 * Summary test - count how many reference messages pass CRC validation.
 * Field-level correctness is asserted by the tests above.
 */
TEST_F(DecoderValidationTest, ReferenceMessagesPassCRC) {
    std::vector<std::string> reference_messages = {
        "8D4840D6202CC371C32CE0576098",  // ID
        "8D40621D58C382D690C8AC2863A7",  // Position
        "8D40621D58C386435CC412692AD6",  // Position
        "8D485020994409940838175B284F",  // Velocity
        "8DA05F219B06B6AF189400CBC33F",  // Velocity
    };

    int valid_count = 0;
    for (const auto& hex : reference_messages) {
        modes::DecodedMessage msg = modes::decode_hex(hex);
        if (msg.valid) valid_count++;
    }

    EXPECT_EQ(valid_count, static_cast<int>(reference_messages.size()))
        << "Not all reference messages decoded successfully";

    std::cout << "CRC validation: " << valid_count << "/"
              << reference_messages.size() << " reference messages accepted\n";
}
