

# ssl options
secopts = {
    'use_certs': False,
    'keyfile': '',
    'certfile': '',
    'ca_certs': '',
    'ifmap_certauth_port': "8444",
}


ifmapops = {
	'ifmap_server_ip': '127.0.0.1',
	'ifmap_server_port': 8443,
	'ifmap_username': 'api-server',
	'ifmap_password': 'api-server',
}


ops = secopts.update(ifmapops)

