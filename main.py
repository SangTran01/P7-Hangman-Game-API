#!/usr/bin/env python

"""main.py - This file contains handlers that are called by taskqueue and/or
cronjobs."""
import logging

import webapp2
from google.appengine.api import mail, app_identity
from api import HangmanApi

from models import User, Game


class SendReminderEmail(webapp2.RequestHandler):

    def get(self):
        """Send a reminder email to each User with an email about games.
        Called every 3 hours using a cron job"""
        app_id = app_identity.get_application_id()
        # Get unfinished games

        users = User.query()
        for user in users:
            # Get all the users games.
            games = Game.query(Game.user == user.key, Game.game_over == False)

            for game in games:
                logging.debug(game)
                subject = 'This is a reminder from HangmanApi!'
                body = ('Hello {}, ready to finish your game? '
                        'Your topic was {}, and you still have'
                        ' {} attempts left!').format(
                    user.name,
                    game.topic,
                    game.attempts_remaining)
                # This will send test emails, the arguments to send_mail are:
                # from, to, subject, body
                mail.send_mail('noreply@{}.appspotmail.com'.format(app_id),
                               user.email,
                               subject,
                               body)


app = webapp2.WSGIApplication([
    ('/crons/send_reminder', SendReminderEmail)
], debug=True)
