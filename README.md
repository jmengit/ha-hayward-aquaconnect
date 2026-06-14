# Hayward AquaConnect for Home Assistant

A Home Assistant custom integration for Hayward AquaConnect AQ-CO-HOMENET adapters using the local web server exposed by the device.

This project is intentionally conservative: it supports read-only status, LCD-derived status sensors, and a small set of direct equipment switches. It does **not** automate deep LCD menu navigation, editing heater setpoints, schedules, timers, settings menus, or starting/stopping superchlorinate.

## Supported hardware

Tested against a Hayward AquaConnect AQ-CO-HOMENET local web UI that exposes:

- `POST /WNewSt.htm` with body `Update Local Server&` for status
- `POST /WNewSt.htm` with body `KeyId=<id>&` for direct button presses

## Installation via HACS

1. In Home Assistant, go to **HACS → Integrations → ⋮ → Custom repositories**.
2. Add this repository URL:

   ```text
   https://github.com/jmengit/ha-hayward-aquaconnect
   ```

3. Category: **Integration**.
4. Install **Hayward AquaConnect**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration**.
7. Search for **Hayward AquaConnect**.
8. Enter your AquaConnect IP/host, for example:

   ```text
   192.168.86.182
   ```

Use a DHCP reservation/static IP for the AquaConnect. Some AquaConnect hostnames contain underscores and may not resolve reliably.

## Branding

The repo includes local brand assets in two places:

- `brand/` at the repository root for HACS repository branding
- `custom_components/hayward_aquaconnect/brand/` for Home Assistant integration branding

Both locations include `icon.png`, `icon@2x.png`, `logo.png`, and `logo@2x.png` assets so refreshes in HACS and Home Assistant can resolve them.

Older Home Assistant/HACS views may render update-card pictures from the public Home Assistant brands CDN instead of local custom integration files. For that path, the same assets also need to be published in `home-assistant/brands` under `custom_integrations/hayward_aquaconnect/`.

## Configuration

Default runtime values are kept conservative so the integration works immediately after install:

- Scan interval: `5` seconds
- Command verification timeout: `10` seconds
- Command retries: `1`
- Button delay: `0.75` seconds

If another AquaConnect installation uses different button IDs or labels, open the integration options and paste a JSON object of slot overrides. Any values you omit keep the defaults.

Example:

```json
{
  "pool_light": {
    "name": "Spa Light",
    "press_key_id": "0E"
  },
  "filter_pump": {
    "press_key_id": "08",
    "enable_switch": true
  }
}
```

## Entities

### Sensors

- Pool Temperature
- Air Temperature
- Salt Level
- Chlorinator Percent
- Super Chlorinate Time Remaining
- Heater Set Point
- Display Line 1
- Display Line 2
- Raw LEDs

The AquaConnect LCD rotates through pages, so temperature/salt/chlorinator sensors retain their last observed values while the display is on another page. Values are also retained while the pump is off and a page is not available; individual measurements are cleared only after they have not been observed for 24 hours. Heater Set Point is captured from heater/pool-heat menu pages and persists indefinitely until the next setpoint page is observed.

Display-related sensors are diagnostic/disabled by default because the LCD rotates frequently.

A diagnostic **Read Health** sensor is also available. It reports:

- `healthy` — fresh read stream
- `degraded` — one recent failure
- `cooldown` — two or three consecutive failures, with backoff between retries
- `stale` — four consecutive failures; core entities become unavailable until a good read returns

Default read-failure behavior:

- success: normal refresh every scan interval
- failure 1: keep last good values
- failure 2: enter cooldown at 2× the scan interval
- failure 3: enter longer cooldown at 4× the scan interval
- failure 4: mark the integration stale and let Home Assistant surface entities as unavailable

This keeps the UI stable during brief hiccups while preventing stale data from looking current.

Read Health is the detailed diagnostic state. For automations and notifications, use the simple **Connection Alert** binary sensor instead.

### Alert binary sensors

Two simple `problem` binary sensors provide at-a-glance alerting:

- **Display Alert** turns on for persistent unexpected LCD text. Non-standard display text is first exposed as a candidate in attributes. It only becomes an active alert after the same candidate text has been observed at least 3 times and has persisted for at least 3 minutes.
- **Connection Alert** turns on when the integration is not successfully getting fresh reads from the AquaConnect device. It is on for `starting`, `degraded`, `cooldown`, or `stale` read-health states, and off only when reads are `healthy`.

This allows brief manual menu use while still surfacing real persistent controller messages such as flow/salt/system warnings.

Super Chlorinate is exposed separately as a non-problem running binary sensor plus a time-remaining sensor when the LCD shows the countdown. It is intentionally not treated as a Display Alert problem.

### Status binary sensors

Used equipment slots are exposed as status entities:

- Heater Manual
- Pool
- Pool Deck Light
- Pool Chiller
- Waterfall Pump
- Filter Pump
- Fire Goblets
- Pool Light

Unused slots are intentionally not exposed by default in this first version.

### Direct switches

The following direct switches are exposed:

- Filter Pump
- Heater Manual
- Pool Chiller
- Pool Light
- Pool Deck Light
- Waterfall Pump
- Fire Goblets

Switches are intentionally limited to direct button slots. The integration does not navigate menus.

## Switch safety and verification

AquaConnect does not provide a modern command API. Switches emulate button presses against the local web UI.

When a Home Assistant switch is toggled, the integration:

1. Polls the current equipment state.
2. If the target is already in the desired state, it does nothing.
3. Sends one direct `KeyId=<id>&` button press.
4. Waits briefly.
5. Polls until the decoded LED state matches the desired state.
6. Retries according to the integration option.
7. Raises a Home Assistant error if the desired state cannot be verified.

Each entity includes command diagnostic attributes such as `last_command_result` or `last_command_error` when applicable.

## Known limitations

- This is local polling over the AquaConnect web UI, not an official Hayward API.
- Deep functions are not implemented:
  - timers
  - settings menu
  - schedule editing
  - changing heater setpoints
  - starting/stopping superchlorinate
  - chlorinator output changes
- Commands are serialized inside the integration so two switch commands do not run at the same time.
- If someone manually uses the AquaConnect panel/app while Home Assistant is sending a command, verification may fail or the command may be rejected.

## Future Phase 3: advanced helper design, not currently implemented

If deeper functions are ever added, the recommended design is **not** to cram LCD menu navigation into Home Assistant entities directly.

A future helper service could run as a local Docker container, for example `aquaconnectd`, and expose a higher-level API:

```http
GET  /api/status
POST /api/equipment/filter_pump/on
POST /api/heater/setpoint
POST /api/chlorinator/superchlorinate
POST /api/menu/navigate
```

Internally, that helper would own the hacky pieces:

- a serialized command queue
- timed button presses
- screen/menu state machine
- retry and rollback logic
- recovery to the home/status screen
- detailed debug logs
- dry-run/read-only mode
- command lockouts when state is uncertain

The HACS integration could then support two modes:

1. **Direct mode** — current behavior: read status and direct simple switches.
2. **Helper mode** — talk to the Docker helper for advanced features.

Advanced HA entities could then be added safely:

- `climate` or `number` for heater setpoint
- `button` for superchlorinate
- `number` for chlorinator percentage
- `select` for heat/cool modes
- schedule/timer entities or services

This project intentionally stops short of that for now.

## Development

Run parser tests:

```bash
python3 -m pytest tests
```

The parser and slot decoder can be tested without a Home Assistant runtime.

## Privacy

Do not commit personal IP addresses, Home Assistant tokens, router details, or local logs. Example IPs in documentation should be generic.
