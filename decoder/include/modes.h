/**
 * @file modes.h
 * @brief Mode S / ADS-B message decoder library
 *
 * This library decodes Mode S transponder messages, specifically focusing on
 * DF17 (ADS-B) messages containing aircraft identification, position, and velocity.
 */

#ifndef MODES_H
#define MODES_H

#include <cstdint>
#include <cstddef>
#include <string>
#include <optional>

namespace modes {

// Mode S message lengths
constexpr size_t SHORT_MSG_BYTES = 7;   // 56 bits - DF0, DF4, DF5, DF11
constexpr size_t LONG_MSG_BYTES = 14;   // 112 bits - DF16, DF17, DF18, DF19, DF20, DF21

// Downlink Format types
enum class DownlinkFormat : uint8_t {
    DF0  = 0,   // Short air-air surveillance
    DF4  = 4,   // Surveillance altitude reply
    DF5  = 5,   // Surveillance identity reply
    DF11 = 11,  // All-call reply
    DF16 = 16,  // Long air-air surveillance
    DF17 = 17,  // Extended squitter (ADS-B)
    DF18 = 18,  // Extended squitter (non-transponder)
    DF19 = 19,  // Military extended squitter
    DF20 = 20,  // Comm-B altitude reply
    DF21 = 21,  // Comm-B identity reply
    DF24 = 24,  // Comm-D (ELM)
    UNKNOWN = 255
};

// ADS-B Type Code categories (within DF17 ME field)
enum class TypeCode : uint8_t {
    AIRCRAFT_ID_CAT_D = 1,   // Aircraft identification (category D)
    AIRCRAFT_ID_CAT_C = 2,   // Aircraft identification (category C)
    AIRCRAFT_ID_CAT_B = 3,   // Aircraft identification (category B)
    AIRCRAFT_ID_CAT_A = 4,   // Aircraft identification (category A)
    SURFACE_POS_5 = 5,       // Surface position
    SURFACE_POS_6 = 6,
    SURFACE_POS_7 = 7,
    SURFACE_POS_8 = 8,
    AIRBORNE_POS_9 = 9,      // Airborne position (Baro Alt)
    AIRBORNE_POS_10 = 10,
    AIRBORNE_POS_11 = 11,
    AIRBORNE_POS_12 = 12,
    AIRBORNE_POS_13 = 13,
    AIRBORNE_POS_14 = 14,
    AIRBORNE_POS_15 = 15,
    AIRBORNE_POS_16 = 16,
    AIRBORNE_POS_17 = 17,
    AIRBORNE_POS_18 = 18,
    AIRBORNE_VELOCITY = 19,  // Airborne velocity
    AIRBORNE_POS_20 = 20,    // Airborne position (GNSS Height)
    AIRBORNE_POS_21 = 21,
    AIRBORNE_POS_22 = 22,
    RESERVED = 23,
    SURFACE_SYSTEM_STATUS = 24,
    RESERVED_25 = 25,
    RESERVED_26 = 26,
    RESERVED_27 = 27,
    AIRCRAFT_STATUS = 28,    // Emergency/priority status
    TARGET_STATE = 29,       // Target state and status
    RESERVED_30 = 30,
    AIRCRAFT_OP_STATUS = 31, // Aircraft operational status
    UNKNOWN = 255
};

// Aircraft category for identification messages
enum class AircraftCategory : uint8_t {
    NO_INFO = 0,
    LIGHT = 1,          // < 15500 lbs
    MEDIUM_1 = 2,       // 15500 to 75000 lbs
    MEDIUM_2 = 3,       // 75000 to 300000 lbs
    HIGH_VORTEX = 4,    // High vortex large
    HEAVY = 5,          // > 300000 lbs
    HIGH_PERF = 6,      // High performance
    ROTORCRAFT = 7,
    GLIDER = 8,
    LIGHTER_THAN_AIR = 9,
    PARACHUTIST = 10,
    ULTRALIGHT = 11,
    UAV = 12,
    SPACE = 13,
    SURFACE_EMERGENCY = 14,
    SURFACE_SERVICE = 15,
    POINT_OBSTACLE = 16,
    CLUSTER_OBSTACLE = 17,
    LINE_OBSTACLE = 18,
    UNKNOWN = 255
};

// Velocity type
enum class VelocityType : uint8_t {
    GROUND_SPEED = 1,   // Ground speed + heading
    AIRSPEED = 2,       // Airspeed + heading
    UNKNOWN = 255
};

// CPR frame type (even/odd)
enum class CPRFormat : uint8_t {
    EVEN = 0,
    ODD = 1
};

/**
 * @brief Decoded aircraft identification
 */
struct AircraftIdentification {
    std::string callsign;           // 8-character callsign
    AircraftCategory category;
};

/**
 * @brief Decoded airborne position
 */
struct AirbornePosition {
    bool surveillance_status;       // Surveillance status
    bool single_antenna;            // Single antenna flag
    int32_t altitude;               // Altitude in feet (barometric or GNSS)
    bool altitude_gnss;             // true if GNSS altitude, false if barometric
    uint32_t time_flag;             // UTC sync flag
    CPRFormat cpr_format;           // Even (0) or Odd (1)
    uint32_t lat_cpr;               // CPR encoded latitude (17 bits)
    uint32_t lon_cpr;               // CPR encoded longitude (17 bits)

    // Decoded position (only valid after combining even+odd frames)
    std::optional<double> latitude;
    std::optional<double> longitude;
};

/**
 * @brief Decoded airborne velocity
 */
struct AirborneVelocity {
    VelocityType type;
    bool intent_change;             // Intent change flag
    bool ifr_capability;            // IFR capability
    uint8_t nav_uncertainty;        // Navigation uncertainty category

    // Ground speed components (type 1)
    std::optional<double> east_west_velocity;   // knots, positive = east
    std::optional<double> north_south_velocity; // knots, positive = north

    // Computed values
    std::optional<double> ground_speed;         // knots
    std::optional<double> heading;              // degrees (0-360)

    // Vertical rate
    std::optional<int32_t> vertical_rate;       // feet/min, positive = climbing
    bool vertical_rate_source_baro;             // true = barometric, false = GNSS

    // Altitude difference (GNSS - Baro)
    std::optional<int32_t> gnss_baro_diff;      // feet
};

/**
 * @brief Complete decoded Mode S message
 */
struct DecodedMessage {
    bool valid;                     // CRC check passed
    DownlinkFormat downlink_format;
    uint32_t icao_address;          // 24-bit ICAO aircraft address

    // Message-specific data (only one will be populated based on type)
    std::optional<AircraftIdentification> identification;
    std::optional<AirbornePosition> position;
    std::optional<AirborneVelocity> velocity;

    // Raw data for debugging
    TypeCode type_code;
    uint8_t raw_msg[LONG_MSG_BYTES];
    size_t msg_len;
};

/**
 * @brief Decode a Mode S message from raw bytes
 *
 * @param raw_message Pointer to raw message bytes (hex decoded)
 * @param len Length of message in bytes (7 for short, 14 for long)
 * @return DecodedMessage structure with decoded data
 */
DecodedMessage decode(const uint8_t* raw_message, size_t len);

/**
 * @brief Decode a Mode S message from hex string
 *
 * @param hex_string Hex-encoded message string (e.g., "8D4840D6202CC371C32CE0576098")
 * @return DecodedMessage structure with decoded data
 */
DecodedMessage decode_hex(const std::string& hex_string);

/**
 * @brief Compute global position from even and odd CPR frames
 *
 * @param even_pos Position from even frame
 * @param odd_pos Position from odd frame
 * @param ref_lat Reference latitude for disambiguation (can be 0)
 * @param ref_lon Reference longitude for disambiguation (can be 0)
 * @return true if position was successfully decoded
 */
bool decode_cpr_global(AirbornePosition& even_pos, AirbornePosition& odd_pos,
                       double ref_lat = 0, double ref_lon = 0);

/**
 * @brief Compute local position from a single CPR frame with reference
 *
 * @param pos Position to decode
 * @param ref_lat Reference latitude (known position)
 * @param ref_lon Reference longitude (known position)
 * @return true if position was successfully decoded
 */
bool decode_cpr_local(AirbornePosition& pos, double ref_lat, double ref_lon);

/**
 * @brief Get string representation of downlink format
 */
const char* df_to_string(DownlinkFormat df);

/**
 * @brief Get string representation of type code
 */
const char* tc_to_string(TypeCode tc);

} // namespace modes

#endif // MODES_H
