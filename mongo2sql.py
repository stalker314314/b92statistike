# -*- coding: UTF-8 -*-

import emoji
from pymongo import MongoClient
import pymssql
import sys

from tools import setup_logger, exception_hook

DB_SERVER = '<add-your-server>.database.windows.net'
DB_USERNAME = '<add-your-username@<server>'
DB_PASSWORD = '<add-your-password>'
DB_NAME = 'b92'

logger = setup_logger('b92statistike-mongo2sql.log')

def workaround_freetds_bug(text):
    """
    Emoticons in Instagram posts are outside of 0xffff unicode range
    TDS doesn't like this. We need to use emoji package to convert
    those pesky emoticons to text + there are some other emoticons
    where emoji fails, I guess I should update emoji DB.
    """
    text = emoji.demojize(text)
    text = text.replace(u'🇫󾓮', u' ')
    text = text.replace(u'🇺', u' ')
    text = text.replace(u'🇺', u' ')
    return text

def insert_one_news(news, cursor):
    """Insert one news from dictionary to SQL (jncluding all of its comments)"""
    news_id = int(news['_id'])
    logger.info('Inserting news %d', news_id)

    news_text = workaround_freetds_bug(news['text'])
    news_html_text = workaround_freetds_bug(news['html_text'])
    cursor.execute('INSERT INTO news (id, link, title, excerpt, date_first_published, date_last_published, text, html_text) ' + 
                   'VALUES (%d, %s, %s, %s, %s, %s, %s, %s)',
                   (
                    news_id, news['link'], news['title'], news['excerpt'],
                    news['date_first_published'], news['date_last_published'], news_text, news_html_text
                    )
                   )

    for category in news['category_ids']:
        cursor.execute('INSERT INTO news_category (news_id, category_id) VALUES(%d, %d)', (news_id, category))

    for comment in news['comments']:
        logger.info('\tInserting comment %s', comment['_id'])
        author = workaround_freetds_bug(comment['author'])
        comment_text = workaround_freetds_bug(comment['text'])
        comment_html_text = workaround_freetds_bug(comment['html_text'])
        cursor.execute('INSERT INTO comments (id, news_id, author, date_published, likes, dislikes, text, html_text) VALUES(%d, %d, %s, %s, %d, %d, %s, %s)',
                       (
                        int(comment['_id'][1:]), news_id, author, comment['date_published'],
                        comment['likes'], comment['dislikes'], comment_text, comment_html_text
                        )
                       )

def get_already_inserted(cursor, partition_id):
    """Returns maximum inserted ID by partition (partition optional)"""
    ids = []
    if partition_id == None:
        cursor.execute('SELECT id FROM news')
    else:
        cursor.execute('SELECT id FROM news WHERE id % 10 = %d', (partition_id,))
    for row in cursor:
        ids.append(row[0])
    logger.info('Found %d news in DB', len(ids))
    return ids

if __name__ == '__main__':
    """
    Program reads all news/comments from Mongo and inserts them in Azure SQL DB.
    Expectation is that we insert news ordered by ID, as this is how we know how
    much we inserted up to now and can continue fast where we stopped. Insertion
    is partitioned by last digit in news ID, so you can run more of this program
    in parallel (partition is argument).
    """
    sys.excepthook = exception_hook
    
    partition_id = None
    if len(sys.argv) == 2:
        partition_id = int(sys.argv[1])
        
    client = MongoClient()
    db = client.b92

    cnx = pymssql.connect(server=DB_SERVER, user=DB_USERNAME, password=DB_PASSWORD, database=DB_NAME)

    already_inserted_ids = get_already_inserted(cnx.cursor(), partition_id)
    
    counter = 0
    news_filter = {}
    if partition_id != None:
        news_filter['_id'] = {'$regex': '%d$' % partition_id}

    all_news = db.news.find(news_filter).sort('_id', -1).batch_size(10)
    for news in all_news:
        if int(news['_id']) in already_inserted_ids:
            logger.info('Skipping already inserted id %s', news['_id'])
        else:
            if counter % 10 == 0:
                # Every 10 times, we commit transaction, not to create large log
                # and print current progress
                cnx.commit()

                if partition_id != None:
                    leftover_filter = {'_id': {'$gt': news['_id'], '$regex': '%d$' % partition_id }}
                    total_filter = {'_id': {'$regex': '%d$' % partition_id}}
                else:
                    leftover_filter = {'_id': {'$gt': news['_id']}}
                    total_filter = {}
                leftover = db.news.find(leftover_filter).count()
                total = db.news.find(total_filter).count()
                logger.info('Current progress %d/%d', leftover, total)
            insert_one_news(news, cnx.cursor())
            counter = counter + 1
    cnx.commit()