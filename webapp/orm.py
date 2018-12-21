# !/usr/bin/env python
# _*_ coding:utf-8 _*_
"""
----------------------------------------
Function:   封装的ORM工具类
Version:    1.0
Author:     jinaijun
Contact:    jin_aijun@icloud.com
----------------------------------------
"""

import asyncio
import aiomysql  # 一次用异步，处处用异步
import logging
logging.basicConfig(level=logging.INFO)


def log(sql, args=()):
    logging.info('SQL: {}'.format(sql))


async def create_pool(loop, **kw):
    logging.info('Create database connection pool...')
    global __pool
    __pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )


async def select(sql, args, size=None):
    log(sql, args)
    global __pool
    with (await __pool) as conn:
        cur = await conn.cursor(aiomysql.DictCursor)
        await cur.execute(sql.replace('?', '%s'), args)
        if size:
            rs = await cur.fetchmany(size)
        else:
            rs = await cur.fetchall()
        await cur.close()
        logging.info('Rows returned: {}'.format(len(rs)))
        return rs


async def execute(sql, args, autocommit=True):
    log(sql)
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                row_affected = cur.rowcount
                if not autocommit:
                    await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise
        return row_affected


def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)


class Field(object):
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<{}>, <{}>: <{}>'.format(self.__class__.__name__, self.column_type, self.name)


class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


class StringField(Field):
    def __init__(self, name=None, column_type='varchar(100)', primary_key=False, default=None):
        super().__init__(name, column_type, primary_key, default)


class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


class ModelMetaClass(type):
    def __new__(mcs, name, bases, attrs):
        if name == 'Model':
            return type.__new__(mcs, name, bases, attrs)
        table_name = attrs.get('__table__', None) or name
        logging.info('Found model: {} (table: {})'.format(name, table_name))
        mappings = dict()
        fields = []
        primary_key = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('Found mapping: {} ==> {}'.format(k, v))
                mappings[k] = v
                if v.primary_key:
                    if primary_key:
                        raise RuntimeError('Duplicate primary key for field: {}'.format(k))
                    primary_key = k
                else:
                    fields.append(k)
        if not primary_key:
            raise RuntimeError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields = list(map(lambda f: '{}'.format(f), fields))
        attrs['__mappings__'] = mappings  # 保存属性和列的对应关系
        attrs['__table__'] = table_name  # 保存表名
        attrs['__primary_key__'] = primary_key  # 主键属性名
        attrs['__fields__'] = fields  # 除主键外的属性名
        # 构造默认的SELECT、INSERT、UPDATE、DELETE操作语句
        attrs['__select__'] = 'select {}, {} from {}'.format(primary_key, ','.join(escaped_fields), table_name)
        attrs['__insert__'] = 'insert into {} ({}, {}) values ({})'\
            .format(table_name, ','.join(escaped_fields), primary_key, create_args_string(len(escaped_fields)+1))
        attrs['__update__'] = 'update {} set {} where {}=?'\
            .format(table_name, ','.join(map(lambda f: '{}=?'.format(mappings.get(f).name or f), fields)), primary_key)
        attrs['__delete__'] = 'delete from {} where {}=?'.format(table_name, primary_key)
        return type.__new__(mcs, name, bases, attrs)


class Model(dict, metaclass=ModelMetaClass):
    def __init__(self, **kw):
        super().__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r'"Model" object has no attribute {}'.format(key))

    def __setattr__(self, key, value):
        self[key] = value

    def getvalue(self, key):
        return getattr(self, key, None)

    def get_value_or_default(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('Using default value for {} : {}'.format(key, value))
                setattr(self, key, value)
        return value

    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: {}'.format(str(limit)))
        rs = await select(' '.join(sql), args)
        return [cls(**rs) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        sql = ['select {} _num_ from {}'.format(selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        'Find object by primary key.'
        rs = await select('{} where {} = ?'.format(cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    async def save(self):
        args = list(map(self.get_value_or_default(), self.__fields__))
        args.append(self.get_value_or_default(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warning('Failed to insert record: affected rows: {}'.format(rows))

    async def update(self):
        args = list(map(self.getvalue, self.__fields__))
        args.append(self.getvalue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warning('Failed to update by primary key: affected rows: {}'.format(rows))

    async def remove(self):
        args = [self.getvalue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warning('Failed to remove by primary key: affected rows: {}'.format(rows))