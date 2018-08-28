import requests

AUTH_URL = "https://itsyou.online/v1/oauth/access_token"


class Client:
    def __init__(self, url, application_id, secret):
        if not url.endswith("/"):
            url += "/"
        self.url = "{}/restmachine/".format(url)
        self.session = None
        self._setup_auth(application_id, secret)

    def _setup_auth(self, application_id, secret):
        params = {
            "grant_type": "client_credentials",
            "client_id": application_id,
            "client_secret": secret,
            "response_type": "id_token",
        }
        self.session = requests.Session()
        resp = self.session.post(AUTH_URL, params=params)
        resp.raise_for_status()
        jwt = resp.content.decode("utf8")
        self.session.headers["Authorization"] = "Bearer {}".format(jwt)

    def request(self, api, **kwargs):
        resp = self.session.post("{}/{}".format(self.url, api), json=kwargs)
        resp.raise_for_status()
        return resp.json()
