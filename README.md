# udi-Kidde

PG3x node server for Kidde HomeSafe alarms, using `udi_interface` and `kidde-homesafe`.  
`kidde-homesafe` is an open source library maintained at [https://github.com/865charlesw/kidde-homesafe](https://github.com/865charlesw/kidde-homesafe).

## Features
- **Controller Node (`SETUP`)**:
  - Node server status (`ST`), online status (`GV1`), number of alarms (`GV0`), and last update time (`TIME`).
  - Heartbeat (`DON`/`DOF`) toggle on `shortPoll`.
  - Accurate `TIME` reporting: only updates when data is successfully received from the Kidde cloud (never on error, startup, or heartbeat).
- **Capability-Based Alarm Subnodes (`KIDDEALARM0` – `KIDDEALARM7`)**:
  - Automatically created and dynamically typed based on device capabilities (Smoke, CO, Air Quality).
  - Telemetry: smoke alarm, CO alarm, smoke hush, smoke level, CO level (PPM), battery state, low battery alarm, IAQ status, chirps schedule (minutes after midnight), model, life remaining, and last seen.
  - Event notifications: sends `DON` on alarm onset and `DOF` on alarm clearance.
  - All status/boolean drivers use the discrete `BOOLEAN` editor (`No` / `Yes`).
- **Device Commands**:
  - `Send Command` (`SENDCMD`) function: Identify, Identify Cancel, Test, Hush.
  - Dedicated `Hush Alarm` (`HUSH`) command.

## Setup
1. Configure custom parameters in PG3x:
   - `EMAIL`: Kidde account email address (required).
   - `PASSWORD`: Kidde account password (required).
   - `TEMP_UNIT`: Optional temperature unit, `F` or `C` (default: `F`).
2. Configure polling intervals in PG3x:
   - `shortPoll` (default: 30s): sends heartbeat toggling `DON`/`DOF`.
   - `longPoll` (default: 180s): polls latest telemetry data from the Kidde cloud.
     > **Note:** Kidde alarms do not push real-time events to the cloud; `longPoll` polls the latest reported state. Updating data fetches the last reported cloud status, so polling excessively fast provides no benefit.
