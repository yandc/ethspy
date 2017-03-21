#!/usr/bin/env python
# coding=utf-8
from AlgoCommonLib.orm_util import *

MonitorLog = getOrmModel('newsdb','monitor_log')
EthspyLog = getOrmModel('newsdb', 'ethspylog')
Leads = getOrmModel('newsdb', 'project_leads')
Investor = getOrmModel('newsdb', 'investor')
Investment = getOrmModel('newsdb', 'investment')
Organization = getOrmModel('newsdb', 'organization')
LagouJob = getOrmModel('newsdb', 'lagou_job')
OrgDetail = getOrmModel('newsdb', 'qimingpian_orgdetail')
ComInfo = getOrmModel('project', 'company_info')
ComChange = getOrmModel('project', 'company_change')
ComHolder = getOrmModel('project', 'company_holder')
ComManager = getOrmModel('project', 'company_manager')

BaseProject = getOrmModel('project', 'base_project')

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

