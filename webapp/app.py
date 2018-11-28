# !/usr/bin/env python
# _*_ coding:utf-8 _*_

import logging; logging.basicConfig(level=logging.INFO)

import asyncio
from aiohttp import web


def index(request):
    return web.Response(body=b'<h1>Awesome</h1>', content_type='text/html')


async def main(loop):
    app = web.Application()
    app.router.add_route('GET', '/', index)
    srv = await loop.create_server(web.AppRunner(app).app.make_handler(), '127.0.0.1', 9000)
    logging.info('Server started at http://{0}:{1}'.format('127.0.0.1', 9000))
    return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop))
loop.run_forever()