
from JumpScale import j

descr = """
Update firewall rules on controller
"""

category = "libvirt"
organization = "greenitglobe"
author = "jo@gig.tech"
license = "bsd"
version = "2.0"
roles = ["controllernode"]
async = True


def action():
    rulespath = "/etc/iptables/rules.v4"
    rules = j.system.fs.fileGetContents(rulespath)
    lines = rules.splitlines()
    changes = False
    for idx, line in enumerate(lines):
        if line == "-A INPUT -i public -p tcp -m multiport --dports 22,3080,7022,80,443 -j ACCEPT":
            changes = True
            lines[idx] = "A INPUT -i public -p tcp -m multiport --dports 3080,7022,80,443 -j ACCEPT"
            break
    if changes:
        j.system.fs.writeFile(rulespath, "\n".join(lines))
    _, output = j.system.process.execute("iptables --line-numbers -vnL")
    linenr = None
    for rule in output.splitlines():
        if "public" in rule and "multiport" in rule and "ACCEPT":
            linenr = rule.split()[0]
            break
    if linenr:
        j.system.process.execute("iptables -R INPUT {} -i public -p tcp -m multiport --dports 3080,7022,80,443 -j ACCEPT".format(linenr))


if __name__ == "__main__":
    action()
