/*
 Beethowen
 Beethowen over ESPNow virtual sensors for ESPHome

 Author: Attila Farago

 */

#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"

#include "esphome/components/bthome_base/bthome_parser.h"

#include "esphome/components/beethowen_base/meshrc_bthome_over_espnow.h"

#include "beethowen_common.h"
#include "beethowen_device.h"
#include "beethowen_basesensor.h"
#include "beethowen_sensor.h"
#include "beethowen_hub.h"

using namespace std;

namespace esphome
{
  namespace beethowen
  {

    static const char *const TAG = "beethowen";

    void BeethowenHub::setup()
    {
      ESP_LOGCONFIG(TAG, "Setting up BeethowenHub...");

      beethowen_lib::begin(); // call it only once

      // setup wifinow hooks
      beethowen_lib::on_data([&](uint8_t *data, uint8_t size)
                             { this->beethowen_on_data_(data, size); });
      beethowen_lib::on_command([&](uint8_t command)
                                { this->beethowen_on_command_(command); });
    }

    void BeethowenHub::beethowen_on_command_(uint8_t command)
    {

#if ESPHOME_LOG_LEVEL >= ESPHOME_LOG_LEVEL_DEBUG
      ESP_LOGD(TAG, "Command received: %d, from: %s", command, addr_to_str(beethowen_lib::sender).c_str());
#endif // ESPHOME_LOG_LEVEL >= ESPHOME_LOG_LEVEL_DEBUG

      if (command == BeethowenCommand_FindServerRequest)
      {
        uint8_t *client_mac = beethowen_lib::sender;
        // BeethowenCommand_FoundServerResponse
        beethowen_lib::send_command_found(client_mac);
      }
    }

    void BeethowenHub::beethowen_on_data_(uint8_t *data, uint8_t size)
    {

      if ((this->get_role_option() & RoleOption_Destination) == RoleOption_Destination)
      {
        return;
      }

      // identify device by mac address -- destination devices (everything under my_devices -> my_sensors)
      const uint64_t address = addr_to_uint64(beethowen_lib::sender);
      BeethowenDevice *btdevice = NULL;
      for (auto btdevice_i : this->my_devices)
      {
        if (btdevice_i->match(address))
        {
          btdevice = btdevice_i;
          break;
        }
      }
      if (!btdevice && this->get_dump_option() == DumpOption_None)
        return;

#if ESPHOME_LOG_LEVEL >= ESPHOME_LOG_LEVEL_VERBOSE
      // log incoming packet
      std::string serviceData = "";
      for (auto i = 0; i < size; i++)
        serviceData += str_snprintf("%02X ", 3, data[i]);
      ESP_LOGV(TAG, "DATA received - %s = %s", addr64_to_str(beethowen_lib::sender).c_str(), serviceData.c_str());
#endif // ESPHOME_LOG_LEVEL_VERBOSE

      // parse the payload and report measurements in the callback, will be fixing this to V2
      bool device_header_reported = false;
      bthome_lib::parse_payload_bthome(
          data, size, bthome_lib::BTProtoVersion_BTHomeV2,
          [&](uint8_t measurement_type, float value)
          {
            this->report_measurement_(measurement_type, value, address, btdevice, device_header_reported);
          },
          [&](const char *message)
          {
            ESP_LOGD(TAG, "%s", message);
          });
    }

    void BeethowenHub::report_measurement_(uint8_t measurement_type, float value, uint64_t address, BeethowenDevice *btdevice, bool &device_header_reported)
    {

      bool matched = btdevice ? btdevice->report_measurement_(measurement_type, value) : false;

#if ESPHOME_LOG_LEVEL >= ESPHOME_LOG_LEVEL_DEBUG
      // show in debug log any unmatched packages based on the dump_options
      if (
          (this->get_dump_option() == DumpOption_All || (!matched && (this->get_dump_option() == DumpOption_Unmatched))) ||
          (btdevice != NULL &&
           (btdevice->get_dump_option() == DumpOption_All || (!matched && (btdevice->get_dump_option() == DumpOption_Unmatched)))))
      {

        if (!device_header_reported)
        {
          ESP_LOGD(TAG, "Data received from %s", addr64_to_str(address).c_str());
          device_header_reported = true;
        }

        ESP_LOGD(TAG, "beethowen reading from %s, measure_type: 0x%02x, value: %0.3f",
                 addr64_to_str(address).c_str(), measurement_type, value);
      }
#endif // ESPHOME_LOG_HAS_DEBUG
    }

  }
}