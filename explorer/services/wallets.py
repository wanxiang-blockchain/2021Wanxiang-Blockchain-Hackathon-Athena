import datetime
from mongoengine import Q
from base.utils.fil import _d, height_to_datetime, datetime_to_height
from explorer.models.wallets import Wallets, WalletRecords
from base.utils.paginator import mongo_paginator


class WalletsService(object):
    """
    钱包服务
    """

    @classmethod
    def get_wallets_list(cls, wallet_type=None, page_index=1, page_size=20):
        """
        获取钱包列表
        :param wallet_type:
        :param page_index:
        :param page_size:
        :return:
        """
        query_dict = {}
        if wallet_type:
            query_dict["wallet_type"] = wallet_type
        else:
            query_dict["wallet_type__in"] = ["fil/5/multisig", "fil/5/storageminer", "fil/5/account"]
        query = Wallets.objects(**query_dict).order_by("-value")
        result = mongo_paginator(query, page_index, page_size)
        result['objects'] = [info.to_dict(only_fields=("id", "address", "value", "wallet_type", "create_height_time",
                                                       "update_height_time")) for info in result['objects']]

        return result

    @classmethod
    def get_wallet_info(cls, id_or_address):
        """
        获取高度区块详情
        :param id_or_address:
        :return:
        """

        wallet = Wallets.objects(Q(id=id_or_address)|Q(address=id_or_address)).first()
        data = wallet.to_dict()
        if data["start_epoch"]:
            data["start_epoch_time"] = height_to_datetime(data["start_epoch"])
        if data["unlock_duration"]:
            data["unlock_duration_time"] = height_to_datetime(data["unlock_duration"])
        return data

    @classmethod
    def get_wallet_record(cls, id_or_address):
        """
        获取高度区块详情
        :param id_or_address:
        :return:
        """

        wallet_records = WalletRecords.objects(Q(address_id=id_or_address)|Q(address=id_or_address))[:100]
        result = [info.to_dict(only_fields=("value", "height_time")) for info in wallet_records]
        return result

    @classmethod
    def get_is_wallet(cls, value):
        """
        判断是否是wallet
        :param value:
        :return:
        """
        return Wallets.objects(Q(id=value) | Q(address=value)).first()






