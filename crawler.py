#!/usr/bin/env python
# coding=utf-8
from spider import *
import sys
import os
import bisect

'''
Can only config one target
'''
Models = {'article':Article}

class IdFiller(Spider):
    configField = {'path_map':TYPE_JSON+REQUIRED, 'headers':TYPE_JSON, 'post':TYPE_STR, 'update':TYPE_BOOL,
                   'link_format':TYPE_STR, 'dynamic':TYPE_BOOL, 'scan_format':TYPE_STR, 'js':TYPE_STR}
    def __init__(self, configFile, target, theSect=None, interval=5):
        Spider.__init__(self, configFile, theSect=theSect, interval=interval)
        self.target = target
        self.redis = RedisUtil()
        self.isFinish = False
        self.id_list = {}
        self.count = self.redis.get_number('ethspy:config:'+target+':count') + 1
        self.pid = self.redis.get_number('ethspy:config:'+target+':checkpoint')
        if self.count % 6 == 0:
            self.pid = max(0, self.pid-4000)
        elif self.count % 21 == 0:
            self.pid = self.pid/2
        if self.pid > 0:
            self.id_list = self.redis.get_obj('ethspy:config:'+target+':idlist')
            
    def onStart(self):
        target = self.target
        tmpid = self.pid
        mdl = Models[target]
        #get all page id into sorted id_list
        rows = mdl.select().where(mdl.id > tmpid)
        for row in rows.naive().iterator():
            source = row.source
            if source not in self.configs or len(self.configs[source]['scan_format']) == 0:
                continue
            tmpid = row.id
            pageid = getPageid(row.website)
            if pageid == 0:#is not id page
                continue
            if source not in self.id_list:
                self.id_list[source] = []
            idx = bisect.bisect(self.id_list[source], pageid)
            if idx == 0 or self.id_list[source][idx-1] != pageid:#only one pageid
                self.id_list[source].insert(idx, pageid)
        if tmpid == self.pid:
            self.isFinish = True
            return
        #fill all gaps, expand right range
        id_range = {}
        logging.info('Fill all gaps in %s: %s-%s, expand right range.'%(target, self.pid, tmpid))
        rows = mdl.select().where((mdl.id>self.pid) & (mdl.id<=tmpid))
        for row in rows.naive().iterator():
            source = row.source
            if source not in self.configs or len(self.configs[source]['scan_format']) == 0:
                continue
            self.pid = row.id
            pageid = getPageid(row.website)
            if pageid == 0:#is not id page
                continue
            idx = bisect.bisect_left(self.id_list[source], pageid)
            if idx == 0:#left range
                lid = 0
            else:
                lid = self.id_list[source][idx-1]
            if idx >= len(self.id_list[source]):#expand the right range
                logging.info('Expand right range for %s,%s: %s-%s.'%(target, source, lid, pageid))
                pageid = pageid + 30
            if pageid - lid < 2:
                continue
            elif pageid - lid > 1000:
                logging.info('Configer for %s,%s: %s-%s'%(target, source, lid, pageid))
                if source not in id_range:
                    id_range[source] = [xrange(lid+1, lid+300)]
                else:
                    id_range[source].append(xrange(lid+1, lid+300))
                id_range[source].append(xrange(pageid-300, pageid-1))
            else:
                if source not in id_range:
                    id_range[source] = [range(lid+1, pageid-1)]
                else:
                    id_range[source].append(range(lid+1, pageid-1))
                logging.info('Configer for %s,%s: %s-%s'%(target, source, lid, pageid))

        configs = {}
        for sect in id_range:
            if sect not in self.configs or len(self.configs[sect]['scan_format']) == 0:
                continue
            configs[sect] = self.configs[sect].copy()
            configs[sect]['start_url'] = configs[sect]['scan_format']%str(id_range[sect])
        for sect, url, post in urlPoller(configs):
            if UrlIsExist(url):
                continue
            task = {'sect':sect, 'type':'detail', 'url':url, 'post':post}
            self.putTask(task)
    
    def onFinish(self):
        logging.info('Breakpid: %s'%self.pid)
        self.redis.set_obj('ethspy:config:'+self.target+':idlist', self.id_list)
        self.redis.set_number('ethspy:config:'+self.target+':checkpoint', self.pid)
        if self.isFinish == True:
            self.redis.set_number('ethspy:config:'+self.target+':count', self.count)
            return True
        return False

class LeadsCrawler(LeadsProcessor, Spider):
    pass
class InvestorCrawler(InvestorProcessor, Spider):
    pass
class InvestmentCrawler(InvestmentProcessor, Spider):
    pass
class OrganizationCrawler(OrganizationProcessor, Spider):
    pass
class CsvCrawler(CsvProcessor, Spider):
    pass
class LeadsIdFiller(LeadsProcessor, IdFiller):
    pass
class InvestorIdFiller(InvestorProcessor, IdFiller):
    pass
class OrganizationIdFiller(OrganizationProcessor, IdFiller):
    pass
class InvestmentProjectCrawler(InvestmentProjectProcessor, Spider):pass

class LagouJobCrawler(LagouProcessor, Spider):
    def registProcessor(self):
        LagouProcessor.registProcessor(self)
        self.processRoute['newjob'] = self.processListPage
        
    def makeTask(self, sect, url, post):
        return {'sect':sect, 'type':'newjob', 'url':url, 'post':post, 'header':self.Header}
        
class QimingpianOrgCrawler(QimingpianOrgProcessor, Spider):pass

class MiaArticleCrawler(MiaArticleProcessor, Spider):
    def getProxy(self):
        return ['H203003O85OWU77D:2E8751BD559CCC72@proxy.abuyun.com:9020']

class ImageCollector(ImageCollectProcessor, Spider):
    def getProxy(self):
        return ['miayandc:miayandc@106.75.99.27:6234']

    
