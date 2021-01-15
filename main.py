import argparse
import datetime
import json
import sys
import time

import pika
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater, CallbackQueryHandler

from lib.config import Config
from lib.consts import *
from lib.utility import get_logger

global class_list
global out_channel
global creation_process
global deletion_process
global characters
global updater
global queue_logger
global telegram_logger
global config
global is_shutdown


def start(update, context):
    global telegram_logger
    reply_markup = InlineKeyboardMarkup(main_keyboard(update.effective_chat.id))
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm idle rpg bot", reply_markup=reply_markup)
    telegram_logger.info("Proceed start command from user {0}".format(update.effective_chat.id))


def class_keyboard():
    keyboard = [[]]
    for i in class_list:
        if len(keyboard[len(keyboard) - 1]) > 4:
            keyboard.append([])
        keyboard[len(keyboard) - 1].append(InlineKeyboardButton(i, callback_data="class_" + str(i)), )
    return keyboard


def main_keyboard(chat_id):
    global config
    keyboard = [
        [InlineKeyboardButton("New character", callback_data=MAIN_MENU_CREATE),
         InlineKeyboardButton("About", callback_data=MAIN_MENU_ABOUT),
         InlineKeyboardButton("Delete character", callback_data=MAIN_MENU_DELETE),
         ],
        [
            InlineKeyboardButton("Get status", callback_data=MAIN_MENU_STATUS),
        ],
    ]
    if chat_id in config.admin_list:
        keyboard.append(
            [
                InlineKeyboardButton("Admin...", callback_data=MAIN_MENU_ADMIN),
            ]
        )

    return keyboard


def admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("Server stats", callback_data=ADMIN_MENU_STATS),
         InlineKeyboardButton("Shutdown...", callback_data=ADMIN_MENU_SHUTDOWN_BASIC),
         ]
    ]

    return keyboard


def shutdown_keyboard():
    keyboard = [
        [InlineKeyboardButton("Shutdown normal", callback_data=SHUTDOWN_MENU_NORMAL),
         InlineKeyboardButton("Shutdown immediate", callback_data=SHUTDOWN_MENU_IMMEDIATE),
         InlineKeyboardButton("Shutdown bot", callback_data=SHUTDOWN_MENU_BOT), ]
    ]

    return keyboard


def status(update, context):
    global telegram_logger
    cmd = {"user_id": update.effective_chat.id, "cmd_type": CMD_GET_CHARACTER_STATUS}
    enqueue_command(cmd)
    context.bot.send_message(chat_id=update.effective_chat.id, text="Status requested")
    telegram_logger.info("Proceed status command from user {0}".format(update.effective_chat.id))


def create(update, context):
    global creation_process
    global telegram_logger
    keyboard = class_keyboard()
    reply_markup = InlineKeyboardMarkup(keyboard)
    creation_process[update.effective_chat.id] = {"stage": STAGE_SELECT_CLASS}
    context.bot.send_message(chat_id=update.effective_chat.id, text="Choose your class", reply_markup=reply_markup)
    telegram_logger.info("Initialized character creation from user {0}".format(update.effective_chat.id))


def delete(update, context):
    global deletion_process
    global telegram_logger
    deletion_process[update.effective_chat.id] = {"stage": STAGE_CONFIRM_DELETION}
    context.bot.send_message(chat_id=update.effective_chat.id, text="Print 'CONFIRM' (all capitals) to continue")
    telegram_logger.info("Initialized character deletion from user {0}".format(update.effective_chat.id))


def about(update, context):
    global telegram_logger
    keyboard = main_keyboard(update.effective_chat.id)
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text=MENU_ABOUT_TEXT, reply_markup=reply_markup)
    telegram_logger.info("Sent \"About\" to user {0}".format(update.effective_chat.id))


def admin(update, context):
    global telegram_logger
    global config
    if update.effective_chat.id in config.admin_list:
        keyboard = admin_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Admin panel", reply_markup=reply_markup)
        telegram_logger.info("Sent \"Admin menu\" to user {0}".format(update.effective_chat.id))
    else:
        telegram_logger.error("Illegal access to \"Admin menu\" from user {0}".format(update.effective_chat.id))


def shutdown(update, context):
    global telegram_logger
    global config
    if update.effective_chat.id in config.admin_list:
        keyboard = shutdown_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Shutdown panel", reply_markup=reply_markup)
        telegram_logger.info("Sent \"shutdown menu\" to user {0}".format(update.effective_chat.id))
    else:
        telegram_logger.error("Illegal access to \"shutdown menu\" from user {0}".format(update.effective_chat.id))


def ask_server_stats(update, context):
    global telegram_logger
    global config
    if update.effective_chat.id in config.admin_list:
        cmd = {"user_id": update.effective_chat.id, "cmd_type": CMD_GET_SERVER_STATS}
        enqueue_command(cmd, True)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Server stats requested",)
        telegram_logger.info("Sent server stats request from user {0}".format(update.effective_chat.id))
    else:
        telegram_logger.error("Illegal access ti \"ask_server_stats\" from user {0}".format(update.effective_chat.id))


def send_shutdown_immediate(update, context):
    global telegram_logger
    global config
    if update.effective_chat.id in config.admin_list:
        cmd = {"user_id": update.effective_chat.id, "cmd_type": CMD_SERVER_SHUTDOWN_IMMEDIATE}
        enqueue_command(cmd, True)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Sent command on immediate shutdown",)
        telegram_logger.info("Sent command on immediate shutdown from user {0}".format(update.effective_chat.id))
    else:
        telegram_logger.error("Illegal access ti \"send_shutdown_immediate\" from user {0}".format(update.effective_chat.id))


def send_shutdown_bot(update, context):
    global telegram_logger
    global config
    global is_shutdown
    if update.effective_chat.id in config.admin_list:
        telegram_logger.info("Shutdown requested")
        context.bot.send_message(chat_id=update.effective_chat.id, text="Ok", )
        is_shutdown = True
    else:
        telegram_logger.error("Illegal access ti \"send_shutdown_bot\" from user {0}".format(update.effective_chat.id))


def send_shutdown_normal(update, context):
    global telegram_logger
    global config
    if update.effective_chat.id in config.admin_list:
        cmd = {"user_id": update.effective_chat.id, "cmd_type": CMD_SERVER_SHUTDOWN_NORMAL}
        enqueue_command(cmd, True)
        context.bot.send_message(chat_id=update.effective_chat.id, text="Sent command on shutdown",)
        telegram_logger.info("Sent command on shutdown from user {0}".format(update.effective_chat.id))
    else:
        telegram_logger.error("Illegal access ti \"send_shutdown_normal\" from user {0}".format(update.effective_chat.id))


def class_menu(update, context):
    global creation_process
    global telegram_logger
    is_correct = False
    if update.effective_chat.id in creation_process.keys():
        if creation_process[update.effective_chat.id]["stage"] == STAGE_SELECT_CLASS:
            is_correct = True
    if is_correct:
        char_class = update["callback_query"]["data"][6:]
        creation_process[update.effective_chat.id]["class"] = char_class
        creation_process[update.effective_chat.id]["stage"] = STAGE_CHOOSE_NAME
        context.bot.send_message(chat_id=update.effective_chat.id, text="You choose {0}, please, enter name".
                                 format(char_class))
        telegram_logger.info("Character creation by user {0} advanced to name input stage".
                             format(update.effective_chat.id))
    else:
        telegram_logger.warning("Character creation by user {0} not advanced to name input stage because of reasons".
                                format(update.effective_chat.id))


def main_menu(update, context):
    global telegram_logger
    global config
    cur_item = update["callback_query"]["data"]
    telegram_logger.info("Received command {0} from user {1} in main menu".
                         format(cur_item, update.effective_chat.id))
    if cur_item == MAIN_MENU_CREATE:
        create(update, context)
    elif cur_item == MAIN_MENU_STATUS:
        status(update, context)
    elif cur_item == MAIN_MENU_DELETE:
        delete(update, context)
    elif cur_item == MAIN_MENU_ABOUT:
        about(update, context)
    elif cur_item == MAIN_MENU_ADMIN:
        if update.effective_chat.id in config.admin_list:
            admin(update, context)
        else:
            telegram_logger.error("Received admin command {0} from ordinary user {1} in main menu".
                                  format(cur_item, update.effective_chat.id))
    else:
        telegram_logger.error("Received unknown command {0} from user {1} in main menu".
                              format(cur_item, update.effective_chat.id))
        context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown command")


def admin_menu(update, context):
    global telegram_logger
    cur_item = update["callback_query"]["data"]
    telegram_logger.info("Received command {0} from user {1} in admin menu".
                         format(cur_item, update.effective_chat.id))
    if cur_item == ADMIN_MENU_STATS:
        ask_server_stats(update, context)
    elif cur_item == ADMIN_MENU_SHUTDOWN_BASIC:
        shutdown(update, context)
    else:
        telegram_logger.error("Received unknown command {0} from user {1} in admin menu".
                              format(cur_item, update.effective_chat.id))
        context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown command")


def shutdown_menu(update, context):
    global telegram_logger
    cur_item = update["callback_query"]["data"]
    telegram_logger.info("Received command {0} from user {1} in shutdown menu".
                         format(cur_item, update.effective_chat.id))
    if cur_item == SHUTDOWN_MENU_NORMAL:
        send_shutdown_normal(update, context)
    elif cur_item == SHUTDOWN_MENU_IMMEDIATE:
        send_shutdown_immediate(update, context)
    elif cur_item == SHUTDOWN_MENU_BOT:
        send_shutdown_bot(update, context)
    else:
        telegram_logger.error("Received unknown command {0} from user {1} in shutdown menu".
                              format(cur_item, update.effective_chat.id))
        context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown command")


def enqueue_command(obj, system=False):
    global queue_logger
    global config
    if system:
        queue_name = QUEUE_NAME_INIT
    else:
        queue_name = QUEUE_NAME_CMD
    msg_body = json.dumps(obj)
    try:
        queue = get_mq_connect(config)
        channel = queue.channel()
        channel.basic_publish(exchange="", routing_key=queue_name,
                              body=msg_body, properties=pika.BasicProperties(delivery_mode=2,
                                                                             content_type="application/json",
                                                                             content_encoding="UTF-8",
                                                                             app_id=QUEUE_APP_ID))
        queue.close()
        queue_logger.info("Sent command {0} in queue {1}".format(msg_body, queue))
    except pika.exceptions.AMQPError as exc:
        queue_logger.critical("Error {2} when Sent command {0} in queue {1}".format(msg_body, queue_name, exc))


def echo(update, context):
    global creation_process
    global deletion_process
    global telegram_logger
    telegram_logger.debug("Echo: update: {0}, context {1}".format(update, context))
    is_correct = False
    if update.effective_chat.id in creation_process.keys():
        if creation_process[update.effective_chat.id]["stage"] == STAGE_CHOOSE_NAME:
            is_correct = True
    if is_correct:
        creation_process[update.effective_chat.id]["stage"] = "confirm"
        creation_process[update.effective_chat.id]["name"] = update["message"]["text"]
        context.bot.send_message(chat_id=update.effective_chat.id, text="Let me check if name is free...")
        cmd = {"user_id": update.effective_chat.id, "cmd_type": CMD_CREATE_CHARACTER,
               "name": creation_process[update.effective_chat.id].get("name"),
               "class": creation_process[update.effective_chat.id].get("class")}
        enqueue_command(cmd)
    elif update.effective_chat.id in deletion_process.keys():
        if deletion_process[update.effective_chat.id]["stage"] == STAGE_CONFIRM_DELETION:
            if update["message"]["text"] == "CONFIRM":
                cmd = {"user_id": update.effective_chat.id, "cmd_type": CMD_DELETE_CHARACTER}
                enqueue_command(cmd)
                context.bot.send_message(chat_id=update.effective_chat.id, text="Try to delete character...")
            else:
                del deletion_process[update.effective_chat.id]
                context.bot.send_message(chat_id=update.effective_chat.id, text="Operation canceled...")
                start(update, context)

    else:
        telegram_logger.info("User {0} sent message {1}".format(update.effective_chat.id, update.message.text))


def class_list_callback(ch, method, properties, body):
    global class_list
    class_list = json.loads(body).get("class_list")


def dict_response_callback(ch, method, properties, body):
    global queue_logger
    queue_logger.info("Received server command " + str(body) + ", started callback")
    msg = json.loads(body)
    cmd_type = msg.get("cmd_type")
    chat_id = msg.get("user_id")
    if cmd_type == CMD_SET_CLASS_LIST:
        class_list_callback(ch, method, properties, body)
    elif cmd_type == CMD_SET_SERVER_STATS:
        reply_markup = InlineKeyboardMarkup(admin_keyboard())
        updater.dispatcher.bot.send_message(chat_id=chat_id, text=msg.get("server_info"), reply_markup=reply_markup)
    elif cmd_type == CMD_SERVER_OK:
        reply_markup = InlineKeyboardMarkup(admin_keyboard())
        updater.dispatcher.bot.send_message(chat_id=chat_id, text=msg, reply_markup=reply_markup)
    else:
        if chat_id is not None:
            updater.dispatcher.bot.send_message(chat_id=chat_id, text="Unknown message".format(msg))
        queue_logger.error("Received unknown server command " + str(body) + ", started callback")


def cmd_response_callback(ch, method, properties, body):
    global creation_process
    global deletion_process
    global updater
    global queue_logger
    queue_logger.info("Received command " + str(body) + ", started callback")
    msg = json.loads(body)
    chat_id = msg.get("user_id")
    reply_markup = InlineKeyboardMarkup(main_keyboard(chat_id))
    if chat_id is not None:
        if msg.get("cmd_type") == CMD_GET_CHARACTER_STATUS:
            updater.dispatcher.bot.send_message(chat_id=chat_id, text=msg.get("char_info"), reply_markup=reply_markup)
        else:
            updater.dispatcher.bot.send_message(chat_id=chat_id, text=msg.get("message"), reply_markup=reply_markup)
            queue_logger.info("Sent message {0}, received from server to user {1}".format(msg.get("message"), chat_id))
        # clear current operations state, if any
        if chat_id in creation_process.keys():
            del creation_process[chat_id]
        if chat_id in deletion_process.keys():
            del deletion_process[chat_id]


def get_mq_connect(config):
    if config.queue_password is None:
        return pika.BlockingConnection(pika.ConnectionParameters(host=config.queue_host, port=config.queue_port))
    else:
        return pika.BlockingConnection(pika.ConnectionParameters(host=config.queue_host, port=config.queue_port,
                                                                 credentials=pika.credentials.PlainCredentials(
                                                                     config.queue_user, config.queue_password)))


def main():
    global class_list
    global creation_process
    global deletion_process
    global characters
    global out_channel
    global updater
    global queue_logger
    global telegram_logger
    global config
    global is_shutdown

    is_shutdown = False
    class_list = None
    creation_process = {}
    deletion_process = {}
    characters = {}
    parser = argparse.ArgumentParser(description='Idle RPG telegram bot.')
    parser.add_argument("--config", '-cfg', help="Path to config file", action="store", default="cfg//main.json")
    parser.add_argument("--test_users", help="Number of test users of each class created", action="store", default=None)
    parser.add_argument("--delay", help="Number of test users of each class created", action="store", default=None)
    args = parser.parse_args()
    if args.delay is not None:
        time.sleep(int(args.delay))
    config = Config(args.config)

    logger = get_logger(LOG_MAIN, config.log_level)
    queue_logger = get_logger(LOG_QUEUE, config.log_level)
    telegram_logger = get_logger(LOG_TELEGRAM, config.log_level)
    # set_basic_logging(config.log_level)
    updater = Updater(token=config.secret, use_context=True)
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start', start)
    create_handler = CommandHandler('create', create)
    class_menu_handler = CallbackQueryHandler(class_menu, pattern="class_")
    main_menu_handler = CallbackQueryHandler(main_menu, pattern="main_")
    admin_menu_handler = CallbackQueryHandler(admin_menu, pattern="admin_")
    shutdown_menu_handler = CallbackQueryHandler(shutdown_menu, pattern="shutdown_")
    echo_handler = MessageHandler(Filters.text & (~Filters.command), echo)
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(create_handler)
    dispatcher.add_handler(main_menu_handler)
    dispatcher.add_handler(echo_handler)
    dispatcher.add_handler(class_menu_handler)
    dispatcher.add_handler(admin_menu_handler)
    dispatcher.add_handler(shutdown_menu_handler)

    out_queue = get_mq_connect(config)
    out_channel = out_queue.channel()
    out_channel.queue_declare(queue=QUEUE_NAME_INIT)
    out_channel.queue_declare(queue=QUEUE_NAME_CMD, durable=True)
    out_channel.queue_declare(queue=QUEUE_NAME_RESPONSES, durable=True)
    out_channel.queue_declare(queue=QUEUE_NAME_DICT, durable=True)

    msg = {"cmd_type": CMD_GET_CLASS_LIST}
    out_channel.basic_publish(exchange="", routing_key=QUEUE_NAME_INIT, body=json.dumps(msg),
                              properties=pika.BasicProperties(content_type="application/json",
                                                              content_encoding="UTF-8",
                                                              app_id=QUEUE_APP_ID))

    logger.info("Asked server for class list")

    out_channel.basic_consume(queue=QUEUE_NAME_DICT, on_message_callback=dict_response_callback, auto_ack=True)

    for method_frame, properties, body in out_channel.consume(QUEUE_NAME_DICT, inactivity_timeout=1):
        if class_list is not None:
            break
    out_channel.cancel()
    logger.info("Class list received")

    if args.test_users is not None:
        test_start_time = datetime.datetime.now()
        cnt_users = 0
        logger.info("Started create test users")
        for i in range(int(args.test_users)):
            for j in class_list:
                cmd = {"cmd_type": CMD_CREATE_CHARACTER, "name": j + '_' + str(i + 1), "class": j}
                cnt_users += 1
                enqueue_command(cmd)
        test_finish_time = datetime.datetime.now()
        logger.info("Finish create test users, was created {}. Started at {}, finish at {}".format(cnt_users,
                                                                                                   test_start_time,
                                                                                                   test_finish_time))

    updater.start_polling()

    logger.info("Start listen server responses")
    while True:
        for method_frame, properties, body in out_channel.consume(QUEUE_NAME_RESPONSES, inactivity_timeout=5,
                                                                  auto_ack=False):
            if body is not None:
                logger.info("Received message {0} with delivery_tag {1}".format(body, method_frame.delivery_tag))
                cmd_response_callback(None, method_frame, properties, body)
                out_channel.basic_ack(method_frame.delivery_tag)
                logger.info("Received message " + str(body) + " with delivery_tag " + str(method_frame.delivery_tag) +
                            " acknowledged")
            else:
                logger.info("No more messages in {}".format(QUEUE_NAME_RESPONSES))
                out_channel.cancel()
                break
        for method_frame, properties, body in out_channel.consume(QUEUE_NAME_DICT, inactivity_timeout=5,
                                                                  auto_ack=False):
            if body is not None:
                logger.info("Received message {0} with delivery_tag {1}".format(body, method_frame.delivery_tag))
                cmd_response_callback(None, method_frame, properties, body)
                out_channel.basic_ack(method_frame.delivery_tag)
                logger.info("Received message " + str(body) + " with delivery_tag " + str(method_frame.delivery_tag) +
                            " acknowledged")
            else:
                logger.info("No more messages in {}".format(QUEUE_NAME_DICT))
                out_channel.cancel()
                break
        # should be in QUEUE_NAME_DICT listener, but to make things easier put it here
        if is_shutdown:
            updater.stop()
            sys.exit(0)


if __name__ == '__main__':
    main()
