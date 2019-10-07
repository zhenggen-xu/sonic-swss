#include "logger.h"
#include "dbconnector.h"
#include "producerstatetable.h"
#include "tokenize.h"
#include "ipprefix.h"
#include "portmgr.h"
#include "exec.h"
#include "shellcmd.h"

using namespace std;
using namespace swss;

PortMgr::PortMgr(DBConnector *cfgDb, DBConnector *appDb, DBConnector *stateDb, const vector<string> &tableNames) :
        Orch(cfgDb, tableNames),
        m_cfgPortTable(cfgDb, CFG_PORT_TABLE_NAME),
        m_cfgLagMemberTable(cfgDb, CFG_LAG_MEMBER_TABLE_NAME),
        m_statePortTable(stateDb, STATE_PORT_TABLE_NAME),
        m_appPortTable(appDb, APP_PORT_TABLE_NAME)
{
}

bool PortMgr::setPortMtu(const string &alias, const string &mtu)
{
    stringstream cmd;
    string res;

    // ip link set dev <port_name> mtu <mtu>
    cmd << IP_CMD << " link set dev " << alias << " mtu " << mtu;
    EXEC_WITH_ERROR_THROW(cmd.str(), res);

    return true;
}

bool PortMgr::setPortAdminStatus(const string &alias, const bool up)
{
    stringstream cmd;
    string res;

    // ip link set dev <port_name> [up|down]
    cmd << IP_CMD << " link set dev " << alias << (up ? " up" : " down");
    EXEC_WITH_ERROR_THROW(cmd.str(), res);

    return true;
}

bool PortMgr::isPortStateOk(const string &alias)
{
    vector<FieldValueTuple> temp;

    if (m_statePortTable.get(alias, temp))
    {
        SWSS_LOG_INFO("Port %s is ready", alias.c_str());
        return true;
    }

    return false;
}

// This function set the default value of the kernelsettings' field
// to fvs if the field does not exist in fvs
void PortMgr::constructKernelSettings(const KernelSettingMap &kernelsettings,
  vector<FieldValueTuple> &fvs)
{
    bool found = false;

    for (auto it : kernelsettings)
    {
        for (auto i : fvs)
        {
            if (fvField(i) == it.first)
            {
                found = true;
                break;
            }
        }

        if (!found)
        {
            FieldValueTuple fv(it.first, it.second);
            fvs.push_back(fv);
        }
    }

    return;
}

// Get kernel settings from fvs if exist
void PortMgr::getKernelSettingsFromFVS(KernelSettingMap &kernelsettings,
  const vector<FieldValueTuple> &fvs)
{
    for (auto& it : kernelsettings)
    {
        for (auto i : fvs)
        {
            if (fvField(i) == it.first)
            {
                it.second = fvValue(i);
                break;
            }
        }
    }
}

bool PortMgr::saveKernelSettingsMap(const string alias,
    KernelSettingMap &kernelsettings)
{
    string admin_status = "admin_status";
    string mtu = "mtu";

    /* no need to update the map if no new settings*/
    if (kernelsettings[admin_status].empty()
        && kernelsettings[mtu].empty())
    {
        return false;
    }

    auto exist_kofvs = m_kernelSettingMap.find(alias);

    // no settings exist, use the new settings
    if (exist_kofvs == m_kernelSettingMap.end())
    {
        m_kernelSettingMap[alias] = kernelsettings;
        return true;
    }

    // update the old settings with new non-empty settings
    for (auto& newsettings : kernelsettings)
    {
        if (!newsettings.second.empty())
        {
            m_kernelSettingMap[alias][newsettings.first] = newsettings.second;
        }
    }

    return true;
}

void PortMgr::doConfigKernelSettings(string alias, KernelSettingMap settings)
{
    string mtu, admin_status;

    mtu = settings["mtu"];
    admin_status = settings["admin_status"];

    if (!mtu.empty())
    {
        setPortMtu(alias, mtu);
        SWSS_LOG_NOTICE("Configure %s MTU to %s", alias.c_str(), mtu.c_str());
    }

    if (!admin_status.empty())
    {
        setPortAdminStatus(alias, admin_status == "up");
        SWSS_LOG_NOTICE("Configure %s admin status to %s", alias.c_str(), admin_status.c_str());
    }
}

void PortMgr::doTask(Consumer &consumer)
{
    SWSS_LOG_ENTER();

    auto table = consumer.getTableName();

    auto it = consumer.m_toSync.begin();
    while (it != consumer.m_toSync.end())
    {
        KeyOpFieldsValuesTuple t = it->second;

        string alias = kfvKey(t);
        string op = kfvOp(t);
        auto fvs = kfvFieldsValues(t);

        if (op == SET_COMMAND)
        {
            map <string, string> kernelsecttings;

            kernelsecttings["admin_status"] = "";
            kernelsecttings["mtu"] = "";

            bool configured = (m_portList.find(alias) != m_portList.end());

            /* If this is the first time we set port settings
             * assign default admin status and mtu
             */
            if (!configured)
            {
                kernelsecttings["admin_status"] = DEFAULT_ADMIN_STATUS_STR;
                kernelsecttings["mtu"] = DEFAULT_MTU_STR;

                constructKernelSettings(kernelsecttings, fvs);
                m_portList.insert(alias);
            }

            // pass to appDB
            m_appPortTable.set(alias, fvs);

            // Save the settings to kernelsettingmap
            // Get from fvs first if exists
            getKernelSettingsFromFVS(kernelsecttings, fvs);

            // If new kernel configurations exists and portstate is ok, apply it now
            // Otherwise, it will be done in doKernelSettingTask()
            if (saveKernelSettingsMap(alias, kernelsecttings))
            {
                if (isPortStateOk(alias))
                {
                    doConfigKernelSettings(alias, m_kernelSettingMap[alias]);
                    m_kernelSettingMap.erase(alias);
                }
            }
        }

        it = consumer.m_toSync.erase(it);
    }
}

void PortMgr::doKernelSettingTask()
{
    SWSS_LOG_ENTER();

    auto it = m_kernelSettingMap.begin();
    while (it != m_kernelSettingMap.end())
    {
        string alias = it->first;
        auto settings = it->second;

        if (!isPortStateOk(alias))
        {
            SWSS_LOG_INFO("Port %s is not ready, retry later...", alias.c_str());
            it++;
            continue;
        }
        doConfigKernelSettings(alias, settings);
        it = m_kernelSettingMap.erase(it);
    }
}
