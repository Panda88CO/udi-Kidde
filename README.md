# udi-Kidde

PG3x node server for Kidde HomeSafe alarms, using udi_interface and kidde-homesafe.  kidde-homesafe is an open source lib maintained at https://github.com/865charlesw/kidde-homesafe

## Features
- Controller node with online status, last update time, and alarm count
- Heartbeat (DON/DOF) toggle on shortPoll
- Asyncio-safe integration with Kidde API
- Dynamic JSON profile update at startup (PG3x dynamic profiles)
- Capability-based alarm nodes (Smoke/CO/Air Quality combinations)
- Device capabilities are queried before node creation so unsupported data is hidden

## Setup
- Configure EMAIL, PASSWORD, and optional TEMP_UNIT in PG3 custom parameters
- TEMP_UNIT accepted values: F or C (default: F)
- Cookie persistence is handled automatically (no user action needed)
- Run install.sh to install dependencies
- Start with udi_kidde.py

## Dynamic Profile Notes
- This project is dynamic-profile only at runtime.
- The static artifacts folder has been retired to profile_static/ so PG3x does not auto-upload static profiles.
- If static artifacts are regenerated for reference, keep them under profile_static/ (not profile/).

