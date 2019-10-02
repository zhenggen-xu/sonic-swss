from swsscommon import swsscommon
import redis
import time
import os
import pytest
from pytest import *
import json

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
def my_fixture(dvs):
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

@pytest.mark.skip("Skipping for now")
@pytest.mark.usefixtures('my_fixture')
class TestPortDPB(object):
  
    def test_sample1(self):
        print "From test_sample1"
        return ''

    def test_port_breakout_all(self, dvs):
        cfg_db = swsscommon.DBConnector(swsscommon.CONFIG_DB, dvs.redis_sock, 0)
        cfg_db_port_table = swsscommon.Table(cfg_db, "PORT")
        cfg_db_port_table_producer = swsscommon.ProducerStateTable(cfg_db, "PORT")

        ports = cfg_db_port_table.getKeys() 
        print "Num of ports: %d" % len(ports)

        print "Delete all ports from configDB"
        ports_info = {}
        for i in range(0, len(ports)):
            k = ports[i]
            (status, fvs) = cfg_db_port_table.get(k)
            assert status == True
            ports_info[k] = fvs 
            print "Delete %s" %(k)
            cfg_db_port_table._del(k)

        print "Wait for 10 seconds"
        time.sleep(10)

        print "Delete all net devices"
        for i in range(0, len(ports)):
            time.sleep(2)
            intf = ports[i]
            cmd = "ip link delete " + intf 
            print cmd
            dvs.runcmd(cmd)

        print "Breakout: Use the saved port info to create child ports"
        for k, fvs in ports_info.items():
            alias_str = fvs[0][1]
            lanes_str = fvs[1][1]
            speed_str = fvs[2][1]
            index_str = fvs[3][1]
            print "Port: %s Lanes: %s Speed: %s, Index: %s" %(k, lanes_str, speed_str, index_str) 

            port_num = int(k.replace("Ethernet", ""))
            lanes_list = list(lanes_str.split(","))
            num_lanes = len(lanes_list)

            num_child_ports = num_lanes
            child_port_speed = int(speed_str)/num_child_ports
            child_port_speed_str = str(child_port_speed)

            print "Create %d child ports each with 1 lane and %sMB speed" %(num_child_ports, child_port_speed_str)
            start_child_port_num = port_num
            for offset in range(num_child_ports):
                child_port_num = port_num+offset
                child_lanes_list = []
                child_lanes_list.append(int(lanes_list[offset]))
                print child_lanes_list
                child_lanes_str = str(child_lanes_list)[1:-1]
                child_index_str = index_str
                child_alias_str = "Eth%d/%d"%(port_num, offset)
                fvs = swsscommon.FieldValuePairs([("alias", child_alias_str),
                                                  ("lanes", child_lanes_str),
                                                  ("speed", child_port_speed_str),
                                                  ("index", child_index_str)])
                child_port = "Ethernet%d"%(port_num+offset)
                cfg_db_port_table.set(child_port, fvs)
        import pdb
        pdb.set_trace()
