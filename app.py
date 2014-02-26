# coding=UTF-8

# General modules.
import os, os.path
import logging
import sys
from threading import Timer
import string
import random

# Tornado modules.
import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.auth
import tornado.options
import tornado.escape
from tornado import gen

# Redis modules.
import brukva

# Import application modules.
from base import BaseHandler
from auth import LoginHandler
from auth import LogoutHandler

# Define port from command line parameter.
tornado.options.define("port", default=8888, help="run on the given port", type=int)



class MainHandler(BaseHandler):
    """
    Main request handler for the root path and for chat rooms.
    """

    @tornado.web.asynchronous
    def get(self, room=None):
        if not room:
            self.redirect("/room/1")
            return
        # Set chat room as instance var (should be validated).
        self.room = str(room)
        # Get the current user.
        self._get_current_user(callback=self.on_auth)


    def on_auth(self, user):
        if not user:
            # Redirect to login if not authenticated.
            self.redirect("/login")
            return
        # Load 50 latest messages from this chat room.
        self.application.client.lrange(self.room, -50, -1, self.on_conversation_found)


    def on_conversation_found(self, result):
        if isinstance(result, Exception):
            raise tornado.web.HTTPError(500)
        # JSON-decode messages.
        messages = []
        for message in result:
            messages.append(tornado.escape.json_decode(message))
        # Render template and deliver website.
        content = self.render_string("messages.html", messages=messages)
        self.render_default("index.html", content=content, chat=1)



class ChatSocketHandler(tornado.websocket.WebSocketHandler):
    """
    Handler for dealing with websockets. It receives, stores and distributes new messages.

    TODO: Not proper authentication handling!
    """

    @gen.engine
    def open(self, room='root'):
        """
        Called when socket is opened. It will subscribe for the given chat room based on Redis Pub/Sub.
        """
        # Check if room is set.
        if not room:
            self.write_message({'error': 1, 'textStatus': 'Error: No room specified'})
            self.close()
            return
        self.room = str(room)
        self.new_message_send = False
        # Create a Redis connection.
        self.client = redis_connect()
        # Subscribe to the given chat room.
        self.client.subscribe(self.room)
        self.subscribed = True
        self.client.listen(self.on_messages_published)
        logging.info('New user connected to chat room ' + room)


    def on_messages_published(self, message):
        """
        Callback for listening to subscribed chat room based on Redis Pub/Sub. When a new message is stored
        in the given Redis chanel this method will be called.
        """
        # Decode message
        m = tornado.escape.json_decode(message.body)
        # Send messages to other clients and finish connection.
        self.write_message(dict(messages=[m]))


    def on_message(self, data):
        """
        Callback when new message received vie the socket.
        """
        logging.info('Received new message %r', data)
        try:
            # Parse input to message dict.
            datadecoded = tornado.escape.json_decode(data)
            message = {
                '_id': ''.join(random.choice(string.ascii_uppercase) for i in range(12)),
                'from': self.get_secure_cookie('user', str(datadecoded['user'])),
                'body': tornado.escape.linkify(datadecoded["body"]),
            }
            if not message['from']:
                logging.warning("Error: Authentication missing")
                message['from'] = 'Guest'
        except Exception, err:
            # Send an error back to client.
            self.write_message({'error': 1, 'textStatus': 'Bad input data ... ' + str(err) + data})
            return

        # Save message and publish in Redis.
        try:
            # Convert to JSON-literal.
            message_encoded = tornado.escape.json_encode(message)
            # Persistently store message in Redis.
            self.application.client.rpush(self.room, message_encoded)
            # Publish message in Redis channel.
            self.application.client.publish(self.room, message_encoded)
        except Exception, err:
            e = str(sys.exc_info()[0])
            # Send an error back to client.
            self.write_message({'error': 1, 'textStatus': 'Error writing to database: ' + str(err)})
            return

        # Send message through the socket to indicate a successful operation.
        self.write_message(message)
        return


    def on_close(self):
        """
        Callback when the socket is closed. Frees up resource related to this socket.
        """
        logging.info("socket closed, cleaning up resources now")
        if hasattr(self, 'client'):
            # Unsubscribe if not done yet.
            if self.subscribed:
                self.client.unsubscribe(self.room)
                self.subscribed = False
            # Disconnect connection after delay due to this issue:
            # https://github.com/evilkost/brukva/issues/25
            t = Timer(0.1, self.client.disconnect)
            t.start()



class Application(tornado.web.Application):
    """
    Main Class for this application holding everything together.
    """
    def __init__(self):

        # Handlers defining the url routing.
        handlers = [
            (r"/", MainHandler),
            (r"/room/([a-zA-Z0-9]*)$", MainHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/socket", ChatSocketHandler),
            (r"/socket/([a-zA-Z0-9]*)$", ChatSocketHandler),
        ]

        # Settings:
        settings = dict(
            cookie_secret = "43osdETzKXasdQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url = "/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies= True,
            autoescape="xhtml_escape",
            # Set this to your desired database name.
            db_name = 'chat',
            # apptitle used as page title in the template.
            apptitle = 'Chat example: Tornado, Redis, brukva, Websockets',
        )

        # Call super constructor.
        tornado.web.Application.__init__(self, handlers, **settings)

        # Stores user names.
        self.usernames = {}

        # Connect to Redis.
        self.client = redis_connect()


def redis_connect():
    """
    Established an asynchronous resi connection.
    """
    # Get Redis connection settings for Heroku with fallback to defaults.
    redistogo_url = os.getenv('REDISTOGO_URL', None)
    if redistogo_url == None:
        REDIS_HOST = 'localhost'
        REDIS_PORT = 6379
        REDIS_PWD = None
        REDIS_USER = None
    else:
        redis_url = redistogo_url
        redis_url = redis_url.split('redis://')[1]
        redis_url = redis_url.split('/')[0]
        REDIS_USER, redis_url = redis_url.split(':', 1)
        REDIS_PWD, redis_url = redis_url.split('@', 1)
        REDIS_HOST, REDIS_PORT = redis_url.split(':', 1)
    client = brukva.Client(host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PWD)
    client.connect()
    return client



def main():
    """
    Main function to run the chat application.
    """
     # This line will setup default options.
    tornado.options.parse_command_line()
    # Create an instance of the main application.
    application = Application()
    # Start application by listening to desired port and starting IOLoop.
    application.listen(tornado.options.options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()