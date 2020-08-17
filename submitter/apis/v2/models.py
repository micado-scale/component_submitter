from marshmallow import Schema, fields


class AppSchema(Schema):

    message = fields.Str(default="MiCADO Application Info")
    adaptors = fields.Method("get_adaptors_status")

    def get_adaptors_status(self, obj):
        adaptors = obj.get("adaptors_object", {})
        if adaptors:
            return {k: v.status for k, v in adaptors.items()}
        return {k: "Unknown" for k in obj.get("components", [])}


class AppListSchema(Schema):
    message = fields.Str(default="MiCADO Applications")
    applications = fields.Function(lambda obj: list(obj.keys()))


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
