#!/usr/bin/env python
# coding=utf-8
from orm_util import *

BaseProject = None
Leads = None
MonitorLog = getOrmModel('material','monitor')
EthspyLog = getOrmModel('material', 'spylog')
Article = getOrmModel('material', 'article')
Offset = getOrmModel('material', 'offset')
Links = getOrmModel('material', 'links')
LinkMap = getOrmModel('material', 'linkmap')
Avatar = getOrmModel('material', 'avatar')
Know = getOrmModel('material', 'knowledge')

def pushInto(model, info, where=[], fnOnExist=None):
    if len(where) == 0:
        mdl = model(**info)
        mdl.save()
        return True, mdl
    kwargs = {'defaults':info}
    for field in where:
        kwargs[field] = info[field]

    row, isCreate = model.get_or_create(**kwargs)
    if isCreate == False:
        if fnOnExist != None:
            fnOnExist(model, row, info)
        else:
            mdl = model(**info)
            mdl.id = row.id
            mdl.save()
    return isCreate, row

