"""Hangman API implemented using Google Cloud Endpoints.

api.py. Contains declarations of endpoint, endpoint methods,
as well as the ProtoRPC message class and container required
for endpoint method definition.
"""

import endpoints
# PROTORPC is a library import modules
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.ext import ndb

from models import User, Game, Score
from models import StringMessage, GameForm
from models import UserForm, UserForms, GameForms
from models import ScoreForm, ScoreForms
from utils import get_by_urlsafe

import logging
import datetime


# ENDPOINT REQUEST
# ---------------------------
USER_REQUEST = endpoints.ResourceContainer(
    name=messages.StringField(1, required=True),
    email=messages.StringField(2, required=True))

NEW_GAME_REQUEST = endpoints.ResourceContainer(
    name=messages.StringField(1, required=True),
    topic=messages.StringField(2, required=True),
    answer=messages.StringField(3, required=True),
    attempts_remaining=messages.IntegerField(4))

CURRENT_GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1))

MAKE_MOVE_REQ = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1, required=True),
    guess=messages.StringField(2, required=True))


CANCEL_GAME_REQUEST = endpoints.ResourceContainer(
    user_name=messages.StringField(1, required=True),
    urlsafe_game_key=messages.StringField(2, required=True))

HIGHEST_SCORES_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    number_of_results=messages.IntegerField(1),
)

# ----------------------------


@endpoints.api(name='hangman_api', version='v1')
class HangmanApi(remote.Service):

    # CREATE USER endpoint
    @endpoints.method(USER_REQUEST,
                      StringMessage,
                      path='game/create_user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique username"""
        if User.query(User.name == request.name).get():
            raise endpoints.ConflictException(
                'A User with that name already exists!')
        user = User(name=request.name, email=request.email)
        user.put()
        return StringMessage(message='User {} created!'.format(request.name))

    # NEW GAME endpoint
    # IF ANSWER HAS A SPACE IN IT REPLACE WITH COMMA
    @endpoints.method(NEW_GAME_REQUEST,
                      GameForm,
                      path='game/new_game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game"""
        user = User.query(User.name == request.name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        try:
            # create hidden blanks array
            hidden = []
            # applylowercase to answer
            request.answer.lower()
            # fill hidden array with blanks
            for char in request.answer:
                if char == " ":
                    hidden.append(",")
                else:
                    hidden.append("_")

            guesses = []
            date = datetime.datetime.now()

            # check if request.attempts_remaining is empty
            if not request.attempts_remaining:
                request.attempts_remaining = 6
            game = Game.new_game(user.key,
                                 request.topic,
                                 request.answer,
                                 hidden,
                                 guesses,
                                 date,
                                 request.attempts_remaining)

            # store active game urlsafe into user for reference later
            user.activeGameKeys.append(game.key.urlsafe())
            user.put()

        except ValueError:
            raise endpoints.BadRequestException('Cant create game')

        msg = 'Good luck playing Hangman!'
        game.add_to_history(msg, 'NONE')
        return game.to_form(msg)

    # GET Current Game endpoint
    @endpoints.method(CURRENT_GAME_REQUEST,
                      GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_current_game',
                      http_method='GET')
    def get_current_game(self, request):
        """Returns a game state with message"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return game.to_form('Time to make a move!')
        else:
            raise endpoints.NotFoundException('Game not found!')

    # MAKE MOVE endpoint
    @endpoints.method(MAKE_MOVE_REQ,
                      GameForm,
                      path='game/{urlsafe_game_key}/make_move',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        user = game.key.parent().get()

        # take guess and apply lowercase
        guess = request.guess.lower()
        # 1.check game already over
        if game.game_over:
            msg = 'Game already over!'
            game.add_to_history(msg, 'NONE')
            return game.to_form(msg)

        # 2. If guess is a digit
        else:
            if guess.isdigit():
                msg = 'Please enter a letter.'
            # 3. IF more than one character
            elif len(guess) != 1:
                msg = "Please enter a single letter!"
            # 4. IF they already guessed same character
            elif guess in game.guesses:
                msg = "You already guessed that! You have {} tries".format(
                    game.attempts_remaining)
            # 5. guess not in answer
            elif guess not in game.answer:
                # minus 1 attempt
                game.attempts_remaining -= 1
                game.guesses.append(guess)
                if game.attempts_remaining < 1:
                    game.end_game(False)
                    msg = 'Game over! You LOSE'
                else:
                    msg = "Nope Sorry! You have {} tries".format(
                        game.attempts_remaining)
            # 6. guess in answer
            elif guess in game.answer:
                game.guesses.append(guess)
                # update hidden
                for idx, item in enumerate(game.answer):
                    if game.answer[idx] == guess:
                        game.hidden[idx] = guess
                # check to make sure all "_" are gone to return win
                if "_" not in game.hidden:
                    game.end_game(True)
                    msg = "CONGRATS You WON! The secret was {}".format(
                        game.answer)
                    # return game.to_form(msg)
                else:
                    msg = "Nice! Looks like you guessed right"
            game.add_to_history(msg, guess)
            game.put()
        return game.to_form(msg)

    # GET USER GAMES endpoint
    @endpoints.method(USER_REQUEST,
                      GameForms,
                      path='game/get_activeGames',
                      name='get_user_games',
                      http_method='GET')
    def get_user_games(self, request):
        """Returns all of an individual User's ACTIVE games"""
        user = User.query(User.name == request.name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')

        game_keys = [ndb.Key(urlsafe=wsck) for wsck in user.activeGameKeys]
        games = ndb.get_multi(game_keys)
        return GameForms(items=[game.to_form() for game in games])

    # CANCEL GAME ENDPOINT
    @endpoints.method(CANCEL_GAME_REQUEST,
                      StringMessage,
                      path='game/{urlsafe_game_key}/cancel',
                      name='cancel_game',
                      http_method='DELETE')
    def cancel_game(self, request):
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')

        """Returns a game state with message"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if not game:
            raise endpoints.NotFoundException('Game not found!')

        # check game is completed
        if game.game_over:
            raise endpoints.NotFoundException(
                "Sorry. You can't delete a completed game")
        else:
            # delete activegame from user
            if request.urlsafe_game_key in user.activeGameKeys:
                user.activeGameKeys.remove(request.urlsafe_game_key)

                ndb.Key(urlsafe=request.urlsafe_game_key).delete()

                user.put()
                return StringMessage(message='Game has been cancelled')

    # GET HIGH SCORES endpoint
    @endpoints.method(HIGHEST_SCORES_REQUEST,
                      ScoreForms,
                      path='game/get_high_scores',
                      name='get_high_scores',
                      http_method='GET')
    def get_high_scores(self, request):
        # order scores descending order by attempts remaining
        # more attempts equal better
        scores = Score.query().order(-Score.attempts_remaining)

        if request.number_of_results:
            return ScoreForms(
                items=[score.to_form() for score in scores.fetch(
                    limit=request.number_of_results)])
        else:
            return ScoreForms(items=[score.to_form() for score in scores])

    # GET USERS endpoint
    @endpoints.method(USER_REQUEST,
                      UserForm,
                      path='game/get_users',
                      name='get_user',
                      http_method='GET')
    def get_user(self, request):
        user = User.query(User.name == request.name).get()
        return user.to_form()

    # GET USER RANKINGS endpoint
    # use performance display win/loss ratio
    @endpoints.method(message_types.VoidMessage,
                      UserForms,
                      path='game/get_user_rankings',
                      name='get_user_rankings',
                      http_method='GET')
    def get_user_rankings(self, request):
        users = User.query().order(-User.performance)
        return UserForms(items=[user.to_form() for user in users])

    # GET_GAME_HISTORY endpoint
    # GET Current Game
    @endpoints.method(CURRENT_GAME_REQUEST,
                      StringMessage,
                      path='game/{urlsafe_game_key}/history',
                      name='get_game_history',
                      http_method='GET')
    def get_game_history(self, request):
        """Returns a summary of a game's guesses."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if not game:
            raise endpoints.NotFoundException('Game not found')
        return StringMessage(message=str(game.history))


APPLICATION = endpoints.api_server([HangmanApi])
