#!/usr/bin/env python
# coding=utf-8
from ethspy import *
from redis_util import *
from scheduler import *
from processor import *
from monitor import *
import sys
import gevent
from gevent import monkey;
monkey.patch_all()

TYPE_STR = 1
TYPE_JSON = 2
TYPE_BOOL = 3
REQUIRED = 10
    
class Spider(Processor, Scheduler):
    configField = {'start_url':TYPE_STR+REQUIRED, 'path_map':TYPE_JSON+REQUIRED, 'headers':TYPE_JSON,
                   'link_format':TYPE_STR, 'dynamic':TYPE_BOOL, 'update':TYPE_BOOL, 'post':TYPE_STR, 'js':TYPE_STR}
    def __init__(self, configFile, theSect=None, interval=5):
        self.configFile = configFile
        self.configs = {}
        self.theSect = theSect
        Scheduler.__init__(self, interval)
        self.proxies = self.getProxy()
        self.loadConfig()
        self.registProcessor()
        self.monitor = Monitor(self.__class__.__name__)

    def getProxy(self):
        redis = RedisUtil()
        proxy = redis.get_obj('ethspy:proxy:%s'%self.__class__.__name__)
        if proxy == None or len(proxy) == 0:
            return ['']
        return proxy

    def onStart(self):
        for sect, url, post in urlPoller(self.configs):
            task = self.makeTask(sect, url, post)
            self.putTask(task)
    def makeTask(self, sect, url, post):
        return {'sect':sect, 'type':'list', 'url':url, 'post':post}
            
    def onFetch(self, task, cid):
        config = self.configs[task['sect']]
        header = config['headers'].copy()
        if 'header' in task:
            header.update(task['header'])
        if task['post'] == '':
            task['post'] = None
        task['proxy'] = self.proxies[cid]
        result = fetch(task['url'], self.proxies[cid], header, task['post'], dynamic=config['dynamic'], js=config['js'])
        if result['status'] == 200:
            result['element'] = extractElement(result['content'], config['path_map'][task['type']])
        else:
            result['element'] = None
        return result

    def onFinish(self):
        logging.info('Spider finish.')
        return True

    def processTask(self, task, cid):
        self.monitor.count(task)
        result = self.onFetch(task, cid)
        result['proxy'] = self.proxies[cid]
        tasks = self.onProcess(task, result)
        for task in tasks:
            self.putTask(task)
            
    def runner(self, cid):
        threads = []
        lastTimestamp = 0
        while True:
            if len(threads) == 100:#sweep dead body
                gevent.joinall(threads)
                del threads[:]
            task = self.getTask(cid)
            if task == None:
                gevent.joinall(threads)
                task = self.getTask(cid)
                if task == None:
                    return
            now = time.time()
            if now - lastTimestamp < 0.2:
                gevent.sleep(now-lastTimestamp)
            lastTimestamp = now
            threads.append(gevent.spawn(self.processTask, task, cid))
            
    def loadConfig(self):
        logging.info('Load config file %s'%self.configFile)
        cf = ConfigUtil(self.configFile)
        for sect in cf.sections():
            if self.theSect != None and sect not in self.theSect:
                continue
            config = {}
            for field, fieldType in self.configField.iteritems():
                _type = fieldType % REQUIRED
                try:
                    if _type == TYPE_STR:
                        config[field] = cf.get(sect, field)
                    elif _type == TYPE_JSON:
                        config[field] = json.loads(cf.get(sect, field))
                    elif _type == TYPE_BOOL:
                        config[field] = cf.getboolean(sect, field)
                except TypeError, e:
                    if fieldType/REQUIRED == REQUIRED:
                        raise e
                    if _type == TYPE_STR:
                        config[field] = ''
                    elif _type == TYPE_JSON:
                        config[field] = {}
                    elif _type == TYPE_BOOL:
                        config[field] = False
                except Exception, e:
                    logging.error('Config file error: %s'%(str(e)))
                    sys.exit(1)
            cookie = getReport('cookie:%s?del=no'%sect)
            if len(cookie) > 0:
                cookieStr = ''
                for ck in cookie[0]['value']:
                    cookieStr += ck['name']+'='+ck['value']+'; '
                config['headers']['Cookie'] = cookieStr
            self.configs[sect] = config
        return self.configs
        
    def run(self):
        threads = []
        while True:
            self.onStart()
            for cid in range(len(self.proxies)):
                threads.append(gevent.spawn(self.runner, cid))
            gevent.joinall(threads)
            if self.onFinish() == True:
                self.monitor.clean()
                break

