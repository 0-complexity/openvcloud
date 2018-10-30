from JumpScale import j

descr = """
Updates the system config for an env
"""

organization = "greenitglobe"
author = "ali.chaddad@gig.tech"
license = "bsd"
version = "1.0"
category = "cloudbroker"
roles = ["controllernode"]
timeout = 120
order = 1
async = True


def action(data):
    import yaml

    cfg_loc = "/tmp/system-config.yaml"
    _, output = j.system.process.execute(
        "kubectl --kubeconfig /root/.kube/config get configmap system-config -o yaml"
    )
    output = yaml.load(output)
    for file_key in output["data"].keys():
        config_data = yaml.load(output["data"][file_key])
        config_data.update(data)
        with open(cfg_loc, "w") as fld:
            yaml.dump(config_data, fld, default_flow_style=False)
        cmd = "kubectl {0} create configmap system-config --from-file={1} --dry-run -o yaml | kubectl {0} replace -f -".format(
            "--kubeconfig /root/.kube/config",
            cfg_loc
        )
        try:
            j.system.process.execute(cmd)
        finally:
            j.system.fs.remove(cfg_loc)

