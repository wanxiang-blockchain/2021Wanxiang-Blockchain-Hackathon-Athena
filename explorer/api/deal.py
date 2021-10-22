import datetime
from flask import request
from explorer.api import util
from explorer.services.deal import DealService
from base.response import response_json


def get_deal_list():
    """
    获取钱包列表
    :return:
    """

    key_words = request.form.get('key_words')
    page_index = int(request.form.get('page_index', 1))
    page_size = min(int(request.form.get('page_size', 10)), 50)
    result = DealService.get_deal_list(key_words, page_index=page_index, page_size=page_size)
    return response_json(result)


def get_deal_info():
    """
    获取钱包详情
    :return:
    """
    deal_id = request.form.get('deal_id')
    result = DealService.get_deal_info(deal_id)
    return response_json(result)


