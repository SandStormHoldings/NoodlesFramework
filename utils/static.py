'''
filedesc: Controller for serving static content
'''
import os
from email.utils import formatdate

from noodles.http import BaseResponse, Error404
from noodles.utils.logger import log




# Mime types dictionary, contain pairs: key - file extansion,
# value - mime type
MIME_TYPES = {
    # Application types
    '.swf': 'application/x-shockwave-flash',

    # Text types
    '.gz': 'application/x-tar',
    '.js': 'text/javascript',
    '.css': 'text/css',
    '.html': 'text/html',
    '.txt': 'text/plain',
    '.xml': 'text/xml',
    # Image types
    '.jpg': 'image/jpeg',
    '.gif': 'image/gif',
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
    '.tiff': 'image/tiff',

    # Sound files

    '.wav': 'audio/x-wav',
    '.mp3': 'audio/mpeg',
    '.ogg': 'audio/ogg',

    # Fonts
    '.ttf': 'application/x-font-ttf',
    '.woff': 'application/x-woff',

    # And much more...
    # Add mime types from this
    # source http://en.wikipedia.org/wiki/Internet_media_type
    # Thank you Jimmy
}


def toInt(val):
    if val == '':
        return 0
    return int(val)


def index(request, path_info, path):
    partial_response = False
    path_info = path_info.replace('%28', '(')\
                         .replace('%29', ')')\
                         .replace('%20', ' ')
    response = BaseResponse()
    # define a file extansion
    base, ext = os.path.splitext(path_info)  # Get the file extansion
    mime_type = MIME_TYPES.get(ext, 'text/plain')
    if not mime_type:
        raise Exception("unknown doc, or something like that :-P: %s" % ext)
    static_file_path = os.path.join(path, path_info)
    # Check if this path exists
    if not os.path.exists(static_file_path):
        error_msg = "<h1>Error 404</h1> No such file STATIC_ROOT/%s"\
                    % path_info
        log.debug('not found: %s' % static_file_path)
        return Error404(error_msg)
    # configure response
    static_file = open(static_file_path, 'rb')  # Open file
    # Here we try to handle Range parameter

    content_offset = 0
    content_end = 0
    request_range = request.headers.get('Range')
    if request_range:
        range_bytes = request_range.replace('bytes=', '')
        range_bytes = range_bytes.split('-')
        if len(range_bytes) > 2:
            raise Exception('Wrong http Range parameter "%s"' % request_range)
        content_offset = toInt(range_bytes[0])
        content_end = toInt(range_bytes[1])
        partial_response = True

    static_content = static_file.read()
    if content_end <= 0 or content_end >= len(static_content):
        content_end = len(static_content) - 1
    response.body = static_content[content_offset: content_end + 1]

    response.charset = 'utf-8'
    response.headerlist = []
    response.headerlist.append(('Content-type', mime_type))

    if ext in ['.jpg', '.gif', '.png', '.tiff', '.mp3', '.ogg', '.ttf']:
        response.headerlist.append(('Access-Control-Allow-Origin', '*'))

    if partial_response:
        response.status = 206
        response.headerlist.append(
            ('Content-Range',
             'bytes %i-%i/%i' % (content_offset, content_end,
                                 len(static_content))))
    st = os.stat(static_file_path)
    response.headerlist.append(('Last-modified', formatdate(st.st_mtime)))
    response.headerlist.append(('Cache-control', 'max-age=626560472'))
    response.conditional_response = True
    response.md5_etag()
    return response
