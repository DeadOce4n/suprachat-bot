def invite(bot, trigger):
    if trigger.account:
        bot.join(trigger.sender)
    else:
        bot.notice(
            "Lo siento, solamente usuarios registrados pueden invitarme a una sala 😔",
            trigger.nick,
        )
