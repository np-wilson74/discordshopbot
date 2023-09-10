import logging
import os
import json
import requests
import asyncio
import urllib.parse
import sys
import xmltodict

##################################################################################
# EBAY UTIL FUNCTIONS
##################################################################################
def get_ebay_token():
    token = get_from_config("prev-ebay-access-token")
    if token == -1:
        debug_logger.info("Access token not found")

    #request parameters to see if current access token stored works
    SHOPPING_HEADERS = {
        'X-EBAY-API-IAF-TOKEN':'Bearer {token}', 
        'X-EBAY-API-SITE-ID':'0',
        'X-EBAY-API-CALL-NAME':'GeteBayTime',
        'X-EBAY-API-VERSION':'863',
        'X-EBAY-API-REQUEST-ENCODING':'xml'
    }
    SHOPPING_BODY = """
    <?xml version="1.0" encoding="utf-8"?>
    <GeteBayTimeRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    </GeteBayTimeRequest>
    """

    #Make simple request with current access token
    api_result = requests.post(f"https://open.api.ebay.com/shopping", headers=SHOPPING_HEADERS, data=SHOPPING_BODY)
    parsed_result = xmltodict.parse(api_result.text)
   
    #If token accepted, then return the current access token
    if parsed_result['GeteBayTimeResponse']['Ack'] == "Success":
        debug_logger.info(f"got ebay access token from cache: {token[-10:]}")
        return(token)
    
    #Otherwise, grab refresh token and try to refresh our access token
    refresh_token = get_from_config("prev-ebay-refresh-token")
    if refresh_token == -1:
        debug_logger.info("REFRESH TOKEN NOT FOUND")
        return(-1)

    #Get request parameters for refresh request
    TOKEN_HEADERS = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {get_from_config("ebay-auth-token-basic")}'
    }
    REFRESH_TOKEN_BODY = {
        "grant_type": "refresh_token",
        "refresh_token": f"{refresh_token}",
        "scope": "https://api.ebay.com/oauth/api_scope"
    }
    
    #Make request for refresh token
    refresh_token_result = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token", 
        headers=TOKEN_HEADERS, 
        data=REFRESH_TOKEN_BODY
    )
    
    #If refresh token worked, get result, otherwise we need to get a new refresh and access token
    if refresh_token_result.ok:
        refresh_token_result = refresh_token_result.json()
        access_token = refresh_token_result['access_token']
        set_ebay_token(access_token, refresh = False)
        debug_logger.info(f"got ebay access token from refresh: {token[-10:]}")
        return(access_token)
    else:
        debug_logger.info("Didn't get the token")
        return(-1)


def set_ebay_token(token, refresh = False):
    if os.path.exists("/home/ec2-user/config.json"):
        with open("/home/ec2-user/config.json", "r") as f_read:
            config_data = json.load(f_read)
            if refresh:
                config_data['prev-ebay-refresh-token'] = token
            else:
                config_data['prev-ebay-access-token'] = token
        with open("/home/ec2-user/config.json", "w") as f_write:
            json.dump(config_data, f_write)

##################################################################################
# COPIED FROM UTILS.PY 
##################################################################################
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
        logger.addHandler(file_handler)
    return(logger)

def get_from_config(field):
    with open("/home/ec2-user/config.json", "r") as f_read:
        config_data = json.load(f_read)
        try:
            token = config_data[field]
        except:
            return(-1)
    return(token)

debug_logger = setup_logger(f"debug-{__name__}", "debug")


##################################################################################
# INSERT ENCODED URL FROM EBAY TO REFRESH TOKENS
##################################################################################
if __name__ == '__main__':    
    TOKEN_HEADERS = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic TmljaG9sYXMtRGlzY29yZFMtUFJELTFiZmZkOTMzZC1lN2ViZDBmMjpQUkQtYmZmZDkzM2Q3MzM3LTAwYjAtNDYxNy1iMTE5LTFjYzc='
    }
            
    coded_url = sys.argv[1]
    decoded_url = urllib.parse.unquote(coded_url)
    code = decoded_url.split("&code=")[1].split("&expires_in=")[0]

    TOKEN_REQUEST_BODY = {
        "grant_type":"authorization_code",
        "code":f"{code}",
        "redirect_uri":f"{get_from_config('ebay_uri')}"
    }

    refresh_token_request = requests.post("https://api.ebay.com/identity/v1/oauth2/token", headers=TOKEN_HEADERS, data=TOKEN_REQUEST_BODY)
    if refresh_token_request.ok:
        refresh_token_request = refresh_token_request.json()
        access_token = refresh_token_request["access_token"]
        refresh_token = refresh_token_request["refresh_token"]
        set_ebay_token(access_token, refresh=False)
        set_ebay_token(refresh_token, refresh=True)
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ACCESS TOKEN ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print(access_token)
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ REFRESH TOKEN ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print(refresh_token)
        print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        print("Refreshed access and refresh token!")
    else:
        print("Could not get token!")
