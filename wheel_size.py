import scrapy

class WheelSizeSpider(scrapy.Spider):
    name = "wheel_size"
    start_urls = ['https://www.wheel-size.com/size/']

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36',
        'COOKIES_ENABLED': True,
        'COOKIES_DEBUG': True
    }

    def start_requests(self):
        cookies = {
            # додайте тут ваші cookies
        }
        for url in self.start_urls:
            yield scrapy.Request(url=url, cookies=cookies, callback=self.parse)

    def parse(self, response):
        page = response.url.split("/")[-2]
        filename = f'wheelsize-{page}.html'
        with open(filename, 'wb') as f:
            f.write(response.body)
        self.log(f'Saved file {filename}')

        for next_page in response.css('a::attr(href)').getall():
            yield response.follow(next_page, self.parse)
