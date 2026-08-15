# Phase 2 acceptance status

Status: **BLOCKED_CAPTURE_PENDING** as of 2026-08-15.

The capture, checksum, freeze, sanitization, privacy, episode, reviewer, and report tooling is implemented and covered by automated tests. The frozen development policy detected 20/20 abrupt and 20/20 gradual targeted synthetic cases (`1.0` recall for each family); the checked-in result is bound to policy SHA-256 `b1ea0ec365b757e3077d24609835ba98466221b9d55ec38a047d98378f47f52d`.

The following release gates are intentionally not claimed:

- Seven usable physical receiver-days have not been captured.
- Days 1–6 have not been reviewed and used to freeze a field-calibrated policy.
- An untouched day-7 chronological holdout does not exist yet.
- No holdout episodes have been manually reviewed.
- No reviewed routine-traffic integrity-alert rate has been measured.
- No public benign feature artifact has passed the required manual privacy sample inspection.

These require the user’s existing RTL-SDR/dump1090 receiver to operate over real elapsed days. The implementation refuses to turn missing holdout data into a zero rate or a passing report. Follow [the field protocol](../BENIGN_FIELD_EVALUATION.md); replace this status only with generated, reviewed evidence tied to the frozen-policy and capture checksums.
