import re
import sched
from sys import exit
import time

import mariadb
from sopel import config, formatting, plugin
from sopel.tools import SopelMemory
from .strings import errors, queries, general

COLOR = formatting.CONTROL_COLOR
GREEN = formatting.colors.GREEN
RED = formatting.colors.RED
BOLD = formatting.CONTROL_BOLD


def get_db(settings):
    conn_params = {
        "user": settings.ScAdmin.db_user,
        "password": settings.ScAdmin.db_password,
        "host": settings.ScAdmin.db_host,
        "database": settings.ScAdmin.db_name,
    }
    try:
        conn = mariadb.connect(**conn_params)
    except mariadb.Error as err:
        print(errors["DB_CONNECTION_ERROR"].format(err))
        exit(1)
    else:
        return conn


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
    if trigger.account:
        bot.join(trigger.sender)
    else:
        bot.notice(
            "Lo siento, solamente usuarios registrados pueden invitarme a una sala 😔",
            trigger.nick,
        )


@plugin.event("JOIN")
@plugin.priority("low")
@plugin.thread(True)
@plugin.unblockable
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def bot_join(bot, trigger):
    if (
        trigger.nick == bot.nick
        and trigger.sender.lower() not in bot.memory["channels"].keys()
    ):
        try:
            conn = get_db(bot.settings)
            cursor = conn.cursor(named_tuple=True)
            cursor.execute(queries["JOIN_CHANNEL"], (trigger.sender.lower(),))
        except mariadb.Error as err:
            bot.say(errors["DB_ERROR"].format(err))
        else:
            conn.commit()
            conn.close()
            bot.memory["channels"][trigger.sender.lower()] = {}
            bot.memory["channels"][trigger.sender.lower()]["badwords"] = False
            bot.memory["channels"][trigger.sender.lower()]["badnicks"] = False
            bot.memory["channels"][trigger.sender.lower()]["rules"] = False
            bot.memory["badwords"][trigger.sender.lower()] = []
            bot.memory["badnicks"][trigger.sender.lower()] = []
            bot.memory["rules"][trigger.sender.lower()] = {}


@plugin.require_chanmsg
@plugin.require_privilege(plugin.ADMIN, errors["COMMAND_NOT_ALLOWED"])
@plugin.command("badwords", "bw")
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def badwords(bot, trigger):
    def show():
        if not bot.memory["channels"][trigger.sender.lower()]["badwords"]:
            bot.say(errors["BADWORDS_NOT_ENABLED"].format(trigger.sender))
        elif len(bot.memory["badwords"][trigger.sender.lower()]) == 0:
            bot.say(errors["NO_BADWORDS"].format(trigger.sender))
        else:
            bot.say(general["BADWORDS_IN_LIST"].format(trigger.sender), trigger.nick)
            for word in bot.memory["badwords"][trigger.sender.lower()]:
                bot.say(f"- {word}", trigger.nick)

    def toggle(activate=True):
        if (
            activate == True
            and bot.memory["channels"][trigger.sender.lower()]["badwords"]
        ):
            bot.say(errors["BADWORDS_ENABLED"].format(trigger.sender))
        elif (
            activate == False
            and not bot.memory["channels"][trigger.sender.lower()]["badwords"]
        ):
            bot.say(errors["BADWORDS_DISABLED"].format(trigger.sender))
        else:
            try:
                conn = get_db(bot.settings)
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    queries["TOGGLE_BADWORDS"],
                    (activate, trigger.sender.lower()),
                )
            except mariadb.ProgrammingError as err:
                print(errors["DB_ERROR"].format(err))
            else:
                conn.commit()
                conn.close()
                bot.memory["channels"][trigger.sender.lower()][
                    "badwords"
                ] = not bot.memory["channels"][trigger.sender.lower()]["badwords"]
                bot.say(
                    general["TOGGLED_BADWORDS"].format(
                        "" if activate else "des", trigger.sender
                    )
                )

    def add(badword):
        if not bot.memory["channels"][trigger.sender.lower()]["badwords"]:
            bot.say(errors["BADWORDS_NOT_ENABLED"].format(trigger.sender))
        elif badword in bot.memory["badwords"][trigger.sender.lower()]:
            bot.say(errors["BADWORD_EXISTS"].format(trigger.sender))
        else:
            try:
                conn = get_db(bot.settings)
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    queries["ADD_BADWORD"],
                    (badword, trigger.sender.lower()),
                )
            except mariadb.IntegrityError as err:
                bot.say(errors["BADWORD_EXISTS"].format(trigger.sender))
                bot.say(err)
            else:
                conn.commit()
                conn.close()
                bot.memory["badwords"][trigger.sender.lower()].append(badword)
                bot.say(general["BADWORD_ADDED"].format(badword, trigger.sender))

    def delete(badword):
        if not bot.memory["channels"][trigger.sender.lower()]["badwords"]:
            bot.say(errors["BADWORDS_NOT_ENABLED"].format(trigger.sender))
        elif badword not in bot.memory["badwords"][trigger.sender.lower()]:
            bot.say(errors["BADWORD_NOT_EXISTS"].format(trigger.sender))
        else:
            try:
                conn = get_db(bot.settings)
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    queries["DELETE_BADWORD"],
                    (badword, trigger.sender.lower()),
                )
            except mariadb.ProgrammingError as err:
                bot.say(errors["BADWORD_NOT_EXISTS"])
                bot.say(err)
            else:
                conn.commit()
                conn.close()
                bot.memory["badwords"][trigger.sender.lower()].remove(badword)
                bot.say(general["BADWORD_DELETED"].format(badword, trigger.sender))

    if trigger.group(3) == "mostrar":
        show()
    elif trigger.group(3) == "activar":
        toggle()
    elif trigger.group(3) == "desactivar":
        toggle(activate=False)
    elif trigger.group(3) == "agregar":
        if trigger.group(4) is None:
            bot.say(errors["WORD_NOT_SPECIFIED"])
            bot.say(f"Ejemplo: {trigger.group(1)} agregar bobo")
        else:
            add(trigger.group(4))
    elif trigger.group(3) == "borrar":
        if trigger.group(4) is None:
            bot.say(errors["WORD_NOT_SPECIFIED"])
            bot.say(f"Ejemplo: {trigger.group(1)} borrar menso")
        else:
            delete(trigger.group(4))
    elif trigger.group(3) is None:
        bot.say(
            general["BADWORDS_COMMANDS"].format(
                f"{bot.config.core.prefix}{trigger.group(1)}",
                "des"
                if bot.memory["channels"][trigger.sender.lower()]["badwords"]
                else "",
            )
        )
    else:
        bot.say(errors["UNKNOWN_COMMAND"].format(trigger.group(3)))


@plugin.rule("(.*)")
@plugin.require_chanmsg
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def match_badword(bot, trigger):
    def handle_mute():
        if bot.channels[trigger.sender].privileges[trigger.nick] == plugin.VOICE:
            if trigger.account is None:
                bot.write(("MODE", trigger.sender.lower(), "-v", trigger.nick))
                bot.write(
                    ("MODE", trigger.sender.lower(), "+b", f"m:*!*@{trigger.host}")
                )
                s = sched.scheduler(time.monotonic, time.sleep)
                s.enter(
                    120.0,
                    1,
                    lambda: bot.write(
                        ("MODE", trigger.sender.lower(), "-b", f"m:*!*@{trigger.host}")
                    ),
                )
                s.run()
            else:
                bot.write(("MODE", trigger.sender.lower(), "-v", trigger.nick))
                bot.write(("CS", "amode", trigger.sender.lower(), "-v", trigger.nick))
                bot.write(
                    ("MODE", trigger.sender.lower(), "+b", f"m:*!*@{trigger.host}")
                )
                s = sched.scheduler(time.monotonic, time.sleep)

                def unmute_avoice():
                    bot.write(
                        ("MODE", trigger.sender.lower(), "-b", f"m:*!*@{trigger.host}")
                    )
                    bot.write(
                        ("CS", "amode", trigger.sender.lower(), "+v", trigger.nick)
                    )

                s.enter(120.0, 1, unmute_avoice)
                s.run()
        elif bot.channels[trigger.sender].privileges[trigger.nick] < plugin.VOICE:
            bot.write(("MODE", trigger.sender.lower(), "+b", f"m:*!*@{trigger.host}"))
            s = sched.scheduler(time.monotonic, time.sleep)
            s.enter(
                120.0,
                1,
                lambda: bot.write(
                    ("MODE", trigger.sender.lower(), "-b", f"m:*!*@{trigger.host}")
                ),
            )
            s.run()

    msg = trigger.group(1)
    if not trigger.sender.is_nick():
        if not bot.memory["channels"][trigger.sender.lower()]["badwords"]:
            pass
        elif trigger.sender.lower() in bot.memory["badwords"].keys():
            for word in bot.memory["badwords"][trigger.sender.lower()]:
                regex = re.compile(rf"\b({word})+\b", re.I)
                match = re.search(regex, msg)
                if match is not None:
                    bot.say(
                        f"{trigger.nick}, la palabra {COLOR}{RED}{word}{COLOR}{GREEN} está prohibida, te vas muteado!"
                    )
                    handle_mute()
                    break


@plugin.require_chanmsg
@plugin.require_privilege(plugin.ADMIN, errors["COMMAND_NOT_ALLOWED"])
@plugin.command("badnicks", "bn")
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def badnicks(bot, trigger):
    def show():
        if not bot.memory["channels"][trigger.sender.lower()]["badnicks"]:
            bot.say(errors["BADNICKS_NOT_ENABLED"].format(trigger.sender))
        elif len(bot.memory["badnicks"][trigger.sender.lower()]) == 0:
            bot.say(errors["NO_BADNICKS"].format(trigger.sender))
        else:
            bot.say(general["BADNICKS_IN_LIST"].format(trigger.sender), trigger.nick)
            for nick in bot.memory["badnicks"][trigger.sender.lower()]:
                bot.say(nick, trigger.nick)

    def toggle(activate=True):
        if (
            activate == True
            and bot.memory["channels"][trigger.sender.lower()]["badnicks"]
        ):
            bot.say(errors["BADNICKS_ENABLED"].format(trigger.sender))
        elif (
            activate == False
            and not bot.memory["channels"][trigger.sender.lower()]["badnicks"]
        ):
            bot.say(errors["BADNICKS_DISABLED"].format(trigger.sender))
        else:
            try:
                conn = get_db(bot.settings)
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    queries["TOGGLE_BADNICKS"],
                    (activate, trigger.sender.lower()),
                )
            except mariadb.ProgrammingError as err:
                print(errors["DB_ERROR"].format(err))
            else:
                conn.commit()
                conn.close()
                bot.memory["channels"][trigger.sender.lower()][
                    "badnicks"
                ] = not bot.memory["channels"][trigger.sender.lower()]["badnicks"]
                bot.say(
                    general["TOGGLED_BADNICKS"].format(
                        "" if activate else "des", trigger.sender
                    )
                )
                if activate:
                    users = {
                        k: v for k, v in bot.channels[trigger.sender].users.items()
                    }
                    for nick in users.keys():
                        if nick in bot.memory["badnicks"][trigger.sender.lower()]:
                            bot.write(
                                ("KICK", trigger.sender.lower(), nick),
                                "tu nick es inapropiado!",
                            )

    def add(badnick):
        if not bot.memory["channels"][trigger.sender.lower()]["badnicks"]:
            bot.say(errors["BADNICKS_NOT_ENABLED"].format(trigger.sender))
        elif badnick.lower() in bot.memory["badnicks"][trigger.sender.lower()]:
            bot.say(errors["BADNICK_EXISTS"].format(trigger.sender))
        else:
            try:
                conn = get_db(bot.settings)
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    queries["ADD_BADNICK"],
                    (badnick.lower(), trigger.sender.lower()),
                )
            except mariadb.IntegrityError as err:
                bot.say(errors["BADNICK_EXISTS"].format(trigger.sender))
                bot.say(err)
            else:
                conn.commit()
                conn.close()
                bot.memory["badnicks"][trigger.sender.lower()].append(badnick.lower())
                bot.say(general["BADNICK_ADDED"].format(badnick, trigger.sender))
                users = {k: v for k, v in bot.channels[trigger.sender].users.items()}
                for nick in users.keys():
                    if nick in bot.memory["badnicks"][trigger.sender.lower()]:
                        bot.write(
                            ("KICK", trigger.sender.lower(), nick),
                            "tu nick es inapropiado!",
                        )

    def delete(badnick):
        if not bot.memory["channels"][trigger.sender.lower()]["badnicks"]:
            bot.say(errors["BADNICKS_NOT_ENABLED"].format(trigger.sender))
        if badnick.lower() not in bot.memory["badnicks"][trigger.sender.lower()]:
            bot.say(errors["BADNICK_NOT_EXISTS"].format(trigger.sender))
        else:
            try:
                conn = get_db(bot.settings)
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    queries["DELETE_BADNICK"],
                    (badnick.lower(), trigger.sender.lower()),
                )
            except mariadb.Error as err:
                bot.say(errors["BADNICK_NOT_EXISTS"].format(trigger.sender))
                bot.say(err)
            else:
                conn.commit()
                conn.close()
                bot.memory["badnicks"][trigger.sender.lower()].remove(badnick.lower())
                bot.say(general["BADNICK_DELETED"].format(badnick, trigger.sender))

    if trigger.group(3) == "mostrar":
        show()
    elif trigger.group(3) == "activar":
        toggle()
    elif trigger.group(3) == "desactivar":
        toggle(activate=False)
    elif trigger.group(3) == "agregar":
        if trigger.group(4) is None:
            bot.say(errors["NICK_NOT_SPECIFIED"])
            bot.say(f"Ejemplo: {trigger.group(1)} agregar {bot.nick}")
        else:
            add(trigger.group(4))
    elif trigger.group(3) == "borrar":
        if trigger.group(4) is None:
            bot.say(errors["NICK_NOT_SPECIFIED"])
            bot.say(f"Ejemplo: {trigger.group(1)} borrar {bot.nick}")
        else:
            delete(trigger.group(4))
    elif trigger.group(3) is None:
        bot.say(
            general["BADNICKS_COMMANDS"].format(
                f"{bot.config.core.prefix}{trigger.group(1)}",
                "des"
                if bot.memory["channels"][trigger.sender.lower()]["badnicks"]
                else "",
            )
        )
    else:
        bot.say(errors["UNKNOWN_COMMAND"].format(trigger.group(3)))


@plugin.event("NICK")
@plugin.priority("high")
@plugin.thread(False)
@plugin.unblockable
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def match_badnick(bot, trigger):
    def filter_nicks(nick: str) -> bool:
        return nick.lower() == trigger.sender.lower()

    for channel in bot.memory["badnicks"]:
        if bot.memory["channels"][channel]["badnicks"]:
            badnick = tuple(filter(filter_nicks, bot.memory["badnicks"][channel]))
            if len(badnick) > 0:
                bot.write(("KICK", channel, badnick[0]), "tu nick es inapropiado!")


@plugin.event("JOIN")
@plugin.priority("high")
@plugin.thread(True)
@plugin.unblockable
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def user_join(bot, trigger):
    if (
        trigger.nick != bot.nick
        and bot.memory["channels"][trigger.sender.lower()]["badnicks"]
        and trigger.nick.lower() in bot.memory["badnicks"][trigger.sender.lower()]
    ):
        bot.write(
            ("KICK", trigger.sender.lower(), trigger.nick), "tu nick es inapropiado!"
        )


@plugin.require_chanmsg
@plugin.command(
    "reglas agregar", "reglas modificar", "rg agregar", "rg modificar", "reglas", "rg"
)
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def rules(bot, trigger):
    def show():
        if not bot.memory["channels"][trigger.sender.lower()]["rules"]:
            bot.say(errors["RULES_NOT_ENABLED"].format(trigger.sender))
        elif len(bot.memory["rules"][trigger.sender.lower()].items()) == 0:
            bot.say(errors["NO_RULES"].format(trigger.sender))
        else:
            bot.say(f"Reglas de {trigger.sender}:", trigger.nick)
            for num, desc in bot.memory["rules"][trigger.sender.lower()].items():
                bot.say(f"{num}.- {desc}", trigger.nick)

    def toggle(activate=True):
        if activate == True and bot.memory["channels"][trigger.sender.lower()]["rules"]:
            bot.say(errors["RULES_ENABLED"].format(trigger.sender))
        elif (
            activate == False
            and not bot.memory["channels"][trigger.sender.lower()]["rules"]
        ):
            bot.say(errors["RULES_DISABLED"].format(trigger.sender))
        else:
            try:
                conn = get_db(bot.settings)
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    queries["TOGGLE_RULES"],
                    (activate, trigger.sender.lower()),
                )
            except mariadb.Error as err:
                print(errors["DB_ERROR"].format(err))
            else:
                conn.commit()
                conn.close()
                bot.memory["channels"][trigger.sender.lower()][
                    "rules"
                ] = not bot.memory["channels"][trigger.sender.lower()]["rules"]
                bot.say(
                    general["TOGGLED_RULES"].format(
                        "" if activate else "des", trigger.sender
                    )
                )

    def add(rule_num: int, rule_desc: str) -> None:
        if not bot.memory["channels"][trigger.sender.lower()]["rules"]:
            bot.say(errors["RULES_NOT_ENABLED"].format(trigger.sender))
        elif rule_num in bot.memory["rules"][trigger.sender.lower()].keys():
            bot.say(errors["RULE_EXISTS"].format(rule_num, trigger.sender))
        else:
            try:
                conn = get_db(bot.settings)
                cursor = conn.cursor()
                cursor.execute(
                    queries["ADD_RULE"],
                    (rule_num, trigger.sender.lower(), rule_desc),
                )
            except mariadb.Error as err:
                bot.say(errors["DB_ERROR"].format(err))
            else:
                conn.commit()
                conn.close()
                bot.memory["rules"][trigger.sender.lower()][rule_num] = rule_desc
                bot.say(general["RULE_ADDED"].format(trigger.sender))

    def update(rule_num: int, rule_desc: str) -> None:
        if not bot.memory["channels"][trigger.sender.lower()]["rules"]:
            bot.say(errors["RULES_NOT_ENABLED"].format(trigger.sender))
        elif rule_num not in bot.memory["rules"][trigger.sender.lower()].keys():
            bot.say(errors["RULE_NOT_EXISTS"].format(rule_num, trigger.sender))
        else:
            try:
                conn = get_db(bot.settings)
                cursor = conn.cursor()
                cursor.execute(
                    queries["UPDATE_RULE"],
                    (rule_desc, trigger.sender.lower(), rule_num),
                )
            except mariadb.Error as err:
                bot.say(errors["DB_ERROR"].format(err))
            else:
                conn.commit()
                conn.close()
                bot.memory["rules"][trigger.sender.lower()][rule_num] = rule_desc
                bot.say(general["RULE_UPDATED"].format(rule_num, trigger.sender))

    def remove(rule_num: int) -> None:
        if not bot.memory["channels"][trigger.sender.lower()]["rules"]:
            bot.say(errors["RULES_NOT_ENABLED"].format(trigger.sender))
        elif rule_num not in bot.memory["rules"][trigger.sender.lower()].keys():
            bot.say(errors["RULE_NOT_EXISTS"].format(rule_num, trigger.sender))
        else:
            try:
                conn = get_db(bot.settings)
                cursor = conn.cursor()
                cursor.execute(
                    queries["DELETE_RULE"],
                    (rule_num, trigger.sender.lower()),
                )
            except mariadb.Error as err:
                bot.say(errors["DB_ERROR"].format(err))
            else:
                conn.commit()
                conn.close()
                bot.memory["rules"][trigger.sender.lower()].pop(rule_num)
                bot.say(general["RULE_DELETED"].format(rule_num, trigger.sender))

    if trigger.group(3) == "mostrar":
        show()

    elif trigger.group(3) == "activar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < plugin.ADMIN:
            bot.say(errors["COMMAND_NOT_ALLOWED"])
        else:
            toggle()

    elif trigger.group(3) == "desactivar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < plugin.OP:
            bot.say(errors["COMMAND_NOT_ALLOWED"])
        else:
            toggle(activate=False)

    elif trigger.group(1) == "reglas modificar" or trigger.group(1) == "rg modificar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < plugin.OP:
            bot.say(errors["COMMAND_NOT_ALLOWED"])
        elif trigger.group(2) is None:
            bot.say(errors["RULE_NUM_NOT_SPECIFIED"])
            bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
        else:
            get_rule = re.search(r"(\b\d+\b)\b(.*)\b", trigger.group(2))
            if get_rule is None:
                bot.say(errors["RULE_NOT_SPECIFIED"])
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            elif get_rule.group(1) is None:
                bot.say(errors["RULE_NUM_NOT_SPECIFIED"])
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            elif not get_rule.group(2):
                bot.say(errors["RULE_DESC_NOT_SPECIFIED"])
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            else:
                update(int(get_rule.group(1)), get_rule.group(2).strip())

    elif trigger.group(1) == "reglas agregar" or trigger.group(1) == "rg agregar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < plugin.OP:
            bot.say(errors["COMMAND_NOT_ALLOWED"])
        elif trigger.group(2) is None:
            bot.say(errors["RULE_NUM_NOT_SPECIFIED"])
            bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
        else:
            get_rule = re.search(r"(\b\d+\b)\b(.*)\b", trigger.group(2))
            if get_rule is None:
                bot.say(errors["RULE_NOT_SPECIFIED"])
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            elif get_rule.group(1) is None:
                bot.say(errors["RULE_NUM_NOT_SPECIFIED"])
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            elif not get_rule.group(2):
                bot.say(errors["RULE_DESC_NOT_SPECIFIED"])
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            else:
                add(int(get_rule.group(1)), get_rule.group(2).strip())

    elif trigger.group(3) == "borrar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < plugin.OP:
            bot.say(errors["COMMAND_NOT_ALLOWED"])
        else:
            try:
                remove(int(trigger.group(4)))
            except ValueError:
                bot.say(errors["INVALID_NUM"].format(trigger.group(4)))
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")

    elif trigger.group(3) is None:
        bot.say(
            general["RULES_COMMANDS"].format(
                f"{bot.config.core.prefix}{trigger.group(1)}",
                "des"
                if bot.memory["channels"][trigger.sender.lower()]["rules"]
                else "",
            )
        )
    else:
        bot.say(errors["UNKNOWN_COMMAND"].format(trigger.group(3)))
