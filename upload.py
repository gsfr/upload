#!/usr/bin/env python
#
# @author:  Gunnar Schaefer

from __future__ import print_function

import os
import cgi
import json
import hashlib
import webapp2
import argparse
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

class Upload(webapp2.RequestHandler):

    def get(self):
        self.response.write('Simple uploader\n')

    def post(self, filename='upload.dat'):
        return self.put(filename)

    def put(self, filename='upload.dat'):
        upload_source = '%s (%s)' % (self.request.user_agent, self.request.client_addr)
        log.debug('incoming upload from ' + upload_source)
        if self.request.content_type == 'multipart/form-data':
            filestream = None
            # use cgi lib to parse multipart data without loading all into memory; use tempfile instead
            # FIXME avoid using tempfile; processs incoming stream on the fly
            fs_environ = self.request.environ.copy()
            fs_environ.setdefault('CONTENT_LENGTH', '0')
            fs_environ['QUERY_STRING'] = ''
            form = cgi.FieldStorage(fp=self.request.body_file, environ=fs_environ, keep_blank_values=True)
            for fieldname in form:
                field = form[fieldname]
                if fieldname == 'file':
                    filestream = field.file
                    filename = field.filename
                elif fieldname == 'metadata':
                    try:
                        metadata = json.loads(field.value)
                        log.info('metadata: %s' % str(metadata))
                    except ValueError:
                        self.abort(400, 'non-JSON value in "metadata" parameter')
            if filestream is None:
                self.abort(400, 'multipart/form-data must contain a "file" field')
        else:
            filestream = self.request.body_file
        filename = os.path.basename(filename)
        with tempfile.TemporaryDirectory(prefix='.tmp', dir=self.app.path) as tempdir_path:
            upload_filepath = os.path.join(tempdir_path, filename)
            with open(upload_filepath, 'wb') as upload_file:
                filesize = 0
                sha1 = hashlib.sha1()
                log.debug('hashing data and streaming to disk...')
                for chunk in iter(lambda: filestream.read(2**20), ''):
                    sha1.update(chunk)
                    filesize += len(chunk)
                    upload_file.write(chunk)
            log.info('received %s [%s] from %s' % (filename, hrsize(filesize), upload_source))
            log.debug('sha1: ' + sha1.hexdigest())
            os.rename(upload_filepath, os.path.join(self.app.path, sha1.hexdigest() + '_' + filename))
        print()


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
