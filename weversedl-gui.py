import PyQt6.Qt6
import PyQt6.Qt6.plugins
import PyQt6.QtCore
import PyQt6.QtGui
import PyQt6.QtWidgets
import sys
import os
import time
import datetime
import multiprocessing

import weverse
import pic


def findResourceFile(filename: str) -> str:
    loadingPath = "_internal" + os.sep + filename
    if os.path.isfile(loadingPath) == False:
        loadingPath = filename
    if os.path.isfile(loadingPath) == False:
        if hasattr(sys, "_MEIPASS"):
            loadingPath = getattr(sys, "_MEIPASS") + os.sep + filename
    return loadingPath


class Window(PyQt6.QtWidgets.QMainWindow):

    class DownloadVideoThread(PyQt6.QtCore.QThread):
        started = PyQt6.QtCore.pyqtSignal()
        info = PyQt6.QtCore.pyqtSignal(dict)
        complete = PyQt6.QtCore.pyqtSignal(bool)
        error = PyQt6.QtCore.pyqtSignal(Exception)
        __filename: str
        __m3u8Tsurl: str
        __duration: float
        __infoData: dict = {}
        __keepDownload: bool

        def __init__(
            self,
            parent,
            path: str,
            m3u8Tsurl: str | None = None,
            duration: float = 10,
        ):
            PyQt6.QtCore.QThread.__init__(self, parent)

            self.__filename = path
            self.__m3u8Tsurl = m3u8Tsurl
            self.__duration = duration * 5
            self.__keepDownload = True

        def initInfoData(self):
            self.__infoData = {}
            self.__infoData["calulatingFilesize"] = None
            self.__infoData["spentTime"] = None
            self.__infoData["estimatedTime"] = None
            self.__infoData["downloadedFilesize"] = None
            self.__infoData["totalFilesize"] = None
            self.__infoData["downloadSpeed"] = None
            self.__infoData["downloadedPercantage"] = None
            self.__infoData["sleep"] = None
            self.__infoData["sleepTime"] = None
            self.__infoData["newRunningTime"] = None

        def getKeepDownloadFlag(self):
            return self.__keepDownload

        def setKeepDownloadFlag(self, flag: bool):
            self.__keepDownload = flag

        def run(self):
            try:
                self.started.emit()

                m3u8TsUrl = self.__m3u8Tsurl
                last_content = b""
                new_content = weverse.Network.downloadBytes(m3u8TsUrl)

                thisPartFilesize = 0
                nowFilesize = 0
                lastTotalFilesize = 0
                savedTsFile = open(self.__filename, "wb+")
                while new_content != last_content:
                    self.initInfoData()

                    self.__infoData["newRunningTime"] = 0
                    for item in new_content.decode().splitlines():
                        if "#EXTINF:" in item:
                            self.__infoData["newRunningTime"] += float(
                                item.split(":", 1)[-1].strip(",")
                            )
                    self.info.emit(self.__infoData)

                    tsfiles = (
                        new_content.replace(last_content, b"", 1)
                        .decode()
                        .split(sep=",")
                    )
                    if m3u8TsUrl.find("live") != -1:
                        end = len(m3u8TsUrl)
                    elif m3u8TsUrl.find("VOD") != -1:
                        end = m3u8TsUrl.find(".m3u8") + 5
                    start = m3u8TsUrl[: m3u8TsUrl.find(".m3u8")].rfind("/")

                    tsurls = []
                    for item in tsfiles:
                        if item.find(".ts") != -1:
                            tmp = item.splitlines()[1]
                            tsurls.append(
                                m3u8TsUrl.replace(m3u8TsUrl[start + 1 : end], tmp)
                            )

                    cnt = 0
                    poolsize = os.cpu_count()
                    if len(tsurls) < poolsize:
                        poolsize = len(tsurls)
                    start = 0
                    end = start + poolsize
                    download_starttime = datetime.datetime.now()

                    self.__infoData["calulatingFilesize"] = True
                    self.info.emit(self.__infoData)

                    thisPartFilesize = weverse.getM3U8TotalFileSize(tsurls)
                    lastTotalFilesize += thisPartFilesize
                    self.__infoData["totalFilesize"] = lastTotalFilesize

                    self.__infoData["calulatingFilesize"] = False

                    zerotime = str(datetime.timedelta(seconds=0)).split(".")[0]
                    self.__infoData["spentTime"] = zerotime
                    self.__infoData["estimatedTime"] = zerotime
                    self.__infoData["downloadedFilesize"] = 0
                    self.__infoData["downloadSpeed"] = 0.0
                    self.__infoData["downloadedPercantage"] = 0.0
                    self.info.emit(self.__infoData)

                    etime = datetime.datetime.now() - download_starttime
                    with multiprocessing.Pool(poolsize) as p:
                        tsurlslen = len(tsurls)
                        while start < len(tsurls) and self.__keepDownload == True:
                            tsurls_part = tsurls[start:end]
                            download_part_size = 0
                            part_starttime = datetime.datetime.now()
                            for item in p.map(
                                weverse.Network.downloadBytes, tsurls_part
                            ):
                                savedTsFile.write(item)
                                download_part_size += len(item)
                                cnt += 1
                            nowtime = datetime.datetime.now()
                            nowFilesize += download_part_size
                            etime = nowtime - download_starttime
                            barsize = 25

                            spent_time = str(etime).split(".")[0]
                            estimated_time = str(etime / cnt * tsurlslen).split(".")[0]
                            downloaded_filesize = "{:4d}".format(nowFilesize >> 20)
                            totalFilesizeFormatted = "{:4d}".format(
                                thisPartFilesize >> 20
                            )
                            download_speed = (float)(
                                int(
                                    download_part_size
                                    / (nowtime.timestamp() - part_starttime.timestamp())
                                )
                                >> 10
                            ) / 1000
                            download_speed_formated = "{:5.1f}".format(download_speed)
                            percantage = cnt * 100 / tsurlslen
                            downloaded_percantage_formated = "{:6.2f}".format(
                                percantage
                            )
                            download_bar = (" [{:" + str(barsize) + "s}]").format(
                                "|" * int((cnt / tsurlslen) * barsize)
                            )

                            self.__infoData["spentTime"] = spent_time
                            self.__infoData["estimatedTime"] = estimated_time
                            self.__infoData["downloadedFilesize"] = nowFilesize
                            self.__infoData["downloadSpeed"] = download_speed
                            self.__infoData["downloadedPercantage"] = percantage
                            self.info.emit(self.__infoData)

                            print(
                                "\r"
                                + spent_time
                                + " / "
                                + estimated_time
                                + " {0} / {1} MB".format(
                                    downloaded_filesize, totalFilesizeFormatted
                                )
                                + " {0} MB/s".format(download_speed_formated)
                                + " {0} %".format(downloaded_percantage_formated)
                                + download_bar,
                                end="",
                            )
                            start = end
                            end = start + poolsize

                    if self.__keepDownload == False:
                        break

                    if m3u8TsUrl.find("live") != -1:
                        print(
                            "\n{0}초간 이어지는 영상이 있는지 확인 후 저장합니다. 라이브 종료까지 반복됩니다.".format(
                                self.__duration
                            )
                        )
                        savedTsFile.close()

                        self.__infoData["sleep"] = True
                        self.__infoData["sleepTime"] = self.__duration
                        self.info.emit(self.__infoData)

                        time.sleep(self.__duration)

                        self.__infoData["sleep"] = False
                        self.info.emit(self.__infoData)

                        savedTsFile = open(self.__filename, "ab+")
                    last_content = new_content

                    if etime.seconds < self.__duration:
                        time.sleep(self.__duration - etime.seconds)

                    new_content = weverse.Network.downloadBytes(m3u8TsUrl)
                savedTsFile.close()

                self.complete.emit(self.__keepDownload)

            except Exception as e:
                self.error.emit(e)

        def stop(self):
            self.quit()
            self.wait(5000)

    class DownloadPageThread(PyQt6.QtCore.QThread):
        started = PyQt6.QtCore.pyqtSignal()
        complete = PyQt6.QtCore.pyqtSignal(weverse.Network)
        error = PyQt6.QtCore.pyqtSignal(Exception)

        def __init__(self, parent, url: str):
            PyQt6.QtCore.QThread.__init__(self, parent)

            self.url = url

        def run(self):
            try:
                starttime = time.time()
                self.started.emit()

                weverseNetwork = weverse.Network(self.url)

                self.complete.emit(weverseNetwork)
                endtime = time.time()
                print(f"download time : {endtime - starttime}")
                print("page download completed")
            except Exception as e:
                self.error.emit(e)

        def stop(self):
            self.quit()
            self.wait(5000)

    class SpriteThread(PyQt6.QtCore.QThread):
        updatePixmap = PyQt6.QtCore.pyqtSignal(PyQt6.QtGui.QPixmap)

        __isrunning = False
        __maxSpriteCount = 0

        def __init__(
            self,
            parent,
            pixmap: list[PyQt6.QtGui.QPixmap | str],
            interval: float = 1,
            runningTime: int = 400,
        ):
            PyQt6.QtCore.QThread.__init__(self, parent)
            self.pixmap = pixmap
            self.interval = interval
            self.__isrunning = True
            self.__maxSpriteCount = round(runningTime / 10)
            if self.__maxSpriteCount < 10:
                self.__maxSpriteCount = 5
            if self.__maxSpriteCount >= 100:
                self.__maxSpriteCount = 100

        def setInterval(self, interval: float):
            self.interval = interval

        def run(self):
            # pics = pic.getAllCroppedPic(self.pixmap)
            shownSpriteCount = 0
            while self.__isrunning:
                for idx in range(len(self.pixmap)):

                    # for item in self.pixmap:

                    shownSpriteCount += 1
                    if isinstance(self.pixmap[idx], str):
                        self.pixmap[idx] = pic.pixmapFromNetwork(self.pixmap[idx])
                    self.updatePixmap.emit(self.pixmap[idx])

                    time.sleep(self.interval)
                    if shownSpriteCount >= self.__maxSpriteCount:
                        shownSpriteCount = 0
                        break
                    if self.__isrunning == False:
                        break
            print("change sprite ended")

        def stop(self):
            self.__isrunning = False
            self.quit()
            self.wait(5000)

    __margin = 10
    __widgetHeight = 30
    __runningDownloads = []
    __runningSprites = []
    __weverseMPD: weverse.MPD = None
    __resolution: str = None
    __downloadVideoThread: DownloadVideoThread = None
    __lastSaveDir: str = ""
    __thumbnailUrl: str = ""

    def __init__(self):
        super().__init__()
        iconPath = findResourceFile("icon.ico")
        self.setWindowIcon(PyQt6.QtGui.QIcon(iconPath))
        self.initUI()
        self.setFocus()
        self.textboxUrl.setFocus()

    def initUI(self):
        style = "border-style: solid; border-width: 1px; border-color: #999999; border-radius: 2px; "
        stylewhitebg = "border-style: solid; border-width: 1px; border-color: #999999; border-radius: 2px; "
        stylered = "color: #FF0000;"

        self.labelUrl = PyQt6.QtWidgets.QLabel("URL : ", self)
        self.labelUrl.adjustSize()

        self.textboxUrl = PyQt6.QtWidgets.QLineEdit("", self)
        self.textboxUrl.setStyleSheet(style)
        self.textboxUrl.setPlaceholderText("https://weverse.io/...")
        self.textboxUrl.setClearButtonEnabled(True)
        self.textboxUrl.setFixedSize(350, self.__widgetHeight)
        self.textboxUrl.textChanged.connect(self.textdir1Changed)

        self.labelPreview = PyQt6.QtWidgets.QLabel("미리보기", self)
        self.labelPreview.setStyleSheet(stylewhitebg)
        self.labelPreview.setFixedSize(200, 200)
        self.labelPreview.setAlignment(PyQt6.QtCore.Qt.AlignmentFlag.AlignCenter)

        self.labelOnLive = PyQt6.QtWidgets.QLabel("● Live ", self)
        self.labelOnLive.setStyleSheet(stylered)
        self.labelOnLive.adjustSize()
        self.labelOnLive.setHidden(True)

        self.labelTitle = PyQt6.QtWidgets.QLabel("제목", self)
        self.labelTitle.adjustSize()

        self.labelTitleText = PyQt6.QtWidgets.QLabel(self)

        self.labelRunningtimeText = PyQt6.QtWidgets.QLabel(self)
        self.labelRunningtimeText.setStyleSheet(stylewhitebg)
        self.labelRunningtimeText.setHidden(True)

        self.labelResolutionTitle = PyQt6.QtWidgets.QLabel("해상도", self)
        self.labelResolutionTitle.adjustSize()

        self.comboResolution = PyQt6.QtWidgets.QComboBox(self)
        self.comboResolution.setStyleSheet(
            "QComboBox  { " + style + " }"
        )
        self.comboResolution.setHidden(True)
        self.comboResolution.currentTextChanged.connect(self.onComboResolutionChanged)

        self.btnDownload = PyQt6.QtWidgets.QPushButton("다운로드", self)
        self.btnDownload.setStyleSheet(
            "QPushButton { "
            + style
            + " } QPushButton:hover { background-color : #65e0d6; }"
        )
        self.btnDownload.clicked.connect(self.onBtnDownloadClicked)

        self.btnStop = PyQt6.QtWidgets.QPushButton("X", self)
        self.btnStop.setStyleSheet(
            "QPushButton { "
            + style
            + " } QPushButton:hover { background-color : #65e0d6; }"
        )
        self.btnStop.setEnabled(False)
        self.btnStop.clicked.connect(self.onBtnStopClicked)

        self.labelDownloadInfo = PyQt6.QtWidgets.QLabel(self)
        self.labelDownloadInfo.setStyleSheet(stylewhitebg)
        self.labelDownloadInfo.setAlignment(PyQt6.QtCore.Qt.AlignmentFlag.AlignTop)

        self.adjustWidgetPosition()

        self.setWindowTitle("Weverse Live Downloader")

        windowWidth = self.textboxUrl.x() + self.textboxUrl.width() + self.__margin
        windowHeight = (
            self.labelPreview.y() + self.labelPreview.height() + self.__margin
        )
        self.setFixedSize(windowWidth, windowHeight)

        winpos = self.frameGeometry()
        screencenter = (
            PyQt6.QtGui.QGuiApplication.primaryScreen().availableGeometry().center()
        )
        winpos.moveCenter(screencenter)
        self.move(winpos.topLeft())

    def adjustWidgetSize(self):
        self.labelTitleText.adjustSize()
        self.labelRunningtimeText.adjustSize()
        self.comboResolution.adjustSize()
        self.comboResolution.setFixedWidth(
            self.textboxUrl.x()
            + self.textboxUrl.width()
            - self.labelResolutionTitle.x()
            - self.labelResolutionTitle.width()
            - self.__margin
        )
        self.labelDownloadInfo.setFixedSize(
            self.textboxUrl.x()
            + self.textboxUrl.width()
            - self.labelResolutionTitle.x(),
            self.btnDownload.y()
            - self.labelResolutionTitle.y()
            - self.labelResolutionTitle.height()
            - self.__margin * 2,
        )
        self.btnDownload.setFixedSize(
            self.btnStop.x() - self.labelPreview.width() - self.__margin * 3,
            int(self.__widgetHeight * 1.5),
        )
        self.btnStop.setFixedSize(self.btnDownload.height(), self.btnDownload.height())

    def adjustWidgetPosition(self):
        self.adjustWidgetSize()

        maxLabelWidth = max(self.labelTitle.width(), self.labelResolutionTitle.width())

        self.labelUrl.move(
            self.__margin,
            self.__margin + int((self.__widgetHeight - self.labelUrl.height()) / 2),
        )

        self.textboxUrl.move(
            self.labelUrl.x() + self.labelUrl.width() + self.__margin, self.__margin
        )

        self.labelPreview.move(
            self.__margin,
            self.textboxUrl.y() + self.textboxUrl.height() + self.__margin,
        )

        self.labelOnLive.move(
            self.labelPreview.x()
            + self.labelPreview.width()
            - self.labelOnLive.width(),
            self.labelPreview.y(),
        )

        self.labelTitle.move(
            self.labelPreview.x() + self.labelPreview.width() + self.__margin,
            self.labelPreview.y(),
        )

        self.labelTitleText.move(
            self.labelTitle.x() + maxLabelWidth + self.__margin,
            self.labelTitle.y(),
        )

        self.labelRunningtimeText.move(
            self.labelPreview.x()
            + self.labelPreview.width()
            - self.labelRunningtimeText.width(),
            self.labelPreview.y()
            + self.labelPreview.height()
            - self.labelRunningtimeText.height(),
        )

        self.labelResolutionTitle.move(
            self.labelTitle.x(),
            self.labelTitle.y() + self.labelTitle.height() + self.__margin,
        )

        self.comboResolution.move(
            self.labelResolutionTitle.x() + maxLabelWidth + self.__margin,
            self.labelResolutionTitle.y(),
        )

        x = int(
            self.labelPreview.x()
            + self.labelPreview.width()
            + self.__margin
            + (
                self.textboxUrl.x()
                + self.textboxUrl.width()
                - (
                    self.labelPreview.x()
                    + self.labelPreview.width()
                    + self.__margin
                    + self.btnDownload.width()
                )
            )
            / 2
        )
        x = self.labelPreview.x() + self.labelPreview.width() + self.__margin
        y = int(
            self.labelResolutionTitle.y()
            + self.labelResolutionTitle.height()
            + (
                self.labelPreview.y()
                + self.labelPreview.height()
                + self.__margin
                - (
                    self.labelResolutionTitle.y()
                    + self.labelResolutionTitle.height()
                    + self.btnDownload.height()
                )
            )
            / 2
        )
        y = (
            self.labelPreview.y()
            + self.labelPreview.height()
            - self.btnDownload.height()
        )
        self.btnDownload.move(x, y)

        self.btnStop.move(
            self.textboxUrl.x() + self.textboxUrl.width() - self.btnStop.width(),
            self.btnDownload.y(),
        )
        self.adjustWidgetSize()

        self.labelDownloadInfo.move(
            self.labelResolutionTitle.x(),
            self.labelResolutionTitle.y()
            + self.labelResolutionTitle.height()
            + self.__margin,
        )

    def setPic(self, pixmap: PyQt6.QtGui.QPixmap):
        if pixmap.isNull() == False:
            keepAspectRatio = PyQt6.QtCore.Qt.AspectRatioMode.KeepAspectRatio
            smoothTransform = PyQt6.QtCore.Qt.TransformationMode.SmoothTransformation
            pixmap = pixmap.scaled(
                self.labelPreview.size(), keepAspectRatio, smoothTransform
            )
        self.labelPreview.setPixmap(pixmap)
        self.repaint()

    def setGif(self, path: str):
        self.movie = PyQt6.QtGui.QMovie(path, PyQt6.QtCore.QByteArray(), self)
        self.movie.setScaledSize(self.labelPreview.size())
        self.labelPreview.setMovie(self.movie)
        self.movie.start()

    # def startSpriteTicker(self, spriteImg: PyQt6.QtGui.QPixmap, runningTime: int):
    #     self.stopThreads(self.__runningSprites)
    #     self.spriteThread = self.SpriteThread(self, spriteImg, 0.5, runningTime)
    #     self.spriteThread.updatePixmap.connect(self.setPic)
    #     self.__runningSprites.append(self.spriteThread)
    #     self.spriteThread.start(PyQt6.QtCore.QThread.Priority.TimeCriticalPriority)

    def setSpriteImage(self, spriteUrl: list, runningTime: int):
        self.stopThreads(self.__runningSprites)

        spriteImg = []
        # for url in spriteUrl:
        #     spriteImg.append(pic.pixmapFromNetwork(url))

        if spriteUrl != []:
            self.spriteThread = self.SpriteThread(self, spriteUrl, 0.5, runningTime)
            self.spriteThread.updatePixmap.connect(self.setPic)
            self.__runningSprites.append(self.spriteThread)
            self.spriteThread.start(PyQt6.QtCore.QThread.Priority.TimeCriticalPriority)

    def setLoadingImage(self):
        loadingGifPath = findResourceFile("loading.gif")
        self.setGif(loadingGifPath)
        self.repaint()

    def clearImage(self):
        self.labelPreview.setText("미리보기")

    def clearData(self):
        self.__weverseMPD = None
        self.__resolution = None

    def clearForm(self):
        self.clearData()
        self.clearImage()
        self.labelTitleText.clear()
        self.labelRunningtimeText.clear()
        self.comboResolution.clear()
        self.comboResolution.setHidden(True)
        self.labelRunningtimeText.setHidden(True)
        self.labelDownloadInfo.clear()

    def setTitleText(self, title: str):
        print("title :", title)
        self.labelTitleText.setText(title)

    def formatTime(self, time: float):
        hour = int(time // 3600)
        minute = int((time // 60) % 60)
        sec = int(time % 60)
        timestr = str(hour) + ":" + str(minute) + ":" + str(sec)
        timestr = "{:01d}:{:02d}:{:02d}".format(hour, minute, sec)
        return timestr

    def setRunningTimeText(self, time: str):
        if self.labelRunningtimeText.text() != time:
            print("running time :", time)
        self.labelRunningtimeText.setText(time)

    def setComboResolution(self, resolutionList: list):
        self.comboResolution.clear()
        self.comboResolution.addItems(resolutionList)
        self.comboResolution.setHidden(False)
        self.labelRunningtimeText.setHidden(False)
        self.btnDownload.setHidden(False)

    def onDownloadPageCompleted(self, weverseNetwork: weverse.Network):
        weverseNetwork.checkMpd()
        self.__weverseMPD = weverse.MPD(weverseNetwork.getMPD())

        if weverseNetwork.isOnLive():
            # self.__thumbnailUrl = weverseNetwork.getThumbnailUrl()
            # self.setPic(pic.pixmapFromNetwork(self.__thumbnailUrl))

            self.labelOnLive.setHidden(False)
        else:
            self.setSpriteImage(
                self.__weverseMPD.getSpriteUrl(), self.__weverseMPD.getRunningTime()
            )

            self.labelOnLive.setHidden(True)
        self.setTitleText(weverseNetwork.getPageTitle())
        self.setRunningTimeText(self.formatTime(self.__weverseMPD.getRunningTime()))
        self.setComboResolution(self.__weverseMPD.getAvailableResolutions())

        self.adjustWidgetPosition()

    def onDownloadPageError(self, error: Exception):
        print(error)
        self.clearForm()

    def startDownloadPage(self, url):
        downloadThread = self.DownloadPageThread(self, url)
        downloadThread.started.connect(self.setLoadingImage)
        downloadThread.complete.connect(self.onDownloadPageCompleted)
        downloadThread.error.connect(self.onDownloadPageError)
        self.__runningDownloads.append(downloadThread)
        downloadThread.start(PyQt6.QtCore.QThread.Priority.TimeCriticalPriority)

    def stopThreads(self, threads: list):
        runningCnt = 0
        for thread in threads:
            if thread.isRunning():
                runningCnt += 1
                thread.stop()
                thread.quit()

    def textdir1Changed(self):
        strippedUrl = self.textboxUrl.text().strip()
        if strippedUrl != self.textboxUrl.text():
            self.textboxUrl.setText(strippedUrl)
            return
        self.stopThreads(self.__runningDownloads)
        self.stopThreads(self.__runningSprites)
        self.clearForm()

        print('input url : "' + self.textboxUrl.text() + '"')

        if strippedUrl.startswith("https://weverse.io"):
            self.startDownloadPage(strippedUrl)

    def onComboResolutionChanged(self):
        if self.comboResolution.currentIndex() != -1:
            resolution = self.comboResolution.currentText()
            print("selected resolution :", resolution)
            self.__resolution = resolution

    def openSaveFileNameDialog(self, initialFilename: str = None):
        dialogDir = initialFilename
        print(self.__lastSaveDir)
        if self.__lastSaveDir != "":
            dialogDir = self.__lastSaveDir + os.sep + initialFilename

        dir = PyQt6.QtWidgets.QFileDialog.getSaveFileName(directory=dialogDir)
        if os.path.dirname(dir[0]) != "":
            self.__lastSaveDir = os.path.dirname(dir[0])

        return dir

    def onDownloadVideoInfo(self, infoData: list):
        if infoData["newRunningTime"] != None:
            self.setRunningTimeText(self.formatTime(infoData["newRunningTime"]))

        sizecheckMessage = ""
        if infoData["calulatingFilesize"] == True:
            sizecheckMessage = "내려받을 크기 확인 중\n"
            if self.__thumbnailUrl != "":
                self.setPic(pic.pixmapFromNetwork(self.__thumbnailUrl))

        timeMessage = ""
        if infoData["spentTime"] != None:
            timeMessage = "{0} / {1}\n".format(
                str(infoData["spentTime"]), str(infoData["estimatedTime"])
            )

        sizeMessage = ""
        if infoData["downloadedFilesize"] != None:
            if infoData["totalFilesize"] <= (1 << 20) * 10:  # <= 10MB
                unit = "KB"
                downloadedFilesizeUnit = infoData["downloadedFilesize"] >> 10
                totalFilesizeUnit = infoData["totalFilesize"] >> 10
            else:
                unit = "MB"
                downloadedFilesizeUnit = infoData["downloadedFilesize"] >> 20
                totalFilesizeUnit = infoData["totalFilesize"] >> 20

            sizeMessage = "{0} / {1} {2}\n".format(
                downloadedFilesizeUnit, totalFilesizeUnit, unit
            )

        speedMessage = ""
        if infoData["downloadSpeed"] != None:
            speedMessage = "{:0.1f} MB/s\n".format(infoData["downloadSpeed"])

        percentMessage = ""
        if infoData["downloadedPercantage"] != None:
            percentMessage = "{:0.2f} %\n".format(infoData["downloadedPercantage"])

        sleepMessage = ""
        if infoData["sleep"] != None and infoData["sleep"]:
            sleepMessage = "{0}초 후 이어지는 영상 확인\n".format(
                int(infoData["sleepTime"])
            )

        self.labelDownloadInfo.setText(
            timeMessage
            + sizeMessage
            + speedMessage
            + percentMessage
            + sizecheckMessage
            + sleepMessage
        )

    def onDownloadVideoError(self, error: Exception):
        print("video download error")
        print(error)

    def onDownloadVideoStart(self):
        print("video download start")
        self.textboxUrl.setEnabled(False)
        self.comboResolution.setEnabled(False)
        self.btnDownload.setEnabled(False)
        self.btnStop.setEnabled(True)

    def onDownloadVideoComplete(self, isCompleted: bool):
        print("\nvideo download completed")

        message = self.labelDownloadInfo.text()
        if isCompleted == False:
            print("User stopped")
            message = message + "취소"
        else:
            message = message + "완료"
        self.labelDownloadInfo.setText(message)

        self.textboxUrl.setEnabled(True)
        self.comboResolution.setEnabled(True)
        self.btnDownload.setEnabled(True)
        self.btnStop.setEnabled(False)

    def onBtnStopClicked(self):
        self.btnStop.setEnabled(False)
        print("stop clicked")
        if self.__downloadVideoThread != None:
            self.__downloadVideoThread.setKeepDownloadFlag(False)

    def onBtnDownloadClicked(self):
        if self.__resolution == None or self.__weverseMPD == None:
            print("No video")
            return
        print(self.__resolution)

        initialFilename = self.labelTitleText.text() + ".ts"
        savePath = self.openSaveFileNameDialog(initialFilename)

        if savePath[0] == "":
            print("download cancelled")
            return

        print("download thread initialize")
        tsM3u8Url = self.__weverseMPD.getTsM3u8Url(self.__resolution)
        duration = self.__weverseMPD.getDuration()
        downloadVideoThread = self.DownloadVideoThread(
            self, savePath[0], tsM3u8Url, duration
        )
        self.__downloadVideoThread = downloadVideoThread
        downloadVideoThread.info.connect(self.onDownloadVideoInfo)
        downloadVideoThread.error.connect(self.onDownloadVideoError)
        downloadVideoThread.started.connect(self.onDownloadVideoStart)
        downloadVideoThread.complete.connect(self.onDownloadVideoComplete)
        print("download thread start")
        downloadVideoThread.start(PyQt6.QtCore.QThread.Priority.TimeCriticalPriority)


def main():
    multiprocessing.freeze_support()
    app = PyQt6.QtWidgets.QApplication(sys.argv)
    window = Window()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
