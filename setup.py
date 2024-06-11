from cx_Freeze import setup, Executable

buildOptions = {
    "packages": [
        "playwright",
        "requests",
        "os",
        "aiohttp",
        "asyncio",
        "multiprocessing",
        "PyQt6",
        "sys",
        "time",
        "datetime",
    ],
    "excludes": [],
    "include_files": ["icon.ico", "loading.gif"],
    "build_exe": "build/amd64",
}

exe = [Executable("weversedl-gui.py", base="Win32GUI", icon="icon.ico")]

setup(
    name="weversedl-gui",
    version="1.0",
    author="idingg",
    options=dict(build_exe=buildOptions),
    executables=exe,
)
