import logging

from functools import wraps
from flask import request
from flask import current_app as app

# from base.celery_app import celery_app
from base.openapi.exception import OpenApiException
from base.openapi.sign import get_api
from base.response import response_json
# from base.tracing.sentry.error_track import get_request_info

logger = logging.getLogger(__name__)


def open_api(version, api_type="internal"):
    """
    :param version:
    :param api_type: internal针对内部企业open_api, third_xfl针对第三方心福利为我方客户分配秘钥
    :return:
    """
    assert api_type in ["internal", "third_xfl"]

    def fn(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            openClass = get_api(version)
            code, msg = openClass.check_header()
            if code != 0:
                return response_json(code=code, msg=msg)
            # 获取密码药
            app_id = request.headers.get("AppId")
            url = f'/user_center/remote/app_info/{app_id}'
            if api_type == "third_xfl":
                url += '?third_type=xfl'
            response = app.services.call('user_center', url, method='GET', timeout=20).json()
            if response.get('code', -1) != 0:
                return response_json(code=10002, msg='appId无效')
            result = response.get('result', {})
            if not result:
                return response_json(code=10002, msg='appId无效')
            app_secret = result.get('app_secret') or result.get('corp_secret')
            enterprise_id = result.get('enterprise_id')

            if not openClass(app_id, app_secret).verify_sign(request.data.decode()):
                return response_json(code=20001, msg='签名验证失败')
            try:
                return method(*args, **kwargs, enterprise_id=enterprise_id)
            except OpenApiException as e:
                return response_json(code=e.code, msg=e.msg)
            except AssertionError as e:
                return response_json(code=-1, msg=','.join(e.args))
            except Exception as e:
                logging.exception(str(e))
                return response_json(code=40000, msg='业务错误')
            finally:
                celery_app.send_task('user_center.open_api_log.add', (enterprise_id, get_request_info()))

        return wrapper

    return fn
