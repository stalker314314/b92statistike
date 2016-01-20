# -*- coding: UTF-8 -*-

from pymongo import MongoClient
import re
import operator

# Regular expression that extracts all words in unicode
re_words = re.compile(u'[\wčćšđžČĆŠĐŽ]+')


if __name__ == '__main__':
    """
    Program that reads all news from Mongo DB, tokenize words in title
    and builds a histogram of how much each word is being used.
    Possible improvement: use Levenshtein distance, as currently
    I was enumarating similar words manually.
    """
    client = MongoClient('192.168.60.10', 27017)
    db = client.b92
    
    count = 0
    dic = {}
    all_news = db.news.find({}).sort('_id', -1)
    for news in all_news:
        count = count + 1
        if count % 100 == 0:
            print(count)

        # If you want some specific category, uncomment this
        #if (1852 not in news['category_ids']):
        #    continue

        tokens = re_words.findall(news['title'])
        for token in tokens:
            # TODO: this sucks, should be dictionary list for replacement, not like this
            token = token.lower() \
                .replace(u'č', u'c').replace(u'Č', u'c') \
                .replace(u'ć', u'c').replace(u'Ć', u'c') \
                .replace(u'ž', u'z').replace(u'Ž', u'z') \
                .replace(u'š', u's').replace(u'Š', u's') \
                .replace(u'đ', u'dj').replace(u'Đ', u'dj')
            if token not in dic:
                dic[token] = 0
            dic[token] = dic[token] + 1

    # Now print top 1000 words (with highest frequency)
    sorted_dic = sorted(dic.items(), key=operator.itemgetter(1), reverse=True)
    for s in sorted_dic[0:1000]:
        print(s[0] + u' ' + unicode(s[1]))