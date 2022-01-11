import argparse
import json
import logging
import os
import random
import telegram

from dotenv import load_dotenv
from functools import partial


from enum import Enum
from textwrap import dedent
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import CommandHandler
from telegram.ext import CallbackQueryHandler
from telegram.ext import ConversationHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

QUIZ = Enum('Quiz', 'Question Answer')
GLOBAL_MESSAGE = dedent(f'''\
    На скорую руку написаный ISTQB тренажер.
    Вопросы взяты из открытых источников.
    Весь код лежит здесь
    https://github.com/Sam1808/ISTQB_trainer
    Замечания/правки/комментарии - приветствуются.
    
    Если проект понравиться:
    - прикручу статистику    
    ''')


def start(update, _):
    custom_keyboard = [['Новый вопрос', 'Сдаться'], ['Капучино автору!']]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True)
    update.message.reply_text(
        'Привет. Готов проверить себя? Начнем!',
        reply_markup=reply_markup
    )
    return QUIZ.Question


def cancel(update, _):
    update.message.reply_text(
        'Пока-пока!',
        reply_markup=telegram.ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def handle_new_question_request(update, context, quiz_qa):
    question_number = random.choice([*quiz_qa.keys()])

    message = f'''\
    {quiz_qa[question_number]['number']}
    {quiz_qa[question_number]['body']}
    Выберите ответ:
    \n'''
    context.user_data['question_number'] = question_number

    keyboard_row = list()

    for number, answer in enumerate(quiz_qa[question_number]['answers']):

        message += dedent(f'''\
    {number+1}. {answer}
    ''')
        keyboard_row.extend([InlineKeyboardButton(str(number+1), callback_data=number)])
    keyboard = [keyboard_row]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if quiz_qa[question_number]['image']:
        file_path = os.path.join('base', quiz_qa[question_number]['image'])
        update.message.reply_photo(
        photo=open(file_path, 'rb'),
        caption=dedent(message),
        reply_markup=reply_markup
        )
    else:
        update.message.reply_text(dedent(message), reply_markup=reply_markup)

    return QUIZ.Answer


def handle_solution_attempt(update, context, quiz_qa):
    question = quiz_qa[context.user_data['question_number']]
    query = update.callback_query
    question_index = int(query.data)
    answer_result = 'ВЕРНО'
    if question['correct'] != question['answers'][question_index]:
        answer_result = 'НЕВЕРНО'

    message = dedent(f'''\
    Ваш выбор: {question_index+1}.
    Правильный ответ: {question['correct']}
    Результат: {answer_result}
    ''')
    query.message.reply_text(text=message)

    return QUIZ.Question


def handle_give_up(update, context, quiz_qa):
    question = quiz_qa[context.user_data['question_number']]

    message = dedent(f'''\
    Правильный ответ: {question['correct']}
    ''')
    update.message.reply_text(text=message)

    return QUIZ.Question


def handle_about(update, _):
    update.message.reply_text(text=GLOBAL_MESSAGE)
    return QUIZ.Question


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--debug',
        type=bool,
        default=False,
        help='Turn DEBUG mode on'
    )
    arguments = parser.parse_args()

    level = logging.DEBUG if arguments.debug else logging.INFO
    logging.basicConfig(level=level)

    load_dotenv()
    telegram_token = os.environ['TELEGRAM-TOKEN']
    base_file_name = os.environ['BASE_FILE']

    logging.debug(
        'Read questions and answers from files & make QA dictionary'
    )
    base_file = os.path.join('base', base_file_name)
    with open(base_file, 'r') as base_file:
        quiz_qa = json.load(base_file)

    logging.debug('Prepare telegram bot')
    updater = Updater(token=telegram_token)
    dispatcher = updater.dispatcher

    partial_handle_new_question_request = partial(
        handle_new_question_request,
        quiz_qa=quiz_qa,
    )

    partial_handle_solution_attempt = partial(
        handle_solution_attempt,
        quiz_qa=quiz_qa,
    )

    partial_handle_give_up = partial(
        handle_give_up,
        quiz_qa=quiz_qa,
    )

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],

        states={
            QUIZ.Question: [
                MessageHandler(
                    Filters.regex('^(Новый вопрос)$'),
                    partial_handle_new_question_request
                ),
                MessageHandler(
                    Filters.regex('^(Капучино автору!)$'),
                    handle_about
                ),
            ],

            QUIZ.Answer: [
                MessageHandler(
                    Filters.regex('^(Сдаться)$'),
                    partial_handle_give_up
                ),
                MessageHandler(
                    Filters.regex('^(Капучино автору!)$'),
                    handle_about
                ),
                CallbackQueryHandler(
                    partial_handle_solution_attempt
                ),
            ]

        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    dispatcher.add_handler(conversation_handler)

    logging.debug('Run telegram bot')
    updater.start_polling()
    updater.idle()
