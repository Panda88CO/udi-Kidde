# udi-Kidde

PG3x node server for Kidde HomeSafe alarms, using `udi_interface` and `kidde-homesafe`.  
`kidde-homesafe` library: [https://github.com/865charlesw/kidde-homesafe](https://github.com/865charlesw/kidde-homesafe).

## Features
- Controller node (`SETUP`) with Node Server Status, Online Status, Alarm Count, and Last Update Time
- Heartbeat (`DON`/`DOF`) toggle on `shortPoll`
- Dynamic JSON profile loaded after node initialization with named drivers
- Capability-based alarm nodes (`KIDDEALARM0` – `KIDDEALARM7` for Smoke / CO / Air Quality combinations)
- Remote device commands: Identify, Identify Cancel, Test, and Hush

## Setup
- Configure `EMAIL` and `PASSWORD` (from the Kidde app) in PG3 custom parameters
- `TEMP_UNIT` accepted values: `F` or `C` (default: `F`)
- Set `shortPoll` and `longPoll`:
  - `shortPoll` sends heartbeat toggling `DON`/`DOF` (default: 30s)
  - `longPoll` polls data from Kidde cloud (default: 180s)
    - *Note:* LongPoll fetches the latest data reported to the Kidde cloud; alarms do not push real-time events to the cloud, so polling too frequently is not beneficial.
- Alarm nodes support `Send Command`: Identify, Identify Cancel, Test, and Hush
