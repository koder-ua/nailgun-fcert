import os
import re
import json
import time
import urllib2
from functools import partial, wraps


logger = None


def set_logger(log):
    global logger
    logger = log


class Urllib2HTTP(object):
    """
    class for making HTTP requests
    """

    allowed_methods = ('get', 'put', 'post', 'delete', 'patch', 'head')

    def __init__(self, root_url, headers=None, echo=False):
        """
        """
        if root_url.endswith('/'):
            self.root_url = root_url[:-1]
        else:
            self.root_url = root_url

        self.headers = headers if headers is not None else {}
        self.echo = echo

    def do(self, method, path, params=None):
        if path.startswith('/'):
            url = self.root_url + path
        else:
            url = self.root_url + '/' + path

        if method == 'get':
            assert params == {} or params is None
            data_json = None
        else:
            data_json = json.dumps(params)

        if self.echo:
            print "HTTP: {} {}".format(method.upper(), url)

        request = urllib2.Request(url,
                                  data=data_json,
                                  headers=self.headers)
        if data_json is not None:
            request.add_header('Content-Type', 'application/json')

        request.get_method = lambda: method.upper()
        responce = urllib2.urlopen(request)

        if responce.code < 200 or responce.code > 209:
            raise IndexError(url)

        content = responce.read()

        if '' == content:
            return None

        return json.loads(content)

    def __getattr__(self, name):
        if name in self.allowed_methods:
            return partial(self.do, name)
        raise AttributeError(name)


def get_inline_param_list(url):
    format_param_rr = re.compile(r"\{([a-zA-Z_]+)\}")
    for match in format_param_rr.finditer(url):
        yield match.group(1)


class RestObj(object):
    name = None
    id = None

    def __init__(self, conn, **kwargs):
        self.__dict__.update(kwargs)
        self.__connection__ = conn

    def __str__(self):
        res = ["{}({}):".format(self.__class__.__name__, self.name)]
        for k, v in sorted(self.__dict__.items()):
            if k.startswith('__') or k.endswith('__'):
                continue
            if k != 'name':
                res.append("    {}={!r}".format(k, v))
        return "\n".join(res)


def make_call(method, url):
    def closure(obj, entire_obj=None, **data):
        if entire_obj is not None:
            if data != {}:
                raise ValueError("Both entire_obj and data provided")
            request_data = entire_obj
            result_url = url
        else:
            inline_params_vals = {}
            request_data = data.copy()
            for name in get_inline_param_list(url):
                if name in data:
                    inline_params_vals[name] = data[name]
                    del data[name]
                else:
                    inline_params_vals[name] = getattr(obj, name)
            result_url = url.format(**inline_params_vals)

        return obj.__connection__.do(method, result_url, params=request_data)
    return closure


PUT = partial(make_call, 'put')
GET = partial(make_call, 'get')
DELETE = partial(make_call, 'delete')


def with_timeout(tout, message):
    def closure(func):
        @wraps(func)
        def closure2(*dt, **mp):
            ctime = time.time()
            etime = ctime + tout

            while ctime < etime:
                if func(*dt, **mp):
                    return
                sleep_time = ctime + 1 - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                ctime = time.time()
            raise RuntimeError("Timeout during " + message)
        return closure2
    return closure


#-------------------------------  ORM -----------------------------------------


class Node(RestObj):
    def set_node_name(self, name):
        self.__connection__.put('nodes', [{'id': self.id, 'name': name}])


class NodeList(list):
    allowed_roles = "controller,compute,cinder".split(',')

    def __getattr__(self, name):
        if name in self.allowed_roles:
            for node in self:
                if name in node.roles:
                    yield node


class Cluster(RestObj):

    add_node_call = PUT('api/nodes')
    start_deploy = PUT('api/clusters/{id}/changes')
    get_status = GET('api/clusters/{id}')
    delete = DELETE('api/clusters/{id}')
    get_tasks_status = GET("api/tasks?tasks={id}")
    load_nodes = GET('api/nodes?cluster_id={id}')

    def __init__(self, *dt, **mp):
        super(Cluster, self).__init__(*dt, **mp)
        self.nodes = NodeList()

    def check_exists(self):
        try:
            self.get_status()
            return True
        except urllib2.HTTPError as err:
            if err.code == 404:
                return False
            raise

    def add_node(self, node, roles):
        data = {}
        data['pending_roles'] = roles
        data['cluster_id'] = self.id
        data['id'] = node.id
        data['pending_addition'] = True
        logger.debug("Adding node %s to cluster..." % node.id)
        self.add_node_call([data])
        self.nodes.append(node)

    def wait_operational(self, timeout):
        wo = lambda: self.get_status()['status'] == 'operational'
        with_timeout(timeout, "deploy cluster")(wo)()

    def deploy(self, timeout):
        logger.debug("Starting deploy...")
        self.start_deploy()

        self.wait_operational(timeout)

        def all_tasks_finished_ok(obj):
            ok = True
            for task in obj.get_tasks_status():
                if task['status'] == 'error':
                    raise Exception('Task execution error')
                elif task['status'] != 'ready':
                    ok = False
            return ok

        wto = with_timeout(timeout, "wait deployment finished")
        wto(all_tasks_finished_ok)(self)


def reflect_cluster(conn, cluster_id):
    c = Cluster(conn, id=cluster_id)
    c.nodes = c.load_nodes()
    return c


def get_all_nodes(conn):
    for node_desc in conn.get('api/nodes'):
        yield Node(conn, **node_desc)


def get_all_clusters(conn):
    for cluster_desc in conn.get('api/clusters'):
        yield Cluster(conn, **cluster_desc)


def get_cluster_attributes(conn, cluster_id):
    return conn.get(path="/api/clusters/{}/attributes/".format(cluster_id))


def get_cluster_id(name, conn):
    for cluster in get_all_clusters(conn):
        if cluster.name == name:
            logger.info('cluster name is %s' % name)
            logger.info('cluster id is %s' % cluster.id)
            return cluster.id


def update_cluster_attributes(conn, cluster_id, attrs):
    url = "/api/clusters/{}/attributes/".format(cluster_id)
    return conn.put(url, attrs)


def create_empty_cluster(conn, cluster_desc):
    logger.info("Creating new cluster %s" % cluster_desc['name'])
    data = {}
    data['nodes'] = []
    data['tasks'] = []
    data['name'] = cluster_desc['name']
    data['release'] = cluster_desc['release']
    data['mode'] = cluster_desc['deployment_mode']
    data['net_provider'] = cluster_desc['settings']['net_provider']

    cluster_id = get_cluster_id(data['name'], conn)

    if not cluster_id:
        cluster = Cluster(conn, **conn.post(path='api/clusters', params=data))
        cluster_id = cluster.id

        settings = cluster_desc['settings']
        attributes = get_cluster_attributes(conn, cluster_id)

        for option in settings:
            section = False

            if option in ('sahara', 'murano', 'ceilometer'):
                section = 'additional_components'

            if option in ('volumes_ceph', 'images_ceph', 'ephemeral_ceph',
                'objects_ceph', 'osd_pool_size', 'volumes_lvm',
                'volumes_vmdk'):
                section = 'storage'

            if option in ('tenant', 'password', 'user'):
                section = 'access'

            if option in ('vc_password', 'cluster', 'host_ip', 'vc_user',
                'use_vcenter'):
                section = 'vcenter'

            if section:
                attributes['editable'][section][option]['value'] = \
                    settings[option]


            attributes['editable']['common']['debug']['value'] = \
            os.environ.get('DEBUG_MODE', 'true') == 'true'
            update_cluster_attributes(conn, cluster_id, attrs=attributes)

    if not cluster_id:
        raise Exception("Could not get cluster '%s'" % data['name'])

    return cluster

