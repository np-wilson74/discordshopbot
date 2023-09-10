import aiohttp
import asyncio
from aiohttp import TCPConnector
from aiohttp import ClientSession
from utils import setup_logger

debug_logger = setup_logger(f"debug-{__name__}", "debug")

class CS:
    #_cs: ClientSession
    def __init__(self):
        self._conn = None
        self._cs = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args, **kwargs):
        await self.close()

    async def create(self):
        self._conn = TCPConnector(limit=1000)
        self._cs = ClientSession(connector=self._conn)
        return self

    async def close(self) -> None:
        if not self._cs.closed:
            await self._cs.close()

    async def get(self, url):
        async with self._cs.get(url) as resp:
            return await resp.text()

    async def get_requests(self, URLS, headers=None, isJSON=True, retry=False):
        responses = []
        session = self._cs
        try:
            #health checks for session:
            if session.closed:
                self._cs = ClientSession(connector=self._conn)
                session = self._cs
            
            if headers is not None:
                #If only 1 header given, use it for all, otherwise number of urls and headers must match
                if len(headers) != len(URLS) and len(headers) != 1:
                    print("Len of headers needs to either match len urls or be 1")
                    debug_logger.info("Len of headers needs to either match len urls or be 1")
                    return(-1)
                elif len(headers) != 1:
                    for i in range(len(URLS)):
                        #use appropriate header and url to get response either as text or JSON
                        async with session.get(URLS[i], headers=headers[i]) as response:
                            if response.ok and isJSON:
                                res = await response.json()
                            elif response.ok:
                                res = await response.text()
                            else:
                                #If the response is error, return -1 and log error
                                res = await response.text()
                                debug_logger.info(f"request failed: {res}")
                                return(-1)
                            responses.append(res)
                else:
                    for url in URLS:
                        async with session.get(url, headers=headers[0]) as response:
                            if response.ok and isJSON:
                                res = await response.json()
                            elif response.ok:
                                res = await response.text()
                            else:
                                res = await response.text()
                                debug_logger.info(f"request failed: {res}")
                                return(-1)
                            responses.append(res)
            else:
                for url in URLS:
                    async with session.get(url) as response:
                        if response.ok and isJSON:
                            res = await response.json()
                        elif response.ok:
                            res = await response.text()
                        else:
                            res = await response.text()
                            debug_logger.info(f"request failed: {res}")
                            return(-1)
                        responses.append(res)
            #for convenience, if there's only 1 response, don't put it in list, just return outright
            if len(responses) == 1:
                return(responses[0])
            else:
                return(responses)
        except:
            #If something fails, remake the session and try again
            #If second try, then we don't retry
            debug_logger.info("something went wrong with get_request")
            if not retry:
                debug_logger.info("retrying get_request")
                self._cs = ClientSession(connector=self._conn)
                return( self.get_requests(URLS, headers=headers, isJSON=isJSON, retry=True) )
            else:
                debug_logger.info("second try failed")
                return( -1 )
