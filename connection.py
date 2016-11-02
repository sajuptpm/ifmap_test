import gevent
from gevent import monkey
monkey.patch_all()

#contrail patched ifmap client
from cfgm_common.ifmap.client import client
from ifmap.request import NewSessionRequest, RenewSessionRequest, \
    EndSessionRequest, PublishRequest, SearchRequest, \
    SubscribeRequest, PurgeRequest, PollRequest
from ifmap.operations import PublishUpdateOperation, PublishNotifyOperation, \
    PublishDeleteOperation, SubscribeUpdateOperation,\
    SubscribeDeleteOperation
from cfgm_common import exceptions
from lxml import etree
import StringIO

_CT_NS = "contrail"
_ROOT_IMID = _CT_NS + ":config-root:root"

_SOAP_XSD = "http://www.w3.org/2003/05/soap-envelope"
_IFMAP_XSD = "http://www.trustedcomputinggroup.org/2010/IFMAP/2"
_IFMAP_META_XSD = "http://www.trustedcomputinggroup.org/2010/IFMAP-METADATA/2"
_CONTRAIL_XSD = "http://www.contrailsystems.com/vnc_cfg.xsd"

def ifmap_server_connect(args):
    _CLIENT_NAMESPACES = {
        'env':  _SOAP_XSD,
        'ifmap':  _IFMAP_XSD,
        'meta':  _IFMAP_META_XSD,
        _CT_NS:  _CONTRAIL_XSD
    }

    ssl_options = None
    if args.use_certs:
        ssl_options = {
            'keyfile': args.keyfile,
            'certfile': args.certfile,
            'ca_certs': args.ca_certs,
            'cert_reqs': ssl.CERT_REQUIRED,
            'ciphers': 'ALL'
        }
    return client(("%s" % (args.ifmap_server_ip),
                   "%s" % (args.ifmap_server_port)),
                  args.ifmap_username, args.ifmap_password,
                  _CLIENT_NAMESPACES, ssl_options)

def sub_root(ssrc_mapc):
    ident = str(Identity(name=_ROOT_IMID, type="other",
                         other_type="extended"))
    subreq = SubscribeRequest(
        ssrc_mapc.get_session_id(),
        operations=str(SubscribeUpdateOperation("root", ident,
                                                {"max-depth": "255", })))
    #subscribe_root
    result = ssrc_mapc.call('subscribe', subreq)

def init_sub(args):
	#First conn to ifmap server
    ssrc_mapc = ifmap_server_connect(args)
    result = ssrc_mapc.call('newSession', NewSessionRequest())
    ssrc_mapc.set_session_id(newSessionResult(result).get_session_id())
    ssrc_mapc.set_publisher_id(newSessionResult(result).get_publisher_id())
    sub_root(ssrc_mapc)
    #ssrc_initialize
    return ssrc_mapc

def init_arc(args, ssrc_mapc):
	"""
		Poll requests go on ARC channel which don't do newSession but
    	share session-id with ssrc channel. so 2 connections to server but 1
    	session/session-id in ifmap-server (mamma mia!)
    """
    #Second conn to ifmap server
    arc_mapc = ifmap_server_connect(args)
    #but share session-id from first conn.
    #get session id from first conn and set it here
    arc_mapc.set_session_id(ssrc_mapc.get_session_id())
    arc_mapc.set_publisher_id(ssrc_mapc.get_publisher_id())
    return arc_mapc

def start_pl(sub, ssrc_mapc):
    arc_mapc = init_arc(sub._args, ssrc_mapc)
    while True:
        try:
            pollreq = PollRequest(arc_mapc.get_session_id())
            result = arc_mapc.call('poll', pollreq)
            sub.process(result)
        except Exception as e:
        	raise ex

def launch_ssrc(args, sub):
    while True:
        ssrc_mapc = init_sub(args)
        arc_glet = gevent.spawn(start_pl, sub, ssrc_mapc)
        arc_glet.join()

##############################

def parse_pl_res(poll_result_str):
    _XPATH_NAMESPACES = {
        'a': _SOAP_XSD,
        'b': _IFMAP_XSD,
        'c': _CONTRAIL_XSD
    }

    soap_doc = etree.parse(StringIO.StringIO(poll_result_str))
    #soap_doc.write(sys.stdout, pretty_print=True)

    xpath_error = '/a:Envelope/a:Body/b:response/errorResult'
    error_results = soap_doc.xpath(xpath_error,
                                   namespaces=_XPATH_NAMESPACES)
    if error_results:
        if error_results[0].get('errorCode') == 'InvalidSessionID':
            raise exceptions.InvalidSessionID(etree.tostring(error_results[0]))
        raise Exception(etree.tostring(error_results[0]))

    xpath_expr = '/a:Envelope/a:Body/b:response/pollResult'
    poll_results = soap_doc.xpath(xpath_expr,
                                  namespaces=_XPATH_NAMESPACES)
    result_list = []
    for result in poll_results:
        children = result.getchildren()
        for child in children:
            result_type = child.tag
            if result_type == 'errorResult':
                raise Exception(etree.tostring(child))

            result_items = child.getchildren()
            item_list = parse_result_items(result_items)
            for item in item_list:
                ident1 = item[0]
                ident2 = item[1]
                meta = item[2]
                idents = {}
                ident1_imid = ident1.attrib['name']
                ident1_type = get_type_from_ifmap_id(ident1_imid)
                idents[ident1_type] = get_fq_name_str_from_ifmap_id(
                    ident1_imid)
                if ident2 is not None:
                    ident2_imid = ident2.attrib['name']
                    ident2_type = get_type_from_ifmap_id(ident2_imid)
                    if ident1_type == ident2_type:
                        idents[ident1_type] = [
                            idents[ident1_type],
                            get_fq_name_str_from_ifmap_id(ident2_imid)]
                    else:
                        idents[ident2_type] = get_fq_name_str_from_ifmap_id(
                            ident2_imid)
                result_list.append((result_type, idents, meta))
    return result_list
# end parse_poll_result




