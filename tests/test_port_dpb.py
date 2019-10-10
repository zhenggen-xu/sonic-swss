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

    def getPortOid(self, dvs, port_name):
        cnt_r = redis.Redis(unix_socket_path=dvs.redis_sock, db=swsscommon.COUNTERS_DB)
        return cnt_r.hget("COUNTERS_PORT_NAME_MAP", port_name);

    def get_fvs_dict(self, fvs):
        fvs_dict = {}
        for fv in fvs:
            fvs_dict.update({fv[0]:fv[1]})
        return fvs_dict

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
        import pdb
        pdb.set_trace()
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

    '''
    @pytest.mark.skip()
    '''
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
        import pdb
        pdb.set_trace()
        #self.breakout(dvs, "Ethernet0", 2)
        #print "**** 1X100G --> 2X50G passed ****"
        #self.breakin(dvs, ["Ethernet0", "Ethernet2"])
        #print "**** 2X50G --> 1X100G passed ****"


    @pytest.mark.skip()
    def test_port_breakout_all_improved(self, dvs):
        cfg_db = swsscommon.DBConnector(swsscommon.CONFIG_DB, dvs.redis_sock, 0)
        cfg_db_ptbl = swsscommon.Table(cfg_db, "PORT")

        # Read ports and create child ports
        keys = cfg_db_ptbl.getKeys() 
        ports = []
        for k in keys:
            p = Port(dvs, k)
            p.sync_from_config_db()
            ports.append(p)

        child_ports = []
        for p in ports:
            for cp in p.port_split(p.get_num_lanes()):
                child_ports.append(cp)
        print "Created child port objects"

        # Delete ports
        for p in ports:
            p.delete_from_config_db()
            dvs.runcmd("ip link delete " + p.get_name()) #Should be done in VS-sai-redis?
        print "Deleted ports from kernel"

        # Verify ports are deleted from all DBs
        for p in ports:
            assert(p.exists_in_config_db() == False)
        for p in ports:
            assert(p.exists_in_app_db() == False)
        time.sleep(6)
        for p in ports:
            assert(p.exists_in_asic_db() == False)
        print "Verified ports are deleted from all DBs"

        # Add child ports
        for cp in child_ports:
            cp.write_to_config_db()
        print "Added child ports to config DB"

        for cp in child_ports:
            cp.verify_config_db()
        print "Config DB verification passed!"

        time.sleep(1)
        for cp in child_ports:
            cp.verify_app_db()
        print "Application DB verification passed!"

        time.sleep(6)
        for cp in child_ports:
            cp.verify_asic_db()
        print "ASIC DB verification passed!"

    @pytest.mark.skip()
    def test_port_breakout_all(self, dvs):
        cfg_db = swsscommon.DBConnector(swsscommon.CONFIG_DB, dvs.redis_sock, 0)
        cfg_db_port_table = swsscommon.Table(cfg_db, "PORT")
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

        print "Delete all net devices"
        for i in range(0, len(ports)):
            intf = ports[i]
            cmd = "ip link delete " + intf 
            print cmd
            dvs.runcmd(cmd)

        print "Breakout: Use the saved port info to create child ports"
        child_ports= []
        for k, fvs in ports_info.items():
            fvs_dict = self.get_fvs_dict(fvs)
            alias_str = fvs_dict['alias'] 
            lanes_str = fvs_dict['lanes']
            speed_str = fvs_dict['speed'] 
            index_str = fvs_dict['index'] 
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
                child_ports.append(child_port)

        time.sleep(1)
        print "Verification"
        app_db = swsscommon.DBConnector(swsscommon.APPL_DB, dvs.redis_sock, 0)
        app_db_ptbl = swsscommon.Table(app_db, swsscommon.APP_PORT_TABLE_NAME)
        for pname in child_ports:
            (status, fv) = app_db_ptbl.get(pname)
            assert status == True
        print "APP DB check passed"

        time.sleep(6) #TBD: Improve performance 
        asic_db = swsscommon.DBConnector(swsscommon.ASIC_DB, dvs.redis_sock, 0)
        asic_db_ptbl = swsscommon.Table(asic_db, "ASIC_STATE:SAI_OBJECT_TYPE_PORT")
        for pname in child_ports:
            port_oid = self.getPortOid(dvs, pname)
            (status, fv) = asic_db_ptbl.get(port_oid)
            assert status == True
        print "ASIC DB check passed"


        print "Delete all kernel interfaces of child ports" 
        for child_port in child_ports:
            cmd = "ip link delete " + child_port 
            print cmd
            dvs.runcmd(cmd)

