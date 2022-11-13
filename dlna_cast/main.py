import os
from os.path import join, expanduser
import subprocess as sp
import http.server
import threading
from time import sleep

from fire import Fire
from dotenv import load_dotenv
import atexit

from .ssdp import discover

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
    def dlna_cast_dir(self):
        return os.getenv('DLNA_CAST_DIR', join(USER_HOME, 'dlna-cast'))

    def _get_devices(self):
        devices = discover()
        return [d for d in devices if d.find_action('SetAVTransportURI')]

    def _find_device(self, name):
        for d in self._get_devices():
            if d.friendly_name == name:
                return d

    def _start_http_server(self):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(_, *args, **kwargs):
                super().__init__(*args, directory=self.dlna_cast_dir, **kwargs)

        with http.server.ThreadingHTTPServer(("", 0), Handler) as httpd:
            self._httpd = httpd
            self._listen_port = httpd.server_address[1]
            print("HTTP: start to serving at port", self._listen_port)
            httpd.serve_forever()

    def _start_ffmpeg_streaming(self, audio_input, framerate):
        audio_option = 'audio="{audio_input}"'.format(audio_input=audio_input)
        cmd = [
            self.ffmpeg_bin, '-hide_banner',
            '-f', 'gdigrab', '-i', 'desktop', '-framerate', str(
                framerate), '-c:v', 'h264',
            '-f', 'dshow', '-i', audio_option,
            '-f', 'hls', '-hls_list_size', '5', '-hls_flags', 'delete_segments',
            join(self.dlna_cast_dir, 'index.m3u8'),
        ]
        cmd = ' '.join(cmd)
        print('run command: ', cmd)
        self._ffmpeg_process = sp.Popen(cmd)
        atexit.register(lambda: self._ffmpeg_process.kill())

    def __init__(self):
        self._listen_port = None
        self._httpd = None
        self._ffmpeg_process = None

    def screen_cast(self, audio_input=None, dlna_device=None, framerate=30):
        os.makedirs(self.dlna_cast_dir, exist_ok=True)
        thread = threading.Thread(target=self._start_http_server, daemon=True)
        thread.start()

        while self._listen_port is None:
            sleep(1)  # TODO: use thread.Event instead

        audio_input = audio_input or os.getenv('AUDIO_INPUT')
        assert audio_input, 'audio_input must be set!'

        self._start_ffmpeg_streaming(audio_input, framerate)

        dlna_device = dlna_device or os.getenv('DLNA_DEVICE')
        assert dlna_device, 'dlna_device must be set!'
        device = self._find_device(dlna_device)
        assert device, 'cannot find deivce named {}'.format(dlna_device)

        device.AVTransport.SetAVTransportURI(
            InstanceID=0,
            CurrentURI='http://{}:{}/index.m3u8'.format(
                device.iface_ip, self._listen_port),
            CurrentURIMetaData=''
        )
        self._ffmpeg_process.wait()

    def list_ffmpeg_devices(self, device='dshow'):
        cmd = [self.ffmpeg_bin, '-hide_banner',
               '-list_devices', 'true', '-f', device, '-i', 'dummy']
        sp.call(cmd)

    def list_dlna_devices(self):
        devices = self._get_devices()
        for d in devices:
            print(d.friendly_name)


if __name__ == '__main__':
    Fire(WinCast)
