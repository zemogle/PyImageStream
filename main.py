#!/usr/bin/env python3

import argparse
import os
import io
import time
from datetime import datetime

import tornado.ioloop
import tornado.web
import tornado.websocket

from PIL import Image

# import pygame.camera
# import pygame.image
import picamera

parser = argparse.ArgumentParser(description='Start the PyImageStream server.')

parser.add_argument('--port', default=8888, type=int, help='Web server port (default: 8888)')
parser.add_argument('--camera', default=0, type=int, help='Camera index, first camera is 0 (default: 0)')
parser.add_argument('--width', default=640, type=int, help='Width (default: 640)')
parser.add_argument('--height', default=480, type=int, help='Height (default: 480)')
parser.add_argument('--quality', default=70, type=int, help='JPEG Quality 1 (worst) to 100 (best) (default: 70)')
parser.add_argument('--hflip', default=False, action='store_true', help='Flip image in the horizontal direction')
parser.add_argument('--vflip', default=False, action='store_true', help='Flip image in the vertical direction')
parser.add_argument('--stopdelay', default=7, type=int, help='Delay in seconds before the camera will be stopped after '
                                                             'all clients have disconnected (default: 7)')
args = parser.parse_args()

class Camera:

    def __init__(self, index, width, height, quality, stopdelay, hflip, vflip):
        print("Initializing camera...")
        resolution = f"{width}x{height}"
        self._cam = picamera.PiCamera(resolution=resolution, framerate=10)
        print("Camera initialized")
        self.is_started = False
        self.stop_requested = False
        self.quality = quality
        self.stopdelay = stopdelay
        time.sleep(2)
        self._cam.iso = 800
        self._cam.awb_mode = 'auto'
        self._cam.exposure_mode = 'night'
        self._cam.vflip = vflip
        self._cam.hflip = hflip


    def request_start(self):
        if self.stop_requested:
            print("Camera continues to be in use")
            self.stop_requested = False
        if not self.is_started:
            self._start()

    def request_stop(self):
        if self.is_started and not self.stop_requested:
            self.stop_requested = True
            print("Stopping camera in " + str(self.stopdelay) + " seconds...")
            tornado.ioloop.IOLoop.current().call_later(self.stopdelay, self._stop)

    def _start(self):
        print("Starting camera...")
        #self._cam.start()
        print("Camera started")
        self.is_started = True

    def _stop(self):
        if self.stop_requested:
            print("Stopping camera now...")
            self._cam.close()
            print("Camera stopped")
            self.is_started = False
            self.stop_requested = False

    def get_jpeg_image_bytes(self):
        stream = io.BytesIO()
        for _ in self._cam.capture_continuous(stream, 'jpeg', use_video_port=True):
            # pimg.save(stream, "JPEG", quality=self.quality, optimize=True)
            stream.seek(0)
            #yield stream.getvalue()
            yield stream.read()

            # reset stream for next frame
            stream.seek(0)
            stream.truncate()


class ImageWebSocket(tornado.websocket.WebSocketHandler):
    clients = set()

    def check_origin(self, origin):
        # Allow access from every origin
        return True

    def open(self):
        ImageWebSocket.clients.add(self)
        print("WebSocket opened from: " + self.request.remote_ip)
        camera.request_start()

    def on_message(self, message):
        jpeg_bytes = next(camera.get_jpeg_image_bytes())
        self.write_message(jpeg_bytes, binary=True)

    def on_close(self):
        ImageWebSocket.clients.remove(self)
        print("WebSocket closed from: " + self.request.remote_ip)
        if len(ImageWebSocket.clients) == 0:
            camera.request_stop()

if __name__ == '__main__':
    camera = Camera(args.camera, args.width, args.height, args.quality, args.stopdelay, args.hflip, args.vflip)

    script_path = os.path.dirname(os.path.realpath(__file__))
    static_path = script_path + '/static/'

    app = tornado.web.Application([
            (r"/websocket", ImageWebSocket),
            (r"/(.*)", tornado.web.StaticFileHandler, {'path': static_path, 'default_filename': 'index.html'}),
        ])
    app.listen(args.port)

    print("Starting server: http://localhost:" + str(args.port) + "/")

    tornado.ioloop.IOLoop.current().start()
