#!/usr/bin/env python
# coding=utf-8
import sys
import types
import urllib
import requests
from urlparse import *
from lxml import etree
import time
import datetime
import random
import logging
import json
import hashlib
import cookielib
from model import *
from gevent import subprocess
import pdb

RequestHeader = {'User-Agent':"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36"}
session = requests.Session()
cookie = cookielib.MozillaCookieJar('data/cookie.txt')
try:
    cookie.load()
    session.cookies = cookie
except Exception, e:
    pass

'''
obj: object create by json loads
jpath_map: jpath
'''
def getElementByJpathMap(obj, jpath_map):
    results = []
    xtype = type(jpath_map)

    if xtype == unicode or xtype == str:
        parts = jpath_map.split('+')
        if len(parts) > 1:
            for part in parts:
                element = getElementByJpathMap(obj, part)
                results += element
            return results
        parts = jpath_map.split('|')
        part0 = parts[0]
        if len(parts) == 1:
            if part0 == '':
                if type(obj) == list:
                    results += obj
                elif type(obj) == dict:
                    results += list(obj)
            elif type(obj) == list:
                index = int(part0)
                if len(obj) > index:
                    if type(obj[index]) != unicode or len(''.join(obj[index])) > 0:
                        results.append(obj[index])
            elif type(obj) == dict:
                if part0 in obj:
                    if type(obj[part0]) != unicode or len(''.join(obj[part0])) > 0:
                        results.append(obj[part0])
            return results
        elif len(parts) > 1:
            jpath = jpath_map[jpath_map.find('|')+1:]
            if part0 == '':
                for o in obj:
                    if type(obj) == dict:
                        o = obj[o]
                    element = getElementByJpathMap(o, jpath)
                    if len(element) > 0:
                        results += element
            elif type(obj) == list:
                index = int(part0)
                if len(obj) > index:
                    return getElementByJpathMap(obj[index], jpath)
            elif type(obj) == dict:
                if part0 in obj:
                    return getElementByJpathMap(obj[part0], jpath)
            return results
    elif xtype == dict and '_list' in jpath_map and '_piece' in jpath_map:
        node_list = getElementByJpathMap(obj, jpath_map['_list'])
        if type(node_list) != list:
            return []
        for node in node_list:
            element = getElementByJpathMap(node, jpath_map['_piece'])
            if len(element) > 0:
                results.append(element)
    elif xtype == list:
        for jpath_node in jpath_map:
            element = getElementByJpathMap(obj, jpath_node)
            if len(element) > 0:
                results.append(element)
    elif xtype == dict:
        results = {}
        for key, jpath_node in jpath_map.iteritems():
            if key == 'path_type':
                continue
            results[key] = getElementByJpathMap(obj, jpath_node)

    return results
'''
dom: return by lxml.html.fromstring()
xpath_map: string, list, dict, string is the basic xpath
list: element listed in results
dict: element
'''
def getElementByXpathMap(dom, xpath_map):
    results = []
    xtype = type(xpath_map)
    
    if xtype == unicode:
        parts = xpath_map.split('+')
        if len(parts) > 1:
            for part in parts:
                element = getElementByXpathMap(dom, part)
                results += element
            return results
        elements = dom.xpath(xpath_map)
        for ele in elements:
            text = ''
            if type(ele) != etree._Element:
                text = ele.decode()
            else:
                text = ele.text.decode()
            text = ''.join(text.split())
            if len(text) == 1:#discard special char
                c = text[0]
                if c < '0' or c > 'z' or (c > '9' and c < 'A') or (c > 'Z' and c < 'a'):
                    text = ''
            if len(text) > 0:
                results.append(text)
    elif xtype == dict and '_list' in xpath_map and '_piece' in xpath_map:
        for node in dom.xpath(xpath_map['_list']):
            element = getElementByXpathMap(node, xpath_map['_piece'])
            if len(element) > 0:
                results.append(element)
    elif xtype == list:
        for xpath_node in xpath_map:
            element = getElementByXpathMap(dom, xpath_node)
            if len(element) > 0:
                results.append(element)
    elif xtype == dict:
        results = {}
        for key, xpath_node in xpath_map.iteritems():
            if key == 'path_type':
                continue
            if type(key) != unicode:
                continue
            results[key] = getElementByXpathMap(dom, xpath_node)
            
    return results

def findMatchBracket(s, idx):
    reverse = False
    if s[idx] == '[':
        t = ']'
    elif s[idx] == '(':
        t = ')'
    elif s[idx] == '{':
        t = '}'
    elif s[idx] == '<':
        t = '>'
    elif s[idx] == ']':
        reverse = True
        t = '['
    elif s[idx] == '}':
        reverse = True
        t = '{'
    elif s[idx] == ')':
        reverse = True
        t = '('
    elif s[idx] == '>':
        reverse = True
        t = '<'
    else:
        return -1
    count = 0
    if reverse == False:
        st = s[idx:]
    else:
        st = s[:idx:-1]
    i = 0
    for c in st:
        if c == s[idx]:
            count += 1
        elif c == t:
            count -= 1
        if count == 0:
            if reverse == False:
                return idx + i
            else:
                return idx - i
        i += 1
    return -1
            
def urlEngine(startUrl):
    left = startUrl.find('[')
    if left < 0:
        yield startUrl
        return
    right = findMatchBracket(startUrl, left)
    if right < 0 or left > right:
        yield startUrl
        return
    patternStr = startUrl[left:right+1]
    exec('pattern=%s'%patternStr)
    for item in pattern:
        if type(item) == list or type(item) == xrange or type(item) == types.GeneratorType:
            for i in item:
                for url in urlEngine(startUrl[:left]+urllib.quote(str(i))+startUrl[right+1:]):
                    yield url
        else:
            if len(unicode(item)) != len(str(item)):
                strItem = urllib.quote(str(item))
            else:
                strItem = str(item)
            for url in urlEngine(startUrl[:left]+strItem+startUrl[right+1:]):
                yield url
                
def urlEngines(startUrl, startPost):
    for url in urlEngine(startUrl):
        for post in urlEngine(startPost):
            yield url, post
'''
pattern: must be a list, list item in it mean emun
'''
def urlPoller(configs, interval=10):
    engines = {}
    for sect, config in configs.iteritems():
        if type(config) == dict and 'start_url' in config:
            engines[sect] = urlEngines(config['start_url'], config['post'])
        
    while len(engines) > 0:
        nowtime = time.time()
        for sect, engine in engines.iteritems():
            try:
                url, post = engine.next()
                yield sect, url, post
            except StopIteration, e:
                del engines[sect]
                break
            except Exception, e:
                raise e

def extractElement(html, path_map):
    elements = []
    if '_before' in path_map:
        action = 'html = html.'+path_map.pop('_before')
        exec(action)
    if type(path_map) != dict or 'path_type' not in path_map or path_map['path_type'] == 'xpath':
        dom = etree.HTML(html)
        elements = getElementByXpathMap(dom, path_map)
    elif path_map['path_type'] == 'jpath':
        try:
            obj = json.loads(html)
        except:
            json_str = html.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t').replace('\b', '\\b').replace('\f', '\\f')
            obj = json.loads(json_str)
        elements = getElementByJpathMap(obj, path_map)
    elif path_map['path_type'] == 'pipe':
        content = html
        elements = {'_out':[html]}
        for pmap in path_map['_pipe']:
            assert type(pmap) == dict
            key = ''
            if '_key' in pmap:
                key = pmap.pop('_key')
            if type(elements) == list:
                for i in range(len(elements)):
                    ele = elements[i]
                    assert type(ele) == dict
                    assert '_out' in ele
                    out = ''.join(ele.pop('_out'))
                    eles = extractElement(out, pmap)
                    elements[i].update(eles)
            elif type(elements) == dict:
                out = ''.join(elements.pop('_out'))
                eles = extractElement(out, pmap)
                if type(eles) == dict:
                    elements.update(eles)
                elif type(eles) == list:
                    if key:
                        elements['key'] = eles
                    else:
                        elements = eles
    return elements

def getContent(html):
    #find charset
    charset = 'utf-8'
    try:
        doms = etree.HTML(html).xpath('//meta')
        meta = ''
        for dom in doms:
            meta += etree.tostring(dom)
        idx = meta.find('charset=')
        if idx > 0:
            idx2 =  meta[idx:].find('>')
            s = meta[idx:idx+idx2].lower()
            if s.find('utf') < 0:
                if s.find('gb') > 0:
                    charset = 'gbk'
    except:
        pass
    try:
        html = html.decode(charset)
    except:
        pass
    return html
    
def fetch(url, proxy='', header=None, post=None, dynamic=False, js='', timeout=30):
    result = {'status':None, 'url':None, 'content':None}
    try:
        header_tmp = RequestHeader.copy()
        header_tmp['Referer'] = url
        if header != None:
            header_tmp.update(header)
        if dynamic == True:
            kvargs = {'headers':header_tmp, 'url':url, 'js_script':js, 'proxy':proxy}
            if post != None:
                kvargs['data'] = post
                kvargs['method'] = 'POST'
            argstr = json.dumps(kvargs)
            if proxy != '':
                if proxy.find('@') > 0:
                    li = proxy.split('@')
                    cmd = './phantomjs --web-security=false --proxy=%s --proxy-auth=%s phantomjs.js \'%s\''%(li[1], li[0], argstr)
                else:
                    cmd = './phantomjs --web-security=false --proxy=%s phantomjs.js \'%s\''%(proxy, argstr)
            else:
                cmd = './phantomjs phantomjs.js \'%s\''%argstr
            subprocess.check_output(cmd, shell=True)
            fp = open('/tmp/phantomjs.result.'+proxy)
            obj = json.loads(fp.read())
            result['status'] = obj['status_code']
            result['content'] = obj['content']
            result['url'] = obj['url']
        else:
            request = session.get
            kwargs = {'headers':header_tmp, 'timeout':timeout}
            if post != None:
                request = session.post
                if type(post) == dict:
                    postStr = urllib.urlencode(post)
                else:
                    postStr = str(post)
                kwargs['data'] = postStr
            if proxy != '':
                if proxy.find('|') > 0:
                    kwargs['auth'] = tuple(proxy.split('@')[0].split('|'))
                    proxy = proxy.split('@')[1]
                if proxy.find('http://') < 0:
                    proxy = 'http://'+proxy
                kwargs['proxies'] = {'http':proxy, 'https':proxy}
            kwargs['verify'] = False
            resp = request(url, **kwargs)
            result['status'] = resp.status_code
            result['url'] = resp.url
            result['content'] = getContent(resp.content)
            result['resp'] = resp
            cookie.save(ignore_discard=True, ignore_expires=True)
    except Exception, e:
        if type(e) == requests.HTTPError:
            result['status'] = resp.status_code
        else:
            result['status'] = -1
        logging.error('Fetch error: %s, %s'%(str(e), url))
    return result
    
def UrlIsExist(url, checkcount=0):
    try:
        row = EthspyLog.select().where((EthspyLog.link==url) & ((EthspyLog.checkcount>=checkcount) | (EthspyLog.checkcount<-2))).get()
    except:
        return False
    return True

def getPageid(website):
    start = ['&id=', '/']
    for s in start:
        i = website.rfind(s)
        if i >= 0:
            i += len(s)
            break
    if i < 0:
        return 0
    j = i
    for c in website[i:]:
        if c < '0' or c > '9':
            break
        j += 1
    try:
        pageid = int(website[i:j])
    except Exception, e:
        pageid = 0
    return pageid


def onExist(model, row, info):
    info['checkcount'] += row.checkcount
    mdl = model(**info)
    mdl.id = row.id
    mdl.save()
    
def spyError(url):
    md5 = hashlib.md5(url).hexdigest()
    info = {'md5':md5, 'link':url, 'checkcount':-1}
    isCreate, row = pushInto(EthspyLog, info, ['md5'], onExist)
    return int(isCreate)

def spySuccess(url, eles, checkcount=1):
    md5 = hashlib.md5(str(eles)).hexdigest()
    info = {'md5':md5, 'link':url, 'checkcount':checkcount, 'eles':json.dumps(eles)}
    isCreate, row = pushInto(EthspyLog, info, ['md5'])
    return int(isCreate)

def obj2string(obj):
    s = json.dumps(obj, ensure_ascii=False)
    res = ''
    for c in s:
        if c in set(['{', '}', '[', ']', '"']):
            continue
        res += c
    return res

def getUsableKeyword(keyword):
    keys = keyword.split('/')
    res = []
    for key in keys:
        if len(str(key)) == len(key.decode()):
            continue
        testUrl = 'http://10.169.24.35/search?intersect=1&bejson=1&pagesize=1&nocdg=1&'+urllib.urlencode({'query':key})+'&ttlsearch=1&type=33'
        while True:
            try:
                search_res = json.loads(urllib.urlopen(testUrl).read())
                break
            except Exception, e:
                logging.error('Search error: %s, %s'%(str(e), testUrl))
                time.sleep(5)
        if int(search_res['matchcount']) > UNUSABLE_UPPER_BOUND:
            continue
        res.append(key)
    return res

def reportToServer(path, info):
    try:
        url = 'http://0.0.0.0:5011/ethspy/report/%s'%path
        requests.post(url, json=info)
    except Exception, e:
        logging.error('Report to server error:%s'%str(e))

def getReport(path):
    try:
        url = 'http://0.0.0.0:5011/ethspy/get_report/%s'%path
        resp = requests.get(url)
        return resp.json()
    except Exception, e:
        logging.error('Get report error')
        return []
