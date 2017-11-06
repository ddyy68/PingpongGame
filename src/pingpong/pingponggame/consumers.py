import json
from channels import Group
from channels.auth import channel_session_user, channel_session_user_from_http
from django.core.cache import cache
from .models import Player, Game

from django.db import transaction
@channel_session_user_from_http
@transaction.atomic
# Connected to websocket.connect
def ws_add(message):
    player = Player.objects.get(user=message.user)

    # When current player does not exist or do not have a current game
    if not player or not player.current_game:
        message.reply_channel.send({"accept": False})
        return
    
    message.reply_channel.send({"accept": True})
    #available_players means how many players connect to the current game room
    game = player.current_game
    game.player_ready()
    print(game.available_players)
    
    Group("game_%s" % game.id).add(message.reply_channel)
    
    if game.available_players == 2:
        Group("game_%s" % game.id).send({
            "text": json.dumps({
                "TYPE": "STATE",
                "state": "ready",
            }),
        })

@channel_session_user
# Connected to websocket.receive
def ws_message(message):
    player = Player.objects.get(user=message.user)
    game = player.current_game
    data = json.loads(message['text'])
    print(data)
    print(data['TYPE'])
    if (data['TYPE'] == 'GAME'):
        score = data['score']
        game.set_player_score(player, score)
        winner = game.determine_winner()
        if winner:
            Group("game_%s" % game.id).send({
                "text": json.dumps({
                    "TYPE": "GAME",
                    "winner": winner.nickname,
                }),
            })

@channel_session_user
@transaction.atomic
# Connected to websocket.disconnect
def ws_disconnect(message):
    print("some one leaves")
    player = Player.objects.get(user=message.user)
    game = player.current_game
    # this game is over
    if game.winner:
        print("game is already over~")
        return
    game.player_gone()
    player.leave_game()
    print (game.available_players)
    Group("game_%s" % game.id).discard(message.reply_channel)
    Group("game_%s" % game.id).send({
            "text": json.dumps({
                "TYPE": "STATE",
                "state": "unready",
            }),
        })