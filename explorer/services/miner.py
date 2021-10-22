import datetime, math
import decimal

from pymongo import UpdateOne
from mongoengine.connection import get_db
from base.utils.paginator import mongo_paginator, mongo_aggregate_paginator
from base.utils.fil import _d, bson_to_decimal, datetime_to_height, prove_commit_aggregate_gas,local2utc,utc2local
from explorer.models.miner import Miners, MinerStat, MinerHotHistory, MinerDay, MinerSyncLog
from explorer.models.overview import Overview
from explorer.models.message import Messages, TipsetGas
from explorer.services.blocks import BlocksService, Blocks
from mongoengine import Q
from mongoengine.context_managers import switch_collection
from bson.decimal128 import Decimal128


class MinerService(object):
    """
    矿工服务
    """

    @classmethod
    def sync_miner_stat(cls):
        """
        同步miner24小时信息
        :return:
        """
        miner_stats = []
        miner_historys = []
        over_view = Overview.objects().order_by("-height").only("height", "power").first()
        end_height = over_view.height - 200  # 修补block需要150个高度
        start_height = end_height - 2880
        data = BlocksService.get_blocks_by_range_height(start_height=start_height,
                                                        end_height=end_height)
        data_dict = {d["_id"]: d for d in data}
        for miner in Miners.objects(sector_effect__ne=0).no_dereference().all():
            miner_history, miner_stat = cls.get_miner_hot_history(miner, data_dict.get(miner.miner, {}),
                                                                  over_view.power)
            miner_stats.append(miner_stat)
            miner_historys.append(miner_history)
        if miner_stats:
            modified_count = get_db("business").miner_stat.bulk_write(miner_stats).modified_count
        if miner_historys:
            get_db("business").miner_hot_history.bulk_write(miner_historys)
        return modified_count

    @classmethod
    def get_24h_power_increase(cls, miner):
        """
        获取24小时算力增加量
        :param miner:
        :return:
        """
        record_time = datetime.datetime.now()
        last_time = record_time - datetime.timedelta(days=1)
        last_record = MinerHotHistory.objects(miner_no=miner.miner,
                                              record_time__lte=local2utc(last_time)).order_by("-record_time").first()
        if not last_record:
            return _d(miner.sector_all * miner.sector_size), miner.actual_power
        # 计算算力增速、算力增量
        increase_power = (miner.sector_all - last_record.sector_all) * miner.sector_size
        increase_power_offset = miner.actual_power - last_record.actual_power
        return _d(increase_power), increase_power_offset

    @classmethod
    def get_miner_hot_history(cls, miner, data, power):
        """添加矿工48小时热表数据"""
        now = datetime.datetime.now()
        minute = math.floor(now.minute / 30) * 30
        record_time = datetime.datetime(now.year, now.month, now.day, now.hour, minute, 0)
        miner_history = UpdateOne({"miner_no": miner.miner, "record_time": local2utc(record_time)},
                                  {"$set": dict(
                                      raw_power=Decimal128(miner.raw_power),
                                      actual_power=Decimal128(miner.actual_power),
                                      sector_all=miner.sector_all,
                                      sector_effect=miner.sector_effect,
                                      sector_size=miner.sector_size
                                  )},
                                  upsert=True
                                  )
        if data:
            pass
        block_reward = bson_to_decimal(data.get("sum_gas_reward", Decimal128("0"))) + \
                       bson_to_decimal(data.get("sum_block_reward", Decimal128("0")))
        win_count = data.get("sum_win_count", 0)
        block_count = data.get("block_count", 0)
        # 计算平均收益
        avg_reward = block_reward / (miner.actual_power / _d(1024 ** 4)) if miner.actual_power else 0
        avg_reward = avg_reward.quantize(decimal.Decimal("0"), rounding=decimal.ROUND_HALF_UP)
        # 计算24小时算力增速、增量
        increase_power, increase_power_offset = cls.get_24h_power_increase(miner)
        lucky = round(block_count / cls._get_24h_theory_block_count(miner, power), 4)
        miner_stat = UpdateOne({"miner_no": miner.miner},
                               {"$set": dict(
                                   block_reward=Decimal128(block_reward),
                                   block_count=block_count,
                                   win_count=win_count,
                                   increase_power=Decimal128(increase_power),
                                   increase_power_offset=Decimal128(increase_power_offset),
                                   avg_reward=Decimal128(avg_reward),
                                   lucky=Decimal128(_d(lucky)),
                                   sector_size=miner.sector_size
                               )},
                               upsert=True)

        return miner_history, miner_stat

    @classmethod
    def _get_24h_theory_block_count(cls, miner, power):
        """
        或者24h理论出块数量
        :param miner:
        :param power:
        :return:
        """
        return miner.actual_power / power * 2880 * 5

    @classmethod
    def sync_miner_day(cls, date_str=None):
        """
        按天统计miner
        :return:
        """
        if date_str:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            date = datetime.date.today() - datetime.timedelta(days=1)
            date_str = date.strftime("%Y-%m-%d")
        start_height = datetime_to_height(date)
        end_height = start_height + 2880
        over_view = Overview.objects(height__lt=end_height).order_by("-height").only("height", "power").first()
        data = BlocksService.get_blocks_by_range_height(start_height=start_height,
                                                        end_height=end_height)
        data_dict = {d["_id"]: d for d in data}
        miner_days = []
        for miner in Miners.objects(sector_effect__ne=0).no_dereference().all():
            miner_day = cls.get_miner_day(miner, date_str, data_dict.get(miner.miner, {}), over_view.power)
            miner_days.append(miner_day)
        get_db("business").miner_day.bulk_write(miner_days)

    @classmethod
    def get_miner_day(cls, miner, date_str, data, power):
        """
        获取miner每天的数据
        :param miner:
        :param date_str:
        :param data:
        :param power:
        :return:
        """
        # 获取上一次的记录，用于计算增量
        last_record = MinerDay.objects(miner_no=miner.miner, date__lt=date_str).order_by("-date").first()
        # 新增扇区
        new_sector = miner.sector_all
        if last_record:
            new_sector = miner.sector_all - (last_record.sector_all or 0)
        # 新增算力
        increase_power = _d(new_sector * miner.sector_size)
        # 新增算力增量
        increase_power_offset = "0"
        if last_record:
            increase_power_offset = miner.actual_power - last_record.actual_power

        block_reward = bson_to_decimal(data.get("sum_gas_reward", Decimal128("0"))) + \
                       bson_to_decimal(data.get("sum_block_reward", Decimal128("0")))
        win_count = data.get("sum_win_count", 0)
        block_count = data.get("block_count", 0)
        # 计算平均收益
        avg_reward = block_reward / (miner.actual_power / _d(1024 ** 4)) if miner.actual_power else 0
        avg_reward = avg_reward.quantize(decimal.Decimal("0"), rounding=decimal.ROUND_HALF_UP)
        lucky = round(block_count / cls._get_24h_theory_block_count(miner, power), 4)
        miner_day = UpdateOne({"miner_no": miner.miner, "date": date_str},
                              {"$set": dict(
                                  actual_power=Decimal128(miner.actual_power),
                                  raw_power=Decimal128(miner.raw_power),
                                  sector_size=miner.sector_size,
                                  sector_all=miner.sector_all,
                                  sector_effect=miner.sector_effect,
                                  total_balance=Decimal128(miner.total_balance),
                                  available_balance=Decimal128(miner.available_balance),
                                  # pledge_balance=miner.pledge_balance,
                                  initial_pledge_balance=Decimal128(miner.initial_pledge_balance),
                                  locked_balance=Decimal128(miner.locked_balance),
                                  total_reward=Decimal128(miner.total_reward or "0"),
                                  total_block_count=miner.total_block_count or 0,
                                  total_win_count=miner.total_win_count or 0,
                                  increase_power=Decimal128(increase_power),
                                  increase_power_offset=Decimal128(increase_power_offset),
                                  block_reward=Decimal128(block_reward),
                                  avg_reward=Decimal128(avg_reward),
                                  win_count=win_count,
                                  block_count=block_count,
                                  lucky=Decimal128(_d(lucky)),
                                  pre_gas=Decimal128("0"),
                                  pre_gas_count=0,
                                  prove_gas=Decimal128("0"),
                                  prove_gas_count=0,
                                  win_post_gas=Decimal128("0"),
                                  win_post_gas_count=0,
                                  pledge_gas=Decimal128("0"),
                              )},
                              upsert=True)
        return miner_day

    @classmethod
    def sync_miner_total_blocks(cls, ):
        """
        统计每个miner的出块汇总
        :return:
        """
        data = BlocksService.get_blocks_by_range_height()
        miners = []
        for per in data:
            total_reward = bson_to_decimal(per.get("sum_gas_reward", Decimal128("0"))) + \
                           bson_to_decimal(per.get("sum_block_reward", Decimal128("0")))
            miners.append(UpdateOne({"miner": per.get("_id")},
                                    {"$set": dict(
                                        total_reward=Decimal128(total_reward),
                                        total_win_count=per.get("sum_win_count", 0),
                                        total_block_count=per.get("block_count", 0))
                                    }))
        result = get_db("base").miners.bulk_write(miners)
        return result.modified_count

    @classmethod
    def sync_miner_day_gas(cls, date_str=None, reset=False):
        """
        统计miner——day的gas信息
        :param date_str:
        :param reset:
        :return:
        """
        if not date_str:
            date = datetime.date.today() - datetime.timedelta(days=1)
            date_str = date.strftime("%Y-%m-%d")
        save_per_count = 200
        search_step = 5
        sync_obj = MinerSyncLog.objects(date=date_str).first()

        # 开始时间戳
        start_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        start_index = datetime_to_height(start_date)
        temp_index = max(start_index, sync_obj.gas_sync_height if sync_obj else 0)
        # 结束时间戳
        end_index = start_index + 2880
        # 如果需要重置
        if reset:
            # 重置进度表
            sync_obj.gas_sync_height = start_index
            sync_obj.save()
            temp_index = start_index
            # 重置每日矿工表
            MinerDay.objects(date=date_str).update(pre_gas=0, prove_gas=0, win_post_gas=0, pre_gas_count=0,
                                                   prove_gas_count=0, win_post_gas_count=0)

        def _add_v(d, k, t, v, ps, s_c=1):
            if k not in d:
                d[k] = {
                    'pre_gas': _d(0), 'prove_gas': _d(0), 'win_post_gas': _d(0), 'pledge_gas': _d(0),
                    'pre_gas_count': 0, 'prove_gas_count': 0, 'win_post_gas_count': 0
                }
            d[k][t] += bson_to_decimal(v)
            d[k]["pledge_gas"] += bson_to_decimal(ps)
            d[k][t + '_count'] += s_c

        miner_gas_dict = {}
        while temp_index < end_index:
            heights = [x for x in range(temp_index, temp_index + search_step)]
            messages = get_db("base")["messages@zone_" + start_date.strftime("%Y%m")].find({"height": {"$in": heights}})
            # with switch_collection(Messages, "messages@zone_" + start_date.strftime("%Y%m")) as Message_s:
            #     heights = [x for x in range(temp_index, temp_index + search_step)]
            #     messages = Message_s.objects(height__in=heights).as_pymongo().all()
            for per in messages:
                miner_no = per['msg_to']
                # SubmitWindowedPoSt
                if per['msg_method'] == 5:
                    _add_v(miner_gas_dict, miner_no, 'win_post_gas', per['gascost_total_cost'], per['msg_value'])
                # PreCommitSector PreCommitSectorBatch
                if per['msg_method'] in [6, 25]:
                    sector_count = per.get("sector_count", 1)
                    _add_v(miner_gas_dict, miner_no, 'pre_gas', per['gascost_total_cost'], per['msg_value'],
                           sector_count)
                # ProveCommitSector ProveCommitAggregate
                if per['msg_method'] in [7, 26]:
                    prove_agg_gas = 0
                    sector_count = per.get("sector_count", 1)
                    if per['msg_method'] == 26:  # 多扇区封装
                        prove_agg_gas = prove_commit_aggregate_gas(sector_count, int(per["base_fee"]))
                    _add_v(miner_gas_dict, miner_no, 'prove_gas',
                           Decimal128(bson_to_decimal(per['gascost_total_cost']) + _d(prove_agg_gas)),
                           per['msg_value'], sector_count)

            temp_index += search_step
            # 每隔save_per_count次保存一次
            if temp_index % save_per_count == 0:
                cls.save_miner_gas(data=miner_gas_dict, date=date_str, height=temp_index)
                miner_gas_dict = {}
        # 收尾
        if miner_gas_dict:
            cls.save_miner_gas(data=miner_gas_dict, date=date_str, height=temp_index)

    @classmethod
    def save_miner_gas(cls, data, date, height):
        """
        保存汽油费
        :param data:
        :param date:
        :param height:
        :return:
        """
        miner_days = []
        for miner_no, one_data in data.items():
            miner_days.append(
                UpdateOne({"miner_no": miner_no, "date": date},
                          {"$inc": {"pre_gas": Decimal128(one_data["pre_gas"]),
                                    "pre_gas_count": one_data["pre_gas_count"],
                                    "prove_gas": Decimal128(one_data["prove_gas"]),
                                    "prove_gas_count": one_data["prove_gas_count"],
                                    "win_post_gas": Decimal128(one_data["win_post_gas"]),
                                    "win_post_gas_count": one_data["win_post_gas_count"],
                                    "pledge_gas": Decimal128(one_data["pledge_gas"])}})
            )
        if miner_days:
            get_db("business").miner_day.bulk_write(miner_days)
        MinerSyncLog.objects(date=date).upsert_one(gas_sync_height=height)

    @classmethod
    def get_increase_power_loss(cls):
        """
        获取算力损失
        :return:
        """
        # 32
        sector_size_32 = 34359738368
        faults_power_32 = Miners.objects(sector_size=sector_size_32).sum("sector_faults") * _d(sector_size_32)
        sector_size_64 = 68719476736
        faults_power_64 = Miners.objects(sector_size=sector_size_64).sum("sector_faults") * _d(sector_size_64)
        return faults_power_32 + faults_power_64

    @classmethod
    def get_is_miner(cls, value):
        """
        判断是否是miner
        :param value:
        :return:
        """
        return Miners.objects(Q(miner=value)|Q(address=value)).first()

    @classmethod
    def get_miners_by_address(cls, address):
        """
        获取算力损失
        :return:
        """
        result = dict()
        # 名下节点
        result["subordinate"] = list(Miners.objects(owner_address=address).scalar("miner"))
        # 工作节点
        result["worker"] = list(Miners.objects(Q(worker_address=address) | Q(post_address=address)).scalar("miner"))

        return result

    @classmethod
    def get_miner_stat_ranking_list(cls, order=None, sector_type=None, miner_no_list=[]):
        """
        获取24小时的矿工排名记录
        :param order:
        :param sector_type:
        :param miner_no_list:
        :return:
        """
        query_dict = {}
        if sector_type is not None:
            if sector_type == '0':
                query_dict["sector_size"] = 34359738368
            if sector_type == '1':
                query_dict["sector_size"] = 68719476736
        if miner_no_list:
            query_dict["miner_no__in"] = miner_no_list
        query = MinerStat.objects(**query_dict)
        if order:
            query = query.order_by(order)

        return query.as_pymongo()

    @classmethod
    def get_miner_day_ranking_list(cls, start_date, end_date, sector_type=None, miner_no_list=[],
                                   filter_type="increase_power", page_index=1, page_size=20):
        """
        获取指定日期的矿工排行榜数据
        :param start_date:
        :param end_date:
        :param sector_type:
        :param miner_no_list:
        :param filter_type:
        :param page_index:
        :param page_size:
        :return:
        """
        query_dict = {"date__gte": start_date, "date__lte": end_date}
        if sector_type is not None:
            if sector_type == '0':
                query_dict["sector_size"] = 34359738368
            if sector_type == '1':
                query_dict["sector_size"] = 68719476736
        if miner_no_list:
            query_dict["miner_no__in"] = miner_no_list
        if filter_type == "increase_power":
            pipeline = [
                {"$group": {"_id": "$miner_no",
                            "increase_power": {"$avg": "$increase_power"},
                            "increase_power_offset": {"$avg": "$increase_power_offset"}
                            }},
                {"$sort": {"increase_power": -1}}
            ]
        if filter_type == "avg_reward":
            query_dict["avg_reward__lt"] = 10**18
            pipeline = [
                {"$group": {"_id": "$miner_no",
                            "avg_reward": {"$avg": "$avg_reward"}
                            }},
                {"$sort": {"avg_reward": -1}}
            ]
        if filter_type == "block_count":
            pipeline = [
                {"$group": {"_id": "$miner_no",
                            "win_count": {"$sum": "$win_count"},
                            "lucky": {"$avg": "$lucky"},
                            "block_reward": {"$sum": "$block_reward"},
                            }},
                {"$sort": {"win_count": -1}},
            ]
        return mongo_aggregate_paginator(MinerDay.objects(**query_dict), pipeline, page_index, page_size)

    @classmethod
    def get_miner_ranking_list(cls, stats_type, filter_type, sector_type=None, miner_no_list=[],
                               page_index=1, page_size=20):
        """
        矿工排行子函数
        :param stats_type:
        :param filter_type:
        :param sector_type:
        :param miner_no_list:
        :param page_index:
        :param page_size:
        :return:
        """
        if stats_type == "24h":
            query = cls.get_miner_stat_ranking_list("-" + filter_type, sector_type, miner_no_list)
            data = mongo_paginator(query, page_index, page_size)
            miner_no_list = [info["miner_no"] for info in data['objects']]
            if "block_count" == filter_type:
                data["total_block_reward"] = cls.get_miner_stat_total_block_reward(sector_type)
        else:
            end_date = datetime.date.today() - datetime.timedelta(days=1)
            start_date = end_date - datetime.timedelta(days=int(stats_type[0:stats_type.find("d")]))
            start_date = start_date.strftime("%Y-%m-%d")
            end_date = end_date.strftime("%Y-%m-%d")
            data = cls.get_miner_day_ranking_list(start_date, end_date,
                                                  sector_type, miner_no_list, filter_type, page_index, page_size)
            miner_no_list = [info["_id"] for info in data['objects']]
            if "block_count" == filter_type:
                data["total_block_reward"] = cls.get_miner_day_total_block_reward(start_date, end_date, sector_type)
        miner_list = Miners.objects(miner__in=miner_no_list).all()
        miner_no_dict = {}
        for miner in miner_list:
            tmp = {"power": miner.actual_power, "sector_size": miner.sector_size}
            miner_no_dict[miner.miner] = tmp
        return miner_no_dict, data

    @classmethod
    def get_miner_stat_total_block_reward(cls, sector_type=None):
        """
        获取指定日期的矿工排行榜数据
        :param sector_type:
        :return:
        """
        query_dict = {}
        if sector_type is not None:
            if sector_type == '0':
                query_dict["sector_size"] = 34359738368
            if sector_type == '1':
                query_dict["sector_size"] = 68719476736
        return bson_to_decimal(MinerStat.objects(**query_dict).sum("block_reward"))

    @classmethod
    def get_miner_day_total_block_reward(cls, start_date, end_date, sector_type=None):
        """
        获取指定日期的矿工排行榜数据
        :param start_date:
        :param end_date:
        :param sector_type:
        :return:
        """
        query_dict = {"date__gte": start_date, "date__lte": end_date}
        if sector_type is not None:
            if sector_type == '0':
                query_dict["sector_size"] = 34359738368
            if sector_type == '1':
                query_dict["sector_size"] = 68719476736
        return bson_to_decimal(MinerDay.objects(**query_dict).sum("block_reward"))

    @classmethod
    def get_miner_ranking_list_by_power(cls, sector_type=None, miner_no_list=[], page_index=1, page_size=20):
        """
        存储节点算力排行
        :param sector_type:
        :param miner_no_list:
        :param page_index:
        :param page_size:
        :return:
        """
        query_dict = {"sector_effect__ne": 0}
        if sector_type is not None:
            if sector_type == '0':
                query_dict["sector_size"] = 34359738368
            if sector_type == '1':
                query_dict["sector_size"] = 68719476736
        if miner_no_list:
            query_dict["miner_no__in"] = miner_no_list

        query = Miners.objects(**query_dict).order_by("-actual_power")
        data = mongo_paginator(query, page_index, page_size)
        miner_no_list = [info["miner"] for info in data['objects']]
        miner_stat_list = MinerStat.objects(miner_no__in=miner_no_list).all()
        miner_stat_dict = {miner_stat.miner_no: miner_stat.to_dict() for miner_stat in miner_stat_list}
        miner_data = []
        for miner in data['objects']:
            miner_no = miner.miner
            tmp = dict(miner_no=miner_no, power=miner.actual_power, )
            tmp.update(miner_stat_dict.get(miner_no))
            miner_data.append(tmp)
        data["objects"] = miner_data
        return data

    @classmethod
    def get_miner_by_no(cls, miner_no):
        """
        根据矿工no获取信息
        :return:
        """
        miner = Miners.objects(Q(miner=miner_no)| Q(address=miner_no)).first()
        data = miner.to_dict()
        ranking = Miners.objects(actual_power__gt=miner.actual_power).count() + 1
        data["ranking"] = ranking
        # data["miner_id"] = miner.miner
        return data

    @classmethod
    def get_miner_stats_by_no(cls, miner_no, stats_type, start_date=None, end_date=None):
        """
        矿工详情展示产出统计
        """
        now_date = datetime.datetime.today()

        def _format_data(_start_date, _end_date=None):
            increase_power = _d(0)
            increase_power_offset = _d(0)
            block_reward = _d(0)
            block_count = 0
            win_count = 0
            lucky = _d(0)
            query_dict = {"miner_no": miner_no}
            if _start_date:
                query_dict["date__gte"] = _start_date
            if _end_date:
                query_dict["date__lte"] = _end_date
            objs = MinerDay.objects(**query_dict).order_by("-date")
            if not objs:
                return {}
            power = objs[0].actual_power
            count = 0
            for obj in objs:
                count += 1
                increase_power += obj.increase_power
                increase_power_offset += obj.increase_power_offset
                block_reward += obj.block_reward
                block_count += obj.block_count
                win_count += obj.win_count
                lucky += obj.lucky
            # 计算平均收益
            avg_reward = _d(0)
            if power:
                avg_reward = (block_reward / (power / _d(math.pow(1024, 4)))).quantize(decimal.Decimal("1"),
                                                                                       decimal.ROUND_HALF_UP)
            if count:
                lucky = lucky / count
            result_dict = dict(increase_power=increase_power, increase_power_offset=increase_power_offset,
                               block_reward=block_reward, block_count=block_count, win_count=win_count,
                               avg_reward=avg_reward, lucky=round(lucky, 4))
            return result_dict

        if stats_type == "7d":
            _start_date = now_date - datetime.timedelta(days=7)
            return _format_data(_start_date.strftime("%Y-%m-%d"))
        if stats_type == "30d":
            _start_date = now_date - datetime.timedelta(days=30)
            return _format_data(_start_date.strftime("%Y-%m-%d"))
        if stats_type == "24h":
            miner_stat = MinerStat.objects(miner_no=miner_no).first()
            return miner_stat.to_dict()
        if start_date and end_date:
            return _format_data(start_date, end_date)
        return {}

    @classmethod
    def get_miner_gas_stats_by_no(cls, miner_no, stats_type, start_date=None, end_date=None):
        """
        矿工详情展示成本统计
        """
        now_date = datetime.datetime.today()

        def _format_data(_start_date, _end_date=None):
            total_gas = _d(0)  # 总gas
            create_total_gas = _d(0)  # 生产gas
            query_dict = {"miner_no": miner_no}
            if _start_date:
                query_dict["date__gte"] = _start_date
            if _end_date:
                query_dict["date__lte"] = _end_date
            objs = MinerDay.objects(**query_dict).order_by("-date")
            if not objs:
                return {}
            power = objs[0].actual_power
            sector_size = objs[0].sector_size
            initial_pledge_balance = objs[0].initial_pledge_balance
            last_initial_pledge_balance = 0  #
            count = 0
            last_power = 0
            for obj in objs:
                count += 1
                create_total_gas += obj.pre_gas + obj.prove_gas
                total_gas += create_total_gas + obj.win_post_gas
                last_initial_pledge_balance = obj.initial_pledge_balance
                last_power = obj.actual_power
            total_pledge = initial_pledge_balance - last_initial_pledge_balance  # 质押
            # 生产成本
            create_gas = _d(0)
            increase_power = power-last_power
            if increase_power:
                create_gas = create_total_gas / (increase_power / _d(1024 ** 4))
                create_gas = create_gas.quantize(decimal.Decimal("1"), decimal.ROUND_HALF_UP)
            # 全网生产成本
            start_height = datetime_to_height(_start_date + " 00:00:00")
            query_dict["height__gte"] = start_height
            if _end_date:
                end_height = datetime_to_height(_end_date + " 23:59:59")
                query_dict["height__lte"] = end_height
            gas_field = "create_gas_32" if sector_size == 34359738368 else "create_gas_64"
            create_gas_overview = TipsetGas.objects(height__gte=start_height).average(gas_field)

            result_dict = dict(total_gas=total_gas, total_pledge=total_pledge,
                               create_gas=create_gas, create_gas_overview=bson_to_decimal(create_gas_overview))
            return result_dict

        if stats_type:
            days = int(stats_type[:-1])
            _start_date = now_date - datetime.timedelta(days=days)
            return _format_data(_start_date.strftime("%Y-%m-%d"))
        if start_date and end_date:
            return _format_data(start_date, end_date)
        return {}

    @classmethod
    def _get_miner_line_chart_by_no(cls, miner_no, days, spot=30):
        step = int(days / spot)
        now_date = datetime.datetime.today()
        ds_day = now_date - datetime.timedelta(days=days)
        ds_day_list = [ds_day + datetime.timedelta(days=step * x) for x in range(0, spot)]
        objs = MinerDay.objects(miner_no=miner_no, date__gte=ds_day.strftime('%Y-%m-%d')).only("actual_power",
                                                                                               "increase_power_offset",
                                                                                               "block_reward", "date",
                                                                                               "block_count").all()
        ds_day_dict = {}
        for obj in objs:
            ds_day_dict[obj.date] = {
                "power": obj.actual_power,
                "increase_power_offset": obj.increase_power_offset,
                "block_reward": obj.block_reward,
                "block_count": obj.block_count,
                "date": obj.date
            }
        ds_day_list.reverse()
        ds_day_result = []
        for day_step in ds_day_list:
            if step > 1:
                power = ds_day_dict.get(day_step.strftime('%Y-%m-%d'), {}).get('power', 0)
                increase_power_offset = _d(0)
                block_reward = _d(0)
                block_count = _d(0)
                for day1 in [day_step - datetime.timedelta(days=x) for x in range(0, step)]:
                    day_ = day1.strftime('%Y-%m-%d')
                    increase_power_offset += ds_day_dict.get(day_, {}).get('increase_power_offset', _d(0))
                    block_reward += ds_day_dict.get(day_, {}).get('block_reward', _d(0))
                    block_count += ds_day_dict.get(day_, {}).get('block_count', _d(0))
                ds_day_result.append({
                    "power": power,
                    "increase_power_offset": increase_power_offset,
                    "block_reward": block_reward,
                    "block_count": block_count,
                    "date": day_step.strftime('%Y-%m-%d')
                })
            else:
                ds_day_result.append(ds_day_dict.get(day_step.strftime('%Y-%m-%d'), {
                    "power": _d(0),
                    "increase_power_offset": _d(0),
                    "block_reward": _d(0),
                    "block_count": _d(0),
                    "date": day_step.strftime('%Y-%m-%d')
                }))
        return ds_day_result

    @classmethod
    def get_miner_line_chart_by_no(cls, miner_no, stats_type):
        """
        矿工的算力变化和出块统计
        """
        if stats_type == "30d":
            return cls._get_miner_line_chart_by_no(miner_no, 30, 30)
        if stats_type == "180d":
            return cls._get_miner_line_chart_by_no(miner_no, 180, 30)
        if stats_type == "24h":
            hs_24 = datetime.datetime.now() - datetime.timedelta(days=1)
            hs_24_list = [(hs_24 + datetime.timedelta(hours=1 * x)).replace(minute=0, second=0, microsecond=0) for x in
                          range(0, 24)]
            pipeline = [
                {"$project": {"block_reward":"$block_reward",
                              "date": {"$dateToString": {"format": "%Y-%m-%d %H", "date": "$height_time"}}}},
                {"$group": {"_id": "$date",
                            "block_reward": {"$sum": "$block_reward"},
                            "block_count": {"$sum": 1}
                            }}
            ]
            data = Blocks.objects(miner_id=miner_no, height__gte=datetime_to_height(hs_24)).aggregate(pipeline)
            hs_24_dict = {}
            for obj in data:
                date = utc2local(datetime.datetime.strptime(obj["_id"], "%Y-%m-%d %H"))
                hs_24_dict[date] = {
                    "block_reward": bson_to_decimal(obj["block_reward"]),
                    "block_count": obj["block_count"],
                    "date": date.strftime("%Y-%m-%d %H:%M:%S")
                }
            hs_24_result = []
            for hs1 in hs_24_list:
                hs_24_result.append(hs_24_dict.get(hs1, {
                    "block_reward": 0,
                    "block_count": 0,
                    "date": hs1.strftime('%Y-%m-%d %H:%M:%S')
                }))
            hs_24_result.reverse()
            return hs_24_result
