from mariadb import Error as MariaDBError

from ..strings import errors, queries
from ..utils.func import get_db

def bot_join(bot, trigger):
    if (
        trigger.nick == bot.nick
        and trigger.sender.lower() not in bot.memory["channels"].keys()
    ):
        try:
            conn = get_db(bot.settings)
            cursor = conn.cursor()
            cursor.execute(queries["JOIN_CHANNEL"], (trigger.sender.lower(),))
        except MariaDBError as err:
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
