import re

from mariadb import Error as MariaDBError
from sopel.plugin import ADMIN, OP

from ..strings import errors, general, queries
from ..utils.func import get_db


def _show(bot, trigger):
    if not bot.memory["channels"][trigger.sender.lower()]["rules"]:
        bot.say(errors["RULES_NOT_ENABLED"].format(trigger.sender))
    elif len(bot.memory["rules"][trigger.sender.lower()].items()) == 0:
        bot.say(errors["NO_RULES"].format(trigger.sender))
    else:
        bot.say(f"Reglas de {trigger.sender}:", trigger.nick)
        for num, desc in bot.memory["rules"][trigger.sender.lower()].items():
            bot.say(f"{num}.- {desc}", trigger.nick)


def _toggle(bot, trigger, activate=True):
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
        except MariaDBError as err:
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

def _add(bot, trigger, rule_num: int, rule_desc: str) -> None:
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
        except MariaDBError as err:
            bot.say(errors["DB_ERROR"].format(err))
        else:
            conn.commit()
            conn.close()
            bot.memory["rules"][trigger.sender.lower()][rule_num] = rule_desc
            bot.say(general["RULE_ADDED"].format(trigger.sender))

def _update(bot, trigger, rule_num: int, rule_desc: str) -> None:
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
        except MariaDBError as err:
            bot.say(errors["DB_ERROR"].format(err))
        else:
            conn.commit()
            conn.close()
            bot.memory["rules"][trigger.sender.lower()][rule_num] = rule_desc
            bot.say(general["RULE_UPDATED"].format(rule_num, trigger.sender))

def _remove(bot, trigger, rule_num: int) -> None:
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
        except MariaDBError as err:
            bot.say(errors["DB_ERROR"].format(err))
        else:
            conn.commit()
            conn.close()
            bot.memory["rules"][trigger.sender.lower()].pop(rule_num)
            bot.say(general["RULE_DELETED"].format(rule_num, trigger.sender))


def rules(bot, trigger):
    if trigger.group(3) == "mostrar":
        _show(bot, trigger)

    elif trigger.group(3) == "activar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < ADMIN:
            bot.say(errors["COMMAND_NOT_ALLOWED"])
        else:
            _toggle(bot, trigger)

    elif trigger.group(3) == "desactivar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < OP:
            bot.say(errors["COMMAND_NOT_ALLOWED"])
        else:
            _toggle(bot, trigger, activate=False)

    elif trigger.group(1) == "reglas modificar" or trigger.group(1) == "rg modificar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < OP:
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
                _update(bot, trigger, int(get_rule.group(1)), get_rule.group(2).strip())

    elif trigger.group(1) == "reglas agregar" or trigger.group(1) == "rg agregar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < OP:
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
                _add(bot, trigger, int(get_rule.group(1)), get_rule.group(2).strip())

    elif trigger.group(3) == "borrar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < OP:
            bot.say(errors["COMMAND_NOT_ALLOWED"])
        else:
            try:
                _remove(bot, trigger, int(trigger.group(4)))
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
