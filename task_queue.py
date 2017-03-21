#!/user/bin/env python
# coding=utf-8
import gevent
from gevent.queue import Queue
import time
import random

class TaskQueue():
    def __init__(self, interval=5):
        self.taskQueue = gevent.queue.Queue()
        self.interval = interval
        self.lastGetTime = {}
        self.lastAccessTime = 0
        
    def putTask(self, task):
        self.taskQueue.put(task)
        
    def getTask(self, cid):
        if self.taskQueue.empty():
            return None
        
        last = 0
        now = time.time()
        if cid in self.lastGetTime:
            last = self.lastGetTime[cid]
        else:
            self.lastGetTime[cid] = now
            
        diff = now - last
        if diff < self.interval:#ip limit
            gevent.sleep(self.interval-diff)
        diff = now - self.lastAccessTime
        if diff < 1:#queue limit
            gevent.sleep(0.2-diff)
            
        self.lastGetTime[cid] = time.time()
        self.lastAccessTime = time.time()
        if self.taskQueue.empty():#may consume out by other cid
            return None
        return self.taskQueue.get()

    def empty(self):
        return self.taskQueue.empty()

class TaskQueueGroup():
    def __init__(self, interval):
        self.interval = interval
        self.queueGroup = {}
        
    def putTask(self, task):
        if type(task) != dict or 'sect' not in task:
            sect = 'default'
        else:
            sect = task['sect'].split(':')[0]
        if sect not in self.queueGroup:
            self.queueGroup[sect] = TaskQueue(self.interval)
        self.queueGroup[sect].putTask(task)
        
    def getTask(self, cid):
        sectList = [x for x in self.queueGroup]
        random.shuffle(sectList)
        for sect in sectList:
            taskQueue = self.queueGroup[sect]
            task = taskQueue.getTask(cid)
            if task != None:
                return task
        return None
