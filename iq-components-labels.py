#!/usr/bin/python3
# ----------------------------------------------------------------------------
# Python Dependencies
import json
import argparse
import asyncio
import aiohttp

# ----------------------------------------------------------------------------
iq_url, iq_session, components, reports = "", "", {}, {}

def get_arguments():
    global iq_url, iq_session, iq_auth, components
    parser = argparse.ArgumentParser(description='Export Components')
    parser.add_argument('-u', '--url', help='', default="http://localhost:8070", required=False)
    parser.add_argument('-a', '--auth', help='', default="admin:admin123", required=False)
    args = vars(parser.parse_args())
    iq_url = args["url"]
    creds = args["auth"].split(":")
    iq_session = aiohttp.ClientSession()
    iq_auth = aiohttp.BasicAuth(creds[0], creds[1])
    return args

async def main():
    args = get_arguments()
    print(f'   === start ===   ')

    print(f'get list of all apps')
    apps = await get_url(f'{iq_url}/api/v2/applications', "applications")
    print(f' -- {len(apps)} total apps found')

    print(f'get all the reports for apps')
    for app_reports in asyncio.as_completed([
            handle_app(app) for app in apps
        ]):
        reports.update(await app_reports)
    print(f' -- {len(reports)} total reports found')

    print(f'get all components for reports.')
    for resp in asyncio.as_completed([
            handle_details(report) for report in reports.values()
        ]):
        response = await resp
        reports[response["scanId"]] = response
    print(f' -- {len(components)} total components found')

    print(f'get labels for components, (may take awhile...)')
    for resp in asyncio.as_completed([
            handle_labels(component) for component in components.values()
        ]):
        response = await resp
        components[response["hash"]] = response

    # -------------------------------------------
    print(f'reducing components to just those with labels.')
    filter_labes()
    print(f' -- {len(components)} total components with labels')
    # -------------------------------------------

    #print results to json file.
    save_results("results.json", components, True)

    print(f'   === done ===   ')
    await iq_session.close()

#---------------------------------
def pp(page):
    print(json.dumps(page, indent=4))


def filter_labes():
    global components
    for h,c in list( components.items() ):
        for a in list( c['apps'] ):
            if len(a['labels']) == 0:
                c['apps'].remove(a)

        if len(c['apps']) == 0:
            del components[h]

def save_results(file_name, results, indent=False):
    with open(file_name, "w+") as file:
        if indent:
              file.write(json.dumps(results, indent=4))
        else: file.write(json.dumps(results))
    print(f"Json results saved to -> {file_name}")


async def handle_app(app):
    resp = {}
    url = f'{iq_url}/api/v2/reports/applications/{app["id"]}'
    app_reports = await get_url(url)
    if app_reports is not None:
        for report in app_reports:
            scanId = report["reportDataUrl"].split("/")[-2]
            resp.update({scanId:{ 
                "publicId": app["publicId"], 
                "id": app["id"],
                "stage": report["stage"],
                "reportUrl": report["reportDataUrl"],
                "scanId": scanId,
                "components": []
            }})
    return resp

async def handle_details(report):
    global components
    data = await get_url(f'{iq_url}/{report["reportUrl"]}')
    report["components"] = []
    for c in data["components"]:
        hash_ = c["hash"]
        if hash_ is not None:
            if hash_ not in components:
                pack = { 
                    "hash": hash_,
                    "packageUrl" : c["packageUrl"], 
                    "displayName" : c["displayName"], 
                    "apps" : []
                }
                components.update({ hash_ : pack })
                report["components"].append(hash_)

            app_details = {
                "stage": report["stage"], 
                "publicId": report["publicId"], 
                "labels": []
            }
            components[ hash_ ]["apps"].append(app_details)
    return report

async def handle_labels(component):
    for app in component["apps"]:
        resp = await get_label(component["hash"], app["publicId"])
        for owners in resp["labelsByOwner"]:
            for label in owners["labels"]:
                app["labels"].append( label["label"])
    return component

async def get_label(hash_, publicId):
    url = f'{iq_url}/rest/label/component/application/{publicId}/{hash_}'
    resp = await get_url(url)
    return resp

async def get_url(url, root=""):
    resp = await iq_session.get(url, auth=iq_auth)
    if resp.status != 200:
        print(await resp.text())
        return None
    node = await resp.json()
    if root in node:
        node = node[root]
    if node is None or len(node) == 0:
        return None
    return node

if __name__ == "__main__":
    asyncio.run(main())
