
"""
- default: takes single argument, a 4chan url, and download all the images to a directory, also backs up the html. Default action for subsequent downloads is to skip downloading files we already have, but not check their size

- checks for existence of dir, takes optional dir argument

- should check local directory and separate urls of files we don't have. Then can report, "getting 11 new files."

- optional argument forces 'Content-Length' checks against byte-size of each file to make sure
 all of them are complete

X start by working up a printf progress bar like apt-get

- takes an argument list of URLS
"""

import json
from os.path import isdir, isfile, join, dirname, os
import requests
import sys
import time


p = lambda s: print(s)
perr = lambda s: print(s, file=sys.stderr)


def download_file( url, filename ):
    X = requests.get( url )
    with open( filename, 'wb' ) as f:
        f.write(X.content)
    return isfile( filename )


def progress_download( url, filename ):
    def print_progress_bar( fraction ):
        """ fraction is in range 0.0 to 1.0 """
        barlen = 36
        filename_truncated = 44
        frac = int(fraction * barlen)
        flen = filename_truncated if len(filename) > filename_truncated else len(filename)
        print('\r' * (barlen + 2 + flen + 1), end='')
        print(filename[:filename_truncated] + " ["+frac*'='+(barlen-frac)*' '+"]", end='')

    try:
        fd = open( filename, 'wb' )
    except:
        perr(f"couldn't open {filename} for writing")

    req = requests.get( url, stream=True )
    file_expected_length = 0
    if req.headers.get('Content-Length', None):
        file_expected_length = int(req.headers['Content-Length'])

    get_sz = 0
    for blob in req.iter_content(chunk_size=2**13):
        if blob:
            get_sz += len(blob)
        #NOTE Blob is bytes, eg: b''
        fd.write(blob)
        #refresh/print progress bar spinner
        if file_expected_length:
            print_progress_bar(get_sz / file_expected_length)
        else:
            print_progress_bar(0.0)

    if not file_expected_length:
        print_progress_bar(1.0)
    print() # newline

    fd.close()
    return isfile( filename )


def check_file_download( url, filename, dl_func=download_file, chkLen=False ):
    """ check the byte length of every file;
        download it if it doesn't exist,
        OR if the byte lengths don't match .

        Change chkLen to False to only check for existence of a file,
        and disable checking length.

        returns False for not exist or incorrect filelength
    """

    if not os.path.isfile( filename ):
        p( 'getting "{}"'.format(url) )
        dl_func( url, filename )
        return False  # didn't exist
    else:
        print('!EXISTS "{}"'.format(filename))

        if not chkLen:
            return True # did exist

        print('!EXISTS "{}"  **Checking Length** '.format(filename), end='')
        # get headers and compare against byte size of file
        H = requests.head( url )
        if H.headers.get('Content-Length', None):
            if H.headers['Content-Length'] != str(os.stat(filename).st_size):
                a = str(H.headers['Content-Length'])
                b = str(os.stat(filename).st_size)
                print( f'Size doesnt match [{a} != {b}]. Re-getting' )
                dl_func(url, filename)
                return False # didn't checklen correctly
            else:
                print(' ok')
                return True # correct length


def str_indexes( needle, haystack ):
    """ returns list of all indexes of needle found in haystack """
    nlen = len(needle)
    res = []
    index = 0

    while True:
        try:
            i = haystack.index( needle, index )
        except:
            break
        res.append(i)
        index = i + nlen
    return res


def download_rss_xml(url):
    result = requests.get(url)
    feed = result.content.decode('utf-8')
    name = url[url.rindex('/')+1:]
    return feed, name


def rss_xml_from_file(name):
    out = None
    with open(name, "r") as f:
        out = f.read()
    return out, name


def convert_iso_date(iso):
    mons = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    my = iso.split(' ')[2:4]
    i = mons.index(my[0]) + 1
    a = str(i)
    while len(a) < 2:
        a = '0' + a
    return '{}-{}'.format(my[1], a)


def numpad(n, leading_zeros=3):
    s = str(n)
    while len(s) < leading_zeros:
        s = '0' + s
    return s


def get_quoted_strings( sentinel, haystack, payload ):
    count = 0
    indexes = str_indexes( sentinel, haystack )
    for index, start in enumerate(indexes):
        start += len(sentinel)
        end = haystack.index('"', start)
        assert(haystack[end] == '"')
        tstring = haystack[start:end].rstrip().lstrip()
        payload.append(tstring)
        count = count + 1
    return count


def fetch_url( url, saveto ):
    retval = progress_download(url, saveto)
    return retval


def usage(sextra=None):
        perr('usage: {} [options] <URL>'.format(sys.argv[0]))
        perr('    options:')
        perr('    --full    will cause 4chget to recheck the length of each image file')
        if sextra:
            perr(sextra)


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(0)

    if '--help' in sys.argv:
        usage()
        sys.exit(0)

    Args = sys.argv.copy()
    full_download = False


    #TODO FULL DOWNLOAD - check the length of each file
    if '--full' in Args:
        Args = Args[:Args.index('--full')] + Args[Args.index('--full')+1:]
        full_download = True
        perr('**doing a full download, checking the length of each file')
        time.sleep(1.5)

    url = Args[1]

    # created directory
    dirname = url[url.rindex('/')+1:]
    feed_file = os.path.join(dirname, 'index.html')

    if not isdir(dirname):
        perr('creating directory {}'.format(dirname))
        os.mkdir(dirname, mode=(7*8**2 + 5*8**1 + 5*8**0)) #755
    else:
        perr('directory {} exists'.format(dirname))

    # fetch and save html
    perr('saving "{}"'.format(feed_file))
    ret = fetch_url(url, feed_file)
    if not ret:
        perr('failed to download "{}"'.format(url))
        sys.exit(1)
    else:
        with open(feed_file, "r") as f:
            html_string = f.read()

    # collect target image paths
    IMAGE_URLS = []
    sentinels = [ 'i.4cdn.org', 'is2.4chan.org' ]
    for sentinel in sentinels:
        sentinel_matches = []
        get_quoted_strings(sentinel, html_string, sentinel_matches)
        IMAGE_URLS.extend( [f'https://{sentinel}{sent}' for sent in sentinel_matches] )
    # clean out duplicates
    IMAGE_URLS = list(set(IMAGE_URLS))
    # clean out thumbs
    IMAGE_URLS_FILTERED = [x for x in IMAGE_URLS if x[x.rindex('.')-1] != 's']

    img_downloaded = 0

    for index, imgurl in enumerate(IMAGE_URLS_FILTERED):
        print( f"{index+1}/{len(IMAGE_URLS_FILTERED)} ", end='' )
        basename = imgurl[imgurl.rindex('/')+1:]
        if not check_file_download( imgurl, os.path.join(dirname, basename), dl_func=progress_download, chkLen=full_download ):
            img_downloaded = img_downloaded + 1
            time.sleep( 1 ) # sleeping after getting files, not for confirming them

    if img_downloaded:
        perr(f'got {img_downloaded} new files')
    else:
        perr('no new files')


if __name__ == '__main__':
    main()
