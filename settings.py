# settings.py

DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 1,
    'scrupper-tyres.middlewares.ProxyMiddleware': 2,
}
