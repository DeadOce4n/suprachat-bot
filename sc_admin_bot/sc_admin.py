from sopel import config, formatting, plugin
from sopel.tools import SopelMemory

from .commands.badnicks import (
    badnicks as _badnicks,
    match_badnick as _match_badnick,
    user_join as _user_join,
)
from .commands.badwords import badwords as _badwords, match_badword as _match_badword
from .commands.bot_join import bot_join as _bot_join
from .commands.invite import invite as _invite
from .commands.rules import rules as _rules
from .strings import errors, queries
from .utils.func import get_db

COLOR = formatting.CONTROL_COLOR
GREEN = formatting.colors.GREEN
RED = formatting.colors.RED
BOLD = formatting.CONTROL_BOLD


class ScAdminSection(config.types.StaticSection):
    db_host = config.types.ValidatedAttribute("db_host")
    db_user = config.types.ValidatedAttribute("db_user")
    db_name = config.types.ValidatedAttribute("db_name")
    db_password = config.types.ValidatedAttribute("db_password")


def setup(bot):
    bot.config.define_section("ScAdmin", ScAdminSection)
    bot.memory["channels"] = SopelMemory()
    bot.memory["badwords"] = SopelMemory()
    bot.memory["badnicks"] = SopelMemory()
    bot.memory["rules"] = SopelMemory()

    conn = get_db(bot.settings)
    cursor = conn.cursor(named_tuple=True)
    cursor.execute(queries["GET_ALL_CHANNELS"])

    for row in cursor:
        if row.channel_name not in bot.memory["channels"]:
            bot.memory["channels"][row.channel_name] = {}
            bot.memory["badwords"][row.channel_name] = []
            bot.memory["badnicks"][row.channel_name] = []
            bot.memory["rules"][row.channel_name] = {}
        bot.memory["channels"][row.channel_name]["badwords"] = row.badwords_enabled
        bot.memory["channels"][row.channel_name]["badnicks"] = row.badnicks_enabled
        bot.memory["channels"][row.channel_name]["rules"] = row.rules_enabled

    cursor.execute(queries["GET_BADWORDS"])

    for row in cursor:
        if row.channel_name not in bot.memory["badwords"].keys():
            bot.memory["badwords"][row.channel_name] = []
        bot.memory["badwords"][row.channel_name].append(row.badword)

    cursor.execute(queries["GET_BADNICKS"])

    for row in cursor:
        if row.channel_name not in bot.memory["badnicks"].keys():
            bot.memory["badnicks"][row.channel_name] = []
        bot.memory["badnicks"][row.channel_name].append(row.badnick.lower())

    cursor.execute(queries["GET_RULES"])

    for row in cursor:
        if row.channel_name not in bot.memory["rules"].keys():
            bot.memory["rules"][row.channel_name] = {}
        bot.memory["rules"][row.channel_name][row.rule_number] = row.rule_desc

    conn.close()


def configure(bot):
    config.define_section("ScAdmin", ScAdminSection, validate=False)


@plugin.event("INVITE")
@plugin.priority("low")
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def invite(bot, trigger):
    return _invite(bot, trigger)


@plugin.event("JOIN")
@plugin.priority("low")
@plugin.thread(True)
@plugin.unblockable
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def bot_join(bot, trigger):
    return _bot_join(bot, trigger)


@plugin.require_chanmsg
@plugin.require_privilege(plugin.ADMIN, errors["COMMAND_NOT_ALLOWED"])
@plugin.command("badwords", "bw")
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def badwords(bot, trigger):
    return _badwords(bot, trigger)


@plugin.rule("(.*)")
@plugin.require_chanmsg
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def match_badword(bot, trigger):
    return _match_badword(bot, trigger)


@plugin.require_chanmsg
@plugin.require_privilege(plugin.ADMIN, errors["COMMAND_NOT_ALLOWED"])
@plugin.command("badnicks", "bn")
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def badnicks(bot, trigger):
    return _badnicks(bot, trigger)


@plugin.event("NICK")
@plugin.priority("high")
@plugin.thread(False)
@plugin.unblockable
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def match_badnick(bot, trigger):
    return _match_badnick(bot, trigger)


@plugin.event("JOIN")
@plugin.priority("high")
@plugin.thread(True)
@plugin.unblockable
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def user_join(bot, trigger):
    return _user_join(bot, trigger)


@plugin.require_chanmsg
@plugin.command(
    "reglas agregar", "reglas modificar", "rg agregar", "rg modificar", "reglas", "rg"
)
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def rules(bot, trigger):
    return _rules(bot, trigger)
