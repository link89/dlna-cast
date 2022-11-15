import os
from os.path import join, expanduser
import subprocess as sp
import shutil
import http.server
import threading
from time import sleep

from fire import Fire
from dotenv import load_dotenv
import shlex

import atexit

from .ssdp import discover

load_dotenv(join(os.getcwd(), '.env'))
USER_HOME = expanduser("~")


def get_env_or_opt(opt, env_name):
    return opt or os.getenv(env_name)


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
        devices = discover(timeout=10)
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

    def _start_ffmpeg_streaming(self, framerate=30, input_opts='', enc_opts=''):
        input_opts = input_opts or '-f dshow -i video="screen-capture-recorder":audio="virtual-audio-capturer"'
        enc_opts = enc_opts or '-c:v libx264 -preset fast -tune zerolatency -crf 21 -vf format=yuv420p'
        cmd = [
            self.ffmpeg_bin, '-framerate', str(framerate),
            input_opts,
            enc_opts,
            '-f hls -hls_time 3 -hls_list_size 10 -hls_flags delete_segments',
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

    def screen(self, dlna_device=None, framerate=30, input_opts=None, enc_opts=None):
        # start ffmpeg streaming
        input_opts = get_env_or_opt(input_opts, 'FFMPEG_INPUT_OPTS')
        enc_opts = get_env_or_opt(input_opts, 'FFMPEG_ENC_OPTS')

        shutil.rmtree(self.dlna_cast_dir, ignore_errors=True)
        os.makedirs(self.dlna_cast_dir, exist_ok=True)
        self._start_ffmpeg_streaming(framerate, input_opts, enc_opts)

        # discover dlan_device
        dlna_device = get_env_or_opt(dlna_device, 'DLNA_DEVICE')
        assert dlna_device, 'dlna_device must be set!'
        device = self._find_device(dlna_device)
        assert device, 'cannot find deivce named {}'.format(dlna_device)

        # start http server for hls
        thread = threading.Thread(target=self._start_http_server, daemon=True)
        thread.start()

        while self._listen_port is None:
            sleep(1)  # TODO: use thread.Event instead

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

def main():
    Fire(WinCast)


if __name__ == '__main__':
    main()
