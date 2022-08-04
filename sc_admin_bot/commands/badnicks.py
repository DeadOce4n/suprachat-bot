from mariadb import Error as MariaDBError, IntegrityError, ProgrammingError

from ..strings import errors, general, queries
from ..utils.func import get_db


def _show(bot, trigger):
    if not bot.memory["channels"][trigger.sender.lower()]["badnicks"]:
        bot.say(errors["BADNICKS_NOT_ENABLED"].format(trigger.sender))
    elif len(bot.memory["badnicks"][trigger.sender.lower()]) == 0:
        bot.say(errors["NO_BADNICKS"].format(trigger.sender))
    else:
        bot.say(general["BADNICKS_IN_LIST"].format(trigger.sender), trigger.nick)
        for nick in bot.memory["badnicks"][trigger.sender.lower()]:
            bot.say(nick, trigger.nick)


def _toggle(bot, trigger, activate=True):
    if activate == True and bot.memory["channels"][trigger.sender.lower()]["badnicks"]:
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
        except ProgrammingError as err:
            print(errors["DB_ERROR"].format(err))
        else:
            conn.commit()
            conn.close()
            bot.memory["channels"][trigger.sender.lower()]["badnicks"] = not bot.memory[
                "channels"
            ][trigger.sender.lower()]["badnicks"]
            bot.say(
                general["TOGGLED_BADNICKS"].format(
                    "" if activate else "des", trigger.sender
                )
            )
            if activate:
                users = {k: v for k, v in bot.channels[trigger.sender].users.items()}
                for nick in users.keys():
                    if nick in bot.memory["badnicks"][trigger.sender.lower()]:
                        bot.write(
                            ("KICK", trigger.sender.lower(), nick),
                            "tu nick es inapropiado!",
                        )


def _add(bot, trigger, badnick):
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
        except IntegrityError as err:
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


def _delete(bot, trigger, badnick):
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
        except MariaDBError as err:
            bot.say(errors["BADNICK_NOT_EXISTS"].format(trigger.sender))
            bot.say(err)
        else:
            conn.commit()
            conn.close()
            bot.memory["badnicks"][trigger.sender.lower()].remove(badnick.lower())
            bot.say(general["BADNICK_DELETED"].format(badnick, trigger.sender))


def badnicks(bot, trigger):
    if trigger.group(3) == "mostrar":
        _show(bot, trigger)
    elif trigger.group(3) == "activar":
        _toggle(bot, trigger)
    elif trigger.group(3) == "desactivar":
        _toggle(bot, trigger, activate=False)
    elif trigger.group(3) == "agregar":
        if trigger.group(4) is None:
            bot.say(errors["NICK_NOT_SPECIFIED"])
            bot.say(f"Ejemplo: {trigger.group(1)} agregar {bot.nick}")
        else:
            _add(bot, trigger, trigger.group(4))
    elif trigger.group(3) == "borrar":
        if trigger.group(4) is None:
            bot.say(errors["NICK_NOT_SPECIFIED"])
            bot.say(f"Ejemplo: {trigger.group(1)} borrar {bot.nick}")
        else:
            _delete(bot, trigger, trigger.group(4))
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


def match_badnick(bot, trigger):
    def _filter_nicks(nick: str) -> bool:
        return nick.lower() == trigger.sender.lower()

    for channel in bot.memory["badnicks"]:
        if bot.memory["channels"][channel]["badnicks"]:
            badnick = tuple(filter(_filter_nicks, bot.memory["badnicks"][channel]))
            if len(badnick) > 0:
                bot.write(("KICK", channel, badnick[0]), "tu nick es inapropiado!")


def user_join(bot, trigger):
    if (
        trigger.nick != bot.nick
        and bot.memory["channels"][trigger.sender.lower()]["badnicks"]
        and trigger.nick.lower() in bot.memory["badnicks"][trigger.sender.lower()]
    ):
        bot.write(
            ("KICK", trigger.sender.lower(), trigger.nick), "tu nick es inapropiado!"
        )
