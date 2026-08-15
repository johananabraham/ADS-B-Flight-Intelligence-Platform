# Feeder pilot interview guide

Use the same questions for every participant. Ask for examples without requesting
aircraft identities, coordinates, receiver locations, screenshots, or raw data.

## Before the run

1. How do you currently notice that your feeder, decoder, clock, or network is
   behaving incorrectly?
2. What information do you wish dump1090/readsb exposed more clearly?
3. What would make you unwilling to install a local monitoring sidecar?

## After installation

4. Where did you hesitate or need outside help?
5. In your own words, what do `NOMINAL`, `QUESTIONABLE`, and
   `INSUFFICIENT_DATA` mean?
6. Which health or evidence explanation was hardest to understand?

## After the field run

7. Did the sidecar cause you to inspect or change anything in your receiver,
   decoder, clock, network, or configuration? What category of issue was it?
8. Were any warnings obviously unhelpful or repetitive?
9. Did the application ever stop, lose its feed, consume unexpected resources, or
   report drops? Use only the aggregate pilot summary when answering.
10. Would you keep it installed? Why or why not?
11. What single change would create the most value for you?

## Researcher coding

Code responses into `INSTALLABILITY`, `RELIABILITY`, `COMPREHENSION`,
`OPERATIONAL_FINDING`, `NO_OBSERVED_VALUE`, `PRIVACY_CONCERN`, and
`FEATURE_REQUEST`. Preserve negative results and withdrawals. Do not convert
qualitative feedback into percentages when the sample is too small.
