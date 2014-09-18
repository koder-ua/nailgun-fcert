import copy 


class APICall(object):
    # some of them may be stevedore plugin
    pass


def find_api_classes(modules_list=None):
    print modules_list


class Field(object):
    def make_cli_param(self):
        pass


class NodeParams(object):
    id = Field(int, help="....")
    name = Field(str, required=False, help="....")


class UpdateNodes(APICall):
    """Can be used for any node updates...."""
    class params:
        nodes = list(NodeParams)

    rest_url = PUT("nodes")
    cli_name = "nodes update"

    def in_cli(self):
        pass

    def in_rest(self):
        pass

    def in_client(self):
        pass


class SetNodeName(UpdateNodes):
    cli_name = "node rename"

    params = copy.deepcopy(UpdateNodes.params)
    params.name.required = True

    def in_cli(self):
        pass





# -------------------- MANUAL API -----------------------------------------

class Node(RESTObject):
    __urls__ = restfull_url_set('nodes')

    # "GET nodes => node list"
    # "GET nodes/id => node"
    # "POST nodes => new node"
    # "PUT nodes/id => update node"
    # "DELETE nodes/id => delete node"

conn.load_all(Node) => [Node]
conn.load(Node, node_id) => Node

node.name = 'xxxx'
node.cluster = 1
node.save()

conn.save(node_list)

with conn.new_change_set() as transaction:
    nodes = transaction.load_all(Node)
    for node in nodes:
        node.cluster_id = 12

