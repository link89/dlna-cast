import os
from os.path import join, expanduser
import subprocess as sp
import http.server
import _thread

from fire import Fire
from dotenv import load_dotenv
import upnpclient

load_dotenv()
USER_HOME = expanduser("~")


class WinCast:

    @property
    def ffmpeg_home(self):
        return os.getenv('FFMPEG_HOME')

    @property
    def ffmpeg_bin(self):
        default_bin = 'ffmpeg.exe' if self.ffmpeg_home is None else join(
            self.ffmpeg_home, 'ffmpeg.exe')
        return os.getenv('FFMPEG_BIN', default_bin)

    @property
    def dlan_cast_dir(self):
        return os.getenv('DLAN_CAST_DIR', join(USER_HOME, 'dlan-cast'))

    def _get_devices(self):
        devices = upnpclient.discover()
        return [d for d in devices if d.find_action('SetAVTransportURI')]

    def _start_http_server(self):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(_, *args, **kwargs):
                super().__init__(*args, directory=self.dlan_cast_dir, **kwargs)

        with http.server.ThreadingHTTPServer(("", 0), Handler) as httpd:
            self.listen_port = httpd.server_address[1]
            print("serving at port", self.listen_port)
            httpd.serve_forever()

    def _start_ffmpeg(self):
        cmd = [self.ffmpeg_bin, ]

    def __init__(self):
        self.listen_port = None

    def screen_cast(self, audio_device=None, dlan_device=None, framerate=30):
        os.makedirs(self.dlan_cast_dir, exist_ok=True)
        _thread.start_new_thread(self._start_http_server)

    def list_devices(self, device='dshow'):
        cmd = [self.ffmpeg_bin, '-list_devices',
               'true', '-f', device, '-i', 'dummy']
        sp.call(cmd)


if __name__ == '__main__':
    Fire(WinCast)
