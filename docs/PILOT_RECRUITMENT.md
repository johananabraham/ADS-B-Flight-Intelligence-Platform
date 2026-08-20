# Independent feeder pilot recruitment

Use this page to recruit three to five independent dump1090/readsb operators for
the protocol in [PILOT_PROGRAM.md](PILOT_PROGRAM.md). Recruitment is for
deployability, reliability, comprehension, and operational-usefulness evidence.
It is not a test of whether the software proves spoofing or authenticates an
aircraft.

## Who is eligible

A participant must:

- operate an authorized ADS-B receiver that already exposes SBS/BaseStation TCP
  output, normally on port 30003;
- be able to run Docker Compose beside the existing feeder for seven days;
- not be a contributor to this repository; and
- agree to inspect and share only the allow-listed aggregate pilot summaries.

Do not recruit anyone who would need to expose a receiver to the public internet,
share credentials, grant remote shell access, or provide raw traffic, aircraft
identifiers, callsigns, coordinates, screenshots, or receiver-location details.

## Short outreach post

> I am recruiting 3–5 independent ADS-B feeder operators to evaluate an
> open-source, read-only integrity sidecar for dump1090/readsb. It connects to an
> existing local SBS port, runs with Docker Compose, and keeps aircraft traffic
> local. The study takes about 15 minutes to install and one reviewed aggregate
> summary per day for seven days. It measures installation, reliability,
> understandable evidence, and whether the tool prompts a useful receiver or
> pipeline check—not whether it proves spoofing. Participation is voluntary and
> you can stop at any time. Please read the pilot protocol before volunteering:
> https://github.com/johananabraham/ADS-B-Flight-Intelligence-Platform/blob/main/docs/PILOT_PROGRAM.md

## Forum outreach post

> **Seeking dump1090/readsb operators for a privacy-safe seven-day pilot**
>
> I built an open-source local sidecar that consumes an existing
> SBS/BaseStation stream and reports receiver health, data limitations, and
> explainable telemetry-integrity evidence. I am looking for 3–5 operators who
> are not project contributors to test whether the installation and evidence are
> understandable and operationally useful.
>
> Requirements: an authorized dump1090/readsb-compatible feeder with local TCP
> port 30003, Docker Compose, and permission to run a read-only monitor beside
> the feeder. The target is an unaided installation in 15 minutes or less,
> followed by seven days of local operation.
>
> The sidecar does not upload live traffic. Participants inspect one
> allow-listed aggregate summary per day before sharing it. Please do not send
> receiver locations, aircraft identifiers, callsigns, coordinates, raw SBS
> messages, screenshots, credentials, or remote access. `QUESTIONABLE` means
> inconsistent telemetry, not proof of spoofing; this is research software, not
> a safety-of-life system.
>
> Protocol and success criteria:
> https://github.com/johananabraham/ADS-B-Flight-Intelligence-Platform/blob/main/docs/PILOT_PROGRAM.md
>
> If interested, reply without location details or use the sanitized feedback
> form:
> https://github.com/johananabraham/ADS-B-Flight-Intelligence-Platform/issues/new?template=pilot-feedback.yml

## Suggested outreach order

1. Post the short version to [r/ADSB](https://www.reddit.com/r/ADSB/), where
   dump1090/readsb and multi-feeder operators actively discuss local setups.
2. Post the forum version in the appropriate receiver or technical section of
   the [Flightradar24 forum](https://forum.flightradar24.com/).
3. Ask a moderator before posting recruitment in an ADS-B Discord or project
   support channel; follow its self-promotion and research rules.
4. Invite maintainers or users through an appropriate public discussion in the
   [readsb project](https://github.com/wiedehopf/readsb) only if that project's
   contribution guidelines permit it. Do not open unsolicited recruitment bug
   reports.

Record only channel, posting date, aggregate response count, and random pilot
labels in private notes. Do not commit community usernames or private messages.

## First response

Send this checklist to a volunteer before assigning a random pilot label:

> Thank you. Before we begin, please confirm only the following—do not send your
> location or feeder identity:
>
> - You operate or are authorized to test this receiver.
> - dump1090/readsb exposes a local SBS TCP stream.
> - Docker Compose is available.
> - You can keep the sidecar running for up to seven days.
> - You will inspect every aggregate artifact before sharing it.
> - You understand this tool does not prove spoofing or support flight-safety
>   decisions.

After confirmation, assign a private random label (`pilot-01`, `pilot-02`, and so
on) and follow [PILOT_PROGRAM.md](PILOT_PROGRAM.md) without collecting additional
identity or location information.
