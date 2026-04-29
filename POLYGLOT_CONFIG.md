# udi-Kidde

PG3x node server for Kidde HomeSafe alarms, using udi_interface and kidde-homesafe.  kidde-homesafe is an open source lib maintained at https://github.com/865charlesw/kidde-homesafe

## Features
- Controller node with online status, last update time, and alarm count
- Heartbeat (DON/DOF) toggle on shortPoll
- Capability-based alarm nodes (Smoke/CO/Air Quality combinations)

## Setup
- Configure EMAIL, PASSWORD (from KIdde app), and optional TEMP_UNIT in PG3 custom parameters
- TEMP_UNIT accepted values: F or C (default: C)
- Set LongPoll and ShortPoll 
- ShortPoll sends heartbeat (toggling DON/DOF) (60s default)
- LongPoll polls data from alarms (300s default) - Note, it is not a refresh - it just polls latest data from the clould, so it does not make sense to Poll too often
- Alarm nodes support Send Command  Identify, Identify Cancel, Test, 4=Hush


