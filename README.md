# zkillboard-discord-bot
A Discord bot that posts killmails from zkillboard.com to a Discord channel.

## How to use
1. Clone the repository
2. Install the requirements with `pip install -r requirements.txt`
3. Create a Discord bot and add it to your server
4. Copy the bot token and paste it into the `config.py` file
5. Copy the channel ID of the channel you want the bot to post in and paste it into the `config.py` file
6. Run the bot with `python bot.py`
7. Specify the killmails you want to post in the `subscriptions.json` file

## Killmail Configuration
For details on how to configure the killmails you want to post, see the [zkillboard Websocket Documentation](https://github.com/zKillboard/zKillboard/wiki/Websocket)

## Using Docker
1. Clone the repository
2. Create a Discord bot and add it to your server
3. Copy the bot token and paste it into the `config.py` file
4. Copy the channel ID of the channel you want the bot to post in and paste it into the `config.py` file
5. Specify the killmails you want to post in the `subscriptions.json` file
6. Deploy the bot with `deploy.sh`