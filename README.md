# udi-Kidde

PG3x node server for Kidde HomeSafe alarms, using `udi_interface` and `kidde-homesafe`.  
`kidde-homesafe` is an open source library maintained at [https://github.com/865charlesw/kidde-homesafe](https://github.com/865charlesw/kidde-homesafe).

## Features
- **Controller Node (`SETUP`)**:
  - Human-readable driver names: Node Server Status (`ST`), Online Status (`GV1`), Number of Alarms (`GV0`), and Last Update Time (`TIME`).
  - Heartbeat (`DON`/`DOF`) toggle on `shortPoll`.
  - Accurate `TIME` reporting: only updates when telemetry is successfully received from the Kidde cloud (never on error, startup, or poll).
  - Dynamic JSON profile: generated in code and loaded once node initialization completes.
- **Capability-Based Alarm Subnodes (`KIDDEALARM0` – `KIDDEALARM7`)**:
  - Automatically discovered and dynamically typed based on device capabilities (Smoke, CO, Air Quality).
  - Human-readable driver names defined directly on node drivers and synchronized with dynamic profiles.
  - Telemetry: Smoke Alarm, CO Alarm, Smoke Hushed, Smoke Level, CO Level (PPM), Battery State, Low Battery Alarm, IAQ Status, Chirps Schedule (minutes after midnight), Model, Life Remaining, and Last Seen.
  - Event notifications: sends `DON` on alarm onset and `DOF` on alarm clearance.
  - Discrete `BOOLEAN` editor displaying `No` / `Yes` for all boolean states.
- **Device Commands**:
  - `Send Command` (`SENDCMD`): Identify, Identify Cancel, Test, Hush.
  - Dedicated `Hush Alarm` (`HUSH`) command.

## System Requirements
- IoX 6.0.6+
- PG3x 3.4.5+
- `udi_interface` 3.4.5+

## Configuration
1. Configure custom parameters in PG3x:
   - `EMAIL`: Kidde account email address (required).
   - `PASSWORD`: Kidde account password (required).
   - `TEMP_UNIT`: Optional temperature unit, `F` or `C` (default: `F`).
2. Configure polling intervals in PG3x:
   - `shortPoll` (default: 30s): sends heartbeat toggling `DON`/`DOF`.
   - `longPoll` (default: 180s): polls latest telemetry data from the Kidde cloud.
     > **Note:** Kidde alarms do not push real-time events to the cloud; `longPoll` polls the latest reported state. Updating data fetches the last reported cloud status, so polling excessively fast provides no benefit.
