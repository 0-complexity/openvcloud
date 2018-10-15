def main(j, args, params, tags, tasklet):
    out = []
    config = j.application.instanceconfig["navigationlinks"]
    for cfg in config:
        out.append("* [{name}|{url}]".format(**cfg))
    params.result = ("\n".join(out), args.doc)
    return params


def match(j, args, params, tags, tasklet):
    return True
