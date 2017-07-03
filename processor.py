#!/usr/bin/env python
# coding=utf-8
from ethspy import *
import sys
import os
import pdb

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

            for link in ele['link']:
                link = str(link)
                post = None
                if len(config['link_format']) > 0:
                    link = config['link_format']%(link)
                elif link[:4].lower() != 'http':
                    net0 = 'http'
                    net = urlparse(link)
                    net1 = net[1]
                    if not net1:
                        net1 = urlparse(url)[1]
                    link = net0 + '://' + net1 + ''.join(net[2:])
                link = link.replace('https://', 'http://')
                post = None
                part = link.split(';+post=')
                if len(part) > 1:
                    link = part[0]
                    post = part[1]
                if config['update'] == False and UrlIsExist(link):
                    continue
                tasks.append({'sect':sect, 'type':'detail', 'url':link, 'post':post, 'ele':ele})
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
        fp = open('data/'+sect+'.csv', 'a')
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
        
class MiaArticleProcessor(CrawlerProcessor):
    context = {
        '52ce1c02b4c4d649b58b8930':{'catgy':u'彩妆', 'keyword':u'综合'},
        '5590c45c15ff00d961fd14e8':{'catgy':u'美妆护肤', 'keyword':u'综合'},
        '52ce1c02b4c4d649b58b892c':{'catgy':u'护肤', 'keyword':u'综合'},
        '52ce1c02b4c4d649b58b8936':{'catgy':u'母婴', 'keyword':u'综合'},
        'momoso':{'catgy':u'海淘综合', 'keyword':u'app-晒衣橱'},
        'biyabi':{'catgy':u'海淘综合', 'keyword':u'app-逛晒单'},
        'vmei':{'catgy':u'美妆', 'keyword':u'全部'},
        'ymatou':{'catgy':u'全球代购', 'keyword':u'全部'},
        'dealmoon':{'catgy':u'全球代购', 'keyword':u'全部'},
        'wx':{'catgy':u'时尚穿搭护肤美妆', 'keyword':u''},
        u'wx:时尚旅游':{'catgy':u'家居生活', 'keyword':u'公众号'},
        u'wx:gogoboi':{'catgy':u'时尚穿搭', 'keyword':u'公众号'},
        u'wx:置爱':{'catgy':u'家居生活', 'keyword':u'公众号'},
        u'wx:时尚家居':{'catgy':u'家居生活', 'keyword':u'公众号'},
        u'wx:悦己SELF':{'catgy':u'时尚穿搭', 'keyword':u'公众号'},
        u'wx:时尚健康':{'catgy':u'家居生活', 'keyword':u'公众号'},
        u'wx:深夜种草':{'catgy':u'美妆护肤', 'keyword':u'公众号'},
        u'wx:在家ZAIJIA':{'catgy':u'家居生活', 'keyword':u'公众号'},
        u'wx:原来是西门大嫂':{'catgy':u'海淘综合', 'keyword':u'公众号'},
        u'wx:文怡家常菜':{'catgy':u'家居生活', 'keyword':u'公众号'},
        u'wx:宝宝餐餐见':{'catgy':u'宝宝喂养', 'keyword':u'公众号'},
        u'wx:剁手公主':{'catgy':u'美妆护肤', 'keyword':u'公众号'},
        u'wx:年糕妈妈':{'catgy':u'母婴综合', 'keyword':u'公众号'},
        u'wx:健康与美容':{'catgy':u'美妆护肤', 'keyword':u'公众号'},
        u'wx:日本淘':{'catgy':u'美妆护肤', 'keyword':u'公众号'},
        u'wx:女神进化论':{'catgy':u'美妆护肤', 'keyword':u'公众号'},
        u'weibo:种草囤货少女':{'catgy':u'美妆护肤', 'keyword':u'美妆'},
        u'weibo:北美省钱快报':{'catgy':u'全球代购', 'keyword':u'综合'},
        u'weibo:我是种草囤货菌':{'catgy':u'综合', 'keyword':u'综合'},
        u'weibo:种草达人绵绵酱':{'catgy':u'综合', 'keyword':u'综合'},
        u'weibo:化妆miuo的微博':{'catgy':u'美妆护肤', 'keyword':u'美妆'},
        u'weibo:各国美食学起来YOU':{'catgy':u'家居生活', 'keyword':u'综合'},
        u'weibo:买买菌':{'catgy':u'综合', 'keyword':u''},
        u'weibo:美妆第一线':{'catgy':u'美妆护肤', 'keyword':u''},
        u'weibo:化了个妆':{'catgy':u'美妆护肤', 'keyword':u''},
        u'weibo:潮美妆君':{'catgy':u'美妆护肤', 'keyword':u''},
        u'weibo:顶尖化妆教程':{'catgy':u'美妆护肤', 'keyword':u''},
        u'weibo:美容护肤show':{'catgy':u'美妆护肤', 'keyword':u''},
        u'weibo:长颈鹿酱刷睫毛':{'catgy':u'美妆护肤', 'keyword':u''},
        u'weibo:时尚编辑Anna':{'catgy':u'时尚穿搭', 'keyword':u''},
        u'weibo:宝宝美食大本营':{'catgy':u'宝宝喂养', 'keyword':u''},
        u'weibo:宝宝辅食营养攻略':{'catgy':u'宝宝喂养', 'keyword':u''},
        u'weibo:美味宝宝辅食':{'catgy':u'宝宝喂养', 'keyword':u''},
        u'weibo:萌煮辅食':{'catgy':u'宝宝喂养', 'keyword':u''},
        u'weibo:宝宝辅食跟我学':{'catgy':u'宝宝喂养', 'keyword':u''},
        u'weibo:潮宝宝穿搭顾问':{'catgy':u'童装童鞋', 'keyword':u''},
        u'weibo:宝宝穿衣会搭配':{'catgy':u'童装童鞋', 'keyword':u''},
        u'weibo:做衣服的酱妈':{'catgy':u'童装童鞋', 'keyword':u''},
        u'weibo:宝宝衣物穿搭日志':{'catgy':u'童装童鞋', 'keyword':u''},
        u'weibo:i潮童':{'catgy':u'童装童鞋', 'keyword':u''},
        u'weibo:因淘优品':{'catgy':u'母婴综合', 'keyword':u''},
        u'weibo:Cemarose':{'catgy':u'童装童鞋', 'keyword':u''},
        u'weibo:爱上创意家居':{'catgy':u'家居生活', 'keyword':u''},
        u'weibo:DIY设计我的家':{'catgy':u'家居生活', 'keyword':u''},
        u'55bbs:【丽人妆颜】':{'catgy':u'美妆护肤', 'keyword':u'论坛帖子'},
        u'55bbs:【孕宝亲子】':{'catgy':u'孕宝亲子', 'keyword':u'论坛帖子'},
        u'meishai:晒护肤':{'catgy':u'美妆护肤', 'keyword':u'晒护肤'},
        u'meishai:晒彩妆':{'catgy':u'彩妆', 'keyword':u'晒彩妆'},
        u'meishai:晒服装':{'catgy':u'时尚穿搭', 'keyword':u'晒服装'},
        u'meishai:晒鞋子':{'catgy':u'美妆护肤', 'keyword':u'晒鞋子'},
        u'meishai:晒包包':{'catgy':u'美妆护肤', 'keyword':u'晒包包'},
        u'meishai:晒配饰':{'catgy':u'美妆护肤', 'keyword':u'晒配饰'},
        u'meishai:晒家居日用':{'catgy':u'家居生活', 'keyword':u'晒家居日用'},
        u'yidoutang:全屋记':{'catgy':u'家居生活', 'keyword':u'全屋记'},
        u'yidoutang:达人悦':{'catgy':u'家居生活', 'keyword':u'达人悦'},
        u't100':{'catgy':u'童装童鞋', 'keyword':u'童装'},
        u'cloudokids:婴儿':{'catgy':u'童装童鞋', 'keyword':u'婴儿'},
        u'cloudokids:女孩':{'catgy':u'童装童鞋', 'keyword':u'女孩'},
        u'cloudokids:男孩':{'catgy':u'童装童鞋', 'keyword':u'男孩'},
        u'cloudokids:童鞋':{'catgy':u'童装童鞋', 'keyword':u'童鞋'},
        u'cloudokids:玩具&礼物':{'catgy':u'童装童鞋', 'keyword':u'玩具-礼物'},
        u'xiaohongshu:童装':{'catgy':u'童装童鞋', 'keyword':u'童装'},
        u'zintao:晒物':{'catgy':u'综合', 'keyword':u'晒物'},
        u'zintao:乐活':{'catgy':u'家居生活', 'keyword':u'乐活'},
        u'zintao:育儿':{'catgy':u'母婴综合', 'keyword':u'育儿'},
        u'zintao:辣妈厨房':{'catgy':u'家居生活', 'keyword':u'辣妈厨房'},
        u'zintao:其他':{'catgy':u'综合', 'keyword':u'其他'},
        u'pcbaby:辅食评测':{'catgy':u'宝宝食品', 'keyword':u'辅食评测'},
        u'pcbaby:日用品评测':{'catgy':u'宝宝食品', 'keyword':u'日用品评测'},
        u'sougou:玩具清单':{'catgy':u'宝宝玩具', 'keyword':u'玩具清单'},
        u'sougou:宝宝餐具评测':{'catgy':u'宝宝喂养', 'keyword':u'宝宝餐具评测'},
        u'sougou:宝宝奶瓶评测':{'catgy':u'宝宝喂养', 'keyword':u'宝宝奶瓶评测'},
        u'sougou:宝宝辅食':{'catgy':u'宝宝辅食', 'keyword':u'宝宝辅食'},
        u'sougou:玩具辅食评测':{'catgy':u'宝宝食品', 'keyword':u'宝宝辅食评测'},
        u'sougou:绘本推荐':{'catgy':u'宝宝绘本', 'keyword':u'绘本推荐'},
        u'sougou:玩具推荐':{'catgy':u'宝宝玩具', 'keyword':u'玩具推荐'},
        u'sougou:儿童玩具评测':{'catgy':u'宝宝玩具', 'keyword':u'儿童玩具评测'},
        u'sougou:宝宝零食推荐':{'catgy':u'宝宝食品', 'keyword':u'宝宝零食推荐'},
        u'sougou:宝宝零食推荐':{'catgy':u'宝宝食品', 'keyword':u'宝宝零食推荐'},
        u'nggirl':{'catgy':u'美妆护肤', 'keyword':u'南瓜姑娘'},
        u'app887':{'catgy':u'美妆护肤', 'keyword':u'化妆技巧'},
        u'zhefengle':{'catgy':u'海淘综合', 'keyword':u'菌团-精选'},
        u'diywoju':{'catgy':u'家居生活', 'keyword':u'蜗居创意家居生活馆'},
        u'mglife':{'catgy':u'家居生活', 'keyword':u'家居生活'},
        u'lofter':{'catgy':u'化妆护肤', 'keyword':u'好物分享笔记'},
        u'truebuty':{'catgy':u'美妆', 'keyword':u'真魅博客'},
        u'diaox2':{'catgy':u'家居生活', 'keyword':u'有调'}
    }
    def registProcessor(self):
        CrawlerProcessor.registProcessor(self)
        self.processRoute['list1'] = self.processList1Page
        self.processRoute['list2'] = self.processList2Page

    def processList1Page(self, task, result):
        tasks = self.processListPage(task, result)
        for tk in tasks:
            if task['sect'][:6] == 'pclady':
                prefix = 'http://cosme.pclady.com.cn/product/'
                pid = tk['url'][len(prefix):-5]
                if 'page' not in tk:
                    tk['page'] = 1
                if 'pid' not in tk:
                    tk['pid'] = pid
                if 'urlFormat' not in tk:
                    tk['urlFormat'] = 'http://cosme.pclady.com.cn/common/2013/solr_comment_list.jsp?&pageType=1&id=%s&status=2&type=4&pageNum=%s'
                tk['url'] = tk['urlFormat']%(pid, tk['page'])
                tk['type'] = 'list2'
            else:
                tk['url'] += '1_1.html'
                tk['type'] = 'list2'
                del tk['ele']
        return tasks
    
    def processList2Page(self, task, result):
        tasks = self.processListPage(task, result)
        for tk in tasks:
            if task['sect'][:6] == 'pclady':
                if len(tasks) == 10:
                    task['page'] += 1
                    task['url'] = task['urlFormat']%(task['pid'], task['page'])
                    tasks.append(task)
            else:
                tk['type'] = 'list'
                tk['url'] += '1/1/'
                del tk['ele']
        return tasks
    
    def beforeProcess(self, task, result):
        eles = result['element']
        sect = task['sect']
        if sect == 'vmei' and task['type'] == 'list':
            for ele in eles:
                for i in range(len(ele['pics'])):
                    ele['pics'][i] = "https://img06.sephome.com/" + ele['pics'][i]
        elif sect == 'dealmoon' and task['type'] == 'list':
            for ele in eles:
                link = ele['link'][0]
                idx = link.rfind('/')
                ele['link'][0] = link[idx+1:].replace('?', '&')
        elif sect == '55bbs' and task['type'] == 'list':
            for ele in eles:
                link1 = ele.pop('link1')[0]
                link2 = ele.pop('link2')[0]
                idx = link1[7:].find('-')
                tid = link1[7:][:idx]
                idx = link2.rfind('-')
                uid = link2[idx+1:][:-5]
                ele['link'] = ['http://bbs.55bbs.com/viewthread.php?tid=%s&page=1&authorid=%s'%(tid, uid)]
        elif sect == 'zintao' and task['type'] == 'list':
            for ele in eles:
                pics = []
                for pic in ele['pics']:
                    pics.append('http://image.zintao.com/Attachment/'+pic)
                ele['pics'] = pics
        elif sect == 'pcbaby' and task['type'] == 'list':
            for ele in eles:
                links = []
                for link in ele['link']:
                    links.append(link[:-5]+'_all.html')
                ele['link'] = links
        elif sect == 'ikea' and task['type'] == 'detail':
            for i, pic in enumerate(eles['pics']):
                eles['pics'][i] = 'http://www.ikea.com'+pic
        elif sect == 'xiachufang' and task['type'] == 'detail':
            for i, pic in enumerate(eles['pics']):
                idx = pic.find('.jpg')
                if idx > 0:
                    eles['pics'][i] = pic[:idx+4]
        elif sect == 'nggirl' and task['type'] == 'detail':
            textli = []
            picli = []
            for i, ele in enumerate(eles['pics']):
                if ele.find('http') == 0:
                    picli.append(ele)
                if eles['text'][i].find('http') != 0:
                    textli.append(eles['text'][i])
            eles['pics'] = picli
            eles['text'] = textli
        elif task['type'] == 'detail':
            CrawlerProcessor.beforeProcess(self, task, result)
        return True
    
    def onBroken(self, task, result, code=FAIL_PAGE):
        logging.info('%s:(%s) %s'%(code, result['status'], task['url']))
        self.monitor.error(task, result, code)
        if result['status'] == 404 or result['status'] == 500:
            spyError(task['url'])
            return []
        elif code == EMPTY_LIST:
            return []
        else:
            return self.makeRetryTask(task, 3)
        
    def processDetailPage(self, task, result):
        ele = result['element']
        sect = task['sect']
        config = self.configs[sect]
        if 'srcId' not in ele:
            ele['srcId'] = task['url']
        fakeUrl = sect+'//'+obj2string(ele['srcId'])
        if sect == 'wx':
            if len(ele['title']) == 0 or len(ele['pics']) == 0:
                return self.onBroken(task, result, EMPTY_KEYWORD)
        ret = spySuccess(fakeUrl, ele)
        if ret == 1:#need insert or update
            if 'source' in ele:
                ele['source'] = sect+':'+obj2string(ele['source'])
            else:
                ele['source'] = sect.decode()
            if 'title' in ele:
                logging.info('Get article %s'%''.join(ele['title']))
                ele['title'] = json.dumps(','.join(ele['title']))
            if 'tag' in ele:
                ele['tag'] = obj2string(ele['tag'])
            #emoji char truncated, and mysql 5.1=>5.5 Fail, SB
            if 'text' in ele:
                ele['text'] = json.dumps(ele['text'])
            if sect[:5] == 'weibo':
                imgs = []
                for pic in ele['pics']:
                    idx1 = pic.rfind('/')
                    idx2 = pic[:idx1].rfind('/')
                    pic = pic[:idx2]+'/mw690'+pic[idx1:]
                    imgs.append(pic)
                ele['pics'] = imgs
            elif sect[:4] == 't100':
                imgs = []
                for pic in ele['pics']:
                    idx = pic.rfind('_')
                    pic = pic[:idx]
                    imgs.append(pic)
                ele['pics'] = imgs
            ele['pics'] = json.dumps(ele['pics'])
            ele['srcId'] = obj2string(ele['srcId'])
            if 'brand' in ele:
                ele['brand'] = obj2string(ele['brand'])
            if 'date' in ele:
                ele['date'] = obj2string(ele['date'])
            if sect == 'xiaohongshu':
                ele.update(self.context[task['url'][-24:]])
            elif ele['source'] in self.context:
                ele.update(self.context[ele['source']])
            ele['status'] = 'INIT'

            pushInto(Article, ele, ['source', 'srcId'])

    def afterProcess(self, task, result):
        tasks = []
        if 'page' not in task:
            task['page'] = 0
        task['page'] += 1
        if task['page'] > 10:
            return tasks

        if task['sect'][:11] == 'xiaohongshu' and len(result['element']) > 0:
            ele = result['element']
            url = task['url']
            idx = url.find('&oid')
            url = '%s&start=%s&num=40%s'%(url[:idx], ele[-1]['srcId'][0], url[idx:])
            task['url'] = url
            tasks.append(task)
        elif task['sect'] == 'wx' and task['type'] == 'list':
            listLength = 12
            if len(result['element']) < listLength:
                return tasks
            url = task['url']
            if 'offset' not in task:
                task['offset'] = 0
                url += '?start=0'
            task['offset'] += listLength
            idx = url.rfind('=')
            task['url'] = url[:idx+1] + str(task['offset'])
            tasks.append(task)
        return tasks

class LinkDownloadProcessor(Processor):
    def onBroken(self, task, result, code=FAIL_PAGE):
        logging.info('%s:(%s) %s'%(code, result['status'], task['url']))
        tbname = self.srcModel._meta.db_table
        pushInto(LinkMap, {'type':tbname, 'fromLink':task['url'], 'status':code, 'source':task['sect'], 'srcId':task['id']})
        pushInto(Article, {'id':task['id'], 'status':'BROKEN'}, ['id'])
        return []
    
    def registProcessor(self):
        self.processRoute['download'] = self.processDownload

    def processDownload(self, task, result):
        try:
            if not os.path.exists(task['path']):
                os.mkdir(task['path'])
            path = task['path']+task['name']
            fp = open(path, 'w')
            fp.write(result['content'])
            fp.close()
        except Exception, e:
            pdb.set_trace()
            logging.error(str(e))
        tbname = self.srcModel._meta.db_table
        pushInto(LinkMap, {'type':tbname, 'fromLink':task['url'], 'toLink':path, 'status':SUCC_PAGE, 'source':task['sect'], 'srcId':task['id']})

class AvatarProcessor(CrawlerProcessor):
    context = {
        '/528576/':u'母婴综合',
        '/586674/':u'综合',
        '/10036/':u'美妆护肤',
        '/Appearance/':u'时尚穿搭',
        '/chaneldior/':u'美妆护肤',
        '/204251/':u'美妆护肤',
        '/blackeye/':u'母婴综合'
    }
    def processDetailPage(self, task, result):
        ele = result['element']
        pic = ele['pic'][0]
        if not pic or 'user_normal' in pic:
            return
        idx = pic.rfind('/') + 2
        pic = pic[:idx] + 'l' + pic[idx:]
        try:
            mdl = Avatar.select().where(Avatar.pic==pic).get()
            return
        except:
            pass
        name = obj2string(ele['name'])
        catgy = ''
        for key in self.context:
            if key in task['url']:
                catgy = self.context[key]
                break
        pushInto(Avatar, {'source':task['sect'], 'pic':pic, 'name':name, 'catgy':catgy})


class PriceProcessor(CrawlerProcessor):
    def onBroken(self, task, result, code=FAIL_PAGE):
        logging.info('%s:(%s) %s'%(code, result['status'], task['url']))
        if result['status'] == 404 or result['status'] == 500:
            return []
        else:
            return self.makeRetryTask(task, 3)
        
    def processDetailPage(self, task, result):
        sect = task['sect']
        eles = result['element']
        title = ''.join(eles['title']).replace(',', '，')
        price = ''.join(eles['price']).replace(',', '').replace('￥','').replace('¥', '')
        if not price:
            return
        kwds = [line.replace('\n','').replace('\r','') for line in open('config/keyword.csv')]
        keyword = ''
        for kwd in kwds:
            q = urllib.quote(kwd)
            if q in task['url'] or (task['post'] and q in task['post']):
                keyword = kwd
                break
        keyword = keyword.replace(',','，')
        output = '%s,%s,%s,%s,%s\r\n'%(task['sect'], price, title, keyword, time.strftime('%Y-%m-%d %H:%M:%S'))
        fp = open('data/result.csv', 'a')
        fp.write(output.encode('gbk'))
        fp.close()
        logging.info('Get price from %s'%task['url'])

class FlowswapProcessor(CrawlerProcessor):
    def processListPage(self, task, result):
        timeStr = time.strftime('%H:%M')
        freqZone = [('10:00','11:00', 1), ('15:30','16:30', 1)]
        hit = False
        for tzone, freq in freqZone:
            if timeStr > tzone[0] and timeStr < tzone[1]:
                hit = True
                time.sleep(freq)
                break
        if not hit:
            time.sleep(20)
        if 'flowCount' not in task:
            task['flowCount'] = 0
        task['flowCount'] += 1
        if task['flowCount'] % 100 == 0:
            logging.info('Flow swap count %s'%task['flowCount'])
        return task
            
class ReportProcessor(CsvProcessor):
    def beforeProcess(self, task, result):
        eles = result['element']
        for ele in eles:
            ts = int(ele['time'][0])/1000
            dt = datetime.datetime.fromtimestamp(ts)
            ele['time'][0] = dt.strftime('%Y-%m-%d')
            ele['path'][0] = 'http://www.cninfo.com.cn/'+ele['path'][0]
