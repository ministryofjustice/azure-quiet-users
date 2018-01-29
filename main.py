#!/usr/bin/env python3
from datetime import datetime
import json
import logging
import subprocess
import sys
from urllib.parse import urlparse, urljoin, urlencode, parse_qs
from urllib.request import urlopen, Request

logging.basicConfig(level=logging.INFO)

try:
    tenant_id = sys.argv[1]
except:
    print("Usage: ./main.py <tenant_id>")
    sys.exit(1)

GRAPH_URL = "https://graph.windows.net/"

token = json.loads(subprocess.run(
    "az account get-access-token --resource '%s'" % GRAPH_URL,
    shell=True, stdout=subprocess.PIPE
).stdout)
authorization = token['tokenType'] + ' ' + token['accessToken']

def req(path, params={}):
    headers = {'authorization': authorization}
    url = urljoin(GRAPH_URL, tenant_id + '/' + path)
    params['api-version'] = 'beta'
    url = url + '?' + urlencode(params)
    logging.info("Requesting %s" % url)
    with urlopen(Request(url, headers=headers)) as res:
        logging.info("Got response")
        return json.loads(res.read())

def get_skiptoken(nextLink):
    parsed = urlparse(nextLink)
    return parse_qs(parsed.query)["$skiptoken"][0]

def build_user(user):
    return {
        'id': user['objectId'],
        'upn': user['userPrincipalName'],
        'name': user['displayName'],
        'enabled': user['accountEnabled']
    }

def all_users():
    users = []
    params = {}
    def append(res):
        for user in res["value"]:
            users.append(build_user(user))
    while True:
        response = req("users", params)
        append(response)
        try:
            params["$skiptoken"] = get_skiptoken(response["odata.nextLink"])
        except KeyError:
            break
    return users

def build_signin(signin):
    return {
        'id': signin['userId'],
        'upn': signin['userPrincipalName'],
        'when': datetime.utcfromtimestamp(signin['signinDateTimeInMillis'] / 1000)
    }

def signins_by_user():
    oldest = datetime.utcnow()
    signins = {}
    params = {}
    def append(res):
        nonlocal oldest
        for signin in res["value"]:
            signin = build_signin(signin)
            signins[signin['id']] = signin
            oldest = min(oldest, signin['when'])
    while True:
        response = req("activities/signinEvents", params)
        append(response)
        try:
            params["$skiptoken"] = get_skiptoken(response["@odata.nextLink"])
        except KeyError:
            break
    return signins, oldest

users = all_users()
signins, oldest = signins_by_user()

print("\n\n")
print("Report of Users who haven't signed in since %s" % oldest)
print("=" * 40)
for user in users:
    if user['id'] not in signins and not user['enabled']:
        print("%s (disabled)" % user['upn'])
print("-" * 40)
for user in users:
    if user['id'] not in signins and user['enabled']:
        print(user['upn'])
