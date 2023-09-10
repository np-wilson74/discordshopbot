################################################
# Imports 
################################################
import re
import os
import discord
import json
import logging
from ebay_utils import *
from bs4 import BeautifulSoup
import string
import asyncio
import nest_asyncio
from fake_useragent import UserAgent
import multiprocessing as mp
import aiohttp
import urllib.parse

################################################
# Logging Utils
################################################

def setup_logger(module_name:str, fname:str):
    logging_formatter = logging.Formatter(
        ("%(asctime)s : " "%(levelname)s : " "%(name)s : " "%(message)s")
    )
    screen_handler = logging.StreamHandler()
    screen_handler.setFormatter(logging_formatter)
    
    file_handler = logging.FileHandler(f"/home/ec2-user/logs/{fname}.log")
    file_handler.setFormatter(logging_formatter)

    logger = logging.getLogger(module_name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        #logger.addHandler(screen_handler)
        logger.addHandler(file_handler)
    return(logger)

debug_logger = setup_logger(f"debug-{__name__}", "debug")
data_logger = setup_logger(f"data-{__name__}", "data")
api_logger = setup_logger(f"api-{__name__}", "api_calls")

################################################
# Link Retrieval Functions
################################################
#
# Purpose: Return a list of affiliate links from a particular store for the top searches for a certain item
# Inputs:
#   - item: parsed text to be searched in website. Spaces and any non-(alphanumeric or symbol) are removed
#   - num: number of links to return
# Output: json format of [{'name': '_name_', 'link': '_link_'}] where name is name of the product listing
# Author: Nicholas Wilson

#TODO: redo this with an API once I have access
async def get_amazon_links(item, num, ctx, session):
    try:
        debug_logger.info(f"{ctx.token} - Beginning amazon link search process")
        
        url = f"https://www.amazon.com/s?k={item}"
        
        #Making straight request to amazon webpage, headers to help obfuscate
        try:
            ua = UserAgent(browsers=['edge', 'chrome', 'safari', 'firefox'])
            user_agent = ua.random
            headers = {
                'dnt': '1',
                'upgrade-insecure-requests': '1',
                'user-agent': f'user_agent',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-user': '?1',
                'sec-fetch-dest': 'document',
                'referer': 'https://www.amazon.com/',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            }

            source_rq = await session.get_requests([url], headers=[headers], isJSON=False)

            #If error is returned from requests call
            if source_rq == -1:
                debug_logger.info(f'{ctx.token} - The Amazon api call produced an erorr response')
                return([{'name': 'Amazon search failed, please try again later.', 'link':'https://www.amazon.com'}])

            source = source_rq
            #Raise error if amazon detects that we are bot
            if "To discuss automated access to Amazon data please contact" in source:
                debug_logger.info(f"{ctx.token} - Amazon doesn't like my automated access")
                raise Exception
            soup = BeautifulSoup(source, 'html.parser')
        except Exception as e:
            debug_logger.info(f"{ctx.token} - Request to url direct failed")
            return([{'name':'Something went wrong!', 'link':'https://www.amazon.com'}])

        #Go thru the listings on page (found by html tags) and add to top_listings
        top_listings = []
        listings = soup.find_all("div", {"data-component-type":f"s-search-result"})

        #Deal with case where amazon could not find listings for query:
        if listings is None or len(listings) < num:
            debug_logger.info(f"{ctx.token} - Amazon did not return any product info (likely bad input)")
            return([{'name': 'No products found for your search. Please try something else!', 'link':'https://www.amazon.com'}])

        for listing in listings:
            if len(top_listings) >= num:
                break
            try:
                #If we fail to find image_src or price, can omit with blank
                image_src = ''
                try:
                    image_src = listing.find('img')['src']
                except:
                    image_src = ''
                price = ''
                try:
                    price = listing.find('span', {'class': 'a-offscreen'}).text
                except:
                    price = ''
                #grab essential info (title, url) from listing
                title_divs = listing.find_all('h2')
                for title_div in title_divs:
                    try:
                        title = title_div.a.span.text
                        raw_href = title_div.a['href']
                        break
                    except:
                        debug_logger.info(f"{ctx.token} - listing info not found in title div, trying next ...")
                        title = -1
                        raw_href = -1
                        continue

                #parse href based on format
                if '&url=' in raw_href:
                    redirect_url = urllib.parse.unquote(raw_href.split('&url=')[1])
                else:
                    redirect_url = raw_href
                #assemble product link and add our affiliate tag
                listing_url = f"https://www.amazon.com{redirect_url}&tag=discordshopbo-20"
                top_listings.append({
                    "name": f'{title}',
                    "link": f'{listing_url}',
                    "price": f'{price}',
                    "currency": f'USD',
                    "image_link": f'{image_src}'
                })
            except Exception as exception:
                debug_logger.info(f"{ctx.token} - Amazon error finding in soup: {exception}")
                debug_logger.info(f"{ctx.token} - Listing soup: {listing}")
                return([{'name':'Something went wrong!', 'link':'https://www.amazon.com'}])
    except Exception as e:
        debug_logger.info(f"{ctx.token} - Amazon error in setup: {e}")
        return([{'name':'Something went wrong!', 'link':'https://www.amazon.com'}])
    return(top_listings) 

#################################################################
# ETSY
#################################################################
async def get_etsy_links(item, num, ctx, session):
    debug_logger.info(f"{ctx.token} - Beginning Etsy link search process")
    #Grab token and make request to Etsy api for list of products
    etsy_headers = {
        'x-api-key':f'{get_from_config("etsy-api-key")}'
    }
    try:
        api_result = await session.get_requests(
            [f'https://openapi.etsy.com/v3/application/listings/active?limit={num}&keywords={item}&sort_on=score'], 
            headers=[etsy_headers]
        )
        api_logger.info(f"{ctx.token} - Etsy search request: {api_result}")

        #If api return error, send other error message
        if api_result == -1:
            debug_logger.info(f'{ctx.token} - The Etsy api call produced an erorr response')
            return([{'name': 'Etsy search failed, please try again later.', 'link':'https://www.etsy.com'}])

        #If no product info found, return error message
        if len(api_result['results']) < num:
            debug_logger.info(f"{ctx.token} - Etsy did not return any product info (likely bad input)")
            return([{'name': 'No products found for your search. Please try something else!', 'link':'https://www.etsy.com'}])

        #Since basic request doesn't have image links usually, do another call for each product with these request urls
        image_request_urls = [f"https://openapi.etsy.com/v3/application/listings/{result['listing_id']}/images" for result in api_result['results']]

        top_listings = []
        listing_results = await session.get_requests(image_request_urls, headers=[etsy_headers])
        api_logger.info(f"{ctx.token} - Etsy product request: {listing_results}")

        for result in api_result['results']:
            listing_id = result['listing_id']
            image_link = next(item['results'][0]['url_fullxfull'] for item in listing_results if item['results'][0]['listing_id'] == listing_id)
            top_listings.append({
                "name": f'{result["title"]}',
                "link": f'{result["url"]}', #TODO: make affiliate version of this
                "price": f'{result["price"]["amount"]}',
                "currency": f'{result["price"]["currency_code"]}',
                "image_link": f'{image_link}'
            })
        return(top_listings)
    except Exception as e:
        debug_logger.info(f"{ctx.token} - Something went wrong with Etsy search: {e}")
        return([{'name':'Something went wrong!','link':'https://www.etsy.com'}])

#################################################################
# EBAY
#################################################################
async def get_ebay_links(item, num, ctx, session):
    debug_logger.info(f"{ctx.token} - Beginning Ebay link search process")
    try:
        #Grab token and info to assemble header for api call
        token = get_ebay_token()
        camp_id = get_from_config("ebay-campaign-id")
        aff_ref_id = get_from_config("ebay-affiliate-reference-id")
        BUYING_HEADERS = {
            'Authorization':f'Bearer {token}', 
            'X-EBAY-C-MARKETPLACE-ID':'EBAY_US',
            'X-EBAY-C-ENDUSERCTX':f'affiliateCampaignId={camp_id},affiliateReferenceId={aff_ref_id}'
        }
        api_result = await session.get_requests(
            [f"https://api.ebay.com/buy/browse/v1/item_summary/search?q={item}&limit={num}"], 
            headers=[BUYING_HEADERS]
        )

        #If there's error with api result, give error
        if api_result == -1:
            debug_logger.info(f'{ctx.token} - The Ebay api call produced an erorr response')
            return([{'name': 'Ebay search failed, please try again later.', 'link':'https://www.ebay.com'}])

        #If user input was invalid and no products returned:
        if 'itemSummaries' not in api_result or len(api_result['itemSummaries']) < num:
            debug_logger.info(f"{ctx.token} - Ebay did not return any product info (likely bad input)")
            return([{'name': 'No products found for your search. Please try something else!', 'link':'https://www.ebay.com'}])

        #Pretty straightforward
        top_listings = []
        for result in api_result['itemSummaries']:
            top_listings.append({
                "name": f'{result["title"]}',
                "link": f'{result["itemAffiliateWebUrl"]}',
                "price": f'{result["price"]["value"]}',
                "currency": f'{result["price"]["currency"]}',
                "image_link": f'{result["image"]["imageUrl"]}'
            })
        return(top_listings)
    except Exception as e:
        debug_logger.info(f"{ctx.token} - Something went wrong with Ebay search: {e}")
        debug_logger.info(f"{ctx.token} - api result for Ebay search: {api_result}")
        return([{'name':'Ebay search failed, please try again later.','link':'https://www.ebay.com'}])

#################################################################
# WISH
#################################################################
def wish_worker(link):
    ua = UserAgent(browsers=['edge', 'chrome', 'safari', 'firefox'])
    user_agent = "Mozilla/5.0 (X11; U; Linux x86_64; en-US) AppleWebKit/532.0 (KHTML, like Gecko) Chrome/114.0.5735.133 Safari/532.0"
    options = get_base_options()
    options.add_argument(f'user-agent={user_agent}')
    
    driver = webdriver.Chrome(options=options)
    attempt_counter = 0
    while attempt_counter < 10:
        attempt_counter += 1
        try:
            driver.get(link)
            nav_menu = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "related-products-scroll-container")))
            break
        except:
            user_agent = ua.random
            options.add_argument(f'user-agent={user_agent}')
            driver.close()
            driver = webdriver.Chrome(options=options)
            debug_logger.info(f"{ctx.token} - Wish get product page failed attempt {attempt_counter} for {driver.current_url}")
    src = driver.page_source

    soup = BeautifulSoup(src, 'html.parser')
    
    title = soup.find("h1", {"data-testid":"product-name"}).text
    price = soup.find("div", {"data-testid":"product-price"}).text
    image_src = soup.find("img", {"class": "ProductImageContainer__MainImageWrapper-sc-1gow8tc-1 hdakVK"})['src']
    listing = {
        'name': f'{title}',
        'link': f'{driver.current_url}', #TODO: make affiliate version of this
        'price': f'{price}',
        'image_link': f'{image_src}',
        'currency': "USD"
    }
    driver.close()
    return(listing)

async def get_wish_links(item, num, ctx, session):
    debug_logger.info(f"{ctx.token} - Beginning Wish link search process")
    ua = UserAgent(browsers=['edge', 'chrome', 'safari', 'firefox'])
    user_agent = "Mozilla/5.0 (X11; U; Linux x86_64; en-US) AppleWebKit/532.0 (KHTML, like Gecko) Chrome/114.0.5735.133 Safari/532.0"
    options = get_base_options()
    options.add_argument(f'user-agent={user_agent}')
    
    driver = webdriver.Chrome(options=options)
    url = f"https://www.wish.com/search/{item}"
    driver.get(url)
    source = driver.page_source
    #source = rq.get(url, headers=HEADERS).text
    soup = BeautifulSoup(source, 'lxml')
    listing_links = []

    #debug_logger.info(f"{ctx.token} - Beginning search for top listings")
    for row in range( num ):
        row_html = soup.find('div', {"data-index": f"{row}"}).div
        for listing in row_html.find_all("div", recursive=False):
            if  len(listing_links) >= num: #if we're past the max number of listing
                #debug_logger.info(f"{ctx.token} - Terminating Wish search appropriately")
                break
            #Get listing info
            listing_href = listing.a['href']
            listing_links.append(f"http://www.wish.com{listing_href}")
    
    try:
        p = mp.Pool(mp.cpu_count())
        listing_links = p.map(wish_worker, listing_links)
    except Exception as exception:
        debug_logger.info(f"{ctx.token} - Error in wish worker: {exception}")
        return([{'name':'Something went wrong!', 'link':'https://www.wish.com'}])

    return(listing_links)


#################################################################
# TARGET
#################################################################
async def get_target_links(item, num, ctx, session):
    debug_logger.info(f"{ctx.token} - Beginning Target link search process")
    try:
        url = f"https://www.target.com/s?searchTerm={item}"
        ua = UserAgent(browsers=['edge', 'chrome', 'safari', 'firefox'])
        #user_agent = ua.random
        user_agent = "Mozilla/5.0 (X11; U; Linux x86_64; en-US) AppleWebKit/532.0 (KHTML, like Gecko) Chrome/114.0.5735.133 Safari/532.0"
        options = get_base_options()
        options.add_argument(f'user-agent={user_agent}')
        
        driver = webdriver.Chrome(options=options)
        driver.get(f"{url}")
        #TODO: maybe add some try block here to make sure this won't fail
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "section")))
        scroll_down(driver)
        source = driver.page_source
        soup = BeautifulSoup(source, 'html.parser')
    except Exception as e:
        debug_logger.info(f"{ctx.token} - error in target setup: {e}")
        return([{"name": f'Something went wrong!', "link":'https://www.target.com'}])
    image_elems = soup.find_all("picture", {"data-test": "@web/ProductCard/ProductCardImage/primary"})
    title_elems = soup.find_all("a", {"data-test": "product-title"})
    price_elems = soup.find_all("span", {"data-test": "current-price"})

    titles = [title.text for title in title_elems]
    image_srcs = [image.img['src'] for image in image_elems]
    prices = [price.span.text for price in price_elems]
    links = [f"https://www.target.com{title['href']}" for title in title_elems]

    top_listings = []
    for i in range(num):
        top_listings.append({
            "name": f'{titles[i]}', 
            "link": f'{links[i]}', #TODO: make affiliate version of this 
            "price": f'{prices[i]}',
            "currency": "USD",
            "image_link": f'{image_srcs[i]}'
        })
    return(top_listings)



#################################################################
# WALMART
#################################################################
async def get_walmart_links(item, num, ctx, session):
    url = f"https://www.walmart.com/search?q={item}"
    ua = UserAgent(browsers=['edge', 'chrome', 'safari', 'firefox'])
    user_agent = ua.random
    HEADERS = ({'User-Agent':
            f'{user_agent}',
            'Accept-Language': 'en-US, en;q=0.5'})
    
    options = get_base_options()
    options.add_argument(f'user-agent={user_agent}')
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.TAG_NAME, "section")))
        source = driver.page_source
        driver.close()
    except:
        source = requests.get(url, headers=HEADERS).text
        print(source)
    
    soup = BeautifulSoup(source, 'html.parser')
    
    image_elems = soup.find_all("img", {'data-testid':'productTileImage'})
    price_elems = soup.find_all("div", {'data-automation-id':'product-price'})
    title_elems = soup.find_all("span", {'data-automation-id':'product-title'})
    link_elems = soup.select('#results-container + div + section > div > div > div > div > a')

    print(len(link_elems))
    print(len(price_elems))
    print(len(title_elems))
    print(len(image_elems))

    return([{"name":"Top Walmart Listing!","link":"https://www.walmart.com"}])


################################################
# Message Generation and Miscellaneous
################################################

#Split up username by #, then exclude last bit and recombine
def format_user(user):
    user_split = str(user).split("#")
    recombined = "#".join(user_split[:-1])
    return(recombined)

def generate_response_message(user, store, item, links, ctx):
    try:
        #Generate small string to make number of listings appropriate in response
        debug_logger.info(f"{ctx.token} - Generating response message for {item} at {store} ...")
        listing_num_str = ""
        if len(links) == 1:
            listing_num_str = "listing"
        elif len(links) > 1:
            listing_num_str = f"{len(links)} listings"
        else:
            #This would usually occur if we're sent empty links list
            debug_logger.info(f"{ctx.token} - something very wrong with number of links")
            debug_logger.info(f"{ctx.token} - links: {links}")
            raise Exception
      
        #For each listing, make an embed with title that is linked to product url, and include image/price if available
        n = 0
        embeds = []
        for link in links:
            embed = discord.Embed(
                color= discord.Colour.dark_teal()
            )
            #If price info available, format string to include
            if 'price' in link and 'currency' in link and len(str(link['price'])) > 0:
                link['price'] = re.sub("[^\d\.\-]", "", link['price'])
                if str(link['currency']).lower() == 'usd':
                    price_str = f" [${link['price']}]"
                else:
                    price_str = f" [{link['price']} {link['currency']}]"
            else:
                price_str = ''

            #Add image to embed if available
            if 'image_link' in link and len(link['image_link']) > 0:
                embed.set_image(url=link['image_link'])
            #Add main link for listing
            embed.add_field(name=f"{n+1}) ", value=f"[{link['name']}{price_str}]({link['link']})", inline=False) #TODO: remove unicode from name
            embeds.append(embed)
            n += 1
        return(embeds)
    except Exception as e:
        debug_logger.info(f"{ctx.token} - Error in message generation: {e}")

#TODO: more robust logging of data - context and client object in ctx
def log_context(ctx, shop):
    ctx_message = f"""token - {ctx.token}
user - {ctx.user}
id - {ctx.id}
channel - {ctx.channel}
channel_id - {ctx.channel_id}
created_at - {ctx.created_at}
data - {ctx.data}
expires_dat - {ctx.expires_at}
extras - {ctx.extras}
guild - {ctx.guild}
guild_id - {ctx.guild_id}
guild_locale - {ctx.guild_locale}
locale - {ctx.locale}
message - {ctx.message}
namespace - {ctx.namespace}
shop_name - {shop.name}
"""
    return(ctx_message)

#Pulled this from stackoverflow, someone said it was legit and it works _/\(._.)/\_
def asyncio_run(future, as_task=True):
    """ 
    A better implementation of `asyncio.run`.

    :param future: A future or task or call of an async method.
    :param as_task: Forces the future to be scheduled as task (needed for e.g. aiohttp).
    """

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # no event loop running:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(_to_task(future, as_task, loop))
    else:
        nest_asyncio.apply(loop)
        return asyncio.run(_to_task(future, as_task, loop))

#Also ripped from stackoverflow :P
def _to_task(future, as_task, loop):
    if not as_task or isinstance(future, asyncio.Task):
        return future
    return loop.create_task(future)

#Grab sensitive data from config.json file
def get_from_config(field):
    with open("/home/ec2-user/config.json", "r") as f_read:
        config_data = json.load(f_read)
        try:
            token = config_data[field]
        except:
            return(-1)
    return(token)

#Test cases for early testing useless in production
async def test_case():
    test_task = asyncio.create_task(get_walmart_links("Floral+Wallpaper", 5))
    value = await test_task
    print(value)

if __name__ == '__main__':    
    asyncio.run(test_case())
