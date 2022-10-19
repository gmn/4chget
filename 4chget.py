
import json
from os.path import isdir, isfile, join, dirname, os
import requests
import sys
import time

FEED_URL = "https://rss.samharris.org/feed/bcf60cfa-3ee2-406e-ae8e-f5f439a0a993"
FILES_DIR = './FILES'


p = lambda s: print(s)
perr = lambda s: print(s, file=sys.stderr)

def download_file( url, filename ):
    X = requests.get( url )
    with open( filename, 'wb' ) as f:
        f.write(X.content)
    if isfile( filename ):
        p('success: saved "{}"'.format(filename))
    else:
        p('{} download failed [{}]'.format(filename, url))


def progress_download( url, filename ):
    def print_progress_bar( fraction ):
        """ fraction is in range 0.0 to 1.0 """
        barlen = 44
        frac = int(fraction * barlen)

        ftruncate = 36
        flen = ftruncate if len(filename) > ftruncate else len(filename)
        print('\r' * (barlen + 2 + flen + 1), end='')
        print(filename[:ftruncate] + " ["+frac*'='+(barlen-frac)*' '+"]", end='')

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


def check_length_download( url, filename, dl_func=download_file ):
    """ check the byte length of every file;
        download it if it doesn't exist,
        OR if the byte lengths don't match """

    if not os.path.isfile( filename ):
        p( 'getting "{}"'.format(url) )
        dl_func( url, filename )
        time.sleep( 1 )
    else:
        p('!EXISTS "{}" Checking Length....'.format(filename))
        time.sleep( (2 ** 0.5) / 8 / 2 )

        # get headers and compare against byte size of file
        H = requests.head( url )
        if H.headers.get('Content-Length', None):
            if H.headers['Content-Length'] != str(os.stat(filename).st_size):
                perr( f'Size doesnt match server. Getting again: "{filename}"' )
                dl_func(url, filename)
                time.sleep( 1 )


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


def main():
    if not isdir(FILES_DIR):
        perr('creating {}'.format(FILES_DIR))
        os.mkdir(FILES_DIR, mode=(7*8**2 + 5*8**1 + 5*8**0)) #755
    else:
        perr('{} exists'.format(FILES_DIR))

    fetch_remote = True

    if fetch_remote:
        p('downloading Sam Harris RSS feed')
        feed, feed_name = download_rss_xml(FEED_URL)
        p('updating RSS feed --> "{}"'.format(feed_name))
        with open(feed_name,'w') as f:
            f.write(feed)
    else:
        p('loading Sam Harris RSS feed from file')
        FEED_NAME = FEED_URL[FEED_URL.rindex('/')+1:]
        feed, feed_name = rss_xml_from_file(FEED_NAME)

    time.sleep( (2 ** 0.5) )

    #
    # TITLES
    #
    sentinel = '<title>'
    title_indexes = str_indexes( sentinel, feed )
    TITLES = []
    for index, start in enumerate(title_indexes):
        start += len(sentinel)
        end = feed.index('<', start)
        assert(feed[end] == '<')
        tstring = feed[start:end].rstrip().lstrip()
        TITLES.append(tstring)
    TITLES = TITLES[2:] # clip off first two non-item titles
    TITLES.reverse()
    TITLES = [x.removeprefix('#').replace('\u2014','-').replace('#','').replace(':','').replace('?','').encode('ascii','ignore').decode('utf8') for x in TITLES]

    #
    # URLS
    #
    sentinel = '<enclosure length="0" type="audio/mpeg" url="'
    mp3_url_indexes = str_indexes( sentinel, feed )
    URLS = []
    for index, start in enumerate(mp3_url_indexes):
        start += len(sentinel)
        end = feed.index('"', start)
        assert(feed[start] == 'h')
        assert(feed[end] == '"')
        url = feed[start:end].rstrip().lstrip()
        URLS.append(url)
    URLS.reverse()

    assert(len(URLS) == len(TITLES))

    #
    # INDEXES
    #
    INDEXES = [numpad(i+1) for i,_ in enumerate(TITLES)]

    assert(len(URLS) == len(INDEXES))
    print('{} files to check'.format(len(mp3_url_indexes)))

    #
    # create a fully formatted filename with all the best bits in it
    #
    FINAL_NAMES = []
    for (index, title, url) in zip(INDEXES, TITLES, URLS):
        filename = url[url.rindex('/')+1:]
        final = f"{index} - {filename.removesuffix('.mp3')} - {title}.mp3"
        FINAL_NAMES.append(final)

    #
    # retrieve the files we dont have
    #
    for (final_name, url) in zip(FINAL_NAMES, URLS):
        final_filename = join(FILES_DIR, final_name)
        check_length_download( url, final_filename )


def fetch_url( url, saveto ):
    retval = progress_download(url, saveto)
    return retval


def quoted_strings( sentinel, haystack, payload ):
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

if __name__ == '__main__':
    if len(sys.argv) < 2:
        perr('usage: {} <URL>'.format(sys.argv[0]))
        sys.exit(0)
    url = sys.argv[1]

    """
- default: takes single argument, a 4chan url, and download all the images to a directory, also backs up the html. Default action for subsequent downloads is to skip downloading files we already have, but not check their size

- checks for existence of dir, takes optional dir argument

- optional argument forces 'Content-Length' checks against byte-size of each file to make sure
 all of them are complete

- start by working up a printf progress bar like apt-get
    """

    # created directory
    dirname = url[url.rindex('/')+1:]
    feed_file = os.path.join(dirname, 'index.html')

    if not isdir(dirname):
        perr('creating directory {}'.format(dirname))
        os.mkdir(dirname, mode=(7*8**2 + 5*8**1 + 5*8**0)) #755
    else:
        perr('directory {} exists'.format(dirname))

    # fetch and save html
    ret = fetch_url(url, feed_file)
    if not ret:
        perr('failed to download "{}"'.format(url))
        sys.exit(1)
    else:
        perr('saving "{}"'.format(feed_file))
        with open(feed_file, "r") as f:
            html_string = f.read()

    # collect target image paths
    TITLES1 = []
    sentinel = 'i.4cdn.org'
    quoted_strings(sentinel, html_string, TITLES1 )
    TITLES1 = [f'https://{sentinel}{match}' for match in TITLES1]

    TITLES2 = []
    sentinel = 'is2.4chan.org'
    quoted_strings(sentinel, html_string, TITLES2 )
    TITLES2 = [f'https://{sentinel}{match}' for match in TITLES2]

    TITLES = []
    for T_META in (TITLES1, TITLES2):
        for t in T_META:
            if t[t.rindex('.')-1] != 's' and t not in TITLES:
                TITLES.append(t)

    for index, imgurl in enumerate(TITLES):
        print( f"{index+1}/{len(TITLES)} ", end='' )
        basename = imgurl[imgurl.rindex('/')+1:]
        check_length_download( imgurl, os.path.join(dirname, basename), dl_func=progress_download )


