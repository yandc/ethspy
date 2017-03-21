#!/usr/bin/env python
# coding=utf-8
from task_queue import *

class Scheduler():
    def __init__(self, interval=5):
        self.queueGroup = TaskQueueGroup(interval)
    def getTask(self, cid):
        return self.queueGroup.getTask(cid)
    def putTask(self, task):
        self.queueGroup.putTask(task)


