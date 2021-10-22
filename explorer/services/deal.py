import datetime
from mongoengine import Q
from base.utils.fil import _d, height_to_datetime, datetime_to_height
from explorer.models.deal import Deal
from base.utils.paginator import mongo_paginator


class DealService(object):
    """
    订单服务
    """

    @classmethod
    def get_deal_list(cls, key_words=None, page_index=1, page_size=20):
        """
        获取订单列表
        :param key_words:
        :param page_index:
        :param page_size:
        :return:
        """
        query = Q()
        if key_words:
            if key_words.isdigit():
                query = Q(deal_id=key_words)
            else:
                query = (Q(client=key_words) | Q(provider=key_words))
        query = Deal.objects(query).order_by("-deal_id")
        result = mongo_paginator(query, page_index, page_size)
        result['objects'] = [info.to_dict(only_fields=("deal_id", "height_time", "client", "provider", "piece_size",
                                                       "is_verified", "storage_price_per_epoch"))
                             for info in result['objects']]

        return result

    @classmethod
    def get_deal_info(cls, deal_id):
        """
        获取订单详情
        :param deal_id:
        :return:
        """

        wallet = Deal.objects(deal_id=deal_id).first()
        data = wallet.to_dict()
        data["start_time"] = height_to_datetime(data["start_epoch"], need_format=True)
        data["end_time"] = height_to_datetime(data["end_epoch"], need_format=True)
        return data






