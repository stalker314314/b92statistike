from bs4 import BeautifulSoup
import sys
from urllib2 import HTTPError
import urllib2

from tools import renew_ip, setup_logger, exception_hook, headers

logger = setup_logger('b92statistike-dump_categories.log')

if __name__ == '__main__':
    """
    This program reads all pages where categories are defined and prints them out.
    TODO: I used this only when data was in SQL, but even then I manually created inserts
    out of this dumped output. Should be more automatic, but it was one-time thing.
    """
    sys.excepthook = exception_hook
    renew_ip()

    for i in range(1, 2000):
        url = 'http://www.b92.net/info/vesti/index.php?&nav_category={}'.format(i)
        logger.info('Fetching url %s', url)
        retries = 0
        try:
            request = urllib2.Request(url, None, headers)
            response = urllib2.urlopen(request)
        except HTTPError as e:
            logger.warning('Error during fetching')
            if retries == 3:
                raise e
            else:
                retries = retries + 1
        soup = BeautifulSoup(response.read(), 'html5lib', from_encoding='cp1250')
        category_header = soup.select('div.blog-head > h1')
        if len(category_header) == 1:
            category_name = category_header[0].text
            logger.warning('%d:%s', i, category_name)
        else:
            logger.info('No category name for %d', i)
        