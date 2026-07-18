# Validation Results

Recorded July 18, 2026 on Apple Silicon.

## Live instance failure

`decoder2` was stopped three seconds into a 20-second, 300-request/second load
test through nginx. Health checks returned HTTP 200 immediately after the stop
and after load completed. The run completed 3,783 of 3,788 requests successfully
(99.87%) at 160.6 requests/second with 10.34 ms p99 latency; five requests failed
during the transition.

This demonstrates continued service under one instance failure. It does not
demonstrate zero-request loss.

## dump1090-fa 11.0 comparison

The same published ADS-B frames were fed to this decoder and dump1090-fa in
network-only mode. Matching fields were:

| Field | This decoder | dump1090-fa |
|---|---:|---:|
| Callsign | KLM1023 | KLM1023 |
| Barometric altitude | 38,000 ft | 38,000 ft |
| Ground speed | 159.201 kt | 159.2 kt |
| Track/heading | 182.88° | 182.9° |
| Vertical rate | -832 ft/min | -832 ft/min |

dump1090-fa also decoded the even/odd CPR pair to 52.265780° N, 3.938913° E,
which falls within the bounds asserted by `validation_test.cpp`.

Run `tests/dump1090_validation.sh` to repeat the field comparison.
