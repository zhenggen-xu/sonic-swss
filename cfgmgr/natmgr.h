/*
 * Copyright 2019 Broadcom Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef __NATMGR__
#define __NATMGR__

#include "dbconnector.h"
#include "producerstatetable.h"
#include "orch.h"
#include "notificationproducer.h"

#include <set>
#include <map>
#include <string>

namespace swss {

#define STATIC_NAT_KEY_SIZE        1
#define LOCAL_IP                   "local_ip"
#define TRANSLATED_IP              "translated_ip"
#define NAT_TYPE                   "nat_type"
#define SNAT_NAT_TYPE              "snat"
#define DNAT_NAT_TYPE              "dnat"
#define TWICE_NAT_ID               "twice_nat_id"
#define TWICE_NAT_ID_MIN           1
#define TWICE_NAT_ID_MAX           9999
#define ENTRY_TYPE                 "entry_type"
#define STATIC_ENTRY_TYPE          "static"
#define DYNAMIC_ENTRY_TYPE         "dynamic" 
#define STATIC_NAPT_KEY_SIZE       3
#define LOCAL_PORT                 "local_port"
#define TRANSLATED_L4_PORT         "translated_l4_port"
#define TRANSLATED_SRC_IP          "translated_src_ip"
#define TRANSLATED_SRC_L4_PORT     "translated_src_l4_port"
#define TRANSLATED_DST_IP          "translated_dst_ip"
#define TRANSLATED_DST_L4_PORT     "translated_dst_l4_port"
#define POOL_TABLE_KEY_SIZE        1
#define NAT_IP                     "nat_ip"
#define NAT_PORT                   "nat_port"
#define BINDING_TABLE_KEY_SIZE     1
#define NAT_POOL                   "nat_pool"
#define NAT_ACLS                   "access_list"
#define VALUES                     "Values"
#define NAT_ADMIN_MODE             "admin_mode"
#define NAT_ZONE                   "nat_zone"
#define NAT_TIMEOUT                "nat_timeout"
#define NAT_TIMEOUT_MIN            300
#define NAT_TIMEOUT_MAX            432000
#define NAT_TIMEOUT_DEFAULT        600
#define NAT_TCP_TIMEOUT            "nat_tcp_timeout"
#define NAT_TCP_TIMEOUT_MIN        300
#define NAT_TCP_TIMEOUT_MAX        432000
#define NAT_TCP_TIMEOUT_DEFAULT    86400
#define NAT_UDP_TIMEOUT            "nat_udp_timeout" 
#define NAT_UDP_TIMEOUT_MIN        120
#define NAT_UDP_TIMEOUT_MAX        600
#define NAT_UDP_TIMEOUT_DEFAULT    300
#define L3_INTERFACE_KEY_SIZE      2
#define L3_INTERFACE_ZONE_SIZE     1
#define VLAN_PREFIX                "Vlan"
#define LAG_PREFIX                 "PortChannel"
#define ETHERNET_PREFIX            "Ethernet"
#define LOOPBACK_PREFIX            "Loopback"
#define ACL_TABLE_KEY_SIZE         1
#define TABLE_TYPE                 "TYPE"
#define TABLE_STAGE                "STAGE"
#define TABLE_PORTS                "PORTS"
#define TABLE_TYPE_L3              "L3"
#define TABLE_STAGE_INGRESS        "INGRESS"
#define ACL_RULE_TABLE_KEY_SIZE    2
#define ACTION_PACKET_ACTION       "PACKET_ACTION"
#define PACKET_ACTION_FORWARD      "FORWARD"
#define PACKET_ACTION_DO_NOT_NAT   "DO_NOT_NAT"
#define MATCH_IP_TYPE              "IP_TYPE"
#define IP_TYPE_IP                 "IP"
#define IP_TYPE_IPv4ANY            "IPV4ANY"
#define RULE_PRIORITY              "PRIORITY"
#define MATCH_SRC_IP               "SRC_IP"
#define MATCH_DST_IP               "DST_IP"
#define MATCH_IP_PROTOCOL          "IP_PROTOCOL"
#define MATCH_IP_PROTOCOL_ICMP     1
#define MATCH_IP_PROTOCOL_TCP      6
#define MATCH_IP_PROTOCOL_UDP      17          
#define MATCH_L4_SRC_PORT          "L4_SRC_PORT"
#define MATCH_L4_DST_PORT          "L4_DST_PORT"
#define MATCH_L4_SRC_PORT_RANGE    "L4_SRC_PORT_RANGE"
#define MATCH_L4_DST_PORT_RANGE    "L4_DST_PORT_RANGE"
#define IP_PREFIX_SIZE             2
#define IP_ADDR_MASK_LEN_MIN       1
#define IP_ADDR_MASK_LEN_MAX       32
#define IP_PROTOCOL_ICMP           "icmp"
#define IP_PROTOCOL_TCP            "tcp"
#define IP_PROTOCOL_UDP            "udp"
#define L4_PORT_MIN                1
#define L4_PORT_MAX                65535
#define L4_PORT_RANGE_SIZE         2
#define EMPTY_STRING               ""
#define NONE_STRING                "None"
#define ADD                        "A"
#define INSERT                     "I"
#define DELETE                     "D"
#define ENABLED                    "enabled"
#define DISABLED                   "disabled"
#define IS_LOOPBACK_ADDR(ipaddr)   ((ipaddr & 0xFF000000) == 0x7F000000)
#define IS_MULTICAST_ADDR(ipaddr)  ((ipaddr >= 0xE0000000) and (ipaddr <= 0xEFFFFFFF))
#define IS_RESERVED_ADDR(ipaddr)   (ipaddr >= 0xF0000000)
#define IS_ZERO_ADDR(ipaddr)       (ipaddr == 0)
#define IS_BROADCAST_ADDR(ipaddr)  (ipaddr == 0xFFFFFFFF)

const char ip_address_delimiter = '/';

/* Pool Info */
typedef struct {
    string ip_range;
    string port_range;
} natPool_t;

/* Binding Info */
typedef struct {
    string pool_name;
    string acl_name;
    string nat_type;
    string twice_nat_id;
    string pool_interface;
    string acl_interface;
    string static_key;
    bool   twice_nat_added;
} natBinding_t;

/* Static NAT Entry Info */
typedef struct {
    string local_ip;
    string nat_type;
    string twice_nat_id;
    string interface;
    string binding_key;
    bool   twice_nat_added;
} staticNatEntry_t;

/* Static NAPT Entry Info */
typedef struct {
    string local_ip;
    string local_port;
    string nat_type;
    string twice_nat_id;
    string interface;
    string binding_key;
    bool   twice_nat_added;
} staticNaptEntry_t;

/* NAT ACL Table Rules Info */
typedef struct{
    string packet_action;
    uint32_t priority;
    string src_ip_range;
    string dst_ip_range;
    string src_l4_port_range;
    string dst_l4_port_range;
    string ip_protocol;
} natAclRule_t;

/* Containers to store NAT Info */

/* To store NAT Pool configuration,
 * Key is "Pool_name"
 * Value is "natPool_t"
 */
typedef std::map<std::string, natPool_t> natPool_map_t;

/* To store NAT Binding configuration,
 * Key is "Binding_name"
 * Value is "natBinding_t"
 */
typedef std::map<std::string, natBinding_t> natBinding_map_t;

/* To store Static NAT configuration,
 * Key is "Global_ip" (Eg. 65.55.45.1)
 * Value is "staticNatEntry_t"
 */
typedef std::map<std::string, staticNatEntry_t> staticNatEntry_map_t;

/* To store Static NAPT configuration,
 * Key is "Global_ip|ip_protocol|Global_port" (Eg. 65.55.45.1|TCP|500)
 * Value is "staticNaptEntry_t"
 */
typedef std::map<std::string, staticNaptEntry_t> staticNaptEntry_map_t;

/* To store NAT Ip Interface configuration,
 * Key is "Port" (Eg. Ethernet1)
 * Value is "ip_address_list" (Eg. 10.0.0.1/24,20.0.0.1/24)
 */
typedef std::map<std::string, vector<std::string>> natIpInterface_map_t;

/* To store NAT ACL Table configuration,
 * Key is "ACL_Table_Id" (Eg. 1)
 * Value is "ports" (Eg. Ethernet4,Vlan10)
 */
typedef std::map<std::string, std::string> natAclTable_map_t;

/* To store NAT ACL Rules configuration,
 * Key is "ACL_Tabel_Id|ACL_Rule_Id" (Eg. 1|1)
 * Value is "natAclRule_t"
 */
typedef std::map<std::string, natAclRule_t> natAclRule_map_t;

/* To store NAT Zone Interface configuration,
 * Key is "Port" (Eg. Ethernet1)
 * Value is "nat_zone" (Eg. "1")
 */
typedef std::map<std::string, std::string> natZoneInterface_map_t;

/* Define NatMgr Class inherited from Orch Class */
class NatMgr : public Orch
{
public:
    /* NatMgr Constructor */
    NatMgr(DBConnector *cfgDb, DBConnector *appDb, DBConnector *stateDb, const vector<string> &tableNames);
    using Orch::doTask; 

    /* Function to be called from signal handler on nat docker stop */
    void cleanupPoolIpTable(void);
   
private:
    /* Declare APPL_DB, CFG_DB and STATE_DB tables */
    ProducerStateTable m_appNatTableProducer, m_appNaptTableProducer, m_appNatGlobalTableProducer;
    ProducerStateTable m_appTwiceNatTableProducer, m_appTwiceNaptTableProducer;
    Table m_cfgStaticNatTable, m_cfgStaticNaptTable, m_cfgNatPoolTable, m_cfgNatBindingsTable, m_cfgNatGlobalTable;
    Table m_cfgNatAclTable, m_cfgNatAclRuleTable, m_appNaptPoolIpTable;
    Table m_cfgInterfaceTable, m_cfgLagInterfaceTable, m_cfgVlanInterfaceTable, m_cfgLoopbackInterfaceTable;
    Table m_statePortTable, m_stateLagTable, m_stateVlanTable, m_stateInterfaceTable;
    std::shared_ptr<swss::NotificationProducer> flushNotifier;

    /* Declare containers to store NAT Info */
    int     m_natTimeout;
    int     m_natTcpTimeout;
    int     m_natUdpTimeout;
    string  natAdminMode;

    natPool_map_t            m_natPoolInfo;
    natBinding_map_t         m_natBindingInfo;
    staticNatEntry_map_t     m_staticNatEntry;
    staticNaptEntry_map_t    m_staticNaptEntry;
    natIpInterface_map_t     m_natIpInterfaceInfo;
    natZoneInterface_map_t   m_natZoneInterfaceInfo;
    natAclTable_map_t        m_natAclTableInfo;
    natAclRule_map_t         m_natAclRuleInfo;

    /* Declare doTask related fucntions */
    void doTask(Consumer &consumer);
    void doStaticNatTask(Consumer &consumer);
    void doStaticNaptTask(Consumer &consumer);
    void doNatPoolTask(Consumer &consumer);
    void doNatBindingTask(Consumer &consumer);
    void doNatGlobalTask(Consumer &consumer);
    void doNatIpInterfaceTask(Consumer &consumer);
    void doNatAclTableTask(Consumer &consumer);
    void doNatAclRuleTask(Consumer &consumer);

    /* Declare all NAT functionality member functions*/
    void enableNatFeature(void);
    void disableNatFeature(void);
    void addConntrackSingleNatEntry(const string &key);
    void addConntrackSingleNaptEntry(const string &key);
    void deleteConntrackSingleNatEntry(const string &key);
    void deleteConntrackSingleNaptEntry(const string &key);
    void addConntrackTwiceNatEntry(const string &snatKey, const string &dnatKey);
    void addConntrackTwiceNaptEntry(const string &snatKey, const string &dnatKey);
    void deleteConntrackTwiceNatEntry(const string &snatKey, const string &dnatKey);
    void deleteConntrackTwiceNaptEntry(const string &snatKey, const string &dnatKey);
    void deleteConntrackDynamicEntries(const string &ip_range);
    void addStaticNatEntry(const string &key);
    void addStaticNaptEntry(const string &key);
    void addStaticSingleNatEntry(const string &key);
    void addStaticSingleNaptEntry(const string &key);
    void addStaticTwiceNatEntry(const string &key);
    void addStaticTwiceNaptEntry(const string &key);
    void removeStaticNatEntry(const string &key);
    void removeStaticNaptEntry(const string &key);
    void removeStaticSingleNatEntry(const string &key);
    void removeStaticSingleNaptEntry(const string &key);
    void removeStaticTwiceNatEntry(const string &key);
    void removeStaticTwiceNaptEntry(const string &key);
    void addStaticNatEntries(const string port = NONE_STRING, const string ipPrefix = NONE_STRING);
    void addStaticNaptEntries(const string port = NONE_STRING, const string ipPrefix = NONE_STRING);
    void removeStaticNatEntries(const string port = NONE_STRING, const string ipPrefix = NONE_STRING);
    void removeStaticNaptEntries(const string port= NONE_STRING, const string ipPrefix = NONE_STRING);
    void addDynamicNatRule(const string &key);
    void removeDynamicNatRule(const string &key);
    void addDynamicNatRuleByAcl(const string &key, bool isRuleId = false);
    void removeDynamicNatRuleByAcl(const string &key, bool isRuleId = false);
    void addDynamicNatRules(const string port = NONE_STRING, const string ipPrefix = NONE_STRING);
    void removeDynamicNatRules(const string port = NONE_STRING, const string ipPrefix = NONE_STRING);
    void addDynamicTwiceNatRule(const string &key);
    void deleteDynamicTwiceNatRule(const string &key);
    void setDynamicAllForwardOrAclbasedRules(const string &opCmd, const string &pool_interface, const string &ip_range,
                                             const string &port_range, const string &acls_name, const string &dynamicKey);

    bool isNatEnabled(void);
    bool isPortStateOk(const string &alias);
    bool isIntfStateOk(const string &alias); 
    bool isPoolMappedtoBinding(const string &pool_name, string &binding_name); 
    bool isMatchesWithStaticNat(const string &global_ip, string &local_ip);
    bool isMatchesWithStaticNapt(const string &global_ip, string &local_ip);
    bool isGlobalIpMatching(const string &intf_keys, const string &global_ip);
    bool getIpEnabledIntf(const string &global_ip, string &interface);
    void setNaptPoolIpTable(const string &opCmd, const string &nat_ip, const string &nat_port);
    bool setFullConeDnatIptablesRule(const string &opCmd);
    bool setMangleIptablesRules(const string &opCmd, const string &interface, const string &nat_zone);
    bool setStaticNatIptablesRules(const string &opCmd, const string &interface, const string &external_ip, const string &internal_ip, const string &nat_type);
    bool setStaticNaptIptablesRules(const string &opCmd, const string &interface, const string &prototype, const string &external_ip, 
                                    const string &external_port, const string &internal_ip, const string &internal_port, const string &nat_type);
    bool setStaticTwiceNatIptablesRules(const string &opCmd, const string &interface, const string &src_ip, const string &translated_src_ip,
                                        const string &dest_ip, const string &translated_dest_ip);
    bool setStaticTwiceNaptIptablesRules(const string &opCmd, const string &interface, const string &prototype, const string &src_ip, const string &src_port,
                                         const string &translated_src_ip, const string &translated_src_port, const string &dest_ip, const string &dest_port,
                                         const string &translated_dest_ip, const string &translated_dest_port);
    bool setDynamicNatIptablesRulesWithAcl(const string &opCmd, const string &interface, const string &external_ip,
                                           const string &external_port_range, natAclRule_t &natAclRuleId, const string &static_key);
    bool setDynamicNatIptablesRulesWithoutAcl(const string &opCmd, const string &interface, const string &external_ip,
                                              const string &external_port_range, const string &static_key);

};

}

#endif
