# 服务发现（暂时不使用）
### 1 Consul 系统配置
CONSUL_HOST = ''  
CONSUL_PORT = 8500  
CONSUL_TOKEN = None  

### 2、Consul 服务目录配置
* base: 公共基础配置目录，所有service相同的配置

### 3 Consul k/v config配置及示例
支持python, json 格式配置，key命名为python或json即可，其他key都视value为单字符串。  
支持按目录进行多层配置，如 explorer/cache/python, explorer/redis/json, explorer/celery/CELERY_URL，  
除了python/json按照特有格式加载内容中声明的key，其他类型最终加载的key为最后一层，如emi/celery/CELERY_URL。    

###### 如base目录python配置：  
Path: **/base/python**  
value：  
```python
# ---------------------------------------------------
# Sentry Error Track Config
# ---------------------------------------------------
SENTRY_ENABLE = False
SENTRY_DSN = ''
GIT_DIRECTORY = ''
```


### 4 服务注册与健康检查
* 客户端路由模式下，address+port分别是内网IP+端口，**也即无论一个service使用多少个进程，构成唯一的一个service的最小单位是IP+端口。**
* gunicorn启动时，根据bind注册服务和健康检查，检查地址为 **容器IP:bind端口/health**  
* 服务健康检查：默认频率为60s，超时时长5s，30分钟无响应则注销对应service
* 注销service时同时注销check


### 5 服务发现
初期通过config集中配置内部访问地址。
service load balance 交给k8s来实现和路由


### 6 服务间调用
参数说明：
```python
def call(self, name, endpoint, method='POST', body=None, headers={}, timeout=5):
    """
    服务间同步调用请求
    :param name: 服务名, 如 emi、payslip、mall、user_center
    :param endpoint: 服务对应的router，如 /emi/health、/emi/get_orders
    :param method: post、get、put、delete，不区分大小写
    :param body: 字典data
    :param headers: 可选参数
    :param timeout: 
    :return: data
    """
    pass
```
调用示例：
```python
from flask import current_app as app

data = app.services.call('explorer', '/explorer/health', 'get')

```

