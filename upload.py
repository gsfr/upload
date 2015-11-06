#!/usr/bin/env python
#
# @author:  Gunnar Schaefer

from __future__ import print_function

import os
import cgi
import json
import psutil
import hashlib
import webapp2
import argparse
import resource
import paste.httpserver

import logging
logging.basicConfig(
    format='%(asctime)s %(name)8.8s:%(levelname)4.4s %(message)s',
    datafmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('upload')

import tempdir as tempfile


def hrsize(size):
    if size < 1000:
        return '%d%s' % (size, 'B')
    for suffix in 'KMGTPEZY':
        size /= 1024.
        if size < 10.:
            return '%.1f%sB' % (size, suffix)
        if size < 1000.:
            return '%.0f%sB' % (size, suffix)
    return '%.0f%sB' % (size, 'Y')


class HashingFile(file):
    def __init__(self, file_path):
        super(HashingFile, self).__init__(file_path, "w+b")
        self.sha1 = hashlib.sha1()

    def write(self, data):
        self.sha1.update(data)
        return file.write(self, data)

    def get_hash(self):
        return self.sha1.hexdigest()


def getHashingFieldStorage(upload_dir):
    class HashingFieldStorage(cgi.FieldStorage):
        def make_file(self, binary=None):
            self.open_file = HashingFile(os.path.join(upload_dir, self.filename))
            return self.open_file

        def get_hash(self):
            return self.open_file.get_hash()

    return HashingFieldStorage


class Upload(webapp2.RequestHandler):

    def get(self):
        self.response.write('Simple uploader\n')

    def post(self):
        return self.put()

    def put(self):
        before = resource.getrusage(resource.RUSAGE_SELF)
        before_io = psutil.disk_io_counters()

        upload_source = '%s (%s)' % (self.request.user_agent, self.request.client_addr)
        log.debug('incoming upload from ' + upload_source)
        log.debug('type: ' + self.request.content_type)

        if (self.request.content_type == 'multipart/form-data'):
            fs_environ = self.request.environ.copy()
            fs_environ.setdefault('CONTENT_LENGTH', '0')
            fs_environ['QUERY_STRING'] = ''

            # Any incoming file(s) are hashed and written to disk on construction of the HashingFieldStorage class
            form = getHashingFieldStorage(self.app.path)(fp=self.request.body_file, environ=fs_environ, keep_blank_values=True)

            received_file = form['file']
            received_sha = received_file.get_hash()
            received_filename = received_file.filename
            received_size = os.path.getsize(os.path.join(self.app.path, received_filename))

        else:
            received_filename = 'upload.dat'
            received_file = HashingFile(os.path.join(self.app.path, received_filename))
            for chunk in iter(lambda: self.request.body_file.read(2**20), ''):
                received_file.write(chunk)
            received_sha = received_file.get_hash()
            received_size = os.path.getsize(os.path.join(self.app.path, received_filename))

        log.debug('received %s [%s] from %s' % (received_filename, hrsize(received_size), upload_source))
        log.debug('sha1: ' + received_sha)
        os.rename(
            os.path.join(self.app.path, received_filename),
            os.path.join(self.app.path, received_sha + '_' + received_filename))

        after = resource.getrusage(resource.RUSAGE_SELF)
        after_io = psutil.disk_io_counters()
        print('Memory Used (High-water mark): %s' % (hrsize(after.ru_maxrss)))
        print('CPU Time: %d seconds' % ((after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)))
        print('Disk I/O: %s bytes written, %s bytes read' % (hrsize(after_io.write_bytes - before_io.write_bytes), hrsize(after_io.read_bytes - before_io.read_bytes)))


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--path', default='.', help='path to storage area')
arg_parser.add_argument('--host', default='127.0.0.1', help='IP address to bind to')
arg_parser.add_argument('--port', default='8080', help='TCP port to listen on')
arg_parser.add_argument('--ssl', action='store_true', help='enable SSL')
arg_parser.add_argument('--ssl_cert', default='*', help='path to SSL key and cert file')
arg_parser.add_argument('--log_level', help='log level [debug]', default='debug')
args = arg_parser.parse_args()

args.ssl = args.ssl or args.ssl_cert != '*'

logging.getLogger('paste.httpserver').setLevel(logging.WARNING) # silence paste logging
log.setLevel(getattr(logging, args.log_level.upper()))

app = webapp2.WSGIApplication([
    webapp2.Route(r'/upload', Upload),
    webapp2.Route(r'/upload/<filename>', Upload),
])
app.path = args.path
paste.httpserver.serve(app, host=args.host, port=args.port, ssl_pem=args.ssl_cert if args.ssl else None)
