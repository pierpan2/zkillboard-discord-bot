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
global ws_sub_kill_and_loss, ws_sub_only_loss
ws_sub_kill_and_loss = None
ws_sub_only_loss = None

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
processed_hashes = deque(maxlen=hash_limit)

info_logger = logging.getLogger("Discord")
coloredlogs.install(level="INFO", logger=info_logger)
debug_logger = logging.getLogger("WebSocket")
coloredlogs.install(level="DEBUG", logger=debug_logger)
error_logger = logging.getLogger("Error")
coloredlogs.install(level="ERROR", logger=error_logger)

"""
Description: This function is used to send message to discord channel
@:param ws: websocket
@:param message: message received from websocket
@:param track_kill: True if kill is to be tracked
@:return: None
"""


async def send_with_info(channel, km):
    kill_id = km.get("killID")
    kill_hash = km.get("hash")
    url = km.get("url")
    response = requests.get(
        f"https://esi.evetech.net/latest/killmails/{kill_id}/{kill_hash}"
    )
    # Get detailed killmail info from ccp esi
    if response.status_code == 200:
        data = response.json()
        # Retrieve the subscribed characters and corporations
        with open("subscriptions.json", "r") as file:
            subsriptions = json.load(file)
        character_ids = set()
        corp_ids = set()
        for subscription in subsriptions:
            if (
                subscription["action"] == "sub"
                and "character:" in subscription["channel"]
            ):
                character_id = subscription["channel"].split(":")[1]
                character_ids.add(character_id)
            if (
                subscription["action"] == "sub"
                and "corporation:" in subscription["channel"]
            ):
                corp_id = subscription["channel"].split(":")[1]
                corp_ids.add(corp_id)
        # Check if the victim is a subscribed character or in a subscribed corp
        victim = data["victim"]
        victim_char_id = str(victim.get("character_id", ""))
        victim_corp_id = str(victim.get("corporation_id", ""))
        if victim_char_id in character_ids or victim_corp_id in corp_ids:
            response_char = requests.get(
                f"https://esi.evetech.net/latest/characters/{victim_char_id}"
            )
            if response_char.status_code == 200:
                char_data = response_char.json()
                victim_name = char_data.get("name")
            else:
                await channel.send(f"**Fail to get details.**\n{url}")
                return
            response_corp = requests.get(
                f"https://esi.evetech.net/latest/corporations/{victim_corp_id}"
            )
            if response_corp.status_code == 200:
                corp_data = response_corp.json()
                victim_corp_name = corp_data.get("name")
                victim_corp_ticker = corp_data.get("ticker")
            else:
                await channel.send(f"**Fail to get details.**\n{url}")
                return
            await channel.send(
                f"**{victim_name}[{victim_corp_ticker}] FEED** \n{victim_corp_name}\n{url}"
            )
            return
        # Check if the victim is killed by a subscribed character or a subscribed corporation
        # Pre-screen attackers ship type for kill_and_loss list
        killer_ship_id = None
        for attacker in data["attackers"]:
            attacker_char_id = str(attacker.get("character_id", ""))
            attacker_corp_id = str(attacker.get("corporation_id", ""))
            if attacker_char_id in character_ids or attacker_corp_id in corp_ids:
                response_attacker_name = requests.get(
                    f"https://esi.evetech.net/latest/characters/{attacker_char_id}"
                )
                if response_attacker_name.status_code == 200:
                    attacker_data = response_attacker_name.json()
                    attacker_name = attacker_data.get("name")
                else:
                    await channel.send(f"**Fail to get details.**\n{url}")
                    return
                response_attacker_corp = requests.get(
                    f"https://esi.evetech.net/latest/corporations/{attacker_corp_id}"
                )
                if response_attacker_corp.status_code == 200:
                    attacker_corp_data = response_attacker_corp.json()
                    attacker_corp_name = attacker_corp_data.get("name")
                    attacker_corp_ticker = attacker_corp_data.get("ticker")
                else:
                    await channel.send(f"**Fail to get details.**\n{url}")
                    return
                await channel.send(
                    f"**{attacker_name}[{attacker_corp_ticker}] IS KILLING** \n{attacker_corp_name}\n{url}"
                )
                return
            if str(attacker.get("ship_type_id", "")) in kill_and_loss.keys():
                killer_ship_id = attacker.get("ship_type_id", "")
        # Check if the attacker ship type is on the kill_and_loss dic
        if killer_ship_id is not None:
            await channel.send(
                f"**A {kill_and_loss[killer_ship_id]} CONTRIBUTES TO** \n{url}"
            )
            return
        # Check if the victim ship type is subscribed
        victim_ship_id = str(victim.get("ship_type_id", ""))
        if victim_ship_id in kill_and_loss.keys():
            await channel.send(f"**A {kill_and_loss[victim_ship_id]} DEAD:** \n{url}")
            return
        if victim_ship_id in only_loss.keys():
            await channel.send(f"**A {only_loss[victim_ship_id]} DEAD:** \n{url}")
            return

    await channel.send(f"**What happened?**\n{url}")
    return


def on_ws_message(ws, message, track_kill):
    global LAST_MESSAGE_TIME
    data = json.loads(message)
    info_logger.info("Received killmail")
    kill_hash = data.get("hash")
    url = data.get("url")
    ship_id = data.get("ship_type_id")

    if kill_hash and kill_hash not in processed_hashes:
        processed_hashes.append(
            kill_hash
        )  # Adds new hash and may remove the oldest if limit is reached
        # Process the message, e.g., send to Discord channel
        channel = bot.get_channel(channel_id)
        # Send url only if track_kill is True or ship_id is in only_loss
        if channel:
            if track_kill or ship_id in only_loss.values():
                info_logger.info(f"Sending message to channel {channel.name}")
                asyncio.run_coroutine_threadsafe(
                    send_with_info(channel, data), bot.loop
                )
            else:
                info_logger.info("Discard message")
        else:
            error_logger.error("Channel not found")

    else:
        info_logger.info("Duplicate message received, ignoring.")
    LAST_MESSAGE_TIME = time.time()


"""
Description: This function is used to send message to discord channel
@:param ws: websocket
@:param dic: dictionary
"""


def on_ws_open(ws, dic):
    def run(*args):
        if dic == kill_and_loss:
            debug_logger.debug("Subscribing to all kills")
            with open("subscriptions.json", "r") as file:
                subscriptions = json.load(file)
            for subscription in subscriptions:
                ws.send(json.dumps(subscription))
                debug_logger.debug(f"Subscribed to {subscription}")
        for ship_id in dic:
            ws.send(
                json.dumps(
                    {
                        "action": "sub",
                        "channel": f"ship:{ship_id}",
                    }
                )
            )
            debug_logger.debug(f"Subscribed to {dic[ship_id]}")
        debug_logger.debug("Subscribed to all kills")

    debug_logger.debug(f"Opened WebSocket for {dic}")
    threading.Thread(target=run).start()


def start_websocket_kill_and_loss():
    global LAST_MESSAGE_TIME

    ws = websocket.WebSocketApp(
        "wss://zkillboard.com/websocket/",
        on_open=lambda ws: on_ws_open(ws, dic=kill_and_loss),
        on_message=lambda ws, message: on_ws_message(ws, message, track_kill=True),
    )
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.start()
    return ws, ws_thread


def start_websocket_only_loss():
    global LAST_MESSAGE_TIME

    ws = websocket.WebSocketApp(
        "wss://zkillboard.com/websocket/",
        on_open=lambda ws: on_ws_open(ws, dic=only_loss),
        on_message=lambda ws, message: on_ws_message(ws, message, False),
    )
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.start()
    return ws, ws_thread


async def manage_websocket():
    global LAST_MESSAGE_TIME
    LAST_MESSAGE_TIME = time.time()
    global ws_sub_kill_and_loss, ws_sub_only_loss
    ws_sub_kill_and_loss, ws_thread_kill_and_loss = start_websocket_kill_and_loss()
    ws_sub_only_loss, ws_thread_only_loss = start_websocket_only_loss()

    while True:
        await asyncio.sleep(10)  # Check every 10 seconds
        if (time.time() - LAST_MESSAGE_TIME) > inactivity_threshold:
            debug_logger.debug("WebSocket inactive, attempting to reconnect...")

            # Close the WebSocket
            ws_sub_kill_and_loss.close()
            ws_sub_kill_and_loss = None
            ws_sub_only_loss.close()
            ws_sub_only_loss = None
            # Check if the thread is still alive and join it if it is
            if ws_thread_kill_and_loss.is_alive():
                ws_thread_kill_and_loss.join(
                    timeout=10
                )  # Wait for the thread to finish with a timeout

            # Reinitialize the WebSocket and thread
            (
                ws_sub_kill_and_loss,
                ws_thread_kill_and_loss,
            ) = start_websocket_kill_and_loss()
            ws_sub_only_loss, ws_thread_only_loss = start_websocket_only_loss()
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
    info_logger.info(f"Started WebSocket {ws_sub_kill_and_loss}")

    status_update_loop.start()
    info_logger.info("Started status update loop")


# Below are added
# This function add new item to subs.json file
def add_subscription(sub_type, sub_id, filename="subscriptions.json"):
    global ws_sub_kill_and_loss
    # Construct the new subscription item
    new_sub = {"action": "sub", "channel": f"{sub_type}:{sub_id}"}
    ws_sub_kill_and_loss.send(json.dumps(new_sub))
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
    global ws_sub_kill_and_loss
    target_sub = {"action": "sub", "channel": f"{sub_type}:{sub_id}"}

    ws_sub_kill_and_loss.send(json.dumps(target_sub))
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
    if entity_type.lower() not in ["char", "corp"]:
        await ctx.send("Invalid search type. Please select from **char** or **corp**.")
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
    if entity_type.lower() not in ["char", "corp"]:
        await ctx.send("Invalid search type. Please select from **char** or **corp**.")
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
    characters = set()
    corps = set()
    groups = set()
    ships = set()
    systems = set()

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
                            characters.add(name)

                elif type == "corporation":
                    response = requests.get(
                        f"https://esi.evetech.net/latest/corporations/{id}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        name = data.get("name")
                        if name:
                            corps.add(name)
                elif type == "group":
                    response = requests.get(
                        f"https://esi.evetech.net/latest/universe/groups/{id}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        name = data.get("name")
                        if name:
                            groups.add(name)
                elif type == "ship":
                    response = requests.get(
                        f"https://esi.evetech.net/latest/universe/types/{id}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        name = data.get("name")
                        if name:
                            ships.add(name)
                elif type == "system":
                    response = requests.get(
                        f"https://esi.evetech.net/latest/universe/systems/{id}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        name = data.get("name")
                        if name:
                            systems.add(name)
                else:
                    info_logger.info(f"Cannot find id:{id} of type {type}")

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
        result += (
            "**characters:**\n"
            + "\n".join(sorted(characters, key=str.casefold))
            + "\n\n"
        )
    if corps:
        result += (
            "**corporations:**\n" + "\n".join(sorted(corps, key=str.casefold)) + "\n\n"
        )
    if groups:
        result += "**groups:**\n" + "\n".join(sorted(groups, key=str.casefold)) + "\n\n"
    if ships:
        result += "**ships:**\n" + "\n".join(sorted(ships, key=str.casefold)) + "\n\n"
    if systems:
        result += "**systems:**\n" + "\n".join(sorted(systems, key=str.casefold)) + "\n"
    # Trim any extra newline characters from the end of the string
    await ctx.send(result.strip())


# End of new code


bot.run(token)
