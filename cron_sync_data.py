# from gevent import monkey
# monkey.patch_all()
import os
import datetime
import logging
import requests
import threading
# import gevent
from functools import wraps
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.gevent import GeventScheduler
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from explorer.services.miner import MinerService
from explorer.services.overview import OverviewDayService
from explorer.services.message import TipsetGasService
from app import create_app, init_web
app = create_app()
# init_web(app)

logging.basicConfig(
    format='%(levelname)s:%(asctime)s %(pathname)s--%(funcName)s--line %(lineno)d-----%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.WARNING
)

executors = {
    'default': ThreadPoolExecutor(20),
    'processpool': ProcessPoolExecutor(5)
}

def func_log(func):
    '''
    记录操作信息
    '''

    @wraps(func)
    def wrapper(*args, **kwargs):

        thread_id = threading.get_ident()
        start_time = datetime.datetime.now()
        logging.info('[== %s ==]开始执行方法[ %s ]' % (thread_id, func.__name__))
        try:
            result = func(*args, **kwargs)
            logging.warning(result)
        except Exception as e:
            logging.exception(e)
            result = {"code": 99904, "msg": "系统错误"}
        end_time = datetime.datetime.now()
        cost_time = end_time - start_time
        logging.info('[== %s ==]方法[ %s ]执行结束，耗时[ %s ]s' % (thread_id, func.__name__, cost_time.total_seconds()))

        return result

    return wrapper


@func_log
def sync_messages_stat():
    """同步消息分页的预先处理程序"""
    return TipsetGasService.sync_messages_stat()


@func_log
def sync_miner_total_blocks():
    '''同步活跃矿工区块区块信息'''
    return MinerService.sync_miner_total_blocks()


@func_log
def sync_miner_stat():
    '''同步矿工状态'''
    return MinerService.sync_miner_stat()


@func_log
def sync_miner_day():
    '''同步矿工历史'''
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y-%m-%d')
    return MinerService.sync_miner_day(yesterday_str)


@func_log
def sync_miner_day_gas():
    '''同步矿工gas'''
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y-%m-%d')
    return MinerService.sync_miner_day_gas(yesterday_str)


@func_log
def sync_overview_day():
    '''同步每天的全网概览'''
    # 需要依赖 TipsetGas
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y-%m-%d')
    return OverviewDayService.sync_overview_day(yesterday_str)


@func_log
def sync_overview_stat():
    """
    同步每个高度的全网概览
    :return:
    """
    return OverviewDayService.sync_overview_stat()

#
#
# @func_log
# def get_pool_overview():
#     '''同步矿池概览'''
#     url = os.getenv('SERVER_DATA') + '/data/api/overview/get_pool_overview'
#     return requests.post(url=url, timeout=60, data={'must_update_cache': '1'}).json()


@func_log
def sync_overview_tipset_gas():
    '''同步单个区块gas汇总'''
    # start_height = 1200000
    # eng_height = 1300000
    height = TipsetGasService.sync_overview_tipset_gas()
    logging.info("sync_overview_tipset_gas:{}".format(height))


# @func_log
# def sync_miner_lotus():
#     '''同步链上数据'''
#     url = os.getenv('SERVER_DATA') + '/data/api/miner/sync_miner_lotus'
#     return requests.post(url=url, timeout=600).json()

# @func_log
# def sync_miner_day_overtime_pledge_fee_by_last_7days():
#     # 同步之前7日浪费质押gas
#     ret = dict()
#     today = datetime.datetime.today()
#     for i in range(1, 8):
#         date = today - datetime.timedelta(days=i)
#         date = date.strftime('%Y-%m-%d')
#         request_dict = dict(date=date)
#         url = '%s/data/api/miner/sync_miner_day_overtime_pledge_fee' % os.getenv('SERVER_DATA')
#         resp = requests.post(url=url, timeout=600, data=request_dict).json()
#         ret[date] = resp
#     return ret


# @func_log
# def sync_overtime_pledge():
#     '''计算最近的过期质押'''
#     url = os.getenv('SERVER_DATA') + '/data/api/message/sync_overtime_pledge'
#     return requests.post(url=url, timeout=600, data={}).json()


if __name__ == '__main__':
    scheduler = BlockingScheduler(timezone="Asia/Shanghai", executors=executors)
    # scheduler = GeventScheduler(timezone="Asia/Shanghai", executors=executors)

    # scheduler.add_job(func=aps_test, args=('定时任务',), trigger='cron', second='*/5')
    # scheduler.add_job(func=aps_test, args=('一次性任务',), next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=12))
    # scheduler.add_job(func=aps_test, args=('循环任务',), trigger='interval', seconds=3)
    scheduler.add_job(func=sync_miner_total_blocks, trigger='cron', minute='*/10')
    # # scheduler.add_job(func=sync_pool_miners, trigger='cron', minute='*/10')
    # scheduler.add_job(func=sync_miner_day_stat, trigger='cron', hour=2, minute=35)

    scheduler.add_job(func=sync_messages_stat, trigger='cron', minute='*/4')
    scheduler.add_job(func=sync_miner_stat, trigger='cron', minute='*/10')
    scheduler.add_job(func=sync_miner_day, trigger='cron', hour=2, minute=10)
    scheduler.add_job(func=sync_miner_day_gas, trigger='cron', hour=3, minute=40)
    # # scheduler.add_job(func=sync_miner_day_overtime_pledge_fee, trigger='cron', hour=7, minute=10)  # 同步每日浪费质押gas
    scheduler.add_job(func=sync_overview_day, trigger='cron', hour=0, minute=50)
    scheduler.add_job(func=sync_overview_stat, trigger='cron', minute='*/6')
    scheduler.add_job(func=sync_overview_tipset_gas, trigger='cron', minute='*/5')
    # scheduler.add_job(func=sync_overtime_pledge, trigger='cron', minute='*/10')
    # scheduler.add_job(func=sync_deal, trigger='cron', minute='*/30')
    # scheduler.add_job(func=sync_explorer_index, trigger='cron', hour=1, minute=45)  # 计算浏览器昨日指数
    # scheduler.add_job(func=sync_miner_tag, trigger='interval', seconds=60 * 60 * 6)  # 更新浏览器标签
    # scheduler.add_job(func=sync_explorer_fil_index_0, trigger='cron', hour=0, minute=1)  # 计算fil昨日指数
    # scheduler.add_job(func=sync_explorer_fil_index_8, trigger='cron', hour=8, minute=1)  # 计算fil昨日指数
    # scheduler.add_job(func=sync_miner_lotus, trigger='cron', hour=5, minute=1)

    scheduler.start()
    # g.join()
