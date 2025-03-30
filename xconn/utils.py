import asyncio
from typing import Coroutine
import signal


def run(main: Coroutine):
    async def _run():
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def handle_signal(sig):
            print(f"\nReceived signal {sig.name}, stopping...")
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_signal, sig)

        await main
        await stop_event.wait()

    asyncio.run(_run())
