from sopel import config, formatting, plugin
from sopel.tools import SopelMemory

from suprabot.commands.badnicks import (
    badnicks_handler,
    match_badnick_handler,
    user_join_handler,
)
from suprabot.commands.badwords import (
    badwords_handler,
    match_badword_handler,
)
from suprabot.commands.bot_join import bot_join_handler
from suprabot.commands.invite import invite_handler
from suprabot.commands.rules import rules_handler
from suprabot.strings import errors, queries
from suprabot.utils.func import get_db

COLOR = formatting.CONTROL_COLOR
GREEN = formatting.colors.GREEN
RED = formatting.colors.RED
BOLD = formatting.CONTROL_BOLD


class ScAdminSection(config.types.StaticSection):
    db_host = config.types.ValidatedAttribute("db_host")
    db_user = config.types.ValidatedAttribute("db_user")
    db_name = config.types.ValidatedAttribute("db_name")
    db_password = config.types.ValidatedAttribute("db_password")
    db_port = config.types.ValidatedAttribute("db_port")


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
        if row[1] not in bot.memory["channels"]:
            bot.memory["channels"][row[1]] = {}
            bot.memory["badwords"][row[1]] = []
            bot.memory["badnicks"][row[1]] = []
            bot.memory["rules"][row[1]] = {}
        bot.memory["channels"][row[1]]["badwords"] = row[2]
        bot.memory["channels"][row[1]]["badnicks"] = row[3]
        bot.memory["channels"][row[1]]["rules"] = row[4]

    cursor.execute(queries["GET_BADWORDS"])

    for row in cursor:
        if row[1] not in bot.memory["badwords"].keys():
            bot.memory["badwords"][row[1]] = []
        bot.memory["badwords"][row[1]].append(row[0])

    cursor.execute(queries["GET_BADNICKS"])

    for row in cursor:
        if row[1] not in bot.memory["badnicks"].keys():
            bot.memory["badnicks"][row[1]] = []
        bot.memory["badnicks"][row[1]].append(row[0].lower())

    cursor.execute(queries["GET_RULES"])

    for row in cursor:
        if row[2] not in bot.memory["rules"].keys():
            bot.memory["rules"][row[2]] = {}
        bot.memory["rules"][row[2]][row[0]] = row[1]

    conn.close()


def configure(bot):
    config.define_section("ScAdmin", ScAdminSection, validate=False) # type: ignore


@plugin.event("INVITE")
@plugin.priority("low")
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def invite(bot, trigger):
    return invite_handler(bot, trigger)


@plugin.event("JOIN")
@plugin.priority("low")
@plugin.thread(True)
@plugin.unblockable
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def bot_join(bot, trigger):
    return bot_join_handler(bot, trigger)


@plugin.require_chanmsg
@plugin.require_privilege(plugin.ADMIN, errors["COMMAND_NOT_ALLOWED"])
@plugin.command("badwords", "bw")
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def badwords(bot, trigger):
    return badwords_handler(bot, trigger)


@plugin.rule("(.*)")
@plugin.require_chanmsg
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def match_badword(bot, trigger):
    return match_badword_handler(bot, trigger)


@plugin.require_chanmsg
@plugin.require_privilege(plugin.ADMIN, errors["COMMAND_NOT_ALLOWED"])
@plugin.command("badnicks", "bn")
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def badnicks(bot, trigger):
    return badnicks_handler(bot, trigger)


@plugin.event("NICK")
@plugin.priority("high")
@plugin.thread(False)
@plugin.unblockable
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def match_badnick(bot, trigger):
    return match_badnick_handler(bot, trigger)


@plugin.event("JOIN")
@plugin.priority("high")
@plugin.thread(True)
@plugin.unblockable
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def user_join(bot, trigger):
    return user_join_handler(bot, trigger)


@plugin.require_chanmsg
@plugin.command(
    "reglas agregar", "reglas modificar", "rg agregar", "rg modificar", "reglas", "rg"
)
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def rules(bot, trigger):
    return rules_handler(bot, trigger)
