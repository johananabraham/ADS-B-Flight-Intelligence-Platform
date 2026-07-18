/**
 * @file decoder.cpp
 * @brief Mode S / ADS-B message decoder implementation
 */

#include "modes.h"
#include "crc.h"
#include <cstring>
#include <cmath>
#include <algorithm>

namespace modes {

// ADS-B character set for aircraft identification
// 6-bit values map to characters: A-Z (1-26), 0-9 (48-57), space (32)
static const char ADSB_CHARSET[64] = {
    '#', 'A', 'B', 'C', 'D', 'E', 'F', 'G',  // 0-7
    'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O',  // 8-15
    'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W',  // 16-23
    'X', 'Y', 'Z', '#', '#', '#', '#', '#',  // 24-31
    ' ', '#', '#', '#', '#', '#', '#', '#',  // 32-39
    '#', '#', '#', '#', '#', '#', '#', '#',  // 40-47
    '0', '1', '2', '3', '4', '5', '6', '7',  // 48-55
    '8', '9', '#', '#', '#', '#', '#', '#'   // 56-63
};

/**
 * @brief Convert hex string to bytes
 */
static bool hex_to_bytes(const std::string& hex, uint8_t* out, size_t max_len) {
    if (hex.length() % 2 != 0 || hex.length() / 2 > max_len) {
        return false;
    }

    for (size_t i = 0; i < hex.length(); i += 2) {
        char byte_str[3] = {hex[i], hex[i + 1], '\0'};
        char* end;
        long byte_val = strtol(byte_str, &end, 16);
        if (*end != '\0' || byte_val < 0 || byte_val > 255) {
            return false;
        }
        out[i / 2] = static_cast<uint8_t>(byte_val);
    }

    return true;
}

/**
 * @brief Extract bits from message
 * @param data Message bytes
 * @param start Start bit position (0-indexed from MSB)
 * @param len Number of bits to extract
 * @return Extracted value
 */
static uint32_t get_bits(const uint8_t* data, int start, int len) {
    uint32_t result = 0;

    for (int i = 0; i < len; i++) {
        int bit_pos = start + i;
        int byte_idx = bit_pos / 8;
        int bit_idx = 7 - (bit_pos % 8);

        result = (result << 1) | ((data[byte_idx] >> bit_idx) & 1);
    }

    return result;
}

/**
 * @brief Get downlink format from first byte
 */
static DownlinkFormat get_df(uint8_t first_byte) {
    uint8_t df = first_byte >> 3;

    switch (df) {
        case 0:  return DownlinkFormat::DF0;
        case 4:  return DownlinkFormat::DF4;
        case 5:  return DownlinkFormat::DF5;
        case 11: return DownlinkFormat::DF11;
        case 16: return DownlinkFormat::DF16;
        case 17: return DownlinkFormat::DF17;
        case 18: return DownlinkFormat::DF18;
        case 19: return DownlinkFormat::DF19;
        case 20: return DownlinkFormat::DF20;
        case 21: return DownlinkFormat::DF21;
        case 24: return DownlinkFormat::DF24;
        default: return DownlinkFormat::UNKNOWN;
    }
}

/**
 * @brief Get type code from ME field (bits 33-37)
 */
static TypeCode get_type_code(const uint8_t* data) {
    uint8_t tc = get_bits(data, 32, 5);

    if (tc >= 1 && tc <= 4)   return static_cast<TypeCode>(tc);
    if (tc >= 5 && tc <= 8)   return static_cast<TypeCode>(tc);
    if (tc >= 9 && tc <= 18)  return static_cast<TypeCode>(tc);
    if (tc == 19)             return TypeCode::AIRBORNE_VELOCITY;
    if (tc >= 20 && tc <= 22) return static_cast<TypeCode>(tc);
    if (tc == 28)             return TypeCode::AIRCRAFT_STATUS;
    if (tc == 29)             return TypeCode::TARGET_STATE;
    if (tc == 31)             return TypeCode::AIRCRAFT_OP_STATUS;

    return TypeCode::UNKNOWN;
}

/**
 * @brief Decode aircraft identification (TC 1-4)
 */
static AircraftIdentification decode_identification(const uint8_t* data) {
    AircraftIdentification id;

    // Category is in bits 38-40 (3 bits after type code)
    uint8_t tc = get_bits(data, 32, 5);
    uint8_t ca = get_bits(data, 37, 3);

    // Map type code and category to aircraft category enum
    // TC 1 = Category D (reserved), TC 2 = C, TC 3 = B, TC 4 = A
    // Within each, ca further specifies the type
    switch (tc) {
        case 1: id.category = AircraftCategory::NO_INFO; break;
        case 2:
            switch (ca) {
                case 1: id.category = AircraftCategory::SURFACE_EMERGENCY; break;
                case 3: id.category = AircraftCategory::SURFACE_SERVICE; break;
                case 4:
                case 5:
                case 6:
                case 7: id.category = AircraftCategory::POINT_OBSTACLE; break;
                default: id.category = AircraftCategory::NO_INFO; break;
            }
            break;
        case 3:
            switch (ca) {
                case 1: id.category = AircraftCategory::GLIDER; break;
                case 2: id.category = AircraftCategory::LIGHTER_THAN_AIR; break;
                case 3: id.category = AircraftCategory::PARACHUTIST; break;
                case 4: id.category = AircraftCategory::ULTRALIGHT; break;
                case 6: id.category = AircraftCategory::UAV; break;
                case 7: id.category = AircraftCategory::SPACE; break;
                default: id.category = AircraftCategory::NO_INFO; break;
            }
            break;
        case 4:
            switch (ca) {
                case 1: id.category = AircraftCategory::LIGHT; break;
                case 2: id.category = AircraftCategory::MEDIUM_1; break;
                case 3: id.category = AircraftCategory::MEDIUM_2; break;
                case 4: id.category = AircraftCategory::HIGH_VORTEX; break;
                case 5: id.category = AircraftCategory::HEAVY; break;
                case 6: id.category = AircraftCategory::HIGH_PERF; break;
                case 7: id.category = AircraftCategory::ROTORCRAFT; break;
                default: id.category = AircraftCategory::NO_INFO; break;
            }
            break;
        default:
            id.category = AircraftCategory::UNKNOWN;
            break;
    }

    // Decode 8 characters (6 bits each) starting at bit 40
    // Characters are in bits 40-87 (48 bits total)
    id.callsign.reserve(8);
    for (int i = 0; i < 8; i++) {
        uint8_t char_val = get_bits(data, 40 + i * 6, 6);
        char c = ADSB_CHARSET[char_val];
        if (c != ' ' || !id.callsign.empty()) {
            id.callsign += c;
        }
    }

    // Trim trailing spaces
    while (!id.callsign.empty() && id.callsign.back() == ' ') {
        id.callsign.pop_back();
    }

    return id;
}

/**
 * @brief Decode altitude from encoded value
 * @param alt_code 12-bit altitude code
 * @param q_bit Q bit value (determines 25ft vs 100ft resolution)
 * @return Altitude in feet
 */
static int32_t decode_altitude(uint32_t alt_code, bool q_bit) {
    if (q_bit) {
        // 25-foot resolution
        // Remove the Q bit and decode
        uint32_t n = ((alt_code & 0xFE0) >> 1) | (alt_code & 0x00F);
        return static_cast<int32_t>(n * 25 - 1000);
    } else {
        // 100-foot resolution (Gillham code)
        // This uses Gray code conversion - complex but less common
        // For simplicity, return -1 to indicate unsupported
        return -1;
    }
}

/**
 * @brief Decode airborne position (TC 9-18, 20-22)
 */
static AirbornePosition decode_position(const uint8_t* data) {
    AirbornePosition pos;

    uint8_t tc = get_bits(data, 32, 5);

    // Surveillance status (bits 38-39)
    pos.surveillance_status = get_bits(data, 37, 2) != 0;

    // Single antenna flag (bit 40)
    pos.single_antenna = get_bits(data, 39, 1) != 0;

    // Altitude (bits 41-52, 12 bits)
    uint32_t alt_code = get_bits(data, 40, 12);
    bool q_bit = (alt_code & 0x010) != 0;  // Q bit is bit 4 (counting from 1)
    pos.altitude = decode_altitude(alt_code, q_bit);
    pos.altitude_gnss = (tc >= 20 && tc <= 22);

    // Time flag (bit 53)
    pos.time_flag = get_bits(data, 52, 1);

    // CPR format - F flag (bit 54)
    pos.cpr_format = get_bits(data, 53, 1) == 0 ? CPRFormat::EVEN : CPRFormat::ODD;

    // Encoded latitude (bits 55-71, 17 bits)
    pos.lat_cpr = get_bits(data, 54, 17);

    // Encoded longitude (bits 72-88, 17 bits)
    pos.lon_cpr = get_bits(data, 71, 17);

    // Position will be decoded later when we have both even and odd frames
    pos.latitude = std::nullopt;
    pos.longitude = std::nullopt;

    return pos;
}

/**
 * @brief Decode airborne velocity (TC 19)
 */
static AirborneVelocity decode_velocity(const uint8_t* data) {
    AirborneVelocity vel;

    // Subtype (bits 38-40, 3 bits)
    uint8_t subtype = get_bits(data, 37, 3);

    if (subtype == 1 || subtype == 2) {
        vel.type = VelocityType::GROUND_SPEED;
    } else if (subtype == 3 || subtype == 4) {
        vel.type = VelocityType::AIRSPEED;
    } else {
        vel.type = VelocityType::UNKNOWN;
        return vel;
    }

    // Intent change flag (bit 41)
    vel.intent_change = get_bits(data, 40, 1) != 0;

    // IFR capability (bit 42)
    vel.ifr_capability = get_bits(data, 41, 1) != 0;

    // Navigation uncertainty category (bits 43-45, 3 bits)
    vel.nav_uncertainty = get_bits(data, 42, 3);

    if (subtype == 1 || subtype == 2) {
        // Ground speed - East/West and North/South components

        // Direction EW (bit 46): 0=East, 1=West
        bool ew_dir = get_bits(data, 45, 1) != 0;
        // EW velocity (bits 47-56, 10 bits)
        uint32_t ew_vel = get_bits(data, 46, 10);

        // Direction NS (bit 57): 0=North, 1=South
        bool ns_dir = get_bits(data, 56, 1) != 0;
        // NS velocity (bits 58-67, 10 bits)
        uint32_t ns_vel = get_bits(data, 57, 10);

        if (ew_vel != 0) {
            double ew = static_cast<double>(ew_vel - 1);
            if (subtype == 2) ew *= 4;  // Supersonic: 4 knot resolution
            vel.east_west_velocity = ew_dir ? -ew : ew;
        }

        if (ns_vel != 0) {
            double ns = static_cast<double>(ns_vel - 1);
            if (subtype == 2) ns *= 4;  // Supersonic: 4 knot resolution
            vel.north_south_velocity = ns_dir ? -ns : ns;
        }

        // Compute ground speed and heading
        if (vel.east_west_velocity && vel.north_south_velocity) {
            double ew = *vel.east_west_velocity;
            double ns = *vel.north_south_velocity;
            vel.ground_speed = std::sqrt(ew * ew + ns * ns);
            double hdg = std::atan2(ew, ns) * 180.0 / M_PI;
            if (hdg < 0) hdg += 360.0;
            vel.heading = hdg;
        }
    }

    // Vertical rate source (bit 68): 0=GNSS, 1=Barometric
    vel.vertical_rate_source_baro = get_bits(data, 67, 1) != 0;

    // Vertical rate sign (bit 69): 0=Up, 1=Down
    bool vr_sign = get_bits(data, 68, 1) != 0;

    // Vertical rate (bits 70-78, 9 bits)
    uint32_t vr = get_bits(data, 69, 9);
    if (vr != 0) {
        int32_t rate = (static_cast<int32_t>(vr) - 1) * 64;  // 64 ft/min resolution
        vel.vertical_rate = vr_sign ? -rate : rate;
    }

    // GNSS/Baro altitude difference (bits 80-87)
    bool diff_sign = get_bits(data, 79, 1) != 0;
    uint32_t diff = get_bits(data, 80, 7);
    if (diff != 0) {
        int32_t alt_diff = (static_cast<int32_t>(diff) - 1) * 25;  // 25 ft resolution
        vel.gnss_baro_diff = diff_sign ? -alt_diff : alt_diff;
    }

    return vel;
}

DecodedMessage decode(const uint8_t* raw_message, size_t len) {
    DecodedMessage msg;
    msg.valid = false;
    msg.type_code = TypeCode::UNKNOWN;
    msg.downlink_format = DownlinkFormat::UNKNOWN;
    msg.icao_address = 0;

    // Validate length
    if (len != SHORT_MSG_BYTES && len != LONG_MSG_BYTES) {
        return msg;
    }

    // Copy raw message
    std::memcpy(msg.raw_msg, raw_message, len);
    msg.msg_len = len;

    // Get downlink format
    msg.downlink_format = get_df(raw_message[0]);

    // Validate CRC
    uint8_t df = static_cast<uint8_t>(msg.downlink_format);
    if (!crc::is_valid(raw_message, len, df)) {
        return msg;
    }

    msg.valid = true;

    // Extract ICAO address (bits 9-32, 24 bits)
    msg.icao_address = get_bits(raw_message, 8, 24);

    // For DF17/18, decode the extended squitter
    if (msg.downlink_format == DownlinkFormat::DF17 ||
        msg.downlink_format == DownlinkFormat::DF18) {

        msg.type_code = get_type_code(raw_message);
        uint8_t tc = static_cast<uint8_t>(msg.type_code);

        // Aircraft identification (TC 1-4)
        if (tc >= 1 && tc <= 4) {
            msg.identification = decode_identification(raw_message);
        }
        // Airborne position (TC 9-18, 20-22)
        else if ((tc >= 9 && tc <= 18) || (tc >= 20 && tc <= 22)) {
            msg.position = decode_position(raw_message);
        }
        // Airborne velocity (TC 19)
        else if (tc == 19) {
            msg.velocity = decode_velocity(raw_message);
        }
    }

    return msg;
}

DecodedMessage decode_hex(const std::string& hex_string) {
    uint8_t buffer[LONG_MSG_BYTES];
    size_t len = hex_string.length() / 2;

    if (!hex_to_bytes(hex_string, buffer, LONG_MSG_BYTES)) {
        DecodedMessage msg;
        msg.valid = false;
        return msg;
    }

    return decode(buffer, len);
}

const char* df_to_string(DownlinkFormat df) {
    switch (df) {
        case DownlinkFormat::DF0:  return "DF0 (Short Air-Air Surveillance)";
        case DownlinkFormat::DF4:  return "DF4 (Surveillance Altitude Reply)";
        case DownlinkFormat::DF5:  return "DF5 (Surveillance Identity Reply)";
        case DownlinkFormat::DF11: return "DF11 (All-Call Reply)";
        case DownlinkFormat::DF16: return "DF16 (Long Air-Air Surveillance)";
        case DownlinkFormat::DF17: return "DF17 (Extended Squitter / ADS-B)";
        case DownlinkFormat::DF18: return "DF18 (Extended Squitter Non-Transponder)";
        case DownlinkFormat::DF19: return "DF19 (Military Extended Squitter)";
        case DownlinkFormat::DF20: return "DF20 (Comm-B Altitude Reply)";
        case DownlinkFormat::DF21: return "DF21 (Comm-B Identity Reply)";
        case DownlinkFormat::DF24: return "DF24 (Comm-D / ELM)";
        default: return "Unknown";
    }
}

const char* tc_to_string(TypeCode tc) {
    switch (tc) {
        case TypeCode::AIRCRAFT_ID_CAT_D: return "Aircraft Identification (Category D)";
        case TypeCode::AIRCRAFT_ID_CAT_C: return "Aircraft Identification (Category C)";
        case TypeCode::AIRCRAFT_ID_CAT_B: return "Aircraft Identification (Category B)";
        case TypeCode::AIRCRAFT_ID_CAT_A: return "Aircraft Identification (Category A)";
        case TypeCode::AIRBORNE_VELOCITY:  return "Airborne Velocity";
        case TypeCode::AIRCRAFT_STATUS:    return "Aircraft Status";
        case TypeCode::TARGET_STATE:       return "Target State";
        case TypeCode::AIRCRAFT_OP_STATUS: return "Aircraft Operational Status";
        default:
            if (static_cast<uint8_t>(tc) >= 5 && static_cast<uint8_t>(tc) <= 8)
                return "Surface Position";
            if (static_cast<uint8_t>(tc) >= 9 && static_cast<uint8_t>(tc) <= 18)
                return "Airborne Position (Baro Alt)";
            if (static_cast<uint8_t>(tc) >= 20 && static_cast<uint8_t>(tc) <= 22)
                return "Airborne Position (GNSS Alt)";
            return "Unknown";
    }
}

} // namespace modes
