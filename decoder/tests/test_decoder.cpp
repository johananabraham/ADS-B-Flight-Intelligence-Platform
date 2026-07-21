/**
 * @file test_decoder.cpp
 * @brief Unit tests for Mode S message decoder
 */

#include <gtest/gtest.h>
#include "modes.h"
#include <string>

class DecoderTest : public ::testing::Test {
protected:
    // Known test messages with expected values
};

TEST_F(DecoderTest, DecodeDF17Identification) {
    // Aircraft identification message
    // ICAO: 4840D6, Callsign: KLM1023
    modes::DecodedMessage msg = modes::decode_hex("8D4840D6202CC371C32CE0576098");

    EXPECT_TRUE(msg.valid);
    EXPECT_EQ(msg.downlink_format, modes::DownlinkFormat::DF17);
    EXPECT_EQ(msg.icao_address, 0x4840D6u);

    // Type code should be 1-4 for identification
    EXPECT_GE(static_cast<int>(msg.type_code), 1);
    EXPECT_LE(static_cast<int>(msg.type_code), 4);

    ASSERT_TRUE(msg.identification.has_value());
    // Callsign should be decoded
    EXPECT_FALSE(msg.identification->callsign.empty());
}

TEST_F(DecoderTest, DecodeDF17Position) {
    // Airborne position message
    modes::DecodedMessage msg = modes::decode_hex("8D40621D58C382D690C8AC2863A7");

    EXPECT_TRUE(msg.valid);
    EXPECT_EQ(msg.downlink_format, modes::DownlinkFormat::DF17);
    EXPECT_EQ(msg.icao_address, 0x40621Du);

    // Type code should be 9-18 or 20-22 for airborne position
    int tc = static_cast<int>(msg.type_code);
    bool is_position = (tc >= 9 && tc <= 18) || (tc >= 20 && tc <= 22);
    EXPECT_TRUE(is_position);

    ASSERT_TRUE(msg.position.has_value());
    // Should have altitude
    EXPECT_NE(msg.position->altitude, 0);
    // Should have CPR values
    EXPECT_LT(msg.position->lat_cpr, 131072u);  // 2^17
    EXPECT_LT(msg.position->lon_cpr, 131072u);
}

TEST_F(DecoderTest, DecodeDF17Velocity) {
    // Airborne velocity message
    modes::DecodedMessage msg = modes::decode_hex("8D485020994409940838175B284F");

    EXPECT_TRUE(msg.valid);
    EXPECT_EQ(msg.downlink_format, modes::DownlinkFormat::DF17);

    // Type code 19 for velocity
    EXPECT_EQ(static_cast<int>(msg.type_code), 19);

    ASSERT_TRUE(msg.velocity.has_value());
    // Should have some velocity data
    bool has_velocity = msg.velocity->ground_speed.has_value() ||
                       msg.velocity->east_west_velocity.has_value();
    EXPECT_TRUE(has_velocity);
}

TEST_F(DecoderTest, InvalidCRCMessage) {
    // Message with modified CRC (invalid)
    modes::DecodedMessage msg = modes::decode_hex("8D4840D6202CC371C32CE0576099");

    EXPECT_FALSE(msg.valid);
}

TEST_F(DecoderTest, HexDecodeInvalidCharacters) {
    // Invalid hex characters should fail gracefully
    modes::DecodedMessage msg = modes::decode_hex("GGHHIIJJ");
    EXPECT_FALSE(msg.valid);
}

TEST_F(DecoderTest, HexDecodeOddLength) {
    // Odd length hex string
    modes::DecodedMessage msg = modes::decode_hex("8D4840D620");
    // Should handle gracefully (might decode partial or fail)
    // Just shouldn't crash
}

TEST_F(DecoderTest, HexDecodeEmpty) {
    modes::DecodedMessage msg = modes::decode_hex("");
    EXPECT_FALSE(msg.valid);
}

TEST_F(DecoderTest, HexDecodeTooShort) {
    modes::DecodedMessage msg = modes::decode_hex("8D48");
    EXPECT_FALSE(msg.valid);
}

TEST_F(DecoderTest, DownlinkFormatExtraction) {
    // DF17 message - first 5 bits should be 17 (10001)
    // 0x8D = 10001101, first 5 bits = 10001 = 17
    modes::DecodedMessage msg = modes::decode_hex("8D4840D6202CC371C32CE0576098");
    EXPECT_EQ(msg.downlink_format, modes::DownlinkFormat::DF17);
}

TEST_F(DecoderTest, ICAOAddressExtraction) {
    // ICAO is bytes 1-3 (bits 8-31)
    modes::DecodedMessage msg = modes::decode_hex("8D4840D6202CC371C32CE0576098");
    EXPECT_EQ(msg.icao_address, 0x4840D6u);
}

TEST_F(DecoderTest, AltitudeDecoding) {
    // Test altitude decoding from position message
    modes::DecodedMessage msg = modes::decode_hex("8D40621D58C382D690C8AC2863A7");

    ASSERT_TRUE(msg.position.has_value());
    // Altitude should be reasonable (between -1000 and 60000 feet)
    EXPECT_GT(msg.position->altitude, -1000);
    EXPECT_LT(msg.position->altitude, 60000);
}

TEST_F(DecoderTest, RawMessageStorage) {
    modes::DecodedMessage msg = modes::decode_hex("8D4840D6202CC371C32CE0576098");

    EXPECT_EQ(msg.msg_len, 14u);  // 112 bits = 14 bytes
    EXPECT_EQ(msg.raw_msg[0], 0x8Du);
    EXPECT_EQ(msg.raw_msg[1], 0x48u);
    EXPECT_EQ(msg.raw_msg[2], 0x40u);
    EXPECT_EQ(msg.raw_msg[3], 0xD6u);
}

TEST_F(DecoderTest, DFToStringNotNull) {
    EXPECT_NE(modes::df_to_string(modes::DownlinkFormat::DF17), nullptr);
    EXPECT_NE(modes::df_to_string(modes::DownlinkFormat::DF11), nullptr);
    EXPECT_NE(modes::df_to_string(modes::DownlinkFormat::UNKNOWN), nullptr);
}

TEST_F(DecoderTest, TCToStringNotNull) {
    EXPECT_NE(modes::tc_to_string(modes::TypeCode::AIRCRAFT_ID_CAT_A), nullptr);
    EXPECT_NE(modes::tc_to_string(modes::TypeCode::AIRBORNE_VELOCITY), nullptr);
    EXPECT_NE(modes::tc_to_string(modes::TypeCode::UNKNOWN), nullptr);
}

TEST_F(DecoderTest, VelocityTypeDetection) {
    modes::DecodedMessage msg = modes::decode_hex("8D485020994409940838175B284F");

    ASSERT_TRUE(msg.valid);
    ASSERT_TRUE(msg.velocity.has_value());
    EXPECT_NE(msg.velocity->type, modes::VelocityType::UNKNOWN);
}

TEST_F(DecoderTest, MultipleValidMessages) {
    std::vector<std::string> messages = {
        "8D4840D6202CC371C32CE0576098",
        "8D40621D58C382D690C8AC2863A7",
        "8D485020994409940838175B284F",
        "8DA05F219B06B6AF189400CBC33F",
        "8D40621D58C386435CC412692AD6",
    };

    for (const auto& hex : messages) {
        modes::DecodedMessage msg = modes::decode_hex(hex);
        EXPECT_TRUE(msg.valid) << "Failed for: " << hex;
        EXPECT_EQ(msg.downlink_format, modes::DownlinkFormat::DF17);
    }
}
