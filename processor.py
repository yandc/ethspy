#!/usr/bin/env python
# coding=utf-8
from ethspy import *
from model import *
from redis_util import *
import sys
import os

SUCC_PAGE = 'Succ'
FAIL_PAGE = 'Fail'
CAPTCHA_PAGE = 'Captcha'
LOGIN_PAGE = 'Login'
EMPTY_KEYWORD = 'Empty Keyword'
EMPTY_LINK = 'Empty Link'
EMPTY_LIST = 'Empty List'

class Processor():
    processRoute = {}
    def registProcessor(self):pass
    def checkResult(self, task, result):
        if result['status'] != 200:
            return FAIL_PAGE
        return SUCC_PAGE
    def beforeProcess(self, task, result):
        return True
    def afterProcess(self, task, result):pass
    def onProcess(self, task, result):
        ret = self.checkResult(task, result)
        if ret != SUCC_PAGE:
            return self.onBroken(task, result, ret)
        taskList = []
        if self.beforeProcess(task, result) == False:
            return taskList
        if task['type'] in self.processRoute:
            tasks = self.processRoute[task['type']](task, result)
            if type(tasks) == list:
                taskList += tasks
        else:
            logging.warning('Do nothing on process with %s'%task['url'])
        tasks = self.afterProcess(task, result)
        if type(tasks) == list:
            taskList += tasks
        return taskList

    def onBroken(self, task, result, code=FAIL_PAGE):
        logging.info('%s:(%s) %s'%(code, result['status'], task['url']))
        self.monitor.error(task, result, code)
        return self.makeRetryTask(task, 3)

    def makeRetryTask(self, task, maxRetry):
        if 'retry' in task:
            task['retry'] += 1
        else:
            task['retry'] = 1
        if maxRetry < 0 or maxRetry > task['retry']:
            return [task]
        else:
            spyError(task['url'])
            return []

class CrawlerProcessor(Processor):
    def registProcessor(self):
        self.processRoute['detail'] = self.processDetailPage
        self.processRoute['list'] = self.processListPage

    def processListPage(self, task, result):
        if type(result['element']) != list:
            return self.onBroken(task, result)
        if len(result['element']) == 0:
            return self.onBroken(task, result, EMPTY_LIST)
        sect = task['sect']
        config = self.configs[sect]
        url = task['url']
        logging.info('Extract %s links from %s'%(len(result['element']), task['url']))
        tasks = []
        for ele in result['element']:
            if type(ele) != dict or 'link' not in ele:#do not craw down
                self.processDetailPage(task, {'element':ele})
                continue
            if len(ele['link']) == 0:#can find out path_map error
                return self.onBroken(task, result, EMPTY_LINK)
            
            link = str(ele['link'][0])#get link from [link]
            if len(config['link_format']) > 0:
                link = config['link_format']%(link)
            elif link.lower().find('http') != 0:
                net = urlparse(url)
                link = net[0] + '://' + net[1] + link
            link = link.replace('https://', 'http://')
            if config['update'] == False and UrlIsExist(link):
                continue
            tasks.append({'sect':sect, 'type':'detail', 'url':link, 'post':None, 'ele':ele})
        return tasks
            
    def processDetailPage(self, task, result):
        logging.warning('Do nothing with detail page %s'%task['url'])

    def beforeProcess(self, task, result):
        eles = result['element']
        if 'ele' in task:
            ele = task['ele']
            for key in ele:#merge top ele(outline) into eles(details)
                if key not in eles:
                    eles[key] = ele[key]
                elif type(eles[key]) == dict:
                    eles[key].update(ele[key])
                elif len(ele[key]) > 0 and len(eles[key]) == 0:
                    eles[key] = ele[key]
        return True

    def onBroken(self, task, result, code=FAIL_PAGE):
        logging.info('%s:(%s) %s'%(code, result['status'], task['url']))
        self.monitor.error(task, result, code)
        if result['status'] == 404 or result['status'] == 500:
            spyError(task['url'])
            return []
        else:
            return self.makeRetryTask(task, 3)

class LeadsProcessor(CrawlerProcessor):
    def processDetailPage(self, task, result):
        eles = result['element']
        sect = task['sect']
        url = task['url']
        if 'title' not in eles or len(eles['title']) == 0:
            return self.onBroken(task, result, EMPTY_KEYWORD)
        ret = spySuccess(url, eles)
        logging.info('Get leads from %s'%(url))
        if ret == 1:#need insert or update leads
            info = {}
            info['title'] = ','.join(eles['title'])
            info['abstract'] = json.dumps(eles['abstract'], ensure_ascii=False, encoding="utf-8")
            info['city'] = ','.join(eles['city'])
            info['label'] = ','.join(eles['label'])
            info['source'] = sect
            if sect == '36kr':
                info['website'] = url.replace('api/', '')
            elif sect == 'angelcrunch':
                info['website'] = url.replace('/j/detail_info_view', '')
            else:
                info['website'] = url
            pushInto(Leads, info, ['title', 'website'])
	
        if sect == 'angelcrunch':#download bp
            path = 'data/bp/'+eles['title'][0].replace('/', '|')+'.pdf'
            if os.path.exists(path):
                return
            url = 'http://angelcrunch.com/startup/%s/j/bp'%(str(eles['link'][0]))
            result = fetch(url)
            ele = extractElement(result['content'], {'path_type':'jpath', 'bplink':'data|bp'})
            if len(ele['bplink']) > 0:
                bplink = ele['bplink'][0]
                result = fetch(bplink, None)
                if result['content'] != None and len(result['content']) > 0:
                    fp = open(path, 'w')
                    fp.write(html)
                    fp.close()


class InvestorProcessor(CrawlerProcessor):
    def processDetailPage(self, task, result):
        eles = result['element']
        sect = task['sect']
        url = task['url']
        if 'name' not in eles or len(eles['name']) == 0:
            return self.onBroken(task, result, EMPTY_KEYWORD)
        ret = spySuccess(url, eles)
        logging.info('Get investor from %s'%(url))
        if ret == 1:#need insert or update leads
            info = {}
            for key in eles:
                if key == 'link' or key == 'linkText':
                    continue
                info[key] = obj2string(eles[key])
            info['source'] = sect
            if sect == '36kr':
                info['website'] = url.replace('api/', '').replace('user', 'userinfo').replace('/basic', '')
            else:
                info['website'] = url
            info['updateTime'] = time.strftime("%Y-%m-%d %H:%M:%S")
            pushInto(Investor, info, ['website'])

class InvestmentProcessor(CrawlerProcessor):
    def processDetailPage(self, task, result):
        eles = result['element']
        sect = task['sect']
        url = task['url']
        if 'project' not in eles or len(eles['project']) == 0:
            return self.onBroken(task, result, EMPTY_KEYWORD)
        ret = spySuccess(url, eles)
        if ret == 1:#need insert or update leads
            info = {}
            for key in eles:
                if key == 'link' or key == 'linkText':
                    continue
                info[key] = obj2string(eles[key])
            info['source'] = sect
            if sect == 'innotree' and 'date' in info:
                info['date'] = time.strftime("%Y.%m.%d", time.localtime(int(info['date'])))
            isCreate, row = pushInto(Investment, info, ['source', 'project', 'date'])#no need to update
            if isCreate == True:
                logging.info('Get investment %s, %s from %s'%(info['date'], info['project'], url))

class OrganizationProcessor(CrawlerProcessor):
    def processDetailPage(self, task, result):
        eles = result['element']
        sect = task['sect']
        url = task['url']
        if 'name' not in eles or len(eles['name']) == 0:
            return self.onBroken(task, result, EMPTY_KEYWORD)
        ret = spySuccess(url, eles)
        if ret == 1:#need insert or update leads
            info = {}
            for key in eles:
                if key == 'link' or key == 'linkText':
                    continue
                info[key] = obj2string(eles[key])
            info['source'] = sect
            info['website'] = url
            info['updateTime'] = time.strftime("%Y-%m-%d %H:%M:%S")
            isCreate, row = pushInto(Organization, info, ['website'])#update by website
            if isCreate == True:
                logging.info('Get organization %s from %s'%(info['name'], url))

class CsvProcessor(CrawlerProcessor):
    def processDetailPage(self, task, result):
        eles = result['element']
        sect = task['sect']
        url = task['url']
        fp = open(sect+'.csv', 'a')
        output = ''
        for key, value in eles.iteritems():
            output += obj2string(value) + ','
        output += '\r\n'
        fp.write(output.encode('gbk'))
        fp.close()

class InvestmentProjectProcessor(InvestmentProcessor, LeadsProcessor):
    xiniuStageMap = {'1040':'B轮', '1030':'A轮', '1011':'天使轮', '1130':'战略投资', '1020':'Pre-A轮', '1105':'新三板', '1031':'A+轮', '1041':'B+轮', '1106':'新三板定增', '1060':'D轮', '1110':'IPO', '1120':'被收购', None:'未知', '1010':'种子轮', '1050':'C轮', '1051':'C+轮', '1061':'D+轮'}
    def onProcess(self, task, result):
        sect = task['sect']
        config = self.configs[sect]
        for ele in result['element']['investment']:
            if sect == 'xiniudata':
                stage = obj2string(ele['stage'])
                if stage in self.xiniuStageMap:
                    ele['stage'] = self.xiniuStageMap[stage]
                else:
                    ele['stage'] = self.xiniuStageMap[None]
            InvestmentProcessor.processDetailPage(self, task, {'element':ele})
        for ele in result['element']['project']:
            if sect == 'xiniudata':
                stage = obj2string(ele['abstract']['stage'])
                if stage in self.xiniuStageMap:
                    ele['abstract']['stage'] = [self.xiniuStageMap[stage]]
                else:
                    ele['abstract']['stage'] = [self.xiniuStageMap[None]]
            elif sect == 'qimingpian':
                li = obj2string(ele['abstract']['homepage']).split('url=')
                if len(li) > 1:
                    gw = urllib.unquote(li[1])
                    ele['abstract']['homepage'] = [gw]
            task['url'] = obj2string(ele['link'])
            if len(config['link_format']) > 0:
                task['url'] = config['link_format']%task['url']
            LeadsProcessor.processDetailPage(self, task, {'element':ele})
        return []
        
class CompanyInfoProcessor(CrawlerProcessor):
    lastReportTime = {}
    def processListPage(self, task, result):
        tasks = []
        config = self.configs[task['sect']]
        tasks = CrawlerProcessor.processListPage(self, task, result)
        for _task in tasks:
            _task['data'] = task['data']
            _task['header'] = {'Cookie':''}
        return tasks

    def processDetailPage(self, task, result):
        element = result['element']
        ret = spySuccess(task['url'], element)
        if ret != 1:
            return
        data = task['data']
        if 'companyName' not in element or len(element['companyName']) == 0:
            return self.onBroken(task, result, EMPTY_KEYWORD)
        for item in element['change']:
            for key, value in item.iteritems():
                item[key] = obj2string(value)
            item['fromId'] = data.fromId
            item['md5'] = hashlib.md5(str(item)).hexdigest()
            pushInto(ComChange, item, ['fromId', 'md5'])
        for item in element['holders']:
            for key, value in item.iteritems():
                item[key] = obj2string(value)
            item['fromId'] = data.fromId
            pushInto(ComHolder, item, ['fromId', 'name'])
        for item in element['topManager']:
            for key, value in item.iteritems():
                item[key] = obj2string(value)
            item['fromId'] = data.fromId
            pushInto(ComManager, item, ['fromId', 'name'])
        for key, value in element.iteritems():
            element[key] = obj2string(value)
        element['fromId'] = data.fromId
        element['fromUrl'] = task['url']
        pushInto(ComInfo, element)

    def checkResult(self, task, result):
        html = result['content']
        if result['status'] != 200:
            return FAIL_PAGE
        dom = etree.HTML(html)
        title = obj2string(dom.xpath('//head/title/text()'))
        if title.find('错误') >= 0 or title.find('验证') >= 0:
            return CAPTCHA_PAGE
        elif title.find('登录') >= 0 or html.find('点击登录') > 0:
            return LOGIN_PAGE
        elif len(result['element']) == 0:
            return FAIL_PAGE
        return SUCC_PAGE

    def onBroken(self, task, result, code=FAIL_PAGE):
        logging.warning('%s:(%s)%s.'%(code, result['status'], task['url']))
        self.monitor.error(task, result, code)
        if code == CAPTCHA_PAGE:#let man pass captcha
            proxy = result['proxy']
            if proxy == '':#get local ip
                proxy = urllib.urlopen('http://members.3322.org/dyndns/getip').read().replace('\n', '')+':6128'
            report_info = {'proxy':proxy, 'url':task['url']}
            reportToServer('captcha:'+task['sect'], report_info)
            logging.warning('Report captcha and try again later')
            return self.makeRetryTask(task, -1)
        elif code == LOGIN_PAGE:
            now = time.time()
            path = 'login:'+task['sect']
            if path not in self.lastReportTime or now - self.lastReportTime[path] > 60:
                reportToServer(path, {'url':task['url']})
                self.lastReportTime[path] = now
            cookie = getReport('cookie:%s?del=no'%task['sect'])
            cookieStr = ''
            if len(cookie) > 0:
                for ck in cookie[0]['value']:
                    cookieStr += ck['name']+'='+ck['value']+'; '
                self.configs[task['sect']]['headers']['Cookie'] = cookieStr
            logging.warning('Login and try again later')
            return self.makeRetryTask(task, -1)
        else:
            return self.makeRetryTask(task, 3)

class LagouProcessor(LeadsProcessor):
    Header = {'Content-Type':'application/x-www-form-urlencoded',
              'Cookie':'user_trace_token=20160620115451-dae3d8feeb914fba9360b691e6ec2771; LGUID=20160620115451-bd96f6f5-369a-11e6-a3d2-5254005c3644; LGSID=20161221120311-636d2067-c732-11e6-bf98-5254005c3644; LGRID=20161221120312-6478dc9f-c732-11e6-bf98-5254005c3644'}
    def registProcessor(self):
        LeadsProcessor.registProcessor(self)
        self.processRoute['joblist'] = self.processJobList

    def beforeProcess(self, task, result):
        if task['sect'].split(':')[0] == 'lagou':
            return True
        return False

    def afterProcess(self, task, result):
        eles = result['element']
        if task['type'] != 'detail':
            return
        jobNumStr = ''.join([c for c in obj2string(eles['abstract']['jobnum']) if c>'0' and c<'9'])
        jobNum = 0
        if len(jobNumStr) > 0:
            jobNum = int(jobNumStr)
        try:
            row = Leads.select().where(Leads.website==task['url']).get()
            task['fromId'] = row.id
        except:
            return
        if 'ele' in task:
            self.processJobList(task, {'element':[task['ele']]})
            return
        #left for lagou patcher
        url = 'https://www.lagou.com/gongsi/searchPosition.json'
        tasks = []
        for i in range(1, (jobNum+9)/10+1):
            _task = task.copy()
            post = 'companyId='+str(getPageid(task['url']))+'&positionFirstType=%E5%85%A8%E9%83%A8&pageNo='+str(i)+'&pageSize=10'
            _task['post'] = post
            _task['url'] = url
            _task['header'] = self.Header
            _task['type'] = 'joblist'
            tasks.append(_task)
        return tasks

    def processJobList(self, task, result):
        sect = task['sect']
        config = self.configs[sect]
        info = {}
        logging.info('Get %s job from %s'%(len(result['element']), task['post']))
        for ele in result['element']:
            info['position'] = obj2string(ele['position'])
            info['salary'] = obj2string(ele['salary'])
            info['education'] = obj2string(ele['education'])
            info['workYear'] = obj2string(ele['workYear'])
            info['project'] = obj2string(ele['project'])
            info['city'] = obj2string(ele['city'])
            info['jobId'] = ele['jobId'][0]
            pubDate = obj2string(ele['pubDate'])
            if pubDate.find('-') < 0:
                pubDate = str(datetime.date.today())
            info['pubDate'] = pubDate
            info['fromId'] = task['fromId']
            pushInto(LagouJob, info, ['jobId'])

class QimingpianOrgProcessor(CompanyInfoProcessor):
    lastReportTime = {}
    def processListPage(self, task, result):
        element = result['element']
        preEle = None
        logging.info('Extract %s links from %s'%(len(element), task['url']))
        for ele in element:
            for key, value in ele.iteritems():
                ele[key] = obj2string(value)
                if len(ele[key]) == 0 and preEle != None:
                    ele[key] = preEle[key]
            preEle = ele
            pushInto(OrgDetail, ele, ['orgName', 'projectName'])
        
