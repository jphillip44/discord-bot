import re
import csv
from datetime import datetime, timedelta
from itertools import tee

import discord
from discord.ext import commands

from scrapers import scrape_course
from bot.exceptions import CourseNotFoundException
from bot import config
from bot.embed_builder import EmbedBuilder
from ._cog import _Cog

class Course(_Cog, name="course"):
    @commands.command(brief='Fetch information regarding a course from YorkU.')
    async def course(self, context):
        def _format_course(course_info):
            embeds = EmbedBuilder(
                title=course_info['heading'],
                description=course_info['description'],
                color=0x0000ff,
                url=course_info['url'],
                thumbnail='http://continue.yorku.ca/york-scs/wp-content/uploads/2016/06/YorkU-logo6.jpg'
            )
            for section in course_info['sections']:
                tmp = EmbedBuilder()
                tmp.add_field(name='\u200b', value=f"___***{section['section_info']}***___", inline=False)
                for name, value in _format_section(section):
                    tmp.add_field(name=name, value=value, inline=False)
                if len(tmp.get_fields()) > 1:
                    embeds.merge_fields(tmp)
            if len(embeds.get_fields()) > 0:
                return embeds
            return []

        def _format_section(section):
            def _format_lectures(lectures):
                for lecture in lectures:
                    yield ' '.join(_format_lecture(lecture))

            def _format_lecture(lecture):
                def _format_day(day):
                    return dict(csv.reader(open('bot/support/days.csv', 'r'))).get(day, '')

                def _format_times(time, duration):
                    def _format_time(time):
                        return datetime.strptime(str(time), "%H:%M:%S").strftime('%-I:%M %p')

                    hours, minutes = map(int, time.split(':'))
                    start = timedelta(hours=hours, minutes=minutes)
                    end = start + timedelta(minutes=int(duration))

                    return f'{_format_time(start)} to {_format_time(end)}'

                def _format_location(location):
                    return f'@{location}' if location != '\xa0 ' else ''

                def _format_backup(backup):
                    return f' ({backup})' if backup is not None else ''

                yield _format_day(lecture['Day'])
                yield _format_times(lecture['Start Time'], lecture['Duration'])
                yield _format_location(lecture['Location'])
                yield _format_backup(lecture.get('Backup'))

            for name, lecture in section['lectures'].items():
                if len(lecture['lecture_info']) > 0:
                    yield (
                        f"{name}: {lecture.get('instructors', 'Not Available')}",
                        '\n'.join(_format_lectures(lecture['lecture_info'])),
                    )

        error = "The requested course was not found. \n\
            \nCourses should be of the form: \
            \n\u2003\u2002[faculty] dept course [session year] \n\
            \nExamples: \
            \n\u2003\u2022 EECS 3311 \
            \n\u2003\u2022 LE EECS 3311 \
            \n\u2003\u2022 EECS 3311 FW 2020 \
            \n\u2003\u2022 LE EECS 3311 FW 2020"

        course = ' '.join(context.message.content.split()[1:])
        info = re.match("".join((
            "^(?:(?P<faculty>[a-z]{2})\s)?"
            "(?:(?P<department>[a-z]{2,4})\s?(?P<course>[0-9]{4}))+"
            "(?:\s(?P<session>[a-z]{2})\s?(?P<year>[0-9]{4}))?$"
        )), course.lower())
        try:
            courses, test = tee(scrape_course(info.groupdict()))

            if next(test, None) is None:
                raise CourseNotFoundException()
            else:
                for course_info in courses:
                    for embed in _format_course(course_info):
                        await context.channel.send(embed=embed)
        except CourseNotFoundException:
            embed = discord.Embed(title="Error", description=error, color=0xff0000, inline=False)
            await context.channel.send(embed=embed)
