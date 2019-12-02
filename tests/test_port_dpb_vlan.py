from swsscommon import swsscommon
import redis
import time
import os
import pytest
from pytest import *
import json
import re
from port_dpb import Port
from port_dpb import DPB

@pytest.mark.usefixtures('dpb_setup_fixture')
class TestPortDPBVlan(object):
    def check_syslog(self, dvs, marker, log, expected_cnt):
        (exitcode, num) = dvs.runcmd(['sh', '-c', "awk \'/%s/,ENDFILE {print;}\' /var/log/syslog | grep \"%s\" | wc -l" % (marker, log)])
        assert num.strip() >= str(expected_cnt)

    '''
    @pytest.mark.skip()
    '''
    def test_dependency(self, dvs):
        dpb = DPB() 
        dvs.setup_db()
        p = Port(dvs, "Ethernet0")
        p.sync_from_config_db()
        dvs.create_vlan("100")
        #print "Created VLAN100"
        dvs.create_vlan_member("100", p.get_name())
        #print "Added Ethernet0 to VLAN100"
        marker = dvs.add_log_marker()
        p.delete_from_config_db()
        #Verify that we are looping on dependency
        time.sleep(2)
        self.check_syslog(dvs, marker, "doPortTask: Please remove port dependenc(y/ies):VLAN", 1)
        assert(p.exists_in_asic_db() == True)

        dvs.remove_vlan_member("100", p.get_name())
        time.sleep(2)
        # Verify that port is deleted
        assert(p.exists_in_asic_db() == False)

        #Create the port back and delete the VLAN
        p.write_to_config_db() 
        #print "Added port:%s to config DB"%p.get_name()
        p.verify_config_db()
        #print "Config DB verification passed!"
        p.verify_app_db()
        #print "Application DB verification passed!"
        p.verify_asic_db()
        #print "ASIC DB verification passed!"
       
        dvs.remove_vlan("100") 

    '''
    @pytest.mark.skip()
    '''
    def test_one_port_one_vlan(self, dvs):
        dpb = DPB()
        dvs.setup_db()

        # Breakout testing with VLAN dependency
        dvs.create_vlan("100")
        #print "Created VLAN100"
        dvs.create_vlan_member("100", "Ethernet0")
        #print "Added Ethernet0 to VLAN100"

        p = Port(dvs, "Ethernet0")
        p.sync_from_config_db()
        p.delete_from_config_db()
        assert(p.exists_in_config_db() == False)
        assert(p.exists_in_app_db() == False)
        assert(p.exists_in_asic_db() == True)
        #print "Ethernet0 deleted from config DB and APP DB, waiting to be removed from VLAN"

        dvs.remove_vlan_member("100", "Ethernet0")
        assert(p.exists_in_asic_db() == False)
        #print "Ethernet0 removed from VLAN and also from ASIC DB"

        dpb.create_child_ports(dvs, p, 4)

        # Breakin testing with VLAN dependency
        port_names = ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"]
        for pname in port_names:
            dvs.create_vlan_member("100", pname)
        #print "Add %s to VLAN"%port_names            

        child_ports = []
        for pname in port_names:
            cp = Port(dvs, pname)
            cp.sync_from_config_db()
            cp.delete_from_config_db()
            assert(cp.exists_in_config_db() == False)
            assert(cp.exists_in_app_db() == False)
            assert(cp.exists_in_asic_db() == True)
            child_ports.append(cp)
        #print "Deleted %s from config DB and APP DB"%port_names            

        for cp in child_ports:
            dvs.remove_vlan_member("100", cp.get_name())
            time.sleep(1)
            assert(cp.exists_in_asic_db() == False)
        #print "Deleted %s from VLAN"%port_names            

        p.write_to_config_db() 
        #print "Added port:%s to config DB"%p.get_name()
        p.verify_config_db()
        #print "Config DB verification passed!"
        p.verify_app_db()
        #print "Application DB verification passed!"
        p.verify_asic_db()
        #print "ASIC DB verification passed!"

        dvs.remove_vlan("100")

    '''    
    @pytest.mark.skip()
    '''
    def test_one_port_multiple_vlan(self, dvs):
        dpb = DPB()
        dvs.setup_db()

        dvs.create_vlan("100")
        dvs.create_vlan("101")
        dvs.create_vlan("102")
        #print "Created VLAN100, VLAN101, and VLAN102"
        dvs.create_vlan_member("100", "Ethernet0")
        dvs.create_vlan_member("101", "Ethernet0")
        dvs.create_vlan_member("102", "Ethernet0")
        #print "Added Ethernet0 to all three VLANs"

        p = Port(dvs, "Ethernet0")
        p.sync_from_config_db()
        p.delete_from_config_db()
        assert(p.exists_in_config_db() == False)
        assert(p.exists_in_app_db() == False)
        assert(p.exists_in_asic_db() == True)
        #print "Ethernet0 deleted from config DB and APP DB, waiting to be removed from VLANs"

        dvs.remove_vlan_member("100", "Ethernet0")
        assert(p.exists_in_asic_db() == True)
        #print "Ethernet0 removed from VLAN100 and its still present in ASIC DB"

        dvs.remove_vlan_member("101", "Ethernet0")
        assert(p.exists_in_asic_db() == True)
        #print "Ethernet0 removed from VLAN101 and its still present in ASIC DB"

        dvs.remove_vlan_member("102", "Ethernet0")
        assert(p.exists_in_asic_db() == False)
        #print "Ethernet0 removed from VLAN101 and also from ASIC DB"

        dpb.create_child_ports(dvs, p, 4)
        #print "1X40G ---> 4x10G verified"

        # Breakin
        port_names = ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"]
        for pname in port_names:
            cp = Port(dvs, pname)
            cp.sync_from_config_db()
            cp.delete_from_config_db()
            assert(cp.exists_in_config_db() == False)
            assert(cp.exists_in_app_db() == False)
            assert(cp.exists_in_asic_db() == False)
        #print "Deleted %s and verified all DBs"%port_names            

        #Add back Ethernet0
        p.write_to_config_db() 
        p.verify_config_db()
        p.verify_app_db()
        p.verify_asic_db()
        #print "Added port:%s and verified all DBs"%p.get_name()

        # Remove all three VLANs
        dvs.remove_vlan("100")
        dvs.remove_vlan("101")
        dvs.remove_vlan("102")
        #print "All three VLANs removed"


