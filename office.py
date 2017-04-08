#!/usr/bin/env python
# coding=utf-8
import os
import chardet
from email_util import *
from crawler import *
import pdb

class MailOffice:
    def __init__(self):
        pass
    def run(self):
        mailfp = EmailUtil('sina.com', 'dataspy@sina.com', 'YDC21415926')
        mails = mailfp.recvEmail()
        logging.info('Start run...')
        for mail in mails:
            try:
                for part in mail['content']:
                    if type(part) != dict:
                        continue
                    if 'filename' not in part:
                        continue
                    if part['filename'] != 'keyword.csv':
                        continue
                    break
                
                charset = chardet.detect(part['data'])
                encoding = 'gbk'
                if charset['encoding'].lower().find('utf') == 0:
                    encoding = charset['encoding']
                logging.info('Get mail from %s, encoding:%s'%(mail['from'], encoding))
                    
                data = part['data'].decode(encoding).encode('utf8')
                fp = open('config/keyword.csv', 'w')
                fp.write(data)
                fp.close()
                
                if os.path.exists('data/result.csv'):
                    os.remove('data/result.csv')
                    
                spider = PriceCrawler('config/price.cfg')
                spider.run()
                mailfp.sendEmail(mail['from'], 'Re:'+mail['subject'], files=['data/result.csv'])
                logging.info('Send mail Done.')
            except Exception, e:
                logging.error(str(e))

if __name__ == '__main__':
    office = MailOffice()
    office.run()
