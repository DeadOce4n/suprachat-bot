import re
import sched
import time

from mariadb import IntegrityError, ProgrammingError
from sopel.formatting import CONTROL_COLOR as COLOR
from sopel.formatting import colors
from sopel.plugin import VOICE

from ..strings import errors, general, queries
from ..utils.func import get_db

RED = colors.RED
GREEN = colors.GREEN


def _show(bot, trigger):
    if not bot.memory["channels"][trigger.sender.lower()]["badwords"]:
        bot.say(errors["BADWORDS_NOT_ENABLED"].format(trigger.sender))
    elif len(bot.memory["badwords"][trigger.sender.lower()]) == 0:
        bot.say(errors["NO_BADWORDS"].format(trigger.sender))
    else:
        bot.say(general["BADWORDS_IN_LIST"].format(trigger.sender), trigger.nick)
        for word in bot.memory["badwords"][trigger.sender.lower()]:
            bot.say(f"- {word}", trigger.nick)


def _toggle(bot, trigger, activate=True):
    if activate == True and bot.memory["channels"][trigger.sender.lower()]["badwords"]:
        bot.say(errors["BADWORDS_ENABLED"].format(trigger.sender))
    elif (
        activate == False
        and not bot.memory["channels"][trigger.sender.lower()]["badwords"]
    ):
        bot.say(errors["BADWORDS_DISABLED"].format(trigger.sender))
    else:
        try:
            conn = get_db(bot.settings)
            cursor = conn.cursor()
            cursor.execute(
                queries["TOGGLE_BADWORDS"],
                (activate, trigger.sender.lower()),
            )
        except ProgrammingError as err:
            print(errors["DB_ERROR"].format(err))
        else:
            conn.commit()
            conn.close()
            bot.memory["channels"][trigger.sender.lower()]["badwords"] = not bot.memory[
                "channels"
            ][trigger.sender.lower()]["badwords"]
            bot.say(
                general["TOGGLED_BADWORDS"].format(
                    "" if activate else "des", trigger.sender
                )
            )


def _add(bot, trigger, badword):
    if not bot.memory["channels"][trigger.sender.lower()]["badwords"]:
        bot.say(errors["BADWORDS_NOT_ENABLED"].format(trigger.sender))
    elif badword in bot.memory["badwords"][trigger.sender.lower()]:
        bot.say(errors["BADWORD_EXISTS"].format(trigger.sender))
    else:
        try:
            conn = get_db(bot.settings)
            cursor = conn.cursor()
            cursor.execute(
                queries["ADD_BADWORD"],
                (badword, trigger.sender.lower()),
            )
        except IntegrityError as err:
            bot.say(errors["BADWORD_EXISTS"].format(trigger.sender))
            bot.say(err)
        else:
            conn.commit()
            conn.close()
            bot.memory["badwords"][trigger.sender.lower()].append(badword)
            bot.say(general["BADWORD_ADDED"].format(badword, trigger.sender))


def _delete(bot, trigger, badword):
    if not bot.memory["channels"][trigger.sender.lower()]["badwords"]:
        bot.say(errors["BADWORDS_NOT_ENABLED"].format(trigger.sender))
    elif badword not in bot.memory["badwords"][trigger.sender.lower()]:
        bot.say(errors["BADWORD_NOT_EXISTS"].format(trigger.sender))
    else:
        try:
            conn = get_db(bot.settings)
            cursor = conn.cursor()
            cursor.execute(
                queries["DELETE_BADWORD"],
                (badword, trigger.sender.lower()),
            )
        except ProgrammingError as err:
            bot.say(errors["BADWORD_NOT_EXISTS"])
            bot.say(err)
        else:
            conn.commit()
            conn.close()
            bot.memory["badwords"][trigger.sender.lower()].remove(badword)
            bot.say(general["BADWORD_DELETED"].format(badword, trigger.sender))


def badwords(bot, trigger):
    if trigger.group(3) == "mostrar":
        _show(bot, trigger)
    elif trigger.group(3) == "activar":
        _toggle(bot, trigger)
    elif trigger.group(3) == "desactivar":
        _toggle(bot, trigger, activate=False)
    elif trigger.group(3) == "agregar":
        if trigger.group(4) is None:
            bot.say(errors["WORD_NOT_SPECIFIED"])
            bot.say(f"Ejemplo: {trigger.group(1)} agregar bobo")
        else:
            _add(bot, trigger, trigger.group(4))
    elif trigger.group(3) == "borrar":
        if trigger.group(4) is None:
            bot.say(errors["WORD_NOT_SPECIFIED"])
            bot.say(f"Ejemplo: {trigger.group(1)} borrar menso")
        else:
            _delete(bot, trigger, trigger.group(4))
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


def _handle_mute(bot, trigger):
    if bot.channels[trigger.sender].privileges[trigger.nick] == VOICE:
        if trigger.account is None:
            bot.write(("MODE", trigger.sender.lower(), "-v", trigger.nick))
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
        else:
            bot.write(("MODE", trigger.sender.lower(), "-v", trigger.nick))
            bot.write(("CS", "amode", trigger.sender.lower(), "-v", trigger.nick))
            bot.write(("MODE", trigger.sender.lower(), "+b", f"m:*!*@{trigger.host}"))
            s = sched.scheduler(time.monotonic, time.sleep)

            def unmute_avoice():
                bot.write(
                    ("MODE", trigger.sender.lower(), "-b", f"m:*!*@{trigger.host}")
                )
                bot.write(("CS", "amode", trigger.sender.lower(), "+v", trigger.nick))

            s.enter(120.0, 1, unmute_avoice)
            s.run()
    elif bot.channels[trigger.sender].privileges[trigger.nick] < VOICE:
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


def match_badword(bot, trigger):
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
                    _handle_mute(bot, trigger)
                    break
