#!/usr/local/bin/python
"""
MiCADO Command Line Interface
------------------------------

Component to create the command line interface that will talk to the submitter
to launch, update, undeploy the application
"""

import argparse
from submitter_engine import SubmitterEngine
import ast



if __name__=="__main__":
    parser = argparse.ArgumentParser(prog='SUBMITTER')
    subparsers = parser.add_subparsers(help='sub-command help')

    launch = subparsers.add_parser('launch', help="command line to launch the topology template" )
    update = subparsers.add_parser('update', help="command line to update the wanted topology")
    undeploy = subparsers.add_parser('undeploy', help="command line to undeploy the wanted topology")

    launch.set_defaults(which='launch')
    launch.add_argument("--template", "-t", required=True, help="path or url of the template")
    launch.add_argument("--params", "-p", required=False, help="dictionary contianing the inputs that need to be modified")
    launch.add_argument("--id", required=False, help="ID for the application to be set by the user, if not the ID is auto generated")
    
    update.set_defaults(which='update')
    update.add_argument("-id", required=True, help="ID of the topology that needs to be updated")
    update.add_argument("--template", "-t", required=True, help="path or url of the template")
    update.add_argument("--params", "-p", required=False, help="dictionary contianing the inputs that need to be modified")

    undeploy.set_defaults(which='undeploy')
    undeploy.add_argument("-id", required=True, help="ID of the topology that needs to be updated")
    args = parser.parse_args()

    submitter=SubmitterEngine()
    print(args)
    if args.which is "launch":
        if args.params:
            submitter.launch(path_to_file=args.template, parsed_params=ast.literal_eval(args.params))
        else:
            submitter.launch(path_to_file=args.template)
    elif args.which is "update":
        if args.params:
            submitter.update(id_app=args.id, path_to_file=args.template, parsed_params=ast.literal_eval(args.params))
        else:
            submitter.update(id_app=args.id, path_to_file=args.template)
    elif args.which is "undeploy":
        submitter.undeploy(id_app=args.id)
