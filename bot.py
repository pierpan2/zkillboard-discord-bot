import discord
from discord.ext import commands, tasks
import websocket
import json
import threading
import requests
import asyncio
from collections import deque
import time
from config import *
import logging
import coloredlogs

LAST_MESSAGE_TIME = None

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
processed_hashes = deque(maxlen=hash_limit)

info_logger = logging.getLogger("Discord")
coloredlogs.install(level="INFO", logger=info_logger)
debug_logger = logging.getLogger("WebSocket")
coloredlogs.install(level="DEBUG", logger=debug_logger)
error_logger = logging.getLogger("Discord")
coloredlogs.install(level="ERROR", logger=error_logger)


def start_websocket():
    global LAST_MESSAGE_TIME

    def on_ws_message(ws, message):
        global LAST_MESSAGE_TIME
        data = json.loads(message)
        info_logger.info("Received killmail")
        kill_hash = data.get("hash")
        url = data.get("url")

        if kill_hash and kill_hash not in processed_hashes:
            processed_hashes.append(
                kill_hash
            )  # Adds new hash and may remove the oldest if limit is reached
            # Process the message, e.g., send to Discord channel
            channel = bot.get_channel(channel_id)
            if channel:
                info_logger.info(f"Sending message to channel {channel.name}")
                asyncio.run_coroutine_threadsafe(channel.send(url), bot.loop)
            else:
                error_logger.error("Channel not found")

        else:
            info_logger.info("Duplicate message received, ignoring.")
        LAST_MESSAGE_TIME = time.time()

    def on_ws_open(ws):
        def run(*args):
            with open("subscriptions.json", "r") as file:
                subscriptions = json.load(file)
            for subscription in subscriptions:
                ws.send(json.dumps(subscription))
                debug_logger.debug(f"Subscribed to {subscription}")
            debug_logger.debug("Subscribed to all kills")

        debug_logger.debug("Opened WebSocket")
        threading.Thread(target=run).start()

    ws = websocket.WebSocketApp(
        "wss://zkillboard.com/websocket/", on_open=on_ws_open, on_message=on_ws_message
    )
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.start()
    return ws, ws_thread


async def manage_websocket():
    global LAST_MESSAGE_TIME
    LAST_MESSAGE_TIME = time.time()

    ws, ws_thread = start_websocket()

    while True:
        await asyncio.sleep(10)  # Check every 10 seconds
        if (time.time() - LAST_MESSAGE_TIME) > inactivity_threshold:
            debug_logger.debug("WebSocket inactive, attempting to reconnect...")

            # Close the WebSocket
            ws.close()

            # Check if the thread is still alive and join it if it is
            if ws_thread.is_alive():
                ws_thread.join(
                    timeout=10
                )  # Wait for the thread to finish with a timeout

            # Reinitialize the WebSocket and thread
            ws, ws_thread = start_websocket()
            LAST_MESSAGE_TIME = time.time()


async def tq_status():
    server_status = requests.get(
        "https://esi.evetech.net/latest/status/?datasource=tranquility"
    )
    # fethch player count
    player_count = server_status.json()["players"]
    info_logger.info(f"Currently {player_count} players online")

    # set bot status as player count

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"Tq, {player_count} players online",
        )
    )
    info_logger.info("Updated bot status")


@tasks.loop(seconds=600)
async def status_update_loop():
    await tq_status()


@bot.event
async def on_ready():
    info_logger.info(f"Logged in as {bot.user}")

    bot.loop.create_task(manage_websocket())
    info_logger.info("Started WebSocket")

    status_update_loop.start()
    info_logger.info("Started status update loop")


bot.run(token)
