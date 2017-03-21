#!/usr/bin/env python
# coding=utf-8
from model import *
from lxml import etree

class Monitor():
    def __init__(self, spider):
        self.info = {'spider':spider}
        self.stat = {}
    def error(self, task, result, code):
        self.info['source'] = task['sect']
        self.info['taskType'] = task['type']
        self.info['errorCode'] = code
        self.info['url'] = task['url']
        if task['post']:
            self.info['post'] = task['post']
        self.info['proxy'] = task['proxy']
        self.info['status'] = result['status']
        if result['content']:
            dom = etree.HTML(result['content'])
            self.info['content'] = ''.join((ss for ss in dom.xpath('//text()') if len(str(ss)) != len(unicode(ss))))
        pushInto(MonitorLog, self.info)

    def count(self, task):
        sect = task['sect']
        if sect not in self.stat:
            self.stat[sect] = {}
        if task['type'] not in self.stat[sect]:
            self.stat[sect][task['type']] = 0
        self.stat[sect][task['type']] += 1

    def clean(self):
        for k1 in self.stat:
            for k2 in self.stat[k1]:
                self.info['source'] = k1
                self.info['taskType'] = k2
                self.info['errorCode'] = 'Count'
                self.info['status'] = self.stat[k1][k2]
                pushInto(MonitorLog, self.info)
