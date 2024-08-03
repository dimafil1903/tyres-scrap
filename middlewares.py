import random

PROXY_LIST = [
    'http://103.216.82.146:6666',
    'http://103.216.82.153:6666',
    'http://103.216.82.204:6666',
    'http://103.216.82.207:6666',
    'http://103.216.82.208:6666',
    # Додайте більше проксі за потреби
]

class RotateProxyMiddleware(object):
    def process_request(self, request, spider):
        request.meta['proxy'] = random.choice(PROXY_LIST)
