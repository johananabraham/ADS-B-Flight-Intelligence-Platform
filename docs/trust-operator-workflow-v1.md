# Trust operator workflow v1

## Purpose

The trust workflow turns a current, explainable trust calculation into durable
evidence that an operator can inspect and annotate. It preserves each component's
state, policy version, age, reasons, and evidence identifiers. It does not turn those
components into an uncalibrated numeric score.

## Data and API contract

- `POST /api/v1/trust/{icao_hex}/assessments` calculates evidence on the server and
  persists one immutable assessment for that exact evidence state.
- `GET /api/v1/trust-events/` lists assessments and supports ICAO, state, and time
  filters.
- `GET /api/v1/trust-events/{assessment_id}` returns the assessment and its actions.
- `POST /api/v1/trust-events/{assessment_id}/actions` appends `ACKNOWLEDGE` or
  `ANNOTATE`. Annotation requires a non-blank note.
- `GET /api/v1/trust-events/{assessment_id}/export` downloads a JSON evidence bundle.

Assessment IDs are derived from the stable evidence content, excluding request-time
age and evaluation timestamps. Action IDs are supplied by the client. Repeating the
same request therefore returns the existing row; reusing an action ID with different
content is rejected with HTTP 409.

## Reproducible verification

After migrations and the deterministic kinematic attack fixture are running:

```bash
python3 scripts/verify_trust_workflow.py
```

The verifier proves that:

1. the deterministic flagged track produces `QUESTIONABLE`;
2. recalculating identical evidence returns the same assessment ID and one row;
3. retrying the same annotation returns one action row;
4. filtered history, detail, and export contain the assessment;
5. the export discloses that operator identity is `AUTHENTICATED`.

The full application route contract is covered by
`backend/tests/test_route_registration.py`; it checks every product router on the
actual FastAPI application rather than testing isolated routers only.

## Small usability review

Give another developer the running website without showing backend logs. Ask them to:

1. select the deterministic attack aircraft and expand **EXPLAINABLE TRUST STATE**;
2. state the overall trust state and identify the component that caused it;
3. find the supporting evidence identifiers and policy version;
4. annotate the event, filter the history to `QUESTIONABLE`, and export it;
5. explain whether the actor name represents an authenticated user.

Record the reviewer, date, completion result, confusing labels, and any corrective
changes. This checkpoint has not yet completed that human review.

## Security and evidence boundaries

- Actor labels are derived from the authenticated session and marked `AUTHENTICATED`.
- Authentication, authorization, rate limiting, and retention policy are required
  before public deployment.
- The event means the stored evidence matched a deterministic policy. It does not
  prove spoofing, malicious intent, or the aircraft's true location.
- A field-calibrated numeric trust score remains intentionally absent.
