import asyncio
from datetime import date, datetime

from fuzzywuzzy import fuzz
from discord.utils import get
from discord.ext import commands

from ._cog import _Cog
from .user import get_user
from bot import config
from database_tools import df_to_dict, sql_to_df, dict_to_df, df_to_sql, engine
from bot.exceptions import IllegalFormatError, NotApprovedError, WrongChannelError, ShouldBeBannedError

class VerifyUser(_Cog, name="verify"):
    @commands.command(brief='Request roles for yourself.', hidden=True)
    async def verify(self, context):
        def check_reaction(message):
            def check(reaction, user):
                is_correct_reaction = lambda emoji: reaction.message.id == message.id and reaction.emoji == emoji
                is_bot = lambda user: str(user.id) == config.bot_id

                if is_correct_reaction('👍') and not is_bot(user):
                    return True
                if is_correct_reaction('👎') and not is_bot(user):
                    raise IllegalFormatError(user)
                if is_correct_reaction('🥾') and not is_bot(user):
                    raise NotApprovedError(user)
                if is_correct_reaction('🔨') and not is_bot(user):
                    raise ShouldBeBannedError(user)

            return check

        def get_requested_roles(requested_roles):

            for requested_role in requested_roles:
                requested = max(((ratio, role) for role in roles if (ratio := fuzz.token_sort_ratio(role, requested_role)) > 70), default=None)

                if requested is None:
                    requested = max(((ratio, role) for role in roles if (ratio := fuzz.partial_ratio(role, requested_role.lower())) > 70), default=None)

                if requested is not None and (role := roles.get(requested[1])) is not None:
                    yield get(context.message.author.guild.roles, name=role)

        try:
            user_embed = None
            member = context.message.author
            logs = self.client.get_channel(int(config.verification_logs_channel))

            if context.message.channel.id != int(config.verification_channel):
                raise WrongChannelError()

            requested_roles = [ item.strip() for item in context.message.content.split(self.client.command_prefix) if item ]
            if len(requested_roles) == 1 and len(context.message.content.split()) > 1:
                raise IllegalFormatError()

            await context.message.channel.send(f'{context.message.author.mention} A moderator is currently reviewing your verification request and will get back to you shortly.')

            eng = engine(url=config.postgres_url, params=config.postgres_params)
            roles = { role.name.lower() : role.name for role in self.client.get_guild(int(config.server_id)).roles }
            aliases = df_to_dict(sql_to_df('aliases', eng, 'alias')['role'])

            roles = { **roles, **aliases }

            requested_roles = list(get_requested_roles(requested_roles))
            
            user_embed = await get_user(context, context.message.author)
            user_embed.add_field(name='Requested roles', value=context.message.content, inline=False)
            user_embed.add_field(name='Parsed roles', value=' '.join(role.mention for role in requested_roles), inline=False)

            user_embed = await logs.send(embed=user_embed)

            for reaction in ['👍', '👎', '🥾', '🔨']:
                await user_embed.add_reaction(emoji=reaction)

            reaction, user = await self.client.wait_for('reaction_add', timeout=60*60*24, check=check_reaction(user_embed))

        except IllegalFormatError as e:
            channel = self.client.get_channel(int(config.verification_rules_channel))
            await context.message.channel.send(f'{context.message.author.mention} Sorry, your verification request was rejected, please check {channel.mention} and try again!')
            await logs.send(f'{context.message.author} has been rejected by {e.user}')
        except NotApprovedError as e:
            await context.message.author.kick()
            await logs.send(f'{context.message.author} has been kicked by {e.user}.')
        except WrongChannelError:
            channel = self.client.get_channel(int(config.verification_channel))
            await context.message.channel.send(f'Command "verify" is not found')
        except ShouldBeBannedError as e:
            await context.message.author.ban()
            await logs.send(f'{context.message.author} has been banned by {e.user}')
        except (asyncio.TimeoutError, asyncio.exceptions.CancelledError) as e:
            print(e)
        else:
            # eng = engine(url=config.postgres_url, params=config.postgres_params)
            # roles = { role.name.lower() : role.name for role in self.client.get_guild(int(config.server_id)).roles if not role.hoist}
            # aliases = df_to_dict(sql_to_df('aliases', eng, 'alias')['role'])

            # roles = { **roles, **aliases }

            await member.add_roles(*requested_roles)
            await context.message.channel.send(f'{member.mention} has been verified.')
            await logs.send(f'{member} has been accepted by {user}.')

            df = sql_to_df('last_message', eng, 'user_id')
            df.at[str(member.id), 'verified'] = date.today().isoformat()
            df_to_sql(df, 'last_message', eng)
        finally:
            if user_embed is not None:
                await user_embed.clear_reactions()
