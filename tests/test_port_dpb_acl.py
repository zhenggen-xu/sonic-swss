from swsscommon import swsscommon
import redis
import time
import os
import pytest
from pytest import *
import json
import re
from port_dpb import Port
from test_port_dpb import TestPortDPB

@pytest.mark.usefixtures('dpb_setup_fixture')
class TestPortDPBAcl(object):

    '''
    @pytest.mark.skip()
    '''
    def test_one_port_one_acl(self, dvs):
        dvs.setup_db()

        # Create ACL table and bind it to Ethernet0 and Ethernet4
        bind_ports = ["Ethernet0", "Ethernet4"]
        dvs.create_acl_table("test", "L3", bind_ports)
        time.sleep(2)
        acl_table_id = dvs.get_acl_table_id()
        assert acl_table_id
        dvs.verify_acl_group_num(2)
        acl_group_ids = dvs.get_acl_group_ids()
        dvs.verify_acl_group_member(acl_group_ids, acl_table_id)
        dvs.verify_acl_port_binding(bind_ports)

        # Update bind list and verify
        bind_ports = ["Ethernet4"]
        dvs.create_acl_table("test", "L3", bind_ports)
        time.sleep(2)
        dvs.verify_acl_group_num(1)
        acl_group_ids = dvs.get_acl_group_ids()
        dvs.verify_acl_group_member(acl_group_ids, acl_table_id)
        dvs.verify_acl_port_binding(bind_ports)

        # Breakout Ethernet0
        dpb = TestPortDPB()
        dpb.breakout(dvs, "Ethernet0", 4)
        time.sleep(2)

        #Update bind list and verify
        bind_ports = ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3","Ethernet4"]
        dvs.create_acl_table("test", "L3", bind_ports)
        time.sleep(2)
        dvs.verify_acl_group_num(5)
        acl_group_ids = dvs.get_acl_group_ids()
        dvs.verify_acl_group_member(acl_group_ids, acl_table_id)
        dvs.verify_acl_port_binding(bind_ports)
        time.sleep(2)

        # Update bind list and verify
        bind_ports = ["Ethernet4"]
        dvs.create_acl_table("test", "L3", bind_ports)
        dvs.verify_acl_group_num(1)
        acl_group_ids = dvs.get_acl_group_ids()
        dvs.verify_acl_group_member(acl_group_ids, acl_table_id)
        dvs.verify_acl_port_binding(bind_ports)

        #Breakin Ethernet0, 1, 2, 3
        dpb.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        time.sleep(2)

        # Update bind list and verify
        bind_ports = ["Ethernet0", "Ethernet4"]
        dvs.create_acl_table("test", "L3", bind_ports)
        time.sleep(2)
        dvs.verify_acl_group_num(2)
        acl_group_ids = dvs.get_acl_group_ids()
        dvs.verify_acl_group_member(acl_group_ids, acl_table_id)
        dvs.verify_acl_port_binding(bind_ports)

        #Delete ACL table
        dvs.remove_acl_table("test")
        time.sleep(2)
        dvs.verify_acl_group_num(0)

    @pytest.mark.skip()
    def test_two_port_one_acl(self, dvs):
        #TBD
        return 
