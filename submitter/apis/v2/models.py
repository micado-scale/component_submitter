from webargs import fields


class ReqArgs:
    json = {
        "adt": fields.Dict(),
        "url": fields.Str(),
        "params": fields.Dict(),
        "dryrun": fields.Bool(),
    }
    form = {
        "url": fields.Str(),
        "params": fields.Str(),
        "dryrun": fields.Bool(),
    }
    file = {"adt": fields.Field()}
    force = {"force": fields.Bool()}
