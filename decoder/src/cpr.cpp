/**
 * @file cpr.cpp
 * @brief Compact Position Reporting (CPR) decoder implementation
 *
 * CPR encodes latitude and longitude using 17 bits each, requiring either:
 * - Global decoding: combining even and odd frames
 * - Local decoding: using a known reference position
 *
 * Reference: RTCA DO-260B, ICAO Annex 10 Volume IV
 */

#include "modes.h"
#include <cmath>
#include <algorithm>

namespace modes {

// Number of latitude zones
constexpr int NZ = 15;

// CPR latitude zone size for even frames
constexpr double D_LAT_EVEN = 360.0 / (4.0 * NZ);  // 6 degrees
// CPR latitude zone size for odd frames
constexpr double D_LAT_ODD = 360.0 / (4.0 * NZ - 1.0);  // ~6.1 degrees

// Maximum allowed time between even/odd frames (10 seconds)
// Note: Used when implementing timestamp-based frame selection
[[maybe_unused]] constexpr int MAX_CPR_INTERVAL_SEC = 10;

/**
 * @brief Calculate NL (Number of Longitude zones) for a given latitude
 *
 * NL is the number of longitude zones at a given latitude.
 * At the equator, NL=59. Near the poles, NL=1.
 */
static int calc_nl(double lat) {
    // Handle edge cases
    if (lat < 0) lat = -lat;
    if (lat >= 87.0) return 1;

    // NL formula from RTCA DO-260B
    double tmp = 1.0 - std::cos(M_PI / (2.0 * NZ));
    double cos_lat = std::cos(lat * M_PI / 180.0);
    double nl = std::floor(2.0 * M_PI /
                           std::acos(1.0 - tmp / (cos_lat * cos_lat)));

    return static_cast<int>(nl);
}

/**
 * @brief Modulo function that always returns positive result
 */
static double mod(double x, double y) {
    double result = std::fmod(x, y);
    if (result < 0) result += y;
    return result;
}

/**
 * @brief Decode global position from even and odd CPR frames
 *
 * This function implements the global CPR decoding algorithm that
 * combines an even frame and an odd frame to determine position.
 *
 * The algorithm:
 * 1. Calculate latitude index j
 * 2. Calculate latitudes for even and odd frames
 * 3. Check that NL values are consistent
 * 4. Calculate longitude index m
 * 5. Calculate longitude
 *
 * @param even_pos Even frame position data
 * @param odd_pos Odd frame position data
 * @param ref_lat Reference latitude (optional, for disambiguation)
 * @param ref_lon Reference longitude (optional, for disambiguation)
 * @return true if decoding succeeded
 */
bool decode_cpr_global(AirbornePosition& even_pos, AirbornePosition& odd_pos,
                       [[maybe_unused]] double ref_lat, [[maybe_unused]] double ref_lon) {

    // Verify we have the right frame types
    if (even_pos.cpr_format != CPRFormat::EVEN ||
        odd_pos.cpr_format != CPRFormat::ODD) {
        return false;
    }

    // Convert CPR values to fractions (0.0 to 1.0)
    double lat_cpr_even = static_cast<double>(even_pos.lat_cpr) / 131072.0;  // 2^17
    double lon_cpr_even = static_cast<double>(even_pos.lon_cpr) / 131072.0;
    double lat_cpr_odd = static_cast<double>(odd_pos.lat_cpr) / 131072.0;
    double lon_cpr_odd = static_cast<double>(odd_pos.lon_cpr) / 131072.0;

    // Step 1: Calculate latitude index j
    double j = std::floor(59.0 * lat_cpr_even - 60.0 * lat_cpr_odd + 0.5);

    // Step 2: Calculate latitude for even and odd frames
    double lat_even = D_LAT_EVEN * (mod(j, 60.0) + lat_cpr_even);
    double lat_odd = D_LAT_ODD * (mod(j, 59.0) + lat_cpr_odd);

    // Adjust for southern hemisphere
    if (lat_even >= 270.0) lat_even -= 360.0;
    if (lat_odd >= 270.0) lat_odd -= 360.0;

    // Step 3: Check NL consistency
    int nl_even = calc_nl(lat_even);
    int nl_odd = calc_nl(lat_odd);

    if (nl_even != nl_odd) {
        // NL mismatch - frames are from different latitude zones
        // This can happen during zone transitions
        return false;
    }

    // Step 4: Determine which frame is more recent and use that latitude
    // For now, we use the even frame latitude
    // In production, you'd compare timestamps
    double lat = lat_even;
    double lon;

    // Use NL from the chosen latitude
    int nl = nl_even;

    // Step 5: Calculate longitude index m and longitude
    // The formula differs depending on which frame is more recent
    // Assuming even frame is more recent:
    double ni = std::max(nl, 1);
    double d_lon = 360.0 / ni;

    double m = std::floor(lon_cpr_even * (nl - 1.0) - lon_cpr_odd * nl + 0.5);
    lon = d_lon * (mod(m, ni) + lon_cpr_even);

    // Adjust longitude to -180 to +180 range
    if (lon > 180.0) lon -= 360.0;

    // Validate the result
    if (lat < -90.0 || lat > 90.0 || lon < -180.0 || lon > 180.0) {
        return false;
    }

    // Store the decoded position in both frames
    even_pos.latitude = lat;
    even_pos.longitude = lon;
    odd_pos.latitude = lat;
    odd_pos.longitude = lon;

    return true;
}

/**
 * @brief Decode local position using a reference position
 *
 * Local decoding is faster and only requires a single CPR frame,
 * but needs a known reference position within 180 NM.
 *
 * @param pos Position to decode
 * @param ref_lat Reference latitude
 * @param ref_lon Reference longitude
 * @return true if decoding succeeded
 */
bool decode_cpr_local(AirbornePosition& pos, double ref_lat, double ref_lon) {

    // Convert CPR values to fractions
    double lat_cpr = static_cast<double>(pos.lat_cpr) / 131072.0;
    double lon_cpr = static_cast<double>(pos.lon_cpr) / 131072.0;

    // Determine D_LAT based on frame type
    double d_lat;
    if (pos.cpr_format == CPRFormat::EVEN) {
        d_lat = D_LAT_EVEN;
    } else {
        d_lat = D_LAT_ODD;
    }

    // Calculate latitude zone index j
    double j = std::floor(ref_lat / d_lat) +
               std::floor(mod(ref_lat, d_lat) / d_lat - lat_cpr + 0.5);

    // Calculate latitude
    double lat = d_lat * (j + lat_cpr);

    // Calculate NL for this latitude
    int nl = calc_nl(lat);

    // Adjust NL for odd frames
    if (pos.cpr_format == CPRFormat::ODD) {
        nl = std::max(nl - 1, 1);
    }

    // Calculate longitude zone size
    double d_lon = (nl > 0) ? 360.0 / nl : 360.0;

    // Calculate longitude zone index m
    double m = std::floor(ref_lon / d_lon) +
               std::floor(mod(ref_lon, d_lon) / d_lon - lon_cpr + 0.5);

    // Calculate longitude
    double lon = d_lon * (m + lon_cpr);

    // Adjust to -180 to +180 range
    if (lon > 180.0) lon -= 360.0;
    if (lon < -180.0) lon += 360.0;

    // Validate
    if (lat < -90.0 || lat > 90.0 || lon < -180.0 || lon > 180.0) {
        return false;
    }

    // Check distance from reference (should be within ~180 NM for validity)
    // This is approximately 3 degrees at mid-latitudes
    double lat_diff = std::abs(lat - ref_lat);
    double lon_diff = std::abs(lon - ref_lon);
    if (lon_diff > 180.0) lon_diff = 360.0 - lon_diff;

    // Rough check: should be within about 3 degrees
    if (lat_diff > 3.0 || lon_diff > 3.0) {
        return false;
    }

    pos.latitude = lat;
    pos.longitude = lon;

    return true;
}

} // namespace modes
