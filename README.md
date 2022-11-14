# dlna-cast
A cross-platform command-line tool that casts screen and media file to remote DLNA device.

## Introduction
`dlna-cast` uses `ffmpeg` to capture screen and audio, then convert them into HLS streams which could be served by a simple HTTP server. The HLS url will be send to the selected device via uPnP protocol and then you can watch you screen on the remote device (smart TV, typically).

This tool is supposed to be cross-platform but currently I don't have a Linux or MacOS device at hand so it can only run on Windows now. It won't be hard to support other platforms though, as there are no platform specific dependencies.

HLS is chosen just because it is easy to implement. But the problem of HLS is its high latency (up to 5-10s or more) so it's definitely not for scenarios that require low latency (presentation for example). But as a trade-off the streaming quality exceeds a lot of software screen-casting solutions (Lebocast for example) that have been tested by myself, which make it pretty good to stream music or video playing from your PC to TV.

## Install
```bash
pip install dlna-cast
```
Please ensure your Python is 3.7 or above.

### Install ffmpeg
You can install `ffmpeg` by compiling from source code, or just download the prebuild binary from https://ffmpeg.org/download.html

You need to ensure the `ffmpeg` command can be found in the `PATH` environment variable, or else you need to set `FFMPEG_BIN` or `FFMPEG_HOME` to let `dlna-cast` know where to find the command. 

`dlna-cast` supports reading the environment variable from `.env` file.  You can create a `.env` file under the folder you are gonna run the `dlna-cast` command with the following content.

```bash
FFMPEG_BIN=D:\ffmpeg\ffmpeg.exe
# or
FFMPEG_HOME=D:\ffmpeg
```

You can also use the `set_env` command to update the '.env' file.

```bash
dlna-cast set_env FFMPEG_HOME "D:\ffmpeg"
```

### Install Screen Capturer Recorder for Windows
Though `ffmpeg` is shipped with `gdigrab` to capture screens on Windows, its performance is terrible when frame rate is high. `dlna-cast` uses ScreenCapturerRecorder for the sake of performance. You need to [download](https://github.com/rdp/screen-capture-recorder-to-video-windows-free/releases) and install it before starting to use this tool.

## Get Started
Before you start to stream your screen to remote devices that support DLNA protocol, you need to discover available devices in your LAN by running the following command.

```bash
dlna-cast list_dlna_devices
# You will see the output if supported devices are found
HuaweiPro
Lebocast
```  

And now you can cast your screen to one of the found devices by running the following command.
```bash
dlna-cast screen --dlna_device HuaweiPro
``` 

Or you can also set `DLNA_DEVICE` in the '.env' file so that you can skip to set `--dlna_device` next time.

```bash
dlna-cast set_env DLNA_DEVICE HuaweiPro
dlna-cast screen
```

You can stop casting by using `Ctrl+C` to stop the command. 
