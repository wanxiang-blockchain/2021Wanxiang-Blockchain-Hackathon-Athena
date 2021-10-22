import datetime, os, sys
from explorer.models.message import MigrateLog
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(BASE_DIR))
from xm_s_common import inner_server
from bson.decimal128 import Decimal128
from pymongo import UpdateOne
from base.utils.fil import _d
from mongoengine.connection import get_db
import pandas as pd


class PreProcess:
    def __init__(self, app):
        self.process_data(app)

    @classmethod
    def process_data(cls, app):
        # now_day = datetime.datetime.now().strftime("%Y-%m-%d")
        # miner_day = MinerDay.objects().order_by("date").first()
        # if miner_day:
        #     now_day = miner_day.date
        # date = datetime.datetime.strptime(now_day, "%Y-%m-%d")
        # while date > datetime.datetime.strptime("2021-01-03", "%Y-%m-%d"):
        #     date = date - datetime.timedelta(days=1)
        now_str = (datetime.datetime.now() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        tables = pd.date_range('2021-1-03', now_str, freq='D').strftime("%Y-%m-%d").tolist()
        tables.reverse()
        for date_str in tables:
            print(date_str)
            cls.get_history_miner_value(date_str)

    @classmethod
    def get_history_miner_value(cls, date):
        """
        获得历史的矿工产出记录
        :param date: 历史数据日期
        :return:
        """
        i = 1
        miner_days = []
        while True:
            result = inner_server.get_miner_day_records({"page_size": 100, "page_index": i, "date": date})
            # 保存数据
            for miner_info in result['data']['objs']:
                miner_day = UpdateOne({"miner_no": miner_info.get("miner_no"), "date": date},
                                      {"$set": dict(
                                          actual_power=Decimal128(miner_info.get("power")),
                                          raw_power=Decimal128(miner_info.get("raw_power")),
                                          sector_size=int(miner_info.get("sector_size")),
                                          sector_all=int(miner_info.get("total_sector")),
                                          sector_effect=int(miner_info.get("active_sector")),
                                          total_balance=Decimal128(miner_info.get("balance")),
                                          available_balance=Decimal128(miner_info.get("available_balance")),
                                          # pledge_balance=miner.pledge_balance,
                                          initial_pledge_balance=Decimal128(miner_info.get("initial_pledge_balance")),
                                          locked_balance=Decimal128(miner_info.get("locked_pledge_balance")),
                                          total_reward=Decimal128(miner_info.get("total_reward")),
                                          total_block_count=int(miner_info.get("total_block_count")),
                                          total_win_count=int(miner_info.get("total_win_count")),
                                          increase_power=Decimal128(miner_info.get("increase_power")),
                                          increase_power_offset=Decimal128(miner_info.get("increase_power_offset")),
                                          block_reward=Decimal128(miner_info.get("block_reward")),
                                          avg_reward=Decimal128(_d(miner_info.get("avg_reward")) * _d(10**18)),
                                          win_count=int(miner_info.get("win_count")),
                                          block_count=int(miner_info.get("block_count")),
                                          lucky=Decimal128(miner_info.get("lucky")),
                                          pre_gas = Decimal128(miner_info.get("pre_gas")),
                                          pre_gas_count=int(miner_info.get("pre_gas_count")),
                                          prove_gas=Decimal128(miner_info.get("prove_gas")),
                                          prove_gas_count=int(miner_info.get("prove_gas_count")),
                                          win_post_gas=Decimal128(miner_info.get("win_post_gas")),
                                          win_post_gas_count=int(miner_info.get("win_post_gas_count") or 0),
                                          pledge_gas=Decimal128(miner_info.get("pledge_gas")),
                                      )},
                                      upsert=True)
                miner_days.append(miner_day)
            if i >= result['data']["total_page"]:
                break
            else:
                i += 1
        if miner_days:
            get_db("business").miner_day.bulk_write(miner_days)
            now = datetime.datetime.now()
            MigrateLog.objects(version="s1").update(miner_day={"date": date,
                                                               "datetime": now.strftime("%Y-%m-%d %H:%M:%S")},
                                                    upsert=True)
