def main(j, args, params, tags, tasklet):
    page = args.page
    counter = """
<script>
window.onload=function(){
var counter = %s;
var interval = setInterval(function() {
    counter--;
    document.getElementById('counter').innerText = "The following data will be expired in " + counter + " seconds if you didn't use it"
    if (counter <= 0) {
        document.getElementById('counter').innerText = "this data is no longer valid"
    }
}, 1000);
}
</script>
    """
    node_id = args.requestContext.params.get("node")
    node_name, remote = j.apps.cloudbroker.zeroaccess._get_node_info(node_id)
    page.addHTML('<h2 class="title">Access info for node: {}</h2>'.format(node_name))
    oauth = j.clients.oauth.get(instance="itsyouonline")
    jwt = oauth.get_active_jwt(session=args.requestContext.env["beaker.session"])
    if jwt:
        init_time_data = j.apps.cloudbroker.zeroaccess.getSessionInitTime(
            ctx=args.requestContext
        )
        if init_time_data:
            session_init_time = init_time_data["session_init_time"]
        else:
            session_init_time = 60
        counter = counter % (session_init_time)
        session_data = j.apps.cloudbroker.zeroaccess.provision(
            remote=remote, ctx=args.requestContext
        )
        if session_data:
            username = session_data["username"]
            ip = session_data["ssh_ip"]
            port = session_data["ssh_port"]
            link = "chrome-extension://pnhechapfaindjhompbnflcldabbghjo/html/nassh.html#{username}@{ip}:{port}".format(
                username=username, ip=ip, port=port
            )
            accesstext = """
<h4><span id="counter"></span></h4>
Two ways to connect to {node}:

<h3>1. In browser:</h3>
<p>
Via the Secure Shell browser plugin in your Chrome browser. You can install it from <a target="blank" href="https://chrome.google.com/webstore/detail/secure-shell/pnhechapfaindjhompbnflcldabbghjo?utm_source=chrome-app-launcher-info-dialog" target="blank">here</a>.
You can click this link if you have secure shell plugin installed <a target="blank" href="{link}">connect with secure shell</a>
</p>
<p>
<strong>Important</strong><br/>
Before using the secure shell plugin integration with 0-access, make sure you loaded your private key into the Secure Shell browser plugin.
</p>

<h3>2. Via your own terminal:</h3>
""".format(
                link=link, node=remote
            )
            page.addHTML(accesstext)
            ssh_command = "ssh {username}@{ip} -p {port}".format(
                username=username, ip=ip, port=port
            )
            page.addCodeBlock(ssh_command, template="bash", edit=False)
            page.addHTML(counter)
        else:
            page.addCodeBlock(
                "Can not get provisioning data may be jwt has expired",
                template="bash",
                edit=False,
            )
    else:
        page.addCodeBlock(
            "No jwt found in your session please logout and login again",
            template="bash",
            edit=False,
        )

    params.result = page
    return params
