# import debugpy

import playwright
from playwright.sync_api import sync_playwright
import requests

import os
import datetime
import aiohttp
import asyncio

# from multiprocessing import Pool
import multiprocessing


class M3U8:
    __master: dict = {"url": "", "data": ""}
    __ts: dict = {"url": "", "data": ""}

    def __init__(self, masterUrl: str) -> None:
        self.__master: dict = {"url": "", "data": ""}
        self.__ts: dict = {"url": "", "data": ""}
        self.__master["url"] = masterUrl
        self.__master["data"] = Network.downloadM3U8(self.__master["url"])

    def parseFielname(self, m3u8Url: str):
        endPosition = m3u8Url.find("?")
        startPosition = m3u8Url.rfind("/", 0, endPosition) + 1
        m3u8Filename = m3u8Url[startPosition:endPosition]
        return m3u8Filename

    def getAvailableResolutions(self):
        self.__checkMasterUrl()
        self.__checkMasterData()

        resolutions = []
        for item in self.__master["data"].split(","):
            if "RESOLUTION=" in item:
                startPosition = item.find("=") + 1
                endPosition = item.find("\n")
                resolutions.append(item[startPosition:endPosition])
        return resolutions

    def getMaxResolution(self):
        resolutions = self.getAvailableResolutions()

        widths = []
        for item in resolutions:
            width = int(item.split("x")[0])
            widths.append(width)

        return resolutions[widths.index(max(widths))]

    def getm3u8TsUrl(self, resolution: str):
        self.__checkMasterUrl()
        self.__checkMasterData()

        if resolution not in self.getAvailableResolutions():
            raise ValueError("Invalid resolution.")

        for item in self.__master["data"].split(","):
            if resolution in item:
                masterUrlFilename = self.parseFielname(self.__master["url"])
                filenameForResolution = item.splitlines()
                tsUrl = self.__master["url"].replace(
                    masterUrlFilename, filenameForResolution[1]
                )
                # if resolution == None:
                #     self.__ts["url"] = tsUrl
                return tsUrl
        return None

    def getTsList(self, resolution: str):
        self.__checkMasterUrl()
        self.__checkMasterData()
        if resolution not in self.getAvailableResolutions():
            raise ValueError("resolution error")

        tsUrl = self.getm3u8TsUrl(resolution)
        self.__ts["data"] = Network.downloadM3U8(tsUrl)

        m3u8TsFileUrl = []
        for item in self.__ts["data"].splitlines():
            if ".ts" in item:
                m3u8TsFilename = self.parseFielname(self.__ts["url"])
                tsFileUrl = self.__ts["url"].replace(m3u8TsFilename, item)
                m3u8TsFileUrl.append(tsFileUrl)
        return m3u8TsFileUrl

    def getRunningTime(self):
        self.__checkMasterUrl()
        self.__checkMasterData()

        self.__ts["url"] = self.getm3u8TsUrl(self.getMaxResolution())
        # if self.__ts["data"] == "":
        #     self.__ts["data"] = Network.downloadM3U8(self.__ts["url"])
        self.__ts["data"] = Network.downloadM3U8(self.__ts["url"])

        runningTime: float = 0.0
        for item in self.__ts["data"].splitlines():
            if "#EXTINF:" in item:
                runningTime += float(item.split(":", 1)[-1].strip(","))

        return round(runningTime)

    def getDuration(self) -> float:
        self.__checkMasterUrl()
        self.__checkMasterData()

        self.__ts["url"] = self.getm3u8TsUrl(self.getMaxResolution())
        self.__ts["data"] = Network.downloadM3U8(self.__ts["url"])

        for item in self.__ts["data"].splitlines():
            if "EXT-X-TARGETDURATION" in item:
                return float(item.split(":", 1)[-1])

        return None

    def __checkMasterUrl(self):
        if self.__master["url"] == "":
            raise ValueError("m3u8 url error")

    def __checkMasterData(self):
        if self.__master["url"] == "":
            raise ValueError("m3u8 url error")
        if self.__master["data"] == "":
            self.__master["data"] = Network.downloadM3U8(self.__master["url"])


class Network:
    __url = ""
    __title = None
    __requests = []
    __pageHTML = ""
    __knownUrls: list = []
    __thumbnailUrl: str = ""

    def __init__(self, url: str) -> None:
        self.__url = url
        self.getPage()

    def __browserStart(self, playwright: playwright):
        try:
            return playwright.chromium.launch(headless=True, channel="chrome")
        except:
            pass
        try:
            return playwright.chromium.launch(headless=True, channel="msedge")
        except:
            pass
        try:
            return playwright.firefox.launch(headless=True)
        except:
            pass

        return None

    def __browserClose(self, browser):
        browser.close()

    # def getUrl():
    #     # return "https://weverse.io/fromis9/live/4-165555875"
    #     return "https://weverse.io/fromis9/live/1-135588399"

    def __loadPage(self, browser, url: str):
        networkRequests = []
        page = browser.new_context().new_page()
        page.on(
            "request",
            lambda request: networkRequests.append([request.method, request.url]),
        )

        addr = url
        page.goto(url=addr, wait_until="networkidle", timeout=30000)
        pageTitleParsed = page.title().split("-", 1)[0].strip()
        pageHTML = page.content()

        return pageTitleParsed, networkRequests, pageHTML

    def getPage(self):
        self.__checkUrl()
        self.__thumbnailUrl = ""

        for url, title, request, html in self.__knownUrls:
            if url == self.__url:
                self.__title = title
                self.__requests = request
                self.__pageHTML = html
                return
                # return request

        playwright = sync_playwright().start()
        browser = self.__browserStart(playwright)

        try:
            pageTitle, networkRequests, pageHTML = self.__loadPage(browser, self.__url)
            self.__title = pageTitle
            self.__requests = networkRequests
            self.__pageHTML = pageHTML

            if self.isOnLive() == False:
                self.__knownUrls.append(
                    [self.__url, self.__title, self.__requests, self.__pageHTML]
                )
        except Exception as e:
            print(e)
            return []

        self.__browserClose(browser)
        playwright.stop()

        # return networkRequests

    def getPageTitle(self) -> str:
        if self.__title == None:
            self.getPage(self.__url)
        return self.__title

    def getPageHTML(self) -> str:
        if self.__pageHTML == "":
            self.getPage(self.__url)
        return self.__pageHTML

    # def isMobilePage(self) -> bool:
    #     if self.getPageHTML().find("MobileLiveArtistProfileView_container") != -1:
    #         return True
    #     return False

    # def getDivClassHtml(self, html: str, divClassName: str):
    #     startpos = html.rfind("<div", 0, html.find(divClassName))

    #     divCounter = 0
    #     # endpos = 0
    #     for i in range(startpos, len(html)):
    #         if html[i : i + 4] == "<div":
    #             divCounter += 1
    #         elif html[i : i + 5] == "</div":
    #             divCounter -= 1
    #         if divCounter == 0:
    #             endpos = i
    #             break

    #     return html[startpos:endpos]

    # def getArtistProfileContainer(self):
    #     html = self.getPageHTML()

    #     divClassName = "LiveArtistProfileView_container"
    #     if self.isMobilePage():
    #         divClassName = "MobileLiveArtistProfileView_content_wrap"

    #     return self.getDivClassHtml(html, divClassName)

    # def getLiveDate(self):
    # artistProfileHtml = self.getArtistProfileContainer()
    # divClassName = "LiveArtistProfileView_info_wrap"
    # print(self.getDivClassHtml(artistProfileHtml, divClassName))

    def isOnLive(self) -> bool:
        # if len(self.getThumbnailUrl()) > 0:
        if self.getThumbnailUrl() != "":
            return True
        return False

    def getThumbnailUrl(self) -> str:
        if self.__requests == []:
            return ""

        if self.__thumbnailUrl != "":
            return self.__thumbnailUrl

        for item in self.__requests:
            if "thumbnail" in item[1] and ".jpg" in item[1]:
                return item[1]

        return ""

    def getSpriteUrl(self):
        self.__checkRequests()

        spriteUrl = []
        for item in self.__requests:
            if "sprite_" in item[1]:
                spriteUrl.append(item[1])
        return spriteUrl

    # def getM3U8MasterUrl(self):
    #     self.__checkRequests()

    #     m3u8Url = ""
    #     for item in self.__requests:
    #         if ".m3u8" in item[1]:
    #             m3u8Url = item[1]
    #             return m3u8Url
    #     return None

    def getM3U8MasterUrl(self):
        self.__checkRequests()

        allM3U8Url = []
        for item in self.__requests:
            if ".m3u8" in item[1]:
                allM3U8Url.append((item[1], Network.downloadM3U8(item[1])))

        if allM3U8Url == []:
            return None

        for url, data in allM3U8Url:
            if ("?_lsu_sa_=" in url or "playlist.m3u8?" in url) and ".m3u8" in data:
                return url

        return None

    @staticmethod
    def downloadM3U8(url: str):
        try:
            data = requests.get(url).content.decode()
        except:
            raise Exception("download m3u8 error")
        return data

    @staticmethod
    def downloadBytes(url: str):
        try:
            data = requests.get(url).content
        except:
            raise Exception("download error")
        return data

    def __checkUrl(self):
        if self.__url == "":
            raise ValueError("live url error")

    def __checkRequests(self):
        if self.__requests == []:
            raise ValueError("requests error")


async def __getcontentlen_async(urls):
    # # debugpy.debug_this_thread()
    sum = 0
    for url in urls:
        async with aiohttp.ClientSession() as session:
            async with await session.head(url) as response:
                sum += int(response.headers["Content-Length"])
    return sum


def __run_getcontentlen_async(urls):
    # # debugpy.debug_this_thread()
    return asyncio.run(__getcontentlen_async(urls))


def getM3U8TotalFileSize(tsUrlList: list):
    filesize = 0
    # poolsize = os.cpu_count()
    poolsize = 4 if os.cpu_count() > 4 else os.cpu_count()
    if len(tsUrlList) < poolsize:
        poolsize = len(tsUrlList)
    starttime = datetime.datetime.now()
    with multiprocessing.Pool(poolsize) as p:
        tsurls_sliced = []
        for i in range(poolsize):
            tsurls_sliced.append(
                tsUrlList[
                    int(len(tsUrlList) * i / poolsize) : int(
                        len(tsUrlList) * (i + 1) / poolsize
                    )
                ]
            )
        filesize = sum(p.map(__run_getcontentlen_async, tsurls_sliced))
    return filesize
