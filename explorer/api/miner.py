import datetime,json
from flask import request
from explorer.services.miner import MinerService
from base.response import response_json
from base.utils.fil import _d, bson_to_decimal
import pandas as pd

def sync_miner_total_blocks():
    """
    统计每个miner的出块汇总
    :return:
    """
    MinerService.sync_miner_total_blocks()
    return response_json(True)


def sync_miner_stat():
    """
    同步miner24小时信息
    :return:
    """
    MinerService.sync_miner_stat()
    return response_json(True)


def sync_miner_day():
    """
    同步miner24小时信息
    :return:
    """
    # datetime.date.today()
    # yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    # yesterday_str = yesterday.strftime('%Y-%m-%d')
    date_str = request.form.get("date_str")
    MinerService.sync_miner_day(date_str)
    return response_json(True)


def sync_miner_day_gas():
    """
    统计miner——day的gas信息
    :return:
    """
    now_str = (datetime.datetime.now()-datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    tables = pd.date_range('2021-1-03', now_str, freq='D').strftime("%Y-%m-%d").tolist()
    tables.reverse()
    for date_str in tables:
        MinerService.sync_miner_day_gas(date_str)
        print(date_str)
    return response_json(True)


def get_miners_by_address():
    """
    通过账户查询所属节点
    :return:
    """
    address = request.form.get("address")
    result = MinerService.get_miners_by_address(address)
    return response_json(result)


def get_miner_ranking_list():
    """
    首页排行榜
    :return:
    """
    stats_type = request.form.get("stats_type")
    sector_type = request.form.get("sector_type")
    filter_type = request.form.get("filter_type")
    miner_no_list = json.loads(request.form.get('miner_no_list', '[]'))
    page_index = int(request.form.get('page_index', 1))
    page_size = min(int(request.form.get('page_size', 10)), 50)
    miner_no_dict, data = MinerService.get_miner_ranking_list(stats_type, filter_type, sector_type, miner_no_list,
                                                              page_index=page_index, page_size=page_size)
    miner_data = []
    for miner_day in data['objects']:
        miner_no = miner_day.get("miner_no") or miner_day["_id"]
        if "increase_power" == filter_type:
            tmp = dict(miner_no=miner_no, increase_power=bson_to_decimal(miner_day["increase_power"]),
                       increase_power_offset=bson_to_decimal(miner_day["increase_power_offset"]))
        if "avg_reward" == filter_type:
            tmp = dict(miner_no=miner_no, avg_reward=bson_to_decimal(miner_day["avg_reward"]))
        if "block_count" == filter_type:
            tmp = dict(miner_no=miner_no, win_count=miner_day["win_count"], lucky=bson_to_decimal(miner_day["lucky"],4),
                       block_reward=bson_to_decimal(miner_day["block_reward"]))
        tmp.update(miner_no_dict.get(miner_no))
        miner_data.append(tmp)
    data["objects"] = miner_data
    return response_json(data)


def get_miner_ranking_list_by_power():
    """
    首页算力排行榜
    :return:
    """
    sector_type = request.form.get("sector_type")
    miner_no_list = json.loads(request.form.get('miner_no_list', '[]'))
    page_index = int(request.form.get('page_index', 1))
    page_size = min(int(request.form.get('page_size', 10)), 50)
    data = MinerService.get_miner_ranking_list_by_power(sector_type=sector_type, miner_no_list=miner_no_list,
                                                        page_index=page_index, page_size=page_size)
    return response_json(data)


def get_miner_by_no():
    """
    存储提供者详情
    :return:
    """
    miner_no = request.form.get("miner_no")
    data = MinerService.get_miner_by_no(miner_no)
    return response_json(data)


def get_miner_stats_by_no():
    """
    存储提供者产出统计
    :return:
    """
    miner_no = request.form.get("miner_no")
    stats_type = request.form.get("stats_type", "24h")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    data = MinerService.get_miner_stats_by_no(miner_no, stats_type, start_date, end_date)
    return response_json(data)


def get_miner_gas_stats_by_no():
    """
    存储提供者成本统计
    :return:
    """
    miner_no = request.form.get("miner_no")
    stats_type = request.form.get("stats_type", "24h")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    data = MinerService.get_miner_gas_stats_by_no(miner_no, stats_type, start_date, end_date)
    return response_json(data)


def get_miner_line_chart_by_no():
    """
   存储提供者的算力变化和出块统计24/30/180
    :return:
    """
    miner_no = request.form.get("miner_no")
    stats_type = request.form.get("stats_type", "24h")
    data = MinerService.get_miner_line_chart_by_no(miner_no, stats_type)
    return response_json(data)
