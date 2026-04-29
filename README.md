# udi-Kidde
PG3x node server for Kidde HomeSafe alarms, using udi_interface and kidde-homesafe.  kidde-homesafe is an open source lib maintained at https://github.com/865charlesw/kidde-homesafe

## Features
- Controller node with online status, last update time, and alarm count
- Heartbeat (DON/DOF) toggle on shortPoll
- Alarms du not push data, so longPoll is used to update the data.  Note, updating data just fetches last report - not a refresh. so there is really no benefit polling very often
- There is a Send Command function that can send Identify, Identify Cancel, Test and Hush

## Setup
- Configure EMAIL, PASSWORD, and optional TEMP_UNIT in PG3 custom parameters
- TEMP_UNIT accepted values: F or C (default: C)
- The node creates a kidde node with all registered alarms as subnodes (I have only tested 1 alarm (DETECT (EssWFAC))
- Each alarm shows status data and alarm status - need to poll the data (long Poll) - there is no trigger mechanism to trigger alarms when they happen 
- There is a Send Command function with selector values (UOM 25): 1=Identify, 2=Identify Cancel, 3=Test, 4=Hush
