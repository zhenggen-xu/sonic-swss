from swsscommon import swsscommon
import redis
import time
import os
import pytest
from pytest import *
import json
import re
from port_dpb import Port

@pytest.yield_fixture(scope="class")
def create_dpb_config_file(dvs):
    cmd = "sonic-cfggen -j /etc/sonic/init_cfg.json -j /tmp/ports.json --print-data > /tmp/dpb_config_db.json"
    dvs.runcmd(['sh', '-c', cmd])
    cmd = "mv /etc/sonic/config_db.json /etc/sonic/config_db.json.bak"
    dvs.runcmd(cmd)
    cmd = "cp /tmp/dpb_config_db.json /etc/sonic/config_db.json"
    dvs.runcmd(cmd)

@pytest.yield_fixture(scope="class")
def remove_dpb_config_file(dvs):
    cmd = "mv /etc/sonic/config_db.json.bak /etc/sonic/config_db.json"
    dvs.runcmd(cmd)

@pytest.yield_fixture(scope="class", autouse=True)
def dpb_setup_fixture(dvs):
    start_cmd = "/usr/bin/start.sh"

    print "Set Up"
    create_dpb_config_file(dvs)
    #dvs.restart()
    dvs.stop_all_daemons()
    dvs.runcmd(start_cmd)

    yield

    print "Tear Down"
    remove_dpb_config_file(dvs)
    #dvs.restart()
    dvs.stop_all_daemons()
    dvs.runcmd(start_cmd)
        
@pytest.mark.usefixtures('dpb_setup_fixture')
class TestPortDPB(object):

    def breakin(self, dvs, port_names):
        child_ports = []
        for pname in port_names:
            cp = Port(dvs, pname)
            cp.sync_from_config_db()
            child_ports.append(cp)

        for cp in child_ports:
            cp.delete_from_config_db()
            dvs.runcmd("ip link delete " + cp.get_name())
        print "Deleted child ports from config DB"

        for cp in child_ports:
            assert(cp.exists_in_config_db() == False)
        for cp in child_ports:
            assert(cp.exists_in_app_db() == False)
        time.sleep(6)
        for cp in child_ports:
            assert(cp.exists_in_asic_db() == False)
        print "Verified child ports are deleted from all DBs"

        p = Port(dvs)  
        p.port_merge(child_ports)
        p.write_to_config_db()
        print "Added port to config DB"

        p.verify_config_db()
        print "Config DB verification passed!"

        time.sleep(1)
        p.verify_app_db()
        print "Application DB verification passed!"

        time.sleep(6)
        p.verify_asic_db()
        print "ASIC DB verification passed!"

    def breakout(self, dvs, port_name, num_child_ports):

        p = Port(dvs, port_name)
        p.sync_from_config_db()

        # Delete port from config DB and kernel
        p.delete_from_config_db()
        dvs.runcmd("ip link delete " + p.get_name())

        # Verify port is deleted from all DBs
        assert(p.exists_in_config_db() == False)
        assert(p.exists_in_app_db() == False)
        time.sleep(6)
        assert(p.exists_in_asic_db() == False)

        # Create child ports and write to config DB
        child_ports = p.port_split(num_child_ports) 
        for cp in child_ports:
            cp.write_to_config_db()
        print "Added child ports to config DB"

        time.sleep(1)
        for cp in child_ports:
            assert(cp.exists_in_config_db() == True)
            cp.verify_config_db()
        print "Config DB verification passed"

        for cp in child_ports:
            assert(cp.exists_in_app_db() == True)
            cp.verify_app_db()
        print "APP DB verification passed"

        for cp in child_ports:
            assert(cp.exists_in_asic_db() == True)
            cp.verify_asic_db()
        print "ASIC DB verification passed"

    @pytest.mark.skip()
    def test_port_1X40G(self, dvs):
        self.breakout(dvs, "Ethernet0", 4)
        print "**** 1X40G --> 4X10G passed ****"
        self.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        print "**** 4X10G --> 1X40G passed ****"

    @pytest.mark.skip()
    def test_port_1X100G(self, dvs):

        # Change Ethernet0 speed to 100G
        p = Port(dvs, "Ethernet0")
        p.sync_from_config_db()
        p.set_speed(100000)
        p.write_to_config_db()
        p.verify_config_db()
        time.sleep(1)
        p.verify_app_db()
        time.sleep(1)
        p.verify_asic_db()

        self.breakout(dvs, "Ethernet0", 4)
        print "**** 1X100G --> 4X25G passed ****"
        self.breakin(dvs, ["Ethernet0", "Ethernet1", "Ethernet2", "Ethernet3"])
        print "**** 4X25G --> 1X100G passed ****"
        self.breakout(dvs, "Ethernet0", 2)
        print "**** 1X100G --> 2X50G passed ****"
        self.breakin(dvs, ["Ethernet0", "Ethernet2"])
        print "**** 2X50G --> 1X100G passed ****"


    '''
    @pytest.mark.skip()
    '''
    def test_port_breakout_all_4X10G(self, dvs):
        port_names = []
        for i in range(32):
            pname = "Ethernet" + str(i*4)
            port_names.append(pname)

        for pname in port_names:
            self.breakout(dvs, pname, 4)

        import pdb
        pdb.set_trace()
        child_port_names = []
        for i in range(128):
            cpname = "Ethernet" + str(i)
            child_port_names.append(cpname)

        for i in range(32):
            start = i*4
            end = start+4
            self.breakin(dvs, child_port_names[start:end])
        import pdb
        pdb.set_trace()
