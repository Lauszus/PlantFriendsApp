# Copyright (C) 2019 Kristian Sloth Lauszus.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# Contact information
# -------------------
# Kristian Sloth Lauszus
# Web      :  http://www.lauszus.com
# e-mail   :  lauszus@gmail.com

import atexit
import logging
import os
from datetime import datetime
from logging.handlers import SMTPHandler

import coloredlogs
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from flask_caching import Cache
from flask_compress import Compress
from flask_mail import Mail

__version__ = '0.0.1'

app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py')
app.config['UPDATE_FOLDER'] = os.path.join(app.root_path, 'update')
app.config['YEAR'] = datetime.today().year

# Setup logging
level = 'DEBUG' if app.debug or app.testing else 'INFO'
logger_fmt = '[%(asctime)s] [%(name)s] [%(module)s] [%(levelname)s] %(message)s'
coloredlogs.install(level=level, logger=app.logger, fmt=logger_fmt)
coloredlogs.install(level=level, logger=logging.getLogger('werkzeug'), fmt=logger_fmt)
coloredlogs.install(level=level, logger=logging.getLogger('apscheduler'), fmt=logger_fmt)

# Setup cache
cache = Cache(app, with_jinja2_ext=False,
              config={'CACHE_TYPE': 'null' if app.debug or app.testing else 'filesystem',
                      'CACHE_NO_NULL_WARNING': True,  # Cache is disabled during development, this silents the warning
                      'CACHE_DEFAULT_TIMEOUT': 300,
                      'CACHE_DIR': os.path.join(app.root_path, '.app_cache')})

# Tell flask-compress about our Flask-Caching instance so it can use it as a backend
app.config['COMPRESS_CACHE_BACKEND'] = lambda: cache
app.config['COMPRESS_CACHE_KEY'] = lambda response: hashlib.sha1(response.get_data()).hexdigest()
Compress(app)

# Used for checking for firmware updates
scheduler = BackgroundScheduler()
if not app.debug and not app.testing:
    scheduler.start()


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()


# Shut down the scheduler when exiting the app
atexit.register(shutdown_scheduler)

if app.debug or app.testing:
    with app.app_context():
        cache.clear()  # Clear cache during development
    app.config['MAIL_SUPPRESS_SEND'] = True  # Suppress emails during development

mail = Mail(app)


class MailExceptionHandler(SMTPHandler):
    def __init__(self):
        super(MailExceptionHandler, self).__init__(None, None, None, None)

    def emit(self, record):
        # noinspection PyBroadException
        try:
            # Send exception report via email
            from flask_mail import Message
            msg = Message(subject='Plant Friends Exception Report', recipients=app.config['MAIL_ADMINS'],
                          body=self.format(record))
            mail.send(msg)
        except Exception:
            self.handleError(record)


# Send an email with exception info
mailExceptionHandler = MailExceptionHandler()
mailExceptionHandler.setLevel(logging.ERROR)
app.logger.addHandler(mailExceptionHandler)

from .app import *

if __name__ == '__main__':
    app.run(host='0.0.0.0')
