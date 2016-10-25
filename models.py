"""models.py - This file contains the class definitions for the Datastore
entities used by the Game. Because these classes are also regular Python
classes they can include methods (such as 'to_form' and 'new_game')."""

from __future__ import division
import datetime
from protorpc import messages
from protorpc import message_types
from google.appengine.ext import ndb
import logging


class User(ndb.Model):

    """User profile"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()
    activeGameKeys = ndb.StringProperty(repeated=True)
    wins = ndb.IntegerProperty(default=0)
    losses = ndb.IntegerProperty(default=0)
    performance = ndb.FloatProperty(default=0)

    def to_form(self):
        return UserForm(name=self.name, email=self.email,
                        activeGameKeys=self.activeGameKeys,
                        wins=self.wins, losses=self.losses,
                        performance=self.performance)


class UserForm(messages.Message):
    name = messages.StringField(1, required=True)
    email = messages.StringField(2)
    activeGameKeys = messages.StringField(3, repeated=True)
    wins = messages.IntegerField(4)
    losses = messages.IntegerField(5)
    performance = messages.FloatField(6)


class UserForms(messages.Message):

    """Return multiple ScoreForms"""
    items = messages.MessageField(UserForm, 1, repeated=True)


class Game(ndb.Model):

    """Game object"""
    game_over = ndb.BooleanProperty(required=True, default=False)
    user = ndb.KeyProperty(required=True, kind='User')
    topic = ndb.StringProperty(required=True)
    answer = ndb.StringProperty(required=True)
    attempts_remaining = ndb.IntegerProperty()
    hidden = ndb.StringProperty(repeated=True)
    guesses = ndb.StringProperty(repeated=True)
    date_created = ndb.DateTimeProperty()
    # list of history
    history = ndb.PickleProperty(required=True, default=[])

    @classmethod
    def new_game(cls, user, topic, answer, hidden, guesses,
                 date, attempts_remaining):
        """Creates and returns a new game"""
        game = Game(user=user,
                    parent=user,
                    topic=topic,
                    answer=answer,
                    hidden=hidden,
                    guesses=guesses,
                    game_over=False,
                    date_created=date,
                    attempts_remaining=attempts_remaining)
        game.put()
        return game

    def to_form(self, message='test'):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.topic = self.topic
        form.hidden = self.hidden
        form.guesses = self.guesses
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.user.get().name
        form.attempts_remaining = self.attempts_remaining
        form.game_over = self.game_over
        form.message = message
        form.date_created = self.date_created.strftime("%Y-%m-%d %I:%M:%S %p")
        return form

    def to_form_all(self):
        return GamesForm(user=self.user.get().name,
                         topic=self.topic,
                         game_over=self.game_over,
                         attempts_remaining=self.attempts_remaining)

    def end_game(self, won=False):
        """Ends the game - if won is True, the player won. - if won is False,
        the player lost."""
        self.game_over = True

        # get user thats playing this game aka parent
        # remove active game urlsafekey element from array from user
        user = self.key.parent().get()
        user.activeGameKeys.remove(self.key.urlsafe())

        # IF WON is false or true
        if won:
            user.wins += 1
        else:
            user.losses += 1

        total_games = user.wins + user.losses
        user.performance = (user.wins / total_games) * 100

        self.put()
        user.put()
        # Add the game to the score 'board'
        score = Score(name=self.user.get().name,
                      game=self.key, user=self.user,
                      date=datetime.datetime.now(),
                      won=won,
                      attempts_remaining=self.attempts_remaining)
        score.put()

    def add_to_history(self, result, guess):
        # get history
        self.history.append({'message': result, 'guess': guess})
        self.put()

class GameForm(messages.Message):

    """GameForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    attempts_remaining = messages.IntegerField(2, required=True)
    game_over = messages.BooleanField(3, required=True)
    message = messages.StringField(4, required=True)
    user_name = messages.StringField(5, required=True)
    topic = messages.StringField(6, required=True)
    hidden = messages.StringField(7, repeated=True)
    guesses = messages.StringField(8, repeated=True)
    date_created = messages.StringField(9)

class GameForms(messages.Message):

    """Return multiple ScoreForms"""
    items = messages.MessageField(GameForm, 1, repeated=True)


class Score(ndb.Model):

    """Score object"""
    game = ndb.KeyProperty(required=True, kind='Game')
    user = ndb.KeyProperty(required=True, kind='User')
    name = ndb.StringProperty(required=True)
    date = ndb.DateTimeProperty(required=True)
    won = ndb.BooleanProperty(required=True)
    attempts_remaining = ndb.IntegerProperty(required=True)

    def to_form(self):
        return ScoreForm(user_name=self.user.get().name,
                         won=self.won,
                         date=self.date.strftime("%Y-%m-%d %I:%M:%S %p"),
                         attempts_remaining=self.attempts_remaining)


class ScoreForm(messages.Message):
    user_name = messages.StringField(1, required=True)
    date = messages.StringField(2, required=True)
    won = messages.BooleanField(3, required=True)
    attempts_remaining = messages. IntegerField(4, required=True)


class ScoreForms(messages.Message):

    """Return multiple ScoreForms"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)

class StringMessage(messages.Message):

    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)
