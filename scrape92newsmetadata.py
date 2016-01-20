from bs4 import BeautifulSoup
from datetime import datetime
from pymongo import MongoClient
import re
import sys
from time import sleep
from urllib2 import HTTPError
import urllib2

from tools import renew_ip, headers, setup_logger, exception_hook
import os


logger = setup_logger('b92statistike-scrape_newsmetadata.log')

re_extract_link = re.compile('(yyyy=([0-9]+))*(&mm=([0-9]+))*(&dd=([0-9]+))*(&nav_category=[0-9]+)*[&?]nav_id=([0-9]+)')
re_hour_minute = re.compile('([0-9][0-9]):([0-9][0-9])')

def _insert_news_metadata_category(db, category_id):
    """
    Reads news metadata from one news category and insert them in Mongo.
    We go back in time, first we need to skip news after 2015., then we
    process those in 2015. and we know how to quit if we bump into news
    which are earlier than 2015.
    There is simple retry logic if we get any HTTP error. All pages are
    saved locally and we use first those if they exists.
    Function is completely idempotent.
    """
    start = 0 # Start is URL parametar for B92 link
    is_below_2015 = False
    while(not is_below_2015):
        if os.path.exists('dumps/news_metadata/cat%d-start%d.html' % (category_id, start)):
            logger.info('Found cached file cat%d-start%d, reusing it', category_id, start)
            f = open('dumps/news_metadata/cat%d-start%d.html' % (category_id, start), 'r')
            html_content = f.read()
            f.close()
        else:
            url = 'http://www.b92.net/info/vesti/index.php?&nav_category={}&start={}'.format(category_id, start)
            logger.info('Fetching url %s', url)
            retries = 0
            try:
                request = urllib2.Request(url, None, headers)
                response = urllib2.urlopen(request)
                html_content = response.read()
                
                f = open('dumps/news_metadata/cat%d-start%d.html' % (category_id, start), 'w')
                f.write(html_content)
                f.close()
            except HTTPError as e:
                logger.warning('Error during fetching')
                if retries == 3:
                    raise e
                else:
                    retries = retries + 1

        soup = BeautifulSoup(html_content, 'html5lib', from_encoding='cp1250')
        articles = soup.select('article')
        logger.info('Found %d articles', len(articles))
        
        # Now we iterate for all found news on this page and insert metadata.
        # Start will be incremented by how many news we read here.
        for article in articles:
            title = article.select('div.text > h2 > a')[0].text
            link = article.select('div.text > h2 > a')[0]['href']
            if link == "":
                # Some news are not clickable, don't have news text, skip those
                logger.warning('Link completely missing')
                continue
            link_parsed = re.search(re_extract_link, link)
            if not link_parsed:
                logger.error('Link is %s', link)
                continue
            # Some news have full date, some have only year and month, some only year.
            # All we care is news which have all three. However, if we have year, we
            # can detect if we passed 2015. year and bail out quicker.
            _, yearstr, _, monthstr, _, daystr, _, news_id = link_parsed.groups()
            if yearstr == None or monthstr == None or daystr == None:
                logger.error('Link missing a date %s', link)
                if yearstr and int(yearstr) < 2015:
                    is_below_2015 = True
                    break
                elif yearstr and int(yearstr) >= 2015:
                    continue
                else:
                    # We don't even have a year, go back to beginning, if needed
                    continue
            excerpt = article.select('div.text > p')[0].text.strip()
            info_part = article.select('div.text > div.info')[0]
            hour_minute = info_part.select('span')[2].text
            hour_minute_parsed = re.search(re_hour_minute, hour_minute)
            if not hour_minute_parsed:
                logger.error('\tHour and minute was %s', hour_minute)
                raise Exception()
            hourstr, minutestr = hour_minute_parsed.groups()
            comment_count_part = info_part.select('span')[3].text
            if not comment_count_part.startswith('Komentara: '):
                logger.error('\tComment count field is %s', comment_count_part)
                raise Exception()
            comment_count = int(comment_count_part[11:])
            
            date_published = datetime(int(yearstr), int(monthstr), int(daystr), int(hourstr), int(minutestr))
            if date_published < datetime(2015, 1, 1, 0, 0):
                logger.warning('\tFinished with 2015 for category %d', category_id)
                is_below_2015 = True
                break

            if date_published > datetime(2016, 1, 1, 0, 0):
                logger.warning('\tArticle from 2016, skipping')
                continue

            existing_news = db.news.find_one({'_id': news_id})
            if not existing_news:
                db.news.insert_one(
                              {'_id': news_id,
                               'category_ids': [category_id,],
                               'link': link,
                               'title': title,
                               'date_first_published': date_published,
                               'date_last_published': date_published,
                               'excerpt': excerpt,
                               'comment_count': comment_count}
                                   )
            else:
                # If we already have news, maybe we already processed it,
                # but maybe this is same news in multiple categories
                # Append new categories if this one doesn't exist.
                if category_id not in existing_news['category_ids']:
                    existing_news['category_ids'].append(category_id)
                    db.news.replace_one({'_id': existing_news['_id']}, existing_news)
                    logger.info('News %s didnt have category %d, so it is added (new categories %s)', news_id, category_id, existing_news['category_ids'])
                else:
                    logger.info('\tNews %s found in DB, skipping', news_id)
        if len(articles) == 0:
            # break a while, as we looped to the end (no more news)
            is_below_2015 = True
        else:
            start = start + len(articles)
            sleep(1)

def _insert_news_metadata(db):
    """
    Loops through each category and adds news metadata to Mongo.
    IP is renewed after each category.
    """
    
    # Create directory where we will dump HTML pages, if it doesn't exists
    if not os.path.exists('dumps/news_metadata'):
        os.makedirs('dumps/news_metadata')

    current_category_id = 1
    # Try to find ID of highest category and start from there.
    # This means we will always go over existing category again:/
    current_category_row = db.news.find_one(sort=[('category_ids',-1)])
    if current_category_row:
        current_category_id = max(current_category_row['category_ids'])
    logger.info('Current maximum category is %d', current_category_id)
    while(current_category_id < 2000):
        # Some weird category we need to skip (they are empty,
        # I don't care looking at edge cases why they do not work. 
        if current_category_id not in (31, 32, 35, 96, 1683, 1692):
            renew_ip()
            _insert_news_metadata_category(db, current_category_id)
        current_category_id = current_category_id + 1

if __name__ == '__main__':
    """
    1/3 pass to scrape B92. This pass goes through pages where all news are,
    and gets whatever we can from that pages (some basic metadata of news).
    It goes category by category, finds all news in 2015 and adds them to Mongo.
    """
    sys.excepthook = exception_hook

    client = MongoClient()
    db = client.b92
    _insert_news_metadata(db)