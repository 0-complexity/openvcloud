from JumpScale import j
from cloudbrokerlib.baseactor import BaseActor
from JumpScale.portal.portal import exceptions
import requests
import datetime
import socket


class cloudbroker_zeroaccess(BaseActor):
    """
    Operator actions for interventions specific to a user
    """

    def __init__(self):
        super(cloudbroker_zeroaccess, self).__init__()
        self.zeroaccessurl = "http://zero-access:5000"
        self.iyoinstance = j.clients.oauth.get(instance="itsyouonline")

    def _get_jwt(self, ctx):
        return self.iyoinstance.get_active_jwt(session=ctx.env["beaker.session"])

    def listSessions(self, query="", page=None, user="", remote="", **kwargs):
        """
        List available 0-access sessions
        """
        params = {"query": query, "page": page, "user": user, "remote": remote}

        def get_nodes_dict():
            """
            get dict with necessary 0-access nodes information
            """
            mgmt_ip = socket.gethostbyname("management-ssh")
            nodes = {mgmt_ip: {"name": "management", "guid": "0"}}
            for node_id in self.sysmodels.node.list():
                node = self.sysmodels.node.get(node_id)
                if "master" in node.roles:
                    continue
                else:
                    for addr in node.netaddr:
                        if addr["name"] == "backplane1":
                            nodes[addr["ip"][0]] = {
                                "guid": node.guid,
                                "name": node.name,
                            }
                            break
                    else:
                        continue
            return nodes

        ctx = kwargs["ctx"]
        jwt = self._get_jwt(ctx)
        resp = requests.get(
            "{}/sessions".format(self.zeroaccessurl),
            params=params,
            headers={"Authorization": "Bearer {jwt}".format(jwt=jwt)},
        )
        result_data = list()
        if resp.status_code != 200:
            result_data = [
                [
                    "Can not get data from 0-access server jwt may be expired please logout and login again",
                    "",
                    "",
                    "",
                    "",
                ]
            ]
        else:
            result = resp.json()
            if result["total_pages"] != 0:
                sessions = result["page"]["sessions"]
                nodes = get_nodes_dict()
                for session in sessions:
                    if session["start"] and session["end"]:
                        session_id = session["href"].split("/")[-1]
                        itemdata = [
                            "[{sessionid}|/cbgrid/Session Player?sessionid={sessionid}]".format(
                                sessionid=session_id
                            )
                        ]
                        itemdata.append(session["user"]["username"])
                        if session["remote"] in nodes:
                            name = "[{name}|/cbgrid/0-access Node?node={id}]".format(
                                name=nodes[session["remote"]]["name"],
                                id=nodes[session["remote"]]["guid"],
                            )
                            itemdata.append(name)
                        else:
                            itemdata.append(session["remote"])
                        itemdata.append(
                            datetime.datetime.fromtimestamp(session["start"]).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        )
                        itemdata.append(
                            datetime.datetime.fromtimestamp(session["end"]).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        )
                        result_data.append(itemdata)
        return result_data

    def _zero_access_request(self, ctx, url, params=None):
        jwt = self._get_jwt(ctx)
        resp = requests.get(
            url,
            headers={"Authorization": "Bearer {jwt}".format(jwt=jwt)},
            params=params,
        )
        if resp.status_code != 200:
            headers = []
            for name, value in resp.headers.items():
                if name.lower() not in ("connection", "content-length"):
                    headers.append((name, value))
            raise exceptions.BaseError(
                resp.status_code, headers, j.tools.text.toStr(resp.text)
            )
        return resp.json()

    def provision(self, remote, **kwargs):
        return self._zero_access_request(
            kwargs["ctx"], "{0}/provision/{1}".format(self.zeroaccessurl, remote)
        )

    def downloadSession(self, session_id, **kwargs):
        return self._zero_access_request(
            kwargs["ctx"], "{0}/sessions/{1}".format(self.zeroaccessurl, session_id)
        )

    def getSessionInitTime(self, **kwargs):
        return self._zero_access_request(
            kwargs["ctx"], "{}/server/config".format(self.zeroaccessurl)
        )

    def sessionTextSearch(self, query, page, **kwargs):
        return self._zero_access_request(
            kwargs["ctx"],
            "{}/sessions".format(self.zeroaccessurl),
            params={"query": query, "page": page},
        )

    def _get_node_info(self, node_id):
        if node_id == "0":
            return "management", socket.gethostbyname("management-ssh")
        remote = None
        node = self.sysmodels.node.get(node_id)
        node_name = node.name
        for addr in node.netaddr:
            if addr["name"] == "backplane1":
                remote = addr["ip"][0]
                return node_name, remote
        return node_name, remote
