#include <cassert>
#include <fstream>
#include <sstream>
#include <map>
#include <net/if.h>
#include <inttypes.h>

#include "sai_serialize.h"
#include "intfsorch.h"
#include "ipprefix.h"
#include "logger.h"
#include "swssnet.h"
#include "tokenize.h"
#include "routeorch.h"
#include "crmorch.h"
#include "bufferorch.h"
#include "directory.h"
#include "vnetorch.h"

extern sai_object_id_t gVirtualRouterId;
extern Directory<Orch*> gDirectory;

extern sai_router_interface_api_t*  sai_router_intfs_api;
extern sai_route_api_t*             sai_route_api;
extern sai_neighbor_api_t*          sai_neighbor_api;

extern sai_object_id_t gSwitchId;
extern PortsOrch *gPortsOrch;
extern RouteOrch *gRouteOrch;
extern CrmOrch *gCrmOrch;
extern BufferOrch *gBufferOrch;

const int intfsorch_pri = 35;

#define RIF_FLEX_STAT_COUNTER_POLL_MSECS "1000"
#define UPDATE_MAPS_SEC 1

#define LOOPBACK_PREFIX     "Loopback"

static const vector<sai_router_interface_stat_t> rifStatIds =
{
    SAI_ROUTER_INTERFACE_STAT_IN_PACKETS,
    SAI_ROUTER_INTERFACE_STAT_IN_OCTETS,
    SAI_ROUTER_INTERFACE_STAT_IN_ERROR_PACKETS,
    SAI_ROUTER_INTERFACE_STAT_IN_ERROR_OCTETS,
    SAI_ROUTER_INTERFACE_STAT_OUT_PACKETS,
    SAI_ROUTER_INTERFACE_STAT_OUT_OCTETS,
    SAI_ROUTER_INTERFACE_STAT_OUT_ERROR_PACKETS,
    SAI_ROUTER_INTERFACE_STAT_OUT_ERROR_OCTETS,
};

IntfsOrch::IntfsOrch(DBConnector *db, string tableName, VRFOrch *vrf_orch) :
        Orch(db, tableName, intfsorch_pri), m_vrfOrch(vrf_orch)
{
    SWSS_LOG_ENTER();

    /* Initialize DB connectors */ 
    m_counter_db = shared_ptr<DBConnector>(new DBConnector(COUNTERS_DB, DBConnector::DEFAULT_UNIXSOCKET, 0));
    m_flex_db = shared_ptr<DBConnector>(new DBConnector(FLEX_COUNTER_DB, DBConnector::DEFAULT_UNIXSOCKET, 0));
    m_asic_db = shared_ptr<DBConnector>(new DBConnector(ASIC_DB, DBConnector::DEFAULT_UNIXSOCKET, 0));
    /* Initialize COUNTER_DB tables */
    m_rifNameTable = unique_ptr<Table>(new Table(m_counter_db.get(), COUNTERS_RIF_NAME_MAP));
    m_rifTypeTable = unique_ptr<Table>(new Table(m_counter_db.get(), COUNTERS_RIF_TYPE_MAP));

    m_vidToRidTable = unique_ptr<Table>(new Table(m_asic_db.get(), "VIDTORID"));
    auto intervT = timespec { .tv_sec = UPDATE_MAPS_SEC , .tv_nsec = 0 };
    m_updateMapsTimer = new SelectableTimer(intervT);
    auto executorT = new ExecutableTimer(m_updateMapsTimer, this, "UPDATE_MAPS_TIMER");
    Orch::addExecutor(executorT);
    /* Initialize FLEX_COUNTER_DB tables */
    m_flexCounterTable = unique_ptr<ProducerTable>(new ProducerTable(m_flex_db.get(), FLEX_COUNTER_TABLE));
    m_flexCounterGroupTable = unique_ptr<ProducerTable>(new ProducerTable(m_flex_db.get(), FLEX_COUNTER_GROUP_TABLE));

    vector<FieldValueTuple> fieldValues;
    fieldValues.emplace_back(POLL_INTERVAL_FIELD, RIF_FLEX_STAT_COUNTER_POLL_MSECS);
    fieldValues.emplace_back(STATS_MODE_FIELD, STATS_MODE_READ);
    m_flexCounterGroupTable->set(RIF_STAT_COUNTER_FLEX_COUNTER_GROUP, fieldValues);
}

sai_object_id_t IntfsOrch::getRouterIntfsId(const string &alias)
{
    Port port;
    gPortsOrch->getPort(alias, port);
    return port.m_rif_id;
}

bool IntfsOrch::isPrefixSubnet(const IpPrefix &ip_prefix, const string &alias)
{
    if (m_syncdIntfses.find(alias) == m_syncdIntfses.end())
    {
        return false;
    }
    for (auto &prefixIt: m_syncdIntfses[alias].ip_addresses)
    {
        if (prefixIt.getSubnet() == ip_prefix)
        {
            return true;
        }
    }
    return false;
}

string IntfsOrch::getRouterIntfsAlias(const IpAddress &ip, const string &vrf_name)
{
    sai_object_id_t vrf_id = gVirtualRouterId;

    if (!vrf_name.empty())
    {
        vrf_id = m_vrfOrch->getVRFid(vrf_name);
    }

    for (const auto &it_intfs: m_syncdIntfses)
    {
        if (it_intfs.second.vrf_id != vrf_id)
        {
            continue;
        }
        for (const auto &prefixIt: it_intfs.second.ip_addresses)
        {
            if (prefixIt.isAddressInSubnet(ip))
            {
                return it_intfs.first;
            }
        }
    }
    return string();
}

void IntfsOrch::increaseRouterIntfsRefCount(const string &alias)
{
    SWSS_LOG_ENTER();

    m_syncdIntfses[alias].ref_count++;
    SWSS_LOG_DEBUG("Router interface %s ref count is increased to %d",
                  alias.c_str(), m_syncdIntfses[alias].ref_count);
}

void IntfsOrch::decreaseRouterIntfsRefCount(const string &alias)
{
    SWSS_LOG_ENTER();

    m_syncdIntfses[alias].ref_count--;
    SWSS_LOG_DEBUG("Router interface %s ref count is decreased to %d",
                  alias.c_str(), m_syncdIntfses[alias].ref_count);
}

bool IntfsOrch::setRouterIntfsMtu(const Port &port)
{
    SWSS_LOG_ENTER();

    sai_attribute_t attr;
    attr.id = SAI_ROUTER_INTERFACE_ATTR_MTU;
    attr.value.u32 = port.m_mtu;

    sai_status_t status = sai_router_intfs_api->
            set_router_interface_attribute(port.m_rif_id, &attr);
    if (status != SAI_STATUS_SUCCESS)
    {
        SWSS_LOG_ERROR("Failed to set router interface %s MTU to %u, rv:%d",
                port.m_alias.c_str(), port.m_mtu, status);
        return false;
    }
    SWSS_LOG_NOTICE("Set router interface %s MTU to %u",
            port.m_alias.c_str(), port.m_mtu);
    return true;
}

bool IntfsOrch::setRouterIntfsAdminStatus(const Port &port)
{
    SWSS_LOG_ENTER();

    sai_attribute_t attr;
    attr.value.booldata = port.m_admin_state_up;

    attr.id = SAI_ROUTER_INTERFACE_ATTR_ADMIN_V4_STATE;
    sai_status_t status = sai_router_intfs_api->
            set_router_interface_attribute(port.m_rif_id, &attr);
    if (status != SAI_STATUS_SUCCESS)
    {
        SWSS_LOG_ERROR("Failed to set router interface %s V4 admin status to %s, rv:%d",
                port.m_alias.c_str(), port.m_admin_state_up == true ? "up" : "down", status);
        return false;
    }

    attr.id = SAI_ROUTER_INTERFACE_ATTR_ADMIN_V6_STATE;
    status = sai_router_intfs_api->
            set_router_interface_attribute(port.m_rif_id, &attr);
    if (status != SAI_STATUS_SUCCESS)
    {
        SWSS_LOG_ERROR("Failed to set router interface %s V6 admin status to %s, rv:%d",
                port.m_alias.c_str(), port.m_admin_state_up == true ? "up" : "down", status);
        return false;
    }

    return true;
}

set<IpPrefix> IntfsOrch:: getSubnetRoutes()
{
    SWSS_LOG_ENTER();

    set<IpPrefix> subnet_routes;

    for (auto it = m_syncdIntfses.begin(); it != m_syncdIntfses.end(); it++)
    {
        for (auto prefix : it->second.ip_addresses)
        {
            subnet_routes.emplace(prefix);
        }
    }

    return subnet_routes;
}

bool IntfsOrch::setIntf(const string& alias, sai_object_id_t vrf_id, const IpPrefix *ip_prefix, const bool adminUp, const uint32_t mtu)
{
    SWSS_LOG_ENTER();

    Port port;
    gPortsOrch->getPort(alias, port);

    auto it_intfs = m_syncdIntfses.find(alias);
    if (it_intfs == m_syncdIntfses.end())
    {
        if (!ip_prefix && addRouterIntfs(vrf_id, port))
        {
            gPortsOrch->increasePortRouterIntfRefCount(alias);
            IntfsEntry intfs_entry;
            intfs_entry.ref_count = 0;
            intfs_entry.vrf_id = vrf_id;
            m_syncdIntfses[alias] = intfs_entry;
            m_vrfOrch->increaseVrfRefCount(vrf_id);
        }
        else
        {
            return false;
        }
    }
    else
    {
        if (!ip_prefix && port.m_type == Port::SUBPORT)
        {
            // port represents a sub interface
            // Change sub interface config at run time
            bool attrChanged = false;
            if (mtu && port.m_mtu != mtu)
            {
                port.m_mtu = mtu;
                attrChanged = true;

                setRouterIntfsMtu(port);
            }

            if (port.m_admin_state_up != adminUp)
            {
                port.m_admin_state_up = adminUp;
                attrChanged = true;

                setRouterIntfsAdminStatus(port);
            }

            if (attrChanged)
            {
                gPortsOrch->setPort(alias, port);
            }
        }
    }

    if (!ip_prefix || m_syncdIntfses[alias].ip_addresses.count(*ip_prefix))
    {
        /* Request to create router interface, no prefix present or Duplicate entry */
        return true;
    }

    /* NOTE: Overlap checking is required to handle ifconfig weird behavior.
     * When set IP address using ifconfig command it applies it in two stages.
     * On stage one it sets IP address with netmask /8. On stage two it
     * changes netmask to specified in command. As DB is async event to
     * add IP address with original netmask may come before event to
     * delete IP with netmask /8. To handle this we in case of overlap
     * we should wait until entry with /8 netmask will be removed.
     * Time frame between those event is quite small.*/
    /* NOTE: Overlap checking in this interface is not enough.
     * So extend to check in all interfaces of this VRF */
    bool overlaps = false;
    for (const auto &intfsIt: m_syncdIntfses)
    {
        if (port.m_vr_id != intfsIt.second.vrf_id)
        {
            continue;
        }

        for (const auto &prefixIt: intfsIt.second.ip_addresses)
        {
            if (prefixIt.isAddressInSubnet(ip_prefix->getIp()) ||
                    ip_prefix->isAddressInSubnet(prefixIt.getIp()))
            {
                overlaps = true;
                SWSS_LOG_NOTICE("Router interface %s IP %s overlaps with %s.", port.m_alias.c_str(),
                        prefixIt.to_string().c_str(), ip_prefix->to_string().c_str());
                break;
            }
        }

        if (overlaps)
        {
            /* Overlap of IP address network */
            return false;
        }
    }

    addIp2MeRoute(port.m_vr_id, *ip_prefix);

    if (port.m_type == Port::VLAN)
    {
        addDirectedBroadcast(port, *ip_prefix);
    }

    m_syncdIntfses[alias].ip_addresses.insert(*ip_prefix);
    return true;
}

bool IntfsOrch::removeIntf(const string& alias, sai_object_id_t vrf_id, const IpPrefix *ip_prefix)
{
    SWSS_LOG_ENTER();

    Port port;
    if (!gPortsOrch->getPort(alias, port))
    {
        return false;
    }

    if (ip_prefix && m_syncdIntfses[alias].ip_addresses.count(*ip_prefix))
    {
        removeIp2MeRoute(port.m_vr_id, *ip_prefix);

        if(port.m_type == Port::VLAN)
        {
            removeDirectedBroadcast(port, *ip_prefix);
        }

        m_syncdIntfses[alias].ip_addresses.erase(*ip_prefix);
    }

    if (!ip_prefix)
    {
        if (m_syncdIntfses[alias].ip_addresses.size() == 0 && removeRouterIntfs(port))
        {
            gPortsOrch->decreasePortRouterIntfRefCount(alias);
            m_syncdIntfses.erase(alias);
            m_vrfOrch->decreaseVrfRefCount(vrf_id);

            if (port.m_type == Port::SUBPORT)
            {
                if (!gPortsOrch->removeSubPort(alias))
                {
                    return false;
                }
            }

            return true;
        }
        else
        {
            return false;
        }
    }

    return true;
}

void IntfsOrch::doTask(Consumer &consumer)
{
    SWSS_LOG_ENTER();

    if (!gPortsOrch->allPortsReady())
    {
        return;
    }

    auto it = consumer.m_toSync.begin();
    while (it != consumer.m_toSync.end())
    {
        KeyOpFieldsValuesTuple t = it->second;

        vector<string> keys = tokenize(kfvKey(t), ':');
        string alias(keys[0]);

        bool isSubIntf = false;
        size_t found = alias.find(VLAN_SUB_INTERFACE_SEPARATOR);
        if (found != string::npos)
        {
            isSubIntf = true;
        }

        IpPrefix ip_prefix;
        bool ip_prefix_in_key = false;
        bool is_lo = !alias.compare(0, strlen(LOOPBACK_PREFIX), LOOPBACK_PREFIX);

        if (keys.size() > 1)
        {
            ip_prefix = kfvKey(t).substr(kfvKey(t).find(':')+1);
            ip_prefix_in_key = true;
        }

        const vector<FieldValueTuple>& data = kfvFieldsValues(t);
        string vrf_name = "", vnet_name = "";
        uint32_t mtu;
        bool adminUp;
        for (auto idx : data)
        {
            const auto &field = fvField(idx);
            const auto &value = fvValue(idx);
            if (field == "vrf_name")
            {
                vrf_name = value;
            }
            else if (field == "vnet_name")
            {
                vnet_name = value;
            }
            else if (field == "mtu")
            {
                try
                {
                    mtu = static_cast<uint32_t>(stoul(value));
                }
                catch (const std::invalid_argument &e)
                {
                    SWSS_LOG_ERROR("Invalid argument %s to %s()", value.c_str(), e.what());
                    continue;
                }
                catch (const std::out_of_range &e)
                {
                    SWSS_LOG_ERROR("Out of range argument %s to %s()", value.c_str(), e.what());
                    continue;
                }
            }
            else if (field == "admin_status")
            {
                if (value == "up")
                {
                    adminUp = true;
                }
                else
                {
                    adminUp = false;

                    if (value != "down")
                    {
                        SWSS_LOG_WARN("Sub interface %s unknown admin status %s", alias.c_str(), value.c_str());
                    }
                }
            }
        }

        if (alias == "eth0" || alias == "docker0")
        {
            it = consumer.m_toSync.erase(it);
            continue;
        }

        sai_object_id_t vrf_id = gVirtualRouterId;
        if (!vrf_name.empty())
        {
            if (!m_vrfOrch->isVRFexists(vrf_name))
            {
                it++;
                continue;
            }
            vrf_id = m_vrfOrch->getVRFid(vrf_name);
        }

        string op = kfvOp(t);
        if (op == SET_COMMAND)
        {
            if (is_lo)
            {
                if (!ip_prefix_in_key)
                {
                    if (m_syncdIntfses.find(alias) == m_syncdIntfses.end())
                    {
                        IntfsEntry intfs_entry;
                        intfs_entry.ref_count = 0;
                        intfs_entry.vrf_id = vrf_id;
                        m_syncdIntfses[alias] = intfs_entry;
                        m_vrfOrch->increaseVrfRefCount(vrf_id);
                    }
                }
                else
                {
                    if (m_syncdIntfses.find(alias) == m_syncdIntfses.end())
                    {
                        it++;
                        continue;
                    }
                    if (m_syncdIntfses[alias].ip_addresses.count(ip_prefix) == 0)
                    {
                        m_syncdIntfses[alias].ip_addresses.insert(ip_prefix);
                        addIp2MeRoute(m_syncdIntfses[alias].vrf_id, ip_prefix);
                    }
                }

                it = consumer.m_toSync.erase(it);
                continue;
            }

            Port port;
            if (!gPortsOrch->getPort(alias, port))
            {
                if (isSubIntf)
                {
                    if (!gPortsOrch->addSubPort(port, alias, adminUp, mtu))
                    {
                        it++;
                        continue;
                    }
                }
                else
                {
                    /* TODO: Resolve the dependency relationship and add ref_count to port */
                    it++;
                    continue;
                }
            }

            if (m_vnetInfses.find(alias) != m_vnetInfses.end())
            {
                vnet_name = m_vnetInfses.at(alias);
            }

            if (!vnet_name.empty())
            {
                VNetOrch* vnet_orch = gDirectory.get<VNetOrch*>();
                if (!vnet_orch->isVnetExists(vnet_name))
                {
                    it++;
                    continue;
                }
                if (!vnet_orch->setIntf(alias, vnet_name, ip_prefix_in_key ? &ip_prefix : nullptr, adminUp, mtu))
                {
                    it++;
                    continue;
                }

                if (m_vnetInfses.find(alias) == m_vnetInfses.end())
                {
                    m_vnetInfses.emplace(alias, vnet_name);
                }
            }
            else
            {
                if (!setIntf(alias, vrf_id, ip_prefix_in_key ? &ip_prefix : nullptr, adminUp, mtu))
                {
                    it++;
                    continue;
                }
            }

            it = consumer.m_toSync.erase(it);
        }
        else if (op == DEL_COMMAND)
        {
            if (is_lo)
            {
                if (!ip_prefix_in_key)
                {
                    if (m_syncdIntfses.find(alias) != m_syncdIntfses.end())
                    {
                        if (m_syncdIntfses[alias].ip_addresses.size() == 0)
                        {
                            m_vrfOrch->decreaseVrfRefCount(m_syncdIntfses[alias].vrf_id);
                            m_syncdIntfses.erase(alias);
                        }
                        else
                        {
                            it++;
                            continue;
                        }
                    }
                }
                else
                {
                    if (m_syncdIntfses.find(alias) != m_syncdIntfses.end())
                    {
                        if (m_syncdIntfses[alias].ip_addresses.count(ip_prefix))
                        {
                            m_syncdIntfses[alias].ip_addresses.erase(ip_prefix);
                            removeIp2MeRoute(m_syncdIntfses[alias].vrf_id, ip_prefix);
                        }
                    }
                }

                it = consumer.m_toSync.erase(it);
                continue;
            }

            Port port;
            /* Cannot locate interface */
            if (!gPortsOrch->getPort(alias, port))
            {
                it = consumer.m_toSync.erase(it);
                continue;
            }

            if (m_syncdIntfses.find(alias) == m_syncdIntfses.end())
            {
                /* Cannot locate the interface */
                it = consumer.m_toSync.erase(it);
                continue;
            }

            if (m_vnetInfses.find(alias) != m_vnetInfses.end())
            {
                vnet_name = m_vnetInfses.at(alias);
            }

            if (!vnet_name.empty())
            {
                VNetOrch* vnet_orch = gDirectory.get<VNetOrch*>();
                if (!vnet_orch->isVnetExists(vnet_name))
                {
                    it++;
                    continue;
                }

                if (vnet_orch->delIntf(alias, vnet_name, ip_prefix_in_key ? &ip_prefix : nullptr))
                {
                    m_vnetInfses.erase(alias);
                    it = consumer.m_toSync.erase(it);
                }
                else
                {
                    it++;
                    continue;
                }
            }
            else
            {
                if (removeIntf(alias, port.m_vr_id, ip_prefix_in_key ? &ip_prefix : nullptr))
                {
                    it = consumer.m_toSync.erase(it);
                }
                else
                {
                    it++;
                    continue;
                }
            }
        }
    }
}

bool IntfsOrch::addRouterIntfs(sai_object_id_t vrf_id, Port &port)
{
    SWSS_LOG_ENTER();

    /* Return true if the router interface exists */
    if (port.m_rif_id)
    {
        SWSS_LOG_WARN("Router interface already exists on %s",
                      port.m_alias.c_str());
        return true;
    }

    /* Create router interface if the router interface doesn't exist */
    sai_attribute_t attr;
    vector<sai_attribute_t> attrs;

    attr.id = SAI_ROUTER_INTERFACE_ATTR_VIRTUAL_ROUTER_ID;
    attr.value.oid = vrf_id;
    attrs.push_back(attr);

    attr.id = SAI_ROUTER_INTERFACE_ATTR_SRC_MAC_ADDRESS;
    memcpy(attr.value.mac, gMacAddress.getMac(), sizeof(sai_mac_t));
    attrs.push_back(attr);

    attr.id = SAI_ROUTER_INTERFACE_ATTR_TYPE;
    switch(port.m_type)
    {
        case Port::PHY:
        case Port::LAG:
            attr.value.s32 = SAI_ROUTER_INTERFACE_TYPE_PORT;
            attrs.push_back(attr);
            break;
        case Port::VLAN:
            attr.value.s32 = SAI_ROUTER_INTERFACE_TYPE_VLAN;
            attrs.push_back(attr);
            break;
        case Port::SUBPORT:
            attr.value.s32 = SAI_ROUTER_INTERFACE_TYPE_SUB_PORT;
            attrs.push_back(attr);
            break;
        default:
            SWSS_LOG_ERROR("Unsupported port type: %d", port.m_type);
            break;
    }

    switch(port.m_type)
    {
        case Port::PHY:
            attr.id = SAI_ROUTER_INTERFACE_ATTR_PORT_ID;
            attr.value.oid = port.m_port_id;
            attrs.push_back(attr);
            break;
        case Port::LAG:
            attr.id = SAI_ROUTER_INTERFACE_ATTR_PORT_ID;
            attr.value.oid = port.m_lag_id;
            attrs.push_back(attr);
            break;
        case Port::VLAN:
            attr.id = SAI_ROUTER_INTERFACE_ATTR_VLAN_ID;
            attr.value.oid = port.m_vlan_info.vlan_oid;
            attrs.push_back(attr);
            break;
        case Port::SUBPORT:
            attr.id = SAI_ROUTER_INTERFACE_ATTR_PORT_ID;
            attr.value.oid = port.m_parent_port_id;
            attrs.push_back(attr);

            attr.id = SAI_ROUTER_INTERFACE_ATTR_OUTER_VLAN_ID;
            attr.value.u16 = port.m_vlan_info.vlan_id;
            attrs.push_back(attr);

            attr.id = SAI_ROUTER_INTERFACE_ATTR_ADMIN_V4_STATE;
            attr.value.booldata = port.m_admin_state_up;
            attrs.push_back(attr);

            attr.id = SAI_ROUTER_INTERFACE_ATTR_ADMIN_V6_STATE;
            attr.value.booldata = port.m_admin_state_up;
            attrs.push_back(attr);
            break;
        default:
            SWSS_LOG_ERROR("Unsupported port type: %d", port.m_type);
            break;
    }

    attr.id = SAI_ROUTER_INTERFACE_ATTR_MTU;
    attr.value.u32 = port.m_mtu;
    attrs.push_back(attr);

    sai_status_t status = sai_router_intfs_api->create_router_interface(&port.m_rif_id, gSwitchId, (uint32_t)attrs.size(), attrs.data());
    if (status != SAI_STATUS_SUCCESS)
    {
        SWSS_LOG_ERROR("Failed to create router interface %s, rv:%d",
                port.m_alias.c_str(), status);
        throw runtime_error("Failed to create router interface.");
    }

    port.m_vr_id = vrf_id;

    gPortsOrch->setPort(port.m_alias, port);
    m_rifsToAdd.push_back(port);

    SWSS_LOG_NOTICE("Create router interface %s MTU %u", port.m_alias.c_str(), port.m_mtu);

    return true;
}

bool IntfsOrch::removeRouterIntfs(Port &port)
{
    SWSS_LOG_ENTER();

    if (m_syncdIntfses[port.m_alias].ref_count > 0)
    {
        SWSS_LOG_NOTICE("Router interface is still referenced");
        return false;
    }

    const auto id = sai_serialize_object_id(port.m_rif_id);
    removeRifFromFlexCounter(id, port.m_alias);

    sai_status_t status = sai_router_intfs_api->remove_router_interface(port.m_rif_id);
    if (status != SAI_STATUS_SUCCESS)
    {
        SWSS_LOG_ERROR("Failed to remove router interface for port %s, rv:%d", port.m_alias.c_str(), status);
        throw runtime_error("Failed to remove router interface.");
    }

    port.m_rif_id = 0;
    port.m_vr_id = 0;
    gPortsOrch->setPort(port.m_alias, port);

    SWSS_LOG_NOTICE("Remove router interface for port %s", port.m_alias.c_str());

    return true;
}

void IntfsOrch::addIp2MeRoute(sai_object_id_t vrf_id, const IpPrefix &ip_prefix)
{
    sai_route_entry_t unicast_route_entry;
    unicast_route_entry.switch_id = gSwitchId;
    unicast_route_entry.vr_id = vrf_id;
    copy(unicast_route_entry.destination, ip_prefix.getIp());

    sai_attribute_t attr;
    vector<sai_attribute_t> attrs;

    attr.id = SAI_ROUTE_ENTRY_ATTR_PACKET_ACTION;
    attr.value.s32 = SAI_PACKET_ACTION_FORWARD;
    attrs.push_back(attr);

    Port cpu_port;
    gPortsOrch->getCpuPort(cpu_port);

    attr.id = SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID;
    attr.value.oid = cpu_port.m_port_id;
    attrs.push_back(attr);

    sai_status_t status = sai_route_api->create_route_entry(&unicast_route_entry, (uint32_t)attrs.size(), attrs.data());
    if (status != SAI_STATUS_SUCCESS)
    {
        SWSS_LOG_ERROR("Failed to create IP2me route ip:%s, rv:%d", ip_prefix.getIp().to_string().c_str(), status);
        throw runtime_error("Failed to create IP2me route.");
    }

    SWSS_LOG_NOTICE("Create IP2me route ip:%s", ip_prefix.getIp().to_string().c_str());

    if (unicast_route_entry.destination.addr_family == SAI_IP_ADDR_FAMILY_IPV4)
    {
        gCrmOrch->incCrmResUsedCounter(CrmResourceType::CRM_IPV4_ROUTE);
    }
    else
    {
        gCrmOrch->incCrmResUsedCounter(CrmResourceType::CRM_IPV6_ROUTE);
    }
}

void IntfsOrch::removeIp2MeRoute(sai_object_id_t vrf_id, const IpPrefix &ip_prefix)
{
    sai_route_entry_t unicast_route_entry;
    unicast_route_entry.switch_id = gSwitchId;
    unicast_route_entry.vr_id = vrf_id;
    copy(unicast_route_entry.destination, ip_prefix.getIp());

    sai_status_t status = sai_route_api->remove_route_entry(&unicast_route_entry);
    if (status != SAI_STATUS_SUCCESS)
    {
        SWSS_LOG_ERROR("Failed to remove IP2me route ip:%s, rv:%d", ip_prefix.getIp().to_string().c_str(), status);
        throw runtime_error("Failed to remove IP2me route.");
    }

    SWSS_LOG_NOTICE("Remove packet action trap route ip:%s", ip_prefix.getIp().to_string().c_str());

    if (unicast_route_entry.destination.addr_family == SAI_IP_ADDR_FAMILY_IPV4)
    {
        gCrmOrch->decCrmResUsedCounter(CrmResourceType::CRM_IPV4_ROUTE);
    }
    else
    {
        gCrmOrch->decCrmResUsedCounter(CrmResourceType::CRM_IPV6_ROUTE);
    }
}

void IntfsOrch::addDirectedBroadcast(const Port &port, const IpPrefix &ip_prefix)
{
    sai_status_t status;
    sai_neighbor_entry_t neighbor_entry;
    IpAddress ip_addr;

    /* If not IPv4 subnet or if /31 or /32 subnet, there is no broadcast address, hence don't
     * add a broadcast route. */
    if (!(ip_prefix.isV4()) || (ip_prefix.getMaskLength() > 30))
    {
      return;
    }
    ip_addr =  ip_prefix.getBroadcastIp();

    neighbor_entry.rif_id = port.m_rif_id;
    neighbor_entry.switch_id = gSwitchId;
    copy(neighbor_entry.ip_address, ip_addr);

    sai_attribute_t neighbor_attr;
    neighbor_attr.id = SAI_NEIGHBOR_ENTRY_ATTR_DST_MAC_ADDRESS;
    memcpy(neighbor_attr.value.mac, MacAddress("ff:ff:ff:ff:ff:ff").getMac(), 6);

    status = sai_neighbor_api->create_neighbor_entry(&neighbor_entry, 1, &neighbor_attr);
    if (status != SAI_STATUS_SUCCESS)
    {
        SWSS_LOG_ERROR("Failed to create broadcast entry %s rv:%d",
                       ip_addr.to_string().c_str(), status);
        return;
    }

    SWSS_LOG_NOTICE("Add broadcast route for ip:%s", ip_addr.to_string().c_str());
}

void IntfsOrch::removeDirectedBroadcast(const Port &port, const IpPrefix &ip_prefix)
{
    sai_status_t status;
    sai_neighbor_entry_t neighbor_entry;
    IpAddress ip_addr;

    /* If not IPv4 subnet or if /31 or /32 subnet, there is no broadcast address */
    if (!(ip_prefix.isV4()) || (ip_prefix.getMaskLength() > 30))
    {
        return;
    }
    ip_addr =  ip_prefix.getBroadcastIp();

    neighbor_entry.rif_id = port.m_rif_id;
    neighbor_entry.switch_id = gSwitchId;
    copy(neighbor_entry.ip_address, ip_addr);

    status = sai_neighbor_api->remove_neighbor_entry(&neighbor_entry);
    if (status != SAI_STATUS_SUCCESS)
    {
        if (status == SAI_STATUS_ITEM_NOT_FOUND)
        {
            SWSS_LOG_ERROR("No broadcast entry found for %s", ip_addr.to_string().c_str());
        }
        else
        {
            SWSS_LOG_ERROR("Failed to remove broadcast entry %s rv:%d",
                           ip_addr.to_string().c_str(), status);
        }
        return;
    }

    SWSS_LOG_NOTICE("Remove broadcast route ip:%s", ip_addr.to_string().c_str());
}

void IntfsOrch::addRifToFlexCounter(const string &id, const string &name, const string &type)
{
    SWSS_LOG_ENTER();
    /* update RIF maps in COUNTERS_DB */
    vector<FieldValueTuple> rifNameVector;
    vector<FieldValueTuple> rifTypeVector;

    rifNameVector.emplace_back(name, id);
    rifTypeVector.emplace_back(id, type);

    m_rifNameTable->set("", rifNameVector);
    m_rifTypeTable->set("", rifTypeVector);

    /* update RIF in FLEX_COUNTER_DB */
    string key = getRifFlexCounterTableKey(id);


    std::ostringstream counters_stream;
    for (const auto& it: rifStatIds)
    {
        counters_stream << sai_serialize_router_interface_stat(it) << comma;
    }

    /* check the state of intf, if registering the intf to FC will result in runtime error */
    vector<FieldValueTuple> fieldValues;
    fieldValues.emplace_back(RIF_COUNTER_ID_LIST, counters_stream.str());

    m_flexCounterTable->set(key, fieldValues);
    SWSS_LOG_DEBUG("Registered interface %s to Flex counter", name.c_str());
}

void IntfsOrch::removeRifFromFlexCounter(const string &id, const string &name)
{
    SWSS_LOG_ENTER();
    /* remove it from COUNTERS_DB maps */
    m_rifNameTable->hdel("", name);
    m_rifTypeTable->hdel("", id);

    /* remove it from FLEX_COUNTER_DB */
    string key = getRifFlexCounterTableKey(id);

    m_flexCounterTable->del(key);
    SWSS_LOG_DEBUG("Unregistered interface %s from Flex counter", name.c_str());
}

string IntfsOrch::getRifFlexCounterTableKey(string key)
{
    return string(RIF_STAT_COUNTER_FLEX_COUNTER_GROUP) + ":" + key;
}

void IntfsOrch::generateInterfaceMap()
{
    m_updateMapsTimer->start();
}

void IntfsOrch::doTask(SelectableTimer &timer)
{
    SWSS_LOG_ENTER();

    SWSS_LOG_DEBUG("Registering %" PRId64 " new intfs", m_rifsToAdd.size());
    string value;
    for (auto it = m_rifsToAdd.begin(); it != m_rifsToAdd.end(); )
    {
        const auto id = sai_serialize_object_id(it->m_rif_id);
        SWSS_LOG_INFO("Registering %s, id %s", it->m_alias.c_str(), id.c_str());
        std::string type;
        switch(it->m_type)
        {
            case Port::PHY:
            case Port::LAG:
                type = "SAI_ROUTER_INTERFACE_TYPE_PORT";
                break;
            case Port::VLAN:
                type = "SAI_ROUTER_INTERFACE_TYPE_VLAN";
                break;
            case Port::SUBPORT:
                type = "SAI_ROUTER_INTERFACE_TYPE_SUB_PORT";
                break;
            default:
                SWSS_LOG_ERROR("Unsupported port type: %d", it->m_type);
                type = "";
                break;
        }
        if (m_vidToRidTable->hget("", id, value))
        {
            SWSS_LOG_INFO("Registering %s it is ready", it->m_alias.c_str());
            addRifToFlexCounter(id, it->m_alias, type);
            it = m_rifsToAdd.erase(it);
        }
        else
        {
            ++it;
        }
    }
}
