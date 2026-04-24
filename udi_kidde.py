# Entry point for Kidde PG3x node server

if __name__ == "__main__":
    import udi_interface
    #from kidde_homesafe import KiddeClient, KiddeCommand
    import asyncio
    import json
    from nodes import KiddeController
    import sys

    LOGGER = udi_interface.LOGGER
    try:
        polyglot = udi_interface.Interface([])
        polyglot.start({"version": "0.1.0", "requestId": True})
        polyglot.setCustomParamsDoc()
        KiddeController(polyglot, "setup", "setup", "Kidde Monitors")
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
