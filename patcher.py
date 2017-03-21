#!/user/bin/env python
# coding=utf-8
from redis_util import *
import logging
import sys
from ethspy import *
from spider import *
from model import *
from processor import *

class Patcher(Spider):
    srcModel = None
    configField = {'path_map':TYPE_JSON+REQUIRED, 'dynamic':TYPE_BOOL, 'headers':TYPE_JSON,
                   'link_format':TYPE_STR, 'update':TYPE_BOOL, 'post':TYPE_STR, 'entry_format':TYPE_STR}
    def __init__(self, configFile, theSect=None):
        Spider.__init__(self, configFile, theSect=theSect)
        self.count = 0
        self.rowCount = 0
        self.redis = RedisUtil()
        self.checkPoint = self.redis.get_number('Patcher:%s:Checkpoint'%self.__class__.__name__)

    def loadData(self):
        srcModel = self.srcModel
        return srcModel.select().where(srcModel.id>self.checkPoint).order_by(srcModel.id).limit(10)
        
    def setCheckPoint(self, row):
        self.checkPoint = row.id
        
    def makeTask(self, row):
        return []
        
    def progress(self):
        self.count += 1
        if self.count % 100 == 0:
            logging.info('Processed: %s'%self.count)
            
    def onStart(self):
        rows = self.loadData()
        self.rowCount = len(rows)
        for row in rows:
            tasks = self.makeTask(row)
            for task in tasks:
                self.putTask(task)
            self.setCheckPoint(row)
            self.progress()
        
    def onFinish(self):
        key = 'Patcher:%s:Checkpoint'%self.__class__.__name__
        self.redis.set_number(key, self.checkPoint)
        if self.rowCount == 0:#reset breakpoint
            self.redis.set_number(key, 0)
            return True
        return False

class CompanyInfoPatcher(CompanyInfoProcessor, Patcher):
    srcModel = BaseProject
    def makeTask(self, row):
        config = self.configs[self.theSect]
        keyword = row.companyName
        fakeUrl = 'companyInfo/%s'%keyword
        if config['update'] == False and UrlIsExist(fakeUrl):
            return []
        if len(keyword) < 5 or keyword.find('公司') < 0:
            return []
        url = config['entry_format']%urllib.quote(keyword.encode())
        task = {'sect':self.theSect, 'type':'list', 'url':url, 'post':None, 'data':row}
        return [task]

class LeadsPatcher(LeadsProcessor, Patcher):
    srcModel = Leads
    def loadData(self):
        theSect = self.theSect
        srcModel = self.srcModel
        if theSect != None:
            return srcModel.select().where((srcModel.id>self.checkPoint) & (srcModel.source==theSect)).order_by(srcModel.id).limit(50)
        else:
            return srcModel.select().where(srcModel.id>self.checkPoint).order_by(srcModel.id).limit(50)
            
    def makeTask(self, row):
        url = row.website
        sect = row.source
        if row.source == '36kr':
            url = url.replace('/company/', '/api/company/')
        elif row.source == 'angelcrunch':
            url += '/j/detail_info_view'
        task = {'sect':sect, 'type':'detail', 'url':url, 'post':None, 'fromId':row.id}
        return [task]

class LagouPatcher(LagouProcessor, LeadsPatcher):pass
