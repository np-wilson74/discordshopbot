import bot
import os
import json
from utils import asyncio_run

if __name__ == '__main__':
    #Grab token for bot to run it
    if os.path.exists("/home/ec2-user/config.json"):
        with open("/home/ec2-user/config.json") as f:
            config_data = json.load(f)    
    else:
        config_template = {"Token:": ""} 
        with open("/home/ec2-user/config.json", "w+") as f:
            json.dump(config_template, f)
    
    token = config_data["Token"]

    #Start the bot
    asyncio_run(bot.run_discord_bot(token))
