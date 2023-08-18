"""Main library functions for py-omnistream."""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any, Callable

from .exceptions import (
    AlreadyListening,
)

from .websocket import (
    SIGNAL_CONNECTION_STATE,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_STOPPED,
    OmniStreamWebsocket,
)

_LOGGER = logging.getLogger(__name__)

ERROR_TIMEOUT = "Timeout while updating"
INFO_LOOP_RUNNING = "Event loop already running, not creating new one."
USERNAME = "username"
PASSWORD = "password"
CONF_GET = "config_get"
CONF_SET = "config_set"

class omnistream:
    """Represent an omnistream device."""

    def __init__(self, host: str, user: str = "", pwd: str = "") -> None:
        """Connect to omnistream device."""
        self._user = user
        self._pwd = pwd
        self.url = f"ws://{host}/wsapp/"
        self.data = dict = {}
        self.websocket: OmniStreamWebsocket | None = None
        self.callback: Callable | None = None
        self._ws_listening = False
        self._loop = None

    def ws_start(self) -> None:
        """Start the websocket listener."""
        if self._ws_listening:
            raise AlreadyListening
        self._start_listening()

    def _start_listening(self):
        """Start the websocket listener."""
        try:
            _LOGGER.debug("Attempting to find running loop...")
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.get_event_loop()
            _LOGGER.debug("Using new event loop...")

        if not self._ws_listening:
            self._loop.create_task(self.websocket.listen())
            pending = asyncio.all_tasks()
            self._ws_listening = True
            try:
                self._loop.run_until_complete(asyncio.gather(*pending))
            except RuntimeError:
                _LOGGER.info(INFO_LOOP_RUNNING)

    async def _update_status(self, msgtype, data, error):
        """Update data from websocket listener."""
        if msgtype == SIGNAL_CONNECTION_STATE:
            if data == STATE_CONNECTED:
                _LOGGER.debug("Websocket to %s successful", self.websocket.uri)
                self._ws_listening = True
            elif data == STATE_DISCONNECTED:
                _LOGGER.debug(
                    "Websocket to %s disconnected, retrying",
                    self.websocket.uri,
                )
                self._ws_listening = False
            # Stopped websockets without errors are expected during shutdown
            # and ignored
            elif data == STATE_STOPPED and error:
                _LOGGER.error(
                    "Websocket to %s failed, aborting [Error: %s]",
                    self.websocket.uri,
                    error,
                )
                self._ws_listening = False

        elif msgtype == "data":
            _LOGGER.debug("Websocket data: %s", data)
            self.data.update(data)

            if self.callback is not None:
                self.callback()  # pylint: disable=not-callable

    async def ws_disconnect(self) -> None:
        """Disconnect the websocket listener."""
        assert self.websocket
        await self.websocket.close()
        self._ws_listening = False

    async def update(self) -> None:
        """Update the values."""
        if not self._ws_listening:
            self.ws_start()

        if not self.websocket:
            # Start Websocket listening
            self.websocket = OmniStreamWebsocket(self.url, self._update_status)        

    async def send_request(self, request) -> None:
        """Send request to device."""
        request = {}
        request[USERNAME] = self._user
        request[PASSWORD] = self._pwd
        request[CONF_GET] = request

        # Send the request
        await self.websocket.ws_msg(request)

    async def send_command(self, request: dict) -> None:
        """Send request to device."""
        request = {}
        request[USERNAME] = self._user
        request[PASSWORD] = self._pwd
        request[CONF_SET] = json.dumps(request)

        # Send the request
        await self.websocket.ws_msg(request)        

    async def device_info(self) -> dict:
        """Request device info."""
        request = {}
        request[USERNAME] = self._user
        request[PASSWORD] = self._pwd
        request[CONF_GET] = "systeminfo"

        await self.websocket.ws_msg(request)

        data = {}
        data["firmware"] = self.data["config"]["detailedfirmwareversion"]
        data["model"] = self.data["config"]["model"]

        return data

    @property
    def ws_state(self) -> Any:
        """Return the status of the websocket listener."""
        assert self.websocket
        return self.websocket.state
