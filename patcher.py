#!/user/bin/env python
# coding=utf-8
import logging
import sys
import os
from spider import *
from processor import *
import pdb

class Patcher(Spider):
    srcModel = None
    batchSize = 10
    configField = {'path_map':TYPE_JSON+REQUIRED, 'dynamic':TYPE_BOOL, 'headers':TYPE_JSON,
                   'link_format':TYPE_STR, 'update':TYPE_BOOL, 'post':TYPE_STR, 'entry_format':TYPE_STR}
    def __init__(self, configFile, theSect=None):
        Spider.__init__(self, configFile, theSect=theSect)
        self.count = 0
        self.rowCount = 0
        self.loadCheckpoint()

    def saveCheckpoint(self):
        key = 'Patcher:%s:Checkpoint'%self.__class__.__name__
        self.redis.set_number(key, self.checkPoint)
    def loadCheckpoint(self):
        self.redis = RedisUtil()
        self.checkPoint = self.redis.get_number('Patcher:%s:Checkpoint'%self.__class__.__name__)
        
    def loadData(self):
        srcModel = self.srcModel
        return srcModel.select().where(srcModel.id>self.checkPoint).order_by(srcModel.id).limit(self.batchSize)
        
    def setCheckPoint(self, row):
        self.checkPoint = row.id
        
    def makeTask(self, row):
        return []
        
    def progress(self):
        self.count += 1
        if self.count % self.batchSize == 0:
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
        self.saveCheckpoint()
        if self.rowCount == 0:#reset breakpoint
            self.checkPoint = 0
            self.saveCheckpoint()
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
    batchSize = 50
    def loadData(self):
        theSect = self.theSect
        srcModel = self.srcModel
        if theSect != None:
            return srcModel.select().where((srcModel.id>self.checkPoint) & (srcModel.source==theSect)).order_by(srcModel.id).limit(self.batchSize)
        else:
            return srcModel.select().where(srcModel.id>self.checkPoint).order_by(srcModel.id).limit(self.batchSize)
            
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

class LinkDownloader(LinkDownloadProcessor, Patcher):
    srcModel = Article
    def getProxy(self):
        return ['', 'miayandc:miayandc@106.75.99.27:6234']
    
    def saveCheckpoint(self):
        key = 'Patcher:%s:Checkpoint'%self.__class__.__name__
        pushInto(Offset, {'name':key, 'offset':self.checkPoint}, ['name'])

    def loadCheckpoint(self):
        self.checkPoint = 0
        
    def loadData(self):
        srcModel = self.srcModel
        return srcModel.select().where((srcModel.id>self.checkPoint)&(srcModel.status=='INIT')).order_by(srcModel.id).limit(self.batchSize)

    def makeTask(self, row):
        tasks = []
        pics = json.loads(row.pics)
        count = 0
        
        for pic in pics:
            try:
                mdl = LinkMap.select().where(LinkMap.fromLink==pic).get()
                continue
            except:
                pass
            idx = pic.rfind('.')
            idx2 = pic.rfind('/')
            suffix = 'jpg'
            if idx > 0:
                suffix = pic[max(idx, idx2)+1:]
            path = '/data/%s/%s/'%(self.srcModel._meta.db_table, str(row.creationTime)[:10])
            name = '%s-%s.%s'%(row.id, count, suffix)
            if os.path.exists(path+name):
                continue
            task = {'sect':row.source, 'type':'download', 'url':pic, 'path':path, 'name':name}
            tasks.append(task)
            count += 1
        return tasks

    def onFinish(self):
        self.saveCheckpoint()
        if self.rowCount == 0:
            return True
        return False
    
class AvatarDownloader(LinkDownloader):
    srcModel = Links
    def makeTask(self, row):
        tasks = []
        idx = row.link.rfind('.')
        suffix = ''
        if idx > 0:
            suffix = row.link[idx+1:]
        path = '/data/%s/'%(self.srcModel._meta.db_table)
        name = '%s.%s'%(row.id, suffix)
        if os.path.exists(path+name):
            return tasks
        tasks.append({'sect':row.source, 'type':'download', 'url':row.link, 'path':path, 'name':name})
        return tasks
