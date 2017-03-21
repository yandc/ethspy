#!/usr/bin/env python
# coding=utf-8
import logging
import json
import urllib
import urllib2
import time
import subprocess
from selenium import webdriver

srv = 'http://irquasi.ethercap.com'
def reportToServer(path, info):
    try:
        url = srv + '/ethspy/report/' + path
        req = urllib2.Request(url, None, {'Content-Type': ''})
        req.add_data(json.dumps(info))
        resp = urllib2.urlopen(req)
    except Exception, e:
        logging.error('Report to server error:%s'%str(e))

def getReport(path):
    try:
        url = srv + '/ethspy/get_report/' + path
        return json.loads(urllib.urlopen(url).read())
    except Exception, e:
        return []
            
def handle_captcha():
    results = getReport('captcha')
    logging.info('Get %s captcha to handle'%len(results))
    if len(results) == 0:
        return
    for res in results:
        option = webdriver.ChromeOptions()
        sp = None
        if res['value']['proxy'].find('@') > 0:#handle proxy auth
            proxy = res['value']['proxy'].split('@')
            addr = proxy[1].split(':')
            auth = proxy[0].split(':')
            cmd = 'node proxy-login-automator.js  -local_port 8081 -remote_host %s -remote_port %s -usr %s -pwd %s'%(addr[0], addr[1], auth[0], auth[1])
            sp = subprocess.Popen(cmd.split())
            option.add_argument('--proxy-server=localhost:8081')
        else:
            option.add_argument('--proxy-server=%s'%res['value']['proxy'])
        option.add_argument('--test-type')
        option.add_argument('--disable-popup-blocking')
        driver = webdriver.Chrome(chrome_options=option)
        driver.get(res['value']['url'])
        time.sleep(20)
        driver.quit()
        if sp != None:
            sp.kill()

def handle_login():
    results = getReport('login')
    logging.info('Get %s login to handle'%len(results))
    if len(results) == 0:
        return
    for res in results:
        option = webdriver.ChromeOptions()
        option.add_argument('--test-type')
        option.add_argument('--disable-popup-blocking')
        driver = webdriver.Chrome(chrome_options=option)
        sect = res['key'].split(':')[-1]
        driver.get(res['value']['url'])
        time.sleep(30)
        cookies = driver.get_cookies()
        reportToServer('cookie:%s'%sect, cookies)
        driver.quit()
            
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                        datefmt='%d %b %Y %H:%M:%S')
    while True:
        handle_captcha()
        handle_login()
        time.sleep(10)
