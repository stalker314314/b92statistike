import logging.handlers
from time import sleep
import traceback
import urllib2

from TorCtl import TorCtl

# Definition of headers we use throughout whole scrapper
user_agent = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:43.0) Gecko/20100101 Firefox/43.0'
headers={'User-Agent':user_agent}

def setup_logger(filename):
    """Simple logger used throughtout whole scrapper - logs both to file and console."""
    logger = logging.getLogger('main')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    ch = logging.handlers.TimedRotatingFileHandler(filename=filename, when='midnight', interval=1)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger

def exception_hook(exctype, value, tb):
    """
    Catch any unhandled exception and print its stack trace.
    Useful to see what is going on when scrapper crashes.
    """
    logger = logging.getLogger('main')
    logger.critical('{0}: {1}'.format(exctype, value))
    logger.critical(''.join(traceback.format_tb(tb)))

def _set_urlproxy():
    """Global setup to tell urllib2 to use privoxy."""
    proxy_support = urllib2.ProxyHandler({"http" : "127.0.0.1:8118"})
    opener = urllib2.build_opener(proxy_support)
    urllib2.install_opener(opener)

def request(url):
    request=urllib2.Request(url, None, headers)
    return urllib2.urlopen(request).read()
 
def renew_connection():
    """Connects to local TOR and send signal to renew IP address"""
    conn = TorCtl.connect(controlAddr="127.0.0.1", controlPort=9051, passphrase="12345")
    if not conn:
        raise Exception('Seems you are not running Tor, cant let you do this Dave')
    conn.send_signal("NEWNYM")
    conn.close()

# Previous, current and list of all IP address we had
oldIP = "0.0.0.0"
newIP = "0.0.0.0"
ip_list = []

def renew_ip():
    """
    Renew IP address by telling TOR to change IP address.
    We use icanhasip.com to see our current IP address.
    Method has simple rety logic, since renewing IP address with
    TOR can lag some time, so we want to be sure when we exit
    this method that IP is indeed changed
    """
    global oldIP, newIP
    logger = logging.getLogger('main')

    if oldIP == "0.0.0.0":
        logger.info("\tSetting IP for the first time, renewing connection")
        renew_connection()
        _set_urlproxy()
        newIP = oldIP = request("http://icanhazip.com/")
    else:
        logger.info("\tSetting IP, renewing connection")
        oldIP = newIP
        renew_connection()
        newIP = request("http://icanhazip.com/")
        
        # Now loop until we have new address
        count = 0
        while oldIP == newIP:
            logger.info("\tNew IP same as old IP {}, trying again (current count {})".format(oldIP, count))
            sleep(0.5)
            newIP = request("http://icanhazip.com/")
            count += 1
            if count % 10 == 0:
                logger.info("\tGetting new IP stuck, let's try to renew connection again")
                renew_connection()
                count = 0

    if newIP.endswith('\n'):
        ip_to_return = newIP[:-1]
    else:
        ip_to_return = newIP

    ip_list.append(ip_to_return)
    logger.info("\tAll IPs up to now: {}".format(ip_list))
    return ip_to_return