# -*- coding: UTF-8 -*-

from bs4 import BeautifulSoup
import copy
from datetime import datetime
import os
from pymongo import MongoClient
import re
import sys
from time import sleep
import urllib2

from tools import renew_ip, headers, setup_logger, exception_hook


logger = setup_logger('b92statistike-scrape_comments.log')

re_date_comment_extract = re.compile('([0-9]+).\s(.*)\s(201[456])\s([0-9]+):([0-9]+)')

def convert_month(monthstr):
    """
    Converts month as string to something datetime module understands.
    TODO: this sucks, dictionary is better
    """
    if monthstr == 'januar':
        return 1
    elif monthstr == 'februar':
        return 2
    elif monthstr == 'mart':
        return 3
    elif monthstr == 'april':
        return 4
    elif monthstr == 'maj':
        return 5
    elif monthstr == 'jun':
        return 6
    elif monthstr == 'jul':
        return 7
    elif monthstr == 'avgust':
        return 8
    elif monthstr == 'septembar':
        return 9
    elif monthstr == 'oktobar':
        return 10
    elif monthstr == 'novembar':
        return 11
    elif monthstr == 'decembar':
        return 12
    raise Exception('Unknown month %s', monthstr)

def _append_one_news_comments(db, news_id, news_link, news_comment_count):
    """
    Reads comments for one news and appends them in Mongo.
    There is simple retry logic if we get any HTTP error. All pages are
    saved locally and we use first those if they exists.
    """

    if os.path.exists('dumps/comments/k%s.html' % news_id):
        logger.info('Found cached file %s, reusing it', news_id)
        f = open('dumps/comments/k%s.html' % news_id, 'r')
        html_content = f.read()
        f.close()
    else:
        split_path = news_link.split('/')
        if split_path[0] == '':
            url = 'http://www.b92.net/%s/komentari.php?nav_id=%s' % (split_path[1], news_id)
        elif news_link.startswith('http://bulevar.b92.net'):
            url = 'http://bulevar.b92.net/komentari.php?nav_id=%s' % news_id
        else:
            raise Exception('Link for news unrecognized: %s', news_link)
        logger.info('Fetching url %s', url)
        request = urllib2.Request(url, None, headers)
        response = urllib2.urlopen(request)
    
        html_content = response.read()
        
        f = open('dumps/comments/k%s.html' % news_id, 'w')
        f.write(html_content)
        f.close()

    soup = BeautifulSoup(html_content, 'html.parser', from_encoding='cp1250')
    zero_comments = soup.select('div.comments > p')
    if len(zero_comments) == 1 and zero_comments[0].text == 'Nema komentara na izabrani dokument.':
        logger.info('Didnt found any comments')
        db.news.update_one({'_id': news_id}, {'$set': {'comments': []}})
        return

    comments = soup.select('div#tab-comments-h-tab > div.comments > ol')
    if len(comments) != 1:
        raise Exception('Comments cannot be found')
    comment_list = comments[0].select('li')
    logger.info('Comments found: %d, comment detected: %d', len(comment_list), news_comment_count)

    comment_to_insert = []
    for comment in comment_list:
        comment_id = comment['id']
        logger.info('\tProcessing comment %s', comment_id)
        
        # Extract author
        if len(comment.select('span.comment-author')) != 1:
            logger.error('\tComment doesnt have author: %s', unicode(comment))
            raise Exception()
        author = comment.select('span.comment-author')[0].text

        # Extract date
        if len(comment.select('span.comment-date')) != 1:
            logger.error('\tComment doesnt have date: %s', unicode(comment))
            raise Exception()
        date_str = comment.select('span.comment-date')[0].text
        day, month, year, hour, minute = re.search(re_date_comment_extract, date_str).groups()
        date_published = datetime(int(year), convert_month(month), int(day), int(hour), int(minute))

        # Extract likes
        if len(comment.select('a.rate-up')) != 1:
            logger.error('Comment doesnt have likes: %s', unicode(comment))
            raise Exception
        likes = int(comment.select('a.rate-up > span')[0].text[1:-1])
        
        # Extract dislikes
        if len(comment.select('a.rate-dn')) != 1:
            logger.error('Comment doesnt have dislikes: %s', unicode(comment))
            raise Exception
        dislikes = int(comment.select('a.rate-dn > span')[0].text[1:-1])

        # Extract comment text (we use copy yoga here, as we don't want to modify existing soup document
        comment_clone = copy.copy(comment)
        comment_clone.select('div.rate-comment-container')[0].extract()
        [s.extract() for s in comment_clone.findAll('span')]
        [s.extract() for s in comment_clone.findAll('p')]
        [s.extract() for s in comment_clone.findAll('a')]
        text = comment_clone.text.strip()
        if text.endswith('(, )'):
            text = text[:-4].strip()
            
        html_text = comment_clone.decode_contents(formatter='html').strip()
        if html_text.endswith('(, )'):
            html_text = html_text[:-4].strip()
        has_more_to_strip = True
        while(has_more_to_strip):
            if html_text.endswith('<br/>'):
                html_text = html_text[0:-5]
            elif html_text.endswith('\n\t'):
                html_text = html_text[0:-2]
            elif html_text.endswith('&nbsp;'):
                html_text = html_text[0:-6]
            else:
                has_more_to_strip = False
        # For some reason, B92 sometimes don't returns š, but scaron escaped entity
        html_text = html_text.replace('&scaron;', u'š')
        html_text = html_text.replace('&Scaron;', u'Š')

        comment_to_insert.append({
                                  '_id': comment_id,
                                  'author': author,
                                  'date_published': date_published,
                                  'text': text,
                                  'html_text': html_text,
                                  'likes': likes,
                                  'dislikes': dislikes})
    logger.info('\tAdding %d comments', len(comment_to_insert))
    db.news.update_one({'_id': news_id}, {'$set': {'comments': comment_to_insert}})
    sleep(0.1)

def _append_comments(db, partition_id):
    """
    Loops through all news that do not have comments and append them.
    IP is renewed after 1000 processed news.
    """
    
    # Create directory to dump HTML pages if it doesn't exists already
    if not os.path.exists('dumps/comments'):
        os.makedirs('dumps/comments')

    counter = 0
    news_filter = {'comments': {'$exists': False}, 'comment_count': {'$gt': 0}}
    if partition_id != None:
        news_filter['_id'] = {'$regex': '%d$' % partition_id}
    news = next(db.news.find(news_filter).sort('_id', -1).limit(1), None)
    while(news):
        if counter % 1000 == 0:
            leftover = db.news.find(news_filter).count()
            total = db.news.find({'comment_count': {'$gt': 0}}).count()
            logger.info('Current progress %d/%d', total - leftover, total)
            renew_ip()
        _append_one_news_comments(db, news['_id'], news['link'], news['comment_count'])
        news = next(db.news.find(news_filter).sort('_id', -1).limit(1), None)
        counter = counter + 1

if __name__ == '__main__':
    """
    3/3 pass to scrape B92. This pass goes through all news that
    still don't have comments and appends them to existing news.
    This program is partitioned by last digit of news ID, so you can
    run many of them in parallel with different partitions.
    Partition is argument to program and is optional.
    """
    sys.excepthook = exception_hook
    
    partition_id = None
    if len(sys.argv) == 2:
        partition_id = int(sys.argv[1])

    client = MongoClient()
    db = client.b92
    _append_comments(db, partition_id)