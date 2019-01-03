# !/usr/bin/env python
# _*_ coding:utf-8 _*_

import orm
import asyncio, random, string
from models import User, Blog, Comment, next_id


def random_email():
    qq = random.randint(100000000, 999999999)
    return str(qq) + '@qq.com'


def random_name():
    return ''.join(random.sample(string.ascii_letters, 5))


async def test(loop):
    await orm.create_pool(loop=loop, user='root', password='', db='webapp')

    # # 测试插入新用户
    # for x in range(100):
    #     u = User(name=random_name(), email=random_email(), passwd='', image='')
    #     await u.save()

    # # 测试根据主键查询方法
    # u = await User.find('001546503373640973e784b08154f81a97f5f6e57398fa2000')
    # print(u)

    # # 测试更新方法
    # u = await User.find('001546503373640973e784b08154f81a97f5f6e57398fa2000')
    # u['passwd'] = '123'
    # await u.update()

    # 测试删除方法
    u = await User.find('001546485220106182fe06aa53e470181b68a9c30110f4a000')
    await u.remove()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test(loop))
    loop.run_forever()
