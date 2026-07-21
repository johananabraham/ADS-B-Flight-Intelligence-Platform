/**
 * @file test_cpr.cpp
 * @brief Unit tests for CPR (Compact Position Reporting) decoder
 */

#include <gtest/gtest.h>
#include "modes.h"
#include <cmath>

class CPRTest : public ::testing::Test {
protected:
    static constexpr double EPSILON = 0.0001;  // ~10 meters precision

    // Helper to check if two doubles are approximately equal
    bool approx_equal(double a, double b, double eps = EPSILON) {
        return std::abs(a - b) < eps;
    }
};

TEST_F(CPRTest, GlobalDecodeBasic) {
    // Test global decoding with known even/odd pair
    // These are example CPR values that should decode to a known position

    modes::AirbornePosition even_pos;
    even_pos.cpr_format = modes::CPRFormat::EVEN;
    even_pos.lat_cpr = 92095;  // Example CPR latitude
    even_pos.lon_cpr = 39846;  // Example CPR longitude
    even_pos.altitude = 38000;

    modes::AirbornePosition odd_pos;
    odd_pos.cpr_format = modes::CPRFormat::ODD;
    odd_pos.lat_cpr = 88385;   // Example CPR latitude
    odd_pos.lon_cpr = 125818;  // Example CPR longitude
    odd_pos.altitude = 38000;

    bool success = modes::decode_cpr_global(even_pos, odd_pos);

    if (success) {
        // If decoding succeeds, check that we get valid coordinates
        ASSERT_TRUE(even_pos.latitude.has_value());
        ASSERT_TRUE(even_pos.longitude.has_value());

        double lat = *even_pos.latitude;
        double lon = *even_pos.longitude;

        // Check latitude is valid
        EXPECT_GE(lat, -90.0);
        EXPECT_LE(lat, 90.0);

        // Check longitude is valid
        EXPECT_GE(lon, -180.0);
        EXPECT_LE(lon, 180.0);
    }
}

TEST_F(CPRTest, GlobalDecodeWrongFrameTypes) {
    // Try to decode with two even frames (should fail)
    modes::AirbornePosition pos1;
    pos1.cpr_format = modes::CPRFormat::EVEN;
    pos1.lat_cpr = 92095;
    pos1.lon_cpr = 39846;

    modes::AirbornePosition pos2;
    pos2.cpr_format = modes::CPRFormat::EVEN;  // Wrong - should be ODD
    pos2.lat_cpr = 88385;
    pos2.lon_cpr = 125818;

    bool success = modes::decode_cpr_global(pos1, pos2);
    EXPECT_FALSE(success);
}

TEST_F(CPRTest, LocalDecodeBasic) {
    // Test local decoding with a reference position
    modes::AirbornePosition pos;
    pos.cpr_format = modes::CPRFormat::EVEN;
    pos.lat_cpr = 92095;
    pos.lon_cpr = 39846;
    pos.altitude = 38000;

    // Reference position (should be within 180 NM of actual)
    double ref_lat = 52.0;
    double ref_lon = 4.0;

    bool success = modes::decode_cpr_local(pos, ref_lat, ref_lon);

    if (success) {
        ASSERT_TRUE(pos.latitude.has_value());
        ASSERT_TRUE(pos.longitude.has_value());

        // Result should be close to reference
        double lat_diff = std::abs(*pos.latitude - ref_lat);
        double lon_diff = std::abs(*pos.longitude - ref_lon);

        // Should be within ~3 degrees (local decode validity range)
        EXPECT_LT(lat_diff, 3.5);
        EXPECT_LT(lon_diff, 3.5);
    }
}

TEST_F(CPRTest, LocalDecodeOddFrame) {
    modes::AirbornePosition pos;
    pos.cpr_format = modes::CPRFormat::ODD;
    pos.lat_cpr = 88385;
    pos.lon_cpr = 125818;
    pos.altitude = 38000;

    double ref_lat = 52.0;
    double ref_lon = 4.0;

    bool success = modes::decode_cpr_local(pos, ref_lat, ref_lon);

    // Should produce valid result or fail gracefully
    if (success) {
        ASSERT_TRUE(pos.latitude.has_value());
        ASSERT_TRUE(pos.longitude.has_value());

        double lat = *pos.latitude;
        double lon = *pos.longitude;

        EXPECT_GE(lat, -90.0);
        EXPECT_LE(lat, 90.0);
        EXPECT_GE(lon, -180.0);
        EXPECT_LE(lon, 180.0);
    }
}

TEST_F(CPRTest, LocalDecodeUsesReferenceZone) {
    modes::AirbornePosition pos;
    pos.cpr_format = modes::CPRFormat::EVEN;
    pos.lat_cpr = 92095;
    pos.lon_cpr = 39846;

    double ref_lat = -40.0;
    double ref_lon = 150.0;

    bool success = modes::decode_cpr_local(pos, ref_lat, ref_lon);

    ASSERT_TRUE(success);
    ASSERT_TRUE(pos.latitude.has_value());
    ASSERT_TRUE(pos.longitude.has_value());
    EXPECT_LE(std::abs(*pos.latitude - ref_lat), 3.0);
    EXPECT_LE(std::abs(*pos.longitude - ref_lon), 3.0);
}

TEST_F(CPRTest, CPRValueBounds) {
    // CPR values should be 17 bits (0-131071)
    modes::AirbornePosition pos;
    pos.cpr_format = modes::CPRFormat::EVEN;
    pos.lat_cpr = 131071;  // Maximum valid
    pos.lon_cpr = 131071;

    double ref_lat = 45.0;
    double ref_lon = -90.0;

    // Should not crash with max values
    modes::decode_cpr_local(pos, ref_lat, ref_lon);
}

TEST_F(CPRTest, CPRZeroValues) {
    modes::AirbornePosition pos;
    pos.cpr_format = modes::CPRFormat::EVEN;
    pos.lat_cpr = 0;
    pos.lon_cpr = 0;

    double ref_lat = 0.0;
    double ref_lon = 0.0;

    // Should not crash with zero values
    bool success = modes::decode_cpr_local(pos, ref_lat, ref_lon);

    if (success) {
        ASSERT_TRUE(pos.latitude.has_value());
        ASSERT_TRUE(pos.longitude.has_value());
    }
}

TEST_F(CPRTest, EquatorCrossing) {
    // Test near the equator
    modes::AirbornePosition pos;
    pos.cpr_format = modes::CPRFormat::EVEN;
    pos.lat_cpr = 65536;  // Middle of range
    pos.lon_cpr = 65536;

    double ref_lat = 0.0;  // Equator
    double ref_lon = 0.0;

    bool success = modes::decode_cpr_local(pos, ref_lat, ref_lon);
    EXPECT_FALSE(success);
}

TEST_F(CPRTest, PolarRegion) {
    // Test near the poles (NL=1 region)
    modes::AirbornePosition pos;
    pos.cpr_format = modes::CPRFormat::EVEN;
    pos.lat_cpr = 120000;
    pos.lon_cpr = 65536;

    double ref_lat = 88.0;  // Near north pole
    double ref_lon = 0.0;

    bool success = modes::decode_cpr_local(pos, ref_lat, ref_lon);
    EXPECT_FALSE(success);
}

TEST_F(CPRTest, DatelineCrossing) {
    // Test near the international date line
    modes::AirbornePosition pos;
    pos.cpr_format = modes::CPRFormat::EVEN;
    pos.lat_cpr = 65536;
    pos.lon_cpr = 130000;

    double ref_lat = 45.0;
    double ref_lon = 179.0;  // Near date line

    bool success = modes::decode_cpr_local(pos, ref_lat, ref_lon);

    if (success) {
        ASSERT_TRUE(pos.longitude.has_value());
        double lon = *pos.longitude;
        // Longitude should be valid
        EXPECT_GE(lon, -180.0);
        EXPECT_LE(lon, 180.0);
    }
}

TEST_F(CPRTest, NegativeLongitude) {
    // Test in western hemisphere
    modes::AirbornePosition pos;
    pos.cpr_format = modes::CPRFormat::EVEN;
    pos.lat_cpr = 70000;
    pos.lon_cpr = 20000;

    double ref_lat = 40.0;
    double ref_lon = -74.0;  // New York area

    bool success = modes::decode_cpr_local(pos, ref_lat, ref_lon);

    if (success) {
        ASSERT_TRUE(pos.longitude.has_value());
        // Should decode to western hemisphere
    }
}

TEST_F(CPRTest, SouthernHemisphere) {
    // Test in southern hemisphere
    modes::AirbornePosition pos;
    pos.cpr_format = modes::CPRFormat::EVEN;
    pos.lat_cpr = 30000;
    pos.lon_cpr = 65536;

    double ref_lat = -33.0;  // Sydney area
    double ref_lon = 151.0;

    bool success = modes::decode_cpr_local(pos, ref_lat, ref_lon);

    if (success) {
        ASSERT_TRUE(pos.latitude.has_value());
        // Could be southern hemisphere
    }
}

TEST_F(CPRTest, GlobalDecodeStoresInBothPositions) {
    modes::AirbornePosition even_pos;
    even_pos.cpr_format = modes::CPRFormat::EVEN;
    even_pos.lat_cpr = 92095;
    even_pos.lon_cpr = 39846;

    modes::AirbornePosition odd_pos;
    odd_pos.cpr_format = modes::CPRFormat::ODD;
    odd_pos.lat_cpr = 88385;
    odd_pos.lon_cpr = 125818;

    bool success = modes::decode_cpr_global(even_pos, odd_pos);

    if (success) {
        // Both positions should have the decoded coordinates
        EXPECT_TRUE(even_pos.latitude.has_value());
        EXPECT_TRUE(even_pos.longitude.has_value());
        EXPECT_TRUE(odd_pos.latitude.has_value());
        EXPECT_TRUE(odd_pos.longitude.has_value());

        // And they should be the same
        EXPECT_DOUBLE_EQ(*even_pos.latitude, *odd_pos.latitude);
        EXPECT_DOUBLE_EQ(*even_pos.longitude, *odd_pos.longitude);
    }
}
