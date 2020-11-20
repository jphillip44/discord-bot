from pytz import timezone
from datetime import date, datetime

from tabulate import tabulate
from discord.ext import commands
import aiocron

from database_tools import engine, sql_to_df, df_to_sql, redis_access
from bot import config
from ._cog import _Cog

import pandas as pd
import redis

class Unverify(_Cog):
    def __init__(self, client):
        _Cog.__init__(self, client)
        tz = timezone('US/Eastern')
        self.redis = redis_access(url=config.redis_url, params=config.redis_params)
        self.engine = engine(url=config.postgres_url, params=config.postgres_params)
        self.df = sql_to_df('last message', self.engine, 'user id')
        aiocron.crontab('0 4 * * *', func=self.push, tz=tz)

    @_Cog.listener()
    async def on_message(self, message):
        author = message.guild.get_member(message.author.id)
        if author is not None and any(str(role.id) == config.verified_role for role in author.roles):
            self.redis.hmset("users" , {message.author.id : date.today().isoformat()})

    @commands.has_permissions(manage_roles=True)
    @commands.command(hidden=True)
    async def push_df(self, context):
        await self.push()

    async def push(self):
        data = self.redis.hgetall("users")
        df = pd.DataFrame.from_dict(data, orient='index', columns=['last message']).rename_axis('user id')
        df = pd.concat([self.df, df]).groupby(level=0).last()
        df_to_sql(df, 'last message', self.engine)
        self.redis.delete('users')
        print(df)

    @commands.has_permissions(manage_roles=True)
    @commands.command(hidden=True)
    async def get_df(self, context):
        self.df = sql_to_df('last message', self.engine, 'user id')
        print(self.df)
        await context.channel.send(f"```\n{tabulate(self.df, headers='keys', tablefmt='psql')}```")
    
    @commands.has_permissions(manage_roles=True)
    @commands.command(hidden=True)
    async def get_redis(self, context):
        data = self.redis.hgetall("users")
        df = pd.DataFrame.from_dict(data, orient='index', columns=['last message']).rename_axis('user id')
        print(df)
        await context.channel.send(f"```\n{tabulate(df, headers='keys', tablefmt='psql')}```")

    @commands.has_permissions(manage_roles=True)
    @commands.command(hidden=True)
    async def users(self, context):
        data = {}
        for user in self.client.get_all_members():
            if any(str(role.id) == config.verified_role for role in user.roles):
                data[str(user.id)] = [date.today().isoformat(), float('nan')]
        print(data)
        df = pd.DataFrame.from_dict(data, orient='index', columns=['verified', 'last message']).rename_axis('user id')
        df.update(self.df)
        df_to_sql(df, 'last message', self.engine)
        print(df)

    