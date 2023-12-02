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
global ws
ws = None

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
processed_hashes = deque(maxlen=hash_limit)

info_logger = logging.getLogger("Discord")
coloredlogs.install(level="INFO", logger=info_logger)
debug_logger = logging.getLogger("WebSocket")
coloredlogs.install(level="DEBUG", logger=debug_logger)
error_logger = logging.getLogger("Discord")
coloredlogs.install(level="ERROR", logger=error_logger)


def start_websocket_suball():
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
                # make subsricption subscribes suball
                subscriptions = subscriptions["suball"]
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
    global ws
    ws, ws_thread = start_websocket_suball()

    while True:
        await asyncio.sleep(10)  # Check every 10 seconds
        if (time.time() - LAST_MESSAGE_TIME) > inactivity_threshold:
            debug_logger.debug("WebSocket inactive, attempting to reconnect...")

            # Close the WebSocket
            ws.close()
            ws = None
            # Check if the thread is still alive and join it if it is
            if ws_thread.is_alive():
                ws_thread.join(
                    timeout=10
                )  # Wait for the thread to finish with a timeout

            # Reinitialize the WebSocket and thread
            ws, ws_thread = start_websocket_suball()
            LAST_MESSAGE_TIME = time.time()


async def tq_status():
    try:
        server_status = requests.get(
            "https://esi.evetech.net/latest/status/?datasource=tranquility"
        )
        # fetch player count
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
    except Exception as e:
        info_logger.error(f"Error fetching player count: {str(e)}")


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


# Below are added
# This function add new item to subs.json file
def add_subscription(sub_type, sub_id, filename="subscriptions.json"):
    global ws
    # Construct the new subscription item
    new_sub = {"action": "sub", "channel": f"{sub_type}:{sub_id}"}
    ws.send(json.dumps(new_sub))
    # Read the current data from the file
    try:
        with open(filename, "r", encoding="utf-8") as file:
            subs = json.load(file)
    except FileNotFoundError:
        subs = []
    except json.JSONDecodeError:
        print("Error reading the subscriptions file. Is it empty or malformed?")
        return False

    # Add the new subscription to the list
    subs.append(new_sub)

    # Write the updated list back to the file
    try:
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(subs, file, indent=4)
        return True
    except Exception as e:
        print(f"Error writing to the JSON file: {e}")
        return False


# This function delete the item if in subs.json file
def delete_subscription(sub_type, sub_id, filename="subscriptions.json"):
    # Construct the subscription item to be deleted
    global ws
    target_sub = {"action": "sub", "channel": f"{sub_type}:{sub_id}"}

    ws.send(json.dumps(target_sub))
    try:
        # Read the current data from the file
        with open(filename, "r", encoding="utf-8") as file:
            subs = json.load(file)

        # Check if the subscription is in the list and remove it
        if target_sub in subs:
            subs.remove(target_sub)
        else:
            print("Subscription not found in the file.")
            return False

        # Write the updated list back to the file
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(subs, file, indent=4)
        return True

    except FileNotFoundError:
        print("File not found. Please check the file path.")
        return False
    except json.JSONDecodeError:
        print("Error reading the JSON file. Is it malformed?")
        return False
    except Exception as e:
        print(f"Error handling the JSON file: {e}")
        return False


# !sub (char/ship/corp/system) name
@bot.command(name="sub")
async def sub(ctx, entity_type: str, *, entity_name: str):
    # Check if the entity_type is valid
    if entity_type.lower() not in ["char", "ship", "system", "corp"]:
        await ctx.send(
            "Invalid search type. Please select from **char**, **ship**, **system** or **corp**."
        )
        return

    url = "https://esi.evetech.net/latest/universe/ids/?datasource=tranquility&language=en"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=[entity_name], headers=headers)

    if response.status_code != 200:
        await ctx.send("Failed to communicate with the EVE Online API.")
        return

    data = response.json()
    # Check if the desired type is in the response
    if entity_type.lower() == "char" and "characters" in data:
        # Logic to handle character type
        characters = data["characters"]
        # Further logic to display characters or use the information
        await ctx.send(
            f'Character found: {", ".join([char["name"] for char in characters])}'
        )
        add_subscription("character", f'{characters[0]["id"]}')

    elif entity_type.lower() == "ship" and "inventory_types" in data:
        # Logic to handle inventory type
        inventory_types = data["inventory_types"]
        # Further logic to display inventory types or use the information
        await ctx.send(
            f'Ship found: {", ".join([item["name"] for item in inventory_types])}'
        )
        add_subscription("ship", f'{inventory_types[0]["id"]}')

    elif entity_type.lower() == "system" and "systems" in data:
        # Logic to handle inventory type
        system = data["systems"]
        # Further logic to display inventory types or use the information
        await ctx.send(f'System found: {", ".join([item["name"] for item in system])}')
        add_subscription("system", f'{system[0]["id"]}')

    elif entity_type.lower() == "corp" and "corporations" in data:
        # Logic to handle inventory type
        corporation = data["corporations"]
        # Further logic to display inventory types or use the information
        await ctx.send(
            f'Corporation found: {", ".join([item["name"] for item in corporation])}'
        )
        add_subscription("corporation", f'{corporation[0]["id"]}')
    else:
        await ctx.send("No matching data found for the given type and name.")


# !unsub (char/ship/corp/system) name
@bot.command(name="unsub")
async def unsub(ctx, entity_type: str, *, entity_name: str):
    # Check if the entity_type is valid
    if entity_type.lower() not in ["char", "ship", "system", "corp"]:
        await ctx.send(
            "Invalid search type. Please select from **char**, **ship**, **system** or **corp**."
        )
        return

    url = "https://esi.evetech.net/latest/universe/ids/?datasource=tranquility&language=en"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=[entity_name], headers=headers)

    if response.status_code != 200:
        await ctx.send("Failed to communicate with the EVE Online API.")
        return

    data = response.json()

    # Check if the desired type is in the response
    if entity_type.lower() == "char" and "characters" in data:
        # Logic to handle character type
        characters = data["characters"]
        # Further logic to display characters or use the information
        await ctx.send(
            f'Character found: {", ".join([char["name"] for char in characters])}'
        )
        delete_subscription("character", f'{characters[0]["id"]}')

    elif entity_type.lower() == "ship" and "inventory_types" in data:
        # Logic to handle inventory type
        inventory_types = data["inventory_types"]
        # Further logic to display inventory types or use the information
        await ctx.send(
            f'Ship found: {", ".join([item["name"] for item in inventory_types])}'
        )
        delete_subscription("ship", f'{inventory_types[0]["id"]}')

    elif entity_type.lower() == "system" and "systems" in data:
        # Logic to handle inventory type
        system = data["systems"]
        # Further logic to display inventory types or use the information
        await ctx.send(f'System found: {", ".join([item["name"] for item in system])}')
        delete_subscription("system", f'{system[0]["id"]}')

    elif entity_type.lower() == "corp" and "corporations" in data:
        # Logic to handle inventory type
        corporation = data["corporations"]
        # Further logic to display inventory types or use the information
        await ctx.send(
            f'Corporation found: {", ".join([item["name"] for item in corporation])}'
        )
        delete_subscription("corporation", f'{corporation[0]["id"]}')
    else:
        await ctx.send("No matching data found for the given type and name.")


# !list  list currently subscribed characters, ships, corps and systems
@bot.command(name="list")
async def list(ctx):
    filename = "subscriptions.json"
    characters = []
    corps = []
    groups = []
    ships = []
    systems = []

    try:
        # Read the current data from the file
        with open(filename, "r", encoding="utf-8") as file:
            subs = json.load(file)

        # Iterate through subscriptions and sort IDs into respective lists
        for sub in subs:
            channel = sub.get("channel", "")
            if ":" in channel:
                type, id = channel.split(":")
                if type == "character":
                    response = requests.get(
                        f"https://esi.evetech.net/latest/characters/{id}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        name = data.get("name")
                        if name:
                            characters.append(name)

                elif type == "corporation":
                    response = requests.get(
                        f"https://esi.evetech.net/latest/corporations/{id}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        name = data.get("name")
                        if name:
                            corps.append(name)
                elif type == "group":
                    response = requests.get(
                        f"https://esi.evetech.net/latest/universe/groups/{id}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        name = data.get("name")
                        if name:
                            groups.append(name)
                elif type == "ship":
                    response = requests.get(
                        f"https://esi.evetech.net/latest/universe/types/{id}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        name = data.get("name")
                        if name:
                            ships.append(name)
                elif type == "system":
                    response = requests.get(
                        f"https://esi.evetech.net/latest/universe/systems/{id}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        name = data.get("name")
                        if name:
                            systems.append(name)

    except FileNotFoundError:
        print("File not found. Please check the file path.")
        return {}
    except json.JSONDecodeError:
        print("Error reading the JSON file. Is it malformed?")
        return {}
    except Exception as e:
        print(f"Error handling the JSON file: {e}")
        return {}
    result = "**Currently subscribing - **\n\n"
    if characters:
        result += "**characters:**\n" + "\n".join(characters) + "\n\n"
    if corps:
        result += "**corporations:**\n" + "\n".join(corps) + "\n\n"
    if groups:
        result += "**groups:**\n" + "\n".join(groups) + "\n\n"
    if ships:
        result += "**ships:**\n" + "\n".join(ships) + "\n\n"
    if systems:
        result += "**systems:**\n" + "\n".join(systems) + "\n"

    # Trim any extra newline characters from the end of the string
    await ctx.send(result.strip())


# End of new code


bot.run(token)
