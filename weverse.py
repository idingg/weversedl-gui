# import debugpy

import playwright
from playwright.sync_api import sync_playwright
import requests

import os
import datetime
import aiohttp
import asyncio
import re
import json
import xml.etree.ElementTree as ET

import multiprocessing


def searchMpd(mpd_content, header, tag=None):
    ret = []
    try:
        if not mpd_content:
            return []

        # sanitize: remove BOM and any leading junk before the XML declaration/tag
        if mpd_content.startswith('\ufeff'):
            mpd_content = mpd_content.lstrip('\ufeff')
        first_decl = mpd_content.find('<?xml')
        if first_decl == -1:
            first_decl = mpd_content.find('<MPD')
        if first_decl > 0:
            mpd_content = mpd_content[first_decl:]

        # parse namespace
        namespaces = dict(
            re.findall(r'xmlns:([a-zA-Z0-9_]+)=["\']([^"\']+)["\']', mpd_content)
        )

        # parse root
        root = ET.fromstring(mpd_content)

        # Prepare header namespace/local name when header like 'nvod:Source' is given
        header_ns = None
        header_local = header
        if isinstance(header, str) and ':' in header:
            prefix, local = header.split(':', 1)
            header_local = local
            header_ns = namespaces.get(prefix)

        # -----------------------------------------------------------
        # check if root tag(MPD) itself is the search target
        # -----------------------------------------------------------
        # Support both plain header names and namespaced 'prefix:Local' formats
        root_matches = False
        if header_ns:
            root_matches = root.tag == f"{{{header_ns}}}{header_local}" or root.tag.endswith('}'+header_local)
        else:
            root_matches = header in root.tag or root.tag.endswith('}'+header)

        if root_matches:
            if tag:
                val = root.get(tag)
                if val:
                    ret.append(val)
            else:
                if root.text:
                    ret.append(root.text)

        # search child tags (sub nodes)
        # handle both namespaced and non-namespaced tags
        # If `tag` is a list of strings, collect a list for each tag in the same order
        if isinstance(tag, (list, tuple)):
            results = [[] for _ in tag]
            for element in root.iter():
                if not isinstance(element.tag, str):
                    continue
                # element match (respect namespace prefix mapping if provided for header)
                element_matches = False
                if header_ns:
                    element_matches = element.tag == f'{{{header_ns}}}{header_local}' or element.tag.endswith('}'+header_local)
                else:
                    element_matches = element.tag == header or element.tag.endswith('}'+header)

                if not element_matches:
                    continue

                # resolve all requested tags for this element
                vals = []
                skip = False
                for t in tag:
                    if not t:
                        skip = True
                        break
                    if ':' in t:
                        prefix, local = t.split(':', 1)
                        ns_uri = namespaces.get(prefix)
                        if ns_uri:
                            val = element.get(f'{{{ns_uri}}}{local}')
                        else:
                            val = element.get(t)
                    else:
                        val = element.get(t)

                    if not val:
                        skip = True
                        break
                    vals.append(val)

                # only if all tags are present, append values to respective result lists
                if not skip:
                    for idx, v in enumerate(vals):
                        results[idx].append(v)

            return results

        # single tag (existing behavior)
        for element in root.iter():
            # element.tag may be like '{namespace}Tag' or 'Tag'
            if not isinstance(element.tag, str):
                continue
            # determine if this element matches the requested header (support 'prefix:Local')
            element_matches = False
            if header_ns:
                element_matches = element.tag == f'{{{header_ns}}}{header_local}' or element.tag.endswith('}'+header_local)
            else:
                element_matches = element.tag == header or element.tag.endswith('}'+header)

            if element_matches:
                if tag:
                    # handle namespaced attributes like 'nvod:m3u'
                    if ':' in tag:
                        prefix, local = tag.split(':', 1)
                        ns_uri = namespaces.get(prefix)
                        if ns_uri:
                            val = element.get(f'{{{ns_uri}}}{local}')
                        else:
                            val = element.get(tag)
                    else:
                        val = element.get(tag)
                    if val:
                        ret.append(val)
                else:
                    if element.text:
                        ret.append(element.text)

    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        return []

    return ret


class MPD:

    def __init__(self, mpd: str) -> None:
        self.__mpd = mpd

    def parseFielname(self, m3u8Url: str):
        endPosition = m3u8Url.find("?")
        startPosition = m3u8Url.rfind("/", 0, endPosition) + 1
        m3u8Filename = m3u8Url[startPosition:endPosition]
        return m3u8Filename

    def getAvailableResolutions(self):
        mpd_label_result = searchMpd(self.__mpd, "nvod:Label")
        if mpd_label_result is None:
            return []
        label_list = list(set(mpd_label_result))

        splitter = "P_"
        resolutions_int = []
        for item in label_list:
            if splitter in item:
                resolutions_int.append(int(item.split(splitter)[0]))

        resolutions_int = sorted(resolutions_int, reverse=True)

        resolutions = []
        for item in resolutions_int:
            resolutions.append(str(item))

        return resolutions

    def getMaxResolution(self):
        resolutions = self.getAvailableResolutions()

        widths = []
        for item in resolutions:
            width = int(item.split("x")[0])
            widths.append(width)

        return resolutions[widths.index(max(widths))]

    def getTsM3u8Url(self, resolution: str):
        if resolution not in self.getAvailableResolutions():
            raise ValueError("Invalid resolution.")

        mpd_m3u8TsUrl = searchMpd(self.__mpd, "Representation", ["width","height","nvod:m3u"])
        for i in range(len(mpd_m3u8TsUrl[0])):
            if resolution == mpd_m3u8TsUrl[0][i] or resolution == mpd_m3u8TsUrl[1][i]:
                return mpd_m3u8TsUrl[-1][i]

        return ""

    # def getTsList(self, resolution: str):
    #     self.__checkMasterUrl()
    #     self.__checkMasterData()
    #     if resolution not in self.getAvailableResolutions():
    #         raise ValueError("resolution error")

    #     tsUrl = self.getTsM3u8Url(resolution)
    #     self.__ts["data"] = Network.downloadM3U8(tsUrl)

    #     m3u8TsFileUrl = []
    #     for item in self.__ts["data"].splitlines():
    #         if ".ts" in item:
    #             m3u8TsFilename = self.parseFielname(self.__ts["url"])
    #             tsFileUrl = self.__ts["url"].replace(m3u8TsFilename, item)
    #             m3u8TsFileUrl.append(tsFileUrl)
    #     return m3u8TsFileUrl

    def parseDuration(self, duration: str):
        pattern = r"PT(?:(\d+(\.\d+)?)H)?(?:(\d+(\.\d+)?)M)?(?:(\d+(\.\d+)?)S)?"
        match = re.match(pattern, duration)

        if not match:
            return 0.0

        hours = float(match.group(1) or 0)
        minutes = float(match.group(3) or 0)
        seconds = float(match.group(5) or 0)

        total_seconds = (hours * 3600) + (minutes * 60) + seconds
        return total_seconds

    def getRunningTime(self):
        mpd_duration_result = searchMpd(self.__mpd, "MPD", "mediaPresentationDuration")
        duration = mpd_duration_result[0] if mpd_duration_result else "PT0S"
        runningtime = self.parseDuration(duration)

        return round(runningtime)

    def getSpriteUrl(self):
        """Extract sprite/thumbnail URLs from the MPD's nvod:Source elements."""
        _spriteUrl = searchMpd(self.__mpd, "nvod:Source")

        spriteUrl = []
        if not _spriteUrl:
            return []

        for item in _spriteUrl:
            if item and "video" in item and ".jpg" in item:
                spriteUrl.append(item.split("?")[0])

        return spriteUrl

    def getDuration(self) -> float:
        mpd_durations = searchMpd(self.__mpd, "S", "d")

        if not mpd_durations:
            return 0.0

        mpd_durations = [float(duration) for duration in mpd_durations]
        return max(mpd_durations) / 1000

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
    __title = ""
    __mpd = ""
    __pageHTML = ""

    def __init__(self, url: str) -> None:
        self.__url = url
        self.getPage()

    def __browserStart(self, playwright):
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

    def __parseHtmlByClass(self, html: str, divClassName: str):
        pattern = (
            rf'<(\w+)[^>]*class=["\']{re.escape(divClassName)}["\'][^>]*>(.*?)</\1>'
        )

        match = re.search(pattern, html, re.DOTALL)

        if match:
            return match.group(2).strip()
        return None

    def __parseTitle(self, html: str):
        return self.__parseHtmlByClass(html, "media-post-header-_-title")

    def __getMpd(self, responses: list):
        mpd = None

        for item in responses:
            if "playInfo" in item["url"]:
                playinfo = item["content"].text()
                mpd = json.loads(playinfo)["playback"]
                break

        return mpd

    def __loadPage(self, browser, url: str):
        networkResponses = []
        page = browser.new_context().new_page()
        page.on(
            "response",
            lambda response: networkResponses.append(
                {"url": response.url, "content": response}
            ),
        )

        addr = url
        page.goto(url=addr, wait_until="networkidle", timeout=30000)

        pageHTML = page.content()
        pageTitle = self.__parseTitle(pageHTML)
        mpd = self.__getMpd(networkResponses)

        return pageTitle, mpd, pageHTML

    def getPage(self, url: str = ""):
        self.__checkUrl()
        self.__thumbnailUrl = ""

        playwright = sync_playwright().start()
        browser = self.__browserStart(playwright)

        try:
            pageTitle, mpd, pageHTML = self.__loadPage(browser, self.__url if url == "" else url)
            self.__title = pageTitle
            self.__mpd = mpd
            self.__pageHTML = pageHTML

        except Exception as e:
            print(e)
            return []

        self.__browserClose(browser)
        playwright.stop()

    def getPageTitle(self) -> str:
        if self.__title == "":
            self.getPage(self.__url)
        return self.__title or ""

    # def getLiveDate(self):
    # artistProfileHtml = self.getArtistProfileContainer()
    # divClassName = "LiveArtistProfileView_info_wrap"
    # print(self.getDivClassHtml(artistProfileHtml, divClassName))

    def isOnLive(self) -> bool:
        return False
        # if len(self.getThumbnailUrl()) > 0:
        if self.getThumbnailUrl() != "":
            return True
        return False

    def getMPD(self):
        self.checkMpd()

        return self.__mpd

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

    def checkMpd(self):
        if self.__mpd == "":
            raise ValueError("mpd unavailable error")


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
