# udi-Kidde
PG3x node server for Kidde HomeSafe alarms, using udi_interface and kidde-homesafe.  kidde-homesafe is an open source lib maintained at https://github.com/865charlesw/kidde-homesafe

## Features
- Controller node with online status, last update time, and alarm count
- Heartbeat (DON/DOF) toggle on shortPoll
- Capability-based alarm nodes (Smoke/CO/Air Quality combinations)
- Dynamic PG3 profile generated at runtime from `nodes.py` (single source of truth)

## Setup
- Configure EMAIL, PASSWORD, and optional TEMP_UNIT in PG3 custom parameters
- TEMP_UNIT accepted values: F or C (default: C)

- The node creates a kidde node with all registered alarms as subnodes (I have only tested 1 alarm)
- Each alarm shows status data and alarm status - need to poll the data (long Poll) - there is no trigger mechanism to trigger alarms when they happen 
- There is a Send Command function with selector values (UOM 25): 1=Identify, 2=Identify Cancel, 3=Test, 4=Hush
