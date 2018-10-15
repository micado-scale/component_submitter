import requests
from subprocess import check_output


lsof_res = check_output(['lsof', '-i4'])

lsof_res = lsof_res.decode("uft-8")
lsof_res = lsof_res.split()

host = lsof_res[ lsof_res.index('TCP') + 1 ]

requests.get("http://{}/v1.0/list_app/".format(host))
