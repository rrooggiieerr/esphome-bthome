#pragma once

#include "esphome/core/component.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/esp32_ble_tracker/esp32_ble_tracker.h"

#include "lib/bthome_parser.h"

#include "bthome_common.h"
#include "bthome_device.h"
#include "bthome_basesensor.h"
#include "bthome_binarysensor.h"
#include "bthome_sensor.h"

#include <vector>
#include <map>
using namespace std;

#ifdef USE_ESP32

namespace esphome {
namespace bthome {

class BTHome : public Component, public esp32_ble_tracker::ESPBTDeviceListener
{
public:
  DumpOption_e get_dump_option() { return this->dump_option_; };
  void set_dump_option(DumpOption_e value) { this->dump_option_ = value; };

  bool parse_device(const esp32_ble_tracker::ESPBTDevice &device) override;
  float get_setup_priority() const override { return setup_priority::DATA; }

  void register_device(BTHomeDevice *btdevice) {
    this->my_devices.push_back(btdevice);
  }

  BTHomeDevice* register_sensor(BTHomeDevice *btdevice_in, uint64_t address, BTHomeBaseSensor *sensor) {

    // btdevice can be provied for sake of speed
    // if btdevice is not given then look for a matching device (by address)
    BTHomeDevice *btdevice = btdevice_in;
    if (!btdevice) {
      for (auto btdevice_i : this->my_devices) {
        if (btdevice_i->match(address)) {
          btdevice = btdevice_i;
          break;
        }
      }

      if (!btdevice) {
        btdevice = new BTHomeDevice();
        btdevice->set_address(address);
        this->register_device(btdevice);
      }
    }

    // register new btsensor for the btdevice
    btdevice->register_sensor(sensor);
    return btdevice;
  }

protected:
  bthomelib::BTProtoVersion_e parse_header_(const esp32_ble_tracker::ServiceData &service_data);
  bool parse_message_bthome_(const esp32_ble_tracker::ServiceData &service_data, const esp32_ble_tracker::ESPBTDevice &device, bthomelib::BTProtoVersion_e proto);
  void report_measurement_(uint8_t measurement_type, float value, uint64_t address, BTHomeDevice *btdevice);

private:
  DumpOption_e dump_option_{DumpOption_None};
  std::vector<BTHomeDevice *> my_devices;
};

}
}

#endif