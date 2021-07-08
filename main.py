#!/usr/bin/env python3
from kubernetes import client, config
from tabulate import tabulate
from pathlib import Path

import os
import logging
import coloredlogs
import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument(
    "--debug", help="enable DEBUG logging mode", default=False, action="store_true"
)
args = parser.parse_args()

if args.debug:
    coloredlogs.install(
        level="DEBUG",
        milliseconds=True,
        fmt="%(asctime)s,%(msecs)03d %(name)s[%(funcName)s()] %(levelname)s %(message)s",
    )
else:
    coloredlogs.install(
        level="INFO",
        milliseconds=True,
        fmt="%(asctime)s,%(msecs)03d %(name)s %(levelname)s %(message)s",
    )


def printJson(data):
    # parsed = json.loads(data)
    print(json.dumps(data, indent=2, sort_keys=True))


def loadKubernetesClient():
    """
    returns a k8s client object, will attempt to load incluster or KUBECONFIG dynamically
    """
    if isInCluster():
        logging.info("loading incluster config")
        config.load_incluster_config()
    else:
        contexts, _ = config.list_kube_config_contexts()
        if not contexts:
            logging.error("Cannot find any context in kube-config file.")
            exit(1)
        config.load_kube_config(config_file=os.getenv("KUBECONFIG", default=f"{Path.home()}/.kube/config"))
    return client


def envVarIsSet(key):
    if os.environ.get(key) == None:
        logging.debug("env var {} is not set".format(key))
        return False
    logging.debug("env var {} is set".format(key))
    return True


def isInCluster():
    """
    returns true if in cluster, else false
    """
    if envVarIsSet("KUBERNETES_SERVICE_HOST") and envVarIsSet(
        "KUBERNETES_SERVICE_PORT"
    ):
        logging.debug("running inside a cluster")
        return True
    logging.debug("NOT running inside a cluster")
    return False


def main():

    client = loadKubernetesClient()
    client.rest.logger.setLevel(logging.WARNING)  # logging.DEBUG is way to verbose

    v1 = client.CoreV1Api()

    nodeData = []
    nodes = v1.list_node()
    for node in nodes.items:
        nodeData.append(getNodeInfo(node))

    # TODO: use node labels to determine all CB nodes
    couchbaseNodeList = []
    for n in nodeData:
        x = n[3]
        if x.startswith("cb"):
            couchbaseNodeList.append(n)

    stats = []


    # for x in nodeList:
    #     print(x[0])

    nameSpace = "couchbase"
    expectedLabels = "app=couchbase"
    ret = v1.list_namespaced_pod(nameSpace, label_selector=expectedLabels, watch=False)
    for i in ret.items:
        result = gatherData(i, nodeData)

        # remove node from the couchbaseNodeList (so we have a list of unused nodes)
        deleteMe = result[1]  # remove this node from our list of nodes as it has CB stuff
        for j in range(len(couchbaseNodeList)):
            candidateNode = couchbaseNodeList[j]
            if candidateNode[0] == deleteMe:
                couchbaseNodeList.remove(candidateNode)
                break

        stats.append(result)

    nameSpace = "couchbase-sync"
    expectedLabels = "app=sync-gateway"
    ret = v1.list_namespaced_pod(nameSpace, label_selector=expectedLabels, watch=False)
    for i in ret.items:
        result = gatherData(i, nodeData)

        # remove node from the couchbaseNodeList (so we have a list of unused nodes)
        deleteMe = result[1]  # remove this node from our list of nodes as it has CB stuff
        for j in range(len(couchbaseNodeList)):
            candidateNode = couchbaseNodeList[j]
            if candidateNode[0] == deleteMe:
                couchbaseNodeList.remove(candidateNode)
                break

        stats.append(result)

    headers = [
        "ig",
        "node",
        "zone",
        "size",
        "pod",
        "ready",
        "phase",
        "desired zone",
        "data",
        "index",
        "query",
        "search",
    ]
    print(tabulate(stats, headers=headers, tablefmt="simple"))
    print()
    print("found {} total".format(len(stats)))
    print()

    # print(
    #     "tip: get pods on a node with:\n\n  kubectl get pods --all-namespaces -o wide --field-selector spec.nodeName=<nodename>"
    # )

    if len(couchbaseNodeList) > 0 :
        print("\n------------- Warning -----------------\npotentially unused nodes:")
        print(tabulate(couchbaseNodeList))

        print("\n\ncheck whats running on these like so:")
        for x in couchbaseNodeList:
            str = "# kubectl get pods --all-namespaces --field-selector spec.nodeName={}".format(x[0])
            print(str)


def gatherData(pod, nodeData):
    result = []
    node = pod.spec.node_name
    name = pod.metadata.name
    labels = pod.metadata.labels
    phase = pod.status.phase

    ready = getContainerStatuses(pod)
    # node details
    zone = ""
    size = ""
    ig = ""
    for x in nodeData:
        if node == x[0]:
            zone = x[1]
            size = x[2]
            ig = x[3]
    # print("%s\t%s\t%s\t%s" % (pod.status.host_ip, pod.metadata.namespace, pod.metadata.name, pod.metadata.labels))
    result.append(ig)
    result.append(node)
    result.append(zone)
    result.append(size)
    result.append(name)
    result.append(ready)
    result.append(phase)
    result.append(zoneSelector(pod))
    result.append(isCbService(labels, "data"))
    result.append(isCbService(labels, "index"))
    result.append(isCbService(labels, "query"))
    result.append(isCbService(labels, "search"))

    return result


def getNodeInfo(node):
    name = node.metadata.name
    labels = node.metadata.labels
    size = "unknown"
    ig = "unknown"
    zone = "unknown"
    role = "unknown"
    for k in labels.keys():
        if k == "beta.kubernetes.io/instance-type":
            size = labels["beta.kubernetes.io/instance-type"]
        if k == "node.kubernetes.io/instancegroup":
            ig = labels["node.kubernetes.io/instancegroup"]
        if k == "failure-domain.beta.kubernetes.io/zone":
            zone = labels["failure-domain.beta.kubernetes.io/zone"]
        if k == "node.kubernetes.io/instancegroup":
            role = labels["node.kubernetes.io/instancegroup"]
    ## crappy list.. dict would be better
    return [name, zone, size, ig, role]


def zoneSelector(pod):
    """
    filters for node_selector 'failure-domain.beta.kubernetes.io/zone'
    """
    nodeSelector = pod.spec.node_selector
    if nodeSelector != None:
        for x in nodeSelector.keys():
            if x == "failure-domain.beta.kubernetes.io/zone":
                return nodeSelector["failure-domain.beta.kubernetes.io/zone"]
    podAntiAffinity = pod.spec.affinity.pod_anti_affinity
    if podAntiAffinity != None:
        for x in podAntiAffinity.required_during_scheduling_ignored_during_execution:
            if x.topology_key  == "topology.kubernetes.io/zone":
                return "az pod antiaffinity"
    return "NONE"


def getContainerStatuses(pod):
    ready = "?"
    if pod.status != None :
        if pod.status.container_statuses != None:
            statuses = pod.status.container_statuses
            if len(statuses) > 0:
                ready = ""
                for c in statuses:
                    if c.ready:
                        ready = ready + "✅"
                    else:
                        ready = ready + "⭕"

                return ready
    return ready

def isCbService(input, kind):
    """
    returns True if a label matching "enabled" is found
    EG: to test for index, call this method with the labels and "index"
    couchbase_service_index': 'enabled'  > couchbase_service_<kind>': 'enabled',
    couchbase_service_query': 'enabled'  > couchbase_service_<kind>': 'enabled',
    """
    key = "couchbase_service_{}".format(kind)
    if input != None:
        if key in input.keys():
            if input[key] == "enabled":
                return "✅"
    return "⭕"


def podIsCouchbase(input):
    labels = input.metadata.labels
    if "app" in labels.keys():
        if input.metadata.labels["app"] == "couchbase":
            return True
    return False


if __name__ == "__main__":
    main()
