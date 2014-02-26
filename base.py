# coding=UTF-8

# Tornado modules.
import tornado.web

# General modules.
import logging


class BaseHandler(tornado.web.RequestHandler):
    """
    A base request Handler providing user authentication.
    It also provides a render_default() method which passes arguments to render()
    with additional default arguments for the menu, user...
    """
    def __init__(self, application, request, **kwargs):
        # Call super constructor.
        tornado.web.RequestHandler.__init__(self, application, request, **kwargs)


    def _get_current_user(self, callback):
        """
        An async method to load the current user object.
        The callback  function will receive the current user object or None
        as the parameter 'user'.
        """
        # Get the user_id by cookie.
        user_id = self.get_secure_cookie("user")
        if not user_id:
            logging.warning("Cookie not found")
            callback(user=None)
            return
        # Define a callback for the db query.
        def query_callback(result):
            if result == "null" or not result:
                logging.warning("User not found")
                user = {}
            else:
                user = tornado.escape.json_decode(result)
            self._current_user = user
            callback(user=user)
        # Load user object and pass query_callback as callback.
        self.application.client.get("user:" + user_id, query_callback)
        return


    def render_default(self, template_name, **kwargs):
        # Set default variables and render template.
        if not hasattr(self, '_current_user'):
            self._current_user = None
        kwargs['user'] = self._current_user
        kwargs['path'] = self.request.path;
        if hasattr(self, 'room'):
            kwargs['room'] = int(self.room)
        else: kwargs['room'] = None
        kwargs['apptitle'] = self.application.settings['apptitle']

        if not self.request.connection.stream.closed():
            try:
                self.render(template_name, **kwargs)
            except: pass
    
