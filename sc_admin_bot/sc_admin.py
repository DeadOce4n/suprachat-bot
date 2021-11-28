import re
import sched
from sys import exit
import time

import mariadb
from sopel import config, formatting, plugin
from sopel.tools import SopelMemory

settings = config.Config("/home/ivan/.sopel/default.cfg")
NOT_ALLOWED = "No tienes permitido usar este comando."
COLOR = formatting.CONTROL_COLOR
GREEN = formatting.colors.GREEN
RED = formatting.colors.RED
BOLD = formatting.CONTROL_BOLD


def get_db():
    conn_params = {
        "user": settings.ScAdmin.db_user,
        "password": settings.ScAdmin.db_password,
        "host": settings.ScAdmin.db_host,
        "database": settings.ScAdmin.db_name,
    }
    try:
        conn = mariadb.connect(**conn_params)
    except mariadb.Error as err:
        print(f"Error connecting to MariaDB engine: {err}")
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

    conn = get_db()
    cursor = conn.cursor(named_tuple=True)
    cursor.execute("SELECT * FROM channel;")

    for row in cursor:
        if row.channel_name not in bot.memory["channels"]:
            bot.memory["channels"][row.channel_name] = {}
            bot.memory["badwords"][row.channel_name] = []
            bot.memory["badnicks"][row.channel_name] = []
            bot.memory["rules"][row.channel_name] = {}
        bot.memory["channels"][row.channel_name]["badwords"] = row.badwords_enabled
        bot.memory["channels"][row.channel_name]["badnicks"] = row.badnicks_enabled
        bot.memory["channels"][row.channel_name]["rules"] = row.rules_enabled

    cursor.execute(
        "SELECT badword.badword, channel.channel_name FROM badword JOIN"
        " channel ON badword.channel_id = channel.channel_id;"
    )

    for row in cursor:
        if row.channel_name not in bot.memory["badwords"].keys():
            bot.memory["badwords"][row.channel_name] = []
        bot.memory["badwords"][row.channel_name].append(row.badword)

    cursor.execute(
        "SELECT badnick.badnick, channel.channel_name FROM badnick JOIN"
        " channel ON badnick.channel_id = channel.channel_id;"
    )

    for row in cursor:
        if row.channel_name not in bot.memory["badnicks"].keys():
            bot.memory["badnicks"][row.channel_name] = []
        bot.memory["badnicks"][row.channel_name].append(row.badnick.lower())

    cursor.execute(
        "SELECT rule.rule_number, rule.rule_desc, channel.channel_name FROM"
        " rule JOIN channel ON rule.channel_id = channel.channel_id ORDER BY"
        " rule.rule_number ASC;"
    )

    for row in cursor:
        if row.channel_name not in bot.memory["rules"].keys():
            bot.memory["rules"][row.channel_name] = {}
        bot.memory["rules"][row.channel_name][row.rule_number] = row.rule_desc

    conn.close()


def configure(bot):
    config.define_section("ScAdmin", ScAdminSection, validate=False)


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
        print(bot.nick)
        print(trigger.sender.lower())
        try:
            conn = get_db()
            cursor = conn.cursor(named_tuple=True)
            cursor.execute(
                "INSERT INTO channel(channel_name) VALUE(?);", (trigger.sender.lower(),)
            )
        except mariadb.Error as err:
            bot.say(f"Error: {err}", bot.owner)
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
@plugin.require_privilege(plugin.ADMIN, NOT_ALLOWED)
@plugin.command("badwords", "bw")
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def badwords(bot, trigger):
    def show():
        if not bot.memory["channels"][trigger.sender.lower()]["badwords"]:
            bot.say(
                f"Error: la moderación de palabras no está activada para esta sala."
            )
        elif len(bot.memory["badwords"][trigger.sender.lower()]) == 0:
            bot.say(
                f"Error: no hay palabras en lista negra para la sala {trigger.sender}"
            )
        else:
            bot.say(f"Palabras en lista negra para la sala {trigger.sender}")
            for word in bot.memory["badwords"][trigger.sender.lower()]:
                bot.say(f"- {word}")

    def toggle(activate=True):
        if (
            activate == True
            and bot.memory["channels"][trigger.sender.lower()]["badwords"]
        ):
            bot.say(
                f"Error: la moderación de palabras ya está activada para la sala {trigger.sender}."
            )
        elif (
            activate == False
            and not bot.memory["channels"][trigger.sender.lower()]["badwords"]
        ):
            bot.say(
                f"Error: la moderación de palabras ya está desactivada para la sala {trigger.sender}."
            )
        else:
            try:
                conn = get_db()
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    "UPDATE channel SET channel.badwords_enabled = ? WHERE"
                    " channel.channel_id = (SELECT channel_id FROM channel"
                    " WHERE channel_name = ?)",
                    (activate, trigger.sender.lower()),
                )
            except mariadb.ProgrammingError as err:
                print(f"Error: {err}")
            else:
                conn.commit()
                conn.close()
                bot.memory["channels"][trigger.sender.lower()][
                    "badwords"
                ] = not bot.memory["channels"][trigger.sender.lower()]["badwords"]
                bot.say(f"La operación {trigger.group(3)} se realizó con éxito.")

    def add(badword):
        if not bot.memory["channels"][trigger.sender.lower()]["badwords"]:
            bot.say(
                f"Error: la moderación de palabras no está activada para esta sala."
            )
        elif badword in bot.memory["badwords"][trigger.sender.lower()]:
            bot.say(f"Error: esa palabra ya está en la lista de {trigger.sender}")
        else:
            try:
                conn = get_db()
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    "INSERT INTO badword VALUES(?, (SELECT channel_id FROM"
                    " channel WHERE channel_name = ?))",
                    (badword, trigger.sender.lower()),
                )
            except mariadb.IntegrityError as err:
                bot.say(
                    f"Error: la palabra {badword} ya está en la lista de {trigger.sender}"
                )
                bot.say(err)
            else:
                conn.commit()
                conn.close()
                bot.memory["badwords"][trigger.sender.lower()].append(badword)
                bot.say(f"La operación {trigger.group(3)} se realizó con éxito.")

    def delete(badword):
        if not bot.memory["channels"][trigger.sender.lower()]["badwords"]:
            bot.say(
                f"Error: la moderación de palabras no está activada para esta sala."
            )
        elif badword not in bot.memory["badwords"][trigger.sender.lower()]:
            bot.say(
                f"Error: la palabra {badword} no se encuentra en la lista de {trigger.sender}"
            )
        else:
            try:
                conn = get_db()
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    "DELETE FROM badword WHERE(badword.badword = ? AND badword"
                    ".channel_id = (SELECT channel_id FROM channel WHERE"
                    " channel_name = ?))",
                    (badword, trigger.sender.lower()),
                )
            except mariadb.ProgrammingError as err:
                bot.say(
                    f"Error: la palabra {badword} ya está en la lista de {trigger.sender}"
                )
                bot.say(err)
            else:
                conn.commit()
                conn.close()
                bot.memory["badwords"][trigger.sender.lower()].remove(badword)
                bot.say(f"La operación {trigger.group(3)} se realizó con éxito.")

    if trigger.group(3) == "mostrar":
        show()
    elif trigger.group(3) == "activar":
        toggle()
    elif trigger.group(3) == "desactivar":
        toggle(activate=False)
    elif trigger.group(3) == "agregar":
        if trigger.group(4) is None:
            bot.say("Error: no se especificó palabra.")
            bot.say(f"Ejemplo: {trigger.group(1)} agregar bobo")
        else:
            add(trigger.group(4))
    elif trigger.group(3) == "borrar":
        if trigger.group(4) is None:
            bot.say("Error: no se especificó palabra.")
            bot.say(f"Ejemplo: {trigger.group(1)} borrar menso")
        else:
            delete(trigger.group(4))
    else:
        bot.say(f"Error: comando {trigger.group(3)} desconocido.")


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
                regex = re.compile(fr"\b({word})+\b", re.I)
                match = re.search(regex, msg)
                if match is not None:
                    bot.say(
                        f"{trigger.nick}, la palabra {COLOR}{RED}{word}{COLOR}{GREEN} está prohibida, te vas muteado!"
                    )
                    handle_mute()
                    break


@plugin.require_chanmsg
@plugin.require_privilege(plugin.ADMIN, NOT_ALLOWED)
@plugin.command("badnicks", "bn")
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def badnicks(bot, trigger):
    def show():
        if not bot.memory["channels"][trigger.sender.lower()]["badnicks"]:
            bot.say(f"Error: la moderación de nicks no está activada para esta sala.")
        elif len(bot.memory["badnicks"][trigger.sender.lower()]) == 0:
            bot.say(
                f"Error: no hay nicks en lista negra para la sala {trigger.sender}."
            )
        else:
            bot.say(f"Nicks en lista negra para la sala {trigger.sender}:")
            for nick in bot.memory["badnicks"][trigger.sender.lower()]:
                bot.say(nick)

    def toggle(activate=True):
        if (
            activate == True
            and bot.memory["channels"][trigger.sender.lower()]["badnicks"]
        ):
            bot.say(
                f"Error: la moderación de nicks ya está activada para la sala {trigger.sender}."
            )
        elif (
            activate == False
            and not bot.memory["channels"][trigger.sender.lower()]["badnicks"]
        ):
            bot.say("Error: la moderación de nicks ya está desactivada para esta sala.")
        else:
            try:
                conn = get_db()
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    "UPDATE channel SET channel.badnicks_enabled = ? WHERE"
                    " channel.channel_id = (SELECT channel_id FROM channel"
                    " WHERE channel_name = ?)",
                    (activate, trigger.sender.lower()),
                )
            except mariadb.ProgrammingError as err:
                print(f"Error: {err}")
            else:
                conn.commit()
                conn.close()
                bot.memory["channels"][trigger.sender.lower()][
                    "badnicks"
                ] = not bot.memory["channels"][trigger.sender.lower()]["badnicks"]
                bot.say(f"La operación {trigger.group(3)} se realizó con éxito.")
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
            bot.say(f"Error: la moderación de nicks no está activada para esta sala.")
        elif badnick.lower() in bot.memory["badnicks"][trigger.sender.lower()]:
            bot.say(
                f"Error: el nick {badnick} ya está en la lista de {trigger.sender}."
            )
        else:
            try:
                conn = get_db()
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    "INSERT INTO badnick VALUES(?, (SELECT channel_id FROM"
                    " channel WHERE (LOWER(channel_name) = ?)))",
                    (badnick.lower(), trigger.sender.lower()),
                )
            except mariadb.IntegrityError as err:
                bot.say(
                    f"Error: el nick {badnick} ya está en la lista de {trigger.sender}."
                )
                bot.say(err)
            else:
                conn.commit()
                conn.close()
                bot.memory["badnicks"][trigger.sender.lower()].append(badnick.lower())
                bot.say(f"La operación {trigger.group(3)} se realizó con éxito.")
                users = {k: v for k, v in bot.channels[trigger.sender].users.items()}
                for nick in users.keys():
                    if nick in bot.memory["badnicks"][trigger.sender.lower()]:
                        bot.write(
                            ("KICK", trigger.sender.lower(), nick),
                            "tu nick es inapropiado!",
                        )

    def delete(badnick):
        if not bot.memory["channels"][trigger.sender.lower()]["badnicks"]:
            bot.say(f"Error: la moderación de nicks no está activada para esta sala.")
        if badnick.lower() not in bot.memory["badnicks"][trigger.sender.lower()]:
            bot.say(
                f"Error: el nick {badnick} no se encuentra en la lista de {trigger.sender}."
            )
        else:
            try:
                conn = get_db()
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    "DELETE FROM badnick WHERE(badnick.badnick = ? AND badnick"
                    ".channel_id = (SELECT channel_id FROM channel WHERE"
                    " channel_name = ?));",
                    (badnick.lower(), trigger.sender.lower()),
                )
            except mariadb.Error as err:
                bot.say(
                    f"Error: el nick {badnick} ya está en la lista de {trigger.sender}."
                )
                bot.say(err)
            else:
                conn.commit()
                conn.close()
                bot.memory["badnicks"][trigger.sender.lower()].remove(badnick.lower())
                bot.say(f"La operación {trigger.group(3)} se realizó con éxito.")

    if trigger.group(3) == "mostrar":
        show()
    elif trigger.group(3) == "activar":
        toggle()
    elif trigger.group(3) == "desactivar":
        toggle(activate=False)
    elif trigger.group(3) == "agregar":
        if trigger.group(4) is None:
            bot.say("Error: no se especificó palabra.")
            bot.say(f"Ejemplo: {trigger.group(1)} agregar {bot.nick}")
        else:
            add(trigger.group(4))
    elif trigger.group(3) == "borrar":
        if trigger.group(4) is None:
            bot.say("Error: no se especificó nick.")
            bot.say(f"Ejemplo: {trigger.group(1)} borrar {bot.nick}")
        else:
            delete(trigger.group(4))
    else:
        bot.say(f"Error: comando {trigger.group(3)} desconocido.")


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
@plugin.require_privilege(plugin.ADMIN, NOT_ALLOWED)
@plugin.command(
    "reglas agregar", "reglas modificar", "rg agregar", "rg modificar", "reglas", "rg"
)
@plugin.output_prefix(f"{BOLD}{COLOR}{GREEN}")
def rules(bot, trigger):
    def show():
        if not bot.memory["channels"][trigger.sender.lower()]["rules"]:
            bot.say("Error: las reglas no están activadas para esta sala.")
        elif len(bot.memory["rules"][trigger.sender.lower()].items()) == 0:
            bot.say(f"No hay ninguna regla registrada para la sala {trigger.sender}")
        else:
            bot.say(f"Reglas de {trigger.sender}:", trigger.nick)
            for num, desc in bot.memory["rules"][trigger.sender.lower()].items():
                bot.say(f"{num}.- {desc}", trigger.nick)

    def toggle(activate=True):
        if activate == True and bot.memory["channels"][trigger.sender.lower()]["rules"]:
            bot.say(
                f"Error: las reglas ya están activadas para la sala {trigger.sender}."
            )
        elif (
            activate == False
            and not bot.memory["channels"][trigger.sender.lower()]["rules"]
        ):
            bot.say(
                f"Error: las reglas ya están desactivadas para la sala {trigger.sender}."
            )
        else:
            try:
                conn = get_db()
                cursor = conn.cursor(named_tuple=True)
                cursor.execute(
                    "UPDATE channel SET channel.rules_enabled = ? WHERE"
                    " channel.channel_id = (SELECT channel_id FROM channel"
                    " WHERE channel_name = ?)",
                    (activate, trigger.sender.lower()),
                )
            except mariadb.Error as err:
                print(f"Error: {err}")
            else:
                conn.commit()
                conn.close()
                bot.memory["channels"][trigger.sender.lower()][
                    "rules"
                ] = not bot.memory["channels"][trigger.sender.lower()]["rules"]
                bot.say(f"La operación {trigger.group(3)} se realizó con éxito.")

    def add(rule_num: int, rule_desc: str) -> None:
        if not bot.memory["channels"][trigger.sender.lower()]["rules"]:
            bot.say(
                f"Error: las reglas no están activadas para la sala {trigger.sender}"
            )
        elif rule_num in bot.memory["rules"][trigger.sender.lower()].keys():
            bot.say(f"Ya existe la regla {rule_num} para la sala {trigger.sender}")
        else:
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO rule VALUES(?, (SELECT channel.channel_id"
                    " FROM channel WHERE channel.channel_name = ?), ?);",
                    (rule_num, trigger.sender.lower(), rule_desc),
                )
            except mariadb.Error as err:
                bot.say(f"Error: {err}")
            else:
                conn.commit()
                conn.close()
                bot.memory["rules"][trigger.sender.lower()][rule_num] = rule_desc
                bot.say("La regla se agregó correctamente a la base de datos.")

    def update(rule_num: int, rule_desc: str) -> None:
        print(f"{rule_num}, {rule_desc}")
        if not bot.memory["channels"][trigger.sender.lower()]["rules"]:
            bot.say("Error: las reglas no están activadas para esta sala.")
        elif rule_num not in bot.memory["rules"][trigger.sender.lower()].keys():
            bot.say(
                f"Error: no existe la regla {rule_num} para la sala {trigger.sender}"
            )
        else:
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE rule SET rule_desc = ? WHERE (rule.channel_id = (SELECT"
                    " channel_id FROM channel WHERE channel_name = ?) AND rule_number"
                    " = ?);",
                    (rule_desc, trigger.sender.lower(), rule_num),
                )
            except mariadb.Error as err:
                bot.say(f"Error: {err}")
            else:
                conn.commit()
                conn.close()
                bot.memory["rules"][trigger.sender.lower()][rule_num] = rule_desc
                bot.say(f"La operación {trigger.group(3)} se realizó con éxito.")

    def remove(rule_num: int) -> None:
        if not bot.memory["channels"][trigger.sender.lower()]["rules"]:
            bot.say(
                f"Error: las reglas no están activadas para la sala {trigger.sender}."
            )
        elif rule_num not in bot.memory["rules"][trigger.sender.lower()].keys():
            bot.say(
                f"Error: no existe la regla {rule_num} para la sala {trigger.sender}"
            )
        else:
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM rule WHERE(rule_number = ? AND channel_id ="
                    " (SELECT channel_id FROM channel WHERE"
                    " channel_name = ?));",
                    (rule_num, trigger.sender.lower()),
                )
            except mariadb.Error as err:
                bot.say(f"Error: {err}")
            else:
                conn.commit()
                conn.close()
                bot.memory["rules"][trigger.sender.lower()].pop(rule_num)
                bot.say(f"La operación {trigger.group(3)} se realizó con éxito.")

    if trigger.group(3) == "mostrar" or (
        (trigger.group(1) == "rg" or trigger.group(1) == "reglas")
        and trigger.group(3) is None
    ):
        show()

    elif trigger.group(3) == "activar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < plugin.OP:
            bot.say(f"{trigger.nick}, no tienes permiso de ejecutar este comando.")
        else:
            toggle()

    elif trigger.group(3) == "desactivar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < plugin.OP:
            bot.say(f"{trigger.nick}, no tienes permiso de ejecutar este comando.")
        else:
            toggle(activate=False)

    elif trigger.group(1) == "reglas modificar" or trigger.group(1) == "rg modificar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < plugin.OP:
            bot.say(f"{trigger.nick}, no tienes permiso de ejecutar este comando.")
        elif trigger.group(2) is None:
            bot.say("Error: no se especificó número de regla.")
            bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
        else:
            get_rule = re.search(r"(\b\d\b)\b(.*)\b", trigger.group(2))
            if get_rule is None:
                bot.say("Error: no se especificó regla.")
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            elif get_rule.group(1) is None:
                bot.say("Error: no se especificó número de regla.")
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            elif not get_rule.group(2):
                bot.say("Error: no se especificó descripción de regla.")
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            else:
                update(int(get_rule.group(1)), get_rule.group(2).strip())

    elif trigger.group(1) == "reglas agregar" or trigger.group(1) == "rg agregar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < plugin.OP:
            bot.say(f"{trigger.nick}, no tienes permiso de ejecutar este comando.")
        elif trigger.group(2) is None:
            bot.say("Error: no se especificó número de regla.")
            bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
        else:
            get_rule = re.search(r"(\b\d\b)\b(.*)\b", trigger.group(2))
            if get_rule is None:
                bot.say("Error: no se especificó regla.")
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            elif get_rule.group(1) is None:
                bot.say("Error: no se especificó número de regla.")
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            elif not get_rule.group(2):
                bot.say("Error: no se especificó descripción de regla.")
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")
            else:
                add(int(get_rule.group(1)), get_rule.group(2).strip())

    elif trigger.group(3) == "borrar":
        if bot.channels[trigger.sender].privileges[trigger.nick] < plugin.OP:
            bot.say(f"{trigger.nick}, no tienes permiso de ejecutar este comando.")
        else:
            try:
                remove(int(trigger.group(4)))
            except ValueError:
                bot.say(f"Error: {trigger.group(4)} no es un número válido.")
                bot.say(f"Ejemplo: {trigger.group(1)} 1 No decir cosas desagradables.")

    else:
        bot.say(f"Error: comando {trigger.group(3)} desconocido.")


@plugin.interval(600)
def rules_reminder(bot):
    for channel in bot.memory["channels"]:
        if bot.memory["channels"][channel]["rules"]:
            bot.say(
                f"{BOLD}{COLOR}{GREEN}Escribe {COLOR}{RED}!reglas{COLOR}{GREEN} para leer las reglas 📖",
                channel,
            )
