from swsscommon import swsscommon
import redis
import time
import os
import pytest
from pytest import *
import json
import re

class Port():
    def __init__(self, dvs, name = None):
        self._name = name
        if name != None:
            self._port_num = int(re.compile(r'(\d+)$').search(self._name).group(1)) 
        self._alias = None
        self._speed = None
        self._lanes = []
        self._index = None
        self._lanes_db_str = None
        self._lanes_asic_db_str = None
        self._oid = None
        self._dvs = dvs
        self._cfg_db = swsscommon.DBConnector(swsscommon.CONFIG_DB, dvs.redis_sock, 0)
        self._cfg_db_ptbl = swsscommon.Table(self._cfg_db, "PORT")
        self._app_db = swsscommon.DBConnector(swsscommon.APPL_DB, dvs.redis_sock, 0)
        self._app_db_ptbl = swsscommon.Table(self._app_db, swsscommon.APP_PORT_TABLE_NAME)
        self._asic_db = swsscommon.DBConnector(swsscommon.ASIC_DB, dvs.redis_sock, 0)
        self._asic_db_ptbl = swsscommon.Table(self._asic_db, "ASIC_STATE:SAI_OBJECT_TYPE_PORT")

    def set_name(self, name):
        self._name = name
        self._port_num = int(re.compile(r'(\d+)$').search(self._name).group(1))

    def set_speed(self, speed):
        self._speed = speed

    def set_alias(self, alias):
        self._alias = alias

    def set_lanes(self, lanes):
        self._lanes = lanes
        lanes_list = []
        for lane in lanes:
            lanes_list.append(int(lane))
        lanes_list.sort()
        self._lanes_db_str = str(lanes_list)[1:-1]
        self._lanes_asic_db_str = str(len(lanes)) + ":" + self._lanes_db_str
        self._lanes_asic_db_str = self._lanes_asic_db_str.replace(" ", "")

    def set_index(self, index):
        self._index = index

    def get_speed(self):
        return self._speed

    def get_alias(self):
        return self._alias

    def get_lanes(self):
        return self._lanes

    def get_num_lanes(self):
        return len(self._lanes)

    def get_index(self):
        return self._index

    def get_name(self):
        return self._name

    def get_port_num(self):
        return self._port_num 

    def get_lanes_db_str(self):
        return self._lanes_db_str

    def get_lanes_asic_db_str(self):
        return self._lanes_asic_db_str

    def get_oid(self):
        return self._oid

    def print_port(self):
        print "Port: %s Lanes: %s Speed: %d, Index: %d"%(self._name, self._lanes, self._speed, self._index) 

    def port_merge(self, child_ports):
        child_ports.sort(key=lambda x: x.get_port_num())
        self.set_name(child_ports[0].get_name())
        speed = 0
        for cp in child_ports:
            speed = speed + cp.get_speed()
        self.set_speed(speed)
        self.set_alias(child_ports[0].get_alias().rsplit(',',1)[0])
        self.set_index(child_ports[0].get_index())
        lanes =[]
        for cp in child_ports:
            for l in cp.get_lanes():
                lanes.append(l)
        self.set_lanes(lanes)


    def port_split(self, child_ports):
        if child_ports == 1:
            return self
        child_port_list = []
        port_num = self.get_port_num()
        num_lanes = len(self._lanes)
        offset = num_lanes/child_ports;
        lanes_per_child = offset
        for i in range(child_ports):
            child_port_num = port_num + (i * offset)
            child_port_name = "Ethernet%d"%(child_port_num) 
            child_port_alias = "Eth%d/%d"%(port_num, child_port_num)
            child_port_lanes = []
            for j in range(lanes_per_child):
                child_port_lanes.append(self._lanes[(i*offset)+j])
            child_port_speed = self._speed/child_ports
            child_port_index = self._index

            child_port = Port(self._dvs, child_port_name)
            child_port.set_alias(child_port_alias)
            child_port.set_speed(child_port_speed)
            child_port.set_lanes(child_port_lanes)
            child_port.set_index(child_port_index)
            child_port_list.append(child_port)
        return child_port_list

    def delete_from_config_db(self):
        self._cfg_db_ptbl._del(self.get_name())
        self._oid = None

    def sync_from_config_db(self):
        (status, fvs) = self._cfg_db_ptbl.get(self.get_name())
        assert status == True
        fvs_dict = self.get_fvs_dict(fvs)
        self.set_alias(fvs_dict['alias'])
        self.set_speed(int(fvs_dict['speed']))
        self.set_lanes(list(fvs_dict['lanes'].split(",")))
        self.set_index(int(fvs_dict['index']))

    def write_to_config_db(self):
        lanes_str = self.get_lanes_db_str() 
        index_str = str(self.get_index())
        alias_str = self.get_alias() 
        speed_str = str(self.get_speed())
        fvs = swsscommon.FieldValuePairs([("alias", alias_str),
                                          ("lanes", lanes_str),
                                          ("speed", speed_str),
                                          ("index", index_str)])
        self._cfg_db_ptbl.set(self.get_name(), fvs)

    def get_fvs_dict(self, fvs):
        fvs_dict = {}
        for fv in fvs:
            fvs_dict.update({fv[0]:fv[1]})
        return fvs_dict

    def exists_in_config_db(self):
        (status, _) = self._cfg_db_ptbl.get(self.get_name())
        return status

    def exists_in_app_db(self):
        (status, _) = self._app_db_ptbl.get(self.get_name())
        return status

    def exists_in_asic_db(self):
        if self._oid is None:
            counter_redis_conn = redis.Redis(unix_socket_path=self._dvs.redis_sock, db=swsscommon.COUNTERS_DB)
            self._oid = counter_redis_conn.hget("COUNTERS_PORT_NAME_MAP", self.get_name())
            if self._oid is None:
                return False
        (status, _) = self._asic_db_ptbl.get(self._oid)
        return status

    def verify_config_db(self):
        (status, fvs) = self._cfg_db_ptbl.get(self.get_name())
        assert(status == True)
        fvs_dict = self.get_fvs_dict(fvs)
        assert(fvs_dict['alias'] == self.get_alias())
        assert(fvs_dict['lanes'] == self.get_lanes_db_str())
        assert(fvs_dict['speed'] == str(self.get_speed()))
        assert(fvs_dict['index'] == str(self.get_index()))

    def verify_app_db(self):
        (status, fvs) = self._app_db_ptbl.get(self.get_name())
        assert(status == True)
        fvs_dict = self.get_fvs_dict(fvs)
        assert(fvs_dict['alias'] == self.get_alias())
        assert(fvs_dict['lanes'] == self.get_lanes_db_str())
        assert(fvs_dict['speed'] == str(self.get_speed()))
        assert(fvs_dict['index'] == str(self.get_index()))

    def verify_asic_db(self):
        (status, fvs) = self._asic_db_ptbl.get(self.get_oid())
        assert(status == True)
        fvs_dict = self.get_fvs_dict(fvs)
        if (fvs_dict.has_key("SAI_PORT_ATTR_HW_LANE_LIST")):
            assert(fvs_dict['SAI_PORT_ATTR_HW_LANE_LIST'] == self.get_lanes_asic_db_str())
        assert(fvs_dict['SAI_PORT_ATTR_SPEED'] == str(self.get_speed()))

