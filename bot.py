import enum
import asyncio
import nest_asyncio
import discord
from utils import *
from discord import app_commands
from cleantext import clean
from constants import *
import json
import os
import ClientSession

#Create config.json file if doesn't exist (it should)
if os.path.exists("/home/ec2-user/config.json"):
    pass
else:
    configTemplate = {"Token:": ""}

    with open("/home/ec2-user/config.json", "w+") as f: #TODO: secure this part with S3
        json.dump(configTemplate, f)

debug_logger = setup_logger(f"debug-{__name__}", "debug")
data_logger = setup_logger(f"data-{__name__}", "data")
suggestion_logger = setup_logger(f"suggestion-{__name__}", "suggestion")

#Simply defines list of shops that appear in /buy command
class Shopping_Sites(enum.Enum):
    Amazon = 1
    Etsy = 3
    Ebay = 4
#    Wish = 5
#    Target = 6
#    Walmart = 7


async def run_discord_bot(token):
    #Setup client and commands to run
    TOKEN = token
    intents = discord.Intents.default()
    intents.message_content = True

    client = discord.Client(command_prefix='/', intents=intents)
    tree = app_commands.CommandTree(client)

    #Adding this here so we have a persistent ClientSession once the bot starts
    client_sess = asyncio_run(ClientSession.CS().create())
    
    @client.event
    async def on_ready():
        #Makes sure commands up to date, logging
        await tree.sync()
        debug_logger.info(f'{client.user} is now running!')

    @tree.command(name = "help", description = "Learn how to use DiscordShopBot!")
    async def help(ctx):
        await ctx.response.send_message(HELP_MESSAGE)

    @tree.command(name = "about", description = "See information about DiscordShopBot!")
    async def about(ctx):
        await ctx.response.send_message(ABOUT_MESSAGE)
    
    @tree.command(name = "suggestion", description = "Have feedback? Let us know!")
    @app_commands.describe(suggestion="Your feedback")
    async def suggestion(ctx, suggestion: str):
        suggestion_logger.info(f"{ctx.user} says: {suggestion}") 
        await ctx.response.send_message(f"Thanks {ctx.user} for your suggestion!")

    #TODO: Find a away to capitalize Item and Shop for parameter name
    @tree.command(name = "buy", description = "Search for any item within a range of retailers!")#, guild=discord.Object(id=1108985839154896957))
    @app_commands.describe(item="The search term for the item you wish to buy!", shop="The site that you wish to shop from!")
    async def buy(ctx, item: str, shop: Shopping_Sites):
        data_logger.info(log_context(ctx, shop))
        debug_logger.info(f"{ctx.token} - {ctx.user} buying {item} from {shop.name}")
        links = []
        num_results = 3 #hardcoded currently, might turn into actual parameter later

        try:
            #Immediately defer so we have time to make calls
            await ctx.response.defer()
            debug_logger.info(f"{ctx.token} - made it past defer step")
            #Remove illegal characters from user input
            delchars = ''.join(c for c in map(chr, range(256)) if c not in (string.punctuation + string.digits + string.ascii_letters) )
            #change spaces for other chars since no space in urls
            space_replacer = '+'
            if shop.value == 5:
                space_replacer = '%20' 
            item_parsed = clean(item, no_emoji=True)
            item_parsed = item_parsed.replace(' ', space_replacer)
            item_parsed = item_parsed.translate({delchars: None})
        except Exception as e:
            debug_logger.info(f"{ctx.token} - something wrong with name parsing or defer: {e}")
            await ctx.followup.send("Sorry! There was an error with your request. Please try again.")
            return()
        debug_logger.info(f"{ctx.token} - item after name parsing: {item_parsed}")
        #If only illegal chars used, or blank sent, then send this response
        if len(item_parsed) == 0:
            await ctx.followup.send(f"Something is wrong with the input, please try again! (Using emojis for search is not recommended)")
            debug_logger.info(f"User gave invalid input: {item} -> {item_parsed}")
            return()

        #For each shop, start task to get the links, code for that process in utils.py
        #Note, didn't use switch cus it didn't work with version of python on AWS, but totally could otherwise
        if shop.value == 1:
            task = asyncio.create_task(get_amazon_links(item_parsed, num_results, ctx, client_sess))
            links = await task
            #links = get_amazon_links(item_parsed,num_results, ctx)
        elif shop.value == 2: #DEPRECATED - unless I can find way to get aliexpress affiliate status
            #links = get_alibaba_links(item_parsed,num_results, ctx)
            task = asyncio.create_task(get_alibaba_links(item_parsed, num_results, ctx, client_sess))
            links = await task
            debug_logger.info(f"{ctx.token} - this should be deprecated, how did we get here?")
        elif shop.value == 3:
            #links = get_etsy_links(item_parsed,num_results, ctx)
            task = asyncio.create_task(get_etsy_links(item_parsed, num_results, ctx, client_sess))
            links = await task
        elif shop.value == 4:
            #links = get_ebay_links(item_parsed,num_results, ctx)
            task = asyncio.create_task(get_ebay_links(item_parsed, num_results, ctx, client_sess))
            links = await task
        elif shop.value == 5:
            #links = get_wish_links(item_parsed,num_results, ctx)
            task = asyncio.create_task(get_wish_links(item_parsed, num_results, ctx, client_sess))
            links = await task
        elif shop.value == 6:
            #links = get_target_links(item_parsed,num_results, ctx)
            task = asyncio.create_task(get_target_links(item_parsed, num_results, ctx, client_sess))
            links = await task
        elif shop.value == 7:
            #links = get_walmart_links(item,num_results, ctx)
            task = asyncio.create_task(get_walmart_links(item_parsed, num_results, ctx, client_sess))
            links = await task

        debug_logger.info(f"{ctx.token} - got thru the link retrieval process for {item} at {shop}")
        #prepare first part of the message to return to users
        listing_num_str = ""
        if num_results == 1:
            listing_num_str = f"listing"
        else:
            listing_num_str = f"{num_results} listings"

        #Format user name correctly
        if "#" in str(ctx.user):
            user_formatted = "".join(str(ctx.user).split("#")[:-1])
        else:
            user_formatted = str(ctx.user)

        #Format non-embed part of response, then use links retrieved to form full resposne (see utils.py)
        response_message = f"Hey {user_formatted}! Here's the top {listing_num_str} for {clean(item, no_emoji=True)} at {shop.name}:"
        
        await ctx.followup.send(response_message, embeds=generate_response_message(ctx.user, shop, item, links, ctx))
    
    client.run(TOKEN)
