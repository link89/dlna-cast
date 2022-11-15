import sys
import os
from os.path import join, expanduser, exists
import subprocess as sp
import shutil
import http.server
import threading
from time import sleep

from fire import Fire
from dotenv import load_dotenv

import atexit

from .ssdp import discover

load_dotenv(join(os.getcwd(), '.env'))
USER_HOME = expanduser("~")


def get_env_or_opt(opt, env_name):
    return opt or os.getenv(env_name)


class BaseCast:

    @property
    def ffmpeg_name(self):
        raise NotImplemented()

    @property
    def default_ffmpeg_input_opts(self):
        raise NotImplemented()

    @property
    def ffmpeg_home(self):
        return os.getenv('FFMPEG_HOME')

    @property
    def ffmpeg_bin(self):
        default_bin = self.ffmpeg_name if self.ffmpeg_home is None else join(
            self.ffmpeg_home, self.ffmpeg_name)
        return os.getenv('FFMPEG_BIN', default_bin)

    @property
    def dlna_cast_dir(self):
        return os.getenv('DLNA_CAST_DIR', join(USER_HOME, 'dlna-cast'))

    def _get_devices(self):
        devices = discover(timeout=3)
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

    def _start_ffmpeg_streaming(self, framerate=30, input_opts='', segment_size=1, crf=21):
        input_opts = input_opts or self.default_ffmpeg_input_opts
        enc_opts = (
            '-c:v libx264 -preset fast -tune zerolatency -crf {crf} -vf format=yuv420p '
            '-keyint_min:v 1 -force_key_frames:v "expr:gte(t,n_forced*{segment_size})" '
            '-f hls -hls_time {segment_size} -hls_list_size 10 -hls_flags delete_segments'
        ).format(segment_size=segment_size, crf=crf)

        cmd = [
            self.ffmpeg_bin, '-framerate', str(framerate),
            input_opts, enc_opts,
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

    def screen(self, dlna_device=None, framerate=30, input_opts=None, segment_size=2, crf=21):
        # clean up
        shutil.rmtree(self.dlna_cast_dir, ignore_errors=True)
        os.makedirs(self.dlna_cast_dir, exist_ok=True)

        # discover dlan_device
        dlna_device = get_env_or_opt(dlna_device, 'DLNA_DEVICE')
        assert dlna_device, 'dlna_device must be set!'
        device = self._find_device(dlna_device)
        assert device, 'cannot find deivce named {}'.format(dlna_device)

        # start http server for hls
        thread = threading.Thread(target=self._start_http_server, daemon=True)
        thread.start()

        while self._listen_port is None:
            sleep(0.1)  

        # start ffmpeg streaming
        input_opts = get_env_or_opt(input_opts, 'FFMPEG_INPUT_OPTS')
        self._start_ffmpeg_streaming(framerate, input_opts, segment_size, crf)
        while not exists(join(self.dlna_cast_dir, 'index.m3u8')):
            sleep(0.1)

        # play video
        hls_url = 'http://{}:{}/index.m3u8'.format(
            device.iface_ip, self._listen_port)
        print('start to play {} on {}'.format(hls_url, device.friendly_name))
        device.AVTransport.SetAVTransportURI(
            InstanceID=0,
            CurrentURI=hls_url,
            CurrentURIMetaData=''
        )

        def stop_play_on_exit():
            device.AVTransport.Stop(
                InstanceID=0,
            )
            print('stop remote video')

        atexit.register(stop_play_on_exit)

        # wait for subprocess
        self._ffmpeg_process.wait()

    def list_dshow_devices(self):
        cmd = [self.ffmpeg_bin, '-hide_banner',
               '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy']
        sp.call(cmd)

    def list_dlna_devices(self):
        devices = self._get_devices()
        for d in devices:
            print(d.friendly_name)

class WinCast(BaseCast):
    @property
    def ffmpeg_name(self):
        return 'ffmpeg.exe'

    @property
    def default_ffmpeg_input_opts(self):
        return '-f dshow -i video="screen-capture-recorder":audio="virtual-audio-capturer"'

class MacCast(BaseCast):
    @property
    def ffmpeg_name(self):
        return 'ffmpeg'

    @property
    def default_ffmpeg_input_opts(self):
        pass  # TODO

class LinuxCast(BaseCast):
    @property
    def ffmpeg_name(self):
        return 'ffmpeg'

    @property
    def default_ffmpeg_input_opts(self):
        return  #TODO

def main():
    if sys.platform == 'darwin':
        Fire(MacCast)
    elif sys.platform == 'win32':
        Fire(WinCast)
    else:
        Fire(LinuxCast)

if __name__ == '__main__':
    main()
