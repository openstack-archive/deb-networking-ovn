# Copyright 2016 Red Hat, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock

from networking_ovn.common import constants as ovn_const
from networking_ovn import ovn_db_sync
from networking_ovn.tests.unit.ml2 import test_mech_driver


class TestOvnNbSyncML2(test_mech_driver.OVNMechanismDriverTestCase):

    l3_plugin = 'networking_ovn.l3.l3_ovn.OVNL3RouterPlugin'

    def setUp(self):
        super(TestOvnNbSyncML2, self).setUp()

        self.subnet = {'cidr': '10.0.0.0/24',
                       'id': 'subnet1',
                       'subnetpool_id': None,
                       'name': 'private-subnet',
                       'enable_dhcp': True,
                       'network_id': 'n1',
                       'tenant_id': 'tenant1',
                       'gateway_ip': '10.0.0.1',
                       'ip_version': 4,
                       'shared': False}
        self.matches = ["", "", "", ""]

        self.networks = [{'id': 'n1'},
                         {'id': 'n2'}]

        self.security_groups = [
            {'id': 'sg1', 'tenant_id': 'tenant1',
             'security_group_rules': [{'remote_group_id': None,
                                       'direction': 'ingress',
                                       'remote_ip_prefix': '0.0.0.0/0',
                                       'protocol': 'tcp',
                                       'ethertype': 'IPv4',
                                       'tenant_id': 'tenant1',
                                       'port_range_max': 65535,
                                       'port_range_min': 1,
                                       'id': 'ruleid1',
                                       'security_group_id': 'sg1'}],
             'name': 'all-tcp'},
            {'id': 'sg2', 'tenant_id': 'tenant1',
             'security_group_rules': [{'remote_group_id': 'sg2',
                                       'direction': 'egress',
                                       'remote_ip_prefix': '0.0.0.0/0',
                                       'protocol': 'tcp',
                                       'ethertype': 'IPv4',
                                       'tenant_id': 'tenant1',
                                       'port_range_max': 65535,
                                       'port_range_min': 1,
                                       'id': 'ruleid1',
                                       'security_group_id': 'sg2'}],
             'name': 'all-tcpe'}]

        self.ports = [
            {'id': 'p1n1',
             'fixed_ips':
                 [{'subnet_id': 'b142f5e3-d434-4740-8e88-75e8e5322a40',
                   'ip_address': '10.0.0.4'},
                  {'subnet_id': 'subnet1',
                   'ip_address': 'fd79:e1c:a55::816:eff:eff:ff2'}],
             'security_groups': ['sg1'],
             'network_id': 'n1'},
            {'id': 'p2n1',
             'fixed_ips':
                 [{'subnet_id': 'b142f5e3-d434-4740-8e88-75e8e5322a40',
                   'ip_address': '10.0.0.4'},
                  {'subnet_id': 'subnet1',
                   'ip_address': 'fd79:e1c:a55::816:eff:eff:ff2'}],
             'security_groups': ['sg2'],
             'network_id': 'n1'},
            {'id': 'p1n2',
             'fixed_ips':
                 [{'subnet_id': 'b142f5e3-d434-4740-8e88-75e8e5322a40',
                   'ip_address': '10.0.0.4'},
                  {'subnet_id': 'subnet1',
                   'ip_address': 'fd79:e1c:a55::816:eff:eff:ff2'}],
             'security_groups': ['sg1'],
             'network_id': 'n2'},
            {'id': 'p2n2',
             'fixed_ips':
                 [{'subnet_id': 'b142f5e3-d434-4740-8e88-75e8e5322a40',
                   'ip_address': '10.0.0.4'},
                  {'subnet_id': 'subnet1',
                   'ip_address': 'fd79:e1c:a55::816:eff:eff:ff2'}],
             'security_groups': ['sg2'],
             'network_id': 'n2'}]
        self.acls_ovn = {
            'lport1':
            # ACLs need to be removed by the sync tool
            [{'id': 'acl1', 'priority': 00, 'policy': 'allow',
              'lswitch': 'lswitch1', 'lport': 'lport1'}],
            'lport2':
            [{'id': 'acl2', 'priority': 00, 'policy': 'drop',
             'lswitch': 'lswitch2', 'lport': 'lport2'}],
            # ACLs need to be kept as-is by the sync tool
            'p2n2':
            [{'lport': 'p2n2', 'direction': 'to-lport',
              'log': False, 'lswitch': 'neutron-n2',
              'priority': 1001, 'action': 'drop',
             'external_ids': {'neutron:lport': 'p2n2'},
              'match': 'outport == "p2n2" && ip'},
             {'lport': 'p2n2', 'direction': 'to-lport',
              'log': False, 'lswitch': 'neutron-n2',
              'priority': 1002, 'action': 'allow',
              'external_ids': {'neutron:lport': 'p2n2'},
              'match': 'outport == "p2n2" && ip4 && '
              'ip4.src == 10.0.0.0/24 && udp && '
              'udp.src == 67 && udp.dst == 68'}]}
        self.address_sets_ovn = {
            'as_ip4_sg1': {'external_ids': {ovn_const.OVN_SG_NAME_EXT_ID_KEY:
                                            'all-tcp'},
                           'name': 'as_ip4_sg1',
                           'addresses': ['10.0.0.4']},
            'as_ip4_sg2': {'external_ids': {ovn_const.OVN_SG_NAME_EXT_ID_KEY:
                                            'all-tcpe'},
                           'name': 'as_ip4_sg2',
                           'addresses': []},
            'as_ip6_sg2': {'external_ids': {ovn_const.OVN_SG_NAME_EXT_ID_KEY:
                                            'all-tcpe'},
                           'name': 'as_ip6_sg2',
                           'addresses': ['fd79:e1c:a55::816:eff:eff:ff2',
                                         'fd79:e1c:a55::816:eff:eff:ff3']},
            'as_ip4_del': {'external_ids': {ovn_const.OVN_SG_NAME_EXT_ID_KEY:
                                            'all-delete'},
                           'name': 'as_ip4_delete',
                           'addresses': ['10.0.0.4']},
            }

        self.routers = [{'id': 'r1', 'routes': []},
                        {'id': 'r2', 'routes': [{'nexthop': '40.0.0.100',
                         'destination': '30.0.0.0/24'}]}]

        self.get_sync_router_ports = [
            {'fixed_ips': [{'subnet_id': 'subnet1',
                            'ip_address': '192.168.1.1'}],
             'id': 'p1r1',
             'device_id': 'r1',
             'mac_address': 'fa:16:3e:d7:fd:5f'},
            {'fixed_ips': [{'subnet_id': 'subnet2',
                            'ip_address': '192.168.2.1'}],
             'id': 'p1r2',
             'device_id': 'r2',
             'mac_address': 'fa:16:3e:d6:8b:ce'}]

        self.lrouters_with_rports = [{'name': 'r3',
                                      'ports': ['p1r3'],
                                      'static_routes': []},
                                     {'name': 'r1',
                                      'ports': ['p3r1'],
                                      'static_routes':
                                      [{'nexthop': '20.0.0.100',
                                        'destination': '10.0.0.0/24'}]}]

        self.lswitches_with_ports = [{'name': 'neutron-n1',
                                      'ports': ['p1n1', 'p3n1']},
                                     {'name': 'neutron-n3',
                                      'ports': ['p1n3', 'p2n3']}]

    def _test_mocks_helper(self, ovn_nb_synchronizer):
        core_plugin = ovn_nb_synchronizer.core_plugin
        ovn_api = ovn_nb_synchronizer.ovn_api
        ovn_driver = ovn_nb_synchronizer.ovn_driver
        l3_plugin = ovn_nb_synchronizer.l3_plugin

        core_plugin.get_networks = mock.Mock()
        core_plugin.get_networks.return_value = self.networks

        # following block is used for acl syncing unit-test

        # With the given set of values in the unit testing,
        # 19 neutron acls should have been there,
        # 4 acls are returned as current ovn acls,
        # two of which will match with neutron.
        # So, in this example 17 will be added, 2 removed
        core_plugin.get_ports = mock.Mock()
        core_plugin.get_ports.return_value = self.ports
        mock.patch(
            "networking_ovn.common.acl._get_subnet_from_cache",
            return_value=self.subnet
        ).start()
        mock.patch(
            "networking_ovn.common.acl.acl_remote_group_id",
            side_effect=self.matches
        ).start()
        core_plugin.get_security_group = mock.MagicMock(
            side_effect=self.security_groups)
        ovn_nb_synchronizer.get_acls = mock.Mock()
        ovn_nb_synchronizer.get_acls.return_value = self.acls_ovn
        core_plugin.get_security_groups = mock.MagicMock(
            return_value=self.security_groups)
        ovn_nb_synchronizer.get_address_sets = mock.Mock()
        ovn_nb_synchronizer.get_address_sets.return_value =\
            self.address_sets_ovn
        # end of acl-sync block

        # The following block is used for router and router port syncing tests
        # With the give set of values in the unit test,
        # The Neutron db has Routers r1 and r2 present.
        # The OVN db has Routers r1 and r3 present.
        # During the sync r2 will need to be created and r3 will need
        # to be deleted from the OVN db. When Router r3 is deleted, all LRouter
        # ports associated with r3 is deleted too.
        #
        # Neutron db has Router ports p1r1 in Router r1 and p1r2 in Router r2
        # OVN db has p1r3 in Router 3 and p3r1 in Router 1.
        # During the sync p1r1 and p1r2 will be added and p1r3 and p3r1
        # will be deleted from the OVN db
        l3_plugin.get_routers = mock.Mock()
        l3_plugin.get_routers.return_value = self.routers
        l3_plugin._get_sync_interfaces = mock.Mock()
        l3_plugin._get_sync_interfaces.return_value = (
            self.get_sync_router_ports)
        # end of router-sync block

        ovn_api.get_all_logical_switches_with_ports = mock.Mock()
        ovn_api.get_all_logical_switches_with_ports.return_value = (
            self.lswitches_with_ports)

        ovn_api.get_all_logical_routers_with_rports = mock.Mock()
        ovn_api.get_all_logical_routers_with_rports.return_value = (
            self.lrouters_with_rports)

        ovn_api.transaction = mock.MagicMock()

        ovn_driver.create_network_in_ovn = mock.Mock()
        ovn_driver.create_port_in_ovn = mock.Mock()
        ovn_driver.validate_and_get_data_from_binding_profile = mock.Mock()
        ovn_driver.get_ovn_port_options = mock.Mock()
        ovn_driver.get_ovn_port_options.return_value = mock.ANY
        ovn_api.delete_lswitch = mock.Mock()
        ovn_api.delete_lswitch_port = mock.Mock()

        l3_plugin.create_lrouter_in_ovn = mock.Mock()
        l3_plugin.create_lrouter_port_in_ovn = mock.Mock()
        ovn_api.delete_lrouter = mock.Mock()
        ovn_api.delete_lrouter_port = mock.Mock()
        ovn_api.add_static_route = mock.Mock()
        ovn_api.delete_static_route = mock.Mock()

        ovn_api.create_address_set = mock.Mock()
        ovn_api.delete_address_set = mock.Mock()
        ovn_api.update_address_set = mock.Mock()

    def _test_ovn_nb_sync_helper(self, ovn_nb_synchronizer,
                                 networks, ports,
                                 routers, router_ports,
                                 create_router_list, create_router_port_list,
                                 del_router_list, del_router_port_list,
                                 create_network_list, create_port_list,
                                 del_network_list, del_port_list,
                                 add_static_route_list, del_static_route_list,
                                 add_address_set_list, del_address_set_list,
                                 update_address_set_list):
        self._test_mocks_helper(ovn_nb_synchronizer)

        core_plugin = ovn_nb_synchronizer.core_plugin
        ovn_api = ovn_nb_synchronizer.ovn_api
        ovn_driver = ovn_nb_synchronizer.ovn_driver
        l3_plugin = ovn_nb_synchronizer.l3_plugin

        ovn_nb_synchronizer.sync_address_sets(mock.MagicMock())
        ovn_nb_synchronizer.sync_networks_and_ports(mock.ANY)
        ovn_nb_synchronizer.sync_acls(mock.ANY)
        ovn_nb_synchronizer.sync_routers_and_rports(mock.ANY)

        get_security_group_calls = [mock.call(mock.ANY, sg['id'])
                                    for sg in self.security_groups]
        self.assertEqual(core_plugin.get_security_group.call_count,
                         len(self.security_groups))
        core_plugin.get_security_group.assert_has_calls(
            get_security_group_calls, any_order=True)

        self.assertEqual(ovn_driver.create_network_in_ovn.call_count,
                         len(create_network_list))
        create_network_calls = [mock.call(net['net'], net['ext_ids'],
                                          None, None)
                                for net in create_network_list]
        ovn_driver.create_network_in_ovn.assert_has_calls(
            create_network_calls, any_order=True)

        self.assertEqual(ovn_driver.create_port_in_ovn.call_count,
                         len(create_port_list))
        create_port_calls = [mock.call(port, mock.ANY)
                             for port in create_port_list]
        ovn_driver.create_port_in_ovn.assert_has_calls(create_port_calls,
                                                       any_order=True)

        self.assertEqual(ovn_api.delete_lswitch.call_count,
                         len(del_network_list))
        delete_lswitch_calls = [mock.call(lswitch_name=net_name)
                                for net_name in del_network_list]
        ovn_api.delete_lswitch.assert_has_calls(
            delete_lswitch_calls, any_order=True)

        self.assertEqual(ovn_api.delete_lswitch_port.call_count,
                         len(del_port_list))
        delete_lswitch_port_calls = [mock.call(lport_name=port['id'],
                                               lswitch_name=port['lswitch'])
                                     for port in del_port_list]
        ovn_api.delete_lswitch_port.assert_has_calls(
            delete_lswitch_port_calls, any_order=True)

        self.assertEqual(ovn_api.add_static_route.call_count,
                         len(add_static_route_list))

        self.assertEqual(ovn_api.delete_static_route.call_count,
                         len(del_static_route_list))

        create_router_calls = [mock.call(r)
                               for r in create_router_list]
        self.assertEqual(
            l3_plugin.create_lrouter_in_ovn.call_count,
            len(create_router_list))
        l3_plugin.create_lrouter_in_ovn.assert_has_calls(
            create_router_calls, any_order=True)

        create_router_port_calls = [mock.call(mock.ANY,
                                              p['device_id'],
                                              mock.ANY)
                                    for p in create_router_port_list]
        self.assertEqual(
            l3_plugin.create_lrouter_port_in_ovn.call_count,
            len(create_router_port_list))
        l3_plugin.create_lrouter_port_in_ovn.assert_has_calls(
            create_router_port_calls,
            any_order=True)

        self.assertEqual(ovn_api.delete_lrouter.call_count,
                         len(del_router_list))
        delete_lrouter_calls = [mock.call(r['router'])
                                for r in del_router_list]
        ovn_api.delete_lrouter.assert_has_calls(
            delete_lrouter_calls, any_order=True)

        self.assertEqual(
            ovn_api.delete_lrouter_port.call_count,
            len(del_router_port_list))
        delete_lrouter_port_calls = [mock.call(port['id'],
                                               port['router'], if_exists=False)
                                     for port in del_router_port_list]
        ovn_api.delete_lrouter_port.assert_has_calls(
            delete_lrouter_port_calls, any_order=True)

        create_address_set_calls = [mock.call(**a)
                                    for a in add_address_set_list]
        self.assertEqual(
            ovn_api.create_address_set.call_count,
            len(add_address_set_list))
        ovn_api.create_address_set.assert_has_calls(
            create_address_set_calls, any_order=True)

        del_address_set_calls = [mock.call(**d)
                                 for d in del_address_set_list]
        self.assertEqual(
            ovn_api.delete_address_set.call_count,
            len(del_address_set_list))
        ovn_api.delete_address_set.assert_has_calls(
            del_address_set_calls, any_order=True)

        update_address_set_calls = [mock.call(**u)
                                    for u in update_address_set_list]
        self.assertEqual(
            ovn_api.update_address_set.call_count,
            len(update_address_set_list))
        ovn_api.update_address_set.assert_has_calls(
            update_address_set_calls, any_order=True)

    def test_ovn_nb_sync_mode_repair(self):
        create_network_list = [{'net': {'id': 'n2'}, 'ext_ids': {}}]
        del_network_list = ['neutron-n3']
        del_port_list = [{'id': 'p3n1', 'lswitch': 'neutron-n1'},
                         {'id': 'p1n1', 'lswitch': 'neutron-n1'}]
        create_port_list = self.ports
        for port in create_port_list:
            if port['id'] == 'p1n1':
                # this will be skipped by the logic,
                # because it is already in lswitch-port list
                create_port_list.remove(port)

        create_router_list = [{'id': 'r2', 'routes': [{'nexthop': '40.0.0.100',
                               'destination': '30.0.0.0/24'}]}]
        add_static_route_list = [{'destination': '30.0.0.0/24',
                                  'nexthop': '40.0.0.100'}]
        del_static_route_list = [{'nexthop': '20.0.0.100',
                                  'destination': '10.0.0.0/24'}]

        del_router_list = [{'router': 'neutron-r3'}]
        del_router_port_list = [{'id': 'lrp-p3r1', 'router': 'neutron-r1'}]
        create_router_port_list = self.get_sync_router_ports

        add_address_set_list = [
            {'external_ids': {ovn_const.OVN_SG_NAME_EXT_ID_KEY:
                              'all-tcp'},
             'name': 'as_ip6_sg1',
             'addresses': ['fd79:e1c:a55::816:eff:eff:ff2']}]
        del_address_set_list = [{'name': 'as_ip4_del'}]
        update_address_set_list = [
            {'addrs_remove': [],
             'addrs_add': ['10.0.0.4'],
             'name': 'as_ip4_sg2'},
            {'addrs_remove': ['fd79:e1c:a55::816:eff:eff:ff3'],
             'addrs_add': [],
             'name': 'as_ip6_sg2'}]

        ovn_nb_synchronizer = ovn_db_sync.OvnNbSynchronizer(
            self.plugin, self.mech_driver._nb_ovn, 'repair', self.mech_driver)
        self._test_ovn_nb_sync_helper(ovn_nb_synchronizer,
                                      self.networks,
                                      self.ports,
                                      self.routers,
                                      self.get_sync_router_ports,
                                      create_router_list,
                                      create_router_port_list,
                                      del_router_list, del_router_port_list,
                                      create_network_list, create_port_list,
                                      del_network_list, del_port_list,
                                      add_static_route_list,
                                      del_static_route_list,
                                      add_address_set_list,
                                      del_address_set_list,
                                      update_address_set_list)

    def test_ovn_nb_sync_mode_log(self):
        create_network_list = []
        create_port_list = []
        del_network_list = []
        del_port_list = []
        create_router_list = []
        create_router_port_list = []
        del_router_list = []
        del_router_port_list = []
        add_static_route_list = []
        del_static_route_list = []
        add_address_set_list = []
        del_address_set_list = []
        update_address_set_list = []

        ovn_nb_synchronizer = ovn_db_sync.OvnNbSynchronizer(
            self.plugin, self.mech_driver._nb_ovn, 'log', self.mech_driver)
        self._test_ovn_nb_sync_helper(ovn_nb_synchronizer,
                                      self.networks,
                                      self.ports,
                                      self.routers,
                                      self.get_sync_router_ports,
                                      create_router_list,
                                      create_router_port_list,
                                      del_router_list, del_router_port_list,
                                      create_network_list, create_port_list,
                                      del_network_list, del_port_list,
                                      add_static_route_list,
                                      del_static_route_list,
                                      add_address_set_list,
                                      del_address_set_list,
                                      update_address_set_list)


class TestOvnSbSyncML2(test_mech_driver.OVNMechanismDriverTestCase):

    def test_ovn_sb_sync(self):
        ovn_sb_synchronizer = ovn_db_sync.OvnSbSynchronizer(
            self.plugin,
            self.mech_driver._sb_ovn,
            self.mech_driver)
        ovn_api = ovn_sb_synchronizer.ovn_api
        hostname_with_physnets = {'hostname1': ['physnet1', 'physnet2'],
                                  'hostname2': ['physnet1']}
        ovn_api.get_chassis_hostname_and_physnets.return_value = (
            hostname_with_physnets)
        ovn_driver = ovn_sb_synchronizer.ovn_driver
        ovn_driver.update_segment_host_mapping = mock.Mock()
        hosts_in_neutron = {'hostname2', 'hostname3'}

        with mock.patch.object(ovn_db_sync.segments_db,
                               'get_hosts_mapped_with_segments',
                               return_value=hosts_in_neutron):
            ovn_sb_synchronizer.sync_hostname_and_physical_networks(mock.ANY)
            all_hosts = set(hostname_with_physnets.keys()) | hosts_in_neutron
            self.assertEqual(
                len(all_hosts),
                ovn_driver.update_segment_host_mapping.call_count)
            update_segment_host_mapping_calls = [mock.call(
                host, hostname_with_physnets[host])
                for host in hostname_with_physnets]
            update_segment_host_mapping_calls += [
                mock.call(host, []) for host in
                hosts_in_neutron - set(hostname_with_physnets.keys())]
            ovn_driver.update_segment_host_mapping.assert_has_calls(
                update_segment_host_mapping_calls, any_order=True)
