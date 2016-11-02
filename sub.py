import gevent
from gevent import monkey
monkey.patch_all()
from connection import launch_ssrc, parse_pl_res
from settings import ops

class Sub(object):

    def __init__(self, args=None):
        self._args = args

    def process(self, poll_result_str):
        result_list = parse_pl_res(poll_result_str)
        # first pass thru the ifmap message and build data model
        for (result_type, idents, metas) in result_list:
            if result_type != 'searchResult' and not self.ifmap_search_done:
                #self.ifmap_search_done = True
                print "==============>>>1===", result_type, 
                #self.process_stale_objects()
            for meta in metas:
                meta_name = re.sub('{.*}', '', meta.tag)
                if result_type == 'deleteResult':
                    funcname = "delete_" + meta_name.replace('-', '_')
                elif result_type in ['searchResult', 'updateResult']:
                    funcname = "add_" + meta_name.replace('-', '_')
                # end if result_type
                #try:
                #    func = getattr(self, funcname)
                #except AttributeError:
                #    pass
                print "============>>>2=== %s %s/%s/%s. Calling '%s'.", %(
                        result_type.split('Result')[0].title(),
                        meta_name, idents, meta, funcname)

sub = Sub(ops)
print "===Starting sub===1"
ssrc_task = gevent.spawn(launch_ssrc, ops, sub)
print "===Starting sub===2"
gevent.joinall([ssrc_task])




