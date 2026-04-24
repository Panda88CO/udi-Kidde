# udi-Kidde

PG3x node server for Kidde HomeSafe alarms, using udi_interface and kidde-homesafe.

## Features
- Controller node with online status, last update time, and alarm count
- Heartbeat (DON/DOF) toggle on shortPoll
- Asyncio-safe integration with Kidde API
- JSON-driven profile workflow (planned)

## Setup
- Configure EMAIL and PASSWORD in PG3 custom parameters
- Cookie persistence is handled automatically (no user action needed)
- Run install.sh to install dependencies
- Start with udi_kidde.py

## Milestone 1
- Controller node only (no subnodes yet)
- Profile and subnode support coming next
