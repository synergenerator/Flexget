import urllib
import urllib2
import logging
import re
from plugin_urlrewriting import UrlRewritingError
from flexget.entry import Entry
from flexget.plugin import register_plugin, PluginWarning, internet
from flexget.utils.soup import get_soup
from flexget.utils.tools import urlopener
from flexget.utils.search import StringComparator, torrent_availability

timeout = 10
import socket
socket.setdefaulttimeout(timeout)

log = logging.getLogger('newtorrents')


class NewTorrents:
    """NewTorrents urlrewriter and search plugin."""

    def __init__(self):
        self.resolved = []

    # UrlRewriter plugin API
    def url_rewritable(self, feed, entry):
        # Return true only for urls that can and should be resolved
        if entry['url'].startswith('http://www.newtorrents.info/down.php?'):
            return False
        return entry['url'].startswith('http://www.newtorrents.info') and not entry['url'] in self.resolved
        
    # UrlRewriter plugin API
    def url_rewrite(self, feed, entry):
        url = entry['url']
        if (url.startswith('http://www.newtorrents.info/?q=') or
           url.startswith('http://www.newtorrents.info/search')):
            try:
                url = self.entries_from_search(entry['title'], url=url)[0]['url']
            except PluginWarning, e:
                raise UrlRewritingError(e.value)
        else:
            url = self.url_from_page(url)

        if url:
            entry['url'] = url
            self.resolved.append(url)
        else:
            raise UrlRewritingError('Bug in newtorrents urlrewriter')
            
    # Search plugin API
    def search(self, query, comparator, config=None):
        return self.entries_from_search(query, comparator=comparator)

    @internet(log)
    def url_from_page(self, url):
        """Parses torrent url from newtorrents download page"""
        try:
            page = urlopener(url, log)
            data = page.read()
        except urllib2.URLError:
            raise UrlRewritingError('URLerror when retrieving page')
        p = re.compile("copy\(\'(.*)\'\)", re.IGNORECASE)
        f = p.search(data)
        if not f:
            # the link in which plugin relies is missing!
            raise UrlRewritingError('Failed to get url from download page. Plugin may need a update.')
        else:
            return f.group(1)

    @internet(log)
    def entries_from_search(self, name, url=None, comparator=StringComparator(cutoff=0.9)):
        """Parses torrent download url from search results"""
        comparator.set_seq1(name)
        name = comparator.search_string()
        if not url:
            url = 'http://www.newtorrents.info/search/%s' % urllib.quote(name, safe=':/~?=&%')

        log.debug('search url: %s' % url)

        html = urlopener(url, log).read()
        # fix </SCR'+'IPT> so that BS does not crash
        # TODO: should use beautifulsoup massage
        html = re.sub(r'(</SCR.*?)...(.*?IPT>)', r'\1\2', html)
        
        soup = get_soup(html)
        # saving torrents in dict
        torrents = []
        for link in soup.findAll('a', attrs={'href': re.compile('down.php')}):
            torrent_url = 'http://www.newtorrents.info%s' % link.get('href')
            release_name = link.parent.next.get('title')
            # quick dirty hack
            seed = link.findNext('td', attrs={'class': re.compile('s')}).renderContents()
            if seed == 'n/a':
                seed = 0
            else:
                try:
                    seed = int(seed)
                except ValueError:
                    log.warning('Error converting seed value (%s) from newtorrents to integer.' % seed)
                    seed = 0
            
            #TODO: also parse content_size and peers from results
            if comparator.matches(release_name):
                torrents.append(Entry(title=release_name, url=torrent_url, torrent_seeds=seed,
                                      search_ratio=comparator.ratio(), search_sort=torrent_availability(seed, 0)))
            else:
                log.debug('rejecting search result: %s !~ %s' % (release_name, name))
        # sort with seed number Reverse order
        torrents.sort(reverse=True, key=lambda x: x.get('search_sort', 0))
        # choose the torrent
        if not torrents:
            dashindex = name.rfind('-')
            if dashindex != -1:
                return self.entries_from_search(name[:dashindex], comparator=comparator)
            else:
                raise PluginWarning('No matches for %s' % name, log, log_once=True)
        else:
            if len(torrents) == 1:
                log.debug('found only one matching search result.')
            else:
                log.debug('search result contains multiple matches, sorted %s by most seeders' % torrents)
            return torrents

register_plugin(NewTorrents, 'newtorrents', groups=['urlrewriter', 'search'])
