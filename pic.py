# import PyQt6

import PyQt6.QtGui
import PyQt6.QtCore
import PyQt6.QtNetwork
import time

from weverse import Network


def getCroppedPic(pic: PyQt6.QtGui.QPixmap, n: int):
    if n > 99:
        return None

    croppedWidth = int(pic.size().width() / 10)
    croppedHeight = int(pic.size().height() / 10)
    posx = (n % 10) * croppedWidth
    posy = (n // 10) * croppedHeight

    croppedPic = pic.copy(posx, posy, croppedWidth, croppedHeight)

    return croppedPic


def getAllCroppedPic(pic: PyQt6.QtGui.QPixmap):
    return [getCroppedPic(pic, n) for n in range(100)]


def pixmapFromFile(path: str):
    pixmap = PyQt6.QtGui.QPixmap()
    pixmap.load(path)
    return pixmap


def pixmapFromNetwork(url: str):
    spriteRaw = Network.downloadBytes(url)
    spriteImg = PyQt6.QtGui.QPixmap()
    spriteImg.loadFromData(spriteRaw)
    return spriteImg
