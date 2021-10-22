from .api import message, miner, overview, block, wallets, deal, common

url_map = {
    '/health': [lambda *args, **kwargs: 'ok', ['GET']],
    '/common': {
        '/get_price': [common.get_price, ['POST']],
        '/search': [common.search, ['POST']],
        '/search_miner_or_wallet': [common.search_miner_or_wallet, ['POST']],
    },
    '/block_chain': {
        '/get_tipsets': [block.get_tipsets, ['POST']],
        '/get_tipset_info': [block.get_tipset_info, ['POST']],
        '/get_block_info': [block.get_block_info, ['POST']],
        '/get_wallets_list': [wallets.get_wallets_list, ['POST']],
        '/get_wallet_info': [wallets.get_wallet_info, ['POST']],
        '/get_wallet_record': [wallets.get_wallet_record, ['POST']],
        '/get_miners_by_address': [miner.get_miners_by_address, ['POST']],
        '/get_deal_list': [deal.get_deal_list, ['POST']],
        '/get_deal_info': [deal.get_deal_info, ['POST']],
        '/get_mpool_list': [message.get_mpool_list, ['POST']],
        '/get_mpool_info': [message.get_mpool_info, ['POST']],
        '/get_message_list': [message.get_message_list, ['POST']],
        '/get_message_method_list': [message.get_message_method_list, ['POST']],
        '/get_message_info': [message.get_message_info, ['POST']],
    },
    '/homepage': {
        # '/get_overview': [overview.get_overview, ['POST']],
        '/get_miner_ranking_list_by_power': [miner.get_miner_ranking_list_by_power, ['POST']],
        '/get_miner_ranking_list': [miner.get_miner_ranking_list, ['POST']],
    },
    '/miner': {
        '/get_miner_by_no': [miner.get_miner_by_no, ['POST']],
        '/get_miner_stats_by_no': [miner.get_miner_stats_by_no, ['POST']],
        '/get_miner_gas_stats_by_no': [miner.get_miner_gas_stats_by_no, ['POST']],
        '/get_miner_line_chart_by_no': [miner.get_miner_line_chart_by_no, ['POST']],
        '/get_miner_blocks': [block.get_blocks, ['POST']],
        '/get_transfer_list': [message.get_transfer_list, ['POST']],
        '/get_transfer_method_list': [message.get_transfer_method_list, ['POST']],
    },
}

# open_api 专用
url_map_open_api = {
    # '/enterprise/payslip_batch': [open_api.PayslipSync.as_view('openapi_payslip_sync'), ['POST']]

}
