"""Live NASA services: DONKI space weather, Perseverance traverse and raw images.

All three use the same safe HTTP helper (timeouts, status/size checks, JSON-only, API key never logged) and a
local cache. Data fetched from NASA are labelled Real; a file the user loads is User Supplied; the bundled
example files are Synthetic (format examples for offline demos and tests, not NASA measurements)."""
