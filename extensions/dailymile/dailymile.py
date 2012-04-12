# dailymile.py - Posts activity to Dailymile.
#
# Copyright (C) 2012 Philippe Gauthier <philippe.gauthier@deuxpi.ca>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import gtk
import httplib
import json
import logging
import os
import time
import urlparse
import webkit
from oauth import oauth

DAILYMILE_REQUEST_TOKEN_URL = 'https://api.dailymile.com/oauth/request_token'
DAILYMILE_AUTHORIZE_URL = 'https://api.dailymile.com/oauth/authorize'
DAILYMILE_CREATE_ENTRY_URL = "https://api.dailymile.com/entries.json"
DAILYMILE_URL = "www.dailymile.com"

# Please get a new authorization key and secret if you create a derivative of
# this code.
CLIENT_KEY = "92aET5oukEtOhXXQOs8bEFNawaC797s6zSD2sSFN"
CLIENT_SECRET = "bb8oXDB2n0edfs2e1UcYRDWsbsz60FYw0qjpJ1sm"

class DailymileExtension:
    def __init__(self, parent=None, pytrainer_main=None, conf_dir=None, options=None):
        self.pytrainer_main = pytrainer_main
        self.conf_dir = conf_dir
        self.consumer = oauth.OAuthConsumer(CLIENT_KEY, CLIENT_SECRET)
        self.signature = oauth.OAuthSignatureMethod_HMAC_SHA1()
        self.connection = httplib.HTTPSConnection(DAILYMILE_URL)
        self.conf = {}
        try:
            self.conf = json.load(file(
                os.path.join(conf_dir, "dailymile.json")))
            self.access_token = oauth.OAuthToken(
                self.conf['access_token'], None)
        except:
            self.access_token = None

    def run(self, id, activity):
        self.activity = activity
        self.fetch_request_token()
        if self.access_token is None:
            self.authorize()
        else:
            self.post_entry(activity)

    def fetch_request_token(self):
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(
                self.consumer,
                http_method='POST',
                callback="http://www.deuxpi.ca/0/auth.html",
                http_url=DAILYMILE_REQUEST_TOKEN_URL)
        oauth_request.sign_request(self.signature, self.consumer, token=None)
        headers = oauth_request.to_header()
        self.connection.request(oauth_request.http_method,
                DAILYMILE_REQUEST_TOKEN_URL,
                headers=headers)
        response = self.connection.getresponse()
        self.token = oauth.OAuthToken.from_string(response.read())

    def authorize(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.auth_window = window
        web = webkit.WebView()
        web.get_settings().set_property("enable-plugins", False)

        url = DAILYMILE_AUTHORIZE_URL + '?response_type=token&client_id=' + CLIENT_KEY + '&redirect_uri=http://www.deuxpi.ca/0/auth.html'
        web.load_uri(url)
        web.set_size_request(550, 400)
        web.connect('title-changed', self.handle_title_changed)
        scroll = gtk.ScrolledWindow()
        scroll.add(web)
        window.add(scroll)
        window.show_all()

    def handle_title_changed(self, web_view=None, title=None, data=None):
        if title.get_title() != "Success":
            return
        url = web_view.get_main_frame().get_uri()
        data = urlparse.parse_qs(url.split("#", 1)[1])
        self.access_token = oauth.OAuthToken(str(data["access_token"][0]), None)
        logging.debug("Access token: " + self.access_token.key)
        self.conf['access_token'] = self.access_token.key
        json.dump(self.conf,
                  file(os.path.join(self.conf_dir, "dailymile.json"), 'w'))
        web_view.hide()
        self.auth_window.destroy()
        self.post_entry(self.activity)

    def utcisoformat(self, dt):
        return datetime.datetime.utcfromtimestamp(
                time.mktime(dt.timetuple())).isoformat() + "Z"

    def post_entry(self, activity):
        request = oauth.OAuthRequest.from_consumer_and_token(
                self.consumer, token=self.access_token, verifier=None,
                http_method='POST',
                http_url=DAILYMILE_CREATE_ENTRY_URL)
        url = request.to_url()
        workout = {
                'message': activity.comments,
                'workout': {
                    'completed_at': self.utcisoformat(activity.date_time),
                    'distance': {
                        'value': activity.distance,
                        'units': {
                            'miles': 'miles',
                            'km': 'kilometers',
                            }[activity.distance_unit],
                        },
                    'activity_type': {
                        'Run': 'running',
                        'Running': 'running',
                        'Bike': 'cycling',
                        'Mountain Bike': 'cycling',
                        }[activity.sport_name],
                    'duration': activity.time,
                    'title': activity.title,
                    }
                }
        body = json.dumps(workout)
        self.connection.request(request.http_method, url, body,
                {"Content-type": "application/json"})
        response = self.connection.getresponse()
        logging.debug("Dailymile response: " + response.read())
        dialog = gtk.MessageDialog(self.pytrainer_main.windowmain.window1,
                gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_INFO,
                gtk.BUTTONS_OK,
                "Workout has been posted to Dailymile.")
        dialog.set_title("Success")
        dialog.set_modal(True)
        dialog.run()
        dialog.destroy()

