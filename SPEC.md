# Anypath — v1 Spec

## One-line goal
A normal user enters up to 15 points (start, stops, optional end) anywhere in the world, taps **Optimize**, and within 3 seconds gets the fastest visiting order with time, distance, fuel cost and toll cost — then taps **Navigate** to drive it in Google Maps.

## Users
Everyday drivers (errands, tourists, salespeople). Global. Public launch on iOS, Android and web. No accounts in v1.

## In scope (v1)
1. **Stop entry** — Google Places Autocomplete search box, "use my location" as start, tap-on-map pin. **Max 15 points total, including the start and a fixed end** (a round trip's return to start is not counted twice); minimum is start + 1 stop. UI soft-warns above 10.
   - The same place ID cannot be added twice.
   - Two points < 50 m apart show a "looks like a duplicate" warning but are allowed.
2. **Constraints** — Start point (default: current location). Then either an optional fixed end ("finish at home") **or** "round trip". The two can't both be on; the UI makes them mutually exclusive. Optional lock "visit this stop first" (one stop only), which works with either end option.
   - If the fixed end is the same place as the start, the client silently switches to "round trip" and drops the fixed end.
3. **Departure time** — "Now" (default) or a picked time from now up to **+7 days**. Past times are rejected (client and server). The time is passed to the traffic model and the weather lookup.
4. **Vehicle** — Car (default) or Motorcycle (`TWO_WHEELER` where Google supports it). User sets fuel price (with an ISO currency) and consumption (L/100km or MPG) once; stored on device.
   - Fuel settings are optional. If unset, Optimize still runs; fuel cost shows "—" with a "Set fuel price" link (fuel never affects the order).
   - Display units (km/mi) default from the device region (e.g. miles in US/UK), overridable in settings. Independent of the consumption unit.
5. **Optimize** — returns the order that minimizes total time (default objective).
   - Times are **driving time only**; dwell time at stops is not modeled in v1 (UI labels it "driving time").
   - Ties: Fastest breaks ties by distance, Shortest by time; remaining ties go to the lexicographically smallest index order (deterministic).
6. **Alternatives (2 tabs, always shown)**
   - Fastest — minimize traffic-aware duration (default, selected)
   - Shortest — minimize distance
   Identical results are merged ("Fastest is also shortest"). Fuel and toll cost are **reported** for each alternative but are never an optimization objective.
7. **Result screen** — map with numbered pins and route polyline; ordered list 1 → 2 → 3; totals: time, distance, fuel cost, toll cost; "saves X min vs. your entered order".
   - Savings baseline = the entered order with constraints applied (locked stop moved first, fixed end / return-to-start appended). Hide the line if savings < 1 min.
   - Currencies are never converted. Fuel is shown in the user's fuel currency; tolls are shown per currency as Google returns them (e.g. "€4.20 + CHF 40").
   - Toll states are distinct: "No tolls" (route has no toll roads); "Tolls on route, price unavailable" (Google flags tolls without a price; the total excludes them and says so); a price.
8. **Drag to reorder** — user can drag stops; time, distance and fuel recompute from the cached matrix (no API call). The map switches to straight dashed segments between pins, and toll shows "—" with a **Refresh route** button. Refresh makes one `computeRoutes` call for the custom order (polyline + toll). The matrix is never re-requested.
   - Constraints stay pinned: start, the locked first stop and the fixed end / return-to-start can't be dragged; only middle stops move.
   - Refresh has its own daily cap of **20 refreshes per install ID**, separate from the Optimize limit. Refreshing an order already fetched reuses the cached result (no call).
   - Recompute uses the weather-adjusted durations (see Data flow, step 8).
9. **Weather warning** — fetch the forecast at each stop for its estimated arrival hour (two-pass, see Data flow). Show a banner if rain/snow/fog/extreme temperature. Leg A→B gets the **worst (max) multiplier of A and B**; multipliers never compound. Configurable, documented, estimate only.
10. **Navigate** — hand off to the Google Maps app via a Maps URL (`dir_action=navigate`). Maps URLs allow max 9 waypoints in the app and only 3 in mobile browsers, so routes are split into legs; app shows "Navigate leg 1 of 2" and a "Next leg" button.
11. **Re-optimize from here** — the result list has a "done" checkbox per stop; "Next leg" auto-ticks the stops of the leg just handed off. Re-optimize uses current location as start plus the unticked stops (keeping the end / round-trip setting). This is a new Optimize: one new matrix call, counts toward the daily limit. Hidden when location is unavailable.
   - If the locked first stop is ticked done, the lock is dropped. An unticked locked stop stays first.
   - If no unticked stops remain, the button is hidden (a round trip / fixed end can still be navigated directly).
12. **Dark mode**, and last result cached on device so it opens offline. Offline, only display and **Navigate** (Maps URL generation) work; drag-reorder and "done" checkboxes are disabled.

## Out of scope (v1)
Accounts, saved trips, EV charging, trucks, scenic/least-stressful modes, **cheapest (fuel + toll) objective**, currency conversion, arrival time windows per stop, multiple locked stops, automatic background re-optimization, automatic "visited" detection, in-app turn-by-turn (v2: Google Navigation SDK).

## Architecture
- **Frontend:** Expo (React Native + Expo Router), TypeScript. Maps: `react-native-maps` with Google provider on iOS/Android; `@vis.gl/react-google-maps` on web (platform-specific component behind one interface).
- **Backend:** Python 3.12, FastAPI, Pydantic. Holds all API keys (never shipped to the client except a restricted Maps SDK/Places key).
- **Solver:** exact brute force / DP (Held-Karp) for ≤ 10 nodes; Google OR-Tools routing with guided local search, 1 s time limit, for 11–15 nodes. Same interface, chosen automatically.
- **Hosting:** Google Cloud Run (scale to zero; fits free tier).

## Data flow for one Optimize
1. Client sends points (place IDs + lat/lng), constraints, departure time, vehicle, fuel settings, plus the Firebase App Check token and install ID.
2. Backend validates: point count 2–15, no duplicate place IDs, departure within now…+7 days, not both round trip and fixed end, at most one lock.
3. Backend calls **Routes API `computeRouteMatrix`** once (N×N, `TRAFFIC_AWARE`, departure time) → duration + distance per pair. If Motorcycle is unsupported for the region, retry once as `DRIVE` and flag the result.
4. Reachability check: if any point has no route to/from the rest, return an error naming those points (no solve).
5. Weather pass 1: solve the time objective on the raw matrix to get estimated arrival hours per stop.
6. Fetch the forecast per stop at that arrival hour; apply leg multipliers to the durations.
7. Solve twice (time / distance objectives) on the weather-adjusted matrix — no extra matrix calls.
8. For each distinct winning order (≤ 2), call **Routes API `computeRoutes`** once with toll info requested → polyline + exact toll price.
9. Return result + the weather-adjusted matrix (so drag-to-reorder recomputes locally, consistent with displayed totals) + any warnings.

## Edge cases & failure handling
| Case | Behavior |
|---|---|
| Location permission denied / no GPS | Start field becomes required; Optimize disabled until set; "Re-optimize from here" hidden. |
| Point unreachable (island, ferry-only, other continent) | Hard error naming the point(s); user removes them and retries. |
| Matrix call fails / times out | Hard error with retry. Only hard-failing upstream. |
| Weather fails (Google and Open-Meteo) | No multipliers; banner "Weather unavailable — times exclude weather". |
| `computeRoutes` fails for an order | Straight dashed segments, toll "—", Refresh route button. |
| Motorcycle unsupported in region | Car times used; notice "Motorcycle routing not available here; using car times". Fuel still uses motorcycle consumption. |
| Round trip and fixed end both set | Not possible in UI; server rejects with 422. |
| Departure in the past or > 7 days | Not possible in UI; server rejects with 422. |
| Duplicate place ID | Rejected at entry. |
| Points < 50 m apart | Warning, allowed. |
| Tolls in several currencies | Shown as separate amounts, no conversion. |
| Tolls on route but no price from Google | "Tolls on route, price unavailable"; total excludes it and says so. |
| Fuel settings not set | Optimize runs; fuel cost "—" with "Set fuel price" link. |
| Fixed end == start | Client converts to round trip. |
| Locked stop ticked done, then Re-optimize | Lock dropped. |
| All stops done | "Re-optimize from here" hidden. |
| Offline with cached result | Display + Navigate only; drag and checkboxes disabled. |
| Rate limit hit | "Daily limit reached, try again tomorrow." |
| Refresh route cap hit | Toll stays "—", dashed segments; "Refresh limit reached for today." |
| App Check token missing/invalid | Request rejected (401). |

## Cost budget (Google Maps Platform, per-SKU monthly free caps since March 2025)
Matrix is billed **per element** (N×N). Traffic-aware matrix is the more expensive tier with a smaller free cap. Approximate free trips/month:
- 6 points (start + 5 stops) = 36 elements → many hundreds of trips free
- 15 points (max) = 225 elements → only tens of trips free

Each Optimize also makes ≤ 2 `computeRoutes` calls; each Refresh route makes 1 (separately capped at 20 per install ID per day; repeat refreshes of the same order are cached). The two-pass weather lookup adds weather calls only, never a second matrix call.

**Rules:**
- Set a hard daily quota on every Maps API in Google Cloud Console + a billing alert at $10.
- Abuse protection: Firebase App Check on iOS, Android and web; unattested calls are rejected.
- Backend rate limit: **20 optimizations per device (install ID) per day**, plus a cap of **100 optimizations per IP per day**. Re-optimize counts as an optimization.
- Cache geocoding/place lookups for the session; never re-request the matrix for drag-to-reorder.
- Verify exact SKU tiers (traffic-aware matrix, toll fields) on Google's pricing page before launch.

## Weather
Google Maps Platform **Weather API** (same billing account), fallback Open-Meteo (free, no key). Forecast per stop at its estimated arrival hour, taken from a first weather-free solve of the Fastest order (two-pass; departure ≤ 7 days keeps this inside the forecast horizon). Arrival estimates ignore dwell time. Leg multiplier = max of its two endpoints. Slowdown multipliers live in one config file, e.g. heavy rain 1.15, snow 1.35, fog 1.20.

## Gemini / Claude keys
Not required for v1. Optional v1.1 feature: paste free text ("pharmacy, bank near work, then home") → LLM extracts place queries → Places search. Gemini Flash is the cheaper choice for this.

## Performance & quality targets
- p95 Optimize ≤ 3 s for 15 points (excluding user network).
- Solver: for every random instance with ≤ 9 stops, OR-Tools result == brute-force optimum (test).
- Solver: 15 points solves in < 1.5 s on Cloud Run (three solves per Optimize with two-pass weather; budget accordingly).
- Solver: deterministic — same matrix in → same order out (tie-break test).

## Verification (end-to-end acceptance test)
Using recorded API fixtures (no live calls in CI): 8 Chicago addresses with start = current location and end = home (10 points) →
1. order returned in < 3 s,
2. total time ≤ the user's original order (with constraints applied),
3. both alternatives rendered (or merged into one with the "also shortest" label),
4. generated Maps URL(s) contain ≤ 9 waypoints each and open correctly,
5. drag-reorder updates time/distance/fuel without a network call, and toll shows "—" until Refresh route.

Plus fixture-based edge-case tests: unreachable point error, weather-provider failure degrades with banner, motorcycle fallback notice, 422 on round trip + fixed end and on past departure, toll "price unavailable" state, drag cannot move pinned constraints.

One manual live smoke test per release on a real phone.
