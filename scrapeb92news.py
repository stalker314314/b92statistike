from bs4 import BeautifulSoup
from datetime import timedelta
from pymongo import MongoClient
import re
import sys
from time import sleep
from urllib2 import HTTPError
import urllib2

from tools import renew_ip, headers, setup_logger, exception_hook
import os


logger = setup_logger('b92statistike-scrape_news.log')

re_changing_publishing_time = re.compile('.*\|\s+([0-9][0-9]):([0-9][0-9])\s+->.*')

def _append_one_news_text(db, news_id, news_link, news_date_published):
    """
    Reads news text for one news and updates it in Mongo.
    It also updates news first date of publish (we don't have that on metadata fetch).
    There is simple retry logic if we get any HTTP error. All pages are
    saved locally and we use first those if they exists.
    """
    if os.path.exists('dumps/news/n%s.html' % news_id):
        logger.info('Found cached file %s, reusing it', news_id)
        f = open('dumps/news/n%s.html' % news_id, 'r')
        html_content = f.read()
        f.close()
    else:
        if news_link.startswith('?'):
            url = 'http://www.b92.net/info/vesti/index.php%s' % news_link
        elif news_link.startswith('http'):
            url = news_link
        elif news_link.startswith('vesti.php'):
            url = 'http://www.b92.net/%s' % news_link
        else:
            url = 'http://www.b92.net%s' % news_link
        logger.info('Fetching url %s', url)
        retries = 1
        while(True):
            try:
                request = urllib2.Request(url, None, headers)
                response = urllib2.urlopen(request)
                html_content = response.read()

                f = open('dumps/news/n%s.html' % (news_id), 'w')
                f.write(html_content)
                f.close()

                break
            except HTTPError as e:
                if e.code == 404 or e.code == 403:
                    logger.warning('Article doesn\'t exist anymore, error %d', e.code)
                    db.news.update_one({'_id': news_id}, {'$set': {'text': '', 'html_text': ''}})
                    return
                logger.warning('Error during fetching')
                if retries % 10 == 0:
                    raise e
                elif retries % 3 == 0:
                    renew_ip()
                    pass
                retries = retries + 1

    soup = BeautifulSoup(html_content, 'html.parser', from_encoding='cp1250')
    article_header = soup.select('div.article-header')
    if len(article_header) != 1:
        logger.warning('Something wrong with article header')
    else:
        time_element = article_header[0].select('time')
        if len(time_element) == 1:
            pub_time_text = time_element[0].text
            if '->' in pub_time_text:
                # If we see "->" that in B92 means that news was updated (football matches...)
                # We need to be careful if we cross day boundary
                logger.info('Time change detected, previously set %s and now it says %s', unicode(news_date_published), pub_time_text)
                hourstr, minutestr = re.search(re_changing_publishing_time, pub_time_text).groups()
                date_first_published = news_date_published.replace(hour=int(hourstr), minute=int(minutestr))
                if date_first_published > news_date_published:
                    date_first_published = date_first_published - timedelta(days=1)
                    logger.info('Moved date to previous day')
                db.news.update_one({'_id': news_id}, {'$set': {'date_first_published': date_first_published}})
                logger.info('Updated first published date to %s', unicode(date_first_published))
    
    article = soup.select('article.item-page')
    if len(article) != 1:
        logger.warning('Something wrong with article')
        db.news.update_one({'_id': news_id}, {'$set': {'text': '', 'html_text': ''}})
    else:
        paragraphs = article[0].findChildren('p')
        # Remove first paragraph as it is same as excerpt
        # Remove also all empty paragraphs
        # What remains is concatenated
        html_text = ''.join([unicode(p) for p in paragraphs[1:] if p.text != ''])
        text = ''.join([unicode(p.text) for p in paragraphs[1:] if p.text != ''])
        db.news.update_one({'_id': news_id}, {'$set': {'text': text, 'html_text': html_text}})
    sleep(0.1)

def _append_news_text(db):
    """
    Loops through all news that don't have text already, add texts to it.
    IP is renewed after 1000 news have been processed
    """
    
    # Create directory where we will dump HTML pages if it doesn't exists already.
    if not os.path.exists('dumps/news'):
        os.makedirs('dumps/news')

    counter = 0
    news = next(db.news.find({'text': {"$exists": False}}).sort('_id', 1).limit(1), None)
    while(news):
        if counter % 1000 == 0:
            leftover = db.news.find({'text': {"$exists": True}}).count()
            total = db.news.count()
            logger.info('Current progress %d/%d', leftover, total)
            renew_ip()
        _append_one_news_text(db, news['_id'], news['link'], news['date_first_published'])
        news = next(db.news.find({'text': {"$exists": False}}).sort('_id', 1).limit(1), None)
        counter = counter + 1

if __name__ == '__main__':
    """
    2/3 pass to scrape B92. This pass goes through all already inserted
    news metadata and populate news texts. It is taking only news that
    don't have text, so it can continue easily after restart.
    """
    sys.excepthook = exception_hook
    client = MongoClient()
    db = client.b92
    _append_news_text(db)